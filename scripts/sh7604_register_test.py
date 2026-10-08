#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise actual SH7604 register methods, isolated from peripheral scheduling.

The fixture checks register access rules, not timer/DMA/serial timing. --source
allows the same assertions to be run against a previous revision.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile


def method(source, name):
    start = source.index("sh7604_device::" + name + "(")
    start = source.rfind("\n", 0, start) + 1
    brace = source.index("{", start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PREAMBLE = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
using offs_t = unsigned;
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define ACCESSING_BITS_0_31 ((mem_mask & 0xffffffffU) != 0)
#define ACCESSING_BITS_0_15 ((mem_mask & 0xffffU) != 0)
constexpr uint8_t ICF=0x80, OCFA=8, OCFB=4, OVF=2, CCLRA=1;
struct sh7604_device {
    uint32_t m_bcr1=0, m_bcr2=0, m_wcr=0, m_mcr=0, m_rtcsr=0, m_rtcnt=0, m_rtcor=0;
    bool m_is_slave=false;
    uint8_t m_tier=1, m_ftcsr=0, m_ftcsr_read_flags=0, m_sbycr=0;
    uint16_t m_wtcw[2]{}, m_wtcnt=0, m_wtcsr=0, m_rstcsr=0;
    bool m_wtcsr_ovf_read=false, m_rstcsr_wovf_read=false;
    struct { void adjust(int) {} } timer, *m_wdtimer=&timer;
    struct attotime { static constexpr int never=0; };
    void sh2_timer_resync() {} void sh2_timer_activate() {} void sh2_recalc_irq() {}
    void sh2_wtcnt_recalc() {} void sh2_wdt_activate() {}
    template<typename... T> void logerror(T...) {}
    // DECLARATIONS
};
'''

MAIN = r'''
int main() {
    sh7604_device d;
    using writer = void (sh7604_device::*)(offs_t, uint32_t, uint32_t);
    using reader = uint32_t (sh7604_device::*)();
    struct entry { writer w; reader r; uint32_t mask; };
    entry const entries[] = {
        {&sh7604_device::bcr1_w,&sh7604_device::bcr1_r,0x1ff7},
        {&sh7604_device::bcr2_w,&sh7604_device::bcr2_r,0xfc},
        {&sh7604_device::wcr_w,&sh7604_device::wcr_r,0xffff},
        {&sh7604_device::mcr_w,&sh7604_device::mcr_r,0xfefc},
        {&sh7604_device::rtcsr_w,&sh7604_device::rtcsr_r,0xf8},
        {&sh7604_device::rtcnt_w,&sh7604_device::rtcnt_r,0xff},
        {&sh7604_device::rtcor_w,&sh7604_device::rtcor_r,0xff}
    };
    for (auto const &e : entries) {
        (d.*e.w)(0,0xa55affff,0xffffffff);
        assert((d.*e.r)()==e.mask);
        for (uint32_t mask : {0xffU,0xffffU,0xffff0000U,0xff000000U}) {
            (d.*e.w)(0,0xa55a0000,mask);
            assert((d.*e.r)()==e.mask);
        }
        for (uint32_t key : {0U,0xa55b0000U,0xffff0000U}) {
            (d.*e.w)(0,key,0xffffffff);
            assert((d.*e.r)()==e.mask);
        }
        (d.*e.w)(0,0xa55a0000,0xffffffff);
        assert((d.*e.r)()==0);
    }
    d.m_is_slave=true; d.bcr1_w(0,0xa55a0000,0xffffffff);
    assert(d.bcr1_r()==0x8000);
    // Every byte value: reserved bits and the hardwired TIER bit.
    for (unsigned v=0; v<256; ++v) {
        d.tier_w(v); assert(d.tier_r()==((v&0x8e)|1));
        d.m_ftcsr=0; d.m_ftcsr_read_flags=0;
        d.ftcsr_w(v); assert(d.m_ftcsr==(v&1));
        d.fmr_sbycr_w(0,v,0xff); assert(d.m_sbycr==(v&0xdf));
    }
    d.m_ftcsr=0x8e; d.m_ftcsr_read_flags=0;
    d.ftcsr_w(0); assert(d.m_ftcsr==0x8e);
    d.m_ftcsr_read_flags=0x8e; d.ftcsr_w(0); assert(d.m_ftcsr==0);
    // A key left by a previous word must not authorize a later byte write.
    d.wtcnt_w(0,0x5a66,0xffff); assert(d.m_wtcnt==0x66);
    d.wtcnt_w(0,0x0077,0xff); assert(d.m_wtcnt==0x66);
    d.wtcnt_w(0,0x5a00,0xff00); assert(d.m_wtcnt==0x66);
    d.wtcnt_w(0,0x1266,0xffff); assert(d.m_wtcnt==0x66);
    d.rstcsr_w(0,0x5a60,0xffff); assert(d.m_rstcsr==0x60);
    d.rstcsr_w(0,0,0xff); assert(d.m_rstcsr==0x60);
    d.rstcsr_w(0,0x5a00,0xff00); assert(d.m_rstcsr==0x60);
    d.rstcsr_w(0,0x5a00,0xffff); assert(d.m_rstcsr==0);
    std::cout << "SH7604 register access/read-back fixture passed\n";
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("src/devices/cpu/sh/sh7604.cpp"))
    args = parser.parse_args()
    source = args.source.read_text()
    names = [n+s for n in ("bcr1", "bcr2", "wcr", "mcr", "rtcsr", "rtcnt", "rtcor", "tier") for s in ("_r", "_w")]
    names += ["ftcsr_w", "fmr_sbycr_w", "wtcnt_w", "rstcsr_w"]
    methods = [method(source, name) for name in names]
    declarations = "\n".join(m.split("{", 1)[0].replace("sh7604_device::", "").strip()+";" for m in methods)
    with tempfile.TemporaryDirectory(prefix="sh7604-register-") as tmp:
        path = Path(tmp)
        (path/"fixture.cpp").write_text(PREAMBLE.replace("// DECLARATIONS", declarations)+"\n"+"\n".join(methods)+MAIN)
        subprocess.run(["clang++", "-std=c++17", "-O1", "-g", "-fsanitize=address,undefined", str(path/"fixture.cpp"), "-o", str(path/"fixture")], check=True)
        subprocess.run([str(path/"fixture")], check=True)


if __name__ == "__main__":
    main()

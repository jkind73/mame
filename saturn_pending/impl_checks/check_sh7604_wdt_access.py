#!/usr/bin/env python3
"""WDT keyed word writes reject byte/partial accesses; method-level, unvalidated.

Real register handlers; timer/IRQ calls are recorded, not native execution.
This does not qualify longword accesses split by the address-space machinery.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
def extract(name):
    match = re.search(r'^void sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')
head = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <tuple>
#include <initializer_list>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
using offs_t=unsigned;
struct attotime { static constexpr int never=-1; };
struct Timer { int due=123; unsigned adjustments=0; void adjust(int t) { due=t; ++adjustments; } };
struct Device {
 uint8_t m_wtcnt=0x56,m_wtcsr=0xb9,m_rstcsr=0xe0;
 uint16_t m_wtcw[2]{0xa538,0xa500}; Timer timer; Timer *m_wdtimer=&timer;
 unsigned syncs=0,starts=0,irqs=0;
 void sh2_wtcnt_recalc() { ++syncs; }
 void sh2_wdt_activate() { ++starts; timer.adjust(456); }
 void sh2_recalc_irq() { ++irqs; }
 auto snapshot() const { return std::make_tuple(m_wtcnt,m_wtcsr,m_rstcsr,m_wtcw[0],m_wtcw[1],timer.due,timer.adjustments,syncs,starts,irqs); }
'''
tail = r'''
};
int main() {
 unsigned bytes=0,partials=0,words=0,sequences=0;
 for (unsigned target=0;target<2;++target)
 for (unsigned prior : {0xa500U,0xa580U,0x5a00U,0x5a60U,0U,0xffffU})
 for (unsigned value=0;value<256;++value) for (unsigned upper=0;upper<2;++upper) {
  Device d; d.m_wtcw[target]=prior; const auto before=d.snapshot();
  const uint16_t mask=upper?0xff00:0x00ff, data=upper?value<<8:value;
  if (target) d.rstcsr_w(0,data,mask); else d.wtcnt_w(0,data,mask);
  CHECK(d.snapshot()==before); ++bytes;
 }
 // No partial mask may combine with an earlier key. Arbitrary non-byte
 // masks here are defensive method inputs, not asserted CPU bus cycles.
 for (unsigned mask=0;mask<65535;++mask) for (unsigned target=0;target<2;++target) {
  Device d; const auto before=d.snapshot();
  if (target) d.rstcsr_w(0,0xa500,mask); else d.wtcnt_w(0,0x5a12,mask);
  CHECK(d.snapshot()==before); ++partials;
 }
 // Both byte orders must remain ineffective, including after a successful
 // keyed word left the old key in the implementation's command scratch.
 for (unsigned target=0;target<2;++target) for (unsigned order=0;order<2;++order)
 for (unsigned value=0;value<256;++value) {
  Device d;
  if (target) d.rstcsr_w(0,0x5a20,0xffff); else d.wtcnt_w(0,0x5aab,0xffff);
  const auto before=d.snapshot();
  for (unsigned part=0;part<2;++part) {
   const bool upper=bool(part^order); const uint16_t data=upper?0xa500:value, mask=upper?0xff00:0x00ff;
   if (target) d.rstcsr_w(0,data,mask); else d.wtcnt_w(0,data,mask);
  }
  CHECK(d.snapshot()==before); ++sequences;
 }
 // Complete words retain the existing key dispatch. These controls assert
 // no wider WDT timing/reset/read-qualified-flag acceptance.
 for (unsigned target=0;target<2;++target) for (unsigned data=0;data<65536;++data) {
  Device d;
  if (target) {
   d.rstcsr_w(0,data,0xffff);
   unsigned expect=0xe0;
   if ((data>>8)==0xa5 && !(data&0x80)) expect=0x60;
   if ((data>>8)==0x5a) expect=0x80|(data&0x60);
   CHECK(d.m_rstcsr==expect && d.m_wtcnt==0x56 && d.m_wtcsr==0xb9);
   CHECK(!d.syncs && !d.starts && !d.irqs && !d.timer.adjustments);
  } else {
   d.wtcnt_w(0,data,0xffff);
   if ((data>>8)==0x5a) {
    CHECK(d.m_wtcnt==(data&0xff) && d.m_wtcsr==0xb9 && d.starts==1 && !d.syncs && !d.irqs);
   } else if ((data>>8)==0xa5) {
    CHECK(d.m_wtcsr==(data&0xff) && d.syncs==1 && d.irqs==1);
    CHECK(d.m_wtcnt==((data&0x20)?0x56:0));
    CHECK(d.starts==((data&0x20)?1U:0U) && d.timer.adjustments==1);
   } else {
    CHECK(d.m_wtcnt==0x56 && d.m_wtcsr==0xb9 && !d.syncs && !d.starts && !d.irqs && !d.timer.adjustments);
   }
   CHECK(d.m_rstcsr==0xe0);
  }
  ++words;
 }
 std::printf("method-level, unvalidated: %u byte-lane writes; %u partial-mask robustness cases; %u two-byte assembly attempts; %u existing full-word dispatch controls\n",bytes,partials,sequences,words);
 std::puts("method-level, unvalidated: rejected accesses leave counters/status, timer scheduling, IRQ refresh and command scratch unchanged");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-access-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + extract('wtcnt_w') + extract('rstcsr_w') + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

#!/usr/bin/env python3
"""SBYCR bit 5 reads zero; method-level, unvalidated.

Reserved-one inputs are diagnostics, not permitted programming. Peripheral
helpers are mocked; no power-down, clock gating, pin or native lane oracle.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
functions=''
for name,result in [('fmr_sbycr_r','uint16_t'),('fmr_sbycr_w','void')]:
    match=re.search(r'^'+result+r' sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions+=match[0].replace('sh7604_device::','')+'\n'
head=r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#define BIT(v,n) (((v)>>(n))&1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using offs_t=unsigned;
struct Device {
 uint8_t m_sbycr=0;
 uint64_t m_frc_base=0;
 unsigned sci_resets=0,frt_resets=0,timer_activations=0,irqs=0;
 void sci_reset() { ++sci_resets; }
 void frt_reset() { ++frt_resets; }
 void sh2_timer_activate() { ++timer_activations; }
 void sh2_recalc_irq() { ++irqs; }
 uint64_t total_cycles() const { return 1234; }
 template<class... Args> void logerror(const char *,Args...) {}
'''
tail=r'''
};
int main() {
 Device polluted; polluted.m_sbycr=0x20; CHECK(polluted.fmr_sbycr_r()==0);
 unsigned raw=0,replays=0,writes=0,defined=0,fmr_controls=0;
 for (unsigned value=0;value<256;++value) {
  Device d; d.m_sbycr=value; Device replay=d;
  CHECK(d.fmr_sbycr_r()==(value&0xdf) && replay.fmr_sbycr_r()==(value&0xdf));
  CHECK(d.m_sbycr==value && replay.m_sbycr==value);
  CHECK(d.sci_resets==0 && d.frt_resets==0 && d.timer_activations==0 && d.irqs==0);
  ++raw; ++replays;
  Device written; written.fmr_sbycr_w(0,value,0x00ff);
  const auto backing=written.m_sbycr;
  const unsigned calls=written.sci_resets+written.frt_resets+written.timer_activations+written.irqs;
  CHECK(written.fmr_sbycr_r()==(value&0xdf) && written.m_sbycr==backing);
  CHECK(written.sci_resets+written.frt_resets+written.timer_activations+written.irqs==calls);
  ++writes; if (!(value&0x20)) ++defined;
  // Unchanged high-byte/legacy full-word FMR write routing. This is not
  // a native clock-multiplier or bus-lane test.
  for (unsigned mask : {0xff00U,0xffffU})
  for (unsigned word : {0U,1U,2U,3U,0x20U,0x120U,0xffdfU,0xffffU}) {
   Device fmr; fmr.m_sbycr=value;
   fmr.fmr_sbycr_w(0,word,mask);
   CHECK(fmr.m_sbycr==value && fmr.fmr_sbycr_r()==(value&0xdf));
   CHECK(fmr.sci_resets==0 && fmr.frt_resets==0 && fmr.timer_activations==0 && fmr.irqs==0); ++fmr_controls;
  }
 }
 std::printf("method-level, unvalidated: %u raw-storage read masks; %u state-copy replays; %u byte-write/read cases (%u reserved-zero controls); %u legacy FMR routing controls\n",raw,replays,writes,defined,fmr_controls);
 std::puts("method-level, unvalidated: reserved bit masked without read side effects; no native power-down, clock, IRQ, bus-lane, reset-image or save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sbycr-reserved-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

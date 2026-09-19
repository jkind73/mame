#!/usr/bin/env python3
"""BSC keyed longword write gate; method-level, unvalidated.

Valid-write controls preserve the existing payload/storage behavior, not
refresh timing, CMF semantics, reserved fields or upper-half readback.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
names=['bcr1','bcr2','wcr','mcr','rtcsr','rtcnt','rtcor']
functions=''
for name in names:
    match=re.search(r'^void sh7604_device::'+name+r'_w\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions+=match[0].replace('sh7604_device::','')+'\n'
head=r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <tuple>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define ACCESSING_BITS_0_31 (mem_mask & 0xffffffff)
#define ACCESSING_BITS_0_15 (mem_mask & 0xffff)
using offs_t=unsigned;
struct Device {
 uint32_t m_bcr1=0x03f0,m_bcr2=0x00fc,m_wcr=0xaaff,m_mcr=0x5000,m_rtcsr=0x38,m_rtcnt=0x56,m_rtcor=0xab;
 auto snapshot() const { return std::make_tuple(m_bcr1,m_bcr2,m_wcr,m_mcr,m_rtcsr,m_rtcnt,m_rtcor); }
'''
tail=r'''
};
int main() {
 Device unkeyed; unkeyed.wcr_w(0,0x1234,0xffffffff); CHECK(unkeyed.m_wcr==0xaaff);
 using Writer=void (Device::*)(offs_t,uint32_t,uint32_t);
 const Writer writes[]={&Device::bcr1_w,&Device::bcr2_w,&Device::wcr_w,&Device::mcr_w,&Device::rtcsr_w,&Device::rtcnt_w,&Device::rtcor_w};
 uint32_t Device::* const fields[]={&Device::m_bcr1,&Device::m_bcr2,&Device::m_wcr,&Device::m_mcr,&Device::m_rtcsr,&Device::m_rtcnt,&Device::m_rtcor};
 const uint32_t stored_masks[]={0xffff,0xffff,0xffffffff,0xffffffff,0xffffffff,0xff,0xff};
 unsigned partials=0,badkeys=0,valid=0,split=0;
 for (unsigned reg=0;reg<7;++reg) {
  for (uint32_t mask=0;mask<65536;++mask) for (unsigned upper=0;upper<2;++upper) {
   Device d; const auto before=d.snapshot();
   (d.*writes[reg])(0,0xa55a1234,upper?mask<<16:mask);
   CHECK(d.snapshot()==before); ++partials;
  }
  for (uint32_t key=0;key<65536;++key) {
   if (key==0xa55a) continue;
   Device d; const auto before=d.snapshot(); (d.*writes[reg])(0,(key<<16)|0x1357,0xffffffff);
   CHECK(d.snapshot()==before); ++badkeys;
  }
  for (uint32_t payload=0;payload<65536;++payload) {
   Device d,expected; const uint32_t data=0xa55a0000|payload;
   expected.*fields[reg]=data&stored_masks[reg];
   (d.*writes[reg])(0,data,0xffffffff); CHECK(d.snapshot()==expected.snapshot()); ++valid;
  }
  // Separate key/data words cannot assemble a longword command, including
  // when an earlier valid longword left key bits in legacy scratch storage.
  for (unsigned order=0;order<2;++order) {
   Device d; (d.*writes[reg])(0,0xa55a2468,0xffffffff); const auto before=d.snapshot();
   for (unsigned part=0;part<2;++part) {
    const bool upper=part^order;
    (d.*writes[reg])(0,upper?0xa55a0000:0x1357,upper?0xffff0000:0x0000ffff);
   }
   CHECK(d.snapshot()==before); ++split;
  }
 }
 std::printf("method-level, unvalidated: %u partial-mask writes; %u wrong-key longwords; %u existing valid-key dispatch controls; %u split-key sequences\n",partials,badkeys,valid,split);
 std::puts("method-level, unvalidated: register gate only; native address-space routing, upper-half readback and bus/refresh timing not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-bsc-access-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

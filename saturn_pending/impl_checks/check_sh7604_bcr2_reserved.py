#!/usr/bin/env python3
"""BCR2 reserved read bits are zero; method-level, unvalidated.

Reads are checked independently of raw saved storage. Sweeps that inject
reserved encodings are robustness probes, not permission to program them
or change BCR2 after its documented initialization sequence.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
functions=''
for name,result in [('bcr2_r','uint32_t'),('bcr2_w','void')]:
    match=re.search(r'^'+result+r' sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions+=match[0].replace('sh7604_device::','')+'\n'
head=r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using offs_t=unsigned;
struct Device {
 uint32_t m_bcr2=0x00fc;
'''
tail=r'''
};
int main() {
 Device polluted; polluted.m_bcr2=0xffff; CHECK(polluted.bcr2_r()==0xfc);
 unsigned raw=0,writes=0,replays=0,legal=0;
 for (uint32_t low=0;low<65536;++low) {
  for (uint32_t upper : {0U,1U,0xa55aU,0xffffU}) {
   Device d; d.m_bcr2=(upper<<16)|low; Device replay=d;
   const auto before=d.m_bcr2;
   CHECK(d.bcr2_r()==(low&0xfc) && replay.bcr2_r()==(low&0xfc));
   CHECK(d.m_bcr2==before && replay.m_bcr2==before); ++raw; ++replays;
  }
  Device d; d.bcr2_w(0,0xa55a0000|low,0xffffffff);
  const auto before=d.m_bcr2;
  CHECK(d.bcr2_r()==(low&0xfc) && d.m_bcr2==before); ++writes;
 }
 // Encodings 1/2/3 select 8/16/32-bit bus size; zero is reserved.
 for (unsigned a1=1;a1<4;++a1) for (unsigned a2=1;a2<4;++a2) for (unsigned a3=1;a3<4;++a3) {
  Device d; const uint32_t value=(a1<<2)|(a2<<4)|(a3<<6);
  d.bcr2_w(0,0xa55a0000|value,0xffffffff); CHECK(d.bcr2_r()==value); ++legal;
 }
 std::printf("method-level, unvalidated: %u raw-storage masks; %u keyed-write/read cases; %u state-copy replays; %u legal bus-size field combinations\n",raw,writes,replays,legal);
 std::puts("method-level, unvalidated: reserved read bits masked without storage mutation; no native bus-size/timing/reset qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-bcr2-reserved-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

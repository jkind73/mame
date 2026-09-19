#!/usr/bin/env python3
"""CHCR reserved read bits are zero; method-level, unvalidated.

Raw reserved-bit/encoding injections are robustness probes, not permitted
software programming. DMA start/check is mocked; no transfers or IRQ oracle.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
functions=''
for name,result in [('chcr_r','uint32_t'),('chcr_w','void')]:
    match=re.search(r'^'+result+r' sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions+='template <int Channel>\n'+match[0].replace('sh7604_device::','')+'\n'
head=r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using offs_t=unsigned;
struct Device {
 struct { uint32_t chcr=0; } m_dmac[2];
 unsigned checks[2]{};
 void sh2_dmac_check(int channel) { ++checks[channel]; }
'''
tail=r'''
};
template<int Channel> void run(unsigned &raw,unsigned &replays,unsigned &writes) {
 for (uint32_t low=0;low<65536;++low) for (uint32_t upper : {0U,1U,0xa55aU,0xffffU}) {
  Device d; const uint32_t value=(upper<<16)|low,other=value^0x5a5a6996U;
  d.m_dmac[Channel].chcr=value; d.m_dmac[1-Channel].chcr=other; Device replay=d;
  CHECK(d.chcr_r<Channel>()==low && replay.chcr_r<Channel>()==low);
  CHECK(d.chcr_r<1-Channel>()==(other&0xffff));
  CHECK(d.m_dmac[Channel].chcr==value && d.m_dmac[1-Channel].chcr==other);
  CHECK(replay.m_dmac[Channel].chcr==value && replay.m_dmac[1-Channel].chcr==other);
  CHECK(d.checks[0]==0 && d.checks[1]==0 && replay.checks[0]==0 && replay.checks[1]==0);
  ++raw; ++replays;
 }
 // Defined SM/DM/TS fields, dual-address/auto-request, DE=0. Write TE=1
 // to retain the seeded status (not to software-set it). No DMA executes.
 for (unsigned sm=0;sm<3;++sm) for (unsigned dm=0;dm<3;++dm)
 for (unsigned size=0;size<4;++size) for (unsigned ie=0;ie<2;++ie)
 for (unsigned te=0;te<2;++te) {
  Device d; d.m_dmac[Channel].chcr=te<<1; d.m_dmac[1-Channel].chcr=0x1200;
  const uint32_t control=(sm<<12)|(dm<<14)|(size<<10)|0x200|(ie<<2);
  d.chcr_w<Channel>(0,control|2,0xffffffff);
  CHECK(d.chcr_r<Channel>()==(control|(te<<1)) && d.chcr_r<1-Channel>()==0x1200);
  CHECK(d.checks[Channel]==1 && d.checks[1-Channel]==0); ++writes;
 }
}
int main() {
 Device polluted; polluted.m_dmac[0].chcr=0xffff5205; polluted.m_dmac[1].chcr=0xa55a0006;
 CHECK(polluted.chcr_r<0>()==0x5205 && polluted.chcr_r<1>()==6);
 unsigned raw=0,replays=0,writes=0; run<0>(raw,replays,writes); run<1>(raw,replays,writes);
 std::printf("method-level, unvalidated: %u raw-storage read masks; %u state-copy replays; %u disabled-channel write/status controls\n",raw,replays,writes);
 std::puts("method-level, unvalidated: all low-word images with four upper-word patterns on both channels; raw storage/other channel preserved; no native bus/transfer/IRQ/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-chcr-reserved-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

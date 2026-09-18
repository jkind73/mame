#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual complete SCSP DSP methods: zero tails, register continuity and reads."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(os.environ.get('MAME_ROOT',Path(__file__).resolve().parents[2]))
src=Path(os.environ.get('SCSP_DSP_SOURCE',ROOT/'src/devices/sound/scspdsp.cpp')).read_text().replace('#include "emu.h"','')
mutant=os.environ.get('SCSP_DSP_MUTANT','')
if mutant=='addr-unsigned':src=src.replace('util::sext(ADRS_REG, 12)', '(ADRS_REG & 0xfff)')
if mutant=='addr-width':src=src.replace('util::sext(ADRS_REG, 12)', 'util::sext(ADRS_REG, 13)')
if mutant=='addr-unconditional':src=src.replace('if (ADREB)', 'if (true)')
if mutant=='addr-late-latch':
 a=src.index('    if (ADRL) {');b=src.index('    // EFREG',a);block=src[a:b]
 src=src[:a]+src[b:];src=src.replace('    {\n      u32 ADDR',block+'    {\n      u32 ADDR')
if mutant=='input-bypass':src=src.replace('MEMS[IWA] = ReadValue;', 'MEMS[IWA] = ReadValue; if (IRA == IWA) INPUTS = ReadValue;')
if mutant=='signed-input-bypass':src=src.replace('MEMS[IWA] = ReadValue;', 'MEMS[IWA] = ReadValue; if (IRA == IWA) INPUTS = util::sext(ReadValue, 24);')
if mutant=='trimmed':src=src.replace('step < 128;', 'step < LastStep;')
if mutant=='padded-trim':src=src.replace('step < 128;', 'step < std::min(LastStep + 2, 128);')
if mutant=='missing-final':src=src.replace('step < 128;', 'step < 127;')
if mutant=='reset-acc':src=src.replace('void SCSPDSP::Step() {', 'void SCSPDSP::Step() { ACC=0;')
if mutant=='clear-effects':src=src.replace('void SCSPDSP::Step() {', 'void SCSPDSP::Step() { std::fill(std::begin(EFREG),std::end(EFREG),0);')
cpp=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <iterator>
#include <vector>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;
using s16=int16_t;using s32=int32_t;using s64=int64_t;
#define BIT(v,b) ((uint32_t(v)>>(b))&1)
namespace util {template<class T>s32 sext(T v,unsigned bits){u32 mask=(1u<<bits)-1,sign=1u<<(bits-1);return s32((u32(v)&mask)^sign)-s32(sign);}}
struct address_space {
 u16 data=0;unsigned reads=0;bool recording=false;std::vector<u32> addresses;
 u16 read_word(u32 a){if(recording)addresses.push_back(a);else assert(a==0x8000);++reads;return data;}
 void write_word(u32 a,u16){assert(recording);addresses.push_back(a);}
};
// SOURCE
s32 signed_bits(u32 v,unsigned n){s64 x=v&((1ull<<n)-1);return s32(x-(x&(1ull<<(n-1))?(1ll<<n):0));}
s32 tail_acc(s32 t,s32 f){return signed_bits(u32(((s64(t)*signed_bits(f,13))>>12)+t),26);}
s16 effect(s32 a){return std::clamp(a,-0x800000,0x7fffff)>>8;}
int main(){
 unsigned cases=0;u32 random=0x728194ab;
 for(unsigned n=0;n<256;++n){
  random=random*1664525u+1013904223u;
  SCSPDSP d;d.Init();address_space mem;mem.data=0x8123;d.space=&mem;
  s32 t=signed_bits(random,24);std::fill(std::begin(d.TEMP),std::end(d.TEMP),t);
  d.FRC_REG=random>>19;d.MEMS[0]=random;d.INPUTS=0x1357;d.ACC=0x1357;d.DEC=random;
  d.ReadPending=(n&1)?2:0;d.RWAddr=0x8000;
  std::fill(std::begin(d.MIXS),std::end(d.MIXS),1);d.Start();d.Step();
  assert(d.ACC==tail_acc(t,random>>19));assert(d.INPUTS==signed_bits(random,24));
  assert(d.DEC==random-1);assert(!d.ReadPending);assert(mem.reads==(n&1));
  for(auto v:d.MIXS)assert(!v);++cases;
 }
 for(unsigned last=3;last<128;last+=2)
 for(u16 word:{u16(0),u16(0x1234),u16(0x7fff),u16(0x8000),u16(0xffff)})
 for(s16 coeff:{s16(0),s16(8),s16(0x7ff8),s16(-32768),s16(-8)}){
  SCSPDSP d;d.Init();address_space mem;mem.data=word;d.space=&mem;
  random=random*1664525u+1013904223u;s32 t=signed_bits(random,24);
  std::fill(std::begin(d.TEMP),std::end(d.TEMP),t);d.FRC_REG=random>>19;
  d.MEMS[0]=word<<8;d.ReadValue=word<<8;d.ACC=signed_bits(random,26);
  d.COEF[0]=coeff;d.MADRS[0]=0x4000;d.DEC=random;
  d.MPRO[2]=0x1002;d.MPRO[5]=0x20;d.MPRO[6]=2;
  d.MPRO[last*4+1]=0xa000;d.MPRO[last*4+2]=0xa002;d.MPRO[last*4+3]=0x100;
  d.EFREG[1]=123;d.Start();assert(d.LastStep==int(last+1));
  for(unsigned round=0;round<3;++round){
   s32 entry=d.ACC;u32 dec=d.DEC;d.Step();
   s32 expected=last==127?signed_bits(u32((s64(signed_bits(word<<8,24))*(coeff>>3))>>12),26):tail_acc(t,d.FRC_REG);
   assert(d.ACC==expected&&d.EFREG[0]==effect(entry)&&d.EFREG[1]==123);
   assert(d.ReadPending==(last==127?2:0));assert(d.DEC==dec-1);++cases;
  }
  // Program writes beyond the remembered nonzero tail take effect without Start.
  if(last<127){d.MPRO[127*4+2]=0x1100;d.Step();assert(d.EFREG[1]==effect(tail_acc(t,d.FRC_REG)));++cases;}
 }

 unsigned input_cases=0;
 for(unsigned ira=0;ira<32;++ira)for(unsigned iwa=0;iwa<32;++iwa)
 for(u32 prior:{0u,1u,0x7fffffu,0x800000u,0xffff00u,0xffffffu})
 for(u32 incoming:{0u,1u,0x7fffffu,0x800000u,0xffff00u,0xffffffu})
 for(unsigned enabled=0;enabled<2;++enabled){
  SCSPDSP d;d.Init();address_space mem;d.space=&mem;
  d.MEMS[ira]=prior;d.ReadValue=incoming;d.COEF[0]=0x7ff8;
  d.MPRO[5]=0xa000|(ira<<6)|(enabled?0x20:0)|iwa;d.MPRO[6]=0x8a;
  d.MPRO[10]=0x1002;
  d.MPRO[13]=0xa000|(ira<<6);d.MPRO[14]=2;d.MPRO[18]=0x1102;
  d.Start();d.Step();
  u32 after=enabled&&ira==iwa?incoming:prior;
  assert(d.EFREG[0]==effect(s32((s64(signed_bits(prior,24))*4095)>>12)));
  assert(d.EFREG[1]==effect(s32((s64(signed_bits(after,24))*4095)>>12)));
  assert(d.Y_REG==signed_bits(prior,24));
  assert((u32(d.ADRS_REG)&0xfff)==(u32(signed_bits(prior,24)>>16)&0xfff));
  assert((u32(d.MEMS[ira])&0xffffff)==after);
  if(enabled)assert((u32(d.MEMS[iwa])&0xffffff)==incoming);
  ++input_cases;
 }
 std::cout<<input_cases<<" actual MEMS read-before-write/MAC/YRL/ADRL cases passed\n";
 unsigned address_cases=0;
 for(unsigned form=0;form<2;++form)for(unsigned raw=0;raw<(form?4096u:256u);++raw)
 for(unsigned rb=0;rb<4;++rb)for(unsigned table=0;table<2;++table)
 for(unsigned add=0;add<2;++add){
  unsigned nx=raw&1,wr=(raw>>1)&1;
  SCSPDSP d;d.Init();address_space mem;mem.recording=true;d.space=&mem;
  unsigned bases[]={0,1,0xfff,0x1fff,0x7fff,0xffff};
  d.MADRS[0]=bases[raw%6];d.RBL=8192u<<rb;d.RBP=(raw>>4)&63;
  d.DEC=raw*0x10203u;d.ADRS_REG=0xa55;
  d.MEMS[0]=form?u32(-s64(signed_bits(raw<<12,24))):raw<<16;
  d.COEF[0]=-32768;d.MPRO[1]=0xa000;d.MPRO[2]=2;
  d.MPRO[6]=0x80|(form?0x30:0)|(table?0x8000:0)|(wr?0x4000:0x2000);
  d.MPRO[7]=0x100|(add?2:0)|nx;
  d.MPRO[14]=(table?0x8000:0)|(wr?0x4000:0x2000);d.MPRO[15]=d.MPRO[7];
  s64 offset=signed_bits(raw,form?12:8);
  s64 logical=s64(d.MADRS[0])+(table?0:d.DEC)+(add?offset:0)+nx;
  u32 expected=(((u32(logical)&(table?0xffff:d.RBL-1))+(d.RBP<<12))*2);
  s64 old_logical=s64(d.MADRS[0])+(table?0:d.DEC)+(add?signed_bits(0xa55,12):0)+nx;
  u32 first=((u32(old_logical)&(table?0xffff:d.RBL-1))+(d.RBP<<12))*2;
  d.Start();d.Step();assert((mem.addresses==std::vector<u32>{first,expected}));++address_cases;
 }
 std::cout<<address_cases<<" actual signed-displacement/latch/ring/table/read-write cases passed\n";
 SCSPDSP stopped;stopped.Init();stopped.ACC=123;stopped.MIXS[0]=99;stopped.Step();
 assert(stopped.ACC==123&&!stopped.MIXS[0]);
 std::cout<<cases<<" actual SCSP zero-tail/MAC/read/live-program cases plus stopped control passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-dsp-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(cpp.replace('// SOURCE',src))
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'src/devices/sound'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)

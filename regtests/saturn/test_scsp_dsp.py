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
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;
using s16=int16_t;using s32=int32_t;using s64=int64_t;
#define BIT(v,b) ((uint32_t(v)>>(b))&1)
namespace util {template<class T>s32 sext(T v,unsigned bits){u32 mask=(1u<<bits)-1,sign=1u<<(bits-1);return s32((u32(v)&mask)^sign)-s32(sign);}}
struct address_space {
 u16 data=0;unsigned reads=0;
 u16 read_word(u32 a){assert(a==0x8000);++reads;return data;}
 void write_word(u32,u16){assert(false);}
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
 SCSPDSP stopped;stopped.Init();stopped.ACC=123;stopped.MIXS[0]=99;stopped.Step();
 assert(stopped.ACC==123&&!stopped.MIXS[0]);
 std::cout<<cases<<" actual SCSP zero-tail/MAC/read/live-program cases plus stopped control passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-dsp-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(cpp.replace('// SOURCE',src))
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'src/devices/sound'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
"""ASan/UBSan checks of actual SCSP DSP mixer banks and float unpacking."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
sound=root/'src/devices/sound'
shim=r'''
#pragma once
#include <cstdint>
#include <algorithm>
#include <array>
#include <iterator>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;
using s16=int16_t;using s32=int32_t;using s64=int64_t;
template<class T> constexpr unsigned BIT(T value,unsigned bit){return (value>>bit)&1;}
namespace util {template<class T> s32 sext(T value,unsigned bits){return s32(u32(value)<<(32-bits))>>(32-bits);}}
struct address_space {std::array<u16,65536> ram{};u16 read_word(u32 a){return ram[(a/2)&65535];}void write_word(u32 a,u16 v){ram[(a/2)&65535]=v;}};
'''
fixture=r'''
#include <cassert>
int main(){
 address_space memory;SCSPDSP dsp;dsp.Init();dsp.space=&memory;dsp.Start();
 // CPU writes to the read bank survive alternate samples for channels not
 // targeted by a slot; the first slot write overwrites, further writes add.
 dsp.MIXSPrev[3]=0x12345;dsp.MIXS[3]=0x54321;
 for(unsigned i=0;i<8;++i){
  dsp.SetSample(0,0,0);dsp.Step();
  assert(dsp.MIXSPrev[3]==(i%2?0x12345:0x54321));
  assert(dsp.MIXSPrev[0]==0);
 }
 dsp.SetSample(7,3,1);dsp.SetSample(-2,3,1);dsp.Step();assert(dsp.MIXSPrev[3]==5);
 dsp.SetSample(11,3,1);dsp.Step();assert(dsp.MIXSPrev[3]==11);
 dsp.SetSample(13,3,1);dsp.Step();assert(dsp.MIXSPrev[3]==13);
 // Exhaustive float decoder oracle from the supplied suite's mathematical
 // expected-value expression, written using unsigned shifts.
 for(unsigned fv=0;fv<65536;++fv){
  unsigned ex=(fv>>11)&15;
  u32 mant=((fv&0x7ff)|((ex<12)<<11))<<19;
  u32 sign=(fv&0x8000)?0xc0000000U:0;
  s32 expected=s32(mant^sign)>>(8+(ex>11?11:ex));
  assert((u32(UNPACK(fv))&0xffffff)==(u32(expected)&0xffffff));
 }
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-dsp-bank-') as directory:
    out=Path(directory)
    (out/'emu.h').write_text(shim)
    (out/'test.cpp').write_text((sound/'scspdsp.cpp').read_text()+'\n'+fixture)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(out),'-I'+str(sound),str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('SCSP DSP bank/float ASan/UBSan checks passed')

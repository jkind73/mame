#!/usr/bin/env python3
# license:BSD-3-Clause
"""Disassemble actual MVI/D1 opcodes against Sega's distinct destination tables."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parent.parent
src=root/'src/devices/cpu/scudsp'
shim=r'''
#pragma once
#include <cstdint>
#include <string>
#include <ostream>
#include <sstream>
#include <cstdio>
using u32=uint32_t;using offs_t=uint32_t;
namespace util {
template<class...T> std::string string_format(const char*f,T...a){char b[256];snprintf(b,sizeof(b),f,a...);return b;}
template<class...T> void stream_format(std::ostream&s,const char*f,T...a){s<<string_format(f,a...);}
class disasm_interface {
 public:
 static constexpr u32 SUPPORTED=0x80000000,STEP_COND=0x10000000;
 static constexpr u32 step_over_extra(unsigned n){return n<<26;}
 struct data_buffer{u32 value;u32 r32(offs_t)const{return value;}};
 virtual ~disasm_interface()=default;
 virtual u32 opcode_alignment()const=0;
 virtual offs_t disassemble(std::ostream&,offs_t,const data_buffer&,const data_buffer&)=0;
};
}
'''
fixture=r'''
#include "emu.h"
#include "scudspdasm.h"
#include <cassert>
int main(){
 scudsp_disassembler d;
 auto dis=[&](u32 word){util::disasm_interface::data_buffer b{word};std::ostringstream o;d.disassemble(o,0,b,b);return o.str();};
 const char* names[]={"MC0","MC1","MC2","MC3","RX","PL","RA0","WA0","???","???","LOP","???","PC","???","???","???"};
 for(unsigned dest=0;dest<16;++dest){
  assert(dis(0x80000001|(dest<<26))==std::string("MVI #$1,")+names[dest]);
  assert(dis(0x82080001|(dest<<26))==std::string("MVI #$1,")+names[dest]+",NZ");
 }
 assert(dis(0x1c01).find("CT0")!=std::string::npos);
 for(unsigned flags=0;flags<4;++flags)for(unsigned add=0;add<8;++add)for(unsigned bank=0;bank<8;++bank){
  auto text=dis(0xc0000007|(flags<<12)|(add<<15)|(bank<<8));
  assert(text.find("DMA")==0);
  if(bank<5)assert(text.find("???")==std::string::npos);
 }
 util::disasm_interface::data_buffer b{0xd1080001};std::ostringstream o;
 auto bits=d.disassemble(o,0,b,b);
 assert(bits&util::disasm_interface::SUPPORTED);assert(bits&util::disasm_interface::STEP_COND);
 assert(bits&util::disasm_interface::step_over_extra(1));
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-disasm-') as directory:
 p=Path(directory);(p/'emu.h').write_text(shim);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-I'+str(p),'-I'+str(src),str(src/'scudspdasm.cpp'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('SCU DSP MVI/D1 disassembly checks passed (ASan/UBSan)')

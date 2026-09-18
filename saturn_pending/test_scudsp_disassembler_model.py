#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compile the complete real disassembler, interface and formatter, not replicas."""
from pathlib import Path
import os
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
DIR=Path(os.environ.get('SCUDSP_DASM_DIR',ROOT/'src/devices/cpu/scudsp'))
cpp=r'''
#include "emu.h"
#include "scudspdasm.h"
#include <cassert>
#include <iostream>
#include <sstream>
struct buffer:util::disasm_interface::data_buffer {
 uint32_t word;explicit buffer(uint32_t value):word(value){}
 u8 r8(offs_t)const override{assert(false);return 0;}
 u16 r16(offs_t)const override{assert(false);return 0;}
 u32 r32(offs_t pc)const override{assert(pc==0);return word;}
 u64 r64(offs_t)const override{assert(false);return 0;}
};
std::string clean(std::string text){std::istringstream in(text);std::string result,word;while(in>>word){if(!result.empty())result+=' ';result+=word;}return result;}
std::string decode(uint32_t opcode){
 scudsp_disassembler d;buffer b(opcode);std::ostringstream out;
 assert(d.opcode_alignment()==1);assert((d.disassemble(out,0,b,b)&d.LENGTHMASK)==1);
 return clean(out.str());
}
int main(){
 unsigned cases=0;
 const char* mvi[]={"MC0","MC1","MC2","MC3","RX","PL","RA0","WA0","???","???","LOP","???","PC","???","???","???"};
 const char* d1[]={"MC0","MC1","MC2","MC3","RX","PL","RA0","WA0","???","???","LOP","TOP","CT0","CT1","CT2","CT3"};
 for(unsigned dest=0;dest<16;++dest){
  for(bool cond:{false,true})for(unsigned value:{0u,1u,0x12345u,0xffffffffu}){
   unsigned imm=value&(cond?0x7ffff:0x1ffffff);
   auto op=0x80000000u|(dest<<26)|imm|(cond?0x03080000u:0);
   assert(decode(op)==util::string_format("MVI #$%X,%s%s",imm,mvi[dest],cond?",Z":""));++cases;
  }
  assert(decode(0x1031|(dest<<8))==util::string_format("MOV #$31,%s",d1[dest]));++cases;
 }
 for(unsigned x=0;x<8;++x)for(unsigned y=0;y<8;++y)for(unsigned bus:{0u,1u,3u}){
  uint32_t op=(4u<<26)|(x<<23)|(y<<17)|(1<<14)|(bus<<12)|(3<<8)|(bus==1?0x31:2);
  std::string expected="ADD";
  if(x&4)expected+=" MOV M0,X";
  if((x&3)==2)expected+=" MOV MUL,P";
  if((x&3)==3)expected+=" MOV M0,P";
  if(y&4)expected+=" MOV M1,Y";
  if((y&3)==1)expected+=" CLR A";
  if((y&3)==2)expected+=" MOV ALU,A";
  if((y&3)==3)expected+=" MOV M1,A";
  if(bus==1)expected+=" MOV #$31,MC3";
  if(bus==3)expected+=" MOV M2,MC3";
  assert(decode(op)==expected);++cases;
 }
 assert(decode(0)=="NOP");++cases;
 std::cout<<cases<<" real disassembler destination/parallel-command cases passed under UBSan\n";
}
'''
includes=['src/osd','src/emu','src/lib','src/lib/util','src/devices','3rdparty',
          '3rdparty/asio/include','3rdparty/expat/lib','3rdparty/softfloat3/source/include','3rdparty/rapidjson/include']
with tempfile.TemporaryDirectory(prefix='scudsp-dasm-') as folder:
    p=Path(folder);(p/'test.cpp').write_text(cpp)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-fsanitize=undefined',
        '-fno-sanitize-recover=all','-I'+str(DIR),*('-I'+str(ROOT/i) for i in includes),
        str(p/'test.cpp'),str(DIR/'scudspdasm.cpp'),str(ROOT/'src/lib/util/disasmintf.cpp'),
        str(ROOT/'src/lib/util/strformat.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

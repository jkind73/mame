#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual ST-V protected-port handlers: each requested halfword consumes one word."""
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parent.parent
source=(Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/mame/sega/stv.cpp').read_text()
def method(signature):
 a=source.index(signature);b=source.index('{',a);depth=1;i=b+1
 while depth:
  depth+=(source[i]=='{')-(source[i]=='}');i+=1
 return source[a:i]
read=method('uint32_t stv_state::common_prot_r(')
# The old delegate discarded the mask; give its unchanged body an ignored
# argument so the same physical-access fixture can demonstrate skipped words.
read=read.replace('common_prot_r(offs_t offset)','common_prot_r(offs_t offset, uint32_t mem_mask)')
code=r'''
#include <cassert>
#include <cstdint>
#include <array>
using offs_t=uint32_t;
#define ACCESSING_BITS_16_31 (mem_mask & 0xffff0000U)
#define ACCESSING_BITS_0_15 (mem_mask & 0x0000ffffU)
#define COMBINE_DATA(ptr) (*(ptr)=(*(ptr)&~mem_mask)|(data&mem_mask))
uint16_t swapendian_int16(uint16_t n){return (n<<8)|(n>>8);}
struct chip {
 unsigned pos=0,key_calls=0,low_calls=0,high_calls=0;uint16_t key=0;
 std::array<uint16_t,4> words={0x1234,0x5678,0x9abc,0xdef0};
 uint16_t do_decrypt(uint8_t*&base){base=nullptr;return words.at(pos++);}
 void set_subkey(uint16_t value){key=value;++key_calls;}
 void set_addr_low(uint16_t){++low_calls;}
 void set_addr_high(uint16_t){++high_calls;}
};
struct stv_state {
 struct region {std::array<uint32_t,4> data{};uint8_t*base(){return (uint8_t*)data.data();}} rom;
 region*memregion(const char*){return &rom;}
 chip cipher;chip*m_cryptdevice=&cipher;
 uint32_t m_abus_protenable=0x10000,m_abus_protkey=0,m_a_bus[4]{};
 uint32_t common_prot_r(offs_t,uint32_t=~0U);
 void common_prot_w(offs_t,uint32_t,uint32_t=~0U);
};
METHODS
int main(){
 stv_state d;
 assert(d.common_prot_r(3,0xffff0000)==0x34120000 && d.cipher.pos==1);
 assert(d.common_prot_r(3,0x0000ffff)==0x7856 && d.cipher.pos==2);
 assert(d.common_prot_r(3)==0xbc9af0de && d.cipher.pos==4);
 assert(d.common_prot_r(3,0)==0 && d.cipher.pos==4);
 d.cipher.pos=0;
 assert((d.common_prot_r(3,0xff000000)&0xff000000)==0x34000000 && d.cipher.pos==1);
 assert((d.common_prot_r(3,0x000000ff)&0xff)==0x56 && d.cipher.pos==2);
 d.common_prot_w(3,0x11220000,0xffff0000);
 assert(d.cipher.key_calls==1&&d.cipher.key==0x1122);
 d.common_prot_w(3,0x00003344,0x0000ffff);
 assert(d.cipher.key_calls==1&&d.m_abus_protkey==0x11223344);
 d.common_prot_w(2,0x11220000,0xffff0000);assert(d.cipher.low_calls==1&&d.cipher.high_calls==0);
 d.common_prot_w(2,0x00003344,0x0000ffff);assert(d.cipher.low_calls==1&&d.cipher.high_calls==1);
 d.m_abus_protenable=0;d.m_a_bus[3]=0xaabbccdd;
 assert(d.common_prot_r(3)==0xaabbccdd&&d.cipher.pos==2);
}
'''.replace('METHODS',read+'\n'+method('void stv_state::common_prot_w('))
with tempfile.TemporaryDirectory(prefix='stv-crypt-access-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)
print('STV encrypted stream widths and key lanes ASan/UBSan PASS')

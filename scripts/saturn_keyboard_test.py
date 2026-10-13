#!/usr/bin/env python3
# license:BSD-3-Clause
"""Execute actual Saturn keyboard reports against the Sega STN-45 mappings."""
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parent.parent
source=(Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/devices/bus/sat_ctrl/keybd.cpp').read_text()
methods=source[source.index('void saturn_keybd_device::key_make'):]
fixture=r'''
#include <array>
#include <cassert>
#include <cstdint>
unsigned BIT(unsigned x,unsigned b){return (x>>b)&1;}
struct input { uint8_t value=0;input *operator->(){return this;}unsigned read(){return value;} };
struct saturn_keybd_device {
 std::array<input,18> m_key_rows{};uint8_t m_status=0,m_data=0;
 void key_make(uint8_t,uint8_t);void key_break(uint8_t,uint8_t);void key_repeat(uint8_t,uint8_t);
 uint16_t get_game_key();uint8_t read_ctrl(uint8_t);
};
METHODS
int main(){
 saturn_keybd_device d;
 // STN-45 button-to-key table; these codes identify actual matrix inputs.
 const unsigned codes[]={0x8d,0x86,0x8a,0x89,0x76,0x1a,0x21,0x22,0x24,0x1c,0x1b,0x23,0x15};
 const unsigned bits[]={15,14,13,12,11,10,9,8,7,6,5,4,3};
 assert(d.get_game_key()==0xfff8);
 for(unsigned i=0;i<13;++i){
  unsigned code=codes[i];d.m_key_rows[code/8].value=1U<<(code%8);
  assert(d.get_game_key()==(0xfff8^(1U<<bits[i])));
  assert(((unsigned(d.read_ctrl(0))<<8)|d.read_ctrl(1))==d.get_game_key());
  d.m_key_rows[code/8].value=0;
 }
 // The B key is not the pad B trigger: the X key is.
 d.m_key_rows[6].value=4;assert(d.get_game_key()==0xfff8);d.m_key_rows[6].value=0;
 for(auto lock : {std::array<unsigned,2>{0x58,0x40},std::array<unsigned,2>{0x7e,0x10}}){
  auto code=lock[0],flag=lock[1];d.m_status=0;
  for(unsigned press=0;press<4;++press){
   d.key_make(code/8,code%8);assert(d.read_ctrl(3)==code);assert(d.read_ctrl(2)==(6|8|((press%2)?flag:0)));
   d.key_break(code/8,code%8);assert(d.read_ctrl(3)==code);assert(d.read_ctrl(2)==(6|1|((press%2)?0:flag)));
  }
 }
 // Ordinary keys and both Shift keys preserve lock flags and send raw codes.
 d.m_status=0x50;
 for(auto code : {0x1a,0x12,0x59}){
  d.key_make(code/8,code%8);assert(d.read_ctrl(2)==0x5e && d.read_ctrl(3)==code);
  d.key_break(code/8,code%8);assert(d.read_ctrl(2)==0x57 && d.read_ctrl(3)==code);
 }
}
'''.replace('METHODS',methods)
with tempfile.TemporaryDirectory(prefix='saturn-keyboard-') as directory:
    out=Path(directory);(out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('Saturn keyboard pad mappings, lock break transitions and raw Shift codes PASS')

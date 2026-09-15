#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute the production Saturn/ST-V sound CPU map declarations.

Recording-map fixture, not MAME's address-space dispatcher or a 68000 emulator.
MUTATE_SOUND_RAM_MIRROR=1 restores the former expansion alias and must fail.
"""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[2]
def extract(text, sig):
    start=text.index(sig);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
functions=[]
for file,cls in [('sat_console','sat_console_state'),('stv','stv_state')]:
    source=(ROOT/f'src/mame/sega/{file}.cpp').read_text()
    fn=extract(source,'void '+cls+'::sound_mem(')
    if os.environ.get('MUTATE_SOUND_RAM_MIRROR')=='1':
        fn=fn.replace('.ram()', '.ram().mirror(0x80000)')
        fn=fn.replace('map(0x080000, 0x0fffff).nopw();', '')
    functions.append(fn)
    # This correction is CPU-side; do not accidentally remove the separate
    # native sample/DSP RAM wrapping along with it.
    assert '.mirror(0x80000)' in extract(source,'void '+cls+'::scsp_mem(')
harness=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
#include <string>
using u32=uint32_t;using u16=uint16_t;using offs_t=uint32_t;
#define NAME(...) __VA_ARGS__
#define FUNC(...) 0
struct entry {
 u32 lo,hi,mask=0;bool isram=false,ignore=false,registers=false;
 template<class T>entry &before_delay(T){return *this;}
 entry &ram(){isram=true;return *this;}
 entry &share(const char *name){assert(std::string(name)=="sound_ram");return *this;}
 entry &mirror(u32 value){mask=value;return *this;}
 entry &nopw(){ignore=true;return *this;}
 template<class... T>entry &rw(T...){registers=true;return *this;}
};
struct address_map {
 std::vector<entry> entries;std::array<u16,0x40000> ram{};unsigned regwrites=0;
 entry &operator()(u32 lo,u32 hi){entries.push_back({lo,hi});return entries.back();}
 void write16(u32 addr,u16 value,u16 mask=0xffff){
  assert(!(addr&1));
  for(auto i=entries.rbegin();i!=entries.rend();++i){
   u32 decoded=addr&~i->mask;
   if(decoded<i->lo||decoded>i->hi)continue;
   if(i->isram){auto &v=ram.at((decoded-i->lo)/2);v=(v&~mask)|(value&mask);}
   if(i->registers)++regwrites;
   return;
  }
 }
 void write32(u32 addr,u32 value){write16(addr,value>>16);write16(addr+2,value);}
};
struct sat_console_state{int m_scsp=0;void sound_mem(address_map&);};
struct stv_state{void sound_mem(address_map&);};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned machine=0;machine<2;machine++){
  address_map map;if(machine){stv_state s;s.sound_mem(map);}else{sat_console_state s;s.sound_mem(map);}
  map.ram.fill(0xa55a);
  // Upper expansion writes in all supported bus widths must leave installed
  // RAM untouched, including the last word and the adjacent register boundary.
  for(u32 addr:{0x80000u,0x804fcu,0x806bau,0xbfffcu,0xffffeu}){
   map.write16(addr,0);map.write16(addr,0,0xff00);map.write16(addr,0,0x00ff);++cases;
  }
  for(auto word:map.ram)assert(word==0xa55a);
  map.write16(0x7fffe,0x1234);assert(map.ram.back()==0x1234);
  map.write16(0,0x1200,0xff00);map.write16(0,0x0034,0xff);assert(map.ram[0]==0x1234);
  map.write16(0x100400,0x20f);assert(map.regwrites==1);
  map.ram.fill(0xa55a);
  // After Burner II's supplied startup words: MOVEQ #-1,D1; LEA $7F000,A0;
  // MOVE.L D0,(A0)+; DBRA D1,loop, with D0=0. DBRA uses the low 16 bits.
  // Model its intended stores only; executing overwritten code is not modeled.
  map.ram[0]=7;map.ram[1]=0x7834;map.ram[2]=0;map.ram[3]=0x688;
  map.ram[0x6ba/2]=0x20c0;map.ram[0x6bc/2]=0x51c9;map.ram[0x6be/2]=0xfffc;
  auto before=map.ram;u32 addr=0x7f000;u16 count=0xffff;
  do{map.write32(addr,0);addr+=4;--count;}while(count!=0xffff);
  assert(addr==0xbf000);
  for(u32 i=0;i<0x7f000/2;i++)assert(map.ram[i]==before[i]);
  for(u32 i=0x7f000/2;i<map.ram.size();i++)assert(!map.ram[i]);
  assert(map.regwrites==1);++cases;
 }
 // Reproduce the supplied failure fingerprint with the former map. Stop
 // when a store erases the loop opcode rather than pretending execution
 // continues through the overwritten instruction stream.
 {
  address_map old;old(0,0x7ffff).ram().mirror(0x80000).share("sound_ram");
  old.ram.fill(0xa55a);old.ram[0x6ba/2]=0x20c0;old.ram[0x6bc/2]=0x51c9;old.ram[0x6be/2]=0xfffc;
  u32 addr=0x7f000;
  while(old.ram[0x6ba/2]==0x20c0){old.write32(addr,0);addr+=4;assert(addr<=0x806bc);}
  assert(addr==0x806bc&&!old.ram[0]&&!old.ram[0x6ba/2]);
  assert(old.ram[0x6bc/2]==0x51c9&&old.ram[0x6be/2]==0xfffc);++cases;
 }
 std::cout<<"Sound map: "<<cases<<" boundary/clear-loop cases passed for Saturn and ST-V\n";
}
'''.replace('// FUNCTIONS','\n'.join(functions))
with tempfile.TemporaryDirectory(prefix='sound-map-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

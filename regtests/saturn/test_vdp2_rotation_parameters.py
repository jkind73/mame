#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production rotation-table unpacking against ST-058 field-width/bit-position oracle.

RPRCTL reload bits are set: this validates decoding, not raster reload/latch timing.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');p.add_argument('--mutation',action='store_true');a=p.parse_args()
src=subprocess.check_output(['git','show','558f522f:src/mame/sega/saturn.cpp'],cwd=ROOT,text=True) if a.baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text()
head=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
f=extract(src,'void saturn_state::vdp2_fill_rotation_parameter_table(')
if a.mutation:f=f.replace('& word_mask]', '& (word_mask | 0x3ffff)]')
macsrc=re.sub(r'/\*.*?\*/','',src.replace('\\\n',' '),flags=re.S)
defs={m[1]:m[0] for m in re.finditer(r'^#define[ \t]+(VDP2_\w+)[ \t]+[^\n]+',macsrc,re.M)}
names=set(re.findall(r'VDP2_\w+',f));pending=list(names)
while pending:
 name=pending.pop()
 for dependency in re.findall(r'VDP2_\w+',defs[name]):
  if dependency not in names:names.add(dependency);pending.append(dependency)
# name, word, first source bit, signed width, ignored low bits, output shift
schema=[]
for i,n in enumerate(('xst','yst','zst')):schema.append((n,i,0,29,6,0))
for i,n in enumerate(('dxst','dyst','dx','dy'),3):schema.append((n,i,0,19,6,0))
for i,n in enumerate(('A','B','C','D','E','F'),7):schema.append((n,i,0,20,6,0))
for n,i,lo in (('px',13,16),('py',13,0),('pz',14,16),('cx',15,16),('cy',15,0),('cz',16,16)):schema.append((n,i,lo,14,0,16))
for i,n in enumerate(('mx','my'),17):schema.append((n,i,0,30,6,0))
for i,n in enumerate(('kx','ky'),19):schema.append((n,i,0,24,0,0))
schema += [('kast',21,0,32,6,0),('dkast',22,0,26,6,0),('dkax',23,0,26,6,0)]
checks='\n'.join(f'assert(uint32_t(r.{n})==expected({i},{lo},{width},{ignored},{shift}));' for n,i,lo,width,ignored,shift in schema)
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
struct input {bool code_pressed_once(int){return false;}};
struct machine_stub {struct input &input(){static struct input i;return i;}};
struct video {bool large=false;bool get_vramsz(){return large;}};
struct saturn_state {
 video dev;video *m_vdp2=&dev;
 // TABLE
 uint16_t m_vdp2_regs[256]{};std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 int m_vdpdebug_roz=0;machine_stub &machine(){static machine_stub m;return m;}
 void vdp2_fill_rotation_parameter_table(uint8_t);
};
#define DEBUG_DRAW_ROZ 0
#define JOYCODE_Y_UP_SWITCH 1
#define JOYCODE_Y_DOWN_SWITCH 2
#define LOGMASKED(...) ((void)0)
#define popmessage(...) ((void)0)
// MACROS
// FUNCTION
int main(){saturn_state s;unsigned cases=0;
 s.m_vdp2_regs[0xb2/2]=0x707;
 for(bool large:{false,true})for(unsigned address:{0u,0x40u,0x80u,0x7fffcu,0xffffcu})for(unsigned parameter:{1u,2u})
 for(unsigned bit=0;bit<32;++bit)for(unsigned pattern:{0u,0xffffffffu,0x12345678u}){
  s.dev.large=large;unsigned capacity=large?262144:131072;
  unsigned ptr=address/2;s.m_vdp2_regs[0xbc/2]=ptr>>16;s.m_vdp2_regs[0xbe/2]=ptr;
  unsigned base=((address&~0x80u)|((parameter-1)*0x80))/4;
  std::fill(s.m_vdp2_vram.begin(),s.m_vdp2_vram.end(),0xdeadbeef);
  uint32_t words[24];
  for(unsigned i=0;i<24;++i)s.m_vdp2_vram[(base+i)%capacity]=words[i]=(1u<<bit)^(pattern*(i+1));
  s.vdp2_fill_rotation_parameter_table(parameter);auto &r=s.current_rotation_table;
  auto expected=[&](int index,int low,int width,int ignored,int shift){
   uint64_t mask=(uint64_t(1)<<width)-1;
   uint64_t raw=(uint64_t(words[index])>>low)&mask;
   raw&=~((uint64_t(1)<<ignored)-1);
   int64_t value=raw;
   if(width!=32&&(raw&(uint64_t(1)<<(width-1))))value-=uint64_t(1)<<width;
   return uint32_t(value*(int64_t(1)<<shift));
  };
  // CHECKS
  ++cases;
 }
 std::cout<<cases<<" rotation parameter unpacking configurations passed\n";
}
'''
code=code.replace('// TABLE',extract(head,'struct rotation_table {')+' current_rotation_table;').replace('// MACROS','\n'.join(defs[n] for n in sorted(names))).replace('// FUNCTION',f).replace('// CHECKS',checks)
with tempfile.TemporaryDirectory(prefix='saturn-rotation-parameters-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production NBG2/NBG3 dispatch and register decoding for ST-058 Table 5.2.

Cycle-pattern presence checking is also production code. Final tile rendering is
recorded, not a pixel/bus model. --baseline must compile and fail an assertion.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');a=p.parse_args()
src=subprocess.check_output(['git','show','4ff73852:src/mame/sega/saturn.cpp'],cwd=ROOT,text=True) if a.baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(sig):
 start=src.index(sig);end=src.index('{',start)+1;depth=1
 while depth:
  depth+=(src[end]=='{')-(src[end]=='}');end+=1
 return src[start:end]
funcs=[extract(sig) for sig in ('void saturn_state::vdp2_draw_NBG2(', 'void saturn_state::vdp2_draw_NBG3(', 'uint8_t saturn_state::vdp2_check_vram_cycle_pattern_registers(')]
f=extract('static constexpr uint8_t vdp2_cc_blend_level(')+'\n'+'\n'.join(funcs)
# Extract register macros and their dependencies from production; do not mock
# the ZMCTL or CHCTLA bit positions with separate per-field test variables.
macro_source=re.sub(r'/\*.*?\*/','',src.replace('\\\n',' '),flags=re.S)
definitions={m[1]:m[0] for m in re.finditer(r'^#define[ \t]+(VDP2_\w+)[ \t]+[^\n]+',macro_source,re.M)}
needed=set(re.findall(r'VDP2_\w+',f));pending=list(needed)
while pending:
 name=pending.pop()
 assert name in definitions,name
 for dependency in re.findall(r'VDP2_\w+',definitions[name]):
  if dependency not in needed:needed.add(dependency);pending.append(dependency)
fields=sorted(set(re.findall(r'current_tilemap\.(\w+)',f))-{'map_offset','window_control'})
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
struct rectangle {};
struct bitmap_rgb32 {bool drawn=false;};
struct saturn_state {
 uint16_t m_vdp2_regs[256]{};
 struct { // FIELDS
  int map_offset[16]{};
  struct {int logic=0,enabled[2]{},sprite_window=0,area[2]{};} window_control;
 } current_tilemap;
 // DECLS
 void vdp2_check_fade_control_for_layer(){}
 void vdp2_check_tilemap(bitmap_rgb32 &image,const rectangle&){image.drawn=current_tilemap.enabled;}
};
#define STV_TRANSPARENCY_NONE 1
#define STV_TRANSPARENCY_PEN 0
// MACROS
// FUNCTIONS
int main(){
 saturn_state s;unsigned cases=0;
 // Table 5.2 rows, including unrestricted range. Quarter reduction with
 // 256 colors is prohibited and is not assigned a hardware result here.
 struct setting {unsigned colors,range;bool blocked;};
 constexpr setting settings[]={{0,0,false},{0,1,false},{0,2,true},{0,3,true},{1,0,false},{1,1,true}};
 for(auto n0:settings)for(auto n1:settings)for(unsigned bgon=0;bgon<16;++bgon)
 for(bool cycles:{false,true})for(unsigned increment:{0u,0x8000u,0x10000u}){
  s.m_vdp2_regs[0x20/2]=bgon;
  s.m_vdp2_regs[0x28/2]=(n0.colors<<4)|(n1.colors<<12);
  s.m_vdp2_regs[0x98/2]=n0.range|(n1.range<<8);
  // Resource reservation depends on ZMCTL even when the current transform
  // magnifies or has unit increment. It is not a test for actual shrink.
  s.m_vdp2_regs[0x78/2]=increment>>16;s.m_vdp2_regs[0x7a/2]=increment;
  s.m_vdp2_regs[0x88/2]=increment>>16;s.m_vdp2_regs[0x8a/2]=increment;
  for(unsigned i=0x10/2;i<=0x1e/2;++i)s.m_vdp2_regs[i]=cycles?0x2367:0xffff;
  bitmap_rgb32 n2,n3;
  s.vdp2_draw_NBG2(n2,{});s.vdp2_draw_NBG3(n3,{});
  assert(n2.drawn==bool((bgon&4)&&cycles&&!n0.blocked));
  assert(n3.drawn==bool((bgon&8)&&cycles&&!n1.blocked));
  // Removing the reservation must restore the requested planes, without
  // needing a reset or changing their own BGON/cycle settings.
  s.m_vdp2_regs[0x98/2]=0;
  s.vdp2_draw_NBG2(n2,{});s.vdp2_draw_NBG3(n3,{});
  assert(n2.drawn==bool((bgon&4)&&cycles));assert(n3.drawn==bool((bgon&8)&&cycles));
  ++cases;
 }
 std::cout<<cases<<" reduction register/layer restriction scenarios passed\n";
}
'''
code=code.replace('// FIELDS','\n'.join('int '+name+'=0;' for name in fields))
code=code.replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','').strip()+';' for x in funcs))
code=code.replace('// MACROS','\n'.join(definitions[n] for n in sorted(needed))).replace('// FUNCTIONS',f)
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-reduction-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

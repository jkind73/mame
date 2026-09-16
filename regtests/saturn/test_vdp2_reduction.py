#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production NBG1/NBG2/NBG3 dispatch for ST-058 p.61 and Table 5.2.

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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',nargs='?',const='4ff73852');
p.add_argument('--mutation',choices=['color-n1','color-n2','color-n3']);a=p.parse_args()
src=subprocess.check_output(['git','show',a.baseline+':src/mame/sega/saturn.cpp'],cwd=ROOT,text=True) if a.baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text()
if a.mutation:
 conditions={
  'color-n1':'VDP2_N0CHCN == 0x04',
  'color-n2':'VDP2_N0CHCN == 0x02 || VDP2_N0CHCN == 0x03 || VDP2_N0CHCN == 0x04',
  'color-n3':'VDP2_N0CHCN == 0x04 || VDP2_N1CHCN == 0x02 || VDP2_N1CHCN == 0x03',
 }
 original='if ('+conditions[a.mutation]+')'
 assert src.count(original)==1
 src=src.replace(original,'if (false)',1)
def extract(sig):
 start=src.index(sig);end=src.index('{',start)+1;depth=1
 while depth:
  depth+=(src[end]=='{')-(src[end]=='}');end+=1
 return src[start:end]
funcs=[extract(sig) for sig in ('void saturn_state::vdp2_draw_NBG0(', 'void saturn_state::vdp2_draw_NBG1(', 'void saturn_state::vdp2_draw_NBG2(', 'void saturn_state::vdp2_draw_NBG3(', 'uint8_t saturn_state::vdp2_check_vram_cycle_pattern_registers(')]
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
 // Fetch scheduling is independently exercised by test_vdp2_cycle_patterns.py.
 bool m_vdp2_fetch_access_active=false;

 uint16_t m_vdp2_regs[256]{};
 struct device {int get_hreso(){return 0;}int get_vramsz(){return 0;}int get_lsmd(){return 0;}} video;
 device *m_vdp2=&video;
 struct { // FIELDS
  int map_offset[16]{};
  struct {int logic=0,enabled[2]{},sprite_window=0,area[2]{};} window_control;
 } current_tilemap;
 int rotations=0;
 void vdp2_draw_rotation_screen(bitmap_rgb32 &image,const rectangle&,int parameter){
  assert(parameter==2&&current_tilemap.layer_name==0x81);
  assert(current_tilemap.scrollx==0&&current_tilemap.scrolly==0);
  assert(current_tilemap.incx==65536&&current_tilemap.incy==65536);
  assert(!current_tilemap.linescroll_enable&&!current_tilemap.vertical_linescroll_enable);
  assert(!current_tilemap.vertical_cell_scroll_enable&&!current_tilemap.linezoom_enable&&!current_tilemap.roz_mode3);
  assert(!current_tilemap.window_control.enabled[0]&&!current_tilemap.window_control.enabled[1]);
  image.drawn=current_tilemap.enabled;++rotations;
 }
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
 for(auto n0:settings)for(auto n1:settings)for(unsigned bgon=0;bgon<64;++bgon)
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
  assert(n2.drawn==bool((bgon&4)&&((bgon&0x30)!=0x30)&&cycles&&!n0.blocked));
  assert(n3.drawn==bool((bgon&8)&&((bgon&0x30)!=0x30)&&cycles&&!n1.blocked));
  // Removing the reservation must restore the requested planes, without
  // needing a reset or changing their own BGON/cycle settings.
  s.m_vdp2_regs[0x98/2]=0;
  s.vdp2_draw_NBG2(n2,{});s.vdp2_draw_NBG3(n3,{});
  assert(n2.drawn==bool((bgon&4)&&((bgon&0x30)!=0x30)&&cycles));assert(n3.drawn==bool((bgon&8)&&((bgon&0x30)!=0x30)&&cycles));
  ++cases;
 }
 std::cout<<cases<<" reduction register/layer restriction scenarios passed\n";
 cases=0;
 // Independent p.61 permitted-layer masks (bits 1=NBG1, 2=NBG2, 3=NBG3).
 constexpr unsigned allow0[]={14,14,10,10,0},allow1[]={14,14,6,6};
 constexpr setting all0[]={{0,0,false},{0,1,false},{0,2,true},{0,3,true},
                          {1,0,false},{1,1,true},{2,0,false},{3,0,false},{4,0,false}};
 constexpr setting all1[]={{0,0,false},{0,1,false},{0,2,true},{0,3,true},
                          {1,0,false},{1,1,true},{2,0,false},{3,0,false}};
 for(auto n0:all0)for(auto n1:all1)for(unsigned bgon=0;bgon<64;++bgon)
 for(bool cycles:{false,true})for(bool bitmap:{false,true}){
  s.m_vdp2_regs[0x20/2]=bgon;
  s.m_vdp2_regs[0x28/2]=(n0.colors<<4)|(n1.colors<<12)|(unsigned(bitmap)<<9);
  s.m_vdp2_regs[0x98/2]=n0.range|(n1.range<<8);
  for(unsigned i=0x10/2;i<=0x1e/2;++i)s.m_vdp2_regs[i]=cycles?((i&1)?0x6677:0x1235):0xffff;
  unsigned expected=bgon&allow0[n0.colors]&allow1[n1.colors];
  if(n0.blocked)expected&=~4u;
  if(n1.blocked)expected&=~8u;
  if(!cycles||(bgon&0x30)==0x30)expected=0;
  bitmap_rgb32 one,two,three;
  s.vdp2_draw_NBG1(one,{});s.vdp2_draw_NBG2(two,{});s.vdp2_draw_NBG3(three,{});
  assert(one.drawn==bool(expected&2));assert(two.drawn==bool(expected&4));assert(three.drawn==bool(expected&8));
  // Return to 16-color, non-reduced source modes; layers recover immediately.
  s.m_vdp2_regs[0x28/2]=0;s.m_vdp2_regs[0x98/2]=0;
  s.vdp2_draw_NBG1(one,{});s.vdp2_draw_NBG2(two,{});s.vdp2_draw_NBG3(three,{});
  assert(one.drawn==bool(cycles&&((bgon&0x30)!=0x30)&&(bgon&2)));assert(two.drawn==bool(cycles&&((bgon&0x30)!=0x30)&&(bgon&4)));assert(three.drawn==bool(cycles&&((bgon&0x30)!=0x30)&&(bgon&8)));
  ++cases;
 }
 std::cout<<cases<<" color-depth/reduction layer restriction scenarios passed\n";
 for(unsigned flags=0;flags<256;++flags){
  s.m_vdp2_regs[0x20/2]=0x30;
  s.m_vdp2_regs[0x9a/2]=flags;
  s.m_vdp2_regs[0x70/2]=123;s.m_vdp2_regs[0x74/2]=321;
  s.m_vdp2_regs[0x78/2]=2;s.m_vdp2_regs[0x7c/2]=3;
  s.m_vdp2_regs[0xd0/2]=0x3f;
  s.current_tilemap.roz_mode3=true;
  bitmap_rgb32 image;s.vdp2_draw_NBG0(image,{});assert(image.drawn);
 }
 assert(s.rotations==256);
 std::cout<<s.rotations<<" RBG1 shared-register setup cases passed\n";
}
'''
code=code.replace('// FIELDS','\n'.join('int '+name+'=0;' for name in fields))
code=code.replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','').strip()+';' for x in funcs))
code=code.replace('// MACROS','\n'.join(definitions[n] for n in sorted(needed))).replace('// FUNCTIONS',f)
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-reduction-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

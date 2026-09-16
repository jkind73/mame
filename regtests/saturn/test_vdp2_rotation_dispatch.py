#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute production rotation dispatch/cache setup with recording render stages.

Checks optimization eligibility, preserved window configuration/clip and unblended
source-cache flags. Pixel/VRAM renderers are stand-ins; pixel oracles live in the
bitmap and rotation-clip suites. --baseline compiles 69995fab and must fail.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');p.add_argument('--mutation',choices=('coefficient','blend','clear','screen-over','size'));a=p.parse_args()
src=subprocess.check_output(['git','show','69995fab:src/mame/sega/saturn.cpp'],cwd=ROOT,text=True) if a.baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
functions=[extract((ROOT/'src/mame/sega/saturn.cpp').read_text(),'unsigned saturn_state::vdp2_special_priority_mode('),extract((ROOT/'src/mame/sega/saturn.cpp').read_text(),'unsigned saturn_state::vdp2_special_color_mode('),extract(src,'uint8_t saturn_state::vdp2_is_rotation_applied('),extract(src,'void saturn_state::vdp2_draw_rotation_screen(')]
f='\n'.join(functions)
if a.mutation=='size':f=f.replace('RBG0_cache_data.vram_size[iRP - 1] != m_vdp2->get_vramsz() ||', '')
if a.mutation=='screen-over':f=f.replace('!(rot_parameter == 1 ? VDP2_RAOVR : VDP2_RBOVR)', '(rot_parameter != 0)')
if a.mutation=='clear':f=f.replace('fill(rgb_t::transparent(),','fill(rgb_t::black(),')
if a.mutation=='coefficient':
 f=f.replace('!(rot_parameter == 1 ? VDP2_RAKTE : VDP2_RBKTE)', '(rot_parameter != 0)')
if a.mutation=='blend':
 f=f.replace('current_tilemap.colour_calculation_enabled = colour_calculation_enabled;', 'current_tilemap.colour_calculation_enabled = colour_calculation_enabled; if (colour_calculation_enabled) current_tilemap.transparency |= STV_TRANSPARENCY_ALPHA;')
names=sorted(set(re.findall(r'VDP2_\w+',f))|{'VDP2_RAKTE','VDP2_RBKTE','VDP2_CCMD'})
fields=sorted((set(re.findall(r'current_tilemap\.(\w+)',f))|{'roz_mode3'})-{'window_control','map_offset'})
code=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
#include "palette.h"
struct rectangle {int min_x=0,max_x=0,min_y=0,max_y=0;int top()const{return min_y;}int bottom()const{return max_y;}void sety(int t,int b){min_y=t;max_y=b;}rectangle()=default;rectangle(int l,int r,int t,int b):min_x(l),max_x(r),min_y(t),max_y(b){}};
struct bitmap_rgb32 {bool source=false;bool valid()const{return source;}void allocate(int x,int y){assert(x==4096&&y==4096);source=true;}void fill(uint32_t color,const rectangle&){assert(color==0);} };
struct palette {uint32_t black_pen(){return rgb_t::black();}};
struct device {bool large=false;bool get_vramsz(){return large;}int hreso=0,lsmd=0;int get_hreso(){return hreso;}int get_lsmd(){return lsmd;}};
struct profiler {int start(int){return 0;}} g_profiler;
struct saturn_state {
 bool m_vdp2_composition_active=false;
 static constexpr int ROTATION_SCANLINES=1024;bool m_rotation_line_valid[ROTATION_SCANLINES]{};
 // DECLS
 // ROTATION
 struct { // REGS
 } regs;
 struct tilemap {
 // FIELDS
 int map_offset[16]{};
 struct {int logic=0,enabled[2]{},sprite_window=0,area[2]{};} window_control;
 } current_tilemap;
 struct {bitmap_rgb32 roz_bitmap[2];} m_vdp2_legacy;
 struct cache {bool vram_size[2]{};int is_cache_dirty=3,watch_vdp2_vram_writes=0;tilemap layer_data[2]{};int map_offset_min[2]{},map_offset_max[2]{},tile_offset_min[2]{},tile_offset_max[2]{};} RBG0_cache_data;
 struct {int map_offset_min=0,map_offset_max=0,tile_offset_min=0,tile_offset_max=0;} vdp2_layer_data;
 device dev;device *m_vdp2=&dev;palette pal;palette *m_palette=&pal;
 std::vector<int> loaded_lines;
 int loaded=0,direct=0,copied=0,built=0,captured_flags=0;
 tilemap captured{};rectangle captured_clip{};
 void vdp2_fill_rotation_parameter_table(int parameter){loaded=parameter;}
 void vdp2_load_rotation_line(int parameter,int line){loaded=parameter;loaded_lines.push_back(line);}
 bool vdp2_are_map_registers_equal(){return false;}
 void vdp2_check_tilemap(bitmap_rgb32 &b,const rectangle &clip){
  if(b.source){++built;assert(current_tilemap.colour_calculation_enabled==0);assert((current_tilemap.transparency&6)==0);}
  else {++direct;captured=current_tilemap;captured_clip=clip;}
 }
 int vdp2_apply_window_on_layer(rectangle &clip){clip.min_x=4;clip.max_x=8;return 1;}
 void vdp2_copy_roz_bitmap(bitmap_rgb32&,bitmap_rgb32&,const rectangle&,int,int,int,int,int){++copied;captured_flags=current_tilemap.transparency;}
};
#define RP current_rotation_table
#define STV_TRANSPARENCY_NONE 1
#define STV_TRANSPARENCY_ALPHA 4
#define STV_TRANSPARENCY_ADD_BLEND 2
#define LOGMASKED(...) ((void)0)
#define popmessage(...) ((void)0)
#define PROFILER_USER1 1
#define PROFILER_USER2 2
// MACROS
// FUNCTIONS
// UNDEFS
int main(){
 saturn_state s;bitmap_rgb32 output;unsigned cases=0;
 for(int parameter:{1,2})for(int mode:{0,1,2,3})for(int reason=0;reason<11;++reason)
 for(int windows=0;windows<32;++windows)for(int blend:{0,1,2}){
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;
  s.regs.VDP2_RPMD=mode;s.regs.VDP2_RAKTE=0;s.regs.VDP2_RBKTE=0;
  s.dev.hreso=0;s.dev.lsmd=0;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;
  if(reason>=7&&reason<=9){if(parameter==1)s.regs.VDP2_RAOVR=reason-6;else s.regs.VDP2_RBOVR=reason-6;}
  if(reason==10){if(parameter==1)s.regs.VDP2_RBOVR=1;else s.regs.VDP2_RAOVR=1;}
  if(reason==1){if(parameter==1)s.regs.VDP2_RAKTE=1;else s.regs.VDP2_RBKTE=1;}
  if(reason==2){if(parameter==1)s.regs.VDP2_RBKTE=1;else s.regs.VDP2_RAKTE=1;}
  if(reason==3)r.xst=65536;
  if(reason==4)r.yst=65536;
  if(reason==5)s.dev.hreso=2;
  if(reason==6)s.dev.lsmd=3;
  s.regs.VDP2_R0W0E=windows&1;s.regs.VDP2_R0W1E=(windows>>1)&1;
  s.regs.VDP2_R0W0A=(windows>>2)&1;s.regs.VDP2_R0W1A=(windows>>3)&1;s.regs.VDP2_R0LOG=windows>>4;
  s.regs.VDP2_CCMD=blend==2;
  s.current_tilemap={};s.current_tilemap.bitmap_enable=1;s.current_tilemap.bitmap_size=0;
  s.current_tilemap.roz_mode3=mode==3;s.current_tilemap.colour_calculation_enabled=blend!=0;
  // Stale flags from an earlier parameter/render pass must not enter the cache.
  s.current_tilemap.transparency=1|((mode<2&&(reason==0||reason==2||reason==10))?0:6);
  s.RBG0_cache_data={};s.direct=s.copied=s.built=0;
  s.vdp2_draw_rotation_screen(output,{1,14,1,6},parameter);
  assert(s.loaded==parameter);
  bool fast=mode<2&&(reason==0||reason==2||reason==10);
  assert(s.direct==int(fast)&&s.copied==int(!fast));
  if(fast){
   auto &w=s.captured.window_control;
   assert(w.enabled[0]==(windows&1)&&w.enabled[1]==((windows>>1)&1));
   assert(w.area[0]==((windows>>2)&1)&&w.area[1]==((windows>>3)&1)&&w.logic==(windows>>4));
   assert(s.captured_clip.min_x==1&&s.captured_clip.max_x==14&&s.captured_clip.min_y==1&&s.captured_clip.max_y==6);
  }else{
   assert(s.built==1&&s.captured_flags==1);
   assert(s.current_tilemap.colour_calculation_enabled==(blend!=0));
   // A repeated output pass reuses the same unblended source cache.
   s.built=0;s.vdp2_draw_rotation_screen(output,{5,9,2,4},parameter);assert(s.built==0);
  }
  ++cases;
 }
 std::cout<<cases<<" rotation dispatch/window/cache configuration cases passed\n";
 s.current_tilemap.mosaic_screen_enabled=1;
 auto saved_rotation=s.current_rotation_table;s.current_rotation_table={};
 s.current_rotation_table.A=s.current_rotation_table.E=s.current_rotation_table.dx=s.current_rotation_table.dyst=s.current_rotation_table.kx=s.current_rotation_table.ky=65536;
 s.dev.hreso=s.dev.lsmd=0;s.regs.VDP2_RPMD=s.regs.VDP2_RAKTE=s.regs.VDP2_RAOVR=0;
 assert(s.vdp2_is_rotation_applied(1));s.current_tilemap.mosaic_screen_enabled=0;s.regs.VDP2_R0SWE=1;assert(s.vdp2_is_rotation_applied(1));s.regs.VDP2_R0SWE=0;s.current_rotation_table=saved_rotation;
 s.current_tilemap={};s.current_tilemap.bitmap_enable=1;s.current_tilemap.transparency=1;
 s.regs.VDP2_RPMD=s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=0;
 s.dev.hreso=s.dev.lsmd=0;auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;r.xst=65536;
 for(int y=1;y<=6;++y)s.m_rotation_line_valid[y]=true;
 s.RBG0_cache_data={};s.direct=s.copied=s.built=0;s.loaded_lines.clear();
 s.vdp2_draw_rotation_screen(output,{1,14,1,6},1);
 assert(s.copied==6&&s.direct==0&&s.built==1);
 assert((s.loaded_lines==std::vector<int>{1,2,3,4,5,6}));
 s.built=s.copied=0;s.loaded_lines.clear();s.vdp2_draw_rotation_screen(output,{5,9,2,4},1);
 assert(s.built==0&&s.copied==3);assert((s.loaded_lines==std::vector<int>{2,3,4}));
 s.regs.VDP2_SFCCMD=1;s.current_tilemap.colour_calculation_enabled=1;s.current_tilemap.layer_name=0;
 s.built=s.copied=s.direct=0;s.vdp2_draw_rotation_screen(output,{1,14,2,2},1);
 assert(s.built==0&&s.direct==0&&s.copied==1);
 s.regs.VDP2_SFCCMD=0;s.regs.VDP2_SFPRMD=1;s.current_tilemap.colour_calculation_enabled=0;
 s.RBG0_cache_data.is_cache_dirty=3;s.built=s.copied=s.direct=0;s.vdp2_draw_rotation_screen(output,{1,14,2,2},1);
 assert(s.built==0&&s.direct==0&&s.copied==1);
 s.regs.VDP2_SFCCMD=s.regs.VDP2_SFPRMD=0;s.m_vdp2_composition_active=true;s.current_rotation_table.xst=0;
 s.RBG0_cache_data.is_cache_dirty=3;s.built=s.copied=s.direct=0;s.vdp2_draw_rotation_screen(output,{1,14,2,2},1);
 assert(s.built==1&&s.direct==0&&s.copied==1);
 // Changing only VRSIZE must rebuild each independent A/B source cache.
 unsigned size_cases=0;
 for(bool bitmap:{false,true}){
  s.current_tilemap={};s.current_tilemap.bitmap_enable=bitmap;s.current_tilemap.transparency=1;
  s.RBG0_cache_data={};bool valid[2]{},cached_size[2]{};
  for(bool large:{false,true,true,false,false})for(int parameter:{1,2}){
   s.dev.large=large;s.built=0;s.vdp2_draw_rotation_screen(output,{1,14,2,2},parameter);
   bool rebuild=!valid[parameter-1]||cached_size[parameter-1]!=large;
   assert(s.built==int(rebuild));assert(s.RBG0_cache_data.vram_size[parameter-1]==large);
   valid[parameter-1]=true;cached_size[parameter-1]=large;
   s.built=0;s.vdp2_draw_rotation_screen(output,{5,9,2,2},parameter);assert(!s.built);++size_cases;
  }
 }
 std::cout<<size_cases<<" cell/bitmap A/B cache size-transition and reuse cases passed\n";
 std::cout<<"Latched-row dispatch reuses the untransformed cache across clips\n";
}
'''
code=code.replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','').strip()+';' for x in functions))
code=code.replace('// ROTATION',extract(header,'struct rotation_table {')+' current_rotation_table;')
code=code.replace('// REGS','\n'.join('int '+n+'=0;' for n in names)).replace('// FIELDS','\n'.join('int '+n+'=0;' for n in fields))
code=code.replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-dispatch-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-Wno-unused-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

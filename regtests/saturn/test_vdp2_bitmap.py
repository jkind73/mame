#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production bitmap pixels + real palette rebuild + real window/cache evaluation.

The layer configuration and memory arrays are fixtures, not full device dispatch.
Sprite mask dots are controlled inputs; the production framebuffer mask is tested
by test_sprite_scanout.py. This does not certify physical DAC timing.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('window','nibble','additive','fraction','sprite-logic'));a=p.parse_args()
source=(ROOT/'src/mame/sega/saturn.cpp').read_text();header=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(src,sig):
    start=src.index(sig);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
sigs=['void saturn_state::draw_'+n+'_bitmap(' for n in ('4bpp','8bpp','11bpp','rgb15','rgb32')]
sigs+=['void saturn_state::refresh_palette_data(', 'uint32_t saturn_state::vdp2_cram_r(', 'void saturn_state::vdp2_compute_color_offset(', 'void saturn_state::vdp2_get_window0_coordinates(', 'void saturn_state::vdp2_get_window1_coordinates(', 'int saturn_state::get_window_pixel(', 'int saturn_state::vdp2_window_process_pixel(', 'uint32_t saturn_state::vdp2_window_config(', 'void saturn_state::vdp2_window_cache_line(', 'inline int saturn_state::vdp2_window_process(']
funcs=[extract(source,s) for s in sigs]
decls='\n'.join(f[:f.index('{')].replace('saturn_state::','').strip()+';' for f in funcs)
functions=extract(source,'static constexpr uint8_t vdp2_expand_color5(')+'\n'+extract(source,'static void fixup_window_x(')+'\n'+'\n'.join(funcs)
if a.mutation=='sprite-logic':
    old='res = logic_or ? (res | keep) : (res & keep);'
    assert functions.count(old)==1
    functions=functions.replace(old,'res = logic_or ? (res & keep) : (res | keep);')
if a.mutation=='additive':functions=functions.replace('else if (VDP2_CCMD)', 'else if (false && VDP2_CCMD)')
if a.mutation=='window':functions=functions.replace('if (!vdp2_window_process(xdst, ydst))','if (false)')
if a.mutation=='nibble':functions=functions.replace('((xsrc & 1) ? 0 : 4)','((xsrc & 1) ? 4 : 0)')
if a.mutation=='fraction':functions=functions.replace('+ current_tilemap.scrollx_fraction', '+ 0').replace('+ current_tilemap.scrolly_fraction', '+ 0')
macros=sorted(set(re.findall(r'VDP2_\w+',functions)))
fields=sorted((set(re.findall(r'current_tilemap\.(\w+)',functions))|{'scrollx_fraction','scrolly_fraction'})-{'window_control'})
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
using offs_t=uint32_t;
struct rgb_t {uint32_t v;rgb_t(uint32_t a):v(a){}rgb_t(int r,int g,int b):v((r<<16)|(g<<8)|b){}operator uint32_t()const{return v;}};
int pal5bit(int v){return (v<<3)|(v>>2);}
uint32_t alpha_blend_r32(uint32_t d,uint32_t s,unsigned a){uint32_t result=0;for(int sh:{0,8,16})result|=((((s>>sh)&255)*a+((d>>sh)&255)*(256-a))>>8)<<sh;return result;}
uint32_t add_blend_r32(uint32_t d,uint32_t s){uint32_t out=0;for(int sh:{0,8,16})out|=std::min(255u,((d>>sh)&255)+((s>>sh)&255))<<sh;return out;}
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {std::array<uint32_t,96> pixels{};uint32_t &pix(int y,int x){assert(x>=0&&x<12&&y>=0&&y<8);return pixels.at(y*12+x);}};
struct palette {std::array<uint32_t,6144> pens{};void set_pen_color(unsigned i,uint32_t c){pens.at(i)=c;}void set_pen_color(unsigned i,int r,int g,int b){set_pen_color(i,rgb_t(r,g,b));}uint32_t pen(unsigned i){return pens.at(i);}};
struct vdp2 {int hreso=0,lsmd=0;int get_hreso(){return hreso;}int get_lsmd(){return lsmd;}bool get_vramsz(){return false;}};
struct saturn_state {
 bool vdp2_sprite_window(int x,int y){return (x+2*y)%3==0;}
 // DECLS
 struct { // REGS
 } regs;
 struct { // FIELDS
  struct {int logic=0,enabled[2]{},area[2]{};unsigned sprite_window=0;} window_control;
 } current_tilemap;
 palette pal;palette *m_palette=&pal;
 vdp2 device;vdp2 *m_vdp2=&device;
 std::array<uint32_t,1024> m_vdp2_cram{};
 std::array<uint32_t,0x40000> m_vdp2_vram{};
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 void mark_fade_effects_dirty(){}
 static constexpr int WINDOW_CACHE_WIDTH=1024;
 int m_window_cache_y=-1,m_roz_window_cache_y=-1,m_sprite_window_y=-1;uint32_t m_window_cache_cfg=0;
 uint8_t m_window_cache_line[1024]{};
 // INLINE
};
#define STV_TRANSPARENCY_NONE 1
// MACROS
// FUNCTIONS
int main(){
 auto ptr=std::make_unique<saturn_state>();auto &s=*ptr;auto &c=s.current_tilemap;
 for(unsigned i=0;i<1024;++i)s.m_vdp2_cram[i]=(i*0x31415927u)^0x82f0471b;
 s.regs.VDP2_CRMD=1;s.refresh_palette_data();
 auto *mem=s.m_vdp2_legacy.gfx_decode.get();
 for(unsigned i=0;i<0x100000;++i)mem[i]=(i*7+(i>>9)*11)%256;
 using draw=void(saturn_state::*)(bitmap_rgb32&,const rectangle&);
 draw drawers[]={&saturn_state::draw_4bpp_bitmap,&saturn_state::draw_8bpp_bitmap,&saturn_state::draw_11bpp_bitmap,&saturn_state::draw_rgb15_bitmap,&saturn_state::draw_rgb32_bitmap};
 unsigned cases=0;
 for(unsigned format=0;format<5;++format)for(int hreso:{0,2,4,6})for(int interlace:{0,3})
 for(int line:{0,1})for(int config=0;config<128;++config)for(int scale:{32768,65536,98304})for(int additive:{0,1})for(int phase:{0,0x4000,0xff00}){
  s.regs.VDP2_CCMD=additive;
  s.device.hreso=hreso;s.device.lsmd=interlace;
  auto &w=c.window_control;w.enabled[0]=config&1;w.enabled[1]=(config>>1)&1;w.area[0]=(config>>2)&1;w.area[1]=(config>>3)&1;w.logic=(config>>4)&1;w.sprite_window=(config&32)?1|((config&64)?2:0):0;
  s.regs.VDP2_W0SY=1;s.regs.VDP2_W0EY=6;s.regs.VDP2_W1SY=2;s.regs.VDP2_W1EY=5;
  s.regs.VDP2_WPSX0=4;s.regs.VDP2_WPEX0=10;s.regs.VDP2_WPSX1=8;s.regs.VDP2_WPEX1=16;
  s.regs.VDP2_W0LWE=line;s.regs.VDP2_W1LWE=0;s.regs.VDP2_W0LWTA=0;
  for(unsigned y=0;y<8;++y)s.m_vdp2_vram[y]=((4+y%3)<<16)|(10+y%3);
  c.scrollx_fraction=phase;c.scrolly_fraction=phase;
  c.incx=scale;c.incy=scale;c.scrollx=509;c.scrolly=254;c.bitmap_size=0;c.bitmap_map=3;
  c.bitmap_palette_number=1;c.colour_ram_address_offset=2;c.transparency=config&1;c.alpha=128;c.colour_calculation_enabled=(config>>1)&1;
  bitmap_rgb32 image,expected;
  image.pixels.fill(0x204060);expected=image;
  s.m_sprite_window_y=77;s.vdp2_window_cache_invalidate();assert(s.m_sprite_window_y==-1);
  const draw render=drawers[format];
  // Two odd partial rectangles must produce the same image as one full clip.
  (s.*render)(image,{1,5,1,6});(s.*render)(image,{6,10,1,6});
  bitmap_rgb32 full;full.pixels.fill(0x204060);(s.*render)(full,{1,10,1,6});assert(full.pixels==image.pixels);
  for(int y=1;y<=6;++y)for(int x=1;x<=10;++x){
   auto convert=[&](int value){return hreso==0?value/2:hreso==6?value*2:value;};
   int shift=line?((y>>(interlace==3))%3):0;
   bool in0=x>=convert(4+shift)&&x<=convert(10+shift)&&y>=1&&y<=6;
   bool in1=x>=convert(8)&&x<=convert(16)&&y>=2&&y<=5;
   bool allowed=w.logic?false:true;
   if(w.enabled[0]){bool value=w.area[0]?in0:!in0;allowed=w.logic?(allowed||value):(allowed&&value);}
   if(w.enabled[1]){bool value=w.area[1]?in1:!in1;allowed=w.logic?(allowed||value):(allowed&&value);}
   if(w.sprite_window){bool value=((x+2*y)%3==0)==bool(config&64);allowed=w.logic?(allowed||value):(allowed&&value);}
   if(!allowed)continue;
   unsigned sx=((x*scale+phase)/65536+509)%512,sy=((y*scale+phase)/65536+254)%256;
   unsigned dot=sx+sy*512,bytes=format==0?dot/2:format==1?dot:format==4?dot*4:dot*2;
   unsigned address=(bytes+3*0x20000)%0x80000,raw=mem[address];
   if(format==0)raw=(raw>>(sx%2?0:4))&15;
   if(format>=2)raw=(raw<<8)|mem[address+1];
   if(format==2)raw&=2047;
   if(format==4)raw=(raw<<16)|(mem[address+2]<<8)|mem[address+3];
   bool visible=format<3?raw!=0:format==3?(raw&0x8000)!=0:(raw&0x80000000)!=0;
   if(!visible&&!c.transparency)continue;
   uint32_t color;
   if(format<3){unsigned index=raw+(format<2?768:0);unsigned word=s.m_vdp2_cram[index/2]>>(index%2?0:16);color=rgb_t(pal5bit(word&31),pal5bit((word>>5)&31),pal5bit((word>>10)&31));}
   else if(format==3)color=rgb_t(pal5bit(raw&31),pal5bit((raw>>5)&31),pal5bit((raw>>10)&31));
   else color=rgb_t(raw&255,(raw>>8)&255,(raw>>16)&255);
   uint32_t blended;
   if(additive)blended=rgb_t(std::min(255u,32+((color>>16)&255)),std::min(255u,64+((color>>8)&255)),std::min(255u,96+(color&255)));
   else blended=alpha_blend_r32(0x204060,color,128);
   expected.pix(y,x)=c.colour_calculation_enabled?blended:color;
  }
  assert(expected.pixels==image.pixels);++cases;
 }
 std::cout<<cases<<" bitmap/palette/window/partial-clip images passed\n";
}
'''
code=code.replace('// DECLS',decls).replace('// REGS','\n'.join('unsigned '+n+'=0;' for n in macros)).replace('// FIELDS','\n'.join('int '+n+'=0;' for n in fields))
code=code.replace('// INLINE',extract(header,'int vdp2_window_all_disabled() const')+'\n'+extract(header,'void vdp2_window_cache_invalidate()'))
code=code.replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in macros)).replace('// FUNCTIONS',functions)
# Macros apply only to production bodies, not explicit test register members.
code=code.replace('int main(){','\n'.join('#undef '+n for n in macros)+'\nint main(){')
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-bitmap-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

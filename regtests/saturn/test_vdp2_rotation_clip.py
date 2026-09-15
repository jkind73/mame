#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production rotation compositor: split clips, coefficient paths and window calls.

Window masks and coefficient fetch are recording stand-ins. Does not qualify
physical coefficient precision, parameter loading or special-effect composition.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('origin','window','coverage','over','over-name','over-flip'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
head=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
bitmap_functions=[extract(src,'void saturn_state::draw_'+name+'_bitmap(') for name in ('4bpp','8bpp','11bpp','rgb15','rgb32')]
over_function=extract(src,'rgb_t saturn_state::vdp2_screen_over_pattern_pixel(')
f=over_function+'\n'+'\n'.join(bitmap_functions)+'\n'+extract(src,'static inline uint32_t coef_delta(')+'\n'+extract(src,'void saturn_state::vdp2_copy_roz_bitmap(')
if a.mutation=='origin':
 f=f.replace('xs = uint32_t(xs) + uint32_t(int64_t(dxs) * cliprect.left());','(void)0;').replace('ys = uint32_t(ys) + uint32_t(int64_t(dys) * cliprect.left());','(void)0;')
if a.mutation=='window':
 f=f.replace('if (!vdp2_roz_window(hcnt, vcnt))','if (false)').replace('if (current_tilemap.roz_mode3 &&','if (false && current_tilemap.roz_mode3 &&')
if a.mutation=='coverage':f=f.replace('if (pix.a())','if (pix & 0xffffff)')
if a.mutation=='over':f=f.replace('if (outside && !repeat_pattern)','if (outside)')
if a.mutation=='over-name':f=f.replace('iRP == 1 ? VDP2_OVPNRA : VDP2_OVPNRB','VDP2_OVPNRA')
if a.mutation=='over-flip':f=f.replace('x = ~x','x = x').replace('y = ~y','y = y')
names=sorted(set(re.findall(r'VDP2_\w+',f))|{'VDP2_OVPNRB'})
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
using s64=int64_t;
int32_t mul_fixed32(int32_t a,int32_t b){return uint32_t((int64_t(a)*b)>>16);}
bool BIT(unsigned a,int b){return (a>>b)&1;}
#include "palette.h"
uint32_t alpha_blend_r32(uint32_t d,uint32_t s,unsigned a){uint32_t out=0;for(int sh:{0,8,16})out|=((((s>>sh)&255)*a+((d>>sh)&255)*(256-a))>>8)<<sh;return out;}
uint32_t add_blend_r32(uint32_t d,uint32_t s){uint32_t out=0;for(int sh:{0,8,16})out|=std::min(255u,((s>>sh)&255)+((d>>sh)&255))<<sh;return out;}
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {int w,h;std::vector<uint32_t> pixels;bitmap_rgb32(int W,int H):w(W),h(H),pixels(W*H,0x123456){}uint32_t &pix(int y,int x=0){assert(x>=0&&x<w&&y>=0&&y<h);return pixels[y*w+x];}};
struct device {int lsmd=0,hreso=0;int vramsz=0;int get_vramsz(){return vramsz;}int get_lsmd(){return lsmd;}int get_hreso(){return hreso;}};
struct palette {
 bool indexed=false;
 uint32_t pen(unsigned index){if(indexed)return 0xff000000|(index*7919&0xffffff);return index==2?rgb_t(255,0,0):rgb_t::black();}
};
struct saturn_state {
 rgb_t vdp2_screen_over_pattern_pixel(uint16_t,int,int);
 // BITMAP_DECLS
 palette pal;palette *m_palette=&pal;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 bool vdp2_window_process(int,int){return true;}
 void vdp2_compute_color_offset(int*,int*,int*,int){assert(false);}
 // ROTATION
 struct { // REGS
 } regs;
 struct {int colour_calculation_enabled=0,transparency=1,fade_control=0,alpha=120;
 int pattern_data_size=0,bitmap_enable=0,tile_size=0,colour_depth=0,character_number_supplement=0,supplementary_character_bits=0,supplementary_palette_bits=0;
 int incx=65536,incy=65536,scrollx=0,scrolly=0,bitmap_map=0,bitmap_size=0;
 int linescroll_enable=0,vertical_linescroll_enable=0,bitmap_palette_number=0,colour_ram_address_offset=0;
 bool roz_mode3=false;} current_tilemap;
 device dev;device *m_vdp2=&dev;
 bool window=false;unsigned coefficient=65536;bool blank_coefficient=false;
 uint32_t vdp2_read_rotation_coefficient(uint32_t){return coefficient|(blank_coefficient?0x80000000:0);}
 bool vdp2_roz_window(int x,int y){return !window||(x>=3&&x<=11&&y>=2&&y<=5);}
 bool vdp2_roz_mode3_window(int x,int y,int parameter){return ((x+y)&1)==parameter;}
 void vdp2_compute_color_offset_UINT32(rgb_t*,int){assert(false);}
 void vdp2_copy_roz_bitmap(bitmap_rgb32&,bitmap_rgb32&,const rectangle&,int,int,int,int,int);
};
#define LOGMASKED(...) ((void)0)
#define RP current_rotation_table
#define STV_TRANSPARENCY_NONE 1
#define STV_TRANSPARENCY_ALPHA 4
#define STV_TRANSPARENCY_ADD_BLEND 2
// MACROS
// FUNCTIONS
// UNDEFS
int main(){
 saturn_state s;auto &r=s.current_rotation_table;
 bitmap_rgb32 source(64,64);
 for(int y=0;y<64;++y)for(int x=0;x<64;++x)source.pix(y,x)=0xff800000|(y<<8)|x;
 unsigned cases=0;
 for(int parameter:{1,2})for(int coeff_mode:{0,1,2,3})for(int path:{0,1,2})
 for(bool window:{false,true})for(bool selection:{false,true})for(bool blank:{false,true})
 for(int dx:{-65536,32768,65536,131072})for(int blend:{0,1,2})for(int display=0;display<4;++display){
  s.dev.hreso=(display&1)?2:0;s.dev.lsmd=(display&2)?3:0;
  s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;
  s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=coeff_mode;
  s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=2;
  s.window=window;s.blank_coefficient=blank;s.current_tilemap.roz_mode3=selection;
  s.current_tilemap.colour_calculation_enabled=blend!=0;s.current_tilemap.transparency=1;s.regs.VDP2_CCMD=blend==2;
  r={};r.A=r.E=r.kx=r.ky=65536;r.xst=20*65536;r.yst=8*65536;
  r.dx=dx;r.dy=32768;r.dyst=65536;r.dkax=path==2?65536:0;
  s.coefficient=coeff_mode==3?2*65536:65536;
  bitmap_rgb32 full(16,8),parts(16,8),expected(16,8);
  s.vdp2_copy_roz_bitmap(full,source,{1,14,1,6},parameter,64,64,64,64);
  s.vdp2_copy_roz_bitmap(parts,source,{1,4,1,6},parameter,64,64,64,64);
  s.vdp2_copy_roz_bitmap(parts,source,{5,9,1,6},parameter,64,64,64,64);
  s.vdp2_copy_roz_bitmap(parts,source,{10,14,1,6},parameter,64,64,64,64);
  assert(full.pixels==parts.pixels);
  for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
   if(blank&&path)continue;
   if(window&&!(x>=3&&x<=11&&y>=2&&y<=5))continue;
   if(selection&&((x+y)&1)!=parameter-1)continue;
   // Preserve the existing per-dot high-res integer-counter convention;
   // its precision difference from the per-line walker is not certified here.
   int hfixed=path==2?(x>>(display&1))*65536:(x*65536)>>(display&1);
   int vfixed=(y*65536)>>((display>>1)&1);
   int sx=(20*65536+int64_t(dx)*hfixed/65536)/65536+(path&&coeff_mode==3?2:0);
   int sy=(8*65536+vfixed+hfixed/2)/65536;
   if(sx<0||sx>=64||sy<0||sy>=64)continue;
   unsigned color=0xff800000|(sy<<8)|sx;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(full.pixels==expected.pixels);++cases;
 }

 // Execute actual bitmap writers into a transparent cache, then rotate it.
 // Color zero must remain distinguishable from a dot that was never written.
 using draw=void(saturn_state::*)(bitmap_rgb32&,const rectangle&);
 draw drawers[]={&saturn_state::draw_4bpp_bitmap,&saturn_state::draw_8bpp_bitmap,&saturn_state::draw_11bpp_bitmap,&saturn_state::draw_rgb15_bitmap,&saturn_state::draw_rgb32_bitmap};
 unsigned coverage_cases=0;
 s.dev.hreso=s.dev.lsmd=0;s.window=false;s.blank_coefficient=false;s.coefficient=65536;
 s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=0;
 s.current_tilemap.roz_mode3=false;
 for(unsigned format=0;format<5;++format)for(bool opaque:{false,true}){
  bitmap_rgb32 cache(512,256);std::fill(cache.pixels.begin(),cache.pixels.end(),0);
  auto *mem=s.m_vdp2_legacy.gfx_decode.get();
  std::fill_n(mem,0x100000,0);
  for(unsigned y=0;y<256;++y)for(unsigned x=0;x<512;++x){
   unsigned kind=(x+y)%4;
   uint32_t raw=format<3?(kind==3?0:kind):format==3?(kind==1?0x8000:kind==2?0x801f:kind==3?0x1f:0):(kind==1?0x80000000:kind==2?0x800000ff:kind==3?0xff:0);
   unsigned dot=y*512+x;
   if(format==0)mem[dot/2]|=raw<<(x%2?0:4);
   else if(format==1)mem[dot]=raw;
   else {unsigned bytes=format==4?4:2;for(unsigned i=0;i<bytes;++i)mem[dot*bytes+i]=raw>>((bytes-i-1)*8);}
  }
  s.current_tilemap.transparency=opaque?1:0;s.current_tilemap.colour_calculation_enabled=0;
  const draw render=drawers[format];
  (s.*render)(cache,{0,511,0,255});
  for(int y=0;y<256;++y)for(int x=0;x<512;++x){
   unsigned kind=(x+y)%4;bool visible=opaque||kind==1||kind==2;
   uint32_t color=kind==2||(format>=3&&kind==3)?0xffff0000:0xff000000;
   assert(cache.pix(y,x)==(visible?color:0));
  }
  for(int path:{0,1,2})for(int parameter:{1,2})for(int blend:{0,1,2})for(bool reverse:{false,true}){
   s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;
   s.regs.VDP2_CCMD=blend==2;s.current_tilemap.transparency=opaque?1:0;
   s.current_tilemap.colour_calculation_enabled=blend!=0;
   r={};r.A=r.E=r.kx=r.ky=r.dyst=65536;r.dx=reverse?-65536:65536;
   r.xst=(reverse?30:2)*65536;r.yst=3*65536;r.dkax=path==2?65536:0;
   bitmap_rgb32 out(16,8),expected(16,8);
   s.vdp2_copy_roz_bitmap(out,cache,{1,14,1,6},parameter,512,256,512,256);
   for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
    unsigned kind=((reverse?30-x:2+x)+3+y)%4;
    if(!opaque&&kind!=1&&kind!=2)continue;
    uint32_t color=kind==2||(format>=3&&kind==3)?0xffff0000:0xff000000;
    expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
   }
   assert(out.pixels==expected.pixels);++coverage_cases;
  }
 }
 // Independent decoder oracle: assemble character-number bits using the
 // ST-058 one-word format bit wiring, rather than the production expressions.
 auto reference=[&](uint16_t name,int x,int y)->uint32_t{
  auto &t=s.current_tilemap;unsigned code=0;
  int low=t.character_number_supplement?12:10;
  for(int bit=0;bit<low;++bit)if(name&(1u<<bit))code|=1u<<(bit+(t.tile_size?2:0));
  for(int bit=0;bit<5;++bit){
   if(!(t.supplementary_character_bits&(1u<<bit)))continue;
   int dest=-1;
   if(t.tile_size){if(bit<2)dest=bit;else if(!t.character_number_supplement||bit==4)dest=bit+10;}
   else if(!t.character_number_supplement||bit>=2)dest=bit+10;
   if(dest>=0)code|=1u<<dest;
  }
  int size=t.tile_size?16:8;x=(x%size+size)%size;y=(y%size+size)%size;
  if(!t.character_number_supplement){if(name&1024)x=size-1-x;if(name&2048)y=size-1-y;}
  unsigned sizes[]={32,64,128,128,256};unsigned bpc=sizes[t.colour_depth];
  unsigned addr=code*32+(y/8*2+x/8)*bpc;
  unsigned bitpos=((y%8)*8+x%8)*(bpc*8/64);
  uint32_t raw=0;
  unsigned bits=bpc*8/64,mask=s.dev.vramsz?0xfffff:0x7ffff;
  for(unsigned bit=0;bit<bits;++bit){unsigned pos=bitpos+bit;raw=(raw<<1)|((s.m_vdp2_legacy.gfx_decode[(addr+pos/8)&mask]>>(7-pos%8))&1);}
  if(t.colour_depth==2)raw%=2048;
  bool visible=t.colour_depth<3?raw!=0:raw>=(t.colour_depth==3?0x8000u:0x80000000u);
  if(!visible&&!(t.transparency&1))return 0;
  if(t.colour_depth==3){unsigned r=raw%32,g=raw/32%32,b=raw/1024%32;return 0xff000000|((r*8+r/4)<<16)|((g*8+g/4)<<8)|(b*8+b/4);}
  if(t.colour_depth==4)return 0xff000000|((raw%256)<<16)|(raw&0xff00)|((raw>>16)&255);
  unsigned bank=t.colour_depth==0?(name/4096+t.supplementary_palette_bits*16)*16:t.colour_depth==1?(name/4096%8)*256:0;
  return s.pal.pen((bank+raw+t.colour_ram_address_offset*256)%2048);
 };
 for(unsigned i=0;i<0x100000;++i)s.m_vdp2_legacy.gfx_decode[i]=(i*37+(i>>8)*13)&255;
 s.pal.indexed=true;unsigned decode_cases=0;
 for(int depth=0;depth<5;++depth)for(int large:{0,1})for(int extended:{0,1})
 for(int flip=0;flip<4;++flip)for(int supplement:{0,3,20,31})for(int vramsz:{0,1})for(int opaque:{0,1})for(unsigned lowname:{0xa135u,0xf3ffu}){
  auto &t=s.current_tilemap;t.colour_depth=depth;t.tile_size=large;t.character_number_supplement=extended;
  t.supplementary_character_bits=supplement;t.supplementary_palette_bits=supplement%8;t.colour_ram_address_offset=7;
  t.transparency=opaque;s.dev.vramsz=vramsz;uint16_t name=lowname|(flip<<10);
  for(int y=-1;y<17;++y)for(int x=-1;x<17;++x)assert(s.vdp2_screen_over_pattern_pixel(name,x,y)==reference(name,x,y));
  ++decode_cases;
 }
 unsigned over_cases=0;
 for(int depth=0;depth<5;++depth)for(int large:{0,1})for(int parameter:{1,2})
 for(int path:{0,1,2})for(int blend:{0,1,2})for(int opaque:{0,1})for(bool window:{false,true})for(int pnb:{0,1})for(bool parameter_window:{false,true}){
  s.current_tilemap={};auto &t=s.current_tilemap;t.tile_size=large;t.colour_depth=depth;t.transparency=opaque;
  t.colour_calculation_enabled=blend!=0;t.alpha=120;t.pattern_data_size=pnb;t.roz_mode3=parameter_window;
  s.regs.VDP2_CCMD=blend==2;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=1;
  s.regs.VDP2_OVPNRA=0xad35;s.regs.VDP2_OVPNRB=0x5937;
  s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;
  s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=0;
  s.regs.VDP2_RAKDBS=s.regs.VDP2_RBKDBS=0;
  s.dev.lsmd=s.dev.hreso=s.dev.vramsz=0;s.window=window;s.blank_coefficient=false;s.coefficient=65536;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;
  r.xst=-8*65536;r.yst=-4*65536;r.dkax=path==2?65536:0;
  bitmap_rgb32 cache(16,16),out(32,24),expected(32,24),split(32,24);
  std::fill(cache.pixels.begin(),cache.pixels.end(),0xffabcdef);
  s.vdp2_copy_roz_bitmap(out,cache,{1,30,1,22},parameter,16,16,16,16);
  s.vdp2_copy_roz_bitmap(split,cache,{1,12,1,22},parameter,16,16,16,16);
  s.vdp2_copy_roz_bitmap(split,cache,{13,30,1,22},parameter,16,16,16,16);
  for(int y=1;y<=22;++y)for(int x=1;x<=30;++x){
   if(!s.vdp2_roz_window(x,y))continue;
   if(parameter_window&&!s.vdp2_roz_mode3_window(x,y,parameter-1))continue;
   int sx=x-8,sy=y-4;bool outside=sx<0||sy<0||sx>=16||sy>=16;
   uint32_t color=outside?reference(parameter==1?0xad35:0x5937,sx,sy):0xffabcdef;
   if(!(color>>24))continue;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(out.pixels==expected.pixels);assert(split.pixels==expected.pixels);++over_cases;
 }
 std::cout<<decode_cases<<" screen-over character decoding configurations and "<<over_cases<<" screen-over rotation images passed\n";

 std::cout<<coverage_cases<<" bitmap-to-rotation opaque-black/transparent coverage images passed\n";
 std::cout<<cases<<" rotation coefficient/window/split-clip images passed\n";
}
'''
code=code.replace('// BITMAP_DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','').strip()+';' for x in bitmap_functions))
code=code.replace('// ROTATION',extract(head,'struct rotation_table {')+' current_rotation_table;')
code=code.replace('// REGS','\n'.join('unsigned '+n+'=0;' for n in names))
code=code.replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-rotation-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-Wno-unused-but-set-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

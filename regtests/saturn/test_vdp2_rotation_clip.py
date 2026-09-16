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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('origin','window','coverage','over','over-name','over-flip','selection','line-color','overflow','viewpoint','per-dot-bank','rotation-mosaic','sprite-window','special-attribute','special-msb','special-code','priority-attribute','priority-match','priority-zero','11bpp','line-wrap','line-mode'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
head=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
bitmap_functions=[extract(src,'void saturn_state::draw_'+name+'_bitmap(') for name in ('4bpp','8bpp','11bpp','rgb15','rgb32')]
over_helpers=[extract(src,sig) for sig in ('void saturn_state::vdp2_compose_pixel(', 'unsigned saturn_state::vdp2_special_priority_mode(', 'rgb_t saturn_state::vdp2_special_priority_pixel(', 'unsigned saturn_state::vdp2_special_color_mode(', 'rgb_t saturn_state::vdp2_special_color_pixel(', 'rgb_t saturn_state::vdp2_line_color(', 'rgb_t saturn_state::vdp2_dot_pixel(', 'rgb_t saturn_state::vdp2_pattern_pixel(', 'rgb_t saturn_state::vdp2_scroll_pixel(')]
over_function='\n'.join(over_helpers)+'\n'+extract(src,'rgb_t saturn_state::vdp2_screen_over_pattern_pixel(')
f=extract(src,'static uint32_t vdp2_gradation_color(')+'\n'+extract(src,'static uint32_t vdp2_extended_color(')+'\n'+extract(src,'static constexpr bool vdp2_per_dot_coefficients(')+'\n'+extract(src,'static inline int32_t vdp2_wrap_sum(')+'\n'+extract(src,'static inline int32_t vdp2_wrap_sub(')+'\n'+extract(src,'static constexpr uint8_t vdp2_cc_blend_level(')+'\n'+over_function+'\n'+'\n'.join(bitmap_functions)+'\n'+extract(src,'static inline uint32_t coef_delta(')+'\n'+extract(src,'void saturn_state::vdp2_copy_roz_bitmap(')
real_windows=[extract(src,sig) for sig in ('inline bool saturn_state::vdp2_roz_window(', 'inline bool saturn_state::vdp2_roz_mode3_window(', 'inline int saturn_state::get_roz_window_pixel(')]
real_windows=[fn.replace('saturn_state::vdp2_roz_window(', 'saturn_state::real_roz_window(').replace('saturn_state::vdp2_roz_mode3_window(', 'saturn_state::real_mode3_window(') for fn in real_windows]
f+='\n'+'\n'.join(real_windows)
if a.mutation=='line-wrap':
 old='(VDP2_LCTA * 2 + index * 2) & mask'
 assert old in f
 f=f.replace(old,'(VDP2_LCTA * 2 + index * 2) & 0xfffff')
if a.mutation=='line-mode':
 assert 'unsigned const index = VDP2_LCCLMD' in f
 f=f.replace('unsigned const index = VDP2_LCCLMD','unsigned const index = true || VDP2_LCCLMD')
if a.mutation=='11bpp':f=f.replace('(current_tilemap.colour_depth == 2 && !current_tilemap.bitmap_enable) ||', '')
if a.mutation=='origin':
 f=f.replace('xs = uint32_t(xs) + uint32_t(int64_t(dxs) * cliprect.left());','(void)0;').replace('ys = uint32_t(ys) + uint32_t(int64_t(dys) * cliprect.left());','(void)0;')
if a.mutation=='window':
 f=f.replace('if (!vdp2_roz_window(hcnt, vcnt))','if (false)').replace('if (current_tilemap.roz_mode3 &&','if (false && current_tilemap.roz_mode3 &&')
if a.mutation=='coverage':f=f.replace('if (pix.a())','if (pix & 0xffffff)')
if a.mutation=='over':f=f.replace('(outside && !repeat_pattern)', 'outside')
if a.mutation=='over-name':f=f.replace('iRP == 1 ? VDP2_OVPNRA : VDP2_OVPNRB','VDP2_OVPNRA')
if a.mutation=='over-flip':f=f.replace('x = ~x','x = x').replace('y = ~y','y = y')
if a.mutation=='selection':f=f.replace('!selected(hcnt, vcnt)', '(selected(hcnt, vcnt), false)')
if a.mutation=='line-color':f=f.replace('color = (color & 0x780) | (coefficient_color & 0x7f);', 'color = (color & 0x780) | (coefficient_color & 0);')
if a.mutation=='overflow':f=f.replace('return uint32_t(a) + uint32_t(b) + uint32_t(c) + uint32_t(d) + uint32_t(e);','return a + b + c + d + e;')
if a.mutation=='viewpoint':f=f.replace('xp = uint32_t(coeff_table_val) << 8;', 'xp = coeff_table_val;')
if a.mutation=='per-dot-bank':f=f.replace('bool const per_dot_coefficients = vdp2_per_dot_coefficients(VDP2_RAMCTL);', 'bool const per_dot_coefficients = (vdp2_per_dot_coefficients(VDP2_RAMCTL), true);')
if a.mutation=='rotation-mosaic':f=f.replace('return x - x % mosaic_width;', 'return x - (x % mosaic_width) * 0;')
if a.mutation=='sprite-window':f=f.replace('vdp2_sprite_window(x, y)', 'false')
if a.mutation=='special-attribute':f=f.replace('bool(current_tilemap.special_colour_control_register)', 'true')
if a.mutation=='special-msb':f=f.replace('calculate = (m_vdp2_cram[pen >> 1] >> ((pen & 1) ? 15 : 31)) & 1;', 'calculate = true;')
if a.mutation=='special-code':f=f.replace('VDP2_SFCODE >> (((VDP2_SFSEL >> layer) & 1) * 8)', 'VDP2_SFCODE >> ((VDP2_SFSEL & layer) * 0)')
if a.mutation=='priority-attribute':f=f.replace('bool(current_tilemap.special_priority_register)', 'false')
if a.mutation=='priority-match':f=f.replace('(pixel.a() & 2)', '(pixel.a() | 2)')
if a.mutation=='priority-zero':f=f.replace('if (!priority)', 'if (false && !priority)')
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
 bool m_vdp2_composition_active=false;
 bitmap_rgb32 m_vdp2_raw_top{16,8},m_vdp2_raw_under{16,8};
 struct {uint8_t data[16*8]{};uint8_t &pix(int y,int x){assert(x>=0&&x<16&&y>=0&&y<8);return data[y*16+x];}} m_vdp2_raw_alpha,m_vdp2_raw_meta,m_vdp2_under_meta;
 bool vdp2_calculation_window(int,int){return true;}
 bool m_vdp2_extended_active=false;bool m_vdp2_gradation_active=false,m_vdp2_gradation_capture=false;unsigned m_vdp2_gradation_layer=7;bitmap_rgb32 m_vdp2_gradation_source{16,8};

 void vdp2_compose_pixel(bitmap_rgb32&,int,int,rgb_t,bool,unsigned,bool,rgb_t,unsigned);
 int m_vdp2_priority_pass=-1;
 uint32_t m_vdp2_cram[1024]{};
 uint32_t vdp2_cram_r(unsigned i){return m_vdp2_cram[i];}
 unsigned vdp2_special_priority_mode() const;
 rgb_t vdp2_special_priority_pixel(rgb_t,bool);
 unsigned vdp2_special_color_mode() const;
 rgb_t vdp2_special_color_pixel(rgb_t,unsigned,unsigned);
 rgb_t vdp2_scroll_pixel(int32_t,int32_t);
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 rgb_t vdp2_line_color(int,bool,uint8_t);
 rgb_t vdp2_dot_pixel(uint32_t,int,unsigned);
 rgb_t vdp2_pattern_pixel(uint32_t,bool,int,int);
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
 int layer_name=0,line_screen_enabled=0,mosaic_screen_enabled=0;
 int map_count=4,plane_size=0,special_priority_register=0,special_colour_control_register=0;unsigned map_offset[16]{};
 int scrollx_fraction=0,scrolly_fraction=0;
 int pattern_data_size=0,bitmap_enable=0,tile_size=0,colour_depth=0,character_number_supplement=0,supplementary_character_bits=0,supplementary_palette_bits=0;
 int incx=65536,incy=65536,scrollx=0,scrolly=0,bitmap_map=0,bitmap_size=0;
 int linescroll_enable=0,vertical_linescroll_enable=0,bitmap_palette_number=0,colour_ram_address_offset=0;
 bool roz_mode3=false;} current_tilemap;
 rotation_table parameter_a;
 void vdp2_load_rotation_line(uint8_t p,int){assert(p==1);current_rotation_table=parameter_a;}
 device dev;device *m_vdp2=&dev;
 bool real_windows=false;
 int m_roz_win_s_x[2]{3,7},m_roz_win_e_x[2]{11,14},m_roz_win_s_y[2]{2,1},m_roz_win_e_y[2]{5,4};
 void vdp2_roz_window_prepare(int){}
 bool vdp2_sprite_window(int x,int y){return (x+2*y)%3==0;}
 // REAL_WINDOWS
 bool window=false;unsigned coefficient=65536;bool blank_coefficient=false;
 std::vector<uint32_t> b_reads;
 unsigned coefficient_reads=0;
 bool selection_test=false,selection_short=false,line_color_test=false,line_color_short=false,line_color_switch=false;
 uint32_t vdp2_read_rotation_coefficient(uint32_t address){
  ++coefficient_reads;
  if(line_color_test){
   if(line_color_short)return 0x04000400;
   bool a=address<0x40000;unsigned index=(address-(a?0:0x40000))/4;
   return 65536|(((a?0x10:0x40)+index)%128<<24)|((a&&line_color_switch&&index%3==1)?0x80000000:0);
  }
  if(!selection_test)return coefficient|(blank_coefficient?0x80000000:0);
  if(address>=0x40000){b_reads.push_back(address);return 65536|(blank_coefficient?0x80000000:0);}
  auto value=[](unsigned i){return (i%3==1)?0x80000000u:0u;};
  if(selection_short){unsigned i=(address&~3u)/2;return ((1024|(value(i)>>16))<<16)|(1024|(value(i+1)>>16));}
  return 65536|value(address/4);
 }
 bool vdp2_roz_window(int x,int y){if(real_windows)return real_roz_window(x,y);return !window||(x>=3&&x<=11&&y>=2&&y<=5);}
 bool vdp2_roz_mode3_window(int x,int y,int parameter){if(real_windows)return real_mode3_window(x,y,parameter);return ((x+y)&1)==parameter;}
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
 unsigned cases=0;s.regs.VDP2_RAMCTL=0x355;
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
  s.coefficient=coeff_mode==3?2*256:65536;
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
   uint32_t color=outside?reference(parameter==1?0xad35:0x5937,sx,sy):(depth==2?reference(0,sx,sy):0xffabcdef);
   if(!(color>>24))continue;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(out.pixels==expected.pixels);assert(split.pixels==expected.pixels);++over_cases;
 }
 std::cout<<decode_cases<<" screen-over character decoding configurations and "<<over_cases<<" screen-over rotation images passed\n";


 unsigned selection_cases=0;s.selection_test=true;s.window=false;s.dev.lsmd=s.dev.hreso=0;
 for(bool short_a:{false,true})for(int path:{0,1,2})for(int blend:{0,1,2})
 for(bool absent_a:{false,true})for(bool absent_b:{false,true})for(bool b_transparent:{false,true}){
  s.selection_short=short_a;s.blank_coefficient=b_transparent;s.regs.VDP2_RPMD=2;
  s.regs.VDP2_RAKTE=path!=0;s.regs.VDP2_RBKTE=1;
  s.regs.VDP2_RAKDBS=short_a;s.regs.VDP2_RBKDBS=0;
  s.regs.VDP2_RAKTAOS=0;s.regs.VDP2_RBKTAOS=1;
  s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=0;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;
  s.regs.VDP2_CCMD=blend==2;
  s.current_tilemap={};s.current_tilemap.transparency=0;s.current_tilemap.alpha=120;
  s.current_tilemap.colour_calculation_enabled=blend!=0;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;
  r.dkast=65536;r.dkax=path==2?65536:0;s.parameter_a=r;
  bitmap_rgb32 cache_a(16,16),cache_b(16,16),out(16,8),expected(16,8);
  std::fill(cache_a.pixels.begin(),cache_a.pixels.end(),absent_a?0:0xff800000);
  std::fill(cache_b.pixels.begin(),cache_b.pixels.end(),absent_b?0:0xff008000);
  s.b_reads.clear();
  s.vdp2_copy_roz_bitmap(out,cache_b,{1,14,1,6},2,16,16,16,16);
  assert(s.b_reads.size()==6);
  for(unsigned i=0;i<6;++i)assert(s.b_reads[i]==0x40000+(i+1)*4);
  r=s.parameter_a;s.vdp2_copy_roz_bitmap(out,cache_a,{1,14,1,6},1,16,16,16,16);
  for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
   bool b=path!=0&&((y+(path==2?x:0))%3==1);
   if(b?(absent_b||b_transparent):absent_a)continue;
   uint32_t color=b?0xff008000:0xff800000;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(out.pixels==expected.pixels);++selection_cases;
 }
 std::cout<<selection_cases<<" A/B selection-before-composition images passed\n";

 unsigned boundary_cases=0;s.selection_test=false;s.window=false;s.blank_coefficient=false;
 s.regs.VDP2_RAKTAOS=s.regs.VDP2_RBKTAOS=0;s.dev.lsmd=s.dev.hreso=0;
 for(int mode:{0,2,3})for(int origin:{-2,510,1022})for(int parameter:{1,2})
 for(int path:{0,1,2})for(bool short_data:{false,true})for(int sign:{-1,1})for(int blend:{0,1,2}){
  s.regs.VDP2_RPMD=parameter-1;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=mode;
  s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;
  s.regs.VDP2_RAKDBS=s.regs.VDP2_RBKDBS=short_data;
  s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=0;s.regs.VDP2_CCMD=blend==2;
  s.coefficient=short_data?(sign<0?0x7c007c00:0x04000400):(sign<0?0x00ff0000:0x00010000);
  s.current_tilemap={};s.current_tilemap.colour_calculation_enabled=blend!=0;s.current_tilemap.alpha=120;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;
  r.mx=r.my=origin*65536;r.dkax=path==2?65536:0;
  bitmap_rgb32 cache(64,64),out(16,8),expected(16,8),split(16,8);
  std::fill(cache.pixels.begin(),cache.pixels.end(),0xffabcdef);
  s.vdp2_copy_roz_bitmap(out,cache,{1,14,1,6},parameter,1024,512,64,64);
  s.vdp2_copy_roz_bitmap(split,cache,{1,6,1,6},parameter,1024,512,64,64);
  s.vdp2_copy_roz_bitmap(split,cache,{7,14,1,6},parameter,1024,512,64,64);
  for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
   int sx=origin+x*(path?sign:1),sy=origin+y*(path?sign:1);
   bool visible=mode==0||(sx>=0&&sy>=0&&sx<(mode==3?512:1024)&&sy<512);
   if(!visible)continue;
   uint32_t color=0xffabcdef;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(out.pixels==expected.pixels);assert(split.pixels==expected.pixels);++boundary_cases;
 }
 std::cout<<boundary_cases<<" short/long signed-coefficient and screen-over boundary images passed\n";


 // Independent wide-integer oracle with explicit modulo-2^32 stages. Exercise
 // legal signed field limits, not just the small transforms used above.
 unsigned overflow_cases=0;s.selection_test=false;s.window=false;s.blank_coefficient=false;s.dev.hreso=s.dev.lsmd=0;
 s.current_tilemap={};s.regs.VDP2_RPMD=0;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;
 auto wrap=[](int64_t n)->int64_t{uint64_t u=uint64_t(n)&0xffffffff;return u>=0x80000000?int64_t(u)-0x100000000:int64_t(u);};
 auto mul=[&](int64_t a,int64_t b){return wrap((a*b)>>16);};
 uint32_t random=0x582931cd;
 auto field=[&](unsigned bits,unsigned low)->int32_t{random=random*1664525+1013904223;uint32_t n=random&((1u<<bits)-1)&~((1u<<low)-1);return (n&(1u<<(bits-1)))?int64_t(n)-(int64_t(1)<<bits):n;};
 for(int trial=0;trial<32;++trial)for(int parameter:{1,2})for(int path:{0,1,2})for(bool short_data:{false,true})for(int mode=0;mode<4;++mode){
  s.regs.VDP2_RPMD=parameter-1;s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;
  s.regs.VDP2_RAKDBS=s.regs.VDP2_RBKDBS=short_data;s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=mode;
  s.coefficient=short_data?0x7fc07fc0:0x00fff000;
  auto &r=s.current_rotation_table;r={};
  r.xst=field(29,6);r.yst=field(29,6);r.zst=field(29,6);r.dxst=field(19,6);r.dyst=field(19,6);r.dx=field(19,6);r.dy=field(19,6);
  r.A=field(20,6);r.B=field(20,6);r.C=field(20,6);r.D=field(20,6);r.E=field(20,6);r.F=field(20,6);
  r.px=field(14,0)*65536;r.py=field(14,0)*65536;r.pz=field(14,0)*65536;
  r.cx=field(14,0)*65536;r.cy=field(14,0)*65536;r.cz=field(14,0)*65536;
  r.mx=field(30,6);r.my=field(30,6);r.kx=field(24,0);r.ky=field(24,0);r.dkax=path==2?65536:0;
  bitmap_rgb32 source(64,64),out(16,8),expected(16,8);
  for(int y=0;y<64;++y)for(int x=0;x<64;++x)source.pix(y,x)=0xff800000|(y<<8)|x;
  s.vdp2_copy_roz_bitmap(out,source,{1,14,1,6},parameter,64,64,64,64);
  int64_t dx=wrap(mul(r.A,r.dx)+mul(r.B,r.dy)),dy=wrap(mul(r.D,r.dx)+mul(r.E,r.dy));
  int64_t xp=wrap(mul(r.A,wrap(int64_t(r.px)-r.cx))+mul(r.B,wrap(int64_t(r.py)-r.cy))+mul(r.C,wrap(int64_t(r.pz)-r.cz))+r.cx+r.mx);
  int64_t yp=wrap(mul(r.D,wrap(int64_t(r.px)-r.cx))+mul(r.E,wrap(int64_t(r.py)-r.cy))+mul(r.F,wrap(int64_t(r.pz)-r.cz))+r.cy+r.my);
  int64_t kx=path&&(mode==0||mode==1)?-4096:r.kx,ky=path&&(mode==0||mode==2)?-4096:r.ky;
  if(path&&mode==3)xp=-1048576;
  for(int y=1;y<=6;++y){
   int64_t sx=wrap(wrap(r.xst+mul(r.dxst,y*65536))-r.px),sy=wrap(wrap(r.yst+mul(r.dyst,y*65536))-r.py);
   int64_t xsp=wrap(mul(r.A,sx)+mul(r.B,sy)+mul(r.C,wrap(int64_t(r.zst)-r.pz)));
   int64_t ysp=wrap(mul(r.D,sx)+mul(r.E,sy)+mul(r.F,wrap(int64_t(r.zst)-r.pz)));
   for(int x=1;x<=14;++x){
    int64_t tx=path==2?wrap(mul(kx,wrap(xsp+mul(dx,x*65536)))+xp):wrap(wrap(mul(kx,xsp)+xp)+x*mul(kx,dx));
    int64_t ty=path==2?wrap(mul(ky,wrap(ysp+mul(dy,x*65536)))+yp):wrap(wrap(mul(ky,ysp)+yp)+x*mul(ky,dy));
    expected.pix(y,x)=source.pix((ty>>16)&63,(tx>>16)&63);
   }
  }
  assert(out.pixels==expected.pixels);++overflow_cases;
 }
 std::cout<<overflow_cases<<" signed-limit wrapping-coordinate images passed\n";

 unsigned mosaic_cases=0;s.line_color_test=true;s.line_color_short=false;s.selection_test=false;s.blank_coefficient=false;
 s.regs.VDP2_RAMCTL=0x355;s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=0;
 s.regs.VDP2_RAKDBS=s.regs.VDP2_RBKDBS=0;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;
 s.regs.VDP2_RAKTAOS=0;s.regs.VDP2_RBKTAOS=1;
 for(int mode=0;mode<4;++mode)for(bool rbg1:{false,true})for(int path:{0,1,2})for(int width=1;width<=16;++width)
 for(int blend:{0,1,2})for(bool hires:{false,true})for(bool interlace:{false,true})for(bool window:{false,true}){
  if(rbg1&&mode!=0)continue;
  s.regs.VDP2_RPMD=mode;s.regs.VDP2_R1ON=rbg1;s.line_color_switch=mode==2;
  s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;s.regs.VDP2_MZSZH=width-1;s.regs.VDP2_CCMD=blend==2;
  s.dev.hreso=hires?2:0;s.dev.lsmd=interlace?3:0;s.window=window;
  s.current_tilemap={};s.current_tilemap.mosaic_screen_enabled=1;s.current_tilemap.roz_mode3=mode==3;
  s.current_tilemap.colour_calculation_enabled=blend!=0;s.current_tilemap.alpha=120;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;r.xst=3*65536;r.yst=2*65536;r.dkast=65536;r.dkax=path==2?65536:0;s.parameter_a=r;
  bitmap_rgb32 ca(64,64),cb(64,64),out(24,8),split(24,8),expected(24,8);
  for(int y=0;y<64;++y)for(int x=0;x<64;++x){bool covered=(x+2*y)%5!=0;ca.pix(y,x)=covered?(0xff400000|(y<<8)|x):0;cb.pix(y,x)=covered?(0xff004000|(y<<8)|x):0;}
  for(int y=0;y<8;++y)for(int x=0;x<24;++x)out.pix(y,x)=split.pix(y,x)=expected.pix(y,x)=0x123456+x*37+y*53;
  auto render=[&](bitmap_rgb32 &dest,rectangle clip){
   if(rbg1||mode!=0){r=s.parameter_a;s.vdp2_copy_roz_bitmap(dest,cb,clip,2,64,64,64,64);}
   if(!rbg1&&mode!=1){r=s.parameter_a;s.vdp2_copy_roz_bitmap(dest,ca,clip,1,64,64,64,64);}
  };
  s.coefficient_reads=0;render(out,{1,22,1,6});assert(s.coefficient_reads<=18u*(22/(width*(hires?2:1))+1));render(split,{1,7,1,6});render(split,{8,22,1,3});render(split,{8,22,4,6});
  for(int y=1;y<=6;++y)for(int x=1;x<=22;++x){
   if(window&&!(x>=3&&x<=11&&y>=2&&y<=5))continue;
   int anchor=x/(width*(hires?2:1))*(width*(hires?2:1));
   int sx=3+anchor/(hires?2:1),sy=2+y/(interlace?2:1);
   bool b=rbg1||mode==1||(mode==2&&path&&((y/(interlace?2:1)+(path==2?anchor:0))%3==1))||(mode==3&&((anchor+y)&1));
   uint32_t color=b?cb.pix(sy,sx):ca.pix(sy,sx);if(!color)continue;
   uint32_t back=expected.pix(y,x);expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(back,color,120):add_blend_r32(back,color);
  }
  assert(out.pixels==expected.pixels);assert(split.pixels==expected.pixels);++mosaic_cases;
 }
 std::cout<<mosaic_cases<<" horizontal rotation mosaic images and split clips passed\n";
 unsigned line_color_cases=0;s.line_color_test=true;s.selection_test=false;s.window=false;s.blank_coefficient=false;s.dev.vramsz=0;
 s.regs.VDP2_RAKMD=s.regs.VDP2_RBKMD=0;s.regs.VDP2_LCTA=0x3ffff;s.pal.indexed=true;
 for(unsigned n=0;n<16;++n){unsigned address=(0x7fffe + n*2)&0x7ffff;uint16_t value=0x522+n*3;s.m_vdp2_legacy.gfx_decode[address]=value>>8;s.m_vdp2_legacy.gfx_decode[(address+1)&0x7ffff]=value;}
 for(int mode=0;mode<4;++mode)for(bool rbg1:{false,true})for(int path:{0,1,2})for(bool short_data:{false,true})
 for(int klce=0;klce<4;++klce)for(bool lncl:{false,true})for(bool per_line:{false,true})for(int lsmd:{0,2,3})for(bool add:{false,true})for(bool second_ratio:{false,true})for(bool banks:{false,true})for(int mosaic:{0,3,15}){
  if(rbg1&&mode!=0)continue; // RBG1 requires RPMD 0
  s.regs.VDP2_RAMCTL=banks?0x355:0;s.dev.lsmd=lsmd;s.dev.hreso=0;s.line_color_short=short_data;s.line_color_switch=mode==2;
  s.regs.VDP2_RPMD=mode;s.regs.VDP2_R1ON=rbg1;s.regs.VDP2_CCMD=add;s.regs.VDP2_CCCR=second_ratio?0x200:0;s.regs.VDP2_CCRLB=19;
  s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=path!=0;s.regs.VDP2_RAKDBS=s.regs.VDP2_RBKDBS=short_data;
  s.regs.VDP2_RAKLCE=klce&1;s.regs.VDP2_RBKLCE=(klce>>1)&1;s.regs.VDP2_LCCLMD=per_line;
  s.regs.VDP2_RAKTAOS=0;s.regs.VDP2_RBKTAOS=1;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;
  s.regs.VDP2_MZSZH=mosaic;s.current_tilemap={};s.current_tilemap.mosaic_screen_enabled=mosaic!=0;s.current_tilemap.line_screen_enabled=lncl;s.current_tilemap.colour_calculation_enabled=1;s.current_tilemap.alpha=120;s.current_tilemap.roz_mode3=mode==3;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;r.dkast=65536;r.dkax=path==2?65536:0;s.parameter_a=r;
  bitmap_rgb32 ca(16,16),cb(16,16),out(16,8),expected(16,8);std::fill(ca.pixels.begin(),ca.pixels.end(),0xff800000);std::fill(cb.pixels.begin(),cb.pixels.end(),0xff008000);
  if(rbg1||mode!=0)s.vdp2_copy_roz_bitmap(out,cb,{1,14,1,6},2,16,16,16,16);
  if(!rbg1&&mode!=1){r=s.parameter_a;s.vdp2_copy_roz_bitmap(out,ca,{1,14,1,6},1,16,16,16,16);}
  for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
   unsigned anchor=x/(mosaic+1)*(mosaic+1);
   unsigned a_index=(y>>(lsmd==3))+(path==2&&banks?anchor:0);
   bool b=rbg1||mode==1||(mode==2&&path&&!short_data&&a_index%3==1)||(mode==3&&((anchor+y)&1));
   bool coefficient_a=rbg1||mode==2||!b;
   unsigned line_index=per_line?(lsmd==2?y/2:y):(lsmd==3?y%2:0);
   unsigned pen=0x522+line_index*3;
   if(path&&!short_data&&(klce&(coefficient_a?1:2))){
    unsigned index=coefficient_a?a_index:(y>>(lsmd==3))+(path==2&&banks?anchor:0);
    pen=(pen/128)*128+((coefficient_a?0x10:0x40)+index)%128;
   }
   uint32_t second=lncl?s.pal.pen(pen):0x123456,first=b?0xff008000:0xff800000;
   unsigned alpha=lncl&&second_ratio?96:120;
   expected.pix(y,x)=add?add_blend_r32(second,first):alpha_blend_r32(second,first,alpha);
  }
  assert(out.pixels==expected.pixels);++line_color_cases;
 }
 std::cout<<line_color_cases<<" coefficient line-color source/insertion/ratio images passed\n";

 unsigned real_window_cases=0;s.real_windows=true;s.line_color_test=s.selection_test=s.blank_coefficient=false;
 s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=0;s.dev.hreso=s.dev.lsmd=0;
 auto keep=[](unsigned cfg,int x,int y){
  bool inside[]={x>=3&&x<=11&&y>=2&&y<=5,x>=7&&x<=14&&y>=1&&y<=4,(x+2*y)%3==0};
  bool value=!(cfg&16);for(int w=0;w<3;++w){unsigned en=w==2?32:1u<<w,area=w==2?64:4u<<w;if(cfg&en){bool k=bool(cfg&area)==inside[w];value=(cfg&16)?value||k:value&&k;}}return value;
 };
 for(unsigned cfg=0;cfg<128;++cfg)for(unsigned select=0;select<128;++select)for(bool transform:{false,true})for(bool rbg1:{false,true}){
  // RBG1 has no parameter window: sample that case once per output configuration.
  if(rbg1&&select)continue;
  s.regs.VDP2_RPMD=rbg1?0:3;s.regs.VDP2_R1ON=rbg1;
  s.regs.VDP2_RPW0E=select&1;s.regs.VDP2_RPW1E=(select>>1)&1;s.regs.VDP2_RPW0A=(select>>2)&1;s.regs.VDP2_RPW1A=(select>>3)&1;s.regs.VDP2_RPLOG=(select>>4)&1;s.regs.VDP2_RPSWE=(select>>5)&1;s.regs.VDP2_RPSWA=(select>>6)&1;
  s.regs.VDP2_R0W0E=s.regs.VDP2_N0W0E=cfg&1;s.regs.VDP2_R0W1E=s.regs.VDP2_N0W1E=(cfg>>1)&1;
  s.regs.VDP2_R0W0A=s.regs.VDP2_N0W0A=(cfg>>2)&1;s.regs.VDP2_R0W1A=s.regs.VDP2_N0W1A=(cfg>>3)&1;
  s.regs.VDP2_R0LOG=s.regs.VDP2_N0LOG=(cfg>>4)&1;s.regs.VDP2_R0SWE=s.regs.VDP2_N0SWE=(cfg>>5)&1;s.regs.VDP2_R0SWA=s.regs.VDP2_N0SWA=(cfg>>6)&1;
  int blend=(cfg+select)%3,mosaic=select%3==0?3:1;s.regs.VDP2_CCMD=blend==2;s.regs.VDP2_MZSZH=mosaic-1;
  s.current_tilemap={};s.current_tilemap.layer_name=rbg1?0x81:0x80;s.current_tilemap.roz_mode3=!rbg1;s.current_tilemap.mosaic_screen_enabled=mosaic>1;s.current_tilemap.colour_calculation_enabled=blend!=0;s.current_tilemap.alpha=120;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dyst=r.kx=r.ky=65536;r.dx=transform?131072:65536;r.xst=transform?3*65536:0;r.yst=transform?2*65536:0;s.parameter_a=r;
  bitmap_rgb32 ca(64,64),cb(64,64),out(16,8),split(16,8),expected(16,8);
  for(int y=0;y<64;++y)for(int x=0;x<64;++x){ca.pix(y,x)=(x+y)%5?0xff400000|(y<<8)|x:0;cb.pix(y,x)=(x+y)%5?0xff004000|(y<<8)|x:0;}
  auto render=[&](bitmap_rgb32 &dest,rectangle clip){r=s.parameter_a;s.vdp2_copy_roz_bitmap(dest,cb,clip,2,64,64,64,64);if(!rbg1){r=s.parameter_a;s.vdp2_copy_roz_bitmap(dest,ca,clip,1,64,64,64,64);}};
  render(out,{1,14,1,6});render(split,{1,6,1,6});render(split,{7,14,1,6});
  for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
   if(!keep(cfg,x,y))continue;
   int anchor=x/mosaic*mosaic,sx=(transform?3+anchor*2:anchor),sy=(transform?2:0)+y;
   bool b=rbg1||!keep(select,anchor,y);uint32_t color=b?cb.pix(sy,sx):ca.pix(sy,sx);if(!color)continue;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(out.pixels==expected.pixels);assert(split.pixels==expected.pixels);++real_window_cases;
 }
 std::cout<<real_window_cases<<" production rotation/window composition images passed\n";

 unsigned special_cases=0;s.real_windows=s.line_color_test=s.selection_test=s.blank_coefficient=s.window=false;
 s.dev.hreso=s.dev.lsmd=0;s.dev.vramsz=1;s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=0;s.regs.VDP2_CRMD=1;s.pal.indexed=true;
 for(unsigned i=0;i<1024;++i)s.m_vdp2_cram[i]=(i%2?0x80000000:0)|(i%3?0:0x8000);
 for(unsigned depth=0;depth<5;++depth)for(bool one:{false,true})for(bool large:{false,true}){
  unsigned bpd=depth==0?4:depth==1?8:depth==4?32:16;
  unsigned entries=(large?32:64)*(large?32:64),page_bytes=entries*(one?2:4);
  for(unsigned plane=0;plane<16;++plane){
   unsigned code=0x6000+plane*32,name=one?(plane*32>>(large?2:0)):code|((plane&1)<<28)|(((plane>>1)&1)<<29);
   for(unsigned n=0;n<entries;++n){unsigned a=plane*page_bytes+n*(one?2:4);if(one){auto &word=s.m_vdp2_vram[a/4];if(a%4)word=(word&0xffff0000)|name;else word=(word&65535)|(name<<16);}else s.m_vdp2_vram[a/4]=name;}
   for(unsigned dot=0;dot<(large?256u:64u);++dot){
    unsigned raw=((dot%8)+((dot/8)%8)*3+plane)%16,value=depth<3?raw:depth==3?0x8000|raw:0x80000000|raw;
    unsigned address=code*32+dot*bpd/8;auto *mem=s.m_vdp2_legacy.gfx_decode.get();
    if(depth==0){if(dot%2)mem[address]=(mem[address]&0xf0)|value;else mem[address]=value<<4;}
    else for(unsigned j=0;j<bpd/8;++j)mem[address+j]=value>>((bpd/8-j-1)*8);
   }
  }

  for(unsigned y=0;y<256;++y)for(unsigned x=0;x<512;++x){
   unsigned raw=((x%8)+(y%8)*3)%16,value=depth<3?raw:depth==3?0x8000|raw:0x80000000|raw;
   unsigned dot=y*512+x,address=dot*bpd/8;auto *mem=s.m_vdp2_legacy.gfx_decode.get();
   if(depth==0){if(dot%2)mem[address]=(mem[address]&0xf0)|value;else mem[address]=value<<4;}
   else for(unsigned j=0;j<bpd/8;++j)mem[address+j]=value>>((bpd/8-j-1)*8);
  }
  for(unsigned mode=1;mode<4;++mode)for(bool attribute:{false,true})for(unsigned plane=0;plane<16;++plane)
  for(bool rbg1:{false,true})for(bool over:{false,true})for(bool additive:{false,true})for(bool opaque:{false,true})for(bool bitmap:{false,true})for(unsigned priority_mode=0;priority_mode<3;++priority_mode){
   if(((mode==2||priority_mode==2)&&depth>=3)||(bitmap&&over))continue;
   unsigned base_priority=plane%8;s.m_vdp2_priority_pass=(base_priority&6)+(plane%2);
   s.regs.VDP2_SFPRMD=priority_mode<<(rbg1?0:8);s.regs.VDP2_N0PRIN=rbg1?base_priority:(base_priority^6);s.regs.VDP2_R0PRIN=rbg1?(base_priority^6):base_priority;
   s.regs.VDP2_SFCCMD=rbg1?mode|(((mode+1)%4)<<8):(mode<<8)|((mode+1)%4);
   s.regs.VDP2_BMPNB=(rbg1?!attribute:attribute)*16+(rbg1?attribute:!attribute)*32;s.regs.VDP2_BMPNA=(rbg1?attribute:!attribute)*16+(rbg1?!attribute:attribute)*32;
   s.regs.VDP2_SFCODE=0xa55a;s.regs.VDP2_SFSEL=attribute?31:0;
   s.regs.VDP2_RPMD=0;s.regs.VDP2_R1ON=rbg1;s.regs.VDP2_CCMD=additive;s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=over?1:0;s.regs.VDP2_OVPNRA=s.regs.VDP2_OVPNRB=0;
   s.current_tilemap={};auto &t=s.current_tilemap;t.layer_name=rbg1?0x81:0x80;t.map_count=16;t.bitmap_enable=bitmap;t.pattern_data_size=one;t.tile_size=large;t.colour_depth=depth;t.special_priority_register=!attribute;t.special_colour_control_register=attribute;t.supplementary_character_bits=24;t.transparency=opaque;t.colour_calculation_enabled=1;t.alpha=120;
   for(unsigned n=0;n<16;++n)t.map_offset[n]=n;
   auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;r.xst=(over?-13:int(plane%4)*512+3)*65536;r.yst=(over?2:int(plane/4)*512+2)*65536;
   bitmap_rgb32 unused(1,1),out(16,8),split(16,8),expected(16,8);
   s.vdp2_copy_roz_bitmap(out,unused,{1,14,1,6},rbg1?2:1,bitmap?512:2048,bitmap?256:2048,bitmap?512:2048,bitmap?256:2048);
   s.vdp2_copy_roz_bitmap(split,unused,{1,7,1,6},rbg1?2:1,bitmap?512:2048,bitmap?256:2048,bitmap?512:2048,bitmap?256:2048);s.vdp2_copy_roz_bitmap(split,unused,{8,14,1,6},rbg1?2:1,bitmap?512:2048,bitmap?256:2048,bitmap?512:2048,bitmap?256:2048);
   for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){
    int sx=(over?-13:int(plane%4)*512+3)+x,sy=(over?2:int(plane/4)*512+2)+y;bool outside=sx<0;
    unsigned p=over||bitmap?0:plane,raw=((unsigned(sx)%8)+(unsigned(sy)%8)*3+p)%16;
    if(depth<3&&!raw&&!opaque)continue;
    bool attr=bitmap||outside||one?attribute:bool(p&1);
    bool eligible=mode==1?attr:mode==2?attr&&((0xa55a>>((attribute?8:0)+raw/2))&1):depth>=3||((s.m_vdp2_cram[raw/2]>>(raw%2?15:31))&1);
    bool priority_attribute=bitmap||outside||one?!attribute:bool(p&2);
    bool match=(0xa55a>>((attribute?8:0)+raw/2))&1;
    unsigned priority=(base_priority&6)|unsigned(priority_attribute&&(priority_mode==1||match));
    if(priority_mode&&(!priority||priority!=unsigned(s.m_vdp2_priority_pass)))continue;
    uint32_t color=depth<3?s.pal.pen(raw):depth==3?uint32_t(rgb_t(pal5bit(raw),0,0)):uint32_t(rgb_t(raw,0,0));
    expected.pix(y,x)=!eligible?color:additive?add_blend_r32(0x123456,color):alpha_blend_r32(0x123456,color,120);
   }
   assert(out.pixels==expected.pixels);assert(split.pixels==expected.pixels);++special_cases;
  }
 }
 std::cout<<special_cases<<" rotation/map/screen-over special-calculation images passed\n";

 s.regs.VDP2_SFPRMD=s.regs.VDP2_SFCCMD=0;s.m_vdp2_priority_pass=-1;s.real_windows=s.window=false;
 s.regs.VDP2_RAKTE=s.regs.VDP2_RBKTE=s.regs.VDP2_RAOVR=s.regs.VDP2_RBOVR=0;s.dev.hreso=s.dev.lsmd=0;
 for(int parameter:{1,2})for(bool enabled:{false,true})for(bool second:{false,true})for(bool add:{false,true}){
  s.m_vdp2_composition_active=true;s.regs.VDP2_RPMD=parameter-1;s.regs.VDP2_CCCR=second?0x200:0;s.regs.VDP2_CCMD=add;
  s.current_tilemap={};s.current_tilemap.colour_calculation_enabled=enabled;s.current_tilemap.alpha=120;
  auto &r=s.current_rotation_table;r={};r.A=r.E=r.dx=r.dyst=r.kx=r.ky=65536;
  bitmap_rgb32 cache(16,16),out(16,8),expected(16,8);
  for(int y=0;y<16;++y)for(int x=0;x<16;++x)cache.pix(y,x)=(x+y)%5?0xff102030+x*59+y*31:0;
  std::fill(s.m_vdp2_raw_top.pixels.begin(),s.m_vdp2_raw_top.pixels.end(),0x812b47);std::fill_n(s.m_vdp2_raw_alpha.data,128,96);
  s.vdp2_copy_roz_bitmap(out,cache,{1,14,1,6},parameter,16,16,16,16);
  for(int y=1;y<=6;++y)for(int x=1;x<=14;++x){uint32_t color=cache.pix(y,x);if(!color)continue;
   expected.pix(y,x)=!enabled?color:add?add_blend_r32(0x812b47,color):alpha_blend_r32(0x812b47,color,second?96:120);
   assert(s.m_vdp2_raw_top.pix(y,x)==color&&s.m_vdp2_raw_alpha.pix(y,x)==120);
  }
  assert(out.pixels==expected.pixels);
 }
 std::cout<<"16 active raw-second-image rotation integration cases passed\n";
 std::cout<<coverage_cases<<" bitmap-to-rotation opaque-black/transparent coverage images passed\n";
 std::cout<<cases<<" rotation coefficient/window/split-clip images passed\n";
}
'''
code=code.replace('// REAL_WINDOWS','\n'.join(fn[:fn.index('{')].replace('saturn_state::','')+';' for fn in real_windows))
code=code.replace('// BITMAP_DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','').strip()+';' for x in bitmap_functions))
code=code.replace('// ROTATION',extract(head,'struct rotation_table {')+' current_rotation_table;')
code=code.replace('// REGS','\n'.join('unsigned '+n+'=0;' for n in names))
code=code.replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-rotation-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-Wno-unused-but-set-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

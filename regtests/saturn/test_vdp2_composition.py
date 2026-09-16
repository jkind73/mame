#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production raw-second-image composition, ratios, line insertion and shadow updates.

Uses actual MAME RGB blend primitives and an independent /32 component oracle.
Sources/coverage/priority order are controlled inputs, including capture dispatch;
this is not a game replay or a hardware oracle.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation', choices=('cumulative', 'ratio', 'line-history', 'disabled-ratio', 'shadow', 'extended', 'format', 'gradation', 'halo', 'offset', 'shadow-layer'))
a = p.parse_args()
src = (ROOT / 'src/mame/sega/saturn.cpp').read_text()
blend = (ROOT / 'src/emu/drawgfx.h').read_text()


def extract(text, sig):
    start = text.index(sig)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


funcs = [extract(src, sig) for sig in (
    'void saturn_state::vdp2_compute_color_offset_UINT32(',
    'void saturn_state::vdp2_capture_gradation(',
    'void saturn_state::vdp2_begin_composition(',
    'void saturn_state::vdp2_compose_pixel(',
    'void saturn_state::vdp2_shadow_pixel(')]
functions = extract(src, 'static uint32_t vdp2_gradation_color(') + '\n' + extract(src, 'static uint32_t vdp2_extended_color(') + '\n' + extract(src, 'static constexpr uint8_t vdp2_cc_blend_level(') + '\n' + '\n'.join(funcs)
functions = '\n'.join(extract(blend, sig) for sig in (
    'constexpr u32 alpha_blend_r32(', 'constexpr u32 add_blend_r32(')) + '\n' + functions
if a.mutation == 'cumulative':
    functions = functions.replace('? m_vdp2_raw_top.pix(y, x) : dest', '? dest : dest')
if a.mutation == 'ratio':
    functions = functions.replace('? m_vdp2_raw_alpha.pix(y, x) : alpha', '? alpha : alpha')
if a.mutation == 'line-history':
    functions = functions.replace('m_vdp2_raw_top.pix(y, x) = color;', 'm_vdp2_raw_top.pix(y, x) = insert_line ? line_color : color;')
if a.mutation == 'disabled-ratio':
    # Mutate only candidate insertion, not initialization from the back screen.
    pos = functions.index('void saturn_state::vdp2_compose_pixel(')
    functions = functions[:pos] + functions[pos:].replace('m_vdp2_raw_alpha.pix(y, x) = alpha;', 'if (calculate) m_vdp2_raw_alpha.pix(y, x) = alpha;', 1)
if a.mutation == 'shadow':
    functions = functions.replace('bitmap.pix(y, x) = rgb_t(p.r() >> 1, p.g() >> 1, p.b() >> 1);', '(void)p;')

if a.mutation == 'extended':
    functions = functions.replace('if (!second_cc || (cram_mode && third_palette))', 'if (second_cc || (cram_mode && third_palette))')
if a.mutation == 'format':
    functions = functions.replace('(cram_mode && third_palette)', '(cram_mode && !third_palette)')
if a.mutation == 'gradation':
    functions = functions.replace('a / 2 + b / 4 + c / 4', 'a / 4 + b / 4 + c / 2')
if a.mutation == 'halo':
    functions = functions.replace('area.min_x - 2', 'area.min_x')
if a.mutation == 'offset':
    functions = functions.replace('rgb_t adjusted = dest;', 'rgb_t adjusted = color;')
if a.mutation == 'shadow-layer':
    functions = functions.replace('VDP2_SDCTL & mask & 0x3f', '(VDP2_SDCTL | mask) & 0x3f')

code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
#include "palette.h"
using u32=uint32_t;using u8=uint8_t;
struct rectangle {union {int l;int min_x;};int r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
template<class T> struct image {
 int w=0,h=0;unsigned allocations=0;std::vector<T> data;
 image()=default;image(int W,int H){allocate(W,H);}
 void allocate(int W,int H){w=W;h=H;data.assign(w*h,T(0xdeadbeef));++allocations;}
 void fill(T color,const rectangle &r){for(int y=r.t;y<=r.b;++y)for(int x=r.l;x<=r.r;++x)pix(y,x)=color;}
 int width()const{return w;}int height()const{return h;}
 T &pix(int y,int x){assert(x>=0&&x<w&&y>=0&&y<h);return data[y*w+x];}
};
using bitmap_rgb32=image<uint32_t>;using bitmap_ind8=image<uint8_t>;
struct saturn_state {
 unsigned cccr=0,ccrlb=0;bool m_vdp2_composition_active=false;
 bitmap_rgb32 m_vdp2_raw_top,m_vdp2_raw_under;bitmap_ind8 m_vdp2_raw_alpha,m_vdp2_raw_meta,m_vdp2_under_meta;
 bool vdp2_calculation_window(int,int){return true;}
 bool m_vdp2_extended_active=false;bool m_vdp2_gradation_active=false,m_vdp2_gradation_capture=false;unsigned m_vdp2_gradation_layer=7;bitmap_rgb32 m_vdp2_gradation_source;unsigned crmd=0,sdctl=0,clofen=0,clofsl=0;
 unsigned coar=0,coag=0,coab=0,cobr=0,cobg=0,cobb=0;struct {unsigned hreso=0;unsigned get_hreso(){return hreso;}} device;decltype(device)*m_vdp2=&device;
 int m_vdp2_priority_pass=-1,vdp1_sprite_priorities_usage_valid=0;
 uint8_t vdp1_sprite_priorities_used[8]{},vdp1_sprite_priorities_in_fb_line[512][8]{};
 unsigned captures=0;
 static uint32_t dot(unsigned layer,int x,int y){return 0xff000000|((0x139f27+layer*0x319123+x*31719+y*377)&0xffffff);}
 void capture_layer(bitmap_rgb32 &bitmap,const rectangle &r,unsigned layer){
  ++captures;
  for(int y=r.t;y<=r.b;++y)for(int x=r.l;x<=r.r;++x)
   vdp2_compose_pixel(bitmap,x,y,rgb_t(dot(layer,x,y)),true,112,true,rgb_t(0xff777777),layer);
 }
 void vdp2_draw_NBG0(bitmap_rgb32 &b,const rectangle &r){capture_layer(b,r,0);}
 void vdp2_draw_NBG1(bitmap_rgb32 &b,const rectangle &r){capture_layer(b,r,1);}
 void vdp2_draw_NBG2(bitmap_rgb32 &b,const rectangle &r){capture_layer(b,r,2);}
 void vdp2_draw_NBG3(bitmap_rgb32 &b,const rectangle &r){capture_layer(b,r,3);}
 void vdp2_draw_RBG0(bitmap_rgb32 &b,const rectangle &r){capture_layer(b,r,4);}
 void draw_sprites(bitmap_rgb32 &b,const rectangle &r,unsigned priority){if(priority==3)capture_layer(b,r,6);}
 // DECLS
};
#define VDP2_COAR coar
#define VDP2_COAG coag
#define VDP2_COAB coab
#define VDP2_COBR cobr
#define VDP2_COBG cobg
#define VDP2_COBB cobb
#define VDP2_CLOFEN clofen
#define VDP2_CLOFSL clofsl
#define VDP2_SDCTL sdctl
#define VDP2_CRMD crmd
#define VDP2_CCCR cccr
#define VDP2_CCRLB ccrlb
#define VDP2_CCMD ((cccr>>8)&1)
// FUNCTIONS
int main(){saturn_state s;unsigned scenes=0;
 auto half=[](uint32_t c){uint32_t out=0xff000000;for(unsigned sh:{0u,8u,16u})out|=(((c>>sh)&255)/2)<<sh;return out;};
 auto mix=[](uint32_t first,uint32_t second,unsigned ratio,bool add){
  uint32_t out=0;for(unsigned sh:{0u,8u,16u}){unsigned a=(first>>sh)&255,b=(second>>sh)&255;out|=(add?std::min(255u,a+b):(a*(31-ratio)+b*(ratio+1))/32)<<sh;}return out;
 };
 for(unsigned a=0;a<32;++a)for(unsigned b=0;b<32;++b)for(bool second_ratio:{false,true})for(bool additive:{false,true})
 for(unsigned enabled=0;enabled<8;++enabled)for(unsigned line=0;line<8;++line)for(bool shadow:{false,true}){
  s.cccr=0x40|(second_ratio?0x200:0)|(additive?0x100:0);unsigned back_ratio=(a+b)%32,line_ratio=(a^b)%32;
  s.ccrlb=(back_ratio<<8)|line_ratio;unsigned ratios[]={a,b,(a+2*b)%32};
  auto render=[&](bitmap_rgb32 &dest,rectangle clip){
   std::array<uint32_t,32> expected{},raw{};std::array<unsigned,32> raw_ratio{};
   for(int y=clip.t;y<=clip.b;++y)for(int x=clip.l;x<=clip.r;++x){unsigned n=y*8+x;dest.pix(y,x)=expected[n]=raw[n]=0xff123457+x*37+y*53;raw_ratio[n]=back_ratio;}
   s.vdp2_begin_composition(dest,clip);assert(s.m_vdp2_composition_active);
   for(unsigned layer=0;layer<3;++layer){
    for(int y=clip.t;y<=clip.b;++y)for(int x=clip.l;x<=clip.r;++x){
     unsigned n=y*8+x;
     if((layer+x+2*y)%5){
      uint32_t color=0xff000000|((0x813b17+layer*0x315379+x*103+y*7919)&0xffffff),lc=0xff000000|((0xf02541+layer*0x173117+y*997)&0xffffff);
      bool calculate=enabled&(1u<<layer),insert=line&(1u<<layer);
      unsigned selected=second_ratio?(insert?line_ratio:raw_ratio[n]):ratios[layer];
      expected[n]=calculate?mix(color,insert?lc:raw[n],selected,additive):color;
      raw[n]=color;raw_ratio[n]=ratios[layer];
      s.vdp2_compose_pixel(dest,x,y,rgb_t(color),calculate,(31-ratios[layer])*8,insert,rgb_t(lc),layer);
     }
     if(shadow&&layer==1&&(x+y)%3==1){expected[n]=half(expected[n]);s.vdp2_shadow_pixel(dest,x,y,false);}
     assert(dest.pix(y,x)==expected[n]);assert(s.m_vdp2_raw_top.pix(y,x)==raw[n]);assert(s.m_vdp2_raw_alpha.pix(y,x)==(31-raw_ratio[n])*8);
    }
   }
   s.m_vdp2_composition_active=false;
  };
  bitmap_rgb32 full(8,4),split(8,4);render(full,{1,6,1,2});render(split,{1,3,1,2});render(split,{4,6,1,2});
  assert(full.data==split.data);assert(s.m_vdp2_raw_top.allocations==1&&s.m_vdp2_raw_alpha.allocations==1);++scenes;
 }
 // No possible calculation retains the old fast paths without clearing or
 // allocating history; a later mode/size change reinitializes from the new back.
 bitmap_rgb32 larger(11,5);s.cccr=0;s.m_vdp2_composition_active=true;
 s.vdp2_begin_composition(larger,{1,9,1,3});assert(!s.m_vdp2_composition_active&&s.m_vdp2_raw_top.allocations==1);
 s.cccr=0x20;s.vdp2_begin_composition(larger,{1,9,1,3});assert(!s.m_vdp2_composition_active); // LC alone cannot be top
 s.cccr=1;s.ccrlb=31<<8;s.vdp2_begin_composition(larger,{1,9,1,3});
 assert(s.m_vdp2_raw_top.width()==11&&s.m_vdp2_raw_top.height()==5&&s.m_vdp2_raw_top.allocations==2);
 assert(s.m_vdp2_raw_top.pix(1,1)==0xdeadbeef&&s.m_vdp2_raw_alpha.pix(1,1)==0);

 unsigned extended_cases=0;
 // Independent interpretation of the table and figure, using integer division
 // before addition. Mode-0's conflicting 2:1:0 entry is explicitly resolved to
 // figure 12.3's fourth input (also Ymir/MiSTer), not certified on hardware.
 for(unsigned cm=0;cm<3;++cm)for(unsigned hr=0;hr<8;++hr)for(unsigned mode=0;mode<4;++mode)
 for(unsigned palettes=0;palettes<8;++palettes)for(unsigned enables=0;enables<8;++enables)
 for(bool line:{false,true})for(unsigned ratio=0;ratio<32;++ratio)for(bool second:{false,true}){
  s.crmd=cm;s.device.hreso=hr;s.cccr=8|enables|0x20|((mode&1)?0x400:0)|((mode&2)?0x8000:0)|(second?0x200:0);s.ccrlb=7|(11<<8);
  bitmap_rgb32 image(2,1);image.data.assign(2,0xff132537);s.vdp2_begin_composition(image,{0,1,0,0});s.m_vdp2_gradation_active=false;
  uint32_t colors[5]={0xff132537,0xff234765,0xff8193e7,0xfff37b29,0xff091fb1};
  unsigned prior_meta=5,under_meta=5;uint32_t prior=colors[0],under=colors[0];unsigned prior_ratio=11;
  for(unsigned n=0;n<4;++n){
   bool calc=n==3; // lower special-CC eligibility must not substitute for CCEN
   unsigned own_ratio=(ratio+n*7)%32;
   unsigned src=n|((palettes&(1u<<(n%3)))?8:0);
   uint32_t color=colors[n+1],lc=0xff95db61,secondary=line?lc:prior;
   if(calc && (mode&1) && !(mode&2) && hr<2){
    bool sec_cc=line?true:bool(prior_meta&16);
    bool third_pal=(line?prior_meta:under_meta)&8;
    if(sec_cc && (!cm||!third_pal)){
     uint32_t third=line?prior:under;bool four=line&&(prior_meta&16)&&(!cm||!(under_meta&8));
     secondary=0;for(unsigned sh:{0u,8u,16u}){
      unsigned a=((line?lc:prior)>>sh)&255,b=(third>>sh)&255,c=(under>>sh)&255;
      secondary|=(a/2+(four?b/4+c/4:b/2))<<sh;
     }
    }
   }
   bool visible_calc=calc && !(hr>=2 && cm && (line || (prior_meta&8)));
   uint32_t expected=visible_calc?mix(color,secondary,second?(line?7:prior_ratio):own_ratio,false):color;
   s.vdp2_compose_pixel(image,0,0,rgb_t(color),calc,(31-own_ratio)*8,line,rgb_t(lc),src);
   assert(image.pix(0,0)==expected);
   under=prior;under_meta=prior_meta;prior=color;prior_meta=src|((s.cccr&(1u<<n))?16:0);prior_ratio=own_ratio;
   assert(s.m_vdp2_raw_meta.pix(0,0)==prior_meta);
  }
  ++extended_cases;
 }
 // All signed 9-bit offsets, both sets, every background/back/sprite identity.
 // Offset the computed top result, never the raw source recorded for later use.
 unsigned offset_cases=0;s.device.hreso=0;s.crmd=0;
 for(unsigned offset=0;offset<512;++offset)for(bool bank:{false,true})for(unsigned layer=0;layer<7;++layer)
 for(bool calc:{false,true})for(bool add:{false,true}){
  s.cccr=0x40|(add?0x100:0);s.clofen=0;s.clofsl=bank?0x7f:0;
  s.coar=offset;s.coag=(offset+173)%512;s.coab=(offset+317)%512;
  s.cobr=(offset+311)%512;s.cobg=(offset+127)%512;s.cobb=offset;
  bitmap_rgb32 image(2,1);image.data.assign(2,0xff812b67);s.vdp2_begin_composition(image,{0,1,0,0});s.clofen=1u<<layer;
  uint32_t color=0xfff39d21,base=calc?mix(color,0xff812b67,17,add):color,expected=0xff000000;
  unsigned offsets[]={bank?s.cobb:s.coab,bank?s.cobg:s.coag,bank?s.cobr:s.coar};
  for(unsigned i=0;i<3;++i){int delta=offsets[i]<256?int(offsets[i]):int(offsets[i])-512;expected|=std::clamp(int((base>>(i*8))&255)+delta,0,255)<<(i*8);}
  s.vdp2_compose_pixel(image,0,0,rgb_t(color),calc,112,false,rgb_t(0),layer);
  assert(image.pix(0,0)==expected&&s.m_vdp2_raw_top.pix(0,0)==color);
  // A later top ignores the first screen's offset.
  s.clofen=0;s.vdp2_compose_pixel(image,0,0,rgb_t(0xff192b3d),true,112,false,rgb_t(0),0);
  assert(image.pix(0,0)==mix(0xff192b3d,color,17,add));++offset_cases;
 }
 unsigned shadow_cases=0;s.clofen=0;s.cccr=0;
 for(unsigned mask=0;mask<64;++mask)for(unsigned layer=0;layer<7;++layer)for(bool select:{false,true}){
  s.sdctl=mask;s.cccr=1;bitmap_rgb32 image(2,1);image.data.assign(2,0xff812b67);s.vdp2_begin_composition(image,{0,1,0,0});
  s.vdp2_compose_pixel(image,0,0,rgb_t(0xfff37b29),false,112,false,rgb_t(0),layer);
  s.vdp2_shadow_pixel(image,0,0,select);bool shadow=!select||((mask>>layer)&1);
  assert(image.pix(0,0)==(shadow?half(0xfff37b29):0xfff37b29));assert(s.m_vdp2_raw_top.pix(0,0)==0xfff37b29);
  s.vdp2_compose_pixel(image,0,0,rgb_t(0xff193b5d),true,112,false,rgb_t(0),0);
  assert(image.pix(0,0)==mix(0xff193b5d,0xfff37b29,17,false));++shadow_cases;
 }

 unsigned gradation_cases=0;s.sdctl=s.clofen=0;s.crmd=0;s.device.hreso=0;
 constexpr unsigned layers[]={6,4,0,7,1,2,3,7};
 for(unsigned number=0;number<8;++number)for(unsigned ratio=0;ratio<32;++ratio)
 for(bool second:{false,true})for(bool line:{false,true})for(bool calc:{false,true})for(unsigned rank=0;rank<3;++rank){
  s.cccr=0x847f|(number<<12)|(second?0x200:0);s.ccrlb=5|(11<<8);
  unsigned layer=layers[number];
  auto render=[&](bitmap_rgb32 &out,rectangle clip){
   out.fill(0xff123456,clip);s.vdp2_begin_composition(out,clip);
   assert(s.m_vdp2_gradation_active==(layer!=7));s.captures=0;
   if(layer!=7)s.m_vdp2_gradation_source.data.assign(16,0xfffefdfc);
   s.vdp2_capture_gradation(clip);assert(s.captures==(layer!=7));
   for(int y=clip.t;y<=clip.b;++y)for(int x=clip.l;x<=clip.r;++x){
    assert(s.m_vdp2_raw_top.pix(y,x)==0xff123456);
    if(layer==7)continue;
    uint32_t a=s.dot(layer,x,y),b=s.dot(layer,std::max(0,x-1),y),c=s.dot(layer,std::max(0,x-2),y),grad=0;
    if(!x)grad=a;
    else for(unsigned sh:{0u,8u,16u}){unsigned u=(a>>sh)&255,v=(b>>sh)&255,w=(c>>sh)&255;grad|=(x==1?(u+v)/2:u/2+v/4+w/4)<<sh;}
    unsigned other=(layer+1)%7;
    if(rank){
     s.vdp2_compose_pixel(out,x,y,rgb_t(a),false,80,false,rgb_t(0),layer);
     if(rank==2)s.vdp2_compose_pixel(out,x,y,rgb_t(0xff25476b),false,104,false,rgb_t(0),other);
    }
    uint32_t color=rank?0xff91b375:a;
    unsigned chosen_ratio=second?(rank==1?21:rank==2?18:ratio):ratio;
    uint32_t secondary=rank==2?0xff25476b:grad;
    s.vdp2_compose_pixel(out,x,y,rgb_t(color),calc,(31-ratio)*8,line,rgb_t(0xffef351b),rank?other:layer);
    assert(out.pix(y,x)==(calc?mix(color,secondary,chosen_ratio,false):color));
   }
  };
  bitmap_rgb32 full(8,2),split(8,2);render(full,{0,7,0,1});render(split,{0,2,0,1});render(split,{3,7,0,1});assert(full.data==split.data);++gradation_cases;
 }
 std::cout<<gradation_cases<<" gradation capture/halo/source-rank/ratio/line-exclusion/split-clip scenes passed\n";
 std::cout<<extended_cases<<" extended format/CRAM/enable/ratio/mode cases, "<<offset_cases<<" post-calculation signed-offset cases, "<<shadow_cases<<" layer-selective shadow cases passed\n";
 std::cout<<scenes<<" raw-second-image/ratio/line/shadow/split-clip scenes passed\n";
}
'''
code = code.replace('// DECLS', '\n'.join(fn[:fn.index('{')].replace('saturn_state::', '') + ';' for fn in funcs)).replace('// FUNCTIONS', functions)
with tempfile.TemporaryDirectory(prefix='saturn-composition-') as d:
    cpp = Path(d) / 'test.cpp'
    exe = Path(d) / 'test'
    cpp.write_text(code)
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++20', '-I', str(ROOT / 'src/lib/util'),
                    '-O1', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production RGB character helpers: physical boundaries, zoom, flip and split clips.

Uses MAME color/blend primitives and a controlled window; not bus timing or a
complete tilemap/cache rendering fixture.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
names=('vdp2_drawgfx_rgb555','vdp2_drawgfx_rgb888','vdp2_drawgfxzoom_rgb555','vdp2_drawgfxzoom_rgb888')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=names+('tail',));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text();blend=(ROOT/'src/emu/drawgfx.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
funcs=[extract(src,'void saturn_state::'+n+'(') for n in names]
if a.mutation=='tail':
 funcs[0]=funcs[0].replace(') & vram_mask);', '));')
elif a.mutation:
 i=names.index(a.mutation);funcs[i]=funcs[i].replace('? 0xfffff : 0x7ffff','? 0xfffff : 0xfffff')
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include "palette.h"
using u32=uint32_t;using u8=uint8_t;using s32=int32_t;using s64=int64_t;
// BLENDS
struct rectangle {
 int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}
 void operator&=(const rectangle &o){l=std::max(l,o.l);r=std::min(r,o.r);t=std::max(t,o.t);b=std::min(b,o.b);}
};
struct bitmap_rgb32 {
 std::array<uint32_t,24*24> data;bitmap_rgb32(){data.fill(0xff204060);}
 uint32_t &pix(int y,int x=0){assert(y>=0&&y<24&&x>=0&&x<24);return data[y*24+x];}
 rectangle cliprect(){return {0,23,0,23};}
};
struct saturn_state {
 struct video {bool large=false;bool get_vramsz(){return large;}} dev;video *m_vdp2=&dev;
 struct {unsigned incx=65536,incy=65536,fade_control=0;} current_tilemap;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 bool vdp2_window_process(int x,int y){return (x+2*y)%5!=0;}
 void vdp2_compute_color_offset(int*,int*,int*,int){assert(false);}
 // DECLS
};
#define STV_TRANSPARENCY_NONE 1
#define STV_TRANSPARENCY_ADD_BLEND 2
#define STV_TRANSPARENCY_ALPHA 4
// FUNCTIONS
int main(){saturn_state s;unsigned cases=0;
 for(unsigned i=0;i<1048576;++i)s.m_vdp2_legacy.gfx_decode[i]=(i*71+(i>>5)*17+(i>>19)*103)^(i>>8);
 for(unsigned format=0;format<4;++format)for(bool large:{false,true})for(unsigned code:{0u,3u,0x3ff8u,0x3fffu,0x4000u,0x7ff8u,0x7fffu,0x8001u})
 for(unsigned flips=0;flips<4;++flips)for(unsigned width:{4u,8u,16u})for(unsigned mode:{0u,2u,4u})for(bool opaque:{false,true}){
  bool zoom=format>=2,rgb32=format%2; if(!zoom&&(width!=8||mode==2))continue;
  s.dev.large=large;s.current_tilemap.incx=s.current_tilemap.incy=8*65536/width;
  unsigned capacity=large?1048576:524288,bytes=rgb32?4:2;
  bitmap_rgb32 full,split;unsigned flags=mode|unsigned(opaque);
  auto draw=[&](bitmap_rgb32 &b,rectangle clip){
   switch(format){
   case 0:s.vdp2_drawgfx_rgb555(b,clip,code,flips&1,flips&2,2,3,flags,120);break;
   case 1:s.vdp2_drawgfx_rgb888(b,clip,code,flips&1,flips&2,2,3,flags,120);break;
   case 2:s.vdp2_drawgfxzoom_rgb555(b,clip,code,0,flips&1,flips&2,2,3,flags,width*8192,width*8192,width,width,120);break;
   case 3:s.vdp2_drawgfxzoom_rgb888(b,clip,code,0,flips&1,flips&2,2,3,flags,width*8192,width*8192,width,width,120);break;
   }
  };
  draw(full,{0,23,0,23});draw(split,{0,6,0,23});draw(split,{7,23,0,8});draw(split,{7,23,9,23});
  for(unsigned y=0;y<24;++y)for(unsigned x=0;x<24;++x){
   uint32_t expected=0xff204060;
   if(x>=2&&x<2+width&&y>=3&&y<3+width&&(x+2*y)%5){
    unsigned col=(flips&1?width-1-(x-2):x-2)*8/width,row=(flips&2?width-1-(y-3):y-3)*8/width;
    unsigned address=(code*32+(row*8+col)*bytes)%capacity;uint32_t dot=0;
    for(unsigned b=0;b<bytes;++b)dot=(dot<<8)|s.m_vdp2_legacy.gfx_decode[(address+b)%capacity];
    if(opaque||(dot&(rgb32?0x80000000:0x8000))){
     uint32_t color=rgb32?rgb_t(dot&255,(dot>>8)&255,(dot>>16)&255):rgb_t(pal5bit(dot&31),pal5bit((dot>>5)&31),pal5bit((dot>>10)&31));
     expected=mode==4?alpha_blend_r32(expected,color,120):mode==2?add_blend_r32(expected,color):color;
    }
   }
   assert(full.pix(y,x)==expected&&split.pix(y,x)==expected);
  }
  ++cases;
 }
 std::cout<<cases<<" direct-color character boundary/zoom/flip/blend/window/split images passed\n";
}
'''
code=code.replace('// DECLS','\n'.join(f[:f.index('{')].replace('saturn_state::','')+';' for f in funcs)).replace('// FUNCTIONS','\n'.join(funcs)).replace('// BLENDS','\n'.join(extract(blend,s) for s in ('constexpr u32 alpha_blend_r32(', 'constexpr u32 add_blend_r32(')))
with tempfile.TemporaryDirectory(prefix='saturn-direct-cell-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production legacy bitmap VRAM-size/address tests for all five color formats.

Controlled window and palette inputs; not mode-resource, fetch-timing or hardware
qualification. Existing bitmap/window and point-sampling suites cover other paths.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
formats=('4bpp','8bpp','11bpp','rgb15','rgb32')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=formats);a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text();blend=(ROOT/'src/emu/drawgfx.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
funcs=[extract(src,'void saturn_state::draw_'+name+'_bitmap(') for name in formats]
if a.mutation:
 n=formats.index(a.mutation);funcs[n]=funcs[n].replace('? 0xfffff : 0x7ffff', '? 0x7ffff : 0x7ffff')
f=extract(src,'static constexpr uint8_t vdp2_expand_color5(')+'\n'+'\n'.join(funcs)
fields=sorted(set(re.findall(r'current_tilemap\.(\w+)',f)))
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include "palette.h"
using u32=uint32_t;using u8=uint8_t;
// BLEND
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {
 std::array<uint32_t,48> data;bitmap_rgb32(){data.fill(0x204060);}
 uint32_t &pix(int y,int x){assert(x>=0&&x<8&&y>=0&&y<6);return data[y*8+x];}
};
struct saturn_state {
 unsigned mode=0;
 struct video {bool large=false;bool get_vramsz(){return large;}} dev;video *m_vdp2=&dev;
 struct {// FIELDS
 } current_tilemap;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 struct palette {uint32_t pen(unsigned p){assert(p<2048);return 0xff000000|((p*0x1937du)&0xffffff);}} pal;palette *m_palette=&pal;
 bool vdp2_window_process(int x,int y){return (x+2*y)%5!=0;}
 void vdp2_compute_color_offset(int*,int*,int*,int){assert(false);}
 // DECLS
};
#define STV_TRANSPARENCY_NONE 1
#define VDP2_CCMD (mode==2)
// FUNCTIONS
int main(){saturn_state s;auto &t=s.current_tilemap;auto *memory=s.m_vdp2_legacy.gfx_decode.get();
 for(unsigned i=0;i<0x100000;++i)memory[i]=i%23?uint8_t(i*37+(i>>17)*71+(i>>8)*13):0;
 using draw=void(saturn_state::*)(bitmap_rgb32&,const rectangle&);
 draw drawers[]={&saturn_state::draw_4bpp_bitmap,&saturn_state::draw_8bpp_bitmap,&saturn_state::draw_11bpp_bitmap,&saturn_state::draw_rgb15_bitmap,&saturn_state::draw_rgb32_bitmap};
 unsigned cases=0;
 for(unsigned format=0;format<5;++format)for(unsigned size=0;size<4;++size)for(unsigned map=0;map<8;++map)
 for(bool large:{false,true})for(unsigned sx:{0u,511u,1023u})for(unsigned sy:{0u,255u,511u})for(unsigned mode=0;mode<3;++mode)for(bool opaque:{false,true}){
  t={};s.mode=mode;s.dev.large=large;t.bitmap_size=size;t.bitmap_map=map;t.scrollx=sx;t.scrolly=sy;
  t.incx=t.incy=65536;t.bitmap_palette_number=1;t.colour_ram_address_offset=2;t.alpha=120;t.colour_calculation_enabled=mode!=0;t.transparency=opaque;
  bitmap_rgb32 out,split,expected;
  (s.*drawers[format])(out,{1,6,1,4});(s.*drawers[format])(split,{1,3,1,4});(s.*drawers[format])(split,{4,6,1,4});
  unsigned width=size&2?1024:512,height=size&1?512:256,bytes=large?1048576:524288;
  for(unsigned y=1;y<=4;++y)for(unsigned x=1;x<=6;++x){
   if((x+2*y)%5==0)continue;
   unsigned px=(x+sx)%width,py=(y+sy)%height,dot=px+py*width;
   unsigned address=(map*131072+(format==0?dot/2:format==1?dot:format==4?dot*4:dot*2))%bytes;
   unsigned count=format<2?1:format==4?4:2;uint32_t raw=0;
   for(unsigned b=0;b<count;++b)raw=raw*256+memory[(address+b)%bytes];
   if(format==0)raw=(raw>>(px%2?0:4))&15;
   if(format==2)raw%=2048;
   bool covered=format<3?raw!=0:format==3?raw&32768:raw&0x80000000;
   if(!covered&&!opaque)continue;
   uint32_t color;
   if(format<3)color=s.pal.pen(raw+(format<2?768:0));
   else if(format==3){auto expand=[](unsigned v){v&=31;return (v<<3)|(v>>2);};color=0xff000000|(expand(raw)<<16)|(expand(raw>>5)<<8)|expand(raw>>10);}
   else color=0xff000000|((raw&255)<<16)|(raw&0xff00)|((raw>>16)&255);
   uint32_t result=color;
   if(mode){result=0;for(unsigned sh:{0u,8u,16u}){unsigned c=(color>>sh)&255,d=(0x204060>>sh)&255;result|=(mode==2?std::min(255u,c+d):(c*15+d*17)/32)<<sh;}}
   expected.pix(y,x)=result;
  }
  assert(out.data==expected.data&&split.data==expected.data);++cases;
 }
 std::cout<<cases<<" all-format bitmap size/bank/wrap/coverage/blend/split images passed\n";
}
'''
code=code.replace('// FIELDS','\n'.join('unsigned '+n+'=0;' for n in fields)).replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','')+';' for x in funcs)).replace('// FUNCTIONS',f).replace('// BLEND','\n'.join(extract(blend,sig) for sig in ('constexpr u32 alpha_blend_r32(', 'constexpr u32 add_blend_r32(')))
with tempfile.TemporaryDirectory(prefix='saturn-bitmap-size-') as tmp:
 cpp=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

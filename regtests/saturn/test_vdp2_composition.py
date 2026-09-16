#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production raw-second-image composition, ratios, line insertion and shadow updates.

Uses actual MAME RGB blend primitives and an independent /32 component oracle.
Sources/coverage/priority order are controlled inputs; this is not a game replay
or extended four-image/gradation qualification.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation', choices=('cumulative', 'ratio', 'line-history', 'disabled-ratio', 'shadow'))
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
    'void saturn_state::vdp2_begin_composition(',
    'void saturn_state::vdp2_compose_pixel(',
    'void saturn_state::vdp2_shadow_pixel(')]
functions = extract(src, 'static constexpr uint8_t vdp2_cc_blend_level(') + '\n' + '\n'.join(funcs)
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
    functions = functions.replace('m_vdp2_raw_top.pix(y, x) = rgb_t(p.r() >> 1, p.g() >> 1, p.b() >> 1);', '(void)p;')

code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
#include "palette.h"
using u32=uint32_t;using u8=uint8_t;
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
template<class T> struct image {
 int w=0,h=0;unsigned allocations=0;std::vector<T> data;
 image()=default;image(int W,int H){allocate(W,H);}
 void allocate(int W,int H){w=W;h=H;data.assign(w*h,T(0xdeadbeef));++allocations;}
 int width()const{return w;}int height()const{return h;}
 T &pix(int y,int x){assert(x>=0&&x<w&&y>=0&&y<h);return data[y*w+x];}
};
using bitmap_rgb32=image<uint32_t>;using bitmap_ind8=image<uint8_t>;
struct saturn_state {
 unsigned cccr=0,ccrlb=0;bool m_vdp2_composition_active=false;
 bitmap_rgb32 m_vdp2_raw_top;bitmap_ind8 m_vdp2_raw_alpha;
 // DECLS
};
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
      s.vdp2_compose_pixel(dest,x,y,rgb_t(color),calculate,(31-ratios[layer])*8,insert,rgb_t(lc));
     }
     if(shadow&&layer==1&&(x+y)%3==1){expected[n]=half(expected[n]);raw[n]=half(raw[n]);s.vdp2_shadow_pixel(dest,x,y);}
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

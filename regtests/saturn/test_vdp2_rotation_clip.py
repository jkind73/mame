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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('origin','window'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
head=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
f=extract(src,'static inline uint32_t coef_delta(')+'\n'+extract(src,'void saturn_state::vdp2_copy_roz_bitmap(')
if a.mutation=='origin':
 f=f.replace('xs = uint32_t(xs) + uint32_t(int64_t(dxs) * cliprect.left());','(void)0;').replace('ys = uint32_t(ys) + uint32_t(int64_t(dys) * cliprect.left());','(void)0;')
if a.mutation=='window':
 f=f.replace('if (!vdp2_roz_window(hcnt, vcnt))','if (false)').replace('if (current_tilemap.roz_mode3 &&','if (false && current_tilemap.roz_mode3 &&')
names=sorted(set(re.findall(r'VDP2_\w+',f)))
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
using s64=int64_t;
int32_t mul_fixed32(int32_t a,int32_t b){return uint32_t((int64_t(a)*b)>>16);}
bool BIT(unsigned a,int b){return (a>>b)&1;}
struct rgb_t {uint32_t v=0;rgb_t()=default;rgb_t(uint32_t a):v(a){}operator uint32_t()const{return v;}};
uint32_t alpha_blend_r32(uint32_t d,uint32_t s,unsigned a){uint32_t out=0;for(int sh:{0,8,16})out|=((((s>>sh)&255)*a+((d>>sh)&255)*(256-a))>>8)<<sh;return out;}
uint32_t add_blend_r32(uint32_t d,uint32_t s){uint32_t out=0;for(int sh:{0,8,16})out|=std::min(255u,((s>>sh)&255)+((d>>sh)&255))<<sh;return out;}
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {int w,h;std::vector<uint32_t> pixels;bitmap_rgb32(int W,int H):w(W),h(H),pixels(W*H,0x123456){}uint32_t &pix(int y,int x=0){assert(x>=0&&x<w&&y>=0&&y<h);return pixels[y*w+x];}};
struct device {int lsmd=0,hreso=0;int get_lsmd(){return lsmd;}int get_hreso(){return hreso;}};
struct saturn_state {
 // ROTATION
 struct { // REGS
 } regs;
 struct {int colour_calculation_enabled=0,transparency=1,fade_control=0,alpha=120;bool roz_mode3=false;} current_tilemap;
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
 for(int y=0;y<64;++y)for(int x=0;x<64;++x)source.pix(y,x)=0x800000|(y<<8)|x;
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
   unsigned color=0x800000|(sy<<8)|sx;
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(0x123456,color,120):add_blend_r32(0x123456,color);
  }
  assert(full.pixels==expected.pixels);++cases;
 }
 std::cout<<cases<<" rotation coefficient/window/split-clip images passed\n";
}
'''
code=code.replace('// ROTATION',extract(head,'struct rotation_table {')+' current_rotation_table;')
code=code.replace('// REGS','\n'.join('unsigned '+n+'=0;' for n in names))
code=code.replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-rotation-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-Wno-unused-but-set-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

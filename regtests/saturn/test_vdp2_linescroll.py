#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production line-scroll scheduling with recording basic renderers.

Checks packed table addressing, interval anchoring, clipping, zoom and state
restoration, not fractional pixel resampling, interlace fetch timing or bus slots.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', action='store_true')
p.add_argument('--mutation', choices=('address', 'clip', 'zoom', 'restore', 'fraction', 'size'))
a = p.parse_args()
src = subprocess.check_output(['git', 'show', 'd4343068:src/mame/sega/saturn.cpp'], cwd=ROOT, text=True) if a.baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text()
start = src.index('void saturn_state::vdp2_check_tilemap_with_linescroll(')
end = src.index('void saturn_state::vdp2_draw_line(', start)
f = src[start:end]
if a.baseline:
    f = src[src.index('#define VDP2_READ_VERTICAL_LINESCROLL'):start] + f
if a.mutation == 'address': f = f.replace('(first_line / interval) * stride', 'first_line * stride')
if a.mutation == 'clip': f = f.replace('std::min(end - 1, cliprect.bottom())', 'end - 1')
if a.mutation == 'zoom': f = f.replace('read() & 0x0007ff00;', 'util::sext(read() & 0x0007ff00, 19);')
if a.mutation == 'restore': f = f.replace('current_tilemap.incx = main_incx;', '(void)main_incx;')
if a.mutation == 'fraction': f = f.replace('current_tilemap.scrolly_fraction = values[4];', 'current_tilemap.scrolly_fraction = 0;')
if a.mutation == 'size': f = f.replace('address++ & word_mask', 'address++ & (word_mask | 0x20000)')
code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
namespace util {int32_t sext(uint32_t x,int n){return int32_t(x<<(32-n))>>(32-n);}}
struct rectangle {int l,r,t,b;int top()const{return t;}int bottom()const{return b;}void sety(int a,int z){t=a;b=z;}};
using sample=std::array<int64_t,3>;
struct bitmap_rgb32 {std::array<sample,48> rows{};};
struct saturn_state {
 struct video {bool large=false;bool get_vramsz(){return large;}} dev;video *m_vdp2=&dev;
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 struct {int scrollx=11,scrolly=17,incx=65536,incy=65536,linescroll_interval=1;
 unsigned scrollx_fraction=0,scrolly_fraction=0;
 unsigned linescroll_table_address=0;
 bool linescroll_enable=false,vertical_linescroll_enable=false,linezoom_enable=false,bitmap_enable=false;
 } current_tilemap;
 rectangle allowed{0,0,0,0};int calls=0;
 void draw(bitmap_rgb32 &out,const rectangle &clip){
  assert(clip.l==allowed.l&&clip.r==allowed.r&&clip.t>=allowed.t&&clip.b<=allowed.b);
  ++calls;auto &t=current_tilemap;
  for(int y=clip.t;y<=clip.b;++y)out.rows[y]={int64_t(t.scrollx)*65536+t.scrollx_fraction,t.scrolly+((int64_t(y)*t.incy+t.scrolly_fraction)>>16),t.incx};
  // Basic tile rendering normalizes scroll state. The scheduler must not
  // let that alter later runs or the original register-derived descriptor.
  t.scrollx&=7;t.scrolly&=7;
 }
 void vdp2_draw_basic_bitmap(bitmap_rgb32 &b,const rectangle &r){draw(b,r);}
 void vdp2_draw_basic_tilemap(bitmap_rgb32 &b,const rectangle &r){draw(b,r);}
 void vdp2_check_tilemap_with_linescroll(bitmap_rgb32&,const rectangle&);
};
// FUNCTION
int main(){
 saturn_state s;unsigned cases=0;
 for(int flags=1;flags<8;++flags)for(int interval:{1,2,4,8,16})for(int top:{0,1,3,9,17})
 for(int height:{1,3,13})for(int pattern:{0,1})for(bool bitmap:{false,true})for(int step:{32768,65536,98304,131072})for(int phase:{0,0xc000})for(bool large:{false,true}){
  s.dev.large=large;unsigned words=large?0x40000:0x20000;
  auto &t=s.current_tilemap;t={};t.linescroll_enable=flags&1;t.vertical_linescroll_enable=flags&2;t.linezoom_enable=flags&4;
  t.bitmap_enable=bitmap;t.linescroll_interval=interval;t.incy=step;t.scrollx_fraction=t.scrolly_fraction=phase;t.linescroll_table_address=0xffff8;
  unsigned address=t.linescroll_table_address/4;
  // Poison both physical-ring candidates before writing the active table.
  // Otherwise preceding size cases can leave identical data in both halves.
  for(unsigned n=0;n<144;++n){s.m_vdp2_vram[(address+n)%0x40000]=0x017fff00;s.m_vdp2_vram[(address+n)%0x20000]=0x017fff00;}
  // Build packed entries in H, V, Z order. Sparse functions do not leave holes.
  // Distinct H/V values expose wrong table entries; zoom=4.0 exposes signed decoding.
  for(int entry=0;entry<48;++entry){
   if(flags&1)s.m_vdp2_vram[address++%words]=uint32_t((pattern?entry*3-19:-19)*65536+0x8000)&0x07ffff00;
   if(flags&2)s.m_vdp2_vram[address++%words]=uint32_t((pattern?entry*5-7:-7)*65536+0x4000)&0x07ffff00;
   if(flags&4)s.m_vdp2_vram[address++%words]=pattern?(entry%2?0x8000:0x40000):0x40000;
  }
  bitmap_rgb32 out,expected,split;int bottom=top+height-1;
  s.allowed={2,14,top,bottom};s.calls=0;
  s.vdp2_check_tilemap_with_linescroll(out,s.allowed);
  for(int y=top;y<=bottom;++y){
   int entry=y/interval,anchor=entry*interval;
   int64_t x=11*65536+phase+((flags&1)?(pattern?entry*3-19:-19)*65536+0x8000:0);
   int64_t v=17*65536+phase+((flags&2)?(pattern?entry*5-7:-7)*65536+0x4000+int64_t(y-anchor)*step:int64_t(y)*step);
   v >>= 16;
   int z=(flags&4)?(pattern?(entry%2?0x8000:0x40000):0x40000):65536;
   expected.rows[y]={x,v,z};
  }
  assert(out.rows==expected.rows);
  assert(t.scrollx==11&&t.scrolly==17&&t.incx==65536);
  assert(t.scrollx_fraction==unsigned(phase)&&t.scrolly_fraction==unsigned(phase));
  assert(s.calls<=(bottom/interval-top/interval+1));
  if(!pattern&&!(flags&2))assert(s.calls==1);
  // Sequential partial passes must match the whole pass without reinitializing
  // the descriptor, including a split inside an interval.
  for(int y=top;y<=bottom;++y){s.allowed={2,14,y,y};s.vdp2_check_tilemap_with_linescroll(split,s.allowed);}
  assert(split.rows==expected.rows);++cases;
 }
 std::cout<<cases<<" line-scroll scheduling/partial-clip scenarios passed\n";
}
'''
code = code.replace('// FUNCTION', f)
with tempfile.TemporaryDirectory(prefix='saturn-linescroll-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','c++'), '-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

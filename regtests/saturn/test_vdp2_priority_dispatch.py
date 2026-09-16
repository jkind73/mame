#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production frame priority scheduling with controlled opaque layer/sprite dots.

The independent oracle selects the highest (priority, tie-order) source per dot.
Actual name/dot decoding and pass filtering are exercised by the scroll/rotation
image suites. This does not qualify general/extended color composition.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation', choices=('lsb', 'order'))
a = p.parse_args()
src = (ROOT / 'src/mame/sega/saturn.cpp').read_text()


def extract(sig):
    start = src.index(sig)
    end = src.index('{', start) + 1
    depth = 1
    while depth:
        depth += (src[end] == '{') - (src[end] == '}')
        end += 1
    return src[start:end]


functions = '\n'.join(extract(sig) for sig in (
    'static constexpr bool vdp2_priority_pass_matches(',
    'uint32_t saturn_state::screen_update_vdp2('))
if a.mutation == 'lsb':
    functions = functions.replace('(base & 6) == (pass & 6)', 'base == pass')
if a.mutation == 'order':
    functions = functions.replace('vdp2_draw_NBG3(m_tmpbitmap, cliprect);', 'vdp2_draw_NBG0(m_tmpbitmap, cliprect);')

code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
struct screen_device {};
struct rectangle { int l,r,t,b; };
struct bitmap_rgb32 {
 std::array<uint32_t,32> data;
 bitmap_rgb32(){data.fill(0xdeadbeef);}
 uint32_t &pix(int y,int x){assert(x>=0&&x<8&&y>=0&&y<4);return data[y*8+x];}
};
void copybitmap(bitmap_rgb32 &d,bitmap_rgb32 &s,int,int,int,int,const rectangle &c){
 for(int y=c.t;y<=c.b;++y)for(int x=c.l;x<=c.r;++x)d.pix(y,x)=s.pix(y,x);
}
struct saturn_state {
 bool m_vdp2_composition_active=false;
 void vdp2_begin_composition(bitmap_rgb32&,const rectangle&){m_vdp2_composition_active=true;}
 unsigned modes=0,base[5]{},sprite_priority=0,seed=0;
 struct video {bool enabled=true;bool get_disp(){return enabled;}} device;
 video *m_vdp2=&device;
 bitmap_rgb32 m_tmpbitmap;
 int m_vdp2_priority_pass=-1;
 int vdp1_sprite_priorities_usage_valid=0;
 uint8_t vdp1_sprite_priorities_used[8]{},vdp1_sprite_priorities_in_fb_line[4][8]{};
 std::vector<unsigned> events;
 unsigned invalidations=0,fades=0;
 void vdp2_window_cache_invalidate(){++invalidations;}
 void vdp2_fade_effects(){++fades;}
 void vdp2_draw_back(bitmap_rgb32 &b,const rectangle &c){for(int y=c.t;y<=c.b;++y)for(int x=c.l;x<=c.r;++x)b.pix(y,x)=0x112233;}
 void layer(bitmap_rgb32 &b,const rectangle &c,unsigned id){
  assert(m_vdp2_priority_pass>0&&m_vdp2_priority_pass<8);
  events.push_back(m_vdp2_priority_pass*8+id);
  unsigned mode=(modes>>(id*2))&3;
  for(int y=c.t;y<=c.b;++y)for(int x=c.l;x<=c.r;++x){
   if((x+2*y+id+seed)%5==0)continue;
   unsigned priority=base[id];
   if(mode==1||mode==2)priority=(priority&6)|((x+y+id+seed)&1);
   if(priority==unsigned(m_vdp2_priority_pass))b.pix(y,x)=0xff000000|((id+1)*0x10203+x*17+y);
  }
 }
 void vdp2_draw_NBG0(bitmap_rgb32 &b,const rectangle &c){layer(b,c,0);}
 void vdp2_draw_NBG1(bitmap_rgb32 &b,const rectangle &c){layer(b,c,1);}
 void vdp2_draw_NBG2(bitmap_rgb32 &b,const rectangle &c){layer(b,c,2);}
 void vdp2_draw_NBG3(bitmap_rgb32 &b,const rectangle &c){layer(b,c,3);}
 void vdp2_draw_RBG0(bitmap_rgb32 &b,const rectangle &c){layer(b,c,4);}
 void draw_sprites(bitmap_rgb32 &b,const rectangle &c,unsigned priority){
  events.push_back(priority*8+5);
  if(priority!=sprite_priority)return;
  for(int y=c.t;y<=c.b;++y)for(int x=c.l;x<=c.r;++x)if((x+2*y+5+seed)%5)b.pix(y,x)=0xff000000|(6*0x10203+x*17+y);
 }
 uint32_t screen_update_vdp2(screen_device&,bitmap_rgb32&,const rectangle&);
};
#define VDP2_N0PRIN base[0]
#define VDP2_N1PRIN base[1]
#define VDP2_N2PRIN base[2]
#define VDP2_N3PRIN base[3]
#define VDP2_R0PRIN base[4]
#define VDP2_SFPRMD modes
// FUNCTIONS
int main(){saturn_state s;screen_device screen;unsigned cases=0;
 for(unsigned config=0;config<1024;++config)for(unsigned seed=0;seed<16;++seed)for(unsigned sprite=0;sprite<8;++sprite){
  s.seed=seed;s.modes=config;s.sprite_priority=sprite;
  for(unsigned id=0;id<5;++id)s.base[id]=(seed+(seed&8?0:id*3))%8;
  s.events.clear();s.invalidations=s.fades=0;s.m_vdp2_priority_pass=99;
  bitmap_rgb32 out,expected;
  s.screen_update_vdp2(screen,out,{1,6,1,2});
  assert(s.invalidations==1&&s.fades==1&&s.m_vdp2_priority_pass==-1&&!s.m_vdp2_composition_active);
  std::vector<unsigned> events;
  unsigned order[]={3,2,1,0,4,5};
  for(unsigned pri=1;pri<8;++pri)for(unsigned id:order){
   if(id==5){events.push_back(pri*8+id);continue;}
   unsigned mode=(config>>(id*2))&3,lo=s.base[id];
   bool visit=mode==1||mode==2?(pri==lo/2*2||pri==lo/2*2+1):pri==lo;
   if(visit)events.push_back(pri*8+id);
  }
  assert(events==s.events);
  for(int y=1;y<=2;++y)for(int x=1;x<=6;++x){
   unsigned winner=6,best=0;
   for(unsigned id:order){
    if((x+2*y+id+seed)%5==0)continue;
    unsigned priority=id==5?sprite:s.base[id];
    if(id!=5){unsigned mode=(config>>(id*2))&3;if(mode==1||mode==2)priority=priority/2*2+(x+y+id+seed)%2;}
    if(priority&&priority>=best){best=priority;winner=id;}
   }
   expected.pix(y,x)=winner==6?0x112233:0xff000000|((winner+1)*0x10203+x*17+y);
  }
  assert(out.data==expected.data);++cases;
 }
 s.device.enabled=false;s.events.clear();s.m_vdp2_priority_pass=99;
 bitmap_rgb32 out;s.screen_update_vdp2(screen,out,{1,6,1,2});
 assert(s.events.empty()&&s.m_vdp2_priority_pass==-1&&out.pix(1,1)==0x112233);
 std::cout<<cases<<" priority-pass scheduling/tie-order images passed\n";
}
'''.replace('// FUNCTIONS', functions)
with tempfile.TemporaryDirectory(prefix='saturn-priority-dispatch-') as d:
    cpp = Path(d) / 'test.cpp'
    exe = Path(d) / 'test'
    cpp.write_text(code)
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++20', '-O1', '-Wall', '-Wextra',
                    '-Werror', '-Wno-unused-parameter',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production W0/W1 and back-table physical-size wrapping.

Preserves current line/interlace indexing; checks address arithmetic rather than
claiming hardware timing or a linked frame replay.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('w0','w1','back'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(sig):
 start=src.index(sig);end=src.index('{',start)+1;depth=1
 while depth:
  depth+=(src[end]=='{')-(src[end]=='}');end+=1
 return src[start:end]
funcs=[extract(s) for s in ('void saturn_state::vdp2_get_window0_coordinates(', 'void saturn_state::vdp2_get_window1_coordinates(', 'rgb_t saturn_state::vdp2_back_screen_color(', 'void saturn_state::vdp2_draw_back(')]
if a.mutation in ('w0','w1'):
 index=int(a.mutation[1]);funcs[index]=funcs[index].replace('& (base_mask >> 1)', '& 0x3ffff')
if a.mutation=='back':funcs[-1]=funcs[-1].replace('& ((base_mask << 1) | 1)', '& 0xfffff')
f=extract('static void fixup_window_x(')+'\n'+'\n'.join(funcs)
names=sorted(set(re.findall(r'VDP2_\w+',f)))
code=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
#include "palette.h"
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {
 std::vector<uint32_t> data=std::vector<uint32_t>(8*640,0xdeadbeef);
 uint32_t &pix(int y,int x){assert(y>=0&&y<640&&x>=0&&x<8);return data[y*8+x];}
 void fill(uint32_t c,const rectangle &r){for(int y=r.t;y<=r.b;++y)for(int x=r.l;x<=r.r;++x)pix(y,x)=c;}
};
struct video {bool large=false;unsigned hreso=0,lsmd=0;bool get_vramsz(){return large;}unsigned get_hreso(){return hreso;}unsigned get_lsmd(){return lsmd;}bool get_bdclmd(){return true;}bool get_disp(){return true;}};
struct saturn_state {
 video dev;video *m_vdp2=&dev;
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 struct palette {uint32_t black_pen(){return 0;}} pal;palette *m_palette=&pal;
 struct {// REGS
 } regs;
 void vdp2_compute_color_offset(int*,int*,int*,int){assert(false);}
 // DECLS
};
// MACROS
// FUNCTIONS
// UNDEFS
int main(){saturn_state s;unsigned cases=0;
 // Include high address bits in the data so 512-KiB alias mistakes cannot
 // disappear behind a short-period memory fill.
 for(unsigned i=0;i<0x40000;++i){
  unsigned start=(i*37+(i>>17)*71+(i>>8)*3)%512,end=(i*19+(i>>17)*113+(i>>9)*5)%512;
  s.m_vdp2_vram[i]=(start<<16)|end;
  for(unsigned byte=0;byte<4;++byte)s.m_vdp2_legacy.gfx_decode[i*4+byte]=s.m_vdp2_vram[i]>>(24-byte*8);
 }
 s.regs.VDP2_W0LWE=s.regs.VDP2_W1LWE=1;
 s.regs.VDP2_W0SY=s.regs.VDP2_W1SY=3;s.regs.VDP2_W0EY=s.regs.VDP2_W1EY=479;
 for(bool large:{false,true})for(unsigned hreso=0;hreso<8;++hreso)for(unsigned interlace=0;interlace<4;++interlace)
 for(bool alias:{false,true})for(unsigned tail=0;tail<8;++tail)for(bool per_line:{false,true}){
  s.dev.large=large;s.dev.hreso=hreso;s.dev.lsmd=interlace;
  unsigned bytes=large?1048576:524288,words=bytes/2;
  unsigned base=(tail<4?tail:words-8+tail)^(alias?0x40000:0);
  s.regs.VDP2_BKTA=base;s.regs.VDP2_BKCLMD=per_line;
  s.regs.VDP2_W0LWTA=s.regs.VDP2_W1LWTA=base&~1u;
  bitmap_rgb32 out;
  for(int y=0;y<640;++y){
   unsigned address=((base/2)+unsigned(y)/(interlace==3?2:1))%(bytes/4);
   uint32_t value=s.m_vdp2_vram[address];
   auto convert=[&](unsigned x){return (hreso&6)==0?(x&1022)/2:(hreso&6)==2?x&1023:(hreso&6)==4?x&511:(x&511)*2;};
   for(unsigned window=0;window<2;++window){
    int left=-1,right=-1,top=-1,bottom=-1;
    if(window)s.vdp2_get_window1_coordinates(&left,&right,&top,&bottom,y);
    else s.vdp2_get_window0_coordinates(&left,&right,&top,&bottom,y);
    assert(unsigned(left)==convert(value>>16)&&unsigned(right)==convert(value&65535)&&top==3&&bottom==479);
   }
   s.vdp2_draw_back(out,{1,6,y,y});
   unsigned word=(base+(per_line?unsigned(y)/(interlace==3?2:1):0))%words;
   unsigned pixel=(s.m_vdp2_vram[word/2]>>(word%2?0:16))&65535;
   auto expand=[](unsigned n){n&=31;return (n<<3)|(n>>2);};
   uint32_t expected=0xff000000|(expand(pixel)<<16)|(expand(pixel>>5)<<8)|expand(pixel>>10);
   for(int x=1;x<=6;++x)assert(out.pix(y,x)==expected);
   assert(out.pix(y,0)==0xdeadbeef&&out.pix(y,7)==0xdeadbeef);++cases;
  }
 }
 std::cout<<cases<<" W0/W1/back size/alias/boundary/interlace/partial-row cases passed\n";
}
'''
code=code.replace('// REGS','\n'.join('unsigned '+n+'=0;' for n in names)).replace('// DECLS','\n'.join(f[:f.index('{')].replace('saturn_state::','')+';' for f in funcs)).replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-table-wrap-') as t:
 cpp=Path(t)/'test.cpp';exe=Path(t)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production CRAM read/write and palette rebuild; legal word/longword lanes.

--baseline compiles the prior implementation and must fail. Color expansion is
MAME's current pal5bit convention, not a claim about the physical DAC output.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');a=p.parse_args()
src=(subprocess.check_output(['git','show','c43dded9:src/mame/sega/saturn.cpp'],cwd=ROOT,text=True)
     if a.baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text())
def extract(sig):
    start=src.index(sig);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
functions='\n'.join(extract(s) for s in ('uint32_t saturn_state::vdp2_cram_r(', 'void saturn_state::vdp2_cram_w(', 'void saturn_state::refresh_palette_data('))
code=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
using offs_t=uint32_t;
struct rgb_t {uint32_t v;rgb_t(int r,int g,int b):v((r<<16)|(g<<8)|b){}operator uint32_t()const{return v;}};
int pal5bit(int v){return (v<<3)|(v>>2);}
struct palette {std::array<uint32_t,2048> pens{};
 void set_pen_color(unsigned i,uint32_t c){pens.at(i)=c;}
 void set_pen_color(unsigned i,int r,int g,int b){set_pen_color(i,rgb_t(r,g,b));}
};
struct saturn_state {
 unsigned mode=0;bool dirty=false;std::array<uint32_t,1024> m_vdp2_cram{};
 palette pal;palette *m_palette=&pal;
 void mark_fade_effects_dirty(){dirty=true;}
 uint32_t vdp2_cram_r(offs_t);void vdp2_cram_w(offs_t,uint32_t,uint32_t);void refresh_palette_data();
};
#define VDP2_CRMD mode
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
// FUNCTIONS
uint32_t color555(unsigned v){return rgb_t(pal5bit(v&31),pal5bit((v>>5)&31),pal5bit((v>>10)&31));}
int main(){
 saturn_state s;unsigned cases=0;
 for(unsigned mode : {0,1,2})for(unsigned address=0;address<1024;++address)
 for(uint32_t mask : {0xffff0000u,0x0000ffffu,0xffffffffu}){
  s.mode=mode;
  for(unsigned i=0;i<1024;++i)s.m_vdp2_cram[i]=0x84211234u^(i*0x01010101u);
  auto expected=s.m_vdp2_cram;
  constexpr uint32_t data=0xdead801f;
  expected[address]=(expected[address]&~mask)|(data&mask);
  if(mode==0)expected[address^512]=(expected[address^512]&~mask)|(data&mask);
  s.refresh_palette_data();s.dirty=false;
  s.vdp2_cram_w(address+4096,data,mask);assert(s.dirty);
  assert(s.m_vdp2_cram==expected);
  for(unsigned i=0;i<1024;++i)assert(s.vdp2_cram_r(i+4096)==expected[i]);
  // Compare every displayed pen after rebuilding, independently decoded.
  s.refresh_palette_data();
  for(unsigned pen=0;pen<2048;++pen){
   unsigned v;
   if(mode==2){auto raw=expected[pen&1023];v=uint32_t(rgb_t(raw&255,(raw>>8)&255,(raw>>16)&255));}
   else {unsigned index=mode==0?pen&1023:pen;auto raw=expected[index/2];v=color555(raw>>(index%2?0:16));}
   assert(s.pal.pens[pen]==v);
  }
  // Immediate palette update must agree with a subsequent rebuild at the
  // affected entries, including upper-half mode-0 writes and packed lanes.
  s.vdp2_cram_w(address,~data,mask);auto immediate=s.pal.pens;s.refresh_palette_data();
  assert(s.pal.pens==immediate);
  ++cases;
 }
 // Mode selection alone must not mirror reads or destroy physical half data.
 s.mode=1;s.vdp2_cram_w(0,0x11112222,~0u);s.vdp2_cram_w(512,0x33334444,~0u);
 s.mode=0;assert(s.vdp2_cram_r(0)==0x11112222&&s.vdp2_cram_r(512)==0x33334444);
 s.vdp2_cram_w(512,0xabcd0000,0xffff0000);
 assert(s.vdp2_cram_r(0)==0xabcd2222&&s.vdp2_cram_r(512)==0xabcd4444);
 auto memory=s.m_vdp2_cram;auto pens=s.pal.pens;s.dirty=false;
 s.vdp2_cram_w(0,0,0);assert(!s.dirty&&s.m_vdp2_cram==memory&&s.pal.pens==pens);
 std::cout<<cases<<" CRAM lane/address/palette cases and mode-transition checks passed\n";
}
'''.replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-palette-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

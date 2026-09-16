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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');p.add_argument('--layout-baseline',action='store_true');a=p.parse_args()
src=(subprocess.check_output(['git','show',('77d4b989' if a.layout_baseline else 'c43dded9')+':src/mame/sega/saturn.cpp'],cwd=ROOT,text=True)
     if a.baseline or a.layout_baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text())
def extract(sig):
    text=(ROOT/'src/mame/sega/saturn.cpp').read_text() if sig.startswith('static constexpr') else src
    start=text.index(sig);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
functions='\n'.join(extract(s) for s in ('static constexpr bool vdp2_per_dot_coefficients(', 'uint32_t saturn_state::vdp2_cram_r(', 'void saturn_state::vdp2_cram_w(', 'void saturn_state::refresh_palette_data(', 'uint32_t saturn_state::vdp2_read_rotation_coefficient('))
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
 unsigned mode=0;bool dirty=false;bool coefficient_cram=true;std::array<uint32_t,0x40000> m_vdp2_vram{};std::array<uint32_t,1024> m_vdp2_cram{};
 unsigned ramctl=0;struct video{bool large=false;bool get_vramsz(){return large;}} dev;video *m_vdp2=&dev;
 palette pal;palette *m_palette=&pal;
 void mark_fade_effects_dirty(){dirty=true;}
 uint32_t vdp2_read_rotation_coefficient(uint32_t);uint32_t vdp2_cram_r(offs_t);void vdp2_cram_w(offs_t,uint32_t,uint32_t);void refresh_palette_data();
};
#define VDP2_CRMD mode
#define VDP2_CRKTE coefficient_cram
#define VDP2_RAMCTL ramctl
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
// FUNCTIONS
uint32_t color555(unsigned v){return rgb_t(pal5bit(v&31),pal5bit((v>>5)&31),pal5bit((v>>10)&31));}
uint32_t cpu_read(const std::array<uint32_t,1024>& words,unsigned address,unsigned mode){
 if(mode<2)return words[address];
 auto half=[&](unsigned bank){unsigned i=bank*512+address/2;return (words[i]>>(address%2?0:16))&65535;};
 return (half(0)<<16)|half(1);
}
int main(){
 saturn_state s;unsigned cases=0;
 for(unsigned mode : {0,1,2})for(unsigned address=0;address<1024;++address)
 for(uint32_t mask : {0xffff0000u,0x0000ffffu,0xffffffffu}){
  s.mode=mode;
  for(unsigned i=0;i<1024;++i)s.m_vdp2_cram[i]=0x84211234u^(i*0x01010101u);
  auto expected=s.m_vdp2_cram;
  constexpr uint32_t data=0xdead801f;
  if(mode==2){
   for(unsigned bank=0;bank<2;++bank){
    unsigned i=bank*512+address/2,shift=address%2?0:16;
    uint32_t lane_mask=((mask>>(bank?0:16))&65535)<<shift;
    uint32_t lane_data=((data>>(bank?0:16))&65535)<<shift;
    expected[i]=(expected[i]&~lane_mask)|(lane_data&lane_mask);
   }
  }else expected[address]=(expected[address]&~mask)|(data&mask);
  if(mode==0)expected[address^512]=(expected[address^512]&~mask)|(data&mask);
  s.refresh_palette_data();s.dirty=false;
  s.vdp2_cram_w(address+4096,data,mask);assert(s.dirty);
  assert(s.m_vdp2_cram==expected);
  for(unsigned i=0;i<1024;++i)assert(s.vdp2_cram_r(i+4096)==cpu_read(expected,i,mode));
  // Compare every displayed pen after rebuilding, independently decoded.
  s.refresh_palette_data();
  for(unsigned pen=0;pen<2048;++pen){
   unsigned v;
   if(mode==2){auto raw=cpu_read(expected,pen&1023,mode);v=uint32_t(rgb_t(raw&255,(raw>>8)&255,(raw>>16)&255));}
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
 // Mode changes reinterpret addresses without moving or rewriting memory.
 auto physical=s.m_vdp2_cram;
 for(unsigned mode : {1,2,0,2,1}){
  s.mode=mode;s.refresh_palette_data();assert(s.m_vdp2_cram==physical);
  for(unsigned i=0;i<1024;++i)assert(s.vdp2_cram_r(i)==cpu_read(physical,i,mode));
 }
 // CRKTE is legal with mode 1: coefficient reads use the physical upper bank.
 s.mode=1;
 for(unsigned a=0;a<8192;a+=4)assert(s.vdp2_read_rotation_coefficient(a)==physical[((a|0x800)&0xfff)/4]);

 unsigned bank_cases=0;
 for(unsigned i=0;i<s.m_vdp2_vram.size();++i)s.m_vdp2_vram[i]=i*37+0x14283561;
 for(bool cram:{false,true})for(bool large:{false,true})for(unsigned ctl=0;ctl<1024;++ctl){
  s.coefficient_cram=cram;s.ramctl=ctl|(cram?0x8000:0);s.dev.large=large;
  bool per_dot=cram;unsigned permissions[4];
  for(unsigned bank=0;bank<4;++bank){unsigned used=(ctl&(bank<2?256:512))?bank:(bank/2)*2;permissions[bank]=(ctl>>(used*2))&3;per_dot|=permissions[bank]==1;}
  assert(vdp2_per_dot_coefficients(s.ramctl)==per_dot);
  for(unsigned a:{0u,0x1fffeu,0x20000u,0x3fffeu,0x40000u,0x60000u,0x7fffeu,0x80000u,0xffffeu,0xfffffffeu}){
   unsigned physical=a%(large?0x100000:0x80000),bank=physical/(large?0x40000:0x20000);
   uint32_t expected=cram?s.m_vdp2_cram[((a|0x800)&4095)/4]:(per_dot&&permissions[bank]!=1?0x80008000:s.m_vdp2_vram[physical/4]);
   assert(s.vdp2_read_rotation_coefficient(a)==expected);++bank_cases;
  }
 }
 std::cout<<bank_cases<<" partitioned coefficient-bank/CRAM fetch cases passed\n";
 auto memory=s.m_vdp2_cram;auto pens=s.pal.pens;s.dirty=false;
 s.vdp2_cram_w(0,0,0);assert(!s.dirty&&s.m_vdp2_cram==memory&&s.pal.pens==pens);
 std::cout<<cases<<" CRAM lane/address/palette cases and mode-transition checks passed\n";
}
'''.replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-palette-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

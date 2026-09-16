#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production RBG0/RBG1 window-control selection, with fixed rectangle inputs."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',action='store_true');a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(sig):
 start=src.index(sig);end=src.index('{',start)+1;depth=1
 while depth:
  depth+=(src[end]=='{')-(src[end]=='}');end+=1
 return src[start:end]
funcs=[extract('inline bool saturn_state::vdp2_roz_window('),extract('inline int saturn_state::get_roz_window_pixel('),extract('inline bool saturn_state::vdp2_roz_mode3_window(')]
f='\n'.join(funcs)
if a.mutation:f=f.replace('layer_name == 0x81', 'layer_name == 0x82')
names=sorted(set(re.findall(r'VDP2_\w+',f)))
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
struct saturn_state {
 struct {int layer_name=0;} current_tilemap;
 struct {// REGS
 } regs;
 int m_roz_win_s_x[2]{3,7},m_roz_win_e_x[2]{11,14};
 int m_roz_win_s_y[2]{2,1},m_roz_win_e_y[2]{5,4};
 bool vdp2_sprite_window(int x,int y){return (x+2*y)%3==0;}
 void vdp2_roz_window_prepare(int){}
 // DECLS
};
// MACROS
// FUNCTIONS
// UNDEFS
int main(){saturn_state s;unsigned cases=0;
 for(unsigned n0=0;n0<128;++n0)for(unsigned r0=0;r0<128;++r0)for(bool rbg1:{false,true}){
  s.current_tilemap.layer_name=rbg1?0x81:0x80;
  // SETUP
  unsigned cfg=rbg1?n0:r0;
  for(int y=0;y<8;++y)for(int x=0;x<16;++x){
   bool expected=!(cfg&16);
   bool in[]={x>=3&&x<=11&&y>=2&&y<=5,x>=7&&x<=14&&y>=1&&y<=4,(x+2*y)%3==0};
   for(unsigned w=0;w<2;++w)if(cfg&(1u<<w)){
    bool keep=(cfg&(4u<<w))?in[w]:!in[w];
    expected=(cfg&16)?expected||keep:expected&&keep;
   }
   if(cfg&32){bool keep=(cfg&64)?in[2]:!in[2];expected=(cfg&16)?expected||keep:expected&&keep;}
   assert(s.vdp2_roz_window(x,y)==expected);++cases;
  }
 }

 unsigned parameter_cases=0;
 for(unsigned cfg=0;cfg<128;++cfg){
  s.regs.VDP2_RPW0E=cfg&1;s.regs.VDP2_RPW1E=(cfg>>1)&1;s.regs.VDP2_RPW0A=(cfg>>2)&1;s.regs.VDP2_RPW1A=(cfg>>3)&1;
  s.regs.VDP2_RPLOG=(cfg>>4)&1;s.regs.VDP2_RPSWE=(cfg>>5)&1;s.regs.VDP2_RPSWA=(cfg>>6)&1;
  for(int y=0;y<8;++y)for(int x=0;x<16;++x){
   bool inside[]={x>=3&&x<=11&&y>=2&&y<=5,x>=7&&x<=14&&y>=1&&y<=4,(x+2*y)%3==0};
   bool expected=!(cfg&16);
   for(int w=0;w<3;++w){unsigned enable=w==2?32:1u<<w,area=w==2?64:4u<<w;if(cfg&enable){bool keep=bool(cfg&area)==inside[w];expected=(cfg&16)?expected||keep:expected&&keep;}}
   assert(s.vdp2_roz_mode3_window(x,y,0)==expected);assert(s.vdp2_roz_mode3_window(x,y,1)!=expected);++parameter_cases;
  }
 }
 std::cout<<parameter_cases<<" W0/W1/sprite-window A/B selection pixels passed\n";
 std::cout<<cases<<" RBG0/RBG1 window-control selection pixels passed\n";
}
'''
setup=[]
for prefix,cfg in [('N0','n0'),('R0','r0')]:
 for suffix,expr in [('W0E',f'{cfg}&1'),('W1E',f'({cfg}>>1)&1'),('W0A',f'({cfg}>>2)&1'),('W1A',f'({cfg}>>3)&1'),('LOG',f'({cfg}>>4)&1'),('SWE',f'({cfg}>>5)&1'),('SWA',f'({cfg}>>6)&1')]:setup.append(f's.regs.VDP2_{prefix}{suffix}={expr};')
code=code.replace('// REGS','\n'.join('int '+n+'=0;' for n in names)).replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','')+';' for x in funcs)).replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names)).replace('// SETUP','\n'.join(setup))
with tempfile.TemporaryDirectory(prefix='saturn-rotation-windows-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

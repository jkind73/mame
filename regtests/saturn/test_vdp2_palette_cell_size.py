#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production palette-cell source selection and wrapping, with recording decoder.

Validates source dots and decoder routing, not full rendered images or bus timing.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('size','tail','stale'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(sig):
 start=src.index(sig);end=src.index('{',start)+1;depth=1
 while depth:
  depth+=(src[end]=='{')-(src[end]=='}');end+=1
 return src[start:end]
f=extract('const uint8_t *saturn_state::vdp2_get_palette_cell(')
if a.mutation=='size':f=f.replace('? 0xfffff : 0x7ffff','? 0xfffff : 0xfffff')
if a.mutation=='tail':f=f.replace('code == (mask >> 5)','code > (mask >> 5)')
if a.mutation=='stale':f=f.replace('(code * 32 + i) & mask','(code * 32 + (i % 32)) & mask')
# Retained consumers all route through this helper; normalize before pen usage.
for name in ('vdp2_drawgfxzoom','vdp2_drawgfx_alpha','vdp2_drawgfx_transpen'):
 body=extract('void saturn_state::'+name+'(')
 assert 'vdp2_get_palette_cell(gfx, code, wrapped)' in body
 assert 'gfx->get_data(' not in body
 assert 'code &= m_vdp2->get_vramsz() ? 0x7fff : 0x3fff;' in body
 if name=='vdp2_drawgfxzoom':assert body.index('code &=')<body.index('gfx->pen_usage(code)')
assert 'if (tilecode == 0x7fff)' not in extract('void saturn_state::vdp2_draw_basic_tilemap(')
code=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
struct gfx_element {
 unsigned depth=4,capacity=0,calls=0,last=0;uint8_t *raw=nullptr;std::array<uint8_t,64> dots;
 unsigned granularity(){return 1u<<depth;}unsigned elements(){return 32768;}
 const uint8_t *get_data(unsigned code){
  ++calls;last=code;assert(code*32+depth*8<=capacity);
  for(unsigned i=0;i<64;++i)dots[i]=depth==8?raw[code*32+i]:(raw[code*32+i/2]>>(i%2?0:4))&15;
  return dots.data();
 }
};
struct saturn_state {
 struct video {bool large=false;bool get_vramsz(){return large;}} dev;video *m_vdp2=&dev;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(1048576);} m_vdp2_legacy;
 const uint8_t *vdp2_get_palette_cell(gfx_element*,uint32_t,uint8_t (&)[64]);
};
// FUNCTION
int main(){saturn_state s;gfx_element gfx;gfx.raw=s.m_vdp2_legacy.gfx_decode.get();unsigned cases=0;
 for(unsigned i=0;i<1048576;++i)gfx.raw[i]=(i*37+(i>>5)*17+(i>>19)*103)^(i>>8);
 for(bool large:{false,true})for(unsigned depth:{4u,8u})for(unsigned code=0;code<65536;++code){
  s.dev.large=large;gfx.depth=depth;gfx.capacity=large?1048576:524288;gfx.calls=0;
  unsigned physical=code%(gfx.capacity/32);bool wraps=depth==8&&physical==gfx.capacity/32-1;
  uint8_t scratch[64];const uint8_t *data=s.vdp2_get_palette_cell(&gfx,code,scratch);
  assert(gfx.calls==unsigned(!wraps));if(!wraps)assert(gfx.last==physical);
  assert((data==scratch)==wraps);
  for(unsigned dot=0;dot<64;++dot){unsigned address=(physical*32+(depth==8?dot:dot/2))%gfx.capacity;
   unsigned expected=depth==8?gfx.raw[address]:(gfx.raw[address]>>(dot%2?0:4))&15;
   assert(data[dot]==expected);
  }
  if(wraps){
   // Wrapped low-memory changes must be visible without a decoder-cache hit.
   gfx.raw[0]^=0xa5;gfx.raw[31]^=0x71;
   data=s.vdp2_get_palette_cell(&gfx,code,scratch);
   assert(data[32]==gfx.raw[0]&&data[63]==gfx.raw[31]&&!gfx.calls);
   gfx.raw[0]^=0xa5;gfx.raw[31]^=0x71;
  }
  ++cases;
 }
 std::cout<<cases<<" palette-cell capacity/alias/dot/decode-routing configurations passed\n";
}
'''
code=code.replace('// FUNCTION',f)
with tempfile.TemporaryDirectory(prefix='saturn-palette-cell-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

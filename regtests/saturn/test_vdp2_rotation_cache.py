#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute production character-cache range setup and VRAM-write invalidation.

Graphics decoder dirtiness is recorded by a no-op; no raster bus timing model.
"""
import argparse
import os
from pathlib import Path
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
start=src.index('    // Character numbers are 32-byte units, not character lengths.')
end=src.index('\n  }\n}',start)
setup=src[start:end]
if a.mutation:setup=setup.replace('(tilecodemax * 0x20 + character_bytes) / 4', '(tilecodemax + 1) * 8 + character_bytes * 0')
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
using offs_t=uint32_t;
struct gfx {void mark_dirty(unsigned){}};
struct decoder {struct gfx *gfx(int){static struct gfx g;return &g;}};
struct video {void preserve_scanned_output(){}bool size=false;bool get_vramsz(){return size;}};
struct saturn_state {
 struct {unsigned colour_depth=0,tile_size=0;} current_tilemap;
 struct {unsigned tile_offset_min=0,tile_offset_max=0;} vdp2_layer_data;
 struct {unsigned watch_vdp2_vram_writes=0,is_cache_dirty=0,map_offset_min[2]{},map_offset_max[2]{},tile_offset_min[2]{},tile_offset_max[2]{};} RBG0_cache_data;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 decoder dec;decoder *m_gfxdecode=&dec;video vid;video *m_vdp2=&vid;
 void setup(unsigned tilecodemin,unsigned tilecodemax){
 // SETUP
 }
 void vdp2_vram_w(offs_t,uint32_t,uint32_t);
};
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define VDP2_RBG_ROTATION_PARAMETER_A 1
#define VDP2_RBG_ROTATION_PARAMETER_B 2
#define LOGMASKED(...) ((void)0)
// FUNCTION
int main(){saturn_state s;unsigned cases=0;
 unsigned bytes[]={32,64,128,128,256};
 for(unsigned depth=0;depth<5;++depth)for(unsigned large:{0u,1u})for(bool size:{false,true})
 for(unsigned code:{0u,3u,0x3ff0u,0x3fffu,0x7fffu})for(unsigned parameter:{0u,1u}){
  s.vid.size=size;unsigned memory=size?0x100000:0x80000;code&=memory/32-1;
  s.current_tilemap.colour_depth=depth;s.current_tilemap.tile_size=large;s.setup(code,code);
  auto &d=s.vdp2_layer_data;unsigned count=bytes[depth]*(large?4:1);
  bool wraps=code*32+count>memory;
  assert(d.tile_offset_min==(wraps?0:code*8));
  assert(d.tile_offset_max==(wraps?0x40000u:(code*32+count)/4));
  for(unsigned byte=0;byte<count;byte+=4){
   auto &c=s.RBG0_cache_data;c={};c.watch_vdp2_vram_writes=3;
   c.tile_offset_min[parameter]=d.tile_offset_min;c.tile_offset_max[parameter]=d.tile_offset_max;
   s.vdp2_vram_w(((code*32+byte)%memory)/4,0x12345678,0xffffffff);
   assert(c.is_cache_dirty==(1u<<parameter));assert(c.watch_vdp2_vram_writes==(3u^(1u<<parameter)));++cases;
  }
 }
 std::cout<<cases<<" character-tail/wrapped VRAM invalidation writes passed\n";
}
'''
code=code.replace('// SETUP',setup).replace('// FUNCTION',extract('void saturn_state::vdp2_vram_w('))
with tempfile.TemporaryDirectory(prefix='saturn-rotation-cache-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

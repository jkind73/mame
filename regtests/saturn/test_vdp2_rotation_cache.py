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
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',action='store_true');p.add_argument('--bitmap-mutation',choices=('range','names'));a=p.parse_args()
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
bitmap=extract('void saturn_state::vdp2_draw_basic_bitmap(')
bitmap=bitmap[bitmap.index('{'):bitmap.index('  /* new bitmap code')]+"}"
if a.bitmap_mutation=='range':bitmap=bitmap.replace('unsigned const bytes = (width * height / 2) << shift;', 'unsigned const bytes = ((width * height / 2) << shift) / 2;')
if a.bitmap_mutation=='names':bitmap=bitmap.replace('vdp2_layer_data.map_offset_min = vdp2_layer_data.map_offset_max = 0;', '(void)0;')
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
 struct {unsigned colour_depth=0,tile_size=0,enabled=1,layer_name=0x80,bitmap_size=0,bitmap_map=0;} current_tilemap;
 struct {unsigned tile_offset_min=0,tile_offset_max=0,map_offset_min=0,map_offset_max=0;} vdp2_layer_data;
 struct {unsigned watch_vdp2_vram_writes=0,is_cache_dirty=0,map_offset_min[2]{},map_offset_max[2]{},tile_offset_min[2]{},tile_offset_max[2]{};} RBG0_cache_data;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 decoder dec;decoder *m_gfxdecode=&dec;video vid;video *m_vdp2=&vid;
 void setup(unsigned tilecodemin,unsigned tilecodemax){
 // SETUP
 }
 void setup_bitmap() // BITMAP
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
 unsigned bitmap_cases=0;
 constexpr unsigned bits[]={4,8,16,16,32};
 for(unsigned depth=0;depth<5;++depth)for(unsigned size=0;size<4;++size)for(unsigned map=0;map<8;++map)
 for(bool large:{false,true})for(unsigned parameter:{0u,1u}){
  s.vid.size=large;auto &t=s.current_tilemap;t.enabled=1;t.layer_name=0x80+parameter;t.bitmap_size=size;t.bitmap_map=map;t.colour_depth=depth;
  s.vdp2_layer_data={17,29,31,43};s.setup_bitmap();auto d=s.vdp2_layer_data;
  unsigned memory=large?1048576:524288,width=size&2?1024:512,height=size&1?512:256;
  unsigned length=width*height*bits[depth]/8,start=map*131072%memory;
  bool wraps=length>=memory||start+length>memory;
  unsigned low=wraps?0:start/4,high=wraps?memory/4:(start+length)/4;
  assert(!d.map_offset_min&&!d.map_offset_max&&d.tile_offset_min==low&&d.tile_offset_max==high);
  for(unsigned address:{0u,start/4,(start+length-4)%memory/4,memory/4-1,low?low-1:0,low,high-1,high%unsigned(memory/4)}){
   auto &c=s.RBG0_cache_data;c={};c.watch_vdp2_vram_writes=3;
   c.tile_offset_min[parameter]=d.tile_offset_min;c.tile_offset_max[parameter]=d.tile_offset_max;
   c.map_offset_min[parameter]=d.map_offset_min;c.map_offset_max[parameter]=d.map_offset_max;
   s.vdp2_vram_w(address,0xabc12345,0xffffffff);
   unsigned dirty=address>=low&&address<high?1u<<parameter:0;
   assert(c.is_cache_dirty==dirty&&c.watch_vdp2_vram_writes==(3u^dirty));++bitmap_cases;
  }
  // Ordinary/disabled bitmap draws must not replace cache-watch metadata.
  t.layer_name=0;s.vdp2_layer_data={17,29,31,43};s.setup_bitmap();assert(s.vdp2_layer_data.tile_offset_min==17&&s.vdp2_layer_data.map_offset_min==31);
  t.layer_name=0x80;t.enabled=0;s.setup_bitmap();assert(s.vdp2_layer_data.tile_offset_max==29&&s.vdp2_layer_data.map_offset_max==43);
 }
 std::cout<<bitmap_cases<<" bitmap source-range/rotation-parameter invalidation probes passed\n";

}
'''
code=code.replace('// BITMAP',bitmap).replace('// SETUP',setup).replace('// FUNCTION',extract('void saturn_state::vdp2_vram_w('))
with tempfile.TemporaryDirectory(prefix='saturn-rotation-cache-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute production legacy map-base, name-fetch and cache-range arithmetic.

Geometry inputs and memory are controlled; this is not a full tile renderer or
character-pixel/fetch-timing qualification.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation',choices=('base','fetch','watch'))
a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
src=src[src.index('void saturn_state::vdp2_draw_basic_tilemap('):src.index('void saturn_state::vdp2_check_tilemap_with_linescroll(')]
base=src[src.index('  /* Precalculate bases'):src.index('  /* other bits */')]
watch=src[src.index('    // store map information'):src.index('    // Character numbers')]
fetch=re.findall(r'data = (m_vdp2_vram\[[^\n]+\]);',src)
assert len(fetch)==2
if a.mutation=='base':base=base.replace('base[i] &= vram_mask;', 'base[i] &= (vram_mask & 0x7ffff);')
if a.mutation=='fetch':fetch=[s.replace('& (vram_mask >> 2)', '& 0x3ffff') for s in fetch]
if a.mutation=='watch':watch=watch.replace('vdp2_layer_data.map_offset_max = max_base;', 'vdp2_layer_data.map_offset_max = max_base + plsize_bytes / 4;')
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
struct memory {unsigned address=0;uint32_t operator[](unsigned n){assert(n<0x40000);address=n;return n*37+123;}};
struct state {
 struct {unsigned pattern_data_size=0,tile_size=0,plane_size=0,map_count=0,map_offset[16]{};} current_tilemap;
 struct {unsigned map_offset_min=0,map_offset_max=0;} vdp2_layer_data;
 unsigned vram_mask=0,plsize_bytes=0;int base[16]{};memory m_vdp2_vram;
 void setup(){unsigned i;
 // BASE
 // WATCH
 }
 uint32_t read(unsigned newbase,unsigned offs){return current_tilemap.pattern_data_size? /* ONE */ : /* TWO */;}
};
int main(){state s;unsigned maps=0,reads=0;
 for(bool large:{false,true})for(unsigned names:{0u,1u})for(unsigned tile:{0u,1u})for(unsigned plane:{0u,1u,3u})
 for(unsigned count:{4u,16u})for(unsigned reg=0;reg<512;++reg){
  auto &t=s.current_tilemap;t.pattern_data_size=names;t.tile_size=tile;t.plane_size=plane;t.map_count=count;
  unsigned capacity=large?1048576:524288,side=tile?32:64,entry=names?2:4,pages=plane==3?4:plane==1?2:1;
  unsigned page_bytes=side*side*entry;s.plsize_bytes=page_bytes*pages;s.vram_mask=capacity-1;
  unsigned low=capacity/4,high=0;
  for(unsigned i=0;i<count;++i)t.map_offset[i]=(reg+i*71)%512;
  s.vdp2_layer_data={17,29};s.setup();
  for(unsigned i=0;i<count;++i){
   // A map number selects page-sized units, with low plane-select bits
   // ignored. Page count, not the production shift table, supplies alignment.
   unsigned expected=((t.map_offset[i]*page_bytes)/(page_bytes*pages)*(page_bytes*pages))%capacity;
   assert(unsigned(s.base[i])==expected/4);low=std::min(low,expected/4);high=std::max(high,(expected+s.plsize_bytes)/4);
   for(unsigned page=0;page<pages;++page)for(unsigned cell:{0u,1u,side-1,side,side*side-2,side*side-1}){
    unsigned newbase=s.base[i]+page*page_bytes/4;
    unsigned address=(expected+page*page_bytes+cell*entry)%capacity/4;
    uint32_t value=s.read(newbase,cell);assert(s.m_vdp2_vram.address==address&&value==address*37+123);++reads;
   }
  }
  assert(s.vdp2_layer_data.map_offset_min==low&&s.vdp2_layer_data.map_offset_max==high);++maps;
 }
 // Final-index masking is defensive for arbitrary accumulated offsets too;
 // legal aligned planes above do not themselves straddle physical memory.
 for(unsigned capacity:{524288u,1048576u})for(unsigned names:{0u,1u})for(unsigned tail=0;tail<8;++tail)for(unsigned offset=0;offset<64;++offset){
  s.vram_mask=capacity-1;s.current_tilemap.pattern_data_size=names;
  unsigned base=capacity/4-1-tail;
  s.read(base,offset);
  assert(s.m_vdp2_vram.address==(base+offset/(names?2:1))%(capacity/4));++reads;
 }
 std::cout<<maps<<" legacy map-base/watch configurations and "<<reads<<" name-fetch probes passed\n";
}
'''
code=code.replace('// BASE',base).replace('// WATCH',watch).replace('/* ONE */',fetch[0]).replace('/* TWO */',fetch[1])
with tempfile.TemporaryDirectory(prefix='saturn-cell-map-size-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

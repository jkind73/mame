#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production CPU VRAM handlers: aliases, masks, decode/cache coherence and ordering.

Recording decode/screen stages, not a CPU bus, fetch-slot or linked-game model.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation', choices=('read', 'write'))
a = p.parse_args()
src = (ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(sig):
    start = src.index(sig); end = src.index('{', start)+1; depth = 1
    while depth:
        depth += (src[end]=='{')-(src[end]=='}'); end += 1
    return src[start:end]
# Preserve the high aperture bit until the size-aware handler sees it.
for filename in ('sat_console.cpp', 'stv.cpp'):
    driver = (ROOT/'src/mame/sega'/filename).read_text()
    start = driver.index('map(0x05e00000,')
    mapping = driver[start:driver.index('map(0x05f00000,', start)]
    assert '0x05efffff' in mapping and '.mirror(' not in mapping
funcs = [extract('uint32_t saturn_state::vdp2_vram_r('), extract('void saturn_state::vdp2_vram_w(')]
if a.mutation:
    index = 0 if a.mutation == 'read' else 1
    funcs[index] = funcs[index].replace('offset &= m_vdp2->get_vramsz() ? 0x3ffff : 0x1ffff;', '')
code = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <vector>
using offs_t=uint32_t;
struct graphics {std::vector<unsigned> dirty;void mark_dirty(unsigned n){dirty.push_back(n);}};
struct decoder {graphics g[4];graphics *gfx(unsigned n){return &g[n];}};
struct video {
 bool large=false;unsigned preserved=0;std::function<void()> observe;
 bool get_vramsz(){return large;}void preserve_scanned_output(){++preserved;observe();}
};
struct saturn_state {
 video dev;video *m_vdp2=&dev;decoder dec;decoder *m_gfxdecode=&dec;
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 struct {unsigned watch_vdp2_vram_writes=0,is_cache_dirty=0,map_offset_min[2]{},map_offset_max[2]{},tile_offset_min[2]{},tile_offset_max[2]{};} RBG0_cache_data;
 uint32_t vdp2_vram_r(offs_t);
 void vdp2_vram_w(offs_t,uint32_t,uint32_t);
};
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define VDP2_RBG_ROTATION_PARAMETER_A 1
#define VDP2_RBG_ROTATION_PARAMETER_B 2
#define LOGMASKED(...) ((void)0)
// FUNCTIONS
int main(){saturn_state s;unsigned cases=0;
 for(bool large:{false,true})for(unsigned address:{0u,1u,7u,8u,0x1fffeu,0x1ffffu,0x20000u,0x20001u,0x3ffffu})
 for(unsigned mask:{0u,0xff000000u,0x00ff0000u,0x0000ff00u,0x000000ffu,0xffff0000u,0x0000ffffu,0xffffffffu,0x55aa55aau})
 for(unsigned data:{0x12345678u,0xa5c3e719u})for(unsigned parameter:{0u,1u})for(bool names:{false,true}){
  s.dev.large=large;s.dev.preserved=0;
  unsigned capacity=large?262144:131072,physical=address%capacity;
  unsigned other=physical^0x20000,old=0x12345678,poison=0xdeadc0de;
  s.m_vdp2_vram[physical]=old;s.m_vdp2_vram[other]=poison;
  for(unsigned b=0;b<4;++b){s.m_vdp2_legacy.gfx_decode[physical*4+b]=old>>(24-b*8);s.m_vdp2_legacy.gfx_decode[other*4+b]=poison>>(24-b*8);}
  assert(s.vdp2_vram_r(address)==old);
  auto &c=s.RBG0_cache_data;c={};c.watch_vdp2_vram_writes=3;
  (names?c.map_offset_min:c.tile_offset_min)[parameter]=physical;
  (names?c.map_offset_max:c.tile_offset_max)[parameter]=physical+1;
  (names?c.map_offset_min:c.tile_offset_min)[1-parameter]=other;
  (names?c.map_offset_max:c.tile_offset_max)[1-parameter]=other+1;
  for(auto &g:s.dec.g)g.dirty.clear();
  s.dev.observe=[&]{
   assert(s.m_vdp2_vram[physical]==old&&c.is_cache_dirty==0);
   for(unsigned b=0;b<4;++b)assert(s.m_vdp2_legacy.gfx_decode[physical*4+b]==uint8_t(old>>(24-b*8)));
   for(auto &g:s.dec.g)assert(g.dirty.empty());
  };
  s.vdp2_vram_w(address,data,mask);
  unsigned expected=(old&~mask)|(data&mask);
  assert(s.dev.preserved==unsigned(expected!=old));
  assert(s.vdp2_vram_r(address)==expected&&s.m_vdp2_vram[physical]==expected&&s.m_vdp2_vram[other]==poison);
  assert(c.is_cache_dirty==(1u<<parameter)&&c.watch_vdp2_vram_writes==(3u^(1u<<parameter)));
  for(unsigned b=0;b<4;++b){
   assert(s.m_vdp2_legacy.gfx_decode[physical*4+b]==uint8_t(expected>>(24-b*8)));
   assert(s.m_vdp2_legacy.gfx_decode[other*4+b]==uint8_t(poison>>(24-b*8)));
  }
  for(unsigned g=0;g<4;++g){std::vector<unsigned> indices{physical/8};if(g>=2&&physical/8)indices.push_back(physical/8-1);assert(s.dec.g[g].dirty==indices);}
  ++cases;
 }
 std::cout<<cases<<" CPU VRAM alias/masked-write/decode/watch/old-state-order cases passed\n";
}
'''
code = code.replace('// FUNCTIONS', '\n'.join(funcs))
with tempfile.TemporaryDirectory(prefix='saturn-vram-access-') as d:
    cpp=Path(d)/'test.cpp'; exe=Path(d)/'test'; cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','c++'), '-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

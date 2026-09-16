#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production VDP2 startup fields and postload cache/state separation.

Runs actual reconstruction with recording graphics/palette devices. Not a linked
MAME save-manager, timer or screen-buffer replay test.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('capture','priority','decode','window'));a=p.parse_args()
source=(ROOT/'src/mame/sega/saturn.cpp').read_text();header=(ROOT/'src/mame/sega/saturn.h').read_text();device=(ROOT/'src/mame/sega/saturn_vdp2.h').read_text()
def extract(src,sig):
 start=src.index(sig);end=src.index('{',start)+1;depth=1
 while depth:
  depth+=(src[end]=='{')-(src[end]=='}');end+=1
 return src[start:end]
f=extract(source,'void saturn_state::vdp2_state_save_postload(')
if a.mutation=='capture':f=f.replace('m_vdp2_gradation_capture = false;', 'm_vdp2_gradation_capture = true;')
if a.mutation=='priority':f=f.replace('m_vdp2_priority_pass = -1;', 'm_vdp2_priority_pass = 3;')
if a.mutation=='decode':f=f.replace('(data & 0xff000000) >> 24', '(data & 0x00ff0000) >> 16')
if a.mutation=='window':f=f.replace('vdp2_window_cache_invalidate();', '(void)0;')
fields=device[device.index('  u16 m_tvmd'):device.index('  TIMER_CALLBACK_MEMBER(sync_timer_cb)')]
code=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <new>
#include <vector>
using u8=uint8_t;using u16=uint16_t;
struct startup {
 // FIELDS
};
struct saturn_state {
 bool m_vdp2_composition_active=true,m_vdp2_extended_active=true,m_vdp2_gradation_active=true,m_vdp2_gradation_capture=true;
 unsigned m_vdp2_gradation_layer=0;int m_vdp2_priority_pass=3;
 int m_window_cache_y=9,m_roz_window_cache_y=11,m_sprite_window_y=13;
 bool m_rotation_latch_valid=true;std::array<bool,8> m_rotation_line_valid{};
 std::array<int32_t,6> m_rotation_saved{};
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 struct graphics {unsigned dirtied=0;void mark_dirty(unsigned offset){assert(offset<0x8000);++dirtied;}};
 struct decoder {graphics items[4];graphics *gfx(unsigned n){return &items[n];}} dec;decoder *m_gfxdecode=&dec;
 struct _RBG0_cache_data {unsigned is_cache_dirty=0,watch=0;};_RBG0_cache_data RBG0_cache_data;
 struct _vdp2_layer_data {unsigned offset=0;};_vdp2_layer_data vdp2_layer_data;
 unsigned palettes=0;void refresh_palette_data(){++palettes;}
 // INVALIDATE
 void vdp2_state_save_postload();
};
// FUNCTION
int main(){
 for(unsigned poison:{0u,85u,170u,255u}){
  alignas(startup) unsigned char memory[sizeof(startup)];std::memset(memory,poison,sizeof(memory));
  auto *s=new(memory) startup;
  assert(s->m_tvmd==0&&s->m_old_tvmd==65535&&s->m_odd_bit);
  assert(!s->m_disp&&!s->m_bdclmd&&!s->m_lsmd&&!s->m_vreso&&!s->m_hreso);
  assert(!s->m_exten&&!s->m_exlten&&!s->m_exsyen&&!s->m_dasel&&!s->m_exbgen);
  assert(!s->m_hcounter_latch&&!s->m_vcounter_latch&&!s->m_exltfg&&!s->m_exsyfg);
  assert(!s->m_hdisplay&&!s->m_vdisplay&&!s->m_vramsz);
  s->~startup();
 }
 for(unsigned seed=0;seed<32;++seed){
  auto ptr=std::make_unique<saturn_state>();auto &s=*ptr;
  for(unsigned i=0;i<s.m_vdp2_vram.size();++i)s.m_vdp2_vram[i]=(i*0x193725u)^(seed*0x31abcd17u);
  for(unsigned i=0;i<8;++i)s.m_rotation_line_valid[i]=(seed>>i)&1;
  for(unsigned i=0;i<6;++i)s.m_rotation_saved[i]=int32_t((seed+1)*0x137abcd1u+i*997);
  auto saved=s.m_rotation_saved;auto valid=s.m_rotation_line_valid;auto ram=s.m_vdp2_vram;
  s.RBG0_cache_data={1,3};s.vdp2_layer_data.offset=0x1234;
  for(unsigned repeat=0;repeat<2;++repeat){
   s.vdp2_state_save_postload();
   assert(!s.m_vdp2_composition_active&&!s.m_vdp2_extended_active&&!s.m_vdp2_gradation_active&&!s.m_vdp2_gradation_capture);
   assert(s.m_vdp2_priority_pass==-1&&s.m_vdp2_gradation_layer==7);
   assert(s.m_window_cache_y==-1&&s.m_roz_window_cache_y==-1&&s.m_sprite_window_y==-1);
   assert(s.m_rotation_latch_valid&&s.m_rotation_saved==saved&&s.m_rotation_line_valid==valid&&s.m_vdp2_vram==ram);
   assert(s.RBG0_cache_data.is_cache_dirty==3&&!s.RBG0_cache_data.watch&&!s.vdp2_layer_data.offset);
   assert(s.palettes==repeat+1);
   for(unsigned address=0;address<0x100000;++address)assert(s.m_vdp2_legacy.gfx_decode[address]==((ram[address/4]>>(24-8*(address%4)))&255));
   for(unsigned n=0;n<4;++n)assert(s.dec.items[n].dirtied==(repeat+1)*(0x40000u+(n>=2?0x40000u-8:0)));
  }
 }
 std::cout<<"4 poisoned-startup and 64 full-VRAM postload/cache/rotation-history scenarios passed\n";
}
'''
code=code.replace('// FIELDS',fields).replace('// INVALIDATE',extract(header,'void vdp2_window_cache_invalidate()')).replace('// FUNCTION',f)
with tempfile.TemporaryDirectory(prefix='saturn-postload-') as t:
 cpp=Path(t)/'test.cpp';exe=Path(t)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

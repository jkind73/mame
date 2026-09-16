#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production write ordering and completed-line preservation, not fetch-slot timing.

The recording screen models MAME's monotonic partial-update coalescing; actual
save-manager, physical beam and linked renderer acceptance remain separate.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('late','current-line','missing'));args=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text();dev=(ROOT/'src/mame/sega/saturn_vdp2.cpp').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
funcs=[extract(src,s) for s in ('void saturn_state::vdp2_vram_w(', 'uint32_t saturn_state::vdp2_cram_r(', 'void saturn_state::vdp2_cram_w(', 'void saturn_state::vdp2_regs_w(')]
f=extract(dev,'void saturn_vdp2_device::preserve_scanned_output(')+'\n'+'\n'.join(funcs)
if args.mutation=='late':
 f=f.replace('  if ((m_vdp2_vram[offset] ^ data) & mem_mask)\n    m_vdp2->preserve_scanned_output();\n  COMBINE_DATA(&m_vdp2_vram[offset]);',
             '  bool const changed = (m_vdp2_vram[offset] ^ data) & mem_mask;\n  COMBINE_DATA(&m_vdp2_vram[offset]);\n  if (changed) m_vdp2->preserve_scanned_output();')
if args.mutation=='current-line':f=f.replace('update_partial(line - 1)', 'update_partial(line)')
if args.mutation=='missing':f=f.replace('m_vdp2->preserve_scanned_output();','(void)0;')
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <memory>
#include <vector>
using offs_t=unsigned;
struct rgb_t {rgb_t(unsigned,unsigned,unsigned){}};
unsigned pal5bit(unsigned n){return (n<<3)|(n>>2);}
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define LOGMASKED(...) do {} while(0)
#define VDP2_CRMD ((m_vdp2_regs[7]>>12)&3)
#define VDP2_RBG_ROTATION_PARAMETER_A 1
#define VDP2_RBG_ROTATION_PARAMETER_B 2
struct screen {
 bool live=true;int line=0,last=-1,calls=0,draws=0;
 struct {int min_y=0,max_y=5;} visible;
 std::array<std::array<uint32_t,3>,6> rows{};std::function<std::array<uint32_t,3>()> sample;
 bool started(){return live;}int vpos(){return line;}auto const &visible_area(){return visible;}
 void update_partial(int end){++calls;for(int y=last+1;y<=std::min(end,5);++y){rows[y]=sample();++draws;}last=std::max(last,end);}
};
struct saturn_vdp2_device {
 bool get_vramsz(){return false;}
 screen monitor;screen *m_screen=&monitor;bool m_disp=true,m_bdclmd=false;
 void preserve_scanned_output();
};
struct saturn_state {
 saturn_vdp2_device video;saturn_vdp2_device *m_vdp2=&video;
 std::array<uint16_t,256> m_vdp2_regs{};
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 std::array<uint32_t,1024> m_vdp2_cram{};
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);unsigned old_crmd=1;} m_vdp2_legacy;
 struct {unsigned watch_vdp2_vram_writes=0,is_cache_dirty=0,map_offset_min[2]{},map_offset_max[2]{},tile_offset_min[2]{},tile_offset_max[2]{};} RBG0_cache_data;
 struct gfx {void mark_dirty(unsigned){}};struct decoder {gfx g;gfx *gfx(unsigned){return &g;}} decode;decoder *m_gfxdecode=&decode;
 struct palette {void set_pen_color(unsigned,rgb_t){}void set_pen_color(unsigned,unsigned,unsigned,unsigned){}} pal;palette *m_palette=&pal;
 void mark_fade_effects_dirty(){}void vdp2_window_cache_invalidate(){}void refresh_palette_data(){}
 // DECLS
};
// FUNCTIONS
int main(){auto state=std::make_unique<saturn_state>();auto &s=*state;auto &d=s.video;auto &screen=d.monitor;
 screen.sample=[&s](){return std::array<uint32_t,3>{s.m_vdp2_regs[0x70/2],s.m_vdp2_vram[0],s.vdp2_cram_r(0)};};
 unsigned cases=0;
 for(int line=0;line<9;++line)for(unsigned writer=0;writer<3;++writer)
 for(uint32_t mask:{0u,0xffu,0xff00u,0xffffu,0xffff0000u,0xffffffffu})
 for(bool live:{false,true})for(bool display:{false,true})for(bool back:{false,true})for(bool erase:{false,true}){
  screen.live=live;screen.line=line;screen.last=-1;screen.calls=screen.draws=0;screen.rows={};d.m_disp=display;d.m_bdclmd=back;
  s.m_vdp2_regs[7]=0x1000;s.m_vdp2_regs[0x70/2]=0x1234;s.m_vdp2_vram[0]=0x12345678;s.m_vdp2_cram[0]=0x31415927;
  auto old=screen.sample();
  bool changes=writer==0?((old[0]^0x9876)&uint16_t(mask)):writer==1?((old[1]^0x98765432)&mask):((old[2]^0x87654321)&mask);
  bool preserve=live&&(display||back)&&line>0&&line<=6&&changes;
  if(erase&&preserve&&line>1)screen.update_partial(line-2);
  auto write=[&](){if(writer==0)s.vdp2_regs_w(0x70/2+0x100,0x9876,uint16_t(mask));else if(writer==1)s.vdp2_vram_w(0,0x98765432,mask);else s.vdp2_cram_w(1024,0x87654321,mask);};
  write();auto changed=screen.sample();int calls=screen.calls;write();assert(screen.calls==calls); // unchanged writes never request a flush
  assert(screen.draws==(preserve?line:0));screen.update_partial(5);
  for(int y=0;y<6;++y)assert(screen.rows[y]==((preserve&&y<line)?old:changed));
  assert(screen.draws==6);++cases;
 }
 // A mode-0 alias write must preserve when only the opposite bank changes.
 d.m_disp=true;d.m_bdclmd=false;screen.live=true;screen.line=3;screen.last=-1;screen.draws=0;screen.calls=0;
 s.m_vdp2_regs[7]=0;s.m_vdp2_cram[0]=0x12345678;s.m_vdp2_cram[512]=0xabcdef12;
 auto before=screen.sample();s.vdp2_cram_w(512,0xabcdef12,~0u);assert(screen.draws==3);
 for(int y=0;y<3;++y)assert(screen.rows[y]==before);
 // Non-rendering reserved/read-only register storage does not flush output.
 screen.calls=0;s.vdp2_regs_w(0x1f0/2,0xaaaa,0xffff);assert(!screen.calls);
 std::cout<<cases<<" production write/beam/mask/blank/erase/coalescing scenarios passed\n";
}
'''
# Avoid ambiguity between the recording gfx type and the method name.
code=code.replace('struct gfx {','struct graphics {').replace('decoder {gfx g;gfx *gfx(', 'decoder {graphics g;graphics *gfx(')
code=code.replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','')+';' for x in funcs)).replace('// FUNCTIONS',f)
with tempfile.TemporaryDirectory(prefix='saturn-raster-writes-') as tmp:
 cpp=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

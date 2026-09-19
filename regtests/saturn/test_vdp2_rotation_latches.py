#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production RPRCTL one-shot latch, raw table loader and row snapshot selection.

Replay copies exercise state continuity, not MAME save-manager/runtime acceptance.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mutation',choices=('clear','reload','delta'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text();head=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
funcs=[extract(src,sig) for sig in ('void saturn_state::vdp2_fill_rotation_parameter_table(', 'void saturn_state::vdp2_reset_rotation_latches(', 'void saturn_state::vdp2_latch_rotation_parameters(', 'void saturn_state::vdp2_load_rotation_line(')]
f='\n'.join(funcs)
if a.mutation=='clear':f=f.replace('m_vdp2_regs[0xb2 / 2] &= ~0x0707;', '(void)0;')
if a.mutation=='reload':f=f.replace('!m_rotation_latch_valid || (reload & 1)', '!m_rotation_latch_valid || (reload & 1) || true')
if a.mutation=='delta':f=f.replace('m_rotation_x[p] += uint32_t(r.dxst);', 'm_rotation_x[p] += 0;')
macsrc=re.sub(r'/\*.*?\*/','',src.replace('\\\n',' '),flags=re.S)
defs={m[1]:m[0] for m in re.finditer(r'^#define[ \t]+(VDP2_\w+)[ \t]+[^\n]+',macsrc,re.M)}
names=set(re.findall(r'VDP2_\w+',f));pending=list(names)
while pending:
 for dependency in re.findall(r'VDP2_\w+',defs[pending.pop()]):
  if dependency not in names:names.add(dependency);pending.append(dependency)
table=extract(head,'struct rotation_table {')
for field in re.findall(r'(?:u?int32_t)\s+(\w+)\s*=',table):
 assert f'save_item(STRUCT_MEMBER(m_rotation_lines, {field}));' in src
for field in ('m_rotation_line_valid','m_rotation_latch_valid','m_rotation_x','m_rotation_y','m_rotation_k'):
 assert f'save_item(NAME({field}));' in src
assert 'vdp2_latch_rotation_parameters(scanline);' in extract(src,'TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)')
assert 'vdp2_reset_rotation_latches();' in extract(src,'void saturn_state::machine_reset()')
assert 'vdp2_reset_rotation_latches();' in extract(src,'void saturn_state::system_reset_w(')
state=head[head.index('  static constexpr int ROTATION_SCANLINES'):head.index('  struct _vdp2_layer_data')]
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
struct input {bool code_pressed_once(int){return false;}};
struct machine_stub {struct input &input(){static struct input i;return i;}};
struct video {bool get_vramsz(){return false;}int step=1;int get_ystep_count(){return step;}int get_vblank_start_position(){return 16;}};
struct saturn_state {
 // TABLE
 // STATE
 uint16_t m_vdp2_regs[256]{};std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 int m_vdpdebug_roz=0;machine_stub &machine(){static machine_stub m;return m;}
 video device;video *m_vdp2=&device;
 // DECLS
};
#define DEBUG_DRAW_ROZ 0
#define JOYCODE_Y_UP_SWITCH 1
#define JOYCODE_Y_DOWN_SWITCH 2
#define LOGMASKED(...) ((void)0)
#define popmessage(...) ((void)0)
// MACROS
// FUNCTIONS
int main(){unsigned cases=0;
 for(int step:{1,2})for(unsigned mask=0;mask<64;++mask)for(int reload_line:{0,1,3,6}){
  saturn_state s;s.device.step=step;s.m_vdp2_regs[0x20/2]=0x10;
  uint32_t x[2]{},y[2]{},k[2]{};
  saturn_state checkpoint;
  auto program=[&](saturn_state &t,int line){
   unsigned control=line==reload_line?(mask&7)|((mask>>3)<<8):0;
   t.m_vdp2_regs[0xb2/2]=control;
   for(unsigned p=0;p<2;++p){unsigned b=p*32;
    t.m_vdp2_vram[b]=(line*100+p*10+1)*65536;
    t.m_vdp2_vram[b+1]=uint32_t((-line*10-int(p)-1)*65536)&0x1fffffc0;
    t.m_vdp2_vram[b+3]=uint32_t(line%2?-32768:65536)&0x7ffc0;
    t.m_vdp2_vram[b+4]=uint32_t(line%2?65536:-65536)&0x7ffc0;
    t.m_vdp2_vram[b+7]=t.m_vdp2_vram[b+11]=65536;
    t.m_vdp2_vram[b+21]=(1000+line*20+p)*65536;
    t.m_vdp2_vram[b+22]=uint32_t(line%2?-65536:131072)&0x3ffffc0;
    t.m_vdp2_vram[b+23]=65536;
   }
   t.vdp2_latch_rotation_parameters(line*step);
   if(step==2)t.vdp2_latch_rotation_parameters(line*step+1);
  };
  for(int line=0;line<8;++line){
   program(s,line);assert(s.m_vdp2_regs[0xb2/2]==0);
   for(unsigned p=0;p<2;++p){unsigned bits=line==reload_line?(mask>>(p*3))&7:0;
    if(!line||(bits&1))x[p]=(line*100+p*10+1)*65536;else x[p]+=line%2?-32768:65536;
    if(!line||(bits&2))y[p]=(-line*10-int(p)-1)*65536;else y[p]+=line%2?65536:-65536;
    if(!line||(bits&4))k[p]=(1000+line*20+p)*65536;else k[p]+=line%2?-65536:131072;
    assert(s.m_rotation_x[p]==x[p]&&s.m_rotation_y[p]==y[p]&&s.m_rotation_k[p]==k[p]);
    for(int row=line*step;row<(line+1)*step;++row){
     assert(s.m_rotation_line_valid[row]);auto &r=s.m_rotation_lines[row][p];
     assert(uint32_t(r.xst)+uint32_t(int64_t(r.dxst)*line)==x[p]);
     assert(uint32_t(r.yst)+uint32_t(int64_t(r.dyst)*line)==y[p]);
     assert(r.kast+uint32_t(int64_t(r.dkast)*line)==k[p]);
     assert(r.dkax==65536); // read-control bits must not zero per-dot deltas
    }
   }
   if(line==3){checkpoint=s;checkpoint.m_vdp2=&checkpoint.device;}
  }
  for(int line=4;line<8;++line)program(checkpoint,line);
  assert(!memcmp(checkpoint.m_rotation_lines,s.m_rotation_lines,sizeof(s.m_rotation_lines)));
  assert(!memcmp(checkpoint.m_rotation_line_valid,s.m_rotation_line_valid,sizeof(s.m_rotation_line_valid)));
  for(int row=0;row<8*step;++row)for(unsigned p=0;p<2;++p){s.vdp2_load_rotation_line(p+1,row);assert(!memcmp(&s.current_rotation_table,&s.m_rotation_lines[row][p],sizeof(s.current_rotation_table)));}
  s.m_vdp2_regs[0x20/2]=0;s.m_vdp2_regs[0xb2/2]=0x707;s.vdp2_latch_rotation_parameters(0);
  assert(!s.m_rotation_latch_valid&&s.m_vdp2_regs[0xb2/2]==0x707);
  for(bool valid:s.m_rotation_line_valid)assert(!valid);
  s.m_vdp2_regs[0x20/2]=0x10;s.vdp2_latch_rotation_parameters(step*4);
  assert(s.m_rotation_latch_valid&&s.m_vdp2_regs[0xb2/2]==0);++cases;
 }
 std::cout<<cases<<" one-shot reload/accumulation/snapshot replay sequences passed\n";
}
'''
code=code.replace('// TABLE',table+' current_rotation_table;').replace('// STATE',state).replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','')+';' for x in funcs)).replace('// MACROS','\n'.join(defs[n] for n in sorted(names))).replace('// FUNCTIONS',f)
with tempfile.TemporaryDirectory(prefix='saturn-rotation-latches-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

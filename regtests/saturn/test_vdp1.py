#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute VDP1 command/completion, CPU framebuffer and clipping bodies.

Rasterizers, CPU time and IRQ delivery are recording endpoints, not a timing model.
--baseline selects old command, framebuffer or pixel bodies independently.
"""
from pathlib import Path
import argparse, os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', choices=('commands','framebuffer','clipping'))
a=p.parse_args()
path='src/mame/sega/saturn.cpp';current=(ROOT/path).read_text()
old=subprocess.check_output(['git','show','f3b0a5fceb0eeccc21dc83e799c618d79085cc7c:'+path],cwd=ROOT,text=True) if a.baseline else current
header=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
pixels=('drawpixel_poly','drawpixel_8bpp_trans','drawpixel_4bpp_trans','drawpixel_4bpp_notrans','drawpixel_generic')
functions=extract(current,'bool saturn_state::vdp1_pixel_visible(')+'\n'
for group, signatures in [
 ('commands', ['void saturn_state::vdp1_process_list()', 'TIMER_CALLBACK_MEMBER(saturn_state::vdp1_draw_end)']),
 ('framebuffer',['void saturn_state::vdp1_framebuffer0_w(', 'uint32_t saturn_state::vdp1_framebuffer0_r(']),
 ('clipping',['void saturn_state::'+name+'(' for name in pixels])]:
    functions+='\n'.join(extract(old if a.baseline==group else current,s) for s in signatures)+'\n'
# The unrelated periodic scanline path must no longer manufacture a draw-end IRQ.
assert 'vdp1_end_w' not in extract(current,'TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)')
types=extract(header,'struct vdp1_sprite_list')+' current_sprite;'
harness=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
using offs_t=unsigned;
#define VDP1_LOG 0
#define logerror(...) ((void)0)
#define popmessage(...) ((void)0)
#define TIMER_CALLBACK_MEMBER(name) void name(int param)
#define ACCESSING_BITS_24_31 (mem_mask&0xff000000)
#define ACCESSING_BITS_16_23 (mem_mask&0x00ff0000)
#define ACCESSING_BITS_8_15 (mem_mask&0x0000ff00)
#define ACCESSING_BITS_0_7 (mem_mask&0x000000ff)
#define ACCESSING_BITS_16_31 (mem_mask&0xffff0000)
#define ACCESSING_BITS_0_15 (mem_mask&0x0000ffff)
struct rectangle {
 int min_x=0,max_x=31,min_y=0,max_y=31;
 void set(int a,int b,int c,int d){min_x=a;max_x=b;min_y=c;max_y=d;}
 bool contains(int x,int y) const {return x>=min_x&&x<=max_x&&y>=min_y&&y<=max_y;}
};
struct attotime {static constexpr int never=-1;};
struct timer {int delay=-1;void adjust(int value){delay=value;}};
struct cpu {int cycles_to_attotime(int n){return n;}};
struct scu {unsigned irqs=0;void vdp1_end_w(int n){assert(n==1);++irqs;}};
uint16_t alpha_blend_r16(uint16_t,uint16_t,int){assert(false);return 0;}
struct saturn_state {
 // TYPES
 timer timer_;cpu cpu_;scu scu_;cpu *m_maincpu=&cpu_;scu *m_scu=&scu_;
 struct legacy {
  timer *draw_end_timer=nullptr;
  uint16_t lopr=0,copr=0;
  int local_x=0,local_y=0,framebuffer_current_draw=0;
  rectangle user_cliprect,system_cliprect;
  std::vector<uint16_t> framebuffer[2]={std::vector<uint16_t>(1024*512),std::vector<uint16_t>(1024*512)};
  std::vector<uint8_t> gfx_decode=std::vector<uint8_t>(0x100000,0x11);
  uint16_t *framebuffer_draw_lines[512]{};
 } m_vdp1_legacy;
 std::vector<uint32_t> m_vdp1_vram=std::vector<uint32_t>(0x80000/4);
 const rectangle *last_clip=nullptr;
 unsigned draws=0;int tvm=0,m_sprite_colorbank=0;bool cef=false;
 saturn_state(){m_vdp1_legacy.draw_end_timer=&timer_;for(unsigned y=0;y<512;++y)m_vdp1_legacy.framebuffer_draw_lines[y]=m_vdp1_legacy.framebuffer[0].data()+y*1024;}
 void CEF_0(){cef=false;}void CEF_1(){cef=true;}
 void clear_gouraud_shading(){}void vdp1_set_drawpixel(){}
 int vdp1_coord(int v){return int16_t((v&0x1fff)<<3)>>3;}
 int vdp1_apply_gouraud_shading(int,int,int){assert(false);return 0;}
 auto &machine(){return *this;} int rand(){assert(false);return 0;}
 void vdp1_draw_normal_sprite(const rectangle &clip,int){last_clip=&clip;++draws;}
 void vdp1_draw_scaled_sprite(const rectangle&){++draws;}
 void vdp1_draw_distorted_sprite(const rectangle&){++draws;}
 void vdp1_draw_poly_line(const rectangle&){++draws;}
 void vdp1_draw_line(const rectangle&){++draws;}
 int VDP1_TVM(){return tvm;}
 void vdp1_process_list();void vdp1_draw_end(int);
 void vdp1_framebuffer0_w(offs_t,uint32_t,uint32_t);
 uint32_t vdp1_framebuffer0_r(offs_t,uint32_t);
 bool vdp1_pixel_visible(int,int) const;
 void drawpixel_poly(int,int,int,int);void drawpixel_8bpp_trans(int,int,int,int);
 void drawpixel_4bpp_trans(int,int,int,int);void drawpixel_4bpp_notrans(int,int,int,int);
 void drawpixel_generic(int,int,int,int);
 void fire(){if(timer_.delay!=-1){timer_.delay=-1;vdp1_draw_end(0);}}
};
// FUNCTIONS
int main(){
 auto s=std::make_unique<saturn_state>();unsigned commands=0,fb=0,clipping=0;
 // Every lower-bit combination is ignored when END is set.
 for(unsigned ctrl=0x8000;ctrl<=0xffff;++ctrl){
  s->draws=0;s->scu_.irqs=0;s->m_vdp1_vram[0]=ctrl<<16;s->cef=true;
  s->vdp1_process_list();assert(!s->cef&&s->draws==0&&s->m_vdp1_legacy.copr==0&&s->timer_.delay==16);
  assert(s->scu_.irqs==0);s->fire();assert(s->cef&&s->scu_.irqs==1);s->fire();assert(s->scu_.irqs==1);++commands;
 }
 // Replacing pending END with a skip/assign self-loop cancels old completion.
 s->m_vdp1_vram[0]=0x80000000;s->vdp1_process_list();s->m_vdp1_vram[0]=0x50000000;
 s->vdp1_process_list();assert(s->timer_.delay==-1&&!s->cef);++commands;
 // Call last VRAM command, process-next wraps to the command at zero, then
 // RETURN reaches command one. This executes the array boundary under ASan.
 std::fill(s->m_vdp1_vram.begin(),s->m_vdp1_vram.end(),0);
 s->m_vdp1_vram[0]=0x6000fffc;s->m_vdp1_vram[8]=0x80000000;
 s->m_vdp1_vram[0x3fff*8]=0x70000000; // skip-return checks last legal slot
 s->vdp1_process_list();assert(s->m_vdp1_legacy.copr==4&&s->timer_.delay==48);++commands;
 s->m_vdp1_vram[0x3fff*8]=0x40000000; // skip-next wraps, not out-of-bounds
 s->vdp1_process_list();assert(s->timer_.delay==64&&s->m_vdp1_legacy.copr==4);++commands;
 // The list dispatcher must not rasterize outside-clipped commands against
 // the user rectangle: doing so would reject every pixel in the later test.
 for(unsigned mode : {0u,0x200u,0x400u,0x600u}){
  s->m_vdp1_vram[0]=0;s->m_vdp1_vram[1]=mode<<16;s->m_vdp1_vram[8]=0x80000000;
  s->vdp1_process_list();
  assert(s->last_clip==(mode==0x400?&s->m_vdp1_legacy.user_cliprect:&s->m_vdp1_legacy.system_cliprect));++commands;
 }
 // CPU reads/writes only the selected drawing bank; byte accesses are legal
 // only in 8-bit display modes. All 16 combinations of byte lanes are tested.
 for(int bank : {0,1})for(int mode : {0,1,3})for(unsigned lanes=0;lanes<16;++lanes)
 for(uint32_t data : {0u,0x12345678u,0xa5c36987u,0xffffffffu}){
  if(mode==0&&lanes!=0&&lanes!=3&&lanes!=12&&lanes!=15)continue;
  uint32_t mask=0;for(unsigned byte=0;byte<4;++byte)if(lanes&(1u<<byte))mask|=0xffu<<(byte*8);
  auto &l=s->m_vdp1_legacy;l.framebuffer_current_draw=bank;s->tvm=mode;
  l.framebuffer[bank][0]=0x89ab;l.framebuffer[bank][1]=0xcdef;
  l.framebuffer[bank^1][0]=0xfeed;l.framebuffer[bank^1][1]=0xbeef;
  s->vdp1_framebuffer0_w(0,data,mask);uint32_t expected=(0x89abcdef&~mask)|(data&mask);
  assert(l.framebuffer[bank][0]==(expected>>16)&&l.framebuffer[bank][1]==(expected&0xffff));
  assert(s->vdp1_framebuffer0_r(0,mask)==(expected&mask));
  assert(l.framebuffer[bank^1][0]==0xfeed&&l.framebuffer[bank^1][1]==0xbeef);++fb;
 }
 // Actual fast and generic pixel writers: inclusive user boundary, complement
 // mode, system clipping, and negative/out-of-backing-store coordinates.
 s->m_vdp1_legacy.system_cliprect.set(0,31,0,31);
 s->m_vdp1_legacy.user_cliprect.set(8,23,8,23);
 s->current_sprite.CMDCOLR=0x1234;s->current_sprite.ispoly=1;
 using writer=void(saturn_state::*)(int,int,int,int);
 for(writer draw : {&saturn_state::drawpixel_poly,&saturn_state::drawpixel_8bpp_trans,&saturn_state::drawpixel_4bpp_trans,&saturn_state::drawpixel_4bpp_notrans,&saturn_state::drawpixel_generic})
 for(unsigned mode : {0u,0x200u,0x400u,0x600u})for(int y=-1;y<=33;++y)for(int x=-1;x<=33;++x){
  s->current_sprite.CMDPMOD=mode;bool inside=x>=8&&x<=23&&y>=8&&y<=23;
  bool expected=x>=0&&x<=31&&y>=0&&y<=31&&(!(mode&0x400)||((mode&0x200)?!inside:inside));
  if(x>=0&&y>=0)s->m_vdp1_legacy.framebuffer_draw_lines[y][x]=0;
  (s.get()->*draw)(x,y,0,0);
  if(x>=0&&y>=0)assert(bool(s->m_vdp1_legacy.framebuffer_draw_lines[y][x])==expected);
  ++clipping;
 }
 std::cout<<commands<<" VDP1 command/completion, "<<fb<<" framebuffer and "<<clipping<<" pixel-clipping scenarios passed\n";
}
'''.replace('// TYPES',types).replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-vdp1-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

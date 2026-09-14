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
p.add_argument('--baseline', choices=('commands','framebuffer','clipping','sequencer','packed'))
a=p.parse_args()
path='src/mame/sega/saturn.cpp';current=(ROOT/path).read_text()
baseline_revision='aebdb3de991b7601e4ab2f73786b11730ef6cb47' if a.baseline in ('sequencer','packed') else 'f3b0a5fceb0eeccc21dc83e799c618d79085cc7c'
old=subprocess.check_output(['git','show',baseline_revision+':'+path],cwd=ROOT,text=True) if a.baseline else current
header=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
pixels=('drawpixel_poly','drawpixel_8bpp_trans','drawpixel_4bpp_trans','drawpixel_4bpp_notrans','drawpixel_generic')
functions=extract(current,'bool saturn_state::vdp1_pixel_visible(')+'\n'+extract(current,'void saturn_state::vdp1_abort_draw()')+'\n'
functions+='\n'.join(extract(current,s) for s in ('uint16_t saturn_state::vdp1_read_pixel(', 'void saturn_state::vdp1_write_pixel(', 'void saturn_state::vdp1_clear_framebuffer(', 'void saturn_state::vdp1_change_framebuffers()', 'void saturn_state::vdp1_state_save_postload()', 'void saturn_state::vdp1_prepare_framebuffers()', 'void saturn_state::vdp1_regs_w('))+'\n'
for group, signatures in [
 ('commands', ['void saturn_state::vdp1_process_list()', 'TIMER_CALLBACK_MEMBER(saturn_state::vdp1_draw_end)']),
 ('framebuffer',['void saturn_state::vdp1_framebuffer0_w(', 'uint32_t saturn_state::vdp1_framebuffer0_r(']),
 ('clipping',['void saturn_state::'+name+'(' for name in pixels])]:
    functions+='\n'.join(extract(old if (a.baseline==group or (a.baseline=='sequencer' and group=='commands') or (a.baseline=='packed' and group=='clipping')) else current,s) for s in signatures)+'\n'
# The unrelated periodic scanline path must no longer manufacture a draw-end IRQ.
assert 'vdp1_end_w' not in extract(current,'TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)')
for field in ('drawing','command_position','command_return'):
    assert f'save_item(NAME(m_vdp1_legacy.{field}));' in current
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::machine_reset()')
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::system_reset_w(')
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::vdp1_regs_w(')
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
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define VDP1_PTMR (m_vdp1_regs[2])
#define VDP1_EWDR (m_vdp1_regs[3])
#define VDP1_EWLR_X1 ((m_vdp1_regs[4]&0x7e00)>>9)
#define VDP1_EWLR_Y1 (m_vdp1_regs[4]&0x1ff)
#define VDP1_EWRR_X3 ((m_vdp1_regs[5]&0xfe00)>>9)
#define VDP1_EWRR_Y3 (m_vdp1_regs[5]&0x1ff)
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
struct byte_buffer:std::vector<uint8_t> {
 using std::vector<uint8_t>::vector;
 uint8_t *get(){return data();}
};
struct saturn_state {
 // TYPES
 timer timer_;cpu cpu_;scu scu_;cpu *m_maincpu=&cpu_;scu *m_scu=&scu_;
 struct legacy {
  timer *draw_end_timer=nullptr;
  bool drawing=false;int command_position=0,command_return=-1;
  uint16_t lopr=0,copr=0;
  int local_x=0,local_y=0,framebuffer_current_draw=0,framebuffer_current_display=1;
  int framebuffer_width=1024,framebuffer_height=512,framebuffer_mode=0,framebuffer_double_interlace=0,fbcr_accessed=0;
  uint16_t ewdr=0;
  rectangle user_cliprect,system_cliprect;
  std::vector<uint16_t> framebuffer[2]={std::vector<uint16_t>(1024*512),std::vector<uint16_t>(1024*512)};
  byte_buffer gfx_decode=byte_buffer(0x100000,0x11);
  uint16_t *framebuffer_draw_lines[512]{},*framebuffer_display_lines[512]{};
 } m_vdp1_legacy;
 std::vector<uint32_t> m_vdp1_vram=std::vector<uint32_t>(0x80000/4);
 const rectangle *last_clip=nullptr;
 uint16_t m_vdp1_regs[16]{};
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
 int VDP1_TVM() const {return tvm;}
 uint16_t vdp1_read_pixel(const uint16_t *,int) const;
 void vdp1_write_pixel(int,int,uint16_t);void vdp1_clear_framebuffer(int);
 void vdp1_process_list();void vdp1_draw_end(int);void vdp1_abort_draw();
 void vdp1_prepare_framebuffers();void vdp1_state_save_postload();void vdp1_change_framebuffers();
 void vdp1_regs_w(offs_t,uint16_t,uint16_t);
 void vdp1_set_framebuffer_config(){assert(false);}
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
  s->vdp1_process_list();assert(s->m_vdp1_legacy.drawing&&!s->cef&&s->draws==0&&s->m_vdp1_legacy.copr==0&&s->timer_.delay==16);
  assert(s->scu_.irqs==0);s->fire();assert(s->cef&&s->scu_.irqs==1);s->fire();assert(s->scu_.irqs==1);++commands;
 }
 // Replacing pending END with a skip/assign self-loop cancels old completion.
 s->m_vdp1_vram[0]=0x80000000;s->vdp1_process_list();s->m_vdp1_vram[0]=0x50000000;
 s->vdp1_process_list();
 for(unsigned i=0;i<20000;++i){s->fire();assert(s->m_vdp1_legacy.drawing&&!s->cef&&s->timer_.delay==16);}
 s->m_vdp1_vram[0]=0x80000000;s->fire();assert(s->cef&&!s->m_vdp1_legacy.drawing);++commands;
 // Call last VRAM command, process-next wraps to the command at zero, then
 // RETURN reaches command one. This executes the array boundary under ASan.
 std::fill(s->m_vdp1_vram.begin(),s->m_vdp1_vram.end(),0);
 s->m_vdp1_vram[0]=0x6000fffc;s->m_vdp1_vram[8]=0x80000000;
 s->m_vdp1_vram[0x3fff*8]=0x70000000; // skip-return checks last legal slot
 s->vdp1_process_list();s->fire();s->fire();s->fire();assert(s->cef&&s->m_vdp1_legacy.copr==4&&s->timer_.delay==-1);++commands;
 s->m_vdp1_vram[0x3fff*8]=0x40000000; // skip-next wraps, not out-of-bounds
 s->vdp1_process_list();s->fire();s->fire();s->fire();s->fire();assert(s->cef&&s->timer_.delay==-1&&s->m_vdp1_legacy.copr==4);++commands;
 // The list dispatcher must not rasterize outside-clipped commands against
 // the user rectangle: doing so would reject every pixel in the later test.
 for(unsigned mode : {0u,0x200u,0x400u,0x600u}){
  s->m_vdp1_vram[0]=0;s->m_vdp1_vram[1]=mode<<16;s->m_vdp1_vram[8]=0x80000000;
  s->vdp1_process_list();s->fire();
  assert(s->last_clip==(mode==0x400?&s->m_vdp1_legacy.user_cliprect:&s->m_vdp1_legacy.system_cliprect));++commands;
 }
 // All eight flow controls, both skip states, valid RETURN context.
 for(unsigned jump=0;jump<8;++jump){
  s->m_vdp1_vram[0]=((jump<<12)|0u)<<16|8u; // target command 2
  s->vdp1_process_list();
  s->m_vdp1_legacy.command_return=((jump&3)==3)?3:-1;
  s->draws=0;s->fire();
  unsigned next=(jump&3)==0?1:(jump&3)==3?3:2;
  assert(s->m_vdp1_legacy.command_position==int(next));
  assert(s->m_vdp1_legacy.copr==0&&s->draws==unsigned(jump<4));
  assert(s->m_vdp1_legacy.command_return==((jump&3)==2?1:-1));++commands;
 }
 // Stop before each point in a finite sequence: completed work remains,
 // no later command or stale callback can signal END, and PTMR restarts at 0.
 for(unsigned stop=0;stop<4;++stop){
  for(unsigned n=0;n<4;++n)s->m_vdp1_vram[n*8]=n==3?0x80000000:0;
  s->draws=0;s->scu_.irqs=0;s->vdp1_process_list();
  for(unsigned n=0;n<stop;++n)s->fire();
  assert(s->draws==stop);s->vdp1_abort_draw();s->vdp1_draw_end(0);
  assert(!s->m_vdp1_legacy.drawing&&!s->cef&&s->scu_.irqs==0&&s->timer_.delay==-1);
  s->vdp1_process_list();for(unsigned n=0;n<4;++n)s->fire();
  assert(s->cef&&s->scu_.irqs==1&&s->m_vdp1_legacy.copr==12);++commands;
 }
 // Copy the registered sequencer state at a CALL boundary, not host-local
 // loop variables. This models continuation, not a real MAME save-manager run.
 {
  auto restored=std::make_unique<saturn_state>();
  s->m_vdp1_vram[0]=0x60000008;s->m_vdp1_vram[8]=0x80000000;s->m_vdp1_vram[16]=0x70000000;
  s->vdp1_process_list();s->fire();
  restored->m_vdp1_vram=s->m_vdp1_vram;
  restored->m_vdp1_legacy.command_position=s->m_vdp1_legacy.command_position;
  restored->m_vdp1_legacy.command_return=s->m_vdp1_legacy.command_return;
  restored->m_vdp1_legacy.drawing=s->m_vdp1_legacy.drawing;
  restored->timer_.delay=s->timer_.delay;restored->fire();restored->fire();
  assert(restored->cef&&restored->scu_.irqs==1&&restored->m_vdp1_legacy.copr==4);++commands;
 }
 // Execute the actual ENDR register dispatch, including its unused neighbor.
 for(unsigned offset : {6u,7u})for(uint16_t mask : {uint16_t(0),uint16_t(0xffff)}){
  s->vdp1_process_list();s->vdp1_regs_w(offset,0,mask);
  bool running=offset!=6||mask==0;
  assert(s->m_vdp1_legacy.drawing==running&&((s->timer_.delay!=-1)==running));++commands;
 }
 for(unsigned reg=8;reg<=11;++reg){
  s->m_vdp1_regs[reg]=0x1234;s->vdp1_regs_w(reg,0xffff,0xffff);assert(s->m_vdp1_regs[reg]==0x1234);++commands;
 }
 for(int bank : {0,1})for(uint16_t address : {uint16_t(0),uint16_t(4),uint16_t(0xfffc)}){
  auto &l=s->m_vdp1_legacy;l.framebuffer_current_draw=bank;l.framebuffer_current_display=bank^1;
  l.copr=address;s->cef=true;s->vdp1_change_framebuffers();
  assert(l.lopr==address&&l.copr==address&&!s->cef);
  assert(l.framebuffer_current_draw==(bank^1)&&l.framebuffer_current_display==bank);++commands;
 }
 // Actual postload rebuild must preserve the saved bank and geometry, not
 // perform a TVMR reconfiguration that resets the bank to zero.
 for(int bank : {0,1})for(int width : {256,512,1024})for(int height : {256,512}){
  auto &l=s->m_vdp1_legacy;l.framebuffer_current_draw=bank;l.framebuffer_current_display=bank^1;
  l.framebuffer_width=width;l.framebuffer_height=height;l.framebuffer_mode=3;
  l.command_position=123;l.command_return=45;l.drawing=true;
  s->m_vdp1_vram[0]=0x12345678;s->vdp1_state_save_postload();
  assert(l.framebuffer_current_draw==bank&&l.framebuffer_current_display==(bank^1));
  assert(l.framebuffer_width==width&&l.framebuffer_height==height&&l.framebuffer_mode==3);
  assert(l.command_position==123&&l.command_return==45&&l.drawing);
  assert(l.framebuffer_draw_lines[height-1]==l.framebuffer[bank].data()+(height-1)*(width/2));
  assert(l.framebuffer_display_lines[height-1]==l.framebuffer[bank^1].data()+(height-1)*(width/2));
  assert(l.gfx_decode[0]==0x12&&l.gfx_decode[1]==0x34&&l.gfx_decode[2]==0x56&&l.gfx_decode[3]==0x78);++commands;
 }
 s->m_vdp1_legacy.framebuffer_current_draw=0;s->m_vdp1_legacy.framebuffer_mode=0;s->m_vdp1_legacy.framebuffer_width=1024;s->m_vdp1_legacy.framebuffer_height=512;s->vdp1_prepare_framebuffers();
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
 // Packed rendering, CPU readback and scanout use one shared word layout.
 using writer=void(saturn_state::*)(int,int,int,int);
 writer writers[]={&saturn_state::drawpixel_poly,&saturn_state::drawpixel_8bpp_trans,&saturn_state::drawpixel_4bpp_trans,&saturn_state::drawpixel_4bpp_notrans,&saturn_state::drawpixel_generic};
 for(int mode : {1,3})for(int bank : {0,1}){
  auto &l=s->m_vdp1_legacy;int width=mode==1?1024:512,height=mode==1?256:512;
  l.framebuffer_current_draw=bank;l.framebuffer_mode=mode;l.framebuffer_width=width;l.framebuffer_height=height;s->tvm=mode;
  s->vdp1_prepare_framebuffers();l.system_cliprect.set(0,width-1,0,height-1);
  for(unsigned variant=0;variant<5;++variant)for(int y : {0,1,height-1})for(int x : {0,1,width-2,width-1}){
   unsigned index=y*(width/2)+x/2;
   l.framebuffer[bank][index]=0xaabb;l.framebuffer[bank^1][index]=0x5566;
   s->current_sprite.ispoly=1;s->current_sprite.CMDCOLR=0x1234;s->current_sprite.CMDPMOD=0;
   l.gfx_decode[0]=0x11;
   (s.get()->*writers[variant])(x,y,0,0);
   unsigned dot=(variant==0||variant==4)?0x34:variant==1?0x11:1;
   unsigned expected=(x&1)?0xaa00|dot:(dot<<8)|0xbb;
   assert(l.framebuffer[bank][index]==expected&&l.framebuffer[bank^1][index]==0x5566);
   assert(s->vdp1_read_pixel(l.framebuffer_draw_lines[y],x)==dot);
   uint32_t cpuword=s->vdp1_framebuffer0_r(index/2,0xffffffff);
   assert(((cpuword>>((index&1)?0:16))&0xffff)==expected);++fb;
  }
  std::fill(l.framebuffer[bank].begin(),l.framebuffer[bank].end(),0xaabb);
  l.ewdr=0x1234;s->m_vdp1_regs[4]=(1<<9)|3;s->m_vdp1_regs[5]=(2<<9)|3;
  s->vdp1_clear_framebuffer(bank);
  for(unsigned x=0;x<48;++x){
   unsigned expected=x>=16&&x<32?((x&1)?0x34:0x12):((x&1)?0xbb:0xaa);
   assert(s->vdp1_read_pixel(l.framebuffer_draw_lines[3],x)==expected);
  }
  assert(l.framebuffer[bank][2*(width/2)]==0xaabb&&l.framebuffer[bank][4*(width/2)]==0xaabb);++fb;
 }
 s->tvm=0;s->m_vdp1_legacy.framebuffer_mode=0;s->m_vdp1_legacy.framebuffer_current_draw=0;
 s->m_vdp1_legacy.framebuffer_width=1024;s->m_vdp1_legacy.framebuffer_height=512;s->vdp1_prepare_framebuffers();
 // Actual fast and generic pixel writers: inclusive user boundary, complement
 // mode, system clipping, and negative/out-of-backing-store coordinates.
 s->m_vdp1_legacy.system_cliprect.set(0,31,0,31);
 s->m_vdp1_legacy.user_cliprect.set(8,23,8,23);
 s->current_sprite.CMDCOLR=0x1234;s->current_sprite.ispoly=1;
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

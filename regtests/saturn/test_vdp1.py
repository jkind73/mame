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
p.add_argument('--render-mutation',choices=('mon','round','gouraud','endcode'))
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
functions+='\n'.join(extract(current,s) for s in ('uint16_t saturn_state::vdp1_color_calculate(', 'void saturn_state::vdp1_draw_color(', 'uint16_t saturn_state::vdp1_read_pixel(', 'void saturn_state::vdp1_write_pixel(', 'void saturn_state::vdp1_clear_framebuffer(', 'void saturn_state::vdp1_change_framebuffers()', 'void saturn_state::vdp1_video_update()', 'void saturn_state::vdp1_state_save_postload()', 'void saturn_state::vdp1_prepare_framebuffers()', 'void saturn_state::vdp1_regs_w('))+'\n'
for group, signatures in [
 ('commands', ['void saturn_state::vdp1_process_list()', 'TIMER_CALLBACK_MEMBER(saturn_state::vdp1_draw_end)']),
 ('framebuffer',['void saturn_state::vdp1_framebuffer0_w(', 'uint32_t saturn_state::vdp1_framebuffer0_r(']),
 ('clipping',['void saturn_state::'+name+'(' for name in pixels])]:
    functions+='\n'.join(extract(old if (a.baseline==group or (a.baseline=='sequencer' and group=='commands') or (a.baseline=='packed' and group=='clipping')) else current,s) for s in signatures)+'\n'
functions += '\n'.join(extract(current, signature) for signature in (
    'static inline int32_t _shading(', 'uint16_t saturn_state::vdp1_apply_gouraud_shading(',
    'bool saturn_state::vdp1_is_end_code(', 'int saturn_state::x2s(', 'int saturn_state::y2s(')) + '\n'
functions += extract(current, 'void saturn_state::vdp1_draw_normal_sprite(').replace(
    'saturn_state::vdp1_draw_normal_sprite', 'saturn_state::raster_normal') + '\n'
if a.render_mutation:
    mutations = {
        'mon': ('line[(VDP1_TVM() & 1) ? (x >> 1) : x] |= 0x8000;', 'vdp1_write_pixel(x, y, src | 0x8000);'),
        'round': ('(src & dst & 0x0421)', '0'),
        'gouraud': ('const int64_t dx = int64_t(x) - (line.x[0] >> FRAC_SHIFT);', 'const int64_t dx = 0;'),
        'endcode': ('if (++end_codes == 2)', 'if (++end_codes == 99)'),
    }
    before,after=mutations[a.render_mutation]
    assert functions.count(before)==1
    functions=functions.replace(before,after)
# The unrelated periodic scanline path must no longer manufacture a draw-end IRQ.
assert 'vdp1_end_w' not in extract(current,'TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)')
for field in ('drawing','command_position','command_return'):
    assert f'save_item(NAME(m_vdp1_legacy.{field}));' in current
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::machine_reset()')
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::system_reset_w(')
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::vdp1_regs_w(')
types=extract(header,'struct vdp1_sprite_list')+' current_sprite;'
types+='\n'+extract(header,'struct vdp1_poly_scanline {')+';\n'+extract(header,'struct vdp1_poly_scanline_data {')+';'
types+='\n'+extract(header,'struct spoint {')+';'
harness=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
using offs_t=unsigned;
enum {FRAC_SHIFT=16};
constexpr uint16_t RGB_R(uint16_t c){return c&31;}
constexpr uint16_t RGB_G(uint16_t c){return (c>>5)&31;}
constexpr uint16_t RGB_B(uint16_t c){return (c>>10)&31;}
#define VDP1_LOG 0
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define VDP1_PTMR (m_vdp1_regs[2])
#define VDP1_PTM (m_vdp1_regs[2]&3)
#define VDP1_FBCR (m_vdp1_regs[1])
#define VDP1_CEF cef
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
  int framebuffer_clear_on_next_frame=0;
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
 unsigned draws=0;int tvm=0,m_sprite_colorbank=0;bool cef=false,bef=false;
 saturn_state(){m_vdp1_legacy.draw_end_timer=&timer_;for(unsigned y=0;y<512;++y)m_vdp1_legacy.framebuffer_draw_lines[y]=m_vdp1_legacy.framebuffer[0].data()+y*1024;}
 void CEF_0(){cef=false;}void CEF_1(){cef=true;}
 void BEF_0(){bef=false;}void BEF_1(){bef=true;}
 void clear_gouraud_shading(){}void vdp1_set_drawpixel(){}
 int vdp1_coord(int v){return int16_t((v&0x1fff)<<3)>>3;}
 std::unique_ptr<vdp1_poly_scanline_data> vdp1_shading_data=std::make_unique<vdp1_poly_scanline_data>();
 uint16_t vdp1_apply_gouraud_shading(int,int,uint16_t);
 bool vdp1_is_end_code(int,int) const;
 int x2s(int);int y2s(int);
 void raster_normal(const rectangle&,int);
 uint8_t read_gouraud_table(){return 0;}
 void vdp1_setup_shading(const spoint*,const rectangle&){assert(false);}
 void(saturn_state::*drawpixel)(int,int,int,int)=&saturn_state::drawpixel_generic;
 auto &machine(){return *this;} int rand(){assert(false);return 0;}
 void vdp1_draw_normal_sprite(const rectangle &clip,int){last_clip=&clip;++draws;}
 void vdp1_draw_scaled_sprite(const rectangle&){++draws;}
 void vdp1_draw_distorted_sprite(const rectangle&){++draws;}
 void vdp1_draw_poly_line(const rectangle&){++draws;}
 void vdp1_draw_line(const rectangle&){++draws;}
 int VDP1_TVM() const {return tvm;}
 int VDP1_VBE() const {return (m_vdp1_regs[0]>>3)&1;}
 void vdp1_video_update();
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
 static uint16_t vdp1_color_calculate(uint16_t,uint16_t,unsigned);
 void vdp1_draw_color(int,int,uint16_t);
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
  assert(l.lopr==address&&l.copr==address&&!s->cef&&s->bef);
  assert(l.framebuffer_current_draw==(bank^1)&&l.framebuffer_current_display==bank);++commands;
 }
 // A VBlank in manual mode is not a bank change and cannot overwrite BEF.
 for(bool previous : {false,true}){
  s->bef=previous;s->cef=!previous;s->m_vdp1_regs[1]=2;s->m_vdp1_regs[2]=0;
  s->m_vdp1_legacy.fbcr_accessed=0;s->vdp1_video_update();assert(s->bef==previous);++commands;
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
 unsigned colors=0,texture=0;
 // Exhaust all component pairs and carry/MSB combinations independently.
 for(unsigned component=0;component<3;++component)for(unsigned src=0;src<32;++src)
 for(unsigned dst=0;dst<32;++dst)for(unsigned sm=0;sm<2;++sm)for(unsigned dm=0;dm<2;++dm)
 for(unsigned mode : {0u,1u,2u,3u,4u,6u,7u}){
  uint16_t a=(src<<(component*5))|(sm<<15),b=(dst<<(component*5))|(dm<<15),expected;
  switch(mode&3){
   case 0:expected=a;break;
   case 1:expected=dm?0x8000|((dst/2)<<(component*5)):b;break;
   case 2:expected=(sm<<15)|((src/2)<<(component*5));break;
   default:expected=dm?0x8000|(((src+dst)/2)<<(component*5)):a;break;
  }
  assert(s->vdp1_color_calculate(a,b,mode)==expected);++colors;
 }
 // Shading saturation and MSB preservation; evaluate out of order and twice
 // to catch interpolation advanced only by successful writes.
 auto &shade=s->vdp1_shading_data->scanline[0];
 for(unsigned channel=0;channel<3;++channel)for(unsigned original=0;original<32;++original)
 for(int correction=0;correction<32;++correction)for(unsigned msb : {0u,0x8000u}){
  shade={};shade.r[0]=shade.g[0]=shade.b[0]=16<<16;
  if(channel==0){shade.r[0]=0;shade.dr=1<<16;}
  if(channel==1){shade.g[0]=0;shade.dg=1<<16;}
  if(channel==2){shade.b[0]=0;shade.db=1<<16;}
  unsigned value=(original<<(channel*5))|msb;
  unsigned expected=(std::clamp(int(original)+correction-16,0,31)<<(channel*5))|msb;
  assert(s->vdp1_apply_gouraud_shading(correction,0,value)==expected);
  assert(s->vdp1_apply_gouraud_shading(correction,0,value)==expected);++colors;
 }
 // MON preserves all existing destination color bits; source controls only
 // coverage, including texture transparency and mesh.
 s->m_vdp1_legacy.system_cliprect.set(0,1023,0,511);s->current_sprite.ispoly=1;
 for(uint16_t background : {uint16_t(0),uint16_t(0x1234),uint16_t(0x7fff),uint16_t(0xffff)}){
  s->current_sprite.CMDPMOD=0x8000;s->current_sprite.CMDCOLR=0x8321;
  s->m_vdp1_legacy.framebuffer_draw_lines[0][0]=background;s->drawpixel_generic(0,0,0,0);
  assert(s->m_vdp1_legacy.framebuffer_draw_lines[0][0]==(background|0x8000));++colors;
 }
 // All legal combinations use saturated Gouraud BEFORE the half operation.
 for(unsigned mode : {0u,1u,2u,3u,4u,6u,7u})for(unsigned level=0;level<32;++level){
  shade={};shade.r[0]=shade.g[0]=shade.b[0]=31<<16;
  s->current_sprite.CMDPMOD=mode|0x40;s->current_sprite.CMDCOLR=0x8000|level|(level<<5)|(level<<10);
  auto &pixel=s->m_vdp1_legacy.framebuffer_draw_lines[0][0];pixel=0x8421;
  unsigned value=mode&4?std::min(level+15,31u):level;
  unsigned result=mode%4==1?0:mode%4==2?value/2:mode%4==3?(value+1)/2:value;
  s->drawpixel_generic(0,0,0,0);
  assert(pixel==(0x8000|result|(result<<5)|(result<<10)));++colors;
 }
 // Mesh-suppressed dots must not compress the shading ramp.
 shade={};shade.g[0]=shade.b[0]=16<<16;shade.dr=1<<16;
 s->current_sprite.CMDPMOD=0x144;s->current_sprite.CMDCOLR=0x8010;
 for(unsigned x=0;x<32;++x){
  auto &pixel=s->m_vdp1_legacy.framebuffer_draw_lines[0][x];pixel=0x7777;
  s->drawpixel_generic(x,0,0,0);assert(pixel==((x&1)?0x7777:0x8000|x));++colors;
 }
 // Lookup data wraps at physical 512-KiB VRAM, even when the table straddles it.
 s->current_sprite.ispoly=0;s->current_sprite.CMDPMOD=0x88;s->current_sprite.CMDCOLR=0xffff;
 s->m_vdp1_legacy.gfx_decode[0x100]=0xf0;
 s->m_vdp1_legacy.gfx_decode[0x16]=0x8b;s->m_vdp1_legacy.gfx_decode[0x17]=0xad;
 s->drawpixel_generic(0,0,0x100,0);assert(s->m_vdp1_legacy.framebuffer_draw_lines[0][0]==0x8bad);++texture;
 // Full production normal-sprite loop: two ENDs terminate each source row,
 // independently of SPD and in all read directions. ECD disables termination.
 for(unsigned mode=0;mode<6;++mode)for(unsigned direction=0;direction<4;++direction)
 for(unsigned ecd=0;ecd<2;++ecd)for(unsigned spd=0;spd<2;++spd)
 for(unsigned first=0;first<8;++first)for(unsigned second=first+1;second<8;++second){
  auto &l=s->m_vdp1_legacy;l.local_x=l.local_y=0;
  s->current_sprite.CMDCTRL=direction<<4;s->current_sprite.CMDPMOD=(mode<<3)|(ecd<<7)|(spd<<6);
  s->current_sprite.CMDSIZE=0x102;s->current_sprite.CMDSRCA=0x20;
  s->current_sprite.CMDXA=s->current_sprite.CMDYA=0;s->current_sprite.CMDCOLR=mode==1?0x80:0x8000;
  s->current_sprite.ispoly=0;
  for(unsigned i=0;i<16;++i){
   unsigned x=i%8;bool end=x==first||x==second;unsigned val=mode<2?(end?15:1):mode<5?(end?255:1):(end?0x7fff:0x8001);
   if(mode<2){auto &byte=l.gfx_decode[0x100+i/2];if(!(i&1))byte=val<<4;else byte|=val;}
   else if(mode<5)l.gfx_decode[0x100+i]=val;
   else {l.gfx_decode[0x100+2*i]=val>>8;l.gfx_decode[0x101+2*i]=val;}
  }
  for(unsigned i=0;i<16;++i){l.gfx_decode[0x400+2*i]=0x80;l.gfx_decode[0x401+2*i]=1;}
  for(int y=0;y<2;++y)std::fill_n(l.framebuffer_draw_lines[y],8,0x5555);
  s->raster_normal(l.system_cliprect,0);
  for(unsigned y=0;y<2;++y){unsigned ends=0;
   for(unsigned x=0;x<8;++x){unsigned u=(direction&1)?7-x:x;bool end=u==first||u==second;
    if(end)++ends;bool written=ecd||(!end&&ends<2);
    assert((l.framebuffer_draw_lines[y][x]!=0x5555)==written);
   }
  }
  ++texture;
 }
 std::cout<<colors<<" color/shading and "<<texture<<" normal-sprite END scenarios passed\n";
 std::cout<<commands<<" VDP1 command/completion, "<<fb<<" framebuffer and "<<clipping<<" pixel-clipping scenarios passed\n";
}
'''.replace('// TYPES',types).replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-vdp1-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

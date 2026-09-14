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
p.add_argument('--render-mutation',choices=('mon','round','gouraud','endcode','rotation','parameter_b','scale_anchor','scaled_end','line_gouraud','texture_step','eos','line_coverage','quad_coverage','quad_edge','field_boundary','erase_latch','erase_budget','erase_bank','erase_snapshot'))
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
functions+='\n'.join(extract(current,s) for s in ('uint32_t saturn_state::vdp1_vblank_erase_capacity()', 'void saturn_state::vdp1_begin_vblank_erase()', 'void saturn_state::vdp1_finish_vblank_erase()', 'void saturn_state::vdp1_cancel_erase()', 'int saturn_state::vdp1_scaled_coordinate(', 'bool saturn_state::vdp1_texture_sample_visible(', 'void saturn_state::vdp1_fill_line(', 'void saturn_state::vdp1_latch_framebuffer_config()', 'void saturn_state::vdp1_request_termination()', 'TIMER_CALLBACK_MEMBER(saturn_state::vdp1_terminate)', 'std::array<uint32_t, 6> saturn_state::vdp1_rotation_parameters()', 'int saturn_state::vdp1_rotation_coordinate(', 'uint16_t saturn_state::vdp1_display_pixel(', 'uint16_t saturn_state::vdp1_color_calculate(', 'void saturn_state::vdp1_draw_color(', 'uint16_t saturn_state::vdp1_read_pixel(', 'void saturn_state::vdp1_write_pixel(', 'void saturn_state::vdp1_clear_framebuffer(', 'void saturn_state::vdp1_change_framebuffers()', 'void saturn_state::vdp1_video_update()', 'void saturn_state::vdp1_set_framebuffer_config()', 'void saturn_state::vdp1_state_save_postload()', 'void saturn_state::vdp1_prepare_framebuffers()', 'void saturn_state::vdp1_regs_w('))+'\n'
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
functions += extract(current, 'void saturn_state::vdp1_draw_scaled_sprite(').replace(
    'saturn_state::vdp1_draw_scaled_sprite', 'saturn_state::raster_scaled') + '\n'
functions+=extract(current,'void saturn_state::vdp1_draw_scaled_pixels(').replace('saturn_state::vdp1_draw_scaled_pixels','saturn_state::raster_scaled_pixels')+'\n'
functions+=extract(current,'void saturn_state::vdp1_draw_segment(').replace('saturn_state::vdp1_draw_segment','saturn_state::raster_segment')+'\n'
functions+=extract(current,'void saturn_state::vdp1_draw_quad_pixels(')+'\n'
functions+=extract(current,'void saturn_state::vdp1_draw_distorted_sprite(').replace('saturn_state::vdp1_draw_distorted_sprite','saturn_state::raster_distorted')+'\n'
functions+=extract(current,'TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)').replace('TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)','void saturn_state::scanline_tick(int param)')+'\n'
shader_signatures=('uint8_t saturn_state::read_gouraud_table()', 'void saturn_state::vdp1_setup_shading(', 'void saturn_state::vdp1_setup_shading_for_line(', 'void saturn_state::vdp1_setup_shading_for_slope(')
functions+='\n'.join(extract(current,sig) for sig in shader_signatures)+'\n'
for name in ('line','poly_line'):
    functions+=extract(current,'void saturn_state::vdp1_draw_'+name+'(').replace('saturn_state::vdp1_draw_'+name,'saturn_state::raster_'+name)+'\n'
if a.render_mutation:
    mutations = {
        'mon': ('line[word] |= 0x8000;', 'vdp1_write_pixel(x, y, src | 0x8000);'),
        'round': ('(src & dst & 0x0421)', '0'),
        'gouraud': ('const int64_t dx = int64_t(x) - (line.x[0] >> FRAC_SHIFT);', 'const int64_t dx = 0;'),
        'endcode': ('if (++end_codes == 2)', 'if (++end_codes == 99)'),
        'rotation': ('const int sx = vdp1_rotation_coordinate(rotation[0], rotation[2], rotation[4], x, y);', 'const int sx = x;'),
        'erase_budget': ('unsigned remaining = v.vblank_erase_budget;', 'unsigned remaining = 0xffffffff;'),
        'erase_bank': ('v.vblank_erase_bank = v.framebuffer_current_display;', 'v.vblank_erase_bank = v.framebuffer_current_draw;'),
        'erase_snapshot': ('v.framebuffer[v.vblank_erase_bank][address] = v.vblank_erase_data;', 'v.framebuffer[v.vblank_erase_bank][address] = v.ewdr;'),
        'field_boundary': ('if (scanline == 0)', 'if (scanline == vblank_line * y_step)'),
        'erase_latch': ('m_vdp1_legacy.ewdr = VDP1_EWDR;', 'm_vdp1_legacy.ewdr = 0;'),
        'quad_coverage': ('extra = edge_coverage;', 'extra = false;'),
        'quad_edge': ('e.phase = wrap(~longest);', 'e.phase = 0;'),
        'line_coverage': ('const int target = edge_coverage ? -1 : ((horizontal ? dx : dy) < 0 ? 1 : 0);', 'const int target = edge_coverage ? -1 : 0;'),
        'texture_step': ('const int initial = shrink ? source - 2 * destination - int(reverse) : -destination + int(reverse);', 'const int initial = 0;'),
        'eos': ('u * 2 + m_vdp1_legacy.draw_eos', 'u * 2'),
        'line_gouraud': ('colors[i], colors[(i + 1) & 3]', 'colors[0], colors[1]'),
        'scaled_end': ('return (reverse ? width - 1 - u : u) < limit;', 'return true;'),
        'scale_anchor': ('right = left + width;', 'left = vdp1_coord(left - m_vdp1_legacy.local_x) + m_vdp1_legacy.local_x; right = left + width;'),
        'parameter_b': ('0xffbe', '0xfffe'),
    }
    before,after=mutations[a.render_mutation]
    assert functions.count(before)==(2 if a.render_mutation=='eos' else 1)
    functions=functions.replace(before,after)
# The unrelated periodic scanline path must no longer manufacture a draw-end IRQ.
assert 'm_vdp1_texture_end.fill(-1);' in extract(current,'void saturn_state::vdp1_fill_quad(')
assert 'vdp1_fill_line(' in extract(current,'void saturn_state::vdp1_fill_slope(')
assert 'vdp1_end_w' not in extract(current,'TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)')
for field in ('drawing','command_position','command_return'):
    assert f'save_item(NAME(m_vdp1_legacy.{field}));' in current
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::machine_reset()')
assert 'vdp1_abort_draw();' in extract(current,'void saturn_state::system_reset_w(')
assert 'vdp1_request_termination();' in extract(current,'void saturn_state::vdp1_regs_w(')
for bank in (0,1):
    for name in ('framebuffer','field_framebuffer'):
        assert f'save_pointer(NAME(m_vdp1_legacy.{name}[{bank}]), 0x20000);' in current
for name in ('field_valid','draw_field','draw_eos','erase_upper_left','erase_lower_right'):
    assert f'save_item(NAME(m_vdp1_legacy.{name}));' in current
for name in ('pending','active','bank','stride','data','left','right','top','bottom','budget'):
    assert f'save_item(NAME(m_vdp1_legacy.vblank_erase_{name}));' in current
for signature in ('void saturn_state::machine_reset()', 'void saturn_state::system_reset_w('):
    assert 'vdp1_cancel_erase();' in extract(current,signature)
types=extract(current,'struct shaded_point {')+';'+extract(header,'struct _gouraud_shading {')+' gouraud_shading;'+extract(header,'struct vdp1_sprite_list')+' current_sprite;'
types+='\n'+extract(header,'struct vdp1_poly_scanline {')+';\n'+extract(header,'struct vdp1_poly_scanline_data {')+';'
types+='\n'+extract(header,'struct spoint {')+';'
harness=r'''
#include <algorithm>
#include <array>
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
#define VDP1_EOS ((m_vdp1_regs[1]>>4)&1)
#define VDP1_DIL ((m_vdp1_regs[1]>>2)&1)
#define VDP1_DIE ((m_vdp1_regs[1]>>3)&1)
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
struct word_buffer:std::vector<uint16_t> {
 using std::vector<uint16_t>::vector;
 uint16_t *get(){return data();}const uint16_t *get() const{return data();}
};
struct vdp2 {bool large=false;int lsmd=0;bool get_vramsz(){return large;}int get_lsmd(){return lsmd;}int hreso=0,total=263,vblank_start=224;int get_hreso(){return hreso;}bool is_pal() const {return total/(lsmd==3?2:1)==313;}int get_vblank_start_position(){return vblank_start;}int get_ystep_count(){return 1;}};
struct saturn_state {
 // TYPES
 timer timer_,terminate_;cpu cpu_;scu scu_;cpu *m_maincpu=&cpu_;scu *m_scu=&scu_;
 struct legacy {
  timer *draw_end_timer=nullptr,*terminate_timer=nullptr;
  bool drawing=false;int command_position=0,command_return=-1;
  uint16_t lopr=0,copr=0;
  int local_x=0,local_y=0,framebuffer_current_draw=0,framebuffer_current_display=1;
  int framebuffer_clear_on_next_frame=0;
  int framebuffer_width=1024,framebuffer_height=512,framebuffer_mode=0,framebuffer_double_interlace=0,fbcr_accessed=0;
  uint16_t ewdr=0;
  rectangle user_cliprect,system_cliprect;
  word_buffer framebuffer[2]={word_buffer(0x20000),word_buffer(0x20000)};
  word_buffer field_framebuffer[2]={word_buffer(0x20000),word_buffer(0x20000)};
  bool field_valid[2]{};uint8_t draw_field=0,draw_eos=0;uint16_t erase_upper_left=0,erase_lower_right=0;
  bool vblank_erase_pending=false,vblank_erase_active=false;
  uint8_t vblank_erase_bank=0;
  uint16_t vblank_erase_stride=512,vblank_erase_data=0,vblank_erase_left=0,vblank_erase_right=0,vblank_erase_top=0,vblank_erase_bottom=0;
  uint32_t vblank_erase_budget=0;
  byte_buffer gfx_decode=byte_buffer(0x100000,0x11);
  uint16_t *framebuffer_draw_lines[512]{},*framebuffer_display_lines[512]{};
 } m_vdp1_legacy;
 std::vector<uint32_t> m_vdp1_vram=std::vector<uint32_t>(0x80000/4);
 const rectangle *last_clip=nullptr;
 uint16_t m_vdp1_regs[16]{},m_vdp2_regs[128]{};
 vdp2 vdp2_;vdp2 *m_vdp2=&vdp2_;
 std::vector<uint32_t> m_vdp2_vram=std::vector<uint32_t>(0x40000);
 std::array<uint32_t,6> vdp1_rotation_parameters() const;
 static int vdp1_rotation_coordinate(uint32_t,uint32_t,uint32_t,int,int);
 uint16_t vdp1_display_pixel(int,int,const std::array<uint32_t,6>&) const;
 unsigned draws=0;int tvm=0,m_sprite_colorbank=0;bool cef=false,bef=false;
 saturn_state(){m_vdp1_legacy.draw_end_timer=&timer_;m_vdp1_legacy.terminate_timer=&terminate_;for(unsigned y=0;y<512;++y)m_vdp1_legacy.framebuffer_draw_lines[y]=m_vdp1_legacy.framebuffer[0].data()+((y*1024)&0x1ffff);}
 void CEF_0(){cef=false;}void CEF_1(){cef=true;}
 void BEF_0(){bef=false;}void BEF_1(){bef=true;}
 void clear_gouraud_shading(){}void vdp1_set_drawpixel(){}
 int vdp1_coord(int v){return int16_t((v&0x1fff)<<3)>>3;}
 std::unique_ptr<vdp1_poly_scanline_data> vdp1_shading_data=std::make_unique<vdp1_poly_scanline_data>();
 uint16_t vdp1_apply_gouraud_shading(int,int,uint16_t);
 bool vdp1_is_end_code(int,int) const;
 int x2s(int);int y2s(int);
 void raster_normal(const rectangle&,int);
 uint32_t vdp1_vblank_erase_capacity() const;
 void vdp1_begin_vblank_erase();void vdp1_finish_vblank_erase();void vdp1_cancel_erase();
 void scanline_tick(int);
 void raster_scaled(const rectangle&);
 static int vdp1_scaled_coordinate(int,int,int,bool);
 void raster_scaled_pixels(const rectangle&,int,int,int,const spoint*);
 void vdp1_draw_scaled_pixels(const rectangle &r,int a,int w,int,const spoint *q){vdp1_fill_quad(r,a,w,q);}
 std::array<int16_t,256> m_vdp1_texture_end{};
 bool vdp1_texture_sample_visible(int,int,int);
 void vdp1_fill_line(const rectangle&,int,int,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t);
 std::array<spoint,4> quad{};
 std::vector<std::array<uint16_t,2>> shaded_edges;
 void vdp1_fill_quad(const rectangle&,int,int,const spoint *q){
  std::copy_n(q,4,quad.begin());
  if(current_sprite.CMDPMOD&4)shaded_edges.push_back({vdp1_apply_gouraud_shading(q[0].x,q[0].y,0xc210),vdp1_apply_gouraud_shading(q[1].x,q[1].y,0xc210)});
 }
 uint8_t read_gouraud_table();
 void vdp1_setup_shading(const spoint*,const rectangle&);
 void raster_segment(const rectangle&,const spoint&,const spoint&,uint16_t,uint16_t,bool=false,int=-1,int=0);
 void vdp1_draw_quad_pixels(const rectangle&,int,int,const spoint*);
 void vdp1_draw_segment(const rectangle &r,const spoint &a,const spoint &b,uint16_t ca,uint16_t cb,bool coverage=false,int row=-1,int width=0){
  if(coverage)raster_segment(r,a,b,ca,cb,coverage,row,width);
  else shaded_edges.push_back({uint16_t(ca|0x8000),uint16_t(cb|0x8000)});
 }
 void raster_distorted(const rectangle&);
 void raster_line(const rectangle&);void raster_poly_line(const rectangle&);
 SHADER_PROTOTYPES
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
 void vdp1_process_list();void vdp1_draw_end(int);void vdp1_abort_draw();void vdp1_request_termination();void vdp1_terminate(int);
 void vdp1_prepare_framebuffers();void vdp1_state_save_postload();void vdp1_change_framebuffers();
 void vdp1_regs_w(offs_t,uint16_t,uint16_t);
 void vdp1_latch_framebuffer_config();void vdp1_set_framebuffer_config();
 void vdp1_framebuffer0_w(offs_t,uint32_t,uint32_t);
 uint32_t vdp1_framebuffer0_r(offs_t,uint32_t);
 bool vdp1_pixel_visible(int,int) const;
 void drawpixel_poly(int,int,int,int);void drawpixel_8bpp_trans(int,int,int,int);
 void drawpixel_4bpp_trans(int,int,int,int);void drawpixel_4bpp_notrans(int,int,int,int);
 void drawpixel_generic(int,int,int,int);
 static uint16_t vdp1_color_calculate(uint16_t,uint16_t,unsigned);
 void vdp1_draw_color(int,int,uint16_t);
 void fire(){if(timer_.delay!=-1){timer_.delay=-1;vdp1_draw_end(0);}}
 void advance(int clocks){
  while(clocks>0){
   int next=clocks;
   if(timer_.delay>=0)next=std::min(next,timer_.delay);
   if(terminate_.delay>=0)next=std::min(next,terminate_.delay);
   if(timer_.delay>=0)timer_.delay-=next;if(terminate_.delay>=0)terminate_.delay-=next;clocks-=next;
   if(terminate_.delay==0){terminate_.delay=-1;vdp1_terminate(0);}
   if(timer_.delay==0){timer_.delay=-1;vdp1_draw_end(0);}
  }
 }
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
  bool requested=offset==6&&mask!=0;
  assert(s->m_vdp1_legacy.drawing&&s->timer_.delay==16);
  assert(s->terminate_.delay==(requested?30:-1));++commands;
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
 // ENDR remains live until its scheduled deadline at each phase relative
 // to the command fetch clock, then cancels further work without END/IRQ.
 for(int phase=0;phase<16;++phase){
  for(unsigned n=0;n<8;++n)s->m_vdp1_vram[n*8]=n==7?0x80000000:0;
  s->draws=0;s->scu_.irqs=0;s->vdp1_process_list();s->advance(phase);
  s->vdp1_regs_w(6,0,0xffff);assert(s->terminate_.delay==30);
  s->advance(29);assert(s->m_vdp1_legacy.drawing&&!s->cef);
  s->advance(1);assert(!s->m_vdp1_legacy.drawing&&!s->cef&&s->scu_.irqs==0);
  assert(s->timer_.delay==-1&&s->draws==unsigned((phase+29)/16));
  s->vdp1_process_list();assert(s->terminate_.delay==-1&&s->m_vdp1_legacy.command_position==0);++commands;
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
  assert(l.framebuffer_draw_lines[height-1]==l.framebuffer[bank].data()+(((height-1)*(width/2))&0x1ffff));
  assert(l.framebuffer_display_lines[height-1]==l.framebuffer[bank^1].data()+(((height-1)*(width/2))&0x1ffff));
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
  l.ewdr=0x1234;s->m_vdp1_regs[4]=(1<<9)|3;s->m_vdp1_regs[5]=(2<<9)|3;l.erase_upper_left=s->m_vdp1_regs[4];l.erase_lower_right=s->m_vdp1_regs[5];
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
 unsigned rotation_cases=0;
 // Rotation is always parameter A, independent of RPTA bit6 and VRAM size.
 s->tvm=2;
 for(unsigned i=0;i<s->m_vdp2_vram.size();++i)s->m_vdp2_vram[i]=i^0x12345678;
 for(bool large : {false,true})for(unsigned reg : {0u,0x40u,0x170u,0x7fffeu}){
  s->vdp2_.large=large;s->m_vdp2_regs[0xbc/2]=reg>>16;s->m_vdp2_regs[0xbe/2]=reg;
  auto p=s->vdp1_rotation_parameters();unsigned fields[]={0,4,12,16,20,24};
  unsigned base=(reg*2)&~0x83u,mask=large?0xfffff:0x7ffff;
  for(unsigned i=0;i<6;++i)assert(p[i]==s->m_vdp2_vram[((base+fields[i])&mask)/4]);++rotation_cases;
 }
 // Precision must be discarded before accumulation. The signed 20-bit
 // accumulator wraps while out-of-framebuffer samples are transparent.
 assert(s->vdp1_rotation_coordinate(0,0,64,1024,0)==0);
 assert(s->vdp1_rotation_coordinate(0,0,128,511,0)==0);
 assert(s->vdp1_rotation_coordinate(0,0,128,512,0)==1);
 assert(s->vdp1_rotation_coordinate(0,0x7ff80,0,0,512)==-1);
 assert(s->vdp1_rotation_coordinate(0x3ff0000,0,65536,1,0)==-1024);
 assert(s->vdp1_rotation_coordinate(0x0c000000,0,0,0,0)==0);
 rotation_cases+=6;
 for(unsigned bank=0;bank<2;++bank)for(unsigned i=0;i<0x20000;++i)
  s->m_vdp1_legacy.framebuffer[bank][i]=0x8000|((i+bank*73)&0x7fff);
 for(unsigned mode : {2u,3u})for(unsigned bank=0;bank<2;++bank)for(unsigned transform=0;transform<5;++transform){
  s->tvm=mode;s->m_vdp1_legacy.framebuffer_current_display=bank;
  std::array<uint32_t,6> p{};
  switch(transform){
   case 0:p={0,0,0,65536,65536,0};break;
   case 1:p={uint32_t(-2*65536),3*65536,0,65536,65536,0};break;
   case 2:p={511*65536,0,uint32_t(-65536),0,0,65536};break;
   case 3:p={511*65536,255*65536,0,uint32_t(-65536),uint32_t(-65536),0};break;
   case 4:p={32768,32768,0,32768,32768,0};break;
  }
  for(int y : {0,1,255,256,511,512})for(int x : {0,1,2,255,256,511,512,1023}){
   int sx=x,sy=y;
   switch(transform){case 1:sx=x-2;sy=y+3;break;case 2:sx=511-y;sy=x;break;case 3:sx=511-x;sy=255-y;break;case 4:sx=(x+1)/2;sy=(y+1)/2;break;}
   // This sample range crosses the signed accumulator only at +1024.
   if(sx>=1024)sx-=2048;if(sy>=1024)sy-=2048;
   unsigned expected=0;
   if(sx>=0&&sx<512&&sy>=0&&sy<int(mode==3?512:256)){
    unsigned index=sy*(mode==3?256:512)+(mode==3?sx/2:sx);
    unsigned word=0x8000|((index+bank*73)&0x7fff);
    expected=mode==3?((word>>((sx&1)?0:8))&255):word;
   }
   assert(s->vdp1_display_pixel(x,y,p)==expected);++rotation_cases;
  }
 }
 std::cout<<rotation_cases<<" rotated readout/parameter/precision scenarios passed\n";
 unsigned texture_step_cases=0;
 // Iterative error-accumulator oracle, independent of the production division.
 auto texture_oracle=[](int source,int dots,int pixel,bool reverse){
  if(source<=1)return 0;
  int value=reverse?source-1:0,inc=reverse?-1:1;
  int numerator=source-1,denominator=dots,err;
  if(dots<=numerator){++numerator;err=source-1-2*dots+!reverse;}
  else {--denominator;err=-dots+reverse;}
  for(int i=0;i<=pixel;++i){
   while(err>=0){value+=inc;err-=2*denominator;}
   if(i==pixel)return value;err+=2*numerator;
  }return value;
 };
 for(int source=1;source<=64;++source)for(int dots=1;dots<=80;++dots)for(bool reverse : {false,true})for(int i=0;i<dots;++i){
  assert(s->vdp1_scaled_coordinate(source,dots,i,reverse)==texture_oracle(source,dots,i,reverse));++texture_step_cases;
 }
 // Primary p.82: eight-dot source reduced to three dots.
 assert(s->vdp1_scaled_coordinate(8,3,0,false)==1);
 assert(s->vdp1_scaled_coordinate(8,3,1,false)==4);
 assert(s->vdp1_scaled_coordinate(8,3,2,false)==6);
 // Actual scaled readout, both geometry directions, independent texture flips,
 // HSS/EOS, source END values, all six modes, clipping and vertical scaling.
 for(int format : {0,1,3})for(bool ecd : {false,true})for(int mode=0;mode<6;++mode)for(int dots : {1,3,8,13})for(bool hss : {false,true})for(int eos=0;eos<2;++eos)
 for(int direction=0;direction<4;++direction)for(bool invert : {false,true}){
  auto &l=s->m_vdp1_legacy;auto &c=s->current_sprite;
  if(format&&mode==5)continue; // RGB texture mode is prohibited in 8-bit display.
  s->tvm=format;l.framebuffer_double_interlace=0;l.framebuffer_current_draw=0;l.framebuffer_width=format==1?1024:512;l.framebuffer_height=format==3?512:256;
  s->vdp1_prepare_framebuffers();l.system_cliprect.set(2,31,0,7);
  std::fill(l.framebuffer[0].begin(),l.framebuffer[0].end(),0x5555);
  std::fill(l.gfx_decode.begin(),l.gfx_decode.end(),0);
  c.CMDPMOD=(mode<<3)|(hss?0x1000:0)|(ecd?0x80:0);c.CMDCTRL=(direction<<4)|1;c.CMDCOLR=mode==1?0x100:0x8000;c.ispoly=0;
  s->m_vdp1_regs[1]=eos<<4;l.draw_eos=eos;
  if(mode==1)for(int i=0;i<16;++i){l.gfx_decode[0x800+i*2]=0x80;l.gfx_decode[0x801+i*2]=i;}
  for(int v=0;v<4;++v)for(int u=0;u<8;++u){
   int index=v*8+u;bool end=u==1||u==5;int color=1+v;
   if(mode<2)l.gfx_decode[index/2]|=(end?15:color)<<((index&1)?0:4);
   else if(mode<5)l.gfx_decode[index]=end?255:color;
   else {l.gfx_decode[index*2]=end?0x7f:0x80;l.gfx_decode[index*2+1]=end?255:color;}
  }
  saturn_state::spoint q[4]{};q[0].x=invert?dots-1:0;q[1].x=invert?0:dots-1;q[0].y=invert?6:0;q[3].y=invert?0:6;
  s->drawpixel=&saturn_state::drawpixel_generic;uint16_t saved_mode=c.CMDPMOD;
  s->raster_scaled_pixels(l.system_cliprect,0,8,4,q);assert(c.CMDPMOD==saved_mode);
  bool reduced=hss&&dots<8;
  for(int y=0;y<7;++y)for(int x=0;x<dots;++x){
   int u=texture_oracle(reduced?4:8,dots,invert?dots-1-x:x,direction&1);if(reduced)u=2*u+eos;
   int v=texture_oracle(4,7,invert?6-y:y,direction&2);
   bool end=u==1||u==5;bool visible=x>=2&&(reduced||ecd||(!end&&((direction&1)?u>1:u<5)));
   uint16_t color=0x8000|uint16_t(1+v);
   if(end&&(reduced||ecd))color=mode<2?0x800f:mode==2?0x803f:mode==3?0x807f:mode==4?0x80ff:0x7fff;
   uint16_t expected=visible?color:0x5555;if(format)expected&=0xff;
   assert(s->vdp1_read_pixel(l.framebuffer_draw_lines[y],x)==expected);++texture_step_cases;
  }
 }
 std::cout<<texture_step_cases<<" texture-step/scaled HSS/EOS pixel cases passed\n";
 unsigned line_cases=0;
 for(int dx=-12;dx<=12;++dx)for(int dy=-12;dy<=12;++dy)for(bool gouraud : {false,true})for(bool mesh : {false,true}){
  auto &l=s->m_vdp1_legacy;auto &c=s->current_sprite;
  s->tvm=0;l.framebuffer_double_interlace=0;l.framebuffer_current_draw=0;l.framebuffer_width=512;l.framebuffer_height=256;
  s->vdp1_prepare_framebuffers();l.system_cliprect.set(6,26,6,26);
  std::fill(l.framebuffer[0].begin(),l.framebuffer[0].end(),0x5555);
  c.CMDPMOD=0xc0|(gouraud?4:0)|(mesh?0x100:0);c.CMDCOLR=0xc210;c.ispoly=1;s->drawpixel=&saturn_state::drawpixel_generic;
  saturn_state::spoint a{},b{};a.x=a.y=16;b.x=16+dx;b.y=16+dy;
  s->raster_segment(l.system_cliprect,a,b,0x001f,0x7fe0);
  uint16_t expected[32][32];for(auto &row : expected)std::fill(std::begin(row),std::end(row),0x5555);
  int major=std::max(std::abs(dx),std::abs(dy)),minor=std::min(std::abs(dx),std::abs(dy));bool horizontal=std::abs(dx)>=std::abs(dy);
  for(int i=0;i<=major;++i){
   // Closed-form nearest-integer coverage oracle; ties depend on major direction.
   int off=major?(2*minor*i+major-(((horizontal?dx:dy)>=0)?1:0))/(2*major):0;
   int x=16+(dx<0?-1:1)*(horizontal?i:off),y=16+(dy<0?-1:1)*(horizontal?off:i);
   if(x<6||x>26||y<6||y>26||(mesh&&((x^y)&1)))continue;
   uint16_t color=0xc210;
   if(gouraud){int r=texture_oracle(32,major+1,i,true),g=texture_oracle(32,major+1,i,false);color=0x8000|r|(g<<5)|(g<<10);}
   expected[y][x]=color;
  }
  for(int y=0;y<32;++y)for(int x=0;x<32;++x)assert(l.framebuffer[0][y*512+x]==expected[y][x]);++line_cases;
 }
 std::cout<<line_cases<<" integer line coverage/shading/mesh images passed\n";
 unsigned quad_cases=0;
 const int shapes[][8]={{4,4,20,4,20,20,4,20},{4,8,18,2,25,19,12,23},{4,4,20,20,20,4,4,20},
  {4,4,20,4,12,20,12,20},{12,12,12,12,12,12,12,12},{4,4,20,16,20,16,4,4},
  {-5,-3,20,5,14,25,-5,18},{20,4,4,4,4,20,20,20}};
 auto rounded=[](int numerator,int denominator,bool up){return denominator?(2*numerator+denominator-1+up)/(2*denominator):0;};
 auto gradient=[&](int a,int b,int length,int position){return std::min(a,b)+texture_oracle(std::abs(b-a)+1,length,position,b<a);};
 for(auto &shape : shapes)for(int kind=0;kind<5;++kind)for(bool mesh : {false,true})for(int direction=0;direction<4;++direction)
 for(bool hss : {false,true})for(int eos=0;eos<2;++eos)for(int clipping=0;clipping<3;++clipping){
  auto &l=s->m_vdp1_legacy;auto &c=s->current_sprite;s->tvm=0;
  l.framebuffer_double_interlace=0;l.framebuffer_current_draw=0;l.framebuffer_width=512;l.framebuffer_height=256;
  s->vdp1_prepare_framebuffers();l.system_cliprect.set(3,26,3,26);l.user_cliprect.set(8,20,8,20);
  std::fill(l.framebuffer[0].begin(),l.framebuffer[0].end(),0xffff);
  bool textured=kind>=3;c.ispoly=!textured;c.CMDCTRL=(direction<<4)|(textured?2:4);
  c.CMDPMOD=(textured?(4<<3):0)|(kind==4?0:0x80)|(textured?0:0x40)|(kind==1?3:kind==2?4:0)|
    (mesh?0x100:0)|(hss&&textured?0x1000:0)|(clipping?0x400:0)|(clipping==2?0x200:0);
  c.CMDCOLR=textured?0x8000:kind==2?0xc210:0x8421;c.CMDSRCA=0;c.CMDGRDA=0x200;s->m_vdp1_regs[1]=eos<<4;l.draw_eos=eos;
  const uint16_t vertex_colors[4]={0x001f,0x7c00,0x03e0,0x4210};
  s->m_vdp1_vram[0x400]=(uint32_t(vertex_colors[0])<<16)|vertex_colors[1];
  s->m_vdp1_vram[0x401]=(uint32_t(vertex_colors[2])<<16)|vertex_colors[3];
  for(int v=0;v<4;++v)for(int u=0;u<8;++u)l.gfx_decode[v*8+u]=(kind==4&&(u==1||u==5))?255:v*8+u+1;
  saturn_state::spoint q[4]{};for(int i=0;i<4;++i){q[i].x=shape[i*2];q[i].y=shape[i*2+1];}
  s->drawpixel=&saturn_state::drawpixel_generic;uint16_t saved=c.CMDPMOD;
  l.local_x=l.local_y=0;c.CMDSIZE=0x0104;
  c.CMDXA=q[0].x;c.CMDYA=q[0].y;c.CMDXB=q[1].x;c.CMDYB=q[1].y;
  c.CMDXC=q[2].x;c.CMDYC=q[2].y;c.CMDXD=q[3].x;c.CMDYD=q[3].y;
  s->raster_distorted(l.system_cliprect);assert(c.CMDPMOD==saved);
  uint16_t expected[32][32];for(auto &row : expected)std::fill(std::begin(row),std::end(row),0xffff);
  int ex[2],ey[2],length[2],longest=0;
  for(int i=0;i<2;++i){ex[i]=q[3-i].x-q[i].x;ey[i]=q[3-i].y-q[i].y;length[i]=std::max(std::abs(ex[i]),std::abs(ey[i]));longest=std::max(longest,length[i]);}
  for(int row=0;row<=longest;++row){
   int px[2],py[2],edge_colors[2][3]{};
   for(int i=0;i<2;++i){
    int n=rounded(length[i]*row,longest,(std::abs(ex[i])>=std::abs(ey[i])?ex[i]:ey[i])<0);
    px[i]=q[i].x+(ex[i]<0?-1:1)*rounded(std::abs(ex[i])*n,length[i],ey[i]<0);
    py[i]=q[i].y+(ey[i]<0?-1:1)*rounded(std::abs(ey[i])*n,length[i],ex[i]<0);
    if(kind==2)for(int ch=0;ch<3;++ch)edge_colors[i][ch]=gradient((vertex_colors[i]>>(5*ch))&31,(vertex_colors[3-i]>>(5*ch))&31,length[i]+1,n);
   }
   int dx=px[1]-px[0],dy=py[1]-py[0],major=std::max(std::abs(dx),std::abs(dy)),minor=std::min(std::abs(dx),std::abs(dy));
   bool horizontal=std::abs(dx)>=std::abs(dy),reduced=hss&&textured&&major+1<8;
   int v=textured?texture_oracle(4,longest+1,row,direction&2):0,previous=0;
   for(int dot=0;dot<=major;++dot){
    int off=rounded(minor*dot,major,false);
    int x=px[0]+(dx<0?-1:1)*(horizontal?dot:off),y=py[0]+(dy<0?-1:1)*(horizontal?off:dot);
    int u=textured?texture_oracle(reduced?4:8,major+1,dot,direction&1):0;if(reduced)u=2*u+eos;
    bool end=kind==4&&(u==1||u==5);
    bool sample=kind!=4||reduced||(!end&&((direction&1)?u>1:u<5));
    uint16_t color=textured?(0x8000|(end?255:v*8+u+1)):0x8421;
    if(kind==2){color=0x8000;for(int ch=0;ch<3;++ch)color|=gradient(edge_colors[0][ch],edge_colors[1][ch],major+1,dot)<<(5*ch);}
    auto plot=[&](int x,int y){
     if(x<3||x>26||y<3||y>26||!sample||(mesh&&((x^y)&1)))return;
     bool inside=x>=8&&x<=20&&y>=8&&y<=20;if((clipping==1&&!inside)||(clipping==2&&inside))return;
     if(kind==1){uint16_t mixed=0x8000;for(int shift : {0,5,10})mixed|=((((expected[y][x]>>shift)&31)+((color>>shift)&31))/2)<<shift;expected[y][x]=mixed;}
     else expected[y][x]=color;
    };
    plot(x,y);
    if(dot&&off!=previous){bool same=(dx<0)==(dy<0);plot(x-(same?0:(dx<0?-1:1)),y-(same?(dy<0?-1:1):0));}
    previous=off;
   }
  }
  for(int y=0;y<32;++y)for(int x=0;x<32;++x){
   if(l.framebuffer[0][y*512+x]!=expected[y][x])std::cerr<<"quad "<<(&shape-&shapes[0])<<" kind "<<kind<<" mesh "<<mesh<<" dir "<<direction<<" hss "<<hss<<" eos "<<eos<<" clip "<<clipping<<" xy "<<x<<","<<y<<" got "<<l.framebuffer[0][y*512+x]<<" expected "<<expected[y][x]<<"\n";
   assert(l.framebuffer[0][y*512+x]==expected[y][x]);
  }++quad_cases;
 }
 std::cout<<quad_cases<<" native quad coverage/texture/color images passed\n";
 unsigned edge_cases=0;
 for(bool transpose : {false,true})for(int dx : {-8,8})for(int dy : {-8,8})for(int rotation=0;rotation<4;++rotation){
  auto &c=s->current_sprite;auto &l=s->m_vdp1_legacy;l.local_x=l.local_y=0;l.system_cliprect.set(0,63,0,63);
  c.CMDPMOD=0xc4;c.CMDGRDA=0;c.ispoly=1;
  int xs[4]={16,16+dx,16+dx,16},ys[4]={16,16,16+dy,16+dy};
  if(transpose)for(int i=0;i<4;++i)std::swap(xs[i],ys[i]);
  c.CMDXA=xs[0];c.CMDXB=xs[1];c.CMDXC=xs[2];c.CMDXD=xs[3];
  c.CMDYA=ys[0];c.CMDYB=ys[1];c.CMDYC=ys[2];c.CMDYD=ys[3];
  uint16_t colors[4];for(int i=0;i<4;++i){int v=((i+rotation)%4)*8;colors[i]=v|(v<<5)|(v<<10);}
  s->m_vdp1_vram[0]=(uint32_t(colors[0])<<16)|colors[1];s->m_vdp1_vram[1]=(uint32_t(colors[2])<<16)|colors[3];
  s->shaded_edges.clear();s->raster_line(l.system_cliprect);assert(s->shaded_edges.size()==1);
  assert(s->shaded_edges[0][0]==(0x8000|colors[0])&&s->shaded_edges[0][1]==(0x8000|colors[1]));++edge_cases;
  s->shaded_edges.clear();s->raster_poly_line(l.system_cliprect);assert(s->shaded_edges.size()==4);
  for(int i=0;i<4;++i){assert(s->shaded_edges[i][0]==(0x8000|colors[i])&&s->shaded_edges[i][1]==(0x8000|colors[(i+1)%4]));++edge_cases;}
 }
 std::cout<<edge_cases<<" line/polyline Gouraud endpoint cases passed\n";
 unsigned scaled_end_cases=0;
 for(int mode=0;mode<6;++mode)for(bool reverse : {false,true})for(int first=0;first<8;++first)for(int second=first+1;second<8;++second){
  auto &c=s->current_sprite;c.CMDPMOD=mode<<3;c.CMDCTRL=reverse?0x10:0;c.ispoly=0;
  c.CMDCOLR=0x8000;std::fill(s->m_vdp1_legacy.gfx_decode.begin(),s->m_vdp1_legacy.gfx_decode.end(),0);
  auto put=[&](int u,bool end){
   if(mode<2){unsigned shift=(u&1)?0:4;s->m_vdp1_legacy.gfx_decode[u/2]|=(end?15:1)<<shift;}
   else if(mode<5)s->m_vdp1_legacy.gfx_decode[u]=end?255:1;
   else {s->m_vdp1_legacy.gfx_decode[u*2]=end?0x7f:0x80;s->m_vdp1_legacy.gfx_decode[u*2+1]=end?0xff:1;}
  };
  for(int u=0;u<8;++u)put(u,u==first||u==second);
  s->m_vdp1_texture_end.fill(-1);
  for(int u=0;u<8;++u){
   assert(s->vdp1_texture_sample_visible(0,8,u)==(reverse?u>first:u<second));++scaled_end_cases;
  }
  // ECD bypasses row termination without reusing a stale cutoff.
  c.CMDPMOD|=0x80;for(int u=0;u<8;++u)assert(s->vdp1_texture_sample_visible(0,8,u));
 }
 // Exercise production affine spans: clipped/enlarged repeated END samples
 // cannot hide the second source END or incorrectly count the first twice.
 for(int dots : {1,3,8,16,31})for(bool reverse : {false,true})for(int left : {0,2}){
  auto &l=s->m_vdp1_legacy;s->tvm=0;l.framebuffer_double_interlace=0;l.framebuffer_width=512;l.framebuffer_height=256;
  l.framebuffer_current_draw=0;s->vdp1_prepare_framebuffers();l.system_cliprect.set(left,63,0,0);
  std::fill(l.framebuffer[0].begin(),l.framebuffer[0].end(),0x5555);
  for(int u=0;u<8;++u)l.gfx_decode[u]=(u==1||u==5)?255:1;
  s->current_sprite.CMDCTRL=reverse?0x10:0;s->current_sprite.CMDPMOD=4<<3;s->current_sprite.CMDCOLR=0x8000;s->current_sprite.ispoly=0;
  s->m_vdp1_texture_end.fill(-1);s->drawpixel=&saturn_state::drawpixel_generic;
  s->vdp1_fill_line(l.system_cliprect,0,8,0,0,(dots-1)<<16,(reverse?7:0)<<16,(reverse?0:7)<<16,0,0);
  int du=dots==1?0:((reverse?-7:7)*65536)/(dots-1);
  for(int x=0;x<dots;++x){int u=((reverse?7:0)*65536+du*x)>>16;
   bool visible=x>=left&&u!=1&&u!=5&&(reverse?u>1:u<5);
   assert(l.framebuffer[0][x]==(visible?0x8001:0x5555));++scaled_end_cases;
  }
 }
 std::cout<<scaled_end_cases<<" scaled source-END/span cases passed\n";
 unsigned scale_cases=0;
 for(int anchor : {-4096,-1000,0,4095})for(int zoom : {0,5,6,7,9,10,11,13,14,15})for(int direction=0;direction<4;++direction)
 for(int width : {0,1,2,17,1023})for(int height : {0,1,2,19,1023})for(int local : {-1024,0,511}){
  auto &c=s->current_sprite;c.CMDCTRL=(zoom<<8)|(direction<<4)|1;c.CMDPMOD=0xc0;
  c.CMDSIZE=0x0208;c.CMDXA=uint16_t(anchor);c.CMDYA=100;c.CMDXB=width|0x6000;c.CMDYB=height;
  c.CMDXC=1000;c.CMDYC=uint16_t(-100);s->m_vdp1_legacy.local_x=local;s->m_vdp1_legacy.local_y=-local;
  s->raster_scaled(s->m_vdp1_legacy.system_cliprect);
  int left=anchor+local,top=100-local,right=1000+local,bottom=-100-local;
  if(zoom){
   left-=((zoom&3)==2?width/2:(zoom&3)==3?width:0);
   top-=((zoom>>2)==2?height/2:(zoom>>2)==3?height:0);
   right=left+width;bottom=top+height;
  }
  for(unsigned i=0;i<4;++i){
   bool r=i==1||i==2,b=i>=2;
   assert(s->quad[i].x==(r?right:left)&&s->quad[i].y==(b?bottom:top));
   assert(s->quad[i].u==((r^bool(direction&1))?15:0));
   assert(s->quad[i].v==((b^bool(direction&2))?7:0));
  }++scale_cases;
 }
 std::cout<<scale_cases<<" scaled endpoint/anchor/direction cases passed\n";
 unsigned control_cases=0;
 for(int draw : {0,1}) {
  auto &l=s->m_vdp1_legacy;s->vdp1_abort_draw();s->tvm=0;l.framebuffer_mode=0;l.framebuffer_double_interlace=0;
  l.framebuffer_width=512;l.framebuffer_height=256;l.framebuffer_current_draw=draw;l.framebuffer_current_display=draw^1;
  l.draw_field=1;s->m_vdp1_regs[1]=0;s->m_vdp1_regs[2]=0;s->m_vdp1_regs[4]=0;s->m_vdp1_regs[5]=1<<9;s->m_vdp1_regs[3]=0xa55a;s->vdp1_latch_framebuffer_config();l.draw_field=1;
  s->vdp1_prepare_framebuffers();
  // An interpretation change cannot silently swap ownership or latch DIL.
  s->m_vdp1_regs[1]=8;s->vdp1_set_framebuffer_config();
  assert(l.framebuffer_current_draw==draw&&l.framebuffer_current_display==(draw^1)&&l.draw_field==1&&l.framebuffer_double_interlace==0);
  s->m_vdp1_regs[1]=0;s->vdp1_set_framebuffer_config();
  std::fill(l.framebuffer[draw].begin(),l.framebuffer[draw].end(),0x1111);
  std::fill(l.framebuffer[draw^1].begin(),l.framebuffer[draw^1].end(),0x2222);
  s->vdp1_regs_w(1,2,0xffff);s->scanline_tick(224);
  assert(l.framebuffer[draw^1][0]==0x2222&&l.framebuffer_current_draw==draw);
  s->scanline_tick(0);assert(l.framebuffer[draw^1][0]==0xa55a&&l.framebuffer[draw][0]==0x1111);
  l.framebuffer[draw^1][0]=0x3333;s->scanline_tick(0);assert(l.framebuffer[draw^1][0]==0x3333);
  // Masked-out accesses cannot submit or repeat a request.
  s->vdp1_regs_w(1,3,0);assert(!l.fbcr_accessed);
  s->vdp1_regs_w(1,0x13,0xffff);assert(l.draw_eos==0);s->m_vdp1_regs[2]=2;s->scanline_tick(224);
  assert(l.framebuffer_current_draw==draw&&!l.drawing);
  s->scanline_tick(0);assert(l.framebuffer_current_draw==(draw^1)&&l.drawing&&s->timer_.delay==16&&l.draw_eos==1);
  assert(l.framebuffer[draw^1][0]==0x3333);s->vdp1_abort_draw();
  // Persistent VBE repeats without a new FBCR write or bank change.
  s->m_vdp1_regs[0]=8;s->scanline_tick(225);assert(l.vblank_erase_active&&l.framebuffer[draw][0]==0x1111);s->scanline_tick(0);assert(l.framebuffer[draw][0]==0xa55a);
  l.framebuffer[draw][0]=0x4444;s->scanline_tick(225);s->scanline_tick(0);assert(l.framebuffer[draw][0]==0xa55a);
  s->m_vdp1_regs[0]=0;l.framebuffer[draw][0]=0x4444;s->scanline_tick(225);assert(l.framebuffer[draw][0]==0x4444);
  // Writes after the boundary leave active erase data/coordinates untouched.
  s->vdp1_regs_w(3,0x6789,0xffff);s->vdp1_regs_w(4,0x0201,0xffff);s->vdp1_regs_w(5,0x0401,0xffff);
  assert(l.ewdr==0xa55a&&l.erase_upper_left==0&&l.erase_lower_right==0x0200);
  s->vdp1_change_framebuffers();assert(l.ewdr==0x6789&&l.erase_upper_left==0x0201&&l.erase_lower_right==0x0401);
  s->vdp1_regs_w(1,8,0xffff);assert(l.framebuffer_double_interlace==0);
  s->vdp1_change_framebuffers();assert(l.framebuffer_double_interlace==1&&l.framebuffer_height==512);
  ++control_cases;
 }
 std::cout<<control_cases<<" framebuffer-control field sequences passed\n";
 unsigned erase_cases=0;
 // Exact published capacities: ST-013 Table 4.5. Horizontal high resolution
 // packs two dots per erased word and does not double the word budget.
 const int erase_table[][4]={{0,263,224,58812},{0,263,240,34684},{1,263,224,63180},{1,263,240,37260},
  {0,313,224,134212},{0,313,240,110084},{0,313,256,85956},{1,313,224,144180},{1,313,240,118260},
  {1,313,256,92340},{4,525,480,29340},{5,562,480,53136}};
 for(auto &t : erase_table)for(int mode=0;mode<=4;++mode)for(int bank=0;bank<2;++bank){
  auto &l=s->m_vdp1_legacy;s->vdp1_cancel_erase();s->tvm=mode;
  s->vdp2_.hreso=t[0];s->vdp2_.total=t[1];s->vdp2_.vblank_start=t[2]+1;s->vdp2_.lsmd=0;
  assert(s->vdp1_vblank_erase_capacity()==unsigned(t[3]));
  if(t[0]<4){s->vdp2_.hreso|=2;assert(s->vdp1_vblank_erase_capacity()==unsigned(t[3]));s->vdp2_.hreso=t[0];
   s->vdp2_.lsmd=3;s->vdp2_.total*=2;assert(s->vdp1_vblank_erase_capacity()==unsigned(t[3]));s->vdp2_.total/=2;s->vdp2_.lsmd=0;}
  l.framebuffer_current_draw=bank^1;l.framebuffer_current_display=bank;l.ewdr=0xa1b2;
  l.erase_upper_left=0;l.erase_lower_right=((mode==3?32:64)<<9)|(mode==3?511:255);
  for(auto &fb:l.framebuffer)std::fill(fb.begin(),fb.end(),0x7777);
  s->vdp1_begin_vblank_erase();assert(l.vblank_erase_active&&l.framebuffer[bank][0]==0x7777);
  s->vdp1_abort_draw();assert(l.vblank_erase_active); // ENDR is independent of erase.
  // Pending request owns the bank, fill data, format and capacity captured at
  // blank entry; later register/mode writes cannot redirect its completion.
  l.ewdr=0x4321;l.erase_upper_left=0x7fff;l.erase_lower_right=0;s->tvm=mode==3?0:3;
  s->vdp1_finish_vblank_erase();assert(!l.vblank_erase_active);
  for(unsigned i=0;i<0x20000;++i){
   assert(l.framebuffer[bank][i]==(i<unsigned(t[3])?0xa1b2:0x7777));
   assert(l.framebuffer[bank^1][i]==0x7777);
  }
  l.framebuffer[bank][0]=0x5555;s->vdp1_finish_vblank_erase();assert(l.framebuffer[bank][0]==0x5555);
  l.erase_upper_left=0;l.erase_lower_right=1<<9;s->vdp1_begin_vblank_erase();
  l.vblank_erase_pending=true;s->vdp1_cancel_erase();s->vdp1_finish_vblank_erase();
  assert(!l.vblank_erase_pending&&!l.vblank_erase_active&&l.framebuffer[bank][0]==0x5555);
  ++erase_cases;
 }
 // Mid-row exhaustion, sparse windows and restoration of a pending erase.
 // This is a state-copy oracle, not a real MAME save-manager round trip.
 for(int mode : {0,3})for(int bank=0;bank<2;++bank)for(unsigned budget : {0u,15u,16u,17u,79u,80u,81u}){
  auto &l=s->m_vdp1_legacy;s->tvm=mode;l.framebuffer_double_interlace=0;
  l.framebuffer_width=512;l.framebuffer_height=mode==3?512:256;
  l.framebuffer_current_display=bank;l.framebuffer_current_draw=bank^1;
  l.ewdr=0x1357;l.erase_upper_left=(1<<9)|3;l.erase_lower_right=(3<<9)|7;
  for(auto &fb:l.framebuffer)std::fill(fb.begin(),fb.end(),0x2468);
  s->vdp1_begin_vblank_erase();l.vblank_erase_budget=budget;
  auto restored=std::make_unique<saturn_state>();auto &r=restored->m_vdp1_legacy;
  restored->tvm=mode;r.framebuffer_width=l.framebuffer_width;r.framebuffer_height=l.framebuffer_height;
  r.framebuffer_current_display=bank;r.framebuffer_current_draw=bank^1;
  for(int i=0;i<2;++i)r.framebuffer[i]=l.framebuffer[i];
  r.vblank_erase_pending=l.vblank_erase_pending;r.vblank_erase_active=l.vblank_erase_active;r.vblank_erase_bank=l.vblank_erase_bank;
  r.vblank_erase_stride=l.vblank_erase_stride;r.vblank_erase_data=l.vblank_erase_data;r.vblank_erase_budget=l.vblank_erase_budget;
  r.vblank_erase_left=l.vblank_erase_left;r.vblank_erase_right=l.vblank_erase_right;r.vblank_erase_top=l.vblank_erase_top;r.vblank_erase_bottom=l.vblank_erase_bottom;
  restored->vdp1_state_save_postload();restored->vdp1_finish_vblank_erase();s->vdp1_finish_vblank_erase();
  unsigned stride=mode==3?256:512;
  for(unsigned i=0;i<0x20000;++i){unsigned y=i/stride,x=i%stride;
   bool erased=y>=3&&y<=7&&x>=8&&x<24&&((y-3)*16+x-8)<budget;
   assert(l.framebuffer[bank][i]==(erased?0x1357:0x2468));
   assert(r.framebuffer[bank][i]==l.framebuffer[bank][i]&&r.framebuffer[bank^1][i]==0x2468);
  }
  ++erase_cases;
 }
 // Rotated/HDTV automatic and manual erase must wait for blanking, even VBE=0.
 for(int mode : {2,3,4})for(int request : {0,2}){
  auto &l=s->m_vdp1_legacy;s->vdp1_cancel_erase();s->tvm=mode;
  s->vdp2_.hreso=0;s->vdp2_.total=263;s->vdp2_.vblank_start=224;s->vdp2_.lsmd=0;
  l.framebuffer_mode=mode;l.framebuffer_double_interlace=0;l.framebuffer_current_draw=0;l.framebuffer_current_display=1;
  l.framebuffer_width=512;l.framebuffer_height=mode==3?512:256;
  s->m_vdp1_regs[0]=0;s->m_vdp1_regs[1]=request;s->m_vdp1_regs[2]=0;s->m_vdp1_regs[3]=0x8888;s->m_vdp1_regs[4]=0;s->m_vdp1_regs[5]=1<<9;
  s->vdp1_latch_framebuffer_config();for(auto &fb:l.framebuffer)std::fill(fb.begin(),fb.end(),0x9999);
  l.fbcr_accessed=1;s->scanline_tick(0);assert(l.vblank_erase_pending);
  int displayed=l.framebuffer_current_display;
  assert(l.framebuffer[displayed][0]==0x9999&&l.framebuffer[displayed^1][0]==0x9999);
  s->scanline_tick(225);assert(l.vblank_erase_active&&!l.vblank_erase_pending&&l.framebuffer[displayed][0]==0x9999);
  s->scanline_tick(0);assert(l.framebuffer[displayed][0]==0x8888&&l.framebuffer[displayed^1][0]==0x9999);
  ++erase_cases;
 }
 s->vdp1_cancel_erase();s->vdp2_.hreso=0;s->vdp2_.total=263;s->vdp2_.vblank_start=224;
 std::cout<<erase_cases<<" bounded VBlank erase/lifecycle cases passed\n";
 unsigned field_cases=0;
 for(int mode : {0,1}){
  auto &l=s->m_vdp1_legacy;s->tvm=mode;s->vdp2_.lsmd=3;
  l.framebuffer_mode=mode;l.framebuffer_width=mode?1024:512;l.framebuffer_height=512;l.framebuffer_double_interlace=1;
  l.framebuffer_current_draw=0;l.framebuffer_current_display=1;l.draw_field=0;l.field_valid[0]=l.field_valid[1]=false;
  std::fill(l.framebuffer[0].begin(),l.framebuffer[0].end(),0x1111);
  std::fill(l.framebuffer[1].begin(),l.framebuffer[1].end(),0x2222);
  l.system_cliprect.set(0,l.framebuffer_width-1,0,511);
  s->current_sprite.CMDPMOD=0;s->current_sprite.CMDCOLR=0x8033;s->current_sprite.ispoly=1;
  s->m_vdp1_regs[1]=8;s->vdp1_prepare_framebuffers();
  assert(l.framebuffer_draw_lines[0]==l.framebuffer_draw_lines[1]);
  assert(l.framebuffer_draw_lines[2]==l.framebuffer[0].data()+512);
  // Writing DIL does not change the current field before the bank change.
  s->vdp1_regs_w(1,12,0xffff);assert(l.draw_field==0);
  s->drawpixel_poly(0,1,0,0);assert(l.framebuffer[0][0]==0x1111);
  s->drawpixel_poly(0,0,0,0);assert(l.framebuffer[0][0]==(mode?0x3311:0x8033));
  s->vdp1_change_framebuffers();assert(l.draw_field==1&&l.framebuffer_current_draw==1);
  std::array<uint32_t,6> p{};
  assert(s->vdp1_display_pixel(0,0,p)==(mode?0x33:0x8033));
  assert(s->vdp1_display_pixel(0,1,p)==0);
  s->current_sprite.CMDCOLR=0x8055;
  s->drawpixel_poly(0,0,0,0);assert(l.framebuffer[1][0]==0x2222);
  s->drawpixel_poly(0,1,0,0);assert(l.framebuffer[1][0]==(mode?0x5522:0x8055));
  s->m_vdp1_regs[1]=8;s->vdp1_change_framebuffers();assert(l.draw_field==0&&l.field_valid[0]&&l.field_valid[1]);
  assert(s->vdp1_display_pixel(0,0,p)==(mode?0x33:0x8033));
  assert(s->vdp1_display_pixel(0,1,p)==(mode?0x55:0x8055));
  // Drawing the next even field must not overwrite the displayed previous one.
  l.framebuffer[0][0]=0xdead;s->vdp1_state_save_postload();
  assert(s->vdp1_display_pixel(0,0,p)==(mode?0x33:0x8033));
  assert(s->vdp1_display_pixel(0,1,p)==(mode?0x55:0x8055));
  // Erase registers address physical field rows, not an oversized bank.
  l.ewdr=0xa1b2;s->m_vdp1_regs[4]=(1<<9)|1;s->m_vdp1_regs[5]=(2<<9)|1;l.erase_upper_left=s->m_vdp1_regs[4];l.erase_lower_right=s->m_vdp1_regs[5];
  s->vdp1_clear_framebuffer(0);
  assert(l.framebuffer[0][512+8]==0xa1b2&&l.framebuffer[0][1024+8]==0x1111);
  // Both halves of the CPU's 512-KiB window address the same 256-KiB bank.
  s->vdp1_framebuffer0_w(0x10000,0x12345678,0xffffffff);
  assert(s->vdp1_framebuffer0_r(0,0xffffffff)==0x12345678);
  assert(s->vdp1_framebuffer0_r(0x10000,0xffffffff)==0x12345678);
  ++field_cases;
 }
 std::cout<<field_cases<<" interlace field lifecycle sequences passed\n";
 std::cout<<commands<<" VDP1 command/completion, "<<fb<<" framebuffer and "<<clipping<<" pixel-clipping scenarios passed\n";
}
'''.replace('// TYPES',types).replace('// FUNCTIONS',functions)
harness=harness.replace('SHADER_PROTOTYPES','\n'.join(extract(current,sig).split('{')[0].replace('saturn_state::','')+';' for sig in shader_signatures[2:]))
with tempfile.TemporaryDirectory(prefix='saturn-vdp1-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

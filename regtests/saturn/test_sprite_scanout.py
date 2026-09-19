#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production sprite scanout/compositor images with recording VDP2 windows.

Tests output-coordinate replication/decimation, per-output-pixel blending and
odd partial-update clips. Device scheduling, palette and window evaluation are
stand-ins. --old selects the pre-unification functions and must fail.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--old', action='store_true')
p.add_argument('--ratio-baseline', action='store_true')
p.add_argument('--sprite-window-mutation', action='store_true')
p.add_argument('--sprite-bank-mutation', action='store_true')
p.add_argument('--shadow-mutation', choices=('normal-precedence','transparent-enable','self-enable'))
a = p.parse_args()
source = (subprocess.check_output(['git','show',('baf9b069' if a.ratio_baseline else '9f6d2ccc')+':src/mame/sega/saturn.cpp'],cwd=ROOT,text=True)
          if a.old or a.ratio_baseline else (ROOT/'src/mame/sega/saturn.cpp').read_text())
def extract(signature):
    text=(ROOT/'src/mame/sega/saturn.cpp').read_text() if signature.startswith(('bool saturn_state::vdp2_sprite_window','void saturn_state::vdp2_compose_pixel','void saturn_state::vdp2_shadow_pixel','static uint32_t vdp2_extended_color','static uint32_t vdp2_gradation_color')) else source
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
functions='\n'.join(extract(sig) for sig in ('void saturn_state::draw_sprites(',
 'uint16_t saturn_state::vdp1_display_pixel(', 'uint16_t saturn_state::vdp1_read_pixel(',
 'int saturn_state::vdp1_rotation_coordinate('))
functions=extract('static uint32_t vdp2_gradation_color(')+'\n'+extract('static uint32_t vdp2_extended_color(')+'\n'+extract('void saturn_state::vdp2_compose_pixel(')+'\n'+extract('void saturn_state::vdp2_shadow_pixel(')+'\n'+extract('bool saturn_state::vdp2_sprite_window(')+'\n'+functions
if a.shadow_mutation:
    old,new={
        'normal-precedence': ('if (dot == unsigned(sprite_colormask - 1))', 'if (!self_shadow && dot == unsigned(sprite_colormask - 1))'),
        'transparent-enable': ('if (VDP2_SDCTL & 0x100)', 'if (!(VDP2_SDCTL & 0x100))'),
        'self-enable': ('if (self_shadow)', 'if (self_shadow && (VDP2_SDCTL & 1))'),
    }[a.shadow_mutation]
    assert functions.count(old)==1
    functions=functions.replace(old,new)
if a.sprite_window_mutation:functions=functions.replace('& 0x8000) != 0;', '& 0x8000) == 0;')
if a.sprite_bank_mutation:
    old='vdp1_display_pixel(sx, y, rotation)'
    assert functions.count(old)==1
    # Change only normal, in-bounds SW sampling to the opposite physical bank.
    # Keep the other readout modes and the sprite color compositor untouched.
    functions=functions.replace(old,'((VDP1_TVM() == 0 && sx < 512 && y < 256) ? m_vdp1_legacy.framebuffer[1 - m_vdp1_legacy.framebuffer_current_display].get()[y * 512 + sx] : vdp1_display_pixel(sx, y, rotation))')
functions=extract('static constexpr uint8_t vdp2_cc_blend_level(')+'\n'+functions
assert 'vdp2_window_cache_invalidate();' in (ROOT/'src/mame/sega/saturn.cpp').read_text().split('void saturn_state::vdp2_state_save_postload() {',1)[1].split('void saturn_state::vdp2_exit()',1)[0]
names=sorted(set(re.findall(r'VDP2_(\w+)',functions)))
macros='\n'.join('#define VDP2_'+n+' settings.'+n for n in names)
fields='\n'.join('int '+n+'=0;' for n in names)
harness=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
struct rgb_t {
 uint32_t v;
 rgb_t(uint32_t p=0):v(p){} rgb_t(int r,int g,int b):v((r<<16)|(g<<8)|b){}
 operator uint32_t()const{return v;}
 int r()const{return (v>>16)&255;}int g()const{return (v>>8)&255;}int b()const{return v&255;}
};
constexpr bool BIT(unsigned value,int bit){return (value>>bit)&1;}
int pal5bit(int n){return (n<<3)|(n>>2);}
uint32_t alpha_blend_r32(uint32_t d,uint32_t s,int a){
 rgb_t D(d),S(s);return rgb_t((S.r()*a+D.r()*(256-a))>>8,(S.g()*a+D.g()*(256-a))>>8,(S.b()*a+D.b()*(256-a))>>8);
}
uint32_t add_blend_r32(uint32_t d,uint32_t s){rgb_t D(d),S(s);return rgb_t(std::min(255,D.r()+S.r()),std::min(255,D.g()+S.g()),std::min(255,D.b()+S.b()));}
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {
 std::array<uint32_t,48> p{};
 uint32_t &pix(int y,int x=0){assert(y>=0&&y<6&&x>=0&&x<8);return p[y*8+x];}
};
struct buffer {std::array<uint16_t,0x20000> data{};const uint16_t* get()const{return data.data();}uint16_t* get(){return data.data();}};
struct vdp2 {int hreso=0,lsmd=0;int get_hreso()const{return hreso;}int get_lsmd()const{return lsmd;}};
struct palette {uint32_t pen(int n){return (n&255)*0x010101;}};
struct saturn_state {
 bool m_vdp2_composition_active=false;
 bitmap_rgb32 m_vdp2_raw_top,m_vdp2_raw_under;
 struct {std::array<uint8_t,48> data{};uint8_t &pix(int y,int x){assert(x>=0&&x<8&&y>=0&&y<6);return data[y*8+x];}} m_vdp2_raw_alpha,m_vdp2_raw_meta,m_vdp2_under_meta;
 bool vdp2_calculation_window(int,int){return true;}
 bool m_vdp2_extended_active=false;bool m_vdp2_gradation_active=false,m_vdp2_gradation_capture=false;unsigned m_vdp2_gradation_layer=7;bitmap_rgb32 m_vdp2_gradation_source;
 rgb_t vdp2_line_color(int,bool,unsigned){return rgb_t(0x876543);}
 void vdp2_compute_color_offset_UINT32(rgb_t*,int){assert(!settings.CLOFEN);}
 void vdp2_compose_pixel(bitmap_rgb32&,int,int,rgb_t,bool,unsigned,bool,rgb_t,unsigned);
 void vdp2_shadow_pixel(bitmap_rgb32&,int,int,bool);
 static constexpr int WINDOW_CACHE_WIDTH=1024;
 int m_sprite_window_y=-1;uint8_t m_sprite_window_line[WINDOW_CACHE_WIDTH]{};
 bool vdp2_sprite_window(int,int);
 int tvm=0;bool window=false;
 vdp2 device;vdp2 *m_vdp2=&device;palette pal;palette *m_palette=&pal;
 struct { // FIELDS
 } settings;
 struct {struct {int logic,enabled[2],sprite_window,area[2];} window_control;} current_tilemap{};
 struct {
  std::array<buffer,2> framebuffer,field_framebuffer;
  const uint16_t *framebuffer_display_lines[512]{};
  int framebuffer_current_display=0,framebuffer_double_interlace=0;
  bool field_valid[2]={true,true};
 } m_vdp1_legacy;
 int vdp1_sprite_priorities_usage_valid=0;
 uint8_t vdp1_sprite_priorities_used[8]{},vdp1_sprite_priorities_in_fb_line[512][8]{};
 bool vdp2_window_process(int x,int y){return !window||((x+2*y)%3!=1);}
 void vdp2_compute_color_offset(int*,int*,int*,int){assert(false);}
 std::array<uint32_t,6> vdp1_rotation_parameters()const{return {65536,0,0,65536,65536,0};}
 static int vdp1_rotation_coordinate(uint32_t,uint32_t,uint32_t,int,int);
 uint16_t vdp1_read_pixel(const uint16_t*,int)const;
 uint16_t vdp1_display_pixel(int,int,const std::array<uint32_t,6>&)const;
 void draw_sprites(bitmap_rgb32&,const rectangle&,uint8_t);
};
#define VDP1_TVM() tvm
// MACROS
// FUNCTIONS
int main(){
 auto ptr=std::make_unique<saturn_state>();auto &s=*ptr;auto &v=s.m_vdp1_legacy;
 // PRI_INIT
 // CCR_INIT
 unsigned images=0;
 for(int mode : {0,1,2,3,4})for(int hreso : {0,1,2,3,4,5})for(int interlace : {0,3})
 for(bool fields : {false,true})for(bool rgb : {false,true})for(int blend : {0,1,2})
 for(bool window : {false,true})for(rectangle clip : {rectangle{0,7,0,5},rectangle{1,6,1,4},rectangle{7,7,5,5}}){
  // Rotation/HDTV with double-interlace drawing is prohibited.
  if(fields&&mode>=2)continue;
  s.tvm=mode;s.device.hreso=hreso;s.device.lsmd=interlace;s.window=window;
  v.framebuffer_double_interlace=fields;v.framebuffer_current_display=1;
  for(int bank=0;bank<2;++bank)for(unsigned i=0;i<0x20000;++i){
   unsigned value=1+(i+bank*9)%15;
   uint16_t dot=mode&1?((value<<8)|(16-value)):(rgb?0x8000:0)|value;
   v.framebuffer[bank].data[i]=dot;v.field_framebuffer[bank].data[i]=dot;
  }
  for(int y=0;y<512;++y)v.framebuffer_display_lines[y]=v.framebuffer[1].get()+((y*(mode==3?256:512))&0x1ffff);
  s.settings.SPCLMD=rgb;s.settings.SPTYPE=0;
  s.settings.SPCCEN=blend!=0;s.settings.SPCCN=7;s.settings.CCMD=blend==2;
  s.vdp1_sprite_priorities_usage_valid=0;
  bitmap_rgb32 result,expected;
  for(int y=0;y<6;++y)for(int x=0;x<8;++x)result.pix(y,x)=expected.pix(y,x)=rgb_t(10,y*29,x*31);
  s.draw_sprites(result,clip,1);
  for(int y=clip.t;y<=clip.b;++y)for(int x=clip.l;x<=clip.r;++x){
   if(window&&(x+2*y)%3==1)continue;
   // Independent mode table: source dots advanced per output dot.
   constexpr int numerator[5][6]={{2,2,1,1,1,1},{4,4,2,2,1,1},{2,2,2,2,1,1},{2,2,2,2,1,1},{1,1,1,1,1,1}};
   int sx=x*numerator[mode][hreso]/2;
   int sy=(mode==4||(interlace==3&&!fields))?y/2:y;
   int bank=1;
   if(mode==2||mode==3)++sx; // test parameter-A translation
   else if(fields){if(interlace==3){bank=sy%2;sy/=2;}else sy&=255;}
   unsigned index=sy*(mode==3?256:512)+(mode&1?sx/2:sx);
   unsigned value=1+(index+bank*9)%15;
   unsigned dot=mode&1?(sx%2?16-value:value):(rgb?0x8000:0)|value;
   uint32_t color=(dot&0x8000)&&rgb?uint32_t(rgb_t(pal5bit(dot&31),0,0)):s.pal.pen(dot);
   uint32_t dest=expected.pix(y,x);
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(dest,color,120):add_blend_r32(dest,color);
  }
  if(result.p!=expected.p){std::cerr<<"mode "<<mode<<" hreso "<<hreso<<" lsmd "<<interlace<<" fields "<<fields<<" blend "<<blend<<" clip "<<clip.l<<","<<clip.t<<"\n";assert(false);}
  ++images;
 }

 // Normal/MSB shadow and transparent dots must operate on each destination
 // independently, not copy a pre-blended source dot to its replicated peer.
 for(int mode : {0,4})for(int blend : {0,1})for(uint16_t dot : {0,0x8000,0x7fe,0x8001}){

  s.tvm=mode;s.device.hreso=mode==4?4:2;s.device.lsmd=3;s.window=true;
  v.framebuffer_double_interlace=0;
  v.framebuffer[1].data.fill(dot);
  for(int y=0;y<512;++y)v.framebuffer_display_lines[y]=v.framebuffer[1].get()+((y*512)&0x1ffff);
  s.settings.SPCLMD=0;s.settings.SPCCEN=blend;s.settings.CCMD=0;s.settings.SDCTL=0x120;s.settings.SPTYPE=2;
  s.vdp1_sprite_priorities_usage_valid=0;
  bitmap_rgb32 result,expected;
  for(int y=0;y<6;++y)for(int x=0;x<8;++x){
   uint32_t color=rgb_t(x*31,y*41,210);
   result.pix(y,x)=expected.pix(y,x)=color;
   if(dot&&x>=1&&x<=6&&y>=1&&y<=4&&(x+2*y)%3!=1)
    {uint32_t shaded=dot==0x8001?(blend?alpha_blend_r32(color,s.pal.pen(1),120):s.pal.pen(1)):color;
     expected.pix(y,x)=(shaded&0xfefefe)>>1;}
  }
  s.draw_sprites(result,{1,6,1,4},1);
  assert(result.p==expected.p);++images;
 }


 unsigned sw_cases=0;
 for(int mode:{0,1,2,3,4})for(int hreso:{0,1,2,3,4,5})for(int interlace:{0,3})for(bool fields:{false,true})for(int display:{0,1}){
  if(fields&&mode>=2)continue;
  s.tvm=mode;s.device.hreso=hreso;s.device.lsmd=interlace;v.framebuffer_double_interlace=fields;v.framebuffer_current_display=display;
  auto value=[](unsigned i,unsigned bank)->uint16_t{return ((i*37+(i>>9)+bank)%3?0x8000:0)|(i%4?0x123:0);};
  for(int bank=0;bank<2;++bank)for(unsigned i=0;i<0x20000;++i)v.framebuffer[bank].data[i]=v.field_framebuffer[bank].data[i]=value(i,bank);
  for(int y=0;y<512;++y)v.framebuffer_display_lines[y]=v.framebuffer[display].get()+((y*(mode==3?256:512))&0x1ffff);
  for(int type=0;type<16;++type)for(bool enable:{false,true})for(bool mixed:{false,true}){
   s.settings.SPTYPE=type;s.settings.SPWINEN=enable;s.settings.SPCLMD=mixed;s.m_sprite_window_y=-1;
   for(int y=0;y<8;++y)for(int x=0;x<16;++x){
    constexpr int numerator[5][6]={{2,2,1,1,1,1},{4,4,2,2,1,1},{2,2,2,2,1,1},{2,2,2,2,1,1},{1,1,1,1,1,1}};
    int sx=x*numerator[mode][hreso]/2,sy=(mode==4||(interlace==3&&!fields))?y/2:y,bank=display;
    if(mode==2||mode==3)++sx;else if(fields){if(interlace==3){bank=sy%2;sy/=2;}else sy&=255;}
    unsigned index=sy*(mode==3?256:512)+(mode&1?sx/2:sx);
    bool expected=enable&&!mixed&&type>=2&&type<=7&&!(mode&1)&&(value(index,bank)&0x8000);
    assert(s.vdp2_sprite_window(x,y)==expected);++sw_cases;
   }
   assert(!s.vdp2_sprite_window(-1,0)&&!s.vdp2_sprite_window(1024,0)&&!s.vdp2_sprite_window(0,-1)&&!s.vdp2_sprite_window(0,512));
  }
 }
 // Re-render invalidation must discard the derived row after a bank/write change.
 s.tvm=0;s.device.hreso=s.device.lsmd=0;v.framebuffer_double_interlace=0;
 s.settings.SPTYPE=2;s.settings.SPWINEN=1;s.settings.SPCLMD=0;s.m_sprite_window_y=-1;
 v.framebuffer_display_lines[0]=v.framebuffer[0].get();v.framebuffer[0].data[0]=0x8123;
 assert(s.vdp2_sprite_window(0,0));v.framebuffer[0].data[0]=0;s.m_sprite_window_y=-1;assert(!s.vdp2_sprite_window(0,0));
 s.settings.SPWINEN=0;
 std::cout<<sw_cases<<" sprite-window displayed-framebuffer pixels passed\n";
 unsigned ratio_cases=0;
 s.tvm=0;s.device.hreso=0;s.device.lsmd=0;s.window=false;
 v.framebuffer_double_interlace=0;v.framebuffer_current_display=1;
 s.settings.SDCTL=0;s.settings.SPTYPE=0;s.settings.SPCCN=2;
 for(unsigned ratio=0;ratio<32;++ratio)for(unsigned selector=0;selector<8;++selector)
 for(int condition=0;condition<4;++condition)for(int priority : {1,2,3})
 for(bool msb : {false,true})for(bool mixed : {false,true})for(bool enabled : {false,true})for(bool add : {false,true})for(bool history:{false,true})for(bool second:{false,true})for(bool line:{false,true}){
  bool rgb=msb&&mixed;
  if(rgb&&selector)continue; // RGB dots select CCRT0, not palette selector bits.
  s.m_vdp2_composition_active=history;s.settings.CCCR=second?0x200:0;s.settings.SPLCEN=line;s.settings.CCRLB=7;
  s.m_vdp2_raw_top.p.fill(0x714923);s.m_vdp2_raw_alpha.data.fill((31-((ratio+11)%32))*8);
  s.settings.SPCCCS=condition;s.settings.SPCLMD=mixed;s.settings.SPCCEN=enabled;s.settings.CCMD=add;
  // RATIO_PRI
  // RATIO_CCR
  uint16_t dot=7|(msb?0x8000:0)|(rgb?0:selector<<11);
  v.framebuffer[1].data.fill(dot);
  for(int y=0;y<512;++y)v.framebuffer_display_lines[y]=v.framebuffer[1].get()+((y*512)&0x1ffff);
  s.vdp1_sprite_priorities_usage_valid=0;
  bitmap_rgb32 image,expected;
  image.p.fill(0x234567);expected=image;
  s.draw_sprites(image,{1,6,1,4},priority);
  bool calculate=enabled&&(condition==0?priority<=2:condition==1?priority==2:condition==2?priority>=2:msb);
  uint32_t color=rgb?uint32_t(rgb_t(pal5bit(7),0,0)):s.pal.pen(7);
  unsigned own_ratio=(ratio+(rgb?0:selector))&31;
  unsigned selected_ratio=second&&line?7:history&&second?(ratio+11)%32:own_ratio;
  uint32_t background=line?0x876543:history?0x714923:0x234567;
  uint32_t out=color;
  if(calculate){
   if(add)out=rgb_t(std::min(255u,((background>>16)&255)+((color>>16)&255)),std::min(255u,((background>>8)&255)+((color>>8)&255)),std::min(255u,(background&255)+(color&255)));
   else {out=0;for(unsigned shift : {0,8,16})out|=(( ((color>>shift)&255)*(31-selected_ratio)+((background>>shift)&255)*(selected_ratio+1) )/32)<<shift;}
  }
  for(int y=1;y<=4;++y)for(int x=1;x<=6;++x){expected.pix(y,x)=out;if(history){assert(s.m_vdp2_raw_top.pix(y,x)==color);assert(s.m_vdp2_raw_alpha.pix(y,x)==(31-own_ratio)*8);}}
  assert(image.p==expected.p);++ratio_cases;
 }

 unsigned shadow_cases=0;s.settings.SPLCEN=0;s.settings.CCMD=0;s.settings.CCCR=0;s.settings.SPCLMD=0;s.settings.SPCCN=7;s.window=false;
 s.m_vdp2_composition_active=true;
 // SHADOW_PRI
 // SHADOW_CCR
 constexpr unsigned masks[]={2047,2047,2047,2047,1023,2047,1023,511,127,63,63,63,255,255,255,255};
 for(unsigned type=0;type<16;++type)for(unsigned layer=0;layer<7;++layer)
 for(unsigned select:{0u,1u<<layer,1u<<((layer+1)%6),63u})for(unsigned kind=0;kind<6;++kind)
 for(unsigned calculation=0;calculation<3;++calculation)for(bool transparent:{false,true})for(bool window:{false,true}){
  s.tvm=type<8?0:1;s.device.hreso=s.device.lsmd=0;s.settings.SPTYPE=type;s.settings.SDCTL=(select&63)|(transparent?256:0);
  s.settings.SPCCEN=calculation!=0;s.settings.SPCCCS=calculation==2?3:0;s.settings.SPWINEN=window;
  unsigned inputs[]={0,masks[type]-1,32768,32769,32768+masks[type]-1,7};unsigned dot=inputs[kind];if(type>=8)dot&=255;
  v.framebuffer[1].data.fill(type<8?dot:dot*257);
  for(int y=0;y<512;++y)v.framebuffer_display_lines[y]=v.framebuffer[1].get()+((y*512)&0x1ffff);
  s.m_vdp2_raw_top.p.fill(0x314159);s.m_vdp2_raw_alpha.data.fill(120);s.m_vdp2_raw_meta.data.fill(layer);
  bitmap_rgb32 image,expected;image.p.fill(0x314159);expected=image;s.vdp1_sprite_priorities_usage_valid=0;
  s.draw_sprites(image,{1,6,1,4},1);
  unsigned code=dot&masks[type];bool msb=type>=2&&type<=7&&!window&&(dot&32768);
  bool normal=code==masks[type]-1,transparent_shadow=msb&&!(dot&32767);
  uint32_t out=0x314159;
  if(normal||transparent_shadow){if((select&63)&(1u<<layer))if(normal||transparent)out=(out&0xfefefe)>>1;}
  else if(code){out=s.pal.pen(code);bool calculate=calculation==1||(calculation==2&&(dot&32768));if(calculate)out=alpha_blend_r32(0x314159,out,120);if(msb)out=(out&0xfefefe)>>1;}
  for(int y=1;y<=4;++y)for(int x=1;x<=6;++x)expected.pix(y,x)=out;
  assert(image.p==expected.p);++shadow_cases;
 }
 std::cout<<shadow_cases<<" all-sprite-type shadow/SDCTL/CC/MSB/window images passed\n";
 std::cout<<ratio_cases<<" sprite ratio/selector/eligibility images passed\n";
 std::cout<<images<<" production sprite scanout/compositor images passed\n";
}
'''
harness=harness.replace('// FIELDS',fields).replace('// MACROS',macros).replace('// FUNCTIONS',functions)
harness=harness.replace('// SHADOW_PRI',''.join(f's.settings.S{i}PRIN=1;' for i in range(8))).replace('// SHADOW_CCR',''.join(f's.settings.S{i}CCRT=16;' for i in range(8)))
harness=harness.replace('// RATIO_PRI',''.join(f's.settings.S{i}PRIN=priority;' for i in range(8)))
harness=harness.replace('// RATIO_CCR',''.join(f's.settings.S{i}CCRT=(ratio+{i})&31;' for i in range(8)))
harness=harness.replace('// PRI_INIT',''.join(f's.settings.S{i}PRIN=1;' for i in range(8)))
harness=harness.replace('// CCR_INIT',''.join(f's.settings.S{i}CCRT=16;' for i in range(8)))
with tempfile.TemporaryDirectory(prefix='saturn-scanout-') as temp:
    cpp=Path(temp)/'test.cpp';exe=Path(temp)/'test';cpp.write_text(harness)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O1','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

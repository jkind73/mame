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
a = p.parse_args()
source = (subprocess.check_output(['git','show','9f6d2ccc:src/mame/sega/saturn.cpp'],cwd=ROOT,text=True)
          if a.old else (ROOT/'src/mame/sega/saturn.cpp').read_text())
def extract(signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]
functions='\n'.join(extract(sig) for sig in ('void saturn_state::draw_sprites(',
 'uint16_t saturn_state::vdp1_display_pixel(', 'uint16_t saturn_state::vdp1_read_pixel(',
 'int saturn_state::vdp1_rotation_coordinate('))
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
 rgb_t(uint32_t p):v(p){} rgb_t(int r,int g,int b):v((r<<16)|(g<<8)|b){}
 operator uint32_t()const{return v;}
 int r()const{return (v>>16)&255;}int g()const{return (v>>8)&255;}int b()const{return v&255;}
};
constexpr bool BIT(unsigned value,int bit){return (value>>bit)&1;}
int pal5bit(int n){return (n<<3)|(n>>2);}
uint32_t alpha_blend_r32(uint32_t d,uint32_t s,int a){
 rgb_t D(d),S(s);return rgb_t((S.r()*a+D.r()*(256-a))>>8,(S.g()*a+D.g()*(256-a))>>8,(S.b()*a+D.b()*(256-a))>>8);
}
uint32_t add_blend_r32(uint32_t d,uint32_t s){rgb_t D(d),S(s);return rgb_t(std::min(255,D.r()+S.r()),std::min(255,D.g()+S.g()),std::min(255,D.b()+S.b()));}
int vdp2_cc_blend_level(int c){return (32-c)*8;}
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}};
struct bitmap_rgb32 {
 std::array<uint32_t,48> p{};
 uint32_t &pix(int y,int x=0){assert(y>=0&&y<6&&x>=0&&x<8);return p[y*8+x];}
};
struct buffer {std::array<uint16_t,0x20000> data{};const uint16_t* get()const{return data.data();}uint16_t* get(){return data.data();}};
struct vdp2 {int hreso=0,lsmd=0;int get_hreso()const{return hreso;}int get_lsmd()const{return lsmd;}};
struct palette {uint32_t pen(int n){return (n&255)*0x010101;}};
struct saturn_state {
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
   expected.pix(y,x)=blend==0?color:blend==1?alpha_blend_r32(dest,color,128):add_blend_r32(dest,color);
  }
  if(result.p!=expected.p){std::cerr<<"mode "<<mode<<" hreso "<<hreso<<" lsmd "<<interlace<<" fields "<<fields<<" blend "<<blend<<" clip "<<clip.l<<","<<clip.t<<"\n";assert(false);}
  ++images;
 }

 // Normal/MSB shadow and transparent dots must operate on each destination
 // independently, not copy a pre-blended source dot to its replicated peer.
 for(int mode : {0,4})for(int blend : {0,1})for(uint16_t dot : {0,0x8000,0x7fe,0x8001}){
  // MSB-shadow handling in the alpha path is a separate existing VDP2 gap.
  if(blend&&(dot&0x8000))continue;
  s.tvm=mode;s.device.hreso=mode==4?4:2;s.device.lsmd=3;s.window=true;
  v.framebuffer_double_interlace=0;
  v.framebuffer[1].data.fill(dot);
  for(int y=0;y<512;++y)v.framebuffer_display_lines[y]=v.framebuffer[1].get()+((y*512)&0x1ffff);
  s.settings.SPCLMD=0;s.settings.SPCCEN=blend;s.settings.CCMD=0;s.settings.SDCTL=0x101;
  s.vdp1_sprite_priorities_usage_valid=0;
  bitmap_rgb32 result,expected;
  for(int y=0;y<6;++y)for(int x=0;x<8;++x){
   uint32_t color=rgb_t(x*31,y*41,210);
   result.pix(y,x)=expected.pix(y,x)=color;
   if(dot&&x>=1&&x<=6&&y>=1&&y<=4&&(x+2*y)%3!=1)
    expected.pix(y,x)=(color&0xfefefe)>>1;
  }
  s.draw_sprites(result,{1,6,1,4},1);
  assert(result.p==expected.p);++images;
 }
 std::cout<<images<<" production sprite scanout/compositor images passed\n";
}
'''
harness=harness.replace('// FIELDS',fields).replace('// MACROS',macros).replace('// FUNCTIONS',functions)
harness=harness.replace('// PRI_INIT',''.join(f's.settings.S{i}PRIN=1;' for i in range(8)))
harness=harness.replace('// CCR_INIT',''.join(f's.settings.S{i}CCRT=16;' for i in range(8)))
with tempfile.TemporaryDirectory(prefix='saturn-scanout-') as temp:
    cpp=Path(temp)/'test.cpp';exe=Path(temp)/'test';cpp.write_text(harness)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O1','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

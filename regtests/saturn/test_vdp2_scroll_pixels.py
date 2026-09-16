#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production normal-scroll point sampler, table sequencing and pattern decoding.

Independent coordinate/VRAM bitstream oracle. Palette, window and color-offset
inputs are controlled; this is not cycle-slot arbitration or linked gameplay.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation',choices=('phase','cell','mosaic','two-word','special-color','metadata','priority','11bpp-route'))
a=p.parse_args();src=(ROOT/'src/mame/sega/saturn.cpp').read_text();head=(ROOT/'src/mame/sega/saturn.h').read_text()
def extract(text,sig):
 start=text.index(sig);end=text.index('{',start)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
funcs=[extract(src,sig) for sig in ('void saturn_state::vdp2_compose_pixel(', 'unsigned saturn_state::vdp2_special_priority_mode(', 'rgb_t saturn_state::vdp2_special_priority_pixel(', 'unsigned saturn_state::vdp2_special_color_mode(', 'rgb_t saturn_state::vdp2_special_color_pixel(', 'rgb_t saturn_state::vdp2_line_color(', 'rgb_t saturn_state::vdp2_dot_pixel(', 'rgb_t saturn_state::vdp2_pattern_pixel(', 'rgb_t saturn_state::vdp2_scroll_pixel(', 'void saturn_state::vdp2_draw_scroll_screen(')]
f=extract(src,'static uint32_t vdp2_gradation_color(')+'\n'+extract(src,'static uint32_t vdp2_extended_color(')+'\n'+extract(src,'static constexpr uint8_t vdp2_cc_blend_level(')+'\n'+'\n'.join(funcs)
if a.mutation=='phase':f=f.replace('+ t.scrollx_fraction','+ 0').replace('+ t.scrolly_fraction','+ 0')
if a.mutation=='cell':f=f.replace('unsigned((source_x >> 19) - first_cell)','unsigned(sample_x / 8 + first_cell * 0)')
if a.mutation=='mosaic':f=f.replace('t.vertical_cell_scroll_enable && !mosaic','t.vertical_cell_scroll_enable')
if a.mutation=='two-word':f=f.replace('code = data & 0x7fff;', 'code = data & 0x3fff;')
if a.mutation=='special-color':f=f.replace('bool(current_tilemap.special_colour_control_register)', 'true').replace('!(bitmap_flags & 0x10)', 'false && !(bitmap_flags & 0x10)')
if a.mutation=='metadata':f=f.replace('pixel = rgb_t((uint32_t(pixel) & 0xffffff) | metadata);', '(void)metadata; pixel = rgb_t(uint32_t(pixel) | 0xff000000);')
if a.mutation=='priority':f=f.replace('if (!priority)', 'if (false && !priority)').replace('return rgb_t((uint32_t(pixel) & ~0x1c000000U) | (priority << 26));', 'return rgb_t((uint32_t(pixel) & ~0x1c000000U) | ((priority | 1) << 26));')
route=extract(src,'  if (current_tilemap.layer_name < 4 &&')
if a.mutation=='11bpp-route':route=route.replace('(current_tilemap.colour_depth == 2 && !current_tilemap.bitmap_enable) ||', '')
names=sorted(set(re.findall(r'VDP2_\w+',f)))
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>
#include "palette.h"
namespace util {int32_t sext(uint32_t x,int n){return int32_t(x<<(32-n))>>(32-n);}}
struct rectangle {int l,r,t,b;int left()const{return l;}int right()const{return r;}int top()const{return t;}int bottom()const{return b;}bool empty()const{return l>r||t>b;}};
struct bitmap_rgb32 {std::array<uint32_t,24*16> data;bitmap_rgb32(){data.fill(0xff102030);}uint32_t &pix(int y,int x){assert(x>=0&&x<24&&y>=0&&y<16);return data[y*24+x];}};
struct video {int get_hreso(){return 0;}int lsmd=0;bool size=false;int get_lsmd(){return lsmd;}bool get_vramsz(){return size;}};
struct memory {std::vector<uint32_t> words=std::vector<uint32_t>(0x40000);unsigned reads=0;uint32_t operator[](unsigned i){assert(i<words.size());++reads;return words[i];}};
struct palette {uint32_t pen(unsigned i){assert(i<2048);return 0xff000000|((i*7919)&0xffffff);}};
uint32_t blend(uint32_t d,uint32_t s,unsigned a,bool add){uint32_t r=0xff000000;for(int shift:{0,8,16}){unsigned D=(d>>shift)&255,S=(s>>shift)&255;r|=(add?std::min(255u,D+S):(D*(256-a)+S*a)/256)<<shift;}return r;}
uint32_t alpha_blend_r32(uint32_t d,uint32_t s,unsigned a){return blend(d,s,a,false);}
uint32_t add_blend_r32(uint32_t d,uint32_t s){return blend(d,s,0,true);}
struct saturn_state {
 bool m_vdp2_composition_active=false;
 bitmap_rgb32 m_vdp2_raw_top,m_vdp2_raw_under;
 struct {uint8_t data[24*16]{};uint8_t &pix(int y,int x){assert(x>=0&&x<24&&y>=0&&y<16);return data[y*24+x];}} m_vdp2_raw_alpha,m_vdp2_raw_meta,m_vdp2_under_meta;
 bool vdp2_calculation_window(int,int){return true;}
 bool m_vdp2_extended_active=false;bool m_vdp2_gradation_active=false,m_vdp2_gradation_capture=false;unsigned m_vdp2_gradation_layer=7;bitmap_rgb32 m_vdp2_gradation_source;

 int m_vdp2_priority_pass=-1;
 uint32_t m_vdp2_cram[1024]{};
 uint32_t vdp2_cram_r(unsigned i){return m_vdp2_cram[i];}
 // TILEMAP
 struct {// REGS
 } regs;
 video vid;video *m_vdp2=&vid;palette pal;palette *m_palette=&pal;
 struct {std::unique_ptr<uint8_t[]> gfx_decode=std::make_unique<uint8_t[]>(0x100000);} m_vdp2_legacy;
 memory m_vdp2_vram;bool window=false;
 bool vdp2_window_process(int x,int y){return !window||(x+y)%3!=0;}
 void vdp2_compute_color_offset_UINT32(rgb_t *p,int){*p=rgb_t(((uint32_t(*p)^0x010203)&0xffffff)|0xff000000);}
 // DECLS
 void route(bitmap_rgb32 &bitmap,const rectangle &cliprect){
 // ROUTE
 assert(false);
 }
};
#define STV_TRANSPARENCY_NONE 1
// MACROS
// FUNCTIONS
// UNDEFS
int main(){saturn_state s;auto &t=s.current_tilemap;unsigned cases=0;
 for(unsigned i=0;i<1024;++i)s.m_vdp2_cram[i]=i*0x31415927u^0x82f0471b;
 for(unsigned a=0;a<0x100000;++a)s.m_vdp2_legacy.gfx_decode[a]=(a*37+(a>>8)*13+(a>>17)*53)^0x5a;
 for(unsigned a=0;a<0x40000;++a){uint32_t v=0;for(unsigned i=0;i<4;++i)v=(v<<8)|s.m_vdp2_legacy.gfx_decode[a*4+i];s.m_vdp2_vram.words[a]=v;}
 auto put=[&](unsigned a,uint32_t v){a&=0x3ffff;s.m_vdp2_vram.words[a]=v;for(unsigned i=0;i<4;++i)s.m_vdp2_legacy.gfx_decode[a*4+i]=v>>(24-i*8);};
 auto floorq=[](int64_t value,int64_t divisor){return value>=0?value/divisor:-((-value+divisor-1)/divisor);};
 for(bool bitmap:{false,true})for(unsigned depth=0;depth<5;++depth)for(unsigned large:{0u,1u})
 for(unsigned one:{0u,1u})for(unsigned flags=0;flags<16;++flags)for(unsigned layer:{0u,1u})
 for(unsigned phase:{0u,0x8000u})for(unsigned variant=0;variant<6;++variant)for(bool line_color:{false,true})for(unsigned special=0;special<4;++special)for(unsigned priority_mode=0;priority_mode<3;++priority_mode){
  if((special==2||priority_mode==2)&&depth>=3)continue;
  unsigned base_priority=(flags+variant)%8;s.m_vdp2_priority_pass=(flags/2+variant)%8;
  s.regs.VDP2_SFPRMD=priority_mode<<(layer*2);s.regs.VDP2_N0PRIN=layer?(base_priority^6):base_priority;s.regs.VDP2_N1PRIN=layer?base_priority:(base_priority^6);
  s.regs.VDP2_SFCCMD=special<<(layer*2);s.regs.VDP2_SFSEL=(variant&1)<<layer;s.regs.VDP2_SFCODE=0xa55a;s.regs.VDP2_CRMD=variant%3;
  s.regs.VDP2_BMPNA=((variant&2)?0x1010:0)|((variant&1)?0x2020:0);
  t={};t.special_priority_register=variant&1;t.special_colour_control_register=bool(variant&2);t.enabled=1;t.bitmap_enable=bitmap;t.colour_depth=depth;t.tile_size=large;t.pattern_data_size=one;
  t.bitmap_size=variant%4;t.bitmap_map=variant%4;t.bitmap_palette_number=3;t.colour_ram_address_offset=2;
  t.character_number_supplement=variant%2;t.supplementary_character_bits=21;t.supplementary_palette_bits=5;
  unsigned planes[]={0,1,3};t.plane_size=planes[variant%3];t.map_count=4;
  for(unsigned m=0;m<4;++m)t.map_offset[m]=3+m*5;
  t.scrollx=(variant%2)?1019:505;t.scrolly=(variant%2)?1017:507;t.scrollx_fraction=phase;t.scrolly_fraction=phase;
  unsigned increments[]={0,0x8000,0x10000,0x18000,0x20000,0x40000};t.incx=increments[variant];t.incy=increments[(variant+1)%6];
  t.linescroll_enable=flags&1;t.vertical_linescroll_enable=(flags>>1)&1;t.linezoom_enable=(flags>>2)&1;t.vertical_cell_scroll_enable=(flags>>3)&1;
  t.layer_name=layer;t.linescroll_interval=1u<<(variant%4);t.linescroll_table_address=0x60000+layer*0x1000;
  t.mosaic_screen_enabled=variant>=4;t.transparency=variant&1;t.colour_calculation_enabled=variant%3!=0;t.alpha=112;t.fade_control=variant&1;
  t.line_screen_enabled=line_color;s.regs.VDP2_LCTA=0x30000;s.regs.VDP2_LCCLMD=variant&1;s.regs.VDP2_CCCR=(variant&1)?0x200:0;s.regs.VDP2_CCRLB=19;
  s.regs.VDP2_CCMD=variant%3==2;s.regs.VDP2_MZSZH=3;s.regs.VDP2_MZSZV=2;
  s.vid.size=variant&1;s.vid.lsmd=(variant&1)?3:0;s.window=variant&1;
  s.regs.VDP2_N0VCSC=layer==0||variant&1;s.regs.VDP2_N1VCSC=layer==1||variant&1;
  unsigned cell_address=0x7fff8;s.regs.VDP2_VCSTAU=cell_address/2>>16;s.regs.VDP2_VCSTAL=cell_address/2&0xffff;
  unsigned memsize=s.vid.size?0x100000:0x80000,wmask=memsize/4-1;
  unsigned ls=t.linescroll_table_address/4;
  for(unsigned row=0;row<32;++row){
   if(flags&1)put(ls++,(int(row%5)-2)*65536+0x4000);
   if(flags&2)put(ls++,(int(row%7)-3)*65536+0xc000);
   if(flags&4)put(ls++,increments[row%6]);
  }
  for(unsigned cell=0;cell<40;++cell)put((cell_address/4+cell)&wmask,(int(cell%11)-5)*65536+0x8000);
  auto read=[&](unsigned a){return s.m_vdp2_legacy.gfx_decode[a%memsize];};
  auto bits=[&](unsigned address,unsigned bitpos,unsigned count){uint32_t raw=0;for(unsigned b=0;b<count;++b){unsigned pos=bitpos+b;raw=(raw<<1)|((read(address+pos/8)>>(7-pos%8))&1);}return raw;};
  auto pixel=[&](int X,int Y){
   bool attribute=variant&2,priority_attribute=variant&1;unsigned address,pal=0,bitpos=0,bpd[]={4,8,16,16,32};
   if(bitmap){unsigned W=(t.bitmap_size&2)?1024:512,H=(t.bitmap_size&1)?512:256;
    unsigned dot=(unsigned(Y)%H)*W+unsigned(X)%W;address=t.bitmap_map*0x20000;bitpos=dot*bpd[depth];pal=3*256;
   }else{
    unsigned W=(t.plane_size&1)?1024:512,H=(t.plane_size&2)?1024:512,C=large?16:8;
    unsigned XW=unsigned(X)%(W*2),YW=unsigned(Y)%(H*2),map=XW/W+2*(YW/H);
    unsigned page=(XW%W)/512+((YW%H)/512)*(W/512),N=512/C,nb=one?2:4,pgsize=N*N*nb;
    unsigned base=(t.map_offset[map]%(0x100000/pgsize))/(W*H/(512*512))*(W*H/(512*512));
    unsigned off=(base+page)*pgsize+((YW%512)/C*N+(XW%512)/C)*nb;
    uint32_t name=bits(off,0,nb*8);if(!one){attribute=(name>>28)&1;priority_attribute=(name>>29)&1;}unsigned code=0,flip=0;
    if(one){unsigned low=t.character_number_supplement?12:10;
     for(unsigned b=0;b<low;++b)if(name&(1u<<b))code|=1u<<(b+(large?2:0));
     for(unsigned b=0;b<5;++b)if(t.supplementary_character_bits&(1u<<b)){
      int dest=-1;if(large){if(b<2)dest=b;else if(!t.character_number_supplement||b==4)dest=b+10;}else if(!t.character_number_supplement||b>=2)dest=b+10;
      if(dest>=0)code|=1u<<dest;
     }
     if(!t.character_number_supplement)flip=(name/1024)%4;
     pal=depth==0?(name/4096+t.supplementary_palette_bits*16)*16:(name/4096%8)*256;
    }else{code=name%32768;flip=name>>30;pal=(name/65536%128)*16;}
    unsigned xx=unsigned(X)%C,yy=unsigned(Y)%C;if(flip&1)xx=C-1-xx;if(flip&2)yy=C-1-yy;
    unsigned cell=(yy/8)*2+xx/8;address=code*32+cell*64*bpd[depth]/8;bitpos=((yy%8)*8+xx%8)*bpd[depth];
   }
   uint32_t raw=bits(address,bitpos,bpd[depth]);if(depth==2)raw%=2048;
   if(!t.transparency&&(depth<3?raw==0:(raw&(depth==3?0x8000u:0x80000000u))==0))return 0u;
   unsigned pen=0,color;
   if(depth==3){unsigned r=raw%32,g=raw/32%32,b=raw/1024%32;color=((r*8+r/4)<<16)|((g*8+g/4)<<8)|(b*8+b/4);}
   else if(depth==4)color=((raw%256)<<16)|(raw&0xff00)|((raw>>16)&255);
   else{if(depth==1)pal=pal/256%8*256;if(depth==2)pal=0;pen=(pal+raw+512)%2048;color=s.pal.pen(pen)&0xffffff;}
   bool eligible=true;
   if(special==1)eligible=attribute;
   if(special==2)eligible=attribute&&((0xa55a>>((variant%2)*8+(raw/2)%8))&1);
   if(special==3&&depth<3){unsigned mode=variant%3;if(mode<2){pen%=mode==0?1024:2048;eligible=(s.m_vdp2_cram[pen/2]>>(pen%2?15:31))&1;}else eligible=(s.m_vdp2_cram[pen%1024]>>31)&1;}
   if(priority_mode){bool match=(0xa55a>>((variant%2)*8+(raw/2)%8))&1;unsigned priority=(base_priority&6)|unsigned(priority_attribute&&(priority_mode==1||match));if(!priority||priority!=unsigned(s.m_vdp2_priority_pass))return 0u;}
   return color|(eligible?0xff000000u:0xfe000000u);
  };
  bitmap_rgb32 out,split,expected;s.m_vdp2_vram.reads=0;
  s.route(out,{2,21,1,14});
  assert(s.m_vdp2_vram.reads<=14*(3+20*2));
  s.vdp2_draw_scroll_screen(split,{2,9,1,14});s.vdp2_draw_scroll_screen(split,{10,21,1,14});
  for(int y=1;y<=14;++y){
   int MY=t.mosaic_screen_enabled?(s.vid.lsmd==3?6:3):1;int by=y/MY*MY;
   int entry=by/t.linescroll_interval,anchor=entry*t.linescroll_interval;
   int64_t X=int64_t(t.scrollx)*65536+phase+((flags&1)?(entry%5-2)*65536+0x4000:0);
   int64_t Y=int64_t(t.scrolly)*65536+phase+((flags&2)?(entry%7-3)*65536+0xc000+int64_t(by-anchor)*t.incy:int64_t(by)*t.incy);
   unsigned dx=(flags&4)?increments[entry%6]:t.incx;unsigned cell=0;int64_t prev=floorq(X,8*65536);
   for(int x=0;x<=21;++x){
    int mx=t.mosaic_screen_enabled?x/4*4:x;int64_t xx=X+int64_t(mx)*dx;
    if(!t.mosaic_screen_enabled){int64_t next=floorq(xx,8*65536);if(next!=prev){++cell;prev=next;}}
    int64_t yy=Y;
    if((flags&8)&&!t.mosaic_screen_enabled){unsigned cs=(variant&1)?2:1;unsigned ci=cell*cs+(cs==2?layer:0);yy+=(int(ci%11)-5)*65536+0x8000;}
    if(x<2||(s.window&&(x+y)%3==0))continue;
    uint32_t color=pixel(floorq(xx,65536),floorq(yy,65536));if(!(color>>24))continue;
    if(t.fade_control)color^=0x010203;
    if(!t.colour_calculation_enabled||!(color&0x01000000))expected.pix(y,x)=color|0xff000000;
    else{
     unsigned index=(variant&1)?y:(s.vid.lsmd==3?y%2:0),pen=bits(0x60000+index*2,0,16)&2047;
     uint32_t second=line_color?s.pal.pen(pen):0x102030,alpha=line_color&&(variant&1)?96:112;
     uint32_t result=0xff000000;for(unsigned shift:{0u,8u,16u}){unsigned D=(second>>shift)&255,S=(color>>shift)&255;result|=(s.regs.VDP2_CCMD?std::min(255u,D+S):(D*(256-alpha)+S*alpha)/256)<<shift;}expected.pix(y,x)=result;
    }
   }
  }
  assert(out.data==expected.data);assert(split.data==expected.data);
  assert(t.scrollx_fraction==phase&&t.scrolly_fraction==phase);++cases;
 }
 // Unit-step priority-only layers must not fall through to the legacy path.
 t={};t.enabled=1;t.incx=t.incy=65536;t.transparency=1;t.pattern_data_size=1;t.special_priority_register=1;
 s.regs.VDP2_SFPRMD=1;s.regs.VDP2_N0PRIN=1;s.m_vdp2_priority_pass=1;s.window=false;
 bitmap_rgb32 unit;s.route(unit,{0,1,0,1});assert(unit.pix(0,0)!=0xff102030);

 // An ordinary opaque unit-step layer must still record its raw source/ratio
 // when another layer in the frame can calculate with it.
 s.m_vdp2_composition_active=true;s.regs.VDP2_SFPRMD=s.regs.VDP2_SFCCMD=0;t.alpha=88;
 s.route(unit,{0,1,0,1});assert(s.m_vdp2_raw_top.pix(0,0)==unit.pix(0,0)&&s.m_vdp2_raw_alpha.pix(0,0)==88);
 s.m_vdp2_composition_active=false;
 // Plain 11-bit palette cells must not fall through to the 4-bit decoder.
 t.colour_depth=2;t.bitmap_enable=0;t.colour_calculation_enabled=0;
 bitmap_rgb32 plain,reference;s.route(plain,{0,1,0,1});s.vdp2_draw_scroll_screen(reference,{0,1,0,1});assert(plain.data==reference.data);
 unsigned metadata_cases=0;
 unsigned *priorities[]={&s.regs.VDP2_N0PRIN,&s.regs.VDP2_N1PRIN,&s.regs.VDP2_N2PRIN,&s.regs.VDP2_N3PRIN,&s.regs.VDP2_R0PRIN};
 for(int name:{0,1,2,3,0x80,0x81})for(unsigned base=0;base<8;++base)for(unsigned mode:{1u,2u})for(bool attribute:{false,true})for(unsigned bank:{0u,1u})for(unsigned raw=0;raw<256;++raw){
  unsigned layer=name==0x81?0:name==0x80?4:name;t.layer_name=name;t.colour_depth=1;
  for(unsigned i=0;i<5;++i)*priorities[i]=(base+i+2)%8;
  *priorities[layer]=base;s.regs.VDP2_SFPRMD=(1023&~(3u<<(layer*2)))|(mode<<(layer*2));
  s.regs.VDP2_SFCCMD=0;s.regs.VDP2_SFSEL=bank<<layer;s.regs.VDP2_SFCODE=0x96e1;
  rgb_t pixel=s.vdp2_special_color_pixel(rgb_t(0xff123456),raw,raw);pixel=s.vdp2_special_priority_pixel(pixel,attribute);
  bool match=((bank?0x96:0xe1)>>(raw%16/2))&1;unsigned priority=(base/2)*2+unsigned(attribute&&(mode==1||match));
  if(!priority)assert(uint32_t(pixel)==0);
  else {assert((pixel.a()&0x80)&&((pixel.a()>>2)&7)==priority&&(pixel.a()&1));assert((uint32_t(pixel)&0xffffff)==0x123456);}
  ++metadata_cases;
 }
 std::cout<<metadata_cases<<" all-layer priority/code metadata cases passed\n";
 std::cout<<cases<<" fractional tile/bitmap and combined scroll/mosaic images passed\n";
}
'''
code=code.replace('// ROUTE',route)
code=code.replace('// TILEMAP',extract(head,'struct vdp2_tilemap_capabilities {')+' current_tilemap;').replace('// REGS','\n'.join('unsigned '+n+'=0;' for n in names)).replace('// DECLS','\n'.join(x[:x.index('{')].replace('saturn_state::','')+';' for x in funcs)).replace('// MACROS','\n'.join('#define '+n+' regs.'+n for n in names)).replace('// FUNCTIONS',f).replace('// UNDEFS','\n'.join('#undef '+n for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-scroll-pixels-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-I',str(ROOT/'src/lib/util'),'-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

// license:BSD-3-Clause
// Deterministic pictures across modes, priorities, mix/offset/shadow/gradation flags.
#include "saturn_vdp2_render.h"
#include <array>
#include <iostream>
#include <memory>
using namespace saturn_vdp2_render;
uint32_t mix(uint32_t v){v^=v>>16;v*=0x7feb352d;v^=v>>15;return v;}
struct sprites: sprite_source {
 unsigned seed=0;
 uint16_t sprite_word(unsigned x,unsigned y)const override{return mix(seed+x*19+y*509);}
};
int main(){
 auto vram=std::make_unique<uint32_t[]>(0x20000);std::array<uint32_t,1024> cram;std::array<uint16_t,256> regs;
 std::array<uint32_t,704> dots;auto r=std::make_unique<renderer>();sprites spr;
 uint64_t digest=0xcbf29ce484222325ULL;
 for(unsigned t=0;t<256;++t){
  regs.fill(0);for(unsigned i=0;i<0x20000;++i)vram[i]=mix(i+t*991);for(unsigned i=0;i<cram.size();++i)cram[i]=mix(i+t*37);
  regs[0x0e/2]=(t%3)<<12;regs[0x20/2]=0x0f|((t&8)?0x0f00:0);
  regs[0x22/2]=(t&1)?((t%16)<<8)|(((t/16)%16)<<12)|0x1f:0;
  regs[0x28/2]=((t%5)<<4)|(((t/5)%4)<<12)|((t&4)?2:0);
  regs[0x2a/2]=((t&2)?2:0)|((t&1)?0x20:0);
  // Exercise source-accumulator carries and cycle restarts, including
  // stationary, fractional, unity and maximum horizontal increments.
  static constexpr unsigned increments[]={0,1,0xff,0x100,0x101,0x180,0x1ff,0x7ff};
  for(unsigned n=0;n<2;++n){
   unsigned b=0x70+n*0x10,inc=increments[(t+n*3)%8];
   regs[b/2]=mix(t+n)&0x7ff;regs[(b+2)/2]=(mix(t+n+1)&0xff)<<8;
   regs[(b+8)/2]=inc>>8;regs[(b+10)/2]=(inc&0xff)<<8;
  }
  for(unsigned i=0x10;i<=0x1e;i+=4){regs[i/2]=0x0123;regs[(i+2)/2]=0x4567;}
  for(unsigned i=0;i<4;++i)regs[(0x30+2*i)/2]=0x8000|(mix(t+i)&0x3ff);
  regs[0xe0/2]=(t&15)|((t&16)?0x20:0);regs[0xe2/2]=(t&32)?0xff:0;
  regs[0xe8/2]=(t&64)?0x3f:0;
  static constexpr unsigned cc[]={0,0x012f,0x81ff,0x400f};regs[0xec/2]=cc[(t/8)%4];
  for(unsigned i=0;i<4;++i)regs[(0xf0+i*2)/2]=(1+(t+i)%7)|((1+(t+i+3)%7)<<8);
  regs[0xf8/2]=(1+t%7)|((1+(t+2)%7)<<8);regs[0xfa/2]=(1+(t+4)%7)|((1+(t+5)%7)<<8);
  regs[0x110/2]=(t&128)?0x7f:0;regs[0x112/2]=t&0x7f;
  for(unsigned i=0x100;i<=0x10e;i+=2)regs[i/2]=mix(i+t)&0x1f1f;
  for(unsigned i=0x114;i<=0x11e;i+=2)regs[i/2]=mix(i+t)&0x1ff;
  screen_config cfg;cfg.hreso=t%8;cfg.hires=cfg.hreso&2;cfg.exclusive=cfg.hreso&4;
  cfg.width=((cfg.hreso&1)?352:320)*(cfg.hires?2:1);cfg.lsmd=(t/8)%4;cfg.disp=true;
  spr.seed=t;r->begin_frame({regs.data(),vram.get(),cram.data()},cfg);
  for(unsigned y=0;y<16;++y){r->render_line(y,spr,dots.data());for(unsigned x=0;x<cfg.width;++x){digest^=dots[x];digest*=0x100000001b3ULL;}}
 }
 std::cout<<std::hex<<digest<<"\n";
}

// license:BSD-3-Clause
// Compare issued reads, output buffers and cross-line carry against the old traversal.
#include "saturn_vdp2_fetch.h"
#include "vdp2_fetch_reference.h"
#include <cassert>
#include <iostream>
#include <vector>
using namespace saturn_vdp2_fetch;
uint32_t mix(uint32_t v) { v ^= v >> 16; v *= 0x7feb352d; v ^= v >> 15; return v; }
pattern_name pattern(uint32_t v) {
  pattern_name p; p.character=v&0x3fff;p.palette=(v>>14)&0x7ff;
  p.hflip=v&0x10000000;p.vflip=v&0x20000000;p.priority=v&0x40000000;p.colour_calc=v&0x80000000;return p;
}
struct access {
  uint32_t seed=0,x=0,y=0,inc=8;
  std::vector<uint64_t> reads;
  uint32_t pn_address(unsigned sx,unsigned sy) const { return ((seed&0x78000)+((sy&0x1ff)*64+(sx&0x1ff)/8)*4)&0x7ffff; }
  pattern_name read_pn(uint32_t a) { reads.push_back(a|uint64_t(1)<<32);return pattern(mix(a^seed)); }
  uint32_t read32(uint32_t a) { reads.push_back(a);return mix(a^seed); }
  unsigned bank(uint32_t a) const {return (a>>17)&3;}
  unsigned cycle_x(int c) const {return x+c*inc;}
  unsigned cycle_y(int c) const {return y+(c/7);}
};
bool equal(cycle_dots const&a,cycle_dots const&b) {
  return a.dot==b.dot && a.attr==b.attr && a.written==b.written && a.pn_cycle==b.pn_cycle && a.any_write==b.any_write;
}
int main() {
 uint32_t rng=0x3865042;auto next=[&](){rng=mix(rng+0x9e3779b9);return rng;};
 for(unsigned trial=0;trial<8000;++trial) {
  unsigned layer=trial%4,cf=(trial/4)%5,slots=(trial&32)?HIRES_SLOTS:SLOTS;
  schedule s;
  for(unsigned b=0;b<4;++b) for(unsigned t=0;t<SLOTS;++t) {
   uint32_t v=next();unsigned cmd=(v%3==0)?CMD_PN0+layer:(v%3==1)?CMD_CP0+layer:CMD_NONE;
   s.raw[b][t]=cmd;s.command[b][t]=(v&0x100)?cmd:CMD_NONE;
  }
  reduction r{bool(trial&1),bool(trial&2)};
  bitmap_config bm;bm.enabled=layer<2 && (trial&64);bm.base=next()&0x7e000;bm.size=trial%4;bm.attr=pattern(next());
  carry_state original,optimized;
  for(unsigned i=0;i<4;++i) {original.last_pn[i]=pattern(next());original.buffer.attr[i]=pattern(next());for(auto &dot:original.buffer.dot[i])dot=next();}
  original.pn_fetched=trial&128;original.buffer.written=next();original.buffer.pn_cycle=-10;original.buffer.any_write=trial&256;
  optimized=original;
  access a{next(),next()&1023,next()&511,1+(next()%32)},b=a;
  for(unsigned line=0;line<3;++line) {
   std::vector<cycle_dots> ref,out;int cycles=41+(trial%50);
   reference_fetch_line(s,layer,cf,trial&8,r,bm,cycles,a,original,[&](int,cycle_dots const&v){ref.push_back(v);},slots);
   fetch_line(s,layer,cf,trial&8,r,bm,cycles,b,optimized,[&](int,cycle_dots const&v){out.push_back(v);},slots);
   assert(a.reads==b.reads && ref.size()==out.size());
   for(unsigned i=0;i<ref.size();++i) assert(equal(ref[i],out[i]));
   assert(equal(original.buffer,optimized.buffer) && original.last_pn==optimized.last_pn && original.pn_fetched==optimized.pn_fetched && original.vcs_latch==optimized.vcs_latch);
   ++a.y;++b.y;
  }
 }
 std::cout<<"VDP2 fetch equivalence PASS: 24000 lines, issued-read traces, every output buffer and carry state\n";
}

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production cycle presence/address permissions; not a bus-timing oracle."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--mutation',choices=('slots','partition','rotation','fetch-bank','vcsc-order'));a=p.parse_args()
s=(ROOT/'src/mame/sega/saturn.cpp').read_text();start=s.index('uint8_t saturn_state::vdp2_check_vram_cycle_pattern_registers(');end=s.index('{',start)+1;depth=1
while depth:
 depth+=(s[end]=='{')-(s[end]=='}');end+=1
f=s[start:end]
for sig in ('void saturn_state::vdp2_prepare_vram_access(', 'bool saturn_state::vdp2_normal_vram_access('):
 start=s.index(sig);end=s.index('{',start)+1;depth=1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 f+='\n'+s[start:end]
if a.mutation=='fetch-bank':f=f.replace(')) & 3;', ')) & 2;')
if a.mutation=='vcsc-order':f=f.replace('(slots & 6)', '(slots & 7)').replace('(slots & 4)', '(slots & 7)')
if a.mutation=='slots':f=f.replace('? 4 : 8','? 8 : 8')
if a.mutation=='partition':f=f.replace('if ((bank & 1) &&', 'if (false && (bank & 1) &&')
if a.mutation=='rotation':f=f.replace('bank >= 2 && VDP2_R1ON', 'bank >= 4 && VDP2_R1ON')
code=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
struct saturn_state {
 std::array<uint16_t,8> cycles;unsigned ram=0,r0=0,r1=0;
 bool m_vdp2_fetch_access_active=true;unsigned vcsc0=0;
 std::array<std::array<uint8_t,16>,4> m_vdp2_fetch_slots{};
 void vdp2_prepare_vram_access();bool vdp2_normal_vram_access(uint32_t,unsigned)const;
 struct video {unsigned hreso=0;bool large=false;bool get_vramsz(){return large;}unsigned get_hreso(){return hreso;}} dev;video *m_vdp2=&dev;
 uint8_t vdp2_check_vram_cycle_pattern_registers(uint8_t,uint8_t,uint8_t);
};
#define VDP2_N0VCSC vcsc0
#define VDP2_RAMCTL ram
#define VDP2_R0ON r0
#define VDP2_R1ON r1
// MACROS
// FUNCTION
int main(){saturn_state s;unsigned cases=0;
 for(unsigned h=0;h<8;++h)for(unsigned partition=0;partition<4;++partition)
 for(unsigned owner=0;owner<4;++owner)for(unsigned rotation=0;rotation<4;++rotation)
 for(unsigned pn=0;pn<32;++pn)for(unsigned cp=0;cp<32;++cp)for(bool bitmap:{false,true}){
  s.dev.hreso=h;s.ram=partition*256;s.r0=rotation&1;s.r1=(rotation>>1)&1;
  // Reserve different bank roles simultaneously, including coefficient RAM.
  for(unsigned bank=0;bank<4;++bank)s.ram|=((owner+bank)%4)<<(bank*2);
  s.cycles.fill(0xffff);
  auto put=[&](unsigned pos,unsigned command){unsigned reg=pos/4,shift=12-4*(pos%4);s.cycles[reg]=(s.cycles[reg]&~(15u<<shift))|(command<<shift);};
  put(pn,1);put(cp,5);
  bool names=bitmap,characters=false;
  for(unsigned pos=0;pos<32;++pos){
   unsigned bank=pos/8,slot=pos%8;
   bool active=(h<2||slot<4)&&(!(bank%2)||((partition>>(bank/2))&1));
   if(s.r0&&((owner+bank)%4))active=false;
   if(s.r1&&bank>=2)active=false;
   if(active){names|=pos==pn&&pn!=cp;characters|=pos==cp;}
  }
  assert(s.vdp2_check_vram_cycle_pattern_registers(1,5,bitmap)==(names&&characters));++cases;
  if(bitmap)continue;
  s.vdp2_prepare_vram_access();
  for(unsigned bank=0;bank<4;++bank){
   unsigned effective=((partition>>(bank/2))&1)?bank:bank/2*2;
   bool owned=(s.r1&&bank>=2)||(s.r0&&(owner+effective)%4);
   for(unsigned command:{1u,5u}){
    unsigned pos=command==1?pn:cp;
    bool expected=!owned && pos/8==effective && (h<2||pos%8<4) && (command==5||pn!=cp);
    for(bool large:{false,true}){
     s.dev.large=large;unsigned address=(bank<<(large?18:17))+0x1234;
     assert(s.vdp2_normal_vram_access(address,command)==expected);
     assert(s.vdp2_normal_vram_access(address+0x100000,command)==expected);
    }
   }
  }
 }
 unsigned vertical=0;s.r0=s.r1=0;s.ram=0x300;s.dev.large=false;
 for(unsigned h:{0u,2u})for(unsigned first=0;first<32;++first)for(unsigned second=0;second<32;++second)for(bool n0:{false,true}){
  s.dev.hreso=h;s.vcsc0=n0;s.cycles.fill(0xffff);
  auto put=[&](unsigned pos,unsigned command){unsigned reg=pos/4,shift=12-4*(pos%4);s.cycles[reg]=(s.cycles[reg]&~(15u<<shift))|(command<<shift);};
  put(first,12);put(second,13);s.vdp2_prepare_vram_access();
  for(unsigned bank=0;bank<4;++bank){
   bool a=first/8==bank&&first%8<=1&&first!=second;
   bool b=second/8==bank&&second%8<=2&&(!n0||(a&&first%8<second%8));
   assert(s.vdp2_normal_vram_access(bank*0x20000,12)==a);
   assert(s.vdp2_normal_vram_access(bank*0x20000,13)==b);++vertical;
  }
 }
 std::cout<<vertical<<" VCSC addressed-bank/early-slot/order decisions passed\n";
 std::cout<<cases<<" partition/slot/rotation-owner cycle-presence cases passed\n";
}
'''
code=code.replace('// MACROS','\n'.join(f'#define VDP2_CYCA{i//2}{"U" if i%2 else "L"} this->cycles[{i}]' for i in range(8))).replace('// FUNCTION',f)
with tempfile.TemporaryDirectory(prefix='saturn-cycles-') as t:
 cpp=Path(t)/'test.cpp';exe=Path(t)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

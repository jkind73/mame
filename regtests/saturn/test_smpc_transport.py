#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Extracted INTBACK transport, page flags, cancellation and restore tests.

The actual SMPC methods execute against recording timer/IRQ/controller endpoints.
Snapshot restore copies the saved fields, not MAME's save manager. No bit-serial
controller timing, VBlank timeout or extended-size peripheral support is claimed.
"""
import os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'src/mame/sega/smpc.cpp').read_text()

def extract(signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]
functions='\n'.join(extract(s) for s in ('void smpc_hle_device::resolve_intback()', 'void smpc_hle_device::read_saturn_ports()', 'void smpc_hle_device::ireg_w(', 'inline void smpc_hle_device::sr_ack()', 'inline void smpc_hle_device::sr_set(', 'inline void smpc_hle_device::sf_ack(', 'inline void smpc_hle_device::sf_set()', 'TIMER_CALLBACK_MEMBER(smpc_hle_device::intback_continue_request)', 'void smpc_hle_device::device_reset()'))
mutation=os.environ.get('MUTATE_SMPC_TRANSPORT','')
if mutation=='oreg31':
    functions=functions.replace('  irq_request();\n  sf_ack(false);\n}', '  irq_request();\n  m_oreg[31] = 0x10;\n  sf_ack(false);\n}')
if mutation=='resample':
    functions=functions.replace('    if (first)\n      read_saturn_ports();', '    read_saturn_ports();')
if mutation=='remaining':
    functions=functions.replace('(more ? 0x20 : 0)', '0')
if mutation=='zero-mode':
    functions=functions.replace('if (((m_pmode >> (port * 2)) & 3) == 3)', 'if (false)')
if mutation=='empty-tap':
    functions=functions.replace('id == 0xff ? 0 : (id & 0xf)', '(id & 0xf)')
if mutation=='break':
    functions=functions.replace('        m_peripheral_size = m_peripheral_pos = 0;', '')
harness=r'''
#include <algorithm>
#include <array>
#include <vector>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
using u8=uint8_t; using offs_t=unsigned;
#define LOGMASKED(...) ((void)0)
#define TIMER_CALLBACK_MEMBER(name) void name(int param)
struct attotime {
 static constexpr int zero=0;
 static int from_usec(int n){return n;}
 static int from_seconds(int n){return n*1000000;}
};
struct timer {
 bool pending=false; unsigned arms=0;
 void reset(){pending=false;}
 void adjust(int n){assert(n==700);pending=true;++arms;}
 void adjust(int n,int p,int rate){assert(n==0&&p==0&&rate==1000000);pending=true;}
};
struct port {
 u8 status=0xf0;std::vector<u8> ids, data;
 unsigned status_reads=0,id_reads=0,data_reads=0;
 u8 read_status(){++status_reads;return status;}
 u8 read_id(unsigned i){++id_reads;return ids.at(i);}
 // ST-169 pp.70-73: the separate length byte is only queried for an ID
 // whose low nibble is zero.  setup() only builds 0x20|size with size>=2,
 // so this must never be reached here; asserting that also catches a
 // regression that consults it for a plain fixed-size ID.
 u8 read_ext_size(unsigned){assert(false);return 0;}
 // Synthetic variable-length devices keep a packed backing vector; the new
 // interface explicitly identifies a physical device before its payload byte.
 u8 read_ctrl_slot(unsigned index,unsigned offset){
  unsigned base=0;
  for(unsigned i=0;i<index;++i)base+=ids.at(i)==0xff?0:(ids.at(i)&15);
  ++data_reads;return data.at(base+offset);
 }
};
struct smpc_hle_device {
 bool m_resb=false,m_sf=false,m_cd_sf=false,m_iosel1=true,m_iosel2=true,m_exle1=true,m_exle2=true;
 u8 m_sr=0,m_ddr1=0,m_ddr2=0,m_pdr1_readback=0,m_pdr2_readback=0;
 u8 m_ireg[7]{},m_oreg[32]{},m_comreg=0,m_ckchg_tick=0,m_prev_sndoff=0,m_prev_sshoff=0,m_prev_cdoff=0;
 bool m_command_in_progress=false,m_NMI_reset=false,m_cur_dotsel=false,m_has_ctrl_ports=true;
 u8 m_intback_stage=0,m_pmode=0;
 enum {INTBACK_WAIT_NONE,INTBACK_WAIT_COMMAND,INTBACK_WAIT_CONTINUE};
 u8 m_intback_wait=INTBACK_WAIT_NONE;
 bool m_in_vblank=false;
 u8 m_reset_button_count=0;
 u8 m_intback_buf[3]{},m_smem[5]{},m_rtc_data[7]{},m_region_code=1;
 u8 m_peripheral_data[512]{};uint16_t m_peripheral_size=0,m_peripheral_pos=0;
 port *m_ctrl1=nullptr,*m_ctrl2=nullptr;
 unsigned ports=0,irqs=0;
 timer cmd,intback,snd,rtc;
 timer *m_cmd_timer=&cmd,*m_intback_timer=&intback,*m_sndres_timer=&snd,*m_rtc_timer=&rtc;
 void resolve_intback();void read_saturn_ports(); void irq_request(){++irqs;}
 void ireg_w(offs_t,uint8_t);void sr_ack();void sr_set(uint8_t);void sf_ack(bool);void sf_set();
 void intback_continue_request(int);void device_reset();
 void fire(){if(intback.pending){intback.pending=false;intback_continue_request(0);}}
};
// FUNCTIONS
void setup(port &p,unsigned count,unsigned size,bool gap,unsigned seed){
 p.status=count==0?0xf0:count==1?0xf1:0x10|count;
 for(unsigned i=0;i<count;++i){
  bool absent=gap&&i==count/2;
  p.ids.push_back(absent?0xff:0x20|size);
  if(!absent)for(unsigned j=0;j<size;++j)p.data.push_back(u8(seed+i*17+j));
 }
}
std::vector<u8> expected(port const &p){
 std::vector<u8> v{p.status};unsigned off=0;
 for(u8 id:p.ids){v.push_back(id);if(id!=0xff)for(unsigned j=0;j<(id&15);++j)v.push_back(p.data.at(off++));}
 return v;
}
int main(){
 unsigned cases=0;
 for(unsigned n1:{0u,1u,4u,6u,15u})for(unsigned n2:{0u,1u,4u,6u,15u})
 for(unsigned size:{2u,3u,4u,5u,6u,15u})for(bool gap:{false,true})
 for(unsigned mode1:{0u,1u,3u})for(unsigned mode2:{0u,1u,3u})for(bool status:{false,true}){
  port p1,p2;setup(p1,n1,size,gap,0x31);setup(p2,n2,size,gap,0x87);
  std::vector<u8> want;
  for(auto [p,mode]:{std::pair{&p1,mode1},std::pair{&p2,mode2}})
   if(mode!=3){auto part=expected(*p);want.insert(want.end(),part.begin(),part.end());}
  smpc_hle_device s;s.m_ctrl1=&p1;s.m_ctrl2=&p2;s.m_sr=0;
  s.m_intback_buf[0]=status;s.m_intback_buf[1]=((mode2<<2|mode1)<<4)|8;
  s.resolve_intback();
  if(status){s.ireg_w(1,0x80);s.fire();}
  unsigned cursor=0,page=0;std::vector<u8> got;
  for(;;){
   unsigned take=std::min<unsigned>(32,want.size()-cursor);
   bool more=cursor+take<want.size();
   assert(s.m_sr==(0x80|(page==0?0x40:0)|(more?0x20:0)|(mode2<<2)|mode1));
   assert(s.m_intback_stage==(more?2:0)&&!s.m_sf);
   got.insert(got.end(),s.m_oreg,s.m_oreg+take);
   for(unsigned j=0;j<take;++j)assert(s.m_oreg[j]==want.at(cursor+j));
   if(take<32)assert(s.m_oreg[31]==0x10);
   cursor+=take;++page;
   if(!more)break;
   // Save/mutate/restore the registered packet state; mutate physical inputs
   // separately so any unintended resampling corrupts the remaining pages.
   std::array<u8,512> saved;std::copy_n(s.m_peripheral_data,512,saved.begin());
   auto pos=s.m_peripheral_pos,total=s.m_peripheral_size;
   std::fill(std::begin(s.m_peripheral_data),std::end(s.m_peripheral_data),0);
   s.m_peripheral_pos=s.m_peripheral_size=0;
   std::copy(saved.begin(),saved.end(),s.m_peripheral_data);
   s.m_peripheral_pos=pos;s.m_peripheral_size=total;
   std::fill(p1.data.begin(),p1.data.end(),0xee);std::fill(p2.data.begin(),p2.data.end(),0xdd);
   u8 cont=s.m_ireg[0]^0x80;s.ireg_w(1,cont);assert(s.m_sf&&s.intback.pending);
   s.fire();
  }
  assert(got==want);
  assert(p1.status_reads==unsigned(mode1!=3)&&p2.status_reads==unsigned(mode2!=3));
  assert(p1.id_reads==(mode1==3?0:n1)&&p2.id_reads==(mode2==3?0:n2));
  assert(s.irqs==page+unsigned(status));
  // No callback/continue after completion may poll inputs or emit an IRQ.
  auto irqs=s.irqs;s.intback_continue_request(0);assert(s.irqs==irqs);
  ++cases;
 }
 for(bool reset:{false,true}){
  port p;setup(p,15,15,false,0x21);
  smpc_hle_device s;s.m_ctrl1=&p;s.m_intback_buf[1]=8;s.resolve_intback();
  assert(s.m_intback_stage==2);
  s.ireg_w(1,0x80);assert(s.intback.pending);
  if(reset)s.device_reset();else s.ireg_w(1,0xc0);
  auto irqs=s.irqs;s.fire();s.intback_continue_request(0);
  assert(s.irqs==irqs&&!s.intback.pending&&!s.m_intback_stage);
  assert(!s.m_peripheral_size&&!s.m_peripheral_pos);
  ++cases;
 }
 std::cout<<cases<<" SMPC page/snapshot/mode/OREG31/cancel cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='saturn-smpc-') as temp:
    cpp=Path(temp)/'smpc.cpp';exe=Path(temp)/'smpc';cpp.write_text(harness.replace('// FUNCTIONS',functions))
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
# Registration is source-checked; the fixture's rewind is not a live save manager.
for field in ('m_peripheral_data', 'm_peripheral_size', 'm_peripheral_pos'):
    assert f'save_item(NAME({field}));' in source

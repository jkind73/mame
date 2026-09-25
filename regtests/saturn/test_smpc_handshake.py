#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute SMPC IREG0 CONTINUE/BREAK, timer callback and reset bodies.

--baseline tests the old handlers. Scheduler/ports/IRQs are recording endpoints.
"""
import argparse, os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true');a=p.parse_args()
path='src/mame/sega/smpc.cpp';current=(ROOT/path).read_text()
source=subprocess.check_output(['git','show','e7cff8b86e6e028453d01fcffc862bb47be3c2ec:'+path],cwd=ROOT,text=True) if a.baseline else current

def extract(signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]
functions='\n'.join(extract(s) for s in ('void smpc_hle_device::ireg_w(', 'inline void smpc_hle_device::sr_ack()', 'inline void smpc_hle_device::sr_set(', 'inline void smpc_hle_device::sf_ack(', 'inline void smpc_hle_device::sf_set()', 'TIMER_CALLBACK_MEMBER(smpc_hle_device::intback_continue_request)', 'void smpc_hle_device::device_reset()'))
harness=r'''
#include <algorithm>
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
struct smpc_hle_device {
 bool m_resb=false,m_sf=false,m_cd_sf=false,m_iosel1=true,m_iosel2=true,m_exle1=true,m_exle2=true;
 u8 m_sr=0,m_ddr1=0,m_ddr2=0,m_pdr1_readback=0,m_pdr2_readback=0;
 u8 m_ireg[7]{},m_oreg[32]{},m_comreg=0,m_ckchg_tick=0,m_prev_sndoff=0,m_prev_sshoff=0,m_prev_cdoff=0;
 bool m_command_in_progress=false,m_NMI_reset=false,m_cur_dotsel=false,m_has_ctrl_ports=true;
 u8 m_intback_stage=0,m_pmode=0;
 // smpc.h:171-173 -- ST-169 p.50/p.56: collection may not start during
 // vertical blanking, so a CONTINUE seen inside VBlank defers its timer
 // to VBlank-OUT instead of arming it immediately.
 enum {INTBACK_WAIT_NONE,INTBACK_WAIT_COMMAND,INTBACK_WAIT_CONTINUE};
 u8 m_intback_wait=INTBACK_WAIT_NONE;
 bool m_in_vblank=false;
 u8 m_reset_button_count=0;
 u8 m_peripheral_data[512]{};uint16_t m_peripheral_size=64,m_peripheral_pos=0;
 unsigned ports=0,irqs=0;
 timer cmd,intback,snd,rtc;
 timer *m_cmd_timer=&cmd,*m_intback_timer=&intback,*m_sndres_timer=&snd,*m_rtc_timer=&rtc;
 void read_saturn_ports(){++ports;m_peripheral_size=64;m_peripheral_pos=0;} void irq_request(){++irqs;}
 void ireg_w(offs_t,uint8_t);void sr_ack();void sr_set(uint8_t);void sf_ack(bool);void sf_set();
 void intback_continue_request(int);void device_reset();
 void fire(){if(intback.pending){intback.pending=false;intback_continue_request(0);}}
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned stage=0;stage<3;++stage)
  for(unsigned previous : {0u,0x80u})
   for(unsigned data=0;data<256;++data){
    // Simultaneous CONT and BREAK is explicitly prohibited (table 3.2).
    if((data&0x40)&&((previous^data)&0x80))continue;
    smpc_hle_device s;s.m_intback_stage=stage;s.m_peripheral_pos=stage==2?32:0;s.m_ireg[0]=previous;s.m_sr=0xe5;
    s.ireg_w(1,data);
    bool cont=stage&&!(data&0x40)&&((previous^data)&0x80);
    bool stop=stage&&(data&0x40);
    assert(s.intback.pending==cont&&s.m_sf==cont);
    assert(s.m_intback_stage==(stop?0:stage));
    assert(s.m_sr==(stop?5:0xe5));
    s.fire();
    assert(s.irqs==unsigned(cont)&&s.ports==unsigned(cont&&stage==1));
    if(cont){assert(!s.m_sf&&s.m_oreg[31]==0);assert(s.m_intback_stage==(stage==2?0:2));}
    ++cases;
   }
 for(unsigned stage : {1u,2u})
  for(unsigned previous : {0u,0x80u}){
   smpc_hle_device s;s.m_intback_stage=stage;s.m_peripheral_pos=stage==2?32:0;s.m_ireg[0]=previous;s.m_sr=0xe7;
   u8 cont=previous^0x80;s.ireg_w(1,cont);assert(s.intback.pending&&s.m_sf);
   // Rewriting the same CONT bit must not restart or postpone the timer.
   unsigned arms=s.intback.arms;s.ireg_w(1,cont);assert(s.intback.arms==arms);
   s.ireg_w(1,cont|0x40);assert(!s.intback.pending&&!s.m_sf&&s.m_intback_stage==0);
   s.fire();s.intback_continue_request(0);assert(s.irqs==0&&s.ports==0);
   ++cases;
  }
 for(unsigned offset=0;offset<14;++offset){
  smpc_hle_device s;s.m_intback_stage=1;s.ireg_w(offset,0x80);
  assert(s.intback.pending==(offset==1));
  for(unsigned i=0;i<7;++i)assert(s.m_ireg[i]==((offset&1)&&i==offset/2?0x80:0));
  ++cases;
 }
 for(unsigned stage=0;stage<3;++stage){
  smpc_hle_device s;s.m_intback_stage=stage;s.m_peripheral_pos=stage==2?32:0;s.intback.adjust(700);s.m_sf=true;
  s.device_reset();assert(!s.intback.pending&&!s.m_sf&&!s.m_cd_sf&&s.m_intback_stage==0);
  assert(!s.m_iosel1&&!s.m_iosel2&&!s.m_exle1&&!s.m_exle2);
  s.fire();s.intback_continue_request(0);assert(!s.irqs&&!s.ports);
  ++cases;
 }
 for(unsigned stage:{1u,2u}){
  smpc_hle_device s;s.m_has_ctrl_ports=false;s.m_intback_stage=stage;
  s.intback_continue_request(0);
  assert(s.m_oreg[31]==0x10&&s.m_sr==(stage==1?0xc0:0x80));
  assert(s.ports==0&&s.irqs==1&&s.m_intback_stage==(stage==1?2:0));
  ++cases;
 }
 assert(cases==1175);
 std::cout<<cases<<" SMPC handshake/cancel/reset scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='saturn-smpc-') as temp:
    cpp=Path(temp)/'smpc.cpp';exe=Path(temp)/'smpc';cpp.write_text(harness.replace('// FUNCTIONS',functions))
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

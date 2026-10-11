#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual-method ASan/UBSan tests for chapter-11 timer clocks and compare outputs."""
from pathlib import Path
import subprocess
import tempfile
from sh7604_sci_standby_test import extract
PREAMBLE=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <random>
#include <vector>
using offs_t=unsigned;
#define BIT(v,n) (((v)>>(n))&1)
#define ACCESSING_BITS_8_15 (mem_mask&0xff00)
#define ACCESSING_BITS_0_7 (mem_mask&0xff)
#define TIMER_CALLBACK_MEMBER(name) void name(int param)
static constexpr int div_tab[4]={3,5,7,0};
constexpr int CLEAR_LINE=0,ASSERT_LINE=1,SUSPEND_REASON_CLOCK=64;
struct attotime {int64_t v;bool is_never()const{return v==-1;}attotime(int64_t n=0):v(n){};static const attotime never;
 friend attotime operator+(attotime a,attotime b){return a.v+b.v;}
 friend attotime operator*(attotime a,unsigned n){return a.v*n;}
 friend attotime operator/(attotime a,unsigned n){return a.v/n;}
 friend attotime operator-(attotime a,attotime b){return a.v-b.v;}};
const attotime attotime::never(-1);
struct sh2_device {void device_clock_changed(){}};
struct sh7604_device:sh2_device {
 uint32_t m_frt_generation=0,m_frt_clockrate=1,frequency=1;uint32_t clock(){return frequency;}
 void refresh_resync(){} void refresh_activate(){}
 uint32_t m_refresh_clockrate=1;attotime m_refresh_epoch;void* m_refresh_timer=nullptr;
 void suspend(int,bool){}
 uint64_t cycles=0,m_frc_base=0,m_frt_epoch=0;uint32_t m_bus_pending=0;
 bool m_isdrc=false,running=false,debug=false,m_standby=false;
 uint8_t m_sbycr=0,m_tier=1,m_ftcsr=0,m_ftcsr_read_flags=0,m_frc_tcr=0,m_tocr=0xe0,m_frt_temp=0;
 uint16_t m_frc=0,m_ocra=0xffff,m_ocrb=0xffff,m_frc_icr=0;
 attotime m_frt_capture_clock_delay=attotime::never;bool m_frt_capture_pending=false;uint64_t m_frt_icr_read_cycle=~uint64_t(0),m_frt_clear_cycle=~uint64_t(0);
 int m_frt_clock_input=0,m_frt_input=0,m_frt_output[2]{};
 static constexpr uint8_t ICF=0x80,OCFA=8,OCFB=4,OVF=2,CCLRA=1;
 struct timer {sh7604_device&d;int64_t deadline=-1;attotime remaining(){return deadline<0?-1:deadline-d.cycles;}void adjust(attotime t){deadline=t.v<0?-1:d.cycles+t.v;}} timer{*this},capture{*this},*m_timer=&timer,*m_frt_capture_timer=&capture;
 struct machine_type {sh7604_device&d;attotime time(){return d.cycles;}bool side_effects_disabled(){return d.debug;}};
 machine_type machine(){return {*this};}uint64_t total_cycles()const{return cycles;}
 bool executing()const{return running;}attotime local_time(){return cycles;}attotime cycles_to_attotime(uint64_t n){return n/frequency;}
 struct callback {bool bound=false;unsigned calls=0;uint32_t value=0;bool isnull(){return !bound;}void operator()(uint32_t v){calls++;value=v;}}m_ftcsr_read_cb;
 int irq_checks=0;void sh2_recalc_irq(){irq_checks++;}
 std::vector<int> outputs[2];std::function<void(int)> on_a,on_b;
 void m_ftoa(int n){outputs[0].push_back(n);if(on_a)on_a(n);}void m_ftob(int n){outputs[1].push_back(n);if(on_b)on_b(n);}
 // DECLARATIONS
 void tick(){frt_clock_w(0);frt_clock_w(1);}
};
'''
MAIN=r'''
int main(){
 sh7604_device d;
 d.frc_tcr_w(3);d.m_ocra=2;d.m_ocrb=3;d.tocr_w(3);
 d.tick();assert(d.m_frc==1 && !(d.m_ftcsr&12));
 d.tick();assert(d.m_frc==2 && !(d.m_ftcsr&12));
 d.tick();assert(d.m_frc==3 && (d.m_ftcsr&12)==8 && d.m_frt_output[0]==1 && d.m_frt_output[1]==0);
 d.tick();assert(d.m_frc==4 && (d.m_ftcsr&12)==12 && d.m_frt_output[1]==1);
 d.frt_clock_w(1);d.frt_clock_w(1);assert(d.m_frc==4);d.frt_clock_w(0);assert(d.m_frc==4);
 d.tocr_w(0);assert(d.m_frt_output[0]==1 && d.m_frt_output[1]==1);
 d.m_frc=2;d.tick();assert(d.m_frt_output[0]==0 && (d.m_ftcsr&8));
 d.m_frc=3;d.tick();assert(d.m_frt_output[1]==0);
 d.m_frc=0xffff;d.m_ocra=d.m_ocrb=0xffff;d.m_ftcsr=0;d.tocr_w(3);d.tick();
 assert(d.m_frc==0 && (d.m_ftcsr&14)==14 && d.m_frt_output[0] && d.m_frt_output[1]);
 d.m_frc=0xffff;d.m_ftcsr=1;d.tick();assert(d.m_frc==0 && (d.m_ftcsr&14)==12);
 d.m_frc=0;d.m_ocra=1;d.m_ocrb=1;d.m_ftcsr=1;
 d.tick();assert(d.m_frc==1);d.tick();assert(d.m_frc==0 && (d.m_ftcsr&12)==12);
 d.tocr_w(0);d.tick();assert(d.m_frt_output[0]);d.tick();assert(!d.m_frt_output[0] && !d.m_frt_output[1] && d.m_frc==0);
 d.m_sbycr=2;auto n=d.m_frc;d.tick();assert(d.m_frc==n);d.m_sbycr=0;d.frt_clock_w(1);assert(d.m_frc==n);
 d.m_standby=true;d.tick();assert(d.m_frc==n);d.m_standby=false;
 // Repeated reads preserve the prescaler phase in all three internal modes.
 for(int select=0;select<3;select++){
  sh7604_device p;p.m_frc_tcr=select;unsigned period=1U<<div_tab[select];p.m_ocra=2;
  for(unsigned c=1;c<3*period;c++){p.cycles=c;p.sh2_timer_resync();assert(p.m_frc==c/period);assert(!(p.m_ftcsr&8));}
  p.sh2_timer_activate();assert(p.timer.deadline==3*period);
  p.cycles=3*period;p.sh2_timer_callback(0);assert(p.m_frc==3 && (p.m_ftcsr&8));
 }
 // A selected internal high->low switch produces a count; other switches don't.
 sh7604_device p;p.cycles=4;p.frc_tcr_w(1);assert(p.m_frc==1);
 p.frc_tcr_w(0);assert(p.m_frc==1);p.cycles=8;p.sh2_timer_resync();assert(p.m_frc==2);
 // Pending DRC cycles matter only while the CPU is executing.
 sh7604_device c;c.m_isdrc=true;c.m_bus_pending=16;c.sh2_timer_resync();assert(c.m_frc==0);
 c.running=true;c.sh2_timer_resync();assert(c.m_frc==2);c.cycles=16;c.running=false;c.sh2_timer_resync();assert(c.m_frc==2);
 // Capture remains independent of the clock source and observes current FRC.
 d.m_frc=0x1234;d.m_ftcsr=0;d.m_frc_tcr=0x83;d.set_frt_input(0);d.set_frt_input(1);
 assert(d.m_frc_icr==0x1234 && (d.m_ftcsr&0x80));
 d.cycles=111;d.frt_reset();assert(d.m_ocra==0xffff && d.m_ocrb==0xffff && !d.m_frc && !d.m_frt_output[0] && !d.m_frt_output[1]);
 assert(d.m_frc_base==111 && d.m_frt_epoch==111);
 // CPU write priorities on the matching timer clock.
 sh7604_device a;a.m_frc=1;a.m_ocra=1;a.m_ftcsr=1;a.m_tocr=2;a.m_frc_base=8;a.cycles=16;
 a.frc_w(0,0x5555,0xffff);assert(a.m_frc==0 && (a.m_ftcsr&8) && a.m_frt_output[0]==1);
 sh7604_device b;b.m_frc=1;b.m_ocra=1;b.m_tocr=2;b.m_frc_base=8;b.cycles=16;
 b.ocra_b_w(0,0x9999,0xffff);assert(b.m_frc==2 && !(b.m_ftcsr&8) && !b.m_frt_output[0] && b.m_ocra==0x9999);
 sh7604_device o;o.m_frc=0xffff;o.cycles=8;o.frc_w(0,7,0xffff);assert(o.m_frc==7 && !(o.m_ftcsr&2));
 // An ICR upper read and capture on the same cycle defer capture one drive clock.
 sh7604_device r;r.m_frc_tcr=0x83;r.m_frc=2;r.cycles=8;r.m_frc_base=8;
 r.frc_icr_r(0,0xff00);r.set_frt_input(1);assert(r.m_frt_capture_pending && !(r.m_ftcsr&0x80) && r.capture.deadline==12);
 r.cycles=10;r.tick();r.cycles=12;r.frt_capture_callback(0);assert(!r.m_frt_capture_pending && r.m_frc_icr==3 && (r.m_ftcsr&0x80));
 r.debug=true;r.cycles=13;r.frc_icr_r(0,0xff00);assert(r.m_frt_icr_read_cycle==8);
 // Frequency changes preserve remaining capture clocks and reschedule compares.
 sh7604_device rate;rate.frequency=2;rate.m_frt_clockrate=2;rate.m_ocra=2;
 rate.sh2_timer_activate();assert(rate.timer.deadline==12);
 rate.m_frt_capture_pending=true;rate.capture.adjust(2);rate.frequency=4;rate.device_clock_changed();
 assert(rate.timer.deadline==6 && rate.capture.deadline==1 && rate.m_frt_clockrate==4);
 // Host CKIO pause freezes internal events and keeps the capture delay in clocks.
 rate.frequency=0;rate.device_clock_changed();assert(rate.timer.deadline==-1 && rate.capture.deadline==-1);
 rate.frt_clock_w(1);assert(rate.m_frc==0);
 rate.frequency=2;rate.device_clock_changed();assert(rate.capture.deadline==2 && rate.timer.deadline==12);
 // A reset from a pin callback must not leak a stale simultaneous B output.
 sh7604_device reset;reset.m_frc_tcr=3;reset.m_ocra=reset.m_ocrb=0;reset.m_tocr=3;
 reset.on_a=[&](int level){if(level)reset.frt_reset();};reset.tick();
 assert(!reset.m_frt_output[0] && !reset.m_frt_output[1] && !reset.m_ftcsr && !reset.m_frc && reset.m_ocra==0xffff);
 // Status observers see resynchronized values and do not run for debugger reads.
 sh7604_device observer;observer.m_ocra=1;observer.m_ftcsr_read_cb.bound=true;observer.cycles=16;
 assert(observer.ftcsr_r()==8 && observer.m_ftcsr_read_cb.value==0x01080002);
 observer.debug=true;observer.m_ftcsr_read_flags=0;observer.ftcsr_r();
 assert(observer.m_ftcsr_read_cb.calls==1 && !observer.m_ftcsr_read_flags);
 // Event-jump implementation versus a per-clock reference over wrap and clear.
 std::mt19937 rng(7604);
 for(unsigned test=0;test<1000;test++){
  sh7604_device x;x.m_frc=rng();x.m_ocra=(test%9==0)?0:uint16_t(rng());x.m_ocrb=(test%7==0)?x.m_ocra:uint16_t(rng());
  x.m_ftcsr=rng()&15;x.m_tocr=rng()&3;x.m_frt_output[0]=rng()&1;x.m_frt_output[1]=rng()&1;
  uint16_t frc=x.m_frc;uint8_t flags=x.m_ftcsr;int oa=x.m_frt_output[0],ob=x.m_frt_output[1];unsigned ticks=rng()%100000;
  for(unsigned i=0;i<ticks;i++){
   bool a=frc==x.m_ocra,b=frc==x.m_ocrb,clear=a&&(flags&1);
   if(a){flags|=8;oa=(x.m_tocr>>1)&1;}if(b){flags|=4;ob=x.m_tocr&1;}
   if(clear)frc=0;else {frc++;if(!frc)flags|=2;}
  }
  x.frt_advance(ticks);assert(x.m_frc==frc && x.m_ftcsr==flags && x.m_frt_output[0]==oa && x.m_frt_output[1]==ob);
 }
 std::cout<<"SH7604 FRT actual-method ASan/UBSan PASS\n";
}
'''
def main():
 source=Path('src/devices/cpu/sh/sh7604.cpp').read_text()
 names=('frt_cycles','frt_drive','frt_advance','frt_clock_w','sh2_timer_resync','sh2_timer_activate','sh2_timer_callback','frc_tcr_w','tocr_w','frt_reset','set_frt_input','frt_capture','frt_capture_callback','frc_icr_r','frc_w','ocra_b_w','device_clock_changed','ftcsr_r')
 methods=[extract(source,n) for n in names]
 declarations='\n'.join(m.split('{',1)[0].replace('sh7604_device::','').strip()+';' for m in methods)
 declarations=declarations.replace('bool internal, int write_kind)', 'bool internal = false, int write_kind = 0)').replace('int write_kind)', 'int write_kind = 0)')
 with tempfile.TemporaryDirectory(prefix='sh7604-frt-') as tmp:
  cpp=Path(tmp)/'fixture.cpp';binary=Path(tmp)/'fixture'
  cpp.write_text(PREAMBLE.replace('// DECLARATIONS',declarations)+'\n'+'\n'.join(methods)+MAIN)
  subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g',str(cpp),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)
if __name__=='__main__':main()

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute production SCSP reset/IRQ/timer code with a deterministic timer queue.

Not a linked sound CPU or game boot. MUTATE_PARTIAL_SCSP_RESET=1 restores the
old reset behavior and must fail. The clock-change wiring is source-checked.
"""
from pathlib import Path
import os, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'src/devices/sound/scsp.cpp').read_text()
header = (ROOT/'src/devices/sound/scsp.h').read_text()
saturn = (ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
# SYS-CLK01: video clock change must NOT spuriously reset sound (SCSP).
# DOTSEL resets VDP2/SCU per SMPC manual, but sound CPU reset is via m_sndres line, not SCSP device reset.
dot_body = extract(saturn, 'void saturn_state::dot_select_w(')
assert 'm_scsp->reset();' not in dot_body, "DOTSEL must not reset SCSP (sound-preservation correction)"
assert 'm_scu->reset();' in dot_body, "DOTSEL must reset SCU per ST-013/ST-058"
assert 'm_vdp2->reset();' in dot_body, "DOTSEL must reset VDP2 per SMPC manual" 
functions='\n'.join(extract(source, s) for s in (
    'void scsp_device::device_reset()', 'void scsp_device::reset_irq_timers()',
    'void scsp_device::CheckPendingIRQ()', 'void scsp_device::update_main_irq()',
    'void scsp_device::MainCheckPendingIRQ(', 'void scsp_device::timer_sync(',
    'void scsp_device::timer_arm(', 'void scsp_device::timer_write(',
    'TIMER_CALLBACK_MEMBER(scsp_device::timer_cb)'))
if os.environ.get('MUTATE_PARTIAL_SCSP_RESET') == '1':
    functions=functions.replace('  reset_irq_timers();', '  m_current_level = 0;')
harness=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;using offs_t=uint32_t;
constexpr int CLEAR_LINE=0,ASSERT_LINE=1,PARITY_NONE=0,STOP_BITS_1=1,SAMPLE_CLOCKS=512;
#define TIMER_CALLBACK_MEMBER(name) void name(int param)
// One unit is one SCSP oscillator clock. No floating point rounding.
struct attotime {
 int64_t ticks=0;
 static attotime from_ticks(u64 n,unsigned){return {int64_t(n)};}
 int64_t as_ticks(unsigned)const{return ticks;}
 bool operator<=(attotime b)const{return ticks<=b.ticks;}
 attotime operator-(attotime b)const{return {ticks-b.ticks};}
 attotime &operator+=(attotime b){ticks+=b.ticks;return *this;}
};
struct emu_timer {
 attotime *now=nullptr;int64_t deadline=-1;int param=-1;
 void adjust(attotime delay,int p){assert(delay.ticks>0);deadline=now->ticks+delay.ticks;param=p;}
};
struct scsp_device {
 struct {u16 data[24]{};} m_udata;
 // TIMER
 std::array<SCSP_TIMER,3> m_timers{};
 std::array<emu_timer,3> events{};
 attotime now{1000};u32 m_current_level=0,m_MidiW=0,m_MidiR=0,m_lfsr=0;
 u16 m_mcieb=0,m_mcipd=0;
 struct {std::array<bool,8> lines{};void operator()(offs_t n,int v){assert(n<8);lines[n]=v;}} m_irq_cb;
 struct {bool asserted=false;void operator()(int v){asserted=v;}} m_main_irq_cb;
 auto &machine(){return *this;}attotime time(){return now;}unsigned clock(){return 22579200;}
 void set_data_frame(int a,int b,int c,int d){assert(a==1&&b==8&&c==PARITY_NONE&&d==STOP_BITS_1);}
 void set_rate(int r){assert(r==31250);}
 u32 SCILV0(){return m_udata.data[0x24/2];}u32 SCILV1(){return m_udata.data[0x26/2];}u32 SCILV2(){return m_udata.data[0x28/2];}
 void device_reset();void reset_irq_timers();void CheckPendingIRQ();void update_main_irq();void MainCheckPendingIRQ(u16);
 void timer_sync(int);void timer_arm(int);void timer_write(int,u16,u16);void timer_cb(int);
 scsp_device(){for(int i=0;i<3;i++){events[i].now=&now;m_timers[i].timer=&events[i];}}
 bool sound_irq(){return std::any_of(m_irq_cb.lines.begin(),m_irq_cb.lines.end(),[](bool b){return b;});}
 void run_until(int64_t target){
  for(;;){int idx=-1;int64_t when=target+1;
   for(int i=0;i<3;i++)if(events[i].deadline>=0&&events[i].deadline<when){idx=i;when=events[i].deadline;}
   if(idx<0)break;now.ticks=when;timer_cb(idx);
  }now.ticks=target;
 }
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned level=0;level<8;level++)for(unsigned phase=0;phase<3;phase++){
  scsp_device s;
  s.m_udata.data[0]=0x20f; // unrelated common controls are outside this scoped fix
  s.m_udata.data[0x1e/2]=0x80;s.m_udata.data[0x20/2]=0x5c0;
  for(unsigned bit=0;bit<3;bit++)s.m_udata.data[(0x24+bit*2)/2]=(level&(1<<bit))?0x80:0;
  s.m_mcieb=0x40;s.m_mcipd=0x5c0;s.update_main_irq();s.CheckPendingIRQ();
  assert(s.m_current_level==level&&s.m_main_irq_cb.asserted);
  for(int i=0;i<3;i++){
   auto &t=s.m_timers[i];t.counter=0xff;t.prescale=i;t.reload=0xd4;t.reload_pending=phase==1;
   t.base_time=s.now;s.events[i].deadline=s.now.ticks+1;
  }
  if(phase==2)s.now.ticks+=100;
  s.device_reset();assert(!s.sound_irq()&&!s.m_current_level&&!s.m_main_irq_cb.asserted);
  for(unsigned reg=0x18/2;reg<0x30/2;reg++)assert(s.m_udata.data[reg]==0);
  assert(!s.m_mcieb&&!s.m_mcipd&&s.m_udata.data[0]==0x20f);
  for(int i=0;i<3;i++){
   auto &t=s.m_timers[i];assert(!t.counter&&!t.prescale&&!t.reload&&!t.reload_pending);
   assert(t.base_time.ticks==s.now.ticks&&s.events[i].deadline==s.now.ticks+255*512);
  }
  // Old deadlines must not survive; new periodic requests remain masked.
  s.run_until(s.now.ticks+1);assert(!s.m_udata.data[0x20/2]);
  s.run_until(s.now.ticks+2*256*512);assert((s.m_udata.data[0x20/2]&0x1c0)==0x1c0);
  assert(!s.sound_irq()&&!s.m_main_irq_cb.asserted);
  // Model driver setup after reset: programming A5/SCILV/Timer B is now
  // possible before enabling IRQs. Enabling later must still work normally.
  s.m_udata.data[0x20/2]=0;s.m_mcipd=0;
  s.m_udata.data[0x26/2]=0x80;s.m_udata.data[0x1e/2]=0x80;s.m_mcieb=0x80;
  s.timer_write(1,0x01b4,0xffff);s.run_until(s.events[1].deadline);
  assert(s.m_current_level==2&&s.m_irq_cb.lines[2]&&s.m_main_irq_cb.asserted);
  s.device_reset();s.device_reset();assert(!s.sound_irq()&&!s.m_main_irq_cb.asserted);++cases;
 }
 std::cout<<"SCSP reset: "<<cases<<" dirty-state, deadline, IRQ delivery and re-enable cases passed\n";
}
'''.replace('// TIMER',extract(header,'struct SCSP_TIMER')+';').replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='scsp-reset-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

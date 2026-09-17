#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Extract actual SCSP scheduling and post-load functions into an exact clock queue.

All three counters, eight divisors, 256 values, pending/nonpending reload and
four sub-tick phases. Save restoration copies the registered fields and machine
time, NOT MAME's save manager. LFO/volume callbacks are stand-ins. This tests the
existing reload-on-next-tick model, not the hardware reload formula or audio.
MUTATE_SCSP_PHASE=rearm/load restores the respective old behavior and must
compile successfully, then fail a deadline assertion.
"""
from pathlib import Path
import os, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'src/devices/sound/scsp.cpp').read_text()
header = (ROOT/'src/devices/sound/scsp.h').read_text()
assert 'save_item(NAME(m_timers[i].base_time), i);' in source
saturn = (ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
assert 'm_scsp->reset();' in extract(saturn, 'void saturn_state::dot_select_w(')
functions='\n'.join(extract(source, s) for s in (
    'void scsp_device::device_reset()', 'void scsp_device::reset_irq_timers()',
    'void scsp_device::CheckPendingIRQ()', 'void scsp_device::update_main_irq()',
    'void scsp_device::MainCheckPendingIRQ(', 'void scsp_device::timer_sync(',
    'void scsp_device::timer_arm(', 'void scsp_device::timer_write(',
    'TIMER_CALLBACK_MEMBER(scsp_device::timer_cb)', 'void scsp_device::device_post_load()'))
if os.environ.get('MUTATE_SCSP_PHASE') == 'quantization':
    functions=functions.replace('  if (attotime::from_ticks((u64(steps) + 1) * inc_clocks, clock()) <= elapsed)\n    ++steps;', '')
if os.environ.get('MUTATE_SCSP_PHASE') == 'rearm':
    functions=functions.replace('t.base_time + attotime::from_ticks(', 'machine().time() + attotime::from_ticks(')
if os.environ.get('MUTATE_SCSP_PHASE') == 'load':
    functions=functions.replace('  for (int i = 0; i < 3; i++)\n    timer_arm(i);', '  for (int i = 0; i < 3; i++) {\n    m_timers[i].base_time = machine().time();\n    timer_arm(i);\n  }')

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
 attotime operator+(attotime b)const{return {ticks+b.ticks};}
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
 int m_Slots[32]{};void Compute_LFO(int*){};void update_master_volume(){};
 void device_post_load();void device_reset();void reset_irq_timers();void CheckPendingIRQ();void update_main_irq();void MainCheckPendingIRQ(u16);
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
 for(int idx=0;idx<3;idx++)for(unsigned p=0;p<8;p++)
 for(unsigned value=0;value<256;value++)for(bool reload:{false,true})
 for(unsigned fraction:{0u,1u,(512u<<p)/2,(512u<<p)-1}){
  scsp_device s;auto &t=s.m_timers[idx];
  unsigned const period=512u<<p;
  t.counter=value;t.reload=value;t.reload_pending=reload;t.prescale=p;t.base_time={1000};
  s.now.ticks=1000+fraction;
  unsigned incs=reload?256-value:((255-value)&255);if(!incs)incs=256;
  int64_t const deadline=1000+int64_t(incs)*period;
  s.timer_arm(idx);
  assert(s.events[idx].deadline==deadline);
  s.timer_write(idx,0,0);assert(s.events[idx].deadline==deadline);
  // Restoring machine time and the saved device fields must preserve phase.
  auto const saved=t;auto const saved_now=s.now;
  s.now.ticks+=100000000;t.counter=17;t.prescale=7;t.base_time=s.now;
  t=saved;s.now=saved_now;
  s.device_post_load();
  assert(s.events[idx].deadline==deadline);
  s.run_until(deadline-1);assert(!(s.m_udata.data[0x20/2]&(0x40<<idx)));
  s.run_until(deadline);assert(s.m_udata.data[0x20/2]&(0x40<<idx));
  assert(t.counter==0xff);
  assert(s.events[idx].deadline==deadline+256*int64_t(period));
  ++cases;
 }
 std::cout<<"SCSP timer phase: "<<cases<<" rearm/restore/IRQ deadline cases passed\n";
}
'''.replace('// TIMER',extract(header,'struct SCSP_TIMER')+';').replace('// FUNCTIONS',functions)
# Use MAME's real attotime conversion as well as ideal oscillator clocks.
# This catches quantization at a scheduled interrupt, which an integer-only
# test cannot detect. Only the queue/callback plumbing remains a stand-in.
core_root=Path(os.environ.get('MAME_CORE_ROOT', str(ROOT)))
for real_time in (False,True):
    code=harness
    if real_time:
        code=code.replace('attotime','test_time')
        a=code.index('struct test_time {');b=code.index('struct emu_timer',a)
        code=code[:a]+r"""struct test_time {
 int64_t ticks=0; // attoseconds, confined below 9 seconds in this test
 static test_time from_ticks(u64 n,unsigned clock){
  auto t=::attotime::from_ticks(n,clock);
  return {int64_t(t.seconds())*ATTOSECONDS_PER_SECOND+t.attoseconds()};
 }
 int64_t as_ticks(unsigned clock)const{
  return ::attotime(ticks/ATTOSECONDS_PER_SECOND,ticks%ATTOSECONDS_PER_SECOND).as_ticks(clock);
 }
 bool operator<=(test_time b)const{return ticks<=b.ticks;}
 test_time operator+(test_time b)const{return {ticks+b.ticks};}
 test_time operator-(test_time b)const{return {ticks-b.ticks};}
 test_time &operator+=(test_time b){ticks+=b.ticks;return *this;}
};
"""+code[b:]
        code='#include "emucore.h"\n#include "eminline.h"\n#include "attotime.h"\n'+code
        code=code.replace('unsigned const period=512u<<p;', 'int64_t const period=test_time::from_ticks(512u<<p,s.clock()).ticks;')
        code=code.replace('s.now.ticks=1000+fraction;', 's.now.ticks=1000+test_time::from_ticks(fraction,s.clock()).ticks;')
    with tempfile.TemporaryDirectory(prefix='scsp-phase-') as tmp:
        src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(code)
        args=[os.environ.get('CXX','g++'),'-std=c++20','-O1','-g',
              '-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',
              '-ffunction-sections','-fdata-sections','-Wl,--gc-sections']
        if real_time:
            args+=['-DMAME_NOASM']
            args+=['-I'+str(core_root/d) for d in ('src/emu','src/lib/util','src/osd')]
            args+=[str(core_root/'src/emu/attotime.cpp')]
        subprocess.run(args+[str(src),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
        print('Real MAME attotime' if real_time else 'Ideal oscillator clocks',flush=True)

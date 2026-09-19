#!/usr/bin/env python3
"""FRT count-edge compares and recurrent clear-on-A; method-level, unvalidated.

Real methods against a one-count-step oracle. Older timing fixture expectations
are intentionally not used or changed: they described arrival-at-OCR timing.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock = Path(__file__).with_name('check_sh7604_frt_stop.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('device_reset', 'void'), ('frt_reset', 'void'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'),
    ('frc_r', 'uint16_t'), ('frc_w', 'void'), ('frc_tcr_w', 'void'),
    ('ftcsr_r', 'uint8_t'), ('ftcsr_w', 'void'), ('tocr_w', 'void'), ('ocra_b_w', 'void')))
if 'void sh7604_device::frt_compare_tick(' in source:
    functions += '\n' + extract('frt_compare_tick', 'void')
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_timer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_timer_callback(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 unsigned callbacks=0;
 void advance(ticks end) {
  unsigned count=0;
  while (timer.due<=end) {
   CHECK(++count<100000); now=timer.due; timer.due=attotime::never.value;
   sh2_timer_callback(0); ++callbacks;
  }
  now=end;
 }
 void setup(unsigned cks,unsigned initial,unsigned a,unsigned b,unsigned status) {
  device_reset(); frc_tcr_w(cks); frc_w(0,initial,0xffff);
  ocra_b_w(0,a,0xffff); tocr_w(0x10); ocra_b_w(0,b,0xffff);
  m_ftcsr=status; sh2_timer_activate(); callbacks=0;
 }
 void rebind() { m_timer=&timer; }
};
struct Oracle {
 uint16_t counter,a,b; uint8_t status;
 void tick() {
  const auto old=counter; ++counter;
  if (old==a) status|=8;
  if (old==b) status|=4;
  if (old==0xffff) status|=2;
  if ((status&1) && old==a) counter=0;
 }
};
static void check(Device &d,const Oracle &o) {
 CHECK(d.frc_r(0,0xffff)==o.counter && d.m_ftcsr==o.status);
}
int main() {
 unsigned windows=0,periods=0,replays=0,acks=0,wraps=0;
 // Every 16-bit compare value, including zero and FFFF, near the edge.
 for (unsigned a=0;a<65536;++a) for (unsigned clear=0;clear<2;++clear)
 for (unsigned equal=0;equal<2;++equal) {
  now=0; Device d; const unsigned b=equal?a:(a^0xffff), initial=uint16_t(a-1);
  d.setup(0,initial,a,b,clear); Oracle o{uint16_t(initial),uint16_t(a),uint16_t(b),uint8_t(clear)};
  CHECK(d.timer.due>now); d.advance(7); check(d,o); // no asynchronous match on programming
  for (unsigned n=1;n<=4;++n) { d.advance(n*8); o.tick(); check(d,o); }
  ++windows;
 }
 // Latched OCFA does not disable periodic clearing. Compare B can be
 // before, simultaneous with, or unreachable beyond A's clear point.
 for (unsigned cks=0;cks<3;++cks) for (unsigned a=0;a<256;++a)
 for (unsigned b : {0U,a,a+1,65535U}) for (unsigned flags : {0U,8U,14U}) {
  const ticks period=1LL<<div_tab[cks], epoch=123; now=epoch; Device d;
  d.setup(cks,0,a,b,flags|1); Oracle o{0,uint16_t(a),uint16_t(b),uint8_t(flags|1)};
  for (unsigned n=1;n<=4*(a+1);++n) {
   d.advance(epoch+n*period); o.tick(); check(d,o);
  }
  CHECK(d.m_frc==0 && (d.m_ftcsr&8) && d.timer.due>now);
  Device replay=d; replay.rebind(); const auto saved_time=now;
  const auto end=now+2*(a+1)*period;
  d.advance(end); now=saved_time; replay.advance(end);
  CHECK(d.frc_r(0,0xffff)==0 && replay.frc_r(0,0xffff)==0);
  CHECK(d.m_ftcsr==replay.m_ftcsr && d.timer.due==replay.timer.due && d.irqs==replay.irqs);
  CHECK(d.callbacks==replay.callbacks); ++periods; ++replays;
 }
 // Starting above OCRA may reach B and overflow before the first clear.
 // A static OCRB>OCRA gate must not suppress those first-pass events.
 for (unsigned cks=0;cks<3;++cks) for (unsigned flags : {0U,8U,14U}) {
  now=0; Device d; d.setup(cks,0xfffd,2,0xfffe,flags|1);
  Oracle o{0xfffd,2,0xfffe,uint8_t(flags|1)}; const ticks period=1LL<<div_tab[cks];
  for (unsigned n=1;n<=12;++n) { d.advance(n*period); o.tick(); check(d,o); }
  CHECK(d.m_frc==0 && (d.m_ftcsr&0x0e)==0x0e); ++wraps;
 }
 // Equality waits for the next count edge. After acknowledgement, an old
 // equality must not immediately reassert the flag in the same CPU cycle.
 for (unsigned cks=0;cks<3;++cks) for (unsigned clear=0;clear<2;++clear)
 for (unsigned a : {0U,1U,3U,255U,65535U}) {
  now=37; Device d; const ticks period=1LL<<div_tab[cks], epoch=now;
  d.setup(cks,a,a,0xffff,6|clear); CHECK(d.timer.due==epoch+period);
  d.advance(epoch+period-1); CHECK(!(d.m_ftcsr&8));
  d.advance(epoch+period); CHECK(d.m_ftcsr&8);
  d.ftcsr_r(); d.ftcsr_w(6|clear); CHECK(!(d.m_ftcsr&8));
  const ticks cycle=clear?a+1:65536;
  CHECK(d.timer.due==now+cycle*period);
  const auto next=d.timer.due; d.advance(next-1); CHECK(!(d.m_ftcsr&8));
  d.advance(next); CHECK(d.m_ftcsr&8); ++acks;
 }
 std::printf("method-level, unvalidated: %u full-range compare-edge windows; %u repeated-clear streams; %u state-copy replays; %u first-pass wrap streams; %u acknowledgement/reassertion cases\n",windows,periods,replays,wraps,acks);
 std::puts("method-level, unvalidated: zero/FFFF targets, equal A/B, latched flags and OCRB reachability compared to a scalar count-step oracle");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-frt-compare-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

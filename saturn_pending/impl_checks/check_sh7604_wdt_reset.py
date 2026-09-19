#!/usr/bin/env python3
"""WDT RES-style reset image and timer cancellation; method-level, unvalidated.

Real device-reset/WDT methods, mocked SH2 base reset and FRT/SCI helpers.
Does not qualify internally generated watchdog resets or native CPU reset.
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
head = head.replace('struct attotime { ticks value;', 'struct attotime { ticks value; bool operator!=(const attotime &other) const { return value!=other.value; }')
head = head.replace('struct Timer {', '''struct Timer {
 attotime expire() const { return {due}; }
 attotime remaining() const { return {due-now}; }
''')
head = head.replace('struct Device : sh2_device {', '''
static constexpr int wdtclk_tab[8]={1,6,7,8,9,10,12,13};
struct Device : sh2_device {
 uint16_t m_wtcw[2]{};
 uint64_t attotime_to_cycles(attotime t) const { return t.value; }
 void frt_reset() {}
 void sh2_timer_activate() {}
''')

def extract(name, result):
    match = re.search(r'^'+result+r' sh7604_device::'+name+r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n,t) for n,t in (
    ('device_reset','void'),('wtcnt_r','uint16_t'),('rstcsr_r','uint16_t'),
    ('wtcnt_w','void'),('rstcsr_w','void'),('sh2_wtcnt_recalc','void'),('sh2_wdt_activate','void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_wdtimer_callback\)\n\{.*?^\}',source,re.M|re.S)
assert match
functions += '\nvoid sh2_wdtimer_callback(int param)\n'+match[0].split('\n',1)[1]
tail = r'''
 unsigned wdt_callbacks=0;
 void advance(ticks end) {
  unsigned count=0;
  while (wdtimer.due<=end) {
   CHECK(++count<1000); now=wdtimer.due; wdtimer.due=attotime::never.value;
   sh2_wdtimer_callback(0); ++wdt_callbacks;
  }
  now=end;
 }
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
 void initial_wdt() {
  CHECK(m_wtcnt==0 && m_wtcsr==0 && m_rstcsr==0 && m_wdt_read==0);
  CHECK((wtcnt_r(0,0xff00)>>8)==0x18 && (wtcnt_r(0,0xff)&0xff)==0);
  CHECK(rstcsr_r(0,0xff)==0x1f && wdtimer.due==attotime::never.value);
 }
};
int main() {
 unsigned resets=0,restarts=0,replays=0;
 for (unsigned mode=0;mode<2;++mode) for (unsigned cks=0;cks<8;++cks)
 for (unsigned value=0;value<256;++value) for (unsigned phase=0;phase<4;++phase) {
  const ticks period=1LL<<wdtclk_tab[cks]; now=1234; Device d;
  d.wtcnt_w(0,0xa538|(mode<<6)|cks,0xffff); d.wtcnt_w(0,0x5a00|value,0xffff);
  const auto old_deadline=d.wdtimer.due;
  CHECK(old_deadline==now+(256-value)*period);
  d.advance(now+phase*((256-value)*period-1)/3);
  d.m_rstcsr=0xe0; d.m_wdt_read=3;
  d.device_reset(); d.initial_wdt(); CHECK(d.wdt_callbacks==0);
  d.advance(old_deadline+512*period); d.initial_wdt(); CHECK(d.wdt_callbacks==0); ++resets;
  Device replay=d; replay.rebind(); const auto saved_time=now;
  auto restart=[&](Device &x) {
   x.wtcnt_w(0,0xa538|(mode<<6)|cks,0xffff); x.wtcnt_w(0,0x5afc,0xffff);
   const auto next=now+4*period; CHECK(x.wdtimer.due==next);
   x.advance(next-1); CHECK(!(x.m_wtcsr&0x80) && !(x.m_rstcsr&0x80));
   x.advance(next); CHECK(x.wdt_callbacks==1 && x.m_wtcnt==0);
   CHECK(mode?bool(x.m_rstcsr&0x80):bool(x.m_wtcsr&0x80));
   // This ends at the flag producer; WDT-generated internal reset delivery
   // remains unimplemented and is not asserted by this method probe.
   x.device_reset(); x.initial_wdt();
  };
  restart(d); now=saved_time; restart(replay);
  CHECK(d.m_wtcnt==replay.m_wtcnt && d.m_wtcsr==replay.m_wtcsr && d.m_rstcsr==replay.m_rstcsr);
  CHECK(d.wdtimer.due==replay.wdtimer.due && d.m_wdt_read==replay.m_wdt_read); ++restarts; ++replays;
 }
 std::printf("method-level, unvalidated: %u active-deadline reset cases; %u restart controls; %u state-copy replays\n",resets,restarts,replays);
 std::puts("method-level, unvalidated: documented byte-read reset values and no stale post-reset callback; native/internal-watchdog reset delivery not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

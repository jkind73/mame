#!/usr/bin/env python3
"""Active WDT writes retain the selected-clock partial period; method-level, unvalidated."""
import ast
from pathlib import Path
import subprocess
import tempfile

helper=Path(__file__).with_name('check_sh7604_wdt_reset.py')
preamble=[]
for node in ast.parse(helper.read_text()).body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tail' for t in node.targets):
        break
    preamble.append(node)
namespace={'__file__':str(helper)}
exec(compile(ast.Module(body=preamble,type_ignores=[]),str(helper),'exec'),namespace)
head,functions='#include <algorithm>\n'+namespace['head'],namespace['functions']
tail=r'''
 unsigned callbacks=0;
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
 void advance(ticks end) {
  unsigned count=0;
  while (wdtimer.due<=end) {
   CHECK(++count<1000); now=wdtimer.due; wdtimer.due=attotime::never.value;
   sh2_wdtimer_callback(0); ++callbacks;
  }
  now=end;
 }
};
int main() {
 unsigned controls=0,reloads=0,replays=0,disabled=0;
 for (unsigned mode=0;mode<2;++mode) for (unsigned cks=0;cks<8;++cks)
 for (unsigned initial : {0U,1U,127U,254U}) {
  now=0; Device d; const ticks period=1LL<<wdtclk_tab[cks];
  const unsigned control=0xa538|(mode<<6)|cks;
  d.wtcnt_w(0,control,0xffff); d.wtcnt_w(0,0x5a00|initial,0xffff);
  const auto deadline=d.wdtimer.due;
  std::vector<ticks> points{1,2,period-1,period,period+1,2*period-1,2*period,2*period+1,deadline-period-1,deadline-1};
  std::sort(points.begin(),points.end()); points.erase(std::unique(points.begin(),points.end()),points.end());
  for (ticks sample : points) {
   if (sample<=0 || sample>=deadline) continue;
   d.advance(sample); Device replay=d; replay.rebind();
   d.wtcnt_w(0,control,0xffff); replay.wtcnt_w(0,control,0xffff);
   CHECK(d.wdtimer.due==deadline && replay.wdtimer.due==deadline);
   CHECK(d.m_wtcnt==initial+sample/period && replay.m_wtcnt==d.m_wtcnt);
   CHECK(d.callbacks==0 && !(d.m_wtcsr&0x80) && !(d.m_rstcsr&0x80)); ++controls; ++replays;
  }
  d.advance(deadline); CHECK(d.callbacks==1 && (mode?bool(d.m_rstcsr&0x80):bool(d.m_wtcsr&0x80)));
 }
 for (unsigned mode=0;mode<2;++mode) for (unsigned cks=0;cks<8;++cks)
 for (unsigned value=0;value<256;++value) {
  const ticks period=1LL<<wdtclk_tab[cks];
  for (ticks phase : {ticks(0),ticks(1),period/2,period-1}) {
   now=0; Device d; const unsigned control=0xa538|(mode<<6)|cks;
   d.wtcnt_w(0,control,0xffff); d.wtcnt_w(0,0x5a00,0xffff); d.advance(phase);
   Device replay=d; replay.rebind(); const auto deadline=(256-value)*period;
   d.wtcnt_w(0,0x5a00|value,0xffff); replay.wtcnt_w(0,0x5a00|value,0xffff);
   CHECK(d.wdtimer.due==deadline && replay.wdtimer.due==deadline);
   CHECK((d.wtcnt_r(0,0xff)&0xff)==value && (replay.wtcnt_r(0,0xff)&0xff)==value);
   auto finish=[&](Device &x) {
    x.advance(deadline-1); CHECK((x.wtcnt_r(0,0xff)&0xff)==0xff && x.callbacks==0);
    x.advance(deadline); CHECK(x.callbacks==1 && x.m_wtcnt==0);
    if (mode) CHECK(x.m_rstcsr&0x80); else CHECK(x.m_wtcsr&0x80);
   };
   finish(d); now=phase; finish(replay);
   CHECK(d.wdtimer.due==replay.wdtimer.due && d.m_wtcsr==replay.m_wtcsr && d.m_rstcsr==replay.m_rstcsr);
   ++reloads; ++replays;
  }
 }
 // Stop before changing CKS, as required. A disabled timer has no deadline
 // from which to preserve phase; initial startup convention is unchanged.
 for (unsigned cks=0;cks<8;++cks) for (unsigned next=0;next<8;++next) {
  now=0; Device d; d.wtcnt_w(0,0xa538|cks,0xffff); d.wtcnt_w(0,0x5a00,0xffff);
  d.advance(1); d.wtcnt_w(0,0xa518|cks,0xffff); CHECK(d.wdtimer.due==attotime::never.value && d.m_wtcnt==0);
  d.advance(99); d.wtcnt_w(0,0xa518|next,0xffff); d.wtcnt_w(0,0xa538|next,0xffff);
  CHECK(d.wdtimer.due==now+(256LL<<wdtclk_tab[next])); ++disabled;
 }
 std::printf("method-level, unvalidated: %u active WTCSR controls; %u counter reloads; %u state-copy replays; %u stopped-clock-change controls\n",controls,reloads,replays,disabled);
 std::puts("method-level, unvalidated: same-clock writes preserve deadline phase; startup, sub-cycle conversion and native write/clock collisions not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-phase-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

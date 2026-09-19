#!/usr/bin/env python3
"""WTCNT reads at whole-phi sample points; method-level, unvalidated.

Checks count observation against the existing timer deadline, not physical
prescaler startup phase or active-write phase preservation.
"""
import ast
from pathlib import Path
import subprocess
import tempfile

helper = Path(__file__).with_name('check_sh7604_wdt_reset.py')
preamble=[]
for node in ast.parse(helper.read_text()).body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tail' for t in node.targets):
        break
    preamble.append(node)
namespace={'__file__':str(helper)}
exec(compile(ast.Module(body=preamble,type_ignores=[]),str(helper),'exec'),namespace)
head,functions='#include <algorithm>\n'+namespace['head'],namespace['functions']
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
};
int main() {
 unsigned reads=0,replays=0,phases=0;
 for (unsigned mode=0;mode<2;++mode) for (unsigned cks=0;cks<8;++cks)
 for (unsigned initial=0;initial<256;++initial) {
  now=0; Device d; const ticks period=1LL<<wdtclk_tab[cks];
  d.m_wtcsr=0x18; d.wtcnt_w(0,0xa538|(mode<<6)|cks,0xffff);
  d.wtcnt_w(0,0x5a00|initial,0xffff); const auto deadline=d.wdtimer.due;
  CHECK(deadline==(256-initial)*period);
  const unsigned last=255-initial;
  std::vector<ticks> samples;
  for (unsigned edge : {0U,last/2,last}) for (ticks phase : {ticks(0),ticks(1),period/2,period-1}) samples.push_back(edge*period+phase);
  std::sort(samples.begin(),samples.end()); samples.erase(std::unique(samples.begin(),samples.end()),samples.end());
  for (ticks sample : samples) {
   now=sample;
   Device replay=d; replay.rebind();
   const unsigned expected=initial+sample/period;
   const unsigned actual=d.wtcnt_r(0,0x00ff)&0xff;
   CHECK(actual==expected && (replay.wtcnt_r(0,0x00ff)&0xff)==expected);
   CHECK(d.m_wtcnt==replay.m_wtcnt && d.wdtimer.due==deadline && replay.wdtimer.due==deadline);
   CHECK(d.m_wtcsr==(0x38|(mode<<6)|cks) && d.m_rstcsr==0 && d.m_wdt_read==0);
   ++reads; ++replays;
  }
 }
 // Every whole-phi position in a selected-clock period, including phi/8192.
 for (unsigned cks=0;cks<8;++cks) for (unsigned initial : {0U,127U,254U,255U}) {
  now=0; Device d; const ticks period=1LL<<wdtclk_tab[cks];
  d.m_wtcsr=0x18; d.wtcnt_w(0,0xa538|cks,0xffff); d.wtcnt_w(0,0x5a00|initial,0xffff);
  const auto deadline=d.wdtimer.due;
  for (now=0;now<period;++now) {
   CHECK((d.wtcnt_r(0,0x00ff)&0xff)==initial && d.wdtimer.due==deadline); ++phases;
  }
  // The count advances on the selected edge, not phi=1 after loading.
  if (initial<255) CHECK((d.wtcnt_r(0,0x00ff)&0xff)==initial+1);
 }
 std::printf("method-level, unvalidated: %u counter samples; %u state-copy replays; %u exhaustive whole-phi period positions\n",reads,replays,phases);
 std::puts("method-level, unvalidated: reads do not shift deadlines; native sub-cycle timing, startup and active-write phase not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-count-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

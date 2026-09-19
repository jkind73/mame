#!/usr/bin/env python3
"""RSTE=0 watchdog overflow resets only WTCNT/WTCSR; method-level, unvalidated."""
import ast
from pathlib import Path
import subprocess
import tempfile

# Reuse only the reset probe's mock/extraction preamble, not its test cases.
helper = Path(__file__).with_name('check_sh7604_wdt_reset.py')
tree = ast.parse(helper.read_text())
preamble = []
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'tail' for t in node.targets):
        break
    preamble.append(node)
namespace = {'__file__': str(helper)}
exec(compile(ast.Module(body=preamble,type_ignores=[]),str(helper),'exec'),namespace)
head, functions = namespace['head'], namespace['functions']
old = 'struct sh2_device { void device_reset() {} };'
assert old in head
head = head.replace(old, 'static unsigned base_resets=0; struct sh2_device { void device_reset() { ++base_resets; } };')
head = head.replace('struct Device : sh2_device {', 'struct Device : sh2_device { unsigned irq_calls=0;')
head = head.replace('void sh2_recalc_irq() {', 'void sh2_recalc_irq() { ++irq_calls;')
tail = r'''
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
 unsigned overflows=0,replays=0,restarts=0,intervals=0;
 for (unsigned cks=0;cks<8;++cks) for (unsigned value=0;value<256;++value)
 for (unsigned rsts=0;rsts<2;++rsts) for (unsigned ovf=0;ovf<2;++ovf)
 for (unsigned wovf=0;wovf<2;++wovf) for (unsigned seen=0;seen<4;++seen) {
  now=9876; Device d; const ticks period=1LL<<wdtclk_tab[cks];
  d.m_frc=0x1234; d.m_barah=0x34; d.m_iprb=0x5555;
  d.m_wtcsr=ovf?0x80:0; d.m_rstcsr=wovf?0x80:0;
  d.rstcsr_w(0,0x5a1f|(rsts<<5),0xffff); // RSTE=0, retain RSTS
  d.wtcnt_w(0,0xa5f8|cks,0xffff); d.wtcnt_w(0,0x5a00|value,0xffff);
  if (seen&1) d.wtcnt_r(0,0xff00);
  if (seen&2) d.rstcsr_r(0,0xff);
  const auto preserved_read=d.m_wdt_read&2;
  const auto deadline=now+(256-value)*period; CHECK(d.wdtimer.due==deadline);
  const auto saved_time=now; Device replay=d; replay.rebind();
  auto run=[&](Device &x) {
   x.advance(deadline-1); CHECK((x.m_wtcsr&0x60)==0x60 && x.callbacks==0);
   const auto irq_calls=x.irq_calls;
   x.advance(deadline);
   CHECK(x.m_wtcnt==0 && x.m_wtcsr==0 && x.m_rstcsr==(0x80|(rsts<<5)));
   CHECK(x.m_wdt_read==preserved_read && x.wdtimer.due==attotime::never.value);
   CHECK(x.irq_calls==irq_calls+1 && x.callbacks==1 && base_resets==0);
   CHECK(x.m_frc==0x1234 && x.m_barah==0x34 && x.m_iprb==0x5555 && x.sci_resets==0);
   CHECK((x.wtcnt_r(0,0xff00)>>8)==0x18 && (x.wtcnt_r(0,0xff)&0xff)==0);
   CHECK(x.rstcsr_r(0,0xff)==(0x9f|(rsts<<5)));
   x.advance(deadline+512*period+512); CHECK(x.callbacks==1 && x.m_wtcnt==0 && x.m_wtcsr==0);
   // Documented new enable, after any WDTOVF pulse would have finished.
   x.rstcsr_w(0,0xa500,0xffff); CHECK(!(x.m_rstcsr&0x80));
   x.wtcnt_w(0,0xa578|cks,0xffff); x.wtcnt_w(0,0x5aff,0xffff);
   CHECK(x.wdtimer.due==now+period); x.advance(now+period);
   CHECK(x.callbacks==2 && x.m_wtcnt==0 && x.m_wtcsr==0 && (x.m_rstcsr&0x80));
  };
  run(d); now=saved_time; run(replay);
  CHECK(d.wdtimer.due==replay.wdtimer.due && d.m_rstcsr==replay.m_rstcsr && d.m_wdt_read==replay.m_wdt_read);
  ++overflows; ++replays; ++restarts;
 }
 // Interval mode does not take the watchdog-local reset branch, regardless
 // of RSTE/RSTS. Preserve interval rearming as a control, not a reset claim.
 for (unsigned cks=0;cks<8;++cks) for (unsigned rst=0;rst<4;++rst) {
  now=0; Device d; const ticks period=1LL<<wdtclk_tab[cks];
  d.rstcsr_w(0,0x5a1f|(rst<<5),0xffff); d.wtcnt_w(0,0xa538|cks,0xffff); d.wtcnt_w(0,0x5a00,0xffff);
  for (unsigned event=0;event<3;++event) {
   d.advance(now+256*period);
   CHECK(d.m_wtcsr==(0xb8|cks) && d.m_rstcsr==(rst<<5));
   CHECK(d.wdtimer.due==now+256*period && d.callbacks==event+1 && base_resets==0); ++intervals;
  }
 }
 std::printf("method-level, unvalidated: %u watchdog-local resets; %u state-copy replays; %u explicit restart cases; %u interval controls\n",overflows,replays,restarts,intervals);
 std::puts("method-level, unvalidated: RSTE=0 stops counter/control, preserves RSTCSR, consumes OVF read history and refreshes IRQ arbitration without invoking base CPU reset");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-local-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

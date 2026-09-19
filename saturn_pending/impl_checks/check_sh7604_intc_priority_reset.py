#!/usr/bin/env python3
"""IPRA/IPRB and decoded levels reset, not module-stop; method-level, unvalidated.

Real reset and priority handlers; base CPU/FRT/SCI reset helpers and IRQ
refresh remain mocks. Does not qualify native interrupt delivery or reset.
"""
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
head=namespace['head']
functions=namespace['functions']
extract=namespace['extract']
for name,result in [('ipra_r','uint16_t'),('iprb_r','uint16_t'),('ipra_w','void'),('iprb_w','void'),('fmr_sbycr_w','void')]:
    functions+='\n'+extract(name,result)
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
 void priorities(uint16_t a,uint16_t b) {
  CHECK(ipra_r()==a && iprb_r()==b);
  CHECK(m_irq_level.divu==((a>>12)&15) && m_irq_level.dmac==((a>>8)&15) && m_irq_level.wdt==((a>>4)&15));
  CHECK(m_irq_level.sci==((b>>12)&15) && m_irq_level.frc==((b>>8)&15));
 }
};
int main() {
 Device stale; stale.ipra_w(0,0xfed0,0xffff); stale.iprb_w(0,0xcb00,0xffff);
 stale.device_reset(); CHECK(stale.ipra_r()==0 && stale.iprb_r()==0); stale.priorities(0,0);
 unsigned resets=0,retentions=0,reprogrammed=0,replays=0;
 for (unsigned seed=0;seed<65536;++seed) for (unsigned mstp=0;mstp<4;++mstp) {
  now=1234; Device d;
  const uint16_t a=seed&0xfff0,b=(seed*257)&0xff00;
  d.ipra_w(0,a,0xffff); d.iprb_w(0,b,0xffff); d.priorities(a,b);
  // INTC is retained across peripheral module-stop entry/release. This is
  // not a system-standby execution or native clock-stop test.
  d.fmr_sbycr_w(0,mstp,0xff); d.priorities(a,b); ++retentions;
  d.fmr_sbycr_w(0,0,0xff); d.priorities(a,b); ++retentions;
  d.fmr_sbycr_w(0,mstp,0xff); Device replay=d; replay.rebind();
  d.device_reset(); replay.device_reset();
  d.priorities(0,0); replay.priorities(0,0); ++resets; ++replays;
  const uint16_t next_a=(~a)&0xfff0,next_b=(~b)&0xff00;
  for (Device *x : {&d,&replay}) {
   x->ipra_w(0,next_a,0xffff); x->iprb_w(0,next_b,0xffff);
   x->priorities(next_a,next_b); ++reprogrammed;
  }
 }
 std::printf("method-level, unvalidated: %u IPRA/IPRB reset images; %u module-stop retention controls; %u reprogramming controls; %u operand-state-copy replays\n",resets,retentions,reprogrammed,replays);
 std::puts("method-level, unvalidated: all five cached priorities track reset/readback; native reset routing, IRQ delivery, DMA acknowledgements and system standby not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-intc-priority-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
for field in ('m_ipra','m_iprb','m_irq_level.frc','m_irq_level.sci','m_irq_level.divu','m_irq_level.dmac','m_irq_level.wdt'):
    assert f'save_item(NAME({field}));' in namespace['source']
print('method-level, unvalidated: existing IPRA/IPRB/decoded-priority save registrations retained; no new state fields')

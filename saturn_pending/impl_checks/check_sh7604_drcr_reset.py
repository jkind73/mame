#!/usr/bin/env python3
"""DRCR0/1 reset selection and module-stop retention; method-level, unvalidated.

Actual template handlers and reset; mocked CPU/peripheral reset helpers
and IRQ refresh. Does not model DMA transfers or SCI request delivery.
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
for name,result in [('drcr_r','uint8_t'),('drcr_w','void')]:
    functions+='\ntemplate <int Channel>\n'+extract(name,result)
functions+='\n'+extract('fmr_sbycr_w','void')
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
 void selectors(unsigned a,unsigned b) { CHECK(drcr_r<0>()==a && drcr_r<1>()==b); }
};
int main() {
 Device stale; stale.drcr_w<0>(1); stale.drcr_w<1>(2); stale.device_reset();
 stale.selectors(0,0);
 unsigned resets=0,retentions=0,reprogrammed=0,replays=0;
 // Selectors 00/01/10 are defined; 11 is prohibited and not exercised.
 // Requests/channels are idle; programming a live enabled channel is
 // forbidden and is not qualified by this register-only probe.
 for (unsigned a=0;a<3;++a) for (unsigned b=0;b<3;++b)
 for (unsigned mstp=0;mstp<4;++mstp) {
  now=1234; Device d;
  for (unsigned cycle=0;cycle<4;++cycle) {
   d.drcr_w<0>(a); d.drcr_w<1>(b); d.selectors(a,b);
   d.fmr_sbycr_w(0,mstp,0xff); d.selectors(a,b); ++retentions;
   d.fmr_sbycr_w(0,0,0xff); d.selectors(a,b); ++retentions;
   d.fmr_sbycr_w(0,mstp,0xff); Device replay=d; replay.rebind();
   d.device_reset(); replay.device_reset();
   d.selectors(0,0); replay.selectors(0,0); ++resets; ++replays;
   for (Device *x : {&d,&replay}) {
    x->drcr_w<0>((a+1)%3); x->selectors((a+1)%3,0);
    x->drcr_w<1>((b+1)%3); x->selectors((a+1)%3,(b+1)%3); ++reprogrammed;
   }
  }
 }
 std::printf("method-level, unvalidated: %u paired DRCR reset images; %u module-stop retention controls; %u channel-independent reprogramming controls; %u operand-state-copy replays\n",resets,retentions,reprogrammed,replays);
 std::puts("method-level, unvalidated: DREQ/RXI/TXI selection storage only; no DMA transfer, deadline, acknowledgment, request routing, native reset/standby/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-drcr-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
assert 'save_item(STRUCT_MEMBER(m_dmac, drcr));' in namespace['source']
print('method-level, unvalidated: existing DRCR array-member save registration retained; no new state fields')

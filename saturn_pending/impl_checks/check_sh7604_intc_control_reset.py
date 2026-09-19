#!/usr/bin/env python3
"""ICR control reset and cached mode coherence; method-level, unvalidated.

Actual handlers; mocked base/peripheral resets and IRQ refresh. NMIL is
an existing readback regression control, not a native NMI pin/edge oracle.
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
head=namespace['head'].replace('struct Device : sh2_device {','struct Device : sh2_device {\n int m_nmi_line_state=0;')
functions=namespace['functions']
extract=namespace['extract']
for name,result in [('intc_icr_r','uint16_t'),('intc_icr_w','void'),('fmr_sbycr_w','void')]:
    functions+='\n'+extract(name,result)
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
 void controls(unsigned word) {
  CHECK((intc_icr_r()&0x0101)==word);
  CHECK(m_nmie==bool(word&0x100) && m_vecmd==bool(word&1));
 }
};
int main() {
 Device stale; stale.intc_icr_w(0,0x101,0xffff); stale.device_reset();
 CHECK((stale.intc_icr_r()&0x0101)==0); stale.controls(0);
 unsigned resets=0,retentions=0,reprogrammed=0,replays=0;
 for (unsigned flags=0;flags<4;++flags) for (unsigned mstp=0;mstp<4;++mstp)
 for (unsigned pin=0;pin<2;++pin) {
  now=1234; Device d; d.m_nmi_line_state=pin;
  for (unsigned cycle=0;cycle<4;++cycle) {
   const unsigned bits=(flags+cycle)&3, word=(bits&1)|((bits&2)<<7);
   d.intc_icr_w(0,word,0xffff); d.controls(word);
   const auto nmil=d.intc_icr_r()&0x8000;
   d.fmr_sbycr_w(0,mstp,0xff); d.controls(word); ++retentions;
   d.fmr_sbycr_w(0,0,0xff); d.controls(word); ++retentions;
   d.fmr_sbycr_w(0,mstp,0xff); Device replay=d; replay.rebind();
   d.device_reset(); replay.device_reset();
   for (Device *x : {&d,&replay}) {
    x->controls(0); CHECK(x->intc_icr_r()==nmil && x->m_nmi_line_state==int(pin));
    x->intc_icr_w(0,word^0x101,0xffff); x->controls(word^0x101); ++reprogrammed;
   }
   CHECK(d.intc_icr_r()==replay.intc_icr_r()); ++resets; ++replays;
  }
 }
 std::printf("method-level, unvalidated: %u ICR reset images; %u module-stop retention controls; %u reprogramming controls; %u operand-state-copy replays\n",resets,retentions,reprogrammed,replays);
 std::puts("method-level, unvalidated: both cached mode flags clear; existing NMIL readback preserved for two input states; native NMI delivery/edge selection, vector fetch, standby and save/load not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-intc-control-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
for field in ('m_intc_icr','m_nmie','m_vecmd'):
    assert f'save_item(NAME({field}));' in namespace['source']
print('method-level, unvalidated: existing ICR/mode save registrations retained; no new state fields')

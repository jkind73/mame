#!/usr/bin/env python3
"""CCR reset readback, not cache-engine behavior; method-level, unvalidated.

Actual reset/CCR/SBYCR handlers, with base CPU and unrelated peripheral
reset helpers mocked. No cache array, purge, hit/miss or timing oracle.
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
for name,result in [('ccr_r','uint8_t'),('ccr_w','void'),('fmr_sbycr_w','void')]:
    functions+='\n'+extract(name,result)
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
};
int main() {
 Device stale; stale.ccr_w(1); stale.device_reset(); CHECK(stale.ccr_r()==0);
 unsigned resets=0,retentions=0,reprogrammed=0,replays=0;
 for (unsigned value=0;value<256;++value) if (!(value&0x30))
 for (unsigned mstp=0;mstp<4;++mstp) {
  now=1234; Device d;
  for (unsigned cycle=0;cycle<4;++cycle) {
   // Configure from disabled state. This only observes control storage:
   // running a real enabled cache requires prior cache initialization.
   d.ccr_w(0); d.ccr_w(value); CHECK(d.ccr_r()==value);
   d.fmr_sbycr_w(0,mstp,0xff); CHECK(d.ccr_r()==value); ++retentions;
   d.fmr_sbycr_w(0,0,0xff); CHECK(d.ccr_r()==value); ++retentions;
   d.fmr_sbycr_w(0,mstp,0xff); Device replay=d; replay.rebind();
   d.device_reset(); replay.device_reset();
   CHECK(d.ccr_r()==0 && replay.ccr_r()==0); ++resets; ++replays;
   for (Device *x : {&d,&replay}) {
    x->ccr_w(value^0xcf); CHECK(x->ccr_r()==(value^0xcf)); ++reprogrammed;
   }
  }
 }
 std::printf("method-level, unvalidated: %u CCR reset images; %u SCI/FRT module-stop retention controls; %u reprogramming controls; %u operand-state-copy replays\n",resets,retentions,reprogrammed,replays);
 std::puts("method-level, unvalidated: CE/ID/OD/TW/W reset readback only; native reset, cache arrays/purge/timing, CPU engines, standby and save/load not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-ccr-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
assert 'save_item(NAME(m_ccr));' in namespace['source']
print('method-level, unvalidated: existing CCR save registration retained; no new state fields')

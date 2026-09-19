#!/usr/bin/env python3
"""DVCR reset image versus module-stop retention; method-level, unvalidated."""
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
head=('#define LOG(...) ((void)0)\n#define ACCESSING_BITS_0_7 (mem_mask & 0xff)\n'+namespace['head'])
functions=namespace['functions']
extract=namespace['extract']
functions+='\n'+extract('dvcr_r','uint32_t')+'\n'+extract('dvcr_w','void')+'\n'+extract('fmr_sbycr_w','void')
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
};
int main() {
 unsigned resets=0,retentions=0,replays=0;
 for (unsigned flags=0;flags<4;++flags) for (unsigned mstp=0;mstp<4;++mstp) {
  now=1234; Device d;
  for (unsigned cycle=0;cycle<4;++cycle) {
   const unsigned value=(flags+cycle)&3;
   d.dvcr_w(0,value,0xffffffff); CHECK(d.dvcr_r()==value);
   d.fmr_sbycr_w(0,mstp,0xff); CHECK(d.dvcr_r()==value); ++retentions;
   d.fmr_sbycr_w(0,0,0xff); CHECK(d.dvcr_r()==value); ++retentions;
   // Re-arm module stop to cover full reset entered in either state.
   d.fmr_sbycr_w(0,mstp,0xff); Device replay=d; replay.rebind();
   d.device_reset(); replay.device_reset();
   CHECK(d.dvcr_r()==0 && replay.dvcr_r()==0);
   CHECK(!d.m_divu_ovf && !d.m_divu_ovfie && !replay.m_divu_ovf && !replay.m_divu_ovfie);
   ++resets; ++replays;
  }
 }
 std::printf("method-level, unvalidated: %u DVCR full-reset images; %u SCI/FRT module-stop retention controls; %u operand-state-copy replays\n",resets,retentions,replays);
 std::puts("method-level, unvalidated: real device-reset/DVCR/SBYCR methods; base CPU and unrelated peripheral reset helpers mocked; native reset/standby/DIVU IRQ delivery not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-divu-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
source=namespace['source']
assert 'save_item(NAME(m_divu_ovf));' in source and 'save_item(NAME(m_divu_ovfie));' in source
print('method-level, unvalidated: existing DIVU flag save registration retained; no new state fields')

#!/usr/bin/env python3
"""VCRA-D/VCRWDT and FRT decoded vectors reset; method-level, unvalidated.

Only the five documented zero-reset INTC vector registers are covered.
DIVU/DMA vectors, native IRQ/reset/standby and save-manager behavior are not.
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
for register in ('vcra','vcrb','vcrc','vcrd','vcrwdt'):
    functions+='\n'+extract(register+'_r','uint16_t')+'\n'+extract(register+'_w','void')
functions+='\n'+extract('fmr_sbycr_w','void')
tail=r'''
 void rebind() { m_timer=&timer; m_wdtimer=&wdtimer; }
 auto vectors() {
  return std::make_tuple(vcra_r(),vcrb_r(),vcrc_r(),vcrd_r(),vcrwdt_r(),m_irq_vector.fic,m_irq_vector.foc,m_irq_vector.fov);
 }
 void program(uint16_t a,uint16_t b,uint16_t c,uint16_t d,uint16_t w) {
  vcra_w(0,a,0xffff); vcrb_w(0,b,0xffff); vcrc_w(0,c,0xffff); vcrd_w(0,d,0xffff); vcrwdt_w(0,w,0xffff);
  CHECK(vectors()==std::make_tuple(a,b,c,d,w,uint8_t(c>>8),uint8_t(c&127),uint8_t(d>>8)));
 }
 void cleared() {
  CHECK(vcra_r()==0 && vcrb_r()==0 && vcrc_r()==0 && vcrd_r()==0 && vcrwdt_r()==0);
  CHECK(m_irq_vector.fic==0 && m_irq_vector.foc==0 && m_irq_vector.fov==0);
 }
};
int main() {
 Device stale; stale.program(0x1234,0x5678,0x2233,0x4400,0x5566);
 stale.device_reset(); stale.cleared();
 unsigned resets=0,retentions=0,reprogrammed=0,replays=0;
 for (unsigned seed=0;seed<65536;++seed) for (unsigned mstp=0;mstp<4;++mstp) {
  now=1234; Device d;
  const uint16_t a=seed&0x7f7f,b=(seed^0x5555)&0x7f7f,c=(seed*257)&0x7f7f,v=(seed<<8)&0x7f00,w=(~seed)&0x7f7f;
  d.program(a,b,c,v,w); const auto before=d.vectors();
  d.fmr_sbycr_w(0,mstp,0xff); CHECK(d.vectors()==before); ++retentions;
  d.fmr_sbycr_w(0,0,0xff); CHECK(d.vectors()==before); ++retentions;
  d.fmr_sbycr_w(0,mstp,0xff); Device replay=d; replay.rebind();
  d.device_reset(); replay.device_reset();
  d.cleared(); replay.cleared(); CHECK(d.vectors()==replay.vectors()); ++resets; ++replays;
  for (Device *x : {&d,&replay}) {
   x->program(a^0x7f7f,b^0x7f7f,c^0x7f7f,v^0x7f00,w^0x7f7f); ++reprogrammed;
  }
 }
 std::printf("method-level, unvalidated: %u five-register vector reset images; %u module-stop retention controls; %u reprogramming controls; %u operand-state-copy replays\n",resets,retentions,reprogrammed,replays);
 std::puts("method-level, unvalidated: three decoded FRT vectors match reset/readback; CPU/FRT/SCI reset helpers and IRQ refresh mocked; undefined DIVU/DMA vector reset values not asserted");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-intc-vector-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
for field in ('m_vcra','m_vcrb','m_vcrc','m_vcrd','m_vcrwdt','m_irq_vector.fic','m_irq_vector.foc','m_irq_vector.fov'):
    assert f'save_item(NAME({field}));' in namespace['source']
print('method-level, unvalidated: existing vector-register/decoded-vector save registrations retained; no new state fields')

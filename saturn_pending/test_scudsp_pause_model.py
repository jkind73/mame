#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual pause/control and DMA methods with recording scheduler endpoints."""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
src=Path(os.environ.get('SCUDSP_PAUSE_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(signature):
    start=src.index(signature);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(s) for s in ('void scudsp_cpu_device::op_dma(', 'void scudsp_cpu_device::exec_dma()',
    'TIMER_CALLBACK_MEMBER(scudsp_cpu_device::dma_tick_cb)','void scudsp_cpu_device::device_reset()',
    'void scudsp_cpu_device::set_dest_dma_mem(', 'void scudsp_cpu_device::set_dest_mem_reg_2(',
    'uint32_t scudsp_cpu_device::get_mem_source_dma(', 'uint32_t scudsp_cpu_device::program_control_r()',
    'void scudsp_cpu_device::program_control_w('))
fields=re.findall(r'save_item\(NAME\((m_dma\.[a-z_]+|m_dma_state|m_paused)\)\)',src)
restore='\n'.join(f'd.{f}=s.{f};' for f in fields)
mutant=os.environ.get('SCUDSP_PAUSE_MUTANT','')
if mutant=='resume-dma': methods=methods.replace('(m_paused || m_dma.stalled)', 'm_paused')
if mutant=='dma-complete': methods=methods.replace('m_paused ? ASSERT_LINE : CLEAR_LINE', 'CLEAR_LINE')
if mutant=='command-mask': methods=methods.replace('commands = data & mem_mask;', 'commands = data;')
if mutant=='save-pause': restore=restore.replace('d.m_paused=s.m_paused;', '')
if mutant=='save-stall': restore=restore.replace('d.m_dma.stalled=s.m_dma.stalled;', '')
tree=ast.parse((ROOT/'regtests/saturn/test_scudsp_dma.py').read_text())
h=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets))
h=h[:h.index('int main(){')]
h=h.replace('T0F=23','T0F=23,EXF=16,LEF=15,EPF=25,PRF=26,VF=19,EF=18')
h=h.replace('count=0;} m_dma;', 'count=0;bool stalled=false;} m_dma;')
h=h.replace('int clock(){return 1;}', '''bool m_paused=false;int reset=0;
 struct machine_type {bool side_effects_disabled(){return false;}} machine_state;
 machine_type &machine(){return machine_state;}void m_out_irq_cb(int){}void popmessage(const char*){}
 uint32_t program_control_r();void program_control_w(offs_t,uint32_t,uint32_t);
 int clock(){return 1;}''')
h=h.replace('assert(line==INPUT_LINE_HALT);halt=state;', 'if(line==INPUT_LINE_HALT)halt=state;else {assert(line==INPUT_LINE_RESET);reset=state;}')
h=h.replace('#define INPUT_LINE_HALT 1', '''using u32=uint32_t;using offs_t=uint32_t;
#define BIT(x,b) (((x)>>(b))&1)
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define ACCESSING_BITS_0_15 (mem_mask&0xffff)
#define FLAGS_MASK 0x06ff8000
#define INPUT_LINE_RESET 2
#define INPUT_LINE_HALT 1''')
h+=r'''
int main(){
 unsigned cases=0;
 for(unsigned kind=0;kind<4;++kind)for(unsigned mode=0;mode<8;++mode)
 for(unsigned count:{1u,2u,3u,63u,64u,255u,256u})for(unsigned cut:{0u,1u,2u,3u,6u})
 for(unsigned status=0;status<4;++status){
  scudsp_cpu_device s;s.m_flags=(1u<<16)|(status<<21);s.m_ra0=0x06010000/4;s.m_wa0=0x06080000/4;
  s.op_dma(0xc0000000|(kind==0?0x1000:0)|(kind>=2?0x400:0)|(mode<<15)|(count&255));
  if(kind==3)s.set_dest_mem_reg_2(12,0x80);
  for(unsigned i=0;i<cut;++i)s.tick();
  s.program_control_w(0,0x02010000,0xffffffff);
  assert(s.m_paused&&s.halt&&!s.reset&&!(s.program_control_r()&0x10000));
  assert((s.m_flags&0x600000)==status<<21);
  s.program_control_w(0,0x04000000,0xffff); // masked-out resume cannot release pause
  assert(s.m_paused&&s.halt);
  scudsp_cpu_device restored;restore(restored,s);
  assert(restored.m_paused&&restored.m_dma.stalled==s.m_dma.stalled);
  s.writes.clear();restored.writes.clear();s.reads.clear();restored.reads.clear();
  s.finish();restored.finish();
  assert(s.halt&&restored.halt&&s.m_paused&&restored.m_paused);
  assert(s.writes==restored.writes&&s.reads==restored.reads);
  s.program_control_w(0,0x04000000,0xffffffff);
  assert(!s.m_paused&&!s.halt&&!s.reset&&(s.program_control_r()&0x10000));
  restored.program_control_w(0,0x04000000,0xffffffff);
  assert(!restored.m_paused&&!restored.halt);
  s.program_control_w(0,0x02010000,0xffffffff);s.device_reset();
  assert(!s.m_paused&&!s.m_dma.stalled&&!s.halt&&!s.m_dma.ex);
  ++cases;
 }
 // Resume while DMA is still active must retain the independent DMA stall.
 for(unsigned kind=0;kind<4;++kind){
  scudsp_cpu_device s;s.m_flags=1<<16;s.m_ra0=0x06010000/4;s.m_wa0=0x06080000/4;
  s.op_dma(0xc0010000|(kind==0?0x1000:0)|(kind>=2?0x400:0));
  if(kind==3)s.set_dest_mem_reg_2(12,0x80);
  s.program_control_w(0,0x02010000,0xffffffff);
  s.program_control_w(0,0x04000000,0xffffffff);
  assert(s.halt==(kind!=2)&&!s.m_paused&&s.m_dma.ex);
  s.finish();assert(!s.halt);
 }
 std::cout<<cases<<" actual pause/DMA/registered-replay/reset cases plus four live-resume compositions passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-pause-') as tmp:
    p=Path(tmp);(p/'test.cpp').write_text(h.replace('// METHODS',methods).replace('// RESTORE',restore))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

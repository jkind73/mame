#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual DMA methods; C-bus word placement, fractional stride and saved cursor.

Reuse the existing recording endpoint declarations, not its test oracle.
"""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
src=Path(os.environ.get('SCUDSP_CBUS_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(signature):
    start=src.index(signature);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(s) for s in ('void scudsp_cpu_device::op_dma(', 'void scudsp_cpu_device::exec_dma()',
    'TIMER_CALLBACK_MEMBER(scudsp_cpu_device::dma_tick_cb)','void scudsp_cpu_device::device_reset()',
    'void scudsp_cpu_device::set_dest_dma_mem(', 'void scudsp_cpu_device::set_dest_mem_reg_2(',
    'uint32_t scudsp_cpu_device::get_mem_source_dma('))
fields=re.findall(r'save_item\(NAME\((m_dma\.[a-z_]+|m_dma_state)\)\)',src)
restore='\n'.join(f'd.{f}=s.{f};' for f in fields)
mutant=os.environ.get('SCUDSP_CBUS_MUTANT','')
if mutant=='alignment': methods=methods.replace('(cursor & ~3U)', 'cursor')
if mutant=='stride': methods=methods.replace('m_dma.add = (1U << add) & ~1U;', 'm_dma.add = 2 * ((1U << add) & ~1U);')
if mutant=='rounding': methods=methods.replace('((m_dma.dst + 2) >> 2) - ((cursor + 2) >> 2)', '(m_dma.add >> 2)')
if mutant=='saved-phase': restore=restore.replace('d.m_dma.dst=s.m_dma.dst;', 'd.m_dma.dst=s.m_dma.dst & ~3U;')
tree=ast.parse((ROOT/'regtests/saturn/test_scudsp_dma.py').read_text())
harness=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets))
harness=harness[:harness.index('int main(){')]+r'''
int main(){
 unsigned cases=0;
 for(uint32_t base:{0x06080000u,0x060803fcu,0x060ffffcu,0x067ffffcu,0x260803fcu,0x26fffffcu})
 for(unsigned bank=0;bank<4;++bank)for(unsigned mode=0;mode<8;++mode)
 for(unsigned count:{1u,2u,3u,8u,63u,64u,65u,255u,256u})
 for(unsigned memory=0;memory<2;++memory)for(unsigned hold=0;hold<2;++hold){
  scudsp_cpu_device s;s.m_wa0=base/4;s.count_source=count&255;
  s.m_ct0=s.m_ct1=s.m_ct2=s.m_ct3=57;
  for(unsigned i=0;i<256;++i)s.ram[i]=0xa1230000|(i*0x103);
  auto op=0xc0001000|(bank<<8)|(mode<<15)|(hold<<14)|(memory?0x2000:count&255);
  s.op_dma(op);unsigned stride=mode?1u<<mode:0;
  for(unsigned cut:{0u,1u,2u,3u,6u}){
   auto a=s;a.m_dma_timer=&a.t;for(unsigned i=0;i<cut;++i)a.tick();
   scudsp_cpu_device b;restore(b,a);a.writes.clear();b.writes.clear();a.finish();b.finish();
   assert(a.writes==b.writes&&a.m_wa0==b.m_wa0&&a.m_dma.dst==b.m_dma.dst);
  }
  s.finish();assert(s.writes.size()==2*count);
  for(unsigned i=0;i<count;++i){
   uint32_t address=(base+i*stride)&~3u;
   uint32_t value=s.ram[bank*64+((57+i)&63)];
   assert(s.writes[2*i]==std::make_pair(address,uint16_t(value>>16)));
   assert(s.writes[2*i+1]==std::make_pair(address+2,uint16_t(value)));
  }
  assert(s.m_wa0==(hold?base/4:(base+count*stride+2)/4));
  assert(s.m_dma.dst==base+count*stride&&!s.halt&&!s.m_dma.ex);
  ++cases;
 }
 std::cout<<cases<<" actual C-bus write cases with five registered-state replay cuts passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-cbus-') as folder:
    p=Path(folder);(p/'test.cpp').write_text(harness.replace('// METHODS',methods).replace('// RESTORE',restore))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

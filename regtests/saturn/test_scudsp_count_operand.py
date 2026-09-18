#!/usr/bin/env python3
# license:BSD-3-Clause
"""Candidate gate: actual DMA count fetch, unused bits and MCx wrap/ordering.

Reuses only the recording endpoint declarations from the DMA harness. Unlike its
count-width cases, this compiles the actual get_source_mem_value method too.
SCUDSP_OPERAND_SOURCE can select an external candidate; production is default.
No shared-bus timing or real save-manager acceptance is inferred.
"""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = Path(os.environ.get('SCUDSP_OPERAND_SOURCE', ROOT/'src/devices/cpu/scudsp/scudsp.cpp'))
src = source.read_text()

def extract(signature):
    start = src.index(signature)
    end = src.index('{', start) + 1
    depth = 1
    while depth:
        depth += (src[end] == '{') - (src[end] == '}')
        end += 1
    return src[start:end]

module = ast.parse((ROOT/'regtests/saturn/test_scudsp_dma.py').read_text())
harness = next(ast.literal_eval(n.value) for n in module.body
               if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'harness' for t in n.targets))
harness = harness[:harness.index('int main(){')]
stub = 'uint32_t get_source_mem_value(unsigned){return count_source;}'
assert harness.count(stub) == 1
harness = harness.replace(stub, 'uint32_t get_source_mem_value(uint8_t);')
methods = '\n'.join(extract(s) for s in (
    'void scudsp_cpu_device::op_dma(', 'void scudsp_cpu_device::exec_dma()',
    'TIMER_CALLBACK_MEMBER(scudsp_cpu_device::dma_tick_cb)',
    'void scudsp_cpu_device::device_reset()',
    'void scudsp_cpu_device::set_dest_dma_mem(',
    'void scudsp_cpu_device::set_dest_mem_reg_2(',
    'uint32_t scudsp_cpu_device::get_mem_source_dma(',
    'uint32_t scudsp_cpu_device::get_source_mem_value('))
fields = re.findall(r'save_item\(NAME\((m_dma\.[a-z_]+|m_dma_state)\)\)', src)
harness = harness.replace('// METHODS', methods).replace('// RESTORE', '\n'.join(f'd.{f}=s.{f};' for f in fields))
harness += r'''
uint8_t &ct(scudsp_cpu_device &s,unsigned bank){
 switch(bank){case 0:return s.m_ct0;case 1:return s.m_ct1;case 2:return s.m_ct2;default:return s.m_ct3;}
}
int main(){
 unsigned cases=0;
 for(unsigned unused=0;unused<32;++unused)for(unsigned address=0;address<64;++address)
 for(unsigned bank=0;bank<4;++bank)for(unsigned increment=0;increment<2;++increment)
 for(unsigned direction=0;direction<2;++direction)for(unsigned hold=0;hold<2;++hold)
 for(unsigned same=0;same<2;++same){
  scudsp_cpu_device s;
  unsigned transfer_bank=same?bank:(bank+1)%4;
  ct(s,bank)=address;
  s.ram[bank*64+address]=0x12340003;
  s.m_ra0=0x06010000/4;s.m_wa0=0x05e40000/4;
  unsigned op=0xc0002000|((direction?1:2)<<15)|(hold<<14)|(direction<<12)|(transfer_bank<<8)|(unused<<3)|(increment<<2)|bank;
  s.op_dma(op);
  assert(s.m_dma.size==3);
  assert(ct(s,bank)==((address+increment)&63));
  assert(ct(s,transfer_bank)==(same?((address+increment)&63):0));
  for(unsigned cut:{0u,1u,2u,3u,4u}){
   scudsp_cpu_device a=s;a.m_dma_timer=&a.t;
   for(unsigned i=0;i<cut;++i)a.tick();
   scudsp_cpu_device b;restore(b,a);
   a.reads.clear();a.writes.clear();a.finish();b.finish();
   assert(a.ram==b.ram&&a.reads==b.reads&&a.writes==b.writes);
   for(unsigned i=0;i<4;++i)assert(ct(a,i)==ct(b,i));
  }
  s.finish();
  assert(ct(s,bank)==((address+increment+(same?3:0))&63));
  assert(ct(s,transfer_bank)==(same?((address+increment+3)&63):3));
  assert(s.reads.size()==(direction?0:6)&&s.writes.size()==(direction?6:0));
  ++cases;
 }
 assert(cases==131072);
 std::cout<<cases<<" DMA count operand/unused-bit/MC-wrap/overlap cases and five replay cuts passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-operand-') as folder:
    cpp, exe = Path(folder)/'test.cpp', Path(folder)/'test'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++20', '-O2', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

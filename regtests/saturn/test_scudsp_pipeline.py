#!/usr/bin/env python3
# license:BSD-3-Clause
"""Execute actual DSP control/fetch methods across every 8-bit PC/target pair.

Recording instruction endpoints isolate fetch ordering, not complete DSP timing.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[2])
a=p.parse_args()
src=(a.source_root/'src/devices/cpu/scudsp/scudsp.cpp').read_text()
def extract(sig):
    start=src.index(sig);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(sig) for sig in (
    'void scudsp_cpu_device::execute_run()', 'void scudsp_cpu_device::op_jump(',
    'void scudsp_cpu_device::op_loop(', 'void scudsp_cpu_device::op_move_immediate(',
    'void scudsp_cpu_device::set_dest_mem_reg_2(',
    'uint32_t scudsp_cpu_device::compute_condition(', 'void scudsp_cpu_device::device_reset()'))
fields=re.findall(r'save_item\(NAME\((m_pc|m_flags|m_delay|m_delay_pending|m_top|m_lop)\)\)',src)
restore='\n'.join(f'd.{f}=s.{f};' for f in fields)
mutation=os.environ.get('MUTATE_DSP_PIPELINE','')
if mutation=='zero-sentinel':methods=methods.replace('if ( m_delay_pending )','if ( m_delay )')
if mutation=='missing-save':restore=restore.replace('d.m_delay_pending=s.m_delay_pending;','')
if mutation=='missing-reset':
    at=methods.index('void scudsp_cpu_device::device_reset()')
    methods=methods[:at]+methods[at:].replace('m_delay_pending = false;','')
harness=r'''
#include <array>
#include <vector>
#include <cstdint>
#include <cassert>
#include <iostream>
#define BIT(v,b) (((v)>>(b))&1)
#define scudsp_readop(a) readop(a)
#define INPUT_LINE_HALT 1
#define CLEAR_LINE 0
#define ASSERT_LINE 1
namespace util {int32_t sext(uint32_t v,unsigned bits){uint32_t sign=1u<<(bits-1);return int32_t((v&((1u<<bits)-1))^sign)-int32_t(sign);}}
struct attotime {static constexpr int never=-1;};
struct timer {void adjust(int){}};
struct scudsp_cpu_device {
 enum {CF=20,SF=22,ZF=21,T0F=23,DMA_STATE_IDLE=0};
 uint8_t m_pc=0,m_delay=0,m_top=0,m_update_mul=0,m_dma_state=0;
 bool m_delay_pending=false;uint16_t m_lop=0;uint32_t m_flags=0;
 int m_icount=0;int64_t m_mul=0;struct{int32_t si=0;}m_rx,m_ry;
 struct{unsigned ex=0,count=0,dir=0,dst=0;}m_dma;
 timer t;timer *m_dma_timer=&t;
 std::array<uint32_t,256> code{};std::vector<unsigned> fetch;
 uint32_t readop(uint8_t a){fetch.push_back(a);return code[a];}
 void debugger_instruction_hook(uint8_t){}
 void set_dest_mem_reg(uint32_t,uint32_t){assert(false);}
 void op_alu(uint32_t){--m_icount;}
 void op_illegal(uint32_t){assert(false);}void op_dma(uint32_t){assert(false);}
 void op_end(uint32_t){--m_icount;}
 void m_out_ddwt_cb(int){}void m_out_ddmv_cb(int){}void set_input_line(int,int){}
 void execute_run();void op_jump(uint32_t);void op_loop(uint32_t);
 void op_move_immediate(uint32_t);void set_dest_mem_reg_2(uint32_t,uint32_t);
 uint32_t compute_condition(uint32_t);void device_reset();
 void step(){m_icount=1;execute_run();}
};
// METHODS
void restore(scudsp_cpu_device &d,scudsp_cpu_device const&s){
 // RESTORE
}
int main(){
 uint64_t cases=0;
 for(unsigned pc=0;pc<256;++pc)for(unsigned target=0;target<256;++target)
 for(unsigned kind=0;kind<6;++kind){
  scudsp_cpu_device s;s.m_pc=pc;s.m_top=target;s.m_lop=2;
  uint32_t op=0;bool taken=true;unsigned destination=target;
  switch(kind){
   case 0:op=0xd0000000|target;break; // JMP
   case 1:op=0xd0000000|(0x21<<19)|target;s.m_flags=1<<s.ZF;break;
   case 2:op=0xd0000000|(0x21<<19)|target;taken=false;break;
   case 3:op=0xb0000000|target;break; // MVI immediate,PC
   case 4:op=0xe0000000;break; // BTM
   case 5:op=0xe8000000;destination=pc;break; // LPS
  }
  s.code[pc]=op;s.step();
  unsigned next=(pc+1)&255;
  // Save at the control-instruction boundary, poison pending-state validity,
  // and restore ONLY the fields actually registered by the implementation.
  scudsp_cpu_device replay=s;replay.m_dma_timer=&replay.t;
  replay.m_delay_pending=false;replay.m_delay=117;restore(replay,s);
  s.step();replay.step();
  assert(s.fetch.back()==next&&replay.fetch==s.fetch);
  assert(s.m_pc==(taken?destination:((pc+2)&255)));
  // Consume the slot exactly once. Avoid a branch in the slot in this test.
  s.code[next]=0;replay.code[next]=0;
  s.step();replay.step();
  assert(s.fetch.back()==(taken?destination:((pc+2)&255)));
  assert(replay.fetch==s.fetch);
  ++cases;
 }
 scudsp_cpu_device reset;reset.m_delay_pending=true;reset.m_delay=0;
 reset.device_reset();assert(!reset.m_delay_pending);
 std::cout<<cases<<" DSP PC/target/control-flow wrap and registered-state replay cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='dsp-pipeline-') as tmp:
    d=Path(tmp);cpp=d/'test.cpp';exe=d/'test'
    cpp.write_text(harness.replace('// METHODS',methods).replace('// RESTORE',restore))
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O1','-g','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

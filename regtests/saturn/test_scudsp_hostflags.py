#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual control-port write method: masked flags, stopped PC loads and pending-slot invalidation."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
src=Path(os.environ.get('SCUDSP_HOSTFLAGS_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
start=src.index('void scudsp_cpu_device::program_control_w(')
end=src.index('void scudsp_cpu_device::program_w(',start)
method=src[start:end]
mutant=os.environ.get('SCUDSP_HOSTFLAGS_MUTANT','')
if mutant=='active-load': method=method.replace('BIT(commands, LEF) && stopped_on_entry', 'BIT(commands, LEF)')
if mutant=='late-state': method=method.replace('BIT(commands, LEF) && stopped_on_entry', 'BIT(commands, LEF) && (!BIT(m_flags, EXF) || m_paused)')
if mutant=='load-mask': method=method.replace('BIT(commands, LEF)', 'BIT(data, LEF)')
if mutant=='old-slot': method=method.replace('m_delay_pending = false;', '')
cpp=r'''
#include <cstdint>
#include <cassert>
#include <iostream>
using offs_t=uint32_t;
#define BIT(x,b) (((x)>>(b))&1)
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define ACCESSING_BITS_0_15 (mem_mask&0xffff)
#define INPUT_LINE_RESET 1
#define INPUT_LINE_HALT 2
#define ASSERT_LINE 1
#define CLEAR_LINE 0
#define SUSPEND_REASON_HALT 1
struct scudsp_cpu_device {
 enum {EXF=16,ESF=17,LEF=15,EPF=25,PRF=26};
 uint32_t m_flags=0;uint8_t m_pc=0;int reset=0,halt=0;bool m_paused=false,m_delay_pending=false,m_step_pending=false,m_lps_active=false;uint8_t m_delay=0;struct{bool stalled=false;}m_dma;
 unsigned m_suspend_mask=0;
 void suspend(unsigned reason,bool){m_suspend_mask|=reason;}
 void resume(unsigned reason){m_suspend_mask&=~reason;}
 void update_execution_state();
 void set_input_line(int line,int value){if(line==INPUT_LINE_RESET)reset=value;else {assert(line==INPUT_LINE_HALT);halt=value;}}
 void popmessage(const char*){}
 void program_control_w(offs_t,uint32_t,uint32_t);
};
// METHOD
int main(){
 unsigned cases=0;uint32_t random=0x19283746;
 for(unsigned flags=0;flags<256;++flags)
 for(uint32_t mask:{0xffffffffu,0xffff0000u,0x0000ffffu,0xff000000u,0x00ff0000u,0x0000ff00u,0x000000ffu,0u})
 for(unsigned pattern=0;pattern<16;++pattern)
 for(unsigned paused=0;paused<2;++paused)for(unsigned pending=0;pending<2;++pending)
 for(unsigned stalled=0;stalled<2;++stalled){
  random=random*1664525u+1013904223u;
  uint32_t value=pattern==0?0:pattern==1?0xffffffffu:random;
  scudsp_cpu_device s;s.m_flags=flags<<16;s.m_pc=flags;
  s.m_paused=paused;s.m_delay_pending=pending;s.m_dma.stalled=stalled;
  // Only EX (bit 16) is R/W in the flag byte; ES (bit 17) is a (W) strobe.
  // EP/PR writes suppress the EX latch update entirely.
  uint32_t writable=(value&mask&0x06000000)?0:mask&0x00010000;
  uint32_t expected=(s.m_flags&~writable)|(value&writable);
  bool const load=(!(flags&1)||paused)&&(value&mask&0x8000);
  unsigned pc=load?((flags&~mask)|(value&mask))&255:flags;
  bool pause=paused;
  if(flags&1){if(value&mask&0x02000000)pause=true;else if(value&mask&0x04000000)pause=false;}
  s.program_control_w(0,value,mask);
  assert(s.m_pc==pc);assert(s.m_delay_pending==(load?false:bool(pending)));
  assert(s.m_flags==expected);
  assert(s.m_paused==pause);
  // ST-097 pp.51-52: the DSP runs only while EX is latched on, it is not
  // paused, and no DMA is stalling it; a pending ES step allows one stage.
  bool const stopped=pause||stalled||(!BIT(expected,16)&&!s.m_step_pending);
  assert(s.m_suspend_mask==(stopped?SUSPEND_REASON_HALT:0u));++cases;
 }
 std::cout<<cases<<" actual masked flag/PC/pending-slot/entry-state cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-hostflags-') as tmp:
    p=Path(tmp);(p/'test.cpp').write_text(cpp.replace('// METHOD',method))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

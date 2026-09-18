#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual control-port write method: masked read-only flag preservation only."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
src=Path(os.environ.get('SCUDSP_HOSTFLAGS_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
start=src.index('void scudsp_cpu_device::program_control_w(')
end=src.index('void scudsp_cpu_device::program_w(',start)
method=src[start:end]
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
struct scudsp_cpu_device {
 enum {EXF=16,LEF=15,EPF=25,PRF=26};
 uint32_t m_flags=0;uint8_t m_pc=0;int reset=0,halt=0;bool m_paused=false;struct{bool stalled=false;}m_dma;
 void set_input_line(int line,int value){if(line==INPUT_LINE_RESET)reset=value;else {assert(line==INPUT_LINE_HALT);halt=value;}}
 void popmessage(const char*){}
 void program_control_w(offs_t,uint32_t,uint32_t);
};
// METHOD
int main(){
 unsigned cases=0;uint32_t random=0x19283746;
 for(unsigned flags=0;flags<256;++flags)
 for(uint32_t mask:{0xffffffffu,0xffff0000u,0x0000ffffu,0xff000000u,0x00ff0000u,0x0000ff00u,0x000000ffu})
 for(unsigned pattern=0;pattern<16;++pattern){
  random=random*1664525u+1013904223u;
  uint32_t value=pattern==0?0:pattern==1?0xffffffffu:random;
  scudsp_cpu_device s;s.m_flags=flags<<16;s.m_pc=flags;
  uint32_t writable=(value&mask&0x06000000)?0:mask&0x00030000;
  uint32_t expected=(s.m_flags&~writable)|(value&writable);
  s.program_control_w(0,value,mask);
  assert(s.m_flags==expected);assert(s.reset==!BIT(expected,16));
  assert(s.m_paused==bool((flags&1)&&(value&mask&0x02000000)));
  assert(s.halt==s.m_paused);++cases;
 }
 std::cout<<cases<<" actual masked control-port read-only flag cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-hostflags-') as tmp:
    p=Path(tmp);(p/'test.cpp').write_text(cpp.replace('// METHOD',method))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

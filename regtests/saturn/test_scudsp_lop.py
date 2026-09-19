#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual bus/MVI/loop methods:12-bit LOP writes and complete countdowns.

Isolated memory and non-exercised instruction stubs; not native device timing.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
src=Path(os.environ.get('SCUDSP_LOP_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(sig):
    start=src.index(sig);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(sig) for sig in (
    'void scudsp_cpu_device::execute_run()', 'void scudsp_cpu_device::op_loop(', 'void scudsp_cpu_device::op_alu(',
    'void scudsp_cpu_device::op_move_immediate(', 'void scudsp_cpu_device::set_dest_mem_reg(',
    'void scudsp_cpu_device::set_dest_mem_reg_2(', 'uint32_t scudsp_cpu_device::compute_condition(',
    'uint32_t scudsp_cpu_device::get_source_mem_value(', 'uint32_t scudsp_cpu_device::get_source_mem_reg_value('))
macros='\n'.join(re.findall(r'^#define SET_[CSZV]\b.*$',src,re.M))
cpp=r'''
#include <array>
#include <bit>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
using u16=uint16_t;using u32=uint32_t;using s64=int64_t;
union R32{uint32_t ui=0;int32_t si;};union R16{uint16_t ui=0;int16_t si;};
constexpr uint64_t concat_64(uint32_t hi,uint32_t lo){return (uint64_t(hi)<<32)|lo;}
#define BIT(v,b) (((v)>>(b))&1)
#define scudsp_readop(a) code.at(a)
#define scudsp_readmem(a,b) ram.at((b)*64+(a))
#define scudsp_writemem(a,b,v) (ram.at((b)*64+(a))=(v))
#define INPUT_LINE_HALT 1
#define ASSERT_LINE 1
namespace util {int32_t sext(uint32_t v,unsigned bits){uint32_t sign=1u<<(bits-1);return int32_t((v&((1u<<bits)-1))^sign)-int32_t(sign);}}
// MACROS
struct scudsp_cpu_device {
 enum {CF=20,SF=22,ZF=21,T0F=23};
 R32 m_acl,m_pl,m_rx,m_ry;R16 m_ach,m_ph;
 int64_t m_alu=0,m_mul=0;uint32_t m_flags=0,m_ra0=0,m_wa0=0;
 uint8_t m_ct0=0,m_ct1=0,m_ct2=0,m_ct3=0,m_pc=0,m_delay=0,m_top=0;
 uint16_t m_lop=0;bool m_delay_pending=false;uint32_t m_delay_opcode=0;
 int m_update_mul=0,m_icount=0;
 struct{unsigned ex=0,dir=0,dst=0;bool stalled=false;}m_dma;
 std::array<uint32_t,256> code{},ram{};
 void debugger_instruction_hook(uint8_t){}
 void set_input_line(int,int){assert(false);}
 void op_illegal(uint32_t){assert(false);}void op_dma(uint32_t){assert(false);}
 void op_jump(uint32_t){assert(false);}void op_loop(uint32_t);
 void op_end(uint32_t){assert(false);}
 void execute_run();void op_alu(uint32_t);void op_move_immediate(uint32_t);
 void set_dest_mem_reg(uint32_t,uint32_t);void set_dest_mem_reg_2(uint32_t,uint32_t);
 uint32_t compute_condition(uint32_t);uint32_t get_source_mem_value(uint8_t);
 uint32_t get_source_mem_reg_value(uint32_t);
};
// METHODS
int64_t signed_value(uint32_t v,unsigned bits){uint64_t n=v&((1ull<<bits)-1);return n&(1ull<<(bits-1))?int64_t(n)-int64_t(1ull<<bits):int64_t(n);}
void check_write(unsigned mode,uint32_t value){
 scudsp_cpu_device d;d.ram[0]=value;d.m_lop=3;d.m_flags=mode==4?0:1u<<d.ZF;
 uint16_t expected=value&0xfff;
 if(mode==0)d.op_alu(0x3a00);
 else if(mode==1){d.op_alu(0x1a00|(value&255));expected=uint32_t(signed_value(value,8))&0xfff;}
 else if(mode==2)d.op_move_immediate(0xa8000000|(value&0x1ffffff));
 else{d.op_move_immediate(0xab080000|(value&0x7ffff));if(mode==4)expected=3;}
 assert(d.m_lop==expected);assert(d.m_ct0==0&&d.m_ct2==0);
}
void check_loop(unsigned initial,bool lps){
 scudsp_cpu_device d;d.m_lop=initial;d.m_top=23;
 for(unsigned left=initial;;--left){
  d.m_pc=100;d.m_delay_pending=false;d.m_icount=1;d.op_loop(lps?0xe8000000:0xe0000000);
  assert(d.m_icount==0);
  if(left){assert(d.m_lop==left-1&&d.m_delay_pending&&d.m_delay==100&&d.m_pc==(lps?99:23));}
  else{assert(d.m_lop==0&&!d.m_delay_pending&&d.m_pc==100);break;}
 }
}
int main(){
 unsigned cases=0;
 for(unsigned value=0;value<65536;++value)for(uint32_t high:{0u,0x12340000u,0xffff0000u})
 for(unsigned mode=0;mode<5;++mode){check_write(mode,value|high);++cases;}
 for(unsigned value=0;value<4096;++value)for(bool lps:{false,true}){check_loop(value,lps);++cases;}
 std::cout<<cases<<" actual LOP write/width/conditional and full-count BTM/LPS cases passed under UBSan\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-lop-') as folder:
    source=Path(folder)/'test.cpp';exe=Path(folder)/'test'
    source.write_text(cpp.replace('// MACROS',macros).replace('// METHODS',methods))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

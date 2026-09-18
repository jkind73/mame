#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual fetch/ALU/MVI/bus methods: RX write paths and old/new product ordering.

Isolated memory and non-exercised instruction stubs; not native device timing.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
src=Path(os.environ.get('SCUDSP_MULTIPLIER_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(sig):
    start=src.index(sig);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(sig) for sig in (
    'void scudsp_cpu_device::execute_run()', 'void scudsp_cpu_device::op_alu(',
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
 uint16_t m_lop=0;bool m_delay_pending=false;
 int m_update_mul=0,m_icount=0;
 struct{unsigned ex=0,dir=0,dst=0;bool stalled=false;}m_dma;
 std::array<uint32_t,256> code{},ram{};
 void debugger_instruction_hook(uint8_t){}
 void set_input_line(int,int){assert(false);}
 void op_illegal(uint32_t){assert(false);}void op_dma(uint32_t){assert(false);}
 void op_jump(uint32_t){assert(false);}void op_loop(uint32_t){assert(false);}
 void op_end(uint32_t){assert(false);}
 void execute_run();void op_alu(uint32_t);void op_move_immediate(uint32_t);
 void set_dest_mem_reg(uint32_t,uint32_t);void set_dest_mem_reg_2(uint32_t,uint32_t);
 uint32_t compute_condition(uint32_t);uint32_t get_source_mem_value(uint8_t);
 uint32_t get_source_mem_reg_value(uint32_t);
};
// METHODS
int64_t signed_value(uint32_t v,unsigned bits){uint64_t n=v&((1ull<<bits)-1);return n&(1ull<<(bits-1))?int64_t(n)-int64_t(1ull<<bits):int64_t(n);}
void check(unsigned mode,uint32_t a,uint32_t b){
 scudsp_cpu_device d;d.ram[0]=a;d.ram[64]=7;d.ram[192]=b;
 uint32_t op=0x2000000;int64_t rx=signed_value(a,32);
 switch(mode){
 case 1:op=0x3400;break;
 case 2:op=0x1400|(a&255);rx=signed_value(a,8);break;
 case 3:op=0x90000000|(a&0x1ffffff);rx=signed_value(a,25);break;
 case 4:case 5:op=0x93080000|(a&0x7ffff);rx=mode==5?7:signed_value(a,19);break;
 case 6:op=0x2103400;break;
 case 7:op=0x1003400;break;
 }
 std::vector<uint32_t> code={0x1c00,0x1d00,0x1e00,0x1f00,0x2100000,0x8c000,0,
  0x20000,mode==5?0x1501u:0x1500u,3u<<26,0x1000000,op,
  (6u<<26)|0x40000,0x3209,0x320a,0x20000,0x1000000,(6u<<26)|0x40000,0x3209,0x320a};
 for(unsigned i=0;i<code.size();++i)d.code[i]=code[i];
 for(unsigned i=0;i<code.size();++i){d.m_icount=1;d.execute_run();assert(d.m_icount==0);}
 unsigned address=128;
 for(int64_t product:{7*signed_value(b,32),rx*signed_value(b,32)}){
  auto expected=uint64_t(product)&0xffffffffffffull;
  assert(d.ram[address++]==uint32_t(expected));
  assert(d.ram[address++]==uint32_t(expected>>16));
 }
 assert(d.m_rx.si==rx&&d.m_mul==rx*signed_value(b,32));
 assert(d.m_ct0==0&&d.m_ct1==0&&d.m_ct2==4&&d.m_ct3==0);
}
int main(){
 unsigned cases=0;
 uint32_t values[]={0,1,2,7,127,128,255,0x3ffff,0x40000,0xffffff,0x1000000,
  0x7fffffff,0x80000000,0xffffffff,0x12345678,0x87654321};
 for(unsigned mode=0;mode<8;++mode){
  for(auto a:values)for(auto b:values){check(mode,a,b);++cases;}
  uint32_t random=0xcafebeef;
  for(unsigned i=0;i<4096;++i){random=random*1664525u+1013904223u;auto a=random;
   random=random*1664525u+1013904223u;check(mode,a,random);++cases;}
 }
 std::cout<<cases<<" actual fetch/ALU/MVI/RX product and ordering cases passed under UBSan\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-mul-') as folder:
    source=Path(folder)/'test.cpp';exe=Path(folder)/'test'
    source.write_text(cpp.replace('// MACROS',macros).replace('// METHODS',methods))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

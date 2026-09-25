#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual ALU/bus methods: simultaneous reads, writes and counter commit.

Isolated memory and non-exercised instruction stubs; not native device timing.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
src=Path(os.environ.get('SCUDSP_PARALLEL_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(sig):
    start=src.index(sig);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(sig) for sig in (
    'void scudsp_cpu_device::execute_run()', 'void scudsp_cpu_device::op_alu(',
    'void scudsp_cpu_device::op_move_immediate(', 'void scudsp_cpu_device::set_dest_mem_reg(',
    'void scudsp_cpu_device::set_dest_mem_reg_2(', 'uint32_t scudsp_cpu_device::compute_condition(',
    'uint32_t scudsp_cpu_device::get_source_mem_value(', 'uint32_t scudsp_cpu_device::get_source_mem_reg_value(',
    'void scudsp_cpu_device::update_execution_state()'))
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
#define SUSPEND_REASON_HALT 1
#define ASSERT_LINE 1
namespace util {int32_t sext(uint32_t v,unsigned bits){uint32_t sign=1u<<(bits-1);return int32_t((v&((1u<<bits)-1))^sign)-int32_t(sign);}}
// MACROS
struct scudsp_cpu_device {
 enum {LEF=15,EXF=16,ESF=17,CF=20,ZF=21,SF=22,T0F=23};
 R32 m_acl,m_pl,m_rx,m_ry;R16 m_ach,m_ph;
 int64_t m_alu=0,m_mul=0;uint32_t m_flags=0,m_ra0=0,m_wa0=0;
 uint8_t m_ct0=0,m_ct1=0,m_ct2=0,m_ct3=0,m_pc=0,m_delay=0,m_top=0;
 uint16_t m_lop=0;bool m_lps_active=false;bool m_delay_pending=false;uint32_t m_delay_opcode=0;
 int m_update_mul=0,m_icount=0;
 bool m_paused=false,m_step_pending=false;
 unsigned suspend_calls=0,resume_calls=0;
 struct{unsigned ex=0,dir=0,dst=0;bool stalled=false;}m_dma;
 std::array<uint32_t,256> code{},ram{};
 void debugger_instruction_hook(uint8_t){}
 void suspend(int,bool){++suspend_calls;}
 void resume(int){++resume_calls;}
 void update_execution_state();
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
uint32_t word(unsigned bank,unsigned address){return 0x51000000u|(bank<<16)|(address<<8)|(address^bank);}
void check(unsigned xs,unsigned ys,unsigned ds,unsigned dest,unsigned ct,bool immediate,unsigned xm,unsigned ym){
 scudsp_cpu_device d;
 uint8_t *c[]={&d.m_ct0,&d.m_ct1,&d.m_ct2,&d.m_ct3};
 std::array<uint32_t,256> expected;
 for(unsigned bank=0;bank<4;++bank){*c[bank]=(ct+bank*7)&63;for(unsigned i=0;i<64;++i)d.ram[bank*64+i]=word(bank,i);}
 expected=d.ram;
 unsigned initial[4];bool inc[4]={};bool read[4]={};
 for(unsigned bank=0;bank<4;++bank)initial[bank]=*c[bank];
 // xs/ys=8 means idle. All source values are from the instruction-entry image.
 uint32_t opcode=0;
 if(xs<8){opcode|=(xm<<23)|(xs<<20);read[xs%4]=true;inc[xs%4]=xs>=4;}
 if(ys<8){opcode|=(ym<<17)|(ys<<14);read[ys%4]=true;inc[ys%4]|=ys>=4;}
 uint32_t value=uint32_t(int32_t(int8_t(ds==9?0xc5:ds)));
 if(!immediate){
  opcode|=0x3000|ds;
  if(ds<8){read[ds%4]=true;value=word(ds%4,initial[ds%4]);if(ds>=4&&dest!=ds%4)inc[ds%4]=true;}
  else value=ds==9?0x89abcdefu:0x456789abu;
 }else opcode|=0x1000|(ds==9?0xc5:ds);
 opcode|=dest<<8;
 d.m_acl.ui=0x89abcdef;d.m_ach.ui=0x4567;d.m_alu=0xdeadbeef1234;
 // Bank reads suppress D1 writes to that bank; other transfers use old CT.
 if(dest<4){if(!read[dest]){expected[dest*64+initial[dest]]=value;inc[dest]=true;}}
 unsigned final[4];for(unsigned bank=0;bank<4;++bank)final[bank]=(initial[bank]+inc[bank])&63;
 if(dest>=12){final[dest-12]=value&63;}
 d.op_alu(opcode);
 assert(d.ram==expected);
 for(unsigned bank=0;bank<4;++bank)assert(*c[bank]==final[bank]);
 uint32_t rx=xs<8&&xm>=4?word(xs%4,initial[xs%4]):0;
 if(dest==4)rx=value; // retained MAME/Beetle priority, not a resolved hardware oracle
 assert(d.m_rx.ui==rx);
 assert(d.m_ry.ui==(ys<8&&ym>=4?word(ys%4,initial[ys%4]):0));
 uint32_t pl=xs<8&&(xm&3)==3?word(xs%4,initial[xs%4]):0;
 if(dest==5)pl=value;
 assert(d.m_pl.ui==pl&&d.m_ph.ui==((pl>>31)?0xffff:0));
 assert(d.m_acl.ui==(ys<8&&(ym&3)==3?word(ys%4,initial[ys%4]):0x89abcdef));
 assert(d.m_ach.ui==(ys<8&&(ym&3)==3?0:0x4567));
 assert(d.m_icount==-1);
}
int main(){
 unsigned cases=0;
 for(unsigned ct:{0u,1u,31u,56u,63u})
 for(unsigned xs=0;xs<=8;++xs)for(unsigned ys=0;ys<=8;++ys)
 for(unsigned ds:{0u,1u,2u,3u,4u,5u,6u,7u,9u,10u})
 for(unsigned dest:{0u,1u,2u,3u,4u,5u,12u,13u,14u,15u})
 for(bool imm:{false,true})for(unsigned xm:{3u,4u,7u})for(unsigned ym:{3u,4u,7u})
 {check(xs,ys,ds,dest,ct,imm,xm,ym);++cases;}
 std::cout<<cases<<" actual parallel-bus memory/register/counter transitions passed under UBSan\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-parallel-') as folder:
    source=Path(folder)/'test.cpp';exe=Path(folder)/'test'
    source.write_text(cpp.replace('// MACROS',macros).replace('// METHODS',methods))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

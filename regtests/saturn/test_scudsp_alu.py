#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual DSP ALU and host flag-read methods, mathematical oracle and UBSan.

Bus fields are zero; stubs assert if the ALU-only programs access another bus.
Not native device, save-manager, prefetch or commercial-software acceptance.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
src = Path(os.environ.get('SCUDSP_ALU_SOURCE', ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(signature):
    start=src.index(signature);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
macros='\n'.join(re.findall(r'^#define (?:SET_[CSZV]\b|FLAGS_MASK\b).*$',src,re.M))
methods='\n'.join(extract(s) for s in ['void scudsp_cpu_device::op_alu(', 'uint32_t scudsp_cpu_device::program_control_r()'])
cpp=r'''
#include <bit>
#include <cassert>
#include <cstdint>
#include <iostream>
using u16=uint16_t;using u32=uint32_t;using s64=int64_t;
union R32{uint32_t ui=0;int32_t si;};union R16{uint16_t ui=0;int16_t si;};
constexpr uint64_t concat_64(uint32_t hi,uint32_t lo){return (uint64_t(hi)<<32)|lo;}
#define scudsp_writemem(a,b,v) assert(false)
// MACROS
struct scudsp_cpu_device {
 enum{VF=19,EF=18,EXF=16};
 R32 m_acl,m_pl,m_rx,m_ry;R16 m_ach,m_ph;
 int64_t m_alu=0,m_mul=0;uint32_t m_flags=0;bool m_paused=false;
 uint8_t m_ct0=0,m_ct1=0,m_ct2=0,m_ct3=0,m_pc=0;
 int m_update_mul=0,m_icount=0,irq=1;
 struct Machine {bool disabled=false;bool side_effects_disabled(){return disabled;}} mach;
 Machine &machine(){return mach;}void m_out_irq_cb(int n){irq=n;}
 uint32_t get_source_mem_value(int){assert(false);return 0;}
 uint32_t get_source_mem_reg_value(int){assert(false);return 0;}
 void set_dest_mem_reg(int,uint32_t){assert(false);}
 void op_alu(uint32_t);uint32_t program_control_r();
};
// METHODS
constexpr uint32_t V=1u<<19,C=1u<<20,Z=1u<<21,S=1u<<22;
constexpr uint64_t mask48=(1ull<<48)-1;
int64_t signed_value(uint64_t value,unsigned bits){
 return value&(1ull<<(bits-1))?int64_t(value)-int64_t(1ull<<bits):int64_t(value);
}
void check(unsigned op,uint64_t a,uint64_t b,bool prior_v){
 unsigned bits=op==6?48:32;uint64_t mask=(1ull<<bits)-1;
 a&=mask;b&=mask;
 scudsp_cpu_device d;
 d.m_acl.ui=uint32_t(a);d.m_ach.ui=uint16_t(a>>32);
 d.m_pl.ui=uint32_t(b);d.m_ph.ui=uint16_t(b>>32);
 d.m_alu=0xa55a12345678;d.m_flags=0x10812345|(prior_v?V:0);
 uint32_t original=d.m_flags;
 uint64_t result;bool carry,overflow=false;
 if(op<=3){result=op==1?a&b:op==2?a|b:a^b;carry=false;}
 else if(op==8){result=(a/2)|(a&0x80000000);carry=a%2;}
 else if(op==9){result=std::rotr(uint32_t(a),1);carry=a%2;}
 else if(op==10){result=(a<<1)&mask;carry=(a>>31)&1;}
 else if(op==11){result=std::rotl(uint32_t(a),1);carry=(a>>31)&1;}
 else if(op==15){result=std::rotl(uint32_t(a),8);carry=(a>>24)&1;}
 else {
  __int128 math=op==5?__int128(signed_value(a,bits))-signed_value(b,bits):__int128(signed_value(a,bits))+signed_value(b,bits);
  overflow=math<-(__int128(1)<<(bits-1))||math>((__int128(1)<<(bits-1))-1);
  result=(op==5?a-b:a+b)&mask;carry=op==5?a<b:a+b>mask;
 }
 uint64_t expected=op==6?result:(concat_64(d.m_ach.ui,0)|result);
 uint32_t flags=(original&~(C|Z|S))|(carry?C:0)|(result==0?Z:0)|((result&(1ull<<(bits-1)))?S:0)|(overflow?V:0);
 d.op_alu(op<<26);
 assert(uint64_t(d.m_alu)==expected);assert(d.m_flags==flags);
 assert(d.m_acl.ui==uint32_t(a)&&d.m_pl.ui==uint32_t(b));
 assert(d.m_icount==-1&&!d.m_update_mul);
 // Debugger reads must not clear flags; ordinary host reads must clear V/EF.
 d.mach.disabled=true;auto observed=d.program_control_r();
 assert((observed&V)==(flags&V)&&d.m_flags==flags&&d.irq==1);
 d.mach.disabled=false;observed=d.program_control_r();
 assert((observed&V)==(flags&V)&&!(d.m_flags&V)&&d.irq==0);
 assert((d.program_control_r()&V)==0);
}
int main(){
// PROBE
 unsigned cases=0;
 for(unsigned op:{1u,2u,3u,4u,5u,6u,8u,9u,10u,11u,15u}){
  unsigned bits=op==6?48:32;uint64_t sign=1ull<<(bits-1),mask=(1ull<<bits)-1;
  uint64_t values[]={0,1,2,sign-2,sign-1,sign,sign+1,mask-1,mask,0x55555555,0xaaaaaaaa};
  for(auto a:values)for(auto b:values)for(bool sticky:{false,true}){check(op,a,b,sticky);++cases;}
  uint64_t random=0xfeedcafe12345678ull;
  for(unsigned i=0;i<20000;++i){
   random=random*6364136223846793005ull+1442695040888963407ull;auto a=random&mask;
   random=random*6364136223846793005ull+1442695040888963407ull;
   check(op,a,random&mask,i&1);++cases;
  }
 }
 std::cout<<cases<<" actual ALU boundary/random/sticky/read-clear cases passed under UBSan\n";
}
'''
if os.environ.get('SCUDSP_ALU_UB_PROBE'):
    cpp=cpp.replace('// PROBE','scudsp_cpu_device probe;probe.m_acl.ui=0x7fffffff;probe.m_pl.ui=1;probe.op_alu(4u<<26);return 0;')
with tempfile.TemporaryDirectory(prefix='scudsp-alu-') as folder:
    source=Path(folder)/'test.cpp';exe=Path(folder)/'test'
    source.write_text(cpp.replace('// MACROS',macros).replace('// METHODS',methods))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g',
                    '-fsanitize=undefined','-fno-sanitize-recover=all',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

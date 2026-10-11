#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual DSP control/branch methods: documented flags, wraparound and debugger PC."""
from pathlib import Path
import subprocess,tempfile
from saturn_vdp_wip_test import method
root=Path(__file__).resolve().parent.parent
s=(root/'src/devices/cpu/scudsp/scudsp.cpp').read_text()
names=['op_alu','get_source_mem_value','get_source_mem_reg_value','compute_condition','set_dest_mem_reg','set_dest_mem_reg_2','op_move_immediate','op_jump','op_loop','execute_one','program_control_w']
def extract(n):return method(s.replace('scudsp_cpu_device::','saturn_vdp1_device::'),n).replace('saturn_vdp1_device::','scudsp_cpu_device::')
fixture=r'''
#include <cstdint>
#include <cassert>
#include <array>
#include <bit>
using s32=int32_t;using s64=int64_t;using u16=uint16_t;
#define SET_C(v) (m_flags=(m_flags&~(1U<<CF))|((v)?(1U<<CF):0))
#define SET_S(v) (m_flags=(m_flags&~(1U<<SF))|((v)?(1U<<SF):0))
#define SET_Z(v) (m_flags=(m_flags&~(1U<<ZF))|((v)?(1U<<ZF):0))
#define scudsp_readmem(a,b) ram[(b)*64+(a)]
using u32=uint32_t;using offs_t=uint32_t;
#define BIT(x,n) (((x)>>(n))&1)
#define ACCESSING_BITS_24_31 (mem_mask&0xff000000)
#define ACCESSING_BITS_16_23 (mem_mask&0x00ff0000)
#define ACCESSING_BITS_0_15 (mem_mask&0xffff)
#define INPUT_LINE_RESET 0
#define INPUT_LINE_HALT 1
#define ASSERT_LINE 1
#define CLEAR_LINE 0
#define scudsp_readop(a) program[a]
#define scudsp_writemem(a,b,v) ram[(b)*64+(a)]=(v)
namespace util {int32_t sext(uint32_t v,int n){return int32_t(v<<(32-n))>>(32-n);}}
struct scudsp_cpu_device {
 enum{LEF=15,EXF,ESF,EF,VF,CF,ZF,SF,T0F,EPF=25,PRF};
 enum{DMA_STATE_IDLE};
 uint8_t m_instruction_pc=0;
 uint8_t m_pc=0,m_delay=0,m_top=0,m_ct[4]{};
 uint8_t m_loop_pc=0;uint32_t m_loop_opcode=0;bool m_loop_active=false;
 bool m_delay_pending=false,m_paused=false,m_stalled=false;
 uint16_t m_lop=0;uint32_t m_flags=0,m_ra0=0,m_wa0=0;
 union R {uint32_t ui=0;int32_t si;};R m_rx,m_ry,m_pl,m_acl;
 union H {uint16_t ui=0;int16_t si;};H m_ph,m_ach;
 int64_t m_mul=0,m_alu=0;int m_update_mul=0,m_icount=100,m_dma_state=0;
 uint32_t program[256]{},ram[256]{};unsigned hooked=999;
 void debugger_instruction_hook(unsigned p){hooked=p;}
 bool dma_conflict(uint32_t)const{return false;}
 void set_input_line(int,int){}
 void op_alu(uint32_t);uint32_t get_source_mem_value(uint8_t);uint32_t get_source_mem_reg_value(uint32_t);
 void op_illegal(uint32_t){assert(false);}
 void op_dma(uint32_t){--m_icount;}
 void op_end(uint32_t){m_flags&=~(1<<EXF);--m_icount;}
 uint32_t compute_condition(uint32_t)const;
 void set_dest_mem_reg(uint32_t,uint32_t);void set_dest_mem_reg_2(uint32_t,uint32_t);
 void op_move_immediate(uint32_t);void op_jump(uint32_t);void op_loop(uint32_t);void execute_one();
 void program_control_w(offs_t,uint32_t,uint32_t=~0U);
};
// METHODS
int main(){
 scudsp_cpu_device d;
 // Every documented condition, with every combination of its four input flags.
 for(unsigned flags=0;flags<16;++flags){
  d.m_flags=((flags&1)<<d.ZF)|(((flags>>1)&1)<<d.SF)|(((flags>>2)&1)<<d.CF)|(((flags>>3)&1)<<d.T0F);
  for(unsigned mask:{1U,2U,3U,4U,8U})for(unsigned positive:{0U,32U}){
   bool expected=positive?bool(flags&mask):!(flags&mask);
   assert(bool(d.compute_condition(mask|positive))==expected);
   d.m_rx.ui=0;d.op_move_immediate(0x92000000|((mask|positive)<<19)|0x7ffff);
   assert(d.m_rx.ui==(expected?0xffffffffU:0));
   d.m_pc=23;d.m_delay_pending=false;d.op_jump(0xd0000007|((0x40|mask|positive)<<19));
   assert(d.m_pc==(expected?7:23));assert(d.m_delay_pending==expected);
  }
 }
 // Parallel X/Y/D1 reads must use the same original bank address.
 d.m_flags=0;d.m_ct[0]=0;d.ram[0]=3;d.ram[1]=11;
 d.op_alu(0x02493504); // MOV MC0,X; MOV MC0,Y; MOV MC0,PL
 assert(d.m_rx.ui==3 && d.m_ry.ui==3 && d.m_pl.ui==3 && d.m_ct[0]==1);
 // A D1 CT write overrides a parallel postincrement, including wraparound.
 d.m_ct[0]=63;d.ram[63]=17;d.op_alu(0x02401c05);
 assert(d.m_rx.ui==17 && d.m_ct[0]==5);
 // Defined 32-bit ALU operations retain ACH and update S/Z/C.
 for(unsigned op:{1U,2U,3U,4U,5U,8U,9U,10U,11U,15U})
 for(uint32_t a:{0U,1U,0x80000000U,0xffffffffU,0x12345678U})
 for(uint32_t b:{0U,1U,0x80000000U,0xffffffffU}){
  uint32_t value=0;bool carry=false;
  switch(op){
   case 1:value=a&b;break;case 2:value=a|b;break;case 3:value=a^b;break;
   case 4:value=a+b;carry=uint64_t(a)+b>0xffffffff;break;
   case 5:value=a-b;carry=a<b;break;
   case 8:value=(a>>1)|(a&0x80000000);carry=a&1;break;
   case 9:value=(a>>1)|(a<<31);carry=a&1;break;
   case 10:value=a<<1;carry=a>>31;break;
   case 11:value=(a<<1)|(a>>31);carry=a>>31;break;
   case 15:value=(a<<8)|(a>>24);carry=(a>>24)&1;break;
  }
  d.m_acl.ui=a;d.m_pl.ui=b;d.m_ach.ui=0xabcd;d.m_flags=0;d.op_alu(op<<26);
  assert(uint64_t(d.m_alu)==(0xabcd00000000ULL|value));
  assert(bool(BIT(d.m_flags,d.CF))==carry && bool(BIT(d.m_flags,d.ZF))==(value==0) && bool(BIT(d.m_flags,d.SF))==bool(value>>31));
 }
 // Signed multiplication must also update when RX is written through MVI.
 d.m_ry.si=-2;d.m_delay_pending=false;d.m_pc=1;d.program[1]=0x90010000;d.execute_one();assert(d.m_mul==-131072);
 // Arithmetic flags and upper accumulator preservation.
 d.m_ach.ui=0x1234;d.m_acl.ui=0xffffffff;d.m_pl.ui=1;d.m_flags=0;d.op_alu(4U<<26);
 assert(uint64_t(d.m_alu)==0x123400000000ULL && BIT(d.m_flags,d.CF) && BIT(d.m_flags,d.ZF));
 d.m_acl.ui=0x7fffffff;d.m_flags=0;d.op_alu(4U<<26);assert(BIT(d.m_flags,d.VF) && BIT(d.m_flags,d.SF));
 d.m_ach.ui=0xffff;d.m_acl.ui=0xffffffff;d.m_ph.ui=0;d.m_pl.ui=1;d.m_flags=0;d.op_alu(6U<<26);
 assert(d.m_alu==0 && BIT(d.m_flags,d.CF) && BIT(d.m_flags,d.ZF));
 // LPS executes the next instruction LOP+1 times without reexecuting LPS.
 d.m_flags=0;d.m_delay_pending=false;d.m_pc=10;d.m_lop=2;d.m_icount=100;
 d.program[10]=0xe8000000;d.program[11]=0x00001007;d.m_ct[0]=0;
 d.execute_one();for(unsigned i=0;i<3;++i)d.execute_one();
 assert(d.m_ct[0]==3 && d.ram[0]==7 && d.ram[1]==7 && d.ram[2]==7);
 assert(d.m_icount==96 && d.m_lop==0 && !d.m_loop_active && d.m_pc==12);
 // A jump at FF must execute prefetched address 00 before its target.
 d.m_flags=0;d.m_delay_pending=false;d.m_pc=255;d.program[255]=0xd0000007;d.program[0]=0x9000002a;
 d.execute_one();assert(d.m_pc==7 && d.m_delay_pending && d.m_delay==0);
 d.execute_one();assert(d.m_rx.ui==42 && d.m_pc==7 && !d.m_delay_pending && d.hooked==0);
 d.set_dest_mem_reg(10,0xffffffff);assert(d.m_lop==0xfff);
 // Stopped EP/PR writes have no effect; running writes pause and resume.
 d.m_flags=0;d.program_control_w(0,1U<<d.EPF,0xff000000);assert(!d.m_paused);
 d.m_flags=1<<d.EXF;d.program_control_w(0,1U<<d.EPF,0xff000000);assert(d.m_paused);
 d.program_control_w(0,1U<<d.PRF,0xff000000);assert(!d.m_paused);
 // Ordinary 32-bit pause/resume writes preserve EX; ES cannot step a
 // program that was running when the host wrote its stop command.
 d.m_flags=1U<<d.EXF;d.program_control_w(0,1U<<d.EPF);assert(d.m_paused && (d.m_flags&(1U<<d.EXF)));
 d.program_control_w(0,1U<<d.PRF);assert(!d.m_paused && (d.m_flags&(1U<<d.EXF)));
 d.program[0]=0x90000077;d.m_pc=0;d.m_rx.ui=0;
 d.program_control_w(0,1U<<d.ESF);assert(d.m_pc==0 && d.m_rx.ui==0 && !(d.m_flags&(1U<<d.EXF)));
 d.program_control_w(0,1U<<d.ESF);assert(d.m_pc==1 && d.m_rx.ui==0x77);
 for(unsigned i=0;i<4;++i){d.set_dest_mem_reg(12+i,0xff);assert(d.m_ct[i]==63);d.set_dest_mem_reg(i,123+i);assert(d.ram[64*i+63]==123+i && d.m_ct[i]==0);}
}
'''
fixture=fixture.replace('// METHODS','\n'.join(extract(n) for n in names))
with tempfile.TemporaryDirectory(prefix='scudsp-control-') as directory:
 p=Path(directory);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('SCU DSP control, condition matrix, delay wrap/debugger and register widths PASS (ASan/UBSan)')

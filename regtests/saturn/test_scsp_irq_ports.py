#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual SCSP mapped write/read/IRQ methods; timers and serial engine are stand-ins."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
src=Path(os.environ.get('SCSP_IRQ_SOURCE',ROOT/'src/devices/sound/scsp.cpp')).read_text()
def extract(signature):
    a=src.index(signature);b=src.index('{',a)+1;depth=1
    while depth:
        depth+=(src[b]=='{')-(src[b]=='}');b+=1
    return src[a:b]
methods='\n'.join(extract(sig) for sig in (
    'void scsp_device::write(', 'u16 scsp_device::read(',
    'void scsp_device::w16(', 'u16 scsp_device::r16(',
    'void scsp_device::UpdateReg(', 'void scsp_device::UpdateRegR(',
    'void scsp_device::CheckPendingIRQ(', 'void scsp_device::MainCheckPendingIRQ(',
    'void scsp_device::update_main_irq(', 'void scsp_device::ResetInterrupts('))
# Bound old-source recursion before it can exhaust the host stack.
dma=extract('void scsp_device::exec_dma(')
dma=dma.replace('void scsp_device::exec_dma() {','void scsp_device::exec_dma() { assert(++dma_depth==1);')
methods+='\n'+dma[:-1]+'--dma_depth;}'
mutant=os.environ.get('SCSP_IRQ_MUTANT','')
# Old-source negative controls retain their old bodies; add unused mask parameters
# solely to make the old no-mask API callable by the same byte-lane harness.
methods=methods.replace('u16 scsp_device::read(offs_t offset) {','u16 scsp_device::read(offs_t offset, u16 mem_mask) {').replace('u16 scsp_device::r16(u32 addr) {','u16 scsp_device::r16(u32 addr, u16 mem_mask) {').replace('void scsp_device::UpdateRegR(int reg) {','void scsp_device::UpdateRegR(int reg, u16 mem_mask) {')
original=methods
if mutant=='dma-self-write':methods=methods.replace('if (reg_addr < 0x412 || reg_addr > 0x416)', 'if (true)')
if mutant=='dma-memory-step':methods=methods.replace('mem_addr = (mem_addr + 2) & 0xffffe;', 'mem_addr = mem_addr;')
if mutant=='dma-register-step':methods=methods.replace('reg_addr = (reg_addr + 2) & 0xffe;', 'reg_addr = reg_addr;')
if mutant=='dma-gate':methods=methods.replace('gate ? 0 : tmp', 'tmp')
if mutant=='dma-wrap':methods=methods.replace('(mem_addr + 2) & 0xffffe', '(mem_addr + 2)')
if mutant=='midi-read-mask':methods=methods.replace('(mem_mask & 0x00ff) && !machine().side_effects_disabled()', '!machine().side_effects_disabled()')
if mutant=='midi-debug-pop':methods=methods.replace(' && !machine().side_effects_disabled()', '')
if mutant=='midi-merge-pop':methods=methods.replace('r16(offset * 2, 0)', 'r16(offset * 2)')
if mutant=='midi-write-input':methods=methods.replace('if (addr == 0x404)', 'if (false)')
if mutant=='midi-output-mask':methods=methods.replace('if (!(mem_mask & 0x00ff))', 'if (false)')
if mutant=='wrong-port':methods=methods.replace('addr == 0x420 || addr == 0x42c','addr == 0x420 || addr == 0x42e')
if mutant=='stale-clear':methods=methods.replace('= val & mem_mask;', '= val;')
if mutant=='sticky-clear':methods=methods.replace('= val & mem_mask;', '|= val & mem_mask;')
if mutant=='clear-zero':methods=methods.replace('= val & mem_mask;', '= ~val & mem_mask;')
if mutant=='pending-clobber':methods=methods.replace('|= val & mem_mask & 0x20;', '= val & mem_mask & 0x20;')
if mutant=='pending-unmasked':methods=methods.replace('|= val & mem_mask & 0x20;', '|= val;')
if mutant=='main-no-redrive':methods=methods.replace('    m_mcipd &= ~m_udata.data[0x2e / 2];\n    MainCheckPendingIRQ(0);','    m_mcipd &= ~m_udata.data[0x2e / 2];')
if mutant:assert methods!=original,'unknown or no-op mutation'
cpp=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <iterator>
#include <map>
#include <vector>
#include <utility>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using s16=int16_t;using s32=int32_t;using offs_t=u32;
constexpr int CLEAR_LINE=0,ASSERT_LINE=1;
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
struct scsp_device {
 union regs {u16 data[32];u8 datab[64];regs():data{} {}} m_udata;
 struct {regs udata;} m_Slots[32];s16 m_RINGBUF[128]{};
 struct {s16 COEF[64]{},EFREG[16]{},EXTS[2]{};u16 MADRS[32]{},MPRO[512]{};
 s32 TEMP[128]{},MEMS[32]{},MIXS[16]{};u32 RBL=0,RBP=0;void Start(){}}m_DSP;
 struct {u32 dmea=0,drga=0,dtlg=0,ddir=0,dgate=0;}m_dma;
 u16 m_mcieb=0,m_mcipd=0,m_latched_MSLC=0,m_latched_MSLC_data=0;
 u32 m_current_level=0,m_MidiR=0,m_MidiW=0,m_MidiOutR=0,m_MidiOutW=0;
 u8 m_MidiStack[32]{},m_MidiOutStack[32]{};
 struct {bool lines[8]{};bool isunset(){return false;}void operator()(unsigned n,int v){assert(n<8);lines[n]=v;}}m_irq_cb;
 struct {bool line=false;void operator()(int v){line=v;}}m_main_irq_cb;
 struct stream {void update(){}}stream_instance;stream *m_stream=&stream_instance;
 u32 RBL(){return(m_udata.data[1]>>7)&3;}u32 RBP(){return m_udata.data[1]&63;}
 u32 SCILV0(){return m_udata.data[0x24/2];}u32 SCILV1(){return m_udata.data[0x26/2];}u32 SCILV2(){return m_udata.data[0x28/2];}
 bool inspecting=false;bool side_effects_disabled(){return inspecting;}
 auto &machine(){return *this;}const char*describe_context(){return "fixture";}
 template<class...T>void logerror(T...){}
 void update_master_volume(){}unsigned starts=0;void transmit_register_setup(u8){++starts;}void exec_dma();unsigned dma_depth=0;
 std::map<u32,u16> ram;std::vector<u32> reads;std::vector<std::pair<u32,u16>> writes;
 auto &space(){return *this;}
 u16 raw(u32 a){auto it=ram.find(a);return it==ram.end()?u16((a>>1)^0x5a5a):it->second;}
 u16 read_word(u32 a){assert(a<=0xffffe&&!(a&1));reads.push_back(a);return raw(a);}
 void write_word(u32 a,u16 v){assert(a<=0xffffe&&!(a&1));writes.emplace_back(a,v);ram[a]=v;}
 void timer_write(int,u16,u16){}u8 timer_read(int){return 0;}
 void UpdateSlotReg(int,int){}void UpdateSlotRegR(int,int){}
 void write(offs_t,u16,u16=0xffff);u16 read(offs_t,u16=0xffff);
 void w16(u32,u16,u16=0xffff);u16 r16(u32,u16=0xffff);void UpdateReg(int,u16);void UpdateRegR(int,u16=0xffff);
 void CheckPendingIRQ();void MainCheckPendingIRQ(u16);void update_main_irq();void ResetInterrupts();
 void seed(u16 pend,u16 stale,bool main){
  m_udata.data[0x20/2]=pend;m_mcipd=pend;
  m_udata.data[0x1e/2]=0x7ff;m_mcieb=0x7ff;m_udata.data[0x24/2]=0xff;
  m_udata.data[(main?0x2e:0x22)/2]=stale;
  CheckPendingIRQ();update_main_irq();
 }
 void verify(u16 sound,u16 main){
  assert(read(0x420/2)==sound);assert(read(0x42c/2)==main);
  assert(m_current_level==(sound?1u:0u));assert(m_irq_cb.lines[1]==bool(sound));
  assert(m_main_irq_cb.line==bool(main));
 }
};
// METHODS
int main(){
 unsigned dma_cases=0;
 // A self-executing payload would recursively enter exec_dma on the old core.
 for(bool gate:{false,true})for(u16 trigger:{u16(0x1008),u16(0x7008),u16(0x2000),u16(0)}){
  scsp_device s;s.seed(0,0,false);
  s.ram[0x8000]=0x9000;s.ram[0x8002]=0x700;s.ram[0x8004]=trigger;s.ram[0x8006]=0x300;
  s.write(0x412/2,0x8000);s.write(0x414/2,0x412);
  s.write(0x416/2,0x1008|(gate?0x4000:0));
  assert(s.m_dma.dmea==0x8000&&s.m_dma.drga==0x412&&s.m_dma.dtlg==8);
  assert(s.m_dma.ddir==0&&s.m_dma.dgate==unsigned(gate));
  assert(s.m_udata.data[0x12/2]==0x8000&&s.m_udata.data[0x14/2]==0x412);
  assert(s.m_udata.data[0x16/2]==(8|(gate?0x4000:0)));
  assert(s.m_udata.data[0x18/2]==(gate?0:0x300));
  assert(s.reads==std::vector<u32>({0x8000,0x8002,0x8004,0x8006}));
  s.verify(0x10,0x10);
  s.ram[0x8006]=0x100;s.write(0x416/2,0x1008);
  assert(s.m_udata.data[0x18/2]==0x100&&s.reads.size()==8);++dma_cases;
 }
 for(bool dir:{false,true})for(bool gate:{false,true})
 for(u32 base:{0u,2u,0x7fff0u,0xffff0u})for(u16 length:{u16(0),u16(2),u16(32),u16(128)}){
  scsp_device s;s.seed(0,0,false);
  for(unsigned i=0;i<64;++i)s.m_DSP.COEF[i]=s16(0x8000^(i*13));
  s.write(0x412/2,base&0xffff);s.write(0x414/2,((base>>4)&0xf000)|0x700);
  s.write(0x416/2,0x1000|(dir?0x2000:0)|(gate?0x4000:0)|length);
  assert(s.reads.size()==(dir?0:length/2));assert(s.writes.size()==(dir?length/2:0));
  for(unsigned i=0;i<length/2;++i){
   u32 a=(base+i*2)&0xffffe;
   if(dir){assert(s.writes[i]==std::make_pair(a,u16(gate?0:0x8000^(i*13))));}
   else{assert(s.reads[i]==a);assert(u16(s.m_DSP.COEF[i])==(gate?0:s.raw(a)));}
  }
  assert(!(s.m_udata.data[0x16/2]&0x1000));s.verify(0x10,0x10);++dma_cases;
 }
 // DGATE forces zero at the destination but must not suppress source reads.
 for(bool gate:{false,true}){
  scsp_device s;s.m_MidiW=1;s.m_MidiStack[0]=0xa5;s.seed(8,0,false);
  s.write(0x412/2,0x8000);s.write(0x414/2,0x404);
  s.write(0x416/2,0x3002|(gate?0x4000:0));
  assert(s.m_MidiR==1&&s.ram[0x8000]==(gate?0:0xa5));s.verify(0x10,0x10);++dma_cases;
 }
 std::cout<<dma_cases<<" actual DMA transfer/gate/wrap/self-target safety cases passed\n";
 unsigned midi=0;
 for(unsigned pos=0;pos<32;++pos)for(unsigned count:{0u,1u,2u,31u})
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(bool debug:{false,true}){
  scsp_device s;s.m_MidiR=pos;s.m_MidiW=(pos+count)&31;s.m_MidiStack[pos]=0xa5;
  s.m_udata.data[2]=0x7e00;s.seed(count?8:0,0,false);s.inspecting=debug;
  auto value=s.read(0x404/2,mask);assert(value==0x7ea5);
  bool pop=count&&(mask&0xff)&&!debug;
  assert(s.m_MidiR==((pos+pop)&31));assert(s.m_MidiW==((pos+count)&31));
  s.verify(count>unsigned(pop)?8:0,count>unsigned(pop)?8:0);++midi;
 }
 for(unsigned pos=0;pos<32;++pos)for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(u16 val:{u16(0),u16(0xffff),u16(0xa55a)}){
  scsp_device s;s.m_MidiR=pos;s.m_MidiW=(pos+1)&31;s.m_MidiStack[pos]=0xa5;
  s.m_udata.data[2]=0x7ea5;s.seed(8,0,false);
  s.write(0x404/2,val,mask);assert(s.m_MidiR==pos&&s.m_udata.data[2]==0x7ea5);s.verify(8,8);
  s.w16(0x404,val,mask);assert(s.m_MidiR==pos&&s.m_udata.data[2]==0x7ea5);s.verify(8,8);++midi;
 }
 for(unsigned pos=0;pos<32;++pos)for(bool busy:{false,true})
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(u16 val:{u16(0),u16(0xffff),u16(0xa55a)}){
  scsp_device s;s.m_MidiOutW=pos;s.m_MidiOutR=busy?(pos+31)&31:pos;
  s.m_udata.data[3]=0x1234;s.seed(0x200,0,false);s.write(0x406/2,val,mask);
  bool send=mask&0xff;assert(s.m_MidiOutW==((pos+send)&31));
  assert(s.starts==unsigned(send&&!busy));if(send)assert(s.m_MidiOutStack[pos]==(val&255));
  s.verify(send?0:0x200,send?0:0x200);++midi;
 }
 std::cout<<midi<<" actual MIDI read/write/debugger/byte-lane cases passed\n";
 unsigned clears=0,pending=0;
 for(bool main:{false,true})for(unsigned p=0;p<2048;++p)
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(u16 stale:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(unsigned command=0;command<13;++command){
  u16 val=command<11?1u<<command:command==11?0:0xffff;
  scsp_device s;s.seed(p,stale,main);s.write((main?0x42e:0x422)/2,val,mask);
  u16 want=p&~(val&mask);s.verify(main?p:want,main?want:p);++clears;
 }
 for(bool main:{false,true})for(unsigned p=0;p<2048;++p)
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(u16 val:{u16(0),u16(0x10),u16(0x20),u16(0x100),u16(0x400),u16(0x7df),u16(0xffff)}){
  scsp_device s;s.seed(p,0,main);s.write((main?0x42c:0x420)/2,val,mask);
  u16 want=p|(val&mask&0x20);s.verify(main?p:want,main?want:p);++pending;
 }
 std::cout<<clears<<" actual SCSP acknowledgement/mask/stale-command cases and "<<pending<<" pending-port cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-irq-') as tmp:
    p=Path(tmp);(p/'test.cpp').write_text(cpp.replace('// METHODS',methods))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

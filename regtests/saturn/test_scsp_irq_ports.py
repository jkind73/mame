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
    'void scsp_device::update_main_irq(', 'void scsp_device::ResetInterrupts(',
    'void scsp_device::tra_callback(', 'void scsp_device::tra_complete(',
    'void scsp_device::rcv_complete('))
# The pre-FIFO source had no MIDI reset at all: device_reset left both buffers,
# their pointers and the serial shift registers untouched. Reproduce exactly
# that so an old-source negative control fails assertions instead of compiling.
if 'void scsp_device::reset_midi(' in src:
    methods+='\n'+extract('void scsp_device::reset_midi(')
else:
    methods+='\nvoid scsp_device::reset_midi() {}'
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
if mutant=='midi-depth-wrap':methods=methods.replace('    if (m_MidiOutCount == 4)\n      break;\n', '')
if mutant=='midi-status-bits':methods=methods.replace('''    u16 v = (m_MidiCount == 0 ? 0x0100 : 0) |
            (m_MidiCount == 4 ? 0x0200 : 0) |
            (m_MidiOverflow ? 0x0400 : 0) |
            (m_MidiOutCount == 0 ? 0x0800 : 0) |
            (m_MidiOutCount == 4 ? 0x1000 : 0) |
            m_MidiStack[m_MidiR];''', '''    u16 v = m_udata.data[0x4 / 2];
    v &= 0xff00;
    v |= m_MidiStack[m_MidiR];''')
if mutant=='midi-mobuf-readable':methods=methods.replace('    m_udata.data[0x6 / 2] = 0;\n    break;', '    break;')
if mutant=='midi-in-depth':methods=methods.replace('if (m_MidiCount == 4) {', 'if (false) {')
if mutant=='midi-overflow-latch':methods=methods.replace('    m_MidiOverflow = true;', '    m_MidiOverflow = false;')
if mutant=='midi-overflow-clear':methods=methods.replace('        m_MidiOverflow = false;\n', '')
if mutant=='midi-out-count':methods=methods.replace('  if (m_MidiOutCount)\n    --m_MidiOutCount;', '')
if mutant=='midi-early-pop':methods=methods.replace('''void scsp_device::tra_callback() {
  m_midi_out_cb(transmit_register_get_data_bit());''','''void scsp_device::tra_callback() {
  if (m_MidiOutCount) {
    --m_MidiOutCount;
    m_MidiOutR = (m_MidiOutR + 1) & 3;
    if (!m_MidiOutCount) {
      m_udata.data[0x20 / 2] |= 0x200;
      CheckPendingIRQ();
      MainCheckPendingIRQ(0x200);
    }
  }
  m_midi_out_cb(transmit_register_get_data_bit());''').replace('''  if (m_MidiOutCount)
    --m_MidiOutCount;
  m_MidiOutR = (m_MidiOutR + 1) & 3;''', '')
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
 // Deliberately oversized: production indexes both with &3 (ST-077 p.90 says
 // 4 bytes each), and an old-source negative control must fail an assertion
 // rather than write out of bounds first.
 u8 m_MidiStack[32]{},m_MidiOutStack[32]{};
 u8 m_MidiCount=0,m_MidiOutCount=0;bool m_MidiOverflow=false;
 struct {bool lines[8]{};bool isunset(){return false;}void operator()(unsigned n,int v){assert(n<8);lines[n]=v;}}m_irq_cb;
 struct {bool line=false;void operator()(int v){line=v;}}m_main_irq_cb;
 struct {unsigned bits=0;void operator()(int){++bits;}}m_midi_out_cb;
 struct stream {void update(){}}stream_instance;stream *m_stream=&stream_instance;
 u32 RBL(){return(m_udata.data[1]>>7)&3;}u32 RBP(){return m_udata.data[1]&63;}
 u32 SCILV0(){return m_udata.data[0x24/2];}u32 SCILV1(){return m_udata.data[0x26/2];}u32 SCILV2(){return m_udata.data[0x28/2];}
 bool inspecting=false;bool side_effects_disabled(){return inspecting;}
 auto &machine(){return *this;}const char*describe_context(){return "fixture";}
 template<class...T>void logerror(T...){}
 void update_master_volume(){}unsigned starts=0;void exec_dma();unsigned dma_depth=0;
 // Serial-engine stand-ins: a frame is "finished" only when the test says so.
 bool tx_empty=true;u8 rx_byte=0;std::vector<u8> tx;
 void transmit_register_setup(u8 b){assert(tx_empty);tx_empty=false;tx.push_back(b);++starts;}
 bool is_transmit_register_empty(){return tx_empty;}
 void transmit_register_reset(){tx_empty=true;}
 void receive_register_reset(){}void receive_register_extract(){}
 u8 get_received_char(){return rx_byte;}
 u8 transmit_register_get_data_bit(){return 0;}
 void tra_callback();void tra_complete();void rcv_complete();void reset_midi();
 void finish_frame(){tx_empty=true;tra_complete();}
 void set_in(unsigned pos,unsigned count,bool ovf){
  m_MidiR=pos;m_MidiW=(pos+count)&3;m_MidiCount=count;m_MidiOverflow=ovf;
  for(unsigned i=0;i<4;++i)m_MidiStack[i]=0;
  for(unsigned i=0;i<count;++i)m_MidiStack[(pos+i)&3]=u8(0xa5+i);
 }
 u16 status(){return u16(read(0x404/2,0xff00)&0xff00);}
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
  scsp_device s;s.set_in(0,1,false);s.seed(8,0,false);
  s.write(0x412/2,0x8000);s.write(0x414/2,0x404);
  s.write(0x416/2,0x3002|(gate?0x4000:0));
  assert(s.m_MidiR==1&&s.m_MidiCount==0&&s.ram[0x8000]==u16(gate?0:0x08a5));
  s.verify(0x10,0x10);++dma_cases;
 }
 // DRGA advances past MIBUF, so the second word reads write-only MOBUF as 0.
 for(bool gate:{false,true}){
  scsp_device s;s.set_in(3,2,false);s.seed(8,0,false);
  s.write(0x412/2,0x8000);s.write(0x414/2,0x404);
  s.write(0x416/2,0x3004|(gate?0x4000:0));
  assert(s.ram[0x8000]==u16(gate?0:0x08a5)&&!s.ram[0x8002]);
  assert(s.m_MidiR==0&&s.m_MidiCount==1);s.verify(0x18,0x18);++dma_cases;
  // The following two transfers are programmed without DGATE, so the FIFO
  // bytes reach sound RAM whatever the first transfer's gate was.
  // Draining the last queued byte through another transfer releases bit 3.
  s.write(0x412/2,0x8004);s.write(0x414/2,0x404);s.write(0x416/2,0x3002);
  assert(s.ram[0x8004]==0x08a6&&s.m_MidiR==1&&s.m_MidiCount==0);
  s.verify(0x10,0x10);++dma_cases;
  // An empty FIFO read through DMA does not pop and reports MIEMP.
  s.write(0x412/2,0x8006);s.write(0x414/2,0x404);s.write(0x416/2,0x3002);
  assert(s.ram[0x8006]==0x0900&&s.m_MidiR==1&&s.m_MidiCount==0);
  s.verify(0x10,0x10);++dma_cases;
 }
 std::cout<<dma_cases<<" actual DMA transfer/gate/wrap/self-target safety cases passed\n";
 unsigned midi=0;
 // Golden status words pin Figure 4.3 (p.28) bit positions: 8=MIEMP,
 // 9=MIFULL, 10=MIOVF, 11=MOEMP, 12=MOFULL. Data byte 0xa5+i is at slot i.
 {
  scsp_device s;s.seed(0,0,false);s.reset_midi();
  assert(s.status()==0x0900);++midi;                       // both FIFOs empty
  s.rx_byte=0x11;s.rcv_complete();
  assert(s.status()==0x0800&&s.read(0x404/2)==0x0811);++midi;   // data read pops
  assert(s.status()==0x0900&&s.m_MidiCount==0);s.verify(0,0);++midi;
  for(unsigned i=0;i<4;++i){s.rx_byte=u8(0x11+i);s.rcv_complete();}
  assert(s.status()==0x0a00);++midi;                       // MIFULL at exactly 4
  s.rx_byte=0x55;s.rcv_complete();s.rx_byte=0x66;s.rcv_complete();
  assert(s.status()==0x0e00);++midi;                       // MIOVF latched
  // The popped read above left R=1, so the FIFO wraps: bytes sit at 1,2,3,0.
  assert(s.m_MidiCount==4&&s.m_MidiW==1&&s.m_MidiR==1);
  for(unsigned i=0;i<4;++i)assert(s.m_MidiStack[(1+i)&3]==u8(0x11+i));  // kept
  s.verify(8,8);++midi;
  for(unsigned i=0;i<4;++i){
   u16 const want=u16(0x0c00|(i?0:0x0200))|u16(0x11+i);
   assert(s.read(0x404/2)==want);assert(s.m_MidiCount==u8(3-i));
   assert(s.m_MidiOverflow==(i<3));++midi;                  // retires only when empty
  }
  assert(s.status()==0x0900&&!s.m_MidiOverflow);s.verify(0,0);++midi;
  // Output side with the input FIFO empty, so every status word is distinct.
  s.write(0x406/2,0xaa);
  assert(s.status()==0x0100&&s.tx==std::vector<u8>({0xaa}));++midi;
  s.verify(0,0);
  for(u8 b:{u8(0xbb),u8(0xcc),u8(0xdd)})s.write(0x406/2,b);
  assert(s.status()==0x1100&&s.m_MidiOutCount==4&&s.tx.size()==1);++midi;  // MOFULL
  s.write(0x406/2,0xee);
  assert(s.status()==0x1100&&s.m_MidiOutCount==4&&s.tx.size()==1);++midi;  // rejected
  assert(s.read(0x406/2)==0);++midi;                       // MOBUF is write only
  s.finish_frame();
  assert(s.tx==std::vector<u8>({0xaa,0xbb})&&s.m_MidiOutCount==3);
  assert(s.status()==0x0100);s.verify(0,0);++midi;         // MOFULL retired
  s.finish_frame();s.finish_frame();
  assert(s.tx==std::vector<u8>({0xaa,0xbb,0xcc,0xdd})&&s.m_MidiOutCount==1);
  assert(s.status()==0x0100);s.verify(0,0);++midi;
  s.finish_frame();
  assert(s.m_MidiOutCount==0&&s.tx.size()==4&&s.tx_empty);
  assert(s.status()==0x0900);s.verify(0x200,0x200);++midi;  // empty request at frame end
  s.write(0x406/2,0x77);
  assert(s.tx.size()==5&&s.tx.back()==0x77&&s.m_MidiOutCount==1);
  assert(s.status()==0x0100);s.verify(0,0);++midi;         // restarts after a drain
 }
 // Combined status field: every input/output occupancy pair and overflow
 // latch must report exactly the Figure 4.3 bits, with MIBUF in the low byte.
 for(unsigned in=0;in<=4;++in)for(unsigned out=0;out<=4;++out)for(bool ovf:{false,true}){
  scsp_device s;s.set_in(1,in,ovf);s.m_MidiOutW=2;s.m_MidiOutR=2;s.m_MidiOutCount=out;
  for(unsigned i=0;i<out;++i)s.m_MidiOutStack[(2+i)&3]=u8(0x30+i);
  s.tx_empty=!out;s.seed(in?8:0,0,false);
  u16 const want=u16((in?0:0x0100)|(in==4?0x0200:0)|(ovf?0x0400:0)|
                     (out?0:0x0800)|(out==4?0x1000:0));
  assert(s.status()==want);
  assert(s.read(0x404/2)==u16(want|s.m_MidiStack[1]));
  assert(s.m_MidiCount==u8(in?(in-1):0));
  assert(s.read(0x406/2)==0);                    // MOBUF never reads back
  s.verify((in?(in-1):0)?8:0,(in?(in-1):0)?8:0);++midi;
 }
 // Input read matrix: every pointer position, occupancy, lane and peek mode.
 for(unsigned pos=0;pos<4;++pos)for(unsigned count=0;count<=4;++count)
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(bool debug:{false,true})for(bool ovf:{false,true}){
  scsp_device s;s.set_in(pos,count,ovf);s.seed(count?8:0,0,false);s.inspecting=debug;
  u16 const want=u16((count?0:0x0100)|(count==4?0x0200:0)|(ovf?0x0400:0)|0x0800)
                |s.m_MidiStack[pos];
  assert(s.read(0x404/2,mask)==want);
  bool const consume=(mask&0xff)&&!debug;
  bool const pop=count&&consume;
  assert(s.m_MidiR==((pos+pop)&3));assert(s.m_MidiCount==u8(count-pop));
  // The latch retires on any consuming read that leaves the FIFO empty.
  assert(s.m_MidiOverflow==(ovf&&!(consume&&(count-pop)==0)));
  s.verify(s.m_MidiCount?8:0,s.m_MidiCount?8:0);++midi;
 }
 // Input register writes are ignored on every lane and path, DMA-facing too.
 for(unsigned pos=0;pos<4;++pos)for(unsigned count=0;count<=4;++count)
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(u16 val:{u16(0),u16(0xffff),u16(0xa55a)}){
  scsp_device s;s.set_in(pos,count,count==4);s.seed(count?8:0,0,false);
  u16 const want=u16((count?0:0x0100)|(count==4?0x0600:0)|0x0800);
  s.write(0x404/2,val,mask);
  assert(s.m_MidiR==pos&&s.m_MidiCount==count&&s.m_MidiW==((pos+count)&3));
  // The write must not even reach the register file: the merge peek leaves the
  // derived status/MIBUF word there, so a stored value would be observable.
  assert(s.m_udata.data[2]==u16(want|s.m_MidiStack[pos]));
  assert(s.status()==want);s.verify(count?8:0,count?8:0);
  s.w16(0x404,val,mask);
  assert(s.m_MidiR==pos&&s.m_MidiCount==count&&s.status()==want);
  assert(s.m_udata.data[2]==u16(want|s.m_MidiStack[pos]));
  s.verify(count?8:0,count?8:0);++midi;
 }
 // Output write matrix: full FIFO and non-data lanes must not queue or start.
 for(unsigned pos=0;pos<4;++pos)for(unsigned count=0;count<=4;++count)
 for(u16 mask:{u16(0),u16(0xff),u16(0xff00),u16(0xffff)})
 for(u16 val:{u16(0),u16(0xffff),u16(0xa55a)}){
  scsp_device s;s.m_MidiOutW=pos;s.m_MidiOutR=pos;s.m_MidiOutCount=count;
  s.tx_empty=!count;if(count)s.tx={u8(0x10)};
  s.seed(0x200,0,false);s.write(0x406/2,val,mask);
  bool const send=(mask&0xff)&&count<4;
  assert(s.m_MidiOutCount==u8(count+send));
  assert(s.m_MidiOutW==((pos+send)&3)&&s.m_MidiOutR==pos);
  assert(s.tx.size()==(count?1u:(send?1u:0u)));
  if(send)assert(s.m_MidiOutStack[pos]==u8(val&0xff));
  assert(s.status()==u16((count+send?0:0x0800)|((count+send)==4?0x1000:0)|0x0100));
  s.verify(send?0:0x200,send?0:0x200);++midi;
 }
 // Drain order/occupancy through the actual serial-completion method.
 for(unsigned count=1;count<=4;++count){
  scsp_device s;s.seed(0,0,false);
  for(unsigned i=0;i<count;++i)s.write(0x406/2,0x10+i);
  assert(s.tx==std::vector<u8>({0x10})&&s.m_MidiOutCount==count);
  assert(s.status()==u16(0x0100|(count==4?0x1000:0)));
  for(unsigned i=1;i<count;++i){
   s.finish_frame();
   assert(s.tx.size()==i+1);assert(s.tx[i]==u8(0x10+i));
   assert(s.m_MidiOutCount==u8(count-i)&&!s.tx_empty);
   assert(s.status()==0x0100);s.verify(0,0);++midi;
  }
  s.finish_frame();
  assert(s.tx.size()==count&&s.m_MidiOutCount==0&&s.tx_empty);
  assert(s.status()==0x0900);s.verify(0x200,0x200);++midi;
 }
 // Shifting bits out must not change FIFO occupancy: the queued byte leaves
 // only when its frame is complete.
 {
  scsp_device s;s.seed(0,0,false);
  s.write(0x406/2,0xa1);s.write(0x406/2,0xa2);
  for(unsigned i=0;i<9;++i)s.tra_callback();
  assert(s.m_midi_out_cb.bits==9&&s.m_MidiOutCount==2&&s.m_MidiOutR==0);
  assert(s.status()==0x0100);s.verify(0,0);
  s.finish_frame();
  assert(s.m_MidiOutCount==1&&s.m_MidiOutR==1&&s.tx.size()==2);++midi;
 }
 // Input overflow depth: extra frames never enlarge or rotate the FIFO.
 for(unsigned extra=0;extra<=3;++extra){
  scsp_device s;s.seed(0,0,false);s.reset_midi();
  for(unsigned i=0;i<4+extra;++i){s.rx_byte=u8(0x20+i);s.rcv_complete();}
  assert(s.m_MidiCount==4&&s.m_MidiOverflow==(extra>0)&&s.m_MidiW==0);
  for(unsigned i=0;i<4;++i)assert(s.m_MidiStack[i]==u8(0x20+i));
  assert(s.status()==u16(0x0a00|(extra?0x0400:0)));s.verify(8,8);
  for(unsigned i=0;i<4;++i){
   // The reported word is pre-pop, so a latched overflow is still visible on
   // the read that finally empties the FIFO.
   assert(s.read(0x404/2)==(u16(0x0800|(i==0?0x0200:0)|(extra?0x0400:0))|u8(0x20+i)));
   assert(s.m_MidiCount==u8(3-i));++midi;
  }
  assert(!s.m_MidiOverflow&&s.status()==0x0900);s.verify(0,0);++midi;
 }
 // A reset must clear both FIFOs, the overflow latch and the shift registers.
 {
  scsp_device s;s.seed(8,0xff,false);
  s.set_in(2,4,true);s.m_MidiOutW=1;s.m_MidiOutR=1;s.m_MidiOutCount=4;s.tx_empty=false;
  for(unsigned i=0;i<4;++i){s.m_MidiOutStack[i]=u8(0x50+i);}
  s.tx={0x50};s.write(0x406/2,0x60);
  assert(s.tx.size()==1&&s.m_MidiOutCount==4);
  s.reset_midi();
  assert(s.m_MidiCount==0&&s.m_MidiOutCount==0&&!s.m_MidiOverflow&&s.tx_empty);
  assert(s.m_MidiR==0&&s.m_MidiW==0&&s.m_MidiOutR==0&&s.m_MidiOutW==0);
  for(unsigned i=0;i<4;++i)assert(!s.m_MidiStack[i]&&!s.m_MidiOutStack[i]);
  assert(s.status()==0x0900&&s.read(0x406/2)==0);++midi;
  s.write(0x406/2,0x61);
  assert(s.tx.size()==2&&s.tx.back()==0x61&&s.m_MidiOutCount==1);
  assert(s.status()==0x0100);++midi;
 }
 std::cout<<midi<<" actual MIDI FIFO/status/lane/drain/reset cases passed\n";
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

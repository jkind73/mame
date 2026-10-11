#!/usr/bin/env python3
# license:BSD-3-Clause
"""ASan/UBSan checks of actual SCSP DMA phases, reservations and wait methods."""
from pathlib import Path
import subprocess,tempfile
from saturn_vdp_wip_test import method
root=Path(__file__).resolve().parent.parent
src=(root/'src/devices/sound/scsp.cpp').read_text().replace('TIMER_CALLBACK_MEMBER(scsp_device::dma_tick_cb)','void scsp_device::dma_tick_cb()')
def extract(n):return method(src.replace('scsp_device::','saturn_vdp1_device::'),n).replace('saturn_vdp1_device::','scsp_device::')
fixture=r'''
#include <cassert>
#include <algorithm>
#include <cstdint>
#include <array>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;
#define BIT(v,n) (((v)>>(n))&1)
#define SDIR(slot) ((slot)->udata.data[6]&0x100)
#define SSCTL(slot) (((slot)->udata.data[0]>>7)&3)
struct attotime {int64_t n=0;static const attotime zero,never;static attotime from_ticks(int64_t n,int){return {n};}u64 as_ticks(int)const{return n;}bool operator==(attotime b)const{return n==b.n;}bool operator>(attotime b)const{return n>b.n;}};
const attotime attotime::zero{0},attotime::never{999999};
struct timer {attotime left{};void adjust(attotime a){left=a;}attotime remaining()const{return left;}};
struct scsp_device {
 struct slot {struct {u16 data[16]{};}udata;bool active=false;struct{int att=0x3ff;}EG;}m_Slots[32];
 struct {bool Stopped=true;struct{bool MRD=false,MWT=false;}MPRO_decoded[128];}m_DSP;
 struct {u32 dmea=0;u16 drga=0,dtlg=0;u8 ddir=0,dgate=0;u16 remaining=0,data=0;bool active=false,write_phase=false;}m_dma;
 struct{u16 data[32]{};}m_udata;
 struct {void update(){}}stream,*m_stream=&stream;
 timer sample,dma,*m_timerS=&sample,*m_timerDMA=&dma;
 std::array<u16,524288>ram{};std::array<u16,2048>regs{};unsigned readram=0,readreg=0,written=0,irq=0;
 int clock()const{return 1;}
 u16 read_word(u32 a){++readram;return ram[a/2];}u16 r16(u32 a){++readreg;return regs[a/2];}
 scsp_device& space(){return *this;}void write_word(u32 a,u16 v){ram[a/2]=v;++written;}void w16(u32 a,u16 v){regs[a/2]=v;++written;}void SetPending(u16 v){irq|=v;}
 void exec_dma();void dma_step();void dma_tick_cb();bool dma_memory_reserved(unsigned)const;unsigned memory_cycle()const;attotime dma_access_wait(bool)const;
 void phase(unsigned n){sample.left={512-int64_t(n*4)};dma_tick_cb();}
 void start(u32 a,u16 r,u16 count,u16 flags){m_udata.data[9]=a&0xfffe;m_udata.data[10]=((a>>4)&0xf000)|r;m_udata.data[11]=count|flags|0x1000;sample.left={512};exec_dma();}
};
// METHODS
int main(){
 for(int direction=0;direction<2;++direction)for(int gate=0;gate<2;++gate){
  scsp_device d;d.ram[0x8000]=0x1234;d.ram[0x8001]=0x5678;d.regs[0x380]=0xabcd;d.regs[0x381]=0xef12;
  d.start(0x10000,0x700,4,(direction<<13)|(gate<<14));assert(d.m_dma.active&&d.written==0&&d.irq==0);
  assert(d.dma_access_wait(direction!=0).n==4&&d.dma_access_wait(direction==0).n==0);d.dma.left={0};assert(d.dma_access_wait(direction!=0).n==4);d.dma.left={4};
  d.phase(0);if(!direction)assert(d.written==0&&!d.m_dma.write_phase); // refresh stalls memory read
  for(unsigned n=1;d.m_dma.active;++n){assert(n<20);d.phase(n);}
  assert(d.written==2&&d.irq==16&&d.m_timerDMA->left==attotime::never);
  assert(!(d.m_udata.data[11]&0x1000));
  if(direction){assert(d.ram[0x8000]==(gate?0:0xabcd)&&d.regs[0x380]==0xabcd);}else{assert(d.regs[0x380]==(gate?0:0x1234)&&d.ram[0x8000]==0x1234);}
  if(gate)assert(d.readram==0&&d.readreg==0);
  assert(d.dma_access_wait(false)==attotime::zero);
 }
 scsp_device p;p.start(0,0x412,6,0x4000);for(unsigned n=1;p.m_dma.active;++n)p.phase(n);assert(p.written==0&&p.irq==16);
 scsp_device r;r.m_Slots[0].active=true;r.m_Slots[0].EG.att=0;assert(r.dma_memory_reserved(1)&&r.dma_memory_reserved(3));r.m_Slots[0].EG.att=0x3ff;assert(!r.dma_memory_reserved(1));r.m_Slots[0].udata.data[6]=0x100;assert(r.dma_memory_reserved(1));r.m_Slots[0].udata.data[6]=0;r.m_Slots[0].EG.att=0;r.m_Slots[0].udata.data[0]=0x80;assert(!r.dma_memory_reserved(1));
 r.m_DSP.Stopped=false;r.m_DSP.MPRO_decoded[1].MRD=true;assert(r.dma_memory_reserved(2));r.m_DSP.MPRO_decoded[1].MRD=false;r.m_DSP.MPRO_decoded[1].MWT=true;assert(r.dma_memory_reserved(2));r.m_DSP.Stopped=true;assert(!r.dma_memory_reserved(2));assert(r.dma_memory_reserved(0)&&r.dma_memory_reserved(64));
 scsp_device z;z.start(0,0x700,0,0x4000);assert(z.m_dma.remaining==4096);z.exec_dma();assert(z.m_dma.remaining==4096);
}
'''
fixture=fixture.replace('// METHODS','\n'.join(extract(n) for n in ('memory_cycle','dma_memory_reserved','dma_access_wait','exec_dma','dma_step','dma_tick_cb')))
with tempfile.TemporaryDirectory(prefix='scsp-dma-phase-') as td:
 out=Path(td);(out/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)
print('SCSP DMA phases, priority reservations and access waits PASS (ASan/UBSan)')

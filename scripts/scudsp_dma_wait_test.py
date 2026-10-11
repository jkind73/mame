#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise actual DSP DMA timer/host-wait methods under ASan/UBSan."""
from pathlib import Path
import subprocess
import tempfile
from saturn_vdp_wip_test import method
root=Path(__file__).resolve().parent.parent
source=(root/'src/devices/cpu/scudsp/scudsp.cpp').read_text()
def extract(name):
 s=source.replace('TIMER_CALLBACK_MEMBER(scudsp_cpu_device::dma_tick_cb)','void scudsp_cpu_device::dma_tick_cb()')
 return method(s.replace('scudsp_cpu_device::','saturn_vdp1_device::'),name).replace('saturn_vdp1_device::','scudsp_cpu_device::')
fixture=r'''
#include <cassert>
#include <functional>
#include <cstdint>
#include <algorithm>
#define FLAGS_MASK 0x00fd0000
#define LOGMASKED(...)
#define BIT(x,n) (((x)>>(n))&1)
using u32=uint32_t;
struct attotime {
 int64_t value=0;
 static const attotime zero,never;
 static attotime from_ticks(int n,int){return {n};}
 attotime& operator+=(attotime b){value+=b.value;return *this;}
 bool operator>(attotime b)const{return value>b.value;}
 bool operator==(attotime b)const{return value==b.value;}
 attotime operator+(attotime b)const{return {value+b.value};}
};
const attotime attotime::zero{0},attotime::never{999999};
struct timer {attotime left{};void adjust(attotime a){left=a;}attotime remaining(){return left;}};
struct scudsp_cpu_device {
 enum {DMA_STATE_IDLE,DMA_STATE_WAIT,DMA_STATE_MOVE,DMA_STATE_END};
 unsigned m_dma_state=DMA_STATE_MOVE;
 struct {unsigned count=0,size=1,bank=0,dir=0,dst=0,src=0;}m_dma;
 std::function<attotime()>m_dma_wait_cb;
 std::function<bool(u32,bool)>m_dma_ready_cb;
 std::function<bool()>m_dma_start_cb;bool m_dma_wait_ready=false,m_dma_forced=false;attotime m_dma_force_cost{};
 timer storage,*m_dma_timer=&storage;
 unsigned moved=0,ends=0,cost=0;bool busy=true,m_paused=false;
 enum {VF=19,EF=18,EXF=16,CF=20,ZF=21,SF=22,T0F=23};u32 m_flags=0,m_pc=0;unsigned cleared=0;
 struct mach {bool debug=false;bool side_effects_disabled(){return debug;}} host;
 mach& machine(){return host;}
 void m_out_irq_cb(int){++cleared;}
 uint32_t program_control_r();
 int clock(){return 1;}
 void m_out_ddwt_cb(int){}void m_out_ddmv_cb(int){}
 void exec_dma(){++moved;cost+=13;}
 void dma_end(){++ends;busy=false;m_dma_state=DMA_STATE_IDLE;m_dma_forced=false;m_dma_force_cost={};}
 void dma_tick_cb();void dma_resume();attotime dma_finish(attotime prior_wait=attotime::zero);
 bool dma_conflict(uint32_t)const;uint32_t compute_condition(uint32_t)const;
 scudsp_cpu_device(){m_dma_wait_cb=[this](){auto c=cost;cost=0;return attotime{c};};}
};
// METHODS
int main(){
 scudsp_cpu_device d;
 d.dma_tick_cb();assert(d.busy && d.ends==0 && d.cost==0);
 assert(d.m_dma_state==d.DMA_STATE_END && d.storage.left.value==13);
 d.dma_tick_cb();assert(!d.busy && d.ends==1 && d.moved==1);
 // A subsequent transfer must not inherit the previous final unit's cost.
 d.busy=true;d.m_dma_state=d.DMA_STATE_MOVE;d.m_dma.count=0;d.dma_tick_cb();assert(d.storage.left.value==13);
 // Host waits for the remainder of an already issued final beat.
 d.storage.left={7};assert(d.dma_finish().value==7);assert(d.moved==2 && d.busy);d.dma_tick_cb();assert(!d.busy);
 scudsp_cpu_device multi;multi.m_dma.size=3;multi.storage.left={5};
 assert(multi.dma_finish().value==44);assert(multi.moved==3 && multi.cost==0 && multi.busy);multi.dma_tick_cb();assert(!multi.busy);
 scudsp_cpu_device pending;pending.m_dma_state=pending.DMA_STATE_WAIT;pending.storage.left={4};
 assert(pending.dma_finish().value==18);assert(pending.moved==1 && pending.busy && pending.m_dma_state==pending.DMA_STATE_WAIT);
 pending.dma_tick_cb();assert(pending.storage.left.value==14 && pending.busy);
 pending.dma_tick_cb();assert(!pending.busy);
 scudsp_cpu_device blocked;blocked.m_dma_state=blocked.DMA_STATE_WAIT;
 bool grant=false;blocked.m_dma_start_cb=[&](){return grant;};
 blocked.dma_tick_cb();assert(blocked.m_dma_wait_ready && blocked.storage.left.value==attotime::never.value && blocked.moved==0);
 assert(blocked.dma_finish().value==0 && blocked.moved==0);
 grant=true;blocked.dma_resume();assert(blocked.storage.left.value==0);
 blocked.dma_tick_cb();assert(blocked.m_dma_state==blocked.DMA_STATE_MOVE && !blocked.m_dma_wait_ready);
 blocked.dma_tick_cb();assert(blocked.moved==1 && blocked.storage.left.value==13 && blocked.busy);
 blocked.dma_tick_cb();assert(!blocked.busy);
 scudsp_cpu_device queued;queued.m_dma_state=queued.DMA_STATE_WAIT;queued.storage.left={4};
 bool free=false;queued.m_dma_start_cb=[&](){return free;};
 assert(queued.dma_finish({20}).value==34 && queued.moved==1 && queued.busy);
 assert(queued.dma_finish({10}).value==34 && queued.moved==1);
 queued.dma_tick_cb();assert(queued.m_dma_wait_ready);
 free=true;queued.dma_resume();queued.dma_tick_cb();assert(queued.storage.left.value==14 && queued.busy);
 queued.dma_tick_cb();assert(!queued.busy);
 scudsp_cpu_device conflict;
 assert(conflict.dma_conflict(0x80000001));assert(!conflict.dma_conflict(0x90000001));
 assert(!conflict.dma_conflict(0x83080001)); // conditional Z write is not executed
 conflict.m_flags=1<<conflict.ZF;assert(conflict.dma_conflict(0x83080001));
 conflict.m_dma.bank=4;assert(conflict.dma_conflict(0xb0000001)); // PC write waits for program RAM
 assert(conflict.dma_conflict(0x98000001)); // RA0 cannot change while DMA runs
 assert(conflict.dma_conflict(0x1c01));assert(!conflict.dma_conflict(0));
 scudsp_cpu_device startup;startup.m_dma_state=startup.DMA_STATE_WAIT;startup.storage.left={4};
 startup.dma_resume();assert(startup.storage.left.value==4);
 scudsp_cpu_device regs;regs.m_flags=(1<<regs.VF)|(1<<regs.EF)|(1<<regs.EXF);regs.m_pc=7;
 regs.host.debug=true;assert(regs.program_control_r()&((1<<regs.VF)|(1<<regs.EF)));assert(regs.cleared==0);
 regs.host.debug=false;auto value=regs.program_control_r();assert(value&((1<<regs.VF)|(1<<regs.EF)));
 assert(regs.m_flags==(1<<regs.EXF) && regs.cleared==1 && (value&255)==7);
 regs.m_flags=0xffffffff;regs.host.debug=true;regs.m_pc=255;
 assert(regs.program_control_r()==0x00fd00ff); // reserved/write-only bits do not read back
 regs.m_paused=true;assert(regs.program_control_r()==0x00fc00ff);
 assert(regs.m_flags==0xffffffff); // paused readback must not clear the EX latch
 scudsp_cpu_device fifo;bool available=false;fifo.m_dma_ready_cb=[&](u32,bool){return available;};
 fifo.dma_tick_cb();assert(fifo.moved==0 && fifo.m_dma.count==0 && fifo.storage.left.value==1);
 assert(fifo.dma_finish().value==2 && fifo.moved==0);
 available=true;fifo.dma_tick_cb();assert(fifo.moved==1 && fifo.m_dma.count==1);fifo.dma_tick_cb();assert(!fifo.busy);
 scudsp_cpu_device idle;idle.m_dma_state=idle.DMA_STATE_IDLE;assert(idle.dma_finish().value==0);
}
'''
fixture=fixture.replace('// METHODS',extract('dma_tick_cb')+'\n'+extract('dma_finish')+'\n'+extract('dma_resume')+'\n'+extract('program_control_r')+'\n'+extract('compute_condition')+'\n'+extract('dma_conflict'))
with tempfile.TemporaryDirectory(prefix='scudsp-dma-wait-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)
print('SCU DSP final-beat, sequential-transfer and host-wait checks passed (ASan/UBSan)')

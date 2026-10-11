#!/usr/bin/env python3
# license:BSD-3-Clause
"""Verify actual DSP bus cost and independent CPU halt methods with sanitizers."""
from pathlib import Path
import subprocess,tempfile
from saturn_vdp_wip_test import method
root=Path(__file__).resolve().parent.parent
scu=(root/'src/mame/sega/saturn_scu.cpp').read_text()
state=(root/'src/mame/sega/saturn.cpp').read_text()
bus=(root/'src/mame/sega/saturn_bus.cpp').read_text()
def extract(source,cls,name):
 return method(source.replace(cls+'::','saturn_vdp1_device::'),name).replace('saturn_vdp1_device::',cls+'::')
fixture=r'''
#include <cassert>
#include <functional>
#include <algorithm>
#include <cstdint>
#define BIT(x,n) (((x)>>(n))&1)
using u64=uint64_t;using u32=uint32_t;using offs_t=uint32_t;
struct attotime {int64_t n=0;static const attotime zero,never;static attotime from_ticks(int n,int){return {n};}attotime& operator+=(attotime b){n+=b.n;return *this;}attotime operator+(attotime b){return {n+b.n};}bool operator<(attotime b)const{return n<b.n;}};
const attotime attotime::zero{};
const attotime attotime::never{999999};
struct timer {attotime left{};void adjust(attotime a){left=a;}};
struct host {uint16_t read_word(u32,uint16_t){return 0x1234;}void write_word(u32,uint16_t,uint16_t){}attotime cycles_to_attotime(int n){return {n};}};
struct saturn_scu_device {
 struct dma_channel_t {int32_t pending_read=0;unsigned src_add=0,dst_add=0,start_factor=0,mode=0;bool enable_mask=false,done=false,bbus_sound_access=false,cbus=false,read_buffer_valid=false;};
 enum {DMA_EVENT_TRIGGER=7,DMA_MODE_RESET=0};dma_channel_t m_dma[3]{};
 u32 m_ism=0,m_ist=0,m_abus_ack_pending=0,m_aref=0,m_dma_status=0,m_current_irq_level=0,m_timer0_counter=0;
 bool m_aiack=false,m_rsel=false,m_cpu_halt=false,m_tenb=false,m_t1md=false,m_t1_sync=false;
 timer tick,timer1;timer *m_dma_tick_timer=&tick,*m_timer1=&timer1;
 std::function<void(int)>m_main_dtack_cb=[](int){};
 void device_reset();
 int32_t m_dma_cost=0,m_dsp_dma_cost=0;unsigned m_dma_sdram_reads=0;u32 m_asr[2]{};int m_dma_clock_ref=1;
 attotime m_dma_extra{},m_dsp_dma_extra{};host h,*m_hostspace=&h,*m_hostcpu=&h;
 std::function<attotime(bool)> m_scsp_wait_cb;int cbus=0;void m_cbus_cycle_cb(u32,int){++cbus;}int m_vdp2_penalty_cb(int){return 7;}
 int dma_read_cost(u32,unsigned);void dma_write_cost(dma_channel_t&,u32,unsigned);
 uint16_t scudsp_dma_r(offs_t,uint16_t);void scudsp_dma_w(offs_t,uint16_t,uint16_t);attotime scudsp_dma_wait();
};
#define ASSERT_LINE 1
#define CLEAR_LINE 0
#define INPUT_LINE_HALT 0
struct cpu {attotime cycles_to_attotime(int n){return {2*n};}int attotime_to_cycles(attotime a){return a.n/2;}int halted=0;void set_input_line(int,int s){halted=s;}};
struct scsp {attotime duration{};attotime dma_access_wait(bool){return duration;}};
struct saturn_state {scsp chip,*m_scsp=&chip;unsigned sound_dma_wait(bool);bool m_system_halt=false,m_scu_halt=false;cpu a,b,c,*m_maincpu=&a,*m_slave=&b,*m_audiocpu=&c;void update_cpu_halt();void scu_halt_w(int);void system_halt_w(int);};
// METHODS
int main(){
 saturn_scu_device d;d.scudsp_dma_r(0x05a00000,0xffff);d.scudsp_dma_r(0x05a00002,0xffff);assert(d.scudsp_dma_wait().n==26);assert(d.scudsp_dma_wait().n==0);
 d.m_dma_cost=99;d.m_dma_extra={17};d.scudsp_dma_w(0x05a00000,1,0xffff);d.scudsp_dma_w(0x05a00002,2,0xffff);assert(d.scudsp_dma_wait().n==26);assert(d.m_dma_cost==99&&d.m_dma_extra.n==17);
 d.scudsp_dma_w(0x05e00000,1,0xffff);d.scudsp_dma_w(0x05e00002,2,0xffff);assert(d.scudsp_dma_wait().n==16);assert(d.m_dma_cost==99&&d.m_dma_extra.n==17);
 d.scudsp_dma_r(0x02000000,0xffff);d.scudsp_dma_r(0x02000002,0xffff);assert(d.scudsp_dma_wait().n==10);
 d.m_dma_sdram_reads=60;d.scudsp_dma_r(0x06000000,0xffff);d.scudsp_dma_r(0x06000002,0xffff);assert(d.scudsp_dma_wait().n==6&&d.m_dma_sdram_reads==0&&d.cbus==2);
 d.m_scsp_wait_cb=[](bool registers){return attotime{registers?3:5};};d.scudsp_dma_r(0x05a00000,0xffff);assert(d.scudsp_dma_wait().n==31&&d.m_dma_extra.n==17);d.scudsp_dma_w(0x05b00000,1,0xffff);assert(d.scudsp_dma_wait().n==16&&d.m_dma_extra.n==17);
 saturn_state s;assert(s.sound_dma_wait(false)==1);s.chip.duration={1};assert(s.sound_dma_wait(false)==2);s.chip.duration={4};assert(s.sound_dma_wait(true)==3);s.scu_halt_w(1);assert(s.a.halted&&s.b.halted&&!s.c.halted);s.system_halt_w(1);s.scu_halt_w(0);assert(s.a.halted&&s.b.halted&&s.c.halted);s.scu_halt_w(1);s.system_halt_w(0);assert(s.a.halted&&s.b.halted&&!s.c.halted);s.scu_halt_w(0);assert(!s.a.halted&&!s.b.halted&&!s.c.halted);
 // A device reset must release a previously asserted SCU hold at its owner,
 // not merely forget the internal state. The independent SMPC hold remains.
 d.m_main_dtack_cb=[&](int state){s.scu_halt_w(state);};
 s.scu_halt_w(1);d.m_cpu_halt=true;d.device_reset();
 assert(!s.m_scu_halt&&!s.a.halted&&!s.b.halted&&!s.c.halted);
 s.system_halt_w(1);s.scu_halt_w(1);d.m_cpu_halt=true;d.device_reset();
 assert(!s.m_scu_halt&&s.m_system_halt&&s.a.halted&&s.b.halted&&s.c.halted);
}
'''
methods=[extract(scu,'saturn_scu_device',n) for n in ('dma_read_cost','dma_write_cost','scudsp_dma_r','scudsp_dma_w','scudsp_dma_wait','device_reset')]
methods += [extract(state,'saturn_state','sound_dma_wait')]
methods += [extract(bus,'saturn_state',n) for n in ('update_cpu_halt','scu_halt_w','system_halt_w')]
with tempfile.TemporaryDirectory(prefix='saturn-dsp-cost-') as td:
 out=Path(td);(out/'test.cpp').write_text(fixture.replace('// METHODS','\n'.join(methods)))
 subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)
print('DSP bus costs and independent CPU halt ownership PASS (ASan/UBSan)')

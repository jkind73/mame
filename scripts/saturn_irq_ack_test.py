#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check actual SCU acknowledgement/queued interrupt methods under ASan/UBSan."""
from pathlib import Path
import subprocess,tempfile
from saturn_vdp_wip_test import method
root=Path(__file__).resolve().parent.parent
source=(root/'src/mame/sega/saturn_scu.cpp').read_text().replace('IRQ_CALLBACK_MEMBER(saturn_scu_device::irq_ack_cb)','int saturn_scu_device::irq_ack_cb(int irqline)')
def extract(name):
 return method(source.replace('saturn_scu_device::','saturn_vdp1_device::'),name).replace('saturn_vdp1_device::','saturn_scu_device::')
fixture=r'''
#include <cassert>
#include <bit>
#include <cstdint>
using u16=uint16_t;using offs_t=unsigned;
#define BIT(x,n) (((x)>>(n))&1)
#define HOLD_LINE 2
#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))
#define LOGMASKED(...)
struct attotime {static constexpr int zero=0;};
struct timer {bool pending=false;void adjust(int){pending=true;}};
struct cpu {int level=0,calls=0;void set_input_line(int l,int){level=l;++calls;}};
struct saturn_scu_device {
 uint32_t m_ism=0xbfff,m_ist=0;u16 m_abus_ack_pending=0;int m_current_irq_level=0,m_current_vector=0;
 cpu host,*m_hostcpu=&host;timer dispatcher,*m_irq_dispatch_timer=&dispatcher;
 void irq_mask_w(offs_t,uint32_t,uint32_t);void irq_status_w(offs_t,uint32_t,uint32_t);
 void test_pending_irqs();int irq_ack_cb(int);
};
// METHODS
int main(){
 saturn_scu_device d;
 d.m_ist=0xc0;d.test_pending_irqs();assert(d.host.calls==0 && d.m_ist==0xc0);
 d.irq_mask_w(0,0xffffff3f,~0U);assert(d.m_ism==0xbf3f && d.host.level==9 && d.m_current_vector==0x46 && d.m_ist==0x80);
 // IMS 0->1 changes masking, not the vector-fetch acknowledgement latch.
 d.irq_mask_w(0,0x40,0x40);assert(d.m_current_vector==0x46 && d.m_current_irq_level==9 && d.m_ist==0x80);
 assert(d.irq_ack_cb(9)==0x46 && d.dispatcher.pending && d.m_current_irq_level==0);
 d.test_pending_irqs();assert(d.m_current_vector==0x47 && d.host.level==8 && d.m_ist==0);
 assert(d.irq_ack_cb(8)==0x47);d.test_pending_irqs();assert(d.m_current_irq_level==0 && d.host.calls==2);
 d.m_ist=0x1280;d.irq_mask_w(0,0xbfff,~0U);d.irq_status_w(0,0xff7f,0xff);
 assert(d.m_ist==0x1200);d.irq_status_w(0,0xffffefff,0xff00);assert(d.m_ist==0x200);
 d.m_ist=1U<<16;d.irq_mask_w(0,0x3fff,0xffff);assert(d.m_current_vector==0x50 && d.m_abus_ack_pending==1 && d.m_ist==0);
 d.irq_ack_cb(7);d.m_ist=1U<<16;d.test_pending_irqs();assert(d.m_current_irq_level==0 && d.m_ist==(1U<<16));
}
'''
fixture=fixture.replace('// METHODS','\n'.join(extract(n) for n in ('irq_mask_w','irq_status_w','test_pending_irqs','irq_ack_cb')))
with tempfile.TemporaryDirectory(prefix='saturn-irq-ack-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('SCU_IRQ_ACK_PASS masking, IST clearing, vector fetch, queue and external acknowledge')

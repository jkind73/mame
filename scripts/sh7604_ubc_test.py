#!/usr/bin/env python3
# license:BSD-3-Clause
"""Sanitizer fixture for the actual chapter-6 UBC comparator and register methods."""
from pathlib import Path
import subprocess
import tempfile
from sh7604_sci_standby_test import extract
PREAMBLE=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iterator>
#include <iostream>
using offs_t=unsigned;
constexpr uint32_t SH_I=0xf0;
#define BIT(v,n) (((v)>>(n))&1)
struct sh2_device {bool instruction_before(uint32_t,uint16_t){return true;}};
struct sh7604_device:sh2_device {
 uint16_t m_ubc[32]{},m_ubc_live[32]{},m_ubc_fetch[32]{};
 uint32_t m_ubc_previous_pc=0xffffffff;
 bool m_standby=false,m_ubc_inhibit=false,m_ubc_fetch_sequence=false;
 struct cpu_state {uint32_t pc=0,sr=0,m_delay=0;bool pending_nmi=false;} state,*m_sh2_state=&state;
 uint32_t exception_pc=0;
 void sh2_exception_internal(const char*,int level,int vector){assert(level==15 && vector==12);exception_pc=state.pc;state.pc=0x8000;state.sr=SH_I;}
 int64_t now=0,m_ubc_ready=0;
 bool m_ubc_dirty=false,m_ubc_pending=false,m_ubc_sequence=false;
 int m_sci_dma_access=-1;uint8_t m_instruction_monitor=0;
 bool debug=false,m_isdrc=false;unsigned m_bus_pending=0;int irq_checks=0;
 struct machine_type {bool debug;bool side_effects_disabled(){return debug;}};
 machine_type machine(){return {debug};}
 int64_t local_time(){return now;}int64_t cycles_to_attotime(int n){return n;}
 void sh2_recalc_irq(){irq_checks++;}
 // DECLARATIONS
 void put(unsigned off,uint16_t data){ubc_w(off,data,0xffff);ubc_r(off,0xffff);std::copy(std::begin(m_ubc_live),std::end(m_ubc_live),std::begin(m_ubc_fetch));}
 void address(unsigned off,uint32_t data){put(off,data>>16);put(off+1,data);}
};
'''
MAIN=r'''
int main(){
 sh7604_device d;
 d.address(0,0x1003);d.put(4,0x64);d.put(28,0x1000);
 assert(d.ubc_compare(0x1000,0,4,false,false,false,false,false));
 assert(d.m_ubc[28]==0x9000 && d.m_ubc_pending);
 d.put(28,0);d.m_ubc_pending=false;
 assert(!d.ubc_compare(0x1000,0,4,false,false,false,false,false));
 assert(d.ubc_compare(0x1003,0,1,false,false,false,false,false));
 assert(d.m_ubc[28]==0); // compatible mode has no match flags
 d.put(4,0);d.address(16,0x2000);d.put(20,0xa9);
 d.address(24,0x7878);d.address(26,0x0f0f);d.put(28,0x1008);
 assert(d.ubc_compare(0x2000,0x7b,1,true,false,true,false,false));
 assert(d.m_ubc[28]==0x1048);
 assert(!d.ubc_compare(0x2000,0x6b,1,true,false,true,false,false));
 assert(!d.ubc_compare(0x2000,0x7b,2,true,false,true,false,false));
 d.put(28,0x3008);
 assert(d.ubc_compare(0x2000,0,4,true,false,true,true,false)); // external ignores size/data
 d.put(28,0x1008);
 assert(!d.ubc_compare(0x2000,0,4,true,false,true,true,false));
 // A/B simultaneous cannot advance both sequence stages.
 d.address(0,0x3000);d.address(16,0x3000);d.put(4,0x56);d.put(20,0x56);d.put(28,0x1010);
 assert(!d.ubc_compare(0x3000,0,2,false,true,false,false,false));
 assert(d.m_ubc_sequence && d.m_ubc[28]==0x9010);
 assert(d.ubc_compare(0x3000,0,2,false,true,false,false,false));
 d.put(28,0x1010);assert(!d.m_ubc_sequence);
 // Latency and dummy-read synchronization, including side-effect-free debugger reads.
 d.ubc_w(0,0x1234,0xffff);assert(d.m_ubc_live[0]==0);
 d.debug=true;assert(d.ubc_r(0,0xffff)==0x1234 && d.m_ubc_dirty);
 d.debug=false;d.ubc_r(0,0xffff);assert(d.m_ubc_live[0]==0x1234);
 d.ubc_w(0,0xabcd,0xff00);assert(d.m_ubc[0]==0x1234);
 d.m_sci_dma_access=0;d.ubc_w(0,0xabcd,0xffff);assert(d.ubc_r(0,0xffff)==0);
 assert(d.m_ubc[0]==0x1234);d.m_sci_dma_access=-1;
 d.put(4,0xffff);assert(d.m_ubc[4]==0xff);
 d.put(28,0xffff);assert(d.m_ubc[28]==0xf4dc);
 // External pin cycles obey EBBE and stop with the UBC clock in standby.
 sh7604_device e;e.address(0,0x5000);e.put(4,0xa9);e.put(28,0x3000);
 e.m_standby=true;e.ubc_external_cycle(0x5000,true);assert(!e.m_ubc_pending && e.m_ubc[28]==0x3000);
 e.m_standby=false;e.ubc_external_cycle(0x5000,true);assert(e.m_ubc_pending && e.m_ubc[28]==0x7000);
 e.state.pending_nmi=true;e.ubc_accept();assert(e.m_ubc_pending);
 e.state.pending_nmi=false;e.ubc_accept();assert(!e.m_ubc_pending && e.exception_pc==0);
 // A changed condition cannot cancel a match in the already fetched second halfword.
 sh7604_device p;p.address(0,0x1002);p.put(4,0x56);p.put(28,0x1000);
 p.state.pc=0x1000;assert(p.instruction_before(0x1000,9));
 p.ubc_w(4,0,0xffff);p.ubc_r(4,0xffff);
 p.state.pc=0x1002;assert(!p.instruction_before(0x1002,9));assert(p.exception_pc==0x1002);
 // Unsynchronized writes become active after three clocks, not immediately.
 sh7604_device q;q.address(0,0x2000);q.put(4,0);q.put(28,0x1000);
 q.ubc_w(4,0x65,0xffff);q.now=2;
 assert(!q.ubc_compare(0x2000,0,1,false,false,false,false,false));
 q.now=3;assert(q.ubc_compare(0x2000,0,1,false,false,false,false,false));
 std::cout<<"SH7604 UBC actual-method ASan/UBSan PASS\n";
}
'''
def main():
 source=Path('src/devices/cpu/sh/sh7604.cpp').read_text()
 methods=[extract(source,n) for n in ('ubc_r','ubc_w','ubc_commit','ubc_compare','ubc_accept','instruction_before','instruction_after','ubc_external_cycle')]
 declarations='\n'.join(m.split('{',1)[0].replace('sh7604_device::','').strip()+';' for m in methods)
 declarations=declarations.replace('bool external, bool after)', 'bool external = false, bool after = false)')
 with tempfile.TemporaryDirectory(prefix='sh7604-ubc-') as tmp:
  cpp=Path(tmp)/'fixture.cpp';binary=Path(tmp)/'fixture'
  cpp.write_text(PREAMBLE.replace('// DECLARATIONS',declarations)+'\n'+'\n'.join(methods)+MAIN)
  subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g',str(cpp),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)
if __name__=='__main__':main()

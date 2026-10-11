#!/usr/bin/env python3
# license:BSD-3-Clause
"""ASan/UBSan fixture of the real BSC refresh methods, with an independent tick oracle."""
from pathlib import Path
import subprocess
import tempfile
from sh7604_register_test import method

PREAMBLE = r'''
#include <cassert>
#include <cstdint>
#include <algorithm>
#include <iostream>
using offs_t=unsigned;
#define BIT(v,n) (((v)>>(n))&1)
#define TIMER_CALLBACK_MEMBER(n) void n(int param)
#define HZ_TO_ATTOSECONDS(f) (1000000000000000000LL/(f))
struct attotime {
    __int128 v=0;
    static const attotime zero,never;
    static attotime from_ticks(uint64_t c,unsigned f){return {__int128(c)*HZ_TO_ATTOSECONDS(f)};}
    int64_t seconds()const{return v/1000000000000000000LL;}
    int64_t attoseconds()const{return v%1000000000000000000LL;}
    attotime& operator+=(attotime b){v+=b.v;return *this;}
    friend attotime operator+(attotime a,attotime b){return {a.v+b.v};}
    friend attotime operator-(attotime a,attotime b){return {a.v-b.v};}
    friend bool operator<(attotime a,attotime b){return a.v<b.v;}
    friend bool operator<=(attotime a,attotime b){return a.v<=b.v;}
};
const attotime attotime::zero{0},attotime::never{__int128(1)<<100};
struct sh7604_device {
    unsigned m_refresh_phase=0,m_refresh_clockrate=1024,hz=1024;
    uint32_t m_rtcsr=0,m_rtcnt=0,m_rtcor=0;
    bool m_standby=false,m_rtcsr_cmf_read=false,debug=false;
    attotime now{},m_refresh_epoch{};
    struct timer{attotime delay;void adjust(attotime t){delay=t;}} t,*m_refresh_timer=&t;
    struct mach {sh7604_device& d;attotime time(){return d.now;}bool side_effects_disabled(){return d.debug;}};
    mach machine(){return {*this};} bool running=false,m_isdrc=false;unsigned m_bus_pending=0;
    bool executing(){return running;}attotime cycles_to_attotime(unsigned c){return attotime::from_ticks(c,hz);}
    attotime local_time(){return now;}unsigned clock(){return hz;}
    unsigned irq_updates=0;void sh2_recalc_irq(){++irq_updates;}
    void advance(uint64_t cycles){now+=attotime::from_ticks(cycles,hz);refresh_resync();}
    // DECLARATIONS
};
'''
MAIN = r'''
int main(){
    const unsigned divs[]={0,4,16,64,256,1024,2048,4096};
    uint32_t random=1234567;
    for(unsigned select=1;select<8;++select){
        for(unsigned trial=0;trial<1000;++trial){
            sh7604_device d; random=random*1664525+1013904223;
            d.m_rtcsr=select*8;d.m_rtcnt=(random>>8)&255;d.m_rtcor=(random>>16)&255;
            unsigned counter=d.m_rtcnt,constant=d.m_rtcor,phase=0;bool flag=false;
            for(unsigned step=0;step<10;++step){
                random=random*1664525+1013904223;unsigned cycles=random%10000;
                for(unsigned c=0;c<cycles;++c){
                    if(++phase==divs[select]){phase=0;counter=(counter+1)&255;if(counter==constant){counter=0;flag=true;}}
                }
                d.advance(cycles);
                assert(d.m_rtcnt==counter && d.m_refresh_phase==phase);
                assert(bool(d.m_rtcsr&128)==flag);
            }
        }
    }
    sh7604_device d;d.m_rtcor=5;d.rtcsr_w(0,0xa55a0048,~0U);
    assert(d.t.delay.v==attotime::from_ticks(20,d.hz).v);
    d.advance(3);d.refresh_activate();assert(d.m_refresh_phase==3);
    assert(d.t.delay.v==attotime::from_ticks(17,d.hz).v);
    d.advance(17);d.refresh_tick(0);assert(d.m_rtcnt==0 && (d.m_rtcsr&128));
    assert(d.t.delay.v==attotime::never.v);
    d.rtcsr_w(0,0xa55a0048,~0U);assert(d.m_rtcsr&128);
    d.debug=true;d.rtcsr_r();d.debug=false;d.rtcsr_w(0,0xa55a0048,~0U);assert(d.m_rtcsr&128);
    d.rtcsr_r();d.rtcsr_w(0,0xa55a0048,~0U);assert(!(d.m_rtcsr&128));
    d.advance(2);d.m_standby=true;d.refresh_activate();assert(d.t.delay.v==attotime::never.v);
    auto count=d.m_rtcnt;auto phase=d.m_refresh_phase;d.advance(1000);
    assert(d.m_rtcnt==count && d.m_refresh_phase==phase);
    d.m_standby=false;d.refresh_activate();d.advance(18);assert(d.m_rtcsr&128);
    d.rtcsr_r();d.rtcsr_w(0,0xa55a0000,~0U);d.advance(1000);assert(d.m_rtcnt==0);
    // An invalid write must not reset/rephase a running counter.
    d.rtcsr_w(0,0xa55a0038,~0U);d.advance(100);auto epoch=d.m_refresh_epoch.v;
    d.rtcnt_w(0,0xa55a0055,0xffff);d.rtcor_w(0,0x00550055,~0U);
    assert(d.m_rtcnt==0 && d.m_rtcor==5 && d.m_refresh_epoch.v==epoch);
    // A DRC register access sees elapsed sequence cycles before icount commit.
    sh7604_device drc,interpreter;
    drc.m_rtcsr=interpreter.m_rtcsr=8;drc.m_rtcor=interpreter.m_rtcor=10;
    drc.running=true;drc.m_isdrc=true;drc.m_bus_pending=39;
    interpreter.now=attotime::from_ticks(39,interpreter.hz);
    drc.refresh_resync();interpreter.refresh_resync();
    assert(drc.m_rtcnt==9 && drc.m_refresh_phase==3);
    assert(drc.m_rtcnt==interpreter.m_rtcnt && drc.m_refresh_phase==interpreter.m_refresh_phase);
    drc.m_bus_pending=40;interpreter.now=attotime::from_ticks(40,interpreter.hz);
    drc.refresh_resync();interpreter.refresh_resync();
    assert(drc.m_rtcnt==0 && (drc.m_rtcsr&128));
    assert(drc.m_rtcnt==interpreter.m_rtcnt && drc.m_rtcsr==interpreter.m_rtcsr);
    // Committing those cycles must not count them again.
    drc.running=false;drc.m_bus_pending=0;drc.now=attotime::from_ticks(40,drc.hz);
    drc.refresh_resync();assert(drc.m_rtcnt==0 && drc.m_refresh_phase==0);
    std::cout<<"SH7604 refresh actual-method ASan/UBSan PASS (7000 independent tick traces)\n";
}
'''

def main():
    source=Path('src/devices/cpu/sh/sh7604.cpp').read_text().replace('TIMER_CALLBACK_MEMBER(sh7604_device::refresh_tick)', 'void sh7604_device::refresh_tick(int param)')
    names=['refresh_resync','refresh_activate','refresh_tick','rtcsr_r','rtcsr_w','rtcnt_r','rtcnt_w','rtcor_r','rtcor_w']
    methods=[method(source,n) for n in names]
    declarations='\n'.join(m.split('{',1)[0].replace('sh7604_device::','').strip()+';' for m in methods)
    with tempfile.TemporaryDirectory(prefix='sh7604-refresh-') as tmp:
        path=Path(tmp);cpp=path/'test.cpp';binary=path/'test'
        cpp.write_text(PREAMBLE.replace('// DECLARATIONS',declarations)+'\n'+'\n'.join(methods)+MAIN)
        subprocess.run(['clang++','-std=c++17','-O1','-fsanitize=address,undefined',str(cpp),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
if __name__=='__main__':main()

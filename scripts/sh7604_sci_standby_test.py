#!/usr/bin/env python3
# license:BSD-3-Clause
"""ASan/UBSan tests of the actual SCI handshake and standby transition methods.

Scheduling and CPU execution are covered separately by sh7604_power_test.lua.
Only framework/serial-boundary dependencies are mocked here.
"""
from pathlib import Path
import re
import subprocess
import tempfile

PREAMBLE = r'''
#include <cassert>
#include <cstdint>
static uint16_t swapendian_int16(uint16_t x){return __builtin_bswap16(x);}
static uint32_t swapendian_int32(uint32_t x){return __builtin_bswap32(x);}
#include <vector>
#include <functional>
#include <algorithm>
#include <unordered_map>
#include <stdexcept>
#include <iostream>
using offs_t = unsigned; using u32 = uint32_t;
#define LOG(...) ((void)0)
#define BIT(v,n) (((v) >> (n)) & 1)
#define TIMER_CALLBACK_MEMBER(name) void name(int param)
constexpr int INPUT_LINE_NMI=16, CLEAR_LINE=0, ASSERT_LINE=1;
constexpr int SUSPEND_REASON_HALT=1, SUSPEND_REASON_CLOCK=64,SUSPEND_REASON_DMA=128;
static constexpr int wdtclk_tab[8]={1,6,7,8,9,10,12,13};
struct attotime {
    int64_t v=0;
    attotime()=default; attotime(int64_t a):v(a){}
    static const attotime never,zero;
    bool is_never()const{return v==-1;}
    friend attotime operator+(attotime a,attotime b) {return a.v+b.v;}
    friend attotime operator-(attotime a,attotime b) {return a.v-b.v;}
    friend attotime operator*(attotime a,unsigned n){return a.v*n;}
    friend attotime operator/(attotime a,unsigned n){return a.v/n;}
    friend bool operator>=(attotime a,attotime b) {return a.v>=b.v;}
};
const attotime attotime::never(-1),attotime::zero(0);
bool operator==(attotime a,attotime b){return a.v==b.v;}
bool operator<(attotime a,attotime b){return a.v<b.v;}
bool operator<=(attotime a,attotime b){return a.v<=b.v;}
bool operator>(attotime a,attotime b){return a.v>b.v;}
attotime& operator+=(attotime&a,attotime b){a.v+=b.v;return a;}

struct timer { attotime expiry=attotime::never; bool active=false; bool enabled(){return active;} attotime expire(){return expiry;} void adjust(attotime a,int=0){expiry=a;active=true;} attotime remaining(){return expiry;} };
struct sh2_device {
    int assertions=0;
    void device_clock_changed(){}
    void execute_set_input(int n,int s){if(n==16 && s==1) assertions++;}
};
struct sh7604_device:sh2_device {
    uint8_t m_smr=0,m_brr=0xff,m_scr=0,m_tdr=0xff,m_ssr=0x84;
    uint8_t m_rdr=0,m_tsr=0,m_ssr_read=0,m_sbycr=0;
    uint32_t m_tx_frame=0;
    uint8_t m_tx_bit=0,m_tx_bits=0,m_tx_stop=0,m_tx_format=0,m_tx_data=0,m_tx_mpbt=0,m_tx_ext_count=0;
    bool m_tx_prefetched=false,m_rx_busy=false;
    uint8_t m_rsr=0,m_rx_stage=0,m_rx_format=0,m_rx_parity=0,m_rx_errors=0,m_rx_mp=0,m_rx_ext_count=0;
    int m_sci_rxd=1,m_sci_sck_in=1,m_sci_txd_level=1,m_sci_sck_level=1;
    std::function<void(int)> on_txd,on_sck;
    std::vector<int> txd,sck;
    void m_sci_txd(int v){txd.push_back(v);if(on_txd)on_txd(v);}
    void m_sci_sck(int v){sck.push_back(v);if(on_sck)on_sck(v);}
    bool m_ubc_pending=false;
    bool ubc_compare(uint32_t,uint32_t,unsigned,bool,bool,bool){return false;}
    bool m_clock_pause=false; int hiz=0,ack=1;
    void m_standby_hiz(int v){hiz=v;} void m_ckpack(int v){ack=v;}
    bool m_sci_busy=false, m_standby=false,m_standby_waking=false,m_nmie=false,m_divu_busy=false;
    int m_sci_dma_access=-1,m_nmi_pin=0;
    uint8_t m_wtcnt=0,m_wtcsr=0,m_rstcsr=0,m_dmaor=0,m_dmaor_read_flags=0;
    uint8_t m_frt_temp=0;
    uint8_t m_tier=1,m_ftcsr=0,m_ftcsr_read_flags=0,m_frc_tcr=0,m_tocr=0xe0;
    uint16_t m_frc=0,m_ocra=0xffff,m_ocrb=0xffff,m_frc_icr=0;
    uint64_t m_frc_base=0,cycles=0;
    bool m_dma_te_read[2]{};
    struct {uint32_t chcr=0,sar=0,dar=0,tcr=0; uint8_t drcr=0;} m_dmac[2];
    uint32_t m_am=0xc7ffffff;
    int m_dma_timer_active[2]{},m_active_dma_incs[2]{},m_active_dma_incd[2]{},m_active_dma_size[2]{},m_active_dma_steal[2]{};
    uint32_t m_active_dma_src[2]{},m_active_dma_dst[2]{},m_active_dma_count[2]{};
    timer dma[2]; timer *m_dma_current_active_timer[2]={&dma[0],&dma[1]};
    struct cb {bool bound=false;std::function<uint32_t(uint32_t,uint32_t,uint32_t,int)> fn;bool isnull()const{return !bound;} uint32_t operator()(uint32_t a,uint32_t b,uint32_t v,int n)const{return fn?fn(a,b,v,n):v;}} m_dma_kludge_cb,m_dma_fifo_data_available_cb;
    std::unordered_map<uint32_t,uint8_t> bytes;
    struct program {
        sh7604_device &d;
        uint8_t read_byte(uint32_t a){return a==0xfffffe05 ? d.rdr_r() : d.bytes[a];}
        void write_byte(uint32_t a,uint8_t v){if(a==0xfffffe03) d.tdr_w(v); else d.bytes[a]=v;}
        uint16_t read_word(uint32_t a){return (read_byte(a)<<8)|read_byte(a+1);}
        uint32_t read_dword(uint32_t a){return (uint32_t(read_word(a))<<16)|read_word(a+2);}
        void write_word(uint32_t a,uint16_t v){write_byte(a,v>>8);write_byte(a+1,v);}
        void write_dword(uint32_t a,uint32_t v){write_word(a,v>>16);write_word(a+2,v);}
    } memory{*this}, *m_program=&memory;
    bool m_bus_observed=false,m_bus_timed=false;
    void m_bus_observer(uint32_t,unsigned,bool,bool){}
    int m_bus_timing(uint32_t,unsigned,bool,bool,attotime,bool){return 0;}
    bool m_instruction_monitor=false; uint32_t m_bus_endian_width=0, m_bcr1=0,m_bcr2=0xfc,m_mcr=0;
    struct dma_cb {
        bool isunset()const{return true;}
        void operator()(int){} void operator()(unsigned,uint32_t,uint32_t){}
        uint32_t operator()(unsigned,uint32_t){return 0xffffffff;}
    } m_dma_dack[2],m_dma_read[2],m_dma_write[2];
    int m_dma_dreq[2]{1,1},m_dma_dack_level[2]{1,1};
    bool m_dma_dreq_driven[2]{},m_dma_edge[2]{},m_dma_edge_burst[2]{},m_dma_ack_high[2]{};
    unsigned m_dma_requests[2]{},m_dma_ack_count[2]{};
    uint32_t m_dma_io_data[2]{0xffffffff,0xffffffff};
    attotime m_dma_ready[2]{},m_dma_detect_after[2]{},m_dma_ack_start[2][16]{},m_dma_ack_end[2][16]{};
    timer ack_timer[2];timer *m_dma_dack_timer[2]{&ack_timer[0],&ack_timer[1]};
    int m_dma_owner=-1;unsigned m_dma_priority=0,m_dma_step=0,m_dma_step_count=0,m_dma_count_delta=0;
    int m_dma_src_delta=0,m_dma_dst_delta=0;
    uint32_t m_dma_unit_control=0,m_dma_unit_src=0,m_dma_unit_dst=0,m_dma_data[4]{};
    bool m_dma_committed=false,m_dma_cancelled=false,m_dma_staged=false;
    attotime m_dma_bus_end,m_dma_pause_time;
    struct step {uint32_t address=0;unsigned bytes=0,word=0,shift=0;bool write=false;attotime start,end;}m_dma_steps[32];

    void fatalerror(const char*){throw std::runtime_error("unsupported mode");}
    timer sci,rx,serial_clock,frt,wdt,div,standby,capture;timer *m_frt_capture_timer=&capture;
    timer *m_sci_rx_timer=&rx,*m_sci_clock_timer=&serial_clock;
    timer *m_sci_timer=&sci,*m_timer=&frt,*m_wdtimer=&wdt,*m_divu_timer=&div,*m_standby_timer=&standby;
    attotime m_standby_entry;
    int64_t now=0; bool debug=false; int checks[2]{},irq_checks=0; unsigned suspend_flags=0;
    struct machine_stub {int64_t now; bool debug; attotime time(){return now;} bool side_effects_disabled(){return debug;}};
    machine_stub machine()const{return {now,debug};}
    attotime local_time(){return now;}
    attotime cycles_to_attotime(uint64_t c){return c;}
    uint64_t total_cycles(){return cycles;}
    bool suspended(unsigned reasons)const{return (suspend_flags&reasons)!=0;}
    void suspend(int n,bool){suspend_flags|=n;} void resume(int n){suspend_flags&=~n;}
    bool m_divu_ovf=false,m_divu_ovfie=false;
    struct {int sci=0,divu=0,dmac=0,wdt=0,frc=0;} m_irq_level;
    struct {int divu=0,dmac[2]{},fic=0,foc=0,fov=0;} m_irq_vector;
    void refresh_resync() {} void refresh_activate() {}
    timer *m_refresh_timer=nullptr;uint32_t m_refresh_clockrate=1,m_rtcsr=0;attotime m_refresh_epoch=0;
    uint16_t m_vcra=0,m_vcrb=0,m_vcrwdt=0,m_intc_icr=0;
    uint64_t m_frt_icr_read_cycle=~uint64_t(0),m_frt_clear_cycle=~uint64_t(0);attotime m_frt_capture_clock_delay=attotime::never;bool m_frt_capture_pending=false,m_isdrc=false;unsigned m_bus_pending=0;
    bool executing(){return false;}
    int m_frt_input=0,m_frt_output[2]{};uint64_t m_frt_epoch=0;uint32_t m_frt_generation=0,m_frt_clockrate=1;
    uint32_t clock(){return 1;}
    uint64_t frt_cycles(){return cycles;}
    void frt_drive(unsigned c,int v){m_frt_output[c]=v;}
    void m_ftoa(int v){m_frt_output[0]=v;}void m_ftob(int v){m_frt_output[1]=v;}
    struct {int internal_irq_level=0;} state, *m_sh2_state=&state;
    int m_internal_irq_vector=-1,m_test_irq=0;
    static constexpr uint8_t ICF=0x80,OCFA=8,OCFB=4,OVF=2;
    attotime m_module_div_remaining,m_module_dma_remaining[2],m_divu_done;
    void sh2_wtcnt_recalc(){} void sh2_timer_resync(){}
    void sh2_timer_activate(){frt.adjust(m_standby || (m_sbycr&2) ? -1 : 100);}
    std::vector<uint8_t> tx;
    void m_sci_tx(uint8_t data){tx.push_back(data);}
    // DECLARATIONS
};
'''
MAIN = r'''
void tick_tx(sh7604_device &d) {
    assert(d.sci.enabled()); d.now+=d.sci.expiry.v; d.sci.adjust(attotime::never); d.sci_tx_complete(0);
}
void tick_rx(sh7604_device &d) {
    assert(d.rx.enabled()); d.now+=d.rx.expiry.v; d.rx.adjust(attotime::never); d.sci_rx_tick(0);
}
void pulses(sh7604_device &d,unsigned n) {
    for(unsigned i=0;i<n;i++){d.sci_sck_w(0);d.sci_sck_w(1);}
}
void receive(sh7604_device &d,uint8_t value,bool bad_parity=false,bool bad_stop=false,bool mpb=false) {
    unsigned bits=(d.m_smr&0x40)?7:8;
    bool ext=d.m_scr&2;
    d.sci_rxd_w(1); d.sci_rxd_w(0);
    if(ext)pulses(d,8);else tick_rx(d);
    unsigned parity=0;
    for(unsigned bit=0;bit<bits;bit++) {
        int v=BIT(value,bit);parity^=v;d.sci_rxd_w(v);
        if(ext)pulses(d,16);else tick_rx(d);
    }
    if(d.m_smr&0x24) {
        int v=(d.m_smr&4)?mpb:(parity^BIT(d.m_smr,4)^bad_parity);
        d.sci_rxd_w(v);if(ext)pulses(d,16);else tick_rx(d);
    }
    d.sci_rxd_w(!bad_stop);if(ext)pulses(d,16);else tick_rx(d);
    d.sci_rxd_w(1);
}
void drain(sh7604_device &d) {
    for(unsigned n=0;d.m_sci_busy && n<100;n++)tick_tx(d);
    assert(!d.m_sci_busy);
}
int main() {
    sh7604_device d; d.sci_reset();
    d.m_irq_level.sci=5; d.m_vcra=0x0809; d.m_vcrb=0x0a0b;
    d.scr_w(0xa0); assert(d.m_sh2_state->internal_irq_level==5 && d.m_internal_irq_vector==10);
    d.scr_w(0x44); assert(d.m_internal_irq_vector==11);
    d.scr_w(0x50); receive(d,0x22); assert(d.m_internal_irq_vector==9);
    receive(d,0x33); assert(d.m_internal_irq_vector==8 && d.m_rdr==0x22);
    d.sci_reset(); d.sci_update(); assert(d.m_sh2_state->internal_irq_level==0);
    // CPU accesses and debugger reads do not acknowledge/qualify DMA flags.
    d.scr_w(0x30); d.tdr_w(0x11); assert(d.m_ssr==0x84);
    d.debug=true; d.ssr_r(); d.debug=false; d.ssr_w(0); assert(d.m_ssr==0x84);
    d.ssr_r(); d.ssr_w(0); assert(d.m_sci_busy && d.m_tsr==0x11 && d.m_ssr==0x80);
    assert(d.sci.expiry.v==32768); // one bit at BRR=255, 128 clocks/bit
    assert(d.m_sci_txd_level==0);
    d.tdr_w(0x22); d.ssr_r(); d.ssr_w(0); assert(d.m_ssr==0);
    for(int n=0;n<9;n++)tick_tx(d);
    assert(d.m_tx_prefetched && d.m_tsr==0x22 && d.tx.empty()); // preload at stop, not frame end
    drain(d); assert(d.tx.size()==2 && d.tx[0]==0x11 && d.tx[1]==0x22 && d.m_ssr==0x84);
    receive(d,0x53); assert(d.rdr_r()==0x53 && (d.m_ssr&0x40));
    d.m_sci_dma_access=1; assert(d.rdr_r()==0x53 && !(d.m_ssr&0x40)); d.m_sci_dma_access=-1;
    receive(d,0x64); receive(d,0x75); assert((d.m_ssr&0x60)==0x60 && d.rdr_r()==0x64);
    // Both channels require enable plus flag; no CPU mask is used by the request gate.
    d.sci_reset(); d.scr_w(0x30);
    for(int c=0;c<2;c++) {
        d.m_dmac[c].drcr=1; assert(!d.sci_dma_requested(c));
        receive(d,0x86); assert(!d.sci_dma_requested(c));
        d.scr_w(0x70); assert(d.sci_dma_requested(c));
        d.m_sci_dma_access=c; d.rdr_r(); d.m_sci_dma_access=-1; assert(!d.sci_dma_requested(c));
        d.m_dmac[c].drcr=2; assert(!d.sci_dma_requested(c));
        d.scr_w(0xb0); assert(d.sci_dma_requested(c));
        d.m_sci_busy=true; d.m_sci_dma_access=c; d.tdr_w(0xa7); d.m_sci_dma_access=-1;
        assert(!(d.m_ssr&0x84) && !d.sci_dma_requested(c));
        d.scr_w(0x10); assert((d.m_ssr&0x84)==0x84);
        d.m_dmac[c].chcr=0x200; d.m_dmac[c].drcr=3; assert(d.sci_dma_requested(c));
        d.m_dmac[c].chcr=0; assert(!d.sci_dma_requested(c)); d.sci_reset();d.scr_w(0x30);
    }
    // All asynchronous data/parity/stop formats, internal and external receive clocks.
    for(bool ext:{false,true}) for(unsigned format:{0U,0x40U,0x20U,0x30U,0x68U,0x78U}) {
        d.sci_reset();d.m_smr=format;d.scr_w(0x50|(ext?2:0));receive(d,0xa5);
        assert((d.m_ssr&0x78)==0x40 && d.m_rdr==((format&0x40)?0x25:0xa5));
    }
    d.sci_reset(); d.m_smr=0x20; d.scr_w(0x50); receive(d,0x53,true);
    assert((d.m_ssr&0x48)==8 && d.m_rdr==0x53);
    d.ssr_r(); d.ssr_w(0); receive(d,0x64,false,true);
    assert((d.m_ssr&0x50)==0x10 && d.m_rdr==0x64);
    d.sci_reset();d.m_smr=4;d.scr_w(0x58);receive(d,0x11,false,true,false);
    assert((d.m_ssr&0x7a)==0 && (d.m_scr&8)); // MPIE suppresses data and errors
    receive(d,0x22,false,false,true);assert(d.m_rdr==0x22 && (d.m_ssr&0x42)==0x42 && !(d.m_scr&8));
    // External async transmitter: sixteen SCK edges per bit, actual TXD frame.
    d.sci_reset();d.txd.clear();d.scr_w(0x22);d.tdr_w(0xa9);d.ssr_r();d.ssr_w(0);
    assert(d.sci.expire().is_never() && d.m_sci_busy);pulses(d,161);
    assert(d.tx.back()==0xa9 && !d.m_sci_busy && d.m_sci_txd_level==1);
    // Synchronous full duplex: one internal master and one externally clocked peer.
    sh7604_device peer;peer.sci_reset();d.sci_reset(); d.m_smr=peer.m_smr=0x80;d.m_brr=peer.m_brr=1;
    d.on_txd=[&](int v){peer.sci_rxd_w(v);};peer.on_txd=[&](int v){d.sci_rxd_w(v);};
    d.on_sck=[&](int v){peer.sci_sck_w(v);};peer.scr_w(0x32);peer.tdr_w(0x3c);peer.ssr_r();peer.ssr_w(0);
    d.tdr_w(0xa5);d.scr_w(0x20);d.ssr_r();d.ssr_w(0);d.scr_w(0x30);
    for(int n=0;n<16;n++)tick_tx(d);
    assert(d.m_rdr==0x3c && peer.m_rdr==0xa5 && (d.m_ssr&0x40) && (peer.m_ssr&0x40));
    assert(!d.m_sci_busy && !peer.m_sci_busy && d.m_sci_sck_level==1);
    d.on_txd={};d.on_sck={};
    // Actual DMA methods: RX waits between bytes, preserves on-chip source address,
    // acknowledges each receive, updates progress and finishes on both channels.
    d.sci_reset(); d.scr_w(0x70); d.m_dmaor=1;
    for(int c=0;c<2;c++) {
        d.m_dmac[c].chcr=0x4001; d.m_dmac[c].drcr=1;
        d.m_dmac[c].sar=0xfffffe05; d.m_dmac[c].dar=0x20210000; d.m_dmac[c].tcr=2;
        d.sh2_dmac_check(c); assert(d.m_dma_timer_active[c]==0);
        receive(d,0x31); assert(d.m_dma_timer_active[c]==1);
        assert(d.m_active_dma_src[c]==0xfffffe05);
        d.sh2_do_dma(c); assert(d.bytes[0x210000]==0x31 && d.m_dmac[c].tcr==1 && !(d.m_ssr&0x40));
        d.now=d.m_dma_bus_end.v;d.sh2_dma_current_active_callback(c); assert(d.m_dma_timer_active[c]==2 && d.m_dmac[c].tcr==1);
        receive(d,0x42); assert(d.m_dma_timer_active[c]==1);
        d.sh2_do_dma(c); assert(d.bytes[0x210001]==0x42 && d.m_dmac[c].tcr==0);
        d.now=d.m_dma_bus_end.v;d.sh2_dma_current_active_callback(c); assert(d.m_dmac[c].chcr&2);
        assert(d.m_dmac[c].sar==0xfffffe05 && d.m_dmac[c].dar==0x20210002);
        d.m_dmac[c].chcr=0;
    }
    // Existing 32X FIFO adapter: initial enable may see no request at all.
    // A later board notification must start it and a subsequent empty FIFO stall it.
    {
        sh7604_device fifo;bool available=false;
        fifo.m_dma_fifo_data_available_cb.bound=true;
        fifo.m_dma_fifo_data_available_cb.fn=[&](uint32_t a,uint32_t,uint32_t,int){return a==0x4012 && available;};
        fifo.bytes[0x4012]=0x5a;
        fifo.m_dmac[0].sar=0x20004012;fifo.m_dmac[0].dar=0x20210000;
        fifo.m_dmac[0].tcr=2;fifo.m_dmac[0].chcr=0x4001;fifo.m_dmaor=1;
        fifo.sh2_dmac_check(0);assert(fifo.m_dma_timer_active[0]==0);
        available=true;fifo.sh2_notify_dma_data_available();assert(fifo.m_dma_timer_active[0]==1);
        fifo.sh2_do_dma(0);assert(fifo.bytes[0x210000]==0x5a && fifo.m_dmac[0].tcr==1);
        available=false;fifo.now=fifo.m_dma_bus_end.v;fifo.sh2_dma_current_active_callback(0);
        assert(fifo.m_dma_timer_active[0]==2 && fifo.m_dma_owner==-1);
        available=true;fifo.sh2_notify_dma_data_available();assert(fifo.m_dma_timer_active[0]==1);
        fifo.sh2_do_dma(0);fifo.now=fifo.m_dma_bus_end.v;fifo.sh2_dma_current_active_callback(0);
        assert(fifo.bytes[0x210001]==0x5a && (fifo.m_dmac[0].chcr&2));
    }
    // The largest legal unit has 32 memory beats and 16 acknowledge pulses.
    // Instrument the real planner/data path with byte-wide ordinary memory.
    {
        sh7604_device wide;wide.m_bcr2=0x7c;wide.m_dmaor=1;
        wide.m_dmac[0].sar=0x06601000;wide.m_dmac[0].dar=0x06602000;
        wide.m_am=0xffffffff;
        for(unsigned i=0;i<16;i++){wide.bytes[0x06601000+i]=uint8_t(0x80+i);wide.bytes[0x06602000+i]=0;}
        wide.bytes[0x06602010]=0x5a;
        wide.m_dmac[0].tcr=4;wide.m_dmac[0].chcr=0x5f01;
        wide.sh2_dmac_check(0);wide.sh2_do_dma(0);
        assert(wide.m_dma_step_count==32 && wide.m_dma_ack_count[0]==16);
        for(unsigned i=0;i<16;i++)assert(wide.bytes[0x06602000+i]==uint8_t(0x80+i));
        assert(wide.bytes[0x06602010]==0x5a && wide.m_dmac[0].tcr==0);
        wide.now=wide.m_dma_bus_end.v;wide.sh2_dma_current_active_callback(0);
        assert(wide.m_dmac[0].chcr&2);
    }
    // Completing/aborting an internal DMA must never release the external HALT.
    {
        sh7604_device halted;halted.suspend_flags=SUSPEND_REASON_HALT;
        halted.dma_update_halt();assert(halted.suspend_flags==SUSPEND_REASON_HALT);
        halted.m_dma_owner=0;halted.m_active_dma_steal[0]=1;
        halted.dma_update_halt();assert(halted.suspend_flags==(SUSPEND_REASON_HALT|SUSPEND_REASON_DMA));
        halted.m_dma_owner=-1;halted.dma_update_halt();assert(halted.suspend_flags==SUSPEND_REASON_HALT);
    }
    // Sleep does not initialize peripherals. Standby initializes at entry and freezes clocks.
    d.m_sbycr=0; d.m_scr=0x30; d.sleep_enter(0); assert(!d.m_standby && d.m_scr==0x30);
    d.m_sbycr=0xc0; d.m_wtcsr=7; d.m_wtcnt=17; d.m_dmac[0].chcr=0xffff;
    d.suspend_flags=SUSPEND_REASON_DMA; d.now=100; d.sleep_enter(0);
    assert(d.m_standby && d.m_scr==0 && d.m_ssr==0x84 && d.m_brr==0xff);
    assert(d.m_dmac[0].chcr==0 && d.m_wtcsr==7 && d.m_wtcnt==17);
    assert(d.m_ocra==0xffff && d.m_ocrb==0xffff && d.frt.expiry.v==-1);
    assert(d.suspend_flags==SUSPEND_REASON_CLOCK && d.hiz==1);
    d.ckpreq_w(0); assert(d.ack==0 && d.m_clock_pause);
    d.resume(SUSPEND_REASON_CLOCK); d.device_clock_changed(); assert(d.suspend_flags==SUSPEND_REASON_CLOCK);
    d.hiz=0; d.ack=1; d.power_postload(); assert(d.hiz==1 && d.ack==0);
    d.now=105; d.execute_set_input(16,1); assert(!d.m_standby_waking); // entry inhibition
    d.execute_set_input(16,0); d.now=106; d.execute_set_input(16,1);
    assert(d.m_standby_waking && d.standby.expiry.v==((256-17)<<13) && d.assertions==0);
    d.standby_wake(0); assert(!d.m_standby && d.suspend_flags==0 && d.assertions==1 && d.m_wtcnt==0);
    assert(d.hiz==0 && d.ack==1 && !d.m_clock_pause);
    d.execute_set_input(16,0); assert(d.assertions==1);
    d.m_nmie=true; d.execute_set_input(16,1); assert(d.assertions==1);
    d.execute_set_input(16,0); assert(d.assertions==2); // rising pin edge
    assert(d.intc_icr_r()&0x8000);
    d.execute_set_input(16,1); assert(!(d.intc_icr_r()&0x8000));
    // Module stop resets SCI/FRT independently, retaining DMAC registers.
    d.sci_reset(); d.m_sbycr=0; d.scr_w(0x30); d.m_frc=0x1234;
    d.m_sbycr=1; d.module_standby(0); assert(d.m_scr==0 && d.m_frc==0x1234);
    d.m_sbycr=3; d.module_standby(1); assert(d.m_frc==0 && d.m_ocra==0xffff && d.frt.expiry.v==-1);
    d.m_sbycr=1; d.module_standby(3); assert(d.frt.expiry.v==100);
    d.m_dmac[0].sar=0x12345678; d.m_sbycr=0x11; d.module_standby(1);
    assert(d.m_dmac[0].sar==0x12345678 && d.dma[0].expiry.v==-1);
    d.m_sbycr=1; d.module_standby(0x11); assert(d.m_dmac[0].sar==0x12345678);
    // Stopped FRT still tracks its physical input level, without capturing it.
    d.m_frc_tcr=0x80; d.m_ftcsr=0; d.m_frc=0x4321; d.m_sbycr=3;
    d.set_frt_input(1); assert(d.m_frt_input==1 && !(d.m_ftcsr&0x80));
    d.m_sbycr=1; d.set_frt_input(1); assert(!(d.m_ftcsr&0x80));
    d.set_frt_input(0); d.set_frt_input(1); assert((d.m_ftcsr&0x80) && d.m_frc_icr==0x4321);
    std::cout<<"SH7604 SCI handshake / standby actual-method ASan/UBSan PASS\n";
}
'''


def extract(source, name):
    match = re.search(r"(?:[\w:]+\s+sh7604_device::"+name+r"\([^)]*\)(?: const)?|TIMER_CALLBACK_MEMBER\(sh7604_device::"+name+r"\))\s*\{",source)
    assert match, name
    end, depth = match.end(), 1
    while depth:
        depth += (source[end]=='{')-(source[end]=='}')
        end += 1
    return source[match.start():end]


def main():
    source=Path('src/devices/cpu/sh/sh7604.cpp').read_text()
    names=['bsc_endian_update','sci_dma_requested','sci_reset','sci_bit_clocks','sci_drive_txd','sci_drive_sck','sci_reclock','sci_update','sci_load_tsr','sci_start','sci_tx_step','sci_tx_complete','sci_transmit_complete','sci_rx_start','sci_sample_rx','sci_sync_edge','sci_rx_tick','sci_clock_tick','sci_rxd_w','sci_sck_w',
           'sci_receive_byte','scr_w','tdr_w','ssr_r','ssr_w','rdr_r',
           'sh2_notify_dma_data_available','sh2_dmac_check','sh2_do_dma','dma_unit_time','dma_dack_drive','dma_dack_level','dma_dack_tick','dma_run_step','dma_commit_unit','dma_update_halt','sh2_dma_current_active_callback','sh2_recalc_irq','module_standby','frt_reset','standby_init','intc_icr_r','set_frt_input','frt_capture','frt_capture_callback','device_clock_changed','power_postload','sleep_enter','ckpreq_w','execute_set_input','standby_wake']
    methods=[extract(source,n) for n in names]
    core=Path("src/devices/cpu/sh/sh2.cpp").read_text().replace("sh2_device::", "sh7604_device::")
    methods += [extract(core,n) for n in ("external_data_read", "external_data_write")]
    declarations='\n'.join(m.split('{',1)[0].replace('sh7604_device::','').strip()+';' for m in methods)
    declarations=declarations.replace('uint8_t errors, bool mpb)', 'uint8_t errors = 0, bool mpb = false)')
    with tempfile.TemporaryDirectory(prefix='sh7604-sci-standby-') as tmp:
        cpp=Path(tmp)/'fixture.cpp'; binary=Path(tmp)/'fixture'
        cpp.write_text(PREAMBLE.replace('// DECLARATIONS',declarations)+'\n'+'\n'.join(methods)+MAIN)
        subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g',str(cpp),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

if __name__=='__main__': main()

#!/usr/bin/env python3
"""Externally clocked synchronous SCI RX; method-level, unvalidated.

Extracts actual register/edge/completion methods. The pin driver has no timer
and samples a separate data value on each rising edge. Does not run MAME or
its interrupt arbiter/save manager.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('sck_w', 'void'), ('sci_sync_edge', 'void'), ('scr_w', 'void'), ('ssr_r', 'uint8_t'),
    ('ssr_w', 'void'), ('sci_rx_complete', 'void')))
head = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define BIT(v,n) (((v) >> (n)) & 1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
struct attotime { static constexpr int never=-1; };
struct Timer { int adjustments=0; void adjust(int, int=0) { ++adjustments; } };
struct Device {
 static constexpr uint8_t SSR_TDRE=0x80, SSR_RDRF=0x40, SSR_ORER=0x20,
  SSR_FER=0x10, SSR_PER=8, SSR_TEND=4, SSR_MPB=2;
 uint8_t m_scr=0, m_smr=0x80, m_ssr=0x84, m_sci_ssr_read=0, m_tsr=0, m_tdr=0xff, m_rdr=0xa5;
 uint8_t m_sci_tx_bit=0;
 uint8_t m_sci_rx_state=0, m_sci_rx_phase=0, m_sci_rx_shift=0, m_sci_rx_bitcnt=0;
 bool m_sci_tx_active=false, m_sci_tx_loaded=false, m_sci_rx_enabled=false, m_sci_sck=true;
 Timer timer; Timer *m_sci_rx_timer=&timer, *m_sci_tx_timer=&timer;
 int line=1, irqs=0, rate_changes=0;
 // This fixture exercises register/async/external-edge methods, not the internal clock.
 void sci_update_clock() {}
 // External asynchronous receive is exercised by its own pin-clock fixture.
 void sci_rx_tick(int) {}
 uint8_t m_sci_tx_phase=0;
 // External asynchronous TX is covered by a separate pin-clock fixture.
 void sci_tx_tick(int) {}
 Device &machine() { return *this; }
 bool side_effects_disabled() const { return false; }
 int sci_bit_period() const { return 16; }
 void sci_recalc_rates() { ++rate_changes; }
 int m_read_rxd(int) { return line; }
 void m_write_txd(int) {}
 void sci_transmit_start() { std::abort(); }
 void sh2_recalc_irq() { ++irqs; }
'''
tail = r'''
 void bit(int value) {
  line=!value; sck_w(0); sck_w(0); // falling edge synchronizes, not samples
  line=value; sck_w(1); sck_w(7); // repeated high must not consume a bit
 }
 void byte(uint8_t value) { for (int i=0;i<8;++i) bit((value>>i)&1); }
 void acknowledge() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
};
int main() {
 unsigned cases=0, replays=0;
 for (unsigned format=0;format<128;++format) for (unsigned control=0;control<8;++control)
 for (unsigned value=0;value<256;++value) {
  Device d; d.m_smr=0x80|format;
  const unsigned scr=0x12 | (control&1) | ((control&2)?0x40:0) | ((control&4)?8:0);
  d.scr_w(scr); d.irqs=0;
  CHECK(!d.m_sci_rx_enabled); // no asynchronous timer clocking in sync mode
  const int timer_updates=d.timer.adjustments;
  for (int i=0;i<7;++i) { d.bit((value>>i)&1); CHECK(d.m_ssr==0x84 && d.m_rdr==0xa5 && d.irqs==0); }
  d.bit(value>>7);
  CHECK(d.m_ssr==0xc4 && d.m_rdr==value && d.irqs==1);
  CHECK(d.m_scr==scr && d.m_sci_rx_state==0 && d.timer.adjustments==timer_updates);
  d.byte(value^0xff); CHECK(d.m_ssr==0xe4 && d.m_rdr==value && d.irqs==2);
  d.byte(0x5a); CHECK(d.m_ssr==0xe4 && d.m_rdr==value && d.irqs==2);
  d.acknowledge(); d.byte(value^1);
  CHECK(d.m_ssr==0xc4 && d.m_rdr==(value^1));
  ++cases;
 }
 // Snapshot at every half-edge of a frame, including a low SCK input:
 // replay the same level before proceeding, so unsaved edge history is visible.
 for (unsigned value=0;value<256;++value) for (int edge=0;edge<16;++edge) {
  Device d; d.scr_w(0x52);
  for (int i=0;i<=edge;++i) { d.line=(value>>(i/2))&1; d.sck_w(i&1); }
  Device replay=d; replay.m_sci_rx_timer=&replay.timer; replay.m_sci_tx_timer=&replay.timer;
  replay.sck_w(edge&1);
  for (int i=edge+1;i<16;++i) {
   d.line=replay.line=(value>>(i/2))&1; d.sck_w(i&1); replay.sck_w(i&1);
  }
  CHECK(d.m_rdr==value && replay.m_rdr==value && replay.m_ssr==d.m_ssr && replay.irqs==d.irqs);
  ++replays;
 }
 // Neither a high level on RE enable nor a repeated low is a new falling edge.
 Device abort; abort.scr_w(0x12); abort.bit(1); abort.sck_w(0);
 abort.scr_w(2); abort.scr_w(0x12); abort.sck_w(0); abort.sck_w(1);
 CHECK(abort.m_sci_rx_state==0 && abort.m_ssr==0x84);
 abort.byte(0x69); CHECK(abort.m_rdr==0x69);
 // Wrong clock/mode, RE=0 and inherited error flags must suppress receive.
 for (unsigned mode=0;mode<2;++mode) for (unsigned clock=0;clock<4;++clock)
 for (unsigned re=0;re<2;++re) {
  Device d; d.m_smr=mode?0x80:0; d.scr_w(clock|(re?0x10:0));
  d.byte(0x53);
  CHECK(d.m_rdr==((mode&&(clock&2)&&re)?0x53:0xa5));
 }
 for (unsigned error=8;error<=32;error<<=1) {
  Device d; d.scr_w(0x12); d.m_ssr|=error; d.byte(0x57);
  CHECK(d.m_rdr==0xa5 && d.m_ssr==(0x84|error));
  d.acknowledge(); d.byte(0x75); CHECK(d.m_rdr==0x75 && d.m_ssr==0xc4);
 }
 std::printf("method-level, unvalidated: %u sync RX format/control/data cases; %u half-edge state-copy replays\n",cases,replays);
 std::puts("method-level, unvalidated: repeated levels, stop/resume, error stall, overrun and mode gates exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-sync-rx-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_sci_sck));' in source
assert 'm_sci_sck = true;' in source
print('method-level, unvalidated: SCK edge-history reset/save registration present')

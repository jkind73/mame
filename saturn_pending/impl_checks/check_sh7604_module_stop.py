#!/usr/bin/env python3
"""SCI MSTP0/reset methods; method-level, unvalidated.

Uses real register, reset and transfer methods with virtual timers. Legal
halted-entry cases are separate from active-transfer reset robustness probes:
the latter assert software cleanup, not silicon behavior for forbidden use.
State-copy replay is not native save-manager qualification.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock = Path(__file__).with_name('check_sh7604_internal_sync.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))
head = '#include <algorithm>\n#include <bit>\n' + head
head = head.replace('struct Device {', '''
using offs_t = unsigned;
struct sh2_device { void device_reset() {} };
struct Device : sh2_device {
 // FRT implementation is covered separately; these are declaration-only
 // stubs for the unrelated branches of the shared SBYCR/reset methods.
 void frt_reset() {}
 void sh2_timer_activate() {}
 uint64_t total_cycles() const { return now; }
 bool m_frt_clock_input=false;
 uint8_t m_wdt_read=0;
 uint8_t m_sbycr=0, m_rsr=0, m_sci_rx_vote=0;
 bool m_sci_rx_parity_error=false, m_sci_rx_mp=false;
 uint16_t m_vcra=0x1234, m_vcrb=0x5678, m_iprb=0xf000;
 int m_frc=17, m_ocra=18, m_ocrb=19, m_frc_icr=20, m_frc_base=21, m_frt_input=22;
 int m_dma_timer_active[2]{}, m_dma_irq[2]{}, m_active_dma_incs[2]{}, m_active_dma_incd[2]{};
 int m_active_dma_size[2]{}, m_active_dma_steal[2]{}, m_active_dma_src[2]{}, m_active_dma_dst[2]{}, m_active_dma_count[2]{};
 int m_wtcnt=23, m_wtcsr=24, m_barah=25, m_baral=26, m_barbh=27, m_barbl=28;
 bool irq_requested=false;
 template<class... Args> void logerror(const char *, Args...) {}
''')
head = head.replace('void sci_rx_tick(int) {}', '').replace('void sci_tx_tick(int) {}', '')
head = head.replace('void sh2_recalc_irq() { irqs.emplace_back(now,m_ssr); }', '''
 void sh2_recalc_irq() {
  irqs.emplace_back(now,m_ssr);
  irq_requested = ((m_ssr&0x78) && (m_scr&0x40)) || ((m_ssr&0x80) && (m_scr&0x80)) || ((m_ssr&4) && (m_scr&4));
 }
''')
head = head.replace('if (peer) return peer->txd;', 'if (loopback) return txd;\n  if (peer) return peer->txd;')
head = head.replace('Device *peer=nullptr;', 'bool loopback=false;\n Device *peer=nullptr;')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('fmr_sbycr_w', 'void'), ('fmr_sbycr_r', 'uint16_t'), ('device_reset', 'void'),
    ('sck_w', 'void'), ('sci_sync_edge', 'void'), ('sci_update_clock', 'void'),
    ('scr_w', 'void'), ('smr_w', 'void'), ('brr_w', 'void'), ('ssr_r', 'uint8_t'),
    ('ssr_w', 'void'), ('tdr_w', 'void'), ('sci_transmit_start', 'void'),
    ('sci_recalc_rates', 'void'), ('sci_bit_period', 'attotime'), ('sci_rx_complete', 'void')))
# Older production sources have their reset inline; keep the negative control
# intact rather than inserting a replacement reset implementation.
if 'void sh7604_device::sci_reset()' in source:
    functions += '\n' + extract('sci_reset', 'void')
for name in ('sci_clock_tick', 'sci_tx_tick', 'sci_rx_tick'):
    match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::' + name + r'\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    functions += '\nvoid ' + name + '(int param)\n' + match[0].split('\n', 1)[1]

tail = r'''
 void advance(ticks end) {
  unsigned events=0;
  while (std::min({clock_timer.due,tx.due,rx.due})<=end) {
   CHECK(++events<100000); now=std::min({clock_timer.due,tx.due,rx.due});
   if (clock_timer.due==now) { clock_timer.due=attotime::never.value; sci_clock_tick(0); }
   if (tx.due==now) { const auto p=tx.param; tx.due=attotime::never.value; sci_tx_tick(p); }
   if (rx.due==now) { const auto p=rx.param; rx.due=attotime::never.value; sci_rx_tick(p); }
  }
  now=end;
 }
 void queue(uint8_t value) { const auto status=ssr_r(); CHECK(status&0x80); tdr_w(value); ssr_w(status&0x7f); }
 void rebind() { peer=nullptr; m_sci_tx_timer=&tx; m_sci_rx_timer=&rx; m_sci_clock_timer=&clock_timer; }
 void stop(unsigned value=1) { fmr_sbycr_w(0,value,0x00ff); }
 void initial_state() const {
  CHECK(m_smr==0 && m_brr==0xff && m_scr==0 && m_tdr==0xff && m_ssr==0x84 && m_rdr==0);
  CHECK(m_tsr==0 && m_rsr==0 && m_sci_ssr_read==0);
  CHECK(!m_sci_tx_active && !m_sci_tx_loaded && !m_sci_tx_bit && !m_sci_tx_phase);
  CHECK(!m_sci_rx_enabled && !m_sci_rx_state && !m_sci_rx_phase && !m_sci_rx_shift);
  CHECK(!m_sci_rx_parity_error && !m_sci_rx_mp && !m_sci_rx_bitcnt && !m_sci_rx_vote);
  CHECK(!m_sci_clock_running && m_sci_sck_out && txd==1);
  CHECK(tx.due==attotime::never.value && rx.due==attotime::never.value && clock_timer.due==attotime::never.value);
 }
 void quiet_interval() {
  const auto w=wire.size(), c=clocks.size(), i=irqs.size(); const auto r=reads;
  for (unsigned k=0;k<512;++k) { sck_w(0); sck_w(1); }
  advance(now+1000000);
  CHECK(wire.size()==w && clocks.size()==c && irqs.size()==i && reads==r);
  initial_state();
 }
};
int main() {
 unsigned entries=0, replays=0, restarts=0, resets=0, controls=0, robustness=0;
 // TE=RE=0: residual data/status/read qualifications must not survive MSTP0.
 // Inspect mock backing state while stopped; no SCI bus reads/writes there.
 for (unsigned mode=0;mode<256;++mode) for (unsigned flags=0;flags<64;++flags) {
  now=0; Device d; d.smr_w(mode); d.brr_w(mode^0xa5); d.tdr_w(mode^0x5a); d.scr_w(0xc4);
  d.m_ssr=0x84 | ((flags&0x3c)<<1) | (flags&3); d.m_rdr=mode;
  d.m_tsr=mode^0x55; d.m_rsr=mode^0xaa;
  d.m_sci_rx_shift=mode; d.m_sci_rx_bitcnt=7; d.m_sci_rx_phase=13; d.m_sci_rx_vote=3;
  d.m_sci_rx_parity_error=true; d.m_sci_rx_mp=true; d.ssr_r();
  d.sh2_recalc_irq(); CHECK(d.irq_requested);
  d.m_vcra=mode*257; d.m_vcrb=flags*257; const auto irqs=d.irqs.size();
  d.stop(); CHECK(d.fmr_sbycr_r()==1); d.initial_state(); CHECK(!d.irq_requested);
  CHECK(d.irqs.size()==irqs+1 && d.m_vcra==mode*257 && d.m_vcrb==flags*257 && d.m_iprb==0xf000);
  CHECK(d.m_frc==17 && d.m_ocra==18 && d.m_ocrb==19 && d.m_wtcnt==23 && d.m_wtcsr==24);
  CHECK(d.m_barah==25 && d.m_baral==26 && d.m_barbh==27 && d.m_barbl==28);
  const auto clocks=d.clocks.size(), wire=d.wire.size(), irq=d.irqs.size();
  d.stop(1); CHECK(d.clocks.size()==clocks && d.wire.size()==wire && d.irqs.size()==irq);
  d.quiet_interval(); d.stop(0); d.initial_state(); d.quiet_interval(); ++entries;
 }
 // Other SBYCR bits and FMR-only access widths must not reset an idle SCI.
 for (unsigned value=0;value<256;++value) if (!(value&0x21)) {
  for (unsigned mask : {0x00ffU,0xff00U,0xffffU}) {
   now=0; Device d; d.smr_w(0x6b); d.brr_w(3); d.tdr_w(0x69); d.ssr_r();
   d.fmr_sbycr_w(0,value,mask);
   CHECK(d.m_smr==0x6b && d.m_brr==3 && d.m_tdr==0x69 && d.m_sci_ssr_read==0x84);
   CHECK(d.wire.empty() && d.clocks.empty()); ++controls;
  }
 }
 // Preserve existing FMR routing even if its data contains bit zero.
 for (unsigned mask : {0xff00U,0xffffU}) {
  now=0; Device d; d.smr_w(0x23); d.fmr_sbycr_w(0,0x0101,mask);
  CHECK(d.m_smr==0x23 && d.m_sbycr==0 && d.wire.empty()); ++controls;
 }
 // Reinitialize after release; real TX/RX can transfer a fresh byte, not a
 // paused character. Internal and external, asynchronous and synchronous.
 for (unsigned mode : {0U,0x80U}) for (unsigned cke=0;cke<4;++cke)
 for (unsigned value=0;value<256;++value) {
  now=0; Device d; d.stop(); d.quiet_interval();
  Device replay=d; replay.rebind(); const auto saved_time=now;
  auto transfer = [&](Device &x) {
   x.stop(0); x.initial_state(); x.loopback=true; x.smr_w(mode); x.brr_w(1); x.scr_w(cke);
   x.advance(now+x.sci_bit_period().value); x.scr_w(0x30|cke); x.queue(value);
   if (cke&2) {
    for (unsigned pulse=0;pulse<(mode?8U:200U);++pulse) { ++now; x.sck_w(0); ++now; x.sck_w(1); }
   } else x.advance(now+12*x.sci_bit_period().value);
   CHECK(x.m_rdr==value && (x.m_ssr&0xfc)==0xc4 && !x.m_sci_tx_active);
   // Halt legally before the next stop: disable RX/TX and clock output.
   x.scr_w(0); x.stop(1); x.initial_state();
  };
  transfer(d); now=saved_time; transfer(replay);
  CHECK(d.wire==replay.wire && d.clocks==replay.clocks && d.irqs==replay.irqs);
  CHECK(d.m_sbycr==replay.m_sbycr && d.m_ssr==replay.m_ssr); ++replays; ++restarts;
 }
 // Manual/power reset entry point releases SBYCR.MSTP0 too. The SH2 base
 // reset is mocked: this does not qualify native CPU or interrupt reset.
 for (unsigned value=0;value<256;++value) if (!(value&0x20)) {
  now=0; Device d; d.stop(value); d.device_reset();
  CHECK(d.m_sbycr==0); d.initial_state(); ++resets;
 }
 // Robustness only: the manual forbids switching a running module to
 // standby. Exercise cleanup at many TX/RX/clock phases, without claiming
 // these stop edges or aborted characters describe legal hardware use.
 for (unsigned mode : {0U,0x68U,0x80U}) for (unsigned cke=0;cke<4;++cke)
 for (unsigned phase=0;phase<32;++phase) {
  now=0; Device d; d.loopback=true; d.smr_w(mode); d.brr_w(1); d.scr_w(0x30|cke); d.queue(0x69);
  if (cke&2) {
   for (unsigned pulse=0;pulse<phase;++pulse) { ++now; d.sck_w(0); ++now; d.sck_w(1); }
  } else d.advance(phase*d.sci_bit_period().value/8);
  d.stop(); d.initial_state(); d.quiet_interval(); ++robustness;
 }
 std::printf("method-level, unvalidated: %u halted-entry cases; %u access-width/other-bit controls; %u fresh transfers and %u state-copy replays; %u reset-release cases\n",entries,controls,restarts,replays,resets);
 std::printf("method-level, unvalidated: %u forbidden-active-entry cleanup probes (software robustness only)\n",robustness);
 std::puts("method-level, unvalidated: register/read-latch reset, vector preservation, timer cancellation and no stale resume exercised; no native IRQ/save or high-impedance model");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-stop-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_sbycr));' in source
print('method-level, unvalidated: existing SBYCR save registration retained; no new state fields')

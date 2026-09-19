#!/usr/bin/env python3
"""Actual SCI clock/edge/register methods; method-level, unvalidated.

Virtual phi clock measures SCK pulse counts/widths against an independent
BRR/CKS oracle. Two extracted devices can exchange different data on shared
SCK. State-copy replay is not native MAME/save-manager or hardware evidence.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('sck_w', 'void'), ('sci_sync_edge', 'void'), ('sci_update_sync_clock', 'void'),
    ('scr_w', 'void'), ('smr_w', 'void'), ('brr_w', 'void'), ('ssr_r', 'uint8_t'),
    ('ssr_w', 'void'), ('tdr_w', 'void'), ('sci_transmit_start', 'void'),
    ('sci_recalc_rates', 'void'), ('sci_bit_period', 'attotime'), ('sci_rx_complete', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sci_sync_tick\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sci_sync_tick(int param)\n' + match[0].split('\n', 1)[1]
head = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <utility>
#include <limits>
#define BIT(v,n) (((v) >> (n)) & 1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using ticks = int64_t;
static ticks now=0;
struct attotime {
 ticks value;
 static const attotime never;
 static attotime from_ticks(ticks value, unsigned) { return {value}; }
 attotime operator/(int n) const { return {value/n}; }
};
const attotime attotime::never{std::numeric_limits<ticks>::max()};
struct Timer {
 ticks due=attotime::never.value; int param=0;
 void adjust(attotime delay, int p=0) { due=delay.value==attotime::never.value?delay.value:now+delay.value; param=p; }
};
struct Device {
 static constexpr uint8_t SSR_TDRE=0x80, SSR_RDRF=0x40, SSR_ORER=0x20,
  SSR_FER=0x10, SSR_PER=8, SSR_TEND=4, SSR_MPB=2;
 uint8_t m_scr=0, m_smr=0, m_brr=0, m_ssr=0x84, m_sci_ssr_read=0, m_tsr=0, m_tdr=0xff, m_rdr=0xa5;
 uint8_t m_sci_tx_bit=0, m_sci_rx_state=0, m_sci_rx_phase=0, m_sci_rx_shift=0, m_sci_rx_bitcnt=0;
 bool m_sci_tx_active=false, m_sci_tx_loaded=false, m_sci_rx_enabled=false;
 bool m_sci_sck=true, m_sci_sck_out=true, m_sci_clock_running=false;
 Timer tx, rx, clock_timer;
 Timer *m_sci_tx_timer=&tx, *m_sci_rx_timer=&rx, *m_sci_clock_timer=&clock_timer;
 Device *peer=nullptr;
 int txd=1; unsigned reads=0; std::vector<uint8_t> incoming{0x5a};
 std::vector<std::pair<ticks,int>> wire, clocks, irqs;
 // External asynchronous receive is exercised by its own pin-clock fixture.
 void sci_rx_tick(int) {}
 Device &machine() { return *this; }
 bool side_effects_disabled() const { return false; }
 unsigned clock() const { return 1; } // mock attotime retains phi ticks
 int m_read_rxd(int) {
  if (peer) return peer->txd;
  const int bit=(incoming[(reads/8)%incoming.size()]>>(reads&7))&1; ++reads; return bit;
 }
 void m_write_txd(int value) { txd=value; wire.emplace_back(now,value); }
 void m_write_sck(int value) { clocks.emplace_back(now,value); if (peer) peer->sck_w(value); }
 void sh2_recalc_irq() { irqs.emplace_back(now,m_ssr); }
'''
tail = r'''
 void advance(ticks end) {
  unsigned events=0;
  while (clock_timer.due<=end) {
   CHECK(++events<10000); now=clock_timer.due;
   clock_timer.due=attotime::never.value; sci_sync_tick(0);
  }
  now=end;
 }
 void queue(uint8_t data) {
  const auto status=ssr_r(); CHECK(status&0x80); tdr_w(data); ssr_w(status & ~0x80);
 }
 void acknowledge() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
 void rebind() { peer=nullptr; m_sci_tx_timer=&tx; m_sci_rx_timer=&rx; m_sci_clock_timer=&clock_timer; }
};
static void check_clocks(const Device &d, ticks bit, unsigned bits) {
 CHECK(d.clocks.size()==2*bits);
 for (unsigned i=0;i<2*bits;++i) {
  CHECK(d.clocks[i].first==ticks(i+1)*(bit/2)); CHECK(d.clocks[i].second==int(i&1));
 }
}
int main() {
 unsigned rates=0, duplex_cases=0, replays=0;
 for (unsigned cks=0;cks<4;++cks) for (unsigned brr=0;brr<256;++brr)
 for (unsigned cke=0;cke<2;++cke) for (unsigned value : {0U,0x55U,0x80U,0xffU}) {
  now=0; Device d; d.smr_w(0x80|cks); d.brr_w(brr); d.scr_w(0xa4|cke);
  CHECK(!d.m_sci_clock_running && d.clocks.empty()); // TE alone does not start SCK
  const ticks bit=ticks(brr+1)*(16U<<(2*cks));
  CHECK(d.sci_bit_period().value==bit);
  d.queue(value); CHECK(d.clocks.empty() && d.wire.empty());
  // External pin noise cannot drive an internal-mode transfer.
  d.sck_w(0); d.sck_w(1); CHECK(d.wire.empty());
  d.advance(bit*7+bit/2); CHECK(d.m_ssr==0x84 && !d.m_sci_tx_active);
  CHECK(!d.m_sci_sck_out && d.m_sci_clock_running); // last rise still pending
  d.advance(bit*8); CHECK(d.m_sci_sck_out && !d.m_sci_clock_running);
  CHECK(d.clock_timer.due==attotime::never.value);
  CHECK(d.wire.size()==8 && d.txd==int(value>>7) && d.reads==0);
  for (unsigned i=0;i<8;++i) {
   CHECK(d.wire[i].first==ticks(2*i+1)*bit/2);
   CHECK(d.wire[i].second==int((value>>i)&1));
  }
  d.advance(bit*12); check_clocks(d,bit,8); ++rates;
 }
 // Two actual edge engines: master internal clock, slave external input.
 for (unsigned cks=0;cks<4;++cks) for (unsigned brr : {0U,1U,255U})
 for (unsigned value=0;value<256;++value) {
  now=0; Device master,slave; master.peer=&slave; slave.peer=&master;
  master.smr_w(0x80|cks); master.brr_w(brr); master.scr_w(0xf4);
  slave.smr_w(0x80); slave.scr_w(0xf6);
  CHECK(!master.m_sci_clock_running && !slave.m_sci_clock_running);
  const ticks bit=ticks(brr+1)*(16U<<(2*cks));
  slave.queue(value^0xff); slave.queue(value^0x55);
  master.queue(value); master.queue(value^0xaa);
  master.advance(8*bit);
  CHECK(master.m_rdr==(value^0xff) && slave.m_rdr==value);
  CHECK(master.m_ssr==0xc0 && slave.m_ssr==0xc0);
  master.acknowledge(); slave.acknowledge();
  master.queue(value^1); slave.queue(value^0x80);
  master.advance(8*bit+bit/4);
  const auto due=master.clock_timer.due;
  master.scr_w(0x30); master.scr_w(0xf4); CHECK(master.clock_timer.due==due);
  master.advance(24*bit); // unread second RX byte causes overrun on the third
  CHECK(master.m_rdr==(value^0x55) && slave.m_rdr==(value^0xaa));
  CHECK(master.m_ssr==0xe4 && slave.m_ssr==0xe4 && !master.m_sci_clock_running);
  check_clocks(master,bit,24); CHECK(slave.clocks.empty());
  master.acknowledge(); slave.acknowledge();
  CHECK(!master.m_sci_clock_running); // full duplex waits for TX data
  master.queue(0x69); slave.queue(0x96); master.advance(32*bit);
  CHECK(master.m_rdr==0x96 && slave.m_rdr==0x69 && master.m_ssr==0xc4 && slave.m_ssr==0xc4);
  CHECK(!master.m_sci_clock_running && master.m_sci_sck_out); ++duplex_cases;
 }
 // Receive-only clocks continuously until disabled or receive error occurs.
 now=0; Device receiver; receiver.smr_w(0x80); receiver.incoming={0x12,0x34}; receiver.scr_w(0x50);
 CHECK(receiver.m_sci_clock_running); receiver.advance(128);
 CHECK(receiver.m_rdr==0x12 && receiver.m_ssr==0xc4 && receiver.m_sci_clock_running);
 receiver.advance(256); CHECK(receiver.m_rdr==0x12 && receiver.m_ssr==0xe4 && !receiver.m_sci_clock_running);
 receiver.acknowledge(); CHECK(receiver.m_sci_clock_running);
 receiver.advance(384); CHECK(receiver.m_rdr==0x12 && receiver.m_ssr==0xc4);
 receiver.scr_w(0); CHECK(!receiver.m_sci_clock_running && receiver.m_sci_sck_out);
 // Saved level/running/shift state and timer due preserve the final rising edge.
 for (unsigned value=0;value<256;++value) for (unsigned half=1;half<=16;++half) {
  now=0; Device d; d.smr_w(0x80); d.scr_w(0x20); d.queue(value); d.advance(8*half);
  Device replay=d; replay.rebind(); const auto saved_time=now;
  d.advance(160); now=saved_time; replay.advance(160);
  CHECK(d.wire==replay.wire && d.clocks==replay.clocks && d.irqs==replay.irqs);
  CHECK(d.m_sci_sck_out==replay.m_sci_sck_out && d.m_sci_clock_running==replay.m_sci_clock_running);
  ++replays;
 }
 // Cancel in a low half-period: no stale scheduled callback may resume work.
 now=0; Device cancel; cancel.smr_w(0x80); cancel.scr_w(0x20); cancel.queue(0x55); cancel.advance(40);
 CHECK(!cancel.m_sci_sck_out); cancel.scr_w(0); CHECK(cancel.m_sci_sck_out && !cancel.m_sci_clock_running);
 const auto edges=cancel.clocks.size(); cancel.advance(1000); CHECK(cancel.clocks.size()==edges);
 // Internal/external selection and inherited errors gate the generator.
 for (unsigned error=8;error<=32;error<<=1) {
  now=0; Device d; d.smr_w(0x80); d.m_ssr|=error; d.scr_w(0x20); d.queue(0x81);
  CHECK(!d.m_sci_clock_running); d.acknowledge(); CHECK(d.m_sci_clock_running);
  d.advance(128); CHECK(d.m_ssr==0x84 && !d.m_sci_clock_running);
 }
 std::printf("method-level, unvalidated: %u rate/clock-select/TX cases; %u two-device duplex streams; %u half-edge state-copy replays\n",rates,duplex_cases,replays);
 std::puts("method-level, unvalidated: receive-only, eight-pulse termination, error recovery, cancellation and no-retime controls exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-int-sync-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
for field in ('m_sci_sck_out','m_sci_clock_running'):
    assert f'save_item(NAME({field}));' in source
assert 'm_sci_sck_out = true;' in source and 'm_sci_clock_running = false;' in source
print('method-level, unvalidated: clock level/running reset/save registration present')

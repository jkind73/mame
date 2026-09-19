#!/usr/bin/env python3
"""Async baud-rate SCK output and TX phase; method-level, unvalidated.

Extracts real clock/register/TX/RX methods. A virtual phi scheduler compares
SCK periods and data boundaries to an independent frame oracle. Existing
fixtures provide mock declarations only. Optional pre-change source normalizes
helper names, without changing the old implementation bodies.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
source = source.replace('sci_update_sync_clock', 'sci_update_clock').replace('sci_sync_tick', 'sci_clock_tick')
mock = Path(__file__).with_name('check_sh7604_internal_sync.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))
head = '#include <bit>\n#include <algorithm>\n' + head
head = head.replace('void sci_rx_tick(int) {}', '').replace('void sci_tx_tick(int) {}', '')
head = head.replace('Device *peer=nullptr;', 'bool m_sci_rx_parity_error=false, m_sci_rx_mp=false, loopback=false;\n Device *peer=nullptr;')
head = head.replace('if (peer) return peer->txd;', 'if (loopback) return txd;\n  if (peer) return peer->txd;')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('sck_w', 'void'), ('sci_sync_edge', 'void'), ('sci_update_clock', 'void'),
    ('scr_w', 'void'), ('smr_w', 'void'), ('brr_w', 'void'), ('ssr_r', 'uint8_t'),
    ('ssr_w', 'void'), ('tdr_w', 'void'), ('sci_transmit_start', 'void'),
    ('sci_recalc_rates', 'void'), ('sci_bit_period', 'attotime'), ('sci_rx_complete', 'void')))
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
 void queue(uint8_t value, unsigned mp=0) { const auto status=ssr_r(); CHECK(status&0x80); tdr_w(value); ssr_w((status&0x7e)|mp); }
 void ack() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
 void rebind() { peer=nullptr; m_sci_tx_timer=&tx; m_sci_rx_timer=&rx; m_sci_clock_timer=&clock_timer; }
};
static std::vector<int> frame(unsigned value,unsigned mode,unsigned mp) {
 std::vector<int> bits{0}; unsigned n=(mode&0x40)?7:8, parity=(mode>>4)&1;
 for (unsigned i=0;i<n;++i) { bits.push_back((value>>i)&1); parity^=bits.back(); }
 if (mode&4) bits.push_back(mp); else if (mode&0x20) bits.push_back(parity);
 bits.push_back(1); if (mode&8) bits.push_back(1); return bits;
}
static void clock_grid(const Device &d,ticks bit) {
 for (unsigned i=0;i<d.clocks.size();++i) {
  CHECK(d.clocks[i].first==ticks(i+1)*(bit/2) && d.clocks[i].second==int(i&1));
 }
}
int main() {
 unsigned rates=0,streams=0,replays=0,loops=0;
 for (unsigned cks=0;cks<4;++cks) for (unsigned brr=0;brr<256;++brr) {
  now=0; Device d; d.smr_w(cks); d.brr_w(brr); d.scr_w(1); d.wire.clear();
  const ticks bit=ticks(brr+1)*(128U<<(cks*2));
  CHECK(d.m_sci_clock_running && d.sci_bit_period().value==bit);
  d.advance(3*bit); CHECK(d.clocks.size()==6 && d.wire.empty() && d.m_ssr==0x84);
  d.m_ssr|=0x38; // existing error flags must not gate asynchronous clock output
  d.sci_update_clock(); d.advance(5*bit);
  CHECK(d.clocks.size()==10 && d.m_sci_clock_running); clock_grid(d,bit); ++rates;
 }
 for (unsigned chars : {0U,0x40U}) for (unsigned format : {0U,0x20U,0x30U,4U})
 for (unsigned stops : {0U,8U}) for (unsigned value=0;value<256;++value) for (unsigned phase=0;phase<4;++phase) {
  now=0; Device d; const unsigned mode=chars|format|stops|(value&3),mp=value&1;
  d.smr_w(mode); d.brr_w(value^0x55); d.scr_w(1); d.wire.clear();
  const ticks bit=ticks((value^0x55)+1)*(128U<<((value&3)*2));
  d.advance(2*bit+phase*(bit/4)); // wait >1 bit for the documented initialization
  d.scr_w(0xa5); const auto due=d.clock_timer.due;
  d.queue(value,mp); d.queue(value^1,mp);
  CHECK(d.wire.empty() && d.clock_timer.due==due && d.tx.due==attotime::never.value);
  const ticks start=(phase<2?5:7)*(bit/2);
  d.advance(start-1); CHECK(d.wire.empty()); d.advance(start);
  CHECK(d.wire.size()==1 && d.wire[0].first==start && d.wire[0].second==0);
  const auto first=frame(value,mode,mp); const ticks length=first.size()*bit;
  d.advance(start+length-bit); CHECK((d.m_ssr&0x84)==0x80);
  d.queue(value^0xff,mp); d.advance(start+3*length);
  CHECK(!d.m_sci_tx_active && d.m_sci_clock_running && d.tx.due==attotime::never.value);
  auto expected=first;
  for (unsigned nextvalue : {value^1,value^0xff}) { const auto next=frame(nextvalue,mode,mp); expected.insert(expected.end(),next.begin(),next.end()); }
  CHECK(d.wire.size()==expected.size());
  for (unsigned i=0;i<expected.size();++i) {
   CHECK(d.wire[i].first==start+i*bit && d.wire[i].second==expected[i]);
   const unsigned falling=unsigned(2*d.wire[i].first/bit)-1;
   CHECK(d.clocks[falling].second==0);
   CHECK(d.clocks[falling+1].second==1 && d.clocks[falling+1].first==d.wire[i].first+bit/2);
  }
  clock_grid(d,bit); const auto deadline=d.clock_timer.due;
  d.scr_w(0x21); d.scr_w(0xa5); CHECK(d.clock_timer.due==deadline); // interrupt bits do not change phase
  const auto edges=d.clocks.size(); d.scr_w(1); d.advance(now+2*bit);
  CHECK(d.clocks.size()==edges+4 && d.m_sci_clock_running); // TE=0 does not stop SCK
  d.scr_w(0); CHECK(!d.m_sci_clock_running); const auto stopped=d.clocks.size();
  d.advance(now+2*bit); CHECK(d.clocks.size()==stopped); ++streams;
 }
 for (unsigned mode : {0U,0x68U}) for (unsigned value=0;value<256;++value) {
  now=0; Device d; d.loopback=true; d.smr_w(mode); d.scr_w(1); d.advance(128);
  d.scr_w(0x31); d.queue(value); d.advance(192+12*128);
  CHECK((d.m_ssr&0x78)==0x40 && d.m_rdr==(value & (mode?0x7f:0xff)));
  d.ack(); d.queue(value^0xff); d.advance(now+14*128);
  CHECK((d.m_ssr&0x78)==0x40 && d.m_rdr==((value^0xff) & (mode?0x7f:0xff)));
  d.queue(value); d.advance(now+14*128); CHECK(d.m_ssr&0x20);
  CHECK(!d.m_sci_tx_active && d.m_sci_clock_running); ++loops;
 }
 for (unsigned value=0;value<256;++value) for (unsigned quarter=0;quarter<16;++quarter) {
  now=0; Device d; d.scr_w(1); d.advance(128); d.scr_w(0x21); d.queue(value); d.queue(value^1);
  d.advance(128+quarter*32); Device replay=d; replay.rebind(); const auto saved_time=now;
  d.advance(3200); now=saved_time; replay.advance(3200);
  CHECK(d.wire==replay.wire && d.clocks==replay.clocks && d.irqs==replay.irqs);
  CHECK(d.m_sci_tx_bit==replay.m_sci_tx_bit && d.m_sci_sck_out==replay.m_sci_sck_out); ++replays;
 }
 // Cancelling a pending start emits no frame, but preserves free-running SCK.
 now=0; Device abort; abort.scr_w(1); abort.advance(128); abort.scr_w(0x21); abort.wire.clear(); abort.queue(0x55);
 abort.scr_w(1); const auto count=abort.wire.size(); abort.advance(2048);
 CHECK(abort.wire.size()==count && !abort.m_sci_tx_active && abort.m_sci_clock_running);
 std::printf("method-level, unvalidated: %u clock-divider cases; %u phase-aligned three-frame streams; %u RX loopbacks; %u state-copy replays\n",rates,streams,loops,replays);
 std::puts("method-level, unvalidated: idle clock, bit-center rising edges, no competing TX timer, continuous queueing and TE/error independence exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-async-sck-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

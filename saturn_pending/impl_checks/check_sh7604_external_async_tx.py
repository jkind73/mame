#!/usr/bin/env python3
"""External 16x-clock asynchronous TX/duplex; method-level, unvalidated.

Reuses clock/pin mock declarations only. Extracts the real TX/RX engines,
SCK input and registers. Output is compared with an independent frame oracle.
Time values in this fixture count external rising pulses, not CPU phi ticks.
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
head = '#include <bit>\n' + head
head = head.replace('void sci_rx_tick(int) {}', '').replace('void sci_tx_tick(int) {}', '')
head = head.replace('Device *peer=nullptr;', 'bool m_sci_rx_parity_error=false, m_sci_rx_mp=false;\n Device *peer=nullptr;')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('sck_w', 'void'), ('sci_sync_edge', 'void'), ('sci_update_clock', 'void'),
    ('scr_w', 'void'), ('smr_w', 'void'), ('brr_w', 'void'), ('ssr_r', 'uint8_t'),
    ('ssr_w', 'void'), ('tdr_w', 'void'), ('sci_transmit_start', 'void'),
    ('sci_recalc_rates', 'void'), ('sci_bit_period', 'attotime'), ('sci_rx_complete', 'void')))
for name in ('sci_tx_tick', 'sci_rx_tick'):
    match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::' + name + r'\)\n\{.*?^\}', source, re.M | re.S)
    assert match
    functions += '\nvoid ' + name + '(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void queue(uint8_t data, unsigned mp=0) { const auto status=ssr_r(); CHECK(status&0x80); tdr_w(data); ssr_w((status & 0x7e)|mp); }
 void pulse() { sck_w(0); sck_w(0); sck_w(1); sck_w(7); }
 void advance(ticks pulse_index) { while (now<pulse_index) { ++now; pulse(); } }
 void rebind() { peer=nullptr; m_sci_tx_timer=&tx; m_sci_rx_timer=&rx; m_sci_clock_timer=&clock_timer; }
 void no_timers() const { CHECK(tx.due==attotime::never.value && rx.due==attotime::never.value && clock_timer.due==attotime::never.value); }
};
static std::vector<int> frame(unsigned value, unsigned mode, unsigned mp) {
 std::vector<int> bits{0}; unsigned n=(mode&0x40)?7:8, parity=(mode>>4)&1;
 for (unsigned i=0;i<n;++i) { bits.push_back((value>>i)&1); parity^=bits.back(); }
 if (mode&4) bits.push_back(mp); else if (mode&0x20) bits.push_back(parity);
 bits.push_back(1); if (mode&8) bits.push_back(1); return bits;
}
int main() {
 unsigned streams=0,replays=0;
 for (unsigned chars : {0U,0x40U}) for (unsigned format : {0U,0x20U,0x30U,4U})
 for (unsigned stops : {0U,8U}) for (unsigned cke : {2U,3U}) for (unsigned value=0;value<256;++value) {
  now=0; Device d; const unsigned mode=chars|format|stops|(value&3), mp=value&1;
  d.smr_w(mode); d.brr_w(value^0x5a); d.scr_w(0xa4|cke); d.wire.clear();
  d.queue(value,mp); d.queue(value^1,mp); d.no_timers();
  const auto first=frame(value,mode,mp); const ticks length=16*first.size();
  d.advance(21); const auto phase=d.m_sci_tx_phase, bit=d.m_sci_tx_bit;
  d.brr_w(value); CHECK(d.m_sci_tx_phase==phase && d.m_sci_tx_bit==bit); d.no_timers();
  d.advance(length-17); CHECK(!(d.m_ssr&0x84));
  d.advance(length-16); CHECK((d.m_ssr&0x84)==0x80);
  d.queue(value^0xff,mp); d.advance(3*length-16);
  CHECK(d.m_ssr&4); CHECK(d.m_sci_tx_active); d.advance(3*length);
  CHECK(!d.m_sci_tx_active && d.m_sci_tx_phase==0); d.no_timers();
  auto expected=first;
  for (unsigned data : {value^1,value^0xff}) {
   const auto next=frame(data,mode,mp); expected.insert(expected.end(),next.begin(),next.end());
  }
  CHECK(d.wire.size()==expected.size());
  for (unsigned i=0;i<expected.size();++i) { CHECK(d.wire[i].first==16*i && d.wire[i].second==expected[i]); }
  d.advance(3*length+160); CHECK(d.wire.size()==expected.size()); ++streams;
 }
 // Two independently transmitting/receiving endpoints on the same 16x clock.
 // RX overrun must not stop asynchronous TX, unlike synchronous operation.
 for (unsigned value=0;value<256;++value) {
  now=0; Device a,b; a.peer=&b; b.peer=&a;
  a.scr_w(0xf6); b.scr_w(0xf6); a.wire.clear(); b.wire.clear();
  a.queue(value); b.queue(value^0xff); a.queue(value^1); b.queue(value^0xfe);
  for (now=1;now<=480;++now) {
   a.pulse(); b.pulse();
   if (now==144) { a.queue(value^0x55); b.queue(value^0xaa); }
  }
  CHECK(a.m_rdr==(value^0xff) && b.m_rdr==value);
  CHECK(a.m_ssr==0xe4 && b.m_ssr==0xe4); // retained RX byte, ORER, completed TX
  CHECK(a.wire.size()==30 && b.wire.size()==30 && !a.m_sci_tx_active && !b.m_sci_tx_active);
  a.no_timers(); b.no_timers();
 }
 for (unsigned value=0;value<256;++value) for (unsigned phase=0;phase<16;++phase) {
  now=0; Device d; d.scr_w(0x22); d.wire.clear(); d.queue(value); d.advance(16+phase);
  CHECK(d.m_sci_tx_phase==phase);
  Device replay=d; replay.rebind(); const auto saved_time=now;
  replay.sck_w(1); CHECK(replay.m_sci_tx_phase==phase);
  d.advance(160); now=saved_time; replay.advance(160);
  CHECK(d.wire==replay.wire && d.irqs==replay.irqs && d.m_ssr==replay.m_ssr);
  CHECK(d.m_sci_tx_phase==replay.m_sci_tx_phase); ++replays;
 }
 now=0; Device late; late.scr_w(0x22); late.wire.clear(); late.queue(0x81);
 late.advance(152); late.queue(0x42); CHECK(late.wire.size()==10);
 late.advance(160); CHECK(late.wire.size()==11 && late.wire.back().first==160 && late.wire.back().second==0);
 late.advance(320); CHECK(!late.m_sci_tx_active && late.wire.size()==20); late.no_timers();
 now=0; Device cancel; cancel.scr_w(0x22); cancel.wire.clear(); cancel.queue(0x55); cancel.queue(0xaa); cancel.advance(23);
 cancel.scr_w(2); CHECK(cancel.m_sci_tx_phase==0 && !cancel.m_sci_tx_active && cancel.txd==1);
 const auto count=cancel.wire.size(); cancel.scr_w(0x22); cancel.advance(320); CHECK(cancel.wire.size()==count);
 now=0; Device internal; internal.scr_w(0x20); internal.wire.clear(); internal.queue(0x55);
 CHECK(internal.tx.due!=attotime::never.value); internal.advance(32);
 CHECK(internal.wire.size()==1 && internal.m_sci_tx_phase==0); // pin clocks ignored in internal mode
 std::printf("method-level, unvalidated: %u external asynchronous three-frame streams; 256 two-device duplex cases; %u divider state-copy replays\n",streams,replays);
 std::puts("method-level, unvalidated: no internal timers, BRR independence, late queue, RX-overrun isolation and TE cancellation exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-ext-async-tx-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_sci_tx_phase));' in source
assert 'm_sci_tx_phase = 0;' in source
print('method-level, unvalidated: external TX divider reset/save registration present')

#!/usr/bin/env python3
"""SCI asynchronous TX extraction checks; method-level, unvalidated.

Independent virtual-clock frame oracle. Does not run MAME, a CPU, real IRQ
arbitration, a physical cable, or the save manager. Existing fixtures untouched.
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
    ('ssr_r', 'uint8_t'), ('ssr_w', 'void'), ('tdr_w', 'void'),
    ('scr_w', 'void'), ('sci_transmit_start', 'void'),
    ('sci_recalc_rates', 'void'), ('sci_bit_period', 'attotime')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sci_tx_tick\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sci_tx_tick(int param)\n' + match[0].split('\n', 1)[1]

head = r'''
#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <utility>
#include <limits>
#define BIT(v,n) (((v) >> (n)) & 1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using tick_t = int64_t;
static tick_t now=0;
struct attotime {
 tick_t value;
 static const attotime never;
 static attotime from_ticks(tick_t ticks, unsigned) { return {ticks}; }
 attotime operator/(int n) const { return {value/n}; }
};
const attotime attotime::never{std::numeric_limits<tick_t>::max()};
struct Timer {
 tick_t due=attotime::never.value; int param=0;
 void adjust(attotime delay, int p=0) { due=delay.value==attotime::never.value ? delay.value : now+delay.value; param=p; }
};
struct Device {
 static constexpr uint8_t SSR_TDRE=0x80, SSR_TEND=4, SSR_MPB=2;
 static constexpr uint8_t SSR_ORER=0x20, SSR_FER=0x10, SSR_PER=8;
 uint8_t m_scr=0, m_smr=0, m_brr=0, m_ssr=0x84, m_sci_ssr_read=0, m_tsr=0, m_tdr=0xff;
 uint8_t m_sci_tx_bit=0, m_sci_rx_state=0, m_sci_rx_phase=0;
 bool m_sci_tx_active=false, m_sci_tx_loaded=false, m_sci_rx_enabled=false;
 Timer tx, rx;
 Timer *m_sci_tx_timer=&tx, *m_sci_rx_timer=&rx;
 std::vector<std::pair<tick_t,int>> wire, irqs;
 // This fixture exercises register/async/external-edge methods, not the internal clock.
 void sci_update_sync_clock() {}
 uint8_t m_sci_tx_phase=0;
 Device &machine() { return *this; }
 bool side_effects_disabled() const { return false; }
 unsigned clock() const { return 1; } // attotime mock measures CPU phi ticks
 void m_write_txd(int bit) { wire.emplace_back(now,bit); }
 void sh2_recalc_irq() { irqs.emplace_back(now, m_ssr); }
'''
tail = r'''
 void advance(tick_t end) {
  while (tx.due<=end) {
   now=tx.due; const int param=tx.param; tx.due=attotime::never.value;
   sci_tx_tick(param);
  }
  now=end;
 }
 void queue(uint8_t data, int mp=0) {
  const uint8_t status=ssr_r(); CHECK(status & SSR_TDRE);
  tdr_w(data); ssr_w((status & 0x7e) | mp);
 }
};
static std::vector<int> frame(uint8_t data, int mode, int mp=0) {
 std::vector<int> bits{0};
 const int n=(mode&0x40)?7:8;
 int parity=(mode>>4)&1;
 for (int i=0;i<n;++i) { int bit=(data>>i)&1; bits.push_back(bit); parity^=bit; }
 if (mode&4) bits.push_back(mp);
 else if (mode&0x20) bits.push_back(parity);
 bits.push_back(1); if (mode&8) bits.push_back(1);
 return bits;
}
static void compare(const Device &d, const std::vector<int> &bits, tick_t period) {
 CHECK(d.wire.size()==bits.size());
 for (unsigned i=0;i<bits.size();++i) {
  CHECK(d.wire[i].first==i*period); CHECK(d.wire[i].second==bits[i]);
 }
}
int main() {
 unsigned cases=0;
 for (int chars : {0,0x40}) for (int stop : {0,8})
 for (int format : {0,0x20,0x30,4}) for (unsigned value=0;value<256;++value) {
  now=0; Device d; const int mode=chars|stop|format, mp=value&1;
  d.m_smr=mode; d.scr_w(0xa4); // TE, TIE, TEIE
  const tick_t bit=d.sci_bit_period().value;
  const auto first=frame(value,mode,mp);
  const tick_t length=first.size()*bit;
  d.queue(value,mp); CHECK(!(d.m_ssr&4));
  d.advance(bit+bit/2); d.queue(value^1,mp);
  // Enable-bit writes do not stretch the current data bit.
  const auto due=d.tx.due; const auto next=d.tx.param;
  d.scr_w(0x20); d.scr_w(0xa4);
  CHECK(d.tx.due==due && d.tx.param==next);
  d.advance(length-bit-1); CHECK(!(d.m_ssr & 0x84));
  CHECK(d.m_tsr==value); // parity must use the first byte, not the pending one
  d.advance(length-bit); CHECK((d.m_ssr&0x84)==0x80);
  CHECK(d.m_sci_tx_loaded && d.m_tsr==(value^1));
  CHECK(d.irqs.back().first==length-bit && (d.irqs.back().second&0x84)==0x80);
  d.advance(length-bit/2); d.queue(value^0xff,mp);
  // Method-level replay: clone state and timer due, not a save-manager test.
  Device replay=d; replay.m_sci_tx_timer=&replay.tx; replay.m_sci_rx_timer=&replay.rx;
  const auto snapshot_time=now;
  d.advance(3*length-bit-1); CHECK(!(d.m_ssr&4));
  d.advance(3*length-bit); CHECK(d.m_ssr&4); CHECK(d.m_sci_tx_active);
  d.advance(3*length); CHECK(!d.m_sci_tx_active);
  CHECK(!d.m_sci_tx_loaded && d.tx.due==attotime::never.value);
  auto expected=first;
  for (auto b : {value^1,value^0xff}) {
   auto nextframe=frame(b,mode,mp); expected.insert(expected.end(),nextframe.begin(),nextframe.end());
  }
  compare(d,expected,bit);
  now=snapshot_time; replay.advance(3*length);
  CHECK(replay.wire==d.wire && replay.irqs==d.irqs && replay.m_ssr==d.m_ssr);
  ++cases;
 }
 // A byte submitted halfway through the last stop bit waits for its end.
 now=0; Device late; late.scr_w(0x20); late.queue(0x81);
 const tick_t bit=late.sci_bit_period().value;
 late.advance(9*bit); CHECK(late.m_ssr&4);
 late.advance(9*bit+bit/2); late.queue(0x42); CHECK(!(late.m_ssr&4));
 CHECK(late.wire.size()==10);
 late.advance(20*bit);
 auto expected=frame(0x81,0); auto second=frame(0x42,0);
 expected.insert(expected.end(),second.begin(),second.end()); compare(late,expected,bit);
 // TE=0 cancels a queued TSR as well as the timer; reenabling sends nothing.
 now=0; Device aborted; aborted.scr_w(0x20); aborted.queue(0x55);
 aborted.advance(bit); aborted.queue(0xaa); aborted.advance(9*bit);
 CHECK(aborted.m_sci_tx_loaded); aborted.scr_w(0); const auto count=aborted.wire.size();
 CHECK(!aborted.m_sci_tx_loaded && !aborted.m_sci_tx_active);
 aborted.scr_w(0x20); aborted.advance(30*bit);
 CHECK(aborted.wire.size()==count && (aborted.m_ssr&0x84)==0x84);
 std::printf("method-level, unvalidated: %u three-frame format/data cases; exact bit traces and state-copy replay\n",cases);
 std::puts("method-level, unvalidated: late queue, stop-bit hold, IRQ refresh and TE cancellation exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-tx-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_sci_tx_loaded));' in source
assert 'm_sci_tx_loaded = false;' in source
print('method-level, unvalidated: queued-TSR reset/save registration present')

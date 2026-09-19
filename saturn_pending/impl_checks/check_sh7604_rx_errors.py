#!/usr/bin/env python3
"""Extract SCI RX methods; method-level, unvalidated, not hardware acceptance.

The independent completion oracle is SH7604 Table 13.14. Bit input exercises
parity followed by framing status, error stalls, and acknowledgement recovery.
Optional source path permits a pre-change negative control without editing it.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('ssr_r', 'uint8_t'), ('ssr_w', 'void'), ('sci_rx_complete', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sci_rx_tick\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sci_rx_tick(int param)\n' + match[0].split('\n', 1)[1]
head = r'''
#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#define BIT(v,n) (((v) >> (n)) & 1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
struct Timer { void adjust(int, int) {} };
struct Device {
 static constexpr uint8_t SSR_TDRE=0x80, SSR_RDRF=0x40, SSR_ORER=0x20,
  SSR_FER=0x10, SSR_PER=8, SSR_TEND=4, SSR_MPB=2;
 uint8_t m_scr=0x50, m_smr=0, m_ssr=0x84, m_sci_ssr_read=0, m_tsr=0, m_tdr=0xff, m_rdr=0xa5;
 uint8_t m_sci_rx_state=0, m_sci_rx_phase=0, m_sci_rx_shift=0, m_sci_rx_bitcnt=0;
 bool m_sci_tx_active=false, m_sci_rx_enabled=true, m_sci_rx_parity_error=false;
 Timer timer; Timer *m_sci_rx_timer=&timer;
 int line=1, irqs=0;
 Device &machine() { return *this; }
 bool side_effects_disabled() const { return false; }
 int sci_bit_period() const { return 16; }
 int m_read_rxd(int) { return line; }
 void sci_transmit_start() { std::abort(); }
 void sh2_recalc_irq() { ++irqs; }
'''
tail = r'''
 void pulses(int value, int count=16) {
  line=value; for (int i=0;i<count;++i) sci_rx_tick(0);
 }
 void clear_rx_flags() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
};
int main() {
 unsigned direct=0, frames=0;
 // Table 13.14 encoded explicitly: index is ORER condition, FER, PER.
 constexpr uint8_t flags[8]={0x40,0x08,0x10,0x18,0x60,0x68,0x70,0x78};
 for (unsigned old=0;old<256;++old) for (unsigned data=0;data<256;++data)
 for (unsigned error=0;error<8;++error) {
  Device d; d.m_rdr=old; if (error&4) d.m_ssr|=0x40;
  d.sci_rx_complete(data,error&1,error&2);
  CHECK(d.m_ssr==(0x84|flags[error]));
  CHECK(d.m_rdr==((error&4)?old:data)); CHECK(d.irqs==1); ++direct;
 }
 for (int chars : {0,0x40}) for (int stop : {0,8}) for (int odd : {0,0x10})
 for (unsigned value=0;value<256;++value) for (unsigned error=0;error<8;++error) {
  Device d; d.m_smr=chars|stop|odd|0x20;
  if (error&4) d.m_ssr|=0x40;
  const uint8_t initial=d.m_ssr;
  const int data_bits=chars?7:8;
  int parity=odd?1:0;
  d.pulses(0); // start, internally sampled on the oversampling clock
  for (int i=0;i<data_bits;++i) { const int bit=(value>>i)&1; d.pulses(bit); parity^=bit; }
  d.pulses(parity ^ (error&1));
  CHECK(d.m_ssr==initial && d.m_rdr==0xa5 && d.irqs==0);
  // Error publication waits for the stop sample, never parity alone.
  Device replay=d; replay.m_sci_rx_timer=&replay.timer;
  d.pulses((error&2)?0:1);
  CHECK(d.m_ssr==(0x84|flags[error]));
  CHECK(d.m_rdr==((error&4)?0xa5:(value & (chars?0x7f:0xff))));
  CHECK(d.irqs==1 && d.m_sci_rx_state==0);
  replay.pulses((error&2)?0:1);
  CHECK(replay.m_ssr==d.m_ssr && replay.m_rdr==d.m_rdr && replay.irqs==d.irqs);
  if (error) {
   // A held error blocks new input; acknowledgement permits the next frame.
   const auto ssr=d.m_ssr, rdr=d.m_rdr;
   d.pulses(0,192); CHECK(d.m_ssr==ssr && d.m_rdr==rdr && d.irqs==1);
   d.clear_rx_flags(); CHECK(!(d.m_ssr&0x78));
   d.pulses(1,32); d.pulses(0);
   for (int i=0;i<data_bits;++i) d.pulses(1);
   d.pulses((data_bits&1) ^ (odd?1:0)); d.pulses(1);
   CHECK((d.m_ssr&0x78)==0x40 && d.m_rdr==(chars?0x7f:0xff));
  }
  ++frames;
 }
 std::printf("method-level, unvalidated: %u Table 13.14 data/status cases; %u received parity frames\n",direct,frames);
 std::puts("method-level, unvalidated: deferred errors, RDR retention, state-copy replay, stall/recovery exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-rx-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_sci_rx_parity_error));' in source
assert 'm_sci_rx_parity_error = false;' in source
print('method-level, unvalidated: pending parity reset/save registration present')

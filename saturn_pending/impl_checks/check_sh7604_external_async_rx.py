#!/usr/bin/env python3
"""External 16x SCK asynchronous receiver; method-level, unvalidated.

Uses the RX-error fixture's mock declarations, not its oracle. Actual SCK,
register, sampling and receive-completion methods are extracted. Positive RX
timer arms are counted to detect accidental internal clocking. No real MAME
scheduler/IRQ/save manager or physical clock margins are exercised.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock = Path(__file__).with_name('check_sh7604_rx_errors.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))
head = '#include <vector>\n' + head
head = head.replace('struct Timer { void adjust(int, int) {} };', '''
struct attotime { static constexpr int never=-1; };
struct Timer { unsigned arms=0; void adjust(int delay, int=0) { if (delay>=0) ++arms; } };''')
head = head.replace('m_scr=0x50', 'm_scr=0').replace('m_sci_rx_enabled=true', 'm_sci_rx_enabled=false')
head = head.replace('Timer timer; Timer *m_sci_rx_timer=&timer;', '''
 uint8_t m_brr=0, m_sci_tx_bit=0;
 bool m_sci_sck=true, m_sci_tx_loaded=false;
 Timer timer,tx; Timer *m_sci_rx_timer=&timer, *m_sci_tx_timer=&tx;
 void m_write_txd(int) {}
 void sci_sync_edge(bool) { std::abort(); }''')
head = head.replace('int sci_bit_period() const { return 16; }',
                    'int sci_bit_period() const { return (unsigned(m_brr)+1) << (7+2*(m_smr&3)); }')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('sck_w', 'void'), ('scr_w', 'void'), ('brr_w', 'void'), ('smr_w', 'void'),
    ('sci_recalc_rates', 'void'), ('ssr_r', 'uint8_t'), ('ssr_w', 'void'), ('sci_rx_complete', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sci_rx_tick\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sci_rx_tick(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void pulse(int value) {
  line=!value; sck_w(0); sck_w(0); // no sample on falling/repeated level
  line=value; sck_w(1); sck_w(7); // nonzero is high, not another edge
 }
 void frame(uint8_t data, bool badstop=false) {
  for (int i=0;i<16;++i) pulse(0);
  for (int bit=0;bit<8;++bit) for (int i=0;i<16;++i) pulse((data>>bit)&1);
  for (int i=0;i<16;++i) pulse(!badstop);
 }
 void ack() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
 void rebind() { m_sci_rx_timer=&timer; m_sci_tx_timer=&tx; }
};
int main() {
 unsigned frames=0, replays=0;
 for (unsigned chars : {0U,0x40U}) for (unsigned format : {0U,0x20U,0x30U,4U})
 for (unsigned stops : {0U,8U}) for (unsigned cks=0;cks<4;++cks)
 for (unsigned cke : {2U,3U}) for (unsigned value=0;value<256;++value) {
  Device d; d.smr_w(chars|format|stops|cks); d.brr_w((value*17+cks)&255); d.scr_w(0x50|cke); d.irqs=0;
  CHECK(d.m_sci_rx_enabled && d.timer.arms==0);
  const unsigned n=chars?7:8;
  std::vector<int> bits{0}; unsigned parity=(format>>4)&1;
  for (unsigned i=0;i<n;++i) { bits.push_back((value>>i)&1); parity^=bits.back(); }
  if (format==4) bits.push_back(value&1);
  else if (format) bits.push_back(parity);
  bits.push_back(1);
  const unsigned stop_sample=16*(bits.size()-1)+8;
  for (unsigned pulse=0;pulse<stop_sample;++pulse) {
   d.pulse(bits[pulse/16]); CHECK(d.irqs==0 && !(d.m_ssr&0x78));
  }
  d.pulse(1);
  CHECK(d.irqs==1 && (d.m_ssr&0x78)==0x40 && d.m_rdr==(value & (chars?0x7f:0xff)));
  CHECK((d.m_ssr&2)==(format==4 ? (value&1)*2 : 0));
  CHECK(d.timer.arms==0); ++frames;
 }
 // The BRR divider never supplies extra external-mode receiver samples.
 for (unsigned brr=0;brr<256;++brr) {
  Device d; d.smr_w(brr&3); d.brr_w(brr); d.scr_w(0x52); d.frame(0x93);
  CHECK(d.m_rdr==0x93 && d.timer.arms==0);
  d.frame(0x69,true); CHECK(d.m_rdr==0x93 && d.m_ssr==0xf4 && d.timer.arms==0);
  d.frame(0x55); CHECK(d.m_ssr==0xf4 && d.timer.arms==0);
  d.ack(); d.frame(0x69); CHECK(d.m_ssr==0xc4 && d.m_rdr==0x69 && d.timer.arms==0);
 }
 for (unsigned value=0;value<256;++value)
 for (unsigned cut : {0U,7U,8U,15U,16U,23U,24U,143U,144U,151U}) {
  Device d; d.scr_w(0x52);
  for (unsigned i=0;i<=cut;++i) d.pulse(i<16?0:(i<144?((value>>(i/16-1))&1):1));
  Device replay=d; replay.rebind(); replay.sck_w(1); // repeated level after state-copy restore
  for (unsigned i=cut+1;i<=152;++i) {
   const auto bit=i<16?0:(i<144?((value>>(i/16-1))&1):1);
   d.pulse(bit); replay.pulse(bit);
  }
  CHECK(d.m_rdr==value && replay.m_rdr==value && d.m_ssr==replay.m_ssr && d.irqs==replay.irqs);
  CHECK(d.timer.arms==0 && replay.timer.arms==0); ++replays;
 }
 // RE=0 ignores clocks; RE re-enable abandons the partial character.
 Device stopped; stopped.scr_w(0x52);
 for (int i=0;i<40;++i) stopped.pulse(0);
 stopped.scr_w(0x42); stopped.frame(0x55); CHECK(stopped.m_ssr==0x84);
 stopped.scr_w(0x52); stopped.frame(0xa6); CHECK(stopped.m_rdr==0xa6 && stopped.timer.arms==0);
 // Switching clocks while disabled must restore the internal timer path.
 stopped.scr_w(0); stopped.scr_w(0x10); CHECK(stopped.timer.arms==1);
 const auto before=stopped.m_sci_rx_phase; stopped.pulse(0); CHECK(stopped.m_sci_rx_phase==before);
 // False start is rejected at rising pulse eight after detection.
 Device glitch; glitch.scr_w(0x52); glitch.pulse(0);
 for (int i=1;i<8;++i) glitch.pulse(0);
 glitch.pulse(1); CHECK(glitch.m_sci_rx_state==0 && glitch.m_ssr==0x84 && glitch.timer.arms==0);
 std::printf("method-level, unvalidated: %u external-clock async format/data frames; %u phase state-copy replays\n",frames,replays);
 std::puts("method-level, unvalidated: BRR independence, edge filtering, no RX timer arms, errors and clock-mode controls exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-ext-async-rx-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

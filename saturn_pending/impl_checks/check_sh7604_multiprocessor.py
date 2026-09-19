#!/usr/bin/env python3
"""SCI multiprocessor receive filter; method-level, unvalidated.

Uses the RX-error check's mock declarations only, never its oracle or results.
Optional source path supports a pre-change negative control.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock_path = Path(__file__).with_name('check_sh7604_rx_errors.py')
head = next(ast.literal_eval(node.value) for node in ast.parse(mock_path.read_text()).body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in node.targets))

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('ssr_r', 'uint8_t'), ('ssr_w', 'void'), ('sci_rx_complete', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sci_rx_tick\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sci_rx_tick(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void pulses(int value, int count=16) {
  line=value; for (int i=0;i<count;++i) sci_rx_tick(0);
 }
 void body(uint8_t value, int mp) {
  pulses(0); const int n=(m_smr&0x40)?7:8;
  for (int i=0;i<n;++i) pulses((value>>i)&1);
  pulses(mp);
 }
 void acknowledge() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
};
int main() {
 unsigned cases=0;
 for (int chars : {0,0x40}) for (int stop : {0,8})
 for (unsigned value=0;value<256;++value) for (unsigned options=0;options<32;++options) {
  // Independent control dimensions: MPIE, old MPB, received MPB, RDRF, bad stop.
  const bool wait=options&1, oldmp=options&2, mp=options&4, full=options&8, badstop=options&16;
  Device d; d.m_scr=0x50|(wait?8:0);
  // PE and O/E set deliberately: MP mode must use the MP bit, not parity.
  d.m_smr=chars|stop|0x34; d.m_ssr=0x84|(oldmp?2:0)|(full?0x40:0);
  const auto oldstatus=d.m_ssr;
  d.body(value,mp);
  CHECK(d.m_ssr==oldstatus && d.m_rdr==0xa5 && d.irqs==0);
  Device replay=d; replay.m_sci_rx_timer=&replay.timer;
  d.pulses(!badstop);
  const bool accept=!wait || mp;
  unsigned expected=0x84|(mp?2:0)|(full?0x40:0);
  if (accept) {
   if (badstop) expected|=0x10;
   if (full) expected|=0x20;
   else if (!badstop) expected|=0x40;
  }
  CHECK(d.m_ssr==expected);
  CHECK(d.m_scr==(0x50|((wait&&!mp)?8:0)));
  CHECK(d.m_rdr==((!accept||full)?0xa5:(value & (chars?0x7f:0xff))));
  CHECK(d.irqs==(accept?1:0));
  replay.pulses(!badstop);
  CHECK(replay.m_ssr==d.m_ssr && replay.m_scr==d.m_scr && replay.m_rdr==d.m_rdr);
  ++cases;
 }
 // Address followed by data: hardware clears MPIE; MPB then returns to zero.
 Device sequence; sequence.m_smr=4; sequence.m_scr=0x58;
 sequence.body(0x23,1); sequence.pulses(1);
 CHECK(sequence.m_scr==0x50 && sequence.m_rdr==0x23 && (sequence.m_ssr&0x42)==0x42);
 sequence.acknowledge(); sequence.pulses(1,32);
 sequence.body(0x69,0); sequence.pulses(1);
 CHECK(sequence.m_rdr==0x69 && (sequence.m_ssr&0x42)==0x40);
 // Software rejects the address/re-arms MPIE: bad data cannot overwrite RDR
 // or manufacture an error while waiting for another address.
 sequence.acknowledge(); sequence.m_scr|=8; sequence.pulses(1,32);
 sequence.body(0x96,0); sequence.pulses(0);
 CHECK(sequence.m_rdr==0x69 && !(sequence.m_ssr&0x78) && (sequence.m_scr&8));
 sequence.pulses(1,32); sequence.body(0x45,1); sequence.pulses(1);
 CHECK(sequence.m_rdr==0x45 && (sequence.m_ssr&0x42)==0x42 && !(sequence.m_scr&8));
 // With MP=0, MPIE is ignored, and MPB is retained rather than interpreted.
 for (int oldmp : {0,2}) {
  Device normal; normal.m_scr=0x58; normal.m_ssr|=oldmp;
  normal.pulses(0);
  for (int i=0;i<8;++i) normal.pulses((0x93>>i)&1);
  normal.pulses(1);
  CHECK(normal.m_rdr==0x93 && normal.m_ssr==(0xc4|oldmp) && normal.m_scr==0x58);
 }
 std::printf("method-level, unvalidated: %u MP-format/filter/error/data cases and state-copy replay\n",cases);
 std::puts("method-level, unvalidated: address/data, software re-arm and non-MP controls exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-mp-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_sci_rx_mp));' in source
assert 'm_sci_rx_mp = false;' in source
print('method-level, unvalidated: pending MP bit reset/save registration present')

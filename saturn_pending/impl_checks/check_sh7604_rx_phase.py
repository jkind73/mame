#!/usr/bin/env python3
"""SCI 16x RX sampling phase; method-level, unvalidated.

The independent oracle numbers pulses after start detection as 1..8, then
expects data/stop samples at 8+16*n (SH7604 Figure 13.21). Reuses mock
endpoints from the RX-error check only. Optional pre-change source path.
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
head = '#include <vector>\n' + head
match = re.search(r'^void sh7604_device::sci_rx_complete\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions = match[0].replace('sh7604_device::', '')
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sci_rx_tick\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sci_rx_tick(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void pulse(int value) { line=value; sci_rx_tick(0); }
};
int main() {
 // A false start is rejected at pulse 8, not 9.
 Device rejected; rejected.pulse(0);
 for (int tick=1;tick<8;++tick) rejected.pulse(0);
 CHECK(rejected.m_sci_rx_state==1 && rejected.m_sci_rx_bitcnt==0);
 rejected.pulse(1); CHECK(rejected.m_sci_rx_state==0 && rejected.irqs==0);
 unsigned frames=0, glitches=0;
 for (int chars : {0,0x40}) for (int format : {0,0x20,0x30,4})
 for (int stop : {0,8}) for (unsigned value=0;value<256;++value) {
  Device d; d.m_smr=chars|format|stop;
  std::vector<int> bits{0}; int parity=(format>>4)&1;
  const int n=chars?7:8;
  for (int i=0;i<n;++i) { bits.push_back((value>>i)&1); parity^=bits.back(); }
  if (format==4) bits.push_back(value&1);
  else if (format) bits.push_back(parity);
  bits.push_back(1); // receiver checks only the first stop, regardless of STOP
  const int end=(bits.size()-1)*16+8;
  for (int tick=0;tick<end;++tick) {
   d.pulse(bits[tick/16]);
   CHECK(d.irqs==0 && !(d.m_ssr&0x78));
   if (tick>=8 && (tick-8)%16==0) {
    CHECK(d.m_sci_rx_bitcnt==1+(tick-8)/16);
    const int collected=(tick-8)/16;
    if (collected>=1 && collected<=n)
     CHECK(d.m_sci_rx_shift==(value & ((1U<<collected)-1)));
   }
  }
  d.pulse(1);
  CHECK(d.irqs==1 && (d.m_ssr&0x78)==0x40);
  CHECK(d.m_rdr==(value & (chars?0x7f:0xff)));
  ++frames;
 }
 // One-oversample glitches immediately before/at/after each data midpoint
 // distinguish eighth-pulse sampling from seventh/ninth-pulse sampling.
 for (int bit=0;bit<8;++bit) for (int shift : {-1,0,1}) {
  Device d; const int sample=24+bit*16;
  for (int tick=0;tick<=152;++tick) {
   int line=tick<144?0:1; // 8N1 zero byte, good stop at 144
   if (tick==sample+shift) line=1;
   d.pulse(line);
  }
  CHECK(d.irqs==1 && (d.m_ssr&0x78)==0x40);
  CHECK(d.m_rdr==(shift==0 ? (1U<<bit) : 0));
  ++glitches;
 }
 std::printf("method-level, unvalidated: %u frame sample schedules; %u midpoint glitch probes; false-start edge\n",frames,glitches);
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-phase-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

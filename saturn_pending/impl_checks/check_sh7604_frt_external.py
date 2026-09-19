#!/usr/bin/env python3
"""FTCI rising-edge FRT clock; method-level, unvalidated.

Real pin/register/event methods. Optional pre-change source gets only a no-op
shim for its absent pin entry point, never altered counter or compare bodies.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
def literal(file, name):
    return next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name(file).read_text()).body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
head = literal('check_sh7604_frt_stop.py', 'head')
head = head.replace('ticks due=attotime::never.value;', 'ticks due=attotime::never.value; unsigned arms=0;')
head = head.replace('void adjust(attotime delay) {', 'void adjust(attotime delay) { if (delay.value!=attotime::never.value) ++arms;')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('device_reset', 'void'), ('frt_reset', 'void'), ('fmr_sbycr_w', 'void'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'), ('set_frt_input', 'void'),
    ('frc_r', 'uint16_t'), ('frc_w', 'void'), ('frc_tcr_w', 'void'),
    ('ftcsr_r', 'uint8_t'), ('ftcsr_w', 'void'), ('tocr_w', 'void'), ('ocra_b_w', 'void')))
for name in ('ftci_w', 'frt_compare_tick'):
    if 'void sh7604_device::'+name+'(' in source:
        functions += '\n' + extract(name, 'void')
    elif name == 'ftci_w':
        functions += '\nvoid ftci_w(int) {}\n' # pre-change had no external clock API
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_timer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_timer_callback(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void advance(ticks end) {
  CHECK(timer.due==attotime::never.value || timer.due>end); now=end;
 }
 void setup(unsigned initial,unsigned a,unsigned b,unsigned flags) {
  device_reset(); frc_tcr_w(3); frc_w(0,initial,0xffff);
  ocra_b_w(0,a,0xffff); tocr_w(0x10); ocra_b_w(0,b,0xffff);
  m_ftcsr=flags; sh2_timer_activate();
 }
 void rebind() { m_timer=&timer; }
};
'''
tail += 'struct Oracle {' + literal('check_sh7604_frt_compare.py', 'tail').split('struct Oracle {', 1)[1].split('int main()', 1)[0]
tail += r'''
int main() {
 unsigned streams=0,replays=0,controls=0,captures=0;
 for (unsigned initial=0;initial<65536;++initial) for (unsigned flags : {0U,1U,14U,15U}) {
  now=0; Device d; const unsigned a=initial, b=initial^0xffff;
  d.setup(initial,a,b,flags); Oracle o{uint16_t(initial),uint16_t(a),uint16_t(b),uint8_t(flags)};
  const auto arms=d.timer.arms; CHECK(d.timer.due==attotime::never.value);
  d.advance(now+10000); check(d,o); // phi time alone does not count
  for (unsigned pulse=0;pulse<5;++pulse) {
   d.advance(now+8); d.ftci_w(1); o.tick(); check(d,o);
   d.ftci_w(1); d.ftci_w(7); check(d,o); // same logical level
   d.advance(now+8); d.ftci_w(0); d.ftci_w(0); check(d,o);
   CHECK(d.timer.due==attotime::never.value && d.timer.arms==arms);
  }
  ++streams;
 }
 // Replay both low/high pin histories, with all small compare periods and
 // already latched flags. Repeated high after restore is not a new edge.
 for (unsigned a=0;a<256;++a) for (unsigned level=0;level<2;++level)
 for (unsigned flags : {0U,1U,14U,15U}) {
  now=0; Device d; d.setup(0,a,a/2,flags); d.advance(8); d.ftci_w(level);
  Device replay=d; replay.rebind(); const auto saved_time=now;
  auto finish=[&](Device &x) {
   const auto count=x.m_frc; x.ftci_w(level); CHECK(x.m_frc==count);
   for (unsigned n=0;n<4*(a+1);++n) { x.advance(now+8); x.ftci_w(0); x.advance(now+8); x.ftci_w(1); }
  };
  finish(d); now=saved_time; finish(replay);
  CHECK(d.m_frc==replay.m_frc && d.m_ftcsr==replay.m_ftcsr && d.m_frt_clock_input==replay.m_frt_clock_input);
  CHECK(d.irqs==replay.irqs && d.timer.arms==replay.timer.arms); ++replays;
 }
 // Internal selections ignore FTCI while retaining physical level history.
 for (unsigned cks=0;cks<3;++cks) for (unsigned value=0;value<256;++value) {
  now=0; Device d; d.device_reset(); d.frc_tcr_w(cks); d.frc_w(0,value,0xffff);
  const auto due=d.timer.due; d.ftci_w(1); d.ftci_w(0); d.ftci_w(1);
  CHECK(d.m_frc==value && d.timer.due==due && d.m_frt_clock_input);
  d.frc_tcr_w(3); d.ftci_w(1); CHECK(d.m_frc==value);
  d.ftci_w(0); d.advance(now+8); d.ftci_w(1); CHECK(d.m_frc==value+1); ++controls;
 }
 // Module stop ignores clock edges but not pin history. On release the
 // registers are initial; software must reselect external clock explicitly.
 for (unsigned level=0;level<2;++level) {
  now=0; Device d; d.setup(0,3,2,1); d.fmr_sbycr_w(0,2,0xff);
  for (unsigned n=0;n<16;++n) { d.advance(now+8); d.ftci_w(n&1); }
  d.ftci_w(level); CHECK(d.m_frc==0 && d.m_ftcsr==0 && d.m_frt_clock_input==bool(level));
  d.fmr_sbycr_w(0,0,0xff); d.frc_tcr_w(3); d.ftci_w(level); CHECK(d.m_frc==0);
  d.ftci_w(0); d.advance(now+8); d.ftci_w(1); CHECK(d.m_frc==1); ++controls;
 }
 // FTI captures the externally clocked count; it is not another count input.
 for (unsigned value=0;value<256;++value) {
  now=0; Device d; d.setup(value,0xffff,0xffff,0);
  d.ftci_w(1); const auto count=d.m_frc;
  d.set_frt_input(1); d.advance(now+8); d.set_frt_input(0);
  CHECK(d.m_frc==count && d.m_frc_icr==count && (d.m_ftcsr&0x80)); ++captures;
 }
 std::printf("method-level, unvalidated: %u external-clock streams; %u pin-history state-copy replays; %u clock-select/module-stop controls; %u independent FTI captures\n",streams,replays,controls,captures);
 std::puts("method-level, unvalidated: rising-only counts, no timer pacing, compare/clear/overflow, repeated levels and held-level mode transitions exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-frt-ext-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_frt_clock_input));' in source
assert 'm_frt_clock_input = false;' in source and 'm_frt_clock_input(false)' in source
print('method-level, unvalidated: FTCI pin-history constructor/reset/save registration present; save layout changed')

#!/usr/bin/env python3
"""FRT read-one/write-zero status acknowledgement; method-level, unvalidated.

Extracts production register, counter/event and reset methods. Uses the FRT
mock declarations, never its expected values. Virtual cycles and state-copy
replay do not qualify MAME IRQ delivery, save-manager or silicon timing.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock = Path(__file__).with_name('check_sh7604_frt_stop.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))
head = head.replace('bool side_effects_disabled() const { return false; }',
                    'bool inspect=false;\n bool side_effects_disabled() const { return inspect; }')
head = head.replace('struct Callback { bool isnull() const { return true; } void operator()(uint32_t) {} };', '''
struct Callback {
 bool bound=false; unsigned calls=0; uint32_t value=0;
 bool isnull() const { return !bound; }
 void operator()(uint32_t data) { ++calls; value=data; }
};
''')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('ftcsr_r', 'uint8_t'), ('ftcsr_w', 'void'), ('frt_reset', 'void'),
    ('device_reset', 'void'), ('fmr_sbycr_w', 'void'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'), ('set_frt_input', 'void'),
    ('tier_w', 'void'), ('frc_w', 'void'), ('tocr_w', 'void'), ('ocra_b_w', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_timer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_timer_callback(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void advance(ticks end) {
  unsigned events=0;
  while (timer.due<=end) {
   CHECK(++events<10000); now=timer.due; timer.due=attotime::never.value; sh2_timer_callback(0);
  }
  now=end;
 }
 void capture() {
  set_frt_input(1); advance(now+8); set_frt_input(0); // pulse width >= six phi
 }
 void rebind() { m_timer=&timer; }
};
static unsigned flags(unsigned packed) {
 return ((packed&1)?0x80:0) | ((packed&2)?8:0) | ((packed&4)?4:0) | ((packed&8)?2:0);
}
int main() {
 unsigned cases=0, replays=0, reads=0, reset_cases=0;
 for (unsigned old=0;old<32;++old) for (unsigned seen=0;seen<16;++seen)
 for (unsigned value=0;value<32;++value) {
  now=0; Device d; d.m_tier=0x8f; d.m_frc=1; d.m_ocra=100; d.m_ocrb=200;
  d.m_ftcsr=flags(old&15)|(old>>4); d.m_ftcsr_read=flags(seen);
  const unsigned data=flags(value&15)|(value>>4);
  // Independent bitwise oracle, not a copy of the production expression.
  unsigned expected=data&1, qualified=0;
  for (unsigned bit : {1U,2U,3U,7U}) {
   const bool remains=BIT(d.m_ftcsr,bit) && !(BIT(flags(seen),bit) && !BIT(data,bit));
   if (remains) expected|=1U<<bit;
   if (remains && BIT(flags(seen),bit)) qualified|=1U<<bit;
  }
  Device replay=d; replay.rebind();
  d.ftcsr_w(data); replay.ftcsr_w(data);
  CHECK(d.m_ftcsr==expected && d.m_ftcsr_read==qualified);
  CHECK(d.irqs.size()==1 && d.irq_requested==bool(expected&0x8e));
  CHECK(d.m_ftcsr==replay.m_ftcsr && d.m_ftcsr_read==replay.m_ftcsr_read);
  CHECK(d.timer.due==replay.timer.due && d.irqs==replay.irqs);
  ++cases; ++replays;
 }
 // Reserved-bit mask robustness: prohibited set bits never become stored
 // status. This does not assign other silicon effects to invalid writes.
 for (unsigned data=0;data<256;++data) {
  now=0; Device d; d.m_ftcsr=0x8f; d.ftcsr_r(); d.ftcsr_w(data);
  CHECK(d.m_ftcsr==(data&0x8f) && d.m_ftcsr_read==(data&0x8e));
 }
 // Normal reads qualify exactly the returned flags. Debugger reads neither
 // call the legacy CPU-read hook nor replace an earlier qualification.
 for (unsigned status=0;status<32;++status) for (unsigned prior=0;prior<16;++prior) {
  now=0; Device d; d.m_tier=0x81; d.m_frc=0x1234;
  const unsigned image=flags(status&15)|(status>>4);
  d.m_ftcsr=image; d.m_ftcsr_read=flags(prior); d.m_ftcsr_read_cb.bound=true;
  d.inspect=true; CHECK(d.ftcsr_r()==image);
  CHECK(d.m_ftcsr_read==flags(prior) && d.m_ftcsr_read_cb.calls==0);
  d.inspect=false; CHECK(d.ftcsr_r()==image);
  CHECK(d.m_ftcsr_read==(image&0x8e) && d.m_ftcsr_read_cb.calls==1);
  CHECK(d.m_ftcsr_read_cb.value==(0x81000000U|(image<<16)|0x1234U));
  ++reads;
 }
 // Each acknowledgement is consumed. A newly raised event cannot be
 // cleared by reusing its old read, or by inspecting it with the debugger.
 for (unsigned flag : {0x80U,8U,4U,2U}) {
  now=0; Device d; d.m_frc=1; d.m_ocra=100; d.m_ocrb=200; d.m_ftcsr=flag;
  d.ftcsr_w(0); CHECK(d.m_ftcsr==flag); // unread
  d.inspect=true; d.ftcsr_r(); d.ftcsr_w(0); CHECK(d.m_ftcsr==flag);
  d.inspect=false; d.ftcsr_r(); d.ftcsr_w(0); CHECK(d.m_ftcsr==0 && d.m_ftcsr_read==0);
  d.m_ftcsr|=flag; d.ftcsr_w(0); CHECK(d.m_ftcsr==flag);
  d.ftcsr_r(); d.ftcsr_w(flag); CHECK(d.m_ftcsr==flag && d.m_ftcsr_read==flag);
  d.ftcsr_w(0); CHECK(d.m_ftcsr==0 && d.m_ftcsr_read==0);
  // Reading zero before the event does not acknowledge the future event.
  d.ftcsr_r(); d.m_ftcsr|=flag; d.ftcsr_w(1); CHECK(d.m_ftcsr==(flag|1));
 }
 // Real compare, overflow and capture event producers after reading zero.
 // The timer timeline is an integration probe, not physical phase evidence.
 now=0; Device events; events.device_reset(); events.tier_w(0x8f);
 events.ocra_b_w(0,0xfffe,0xffff); events.tocr_w(0x10); events.ocra_b_w(0,0xffff,0xffff);
 events.frc_w(0,0xfffd,0xffff); CHECK(events.ftcsr_r()==0);
 events.advance(24); CHECK(events.m_ftcsr==0x0e); events.capture();
 CHECK(events.m_ftcsr==0x8e && events.irq_requested);
 events.ftcsr_w(0); CHECK(events.m_ftcsr==0x8e && events.irq_requested);
 CHECK(events.ftcsr_r()==0x8e); events.ftcsr_w(0x86);
 CHECK(events.m_ftcsr==0x86 && events.m_ftcsr_read==0x86 && events.irq_requested);
 Device replay=events; replay.rebind(); const auto saved_time=now;
 auto acknowledge_and_rearm=[](Device &d) {
  d.ftcsr_w(0); CHECK(d.m_ftcsr==0 && d.m_ftcsr_read==0 && !d.irq_requested);
  d.capture(); CHECK(d.m_ftcsr==0x80 && d.irq_requested);
  d.ftcsr_w(0); CHECK(d.m_ftcsr==0x80);
  d.ftcsr_r(); d.ftcsr_w(0); CHECK(d.m_ftcsr==0 && !d.irq_requested);
 };
 acknowledge_and_rearm(events); now=saved_time; acknowledge_and_rearm(replay);
 CHECK(events.m_ftcsr==replay.m_ftcsr && events.m_ftcsr_read==replay.m_ftcsr_read);
 CHECK(events.irqs==replay.irqs && events.timer.due==replay.timer.due); ++replays;
 // Reset/module-stop clears read history as well as status. Use real capture
 // events after release to distinguish reset history from merely reset flags.
 for (unsigned kind=0;kind<2;++kind) for (unsigned prior=0;prior<16;++prior) {
  now=100; Device d; d.device_reset(); d.m_ftcsr=flags(prior); d.ftcsr_r();
  if (kind) {
   d.tier_w(1); d.fmr_sbycr_w(0,2,0xff); d.advance(now+1000); d.fmr_sbycr_w(0,0,0xff);
  } else d.device_reset();
  CHECK(d.m_ftcsr==0 && d.m_ftcsr_read==0);
  d.capture(); CHECK(d.m_ftcsr==0x80); d.ftcsr_w(0); CHECK(d.m_ftcsr==0x80);
  d.ftcsr_r(); d.ftcsr_w(0); CHECK(d.m_ftcsr==0 && d.m_ftcsr_read==0); ++reset_cases;
 }
 std::printf("method-level, unvalidated: %u status/read-history/write transitions; %u state-copy replays; %u CPU/debugger read cases; %u reset/module-stop cases\n",cases,replays,reads,reset_cases);
 std::puts("method-level, unvalidated: real compare/overflow/capture producers, selective clear, consumed acknowledgements, CPU-read callback and reserved-bit mask controls exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-ftcsr-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_ftcsr_read));' in source
assert 'm_ftcsr_read = 0;' in extract('frt_reset', 'void')
assert 'm_ftcsr_read(0)' in source
print('method-level, unvalidated: FTCSR read-history constructor/reset/save registration present; save layout changed')

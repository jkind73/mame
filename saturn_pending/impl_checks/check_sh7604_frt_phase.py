#!/usr/bin/env python3
"""FRT prescaler remainder and event deadlines; method-level, unvalidated.

Real methods with virtual CPU cycles; absolute floor(t/divisor) oracles.
Mock declarations reused, not prior expected values. Clock-switch startup
checks describe a provisional software convention, not silicon qualification.
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

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('device_reset', 'void'), ('frt_reset', 'void'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'), ('set_frt_input', 'void'),
    ('tier_w', 'void'), ('ftcsr_r', 'uint8_t'), ('ftcsr_w', 'void'),
    ('frc_r', 'uint16_t'), ('frc_w', 'void'), ('frc_tcr_w', 'void'),
    ('tocr_w', 'void'), ('ocra_b_w', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_timer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_timer_callback(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 std::vector<std::pair<ticks,int>> events;
 void advance(ticks end) {
  unsigned count=0;
  while (timer.due<=end) {
   CHECK(++count<10000); now=timer.due; timer.due=attotime::never.value;
   sh2_timer_callback(0); events.emplace_back(now,m_ftcsr);
  }
  now=end;
 }
 void setup(unsigned cks) {
  device_reset(); frc_tcr_w(cks); tier_w(0x8f);
  ocra_b_w(0,37,0xffff); tocr_w(0x10); ocra_b_w(0,53,0xffff);
 }
 void rebind() { m_timer=&timer; }
};
int main() {
 unsigned partitions=0, writes=0, replays=0, idle=0, wraps=0, switches=0;
 const ticks divisors[]{8,32,128};
 // Any polling partition must give the same count and event timestamps as
 // a device that runs without register reads. Include nonzero reset epochs.
 for (unsigned cks=0;cks<3;++cks) for (ticks epoch : {0,1,7,113})
 for (ticks stride=1;stride<=divisors[cks]+1;++stride) {
  const ticks period=divisors[cks]; now=epoch; Device polled; polled.setup(cks);
  Device control=polled; control.rebind();
  for (ticks t=stride;t<60*period;t+=stride) {
   polled.advance(epoch+t); CHECK(polled.frc_r()==t/period);
   CHECK(polled.timer.due==epoch+(t<37*period?37:t<53*period?53:65536)*period);
   CHECK((polled.m_ftcsr&0x0e)==unsigned((t>=37*period?8:0)|(t>=53*period?4:0)));
  }
  polled.advance(epoch+60*period); CHECK(polled.frc_r()==60);
  now=epoch; control.advance(epoch+60*period); CHECK(control.frc_r()==60);
  CHECK(polled.events==control.events && polled.irqs==control.irqs);
  CHECK(polled.events.size()==2);
  CHECK(polled.events[0].first==epoch+37*period && polled.events[1].first==epoch+53*period);
  CHECK(polled.m_frc_base==control.m_frc_base && polled.timer.due==control.timer.due);
  ++partitions;
 }
 // Non-clock-changing writes and capture edges must retain every possible
 // fractional divider phase, even though several call timer activation.
 for (unsigned cks=0;cks<3;++cks) for (ticks phase=0;phase<divisors[cks];++phase)
 for (unsigned op=0;op<6;++op) {
  const ticks period=divisors[cks], epoch=123; now=epoch; Device d; d.setup(cks);
  d.set_frt_input(1); d.advance(epoch+10*period+phase);
  switch (op) {
   case 0: d.tier_w(0x81); break;
   case 1: d.tocr_w(0x13); break;
   case 2: d.frc_tcr_w(0x80|cks); break; // IEDG only, unchanged CKS
   case 3: d.ftcsr_w(0x8e); break; // keep status, CCLRA remains zero
   case 4: d.ocra_b_w(0,53,0xffff); break; // unchanged OCRB
   case 5: d.set_frt_input(0); CHECK(d.m_frc_icr==10); break;
  }
  CHECK(d.frc_r()==10 && d.m_frc_base==uint64_t(epoch+10*period));
  CHECK(d.timer.due==epoch+37*period);
  Device replay=d; replay.rebind(); const auto saved_time=now;
  auto finish=[&](Device &x) {
   x.advance(epoch+37*period); CHECK((x.m_ftcsr&8) && x.m_frc==37);
   CHECK(x.timer.due==epoch+53*period);
   x.advance(epoch+55*period); CHECK(x.frc_r()==55 && (x.m_ftcsr&0x0e)==0x0c);
  };
  finish(d); now=saved_time; finish(replay);
  CHECK(d.events==replay.events && d.irqs==replay.irqs && d.m_frc_base==replay.m_frc_base);
  CHECK(d.timer.due==replay.timer.due && d.m_ftcsr==replay.m_ftcsr);
  ++writes; ++replays;
 }
 // All event flags already latched: no callback is scheduled, but counting
 // and wraparound still follow the divider independently of read cadence.
 for (unsigned cks=0;cks<3;++cks) for (ticks stride=1;stride<=divisors[cks]+1;++stride) {
  now=0; Device d; d.setup(cks); d.frc_w(0,0xfff0,0xffff);
  d.m_ftcsr=0x0e; d.sh2_timer_activate(); CHECK(d.timer.due==attotime::never.value);
  const ticks period=divisors[cks];
  for (ticks t=stride;t<100*period;t+=stride) {
   d.advance(t); CHECK(d.frc_r()==uint16_t(0xfff0+t/period));
   CHECK(d.m_frc_base==uint64_t((t/period)*period) && d.m_ftcsr==0x0e);
   CHECK(d.timer.due==attotime::never.value);
  }
  ++idle;
 }
 // Poll through overflow and compare events across the 16-bit wrap.
 for (unsigned cks=0;cks<3;++cks) for (ticks stride=1;stride<=divisors[cks]+1;++stride) {
  now=99; Device d; d.setup(cks); d.frc_w(0,0xfff0,0xffff);
  d.tocr_w(0); d.ocra_b_w(0,4,0xffff); d.tocr_w(0x10); d.ocra_b_w(0,9,0xffff);
  const ticks period=divisors[cks];
  for (ticks t=stride;t<30*period;t+=stride) {
   d.advance(99+t); CHECK(d.frc_r()==uint16_t(0xfff0+t/period));
  }
  d.advance(99+30*period); CHECK(d.events.size()==3);
  CHECK(d.events[0]==std::make_pair(99+16*period,2));
  CHECK(d.events[1]==std::make_pair(99+20*period,10));
  CHECK(d.events[2]==std::make_pair(99+25*period,14)); ++wraps;
 }
 // Software-convention controls only: an actual CKS change establishes a
 // fresh interval. Do not turn an old large-divider remainder into an
 // unsigned delay underflow on a smaller divider. No external FTCI model.
 for (unsigned old=0;old<4;++old) for (unsigned next=0;next<4;++next) if (old!=next)
 for (ticks phase=0;phase<(old<3?divisors[old]:8);++phase) {
  now=1000; Device d; d.setup(old); const ticks previous=(old<3?divisors[old]:8);
  d.advance(now+5*previous+phase); const unsigned count=old<3?5:0;
  d.frc_tcr_w(next); CHECK(d.frc_r()==count && d.m_frc_base==uint64_t(now));
  const auto changed=now;
  if (next<3) {
   CHECK(d.timer.due==changed+(37-count)*divisors[next]);
   d.advance(changed+divisors[next]-1); CHECK(d.frc_r()==count);
   d.advance(changed+divisors[next]); CHECK(d.frc_r()==count+1);
  } else {
   CHECK(d.timer.due==attotime::never.value);
   d.advance(changed+10000); CHECK(d.frc_r()==count);
  }
  ++switches;
 }
 // Retain the existing zero-distance compare scheduling convention rather
 // than underflowing its delay. Its immediate-match hardware semantics are
 // explicitly outside this candidate's scope.
 for (unsigned cks=0;cks<3;++cks) {
  now=0; Device d; d.setup(cks); d.advance(10*divisors[cks]+3);
  d.tocr_w(0); d.ocra_b_w(0,10,0xffff); CHECK(d.timer.due==now);
  d.advance(now); CHECK(d.m_ftcsr&8); CHECK(d.timer.due==53*divisors[cks]);
 }
 std::printf("method-level, unvalidated: %u polling partitions; %u fractional-phase register/capture cases; %u state-copy replays; %u unscheduled-counter cases; %u wraparound schedules\n",partitions,writes,replays,idle,wraps);
 std::printf("method-level, unvalidated: %u clock-switch software-convention controls; three zero-distance delay-underflow controls\n",switches);
 std::puts("method-level, unvalidated: absolute count/event oracles and no-polling comparison exercised; native timing and clock-switch silicon phase not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-frt-phase-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_frc_base));' in source
print('method-level, unvalidated: existing saved/reset cycle epoch reused; no new state fields')

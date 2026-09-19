#!/usr/bin/env python3
"""FTOA/FTOB compare outputs; method-level, unvalidated.

Real timer/pin/register methods against scalar level and count evolution.
Callbacks record logical transitions, not physical propagation or pin drive.
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
head = head.replace(' void m_write_ftoa(int) {}\n void m_write_ftob(int) {}', '''
 using Edge=std::tuple<ticks,int,int,unsigned,unsigned,unsigned>;
 std::vector<Edge> wave;
 void m_write_ftoa(int level) { wave.emplace_back(now,0,level,m_frc,m_frt_out_a|(m_frt_out_b<<1),m_ftcsr); }
 void m_write_ftob(int level) { wave.emplace_back(now,1,level,m_frc,m_frt_out_a|(m_frt_out_b<<1),m_ftcsr); }
''')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('device_reset', 'void'), ('frt_reset', 'void'), ('fmr_sbycr_w', 'void'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'), ('frt_compare_tick', 'void'),
    ('ftci_w', 'void'), ('frc_r', 'uint16_t'), ('frc_w', 'void'), ('frc_tcr_w', 'void'),
    ('ftcsr_r', 'uint8_t'), ('ftcsr_w', 'void'), ('tocr_w', 'void'), ('ocra_b_w', 'void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_timer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_timer_callback(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
 void advance(ticks end) {
  unsigned events=0;
  while (timer.due<=end) {
   CHECK(++events<100000); now=timer.due; timer.due=attotime::never.value; sh2_timer_callback(0);
  }
  now=end;
 }
 void setup(unsigned mode,unsigned a,unsigned b,unsigned status,unsigned levels) {
  device_reset(); frc_tcr_w(mode); ocra_b_w(0,a,0xffff); tocr_w(0x10); ocra_b_w(0,b,0xffff);
  m_ftcsr=status; tocr_w(levels); wave.clear();
 }
 void rebind() { m_timer=&timer; }
};
struct Oracle {
 uint16_t count=0,a,b; uint8_t status; unsigned levels=0;
 std::vector<Device::Edge> wave;
 void step(unsigned selected,ticks time) {
  const auto before=count; ++count; const auto old=levels;
  if (before==a) { status|=8; levels=(levels&2)|((selected>>1)&1); }
  if (before==b) { status|=4; levels=(levels&1)|((selected&1)<<1); }
  if (before==0xffff) status|=2;
  if (before==a && (status&1)) count=0;
  if ((old^levels)&1) wave.emplace_back(time,0,levels&1,count,levels,status);
  if ((old^levels)&2) wave.emplace_back(time,1,(levels>>1)&1,count,levels,status);
 }
};
int main() {
 unsigned streams=0,replays=0,resets=0;
 const ticks periods[]{8,32,128,16};
 // Change selected output levels halfway between count edges. TOCR writes
 // alone never move a pin. Match application is independent of flag state.
 for (unsigned mode=0;mode<4;++mode) for (unsigned a=0;a<64;++a)
 for (unsigned b : {0U,a,a/2,a+1,65535U}) for (unsigned initial=0;initial<4;++initial)
 for (unsigned flags : {0U,1U,14U,15U}) {
  const ticks epoch=111, period=periods[mode]; now=epoch; Device d;
  d.setup(mode,a,b,flags,initial); Oracle o{0,uint16_t(a),uint16_t(b),uint8_t(flags),0,{}};
  for (unsigned n=1;n<=2*(a+2)+3;++n) {
   d.advance(epoch+(n-1)*period+period/2); if (mode==3) d.ftci_w(0);
   const auto edges=d.wave.size(); const auto pins=d.m_frt_out_a|(d.m_frt_out_b<<1);
   const unsigned selected=(initial+n/3)&3; d.tocr_w(selected|((n&1)<<4));
   CHECK(d.wave.size()==edges && (d.m_frt_out_a|(d.m_frt_out_b<<1))==pins);
   d.advance(epoch+n*period); if (mode==3) d.ftci_w(1);
   o.step(selected,now);
   CHECK(d.frc_r(0,0xffff)==o.count && d.m_ftcsr==o.status);
   CHECK((d.m_frt_out_a|(d.m_frt_out_b<<1))==o.levels && d.wave==o.wave);
  }
  ++streams;
 }
 // Save with both outputs high, both flags latched and a pending selection
 // change to low. Internal scheduling must not skip the next compare just
 // because OCFA/OCFB have not been acknowledged.
 for (unsigned mode=0;mode<4;++mode) for (unsigned a=0;a<256;++a) {
  now=0; Device d; const ticks period=periods[mode]; d.setup(mode,a,a,15,3);
  auto pulse=[&](Device &x) { x.advance(now+period/2); x.ftci_w(0); x.advance(now+period/2); x.ftci_w(1); };
  if (mode==3) for (unsigned n=0;n<a+1;++n) pulse(d);
  else d.advance((a+1)*period);
  CHECK(d.m_frt_out_a && d.m_frt_out_b && d.wave.size()==2 && d.m_frc==0);
  d.advance(now+period/2); const auto edges=d.wave.size(); d.tocr_w(0);
  CHECK(d.m_frt_out_a && d.m_frt_out_b && d.wave.size()==edges);
  Device replay=d; replay.rebind(); const auto saved_time=now;
  auto finish=[&](Device &x) {
   if (mode==3) for (unsigned n=0;n<a+1;++n) pulse(x);
   else x.advance(now+(a+1)*period);
   CHECK(!x.m_frt_out_a && !x.m_frt_out_b && x.wave.size()==4);
  };
  finish(d); now=saved_time; finish(replay);
  CHECK(d.wave==replay.wave && d.m_ftcsr==replay.m_ftcsr && d.timer.due==replay.timer.due);
  ++replays;
 }
 // Reset and module stop drive low. Reset notifications can repeat the
 // current level; ordinary compare notifications are transitions only.
 for (unsigned mode=0;mode<4;++mode) for (unsigned kind=0;kind<2;++kind) {
  now=0; Device d; d.setup(mode,0,0,1,3);
  if (mode==3) { d.advance(8); d.ftci_w(1); } else d.advance(periods[mode]);
  CHECK(d.m_frt_out_a && d.m_frt_out_b);
  const auto edges=d.wave.size();
  if (kind) d.fmr_sbycr_w(0,2,0xff); else d.device_reset();
  CHECK(!d.m_frt_out_a && !d.m_frt_out_b && d.wave.size()==edges+2);
  CHECK(std::get<2>(d.wave[edges])==0 && std::get<2>(d.wave[edges+1])==0);
  CHECK(d.m_tocr==0xe0); ++resets;
 }
 std::printf("method-level, unvalidated: %u scalar-oracle output streams; %u pending-output state-copy replays; %u reset/module-stop output cases\n",streams,replays,resets);
 std::puts("method-level, unvalidated: internal/external clocks, latched flags, delayed OLVL application, simultaneous compares and post-clear callback state exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-frt-out-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
for field in ('m_frt_out_a','m_frt_out_b'):
    assert f'save_item(NAME({field}));' in source
    assert f'{field} = false;' in source and f'{field}(false)' in source
print('method-level, unvalidated: FTO level constructor/reset/save registrations present; save layout changed')

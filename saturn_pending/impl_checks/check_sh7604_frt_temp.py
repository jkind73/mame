#!/usr/bin/env python3
"""Shared FRT TEMP byte latch; method-level, unvalidated.

Real register/reset/event methods with virtual timers. Byte masks represent
big-endian high/low lanes, not a native address-space dispatch qualification.
Optional old source adapts read signatures only, preserving method bodies.
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

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    text = match[0].replace('sh7604_device::', '')
    if name in ('frc_r', 'frc_icr_r'):
        text = text.replace(name+'()', name+'(offs_t offset, uint16_t mem_mask)')
    return text

functions = '\n'.join(extract(n, t) for n, t in (
    ('device_reset', 'void'), ('frt_reset', 'void'), ('fmr_sbycr_w', 'void'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'), ('set_frt_input', 'void'),
    ('frc_r', 'uint16_t'), ('frc_w', 'void'), ('frc_icr_r', 'uint16_t'),
    ('tocr_w', 'void'), ('ocra_b_r', 'uint16_t'), ('ocra_b_w', 'void')))
if 'void sh7604_device::frt_compare_tick(' in source:
    functions += '\n' + extract('frt_compare_tick', 'void')
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
 void capture() { set_frt_input(1); advance(now+8); set_frt_input(0); }
 void rebind() { m_timer=&timer; }
 void write(unsigned target,uint16_t data,uint16_t mask) {
  if (target==0) frc_w(0,data,mask); else ocra_b_w(0,data,mask);
 }
 uint16_t value(unsigned target) const {
  return target==0?m_frc:target==1?m_ocra:m_ocrb;
 }
};
int main() {
 unsigned writes=0,snapshots=0,peeks=0,replays=0,shared=0,resets=0;
 // All byte pairs for all three writable words. A high-byte access must
 // not commit, change the event deadline or recalculate interrupts.
 for (unsigned target=0;target<3;++target) for (unsigned data=0;data<65536;++data) {
  now=0; Device d; d.device_reset(); d.frc_w(0,0x1357,0xffff);
  d.tocr_w(target==2?0x10:0); const auto before=d.value(target);
  const auto due=d.timer.due; const auto irqs=d.irqs.size();
  d.write(target,data&0xff00,0xff00);
  CHECK(d.value(target)==before && d.timer.due==due && d.irqs.size()==irqs);
  CHECK(d.m_frt_temp==(data>>8));
  Device replay=d; replay.rebind();
  d.write(target,data&0xff,0x00ff); replay.write(target,data&0xff,0x00ff);
  CHECK(d.value(target)==data && d.m_frt_temp==(data>>8));
  CHECK(d.value(target)==replay.value(target) && d.timer.due==replay.timer.due && d.irqs==replay.irqs);
  ++writes; ++replays;
 }
 // Read the high byte, allow the live register to change, then read the low
 // byte. Reconstructing the pair must give the original snapshot.
 for (unsigned target=0;target<2;++target) for (unsigned data=0;data<65536;++data) {
  now=0; Device d; d.device_reset();
  d.frc_w(0,target?uint16_t(data-1):data,0xffff);
  if (target) { d.capture(); CHECK(d.m_frc_icr==data); }
  const auto high=target?d.frc_icr_r(0,0xff00):d.frc_r(0,0xff00);
  CHECK((high>>8)==(data>>8) && d.m_frt_temp==(data&0xff));
  Device replay=d; replay.rebind(); const auto saved_time=now;
  auto finish=[&](Device &x) {
   if (target) x.capture(); else x.advance(now+8);
   const auto low=target?x.frc_icr_r(0,0x00ff):x.frc_r(0,0x00ff);
   CHECK(((high&0xff00)|(low&0xff))==data);
   CHECK(x.m_frt_temp==(data&0xff));
   CHECK((target?x.m_frc_icr:x.m_frc)==uint16_t(data+1));
  };
  finish(d); now=saved_time; finish(replay);
  CHECK(d.m_frt_temp==replay.m_frt_temp && d.m_frc==replay.m_frc && d.m_frc_icr==replay.m_frc_icr);
  CHECK(d.timer.due==replay.timer.due && d.irqs==replay.irqs);
  ++snapshots; ++replays;
 }
 // OCR reads are the explicit exception: they return live register bytes
 // without reading or modifying TEMP, including across OCRS changes.
 for (unsigned temp=0;temp<256;++temp) {
  now=0; Device d; d.device_reset(); d.m_ocra=0x1234; d.m_ocrb=0xabcd;
  d.frc_w(0,temp<<8,0xff00);
  d.tocr_w(0); CHECK(d.ocra_b_r()==0x1234 && d.m_frt_temp==temp);
  d.tocr_w(0x10); CHECK(d.ocra_b_r()==0xabcd && d.m_frt_temp==temp);
  d.frc_w(0,0x56,0xff); CHECK(d.m_frc==((temp<<8)|0x56)); ++shared;
 }
 // One latch, not one per register: intervening accesses overwrite it.
 // This models shared-latch interference; software must protect byte pairs.
 for (unsigned temp=0;temp<256;++temp) {
  now=0; Device d; d.device_reset(); d.frc_w(0,0x1200,0xff00);
  d.ocra_b_w(0,temp<<8,0xff00); d.frc_w(0,0x34,0xff);
  CHECK(d.m_frc==((temp<<8)|0x34));
  d.m_frc=0x56cd; d.m_frc_icr=0xab00|temp;
  CHECK((d.frc_r(0,0xff00)>>8)==0x56);
  CHECK((d.frc_icr_r(0,0xff00)>>8)==0xab);
  CHECK((d.frc_r(0,0xff)&0xff)==temp);
  // A read-low snapshot can supply the high byte of a later write-low.
  d.ocra_b_w(0,0x78,0xff); CHECK(d.m_ocra==((temp<<8)|0x78));
  // OCRS is evaluated at the low-byte commit, not saved by the high write.
  d.tocr_w(0); d.ocra_b_w(0,0x9a00,0xff00); d.tocr_w(0x10);
  d.ocra_b_w(0,0xbc,0xff); CHECK(d.m_ocrb==0x9abc && d.m_ocra==((temp<<8)|0x78));
  ++shared;
 }
 // Inspection returns live values without disturbing staged write data or
 // a read snapshot. It must not make a following CPU low read become live.
 for (unsigned target=0;target<2;++target) for (unsigned temp=0;temp<256;++temp)
 for (unsigned mask : {0xff00U,0x00ffU,0xffffU}) {
  now=0; Device d; d.device_reset(); d.m_frc=0x1234; d.m_frc_icr=0xabcd;
  d.m_frt_temp=temp; d.inspect=true;
  const auto value=target?d.frc_icr_r(0,mask):d.frc_r(0,mask);
  CHECK(value==(target?0xabcd:0x1234) && d.m_frt_temp==temp);
  d.inspect=false;
  CHECK(((target?d.frc_icr_r(0,0xff):d.frc_r(0,0xff))&0xff)==temp); ++peeks;
 }
 // Retain full-width callback compatibility as an ordered high/low pair;
 // this is not hardware qualification of word accesses (manual says bytes).
 for (unsigned value=0;value<65536;++value) {
  now=0; Device d; d.device_reset(); d.frc_w(0,value,0xffff);
  CHECK(d.m_frc==value && d.m_frt_temp==(value>>8));
  CHECK(d.frc_r(0,0xffff)==value && d.m_frt_temp==(value&0xff));
  d.m_frc_icr=value^0xffff;
  CHECK(d.frc_icr_r(0,0xffff)==(value^0xffff) && d.m_frt_temp==((value^0xffff)&0xff));
 }
 // Timer events can occur between write bytes without committing the staged
 // high byte. No CPU FRC read is inserted here: that would overwrite TEMP.
 for (unsigned phase=0;phase<8;++phase) {
  now=0; Device d; d.device_reset(); d.ocra_b_w(0,4,0xffff);
  d.advance(8+phase); const auto due=d.timer.due;
  d.frc_w(0,0xab00,0xff00); CHECK(d.timer.due==due);
  d.advance(40); CHECK(d.m_ftcsr&8); CHECK(d.m_frt_temp==0xab);
  d.frc_w(0,0x5a,0xff); CHECK(d.m_frc==0xab5a);
 }
 // Initializing TEMP to zero is a deterministic emulator reset convention;
 // do not infer a silicon value from a prohibited low-only first access.
 for (unsigned kind=0;kind<2;++kind) for (unsigned temp=0;temp<256;++temp) {
  now=0; Device d; d.device_reset(); d.frc_w(0,temp<<8,0xff00);
  if (kind) { d.fmr_sbycr_w(0,2,0xff); d.fmr_sbycr_w(0,0,0xff); }
  else d.device_reset();
  CHECK(d.m_frt_temp==0);
  d.frc_w(0,0x7800,0xff00); d.frc_w(0,0x56,0xff); CHECK(d.m_frc==0x7856); ++resets;
 }
 std::printf("method-level, unvalidated: %u byte-pair writes; %u changing-register read snapshots; %u state-copy replays; %u shared-latch/OCR-read cases; %u debugger inspections; %u reset cases\n",writes,snapshots,replays,shared,peeks,resets);
 std::puts("method-level, unvalidated: 65536 full-width compatibility controls and eight between-byte timer-event probes; native byte-lane dispatch and save-manager not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-frt-temp-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'save_item(NAME(m_frt_temp));' in source
assert 'm_frt_temp = 0;' in extract('frt_reset', 'void')
assert 'm_frt_temp(0)' in source
print('method-level, unvalidated: TEMP constructor/reset/save registration present; save layout changed')

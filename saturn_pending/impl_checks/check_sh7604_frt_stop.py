#!/usr/bin/env python3
"""Real FRT reset/module-stop methods; method-level, unvalidated.

Virtual CPU-cycle/timer harness. SCI and SH2 base reset/IRQ delivery are mocked.
Checks do not qualify native CPU timing, input synchronizers or save-manager.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)[^\n{]*\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('device_reset', 'void'), ('fmr_sbycr_w', 'void'), ('fmr_sbycr_r', 'uint16_t'),
    ('sh2_timer_resync', 'void'), ('sh2_timer_activate', 'void'), ('set_frt_input', 'void'),
    ('tier_r', 'uint8_t'), ('tier_w', 'void'), ('ftcsr_r', 'uint8_t'), ('ftcsr_w', 'void'),
    ('frc_r', 'uint16_t'), ('frc_w', 'void'), ('frc_tcr_r', 'uint8_t'), ('frc_tcr_w', 'void'),
    ('tocr_r', 'uint8_t'), ('tocr_w', 'void'), ('ocra_b_r', 'uint16_t'),
    ('ocra_b_w', 'void'), ('frc_icr_r', 'uint16_t')))
# Preserve pre-change reset bodies for the negative control.
if 'void sh7604_device::frt_reset()' in source:
    functions += '\n' + extract('frt_reset', 'void')
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_timer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_timer_callback(int param)\n' + match[0].split('\n', 1)[1]
head = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <utility>
#include <limits>
#include <tuple>
#define BIT(v,n) (((v) >> (n)) & 1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
using offs_t = unsigned;
using ticks = int64_t;
static ticks now=0;
static constexpr int div_tab[4]={3,5,7,0};
static constexpr int CLEAR_LINE=0, ASSERT_LINE=1;
struct attotime { ticks value; static const attotime never; };
const attotime attotime::never{std::numeric_limits<ticks>::max()};
struct Timer {
 ticks due=attotime::never.value;
 void adjust(attotime delay) { due=delay.value==attotime::never.value?delay.value:now+delay.value; }
};
struct Callback { bool isnull() const { return true; } void operator()(uint32_t) {} };
struct sh2_device { void device_reset() {} };
struct Device : sh2_device {
 static constexpr uint8_t ICF=0x80, OCFA=8, OCFB=4, OVF=2, CCLRA=1;
 uint8_t m_sbycr=0, m_tier=0, m_ftcsr=0, m_frc_tcr=0, m_tocr=0;
 uint16_t m_frc=0, m_ocra=0, m_ocrb=0, m_frc_icr=0;
 uint64_t m_frc_base=0; int m_frt_input=0;
 uint16_t m_iprb=0x8700, m_vcrc=0x1234, m_vcrd=0x5600;
 struct { uint8_t fic=0x12, foc=0x34, fov=0x56; } m_irq_vector;
 Timer timer; Timer *m_timer=&timer; Callback m_ftcsr_read_cb;
 unsigned sci_resets=0; bool irq_requested=false;
 std::vector<std::pair<ticks,int>> irqs;
 int m_dma_timer_active[2]{}, m_dma_irq[2]{}, m_active_dma_incs[2]{}, m_active_dma_incd[2]{};
 int m_active_dma_size[2]{}, m_active_dma_steal[2]{}, m_active_dma_src[2]{}, m_active_dma_dst[2]{}, m_active_dma_count[2]{};
 int m_wtcnt=23, m_wtcsr=24, m_barah=25, m_baral=26, m_barbh=27, m_barbl=28;
 void sci_reset() { ++sci_resets; }
 uint64_t total_cycles() const { return now; }
 attotime cycles_to_attotime(uint64_t cycles) const { return {ticks(cycles)}; }
 const char *tag() const { return "method-mock"; }
 template<class... Args> void logerror(const char *, Args...) {}
 void sh2_recalc_irq() {
  irq_requested=(m_tier&m_ftcsr&0x8e)!=0; irqs.emplace_back(now,irq_requested);
 }
'''
tail = r'''
 void advance(ticks end) {
  unsigned events=0;
  while (timer.due<=end) {
   CHECK(++events<10000); now=timer.due; timer.due=attotime::never.value; sh2_timer_callback(0);
  }
  now=end;
 }
 void stop(unsigned value) { fmr_sbycr_w(0,value,0x00ff); }
 auto regs() const { return std::make_tuple(m_tier,m_ftcsr,m_frc_tcr,m_tocr,m_frc,m_ocra,m_ocrb,m_frc_icr); }
 void initial_state() const {
  CHECK(m_tier==1 && m_ftcsr==0 && m_frc_tcr==0 && m_tocr==0xe0);
  CHECK(m_frc==0 && m_ocra==0xffff && m_ocrb==0xffff && m_frc_icr==0);
 }
 void vectors() const {
  CHECK(m_iprb==0x8700 && m_vcrc==0x1234 && m_vcrd==0x5600);
  CHECK(m_irq_vector.fic==0x12 && m_irq_vector.foc==0x34 && m_irq_vector.fov==0x56);
 }
 void finish() {
  stop(0); initial_state(); vectors(); CHECK(fmr_sbycr_r()==0);
  const auto release=now; CHECK(timer.due==release+65535*8);
  CHECK(tier_r()==1 && ftcsr_r()==0 && tocr_r()==0xe0 && frc_tcr_r()==0 && frc_icr_r()==0);
  CHECK(ocra_b_r()==0xffff && frc_r()==0);
  advance(release+7); CHECK(frc_r()==0);
  advance(release+8); CHECK(frc_r()==1);
  advance(release+65535*8);
  CHECK(m_frc==0xffff && m_ftcsr==0x0c && !irq_requested);
  advance(release+65536*8);
  CHECK(m_frc==0 && m_ftcsr==0x0e && !irq_requested);
 }
};
int main() {
 unsigned entries=0,replays=0,resets=0,controls=0,captures=0;
 for (unsigned mode=0;mode<4;++mode) for (unsigned value=0;value<256;++value)
 for (unsigned phase=0;phase<4;++phase) {
  now=97+value; Device d;
  // Configure an arbitrary prior state, with interrupts disabled as required
  // by section 14.5. FRT has no separate counter enable bit.
  d.m_tier=1; d.frc_tcr_w(mode | ((value&1)?0x80:0));
  d.frc_w(0,value*257,0xffff); d.ocra_b_w(0,(value*17+101)&0xffff,0xffff);
  d.tocr_w(0x13); d.ocra_b_w(0,(value*127+31)&0xffff,0xffff);
  d.m_frc_icr=value*251; d.m_ftcsr=0x8e;
  d.advance(now+phase*128);
  const auto sci=d.sci_resets; d.stop(2);
  d.initial_state(); d.vectors(); CHECK(d.sci_resets==sci && !d.irq_requested);
  CHECK(d.timer.due==attotime::never.value && d.fmr_sbycr_r()==2);
  const auto irq=d.irqs.size();
  d.advance(now+12345+value); d.stop(2); CHECK(d.irqs.size()==irq);
  // Only pin updates while stopped, not forbidden FRT register accesses.
  for (unsigned edge=0;edge<8;++edge) { d.advance(now+16); d.set_frt_input(edge&1); }
  d.advance(now+1000000); d.initial_state(); CHECK(d.irqs.size()==irq);
  // Defensive entry-point probes are not CPU register transactions.
  d.sh2_timer_resync(); d.sh2_timer_activate(); d.sh2_timer_callback(0);
  d.initial_state(); CHECK(d.timer.due==attotime::never.value && d.irqs.size()==irq);
  Device replay=d; replay.m_timer=&replay.timer; const auto saved_time=now;
  d.finish(); now=saved_time; replay.finish();
  CHECK(d.regs()==replay.regs() && d.irqs==replay.irqs && d.timer.due==replay.timer.due);
  CHECK(d.m_frc_base==replay.m_frc_base && d.m_frt_input==replay.m_frt_input);
  ++entries; ++replays;
 }
 // Device reset has the same initial register image even at nonzero cycles;
 // it releases MSTP1 and starts counting rather than leaving a stale timer.
 for (unsigned value=0;value<256;++value) {
  now=100000+value*19; Device d; d.m_sbycr=3; d.m_tier=0xff; d.m_ftcsr=0x8f;
  d.m_frc_tcr=0x83; d.m_tocr=0x13; d.m_frc=0xa5a5; d.m_ocra=12; d.m_ocrb=34;
  d.timer.adjust({3}); d.device_reset(); d.initial_state();
  CHECK(d.m_sbycr==0 && d.m_frc_base==uint64_t(now) && d.m_frt_input==0 && d.sci_resets==1);
  const auto start=now; d.advance(start+8); CHECK(d.frc_r()==1 && d.ftcsr_r()==0);
  CHECK(d.timer.due==start+65535*8); ++resets;
 }
 // Unrelated SBYCR bits and existing FMR byte/word routing do not reset FRT.
 for (unsigned value=0;value<256;++value) if (!(value&0x22))
 for (unsigned mask : {0x00ffU,0xff00U,0xffffU}) {
  now=1234; Device d; d.m_tier=1; d.m_frc=0x1234; d.m_frc_tcr=1;
  d.m_ocra=0xabcd; d.m_ocrb=0x9876; d.sh2_timer_activate();
  const auto regs=d.regs(); const auto due=d.timer.due;
  d.fmr_sbycr_w(0,value,mask); CHECK(d.regs()==regs && d.timer.due==due); ++controls;
 }
 for (unsigned mask : {0xff00U,0xffffU}) {
  now=0; Device d; d.m_frc=0x2345; d.fmr_sbycr_w(0,0x0202,mask);
  CHECK(d.m_sbycr==0 && d.m_frc==0x2345); ++controls;
 }
 // Captures are suppressed during stop, with physical level history retained
 // so a repeated held level on release cannot manufacture a capture edge.
 for (unsigned before=0;before<2;++before) for (unsigned held=0;held<2;++held)
 for (unsigned delay=0;delay<64;++delay) {
  now=0; Device d; d.m_tier=1; d.m_frt_input=before; d.stop(2);
  d.advance(now+1000+delay); d.set_frt_input(held); d.initial_state();
  d.stop(0); const auto release=now; d.tier_w(0x81); d.set_frt_input(held);
  CHECK(d.ftcsr_r()==0 && !d.irq_requested);
  d.set_frt_input(1); d.advance(release+16); d.set_frt_input(0);
  CHECK(d.frc_icr_r()==2 && d.ftcsr_r()==0x80 && d.irq_requested); ++captures;
 }
 std::printf("method-level, unvalidated: %u MSTP1 entry/release cases; %u state-copy replays; %u reset cases; %u access-width/other-bit controls; %u input-capture cases\n",entries,replays,resets,controls,captures);
 std::puts("method-level, unvalidated: initial register image, stopped-time exclusion, compare/overflow restart, vector preservation and capture gating exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-frt-stop-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
for field in ('m_sbycr','m_tier','m_ftcsr','m_frc_tcr','m_tocr','m_frc','m_ocra','m_ocrb','m_frc_icr','m_frc_base','m_frt_input'):
    assert f'save_item(NAME({field}));' in source
print('method-level, unvalidated: existing FRT/SBYCR save registrations retained; no new state fields')

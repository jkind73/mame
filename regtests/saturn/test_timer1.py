#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Exercise production SCU timer callbacks against a recording one-shot scheduler.

ST-210 item 31: reload on HBlank only when stopped; zero means 512 counts.
This does not validate the clock divisor, timer-0 phase or full T1MD semantics.
--baseline reproduces the inherited postponement bug.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "868d72fc669765f8a0b9af6503a59642d293cbae"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_scu.cpp"
source = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
          if args.baseline else (ROOT / path).read_text())


def extract(signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


functions = "\n".join(extract(signature) for signature in (
    "void saturn_scu_device::hblank_in_w(",
    "void saturn_scu_device::t1_setdata_w(",
    "void saturn_scu_device::t1_mode_w(",
    "TIMER_CALLBACK_MEMBER(saturn_scu_device::timer1_irq_cb)"))
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
using offs_t = unsigned;
constexpr unsigned DMA_EVENT_HBLANKIN=0, DMA_EVENT_TIMER0=1, DMA_EVENT_TIMER1=2;
constexpr unsigned IST_HBLANK_IN=1, IST_TIMER_0=2, IST_TIMER_1=4;
constexpr bool BIT(unsigned x, unsigned bit) { return (x >> bit) & 1; }
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define TIMER_CALLBACK_MEMBER(name) void name()
struct attotime {
  int64_t ticks;
  static const attotime never;
  bool is_never() const { return ticks == -1; }
  static attotime from_ticks(int count, int rate) { assert(rate == 1); return {count}; }
};
const attotime attotime::never{-1};
struct timer {
  int64_t now = 0;
  attotime deadline = attotime::never;
  bool active = false;
  int arms = 0;
  bool enabled() const { return active; }
  attotime expire() const { return deadline; }
  void adjust(attotime delay) {
    // Mirrors emu_timer::adjust: even adjust(never) sets enabled=true.
    active = true;
    deadline = delay.is_never() ? delay : attotime{now + delay.ticks};
    if (!delay.is_never()) ++arms;
  }
};
struct saturn_scu_device {
  timer tim;
  timer *m_timer1 = &tim;
  bool m_tenb = false, m_t1md = false;
  uint32_t m_t1md_reg = 0, m_t1s = 0, m_t0c = 1023;
  uint32_t m_timer0_counter = 0, m_ist = 0;
  unsigned events[3]{};
  int clock() const { return 8; } // existing divisor gives one test tick per count
  void dma_start_factor_ack(unsigned event) { ++events[event]; }
  void test_pending_irqs() {}
  void hblank_in_w(int);
  void t1_setdata_w(offs_t, uint32_t, uint32_t = ~0u);
  void t1_mode_w(offs_t, uint32_t, uint32_t = ~0u);
  void timer1_irq_cb();
  void advance(int64_t target) {
    assert(target >= tim.now);
    if (tim.active && !tim.deadline.is_never() && tim.deadline.ticks <= target) {
      tim.now = tim.deadline.ticks;
      // Real scheduler disables one-shot before its callback, then retires it.
      tim.active = false;
      timer1_irq_cb();
      tim.deadline = attotime::never;
    }
    tim.now = target;
  }
};
// PRODUCTION_FUNCTIONS
int main() {
  // Specific regression: 512-count timer must expire despite HBlank at 426.
  saturn_scu_device long_timer;
  long_timer.tim.adjust(attotime::never); // device reset representation
  long_timer.t1_mode_w(0, 1);
  long_timer.hblank_in_w(1);
  assert(long_timer.tim.deadline.ticks == 512);
  long_timer.advance(426);
  long_timer.hblank_in_w(1);
  assert(long_timer.tim.deadline.ticks == 512);
  long_timer.advance(512);
  assert(long_timer.events[DMA_EVENT_TIMER1] == 1);

  int cases = 0;
  for (unsigned reload = 0; reload < 512; ++reload)
    for (int line_ticks : {426, 454}) {
      saturn_scu_device s;
      s.tim.adjust(attotime::never);
      s.t1_setdata_w(0, reload);
      s.t1_mode_w(0, 1);
      s.hblank_in_w(0);
      assert(s.tim.arms == 0);
      s.hblank_in_w(1);
      int count = reload ? reload : 512;
      assert(s.tim.deadline.ticks == count);
      // Reload writes affect the next load, not the in-progress countdown.
      unsigned next_reload = 511 - reload;
      s.advance(count / 2);
      s.t1_setdata_w(0, next_reload);
      assert(s.tim.deadline.ticks == count);
      if (count > line_ticks) {
        s.advance(line_ticks);
        s.hblank_in_w(1);
        assert(s.tim.deadline.ticks == count && s.tim.arms == 1);
      }
      s.advance(count);
      assert(s.events[DMA_EVENT_TIMER1] == 1 && (s.m_ist & IST_TIMER_1));
      s.advance(count + line_ticks);
      assert(s.events[DMA_EVENT_TIMER1] == 1); // no automatic periodic reload
      s.hblank_in_w(1);
      int next_count = next_reload ? next_reload : 512;
      assert(s.tim.deadline.ticks == s.tim.now + next_count);
      assert(s.tim.arms == 2);
      // TENB off cancels; HBlank while disabled must not arm.
      s.t1_mode_w(0, 0, 0xff);
      assert(s.tim.enabled() && s.tim.expire().is_never());
      s.hblank_in_w(1);
      s.advance(s.tim.now + 1024);
      assert(s.events[DMA_EVENT_TIMER1] == 1 && s.tim.arms == 2);
      s.t1_mode_w(0, 1, 0xff);
      s.hblank_in_w(1);
      assert(s.tim.arms == 3); // adjust(never) must not block re-enable
      s.advance(s.tim.deadline.ticks);
      assert(s.events[DMA_EVENT_TIMER1] == 2);
      ++cases;
    }
  // Retain existing T1MD load gating; changing mode cannot postpone a count.
  saturn_scu_device gated;
  gated.t1_setdata_w(0, 100);
  gated.t1_mode_w(0, 0x101);
  gated.hblank_in_w(1);
  assert(gated.tim.arms == 0);
  gated.m_t0c = gated.m_timer0_counter;
  gated.hblank_in_w(1);
  assert(gated.tim.deadline.ticks == 100);
  gated.advance(40);
  gated.t1_mode_w(0, 0, 0xff00); // clear T1MD, leave TENB set
  gated.hblank_in_w(1);
  assert(gated.tim.deadline.ticks == 100 && gated.tim.arms == 1);
  gated.advance(100);
  assert(gated.events[DMA_EVENT_TIMER1] == 1);
  // Data register mask/width; high-byte writes cannot alter the 9-bit value.
  gated.t1_setdata_w(0, 0xffffffff);
  assert(gated.m_t1s == 511);
  gated.t1_setdata_w(0, 0, 0xffff0000);
  assert(gated.m_t1s == 511);
  std::cout << cases << " timer-1 reload scenarios passed; gating/masks passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-timer1-") as temp:
    cpp = Path(temp) / "timer1.cpp"
    exe = Path(temp) / "timer1"
    cpp.write_text(harness.replace("// PRODUCTION_FUNCTIONS", functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

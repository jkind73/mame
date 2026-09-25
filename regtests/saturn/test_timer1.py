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
  // ST-210 precaution 31: "Loading the value of Timer 1 set data register to
  // Timer 1 occurs when Timer 1 is stopped and H-Blank occurs." There is no
  // T1MD term in the load condition. ST-097 p.11 (fig. 1.16) makes T1MD select
  // interrupt occurrence only: 0 = every line, 1 = only lines designated by
  // Timer 0. Changing mode must not postpone a running count.
  saturn_scu_device gated;
  gated.t1_setdata_w(0, 100);
  gated.t1_mode_w(0, 0x101); // T1MD=1, TENB=1
  gated.hblank_in_w(1);
  assert(gated.tim.arms == 1 && gated.tim.deadline.ticks == 100);
  gated.advance(40);
  gated.t1_mode_w(0, 0, 0xff00); // clear T1MD, leave TENB set
  gated.hblank_in_w(1);
  assert(gated.tim.deadline.ticks == 100 && gated.tim.arms == 1);
  gated.advance(100);
  assert(gated.events[DMA_EVENT_TIMER1] == 1);

  // ST-097 fig. 2.13 (in sync with Timer 0): the count is still loaded each
  // line, but expiry only raises the interrupt on the designated line.
  saturn_scu_device synced;
  synced.t1_setdata_w(0, 50);
  synced.t1_mode_w(0, 0x101); // T1MD=1, TENB=1
  synced.hblank_in_w(1);      // timer 0 counter becomes 1
  assert(synced.tim.arms == 1);
  synced.advance(50);
  // m_t0c is 1023, so Timer 0 designates no line here: no Timer 1 interrupt.
  assert(synced.events[DMA_EVENT_TIMER1] == 0);

  saturn_scu_device designated;
  designated.t1_setdata_w(0, 50);
  designated.t1_mode_w(0, 0x101);
  designated.m_t0c = 1;      // designate the first counted line
  designated.hblank_in_w(1); // timer 0 counter becomes 1 == m_t0c
  assert(designated.tim.arms == 1);
  designated.advance(50);
  assert(designated.events[DMA_EVENT_TIMER1] == 1 &&
         (designated.m_ist & IST_TIMER_1));
  // Data register mask/width; high-byte writes cannot alter the 9-bit value.
  gated.t1_setdata_w(0, 0xffffffff);
  assert(gated.m_t1s == 511);
  gated.t1_setdata_w(0, 0, 0xffff0000);
  assert(gated.m_t1s == 511);
  std::cout << cases << " timer-1 reload scenarios passed; ST-210 No.31 load and T1MD occurrence gating passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-timer1-") as temp:
    cpp = Path(temp) / "timer1.cpp"
    exe = Path(temp) / "timer1"
    cpp.write_text((ROOT / "regtests/saturn/scu_timer_harness.h").read_text()
                   + functions + "\n" + harness)
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

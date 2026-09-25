#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""SCU timer-0 event-order tests based on ST-097 section 3.4 / ST-210 item 30.

--baseline runs pre-fix callbacks and must fail the compare-zero assertion.
The recording scheduler does not validate physical VDP2 phase or SH-2 delivery.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "c14588532ad776662aad5b05b65113598ea61fcf"
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
    "void saturn_scu_device::vblank_out_w(",
    "void saturn_scu_device::vblank_in_w(",
    "void saturn_scu_device::hblank_in_w(",
    "void saturn_scu_device::t0_compare_w(",
    "void saturn_scu_device::t1_setdata_w(",
    "void saturn_scu_device::t1_mode_w(",
    "TIMER_CALLBACK_MEMBER(saturn_scu_device::timer1_irq_cb)"))
harness = r'''
int main() {
  // The old implementation resets at VBlank-OUT but delays compare zero.
  saturn_scu_device zero;
  zero.t1_mode_w(0, 1);
  zero.t0_compare_w(0, 0);
  zero.m_timer0_counter = 201;
  zero.vblank_out_w(1);
  assert(zero.m_timer0_counter == 0);
  assert(zero.events[DMA_EVENT_TIMER0] == 1);
  assert(zero.irq_snapshot == (IST_VBLANK_OUT | IST_TIMER_0));
  assert(zero.tim.arms == 0); // no timer-1 load at VBlank-OUT
  zero.hblank_in_w(1);
  assert(zero.m_timer0_counter == 1 && zero.events[DMA_EVENT_TIMER0] == 1);

  unsigned cases = 0;
  for (int lines : {263, 313})
    for (unsigned compare = 0; compare < 1024; ++compare)
      for (bool enabled : {false, true})
        for (bool mode : {false, true}) {
          saturn_scu_device s;
          s.t0_compare_w(0, compare);
          s.t1_setdata_w(0, 1);
          s.t1_mode_w(0, (mode ? 0x100 : 0) | enabled);
          unsigned expected_events = 0;
          for (int frame = 0; frame < 2; ++frame) {
            // Unasserted inputs do nothing, even to a nonzero counter.
            auto old_counter = s.m_timer0_counter;
            auto checks = s.irq_checks;
            s.vblank_out_w(0); s.vblank_in_w(0); s.hblank_in_w(0);
            assert(s.m_timer0_counter == old_counter && s.irq_checks == checks);
            s.m_ist = 0;
            int arms = s.tim.arms;
            s.vblank_out_w(1);
            if (enabled && compare == 0) ++expected_events;
            assert(s.m_timer0_counter == 0);
            assert(s.events[DMA_EVENT_TIMER0] == expected_events);
            assert(bool(s.m_ist & IST_TIMER_0) == (enabled && compare == 0));
            assert(s.tim.arms == arms);
            for (int edge = 1; edge <= lines; ++edge) {
              s.m_ist = 0;
              arms = s.tim.arms;
              s.hblank_in_w(1);
              bool hit = enabled && compare == unsigned(edge);
              if (hit) ++expected_events;
              assert(s.m_timer0_counter == unsigned(enabled ? edge : 0));
              assert(s.events[DMA_EVENT_TIMER0] == expected_events);
              assert(bool(s.m_ist & IST_TIMER_0) == hit);
              assert(s.irq_snapshot & IST_HBLANK_IN);
              // ST-210 precaution 31: Timer 1 loads "when Timer 1 is stopped
              // and H-Blank occurs" -- T1MD is not part of that condition,
              // it only selects interrupt occurrence (ST-097 fig. 1.16).
              // The advance below retires the one-shot, so every HBlank
              // finds Timer 1 stopped and must reload it.
              assert(s.tim.arms == arms + int(enabled));
              s.advance(s.tim.now + 2); // allow the one-count timer to finish
              // VBlank-IN must not reset timer 0: counting continues in blanking.
              if (edge == 225) {
                auto before = s.m_timer0_counter;
                s.vblank_in_w(1);
                assert(s.m_timer0_counter == before);
                assert(s.events[DMA_EVENT_TIMER0] == expected_events);
              }
            }
          }
          assert(s.events[DMA_EVENT_HBLANKIN] == unsigned(2 * lines));
          assert(s.events[DMA_EVENT_VBLANKOUT] == 2);
          assert(s.events[DMA_EVENT_TIMER0] == unsigned(enabled && compare <= unsigned(lines) ? 2 : 0));
          ++cases;
        }
  // TENB-off HBlanks must neither advance nor generate a timer event; unrelated
  // HBlank interrupt/DMA events continue. Existing disable resets to zero.
  saturn_scu_device gate;
  gate.t0_compare_w(0, 1);
  gate.t1_mode_w(0, 1);
  gate.hblank_in_w(1);
  assert(gate.events[DMA_EVENT_TIMER0] == 1);
  gate.t1_mode_w(0, 0, 0xff);
  for (int i = 0; i < 7; ++i) gate.hblank_in_w(1);
  assert(gate.m_timer0_counter == 0 && gate.events[DMA_EVENT_TIMER0] == 1);
  gate.t1_mode_w(0, 1, 0xff);
  gate.hblank_in_w(1);
  assert(gate.events[DMA_EVENT_TIMER0] == 2);
  // Preserve ten-bit register storage versus nine-bit counter width.
  gate.t0_compare_w(0, ~0u);
  assert(gate.m_t0c == 1023);
  gate.t0_compare_w(0, 0, 0xffff0000);
  assert(gate.m_t0c == 1023);
  gate.t0_compare_w(0, 0, 0xff);
  assert(gate.m_t0c == 768);
  gate.t0_compare_w(0, 512);
  gate.m_timer0_counter = 511;
  gate.hblank_in_w(1);
  assert(gate.m_timer0_counter == 0 && gate.events[DMA_EVENT_TIMER0] == 2);
  std::cout << cases << " timer-0 two-frame scenarios passed; gating/masks passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-timer0-") as temp:
    cpp = Path(temp) / "timer0.cpp"
    exe = Path(temp) / "timer0"
    cpp.write_text((ROOT / "regtests/saturn/scu_timer_harness.h").read_text()
                   + functions + "\n" + harness)
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

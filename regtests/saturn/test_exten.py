#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Test production EXTEN reset, write/read handlers and external latch callback.

ST-058 section 2.5: reset clears EXTEN, selecting register-read counter latching.
Recording stand-ins do not validate the physical beam or complete device reset.
--baseline uses the pre-fix reset callback and must fail.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "167c45469b379251c68cef6ff81d6b57ceed58c4"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_vdp2.cpp"
source = (ROOT / path).read_text()
old = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
       if args.baseline else source)


def body(text, marker):
    start = text.index("{", text.index(marker))
    end, depth = start + 1, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


exten_map = source[source.index("  map(0x0002, 0x0003)"):source.index("  // $5f80004")]
functions = "void saturn_vdp2_device::device_reset() " + body(old, "void saturn_vdp2_device::device_reset()")
functions += "\nvoid saturn_vdp2_device::external_latch() " + body(source, "void saturn_vdp2_device::external_latch()")
functions += "\nu16 saturn_vdp2_device::read_exten(offs_t offset) " + body(exten_map, "[this](offs_t offset)")
functions += "\nvoid saturn_vdp2_device::write_exten(offs_t offset, u16 data, u16 mem_mask) " + body(exten_map, "[this](offs_t offset, u16 data, u16 mem_mask)")
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
using u16 = uint16_t;
using offs_t = unsigned;
constexpr bool BIT(unsigned data, unsigned bit) { return (data >> bit) & 1; }
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define LOG(...) do {} while (0)
struct screen {
  int time_until_pos(int y) { assert(y == 0); return 17; }
};
struct timer {
  int arms = 0;
  void adjust(int delay, int param) { assert(delay == 17 && param == 0); ++arms; }
};
struct machine_stub {
  bool peek = false;
  bool side_effects_disabled() const { return peek; }
};
struct saturn_vdp2_device {
  screen scr;
  timer tim;
  screen *m_screen = &scr;
  timer *m_video_sync_timer = &tim;
  machine_stub mach;
  machine_stub &machine() { return mach; }
  bool m_odd_bit = false, m_vramsz = true;
  u16 m_old_tvmd = 0, m_tvmd = 0;
  uint8_t m_disp = 0, m_bdclmd = 0, m_lsmd = 0, m_vreso = 0, m_hreso = 0;
  u16 m_exten = 0;
  bool m_exlten = false, m_exsyen = false, m_dasel = false, m_exbgen = false;
  u16 m_hcounter_latch = 0, m_vcounter_latch = 0;
  unsigned m_exltfg = 0;
  int reconfigurations = 0;
  int get_hcounter() const { return 0x2ab; }
  int get_vcounter() const { return 0x355; }
  void reconfigure_crtc() { ++reconfigurations; }
  void device_reset();
  void external_latch();
  u16 read_exten(offs_t offset = 0);
  void write_exten(offs_t offset, u16 data, u16 mem_mask = 0xffff);
  void clear_latches() { m_hcounter_latch = 0x111; m_vcounter_latch = 0x222; m_exltfg = 0; }
  void assert_controls() {
    assert(m_exlten == BIT(m_exten, 9));
    assert(m_exsyen == BIT(m_exten, 8));
    assert(m_dasel == BIT(m_exten, 1));
    assert(m_exbgen == BIT(m_exten, 0));
  }
  void assert_latched(bool yes) {
    assert(m_hcounter_latch == (yes ? 0x2ab : 0x111));
    assert(m_vcounter_latch == (yes ? 0x355 : 0x222));
    assert(m_exltfg == unsigned(yes));
  }
};
// PRODUCTION_FUNCTIONS
int main() {
  unsigned cases = 0;
  for (unsigned bits = 0; bits < 16; ++bits)
    for (bool split : {false, true})
      for (bool high_first : {false, true}) {
        saturn_vdp2_device d;
        u16 value = ((bits & 12) << 6) | (bits & 3);
        // Exercise all combinations and both byte write orders. This preserves
        // existing handler mask behavior; it doesn't endorse hardware byte writes.
        if (split) {
          d.write_exten(0, value, high_first ? 0xff00 : 0x00ff);
          d.assert_controls();
          d.write_exten(0, value, high_first ? 0x00ff : 0xff00);
        } else d.write_exten(0, value);
        d.assert_controls();
        assert(d.m_exten == value);
        d.clear_latches();
        d.external_latch();
        d.assert_latched(BIT(value, 9));
        d.clear_latches();
        assert(d.read_exten() == value);
        d.assert_latched(!BIT(value, 9));
        for (int reset = 0; reset < 2; ++reset) {
          d.device_reset();
          assert(d.m_exten == 0);
          d.assert_controls();
          assert(d.m_odd_bit && !d.m_vramsz && d.m_old_tvmd == 0xffff);
          assert(d.reconfigurations == reset + 1 && d.tim.arms == reset + 1);
          d.clear_latches();
          d.external_latch();
          d.assert_latched(false);
          d.mach.peek = true;
          assert(d.read_exten() == 0);
          d.assert_latched(false);
          d.mach.peek = false;
          assert(d.read_exten() == 0);
          d.assert_latched(true);
        }
        // Guest can re-enable external latching after reset without stale state.
        d.write_exten(0, 0x0200, 0xff00);
        d.assert_controls();
        d.clear_latches();
        assert(d.read_exten() == 0x0200);
        d.assert_latched(false);
        d.external_latch();
        d.assert_latched(true);
        ++cases;
      }
  std::cout << cases << " EXTEN write/reset/latch scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-exten-") as temp:
    cpp = Path(temp) / "exten.cpp"
    exe = Path(temp) / "exten"
    cpp.write_text(harness.replace("// PRODUCTION_FUNCTIONS", functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

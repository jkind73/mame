#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Check production V-counter table equivalence and field-line addressing.

--baseline runs the inherited getter instead (expected sanitizer failure).
--encoding-baseline runs the bounds-fixed, pre-encoding getter (assertion failure).
Requires the inherited base commit to be available in local Git history.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "868d72fc669765f8a0b9af6503a59642d293cbae"
PATH = "src/mame/sega/saturn_vdp2.cpp"
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--baseline", action="store_true")
mode.add_argument("--encoding-baseline", action="store_true")
args = parser.parse_args()
old = subprocess.check_output(["git", "show", BASE + ":" + PATH], cwd=ROOT, text=True)
new = (ROOT / PATH).read_text()
encoding_base = (subprocess.check_output(
    ["git", "show", "fa629f552c338136e9945eb409e7db10bedff491:" + PATH], cwd=ROOT, text=True)
    if args.encoding_baseline else new)


def extract(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


init = "void saturn_vdp2_device::init_vcounter_table()"
getter = "int saturn_vdp2_device::get_vcounter()"
functions = extract(old, init).replace("::init_vcounter_table()", "::baseline_table()")
functions += "\n" + extract(new, init)
functions += "\n" + extract(old if args.baseline else encoding_base, getter)
functions += "\n" + extract(new, "void saturn_vdp2_device::external_latch()")
harness = r'''
#include <cassert>
#include <cstdint>
#include <iterator>
#include <iostream>
using u16 = uint16_t;
using u8 = uint8_t;
constexpr bool BIT(unsigned value, unsigned bit) { return (value >> bit) & 1; }
struct screen {
  int line;
  int vpos() const { return line; }
};
struct saturn_vdp2_device {
  screen scr;
  screen *m_screen = &scr;
  bool m_is_pal = false, m_odd_bit = false;
  int m_hreso = 0, m_lsmd = 0, m_vreso = 0;
  u16 true_vcount[313][4]{};
  void init_vcounter_table();
  void baseline_table();
  int get_vcounter();
  bool m_exlten = true;
  unsigned m_exltfg = 0;
  u16 m_hcounter_latch = 0, m_vcounter_latch = 0;
  int get_hcounter() const { return 0x2aa; }
  void external_latch();
};
// PRODUCTION_FUNCTIONS
int main() {
  unsigned checks = 0;
  // Test the documented encoding independently of the inherited timing table.
  // Synthetic field counts cover every bit and both field polarities, including
  // counts above 255 where a nine-bit result would lose information.
  if (!baseline) {
    saturn_vdp2_device encoded;
    encoded.m_lsmd = 3; encoded.scr.line = 0;
    for (int hreso = 0; hreso < 4; ++hreso)
      for (bool odd : {false, true})
        for (unsigned count = 0; count < 512; ++count) {
          encoded.m_hreso = hreso; encoded.m_odd_bit = odd;
          encoded.true_vcount[0][0] = count;
          unsigned result = encoded.get_vcounter();
          assert(result / 2 == count);
          assert(result % 2 == unsigned(!odd));
          assert(result <= 1023);
          encoded.m_exltfg = 0;
          encoded.external_latch();
          assert(encoded.m_vcounter_latch == result);
          assert(encoded.m_hcounter_latch == 0x2aa && encoded.m_exltfg == 1);
          ++checks;
        }
    encoded.m_exlten = false;
    encoded.m_vcounter_latch = 0x355;
    encoded.m_hcounter_latch = 0x155;
    encoded.m_exltfg = 0;
    encoded.external_latch();
    assert(encoded.m_vcounter_latch == 0x355 && encoded.m_hcounter_latch == 0x155);
    assert(encoded.m_exltfg == 0);
  }
  for (bool pal : {false, true}) {
    saturn_vdp2_device reference, d;
    reference.m_is_pal = d.m_is_pal = pal;
    reference.baseline_table();
    // Fill with poison first to detect any uninitialized table entries.
    for (auto &row : d.true_vcount) for (auto &cell : row) cell = 0xdead;
    d.init_vcounter_table();
    for (int y = 0; y < 313; ++y)
      for (int mode = 0; mode < 4; ++mode) {
        assert(reference.true_vcount[y][mode] == d.true_vcount[y][mode]);
        ++checks;
      }
    int lines = pal ? 313 : 263;
    for (int mode = 0; mode < 4; ++mode)
      for (int lsmd = 0; lsmd < 4; ++lsmd)
        for (bool odd : {false, true}) {
          d.m_vreso = mode; d.m_lsmd = lsmd; d.m_odd_bit = odd;
          int scale = lsmd == 3 ? 2 : 1;
          // Every row including odd rendered rows, rollback and final row.
          for (int y = 0; y < lines * scale; ++y) {
            d.scr.line = y;
            int expected = reference.true_vcount[y / scale][mode & (pal ? 3 : 1)];
            if (lsmd == 3) expected = expected * 2 + int(!odd);
            int actual = d.get_vcounter();
            if (!baseline || lsmd != 3) assert(actual == expected);
            ++checks;
          }
        }
    // Exclusive mode bypasses the field table, even with LSMD=3.
    for (int hreso : {4, 5, 6, 7})
      for (int lsmd = 0; lsmd < 4; ++lsmd) {
        d.m_hreso = hreso; d.m_lsmd = lsmd;
        for (int y = 0; y < ((hreso & 1) ? 561 : 525); ++y) {
          d.scr.line = y;
          assert(d.get_vcounter() == y);
          ++checks;
        }
      }
  }
  std::cout << checks << " V-counter checks passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-vcounter-") as temp:
    cpp = Path(temp) / "vcounter.cpp"
    exe = Path(temp) / "vcounter"
    cpp.write_text(harness.replace("// PRODUCTION_FUNCTIONS",
                                   "constexpr bool baseline = " + str(args.baseline).lower() + ";\n" + functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

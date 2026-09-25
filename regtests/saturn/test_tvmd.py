#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Check TVMD initialization/reset against ST-058 section 2.4.

Compiles actual member initializers, register handlers, reset and CRTC helpers.
The screen/timer are recording stand-ins, not full MAME devices.
--baseline uses the pre-fix reset callback and must fail.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "f8b5cff9036f93c438a85083429277e73c9e6c92"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_vdp2.cpp"
source = (ROOT / path).read_text()
old = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
       if args.baseline else source)
header = (ROOT / "src/mame/sega/saturn_vdp2.h").read_text()
start = header.index("  u16 m_tvmd")
initializers = header[start:header.index("  bool m_odd_bit", start)]


def body(text, marker):
    start = text.index("{", text.index(marker))
    end, depth = start + 1, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


functions = "void saturn_vdp2_device::device_reset() " + body(old, "void saturn_vdp2_device::device_reset()")
for signature in ("void saturn_vdp2_device::reconfigure_crtc()",
                  "int saturn_vdp2_device::get_pixel_clock()",
                  "int saturn_vdp2_device::get_hblank_duration()",
                  "int saturn_vdp2_device::get_vblank_duration()"):
    functions += "\n" + signature + " " + body(source, signature)
regmap = source[source.index("  map(0x0000, 0x0001)"):source.index("  // $5f80002")]
functions += "\nu16 saturn_vdp2_device::read_tvmd() " + body(regmap, "[this]()")
functions += "\nvoid saturn_vdp2_device::write_tvmd(offs_t offset, u16 data, u16 mem_mask) " + body(regmap, "[this](offs_t offset, u16 data, u16 mem_mask)")
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
using u8 = uint8_t;
using u16 = uint16_t;
using offs_t = unsigned;
constexpr bool BIT(unsigned data, unsigned bit) { return (data >> bit) & 1; }
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define ACCESSING_BITS_0_7 (mem_mask & 0xff)
struct attotime {
  int ticks = 0, rate = 0;
  static attotime from_ticks(int ticks, int rate) { assert(rate > 0); return {ticks, rate}; }
};
struct rectangle {
  int l, r, t, b;
  rectangle(int l, int r, int t, int b) : l(l), r(r), t(t), b(b) {}
};
struct screen {
  int updates = 0, ht = 0, vt = 0;
  rectangle visible{0, 0, 0, 0};
  attotime refresh;
  int time_until_pos(int y) { assert(y == 0); return 17; }
  void configure(int h, int v, rectangle area, attotime time) {
    ++updates; ht = h; vt = v; visible = area; refresh = time;
  }
};
struct timer {
  int arms = 0;
  void adjust(int delay, int param) { assert(delay == 17 && param == 0); ++arms; }
};
struct saturn_vdp2_device {
 // saturn_vdp2.h:57 -- device_reset() now notifies the owner so the
 // legacy rendering half is reset too (saturn_vdp2.cpp:108-109).
 struct line_cb{unsigned calls=0;int last=-1;
                void operator()(int s){++calls;last=s;}}m_register_reset_cb;
 bool m_exltfg=false,m_exsyfg=false;
 u16 preserved_tvmd=0xffff;
 void preserve_scanned_output(){preserved_tvmd=m_tvmd;}
  screen scr;
  timer tim;
  screen *m_screen = &scr;
  timer *m_video_sync_timer = &tim;
  bool m_is_pal = false, m_dotsel_352 = false;
// PRODUCTION_INITIALIZERS
  bool m_odd_bit = false, m_vramsz = true;
  u16 m_exten = 0xffff;
  bool m_exlten = true, m_exsyen = true, m_dasel = true, m_exbgen = true;
  u16 m_hdisplay = 0, m_vdisplay = 0;
  int clock() const { return 57272727; } // recorded input, not a clock-accuracy oracle
  void device_reset();
  void reconfigure_crtc();
  int get_pixel_clock();
  int get_hblank_duration();
  int get_vblank_duration();
  u16 read_tvmd();
  void write_tvmd(offs_t, u16, u16 = 0xffff);
  void coherent() {
    assert(m_disp == BIT(m_tvmd, 15) && m_bdclmd == BIT(m_tvmd, 8));
    assert(m_lsmd == ((m_tvmd >> 6) & 3));
    assert(m_vreso == ((m_tvmd >> 4) & 3) && m_hreso == (m_tvmd & 7));
  }
  void reset_geometry() {
    assert(scr.ht == 427 && scr.vt == (m_is_pal ? 313 : 263));
    assert(scr.visible.l == 0 && scr.visible.r == 319);
    assert(scr.visible.t == 0 && scr.visible.b == 223);
    assert(m_hdisplay == 320 && m_vdisplay == 224);
    assert(scr.refresh.ticks == scr.ht * scr.vt && scr.refresh.rate == clock() / 8);
  }
};
// PRODUCTION_FUNCTIONS
int main() {
  unsigned cases = 0;
  for (bool pal : {false, true})
    for (int lsmd = 0; lsmd < 4; ++lsmd)
      for (int vres = 0; vres < 4; ++vres)
        for (int hres = 0; hres < 8; ++hres)
          for (int display = 0; display < 4; ++display)
            for (int writes = 0; writes < 3; ++writes) {
              saturn_vdp2_device d;
              d.m_is_pal = pal;
              // Exercise the initializers taken from the production header,
              // before device_reset, as the startup clock notification does.
              assert(d.read_tvmd() == 0);
              d.coherent();
              d.reconfigure_crtc();
              d.reset_geometry();
              u16 value = ((display & 2) << 14) | ((display & 1) << 8)
                        | (lsmd << 6) | (vres << 4) | hres;
              if (writes == 0) d.write_tvmd(0, value);
              else {
                d.write_tvmd(0, value, writes == 1 ? 0xff00 : 0x00ff);
                d.coherent();
                d.write_tvmd(0, value, writes == 1 ? 0x00ff : 0xff00);
              }
              assert(d.read_tvmd() == value);
              d.coherent();
              for (int reset = 0; reset < 2; ++reset) {
                int updates = d.scr.updates;
                d.device_reset();
                assert(d.read_tvmd() == 0);
                d.coherent();
                assert(d.m_disp == 0 && d.m_bdclmd == 0 && d.m_lsmd == 0);
                assert(d.m_hreso == 0 && d.m_vreso == 0);
                d.reset_geometry();
                assert(d.scr.updates == updates + 1 && d.tim.arms == reset + 1);
                assert(d.m_old_tvmd == 0xffff && d.m_odd_bit);
                assert(d.m_is_pal == pal);
              }
              // Preserve the first low-byte write's forced reconfiguration and
              // high-byte DISP/BDCLMD writes without a geometry change.
              int updates = d.scr.updates;
              d.write_tvmd(0, 0, 0x00ff);
              assert(d.scr.updates == updates + 1 && d.m_old_tvmd == 0);
              d.write_tvmd(0, 0x8100, 0xff00);
              assert(d.scr.updates == updates + 1);
              d.coherent();
              assert(d.read_tvmd() == 0x8100 && d.preserved_tvmd == 0);
              d.write_tvmd(0, 0, 0xff00);
              assert(d.read_tvmd() == 0 && d.preserved_tvmd == 0x8100);
              d.write_tvmd(0, 0xffff, 0);
              assert(d.preserved_tvmd == 0x8100);
              ++cases;
            }
  std::cout << cases << " TVMD startup/write/reset scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-tvmd-") as temp:
    cpp = Path(temp) / "tvmd.cpp"
    exe = Path(temp) / "tvmd"
    cpp.write_text(harness.replace("// PRODUCTION_INITIALIZERS", initializers)
                   .replace("// PRODUCTION_FUNCTIONS", functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

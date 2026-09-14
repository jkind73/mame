#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Compile the production sync callbacks against a small recording scheduler.

No ROMs or MAME build required. This tests callback control flow, not emu_timer
implementation, CPU interrupt delivery, or hardware cycle accuracy.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(path, signature):
    source = (ROOT / path).read_text()
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


callbacks = function("src/mame/sega/saturn_vdp2.cpp",
                     "TIMER_CALLBACK_MEMBER(saturn_vdp2_device::sync_timer_cb)")
callbacks += "\n" + function("src/mame/sega/saturn.cpp",
                            "void saturn_state::hint_callback(int state)")
harness = r'''
#include <cassert>
#include <iostream>
#include <utility>
#include <vector>
#define TIMER_CALLBACK_MEMBER(name) void name()
constexpr int ASSERT_LINE = 1;
struct screen {
  int y = 0, x = 0;
  int vpos() const { return y; }
  std::pair<int, int> time_until_pos(int v, int h) { return {v, h}; }
};
struct timer {
  std::pair<int, int> next;
  void adjust(std::pair<int, int> p) { next = p; }
};
struct scu {
  int edges = 0;
  void hblank_in_w(int state) { edges += state; }
};
struct cpu {
  std::vector<int> lines;
  void set_input_line(int line, int) { lines.push_back(line); }
};
struct saturn_state {
  bool m_prev_hint = false, m_prev_vint = false;
  scu sc;
  cpu slave;
  scu *m_scu = &sc;
  cpu *m_slave = &slave;
  void hint_callback(int state);
};
struct saturn_vdp2_device {
  screen scr;
  timer tim;
  screen *m_screen = &scr;
  timer *m_video_sync_timer = &tim;
  saturn_state host;
  int m_hdisplay = 320, total, step, blank;
  bool m_odd_bit = true;
  int v_in = 0, v_out = 0;
  int get_hblank() { return scr.x >= m_hdisplay; }
  int get_vblank() { return scr.y >= blank; }
  int get_ystep_count() { return step; }
  int get_vblank_duration() { return total; }
  void m_vint_cb(int state) {
    if (state != host.m_prev_vint) {
      if (state) ++v_in; else ++v_out;
    }
    host.m_prev_vint = state;
  }
  void m_hint_cb(int state) { host.hint_callback(state); }
  void sync_timer_cb();
};
// PRODUCTION_CALLBACKS
int main() {
  int cases = 0;
  for (int total : {263, 313, 526, 626, 525, 561}) {
    int step = (total == 263 || total == 313) ? 1 : 2;
    for (int active : {224, 240, 256}) {
      for (int width : {320, 352, 640, 704}) {
        saturn_vdp2_device d;
        d.total = total; d.step = step;
        d.blank = (active + 1) * step; d.m_hdisplay = width;
        const int lines = (total + step - 1) / step;
        const int active_lines = std::min(lines, active + 1);
        // Two fields: every logical line must have exactly one rising edge,
        // including VBlank and the final line, even with an odd line total.
        for (int frame = 0; frame < 2; ++frame) {
          for (int line = 0; line < lines; ++line) {
            assert(d.scr.y == line * step && d.scr.x == 0);
            d.sync_timer_cb();
            assert(d.tim.next == std::make_pair(line * step, width));
            assert(d.m_odd_bit == (frame == 0));
            d.scr.y = d.tim.next.first; d.scr.x = d.tim.next.second;
            d.sync_timer_cb();
            assert(d.tim.next == std::make_pair(line + 1 == lines ? 0 : (line + 1) * step, 0));
            assert(d.m_odd_bit == ((frame == 0) != (line + 1 == lines)));
            d.scr.y = d.tim.next.first; d.scr.x = d.tim.next.second;
          }
          assert(d.host.sc.edges == (frame + 1) * lines);
          int slave_edges = 0;
          for (int line : d.host.slave.lines) if (line == 2) ++slave_edges;
          assert(slave_edges == (frame + 1) * active_lines);
        }
        // Complete the final VBlank-out edge without introducing HBlank-in.
        d.sync_timer_cb();
        assert(d.v_in == (d.blank < total ? 2 : 0));
        assert(d.v_out == d.v_in);
        assert(d.host.sc.edges == 2 * lines);
        ++cases;
      }
    }
  }
  // Repeated levels must not retrigger; neither slave transition is sent in VBlank.
  saturn_state s;
  s.hint_callback(1); s.hint_callback(1); s.hint_callback(0);
  assert(s.sc.edges == 1 && s.slave.lines == std::vector<int>({2, 0}));
  s.m_prev_vint = true;
  s.hint_callback(1); s.hint_callback(1); s.hint_callback(0);
  assert(s.sc.edges == 2 && s.slave.lines == std::vector<int>({2, 0}));
  std::cout << cases << " sync configurations passed; edge gating passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-sync-") as temp:
    cpp = Path(temp) / "sync.cpp"
    exe = Path(temp) / "sync"
    cpp.write_text(harness.replace("// PRODUCTION_CALLBACKS", callbacks))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra",
                    "-Werror", "-fsanitize=undefined", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

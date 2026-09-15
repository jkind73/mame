#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Compile the production vertical cell-scroll branch with recording stand-ins.

Tests clip containment, scroll-table addressing and column-call counts, not the
nested line-scroll renderer or hardware column width. --baseline must fail.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "a562a96f"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
parser.add_argument("--mutation", choices=("gate", "restore"))
args = parser.parse_args()
path = "src/mame/sega/saturn.cpp"
source = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
          if args.baseline else (ROOT / path).read_text())
start = source.index("void saturn_state::vdp2_check_tilemap(")
start = source.index("  if (current_tilemap.", start)
end = source.index("  } else if", start)
branch = source[start:end] + "  }\n"
if args.mutation == "gate":
    branch = branch.replace("if (current_tilemap.vertical_cell_scroll_enable &&", "if (current_tilemap.linescroll_enable && current_tilemap.vertical_cell_scroll_enable &&")
if args.mutation == "restore":
    branch = branch.replace("    current_tilemap.scrollx = base_scrollx;\n    current_tilemap.scrolly = base_scrolly;", "")

harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
struct rectangle {
  int l, r, t, b;
  int left() const { return l; }
  int right() const { return r; }
  bool empty() const { return l > r || t > b; }
  void setx(int left, int right) { l = left; r = right; }
};
struct bitmap_rgb32 {
  std::vector<int> data = std::vector<int>(37 * 5, -9999);
};
struct vdp2 {
  bool size = false;
  bool get_vramsz() const { return size; }
};
struct table {
  std::vector<unsigned> reads;
  uint32_t operator[](unsigned index) {
    assert(index < 0x40000);
    reads.push_back(index);
    // Exercise positive and negative 11-bit scrolls without allocating VRAM.
    return ((index * 617u + 1031u) & 0x7ff) << 16;
  }
};
struct saturn_state {
  struct tilemap {
    bool linescroll_enable = true, vertical_cell_scroll_enable = true;
    bool vertical_linescroll_enable = false, linezoom_enable = false, bitmap_enable = false;
    int layer_name = 0, scrollx = 17, scrolly = 23;
  } current_tilemap;
  vdp2 video;
  vdp2 *m_vdp2 = &video;
  table m_vdp2_vram;
  unsigned high = 0, low = 0;
  bool n0 = true, n1 = false;
  rectangle requested;
  int calls = 0;
  void vdp2_check_tilemap_with_linescroll(bitmap_rgb32 &bitmap, const rectangle &clip) {
    assert(current_tilemap.linescroll_enable);
    draw(bitmap, clip);
  }
  void vdp2_draw_basic_bitmap(bitmap_rgb32 &bitmap, const rectangle &clip) {
    assert(!current_tilemap.linescroll_enable && current_tilemap.bitmap_enable);
    draw(bitmap, clip);
  }
  void vdp2_draw_basic_tilemap(bitmap_rgb32 &bitmap, const rectangle &clip) {
    assert(!current_tilemap.linescroll_enable && !current_tilemap.bitmap_enable);
    draw(bitmap, clip);
  }
  void draw(bitmap_rgb32 &bitmap, const rectangle &clip) {
    assert(!clip.empty());
    assert(clip.l >= requested.l && clip.r <= requested.r);
    assert(clip.t == requested.t && clip.b == requested.b);
    assert(current_tilemap.scrollx == 17);
    ++calls;
    for (int y = clip.t; y <= clip.b; ++y)
      for (int x = clip.l; x <= clip.r; ++x) {
        assert(x >= 0 && x < 37 && y >= 0 && y < 5);
        auto &pixel = bitmap.data[y*37+x];
        assert(pixel == -9999); // no duplicate column coverage
        pixel = current_tilemap.scrolly;
      }
    current_tilemap.scrollx = 1;
    current_tilemap.scrolly = 2;
  }
  void run(bitmap_rgb32 &bitmap, const rectangle &cliprect);
};
#define VDP2_VCSTAU high
#define VDP2_VCSTAL low
#define VDP2_N0VCSC n0
#define VDP2_N1VCSC n1
void saturn_state::run(bitmap_rgb32 &bitmap, const rectangle &cliprect) {
  rectangle mycliprect = cliprect;
// PRODUCTION_BRANCH
}
int main() {
  unsigned checks = 0;
  for (bool size : {false, true})
    for (unsigned address : {0u, 2u, 0x3fffeu, 0x3ffffu, 0x7fffeu, 0x7ffffu})
      for (int ports : {1, 2, 3})
        for (int layer : {0, 1})
          for (int left = 0; left < 37; ++left)
            for (int right : {left - 1, left, std::min(left + 9, 36), 36})
              for (bool empty_y : {false, true})
              for (bool horizontal : {false, true})
              for (bool bitmap_mode : {false, true}) {
                saturn_state s;
                s.video.size = size;
                s.high = address >> 16; s.low = address & 0xffff;
                s.n0 = ports & 1; s.n1 = ports & 2;
                s.current_tilemap.layer_name = layer;
                s.current_tilemap.linescroll_enable = horizontal;
                s.current_tilemap.bitmap_enable = bitmap_mode;
                rectangle clip{left, right, 1, empty_y ? 0 : 3};
                s.requested = clip;
                bitmap_rgb32 bitmap;
                s.run(bitmap, clip);
                assert(s.current_tilemap.scrollx == 17 && s.current_tilemap.scrolly == 23);
                unsigned base = (address & (size ? 0x7ffff : 0x3ffff)) / 2;
                int stride = ports == 3 ? 2 : 1;
                int offset = ports == 3 ? layer : 0;
                int expected_calls = clip.empty() ? 0 : right/8 - left/8 + 1;
                assert(s.calls == expected_calls);
                assert(s.m_vdp2_vram.reads.size() == unsigned(expected_calls));
                for (int i = 0; i < expected_calls; ++i)
                  assert(s.m_vdp2_vram.reads[i] == ((base + (left/8+i)*stride + offset) & 0x3ffff));
                for (int y = 0; y < 5; ++y)
                  for (int x = 0; x < 37; ++x) {
                    int expected = -9999;
                    if (!clip.empty() && x >= left && x <= right && y >= clip.t && y <= clip.b) {
                      unsigned index = (base + (x/8)*stride + offset) & 0x3ffff;
                      int scroll = (index*617u + 1031u) & 0x7ff;
                      if (scroll >= 1024) scroll -= 2048;
                      expected = 23 + scroll;
                    }
                    assert(bitmap.data[y*37+x] == expected);
                  }
                ++checks;
              }
  std::cout << checks << " vertical cell-scroll configurations passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-cell-scroll-") as temp:
    cpp = Path(temp) / "cell.cpp"
    exe = Path(temp) / "cell"
    cpp.write_text(harness.replace("// PRODUCTION_BRANCH", branch))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=all", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

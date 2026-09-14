#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Test the production mosaic function with a bounds-checked recording bitmap.

Run with --baseline to demonstrate that the inherited base implementation fails.
This verifies clipping, not hardware mosaic alignment or layer compositing.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn.cpp"
if args.baseline:
    source = subprocess.check_output(["git", "show", "868d72fc669765f8a0b9af6503a59642d293cbae:" + path], cwd=ROOT, text=True)
else:
    source = (ROOT / path).read_text()
start = source.index("void saturn_state::vdp2_draw_mosaic(")
end = source.index("\nvoid saturn_state::vdp2_check_tilemap(", start)
function = source[start:end]

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
  int top() const { return t; }
  int bottom() const { return b; }
};
struct bitmap_rgb32 {
  int width, height;
  std::vector<uint32_t> data;
  bitmap_rgb32(int w, int h) : width(w), height(h), data(w*h) {
    for (int i = 0; i < w*h; ++i) data[i] = i + 1;
  }
  uint32_t &pix(int y, int x) {
    // Check each coordinate: a right-edge overrun must not alias the next row.
    assert(x >= 0 && x < width && y >= 0 && y < height);
    return data[y*width+x];
  }
};
struct vdp2 {
  int lsmd;
  int get_lsmd() const { return lsmd; }
};
struct saturn_state {
  int horizontal, vertical;
  vdp2 video;
  vdp2 *m_vdp2 = &video;
  void vdp2_draw_mosaic(bitmap_rgb32 &, const rectangle &, uint8_t);
};
#define VDP2_MZSZH horizontal
#define VDP2_MZSZV vertical
// PRODUCTION_FUNCTION
int main() {
  int cases = 0;
  const rectangle clips[] = {
    {0, 36, 0, 34},  // partial blocks at bitmap edges
    {3, 29, 5, 27},  // offset clip with untouched pixels on all four sides
    {36, 36, 34, 34}, // single bottom-right pixel
    {0, 0, 0, 34},   // one column
    {0, 36, 0, 0},   // one row
    {0, 31, 0, 31},  // aligned and unaligned block sizes
    {5, 4, 3, 9},    // empty horizontal interval
    {3, 9, 5, 4}     // empty vertical interval
  };
  for (int hs = 1; hs <= 16; ++hs)
    for (int vs = 1; vs <= 16; ++vs)
      for (int lsmd : {0, 1, 2, 3})
        for (int roz : {0, 1})
          for (const auto &clip : clips) {
            bitmap_rgb32 bitmap(37, 35);
            const auto original = bitmap.data;
            saturn_state state;
            state.horizontal = hs - 1;
            state.vertical = vs - 1;
            state.video.lsmd = lsmd;
            state.vdp2_draw_mosaic(bitmap, clip, roz);
            // Independent per-pixel oracle: sample the original block anchor.
            // Preserve the existing unit-size early return and interlace order.
            int effective_vs = roz ? 1 : vs;
            bool bypass = hs == 1 && effective_vs == 1;
            if (lsmd == 3) effective_vs *= 2;
            for (int y = 0; y < bitmap.height; ++y)
              for (int x = 0; x < bitmap.width; ++x) {
                int sx = x, sy = y;
                if (!bypass && x >= clip.l && x <= clip.r && y >= clip.t && y <= clip.b) {
                  sx = clip.l + ((x - clip.l) / hs) * hs;
                  sy = clip.t + ((y - clip.t) / effective_vs) * effective_vs;
                }
                assert(bitmap.pix(y, x) == original[sy*bitmap.width+sx]);
              }
            ++cases;
          }
  std::cout << cases << " mosaic configurations passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-mosaic-") as temp:
    cpp = Path(temp) / "mosaic.cpp"
    exe = Path(temp) / "mosaic"
    cpp.write_text(harness.replace("// PRODUCTION_FUNCTION", function))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

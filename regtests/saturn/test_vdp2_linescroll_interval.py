#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""SCRCTL line-scroll table read interval, ST-058 chapter 5's SCRCTL table.

The manual's exact table (from the clean SSDDV25 documentation set,
C:\\Users\\jkind\\cassini - fusion\\docs\\SSDDV25, resolving what the earlier OCR/PDF
extraction had left as "garbled" and unverifiable per V2-P1-26):

  NxLSS1 NxLSS0  non-interlaced  single-density  double-density
    0      0        1 line          2 lines         1 line
    0      1        2 lines         4 lines         2 lines
    1      0        4 lines         8 lines         4 lines
    1      1        8 lines        16 lines         8 lines

Non-interlaced and double-density interlace share the same 1/2/4/8 progression
(matching `1 << LSS`); single-density interlace doubles it (2/4/8/16, i.e.
`2 << LSS`). Table 2.4 (V counter register bit contents) groups single-density
with non-interlace for the V counter's own bit layout (direct passthrough, no
shift or field-parity bit, unlike double-density's shifted+parity encoding),
so the V counter - and this table's "lines" - already count picture rows 1:1
in single-density, the same units the driver's bitmap uses. The doubled
interval is a real, distinct requirement, not a raster-vs-picture unit
mismatch that would cancel it out.

Before this fix, `vdp2_draw_NBG0`/`vdp2_draw_NBG1` used a flat `1 << LSS` for
every interlace mode, with a comment arguing the non-interlace value was
correct here too (via a since-superseded "our bitmap is picture-row-indexed"
argument). Corroborated against upstream MAME's current mainline saturn.cpp,
which already carries this exact `(get_lsmd()==2 ? 2 : 1) << LSS` fix for both
NBG0 and NBG1.

Extracts both assignment expressions verbatim and checks them against the
table for LSMD in {0 (non-interlace), 2 (single-density), 3 (double-density)}
(1 is "setting prohibited" per the TVMD LSMD field and not exercised) and all
four LSS values.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / 'src/mame/sega/saturn.cpp').read_text()


def extract_expr(anchor):
    start = src.index(anchor)
    end = src.index(';', start) + 1
    return src[start:end]


nbg0_expr = extract_expr('current_tilemap.linescroll_interval = (m_vdp2->get_lsmd() == 2 ? 2U : 1U) << VDP2_N0LSS')
nbg1_expr = extract_expr('current_tilemap.linescroll_interval = (m_vdp2->get_lsmd() == 2 ? 2U : 1U) << VDP2_N1LSS')
assert nbg0_expr.count('current_tilemap.linescroll_interval') == 1
assert nbg1_expr.count('current_tilemap.linescroll_interval') == 1

harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
struct vdp2_stub {
 unsigned lsmd = 0;
 unsigned get_lsmd() const { return lsmd; }
};
struct saturn_state {
 vdp2_stub m_vdp2_obj;
 vdp2_stub *m_vdp2 = &m_vdp2_obj;
 struct { unsigned linescroll_interval; } current_tilemap;
 unsigned N0LSS = 0, N1LSS = 0;
#define VDP2_N0LSS N0LSS
#define VDP2_N1LSS N1LSS
 void nbg0() { NBG0_EXPR }
 void nbg1() { NBG1_EXPR }
};
int main() {
 unsigned n = 0;
 static const unsigned expected[3][4] = {
  {1, 2, 4, 8},   // lsmd=0 non-interlace
  {2, 4, 8, 16},  // lsmd=2 single-density
  {1, 2, 4, 8},   // lsmd=3 double-density
 };
 unsigned row = 0;
 for (unsigned lsmd : {0u, 2u, 3u}) {
  for (unsigned lss = 0; lss < 4; ++lss) {
   saturn_state s;
   s.m_vdp2_obj.lsmd = lsmd;
   s.N0LSS = lss; s.nbg0();
   if (s.current_tilemap.linescroll_interval != expected[row][lss]) {
    printf("NBG0 lsmd=%u lss=%u got=%u want=%u\n", lsmd, lss, s.current_tilemap.linescroll_interval, expected[row][lss]);
    return 1;
   }
   s.N1LSS = lss; s.nbg1();
   if (s.current_tilemap.linescroll_interval != expected[row][lss]) {
    printf("NBG1 lsmd=%u lss=%u got=%u want=%u\n", lsmd, lss, s.current_tilemap.linescroll_interval, expected[row][lss]);
    return 1;
   }
   n += 2;
  }
  ++row;
 }
 printf("%u cases passed\n", n);
}
'''
harness = harness.replace('NBG0_EXPR', nbg0_expr).replace('NBG1_EXPR', nbg1_expr)


def main():
    with tempfile.TemporaryDirectory(prefix='linescroll-interval-') as tmp:
        p = Path(tmp)
        (p / 'test.cpp').write_text(harness)
        import os
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++17', '-O1',
                        str(p / 'test.cpp'), '-o', str(p / 'test')], check=True)
        result = subprocess.run([str(p / 'test')], capture_output=True, text=True)
        print(result.stdout, end='')
        if result.returncode != 0:
            raise SystemExit(f'SCRCTL line-scroll interval check failed:\n{result.stdout}')
    print('VDP2-LINESCROLL-INTERVAL PASS')


if __name__ == '__main__':
    main()

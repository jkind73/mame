#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Runtime-logic check for the NBG0-colour-depth-disables-NBG2/NBG3 rule (ST-058 p.61 /
"Table 5.2"), found already implemented in vdp2_draw_NBG2/vdp2_draw_NBG3 (saturn.cpp)
while researching Jo Engine's vdp2.h documentation comments earlier this session, and at
the time verified only by reading the code. This extracts the exact enable/disable
statements verbatim (the same brace-free technique other regtests in this suite use for
whole functions, applied here to a short, self-contained statement run) and evaluates
them in a minimal harness, rather than driving a full VDP2 render - a prior attempt at a
pixel-rendering fixture for this same rule got tangled in unrelated VDP2 tilemap/pattern-
name-format setup mistakes (PNCN2 vs MPABN2) with no bearing on the rule itself; this is
a more direct and far more robust way to guard the same logic.

Rule under test: NBG0 at 2048-color, 32768-color or 16.77M-color (CHCTLA.N0CHCN in
{2,3,4}) excludes NBG2; NBG0 at 16.77M-color, or NBG1 at 2048/32768-color (N0CHCN==4 or
N1CHCN in {2,3}), excludes NBG3. Both apply regardless of the two rotation screens'
combined exclusion (checked immediately above each block in the source) and regardless
of the NBG0/NBG1 reduction-range exclusion checked just below it - this only isolates the
p.61/Table 5.2 colour-depth block itself.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / 'src/mame/sega/saturn.cpp').read_text()


def extract(anchor_start, anchor_end):
    start = src.index(anchor_start)
    end = src.index(anchor_end, start) + len(anchor_end)
    return src[start:end]


nbg2_block = extract(
    '// ST-058 Table 5.2: quarter reduction on NBG0, or half reduction',
    '  if (VDP2_N0CHCN == 0x02 || VDP2_N0CHCN == 0x03 || VDP2_N0CHCN == 0x04)\n'
    '    current_tilemap.enabled = 0;')
assert 'ST-058 p.61: 2048-color and both RGB formats exclude NBG2' in nbg2_block
assert nbg2_block.count('current_tilemap.enabled = 0;') == 2

nbg3_block = extract(
    '// The corresponding NBG1 reduction settings disable NBG3',
    '  if (VDP2_N0CHCN == 0x04 || VDP2_N1CHCN == 0x02 || VDP2_N1CHCN == 0x03)\n'
    '    current_tilemap.enabled = 0;')
assert 'ST-058 p.61: RGB888 NBG0, or 2048-color/RGB555 NBG1, excludes NBG3' in nbg3_block
assert nbg3_block.count('current_tilemap.enabled = 0;') == 2

harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
struct regs {
 int N0CHCN=0, N1CHCN=0, N0ZMQT=0, N0ZMHF=0, N1ZMQT=0, N1ZMHF=0, R0ON=0, R1ON=0;
} r;
#define VDP2_N0CHCN r.N0CHCN
#define VDP2_N1CHCN r.N1CHCN
#define VDP2_N0ZMQT r.N0ZMQT
#define VDP2_N0ZMHF r.N0ZMHF
#define VDP2_N1ZMQT r.N1ZMQT
#define VDP2_N1ZMHF r.N1ZMHF
#define VDP2_R0ON r.R0ON
#define VDP2_R1ON r.R1ON

bool nbg2_enabled() {
 struct { bool enabled; } current_tilemap{true}; // start enabled: N2ON=1
// NBG2_BLOCK
 return current_tilemap.enabled;
}
bool nbg3_enabled() {
 struct { bool enabled; } current_tilemap{true};
// NBG3_BLOCK
 return current_tilemap.enabled;
}

int main() {
 unsigned n = 0;
 // NBG2: colour_depth in {0,1} (16/256-color) with no reduction must stay enabled;
 // {2,3,4} (2048/32768/16.77M) must disable it, independent of NBG1's fields.
 for (int depth = 0; depth <= 4; ++depth) {
  r = regs{}; r.N0CHCN = depth;
  bool enabled = nbg2_enabled();
  bool expect = !(depth == 2 || depth == 3 || depth == 4);
  if (enabled != expect) { printf("NBG2 depth=%d got=%d want=%d\n", depth, enabled, expect); return 1; }
  ++n;
 }
 // NBG3: N0CHCN==4 disables it; N1CHCN in {2,3} disables it; N1CHCN in {0,1} (with
 // N0CHCN!=4) leaves it enabled.
 for (int n0 : {0, 1, 2, 3, 4}) {
  for (int n1 = 0; n1 <= 3; ++n1) {
   r = regs{}; r.N0CHCN = n0; r.N1CHCN = n1;
   bool enabled = nbg3_enabled();
   bool expect = !(n0 == 4 || n1 == 2 || n1 == 3);
   if (enabled != expect) { printf("NBG3 n0=%d n1=%d got=%d want=%d\n", n0, n1, enabled, expect); return 1; }
   ++n;
  }
 }
 printf("%u cases passed\n", n);
}
'''
harness = harness.replace('// NBG2_BLOCK', nbg2_block).replace('// NBG3_BLOCK', nbg3_block)


def main():
    with tempfile.TemporaryDirectory(prefix='nbg-exclusion-') as tmp:
        p = Path(tmp)
        (p / 'test.cpp').write_text(harness)
        import os
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++17', '-O1',
                        str(p / 'test.cpp'), '-o', str(p / 'test')], check=True)
        result = subprocess.run([str(p / 'test')], capture_output=True, text=True)
        print(result.stdout, end='')
        if result.returncode != 0:
            raise SystemExit(f'NBG0-disables-NBG2/NBG3 check failed:\n{result.stdout}')
    print('NBG0-DISABLES-NBG2/NBG3 PASS')


if __name__ == '__main__':
    main()

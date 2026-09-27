#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""VDP2 VRAM cycle pattern access-count requirement (ST-058 pp.33-34, Tables 3.2 and 3.3).

Extracts the production vdp2_required_cycle_pattern_counts() table and
vdp2_check_vram_cycle_pattern_registers() logic unchanged and checks them
against the official manual text: the pattern-name access count required in
one cycle depends only on the reduction range (1/2/4 for 1x/half/quarter);
the character-pattern access count also depends on colour depth (16, 256,
2048, 32768, 16,770,000 colours). Above 256 colours the table gives a single,
reduction-independent count. Quarter reduction with 256 colours has no entry
in Table 3.3 and is not guessed at.

Before this change the driver only checked that each access command was
present *somewhere* in the cycle pattern registers ("a presence gate, not
fetch-address matching or a slot arbiter", per its own prior comment), so a
layer provisioned with only one access of a command needing two or four would
incorrectly stay enabled. This is a pure extraction: no game ROM, no display.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / 'src/mame/sega/saturn.cpp').read_text()


def extract(signature):
    start = src.index(signature)
    end = src.index('{', start) + 1
    depth = 1
    while depth:
        depth += (src[end] == '{') - (src[end] == '}')
        end += 1
    return src[start:end]


counts_fn = extract('static bool vdp2_required_cycle_pattern_counts(')
check_fn = extract('uint8_t saturn_state::vdp2_check_vram_cycle_pattern_registers(')
check_fn = check_fn.replace('uint8_t saturn_state::vdp2_check_vram_cycle_pattern_registers(',
                            'uint8_t saturn_state::check(', 1)

mutant = os.environ.get('VDP2_CYCLE_MUTANT', '')
if mutant == 'old-presence-gate':
    # The pre-fix behaviour: any single occurrence of each command satisfies the gate.
    check_fn = re.sub(
        r'if \(!vdp2_required_cycle_pattern_counts.*?return pnmdr_seen >= required_pnmdr && cpdr_seen >= required_cpdr;',
        'return pnmdr_seen != 0 && cpdr_seen != 0;', check_fn, flags=re.S)
    assert 'return pnmdr_seen != 0 && cpdr_seen != 0;' in check_fn
if mutant == 'wrong-256-half':
    counts_fn = counts_fn.replace('cpdr_count = reduction_half ? 4 : 2;', 'cpdr_count = 2;')
    assert 'cpdr_count = 2;\n    return true;\n  case 2:' in counts_fn

harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
using u8 = uint8_t; using u16 = uint16_t;
struct vdp2_stub {
 u16 hreso = 0;
 unsigned get_hreso() const { return hreso; }
};
struct saturn_state {
 u16 m_vdp2_regs[0x100] = {};
 vdp2_stub m_vdp2_obj;
 vdp2_stub *m_vdp2 = &m_vdp2_obj;
#define VDP2_RAMCTL (m_vdp2_regs[0x00e / 2])
#define VDP2_CYCA0L (m_vdp2_regs[0x010 / 2])
#define VDP2_CYCA0U (m_vdp2_regs[0x012 / 2])
#define VDP2_CYCA1L (m_vdp2_regs[0x014 / 2])
#define VDP2_CYCA1U (m_vdp2_regs[0x016 / 2])
#define VDP2_CYCA2L (m_vdp2_regs[0x018 / 2])
#define VDP2_CYCA2U (m_vdp2_regs[0x01a / 2])
#define VDP2_CYCA3L (m_vdp2_regs[0x01c / 2])
#define VDP2_CYCA3U (m_vdp2_regs[0x01e / 2])
#define VDP2_BGON (m_vdp2_regs[0x020 / 2])
#define VDP2_R0ON ((VDP2_BGON & 0x0010) >> 4)
#define VDP2_R1ON ((VDP2_BGON & 0x0020) >> 5)
 uint8_t check(uint8_t access_command_pnmdr, uint8_t access_command_cpdr,
              uint8_t bitmap_enable, uint8_t colour_depth,
              bool reduction_quarter, bool reduction_half);
};
// COUNTS_FN
// CHECK_FN
int main() {
 // --- Table lookup itself, straight from ST-058 pp.33-34 ---
 unsigned pn, cp;
 struct Case { uint8_t depth; bool q, h; bool ok; unsigned pn, cp; };
 static const Case cases[] = {
  {0,false,false,true,1,1}, {0,false,true,true,2,2}, {0,true,false,true,4,4},
  {1,false,false,true,1,2}, {1,false,true,true,2,4}, {1,true,false,false,0,0},
  {2,false,false,true,1,4}, {2,false,true,true,2,4}, {2,true,false,true,4,4},
  {3,false,false,true,1,4}, {3,true,true,true,4,4},
  {4,false,false,true,1,8}, {4,true,false,true,4,8},
 };
 unsigned n = 0;
 for (auto &c : cases) {
  bool ok = vdp2_required_cycle_pattern_counts(c.depth, c.q, c.h, pn, cp);
  assert(ok == c.ok);
  if (ok) { assert(pn == c.pn); assert(cp == c.cp); }
  ++n;
 }
 printf("%u table lookup cases passed\n", n);

 // --- Integration: a layer with too few provisioned accesses must disable ---
 auto make = [](unsigned pn_count, unsigned cp_count) {
  saturn_state s;
  // Fill every slot with "no access" (1111), then place pn_count copies of the
  // NBG0 pattern-name command (0000) and cp_count copies of its
  // character-pattern command (0100), all in bank A0 (8 slots available).
  auto set_nibble = [&](unsigned slot, unsigned val) {
   unsigned word = slot / 4, nib = slot % 4;
   uint16_t *regs[4] = {&s.m_vdp2_regs[0x010/2], &s.m_vdp2_regs[0x012/2],
                        &s.m_vdp2_regs[0x014/2], &s.m_vdp2_regs[0x016/2]};
   uint16_t &r = *regs[word];
   unsigned shift = 12 - nib * 4;
   r = (r & ~(0xfU << shift)) | (val << shift);
  };
  // Every bank defaults to "no access" (0xf nibbles), including banks 1-3
  // (CYCA1*/CYCA2*/CYCA3*), which the real register layout also leaves at
  // reset; otherwise banks 2/3 (never gated by RAMCTL/R0ON/R1ON when both are
  // zero, as here) would be read as all-zero nibbles, which happens to equal
  // the NBG0 pattern-name command (0x0) and spuriously inflate pnmdr_seen.
  s.m_vdp2_regs[0x014/2] = s.m_vdp2_regs[0x016/2] = 0xffff;
  s.m_vdp2_regs[0x018/2] = s.m_vdp2_regs[0x01a/2] = 0xffff;
  s.m_vdp2_regs[0x01c/2] = s.m_vdp2_regs[0x01e/2] = 0xffff;
  for (unsigned i = 0; i < 8; ++i) set_nibble(i, 0xf);
  unsigned slot = 0;
  for (unsigned i = 0; i < pn_count; ++i) set_nibble(slot++, 0x0);
  for (unsigned i = 0; i < cp_count; ++i) set_nibble(slot++, 0x4);
  return s;
 };
 unsigned int_cases = 0;
 // 256 colours, half reduction needs 2 pattern-name + 4 character-pattern accesses.
 {
  saturn_state under_pn = make(1, 4); // only 1 pattern-name access provisioned (needs 2)
  assert(!under_pn.check(0x0, 0x4, 0, 1, false, true));
  saturn_state under_cp = make(2, 3); // only 3 character-pattern accesses (needs 4)
  assert(!under_cp.check(0x0, 0x4, 0, 1, false, true));
  saturn_state exact = make(2, 4);
  assert(exact.check(0x0, 0x4, 0, 1, false, true));
  int_cases += 3;
 }
 // 16 colours, no reduction: 1 of each is already sufficient (matches the old gate).
 {
  saturn_state ok = make(1, 1);
  assert(ok.check(0x0, 0x4, 0, 0, false, false));
  int_cases += 1;
 }
 // Bitmap layers bypass the requirement entirely.
 {
  saturn_state empty = make(0, 0);
  assert(empty.check(0x0, 0x4, 1, 4, true, true));
  int_cases += 1;
 }
 printf("%u integration cases passed\n", int_cases);
}
'''
harness = harness.replace('// COUNTS_FN', counts_fn).replace('// CHECK_FN', check_fn)

with tempfile.TemporaryDirectory(prefix='vdp2-cycle-') as tmp:
    p = Path(tmp)
    (p / 'test.cpp').write_text(harness)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++17', '-O1', str(p / 'test.cpp'), '-o', str(p / 'test')],
                    check=True)
    subprocess.run([str(p / 'test')], check=True)
print('VDP2-CYCLE-COUNT PASS')

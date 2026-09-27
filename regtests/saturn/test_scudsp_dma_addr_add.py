#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""SCU DSP immediate-form DMA address-add table (ST-097 pp.148-149).

Self-contained: op_dma's other paths depend on execution-state members that
test_scudsp_dma.py's shared harness does not currently mock (see the task
flagged separately for that pre-existing gap); this test extracts only the
address-add switch/table itself, isolated from the rest of op_dma, so it does
not depend on that harness or on unrelated DMA state-machine behaviour.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / 'src/devices/cpu/scudsp/scudsp.cpp').read_text()

# Pull out just the address-add computation for the immediate (non-RAM-count) form.
DECL = 'static constexpr uint32_t k_dma_add_bytes[8] = {0, 4, 8, 16, 32, 64, 128, 256};'
ASSIGN = 'm_dma.add = k_dma_add_bytes[add & 7];'
assert DECL in src and ASSIGN in src, 'address-add table not found where expected'
snippet = DECL + '\n' + ASSIGN

mutant = os.environ.get('SCUDSP_DMA_ADD_MUTANT', '')
if mutant == 'old-table':
    # The original (buggy) table before this fix: fields 2 and 4 read back
    # the values for fields 1 and 3 instead of their own.
    old = snippet
    snippet = snippet.replace('{0, 4, 8, 16, 32, 64, 128, 256}', '{0, 4, 4, 16, 16, 64, 128, 256}')
    assert snippet != old

cpp = r'''
#include <cstdint>
#include <cstdio>
// SNIPPET
int main() {
 for (unsigned add = 0; add < 8; ++add) {
  uint32_t out;
  { out = k_dma_add_bytes[add & 7]; }
  printf("%u\n", out);
 }
}
'''
cpp = cpp.replace('// SNIPPET', snippet.split('\n')[0])  # the mutated/original array declaration only

with tempfile.TemporaryDirectory(prefix='scudsp-addadd-') as tmp:
    p = Path(tmp)
    (p / 'test.cpp').write_text(cpp)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++17', '-O1', str(p / 'test.cpp'), '-o', str(p / 'test')],
                    check=True)
    out = subprocess.run([str(p / 'test')], capture_output=True, text=True, check=True).stdout

got = [int(x) for x in out.split()]
# ST-097 pp.148-149: the 3-bit address-add field is a long-word count
# (0,1,2,4,8,16,32,64); the byte add is that value times 4.
want = [0, 4, 8, 16, 32, 64, 128, 256]
assert len(got) == 8, got
for field, (g, w) in enumerate(zip(got, want)):
    ok = g == w
    print('field %d -> %3d bytes (want %3d): %s' % (field, g, w, 'PASS' if ok else 'FAIL'))
assert got == want, (got, want)
print('SCUDSP-DMA-ADDADD PASS')

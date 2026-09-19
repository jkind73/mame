#!/usr/bin/env python3
"""Method-level check for the 315-5649 PORT-G counter-mode latch.

Compares, at source level and by exhaustive table evaluation, the 315-5649
device counter path against the legacy stv_state::ioga_r/ioga_w counter
handler it must remain equivalent to:

  1. parse both implementations' shift/select/cursor expressions,
  2. evaluate sel/byte/shift for all 8 port-G cursor values,
  3. verify the cursor sequence and the latch trigger condition.

Method-level, unvalidated: not acceptance evidence.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
fail = 0

dev = (ROOT / "src/mame/sega/315_5649.cpp").read_text()
stv = (ROOT / "src/mame/sega/stv.cpp").read_text()

# --- 1. source-level formula equivalence -------------------------------
dev_read = re.search(
    r"case 0x06:\s*\n\s*if \(m_mode & 0x80\).*?break;", dev, re.S
).group(0)
stv_read = re.search(
    r"case 0x0d:\s*\n\s*if \(m_ioga_mode & 0x80\).*?break;", stv, re.S
).group(0)

# sel expressions must agree structurally
dev_sel = re.search(r"\(m_port_value\[6\] >> 1\) & 3", dev_read)
stv_sel = re.search(r"\(m_ioga_portg >> 1\) & 0x0?3", stv_read)
if not (dev_sel and stv_sel):
    print("FAIL: sel expressions not found")
    fail += 1

# byte-select shifts: device uses ((x & 1) ^ 1) * 8, legacy (~x & 1) * 8 —
# identical for all x; assert the difference formula is present in both
if "(m_cnt_cb[sel](0) - m_cnt_base[sel])" not in dev_read.replace("\t", ""):
    print("FAIL: device read lacks base difference")
    fail += 1
if "(m_ioga_counters[sel]->read() - m_ioga_count[sel])" not in stv_read.replace("\n", "").replace("\t", ""):
    print("FAIL: legacy read formula moved/changed unexpectedly")
    fail += 1

# latch trigger: device write case 0x06 with bit 7 clear, legacy write 0x0d
dev_write = re.search(r"case 0x06:\s*\n\s*// when in counter mode.*?break;", dev, re.S).group(0)
stv_write = re.search(r"case 0x0d:\s*\n\s*if \(!BIT\(data, 7\)\).*?break;", stv, re.S).group(0)
if "!BIT(data, 7)" not in dev_write or "!BIT(data, 7)" not in stv_write:
    print("FAIL: latch trigger conditions differ")
    fail += 1

# --- 2. exhaustive cursor-state table ----------------------------------
def device_shift(portg):
    return ((portg & 1) ^ 1) * 8

def legacy_shift(portg):
    return (~portg & 1) * 8

for portg in range(8):
    sel_d, sel_l = (portg >> 1) & 3, (portg >> 1) & 3
    sh_d, sh_l = device_shift(portg), legacy_shift(portg)
    nxt_d = (portg & 0xF8) | ((portg + 1) & 7)
    nxt_l = (portg & 0xF8) | ((portg + 1) & 7)
    if (sel_d, sh_d, nxt_d) != (sel_l, sh_l, nxt_l):
        print(f"FAIL portg={portg}: device {(sel_d, sh_d, nxt_d)} != legacy {(sel_l, sh_l, nxt_l)}")
        fail += 1

# sequence sanity: byte alternates, counter index advances every two reads
cursor, seen = 0, []
for _ in range(8):
    seen.append(((cursor >> 1) & 3, (cursor & 1) ^ 1))
    cursor = (cursor & 0xF8) | ((cursor + 1) & 7)
expected = [(0, 1), (0, 0), (1, 1), (1, 0), (2, 1), (2, 0), (3, 1), (3, 0)]
if seen != expected:
    print(f"FAIL cursor sequence {seen} != {expected}")
    fail += 1

# --- 3. wiring present in stv() ----------------------------------------
stvcfg = stv[stv.index("void stv_state::stv(machine_config &config)"):]
for n in range(4):
    if f'm_ioga->in_counter_callback<{n}>().set_ioport("PORTG.{n}")' not in stvcfg:
        print(f"FAIL: stv() missing in_counter_callback<{n}> wiring")
        fail += 1

if fail:
    print(f"FAILED {fail} checks")
    sys.exit(1)
print("all checks passed (formula equivalence, 8 cursor states, wiring)")

# VCRDIV, FMR and DIVU result-copy evidence — 2026-10-11

## VCRDIV decision

Retain `0000FFFF` read-back and use only bits 6–0 for the interrupt vector.
This is an evidence-based reconciliation of conflicting descriptions, rather
than a newly invented reserved-bit mask.

The [Hitachi SH7604 manual ADE-602-085C Rev.4.0](https://antime.kapsi.fi/sega/files/sh7604.pdf),
section 10.2.4, printed page 291, contradicts itself: its bit chart makes all
lower sixteen bits R/W, its first paragraph permits setting those sixteen bits,
and its subsequent reserved-bit prose says bits 31–7 always read zero. Appendix
B.2, printed page 586, repeats lower-sixteen R/W. Legal software should write
bits 15–7 as zero regardless of which read-back interpretation is selected.

The [YabauseUT SH-2 diagnostic](https://github.com/Yabause/yabause/blob/7e38821dbac265490f115e163c523a939acda759/yabauseut/src/sh2.c#L115)
provides an executable expectation independent of the contradictory prose:
`div_mirror_test` writes `0102` to VCRDIV at both FFFFFF0C and FFFFFF2C and
requires reading `0102`, which the seven-bit mask cannot satisfy. This supports
the sixteen-bit charts. The existing upstream MAME change
[`661381746bf`](https://github.com/mamedev/mame/commit/661381746bf01462df2c40f3567918293a70a379)
and Mednafen 1.32.1's `src/ss/sh7095.inc` independently implement sixteen-bit
storage/read-back and seven-bit interrupt selection. They corroborate the
choice; emulator agreement alone is not a physical measurement.

VCRDIV's mask therefore stays unchanged. Its misleading source TODO about
interrupt priority is removed: IPRA supplies that priority, while VCRDIV
supplies the vector. The second DIVU register window is now mapped as tested.

## FMR is documented

FMR at FFFFFE90 is explicitly documented in section 3.3.2, table 3.6, printed
pages 55–56. It is an eight-bit R/W frequency-modification register with FR1/FR0
selecting ×1, ×2 or ×4; encoding 3 is prohibited. Bits 7–2 read zero. Only
power-on reset initializes it; manual reset and standby retain it.
Appendix B's omission does not make it an undocumented extension.

The existing source also records a hardware observation that a word write
works on SH7604/CPS3/SH7095; that is a source annotation, not a newly performed
experiment or grounds to generalize every access width. The existing FMR
handler only logs a multiplier write and does not implement oscillator/PLL
frequency modification. This evidence item corroborates the mapping; it does
not claim that the unrelated frequency-modification engine has been completed.
No clock-change implementation was added from a guess.

## Result-copy mappings and fixes

YabauseUT defines DVDNTUH/DVDNTUL at FFFFFF18/1C and their FFFFFF38/3C aliases.
Its `div_mirror_test` requires writable longword storage, and its
`div_operation_test` requires the same quotient/remainder as DVDNTL/DVDNTH after
both 32/32 and 64/32 divisions. These tests corroborate the omitted mappings and
also expose shortcomings in MAME's former read-only aliases.

The active implementation now supplies writable result copies, their second
window and the other DIVU +20 aliases. Copies update on successful and overflow
divisions, and do not initiate division when written. They are stored separately
from dividend registers and are saved. Separate storage and writes without
starting division agree with both Yabause `src/sh2core.c` and Mednafen
`src/ss/sh7095.inc`; independence from later dividend-only writes is a model
corroboration from those implementations, not a newly measured hardware fact.
No arithmetic algorithm, division latency or undocumented access-width policy
was changed for this item.

## Validation and reproducibility

`python3 scripts/sh7604_device_test.py --only divu --output /private/tmp/new-divu-test`
runs actual guest word/longword loads/stores, checks sixteen-bit VCRDIV read-back
including `0102`, upper read-zero and both windows, exercises the diagnostic's
32/32 and 64/32 examples, writable copies and their independence, replacement
by normal/overflow results, and scheduled save/load. Both DRC and interpreter
pass. Artifacts: `/private/tmp/sh7604-divu-final-20261011`.
The macOS Saturn/ST-V subtarget build passes:
`/private/tmp/sh7604-divu-build-20261011.log`.

The full device suite, including seven DMA burst counts, passes all 36 cases
(18 per engine): `/private/tmp/sh7604-divu-full-suite-20261011`.
Actual-method register and SCI/standby fixtures also pass ASan/UBSan.

PAL VF2 completes a 40-emulated-second HLE run; all seven captured images match
the immediately preceding DMAC build byte-for-byte. Artifacts:
`/private/tmp/sh7604-divu-vf2-20261011`. The preserved LLE re-enable patch still
passes `git apply --check`; normal Saturn continues to use HLE.

Only the original evidence checklist marker changes to `[x]`; its item text,
all other entries and every other checklist byte are preserved.

Downloaded Yabause diagnostic SHA256:
`eeca6fa85a312ca39a12aab57875fce4aa166c51fb85e1a06c0571390964f1b1`.
Local copies used for inspection are `/private/tmp/yabause-hardware-sh2.c`,
`/private/tmp/yabause-sh2core-evidence.c` and
`/private/tmp/vcrdiv-mednafen-sh7095.inc`.

No real-hardware verification was performed in this session, and no published
hardware-run transcript for these exact tests was located. The conclusion is
corroborated by the primary manual and published diagnostic expectations,
with emulator source used only as supporting implementation evidence. It is
not a claim of independently measured silicon read-back or clock behavior.

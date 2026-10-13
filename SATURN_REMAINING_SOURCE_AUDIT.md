# Remaining source audit — 2026-10-13

The original rewrite checklist retains its original item membership and prose.
Partial fixes below do not close a combined item.

## CD-ROM legacy metadata

`cdrom_file::parse_metadata` previously indexed an empty or truncated legacy
metadata vector, read 595 words without validating its size, and accepted an
invalid track count after byte swapping. It now rejects incomplete metadata and
counts outside 1–99 before populating the TOC. Copying into aligned word storage
also removes the unaligned/aliasing access through a byte-vector pointer.
Existing valid legacy metadata in either accepted byte order is preserved.
This does not claim that the historical host-endian format has been redesigned.

`scripts/cdrom_legacy_metadata_test.py` extracts the actual production decoder
and track structure. ASan/UBSan pass all 2,380 truncated lengths, invalid counts,
and valid 1/99-track metadata in both byte orders. The parent decoder crashes on
empty metadata under the same fixture. The full Saturn/ST-V subtarget builds.
The combined nvram/ticket/cdrom checklist item remains open.

## Mission Stick direction bits

The existing `analog` controller, ID `0x15`, is the Mission Stick rather than
the ID `0x16` 3D pad. Its displayed name now identifies it correctly, keeping its
existing slot/device identifiers. Digital directions now come from analog X/Y
instead of independent joystick switches. Active-low right/down assert at 170,
release at 149; left/up assert at 86, release at 107. The hysteresis state is
initialized, reset and saved. Analog bytes and button assignments are retained.
The device samples the axes when the host reads its digital report; this is
functional peripheral emulation, not an emulated controller MCU sampling clock.

Source: [Sega SMPC manual, Table 3.19](https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p03_30.htm).
`scripts/saturn_mission_stick_test.py` extracts the production read/reset methods:
ASan/UBSan pass both directions of every X/Y ADC code, inclusive thresholds,
history-dependent deadbands, restored hysteresis, button bits and analog bytes.
The parent fails the axis sweep. The full Saturn/ST-V subtarget builds.
This fixes part of the peripheral-format audit; it does not close the entire
SMPC errata or controller collection.

## Keyboard pad mappings and lock flags

Sega STN-45 maps pad B to X, R to E and L to Q. The active keyboard incorrectly
used B for pad B and exchanged the two shoulder buttons; all three are fixed.
Caps and Scroll Lock now have host bindings and toggle their reported flags on
**break**, matching the original STN-45 flag diagram. The existing saved status
byte retains the flags; ordinary keys and left/right Shift preserve them.

Sources: [original STN-45](https://docs.exodusemulator.com/Archives/SSDDV25/segahtml/info/hon/stn45_j.htm),
[lock transition diagram](https://www.infochunk.com/saturn/segahtml_en/info/grp/stn45_1.gif).
`scripts/saturn_keyboard_test.py` executes the production methods under
ASan/UBSan. All 13 pad mappings, the non-trigger B key, four lock cycles each,
and raw Shift make/break codes pass. The parent fails the mapping fixture.
The full subtarget builds. Num lock's physical source, controller MCU,
rollover/repeat timing and game-specific kana behavior are still open; no
unsubstantiated repeat constants or Num-to-kana substitution were introduced.

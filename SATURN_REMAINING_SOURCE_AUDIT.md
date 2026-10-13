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

## Independent DSP instruction comparison

`scripts/scsp_dsp_ymir_compare_test.py --ymir <checkout>` compiles the actual
MAME DSP and the external Ymir DSP separately into a test executable. A
callback inserted only in the generated test source compares each instruction's
TEMP, MEMS, EFREG, accumulator, fraction, Y, address and memory-pipeline state.
After each sample it compares the full 512 KiB sound RAM. 256 deterministic
random programs, lengths 1–128, all four ring sizes, 17 ring base addresses and
four successive samples pass under ASan/UBSan. Both floating and raw memory
operations are exercised. Simultaneous read/write requests and terminal memory
requests at instruction 127 are excluded from this synthetic fixture.

This is independent behavior comparison; no GPL reference code is copied into
MAME. It does not prove BIOS waveform parity: actual BIOS input traces and
whole-chip mixer/slot timing remain necessary before closing the chime item.

## VDP2 VRSIZE state and reset

The VRAM-size control bit was initialized at construction but never saved or
cleared by device reset. It is now registered for save states and cleared on
reset, per [VDP2 manual 3.1](https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p03_10.htm).
The documented initial silicon version remains read-only zero.
`scripts/saturn_vdp2_reset_unit_test.py` executes the actual reset method under
ASan/UBSan with dirty register state; it passes, and the parent fails VRSIZE.
The full subtarget builds. Native reset and scan-state fixtures include VRSIZE and pass under both DRC
and interpreter (`/private/tmp/vrsz-reset-native-20261013` and
`/private/tmp/vrsz-state-native-20261013`).
The larger VDP2 timing/source item is still open.

## Sparse multitap and mixed payload routing

A disconnected controller port now reports status `F0` and ID `FF`, rather than
zero. SMPC emits only the `FF` ID for an empty tap connector and selects payload
bytes using the physical connector index. Previously a hole shifted later data
because offsets were accumulated from earlier payload sizes; the adapters
then decoded that offset as a fixed two-byte joypad index. The new indexed
interface keeps single-controller behavior and legacy flat reads intact.
The six-port Saturn tap now offers the existing Saturn analog, racing,
trackball, keyboard and mouse devices as well as joypads, so supported mixed
packet lengths are actually configurable. Nested taps are excluded.

Source: [SMPC 3.1, Figures 3.16–3.20](https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p03_17.htm).
`scripts/saturn_multitap_test.py` runs the actual port accessors, both adapters'
indexed routing, and SMPC collection under ASan/UBSan. It passes all 64 six-port
and 16 four-port occupancy masks across all 16 port-mode combinations, mixed
1/2/3-byte payloads, empty main ports and invalid adapter indices. The parent
SMPC collector fails the same fixture. The full subtarget builds.
This does not close MCU-level controller timing, unsupported devices or the
full SMPC errata item.

Native controller validation now passes all six runs (DRC/interpreter × Mission
Stick, keyboard, mixed sparse six-port tap). `saturn_controller_report_test.py`
uses real input fields, matrix keyboard scans, controller devices and timed
INTBACK, checking the public OREG byte stream. The tap uses occupied connectors
1/3/5/6 with empty 2/4 and distinct pad/analog/keyboard payloads. Keyboard tests
exercise X/E/Q and physical Caps/Scroll make/break transitions. Mission Stick
checks both hysteresis bands. Logs: `/private/tmp/controller-reports-native-20261013`.

## SH-2 illegal delay slots — host stack overflow

The full survey's Astrass crash reproduces on the current pre-fix build. The
macOS crash report identifies stack exhaustion in recursive
`drc_frontend_base::describe_one`, following a PC-writing instruction inside a
delayed branch's slot. SH7604 manual 4.5.3 / Table 4.9 requires a slot-illegal
exception, not another branch decode.

SH-2 frontend decoding now rejects these slots before recursion, including
reserved aliases accepted by the legacy group decoders. Both engines take
vector 6 for PC-writing and undefined slot instructions, saving SR and the
original delayed jump destination. A general undefined opcode uses vector 4
and saves its own address. DRC invalid descriptors now take the exception
instead of terminating MAME. Illegal-exception overhead follows the existing
interpreter cost in both engines; its physical hardware cycle count remains
unverified. SH-3/4 behavior is not changed by the SH-2 slot predicate.

`scripts/sh7604_illegal_slot_test.py` passes both engines: 80 slots across BRA,
BSR, JMP and JSR, self-referential slot branches, all documented PC-writing
classes, undefined instructions and reserved branch aliases; checks vector,
stack depth, saved jump PC/SR and PR preservation, plus general illegal vector
4. The preserved pre-fix executable crashes under this fixture. Instruction
cache, slice-boundary and UBC native regressions also pass both engines.
Logs: `/private/tmp/sh7604-illegal-slot-final-20261013`,
`/private/tmp/sh7604-illegal-slot-parent-20261013`, `sh7604-slot-cache-20261013`,
`sh7604-slot-slice-20261013` and `sh7604-slot-ubc-20261013` under `/private/tmp`.
Retail re-tests are recorded in `SATURN_GAME_REGRESSIONS.md`: Astrass and
Decathlete no longer crash but remain black; Super Goal has a separate
host-memory failure in both engines and is still being investigated.

## Twin Stick controller

Sega SMPC 3.2's Twin Stick table maps two digital sticks and their buttons to
the standard-pad ID 02 and two-byte active-low report. A dedicated
`twin_stick` slot now exposes both eight-way sticks, both triggers/buttons and
Start, directly or through MultiTerminal 6. It reuses the pad's packet and
direct-read implementation, retaining the three high unused bits.

Source: https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p03_30.htm
Native `saturn_controller_report_test.py` passes both CPU engines for all 13
individual controls, release states and simultaneous diagonals on both sticks.
Mission Stick, keyboard and sparse multitap regressions also pass. Logs:
`/private/tmp/controller-twin-stick-native-20261013`. Hardware verification
was not performed. The broad SMPC errata/controller items remain open because
other listed features are not complete.

## Sega Tap supported peripherals

SMPC 3.3 Table 3.17 specifies Mega Drive three/six-button pads and the mouse
for Sega Tap; the previous configuration exposed Saturn pads only. Its four
subports now offer those documented devices and default to a three-button
Mega Drive pad. MultiTerminal 6 also accepts both Mega Drive pad variants, as
Table 3.21 requires. The obsolete pad-only slot helper was removed.

Native controller reports pass both engines with mixed E1/E2/E3 IDs, different
payload sizes and an empty fourth connector. All existing controller report
tests pass too. Artifacts: `/private/tmp/controller-segatap-native-20261013`.
This corrects device selection and SMPC reports; real adapter electrical
handshakes have not been checked against hardware.

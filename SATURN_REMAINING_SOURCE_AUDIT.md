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

## ST-V sound RAM map overflow

The earlier 512KiB SCSP RAM correction updated the sound-CPU and SCSP maps but
missed ST-V's SH-2 map, which still called shared RAM handlers over 1MiB.
Offsets in 05A80000–05AFFFFF therefore indexed beyond the 512KiB allocation.
Retail Super Goal failures appeared later in the Billboard Z80 or sound
68000 memory dispatch, depending on which adjacent heap storage was damaged.
The ST-V SH-2 map now ends at 05A7FFFF, matching the allocation and both sound
views. No expansion RAM or guessed mirror is provided. Expansion electrical
readback has not been verified on hardware.

`saturn_sound_ram_boundary_test.py` passes both CPU engines through actual
SH-2 master/slave and 68000 maps: first/last physical words are shared; every
word of the formerly mapped expansion range is tested for unbacked reads and
writes without altering installed RAM. Logs:
`/private/tmp/sound-ram-boundary-native-20261013`. The same test passes under AddressSanitizer in both engines. The preserved
pre-fix ASan executable fails at `soundram_w`, reading two bytes exactly after
the 524288-byte allocation (the masked write first reads the old word).
Artifacts: `/private/tmp/sound-ram-boundary-asan-fixed-20261013` and
`/private/tmp/sound-ram-boundary-asan-parent-raw-20261013`. All three retail
re-tests now finish without a host crash, but remain black at the final frame;
those game failures remain open.

## Multi-controller / 3D pad

The dedicated `multicontroller` option implements STN-43 and SMPC 3.3: digital
ID 02 with two button bytes; analog ID 16 with button bytes followed by X/Y/R/L
ADC values. The D-pad stays independent of the stick. Analog triggers use the
published hysteresis (assert at 145, release at 85). Power-on and mode changes
calibrate current stick positions to 128/128 and current triggers to zero.
Calibration, selected mode and trigger latch states are saved. The option is
available directly and on MultiTerminal 6.

Host-axis conversion uses translated calibration offsets, clamps negative
trigger travel to zero and projects stick inputs outside the documented
128-radius circle onto its boundary; stick output never reaches zero. Sega
does not publish the MCU's full ADC calibration/rounding algorithm, so this
conversion is a documented emulation model, not a hardware-validated curve.
Sources: https://www.infochunk.com/saturn/segahtml_en/info/hon/stn43.htm and
https://www.infochunk.com/saturn/segahtml_en/info/grp/stn43_2.gif .

The native controller report fixture passes both CPU engines for the two
modes, independent D-pad, trigger thresholds/deadband, circular limiting,
mode-switch calibration and actual save/load restoration. The test reapplies
the external configuration switch after load before reading the saved
calibration. All other controller regressions also pass. Artifacts:
`/private/tmp/controller-multicontroller-state2-native-20261013`. The broader
SMPC errata/controller items still include unfinished keyboard and protocol
work and remain open.

## CDRDAO TOC bounds and omitted lengths

The real `.toc` parser rejected neither track-local directives before TRACK
nor a hundredth track, risking array access outside track/input storage.
Those cases now return INVALID_DATA before access. FILE/AUDIOFILE starts with
omitted or zero length consume the remaining complete sectors; a DATAFILE
length no longer depends on being the first track. Explicit lengths, SWAP,
byte offsets and subchannel sector strides remain covered by the fixture.
Missing files, exhausted offsets and incomplete-sector remainders return an
error instead of silently generating empty/truncated tracks.

The fixture compiles the production parser/helpers against the actual CD TOC
types, with filesystem-size and unused-format adapters. ASan/UBSan passes
all nine pre-TRACK directives, 99/100 tracks, missing/zero/explicit lengths,
starts, legacy byte offsets, subcode strides, SWAP and invalid file extents.
The parent parser fails; `/private/tmp/cdrom-toc-parent-20261013.log` retains
that result. The full subtarget build and legacy-metadata tests also pass.

Source: https://raw.githubusercontent.com/cdrdao/cdrdao/master/dao/cdrdao.man .
This does not claim full CDRDAO grammar: scalar sample/byte units, WAVE input,
multiple concatenated segments and partial-sector padding remain separate
parser limitations. The original combined nvram/ticket/cdrom item stays open.

## Extended SMPC reports and pending-report save states

SMPC 3.1 Figures 3.17/3.18 define an extended size byte when the ID's low
nibble is zero. The collector now includes that size, applies the selected
15/255-byte limit and the adapter's maximum, then reads the payload from the
correct physical connector. MultiTerminal 6 limits each connector to 15 bytes
even in 255-byte mode. Figure 3.20 UNKNOWN IDs F0–FE, like FF empty slots,
produce no payload reads. Existing short reports retain their layout.

The previous report vector was empty when registered with MAME's save manager;
that overload saves its current allocation/count, not future vector contents.
The queued bytes were consequently absent from a mid-report save. Reports now
use fixed, saved 7712-byte storage with a saved used count and cursor, large
enough for two 15-connector ports with 255-byte extended payloads. Reset, BREAK
and completed reports clear the storage deterministically.

Actual-method ASan/UBSan tests pass all extended sizes 0–255, every port mode,
sparse 4/6-port masks, physical tap limits, all UNKNOWN IDs, a 516-byte paged
report and the maximum 7712-byte report. The pre-change collector fails.
Native reports pass both engines for all existing peripherals and a pending
43-byte MultiTerminal report: consume, load, change live input, CONTINUE, and
verify that the original queued bytes and final padding are restored. Logs:
`/private/tmp/controller-extended-save-native-20261013` and
`/private/tmp/smpc-extended-parent-20261013.log`. Full subtarget build passes.
Sources: https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p03_17.htm
and https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p03_13.htm .
No physical serial-protocol or collection-time verification is claimed.
The broad SMPC inline/source items still contain unrelated unfinished work.

### CDRDAO scalar units and checked extents

The follow-up decoder uses CDRDAO's documented units: scalar data positions
are bytes; scalar audio positions are stereo samples (four bytes), while MSF
positions are sectors including any subcode stride. DATAFILE's single value
is a length; FILE/AUDIOFILE's first value is a start. The legacy #byte-offset
plus start/length extension remains supported. Checked unsigned conversion
rejects malformed numbers, invalid MSF fields, overflowing extents, excessive
arguments and selections beyond the file instead of integer overflow or
later short reads. Non-sector-aligned audio starts are allowed when the
selected length contains complete sectors.

The actual-parser ASan/UBSan fixture passes scalar byte/sample and MSF cases,
all earlier bounds/length cases, and malformed/overflowing extents. The parent
parser fails the new byte-length case; log:
`/private/tmp/cdrom-toc-units-parent-20261013.log`. Full subtarget build and
legacy metadata regressions pass. WAVE decoding, concatenated segments and
partial-sector padding are not claimed complete by this change.

### Live BIOS DSP instruction comparison (2026-10-13)

The new BIOS capture scripts save thirteen real Japanese BIOS DSP states,
including sound RAM, from frames 180 through 540. Replaying each captured
program through the actual MAME and external Ymir DSP kernels matches every
executed instruction (109 per capture), pipeline registers, effect outputs
and RAM. The random-program comparison also passes. This checks the DSP
kernel, not the complete mixer or the audible BIOS chime; that item remains
open. Artifacts: `/private/tmp/bios-dsp-live-20261013` and
`/private/tmp/bios-dsp-ymir-compare-20261013.log`. No real hardware validation.

### SCSP master-volume clipping order (2026-10-13)

Master volume previously attenuated the already saturated sound-stream output.
It now attenuates the unsaturated stereo mix before either DAC path clips,
matching the order in Ymir and MiSTer's SCSP mixer. For example, a +65536
mix at half volume now reaches +32767 rather than being clipped first and
reduced to +16383. Zero volume mutes; all sixteen settings retain the
shift/quarter attenuation curve. Widened intermediate arithmetic prevents
overflow. The actual-method ASan/UBSan fixture covers signed extremes,
rounding, loud mixes and both DAC paths. Full subtarget build and native
Japanese BIOS capture pass. No real hardware verification; this is not a
claim that the remaining BIOS chime mismatch is resolved.

### SCSP send and pan attenuation (2026-10-13)

Send-level and pan lookup construction now uses exact halving steps and
quarter subtraction, as in Ymir and MiSTer's SCSP arithmetic, instead of
pow(10, rounded_dB/20). Send level 1 is 1/64; pan level 1 is 3/4. Pan 15
retains the existing mute behavior corroborated by Ymir. Total-level and
envelope attenuation are separate and unchanged. All 65,536 lookup entries
pass the actual-construction ASan/UBSan fixture, including every send/pan
combination and total-level bounds. The parent fails the new gain checks.
The full build and a 110-second native VF2J run with 48kHz audio pass;
artifacts: `/private/tmp/scsp-mix-level-vf2-20261013`. No real hardware
verification or complete BIOS chime parity is claimed.

### CD source WAVE chunk validation (2026-10-13)

The CUE WAVE reader now checks read errors and exact byte counts, uses
64-bit bounded RIFF extents, includes the eight-byte RIFF prefix in the
container boundary and skips WORD padding after odd-sized chunks. Short
format chunks, truncated payloads, oversized extents, empty data and
incomplete stereo sample frames fail instead of returning unsafe lengths.
Offsets are cleared on failure and checked before narrowing to the existing
32-bit interface. Stereo 44.1kHz 16-bit PCM support is retained.

The actual-parser ASan/UBSan fixture passes ordinary PCM, padded unknown
chunks, every truncation of a complete file, injected short reads and invalid
format/data lengths. The parent fails the padded-file assertion. Full Saturn
build and existing TOC parser tests pass. This is a source-file parser fix,
not CD hardware validation or closure of the combined unrelated global notes.
RIFF padding/extent reference:
https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-

### CUE track/index storage bounds (2026-10-13)

CUE track numbers are now checked before indexing fixed storage: they must
be sequential, within 1–99, and follow a FILE declaration. FILE after the
99th track cannot index a nonexistent next entry. INDEX, PREGAP, POSTGAP,
FLAGS and REM LEAD-OUT before the first TRACK fail. Index numbers use checked
conversion and invalid-index exits close the input stream. Empty CUE files
are rejected.

The actual-parser ASan/UBSan fixture covers all these failures, overflowing
numeric fields, duplicate/nonsequential tracks and a valid 99-track image.
The parent produces a stack-buffer-overflow on the malformed track input:
`/private/tmp/cdrom-cue-parent-20261013.log`. WAVE/TOC fixtures and full build
also pass. This closes concrete parser defects without claiming the broad
combined nvram/ticket/cdrom checklist scope is complete.

### SH7604 delayed branches to address zero (2026-10-13)

The interpreter used zero as the inactive delayed-branch sentinel, so JMP,
JSR, RTS and RTE to zero mishandled their slot and slot exceptions. It now
retains a saved pending bit for a zero destination. Interrupt/user-break
deferral, operand validation, PC-relative addressing and return from DRC
interpreter fallback use the same pending-state check. Reset, debugger PC
changes and address-error exceptions clear the bit. Untaken conditional
branches do not create a pending slot.

The native regression confirms the preserved parent interpreter takes the
wrong exception vector; the parent DRC passes. Both corrected engines pass
80 existing illegal-slot cases, six illegal and six legal zero-target slots (including BRAF/BSRF wraparound),
and a pending-zero-slot save/load/resume check. Timer slice-boundary,
instruction-cache and UBC native tests also pass on both engines. Full build
passes. Artifacts: `/private/tmp/sh7604-zero-delay-save-20261013` and
`/private/tmp/sh7604-zero-delay-parent-20261013`. This is a concrete CPU
correctness fix, not a claim to resolve every outstanding game IRQ issue.

CUE shared-file extents are also validated before subtraction/narrowing.
Descending/equal track indexes and a last-track offset beyond the source
file now fail instead of unsigned underflow producing a huge track length.
Previous-track byte extents use widened arithmetic. The native parser
fixture passes a valid two-track shared file and rejects reversed/beyond-file
indexes; the parent fails the reversed-index regression. Full build and
WAVE checks pass (`/private/tmp/cdrom-cue-extents-parent-20261013.log`).

A 110-second VF2J retail run after the delay-slot correction completes with
visible fighting attract graphics and a complete 48kHz recording:
`/private/tmp/sh7604-zero-delay-vf2-20261013`.

SCSP reset/postload explicitly restore unity output-channel gains. MAME saves
those gains, so leaving the previous post-clipping MVOL value in a compatible
state would apply attenuation twice after moving MVOL into the mixer. The
actual postload method fixture starts with two stale gains and verifies both
become unity while DSP/LFO restoration still runs. ASan/UBSan and the full
build pass. User-configured gains are stored separately and are unaffected.

# Saturn / ST-V reference audit — 2026-09-14

## Scope and evidence policy

This pass starts from `868d72fc669765f8a0b9af6503a59642d293cbae`, the inherited
Saturn work, and inspects selected files from all six requested repositories.
It is **not** an exhaustive audit or a claim of hardware-perfect emulation.
Behavior is implemented in MAME's existing callbacks; no external source code
has been imported. GitHub license metadata is only a starting point: inspect
actual file licenses before any future code reuse, especially SDK material and
repositories without a declared license. Agreement between emulators is useful
evidence, not a substitute for hardware traces.

## Pinned references

### Ymir

- Revision: `6d779960127ced72087a418c1daefc637d0aaa80`
- Inspected: [libs/ymir-core/src/ymir/hw/scu/scu.cpp](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
- Finding: `SCU::UpdateHBlank` sends SCU HBlank/timer/DMA events regardless of VB, but gates slave interrupt assertion and clearing with `!vb`. Primary reference for separating these signals.

### Saturn_MiSTer

- Revision: `a95b085038ace57fa621558d60a7adc7a3c53f78`
- Inspected: [rtl/Saturn/VDP2/VDP2.sv](https://github.com/jkind73/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/VDP2/VDP2.sv)
- Finding: `HB_INT` is set/cleared by horizontal counter comparisons, independently of the adjacent `VB_INT` logic. Supports continuing horizontal edges through vertical blanking; not proof of every downstream SCU rule.

### mednafen-git

- Revision: `f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc`
- Inspected: [src/ss/vdp2.cpp](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp2.cpp)
- Finding: `VDP2_Update` advances horizontal phases and passes horizontal and vertical states separately to `SCU_SetHBVB`. Supports independent phase scheduling; downstream SCU interrupt/timer semantics still need review.

### yabause

- Revision: `82cb29171ebe61cf0129682794af5ceb5acaa0f2`
- Inspected: [yabause/src/vdp2.cpp](https://github.com/jkind73/yabause/blob/82cb29171ebe61cf0129682794af5ceb5acaa0f2/yabause/src/vdp2.cpp)
- Finding: This fork gates `Vdp2HBlankIN` and `ScuSendHBlankIN` by the active vertical area. This disagrees with the Ymir model; it is not counted as corroboration for the fix.

### SaturnRecomp

- Revision: `26c9715e5493054b8a205aa31d73d8f125fdd8f5`
- Inspected: [runner/src/vdp2.c](https://github.com/jkind73/SaturnRecomp/blob/26c9715e5493054b8a205aa31d73d8f125fdd8f5/runner/src/vdp2.c)
- Finding: Background renderer useful for future pixel-format/compositing comparisons. Not used as evidence for scanline interrupt timing.

### saturnsdk

- Revision: `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`
- Inspected: [SBL6/SEGALIB/MAN/MANVDP2.TXT](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/SBL6/SEGALIB/MAN/MANVDP2.TXT)
- Finding: SBL scroll-library API documentation, not an electrical timing specification. Useful for future guest-side rendering tests; no timing claim inferred from it.

## Implemented: preserve horizontal edges during VBlank

The inherited `sync_timer_cb` scheduled only line starts whenever `vsync` was
true. At those positions HBlank is false, so SCU HBlank events disappeared
throughout VBlank despite the work list claiming timer 0 continued to run.

- Schedule line start and HBlank start on every logical line, not just active
  display lines. SCU HBlank-driven timer and DMA logic now receives those edges.
- Wrap only after the final HBlank edge; toggle ODD once at that boundary.
- Keep slave SH-2 HBlank assertion/clearing suppressed during VBlank, separately
  from the SCU path. `vint_callback` updates `m_prev_vint` before `hint_callback`.
- The callbacks are shared by Saturn and ST-V. No game-specific bypass added.

This deliberately preserves the current HBlank position, VBlank position,
vertical step calculation, and approximate interlace/exclusive geometry. It does
not claim those positions are hardware-accurate. The corrected scheduler adds
one callback per blanked logical line; this is an accuracy fix, not a measured
speed optimization. No extra per-pixel work or new saved state is introduced.

## Validation

Run from repository root:

```sh
python3 regtests/saturn/test_sync.py
```

The test compiles the **actual two callback bodies** with recording stand-ins for
the screen, timer, SCU and slave CPU, using C++17, warnings-as-errors and UBSan.
It checks 72 combinations (263/313/526/626/525/561 total rows; 224/240/256 active
lines; 320/352/640/704 widths), two fields each: every horizontal edge including
VBlank, wrapping, ODD changes, VBlank transitions, slave gating, and repeated
level suppression. These combinations are control-flow stress cases, not a
claim that every combination is a valid hardware mode. **All passed.** Running
the same harness against the inherited `HEAD` callback bodies fails at the first
missing VBlank HBlank event (negative control).

The stand-ins do not test MAME's timer implementation, real interrupt delivery,
SCU timer values, DMA transfers, save/load, rendering, or game compatibility.
A targeted build was attempted with:

```sh
make SUBTARGET=saturn SOURCES=src/mame/sega/saturn.cpp,src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp -j2 REGENIE=1
```

It stopped during project generation: `pkg-config`, Qt `moc`/`qmake6` are absent.
No full MAME compilation or ROM boot was completed. The ROM directory contains
no test ROMs. `git diff --check` passed.

## Next work, in priority order

1. Complete a targeted build in a configured MAME build environment; boot Saturn
   NTSC/PAL and ST-V (including Die Hard Arcade and games using HBlank DMA).
   Trace SCU timer 0 matches in active display and VBlank; check slave IRQ levels,
   save/load across VBlank, and baseline/candidate performance with identical input.
2. Audit V counter table generation and double-density lookup. The current table
   has 313 rows while double-density lookup masks a screen position to 9 bits;
   bounds and field-coordinate conversion require dedicated tests before changes.
   Simplify the contradictory table-generation comments only alongside verified
   NTSC/PAL breakpoint/field rules.
3. Resolve timer semantics against SCU specifications and hardware tests: Ymir
   increments before compare and schedules timer 1 differently from this branch.
   Do not label timer accuracy complete solely because the timers now receive edges.
4. Audit B-bus DMA transfer width, forbidden bus pairs, and wait-state accounting
   against pinned SCU implementations/RTL and SCU manual errata. Test transfer
   results and IRQ ordering, not only game boot success.
5. Compare rendering behavior using SaturnRecomp, Ymir, Mednafen and Yabause,
   with SDK-generated test patterns where redistribution permits. Prioritize
   line scroll/zoom, VDP1 erase/draw ordering and VDP2 window/rotation edge cases.
6. Profile before optimizing. Keep optimizations separate from timing changes;
   preserve callback order and deterministic output, and record measured deltas.

### Additional syntax validation

Using the recovered previous-session C++20 syntax-check recipe exposed an
inherited include-order error in `saturn_vdp2.cpp`: `emu.h` must precede the
device header, which includes `screen.h`. Corrected that order; the complete
VDP2 translation unit now passes `g++ -fsyntax-only` with the MAME include paths
and `MAME_NOASM`. All 72 callback configurations still pass. This does not
replace the pending full build or validate the complete Saturn driver.

## Mosaic clipping follow-up

Extracted only the bounds fix from the user-supplied rendering patch. The final
mosaic block is truncated to the clip rectangle in both axes; block sizes are
computed once per block rather than adding clip comparisons per output pixel.
The existing sampling origin, unit-size bypass, rotation handling, and interlace
ordering are unchanged. No speedup is claimed without profiling.

```sh
python3 regtests/saturn/test_mosaic.py
python3 regtests/saturn/test_mosaic.py --baseline  # expected failure on inherited HEAD
```

The test compiles the actual mosaic function with AddressSanitizer and UBSan.
A bounds-checked bitmap catches coordinate overruns; an independent per-pixel
oracle checks every output pixel, including unchanged pixels outside the clip.
All **16,384 configurations passed**: every 1–16 horizontal/vertical block size,
all four LSMD values, rotation/non-rotation, whole-bitmap and offset clips,
single pixels/rows/columns, and empty rectangles. The inherited HEAD version
fails the bitmap bounds assertion as expected. Existing 72 sync cases also pass.

A standalone C++20 syntax check of the complete `saturn.cpp` initially exposed
the same inherited include-order issue as VDP2 (`emu.h` must come first).
Corrected that order; the complete translation unit now passes syntax checking.

The mosaic/line-screen `TEST_FUNCTIONS` gates remain disabled: correct per-layer
compositing is still missing. This is a tested safety fix to the helper, **not**
a newly enabled game-visible mosaic implementation. Screen-over-pattern support,
CRAM byte-write behavior, RBG1 access rules, and cell-scroll width changes from
the pasted patch are not integrated. Full build, ROM-based comparisons, hardware
mosaic alignment, and save/load validation remain pending.


## V counter safety and table initialization follow-up

`get_vblank_duration()` doubles the screen height for LSMD=3, and the sync
scheduler advances by two screen rows per logical line. The V counter rollback
table contains 313 **field lines**, however the inherited getter indexed it with
`vpos & 0x1ff`. This reads outside the table at screen positions 313–511 and
incorrectly wraps subsequent screen positions to the start of the table.

The getter now divides the screen position by two before the double-density
lookup and asserts the resulting table bound. Exclusive-mode early return,
VRESO masking, non-double-density lookup, and the inherited approximate ODD-bit
encoding are unchanged. No saved-state members or layouts changed. This is a
correction to MAME's coordinate conversion, not a new hardware counter model.

The table builder now fills each entry once using region/mode jump arrays.
Existing values (including unused NTSC rows and columns) are preserved exactly.
This removes redundant startup loops and conflicting comments; it does not
provide a measured emulation speedup or validate the underlying timing values.

```sh
python3 regtests/saturn/test_vcounter.py
python3 regtests/saturn/test_vcounter.py --baseline  # expected sanitizer failure
```

The test extracts the production initializer and getter. The inherited initializer
from pinned base `868d72fc669765f8a0b9af6503a59642d293cbae` supplies the comparison
table; that commit must be available locally. The baseline option replaces only
the getter with its inherited version to reproduce the invalid access.

**42,920 checks passed** under AddressSanitizer/UBSan, including all 2,504 table
entries across both regions, every screen row for every VRESO/LSMD/ODD combination
in normal modes, and exclusive-mode bypass checks. The baseline run reports an
AddressSanitizer out-of-bounds read in `get_vcounter()`. The test uses stand-ins
for the device and screen, not the full register-latch path or MAME scheduler.

Both complete changed C++ translation units pass standalone syntax checks;
72 sync and 16,384 mosaic configurations still pass. Full build/ROM tests remain
pending. Next timing work must verify actual interlace counter encoding and
rollback positions against specifications/hardware rather than treating these
preserved values as a correctness oracle for real hardware.

## Vertical cell-scroll clipping follow-up

The existing vertical cell-scroll path replaced the caller's horizontal clip
with full 8-dot columns starting at X=0. Consequently partial updates could
modify pixels to the left of their clip and the final column could extend past
the right edge, including a bitmap boundary.

- Begin at the 8-dot column containing the clip's left edge, keeping scroll-table
  addresses anchored to screen X=0 (not rebased to the clip).
- Intersect each column with the caller's horizontal limits, preserving its
  vertical limits. Empty rectangles return without table reads or rendering.
- Retain the existing table stride for NBG0/NBG1, 11-bit signed offsets, address
  masking, and eight-dot column width. The proposed 16-dot rule from the supplied
  patch remains unverified and is not included.

```sh
python3 regtests/saturn/test_cell_scroll.py
python3 regtests/saturn/test_cell_scroll.py --baseline  # expected clip assertion failure
```

**21,312 configurations passed** with AddressSanitizer/UBSan: both VRAM-size
settings, table addresses near wrap boundaries, NBG0/NBG1/interleaved tables,
positive/negative scroll values, all left-edge alignments in a 37-pixel-wide
bitmap, clipped trailing columns, single-pixel width, and empty rectangles.
The harness compiles the production cell-scroll branch and records the nested
renderer calls. It checks table addresses, exact call counts, no duplicate pixel
coverage, expected signed scroll per pixel, and untouched pixels outside the
clip. It does not execute the nested line-scroll renderer or prove hardware
cell-scroll width/phase. The pinned inherited branch fails clip containment.

Skipping columns wholly left of a partial clip reduces table reads and nested
renderer calls; the test verifies the exact intersecting-column count. No
wall-clock speedup is claimed and full-width rendering is not accelerated.
The complete `saturn.cpp` and `saturn_vdp2.cpp` syntax checks, plus all existing
sync/mosaic/V-counter tests, still pass. ROM-based visual validation is pending.


## Primary-document reference update

The earlier limited SDK review is superseded by
[official_specs.md](official_specs.md), which records selected hardware-manual
and bulletin sections actually read, plus [sdk_documents.csv](sdk_documents.csv)
with 103 PDF entries. These findings reopen timer and rendering correctness
questions that the callback and safety tests do not answer. No runtime code was
changed during the documentation audit.

## SCU timer-1 stopped-only reload fix

ST-210 item 31 (printed p.9 / PDF p.13) says HBlank loads timer 1 only when
stopped. The branch now preserves an in-progress one-shot's deadline rather than
re-arming it at each eligible HBlank. Both `enabled()` and `expire().is_never()`
are checked: MAME's `emu_timer::adjust(never)` sets enabled=true, including on SCU
reset and TENB disable. One-shot expiry disables the timer before its callback.
No extra saved-state flag was introduced.

Cross-checks, restricted to not overwriting an in-progress count:
- [Ymir `UpdateHBlank`](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  schedules only if the timer event is not already scheduled.
- [Mednafen `SCU_SetHBVB`](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  gates HBlank reload with `Timer1_Met`. Its counter/interrupt model and Ymir's
  reload arithmetic are not identical to MAME's. Neither is wholesale copied.

```sh
python3 regtests/saturn/test_timer1.py
python3 regtests/saturn/test_timer1.py --baseline  # expected deadline assertion failure
```

**1,024 reload scenarios pass** (all 512 register encodings at 426/454-count line
intervals), plus focused checks for T1MD load gating, partial writes, and the
512-count regression. Tests check unchanged running deadlines, expiry IRQ/DMA
events, reload writes affecting the next count, no spontaneous periodic reload,
TENB cancellation and re-enabling after adjust(never). The production HBlank,
mode-write, reload-write and expiry callback bodies are compiled against a
recording scheduler with ASan/UBSan. The inherited getter-independent baseline
fails the repeated-HBlank deadline assertion.

The stand-in scheduler follows the inspected one-shot semantics of
`src/emu/schedule.cpp`; this is not a full emu_timer/device integration test.
Simultaneous expiry/HBlank ordering, hardware clock rate, exact T1MD interrupt
qualification, and save/load behavior remain unverified. Existing T1MD gating,
zero-to-512 conversion and clock divisor are intentionally retained. Timer-0
compare ordering is still open.

Complete `saturn.cpp`, `saturn_vdp2.cpp`, and `saturn_scu.cpp` syntax checks pass.
SCU's inherited include order was corrected to include `emu.h` first. All four
previous regression scripts pass. Full build and ROM testing remain pending.

## SCU timer-0 compare ordering and TENB gating

Implemented ST-097 §3.4 (printed pp.55–56 / PDF pp.71–72) and ST-210 item 30
(printed p.9 / PDF p.13):

- VBlank-OUT resets timer 0 and, when TENB is set and compare is zero, produces
  timer-0 status and DMA trigger at that event. Both VBlank-OUT and timer-0 status
  are present before pending IRQ evaluation. Timer 1 is not loaded by VBlank-OUT.
- With TENB enabled, HBlank increments the nine-bit counter before comparing it
  with the ten-bit compare register. Positive compare K matches HBlank number K
  following VBlank-OUT. TENB-off HBlanks do not increment the counter; ordinary
  HBlank IRQ/DMA processing is unaffected.
- VBlank-IN does not reset timer 0; HBlank counting continues through blanking.
  Existing register masks and TENB-off reset/cancellation behavior are retained.

Cross-checked the same pinned Ymir `UpdateHBlank`, `UpdateVBlank`, `CheckTimer0`
and Mednafen `SCU_SetHBVB`, `Timer0_Check` implementations linked in the timer-1
section. Both gate HBlank increment with timer enable and compare after increment;
both check the reset counter at VBlank-out when enabled. Their broader interrupt
and timer-1 models are not imported.

```sh
python3 regtests/saturn/test_timer0.py
python3 regtests/saturn/test_timer0.py --baseline  # expected compare-zero assertion failure
python3 regtests/saturn/run_all.py               # all six regression scripts
```

**8,192 two-frame scenarios passed** with ASan/UBSan: 263/313 HBlank events per
frame, all compare values 0–1023, TENB on/off and T1MD 0/1. Tests check the exact
event of timer-0 status/DMA generation, unsupported compare values, counting
through VBlank-IN, deasserted inputs, one-count timer-1 eligibility, no timer-1
load at VBlank-OUT, disable/re-enable, masked writes and nine-bit counter wrap.
The pre-fix callbacks from `c14588532ad776662aad5b05b65113598ea61fcf` fail the
compare-zero regression. Timer-0 and timer-1 tests now share the recording
stand-ins in `scu_timer_harness.h`; timer-1's next-match setup was updated to
account for the corrected increment order.

CRTC integration assessment: the current VDP2 sync callback dispatches VBlank
before HBlank at each position. It clears HBlank at the line start, then sends
one rising HBlank edge at `m_hdisplay`; after wrapping, VBlank-OUT occurs at line
zero's start. Thus compare K is reached at screen row K-1's HBlank for normal
modes, or row 2*(K-1) in MAME's doubled geometry. This mapping follows the current
code, not a new hardware measurement. Existing VBlank-start active+1 positioning
and approximate field geometry are unchanged and still need trace validation.

These tests execute production SCU callback bodies, not a full CPU/SCU/VDP2
machine. The IRQ stub records pending bits, not SH-2 delivery or priority arbitration;
DMA stubs record triggers, not transfers. No physical blank-boundary timing,
mid-line compare-write immediate behavior, full T1MD IRQ qualification, save/load,
or game compatibility claim is made. In particular the inherited T1MD policy
still gates timer-1 loading; other emulators qualify its expiry differently.

All six regression scripts and standalone syntax checks of `saturn.cpp`,
`saturn_vdp2.cpp`, and `saturn_scu.cpp` pass. Full build and ROM testing remain
pending; next prioritize that validation and interlace counter encoding.

## Reproducible object/full-build validation

```sh
python3 regtests/saturn/validate_build.py
```

This runs all six regression scripts, then compiles the complete changed
translation units (`saturn.cpp`, `saturn_vdp2.cpp`, `saturn_scu.cpp`) to objects
with C++20, `-O1`, `MAME_NOASM` and the recorded include paths. This exercises
code generation as well as parsing; it does **not** resolve external symbols or
link MAME. Object files are temporary and deleted automatically. Set `CXX` to
select the compiler for the object/regression checks.

**Result on 2026-09-14:** all regressions and all three object compilations passed
with GCC 12.2.0. There were no emulation behavior changes in this validation pass.

For a Debian/Ubuntu machine with package access, the intended focused-build path
is:

```sh
sudo apt-get update
sudo apt-get install build-essential python3 git pkg-config libsdl2-dev libsdl2-ttf-dev libfontconfig-dev
python3 regtests/saturn/validate_build.py --full --jobs 2
```

The full mode checks required pkg-config modules, runs regressions and object
checks, then invokes MAME's makefile with a Saturn/ST-V source filter. It disables
Qt debugging, X11, OpenGL and optional MIDI/PortAudio/PulseAudio/PipeWire backends
to reduce build dependencies. After linking it attempts `mamesaturn -validate`,
which checks machine configurations without booting ROMs. These reduced-backend
options are for build validation, not recommended final desktop performance
settings. Use `--jobs 1` on memory-constrained machines.

**Full path remains unverified:** this sandbox has neither pkg-config nor SDL
development packages. Attempts to install them via both HTTP and HTTPS Debian
repositories failed (connection/TLS errors); full-mode preflight correctly stops
at missing pkg-config. No executable was linked or configuration validation run.
The package list/build recipe may need adjustment for the target environment.
No usable ROMs are present here, so no Saturn or ST-V boot, audio, frame output,
save/load or performance comparison was performed.

## User-supplied firmware reference

The user supplied commit
[`8578abbe02220ae4d174d364b4544997cb61a2cd`](https://github.com/jkind73/mame/commit/8578abbe02220ae4d174d364b4544997cb61a2cd),
which adds eight ZIP archives under `regtests/`. Copies were inspected in an
external disposable cache. The remote branch already includes the user's BIOS
commit, which was preserved when reconciling the restored sandbox history; this
audit adds no further firmware binaries. [firmware_manifest.json](firmware_manifest.json) preserves source
commit/path, archive SHA-256, entry metadata and relevant firmware SHA-1 checks.

- `saturnjp.zip`, `saturneu.zip`, `saturnkr.zip`: console firmware candidates.
- `satcdb.zip`: CD-block firmware; `stvbios.zip`: ST-V BIOS variants.
- `segabill.zip`: Sega bill-validator firmware, not an ST-V game cartridge.
- `saturn2.zip` is Bell Games' Saturn 2 pinball (`by35.cpp`), and `saturnzi.zip`
  is the Zilec/Jaleco arcade Saturn (`blueprnt.cpp`). Neither is Sega Saturn
  firmware; exclude them from this project's boot matrix.

ZIP integrity checks passed for all eight archives. All 35 entries in the six
relevant archives have SHA-1 values present in the current Sega driver/device
ROM declarations. This is a source/hash cross-check, not MAME `-verifyroms`,
a completeness audit or a successful boot. In particular `saturnkr` currently
uses a Japanese BIOS marked BAD_DUMP as a placeholder for undumped Korean
firmware; the archive does not establish authentic Korean BIOS coverage.

This supersedes the earlier "no firmware available" limitation: the supplied
commit provides retrievable candidates for BIOS startup testing. The full-build
blocker remains, and no game cartridge/disc validation has been performed.
Availability on GitHub is not a redistribution license; this audit adds only
metadata and notes. Cache loss can be recovered using the pinned source commit.

## Double-density V-counter register encoding

Implemented the bit layout in ST-058 table 2.4 (printed p.24 / PDF p.42): in
normal/high-resolution double-density interlace, the nine-bit field count occupies
VCT9..1, with VCT0=0 for odd fields and 1 for even fields. The old expression
replaced the field count's low bit and masked to nine bits, losing both resolution
and the tenth output bit. The getter now shifts the field count and preserves all
ten register bits. The earlier screen-row/field-line conversion remains intact.

Reference cross-checks:
- [Ymir `ReadEXTEN`](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/include/ymir/hw/vdp/vdp2_regs.hpp)
  shifts VCNT using VCNTShift and inserts ODD xor 1 for double density.
  [VDP timing setup](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/vdp.cpp)
  selects a shift of one only for double density. Its separate VCNTSkip and
  field-timing calculations are not copied or treated as equivalent to our table.
- [Mednafen `GetNLVCounter` / `LatchHV`](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp2.cpp)
  shifts its field count and adds inverse ODD only for double density, then
  stores the result in the latched counter.

`test_vcounter.py` now includes an independent encoding oracle: for each of all
512 possible field counts, both field polarities and all four normal/high-res
HRESO values, decoding result bits 9:1 must recover the original count and bit 0
must recover parity. These **4,096 additional cases** also run the production
`external_latch()` function and check that all ten VCNT bits survive storage,
HCNT is captured and EXLTFG is set. With EXLTEN disabled, latch contents and flag
remain unchanged. No register-map read/side-effect integration is simulated.

The full test now passes **47,016 checks** under ASan/UBSan, retaining complete
NTSC/PAL table equivalence and mode/row coverage. All other regression scripts
and three full object compilations pass through `validate_build.py`.

```sh
python3 regtests/saturn/test_vcounter.py
python3 regtests/saturn/test_vcounter.py --encoding-baseline  # expected encoding assertion failure
python3 regtests/saturn/test_vcounter.py --baseline           # expected original bounds failure
```

The encoding negative control uses `fa629f552c338136e9945eb409e7db10bedff491`,
which already contains the bounds fix. The older negative control still detects
row 313 being read outside the table. This distinguishes the two bugs.

Non-interlace, single-density and exclusive-mode behavior is unchanged, as are
all rollback table values. The inherited note disputing the manual's non-interlace
shift is not overridden. Field lengths, ODD transition phase, rollback thresholds,
exact external-latch timing and hardware traces remain open. This is a supported
register-encoding correction, not a complete interlace timing implementation.

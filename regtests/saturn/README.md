# Saturn / ST-V reference audit — 2026-09-14

## VDP1 rendering/status audit — 2026-09-14

Implemented destination-preserving MON, coordinate-based Gouraud evaluation
(which does not stall on skipped mesh/transparent/clipped dots), explicit
component-wise color calculations, bounded color-lookup fetches, and two-end-code
row termination in the production normal-sprite loop. BEF now latches on an actual
framebuffer change rather than every VBlank in manual mode. This does not complete
scaled/distorted texture traversal, interlace, rotated scanout or pixel timing.

Tests pass: 92,420 color/shading cases, 2,689 normal-texture/boundary cases,
32,816 command/lifecycle cases, 532 framebuffer cases and 24,500 clipping cases.
Four independent render mutations (MON source replacement, dropped odd carry,
fixed Gouraud coordinate, disabled second-END termination) fail their assertions.
All 18 scripts/nine objects pass. Shader tests do not establish polygon edge or
interpolation precision on silicon; callbacks use recording timer/CPU endpoints.
Full chip completion and BIOS/game/runtime/save-manager proof are not claimed.


## VDP1 sequencer and packed framebuffer implementation — 2026-09-14

Replaced whole-list synchronous dispatch with saved, timer-driven command
execution. Lists no longer stop at a host iteration cap; CPU edits to looping
lists are seen on subsequent fetches. ENDR cancels at command boundaries, reset
cancels pending work, and a new PTMR start restarts at command zero. COPR tracks
the fetched command; LOPR latches on framebuffer changes; read-only status
register writes are ignored. Legal jump/skip/CALL/RETURN controls are tested;
nested CALLs and main-routine RETURNs are prohibited by Sega, not legal features.

Packed 8-bit drawing now shares CPU-visible words with scanout and erase, with
neighbor-byte preservation and correct word stride for high-resolution and
rotation-8 storage. All five pixel writers use shared pixel accessors. Postload
rebuilds line pointers without resetting the restored drawing bank/geometry.

18 scripts/nine object compilations pass. VDP1 coverage is now 32,814 command/
lifecycle, 532 framebuffer and 24,500 clipping scenarios. Pre-sequencer and
pre-packed-rendering substitutions fail independently, as do the older baseline
controls. Timer/CPU/raster endpoints and copied state are not runtime proof.
Primitive rendering remains synchronous; the sequencer uses a 16-cycle fetch
allowance without pixel/bus costs. ENDR's ~30-clock pipeline behavior, interlace
fields, rotated VDP2 readout, texture end-code traversal and raster/color accuracy
remain open. See `regtests/saturn/vdp1_completion.md` for the updated audit.


## VDP1 implementation pass — 2026-09-14

Fixed END-bit recognition, VRAM command wrap, completion-driven SCU IRQs (removed
periodic scanline IRQ workaround), 8-bit CPU framebuffer byte lanes, and outside
user clipping across fast/generic pixel writers. 32,775 command, 288 framebuffer
and 24,500 clipping cases pass; three independent baseline substitutions fail.
All 18 scripts/nine object builds pass. This is **not complete VDP1**: synchronous
drawing, ENDR, exact draw/erase/swap timing, BEF/pointer details, full framebuffer
formats, rasterization/texture/color edge cases and real save/load/runtime proof
remain. See `regtests/saturn/vdp1_completion.md` for evidence and acceptance gates.


## Four-priority pass — 2026-09-14

This is a bounded implementation in all four requested areas, **not completion
of all Saturn compatibility work and not a demonstrated game fix**.

1. **DMA width/fixed source:** buffer 32-bit source reads and deliver halfwords,
   advancing the source longword base by 0 or 4, rather than repeating one
   halfword for fixed-source fills. Save/reset/invalidate the buffer state at
   starts, descriptor changes and forced stop. 1,152 new ASan/UBSan cases cover
   all three channels, both ordinary writers, offsets, strides and continuation.
   The old implementation fails the source-read-count assertion. Odd transfer
   counts, destination alignment and detailed B-Bus timing remain unresolved;
   the special CD DMA path is unchanged.
2. **CD ports/completion:** inactive/wrong-direction long reads no longer throw
   emulator-fatal errors. Null partitions, array indices, invalid block sizes
   and remaining longword space are checked. Get-and-Delete accounts for whole
   deleted sectors even after a partial read, preserving block/index compaction.
   Existing first-excess-read deletion timing is retained, but DataEnd still
   receives the active command and signals EHST without deleting twice. DataEnd
   invalidates both transfer interfaces, including GET/PUT. 336 sanitizer cases
   pass. The existing all-ones idle/dummy value is not hardware-verified; partial
   GET prefetch/count reporting, zero-data count/error semantics, command range
   rejection and exact IRQ timing still need work. No successful payload is
   fabricated by invalid port reads.
3. **Reset/save-load/shared HALT:** Saturn/ST-V now OR independent SMPC, SCU
   main/slave and SCU sound HALT ownership. Reset releases SCU-owned stalls
   without releasing SMPC's halt. Driver reset clears ownership; three latches
   are saved and a postload callback reapplies the combined levels. 1,296 event
   sequences pass. DMA/HALT snapshot tests copy stand-in state and statically
   check registrations; they do **not** exercise MAME's save manager. CD save
   coverage remains incomplete (sector payloads, filter/partition pointers,
   directory and MPEG state). The ISO directory parser also needs bounds and
   subdirectory-length repairs; no untested large serialization rewrite was made.
4. **SMPC/dual CPU:** CONTINUE detects either reversal of IREG0 bit 7, not a
   high level. BREAK cancels queued continuation, acknowledges SF and prevents
   stale callbacks from producing data/IRQs. IOSEL/EXLE reset to zero. 1,173
   sanitizer cases pass; old handlers fail the handshake assertion. Simultaneous
   CONTINUE/BREAK is excluded as prohibited by Sega. The existing 700us delay
   is unchanged, not newly validated; VBlank timeout remains open. DCC width
   filtering and synchronized FRT delivery were inspected, not retimed; paired
   SH-2/DRC runtime traces are still required.

Validation: **17 regression scripts and nine object compilations pass**. The
ninth object is SMPC; adding it exposed and fixed its `emu.h` include ordering.
No linked executable, MAME save/load round trip or BIOS/game boot was validated;
the SDL/pkg-config dependency blocker remains. Source, tests and evidence are
kept in Git; downloaded PDFs and temporary build products stay outside it.

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

This runs all thirteen regression scripts, then compiles eight complete translation
units: `saturn.cpp`, `saturn_vdp2.cpp`, `saturn_scu.cpp`, `saturn_dcc.cpp`,
`sat_console.cpp`, `stv.cpp`, `saturn_cd_hle.cpp` and `saturn_cdb.cpp`.
The flags use C++20, `-O1`, `MAME_NOASM` and
MAME/shared include paths. MAME's `scripts/build/complay.py` generates the three
required ST-V layout headers (`critcrsh`, `segabill`, `segabillv`) in the temporary
object directory. No generated headers or objects are checked into Git.

This exercises code generation as well as parsing, including the console and
ST-V driver configurations; it does **not** resolve external symbols, link MAME,
or validate those configurations at runtime. Temporary files are automatically
deleted. Set `CXX` to select the compiler for the object/regression checks.

**Latest result on 2026-09-14:** all thirteen scripts and eight object compilations
pass with GCC 12.2.0. Widened validation found and corrected `emu.h` include
ordering in DCC, ST-V and CD HLE, without changing emulation behavior. Earlier
sections below retain their historical three- and six-object results.

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
User-supplied firmware has since been archived and hash-inspected, but without a
linked executable no Saturn/ST-V boot, audio, frame output, save/load or performance
comparison has been performed.

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

## EXTEN reset coherence

ST-058 §2.5 (printed p.19 / PDF p.37) states that the external signal enable
register is cleared on power-on or reset. EXLTEN=0 selects counter latching on
EXTEN reads; EXLTEN=1 selects external signals. The inherited reset cleared
`m_exten` but left `m_exlten`, `m_exsyen`, `m_dasel` and `m_exbgen` unchanged.
This allowed readback to report zero while behavior still used pre-reset controls.

Reset now explicitly clears all four decoded controls alongside the register.
Cross-checks: [Ymir VDP2Regs::Reset](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/include/ymir/hw/vdp/vdp2_regs.hpp)
clears the packed EXTEN value, and
[Mednafen VDP2::Reset](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp2.cpp)
clears all four decoded controls. No reference code was imported.

```sh
python3 regtests/saturn/test_exten.py
python3 regtests/saturn/test_exten.py --baseline  # expected decoded-control assertion failure
```

**64 write/reset/latch scenarios passed** with ASan/UBSan. The harness compiles
the actual reset and external-latch callbacks plus the EXTEN read/write lambda
bodies. It covers all sixteen control combinations, full/masked write sequences,
repeated reset, readback/control coherence, restored register-read latching,
suppressed external latching after reset, side-effect-disabled reads and guest
re-enabling EXLTEN. Masked writes preserve existing software handler behavior;
they are not a claim about unsupported physical byte accesses. The negative
control uses the pre-fix reset from `167c45469b379251c68cef6ff81d6b57ceed58c4`.

The beam counters, scheduler, CRTC reconfiguration and machine wrapper are
recording stand-ins. These tests do not exercise the actual address-map dispatcher,
TVSTAT flag clearing, complete register reset semantics or lightgun input timing.
Latch contents/status flags are not changed by this patch; the test resets its
latch sentinels separately to observe each access. No saved-state layout changes.

All **seven** regression scripts and three object compilations pass through
`validate_build.py`. Full linking, boot, save/load and game tests remain pending.

## TVMD power-on and device-reset coherence

ST-058 §2.4 (printed p.16 / PDF p.34) specifies that TVMD clears to zero after
power-on or reset. Both [Ymir VDP2Regs::Reset](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/include/ymir/hw/vdp/vdp2_regs.hpp)
and [Mednafen VDP2::Reset](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp2.cpp)
clear the register/display controls and interlace/resolution selections.

The inherited MAME callback reset only `m_old_tvmd`, leaving TVMD and its decoded
controls from the previous session. Also, only HRESO and VRESO were initialized
in device_start, although device_t::start invokes notify_clock_changed before
device reset, which calls VDP2 reconfigure_crtc and reads LSMD. Added in-class
initializers for TVMD, its change latch and all five decoded fields; device reset
now clears raw and decoded state before reconfiguration. Removed redundant
startup assignments and misleading commented-out reset lines. No new saved
members, change to region/DOTSEL configuration, or change to the register's
existing masked-write/change-detection logic.

```sh
python3 regtests/saturn/test_tvmd.py
python3 regtests/saturn/test_tvmd.py --baseline  # expected reset readback assertion failure
```

**3,072 startup/write/reset scenarios passed** under ASan/UBSan. The test compiles
member initializers from the production header, TVMD read/write lambda bodies,
reset callback, CRTC reconfiguration and timing helpers. A recording screen
checks that startup and reset configure the current default 320x224 geometry
with 427 horizontal total and 263/313 vertical total, and that raw/decoded state
agrees. The matrix covers both regions, every LSMD/VRESO/HRESO bit combination,
DISP/BDCLMD combinations, full writes and both half-register write orders,
repeated reset, and the existing first-low-byte-write configuration behavior.
This includes reserved-mode stress cases, not a claim they are valid hardware
modes. Existing half-register mask behavior is not validation of physical byte
accesses prohibited by the manual.

The negative control uses the old reset from `f8b5cff9036f93c438a85083429277e73c9e6c92`
with the new header initializers, isolating stale reset state rather than relying
on undefined startup memory. Screen/timer behavior is mocked: no complete device
startup, physical beam timing, live resolution-switch scheduling, SMPC-to-VDP2
reset wiring or BIOS boot is executed. The geometry assertions preserve MAME's
current conventions and are not hardware timing measurements. Other registers'
reset values and status/latch flags remain separate audit work.

All **eight** regression scripts and three object compilations pass through
`validate_build.py`. Full build and BIOS/game execution remain pending.

## SCU high work-RAM mirror classification

Both Saturn (`sat_console.cpp`) and ST-V (`stv.cpp`) map high work RAM as
`0x06000000..0x060fffff` with mirror mask `0x21f00000`. The SCU's manually coded
address classifier only accepted the `0x06xxxxxx` half of the physical C-Bus
window; `0x07000000..0x07ffffff` returned no bus. Direct DMA using those aliases
was rejected as illegal. Indirect descriptor decoding uses the same classifier,
so upper mirrored destinations also missed C-Bus write-mode selection there.

Added the missing `0x07000000` switch case. The change preserves existing wait
penalties, address masks, bus restrictions and transfer routines. References:
- [Ymir GetBusID](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/include/ymir/hw/scu/scu_defs.hpp)
  masks addresses to 27 bits and classifies the entire range at or above
  `0x06000000` as work RAM.
- [Mednafen AddressToBus and DMA_ReadCBus](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  classify the same range as C-Bus and mask RAM reads to the 1 MiB storage;
  transfer addresses are constrained to 27 bits.

This fix reconciles SCU decoding with the existing machine address maps and two
independent emulator implementations. The official-document audit has not yet
established a precise section specifying the full mirror aperture; do not cite
this as newly hardware-measured or as verified from the overview's RAM size alone.

```sh
python3 regtests/saturn/test_dma_bus.py
python3 regtests/saturn/test_dma_bus.py --baseline  # expected classification assertion failure
```

**768 address classifications and 2,304 mirrored DMA scenarios passed** under
ASan/UBSan. Tests cover all 32 one-MiB mirrors, physical and `0x20000000` aliases,
read/write classification, boundary offsets, all three DMA levels, programmed
write increments 0/2/128, A-Bus-to-C-Bus acceptance, C-Bus-to-VDP2 acceptance and
same-C-Bus rejection. Actual production direct setup and two word-transfer steps
are executed; C-Bus destinations must use fixed word stepping, while emitted
addresses retain the correct physical mirror. Neighboring bus decoding and
selected A-Bus wait fields are checked for regressions. The negative control
uses the classifier from `2cc26488273905f3623ef0b1d1e0fcd2e4a1e020`.

Memory and DMA timer/IRQ endpoints are recording stand-ins; this does not test
RAM alias resolution in MAME's address-space dispatcher, DMA completion, bus
arbitration, timing, or a full indirect-descriptor chain. The indirect consequence
above follows code inspection rather than an executed indirect DMA integration
test. No broad DMA-accuracy completion claim or measured speedup.

All **nine** regression scripts and three object compilations pass. Full linking
and BIOS/game runtime validation remain pending.

## Indirect DMA descriptor count and chain execution

Indirect descriptor counts now use twenty bits on all three channels, with a
masked count of zero representing 1 MiB. The inherited path used eighteen bits
on channels 1/2 and left zero as zero, causing short or maximum-size requests to
finish after the first word. The direct register masks/default sizes are unchanged.

Evidence is separated by source:
- ST-097 §2.1 (printed pp.19–20 / PDF pp.35–36) describes three-longword descriptor
  execution and repeated transfers; §3.2 (printed p.42 / PDF p.58) describes the
  different **direct register** count widths. ST-210 item 25 (printed p.8 / PDF
  p.12) specifies the count/destination/source order and final source bit 31.
  The inspected manual sections do not explicitly establish the all-channel
  descriptor count width or zero encoding.
- [Ymir DMAReadIndirectTransfer](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  normalizes every channel's descriptor count into 1..0x100000 with a 20-bit mask.
- [Mednafen NextIndirect](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  explicitly masks to 20 bits and converts zero to 0x100000 without a channel split.
- [MiSTer SCU.sv](https://github.com/jkind73/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/SCU/SCU.sv)
  uses 20-bit DMA_RTN/WTN and loads descriptor bits 19:0 in both indirect-read
  paths, corroborating the width. This audit did not simulate the RTL countdown.

```sh
python3 regtests/saturn/test_dma_indirect.py
python3 regtests/saturn/test_dma_indirect.py --baseline       # expected zero-count failure
python3 regtests/saturn/test_dma_indirect.py --baseline-wide  # expected channel-1 width failure
```

**54 two-descriptor chains passed through completion**, executing actual production
start, wait/move selection, descriptor fetch, word transfers, pointer update,
completion IRQ, and return-to-idle code with ASan/UBSan. Cases cover all channels,
WUP both ways, sizes 0, 4, 0x1004, 0x23000, 0x40000, 0x80000, 0xffffe, and reserved
high-bit encodings. Full 1 MiB requests are transferred word-by-word, not fast-
forwarded. The second descriptor exercises C-Bus-to-SCSP following A-Bus-to-C-Bus,
using an upper RAM mirror for table/data. Tests check source end-bit stripping,
six ordered descriptor reads, no fetch past the final entry, word addresses/data,
no premature completion interrupt, final status, bus-steal callback counts,
WUP pointer changes and unchanged direct-only source/count registers.

The negative controls use DMA ticks from `e718c19335be7944e183b3746966a82a518eb959`.
The GCC test wrapper locally suppresses `-Wmaybe-uninitialized` around extracted
production definitions because GCC 12 diagnoses an anonymous temporary in the
sanitized pointer-to-member dispatch; ASan/UBSan remain enabled and the assertion/
setup code remains warning-checked. Other tests retain their existing flags.

Memory endpoints record requests and return deterministic test data rather than
implementing MAME address-space/RAM alias resolution. Timers are recording stubs;
ticks run sequentially, not in a CPU scheduler. Single-channel legal word-aligned
chains are covered; concurrency, held triggers, illegal transfers, odd-byte
counts, unusual source increments, descriptor boundary wrapping, save/load and
real bus timing are not established. This expands the previous direct-only DMA
coverage without claiming complete indirect DMA hardware accuracy.

All **ten** regression scripts and three object compilations pass. Full linking
and BIOS/game runtime tests remain pending.

## Two-channel DMA priority and ownership handoff

Corrected the preemption branch in `dma_tick_cb`: after promoting the waiting,
higher-priority channel to MOVE, it must put the **previous moving channel** into
WAIT. The old code put the newly promoted channel back into WAIT, leaving the
lower-priority channel running. Live source/destination/count/descriptor state is
retained while suspended. Resumption clears the existing background bit and
continues from the saved transfer position.

On selection and resumption, CPU halt callbacks are now set for the new owner
rather than retaining the previous owner's state or leaving both deasserted after
completion. This preserves the current MAME direct/indirect policy (direct halts,
indirect steals cycles; sound halt depends on SCSP access). It is **not** evidence
that this policy itself matches the hardware's bus-dependent arbitration.

Evidence:
- ST-097 §3.2, printed p.41 / PDF p.57: priority runs from level 2 (highest) to 0.
- ST-210 item 20, printed p.7 / PDF p.11: only two simultaneous DMA channels
  guarantee priority. Item 35, printed p.10 / PDF p.14: starting level 2 during
  level 1 is prohibited. Tests use pairs 0/1 and 0/2, not the prohibited case.
- [Ymir RecalcDMAChannel](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  selects from level 2 down to 0, keeping active channel state.
- [Mednafen SCU_UpdateDMA](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  visits active channels in descending priority. Its RecalcDMAHalt uses bus-dependent
  rules and contains its own overlap TODO; it does not verify MAME's halt policy.

```sh
python3 regtests/saturn/test_dma_indirect.py
python3 regtests/saturn/test_dma_indirect.py --arbitration-baseline  # expected priority assertion failure
```

The DMA harness now passes **64 two-channel arbitration scenarios**, in addition
to the previous 54 indirect chains. The matrix covers pairs 0/1 and 0/2, both
arrival orders, every direct/indirect pairing, and both sound/non-sound destinations
for each channel. Tests run production ticks and verify MOVE/WAIT/background
bits, no progress in the suspended channel, correct halt callback handoff,
resumption without restarting, final source/destination positions, exact word
counts, completion IRQ order, descriptor-read count, and return to idle. The
pre-fix ticks from `317dc6b785e4d675db89485914e0f2aea407da69` fail the priority
assertion. Existing count-decoding negative controls remain available.

Tests retain MAME's granularity: the current channel gets its existing transfer
step before the tick performs arbitration. They do not establish exact preemption
latency, simultaneous last-word/completion ordering, real CPU halts, three-way
DMA, DSP overlap, illegal level-1/2 sequences or actual memory bus timing. The
recording memory/scheduler and GCC warning exception documented above still apply.

All ten regression scripts and three object compilations pass. Full MAME linking
and BIOS/game runtime validation remain pending.

## Held external DMA triggers — audit and regression coverage

**No production change was warranted by this audit.** The existing one-slot
`pending_trigger` handling passed the cases below. `test_dma_indirect.py` now
extracts the actual `dma_start_factor_ack` event filter and `dma_event_id_t` in
addition to the start/tick/transfer/completion functions already covered.

Primary evidence:
- [ST-210-110194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-210-110194.pdf),
  printed p.7 / PDF p.11, items 21–23: enable AND matching start factor; hold a
  trigger arriving during DMA once and execute it after completion; do not rewrite
  the active channel's registers. Item 20 limits guaranteed priority to two
  channels; item 35 prohibits starting level 2 during level 1.
- [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf),
  printed pp.45–46 / PDF pp.61–62: enable, one-shot DxGO, address updates and
  the seven external start factors. The tests here exercise external events,
  **not the MMIO DxGO write lambda**.
- [Mednafen](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  sets the boolean `GoGoGadget` for enabled matching external events, consumes it
  in `CheckDMAStart` only when inactive, and calls that function again in
  `SCU_DoDMAEnd`. This independently corroborates the one-slot held restart.
- [Ymir](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  `TriggerDMATransfer` agrees on enable/event gating but filters `!ch.active`.
  The inspected pinned path therefore does **not** corroborate holding external
  triggers during active DMA; it was not copied over the primary-document-backed
  MAME behavior.

**924 held-trigger scenarios pass with ASan/UBSan**:
- 756 cases: all three channels, all seven external factors, direct RUP/WUP in
  all four combinations or indirect WUP either way, triggers in initial WAIT,
  active MOVE or the done-before-IRQ phase, and bursts of one or three triggers.
- 168 cases: level 0 suspended under either level 1 or level 2, with the same
  event/mode/update/burst combinations. No prohibited level-1/2 start sequence.

Assertions check disabled and nonmatching events are ignored; matching busy
triggers change only the pending latch, not live state, registers, memory/IRQ/
bus callbacks or timer scheduling; and the held trigger survives suspension.
Both activations execute all their words. Tests verify updated or preserved
source/destination registers are used on restart, indirect tables are re-read
at the correct pointer, each activation produces a completion callback, repeated
triggers yield only one restart, and the timer stops with idle status and no
third activation. Setup writes occur while idle. IRQ acknowledgement is a change
to the recording endpoint, not an exercised MAME register handler.

```sh
python3 regtests/saturn/test_dma_indirect.py
# Each command below deliberately mutates only the extracted temporary C++
# translation unit and MUST fail a regression assertion:
python3 regtests/saturn/test_dma_indirect.py --hold-mutation drop
python3 regtests/saturn/test_dma_indirect.py --hold-mutation sticky
python3 regtests/saturn/test_dma_indirect.py --hold-mutation enable
python3 regtests/saturn/test_dma_indirect.py --hold-mutation factor
python3 regtests/saturn/test_dma_indirect.py --hold-mutation stride
```

All five controls failed their intended assertions: missing hold, uncleared hold,
disabled-event acceptance, wrong-factor acceptance and wrong status-field stride.
These are **mutation tests**, not claims that those faults exist at current HEAD
or that a newly fixed historical baseline was reproduced. Mutation targets have
occurrence-count guards against silent drift and never modify production files.

Together with 54 indirect chains and 64 arbitration scenarios, all ten regression
scripts and three object compilations pass. Initial WAIT/done-phase acceptance
is a regression check of the existing software model, not proof of hardware
trigger setup/hold timing. Real scheduler/IRQ delivery, DxGO writes, reset/save-
load while a trigger is held, continuous event streams, illegal configurations,
DSP overlaps and BIOS/game behavior still require further validation. The existing
recording-endpoint and GCC warning-exception limitations remain unchanged.

## A-Bus refresh register reset and write mask

Corrected AREF reset to **0x10** (ARFEN set, ARWT zero), and constrained stored
writes to bits **4:0**. Byte/halfword/longword masked writes preserve untouched
implemented bits. ARFEN is not forced high on every write: a software prohibition
on changing a bit does not itself establish that the hardware ignores writes.

Evidence and reference differences:
- [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf),
  printed p.72 / PDF p.88, figure 3.30 and table 3.24: ARFEN is bit 4, ARWT is
  bits 3:0. This older figure prints an initial value of zero.
- [ST-210-110194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-210-110194.pdf),
  printed p.10 / PDF p.14, item 33, explicitly **changes** the power-on reset
  value to ARFEN=1 and says software should not change that bit. This supersedes
  the older figure; ARWT remains zero.
- [MiSTer SCU_PKG.sv](https://github.com/jkind73/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/SCU/SCU_PKG.sv)
  gives `AREF_WMASK = 0x1f`; SCU.sv applies that mask on writes. However,
  `AREF_INIT = 0` still follows the older reset value, not item 33.
- [Mednafen scu.inc](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  masks AREF writes to `0x1f`, but also resets AREF to zero.
- [Ymir scu.cpp](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  ignores the AREF write cases. It does not independently establish a reset value.
  The reset correction follows the explicit Sega erratum, not implementation consensus.

```sh
python3 regtests/saturn/test_scu_abus.py
python3 regtests/saturn/test_scu_abus.py --baseline-reset  # expected reset assertion failure
python3 regtests/saturn/test_scu_abus.py --baseline-write  # expected stored-value assertion failure
```

The harness extracts the **complete production device_reset**, AREF/ASR write
handlers, address classifier, and header bus/channel/enum definitions. It passes
32 dirty-state resets, **32,768 refresh writes**, 288 ASR writes and 24,576 static
wait classifications with ASan/UBSan. Refresh writes cover all 32 initial and input
low-bit patterns, all 16 byte-enable combinations, and reserved bits zero/all-one.
ASR tests protect the other register and existing preread-bit filtering; classifier
tests cover all combinations of the three four-bit wait fields in both directions.
Each negative control independently substitutes the corresponding body from
`0d7e9fe416ef866951290d2816211eff0ffc32c4` and fails its intended assertion.

**Scope:** AREF is stored/saved but is not currently consumed by MAME's bus timing.
This is a register-state correction, not actual refresh emulation or a demonstrated
performance/game fix. The existing `AnNW+3` decoder is checked for regression,
not validated as cycle-accurate. Tests call handlers directly with recording timers;
MMIO routing, actual CPU halt/reset interactions, physical refresh pulses, power-
on versus SMPC reset wiring, and save/load round trips remain untested. No ASR
mask/timing change or permanent-ARFEN write protection was inferred from this audit.

All **eleven** Saturn regression scripts and three object compilations pass.
Full linking and BIOS/game runtime validation remain pending.

## A-Bus interrupt mask polarity and delivery regression

Corrected IMS bit 15 from an active-high enable to an **active-high mask**, matching
bits 13:0: one blocks, zero allows delivery. Previously the reset/acknowledgement
value `0xbfff` could permit external interrupts, while clearing bit 15 blocked
requests that software intended to enable. The per-source AIACK pending gate,
internal priority table, vector fetch and status write semantics are unchanged.

Evidence:
- [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf),
  §3.5, printed p.57 / PDF p.73: zero does not mask, one masks; figure 3.21 and
  its first field definition explicitly include A-Bus mask IMS15. Printed p.27 /
  PDF p.43, table 2.1 supplies the source/vector/priority assignments. Table 3.8
  (printed p.59 / PDF p.75) defines status writes: zero resets, one preserves.
  §3.6 (printed p.61 / PDF p.77) describes external acknowledgement and rearming.
- [Mednafen scu.inc](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  computes `IPending & ~(int16)IMask`; sign extension of IMS15 masks all external
  bits when it is set. `SCU_MSH2VectorFetch` restores `IMask = 0xbfff`.
- [Ymir scu.cpp](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  `UpdateMasterInterruptLevel` instead includes external bits when
  `m_intrMask.ABus_ExtIntrs` is one. `InterruptMask` in scu_defs.hpp makes this a
  direct bit-15 field, so the inspected pinned implementation disagrees with the
  manual on polarity. It agrees on priority levels and the vector-ack mask reset,
  but its external-mask condition was not copied over the primary specification.

```sh
python3 regtests/saturn/test_scu_irqs.py
python3 regtests/saturn/test_scu_irqs.py --baseline  # expected polarity assertion failure
```

The new ASan/UBSan harness extracts the actual arbiter, IMS/IST readers and write
handlers, external input handler, AIACK writer and vector-acknowledgement callback,
plus the header's writable mask. It passes:
- **1,920 arbitration cases:** each external source versus each internal source
  (or none), independent mask settings and existing per-source pending-ack gating.
  Checks priority, vector, selected status-bit consumption and preserved pending
  bits; vector fetch clears the issued CPU line and restores all masks.
- **16 acknowledgement sequences:** one for each external source. Masked requests
  remain pending, unmasking delivers them, later requests cannot replace an already
  issued vector, AIACK respects its byte lane, and a queued higher-priority internal
  request is retained until explicitly unmasked.
- **512 masked register writes:** IMS defined-bit filtering/preservation and IST
  write-zero-to-clear across all 16 byte-enable combinations and mixed data/state.

The pre-fix arbiter from `024d7e28b1c4a67e6f667f89e2999eaaf2e519d8` fails the
expected IRQ-level assertion. Tests record CPU input-line calls and invoke vector
acknowledgement directly; they do not run SH-2 instructions or MAME address-space
routing. Physical request sampling/deassertion, same-class multi-source tie cases,
complete external acknowledge bus cycles, and global versus per-source AIACK
hardware behavior are not established. No change to those behaviors was inferred
from the mask-polarity fix. CD/game effects still need runtime confirmation.

All **twelve** regression scripts and three object compilations pass; full linking,
BIOS boot and game validation remain pending.

## DMA programmed address-register width

Changed DxR/DxW write masks from `0x27ffffff` to **`0x07ffffff`** on all three
channels. The old mask incorrectly retained the SH-2 cache-alias bit 29 in stored
registers and readback. For example, writing `0x26012345` now programs `0x06012345`.
Bits 26:0, including bit 0, are preserved; this is not an alignment restriction.
Direct count-register masks and indirect descriptor decoding are unchanged.

Evidence:
- [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf),
  §3.2, printed p.41 / PDF p.57, figures 3.1/3.2 and their field definitions:
  all three DxR/DxW registers implement bits 26:0. Printed p.42 / PDF p.58
  defines D0C bits 19:0 and D1C/D2C bits 11:0, retained in this change.
- [Ymir WriteRegLong](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  writes both address fields using `bit::extract<0, 26>(value)` on every channel.
- [Mednafen scu.inc](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  masks writes to StartReadAddr and StartWriteAddr with `0x07ffffff`.
- [MiSTer SCU_PKG.sv](https://github.com/jkind73/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/SCU/SCU_PKG.sv)
  specifies `0x07ffffff` for both read and write masks of DxR and DxW.

```sh
python3 regtests/saturn/test_dma_regs.py
python3 regtests/saturn/test_dma_regs.py --baseline src  # expected source readback failure
python3 regtests/saturn/test_dma_regs.py --baseline dst  # expected destination readback failure
```

The harness extracts the actual three register read/write lambdas from dma_map,
instantiates them for levels 0/1/2, and uses the header's channel structure. It
passes **15,360 address writes/readbacks and 7,680 direct count writes/readbacks**
with ASan/UBSan. Cases cover 40 single-bit/alias/boundary/mixed data patterns, four
valid initial values, all 16 byte-enable combinations, preserved untouched bits,
and isolation from other registers/channels. Extra cache-alias checks retain
odd addresses rather than silently imposing alignment. Each negative control
substitutes only the named pre-fix register handler from
`eca12b2a22c8448d76d38eaf6d8076b69a4d6b4d` and fails its readback assertion.

This validates programmed register storage and readback, not the complete MAME
MMIO dispatcher, live-register write restrictions, DxGO activation or real cache
coherency. The existing transfer code already masks host memory accesses to 27
bits; no changed transfer data or game/performance improvement is claimed here.
Address-update overflow at the end of the 27-bit window, save/load normalization
and whole-device execution from these writes are not tested or changed.

All **thirteen** regression scripts and three object compilations pass. Full
linking and BIOS/game runtime validation remain pending.

## DMA control-register decoding and software-start gate audit

**The existing implementation passed; no production change was needed.** Extended
`test_dma_regs.py` to extract the actual DxAD, DxEN/DxGO and DxMOD/RUP/WUP/FT write
lambdas and the header's event enum. Together with the address/count tests, this
covers the six programmed register handlers without duplicating their bodies.

Evidence: [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf)
§3.2, printed p.43 / PDF p.59, tables 3.2/3.3, defines source addition 0/4 and
write-add decoding 0/2/4/8/16/32/64/128. Printed pp.45–46 / PDF pp.61–62 defines
enable bit 8, one-shot GO bit 0 with factor 7, mode bit 24, RUP bit 16, WUP bit 8
and factor bits 2:0. [Ymir WriteRegLong/TriggerImmediateDMA](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
agrees on those decoded fields and the immediate-start gate.
[Mednafen scu.inc](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
merges masked control writes and checks GO, Enable and SF==7 together.

**13,824 control-register scenarios pass with ASan/UBSan**:
- 6,144 enable/GO cases: all channels, all 16 byte-enable combinations, initial
  and written enable states, GO zero/one, all eight factors and both DMA modes.
  Checks the selected start endpoint/channel and that a later enable-byte-only
  write does not replay GO.
- 1,536 address-add cases: every encoded increment, contrasting initial values,
  all channels and byte-enable combinations, with reserved bits set.
- 6,144 mode/update cases: every defined-bit input combination, contrasting initial
  values and byte-enable combinations. Untouched bytes and other channels must
  remain unchanged; merely changing mode/add fields must not call a start endpoint.

```sh
python3 regtests/saturn/test_dma_regs.py
# Deliberate temporary test-only mutations; each MUST fail an assertion:
python3 regtests/saturn/test_dma_regs.py --mutation go-lane
python3 regtests/saturn/test_dma_regs.py --mutation enable
python3 regtests/saturn/test_dma_regs.py --mutation factor
python3 regtests/saturn/test_dma_regs.py --mutation dispatch
```

All four controls failed the expected start-dispatch assertion. They remove the
GO-byte, enable or factor gate, or invert direct/indirect dispatch. Mutation targets
are occurrence-count guarded and affect only temporary extracted C++, never MAME.
They are not newly reproduced historical production bugs.

Start methods in this harness are recording endpoints: these checks cover the
register-to-start decision, **not** register writes through MAME's MMIO dispatcher
followed by real transfer execution/IRQ. No DMA actually runs between the test
writes. The hardware prohibition on rewriting active registers and the documented
bus-specific restrictions on increment settings are not relaxed or validated by
these field-decoding tests. CPU bus access granularity, save/load and actual game
behavior remain open. Existing transfer/held-trigger tests independently exercise
production start/tick functions but do not close that complete integration gap.

All thirteen scripts and three object compilations pass. Full linking and runtime
validation remain pending.

## Wider driver/DCC object validation

Added `saturn_dcc.cpp`, `sat_console.cpp` and `stv.cpp` to the normal object-check
path. The standalone build exposed `saturn_dcc.h`/`stv.h` being included before
`emu.h`. DCC failed on undefined MAME attributes/types (including `ATTR_COLD`);
ST-V reached the explicit `divo.h` diagnostic requiring `emu.h` first. Moving
`emu.h` ahead of the device headers fixes both without changing executable logic.

ST-V also needs the normal `src/mame/shared` include directory (`rax.h`) and three
compiled layout headers. The validator now supplies that directory and runs the
repository's actual layout compiler against the checked-in `.lay` sources in a
temporary directory. It does not substitute dummy layout definitions or rely on
stale generated files in a previous build tree.

Negative validation used both original translation units from
`7af22fbcf041c93dde51e5075e534414cd41c149`, compiled from temporary files with
all required include directories and freshly generated layouts. Both still failed
on include-order/type-definition errors, **not** missing `rax.h` or layout files.
The fixed files pass under the same object flags. All thirteen regression scripts
and all six objects pass through `validate_build.py`.

This is a build-integration fix, not a new Sega hardware-spec interpretation.
It does not cover every linked Saturn/ST-V dependency, replace a full MAME build,
exercise the DRC at runtime, or establish DCC interrupt/handshake accuracy. Full
linking, configuration validation, BIOS/game execution and performance measurements
remain pending. No firmware, downloaded references or generated artifacts were
added to Git in this increment.

## CD component object validation

Added `saturn_cd_hle.cpp` and `saturn_cdb.cpp` to routine object compilation.
The original CD HLE translation unit at
`186593db3cb90a90fbfe7464567d11fc7b7ddc7d` failed under the same standalone object
flags: its header preceded `emu.h`, triggering `romentry.h`'s explicit include
order error and incomplete `device_t` errors through the CD image headers.
Moved `emu.h` first. The CD block wrapper already compiled and needed no source
change. Both files now compile without forced includes or precompiled headers.

All thirteen regression scripts and eight complete objects pass through
`validate_build.py`. The change does not alter CD command processing, sector
buffering, timing, audio, authentication or the disabled SH-1 in the CD block
wrapper. This is build coverage only; CD emulation fidelity is not established by
compilation. Linking, configuration validation, actual disc access and BIOS/game
execution remain pending, as does validation of other transitive dependencies.
Objects and generated layouts remain temporary and are not committed.

## DMA forced stop — previously missing register control

Mapped DSTP at `$05fe0060` and implemented its bit-0 command for the three
CPU-programmed channels. Effective writes cancel MOVE/WAIT/background status,
completion retirement and the one-slot held restart. The DMA timer stops. Programmed
addresses/counts/enables and already-pending interrupts are preserved, so a later
start is a fresh transfer. No end IRQ is manufactured for a canceled transfer.

Under the existing halt/cycle-steal model, halt outputs asserted for a running
direct channel are released. An idle/WAIT-only stop does not release halt lines
that may belong to another component. DSP status is left alone; the handler does
not reset or abort the separate DSP engine.

Evidence:
- [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf),
  §3.2, printed p.47 / PDF p.63, figure 3.11: DSTOP bit 0 stops DMA in operation.
  The following pages define the channel WAIT/MOVE/background status bits.
- [Ymir scu.cpp](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scu/scu.cpp)
  has byte/word/longword stop cases that clear the three channels' active state
  and active-channel selection without issuing completion interrupts.
- [Mednafen scu.inc](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/scu.inc)
  case 0x60 tests data AND mask AND bit 0, clears Active/GoGoGadget for all levels,
  and recalculates CPU halt. That reference marks the stop case TODO: Test;
  it corroborates the implementation model, not physical timing measurements.

```sh
python3 regtests/saturn/test_dma_indirect.py
python3 regtests/saturn/test_dma_indirect.py --stop-noop  # expected stop assertion failure
```

**2,321 forced-stop scenarios pass with ASan/UBSan**: 2,304 cases over levels,
direct/indirect mode, initial WAIT/MOVE/done-before-IRQ, held/non-held starts,
all 16 byte-enable masks and four data patterns; 16 supported two-channel overlap
cases; and an idle CPU-DMA case preserving DSP status/other halt ownership.
Effective stops do no further memory work or completion signalling. All effective
single-channel cases execute a later fresh transfer through completion. Zero and
masked-out writes are checked for no state/callback/timer changes. The register-map
binding is checked in source and compiled in the full SCU object.

The negative control deliberately substitutes a no-op for the handler, modelling
the old unmapped write at `3527325f9ae68d2528c7c7efa761c45f319bd548`; it is not an
extracted old handler (none existed). It fails the stopped/status assertion.
Existing held-trigger mutation controls were rerun and still fail their intended
assertions; the sticky-hold target is scoped to completion rather than stop cleanup.

Stop is immediate at the current software callback boundary. Exact hardware
termination latency, partially issued bus accesses, real shared HALT ownership,
DSP overlap and scheduler/MMIO/game execution remain unvalidated. The work does
not claim a particular title is now running. All thirteen scripts/eight objects
pass. See [game_blockers.md](game_blockers.md) for the broader compatibility plan
and remaining priorities; not all missing game-blocking behavior is implemented.

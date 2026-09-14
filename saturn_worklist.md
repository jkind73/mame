# Saturn Work List — ordered by reference coverage (5 refs: Ymir, MiSTer, mednafen, yabause, SaturnRecomp)

## OutRun visual regression report — investigation, not fixed

The user reports sprites flashing on/off and an oversized, off-center image,
suspecting reversed scaling coordinates. Exact game variant, running commit and
scene have not yet been confirmed. Treat this as unresolved runtime evidence;
passing extracted tests do not establish that OutRun renders correctly.

Review of ST-013 pp.73–76/120–123 agrees with the current register roles: XA/YA
is the anchor, XB/YB the display extent in zoom-point mode, and XC/YC the opposite
corner in two-coordinate mode. No X/Y reversal has been demonstrated. The VDP2
compositor also has separate mode-dependent horizontal/vertical doubling, while
framebuffer scheduling may independently explain flashing. These are investigation
paths, not established causes; no coordinate swap or timing workaround was applied.

Added observational `VDP1TRACE` logging, enabled with `-verbose -log`. Rebuild this
branch, append those flags to the **same launch command that reproduces the bug**,
and capture a short section showing the failure. Preserve `error.log` (it can grow
quickly and be overwritten by the next run), the launch command/build revision,
and a screenshot or short video. The trace records raw scaled-sprite coordinates,
source/destination dimensions and computed bounds; TVMR/FBCR/PTMR, HRESO/LSMD;
framebuffer ownership, busy state, COPR/LOPR and raster cursor; register writes,
starts/aborts/END and bank changes. It introduces no emulated-state fields and is
disabled without verbose logging. No game-specific hack was added.

All 18 regression scripts and nine production object compilations pass after the
instrumentation. The extracted renderer fixture stubs the trace sink; object
compilation checks the production logging implementation. No linked OutRun run,
trace capture, root-cause confirmation or visual fix is claimed here.

## Pre-clipping disabled traversal — 2026-09-14

Pclp=1 now preserves normal/scaled row traversal and native line/quad spans instead
of applying advance clipping/rejection. Pixel writers continue enforcing system,
user, mesh and physical framebuffer bounds. Normal sprites consequently count END
markers encountered before the visible window; those markers can terminate a row
without drawing any pixels. Queued offscreen work remains interruptible and cannot
prematurely fetch END. Scaled synchronous sampling now indexes temporary source
coordinates relative to the span, safely handling negative/offscreen X.

The queue allows 8192 spans (416 KiB of descriptors): two signed 13-bit scaled
endpoints can be that far apart with clipping disabled. Native quad traversal is
still bounded by its 4096-row recurrence. Reset retains the constant-time active
index/cursor reset, not a bulk descriptor clear. No new persistent cursor fields
were necessary; fetched PMOD, coordinates and normal END count were already saved.

Validation adds **10,681 cases**: 10,560 literal normal-sprite images across texture
formats, packed storage, direction, END enable, mesh, user clipping and offscreen
origins; eight offscreen cursor/END-count state copies, with CPU edits to a future
END marker and pending ENDR, also using Gouraud; 112 scaled/native images and one
8192-row interruption/capacity case. Physical packed words are checked independently
of derived line pointers. Three forced-preclip mutations fail queue assertions;
a hidden-END-skipping mutation fails the image oracle. All 18 regression scripts
and nine production object compilations pass.

Primary [ST-013-R3](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf)
p.83 explicitly distinguishes disabled pre-clipping from per-dot clipping, and
pp.86–87 describes END termination/read direction. Cross-checks: pinned
[MiSTer](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/VDP1/VDP1.sv)
gates separated-line rejection and boundary stopping on `!PCLP`, separately from
END detection; pinned [Mednafen](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp1.cpp)
likewise distinguishes `PCD` in `SetupDrawLine`. No reference renderer was imported.

This does **not** complete pre-clipping: Pclp=0 horizontal/vertical start reversal
and its END ordering, exact setup/VRAM costs, extreme/degenerate qualification and
native/scaled source-prefetch timing remain open. Existing texture cutoff caches
are not a hardware FIFO model. Active-display erase and linked game/save-manager
acceptance also remain unfinished; the prior dependency-fetch blocker is unchanged.

## Rectangular Gouraud endpoint and interpolation correction — 2026-09-14

Normal/scaled sprites now prepare integer edge-then-row Gouraud values, matching
this core's native primitive model. Scaled rectangles include the final row and
both destination endpoints; normal rectangle endpoints use character size minus
one. Clipped or reversed coordinates retain their original gradient position.
This removes stale shading on scaled final rows, including one-row rectangles.
A saved per-row representation tag distinguishes integer data from the retained
legacy fallback. The legacy helper also swaps its stored X origin with endpoint
colors when the input endpoints are reversed.

2640 independent queued Gouraud images cover normal/scaled sprites, one-dot and
short dimensions, reversed axes, all texture directions, clipping, and Gouraud
modes 4/6/7. Three legacy-origin probes pass. Existing rectangle interruption and
state-copy/Gouraud-table-edit tests still pass. Missing final row, reversed origin,
wrong interpolation length and legacy-origin mutations all fail assertions.
All 18 regression scripts and nine production object compilations pass; the final
standalone run additionally includes the three legacy probes.

Primary [ST-013-R3](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf)
pp.64–65/106 assigns correction values to A/B/C/D, then interpolates and saturates;
pp.118–123 defines normal character extents and inclusive scaled endpoints, with
independent coordinate inversion. Exact integer ties follow the existing native
model cross-checked against [Ymir GouraudChannelStepper/Edge](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/include/ymir/hw/vdp/renderer/common/vdp1_steppers.hpp).
The pinned [MiSTer RTL](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/VDP1/VDP1.sv)
uses fractional division for Gouraud setup (`GRD_DIV_*`), so exact rounding is not
claimed to have three-way agreement or hardware-trace proof. No external renderer
code was imported. Preclip/degenerate qualification, exact timing, active-display
erase, linked BIOS/game execution and real save-manager acceptance remain open.

### Linked-build attempt after the Gouraud correction

Retried dependency installation rather than treating the earlier missing tools as
permanent. This workspace allows passwordless package installation, but Debian
package indexes could not be fetched: HTTP connections failed and HTTPS terminated
during TLS, including alternate mirror probes. Consequently `pkg-config`, SDL2 and
SDL2_ttf development files remain unavailable. `validate_build.py --full` stops at
its missing-`pkg-config` preflight. No linked binary, game boot or real save-manager
round trip was produced. This is an environment blocker for linked acceptance,
not evidence that the remaining VDP1 behavior is complete. Downloaded references
and failed build/dependency logs remain outside Git.

## Interruptible normal/scaled sprites — 2026-09-14

Normal and scaled sprite commands now enqueue rectangle rows and share the saved
raster worker. Normal sprites retain their fetched END count within a row; scaled
sprites retain integer sampling, direction/HSS/EOS and source-row END cutoffs.
Prepared rectangular Gouraud scanline coefficients are save-registered, rather
than reconstructed from a potentially modified VRAM table after loading.

**1040 queued rectangle cases pass**: 1024 texture/format/direction/HSS/EOS images
and 16 normal/scaled interruption and state-copy sequences, including Gouraud,
blending, source END and a mid-command Gouraud-table edit. Completed lifecycle
images also match synchronous rendering. Reset-END-count and replayed-texture
cursor mutations fail assertions. All 18 scripts and nine production objects pass.
The command harness now actually executes both rectangle pixel paths when enabled;
geometry-only dispatch fixtures remain explicitly separate.

All ordinary primitive families now yield within commands. The unspecified scaled
zero-height fallback remains atomic. Timing is still batched/nominal: early normal
END detection can leave unused clocks in an already-scheduled quantum, coverage
pairs can produce two writes per position, and fetch/setup/VRAM arbitration is not
measured. Active-display erase, preclip/degenerate qualification, linked BIOS/game
execution and actual MAME save-manager tests remain open. **VDP1 completion is not
claimed.** This supersedes the atomic-normal/scaled limitation in older entries.

## Interruptible native polygons/distorted sprites — 2026-09-14

The saved raster queue now also handles commands 2/3/4, retaining span texture
coordinates, Gouraud endpoints, the signed line-error cursor, pending coverage
and the texture-row END cutoff cache. Up to 4096 spans are bounded by the native
12-bit outer-edge length. Reset clears active indices, not the entire 208 KiB
span array. Pixel writes are evaluated when their slice executes, not pre-rendered
or replayed. END fetch waits for the raster queue; ENDR discards pending work.

**4362 additional queued-quad cases pass**: 3840 native-image comparisons, 512
texture/packed-format/HSS/EOS/direction combinations, eight mid-span state-copy
and ENDR sequences, maximum capacity and wholly clipped completion. Texture tests
use the actual VRAM writer and command decoder. Restored END cutoffs survive a
source edit; this establishes model consistency, not hardware prefetch behavior.
Lost-coverage and wrong-texture-row mutations both fail image assertions. All
18 regression scripts and nine production object compilations pass.

Primary constraints remain ST-013-R3 pp.20, 51–56 (progression/termination/END);
geometry reuses the integer recurrence cross-checked against pinned Ymir steppers,
not imported renderer/scheduler code. A slice processes up to 16 raster positions
and their paired coverage dots (potentially 32 writes). This is nominal timing,
not measured bus arbitration or single-dot visibility. **Normal/scaled sprites
remain atomic**. Active-display erase, exact timing, preclip/degenerate cases and
linked BIOS/game/actual save-manager acceptance remain unfinished. Older progress
entries below describe their checkpoints, not the current primitive coverage.

## Interruptible VDP1 lines/polylines — 2026-09-14

Added saved, bounded pixel slices for line/polyline commands, ENDR cancellation,
fetch/END ordering, short-slice scheduling and restart handling. 748 image/lifecycle
cases pass; unlimited-quantum and lost-cursor mutations fail. All 18 scripts/nine
objects pass. Sprite/polygon paths remain atomic; bus timing, hardware pre-clipping
and linked runtime/save-manager validation remain unfinished. Details are in
`regtests/saturn/vdp1_completion.md` and `regtests/saturn/official_specs.md`.


## Bounded VBlank erase — 2026-09-14

Implemented Sega's field-limited erase capacity, captured erase ownership/data,
blank-only rotation/HDTV erase scheduling and save/reset handling. All 12 primary
table capacities and 154 erase/lifecycle cases pass; three mutation controls fail.
All 18 scripts/nine objects pass. Erase commits coarsely at blank end; per-clock
arbitration, active-display erase, interruptible primitives and real runtime/save
validation remain unfinished. See `regtests/saturn/vdp1_completion.md` and
`regtests/saturn/official_specs.md` for the current evidence and acceptance limits.


## Framebuffer field control and register latches — 2026-09-14

- Bank changes and automatic PTMR drawing now occur at screen field start
  (VDP2 VBlank OUT), not VBlank IN. This is scanline-resolution scheduling,
  not the final HBlank-edge timing model.
- Manual erase is consumed in the next field without requiring a later manual
  change. VBE erases the displayed bank after the first blank line and repeats
  while enabled, even without a fresh FBCR change request. Erase is still atomic;
  per-line/blank-budget truncation and scanout interaction remain unfinished.
- TVM changes no longer reset bank ownership. DIE, DIL, EOS, erase data and erase
  bounds latch on bank change, rather than being read live by rendering/erase.
  New latch state is save-registered; postload reconstructs views without latching
  pending writes. Zero-mask register accesses cannot submit requests.
- Removed the obsolete deferred-clear flag and debug-dependent automatic start.

Evidence: ST-013-R3 p.35 register switch timing, pp.38–40 manual modes and VBE,
p.43 DIL; MiSTer a95b085 FRAME_CHANGE/VBOUT and DIE/DIL latches; Mednafen f0ee9d5
field-boundary erase-parameter latching; Ymir 6d77996 VDP1SwapFramebuffer and its
explicit pending-latch TODO. No wholesale reference code was imported.

Tests execute production scanline, register-write, bank-change and erase helpers
through two multi-field sequences, one per bank. They cover no-op writes,
manual erase without a later swap, one-shot requests, persistent VBE, automatic
start phase, preserved ownership, and delayed DIE/EOS/erase settings. Wrong field
phase and wrong erase latch mutations fail assertions. All 18 scripts/nine object
compilations pass. No linked game/BIOS or actual save-manager round trip is claimed.

VDP1 remains incomplete: raster primitives are still atomic, so ENDR cannot stop
inside one; pixel/VRAM arbitration, erase budgets, hardware pre-clipping and exact
boundary timing still need implementation and runtime qualification.


## Native line and quad coverage — 2026-09-14

Lines/polylines now use a signed 13-bit integer line-error datapath with directional
ties, inclusive endpoints and per-dot Gouraud progression. Polygon/distorted
commands now walk A–D and B–C edges, resampling the shorter edge before drawing
each connecting line. They no longer use the affine quad filler. Coverage pixels
share the current texel/shade and can blend the destination again; they are not
filtered antialiasing. Distorted spans now use integer texture stepping, HSS/EOS,
per-source-row END limits and per-edge/per-span Gouraud colors. Safe host-only
out-of-bounds rejection retains a margin for coverage pixels; this is not a model
of the hardware pre-clipping optimization.

Validation adds 2,500 complete line images (all small octants, mesh, clipping and
Gouraud) and 3,840 complete quad images (regular/skewed/reversed/twisted/degenerate
geometry, texture flips, HSS/EOS, END, clipping modes, mesh, translucency and
Gouraud). The quad tests execute the actual distorted-command entry point. The
pixel oracles use closed-form geometric rounding rather than the implementation's
iterative edge/line accumulators. Removing coverage pixels or changing edge phase
fails assertions; line direction and vertex-pair controls also fail. Full 18-script/
nine-object validation passes, with no linked BIOS/game or real save/load run.

Primary: ST-013 §§7.6–7.9 (distortion, polygons, line/polyline semantics), §§6.3/6.8
(texture/color controls and Gouraud tables). Pinned Ymir 6d77996 line/edge/quad
steppers and per-edge gradients cross-check the implemented integer model;
MiSTer a95b085 supplies a separate texture-error datapath cross-check. This is
not a claim that all their precision/timing choices agree with hardware.

Still unfinished: interruptible pixel execution, pixel/VRAM timing, automatic
swap/erase/transfer timing and latch qualification, hardware pre-clipping behavior,
scaled/normal Gouraud precision qualification, and linked runtime/save-manager
acceptance. The older affine filler survives only as the explicitly unqualified
zero-height scaled-pattern fallback; its remaining presence is not the normal
polygon/distorted rendering path.


## Scaled integer texture stepping / HSS / EOS — 2026-09-14

Scaled sprites now use a dedicated integer texture walker instead of the affine
quad sampler. A closed-form error accumulator preserves reduction/enlargement
and directional tie behavior; horizontal coordinates are computed once and reused
across rows. HSS decimates the source before sampling and EOS selects original
source-X parity, independently of texture flips and geometry direction. Clipping
does not restart the sampling phase. Source-row END limits still apply outside
HSS reduction, including HSS-enabled enlargement. Zero-width patterns repeat their
first texel; the zero-height legacy fallback remains explicitly unqualified.

Added 593,920 recurrence/pixel cases covering both directions, source/destination
sizes, vertical scaling, all six texture modes, ECD, HSS/EOS, clipping, 16-bit and
both packed 8-bit layouts. The iterative oracle is separate from the production
closed-form calculation. Wrong texture phase and ignored EOS mutations fail.
All 18 scripts/nine objects pass; no linked runtime or save-manager proof.

Primary: ST-013 pp.81–82 (HSS/EOS and sampling diagrams), p.86 HSS/ECD table.
MiSTer a95b085 TEXT_ERROR and Ymir 6d77996 TextureStepper agree on the tested
integer recurrence. **Disagreement:** primary p.86 says HSS-reduced end codes
become colors even with ECD clear; the inspected Ymir/MiSTer pixel gates suppress
them. This implementation follows the primary table, not a claimed three-way
agreement. Sega recommends ECD=1 for HSS reduction. The blanket HSS wording on
pp.81/159 also conflicts with the enlargement row of that table.

Distorted sprites still use the affine fallback: their HSS/EOS/edge stepping,
polygon/line coverage, precise Gouraud interpolation, pre-clipping, automatic
swap/erase timing and a resumable pixel pipeline remain unfinished.


## Scaled traversal and line shading follow-up — 2026-09-14

- Scaled-sprite endpoints now decode signed fields before anchor arithmetic,
  preserving independent geometry inversion and texture direction. Zero extents
  describe one dot; odd centered extents retain the correct endpoint distance.
- The affine scaled/distorted path now applies second-END source-row termination
  with HSS disabled. Each referenced row is scanned at most once per primitive;
  reduction cannot skip the terminators and repeated enlarged samples cannot
  count one terminator twice. Both span paths share the same implementation.
  This does **not** implement HSS/EOS decimation or hardware edge walking.
- Lines now initialize their own Gouraud data using A/B only. Every polyline
  edge initializes the appropriate pair (A/B, B/C, C/D, D/A), instead of using
  stale data for the first three edges and a mis-mapped table for the last.
- New tests: 12,000 scaled endpoint/anchor/direction cases; 2,924 source-END and
  actual affine-span cases; 160 line/polyline Gouraud endpoint cases using the
  production table reader and shading setup. Three new mutations fail assertions.
  The complete 18-script/nine-object validator passes; no linked runtime proof.

Evidence: ST-013-R3 pp.86–87 (horizontal source END), pp.120–123 (scaled
coordinates/anchors and zero extents), §§7.8–7.9 (polyline vertex colors, line A/B
colors only); pinned Ymir renderer scaled endpoints and per-edge Gouraud pairs.
The p.86 HSS/ECD table distinguishes enlargement from reduction, unlike the
blanket HSS wording on p.159. HSS is explicitly left to a proper fetch stepper,
not guessed from the presence of the flag. Affine edge coverage, interpolation
precision, pre-clipping, pixel timing and real save/load remain unfinished.


## Rotation, interlace and delayed ENDR — 2026-09-14

Implemented six-parameter-A sprite framebuffer readout in both rotated formats,
with signed Q9 accumulation, parameter-table masking/VRAM-size selection and
transparent out-of-plane samples. All three sprite compositor paths use it.
Double-interlace drawing selects the latched DIL parity and halves physical Y;
full-frame display weaves completed-field snapshots, not a bank being redrawn.
Physical banks are now 256 KiB, including CPU-window mirroring, physical erase
rows and wrapped line views. Both physical payloads and field snapshots are
save-registered. **Correction:** the old framebuffer payloads were not registered;
previous pointer/postload tests did not establish framebuffer-content saving.

ENDR now schedules termination after 30 modeled SH-2/VDP1 clocks instead of
aborting immediately. Reset/restart/END cancels pending termination. Primitives
remain atomic: this is not a completed pixel pipeline or measured bus timing.

Validation: 18 scripts/nine objects pass; VDP1 has 92,420 color/shading, 2,689
normal-END, 974 rotation, 32,832 command, 532 framebuffer, 24,500 clipping cases
and two multi-step interlace lifecycle sequences (16-bit/high-resolution 8-bit).
Rotation/parameter-B mutations and all four previous render mutations fail
assertions. Field tests cover DIL latching, parity, snapshots during redraw,
postload pointer reconstruction, physical erase rows and CPU mirroring.
No linked BIOS/game run or actual save-manager round trip is claimed.

Primary: ST-013-R3 pp.15,43,47–51; ST-58-R2 pp.159–160. Cross-checks: pinned
MiSTer a95b085 (rotation datapath/physical banks), Ymir 6d77996 (affine readout),
Mednafen f0ee9d5 (field parity/physical Y). MiSTer confirms Q9 truncation before
accumulation; Ymir's Q10 differs. Rotation-8 byte selection follows transformed
source X; MiSTer's output-X byte mux remains an unresolved reference difference.


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


Post 07ee024a fix — SCSP boots, 0 TODO in SCSP.

## Tier 2 — next (high coverage, should be doable)

### 1. VDP2 H/V blank + V counter rollback (5/5 refs) — **DONE**

- Files: `saturn.cpp` @TODO list (vpos 0=0x1ff VBE, 1=0, 241=0xf0 VBI, 247=0x1ef rollback, 263=0x1ff), `saturn_vdp2.cpp:418` refine hblank/vblank, `446` second setting at 241, `484` T0C runs after.
- Implemented: true_vcount table with BREAK/JUMP (NTSC 224 236->486, 240 245->495, PAL 224 257->458, 240 265->466, 256 273->474), VBI active+1, HBlank via m_hdisplay, sync_timer walks VBlank.
- Refs: Ymir vTimingsNormal, MiSTer BREAK/JUMP.

### 2. SCU timer0/1 semantics (5/5 refs) — **DONE**

- Files: `saturn.cpp` @TODO: Timer 0 doesn't work if TENB not enabled, fires at HBlank-In not before; Timer1 0=512, counts backwards from 0x6b; Yabause note DISP bit gates vblank irqs.
- Fixed: T1MD at 0x0098 (was 0x009A) so TENB actually enables timers, timer0 at HBlank-In, timer1 0=512 handling, DISP gates VBlank flag per TB12.

### 3. SCU waitstate penalties (2 refs: MiSTer + Ymir partial) — **DONE**

- Files: `saturn_scu.cpp:446` waitstate penalties needs HW tests, `517` SDRAM refresh overhead, `403` FIXME /4 vs BIOS.
- Implemented: ASR0/ASR1/AREF at 05FE00B0/B4/B8, AnNW+3 formula, dma_hog_bus steal callbacks.

### 4. SMPC TH control mode — 3D Lemmings ID (1-2 refs) — **DONE**

- File: `sat_console.cpp:821` — TH Control mode returns ID, Ymir has handling.
- Implemented: TH=3 returns ID per Ymir smpc.cpp.

### 5. DOTSEL guard (2-3 refs) — **DONE**

- File: `saturn_vdp2.cpp:307` guard against wrong DOTSEL from SMPC.
- Implemented: reconfigure_crtc checks m_dotsel_352 vs HRESO bit 0, logs instability.

## Tier 2 — medium coverage

- SCU DMA bus validation (`saturn_scu.cpp:636,790`) — we did directional rules in 6113d660, but TODO other rules still applies.
- DCC irqline 0xff vs 0x00 (`saturn_dcc.cpp:114`)
- B-Bus dword read / word write (`saturn_scu.cpp:903`)

## Tier 1 remaining (low coverage)

- CD HLE MPEG ROM retrieval (`saturn_cd_hle.cpp:2542`) — needs MPEG cart ROM dump, Ymir has MPEG.
- CD sector read path (`saturn_cd_hle.cpp:2208`)

## Tier 3 — rendering edge cases (long tail, 0-2 refs, game-specific)

- VDP1 automatic draw timing (Night Striker S)
- VDP1 framebuffer clear on VBE
- VDP2 line scroll / line zoom (Batman Forever)
- VDP2 rotation param window (OVPNRA/B)
- Pretty Fighter X, Game Tengoku shadows, etc.

## Tier 4 — refactor

- VDP1/VDP2 code structure split (issue #8915) — move out of saturn_state
- NVRAM config change bug
- Spaghetti / optimization TODOs

## Follow-up audit — 2026-09-14

The DONE labels above describe inherited implementation work, **not complete
hardware validation**. Review and test results are in
[`regtests/saturn/README.md`](regtests/saturn/README.md).

- Fixed a remaining scheduler gap: HBlank edges were still skipped throughout
  VBlank, starving SCU timer/DMA events. Slave HBlank IRQs remain VBlank-gated.
- Callback regression harness passes 72 configurations and rejects the inherited
  implementation. Full build/game validation is pending (missing build tools).
- Next: runtime timing traces, V counter/interlace bounds and field-coordinate
  audit, then SCU timer semantics and DMA bus width. Do not assume existing
  breakpoint tables or wait-state formulas are validated solely by DONE labels.

### Mosaic bounds follow-up

- Applied clipping safety fix from the supplied candidate patch, without enabling
  the incomplete mosaic/line-screen compositing paths.
- 16,384 sanitizer-backed helper configurations pass; inherited implementation
  fails the bounds assertion. Full `saturn.cpp` syntax check passes after fixing
  its inherited include order. Details: `regtests/saturn/README.md`.


### V counter bounds and table follow-up

- Fixed double-density screen-row indexing: divide by two before field-table
  lookup, rather than masking a doubled screen position to nine bits.
- Simplified region-specific initialization to one fill per table cell. All
  2,504 entries remain identical to the inherited implementation.
- 42,920 table/getter checks pass with ASan/UBSan; the inherited getter reproduces
  an out-of-bounds read. Exact rollback thresholds and interlaced counter encoding
  are still unverified. Exclusive-mode lookup behavior is unchanged.
- Updated `saturn_todo_inventory.md` with current-branch validation notes.

### Vertical cell-scroll clip follow-up

- Fixed caller clip containment for first/last columns; skip wholly clipped
  columns and empty clips while preserving screen-anchored table addressing.
- 21,312 sanitizer-backed configurations pass; inherited code fails the clip
  assertion. Reduced nested-renderer call counts verified, not benchmarked.
- Existing eight-dot width retained. Sixteen-dot character behavior, combined
  line zoom/vertical line scroll, and game-level output remain unverified.


## Official SDK specification audit — 2026-09-14

See [`regtests/saturn/official_specs.md`](regtests/saturn/official_specs.md)
and its 103-PDF manifest. Selected hardware-manual and bulletin sections were
read, not just SDK library documentation. Indexed does not mean fully reviewed.

**Reopened correctness items supported by primary documentation:**
- SCU timer 1: ST-210 item 31 allows HBlank reload only while stopped; current
  code unconditionally re-arms on eligible lines. Fix/test this next.
- SCU timer 0: ST-210 item 30 puts compare-zero at VBlank-OUT; current callback
  clears without comparing, while HBlank compares before incrementing.
- V counter: ST-058 table 2.4 specifies double-density field count in bits 9:1;
  current approximate encoding remains inconsistent. Bounds safety is fixed,
  exact hardware encoding is not.
- Vertical cell scroll: fractional table data and bulletin #14 combined-scroll
  example are not handled by the current restricted path.
- Screen-over repeated pattern is cell-format only; include this restriction in
  any future implementation. CRAM byte prohibition does not prove ignored writes.

No emulator changes made in this audit pass; earlier DONE labels must be read
alongside these reopened items.

### SCU timer-1 stopped-only reload — implemented and unit-tested

- ST-210 item 31, cross-checked with Ymir and Mednafen: preserve a running count
  across HBlank; reload only when stopped. Account for MAME adjust(never) leaving
  enabled=true. No new saved-state members.
- 1,024 reload scenarios plus gating/mask tests pass under ASan/UBSan; baseline
  fails repeated-HBlank deadline test. Existing tests and three syntax checks pass.
- Timer-0 compare ordering remains next. Full timer accuracy, actual T1MD IRQ
  qualification, simultaneous event ordering and ROM compatibility remain open.

### SCU timer-0 ordering — implemented and callback-tested

- ST-210 item 30 / ST-097 §3.4, cross-checked with Ymir and Mednafen: compare zero
  at VBlank-OUT; increment before HBlank compare; TENB gates counter operation.
- 8,192 two-frame scenarios pass; pre-fix callbacks fail compare-zero regression.
  All six regression scripts and three syntax checks pass. Use
  `python3 regtests/saturn/run_all.py` to reproduce the complete ROM-free suite.
- Physical CRTC phase, immediate register-write effects, full T1MD IRQ semantics,
  save/load and runtime compatibility remain unverified. No blanket timer DONE.
- Next priorities: full build/runtime validation and interlaced counter encoding.

### Build-validation follow-up

- All six regression scripts and object-code compilation of the three changed
  C++ translation units pass using `regtests/saturn/validate_build.py`.
- Full-build preflight fails because pkg-config/SDL development dependencies are
  missing; sandbox package downloads failed over HTTP and HTTPS. No linked MAME
  executable or ROM boot validated. A documented `--full` recipe is preserved
  for a machine with dependencies; it is not yet verified end-to-end.

### Supplied firmware availability

- User commit `8578abbe02220ae4d174d364b4544997cb61a2cd` supplies BIOS/CD firmware
  candidates. Archive integrity and 35 relevant entry SHA-1s checked against Sega
  source declarations; metadata preserved in `regtests/saturn/firmware_manifest.json`.
- `saturn2`/`saturnzi` are unrelated games, not Sega Saturn BIOSes. Korean BIOS is
  still the driver's BAD_DUMP placeholder. Audit adds no additional binaries; the
  user's remote BIOS commit is preserved.
- BIOS availability no longer blocks future startup checks; full executable build
  remains blocked and BIOS hashes are not evidence of successful boot/game tests.

### Double-density VCNT encoding — implemented and tested

- ST-058 table 2.4, Ymir and Mednafen agree: field count in bits 9:1, inverse ODD
  in bit 0. Fixed the getter's bit replacement/nine-bit truncation.
- 47,016 V-counter checks now pass, including 4,096 independent encoding/latch
  cases. Pre-encoding and pre-bounds negative controls both fail as expected.
- All six regression scripts and three object compilations pass. Normal/single-
  density/exclusive behavior and all rollback values are unchanged. Exact field
  timing and runtime validation remain open; no blanket interlace DONE.

### EXTEN reset coherence — implemented and tested

- ST-058 §2.5 plus Ymir/Mednafen: reset clears all four decoded EXTEN control bits
  with the raw register, restoring register-read HV latching.
- 64 write/reset/latch scenarios pass; baseline reset fails coherence. Seven
  regression scripts and three object compilations pass. Whole-device reset,
  actual address-map dispatch, lightgun timing and runtime validation remain open.

### TVMD startup/reset coherence — implemented and tested

- ST-058 §2.4, Ymir and Mednafen: initialize TVMD/decoded controls before startup
  clock notification, clear them on device reset before CRTC reconfiguration.
- 3,072 header-initializer/register/reset/CRTC scenarios pass; old reset fails.
  All eight regression scripts and three object compilations pass.
- No change to region/DOTSEL or saved-state layout. Full-device reset integration,
  other register/status initialization and BIOS/game runtime remain unverified.

### SCU C-Bus mirror decode — implemented and tested

- Recognize high work-RAM mirrors in `0x07000000..0x07ffffff`, matching both
  machine maps and Ymir/Mednafen. Direct DMA no longer rejects these aliases;
  the shared classifier also supplies C-Bus mode selection for indirect entries.
- 768 address checks and 2,304 direct DMA scenarios pass; old classifier fails.
  All nine regression scripts and three object compilations pass.
- Full indirect DMA execution, bus timings and exact official mirror-aperture
  documentation remain unverified. This does not complete the wider DMA audit.

### Indirect DMA count decoding — implemented and chain-tested

- Use twenty-bit descriptor counts on all channels; masked zero means 1 MiB.
  Ymir/Mednafen agree; MiSTer corroborates descriptor width. ST-097/ST-210 support
  the descriptor format, not an explicit all-channel count-width claim here.
- 54 two-entry chains execute through completion with ASan/UBSan, including full
  1 MiB requests, upper C-Bus mirrors, WUP and source end flags. Both pre-fix zero
  and narrow-count negative controls fail. Direct-register limits unchanged.
- All ten regression scripts and three object compilations pass. Simultaneous
  DMA, held triggers, unusual alignments/increments and runtime remain open.

### Two-channel DMA arbitration — implemented and tested

- Suspend the old lower-priority channel when promoting a new higher-priority
  owner; restore halt callbacks on promotion/resumption using the existing policy.
- ST-097 priority / ST-210 two-channel restrictions checked with Ymir/Mednafen.
  64 direct/indirect, sound/non-sound, arrival-order scenarios pass alongside 54
  indirect chains. Pre-fix ticks fail the priority assertion.
- Exact cycle/bus halt policy, completion-boundary races, held triggers and DSP/
  three-channel overlap remain open. All ten scripts and three object builds pass.

### Held DMA external triggers — audited, existing implementation retained

- Expanded production-function tests to include the actual event filter. 924
  cases cover enabled/matching selection, one-slot holds, initial WAIT/MOVE/done,
  suspended level 0, register update policies and exactly one restart.
- ST-210 item 22 and Mednafen agree on held external events. Ymir's pinned path
  skips active channels; it was not used to override the primary specification.
- Five test-only mutation controls fail as intended. No production fix needed.
  All ten scripts and three object builds pass. DxGO MMIO, real event timing,
  reset/save-load with pending work and continuous event streams remain open.

### A-Bus refresh register — corrected reset and defined-bit storage

- AREF resets to 0x10 per ST-210 item 33, superseding ST-097 figure 3.30's zero.
  Writes retain bits 4:0, corroborated by MiSTer/Mednafen masks. Both reference
  reset values are still zero; Ymir ignores AREF, so the primary erratum governs.
- New ASan/UBSan tests pass 32 dirty resets, 32,768 refresh writes, 288 ASR writes
  and 24,576 static wait classifications. Both pre-fix controls fail as expected.
- Register-state correction only: AREF is not yet used for dynamic refresh
  timing. ASR behavior unchanged; physical bus/CPU reset wiring and save/load
  remain open. All eleven scripts and three object compilations pass.

### A-Bus interrupt mask — corrected polarity and added delivery tests

- IMS15 is a mask, not an enable: set blocks, clear permits. ST-097 §3.5 and
  Mednafen agree; pinned Ymir differs. Reset/ack mask 0xbfff now blocks external
  sources as intended. Existing AIACK and internal arbitration policies unchanged.
- 1,920 arbitration cases, 16 acknowledgement sequences and 512 masked register
  writes pass with ASan/UBSan. The pre-fix arbiter fails its IRQ-level assertion.
- All twelve scripts and three object compilations pass. Physical bus handshake,
  multi-source external edge cases and SH-2/CD/game runtime remain open.

### DMA programmed address registers — corrected 27-bit masks

- DxR/DxW writes no longer retain SH-2 cache-alias bit 29. ST-097 §3.2 and
  Ymir/Mednafen/MiSTer agree; bits 26:0 and direct count widths are preserved.
- Actual register lambdas pass 15,360 address and 7,680 count readback cases,
  with independent failing pre-fix source/destination controls.
- All thirteen scripts and three object compilations pass. MMIO routing, DxGO,
  address-update overflow and real CPU/cache/game execution remain open.

### DMA control registers — audited, existing implementation retained

- Extracted DxAD, DxEN/DxGO and mode/update/factor lambdas into the register test.
  13,824 scenarios pass, including partial-write isolation and software-start gating.
- ST-097 field definitions agree with Ymir/Mednafen. Four test-only gate/dispatch
  mutations fail as intended; no production change needed.
- All thirteen scripts and three objects pass. Start endpoints are recorders;
  complete MMIO-to-transfer integration and actual runtime remain open.

### Wider driver/DCC build validation — implemented

- Normal validation now compiles six objects, including sat_console, stv and DCC.
  Uses MAME's layout compiler for temporary ST-V headers and the shared include path.
- Fixed DCC/ST-V including device headers before emu.h. Pre-fix files reproduce
  include-order errors even with the correct layout/shared dependencies supplied.
- All thirteen scripts/six objects pass. No emulation behavior change; full
  dependency linking, configuration validation and runtime remain pending.

### CD component build validation — implemented

- Added CD HLE and the CD block wrapper to routine object checks (eight total).
  Fixed CD HLE including its device header before emu.h; the original file fails
  on MAME's explicit include guard and incomplete device types.
- All thirteen scripts/eight objects pass. No CD behavior changed; disc/BIOS/game
  runtime, full linking and remaining transitive dependencies are still untested.

### Game-blocker implementation effort — started

- Broader goal and prioritized remaining work are in `regtests/saturn/game_blockers.md`.
  No complete inventory or claim that all remaining game blockers are fixed.
- Implemented formerly unmapped DSTP forced stop: cancels three CPU DMA channels,
  held restarts and transfer scheduling without fabricated completion interrupts.
- 2,321 stop cases pass, including cancellation/restart and two-channel overlap.
  No-op control fails; all thirteen scripts/eight object compilations pass.
- Runtime build still lacks pkg-config/SDL development dependencies. Full linking,
  BIOS/game execution and hardware stop timing remain pending.

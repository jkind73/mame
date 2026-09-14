# VDP1 completion audit — 2026-09-14

## Interruptible line/polyline execution — 2026-09-14

Line and polyline commands now enqueue up to four segments and execute in at most
16-dot timer slices. Completed segments share the remaining slice budget. The last
short slice uses its actual dot count instead of adding a full 16 clocks. The next
command/END fetch is blocked until queued pixels finish; COPR stays on the active
command. ENDR discards the unfinished cursor and cancels scheduling without an IRQ;
PTMR restart and automatic field restart also discard old work. Reset now restores
the defined bank roles (drawing 0, display 1), rebuilding views without clearing
framebuffer RAM; the old initialization had reversed these roles.

Coordinates, error accumulator, dot index, segment colors, clip bounds and fetched
command fields are saved. Pixel dispatch is reconstructed for each slice, so it is
not a saved host pointer. Gouraud uses the original dot index after resumption;
half-transparent pixels are not replayed. CPU framebuffer writes between slices
are visible to subsequent blends. A state load resumes emulation state; ENDR itself
does not support hardware continuation.

Validation adds **748 cases**: sliced versus synchronous images across octants,
line/polyline commands, mesh, color operations and packed storage; every ENDR slice
phase; short-slice/END ordering; CPU framebuffer writes; PTMR/automatic restart;
and state copies inside segments and between edges, including a pending ENDR.
Unlimited-quantum, lost-cursor and wrong-reset-bank mutations fail assertions. All 18 scripts/nine
objects pass. No real MAME save/load or linked BIOS/game test is claimed.

This is a nominal one-dot-per-clock model with batched visibility, not exact bus
arbitration. Gouraud/setup/VRAM wait costs remain unqualified. **Normal/scaled/
distorted sprites and polygons remain atomic** and still need resumable execution.
The existing native pixel model is reused rather than replaying completed work or
pre-rendering framebuffer writes.


## Bounded VBlank erase — 2026-09-14

VBlank erase now captures the displayed bank, word layout, latched bounds/data,
and Sega's per-field erase capacity at blank entry. It commits only the permitted
prefix before the next bank exchange; excess pixels stay untouched. Rotation and
HDTV automatic/manual erase now queue for blanking instead of clearing a whole
bank immediately. Persistent VBE still repeats. Pending/in-flight state is saved;
machine/system reset cancels it, while stopping command drawing does not.

The capacity reproduces all 12 entries of ST-013 Table 4.5, including NTSC/PAL,
31 kHz and HDTV. High-resolution 8-bit mode erases two dots per word, not twice as
many words. Double-density interlace does not double the per-field capacity.

Validation adds **154 erase cases**, checking complete physical banks, partial-row
cutoffs, sparse windows, both banks and all five TVM formats, pending-state copy /
postload reconstruction, reset cancellation and blank-only scheduling. Three
independent mutations (unlimited budget, wrong bank, live instead of captured data)
fail assertions. All 18 scripts/nine objects pass. No real MAME save round trip or
linked game/BIOS run has been performed.

This remains a **coarse blank-period model**: writes commit at VBlank OUT. It does
not model individual erase bus slots, row setup overhead, or intermediate debugger
visibility. Active-display erase, interruptible command rasterization, pixel/VRAM
arbitration and hardware pre-clipping remain unfinished. See `official_specs.md`
for primary/reference evidence and differences.


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
scaled/distorted texture traversal or pixel timing; rotation/interlace were added in the later pass above.

Tests pass: 92,420 color/shading cases, 2,689 normal-texture/boundary cases,
32,816 command/lifecycle cases, 532 framebuffer cases and 24,500 clipping cases.
Four independent render mutations (MON source replacement, dropped odd carry,
fixed Gouraud coordinate, disabled second-END termination) fail their assertions.
All 18 scripts/nine objects pass. Shader tests do not establish polygon edge or
interpolation precision on silicon; callbacks use recording timer/CPU endpoints.
Full chip completion and BIOS/game/runtime/save-manager proof are not claimed.


**Status: in progress, not a complete VDP1 implementation.** The command engine now yields between commands; primitive rasterization
is still synchronous, and pixel/bus timing is not complete. No BIOS/game or hardware trace has been run here.

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

## Earlier implemented corrections

- Recognize CMDCTRL.END independently of the other control bits.
- Wrap sequential command fetch at the 512 KiB VRAM boundary.
- Generate SCU draw-end at the existing completion callback, alongside CEF, not
  unconditionally eight scanlines after VBlank. A host iteration-limit exit or
  unsupported command is not reported as a fetched END. Starting another list
  cancels the old outstanding completion estimate.
- Fix the upper two data lanes of CPU framebuffer writes in 8-bit modes. Preserve
  masked-off bytes and keep accesses on the selected drawing bank.
- Implement outside-user-clipping in all five pixel writers, keeping system
  clipping enabled. Inside includes the rectangle boundary; outside excludes it.
  Reject negative coordinates before indexing framebuffer line pointers. Outside
  mode rasterizes against the system rectangle, not the excluded user rectangle.

These remove a title-specific periodic IRQ workaround rather than adding one.
They can expose software that depended on the old fabricated completion; runtime
regression coverage is required before claiming improved game compatibility.

## Evidence

Primary: [Sega ST-013-R3-061694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf).
The PDF was downloaded/extracted outside Git, with 178 pages.

- §3.1 printed p.19 / PDF p.34: command fetch wraps after 07FFFFH.
- Printed p.20 / PDF p.35: CPU accesses the drawing framebuffer; byte access is
  allowed in 8-bit display, prohibited in 16-bit display. The lane repair follows
  the existing big-endian CPU register interface; no prohibited-access behavior
  is invented.
- §4.6 printed p.52 / PDF p.67: END fetch sets CEF and produces an interrupt;
  unreachable/missing END leaves CEF clear. This does not establish our delay.
- §7.10 printed p.132 / PDF p.147: END is bit15; the remaining command is ignored.
- §6.3 and §7.1/7.2: system clipping always applies, with inclusive rectangle
  boundaries; user clipping can select inside or outside. Technical Bulletin 15
  corrects swapped Clip/Cmod prose in an earlier manual edition. This edition's
  §6.3 also has contradictory Cmod boundary prose; §7.2 explicitly treats points
  on the line as inside, consistent with the diagram and reference renderer.

Cross-check: [Ymir VDP](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/vdp.cpp)
uses `control.end`, masks the next address to 0x7ffff and emits draw-end in
`VDP1EndFrame`. Its [software renderer](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp)
checks system clipping and complements the inclusive user test for outside mode.
Reference agreement is not hardware timing proof, and no source was imported.

## Executed coverage

`python regtests/saturn/test_vdp1.py` extracts production bodies and runs ASan/UBSan:

- 32,775 command/completion cases: every END control combination, a looping list
  replacing pending completion, CALL/RETURN at the final VRAM slot, sequential
  wrap, and dispatcher clip-rectangle selection.
- 288 CPU framebuffer cases: both banks, normal and 8-bit modes, four payloads,
  all legal byte-lane combinations (only word accesses tested in 16-bit mode),
  readback and preservation of the other bank.
- 24,500 actual pixel-writer cases: fast and generic variants, both clip bits,
  inside/outside/boundary/system rejection and negative coordinates.
- `--baseline commands`, `--baseline framebuffer`, and `--baseline clipping`
  substitute the pre-fix bodies and fail independently.

Rasterizers, time conversion, and SCU IRQ delivery are recording endpoints in
this harness. Generic color calculation is not tested here. No claim follows
about full rendering, actual IRQ latency or MAME save-manager restoration.
The full validator passes **18 scripts and nine object compilations**.

## Remaining implementation and acceptance gates

| Area | Current gap | Required implementation/verification |
|---|---|---|
| Command scheduling / ENDR | Timer-driven commands and saved return/fetch state now implemented; ENDR schedules a 30-clock stop; line/polyline raster work now yields within commands. | Extend saved pixel cursors to sprites/polygons and qualify pipeline termination; real save/load during primitives. |
| Timing / transfer-over | Command fetches use 16 cycles; lines/polylines have nominal pixel slices. Other primitive and bus costs remain absent. | Model fetch/pixel/VRAM arbitration and elapsed drawing across frames; measure against primary constraints and traces, not title delays. |
| PTMR / FBCR / EDSR / pointers | PTMR restarts, live COPR, bank-change LOPR and read-only writes are implemented. BEF now latches on bank change. Field-start changes, deferred register latches and bounded blank-only erase are implemented; sub-scanline timing and active-display erase remain incomplete. | Resolve latch points and reset behavior from manuals/supplements; test manual erase/change, automatic draw, busy writes and transfer-over. Do not equate each VBlank with a framebuffer change. |
| Command control | Valid eight jump controls, persistent fetch state and scheduler-yielding loops are implemented. Prohibited/undocumented commands still use fallback behavior. | Hardware investigation of illegal opcodes/aliases and prohibited flow; do not invent a primary-defined result for them. |
| Framebuffer formats | Packed 8-bit rendering, erase, CPU access and unrotated scanout now share storage; rotation-8 has its physical row stride. | Rotation, DIE/DIL and EOS are implemented; mismatched formats and hardware timing qualification remain. |
| Rasterization | Native integer line/quad and scaled texture walkers are implemented and image-tested. | Hardware pre-clipping, interpolation precision and silicon-image qualification; resumable pixel execution. |
| Texture / color | Normal-sprite second-END termination, destination MON and Gouraud/color combinations are implemented and tested. | Scaled/distorted END and HSS/EOS are implemented above; pre-clipping and hardware interpolation/rounding qualification remain. |
| Save/reset | Command fetch/return/activity state saved; postload preserves restored bank/geometry and reset cancels pending execution. Physical banks, field caches and pending VBlank erase are saved; line/polyline cursors and fetched command fields are saved; other intra-primitive state remains future work. | Real MAME round trips during drawing/erase, before END, after ENDR and across framebuffer changes; verify reconstructed pointers and no duplicate IRQs. |
| Runtime | No linked executable in this sandbox. | Install documented SDL/pkg-config dependencies, link and `-validate`, then BIOS and legally available Saturn/ST-V smoke/pixel comparisons (including prior workaround titles). |

Do not mark this table complete from standalone tests or an absence of TODOs.

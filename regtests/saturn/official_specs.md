# Sega SDK hardware-document audit

## P2 rotation mosaic integration — 2026-09-15

Implemented horizontal-only RBG0/RBG1 mosaic in the rotation source sampler,
including unit transforms (the ordinary shortcut is disabled for mosaic).
Blocks are anchored at screen X=0, including partial clips. High-resolution
rotation dots use doubled physical width; vertical size does not quantize rotation
rows. Parameter-window/coefficient selection and coefficient line-color data use
the block anchor. Output clipping/windows and destination blending remain per
output dot: this does not copy a previously blended framebuffer pixel. Coefficient
reads are memoized per pass, bounded by source blocks rather than repeated output
dots, with no persistent stale-cache state.

Primary: ST-058 printed pp.117–119, especially horizontal-only RBG0/RBG1 processing
and N0MZE sharing. Pinned Ymir 6d779960 rotation sampling corroborates source-layer
replication and high-resolution doubling. Ymir also copies the anchor's window
result; this renderer retains per-output window evaluation. That ordering difference
and physical interlace behavior require hardware qualification, not a claim that
the two renderers are identical.

Validation: **5,760** dedicated mosaic images (all 16 widths, RBG0/RBG1, parameter
modes, coefficient paths, opaque/ratio/additive, coverage, high resolution,
interlace, windows, split clips and read bounds). The coefficient line-color suite
now runs **34,560** images including mosaic. Removing mosaic sampling compiles and
assertion-fails. **34 scripts / eleven production objects pass** using
`validate_build.py`; log `/home/user/.cache/saturn/p2-mosaic-validation.log`.
No linked-game, actual save-manager or hardware timing acceptance is inferred.

The restored checkout was reconciled with pushed `8b070d34` after verifying its
local source/test versions against Git history. Earlier source/text copies are
preserved in `/home/user/mame-recovery-20260915`; user captures/logs were retained.

**P2 still has implementation gaps:** shared special-function metadata and general/
extended composition, raster preservation and pattern/character bus arbitration.
Linked game/save/load/performance qualification also remains open. Rotation mosaic
is no longer a missing implementation, but the ordering/timing qualifications above
remain explicit.

## P2 integrated sampling, rotation latches and coefficient handling — 2026-09-15

This supersedes the earlier combined-batch status at `5089d2e4`. **P2 remains
partial**, specifically where it depends on missing shared special-function
composition, raster/fetch arbitration and linked qualification. The fractional
character sampler, combined scroll modes, RPRCTL latches and coefficient line-color
interaction are now implemented, not still listed as missing.

### Implemented together

- **S01/S02:** one fixed-point point sampler handles tile/bitmap ordinary zoom,
  fractional scroll, all H/V-line/line-zoom/vertical-cell combinations, packed
  intervals, screen-left source-cell anchoring, dual-layer table interleaving and
  physical wrapping. Mosaic samples the upper-left output block and suppresses
  vertical cell scroll. No nested column-by-line redraw; per-cell table reads and
  repeated source-dot lookups are memoized. Simple unmodified layers retain their
  existing fast paths. A shared pattern/dot decoder also serves OVPNRA/B pixels.
- **R02:** defined modulo-32-bit coordinate arithmetic replaces signed-overflow
  assumptions. Mode-3 viewpoint coefficients now use the documented .8 long/.2
  short formats, rather than treating them as .16/.10 scale coefficients.
- **R03:** first enabled scanline loads A/B starts; later reads consume one-shot
  RPRCTL requests or accumulate fresh table deltas. Normalized per-row snapshots
  preserve earlier parameter reads through later rendering; paired-row handling
  retains the existing interlace convention. Both resets invalidate history;
  every snapshot field and accumulator is registered for save states. Row dispatch
  reuses the untransformed source cache rather than rebuilding it for every row.
- **R03 line color:** line-table addressing, long-coefficient low-seven-bit palette
  substitution, KTE/KLCE/size gating, RPMD 0/1/2/3 and RBG1 A/B selection, inserted
  second-image ratio/additive calculation and CCRLB selection under CCRTMD.
  Normal scroll also uses this insertion. This does **not** replace the existing
  compositor with a priority-aware top/second/third-image pipeline.
- **R02/R04 resources:** effective RAMCTL bank designations and partition bits gate
  per-dot coefficients; without a dedicated bank, VRAM coefficients are per-line.
  CRAM retains upper-half addressing; VRAM fetches wrap at physical size. Failed
  designated-bank fetches use Ymir's transparent fallback (both short halves and
  long MSB). Sega specifies failed fetches, not their resulting color: that fallback
  is not claimed as measured bus-latch behavior or full arbitration.

### Primary references and cross-checks

Pinned ST-058 pp.69–73/115–117/124–138 cover patterns, screen-over, mosaic and
fractional/combined scroll. Pages 150–158 cover bank designations and scanline
parameter loads/one-shot requests. Pages 161–168 cover coefficient selection,
mode-3 formats, per-dot resources and coefficient line color. Pages 172/231/243–244
cover line-table addressing, second-image insertion and ratios.

Pinned Ymir `6d779960127ced72087a418c1daefc637d0aaa80` corroborates scanline
accumulation, coefficient conversion, bank permissions and line-color selection.
Pinned MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78` corroborates shared pattern
addressing and wrapping Q16 RotCoord_t/MultRC. Ymir uses a Q10 coordinate pipeline;
this is not evidence that their intermediate precision is identical. MiSTer's
reload scheduling is not treated as independent confirmation of all RPRCTL rules.

### Validation

- **30,720** actual normal dispatch/sampler images: tile/bitmap formats, fractional
  phases, all scroll combinations, mosaic, table interleaving/wrapping, windows,
  line-color ratio/additive insertion, split clips and bounded table reads.
- **512** scanline latch sequences: all six request bits, varied reload lines,
  fresh signed deltas, step 1/2, auto-clear, disabled/re-enabled state, snapshot
  selection and copied-state replay. Copy replay is not save-manager acceptance.
- **1,536** signed-limit coordinate images against a separate wide-integer modular
  oracle; **11,520** coefficient line-color/resource/insertion images.
- **40,960** physical coefficient-bank/partition/CRAM fetch cases; existing **9,216**
  CRAM lane/address/palette cases continue to pass.
- Existing **2,560** pattern decodes, **2,880** screen-over-pattern images, **144**
  selection images, **648** signed coefficient boundaries, **360** coverage images,
  **9,216** rotation images and **8,448** dispatch cases pass. New latched-row
  dispatch assertions verify cache reuse across rows and subsequent partial clips.
- Fraction, cell, mosaic, two-word character, request-clear/reload/delta, line-color,
  mode-3 viewpoint and per-dot-bank mutations assertion-fail; signed-overflow
  mutation fails UBSan. The original periodic pixel seed concealed the two-word
  mutation; a high-address-dependent seed fixes that test weakness.
- **34 regression scripts and eleven production object compilations pass** via
  `python regtests/saturn/validate_build.py`. Full log remains in the external cache
  at `/home/user/.cache/saturn/p2-full-validation.log`. No linked executable/game,
  hardware timing, measured frame-time or actual save-manager acceptance is claimed.

### Remaining P2 dependencies (not silently waived)

| Parent | Remaining work/qualification |
|---|---|
| S01/S02 | Linked image/timing/performance qualification and real interlace fetch behavior; implemented combination routing is no longer excluded. |
| R01 | Shared SFPRMD/SFCCMD/SFSEL/SFCODE metadata/composition (C01/C04), including screen-over patterns; linked qualification. |
| R02 | Hardware intermediate-precision comparison and bus/fetch-history behavior beyond explicit arithmetic and bank-permission tests. |
| R03 | Priority-aware general/extended line-color composition (C01/C05), memory-write raster preservation (T01), actual save-manager and interlace qualification. |
| R04 | Pattern/character bank scheduling and arbitration, shared special effects, mosaic ordering/timing qualification, linked cache/save/load/performance qualification. |


## S02: standalone vertical cell-scroll dispatch — 2026-09-15

Removed the accidental horizontal-line-scroll prerequisite from the existing
vertical cell-scroll branch. With vertical cell scroll alone enabled, each clipped
column now goes directly to the basic tile or bitmap renderer; when horizontal
line scroll is also enabled, it retains the interval scheduler. The existing
exclusions for vertical line scroll and line zoom remain, rather than enabling
unqualified nested combinations. Original scroll X/Y are restored after the column
pass, preventing the final column or downstream normalization from leaking into
later partial updates.

Primary ST-058 printed p.134 describes vertical cell scroll as its own function;
SCRCTL's independent VCSC/LSCX enable bits do not require horizontal line scroll.
Pinned Ymir 6d779960 `vdp_renderer_sw.cpp` independently enables vertical cell scroll
without requiring horizontal line scroll. Its per-source-cell stepping and mosaic
priority are comparison points, not behavior implemented by this dispatch fix.

Extended `test_cell_scroll.py` to **85,248 configurations**: standalone and combined
horizontal-line-scroll paths, direct tile/bitmap dispatch, both table interleaving
offsets, VRAM sizes/wrapping, negative offsets, partial/empty clips, column call bounds
and restoration despite downstream coordinate normalization. Prior a562a96f compiles
and assertion-fails; independent restored-prerequisite and removed-restoration
mutations compile and fail the appropriate assertions.

All **29 regression scripts / eleven production object builds pass**. This fixture
records dispatch and offsets, not final hardware pixels. The existing screen-X
8-dot column convention is preserved, not newly certified: source-coordinate cell
boundaries, fractional scrolling, zoom/vertical-line combinations, mosaic priority,
and linked runtime/save/performance qualification keep S02 open.


## S02: line-scroll intervals and partial rendering — 2026-09-15

Reworked line-scroll scheduling around screen-origin interval boundaries. Packed
H/V/zoom entries are indexed by `floor(screen_y / interval)`, not by the partial
clip's first scanline. Vertical interpolation is anchored at the entry's first
line; a clip starting inside an interval retains the previously selected entry.
Every downstream draw is bounded to the requested clip, including short final
intervals. Equivalent adjacent renderer states are still batched; no look-ahead
fetch is made beyond the final required entry. Original scroll X/Y and horizontal
increment are restored after rendering so later clips/columns do not inherit the
last table entry or downstream coordinate normalization.

Line-zoom values now decode as unsigned 3.8 increments. In particular, 4.0 is no
longer sign-extended into a negative increment. This does not invent clamping for
software exceeding the configured ZMCTL reduction range.

Primary: ST-058 printed pp.131–133 describes compact H/V/zoom table ordering and
holding entries between interval boundaries; p.137 specifies the interval modes;
pp.132/138 specify horizontal increments matching the unsigned coordinate format.
Pinned Ymir 6d779960 `vdp_renderer_sw.cpp` `VDP2UpdateLineScreenScroll` corroborates
interval-controlled reads, packed fields and unsigned zoom extraction. Pinned
MiSTer a95b0850 `VDP2.sv` lines 1298–1305 advances the table offset on interval
boundaries using `NxLSTblSize`. Their interlace handling is not claimed equivalent
to this scheduler; field-specific fetch timing remains a separate audit.

`test_vdp2_linescroll.py` executes the production scheduler with recording basic
renderers and a separate per-line table oracle. **4,200 scenarios** cover all seven
active-function combinations, intervals 1/2/4/8/16, nonzero and unaligned clip
origins, short clips, wrapped VRAM tables, negative scroll values, constant/varying
entries, tile/bitmap dispatch, integer vertical increments, sequential single-line
partial passes, state restoration and batching bounds. Previous d4343068 compiles
and assertion-fails. Independent address, clip, signed-zoom and restoration
mutations also compile and fail their intended assertions.

All **29 scripts / eleven production object builds pass**. S02 remains open for
fractional-coordinate resampling, broader simultaneous vertical-cell-scroll
combinations, actual interlace fetch timing, and linked gameplay/save/performance.
These tests record renderer parameters, not final hardware pixels or bus arbitration.


## R01: screen-over-pattern pixels implemented — 2026-09-15

Rotation screen-over mode 1 now repeats the character selected by OVPNRA/OVPNRB
outside the full screen extent, instead of discarding those pixels. The selected
name is decoded as one word regardless of ordinary map pattern-name size, using
PNCR supplement/flip controls, 8×8 or 16×16 characters, all five legal color formats,
CRAO offsets, raw-dot transparency and VRAM address wrapping. Bitmap mode is not
assigned an invented pattern behavior; its existing outside clipping is retained.

The character is decoded into at most 256 unblended pixels per output pass. This
keeps per-output-dot lookup cheap and avoids new persistent cache invalidation or
save-state fields: register, palette and character-data changes are read anew.
Both coefficient paths use the same pattern lookup, ordinary/parameter windows,
coverage test and final color-offset/calculation stages. The unity-transform shortcut
now requires screen-over repeat mode; other modes cannot bypass their boundaries.

Primary: ST-058 printed pp.115–116, one-word bit layouts pp.69–74, and palette offset
rules p.215. Pinned MiSTer `VDP2.sv` lines 2872–2873 supplies OVPNR through `PNData`;
`VDP2_pkg.sv` `PNData` and `RxCHAddr` corroborate supplement/flip/cell addressing.
Pinned Ymir `VDP2DrawRotationCharBG` has a RepeatChar branch calling its one-word
extractor, corroborating the mode, but its low-three-bit dot coordinates are not
used as an oracle for 16×16 cell selection. Sega's character-size rule and MiSTer's
four-cell addressing are the basis for that case.

Validation:
- **2,560 decoding configurations**, each checked at 324 positive/negative coordinates
  against a separate bit-wiring/bitstream oracle; color formats, supplement modes,
  flips, sizes, transparency, both VRAM sizes, palette offsets and address wrapping.
- **2,880 screen-over images** through the production compositor: A/B, both ordinary
  pattern-name sizes, no/line/dot coefficients, ordinary and parameter windows,
  opaque/ratio/additive output, source boundaries, and whole/split clips.
- **8,448 dispatch configurations**, including each selected screen-over mode and
  nonselected-parameter controls. Existing 9,216 rotation images and 360 coverage
  images still pass.
- Separate missing-pattern, wrong-A/B-name, missing-flip and shortcut-bypass mutations
  compile and assertion-fail. Full **28 scripts / eleven object builds pass**.

Palette lookup, coefficient fetch and window inputs remain controlled stand-ins;
RGB555 conversion retains MAME's current expansion rather than claiming DAC accuracy.
R01's base pixel path is implemented, but shared special-priority/calculation metadata,
parameter-switching qualification, linked gameplay, save/load and performance remain
open. No D-Xhird gameplay result or hardware certification is claimed.


## A03/C01: color-depth screen restrictions — 2026-09-15

Applied the remaining normal-screen color-count exclusions from ST-058 printed
p.61: 2048-color NBG0 suppresses NBG2; 2048-color NBG1 suppresses NBG3; RGB888
NBG0 suppresses NBG1 and NBG3 as well as the already-suppressed NBG2. Existing
RGB555 exclusions remain. Removed the unreachable N1CHCN==4 check (a two-bit
field). These are configured resource exclusions, not tests of the other layer's
BGON flag, and do not introduce handling for prohibited color formats.

Pinned Ymir `vdp_state.hpp` lines 775–793 and MiSTer `VDP2.sv` lines 3199–3201
independently match the primary color-count rules. Unlike the ZMCTL access-count
comparison above, Ymir's color-depth gates are active code.

Extended `test_vdp2_reduction.py` with actual NBG1 setup and **4,608 additional
color-depth/reduction scenarios**: every legal normal-screen color count paired
with permitted reduction ranges, all BGON combinations, cycle presence/absence,
NBG1 tile/bitmap setup, and recovery after clearing the restrictions. Expected
screen masks come from a separate p.61 table. NBG1 video mode queries and final
rendering are stand-ins; no full tile image or arbitration claim is made.
Baseline f941e312 compiles and assertion-fails. Three independent mutations,
one per affected layer's color gate, compile and fail their corresponding assertions.

The prior 3,456 reduction scenarios and full **28 scripts / eleven production
object builds pass**. Full A03 register qualification, C01 composition metadata,
S01 coordinate behavior, and linked runtime/save/performance remain open.


## S01: ZMCTL paired-screen restrictions — 2026-09-15

NBG0 quarter-reduction enable now suppresses NBG2; half-reduction enable does
so with 256-color NBG0. NBG1 has the corresponding effect on NBG3. This is a
configured resource restriction, independent of the current coordinate increment
or the paired source screen's BGON bit. No undocumented increment clamping was added.

Primary: ST-058 printed pp.129–130, Table 5.2 (quarter enable dominates half).
Pinned MiSTer `VDP2.sv` lines 3137–3138 and 3200–3201 corroborate these gates.
Pinned Ymir `WriteZMCTL` masks 0x0303 and dirties access patterns, but its related
access-count multipliers in `vdp_state.hpp` are commented out with a compatibility
FIXME; it is not an independent passing oracle for this restriction.

`test_vdp2_reduction.py` executes production NBG2/NBG3 setup, actual register
macros, and cycle-pattern presence checking. **3,456 scenarios** cover the legal
16/256-color reduction settings, both pairs, all normal BGON combinations, cycle
presence/absence, three increments, and clearing ZMCTL without reset. The final
tile renderer is a recording stand-in; prohibited 256-color quarter reduction is
not assigned a silicon expectation. Baseline 4ff73852 compiles and assertion-fails.
**28 scripts / eleven production object builds pass**, not linked/runtime/save
qualification. S01 remains open for fractional scroll/zoom and broader combinations.


## A04/C01: preserve opaque black through rotation caching — 2026-09-15

Rotation caches now distinguish **coverage from RGB intensity**. Cache construction
clears with `rgb_t::transparent()` instead of opaque black. Actual source writers
already produce alpha=255 on every drawn RGB/palette dot (including RGB black);
transparent source dots leave the cache untouched. Both coefficient paths now test
that coverage byte rather than rejecting every pixel with RGB=0. Transparency-code
disable is handled by the source writer, not reapplied against decoded RGB.
This byte is host cache metadata, not a new Saturn alpha channel or a replacement
for the still-missing source-layer/priority/second-image metadata.

Primary ST-058 printed pp.57–58 defines transparency from palette dot code zero
or the RGB source MSB, and permits disabling that test. A nonzero palette index
resolving to black and RGB 8000/80000000 are therefore not transparent. Pinned
MiSTer `MakeDotData`/R0DOT.TP and Ymir's background dot/window processing likewise
keep transparency separate from the final RGB value. MAME `palette.h` and palette
initialization confirm that ordinary black pens and three-channel RGB constructors
are opaque, while `rgb_t::transparent()` has zero coverage.

The rotation fixture now uses the **actual MAME rgb_t** definition. Added **360
bitmap-to-rotation coverage images** execute the five production bitmap writers
into a transparent source cache and then the production rotation compositor:
zero/black/red dots, RGB transparent codes with nonzero payload, transparency on/off,
A/B, coefficient paths, forward/reversed traversal and opaque/ratio/additive output.
Palette lookup and window/coefficient inputs remain controlled stand-ins; this is
not exhaustive character-tile rendering or full device integration.
The 9,216 existing rotation images still pass. Cache setup also uses actual rgb_t
and verifies transparent clearing. Restoring RGB-zero rejection or opaque cache
clearing causes separate assertion failures.

All **27 regression scripts and eleven production object builds pass**. Full
source-layer-aware composition, special effects, sprite windows, precision and real
linked runtime/save/performance qualification remain open. No particular game's
black-pixel symptom or title/logo placement is claimed fixed without runtime evidence.


## A04/C03/C05: rotation shortcut and source-cache composition — 2026-09-15

The no-transform rotation shortcut no longer collapses window behavior into one
rectangle and then disables window inputs. It preserves the original partial clip
and forwards ordinary per-pixel window configuration to the background renderer.

The shortcut is now limited to its actual assumptions: identity geometry, zero
start-coordinate offsets, unit output stepping and no enabled coefficient table
for the selected A/B parameter. Nonzero Xst/Yst, double-density output and horizontal
rescaling use the general rotation path. A coefficient table belonging only to the
other parameter does not unnecessarily disable the shortcut. RPMD 2/3 were already
excluded by the predicate; the obsolete mode-3 fast-path block was removed, not
counted as newly implemented parameter-window support.

Rotation source-cache construction clears prior alpha/additive flags and stores
unblended source pixels. The wrapper no longer forces alpha after rendering that
source; the final rotation compositor selects ratio/additive calculation using
CCMD. This fixes the wrapper-level interference with additive output that the
isolated rotation compositor fixture could not detect.

Evidence: ST-058 chapter 6 defines Xst/Yst and coefficient-controlled conversion;
chapter 8 defines the window combinations; printed p.241 defines CCMD calculation.
Pinned Ymir's parameter/line-output and window preparation, and MiSTer's independent
coefficient/window controls, are comparison points. The tighter shortcut conditions
are an equivalence safeguard, not a new silicon timing claim.

`test_vdp2_rotation_dispatch.py` executes actual dispatch, optimization predicate
and cache setup in **5,376 cases**, including A/B, RPMD 0–3, selected/unselected
coefficient enables, starts, output stepping, 32 window configurations, calculation
modes, stale blend flags and cache reuse. Downstream rendering is recorded rather
than treated as a complete pixel implementation. Previous 69995fab code compiles
and fails preserved-window assertions; coefficient-bypass and forced-alpha mutations
fail independently. Existing bitmap and rotation pixel suites also pass.

All **27 scripts and eleven production object builds pass**. Broader window/rotation
features, precision, sprite windows, second-image selection and real linked runtime/
save/performance qualification remain open. General-path use may increase rotation
cache work in affected modes and needs profiling with a linked executable.


## A04/C03: rotation partial clips and coefficient-path windows — 2026-09-15

`vdp2_copy_roz_bitmap` now advances its per-line source accumulators to the
partial clip's left edge instead of restarting at screen X=0. The advance uses
64-bit products and explicit 32-bit wrapping. Its per-dot coefficient path now
applies the ordinary rotation-screen and mode-3 parameter-window predicates,
matching the checks already present in the per-line path. No new window geometry
or screen-over-pattern implementation is implied.

Primary ST-058 chapter 6 defines rotation from TV-screen Hcnt/Vcnt coordinates;
chapter 8 defines screen and rotation-parameter windows. A host clip rectangle
does not redefine those coordinates or disable windows. Cross-checks: pinned Ymir
`VDP2CalcWindows` computes background and rotation-parameter masks independently
of coefficient granularity; pinned MiSTer `RxW_EN` evaluates the rotation-screen
window from output window hits. This corrects missing integration rather than
claiming newly measured silicon rounding rules.

New `test_vdp2_rotation_clip.py` executes the production rotation compositor:
**9,216 image cases** cover A/B, no/per-line/per-dot coefficient paths, all four
coefficient modes with controlled values, discarded coefficients, reversed and
fractional steps, ordinary and parameter windows, interlace/high-resolution
coordinates, opaque/ratio/additive output and split partial rectangles. Window
predicates and coefficient reads are recording stand-ins; source pixels and output
images are independently checked. Removing the clip advance fails split/full
comparison; bypassing per-dot windows fails the image oracle.

All **26 regression scripts and eleven production object builds pass**. Existing
per-line/per-dot high-resolution coordinate precision differences are preserved
and explicitly not hardware-qualified by the fixture. Complete coefficient-table
fetch/precision, sprite windows, screen-over-pattern, second-image composition,
real save/load and linked runtime acceptance remain open. A04/C03 are not closed.


## C05: sprite zero-ratio calculation and eligibility — 2026-09-15

Sprite palette composition no longer uses CCRT=0 as a disabled-calculation sentinel.
Ratio zero is the valid 31:1 top/second-image blend. Per-dot MSB eligibility is now
kept separately, so eligible additive pixels also calculate at ratio zero while
ineligible pixels still replace the destination. Other priority conditions and RGB
selection are preserved. This does not implement CCRTMD second-image ratio selection,
full underlying-layer eligibility, sprite windows or the remaining shadow behavior.

Primary: ST-058 §12.1 printed p.235 gives the 31:1 through 0:32 range; p.241 says
CCMD=1 ignores ratio registers; sprite condition rules are in §9.2. Pinned Ymir
sprite ratio attributes and final calculation, and MiSTer separate CCRT/CCENFST
inputs to ColorCalc, corroborate keeping eligibility separate from the ratio.

The sprite fixture now extracts the **actual production blend-level helper**, not
the earlier fixed-purpose stand-in. Existing ratio-16 expected images use the real
15:17 weight. Added **38,400 ratio/selector/eligibility images** cover every ratio,
eight palette selectors, all four conditions, three tested priorities, mixed/RGB
selection, MSB eligibility, disabled calculation and additive saturation. The
baf9b069 baseline compiles and fails the new oracle. The prior 3,036 scanout cases
also pass. Palette/window devices in this sprite fixture remain stand-ins; actual
palette/window integration is tested separately in the bitmap fixture.

All **25 regression scripts and eleven production object compilations pass**.
No linked runtime, physical hardware or real save-manager acceptance is claimed.
Parent C05 and the broader composition tasks remain open.


## A04/C05: bitmap additive calculation — 2026-09-15

The real bitmap fixture exposed a shared omission: all five bitmap routines used
ratio alpha calculation even when CCMD requested direct addition. They now select
saturating addition when calculation is enabled and CCMD=1. Disabled calculation
still replaces the pixel, and CCMD=0 retains the ratio path. No special-function,
second-image eligibility or high-resolution resource restriction is newly claimed.

Primary ST-058 printed p.241 defines CCMD=1 as “Add as is” and ignores ratio
registers. Pinned Ymir `Color888SatAddMasked` and MiSTer `ColorCalc(...CCMD)`
corroborate the operation; MAME's existing `add_blend_r32` is reused.
The bitmap suite now has **15,360 image cases** with real palette and windows,
including additive saturation. An additive-disabled mutation fails the image oracle.
All **25 scripts / eleven production objects pass**; no linked runtime qualification.

The register ledger also now cross-references MiSTer register write masks, preserving
conditional alternatives. These remain explicitly separate from the primary
hardware-mask/reset/latch audit; no broad masking change was applied to production.
A03/A04 and the full C05 composition task remain open.


## A04/A05: physical CRAM banks and integrated bitmap fixture — 2026-09-15

CRAM now retains physical mode-1 bank order in storage. Mode 2 maps the CPU high
word to bank 0 and low word to bank 1 at the same palette index. Reads, masked
writes and palette rebuilds use that mapping; changing modes does not move data.
CRKTE coefficient reads retain the physical upper-bank path required in mode 1.
Primary ST-058 §3.4/Figures 3.9–3.10 specifies the color layouts and writing color
data after mode selection. The exact cross-mode address permutation is supported
by pinned Ymir `MapCRAMAddress` and MiSTer `IO_PAL_A`/`IO_PAL_RD`/bank write enables,
not claimed as a fresh hardware measurement. Reserved CRMD=3 retains mode-2-style
fallback; prohibited byte accesses and DAC precision are not redefined.

`test_vdp2_palette.py` now checks 9,216 lane/address/palette cases, repeated mode
changes without memory mutation and upper-bank coefficient reads. The 77d4b989
layout baseline compiles and fails the read-address oracle.

`test_vdp2_bitmap.py` adds **7,680 image cases** executing the actual five bitmap
pixel routines, actual CRAM palette rebuild, both window coordinate functions,
line-window table fetches, keep/reject logic and window cache. Covers RGB/palette,
transparency, alpha, source wrapping/zoom, normal/high/exclusive window coordinates,
interlace table cadence and split odd partial clips. Window bypass and reversed
nibble mutations fail. Layer setup and devices remain stand-ins; this is not full
NBG tilemap/rotation dispatch, sprite windows, a special-effect oracle or physical
DAC qualification. The fixture preserves current MAME pal5bit expansion.

All **25 scripts and eleven production object builds pass**. A03's per-bit ledger,
A04 tilemap/complete layer dispatch, and A05 hardware precision qualification remain
open; do not mark their parent tasks finished. No linked runtime/save acceptance.


## A03–A05: CRAM broadcast and palette fixture — 2026-09-15

Mode-0 CRAM writes now merge into **both physical 1K-word halves**, rather than
writing one location and updating pens from another. Each masked word lane is
merged independently into each half; reads remain independent. A mode change
alone must not destroy differing unwritten data. Masked-out writes have no effect.

Primary: ST-058 §3.4, printed pp.43–46 (especially p.46), specifies simultaneous
writes to the two halves. Ymir `VDP2Memory::WriteCRAM` in `vdp_state.hpp` at
6d779960127ced72087a418c1daefc637d0aaa80 and MiSTer `IO_PAL0_WE`/`IO_PAL1_WE` at
a95b085038ace57fa621558d60a7adc7a3c53f78 also broadcast accesses addressed through
the upper half. The manual explicitly describes lower-half writes; upper-half
broadcast and independent reads are cross-implementation evidence, not a new
hardware measurement. No byte-write ignore rule is invented.

`test_vdp2_palette.py` extracts production CRAM reads/writes and palette rebuilds:
**9,216 address/lane/palette cases** plus mode-transition and zero-mask checks pass
under ASan/UBSan. The prior c43dded9 implementation compiles and fails the raw-memory
oracle. All **24 regression scripts and eleven production object builds pass**.
No linked runtime or real save/load acceptance is claimed.

[A03 register ledger](vdp2_registers.md) now inventories all halfwords through 0x11E
and the remaining backing-file range. Per-bit hardware masks/reset/latch verification
is still open. A04 has a real palette fixture, not yet a full-background/window
fixture. A05's mode-0 write defect is fixed; mode-2 physical layout across mode
changes, coefficient interactions and physical color-output precision remain open.
Current MAME `pal5bit` expansion is preserved; the manual's zero-filled low bits
require a separate pipeline audit. None of the parent A03–A05 tasks is marked done.


## Current workstream: VDP2 audit and progress tracker — 2026-09-15

See [VDP2 implementation report and checklist](vdp2_completion.md) for the current
source-audited feature matrix, test limits, stable task IDs, priorities and acceptance
gates. Baseline: `ad5ae529`. Normal/rotation rendering is substantial, but special
composition, sprite windows/shadows, line-color/mosaic integration, rotation edge
cases, scroll combinations and bus/raster timing remain incomplete. In particular,
a tested mosaic helper is not an enabled production mosaic feature.

This entry is documentation-only. The latest implementation validation remains
23 Saturn scripts and eleven object compilations, not a linked runtime certification.


## Active-display erase — 2026-09-15

Manual and one-cycle display erase now advance behind scanout, instead of clearing
at a field boundary. Each affected physical row is presented with
`screen_device::update_partial` before its framebuffer words are erased. Interlaced
output waits for both output rows. The captured bank/data/window and saved next-row
cursor prevent register writes or restoration from restarting an erased prefix.
Field end only retires the operation; it cannot erase unscanned/offscreen rows.

One-cycle mode now schedules erase on the newly displayed bank; the next swap makes
that already-erased bank drawing-owned. It no longer clears the newly selected draw
bank wholesale at swap. Normal/packed-8 display erase is limited vertically to active
rows and horizontally to active words plus four words (four normal or eight packed
dots), following ST-013-R3-061694 printed p.49. Blank-only TV modes retain the separate
progressive VBlank implementation.

Cross-checks: MiSTer VDP1 `FRAME_ERASE_EN`, `FB_ERASE_A` and `OUT_Y` at
`a95b085038ace57fa621558d60a7adc7a3c53f78` erase the display bank during active scanout.
Ymir `vdp.cpp` and `VDP1DoEraseFramebuffer` at
`6d779960127ced72087a418c1daefc637d0aaa80` also select the display bank, but their coarse
whole-operation erase clamps horizontal words to 400/428 rather than the primary's
active-width-plus-four limit. MiSTer's counter also is not an exact boundary oracle.
This change follows the primary bound; those implementation differences still need
hardware qualification, not a claim of three-source agreement on every edge.

Validation: **180 new active-display cases** cover bounds, packed payloads, both
banks, interlace cadence, presentation-before-write, partial-state restoration,
CPU edits behind the cursor, retirement without a final bulk clear, and one-cycle
ownership. The existing 24 manual-field presentation cases now run actual row ticks.
Mutations removing scanline progress, removing presentation, or removing the
horizontal bound all compile and fail assertions. **23 scripts and eleven production
object builds pass.** The screen is a recording stand-in in extracted tests; these
are not linked MAME visual tests or real save-manager round trips.

Remaining: within-raster CPU/readout/erase arbitration, precise latch/edge timing,
performance and real runtime/save-load qualification. The accepted HSS/ECD pixel
logic was not changed, but the broader timing change has no new game acceptance.
Separate title/logo geometry is still open. Full VDP1 completion is not claimed.


## Progressive VBlank erase — 2026-09-15

VBlank erase now advances at physical-raster boundaries instead of committing the
whole operation at VBlank OUT. A saved X/Y cursor and remaining word budget keep
CPU-visible progress, partial rows and resumed operations consistent. The bank,
format, payload, per-raster quota and output-row cadence are captured at entry;
later register writes cannot redirect the erase. ENDR remains independent;
reset/cancellation stops future writes without undoing the completed prefix.
A CPU edit behind the saved cursor is not erased again on resumption.

The existing VBlank edge convention can leave a few raster quotas at field end;
only that residual budget is flushed before bank exchange. This is **scanline-level
progress, not cycle-exact arbitration**. Active-display erase remains field-coarse.

Sources: ST-013-R3-061694 printed pp.49–50, Tables 4.4/4.5, supplies the unchanged
per-raster quota and total field capacity. MiSTer VDP1 at
`a95b085038ace57fa621558d60a7adc7a3c53f78`, `VBLANK_ERASE_EN`/`OUT_X`/`OUT_Y`,
corroborates progressive traversal during blanking. Ymir `vdp.cpp` at
`6d779960127ced72087a418c1daefc637d0aaa80` was cross-checked: it uses a **113 rather
than 200** horizontal penalty with an explicit TODO and title examples, and commits
erase at blank end. That discrepancy is not hardware proof; this change preserves
Sega's published capacity and introduces no game-specific adjustment.

Validation: **552 new production-helper slice/restore/cancellation/callback cases**,
including both banks, five framebuffer modes, partial rows, over-budget requests,
interlace cadence and exclusive display modes. Mutations disabling scanline progress
or bypassing the budget cap compile and fail image assertions. All **23 regression
scripts and eleven production object builds pass**. Saved-field registration is
checked, but state-copy tests do not certify real MAME save-manager round trips.
No new linked game acceptance or resolution of the separate title/logo issue is
claimed; previous user-accepted rendering fixes remain unchanged.


## Screen-coordinate VDP1 scanout — 2026-09-15

Implemented TVM=4 HDTV/31-kHz 2×2 dot replication and unified the VDP2 sprite
compositor around output-screen coordinates. Normal-16/high-resolution output
replication and high-resolution-8/normal-output decimation are now handled at
framebuffer sampling, before rotation or field selection, rather than by copying
already-composited output pixels. Odd partial clips and per-output-pixel windows,
alpha/additive blending and normal shadows therefore use the correct destination.
The accepted HSS/ECD rendering fix is unchanged; no title-position hack was added.

Evidence: ST-013-R3-061694 §1.2 (printed p.14), pp.36–37 defines HDTV replication
and legal framebuffer formats; pinned Ymir `VDP2DrawSpriteLayer` at
`6d779960127ced72087a418c1daefc637d0aaa80` corroborates horizontal readout shifts;
MiSTer VDP1 `VOUTO` at `a95b085038ace57fa621558d60a7adc7a3c53f78` independently
models packed-byte dot-clock phases. Mismatched-mode decimation is cross-emulator
behavior, not a claim that Sega specifies every prohibited combination.

Validation: **23 regression scripts and eleven production object compilations
passed**. New `test_sprite_scanout.py` extracts the actual compositor and readout
functions: **3,036 image cases** under ASan/UBSan cover framebuffer modes, resolution
mismatches, interlace, field caches, translated rotation, RGB/palette output,
windows, blending, shadows and odd clips. Palette/window evaluation and device
scheduling are stand-ins. `--old` compiles the pre-change implementation and fails
an odd interlaced clip image (not a compilation failure). Existing VDP2 MSB-shadow
handling in the alpha path remains a separate gap; these tests do not certify it.

Not full VDP1 completion: active-display erase remains field-coarse, VBlank erase
is budgeted but committed at field end, bus arbitration remains nominal, and real
MAME save/load and linked runtime qualification remain outstanding. SDL/pkg-config
build dependencies are unavailable in this sandbox; two Debian fetch attempts
failed. AB2 explosions/boot, Power Drift cars and OutRun flashing retain their
previous user acceptance. Separate logo/title placement is still unverified.


## User-verified results — 2026-09-15

The user confirms that **969cc3ae fixes After Burner II explosion transparency
and the Power Drift car rendering issue**. These are now runtime-accepted
results, not pending visual checks. After Burner II boot remains accepted with
the earlier SH DRC correction. This does not establish full gameplay or save/load
acceptance, nor resolution of the separately reported logo/title placement bugs.

The common fix preserves ECD-controlled END-pixel rejection during HSS reduction
while bypassing two-END row termination. No game-specific workaround was used.
The recorded validation remains 22 regression scripts and eleven object builds;
this acceptance update changes documentation only.


## Latest: captured HSS/LUT END-pixel defect corrected (3c31f363)

The live video capture locates opaque 8000 pixels in the explosion framebuffer.
LUT index F maps to that black value; the corresponding reduced commands use
PMOD=1808 (HSS=1, ECD=0). The renderer incorrectly forced ECD during reduction.
Keep ECD unchanged: bypass two-END row termination for HSS but reject individual
END pixels. Ymir and MiSTer agree on this distinction; the Sega p.86 HSS table
has conflicting wording, documented rather than presented as proof.

Corrected synchronous/queued scaled and native texture paths. Four synthetic
LUT marker/cutoff cases plus existing HSS/EOS/quad images pass; restoring the
old behavior fails a C++ pixel assertion. All 22 scripts and eleven objects
pass. Rebuild/game visual acceptance is pending; boot remains confirmed.
See `regtests/saturn/visual_followup_3c31f363.md` for exact capture evidence,
reference code and limitations. Logo/title displacement is still separate.


## Latest: explosion rectangles still present (d0166ac6)

User confirms the 94cc6b24 RGB correction did **not** resolve After Burner II's
explosion transparency. The new archive contains 670,624 scaled command records;
every one uses color mode 1 (4-bit lookup table), not RGB texture mode 5. That
rules out describing the preceding RGB fix as this symptom's solution. The boot
fix remains user-confirmed. No new emulation change is justified from these
records alone: texture/LUT contents and framebuffer words are not logged.

Added `regtests/saturn/video_capture.lua`: on F12, capture the visible image,
VDP1 texture/LUT/command RAM, both framebuffer banks, VDP2 RAM/CRAM/registers
and small VDP1 state together. No rebuild or verbose log is needed. Standalone
Lua mocks pass (schema, byte bounds, cap, collisions, missing-item failure);
live MAME capture delivery is not yet tested. Instructions and binary format:
`regtests/saturn/video_capture.md`. Geometry and explosion artifacts remain open.


## Current: boot confirmed; visual follow-up (d402162b)

The user confirms After Burner II boots with d68770ea. Startup is no longer an
open blocker. New screenshots show effect rectangles and displaced/clipped
artwork. Corrected VDP1 RGB transparency: ECD/HSS must not make MSB-clear 7FFF
opaque with SPD=0 (MiSTer/Ymir agree). 262,144 RGB gate cases pass; the old
behavior fails a normal-sprite image assertion. All 22 regression scripts and
eleven objects pass. Screenshot-level improvement needs a rebuilt game run.

Geometry remains unresolved, not fixed by an arbitrary anchor adjustment.
The verbose trace now includes VDP2 sprite-rotation/normal-layer scroll/zoom
state and command COLR. Keep each game's log separately; the sound probe is
not needed for graphics checks. Details and source limits:
`regtests/saturn/visual_followup_d402162b.md`.


## After Burner II follow-up — sound ready, later DMA-related wait

Latest captures `cc8a7db8`/`3e4b4384` show sound initialization completed:
RAM 04FC=0007F000, A5=00100000, A0=000BF000 and sound code intact. The main CPU
now waits at 0607BBC4 on software flag 06004E64=1, in a routine programming SCU
DMA. This is not the old sound wait and not yet a confirmed DMA/IRQ root cause.

Extended the existing Lua probe with read-only SCU DMA/IRQ state and main-RAM
operand/vector/handler snapshots; no executable rebuild is needed. Updated Lua
mock-binding tests pass. No new C++ emulation fix or successful game-boot claim.
See `regtests/saturn/afterburner2_boot_analysis.md` for evidence and command.

## After Burner II latest probe — false sound-CPU RAM mirror corrected

New uploads `d05617ff`/`faa4291a` show the SCSP reset correction clears the old
IRQ. A second blocker is now visible: the sound driver's clear loop writes beyond
07FFFF, and the 68000 map wrongly aliases the uninstalled expansion area onto its
own code. The snapshot's A0=0806BC and erased opcode at 06BA exactly match a
store through this false alias. Removed the CPU-side mirror for Saturn/ST-V;
Sega ST-077 Figure 1.3, MiSTer RAM chip select and Ymir CPU mapping agree.

Thirteen map/store cases include the historical corruption fingerprint; the old
alias mutation fails. **21 scripts/ten objects pass**, plus updated Lua fixture
checks. DSP/sample address wrapping is unchanged. No game boot acceptance claim:
rebuild/retest needed. See `regtests/saturn/afterburner2_boot_analysis.md`.
OutRun flashing is user-confirmed fixed; Power Drift geometry remains separate.

## After Burner II SOUNDPROBE — clock-change SCSP reset correction

The supplied three snapshots identify an old Timer B IRQ preempting startup
before A5 becomes the SCSP base. A5=00009CC0 sends acknowledgement writes to RAM;
the sound driver never reaches its ready-pointer write at 06F0 to RAM 04FC.
CKCHG320 had called SCSP reset, but that routine retained BIOS interrupt masks,
pending state and running timers. Sega ST-169 pp.30–31 require power-on defaults.

Fixed the SCSP interrupt/timer reset domain, including physical IRQ release and
replacement of old timer deadlines. No SNDON IRQ suppression, ready-flag patch or
68000 RESET-opcode change. New production-code reset regressions pass and reject
the old partial reset; **20 scripts/ten objects pass**, now including SCSP itself.
Game boot still needs runtime confirmation; broader SCSP reset fidelity is not
claimed complete. Details: `regtests/saturn/afterburner2_boot_analysis.md`.

## After Burner II follow-up 366ac068 — still hangs

User confirms `436988f9` did not fix boot. Decoded the new BOOTCPU capture: SH-2
loops on a zero longword at sound RAM 04FC (R1=25A004FC). The running sound CPU
repeatedly samples its level-2 handler at 07E6, with intended Timer B/SCIRE accesses
through A5. Missing sound A5 and SCSP enable/pending state prevent an exact cause
claim; no new interrupt suppression or game workaround is applied.

Added a read-only Lua snapshot probe that runs on the existing executable, without
a rebuild, plus a passing standalone mock-binding test. See
`regtests/saturn/afterburner2_boot_analysis.md` for decoded instructions and the
command. The earlier IRQ/reset correction remains separately tested, not an
After Burner II boot fix. OutRun flashing remains user-confirmed resolved.

## After Burner II instrumented follow-up — sound-startup wait

Analyzed and preserved user commit `629e6569`: the first CD read completes and
boot progresses through 2,351 CD commands. The persistent wait begins after
SNDON near 17.56 s; main PC remains 06010276/06010278 through 155 s. No new VDP1
lists are submitted; no pending CD transfer/command remains.

Corrected a source-backed sound IRQ/reset defect: SCSP level changes must reach
the 68000 even during SNDOFF/reset, otherwise change-only callbacks can lose an
assertion or leave a stale IRQ at SNDON. Sega SMPC, MiSTer wiring and Ymir were
cross-checked. Added bounded BOOTCPU instruction/register/sound-state diagnostics.
64 reset/IRQ transition tests pass; the old-gate mutation fails. All 19 scripts
and nine production objects pass. **Game boot is not yet confirmed fixed.**
See `regtests/saturn/afterburner2_boot_analysis.md` for evidence and acceptance.
OutRun flashing stays user-confirmed fixed; size/offset status stays unconfirmed.

## After Burner II boot stall — active investigation

The user clarifies that the `822d45ac` capture intentionally shows After Burner II
failing to boot. It is not a replacement OutRun scaling test. Analysis finds the
same 18-sector Read File/PAUSE sequence twice, separated by a long interval without
further logged CD commands and a soft reset. VDP1 continues completing lists.
Existing logging cannot distinguish a CD completion/polling issue from a CPU stall.

Added opt-in, rate-limited `CDBOOT` status/CPU-PC/host-read diagnostics without
changing emulation behavior. Diagnostic checks and 336 CD transfer cases pass;
all 18 scripts/nine production objects passed with the instrumentation. See
`regtests/saturn/afterburner2_boot_analysis.md` for timestamps, limits and the
focused next capture. No After Burner II boot fix is claimed. OutRun flashing
remains user-confirmed resolved; the reported size/offset issue remains open.

## Runtime follow-up: OutRun flashing confirmed resolved

The user confirms the flashing sprites are gone following the manual display-erase
ordering fix. This is user-run validation, not a local game boot or full VDP1
acceptance. The size/offset issue has not been confirmed resolved.

Reviewed upload `822d45ac`: its console includes OutRun followed by After Burner
II. `newerror.log` appears to contain the later ~92-second run, with 2,336 normal
sprite records and no scaled records. Logged normal source/destination dimensions
match; the file cannot establish an OutRun scaling cause. The earlier trace and
new upload remain preserved. See `regtests/saturn/outrun_trace_analysis.md` for
provenance and single-game capture instructions. No rendering changes or new
regression-test claims were made in this documentation-only follow-up.

## OutRun log received: manual erase presentation ordering

Analyzed the user's `c4ae255c` upload: Saturn Japan/OutRun, 44,945 scaled commands,
2,265 completed lists and 1,647 idle bank swaps. No busy swaps or mode-dependent
sprite doubling occur in the capture. A car-sized command maps 88x41 source to
88x41 destination. These findings supersede the unconfirmed hypotheses below.

The trace alternates manual erase/change. The existing manual-erase path blanked
the displayed bank at the start of its presentation field. It now captures the
erase and commits after that field, before the following bank exchange, retaining
the visible image for both fields. Pending bank/data/bounds are saved and canceled
on reset. This is coarse read-before-erase ordering, not a per-HBlank bus model.
24 new presentation/restore cases pass; early-erase and wrong-bank mutations fail.
All 18 regression scripts and nine production objects pass.

See `regtests/saturn/outrun_trace_analysis.md` for exact timestamps, provenance,
primary/reference support and acceptance limits. Normal-sprite trace records were
added to investigate the earlier logo scene. **The flashing fix needs a game rerun;
the size/displacement defect remains unresolved.** No wholesale X/Y swap was made.

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

## VDP1 line execution across scheduler boundaries — 2026-09-14

- Primary [ST-013-R3](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf), printed p.20: drawing is synchronized to the CPU operating clock, with one pixel's data drawn in sync. This supports a nominal pixel progression model, **not** proof that every color operation takes one clock.
- Printed p.51: ENDR terminates current drawing within approximately 30 clocks, and interrupted drawing cannot be resumed. The line/polyline cursor is now canceled by the existing 30-clock timer, not left waiting until the whole primitive completes. PTMR starts anew at command zero.
- Printed pp.52–56: END fetch produces completion; COPR identifies the interrupted command and pseudo-continuation uses a new command-list start. The command engine now blocks the next fetch while a line cursor is active, so a queued END cannot finish an incomplete line.
- Geometry and Gouraud progression reuse the native integer model cross-checked against [Ymir's steppers](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/include/ymir/hw/vdp/renderer/common/vdp1_steppers.hpp). No reference scheduler or renderer code was imported.
- Printed p.20 also defines drawing bank 0/display bank 1 after power-on or reset. Startup, machine reset and SMPC system reset now share a bank-view reset helper, without adding a RAM clear. The old startup assignment reversed the roles. The test checks pointer/CPU ownership and data preservation.
- A 16-dot host quantum bounds work; partial final quanta use their actual dot count. Writes become visible in batches. Exact Gouraud/setup/VRAM costs and partial-quantum bus visibility are not modeled. Sprite/polygon execution remains atomic.
- 748 tests exercise actual queued line/polyline entry points and pixel writers, cancellation at each phase, END-before-stop ordering, CPU framebuffer writes, restart and manual state-copy/postload reconstruction (also with pending ENDR). Real save-manager and linked runtime acceptance remain pending.


## VDP1 finite VBlank erase capacity — 2026-09-14

- Primary [ST-013-R3 pp.46–50](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf): EWDR stores a word (two dots in 8-bit); X registers use eight-word groups; excess blank erase work is interrupted and must be filled with polygons. Table 4.5 gives the capacity as `(clocks_per_raster - 200) * blank_rasters`. All 12 published capacities are tested literally.
- [MiSTer VDP1](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/VDP1/VDP1.sv): `VBERASE_PEND` routes rotated erase into blanking; erase word addressing advances while `VBLANK_ERASE` is active and stops at blank end. The RTL is a cross-check, not imported source.
- [Mednafen VDP1](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp1.cpp), `SetHBVB`: captures blank entry, commits bounded erase at blank end before bank swap, and latches erase parameters on swap. Its coarse commit strategy supports this integration approach; its cycle accounting includes row overhead and eight-word chunks, unlike this implementation's primary-table word capacity. No claim of identical bus timing or three-way cycle agreement.
- New implementation saves pending request, target bank, format stride, bounds, data and capacity; reset cancels without touching the bank. ENDR does not cancel erase. Per-slot/row overhead and active-display erasure remain future implementation work.
- 154 cases validate full-bank images, all TVM layouts/banks, sparse windows and partial-row cutoffs, delayed writes, pending-state copy plus postload reconstruction, reset cancellation and blank-only scheduling. This is not a real save-manager round trip. Full 18-script/nine-object validation passes; unlimited-budget/wrong-bank/live-data mutations fail independently.


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


Date: 2026-09-14. Repository: `jkind73/saturnsdk`.
Pinned revision: `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`.

## Coverage and provenance

The complete, non-truncated Git tree contains 3,968 files, including 106 paths
ending in `.pdf`. Three are `._` metadata companions; excluding those leaves
**103 PDF documents** (65,492,354 bytes). See [sdk_documents.csv](sdk_documents.csv)
for paths, Git blob hashes, byte sizes, and text-extraction status. The manifest
covers PDFs, not the repository's additional DOC/TXT files or compressed archives.

95 PDFs were converted to searchable text with pypdf. Eight have no extracted
text in this pass; see the manifest. The batch encountered a null encryption
entry parsing error; that error is not a finding about document contents, and
we have not classified the individual remaining failures. PDF page counts in
the manifest come from successful text extraction. **Extraction/indexing is not
reading or validating every document.** Selected sections actually read are below.
Diagrams/tables extracted as text may lose layout; ambiguous diagrams require
visual review before implementing their behavior.

Manuals and extracted text are cached outside the repository, not committed.
Only bibliographic metadata and original analysis are added. Repository hosting
does not imply redistribution permission for Sega manuals, SDK code or libraries.
The cache is disposable; pinned links and blob hashes are the durable references.

## Core reference map

All links below point to the pinned SDK revision. PDF page numbers are one-based
file pages, distinct from the manual's printed page numbers.

| Document | Role | Review in this pass |
|---|---|---|
| [ST-058-R2-060194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-058-R2-060194.pdf) — VDP2 User's Manual v1.1 | Registers, counters, scroll and compositing | Selected sections listed below |
| [ST-013-R3-061694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf) — VDP1 User's Manual | Drawing, framebuffer control | Indexed; behavior sections not yet audited |
| [ST-013-SP1-052794](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-SP1-052794.pdf) — VDP1 supplement | Supplementary VDP1 information | Indexed only |
| [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf) — SCU User's Manual, third version | DMA, interrupts, DSP, timers | Timer registers §3.4, printed pp.55–56 / PDF pp.71–72; interrupt masks/status PDF p.74 |
| [ST-210-110194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-210-110194.pdf) — SCU Final Specifications: Precautions | Corrections and hardware restrictions | Items 20–24, PDF p.11; items 29–32, PDF p.13 |
| [ST-077-R2-052594](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-077-R2-052594.pdf) — Saturn SCSP User's Manual | Audio hardware | Indexed; earlier source citations not revalidated yet |
| [ST-169-R1-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-169-R1-072694.pdf) — SMPC User's Manual | System manager and peripherals | Indexed only |
| [Sattechs.pdf](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/Sattechs.pdf) — technical bulletin collection | Corrections and programming guidance | Bulletin #12 PDF p.54; #14 PDF pp.56–59; slave interrupt discussion PDF p.88 |
| [ST-202-R1-120994](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-202-R1-120994.pdf) — Dual CPU User's Guide | CPU coordination | Indexed only; use alongside DCC and slave-IRQ investigation |
| [sh7604.pdf](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/sh7604.pdf) | SH-2 reference candidate | Located, text not extracted; not yet reviewed |

## Findings affecting the current branch

### 1. SCU timer work is not complete

ST-210 item 30 (printed p.9, PDF p.13) explicitly places timer-0 compare value
**0 at VBlank-OUT**, and lists positive compare values against HBlank-IN, including
263 for the NTSC example. ST-097 §3.4 says the counter increases on HBlank-IN and
clears at VBlank-END.

Current `vblank_out_w()` clears the counter but does not check timer 0. Current
`hblank_in_w()` compares before incrementing. This needs an event-order fix and
trace tests; the earlier scheduler fix restored missing edges but did not fix
these compare semantics. TENB gating and exact frame phase must be considered
before changing ordering.

ST-210 item 31 explicitly says timer 1 reloads on HBlank **when stopped**. It also
confirms that a programmed zero represents 512 counts. Current `hblank_in_w()`
re-arms `m_timer1` on every eligible HBlank, even if it is still running. A count
longer than one line can therefore be perpetually postponed instead of completing.
This is the highest-priority next behavioral fix, with tests for repeated HBlank,
expiry, disable, reload-register writes and T1MD. The existing zero-to-512 conversion
is supported, but by itself is insufficient.

ST-210 item 24 says DMA-illegal status does not occur during indirect DMA execution.
Audit this against the inherited directional validation before claiming DMA rules
complete. Items 21–22 document enable-gated start factors and one held trigger;
they provide concrete future DMA test cases.

### 2. V-counter bounds fix versus counter encoding

ST-058 §2.2, printed p.24 / PDF p.42, table 2.4 describes a **10-bit** double-density
counter: field count in bits 9:1, odd/even indication in bit 0 (0 odd, 1 even).
The current approximate expression replaces bit 0 of an unshifted field count and
masks to nine bits. That is not the documented encoding. The same manual table's
non-interlace encoding conflicts with the hardware-test note inherited in MAME.
Do not silently change all modes based on the table alone: obtain the hardware
trace behind that note and cross-check interlace separately.

Our `vpos / 2` change fixes table addressing within MAME's doubled screen geometry;
it does not establish the register's real encoded value or rollback positions.
The prior table-equivalence tests are preservation tests, not hardware oracles.

### 3. Vertical cell scroll: confirmed layout, missing fractional behavior

ST-058 §5.1, printed pp.134–136 / PDF pp.152–154, documents screen-left table order,
relative vertical offsets, and alternating NBG0/NBG1 entries when both are enabled.
This supports preserving screen-anchored addressing in our clip fix. Bitmap format
uses eight-dot units. It does **not** by itself justify the proposed unconditional
16-dot width change for larger character patterns.

Figure 5.7 includes an **eight-bit fractional part** alongside the eleven-bit
integer part. The current path reads only the upper halfword and drops the
fraction. Bulletin #14 (PDF pp.56–59) gives a bitmap technique combining vertical
cell scroll and line scroll, with fractional values. The current branch expressly
excludes combined vertical-line-scroll/line-zoom cases. Clipping safety tests do
not cover those missing hardware functions.

### 4. Mosaic remains incomplete even with safe bounds

ST-058 §4.11, printed pp.117–119 / PDF pp.135–137, describes upper-left sampling
per mosaic block, sizes, horizontal-only rotation mosaic, and mosaic priority over
vertical cell scroll. The current helper's interlace/rotation handling and block
origin need a hardware-level review; preserving existing output in the bounds test
is not validation of these rules. Keep the incomplete post-processing paths gated
until per-layer transparency/compositing is correct.

### 5. Screen-over pattern has a cell-format restriction

ST-058 screen-over discussion, printed p.115 / PDF p.133, confirms the one-word
pattern-name interpretation, supplementary bits, and per-rotation-parameter A/B
selection. It also explicitly excludes the repeated over-pattern mode for bitmap
format. The supplied candidate patch lacked that restriction, in addition to the
previously identified decoding and address-wrap problems. Do not apply it wholesale.

### 6. CRAM byte writes are prohibited, not documented as ignored

ST-058 §1.2, printed pp.3–4 / PDF pp.21–22, permits word/longword accesses to CRAM
and registers and prohibits byte access. This supports a software restriction,
not the proposed implementation claim that all byte writes have no effect.
ST-210 item 32 (PDF p.13) distinguishes external longword reads from byte-sized
writes on the A/B buses; it does not specify the VDP2's response to an illegal
CRAM byte write. Hardware tests are still required for that response.

### 7. TVSTAT citation verified; slave timing needs separate care

Bulletin #12 item 3 (PDF p.54) confirms that DISP=0 forces the TVSTAT VBLANK bit to
one. It does not say to force HBLANK or suppress SCU interrupts. The existing
TVSTAT comment correctly limits the claim to that flag.

The slave-interrupt discussion in Sattechs PDF p.88 confirms level-sensitive
blank interrupts through DCC, with HBlank vector 0x41 and VBlank vector 0x43.
It does not by itself prove the exact VBlank gating adopted from Ymir. Keep that
emulator comparison distinct from the official-document evidence.

## Next implementation and validation order

1. Fix timer-1 running/reload behavior against ST-210 item 31, cross-check Ymir
   and another implementation, and add event-order tests.
2. Resolve timer-0 compare-zero/increment order against item 30 and actual CRTC
   phase; test both NTSC and PAL plus TENB/T1MD interactions.
3. Verify interlace register encoding and field transitions with independent
   traces before altering the preserved rollback tables.
4. Implement missing scroll/compositing behavior with per-pixel tests derived
   from manual rules and bulletin #14 examples, not just existing MAME output.

No emulation behavior changed in this documentation pass. All new findings are
open until implemented and validated. Official Saturn documents establish shared
chip behavior, but ST-V board-specific wiring still needs separate evidence.

## Implementation update: timer-1 reload

The stopped-only reload issue identified in finding 1 is now fixed and covered by
`test_timer1.py`; see the [test report](README.md#scu-timer-1-stopped-only-reload-fix).
The earlier findings describe the code as inspected during the document audit.
Timer-0 ordering, T1MD interrupt qualification, hardware timer rate, and the other
open findings are not resolved by this narrowly scoped fix.

## Implementation update: timer-0 event order

The compare-zero and increment-order discrepancies in finding 1 are now fixed:
TENB gates counting, zero is checked at VBlank-OUT, and positive compares follow
the HBlank increment. See the timer-0 section in README.md for 8,192 tested
scenarios and remaining limitations. Current CRTC phase, mid-line register-write
behavior and full timer-1 mode qualification have not been hardware-validated.
The original findings and next-work list above are the historical audit, not the
current completion status; these implementation updates supersede them narrowly.

## Implementation update: double-density V-counter encoding

Finding 2's double-density bit-layout discrepancy is now corrected: nine field
count bits in VCT9..1, inverse ODD in VCT0, ten bits retained. The ST-058 table 2.4
interpretation was cross-checked with Ymir and Mednafen. Tests independently cover
all count/field combinations and external-latch storage; see the README report.
The non-interlace manual/hardware-note discrepancy, field geometry and rollback
values remain unresolved. Earlier statements describing the approximate encoding
refer to the pre-fix audit, not the current getter.

## Additional reset audit: EXTEN

Read ST-058 §2.5, printed p.19 / PDF p.37, covering EXTEN reset and latch-source
selection. Confirmed the all-zero reset against Ymir and Mednafen. Corrected the
MAME reset's stale decoded control bits; register readback now agrees with the
external-latch enable and other controls. See `test_exten.py` and README.md for
64 tested scenarios and limits. This does not validate the whole VDP2 reset or
TVMD initialization; those remain separate audit items.

## Additional reset audit: TVMD

Read ST-058 §2.4, printed p.16 / PDF p.34, confirming TVMD clears on power-on/reset.
Verified with Ymir/Mednafen. TVMD and decoded display/mode controls now initialize
before the startup clock callback and clear on device reset before CRTC setup.
3,072 scenarios cover initializers, register handlers and reset/CRTC helpers.
This supersedes the previous note that TVMD initialization remains unaddressed;
other reset registers, actual screen scheduling and SMPC reset wiring remain open.

## Address-map audit update: C-Bus mirrors

The missing `0x07xxxxxx` C-Bus decode was corrected using the existing Saturn/ST-V
memory maps plus Ymir GetBusID and Mednafen AddressToBus/DMA_ReadCBus. The README
records 768 classification checks and 2,304 direct DMA scenarios. This is an
explicit source/emulator cross-check: a precise official mirror-aperture section
has not yet been established, and no hardware measurement is claimed.

## Indirect descriptor audit update

Read ST-097 §2.1, printed pp.19–20 (PDF pp.35–36), §3.2 printed p.42 (PDF p.58),
and ST-210 item 25, printed p.8 (PDF p.12). These distinguish indirect descriptor
execution/format from direct count registers. The all-channel twenty-bit descriptor
width and zero-to-1-MiB rule are supported by Ymir/Mednafen, with MiSTer confirming
the width, not explicitly by the inspected manual prose. Corrected the narrower
channel-1/2 mask and zero handling; 54 legal two-entry chains now pass through
completion. Runtime/clock/arbitration and unusual transfer cases remain open.

## Two-channel DMA priority audit update

Re-read ST-097 §3.2, printed p.41 / PDF p.57, and ST-210 items 20 and 35 (printed
pp.7/10, PDF pp.11/14). Fixed the tick state update that suspended the new winner
rather than the lower-priority previous owner. Ymir and Mednafen independently
select active channels in descending priority. 64 supported two-channel scenarios
cover preemption/resume; the separate halt handoff fix preserves MAME's existing
approximate policy, not Mednafen's bus-dependent implementation or proven physical
CPU-halt behavior. Exact latency and unsupported overlaps remain open.

## Held external DMA trigger audit update

ST-210 printed p.7 / PDF p.11, items 21–23, establish enabled matching events,
one held activation and the prohibition on rewriting active registers. ST-097
printed pp.45–46 / PDF pp.61–62 supplies the enable/start/update definitions.
Mednafen's `GoGoGadget`/`CheckDMAStart`/`SCU_DoDMAEnd` path corroborates one-slot
external-event holding. Ymir's pinned `TriggerDMATransfer` excludes active channels
and does not corroborate that behavior; the documented MAME behavior was retained.
924 external-event scenarios pass; five explicit test-only mutations fail. No
production change was needed. Exact hardware event timing, DxGO MMIO and held-
state reset/save-load are not established by this test.

## AREF audit update

ST-097 figure 3.30 / table 3.24 (printed p.72, PDF p.88) defines AREF bits 4:0
but prints the older zero initial value. ST-210 item 33 (printed p.10, PDF p.14)
explicitly changes ARFEN to 1 on power-on reset. Corrected the device reset value
to 0x10 and masked stored writes to 0x1f. MiSTer/Mednafen corroborate the mask,
not the corrected reset; Ymir ignores AREF writes. The primary erratum takes
precedence. No dynamic refresh timing or hardware write-protection behavior was
inferred. Independent pre-fix reset and write controls fail; 32 resets, 32,768
AREF writes, 288 ASR writes and 24,576 existing static wait decodes pass.

## A-Bus interrupt mask audit update

ST-097 §3.5, printed p.57 / PDF p.73, explicitly defines IMS15 as a mask with
one blocking and zero allowing interrupts. Corrected the reversed external condition.
Table 2.1 (printed p.27 / PDF p.43) supplies the tested priorities/vectors; table
3.8 (printed p.59 / PDF p.75) defines status write clearing. Mednafen sign-extends
IMask bit 15 to mask external requests and corroborates polarity. Pinned Ymir uses
the opposite external condition despite a direct bit-15 field; it was not treated
as authoritative over the manual. 1,920 arbitration cases, 16 acknowledgement
sequences and 512 register writes pass; pre-fix arbitration fails. Actual CPU/CD
runtime and full external-acknowledgement bus behavior remain unvalidated.

## DMA programmed address width audit update

ST-097 §3.2, printed p.41 / PDF p.57, defines DxR/DxW bits 26:0 for every channel.
Removed incorrectly stored cache-alias bit 29 from both write masks. Ymir extracts
bits 0..26; Mednafen and MiSTer use 0x07ffffff. Direct count widths on the following
page remain unchanged. 15,360 address and 7,680 count writes/readbacks pass with
separate failing pre-fix source/destination controls. End-of-transfer address-update
wrapping, MMIO routing and CPU/cache runtime are outside this increment.

## DMA control-register audit update

ST-097 §3.2 printed pp.43/45/46 (PDF pp.59/61/62) supplies increment decoding,
enable/GO and mode/update/factor fields. Cross-checked with Ymir's WriteRegLong /
TriggerImmediateDMA and Mednafen's masked control writes. Existing handlers pass
13,824 new field/byte-lane/start-gate scenarios; no production correction warranted.
Four test-only mutations fail. Dispatch endpoints are recorders, so full MMIO-to-
transfer/IRQ integration, active-register restrictions and bus-specific increment
behavior remain outside this test.

## Build coverage update (no hardware behavior change)

Validation now compiles six core/driver translation units, adding Saturn console,
ST-V and DCC. Corrected emu.h include ordering in DCC/ST-V; pre-fix files fail with
otherwise complete shared/layout include paths. Layout headers are generated with
MAME's own tool in temporary storage. All thirteen scripts/six objects pass.
This is build evidence only, not additional primary-document or runtime validation.

## CD build coverage update (no hardware behavior change)

Routine object validation now includes CD HLE and the CD block wrapper, bringing
the total to eight. Corrected CD HLE's emu.h include order after reproducing the
header/incomplete-type errors; the CD block wrapper compiled unchanged. All
thirteen scripts/eight objects pass. No primary hardware interpretation or CD
runtime correctness claim follows from this build-only change.

## DMA forced-stop control implementation

ST-097 §3.2, printed p.47 / PDF p.63, defines DSTP bit 0 at $05fe0060. Previously
unmapped, it now cancels CPU-programmed DMA including waiting/held work, preserving
programmed registers and existing IRQs. Ymir/Mednafen corroborate three-channel
cancellation without completion IRQ; Mednafen's stop case remains marked untested.
2,321 standalone scenarios pass; a no-op control models the old missing mapping
and fails. Physical stop latency and actual game compatibility remain unestablished.

## Four-priority implementation evidence — 2026-09-14

- **SCU source buffering:** ST-097 §3.2, printed pp.41–43 (PDF pp.57–59),
  supplies source address and 0/4 increment controls. Pinned Ymir SCU `doRead`
  and Mednafen `DMA_Read` corroborate longword buffering/byte position. New
  source-buffer tests pass 1,152 scenarios; baseline e7cff8b8 fails. This is not
  verification of every alignment/count configuration or the separate CD path.
- **CD DataEnd/deletion:**
  [ST-162-062094](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-162-062094.pdf),
  CD Communication Interface, printed p.32/PDF p.20 requires DataEnd after an
  accepted transfer; printed p.81/PDF p.69 specifies stopping, dummy excess
  data and effective CD word counts; printed p.96/PDF p.84 specifies deleting
  the entire Get-and-Delete range even when not fetched. Printed p.97/PDF p.85
  says interrupted PUT retains designated sector count, with unspecified tail
  bytes. Pinned Ymir CD `EndTransfer` and Mednafen `COMMAND_END_DATAXFER` both
  deactivate transfers; they disagree on some deletion/dummy details, so the
  primary full-range rule governs. Existing idle value and deletion timing
  are retained, not claimed as hardware measurements. Partial GET count needs
  a prefetch model; zero-data error reporting is also not fixed in this pass.
- **SMPC:** ST-169-R1-072694 printed p.49/PDF p.59 resets IOSEL/EXLE;
  printed pp.50/52/58 (PDF pp.60/62/68) defines CONTINUE as reversing IREG0 bit7,
  BREAK termination, and prohibits simultaneous CONTINUE/BREAK. Mednafen's
  alternating `NextContBit` corroborates the toggle; Ymir's level-based check
  disagrees and was not copied. Ymir does corroborate clearing SF/canceling
  pending collection on BREAK. Neither current 700us delay nor VBlank timeout
  is validated by these tests.
- **HALT ownership:** this is host-emulator signal composition, not a new Sega
  timing claim. Both Saturn/ST-V wired SMPC and SCU directly to the same HALT
  lines; independent saved sources prevent one callback clearing the other.
  1,296 event sequences verify composition/reset with recording CPU endpoints.

PDF extraction correction: both ST-162 files have a malformed `/Encrypt null`
trailer, not actual encryption. Ignoring only that null entry lets pypdf extract
ST-162-062094 (91 pages) and ST-162-R1-092994 (53 pages). The latter is System
Library, not the CD Communication Interface. The earlier SDK extraction manifest
is historical and still records these two failures; six other failures have not
been retried. No downloaded SDK documents were added to Git.

All 17 scripts/nine objects pass. CD pointer/payload/directory/MPEG saves and ISO
parser bounds remain open; copied-state tests are not real MAME save/load proof.
See `game_blockers.md` for scope and the remaining runtime dependency blocker.

## VDP1 implementation pass — 2026-09-14

Fixed END-bit recognition, VRAM command wrap, completion-driven SCU IRQs (removed
periodic scanline IRQ workaround), 8-bit CPU framebuffer byte lanes, and outside
user clipping across fast/generic pixel writers. 32,775 command, 288 framebuffer
and 24,500 clipping cases pass; three independent baseline substitutions fail.
All 18 scripts/nine object builds pass. This is **not complete VDP1**: synchronous
drawing, ENDR, exact draw/erase/swap timing, BEF/pointer details, full framebuffer
formats, rasterization/texture/color edge cases and real save/load/runtime proof
remain. See `regtests/saturn/vdp1_completion.md` for evidence and acceptance gates.

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

### Primary sections and reference qualifications for the sequencer/packed pass

ST-013-R3-061694 §4.3 (printed p.45/PDF p.60) specifies PTMR=1 restarts drawing
from the top even while drawing. §4.5 (p.51/PDF p.66) specifies ENDR, no resume,
and approximately 30 clocks to terminate; this pass implements command-boundary
cancellation, **not** that pixel-pipeline latency. §§4.7–4.8 (pp.54–55/PDF69–70)
specify LOPR at framebuffer change and live COPR. The command jump table lists
all eight jump/skip controls; precautions pp.158–159/PDF173–174 prohibit nested
CALL and RETURN in the main routine. These prohibited cases remain distinct
from the valid sequencer paths, without claiming a primary-defined result.

§1.1 p.13/PDF28 defines low-eight-bit pixel writes; the framebuffer is two
2-Mbit banks, and §4.4/EWDR defines even-X/odd-X byte pairs. The packed tests
cover replace rendering, not prohibited 8-bit color calculations (§6.3).
Pinned Ymir `VDP1ProcessCommand` uses 16-cycle command fetches and persistent
command/return addresses. Its software renderer `VDP1PlotPixel` stores byte dots
for 8-bit mode and derives byte offsets from framebuffer width. This supports
the layout change, not a complete hardware timing claim. Ymir also has an ENDR
30-cycle TODO and a game-dependent start-delay workaround; neither was imported.
The mere presence of a feature in a reference emulator is not proof of all its
edge cases. No unreviewed source or title-specific delay was copied.

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

### Rendering evidence and disagreements

Primary ST-013-R3-061694 §6.3 printed pp.86–87/PDF101–102 defines the second
horizontal source end code and independence from SPD. The normal-sprite tests
cover all six documented texture formats, four read directions, ECD/SPD and
pairs of end positions on two rows. They do not cover scaled/distorted sampling
or pre-clipping inversion. Lookup address wrap includes a deliberately unaligned
(outside Sega's legal alignment requirements) table as a memory-boundary test,
not evidence of a supported guest configuration.

§6.3 pp.94–97/PDF109–112 defines replace/shadow/half-luminance/half-transparency,
Gouraud saturation before combination, and MON modifying the existing framebuffer.
The arithmetic tests include exhaustive component pairs, both MSBs and legal
operation selectors. MSB-clear RGB arithmetic cases test the chosen model, not a
hardware guarantee where Sega says results cannot be guaranteed.

Pinned Ymir `VDP1PlotPixel` and Mednafen `PlotPixel` support destination-preserving
MON and average-then-truncate blending. Ymir's line traversal also advances Gouraud
through suppressed dots and counts end codes on newly fetched texels. Pinned
MiSTer `VDP1.sv` selects the background for MON and ORs the top framebuffer bit;
`VDP1_pkg.sv` confirms saturation and component operations. **MiSTer's ColorCalc
halves each operand before addition, unlike the Ymir/Mednafen odd+odd result.**
This implementation follows the manual's average wording and Ymir/Mednafen, not
an assertion that all three references agree. 8-bit MON word-alignment is still
reference-modeled and not independently hardware-verified.

BEF's bank-change latch is supported by §4.6 printed p.53/PDF68 and Ymir's
`VDP1SwapFramebuffer`; main-list start still clears CEF without overwriting BEF.
The manual's start-of-drawing wording needs hardware qualification; no complete
frame timing claim follows from correcting the unconditional VBlank overwrite.

The version supplement ST-013-SP1-052794 was also read (14 PDF pages); it describes
version-0 versus version-1 EOS/HSS/pre-clipping differences, not missing rounding
or pipeline timing details. No source code was imported from any reference.


### After Burner II masked DMA completion (29b70a92 capture)

DMA0 has completed; IST=289f holds DMA0-end pending while IMS=bfff masks it.
The CPU waits inside an interrupt callback. Do not remove the documented
acknowledgement mask reset or force the game flag. The no-rebuild sound probe
now adds bounded register-write/vector-read history and BIOS mask/dispatch
RAM snapshots to distinguish mask restoration from a later acknowledgement.
Sound startup is fixed; game boot remains unverified. See
`regtests/saturn/afterburner2_boot_analysis.md` for evidence and trace caveats.


### After Burner II / SH DRC delay-slot IRQ correction (2f84a960 evidence)

The new trace shows VBlank delivery after software has masked all interrupts
again. The shared SH DRC discarded `checkints` set by an SR load in a branch
delay slot; Saturn BIOS ChangeSCUMask restores SR in the RTS delay slot.
Propagate that compiler state so the caller checks interrupts after the slot.
SCU latch/mask reset and DMA timing remain unchanged (Ymir/MiSTer corroborate
the latch). Regression: 72 cases pass, old-state mutation fails; all 22 Python
scripts and eleven objects pass, including the modified SH core. This is a
concrete code correction, not confirmed game-boot acceptance. A rebuilt
executable is now required; the existing probe needs no further change.
See `regtests/saturn/afterburner2_boot_analysis.md` for ordering and limits.

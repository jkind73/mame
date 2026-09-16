# VDP2 implementation report and progress tracker

## P2 combined scroll/rotation batch — 2026-09-15

**P2 is not fully complete.** This batch implements and tests several remaining
S01/S02/R02/R03/R04 defects together; the parent checkboxes below deliberately remain
open where implementation or qualification is still missing.

### Delivered changes

- **S01/S02:** retain 8-bit fractional X/Y scroll phases in NBG0/NBG1 descriptors and
  all five bitmap writers. Line-scroll table offsets now retain fractional carry,
  including vertical interpolation when an entry begins at a fractional phase.
  Derived descriptor phases are restored between partial passes and cleared for
  unscrolled rotation-cache construction. Tilemap sampling does not yet consume
  those phases: this is not completion of ordinary fractional tile rendering.
- **R02:** correct Px sign extension (only the 14-bit coordinate's sign bit, not
  the next lower positive-coordinate bit). Added actual parameter-table unpacking
  checks across A/B addresses and all parameter field widths, with RPRCTL reload
  bits enabled. Added signed short/long coefficient and screen-over boundary images.
- **R03:** RPMD 2 now selects B using A's coefficient MSB *before* transparency and
  color calculation. B is no longer a second background drawn beneath A: an absent
  A dot exposes the previously composed screen, and ratio/additive calculation does
  not combine both parameters. When A reads per-dot coefficients, B reads per-line
  coefficients as required. A coefficient selection reads are cached only within
  the current compositor pass.
- **R04:** RBG1 already reached rotation B; it now discards inherited normal-scroll
  X/Y increments, line/cell-scroll enables and stale mode-3 state. Its output windows
  use NBG0-shared controls, not RBG0's. The ordinary shortcut is excluded for RBG1;
  source-cache windows remain disabled and output windows remain active. Two enabled
  rotation screens suppress the normal screens.
- **R04 cache:** track effective character numbers after masking/format adjustment.
  Watch the full character extent for each format/size, not just the first 32 bytes
  of the last character. A wrapping character conservatively watches the entire
  decode allocation, including the existing upper-aperture access behavior.

### Evidence and validation

Primary ST-058: pp.124–128/131–138 fractional coordinate and line-scroll formats;
pp.153–156 parameter layouts; pp.161/166 mode-2 parameter selection, B coefficient
fetch restriction and transparency; p.148 dual-rotation resource restrictions;
chapter 4 character sizes/data and shared screen controls. Pinned Ymir 6d779960
`VDP2SelectRotationParameter` selects before pixel composition; its scroll state
retains fractional coordinates. Pinned MiSTer a95b0850 `PNData`/`RxCHAddr` corroborate
format-dependent character extent and shared rotation addressing. These comparisons
are not a silicon timing oracle.

- **46,080** production bitmap/palette/window images, now including fractional phase.
- **16,800** production line-scroll scheduling cases, now including fractional table
  offsets, fractional vertical increments and whole-versus-split equivalence.
- **960** production A/B parameter unpacking configurations against a separate
  field-width/bit-position oracle; the prior Px decoder compiles and assertion-fails.
- **144** selection-before-composition images with short/long A entries, no/line/dot
  coefficients, absent A/B pixels, B transparency and opaque/ratio/additive output.
- **648** additional signed short/long coefficient images covering repeat,
  transparent-outside and fixed-512 boundaries and split clips. Earlier 2,880
  screen-over-pattern, 9,216 rotation and 360 coverage images still pass.
- **262,144** RBG0/RBG1 window-control pixels; **256** RBG1 shared-register setup cases.
- **13,824 + 18,432** reduction/color-depth dispatch cases, including dual-rotation gates.
- **15,200** actual VRAM-write invalidation checks across character tails/wrapping.
- Independent dropped-fraction, selection-bypass, wrong-window-bank and truncated
  cache-range mutations compile and assertion-fail. **32 scripts / eleven production
  object builds pass**; log: `/home/user/.cache/saturn/p2-batch-validation.log`.

### What still prevents P2 completion

| Parent | Remaining implementation/qualification |
|---|---|
| S01 | Fractional character-tile sampling and complete zoom-coordinate equivalence; bitmap tests do not establish it. |
| S02 | Source-coordinate cell boundaries, cell-scroll with vertical line scroll/line zoom, mosaic priority, actual interlace fetches, and combined pixel fixtures without nested-render growth. Existing combination exclusions remain in production. |
| R01 | Shared special-priority/calculation metadata and linked qualification; base repeated-pattern pixels are implemented. |
| R02 | Full fixed-point precision/overflow and physical coefficient-fetch behavior beyond the new field/image fixtures. |
| R03 | **RPRCTL one-shot scanline reloads remain missing.** ST-058 pp.152/158 describes reloading and clearing bits at the next parameter read. Existing frame-snapshot overrides are not that model. Coefficient line-color interaction remains missing. |
| R04 | Physical VRAM resource/arbitration qualification and linked cache/save/load/performance checks beyond descriptor/window/invalidation fixtures. |

RPRCTL requires a scanline latch/partial-presentation model coordinated with T01/H01;
this batch does not silently substitute a guessed frame-level reload rule. No new
persistent hardware latch state was added; fractional fields and coefficient memoization
are derived render state. Save-manager and game acceptance are still not established.


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


**Audit date:** 2026-09-15  
**Audited implementation:** `ad5ae529` on `arena/01a09f50-mame`  
**Scope:** Saturn/ST-V VDP2 device, background renderer, VDP1-to-VDP2 composition, memory/register integration and validation. This is a source-level baseline, not hardware certification. No emulation code changes are included in this report.

## 1. Executive summary

VDP2 is **substantially implemented but not feature-complete**. Normal backgrounds, bitmap/tile rendering, rotation backgrounds, scroll tables, basic priorities, RGB/palette output, ordinary blending, color offsets, windows, timing/status and framebuffer composition have working code paths. Several important effects are partial, gated off, or missing.

The largest functional gaps are:

- **Complete per-pixel composition:** special priority, special color calculation, sprite-window masking, destination-layer-aware shadows and additional color-calculation modes.
- **Line-color screen and mosaic integration:** helper functions exist, but their normal background postprocessing calls are disabled by `TEST_FUNCTIONS == 0`. The mosaic test does not mean the feature is enabled.
- **Rotation edge cases:** screen-over-pattern base pixels are implemented; shared special-function metadata and parameter switching still need qualification.
- **Scroll combinations and reduction controls:** only a subset of combined vertical cell scroll/line scroll is handled; reduction-enable controls are defined but not applied by a complete limiter implementation.
- **Raster-visible register/memory changes:** the renderer supports clip rectangles, but generic VDP2 writes do not first preserve the already-scanned image. The new VDP1 erase-driven partial updates are not a general VDP2 raster-effects implementation.
- **VRAM access scheduling:** cycle patterns are checked for access-command presence, not modeled as a bank/slot-accurate fetch and CPU-contention system.
- **Timing and qualification:** true interlace/half-lines, PAL/exclusive modes, physical counter edges, real save/load and linked runtime/performance testing remain open.

Do **not** assign a completion percentage: individual features have very different scopes, and most combinations have not been qualified. Likewise, the old source comment calling the device a “stub overlay” describes the separate timing device, not the entire renderer.

## 2. Status definitions and tracking rules

- **Implemented:** an active production path exists. This does not certify every legal combination.
- **Partial:** a useful subset exists, with identified omissions or approximations.
- **Missing/gated:** no effective complete path was found, or the path is disabled in normal builds.
- **Qualification open:** code exists, but sufficient hardware or linked-runtime evidence is absent.
- `[x]` records a completed, narrowly stated baseline fact or task. It does not close the parent feature.
- `[ ]` records remaining implementation or verification work. Keep stable IDs when updating this report.

Every future implementation entry should record: primary-document section, independent cross-checks and disagreements, production-code changes, positive tests, a failing old-code/mutation test, object/build validation, commit and runtime acceptance where available. Never mark a feature complete merely because a register macro exists or its TODO disappeared.

## 3. Architecture and source map

| Component | Current responsibility | Main source anchors |
|---|---|---|
| VDP2 device | TVMD/EXTEN/TVSTAT/VRSIZE/HCNT/VCNT, CRTC, sync callbacks, field state | `src/mame/sega/saturn_vdp2.cpp`, `.h` |
| Legacy renderer | Register backing, VRAM/CRAM, all background drawing, rotation, windows, color operations | `src/mame/sega/saturn.cpp` |
| Normal planes | NBG0–NBG3 configuration and tile/bitmap dispatch | `vdp2_draw_NBG0` through `vdp2_draw_NBG3` |
| Rotation planes | Parameter decoding, coefficient fetch, cached source maps, transformed sampling | `vdp2_fill_rotation_parameter_table`, `vdp2_copy_roz_bitmap`, `vdp2_draw_rotation_screen`, `vdp2_draw_RBG0` |
| Sprite composition | VDP1 framebuffer interpretation, priority, window and color/shadow operations | `draw_sprites`, `vdp1_display_pixel`, `screen_update_vdp2` |
| Memory and derived state | Register/VRAM/CRAM handlers, palette rebuilds, cache invalidation and postload | `vdp2_regs_*`, `vdp2_vram_*`, `vdp2_cram_*`, `vdp2_state_save_postload` |
| Regression framework | Extracted production functions with stand-ins, full object compilation | `regtests/saturn/test_*.py`, `run_all.py`, `validate_build.py` |

Function names are the durable anchors; line numbers move as implementation progresses. A later device extraction may be useful, but it is not a prerequisite for correcting behavior and must not be counted as a hardware feature.

## 4. Feature-by-feature assessment

| Feature group | Already present | Missing, partial, or not qualified |
|---|---|---|
| Normal backgrounds | NBG0, NBG1, NBG2 and NBG3 enable/configuration and drawing paths | Exhaustive layer/color-depth/resource-conflict matrix; special-function behavior |
| Character backgrounds | Tilemap/page/plane addressing, pattern-name handling, character-size and flip paths | Per-layer format restrictions, supplementary fields, boundaries and address wrapping need dedicated image oracles |
| Bitmap backgrounds | Bitmap-size/map/palette selection; palette and direct-color drawing paths | Complete legal per-layer combinations and wrap/clip/zoom/window qualification |
| Color formats | Palette-based paths and RGB555/RGB888 helpers | This is not proof all 16/256/2048-color and direct-color combinations work on every eligible layer; a non-bitmap 2048-color diagnostic remains |
| Ordinary scroll/zoom | Scroll registers, coordinate increments and zoom drawing helpers | Fractional precision, wrapping and zoom limits need systematic verification |
| Line scroll/line zoom | Horizontal/vertical line-scroll and line-zoom table processing | All interval/combination/format interactions and raster writes are not covered |
| Vertical cell scroll | An implemented combined branch with table addressing and partial-clip fixes | Branch requires horizontal line scroll and excludes vertical line scroll and line zoom; unsupported combinations remain |
| Reduction enable | ZMCTL reduction bits are defined | Complete enforcement of reduction limits is not present |
| RBG0 | Rotation A/B parameter loading, transformed sampling and coefficient processing | Rounding, coefficient transitions, read-control latches and all parameter-mode combinations need qualification |
| RBG1 | Routed through the NBG0 configuration/rotation path | Resource conflicts, priority/window integration and cycle-pattern checks are incomplete; not equivalent to a separately qualified full RBG1 implementation |
| Rotation coefficients | VRAM and CRAM coefficient-source paths; coefficient-size/mode handling | Addressing, signed stepping, coefficient flags, line-color use and all modes need independent image tests |
| Rotation parameter switching | Multiple parameter paths and rotation-window preparation exist | Mode-3/no-transform path has a documented limitation; parameter switching/read-control edge cases remain |
| Screen-over processing | Repeat, transparent-outside, 512×512 restriction and OVPNRA/OVPNRB character pixels | Screen-over fixture coverage added; special-function metadata and linked/runtime qualification remain open |
| Back screen | Single-color and per-line color, DISP/BDCLMD handling and color offsets | Dedicated partial-update/table-wrap tests and the historical Biohazard symptom need verification |
| Line-color screen | `vdp2_draw_line`, table access and configuration fields exist | Ordinary postprocessing invocation is gated off; correct insertion into the color-calculation pipeline is incomplete |
| Mosaic | Bounds-aware helper and focused clipping tests exist | Production invocation is gated off; per-layer source sampling/composition and rotation behavior are not complete |
| Ordinary priorities | Layer priorities and eight sprite priority selectors feed ordered composition | Tie rules and all sprite types need exhaustive tests; final RGB output does not retain sufficient layer identity for all effects |
| Special priority | Register definitions and layer configuration fields exist | A complete SFPRMD/SFSEL/SFCODE-driven per-dot priority implementation was not found |
| Ordinary color calculation | Ratio and additive helpers, per-layer enables, sprite conditions and color offsets | Exact selection of eligible second image, rounding and interaction with windows/shadows are not fully qualified |
| Special color calculation | Register definitions and some related pattern configuration | Complete SFCCMD/per-dot special-function eligibility is missing/incomplete |
| Extended calculation / gradation | Control bits are described in the register comments | Complete EXCCEN, CCRTMD and BOKEN-related operation paths were not found; require explicit implementation audit and tests |
| Color offset A/B | Signed RGB offsets, clamps, enable/select handling and cached faded palettes | Mid-display changes and ordering relative to calculation and special effects need verification |
| Window 0/1 | Coordinate/table reads, inside/outside evaluation, AND/OR combination and per-line caching | Boundary/resolution combinations and differences between basic and rotation paths need dedicated tests |
| Sprite window | Control fields and limited sprite pixel rejection exist | Generic window evaluation uses window 0/1 but does not combine a complete sprite-derived mask; end-to-end support is incomplete |
| Color-calculation window | Some shared window infrastructure exists | A complete independently qualified calculation-only window/eligibility path was not established |
| Shadows | Normal-shadow and opaque-path MSB-shadow behavior exists | Alpha-path MSB shadows and underlying-layer eligibility are incomplete; code comments acknowledge this |
| VDP1 scanout integration | Normal/packed output, interlace caches, rotation input and HDTV replication; output-coordinate compositor | Full sprite-type/window/shadow matrix and hardware readout phases remain open |
| Raster effects | Clip-aware rendering; recent VDP1 active-erase callbacks force partial presentation | VDP2 register, VRAM and CRAM changes are not generally sequenced against already-presented output |
| VRAM | Allocated storage, CPU handlers, decode updates and cache invalidation | All VRSIZE/bank/partition/address-mask interactions need audit; physical access-slot effects and contention are incomplete |
| Cycle patterns | Presence checks for character/pattern-name access commands | Slot counts/order, bank ownership, bandwidth, fetch denial/corruption and CPU waits are not modeled comprehensively |
| CRAM | 4 KiB storage; 15-bit/24-bit palette paths; palette rebuilds and mode-0 palette mirroring | Mode-0 backing/read alias behavior is a TODO; byte-write behavior is unresolved. Mode 3 falls through to the 24-bit path and must not be certified as a legal mode |
| Registers | Backing register file mirrors, masked writes, decoded device status/control paths | Per-register masks, access widths, read-only/write-only behavior, reset values and latch times require a complete inventory |
| TV modes | Display enable, horizontal/vertical resolution and CRTC reconfiguration | Interlace half-lines, PAL, DOTSEL coordination and exclusive-mode timing retain explicit uncertainty |
| Counters/status | H/V latches, ODD state, V-counter table, TVSTAT behavior and external latch callback | Physical beam accuracy, wrap edges, exclusive modes and external sync qualification |
| External inputs | EXTEN fields, latch control and flags | External background/MPEG/genlock rendering is missing; actual external synchronization is not established as complete |
| Reset/save | Device fields and backing memories registered; decoded graphics/palette/rotation caches rebuilt after load | Full reset coverage, every derived cache and real MAME round trips mid-raster remain unqualified |
| Performance | Cached rotation maps, windows, palettes and decode invalidation | No current linked benchmark; large rotation maps and combined scroll/partial-update workloads remain risks |

## 5. What has actually been tested

The latest implementation baseline passed **23 Saturn regression scripts and eleven production object compilations**. That is the whole Saturn suite, **not 23 dedicated VDP2 tests**. This documentation audit does not claim a new linked build or hardware run.

| Test | Evidence provided | Important limit |
|---|---|---|
| `test_tvmd.py` | Actual reset/register/CRTC helper behavior using recording devices | Not physical timing or every TV-mode transition |
| `test_exten.py` | Actual reset/read/write and external latch callback | Not genlock, external video or physical beam verification |
| `test_vcounter.py` | Table equivalence, field-line indexing and counter encoding | Historical lookup equivalence is not silicon proof |
| `test_sync.py` | Production sync callback control flow and scheduling | Not real timer/CPU interrupt delivery or exact clocks |
| `test_cell_scroll.py` | Clip containment, table addressing and column-call counts | Nested renderer, hardware column width and unsupported combinations are not certified |
| `test_mosaic.py` | Production helper clipping/bounds | Helper is not enabled in the normal pipeline; alignment and multi-layer composition are not certified |
| `test_sprite_scanout.py` | 3,036 compositor/readout image cases across modes, clips and selected effects | Palette/window evaluation and devices are stand-ins; full shadow/window/color hardware behavior is not certified |
| `test_vdp1.py` | Additional rotation/field integration and erase-driven presentation sequencing | Primarily VDP1; the recording screen is not a complete VDP2 render/save round trip |
| SCU timer/IRQ tests | Related timing-consumer integration | Not a substitute for VDP2 raster accuracy |

Not currently established by dedicated end-to-end image suites: all NBG formats, all RBG modes, actual window logic combined with layer rendering, special priorities/calculation, line-color insertion, sprite-window masks, underlying-layer shadows, VRAM scheduling and mid-display CRAM changes.

Runtime acceptance from earlier work remains narrowly scoped to the user's AB2 boot/explosions, Power Drift cars and OutRun flashing observations. These are **not VDP2-wide acceptance**. The separately reported title/logo placement issue remains open and is not assigned to VDP2 without evidence.

## 6. Prioritized multi-level implementation checklist

### P0 — Establish trustworthy pixel and register baselines

- [x] **V2-A01** Audit both device and legacy-renderer ownership, rather than treating one file as the entire VDP2.
- [x] **V2-A02** Record active paths, gated helpers, source TODOs and test limitations in this report.
- [ ] **V2-A03** Build a complete register ledger against ST-058: offset, bit mask, access type/width, reset, latch boundary, active consumer, tests.
  - [ ] Distinguish defined-but-unused fields from implemented fields.
  - [ ] Separate prohibited combinations and undocumented aliases from legal features.
  - [ ] Reconcile RAMCTL, VRSIZE, TVMD/EXTEN and CRAM-mode behavior.
- [x] **V2-A04a** Add production bitmap/palette/window pixel fixtures: 7,680 images, two negative mutations.
- [ ] **V2-A04** Add extracted full-background/compositor image fixtures, with real production palette and window evaluation where practical.
  - [ ] NBG0–3, bitmap/cell, legal color formats, page/plane boundaries, flips and transparency.
  - [ ] Clipped updates versus an equivalent full-frame reference.
  - [ ] Layer-over-layer scenes preserving which source should win and which should blend.
  - [ ] Negative mutations for each newly covered behavior.
- [x] **V2-A05a** Correct mode-0 write broadcast and test legal word/longword lanes, independent reads and immediate/rebuilt palette agreement.
- [x] **V2-A05b** Preserve physical CRAM banks across mode changes and test coefficient reads.
- [ ] **V2-A05** Audit CRAM mode-0 storage/read aliases and legal word/longword writes before relying on the palette as an oracle.

### P1 — Correct composition and ordinary visual effects

- [x] **V2-C01b** Enforce normal-screen color-depth resource exclusions from ST-058 p.61.
- [x] **V2-C01a** Preserve decoded pixel coverage separately from RGB in rotation caches; verify opaque-black and transparent source dots.
- [ ] **V2-C01** Establish per-pixel source identity/priority/eligibility sufficient for correct effect selection.
  - [ ] Top image and eligible second image selection.
  - [ ] Same-priority tie order and priority-zero suppression.
  - [ ] All sprite types and palette/direct-RGB encodings.
- [ ] **V2-C02** Implement/qualify normal and MSB shadows across opaque and calculation paths.
  - [ ] SDCTL eligibility based on the actual underlying layer.
  - [ ] Sprite-window conflicts, transparent shadow codes and priority interactions.
- [x] **V2-C03a** Apply rotation/parameter windows on per-dot coefficient paths and preserve partial-clip source origins; add 9,216 image cases.
- [x] **V2-C03b** Preserve no-transform rotation windows and audit shortcut eligibility; test wrapper/cache configuration.
- [ ] **V2-C03** Complete window behavior.
  - [ ] Window 0/1 boundaries, line windows, AND/OR and disabled-window neutral values.
  - [ ] Sprite-derived mask as a real window input.
  - [ ] Calculation-only windows and rotation-parameter windows.
  - [ ] Partial clips, interlace and high/exclusive resolution coordinates.
- [ ] **V2-C04** Complete special priority and special color calculation.
  - [ ] SFPRMD, SFCCMD, SFSEL/SFCODE and pattern-name/dot attributes.
  - [ ] Eligibility before blending, rather than a late RGB-only approximation.
- [x] **V2-C05a** Separate sprite calculation eligibility from zero ratio; test all ratios/selectors and additive mode.
- [ ] **V2-C05** Qualify ordinary ratio/additive calculation and color-offset ordering.
  - [ ] Ratio extremes, integer rounding and overflow/clamping.
  - [ ] Correct second-image eligibility and sprite condition modes.
  - [ ] A/B signed offsets before/after each operation as specified.
- [ ] **V2-C06** Implement/qualify extended calculation, ratio-source selection and gradation controls.
- [ ] **V2-C07** Integrate line-color screen as a proper calculation input.
  - [ ] Single/per-line tables, enables, coefficients and ratio behavior.
  - [ ] Remove the production gate only after image tests prove placement.
- [ ] **V2-C08** Integrate mosaic per eligible layer.
  - [ ] Source-sample origin, horizontal/vertical sizes and partial clips.
  - [ ] Prevent mosaic from modifying already-composited unrelated layers.
  - [ ] Rotation constraints and scroll/window/calculation combinations.
  - [ ] Remove the production gate only after qualification.

### P2 — Scroll and rotation completeness

- [ ] **V2-S01** Qualify ordinary fractional scroll/zoom and implement reduction-enable limits.
- [x] **V2-S01b** Preserve fractional bitmap scroll phases and line-scroll table fractions; tile sampling remains open.
- [x] **V2-S01a** Enforce documented ZMCTL restrictions on paired NBG2/NBG3 screens.
- [ ] **V2-S02** Complete line-scroll, vertical line-scroll, line-zoom and vertical cell-scroll combinations.
  - [x] **V2-S02b** Dispatch standalone vertical cell scroll and restore column-pass scroll state; keep unqualified combinations excluded.
  - [x] **V2-S02a** Correct packed interval addressing, partial-clip containment, unsigned line zoom and descriptor restoration; retain equivalent-entry batching.
  - [ ] Table stride/interval, simultaneous NBG0/NBG1, screen-left anchoring and wrapping.
  - [ ] Correct per-dot/column behavior without an uncontrolled nested-render cost.
- [ ] **V2-R01** Implement and qualify screen-over-pattern mode using OVPNRA/OVPNRB. Base pixel path implemented; shared special-function and runtime qualification remain open.
  - [x] **V2-R01a** Decode and composite repeated OVPNRA/OVPNRB character pixels, with bounded per-pass decoding and clip/dispatch regression coverage.
- [ ] **V2-R02** Qualify rotation A/B parameters, fixed-point precision and coefficient tables.
  - [x] **V2-R02a** Validate packed parameter fields and correct Px sign extension; exercise signed short/long coefficient screen-over boundaries.
  - [ ] VRAM/CRAM, short/long coefficient entries, signed increments and flags.
  - [ ] Repeat, transparent and 512×512 screen-over modes.
- [ ] **V2-R03** Complete parameter-selection modes and read-control behavior.
  - [x] **V2-R03a** Select mode-2 A/B before coverage/composition and enforce B per-line coefficients when A is per-dot.
  - [ ] Window selection with and without a geometric transform.
  - [ ] Coefficient-based switching and line-color interaction.
- [ ] **V2-R04** Qualify RBG1/NBG0 sharing, resource restrictions and rotation caches.
  - [x] **V2-R04a** Separate inherited normal-scroll state, select RBG1 output-window controls and enforce dual-rotation screen exclusions.
  - [x] **V2-R04b** Watch full format/size-dependent character extents and wrapping accesses for rotation-cache invalidation.

### P3 — Raster state and VRAM bus behavior

- [ ] **V2-T01** Preserve scanned output before render-affecting register/CRAM/VRAM writes.
  - [ ] Define latch granularity from primary documentation, not an unconditional flush on every write.
  - [ ] Verify memory changes, color offsets, windows, scroll and priority changes independently.
  - [ ] Ensure active VDP1 erase-triggered updates do not duplicate or lose rendering.
- [ ] **V2-T02** Implement bank/slot-aware cycle-pattern validation and fetch behavior.
  - [ ] Bank partitioning, access-command counts/order and screen-mode bandwidth.
  - [ ] RBG1 and coefficient/table fetch restrictions.
  - [ ] CPU availability/contention and insufficient-fetch consequences, supported by hardware evidence.
- [ ] **V2-T03** Qualify VRAM size/address masking and cache invalidation for all consumers.

### P4 — Display timing and external interfaces

- [ ] **V2-H01** Qualify NTSC/PAL field lengths, half-lines, ODD and H/V counter wrap/latch edges.
- [ ] **V2-H02** Qualify interlace and exclusive modes, clock changes and SMPC DOTSEL coordination.
- [ ] **V2-H03** Audit external latch/sync flags and reset behavior against real callback timing.
- [ ] **V2-H04** Implement external-background/MPEG/genlock input and composition where supported.
  - [ ] Keep external-device input provisioning separate from the VDP2 mixer.
  - [ ] Explicitly identify any configuration for which the external source is absent.

### P5 — Save/reset, performance and acceptance

- [ ] **V2-Q01** Audit register, memory, decoded state and all derived caches across reset/postload.
  - [ ] Window/fade/rotation caches and any new per-pixel/raster state.
  - [ ] Mid-line and mid-field save/load with no stale picture or duplicate event.
- [ ] **V2-Q02** Link the focused Saturn/ST-V executable and run `-validate`.
  - [ ] Resolve the SDL/pkg-config dependency blocker; prior Debian fetch attempts failed.
- [ ] **V2-Q03** Run real MAME save/load and BIOS/Saturn/ST-V visual smoke tests.
  - [ ] Preserve user-accepted prior fixes; record the exact build and scene.
  - [ ] Obtain independent expected images or traces for the new VDP2 features.
- [ ] **V2-Q04** Profile before optimizing.
  - [ ] Large rotation maps and invalidation frequency.
  - [ ] Combined scroll effects, windows and repeated partial updates.
  - [ ] Prove image equivalence for every optimization.
- [ ] **V2-Q05** Investigate the separate title/logo placement report without assuming the responsible chip.
- [ ] **V2-Q06** Close historical game notes only with current reproducible evidence.

## 7. Recommended work order and acceptance gates

1. **Register/palette and pixel fixtures (A03–A05).** Needed to avoid “fixing” the compositor against an incorrect palette or mocked window oracle.
2. **Composition core, shadows and windows (C01–C03).** This enables reliable special-function, line-color and mosaic work.
3. **Special calculation and gated effects (C04–C08).** Do not simply turn on `TEST_FUNCTIONS`.
4. **Scroll combinations and rotation gaps (S01–R04).** In particular screen-over-pattern is a bounded implementation target.
5. **Raster-write and bus accuracy (T01–T03), with timing work (H01–H03) as needed.** Source the latch model before broad write-handler changes.
6. **External video and final qualification (H04, Q01–Q06).** Save/load, runtime and performance checks should also accompany earlier increments whenever a linked build is available.

An item closes only when its implementation and test evidence are recorded. Hardware-sensitive items may remain “implemented; qualification open” after the code lands. A passing extracted test is not a substitute for a linked game or real save-manager test.

## 8. Historical notes requiring care

The source lists examples involving Decathlete, dragndrm, Magical Drop logos, Dokyusei/dokyuif, Shienryu stage 2, Scud, window transitions, Batman Forever's Riddler scene, Radiant Silvergun, Biohazard and others. These are **historical investigation leads**, not freshly reproduced defects on the audited commit.

Two particularly misleading completion signals:

- “Mosaic missing” is not wholly obsolete: clipping in the helper was fixed, but its ordinary production integration remains disabled.
- “ODD/H/V counters not emulated” is too broad: counter/status code and regression fixes exist, while physical timing qualification remains open.

Do not delete old evidence merely to make the checklist appear shorter, and do not assign every title-position issue to VDP2 without tracing its source coordinates and composition.

## 9. Reference and evidence policy

Primary baseline: [Sega VDP2 User's Manual, ST-058-R2-060194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-058-R2-060194.pdf), plus relevant SDK supplements/bulletins. Existing section-specific audit notes are in [official_specs.md](official_specs.md).

Independent cross-check baselines already used in this project:

- Ymir revision `6d779960127ced72087a418c1daefc637d0aaa80` — device timing and software renderer.
- MiSTer Saturn revision `a95b085038ace57fa621558d60a7adc7a3c53f78` — VDP2 and VDP1 interface RTL.

This report audits local production code and existing test scope; it is **not** a fresh line-by-line comparison of the entire Sega manual against both independent implementations. Each future item must pin the actual source sections consulted and document disagreements rather than silently selecting a convenient emulator behavior.

## 10. Progress log

| Date | Change | Evidence | Status |
|---|---|---|---|
| 2026-09-15 | Initial VDP2 source audit and stable-ID tracker against `ad5ae529` | Both production components, renderer gates, selected function bodies and all current test descriptions inspected | Documentation baseline; no new VDP2 implementation or runtime acceptance |

For future rows: include checklist IDs, commit, tests/mutations, object/linked-build result, source references and any remaining acceptance gate.

# Saturn TODO Inventory — 2026-09-13 (post 07ee024a fix)

## V2-Q01a: deterministic startup and postload state separation — 2026-09-16

VDP2 startup now initializes external controls/status, counter samples, display
extents, VRAM size and DOTSEL state explicitly. Reset clears EXLTFG/EXSYFG while
retaining the counter samples until another latch. ST-058 section 2.5 defines
flag and latch behavior; pinned MiSTer a95b0850 resets TVSTAT in both reset paths
(VDP2.sv lines 3646/3795). Initial zero counter samples are a deterministic emulator
fallback, not a claim about unspecified physical power-on counter contents.

Driver postload now clears all transient composition/extended/gradation/capture
flags, the gradation selector and priority pass. This matters because capture
bypasses composition even when the ordinary active flag is false. Saved rotation
line-valid state and accumulators remain intact. Existing reconstruction rebuilds
all decoded VRAM bytes, invalidates character/rotation/window caches and refreshes
the palette. No new persistent state or timer rescheduling is introduced; MAME's
screen device already saves its geometry and partial-update timing state.

Validation: **39 regression scripts and eleven production object builds pass**.
The new fixture uses production field initializers against four poisoned storage
patterns and executes **64** full-VRAM postload passes. It checks byte order, dirty
notifications, palette refresh, idempotence, window cache invalidation, render-flag
reset and preservation of saved rotation history. Capture, priority, byte-order and
window-invalidation mutations compile and fail assertions. Existing 64 EXTEN cases
now verify both flags clear on repeated reset without changing latched samples.

**Q01 remains partial:** recording graphics/palette devices are not actual MAME
save-manager, screen-buffer or timer replay. Linked mid-field save/load, performance
and hardware qualification remain open. The restored workspace was reconciled with
the pushed e12e2cf7 checkpoint before this work; user logs and ROM archives were
retained, not added to this commit.


## V2-T02a: active cycle slots and bank ownership — 2026-09-15

The normal-screen cycle-command presence gate now ignores A1/B1 cycle registers
when their VRAM halves are not partitioned, and ignores T4–T7 in high-resolution
and exclusive modes. Banks assigned to an enabled RBG0 no longer supply normal
fetch commands; RBG1 excludes both B banks. RBG0 assignments do not reserve banks
when that rotation screen is disabled. Bitmap screens still need character/bitmap
commands but do not require pattern-name commands.

Primary evidence: ST-058 printed pp.29–32 and 149–150. Pinned MiSTer a95b0850,
VDP2.sv lines 668–709, independently selects A0/B0 registers for unpartitioned
memories and gates normal name/character accesses against enabled rotation owners.
This changes the existing layer-enable check, not the order or number of passes.

Validation: **38 scripts and eleven production object builds pass**. New
`test_vdp2_cycle_patterns.py` extracts the production helper and checks **1,048,576**
slot/partition/rotation-owner/bitmap configurations. Inactive-slot, partition and
RBG1-owner mutations compile and fail assertions. Existing reduction/color-resource
and RBG1 setup suites pass unchanged expectations.

**T02 remains partial:** this is command presence across eligible banks, not matching
each fetch address to a bank, required access counts, legal slot spacing, insufficient
fetch behavior or CPU contention. No hardware, linked-game or frame-time acceptance
is claimed. Those remaining items must not be inferred from the presence-gate tests.


## V2-T01a: preserve completed lines before state writes — 2026-09-15

Changed render-affecting register, VRAM and physical CRAM writes now preserve the
completed visible-line prefix **before** mutating storage or decoded state. The
VDP2 device's TVMD and VRSIZE handlers use the same preservation entry point before
updating display/geometry/address-size controls. CRAM change detection accounts for
mode-0 broadcasts to a different opposite bank and mode-2 physical-bank mapping.
Masked no-ops do not request a flush; reserved/read-only register storage is excluded.

This is a scanline-renderer correctness step, **not a hardware register-latch model**.
It preserves only lines before the current beam line, never guesses at current-dot
fetch completion. It checks device startup, visible-line bounds and display/back
output enable. MAME screen_device coalesces repeated prefix requests, including the
existing VDP1 erase-triggered partial updates; no new save state or per-write image
buffers are added. ST-058 chapter 2 supplies scan/display mode definitions; pinned
Ymir's VDP2DrawLine output ordering corroborates keeping completed rows independent
of subsequent memory/register writes, not exact latch/slot timing.

Validation: **37 scripts and eleven production objects pass**. New production write
handlers and preservation helper pass **2,592** beam/mask/display/back/startup/
erase/coalescing scenarios with a recording screen. A mode-0 opposite-bank-only
change also preserves the old prefix. Moving preservation after the write,
preserving the current line, or removing preservation all fail assertions. The
**3,072** TVMD cases additionally verify preservation sees old TVMD before a display
change and ignores zero-mask writes. Palette and rotation-cache suites remain passing.

T01 remains partial: current-line/dot preservation, exact per-register latches,
fetch-slot arbitration, CPU contention and linked runtime/save-load qualification
are not supplied by this change. Alternate Debian mirrors also fail TLS in this
sandbox; no linked MAME executable or successful runtime acceptance is claimed.


## Full-VDP2 scope: compositor, shadows and windows — 2026-09-15

Scope is now the entire VDP2 tracker, not just P2. This increment implements the
remaining major calculation operations rather than stopping at ordinary blending:

- **V2-C06a/C06b:** extended second/third/fourth-input calculation, source format
  and CCEN metadata, CRAM-mode restrictions, BOKEN exclusion, and gradation's
  designated-screen 2:1:1 horizontal input. A single raw-screen capture with a
  two-dot left halo preserves split clips without rendering every layer twice.
- **V2-C02a:** underlying NBG/RBG/back SDCTL selection; normal-shadow precedence,
  transparent-shadow TPSDSL, type-2–7 MSB self-shadow and sprite-window exclusion.
  Both opaque/calculated sprites share the same output path. Shadows occur after
  calculation/offset and no longer alter a raw input seen by a later higher layer.
  This explicitly corrects the earlier raw-history shadow-half implementation.
- **V2-C05c:** apply only the top screen's signed A/B color offset after calculation;
  keep raw background, back and sprite inputs unoffset. Table 12.1 high/exclusive
  restrictions reject palette second inputs in CRAM modes 1/2.
- **V2-C07b:** sprite line-color insertion, including CCRLB second-ratio selection.
- **V2-C03c:** calculation-only W0/W1/SW windows suppress calculation, not coverage;
  normal/sprite output windows now retain SW area polarity and include it in cached
  row evaluation and cache keys. Existing rotation/parameter windows are retained.

Primary evidence: ST-058 pp.190, 231, 236–242, 250–252, 256–260. Pinned MiSTer
(a95b0850) `ExtColorCalc`, `ColorCalcExtRatio`, output offset/shadow stages, and
pinned Ymir (6d779960) ordered composition/gradation provide independent checks.
**Document conflict:** table 12.2's mode-0 2:1:0 entry conflicts with figure 12.3's
fourth input. Implementation follows the figure's 2:1:1 and both references.
CRAM-1/2 fourth-palette restrictions follow the table; the references simplify this.
Gradation pixels 0/1 use Ymir's edge policy; outside-display inputs and prohibited
transparent gradation boundaries are not claimed hardware-qualified.

Validation: **36 regression scripts and eleven production object builds pass**.
Production helpers plus actual MAME blend/offset arithmetic pass 786,432 extended
format/enable/mode/ratio cases, 28,672 signed post-offset cases, 896 SDCTL identity
cases, 6,144 gradation capture/halo/rank/ratio/split-clip scenes and the existing
524,288 ordinary scenes. Eleven mutations fail assertions (including format,
extended enable, gradation weights/halo, offset ordering and SDCTL selection).
Sprite scanout adds 32,256 all-type shadow/CC/window images and 307,200 ratio/line
images. Actual palette/bitmap/window/cache fixtures pass 184,320 images; 16,384
W0/W1/SW control cases now also exercise calculation windows. Capture dispatch uses
controlled source screens in its oracle; it is not a linked-game acceptance test.

All new buffers/flags are derived render state, gated by the frame-active flag;
unchanged dimensions reuse allocations. The extra underlying RGB/metadata buffers
are allocated only for extended mode; the raw designated-screen buffer only for
legal gradation. No-effect frames preserve the legacy fast paths. Runtime frame
time, actual save-manager replay, timing/arbitration, external interfaces and the
remaining tracker qualifications are still open. **The whole VDP2 is not complete.**


## P2 dependency: ordinary raw-second-image composition — 2026-09-15

Normal, rotation and sprite output now share a bounded raw-source/ratio history.
The current calculated top uses the nearest covered raw second image, not the
already-calculated RGB displayed by that lower layer. CCRTMD selects the top or
second source's own CCR; disabled calculation does not discard that source's ratio.
Line-color insertion substitutes the designated line color and low CCRLB ratio
only for that top; it does not contaminate the candidate seen by a later layer.
The back screen initializes the candidate with high CCRLB. Ratio/additive arithmetic
uses the existing MAME primitives and the documented (31-r):(r+1) weights.

History is derived per clip, reused without reallocating unchanged dimensions,
and deactivated after the frame and on postload. No-CCEN frames retain the legacy
fast/cache routes; active composition forces normal point submission and bypasses
the rotation unity shortcut without recording source-cache construction as output.
Existing shadow gates now update displayed and raw RGB consistently, but actual
underlying-layer SDCTL eligibility remains unfinished. There is no new saved state.

Primary evidence: ST-058 printed pp.231, 235, 241–244 (top/second selection,
line insertion, ratio direction and CCRLB). Pinned Ymir 6d779960's layer-color
lookup and ordered composition independently corroborate raw-source selection;
no reference implementation was imported.

Validation: **36 scripts and eleven production object compilations pass**.
`test_vdp2_composition.py` checks **524,288** ordered-source scenes using the actual
production history helpers and MAME blend primitives against independent /32 RGB
math, all ratios, eligibility, line insertion, coverage omissions, shadows and split
clips; it also checks allocation reuse, resize and no-CC activation. All five
cumulative-result, wrong-ratio, line-history, disabled-ratio and shadow-history
mutations fail assertions. Active integration includes **153,600** sprite
ratio/selector/condition images (active/inactive and both ratio directions), normal
unit-step routing/raw-ratio recording, **16** rotation history images, and rotation
shortcut rejection. Existing sampling/priority/window suites remain passing.

**Tracker:** V2-C01c/V2-C05b ordinary raw-second selection and ratio provenance are
implemented/tested. This advances the R03 line-color dependency, not completion of
P2 or the parent C01/C05/C06 tasks. Extended three/four-image calculation, gradation,
layer-selective shadows, color-offset ordering, raster/fetch arbitration and linked
game/save-manager/performance qualification remain open. The history stores one
candidate, not enough for extended calculation. These fixtures are not linked-game
or hardware acceptance; active-path performance has not been benchmarked.


## P2 shared special priority and frame-pass scheduling — 2026-09-15

This supersedes the earlier missing-special-priority statements. SFPRMD modes 1/2
now replace only the low priority bit using the character/bitmap attribute and,
for mode 2, the raw dot's selected SFSEL/SFCODE match. Effective priority zero is
transparent, including cases where a register value of zero can produce priority
one. One-word names use PNC SPR, two-word names use bit 29, and bitmaps use BMPNA/B
bit 5. RBG1 shares NBG0's priority and special-function controls.

The shared decoder carries coverage, color-calculation eligibility, code match and
priority independently in private metadata. Normal and rotation samplers filter
against the current frame priority pass before composition; priority-zero dots are
suppressed at decoding. This also applies to OVPNRA/B patterns and preserves color
offset/calculation eligibility. Rotation layers needing priority attributes use the
bounded direct source path even when color calculation is disabled.

Frame dispatch visits each special-priority layer in at most its two possible
nonzero priority passes, not all seven. Ordinary layers retain their single-pass
routing. Existing equal-priority order (NBG3, NBG2, NBG1, NBG0/RBG1, RBG0, sprites)
is unchanged. The pass number is ephemeral render state, reset after screen update;
no new persistent hardware state or save-manager registration is introduced.

Primary evidence: ST-058 printed pp.228–230 and pattern/bitmap attribute layouts
(chapter 4; bitmap priority bits also listed on p.344). Pinned Ymir 6d779960
`VDP2FetchPixel` corroborates replacement of the LSB and attribute-plus-code gating.
RGB per-dot priority and SFPRMD mode 3 are prohibited: the former has a zero-LSB
fallback, and the latter retains ordinary priority. Reserved-mode fixture cases
check that software fallback, not undocumented silicon behavior.

Validation:
- **294,912** normal tile/bitmap/combined-scroll images with mixed special priority
  and color modes, priority-zero/pass filtering, metadata preservation, windows,
  split clips and a priority-only unit-transform dispatch assertion.
- **107,520** special-function rotation images across all maps, bitmaps, OVPNRA/B,
  RBG0/RBG1 controls, name/character sizes, coverage and ratio/additive output.
- **98,304** all-layer metadata cases cover NBG0–3/RBG0/RBG1 register-bank selection,
  all priority bases, both code banks and all 256 palette dot codes.
- New `test_vdp2_priority_dispatch.py`: **131,072** actual frame-dispatch scheduling
  and opaque-composition images, using controlled source dots and an independent
  highest-(priority,tie-order) oracle. It also checks bounded pass counts, blank
  display and pass-state cleanup. Real decoding/filtering is exercised separately
  by the normal/rotation suites, not substituted into this scheduling fixture.
- Missing attribute/code gates, missing priority-zero suppression, wrong LSB
  scheduling and changed layer order all compile and assertion-fail.
- **35 regression scripts / eleven production objects pass**; external log:
  `/home/user/.cache/saturn/p2-special-priority-validation.log`.

**Still open:** priority-aware general/extended color composition, raster/fetch
arbitration and linked game/save/load/performance qualification. Special-priority
implementation is no longer missing, but these tests are not hardware or linked
runtime acceptance and do not close all P2 parent tasks.

## P2 shared special color-calculation eligibility — 2026-09-15

Implemented SFCCMD eligibility in the shared dot/pattern sampler: per-screen,
per-character/bitmap attribute, per-dot SFSEL/SFCODE match and color-data MSB.
One-word names use the PNC supplement; two-word names use bit 28; bitmap modes
use BMPNA/B bit 4. NBG0/NBG1/NBG2's previously truncated PNC assignment is corrected
to the actual SCC bit. RBG1 selects NBG0's controls; RBG0 selects its own controls.
Palette mode 3 consults CRAM's MSB (including CRAO and CRAM-mode addressing), which
is absent from the RGB palette cache. RGB mode 3 always permits calculation.
RGB mode 2 remains prohibited; the code-7 fallback agrees with pinned Ymir but is
not a hardware guarantee for that invalid setup.

Eligibility is carried alongside coverage in private decoded-dot alpha metadata:
zero is uncovered, FE/FF are covered with calculation disabled/enabled. Final
composition restores opaque alpha, and normal color-offset processing preserves
this metadata. Disabled calculation draws the covered source dot normally; it does
not make it transparent or insert line color. General/extended composition is not
replaced by this eligibility change.

Normal special-calculation layers use the bounded fractional sampler, including
otherwise-unit transforms. Rotation layers with special calculation bypass the
RGB-only source cache and decode output source samples directly, memoizing repeated
coordinates. Shared map lookup now handles all 16 rotation planes. OVPNRA/B uses
the same one-word attribute and dot-code logic, independently of ordinary map name
size. Ordinary non-special rotation cache paths are retained. No new persistent
hardware state is added and no whole-map special-calculation cache is constructed.

Primary evidence: ST-058 pattern-name layouts/attributes (chapter 4), bitmap SCC
bits (printed p.345), special function codes (section 10.3), and SFCCMD rules
(printed pp.245–247). Pinned Ymir 6d779960 `VDP2FetchPixel` independently checks
attribute/code/MSB eligibility and treats RGB mode 3 as enabled.

Validation: **110,592** normal tile/bitmap/combined-scroll images now cover legal
special modes, name/bitmap attributes, both code banks, CRAM modes, line color,
coverage, split clips and metadata retention through a controlled color-offset
stand-in. **39,936** additional rotation tile/bitmap/all-map/screen-over images cover
RBG0/RBG1 sharing, one/two-word names, 8/16-dot cells, coverage and ratio/additive
output. An intentionally unusable 1×1 RGB cache verifies the direct source path.
Attribute, code-bank, CRAM-MSB and lost-metadata mutations compile and assertion-fail.
**34 scripts / eleven production objects pass**, with the external log at
`/home/user/.cache/saturn/p2-special-color-validation.log`.

**Still open:** per-dot special priority, priority-aware general/extended composition,
raster/fetch arbitration and linked game/save/load/performance qualification. This
implements special color-calculation eligibility, not all of C04 or all of P2.

## P2 rotation sprite-window selection and combined qualification — 2026-09-15

RBG0/RBG1 output windows and RPMD 3 parameter selection now combine W0, W1 and
the sprite window, including independent area bits and OR/AND control. Previously,
SWE without W0/W1 was treated as a constant rather than a framebuffer mask.
Unit-transform RBG0 draws with sprite windows no longer take the normal-renderer
shortcut, which would bypass the rotation window implementation.

The sprite mask comes from the displayed VDP1 framebuffer MSB through the existing
scanout helper: display-bank selection, packed formats, rotation and field addressing
are retained. ST-058 pp.187–188 restrict this to SPWINEN, palette-only SPCLMD=0 and
types 2–7. Nonzero color data with MSB set also belongs to the mask, not just 8000H.
A bounded derived row cache avoids repeating scanout/rotation setup for every window
query. It is invalidated for partial renders/register writes and explicitly on
postload; no new persistent hardware state is asserted. Ordinary NBG/sprite-layer
window integration and color-calculation windows remain separate C03/C05 work.

Validation:
- **1,376,256** sprite-window pixels through production framebuffer scanout, covering
  display banks, modes, high resolution, interlace, field buffers, type/enable/color
  gating and bounds. Existing **3,036** sprite images and **38,400** ratio images pass.
- **4,194,304** RBG0/RBG1 output-window pixels and **16,384** complementary A/B
  parameter-window pairs, including all W0/W1/SW enable/area/logic combinations.
- **33,024** images run production rotation and production window decisions together,
  with and without transforms, coverage, ratio/additive blending, mosaic, RBG1
  sharing and split clips. Rectangle inputs and the mask are controlled stand-ins;
  actual mask scanout is tested separately above.
- Inverted framebuffer-MSB and ignored sprite-window mutations compile and
  assertion-fail. **34 scripts / eleven production objects pass** via
  `validate_build.py`; external log `p2-sprite-window-validation.log` in the cache.

R02's repeat/transparent/fixed-512 leaf is reconciled with existing signed-boundary
image coverage; R03's transformed/untransformed window leaf now has combined image
coverage. Parent completion is **not** claimed: R01 shared special-function metadata,
general/extended composition, raster/fetch arbitration and linked game/save/load/
performance qualification remain open. These tests are not silicon certification.

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


## VDP2 rotation coverage update — 2026-09-15

Rotation caches now distinguish opaque black from transparent pixels using existing
MAME RGB alpha metadata. 360 new production bitmap-to-rotation images and independent
RGB-zero/opaque-clear mutations validate the correction. All 27 scripts/11 objects
pass; full composition and runtime acceptance remain open. See the VDP2 tracker.


## VDP2 composition update — 2026-09-15

Sprite CCRT=0 now calculates as a valid ratio; MSB eligibility is separate from
ratio data. 38,400 new cases plus 3,036 existing scanout cases pass with the actual
blend-level helper; previous code fails. All 25 scripts/11 objects pass. See
`regtests/saturn/vdp2_completion.md`; full composition and runtime acceptance remain open.


## Current workstream — VDP2

The source-audited feature matrix and prioritized, stable-ID checklist are now in
[regtests/saturn/vdp2_completion.md](regtests/saturn/vdp2_completion.md).
Use that report to track VDP2 implementation, tests and hardware/runtime acceptance;
older dated notes below are historical. No new emulation change in this audit.


## Update — 2026-09-15: active-display erase

Manual/one-cycle erase now follows presented scanlines, with saved progress and
primary-defined display limits. One-cycle erase owns the displayed bank, not the
new draw bank. 180 new cases, three failing mutations, 23 passing scripts/11 objects.
Within-raster arbitration, real save/load and runtime/performance qualification
remain. See `regtests/saturn/vdp1_completion.md` for source disagreements and limits.


## Update — 2026-09-15: progressive VBlank erase

VBlank erase now has a saved partial-row cursor, remaining budget and raster-level
progress; only the residual quota is flushed at field end. 552 new cases and two
negative mutations validated; all 23 regression scripts/11 objects pass. Active
manual erase and within-raster arbitration remain open. See
`regtests/saturn/vdp1_completion.md` for source discrepancies and acceptance limits.


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


## DMA forced-stop feature — 2026-09-14

Implemented the previously unmapped DSTP command with cancellation/held-trigger/
restart coverage (2,321 cases). CPU DMA only; DSP engine unchanged. Stop latency
and actual game compatibility still require runtime validation. The broader
remaining-blocker plan is in `regtests/saturn/game_blockers.md`.

## CD component build validation — 2026-09-14

Fixed CD HLE include order and added both CD translation units to routine checks.
All thirteen scripts/eight objects pass. CD behavior is unchanged; actual disc
access, authentication, audio and BIOS/game execution still need runtime validation.

## Wider driver/DCC build validation — 2026-09-14

Normal validation now compiles six objects, including Saturn console, ST-V and
DCC. Fixed DCC/ST-V include order; generated layouts remain temporary. All thirteen
scripts and six objects pass. No hardware behavior was changed, and a linked
executable/full dependency and runtime validation are still pending.

## DMA control-register audit — 2026-09-14

Existing increment, mode/update and enable/GO decoding passed 13,824 new cases,
with four failing test-only mutation controls. No production change needed.
Register-to-start dispatch is covered; real MMIO-to-transfer/IRQ execution and
writes to active channels remain unvalidated.

## DMA address-register width update — 2026-09-14

Programmed DxR/DxW addresses now retain only bits 26:0, not cache-alias bit 29,
per Sega and Ymir/Mednafen/MiSTer. Extracted lambdas pass address/count readback
coverage with two failing pre-fix controls. Register-update overflow, full MMIO
routing and runtime CPU/cache behavior are not established by this correction.

## A-Bus interrupt mask update — 2026-09-14

Fixed reversed IMS15 polarity using ST-097 and Mednafen; the pinned Ymir condition
disagrees with the manual. Added arbitration, acknowledgement and register-write
coverage with a failing pre-fix control. Full external acknowledge cycles, input
sampling and actual SH-2/CD/game behavior still require runtime validation.

## A-Bus refresh register update — 2026-09-14

AREF now resets to 0x10 per Sega's later erratum and stores only defined bits 4:0.
New register/reset/static-decoder coverage passes with two failing pre-fix controls.
This corrects stored configuration, not physical refresh timing: AREF is not yet
consumed by the bus model. Existing static wait approximations remain unvalidated
against hardware; no game/performance benefit is claimed.

## Held DMA trigger audit — 2026-09-14

Existing external-event hold behavior passed 924 new scenarios, including one-slot
restart and suspended level 0. Added event-filter extraction and five failing
mutation controls; no production change. ST-210/Mednafen corroborate holding;
Ymir's pinned external-trigger path differs. DxGO, held-state reset/save-load and
real scheduler timing remain open.

## DMA arbitration update — 2026-09-14

Fixed two-channel preemption suspending the wrong channel, and made halt callback
handoff consistent with the existing direct/indirect model. 64 supported overlap
scenarios pass through resume/completion, cross-checked against documented priority
and Ymir/Mednafen. Exact physical bus timing and unsupported overlaps remain open.

## Indirect DMA count update — 2026-09-14

Corrected indirect counts to twenty bits on every channel, with zero meaning
1 MiB, cross-checked against Ymir/Mednafen and MiSTer width. 54 legal two-descriptor
chains pass through completion. This extends the earlier direct-only coverage;
full DMA arbitration/timing and unusual descriptor/transfer cases remain open.

## C-Bus mirror decode update — 2026-09-14

SCU now recognizes `0x07xxxxxx` high work-RAM mirrors, consistent with Saturn/ST-V
address maps and Ymir/Mednafen. 768 classification checks and 2,304 direct DMA
scenarios pass. Full DMA timing/indirect-chain validation and precise primary
mirror-aperture documentation remain outstanding.

## TVMD startup/reset update — 2026-09-14

TVMD and decoded display/interlace/resolution controls now initialize before the
startup clock notification and clear on device reset, following ST-058 §2.4 and
Ymir/Mednafen. 3,072 scenarios pass; complete runtime/reset wiring and the wider
register/status initialization audit remain pending.

## EXTEN reset update — 2026-09-14

Fixed stale decoded EXTEN bits after reset, following ST-058 §2.5 and cross-checks
with Ymir/Mednafen. 64 read/write/reset/latch scenarios pass. This is an EXTEN
coherence fix, not completion of the wider VDP2 power-on/reset or lightgun audit.

## Double-density counter encoding update — 2026-09-14

The documented double-density bit layout is now implemented and cross-checked
with Ymir/Mednafen: field count in bits 9:1 and inverse ODD in bit 0. 47,016
V-counter checks pass including independent encoding and external-latch storage.
This supersedes earlier approximate-encoding notes below only for this mode;
rollback thresholds, field phase and non-interlace discrepancies remain open.

## Timer-0 implementation update — 2026-09-14

The compare-zero/increment-order issue identified below is fixed and tested:
zero at VBlank-OUT, positive compares after HBlank increment, TENB-gated counting.
8,192 two-frame callback scenarios pass. Earlier statements that timer-0 ordering
is still next are superseded by this update; exact CRTC phase, register-write
side effects and full timer-1 mode behavior remain open. See the current report
in `regtests/saturn/README.md` rather than interpreting historical DONE labels as
hardware validation.

## Timer-1 implementation update — 2026-09-14

The stopped-only HBlank reload issue below is now fixed and regression-tested
against ST-210 item 31, with Ymir/Mednafen cross-checks. 1,024 reload scenarios
plus gating/mask tests pass. Timer-0 ordering, full T1MD interrupt semantics and
hardware clock-rate validation remain open; this is not a blanket timer DONE.

## Primary-document audit update — 2026-09-14

[`regtests/saturn/official_specs.md`](regtests/saturn/official_specs.md) now records
exact sections/pages read from the SDK hardware manuals and technical bulletins.
It reopens timer-0 compare ordering, timer-1 running/reload semantics, interlaced
counter encoding, and fractional/combined cell scroll. These are not resolved by
the safety fixes below. The linked manifest indexes 103 PDFs; it is not a claim
that all documents were read.

## Current-branch follow-up — 2026-09-14

The historical DONE labels below describe prior implementation work, not proof
of hardware accuracy. See `regtests/saturn/README.md` for reproducible tests and
pinned reference notes. Line numbers below belong to the inherited snapshot.

- **VDP2/SCU HBlank delivery:** corrected missing horizontal edges during VBlank;
  the slave SH-2 HBlank IRQ remains VBlank-gated. 72 callback configurations pass.
- **Mosaic safety:** bounded partial blocks to the clip rectangle; 16,384
  sanitizer-backed configurations pass. Mosaic/line-screen compositing is still
  gated and is **not** marked implemented.
- **Vertical cell-scroll clipping:** preserve caller limits, skip wholly clipped
  columns and empty clips, retain screen-based table indices. 21,312 sanitizer
  configurations pass; inherited code fails clip containment. The eight-dot
  width remains unchanged pending hardware verification.
- **V counter double-density safety:** convert doubled screen rows to field
  lines before the 313-row table lookup. The inherited getter produces an
  AddressSanitizer out-of-bounds read; the corrected getter passes exhaustive
  configured-frame lookup checks. Existing field-bit encoding remains approximate.
- **V counter table cleanup:** removed redundant fills and contradictory comments;
  all 2,504 table entries match the inherited implementation. This does not
  validate rollback thresholds against hardware.
- Complete `saturn.cpp` and `saturn_vdp2.cpp` translation units pass standalone
  syntax checks after correcting inherited include order. Full build/ROM testing
  and exact hardware timing validation remain pending.


Generated after SCSP 0-outputs regression fix. Tree boots saturnjp + aburner2 at 100% (28s). SCSP now has 0 TODO/FIXME.

## How to read

- **File:Line — text**
- **Refs**: which of 5 reference emulators (Ymir, MiSTer, mednafen, yabause, SaturnRecomp) already solve it, based on prior cross-checks and manual notes.
- **Tier**: 1 = CD/SCSP/SMPC functional, 2 = SCU/VDP accuracy, 3 = VDP1/VDP2 rendering edge cases, 4 = ST-V specific.

---

### 1. SCU — `saturn_scu.cpp`

- `7: TODO:` — file header placeholder, not actionable.
- `403: FIXME: should be /4 but saturn BIOS already disagrees` — DMA timing divisor? Needs HW test. Refs: MiSTer models /? Ymir? Unknown. Tier 2.
- `446: TODO: waitstate penalties needs HW tests` — ASR/AREF wait penalties. We already implemented MiSTer AnNW+3 formula in 2d0ed85c, but TODO remains. Refs: MiSTer solved, Ymir partial. Tier 2. **DONE in this branch — ASR0/ASR1/AREF at 05FE00B0/B4/B8, penalties AnNW+3, DMA hog via steal callbacks.**
- `517: TODO: overhead due of SDRAM refresh?` — DMA bus steal overhead. Tier 2. **DONE — dma_hog_bus with 1+penalty steal.**
- `636: TODO: check if other buses can be used` — DMA source/dest bus validation, we implemented No.01/02 in 6113d660 but TODO remains for other combos. Tier 2. **DONE — directional rules A-Bus read-only dest, VDP2 read-only source, SCU reg exclusion, DMA-illegal IRQ.**
- `648: TODO: reimplement me` — likely DSP? Needs context. Tier 2.
- `778: TODO: why guardherj sets up a 0x23000 transfer for the FMV?` — game-specific. Tier 3.
- `790: TODO: other rules still applies` — DMA illegal rules. Tier 2. **DONE — see above.**
- `903: TODO: actually reads as dword and writes as word for B-Bus transfers` — B-Bus width. Refs: Ymir? Tier 2.
- `910,930: TODO: reimplement me` — DSP/INT? Tier 2.

### 2. VDP2 — `saturn_vdp2.cpp`

- `7: TODO:` header.
- `112: TODO: PAL only 256 mode` — PAL 256-color? Tier 3.
- `217: TODO: version` — VDP2 version register. Tier 3.
- `221: TODO: probably akin to YM7101 equivalent on stock Saturn` — VDP2 dot clock? Tier 3.
- `260: TODO: interlace mode "eats" one line, should be 262.5` — interlace. Refs: Ymir handles, mednafen? Tier 2/3.
- `284: TODO: divider is always 8, need to compensate out of lack of MAME interlace support` — DOTSEL divider. Tier 3.
- `293: TODO: Unknown for Exclusive modes` — VDP2 exclusive. Tier 3.
- `307: TODO: guard against the wrong DOTSEL being configured from SMPC.` — SMPC DOTSEL validation. Tier 2. **DONE in this branch — guard added in reconfigure_crtc with m_dotsel_352 check (MiSTer/Ymir).**
- `319: TODO: this should just be reserved and return VRESO == 2` — VDP2 VRESO bits. We already mask VRESO in earlier commit 65937035? Check. Tier 2.
- `329: TODO: find a software that makes use of this` — unknown reg. Tier 3.
- `418: TODO: refine hblank/vblank positions` — H/V blank timing. Refs: Ymir has precise tables. Tier 2. **DONE — now uses Ymir/MiSTer BBd/BSy/VCS/TBd/LLn/ADp timings, VBI 225/241/257, VBE at 0=0x1FF, rollback 247=0x1EF.**
- `424: if (cur_h > visarea.right()) //TODO` — H counter vs visarea. Tier 3. **DONE — now uses m_hdisplay threshold.**
- `446: TODO: test says that second setting happens at 241, might need further investigation ...` — VDP2 line. Tier 3. **DONE — VBI at 241 for 240 mode.**
- `463: TODO: 263 & 313 needs to be static constexpr` — NTSC/PAL line counts. Tier 3 (trivial).
- `484: TODO: T0C in SCU seems to run even after this point` — SCU timer 0 vs VDP2. Tier 2. **DONE — sync_timer_cb now walks through VBlank lines and only flips ODD at last line, timer0 continues via HBlank.**

### 3. Saturn core — `saturn.cpp`

This file is huge (10k lines) and contains most VDP1/VDP2 legacy implementation (now split to stvvdp1/2 devices but still here for saturn).

- `8: @TODO List of things that needs to be implemented:` — top-level list, contains many of below.
- `45: TODO (VDP1):` / `77: TODO (VDP2):` — section headers.
- `85: scud zoom-in on melee attacks with pink backgrounds (TODO: reinvestigate this),` — game-specific VDP? Tier 3.
- `88: cfr. gpanicss gal select, one of the Wangan games (TODO: find which),` — Tier 3.
- `137: Framebuffer TODO:` — VDP1 framebuffer. Tier 3.
- `283, 407: TODO:` — placeholder.
- `322: TODO: stuff that should really be in VDP1` — code structure. Tier 4 (refactor, like issue #8915).
- `335: TODO: when Automatic Draw actually happens? Night Striker S is very fussy...` — VDP1 timing. Refs: Ymir has more accurate VDP1 timing. Tier 2/3.
- `346, 2305: TODO: temporary for Batman Forever, presumably anonymous timer not behaving well.` — anon timers. Tier 3.
- `443: TODO: edge triggered?` — IRQ edge vs level. Tier 2.
- `449: TODO: actually send a device reset signal to the connected devices` — reset. Tier 2.
- `4866: TODO: disable read control if these undocumented bits are on (Radiant Silvergun Xiga final boss)` — VDP2 undoc bits. Tier 3.
- `619: TODO: write-only regs should return open bus or zero` — VDP1 regs. Tier 3.
- `622: TODO: TVM & 1 is just a kludgy work-around, the VDP1 actually needs to be rewritten from scratch.` — VDP1 TVM. Tier 3/4.
- `7339,7340: TODO: vertical linescroll, linezoom` — VDP2 line scroll. Tier 3.
- `7396: TODO: + 16 for tilemap and char size = 16?` — VDP2 tile. Tier 3.
- `7423: TODO: needs layer bitmaps to be individual planes to work correctly` — VDP2 layers. Tier 3.
- `7625: TODO: not supported, cfr. VDP2_OVPNRA / VDP2_OVPNRB` — VDP2 rotation param window. Tier 3.
- `7673: TODO: nuke this spaghetti code` — VDP2 code quality. Tier 4.
- `8088: TODO: check cycle pattern for RBG1` — VDP2 RBG1. Tier 3.
- `8515: TODO: Cotton 2 enables mode 3 without an actual RP window enabled` — VDP2 mode. Tier 3.
- `8858,8865: TODO: mode 0 handling, byte writes are goofy` — VDP2. Tier 3.
- `9088,9392: TODO: Optimize / remove crap` — performance. Tier 4.
- etc — many rendering edge cases, mostly Tier 3.

### 4. CD Block HLE — `saturn_cd_hle.cpp`

- `26: TODO:` header.
- `185, 659, 993, 1043, 1485, 3792: FIXME` — various CD timing/buffer issues.
- `288: TODO: move out of here, breaks daytoncej boot` — CD HLE init. Tier 1 (but we already fixed CD timing in 9a970027/d8d80151).
- `392, 571, 591, 619, 653, 782, 787, 796, 819, 829, 867, 875, 1053, 1137, 1176, 1292, 1310, 1536, 1546, 1569, 1808, 1854, 1863, 1916, 1929, 1956, 1975, 2093, 2208, 2542, 3336, 4140, 4177, 4193` — ~40 TODOs covering seek timing, filter, buffer full, partition init, etc. Many already addressed in Tier1 CD commits (88/89). Remaining: MPEG cart integration (done in 79), MP3, etc. Tier 1/2.

### 5. DCC — `saturn_dcc.cpp`

- `11: TODO:` header.
- `114: TODO: 0xff rather than 0x00 for irqline == 0?` — DCC IRQ. Tier 2.

### 6. ST-V — `stv.cpp`

- `11: TODO:` header.
- `121,124,218,558,1207,1239,1374,1422,1434,2031,2133,2134,3432,3769,3875,3891,3911,3932,3955,4194: TODO` — ST-V specific: SCSP reset line, RAX->SCSP, coin error, EEPROM defaults, etc. Many ST-V drivers have similar SCSP mirror fix already done in a9c5cfa7. Tier 2/3.

### 7. Console driver — `sat_console.cpp`

- `16,407: TODO:` headers.
- `550: TODO: Bug! accesses this one, if returning 0 the SH-2 hard-crashes. Might be an actual bug with the CD block.` — A-Bus dummy. We already return -1. Tier 2.
- `663: TODO: if you change the driver configuration then NVRAM contents gets screwed, needs mods in MAME framework` — NVRAM. Tier 4 (framework).
- `821: TODO: 3D Lemmings bogusly enables TH Control mode, wants this to return the ID, needs HW tests.` — SMPC TH control. Refs: Ymir handles? Tier 2.

---

## Work List ordered by reference coverage (5 refs)

We order by how many of Ymir/MiSTer/mednafen/yabause/SaturnRecomp already solve it (higher first = easier to port).

### Tier 1 (CD functional — mostly done)

- CD seek timing, SCDQ periodic, filter invert — DONE (88/89)
- MPEG cart — DONE (79)
- SCSP DMA burst + DGATE + wrap — DONE (2aedb4de)
- SCSP EG — DONE (9c2774f9)
- SMPC RTC battery — DONE (c5c90716)
- SCSP re-clock SAMPLE_CLOCKS — DONE (9cfda641)

Remaining CD TODOs (low ref coverage):

- `saturn_cd_hle.cpp:2542` MPEG ROM retrieval — needs MPEG cart ROM dump (Tier 1, 1 ref: Ymir has MPEG)
- `saturn_cd_hle.cpp:2208` how to actually read? — CD sector read path

### Tier 2 (SCU/VDP2 timing, interrupts)

High coverage (4-5 refs solve):

- VDP2 H/V blank positions, V counter rollback (saturn.cpp @TODO list, vdp2.cpp:418) — Ymir + MiSTer + mednafen have precise tables (5/5). **Next candidate**.
- SCU timer0/1 semantics (saturn.cpp: timer0 fires at HBlank-In, T0C=0 timing, timer1 0=512) — Ymir + MiSTer + mednafen (5/5). We have partial in scu but TODO remains.
- IMS reset at vector fetch — DONE (c19e25f8)
- SCU waitstate penalties (scu.cpp:446) — MiSTer has formula (2 refs: MiSTer, Ymir partial)
- DOTSEL guard (vdp2.cpp:307) — Ymir + MiSTer (2-3 refs)
- SMPC TH control mode (sat_console.cpp:821) — Ymir has handling (1-2 refs)

Medium coverage (2-3 refs):

- SCU DMA bus checks (scu.cpp:636, 790) — we did 6113d660 but TODO remains
- DCC irqline 0xff vs 0x00 (dcc.cpp:114) — Ymir?
- B-Bus dword read / word write (scu.cpp:903) — needs HW test

Low coverage (0-1 ref, needs HW tests):

- guardherj FMV transfer size (scu.cpp:778)
- SDRAM refresh overhead (scu.cpp:517)

### Tier 3 (VDP1/VDP2 rendering edge cases)

Mostly 0-2 refs, game-specific, long tail:

- VDP1 automatic draw timing (saturn.cpp:335) — Night Striker S fussy
- VDP1 framebuffer clear on VBE (saturn.cpp: vblank_line+1)
- VDP2 line scroll / line zoom (saturn.cpp:7339-7340) — Batman Forever Riddler stage
- VDP2 rotation parameter window (saturn.cpp:7625)
- VDP2 layer bitmaps as individual planes (saturn.cpp:7423)
- Pretty Fighter X, Game Tengoku shadows, etc.

### Tier 4 (Refactor / framework)

- VDP1/VDP2 code structure split across saturn_state and stvvdp1/2 devices — issue #8915 closed but code still split (needs refactor, no functional change)
- NVRAM config change bug (sat_console.cpp:663) — framework
- TODO: nuke spaghetti, optimize, etc.

---

## Next actionable (proposed order)

1. **VDP2 H/V blank + V counter rollback** — 5/5 refs have it, we have partial but TODO: refine hblank/vblank positions (vdp2.cpp:418) and saturn.cpp @TODO list. Implement Ymir's vpos table (line 0=0x1ff VBE, line 1=0, line 241=0xf0 VBI, line 247=0x1ef rollback, line 263=0x1ff).
2. **SCU timer0/1** — 5/5 refs, timer0 TENB gating, HBlank-In firing, timer1 0=512 and backwards counting from 0x6b.
3. **SCU waitstate penalties** — finish ASR/AREF implementation (scu.cpp:446) with HW tests from MiSTer AnNW+3.
4. **SMPC TH control** — 3D Lemmings ID return (sat_console.cpp:821).
5. **CD HLE MPEG ROM retrieval** — needs actual MPEG ROM.

All above are Tier 2, high ref coverage.

## Build-validation follow-up — 2026-09-14

All six regression scripts plus actual object compilation of the three changed
C++ files pass (`regtests/saturn/validate_build.py`). This is stronger than the
syntax-only checks above, but still not a linked MAME build. Missing development
packages and failed sandbox package access block full-build validation; ROM
runtime/save-state/performance checks remain outstanding.


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

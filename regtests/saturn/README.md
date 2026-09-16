# Saturn / ST-V reference audit — 2026-09-14

## Build correction: priority initializer narrowing — 2026-09-16

Explicitly convert all five masked priority-register expressions to unsigned in
`vdp2_special_priority_pixel`. The underlying 16-bit registers promote to `int`;
list-initializing the unsigned array from these runtime expressions caused the
user's production `-Werror=narrowing` build failure. Values remain 0–7 and rendering
semantics are unchanged. Previous local object builds emitted these five warnings
but did not reject them; their reported success did not establish compatibility
with the production warning policy.

`validate_build.py` now enables `-Werror=narrowing` for every production object.
All **43 scripts and eleven production object builds pass** with that flag. This
fix addresses the reported diagnostic, not full linking or runtime acceptance.


## V2-T03e: legacy cell-map physical addressing — 2026-09-16

Legacy tilemap base calculation now uses the configured 512 KiB/1 MiB byte mask,
instead of forcing 512 KiB under a historical game-specific comment. Both one-word
and two-word pattern-name fetches also mask their complete final longword index.
The existing map/page geometry, name decoding and character rendering are unchanged.
Rotation-cache map watches use the same physical bases and complete plane lengths;
the redundant extra-page extension is removed. A defensive wrapped-range fallback
covers the physical allocation. The separate character watch is unchanged.

Primary evidence: ST-058 pp.82–83, table 4.8, gives map selection address units for
one/two-word names, 8/16-dot characters and each legal plane size, and explicitly
omits the highest used bit only at 4 Mbit. Capacity rules are pp.26–28. The pinned
Ymir shared physical-address wrapping cross-check remains limited to 512 KiB;
1-MiB address expectations here are derived from Sega's map table.

**43 scripts and eleven production object builds pass**. New fixture executes the
production base loop, pattern-name read expressions and map-watch setup against
independent page-byte/alignment arithmetic: **24,576** both-size/name/tile/plane/
4-or-16-map/register configurations and **3,442,688** fetch probes. Legal aligned
planes do not straddle physical memory; extra synthetic offset probes separately
exercise defensive final-index wrapping. Base-mask, final-fetch-mask and oversized
watch mutations compile and fail assertions. Geometry and memory are controlled;
this is not a complete legacy tile-renderer image or linked-game test.

T03 remains partial for character-pixel fetch/decode tails, including physical-end
wrapping in retained render helpers. Hardware fetch timing, linked save/load/game
acceptance and performance qualification remain open. No measured speedup claimed.


## V2-T03d: CPU VRAM physical aliases and write coherence — 2026-09-16

CPU VRAM read/write handlers now normalize the longword offset to the configured
512 KiB/1 MiB physical capacity. In 4-Mbit mode the upper half of the mapped aperture
therefore aliases lower memory instead of acting as independent storage. Writes
normalize before the changed-data comparison and completed-line preservation, and
before updating the decoded byte buffer, decoder dirty indices and A/B map/character
cache watch ranges. Partial-write merging and existing conservative cache dirtiness
(including unchanged writes) are preserved. The unused upper backing allocation is
not erased, and this does not redefine behavior of changing VRSIZE after loading RAM.

Evidence: ST-058 section 3.1 pp.26–28 defines physical capacities/address maps and
requires setting VRAMSZ before writing VRAM. Pinned Ymir 6d779960's shared
MapVRAMAddress/ReadVRAM/WriteVRAM implementation corroborates modulo-512-KiB storage
access; its 1-MiB support remains TODO. The 1-MiB case follows the Sega capacity map.
These references do not qualify exact CPU bus turnaround, open-bus behavior or
contention. This change makes CPU accesses coherent with the implemented physical
wrapping model, not a new bus-timing claim.

**42 scripts and eleven production object builds pass**. New production-handler
fixture: **1,296** capacity/boundary/alias/mask/data/A-B/name-character-watch cases.
It checks reads, merged longwords, big-endian decode bytes, unchanged opposite-half
storage, decoder dirty indices, exact cache selection and old-state visibility at
the preservation callback. Read-mask and write-mask removal mutations compile and
fail assertions. Existing **2,592** raster-write and **20,320** character/bitmap
cache-invalidation cases pass. Screen and graphics-decoder stages are recording
stand-ins, not a linked CPU/game/save-manager replay.

T03 remains partial: legacy cell-map/character fetches still need a complete
physical-size audit. Linked runtime, display fetch arbitration and performance
qualification remain open; no frame-time or game-compatibility acceptance claimed.


## V2-T03c: rotation and retained line-color table wrapping — 2026-09-16

The raw rotation-parameter loader now masks every final longword index to the
configured 512 KiB/1 MiB capacity. Previously it always used the full 1 MiB backing
allocation, including when reading a table through a 4-Mbit high-address alias or
across the physical end. A/B selection, field widths/sign extension, ignored bits
and RPRCTL/latch behavior are unchanged. The retained additive line-color renderer
now applies its configured physical byte mask after adding the row offset, rather
than wrapping at the full backing-buffer length. Its color operation and current
interlace indexing are unchanged.

Primary evidence: ST-058 pp.26–28 memory capacity/map; p.159 explicitly ignores the
rotation-table address MSB at 4 Mbit and defines A/B address selection; p.174 gives
the same capacity rule for LCTA. Pinned Ymir 6d779960's shared ReadVRAM path is a
512 KiB final-address cross-check only; larger-memory support is not its oracle.

**41 scripts and eleven production objects pass**. The rotation unpacking fixture
now checks **1,920** both-capacity/address/A/B/field-pattern configurations against
its independent field schema. The existing **1,310,720** table-boundary scenarios
now additionally execute the production retained line-color renderer, using a
controlled palette/color stage to expose the selected index (not to qualify color
math). **512** latch/reload replay sequences still pass. Both fixed-1-MiB-mask
mutations compile and fail assertions. This is extracted-code/address qualification,
not linked save-manager, raster timing or game acceptance. T03 remains open for
CPU aliases and the remaining legacy cell-map/character fetch audit.


## V2-T03b/R04d: bitmap/scroll size masks and source-cache validity — 2026-09-16

All five retained bitmap renderers now use the configured 512 KiB/1 MiB physical
mask, matching the point sampler rather than always folding upper bitmap data into
512 KiB. Legacy line-scroll and vertical-cell-scroll fallback reads now mask the
complete table index to the configured size. Their row/column indexing, fractional
math, batching and dispatch policy are unchanged; normal complex scroll continues
to use the shared point sampler.

The audit also found that bitmap cache construction did not establish source watch
ranges. Rotation bitmaps now clear stale name-table ranges and watch their complete
format/size-dependent source surface. Wrapping/oversized surfaces conservatively
watch the physical memory rather than omit the low wrapped portion. Normal and
disabled bitmap draws leave cache metadata alone. Finally, each A/B source-cache
key includes VRAM size: changing only VRSIZE rebuilds the relevant cache instead of
reusing pixels decoded with the previous wrap. This is derived cache state, reset
by the existing postload invalidation, not new saved hardware state.

Primary evidence: ST-058 pp.26–28 (memory capacity/map), p.95/table 4.11 (bitmap
surface lengths, 20000H base alignment and oversized-surface repetition), and
pp.140–142 (line/vertical-cell table addressing). Pinned Ymir 6d779960's shared
ReadVRAM/MapVRAMAddress path corroborates 512 KiB final-address wrapping; its larger
memory mode remains TODO and is not used as an 8-Mbit oracle. The 1 MiB cases use
Sega's capacity/layout rules and independent byte-address arithmetic.

Validation: **41 scripts and eleven production object builds pass**. New bitmap
fixture: **17,280** all-format size/bank/wrap/coverage/blend/split-clip images using
production renderers and MAME blend primitives. Expanded legacy line-scroll tests:
**33,600** cases across both sizes, with poisoned inactive table rings. Existing
**85,248** cell-scroll cases now check physical-size addresses. Production cache
setup/write handlers pass **5,120** bitmap invalidation probes in addition to the
character suite; production rotation dispatch passes **20** cell/bitmap A/B size
transition/reuse cases. Ten old-mask/range/name/size-key mutations fail assertions.

**T03/R04 remain partial:** CPU-visible VRAM aliases, remaining legacy fetch consumers,
fetch-slot timing, and actual linked save/load/game/performance qualification are
not established by these extracted tests. Conservative wrapped watch ranges may
invalidate on unrelated writes; no frame-time improvement is claimed.


## V2-T03a: line-window and back-table physical wrapping — 2026-09-16

W0/W1 line-table reads and per-line back-screen reads now apply the configured
VRAM-size mask after adding the row offset. Previously only the table base used
the 512 KiB mask; a table near its end could read from the unused upper half of
the 1 MiB backing allocation rather than wrap to the start. The 1 MiB mode retains
its larger address range. Existing interlace/row selection is unchanged.

Primary evidence: ST-058 pp.176–177 and 186–187 describe table-address formation
and ignoring the high address bit in 4-Mbit mode. Pinned Ymir 6d779960 reads each
window/back entry through VDP2ReadRendererVRAM and VDP2Memory::MapVRAMAddress,
which masks the final address to 512 KiB. Its 1 MiB mode is explicitly TODO, so
it is not used as corroboration for the larger mode.

Validation: **40 regression scripts and eleven production object builds pass**.
New `test_vdp2_table_wrap.py` executes the production coordinate/back renderers in
**1,310,720** size/alias/end-of-memory/interlace/partial-row cases with an independent
modulo-address oracle. Memory includes high address bits in its pattern to expose
incorrect aliases. All three old-mask mutations (W0, W1, back) fail assertions.
This qualifies these consumers' wrapping, not all VDP2 fetches, hardware interlace
timing, or linked-game behavior. **T03 remains partial** pending the remaining
legacy consumers, CPU-visible aliases and runtime/cache qualification.


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

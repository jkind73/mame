# VDP2 implementation report and progress tracker

## V2-C02d: linked RBG0 shadow identity and color operations — 2026-09-16

Added **64 RBG0 shadow scenes per configuration**: normal-MSB precedence and
transparent shadow; sprite priorities zero/below/tied/above; R0SDEN versus the
wrong NBG0 shadow bit; plain versus calculated/offset RBG0; both VRAM capacities.
RBG0 is an opaque magenta 11-bit cell layer over the blue back screen, using
identity parameter A. The cells use the previously qualified 128-byte stride.

RBG0 priority is 2. Its calculated/offset result is 7f10ff; a qualifying shadow must
produce 3f087f, while a sprite below RBG0 must not darken it. The independent oracle
checks 144 probes and real save/mutate/load/full-image replay per scene. CPU writes
overwrite both VDP1 framebuffer banks during mutation, and a rotation character
word is explicitly changed and checked after restore. Captures 497 (below RBG0)
and 505 (above RBG0) were inspected.

**4,352 synthetic cases pass freshly** (3,264 DRC / 1,088 interpreter): 1,042 composition
plus 46 background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible
BIOS replays, all 47 regression scripts and 44 protocol cases pass; `-validate` has
no diagnostics. Extracted underlying-layer and offset-order mutations were rerun:
both compile and fail assertions. Production and the previously rebuilt executable
are unchanged; full-link/eleven-object evidence is retained, not a new source build.

Primary ST-058 pp.148–150 and 259 were reread alongside the previously audited
priority/shadow rules. Pattern names and character data use separate rotation-owned
banks: RAMCTL 110e at 4 Mbit selects A0 for names and A1 for characters; RAMCTL
1023 at 8 Mbit selects B for names and A for characters. The normal backgrounds
are disabled in these scenes. Pinned MiSTer VDP2 lines 3276–3282 corroborate R0SDEN
and sprite/RBG0 priority gating; pinned Ymir lines 3986–4001 corroborate selection
of the underlying background shadow bit. Sega/MiSTer, not Ymir's differing offset
order, remain the color-operation ordering basis.

This qualifies **identity-rotation RBG0 composition**, not general rotation
coordinates: the opaque constant-color source cannot prove transformed sampling,
coefficient permissions/precision, RBG1 sharing or parameter latch timing. Framebuffer
injection also does not establish VDP1 command timing or hardware access windows.
Those acceptance items and full VDP2 remain open. Older totals below are historical.

## V2-C02c: linked shadow layer identity, rank and precedence — 2026-09-16

Added **160 shadow-ranking scenes per configuration**: underlying NBG0, NBG1,
NBG2, NBG3 or back screen; sprite priorities 0/1/2/3; correct versus wrong SDCTL
layer selection; normal-MSB precedence versus transparent shadow; and both VRAM
capacities. Background priority is 2, so zero, below, tied and above are distinct.
For the back screen, nonzero sprite priority wins. Normal tests use type-2 pixel
87fe: its MSB is set but the normal-shadow color code must take precedence over
self-shadow. Transparent tests use 8000 with TPSDSL enabled.

NBG0/1 use red/green bitmaps; NBG2/3 use yellow/white cells with independent plane
and character storage and real PN/CP commands. The back screen is blue. The oracle
selects the expected underlying color, applies documented rank/eligibility rules,
then halves channels only at framebuffer checker pixels. Each scene checks 144
probes plus real save/mutate/load/full-image replay with both framebuffer banks
overwritten. Captures 431 (normal-code/MSB tie over NBG2) and 489 (transparent
shadow over back) were inspected.

**4,096 synthetic cases pass freshly** (3,072 DRC / 1,024 interpreter): 978 composition
plus 46 background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible
BIOS replays, all 47 regression scripts and 44 protocol cases pass; `-validate` has
no diagnostics. New extracted priority-zero-pass and sprite-before-background
mutants compile and fail dispatch assertions; the unmodified dispatch suite passes
131,072 images. Normal/MSB precedence and underlying-layer mutants were rerun and
also assertion-rejected. Dispatch callbacks are stand-ins in that extracted suite;
these linked scenes separately exercise the real framebuffer/compositor path.
Production and the previously rebuilt executable are unchanged.

Primary ST-058 pp.224–225/Table 11.1 and pp.256,258–260 were reread: priority zero
is transparent, sprites win equal priorities, normal-shadow codes take precedence,
and SDCTL selects each underlying screen independently. Pinned Ymir renderer lines
3986–4001 corroborate the rank and underlying-layer gates; MiSTer VDP2 lines
3276–3282 and 3298–3315 corroborate shadow rank comparisons and sprite tie order.
The earlier Ymir offset-order disagreement remains documented and is not used as
an ordering oracle here.

This closes the bounded NBG0–3/back shadow-ranking submatrix, not RBG0/RBG1,
8-bit framebuffer modes, mixed RGB/window effects, per-dot background priority
crossings or raster/VDP1 command timing. Full VDP2 and parent C02 remain open;
older totals below are historical checkpoints.

## V2-C02b: linked normal/MSB shadows and color-operation order — 2026-09-16

Added **160 shadow scenes per configuration** at both VRAM capacities. Normal
shadow codes cover word-sized sprite types 0–7, underlying NBG0 eligibility and
plain versus calculated/offset backgrounds. Types 2–7 additionally cover transparent
MSB shadow with both TPSDSL and underlying eligibility gates, plus opaque sprite
self-shadow with calculation/offset on/off and differing SDCTL selections. The
wrong underlying-layer bit is deliberately set when NBG0 eligibility is disabled.

The real CPU-mapped 16-bit VDP1 draw framebuffer receives shadow/transparent
checker pixels, followed by manual display-bank change. Sprite priority 3 is above
NBG0 priority 2 and NBG1 priority 1. Normal shadows halve the finished NBG0 result;
self-shadow always halves its own finished sprite result. The offset scenes distinguish
half-after-offset from offset-after-half: 8f7f00 becomes 473f00, and the calculated/
offset blue sprite becomes 47003f. Captures 341 and 365 were inspected. Each scene
checks 144 probes and real save/mutate/load/full-image replay. Mutation overwrites
both physical framebuffer banks and clears sprite priorities and SDCTL.

**3,456 synthetic cases pass freshly** (2,592 DRC / 864 interpreter): 818 composition
plus 46 background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible
BIOS replays, all 47 regression scripts and 44 protocol cases pass; `-validate` has
no diagnostics. Five extracted mutants compile and fail assertions: normal-shadow
precedence, transparent enable, self-shadow enable, underlying-layer selection and
offset ordering. The extracted all-type scanout matrix still passes 32,256 shadow
images; normal-shadow/MSB precedence is tested there, not newly in the linked matrix.
Composition watchdog is 360 emulated seconds; runner wall timeout defaults to 600.
Production and the previously rebuilt executable are unchanged.

Primary ST-058 pp.256–260 were reread: shadow follows calculation and offset;
normal code is all color bits set except LSB; MSB shadow is limited to types 2–7;
TPSDSL and screen selection gate transparent shadow, while self-shadow is unconditional.
Pinned Ymir lines 5393–5404 corroborate special-pattern decoding, but lines 4181–4195
apply shadow **before** offset, disagreeing with Sega. It is not the ordering oracle.
Pinned MiSTer VDP2 lines 3517–3532 implement calculation, offset, then shadow,
consistent with the primary reference and this independent color oracle.

This is bounded highest-priority, palette-only, normal 16-bit scanout over NBG0;
other underlying layers, 8-bit/readout modes, mixed RGB/window combinations,
priority crossings and raster/VDP1 command timing remain separate acceptance.
CPU framebuffer injection does not establish the hardware access/latch window.
Full VDP2 and parent C02 remain open; older totals below are historical checkpoints.

## V2-C06d: linked extended calculation and third-image format — 2026-09-16

Added **192 extended-calculation scenes per configuration**: EXCCEN on/off, second
image CC enable, top/second ratio source, top CC enable, CRAM modes 0/1/2, RGB versus
palette third image, and both VRAM capacities. Opaque red NBG0 is above green NBG1;
the third image is either the direct-RGB blue back screen or an added blue NBG2
cell layer. The NBG2 plane, character data and bitmap data are disjoint and have
real PN/CP cycle commands. Mode-2 colors are written as CPU RGB888 longwords.

The independent expected colors distinguish second-image-only (4:0:0) from
second/third (2:2:0) calculation. CRAM modes 1/2 must suppress extended mixing when
the third image is palette, even if NBG1 CC is enabled; an RGB third remains eligible.
Different top/second ratios (15/7) expose ratio ownership and raw lower-image
history. Sixteen probes and real save/mutate/load/full-image replay pass per scene.
Captures 263 (RGB third, 7f3f3f) and 311 (palette third, 7f7f00) were inspected.

**2,816 synthetic cases pass freshly** (2,112 DRC / 704 interpreter): 658 composition
plus 46 background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible
BIOS save/load replays, all 47 regression scripts and 44 protocol cases pass;
`-validate` has no diagnostics. Extracted extended-enable, third-format and
ratio-metadata mutations compile and fail assertions. The composition watchdog is
240 emulated seconds for the larger matrix; strict ordered case/PASS checks remain.
Production and the previously rebuilt executable are unchanged.

Primary ST-058 pp.237–238/Table 12.2 were reread from the pinned SDK PDF. Pinned
MiSTer package lines 2401–2421 and main lines 3475–3483 corroborate arithmetic,
third-format gating and top/second ratio selection. Pinned Ymir renderer lines
4101–4134 corroborate second-enable-controlled lower-image combination, but this
path does not establish the table's palette-format restriction and is not that
restriction's oracle. These tests deliberately omit line insertion: the documented
CRAM0 2:1:0 versus figure/reference 2:1:1 discrepancy is **not** resolved or qualified.
This is bounded normal-resolution, opaque, no-line-color coverage, not all layer
orders, RGB sprite inputs, display modes, timing, games or hardware evidence.
Full VDP2 and parent C06 remain open; older totals below are historical checkpoints.

## V2-Q02c: fresh full rebuild and linked requalification — 2026-09-16

Restored the missing external SDL/pkg-config dependency cache and rebuilt the
focused Saturn/ST-V executable from the recovered source. All **47 regression
scripts and eleven production object compilations pass freshly**. The initial
two-job full build lost `cc1plus` while compiling `luaengine.cpp`; resuming with
one job completed successfully without source changes. GCC garbage-collection
limits remain enabled as documented in the reproduction command.

The rebuilt executable SHA-256 is **identical** to the previous qualified binary:
`85bef0b9d5d9c1f47847c571bcd1f70427e30f9e157541982a3774a93e04302e`.
MAME `-validate` produces no diagnostics; `-listxml` confirms 122 runnable systems.
All twelve linked runs were refreshed: **2,048 synthetic cases** (1,536 DRC /
512 interpreter), comprising 466 composition and 46 background cases on JP/PAL/
ST-V DRC and JP interpreter, plus **four visible BIOS save/load replays**. The
strict runner also passed its 44 protocol cases within the regression suite.

`linked_runtime_results.json` now contains fresh log/capture hashes and full-build
provenance. This supersedes A05c's missing-executable limitation, not its separate
CRAM callback-test limits. Build/cache/log/state artifacts remain outside Git or
in ignored build paths; unrelated user logs are preserved. PR and the official-doc
mirror track this checkpoint. No production correction was needed, no new rendering
cases are added, and no performance improvement is inferred from matching hashes.

Q02c restores current executable evidence; it does not close all-layer/effect,
physical latch/arbitration, hardware rounding, external video, game/title or
comparative-performance acceptance. Full VDP2 remains incomplete. Earlier
checkpoint results and restoration limitations below are historical.

## V2-A05c: stateful CRAM writes and preservation ordering — 2026-09-16

Recovered this session's pushed `03a20495` branch after the workspace returned to
an older base. The pre-recovery tracked patch and Saturn files are backed up outside
the repository and in a Git stash; unrelated console/error logs were restored.
No older production changes were blindly reapplied over the recovered branch.

Extended `test_vdp2_palette.py` with a deterministic **4,096-write sequence** and
an independent physical byte-array oracle. The modeled CPU operations remain legal
word/longword writes, not byte writes. CRAM modes 0/1/2 change throughout; every
step checks physical storage, all CPU-readable words, all decoded palette entries,
and immediate versus rebuilt palette agreement. The sequence includes **234 writes
that change only the mirrored bank** and **790 redundant writes**. Recording callbacks
must see the complete pre-write memory, occur for actual changes (including mirror-only
changes), and be absent for unchanged writes. Mode changes rebuild pens explicitly;
this does not execute the RAMCTL register handler or the real raster scheduler.

All **47 regression scripts pass freshly** under the restored checkout. Three
mutants compile and fail C++ assertions: omitted mirror-only preservation,
redundant preservation and preservation after memory mutation. The existing 9,216
CRAM lane/address/palette cases and 40,960 coefficient-bank cases also pass.
Evidence is recorded in `cram_stateful_results.json`. No production fix was needed.

Basis remains ST-058 section 3.4 pp.43–46 and the pinned Ymir/MiSTer physical-bank
cross-checks recorded below. Upper-half broadcast/read independence remains
cross-implementation evidence, not new hardware evidence. Callback ordering tests
protect the current preserve-before-write contract; they do not establish latch
granularity, contention, DAC output, bus timing or actual save-manager behavior.

The restored workspace lacks the prior linked executable and dependency cache.
The **2,048 linked synthetic cases and four BIOS replays remain historical evidence
from 03a20495**, not freshly rerun results. `linked_runtime_results.json` is left
unchanged. Full VDP2 and the parent A05/T01 acceptance items remain open.

## V2-C06c: linked gradation source, filter and ratios — 2026-09-16

Added **16 gradation scenes per configuration**: patterned opaque NBG0 (top) or
NBG1 (second), BOKEN on/off, both ratio-source settings and both VRAM capacities.
The fixture explicitly selects CRAM mode 0 and normal resolution. Three-pixel color
runs vary by row; 48 independent probes cover both preceding source dots and filter
transitions. Top and lower ratios differ (15/7), revealing replacement of the second
image and its ratio when the designated screen is top. Real save/mutate/load replay
checks the entire image; mutation clears CCCTL. Captures 227 and 233 were inspected.

**2,048 synthetic cases pass** (1,536 DRC / 512 interpreter): 466 composition plus 46
background cases on JP/PAL/ST-V DRC and JP interpreter. All four background runs and
four visible BIOS save/load replays were refreshed. All 47 regression scripts and
44 runner-protocol tests pass; `-validate` reports no diagnostics. Extracted
filter-weight and missing-left-history mutants compile and fail assertions.
Production code and the previously linked executable are unchanged.

Primary basis: ST-058 pp.238–241 (opaque source, normal/CRMD0 legality, 1:1:2
horizontal filter, designated top/second replacement and ratio controls). Pinned
MiSTer VDP2 lines 3393–3401 and 3476–3489, package lines 2401–2421 corroborate
source selection and separate half/quarter-term truncation. Pinned Ymir renderer
lines 4076–4100 corroborate source rank but its Color888GradationMasked implementation
uses nested averages: **low-bit rounding differs**, so it is not an arithmetic oracle.
The linked oracle follows the pre-scaled-term interpretation and MiSTer, not a
hardware capture. Probe expectations deliberately exclude x=0/1; full-image replay
there tests save determinism only. Transparent boundaries, other layers/formats,
partial-render scheduling, hardware rounding and the parent C06 remain unqualified.
Full VDP2 is not declared complete; earlier totals below are historical.

## V2-C03e: linked three-window logic matrix — 2026-09-16

Continued from C03d with **64 combined W0/W1/sprite-window scenes per
configuration**: all eight retained-area polarities, both LOG settings and both
coverage/calculation-only uses, at both VRAM capacities. The independent oracle
complements the documented active-area logic (ST-058 pp.189–195): LOG=0 retains
the intersection; LOG=1 retains the union. Asymmetric overlapping rectangles and
the displayed-framebuffer checker exercise all three inputs with 144 probes per
scene. Both physical framebuffer banks are overwritten before full-image save
replay. Captures 194 and 225 were inspected. Pinned Ymir lines 2450–2463 and
MiSTer lines 3161–3168 provide cross-checks, not the expected-image oracle.

All four **450-case composition runs pass**. With the unchanged 46-case background
path and four BIOS replays from C03d, the recorded total is **1,984 synthetic cases**
(1,488 DRC / 496 interpreter). JSON records distinguish the retained background/BIOS
fixture hashes from the expanded composition fixture. All 47 regression scripts
pass again, as do 44 protocol cases and `-validate`. A new extracted mutation
reversing only the SW combination operator compiles and fails the bitmap-image
assertion; the unmodified bitmap suite passes 184,320 images.

No production change was required. C03e qualifies this normal-resolution NBG0
three-window matrix, not all layers, rotation/line-window mixtures, latch timing,
physical arbitration, games or comparative performance. Full VDP2 remains open;
totals in older sections are historical checkpoints.

## V2-C03d: linked displayed-framebuffer sprite windows — 2026-09-16

Added **48 sprite-window scenes per configuration**: legal palette-only sprite types
2–7, coverage/calculation-only windows and both retained areas, at both VRAM
capacities. CPU-mapped VDP1 drawing-bank writes provide a 13-by-9 MSB checker;
manual framebuffer change exposes it to VDP2. Sprite priorities are zero, leaving
red/green backgrounds to reveal coverage and calculation independently. Each scene
checks 144 coordinate/color probes and real save/mutate/load/full-image replay.
Mutation overwrites **both physical framebuffer banks**, preventing a bank-selector
restore alone from recovering the saved image. Captures 170 and 193 were inspected.

**1,728 synthetic cases pass** (1,296 DRC / 432 interpreter): 386 composition plus 46
background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible BIOS
replays, all 47 regression scripts and 44 runner-protocol tests pass; `-validate`
reports no diagnostics. Extracted MSB-inversion and wrong-bank mutants compile and
fail sprite-window assertions; the unmodified extracted suite passes 1,376,256
sprite-window probes. Production code and the previously linked executable are unchanged.

Primary basis: ST-058 pp.187–190 and ST-013-R3 p.38 (CPU drawing-bank access and
manual next-field change), pinned SDK revision documented below. Cross-checks:
pinned Ymir renderer lines 2450–2463 and MiSTer VDP2 lines 3161–3168. The fixture
waits across fields; injected register writes do **not** certify the documented
interrupt/access window, latch timing, bus arbitration or VDP1 command execution.
C03d is bounded to normal 16-bit framebuffer scanout and these NBG0 windows; mixed
windows, other scanout modes, all layers/rotation, games and comparative performance
remain separate acceptance work. Full VDP2 is not declared complete. Older totals
below are historical checkpoints.

## V2-C04c: linked per-dot priority and special calculation — 2026-09-16

Added **96 special-function scenes per configuration** using transparent/red/green
NBG0 bitmap dots over an opaque blue NBG1. Priority modes 0–2 are crossed with bitmap
attributes and both special-code selectors; separate scenes verify base-zero promotion
and effective-zero suppression. All four special-calculation modes are crossed with
attribute state, selector and top-screen CC enable. Red has its CRAM MSB set while
green does not. Combined scenes exercise per-dot priority and MSB-selected calculation
simultaneously. Each scene checks 144 independent coordinate/color probes plus real
save/mutate/load/full-image replay. Special mode, code and attribute registers are
explicitly cleared during mutation. Both combined-selector captures were inspected.

**1,536 synthetic cases pass** (1,152 DRC / 384 interpreter): 338 composition plus 46
background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible BIOS
replays pass, all 47 regression scripts pass, and `-validate` has no diagnostics.
The unchanged production executable retains its full-link/eleven-object evidence.
Priority-zero, priority-attribute, special-MSB and special-code mutations compile and
fail extracted assertions. The 44 fake-executable runner-protocol cases pass.

Primary basis: ST-058 pp.228–229 and 245–247, corroborated by pinned Ymir/MiSTer
priority/eligibility logic. No prohibited priority mode 3 or RGB mode-2 combinations
are treated as legal. No production correction was needed. C04c qualifies the bounded
normal-resolution NBG0 four-bit bitmap matrix, not all cell formats, layers, rotation,
CRAM/display modes or effects. Exact bus/latches, external video, games/title and
comparative performance remain open. Full VDP2 is not declared complete. Older totals
below describe earlier checkpoints.

## V2-C07a: linked line-color insertion, ratios and table wrapping — 2026-09-16

Added **16 line-color scenes per configuration**: single/per-line tables, top-screen
insertion, second-screen ratio selection from CCRLB, lower-layer line-color history
isolation, and disabled top calculation, at both VRAM capacities. Blue/yellow table
colors differ from the red/green background inputs. Top, lower-background, line and
back ratio values deliberately differ. Tables cross the physical VRAM boundary and
set ignored upper bits; bitmap and back data remain disjoint. Forty-eight probes
include rows on both sides of the wrapping point and the first/last visible rows.
The table and its address/enable/ratio controls are cleared during mutation before
real load and full-image replay. Per-line and lower-history captures were inspected.

**1,152 synthetic cases pass** (864 DRC / 288 interpreter): 242 composition plus 46
background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible BIOS
replays pass, all 47 regression scripts pass, and `-validate` again has no diagnostics.
The unchanged production executable retains its full-link/eleven-object evidence.
Production line-color wrapping, single/per-line mode, line-ratio selection and
raw-lower-history mutations compile and fail extracted image/state assertions.
The 44 fake-executable runner-protocol cases pass; they are not renderer evidence.

Primary basis: ST-058 pp.172–174,231,241–244. Pinned Ymir/MiSTer corroborate selected
second-image insertion and ratio routing, not hardware timing or all combinations.
No production correction was required by these scenes. C07a is bounded ordinary
NBG0/NBG1 normal-resolution qualification: coefficient-selected/rotation line colors,
interlace, extended/gradation interactions, exact bus/latches, external video,
games/title and comparative performance remain open. Full VDP2 is not declared
complete. Earlier totals below describe earlier checkpoints.

## V2-C08a: linked source mosaic, transparency and blending — 2026-09-16

Added **16 mosaic scenes per configuration**: 1x1, 3x5, 16x16 and 7x2 blocks,
with and without ordinary blending, at both physical VRAM capacities. NBG0 uses
transparent/red/green source patterns and nonzero X/Y scroll; NBG1 uses an independent
yellow/white pattern. The analytic oracle samples only NBG0 at each mosaic block's
upper-left coordinate, then composites against the unchanged NBG1 dot. This detects
post-composition mosaicking and accidental resampling of the lower screen. Every
scene enables a nonzero nine-line vertical-cell-scroll table that mosaic must suppress,
including when the mosaic dimensions are 1x1. Each scene checks 144 probes and real
save/mutate/load/full-image replay; the mutation explicitly clears MZCTL. Captures
with and without blending were inspected.

**1,088 synthetic cases pass** (816 DRC / 272 interpreter): 226 composition plus 46
background cases on JP/PAL/ST-V DRC and JP interpreter. Four fresh visible BIOS
replays pass, all 47 regression scripts pass, and `-validate` again has no diagnostics.
The unchanged production executable retains the existing full-link/eleven-object
qualification. Mosaic/VCSC-suppression and clip-relative-origin mutations compile
and fail independent extracted image assertions. Unmutated point-sampler coverage
passes 294,912 images and 98,304 metadata cases; the 44 runner-protocol cases pass.

Primary basis: ST-058 pp.117–119. Pinned Ymir/MiSTer corroborate layer-local mosaic
and VCSC priority, not hardware timing or every combination. No production correction
was required by these scenes. C08a is bounded NBG0 normal-resolution qualification;
other layers, rotation/interlace, all size/effect combinations, exact bus/latches,
external video, games/title and comparative performance remain open. Full VDP2 is
not declared complete. Earlier totals below describe earlier checkpoints.

## V2-C03b: linked line-window tables and physical wrapping — 2026-09-16

Added **16 line-window scenes per configuration** to the composition fixture:
W0 alone, W1 alone, intersection and union, each as coverage or calculation-only
windows, at both physical VRAM capacities. Each table is independently exercised
crossing the physical end of VRAM. Horizontal bounds alternate by scanline, selected
rows have start greater than end, and vertical bounds remain register controlled.
Analytic screen-coordinate expectations check 144 boundary probes per scene.
Bitmap/back data are placed away from both tables, avoiding accidental scene aliases.
Both tables and their enable/address registers are cleared during the save/load
mutation, then restored data and full-image equality are verified.

The **210-case composition and 46-case background suites pass** on JP/PAL/ST-V DRC
and JP interpreter: **1,024 current synthetic cases (768 DRC / 256 interpreter)**.
Four visible BIOS replays were rerun and pass; `-validate` again produces no
diagnostics. All 47 regression scripts pass. The extracted table-address fixture
passes 1,310,720 cases; W0/W1 capacity-mask and one-row-shift mutations compile and
fail assertions. Those address tests preserve existing interlace indexing and are
not independent hardware timing evidence. Line-window captures were inspected.

Primary basis: ST-058 pp.184–187 (per-line X bounds, inclusive borders, inverted
rows, table address/physical-size rules). Pinned Ymir and MiSTer corroborate paired
start/end table entries and the separation of horizontal table data from vertical
register bounds, not full 1 MiB or interlace certification. No production correction
was needed for these new scenes. C03b is bounded normal-resolution qualification;
sprite-window combinations, interlace/other display modes, exact latches/contention,
external video, games/title and comparative performance remain open. Full VDP2 is
not declared complete. Earlier case totals below are historical checkpoints.

## V2-C03a / C05b: linked windows and color offsets — 2026-09-16

The pushed composition work was extended to **194 cases per configuration**. Added
post-blend color offsets, exclusion of the lower screen's offset from calculation,
positive/negative saturation, and A/B offset selection. W0/W1 coverage and calculation-
only windows now cover inclusive boundaries and immediately adjacent dots, overlap,
inside/outside selection, a disabled peer, and all-disabled behavior under both LOG
values. The reference predicates describe retained pixels; the hardware LOG bit
combines the complementary active/suppressed areas (ST-058 p.194), not those predicates.
Window scenes use **144 boundary probes**, versus sixteen probes in other scenes.
Save/load tests now explicitly clear window and offset registers during mutation.

**All 960 synthetic cases pass** (720 DRC / 240 interpreter): 46 background plus 194
composition cases on JP/PAL/ST-V DRC and JP interpreter. All four visible BIOS replays
were rerun and passed; `-validate` was rerun with no diagnostics. The 47-script suite
passes, and the unchanged production sources retain eleven-object/focused-link
qualification. The 44 fake-executable runner cases pass. Production offset-order,
calculation-window endpoint and disabled-window mutations compile and fail assertions.
Coverage-window and calculation-only-window captures were inspected separately.

Primary sources re-read: ST-058 pp.189–195 and 250–252. Pinned Ymir's final-output
color-offset pass and MiSTer's signed `ColorOffset` helper corroborate offset ordering/
selection, but are not hardware oracles. No production correction was required by
these new tests. This closes bounded C03a/C05b qualification, not their parent items:
line/sprite windows, rotation combinations, other display modes, exact raster/bus
behavior, external video, games/title and performance remain open. Full VDP2 is not
claimed complete. Older totals below are historical checkpoints.

## V2-A04d / C05 linked two-background qualification — 2026-09-16

Continued from isolated backgrounds into real linked composition. **138 additional
cases per configuration pass** on JP/PAL/ST-V DRC and JP interpreter (552 new cases):
NBG0/NBG1 tie order, NBG1 above NBG0, priority-zero suppression, all 32 color ratios
using both top- and second-screen ratio selection, additive saturation, and disabled
calculation on the top screen despite calculation enabled below it. Both physical
VRAM capacities are covered. Each scene uses the real palette, bitmap consumers,
compositor and save manager; sixteen expected-color probes plus restored memory and
full-image replay are checked. The additive scene uses red over yellow to force
red-channel saturation, not merely disjoint-channel addition.

Current total: **736 synthetic cases (552 DRC / 184 interpreter), four visible BIOS
replays, 47 regression scripts, eleven production objects and a clean focused link /
`-validate` for 122 runnable systems**. The runner now distinguishes the 46-case
background suite from the optional 138-case `--composition` suite. Its 44 fake-
executable protocol cases pass; they are not renderer evidence. Production ratio
and disabled-second-ratio mutations also compile and fail image/state assertions.

Primary basis: ST-058 pp.241–244 for calculation enable, ratio source, /32 weights
and additive mode. Normal-resolution 512x256 bitmaps and 16x16 one-word cells are
bounded coverage, not every size, pattern format, partial clip, resource conflict or
combined effect. C05/A04 parents remain open for those combinations and hardware
qualification. Full VDP2, exact bus/latch timing, external video, games/title placement
and comparative performance are not declared complete. Evidence and capture hashes
are in `regtests/saturn/linked_runtime_results.json`; reproduction is in
`regtests/saturn/linked_runtime.md`.

## Fresh linked qualification — 2026-09-16

The reconstructed executable now **links and passes `-validate` for 122 runnable
systems with no validation diagnostics**. Current executed evidence is 47 regression
scripts, eleven production-object compilations, **138 DRC synthetic cases** across
Japanese Saturn/PAL Saturn/ST-V, plus **46 Japanese Saturn interpreter cases**.
Every synthetic case verifies mapped registers, sixteen expected-color probes,
real save notification, VRAM/CRAM/priority/CRAM-mode/VRSIZE mutation, load notification,
restored data and full-image equality. Four distinct cell colors exercise H/V flips.

**Four visible BIOS replays pass:** JP/PAL/ST-V DRC and JP interpreter. Each boots
900 frames without injected register/memory changes, rejects uniform RGB output,
saves, advances half a second and checks time, main SH-2 PC and full-image identity
on replay. JP date/time, PAL language selection and synthetic 11-bit cell captures
were inspected. ST-V is BIOS-only, not cartridge/game acceptance.

Executable SHA-256: `85bef0b9d5d9c1f47847c571bcd1f70427e30f9e157541982a3774a93e04302e`.
This independently rebuilt hash matches the historical lost build. New run/capture
hashes are recorded in `regtests/saturn/linked_runtime_results.json` (paths relative
to the repository root). Full logs, snapshots and states stay outside Git.

**V2-Q02 is closed** for the focused build/configuration check. A04/Q01/Q03 receive
bounded linked coverage, not complete parent acceptance. Exact contention/latching,
mid-field reconstruction, external video, combined effects/hardware precision,
games/title placement and comparative performance remain open. Older “pending”
entries below describe the pre-execution recovery/authorship checkpoints.

## V2-A04c: expanded linked-background fixture — 2026-09-16

The linked fixture now defines **46 cases per system**: NBG0 cells/bitmaps at five
depths, NBG1 cells/bitmaps at four depths, NBG2/NBG3 cells at two depths, and the
existing RBG0 11-bit cell case, each at both VRAM capacities. Normal 16x16 cells
use four distinct 8x8 colors and alternating horizontal/vertical pattern-name flips;
independent screen-coordinate expectations distinguish swapped H/V decoding.
The same real-save/memory/palette/mode/priority mutation and full-image replay
checks apply. This is authored coverage, **not yet linked execution evidence**.

ST-058 printed pp.60–61 and 69–75 were re-read from the pinned SDK blob for legal
formats, character-number supplements and flip encoding. No new production fix is
inferred from an unexecuted fixture. The runner now requires every ordered case
record plus an exact completion marker; BIOS markers must match the selected system.

**47 regression scripts pass**, including 28 fake-executable runner-protocol cases;
the Lua syntax check passes. The fake executable tests failure detection, not video.
The unchanged production sources retain the earlier eleven-object compilation pass.
The full build was reduced to one job to avoid concurrent high-memory GCC units;
link/validate and current-checkout BIOS/synthetic replay remain pending. Parent A04
and full VDP2 acceptance remain open.

### Cell-stride/flip cross-check

ST-058 table 4.2 (p.53) specifies 128-byte cells for 2048-color palette data.
The pinned MiSTer `NxCHAddr` agrees. The pinned Ymir normal-character caller
passes cell index 0–3, but its `VDP2FetchCharacterPixel` scales Palette2048 by two
32-byte units rather than four; its dot fetch still reads 16 bits. This is a
source discrepancy, not an independent hardware oracle. MAME retains the primary-
documented 128-byte stride. New 64-byte-stride and swapped-H/V mutations both
compile and fail the independent point-sampler image assertions. Unmutated sampler:
294,912 image cases and 98,304 priority/code metadata cases pass.


## Integrated recovery — 2026-09-16

Reconstructed the unpushed integration lost during sandbox restoration: all six
three-bit map offsets, capacity-aware full console/ST-V CPU apertures, ordinary
11-bit palette-cell sampler routing at all three dispatch/source sites, explicit
FF initialization for 60 undumped EEPROM placeholders, and the full validator's
actual executable path. Existing 4/8-bit cached paths and dumped EEPROMs are kept.

**Current evidence: 46 scripts and eleven production object compilations pass;
nine targeted mutations fail assertions.** External SDK provisioning also passes.
Linked synthetic/save-manager and visible BIOS replay tools have been restored,
but current-checkout linked/runtime acceptance is pending. The earlier unpushed
checkout's successful full build and 42 synthetic/three DRC BIOS runs are historical:
the executable and captures were lost, so they do not certify this reconstruction.
See [reproduction, evidence and limits](linked_runtime.md).

Full VDP2 is not complete; exact contention/latching, external video, combined-effect
hardware qualification, mid-field reconstruction, games and performance remain open.
The dated sections below preserve earlier checkpoints; their test totals describe
those checkpoints, not the current regression count. No additional parent acceptance
checkbox is closed merely by reconstructing historically tested work.

## V2-T03g: retained palette-cell boundary source selection — 2026-09-16

Zoom, alpha and transparent-pen palette helpers now normalize character numbers
before use and share `vdp2_get_palette_cell`. Ordinary cells retain generic decoded
cache access. The final 8-bit cell starts 32 bytes before physical memory ends but
contains 64 bytes; it is read into a local 64-byte wrapped buffer instead of asking
the contiguous generic decoder to read beyond physical memory. This also observes
changes to its low-memory half without relying on a decoder dirty predecessor
across the wrap. Four-bit cells fit within their 32-byte unit. The old last-8-bit-
character decrement workaround is removed, so the requested character is retained.
Zoom pen-usage lookup receives the normalized code too.

Primary evidence: ST-058 p.53, table 4.2, specifies 32-byte base alignment for both
32-byte four-bit and 64-byte eight-bit cells; section 3.1 supplies physical capacity.
The pinned Ymir shared storage wrapping corroborates the 512 KiB address model,
not 1 MiB support. The retained MAME 8x8x8 layout uses a 32-byte character increment,
which explains the final-cell contiguous-decoder overrun.

**45 scripts and eleven production object builds pass**, with narrowing errors
enforced. New production-source-selector fixture checks **262,144** capacity/depth/
code-alias configurations, all 64 dots, ordinary decoder routing and wrapped low-
memory updates. Size, missing-tail and wrong-tail mutations compile and fail
assertions. Decoder and memory updates are controlled stand-ins; renderer routing
and workaround removal are source assertions. This is not a linked generic-decoder
or full palette-renderer image/cache/save-manager replay. No measured speedup claimed.

T03 remains partial pending integrated consumer/decoder qualification. The generic
decoder itself and non-renderer users such as graphics inspection are not changed.
Full VDP2, fetch timing, linked game/save-load and performance acceptance remain open.


## V2-T03f: retained direct-color character row wrapping — 2026-09-16

The four RGB555/RGB888 zoomed and unzoomed character render helpers now normalize
the character base and each source-row address to configured physical VRAM size.
Previously their raw base pointer plus row offsets could read inactive upper memory
at 4 Mbit or run beyond the backing buffer at its end. Cells use 32-byte base units;
16/32-byte rows are aligned and cannot themselves straddle physical memory, so a
single mask per row covers each dot without per-byte masking or scratch copies.
Pixel decoding, zoom coordinates, flip, transparency, windows and blending are
unchanged. No palette-decoder or character-number workaround is changed here.

Primary evidence: ST-058 section 4.1 character-pattern layout specifies 32-byte base
alignment and 128/256-byte cells for 16/32 bits per dot; section 3.1 defines physical
memory capacities. Pinned Ymir's shared ReadVRAM physical wrapping corroborates the
512 KiB model only; larger-memory expectations use Sega's layout/capacity rules.

**44 scripts and eleven production objects pass**, including `-Werror=narrowing`.
New extracted production-helper fixture: **2,816** full/split images across both
capacities, boundary/aliased bases, both direct formats, normal/zoom helpers,
reduction/enlargement, flips, transparency and supported blend paths. It uses MAME
color/blend primitives, independent byte-modulo pixel addressing, a controlled
window and ASan/UBSan. Four wrong-capacity mutations plus a missing-row-wrap
mutation compile and fail assertions. Color offset remains disabled in this fixture.

T03 remains partial for palette/decoded-character tails and retained decoder
workarounds. These are helper images, not full tilemap/cache/game or linked
save-manager acceptance. Bus timing and measured performance remain unqualified.


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

**T02 implementation update, 2026-09-16 (parent remains open):** normal
PN/CP consumers now require their command in the addressed physical bank, with
4/8-Mbit wrapping, partition aliases, active slots and rotation ownership resolved
once per partial render. VCSC consumers require the documented early slots and
NBG0-before-NBG1 ordering in the addressed bank (ST-058 p.35; pinned MiSTer
VDP2.sv 725–732 and 1145–1208 cross-check). Normal rendering cannot bypass these
checks through the retained fast paths. Derived slot masks are rebuilt, not saved.
Denied PN/CP uses transparency; denied VCSC uses zero offset. These are conservative
no-fetch policies, **not hardware-certified stale-latch output**.

All 47 existing regression scripts pass together. The existing cycle fixture now
also exercises addressed-bank/capacity aliases and 16,384 VCSC decisions; the scroll
fixture exercises 192 real PN/CP consumer/route images and 12 VCSC images. Eight
cycle/fetch mutations compiled and were assertion-rejected. The linked background
fixture now removes each addressed group's CP, then PN for cells, while retaining
the command in the other group; it restores access before save/load replay. That
Lua fixture passes syntax checking, but its new linked runs are **pending**, as are
the full build/validate result and performance acceptance. Earlier linked results
above belong to earlier source, not this update.

Still missing within this same parent: PN/CP counts and dependency/slot ordering,
screen-mode/reduction bandwidth, actual fetch/latch timing, complete RBG1 and
coefficient/table restrictions, and CPU/SCU-DMA grants/waits. The SH2 execution
paths currently lack memory-access replay support; a renderer permission check
must not be described as bus contention. No whole-T02 or whole-VDP2 completion,
hardware, linked-game or frame-time acceptance is claimed.


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

## 4. Current feature-by-feature assessment

Updated after integration recovery. “Implemented” describes production code and
bounded extracted tests, not complete hardware or linked-game qualification.

| Feature group | Implemented / exercised | Still open |
|---|---|---|
| Normal backgrounds | NBG0–3 configuration, resource exclusions and drawing | Exhaustive legal format/resource/image matrix |
| Character backgrounds | One/two-word names, supplement, flips, cell/page addressing and capacity wrapping; explicit 11-bit cell routes | Linked boundaries, all formats/layers and simultaneous effects |
| Bitmap backgrounds | Five NBG0 formats, capacity-aware source addressing and sampling | All legal layer/size/window combinations |
| Map offsets / CPU aperture | All six three-bit MPOF fields; size-aware full 1 MiB console/ST-V mapping | Linked normal-screen/RBG0 high-bank replay passes; remaining consumers open |
| Fractional scroll / reduction | Fractional sampling and reduction-enable limits | Independent precision and combined image references |
| Line / vertical cell scroll | Combined line-X/Y/zoom and VCSC point sampling, interval/interleaving handling | Hardware precision and exhaustive simultaneous combinations |
| RBG0 / RBG1 | A/B transforms, parameter selection, NBG0 sharing and resource rules | Complete cycle contention and combined linked images |
| Rotation coefficients / latches | VRAM/CRAM access, permission rules, flags, line color, accumulation/read controls | Independent fixed-point oracle; exact latch timing |
| Screen-over patterns | OVPNRA/B pixels and special-function metadata | Linked composition and hardware qualification |
| Back / line-color screens | Table wrapping; line-color insertion into compositor | All coefficient/ratio/window/raster combinations |
| Mosaic | Per-source sampling including rotation restrictions; production enabled | Complete combinations and hardware images |
| Pixel identity / priority | Ordered per-dot source metadata, effective priorities and special priority modes | Exhaustive sprite types/ties and combined scenes |
| Ordinary / special calculation | Ratio/additive, ratio-source selection, special eligibility, calculation window and offsets | Complete rounding/selection/hardware image matrix |
| Extended / gradation | Production second/third/fourth combination and designated-source gradation | ST-058 CRMD0 line row prints 2:1:0; cross-emulators use 2:1:1; discrepancy unresolved |
| Windows | Rectangle/line windows, sprite mask, calculation-only and rotation selection | All resolution/interlace/clip combinations with actual layers |
| Shadows | Normal, transparent and self-shading MSB paths with source eligibility | Exhaustive priority/window/alpha matrix and hardware images |
| VDP1 scanout | Packed/normal, rotation, interlace and output-coordinate composition | Full sprite/window/shadow matrix and readout phases |
| Raster writes | Prior-line partial presentation for render-affecting writes | Exact dot/line latch boundaries and mid-line state |
| VRAM / caches | Capacity masks, wrapped tables/cells/bitmaps, dirty invalidation and rotation cache keys | All consumers, debugger decode boundaries and integrated cache replay |
| Cycle patterns | Bank/command/reduction/resource-aware eligibility | Slot/address/count fetch scheduling, corruption and CPU contention |
| CRAM | Mode-0 broadcast/read handling and mode-dependent palette paths | Full register/access-width ledger, prohibited mode behavior and linked alias matrix |
| Registers | Decoded controls, status, masks and render-write handling | Complete legality/reset/access/latch ledger |
| TV modes / counters | CRTC modes, counter tables/latches, ODD and external callback | Physical beam, half-lines, DOTSEL and exclusive/interlace transitions |
| External inputs | Latch/sync flags and callbacks | Actual MPEG/external-background/genlock provisioning and rendering |
| Reset / save | Registered backing state; postload palette/decode/rotation invalidation | Bounded linked replay passes; complete mid-field picture reconstruction open |
| Performance | Existing palette/window/rotation/decode caches retained | Linked comparative profile and equivalent-image optimization evidence |

## 5. What has actually been tested

The current checkout passed **47 Saturn regression scripts and eleven production
object compilations**, not 47 dedicated VDP2 scripts. All six map-mask truncations
and three plain 11-bit routing mutations compiled and failed assertions. The
external dependency bootstrap executed successfully. The fresh full link/validate passes. The linked matrix passes 1,536 synthetic
cases and four visible BIOS replays, as recorded at the top of this report.

| Fixture family | Evidence | Limit |
|---|---|---|
| Map-offset / VRAM-access | Actual macros/handlers; real machine-map guards | Arithmetic and mapping guards are not a linked renderer |
| Bitmap, cell-map, direct/palette-cell, table-wrap | Source addressing, physical masks, wrapping and retained-decoder selection | Controlled decoder/storage inputs; not every integrated consumer |
| Scroll, line-scroll, reduction | Production sampling/dispatch and clipped image comparisons | Independent silicon precision oracle absent |
| Rotation parameters, latches, windows, clip, dispatch, cache | Production helpers and negative mutations | Stand-in devices/selected sources; not hardware timing |
| Composition, palette, priority dispatch, sprite scanout | Production metadata/effect/eligibility and selected image cases | Does not exhaust combined linked scenes |
| Raster writes, cycle patterns, postload | Ordering, access eligibility, cache invalidation | Not exact bus scheduling or real mid-field save reconstruction |
| TVMD, EXTEN, V-counter, sync | Production control flow and tables | Recording devices, not physical beam timing |
| Related VDP1 / SCU / SH-2 / sound tests | Preserve prior component regressions | Not a substitute for whole-VDP2 acceptance |

See [linked runtime instructions and recovery provenance](linked_runtime.md).
Historical lost-checkout results are explicitly separate from current execution.
User-accepted AB2 boot/explosions, Power Drift cars and OutRun flashing remain
narrow acceptance. The separate title/logo issue remains unresolved.

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
  - [x] **V2-A04c** Linked isolated NBG0–3 legal cell/bitmap depth, 16x16 flip and high-bank matrix passes at both capacities; RBG0 11-bit cell retained. Not all sizes/boundaries/combinations.
  - [ ] NBG0–3, bitmap/cell, legal color formats, page/plane boundaries, flips and transparency.
  - [ ] Clipped updates versus an equivalent full-frame reference.
  - [x] **V2-A04d** Bounded linked NBG0/NBG1 priority, ratio-source and additive scenes pass at both capacities; all-layer/effect combinations remain open.
  - [ ] Negative mutations for each newly covered behavior.
- [x] **V2-A05a** Correct mode-0 write broadcast and test legal word/longword lanes, independent reads and immediate/rebuilt palette agreement.
- [x] **V2-A05b** Preserve physical CRAM banks across mode changes and test coefficient reads.
- [x] **V2-A05c** Stateful legal CRAM writes/mode reinterpretation and callback decision/pre-write-memory audit; byte-array oracle and three assertion-rejected mutants. Not RAMCTL dispatch or hardware timing.
- [ ] **V2-A05** Audit CRAM mode-0 storage/read aliases and legal word/longword writes before relying on the palette as an oracle.

### P1 — Correct composition and ordinary visual effects

- [x] **V2-C01b** Enforce normal-screen color-depth resource exclusions from ST-058 p.61.
- [x] **V2-C01a** Preserve decoded pixel coverage separately from RGB in rotation caches; verify opaque-black and transparent source dots.
- [x] **V2-C01c** Ordinary raw-second source selection after coverage/window/priority filtering; extended and layer-identity effects remain open.
- [ ] **V2-C01** Establish per-pixel source identity/priority/eligibility sufficient for correct effect selection.
  - [x] Ordinary top/raw-second selection (C01c); extended selection remains open.
  - [ ] Same-priority tie order and priority-zero suppression.
  - [ ] All sprite types and palette/direct-RGB encodings.
- [x] **V2-C02a** Layer-selective normal/transparent shadows and type-2–7 self-shadow, after color operations; all-type extracted scanout tests.
- [ ] **V2-C02** Implement/qualify normal and MSB shadows across opaque and calculation paths.
  - [x] **V2-C02d** Linked identity-rotation RBG0 shadow eligibility/rank and post-calculation/offset order at both capacities. Not transformed sampling, RBG1, coefficient precision or hardware timing.
  - [x] **V2-C02c** Linked NBG0–3/back eligibility, zero/below/tied/above sprite rank, and normal-MSB precedence at both capacities. Rotation, other framebuffer/mixed modes and timing remain open.
  - [x] **V2-C02b** Linked word-sized normal codes, type-2–7 transparent/self shadows, NBG0 eligibility and post-calculation/offset order at both capacities. Other underlying layers, priority crossings, mixed/readout modes and timing remain open.
  - [x] SDCTL eligibility based on actual underlying layer (C02a); linked qualification open.
  - [ ] Sprite-window conflicts, transparent shadow codes and priority interactions.
- [x] **V2-C03a** Apply rotation/parameter windows on per-dot coefficient paths and preserve partial-clip source origins; add 9,216 image cases.
- [x] **V2-C03b** Preserve no-transform rotation windows and audit shortcut eligibility; test wrapper/cache configuration.
- [x] **V2-C03c** Calculation-only W0/W1/SW windows and normal/sprite SW area/cache integration.
- [ ] **V2-C03** Complete window behavior.
  - [x] **V2-C03e** Linked three-window W0/W1/SW matrix: all retained-area polarities, both logic settings, coverage/calculation, normal-resolution NBG0 and both capacities. Other layers, line/rotation mixtures and timing remain open.
  - [x] **V2-C03d** Linked displayed-framebuffer MSB windows: types 2–7, both retained areas, coverage/calculation and both-bank save replay. Normal 16-bit scanout only; timing/all-mode acceptance remains open.
  - [x] **V2-C03b** Linked W0/W1 line-table sampling, independent physical wrapping, inverted rows and coverage/calculation-only combinations pass in normal resolution. Not interlace, exact fetch timing or all sprite/rotation combinations.
  - [x] **V2-C03a** Linked W0/W1 coverage/calculation-only boundary, overlap and disabled-window matrix passes in normal resolution at both VRAM capacities. Not line/sprite/rotation/all-mode coverage.
  - [ ] Window 0/1 boundaries, line windows, AND/OR and disabled-window neutral values.
  - [ ] Sprite-derived mask as a real window input.
  - [ ] Calculation-only windows and rotation-parameter windows.
  - [ ] Partial clips, interlace and high/exclusive resolution coordinates.
- [ ] **V2-C04** Complete special priority and special color calculation.
  - [x] **V2-C04c** Linked NBG0 four-bit bitmap priority/code/attribute and all special-calculation modes pass, including zero promotion/suppression, CC-enable subordination, CRAM MSB, combined modes and save/load. Other formats/layers/modes remain open.
  - [x] **V2-C04a** SFCCMD eligibility from pattern/bitmap attributes, SFSEL/SFCODE and CRAM MSB, integrated with normal and rotation samplers.
  - [x] **V2-C04b** SFPRMD, SFCCMD, SFSEL/SFCODE and pattern/bitmap/dot attributes, including bounded frame-pass scheduling.
  - [x] Eligibility and priority filtering before blending; general/extended underlying-image composition remains C01/C05 work.
- [x] **V2-C05a** Separate sprite calculation eligibility from zero ratio; test all ratios/selectors and additive mode.
- [x] **V2-C05b** Ordinary raw-second ratio provenance, CCRTMD including sprite selectors and disabled lower-layer calculation, and line/back CCRLB.
- [x] **V2-C05c** Top-only post-calculation signed A/B offsets and table-12.1 second-format restrictions.
- [ ] **V2-C05** Qualify ordinary ratio/additive calculation and color-offset ordering.
  - [x] **V2-C05b** Linked post-calculation top offset, lower-offset isolation, signed saturation and A/B selection pass, including register mutation/save/load.
  - [x] **V2-C05a** Linked two-background all-32-ratio/top-or-second-source, top-enable and additive saturation matrix passes; offsets and other combinations remain open.
  - [ ] Ratio extremes, integer rounding and overflow/clamping.
  - [ ] Correct second-image eligibility and sprite condition modes.
  - [x] Top-only signed A/B offsets after calculation (C05c); linked qualification open.
- [x] **V2-C06a** Extended raw-input format/enable/CRAM selection and fixed-ratio arithmetic; documented table/figure conflict remains unverified.
- [x] **V2-C06b** Gradation capture/halo/designated-rank selection and mode/line exclusion; edge/runtime qualification remains open.
- [ ] **V2-C06** Implement/qualify extended calculation, ratio-source selection and gradation controls.
  - [x] **V2-C06d** Linked no-line-color extended matrix: CRAM0/1/2, palette/RGB third, top/second enables, both ratio sources and both capacities. Line-insertion discrepancy, other orders/formats/modes and hardware timing remain open.
  - [x] **V2-C06c** Linked opaque NBG0/NBG1 gradation source/rank, enable and ratio matrix at both capacities. Separate-term rounding matches MiSTer, differs from Ymir nested averaging; hardware rounding, left-edge inputs and other modes remain open.
- [x] **V2-C07b** Sprite line-color insertion and line-ratio provenance in the shared compositor.
- [ ] **V2-C07** Integrate line-color screen as a proper calculation input.
  - [x] **V2-C07a** Linked ordinary single/per-line LNCL, physical wrapping, top insertion, line-ratio routing and lower-history isolation pass at both capacities, including save/load. Coefficients, other modes and combined effects remain open.
  - [ ] Single/per-line tables, enables, coefficients and ratio behavior.
  - [x] Production line-color gate removed with extracted compositor image coverage; linked combinations remain open.
- [ ] **V2-C08** Integrate mosaic per eligible layer.
  - [x] **V2-C08a** Linked NBG0 mosaic at four H/V sizes, scroll, transparent/lower-layer preservation, blending and VCSC suppression passes at both capacities, including save/load. Other layers/rotation/interlace/combinations remain open.
  - [ ] Source-sample origin, horizontal/vertical sizes and partial clips.
  - [ ] Prevent mosaic from modifying already-composited unrelated layers.
  - [ ] Rotation constraints and scroll/window/calculation combinations.
  - [x] Production mosaic source sampling enabled with extracted coverage; full parent qualification remains open.

### P2 — Scroll and rotation completeness

- [ ] **V2-S01** Qualify ordinary fractional scroll/zoom and implement reduction-enable limits.
- [x] **V2-S01b** Preserve fractional bitmap scroll phases and line-scroll table fractions. See S01c for shared character sampling.
- [x] **V2-S01a** Enforce documented ZMCTL restrictions on paired NBG2/NBG3 screens.
- [x] **V2-S01c** Shared fractional character/bitmap point sampling with ordinary zoom and image fixtures; linked qualification open.
- [ ] **V2-S02** Complete line-scroll, vertical line-scroll, line-zoom and vertical cell-scroll combinations.
  - [x] **V2-S02b** Dispatch standalone vertical cell scroll and restore legacy column-pass state; shared sampler supersedes normal complex-scroll routing.
  - [x] **V2-S02a** Correct packed interval addressing, partial-clip containment, unsigned line zoom and descriptor restoration; retain equivalent-entry batching.
  - [x] **V2-S02c** Combined point sampling, table stride/interval, NBG0/NBG1 interleaving, source-cell screen-left anchoring and wrapping (stand-in images).
  - [x] Bounded point/column lookups without nested redraw; real frame-time qualification remains open.
- [ ] **V2-R01** Implement and qualify screen-over-pattern mode using OVPNRA/OVPNRB. Base pixels and shared special-function metadata implemented; compositor/runtime qualification remains open.
  - [x] **V2-R01a** Decode and composite repeated OVPNRA/OVPNRB character pixels, with bounded per-pass decoding and clip/dispatch regression coverage.
  - [x] **V2-R01b** Shared special color-calculation attributes/code/MSB through ordinary and screen-over sampling.
  - [x] **V2-R01c** Shared character/dot special priority, effective-zero suppression and priority-pass filtering, including OVPNRA/B.
- [ ] **V2-R02** Qualify rotation A/B parameters, fixed-point precision and coefficient tables.
  - [x] **V2-R02a** Validate packed parameter fields and correct Px sign extension; exercise signed short/long coefficient screen-over boundaries.
  - [x] **V2-R02b** Wrapping coordinate arithmetic and short/long viewpoint formats; signed-limit image oracle.
  - [x] **V2-R02c** VRAM/CRAM bank/partition permissions and per-line/per-dot routing; invalid-fetch fallback is reference-modeled, not hardware-qualified.
  - [x] Repeat, transparent and 512×512 screen-over modes exercised by production signed-boundary images; hardware/runtime qualification remains open.
- [ ] **V2-R03** Complete parameter-selection modes and read-control behavior.
  - [x] **V2-R03a** Select mode-2 A/B before coverage/composition and enforce B per-line coefficients when A is per-dot.
  - [x] Window selection with and without a geometric transform: production rotation/window combined images, including W0/W1/SW.
  - [x] **V2-R03d** Framebuffer-backed sprite-window selection for RBG0/RBG1 and RPMD 3, shared area/logic handling and postload cache invalidation.
  - [x] **V2-R03b** One-shot scanline RPRCTL accumulation, normalized history, reset/save registration and row-cache dispatch.
  - [x] **V2-R03c** Coefficient-based switching and basic line-color interaction; general/extended composition still depends on C01/C05.
- [x] **V2-R04d** Bitmap source write-watch ranges and independent A/B cache invalidation on VRAM-size changes; extracted tests.
- [ ] **V2-R04** Qualify RBG1/NBG0 sharing, resource restrictions and rotation caches.
  - [x] **V2-R04a** Separate inherited normal-scroll state, select RBG1 output-window controls and enforce dual-rotation screen exclusions.
  - [x] **V2-R04b** Watch full format/size-dependent character extents and wrapping accesses for rotation-cache invalidation.
  - [x] **V2-R04c** Integrate horizontal rotation mosaic, source selection, split-clip anchoring and bounded coefficient reads; hardware ordering/interlace qualification remains open.

### P3 — Raster state and VRAM bus behavior

- [x] **V2-T01a** Preserve completed visible lines before changed render-register/CRAM/VRAM and TVMD/VRSIZE writes; scanline granularity only.
- [ ] **V2-T01** Preserve scanned output before render-affecting register/CRAM/VRAM writes.
  - [ ] Define latch granularity from primary documentation, not an unconditional flush on every write.
  - [ ] Verify memory changes, color offsets, windows, scroll and priority changes independently.
  - [ ] Ensure active VDP1 erase-triggered updates do not duplicate or lose rendering.
- [x] **V2-T02a** Restrict cycle-command presence to active mode slots, partition-selected registers and non-rotation-owned banks.
- [ ] **V2-T02** Implement bank/slot-aware cycle-pattern validation and fetch behavior.
  - [ ] Bank partitioning, access-command counts/order and screen-mode bandwidth. Addressed-bank PN/CP permission and early-slot/order VCSC consumers implemented; counts, PN→CP scheduling and bandwidth remain missing.
  - [ ] RBG1 and coefficient/table fetch restrictions.
  - [ ] CPU availability/contention and insufficient-fetch consequences, supported by hardware evidence.
- [x] **V2-T03a** Wrap W0/W1 line-window and back-table row addresses at the configured physical VRAM size; production boundary fixtures.
- [x] **V2-T03b** Configured bitmap and legacy scroll-table wrapping; format/size-aware bitmap watch ranges and VRAM-size cache keys.
- [x] **V2-T03c** Wrap every rotation-parameter and retained line-color table fetch to physical size; decoding/latch/line indexing unchanged.
- [x] **V2-T03d** CPU read/write physical aliases and decode/cache/preservation coherence; extracted handler tests, not bus timing.
- [x] **V2-T03e** Legacy cell-map bases, final name-fetch masks and physical plane watch extents; extracted arithmetic tests.
- [x] **V2-T03f** RGB555/RGB888 retained character base/row physical wrapping, zoomed/unzoomed production-helper images.
- [x] **V2-T03g** Retained palette renderer physical character codes and final 8-bit wrapped cell; remove previous-character substitution.
- [ ] **V2-T03** Qualify VRAM size/address masking and cache invalidation for all consumers.

### P4 — Display timing and external interfaces

- [ ] **V2-H01** Qualify NTSC/PAL field lengths, half-lines, ODD and H/V counter wrap/latch edges.
- [ ] **V2-H02** Qualify interlace and exclusive modes, clock changes and SMPC DOTSEL coordination.
- [ ] **V2-H03** Audit external latch/sync flags and reset behavior against real callback timing.
- [ ] **V2-H04** Implement external-background/MPEG/genlock input and composition where supported.
  - [ ] Keep external-device input provisioning separate from the VDP2 mixer.
  - [ ] Explicitly identify any configuration for which the external source is absent.

### P5 — Save/reset, performance and acceptance

- [x] **V2-Q01a** Deterministic device startup/status reset and postload render/cache invalidation, preserving saved rotation history; extracted qualification only.
- [ ] **V2-Q01** Audit register, memory, decoded state and all derived caches across reset/postload.
  - [ ] Window/fade/rotation caches and any new per-pixel/raster state.
  - [ ] Mid-line and mid-field save/load with no stale picture or duplicate event.
- [x] **V2-Q02** Focused executable linked; `-validate` passes for 122 runnable systems with no diagnostics.
  - [x] **V2-Q02a** Resolve SDL/pkg-config dependencies: external bootstrap executed successfully after recovery.
  - [x] **V2-Q02b** Link and `-validate` re-executed on recovered source.
  - [x] **V2-Q02c** After the later workspace reset, full link restored with identical executable hash; 122-system validation, 2,048 synthetic cases and four BIOS replays refreshed following 192f00fb.
- [ ] **V2-Q03** Run real MAME save/load and BIOS/Saturn/ST-V visual smoke tests.
  - [x] **V2-Q03a** JP/PAL/ST-V DRC and JP interpreter visible BIOS save/advance/load/replay pass; not games.
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

## Implementation-first continuation — rotation bank ownership

IMPL-0137 adds addressed-bank PN/CP permissions for rotation scanout: RBG0 uses
RAMCTL's effective name/character designations, while RBG1 uses fixed B1/B0 and
excludes RBG0 from those image banks. Active rotation output uses transformed
point sampling, avoiding stale RGB-cache pixels across ownership changes.
Sega ST-058 pp.148–150 and pinned Mednafen, MiSTer and Ymir source references
are recorded in the append-only implementation handoff.

Denied fetches use the existing transparent fallback policy, not a claimed
hardware stale-latch value. Both VRAM capacities are addressed; no new saved
fields. TU syntax/diff checks only, no validator tests or gameplay claims.
V2-T02 and V2-R04 remain open for timing, failed-fetch behavior and qualification.

Candidate IMPL-0138 shares the existing postload memory-view rebuild with the
system-reset RAM-clear path. Byte-decoded graphics, decoded tiles, retained RBG
source caches and base palette colors now follow the changed VRAM/CRAM instead
of retaining old pixels. This does not change the existing clearing policy or
claim hardware zero-filled reset RAM. No new saved fields; syntax/diff checks
only. Detailed primary/three-peer references and proposed falsifier are in the
append-only handoff; V2-T03/V2-A05 remain open.

Candidate IMPL-0139 routes SMPC SYSRES to the existing VDP2 device reset. The
previous driver-array clear missed device-owned TVMD/EXTEN/VRSIZE and decoded
CRTC controls. No clock-selection or sound-reset code changed. Sega SYSRES and
VDP2 reset documentation plus Mednafen/MiSTer/Ymir routing are recorded in the
handoff. Syntax/diff checks only; no new saved state or parent completion claim.

Candidate IMPL-0140 connects the VDP2 device reset to the driver-owned rendering
registers on both Saturn and ST-V. Machine/device/clock-change resets now clear
those controls too, invalidate dependent caches/latches and reinterpret retained
CRAM using reset mode0. The clock-selection/sound-reset body is unchanged, and
the callback does not erase VRAM/CRAM. No new saved fields. Four touched TUs syntax
checked; ST-V required its shared include path and generated layout headers.
No validation runs; see the handoff for primary/three-peer contracts and limits.

Candidate IMPL-0141 corrects sprite SPCCCS3 eligibility: palette sprites use the
selected CRAM color's MSB after SPCAOS/CRMD addressing, not framebuffer bit15.
Direct RGB continues to qualify directly. A shared helper preserves the existing
background SFCCMD3 behavior. Sega pp.205/207 and all three peers support this.
Source inspection found old raw-pixel-bit expectations in test_sprite_scanout.py;
the handoff reports them for the validator, with no fixture edits or test runs.
Syntax/diff checked only; V2-C01/V2-C05 qualification remains open.

Candidate IMPL-0142 replaces VDP2 RGB555 bit replication with the documented
three-zero-bit expansion, consistently across palette, direct-color, sprite and
back-screen sources. Channel31 now enters VDP2 arithmetic as248, not255; RGB888
and VDP1 drawing/storage are unchanged. Sega p.43 and all three peers agree.
The handoff identifies stale full-range fixture assumptions without editing or
running them. Syntax/diff checks only; no saved fields or gameplay acceptance.

Candidate IMPL-0143 removes a second single-density-interlace scaling of NBG0/1
line-scroll intervals. MAME's single-density bitmap already uses picture rows,
so table cadence is1/2/4/8 rows just as in non-interlace. Sega's physical-line
counts and all three peers' counter representations are reconciled in the handoff.
Non-interlace/double-density setup values and CRTC timing are unchanged. Syntax/
diff checks only; no fixtures changed or validation runs. V2-S02 remains open.

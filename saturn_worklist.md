# Saturn Work List — ordered by reference coverage (5 refs: Ymir, MiSTer, mednafen, yabause, SaturnRecomp)

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
See [reproduction, evidence and limits](regtests/saturn/linked_runtime.md).

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

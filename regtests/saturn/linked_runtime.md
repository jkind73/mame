# Linked Saturn / ST-V qualification

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

Pinned sources:
- Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, ST-058 PDF blob
  `64ba1bac76427b122bf4c10a557d1a3cec29c3a1`, printed pp.53, 60–61, 69–75.
- [Ymir cell index and fetch](https://github.com/StrikerX3/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp#L5073-L5108),
  and [cell stride](https://github.com/StrikerX3/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp#L5197-L5225).
- [MiSTer pattern/character addressing](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/VDP2/VDP2_pkg.sv#L1731-L1878),
  `PNData` H/V fields and `NxCHAddr` cell ordering / 16-bit stride.


## Recovery status — 2026-09-16

The sandbox restoration lost unpushed commit `ade338f9` and its linked executable,
SDK and runtime captures. The source fixes and tools have been reconstructed on
`81eb1b74`. **Current executed evidence:** 46 regression scripts, eleven production
object compilations with narrowing errors enabled, nine rejected targeted mutations,
and successful external SDK provisioning. A new linked build and runtime replay
are pending. Do not treat the historical results below as current-tree acceptance.

Restored production corrections:
- Six MPOFN/MPOFR map offsets preserve bit 2 (ST-058 pp.85–86).
- Console/ST-V expose the whole 1 MiB aperture to capacity-aware handlers (ST-058
  §3.1), rather than discarding the high bit through a fixed 512 KiB map mirror.
- Plain 11-bit palette cells select the existing point sampler at normal dispatch,
  rotation dispatch and rotation source selection (ST-058 pp.69–74). Cached 4/8-bit
  routes remain intact. No game-specific shortcut or wholesale emulator merge.
- Sixty intentionally undumped EEPROM placeholders explicitly initialize to FF.
  Dumped EEPROMs and existing blank-detection/factory synthesis are unchanged.
- The full validator invokes the actual `saturn` executable, not `mamesaturn`.

## Reproduce

Use normal SDL2, SDL2_ttf and fontconfig development packages where available. For
this restricted Linux x86-64 environment, an optional external SDK bootstrap uses
pinned upstream SDL/X11/glvnd headers/sources and pygame runtime libraries. This is
a headless qualification setup, not an OSD or graphics-backend change:

```sh
python regtests/saturn/bootstrap_linked_deps.py --prefix /home/user/.cache/saturn/linked-sdk
. /home/user/.cache/saturn/linked-sdk/build-env.sh
CXXFLAGS='--param=ggc-min-expand=10 --param=ggc-min-heapsize=32768' \
  python regtests/saturn/validate_build.py --full --jobs 1
python regtests/saturn/run_vdp2_runtime.py \
  --executable ./saturn --rompath ./regtests --system saturnjp --drc \
  --output /home/user/.cache/saturn/runtime-jp
python regtests/saturn/run_vdp2_runtime.py \
  --executable ./saturn --rompath ./regtests --system saturnjp --drc --bios \
  --boot-frames 900 --output /home/user/.cache/saturn/bios-jp
```

For the 818-case composition matrix, add `--composition` (mutually exclusive
with `--bios`) and use a separate output directory:

```sh
python regtests/saturn/run_vdp2_runtime.py \
  --executable ./saturn --rompath ./regtests --system saturnjp --drc --composition \
  --output /home/user/.cache/saturn/composition-jp
```

Within each capacity, composition cases 1–3 cover priorities, 4–35 top-selected
ratios, 36–67 second-selected ratios, 68 additive saturation, 69 disabled top
calculation, 70–73 offsets, 74–85 coverage windows, 86–97 calculation-only windows,
98–101 coverage line windows, 102–105 calculation-only line windows, and 106–113
mosaic. The latter alternate plain/blended scenes at 1x1, 3x5, 16x16 and 7x2 sizes.
Cases 114–117 exercise single-color LNCL and 118–121 per-line LNCL: top insertion,
line-selected ratio, lower-history isolation and disabled top calculation.
Cases 122–133 cover special-priority modes/attributes/selectors; 134–135 cover
priority promotion/demotion through zero; 136–167 cover special-calculation
modes/attributes/selectors/CC enable; 168–169 combine special priority with MSB
calculation. Cases 170–193 cover sprite-window types 2–7, coverage/calculation and retained areas. Cases 194–225 cross all three-window area polarities, logic settings and uses. Cases 226–233 cover gradation source, enable and ratio selection. Cases 234–281 cover extended calculation with RGB third; 282–329 use palette NBG2 third. Each group crosses CRAM0/1/2, extended enable, second enable, ratio source and top enable. Cases 330–361 cover normal shadows; 362–409 cover transparent/self MSB shadows for types 2–7. Cases 410–818 repeat at the larger capacity. Line scenes use table bases at physical
capacity minus 16 and 0x60000, swapping which window wraps. Their foreground bitmap
uses map 2 and their blue back word is at 0x5fffe, disjoint from both tables.
The composition watchdog is 120 emulated seconds; completion still requires all
818 ordered case records and the exact final marker. Sources are red over green;
additive saturation changes the lower source to yellow. Window scenes change expected colors per coordinate using retained-area predicates.
Mosaic scenes replace the solid source data with a transparent/red/green foreground
and yellow/white lower screen. Their source sample is displaced by scroll (5,7);
the lower screen is sampled at the destination dot. The nine-line VCSC poison table
must be ignored even when enabled mosaic has unit size. These checks do not measure
fetch timing or certify other mosaic/interlace modes.

Line-color scenes use the last eight bytes of physical VRAM as the table base,
so per-line entries cross the boundary between rows 3 and 4. The displayed bitmap
and back word move away from that table. Table pen codes 5 (blue) and 3 (yellow)
include ignored upper bits, and line ratio 7 differs from top ratio 15 and lower/back
ratio 31. Probe rows include 0, 1, 2, 3, 4, 5, 7, 8, 17, 63, 127 and 223.

Special-function scenes use code 0 as transparent, code 1 as red (CRAM MSB set),
code 2 as green (CRAM MSB clear), and an opaque blue lower screen. SFCODE selects
code 2 through set A and code 1 through set B. Bitmap priority/CC attributes are
independent of palette-number bits. Analytic expected effective priorities choose
the winning dot before deciding whether ordinary 50:50 calculation is eligible.

Scene selection and expected colors are independent of production renderer routines. Output screenshots are not
hardware-derived reference images.

Repeat for `saturneu` and `stvbios`; omit `--drc` for interpreter execution. ROMs
must be supplied by the user. Outputs, SDK, generated objects, snapshots and save
states stay outside Git. The runner checks PASS markers, not merely exit status:
Lua assertions may otherwise leave an emulator process exit code of zero.

Synthetic mode settles 180 frames then holds both SH-2s in RAM loops. The expanded
46-case matrix is specified above. Each checks sixteen independently expected
color probes, schedules a real save, mutates VRAM, CRAM, priority,
CRAM mode and VRSIZE to blue output, loads, checks restored state and full-image
identity. It exercises the linked CPU maps, renderer and save manager, not games.

BIOS mode makes no injected CPU/register/memory changes. After 900 frames it saves,
advances half a second, loads and replays to the same emulated time, checking PC and
full image. A nonuniform RGB check ignores alpha and rejects blank-screen equality.
Retained notifier subscriptions prevent Lua garbage collection unsubscribing them.

## Historical evidence (lost artifacts, not re-executed recovery acceptance)

Before restoration, the lost integrated checkout linked and passed `-validate`
for 122 drivers without errors/warnings. Its 42 DRC synthetic cases passed across
JP/PAL/ST-V. Visible 900-frame DRC BIOS replay passed on all three; JP interpreter
also passed. Observed JP date/time, PAL language setup and ST-V BIOS-only cartridge
error screens. Reported DRC reference states were:

| BIOS | Time (seconds) | Main SH-2 PC |
|---|---:|---|
| JP | 15.560998664 | 06040226 |
| PAL | 18.439710253 | 060402e6 |
| ST-V | 15.543578728 | 060154b8 |

Those captures, executable hash and logs are no longer available to inspect. A new
run must produce its own evidence; numerical equality is not a promised result.

## Remaining acceptance

Full VDP2 remains incomplete. Neither this synthetic matrix nor BIOS replay closes
slot/address/count fetch arbitration and contention, exact register latch timing,
mid-line/mid-field saved-picture reconstruction, external MPEG/genlock, combined
effects/interlace and hardware/precision discrepancies, title/game acceptance, or
comparative performance. The extended-color CRMD0 line-color table's printed
2:1:0 versus implemented/cross-emulator 2:1:1 remains an explicit primary-source
discrepancy. No hardware certification or measured speedup is claimed.

## Offset/window cross-check locations

- Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, ST-058 PDF blob
  `64ba1bac76427b122bf4c10a557d1a3cec29c3a1`: pp.189–195 distinguish active
  window areas from their retained complements; pp.250–252 specify post-calculation
  top-screen offset enable/select and signed saturation.
- Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, renderer lines 4187–4195:
  final-output offset uses the top layer's selected offset bank.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`, VDP2 package lines
  2423–2429: signed offset, bank selection and saturation. The `WinTest` helper's
  all-disabled branch returns zero for either LOG value; that helper alone is not
  a complete caller-level comparison. The fixture follows Sega's explicit p.194
  all-disabled rule rather than importing that helper's result as an oracle.

## Line-window cross-check locations

- Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, ST-058 PDF blob
  `64ba1bac76427b122bf4c10a557d1a3cec29c3a1`, printed pp.184–187.
- Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, software renderer
  lines 2372–2424: vertical bounds checked separately; per-row start/end fetched
  at table base plus four bytes per row. Its out-of-range compatibility behavior
  and other display-mode indexing are not imported as an oracle.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`, `VDP2.sv`
  lines 1312–1314, 1462–1464 and 2144–2190: paired word addresses, fetched
  horizontal bounds and separate vertical bounds. Field/address scheduling and
  out-of-range conventions are outside this normal-resolution fixture's claims.

## Mosaic cross-check locations

- Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, ST-058 PDF blob
  `64ba1bac76427b122bf4c10a557d1a3cec29c3a1`, printed pp.117–119:
  upper-left source, 1–16 dot sizes, per-layer enable and VCSC suppression.
- Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, renderer
  lines 4544–4569: per-layer horizontal mosaic takes priority over vertical-cell
  scroll. This is corroboration, not an independent linked/hardware oracle.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`, `VDP2.sv`
  lines 1683–1694 and 3018–3022: VCSC contribution masked when MZE is set,
  vertical/horizontal counters use the programmed size. Other pipeline timing
  and interlace conventions are outside this fixture's acceptance.

## Line-color cross-check locations

- Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, ST-058 PDF blob
  `64ba1bac76427b122bf4c10a557d1a3cec29c3a1`, printed pp.172–174:
  table format/address and single/per-line selection; p.231 top-screen LNCL
  insertion; pp.241–244 calculation enable and ratio selection.
- Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, renderer
  lines 2596–2601, 4049–4066 and 4128–4140: table color, top-layer LNCL
  selection and replacement of the second image in ordinary calculation.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`, `VDP2.sv`
  lines 1328,1466,3291–3296 and 3478–3483: table stepping, per-layer enable
  and selected second-image ratio. Extended calculation disagreements recorded
  elsewhere are not resolved by these ordinary-calculation tests.

## Special-function cross-check locations

- Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, ST-058 PDF blob
  `64ba1bac76427b122bf4c10a557d1a3cec29c3a1`, printed pp.228–229:
  priority LSB replacement, bitmap attribute source and effective-zero suppression;
  pp.245–247: four calculation modes subordinate to top-screen enable.
- Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, renderer
  lines 5273–5285 and 5348–5364: attribute/code/MSB eligibility and priority LSB.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`, `VDP2_pkg.sv`
  lines 2436–2451: code-set selection; `VDP2.sv` lines 3226–3248 and
  3481–3483: special priority, calculation enable and top color-MSB gate.
  These are cross-checks, not hardware oracles or complete format/mode coverage.

# Linked Saturn / ST-V qualification

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

For the 226-case two-background composition matrix, add `--composition` (mutually exclusive
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
Cases 114–226 repeat at the larger capacity. Line scenes use table bases at physical
capacity minus 16 and 0x60000, swapping which window wraps. Their foreground bitmap
uses map 2 and their blue back word is at 0x5fffe, disjoint from both tables.
The composition watchdog is 120 emulated seconds; completion still requires all
226 ordered case records and the exact final marker. Sources are red over green;
additive saturation changes the lower source to yellow. Window scenes change expected colors per coordinate using retained-area predicates.
Mosaic scenes replace the solid source data with a transparent/red/green foreground
and yellow/white lower screen. Their source sample is displaced by scroll (5,7);
the lower screen is sampled at the destination dot. The nine-line VCSC poison table
must be ignored even when enabled mosaic has unit size. These checks do not measure
fetch timing or certify other mosaic/interlace modes.

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

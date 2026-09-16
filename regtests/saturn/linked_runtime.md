# Linked Saturn / ST-V qualification

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

For the 194-case two-background composition matrix, add `--composition` (mutually exclusive
with `--bios`) and use a separate output directory:

```sh
python regtests/saturn/run_vdp2_runtime.py \
  --executable ./saturn --rompath ./regtests --system saturnjp --drc --composition \
  --output /home/user/.cache/saturn/composition-jp
```

Within each capacity, composition cases 1–3 cover priorities, 4–35 top-selected
ratios, 36–67 second-selected ratios, 68 additive saturation, 69 disabled top
calculation, 70–73 offsets, 74–85 coverage windows and 86–97 calculation-only windows.
Cases 98–194 repeat at the larger capacity. Sources are red over green;
additive saturation changes the lower source to yellow. Window scenes change expected colors per coordinate using retained-area predicates.
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

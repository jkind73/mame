# Prior PR description

Historical description before consolidation. Superseded status statements are
not current acceptance claims; use the live PR description and README.md.

Current source `2781f96b`: applied VBlank expiry and initialized/reset/save-registered H/V edge history after four linked negative cases on 234c. Native rebuild is pending; focused extracted/edge/mutation/full-TU checks pass. **234c7abc live PASS**: all six two-multitap cases and real partial-report save/mutate/load, plus the complete CD/cart/backup/timer/BIOS/background gate. Baseline 5008 composition now passes all four configurations (4,168 cases). Artifact transfer is solved through an independently checksum-verified temporary GitHub API blob; draft release remains unpublished. No user ZIP upload is needed for 234c. No working flags promoted.

Current checkpoint: prepared (NOT applied) reference-backed VBlank timeout plus deterministic/save-registered H/V edge history. 73,728 compiled state checks + four edge/order checks pass; eight compiled mutants rejected and both full translation units pass syntax checks. The partial-report file-save fixture now freezes emulated time during host I/O and passes its old-binary negative/control runs. Baseline PAL DRC composition: all 1,042 cases passed. Native build 35291979814 succeeded, but its artifact transfer is still blocked; the production input trees remain identical to built source 234c7abc.

Checkpoint `fab6ebe7`: native SMPC build 35291979814 succeeded (source 234c7abc); artifact transfer is blocked by Azure EOF, so new-source live acceptance remains pending. Added a scheduled partial-report save/mutate/load gate: 14 fake-runner controls pass, existing 10 controls pass, and the old verified 5008 binary completes real save/load notifications but fails the expected transport assertions. No buffer-save shortcut or working-flag promotion.

Additional verified baseline result: all 1,042 JP DRC composition/pixel/save-replay cases passed on binary 5008a923 (log pushed). Earlier live CD/cart/backup/timers, 184 backgrounds and four BIOS replays also passed. New integrated SMPC source has a full 54-script ROM-free pass and an active native rebuild (35291979814); no positive live result is attributed to that new source yet.

Integrated SMPC source `234c7abc` now passes the full 54-script regression batch (three default-binary live skips excluded from acceptance). Native rebuild https://github.com/jkind73/mame/actions/runs/35291979814 is compiling. Verified baseline `5008a923` already passed CD/cart/backup/timer and four BIOS/background replay configurations; new multitap live-positive testing awaits the rebuilt binary. Baseline-only JP DRC composition testing is also in progress.

Current integration `234c7abc`: uploaded CI binary verified and the live baseline passed (CD/cart/backup RAM, SCSP timer matrix, JP DRC/interpreter + PAL/ST-V DRC BIOS/background replays). ST-V is the expected no-cartridge error screen, not game acceptance. Real two-multitap negative test reproduced bad NPE, OREG31 clobber, missing tail and wrong port modes. The SMPC transport fix is now applied; 5,402 transport cases, 1,175 handshake cases, six rejected compiled mutants and syntax checks pass. New native build/live positive test still required. Text baseline evidence is pushed in `saturn_pending/evidence/5008-live/`; no ROMs or states included.

Native CI PASS: https://github.com/jkind73/mame/actions/runs/35287467065 at `5008a923` completed build, -validate and ROM-free regressions. Artifact ID 10526830262 (16,305,765 bytes) and GitHub ZIP digest are recorded in `saturn_pending/ci-35287467065.json`. Local BIOS/device execution is BLOCKED on ZIP transfer: outbound artifact TLS closes and inbound preview requires an access token; no token/protection bypass occurred. User ZIP ingestion independently checks GitHub digest then source/binary provenance. No BIOS/gameplay/save-manager acceptance claimed; SMPC transport remains a tested pending patch.

Runtime preparation: real SDL 2.28.4 and SDL_ttf 2.20.1 now load through the standard SONAME aliases expected by the Ubuntu CI binary, with no missing SDL_ttf dependencies. This avoids a known local-loader mismatch without replacing implementations. CI 35287467065 remains in compilation; actual MAME/BIOS execution is not yet claimed. The live multitap fixture is pushed and its syntax/protocol tests pass, not its hardware test.

GCC12 CI run 35287467065 is now compiling. Prepared a live two-multitap CPU-register fixture (12 distinct pad patterns, 38/19-byte reports, status/peripheral-only requests, retained second-page data). Python/Lua syntax and ten fake-runner controls pass; actual live execution is pending and expected to reject the pre-transport binary. Pending transport implementation is unchanged and unapplied.

Latest checkpoint `0d16de3f`: general CI now cancels superseded runs only on the session branch; existing job definitions and other-branch behavior are unchanged. Dedicated Saturn CI remains non-canceling and its GCC12 run 35287467065 is still queued. The combined SMPC transport candidate is preserved in `a6e83105`, with 5,402 packet cases, 1,175 handshake cases, six rejected mutants and syntax checks; unapplied and not live-validated. No working flags changed.

New pending implementation: `saturn_pending/smpc-transport.patch` supersedes the mode-only candidate. It snapshots existing-format controller reports, streams all OREG bytes across continuation pages, sets PDL/NPE correctly, honors zero-byte ports and preserves/reset-clears packet state. 5,402 extracted transport cases, 1,175 handshake cases and SMPC syntax pass; six compiled mutants are rejected. Not applied or live-validated; extended IDs/VBlank timeout remain open. GCC12 CI run 35287467065 is still queued; frozen production inputs are unchanged.

Current CI: GCC11 run 35287036055 failed in bundled ASTC encoder warning handling before Saturn compilation. GCC12 replacement: https://github.com/jkind73/mame/actions/runs/35287467065 at `5008a923`; no linked PASS yet. Artifact verification/local-runtime tools are pushed. Pending, unapplied SMPC port-mode fix has fresh primary-reference support, 576 passing control cases, 1,173 unchanged handshake cases and two rejected compiled mutants; current build inputs remain frozen.

Durable native build confirmed running: https://github.com/jkind73/mame/actions/runs/35287036055 at `31266601`. Repeated sandbox resets lost the previous local builds, so none are claimed passed. Added provenance-gated CI artifact consumption and local BIOS/device validation without another full rebuild; 12 synthetic verifier controls pass and runtime script syntax passes. No BIOS/game files uploaded. Live acceptance remains pending.

Fresh evidence: full ROM-free regression batch on `10579b9c` passed, with optional live-device skips explicitly excluded from acceptance. Added auxiliary three-timer/eight-prescaler live runner with correct SCIRE clear/reassert controls and 10 passing fake-executable protocol checks; actual linked execution pending. Native source/test inputs remain unchanged; build is active.

Current integrated WIP: `10579b9c` applies the previously reviewed legacy IOGA inspection and SCSP phase/save-origin/attotime fixes. Production-path extracted checks and SCSP/ST-V syntax checks pass; three compiled SCSP mutants fail. Workspace restoration lost the earlier build/logs, so no linked result is claimed. A fresh native validation starts against this revision. No working flags promoted.

Additional reviewed WIP: `saturn_pending/scsp-timer-phase.patch` preserves timer-origin save registration, phase-correct rearm and attotime-boundary reconciliation. 49,152 ideal-clock + 49,152 real-attotime cases and 24 reset cases pass; three compiled mutants fail. Candidate syntax checked, **not applied or linked-validated**. Active integration inputs still match `8f2c12ff`. Details and primary-reference discrepancy in `saturn_pending/README.md`.

Additional pushed recovery WIP: `saturn_pending/ioga-inspection.patch` preserves the next reviewed legacy ST-V counter-inspection fix and 5,124-case extracted fixture. It is not applied; active build/test inputs remain identical to `8f2c12ff`. Original code compiled and assertion-failed, candidate passed. Native `8f2c12ff` validation is still running.

Current WIP: `8f2c12ff` registers internal console backup RAM for save states and makes debugger HIRQ reads non-mutating. Extended extracted register tests, console syntax checking and 62 runner protocol cases pass; new real save/mutate/load coverage is prepared, not yet executed. Native integration validation resumed at this revision. Earlier cartridge/CD WIP remains included. No working/save flag promotion or Agent1 bus/CPU changes imported.

Current implementation WIP: `934a0754` integrates reviewed cartridge guards and CD DCHG reporting, with hardened live-test runners. Fresh extracted HIRQ/transfer/cart and failure-protocol checks pass; original read/empty-cart behavior is rejected by compiled negative controls. Linked build, boot/game/save acceptance remain pending. The follow-up commit checks in `regtests/saturn/validate_integration.sh` before the long run. No Agent1 CPU-wait code or driver promotion imported.

WIP preservation checkpoint: `4edfe4bc` backs up the recovered tracked diff and 114 untracked source/test/document files under `regtests/saturn/recovery/2026-09-17-workspace/`. Remote production code is unchanged. This is an unreviewed recovery artifact, not a validated integration; previous background jobs and external logs were absent after workspace recovery. ROMs/build downloads/runtime artifacts are excluded from this new checkpoint.

Current platform report: `a23c6c95` — [`saturn_stv_completion.md`](https://github.com/jkind73/mame/blob/arena/01a09f50-mame/saturn_stv_completion.md) contains 85 dependency-ordered parent checklist entries covering the shared motherboard, Saturn CD/peripherals, ST-V protection/cabinet hardware, optional expansions and whole-machine acceptance. Missing/partial/verification/research statuses are separated; existing VDP2 IDs and accepted fixes are retained. Documentation audit only; no new hardware or runtime acceptance is claimed.

Current implementation: `812ec7a8` — addressed-bank normal VDP2 PN/CP fetch permissions and early-slot/order VCSC gating. All 47 existing regression scripts pass as one batch; eight compiled mutations are assertion-rejected. Linked background fixture extended and Lua syntax checked. Full build/validate is still running; new linked/save-load/performance results are pending. T02 remains open: access counts, PN→CP scheduling/bandwidth, real fetch latches, complete rotation/table restrictions and CPU/SCU-DMA contention are not implemented. This is a preservation commit, not whole-parent or whole-VDP2 completion. Earlier linked totals below are historical.

Latest checkpoint: `8aa5408c` — linked shadow rank/layer/precedence. **4,096 synthetic cases** (978 composition + 46 background across four configurations), four fresh BIOS replays, 47 scripts/44 protocol cases, clean `-validate`. NBG0–3/back, zero/below/tied/above sprite rank and normal-MSB precedence covered; four extracted mutations rejected. Production unchanged; rotation/mixed modes/timing and full VDP2 acceptance remain open.

Latest checkpoint: `de4d8906` — linked normal/MSB shadows. **3,456 synthetic cases** (818 composition + 46 background across four configurations), four fresh BIOS replays, 47 scripts/44 protocol cases, clean `-validate`. Normal/transparent/self shadows and post-calculation/offset ordering covered; five extracted mutants rejected. Sega/MiSTer ordering retained; pinned Ymir disagreement documented. Production unchanged; full VDP2 acceptance remains open.

Latest checkpoint: `c6bfc2f9` — linked extended-calculation format/eligibility matrix. **2,816 synthetic cases** (658 composition + 46 background across four configurations), four fresh BIOS replays, 47 scripts/44 protocol cases, clean `-validate`. CRAM0/1/2, RGB/palette third image, top/second enable and ratio source covered; three extracted mutations rejected. Production unchanged. Line-insertion discrepancy and full VDP2 acceptance remain open.

Latest checkpoint: `8756e268` — full rebuild restored with identical executable SHA-256. Fresh 2,048 synthetic cases, four BIOS replays, 47 scripts, eleven objects and clean 122-system validation. Full VDP2 remains open.

Latest checkpoint: `192f00fb` — recovered pushed branch and added stateful CRAM audit. **4,096 stateful writes**, 234 mirror-only changes, 790 redundant writes; all 47 regression scripts freshly pass. Missing, redundant and late preservation mutants compile/assertion-fail. Production unchanged. Prior 2,048 linked cases/four BIOS replays are historical: reset removed executable/cache; no fresh linked/-validate claim. Full VDP2 remains open.

Latest checkpoint: `03a20495` — linked gradation. **2,048 synthetic cases** (466 composition + 46 background across four configurations), four fresh visible BIOS replays, 47 scripts, 44 protocol cases, clean `-validate`. Filter and halo mutations rejected. MiSTer/Ymir low-bit rounding disagreement documented; left-edge and hardware acceptance remain open. Production unchanged; full VDP2 incomplete.

Latest checkpoint: `ecb58edb` — combined W0/W1/SW logic. **1,984 synthetic cases** (450 composition + 46 background across four configurations); four BIOS replays retained from 40320fcc with explicit fixture hashes. All 47 scripts and 44 protocol tests pass, clean `-validate`; reversed SW combination mutant rejected. Production unchanged; full VDP2 acceptance remains open.

Latest checkpoint: `40320fcc` — linked sprite windows. **1,728 synthetic cases** (386 composition + 46 background across four configurations), four fresh BIOS replays, 47 regression scripts, 44 protocol tests, clean `-validate`. MSB and wrong-bank mutations rejected; both physical framebuffer banks overwritten before save-state replay. Production unchanged. Full VDP2 acceptance remains open.

## Linked special-function qualification PASS

Added 384 linked scenes: priority modes 0–2, bitmap attributes, both code selectors,
base-zero promotion/effective-zero suppression, all four calculation modes, CC-enable
subordination, CRAM MSB and combined priority/calculation metadata. JP/PAL/ST-V DRC
and JP interpreter, both capacities, 144 probes per scene and real save/mutate/load/
full-image replay pass. Both combined-selector captures were inspected.

Current evidence: **1,536 synthetic cases (1,152 DRC / 384 interpreter), four fresh
visible BIOS replays, 47 regression scripts and clean `-validate`**. Unchanged
production sources retain full-link/eleven-object evidence. Priority-zero/attribute
and special-MSB/code mutations fail extracted assertions. Primary ST-058 pp.228–229,
245–247 and pinned cross-check limits are recorded; fresh run/capture hashes are in
`regtests/saturn/linked_runtime_results.json`.

C04c qualifies normal-resolution NBG0 four-bit bitmaps, not all formats/layers/modes.
Exact bus/latches, external video, games/title and performance remain open. No
production correction was needed; full VDP2 is not declared complete. Older totals
below describe earlier checkpoints.

## Linked line-color qualification PASS

Added 64 linked LNCL scenes: single/per-line tables, physical wrapping, ignored upper
bits, top insertion, line-ratio selection, lower-history isolation and disabled top
calculation. JP/PAL/ST-V DRC and JP interpreter, both capacities, 48 probes per scene
(including the wrap and first/last visible rows), real mutation/load and full-image
replay pass. Per-line and lower-history captures were inspected.

Current evidence: **1,152 synthetic cases (864 DRC / 288 interpreter), four fresh
visible BIOS replays, 47 regression scripts and clean `-validate`**. Unchanged
production sources retain full-link/eleven-object evidence. Wrapping, table-mode,
line-ratio and lower-history mutations fail extracted assertions. Primary ST-058
pp.172–174,231,241–244 and pinned cross-check limits are documented; run/capture
hashes are in `regtests/saturn/linked_runtime_results.json`.

C07a is bounded ordinary NBG0/NBG1 qualification, not whole-VDP2 completion.
Coefficients/rotation/interlace/extended combinations, exact bus/latches, external
video, games/title and performance remain open. No production correction was
required by these scenes. Older totals below are historical checkpoints.

## Linked mosaic qualification PASS

Added 64 linked mosaic scenes: four H/V sizes, nonzero scroll, transparent top dots,
independently patterned lower layer, plain/blended composition, and a live nonzero
VCSC table that must be suppressed. JP/PAL/ST-V DRC and JP interpreter, both VRAM
capacities, 144 probes per scene and real save/mutate/load/full-image replay pass.
Plain and blended captures were inspected.

Current evidence: **1,088 synthetic cases (816 DRC / 272 interpreter), four fresh
visible BIOS replays, 47 regression scripts and clean `-validate`**. Unchanged
production sources retain the full-link/eleven-object evidence. Mosaic/VCSC and
clip-relative-origin mutations fail extracted image assertions. Primary ST-058
pp.117–119 and pinned cross-check limits are documented; run/capture hashes are
in `regtests/saturn/linked_runtime_results.json`.

C08a is bounded NBG0 normal-resolution qualification, not whole-VDP2 completion.
Other layers/rotation/interlace, exact bus/latches, external video, games/title and
performance remain open. No production correction was required by these scenes.
Older totals below are historical checkpoints.

## Linked line-window qualification PASS

Added 64 linked line-window scenes across JP/PAL/ST-V DRC and JP interpreter:
W0/W1 alone and together, coverage/calculation-only use, alternating bounds,
inverted rows and independent physical-end wrapping of each table at both capacities.
Tables and address/enable controls are explicitly mutated before real save/load
replay. 144 boundary probes per scene and full-image equality pass.

Current evidence: **1,024 synthetic cases (768 DRC / 256 interpreter), four freshly
rerun visible BIOS replays, 47 regression scripts and clean `-validate`**. The
unchanged production executable retains its full-link/eleven-object evidence.
W0/W1 capacity-mask and row-index mutations fail extracted assertions. Primary
ST-058 pp.184–187 and pinned cross-checks are recorded in `linked_runtime.md`;
current run/capture hashes are in `linked_runtime_results.json`.

C03b closes bounded normal-resolution qualification only. Sprite/rotation window
combinations, other modes, exact bus/latches, external video, games/title and
performance remain open. No new production correction was required; full VDP2
is not declared complete. Older case totals below are historical checkpoints.

## Linked offsets and windows qualification PASS

Current evidence: **960 synthetic cases (720 DRC / 240 interpreter), four freshly
rerun visible BIOS replays, 47 regression scripts and clean focused configuration
validation**. The existing eleven-object/full-link evidence applies to unchanged
production sources. No production correction was needed for the new cases.

The 194-case composition suite adds post-blend/top-screen offsets, lower-offset
isolation, signed saturation, A/B selection, W0/W1 coverage and calculation-only
boundaries, overlap and disabled-window rules. Window scenes check 144 boundary
probes and real save/mutate/load/full-image replay; offset/window registers are
explicitly mutated. 44 runner-protocol tests pass. Production offset-order, window
endpoint and disabled-window mutations fail assertions. Primary ST-058 pp.189–195,
250–252 re-read; pinned cross-check limits documented.

C03a/C05b are bounded acceptance, not whole-VDP2 completion. Line/sprite/rotation
window combinations, other modes, exact bus/latches, external video, games/title and
performance remain open. Reproduction/evidence: `regtests/saturn/linked_runtime.md`
and `linked_runtime_results.json`. Older totals below are historical checkpoints.

## Linked composition qualification — pushed after reconnection

Commit `162cda56` is now pushed. Current executed evidence: 736 synthetic pixel/save-load/full-image cases (552 DRC, 184 interpreter), four visible BIOS replays, 47 regression scripts, eleven production objects and clean focused link/validate for 122 runnable systems.

Includes NBG0–3 format/flip coverage and NBG0/NBG1 priority, all 32 ordinary ratios with top/second source selection, additive saturation and top-screen enable. Evidence: `regtests/saturn/linked_runtime_results.json`. Full VDP2 remains open, including exact contention/latches, external video, combined hardware qualification, games/title and performance. Earlier pending-push notes are superseded.

## Fresh linked qualification PASS (2026-09-16)

Focused executable linked and `-validate` passes for 122 runnable systems without
diagnostics. 47 scripts and eleven production objects pass. 138 DRC synthetic
pixel/save-load/full-image cases pass across JP/PAL/ST-V; 46 JP interpreter cases
also pass (184 total). Visible 900-frame unmodified BIOS replay passes on all three
with DRC and on JP interpreter (four replays). Inspected JP/PAL setup and 11-bit
cell captures. ST-V is BIOS-only, not cartridge gameplay.

Executable SHA-256 `85bef0b9d5d9c1f47847c571bcd1f70427e30f9e157541982a3774a93e04302e`.
Fresh evidence/capture hashes: `regtests/saturn/linked_runtime_results.json`.
Q02 is closed; bounded A04c/Q03a acceptance is recorded. Full VDP2, exact fetch/latch
behavior, external video, hardware combinations, games/title and performance remain
open. Earlier pending notes below are historical checkpoints, superseded by this run.

Cell-stride cross-check (`885bebc5`): ST-058 p.53 and pinned MiSTer specify 128-byte
2048-color cells; pinned Ymir's character-fetch cell index uses a 64-byte step.
MAME retains the Sega-documented stride. Both 64-byte-stride and swapped-H/V
mutations compile and fail independent image assertions; unmutated sampler passes
294,912 images and 98,304 metadata cases. Full linked execution remains pending.

## Expanded background qualification fixture (2026-09-16)

Authored 46 linked cases per system across normal-background legal cell/bitmap depths,
both capacities and existing RBG0 11-bit cells. Four-color 16x16 patterns distinguish
horizontal/vertical flips. Runtime runner requires all ordered case records and exact
system/completion markers. 47 regression scripts PASS, including 28 fake-executable
failure-protocol cases; Lua syntax PASS. Fake execution does not certify pixels.
ST-058 pp.60–61/69–75 re-read from the pinned Sega SDK blob.

Full build resumed with one job to avoid concurrent high-memory GCC units. Actual
link/validate and expanded fixture/BIOS execution remain pending; no parent VDP2
acceptance is closed by authored coverage. See `regtests/saturn/linked_runtime.md`.

## Recovered integration (2026-09-16)

Reconstructed the lost unpushed integration on the safely recovered remote branch.
All six map-offset high bits, both size-aware CPU apertures and three plain 11-bit
cell sampler routes are restored, with regression coverage and nine rejected mutations.
Sixty undumped EEPROM placeholders explicitly initialize to FF; dumped defaults unchanged.
Restored linked SDK bootstrap, synthetic save-manager fixture, visible unmodified BIOS
replay fixture and correct `saturn` validation executable path.

Current validation: 46 scripts + eleven production objects PASS; external SDK provisioning
PASS; both Lua fixtures pass the repository Lua syntax compiler. Recovery commits
`6dc85a25` and `8cb4c406` are pushed; the canonical feature assessment is reconciled.
Fresh full-build validation is running with two jobs and bounded GCC GC settings;
its link/validate result and current-checkout runtime qualification remain pending. Historical ade338f9 execution
results and lost captures are explicitly separated in `regtests/saturn/linked_runtime.md`.
Full VDP2, exact fetch/latch/external-video fidelity, games and performance remain open.

## Palette-cell tail source selection (81eb1b74)

Retained palette helpers normalize codes and use a shared source selector. Ordinary cells retain decoder caching; the final 8-bit cell uses a small wrapped buffer, observing low-memory changes and avoiding contiguous decode overrun. Removed the last-character decrement workaround. ST-058 table 4.2 supplies cell size/alignment.

45 scripts + 11 production objects pass with narrowing errors enforced. New 262,144 source-selector cases and three assertion-sensitive mutations. Controlled decoder/update stand-ins and renderer routing assertions are not full palette images or linked-decoder/save/game qualification. Generic decoder/graphics inspection and integrated consumer qualification remain open. Docs/tracker synchronized; user logs preserved.

## Direct-color character physical wrapping (8603a0aa)

Four retained RGB555/RGB888 zoomed/unzoomed helpers normalize bases and row addresses to configured VRAM size, avoiding inactive-half reads and backing-buffer overruns at character tails. Row alignment permits one mask per row. Pixel/color/zoom behavior is unchanged; palette decoder workarounds remain open.

44 scripts + 11 production object builds pass with narrowing errors enforced. New 2,816 boundary/alias/zoom/flip/blend/window/split images use production helpers and independent byte-modulo addressing. Five mutations fail assertions. Extracted helper tests are not full tilemap/game/save-manager or bus-timing qualification. Tracker/docs synchronized; user logs preserved and excluded.

## Production build correction (56aaba61)

Fix five narrowing conversions in the special-priority unsigned array using explicit unsigned conversions. Register expressions promote to int; priority values and rendering behavior are unchanged. Previous local object builds emitted but did not reject these warnings. Production object checks now enforce `-Werror=narrowing`.

43 regression scripts and eleven production objects pass under the strengthened check. Full linking/runtime acceptance remains separate.

## Legacy cell-map physical addressing (eff37909)

Map bases now honor 512 KiB/1 MiB capacity; one/two-word name reads mask final indices. Rotation-cache map watches cover the actual source-plane extent without an extra page. Character rendering and its separate watch are unchanged. ST-058 table 4.8 is primary.

43 scripts + 11 production object builds pass. New 24,576 base/watch configurations and 3,442,688 name-fetch probes; three assertion-sensitive mutations. Extracted arithmetic with controlled geometry/memory, not full tile-renderer images or linked-game qualification. Character-pixel tail wrapping, fetch timing, save/load/game and performance acceptance remain open. Docs/tracker synchronized; user logs excluded.

## CPU VRAM physical aliases/coherence (0275ab03)

CPU VRAM reads/writes now normalize to configured capacity before comparison, old-output preservation, byte decode and cache-watch invalidation. Partial-write semantics and conservative dirtiness remain unchanged. Sega capacity maps are primary; pinned Ymir's shared storage wrapping corroborates the 512 KiB model only. No bus timing/open-bus claim.

42 scripts + 11 production objects pass. New 1,296 alias/mask/decode/cache/order cases; two mask-removal mutations fail assertions. Existing 2,592 raster-write and 20,320 cache-invalidation probes pass. Legacy cell-map/character fetch audit, linked game/save-load, bus arbitration and performance qualification remain open. Docs/tracker synchronized; user logs preserved and excluded.

## Rotation/legacy line-color physical wrapping (fca6c93f)

All rotation-parameter longword fetches and retained line-color row reads now honor configured physical VRAM size. Parameter decoding, A/B selection, RPRCTL/latches and line/interlace indexing are unchanged. ST-058 pp.159/174 explicitly document the 4-Mbit address rule.

41 scripts + 11 production object builds pass: 1,920 rotation unpacking configurations, 1,310,720 table scenarios now also covering legacy line-color reads, and 512 unchanged latch replay sequences. Both old-mask mutations fail assertions. Controlled palette/color stages qualify addresses, not color math. T03 remains open for CPU aliases/remaining legacy cell fetches; linked runtime, timing and performance qualification remain open.

## Bitmap/scroll size masks and rotation cache validity (a0de2e0e)

Five bitmap renderers and legacy line/cell-scroll reads now honor configured physical VRAM size. Cached bitmaps establish format/size-aware write-watch ranges instead of inheriting stale character-map ranges. Independent A/B source-cache keys include VRSIZE, rebuilding on a size transition while preserving repeated-pass reuse.

41 scripts + 11 objects pass. New 17,280 bitmap images; 33,600 line-scroll scenarios, 85,248 cell-scroll cases, 5,120 bitmap invalidation probes and 20 size-transition cache cases. Ten assertion-sensitive mutations. Sega memory/layout/table rules are primary; Ymir corroborates only the 512 KiB memory model. CPU aliases, other fetch consumers, bus timing and linked runtime/performance qualification remain open. Docs and spec mirror synchronized; user logs excluded.

## Window/back-table physical wrapping (157fab78)

W0/W1 line-window and back-screen row addresses now wrap after row addition at the configured 512 KiB/1 MiB VRAM boundary. This prevents 512 KiB tables spilling into the unused upper allocation. Existing interlace indexing is unchanged.

40 scripts + 11 production objects pass. New 1,310,720-case production boundary/alias oracle; all three old-mask mutations fail assertions. Sega ST-058 pp.176–177/186–187 and pinned Ymir corroborate the 512 KiB path; Ymir's 1 MiB mode remains TODO. T03 stays partial for other consumers/CPU aliases/runtime. Docs and local spec mirror synchronized; user logs excluded.

## VDP2 startup/postload state separation (81c74199)

Initialized external/status/counter/display-size startup fields; reset clears event flags without overwriting latched samples. Postload discards all transient composition/capture/gradation/priority state while retaining saved rotation history and rebuilding decoded VRAM/caches/palette.

39 scripts + 11 production objects pass. Four poisoned-startup patterns, 64 full-VRAM reconstruction passes, four assertion-sensitive mutations; EXTEN reset tests strengthened. Counter startup zero is an emulator fallback, not asserted silicon behavior. Q01 remains partial pending actual save-manager/screen/timer replay. Workspace restored to the pushed checkpoint; user logs/ROM archives preserved and excluded from this commit. Docs/home mirror synchronized.

## Active VRAM cycle slots and bank ownership (e12e2cf7)

Normal-screen presence checks now ignore inactive A1/B1 registers, T4–T7 in high/exclusive modes, and banks reserved by enabled RBG0/RBG1. Sega ST-058 pp.29–32/149–150 and pinned MiSTer corroborate selection.

38 regression scripts + 11 production objects pass; 1,048,576 new presence cases and three assertion-sensitive mutations. T02 remains partial: per-fetch address matching, access counts/spacing, starvation behavior and CPU contention remain open. No linked/hardware/performance acceptance claimed. Tracker/spec mirror synchronized.

## Raster preservation follow-through (7a4e44a9)

Following the compositor pass, changed render-register/VRAM/CRAM writes now preserve completed visible lines before mutation; device-owned TVMD/VRSIZE changes preserve old decoded display state. Masked no-ops, startup/blanking, CRAM broadcast aliases and existing erase-triggered updates are covered.

37 scripts and 11 production object builds pass; 2,592 write/prefix/coalescing scenarios and three assertion-sensitive mutations, plus old-state-before-TVMD assertions. This is completed-line preservation, not current-dot fetch timing or a hardware latch model. T01/T02, timing/external interfaces, linked save/load and performance qualification remain open. Whole VDP2 is not yet complete. Docs/tracker/home mirror synchronized.

## Full-VDP2 scope: compositor/shadow/window pass (a5680c75)

Implemented extended calculation and gradation with bounded raw-source history/capture; underlying-layer SDCTL and normal/MSB shadows; top-only post-calculation signed offsets; high/exclusive palette-second restrictions; sprite line colors; calculation-only and normal/sprite SW windows.

36 scripts + 11 objects pass. New coverage: 786,432 extended, 28,672 signed-offset, 896 SDCTL identity, 6,144 gradation scenes; 32,256 all-type sprite shadow images, 307,200 sprite ratio/line images, 184,320 actual bitmap/palette/window images. Eleven assertion-sensitive mutations. Sega table/figure conflict and gradation edge policy documented explicitly.

Whole VDP2 remains incomplete: raster/fetch arbitration, timing/external interfaces, runtime save/load and performance qualification remain open. This is not a linked-game acceptance claim. Tracker/spec mirror synchronized.

## Latest: ordinary raw-second-image composition (2e728a7a)

- Shared normal/rotation/sprite raw-source history fixes cumulative lower-result blending; CCRTMD preserves second-source ratios even when their own calculation is disabled.
- Correct line/back CCRLB provenance, per-clip derived history, unchanged no-CC fast paths; existing shadows update raw/displayed RGB without claiming SDCTL completeness.
- 36 regression scripts + 11 production objects pass. New 524,288-scene independent oracle rejects five mutations; 153,600 sprite ratio images, active normal routing and rotation history/shortcut integration pass.
- Tracker/docs and local official-spec mirror synchronized. P2 remains incomplete: extended/gradation composition, layer-selective shadows, raster/fetch and linked game/save/performance qualification remain open. No linked-game acceptance claimed.

## Summary
Continue the Saturn/ST-V audit on `arena/01a09f50-mame`, including the earlier timer/IRQ/DMA/reference-audit increments already pushed on this branch. PR #1 is merged from the predecessor branch and is not modified.

Latest four-priority implementation (`f3b0a5fc`):
- Buffer longword SCU source reads for halfword delivery, including fixed-source fills; save/reset/invalidate buffer state.
- Make inactive CD long reads nonfatal, bound port accesses, stop both interfaces on DataEnd, and account for whole Get-and-Delete sectors after partial reads. Retain existing excess-read deletion timing without double deletion or losing DataEnd's EHST.
- Compose independent SMPC/SCU HALT ownership for Saturn and ST-V, save the latches, reapply them on postload, and release only SCU-owned stalls on SCU reset.
- Detect SMPC CONTINUE by bit reversal, cancel queued collection on BREAK, prevent stale callback responses, and reset IOSEL/EXLE.
- Extend object validation to SMPC and fix its include ordering.

## Evidence and tests
- Sega primary sections and pinned Ymir/Mednafen corroboration/disagreements recorded in `regtests/saturn/official_specs.md`.
- `python regtests/saturn/validate_build.py`: **17 scripts and nine object compilations passed**.
- New ASan/UBSan coverage: DMA 1,152 scenarios; CD 336; shared HALT 1,296 event sequences; SMPC 1,173.
- DMA and SMPC baseline handlers fail their intended assertions. Forced-stop no-op and five held-trigger mutations also fail their intended assertions.
- `git diff --check` passes.

## Explicit limitations
This is not a claim that all games now run, nor that all four subsystems are complete. No linked MAME/BIOS/game run or actual MAME save-manager round trip was performed; the documented SDL/pkg-config dependency blocker remains. Copied-state harnesses are not real save/load proof.

Still open: DMA odd counts/alignment and detailed bus timing; CD dummy-value verification, FIFO-prefetch/count and zero-data reporting, command ranges, full pointer/payload/directory/MPEG serialization and ISO parser safety; exact SMPC delay/VBlank timeout and paired SH-2/DRC traces. No game-specific success bypasses or speculative DCC retiming were added.

See `regtests/saturn/game_blockers.md` and the README for remaining work and reproducible validation commands. Downloaded SDK PDFs/build products remain outside Git.


## VDP1 implementation update
- Recognize END by bit15 and wrap command fetch at 512 KiB.
- Emit SCU draw-end alongside CEF in the completion callback, replacing the unconditional scanline workaround; do not report END after host loop-limit/unsupported-command exits.
- Correct upper byte lanes of 8-bit CPU framebuffer writes.
- Implement outside-user-clipping, always retain system clipping, and reject negative framebuffer coordinates in all pixel variants.
- ASan/UBSan: 32,775 command/completion, 288 framebuffer, 24,500 clipping scenarios pass; old command/framebuffer/clipping bodies fail independently.
- Full validation now passes **18 scripts and nine object compilations**.

**VDP1 is not complete.** Synchronous rendering still prevents faithful ENDR, transfer-over and in-flight save/load behavior. Exact draw/erase/swap timing, full framebuffer formats and rasterization/texture/color edge cases remain. No game-boot proof is claimed. `regtests/saturn/vdp1_completion.md` records primary sections, pinned Ymir comparisons, test scope and remaining acceptance gates.


## VDP1 command engine and packed 8-bit follow-up
- Timer-driven, saved command fetch/return/activity state replaces the host-limited whole-list loop. Valid jump/skip/CALL/RETURN controls execute incrementally; looping lists observe later CPU edits.
- ENDR stops at command boundaries without manufacturing END; reset cancels queued work and PTMR restarts from command zero. Exact approximately 30-clock pixel-pipeline stop is still open.
- COPR tracks fetched commands; framebuffer changes latch LOPR; EDSR/LOPR/COPR/MODR writes are ignored.
- Packed 8-bit dots, erase byte pairs, CPU word access and scanout now share storage, including high-resolution/rotation-8 row stride. All five pixel writers preserve adjacent bytes.
- Postload reconstructs pointers without resetting the restored drawing bank/geometry.
- **18 scripts/nine objects pass**. VDP1: **32,814 command/lifecycle, 532 framebuffer, 24,500 clipping cases**. Includes a 20,000-iteration loop and subsequent CPU edit, stop/restart, bank/geometry postload and actual pixel/erase/CPU readback checks. Pre-sequencer and pre-packed-rendering controls fail independently.

Primitive rasterization still runs synchronously, with a 16-cycle fetch allowance rather than full pixel/bus costs. Interlace field handling, rotated VDP2 coordinate readout, texture traversal/end-code and raster/color work remain. Sega explicitly prohibits nested CALLs and main-routine RETURNs; these are not missing legal features. No claim of complete VDP1 or game/runtime proof.


## VDP1 rendering/status follow-up
- MON preserves destination color bits; Gouraud is evaluated at the destination coordinate, avoiding drift across suppressed mesh/transparent/clipped dots.
- Explicit component color operations and saturation-before-combination coverage; bounded CLUT fetching.
- Normal sprites terminate each texture row at its second fetched end code, across formats/read directions/ECD/SPD. Scaled/distorted traversal is not claimed complete.
- BEF latches on actual bank changes, not every VBlank in manual mode.
- **18 regression scripts and nine object compilations pass.** Tests now include 92,420 color/shading, 2,689 texture/boundary, 32,816 command/lifecycle, 532 framebuffer and 24,500 clipping cases. Four render mutations fail independently.
- Primary manual plus Ymir/Mednafen/MiSTer were inspected. Pinned MiSTer differs on odd+odd blend rounding; the chosen average model follows the primary average wording and Ymir/Mednafen. No claim that all references agree or that hardware testing is complete.

**Still incomplete:** interlace/rotated readout, scaled/distorted texture traversal, hardware-consistent edge/scaling coverage and sub-primitive timing/ENDR/save-load. No BIOS/game execution or MAME save-manager round trip was performed. The detailed completion ledger remains `regtests/saturn/vdp1_completion.md`.


### VDP1 rotation/interlace/ENDR follow-up

- Six-parameter-A rotated framebuffer readout with Q9 arithmetic, bounds and both formats.
- DIL-latched physical interlace addressing and completed-field display snapshots; 256-KiB bank mirroring and physical erase rows.
- Register physical framebuffer payloads and field caches for saves (previous payloads were not registered).
- Schedule ENDR after 30 modeled clocks; primitive-level interruption/timing remains unfinished.
- All 18 regression scripts/nine object compilations pass; 974 rotation cases, two multi-step field sequences and 16 additional termination phases. Six render mutations fail assertions.
- Remaining scope and unvalidated runtime/save-manager behavior remain explicit in `regtests/saturn/vdp1_completion.md`.

### VDP1 scaled traversal and line shading follow-up

- Signed scaled endpoints/zoom anchors, independent flips and zero extents.
- Second-END source-row cutoff in both affine span paths with HSS disabled; cached per primitive. HSS/EOS and hardware edge stepping remain unfinished.
- Initialize line A/B Gouraud colors and all four polyline edge pairs correctly.
- Added 12,000 geometry, 2,924 source-END/span and 160 production shading-endpoint cases; three new mutation controls fail assertions. Full 18-script/nine-object validation passes.

### VDP1 scaled integer texture stepping

- Dedicated scaled texture walker with integer sampling phase, HSS/EOS decimation, independent flips and clipping phase preservation.
- 593,920 new recurrence/pixel cases across texture/color/framebuffer modes; texture-phase and EOS mutations rejected. Full 18-script/nine-object validation passes.
- Primary/reference HSS+ECD disagreement documented explicitly. Distorted edge walking, pixel timing and runtime/save-manager validation remain unfinished.


### Native renderer and framebuffer-control follow-up

- Pushed abb5a180: integer line/dual-edge quad rasterization, coverage pixels, per-edge Gouraud and distorted HSS/EOS/END integration; 2,500 line images and 3,840 quad images tested.
- Field-start bank change/automatic drawing, one-field manual erase and persistent VBE handling; TVM interpretation changes preserve bank ownership.
- Bank-change DIE/DIL/EOS and erase data/bounds latches, save registration and zero-mask write protection.
- Production multi-field lifecycle sequences pass for both banks; field-phase and erase-latch mutations rejected. All 18 scripts/nine object compilations pass.
- Still incomplete: interruptible primitives, pixel/VRAM timing, erase budgets, hardware pre-clipping and linked runtime/save-load acceptance. See regtests/saturn/vdp1_completion.md.


### Bounded VDP1 VBlank erase

- Capture displayed-bank ownership, latched data/bounds, word stride and field erase capacity at blank entry; commit the bounded prefix before bank exchange and preserve unerased pixels.
- Queue rotation/HDTV automatic/manual erase for blanking even with VBE clear. Save pending/in-flight state; reset cancels it independently of command-drawing ENDR.
- All 12 Sega Table 4.5 capacities and 154 erase/lifecycle cases pass, including full-bank images, partial-row cutoffs, sparse windows, both banks/formats and pending-state copy/postload tests. Three negative mutation controls reject unlimited capacity, wrong bank and live-data substitution.
- All 18 scripts/nine object compilations pass. Coarse blank-end commit is explicit: per-slot arbitration/row overhead, active-display erase, interruptible primitives, hardware pre-clipping and linked runtime/save-manager validation remain unfinished.


### Interruptible VDP1 line/polyline execution

- Queue up to four segments and execute bounded pixel slices, retaining coordinates, error/Gouraud phase and fetched command state. Short final slices use their dot count.
- Block the next command/END fetch until raster work finishes. ENDR cancels pending pixels without completion; PTMR and automatic field starts discard old cursors.
- Reconstruct pixel dispatch after restoration; CPU framebuffer writes between slices affect later blends. Save state-copy tests cover inside/between edges and pending ENDR.
- Restore documented reset bank ownership (draw 0/display 1), without clearing framebuffer contents.
- 748 image/lifecycle cases pass; quantum/cursor/reset-bank mutations fail. All 18 scripts/nine object compilations pass.
- Sprite/polygon rasterizers remain atomic. Batched visibility, nominal pixel costs, bus arbitration and real linked runtime/save-load acceptance remain explicit limitations.


### Native VDP1 quad slicing
- Polygons and distorted sprites now use saved, bounded raster slices; preserve pending coverage and texture END cutoff state across scheduler/save boundaries.
- 4362 queued-quad image/packed-format/texture/interruption/state-copy cases pass; coverage and texture-row mutations rejected. All 18 scripts/nine production objects pass.
- Normal/scaled sprites, exact bus arbitration, active-display erase and linked runtime/save-manager qualification remain unfinished.


### Normal/scaled VDP1 sprite slicing
- Normal and scaled sprites now share saved row/pixel execution, including in-row END count, source sampling and saved Gouraud coefficients. Supersedes the normal/scaled atomic limitation above; the unspecified zero-height fallback remains atomic.
- 1040 additional queued rectangle image/lifecycle cases pass; END-counter and texture-cursor mutations fail. All 18 scripts and nine production objects pass.
- Exact bus timing/early-END quantum accounting, active-display erase, preclip/degenerate qualification and linked game/save-manager acceptance remain open; no whole-chip completion claim.


### Rectangular Gouraud correction
- Inclusive scaled final rows, correct normal endpoints, original gradient coordinates under clipping/reversal, saved integer shading representation, and corrected legacy reversed origins.
- 2640 independent queued Gouraud images and three legacy probes pass; four mutations rejected. All 18 scripts and nine objects pass.
- Primary-backed endpoint fixes; integer rounding follows the Ymir/native model, not claimed identical to MiSTer fractional Gouraud or hardware traces. Whole-chip/runtime/save-manager acceptance remains open.

- Linked validation retry: package installation permitted, but Debian HTTP/TLS fetches fail; required pkg-config/SDL development dependencies could not be installed. `--full` fails its preflight, not a successful linked/game/save-manager run.


### Disabled VDP1 pre-clipping
- Honor Pclp=1 across ordinary normal/scaled/native paths; retain offscreen traversal and count hidden normal-sprite END markers without bypassing pixel clipping. Bound full-height scaled queues at 8192 spans.
- 10,681 new image/lifecycle/capacity cases pass; four mutation controls rejected. All 18 scripts/nine objects pass.
- Pclp=0 start reversal/END ordering, exact timing/source-prefetch, active-display erase and linked runtime/save-manager acceptance remain open. Not a whole-VDP1 completion claim.


### Unresolved OutRun visual regression
- User reports flashing sprites and oversized/off-center output. Running game variant/build and failing scene remain unconfirmed; passing extracted tests are not runtime acceptance.
- Added opt-in `-verbose -log` VDP1TRACE output for scaled raw/computed coordinates, source/destination dimensions, video-mode registers, framebuffer swaps and in-flight drawing. No speculative X/Y swap or game workaround.
- All 18 scripts/nine objects pass after instrumentation. Await failing-run launch details, screenshot/video and error.log; no visual fix or root cause claimed.


### OutRun supplied trace: manual display erase ordering
- Analyzed c4ae255c error.log and console description: saturnjp/outrun; 2,265 completed lists, 1,647 idle swaps, no compositor doubling modes. Manual erase/change sequence exposed field-start clearing of the displayed image.
- Fixed manual display erase presentation ordering: save captured erase, commit after presentation before next bank exchange, cancel on reset. 24 new presentation/state cases and two mutation controls; all 18 scripts/nine objects pass.
- Added normal-sprite geometry trace for logo diagnosis. Detailed evidence in regtests/saturn/outrun_trace_analysis.md. Visual rerun still needed; size/offset defect not claimed fixed.
- Preserved and merged the user-uploaded log commit without overwriting remote history.


### User runtime confirmation and follow-up log
- User confirms OutRun flashing is gone after the manual-erase fix; supersedes the pending flashing-confirmation note above.
- User clarifies that 822d45ac intentionally captures After Burner II failing to boot. This is a separate active issue, not a mistaken OutRun capture; no scaling root cause claimed.
- Preserved the uploaded commit and documented single-game log capture. Size/offset remains unconfirmed; documentation-only follow-up, no new emulation/test claims.


### After Burner II boot stall: focused CD/host diagnosis
- Analyzed the supplied capture: Read File at FAD 0xAB for 18 sectors reaches PAUSE near 7.05s; no further CD commands are logged before a soft reset near 83.58s; the same sequence repeats. VDP1 continues completing command lists. Existing logging cannot establish host wait/root cause.
- b4372499b33 adds verbose-only CDBOOT CPU PCs, HIRQ/mask, pending command/register/buffer/transfer state and host register-read counts. Periodic output once per emulated second, with command-dispatch and file-EFLS events; debugger reads excluded. No emulation behavior change or boot fix claimed.
- Sanitizer diagnostic checks and all 336 CD transfer cases pass. All 18 regression scripts/nine production objects passed with the instrumentation; no linked game run claimed.
- Analysis/capture instructions: regtests/saturn/afterburner2_boot_analysis.md. Need one instrumented failing run to distinguish CD polling/completion from CPU-side stall; the original log has already been analyzed. Six status docs and official-doc mirror synchronized; misleading OutRun capture framing corrected.


### After Burner II instrumented follow-up and sound reset/IRQ fix (436988f9)
- Preserved user capture 629e6569. It progresses past the first file read: 2,351 CD commands; last transfer ends near 17.487s, then SNDON near 17.56s. Main PC stays 06010276/06010278 for all 138 samples at 18–155s. CD has no pending command/transfer; no new VDP1 lists are submitted.
- Corrected dropped SCSP IRQ assertions/clears while the 68000 was held in reset. The SCSP only reports level changes, so ignoring changes during SNDOFF could lose or retain an IRQ after SNDON. Sega ST-169-R1 pp.3/25–26, MiSTer direct IPL/reset wiring and Ymir independently support preserving the signals.
- 64 extracted production SCSP/reset wiring cases pass; restoring the old gate fails. Bounded verbose-only BOOTCPU records add CPU register/instruction RAM and sound execution/reset/HALT evidence if the wait persists. No MMIO reads or bus timing changes from diagnostics.
- All 19 regression scripts and nine production-object builds pass; no linked/game/save-manager acceptance claimed. The wiring defect is confirmed in tests, but After Burner II boot still requires a user rerun. No game-specific workaround or whole-VDP1 completion claim.
- Evidence and source links: regtests/saturn/afterburner2_boot_analysis.md. Six status docs and /home/user/saturn_official_docs.md synchronized. OutRun flashing remains user-confirmed fixed; size/offset unconfirmed.


### After Burner II 366ac068: boot still fails; wait decoded (7dfefdd1)
- User confirms the prior IRQ/reset correction did not resolve the hang. Preserved the uploaded commit. No new speculative C++ emulation change.
- BOOTCPU words decode to MOV.L @R1,R0 / CMP/EQ #0,R0 / BT at 06010276–0601027A. R1=25A004FC, RAM word remains zero: this is a sound-RAM readiness wait, not CD/VDP1 polling.
- Sound CPU executes and is not externally held. Samples repeatedly enter its level-2 handler at 07E6; it accesses Timer B/SCIRE offsets through A5. A5 and SCSP enabled/pending state were not in the trace, so exact IRQ/initialization cause is not yet established.
- Added afterburner2_sound_probe.lua to inspect the missing CPU/save-item/RAM state with the existing executable (no rebuild required). Three read-only snapshots; no MMIO reads or emulated writes. Standalone Lua mock-binding tests pass, not a linked MAME acceptance run.
- Analysis, six status docs and official-doc mirror updated. Game boot remains unresolved; no fixed/completed claim.


### After Burner II SOUNDPROBE: SCSP clock-change reset defect (59976aa0)
- Three user snapshots resolve the missing state: A5=9CC0, SCIEB=80, SCIPD=5C0, IRQ level 2. The new handler writes RAM A0DA/A0E2 instead of SCSP Timer B/SCIRE; an old interrupt preempts startup before A5 initialization at 06C4 and the ready-pointer write at 06F0.
- Found CKCHG320 near 13.28s in the supplied log. Existing dot_select_w calls SCSP reset, but device_reset retained BIOS masks, pending flags, timer configuration and deadlines while merely clearing the cached level. This contradicts Sega ST-169 pp.30–31 power-on defaults; ST-077 reset semantics, MiSTer register-reset RTL and Ymir timer/IRQ reset independently cross-checked.
- Corrected the SCSP interrupt/timer reset domain: release old physical sound IRQ, clear both CPU interrupt state/levels, reset timers and replace old deadlines. No SNDON suppression, RESET-opcode workaround, sound-RAM alteration or game-ready flag patch.
- 24 production-code reset/IRQ/timer scenarios pass; restoring the previous partial reset fails. All 20 scripts/ten production objects pass, with SCSP newly included in validation. Fixed a pre-existing emu.h include-order dependency exposed by the standalone SCSP compile.
- User game rerun still required: source/test-confirmed reset defect, not yet confirmed successful boot. Broader SCSP slot/DSP/FIFO reset defaults and 30-us reset timing remain outside this scoped fix. Six docs and official-doc mirror updated; detailed evidence in regtests/saturn/afterburner2_boot_analysis.md.


### After Burner II latest uploads: false 68000 expansion-RAM mirror (1ac828eb)
- Preserved d05617ff probe and faa4291a error.log. New state confirms the old IRQ is cleared; boot now fails because low sound RAM and vectors are overwritten.
- Decoded clear loop at 06B2–06BE writes longwords from 07F000 beyond installed RAM. Former CPU mirror makes the write at 0806B8 erase its own opcode at 06BA. Historical-map replay matches the uploaded A0=0806BC, zeroed 06BA, and intact 51C9/FFFC at 06BC/06BE exactly.
- Removed the false 080000–0FFFFF CPU RAM alias for Saturn/ST-V; expansion writes are ignored. ST-077 p.4 Figure 1.3 identifies uninstalled memory; pinned MiSTer deselects RAM using address bit 19, and Ymir CPU mapping ignores those writes. Native DSP/sample wrapping and SH-2 mapping unchanged.
- Updated BOOTCPU/Lua pointer inspection to reject the expansion region. Thirteen map/store cases pass, including historical failure replay; old-alias mutation fails. All 21 regression scripts/ten production objects pass, plus Lua mock-binding tests. Not a linked CPU/game acceptance run.
- User rebuild/retest still required; no ready-flag patch, game-specific workaround or full boot-completion claim. Six status docs/official-doc mirror synchronized; detailed evidence in regtests/saturn/afterburner2_boot_analysis.md. Power Drift image issue remains separate.


### After Burner II: sound initialization passes; later software DMA wait (cddd9bd2)
- Preserved cc8a7db8 error.log and 3e4b4384 probe. All three snapshots show readiness pointer 0007F000, valid A5=00100000 and completed clear-loop A0=000BF000; original sound-startup blockers are passed in this capture. Not a claim of successful overall game boot.
- Main CPU instead remains at 0607BBC4/0607BBC6 from ~21–72s, polling software flag 06004E64=1 in a routine programming SCU DMA. Final VDP1 list completes at 20.633709108s. Existing trace cannot distinguish transfer, IRQ delivery/masking, or handler causes.
- Extended no-rebuild Lua probe with SCU registered DMA/IRQ/A-Bus state and main-RAM wait operands, vector table and high-RAM DMA handlers. Save-item/backing-RAM inspection only; no MMIO or emulated writes. Extended standalone Lua mock-binding tests pass.
- No speculative DMA/IRQ change or fresh C++ build claim. Evidence/six status docs/official-doc mirror updated. New SCU snapshot required to continue the later-wait diagnosis; already supplied logs have been analyzed.


- **7353d928 / AB2 diagnostic refinement:** capture 29b70a92 proves DMA0 finished but DMA0-end remains pending and masked (IMS=BFFF) inside the VBlank callback. Retain documented/Ymir-confirmed acknowledge mask reset. No production emulation change or boot-fix claim. No-rebuild Lua probe adds bounded DMA/IRQ write and vector-read history plus BIOS mask/dispatch RAM; standalone mock checks and diff check pass. Updated analysis/worklists/spec mirror; next evidence requires this new access-order capture on the existing executable.


- **SH DRC delay-slot IRQ fix (2f84a960 runtime evidence):** preserve `compiler_temp.checkints` when returning from `generate_delay_slot`. BIOS ChangeSCUMask restores SR in an RTS delay slot; the old helper dropped the interrupt-check request, consistent with VBlank delivery after a subsequent mask-all operation and AB2 waiting for masked DMA0-end. Keep SCU masks/latch/DMA timing unchanged (Ymir/MiSTer cross-check). Added 72 production-helper state cases; old-state mutation fails. All 22 Python regression scripts and eleven objects pass, including shared SH core. Updated analysis/spec/worklists and external spec mirror. **Requires rebuilt executable for game-boot acceptance; no linked-game or SH-4 runtime pass claimed.**


- **d402162b follow-up: After Burner II boot is user-confirmed with d68770ea.** Visual defects remain separate. Correct RGB transparency so 7FFF stays transparent with SPD=0 when ECD/HSS disables END processing; independent TP/EC gates corroborated by Sega control definitions plus MiSTer GetPattern and Ymir. Exhaustive 262,144 RGB-word/ECD/SPD cases and updated normal/queued/scaled-HSS image oracles pass; old behavior mutation fails. All 22 regression scripts and eleven objects pass. Add verbose field-boundary rotation/VDP2 scroll/zoom state and command COLR for unresolved displacement. Updated worklists/spec mirror and visual evidence analysis. **Effect-rectangle improvement needs rebuilt-game confirmation; logo/title geometry is not claimed fixed.** Preserve a separate log per game; startup Lua probe no longer needed for graphics checks.


- **d0166ac6: user confirms explosion transparency is unchanged by 94cc6b24.** All 670,624 scaled command records use LUT color mode, not the corrected RGB mode. Boot remains confirmed; explosions and geometry remain open. Add no-rebuild, F12-triggered read-only video capture (screen, texture/LUT/command RAM, both framebuffer banks, VDP2 VRAM/CRAM/registers) to discriminate VDP1 output from VDP2 composition without another huge verbose log. Lua mocks pass schema/bounds/cap/collision/failure checks; no live capture or new emulation fix claimed. Updated analysis/worklists/spec mirror.


- **3c31f363 capture: HSS/LUT explosion artifact identified and corrected.** Capture 001 contains framebuffer 8000 in the rectangle; LUT F maps to 8000 and the matching 20x37 commands use PMOD=1808. Stop forcing ECD during HSS reduction: bypass row termination but retain individual END-pixel rejection, matching Ymir and MiSTer (document the conflicting Sega p.86 table wording). Fix all three scaled/native paths; four focused synthetic marker/cutoff cases plus HSS/EOS/native image oracles pass. Old forced-ECD mutation compiles and fails the C++ pixel test. All 22 Python scripts and eleven objects pass. Boot remains accepted; **rebuilt-game explosion acceptance pending, other geometry still open**. Updated source analysis/worklists/spec mirror; no extracted assets committed.


- **User acceptance (2026-09-15): 969cc3ae fixes After Burner II explosion transparency AND Power Drift cars.** Both are runtime-confirmed, superseding earlier pending-acceptance notes. After Burner II boot remains accepted. Separate logo/title placement issues remain open; no full gameplay/save-load or VDP1 completion claim. Documentation/spec mirror updated; no emulation changes in this acceptance update.


### VDP1 scanout completion increment — 68f87162
- Implement HDTV/31-kHz 2×2 replication and framebuffer/output-resolution sampling; unify compositor output coordinates for partial clips, interlace, rotation, windows, blending and shadows.
- Preserve user-accepted HSS/ECD explosion/car fix; no title-position workaround.
- Add actual extracted compositor/readout regression: 3,036 ASan/UBSan image cases. Pre-change code compiles and fails an odd interlaced partial-clip image.
- All 23 regression scripts and eleven production objects pass. Reconcile stale completion matrix: all legal primitives already have saved resumable cursors.
- Full completion is not claimed: field-coarse active erase, nominal bus arbitration, real save/load and linked runtime qualification remain. SDL/pkg-config dependency retrieval failed; separate title/logo geometry remains open.


### Progressive VBlank erase
- Saved partial-row cursor, remaining budget, latched bank/data/format and raster quota; expose erase progress during blanking rather than one field-end update. Flush only residual budget before bank exchange.
- Preserve ST-013 published capacities; document Ymir's 113-vs-200 penalty discrepancy instead of adopting a title-driven timing change.
- 552 new slice/restore/cancel/callback cases; no-progress and uncapped-budget mutations fail image assertions. All 23 scripts and 11 production objects pass.
- Active-display erase, cycle-exact arbitration and real save-manager/linked runtime qualification remain open. Existing user-accepted fixes unchanged.


### Active-display erase
- Manual/one-cycle erase follows partial presentation of affected physical rasters, with a saved next-row cursor and latched ownership/data/window/cadence. Field end no longer bulk-erases unvisited rows.
- One-cycle mode erases the displayed bank before its next swap into draw ownership. Apply ST-013 p.49 active display limits; document differing Ymir/MiSTer bounds rather than claiming exact cross-source agreement.
- 180 new cases plus updated manual presentation sequences. Three mutations fail; 23 regression scripts and eleven production objects pass.
- Within-raster arbitration, edge/performance qualification and real MAME save/load/runtime acceptance remain open. No title-position hack or HSS/ECD pixel change.


### VDP2 source audit and progress tracker
- Add `regtests/saturn/vdp2_completion.md`: feature-by-feature matrix, source anchors, actual test scope, stable-ID multi-level checklist, priorities and acceptance gates, audited against ad5ae529.
- Distinguish active implementations from partial/unused register fields and disabled helpers. Mosaic and ordinary line-color postprocessing remain gated off despite helper code/tests.
- Track composition/shadows/sprite windows, special effects, scroll/rotation gaps, raster writes/VRAM scheduling, timing/external video and save/runtime/performance qualification.
- Link the report from README, official specs and root worklists; sync the external specs mirror. Documentation only; no new runtime acceptance claimed.


### VDP2 A03–A05 first implementation
- Fix mode-0 CRAM write broadcast to both halves with independent masked-lane merges; retain physical reads and ignore zero-mask transactions.
- Primary ST-058 §3.4 pp.43–46; corroborating Ymir WriteCRAM and MiSTer IO_PAL0/1_WE. Document upper-half/read evidence distinction and remaining mode-layout/DAC questions.
- Add extracted production palette oracle: 9,216 cases plus transition checks; old implementation fails raw-memory assertion. All 24 scripts and eleven objects pass.
- Add complete-address first-pass register ledger; masks/reset/latch and full background/window fixtures remain open. Parent A03–A05 tasks not yet closed.


### Continued VDP2 foundation/composition work
- d123200e preserves physical CRAM banks across 15/24-bit mode changes and verifies upper-bank coefficient reads. Previous layout fails the new address oracle.
- Add real bitmap/palette/window/cache fixture for five bitmap pixel formats, line windows, scale/wrap and odd partial clips; not mocked window evaluation.
- Fix CCMD additive selection in all five bitmap paths, with a failing no-additive mutation. Fixture now covers 15,360 images; palette suite covers 9,216 cases plus transitions.
- All 25 regression scripts and eleven objects pass. Extend register ledger with pinned MiSTer mask cross-references, explicitly not yet primary-certified masks/latches. A03/A04 and complete composition remain open.


### VDP2 sprite zero-ratio composition
- Separate MSB-based per-dot calculation eligibility from CCRT; ratio zero now performs its valid 31:1 blend, and additive calculation remains independent of ratio.
- Extract actual blend-level helper into sprite tests. Add 38,400 ratio/selector/condition images; previous baf9b069 code compiles and fails. Existing 3,036 scanout cases pass.
- All 25 regression scripts and eleven objects pass. Full second-image eligibility, shadows, sprite windows, CCRTMD and runtime qualification remain open.


### VDP2 rotation partial clips and coefficient windows
- Advance per-line rotation accumulators to the partial clip's screen X, preserving wrap semantics; no restart at X=0.
- Apply ordinary RBG and mode-3 parameter windows on per-dot coefficient rendering, matching the per-line path.
- Add 9,216 production rotation image cases; missing-origin and bypassed-window mutations fail. All 26 scripts and eleven objects pass.
- Coefficient/window inputs are controlled stand-ins. High-resolution precision differences, full window/rotation features and linked runtime/save acceptance remain open.


### VDP2 rotation shortcut/cache integration
- Preserve real window configuration and partial clips on the no-transform path; remove the lossy rectangle shortcut.
- Restrict shortcut to coefficient-free selected parameter, zero starts and unit output stepping; RPMD 2/3 were already excluded, not newly implemented.
- Keep source caches unblended and let final compositor select CCMD instead of forcing alpha over additive output.
- 5,376 production dispatch/cache cases, old-code window failure and independent coefficient/alpha mutations. All 27 scripts and eleven production objects pass.
- Actual full runtime/save/performance qualification and remaining composition/window/rotation features are still open.


### VDP2 rotation pixel coverage
- Clear source caches transparently and test decoded coverage instead of RGB intensity. Valid palette/RGB black is no longer dropped; source transparency is not re-tested against resolved color.
- Use real MAME rgb_t in rotation/cache fixtures. Add 360 production bitmap-to-rotation coverage images across five formats, source transparency controls, A/B/coefficient paths, traversal and blend modes.
- RGB-zero-rejection and opaque-clear mutations fail separately. Existing 9,216 rotation images and all 27 scripts/eleven objects pass.
- Cache coverage is host metadata, not full layer/priority/second-image tracking. No linked runtime/save or specific-game acceptance claimed.



### ZMCTL paired-screen restrictions
- Enforce ST-058 Table 5.2 restrictions for NBG0→NBG2 and NBG1→NBG3.
- 3,456 actual register/layer-setup scenarios pass; previous HEAD compiles and assertion-fails.
- Full 28-script / eleven-object validation passes; S01 and runtime qualification remain open.



### Normal-screen color-depth exclusions
- Complete ST-058 p.61 2048-color/RGB888 screen restrictions, corroborated by pinned Ymir/MiSTer.
- 4,608 additional production layer-setup scenarios plus 3,456 reduction scenarios pass. Prior commit and three independent layer mutations compile/assertion-fail.
- Full 28-script / eleven-object validation passes. Tracker, root worklists and official-doc mirror synchronized; parent/runtime tasks remain open.



### Rotation screen-over-pattern implementation
- Decode OVPNRA/OVPNRB one-word characters and repeat outside the source bounds in both coefficient paths. Support five color formats, supplement/flip controls, character sizes, transparency and normal final composition.
- Restrict unity shortcut to screen-over repeat mode. Per-pass small pattern decode avoids persistent cache/save fields.
- 2,560 decoder configurations, 2,880 new images, 8,448 dispatch configurations pass; four independent mutations compile/assertion-fail. Full 28 scripts/11 objects pass.
- R01 base pixels implemented; shared special-function metadata, parameter switching and actual runtime/save/performance qualification remain open. Documentation and official-doc mirror synchronized.



### Line-scroll interval and partial-clip scheduling
- Anchor packed H/V/zoom reads and vertical interpolation to screen intervals; bound every draw to the requested clip, retain batching, restore the original descriptor.
- Decode unsigned line zoom correctly, including 4.0. No invented ZMCTL clamping.
- 4,200 scheduling scenarios pass; previous commit and four targeted mutations compile/assertion-fail. All 29 scripts/11 production objects pass.
- S02 fractional resampling, vertical-cell combinations and runtime/interlace-fetch qualification remain open. Tracker/worklists/official-doc mirror synchronized.



### Standalone vertical cell-scroll dispatch
- Remove accidental horizontal-line-scroll prerequisite. Dispatch standalone columns directly to tile/bitmap renderers; restore original scroll state.
- 85,248 recording-fixture configurations pass; prior commit and two independent mutations compile/assertion-fail. All 29 scripts/11 production objects pass.
- Source-coordinate cell boundaries, fractional/mosaic/zoom combinations and linked runtime qualification remain open. Tracker, worklists and official-doc mirror synchronized.



### Combined P2 scroll/rotation batch — P2 remains incomplete
- Preserve fractional bitmap/table phases; correct Px sign extension. Select mode-2 A/B before coverage/composition and restrict B to per-line coefficients when A is per-dot.
- Separate RBG1 normal-scroll state/window controls; enforce dual-rotation exclusions. Correct full-character cache write watches, with conservative wrap handling.
- New/expanded fractional images, 960 parameter configurations, 144 selection images, 648 signed-coefficient boundary images, 262,144 window pixels, 256 RBG1 setup cases and 15,200 cache invalidation writes pass. Full 32 scripts/11 production objects pass.
- Parent tasks remain open: fractional tile sampling, full cell/line/mosaic combinations, one-shot scanline RPRCTL reloads, coefficient line-color interaction, precision/arbitration and linked runtime/save/performance. Tracker lists these as implementation gaps, not merely uncertified hardware. Documentation and official-doc mirror synchronized.



### Integrated P2 implementation — `8b070d34`
Supersedes the implementation-gap list in the previous combined-batch update.
- Shared fractional tile/bitmap point sampling now implements all line/vertical-line/zoom/cell combinations, source-cell anchoring, interleaving, wrapping and normal mosaic without nested redraw.
- Scanline A/B RPRCTL one-shot reload/accumulation, normalized row history, reset/save registrations and row dispatch with source-cache reuse.
- Basic coefficient line-color second-image insertion, A/B/RBG1 selection and CCRLB/CCRTMD; explicit wrapping coordinate arithmetic and corrected mode-3 short/long viewpoint formats.
- RAMCTL partition-aware per-dot availability and coefficient bank permissions, physical VRAM wrapping and CRAM upper-half access. Invalid-bank transparent fallback follows Ymir, not a measured bus-latch result.
- **34 scripts / eleven production objects pass**. New coverage includes **30,720** scroll images, **512** latch sequences, **1,536** signed-limit images, **11,520** line-color/resource images and **40,960** bank/CRAM fetch cases; targeted mutations assertion-fail or trigger UBSan as intended.
- **P2 remains partial:** shared special-priority/calculation metadata and general/extended composition, raster/fetch arbitration, rotation mosaic and linked game/save/load/performance qualification remain open. No hardware certification or runtime save-manager acceptance from extracted fixtures.
- Tracker, worklists, reference notes and `/home/user/saturn_official_docs.md` synchronized. Existing user logs preserved untouched.



### Rotation mosaic integration
- Horizontal RBG0/RBG1 source sampling, screen-left anchoring across split clips, high-resolution doubling, parameter/coefficient/line-color sampling at mosaic anchors and per-output destination blending.
- Disable unit-transform shortcut for mosaic; memoize coefficient reads per pass.
- 5,760 mosaic images, 34,560 coefficient line-color images, mutation rejection and full 34-script/11-object validation pass.
- Tracker/reference mirror synchronized. Shared special-function composition, raster/bus implementation and linked qualification remain open. Per-output window ordering differs from Ymir's copied anchor-window result and remains hardware-unqualified.



### P2 rotation sprite windows — `6517550c`
- Replace constant SWE results with displayed-framebuffer masks for RBG0/RBG1 and RPMD 3 selection; combine W0/W1/SW area/logic controls.
- Use existing VDP1 scanout addressing, enforce documented type/color eligibility, invalidate derived rows on partial rendering/writes/postload, and prevent unit-transform shortcut bypass.
- 1,376,256 mask scanout pixels, 4,194,304 output-window pixels, 16,384 A/B window pairs and 33,024 production rotation/window composition images pass. Meaningful ignored-mask and inverted-MSB mutations fail.
- Full 34-script/11-object validation passes. R02 screen-over and R03 transformed/untransformed-window leaves reconciled with image evidence; tracker and official-doc mirror synchronized.
- **P2 is not complete:** shared special-function/general/extended composition, raster/fetch arbitration and linked game/save/load/performance qualification remain open. Normal NBG/sprite-layer SW integration remains separate C03 work.



### P2 shared special color eligibility — `2cbe3d4f`
- Implement SFCCMD per-character/bitmap, SFSEL/SFCODE per-dot, and CRAM-MSB eligibility in shared sampling. Correct NBG0/1/2 PNC SCC extraction; preserve RBG1/NBG0 sharing.
- Retain coverage independently of calculation, preserve eligibility through color offset, and apply it to normal, rotation and OVPNRA/B composition.
- Bounded direct source sampling for special-calculation rotation avoids an RGB-only/full-map cache; supports all 16 maps and retains ordinary cache paths.
- 110,592 normal images, 39,936 special rotation/map/bitmap/screen-over images, meaningful attribute/code/MSB/metadata mutations and full 34-script/11-object validation pass.
- Tracker and official-doc mirror synchronized. Per-dot special priority, general/extended composition, raster/fetch arbitration and linked runtime qualification remain open; this is not all-P2 completion.



### P2 shared special priority — `90f6b10b`
- Implement per-character/bitmap and per-dot priority LSB replacement, SFSEL/SFCODE matching and effective-priority-zero transparency, including OVPNRA/B and RBG1/NBG0 sharing.
- Carry priority independently of coverage/calculation; filter normal/rotation output by the active priority pass. Attribute-dependent rotation bypasses RGB-only caching even without color calculation.
- Dispatch each special layer in at most two nonzero priority passes; preserve the established layer/sprite tie order and ordinary-layer fast paths.
- 294,912 normal images, 107,520 special rotation images, 98,304 all-layer metadata cases, 131,072 frame-scheduling/tie-order images and meaningful negative mutations pass. Full **35 scripts / eleven production object builds pass**.
- Tracker and official-doc mirror synchronized. Special-priority implementation is no longer missing; general/extended color composition, raster/fetch arbitration and linked runtime qualification remain open. No all-P2 or silicon certification claim.

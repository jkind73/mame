# VDP1 completion audit — 2026-09-14

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

## Interruptible line/polyline execution — 2026-09-14

Line and polyline commands now enqueue up to four segments and execute in at most
16-dot timer slices. Completed segments share the remaining slice budget. The last
short slice uses its actual dot count instead of adding a full 16 clocks. The next
command/END fetch is blocked until queued pixels finish; COPR stays on the active
command. ENDR discards the unfinished cursor and cancels scheduling without an IRQ;
PTMR restart and automatic field restart also discard old work. Reset now restores
the defined bank roles (drawing 0, display 1), rebuilding views without clearing
framebuffer RAM; the old initialization had reversed these roles.

Coordinates, error accumulator, dot index, segment colors, clip bounds and fetched
command fields are saved. Pixel dispatch is reconstructed for each slice, so it is
not a saved host pointer. Gouraud uses the original dot index after resumption;
half-transparent pixels are not replayed. CPU framebuffer writes between slices
are visible to subsequent blends. A state load resumes emulation state; ENDR itself
does not support hardware continuation.

Validation adds **748 cases**: sliced versus synchronous images across octants,
line/polyline commands, mesh, color operations and packed storage; every ENDR slice
phase; short-slice/END ordering; CPU framebuffer writes; PTMR/automatic restart;
and state copies inside segments and between edges, including a pending ENDR.
Unlimited-quantum, lost-cursor and wrong-reset-bank mutations fail assertions. All 18 scripts/nine
objects pass. No real MAME save/load or linked BIOS/game test is claimed.

This is a nominal one-dot-per-clock model with batched visibility, not exact bus
arbitration. Gouraud/setup/VRAM wait costs remain unqualified. **Normal/scaled/
distorted sprites and polygons remain atomic** and still need resumable execution.
The existing native pixel model is reused rather than replaying completed work or
pre-rendering framebuffer writes.


## Bounded VBlank erase — 2026-09-14

VBlank erase now captures the displayed bank, word layout, latched bounds/data,
and Sega's per-field erase capacity at blank entry. It commits only the permitted
prefix before the next bank exchange; excess pixels stay untouched. Rotation and
HDTV automatic/manual erase now queue for blanking instead of clearing a whole
bank immediately. Persistent VBE still repeats. Pending/in-flight state is saved;
machine/system reset cancels it, while stopping command drawing does not.

The capacity reproduces all 12 entries of ST-013 Table 4.5, including NTSC/PAL,
31 kHz and HDTV. High-resolution 8-bit mode erases two dots per word, not twice as
many words. Double-density interlace does not double the per-field capacity.

Validation adds **154 erase cases**, checking complete physical banks, partial-row
cutoffs, sparse windows, both banks and all five TVM formats, pending-state copy /
postload reconstruction, reset cancellation and blank-only scheduling. Three
independent mutations (unlimited budget, wrong bank, live instead of captured data)
fail assertions. All 18 scripts/nine objects pass. No real MAME save round trip or
linked game/BIOS run has been performed.

This remains a **coarse blank-period model**: writes commit at VBlank OUT. It does
not model individual erase bus slots, row setup overhead, or intermediate debugger
visibility. Active-display erase, interruptible command rasterization, pixel/VRAM
arbitration and hardware pre-clipping remain unfinished. See `official_specs.md`
for primary/reference evidence and differences.


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
scaled/distorted texture traversal or pixel timing; rotation/interlace were added in the later pass above.

Tests pass: 92,420 color/shading cases, 2,689 normal-texture/boundary cases,
32,816 command/lifecycle cases, 532 framebuffer cases and 24,500 clipping cases.
Four independent render mutations (MON source replacement, dropped odd carry,
fixed Gouraud coordinate, disabled second-END termination) fail their assertions.
All 18 scripts/nine objects pass. Shader tests do not establish polygon edge or
interpolation precision on silicon; callbacks use recording timer/CPU endpoints.
Full chip completion and BIOS/game/runtime/save-manager proof are not claimed.


**Status: in progress, not a complete VDP1 implementation.** The command engine now yields between commands; primitive rasterization
is still synchronous, and pixel/bus timing is not complete. No BIOS/game or hardware trace has been run here.

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

## Earlier implemented corrections

- Recognize CMDCTRL.END independently of the other control bits.
- Wrap sequential command fetch at the 512 KiB VRAM boundary.
- Generate SCU draw-end at the existing completion callback, alongside CEF, not
  unconditionally eight scanlines after VBlank. A host iteration-limit exit or
  unsupported command is not reported as a fetched END. Starting another list
  cancels the old outstanding completion estimate.
- Fix the upper two data lanes of CPU framebuffer writes in 8-bit modes. Preserve
  masked-off bytes and keep accesses on the selected drawing bank.
- Implement outside-user-clipping in all five pixel writers, keeping system
  clipping enabled. Inside includes the rectangle boundary; outside excludes it.
  Reject negative coordinates before indexing framebuffer line pointers. Outside
  mode rasterizes against the system rectangle, not the excluded user rectangle.

These remove a title-specific periodic IRQ workaround rather than adding one.
They can expose software that depended on the old fabricated completion; runtime
regression coverage is required before claiming improved game compatibility.

## Evidence

Primary: [Sega ST-013-R3-061694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf).
The PDF was downloaded/extracted outside Git, with 178 pages.

- §3.1 printed p.19 / PDF p.34: command fetch wraps after 07FFFFH.
- Printed p.20 / PDF p.35: CPU accesses the drawing framebuffer; byte access is
  allowed in 8-bit display, prohibited in 16-bit display. The lane repair follows
  the existing big-endian CPU register interface; no prohibited-access behavior
  is invented.
- §4.6 printed p.52 / PDF p.67: END fetch sets CEF and produces an interrupt;
  unreachable/missing END leaves CEF clear. This does not establish our delay.
- §7.10 printed p.132 / PDF p.147: END is bit15; the remaining command is ignored.
- §6.3 and §7.1/7.2: system clipping always applies, with inclusive rectangle
  boundaries; user clipping can select inside or outside. Technical Bulletin 15
  corrects swapped Clip/Cmod prose in an earlier manual edition. This edition's
  §6.3 also has contradictory Cmod boundary prose; §7.2 explicitly treats points
  on the line as inside, consistent with the diagram and reference renderer.

Cross-check: [Ymir VDP](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/vdp.cpp)
uses `control.end`, masks the next address to 0x7ffff and emits draw-end in
`VDP1EndFrame`. Its [software renderer](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp)
checks system clipping and complements the inclusive user test for outside mode.
Reference agreement is not hardware timing proof, and no source was imported.

## Executed coverage

`python regtests/saturn/test_vdp1.py` extracts production bodies and runs ASan/UBSan:

- 32,775 command/completion cases: every END control combination, a looping list
  replacing pending completion, CALL/RETURN at the final VRAM slot, sequential
  wrap, and dispatcher clip-rectangle selection.
- 288 CPU framebuffer cases: both banks, normal and 8-bit modes, four payloads,
  all legal byte-lane combinations (only word accesses tested in 16-bit mode),
  readback and preservation of the other bank.
- 24,500 actual pixel-writer cases: fast and generic variants, both clip bits,
  inside/outside/boundary/system rejection and negative coordinates.
- `--baseline commands`, `--baseline framebuffer`, and `--baseline clipping`
  substitute the pre-fix bodies and fail independently.

Rasterizers, time conversion, and SCU IRQ delivery are recording endpoints in
this harness. Generic color calculation is not tested here. No claim follows
about full rendering, actual IRQ latency or MAME save-manager restoration.
The full validator passes **18 scripts and nine object compilations**.

## Remaining implementation and acceptance gates (reconciled 2026-09-15)

Earlier dated sections are historical checkpoints, not the current feature matrix.

| Area | Implemented | Remaining implementation/verification |
|---|---|---|
| Command scheduling / ENDR | All legal primitives use saved, bounded raster cursors; command loops yield; ENDR schedules a 30-clock stop. | Qualify pipeline termination and real save/load during each primitive. |
| Timing / transfer-over | 16-cycle command fetch and nominal sliced pixel work across frames. | Fetch/pixel/VRAM arbitration and silicon timing measurements, not title-specific delays. |
| PTMR / FBCR / EDSR / pointers | Restarts, live COPR, bank-change LOPR/BEF, read-only writes, deferred latches and field control. | Sub-scanline latch qualification; active-display erase now follows presented rasters with saved progress; VBlank erase progresses by raster with a residual budget flush at field end. Within-raster arbitration and edge qualification remain. |
| Command control | Eight legal jump controls and persistent fetch/return state. | Hardware investigation of prohibited opcodes/aliases and flow; no invented primary-defined results. |
| Framebuffer formats | Packed 8-bit storage, CPU access, rotation, DIE/DIL, field caches and HDTV replication; unified output-resolution sampling. | Physical readout phase/hardware qualification, particularly mismatched modes and rotated packed-byte lanes. |
| Rasterization | Native integer line/quad and normal/scaled walkers, all resumable; pre-clipping-disabled traversal and clipping tests. | Silicon coverage, pre-clipping and interpolation/rounding qualification. |
| Texture / color | END, HSS/EOS, transparency, MON, mesh and Gouraud combinations implemented and tested. | Hardware rounding/coverage checks; independent VDP2 alpha/MSB-shadow and underlying-layer shadow eligibility are not complete. |
| Save/reset | Command state, all legal intra-primitive cursors, physical banks, field caches and pending erase saved; postload reconstructs views. | Real MAME round trips during drawing/erase, ENDR and bank changes; no duplicate IRQs. |
| Runtime | User accepted AB2 boot/explosions, Power Drift cars and OutRun flashing. | Linked build/configuration validation, broader game/save smoke tests and the separate logo/title geometry report. Dependency downloads currently fail. |

Do not mark this table complete from standalone tests or an absence of TODOs.


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

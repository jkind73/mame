# OutRun trace analysis and manual-erase ordering fix

## Follow-up: flashing resolved in the user's run

The user confirmed after uploading commit
[822d45ac](https://github.com/jkind73/mame/commit/822d45ac1a5ce7509993ace32d9000eb57b138e4)
that the flashing sprites are gone. This is runtime confirmation from the user of
the manual-erase fix, not a locally performed game test or whole-chip acceptance.
The earlier request for flashing confirmation below is superseded by this result.

The new console description includes an OutRun run (56 seconds), followed by
After Burner II (`saturn:aburner2`, 91 seconds). The uploaded `newerror.log` is
3,230,668 bytes / 18,519 lines, SHA-256
`2288b3f5c73cd4fb0d00c98b003fcdebece80cbbe27a1531ed51cf14838df374`.
Its emulated timestamps extend to 92.097 seconds and it has no scaled records;
the user explicitly confirms this is an intentional After Burner II boot-stall
capture, not an OutRun scaling test. See [the boot investigation](afterburner2_boot_analysis.md)
for analysis and the new focused CD diagnostics. Do not attribute its geometry to
OutRun.

It contains 2,336 normal-sprite records (eight distinct command/bounds records),
all with equal source and destination dimensions and local coordinates (158,107).
All timestamped modes are TVMR=0, HRESO=0, LSMD=0. There are 331 manual-erase
begin/end pairs. None of this establishes the cause of the reported logo offset.
No speculative coordinate or display-mode change was made from this capture.

For any size/offset defect still present, capture only the affected game per
process. For OutRun, the Windows command is:

```bat
mame saturnjp outrun -verbose -log
copy error.log outrun-error.log
```

Exit MAME completely before the copy and before launching another game. Save a
screenshot of the remaining defect alongside the log, identifying the game/scene.
These OutRun instructions are conditional on a remaining visual defect; they are
not a request to repeat the supplied After Burner II capture.

## Supplied evidence

User upload: [commit c4ae255c](https://github.com/jkind73/mame/commit/c4ae255c6fcc0447f704826ff13b2262b7c554ab).
The commit message contains console output; `regtests/saturn/error.log` contains
VDP1TRACE records. The console identifies `saturnjp` with software `saturn:outrun`.
The user reports both visual defects existed at base commit `868d72fc`; they are
not established as regressions introduced by the later sliced renderer.

Analyzed file: 22,075,595 bytes, 122,954 lines, SHA-256
`e48833d63608b30d813f0398fdd98df39333dbd29db146067f77813f2e9fd374`.
The large original and console machine/device details are not duplicated here.

## Findings

- 2,265 draw starts, 2,265 END events, no abort events.
- 1,647 framebuffer exchanges; **zero have busy=1 before exchange**.
- All 65,800 timestamped records have TVMR=0, HRESO=0, LSMD=0. The compositor's
  mode-dependent X/Y doubling conditions are false in this capture.
- 44,945 scaled commands all have local coordinates (-192,0).
- At t=56.892954444, COPR=00d8, SRCA=7000, SIZE=0b29: source 88x41,
  destination 88x41, bounds (119,181)-(206,221). This car-sized command does not
  show enlargement or exchanged axes. Texture identity was not independently
  verified; this does not resolve the reported logo displacement/size problem.
- First scaled record is t=26.037959458. Earlier logo rendering cannot be diagnosed
  from scaled-only geometry logging. The trace now includes normal-sprite bounds.
- Console output also reports an unavailable D3DX effect entry point. There is no
  evidence here that this explains sprite disappearance; no host-renderer fix is
  claimed.

## Trace-derived flashing mechanism

Representative sequence (seconds):

| Time | Event |
|---|---|
| 56.724831177 | Swap: display bank becomes 1, drawing bank becomes 0; idle. |
| 56.724918498 | CPU writes FBCR=2 (manual erase). |
| 56.724918721–56.725697815 | Draw into bank 0 completes. |
| 56.741563434 | Next field: FBCR=2, no swap. |
| 56.741648444 | CPU writes FBCR=3 (manual change). |
| 56.741648556–56.741650344 | Short command list finishes; no scaled records. |
| 56.758295690 | Following field: swap displays bank 0. |

Before this fix, the FBCR=2 field called `vdp1_clear_framebuffer(display_bank)`
**at its beginning**. Bank 1 was therefore blanked for the second presentation
field, consistent with disappearing sprites while the VDP2 background remained.

[ST-013-R3](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf)
pp.39/49 specifies display-period manual erase. Pixel readout must precede erase.
Cross-checks: pinned MiSTer VDP1 separates display read/erase phases; pinned
[Mednafen](https://github.com/jkind73/mednafen-git/blob/f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc/src/ss/vdp1.cpp)
`GetLine` copies display pixels before its erase loop.

## Implemented correction and limits

Manual display erase now captures bank, data and bounds at the requested field.
It commits after that display field, at the following boundary **before bank
exchange**. The next drawing owner therefore receives the cleared bank, without
blanking the field that still needs to present it. Captured state is saved and
reset/system-reset cancellation discards pending work. This is a coarse
presentation-order model, not per-HBlank erase/scanout arbitration; existing
horizontal/vertical erase-extent limitations remain. Automatic erase and VBlank
erase paths are unchanged.

24 new tests cover repeated erase/change presentation pairs in both bank roles,
16-bit/packed formats, pending-state copies, captured data/bank ownership and
cancellation. Early erase and wrong-bank mutations fail assertions. All 18
regression scripts and nine production object compilations pass.

**OutRun flashing is user-confirmed fixed.** No claim is made that the
oversized/displaced logo is fixed. Rebuild this branch and test the same scene;
`-verbose -log` now also records normal-sprite source/destination bounds.

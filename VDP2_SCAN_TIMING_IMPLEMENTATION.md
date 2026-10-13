# VDP2 scan counters, exclusive timing and EXLAT

Implemented 2026-10-09 under the user's explicit authorization to use an emulator-derived model without real-hardware verification. **No real Saturn hardware measurement independently validates this implementation.**

The exclusive scan-timing and H/V counter checklist markers are complete under that authorization. Their original wording is preserved by request; the old claims that the dedicated-B target gives the wrong raster length and that exclusive-B VCNT advances at the horizontal jump are superseded by this report.

## Implemented behavior

The hidden horizontal phase is distinct from the linear screen position and the CPU-visible counter. Ordinary modes jump after 347/375 low-resolution dots to hidden phase 0x3B0. High resolution preserves the half-dot bit in CPU readback. Exclusive modes advance their phase in two-count slots, jump after 173/188 slots to 0x3B0/0x3D0, and wrap after 213/212 slots. Their raster lengths remain 852/848 system clocks, or 426/424 dedicated-normal screen pixels. Counter readback follows the mode-specific masking/shifting.

Exclusive TVSTAT.HBLANK follows the discontinuous phase, asserts at 0x148/0x168 and clears at phase 8. The external HBLANK callback follows the independent linear raster. For MiSTer's exclusive even-valued phase sequence, its comparator at nominal 0x143/0x163 minus one becomes a post-edge transition at linear 0x144/0x164. Its clear comparator at 2 becomes a post-edge transition at 4. High-resolution screen coordinates scale these positions by two. These edge conventions are deliberate; copying the nominal constants directly as screen positions would give a different model.

VCNT advances before the screen line ends. Ordinary modes advance at the horizontal discontinuity. Exclusive A advances at linear dot 346; exclusive B advances at dot 364, before its horizontal jump at 376. TVSTAT.VBLANK uses the same counter advancement. Dedicated vertical counters skip from 0x1E9 to 0x3DD or 0x1F6 to 0x3C5 and wrap at 0x3FF. Ordinary PAL/NTSC vertical skips depend on the active-height mode; double-density readback includes field parity. Existing external vertical callbacks remain distinct from TVSTAT readback.

The public `exlat_w(int)` input accepts a physical active-low pin transition at its scheduled machine timestamp. With EXLTEN set, a falling edge captures the contemporaneous formatted H/V counters and sets EXLTFG. Repeated low levels do not relatch; disabled edges do not latch. The input level is saved and retained across reset, while enable, captured counters and status reset. EXTEN-triggered internal capture and side-effect-aware TVSTAT flag clearing remain implemented. The API supplies the previously missing VDP2 input; physical light-gun board wiring is a separate consumer of that input.

## Validation

- macOS Saturn/ST-V build passed.
- `scripts/saturn_video_modes_test.py`: ASan/UBSan extracted real methods; ordinary/exclusive counter jumps and wrapping, counter widths, PAL/NTSC vertical skips, exclusive VBLANK transitions, EXLAT enable/edge behavior, alongside video-mode fixtures.
- `scripts/saturn_scan_timing_test.py`: real mapped VDP2 register reads across all eight horizontal modes, DRC and interpreter, using isolated generated diagnostic ROMs. This verifies executable device integration, not retail BIOS boot or hardware accuracy.
- Existing real-renderer window/rotation and real-framebuffer erase sanitizer fixtures pass.

Sources: Sega VDP2 2.5 counter layouts; VDP1 4.4 raster totals; https://github.com/MiSTer-devel/Saturn_MiSTer/blob/main/rtl/Saturn/VDP2/VDP2.sv . MAME implementation was written independently using observed numeric timing behavior, without copying GPL source.

## Board scan-edge save/load continuity, 2026-10-13

The shared board's previous HBLANK/VBLANK levels were uninitialized and omitted
from save registration. They now start low and are saved with the device signal
and timer state, preventing a restored state from using the abandoned timeline's
edge detector. The native `saturn_scan_state_test.lua` saves mid-frame away from
signal transitions, changes both detectors, loads, checks their restored levels
in the post-load notifier, then verifies subsequent HBLANK-IN and VBLANK-IN/OUT
events reach the SCU. Both DRC and interpreter pass; the previous binary fails
because its edge-detector state is missing. Artifacts:
`/private/tmp/scan-state-positive2-20261013` and
`/private/tmp/scan-state-negative-20261013`.

This fixes state restoration and startup initialization. It does not establish
hardware behavior with DISP disabled or complete the broader connected-device
reset checklist item.

## Megamix remains incomplete

Inspected current MiSTer and Mednafen sources for the remembered NBG2 B0-T1 PN / A0-T0 character fetch divergence. MiSTer's active NBG2/3 path still uses its early PN update, with the alternative bank-dependent update commented out. Mednafen's `T_DrawNBG23` explicitly applies a layer-offset workaround matching several Fighters Megamix register patterns; it does not provide an independent cycle-accurate fetch-port measurement.

Consequently the emulator disagreement is still unresolved. Changing the generic B-bank latency to four would choose the inactive RTL alternative on the basis of a reference-emulator workaround, potentially affecting other games. No minimized captured memory/slot trace demonstrating the correct returned pattern exists among the inspected local artifacts. This item remains `[ ]`; hardware-verification waiver alone does not supply the missing behavioral result or make a speculative change a verified fix.

## Duplicate counter audit entry — 2026-10-13

The section-12.3 H/V counter, rollback and latch item refers to the same
implemented counter engine described above. Re-ran the real-method video-mode
ASan/UBSan fixture and mapped-register scan diagnostic on both CPU engines.
All pass. The fixture covers vertical skip/wrap, horizontal discontinuities,
PAL/NTSC and dedicated counter layouts, and EXLAT edge/enable behavior.
The duplicate marker is now complete; its original text is unchanged. This
does not add physical hardware verification beyond the earlier authorized
emulator-derived implementation. Native logs: `/private/tmp/checklist-scan-20261013`.

## Timer 1 against the replaced H-counter model, 2026-10-13

The Timer 1 implementation is already connected to the scheduled HBLANK-IN
signal. Rechecked that connection with the native `saturn_timer1_scan_test.lua`:
12 settings in each of the eight horizontal modes, including zero's 512-count
reload and settings crossing the H/V counter discontinuities. Each case checks
that the real SCU status remains clear half a SCU clock before expiry and becomes
pending half a clock after expiry. The diagnostic then latches the mapped H/V
registers. DRC and interpreter produce identical 96-entry counter traces.

The historical header table is obsolete: it assumes the old signal position and
linear counter until the line ends. Selected current mode-0 latch values:

| Timer setting | Old header HCNT | Current HCNT |
|---|---|---|
| 1 | 0x282 | 0x288 |
| 0x10 | 0x2a0 | 0x2a4 |
| 0x20 | 0x2c0 | 0x36c |
| 0x40 | 0x300 | 0x3a8 |
| 0x69 | 0x352 | 0x3f4 |
| 0x6a | 0 | 0x3f6 |
| 0x80 | 0x02c | 0x020 |
| 0x100 | 0x12c | 0x110 |

These are measurements before the shared reset-clock correction below, not replacement hardware timing
constants. The parked diagnostic BIOS leaves SCU on its configured 352-mode
oscillator and VDP2 on its configured 320-mode oscillator; a real BIOS clock
change selects the clocks together, so these counters must not be treated as a
universal table. No production timing change was necessary for this recheck.
The stale verification TODO is removed, and the old observations remain labeled
historical. The original recheck checklist marker alone changes to complete.
No physical Saturn verification is claimed. Artifacts:
`/private/tmp/timer1-scan-20261013`.

## VDP2 register reset defaults, 2026-10-13

Corrected reset to clear TVMD and every decoded display, border, interlace and
resolution field, as required by [VDP2 2.4](https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p02_40.htm).
EXTEN already read back zero after reset, but external synchronization, display
area selection and external background controls retained their old decoded
values; these now clear together with the register per [VDP2 2.5](https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p02_50.htm).

The native reset regression writes dense-interlace, dedicated-monitor and
240-line configurations, enables all four EXTEN controls, and performs actual
scheduled machine resets. It checks public read-back, each decoded control and
the display-off VBLANK status. Both CPU engines pass; the previous binary fails
because TVMD retains its previous value. Artifacts:
`/private/tmp/vdp2-reset-positive-20261013` and
`/private/tmp/vdp2-reset-negative-20261013`.

No physical hardware verification is claimed. This is a documented register
reset correction, not completion of the entire board-reset or broad VDP2-note
checklist item. Their markers and original text remain unchanged.

## Connected SYSRES and shared reset clock, 2026-10-13

Completed the shared driver's system-reset path per [SMPC 2.3 SYSRES](https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p02_30.htm).
It detects the assertion edge, clears volatile memories and schedules MAME's
whole-machine reset after the command callback returns. This resets every
connected device, including the previously omitted SCSP and CD block, and
restarts the master at its power-on vector. Battery backup RAM, SMPC settings
and RTC storage remain retained. SMPC preserves the initiating command's
documented OREG31=0x0d result through that reset.

The existing 320-mode reset selection now drives all devices sharing that
oscillator, rather than resetting only the SH-2 clocks while leaving SCU/VDP2
on their previous selection. DCC follows the same divider used by clock-change
commands. Board scan-edge detectors also return to their initial levels.

Native tests perform CKCHG352 followed by SYSRES twice and check the CPU vector,
SCU/SCSP/VDP2/CD reset state, volatile memory clearing, battery data retention,
reset pixel period and command result. Both engines pass; the preceding binary
fails at the retained SCSP register. All 16 SCU/SMPC regression runs pass, as do
the all-mode Timer 1 and saved scan-edge checks and video-mode ASan/UBSan fixture.
The updated Timer 1 mode-0 trace now has HCNT 0x28a for setting 2, 0x2a6 for
0x10, 0x370 for 0x20 and 0x002 for 0x69. These are software-model measurements,
not hardware calibration values. Logs:
`/private/tmp/systemreset-result-positive-20261013`,
`/private/tmp/systemreset-negative-20261013`,
`/private/tmp/systemreset-full-dma-audit-20261013`,
`/private/tmp/systemreset-clock-timer1-20261013` and
`/private/tmp/systemreset-clock-scanstate-20261013`.

Retail HLE VF2J runs for 110 seconds with preserved initialized backup RAM,
reaches the first attract movie, and records its full 50.73-second audio section
(28.36–79.09 seconds). Fresh backup RAM instead stops at the expected BIOS
date-setting prompt and is not a game regression verdict. Retail artifacts:
`/private/tmp/systemreset-vf2-initialized-20261013`.
No physical hardware verification is claimed. Only the original shared-driver
reset checklist marker changes; the broader VDP2 item remains open.

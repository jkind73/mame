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

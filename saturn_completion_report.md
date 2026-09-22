# Saturn / ST-V Driver Completion Report

**Date:** 2026-09-22  
**Branch:** `arena/01a0b897-mame`  
**Published implementation head:** `35fa8676`  
**Scope:** implementation inventory and promotion plan; this is not a validator acceptance report.

## 1. Promotion definition

Promote the Saturn/ST-V driver only when the following are all true:

1. The documented hardware contract is implemented for VDP1, VDP2, SCU, SMPC, DMA, SH-2 master/slave, CD and sound interfaces.
2. Undefined and prohibited inputs are deterministic and do not depend on host timing, host randomness, or game-specific hacks.
3. Device state that affects execution is saved and restored coherently.
4. Native validator coverage confirms observable behavior against primary documentation, MiSTer, Mednafen, Ymir, and hardware captures where available.
5. No protected fixture, frozen behavior, or accepted subsystem is regressed.
6. Remaining limitations are explicitly documented rather than silently approximated.

Status vocabulary used below:

- **Implemented:** code exists, but validator acceptance may still be pending.
- **Candidate:** implementation change has a documented contract and local syntax/diff checks.
- **Open:** work remains or behavior is not sufficiently defined.
- **Blocked:** do not guess; a named artifact or measurement is required.
- **Frozen:** intentionally outside the current change scope.

## 2. Current checkpoint and published implementation history

| Checkpoint | Commit | Area | Status |
|---|---|---|---|
| VDP1 candidates | `a74a4302`, `8b229a14`, `9fbe664f` | erase/reset/framebuffer/memory | Implemented; acceptance tracked separately |
| VDP2/rendering candidates | `60dd59a3` through `d9c20cb0` | command LUT, colour, windows, scroll, rotation, framebuffer readout | Implemented; open edge cases remain |
| SCU | `9f6d24da` | Timer 1 HBlank behavior | Candidate |
| DSP | `ff84a2fc` through `c7577747` | stop/pipeline/ES/ENDI | Candidate; MVI wait and PDR coupling remain open |
| SMPC | `67c192fa` through `3e30bc8b` | RTC, STE, NMI, DDR, framing, VBlank collection | Candidate |
| DMA | `aad6e471` through `7e0ef6eb` | counts, addresses, CD tails/destinations | Candidate; integration edge cases remain |
| SH-2 DMA | `911b028f` through `fa44f923` | postdecrement, progress, buffering, suspension, NMI gates | Candidate; AE integration remains blocked |
| SH arithmetic/metadata | `0d4daf7a` through `8f115979` | defined multiply behavior, MAC metadata | Candidate |
| SH IRQ ownership | `fc78f6ae` | inherited poll latch ownership | Candidate; old-save compatibility disclosed |
| SH TIER | `900c3427` | TIER reset/reserved bits | Candidate; primary/peer discrepancy documented |
| SH DRC MAC | `9dbbc0e3` | baseline cycle accounting | Candidate |
| SH DRC illegal exception | `1fdfa573` | stack SR/PC before vector fetch | Candidate |
| SH DRC TRAPA | `446d8cb1` | charge pending cycles before handler dispatch | Candidate |
| VDP1 invalid modes | `35fa8676` | deterministic reserved colour-mode fetch | Candidate |

## 3. VDP1 completion plan

### 3.1 Already implemented / candidate behavior

- Command decoding and drawing paths for sprites, polygons, polylines, lines and distorted sprites.
- Normal, packed 8-bit and RGB texture access.
- Colour lookup-table latching for mode 1.
- Transparent-pixel, end-code, mesh, SPD/ECD and Gouraud-related paths.
- User/system clipping and out-of-plane transparency.
- Framebuffer bank ownership, manual erase, display-time erase and VBlank erase progression.
- Packed 8-bit CPU access, erase and display readout.
- Rotation/readout support and interlace-related state.
- Reserved colour modes no longer use host randomness; they use deterministic VRAM word-0 behavior.

### 3.2 Remaining implementation work

1. **Exact transfer-over semantics — Open**
   - Audit every texture mode and the interaction of SPD, ECD, end code, transparent pen, colour calculation and MON.
   - Cross-check each mode against ST-013 tables and the corresponding MiSTer, Mednafen and Ymir pixel paths.
   - Implement only differences that have a stable source/peer contract.
   - Track source pixel, destination pixel, control bits and resulting framebuffer word as observables.

2. **Reversed and empty erase windows — Open / needs primary clarification**
   - Define whether `X1 > X3` or `Y1 > Y3` means no operation, wrapped range, or a prohibited/undefined command.
   - Compare active-display, manual and VBlank erase independently.
   - Do not merge behavior based solely on emulator convention.

3. **Inclusive/exclusive erase endpoint accounting — Open**
   - Reconcile the register-unit dimensions, stored word width, row setup cost and current cursor conditions.
   - Resolve the apparent distinction between `(X3-X1+1)` budget units and the current exclusive write cursor.
   - Use a primary page/figure or hardware capture before changing endpoint semantics.

4. **Within-raster erase/readout/CPU arbitration — Blocked**
   - Current implementation is scanline/field-coarse.
   - Required artifact: hardware trace or authoritative timing capture showing ordering when CPU VRAM access, display readout and erase share a raster.
   - MiSTer/Mednafen/Ymir comparisons alone are not sufficient to establish silicon arbitration.

5. **CEF/BEF and command timing — Open**
   - Determine exact command completion and end-bit timing for normal, illegal, empty and chained command lists.
   - Resolve draw-by-request behavior and VDP1 end interrupt ownership with SCU.
   - Required observables: EDSR transitions, PTMR/FBCR state, command address, SCU interrupt edge and framebuffer completion.

6. **Geometry and texture edge cases — Open**
   - Pre-clipping versus post-clipping for reversed coordinates and degenerate primitives.
   - HSS/reduction rounding and end-code interaction.
   - Gouraud table edits during a command.
   - Wireframe/stipple behavior and polygon vertex ordering.
   - Preserve the existing documented limits until a primary/peer discriminator exists.

7. **VDP1/VDP2 composition — Open**
   - Verify per-dot priority, colour calculation, shadow, transparency and VDP1 readout format for all display modes.
   - Resolve high-resolution, interlace, rotated framebuffer and packed-8bpp lane behavior.

## 4. VDP2 completion plan

1. **Priority and layer mixing — Open**
   - Complete per-dot priority ordering between VDP1, NBG/RBG layers, sprites and back screen.
   - Verify ties, transparent dots, special priority and colour-calculation enable conditions.

2. **Windows — Open**
   - Finish normal/inverted window combinations, line-window behavior, sprite-window modes and clipping at boundaries.
   - Explicitly cover zero-width, reversed and coincident boundaries.

3. **Colour calculation — Open**
   - Validate normal/add/subtract/ratio modes, special colour modes, shadow and transparent-source handling.
   - Resolve fade direction and per-dot versus per-line control.

4. **Mosaic and reduction — implemented, acceptance pending**
   - Existing code covers NBG/RBG mosaic and reduction paths.
   - Validator must confirm block dimensions, interlace scaling, source sampling and reduction limits.
   - Remove or correct stale TODO text only after the implementation inventory is reconciled.

5. **Rotation/RBG parameter timing — Open**
   - Verify table reads, parameter reload controls, coefficient stepping, line changes, mosaic interaction and invalid/out-of-range coordinates.

6. **Raster/interlace/PAL timing — Open**
   - Confirm ODD, H/V counters, PAL field lengths, interlace field selection and partial update boundaries.

7. **External/unsupported layers — Open / scoped**
   - EXBG/MPEG/genlock and any external source path require an explicit supported/not-supported decision.
   - Do not silently present unsupported layers as complete.

## 5. SCU and DSP completion plan

1. **Timers — Candidate**
   - Confirm Timer 1 HBlank behavior, reload/underflow timing and interrupt edge ownership.
   - Reconcile timer state with VDP2 display-disable behavior.

2. **DSP — Candidate**
   - Confirm stop/pipeline drain, end/interrupt behavior and status timing.
   - **Blocked:** universal MVI wait timing without a primary or trace.
   - **Open:** PDR propagation where it interacts with frozen sound behavior.

3. **SCU DMA — Candidate**
   - Confirm programmed versus live count/address readback, 27-bit masking, CD A/B/C destination behavior and tail handling.
   - Preserve the frozen DMA acknowledgement behavior.

4. **DMA arbitration — Open**
   - DREQ, priority, bus ownership, waits and preemption during bursts.
   - Current fixes do not claim cycle-exact arbitration.

5. **SCU VDP1 end event — Open**
   - Determine whether the event is command completion, framebuffer completion, or a separately scheduled edge.
   - Requires a primary timing description and/or hardware capture.

## 6. SMPC, RTC and interrupt completion plan

1. **SMPC protocol — Candidate**
   - RTC phase, STE, BCD century, NMI debounce, DDR/SF strobe, extended framing and type-F zero payload are implemented candidates.
   - Validator must cover command framing, reset, abort, end/reset ownership and repeated commands.

2. **NMI/IRQ interaction — Open**
   - Confirm debounce, pending-latch lifetime, mask behavior and ordering relative to SH-2 instruction boundaries.
   - Do not alter frozen delay-slot IRQ behavior without a new primary contract.

3. **AE/address error — Blocked**
   - Required artifact: vector-10 behavior with SR.I, fault persistence, delay-slot context and above-NMI priority.
   - Existing changes do not implement a synthetic fault latch.

4. **SH-2 master/slave symmetry — Open**
   - Run the same protocol and exception matrix on both CPUs and confirm shared versus private state.

## 7. SH-2 core completion plan

1. **DRC cycle accounting — Candidate**
   - MAC baseline and helper accounting are implemented.
   - TRAPA now charges pending block cycles before dispatch and preserves the handler PC.
   - Illegal instruction vector fetch now follows SR/PC stacking.
   - Validator must check no double debit, correct resume PC and budget-exit state.

2. **Exception families — Open**
   - Ordinary illegal, slot illegal, address error, TRAPA, NMI and maskable IRQ need a unified matrix for stack order, saved PC, vector fetch, SR.I, delay-slot state and timing.
   - SH3/SH4 overrides must remain separately qualified.

3. **Reserved opcode behavior — Open**
   - Keep the existing frontend/generator fallback unless a reachable incorrect path is demonstrated.
   - Do not reintroduce the rejected invalid-descriptor fatal-guard bypass without a reproducer.

4. **SH-2 DMA — Candidate / integration pending**
   - Postdecrement, progress readback, buffered mode, private burst suspension and NMI gates are implemented candidates.
   - AE/vector integration, mid-block waits, DREQ and priority remain open.

5. **Peripheral instruction timing — Open**
   - DIVU edge cases, refresh request timing and SCI MPBT latch semantics remain blocked pending the named traces/primary evidence.

6. **Save-state compatibility — Required**
   - Explicitly test new and old save formats for fields changed in 0172 and subsequent SH state changes.
   - Treat pre-0172 saves as incompatible where already disclosed unless a migration path is added.

## 8. CD, SCSP and integration status

### CD

- Earlier CD promotion work and validator review were recorded as attributed acceptance for the accepted scope.
- Remaining integration work:
  1. folded-host semantic port;
  2. residual BFUL Home/reset edge;
  3. trustworthy Q readout;
  4. preserve EOF/Abort ownership through End/reset;
  5. preserve `FAD = LBA + 150` and exclusive leadout behavior.

### SCSP

- Sound reset/video-clock behavior, LFO/EG/FM/PCM/MVOL and frozen game-specific behavior are out of the current change scope.
- Do not reopen frozen sound fixes while completing video or SH work.

### IO-02 inventory

- Keep the supported/not-supported device inventory explicit.
- Do not close IO-02 merely because a related device path has a candidate implementation.

## 9. Validator promotion checklist

1. Run TU syntax checks for every changed production file.
2. Run `git diff --check` and inspect generated diffs for unintended fixture/evidence changes.
3. Build using the validator-owned native configuration.
4. Run the complete Saturn/ST-V script set without skips.
5. Run live-host checks for VDP1/VDP2, SCU, SMPC, DMA, SH-2 and CD.
6. Run BIOS replay and representative Saturn/ST-V game smoke coverage.
7. Run save/load tests across reset, VBlank, DMA, exception and CD boundaries.
8. Compare master/slave behavior and interpreter/DRC behavior.
9. Record every failure as a new candidate or blocker; do not mutate fixture expectations to hide it.
10. Promote only after the validator records acceptance with commit, artifact, observable, tolerance and limitations.

## 10. Work ordering

1. VDP1: transfer-over, erase-window endpoints, CEF/BEF, command timing, then arbitration blockers.
2. VDP2: priority/mixing, windows, colour calculation, rotation/interlace/PAL edge cases.
3. SCU/DSP: timer and DMA event timing, then VDP1 end-event integration.
4. SMPC: protocol and interrupt boundary completion.
5. DMA: arbitration, DREQ, waits and master/slave integration.
6. SH-2 master/slave: exception matrix, DRC/interpreter parity, AE blocker, peripheral timing.
7. CD integration and final IO-02 inventory.
8. Validator-owned promotion run and release decision.

## 11. Explicit non-claims

- No full build or runtime validation was performed by this implementation agent for the current checkpoint.
- No VDP1/VDP2 timing behavior is claimed cycle-exact unless specifically documented above.
- MiSTer, Mednafen and Ymir are peer cross-checks, not substitutes for silicon evidence when all peers share an approximation.
- Frozen DMA acknowledgements, delay-slot IRQ behavior, sound fixes and game-specific fixes remain frozen.
- Parent milestones remain open until the validator records acceptance; candidate commits do not close parent IDs.

# Saturn/ST-V game-blocker implementation plan

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


Goal: implement missing behavior that can prevent games from starting or progressing,
with reproducible failures, primary-document evidence and regression tests. This is
not a claim to enumerate every remaining compatibility issue. No particular game
has been shown fixed by the changes below in a linked runtime yet.

## Delivery requirements

1. Reproduce the failure in the real emulator when an executable/image is available,
   or identify a concrete missing control with a standalone regression.
2. Compare Sega documentation and pinned reference implementations; document any
   disagreements rather than choosing whichever implementation is convenient.
3. Implement the smallest general fix, without title-specific bypasses or invented
   successful responses. Preserve meaningful error conditions.
4. Run regressions/object checks, then link/configuration/BIOS/game/save-load checks
   where available. Keep compile/test evidence separate from runtime claims.
5. Push source, tests and documentation on the session branch.

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

## Previous confirmed implementation gap addressed

**SCU DMA forced stop — implemented, standalone-tested.** DSTP at $05FE0060 was
unmapped. A masked write of bit 0 now cancels all three CPU-programmed DMA channels,
including waiting/background transfers and held restarts, without manufacturing
completion IRQs or changing programmed registers/enables. Tests cover 2,321 cases,
including restarting after cancellation. Sega ST-097 §3.2 and Ymir/Mednafen support
this control. Exact stop latency and actual game impact still need runtime tests.

## Prioritized remaining work

| Priority | Candidate / evidence | Required next evidence or implementation |
|---|---|---|
| P0 | Runtime validation is unavailable: pkg-config and SDL development files remain missing; previous package downloads failed. | Build on an environment with the documented dependencies, link the focused executable, run `-validate`, then BIOS boot and a representative Saturn/ST-V smoke matrix. Nine standalone objects are not a substitute. |
| P1 | DMA B-Bus read width/fixed-source handling: ordinary writers now buffer longword reads, with 1,152 new cases; odd counts/alignment remain open. | Validate source readback, odd counts and bus-specific destination alignment against hardware/runtime traces. Some configurations are prohibited by Sega and must not be treated as valid requirements. |
| P1 | CD data-port failure path: invalid long reads are nonfatal and bounded; exact idle/dummy value is not verified. | Reproduce which commands/reads reach it. Establish real idle/overread/rejection behavior before replacing the exception; do not simply return fake success. Audit transfer bounds and completion state alongside this. |
| P1 | Pending work across reset/save-load and shared CPU halt lines. | Boot/reset traces and save/load round trips during direct/indirect/held DMA. Existing halt callbacks are an approximation and interact with SMPC; do not unconditionally release another component's halted CPU. |
| P1 | CD command/sector-transfer completion and timing TODOs. | Reproduce load/progression failures, compare documented command/status sequences and test complete transfers. Compilation of CD components does not validate protocol behavior. |
| P2 | DCC/SMPC handshakes, input/control timing and slave CPU synchronization. | Paired CPU traces and representative software; current DCC object compilation is not behavioral coverage. |
| P2 | VDP1 draw-completion/erase timing, VDP2 combinations. | Prioritize status/interrupt waits that stall software, then graphical defects. Do not equate a visual TODO with a game-start blocker. |
| P2 | External interrupt acknowledgement and sampling edge cases. | Hardware/ref comparison plus CD/runtime traces; IMS polarity is fixed, but the whole external acknowledgement bus is not validated. |
| P3 | MPEG cartridge-specific support. | Relevant hardware documentation, firmware and reproducible titles. This is not required for ordinary non-MPEG Saturn software. |

The CD block's disabled low-level SH-1 is not by itself proof that all games require
an LLE rewrite: CD HLE is the existing execution path. Likewise, unimplemented
refresh timing is not automatically a demonstrated boot blocker.

## Runtime test matrix to establish

- Saturn BIOS boot, reset and CD menu; ST-V BIOS startup.
- Supplied, legally available representative titles covering disc loading, CD audio,
  SCU DSP use, DMA streaming, slave-CPU synchronization and ST-V protection paths.
- For each failure: set name/region, image identification, reproducible steps, log,
  interpreter/DRC setting, first divergent event and a narrowly justified fix.
- Reset/save-load during transfer, progression beyond menus and bounded runs with
  no debugger/fatal stops. Frame/audio correctness and performance are separate checks.

**Current validation:** thirteen regression scripts and eight object compilations
pass. No linked executable, BIOS boot, game progression or hardware measurement
has been established. Completion of “all game blockers” cannot be certified yet.

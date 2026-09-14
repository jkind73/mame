# Saturn/ST-V game-blocker implementation plan

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

## Current confirmed implementation gap addressed

**SCU DMA forced stop — implemented, standalone-tested.** DSTP at $05FE0060 was
unmapped. A masked write of bit 0 now cancels all three CPU-programmed DMA channels,
including waiting/background transfers and held restarts, without manufacturing
completion IRQs or changing programmed registers/enables. Tests cover 2,321 cases,
including restarting after cancellation. Sega ST-097 §3.2 and Ymir/Mednafen support
this control. Exact stop latency and actual game impact still need runtime tests.

## Prioritized remaining work

| Priority | Candidate / evidence | Required next evidence or implementation |
|---|---|---|
| P0 | Runtime validation is unavailable: pkg-config and SDL development files remain missing; previous package downloads failed. | Build on an environment with the documented dependencies, link the focused executable, run `-validate`, then BIOS boot and a representative Saturn/ST-V smoke matrix. Eight standalone objects are not a substitute. |
| P1 | DMA B-Bus read width/fixed-source handling: `dma_transfer_direct_default` explicitly still reads a word, with a TODO for longword reads and word writes. | Trace correct source buffering, increments, odd addresses and partial counts against Sega/ref implementations; add executed transfer tests before replacing the path. Some configurations are prohibited by Sega and must not be treated as valid requirements. |
| P1 | CD data-port failure path: `dataxfer_long_r` throws an emulator-fatal error for invalid transfer mode. | Reproduce which commands/reads reach it. Establish real idle/overread/rejection behavior before replacing the exception; do not simply return fake success. Audit transfer bounds and completion state alongside this. |
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

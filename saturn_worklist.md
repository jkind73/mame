# Saturn Work List — ordered by reference coverage (5 refs: Ymir, MiSTer, mednafen, yabause, SaturnRecomp)

Post 07ee024a fix — SCSP boots, 0 TODO in SCSP.

## Tier 2 — next (high coverage, should be doable)

### 1. VDP2 H/V blank + V counter rollback (5/5 refs) — **DONE**

- Files: `saturn.cpp` @TODO list (vpos 0=0x1ff VBE, 1=0, 241=0xf0 VBI, 247=0x1ef rollback, 263=0x1ff), `saturn_vdp2.cpp:418` refine hblank/vblank, `446` second setting at 241, `484` T0C runs after.
- Implemented: true_vcount table with BREAK/JUMP (NTSC 224 236->486, 240 245->495, PAL 224 257->458, 240 265->466, 256 273->474), VBI active+1, HBlank via m_hdisplay, sync_timer walks VBlank.
- Refs: Ymir vTimingsNormal, MiSTer BREAK/JUMP.

### 2. SCU timer0/1 semantics (5/5 refs) — **DONE**

- Files: `saturn.cpp` @TODO: Timer 0 doesn't work if TENB not enabled, fires at HBlank-In not before; Timer1 0=512, counts backwards from 0x6b; Yabause note DISP bit gates vblank irqs.
- Fixed: T1MD at 0x0098 (was 0x009A) so TENB actually enables timers, timer0 at HBlank-In, timer1 0=512 handling, DISP gates VBlank flag per TB12.

### 3. SCU waitstate penalties (2 refs: MiSTer + Ymir partial) — **DONE**

- Files: `saturn_scu.cpp:446` waitstate penalties needs HW tests, `517` SDRAM refresh overhead, `403` FIXME /4 vs BIOS.
- Implemented: ASR0/ASR1/AREF at 05FE00B0/B4/B8, AnNW+3 formula, dma_hog_bus steal callbacks.

### 4. SMPC TH control mode — 3D Lemmings ID (1-2 refs) — **DONE**

- File: `sat_console.cpp:821` — TH Control mode returns ID, Ymir has handling.
- Implemented: TH=3 returns ID per Ymir smpc.cpp.

### 5. DOTSEL guard (2-3 refs) — **DONE**

- File: `saturn_vdp2.cpp:307` guard against wrong DOTSEL from SMPC.
- Implemented: reconfigure_crtc checks m_dotsel_352 vs HRESO bit 0, logs instability.

## Tier 2 — medium coverage

- SCU DMA bus validation (`saturn_scu.cpp:636,790`) — we did directional rules in 6113d660, but TODO other rules still applies.
- DCC irqline 0xff vs 0x00 (`saturn_dcc.cpp:114`)
- B-Bus dword read / word write (`saturn_scu.cpp:903`)

## Tier 1 remaining (low coverage)

- CD HLE MPEG ROM retrieval (`saturn_cd_hle.cpp:2542`) — needs MPEG cart ROM dump, Ymir has MPEG.
- CD sector read path (`saturn_cd_hle.cpp:2208`)

## Tier 3 — rendering edge cases (long tail, 0-2 refs, game-specific)

- VDP1 automatic draw timing (Night Striker S)
- VDP1 framebuffer clear on VBE
- VDP2 line scroll / line zoom (Batman Forever)
- VDP2 rotation param window (OVPNRA/B)
- Pretty Fighter X, Game Tengoku shadows, etc.

## Tier 4 — refactor

- VDP1/VDP2 code structure split (issue #8915) — move out of saturn_state
- NVRAM config change bug
- Spaghetti / optimization TODOs

## Proposed next commit

Implement #1 VDP2 V counter rollback + H/V blank positions — highest ref coverage, unblocks timer0 and VBlank IRQs.

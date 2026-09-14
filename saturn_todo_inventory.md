# Saturn TODO Inventory — 2026-09-13 (post 07ee024a fix)

## DMA address-register width update — 2026-09-14

Programmed DxR/DxW addresses now retain only bits 26:0, not cache-alias bit 29,
per Sega and Ymir/Mednafen/MiSTer. Extracted lambdas pass address/count readback
coverage with two failing pre-fix controls. Register-update overflow, full MMIO
routing and runtime CPU/cache behavior are not established by this correction.

## A-Bus interrupt mask update — 2026-09-14

Fixed reversed IMS15 polarity using ST-097 and Mednafen; the pinned Ymir condition
disagrees with the manual. Added arbitration, acknowledgement and register-write
coverage with a failing pre-fix control. Full external acknowledge cycles, input
sampling and actual SH-2/CD/game behavior still require runtime validation.

## A-Bus refresh register update — 2026-09-14

AREF now resets to 0x10 per Sega's later erratum and stores only defined bits 4:0.
New register/reset/static-decoder coverage passes with two failing pre-fix controls.
This corrects stored configuration, not physical refresh timing: AREF is not yet
consumed by the bus model. Existing static wait approximations remain unvalidated
against hardware; no game/performance benefit is claimed.

## Held DMA trigger audit — 2026-09-14

Existing external-event hold behavior passed 924 new scenarios, including one-slot
restart and suspended level 0. Added event-filter extraction and five failing
mutation controls; no production change. ST-210/Mednafen corroborate holding;
Ymir's pinned external-trigger path differs. DxGO, held-state reset/save-load and
real scheduler timing remain open.

## DMA arbitration update — 2026-09-14

Fixed two-channel preemption suspending the wrong channel, and made halt callback
handoff consistent with the existing direct/indirect model. 64 supported overlap
scenarios pass through resume/completion, cross-checked against documented priority
and Ymir/Mednafen. Exact physical bus timing and unsupported overlaps remain open.

## Indirect DMA count update — 2026-09-14

Corrected indirect counts to twenty bits on every channel, with zero meaning
1 MiB, cross-checked against Ymir/Mednafen and MiSTer width. 54 legal two-descriptor
chains pass through completion. This extends the earlier direct-only coverage;
full DMA arbitration/timing and unusual descriptor/transfer cases remain open.

## C-Bus mirror decode update — 2026-09-14

SCU now recognizes `0x07xxxxxx` high work-RAM mirrors, consistent with Saturn/ST-V
address maps and Ymir/Mednafen. 768 classification checks and 2,304 direct DMA
scenarios pass. Full DMA timing/indirect-chain validation and precise primary
mirror-aperture documentation remain outstanding.

## TVMD startup/reset update — 2026-09-14

TVMD and decoded display/interlace/resolution controls now initialize before the
startup clock notification and clear on device reset, following ST-058 §2.4 and
Ymir/Mednafen. 3,072 scenarios pass; complete runtime/reset wiring and the wider
register/status initialization audit remain pending.

## EXTEN reset update — 2026-09-14

Fixed stale decoded EXTEN bits after reset, following ST-058 §2.5 and cross-checks
with Ymir/Mednafen. 64 read/write/reset/latch scenarios pass. This is an EXTEN
coherence fix, not completion of the wider VDP2 power-on/reset or lightgun audit.

## Double-density counter encoding update — 2026-09-14

The documented double-density bit layout is now implemented and cross-checked
with Ymir/Mednafen: field count in bits 9:1 and inverse ODD in bit 0. 47,016
V-counter checks pass including independent encoding and external-latch storage.
This supersedes earlier approximate-encoding notes below only for this mode;
rollback thresholds, field phase and non-interlace discrepancies remain open.

## Timer-0 implementation update — 2026-09-14

The compare-zero/increment-order issue identified below is fixed and tested:
zero at VBlank-OUT, positive compares after HBlank increment, TENB-gated counting.
8,192 two-frame callback scenarios pass. Earlier statements that timer-0 ordering
is still next are superseded by this update; exact CRTC phase, register-write
side effects and full timer-1 mode behavior remain open. See the current report
in `regtests/saturn/README.md` rather than interpreting historical DONE labels as
hardware validation.

## Timer-1 implementation update — 2026-09-14

The stopped-only HBlank reload issue below is now fixed and regression-tested
against ST-210 item 31, with Ymir/Mednafen cross-checks. 1,024 reload scenarios
plus gating/mask tests pass. Timer-0 ordering, full T1MD interrupt semantics and
hardware clock-rate validation remain open; this is not a blanket timer DONE.

## Primary-document audit update — 2026-09-14

[`regtests/saturn/official_specs.md`](regtests/saturn/official_specs.md) now records
exact sections/pages read from the SDK hardware manuals and technical bulletins.
It reopens timer-0 compare ordering, timer-1 running/reload semantics, interlaced
counter encoding, and fractional/combined cell scroll. These are not resolved by
the safety fixes below. The linked manifest indexes 103 PDFs; it is not a claim
that all documents were read.

## Current-branch follow-up — 2026-09-14

The historical DONE labels below describe prior implementation work, not proof
of hardware accuracy. See `regtests/saturn/README.md` for reproducible tests and
pinned reference notes. Line numbers below belong to the inherited snapshot.

- **VDP2/SCU HBlank delivery:** corrected missing horizontal edges during VBlank;
  the slave SH-2 HBlank IRQ remains VBlank-gated. 72 callback configurations pass.
- **Mosaic safety:** bounded partial blocks to the clip rectangle; 16,384
  sanitizer-backed configurations pass. Mosaic/line-screen compositing is still
  gated and is **not** marked implemented.
- **Vertical cell-scroll clipping:** preserve caller limits, skip wholly clipped
  columns and empty clips, retain screen-based table indices. 21,312 sanitizer
  configurations pass; inherited code fails clip containment. The eight-dot
  width remains unchanged pending hardware verification.
- **V counter double-density safety:** convert doubled screen rows to field
  lines before the 313-row table lookup. The inherited getter produces an
  AddressSanitizer out-of-bounds read; the corrected getter passes exhaustive
  configured-frame lookup checks. Existing field-bit encoding remains approximate.
- **V counter table cleanup:** removed redundant fills and contradictory comments;
  all 2,504 table entries match the inherited implementation. This does not
  validate rollback thresholds against hardware.
- Complete `saturn.cpp` and `saturn_vdp2.cpp` translation units pass standalone
  syntax checks after correcting inherited include order. Full build/ROM testing
  and exact hardware timing validation remain pending.


Generated after SCSP 0-outputs regression fix. Tree boots saturnjp + aburner2 at 100% (28s). SCSP now has 0 TODO/FIXME.

## How to read

- **File:Line — text**
- **Refs**: which of 5 reference emulators (Ymir, MiSTer, mednafen, yabause, SaturnRecomp) already solve it, based on prior cross-checks and manual notes.
- **Tier**: 1 = CD/SCSP/SMPC functional, 2 = SCU/VDP accuracy, 3 = VDP1/VDP2 rendering edge cases, 4 = ST-V specific.

---

### 1. SCU — `saturn_scu.cpp`

- `7: TODO:` — file header placeholder, not actionable.
- `403: FIXME: should be /4 but saturn BIOS already disagrees` — DMA timing divisor? Needs HW test. Refs: MiSTer models /? Ymir? Unknown. Tier 2.
- `446: TODO: waitstate penalties needs HW tests` — ASR/AREF wait penalties. We already implemented MiSTer AnNW+3 formula in 2d0ed85c, but TODO remains. Refs: MiSTer solved, Ymir partial. Tier 2. **DONE in this branch — ASR0/ASR1/AREF at 05FE00B0/B4/B8, penalties AnNW+3, DMA hog via steal callbacks.**
- `517: TODO: overhead due of SDRAM refresh?` — DMA bus steal overhead. Tier 2. **DONE — dma_hog_bus with 1+penalty steal.**
- `636: TODO: check if other buses can be used` — DMA source/dest bus validation, we implemented No.01/02 in 6113d660 but TODO remains for other combos. Tier 2. **DONE — directional rules A-Bus read-only dest, VDP2 read-only source, SCU reg exclusion, DMA-illegal IRQ.**
- `648: TODO: reimplement me` — likely DSP? Needs context. Tier 2.
- `778: TODO: why guardherj sets up a 0x23000 transfer for the FMV?` — game-specific. Tier 3.
- `790: TODO: other rules still applies` — DMA illegal rules. Tier 2. **DONE — see above.**
- `903: TODO: actually reads as dword and writes as word for B-Bus transfers` — B-Bus width. Refs: Ymir? Tier 2.
- `910,930: TODO: reimplement me` — DSP/INT? Tier 2.

### 2. VDP2 — `saturn_vdp2.cpp`

- `7: TODO:` header.
- `112: TODO: PAL only 256 mode` — PAL 256-color? Tier 3.
- `217: TODO: version` — VDP2 version register. Tier 3.
- `221: TODO: probably akin to YM7101 equivalent on stock Saturn` — VDP2 dot clock? Tier 3.
- `260: TODO: interlace mode "eats" one line, should be 262.5` — interlace. Refs: Ymir handles, mednafen? Tier 2/3.
- `284: TODO: divider is always 8, need to compensate out of lack of MAME interlace support` — DOTSEL divider. Tier 3.
- `293: TODO: Unknown for Exclusive modes` — VDP2 exclusive. Tier 3.
- `307: TODO: guard against the wrong DOTSEL being configured from SMPC.` — SMPC DOTSEL validation. Tier 2. **DONE in this branch — guard added in reconfigure_crtc with m_dotsel_352 check (MiSTer/Ymir).**
- `319: TODO: this should just be reserved and return VRESO == 2` — VDP2 VRESO bits. We already mask VRESO in earlier commit 65937035? Check. Tier 2.
- `329: TODO: find a software that makes use of this` — unknown reg. Tier 3.
- `418: TODO: refine hblank/vblank positions` — H/V blank timing. Refs: Ymir has precise tables. Tier 2. **DONE — now uses Ymir/MiSTer BBd/BSy/VCS/TBd/LLn/ADp timings, VBI 225/241/257, VBE at 0=0x1FF, rollback 247=0x1EF.**
- `424: if (cur_h > visarea.right()) //TODO` — H counter vs visarea. Tier 3. **DONE — now uses m_hdisplay threshold.**
- `446: TODO: test says that second setting happens at 241, might need further investigation ...` — VDP2 line. Tier 3. **DONE — VBI at 241 for 240 mode.**
- `463: TODO: 263 & 313 needs to be static constexpr` — NTSC/PAL line counts. Tier 3 (trivial).
- `484: TODO: T0C in SCU seems to run even after this point` — SCU timer 0 vs VDP2. Tier 2. **DONE — sync_timer_cb now walks through VBlank lines and only flips ODD at last line, timer0 continues via HBlank.**

### 3. Saturn core — `saturn.cpp`

This file is huge (10k lines) and contains most VDP1/VDP2 legacy implementation (now split to stvvdp1/2 devices but still here for saturn).

- `8: @TODO List of things that needs to be implemented:` — top-level list, contains many of below.
- `45: TODO (VDP1):` / `77: TODO (VDP2):` — section headers.
- `85: scud zoom-in on melee attacks with pink backgrounds (TODO: reinvestigate this),` — game-specific VDP? Tier 3.
- `88: cfr. gpanicss gal select, one of the Wangan games (TODO: find which),` — Tier 3.
- `137: Framebuffer TODO:` — VDP1 framebuffer. Tier 3.
- `283, 407: TODO:` — placeholder.
- `322: TODO: stuff that should really be in VDP1` — code structure. Tier 4 (refactor, like issue #8915).
- `335: TODO: when Automatic Draw actually happens? Night Striker S is very fussy...` — VDP1 timing. Refs: Ymir has more accurate VDP1 timing. Tier 2/3.
- `346, 2305: TODO: temporary for Batman Forever, presumably anonymous timer not behaving well.` — anon timers. Tier 3.
- `443: TODO: edge triggered?` — IRQ edge vs level. Tier 2.
- `449: TODO: actually send a device reset signal to the connected devices` — reset. Tier 2.
- `4866: TODO: disable read control if these undocumented bits are on (Radiant Silvergun Xiga final boss)` — VDP2 undoc bits. Tier 3.
- `619: TODO: write-only regs should return open bus or zero` — VDP1 regs. Tier 3.
- `622: TODO: TVM & 1 is just a kludgy work-around, the VDP1 actually needs to be rewritten from scratch.` — VDP1 TVM. Tier 3/4.
- `7339,7340: TODO: vertical linescroll, linezoom` — VDP2 line scroll. Tier 3.
- `7396: TODO: + 16 for tilemap and char size = 16?` — VDP2 tile. Tier 3.
- `7423: TODO: needs layer bitmaps to be individual planes to work correctly` — VDP2 layers. Tier 3.
- `7625: TODO: not supported, cfr. VDP2_OVPNRA / VDP2_OVPNRB` — VDP2 rotation param window. Tier 3.
- `7673: TODO: nuke this spaghetti code` — VDP2 code quality. Tier 4.
- `8088: TODO: check cycle pattern for RBG1` — VDP2 RBG1. Tier 3.
- `8515: TODO: Cotton 2 enables mode 3 without an actual RP window enabled` — VDP2 mode. Tier 3.
- `8858,8865: TODO: mode 0 handling, byte writes are goofy` — VDP2. Tier 3.
- `9088,9392: TODO: Optimize / remove crap` — performance. Tier 4.
- etc — many rendering edge cases, mostly Tier 3.

### 4. CD Block HLE — `saturn_cd_hle.cpp`

- `26: TODO:` header.
- `185, 659, 993, 1043, 1485, 3792: FIXME` — various CD timing/buffer issues.
- `288: TODO: move out of here, breaks daytoncej boot` — CD HLE init. Tier 1 (but we already fixed CD timing in 9a970027/d8d80151).
- `392, 571, 591, 619, 653, 782, 787, 796, 819, 829, 867, 875, 1053, 1137, 1176, 1292, 1310, 1536, 1546, 1569, 1808, 1854, 1863, 1916, 1929, 1956, 1975, 2093, 2208, 2542, 3336, 4140, 4177, 4193` — ~40 TODOs covering seek timing, filter, buffer full, partition init, etc. Many already addressed in Tier1 CD commits (88/89). Remaining: MPEG cart integration (done in 79), MP3, etc. Tier 1/2.

### 5. DCC — `saturn_dcc.cpp`

- `11: TODO:` header.
- `114: TODO: 0xff rather than 0x00 for irqline == 0?` — DCC IRQ. Tier 2.

### 6. ST-V — `stv.cpp`

- `11: TODO:` header.
- `121,124,218,558,1207,1239,1374,1422,1434,2031,2133,2134,3432,3769,3875,3891,3911,3932,3955,4194: TODO` — ST-V specific: SCSP reset line, RAX->SCSP, coin error, EEPROM defaults, etc. Many ST-V drivers have similar SCSP mirror fix already done in a9c5cfa7. Tier 2/3.

### 7. Console driver — `sat_console.cpp`

- `16,407: TODO:` headers.
- `550: TODO: Bug! accesses this one, if returning 0 the SH-2 hard-crashes. Might be an actual bug with the CD block.` — A-Bus dummy. We already return -1. Tier 2.
- `663: TODO: if you change the driver configuration then NVRAM contents gets screwed, needs mods in MAME framework` — NVRAM. Tier 4 (framework).
- `821: TODO: 3D Lemmings bogusly enables TH Control mode, wants this to return the ID, needs HW tests.` — SMPC TH control. Refs: Ymir handles? Tier 2.

---

## Work List ordered by reference coverage (5 refs)

We order by how many of Ymir/MiSTer/mednafen/yabause/SaturnRecomp already solve it (higher first = easier to port).

### Tier 1 (CD functional — mostly done)

- CD seek timing, SCDQ periodic, filter invert — DONE (88/89)
- MPEG cart — DONE (79)
- SCSP DMA burst + DGATE + wrap — DONE (2aedb4de)
- SCSP EG — DONE (9c2774f9)
- SMPC RTC battery — DONE (c5c90716)
- SCSP re-clock SAMPLE_CLOCKS — DONE (9cfda641)

Remaining CD TODOs (low ref coverage):

- `saturn_cd_hle.cpp:2542` MPEG ROM retrieval — needs MPEG cart ROM dump (Tier 1, 1 ref: Ymir has MPEG)
- `saturn_cd_hle.cpp:2208` how to actually read? — CD sector read path

### Tier 2 (SCU/VDP2 timing, interrupts)

High coverage (4-5 refs solve):

- VDP2 H/V blank positions, V counter rollback (saturn.cpp @TODO list, vdp2.cpp:418) — Ymir + MiSTer + mednafen have precise tables (5/5). **Next candidate**.
- SCU timer0/1 semantics (saturn.cpp: timer0 fires at HBlank-In, T0C=0 timing, timer1 0=512) — Ymir + MiSTer + mednafen (5/5). We have partial in scu but TODO remains.
- IMS reset at vector fetch — DONE (c19e25f8)
- SCU waitstate penalties (scu.cpp:446) — MiSTer has formula (2 refs: MiSTer, Ymir partial)
- DOTSEL guard (vdp2.cpp:307) — Ymir + MiSTer (2-3 refs)
- SMPC TH control mode (sat_console.cpp:821) — Ymir has handling (1-2 refs)

Medium coverage (2-3 refs):

- SCU DMA bus checks (scu.cpp:636, 790) — we did 6113d660 but TODO remains
- DCC irqline 0xff vs 0x00 (dcc.cpp:114) — Ymir?
- B-Bus dword read / word write (scu.cpp:903) — needs HW test

Low coverage (0-1 ref, needs HW tests):

- guardherj FMV transfer size (scu.cpp:778)
- SDRAM refresh overhead (scu.cpp:517)

### Tier 3 (VDP1/VDP2 rendering edge cases)

Mostly 0-2 refs, game-specific, long tail:

- VDP1 automatic draw timing (saturn.cpp:335) — Night Striker S fussy
- VDP1 framebuffer clear on VBE (saturn.cpp: vblank_line+1)
- VDP2 line scroll / line zoom (saturn.cpp:7339-7340) — Batman Forever Riddler stage
- VDP2 rotation parameter window (saturn.cpp:7625)
- VDP2 layer bitmaps as individual planes (saturn.cpp:7423)
- Pretty Fighter X, Game Tengoku shadows, etc.

### Tier 4 (Refactor / framework)

- VDP1/VDP2 code structure split across saturn_state and stvvdp1/2 devices — issue #8915 closed but code still split (needs refactor, no functional change)
- NVRAM config change bug (sat_console.cpp:663) — framework
- TODO: nuke spaghetti, optimize, etc.

---

## Next actionable (proposed order)

1. **VDP2 H/V blank + V counter rollback** — 5/5 refs have it, we have partial but TODO: refine hblank/vblank positions (vdp2.cpp:418) and saturn.cpp @TODO list. Implement Ymir's vpos table (line 0=0x1ff VBE, line 1=0, line 241=0xf0 VBI, line 247=0x1ef rollback, line 263=0x1ff).
2. **SCU timer0/1** — 5/5 refs, timer0 TENB gating, HBlank-In firing, timer1 0=512 and backwards counting from 0x6b.
3. **SCU waitstate penalties** — finish ASR/AREF implementation (scu.cpp:446) with HW tests from MiSTer AnNW+3.
4. **SMPC TH control** — 3D Lemmings ID return (sat_console.cpp:821).
5. **CD HLE MPEG ROM retrieval** — needs actual MPEG ROM.

All above are Tier 2, high ref coverage.

## Build-validation follow-up — 2026-09-14

All six regression scripts plus actual object compilation of the three changed
C++ files pass (`regtests/saturn/validate_build.py`). This is stronger than the
syntax-only checks above, but still not a linked MAME build. Missing development
packages and failed sandbox package access block full-build validation; ROM
runtime/save-state/performance checks remain outstanding.

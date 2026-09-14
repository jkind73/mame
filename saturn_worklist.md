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

## Follow-up audit — 2026-09-14

The DONE labels above describe inherited implementation work, **not complete
hardware validation**. Review and test results are in
[`regtests/saturn/README.md`](regtests/saturn/README.md).

- Fixed a remaining scheduler gap: HBlank edges were still skipped throughout
  VBlank, starving SCU timer/DMA events. Slave HBlank IRQs remain VBlank-gated.
- Callback regression harness passes 72 configurations and rejects the inherited
  implementation. Full build/game validation is pending (missing build tools).
- Next: runtime timing traces, V counter/interlace bounds and field-coordinate
  audit, then SCU timer semantics and DMA bus width. Do not assume existing
  breakpoint tables or wait-state formulas are validated solely by DONE labels.

### Mosaic bounds follow-up

- Applied clipping safety fix from the supplied candidate patch, without enabling
  the incomplete mosaic/line-screen compositing paths.
- 16,384 sanitizer-backed helper configurations pass; inherited implementation
  fails the bounds assertion. Full `saturn.cpp` syntax check passes after fixing
  its inherited include order. Details: `regtests/saturn/README.md`.


### V counter bounds and table follow-up

- Fixed double-density screen-row indexing: divide by two before field-table
  lookup, rather than masking a doubled screen position to nine bits.
- Simplified region-specific initialization to one fill per table cell. All
  2,504 entries remain identical to the inherited implementation.
- 42,920 table/getter checks pass with ASan/UBSan; the inherited getter reproduces
  an out-of-bounds read. Exact rollback thresholds and interlaced counter encoding
  are still unverified. Exclusive-mode lookup behavior is unchanged.
- Updated `saturn_todo_inventory.md` with current-branch validation notes.

### Vertical cell-scroll clip follow-up

- Fixed caller clip containment for first/last columns; skip wholly clipped
  columns and empty clips while preserving screen-anchored table addressing.
- 21,312 sanitizer-backed configurations pass; inherited code fails the clip
  assertion. Reduced nested-renderer call counts verified, not benchmarked.
- Existing eight-dot width retained. Sixteen-dot character behavior, combined
  line zoom/vertical line scroll, and game-level output remain unverified.


## Official SDK specification audit — 2026-09-14

See [`regtests/saturn/official_specs.md`](regtests/saturn/official_specs.md)
and its 103-PDF manifest. Selected hardware-manual and bulletin sections were
read, not just SDK library documentation. Indexed does not mean fully reviewed.

**Reopened correctness items supported by primary documentation:**
- SCU timer 1: ST-210 item 31 allows HBlank reload only while stopped; current
  code unconditionally re-arms on eligible lines. Fix/test this next.
- SCU timer 0: ST-210 item 30 puts compare-zero at VBlank-OUT; current callback
  clears without comparing, while HBlank compares before incrementing.
- V counter: ST-058 table 2.4 specifies double-density field count in bits 9:1;
  current approximate encoding remains inconsistent. Bounds safety is fixed,
  exact hardware encoding is not.
- Vertical cell scroll: fractional table data and bulletin #14 combined-scroll
  example are not handled by the current restricted path.
- Screen-over repeated pattern is cell-format only; include this restriction in
  any future implementation. CRAM byte prohibition does not prove ignored writes.

No emulator changes made in this audit pass; earlier DONE labels must be read
alongside these reopened items.

### SCU timer-1 stopped-only reload — implemented and unit-tested

- ST-210 item 31, cross-checked with Ymir and Mednafen: preserve a running count
  across HBlank; reload only when stopped. Account for MAME adjust(never) leaving
  enabled=true. No new saved-state members.
- 1,024 reload scenarios plus gating/mask tests pass under ASan/UBSan; baseline
  fails repeated-HBlank deadline test. Existing tests and three syntax checks pass.
- Timer-0 compare ordering remains next. Full timer accuracy, actual T1MD IRQ
  qualification, simultaneous event ordering and ROM compatibility remain open.

### SCU timer-0 ordering — implemented and callback-tested

- ST-210 item 30 / ST-097 §3.4, cross-checked with Ymir and Mednafen: compare zero
  at VBlank-OUT; increment before HBlank compare; TENB gates counter operation.
- 8,192 two-frame scenarios pass; pre-fix callbacks fail compare-zero regression.
  All six regression scripts and three syntax checks pass. Use
  `python3 regtests/saturn/run_all.py` to reproduce the complete ROM-free suite.
- Physical CRTC phase, immediate register-write effects, full T1MD IRQ semantics,
  save/load and runtime compatibility remain unverified. No blanket timer DONE.
- Next priorities: full build/runtime validation and interlaced counter encoding.

### Build-validation follow-up

- All six regression scripts and object-code compilation of the three changed
  C++ translation units pass using `regtests/saturn/validate_build.py`.
- Full-build preflight fails because pkg-config/SDL development dependencies are
  missing; sandbox package downloads failed over HTTP and HTTPS. No linked MAME
  executable or ROM boot validated. A documented `--full` recipe is preserved
  for a machine with dependencies; it is not yet verified end-to-end.

### Supplied firmware availability

- User commit `8578abbe02220ae4d174d364b4544997cb61a2cd` supplies BIOS/CD firmware
  candidates. Archive integrity and 35 relevant entry SHA-1s checked against Sega
  source declarations; metadata preserved in `regtests/saturn/firmware_manifest.json`.
- `saturn2`/`saturnzi` are unrelated games, not Sega Saturn BIOSes. Korean BIOS is
  still the driver's BAD_DUMP placeholder. Audit adds no additional binaries; the
  user's remote BIOS commit is preserved.
- BIOS availability no longer blocks future startup checks; full executable build
  remains blocked and BIOS hashes are not evidence of successful boot/game tests.

### Double-density VCNT encoding — implemented and tested

- ST-058 table 2.4, Ymir and Mednafen agree: field count in bits 9:1, inverse ODD
  in bit 0. Fixed the getter's bit replacement/nine-bit truncation.
- 47,016 V-counter checks now pass, including 4,096 independent encoding/latch
  cases. Pre-encoding and pre-bounds negative controls both fail as expected.
- All six regression scripts and three object compilations pass. Normal/single-
  density/exclusive behavior and all rollback values are unchanged. Exact field
  timing and runtime validation remain open; no blanket interlace DONE.

### EXTEN reset coherence — implemented and tested

- ST-058 §2.5 plus Ymir/Mednafen: reset clears all four decoded EXTEN control bits
  with the raw register, restoring register-read HV latching.
- 64 write/reset/latch scenarios pass; baseline reset fails coherence. Seven
  regression scripts and three object compilations pass. Whole-device reset,
  actual address-map dispatch, lightgun timing and runtime validation remain open.

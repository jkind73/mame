# Sega Saturn / ST-V driver — master implementation plan

Branch: `arena/01a0d806-mame`
Baseline commit analysed: `a999555891ee3df19a53a2eb8eb885d07cc870ea`
Date of analysis: 2026-09-25

---

## Phase 1 — measured state of the tree (all claims verified this session)

### 1.1 Driver promotion flags

| Driver | Location | Flags at HEAD |
|---|---|---|
| `saturn`, `saturnjp`, `saturneu`, `saturnkr`, `vsaturn`, `hisaturn` | `src/mame/sega/sat_console.cpp:1341-1352` | all `MACHINE_NOT_WORKING` |
| ST-V (`stvbios` + ~40 games) | `src/mame/sega/stv.cpp:5928+` | mostly `MACHINE_IMPERFECT_SOUND \| MACHINE_IMPERFECT_GRAPHICS` |

The console drivers are therefore **not** promoted. The ST-V entries carry
"imperfect" rather than "not working", which is a separate question from whether
they are trustworthy.

### 1.2 The verification harness is red at HEAD — the central finding

`regtests/saturn/run_all.py` is the project's own runner. Executing every
`test_*.py` individually at HEAD gives:

```
44 PASS / 29 FAIL
```

This is the blocker. A red suite cannot certify anything, so **no** "working"
claim is currently supportable for either driver. Restoring it is Phase 0.

The 29 failures split into three verified categories:

**(a) Stale harness mock / stale extraction list — 26 tests.** Every symbol the
harnesses report as missing still exists in production:

| Symbol the harness cannot see | Where it actually lives |
|---|---|
| `m_register_reset_cb` | `saturn_vdp2.h:57`, used `saturn_vdp2.cpp:108-109` |
| `read_ext_size` | `ctrl.cpp:94`, `ctrl.h:40`, called `smpc.cpp:968` |
| `update_execution_state` | `scudsp.cpp:407` |
| `m_lps_active` | `scudsp.h:129`, `scudsp.cpp:401,874,929,1015,1091,1129,1200` |
| `ESF` | `scudsp.h:96` (`= 0x0002'0000`) |
| `m_intback_wait` / `INTBACK_WAIT_*` / `m_in_vblank` / `m_reset_button_count` | `smpc.h:151,171-174` |
| `vdp2_expand_color5` | `saturn.cpp:6327` |
| `vdp2_palette_color_msb` | `saturn.cpp:9154`, `saturn.h:469` |
| `vdp2_rebuild_memory_views` | `saturn.cpp:11121`, `saturn.h:514` |

Mechanism: these harnesses *extract* production functions from the source text
and splice them into a hand-written mock class. Production gained members and
free helpers; the mocks and extraction lists were not updated. The generated
translation unit then fails to compile. Production is not broken.

**(b) Stale literal-source assertions — 1 test.** `test_vdp1.py:105` requires
the literal text `vdp1_abort_draw();` inside `saturn_state::machine_reset()`.
`machine_reset()` now calls `vdp1_reset()` (which itself calls
`vdp1_abort_draw()` as its first statement, `saturn.cpp:2969+`). The behaviour
is preserved one level down; only the text match fails.

**(c) Behavioural assertions encoding superseded semantics — 2 tests.**
`test_timer0.py` and `test_timer1.py`. Adjudicated against the SDK below.

### 1.3 SDK adjudication of the SCU Timer 0/1 conflict

Ground truth extracted from the Sega Saturn SDK (`jkind73/saturnsdk`):

- **ST-097-R5-072694.pdf — "SCU User's Manual"**, p.11 (Figure 1.16), Timer 1
  Mode Register: timer-1 mode bit `=0: occurs at each line`,
  `=1: occurs only for lines designated by timer 0`; enable bit `=1: ON`.
- **ST-097** pp.31-32 (Figures 2.13/2.14): both diagrams label
  "Timer 1 Data Set (each line)". The *load* is per-line in **both** modes; only
  interrupt *occurrence* depends on the mode bit.
- **ST-210-110194.pdf — "SATURN SCU Final Specs: Precautions" No. 31**:
  "Loading the value of Timer 1 set data register to Timer 1 occurs **'when
  Timer 1 is stopped and H-Blank occurs.'** If data larger than the count number
  of 1 line is set ... Timer 1 interrupt no longer occurs for each line.
  (Be aware that this becomes **512** when a count number of 0 is specified)"
- **ST-210 No. 30** (Timer 0 compare): "T0C9-0 = 0 -> Interrupt occurs with the
  same timing as V-Blank-OUT"; 264~1023 -> no interrupt.

Production `saturn_scu.cpp::hblank_in_w` loads Timer 1 on the `stopped && HBlank`
condition with no T1MD test, uses `m_t1s ? m_t1s : 512`, and gates only the
*interrupt* in `timer1_irq_cb` via `(m_t1md && m_timer0_counter != m_t0c)`.
`vblank_out_w` fires Timer 0 when `m_t0c == 0`. **All four documented rules are
implemented correctly.** The two failing tests assert the older semantics in
which T1MD gates the load — contradicted by No. 31 — so the tests are wrong.

Timer 1 decrement rate was separately checked and is **correct**: SCU clock is
`MASTER_CLOCK_352` = 14318181 x 4 = 57272724 Hz (`saturn.h:657`,
`sat_console.cpp:1103`), and `from_ticks(count, clock()/8)` = 7159090 Hz, which
is the manual's "7 MHz or about 1/4 the system clock" (28.6364/4). No change.

---

## Phase 2 — itemized master plan

### Phase 0 — restore verification (prerequisite for every later phase)

- **0.1** SCUDSP harness group (9 tests): `test_scudsp_cbus`, `_count_operand`,
  `_dma`, `_pause`, `_hostflags`, `_lop`, `_multiplier`, `_parallel`,
  `_pipeline`. Add `ESF` to the mock flag enums, add `m_lps_active`,
  `m_step_pending`, `suspend`/`resume` endpoints and `SUSPEND_REASON_HALT`, and
  extract `update_execution_state()`.
- **0.2** SMPC harness group (4 tests): `test_smpc_handshake`, `_timeout`,
  `_transport`, plus `test_controller_slots`. Add `m_intback_wait`,
  `INTBACK_WAIT_*`, `m_in_vblank`, `m_reset_button_count` and `read_ext_size`.
- **0.3** VDP2 harness group (13 tests): extract/declare `vdp2_expand_color5`,
  `vdp2_palette_color_msb`, `vdp2_rebuild_memory_views`, `m_register_reset_cb`.
- **0.4** VDP1 + scanout: fix the stale literal assertion in `test_vdp1.py`;
  repair `test_sprite_scanout`.
- **0.5** SCU timer tests: rewrite `test_timer0.py` / `test_timer1.py`
  expectations to the ST-210 No.30/No.31 semantics, with citations, and keep a
  mutant proving the new assertions bite.
- **0.6** Re-run the full runner; require 73/73.

### Phase 1 — SMPC
Interrupt-back CONTINUE/BREAK timing, VBlank-driven peripheral scan, NMI reset
button sampling (3 samples -> NMI), PDR1/PDR2 and DDR polarity, EXLE/IOSEL
latch timing, save-state coverage.

### Phase 2 — SCU
DMA level arbitration (ST-210 No.20: two channels concurrent), indirect-mode
3-longword table layout (No.25), A-Bus/B-Bus contention (No.12), refresh
initial state (No.33), DSP interface, interrupt mask/status polarity.

### Phase 3 — VDP1
Command list fetch/execute timing, PTM state machine, per-command end codes,
framebuffer banking, erase timing, CEF/BEF, clipping, mesh/endianness.

### Phase 4 — VDP2
RAMCTL bank/size decoding, cycle patterns, per-line scroll and cell scroll,
rotation window/parameter latch timing, colour offset and calculation,
back-screen, priority and shadow.

### Phase 5 — SCSP
Slot envelope/LFO phase, DSP MVOL/mixer, timer phases, MIDI FIFO, DMA, IRQ.

### Phase 6 — SH-2 master/slave
Dual-SH2 bus arbitration and inter-CPU synchronisation, cache/FTLB behaviour,
DCC (slave-to-master) channel, IRQ vectoring through SCU/DCC.

### Phase 7 — promotion gates
Re-audit the flags in 1.1 against measured behaviour; promote only what the
restored suite plus a live BIOS replay actually demonstrates.

---

## Environment constraints (recorded honestly)

- 2 CPU cores, 3 GB RAM, no ccache. A full MAME link is not feasible here.
  Verification is therefore the extracted-function ASan/UBSan suite, which does
  execute the real production function bodies.
- No game ROMs. `regtests/*.zip` **do** contain real firmware
  (`sega_101.bin`, `mpr-17933.bin`, `stv110.bin`, ...), so a BIOS boot replay is
  possible once a binary can be linked.

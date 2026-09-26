# Saturn / ST-V master plan (audit of 2026-09-25)

Companion to `saturn_completion_report.md` and `saturn_stv_completion.md` (component checklist).
Ordered by subsystem; SCU DMA and VDP2 first, per project direction: fix missing
hardware behaviour before triaging individual games.

## A. Verified against SDK and peers: no defect found

Checked against ST-097 (SCU User's Manual), ST-210-110194 (SCU precautions), Mednafen `scu.inc`
and Ymir `scu.cpp`. Do not reopen without a reproducer.

| Behaviour | Code | Reference |
|---|---|---|
| DxR/DxW 27-bit, DxC 20-bit (L0) / 12-bit (L1, L2), zero count = max | `saturn_scu.cpp` `dma_map` | ST-097 3.2, Mednafen `StartByteCount`, Ymir `AdjustZeroSizeXferCount` |
| Direct mode illegal setup (same bus, A-bus dest, VDP2 source, SCU/none) raises DMA-illegal, nothing moves | `trigger_dma_direct` | ST-210 No.01/02, Ymir, Mednafen |
| Indirect descriptor: 3 longwords, count/write/read order, bit 31 end flag, 20-bit count, 0 = 1 MiB | `dma_tick_cb` | ST-210 No.25, Mednafen `NextIndirect`, Ymir |
| Start trigger during transfer is held once and re-run after completion | `pending_trigger` | ST-210 No.22 |
| IMS reset to 0000BFFFH on master vector fetch | `irq_ack_cb` | Mednafen `SCU_MSH2VectorFetch`, Ymir |
| Timer 0 counter is 9 bits, compare 10 bits, T0C=0 fires at VBlank-OUT | `hblank_in_w` | ST-210 No.30, Ymir |
| Timer 1 loads on HBlank only while stopped, 0 means 512 | `hblank_in_w` | ST-210 No.31 |

## B. Open items with a known contract (implementable)

1. **VDP2 stale documentation.** `saturn.cpp` header TODOs still list mosaic, reduction limits,
   per-line raster effects and shadows as missing; the code implements them (ST-058 citations).
   Reconcile the comment block with the implementation so real gaps are not hidden.
2. **stv.cpp MINIT/SINIT aliases** at 21000000H/21800000H: done (`99ad10bbe46`).
3. **CD block periodic report** gated on command state: done (`c910217351d`).

## C. Open items that need a hardware trace or measured table (do not guess)

| ID | Item | Needed artifact |
|---|---|---|
| SCU-04 / BUS-01 | B-bus device wait states (SCSP/VDP1/VDP2/SCU penalties are commented out in `get_address_flags`); burst vs cycle-steal cost | measured per-bus DMA timing; Mednafen `dma_write_tab` and MiSTer sequencer are the only sources |
| SCU indirect mode | Legality of a descriptor whose buses are illegal mid-chain. ST-210 No.24 says no DMA-illegal IRQ in indirect mode; Ymir raises one, Mednafen ignores the return value | hardware capture |
| SCU DMA | Register write while the level is active (ST-097 says prohibited, ST-210 No.23 says hang) | hardware capture; neither peer models it |
| V2-T02 | VRAM cycle-pattern contention and CPU/VDP2 grants | VDP2 access timing capture |
| V1-01 | VDP1 command/pixel costs, erase/readout arbitration | VDP1 timing capture |
| SH-2 | DIVU busy-stall on register read (Mednafen `divide_finish_timestamp`), AE vector 10 | needs exact mid-block time in the DRC; contract exists (39 / 6 cycles), infrastructure does not |

## D. Runtime findings (roms in `roms/` and `Z:\mame\roms`)

* All five local Saturn discs reach attract/gameplay; Daytona USA needs the US BIOS (region lock).
* ST-V survey: 104 of 119 games launch; blank after 65 s: rsgun, elandore, skychal, techbowl, znpwfvt,
  pcpooh2, dfeverg. rsgun/elandore reproduce on the pre-session build too. Master waits on a flag
  its interrupt handler never sets; SH-2 DMAC ch1 and FRC verified healthy. Treat as a symptom
  to re-test after A/B/C work, not as a target.

## E. SH7604 chip audit (2026-09-25, code read against ADE-602-085C)

Method: each on-chip module's code was read against its manual chapter.

Fixed (all verified through the debugger on the Saturn BIOS):

| Module | Defect found in code | Change |
|---|---|---|
| INTC | DIVU overflow interrupt was stored but never raised; BSC compare-match request absent; equal levels resolved in the wrong module order | `sh2_recalc_irq` follows Table 5.4 and adds DIVU/REF |
| BSC | RTCNT never counted, CMF never set, no CMI | refresh timer per 7.2.5-7.2.7 (closed form checked against a tick simulation for all counter/RTCOR states) |
| Reset | no manual reset, BSC/UBC never re-initialised, watchdog overflow only set WOVF | power-on/manual reset types, WDT internal reset with RSTS, /WDTOVF pin, 512-clock hold |
| DMAC | every channel was auto-request; no DREQ/DACK, SCI RXI/TXI requests, single-address mode, DMAOR.PR, address errors; on-chip register addresses were masked so the DMAC could not reach them | reworked per section 9 |

Open in the SH-2 (each needs a design decision, not a guess):

* **UBC**: only BARA/BARB are stored; BAMR, BBR, BDR, BDMR, BRCR and the user-break exception are absent.
* **CPU address errors** (vectors 9/10, Table 4.6): the core never raises them. The DRC accessors would need an exception path that knows the faulting instruction.
* **Cache**: CCR is stored only; no cache array, purge, way or 2-way behaviour is modelled.
* **Standby/module stop**: MSTP4/MSTP2 (DMAC, DIVU), SBY standby and FMR clock multiplication are not modelled.
* **NMI edge select**: ICR.NMIE is stored, NMIL read-back ignores it (TODO in `intc_icr_r`).

Reference-oracle note: the Ymir source in `docs` has empty vendor submodules (fmt, mio, libchdr deps), so it cannot be built here without downloading them.

## F. SCSP audit (2026-09-26, `scsp.cpp`/`scspdsp.cpp` read against Ymir, MiSTer `SCSP.sv`, ST-077)

Done already (committed `81812edad51`): LFO stepped in whole-sample intervals (1020..1 samples per step,
Ymir `s_lfoStepTbl`), advanced every sample regardless of PLFOS/ALFOS. Regression: `regtests/saturn/test_scsp_lfo.py`.

Read and found consistent with the references (no action): DSP microprogram decode incl. NOFL bit 8, INPUTS latch,
26-bit ACC, SHIFT/ADRL/FRCL, MADRS/RBL/RBP addressing, one memory access per step, EFREG persistence, UNPACK/PACK;
slot addressing, interpolation, loop modes, SDIR/STWINH paths, EG tables.

Open, needs a decision or a hardware capture (not to be guessed):

| ID | Item | Note |
|---|---|---|
| SCSP-01 | Interrupt priority: MAME uses the maximum pending level, MiSTer uses a fixed source order | inconclusive between references |
| SCSP-02 | `aica.cpp` has its own LFO struct (phase accumulator) that was not updated | same interval model may apply; AICA is out of Saturn scope, record only |
| SCSP-03 | Remaining unread: timers, DMA (`exec_dma`), MIDI, slot register readback (`UpdateRegR`), master volume, per-sample mixer/pan/DAC ordering | complete Phase 1 read |

## G. SCU DSP audit (2026-09-26, `scudsp.cpp` against Ymir `scu_dsp.cpp`)

Compared: ALU op set and flags, X/Y/D1 bus parallel semantics incl. CT increment-once and same-bank read/write
suppression, MVI/JMP/LPS/BTM/END/ENDI, condition codes, DMA count (8-bit, 0 = 256), DMA address-add tables,
program-RAM DMA restart at TOP, ENDI edge rearm on PPAF read. No behavioural difference found that is
attributable to MAME being wrong. Differences that remain and need a capture rather than a guess:

* Ymir treats condition codes as OR-ed bit masks (Z|C etc.); MAME decodes only the documented codes (1,2,3,4,8).
* Instruction timing is approximated (DMA cycle-steal, 1-cycle ops); the source says the real timings are unknown.

## H. VDP1 verification plan (harness built, run not completed)

A randomized single-command differential harness exists in the scratchpad (`yoracle/vdp1fuzz.cpp` generates cases
and draws them in Ymir; `yoracle/vdp1fuzz.lua` replays them in MAME with the CPUs parked and reads
`m_vdp1_legacy.framebuffer[]`). Status: Ymir side generates cases (a case with a gouraud polyline never signals
draw-finished and needs investigation on the Ymir side); the MAME side is written but has not been run, and the
comparison script does not exist yet. Phase 2 work item: finish it, triage differences against ST-013 and MiSTer
`VDP1.sv`, and record each mismatch here with the arbiter used.

## I. Remaining Phase 1 coverage (not yet audited)

VDP2 (all layers, rotation, colour calculation, line/back screens, windows, mosaic, interlace) against Ymir and MiSTer;
VDP1 drawing rules above; SCU DMA legality decision (SCU-D1: peers allow A-bus writes and VDP2 reads, MAME rejects);
CD block, SMPC (commands, timings, peripherals), IOGA/cartridge/ST-V I/O, SH-2 dual-CPU synchronisation, memory map
versus `saturn_memory_map.md`. Sections A-E above remain the only completed audits; F and G are complete for the parts stated.

## J. Process note

Implementation is Phase 2 and proceeds item by item from this document. One SCSP LFO change was implemented during
Phase 1 (`81812edad51`); it is listed here so the Phase 2 order can account for it.

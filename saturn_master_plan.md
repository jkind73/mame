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
| SCSP-01 | Interrupt priority to the 68K: MAME picks the highest pending level over SCILV0-2 with sources 8-10 sharing source 7's level; Ymir does the identical computation (`UpdateM68KInterrupts`). Only MiSTer's fixed source order differs | keep MAME; MiSTer RTL to be re-read to see whether its order is a simplification |
| SCSP-02 | `aica.cpp` has its own LFO struct (phase accumulator) that was not updated | same interval model may apply; AICA is out of Saturn scope, record only |
| SCSP-03 | Timers (TIMA-C load-on-next-tick, SCIRE re-pend), SCIEB/SCIPD/SCIRE/MCIEB/MCIPD, MIDI in/out FIFOs, DMA (burst on DEXE, DGATE, DMA-register self-target ignored), TEMP/MEMS/MIXS/EFREG/EXTS readback windows, COEF/MADRS mirrors: read, consistent with Ymir/mednafen | no action |
| SCSP-04 | The 1Fs sample-tick interrupt (SCIPD bit 10) is raised once per sound-stream update batch, not once per 44.1 kHz sample as on hardware; code comment says it follows Yabause | quantify batch size; per-sample raise would need the 68K to be scheduled at sample granularity |
| SCSP-05 | Register 0x400 bit 9 (MEM4MB) is neither stored nor used; Ymir stores it but does not use it either | document only; check MiSTer `SCSP.sv` for any effect on the RAM address map |
| SCSP-06 | DMA and 68K wait states from SCSP RAM arbitration are not modelled (source comment, same in Ymir/mednafen) | needs measured timing |

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

## K. SMPC audit (2026-09-26, `sega/smpc.cpp` against Ymir `smpc.cpp` and Mednafen `smpc.cpp`)

Command set, INTBACK staging, SETTIME/SETSMEM/STE, RESENAB/RESDISA, CKCHG halt/NMI sequence and command timing table
are implemented and are a superset of Ymir (which lacks CDON/CDOFF and NETLINK). Defects/gaps recorded:

| ID | Item | Evidence |
|---|---|---|
| SMPC-01 | SYSRES scope: `system_reset_w` resets SCU/VDP1/VDP2, clears RAMs and pulses only the master SH-2 reset. The slave SH-2 (and its SSHON/SSHOFF shadow), the SCSP/68K, the CD block and the clock ratio (return to 320) are not reset. Ymir's soft reset resets both SH-2s (slave off), SCU, VDP, SMPC, SCSP, CD block and clock; Mednafen's CKCHG path also resets the sound CPU/SCSP | Ymir `Saturn::Reset(false)`, Mednafen `smpc.cpp` |
| SMPC-02 | The RAM clearing in SYSRES (work RAM, sound RAM, VRAM) is asserted by a comment ("only backup RAM and SMPC RAM are retained"); Ymir does not clear RAM on soft reset | decide from ST-169 text before changing |
| SMPC-03 | NETLINK on/off only logs; undocumented SEC_GETSEED/SEC_VERIFY (0x1E/0x1F) unhandled | no reference behaviour available |
| SMPC-04 | Command timing for INTBACK peripheral collection is a fixed 700 us (TODO per device) | ST-169 pp.55-57 |

## L. CD block audit (2026-09-26, HLE `saturn_cd_hle.cpp` command dispatch against ST-162, `docs/cdblock`, Mednafen `cdb.cpp`)

| ID | Item | Evidence |
|---|---|---|
| CD-01 | **Defect**: commands 0x65 and 0x66 are swapped. The dispatch calls `cmd_move_sector_data()` for 0x65 and `cmd_copy_sector_data()` for 0x66; 0x65 is Copy Sector Data and 0x66 is Move Sector Data | `docs/cdblock/saturn_cdblock_commands.md` lines 725/736, `saturn_cdblock_firmware.md` 637-638, Mednafen `COMMAND_COPY_SECDATA = 0x65`, `COMMAND_MOVE_SECDATA = 0x66` |
| CD-02 | 0x05 Open Tray is not dispatched; it falls to the unknown-command path (popmessage, only CMOK set) | Mednafen `COMMAND_OPEN`, Ymir `CmdOpenTray` |
| CD-03 | 0x55 Execute FAD Search and 0x56 Get FAD Search Results are commented out | Mednafen implements both |
| CD-04 | Remaining MPEG commands are partly stubbed (0xA7-0xAD reject by design); 0xE2 handled | acceptable per ST-162 text quoted in code |

## M. Memory map audit (2026-09-26, `sat_console.cpp` `saturn_mem` against `docs/system/saturn_memory_map.md`)

Every region of the documented map is present with the documented bus behaviour: BIOS/SMPC/backup RAM/work RAM-L in the
CPU-local space, MINIT/SINIT windows (cache-through aliases included), A-Bus dummy area, CS2/CD block, SCSP RAM and
registers, VDP1 VRAM/frame buffer/registers, VDP2 VRAM/CRAM/registers, SCU registers, work RAM-H with mirrors, purge
space, cache address and data arrays. Cartridge areas (CS0/CS1) are mapped dynamically in `device_start` per cartridge ID
(battery RAM 21h, data RAM 5Ah, ROM), which is why the static map lines are commented out.

Decision input for SCU-D1 (DMA legality, section C): `saturn_memory_map.md` cites ST-210 No.01 (A-bus writes by SCU-DMA
prohibited) and No.02 (reading VDP2 by SCU-DMA prohibited), which is exactly what MAME rejects. The peers' permissive
behaviour is therefore not supported by the SDK text; recommendation for Phase 2: keep the current rejection, and only
change it if a hardware trace shows the transfer completes.

Unverified in this pass: exact mirror extents (work RAM-L mirrored at 00300000H, work RAM-H mirror span, SCSP register
mirror stride, VDP1 register window 20h vs documented 18h) against a hardware read-back.

## N. ST-V I/O audit (2026-09-26, `315_5649.cpp`, `stv.cpp` legacy `ioga_r/w`)

No IOGA (315-5649) documentation exists in `docs` (SDK, cartridge notes, MiSTer and Ymir do not cover ST-V), so this
chip can only be checked for internal consistency, not against a hardware reference. Observed:

| ID | Item |
|---|---|
| IO-01 | The device implements ports A-G with a direction register, port G 4x16-bit counter mode with auto-increment and reset latch, the analog mux with auto-increment, two RS-422 channels with holding registers and loopback, and the mode register. Serial timing is byte-level (transmit register drains immediately) and the status error/enable bits (RX IE, framing) always read 0 |
| IO-02 | `stv.cpp` still carries a duplicate legacy `ioga_r/w` (marked TODO "remove this legacy fallback") used by the per-game maps for critcrsh, stvmp and the hopper games; it reimplements the port G counter and the mode/serial-status reads separately from the device (the serial status read there is a constant 0) |
| IO-03 | Port D coin counter/lockout mapping and the billboard write are inferred from game behaviour, not from a document |

Phase 2 candidates that need no new hardware data: route the legacy per-game maps through the device (removing the divergence in IO-02).

## O. SH-2 dual-CPU synchronisation audit (2026-09-26, `saturn_dcc.cpp`, `sat_console.cpp` config, `sh2.cpp` cycle accounting)

Implemented: MINIT/SINIT as 16-bit-only write triggers into the other CPU's FRT input capture (byte/longword writes
ignored), a temporary tighter scheduler quantum around each trigger, per-CPU interrupt acknowledge (master through the SCU
with IMS reset, slave through the DCC vector table 41h-43h), SMPC SSHON/SSHOFF as a reset line, SCU DMA/system halt lines
shared with SMPC clock change.

| ID | Item |
|---|---|
| DUAL-01 | The core charges a fixed cycle count per instruction from a table; no per-access memory wait states (SDRAM CAS latency, SCU bus, A/B-bus penalties) and no bus arbitration between the two CPUs for work RAM-H/SCU are modelled, so relative timing of the two CPUs is approximate. The two SH-2s are interleaved by the scheduler quantum, not by shared-bus contention |
| DUAL-02 | The tighter quantum after MINIT/SINIT is a constant (`INTERLEAVE_DIV`/`INTERLEAVE_DURATION`), not derived from hardware timing |
| DUAL-03 | Cache is not modelled (Section E), so cache-coherency-sensitive code paths (cached vs cache-through alias) behave as if always coherent |

These need measured bus timing (see C: SCU-04/BUS-01) rather than a guess; recorded as accuracy limits, not defects.

## H2. VDP2 verification plan

Name-based coverage grep of the VDP2 register set in `saturn.cpp` found the registers implemented (RPMD/RPRCTL/KTCTL,
coefficient tables, colour-calc, line colour, shadow, window, mosaic, zoom, cycle patterns); name matching cannot prove
behaviour. Plan: extend the same capture-and-replay oracle (MAME injects random VRAM/CRAM/register state, Ymir renders
it) with randomized static VDP2 states per feature group (NBG0-3 cell/bitmap in every colour depth, RBG0/1 with both
coefficient modes, priority/colour-calc/extended-CC, windows, line-colour and back screen, mosaic, hi-res/interlace).
Limits already known: mid-frame register changes cannot be reproduced, so per-line effects are checked separately by
reading the code against ST-058.

## I. Remaining Phase 1 coverage (not yet audited)

VDP2 (all layers, rotation, colour calculation, line/back screens, windows, mosaic, interlace) against Ymir and MiSTer;
VDP1 drawing rules above; SCU DMA legality decision (SCU-D1: peers allow A-bus writes and VDP2 reads, MAME rejects);
CD block, SMPC (commands, timings, peripherals), IOGA/cartridge/ST-V I/O, SH-2 dual-CPU synchronisation, memory map
versus `saturn_memory_map.md`. Sections A-E above remain the only completed audits; F and G are complete for the parts stated.

## J. Process note

Implementation is Phase 2 and proceeds item by item from this document. One SCSP LFO change was implemented during
Phase 1 (`81812edad51`); it is listed here so the Phase 2 order can account for it.

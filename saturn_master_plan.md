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

## H. VDP1 verification (differential fuzz against Ymir; tooling in `regtests/saturn/vdp1_fuzz`)

Method: 600 random single-command cases (seed 2): normal/scaled/distorted sprites, polygons, polylines and lines;
all colour modes, gouraud, mesh, shadow/half-luminance/half-transparent, MSB-on, SPD/ECD, HSS, user/system clipping,
flip, local coordinates, 16 and 8 bpp frame buffers. Result: **581/600 pixel-identical**; with ECD forced on,
**596/600**; every remaining difference is a Ymir divergence (D1, D2), none is a MAME defect so far. Limits: single commands, no rotation/HDTV/double-interlace frame buffer modes, no command chaining
(jump/call), no timing.

| ID | Finding | Verdict |
|---|---|---|
| VDP1-D1 | 15 of the 19 differences disappear with ECD=1: with ECD=0 and two end codes in a texture row, Ymir drops the texels *before* the end code; MAME, Mednafen (`ec_count = 2`) and the MiSTer RTL (`EC_FIND`, `VDP1.sv:1270-1331`) draw them | Ymir differs; **MAME is consistent with Mednafen and hardware RTL**, no action |
| VDP1-D2 | 4 cases differ only at frame-buffer/system-clip boundaries (right edge x=319, bottom-left) for quads and distorted sprites with vertices far outside the clip: MAME draws boundary pixels Ymir does not. In case 560 the drawn pixels lie on row lines that start outside the clip (left edge of the quad at x=322) and run *toward* it. The MiSTer RTL ends a line only when its position is outside the system clip **and moving away** (`VDP1.sv:1313-1318`; `LINE_DIRX=1` adds -1), and Mednafen stops a line only after it has been inside and left (`drawn_ac`, `vdp1_common.h:448-476`); a line that starts outside and moves in keeps drawing, so its pixels at x<=319 are written. MAME's per-pixel clipping produces exactly those pixels | Ymir differs; **MAME is consistent with the RTL and Mednafen**, no action. In-line termination in the RTL cannot change visible pixels (it only fires when every remaining pixel is clipped) |
| VDP1-D3 | Zero-width/zero-height scaled sprite: Ymir draws a one-row/one-column line, MAME draws a single dot (seen in an earlier generator run that produced degenerate zoom-point sizes) | undecided; not arbitrated against RTL |

Phase 2 items: extend the generator to
command chains and the remaining frame-buffer modes; keep `FZ_ECD` runs to isolate Ymir's end-code divergence.

## H2. VDP2 verification (register-mutation differential against Ymir; tooling in `regtests/saturn/vdp2_fuzz`)

Method: four captured states (BIOS logo, BIOS menu, After Burner II, Daytona USA attract) x 400 random register
mutations each (sprite layer hidden). Baselines are pixel-identical for all four. Racing-game captures with mid-frame
register changes (OutRun) were excluded. Result: 3, 14, 4 and 17 of 401 mutated states differ (BIOS logo, BIOS menu,
AB2, Daytona); interlace toggles (TVMD LSMD) differ in size only (Ymir 448 lines vs MAME 224) and are not counted.
Every remaining difference was isolated to a single register:

| ID | Register (word idx) | Observation | Verdict so far |
|---|---|---|---|
| VDP2-D1 | CYCA0L/CYCA1U/CYCB0L/CYCB1L/CYCB1U (8, 11, 12, 14, 15) | VRAM cycle patterns that leave a layer with fewer character-pattern reads than ST-058 Table 3.3 requires (e.g. a 256-colour NBG with one read): Ymir hides the layer, MAME keeps drawing it. MAME's `vdp2_check_vram_cycle_pattern_registers` is documented in the code as a presence gate ("not fetch-address matching or a slot arbiter"): any PN and any CP command in any bank enables the layer; Table 3.3 counts (1/2/4/8 by colour depth and reduction), Table 3.4 timing limits and the pattern-name access limits are not enforced | ST-058 p.33: "the access number must be the same as ... determined by the conditions" and p.32: the correct screen "will not be displayed" otherwise; the hardware failure picture is not documented. Open: Phase 2 needs a rule for the illegal case (MiSTer RTL is the arbiter) |
| VDP2-D2 | BKTAU/BKTAL (86/87) | Per-line back screen colour table (BKCLMD=1): Ymir reads the same entry for every line (its per-line branch increments the line-screen address instead of the back-screen address, `vdp_renderer_sw.cpp:2606-2612`); MAME reads `BKTA*2 + 2*y` | **Ymir defect**; MAME correct |
| VDP2-D3 | PNCN2, MPABN2 (26, 36) | With NBG2 pattern-name mode/map address changed Ymir draws a garbage tile layer that MAME does not draw. Needs arbitration: check whether MAME still honours these for NBG2 or hides the layer through the D1 gate | undecided |
| VDP2-D4 | CHCTLA, CHCTLB (20, 21) | Character size/colour-depth changes: MAME and Ymir differ (probably D1 again for changed colour depth, and character number supplement handling) | undecided |
| VDP2-D5 | WCTLB (105) | Window control for NBG2/NBG3 with random window enable/logic bits: a few thousand pixels differ in three captures | undecided; window logic to be read against ST-058 window chapter |
| VDP2-D6 | ZMCTL (76) | Zoom control (NBG0/NBG1 reduction) with NBG0/1 disabled changes the display in MAME versus Ymir by the same 5759 pixels in every capture (likely the D1 gate again: reduction changes the required access count) | undecided |
| VDP2-D7 | SCRCTL (77) | Line/vertical-cell scroll enables: 25k pixels differ | undecided |

Limits: VRAM 4-Mbit layout only (both emulators wrap the upper half), single static states, one-to-three-register
mutations, no mid-frame changes. Phase 2: arbitrate D3-D7 by reading MiSTer `VDP2*.sv` and ST-058 chapters, then add
targeted (non-random) generators for windows, line scroll and colour calculation.

## I. Phase 1 coverage status (updated 2026-09-26)

Audited: A (SCU DMA/timers), E (SH7604), F (SCSP), G (SCU DSP), H (VDP1, differential), H2 (VDP2 register mutations),
K (SMPC), L (CD block dispatch), M (memory map), N (ST-V I/O), O (dual-CPU sync), P (runtime sweep).
Not yet audited: VDP2 rotation/colour-calculation/window logic against MiSTer RTL (only register-mutation differential
done), VDP1 command chains and rotation frame-buffer modes, CD-block sector filtering/selector semantics beyond the
dispatch table, SMPC peripheral timing, SCSP 1Fs interrupt granularity measurement.

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

## P. Runtime sweep and Phase 2 master plan (2026-09-26)

Sweep: 1163 Saturn softlist discs (region-matched console, per-run NVRAM copy with clock/language valid) and 107 ST-V sets,
26-30 s each, headless. Result: 1151/1163 Saturn discs load and run game code; all 107 ST-V sets run without host crash.
Harness: `satbatch/` (outside the repo). Fixed during the sweep (committed): CD Init soft reset now resets host information
(ST-38 / Mednafen `SWReset`) - `6caee70`; SH-2 illegal slot instruction exception in interpreter and DRC and the general
illegal exception for undefined DRC opcodes (SH7604 4.5.3/4.5.4) - `73816db`, `296a657`; CD periodic report gating restored
to the CR4-read rule - `8899421`; CR1 bit 7 = data track (Mednafen `MakeReport`) - `0d40097`.

Open runtime findings (each to be closed or explicitly recorded):

| ID | Finding | Evidence / lead |
|---|---|---|
| RT-01 | `steamgea`, `nobutens`, `rayman` request the BIOS CD player on this tree, run on upstream | after an INTBACK peripheral BREAK the status register reads 00h here and 60h upstream; the game then probes the direct-mode port. `-ctrl1 joy_md3` avoids it |
| RT-02 | 12 Print Club sets stall in the 1,000,000-iteration timeout of a poll of I/O status byte 0040001Bh; upstream reaches the "call attendant" screen | status byte reads 0 in both trees; see N |
| RT-03 | Pulirula master/slave command-queue race (slave finishes a handler after the master rewound the queue) | missing bus wait states (DUAL-01) |
| RT-04 | `machi`, `gaxeduel` fail on upstream as well | likely disc-specific |
| RT-05 | `dukenk3d` asmjit InvalidInstruction once in the sweep, not reproducible | intermittent |

Phase 2 order (one subsystem at a time; each item gets a commit with its documented source):

1. CD block: CD-01 (0x65/0x66 swap), CD-02 (Open Tray), CD-03 (FAD search 0x55/0x56).
2. SMPC: RT-01 (BREAK / status register / INTBACK termination against ST-169 text), SMPC-01 (SYSRES scope), SMPC-02.
3. ST-V I/O: IO-02 (route legacy per-game maps through the 315-5649 device), RT-02.
4. SH-2: address errors (E), NMIL edge select, then DUAL-01/RT-03 only with a documented bus-cycle model.
5. VDP2: VDP2-D1 access-pattern rule, D3-D7 arbitration against ST-058 and RTL; stale TODO reconciliation (B.1).
6. VDP1: VDP1-D3, command chains.
7. SCSP: SCSP-04 (1Fs interrupt granularity).
8. Validation: rerun the disc and ST-V sweeps; promote only what the sweep and the audit support.

## J. Process note

Implementation is Phase 2 and proceeds item by item from this document. One SCSP LFO change was implemented during
Phase 1 (`81812edad51`); it is listed here so the Phase 2 order can account for it.

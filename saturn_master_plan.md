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
| VDP2-D1 | CYCA0L/CYCA1U/CYCB0L/CYCB1L/CYCB1U (8, 11, 12, 14, 15) | VRAM cycle patterns that leave a layer with fewer character-pattern reads than ST-058 Table 3.3 requires (e.g. a 256-colour NBG with one read): Ymir hides the layer, MAME keeps drawing it. MAME's `vdp2_check_vram_cycle_pattern_registers` is documented in the code as a presence gate ("not fetch-address matching or a slot arbiter"): any PN and any CP command in any bank enables the layer; Table 3.3 counts (1/2/4/8 by colour depth and reduction), Table 3.4 timing limits and the pattern-name access limits are not enforced | ST-058 p.33: "the access number must be the same as ... determined by the conditions" and p.32: the correct screen "will not be displayed" otherwise; the hardware failure picture is not documented. The MiSTer RTL (`VDP2.sv:657-732`) implements a per-slot fetch pipeline: every T slot whose command matches issues that fetch, so an illegal count is not "layer off" but whatever partial/stale data the pipeline holds. Neither MAME (presence gate) nor Ymir (layer hidden) models that, so this is an **accuracy limit shared with Ymir, not a MAME defect**; a faithful fix needs the slot pipeline, decide in Phase 2 whether to port it |
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

Phase 3 attempt (2026-09-27): routing critcrsh/stvmp/hopper through `sega_315_5649_device` was scoped and deferred rather than
done blind. The legacy `ioga_r/w` index registers as `offset & 0xf` with `offset*2+1` selecting the byte lane (a
pre-device decode), while the device's `read(offs_t offset)`/`write` already take the 0-0xF register index directly
from the `umask32` mapping used for every other ST-V board (`stv.cpp:1207-1211`). The three legacy maps would need
their own case statements (lightgun latch, mahjong mux, hopper motor) rewritten against the device's register numbers
and reconnected to its callbacks, not just a call-site swap, and none of the three games has a regtest that exercises
its input hardware (lightgun coordinates, mahjong panel, hopper motor) to check the result. Left as documented,
verified-by-code-reading-only debt (IO-02) rather than an unverified behavioural change.

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

## Q. Phase 2 master implementation plan (derived only from `saturn_phase1_report.md`; no code is changed in Phase 2)

Derivation. Every item below cites the finding IDs of the Phase 1 report (`saturn_phase1_report.md`, sections 1-12), which were
produced by comparing the code with the official documents. Earlier audit sections of this file (A-P) are history and are not the
source of any item. Items come from class A (the code contradicts a stated rule) and from the class-B items whose comments or
behaviour need a decision. Class C items (timing and arbitration) are listed as BLOCKED until a measurement source exists; class D
(no document) is listed as runtime work only.

Working rules for Phase 3: one item at a time in the order at the end, each implemented completely (no stubs, no game-specific
hacks), each citing its official source first (Mednafen/Ymir/MiSTer only where the document is silent or garbled, and then named in the
code comment), verified by the stated check, and committed alone with a technical message. "DECISION" items need the stated evidence to
be gathered and the decision recorded in the commit before any code changes. "DOC" items first re-read the original PDF page because
the text extraction of the table was garbled (Phase 1 marks each one).

### Q1. SMPC (`smpc.cpp`, port glue in `sat_console.cpp`/`saturn.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-SMPC-01 | SMPC-P1-01; SMPC manual Table 1.1, p.29 | SYSRES resets everything the manual lists: slave SH-2 held in reset with the SSHON shadow updated, sound CPU/SCSP reset with the SNDOFF shadow, dot clock back to 320, then the boot ROM starts; write the exact scope from Table 1.1 as the acceptance list first | regtest: issue SYSRES from a running system and read back each item; sweeps unchanged |
| PL-SMPC-02 | SMPC-P1-02; p.17 | status-only INTBACK completes about 300 us after the command instead of 16 us | timing regtest (command write to SMPC interrupt), then the three titles of RT-01 are re-run |
| PL-SMPC-03 | SMPC-P1-03; pp.55-57, Fig 3.5 | implement the IREG1 OPE optimisation (first frame measures the collection time, later frames start so it ends 1 ms after) | regtest with OPE set and clear across several frames |
| PL-SMPC-04 | SMPC-P1-04; pp.38, 60 | DECISION: the manual defines no behaviour for IREG2 other than F0h, so keep it accepted; remove the stale TODO and record the reason | none |
| PL-SMPC-05 | RT-01 (runtime symptom), SMPC-P1-01..03 | after PL-SMPC-01..03, rerun steamgea, nobutens and rayman without `joy_md3`; if they still leave the game, trace the INTBACK BREAK/CONTINUE status byte by byte against Table 3.2 and Figs 3.3, 3.4, 3.7 and file the result as a new item | the three titles reach game code |

### Q2. Memory map (`sat_console.cpp` `saturn_mem`, VDP1 register window)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-MM-01 | MM-P1-01, V1-P1-06 | VDP1 registers span 24 bytes: map and size `m_vdp1_regs` to 05D00000-05D00017 | read/write regtest at the edges |
| PL-MM-02 | MM-P1-02 | map the whole 1 MB CS2 region (05800000-058FFFFF) and define the behaviour of 058A0000-058FFFFF from the memory map note | regtest reads |
| PL-MM-03 | MM-P1-03, SH-P1-06 | cache address array 60000000-7FFFFFFF read/write (implemented together with PL-SH-03) | with PL-SH-03 |
| PL-MM-04 | MM-P1-04 | A-Bus dummy area accepts writes (boot ROM mode words at 057FFFFC) in the console map | boot to the game intro, sweeps unchanged |
| PL-MM-05 | MM-P1-05 | MINIT/SINIT are 4-byte registers; check what the document permits before narrowing the 8 MB decode | regtest; dual-CPU sweep titles unchanged |
| PL-MM-06 | MM-P1-06, MM-P1-07 | DECISION: mirrors and undocumented mappings have no document; keep and record | none |

### Q3. SH-2 core and SH7604 modules (`sh.cpp`, `sh2.cpp`, `sh7604*.cpp`, `saturn_dcc.cpp`, `sat_console.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-SH-01 | SH-P1-03; SH7604 4.3.1 Table 4.6, 4.3.2 | raise address errors (vector 9) for every access and fetch case of Table 4.6 in both the interpreter and the DRC, with the stacked PC/SR of Table 4.11, not accepted in delay slots | parity regtest: the same faulting sequences in both cores give identical frames and handler entry |
| PL-SH-02 | SH-P1-01, SH-P1-06 | give each SH-2 its own C0000000 data array in two-way mode and the address array | regtest: master and slave write the same address and read different data |
| PL-SH-03 | SH-P1-02, SH-P1-05 | DECISION first: choose a cache model that gives stale reads for cached alias accesses and purge semantics without a large slowdown (way/LRU tags, associative purge at 40000000h with the ST-202 versus SH7604 disagreement recorded); then implement CCR enable, two-way, replacement disable and purge | stale-line and purge regtest; both sweeps must not regress |
| PL-SH-04 | SHM-P1-12; SH7604 chapter 6 | implement UBC: BAMRA, BBRA, BARB/BAMRB/BBRB, BDRB/BDMRB, BRCR and the user break exception after the matching bus cycle | register test and a break exception frame check |
| PL-SH-05 | SHM-P1-02; 10.3.3 | replace the +2^31 special case by the six-cycle overflow path | division corner-case regtest against the Table 10.2 results |
| PL-SH-06 | SHM-P1-01; 10.1, 10.4.1 | DECISION: model the 39/6 cycle busy stall and the one-cycle read extension only if the DRC can expose the cycle time; otherwise record as a limit | cycle-count test in the interpreter and DRC |
| PL-SH-07 | SH-P1-04, SHM-P1-10 | BLOCKED for the SCU/A-Bus/B-Bus parts (no per-bus table); the SDRAM/BSC part (BCR1/BCR2/WCR/MCR, CAS latency, refresh) can be designed from chapter 7. Acceptance: the Pulirula master/slave queue race no longer reproduces | Pulirula runtime |
| PL-SH-08 | SH-P1-04, documentation | DECISION on dual-CPU timing (ST-202): replace the constant interleave quantum with the documented FRT input-capture latency for MINIT/SINIT | timing test from MINIT write to slave ICF |
| PL-SH-09 | SHM-P1-11, SHM-P1-08 | trace and complete the refresh compare-match interrupt and DMAOR NMIF paths | register-level regtest |
| PL-SH-10 | all | DRC/interpreter parity suite for exceptions and the new features (illegal, slot illegal, TRAPA, address error, NMI, IRQ in a delay slot, UBC break) | single script compares registers and stack in both cores |
| PL-SH-11 | Yabause wiki SH-2CPU page (Charles MacDonald hardware notes) | DECISION/mostly BLOCKED: on-chip register area (0xE0000000-0xFFFFFFFF, top 3 address bits 111) mirrors far beyond the canonical 0xFFFFFE00-0xFFFFFFFF window `sh7604_map` implements. Precise decode (address bits numbered from bit0=LSB): bits 27-16, 15 and 13 are don't-care (mirror) bits; register offset is bits 8-0 (0-511); offsets 256-511 always decode to the real register regardless of any other bit; offsets 0-255 decode to the real register only when bit28=1 AND bit12=1, otherwise every read in that mirrored range returns a fixed pattern ($00000001000200030004000500060007, i.e. each 16-bit half-word reads its own index 0-7 mod 8); separately, if bit14=0 anywhere in this space the real chip locks up (undocumented in ST-097/ADE-602-085C; sourced only from Charles MacDonald's hardware-probing notes as republished on the wiki, not from the manual). Confirmed reachable in MAME's decode: `sh2_device::read/write_byte/word/long` only apply the `m_am` address mask for `offset < 0x40000000`; the on-chip area is well above that, so the full unmasked offset reaches `m_program`, meaning today's un-mapped mirror addresses simply fall through to default-unmapped (reads as 0) instead of the documented garbage pattern. Implementing the garbage-pattern mirror correctly needs new `.mirror()`-based address_map entries layered so they do not override any of the ~40 existing per-register `map()` lines in `sh7604_map` for the canonical addresses - a wide-blast-radius change to code every SH-2 access in every game depends on, for a corner case with no known game dependency and no official-manual citation. The lockup half cannot be modeled at all without new hang/halt machinery. Recorded as a DECISION rather than implemented this pass: the garbage-mirror portion could be attempted later behind its own regtest that first proves the mirror install order does not disturb a single canonical register access; the lockup portion stays BLOCKED indefinitely | none yet; needs a full canonical-register regression pass before any mirror() change ships |

### Q4. SCU and DSP (`saturn_scu.cpp`, `scudsp.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-SCU-01 | SCU-P1-01 | **Already done before this plan was written** (commit `fd61d181e47a`, 2026-09-13): the mask resets to 0xBFFF at vector fetch (Mednafen/Ymir behaviour) and the comment already separates that from the manual-sourced power-on value it cites ST-097 fig 3.21 for. No action needed; the Phase 1 finding predates this fix | none |
| PL-SCU-02 | SCU-P1-02 | **Already done before this plan was written** (commit `fd61d181e47a`, 2026-09-13, same as PL-SCU-01): IST is cleared when the interrupt is issued (`m_ist &= ~(1 << internal)` / the external equivalent in `test_pending_irqs`), matching Table 3.8's write-0-resets/write-1-maintains rule and the SBL DSP library's own usage. `test_scu_irqs.py` (1920 arbitration cases) verified passing 2026-09-27 (its sanitizer flags fail to link on this machine's MinGW, libasan/libubsan are not installed here; re-ran without them to confirm the logic) | none |
| PL-SCU-03 | SCU-P1-16, SCU-P1-17 | DSP DMA address-add: derive the mapping of the 3-bit field (0,1,2,4,8,16,32,64) per ST-097 pp.134-140 and reconcile the immediate and RAM count forms; arbiter Ymir/Mednafen for the bus-specific cases | DSP DMA regtest for each add value and bus |
| PL-SCU-04 | SCU-P1-07/08/09 | DECISION: prohibited operations are documented as hangs; keep accepting them and record instead of inventing behaviour | none |
| PL-SCU-05 | SCU-P1-11/15/18/20 | BLOCKED: A-Bus/B-Bus/DSP DMA timing needs a measurement source | none |

### Q5. VDP1 (`saturn.cpp` VDP1 section)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-V1-01 | V1-P1-01 (retracted) | **Retracted 2026-09-27.** ST-013 p.48 Figure 4.2 was misread: (b) X1>=X3, Y1>Y3 -> *No* erase-write, the opposite of the original finding. The existing `left >= right` / empty-Y-range early-out in `vdp1_advance_vblank_erase` and `vdp1_begin_display_erase` already matches this. A draft implementation of the wrong finding was sitting uncommitted in the tree from an earlier session; it has been discarded (not committed) rather than landed | none: verified correct by direct re-reading of the PDF text |
| PL-V1-02 | V1-P1-02 | write BEF from CEF at the start of drawing as well as at frame change | EDSR readback regtest across PTM=01 |
| PL-V1-03 | V1-P1-03 | decode PTMR through bits 1-0 | regtest writing 0x0101 |
| PL-V1-04 | V1-P1-13, V1-P1-09/10 | END with a non-zero command select, prohibited command codes and unmatched return: DECISION per Ymir/Mednafen evidence, then make list termination consistent with CEF/interrupt behaviour | command-list regtests for each case |
| PL-V1-05 | V1-P1-08, V1-P1-20, V1-P1-14..18 | DECISION: keep the reference-emulator behaviours (commands 3 and 7, 13-bit coordinates, mode 5 transparency, polygon flags, MON in 8 bpp) but label each in the source as reference-derived rather than manual-derived | none |
| PL-V1-06 | V1-P1-26/27/28 | the line/polygon algorithm and timing stay as accuracy limits; pre-clip direction inversion check against the differential fuzz | existing vdp1_fuzz |

### Q6. VDP2 (`saturn.cpp` VDP2 section, `saturn_vdp2.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-V2-01 | V2-P1-11 | **Done (2026-09-27), Tables 3.2/3.3 only.** Pattern-name and character/bitmap-pattern access counts required per reduction/colour-depth, per ST-058 pp.33-34 (source: SSDDV25 official documentation set); T-slot limits and the CPU slot (Table 3.4) are untouched, still open | `test_vdp2_cycle_pattern_counts.py` |
| PL-V2-02 | V2-P1-14 | **Done (2026-09-27, comment only, commit follows).** Decoding CRMD=3 like mode 2 is a documented decision (no reference describes prohibited-mode-3 hardware behaviour); the source now cites this explicitly instead of looking like an oversight. CRKTE's own contract (reading the rotation coefficient table from the upper half of CRAM) was checked in `vdp2_read_rotation_coefficient` and already does not depend on CRMD, so the "requires mode 1" constraint is a software rule with nothing to enforce on the emulator side | code reading only |
| PL-V2-03 | V2-P1-39, V2-P1-40 | DOC: read Table 8.1 from the PDF, then ignore window coordinate bits above the documented widths and fix the exclusive-mode X mapping if the table requires it | window regtest per graphics mode |
| PL-V2-04 | V2-P1-37, V2-P1-46 | **Verified correct, no defect (2026-09-27).** Every palette-indexed pen path (`vdp2_dot_pixel`, the sprite/line-colour readers) goes through `m_palette`, which `vdp2_cram_w`/`refresh_palette_data` already write with the MSB-mirrored duplicate for both mode 0 (`^0x400`) and mode 2/3 (`^0x400`), so masking with `0x7ff` on the read side returns the same colour regardless of that bit. The one place that reads physical CRAM storage directly instead of through `m_palette` (`vdp2_palette_color_msb`) already masks to the correct 10-bit range for CRMD<2's mode-0 case and for CRMD>=2. No mismatch found | code reading of both the write and read paths |
| PL-V2-05 | V2-P1-16, V2-P1-25, V2-P1-10 | remove the stale TODO/"guessed" comments; add a test showing special high-resolution A/B renders as the manual's join | image test |
| PL-V2-06 | V2-P1-02, V2-P1-03, V2-P1-26, V2-P1-36, V2-P1-41 | DOC: re-read Tables 2.3, 2.4, the SCRCTL line scroll interval table and the interlace line-table rules from the PDF; resolve each against Mednafen; adjust only where a document rule is proven | per-table regtests |
| PL-V2-07 | V2-P1-01 | DECISION: ODD flag toggling in non-interlace contradicts the manual; keep with the game evidence stated, unless the reference emulators show a different rule | none |
| PL-V2-08 | V2-P1-12 and timing items | BLOCKED: CPU/VDP2 VRAM arbitration and access timing | none |

### Q7. SCSP (`scsp.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-SC-01 | SC-P1-01 | raise the 1 Fs interrupt every sample rather than once per stream batch | 68K interrupt count equals the sample count over a fixed time |
| PL-SC-02 | SC-P1-05 | widen RBP to the documented seven bits | DSP ring-buffer regtest |
| PL-SC-03 | SC-P1-04, SC-P1-08 | DECISION: EG numbers and the DSP come from the reference emulators; document each source in the code; audio capture comparison against Ymir/Mednafen renders | capture/compare script |
| PL-SC-04 | SC-P1-02/03/06 | BLOCKED: memory arbitration, MCRDYN wait states, DMA slowdown | none |
| PL-SC-05 | SC-P1-10 | trace MEM4MB, DAC18B and MONO effects | register regtest |

### Q8. CD block (`saturn_cd_hle.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-CD-01 | CD-P1-02 | dispatch 65h to Copy Sector Data and 66h to Move Sector Data | regtest: 65h keeps the source, 66h removes it |
| PL-CD-02 | CD-P1-01 | implement Open Tray (05h): status response, DCHG, drive state OPEN, disc retained so closing restores PAUSE | regtest: command then close |
| PL-CD-03 | CD-P1-03, CD-P1-04 | read standby time, ECC and retry parameters of Init, and model the PAUSE to STANDBY transition after the standby time (default 180 s) | regtest with a short standby time |
| PL-CD-04 | CD-P1-05, CD-P1-06 | Init closes an open tray; apply the init flag bit 7 (change request) rule after the ST-38 text is confirmed from the PDF | regtest |
| PL-CD-05 | CD-P1-07 | implement reset-selector bit 3 (partition output connectors) after confirming the bit polarity from the PDF | selector regtest |
| PL-CD-06 | CD-P1-08 | trace initialisation of file and TOC information at tray open and soft reset against 5.5 | regtest |
| PL-CD-07 | CD-P1-09 | report the CD flag bits (mode/form, mute/emphasis) | CR1 comparison script |
| PL-CD-08 | CD-P1-11, CD-P1-12 | FAD search, MPEG and read-error states have no ST-38 text: BLOCKED, keep as runtime work. **Re-checked 2026-09-27, still BLOCKED** (see progress log): the Yabause wiki gives the CR1-CR4 I/O contract for 0x55/0x56 but not the search semantics, and no reference emulator implements the algorithm | none |

### Q9. Peripherals (`bus/sat_ctrl`, `smpc.cpp`)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-PER-01 | PER-P1-01 | DECISION: mouse movement encoding, absolute value with sign bits (manual) versus two's complement (code); check Mednafen and Ymir before touching | mouse-data regtest |
| PL-PER-02 | PER-P1-04 | BLOCKED: per-device INTBACK collection time | none |

### Q10. ST-V I/O and boards (no official document)
| ID | Source | Change | Verification |
|---|---|---|---|
| PL-STV-01 | section 11.2 | runtime work only: the Print Club poll of 0040001Bh and the blank-frame titles, found by tracing the games; documentation of what each poll waits for | the sets reach the same screens as upstream or are documented |

### Q11. Validation and promotion
1. Rebuild; run `regtests/saturn/run_all.py` and every regtest added above with zero skips.
2. Re-run the Saturn disc sweep (1163 discs) and the ST-V sweep (107 sets) with the `satbatch/` harness; compare with the previous results and with upstream.
3. Audio comparison (PL-SC-03) and visual spot checks of a fixed title set.
4. Promote (remove `MACHINE_NOT_WORKING`, set IMPERFECT flags for known limits) only what steps 1-3 support; BLOCKED items stay documented as limits.

Order for Phase 3: PL-CD-01, PL-CD-02; PL-SMPC-01, PL-SMPC-02, PL-SMPC-03, PL-SMPC-05; PL-MM-01, PL-MM-02, PL-MM-04, PL-MM-05; PL-V1-01,
PL-V1-02, PL-V1-03; PL-SH-01, PL-SH-05, PL-SH-10; PL-SC-01, PL-SC-02; PL-V2-02, PL-V2-04, PL-V2-05; PL-CD-03 to PL-CD-07;
PL-V2-01, PL-V2-03, PL-V2-06; PL-SH-02, PL-SH-03, PL-SH-04, PL-MM-03; PL-SCU-03; then the DECISION items as their evidence is gathered; then Q11.

## J. Process note

Phases: 1 = analysis (sections A-P), 2 = this master plan (section Q, no code changes), 3 = execution, one item at a time with a commit per item. One SCSP LFO change (81812edad51) and the disc-sweep fixes listed in P were made before the plan was written; Q accounts for them.

## R. Phase 3 progress log
- PL-CD-01 (65h Copy / 66h Move) and PL-CD-02 (Open Tray 05h): done, `test_cd_copy_move_tray.py` passes.
- PL-SMPC-01 (SYSRES scope): done, `test_smpc_sysres.py` passes.
- PL-SMPC-02 (INTBACK status 300 us) and PL-SMPC-03 (OPE optimization): done, `test_smpc_intback_time.py` and `test_smpc_ope.py` pass.
- PL-SMPC-05: after PL-SMPC-01..03, steamgea, nobutens and rayman (previously falling to the CD player without `joy_md3`) boot to game code with the default controller (satbatch probe: shell=false, game header loaded); Dracula X unchanged. The RT-01 symptom is closed by the documented INTBACK status timing.
- PL-SC-01 (1 Fs interrupt per sample): done (`ccbd00a1bca`), `test_scsp_1fs.lua`: 482 requests/s before, 44274 after.
- PL-SC-02 (RBP seven bits): done (`a8b1368a061`), `test_scsp_rbp.lua`.
- PL-SH-05 (DIVU overflow boundary): done (`4ae640ff108`); reference is the MiSTer divider (`DIVU.sv`), not only the text: exact quotients of +-2^31 complete only for a negative dividend, everything else outside -(2^31-1)..2^31-1 takes the six-cycle path; `test_sh7604_divu_rtl.py` 0 of 40938 cases differ (106 before).
- PL-SH-01 (address errors) and PL-SH-10 (DRC/interpreter parity suite): CLAIMED by the session that committed PL-SC-01/02 and PL-SH-05 (touches sh.cpp/sh2.cpp/sh2fe.cpp only); the VDP1/VDP2 items in saturn.cpp are left to the other session.
- PL-SH-01 done (`2be0d3508bf`): CPU address errors (vector 9) in both cores per Table 4.6/4.10, `test_sh2_address_error.lua` 15 sequences pass with -drc and -nodrc. The on-chip module space for fetch/PC-relative/TAS/byte/longword rules is FFFFFE00-FFFFFFFF (Table 7.3); the rest of area 111 is reserved and unchecked.
- PL-SH-10 partly done (`dde81efb189`): parity script `test_sh2_exception_parity.lua` (TRAPA, illegal, illegal slot, address error in a delay slot) exposed and fixed two defects: undefined code in a delay slot took vector 4 in both cores (manual: vector 6, branch target stacked) and the two cores stacked different PCs. Still open under PL-SH-10: NMI/IRQ in a delay slot, UBC break (with PL-SH-04).
- PL-CD-03/04/05/06 done (`941ca574433`, `5324b29b8d7`): Init standby time -> STANDBY, tray closing on Init, init flag bit 7 ("no change"), Reset Selector bit 3 (partition output connectors -> MPEG connection). `test_cd_init_params.py` (283 checks) and the extended `test_cd_copy_move_tray.py` (46 checks) pass. CD-P1-08/09/10 remain open (file/TOC init tracing, CD flag byte mode/form bits, status-code mapping is host-library-only and not in ST-38).
- PL-SCU-03 partly done (`4843908e333`): the DSP DMA immediate-form (SImm) address-add table had fields 2 and 4 swapped for the byte values of fields 1 and 3 (4 and 16 instead of 8 and 32), against ST-097 pp.148-149's explicit 8-value list; fixed and verified with `test_scudsp_dma_addr_add.py`. The RAM-source-count form's own address-add rules (pp.150-151, HOLD variants pp.152-155) read as contradictory in this OCR pass (single-bit vs. full 3-bit field depending on direction) and were left untouched rather than guessed at; still open. Also flagged (not fixed here): `test_scudsp_dma.py`'s shared harness has a pre-existing, unrelated compile/assertion break against the current `scudsp_cpu_device` (missing execution-state mock members from an earlier commit); spun off as a separate task.
- PL-V2-01 partly done (`021ea7ffbb1`, 2026-09-27), Tables 3.2/3.3 only: `vdp2_check_vram_cycle_pattern_registers` previously only checked that each access command was present *somewhere* in a layer's cycle pattern registers (a "presence gate"), not that the manual's required count of accesses was actually provisioned. ST-058 pp.33-34 Tables 3.2 (pattern name: 1/2/4 accesses by reduction) and 3.3 (character/bitmap pattern: also keyed on colour depth; 256-color has no quarter-reduction entry; 2048/32768/16.77M-color are reduction-independent) are now enforced via a new `vdp2_required_cycle_pattern_counts` table, sourced from the newly available clean SSDDV25 official documentation (`C:\Users\jkind\cassini - fusion\docs\SSDDV25`). NBG2/NBG3 pass no-reduction (ST-058 Table 1.4: no scale capability). Verified against `test_vdp2_cycle_pattern_counts.py` including two mutant negative controls (old-presence-gate, wrong-256-half). Table 3.4 (T-slot limits, CPU slot) remains open under this ID.
- PL-CD-08 (FAD search 0x55/0x56) re-checked 2026-09-27 and found still BLOCKED, correcting an earlier (uncommitted) assumption in this session that Mednafen had a working reference implementation to corroborate the Yabause wiki's register format. Live sources checked: (1) the Yabause wiki `CDCommands` page (not the incomplete `CDBlock` page) does give the CR1-CR4 I/O contract - 0x55 in: CR2=Sector Position, CR3=Buffer Number(hi)/FAD bits 23-16(lo), CR4=FAD bits 15-0; 0x56 out: CR2=Sector Position, CR3=Buffer Number(hi)/FAD bits 23-16(lo), CR4=FAD bits 15-0 - but this is register plumbing, not the search algorithm. (2) Yabause's own `cs2.c` `Cs2ExecFadSearch`/`Cs2GetFadSearchResults` are literal `// finish me` stubs that only set HIRQ flags. (3) Ymir's `cdblock.cpp` `CmdExecuteFADSearch`/`CmdGetFADSearchResults` exist but are dead code (commented out of the dispatch switch) and are themselves unimplemented TODOs, with the exact open question ("how does sectorPos factor in here?") that blocks a faithful implementation - i.e. the interaction between the input "Sector Position" and the searched-for FAD is not established by any source checked. (4) A grep.app search for Mednafen's FAD-search command names returned no hits; no Mednafen implementation was found to exist. No implementation was written for this reason - a guessed search semantics (exact match vs. nearest vs. floor-by-FAD) would be exactly the kind of hallucinated hardware behaviour this plan avoids.
- VDP2 CRAM mode 2/3 address bit-shuffle (`vdp2_cram_r`/`vdp2_cram_w`, related to PL-V2-04) verified bit-for-bit correct 2026-09-27 against Ymir's `kVDP2CRAMAddressMapping` table (`vdp2_defs.hpp`): for CRMD>=2, Ymir maps a byte address as `(bit1<<11) | (bits[2:11]<<1) | bit0`. Translated to MAME's word-index `offset` (0-1023) and its `shift=(offset&1)?0:16`/`m_vdp2_cram[offset>>1]`/`m_vdp2_cram[(offset>>1)|0x200]` scheme, a script cross-checking all 1024 colours x 2 halves (2048 cases) found zero mismatches between the two formulas' physical word+halfword targets. No defect; this was a qualitative-only check before, now confirmed exactly.

# Saturn / ST-V Phase 1 report: code compared with the official documentation

Method. For each subsystem the official document (SMPC User's Manual, SCU User's Manual and precautions, SH7604 and SH-1/SH-2
manuals, VDP1/VDP2 manuals, SCSP manual, ST-38/ST-162 for the CD block, memory map notes) is read and its contract is
compared with the current source. Earlier audit notes in this repository (`saturn_master_plan.md`, `saturn_completion_report.md`)
are NOT used as evidence. Every finding cites the document page or section and the code location. Runtime observations from
the disc/ST-V sweep are recorded separately and only as symptoms. No code is changed in Phase 1.

Status per subsystem: SMPC (ง1), memory map (ง2), SH-2 dual-CPU/exceptions/cache (ง3), SCSP (ง4, partial), VDP1 (ง5), VDP2 (ง6) and SCU with its DSP (ง7) are done below, chapters listed per section; remaining SH7604 modules (INTC, UBC, BSC, DMAC, DIVU, FRT/WDT/SCI), the CD block, ST-V I/O, peripherals and the unfinished SCSP parts (EG, pitch, FM, MIDI, DMA, DSP) are pending.

## 1. SMPC (`src/mame/sega/smpc.cpp`, `smpc.h`, client glue `saturn.cpp`/`sat_console.cpp`)

Documents: SMPC User's Manual (`docs/smpc/smpc_users_manual.pdf`) sections 1-3.

### 1.1 Confirmed consistent with the manual

| Item | Manual | Code |
|---|---|---|
| Register map, byte access only, IREG0-6 write-only, OREG0-31 read-only | Fig 1.3, p.5-6 | `smpc_map` 0x01..0x77, even bytes ignored |
| SF is set-only by the SH-2 (write sets, SMPC clears); bits other than bit 0 undefined | p.6 | `status_flag_w` sets unconditionally, `sf_ack` clears |
| OREG31 receives the command code when execution begins | p.21, command tables | `m_oreg[31] = m_comreg` |
| PDR read-back of output pins returns the written value; DDR 7 bits, 0 = input; IOSEL 0 = SMPC control mode; EXLE bit | p.7-9, Tables 1.3-1.5 | `pdr1_r/pdr1_w`, `ddr1_w`, `iosel_w`, `exle_w` |
| Command codes 00,02,03,06,07,08,09,0D,0E,0F,10,16,17,18,19,1A and their fixed execution times (30 us, 40 us CD, 100 ms clock/system reset, 70 us SETTIME, 40 us SETSMEM) | Tables 2.1-2.3, p.12 | `m_cmd_table_timing` |
| NMIREQ is unconditional; RESENAB/RESDISA gate the reset-button NMI, default disabled, 3 V-INT debounce, RESB shows the button state at V-BLANK-IN | pp.32-34 | `master_sh2_nmi`, `m_NMI_reset`, `vblank_in` 3-count |
| INTBACK status: OREG0 bit7 STE, bit6 RESD (1 = reset disabled, default), OREG1-7 BCD time with weekday in the high nibble of OREG3 and hexadecimal month, OREG8 cartridge code, OREG9 area code, OREG10/11 system status, OREG12-15 SMEM | pp.39-41 | `resolve_intback` |
| SETTIME/SETSMEM store the IREG bytes; SMEM cleared at cold reset | pp.44-46 | `handle_command` 0x16/0x17 |
| RTC counts seconds with BCD rollover through 2099 including leap years | p.46 | `handle_rtc_increment` |
| SR in control mode: bit7 always 1, bit6 PDL (first peripheral data), bit5 NPE (data remains), bit4 RESB, bits3-0 port modes; status-only SR reads 0x40/0x60 pattern | Fig 3.13 p.66, Fig in 2.4 | `sr_set(0x80 \| PDL \| NPE \| pmode)` |
| Peripheral collection begins at V-BLANK-OUT and must finish by V-BLANK-IN, otherwise the command ends (time over) | pp.17, 50, 56 | `vblank_in`, `vblank_out`, `INTBACK_WAIT_*` |
| BREAK ends the command; CONTINUE is a change of IREG0 bit7; both prohibited together | Table 3.2 p.50, Fig 3.7 | `ireg_w` offset 1 |
| SYSRES: all memory except the 256 Kbit backup RAM is not retained | p.29 | `saturn_state::system_reset_w` clears work RAM-H/L, sound RAM, VDP1/VDP2 VRAM and CRAM |
| CKCHG320/352: slave SH-2 OFF, sound CPU reset, work RAM and CD block retained, VRAM not retained, master leaves via NMI after the clock switch | pp.30-31, Fig 2.1 | `handle_command` 0x0e/0x0f |

### 1.2 Discrepancies found (code differs from the document, or the document requires behaviour that is absent)

| ID | Finding | Document | Code | Effect |
|---|---|---|---|---|
| SMPC-P1-01 | SYSRES does not restore the power-on state of every unit. Table 1.1 (power-on state): slave SH-2 OFF, sound CPU reset, dot clock 320. SYSRES "resets (initializes) all functions" and "starts up the boot ROM" | p.3 Table 1.1, p.29 | SMPC pulses `m_sysres` and only the master reset line. `system_reset_w` resets SCU/VDP/RAM but does not put the slave SH-2 in reset, does not reset the SCSP/68000, does not return DOTSEL to 320 and leaves the SMPC `m_prev_sshoff/sndoff/cur_dotsel` shadows unchanged | after SYSRES a running slave and sound CPU keep executing and OREG10 reports stale signal state |
| SMPC-P1-02 | INTBACK status acquisition time. "SMPC status acquisition ends approximately 300 us after INTBACK command issue and an SMPC interrupt is requested" | p.17 | status-only INTBACK completes after `timing = 8 + 8` = 16 us | status arrives about 18 times faster than the documented time; software with a fixed wait window sees different ordering |
| SMPC-P1-03 | Peripheral acquisition time optimisation (IREG1 OPE bit, Fig 3.5): first frame measures collection time, later frames start collection so that it ends 1 ms after the measured time | pp.55-57 | `OPE` ignored (TODO in source, `timing += 700` fixed) | collection always starts at V-BLANK-OUT; timing-sensitive titles cannot observe the optimised start |
| SMPC-P1-04 | INTBACK parameter validation: IREG2 "must be F0h" | pp.38, 60 | IREG2 is not checked (`TODO: check against ireg2` in `command_register_w`) | the manual defines no behaviour for other values, so no incorrect result; recorded as an unimplemented check |
| SMPC-P1-05 | INTBACK command time is "320 msec max" in the command table but completion uses the 16/716 us path; the table value is dead data | Table 2.2 | `m_cmd_table_timing[0x10]` unused | none observable |
| SMPC-P1-06 | Commands 0x0A/0x0B (NETLINK) and 0x1E/0x1F are not in the manual | - | log/popmessage only | outside the document |

### 1.3 Not verifiable from the manual (recorded, not judged)

* Peripheral data formats for the peripherals themselves (Tables 3.10-3.39) live in `src/devices/bus/sat_ctrl`; they are exercised by the disc sweep but have not yet been compared line by line.
* Behaviour of the status register between a BREAK and the next INTBACK is not specified by the manual (Table 3.2 states only that collection stops and the command terminates).

## 2. Memory map (`sat_console.cpp` `saturn_mem`, `stv.cpp` `stv_mem`)

Documents: `docs/system/saturn_memory_map.md` (a compilation of ST-097 Figs 1.3/1.5/1.6, ST-210, ST-013, ST-058, ST-077,
ST-162, ST-202 and SH7604 Table 7.3), read together with the SH7604 address-space table. The SH-2 device is created with
address mask C7FFFFFFh, so the 20000000h cache-through alias is produced by the CPU mask and needs no map mirror.

### 2.1 Confirmed present with the documented extent

BIOS 00000000-0007FFFF; SMPC 00100000-0010007F; backup RAM 00180000-0018FFFF; work RAM-L 00200000-002FFFFF; MINIT/SINIT
at 01000000/01800000 (both cache-through aliases, 16-bit-only trigger); A-Bus dummy 05000000-057FFFFF; sound RAM 512 KB at
05A00000; SCSP registers at 05B00000; VDP1 VRAM 05C00000-05C7FFFF; VDP1 frame buffer 256 KB at 05C80000; VDP2 VRAM, colour
RAM and registers; SCU registers 05FE0000-05FE00CF; work RAM-H 06000000-060FFFFF; cache data array C0000000, 4 KB;
associative purge space 40000000-47FFFFFF (writes ignored).

### 2.2 Discrepancies and gaps

| ID | Finding | Document | Code |
|---|---|---|---|
| MM-P1-01 | VDP1 register window is 24 bytes (05D00000-05D00017) | memory map, ST-013 register list | mapped as 05D00000-05D0001F (32 bytes) so 05D00018-05D0001F reach the register handlers |
| MM-P1-02 | A-Bus CS2 is a 1 MB region (05800000-058FFFFF) containing the CD block | memory map, ST-162 | only 05800000-0589FFFF is mapped; 058A0000-058FFFFF is unmapped |
| MM-P1-03 | Cache address array 60000000-7FFFFFFF is read/write (A31-A29 = 011) | SH7604 Table 8.2 / memory map | only 60000000-600003FF is mapped and write-only (no read-back); consistent with the cache not being modelled (see the SH-2 section) |
| MM-P1-04 | A-Bus dummy area accepts writes (the boot ROM writes mode words to 057FFFFC) | memory map | console map has a read handler only for 05000000-057FFFFF; writes there are unmapped accesses (ST-V map ignores them) |
| MM-P1-05 | MINIT/SINIT regions are 4 bytes | memory map | decoded as 8 MB windows starting at 01000000/01800000; decoding beyond 4 bytes is not specified by the document |
| MM-P1-06 | Undocumented mappings exist: 00400000 (reads FFFFh, "unknown device"), 05FC0000-05FDFFFF (reads 000E0000h constant), 04FFFFFF (cartridge ID byte) | none of the documents lists them | present in code; 04FFFFFF is documented by the cartridge notes, the other two have no document |
| MM-P1-07 | Mirror extents of work RAM-L (mirrored at 00300000), work RAM-H, SCSP register window, VDP2 register window | memory map gives the primary extents only | code mirrors them; the documents do not state mirror behaviour, so this cannot be judged from documentation |

## 3. SH-2 master/slave: dual-CPU operation, exceptions, cache (`sh.cpp`, `sh2.cpp`, `sh7604.cpp`, `saturn_dcc.cpp`, `sat_console.cpp`)

Documents: Dual CPU User's Guide ST-202-R1 (all of it), SH7604 Hardware Manual chapters 4 (exceptions, address errors 4.3,
illegal slot 4.5) and 8 (cache, Table 8.2, 8.4.7-8.4.9), SH-1/SH-2 Programming Manual (Delay_Slot, exception notes).
Not yet compared in this pass: SH7604 INTC, UBC, BSC register behaviour, DMAC, DIVU, FRT/WDT/SCI details, SBY, instruction
timing tables.

### 3.1 Confirmed consistent

| Item | Document | Code |
|---|---|---|
| A 16-bit write to 21000000h raises FRT input capture on the slave; a 16-bit write to 21800000h raises it on the master; data ignored | ST-202 1.2, 5.1, 6.1 | `saturn_dcc_device::minit_w/sinit_w` (16-bit masks only), cache-through aliases mapped |
| The clock change command puts the slave in reset; it must be restarted with SSHON | ST-202 3.0 | SMPC CKCHG path asserts `m_sshres` |
| Slave is held in reset until SSHON; both CPUs execute the same shared address space | ST-202 1.1, 4.3 | slave `INPUT_LINE_RESET` driven by `slave_sh2_reset_w`, one `saturn_mem` for both CPUs |
| Illegal slot instruction (BF, BT, BRA, BSR, JMP, JSR, RTS, RTE, TRAPA, BF/S, BT/S, BRAF, BSRF in a delay slot) and general illegal instruction exceptions with the stacked values of Table 4.11 | SH7604 4.5.3/4.5.4, SH-1/SH-2 PM | implemented in interpreter and DRC (commits 73816db, 296a657) |

### 3.2 Discrepancies and gaps

| ID | Finding | Document | Code |
|---|---|---|---|
| SH-P1-01 | Each SH-2 has its own on-chip cache data array. In two-way mode (CCR.TW=1) ways 0 and 1 are 2 KB of RAM addressed at C0000000h; "programs placed in internal RAM are not shared" between the CPUs | SH7604 8.2 (CCR bit 3), Table 8.2, ST-202 4.1 | `saturn_mem` maps C0000000-C0000FFF as ordinary RAM in the one address map used by both CPUs, so master and slave see the same 4 KB and overwrite each other |
| SH-P1-02 | The cache has no bus snoop; a CPU reading data written by the other CPU or by DMA sees stale data unless it reads through 20000000h or purges (40000000h) | ST-202 7.0-7.2, SH7604 8.4.7 | CCR is stored only (`ccr_w`); there is no cache array, purge or replacement, so every access is coherent |
| SH-P1-03 | Address errors (vector 9) are raised for: odd-address instruction fetch; instruction fetch from on-chip peripheral space; odd-address word access; longword access not on a longword boundary; PC-relative access to purge/address-array/on-chip space; TAS.B to purge, address array, data array or on-chip space; byte access to FFFFFF00-FFFFFFFF; longword access to FFFFFE00-FFFFFEFF | SH7604 4.3.1 Table 4.6, 4.3.2 | the CPU cores never raise it (only the DMAC sets DMAOR.AE, `dmac_address_error`); misaligned accesses complete |
| SH-P1-04 | When the two CPUs compete for an external access one waits, so execution slows; cycle cost of an access depends on the bus state controller settings | ST-202 1.1, SH7604 chapter 7 | instruction cost is a fixed table value (`icount` per instruction); no per-access wait states and no arbitration between the CPUs. Relative CPU timing is therefore approximate; a documented example of software sensitive to it is the master/slave queue protocol seen in Pulirula |
| SH-P1-05 | The two documents disagree on the associative-purge access: ST-202 7.2 says a 16-bit write of 0; SH7604 8.4.7 says access should be a longword | ST-202, SH7604 | writes to 40000000-47FFFFFF are ignored (`nopw`), so neither is emulated; consequence follows from SH-P1-02 |
| SH-P1-06 | Address array (60000000-7FFFFFFF) and data array (C0000000-C0000FFF) are read/write spaces | SH7604 Table 8.2 | address array: write-only 1 KB window; data array: RAM (see SH-P1-01) |

## 4. SCSP (`src/devices/sound/scsp.cpp`, `scspdsp.cpp`)

Document: SCSP User's Manual ST-077-R2 (`docs/scsp/scsp_users_manual.pdf`). Compared in this pass: chapter 3 (interface and
memory arbitration), the slot-register descriptions for LFO, TL/SDIR, mixer and pan, the timer registers, the interrupt
registers and Tables 4.18, 4.21, 4.24-4.30 and 4.33-4.38. Not yet compared: EG rate behaviour and KRS, pitch tables
4.19/4.20, FM modulation Tables 4.15-4.17, MIDI, DMA (Tables 4.39/4.40), DSP chapter 5 and Table 4.41, slot status
registers, memory-size register.

### 4.1 Confirmed consistent (checked value by value)

| Item | Document | Code |
|---|---|---|
| LFO frequency for each of the 32 LFOF values (0.17 Hz ... 172.3 Hz) | Table 4.21 | `LFOStepInterval[32]`: 44100/(256 x interval) reproduces all 32 printed values within their rounding (script check, no mismatch) |
| Amplitude-LFO depth 0/0.4/0.8/1.5/3/6/12/24 dB and pitch-LFO depth 0/7/13.5/27/55/112/230/494 cent | Table 4.24 | `ASCALE[]`, `PSCALE[]` |
| Send levels for IMXL/DISDL/EFSDL: -inf, -36, -30, -24, -18, -12, -6, 0 dB | Tables 4.26, 4.27, 4.29 | `SDLT[8]` |
| Fixed pan: DIPAN/EFPAN 00h and 10h centre, bits weigh 3/6/12/24 dB on the left (00h-0Fh) or right (10h-1Fh) side, 0Fh left silent, 1Fh right silent | Tables 4.28, 4.30 | pan table generation (`iPAN` bits, `(iPAN & 0xf) == 0xf`) |
| Timers A/B/C count once every 1, 2, 4, ... 128 samples, request the interrupt when the 8-bit counter reaches FFh, interrupt time = (255 - TIM) x cycle | Tables 4.33-4.37 | `timer_sync/timer_arm`: tick = 512 clocks << prescale, deadline at (FFh - counter) ticks |
| Interrupt pending bits: 0-2 external INT0N-2N, 3 MIDI in, 4 DMA end, 5 CPU manual (only writable bit), 6-8 timers A/B/C, 9 MIDI out, 10 1Fs sample; pending flags are set regardless of the enable register and reset by SCIRE/MCIRE | Fig 4.63, Table 4.38 | `m_udata.data[0x20/2]` bit assignments, `ResetInterrupts`, timer bits `0x40 << idx` |
| Main CPU accesses the SCSP in 16-bit units | 3.1 | 16-bit register handlers |

### 4.2 Discrepancies and gaps

| ID | Finding | Document | Code |
|---|---|---|---|
| SC-P1-01 | The 1 Fs (one sample) interrupt is a per-sample source | Fig 4.63 ("1 Sample (1Fs) Interrupt"), 3.2 (128 memory cycles per 22.68 us sample) | raised once per sound-stream update batch (`if (stream.samples() > 0)` sets bit 10 once), a comment in the source states the hardware rate is per sample. The rate seen by the 68000 is therefore the batch rate, not 44.1 kHz |
| SC-P1-02 | Sound memory access priorities and wait states (PCM/DSP, refresh, DMA, main CPU, sound CPU; two idle cycles per sample; CPU speed drops with SCSP DMA use) | 3.2, Figure 3.2 | no arbitration model; CPU accesses to sound RAM are not delayed by slot/DSP/DMA activity |
| SC-P1-03 | Main CPU accesses insert wait states via MCRDYN until internal processing finishes | 3.1 (2) | no wait states on SCSP register or sound-RAM access from the SH-2 |

## 5. VDP1 registers and frame control (ST-013 chapter 4 against `saturn.cpp`)

Compared: TVMR, FBCR, PTMR, EWDR/EWLR/EWRR, ENDR, EDSR, LOPR, COPR, MODR, the frame change modes of Table 4.3, and the
V-blank erase budget of Tables 4.4/4.5. The command tables and the drawing rules (chapters 5 and 6) are in ยง5b.

Matches the manual:
- MODR (`vdp1_regs_r` 0x16): VER=1 in bits 15-12, PTM1 bit 8, EOS/DIE/DIL/FCM bits 7-4, VBE bit 3, TVM bits 2-0 (section 4.9).
- EDSR/LOPR/COPR writes are ignored (read-only, 4.6-4.8). COPR is stored as command address/8 (`position << 2` for 0x20-byte tables).
- LOPR is latched from COPR on a frame-buffer change; CEF is cleared on the change, BEF takes the previous CEF (4.6/4.7).
- ENDR terminates after about 30 clocks via `terminate_timer` (4.5); PTM=01 restarts from the top of the table, PTM is reset
  to 00 by reset (4.3); `PTM=10` starts drawing after a frame change (`vdp1_video_update`).
- FBCR FCM/FCT decoding follows Table 4.3: (0,x) one-cycle, (1,0) erase only, (1,1) change only, (0,1) prohibited and ignored.
- Erase X unit is 8 or 16 dots by TVM bit 0, Y is doubled by DIE (4.4). EWDR/EWLR/EWRR are latched at the bank change.
- The END command fetch sets CEF and raises the SCU draw-end interrupt (4.6).

Differences found:
| ID | Finding | Manual | Code |
|---|---|---|---|
| V1-P1-01 | Degenerate erase area not erased | 4.4: if X1>=X3 or Y1>Y3, erase still covers 1 dot (8 dots in rotation/HDTV) as if X3=X1+1, Y3=Y1 | `vdp1_clear_framebuffer` and `vdp1_advance_vblank_erase` end at once when `left >= right` or `y > bottom`, so nothing is erased |
| V1-P1-02 | BEF is not written when drawing starts | 4.6: BEF takes CEF "when the frame buffer is changed or at the start of drawing" | `vdp1_process_list` clears CEF only; BEF changes only in `vdp1_change_framebuffers` |
| V1-P1-03 | PTMR compared as a whole register | 4.3: only bits 1-0 are PTM | `vdp1_regs_w` tests `VDP1_PTMR == 1`, so a write of 0x0101 does not start drawing, while MODR and PTM=2 decode use the masked value |
| V1-P1-04 | Write-only registers readable | 4.1-4.5 and 4.9: TVMR, FBCR, PTMR, EWDR, EWLR, EWRR, ENDR are write-only, values not readable; FBCR read returns 0 in code, but the others return the stored word and log a warning | `vdp1_regs_r` default path returns `m_vdp1_regs[offset]` (marked TODO in code). The manual does not define the value, so this is an accuracy limit, not a defect |
| V1-P1-05 | TVMR/FBCR changes accepted at any time | 4.1/4.2: TVM changes only from the second H-blank IN after V-blank IN to the H-blank IN after V-blank OUT; VBE/FCM/FCT only immediately after V-blank IN/OUT | the code accepts writes at any moment; software that follows the manual is unaffected. No enforcement needed, recorded so behaviour outside the window is not assumed correct |
| V1-P1-06 | VDP1 register window size | 4.1: registers span 100000h-100017h (24 bytes) | `m_vdp1_regs` holds 0x20 bytes; offsets 0x18-0x1f store and return data (see memory map MM-P1-01) |
| V1-P1-07 | V-blank erase budget (no defect) | Tables 4.4/4.5: (pixels per raster - 200) x (rasters per field - display rasters) | `vdp1_vblank_erase_capacity` uses 1708/1820/852/848 and 263/313/525/562; recomputed 1508x39=58812 (NTSC 320x224), 652x45=29340 (31KC 480 lines) and 648x82=53136 (HDTV 480 lines), all equal to the table |

Missing from the driver as compared with the manual: none of the registers above is absent. The pseudo draw continuation
procedure (4.8) needs COPR to hold the address of the interrupted table; the code retains COPR on forced termination,
which matches.

### 5b. VDP1 command list and CMDPMOD (ST-013 sections 6.1-6.3, 7.1-7.3 against `vdp1_draw_end`)

Compared so far: command decoding (Table 6.1), the jump modes, the clipping/local-coordinate commands, and the CMDPMOD bits
HSS, Pclp, Clip/Cmod, Mesh. Colour modes, colour calculation (Gouraud, shadow, half-luminance, half-transparent), the
character-size/direction fields, and the exact line/polygon rasterisation rules (6.4-6.7 and chapter 7 figures) are NOT yet
compared and remain open for this report.

Matches the manual:
- Table 6.1: END bit in CMDCTRL bit 15 ends the list (CEF set, draw-end interrupt raised); commands 0-2 textured, 4-6 polygon/
  polyline/line, 8/9/A clipping and local coordinates. Command tables are 0x20 bytes, CMDLINK is address/8 (`>> 2` to the table index).
- Jump modes: next, assign, call (return address = next table), return, and the four skip forms that process no draw but still
  follow the link; skip-call/skip-return follow the same nesting rule (section 6.1 Jump Mode table).
- Clip=1, Cmod=0 draws inside the user rectangle; Clip=1, Cmod=1 draws outside, still bounded by the system rectangle (6.3).
- Mesh draws only pixels where X LSB XOR Y LSB = 0 (`(x ^ y) & 1` rejects the rest).
- HSS samples even/odd source columns by FBCR.EOS only when reducing, and ignores the end code (Figure 6.5).
- Pclp=0 pre-clips, Pclp=1 skips it (`0x0800` tests in the sprite and line paths).

Differences and limits:
| ID | Finding | Manual | Code |
|---|---|---|---|
| V1-P1-08 | Aliased command codes | Table 6.1 defines only Comm 0,1,2,4,5,6,8,9,A; all others are "setting prohibited" | Comm 3 is drawn as a distorted sprite and 7 as a polyline (comments cite Hardcore 4x4, Baroque, Samurai Shodown 4). Not in the manual; taken from software behaviour. Keep only if the reference emulators agree |
| V1-P1-09 | Prohibited command aborts the list | Undefined by the manual | codes 0x0b-0x0f abort the list without CEF or a draw-end interrupt (the code comment states the exact progression is unimplemented). Titles listed in the comments (Asenna, Rayman, Choro Q, Albody) reach these codes, so the reference behaviour needs to be established |
| V1-P1-10 | Return with no call | Undefined | jump/skip return with no subroutine ends the list without CEF |
| V1-P1-11 | Nested call | 6.1: one level of nesting, "do not use jump calls in subroutines" | a nested call is ignored and execution falls to the next table; undefined in the manual |
| V1-P1-12 | System clip lower-left fixed at 0,0 | 7.1: system clipping command takes only the lower-right (XC,YC) | matches (`set(0,XC,0,YC)`); coordinates masked to 13 bits, unsigned |
| V1-P1-13 | CMDCTRL and END decode | Table 6.1: END=1 only with Comm 0 | code tests bit 15 alone, so END with a nonzero Comm ends the list; the manual calls that combination prohibited |

### 5c. VDP1 colour modes, end/transparent codes and colour calculation (ST-013 6.3, Table 6.2, 6.4)

Compared `drawpixel_generic`, the fast-path selector `vdp1_set_drawpixel`, `vdp1_latch_color_lookup`, `vdp1_color_calculate` and `vdp1_draw_color`.

Matches the manual:
- Colour bank modes: mode 0 adds the 4-bit code to CMDCOLR bits 15-4, mode 2 uses 6 bits over `CMDCOLR & 0xffc0`, mode 3 uses 7 bits over `0xff80`, mode 4 uses 8 bits over `0xff00`; only the low 8 bits reach an 8 bpp buffer (`vdp1_write_pixel`).
- End codes F (4-bit modes), FF (8-bit modes), 7FFF (mode 5); transparent codes 0, 00, 0000. Mode 2/3 end and transparent tests use the unmasked byte, as the manual's FFH/00H definitions require.
- Lookup-table mode reads the 16-entry table at CMDCOLR*8 (32-byte aligned) and writes entries unchanged; the table is latched once per command.
- Mode 5 forces a 16-byte aligned character address (cross-checked by Mednafen and Ymir per the code comment; the manual does not state it).
- Colour calculation: replace, shadow (only when the frame-buffer MSB is 1, halves the buffer, keeps the MSB), half-luminance (source halved, no buffer read), half-transparency (replace when buffer MSB is 0, else average with buffer MSB kept), Gouraud alone, Gouraud + half-luminance (6), Gouraud + half-transparency (7). 8 bpp always replaces (p.94).
- MON sets the frame-buffer MSB and writes no colour, after the mesh test (so a mesh pattern applies to the MSB write, per "MSB is set to ON in the mesh condition").

Differences and limits:
| ID | Finding | Manual | Code |
|---|---|---|---|
| V1-P1-14 | Mode 5 transparency broader than the table | Table 6.2: 0000H is the transparent code; 0001H-7FFEH are "setting prohibited" in RGB mode | `transpen = (raw & 0x8000) ? 0 : raw` treats every MSB-clear word as transparent (code comment cites MiSTer GetPattern and Ymir). Consistent with the reference implementations, wider than the manual; it only matters for prohibited data |
| V1-P1-15 | Colour-calc mode 5 (Gouraud bit clear, bits 2:0 = 101) | Prohibited | `vdp1_color_calculate(mode & 3)` treats it as shadow after Gouraud is applied to the source; no manual behaviour to compare |
| V1-P1-16 | Colour modes 6/7 and reserved values | Prohibited | source data is read from VRAM word 0 (Mednafen behaviour, per comment), not from the character pattern. Not in the manual; a `TODO: check transpen` remains in the code |
| V1-P1-17 | Polygon/line ECD and SPD | 6.3: ECD and SPD must both be 1 for polygons, polylines and lines | with ECD=0 a polygon colour of FFFFH is dropped as an end code and with SPD=0 a colour of 0 is dropped as transparent; matches what an unmodified hardware pipeline would do only if the reference emulators agree. Manual-conforming software is unaffected |
| V1-P1-18 | 8 bpp MON write | 6.3: not described for 8 bpp | code sets bit 15 of the shared word (the even pixel's top bit), following Ymir; the code comment says silicon behaviour is unverified |
| V1-P1-19 | Drawing speed | 6.3: shadow and half-transparent draw pixels 6 times slower | draw slicing uses `vdp1_raster_slice_cycles`; per-mode pixel cost not re-derived here (timing capture noted as unavailable) |

Still to compare for VDP1: Gouraud table interpolation (6.7), character size and read direction (6.5-6.6, CMDCTRL Dir), the zoom-point placement rules, polygon/line/polyline rasterisation and pre-clip inversion, and chapter 7 clip/local-coordinate semantics.

### 5d. VDP1 command fields, coordinates and Gouraud (ST-013 5.1-5.3, 6.4-6.8)

Matches the manual: CMDSIZE X field is bits 13-8 (times 8) and Y is bits 7-0 (`>> 8 & 0x3f`, `& 0xff`); the lookup table base is
CMDCOLR*8 on a 32-byte boundary; CMDGRDA, CMDSRCA and CMDLINK are address/8. Gouraud correction per component is a 5-bit
value with 16 meaning "no change" (`original + correction - 16`, clamped to 0-31, MSB preserved), interpolated along edges and
then along the span. The Gouraud table is bound to vertices A, B, C, D independently of the texture read direction.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V1-P1-20 | Vertex coordinate width | 6.7: 11-bit signed, range -1024 to 1023, upper 5 bits are extension bits equal to bit 10 | `vdp1_coord` treats coordinates as 13-bit signed (bit 12 is the sign) and ignores bits 15-13; the code comment cites Mednafen and a Virtua Fighter 2 intro in Ymir. For values inside -1024..1023 both agree; outside that range the code follows the reference emulators, not ST-013. Local coordinates and user/system clip values are masked to 13 bits |
| V1-P1-21 | CMDSIZE zero | 6.6: zero X or Y size is prohibited | code accepts and special-cases zero sizes (see the `CMDSIZE.H = 0` comment near `vdp1_draw_distorted_sprite`); behaviour taken from reference emulators, not the manual |
| V1-P1-22 | Character/table address zero | 5.1-5.3: character patterns, lookup tables and Gouraud tables cannot start at 00000H (Gouraud: 00000H-0001FH) | no check; the manual states it as a constraint on software, not as hardware behaviour |
| V1-P1-23 | Line Gouraud | 5.3: for lines only vertices A and B are used (start and end) | verified only for the sprite/polygon path (`vdp1_setup_rectangle_shading`); the line path is read in ยง5e |

### 5e. VDP1 clipping, local coordinates, zoom point and lines (ST-013 6.1 Zoom Point, chapter 7)

Matches the manual:
- System clip: upper-left fixed at (0,0), lower-right (XC,YC) inclusive (`system_cliprect.set(0,XC,0,YC)`); points on the clip line are drawn.
- User clip: (XA,YA)-(XC,YC) inclusive; inside mode draws it, outside mode excludes the boundary line as well (`vdp1_pixel_visible` inverts an inclusive test); the system clip always applies too (7.2).
- Local coordinates are added to draw-command vertices (`x2s`/`y2s`) and not to the clip rectangles (7.3).
- Zoom point ZP: bits 9-8 select left/centre/right (01/10/11), bits 11-10 select top/centre/bottom; the anchor is CMDXA/CMDYA and the extent is CMDXB/CMDYB (`vdp1_draw_scaled_sprite`). ZP=0 uses the A and C vertices; A=C draws one dot.
- Horizontal/vertical inversion from Dir (CMDCTRL bits 5-4) is independent of extent inversion.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V1-P1-24 | Zoom-point centre rounding | 6.1: an odd extent leaves the centre point off-centre, computed from A and the display width | `left -= width >> 1` (arithmetic shift, floor for negatives); the manual gives no rounding rule for negative widths, and states a negative display width is not guaranteed |
| V1-P1-25 | Prohibited zoom-point codes | 6.1: only 0,5,6,7,9,A,B,D,E,F are defined | the decode uses `zoompoint & 3` and `>> 2 & 3` independently, so a code such as 4, 8 or C (one field zero) is decoded as left/top anchoring; undefined in the manual |
| V1-P1-26 | Rasterisation rules | chapter 7 defines the command tables and figures only; the line/polygon/edge-coverage algorithm is not specified | `vdp1_draw_segment` implements a signed 13-bit error datapath with an extra edge-coverage dot, with comments citing MiSTer/Ymir. It cannot be verified against ST-013; the differential fuzz against the reference emulators is the only check available |
| V1-P1-27 | Pre-clip rejection | 6.3 Pclp: pre-clipping skips wholly outside lines and inverts the horizontal drawing direction | the rejection test exists in `vdp1_draw_segment` (one-dot margin). Whether the horizontal direction inversion is modelled was not checked in this pass; it only affects the order of partial writes over a shared destination |
| V1-P1-28 | Timing | chapter 7 gives no per-command timing; Table 4.4/4.5 and the "6 times slower" notes are the only figures | per-pixel cost of colour calculation and command fetch are approximations (`vdp1_raster_slice_cycles`, 16-cycle fetch from Ymir); acknowledged as incomplete in the code comments |

Summary of the VDP1 review (ยง5-5e): the register file, frame-change modes, command list and colour paths agree with ST-013
except for the items V1-P1-01 to -03 (erase of degenerate areas, BEF at draw start, PTMR bit mask), which are defects, and
V1-P1-08 to -11, -13, -14, -20 and -21, where the code follows the reference emulators for cases the manual calls
prohibited or defines differently. The remaining items are accuracy limits.

## 6. VDP2 (ST-058 against `saturn_vdp2.cpp` and the VDP2 half of `saturn.cpp`)

VDP2 is the largest document. It is compared chapter by chapter; each subsection below says exactly which registers and
rules were read, and what was left for the next one. Numbers are V2-P1-nn.

### 6.1 TV screen mode, external signals, status and counters (ST-058 chapter 2, 3.1 VRSIZE)

Compared: TVMD (180000h), EXTEN (180002h), TVSTAT (180004h), VRSIZE (180006h), HCNT (180008h), VCNT (18000Ah), resolution and
blanking geometry in `reconfigure_crtc`.

Matches the manual:
- Reset value 0 for TVMD, EXTEN and VRAMSZ; VRSIZE version field reads 0 ("the first is 0"); HCNT/VCNT/TVSTAT are read-only.
- TVMD decode: DISP bit 15, BDCLMD bit 8, LSMD bits 7-6, VRESO bits 5-4, HRESO bits 2-0; widths 320/352/640/704 by HRESO bits 1-0; VRESO 224/240/256 lines, VRESO=3 not allowed; exclusive monitor modes (HRESO bit 2) force 480 lines regardless of VRESO; double-density interlace doubles the vertical size.
- EXTEN: EXLTEN=0 latches the H/V counters when EXTEN is read; EXLTEN=1 latches from the external signal (`external_latch`, light gun); EXLTFG is set by a latch and cleared by reading TVSTAT.
- TVSTAT bit layout: EXLTFG bit 9, EXSYFG bit 8, VBLANK bit 3, HBLANK bit 2, ODD bit 1, PAL bit 0. Exclusive modes force ODD to 1.
- HCNT: normal modes return the H counter shifted left by one (HCT0 invalid); the exclusive-normal mode masks 9 bits.
- VCNT double density: VCT9..1 hold the field line count and VCT0 is 0 for an odd field and 1 for an even field.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-01 | ODD flag in non-interlace | 2.5: "the non-interlace mode is always 1" | `m_odd_bit` toggles every frame (`sync_timer_cb`) in every mode and TVSTAT returns it; comments cite STV seabass, grdforce, finlarch, sasissu and magzun as requiring the toggling. The manual is contradicted by the code on the strength of game behaviour; not arbitrated against MiSTer/Ymir/Mednafen in this pass |
| V2-P1-02 | VCNT non-interlace layout | Table 2.4 shows the counter in VCT9..1 with VCT0 invalid for non-interlace | code returns the unshifted table value (comment: "docs says << 1, but according to HW tests it's a typo"). Mednafen `GetNLVCounter` also shifts only in double-density interlace, so the reference agrees with the code and disagrees with the manual text |
| V2-P1-03 | HCNT in hi-res and exclusive hi-res | Table 2.3: bit positions differ per mode | hi-res returns `hpos & 0x3ff` unshifted and exclusive hi-res returns `(hpos >> 1) & 0x1ff`; Mednafen returns `HCounter << 1` in every mode. Table 2.3's text extraction is garbled, so the required layout was not derived from ST-058 alone; the modes differ between code and Mednafen and need arbitration |
| V2-P1-04 | TVSTAT VBLANK with DISP=0 | not in ST-058 | code forces VBLANK=1 when DISP=0, citing Technical Bulletin 12. Documented outside ST-058; accepted |
| V2-P1-05 | LSMD=1 (setting not allowed) and single-density interlace | 2.4: LSMD=01 prohibited, LSMD=10 single-density interlace | only LSMD=3 changes timing (`m_lsmd == 3`); single-density interlace (2) is treated as non-interlace, with no per-field parity/pixel difference, and 01 is treated as non-interlace |
| V2-P1-06 | TVMD/EXTEN readback | 2.4/2.5: unused bits are "~" | both registers store and return all 16 bits written, including unused bits; hardware behaviour of the unused bits is not specified |
| V2-P1-07 | EXSYEN/EXSYFG, EXBGEN, DASEL | 2.5: external sync and external screen input | stored only; EXSYFG never set, EXBGEN/DASEL have no effect on rendering (no external screen input on Saturn hardware exists in the driver). Accepted limit |
| V2-P1-08 | Resolution change rules | 2.4: change DISP 0 to 1 during VBLANK; exclusive to normal mode needs a VDP2 reset; special high-resolution needs other registers set | none enforced (`reconfigure_crtc` accepts any transition). Software-side rules; no hardware behaviour is defined |
| V2-P1-09 | Blanking geometry | ST-058 chapter 2 gives no total line/dot counts or clocks (Table 2.1 lists only active resolutions and the PAL/31 kHz/Hi-Vision restrictions) | H total 427/455, V total 263/313 (525/561 exclusive) and the pixel clock come from other sources (Charles MacDonald measurements, Ymir, MiSTer per the code comments); not verifiable against ST-058 |
| V2-P1-10 | Special high-resolution graphics A/B | 2.1: NBG0 and NBG1 are joined into one 640/704-wide screen; software must follow the listed settings (identical tables, NBG1 X scroll = NBG0 + 1, increments of 2, colour RAM mode 0) | no dedicated code path exists (no reference to the mode in `saturn.cpp`); the result depends on the generic hi-res NBG0/NBG1 renderer reproducing the manual's join. Whether it does was not tested here; flagged for the runtime validation step |

Not compared in 6.1 and continued in 6.2: the VRAM cycle pattern registers and the access-timing rules (3.2-3.3), RAMCTL and the
colour RAM modes (3.4), then the scroll-screen chapters.

### 6.2 RAMCTL, colour RAM modes and VRAM cycle patterns (ST-058 sections 3.2-3.4)

Compared: RAMCTL (18000Eh), the eight cycle-pattern registers CYCA0L..CYCB1U (180010h-18001Eh), the access-command table (3.5),
colour RAM modes 0/1/2 and their write behaviour, `vdp2_cram_r/w`, `vdp2_prepare_vram_access`, `vdp2_normal_vram_access`,
`vdp2_rotation_vram_access`, `vdp2_check_vram_cycle_pattern_registers`.

Matches the manual:
- RAMCTL field decode: CRKTE bit 15, CRMD bits 13-12, VRBMD/VRAMD bits 9-8, RDBS fields bits 7-0.
- Unpartitioned VRAM-A/B uses only the A0/B0 cycle registers (bank 1 registers ignored); hi-res and exclusive modes use T0-T3 and ignore T4-T7 (`slots = 4 : 8`).
- Access commands 0-3 name reads, 4-7 character reads, Ch/Dh NBG0/NBG1 vertical cell scroll reads, others no access; the vertical cell scroll early-fetch rule (NBG0 before NBG1 in the same bank, p.35) is modelled.
- RBG1 owns bank B1 for names and B0 for characters; when RBG1 is on, the cycle registers of B0/B1 are ignored (ST-058 p.32).
- Colour RAM mode 0 writes reach both 1K-word halves (the code merges each half separately); mode 2 uses two 1K-word banks with 32-bit entries; RGB555 expands by appending three zero bits (p.43: 31 becomes 248).

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-11 | Cycle patterns are a presence gate | 3.3: the number and timing of pattern-name and character-pattern reads is fixed by colour count, reduction and the selection limits of Tables 3.2-3.4 (e.g. NBG at 1/2 reduction needs 2 name reads); a layer with too few or misplaced slots is not displayed correctly | `vdp2_check_vram_cycle_pattern_registers` only checks that a name command and a character command appear somewhere; the code comment states it is "not fetch-address matching or a slot arbiter". Tables 3.2-3.4 counts and T-slot limits are not enforced (this is the earlier VDP2-D1 class) |
| V2-P1-12 | CPU access wait | 3.3: the CPU waits for its selected CPU read/write slot during display; write wait is omitted after two words | no CPU/VDP2 VRAM arbitration is modelled (also listed under the memory-map timing limits) |
| V2-P1-13 | Cycle-pattern registers write-only | 3.3: CYC registers are write-only | `vdp2_regs_r` returns the stored value for the whole 0x200-byte window, including the write-only registers (the hardware readback is not specified) |
| V2-P1-14 | RAMCTL=mode 3 and CRKTE constraint | 3.4: CRMD=3 not allowed; CRKTE=1 requires mode 1 and turns the upper colour RAM half into the coefficient table | code treats `VDP2_CRMD & 2` as mode 2/3 alike (`case 2: case 3:`), so the prohibited mode 3 is decoded as 24-bit; whether the coefficient-table read uses the correct colour RAM half is checked in the rotation section |
| V2-P1-15 | Mode change with stale halves | 3.4: "saving colour data must be done after these bits have been set" | halves can differ after a mode change until rewritten; the code comment states this and does not copy data. Consistent with the manual's rule |

### 6.3 Screen enable, transparency enable and mosaic (ST-058 4.1, 4.16-4.17 mosaic)

Compared: BGON (180020h), MZCTL (180022h) and their use in the NBG/RBG renderers.

Matches the manual: BGON bit layout (N0ON..N3ON bits 0-3, R0ON bit 4, R1ON bit 5, N0TPON..N3TPON bits 8-11, R0TPON bit 12) and the
"xxTPON=1 shows transparent-code dots" meaning; MZCTL layout (N0MZE..N3MZE, R0MZE bits 0-4, MZSZH bits 11-8, MZSZV bits 15-12,
size = field + 1 dot); rotation surfaces mosaic horizontally only (`mosaic_width`, p.119); NBG mosaic disables vertical cell scroll
(`cell_scroll = ... && !mosaic`).

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-16 | Stale "missing mosaic" statement | n/a | the header TODO list at the top of `saturn.cpp` still lists "Missing mosaic effect", but mosaic is implemented in the NBG and RBG scanline renderers (`mosaic_x/mosaic_y`); the legacy `vdp2_draw_mosaic` post-pass is compiled out by `TEST_FUNCTIONS 0`. The comment is stale (this is the earlier V2-D item) |
| V2-P1-17 | Interlace and mosaic | 4.17: vertical size table gives doubled sizes for interlace but the note says there is no relationship with the interlace setting; with double-density interlace, mosaic screens display as single-density interlace | code doubles the vertical size when LSMD=3 (`(MZSZV+1) * 2`) and does not switch the screen to single-density; the manual text is self-contradictory on the doubling and the behaviour is not settled by ST-058 alone |
| V2-P1-18 | BGON with R1ON but not R0ON, and RBG with NBG | 4.1: R1ON must not be set without R0ON; when R0ON and R1ON are both 1 the normal scroll screens cannot display and their ON bits should be 0 | `vdp2_prepare_vram_access` treats R1ON as owning B0/B1 and skips their cycle registers, but the renderers are not shown to suppress NBG output when both are on; not checked further |

### 6.4 Cell/bitmap dot formats, transparency, pattern name data (ST-058 4.3-4.6, Tables 4.1-4.6, Figures 4.9-4.11)

Compared: `vdp2_dot_pixel`, `vdp2_pattern_pixel`, `vdp2_scroll_pixel`, CHCTLA/CHCTLB and PNCN0-3/PNCR field decode.

Matches the manual (each item checked field by field):
- CHCTLA/CHCTLB layout: N0CHCN bits 6-4, N0BMSZ 3-2, N0BMEN 1, N0CHSZ 0; N1CHCN bits 13-12, N1BMSZ 11-10, N1BMEN 9, N1CHSZ 8; N2CHCN bit 1, N2CHSZ bit 0, N3CHCN bit 5, N3CHSZ bit 4; R0CHCN bits 14-12, R0BMSZ bit 10, R0BMEN bit 9, R0CHSZ bit 8.
- Dot sizes and cell bytes: 4, 8, 16, 32 bits per dot with 32/64/128/256 bytes per cell on 20h boundaries (`bytes_per_cell = 32 << ...`); 4-bit dots take the high nibble first.
- Transparent code: 4-bit and 8-bit dots are transparent at zero, 2048-colour dots at zero in the low 11 bits (`raw &= 0x7ff`), 32768- and 16.77M-colour dots when the MSB is 0; xxTPON=1 draws them (`STV_TRANSPARENCY_NONE`).
- Palette bits: 16-colour uses the 4-bit (one-word) or 7-bit (two-word) palette number shifted left by 4, 256-colour uses the top 3 palette bits (`& 0x700`), 2048-colour ignores the palette number, RGB formats ignore it (Figure 4.11).
- Two-word pattern name: vertical flip bit 31, horizontal flip bit 30, PR bit 29, CC bit 28, palette bits 22-16, character number bits 14-0.
- One-word pattern name (Table 4.6): for all eight size/colour/supplement combinations the character-number assembly (10-bit or 12-bit field from the name, plus supplement bits 1-0 and 4-2 as the table requires, with bits 4-2 supplying character bits 14-12 and bit 4 alone supplying bit 14 for the 2x2/mode 1 case) matches; flips are only honoured in supplement mode 0.
- 4 Mbit VRAM: character number bit 14 is unused (the address is masked by `word_mask`).
- 2x2 characters flip the whole 16x16 character, not each cell.
- RGB555 to RGB888 appends three zero bits; 24-bit dots use bits 23-0 with the MSB as the transparent flag.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-19 | Colour-count exclusions | 4.5 (p.61): NBG0 at 2048/32768 colours removes NBG2; NBG0 at 16.77M removes NBG1-NBG3; NBG1 at 2048/32768 removes NBG3; 5.2 Table 5.2 reduction ties up NBG2 | enforced in the NBG2/NBG3/NBG1 setup (`current_tilemap.enabled = 0` for `N0CHCN` 2-4, `N0ZMQT`, `N0ZMHF` with 256 colours, `N1CHCN` 2-3). Prohibited depths (N0CHCN 5-7) are drawn transparent. Not enforced: RBG0/RBG1 "cannot display" in exclusive monitor mode |
| V2-P1-20 | VRAM 4 Mbit vs 8 Mbit character number | 4.6: bit 14 unused only with 4 Mbit VRAM | with 8 Mbit VRAM the full 15 bits are used; the bitmap and character addressing use the same VRAMSZ mask, verified by reading `word_mask` use only |
| V2-P1-21 | Bitmap size decode | 4.5: NBG0/NBG1 use two bits (00=512x256, 01=512x512, 10=1024x256, 11=1024x512); RBG0 uses one bit (0=512x256, 1=512x512) | matches: NBG sizes are decoded through `bitmap_size & 2` (width) and `& 1` (height), RBG0 stores the single bit so its width is always 512. Only the register-block comment still says "*guessed*" (stale comment) |

### 6.5 Planes, maps and map offsets (ST-058 4.6-4.8, Table 4.8)

Compared: PNCN0-3/PNCR bit layout, PLSZ (18003Ah), MPOFN/MPOFR (18003Ch/18003Eh), MPABN0..MPCDN3 (180040h-18004Eh),
`vdp2_scroll_pixel` page/plane/map addressing, `map_offset[]` assembly.

Matches the manual:
- PNCN layout: PNB bit 15 (1 = one word), CNSM bit 14, SPR bit 9, SCC bit 8, SPLT6-4 bits 7-5, SCN4-0 bits 4-0.
- PLSZ layout: N0..N3 at bits 1-0/3-2/5-4/7-6, RA at bits 9-8, RB at bits 13-12; 00 = 1x1 page, 01 = 2x1, 11 = 2x2.
- MPOFN: N0 bits 2-0, N1 bits 6-4, N2 bits 10-8, N3 bits 14-12; each map register byte holds two 6-bit plane fields (A/C low byte, B/D high byte). The map value is `MPx | (offset << 6)`, a 9-bit selector.
- Table 4.8: the page address is `(selector & mask) & ~(pages-1)` in page units, with masks of 6, 7, 8 or 9 bits depending on (one/two word, 1x1/2x2 character) โ€” recomputed: one word 2x2 uses bits 8-0 (x800h), one word 1x1 bits 6-0 (x2000h), two words 2x2 bits 7-0 (x1000h), two words 1x1 bits 5-0 (x4000h); for larger planes the low bit(s) are dropped (e.g. 2x2 pages, 2 words, 1x1: bits 5-2 x10000h). For 4 Mbit VRAM the top selector bit is dropped by the VRAM word mask.
- Bitmap boundary = map offset x 20000h.
- Page sizes 8192/2048/16384/4096 bytes (Table 4.4) follow from `page_bytes`.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-22 | Invalid plane size 10b | 4.7: PLSZ=10 is invalid, do not set | decoded as 1 page wide by 2 pages tall (`plane_size & 2` gives 2 V pages); no manual behaviour to compare |
| V2-P1-23 | 2x2 pages with 1/4 reduction | 4.7/4.8: do not set 2x2 pages when NBG0/NBG1 reduce to 1/4; the map becomes "normal" size | not enforced or specially handled (`map_count == 4` for NBG0/1); the manual text about the reduced map (Figure 4.16) is ambiguous |
| V2-P1-24 | RBG1 plane size source | 4.5: NBG0 registers apply to RBG1 for colour/character control | `current_tilemap.plane_size = R1ON ? RBPLSZ : N0PLSZ` uses rotation parameter B's plane size for RBG1; whether ST-058 chapter 6 assigns RBG1's plane and map to parameter B is checked in the rotation section |
| V2-P1-25 | Comment "guessed" registers | n/a | the macro comments still say "*guessed*" for bitmap sizes (stale) |

### 6.6 Normal scroll screens: scroll, zoom, reduction, line and vertical cell scroll (ST-058 chapter 5)

Compared: SCXIN0-SCYN3 (180070h-180096h), ZMXIN0-ZMYDN1 (180078h-18008Eh), ZMCTL (180098h), SCRCTL (18009Ah), LSTA0/1
(1800A0h-1800A6h), VCSTA (18009Ch-18009Eh), and the scanline renderer in `vdp2_draw_scroll_screen`.

Matches the manual:
- NBG0/NBG1 scroll values are 11-bit integer + 8-bit fraction (fraction in bits 15-8 of the second word); NBG2/NBG3 are 11-bit integers. Coordinate increments have a 3-bit integer part and 8-bit fraction (`0x7ff00` mask); NBG2/NBG3 increments are fixed at 1.0 (0x10000).
- Display coordinate = increment x counter + scroll value, fraction kept through the calculation and discarded for the final coordinate (p.126, `int64` 16.16 accumulation).
- ZMCTL bits: N0ZMHF bit 0, N0ZMQT bit 1, N1ZMHF bit 8, N1ZMQT bit 9. Table 5.2 exclusions are enforced (ยง6.4 V2-P1-19).
- SCRCTL: N0VCSC bit 0, N0LSCX bit 1, N0LSCY bit 2, N0LZMX bit 3, N0LSS bits 5-4; NBG1 fields at bits 8-13.
- Line scroll tables: entries hold horizontal scroll (11.8, signed relative), vertical scroll (11.8) and horizontal increment (3.8), in that order, only for the enabled fields (`stride`); one table entry per interval of 1/2/4/8 lines, the vertical scroll for lines inside an interval advancing by the vertical increment (p.131).
- Line and vertical cell scroll table addresses: register value x 4 (`(U<<16|L) * 2` bytes in the code's bit layout, which places LSTA1 at bit 1); the MSB is ignored for 4 Mbit VRAM.
- Vertical cell scroll table entries: 32-bit (11.8) per cell; when both NBG0 and NBG1 use it, entries alternate NBG0/NBG1 (`cell_stride = 2`); vertical cell scroll is ignored when mosaic is on.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-26 | Line scroll interval in interlace | 5.3 SCRCTL table: the interval in lines depends on the interlace mode (non-interlace 1/2/4/8, single-density and double-density differ) | the code uses `1 << LSS` bitmap rows for every mode; comments state a single-density field repeats the picture. The garbled table in the text extraction was not fully reconstructed, so equivalence with the manual is not established for single- and double-density interlace |
| V2-P1-27 | Coordinate increment above the reduction range | 5.2 Table 5.1: increments above 1, 2, 4 are prohibited for none/half/quarter reduction | no clamp: a larger increment is applied as written |
| V2-P1-28 | Negative scroll values | 5.1: scroll values must be positive; the display area repeats | scroll and line-scroll tables are decoded as signed when relative (line scroll data is relative and sign-extended); register scroll values are used as 11-bit positive numbers |
| V2-P1-29 | Reduction of a bitmap layer and cell-scroll granularity | 5.3: vertical cell scroll operates in 8-dot columns also in bitmap format | cell boundaries are counted in source-cell columns (`>> 19`), matching the manual's 8-dot cells |
| V2-P1-30 | RBG1 plane size (resolves V2-P1-24) | ST-058 chapter 6 intro and Table 6.1: RBG1 always uses rotation parameter B | `plane_size = R1ON ? RBPLSZ : N0PLSZ` is consistent with the manual |

### 6.7 Rotation scroll surfaces (ST-058 chapter 6)

Compared: rotation parameter table decode (`vdp2_fill_rotation_parameter_table`), RPTA/RPMD/RPRCTL/KTCTL/KTAOF/RAMCTL RDBS/PLSZ.OVR
fields, the per-line latch (`vdp2_latch_rotation_parameters`), the coefficient table modes, screen-over, and the RBG0/RBG1
renderer set-up in `saturn.cpp`.

Matches the manual (field widths checked against Figure 6.2 and Figure 6.3):
- Table layout: 0x60-byte tables, parameter A at RPTA and parameter B at +0x80 (RPTA6 forced 0/1 via byte address bit 7); RPTA byte address = register x 2 in the code's bit layout; wrap inside VRAM.
- Xst/Yst/Zst 13-bit signed integer-in-word + 10-bit fraction (`0x1fffffc0`), Xst/Yst increments and X/Y increments 13 bits (`0x7ffc0`, sign bit 18), matrix A-F 14 bits (`0xfffc0`, sign bit 19), Px/Py/Pz and Cx/Cy/Cz 14-bit signed integers (two per word for Px/Py and Cx/Cy), Mx/My 24 bits (`0x3fffffc0`), kx/ky 24 bits with 16-bit fraction, KAst 32 bits (16.10), dKAst/dKAx 20 bits (`0x03ffffc0`); word order matches the 24 words of Figure 6.3.
- Xst/Yst/KAst are read on the first line and re-read only when RPRCTL requests it (`m_rotation_latch_valid`, `reload & 1/2/4`); otherwise the per-line increment accumulates. RPRCTL bits 0-2 and 8-10 are cleared when consumed ("At the same time, this bit is cleared to 0").
- RPMD modes 0-3: A, B, A/B switched by the coefficient MSB of A's table, A/B switched by the rotation parameter window; RBG1 always uses parameter B and RBG1's coefficient and line-colour source is A's table; RPMD=2 with A reading coefficients per dot ignores B's per-dot request (`per_dot_coefficients`).
- KTCTL: RAKTE bit 0, RAKDBS bit 1, RAKMD bits 3-2, RAKLCE bit 4, B fields +8; KTAOF: RAKTAOS bits 2-0, RBKTAOS bits 10-8; 2-word tables use `(KTAOS & 3) x 40000h + index x 4`, 1-word tables `(KTAOS & 7) x 20000h + index x 2` (p.170).
- RAMCTL RDBS decode selects the coefficient/name/character bank roles (see 6.2); the coefficient table can be in the upper half of colour RAM when CRKTE=1 (comment at coefficient setup).
- Screen over: RxOVR=1 repeats the OVPNR character pattern (cell format only), 2/3 make the outside transparent (display area 512x512 for 3).
- Rotation coordinates: start value 20 bits with 9 fractional bits, increment 12 bits (`vdp1_rotation_coordinate`, ST-058 p.159, used for frame-buffer rotation read).

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-31 | Unit-step rotation shortcut | 6.1: coordinates always derive from the full matrix, kx/ky, coefficient table and windows | `vdp2_is_rotation_applied` returns "no rotation" when A=E=1, others 0, dxst=0, dyst=1, dx=1, dy=0, kx=ky=1, xst=yst=0 and no coefficient table, over-process, line screen, mosaic, window, LSMD=3 or hi-res; the shortcut path is expected to be equivalent but its equivalence with the full path was not proven in this pass |
| V2-P1-32 | Coefficient MSB semantics | Table 6.4 | the mode-2 A switch, B/other transparent-bit handling and RBG1 always-transparent rules are present (see `selected`, per-dot code); RBG1 transparency for coefficient MSB was not traced |
| V2-P1-33 | Prohibited RAMCTL combinations | 6.2/6.4: RBG1 requires RDBSB fields 00, CRKTE=1 requires colour RAM mode 1 and forbids the coefficient RAM role in bank 4 | not enforced beyond the fetch gating of 6.2 |
| V2-P1-34 | Rotation in exclusive monitor modes | 4.5 notes: RBG0/RBG1 "cannot display" for some colour counts in exclusive monitor | not enforced (same as V2-P1-19) |
| V2-P1-35 | Per-line rotation parameter timing | 6.3: parameters are read once per line; software changes take effect from the next read | latched per output line at scanline callbacks (`vdp2_latch_rotation_parameters`), interlace stepping preserved; the exact hardware read position within the line is not modelled |

### 6.8 Line colour screen and back screen (ST-058 chapter 7)

Compared: LCTAU/LCTAL (1800A8h/1800AAh), BKTAU/BKTAL (1800ACh/1800AEh), `vdp2_line_color`, `vdp2_back_screen_color`, `vdp2_draw_back`.

Matches the manual: LCCLMD/BKCLMD are bit 15 of the upper word (0 = single colour from the first entry, 1 = one entry per line); table address is the 19-bit register value x 2 with the top bit dropped for 4 Mbit VRAM (`base_mask` on BKTA, `mask` on the line colour address, per-row wrap); back screen data is 5-5-5 RGB expanded by appending three zero bits; line colour data is an 11-bit colour RAM address (`& 0x7ff`) and replaces its low seven bits with the coefficient colour bits when a rotation coefficient table carries line colour (p.164); the line colour has no colour RAM address offset added; DISP=0 with BDCLMD=1 still shows the back screen and DISP=0 with BDCLMD=0 shows black (2.4).

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-36 | Single-density interlace entry pairing | 7.1/7.2: in single-density interlace one table entry covers two lines | both functions index by the output row `y` with one entry per row for every mode; the comments state that the output bitmap already carries one row per picture line in single-density, which would make the code equivalent, but that mapping was not independently verified |
| V2-P1-37 | Colour RAM mode 0/2 address MSB | 7.1 Figure 7.3: in modes 0 and 2 the MSB of the 11-bit address is ignored | `& 0x7ff` keeps bit 10; in mode 0 the two 1K-word halves mirror each other, but in mode 2 the palette lookup of an address with bit 10 set may address the other bank instead of wrapping |
| V2-P1-38 | Back screen border area | 2.4: with per-line back screen the border takes the colour of the last display line | the whole clip rectangle is filled row by row; the horizontal/vertical border area outside the active area is not separately drawn |

### 6.9 Windows (ST-058 chapter 8)

Compared: WPSX0..WPEY1 (1800C0h-1800CEh), LWTA0/1 (1800D8h-1800DEh), SPCTL SPWINEN, WCTLA-D (1800D0h-1800D6h), the
window evaluation in `vdp2_window_process_pixel`, `vdp2_roz_window`, `vdp2_roz_mode3_window`, `vdp2_calculation_window`,
`vdp2_sprite_window`.

Matches the manual (each window-control field checked against the bit tables in 8.2):
- WCTL bit layout: per screen W0A/W0E/W1A/W1E/SWA/SWE/LOG at bits 0-5 and 7 of each byte (NBG0/RBG1 low byte of WCTLA, NBG1 high byte; NBG2/NBG3 in WCTLB; RBG0/sprite in WCTLC; rotation-parameter/colour-calculation in WCTLD).
- The window logic is implemented on "drawn" flags, so De Morgan applies: LOG=0 (OR of valid areas) ANDs the per-window drawn flags and LOG=1 (AND of valid areas) ORs them; with no window enabled LOG=0 leaves the screen unaffected and LOG=1 makes the whole screen a valid area (`vdp2_window_all_disabled`). This matches the manual (p.193) and Ymir's `0=OR, 1=AND`.
- Area bit A=0 selects the inside and A=1 the outside; the boundary line belongs to the inside; a start coordinate greater than the end coordinate gives an empty inside (whole screen outside), because the inclusive comparison fails.
- The colour calculation window suppresses calculation only (`vdp2_calculation_window`, p.190) with its own W0/W1/SW enables and logic; the rotation parameter window selects between A and B in RPMD mode 3 with its own W0/W1 enables.
- Sprite window: valid only when SPWINEN=1, SPCLMD=0 and sprite type 2-7; it tests the MSB of the VDP1 frame buffer word.
- Line window table: entries of start (high half) and end (low half), the address is the register value x 4 with the top bit dropped for 4 Mbit; enable bit W0LWE/W1LWE is bit 15 of the upper word.
- Vertical coordinates: nine bits; in double-density interlace of the normal/hi-res modes bit 0 is ignored for the start and set for the end so both fields are covered (Table 8.2).

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-39 | Negative window coordinates | 8.1: only 10 bits (X) and 9 bits (Y) are defined; the shaded upper bits of the registers and table entries are ignored | `vdp2_get_window*_coordinates` reads `(int16_t)` values and `fixup_window_x` treats a set bit 15 as a negative coordinate (start clamped to 0, an end below zero forces the start to 3FFh). Not in ST-058; bits 15-10 should be ignored |
| V2-P1-40 | Horizontal coordinate mapping per graphics mode | Table 8.1 (garbled in the extraction): normal and hi-res use 9 bits H8-H0 with the LSB invalid, exclusive normal uses ten bits, exclusive hi-res drops the top bit | normal `(v & 0x3fe) >> 1`, hi-res `v & 0x3ff`, exclusive normal `v & 0x1ff`, exclusive hi-res `(v & 0x1ff) << 1`; the exclusive normal mode masks nine bits although the table lists ten. Table 8.1 could not be reconstructed with certainty from the extraction, so this needs a check against the original PDF |
| V2-P1-41 | Single-density interlace line tables | 8.1 Figure 8.4: one entry per two lines in single-density interlace | one entry per output row in every mode (`m_vdp2_vram[... + y]`); comments assert the output bitmap has one row per picture line in single-density |
| V2-P1-42 | Rotation parameter window bits | 8.2 WCTLD: RPSWE and RPSWA are unused ("~") | `vdp2_roz_mode3_window` decodes RPSWE (bit 5) and RPSWA (bit 4) as a sprite-window enable/area for the rotation parameter window; software that leaves them 0 is unaffected |
| V2-P1-43 | Window on RBG0 | 8.2: transparency window per screen including RBG0 | the RBG0 tilemap setup zeroes its window control ("we apply them in the roz routines") and applies `vdp2_roz_window` per dot; RBG1 uses the NBG0 window bits, as the manual assigns ("NBG0 (or RBG1)") |

### 6.10 Sprite data, priority and colour calculation ratio registers (ST-058 chapter 9, Figure 9.1, Tables 9.1-9.3)

Compared: SPCTL (1800E0h), PRISA-PRISD (1800F0h-1800F6h), CCRSA-CCRSD (180100h-180106h), and `draw_sprites` with its five
per-type tables.

Matches the manual (all sixteen sprite types were checked against Figure 9.1, bit by bit):
- Type 0: PR1-0 bits 15-14, CC2-0 bits 13-11, DC10-0; type 1: PR2-0 bits 15-13, CC1-0 bits 12-11; type 2: SD 15, PR0 14, CC2-0 13-11; type 3: SD, PR1-0 14-13, CC1-0 12-11; type 4: SD, PR1-0 14-13, CC2-0 12-10, DC9-0; type 5: SD, PR2-0 14-12, CC0 11, DC10-0; type 6: SD, PR2-0 14-12, CC1-0 11-10, DC9-0; type 7: SD, PR2-0 14-12, CC2-0 11-9, DC8-0. The `priority_shift/mask`, `ccrr_shift/mask`, `colormask` and `shadow_mask` tables agree for types 0-7.
- 8-bit types: type 8 PR0 bit 7 with a 7-bit dot; type 9 PR0 bit 7, CC0 bit 6, 6-bit dot; type A PR1-0 bits 7-6; type B CC1-0 bits 7-6, no priority bit; types C-F have the shared bits (SP/SC are also part of the 8-bit dot): C SP0 bit 7, D SP0/SC0 bits 7/6, E SP1-0 bits 7-6, F SC1-0 bits 7-6. Bits that a type lacks read as 0, so the missing priority selects register 0 and the missing ratio selects register 0.
- Priority register selection (Table 9.2) and ratio register selection (Table 9.3) use the value of the type's PR/CC bits as the register index; RGB sprites (mixed mode, MSB=1, SPCLMD=1) always use register 0 for priority and ratio; a priority number of 0 is not displayed.
- Sprite colour calculation condition: 0 = priority <= condition number, 1 = equal, 2 = >=, 3 = colour data MSB (RGB sprites always calculate with SPCCCS=3); enabled only with SPCCEN.
- The sprite palette address is `dot + SPCAOS x 256`, bit 10 masked at 0x7ff; SD is bit 15 for types 2-7 and is not present for other types.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-44 | Mixed RGB/palette mode with 8-bit sprites | 9.2: do not set SPCLMD=1 with 8-bit pixels | `direct = (pix & 0x8000) && SPCLMD` is evaluated for 8-bit types too, where the display word can only be 0-255; harmless for compliant software |
| V2-P1-45 | Sprite data with types selected inconsistently with the VDP1 depth | 9.1: 16-bit frame buffer must use types 0-7, 8-bit types 8-F | not enforced; the type table is applied to whatever value the VDP1 display pipeline returns |
| V2-P1-46 | Colour RAM address bit 10 in modes 0/2 | 10.1 Figure 10.2: the MSB is ignored in modes 0 and 2 | `& 0x7ff` retains bit 10; same open point as V2-P1-37 |

### 6.11 Pixel formats, colour RAM address offset, special function codes and priority (ST-058 chapters 10 and 11.1-11.2)

Compared: CRAOFA/CRAOFB (1800E4h-1800E6h), SFSEL (180024h), SFCODE (180026h), SFPRMD (1800EAh), PRINA/PRINB/PRIR
(1800F8h-1800FCh), `vdp2_special_priority_pixel`, `vdp2_special_color_pixel`, `vdp2_priority_pass_matches`,
`screen_update_vdp2` layer ordering.

Matches the manual:
- Priority registers: N0PRIN bits 2-0 and N1PRIN bits 10-8 in PRINA, N2/N3 in PRINB, R0PRIN in PRIR; a priority of 0 is transparent; screens are drawn per priority number 1-7 in the order NBG3, NBG2, NBG1, NBG0, RBG0, sprite, so equal priorities resolve as sprite > RBG0 > NBG0 > NBG1 > NBG2 > NBG3 (Table 11.1); RBG1 shares the NBG0 slot and is drawn before RBG0.
- Special function code select: bit n of SFSEL picks code A (low byte) or B (high byte) of SFCODE for layer n; code bit k corresponds to the dot codes 2k and 2k+1, so the code is indexed by `(dot >> 1) & 7`; only palette formats use it.
- Special priority mode (SFPRMD, two bits per screen, R0 at bits 9-8): mode 0 keeps the register value, mode 1 uses the pattern-name special priority bit as the priority LSB, mode 2 sets the LSB only for dots whose code matches while the special priority bit is 1; the two upper bits always come from the register; a resulting priority of 0 is transparent; RGB formats ignore mode 2.
- CRAOFA/CRAOFB layout: N0 bits 2-0, N1 bits 6-4, N2 bits 10-8, N3 bits 14-12, R0 bits 2-0 and sprite bits 6-4 of CRAOFB; the offset is added to the top three bits of the 11-bit colour address (`<< 8`).
- RGB formats append three zero bits to each 5-bit component; the back screen does the same.

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-47 | Colour RAM address offset scale | 10.1: mode 0/2 offset = register x 200h, mode 1 offset = register x 400h (byte addresses, per the text) | the code adds `offset << 8` to the 11-bit palette index in every mode (top-three-bits rule of Figures 10.2/10.4, also used by the reference emulators); the byte-address formulas in the manual (which differ by mode and by entry size) were not reconciled with the entry-index formula |
| V2-P1-48 | Special priority in bitmap layers | 11.2: for bitmap formats the special priority bit comes from the bitmap palette number register (BMPNA/BMPNB), not the pattern name | implemented (`bitmap_flags & 0x20` for priority, `& 0x10` for colour calculation) |
| V2-P1-49 | EXBG restrictions | 11.2: EXBG must be in special priority mode 0 | external screen input is not modelled (V2-P1-07) |
| V2-P1-50 | Equal-priority order with two rotation screens or external input | Table 11.1: separate orderings for RBG1 and EXBG | RBG1 order follows Table 11.1; the EXBG orders cannot apply |

### 6.12 Line colour insertion, colour calculation, gradation, colour offset and shadow (ST-058 chapters 11.3, 12, 13, 14)

Compared: LNCLEN, CCCR (1800ECh: BOKEN bit 15, BOKN 14-12, EXCCEN bit 10, CCRTMD bit 9, CCMD bit 8, N0-N3/R0/LC/SP CCEN bits 0-6),
CCRNA/CCRNB/CCRR/CCRLB (180108h-18010Eh), SFCCMD (1800EEh), CLOFEN/CLOFSL (180110h/180112h), COAR-COBB (180114h-18011Eh), SDCTL (1800E2h),
and `vdp2_compose_pixel`, `vdp2_begin_composition`, `vdp2_extended_color`, `vdp2_gradation_color`, `vdp2_shadow_pixel`,
`vdp2_compute_color_offset`, `vdp2_calculation_window`.

Matches the manual:
- Ratio: 5-bit value n gives top:second = (31-n):(n+1) (`vdp2_cc_blend_level`, `(31-n) x 8` of 256, exact), n=15 gives 16:16 and n=31 gives 0:32; CCRTMD=0 uses the top screen's ratio, CCRTMD=1 the second screen's (line colour screen and back screen use LCCCRT/BKCCRT); CCMD=1 adds the colours as is with saturation and ignores the ratio registers; calculation is enabled by the top image's CCEN bit.
- Table 12.1 (hi-res and exclusive modes): with colour RAM mode 1 or 2 a palette second image cannot be used, mode 0 always can (`hreso & 6`, `VDP2_CRMD`, second image palette flag).
- Extended colour calculation: only in normal modes and only when BOKEN is 0 (`(CCCR & 0x8400) == 0x400`); fixed 1/2, 1/4 weights per Table 12.2, truncating each component before adding; the line colour screen is the extra second input when inserted.
- Gradation: only with BOKEN=1, colour RAM mode 0 and normal mode; BOKN selects sprite (0), RBG0 (1), NBG0/RBG1 (2), NBG1 (4), NBG2 (5), NBG3 (6); the calculation is 1:1:2 of two-left, one-left and current dot per component; the designated screen is forced into the second image; incompatible with line colour insertion and extended calculation.
- Colour offset: A/B selected per screen by CLOFSL; each component is a 9-bit two's-complement value clamped to 0..255; applied after colour calculation and only with the top image's enable bit; the back screen offset affects only the visible back (`VDP2_CLOFEN & 0x20`).
- Shadow: normal shadow when the sprite dot equals the type's dot mask minus one; MSB shadow only for types 2-7 with the sprite window off; transparent shadow (MSB set, remaining 15 bits zero) only when TPSDSL is 1; normal shadow takes precedence over MSB shadow; scroll and back screens are shadowed only when their SDEN bit is set; a sprite shadow always shades its own dot; the shadow halves each component and is applied after colour calculation and colour offset.
- Colour RAM MSB special colour calculation (mode 3) reads the physical colour RAM MSB including mode-0 aliasing (`vdp2_palette_color_msb`).

| ID | Finding | Manual | Code |
|---|---|---|---|
| V2-P1-51 | Extended calculation ratio 2:1:0 | Table 12.2 lists 2:1:0 for one row and Figure 12.3 shows a fourth input | the code uses 2:1:1 (`(a >> 1) + (b >> 2) + (c >> 2)`) in that row; its comment cites the Figure and both reference emulators for the change; the manual's own table and figure disagree |
| V2-P1-52 | Gradation left-edge policy | 12.2: pixels outside the left display edge are not specified | x=0 keeps the current dot, x=1 averages current and left; policy taken from Ymir |
| V2-P1-53 | BOKEN with unusable modes | 12.2: gradation requires normal mode and colour RAM mode 0 | the function is silently disabled outside that condition rather than showing an error state; no manual behaviour defined |
| V2-P1-54 | Line colour insertion with gradation | 11.3: cannot be used together | insertion is forced off when gradation is active (`if (gradation) insert_line = false`) |
| V2-P1-55 | Shadow "highest priority" rule | 14.1: the shadow applies when the shadow sprite's priority is the highest | implemented per sprite pass: the shadow darkens the composed image below the sprite and higher-priority layers drawn afterwards overwrite it; equivalence with the manual's top-image wording was reasoned, not tested |
| V2-P1-56 | Colour offset clamp detail | 13.1: values below 00h read as 00h, above FFh as FFh | matches (`vdp2_compute_color_offset`) |

VDP2 items not compared in this pass: exact VRAM bank timing (Tables 3.2-3.4, V2-P1-11), CRAM layout for the coefficient table in
colour RAM (CRKTE) at the byte level, and the framebuffer/VDP1 to VDP2 handoff for the 8-bit and 16-bit sprite word delivery in
hi-res and rotation modes (VDP1 `vdp1_display_pixel`, checked only for the type decode).

## 7. SCU (ST-097 SCU User's Manual and ST-210 SCU Final Specifications: Precautions against `saturn_scu.cpp`)

The DSP (ST-097 chapter 4 and the DSP assembler manual) is compared in ยง7.2. Numbers are SCU-P1-nn.

### 7.1 DMA, timers, interrupts, A-Bus registers

Compared: DMA set registers (25FE0000h-25FE0057h), DSTP (25FE0060h), DSTA (25FE007Ch), timers (25FE0090h-25FE0098h), IMS/IST
(25FE00A0h/25FE00A4h), AIACK (25FE00A8h), ASR0/ASR1/AREF (25FE00B0h-25FE00B8h), RSEL (25FE00C4h), version (25FE00C8h), the
interrupt table (Table 2.1), the DMA engine and indirect table, and precautions No.01-36 of ST-210.

Matches the manual:
- DxR/DxW store 27 bits; D0C is 20 bits and D1C/D2C are 12 bits; DxAD read add value is bit 8 (0 = none, 1 = 4 bytes) and write add value is bits 2-0 (0 none, 1 = 2, 2 = 4, ... 7 = 128 bytes); DxEN enable is bit 8 and DxGO bit 0; DxMD indirect bit 24, RUP bit 16, WUP bit 8, start factor bits 2-0 (Tables 3.2-3.4, ST-210 No.21: 0 V-BLANK-IN, 1 V-BLANK-OUT, 2 H-BLANK-IN, 3 Timer 0, 4 Timer 1, 5 sound request, 6 sprite draw end, 7 enable+GO).
- DMA status DSTA bit layout: level 0 wait/move bits 5/4, level 1 bits 9/8, level 2 bits 13/12, DSP wait/move bits 1/0, level 0/1 interrupted (background) bits 16/17, bus-access bits 20-22; higher levels pre-empt lower ones and a lower level waits (Figure 3.12).
- Interrupt table: bit n vector 40h+n and levels F, E, D, C, B, A, 9, 8, 8, 6, 6, 5, 3, 2 for bits 0-13; A-Bus external interrupts bits 16-31 use vectors 50h-5Fh at levels 7 (0-3), 4 (4-7) and 1 (8-15); IMS reset value 0000BFFFh; masks are active-high; IST bits are cleared by writing 0.
- Indirect DMA table (ST-210 No.25): three longwords (byte count, write address, read address with bit 31 as the last-entry flag), 12 bytes per entry.
- ST-210 No.01/02: A-Bus writes and VDP2 reads are rejected as DMA-illegal (IST bit set, nothing moves); No.04 (work RAM-L, and BIOS/backup RAM as sources) rejected; a start trigger during a running transfer is held once and re-run at the end (No.22); AREF initial ARFEN=1 (No.33); RSEL resets to 0 (No.34); ASR0/ASR1 preread bits 31 and 15 are forced 0 (No.09).
- Timer 0: cleared at V-Blank-OUT, incremented at H-Blank-IN, compare register is 10 bits; T0C=0 fires at V-Blank-OUT and T0C>263 never fires (No.30). Timer 1: loaded from the 9-bit T1S at H-Blank-IN when stopped, counts down at 7.16 MHz (clock/8), T1MD=1 restricts the interrupt to the Timer 0 line, T1S=0 means 512 (No.31); TENB gates both timers.

| ID | Finding | Manual | Code |
|---|---|---|---|
| SCU-P1-01 | Interrupt mask reset on vector fetch | ST-097 gives only the IMS initial value 0000BFFFh (Figure 3.21); nothing in ST-097 or ST-210 says the mask is reset when an interrupt is acknowledged | `irq_ack_cb` sets `m_ism = 0xbfff` at every vector fetch; the code comment attributes this to ST-097 figure 3.21, but the behaviour comes from the Mednafen `SCU_MSH2VectorFetch` and Ymir `AcknowledgeExternalInterrupt` implementations (both set the mask to BFFFh). It is reference-emulator behaviour, not a manual rule, and the comment should say so |
| SCU-P1-02 | IST bit cleared at delivery | Table 3.8: IST bit 1 = interrupt occurs, writing 0 resets, writing 1 keeps; the manual does not say the bit clears when the CPU takes the interrupt | `test_pending_irqs` clears the IST bit as soon as it asserts the SH-2 line (`m_ist &= ~(1 << internal)`), so software cannot read a taken interrupt as pending; not established by the manual |
| SCU-P1-03 | Timer 0 counter width | 3.4: T0C is 10 bits; the counter counts H-Blank-IN from V-Blank-OUT | the counter is masked to 9 bits (`& 0x1ff`); with <= 525/562 lines per frame and the counter cleared each V-Blank-OUT this only matters for compare values 512-1023, which never fire in either case (ST-210 No.30) |
| SCU-P1-04 | Write-only registers readable | Figure 3.1-3.4: DxR/DxW/DxC listed R/W in ST-097 but ST-210 No.15 says DxC is write-only and reads are not guaranteed; D0AD/D0EN/D0MD are write-only | DxR, DxW and DxC are readable in `dma_map`; the other registers read as 0 (`nopr`) |
| SCU-P1-05 | DSTA reads | ST-210 No.13: the DMA status register function was deleted (only the bits left in the 2nd version manual remain valid) | DSTA is readable at 25FE007Ch and also mirrored at 25FE005Ch ("undocumented ... mirror?" in the code) for stv smleague/shinmtaz |
| SCU-P1-06 | DSTP | ST-210 No.14: the force-stop register function was deleted, writes prohibited | `dma_force_stop_w` implements the ST-097 behaviour (idle all levels, keep registers) |
| SCU-P1-07 | Writing DMA registers while running | ST-097 3.2 and ST-210 No.23: prohibited (the SCU hangs) | not modelled; writes are accepted |
| SCU-P1-08 | Level 2 started during level 1 | ST-210 No.35: malfunction possible | not modelled |
| SCU-P1-09 | Address add restrictions | ST-210 No.16-19: read add must be 1 (4 bytes) except in the A-Bus CS2 space; write add restrictions per bus; RUP/WUP require the matching add value | not enforced; illegal combinations are accepted and run |
| SCU-P1-10 | DMA illegal interrupt in indirect mode | ST-210 No.24: does not occur during an indirect transfer | the illegal check runs at `trigger_dma_direct` only, so indirect setups never raise it (consistent) |
| SCU-P1-11 | A-Bus timing registers | 3.6: ASR0/ASR1 fields (pre-charge, external wait, burst wait/length, bus size, normal wait) and AREF | only A0NW/A1NW/A3NW normal-wait counts are used (as `n + 3`) for DMA penalties; burst, precharge, bus size and refresh are stored but unused; A-Bus and B-Bus wait states remain a listed TODO in the file header |
| SCU-P1-12 | RSEL effect | ST-210 No.34: selects the SDRAM size (2 Mbit x 2 or 4 Mbit x 2) | stored only; work RAM-H is always 1 MiB |
| SCU-P1-13 | SCU version register | 3.7: version register | returns 4 "correct for stock Saturn at least" (comment); not verifiable against ST-097 from the extraction |
| SCU-P1-14 | External interrupt sources | 1.3/3.6: A-Bus interrupts and the PAD interrupt (bit 8) | only the CD block raises an external interrupt; PAD interrupt from SMPC lightgun/mouse is a TODO in the header; SMPC interrupt is wired to the system-manager bit (7) |
| SCU-P1-15 | DMA transfer unit and speed | 2.1 (p.16, Figure 2.1): DMA is basically longword access through the controller buffer, with byte units at unaligned head/tail; the B-bus splits each longword into two 16-bit writes (Figures 3.6-3.8); no transfer-time table is given | the engine reads a longword into a source buffer and writes 16-bit units (byte units at head/tail), matching the description; its per-unit time (`dma_clock_ref = clock / 1`, comment "should be /4 but saturn BIOS already disagrees") and the 1-cycle CPU steal are not derived from the manual. Accuracy limit |

### 7.2 SCU DSP (ST-097 chapters 3.3 and 4 against `scudsp.cpp`)

Compared: PPAF/PPD/PDA/PDD ports (25FE0080h-25FE008Ch), the block map (4.1), the command list (4.2-4.5): ALU, X-bus,
Y-bus, D1-bus operations, MVI, DMA/DMAH, JMP, BTM/LPS, END/ENDI, the conditional-flag rules, and the special sequences of 4.4.

Matches the manual:
- Program control port: EX bit 16 (read/write latch), ES bit 17 (write strobe, only accepted while stopped), LE bit 15 (write strobe, only while stopped), PR bit 26 / EP bit 25 (pause reset / pause, only while executing), T0 bit 23, S bit 22, Z bit 21, C bit 20, V bit 19, E bit 18; the program address P7-0 reads back the counter; reading the port clears V and E (ST-097 p.51-52, ST-210 No.36). ST-210 No.26: ENDI cannot raise another end interrupt while E is still set.
- Program RAM 256 words, four 64-word data RAM banks, PDA selects bank in bits 7-6 and word in bits 5-0 and auto-increments on PDD access; the RA field is independent of CT0-CT3 (as the code comment says).
- ALU: AND/OR/XOR set S and Z and clear C; ADD/SUB set S, Z, C and V on 32 bits; AD2 works on the 48-bit ACH:ACL and PH:PL pair; SR keeps the MSB and shifts b0 into C, RR rotates b0 into b31 and C, SL shifts b31 into C, RL rotates b31 into b0 and C, RL8 rotates by 8 with C = b24; opcodes 7 and Ch-Eh do nothing; V is a latch cleared by reading the port.
- X-bus: MOV [s],X loads RX, MOV MUL,P loads PH (high 16) and PL (low 32) from the 48-bit product (X x Y recomputed after each instruction), MOV [s],P loads PL and sign-extends PH; Y-bus: CLR A, MOV ALU,A (48 bits), MOV [s],A with ACH sign-extended from ACL; a source with "C" increments its CTx after the instruction, all buses see the instruction-entry CT values and each increment is applied once.
- D1-bus: MOV SImm,[d] (signed 8 bits) and MOV [s],[d] with destinations MC0-MC3, RX, PL, RA0, WA0, LOP, TOP, CT0-CT3 (codes 8 and 9 unused) and ALU low/high as sources.
- MVI: unconditional 25-bit signed immediate, conditional 19-bit signed with Z, NZ, S, NS, C, NC, T0, NT0, ZS, NZS conditions; MVI to PC saves the next address in TOP so a subroutine runs the following word twice (p.85, Figure 4.4).
- JMP/conditional JMP: absolute 8-bit address, one prefetched word executes before the jump.
- BTM/LPS: while LOP is not 0 the loop counter decrements and the PC returns to TOP (BTM) or the next word repeats (LPS, executed LOP+1 times).
- END/ENDI clear EX (ENDI also sets E and raises the DSP-end interrupt); a running DMA continues after END (p.88).

| ID | Finding | Manual | Code |
|---|---|---|---|
| SCU-P1-16 | DSP DMA address-add mapping (immediate count) | 4.5 DMA/DMAH: add field 0,1,2,3,4,5,6,7 selects address add 0,1,2,4,8,16,32,64 (long-word steps; only 0 and 1 valid on the A-bus; all values on the B-bus) | `op_dma` maps the field to byte adds 0,4,4,16,16,64,128,256; the entries for field values 2 and 4 (adds of 2 and 8 in the manual, i.e. 8 and 32 bytes) differ, and the code comment says "why this calculation diverges vs. SCU DMA". Bus-specific rules are then applied on top |
| SCU-P1-17 | DSP DMA count from RAM | 4.5: count from data RAM `[s]` with add value in the command | the RAM-count form only distinguishes add 0 and "not 0" (both mapped to 4 bytes), so add values above 1 are not honoured for A-bus/C-bus reads and are handled per bus in the block below |
| SCU-P1-18 | DSP DMA timing | 4.3 Tables 4.6/4.7: transfer follows the data-ready signal in long-word units; T0 stays set until the end signal | modelled as a timed transfer (T0F set, `m_dma_timer` 4 clocks) with a stated "HACK ... cycle steal" to stop the SH-2s overrunning (vfremix); no bus timing data exists in the manual |
| SCU-P1-19 | Program end interrupt | 2.2/3.3: E flag set by ENDI, interrupt raised, E cleared by reading the port | matches, with the ST-210 No.26 rule; a read of the port while the DSP runs may suppress the end interrupt per ST-210 No.36 and this is not modelled (the interrupt is raised regardless) |
| SCU-P1-20 | Clock and cycle count | 4.1: D0-bus 28 MHz, X/Y bus 14 MHz; one step about 70 ns | `SCUDSP(config, ..., XTAL(57'272'727) / 4)` = 14.3 MHz with one icount per instruction; DMA and memory-access stalls approximate. The header lists "Fix timings (no info available so far)" |
| SCU-P1-21 | Unassigned opcode groups | 4.2 lists no encoding for ALU op 7 and Ch-Eh, D1 sub-code 2, and MOV/MVI destinations 8-9 | treated as no-ops (`case 0x7`, `case 0x2 /* ??? */`, `unused`) |

## 8. CD block (ST-38 "Saturn CD Communication Interface" against `saturn_cd_hle.cpp`)

Scope of the official document. ST-38 (Doc. ST-38-R1-121093) specifies the host library (`CDC_*` functions), the four host
registers (HIRQREQ, HIRQMSK, DATATRNS, DATASTAT), the drive status model, the selector/filter/partition model and the sector
formats. It does NOT list hardware command codes, CR1-CR4 field layouts, or the MPEG and FAD-search commands. Where a finding below
needs a command code it is derived from the order of the functions in ST-38 Table 8.1 (functions are numbered in command-code
order) and the derived firmware notes in `docs/cdblock/saturn_cdblock_commands.md`, and says so. Command-level behaviour that ST-38
leaves undefined (CR-field encodings, REJECT rules) is not judged here. Numbers are CD-P1-nn.

Compared: HIRQ/HIRQMSK semantics (3.2), the drive status model and play/seek/scan rules (4.1-4.2), the selector model, filter
mode/connection/reset semantics (5, 8.2.5), buffer and sector-length functions (8.2.6-8.2.7), initialisation scope (5.5),
file system functions (8.2.8), and `cd_exec_command`, `cmd_init_cdsystem`, filter/selector command handlers.

Matches ST-38:
- HIRQ bits used by the code: CMOK 0, DRDY 1, CSCT 2, BFUL 3, PEND 4, DCHG 5 (ST-38 lists CMOK-MPEG only; ESEL/EFLS/ECPY/EHST exist in the hardware and are not in ST-38); masked bits do not drive the IRQ but remain visible in HIRQREQ.
- Selectors: 24 (0-23); default filter i true output connected to partition i, false output disconnected; filter mode bit 7 restores the defaults (range 0/0, subheader conditions 0, mode 0) and ignores the other bits; CDC_ResetSelector reset-mode bits 2-7 (partition data, partition outputs, filter conditions, filter inputs, true outputs, false outputs) are decoded per bit.
- Sector length types 2048/2336/2340/2352 with "no change" (0xff); mode 2 form 2 data of 2324 bytes is handled in the sector formatter.
- Play mode: maximum repeats in the low 4 bits, 0x7f = no change, 0x0f endless; repeat counter 4 bits, cleared when the play range or the maximum changes; play end at range end + 1 gives PAUSE and PEND (`cd_change_status(PAUSE); hirqreg |= PEND`); a full buffer pauses and sets BFUL and play resumes when space appears (`buffull_temp_pause`).
- Initialisation scope (5.5): only the soft-reset flag returns host information (play info, selector information, buffered data, transfer state) to the initial state (`cd_reset_host_information` is called only for `cr1 & 1`).
- Directory file information holds up to 254 files (`XFERTYPE_FILEINFO_254`, `std::min<size_t>(254, ...)`).

| ID | Finding | ST-38 | Code |
|---|---|---|---|
| CD-P1-01 | Open Tray | Table 8.1/4.2: `CDC_OpenTray` (function 1.7, between CdInit 1.6 and DataReady 1.8, i.e. command code 05h) "Opens the tray" | not dispatched: `cd_exec_command` has no case 0x05 (also no 0x55/0x56 and the MPEG codes beyond the implemented ones); the tray state can only change through the front-end tray control |
| CD-P1-02 | Copy and Move command codes | Table 8.1: 7.5 Write, 7.6 Copy, 7.7 Move, 7.8 Get copy/move error (numbers follow command-code order 64h, 65h, 66h, 67h); `saturn_cdblock_commands.md` also gives 65h = copy, 66h = move | `case 0x65: cmd_move_sector_data(); case 0x66: cmd_copy_sector_data();` swapped |
| CD-P1-03 | Init parameters ignored | 8.2.1 CdInit: standby time (0 = 180 s default, ffffh no change), ECC repetitions (0, 1-5, 80h none, ffh no change), retries (0, 1-Fh, 41h-4Fh, 80h, ffh no change) | `cmd_init_cdsystem` decodes only the init flag (soft reset, fixed-speed bit 4); CR2/CR3 (standby, ECC, retries) are not read. No error or retry model exists |
| CD-P1-04 | Pause to standby | 4.1 and CdInit: after the standby time in PAUSE the drive is "regarded as STANDBY" | there is no standby timer; STANDBY is entered only by an explicit stop (seek to the home position) |
| CD-P1-05 | Init closes the tray | 8.2.1: "If tray is open, this closes it" | Init keeps OPEN/NODISC (the seek is only started when a disc is present) |
| CD-P1-06 | Init flag bit 7 | 8.2.1: bit 7 = request for change in the init flag | the fixed-speed bit is applied to `cd_speed` on every Init, whether or not bit 7 is set; the code comment reads it as "no change flag" |
| CD-P1-07 | Reset selector: partition output connectors | 8.2.5: bit 3 initialises all partition output connectors (to unconnected) | `// TODO: bit 3, initialize all partition output connectors` |
| CD-P1-08 | File information at soft reset | 5.5: file information is initialised when the tray opens or on a soft reset; TOC/session information only when the tray opens (a soft reset does not touch it) | `cd_reset_host_information` is tied to the soft-reset flag; the tray-open initialisation of file/TOC information was not traced in this pass |
| CD-P1-09 | CD flag byte | 3.2 CdcStat: CD flag is a 4-bit flag, CD-DA (mute, emphasis) or CD-ROM (form, mode) | `cr_standard_return` sets CR1 bit 7 from the Q control data-track bit (added earlier); the CD-ROM mode/form bits and CD-DA mute/emphasis are reported as 0 |
| CD-P1-10 | Drive status code values | Table 4.1 / CdcRet: library status codes 00h BUSY, 10h PAUSE, 11h STANDBY, 20h PLAY, 21h SEEK, 22h SCAN, 30h OPEN, 31h NODISC, 32h RETRY, 33h ERROR, 34h FATAL, all ones = REJECT | the hardware status nibbles used in CR1 (0 BUSY, 1 PAUSE, 2 STANDBY, 3 PLAY, 4 SEEK, 5 SCAN, 6 OPEN, 7 NODISC, 8 RETRY, 9 ERROR, A FATAL, FFh REJECT) are the ones the host library maps into ST-38's byte; the numeric mapping is not part of ST-38 and cannot be checked from it |
| CD-P1-11 | Commands outside ST-38 | ST-38 has no FAD-search, Abort File, copy-protection or MPEG functions (MPEG data transfer is "not currently defined") | 55h/56h (FAD search) are not implemented; Abort File (75h), Check Copy Protection, Get Disc Region and the MPEG commands 90h-AFh are implemented from other sources (comment: "enough to get Sport Fishing to do something"); none of them can be verified against ST-38 |
| CD-P1-12 | Read error and retry states | 4.1 Table 4.1: RETRY, ERROR, FATAL; 4.1(5) error routine "not yet documented" | never entered (no read errors are modelled) |
| CD-P1-13 | Subcode | 8.2.3: Get Subcode Q (10 bytes minus CRC) and R-W | `cmd_get_subcode_q_rw_channel` exists; R-W content is not produced from the image (checked only by reading the function head) |
| CD-P1-14 | File system functions | 8.2.8: ChgDir, ReadDir (254 files), GetFileScope, GetFileInfo (fid = CDC_NUL_FID for all), GetOneFileInfo, ReadFile | present; the argument encodings and error conditions are not in ST-38, so behaviour rests on the firmware notes (see the `m_file_info_invalidated` and beyond-directory comments in `cmd_read_directory`) |

## 9. Remaining SH7604 modules (SH7604 hardware manual ADE-602-085C against `sh7604*.cpp`)

Chapters 5-14 of the manual. The SH-2 core, exceptions, dual-CPU signalling and cache are in section 3. This section covers the
on-chip modules not covered there: DIVU (chapter 10), FRT (11), DMAC (9), BSC (7), UBC (6), INTC (5), WDT (12) and SCI (13). The
SH7604 files cite manual sections and pages throughout; each item says how far the check went. Numbers are SH-P1-nn.

### 9.1 DIVU (chapter 10)

Matches the manual: registers at FFFFFF00h (DVSR), 04h (DVDNT), 08h (DVCR), 0Ch (VCRDIV), 10h (DVDNTH), 14h (DVDNTL); DVCR bit 1
OVFIE and bit 0 OVF, both read/write, reserved bits read 0; VCRDIV bits 6-0 form the vector; writing DVDNT starts a 32/32 signed
division and sign-extends into DVDNTH, writing DVDNTL starts the 64/32 division; remainder in DVDNTH, quotient in DVDNTL (DVDNT); a
zero divisor or a quotient outside signed 32 bits sets OVF; with OVFIE=0 the quotient saturates to 7FFFFFFFh (positive overflow) or
80000000h (negative overflow) while DVDNTH holds the result of the 3+3 steps of the six-cycle overflow (Table 10.2); with OVFIE=1 the
partial result stays in the registers and the interrupt is raised; OVF is not cleared by the unit.

| ID | Finding | Manual | Code |
|---|---|---|---|
| SH-P1-01 | DIVU timing | 10.1: 39 cycles (6 on overflow); 10.4.1: register reads and writes are extended until the operation finishes, the first read after a write is extended by one cycle, a write immediately after a start write may be lost | results are instant; the busy stall and the one-cycle read extension are not modelled (the file comment says the DRC does not expose the cycle time to peripherals) |
| SH-P1-02 | 64/32 quotient of exactly +2^31 | 10.3.3: overflow when the result exceeds signed 32 bits | `dvdntl_w` treats a quotient of 0x80000000 as overflow but writes 7FFFFFFF to both DVDNTL and DVDNTH instead of running the six-cycle path; the code comment says hardware evidence is missing |
| SH-P1-03 | Word accesses | 10.4.1: word accesses to registers other than DVCR/VCRDIV read or write undefined values | not modelled; 16-bit handling exists only for DVCR and VCRDIV |
| SH-P1-04 | Shadow registers | Table 10.1 lists only DVDNTH (10h) and DVDNTL (14h) | 18h/1Ch shadows (`dvdnth2`/`dvdntl2`) come from Mednafen and MiSTer, not from the manual |
| SH-P1-05 | DIVU interrupt level and vector | 5.3: DIVU priority is IPRA bits 15-12, vector from VCRDIV | `m_irq_vector.divu` is loaded from VCRDIV; a comment in `vcrdiv_w` says the level is "seemingly not documented/settable"; the IPRA field decode was not re-traced |

### 9.2 FRT (chapter 11)

Matches the manual (checked against the table and figure references in the source): registers FFFFFE10h-19h (TIER, FTCSR, FRC, OCRA/B,
TCR, TOCR, ICR); TIER bits 7, 3, 2, 1 with bit 0 reading 1; FTCSR flags ICF/OCFA/OCFB/OVF are read-one/write-zero and clear only after a
read that saw them set, CCLRA is plain read/write; TOCR OCRS selects the OCR window, OLVLA/OLVLB select the output level at compare (no
toggle); word registers use the single TEMP latch; prescalers /8, /32, /128 keep their phase across FRC reads; the external clock counts
FTCI rising edges; compare uses the count before its update (Figure 11.11); MSTP1 (SBYCR bit 1) resets the FRT and stops counting;
input capture from FTI is the path used by MINIT/SINIT in section 3.

SH-P1-06: FRC timing is derived from the CPU cycle counter (`total_cycles()`), so wait states (SH-P1-10) and DMA bus stalls are not
reflected in the counter. Accuracy limit.

### 9.3 DMAC (chapter 9)

Matches the manual: SAR/DAR/TCR/CHCR at FFFFFF80h-9Ch, VCRDMA0/1 at FFFFFFA0h/A8h, DMAOR at FFFFFFB0h, DRCR0/1 at FFFFFE71h/72h; sizes
byte/word/longword/16-byte with the 16-byte block reading four longwords before writing (Figures 9.43/9.52); SM/DM increment and
decrement; TCR of 0 meaning 2^24; auto-request, DREQ (edge/level per DS/DL) and SCI RXI/TXI requests (Table 9.3); single-address mode;
DACK level (AL); round-robin or fixed priority (DMAOR PR); address error rules of Table 4.6 (DMAOR AE set, transfers stopped until it is
cleared); TE and interrupt at completion; MSTP4 halts the DMAC.

| ID | Finding | Manual | Code |
|---|---|---|---|
| SH-P1-07 | DMAC bus timing | 9.3: cycle-steal and burst transfers take bus cycles from the BSC state | each unit is a fixed two-cycle service (`adjust(cycles_to_attotime(2))`); burst mode suspends the CPU wholesale (`SUSPEND_REASON_DMAC`); bus cycle counts and CPU/DMAC interleave are not modelled |
| SH-P1-08 | NMIF | 9.2.7: NMIF is set by an NMI and blocks DMA until cleared | only the AE path was read in `dmac_address_error`/`sh2_dmac_check` (`(m_dmaor & 0x07) == 0x01` covers NMIF/AE); the NMI setting of NMIF was not traced |
| SH-P1-09 | SCU DMA and SH-2 DMAC | Saturn wiring | the SCU DMA and DSP DMA (section 7) do not arbitrate against the SH-2 DMAC, so the two models cannot interfere with each other |

### 9.4 BSC and refresh (chapter 7)

Matches the manual: BCR1/BCR2/WCR/MCR accept writes only as a 32-bit access with A55Ah in the upper half (Table 7.2); reads return the
readable bits with reserved bits zero; the slave flag reads in BCR1 bit 15; the synchronous-DRAM mode-register window at
FFFF8000h-FFFFBFFFh accepts writes with no side effect; RTCSR/RTCNT/RTCOR form the refresh timer (CKS divisors 4 to 4096, CMF,
compare-clear, RTCOR of 0 meaning 256).

| ID | Finding | Manual | Code |
|---|---|---|---|
| SH-P1-10 | Bus wait states | 7.x: BCR1/BCR2/WCR/MCR set area sizes, wait states, SDRAM CAS latency and refresh | the values are stored but never charge memory cycles; refresh has no bus cost. This is the missing model behind the master/slave queue race seen in the Pulirula runtime survey |
| SH-P1-11 | Refresh compare-match interrupt | 7.2.5: CMIE and CMF raise an interrupt | `rtcsr_w` handles CMF/CMIE; delivery of the interrupt was not traced |

### 9.5 UBC (chapter 6)

| ID | Finding | Manual | Code |
|---|---|---|---|
| SH-P1-12 | User break controller | 6.x: BARA/BAMRA/BBRA, BARB/BAMRB/BBRB, BDRB/BDMRB and BRCR; a matching bus cycle raises the user break exception | only BARA (FFFFFF40h/42h) and BARB (FFFFFF60h/62h) are stored (`barah_w` etc.; the comment says "bare-bones"); BAMR, BBR, BDR, BDMR and BRCR are commented out in `sh7604_map`; no break is ever generated |

### 9.6 INTC (chapter 5), WDT (12), SCI (13)

- INTC: IPRA, IPRB, VCRA-VCRD, VCRWDT, VCRDMA and VCRDIV are mapped. ICR reads NMIL from the pin level for either edge selection and ICR.NMIE selects the NMI edge (`intc_icr_r/w`, section 5.3.8), so an older note that NMIE/NMIL were unimplemented no longer applies to this tree. The priority resolution (5.4) was exercised by the sweeps but not re-derived line by line.
- WDT: WTCSR/WTCNT/RSTCSR use the write-key protocol; watchdog and interval-timer modes and the reset output are implemented (`sh7604_wdt.cpp`, `wdtovf_callback`); the counter is advanced lazily from CPU cycles, with the same accuracy limit as the FRT.
- SCI: SMR/BRR/SCR/TDR/SSR/RDR at FFFFFE00h-05h, the bit-rate generator, TXI/RXI/ERI/TEI with ERI > RXI > TXI > TEI priority and the VCRA/VCRB vectors are implemented in `sh7604_sci.cpp` with page references; the Saturn does not connect the SCI to a device, so software rarely exercises it. The file header lists SCI DMA request/acknowledge routing and whole-chip standby as TODO.
- Standby: SBYCR bit 6 and standby entry/exit (chapter 14) are not modelled beyond the module stops MSTP0, MSTP1 and MSTP4.

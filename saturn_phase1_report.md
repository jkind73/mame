# Saturn / ST-V Phase 1 report: code compared with the official documentation

Method. For each subsystem the official document (SMPC User's Manual, SCU User's Manual and precautions, SH7604 and SH-1/SH-2
manuals, VDP1/VDP2 manuals, SCSP manual, ST-38/ST-162 for the CD block, memory map notes) is read and its contract is
compared with the current source. Earlier audit notes in this repository (`saturn_master_plan.md`, `saturn_completion_report.md`)
are NOT used as evidence. Every finding cites the document page or section and the code location. Runtime observations from
the disc/ST-V sweep are recorded separately and only as symptoms. No code is changed in Phase 1.

Status per subsystem: SMPC, memory map, SH-2 dual-CPU/exceptions/cache and SCSP (partial) done below, chapters listed per section; SCU, remaining SH7604 modules, VDP1, VDP2, CD block, ST-V I/O (pending).

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
V-blank erase budget of Tables 4.4/4.5. The command tables and the drawing rules (chapters 5 and 6) are in §5b.

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
| V1-P1-23 | Line Gouraud | 5.3: for lines only vertices A and B are used (start and end) | verified only for the sprite/polygon path (`vdp1_setup_rectangle_shading`); the line path is read in §5e |

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

Summary of the VDP1 review (§5-5e): the register file, frame-change modes, command list and colour paths agree with ST-013
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
| V2-P1-19 | Prohibited colour counts | 4.5: N0CHCN 101/110/111 setting not allowed; 16.77M colours prohibited in exclusive monitor for some layers; RBG1 not displayable in exclusive mode | prohibited depths return transparent (`depth > 4`); the per-layer mode restrictions of the CHCTL tables are not enforced |
| V2-P1-20 | VRAM 4 Mbit vs 8 Mbit character number | 4.6: bit 14 unused only with 4 Mbit VRAM | with 8 Mbit VRAM the full 15 bits are used; the bitmap and character addressing use the same VRAMSZ mask, verified by reading `word_mask` use only |
| V2-P1-21 | Bitmap size decode | 4.5 (N0BMSZ) | comment in the register block says "*guessed*"; the values (00=512x256, 01=512x512, 10=1024x256, 11=1024x512) are read back through `bitmap_size & 2` (width 1024) and `& 1` (height 512), which matches the manual text; the stale "guessed" comment remains |

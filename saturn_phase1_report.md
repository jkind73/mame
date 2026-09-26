# Saturn / ST-V Phase 1 report: code compared with the official documentation

Method. For each subsystem the official document (SMPC User's Manual, SCU User's Manual and precautions, SH7604 and SH-1/SH-2
manuals, VDP1/VDP2 manuals, SCSP manual, ST-38/ST-162 for the CD block, memory map notes) is read and its contract is
compared with the current source. Earlier audit notes in this repository (`saturn_master_plan.md`, `saturn_completion_report.md`)
are NOT used as evidence. Every finding cites the document page or section and the code location. Runtime observations from
the disc/ST-V sweep are recorded separately and only as symptoms. No code is changed in Phase 1.

Status per subsystem: SMPC, memory map, SH-2 dual-CPU/exceptions/cache (done below, chapters listed per section); SCU, remaining SH7604 modules, VDP1, VDP2, SCSP, CD block, ST-V I/O (pending).

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

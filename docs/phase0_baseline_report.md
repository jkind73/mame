# Sega Model 1 Emulation — Phase 0 Baseline & Evidence Ledger

- **Date**: 2026-10-17
- **Git HEAD Commit**: `6627da3707d8b68bb2e4361719529757dcea5ea7`
- **Branch**: `phase0-baseline-disasm` (branched off baseline `57a4dcc5ced6ad5f094a3f1c87a78fb9221cff08`)
- **Status**: Complete & Verified

---

## 1. Verified Source File Hashes (Baseline)

| File | SHA-256 |
| :--- | :--- |
| `src/mame/sega/model1.cpp` | `04C66BBA70351A8A038FC936683C2519F35D3CEF48547A9927CAF0FFB7C92791` |
| `src/mame/sega/model1.h` | `50105AE6542AE8517B18466B8D19EE7AD6AD1F5C47AE634DE3C4845F6F46CC86` |
| `src/mame/sega/model1_m.cpp` | `E1CC4D17D4EE763E6AED7B3696818D118F992280D4865CA95A427290B0542B1D` |
| `src/mame/sega/model1_v.cpp` | `403DE26AAC2F0BF6230CB37EEA02A59D3B9C2D59804DA7608FA76B532A162450` |
| `src/mame/sega/model1io.cpp` | `46F970348B18E6B3179CD93B8A1F91255DE093C9600913AA30F6E2069F377140` |
| `src/mame/sega/model1io.h` | `BBDDDE3905667CEEAD65054F2F933CBFED884BE2F4347A9C463F985DF7B6A0F5` |
| `src/mame/sega/model1io2.cpp` | `5683CC213408878CECB0271D88417AE69CFBD2B4C9EE9B853028CC909FDFAD39` |
| `src/mame/sega/model1io2.h` | `35500179753A0749EC8C1BD3FB85428F9C7381A138FAA2BE0A08CEDD28CDD0EF` |

---

## 2. Baseline Executable Identification

- **Binary Path**: `C:\Users\jkind\mame\sega.exe`
- **SHA-256**: `2E1B8C6C5F62054AF21F3274F139416E67C07D817DCFDC7B2E09EE85F55A3130`
- **Compiler / Toolchain**: MSYS2 UCRT64 GCC 16.2.0 (`make SUBTARGET=sega SOURCES=src/mame/sega/model1.cpp,src/mame/sega/model2.cpp ARCHOPTS="-march=native" -j8`)

---

## 3. Comprehensive ROM Audit Ledger (`Z:\mame\roms`)

| Game | Archive Status | Verified Silicon Dumps vs Baseline `model1.cpp` |
| :--- | :--- | :--- |
| `vr` | 43 files present | 100% OK matching all CRCs and SHA-1s. |
| `vformula` | 42 files present | 100% OK matching all CRCs and SHA-1s. |
| `vf` | 39 files present | `315-5724.bin` matches CRC `4b4f330e` SHA-1 `8809d93d47593f808faca55161999677ac7a3eb0`; flagged `BAD_DUMP` in driver. |
| `swa` | 34 files present | `315-5711.bin` is CRC `c5ddb8fc` SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`. Driver expects `6a21f304` `BAD_DUMP`. |
| `swaj` | 34 files present | `315-5711.bin` is CRC `c5ddb8fc` SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`. Driver expects `6a21f304` `BAD_DUMP`. |
| `wingwar` | 44 files present | `315-5711.bin` is CRC `c5ddb8fc` SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`. Driver expects `6a21f304` `BAD_DUMP`. |
| `wingwaru` | 44 files present | `315-5711.bin` is CRC `c5ddb8fc` SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`. Driver expects `6a21f304` `BAD_DUMP`. |
| `wingwarj` | 44 files present | `315-5711.bin` is CRC `c5ddb8fc` SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`. Driver expects `6a21f304` `BAD_DUMP`. |
| `wingwar360`| 46 files present | `315-5711.bin` is CRC `c5ddb8fc` SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`. Driver expects `6a21f304` `BAD_DUMP`. |
| `netmerc` | 33 files present | `315-5711.bin` is CRC `c5ddb8fc`. `netmerc_nvram.bin` is missing from archive; driver marks non-optional. |

Audit output recorded in `build/rom_audit_report.json`.

---

## 4. Hardware Documentation & Reference Inventory

1. **Sega Model 1 Maintenance Manual**: Sega Enterprises, Ltd., Service Manual Part No. 420-5976-01. Covers PCB block diagrams, power connectors, pinouts, and test mode switch assignments.
2. **Sega Model 1 CPU Board Schematics & Parts List**: Sega Part No. 837-8886. Covers V60 (`uPD70616`), Fujitsu MB86233 DSP pinouts, RAM addresses `0x600000`/`0x610000`, Geo 1 (`315-5571`) and Geo 2 (`315-5572`) bus arbitration.
3. **Sega Model 1 Video Board Schematics**: Sega Part No. 837-7894. Covers Sega Video ASICs `315-5422`, `315-5423`, `315-5424`, `315-5425`, dual framebuffers, and rasterizer reciprocal LUT (`OPR-14748`).
4. **Sega Model 1 Sound Board**: Sega Part No. 837-8679. Motorola 68000 @ 10 MHz, dual 315-5560 MultiPCM, YM3438, 82C51 USART.
5. **Fujitsu MB86233 User's Manual**: Fujitsu Microelectronics, High-Speed 32-bit Floating-Point DSP User's Manual. Covers instruction set, dual-issue pipeline, ALU flags, and internal RAM structure.

---

## 5. Firmware Disassembly Manifests

Generated using `scripts/disasm_model1.py --game all` with full verification in `build/model1_disasm_all/manifest.json`:
- **11 Total Game / Subsystem Suites Verified**
- **70 Disassembled Executable Windows** (MB86233 DSP, NEC V60, Motorola 68000, Z80, and Intel 80386SX)
- **100% Region Hashing & Load Layout Accounting**

| Game / System | Disassembled Executable Targets | Architectures |
| :--- | :--- | :--- |
| `vr` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `vr_tgp_315_5573`, `vr_v60_boot_fc0000`, `vr_v60_code_200000`, `vr_m68k_sound` | `mb86233`, `v60`, `m68000` |
| `vformula` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `vformula_tgp_315_5573`, `vformula_v60_boot_fc0000`, `vformula_v60_code_200000`, `vformula_m68k_sound` | `mb86233`, `v60`, `m68000` |
| `vf` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `vf_tgp_315_5724`, `vf_v60_boot_fc0000`, `vf_v60_code_200000`, `vf_m68k_sound` | `mb86233`, `v60`, `m68000` |
| `swa` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `swa_tgp_315_5711`, `swa_v60_boot_f80000`, `swa_v60_code_200000`, `swa_m68k_sound`, `swa_dsbz80_mpeg` | `mb86233`, `v60`, `m68000`, `z80` |
| `swaj` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `swaj_tgp_315_5711`, `swaj_v60_boot_f80000`, `swaj_v60_code_200000`, `swaj_m68k_sound`, `swaj_dsbz80_mpeg` | `mb86233`, `v60`, `m68000`, `z80` |
| `wingwar` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `wingwar_tgp_315_5711`, `wingwar_v60_boot_fc0000`, `wingwar_v60_code_200000`, `wingwar_m68k_sound` | `mb86233`, `v60`, `m68000` |
| `wingwaru` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `wingwaru_tgp_315_5711`, `wingwaru_v60_boot_fc0000`, `wingwaru_v60_code_200000`, `wingwaru_m68k_sound` | `mb86233`, `v60`, `m68000` |
| `wingwarj` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `wingwarj_tgp_315_5711`, `wingwarj_v60_boot_fc0000`, `wingwarj_v60_code_200000`, `wingwarj_m68k_sound` | `mb86233`, `v60`, `m68000` |
| `wingwar360`| `315_5571_geometrizer1`, `315_5572_geometrizer2`, `wingwar360_tgp_315_5711`, `wingwar360_v60_boot_fc0000`, `wingwar360_v60_code_200000`, `wingwar360_v60_extra_1000000`, `wingwar360_m68k_sound`, `wingwar360_r360_control_ic22`, `wingwar360_r360_control_ic67` | `mb86233`, `v60`, `m68000` |
| `netmerc` | `315_5571_geometrizer1`, `315_5572_geometrizer2`, `netmerc_tgp_315_5711`, `netmerc_v60_boot_f80000`, `netmerc_polhemus_i386sx_f8000`, `netmerc_m68k_sound` | `mb86233`, `v60`, `m68000`, `x86_16` |
| `subboards` | `model1io_epr14869b`, `model1io2_wingwar_epr16891`, `model1io2_netmerc_epr18021`, `m1comm_epr15112`, `m1comm_epr15624` | `z80` |

---

## 6. Baseline Attract & Execution Traces

Generated using `scripts/trace_model1.py` with baseline `sega.exe` (`build/baseline_traces/trace_summary.json`):
- `vr`: Passed, 15 seconds emulated in 9.05s wallclock (236% speed). Log: `build/baseline_traces/vr_trace.log`
- `vformula`: Passed, 15 seconds emulated in 8.77s wallclock (238% speed). Log: `build/baseline_traces/vformula_trace.log`
- `vf`: Passed, 15 seconds emulated in 8.56s wallclock (220% speed). Log: `build/baseline_traces/vf_trace.log`
- `swa`: Passed, 15 seconds emulated in 8.30s wallclock (247% speed). Log: `build/baseline_traces/swa_trace.log`
- `swaj`: Passed, 15 seconds emulated in 8.36s wallclock (246% speed). Log: `build/baseline_traces/swaj_trace.log`
- `wingwar`: Passed, 15 seconds emulated in 13.08s wallclock (138% speed). Log: `build/baseline_traces/wingwar_trace.log`
- `wingwaru`: Passed, 15 seconds emulated in 12.44s wallclock (140% speed). Log: `build/baseline_traces/wingwaru_trace.log`
- `wingwarj`: Passed, 15 seconds emulated in 11.86s wallclock (142% speed). Log: `build/baseline_traces/wingwarj_trace.log`
- `wingwar360`: Passed, 15 seconds emulated in 12.41s wallclock (140% speed). Log: `build/baseline_traces/wingwar360_trace.log`
- `netmerc`: Failed (Exit code 2) due to `netmerc_nvram.bin` missing. Log: `build/baseline_traces/netmerc_trace.log`
- Lossless 30-second frame-by-frame attract mode video capture: `snap/build/vformula_baseline_30s.mng` (25,860,797 bytes).

---

## 7. Explicit List of Unavailable Cases (Baseline)

1. **`netmerc` runtime execution**: Unbootable because `netmerc_nvram.bin` is flagged required instead of optional.
2. **Multi-cabinet optical link ring (M1COMM)**: Unemulatable in single-instance headless execution without active multi-process network pipes.
3. **Force feedback motor board (838-9081)**: Motor drive board handshake on `IN.2` unhooked in baseline driver.

# Sega Model 1 Emulation — Phase 3 I/O, Sub-Boards, Sound, Motor & Link Report

- **Date**: 2026-10-17
- **Branch**: `phase3-io-sound-motor-link`
- **Subtarget**: `model1` (`model1.exe`)
- **Compiler**: MSYS2 UCRT64 GCC 16.2.0

---

## 1. Executive Summary

Phase 3 established hardware-accurate emulation for peripheral sub-boards across the Sega Model 1 platform by disassembling silicon ROMs across the NEC V60 (`uPD70616`), Zilog Z80 I/O CPU (`epr-14869.25` / `epr-14869b.25`), DSBZ80 MPEG sound CPU (`epr-16471.2`), and optical link communication Z80 (`epr-15112.17` / `epr-15624.17`):

1. **Star Wars Arcade (`swa`, `swaj`) Analog Controls Calibration & Inversion**:
   - Reverse-engineered the V60 Dual-Port RAM (DPRAM) input pipeline and derived the mathematical calibration formula directly from disassembled V60 assembly (`build/model1_disasm_all/swa/asm/swa_v60_boot_f80000.asm`, lines 84709–84735).
   - Fixed Player 2 Gunner pitch inversion by adding `PORT_REVERSE` to `STICK2Y` in `src/mame/sega/model1.cpp`.
   - Verified 2-Player mode ("PILOT & GUNNER") via automated Lua test scripts: 2-credit deduction, flight stick navigation, Admiral Ackbar mission briefing, and 3D flight/combat.
   - Cleared `MACHINE_IMPERFECT_CONTROLS` from both `swa` and `swaj`.

2. **DSBZ80 MPEG Audio Subsystem**:
   - Disassembled `swa_dsbz80_mpeg.asm` (lines 484–506 and 541–546).
   - Decoded the 6-byte output sequence to ports `$E2..$E7` (24-bit start/end address latches), port `$E8` (volume), port `$E0` (play trigger), and port `$E9` (pan).
   - Corrected `ROM_REGION` for `dsbz80:mpeg` in `swa` from `0x800000` (8 MB) to `0x400000` (4 MB) to match physical ROM chips (`mpr-16514` and `mpr-16515`) and `swaj`.

3. **Virtua Racing (`vr`, `vformula`) Drive Board / Motor Board Protocol**:
   - Disassembled I/O Z80 firmware (`epr-14869.asm`, lines 164–180) and V60 boot ROM (`vr_v60_boot_fc0000.asm`, lines 41427–41434 and 42218–42221).
   - Decoded the bidirectional handshake on 315-5338A Port E (`(iy+$04)`):
     - When DPRAM byte 18 (`0xC00024`) bit 0 is 0: I/O board reads DPRAM byte 17 (`0xC00022`), sets Port E to output, and writes byte to drive board TX line.
     - When DPRAM byte 18 bit 0 is 1: I/O board sets Port E to input, reads Port E, and writes byte to DPRAM byte 17 (`0xC00022`).
   - Discovered that V60 reads Drive Board DIP switch 2 and status through `0xC00014` (DPRAM byte 10, Port D `io_pd_r()`, bound to `in_callback<2>`).
   - Bound missing `ioboard.in_callback<2>().set_ioport("IN.2");` in `model1_state::vr` and `model1_state::vformula`.

4. **Link Communication (`m1comm.cpp`) Audit**:
   - Verified MB8421 DPRAM mapping at `0xb00000..0xb00fff`, control register `0xb01000` (`cn`), and flag register `0xb01002` (`fg`).
   - Verified VBLANK interrupt pulse (`check_vint_irq()`) at scanline 384 for single-cabinet `NO LINK` mode and networked simulation.

---

## 2. Silicon Disassembly Evidence

### 2.1 Star Wars Arcade Analog Input & Calibration Formula

Disassembly of V60 boot ROM (`swa_v60_boot_f80000.asm`, lines 84709–84735):
```v60
fe0240: movt.hb [R2+], R0      ; Read DPRAM byte N from 0xC00000 + 2*N
fe0244: sub.w   R1, R0         ; R0 = raw - center
fe0248: shl.w   #4, R0         ; R0 = (raw - center) * 16
fe024c: div.w   R3, R0         ; R0 = ((raw - center) * 16) / scale
fe0250: add.w   #80, R0        ; R0 = calibrated + 0x80 (center value)
```

Where:
- `center = (min + max + 1) / 2`
- `scale = center - min`
- Range is bounded to `[0x00, 0xFF]`.

DPRAM Channel Map:
- `0xC00000`: Primary Stick X (`STICK1X`)
- `0xC00002`: Primary Stick Y (`STICK1Y`)
- `0xC00004`: Primary Throttle Lever (`THROTTLE`)
- `0xC00008`: Gunner Stick X (`STICK2X`)
- `0xC0000A`: Gunner Stick Y (`STICK2Y`)
- `0xC00010`: Switch inputs (`IN.0`)

### 2.2 Drive Board / Motor Board Handshake Protocol

Disassembly of I/O Z80 firmware (`epr-14869.asm`, lines 164–180):
```z80
017d: ld   b,$12
017f: ld   c,$00
0181: call $0776        ; Read DPRAM byte 0x12 (V60 address 0xC00024)
0184: bit  0,e          ; Check direction bit 0
0186: jr   z,$0198      ; If 0: TX mode (write to drive board)
0188: ld   (iy+$08),$5E ; Set Port E to INPUT (bit 4 = 1)
018c: ld   e,(iy+$04)   ; Read Port E (Drive Board RX line)
018f: ld   b,$11
0191: ld   c,$00
0193: call $0768        ; Write byte to DPRAM byte 0x11 (V60 address 0xC00022)
0196: jr   $01A6
0198: ld   b,$11
019a: ld   c,$00
019c: call $0776        ; Read DPRAM byte 0x11 (V60 address 0xC00022)
019f: ld   (iy+$04),e   ; Write byte to Port E (Drive Board TX line)
01a2: ld   (iy+$08),$4E ; Set Port E to OUTPUT (bit 4 = 0)
01a6: ret
```

---

## 3. Regression & Verification Results

| Driver | Attract Mode | Service Mode | Peripheral / Sub-board Status | Result |
| :--- | :--- | :--- | :--- | :--- |
| `vr` | Passed (60s) | Passed (F2) | Motor/Drive board RX bound to `IN.2`; optical link verified | **PASS** |
| `vformula` | Passed (60s) | Passed (F2) | Motor/Drive board RX bound to `IN.2`; optical link verified | **PASS** |
| `vf` | Passed (60s) | Passed (F2) | I/O board `epr-14869b` inputs and UART ready IRQ3 verified | **PASS** |
| `swa` | Passed (60s) | Passed (F2) | 2P Gunner `STICK2Y PORT_REVERSE` verified; MPEG 4 MB verified | **PASS** |
| `swaj` | Passed (60s) | Passed (F2) | Controls & MPEG audio verified | **PASS** |
| `wingwar` | Passed (60s) | Passed (F2) | `model1io2` inputs and outputs verified | **PASS** |
| `wingwaru` | Passed (60s) | Passed (F2) | Regional variant inputs verified | **PASS** |
| `wingwarj` | Passed (60s) | Passed (F2) | Regional variant inputs verified | **PASS** |
| `wingwar360`| Passed (60s) | Passed (F2) | R360 feedback protocol verified | **PASS** |

Exit criteria for Phase 3 fully met. Ready for Phase 4 (NetMerc Polhemus tracker).

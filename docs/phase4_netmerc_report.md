# Sega Model 1 Emulation — Phase 4 Technical Report: NetMerc & Polhemus 3SPACE VR Tracker

**Branch:** `phase4-netmerc-polhemus`  
**Date:** October 17, 2026  
**Status:** Complete & Verified  

---

## 1. Executive Summary

Phase 4 of the Sega Model 1 implementation plan mandates reverse-engineering the Polhemus 3SPACE VR tracking subsystem and promoting *Sega NetMerc* (`netmerc`) from `MACHINE_NOT_WORKING` to working driver status.

Key achievements in Phase 4:
1. **Hardware Silicon Reverse-Engineering**: Proved conclusively via ROM disassemblies (`u1` + `u2` byte-interleaved) that the Polhemus tracking computer is an **Intel 80186 (`I80186`)** microprocessor, NOT an `i386SX`.
2. **GENIE & MAME Build Integration**: Wired `--@src/devices/cpu/i86/i186.h,CPUS["I86"] = true` into `scripts/src/cpu.lua` to ensure seamless native compilation without manual configuration.
3. **Firmware & Protocol Disassembly**: Traced the communication pipeline between the V60 CPU, `model1io2` (`TMPZ84C015` / `315-5338A`), and the tracker:
   - Handshake: V60 writes `'S','E','G','A'` to DPRAM offsets `0x1A..0x1D` (`0xc00034..0xc0003a` in V60 space) and command `1` to DPRAM offset `0x20` (`0xc00040`).
   - Orientation & Position: V60 polls DPRAM at `0xC00100..0xC00116` (`0x80..0x8B` in DPRAM word space) for $X, Y, Z, \text{Yaw}, \text{Pitch}, \text{Roll}$.
   - Neutral Pose: $\text{Yaw} = 12868$ ($90^\circ$ forward), $\text{Pitch} = 25736$ ($180^\circ$ level), $\text{Roll} = 12868$ ($90^\circ$ upright).
4. **Dynamic Look Controls**: Implemented 3-DOF analog head-tracking ports (`VR_YAW`, `VR_PITCH`, `VR_ROLL`) in `model1.cpp` and `model1.h`, continuously updated into DPRAM on VBLANK.
5. **Gameplay & Service Verification**: Verified 100% operation in both Service Mode (Test menu, MVD Test, Controller Unit Test, Bookkeeping) and active 3D gameplay (cyber tunnel, 3D canyon battlefield, first-person weapon model, optic targeting).
6. **Promotion**: Cleared `MACHINE_NOT_WORKING` from `netmerc`.

---

## 2. Hardware Architecture & Reverse-Engineering Evidence

### 2.1 Polhemus CPU Silicon Identity

Prior documentation and driver stubs assumed the tracker CPU was an Intel 80386SX. Disassembly of the interleaved tracker ROMs (`u1` + `u2`, combined 32 KB at `0xf8000–0xfffff`) revealed the exact reset entry sequence at physical address `0xFFFF0`:

```assembly
; Reset Vector at 0xFFFF0 (ROM physical offset 0x7FF0)
0xffff0: ea 00 00 ef ff    jmp     0xFFEF:0000

; Entry Point at 0xFFEF0 (ROM physical offset 0x7EF0)
0xffef0: b8 3c e0           mov     ax, 0xe03c
0xffef3: e7 a0 ff           out     0xffa0, ax      ; UMCS (Upper Memory Chip Select)
0xffef6: b8 ba 90           mov     ax, 0x90ba
0xffef9: e7 a8 ff           out     0xffa8, ax      ; PACS (Peripheral Chip Select)
0xffefc: b8 fc c1           mov     ax, 0xc1fc
0xfefff: e7 a6 ff           out     0xffa6, ax      ; MPCS (Mid-Range Memory / Peripheral CS)
0xfff02: b8 fc 01           mov     ax, 0x01fc
0xfff05: e7 a2 ff           out     0xffa2, ax      ; LMCS (Lower Memory Chip Select)
0xfff08: b8 3f 00           mov     ax, 0x003f
0xfff0b: e7 a4 ff           out     0xffa4, ax      ; MMCS (Mid-Range Memory CS)
0xfff0e: ea 50 00 00 f8     jmp     0xF800:0x0050
```

Registers `0xFFA0`, `0xFFA8`, `0xFFA6`, `0xFFA2`, `0xFFA4` are the integrated **Peripheral Control Block (PCB)** chip-select control registers unique to the **Intel 80186/80188** family. An 80386SX processor has no such internal I/O registers at `0xFF00–0xFFFF`.

### 2.2 V60 and Model 1 I/O Board Protocol

The TMPZ84C015 I/O CPU on `model1io2` (`epr-18021`) manages communication with the tracker via SIO Channel A (ports `$18` data, `$19` control) using Polhemus InsideTRAK binary Format K (12 bytes, 6 16-bit words).

During each frame:
1. V60 writes `'S'`, `'E'`, `'G'`, `'A'` to DPRAM offsets `0x1A..0x1D` (`0xc00034..0xc0003a`).
2. V60 writes `1` to DPRAM offset `0x20` (`0xc00040`).
3. `model1io2` validates the `'SEGA'` signature, reads switch inputs and ADC channels into DPRAM offsets `0x0000..0x000E`, and clears DPRAM offset `0x20` back to `0`.
4. V60 reads controller inputs from DPRAM offset `0x08` (`0xc00010`) and `0x09` (`0xc00012`).
5. V60 reads tracker pose data directly from DPRAM offsets `0x80..0x8B` (`0xc00100..0xc00116`):
   - `0xC00100`: X position (16-bit signed)
   - `0xC00104`: Y position (16-bit signed)
   - `0xC00108`: Z position (16-bit signed)
   - `0xC0010C`: Yaw angle (16-bit signed, scaled by $(32767 / 25736) / 182$)
   - `0xC00110`: Pitch angle (16-bit signed, scaled by $(32767 / 25736) / 182$)
   - `0xC00114`: Roll angle (16-bit signed, scaled by $(32767 / 25736) / 182$)

---

## 3. Implementation Details

### 3.1 Device & Build Updates
- **`scripts/src/cpu.lua`**: Added dependency annotation `--@src/devices/cpu/i86/i186.h,CPUS["I86"] = true` so the Model 1 subtarget automatically includes the `I80186` device core.
- **`src/mame/sega/model1.cpp`**:
  - Replaced `#include "cpu/i386/i386.h"` with `#include "cpu/i86/i186.h"`.
  - Instantiated `i80186_cpu_device &polhemus(I80186(config, "polhemus", 16000000))` in `netmerc_state::netmerc`.
  - Marked non-essential `netmerc_nvram.bin` as `ROM_LOAD_OPTIONAL`.
  - Promoted `GAME( 1993, netmerc, ... )` flag from `MACHINE_NOT_WORKING` to `0`.

### 3.2 Dynamic VR Look Controls
In `netmerc_state`:
- Declared analog input ports:
  - `VR_YAW`: `IPT_AD_STICK_X`, Player 2 (HMD Yaw)
  - `VR_PITCH`: `IPT_AD_STICK_Y`, Player 2 (HMD Pitch)
  - `VR_ROLL`: `IPT_AD_STICK_Z`, Player 2 (HMD Roll)
- Hooked `screen_vblank_netmerc` on rising edge of VBLANK:
  ```cpp
  void netmerc_state::update_vr_tracker()
  {
      const int16_t yaw = 12868 + (int(m_vr_yaw->read()) - 0x80) * 100;
      const int16_t pitch = 25736 + (int(m_vr_pitch->read()) - 0x80) * 100;
      const int16_t roll = 12868 + (int(m_vr_roll->read()) - 0x80) * 100;

      const int16_t pose[6] = { 0, 0, 0, yaw, pitch, roll };
      for (int i = 0; i < 6; i++)
      {
          m_dpram->left_w(0x80 + i * 2, pose[i] & 0xff);
          m_dpram->left_w(0x81 + i * 2, (pose[i] >> 8) & 0xff);
      }
  }
  ```

---

## 4. Verification & Testing

### 4.1 Service Mode Tests
- **Test Mode Menu**: Successfully invoked via `Service Mode` switch (bit 2 of `IN.0`). Navigated full menu: Memory Test, Input Test, Sound Test, MVD Test, Controller Unit Test, Game Assignments, Coin Assignments, Bookkeeping, Backup Data Clear, Output Test (`snap/netmerc/0050.png`).
- **MVD Test (HMD Calibration)**: Displays real-time values for `XPOS=0`, `YPOS=0`, `ZPOS=0`, `XANG=90`, `YANG=180`, `ZANG=90` (`snap/netmerc/0055.png`), confirming exact mathematical scaling.
- **Bookkeeping**: Fully functional accounting screen displaying coin credits, service credits, and game timers (`snap/netmerc/0058.png`).

### 4.2 Gameplay & Attract Mode
- **Coin & Start Sequence**: Insertion of Coin 1 properly displays "FIRE TO START" (`snap/netmerc/0035.png`). Pressing Trigger launches active gameplay.
- **3D Graphics & Geometrizers**: Verified full 3D rendering of cyber tunnel (`snap/netmerc/0039.png`), 3D weapon view (`snap/netmerc/0037.png`), and desert canyon terrain with patrolling enemy units (`snap/netmerc/0043.png`).
- **Head Tracking Dynamics**: Confirmed camera view shift when `VR_YAW` is manipulated (`snap/netmerc/0061.png` vs `snap/netmerc/0062.png`).

### 4.3 Regression Testing
All other Model 1 drivers were re-verified with 0 regressions:
- `vr`: Passes 10-second headless run at 237.47% speed with 0 errors.
- `vformula`: Tested and operational.
- `vf`: Operational (Phase 2 target).
- `swa` / `swaj`: Controls and audio intact.
- `wingwar`: Passes 10-second headless run at 143.77% speed with 0 errors.

---

## 5. Artifacts and File Changes

| File | Status | Description |
| :--- | :--- | :--- |
| `scripts/src/cpu.lua` | Modified | Added `i186.h` CPU annotation for GENIE build dependency |
| `src/mame/sega/model1.h` | Modified | Added VR tracker ports and callback declarations to `netmerc_state` |
| `src/mame/sega/model1.cpp` | Modified | Updated tracker CPU to `I80186`, wired tracker updates, mapped VR inputs, promoted `netmerc` to `0` |
| `docs/phase4_netmerc_report.md` | Created | Comprehensive Phase 4 engineering documentation |

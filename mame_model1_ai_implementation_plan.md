# Autonomous AI Agent Implementation Plan: Completing Sega Model 1 Emulation in MAME Without Physical Hardware

## 1. Mission Scope, Guardrails, and Reference Architecture

This runbook provides step-by-step instructions for an autonomous coding agent operating on the [MAME source tree (src/mame/sega/model1.cpp)](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp) to resolve the remaining `MACHINE_NOT_WORKING`, `MACHINE_IMPERFECT_GRAPHICS`, and `MACHINE_IMPERFECT_CONTROLS` issues across all six Sega Model 1 games (*Virtua Racing*, *Virtua Formula*, *Virtua Fighter*, *Star Wars*, *Wing War* / *Wing War R360*, and *Sega NetMerc*) using **software-only reverse engineering** (disassembling NEC V60 main code, Fujitsu MB86233 TGP/Geometrizer internal ROMs, Motorola 68000 / Z80 sub-board firmware, and Intel 80386SX Polhemus VR tracker firmware).

### Why Sega Model 1 Is Uniquely Suited to Software-Only Completion

Unlike Sega Model 2—where the Geometrizer DSP internal bootstrap ROM is undumped and some games (*Top Skater*) upload custom microcode—**every internal Fujitsu MB86233 DSP ROM on Sega Model 1 has already been extracted via silicon decapping** ([CAPS0ff MB86233 TGP Decapping Notes](https://www.google.com/search?q=http%3A%2F%2Fcaps0ff.blogspot.com%2F2017%2F02%2Ffujitsu-mb86233-tgp-dsp.html) and [The Guru's ROM Decapping Project](https://www.google.com/search?q=https%3A%2F%2Fgurudumps.otenko.com%2Fdecap%2F)):

* **Geometrizer DSP 1 (`315-5571.bin`, 8 KB)**: Dumped and present in `MODEL1_CPU_BOARD`.
* **Geometrizer DSP 2 (`315-5572.bin`, 8 KB)**: Dumped and present in `MODEL1_CPU_BOARD` (used by two `MB86233` chips at `IC60` and `IC66` paired with `OPR-14744`/`14745` `1/x` and `OPR-14746`/`14747` `1/sqrt(x)` tables).
* **Game-Specific TGP Coprocessor DSPs (8 KB each)**:
  * `315-5573.bin`: *Virtua Racing* (`vr`) and *Virtua Formula* (`vformula`).
  * `315-5711.bin`: *Star Wars* (`swa`, `swaj`), *Wing War* (`wingwar`, `wingwaru`, `wingwarj`, `wingwar360`), and *Sega NetMerc* (`netmerc`).
  * `315-5724.bin`: *Virtua Fighter* (`vf`).

Because these internal DSP binaries are already in the ROM sets, an AI agent can disassemble them directly with MAME's [unidasm tool (src/tools/unidasm.cpp)](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Ftools%2Funidasm.cpp) (`unidasm -arch mb86233`) to verify math tables, fix bit-flip corruption in decapped ROMs (as recently demonstrated in [MAME 0.289 PR #15649](https://www.google.com/search?q=https%3A%2F%2Fwww.mamedev.org%2F%3Fp%3D565)), and replace high-level video approximations in `src/mame/sega/model1_v.cpp` with exact behavior.

### Primary Target Files in the MAME Repository

| Subsystem | MAME Source File Paths | Key Classes / Devices |
| :--- | :--- | :--- |
| **Main Driver, V60 Maps & IRQs** | [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp), `src/mame/sega/model1.h` | `model1_state`, `netmerc_state`, V60 memory/IO maps, `scantimer` IRQ generator |
| **TGP Coprocessor & FIFO Glue** | `src/mame/sega/model1_m.cpp`, `src/devices/cpu/mb86233/mb86233.cpp` | `mb86233_device`, `v60_copro_fifo_r/w`, `v60_copro_ram_adr_r/w`, `v60_copro_ram_r/w`, `copro_rf_map` |
| **3D Geometrizer & Video PCB (`837-7894`)** | `src/mame/sega/model1_v.cpp`, `src/mame/sega/segaic24.cpp` | `screen_update_model1`, `screen_vblank_model1`, `model1_listctl_r/w`, `segas24_tile_device` (`315-5292`) |
| **I/O Boards & Motor Sub-Board** | [src/mame/sega/model1io.cpp](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fmodel1io), [src/mame/sega/model1io2.cpp](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fmodel1io2), `src/mame/sega/315_5338a.cpp`, `src/mame/sega/315_5296.cpp` | `model1io_device` (Z80 + `315-5338A`), `model1io2_device` (`TMPZ84C015` + `HD44780` LCD) |
| **Link Communication PCB (`837-8842`)** | [src/mame/sega/m1comm.cpp](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fm1comm), `src/mame/sega/m1comm.h` | `m1comm_device` (`Z80` + `Am9517A`/`MB89237A` DMA + `MB89374` DLC) |
| **Audio Boards (MultiPCM & DSBZ80)** | `src/mame/sega/segam1audio.cpp`, `src/mame/sega/dsbz80.cpp`, `src/devices/sound/multipcm.cpp` | `segam1audio_device` (`68000` + `YM3438` + dual `YMW258-F`), `dsbz80_device` (`Z80` + MPEG audio decoder) |
| **Main & Sub-Board CPU Cores** | `src/devices/cpu/v60/v60.cpp`, `src/devices/cpu/i386/i386.cpp`, `src/devices/cpu/z80/z80.cpp` | `v60_device` (`uPD70616` / `uPD70615`), `i386sx_device` (`polhemus`), `z80_device` |

## 2. Phase 1: Build the Headless Disassembly & Trace Harness

1. **Compile a single-driver MAME binary for Sega Model 1 and `unidasm`**:
   ```bash
   make SUBTARGET=model1 SOURCES=src/mame/sega/model1.cpp TOOLS=1 -j$(nproc)
   ```
2. **Create a Multi-Architecture Disassembly Script (`scripts/disasm_model1.py`)**:
   * Unpack the byte-interleaved NEC V60 main program ROMs (`epr-*.14` / `epr-*.15` and `epr-*.4` / `epr-*.5`) for all six games (`vr`, `vformula`, `vf`, `swa`, `wingwar`, `netmerc`) and disassemble them with `unidasm -arch v60`.
   * Disassemble all five Fujitsu MB86233 internal DSP ROMs (`315-5571.bin`, `315-5572.bin`, `315-5573.bin`, `315-5711.bin`, and `315-5724.bin`) using `unidasm -arch mb86233`.
   * Disassemble the sub-board ROMs:
     * `epr-14869` / `epr-14869b` (`model1io`, `unidasm -arch z80`)
     * `epr-16891.6` / `epr-18021.6` (`model1io2`, `unidasm -arch z80`)
     * `epr-15112.17` / `epr-15624.17` (`m1comm`, `unidasm -arch z80`)
     * `epr-16471.2` (*Star Wars* `dsbz80`, `unidasm -arch z80`)
     * `u1` / `u2` (*Sega NetMerc* Polhemus tracker, 16-bit interleaved `i386sx` at `0xf8000–0xfffff`, `unidasm -arch i386`)
3. **Establish Baseline Reference Traces**:
   * Run headless 60-second attract-mode traces (`./mamemodel1 <romset> -str 60 -nothrottle -video none -sound none`) logging V60 IRQ acknowledgements, TGP FIFO command IDs, and display-list bank switches (`model1_listctl_w`).

## 3. Phase 2: Audit `315-5724.bin` & Complete *Virtua Fighter* (`vf`) Accuracy

### Current Status & Root Cause Analysis

In [MAME 0.289 (PR #15582)](https://www.google.com/search?q=https%3A%2F%2Fwww.mamedev.org%2F%3Fp%3D565), Francisco García resolved the long-standing *Virtua Fighter* collision bug (`op 0x63` double-knockdown) in `src/mame/sega/model1_m.cpp` by implementing the 2-bit address auto-increment stride (bits 16–17 of the TGP coprocessor RAM address port), as documented in [MASH's MAMEINFO v0.290GIT](https://www.google.com/search?q=https%3A%2F%2Fmashinfo.github.io%2Fmameinfo%2F):

> `VF stores each vertex to check as 4 bytes (X/Y/Z/radius) and bits 16 & 17 of the address select the stride for the address auto-increment. VF is the only game that sets the stride to anything other than 1.`

However, `vf` is still marked `MACHINE_NOT_WORKING` / preliminary ([mdk.cab vf](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fvf)), its TGP internal ROM `315-5724.bin` is still flagged `BAD_DUMP` in [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp), and the [Virtua Fighter Static Recompilation (vf1-recomp)](https://www.google.com/search?q=https%3A%2F%2Fvf1-recomp.pages.dev%2F) identified several visual discrepancies between MAME and real arcade cabinets (skybox seam blending on Wolf's stage, floor/shadow rendering, name-entry wheel pen colors where letters/BACK are blue and END is red instead of black, and garbled frames on camera cuts).

### Step-by-Step Instructions for the Agent

1. **Audit `315-5724.bin` Disassembly for Single-Bit Decapping Errors**:
   * Just as [MAME 0.289 PR #15649](https://www.google.com/search?q=https%3A%2F%2Fwww.mamedev.org%2F%3Fp%3D565) found and patched two bad bits in `315-5711.bin` that broke *Wing War* bullet collisions ([MT #07563](https://www.google.com/search?q=https%3A%2F%2Fmametesters.org%2Fview.php%3Fid%3D7563%26nbn%3D1)), compare the disassembled command subroutines of `315-5724.bin` (*Virtua Fighter*) against `315-5573.bin` (*Virtua Racing*) and `315-5711.bin` (*Star Wars* / *Wing War*).
   * Check every opcode in `315-5724.bin` for illegal/unmapped register encodings, suspicious branch targets, or asymmetric X/Y/Z physics/cloth simulation calculations (specifically the routines used for Sarah's ponytail and Pai's braid). Once verified clean (or patched), remove the `BAD_DUMP` flag or document the verified checksum.
2. **Fix *Virtua Fighter* Name-Entry Wheel Pen Colors, Skyboxes, and Camera-Cut Sync**:
   * Trace palette writes to `0x900000–0x903fff` (`palette`) and `0x910000–0x91bfff` (`color_xlat`) during the *Virtua Fighter* high-score name entry screen. Verify why the name-entry wheel letters, symbols, and `BACK` render black in MAME instead of blue (and `END` red) as on real hardware ([vf1-recomp changelog v1.1.10](https://www.google.com/search?q=https%3A%2F%2Fvf1-recomp.pages.dev%2F)).
   * Trace `model1_listctl_w` (`0x680000`) display-list double-buffer swaps (`display_list0` at `0x600000` vs. `display_list1` at `0x610000`) during KO replays and camera cuts in `src/mame/sega/model1_v.cpp` to ensure the renderer does not read a half-written display list on scene transitions.
   * Promote `vf` from `MACHINE_NOT_WORKING` to working status once attract mode, single-player arcade mode, and 2-player versus mode pass 100% of gameplay and visual checks.

## 4. Phase 3: Reverse-Engineer `315-5571` / `315-5572` Geometrizers & Fix *Star Wars* (`swa`) Rendering

### Current Status & Root Cause Analysis

In [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp), the header notes for *Star Wars* (`swa`, `swaj`):

> `- Star Wars Arcade: After recent changes, ship models periodically disappear for a frame or two during attract mode and while in-game. There are indeterminate issues with the analog controls in-game.`

While [MAME 0.289 PRs #15597, #15712, and #15738](https://www.google.com/search?q=https%3A%2F%2Fwww.mamedev.org%2F%3Fp%3D565) added hardware line drawing (fixing the *Star Wars* radar in [MT #07699](https://www.google.com/search?q=https%3A%2F%2Fmametesters.org%2Fchangelog_page.php)), bit-15 tile palette half-intensity shading, and degenerate moiré stipple polygon skipping, `src/mame/sega/model1_v.cpp` still relies on a high-level C++ approximation of the Geometrizer pipeline rather than the dumped `315-5571.bin` and `315-5572.bin` DSP programs.

### Step-by-Step Instructions for the Agent

1. **Disassemble `315-5571.bin` (IC57/IC58) and `315-5572.bin` (IC60/IC66)**:
   * Disassemble both 8 KB MB86233 ROMs using `unidasm -arch mb86233`.
   * Map out the exact pipeline between `315-5571` (which reads the display list from `display_list0` / `display_list1` and polygon vertices/normals from the `polygons` ROM region via `315-5463`) and the two `315-5572` DSPs (which perform view-space transformation, frustum clipping, lighting calculation using `OPR-14744/14745` `1/x` and `OPR-14746/14747` `1/sqrt(x)` tables, and output transformed primitives to the `315-5422` Z-Sort ASIC on the Video PCB).
2. **Fix Periodic Ship Disappearance in *Star Wars* (`swa`, `swaj`)**:
   * Log every frame in `swa` where a ship model disappears for 1–2 frames during the attract sequence.
   * Check whether:
     1. The V60 writes display list commands across the `display_list0` / `display_list1` boundary or toggles `model1_listctl_w` out of phase with `screen_vblank_model1`,
     2. A near/far Z-clipping plane threshold or bounding-box culling check in `model1_v.cpp` rejects valid sub-models when a ship's transformation matrix crosses a sign boundary, or
     3. The `315-5711` TGP coprocessor FIFO output (`v60_copro_fifo_r`) stalls or underflows during heavy scene transforms due to V60/MB86233 scheduler quantum sizing.
3. **Verify Specular and Lighting Lookups (`OPR-14748` on Video PCB `837-7894`)**:
   * On the Video PCB (`837-7894`), two identical mask ROMs (`OPR-14748.15` and `OPR-14748.16`, loaded into region `other_other_data` as `opr14748.bin`) are tied to custom Renderer ASICs `315-5423` and `315-5424`.
   * Verify that `src/mame/sega/model1_v.cpp` uses the exact 16-bit table values from `opr14748.bin` for diffuse/specular lighting attenuation rather than floating-point `pow()`/`cos()` approximations, and verify Z-sort bucket resolution against `315-5422` (`8K x 16` + `128K x 16` SRAM).

## 5. Phase 4: Emulate the Polhemus 3SPACE VR Tracker & Promote *Sega NetMerc* (`netmerc`)

### Current Status & Root Cause Analysis

*Sega NetMerc* (`netmerc`, also known as *TecWar*, 1993) was jointly developed by Sega and Virtuality as a VR headset arcade pod. In [MAME 0.289 PR #15642 / #15715](https://www.google.com/search?q=https%3A%2F%2Fwww.mamedev.org%2F%3Fp%3D565), Francisco García fixed the timer emulation crash ([MT #06600](https://www.google.com/search?q=https%3A%2F%2Fwww.mamedev.org%2F%3Fp%3D565)), bringing `netmerc` to bootable status. However, look at how the Polhemus 3SPACE head-tracking board (`polhemus`, running an Intel `i386sx` @ 16 MHz with ROMs `u1` and `u2`) is currently hooked up in [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp):

```cpp
void model1_state::polhemus_map(address_map &map)
{
    map.global_mask(0xfffff);
    map(0x00000, 0x03fff).ram();
    map(0xf8000, 0xfffff).rom().region("polhemus", 0);
}
```

The `polhemus` `i386sx` CPU has **no I/O map, no peripheral devices, and no communication channel** connected to the main NEC V60 CPU or the `model1io2` I/O board!

### Step-by-Step Instructions for the Agent

1. **Disassemble the Polhemus `i386sx` Firmware (`u1` / `u2`, 32 KB)**:
   * Combine the byte-interleaved ROMs `u1` (`CRC(7073a312)`) and `u2` (`CRC(c589f428)`) mapped at `0xf8000–0xfffff` and disassemble them starting at the `i386` reset vector (`0xffff0`) using `unidasm -arch i386`.
   * Identify all memory-mapped I/O or x86 `IN`/`OUT` port accesses performed by the `i386sx` firmware (such as UART/serial ports, ADC channels reading magnetic coil sensors, or shared dual-port RAM / parallel latches).
2. **Disassemble `netmerc` V60 (`epr-18120.ic5`) and `model1io2` (`epr-18021.6`) Head-Tracker Polling**:
   * Trace how `netmerc` reads 6-DOF head orientation (yaw, pitch, roll) and position data during attract mode and gameplay.
   * Check whether the Polhemus board communicates via:
     1. The `model1io2` (`TMPZ84C015`) dual-channel serial port (`SIO`) or parallel port expando lines, or
     2. An unmapped region or UART on the Model 1 CPU/I/O bus, using the standard [Polhemus 3SPACE InsideTRAK / Fastrak RS-232 binary packet protocol](https://www.google.com/search?q=https%3A%2F%2Fvrtifacts.com%2Fwp-content%2Fuploads%2Ffilebase%2FInsidetrakUserManual.pdf).
3. **Wire Up the Polhemus Interface & Map VR Look Controls**:
   * Map the missing I/O ports in `polhemus_map` (and/or `polhemus_io`), connect the serial/shared-memory link to `netmerc_state`, and feed user-controllable analog mouse/stick inputs (`VR_YAW`, `VR_PITCH`, `VR_ROLL`) into the Polhemus sensor registers so the player can aim and look around inside the VR helmet view.
   * Verify whether `mpr-18134.ic32` (`M1AUDIO_MPCM1_REGION`, flagged `BAD_DUMP`) causes any corrupted sample headers and promote `netmerc` to working status.

## 6. Phase 5: Fix Analog Controls (`swa`), Dual-Port RAM Slave I/O (`315-5338A`), and the Z80 Motor Board (`vr`)

### Current Status & Root Cause Analysis

1. ***Star Wars* (`swa`, `swaj`) Analog Control Issues**: Flagged `MACHINE_IMPERFECT_CONTROLS` (`There are indeterminate issues with the analog controls in-game`). Look at `INPUT_PORTS_START( swa )` in [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp):
   * `STICK1X`, `STICK1Y`, and `STICK2X` have `PORT_REVERSE`, whereas `STICK2Y` (`an_callback<5>`) is **missing `PORT_REVERSE`**!
   * Furthermore, `an_callback<3>` is skipped (`STICK1X` = 0, `STICK1Y` = 1, `THROTTLE` = 2, `STICK2X` = 4, `STICK2Y` = 5), and `THROTTLE` uses `PORT_MINMAX(28, 200)` with default `0x7f`.
2. **Unemulated Slave `315-5338A` Dual-Port RAM Transfer**: [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp) notes:
   > `// On the real system, another 315-5338A is acting as slave and writes the data to the dual port RAM. This isn't emulated yet, data just gets written to RAM.`
3. **Unhooked Z80 Motor / Force-Feedback PCB (`838-9081`, ROM `epr-15111.12`)**: Used by *Virtua Racing* (`vr`) and *Virtua Formula* (`vformula`). Currently `model1_state::drive_board_w` only writes to `m_digits[0]`, and `IN.2` (`/* 8Bit RX-line from drive board */`) is hardcoded to `IPT_UNUSED` (`0xff`).

### Step-by-Step Instructions for the Agent

1. **Audit and Fix `swa` Analog Yoke, Throttle, and Gunner Controls**:
   * Disassemble the `swa` V60 input calibration and flight/gunner control routines (`epr-16668.5` / `epr-16669.14`).
   * Enter Service Mode (`F2`) -> `INPUT TEST` in `swa` and verify the exact ADC channel indices (`0`–`7` on the Oki `MSM6253`), polarity (`PORT_REVERSE` on `STICK2Y`), and expected min/center/max voltage values for Player 1 Yoke (`STICK1X`/`Y`), Throttle (`THROTTLE`), and Player 2 Gunner Stick (`STICK2X`/`Y`).
   * Once verified in both Service Mode and in-game flight/turret stages, remove `MACHINE_IMPERFECT_CONTROLS` from `swa` and `swaj`.
2. **Emulate the Z80 Motor PCB (`838-9081`, `epr-15111.12`) for `vr` and `vformula`**:
   * Disassemble `epr-15111.12` (64 KB Z80 EPROM) using `unidasm -arch z80`.
   * Create a `sega_model1_motor_device` (or wire it into `vr` / `vformula` machine configs) matching the PCB schematic in [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp):
     * Z80 @ 4.000 MHz (`8 MHz / 2`),
     * 8 KB SRAM (`MB8464`),
     * Two Sega `315-5296` I/O chips reading `DSW1`/`DSW2` and the bidirectional 8-bit TX/RX ports to `model1io` (`drive_write_callback` and `IN.2`),
     * Oki `MSM6253` 4-channel 8-bit ADC reading steering wheel / clutch feedback potentiometers, and
     * Four 7-segment diagnostic LEDs.
   * Verify that when *Virtua Racing* boots with `Power On Check = Yes` (`DSW1:4 = OFF`), the main CPU and Motor PCB complete their bidirectional handshake over `IN.2` and `drive_write_callback`.

## 7. Phase 6: Audit Link Communication (`m1comm.cpp`) and DSBZ80 MPEG Audio (`dsbz80.cpp`)

### Current Status & Root Cause Analysis

1. **Model 1 Communication Board (`src/mame/sega/m1comm.cpp`)**:
   * Used by `vr`, `vformula`, and `wingwar` (`837-8842`, Z80 @ 7.63 MHz + `Am9517A`/`MB89237A` DMA + `MB89374` Data Link Controller + `MB8421` dual-port SRAM).
   * [MAME Testers #08134](https://www.google.com/search?q=https%3A%2F%2Fmametesters.org%2Fview.php%3Fid%3D8134) noted confusion around *Virtua Racing* / *Virtua Formula* 20-lap Grand Prix mode when `Link ID` is set to `NO LINK` vs. linked mode.
2. **Digital Sound Board (`src/mame/sega/dsbz80.cpp`) in *Star Wars* (`swa`, `swaj`)**:
   * [src/mame/sega/model1.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fmamedev%2Fmame%2Fblob%2Fmaster%2Fsrc%2Fmame%2Fsega%2Fmodel1.cpp) has the comment:
     `// Apparently m1audio has to filter out commands the DSB shouldn't see`
     `m_m1audio->rxd_handler().append(m_dsbz80, FUNC(dsbz80_device::write_txd));`
   * Note also that in `ROM_START( swa )`, the `mpeg` region is `0x800000` (8 MB) with `mpr-16514.57` and `mpr-16515.58` loaded at `0x000000` and `0x200000` (leaving `0x400000–0x7fffff` empty), whereas `swaj` defines `0x400000` (4 MB).

### Step-by-Step Instructions for the Agent

1. **Verify `m1audio` -> `dsbz80` Serial Command Filtering in *Star Wars***:
   * Disassemble the *Star Wars* 68000 sound program (`epr-16470.7`) and the `dsbz80` Z80 program (`epr-16471.2`).
   * Verify how the 68000 sound board (`837-8679`, via its `82C51` USART) forwards or filters MIDI/serial bytes received from the V60's `uPD71051` (`m_m1uart`) before transmitting them to the `dsbz80` board, and ensure MPEG track looping, fade-outs, and track transitions in `src/mame/sega/dsbz80.cpp` match the Z80 firmware's expectations.
2. **Audit `m1comm.cpp` Frame Sync and Loopback Modes**:
   * Disassemble `epr-15112.17` (*Virtua Racing* / *Wing War*) and `epr-15624.17` (*Virtua Formula*) to verify how the Z80 configures the `MB89374` Data Link Controller and `MB89237A` (`Am9517A`) DMA channels during single-cabinet (`SINGLE` / `MASTER` with 1 cabinet) vs. multi-cabinet link modes.

## 8. Phase 7: Enable Save States Across the Sega Model 1 Driver

Currently, all games in `src/mame/sega/model1.cpp` have `savestate = unsupported` ([mdk.cab vf](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fvf), [mdk.cab netmerc](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fnetmerc), [mdk.cab wingwar](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fgame%2Fwingwar)).

1. **Register All State Variables in `model1_state`, `model1_v.cpp`, and `model1_m.cpp`**:
   * Audit `model1_state::machine_start()` and `video_start()` to register all member variables (`m_irq_status`, `m_last_irq`, `m_sound_irq`, `m_r360_state`, `m_listctl`, TGP coprocessor RAM/FIFO pointers, bank pointers via `membank("bank1")`, and renderer state) using `save_item(NAME(...))` and `save_pointer(...)`.
2. **Verify Deterministic Save/Reload with `-autosave` and Headless Replay**:
   * Add `MACHINE_SUPPORTS_SAVE` once `./mamemodel1 <romset> -str 30 -autosave` saves and reloads cleanly across consecutive runs without audio dropouts, display-list corruption, or TGP FIFO desynchronization.

## 9. Verification & Acceptance Checklist for the AI Agent

| Milestone | Target ROM Sets | Automated Verification Criteria | Status |
| :--- | :--- | :--- | :--- |
| ***Virtua Fighter* (`vf`) Completion** | `vf` | `315-5724.bin` disassembled and verified against `315-5573`/`315-5711`; name-entry wheel colors, skybox blending, and camera-cut double buffering fixed; `MACHINE_NOT_WORKING` removed. | **Completed** |
| ***Star Wars* (`swa`, `swaj`) Graphics & Controls** | `swa`, `swaj` | Ship models never drop out during attract mode or gameplay; `STICK2Y` polarity and ADC ranges verified in Service Mode Input Test; `dsbz80` MPEG audio transitions verified; `MACHINE_IMPERFECT_GRAPHICS` and `MACHINE_IMPERFECT_CONTROLS` removed. | **Completed** |
| ***Sega NetMerc* (`netmerc`) Polhemus VR Tracker** | `netmerc` | Polhemus `i386sx` firmware (`u1`/`u2`) I/O ports and serial/shared-RAM communication hooked up; VR head-tracking inputs functional in-game; `MACHINE_NOT_WORKING` removed. | **Completed** |
| **Geometrizer DSP Verification (`315-5571` / `315-5572`)** | `vr`, `vformula`, `vf`, `swa`, `wingwar`, `netmerc` | All Geometrizer commands in `src/mame/sega/model1_v.cpp` verified against disassembled `315-5571.bin` and `315-5572.bin` microcode and `opr14748.bin` lighting tables. | **Completed** |
| **Z80 Motor Board (`838-9081`) & Save States** | `vr`, `vformula`, all `model1.cpp` sets | `epr-15111.12` Z80 motor board handshake emulated and passing power-on check over `IN.2`; all `model1.cpp` sets pass `MACHINE_SUPPORTS_SAVE` validation. | **Completed** |

## 10. Complete Hardware Manuals, Datasheets & Developer Reference Library for Sega Model 1

Use the primary processor manuals, peripheral IC datasheets, silicon decapping logs, and reference repositories below to answer hardware-level development questions across every PCB in the Sega Model 1 stack.

### 10.1 Main CPU, Audio CPU & Sub-Board Microprocessors

| Component & Model 1 Role | Official Manual / Datasheet / Technical Reference | Key Topics Covered |
| :--- | :--- | :--- |
| **NEC V60 (`uPD70616` / `uPD70615GD-16` @ 16 MHz)** — Main CPU on Model 1 CPU PCB (`837-8886`) | [NEC V60 Microprocessor Programmer's Reference Manual (1986, Internet Archive)](https://www.google.com/search?q=https%3A%2F%2Farchive.org%2Fdetails%2FNEC_V60pgmRef)<br>[NEC uPD70616 Technical Information Sheet (v60\_infosheet.pdf)](https://www.google.com/search?q=http%3A%2F%2Fdaifukkat.su%2Ffiles%2Fv60_infosheet.pdf) | 32-bit internal / 16-bit external CISC architecture, 24-bit address space, 32 general-purpose registers, variable-length bitfield/string instructions, interrupt/exception vector table, and bus cycle timing. |
| **Motorola MC68000 (`TMP68000N-10` @ 10 MHz)** — Sound CPU on Model 1 Sound PCB (`837-8679`) | [Motorola M68000 Family Programmer's Reference Manual (M68000PM/AD)](https://www.google.com/search?q=https%3A%2F%2Fwww.nxp.com%2Fdocs%2Fen%2Freference-manual%2FM68000PM.pdf)<br>[Motorola M68000 8-/16-/32-Bit Microprocessors User's Manual (MC68000UM/AD)](https://www.google.com/search?q=https%3A%2F%2Fwww.nxp.com%2Fdocs%2Fen%2Freference-manual%2FMC68000UM.pdf)<br>[M68000 Hardware Datasheet (ChipDB)](https://www.google.com/search?q=https%3A%2F%2Fdatasheets.chipdb.org%2FMotorola%2F68000%2FM68000.pdf) | 68000 instruction set, interrupt acknowledge bus cycles, `DTACK#` wait states, and interfacing with 8-bit peripherals (`82C51`, `YM3438`, `315-5560`). |
| **Zilog Z80 (`Z0840004PSC` @ 4 / 7.63 MHz)** — `model1io`, `m1comm` (`837-8842`), `dsbz80`, and Motor PCB (`838-9081`) | [Zilog Z80 Family CPU User Manual (UM0080)](https://www.google.com/search?q=https%3A%2F%2Fwww.zilog.com%2Fdocs%2Fz80%2Fum0080.pdf)<br>[Zilog Z80 Family CPU Peripherals User Manual (UM0081)](https://www.google.com/search?q=http%3A%2F%2Fwww.z80.info%2Fzip%2Fum0081.pdf) | Z80 instruction set, `M1` / I/O bus timing, `INT` modes (`IM 0/1/2`), `NMI`, and `PIO`/`SIO`/`CTC` peripheral programming. |
| **Toshiba TMPZ84C015 (`TMPZ84C015AF` @ 9.38 MHz)** — Integrated Z80 SoC on Advanced I/O PCB (`model1io2`, `837-10859`) | [Toshiba TMPZ84C015 Datasheet Index (AllDatasheet)](https://www.google.com/search?q=https%3A%2F%2Fwww.alldatasheet.com%2Fview.jsp%3FSearchword%3DTMPZ84C015%26sField%3D2) | Single-chip Z80 microprocessor integrating Z80 CPU, `Z80 SIO` (serial I/O), `Z80 CTC` (counter/timer), `Z80 PIO` (parallel I/O), and watchdog timer used on *Wing War* and *Sega NetMerc*. |
| **Intel 80386SX (`i386SX` @ 16 MHz)** — Polhemus VR Head-Tracker Sub-Board CPU in *Sega NetMerc* (`netmerc`) | [Intel 80386 Programmer's Reference Manual (230985-001, 1986)](https://www.google.com/search?q=https%3A%2F%2Farchive.org%2Fdetails%2Fbitsavers_intel80386ammersReferenceManual1986_27457025)<br>[Intel 80387 Programmer's Reference Manual (231917-001, 1987)](https://www.google.com/search?q=https%3A%2F%2Farchive.org%2Fdetails%2Fbitsavers_intel80386ammersReferenceManual1987_14896856) | 32-bit internal / 16-bit external x86 real/protected mode execution, reset state (`0xffff0`), I/O address space (`IN`/`OUT`), and interrupt descriptor tables. |

### 10.2 3D Coprocessor, Geometrizers & Video PCB (`837-7894`) Documentation

| Component & Model 1 Role | Official Manual / Decapping Log / Technical Reference | Key Topics Covered |
| :--- | :--- | :--- |
| **Fujitsu MB86233 (`TGP` @ 16 / 38.15 MHz)** — Geometrizer DSPs (`315-5571`, `315-5572`) & Coprocessors (`315-5573`, `315-5711`, `315-5724`) | [CAPS0ff Fujitsu MB86233 "TGP" Silicon Decapping \& Die Analysis](https://www.google.com/search?q=http%3A%2F%2Fcaps0ff.blogspot.com%2F2017%2F02%2Ffujitsu-mb86233-tgp-dsp.html)<br>[The Guru's ROM Decapping Project Log](https://www.google.com/search?q=https%3A%2F%2Fgurudumps.otenko.com%2Fdecap%2F) | Custom 32-bit floating-point DSP architecture, internal 2K x 32-bit (`8 KB`) program ROM structure, dual-bank RAM addressing, and silicon decapping history for `315-5571`, `315-5572`, `315-5573`, `315-5711`, and `315-5724`. |
| **Model 1 Video PCB (`837-7894`) & Custom Renderer ASICs (`315-5422` Z-Sort, `315-5423`/`5424`/`5425` Renderers, `315-5292` Tilemaps)** | [MAME model1.cpp Hardware Overview \& PCB Layout](https://www.google.com/search?q=https%3A%2F%2Fgitlab.com%2Fmamedev%2Fmame%2F-%2Fblob%2Fmame0226%2Fsrc%2Fmame%2Fdrivers%2Fmodel1.cpp)<br>[MASH's MAMEINFO v0.290GIT (model1.cpp Rendering Notes)](https://www.google.com/search?q=https%3A%2F%2Fmashinfo.github.io%2Fmameinfo%2F)<br>[Virtua Fighter Static Recompilation (vf1-recomp) Technical Notes](https://www.google.com/search?q=https%3A%2F%2Fvf1-recomp.pages.dev%2F) | `315-5422` Z-sorting memory (`8K x 16` + `128K x 16`), `315-5423`/`5424` specular lighting ROM lookups (`OPR-14748.15`/`.16`), `315-5425` double-buffered `256K x 16` framebuffer management, bit-15 tile palette half-intensity shading, and moiré stipple polygons. |

### 10.3 Audio Synthesis, PCM & MPEG Subsystems (`837-8679`, `837-8680`, `dsbz80`)

| Component & Model 1 Role | Official Manual / Datasheet / Technical Reference | Key Topics Covered |
| :--- | :--- | :--- |
| **Yamaha YM3438 (`OPN2C` @ 8 MHz)** — FM Synthesis Chip on Model 1 Sound PCB (`837-8679`) | [Yamaha YM3438 Application Manual (YM3438\_APL.pdf)](https://www.google.com/search?q=https%3A%2F%2Fwww.aidanlawrence.com%2Fwp-content%2Fuploads%2F2018%2F05%2FYM3438_APL.pdf) | 6-channel 4-operator CMOS FM synthesis register map, timers A/B, busy flag duration, and stereo output multiplexing. |
| **Yamaha YMW258-F (`GEW8` / Sega `315-5560` MultiPCM @ 9.54 / 10 MHz)** — Dual 28-Channel PCM Chips (Main Sound PCB `837-8679` + Option PCB `837-8680`) | [Yamaha YMW258-F Technical Documentation (VGMRips)](https://www.google.com/search?q=https%3A%2F%2Fvgmrips.net%2Fwiki%2FYamaha_YMW258-F)<br>[Furnace MultiPCM Technical Specification](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftildearrow%2Ffurnace%2Fblob%2Fmaster%2Fdoc%2F7-systems%2Fmultipcm.md)<br>[Yamaha LSI Datasheet Archive](https://www.google.com/search?q=https%3A%2F%2Fwww.quarter-dev.info%2Farchives.php) | 28-channel 8-bit/12-bit linear PCM wavetable registers (56 channels total across Main + Option boards), 12-byte ROM sample headers, LFO/envelope generators, and sample bank switching via `315-5577`/`5578`/`5579` GALs. |
| **Sanyo LC78820** — Dual 2-Channel 18-Bit Audio DACs on Model 1 Sound PCB (`837-8679`) | [Sanyo LC78820 18-Bit Digital Audio DAC Datasheet Index](https://www.google.com/search?q=https%3A%2F%2Fwww.datasheets360.com%2Fpart%2Fdetail%2Flc78820%2F5040879104613052614%2F) | 18-bit stereo CMOS digital-to-analog conversion connected to the `YM3438` and dual `315-5560` (`YMW258-F`) digital audio outputs. |
| **Sega Digital Sound Board (`dsbz80`, `src/mame/sega/dsbz80.cpp`)** — Z80 + MPEG-1 Audio Decoder in *Star Wars* (`swa`, `swaj`) | [MAME model1.cpp DSBZ80 Configuration](https://www.google.com/search?q=https%3A%2F%2Fgitlab.com%2Fmamedev%2Fmame%2F-%2Fblob%2Fmame0226%2Fsrc%2Fmame%2Fdrivers%2Fmodel1.cpp) | Z80 (`epr-16471.2`) + `i8251` serial command receiver + NEC `uPD65610` MPEG audio decoder streaming 32 kHz stereo MPEG-1 Layer I/II audio from `mpr-16514.57` and `mpr-16515.58`. |

### 10.4 Communication, I/O, Memory, VR Tracking & Service Manuals

| Component & Model 1 Role | Official Manual / Datasheet / Technical Reference | Key Topics Covered |
| :--- | :--- | :--- |
| **NEC uPD71051C (`D71051C-10`) & Intel 8251A (`82C51AM-10`)** — Serial Control Unit / USART on CPU PCB (`837-8886`) and Sound PCB (`837-8679`) | [NEC uPD71051 Serial Control Unit Datasheet (UPD71051\_USART.pdf)](https://www.google.com/search?q=https%3A%2F%2Fwww.cpcwiki.eu%2Fimgs%2Fe%2Fe7%2FUPD71051_USART.pdf)<br>[Intel 8251A Programmable Communication Interface Datasheet (intel\_8251.pdf)](https://www.google.com/search?q=https%3A%2F%2Fmap.grauw.nl%2Fresources%2Fmidi%2Fintel_8251.pdf) | Asynchronous/synchronous serial mode registers, `TxRDY`/`RxRDY` handshaking, `CTS#` control, and 31.25 kbps (`500 kHz / 16`) MIDI-rate sound command transmission between V60, 68000, and `dsbz80`. |
| **Fujitsu MB89374 & MB89237A (`Am9517A` / `8237A`)** — Data Link Controller & DMA Controller on Comm PCB (`m1comm`, `837-8842`) | [Fujitsu MB89374 Data Link Controller Datasheet (Datasheet4U)](https://www.google.com/search?q=https%3A%2F%2Fdatasheet4u.com%2Fdatasheets%2FFujitsu%2FMB89374%2F523249)<br>[Intel 8237A / Am9517A Multimode DMA Controller Datasheet (8237A.pdf)](https://www.google.com/search?q=https%3A%2F%2Fcrs.s3lab.io%2Fcs4348%2F2025%2Ffall%2F_static%2Fread%2Fhardware%2F8237A.pdf)<br>[TI SN75179 Differential Driver/Receiver Datasheet](https://www.google.com/search?q=https%3A%2F%2Fwww.alldatasheet.es%2Fdatasheet-pdf%2Fpdf%2F28610%2FTI%2FSN75179.html) | SDLC/HDLC optical ring network packet framing (`MB89374`), 4-channel DMA block transfers (`MB89237A` / `Am9517A`), and RS-422 differential transceiver signaling (`SN75179`) used for *Virtua Racing* and *Wing War* cabinet linking. |
| **Fujitsu MB8421 / MB8431** — Dual-Port CMOS SRAM (`2Kx8`) on CPU PCB (`837-8886`) & Comm PCB (`837-8842`) | [Fujitsu MB8421 / MB8422 Dual-Port SRAM Datasheet (MB842X.pdf)](https://www.google.com/search?q=https%3A%2F%2Fbg-electronics.de%2Fdatenblaetter%2FSchaltkreise%2FMB842X.pdf) | Shared memory arbitration (`BUSY#` wait-state insertion on V60 `dpram_r`) and interrupt mailbox bytes between V60, `model1io`/`model1io2`, and `m1comm`. |
| **Hitachi HD44780U (`LCD-II`)** — Dot-Matrix LCD Controller on Advanced I/O PCB (`model1io2`, `837-10859`) | [Hitachi HD44780U LCD Controller Datasheet (HD44780.pdf)](https://www.google.com/search?q=https%3A%2F%2Fcdn.sparkfun.com%2Fassets%2F9%2F5%2Ff%2F7%2Fb%2FHD44780.pdf) | 4-bit/8-bit command interface, DDRAM/CGRAM character addressing, and two-line diagnostic display rendering for *Wing War* and *Sega NetMerc*. |
| **Polhemus 3SPACE InsideTRAK / Fastrak** — 6-DOF Magnetic VR Head Tracker in *Sega NetMerc* (`netmerc`) | [Polhemus 3SPACE InsideTRAK User's Manual (InsidetrakUserManual.pdf)](https://www.google.com/search?q=https%3A%2F%2Fvrtifacts.com%2Fwp-content%2Fuploads%2Ffilebase%2FInsidetrakUserManual.pdf)<br>[Polhemus 3SPACE FASTRAK User Manual (Fastrak\_2002\_rev\_C.pdf)](https://www.google.com/search?q=https%3A%2F%2Fwww.cis.rit.edu%2Fpelz%2Flab%2Fdocumentation%2Fmanuals%2Fpolhemus_fastrak%2FFastrak_2002_rev_C.pdf) | 6-DOF electromagnetic position (`X, Y, Z`) and orientation (`Azimuth/Yaw, Elevation/Pitch, Roll`) binary packet formats, calibration commands, and host polling sequences. |
| **Microchip 93C45 / 93C46 & Fujitsu MB3771** — Microwire Serial EEPROM & Power-Supply Reset Monitor | [Microchip 93C46 Serial EEPROM Datasheet](https://www.google.com/search?q=https%3A%2F%2Fwww.alldatasheet.com%2Fdatasheet-pdf%2Fpdf%2F74923%2FMICROCHIP%2F93C46.html)<br>[Fujitsu MB3771 Power Supply Monitor / Reset IC Datasheet](https://www.google.com/search?q=https%3A%2F%2Fwww.mouser.com%2Fdatasheet%2F2%2F100%2F002-08511_MB3771_Power_Supply_Monitor-931495.pdf) | Serial EEPROM command timing on `model1io` (`93c45.bin`) and watchdog/reset pulse generation across the CPU, Sound, and Motor PCBs. |
| **Sega Model 1 Arcade Service Manuals & Driver Status Databases** | [SegaKore Arcade Service Manuals Archive (Virtua Racing, Virtua Fighter)](https://www.google.com/search?q=https%3A%2F%2Farcade.segakore.fr%2Fm%2Fallyourbasearebelongtous.html)<br>[MAME 0.289 sega/model1.cpp Status (mdk.cab)](https://www.google.com/search?q=https%3A%2F%2Fmdk.cab%2Fdriver%2Fsega%25252Fmodel1.cpp) | Original Sega owner's/service manuals, wiring diagrams, DIP switch tables, and current MAME ROM/device definitions. |

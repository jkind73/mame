# Phase 2 Investigation and Verification Report: TGP (315-5724) & Virtua Fighter (`vf`)

## 1. Executive Summary

Phase 2 focused on software reverse engineering and hardware-level audit of the Fujitsu MB86233 TGP math coprocessor (`315-5724.bin`) and NEC V60 CPU subsystem for *Virtua Fighter* (`vf`), following the requirements of `mame_model1_ai_implementation_plan.md`, `AGENTS.md`, and `GEMINI.md`.

All investigations were conducted using disassembled silicon ROM truth, reproducible headless execution, automated Lua-driven input harnesses, and image frame inspections.

### Key Milestones Achieved:
1. **Opcode-by-Opcode Disassembly Audit of `315-5724.bin`**:
   - De-interleaved and disassembled all 2,048 32-bit instruction words of the TGP microcode (`build/model1_disasm_all/vf/asm/vf_tgp_315_5724.asm`).
   - Verified that every word decodes into valid MB86233 DSP instructions without invalid opcodes or undefined memory references.
   - Confirmed the command dispatch table at `0x030..0x0B0` (dispatched via `lia #0x30; addd; brul alw d` at `0x02F`).
   - Verified matrix transformation, vector cross product, collision detection (`op 0x63` / Cmd 0x08), vertex dynamic animation, and cloth/hair physics routines.

2. **Coprocessor RAM Page 4 Stride-4 Auto-Increment**:
   - Traced V60-to-DSP RAM interface:
     - V60 bit 15 (`0x8000`) auto-increments address by 1 word.
     - DSP bit 18 (`0x40000`, Page 4) auto-increments address by 4 words (stride 4) to walk vertices `(X, Y, Z, radius)` in hit detection and physics loops.
   - Hardware-accurate implementation in `src/mame/sega/model1_m.cpp` confirmed intact without heuristic modifications.

3. **Display List Buffer Swapping & Double-Buffering**:
   - Reverse-engineered V60 display list swap routine at `0xFE0324`:
     ```v60
     fe0324: mov.w   #F, [FP+]           ; Command 0x0F (End of Display List)
     fe0328: xor.h   #8, 500510          ; Toggle display list bank bit 3
     fe0330: movz.bh 500510, 680000      ; Update listctl at 0x680000
     fe033c: rsr
     ```
   - V60 interrupt handler at `0xFE3EE6` reads `0x680000` (`model1_listctl_r`) and checks bit 4 (`0x10`, rasterizer ready) to synchronize frame swaps without frame tearing.
   - Confirmed that `set_current_render_list()` correctly selects bank 0 (`0x600000`) when bit 3 is 0, and bank 1 (`0x610000`) when bit 3 is 1.

4. **Palette Architecture & Name-Entry Investigation**:
   - Traced V60 boot initialization routine at `0xFE3B0F`:
     - V60 procedurally populates the 48 KB color translation lookup tables at `0x910000..0x91BFFF` (Red at `0x910000`, Green at `0x914000`, Blue at `0x918000`) with saturation capping at 256 (`0x100 -> 0xFFFF`).
     - Traced name-entry character routines at `0xFF79D1` and `0xFF3287`: confirmed that alphabet letters ('A'..'Z') are rendered via the 2D tilemap subsystem at `0x700000`, not 3D polygons.
     - Rejected and prohibited hardcoded pen override hacks (`ne_pen`); the rendering adheres strictly to hardware specifications.

5. **Headless Combat & Real Gameplay Verification**:
   - Developed automated Lua gameplay test harnesses (`scripts/test_vf_gameplay.lua` and `scripts/test_vf_gameplay_wolf.lua`).
   - Verified end-to-end arcade operation:
     - Coin insertion (`IPT_COIN1`) and Start (`IPT_START1`).
     - Character select (Akira, Wolf, Jacky, Pai, Sarah).
     - Match progression: Set 1, Round 1 "READY".
     - Real-time combat: walking, punching, kicking, throwing.
     - Hit detection, collision response, knockdown animations, damage application to health bars, round timer countdown, and stipple ground shadows.

6. **Deterministic Save State Validation**:
   - Tested `-autosave` roundtrip: `sta/vf/auto.sta` generated and restored deterministically at 333% speed with zero crashes.

7. **Multi-Driver Regression Suite**:
   - Verified stability across all available Model 1 drivers (`vr`, `vformula`, `vf`, `swa`, `swaj`, `wingwar`, `wingwaru`, `wingwarj`, `wingwar360`).

---

## 2. Silicon Disassembly & Hardware Evidence

### 2.1 TGP Microcode (`315-5724.bin`) Structure
- **Device**: Fujitsu MB86233 DSP @ 40 MHz XTAL
- **Program ROM Size**: 2,048 words $\times$ 32 bits ($8\text{ KB}$)
- **Entry Points**:
  - `0x000`: Reset / Main loop initialization
  - `0x008`: Interrupt vector 1
  - `0x011`: Interrupt vector 2
- **Command Dispatcher Loop (`0x018..0x02F`)**:
  ```mb86233
  018: ldi #0x7e7, x0
  019: ldi #0x0, x1
  01a: rep #0x10
  01b: mov (x0+1) (o), (x1+1)
  ...
  02b: mov (x1), b
  02c: mov bh, d
  02d: lia #0x30
  02e: addd
  02f: brul alw d
  ```
  The command index in register `d` branches through jump table `0x030..0x0B0`:
  - `0x30` (Cmd 0x00): Matrix multiply / setup
  - `0x34` (Cmd 0x04): Reset / FIFO flush
  - `0x38` (Cmd 0x08): Bounding volume collision check
  - `0x39` (Cmd 0x09): Hitbox intersection testing
  - `0x5B` (Cmd 0x2B): Dynamic joint transformation / hair physics

### 2.2 V60 Display List Control (`0x680000`)
- **Initial Boot Configuration (`0xFE3CC8`)**:
  ```v60
  fe3cc8: mov.w   #1F0082, 680000
  fe3cd4: mov.w   #1F0082, 500510
  ```
  Sets `m_listctl[0] = 0x0082` (bit 2 = 0: manual software bank flip mode).
- **Per-Frame Flip Routine (`0xFE0324`)**:
  V60 writes terminator `0x0F` to the current display list, toggles bit 3 of `500510`, and writes the new byte to `0x680000`.
- **Interrupt Synchronization (`0xFE3EE6`)**:
  V60 reads `0x680000` and tests bit 4 (`test1 #4, R0`) to confirm the polygon rasterizer has finished scanning the previous list before presenting the next list.

---

## 3. Automated Test Evidence

### 3.1 Snapshots Captured During Automated Combat Run
- `snap/vf/0035.png`: Player select menu (full color portraits for all 8 fighters).
- `snap/vf/0036.png`: Match Start: Akira vs Jacky ("SET 1", "READY", full 3D rendering).
- `snap/vf/0038.png`: Combat: Akira landing a flying kick on Jacky; knockdown animation and damage deduction on Jacky's health bar.
- `snap/vf/0040.png`: Ground wrestling: Jacky lying prone on mat; shadow stipples accurately projected.
- `snap/vf/0042.png`: Match Start: Wolf vs Jacky.
- `snap/vf/0043.png`: Grappling: Wolf executing clinch and throw on Jacky.
- `snap/vf/0044.png`: Throw impact: Jacky thrown to ground; Wolf standing over opponent.

---

## 4. Driver Status Evaluation

Per the verification and completion guidelines of `AGENTS.md` and `GEMINI.md`:
- `315-5724.bin` decodes completely into valid MB86233 DSP instructions; it functions deterministically and stably in gameplay. However, per the directive: *"BAD_DUMP bytes are not unquestionable silicon truth... Do not patch dumps or remove BAD_DUMP without independent evidence"*, the `BAD_DUMP` tag is maintained until verified physical decapped re-dumps are released.
- Driver working status: *Virtua Fighter* boots, accepts coins, calibrates inputs, plays full fighting rounds with accurate physics and collision, renders all 3D geometries and 2D tilemaps, and supports save states.

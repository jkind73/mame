# Saturn/ST-V Bus and Execution Handoff — Core Contracts
**Status:** Implemented BUS-01/02/03 v2 — Agent A ownership SYS-CLK01/SYS-MEM01/CPU-04/BUS-01..03/SCU-02..04/DSP-02/03/DCC-01
**Baseline:** 03c19a78e4cee7e9008a1100118934e8d84c0ea5 (arena/01a0ac88-mame)
**Date:** 2026-09-16 UTC — Updated with BUS-02/03 implementation
**Branch:** arena/01a0ac88-mame (PR #4 merged d98482eb, continuing)

This file defines the exact API signatures and contracts required before implementing coherent bus arbitration and deferred CPU transactions. It is the blocking prerequisite for BUS-01/02/03 and CPU-04.

## Current Implementation Snapshot (BUS-02/03)

Implemented in `src/mame/sega/saturn_bus.{h,cpp}`, `saturn.h/.cpp`, `sat_console.cpp`, `stv.cpp`, `saturn_scu.cpp`:

```cpp
// saturn_bus.h — master and bus enums (exact)
enum saturn_bus_master : uint8_t {
    SATURN_MASTER_NONE = 0xff,
    SATURN_MASTER_MAIN_SH2 = 0,
    SATURN_MASTER_SLAVE_SH2,
    SATURN_MASTER_SCU_DMA0,
    SATURN_MASTER_SCU_DMA1,
    SATURN_MASTER_SCU_DMA2,
    SATURN_MASTER_SCU_DSP,
    SATURN_MASTER_SOUND_68K,
    SATURN_MASTER_VDP1,
    SATURN_MASTER_VDP2,
    SATURN_MASTER_CD_BLOCK,
    SATURN_MASTER_COUNT
};
enum saturn_bus_type : uint8_t {
    SATURN_BUS_A = 0,
    SATURN_BUS_B,
    SATURN_BUS_C,
    SATURN_BUS_SCU_REG,
    SATURN_BUS_DSP,
    SATURN_BUS_COUNT
};
struct saturn_bus_transaction {
    uint32_t address;
    uint8_t  size;
    bool     is_write;
    bool     is_fetch;
    bool     is_burst;
    saturn_bus_master master;
    saturn_bus_type   bus;
    uint16_t flags;   // from SCU get_address_flags
    int      penalty;  // AnNW+3 etc
    bool     committed;
};
using saturn_bus_ready_cb = std::function<bool (const saturn_bus_transaction &)>;
class saturn_bus_device : public device_t {
    bool request_bus(saturn_bus_type bus, saturn_bus_master master, bool burst=false);
    void release_bus(saturn_bus_type bus, saturn_bus_master master);
    void release_all(saturn_bus_master master);
    bool is_bus_owned(saturn_bus_type bus, saturn_bus_master *owner=nullptr) const;
    uint32_t get_cpu_wait(offs_t offset, bool is_write, saturn_bus_master cpu_master);
    void set_ready_cb(saturn_bus_type bus, saturn_bus_ready_cb cb);
    bool acquire_dma_buses(uint8_t level, uint16_t src_flags, uint16_t dst_flags, int src_penalty, int dst_penalty);
    void release_dma_buses(uint8_t level);
    void set_asr_regs(uint32_t asr0, uint32_t asr1, uint32_t aref);
};
```

```cpp
// saturn.h — readiness gates (exact)
bool is_vdp1_cpu_accessible(uint32_t address) const; // checks m_vdp1_legacy.drawing, vblank_erase_active, display_erase.pending
bool is_vdp2_cpu_accessible(uint32_t address) const; // if address in 0x05E00000-05EFFFFF, calls vdp2_normal_vram_access(addr,0)
bool vdp2_normal_vram_access(uint32_t address, unsigned command) const; // existing, command 0=CPU
```

```cpp
// sat_console.cpp / stv.cpp machine_start wiring (exact)
m_bus->set_ready_cb(SATURN_BUS_B, [this](const saturn_bus_transaction &t)->bool {
    if (t.flags == B_BUS_VDP1) return is_vdp1_cpu_accessible(t.address);
    if (t.flags == B_BUS_VDP2) return is_vdp2_cpu_accessible(t.address);
    return true;
});
```

```cpp
// saturn_bus.cpp flags_to_penalty (exact, MiSTer a95b085 derived)
case B_BUS_VDP1: return is_write ? 14 : 9;
case B_BUS_VDP2: return is_write ? 20 : 3;
case B_BUS_SCSP: return is_write ? 24 : 13;
case B_BUS_SCU:  return is_write ? 8 : 4;
```

```cpp
// saturn_scu.cpp DSP arbitration (exact)
m_scudsp->out_ddmv_callback().set([this](int state){
    if(state){ m_dma_status|=DMA_DSP_MOVE; m_bus->request_bus(SATURN_BUS_A, SATURN_MASTER_SCU_DSP, true); m_bus->request_bus(SATURN_BUS_B, SATURN_MASTER_SCU_DSP, true); m_bus->request_bus(SATURN_BUS_C, SATURN_MASTER_SCU_DSP, false); }
    else { m_dma_status&=~DMA_DSP_MOVE; m_bus->release_all(SATURN_MASTER_SCU_DSP); }
});
```

**Contracts preserved:** No host sleeps, devices/delegates via std::function (ready_cb), no game-name tests, penalties from ASR or MiSTer documented B-Bus table, not guessed.

## 1. Time Units

- **Primary time base:** `attotime` derived from device clocks. No host `sleep`, no `std::this_thread::sleep`, no wall-clock delays.
- **SCU reference:** `MASTER_CLOCK_352 = 14.31818 MHz *4 = 57.272727 MHz` divided: SCU runs at `/4 = 14.31818175 MHz`. DMA tick timer uses `m_dma_clock_ref = clock()/1` (currently SCU clock). Future: `clock()/1` for SCU, `clock()/4` for DSP DMA alignment after hardware audit.
- **SH-2 reference:** `MASTER_CLOCK_352/2 = 28.6363635 MHz`. `sh2_device::m_program` accesses occur at CPU clock. Bus arbitration converts penalties to SH-2 cycles via `adjust_icount(-penalty)` or timer scheduling, never via immediate subtraction without grant.
- **All delays** expressed as `attotime::from_ticks(ticks, clock)` or `from_nsec()`. No guessed constants: penalties come from ASR registers (`A0NW+3`, etc.) or documented bus widths. Undocumented penalties are `R` (research required) and must not be hardcoded.
- **DCC interleave:** `INTERLEAVE_DIV=32`, `INTERLEAVE_DURATION=1666us` is a temporary quantum workaround. Real fix requires transaction grant yield, not quantum tuning.

## 2. Master IDs

```cpp
enum saturn_bus_master : uint8_t {
    SATURN_MASTER_MAIN_SH2 = 0,
    SATURN_MASTER_SLAVE_SH2,
    SATURN_MASTER_SCU_DMA0,
    SATURN_MASTER_SCU_DMA1,
    SATURN_MASTER_SCU_DMA2,
    SATURN_MASTER_SCU_DSP,      // DSP DMA engine, not DSP CPU execution
    SATURN_MASTER_SOUND_68K,
    SATURN_MASTER_VDP1,         // VDP1 internal fetch/framebuffer ownership
    SATURN_MASTER_VDP2,         // VDP2 display fetch (for readiness)
    SATURN_MASTER_CD_BLOCK,     // CD block FIFO DMA
    SATURN_MASTER_SCSP_DMA,     // SCSP DMA (if separated)
    SATURN_MASTER_COUNT
};
```

- **Ownership rule:** Only one master may own a given bus at a time. Ownership is per bus type, not global.
- **HALT vs steal:** `MAIN` and `SOUND` HALT lines are ORed from independent owners (SMPC, SCU main/slave/sound). `saturn_state::reset_halt_state()` / `update_halt_lines()` is canonical. New arbiter must call `main_dtack_cb` / `sound_dtack_cb` for HALT and `main_steal_cb` / `sound_steal_cb` for cycle steal, preserving existing SMPC halt.

## 3. Bus Types and Address/Width/Mask

```cpp
enum saturn_bus_type : uint8_t {
    SATURN_BUS_A = 0,   // 0x02000000-0x058FFFFF: CS0/CS1/CS2/DUMMY
    SATURN_BUS_B,       // 0x05900000-0x05FFFFFF: SCSP/VDP1/VDP2/SCU regs
    SATURN_BUS_C,       // 0x06000000-0x07FFFFFF: WorkRAM-H mirrored
    SATURN_BUS_SCU_REG, // 0x05FE0000-0x05FE00CF internal
    SATURN_BUS_DSP,     // DSP program/data RAM internal
    SATURN_BUS_COUNT
};

struct saturn_bus_transaction {
    uint32_t address;       // 27-bit masked: address & 0x07FFFFFF, bit29 stripped (cache alias)
    uint32_t data;          // for writes: valid up to size
    uint8_t  size;          // 1,2,4 bytes; SCU DMA always 2 bytes except CD 4-byte
    uint8_t  mem_mask;      // MAME mem_mask for byte lanes, or derived from size
    bool     is_write;
    bool     is_fetch;      // instruction fetch vs data
    bool     is_burst;      // true for direct DMA burst, false for indirect cycle-steal
    saturn_bus_master master;
    saturn_bus_type   bus;
    uint16_t flags;         // A_BUS_CS0 etc from get_address_flags(), for penalty
    int      penalty;       // wait-state penalty from ASR: AnNW+3, or B-Bus device penalty
    // Deferred state:
    bool     committed;     // true after physical access, before completion IRQ
    bool     needs_retry;   // true if bus was busy, must replay without side effects
};
```

- **Address decode:** `get_address_flags()` returns `(flags, penalty)` using ASR0/ASR1 for A-Bus. `0x06000000` and `0x07000000` both decode as `C_BUS` (high work RAM mirror). `0x05FE` decodes as `B_BUS_SCU` but is illegal for SCU DMA (must raise DMAILL). Cache-through aliases `0x20000000` and `0x21000000/0x21800000` for MINIT/SINIT are stripped to physical before bus classification.
- **Width/mask:** SH-2 `read_byte/word/long` and `write_*` currently use `m_program->read/write` with `0x40000000` purge mask and `m_am=0x07FFFFFF` DRC mask. Future: transaction size must be preserved. For DMA, `dma_read_word()` buffering already implements longword->halfword conversion per ST-097 3.2; do not reintroduce fixed-source halfword repeat bug.
- **Save/load:** Transaction's `live_src/dst/size/count/read_buffer` already saved for DMA. For CPUs, pending transaction must be saved.

## 4. Readiness vs Committed Access

Two-phase model required to prevent immediate completion when device not ready:

```cpp
// Device readiness delegate: returns true if device can accept access NOW.
// If false, arbiter keeps transaction in WAIT and does not advance live pointers.
using saturn_bus_ready_delegate = device_delegate<bool (const saturn_bus_transaction &trans)>;

// Transaction completion delegate: called after physical memory access, before bus release.
using saturn_bus_complete_delegate = device_delegate<void (const saturn_bus_transaction &trans)>;
```

- **Readiness examples:**
  - VDP1: `vdp1_framebuffer0_r/w` ready only when not in active display erase and not drawing to that bank. Command/texture fetch ready only when VDP1 not in raster slice.
  - VDP2: CPU VRAM access ready only when `vdp2_normal_vram_access(address, command)` per `V2-T02` slot/partition/rotation ownership. Display fetch has priority over CPU.
  - SCSP: sound RAM ready always, but SCSP register access may have wait.
  - CD: FIFO ready only when DRDY set.

- **Committed:** After `m_hostspace->read/write` actually executed, transaction is committed. Live pointers advance, but bus still owned until completion tick. IRQ generation (DMA end, VDP1 end) happens after committed phase, not before.

- **Current gap:** `dma_hog_bus()` uses `adjust_icount(-hog)` which is cycle-steal approximation, not true HALT/grant. It does not check VDP1/VDP2 readiness. Must be replaced by grant check.

## 5. Arbitration Priority and Device API

### 5.1 New arbiter device (proposed)

```cpp
class saturn_bus_arbiter_device : public device_t {
public:
    // Request bus ownership. Returns true if granted immediately, false if queued.
    // If false, requester must suspend (CPU: save pending transaction, yield).
    bool request_access(saturn_bus_transaction &trans, device_t *requester,
                        saturn_bus_ready_delegate ready_cb = {},
                        saturn_bus_complete_delegate complete_cb = {});

    void release_bus(saturn_bus_type bus, saturn_bus_master master);
    bool is_bus_owned(saturn_bus_type bus, saturn_bus_master *owner = nullptr) const;

    // Device readiness registration (VDP1/VDP2/SCSP/CD)
    void set_device_ready_cb(saturn_bus_type bus, saturn_bus_ready_delegate cb);

    // For SCU DMA: query if bus can be preempted by higher level
    std::tuple<int,int> check_dma_levels() const; // (move_level, wait_level)

    // Save/load: pending transactions per master
    // void device_start() saves pending queue
};
```

- **Priority order (ST-097 3.2, ST-210 20/35):** Level 2 highest, then 1, then 0. Only two simultaneous DMA channels guarantee priority; starting level 2 during level 1 is prohibited (must not be used in tests). DSP DMA vs CPU DMA: DSP MOVE yields SCU DMA tick (existing `DMA_DSP_MOVE` check in `dma_tick_cb`), but DSP should not hard-assert HALT; it should use arbiter.
- **Preemption:** When higher priority arrives, current MOVE goes to WAIT, preserving `live_src/dst/count/read_buffer`. Lower priority resumes after higher completes. Current code in `dma_tick_cb` does this but uses `m_main_dtack_cb(direct)` for ownership; new arbiter must preserve that semantic but via grant API.
- **Held triggers:** ST-210 21-23: enable AND matching start factor, hold one trigger during DMA, execute after completion, do not rewrite active registers. Already implemented via `pending_trigger` bool; must be preserved in new arbiter.

### 5.2 SH-2 CPU-04 Deferred Transaction API

Current `sh2.cpp` `read_byte/word/long` and `write_*` are immediate:

```cpp
uint8_t sh2_device::read_byte(offs_t A) { return m_program->read_byte(A & AM); }
```

Required for BUS-01/02:

```cpp
// In sh2_device (interpreter and DRC):
struct sh2_pending_transaction {
    saturn_bus_transaction trans;
    bool active;
    uint32_t result; // for reads
};

bool sh2_try_access(saturn_bus_transaction &trans); // returns false if bus busy -> save pending
void sh2_resume_pending(); // called by arbiter grant callback
void sh2_save_pending_state(); // for save/load
```

- **DRC:** `static_generate_memory_accessor()` currently emits `UML_READ/WRITE` directly. Must emit call to arbiter that can suspend DRC execution (like `sh2_notify_dma_data_available` does for DMAC). Use `m_dma_kludge_cb` pattern as reference but for bus grant.
- **Interpreter:** `execute_run()` loop must check pending transaction before next instruction, not duplicate side effects.
- **No duplication:** Resume at granted access without re-executing instruction's side effects (e.g., post-increment). Save PC, instruction, and transaction.

### 5.3 SCU DMA Integration

- `trigger_dma_direct/indirect` must call `arbiter->request_access()` instead of directly setting `DMA_STATE_WAIT` and scheduling tick.
- `dma_tick_cb` must check `arbiter->is_bus_owned()` and `ready_cb()` before `dma_transfer_*`. If not ready, stay in WAIT, do not advance `live_count`.
- `dma_hog_bus()` becomes `arbiter->charge_penalty(level)` which calls steal callbacks only after grant confirmed.
- Preserve existing illegal checks: same-bus, B_BUS_SCU, A-Bus dest, VDP2 src, etc.

### 5.4 SCU DSP (DSP-02/03)

Current `scudsp.cpp`:
- DMA states WAIT/MOVE/IDLE, WAIT 4 ticks, MOVE per tick.
- `INPUT_LINE_HALT` asserted during DMA (wrong, should be bus ownership).
- `m_program->read_word` etc. for DMA uses `scudsp_dma_r/w` which calls `m_hostspace->read/write` via SCU.

Required:
- DSP DMA must request B/C bus via arbiter, not HALT line.
- T0F flag semantics preserved.
- Save/load of `m_dma` struct plus pending bus ownership.

## 6. IRQ Ordering

- **Levels (ST-097 Table 2.1):** 15:VBlank-In, 14:VBlank-Out, 13:HBlank-In, 12:Timer0, 11:Timer1, 10:DSP End, 9:SCSP, 8:SMPC/PAD, 6:DMA LV2/LV1, 5:DMA LV0, 3:DMA Illegal, 2:VDP1 End, 7:A-Bus Ext 0-3 (vectors 0x50-0x53), 4:A-Bus Ext 4-7 (0x54-0x57), 1:A-Bus Ext 8-15 (0x58-0x5F).
- **Mask reset:** On `irq_ack_cb` (vector fetch), `m_ism = 0xBFFF` (all masked). Pending IST bits survive. `m_current_irq_level` gates re-evaluation. This fixes Rayman SMPC INTBACK race.
- **A-Bus external:** IMS15 is active-high mask (1=mask), not enable. `m_abus_pending_ack` latch prevents re-delivery until AIACK write bit0=1. `abus_external_interrupt(index, state)` latches IST.
- **DMA IRQ:** `IST_DMALV0/1/2` set only after `done` true and `live_count >= live_size`. No IRQ on forced stop (DSTP 0x05FE0060 bit0). `dma_force_stop_w` clears MOVE/WAIT/BK, stops timer, preserves programmed regs, no IRQ.
- **Timer0:** VBlank-Out resets counter, compare zero generates Timer0 immediately if TENB set (ST-210 30). HBlank increments counter before compare (increment-before-compare). TENB gates counting.
- **Timer1:** HBlank loads only when stopped (`enabled() && !expire().is_never()` check). Zero count means 512. T1MD selects every line vs Timer0 hit only.

## 7. Save/Load of Pending Transactions

- All pending transactions must be in `save_item`:
  - SCU DMA: `live_src/dst/size/count`, `read_buffer`, `read_address`, `read_offset`, `read_buffer_valid`, `indirect_fetch_phase`, `pending_trigger`, `mode`, `done`, `bbus_sound_access`, `transfer_penalty`.
  - SH-2: `sh2_pending_transaction` with address, size, is_write, data, PC, active flag.
  - DSP: `m_dma.src/dst/add/size/update/ex/dir/count` plus `m_dma_state`.
  - Bus arbiter: queue of waiting masters per bus, current owner per bus.
- Postload must reapply HALT lines via `update_halt_lines()` and restore timer scheduling (`dma_tick_timer` adjust if any MOVE/WAIT active).

## 8. Clock/Reset/Memory Contracts (SYS-CLK01/SYS-MEM01)

- **Clocks:** SH-2 28.63636 MHz, SCU 14.31818 MHz, SCSP 11.2896 MHz, M68K 11.2896 MHz, SCU DSP 14.31818 MHz, CD 20 MHz? Verify via `device_clock_changed()`. DOTSEL changes must not reset sound (existing correction preserved).
- **Reset order:** SMPC system reset -> SCU reset (releases SCU-owned HALT only) -> SH-2 reset (master/slave via `master_sh2_reset_w`/`slave_sh2_reset_w`) -> sound reset (`sound_68k_reset_w` with full SCSP interrupt/timer reset per ST-169 30-31). `device_reset_after_children` for SCU DSP.
- **Memory:** Low WorkRAM 0x00200000-0x002FFFFF mirrored 0x20200000, High WorkRAM 0x06000000-0x060FFFFF mirrored 0x07000000-0x07FFFFFF and 0x26000000 etc (27-bit mask). BIOS 0x00000000-0x0007FFFF mirrored 0x20000000. Sound RAM 0x05A00000-0x05A7FFFF mirrored 0x05A80000 (512KB). SCSP regs 0x05B00000 mirrored. VDP1 VRAM 0x05C00000, FB 0x05C80000, regs 0x05D00000. VDP2 VRAM 0x05E00000 with VRSIZE wrap, CRAM 0x05F00000, regs 0x05F80000. SCU regs 0x05FE0000-0x05FE00CF. A-Bus dummy 0x05000000-0x057FFFFF returns -1 but logs. Cartridge area 0x02000000-0x04FFFFFF handled via slot.
- **Open-bus:** Unmapped reads return 0xFFFFFFFF? Current `saturn_null_ram_r` returns -1 for 0x02400000-0x027FFFFF unmapped. Must qualify via hardware, not assume zero. Preserve `abus_dummy_r` logging.

## 9. DCC and SMPC Clocks (DCC-01, SMPC-01..04)

- **DCC:** MINIT/SINIT triggers are 16-bit writes only (`mem_mask == 0xFFFF` or `0xFFFF0000` with correct data lane). Cache-through aliases at 0x21000000/0x21800000 must reach bus, not sit in cache. `add_quantum` with `INTERLEAVE_DIV 32` / `1666us` is workaround; real fix is bus grant yield.
- **SMPC:** Command timings from `cmd_table_timing`: 30us..320ms, INTBACK multi-phase, CONTINUE 700us, CKCHG 5 ticks with syshalt 3-4 frames. IOSEL/EXLE reset false per ST-169 Table 3.1. SR 0x40 always-on, SF/CD_SF handshake. RTC BCD.

## 10. Testing Constraints

- **No game-name tests:** Do not write `if (game == "afterburner2")`. Use bus type, address, size, master ID.
- **No host sleeps:** Use `emu_timer` or `adjust_icount`.
- **No guessed delays:** Penalties from ASR or documented B-Bus device waits only. If undocumented, mark `TODO` and keep bus immediate but log.
- **Devices/delegates:** All cross-device calls via `devcb_write_line`, `devcb_write8`, `device_delegate`, not direct pointers except `m_hostspace` for memory (already present).
- **Regtests:** Existing `test_dma_bus.py`, `test_dma_indirect.py`, `test_scu_abus.py`, `test_scu_irqs.py`, `test_timer0.py`, `test_timer1.py`, `test_halt.py`, `test_sync.py`, `test_sh_delay_irq.py`, `test_smpc_handshake.py` must continue passing. New tests must use production callback extraction, ASan/UBSan, not fake executables.

## 11. Implementation Order (from saturn_stv_completion.md)

1. SYS-CLK01/SYS-MEM01 qualification (this file documents current known values)
2. CPU-04 deferred transactions (SH-2 interpreter + DRC)
3. BUS-01/02/03 arbiter with readiness vs committed
4. SCU-02/03/04 DMA timing with real grants
5. DSP-02/03 bus interaction
6. DCC-01 writer-origin and FRT sync
7. SMPC-01..04 handshake/timing
8. Full regressions: `validate_build.py` + linked BIOS replays

## 12. Source Manifest (for license tracking)

- Primary: Sega ST-097-R5 (SCU), ST-058-R4 (VDP2), ST-013-R3 (VDP1), ST-077 (sound map), ST-169 (SMPC), ST-210 (SCU errata), Hitachi SH7604 HW manual.
- Pinned emulators: Ymir 6d779960, MiSTer a95b085, mednafen f0ee9d59, Yabause 82cb2917, SaturnRecomp 26c9715e, saturnsdk 0fab2c30, Cassini (to be pinned).
- No code imported yet in this branch; this file is documentation only. Future imports must note file, revision, license, and attribution in commit message.

## 13. Open Questions (R)

- B-Bus device wait penalties: VDP1 9/14, VDP2 3/20, SCSP 13/24, SCU 4/8 (MiSTer) vs dynamic ARWT? Need hardware measurement.
- SCU DMA burst vs cycle-steal: ST-097 says direct is burst, indirect is cycle-steal, but penalty calculation for burst? Current `extra_penalty = transfer_penalty` approximates stall without HALT deadlock.
- DSP DMA address-add/boundary rules: Does DSP DMA follow same C-Bus fixed add rule?
- SH-2 cache-through alias handling for DMA visibility: When does cache flush matter for SCU DMA source?
- VDP1/VDP2 readiness granularity: per-dot, per-line, per-command? Need to connect V2-T02 slot cache to bus arbiter.

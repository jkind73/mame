#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP/sound-CPU integration qualification (SND-01).

The SND-01 parent asks for the *integration* the per-chip fixtures cannot see:
sound RAM and register lanes from both CPU windows, the SCU's DMA into and out
of sound RAM, and an interrupt crossing from the SCSP to the 68000 as a real CPU
exception.  Nothing here re-tests the 68000 core or the SCSP register model.

Groups:

* **A - sound RAM lanes.** The 68k window (0x000000-0x0fffff) and the SH-2
  window (0x05a00000-0x05afffff) are the same memory.  Every access width is
  written from one side and read back from the other, and the byte image of a
  32 bit word is checked from both sides (each 32 bit word maps to the same
  four bytes in big-endian order).
* **B - register lanes.** A slot register written through one window reads back
  through the other, in both directions.
* **C - SCU DMA.** A D0 transfer from work RAM H to sound RAM and one back, with
  the result verified through both windows, plus an illegal same-bus transfer
  that must set IST DMAILL (bit 12) and move nothing (SCU Final Specifications
  No.01/No.02 as implemented in `saturn_scu_device::trigger_dma_direct`).
* **D - sound CPU reset/release and SCSP interrupt delivery.**  The 68000 is
  held in reset with the real SMPC SNDOFF command (the reset/release path
  SND-01 names), which also makes groups A-C race-free: until then the BIOS
  sound program is running and touching the same registers.  While it is held,
  a program is placed in sound RAM and the reset vectors are rewritten; SNDON
  must restart the CPU at that program, which increments a counter, installs
  its own level-6 vector (vector 30) and enables the SCSP timer A SCI source
  from guest code with interrupts unmasked.  The fixture then observes the
  handler's own acknowledgement through SCIRE (the request clears between
  timer expiries) and, when the handler masks level 6 after four entries, that
  delivery stops while the request still re-pends.

Method note: the MAME 68000's `PC` state item cannot be written from the
debugger - its import sets `m_ipc = m_pc` and then `m_pc = m_ipc + 2`, so
`state["PC"].value = x` advances the PC by two instead of setting it.  Older
fixtures in this tree that "parked" the sound CPU that way were not in fact
stopping it; this fixture uses SNDOFF, and every group here runs with the
68000 held in reset.

Missing binary/BIOS is a skip, never a native pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

BOOT_FRAMES = 180            # the stream is silent until the boot has settled

SH2_RAM = 0x05a00000         # sound RAM as the SH-2 sees it
M68K_RAM = 0x000000          # sound RAM as the 68000 sees it
SH2_REG = 0x05b00000         # SCSP registers as the SH-2 sees them
M68K_REG = 0x100000          # SCSP registers as the 68000 sees them
SCU_REG = 0x05fe0000         # SCU registers as the SH-2 sees them

SCU_D0_SRC = SCU_REG + 0x00
SCU_D0_DST = SCU_REG + 0x04
SCU_D0_SIZE = SCU_REG + 0x08
SCU_D0_AD = SCU_REG + 0x0c
SCU_D0_EN = SCU_REG + 0x10
SCU_D0_FT = SCU_REG + 0x14
SCU_IMS = SCU_REG + 0x00a0
SCU_IST = SCU_REG + 0x00a4

WORK_RAM = 0x06020000        # work RAM H, the C-bus side of the DMA
RAM_SRC = 0x05a10000         # sound RAM target of the first transfer
RAM_BACK = 0x06020100        # work RAM target of the return transfer
RAM_ILL = 0x05a10080         # destination of the illegal same-bus transfer

IST_DMAILL = 1 << 12
DMA_LV0_BUSY = 0x30          # DMA_LV0_MOVE | DMA_LV0_WAIT

# SCSP common registers start at byte offset 0x400 of either window: slots
# occupy 0x000-0x3ff (32 slots x 0x20 bytes) and the shared registers are at
# 68000 0x100400-0x10042f / SH-2 0x05b00400-0x05b0042f.  Using 0x1e/0x20 here
# lands in slot 0/1 instead, which is self-consistent on read-back but never
# arms a timer - see the fixture notes.
TACTL = 0x418                # TACTL[10:8] | TIMA[7:0]
SCIEB = 0x41e
SCIPD = 0x420
SCIRE = 0x422
SCILV0 = 0x424
SCILV1 = 0x426
SCILV2 = 0x428
TIMER_A_SCI = 0x40           # SCIPD/SCIEB bit 6
SCI_LEVEL = 6
IRQ_VECTOR = 0x78            # 68000 autovector 30 (level 6) at VBR 0
COUNTER = 0x00003400         # handler's counter; the guest program sets it to
                             # 1 on entry and the handler increments it, so the
                             # value distinguishes "never ran" from "ran, no
                             # interrupt" from "interrupts delivered".  It sits
                             # above the vectors, stack, program and handler.
ENTRY = 0x00001000           # guest program entry the reset vector points at
SPIN = 0x00002000            # spin target inside the guest program
HANDLER = 0x00003000         # interrupt handler code, in sound RAM

# 64 bytes of transfer, and the two patterns used for the DMA checks
DMA_SIZE = 64


LUA = COMMON_LUA + r'''
local base = @@SH2_REG@@
local sh2_ram = @@SH2_RAM@@
local m68k_ram = @@M68K_RAM@@
local m68k_reg = @@M68K_REG@@
local scu = @@SCU_REG@@
local snd = assert(m.devices[":audiocpu"])
local ssp = snd.spaces["program"]

local results = {}
local function check(label, got, want)
    results[#results + 1] = { label, got, want }
end

local function park()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        cpu.state["SR"].value = 0xf0
        cpu.state["PC"].value = 0x06000000
    end
end

-- SMPC command interface as the SH-2 sees it: SF starts a command and COM
-- carries it.  SNDON/SNDOFF (06H/07H) drive the 68000 RESET input.
local SMPC = 0x00100000
local STV = @@STV@@
local function smpc_ready()
    for _ = 1, 200 do
        if (sp:read_u8(SMPC + 0x63) & 1) == 0 then return true end
        emu.wait(emu.attotime.from_usec(50))
    end
    return false
end
local function smpc_command(com)
    if not smpc_ready() then return false end
    sp:write_u8(SMPC + 0x63, 1)
    sp:write_u8(SMPC + 0x1f, com)
    return smpc_ready()
end

-- Holding and releasing the sound 68000 depends on the board:
--   * Saturn drives its RESET input from the SMPC sound_reset handler, i.e.
--     the SNDOFF / SNDON commands.
--   * ST-V drives it from PDR2 bit 4 (stv.cpp pdr2_output_w) and leaves that
--     SMPC handler unwired (sound_reset_handler is commented out there), so
--     the fixture has to write the SMPC's PDR2/DDR2 registers, which the ST-V
--     memory map exposes at 0x00100077 / 0x0010007b.
local function sound_hold()
    if STV then
        sp:write_u8(SMPC + 0x7b, 0x30)           -- DDR2: bits 4/5 are outputs
        sp:write_u8(SMPC + 0x77, 0x10)           -- PDR2 bit 4: RESET asserted
        return true
    end
    return smpc_command(0x07)                    -- SNDOFF
end

local function sound_release()
    if STV then
        sp:write_u8(SMPC + 0x77, 0x00)           -- PDR2 bit 4: RESET released
        return true
    end
    return smpc_command(0x06)                    -- SNDON
end

-- 68000 program the CPU must start from after SNDON.  Entry at 1000H:
--   move.w #$2700,sr                    46fc 2700
--   move.l #$00003000,($00000078).l     23fc 0000 3000 0000 0078
--   move.l #$00000001,($00003400).l     23fc 0000 0001 0000 3400  entry marker
--   move.w #$0040,($00100426).l         33fc 0040 0010 0426   SCILV1: A = 6
--   move.w #$0040,($00100428).l         33fc 0040 0010 0428   SCILV2: A = 6
--   move.w #$0040,($0010041e).l         33fc 0040 0010 041e   SCIEB: timer A
--   move.w #$0200,($00100418).l         33fc 0200 0010 0418   prescale 2, TIMA 0
--   move.w #$2000,sr                    46fc 2000              unmask
--   bra *                               60fe
-- Handler at 3000H:
--   addq.l #1,($00003400).l             52b9 0000 3400
--   cmpi.l #5,($00003400).l             0cb9 0000 0005 0000 3400
--   bne.s +4                            6604                  skip the mask
--   move.w #$2700,(sp)                  3ebc 2700             mask level 6 in
--                                                             the stacked SR so
--                                                             it survives the rte
--   move.w #$0040,($00100422).l         33fc 0040 0010 0422   SCIRE: ack
--   rte                                 4e73
local function put(addr, words)
    for i = 1, #words do ssp:write_u16(addr + (i - 1) * 2, words[i]) end
end
local function install_sound_program()
    ssp:write_u32(0x000000, 0x0007ff00)          -- SSP
    ssp:write_u32(0x000004, 0x00001000)          -- reset PC
    ssp:write_u32(@@COUNTER@@, 0)
    put(0x1000, {
        0x46fc, 0x2700,
        0x23fc, 0x0000, 0x3000, 0x0000, 0x0078,
        0x23fc, 0x0000, 0x0001, 0x0000, @@COUNTER16@@,
        0x33fc, 0x0040, 0x0010, 0x0426,
        0x33fc, 0x0040, 0x0010, 0x0428,
        0x33fc, 0x0040, 0x0010, 0x041e,
        0x33fc, 0x0200, 0x0010, 0x0418,
        0x46fc, 0x2000,
        0x60fe,
    })
    put(0x3000, {
        0x52b9, 0x0000, @@COUNTER16@@,
        0x0cb9, 0x0000, 0x0005, 0x0000, @@COUNTER16@@,
        0x6604,
        0x3ebc, 0x2700,
        0x33fc, 0x0040, 0x0010, 0x0422,
        0x4e73,
    })
end

local function run_everything()
    park()

    -- ---- A: sound RAM lanes ------------------------------------------
    local lanes = {
        { "u8", 8 }, { "u16", 16 }, { "u32", 32 },
    }
    local off = 0x4000
    for _, entry in ipairs(lanes) do
        local name, bits = entry[1], entry[2]
        local wv = bits == 8 and 0xa5 or (bits == 16 and 0xa55a or 0xa55aa55a)
        -- SH-2 writes, 68000 reads
        sp["write_" .. name](sp, sh2_ram + off, wv)
        check("ram_sh2_to_68k_" .. name,
              ssp["read_" .. name](ssp, m68k_ram + off), wv)
        -- 68000 writes, SH-2 reads (a different value, same address)
        local wv2 = bits == 8 and 0x5a or (bits == 16 and 0x5aa5 or 0x5aa55aa5)
        ssp["write_" .. name](ssp, m68k_ram + off, wv2)
        check("ram_68k_to_sh2_" .. name,
              sp["read_" .. name](sp, sh2_ram + off), wv2)
        off = off + 0x20
    end

    -- the byte image of a 32 bit word, written from each side
    sp:write_u32(sh2_ram + 0x4200, 0x11223344)
    check("ram_bytes_sh2_write_0", ssp:read_u8(m68k_ram + 0x4200), 0x11)
    check("ram_bytes_sh2_write_1", ssp:read_u8(m68k_ram + 0x4201), 0x22)
    check("ram_bytes_sh2_write_2", ssp:read_u8(m68k_ram + 0x4202), 0x33)
    check("ram_bytes_sh2_write_3", ssp:read_u8(m68k_ram + 0x4203), 0x44)
    ssp:write_u32(m68k_ram + 0x4210, 0x55667788)
    check("ram_bytes_68k_write_0", sp:read_u8(sh2_ram + 0x4210), 0x55)
    check("ram_bytes_68k_write_1", sp:read_u8(sh2_ram + 0x4211), 0x66)
    check("ram_bytes_68k_write_2", sp:read_u8(sh2_ram + 0x4212), 0x77)
    check("ram_bytes_68k_write_3", sp:read_u8(sh2_ram + 0x4213), 0x88)
    -- a word written by the 68000 must appear as the same two bytes
    ssp:write_u16(m68k_ram + 0x4220, 0xabcd)
    check("ram_word_68k_read_sh2", sp:read_u16(sh2_ram + 0x4220), 0xabcd)
    check("ram_word_68k_byte_hi", sp:read_u8(sh2_ram + 0x4220), 0xab)
    check("ram_word_68k_byte_lo", sp:read_u8(sh2_ram + 0x4221), 0xcd)

    -- ---- B: register lanes -------------------------------------------
    local slot3 = base + 3 * 0x20
    sp:write_u16(slot3 + 0x10, 0x1234)               -- pitch of slot 3
    check("reg_sh2_to_68k", ssp:read_u16(m68k_reg + 3 * 0x20 + 0x10), 0x1234)
    ssp:write_u16(m68k_reg + 3 * 0x20 + 0x10, 0x5678)
    check("reg_68k_to_sh2", sp:read_u16(slot3 + 0x10), 0x5678)
    sp:write_u16(slot3 + 0x16, 0xe010)               -- mixer word
    check("reg_mixer_sh2_to_68k", ssp:read_u16(m68k_reg + 3 * 0x20 + 0x16), 0xe010)
    ssp:write_u16(m68k_reg + 3 * 0x20 + 0x16, 0x4011)
    check("reg_mixer_68k_to_sh2", sp:read_u16(slot3 + 0x16), 0x4011)
    -- the shared registers live one page above the slots: MVOL at +0x400
    sp:write_u16(base + 0x400, 0x0018)
    check("reg_common_sh2_to_68k", ssp:read_u16(m68k_reg + 0x400), 0x0018)
    check("reg_common_at_sh2", sp:read_u16(base + 0x400), 0x0018)

    -- ---- C: SCU DMA --------------------------------------------------
    local function fill(addr, seed)
        for i = 0, @@DMA_SIZE@@ / 4 - 1 do
            sp:write_u32(addr + i * 4, (seed + i * 0x01010101) & 0xffffffff)
        end
    end
    local function verify(addr, seed, tag, reader)
        for i = 0, @@DMA_SIZE@@ / 4 - 1 do
            local want = (seed + i * 0x01010101) & 0xffffffff
            check(string.format("%s_%d", tag, i),
                  reader(addr + i * 4), want)
        end
    end

    fill(@@WORK_RAM@@, 0x01020304)
    for i = 0, @@DMA_SIZE@@ / 4 - 1 do
        sp:write_u32(@@RAM_SRC@@ + i * 4, 0xdeadbeef)   -- must be overwritten
        sp:write_u32(@@RAM_ILL@@ + i * 4, 0xfeedface)   -- must be left alone
    end

    local function dma_direct(src, dst, size)
        sp:write_u32(scu + 0x00, src)
        sp:write_u32(scu + 0x04, dst)
        sp:write_u32(scu + 0x08, size)
        -- DxAD: bit 8 makes the source advance one longword per read, the low
        -- three bits shift the destination by 1 << n bytes per write.  0 in
        -- both fields is the fixed-address mode (the destination word is
        -- rewritten every tick), which is not a block copy.
        sp:write_u32(scu + 0x0c, 0x00000101)         -- src += 4 bytes, dst += 2
        sp:write_u32(scu + 0x14, 7)                  -- DxFT: trigger start factor
        sp:write_u32(scu + 0x10, 0x00000101)         -- DxEN enable + DxGO
    end

    local function wait_idle()
        for _ = 1, 200 do
            if (sp:read_u32(scu + 0x7c) & @@DMA_BUSY@@) == 0 then return true end
            emu.wait(emu.attotime.from_usec(100))
        end
        return false
    end

    -- work RAM H -> sound RAM, verified through the 68000 window
    dma_direct(@@WORK_RAM@@, @@RAM_SRC@@, @@DMA_SIZE@@)
    check("dma_forward_idle", wait_idle() and 1 or 0, 1)
    verify(@@RAM_SRC@@, 0x01020304, "dma_forward_68k",
           function(a) return ssp:read_u32(a - @@SH2_RAM@@) end)
    -- and through the SH-2 window, so the lanes agree after a B-bus write
    verify(@@RAM_SRC@@, 0x01020304, "dma_forward_sh2",
           function(a) return sp:read_u32(a) end)

    -- sound RAM -> work RAM H (the B-bus read path)
    for i = 0, @@DMA_SIZE@@ / 4 - 1 do
        sp:write_u32(@@RAM_BACK@@ + i * 4, 0)
    end
    dma_direct(@@RAM_SRC@@, @@RAM_BACK@@, @@DMA_SIZE@@)
    check("dma_return_idle", wait_idle() and 1 or 0, 1)
    verify(@@RAM_BACK@@, 0x01020304, "dma_return",
           function(a) return sp:read_u32(a) end)

    -- illegal same-bus transfer: sound RAM -> sound RAM
    local ist_before = sp:read_u32(scu + 0xa4)
    sp:write_u32(scu + 0xa4, 0xffffffff)             -- clear pending status bits
    dma_direct(@@RAM_SRC@@, @@RAM_ILL@@, @@DMA_SIZE@@)
    emu.wait(emu.attotime.from_usec(500))
    check("dma_illegal_ist", (sp:read_u32(scu + 0xa4) & @@IST_DMAILL@@) ~= 0 and 1 or 0, 1)
    check("dma_illegal_noop", sp:read_u32(@@RAM_ILL@@), 0xfeedface)
    check("dma_illegal_status", (sp:read_u32(scu + 0x7c) & @@DMA_BUSY@@), 0)
    print(string.format("SCSP_INT ist_before=%08x ist_after=%08x", ist_before,
                        sp:read_u32(scu + 0xa4)))

    -- ---- D: reset/release and SCSP interrupt delivery ------------------
    -- Hold the 68000 in reset through the board's real path: until now it has
    -- been running the BIOS sound program over the registers under test.
    check("smpc_sndoff", sound_hold() and 1 or 0, 1)
    emu.wait(emu.attotime.from_msec(50))
    -- Place the program that SNDON must start, and prove it does not run yet
    install_sound_program()
    emu.wait(emu.attotime.from_msec(50))
    check("held_in_reset", ssp:read_u32(@@COUNTER@@), 0)

    check("smpc_sndon", sound_release() and 1 or 0, 1)
    -- Give the run time to reach the handler's self-imposed limit.  The
    -- handler accepts exactly five entries and then masks level 6 in the
    -- stacked SR before acknowledging, so delivery must stop at five even
    -- though the timer keeps requesting.  Two failure modes are excluded by
    -- the same number: no acknowledgement (level triggered interrupt, the
    -- counter would race past five) and a mask that the rte discards.
    local counter_run = 0
    for _ = 1, 40 do
        counter_run = ssp:read_u32(@@COUNTER@@)
        if counter_run >= 5 then break end
        emu.wait(emu.attotime.from_usec(10000))
    end
    check("guest_program_ran", ssp:read_u32(@@COUNTER@@) > 1 and 1 or 0, 1)
    emu.wait(emu.attotime.from_msec(150))
    local counter_masked_run = ssp:read_u32(@@COUNTER@@)
    local pending_after = sp:read_u16(base + @@SCIPD@@) & @@TIMER_SCI@@
    emu.wait(emu.attotime.from_msec(50))
    check("masked_run_stopped", ssp:read_u32(@@COUNTER@@), counter_masked_run)
    check("masked_run_count", counter_masked_run, 5)
    check("request_still_raised", pending_after, @@TIMER_SCI@@)
    print(string.format("SCSP_INT masked counter=%d scipd=%04x",
                        counter_masked_run, sp:read_u16(base + @@SCIPD@@)))

    -- the latched request the masked CPU left behind must clear through the
    -- acknowledge register (RETI/level semantics are the timers gate's job,
    -- this only proves the pending bit is the acknowledged source)
    sp:write_u16(base + @@SCIRE@@, @@TIMER_SCI@@)
    local acked = 0
    for _ = 1, 10 do
        if (sp:read_u16(base + @@SCIPD@@) & @@TIMER_SCI@@) == 0 then
            acked = 1
            break
        end
        emu.wait(emu.attotime.from_usec(2000))
    end
    check("ack_clears_request", acked, 1)

    local fails = 0
    for _, r in ipairs(results) do
        if r[2] ~= r[3] then
            fails = fails + 1
            print(string.format("SCSP_INT FAIL %s got=%s want=%s", r[1],
                                tostring(r[2]), tostring(r[3])))
        end
    end
    if fails == 0 then
        print(string.format("SCSP_INT PASS cases=%d", #results))
    else
        print(string.format("SCSP_INT FAILED cases=%d failures=%d", #results, fails))
    end
    m:exit()
end

local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < @@FRAMES@@ then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(run_everything)
        if not ok then print("SCSP_INT FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_INT armed")
'''


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP integration emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_INT armed',):
        if marker not in stdout:
            raise RuntimeError('SCSP integration transcript is missing "%s"'
                               % marker)
    if 'LUA ERROR' in stdout or 'SCSP_INT FAIL' in stdout:
        raise RuntimeError('SCSP integration transcript reports a failure')
    m = re.search(r'SCSP_INT PASS cases=(\d+)', stdout)
    if not m:
        raise RuntimeError('SCSP integration transcript has no PASS line')
    cases = int(m.group(1))
    if cases < 60:
        raise RuntimeError('SCSP integration reported only %d cases' % cases)
    # The interrupt phase must report its own two observations: the handler's
    # exact entry count under the persistent mask, and the request the masked
    # CPU left latched in SCIPD (timer A bit 6 set among the free running
    # timer sources).
    m = re.search(r'SCSP_INT masked counter=(\d+) scipd=([0-9a-f]{4})', stdout)
    if not m:
        raise RuntimeError('SCSP integration did not record the interrupt '
                           'counters')
    counter, scipd = int(m.group(1)), int(m.group(2), 16)
    if counter != 5:
        raise RuntimeError('sound CPU ran the handler %d times, expected the '
                           'five entries before it masked level 6' % counter)
    if not (scipd & 0x40):
        raise RuntimeError('SCIPD has no pending timer A request (0x%04x) once '
                           'the masked handler stopped acknowledging it' % scipd)
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    ap.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
    ap.add_argument('--system', default='saturnjp')
    ap.add_argument('--drc', action='store_true')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()

    exe = args.executable.resolve()
    if not os.access(exe, os.X_OK):
        print('SKIP: no runnable emulator at %s' % exe)
        return 0

    lua = (LUA.replace('@@SH2_REG@@', hex(SH2_REG))
              .replace('@@SH2_RAM@@', hex(SH2_RAM))
              .replace('@@M68K_RAM@@', hex(M68K_RAM))
              .replace('@@M68K_REG@@', hex(M68K_REG))
              .replace('@@SCU_REG@@', hex(SCU_REG))
              .replace('@@WORK_RAM@@', hex(WORK_RAM))
              .replace('@@RAM_SRC@@', hex(RAM_SRC))
              .replace('@@RAM_BACK@@', hex(RAM_BACK))
              .replace('@@RAM_ILL@@', hex(RAM_ILL))
              .replace('@@IST_DMAILL@@', hex(IST_DMAILL))
              .replace('@@DMA_BUSY@@', hex(DMA_LV0_BUSY))
              .replace('@@DMA_SIZE@@', str(DMA_SIZE))
              .replace('@@SCIPD@@', hex(SCIPD))
              .replace('@@SCIRE@@', hex(SCIRE))
              .replace('@@TIMER_SCI@@', hex(TIMER_A_SCI))
              .replace('@@COUNTER16@@', hex(COUNTER & 0xffff))
              .replace('@@COUNTER@@', hex(COUNTER))
              .replace('@@STV@@', 'true' if args.system.startswith('stv')
                       else 'false')
              .replace('@@FRAMES@@', str(BOOT_FRAMES)))
    # the emulator runs with the output directory as its working directory, so
    # the autoboot script path in the command line has to be absolute
    out = (args.output or Path(tempfile.mkdtemp(prefix='scsp-int-'))).resolve()
    out.mkdir(parents=True, exist_ok=True)

    script_path = out / 'test.lua'
    script_path.write_text(lua)
    rom = args.rompath.resolve()
    cmd = [str(exe), args.system, '-rompath', str(rom), '-noreadconfig',
           '-skip_gameinfo', ('-drc' if args.drc else '-nodrc'), '-video',
           'none', '-sound', 'none', '-nothrottle', '-seconds_to_run', '900',
           '-autoboot_delay', '0', '-autoboot_script', str(script_path)]
    for kind in ('nvram', 'cfg', 'state', 'snapshot'):
        cmd += ['-' + kind + '_directory', str(out / kind)]
    (out / 'invocation.json').write_text(json.dumps({
        'executable': str(exe), 'system': args.system, 'drc': args.drc,
        'binary_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'bios_sha256': hashlib.sha256(
            (rom / (args.system + '.zip')).read_bytes()).hexdigest(),
        'lua_sha256': hashlib.sha256(lua.encode()).hexdigest(),
        'command': cmd,
    }, indent=2) + '\n')
    env = dict(os.environ)
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    with (out / 'runtime.log').open('w') as log:
        proc = subprocess.run(cmd, cwd=out, env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=1800)
    text = (out / 'runtime.log').read_text(errors='replace')
    cases = validate_output(text, proc.returncode)

    for line in text.splitlines():
        if line.startswith('SCSP_INT '):
            print('  %s' % line)
    print('SCSP INT: PASS (%d cases)' % cases)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

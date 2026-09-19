
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local screen = m.screens[":screen"]
local C = 0x00100000
local I0,I1,I2,COM,OREG,SR,SF = C+1,C+3,C+5,C+0x1f,C+0x21,C+0x61,C+0x63
local fails, pads = {}, {}
local function check(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%x want=%x",label,got,want) end
end
local function ready()
    for n=1,80 do
        if (sp:read_u8(SF)&1)==0 then return end
        emu.wait(emu.attotime.from_usec(50))
    end
    error("SMPC SF timeout")
end
local function park()
    sp:write_u32(0x06000000,0xaffe0009)
    for _,tag in ipairs({":maincpu",":slave"}) do
        local cpu=m.devices[tag]
        cpu.state["SR"].value=0xf0;cpu.state["PC"].value=0x06000000
    end
end
local function wait_vblank()
    -- Observe the device/SCU edge, not screen blank (one scanline earlier).
    -- Both SH-2s are parked with IRQs masked, so they cannot acknowledge it.
    sp:write_u32(0x05fe00a4,0xfffffffe)
    for n=1,800 do
        if (sp:read_u32(0x05fe00a4)&1)~=0 then return end
        emu.wait(emu.attotime.from_usec(50))
    end
    error("SCU VBlank-IN timeout")
end
local buttons={{"A",0x0400},{"B",0x0100},{"X",0x0040},{"Y",0x0020}}
local function set_pad(index, pattern)
    local word=0xffff
    for bit,entry in ipairs(buttons) do
        local pressed=(pattern>>(bit-1))&1
        pads[index].fields[entry[1]]:set_value(pressed)
        if pressed==1 then word=word & ~entry[2] end
    end
    return word
end

local base = 0x5b00000
local sh2_ram = 0x5a00000
local m68k_ram = 0x0
local m68k_reg = 0x100000
local scu = 0x5fe0000
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
local STV = false
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
    ssp:write_u32(0x3400, 0)
    put(0x1000, {
        0x46fc, 0x2700,
        0x23fc, 0x0000, 0x3000, 0x0000, 0x0078,
        0x23fc, 0x0000, 0x0001, 0x0000, 0x3400,
        0x33fc, 0x0040, 0x0010, 0x0426,
        0x33fc, 0x0040, 0x0010, 0x0428,
        0x33fc, 0x0040, 0x0010, 0x041e,
        0x33fc, 0x0200, 0x0010, 0x0418,
        0x46fc, 0x2000,
        0x60fe,
    })
    put(0x3000, {
        0x52b9, 0x0000, 0x3400,
        0x0cb9, 0x0000, 0x0005, 0x0000, 0x3400,
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
        for i = 0, 64 / 4 - 1 do
            sp:write_u32(addr + i * 4, (seed + i * 0x01010101) & 0xffffffff)
        end
    end
    local function verify(addr, seed, tag, reader)
        for i = 0, 64 / 4 - 1 do
            local want = (seed + i * 0x01010101) & 0xffffffff
            check(string.format("%s_%d", tag, i),
                  reader(addr + i * 4), want)
        end
    end

    fill(0x6020000, 0x01020304)
    for i = 0, 64 / 4 - 1 do
        sp:write_u32(0x5a10000 + i * 4, 0xdeadbeef)   -- must be overwritten
        sp:write_u32(0x5a10080 + i * 4, 0xfeedface)   -- must be left alone
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
            if (sp:read_u32(scu + 0x7c) & 0x30) == 0 then return true end
            emu.wait(emu.attotime.from_usec(100))
        end
        return false
    end

    -- work RAM H -> sound RAM, verified through the 68000 window
    dma_direct(0x6020000, 0x5a10000, 64)
    check("dma_forward_idle", wait_idle() and 1 or 0, 1)
    verify(0x5a10000, 0x01020304, "dma_forward_68k",
           function(a) return ssp:read_u32(a - 0x5a00000) end)
    -- and through the SH-2 window, so the lanes agree after a B-bus write
    verify(0x5a10000, 0x01020304, "dma_forward_sh2",
           function(a) return sp:read_u32(a) end)

    -- sound RAM -> work RAM H (the B-bus read path)
    for i = 0, 64 / 4 - 1 do
        sp:write_u32(0x6020100 + i * 4, 0)
    end
    dma_direct(0x5a10000, 0x6020100, 64)
    check("dma_return_idle", wait_idle() and 1 or 0, 1)
    verify(0x6020100, 0x01020304, "dma_return",
           function(a) return sp:read_u32(a) end)

    -- illegal same-bus transfer: sound RAM -> sound RAM
    local ist_before = sp:read_u32(scu + 0xa4)
    sp:write_u32(scu + 0xa4, 0xffffffff)             -- clear pending status bits
    dma_direct(0x5a10000, 0x5a10080, 64)
    emu.wait(emu.attotime.from_usec(500))
    check("dma_illegal_ist", (sp:read_u32(scu + 0xa4) & 0x1000) ~= 0 and 1 or 0, 1)
    check("dma_illegal_noop", sp:read_u32(0x5a10080), 0xfeedface)
    check("dma_illegal_status", (sp:read_u32(scu + 0x7c) & 0x30), 0)
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
    check("held_in_reset", ssp:read_u32(0x3400), 0)

    check("smpc_sndon", sound_release() and 1 or 0, 1)
    -- Give the run time to reach the handler's self-imposed limit.  The
    -- handler accepts exactly five entries and then masks level 6 in the
    -- stacked SR before acknowledging, so delivery must stop at five even
    -- though the timer keeps requesting.  Two failure modes are excluded by
    -- the same number: no acknowledgement (level triggered interrupt, the
    -- counter would race past five) and a mask that the rte discards.
    local counter_run = 0
    for _ = 1, 40 do
        counter_run = ssp:read_u32(0x3400)
        if counter_run >= 5 then break end
        emu.wait(emu.attotime.from_usec(10000))
    end
    check("guest_program_ran", ssp:read_u32(0x3400) > 1 and 1 or 0, 1)
    emu.wait(emu.attotime.from_msec(150))
    local counter_masked_run = ssp:read_u32(0x3400)
    local pending_after = sp:read_u16(base + 0x420) & 0x40
    emu.wait(emu.attotime.from_msec(50))
    check("masked_run_stopped", ssp:read_u32(0x3400), counter_masked_run)
    check("masked_run_count", counter_masked_run, 5)
    check("request_still_raised", pending_after, 0x40)
    print(string.format("SCSP_INT masked counter=%d scipd=%04x",
                        counter_masked_run, sp:read_u16(base + 0x420)))

    -- the latched request the masked CPU left behind must clear through the
    -- acknowledge register (RETI/level semantics are the timers gate's job,
    -- this only proves the pending bit is the acknowledged source)
    sp:write_u16(base + 0x422, 0x40)
    local acked = 0
    for _ = 1, 10 do
        if (sp:read_u16(base + 0x420) & 0x40) == 0 then
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
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(run_everything)
        if not ok then print("SCSP_INT FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_INT armed")

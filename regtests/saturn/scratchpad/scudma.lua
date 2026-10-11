
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local checks = 0
local BYTES = 0x10000
local function now() return m.time:as_double() * 1e6 end
local S = 0x05FE0000
local function dma(src, dst, dst_add)
    sp:write_u32(S + 0xA4, 0)                  -- IST: clear
    sp:write_u32(S + 0x00, src); sp:write_u32(S + 0x04, dst); sp:write_u32(S + 0x08, BYTES)
    sp:write_u32(S + 0x0C, 0x100 | dst_add)    -- D0AD: read +4, write per dst_add code
    sp:write_u32(S + 0x14, 0x7)                -- D0MD: direct, no update, start by GO
    sp:write_u32(S + 0x10, 0x100)              -- D0EN: enable
    local t0 = now()
    sp:write_u32(S + 0x10, 0x101)              -- GO
    local deadline = t0 + 1e6
    while (sp:read_u32(S + 0xA4) & 0x800) == 0 do
        emu.wait(emu.attotime.from_usec(1))
        assert(now() < deadline, string.format('DMA %08x -> %08x did not end', src, dst))
    end
    return now() - t0
end
local function test()
    sp:write_u32(0x06000000, 0x300089fd)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        m.devices[tag].state["SR"].value = 0xf0
        m.devices[tag].state["PC"].value = 0x26000000
    end
    emu.wait(emu.attotime.from_msec(2))
    sp:write_u16(0x25F80000, 0x0000)          -- TVMD: 320 dots, display off
    sp:write_u32(S + 0xB0, 0)                 -- ASR0: no A-bus waits
    emu.wait(emu.attotime.from_msec(40))
    local clock = (sp:read_u16(0x25F80000) & 1) ~= 0 and 14318181.8 * 4 / 2 or 14318181.8 * 3.75 / 2
    local cases = {
        {'Work RAM-H to VDP1 VRAM', 0x06040000, 0x05C40000, 1, 32768 + (16384 // 31) * 4},
        {'VDP1 VRAM to Work RAM-H', 0x05C40000, 0x06040000, 1, 32768},
        {'Work RAM-H to SCSP RAM', 0x06040000, 0x05A40000, 1, 32768 * 13},
        {'A-bus CS0 to Work RAM-H', 0x02000000, 0x06040000, 1, 16384 * 10},
    }
    for _, c in ipairs(cases) do
        local cycles = dma(c[2], c[3], c[4]) * clock / 1e6
        print(string.format('%s %s %.0f cycles, model %d', 'SCU_DMA_TIMING', c[1], cycles, c[5]))
        checks = checks + 1
        assert(math.abs(cycles - c[5]) <= c[5] * 0.005, c[1] .. ' off the model')
    end
    -- An A-bus to B-bus DMA leaves the SH-2s running, but it owns both buses:
    -- the master starts one (A-bus CS0 to VDP1 VRAM) and reads the last
    -- destination word at once. The read must wait for the transfer and see
    -- its data, not the value placed there before; the program takes the
    -- transfer's 16384 longwords of 10 cycles.
    --   mov.l r2,@r1 (GO); mov.w @r3,r0; mov.l r0,@r4; mov #1,r5; mov.l r5,@(4,r4); bra self; nop
    local CODE, PARAM = 0x06000100, 0x06000200
    local prog = {0x2122, 0x6031, 0x2402, 0xE501, 0x1451, 0xAFFE, 0x0009}
    for i, w in ipairs(prog) do sp:write_u16(CODE + (i - 1) * 2, w) end
    sp:write_u32(PARAM, 0); sp:write_u32(PARAM + 4, 0)
    local last = 0x05C40000 + BYTES - 2
    sp:write_u16(last, 0x1234)
    sp:write_u32(S + 0xA4, 0)
    sp:write_u32(S + 0x00, 0x02000000); sp:write_u32(S + 0x04, 0x05C40000); sp:write_u32(S + 0x08, BYTES)
    sp:write_u32(S + 0x0C, 0x101); sp:write_u32(S + 0x14, 0x7); sp:write_u32(S + 0x10, 0x100)
    local cpu = m.devices[":maincpu"]
    cpu.state["R1"].value = 0x25FE0010; cpu.state["R2"].value = 0x101
    cpu.state["R3"].value = 0x20000000 | last; cpu.state["R4"].value = PARAM | 0x20000000
    local t0 = now()
    cpu.state["PC"].value = CODE | 0x20000000
    while sp:read_u32(PARAM + 4) ~= 1 do
        emu.wait(emu.attotime.from_usec(1))
        assert(now() < t0 + 1e6, 'the CPU read did not finish')
    end
    local cycles = (now() - t0) * clock / 1e6
    local seen, final = sp:read_u32(PARAM) & 0xffff, sp:read_u16(last)
    print(string.format('%s SH-2 read during an A-bus to VDP1 DMA: %.0f cycles, model %d; read %04x, final %04x',
        'SCU_DMA_TIMING', cycles, 16384 * 10, seen, final))
    checks = checks + 1
    assert(final ~= 0x1234 and seen == final, 'the read saw the data before the transfer')
    checks = checks + 1
    assert(math.abs(cycles - 16384 * 10) <= 16384 * 10 * 0.01, 'the read did not wait for the transfer')
    print('SCU_DMA_TIMING' .. ' PASS checks=' .. checks)
    m:exit()
end
local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 30 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print('SCU_DMA_TIMING' .. ' FAIL ' .. tostring(err)); m:exit() end
    end)()
end)
print('SCU_DMA_TIMING' .. ' armed')

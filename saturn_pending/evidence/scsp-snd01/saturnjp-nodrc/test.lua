
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

local base, ram, scu = 0x5b00000, 0x5a00000, 0x5fe0000
local reg68 = 0x100000
local HANDLER, MAINLOOP, STACK = 0x7000, 0x7100, 0x7fff0
local LIVENESS, NMIHANDLER, NMICOUNT = 0x7210, 0x7300, 0x7310
local COUNTER, UNMASKED = 0x7200, 0x7208
local snd = nil
local ssp = nil
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_INT hooked=" .. tostring(hooked))
local results = {}

local function w16(a, v) sp:write_u16(a, v) end
local function r16(a) return sp:read_u16(a) end
local function ms(t) return emu.attotime.from_msec(t) end

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
local function sound_hold()
    if STV then
        sp:write_u8(SMPC + 0x7b, 0x30)
        sp:write_u8(SMPC + 0x77, 0x10)
        return true
    end
    return smpc_command(0x07)
end
local function sound_release()
    if STV then
        sp:write_u8(SMPC + 0x77, 0x00)
        return true
    end
    return smpc_command(0x06)
end

local function park_sh2()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        cpu.state["SR"].value = 0xf0
        cpu.state["PC"].value = 0x06000000
    end
end

local function show(v)
    if type(v) == 'number' then return string.format("%x", v) end
    return tostring(v)
end
local function check(name, got, want)
    if got ~= want then
        print(string.format("SCSP_INT FAIL %s got=%s want=%s",
            name, show(got), show(want)))
        results.failed = (results.failed or 0) + 1
    end
    results.cases = (results.cases or 0) + 1
end

-- 68000 program: level 6 handler at HANDLER, idle loop at MAINLOOP
local function upload_sound_program()
    ssp:write_u32(0x00000000, STACK)          -- initial SSP
    ssp:write_u32(0x00000004, MAINLOOP)       -- initial PC
    ssp:write_u32(0x00000078, HANDLER)        -- autovector 30: level 6
    -- level 7 would be taken even with the mask closed, so the vector is filled
    -- with a counter that must stay zero: it discriminates a level 6 request
    -- from a level 7 one (which an uninitialised vector would turn into a jump
    -- into the weeds)
    ssp:write_u32(0x0000007c, NMIHANDLER)     -- autovector 31: level 7
    ssp:write_u16(NMIHANDLER + 0x00, 0x52b9)  -- addq.l #1,($00007310).l
    ssp:write_u32(NMIHANDLER + 0x02, NMICOUNT)
    ssp:write_u16(NMIHANDLER + 0x06, 0x4e73)  -- rte
    ssp:write_u32(NMICOUNT, 0)
    -- handler: counter++, acknowledge the SCSP source, return
    ssp:write_u16(HANDLER + 0x00, 0x52b9)     -- addq.l #1,($00007200).l
    ssp:write_u32(HANDLER + 0x02, 0x7200)
    ssp:write_u16(HANDLER + 0x06, 0x33fc)     -- move.w #$0040,($00100422).l
    ssp:write_u16(HANDLER + 0x08, 0x0040)     -- SCIRE: clear the timer A request
    ssp:write_u32(HANDLER + 0x0a, reg68 + 0x422)
    ssp:write_u16(HANDLER + 0x0e, 0x4e73)     -- rte
    -- Program: keep interrupts masked for a fixed delay while spinning a
    -- liveness counter, then open the mask and idle.  The SCSP request is
    -- already pending when the CPU comes out of reset, so the mask has to be
    -- held for a moment: an interrupt taken on the first instruction after the
    -- reset builds its frame before the program has settled and returns into
    -- the weeds (measured: the handler ran and acknowledged, the CPU then
    -- executed the vector table as code).
    ssp:write_u16(MAINLOOP + 0x00, 0x46fc)     -- move.w #$2700,sr
    ssp:write_u16(MAINLOOP + 0x02, 0x2700)
    ssp:write_u16(MAINLOOP + 0x04, 0x223c)     -- move.l #$1000,d1
    ssp:write_u32(MAINLOOP + 0x06, 0x00001000)
    ssp:write_u16(MAINLOOP + 0x0a, 0x52b9)     -- addq.l #1,($00007210).l
    ssp:write_u32(MAINLOOP + 0x0c, LIVENESS)
    ssp:write_u16(MAINLOOP + 0x10, 0x5381)     -- subq.l #1,d1
    ssp:write_u16(MAINLOOP + 0x12, 0x66f6)     -- bne.s back to the increment
    ssp:write_u16(MAINLOOP + 0x14, 0x46fc)     -- move.w #$2000,sr
    ssp:write_u16(MAINLOOP + 0x16, 0x2000)
    ssp:write_u16(MAINLOOP + 0x18, 0x52b9)     -- addq.l #1,($00007208).l
    ssp:write_u32(MAINLOOP + 0x1a, UNMASKED)
    ssp:write_u16(MAINLOOP + 0x1e, 0x60fe)     -- bra.s *
    ssp:write_u32(COUNTER, 0)
    ssp:write_u32(LIVENESS, 0)
    ssp:write_u32(UNMASKED, 0)
end

local function read_counter() return ssp:read_u32(COUNTER) end

local function test()
    park_sh2()
    snd = assert(m.devices[":audiocpu"])
    ssp = snd.spaces["program"]
    if not sound_hold() then error('SMPC SNDOFF was refused') end
    emu.wait(ms(20))
    upload_sound_program()

    -- Group A: sound RAM lanes through both windows
    local off = 0x4000
    local function sh2(a) return ram + off + a end
    ssp:write_u8(off + 0x00, 0xa5)
    check('ram8_68k_to_sh2', sp:read_u8(sh2(0x00)), 0xa5)
    sp:write_u8(sh2(0x01), 0x5a)
    check('ram8_sh2_to_68k', ssp:read_u8(off + 0x01), 0x5a)
    sp:write_u16(sh2(0x02), 0x1234)
    check('ram16_sh2_to_68k', ssp:read_u16(off + 0x02), 0x1234)
    check('ram16_sh2_byte_hi', ssp:read_u8(off + 0x02), 0x12)
    check('ram16_sh2_byte_lo', ssp:read_u8(off + 0x03), 0x34)
    ssp:write_u16(off + 0x04, 0xabcd)
    check('ram16_68k_to_sh2', sp:read_u16(sh2(0x04)), 0xabcd)
    check('ram16_68k_byte_hi', sp:read_u8(sh2(0x04)), 0xab)
    check('ram16_68k_byte_lo', sp:read_u8(sh2(0x05)), 0xcd)
    sp:write_u32(sh2(0x08), 0x11223344)
    check('ram32_sh2_to_68k', ssp:read_u32(off + 0x08), 0x11223344)
    check('ram32_sh2_b0', ssp:read_u8(off + 0x08), 0x11)
    check('ram32_sh2_b1', ssp:read_u8(off + 0x09), 0x22)
    check('ram32_sh2_b2', ssp:read_u8(off + 0x0a), 0x33)
    check('ram32_sh2_b3', ssp:read_u8(off + 0x0b), 0x44)
    ssp:write_u32(off + 0x0c, 0x55667788)
    check('ram32_68k_to_sh2', sp:read_u32(sh2(0x0c)), 0x55667788)
    check('ram32_68k_b0', sp:read_u8(sh2(0x0c)), 0x55)
    check('ram32_68k_b1', sp:read_u8(sh2(0x0d)), 0x66)
    check('ram32_68k_b2', sp:read_u8(sh2(0x0e)), 0x77)
    check('ram32_68k_b3', sp:read_u8(sh2(0x0f)), 0x88)

    -- Group B: the same SCSP slot registers through both windows
    local slot3 = 0x60
    w16(base + slot3 + 0x10, 0x1234)          -- slot 3 pitch
    check('reg_pitch_68k_read', ssp:read_u16(reg68 + slot3 + 0x10), 0x1234)
    ssp:write_u16(reg68 + slot3 + 0x10, 0x5678)
    check('reg_pitch_sh2_read', r16(base + slot3 + 0x10), 0x5678)
    w16(base + slot3 + 0x16, 0x9abc)          -- slot 3 mixer
    check('reg_mix_68k_read', ssp:read_u16(reg68 + slot3 + 0x16), 0x9abc)
    ssp:write_u16(reg68 + slot3 + 0x16, 0xdef0)
    check('reg_mix_sh2_read', r16(base + slot3 + 0x16), 0xdef0)
    -- the common page sits at the same byte offsets in both windows: 0x422 is
    -- SCIRE and 0x424 is SCILV0, not the other way round
    w16(base + 0x426, 0x0040)                 -- SCILV1 through the SH-2 window
    check('reg_common_68k_read', ssp:read_u16(reg68 + 0x426), 0x0040)
    ssp:write_u16(reg68 + 0x426, 0x0000)
    check('reg_common_sh2_read', r16(base + 0x426), 0x0000)

    -- Group C: SCU DMA level 0, work RAM H <-> sound RAM
    local src, dst = 0x06020000, ram + 0x1000
    for i = 0, 15 do
        sp:write_u32(src + 4 * i, 0xdead0000 | i)
    end
    for i = 0, 15 do
        sp:write_u32(dst + 4 * i, 0xffffffff)
    end
    sp:write_u32(scu + 0x00, src)
    sp:write_u32(scu + 0x04, dst)
    sp:write_u32(scu + 0x08, 64)
    sp:write_u32(scu + 0x0c, 0x00000101)      -- src steps by dword, dst by word
    sp:write_u32(scu + 0x14, 0x00000007)      -- start factor: trigger
    sp:write_u32(scu + 0x10, 0x00000101)      -- enable + D0GO
    for n = 1, 200 do
        if (sp:read_u32(scu + 0x7c) & 0x30) == 0 then break end
        emu.wait(ms(1))
    end
    results.dma_status = sp:read_u32(scu + 0x7c)
    results.dma_status_after = sp:read_u32(scu + 0x7c)
    local moved = 0
    for i = 0, 15 do
        if ssp:read_u32(0x00001000 + 4 * i) == (0xdead0000 | i) then moved = moved + 1 end
    end
    check('dma_to_sound_ram_words', moved, 16)
    local back = 0
    for i = 0, 15 do
        if sp:read_u32(ram + 0x1000 + 4 * i) == (0xdead0000 | i) then back = back + 1 end
    end
    check('dma_sound_ram_sh2_view', back, 16)
    -- reverse direction
    sp:write_u32(scu + 0x00, ram + 0x1000)
    sp:write_u32(scu + 0x04, 0x06020100)
    sp:write_u32(scu + 0x08, 64)
    sp:write_u32(scu + 0x0c, 0x00000101)
    sp:write_u32(scu + 0x10, 0x00000101)
    for n = 1, 200 do
        if (sp:read_u32(scu + 0x7c) & 0x30) == 0 then break end
        emu.wait(ms(1))
    end
    local back2 = 0
    for i = 0, 15 do
        if sp:read_u32(0x06020100 + 4 * i) == (0xdead0000 | i) then back2 = back2 + 1 end
    end
    check('dma_from_sound_ram_words', back2, 16)
    -- control: the same bus on both sides is illegal
    local ist_before = sp:read_u32(scu + 0xa4)
    for i = 0, 15 do
        sp:write_u32(ram + 0x2000 + 4 * i, 0x5a5a0000 | i)
    end
    sp:write_u32(scu + 0x00, ram + 0x1000)
    sp:write_u32(scu + 0x04, ram + 0x2000)
    sp:write_u32(scu + 0x08, 64)
    sp:write_u32(scu + 0x0c, 0x00000101)
    sp:write_u32(scu + 0x10, 0x00000101)
    emu.wait(ms(5))
    local ist_after = sp:read_u32(scu + 0xa4)
    results.ist_before = ist_before
    results.ist_after = ist_after
    check('dma_illegal_ist', (ist_after & 0x1000) ~= 0, true)
    local untouched = 0
    for i = 0, 15 do
        if sp:read_u32(ram + 0x2000 + 4 * i) == (0x5a5a0000 | i) then untouched = untouched + 1 end
    end
    check('dma_illegal_untouched', untouched, 16)
    check('dma_illegal_status_idle', sp:read_u32(scu + 0x7c) & 0x30, 0)

    -- Group D: SCSP timer A request through the 68000's level 6 autovector
    check('program_uploaded', ssp:read_u32(0x00000078), HANDLER)
    -- a nil address in a debugger write lands on address 0 (measured), which
    -- silently destroys the reset vector; the fixture must never be able to
    -- lose it without saying so
    check('initial_ssp_intact', ssp:read_u32(0x00000000), STACK)
    check('counter_cleared', read_counter(), 0)
    check('liveness_cleared', ssp:read_u32(LIVENESS), 0)
    check('nmi_count_cleared', ssp:read_u32(NMICOUNT), 0)
    -- The level is the OR of the three SCILV bits for the source, so all three
    -- are written: leaving SCILV0 at whatever the BIOS program left set made the
    -- request level 7, which the mask cannot hold off.
    w16(base + 0x424, 0x0000)                 -- SCILV0 bit 6: level bit 0 clear
    w16(base + 0x426, 0x0040)                 -- SCILV1 bit 6: level bit 1
    w16(base + 0x428, 0x0040)                 -- SCILV2 bit 6: level bit 2
    w16(base + 0x41e, 0x0040)                 -- SCIEB: enable timer A
    w16(base + 0x418, 0x0000)                 -- TACTL: timer A, prescale 0
    check('irq_masked_counter', read_counter(), 0)
    local saw_pending = false
    for n = 1, 200 do
        if (r16(base + 0x420) & 0x40) ~= 0 then saw_pending = true; break end
        emu.wait(ms(1))
    end
    check('irq_masked_pending', saw_pending, true)
    check('irq_masked_counter_after_wait', read_counter(), 0)
    -- release the CPU: it must run the uploaded program, which opens the mask
    -- and only then takes the level 6 request
    if not sound_release() then error('SMPC SNDON was refused') end
    emu.wait(ms(2))
    local live = ssp:read_u32(LIVENESS)
    local masked_counter = read_counter()
    results.liveness = live
    results.masked_counter = masked_counter
    check('cpu_runs_after_release', live > 0, true)
    check('irq_held_while_masked', masked_counter, 0)
    emu.wait(ms(40))
    -- the masked delay loop must have run to completion (4096 iterations with
    -- the mask closed) and the mask was then opened
    local liveness_end = ssp:read_u32(LIVENESS)
    results.liveness_end = liveness_end
    check('program_delay_completed', liveness_end >= 0x1000, true)
    local first = read_counter()
    emu.wait(ms(300))
    local later = read_counter()
    results.counter_first = first
    results.counter_later = later
    -- the level 6 request must now be delivered through the 68000's own
    -- exception path: the handler counts, acknowledges and returns, and the
    -- timer keeps requesting, so the count advances over the window
    check('irq_handler_entered', later > 0, true)
    check('irq_handler_keeps_running', later > first, true)
    -- the handler's acknowledgement clears the request, and the timer raises it
    -- again at the next expiry: the bit must be clear inside a window shorter
    -- than one timer period
    local cleared = false
    for n = 1, 400 do
        if (r16(base + 0x420) & 0x40) == 0 then cleared = true; break end
        emu.wait(ms(1))
    end
    check('irq_request_cleared_by_handler', cleared, true)
    -- the timer requests again at its own rate, so the count must advance over
    -- another full delivery window after the acknowledgement was observed
    emu.wait(ms(300))
    local grown = read_counter()
    results.counter_end = grown
    check('irq_counter_keeps_growing', grown > later, true)
    results.nmi_count = ssp:read_u32(NMICOUNT)
    check('irq_stayed_below_level_7', results.nmi_count, 0)
    results.unmasked = ssp:read_u32(UNMASKED)
    check('program_reached_unmask', results.unmasked > 0, true)
    results.pc_after = snd.state["PC"].value
    results.ssp_after = snd.state["SP"].value
    check('ssp_restored_after_handlers', results.ssp_after, STACK)
    do
        local vecs = {}
        for lv = 1, 7 do
            vecs[#vecs + 1] = string.format("%d:%08x", lv,
                ssp:read_u32(0x60 + 4 * lv))
        end
        print("SCSP_INT vectors " .. table.concat(vecs, " ") ..
            string.format(" v0=%08x v4=%08x", ssp:read_u32(0x0),
                ssp:read_u32(0x4)))
    end
    print(string.format('SCSP_INT unmasked=%d scipd=%04x scieb=%04x scilv=%04x/%04x/%04x',
        results.unmasked, r16(base + 0x420), r16(base + 0x41e),
        r16(base + 0x424), r16(base + 0x426), r16(base + 0x428)))
    check('irq_stayed_below_level_7', results.nmi_count, 0)

    print(string.format('SCSP_INT ack addr=%08x', reg68 + 0x422))
    print(string.format('SCSP_INT ist before=%x after=%x',
        results.ist_before or 0, results.ist_after or 0))
    print(string.format('SCSP_INT irq first=%d later=%d end=%d liveness=%d '
        .. 'masked_counter=%d nmi=%d pc_after=%08x ssp_after=%08x '
        .. 'unmasked=%d',
        results.counter_first or 0, results.counter_later or 0,
        results.counter_end or 0, (results.liveness_end or results.liveness or 0),
        results.masked_counter or 0, results.nmi_count or 0,
        results.pc_after or 0, results.ssp_after or 0,
        results.unmasked or 0))
    print(string.format('SCSP_INT dma status=%08x after_second=%08x',
        results.dma_status or 0, results.dma_status_after or 0))
    if (results.failed or 0) == 0 then
        print(string.format('SCSP_INT PASS cases=%d', results.cases or 0))
    else
        print(string.format('SCSP_INT FAILS %d', results.failed))
    end
    m:exit()
end

local frames = 0
local started = false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_INT FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_INT armed")

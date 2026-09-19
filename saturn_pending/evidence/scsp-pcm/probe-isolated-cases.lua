
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

local base = 0x05b00000
local c0, cr = base, base + 0x40
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true end
end
local cap = { on = false }
emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    for i = 1, #chans[1] do
        if cap.n < cap.want then
            cap.n = cap.n + 1
            cap.l[cap.n] = chans[1][i]
        end
    end
end)
local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end

local function play(label, lsa, sa, lea, lpctl, pcm8b, oct)
    local ref = nil
    w(c0, 0x00, 0x1030)
    w(cr, 0x00, 0x1030)
    emu.wait(ms(20))
    w(c0, 0x00, (pcm8b and 0x0010 or 0x0000) | ((lpctl & 3) << 5))
    w(c0, 0x02, sa)
    w(c0, 0x04, lsa)
    w(c0, 0x06, lea)
    w(c0, 0x08, 0x0020)
    w(c0, 0x0a, 0x3fe0)
    w(c0, 0x0c, 0x0200)
    w(c0, 0x0e, 0x0000)
    w(c0, 0x10, oct)
    w(c0, 0x14, 0x0000)
    w(c0, 0x16, 0xe000 | (0x1f << 8))
    if ref then
        w(cr, 0x00, 0x0030)
        w(cr, 0x02, ref)
        w(cr, 0x04, 0x0000)
        w(cr, 0x06, lea)
        w(cr, 0x08, 0x0020)
        w(cr, 0x0a, 0x3fe0)
        w(cr, 0x0c, 0x0200)
        w(cr, 0x0e, 0x0000)
        w(cr, 0x10, oct)
        w(cr, 0x14, 0x0000)
        w(cr, 0x16, 0xe000 | (0x0f << 8))
    else
        w(cr, 0x16, 0x0000)
        w(cr, 0x00, 0x0030)
    end
    emu.wait(ms(4))
    -- key on, let the attack reach full volume, then capture
    if ref and ref ~= 0 then w(cr, 0x00, 0x0830) end
    w(c0, 0x00, 0x3830 & ~0x10 | (pcm8b and 0x10 or 0))
    emu.wait(ms(250))

    do
        local rows = {}
        for _, pair in ipairs({{"c0", c0}, {"cr", cr}}) do
            local t = {}
            for off = 0, 0x16, 2 do
                t[#t + 1] = string.format("%04x", sp:read_u16(pair[2] + off))
            end
            rows[#rows + 1] = pair[1] .. "=" .. table.concat(t, " ")
        end
        print("DUMP " .. table.concat(rows, " | "))
    end
    cap = { on = true, n = 0, want = 512, l = {} }
    emu.wait(ms(20))
    cap.on = false
    local first = {}
    for i = 1, math.min(40, cap.n) do
        first[#first + 1] = string.format("%d", math.floor(cap.l[i] * 32768 + 0.5))
    end
    local peak = 0
    for i = 1, cap.n do if math.abs(cap.l[i]) > peak then peak = math.abs(cap.l[i]) end end
    local span = 0
    for i = 1, cap.n do
        for j = 1, cap.n do end
    end
    local lo, hi = 999, -999
    for i = 1, cap.n do
        if cap.l[i] < lo then lo = cap.l[i] end
        if cap.l[i] > hi then hi = cap.l[i] end
    end
    print(string.format("ONE %-22s peak=%.5f span=%.5f first=[%s]", label, peak,
        hi - lo, table.concat(first, ",")))
end

local function test()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        cpu.state["SR"].value = 0xf0
        cpu.state["PC"].value = 0x06000000
    end
    local snd = assert(m.devices[":audiocpu"])
    ss = snd.spaces["program"]
    ss:write_u16(0x70000, 0x60fe)
    snd.state["SR"].value = 0x2700
    snd.state["PC"].value = 0x70000
    w(base + 0x400, 0x000f)
    -- 16 bit ramp, 3 x 1024 words of 64 steps of 1024 units, big endian
    for n = 0, 3 * 1024 - 1 do
        local v = ((n % 64) * 1024) - 32768
        if v < 0 then v = v + 65536 end
        ss:write_u8(0x3000 + 2 * n, (v >> 8) & 0xff)
        ss:write_u8(0x3000 + 2 * n + 1, v & 0xff)
    end
    -- 8 bit ramp of the same shape at 0x2000
    for n = 0, 3 * 1024 - 1 do
        ss:write_u8(0x2000 + n, (((n % 64) * 4) - 128) & 0xff)
    end
    play("fwd  lsa=0", 0, 0x2400, 64, 1, true, 0x7000)
    play("rev  lsa=0", 0, 0x2400, 64, 2, true, 0x7000)
    play("ping lsa=0 after rev", 0, 0x2400, 64, 3, true, 0x7000)
    play("ping lsa=0 again", 0, 0x2400, 64, 3, true, 0x7000)
    play("ping lsa=0 third", 0, 0x2400, 64, 3, true, 0x7000)
    play("ping lsa=0 fourth", 0, 0x2400, 64, 3, true, 0x7000)
    play("ping lsa=0 fifth", 0, 0x2400, 64, 3, true, 0x7000)
    m:exit()
end
local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("ONE FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("ONE armed")

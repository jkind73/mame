
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
local c0 = base
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

local function play(label, sa, lea, lpctl, pcm8b, oct)
    w(c0, 0x00, 0x1030)
    emu.wait(ms(10))
    w(c0, 0x00, (pcm8b and 0x0010 or 0x0000) | ((lpctl & 3) << 5))
    w(c0, 0x02, sa)
    w(c0, 0x04, 0x0000)
    w(c0, 0x06, lea)
    w(c0, 0x08, 0x0020)
    w(c0, 0x0a, 0x3fe0)
    w(c0, 0x0c, 0x0200)
    w(c0, 0x0e, 0x0000)
    w(c0, 0x10, oct)
    w(c0, 0x16, 0xe000 | (0x1f << 8))
    emu.wait(ms(4))
    cap = { on = true, n = 0, want = 4096, l = {} }
    w(c0, 0x00, 0x3830 & ~0x10 | (pcm8b and 0x10 or 0))
    emu.wait(ms(1 + 4096 / 44))
    cap.on = false
    -- report the run lengths of the sign of the capture from sample 1000 on
    local runs, last, count, first = {}, nil, 0, nil
    for i = 1000, cap.n do
        local sgn = (cap.l[i] >= 0) and 1 or 0
        if last == nil then last = sgn; first = i end
        if sgn == last then count = count + 1
        else runs[#runs + 1] = count; count = 1; last = sgn end
    end
    local head = {}
    for i = 1, math.min(6, #runs) do head[i] = runs[i] end
    local peak = 0
    for i = 1, cap.n do if math.abs(cap.l[i]) > peak then peak = math.abs(cap.l[i]) end end
    print(string.format("SQ %-14s n=%d peak=%.5f runs=[%s]", label, cap.n, peak,
        table.concat(head, ",")))
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
    -- 16 bit square, equal bytes: 512 words high then 512 low, at 0x3000
    for n = 0, 4095 do
        local b = ((n % 1024) < 512) and 0x40 or 0xc0
        ss:write_u8(0x3000 + 2 * n, b)
        ss:write_u8(0x3000 + 2 * n + 1, b)
    end
    -- 8 bit square of the same duty at 0x6000
    for n = 0, 4095 do
        ss:write_u8(0x6000 + n, ((n % 1024) < 512) and 0x40 or 0xc0)
    end
    play("pcm16 lea=1024", 0x3000, 1024, 1, false, 0x7000)
    play("pcm16 lea=512", 0x3000, 512, 1, false, 0x7000)
    play("pcm8  lea=1024", 0x6000, 1024, 1, true, 0x7000)
    play("pcm16 1 word/s", 0x3000, 1024, 1, false, 0x0000)
    m:exit()
end
local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SQ FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SQ armed")

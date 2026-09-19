
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
local lmax, rmax, on = 0, 0, false
emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not on then return end
    if chans[1] then for i = 1, #chans[1] do
        if math.abs(chans[1][i]) > lmax then lmax = math.abs(chans[1][i]) end
    end end
    if chans[2] then for i = 1, #chans[2] do
        if math.abs(chans[2][i]) > rmax then rmax = math.abs(chans[2][i]) end
    end end
end)
local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end
local function cfg(slot, sa, dipan, disdl)
    w(slot, 0x00, 0x0030)
    w(slot, 0x02, sa)
    w(slot, 0x04, 0x0000)
    w(slot, 0x06, 64)
    w(slot, 0x08, 0x0020)
    w(slot, 0x0a, 0x3fe0)
    w(slot, 0x0c, 0x0200)
    w(slot, 0x0e, 0x0000)
    w(slot, 0x10, 0x7000)
    w(slot, 0x16, (disdl << 13) | (dipan << 8))
end
local function measure(label, cfg0, cfg2)
    w(c0, 0x00, 0x1030) w(cr, 0x00, 0x1030)
    emu.wait(ms(20))
    lmax, rmax, on = 0, 0, true
    emu.wait(ms(40))                              -- control: nothing keyed
    local base_l, base_r = lmax, rmax
    if cfg0 then cfg(c0, 0x3600, cfg0.dipan, cfg0.disdl) end
    if cfg2 then cfg(cr, 0x3a00, cfg2.dipan, cfg2.disdl) end
    emu.wait(ms(4))
    if cfg2 then w(cr, 0x00, 0x0830) end
    if cfg0 then w(c0, 0x00, 0x3830) end
    emu.wait(ms(60))
    on = false
    print(string.format("PAN %-26s L=%.5f R=%.5f (idle %.5f/%.5f)", label, lmax,
        rmax, base_l, base_r))
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
    for n = 0, 255 do ss:write_u8(0x3600 + n, 0x40) end    -- +0.5 (c0)
    for n = 0, 255 do ss:write_u8(0x3a00 + n, 0x20) end    -- +0.25 (cr)
    measure("idle only", nil, nil)
    measure("c0 only DIPAN=0x1f", {dipan = 0x1f, disdl = 7})
    measure("c0 only DIPAN=0x0f", {dipan = 0x0f, disdl = 7})
    measure("c0 only DIPAN=0x10", {dipan = 0x10, disdl = 7})
    measure("cr only DIPAN=0x0f", {dipan = 0x0f, disdl = 0}, {dipan = 0x0f, disdl = 7})
    measure("cr only DIPAN=0x1f", {dipan = 0x0f, disdl = 0}, {dipan = 0x1f, disdl = 7})
    measure("both, 0x1f/0x0f", {dipan = 0x1f, disdl = 7}, {dipan = 0x0f, disdl = 7})
    m:exit()
end
local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("PAN FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("PAN armed")

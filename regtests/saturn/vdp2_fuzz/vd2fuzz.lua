-- env: VF_CAP (capture file), VF_MUT (mutation file), VF_OUT (output)
local capname, mutname, outname = assert(os.getenv('VF_CAP')), assert(os.getenv('VF_MUT')), assert(os.getenv('VF_OUT'))
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local mem = cpu.spaces['program']
local screen = machine.screens[':screen']

local function load_cap(path)
    local f = assert(io.open(path, 'rb'))
    local all = f:read('a')
    f:close()
    local p, m = 16, {}
    while p + 4 <= #all do
        local nl = string.unpack('>I4', all, p); p = p + 4
        local name = all:sub(p, p + nl - 1); p = p + nl
        local el, len = string.unpack('>I4I4', all, p); p = p + 8
        m[name] = all:sub(p, p + len - 1)
        p = p + len
    end
    return m
end

local cap = load_cap(capname)
local muts = {}
for line in io.lines(mutname) do muts[#muts + 1] = line end
local out = assert(io.open(outname, 'wb'))
local regs = {}
for i = 0, 0xff do regs[i] = string.unpack('<I2', cap['m_vdp2_regs'], i * 2 + 1) end
for _, k in ipairs({'vdp2.m_tvmd', 'vdp2.m_exten', 'vdp2.m_vramsz'}) do cap[k] = cap[k] .. string.rep('\0', 4) end
local function u32rec(name, i) return string.unpack('<I4', cap[name], i * 4 + 1) end
regs[0] = u32rec('vdp2.m_tvmd', 0) & 0xffff
regs[1] = u32rec('vdp2.m_exten', 0) & 0xffff
regs[3] = (u32rec('vdp2.m_vramsz', 0) & 1) << 15

local phase, frame, idx = 'boot', 0, 0
emu.register_frame_done(function()
    frame = frame + 1
    if phase == 'boot' then
        if emu.time() < 3.0 then return end
        mem:write_u32(0x06000000, 0xAFFE0009)
        cpu.state['PC'].value = 0x06000000
        cpu.state['SR'].value = 0xF0
        for i = 0, 0xff do mem:write_u16(0x05F80000 + i * 2, regs[i]) end
        -- VDP2 memories once
        local nvram = ((regs[3] >> 15) & 1) == 1 and 0x40000 or 0x20000
        for i = 0, nvram - 1 do mem:write_u32(0x05E00000 + i * 4, u32rec("m_vdp2_vram", i)) end
        for i = 0, 0x400 - 1 do mem:write_u32(0x05F00000 + i * 4, u32rec('m_vdp2_cram', i)) end
        phase, frame = 'apply', 0
        return
    end
    if phase == 'apply' then
        if idx >= #muts then
            out:close()
            print('VD2FUZZ done ' .. idx)
            machine:exit()
            return
        end
        local r = {}
        for i = 0, 0xff do r[i] = regs[i] end
        for a, b in muts[idx + 1]:gmatch('(%d+)=(%d+)') do r[tonumber(a)] = tonumber(b) end
        for i = 0, 0xff do mem:write_u16(0x05F80000 + i * 2, r[i]) end
        phase, frame = 'wait', 0
    elseif phase == 'wait' then
        if frame >= tonumber(os.getenv("VF_WAIT") or "6") then
            local px, w, h = screen:pixels()
            out:write(string.pack('<I4I4', w, h), px)
            idx = idx + 1
            phase, frame = 'apply', 0
        end
    end
end)

emu.register_frame_done(function()
    if phase == 'wait' and frame == 2 and not dbg_done then
        dbg_done = true
        local bad, first = 0, nil
        for i = 0, 0x40000 - 1 do
            if mem:read_u32(0x05E00000 + i * 4) ~= u32rec('m_vdp2_vram', i) then bad = bad + 1; first = first or i end
        end
        local badc = 0
        for i = 0, 0x400 - 1 do
            if mem:read_u32(0x05F00000 + i * 4) ~= u32rec('m_vdp2_cram', i) then badc = badc + 1 end
        end
        local badr = 0
        for i = 0, 0x8f do
            local v = mem:read_u16(0x05F80000 + i * 2)
            if v ~= regs[i] then badr = badr + 1; print(string.format('reg %02x read %04x want %04x', i * 2, v, regs[i])) end
        end
        print('DBG vram mismatches', bad, first, 'cram', badc, 'regs', badr)
    end
end)

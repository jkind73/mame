-- Runs the cases written by vdp1fuzz through MAME's VDP1 and records the displayed frame buffer.
-- env: FZ_PREFIX (path prefix of <prefix>_cases.bin), FZ_COUNT
local prefix = assert(os.getenv('FZ_PREFIX'))
local count = tonumber(os.getenv('FZ_COUNT') or '10')
local f = assert(io.open(prefix .. '_cases.bin', 'rb'))
local out = assert(io.open(prefix .. '_mame.bin', 'wb'))
local CASE = 0x10000 + 4
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local mem = cpu.spaces['program']
local fbitems = {}
local dispitem
local phase, frame, case = 'boot', 0, 0
local data

local function find_items()
    local root = machine.devices[':']
    for path, index in pairs(root.items) do
        local name = path:match('/([^/]+)$') or path
        if name == 'm_vdp1_legacy.framebuffer[0]' then fbitems[0] = emu.item(index)
        elseif name == 'm_vdp1_legacy.framebuffer[1]' then fbitems[1] = emu.item(index)
        elseif name == 'm_vdp1_legacy.framebuffer_current_display' then dispitem = emu.item(index) end
    end
    assert(fbitems[0] and fbitems[1] and dispitem, 'save items missing')
end

local function w16(a, v) mem:write_u16(a, v) end
local function clear_fb()
    for i = 0, 0x10000 - 1 do mem:write_u32(0x05C80000 + i * 4, 0) end
end

emu.register_frame_done(function()
    frame = frame + 1
    if phase == 'boot' then
        if emu.time() < 3.0 then return end
        -- park the master SH-2 in a tight loop with interrupts masked
        mem:write_u32(0x06000000, 0xAFFE0009)
        cpu.state['PC'].value = 0x06000000
        cpu.state['SR'].value = 0xF0
        find_items()
        phase, frame = 'load', 0
        return
    end
    if case >= count then
        out:close() f:close()
        print('FUZZ done ' .. count)
        machine:exit()
        return
    end
    if phase == 'load' then
        data = f:read(CASE)
        assert(data and #data == CASE, 'short case file')
        for i = 0, 0x4000 - 1 do
            -- big-endian words: pack two at a time as one long write
            local hi = string.unpack('>I2', data, i * 4 + 1)
            local lo = string.unpack('>I2', data, i * 4 + 3)
            mem:write_u32(0x05C00000 + i * 4, (hi << 16) | lo)
        end
        local tvmr = string.unpack('<I2', data, 0x10000 + 1)
        w16(0x05D00000, tvmr)
        w16(0x05D00006, 0)
        w16(0x05D00008, 0)
        w16(0x05D0000A, 0x50DF)
        w16(0x05D00002, 3)
        phase, frame = 'clear1', 0
    elseif phase == 'clear1' then
        if frame >= 3 then
            clear_fb()
            w16(0x05D00002, 3)
            phase, frame = 'clear2', 0
        end
    elseif phase == 'clear2' then
        if frame >= 3 then
            clear_fb()
            phase, frame = 'settle', 0
        end
    elseif phase == 'settle' then
        if frame >= 2 then
            w16(0x05D00004, 1)
            phase, frame = 'draw', 0
        end
    elseif phase == 'draw' then
        if frame >= 8 then
            w16(0x05D00002, 3)
            phase, frame = 'swap', 0
        end
    elseif phase == 'swap' then
        if frame >= 4 then
            local disp = dispitem:read(0) & 1
            out:write(fbitems[disp]:read_block(0, 0x40000))
            case = case + 1
            phase, frame = 'load', 0
        end
    end
end)

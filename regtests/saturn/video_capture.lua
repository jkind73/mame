-- Read-only graphics capture for Saturn/ST-V. No rebuild, -verbose or -log needed.
-- mame saturnjp aburner2 -autoboot_delay 0 -autoboot_script regtests/saturn/video_capture.lua
-- Press F12 while the artifact is visible (also takes MAME's normal screenshot).
-- Up to three saturn-video-*.bin files are written in the working directory.
local captures, failed = 0, false
local prefix = 'saturn-video-' .. os.date('%Y%m%d-%H%M%S')
local required = {
    ['m_vdp1_vram'] = {4, 0x80000},
    ['m_vdp1_regs'] = {2, 0x20},
    ['m_vdp2_vram'] = {4, 0x100000},
    ['m_vdp2_regs'] = {2, 0x200},
    ['m_vdp2_cram'] = {4, 0x1000},
    ['m_vdp1_legacy.framebuffer[0]'] = {2, 0x40000},
    ['m_vdp1_legacy.framebuffer[1]'] = {2, 0x40000},
    ['m_vdp1_legacy.framebuffer_current_display'] = {nil, nil},
}
local function capture(machine)
    local root = assert(machine.devices[':'], 'root device missing')
    local screen = assert(machine.screens[':screen'], 'screen missing')
    local records, found = {}, {}
    for path, index in pairs(root.items) do
        local name = path:match('/([^/]+)$') or path
        local wanted = required[name]
        if wanted or name:find('m_vdp1_legacy.', 1, true) == 1
                  or name:find('current_sprite.', 1, true) == 1 then
            local item = emu.item(index)
            local bytes = item.size * item.count
            -- Ignore large derived buffers. Capture both real physical banks,
            -- raw texture/LUT VRAM and small command/framebuffer state only.
            if wanted or bytes <= 1024 then
                assert(not found[name], 'duplicate save item: ' .. name)
                if wanted and wanted[1] then
                    assert(item.size == wanted[1] and bytes >= wanted[2], 'bad shape: ' .. name)
                    bytes = wanted[2]
                end
                assert(bytes > 0 and bytes <= 0x100000, 'bad size: ' .. name)
                local data = item:read_block(0, bytes)
                assert(#data == bytes, 'short read: ' .. name)
                records[#records + 1] = {name, item.size, data}
                found[name] = true
            end
        end
    end
    for name in pairs(required) do assert(found[name], 'save item missing: ' .. name) end
    local pixels, width, height = screen:pixels()
    assert(width > 0 and height > 0 and #pixels == width * height * 4 and #pixels <= 0x800000,
           'invalid screen buffer')
    local endian = string.pack('I2', 0x0102):byte(1) == 2 and 'little' or 'big'
    local meta = string.format('system=%s\ntime=%.9f\nwidth=%d\nheight=%d\nendian=%s\n',
                              machine.system.name, emu.time(), width, height, endian)
    records[#records + 1] = {'metadata', 1, meta}
    records[#records + 1] = {'screen.pixels', 4, pixels}
    table.sort(records, function(a,b) return a[1] < b[1] end)
    local pieces = {'SATURN-VIDEO-1\n'}
    for _, record in ipairs(records) do
        pieces[#pieces + 1] = string.pack('>I4', #record[1]) .. record[1]
            .. string.pack('>I4I4', record[2], #record[3]) .. record[3]
    end
    -- Avoid overwriting captures from another machine launch in the same second.
    local filename
    for serial = 1, 1000 do
        local candidate = prefix .. string.format('-%03d.bin', serial)
        local previous = io.open(candidate, 'rb')
        if previous then previous:close() else filename = candidate; break end
    end
    assert(filename, 'capture filename limit exceeded')
    local f = assert(io.open(filename, 'wb'))
    local ok, err = f:write(table.concat(pieces))
    local closed, close_error = f:close()
    if not ok or not closed then
        os.remove(filename)
        error(err or close_error)
    end
    print('VIDEOCAPTURE saved ' .. filename)
end
emu.register_frame_done(function()
    if failed or captures >= 3 then return end
    local machine = manager.machine
    local key = machine.input:code_from_token('KEYCODE_F12')
    if not machine.input:code_pressed_once(key) then return end
    local ok, err = pcall(capture, machine)
    if not ok then
        failed = true
        print('VIDEOCAPTURE failed: ' .. tostring(err))
        return
    end
    captures = captures + 1
end)
print('VIDEOCAPTURE: press F12 on a bad frame; up to three read-only graphics captures.')

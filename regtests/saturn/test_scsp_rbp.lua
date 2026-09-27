-- license:BSD-3-Clause
-- SCSP DSP ring buffer pointer: RBP is a seven-bit field (register 402h bits 6-0, ST-077 pp.101-102). Bit 6 must
-- reach the DSP (m_DSP.RBP); the field used to be masked to six bits.
--
--   mame saturnjp -rompath <roms> -nothrottle -video none -sound none -autoboot_script test_scsp_rbp.lua
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local mem = cpu.spaces['program']
local scsp = machine.devices[':scsp']

local function dsp_item(name)
    for path, index in pairs(scsp.items) do
        if path:match('/([^/]+)$') == name then return emu.item(index) end
    end
    error('save item ' .. name .. ' not found')
end

local rbp = dsp_item('m_DSP.RBP')
local failed, done = false, false
emu.register_frame_done(function()
    if done or emu.time() < 3.0 then return end
    done = true
    for _, v in ipairs({0x00, 0x3F, 0x40, 0x7F, 0x55}) do
        -- keep RBL (bits 8-7) at its current value, write only the RBP field
        local cur = mem:read_u16(0x05B00402)
        mem:write_u16(0x05B00402, (cur & 0xFF80) | v)
        local got = rbp:read(0)
        local ok = got == v
        failed = failed or not ok
        print(string.format('SCSP-RBP write %02x -> DSP RBP %02x: %s', v, got, ok and 'PASS' or 'FAIL'))
    end
    print(failed and 'SCSP-RBP FAIL' or 'SCSP-RBP PASS')
    machine:exit()
end)

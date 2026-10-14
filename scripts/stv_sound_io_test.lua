-- license:BSD-3-Clause
-- The sound firmware must not report unconnected ST-V switches as pressed.
local m = manager.machine
local mem = m.devices[':audiocpu'].spaces.program
local frame = 0
STV_SOUND_IO_SUBSCRIPTION = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    if frame ~= 1 and frame ~= 1800 then return end
    local ok, err = pcall(function()
        if frame == 1800 then
            local cpu = m.devices[':maincpu']
            assert(cpu.spaces.program:read_u32(0x060cf888) == 0,
                   'Astra callback initialization did not complete')
            assert(cpu.state.PC.value ~= 0x0600205a, 'Astra entered fatal startup loop')
            assert(cpu.spaces.program:read_u16(0x06000728) & 3 == 0,
                   'unconnected switches produced pressed-state bits')
            m.screens[':screen']:snapshot(m.options.entries['diff_directory']:value() .. '/startup.png')
            print('STV_SOUND_IO_PASS Astra startup and inactive firmware report')
            m:exit()
            return
        end
        assert(mem:read_u16(0x600000) == 0x00ff, 'inactive sound switches')
        assert(mem:read_u8(0x600000) == 0, 'sound switch upper byte')
        assert(mem:read_u8(0x600001) == 0xff, 'sound switch lower byte')
        mem:write_u16(0x600000, 0)
        assert(mem:read_u16(0x600000) == 0x00ff, 'write changed input pins')
        print('STV_SOUND_IO_PASS inactive inputs and byte lanes')
    end)
    if not ok then
        print('STV_SOUND_IO_FAIL ' .. tostring(err))
        m:exit()
    end
end)

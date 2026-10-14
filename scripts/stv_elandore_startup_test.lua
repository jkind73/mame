-- license:BSD-3-Clause
-- Normal game startup must get past SGL's VBlank-OUT/VDP1 completion wait.
local m=manager.machine
local frame=0
local output=m.options.entries['snapshot_directory']:value()
STV_ELANDORE_STARTUP=emu.add_machine_frame_notifier(function()
    frame=frame+1
    if frame==1800 then
        local p=m.devices[':maincpu'].spaces.program
        local tvmd=p:read_u16(0x05f80000)
        assert((tvmd&0x8000)~=0,string.format('Elan display remains disabled: TVMD=%04x',tvmd))
        assert((tvmd&0xff)==0xc3,string.format('Elan has not entered its game video mode: TVMD=%04x',tvmd))
        m.screens[':screen']:snapshot(output..'/startup.png')
        print(string.format('STV_ELANDORE_STARTUP_PASS TVMD=%04x PC=%08x',tvmd,m.devices[':maincpu'].state.CURPC.value))
    end
end)

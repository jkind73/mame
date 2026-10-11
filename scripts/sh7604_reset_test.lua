-- license:BSD-3-Clause
-- Reset during standby NMI settling; uses the harness's synthetic parking ROM.
-- Persistent guard prevents autoboot reload from repeatedly resetting the machine.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local frame=0
local after_reset=rawget(_G,'sh7604_reset_requested') or false
sh7604_reset_test_subscription=emu.add_machine_frame_notifier(function()
    frame=frame+1
    local ok,err=pcall(function()
        if after_reset then
            if frame==8 then
                assert(space:read_u8(0xfffffe91)==0,'reset retained SBY')
                assert(space:read_u16(0xfffffe12)~=0,'reset did not restart FRT')
                local pc=cpu.state.PC.value
                assert(pc==0x100 or pc==0x102,'reset did not release CPU or stale wake timer fired')
                print('SH7604_RESET_PASS reset escapes standby, cancels settling wake, restarts CPU/FRT')
                machine:exit()
            end
        elseif frame==1 then
            space:write_u32(0x05fe00a0,0xffffffff)
            space:write_u16(0x26003000,0x001b)
            space:write_u16(0xfffffe80,0xa507)
            space:write_u8(0xfffffe91,0x80)
            cpu.state.SR.value=0xf0
            cpu.state.CURPC.value=0x26003000
        elseif frame==2 then
            assert(space:read_u16(0xfffffe12)==0,'fixture did not enter standby')
            space:write_u8(0x0010001f,0x18)
        elseif frame==3 then
            assert(space:read_u16(0xfffffe12)==0,'fixture did not remain in settling')
            _G.sh7604_reset_requested=true
            machine:soft_reset()
        end
    end)
    if not ok then print('SH7604_RESET_FAIL '..tostring(err)); machine:exit() end
end)

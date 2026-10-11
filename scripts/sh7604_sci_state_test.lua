-- license:BSD-3-Clause
-- Save/restore a queued SCI transmit and waiting DMA at BRR=255, both CPU cores.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local frame=0
local path=assert(os.getenv('SH7604_SCI_STATE_PATH'),'state path required')
sh7604_sci_state_test_subscription=emu.add_machine_frame_notifier(function()
    frame=frame+1
    local ok,err=pcall(function()
        if frame==1 then
            space:write_u16(0x26002000,0xaffe); space:write_u16(0x26002002,0x0009)
            cpu.state.CURPC.value=0x26002000; cpu.state.SR.value=0xf0
            space:write_u32(0x05fe00a0,0xffffffff)
            space:write_u32(0xffffffb0,0)
            space:write_u8(0xfffffe00,0); space:write_u8(0xfffffe01,255)
            space:write_u8(0xfffffe02,0x20)
            for i=0,3 do space:write_u8(0x26002600+i,0x51+i) end
            space:write_u8(0xfffffe71,2)
            space:write_u32(0xffffff80,0x26002600); space:write_u32(0xffffff84,0xfffffe03)
            space:write_u32(0xffffff88,4); space:write_u32(0xffffff8c,0x1001)
            space:write_u32(0xffffffb0,1)
        elseif frame==2 then
            assert(space:read_u32(0xffffff88)==4)
            space:write_u8(0xfffffe02,0xa0)
        elseif frame==3 then
            assert(space:read_u32(0xffffff88)==1,'slow SCI must wait for byte readiness')
            assert((space:read_u8(0xfffffe04)&0x84)==0,'queued transmit status')
            machine:save(path)
        elseif frame==5 then
            assert(space:read_u32(0xffffff88)==0)
            assert((space:read_u8(0xfffffe04)&0x84)==0x84)
            machine:load(path)
        elseif frame==6 then
            assert((space:read_u8(0xfffffe04)&4)==0,'restored transmit completed too early')
        elseif frame==8 then
            assert(space:read_u32(0xffffff88)==0,'restored DMA failed to finish')
            assert(space:read_u32(0xffffff80)==0x26002604,'restored DMA source progress')
            assert(space:read_u8(0xfffffe03)==0x54,'restored DMA byte order')
            assert((space:read_u8(0xfffffe04)&0x84)==0x84,'restored transmitter failed to finish')
            print('SH7604_SCI_STATE_PASS queued byte, byte-ready DMA stall/rearm, source progress and timer phase restored')
            machine:exit()
        end
    end)
    if not ok then print('SH7604_SCI_STATE_FAIL '..tostring(err)); machine:exit() end
end)

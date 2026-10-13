-- license:BSD-3-Clause
-- Exercise real SMPC CKCHG352/320 through full standby, on both CPU cores.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local frame=0
local base,marker,stack=0x26003000,0x26003500,0x26090000
local function enter(command)
    space:write_u32(0xfffffff0,0xa55a0000)
    space:read_u32(0xfffffff0)
    space:write_u32(0xfffffff0,0xa55a0000)
    space:write_u32(0xfffffff8,0xa55a00c8)
    space:write_u32(0xfffffff4,0xa55a0011)
    space:write_u32(0xfffffff0,0xa55a0038)
    space:write_u32(marker,0)
    space:write_u8(0xfffffe02,0x20)
    space:write_u16(0xfffffe80,0xa507)
    space:write_u8(0xfffffe91,0x80)
    cpu.state.CURPC.value=base
    space:write_u8(0x0010001f,command) -- deferred HALT lets SLEEP execute
end
sh7604_pll_test_subscription=emu.add_machine_frame_notifier(function()
    frame=frame+1
    local ok,err=pcall(function()
        if frame==1 then
            space:write_u32(0x05fe00a0,0xffffffff)
            local code={0x001b,0xd003,0xe101,0x2012,0xaffe,0x0009}
            for i,op in ipairs(code) do space:write_u16(base+(i-1)*2,op) end
            space:write_u32(base+16,marker)
            space:write_u16(base+0x80,0x002b); space:write_u16(base+0x82,0x0009)
            space:write_u32(0x26001000+11*4,base+0x80)
            cpu.state.VBR.value=0x26001000; cpu.state.R15.value=stack; cpu.state.SR.value=0xf0
            space:write_u16(0xfffffee0,0)
            enter(0x0e)
        elseif (frame>=2 and frame<=6) or (frame>=19 and frame<=23) then
            assert(space:read_u32(marker)==0,'PLL transition woke SLEEP prematurely')
            assert(space:read_u8(0xfffffe02)==0,'PLL standby did not initialize SCI on entry')
            assert(space:read_u16(0xfffffe12)==0,'PLL standby allowed FRT clock progress')
            assert(space:read_u32(0xfffffff4)==17,'PLL standby allowed BSC clock progress')
        elseif frame==18 then
            assert(space:read_u32(marker)==1,'CKCHG352 failed to wake after settling')
            assert(cpu.state.R15.value==stack,'352 wake stack')
            assert(space:read_u32(0xffffffb0)==0,'352 clock wake inhibited DMAC')
            assert((space:read_u32(0xfffffff0)&0x80)~=0,'352 wake did not restart BSC refresh')
            enter(0x0f)
        elseif frame==35 then
            assert(space:read_u32(marker)==1,'CKCHG320 failed to wake after settling')
            assert(cpu.state.R15.value==stack,'320 wake stack')
            assert(space:read_u32(0xffffffb0)==0,'320 clock wake inhibited DMAC')
            assert((space:read_u32(0xfffffff0)&0x80)~=0,'320 wake did not restart BSC refresh')
            print('SH7604_PLL_PASS CKCHG352/320, entry reset, peripheral clock halt, delayed NMI and stack')
            machine:exit()
        end
    end)
    if not ok then print('SH7604_PLL_FAIL '..tostring(err)); machine:exit() end
end)

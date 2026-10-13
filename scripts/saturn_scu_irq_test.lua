-- license:BSD-3-Clause
-- Real SH7604/SCU regression: each completed DMA must interrupt exactly once,
-- even when its handler lowers SR before returning. Run on vfkids with
-- -autoboot_delay 0 -autoboot_script scripts/saturn_scu_irq_test.lua.
-- This isolated fixture replaces guest execution; it is not a gameplay test.
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local space = cpu.spaces.program
local frame = 0
local counter, stack = 0x26004000, 0x26090000
local function set_mask(value)
    space:write_u32(0x06004004, value & 0xbfff)
    space:write_u32(0x05fe00a0, value)
end
local function transfer()
    space:write_u32(0x05fe0000, 0x06006000)
    space:write_u32(0x05fe0004, 0x05c01000)
    space:write_u32(0x05fe0008, 4)
    space:write_u32(0x05fe000c, 0x101)
    space:write_u32(0x05fe0014, 7)
    space:write_u32(0x05fe0010, 0x101)
end
local function expect(count)
    local actual = space:read_u32(0x06004000)
    print(string.format('SCU_IRQ_CHECK frame=%d count=%d expected=%d sp=%08x pc=%08x sr=%08x r0=%08x r1=%08x r2=%08x r3=%08x ret=%08x',frame,actual,count,cpu.state.R15.value,cpu.state.PC.value,cpu.state.SR.value,cpu.state.R0.value,cpu.state.R1.value,cpu.state.R2.value,cpu.state.R3.value,space:read_u32(stack-8)))
    assert(actual == count, 'SCU request acknowledged more than once or lost')
    assert(space:read_u32(0x06004008) == 0xbfff, 'SCU acknowledgment did not reset IMS')
    assert(cpu.state.R15.value == stack, 'Interrupt handler did not restore stack')
    assert(space:read_u32(0x05c01000) == 0x12345678, 'DMA payload mismatch')
end
saturn_scu_irq_test_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    if frame < 60 then return end
    local stage = frame - 59
    local ok, err = pcall(function()
        if stage == 1 then
            cpu.state.SR.value = 0xf0
            set_mask(0xffffffff)
            space:write_u32(0x05fe00a4, 0)
            space:write_u16(0xfffffee0, 1) -- external vector mode
            space:write_u16(0x06002000, 0xaffe)
            space:write_u16(0x06002002, 0x0009)
            local code = {0x410e,0xd00f,0x6202,0x7201,0x2022,
                          0xe27f,0x4210,0x8bfd,0xd00c,0x6202,
                          0xd30d,0x2322,0xd20b,0x6222,0x2022,
                          0x002b,0x0009}
            for i,op in ipairs(code) do space:write_u16(0x06003000+(i-1)*2,op) end
            space:write_u32(0x06003040, counter)
            space:write_u32(0x06003044, 0x25fe00a0)
            space:write_u32(0x06003048, counter+4)
            space:write_u32(0x0600304c, counter+8)
            for vector=0x40,0x5f do space:write_u32(0x06001000+vector*4,0x26003000) end
            space:write_u32(0x06004000, 0)
            space:write_u32(0x06006000, 0x12345678)
            cpu.state.VBR.value = 0x26001000
            cpu.state.R15.value = stack
            cpu.state.R1.value = 0
            cpu.state.CURPC.value = 0x26002000
            cpu.state.SR.value = 0
        elseif stage == 2 then
            space:write_u32(0x06004000, 0) -- discard a pre-fixture latched request
            cpu.state.SR.value = 0
            set_mask(0xffffffff & ~(1<<11))
            transfer()
        elseif stage == 3 then
            expect(1)
            transfer()
        elseif stage == 4 then
            expect(2)
            set_mask(0xffffffff)
            transfer()
        elseif stage == 5 then
            expect(2) -- completion stays pending while masked
            set_mask(0xffffffff & ~(1<<11))
        elseif stage == 6 then
            expect(3)
            print('SATURN_SCU_IRQ_PASS exactly-once acknowledgment, rearm, masked completion, stack, payload')
            machine:exit()
        end
    end)
    if not ok then
        print('SATURN_SCU_IRQ_FAIL '..tostring(err))
        machine:exit()
    end
end)

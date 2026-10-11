-- license:BSD-3-Clause
-- Isolated real-device DMA test, run on saturnjp with -autoboot_delay 0
-- -autoboot_script scripts/sh7604_dma_test.lua -video none -sound none.
-- Replaces CPU execution with an interrupt-masked WRAM loop for this test only.
local machine = manager.machine
local cpu = machine.devices[":maincpu"]
local space = cpu.spaces["program"]
local frame = 0
local burst_count = tonumber(os.getenv("SH7604_TEST_BURST_COUNT")) or 2
assert(burst_count >= 1 and burst_count <= 7)
local src, dst = 0x20210100, 0x20210200 -- cache-through bits must survive read-back
sh7604_dma_test_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    if frame == 1 then
        space:write_u16(0x00210000, 0xaffe) -- BRA to itself
        space:write_u16(0x00210002, 0x0009) -- NOP delay slot
        cpu.state["SR"].value = 0xf0
        cpu.state["CURPC"].value = 0x00210000
        for i = 0, 7 do
            space:write_u32(src + i*4, 0x12345600+i)
            space:write_u32(dst + i*4, 0)
        end
        space:write_u32(0xffffffb0, 0)
        space:write_u32(0xffffff80, src)
        space:write_u32(0xffffff84, dst)
        space:write_u32(0xffffff88, 8)
        space:write_u32(0xffffff8c, 0x5a01) -- increment both, longwords, auto-request
        space:write_u32(0xffffffb0, 1)
        for i=0,7 do space:write_u32(dst+0x100+i*4,0xdeadbeef) end
        space:write_u32(0xffffff90,src)
        space:write_u32(0xffffff94,dst+0x100)
        space:write_u32(0xffffff98,burst_count)
        space:write_u32(0xffffff9c,0x5e01) -- short final 16-byte burst
    elseif frame == 2 then
        for i = 0, 7 do
            assert(space:read_u32(dst+i*4)==0x12345600+i, "DMA payload mismatch")
        end
        assert(space:read_u32(0xffffff80)==src+32, "SAR progress/alias mismatch")
        assert(space:read_u32(0xffffff84)==dst+32, "DAR progress/alias mismatch")
        assert(space:read_u32(0xffffff88)==0, "TCR completion mismatch")
        assert((space:read_u32(0xffffff8c)&2)==2, "TE not set")
        for i=0,7 do
            assert(space:read_u32(dst+0x100+i*4)==(i<burst_count and 0x12345600+i or 0xdeadbeef), "short burst overwrote destination")
        end
        assert(space:read_u32(0xffffff98)==0,"short burst TCR mismatch")
        assert(space:read_u32(0xffffff90)==src+math.ceil(burst_count/4)*16,"short burst SAR mismatch")
        print("SH7604_REAL_DMA_PASS payload, SAR/DAR alias bits, TCR and TE; burst_count="..burst_count)
        machine:exit()
    end
end)

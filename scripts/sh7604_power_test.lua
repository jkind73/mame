-- license:BSD-3-Clause
-- Real-device SCI TX DMA and full-standby entry/wake regression, both CPU cores.
-- Isolated saturnjp guest; -autoboot_delay 0, -video none -sound none.
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local space = cpu.spaces.program
local frame = 0
local statepath=os.getenv('SH7604_POWER_STATE_PATH')
local base, marker, vectors, stack = 0x26002000, 0x26002500, 0x26001000, 0x26090000
local function nmi()
    space:write_u8(0x0010001f,0x18) -- SMPC NMIREQ
end
sh7604_power_test_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    local ok,err=pcall(function()
        if frame == 1 then
            space:write_u32(0x05fe00a0,0xffffffff)
            space:write_u16(base,0xaffe); space:write_u16(base+2,0x0009)
            cpu.state.SR.value=0xf0; cpu.state.CURPC.value=base
            space:write_u32(0xffffffb0,0)
            space:write_u8(0xfffffe00,0); space:write_u8(0xfffffe01,1)
            space:write_u16(0xfffffe60,0x7000) -- SCI priority 7; CPU mask 15 must not block DMA
            space:write_u8(0xfffffe02,0x20) -- TE enabled, TIE disabled
            for i=0,2 do space:write_u8(0x26002600+i,0x41+i) end
            space:write_u8(0xfffffe71,2) -- TXI
            space:write_u32(0xffffff80,0x26002600)
            space:write_u32(0xffffff84,0xfffffe03)
            space:write_u32(0xffffff88,3)
            space:write_u32(0xffffff8c,0x1001) -- bytes, increment source, fixed TDR, AR=0
            space:write_u32(0xffffffb0,1)
        elseif frame == 2 then
            assert(space:read_u32(0xffffff88)==3,'DMA ran without TIE')
            space:write_u8(0xfffffe02,0xa0)
        elseif frame == 3 then
            assert(space:read_u32(0xffffff88)==0,'TX DMA did not rearm per byte')
            assert((space:read_u32(0xffffff8c)&2)==2,'TX DMA did not set TE')
            assert(space:read_u8(0xfffffe03)==0x43,'TX DMA payload/order')
            assert((space:read_u8(0xfffffe04)&0x84)==0x84,'TX did not finish')
            space:write_u8(0xfffffe02,0x20) -- disable TXI before unmasking CPU
            local code={0x001b,0xd003,0xe101,0x2012,0xaffe,0x0009}
            for i,op in ipairs(code) do space:write_u16(base+(i-1)*2,op) end
            space:write_u32(base+16,marker); space:write_u32(marker,0)
            space:write_u16(base+0x80,0x002b); space:write_u16(base+0x82,0x0009)
            space:write_u32(vectors+11*4,base+0x80)
            for v=64,95 do space:write_u32(vectors+v*4,base+0x80) end
            cpu.state.VBR.value=vectors; cpu.state.R15.value=stack
            cpu.state.CURPC.value=base; cpu.state.SR.value=0
            space:write_u16(0xfffffe80,0xa507) -- max settling delay (~74 ms)
            space:write_u16(0xfffffee0,0) -- falling physical NMI edge
            space:write_u8(0xfffffe91,0x80)
            space:write_u32(0x05fe00a0,0xfffffffe) -- unmask external VBLANK IRQ
        elseif frame == 4 then
            assert(space:read_u8(0xfffffe02)==0,'SCI was not initialized on ENTRY')
            assert(space:read_u32(0xffffff8c)==0,'DMA CHCR not initialized on ENTRY')
            assert(space:read_u32(0xffffffb0)==0,'DMAOR not initialized on ENTRY')
            assert(space:read_u16(0xfffffe12)==0,'FRT advanced in standby')
            assert(space:read_u32(marker)==0,'maskable IRQ woke standby')
            if statepath then machine:save(statepath) end
            nmi()
        elseif frame == 5 or frame == 6 then
            assert(space:read_u32(marker)==0,'NMI skipped WDT settling delay')
            assert(space:read_u16(0xfffffe12)==0,'FRT advanced during settling')
        elseif frame == 10 then
            assert(space:read_u32(marker)==1,'NMI did not resume after SLEEP')
            assert(cpu.state.R15.value==stack,'wake exception stack not restored')
            space:write_u32(0x05fe00a0,0xffffffff)
            if statepath then machine:load(statepath)
            else
                print('SH7604_POWER_PASS SCI TX DMA enable/rearm/payload; standby entry, clock halt, maskable rejection, delayed NMI, stack')
                machine:exit()
            end
        elseif frame == 11 and statepath then
            assert(space:read_u32(marker)==0,'standby save/load lost guest state')
            nmi()
        elseif frame == 17 and statepath then
            assert(space:read_u32(marker)==1,'standby save/load failed to wake')
            assert(cpu.state.R15.value==stack,'save/load wake stack')
            print('SH7604_POWER_PASS SCI TX DMA; standby entry/halt/NMI/settling; suspended save/load/wake')
            machine:exit()
        end
    end)
    if not ok then print('SH7604_POWER_FAIL '..tostring(err)); machine:exit() end
end)

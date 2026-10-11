-- license:BSD-3-Clause
-- Real VDP2 register reads, all horizontal modes, synthetic parked SH2 guest.
local machine=manager.machine
local space=machine.devices[':maincpu'].spaces.program
local started=false
saturn_scan_timing_subscription=emu.add_machine_frame_notifier(function()
    if started then return end
    started=true
    saturn_scan_timing_coroutine=coroutine.create(function()
        for mode=0,7 do
            space:write_u16(0x05f80000,0x8000|mode)
            for sample=1,160 do
                emu.wait(0.000001)
                space:read_u16(0x05f80002) -- internal latch
                local counter=space:read_u16(0x05f80008)
                local phase
                if (mode&4)~=0 then
                    assert(counter<512,'exclusive HCNT width')
                    phase=(mode&2)~=0 and ((counter<<1)&511) or counter
                    local stop=(mode&1)~=0 and 0x176 or 0x158
                    local target=(mode&1)~=0 and 0x1d0 or 0x1b0
                    assert(phase<=stop or phase>=target,'exclusive skipped range')
                else
                    phase=counter>>1
                    local stop=(mode&1)~=0 and 374 or 346
                    assert(phase<=stop or phase>=0x1b0,'ordinary skipped range')
                end
                local flags=space:read_u16(0x05f80004)
                local blank
                if (mode&4)~=0 then blank=(phase&511)>=((mode&1)~=0 and 0x168 or 0x148) or phase<8
                else blank=phase>=((mode&1)~=0 and 0x164 or 0x144) or phase<4 end
                assert(((flags&4)~=0)==blank,'HBLANK mode '..mode)
            end
        end
        print('SATURN_SCAN_TIMING_PASS')
        machine:exit()
    end)
    local ok,err=coroutine.resume(saturn_scan_timing_coroutine)
    if not ok then error(err) end
end)

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped SCSP MIDI FIFO depth/status/drain timing on both CPU buses.

Guest-visible registers and virtual time only: no private state is patched and
no MIDI wire is injected. MIDI *input* has no driver wiring, so its FIFO depth
and overflow latch stay method-level evidence (regtests/saturn/test_scsp_irq_ports.py).
Missing binary/BIOS is a skip, never a native pass.
"""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
CASES=24
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local base=0x05b00000
local function test()
    park();local snd=assert(m.devices[':audiocpu']);local ss=snd.spaces['program']
    ss:write_u16(0x70000,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
    sp:write_u16(base+0x41e,0);sp:write_u16(base+0x42a,0)
    emu.wait(emu.attotime.from_msec(20))
    local step=emu.attotime.from_usec(50)
    -- One 10-bit frame at 31.25 kbps is 320 usec; polling at 50 usec keeps the
    -- windows wide enough for exact virtual timing yet narrow enough to tell
    -- four queued frames (1280 usec) from five (1600) or from a frame-start
    -- pop edge (960).
    local function drain(limit)
        for n=1,limit do
            emu.wait(step)
            if (sp:read_u16(base+0x420)&0x200)~=0 then return n end
        end
        return -1
    end
    local case=0
    for _,bus in ipairs({{space=sp,base=base},{space=ss,base=0x100000}}) do
      local function status() return bus.space:read_u16(bus.base+0x404)&0xff00 end
      local function put(width,value)
        if width==0 then bus.space:write_u16(bus.base+0x406,value)
        else bus.space:write_u8(bus.base+0x406+width-1,value) end
      end
      for width=0,2 do for _,value in ipairs({0x00,0x5a,0xa5,0xff}) do
        case=case+1;local before=#fails;local queues=width~=1
        check('idle_status'..case,status(),0x0900)
        check('idle_mobuf_zero'..case,bus.space:read_u16(bus.base+0x406),0)
        check('idle_sound_pending'..case,sp:read_u16(base+0x420)&0x200,0x200)
        check('idle_main_pending'..case,sp:read_u16(base+0x42c)&0x200,0x200)
        put(width,value)
        if queues then
            check('one_status'..case,status(),0x0100)
            check('one_sound_activity'..case,sp:read_u16(base+0x420)&0x200,0)
            check('one_main_activity'..case,sp:read_u16(base+0x42c)&0x200,0)
            local n=drain(30)
            check('one_frame_window'..case,(n>=5 and n<=10) and 1 or 0,1)
            check('one_drained_status'..case,status(),0x0900)
            check('one_drained_pending'..case,sp:read_u16(base+0x420)&0x200,0x200)
            for i=1,4 do put(width,(value+i)&0xff) end
            check('full_status'..case,status(),0x1100)
            put(width,(value+5)&0xff)
            check('fifth_status'..case,status(),0x1100)
            check('fifth_mobuf_zero'..case,bus.space:read_u16(bus.base+0x406),0)
            check('fifth_sound_activity'..case,sp:read_u16(base+0x420)&0x200,0)
            local f=drain(60)
            check('four_frame_window'..case,(f>=23 and f<=30) and 1 or 0,1)
            check('full_drained_status'..case,status(),0x0900)
            check('full_drained_pending'..case,sp:read_u16(base+0x420)&0x200,0x200)
            check('full_drained_main'..case,sp:read_u16(base+0x42c)&0x200,0x200)
        else
            check('lane_status'..case,status(),0x0900)
            check('lane_sound_pending'..case,sp:read_u16(base+0x420)&0x200,0x200)
            emu.wait(emu.attotime.from_usec(400))
            check('lane_status_later'..case,status(),0x0900)
            for i=1,5 do put(width,(value+i)&0xff) end
            check('lane_full_status'..case,status(),0x0900)
            check('lane_full_pending'..case,sp:read_u16(base+0x420)&0x200,0x200)
        end
        if #fails==before then print('SCSP_MIDI_FIFO case='..case..' PASS') end
      end end
    end
    if #fails==0 then print('SCSP_MIDI_FIFO PASS cases='..case)
    else for _,f in ipairs(fails) do print('SCSP_MIDI_FIFO FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SCSP_MIDI_FIFO FAIL '..tostring(err));m:exit() end
    end)()
end)
print('SCSP_MIDI_FIFO armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_MIDI_FIFO FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_MIDI_FIFO case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,CASES+1)] or
        len(re.findall(r'^SCSP_MIDI_FIFO PASS cases=%d$'%CASES,text,re.M))!=1):
        raise RuntimeError('SCSP MIDI FIFO fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP MIDI FIFO: %d depth/status/drain-window cases passed live'%CASES)

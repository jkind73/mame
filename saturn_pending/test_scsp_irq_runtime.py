#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual SH-2/68000 mapped SCSP IRQ commands; sources raised by timers, DMA and CPU."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local base=0x05b00000
local function dma()
    sp:write_u16(base+0x412,0x8000);sp:write_u16(base+0x414,0x700)
    sp:write_u16(base+0x416,0x1002)
end
local function seed()
    for i=0,2 do sp:write_u16(base+0x418+i*2,0xff) end
    sp:write_u16(base+0x406,0) -- real serial transmission raises MIDI-output-empty
    emu.wait(emu.attotime.from_usec(500))
    dma();sp:write_u16(base+0x420,0x20);sp:write_u16(base+0x42c,0x20)
    assert((sp:read_u16(base+0x420)&0x7f0)==0x7f0,'sound source setup failed')
    assert((sp:read_u16(base+0x42c)&0x7f0)==0x7f0,'main source setup failed')
    for i=0,2 do assert((sp:read_u16(base+0x418+i*2)&255)~=255,'timer still at expiry') end
end
local function test()
    park();local snd=assert(m.devices[':audiocpu']);local ss=snd.spaces['program']
    ss:write_u16(0x70000,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
    sp:write_u16(base+0x400,0);sp:write_u16(base+0x41e,0);sp:write_u16(base+0x42a,0)
    for i=0,511 do sp:write_u16(base+0x800+i*2,0) end
    sp:write_u16(0x05a08000,0)
    local case=0
    for _,bus in ipairs({{space=sp,base=base},{space=ss,base=0x100000}}) do
      for _,main in ipairs({false,true}) do
        local port=main and 0x42e or 0x422
        for _,stale in ipairs({0,0xff,0xff00,0xffff}) do for width=0,2 do
          for _,command in ipairs({0,0x10,0x20,0x40,0x80,0x100,0x200,0x400,0x7ff}) do
            case=case+1;local before=#fails
            bus.space:write_u16(bus.base+port,stale);seed()
            local sound=sp:read_u16(base+0x420)&0x7ff;local host=sp:read_u16(base+0x42c)&0x7ff
            local mask=width==0 and 0xffff or (width==1 and 0xff00 or 0xff)
            if width==0 then bus.space:write_u16(bus.base+port,command)
            else bus.space:write_u8(bus.base+port+width-1,width==1 and command>>8 or command&255) end
            local active=command&mask
            check('sound_ack'..case,sp:read_u16(base+0x420)&0x7ff,main and sound or sound&~active)
            check('main_ack'..case,sp:read_u16(base+0x42c)&0x7ff,main and host&~active or host)
            if #fails==before then print('SCSP_IRQ case='..case..' PASS') end
          end
        end end
      end
    end
    if #fails==0 then print('SCSP_IRQ PASS cases=432')
    else for _,f in ipairs(fails) do print('SCSP_IRQ FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SCSP_IRQ FAIL '..tostring(err));m:exit() end
    end)()
end)
print('SCSP_IRQ armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_IRQ FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_IRQ case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,433)] or
        len(re.findall(r'^SCSP_IRQ PASS cases=432$',text,re.M))!=1):
        raise RuntimeError('SCSP IRQ fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP IRQ: 432 mapped acknowledgement cases passed live')

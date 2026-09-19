#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped MIDI output byte lanes and real serial-completion IRQs, not RX pin QA."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local base=0x05b00000
local function test()
    park();local snd=assert(m.devices[':audiocpu']);local ss=snd.spaces['program']
    ss:write_u16(0x70000,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
    sp:write_u16(base+0x41e,0);sp:write_u16(base+0x42a,0)
    emu.wait(emu.attotime.from_msec(20))
    local case=0
    for _,bus in ipairs({{space=sp,base=base},{space=ss,base=0x100000}}) do
      for width=0,2 do for value=0,255 do
        case=case+1;local before=#fails
        sp:write_u16(base+0x406,0x5a);emu.wait(emu.attotime.from_usec(500))
        assert((sp:read_u16(base+0x420)&0x200)==0x200,'sound transmit setup failed')
        assert((sp:read_u16(base+0x42c)&0x200)==0x200,'main transmit setup failed')
        if width==0 then bus.space:write_u16(bus.base+0x406,(value<<8)|value)
        else bus.space:write_u8(bus.base+0x406+width-1,value) end
        local want=width==1 and 0x200 or 0
        check('sound_output_activity'..case,sp:read_u16(base+0x420)&0x200,want)
        check('main_output_activity'..case,sp:read_u16(base+0x42c)&0x200,want)
        emu.wait(emu.attotime.from_usec(500))
        check('sound_output_completion'..case,sp:read_u16(base+0x420)&0x200,0x200)
        check('main_output_completion'..case,sp:read_u16(base+0x42c)&0x200,0x200)
        if #fails==before then print('SCSP_MIDI case='..case..' PASS') end
      end end
    end
    if #fails==0 then print('SCSP_MIDI PASS cases=1536')
    else for _,f in ipairs(fails) do print('SCSP_MIDI FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SCSP_MIDI FAIL '..tostring(err));m:exit() end
    end)()
end)
print('SCSP_MIDI armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_MIDI FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_MIDI case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,1537)] or
        len(re.findall(r'^SCSP_MIDI PASS cases=1536$',text,re.M))!=1):
        raise RuntimeError('SCSP MIDI fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP MIDI: 1536 output-byte/serial-completion cases passed live')

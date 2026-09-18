#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped SCSP microprograms: zero-tail state and live program writes, not audio QA."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local base=0x05b00000
local function blank()
    local code={};for i=1,512 do code[i]=0 end;return code
end
local function upload(code)
    for i=1,512 do sp:write_u16(base+0x800+(i-1)*2,code[i]) end
    sp:write_u16(base+0xbf0,code[505])
end
local function code_for(last)
    local code=blank();code[3]=0x1002;code[6]=0x20;code[7]=2
    code[last*4+2]=0xa000;code[last*4+3]=0xa002;code[last*4+4]=0x100
    return code
end
local function scaled(word)
    local v=word>=0x8000 and word-0x10000 or word
    return ((v*256*4095//4096)//256)&0xffff
end
local function test()
    park()
    local snd=m.devices[':audiocpu']
    if snd then
        snd.spaces['program']:write_u16(0x100,0x60fe)
        snd.state['SR'].value=0x2700;snd.state['PC'].value=0x100
    end
    sp:write_u16(base+0x400,0);sp:write_u16(base+0x402,0)
    sp:write_u16(base+0x700,0x7ff8);sp:write_u16(base+0x702,0)
    sp:write_u16(base+0x780,0x4000)
    -- Clear TEMP through actual microinstructions, not private DSP injection.
    local clear=blank()
    for i=0,127 do clear[i*4+1]=0x80|i;clear[i*4+2]=0x2000;clear[i*4+3]=2;clear[i*4+4]=0x200 end
    upload(clear);emu.wait(emu.attotime.from_msec(2))
    sp:write_u16(0x05a08000,0x1234)
    local seed=code_for(3);seed[19]=0x1100;upload(seed);emu.wait(emu.attotime.from_usec(500))
    check('seed_effect1',sp:read_u16(base+0xec2),scaled(0x1234))
    local case=0
    for _,last in ipairs({3,5,31,63,125,127}) do
      for _,word in ipairs({0,0x1234,0x7fff,0x8000,0xffff}) do
        case=case+1;local before=#fails
        sp:write_u16(0x05a08000,word);upload(code_for(last))
        emu.wait(emu.attotime.from_usec(500))
        check('memory_control'..case,sp:read_u32(base+0xe00)&0xffffff,word<<8)
        check('zero_tail_effect'..case,sp:read_u16(base+0xec0),last==127 and scaled(word) or 0)
        if #fails==before then print('SCSP_DSP case='..case..' PASS') end
      end
    end
    case=case+1;local before=#fails
    sp:write_u16(0x05a08000,0x1234);upload(code_for(3));emu.wait(emu.attotime.from_usec(500))
    check('unwritten_effect_persists',sp:read_u16(base+0xec2),scaled(0x1234))
    -- Step127 word2 is not the legacy Start trigger at step126 word0.
    sp:write_u16(base+0xbfc,0x1100);emu.wait(emu.attotime.from_usec(500))
    check('live_tail_extension',sp:read_u16(base+0xec2),0)
    if #fails==before then print('SCSP_DSP case='..case..' PASS') end
    if #fails==0 then print('SCSP_DSP PASS cases=31')
    else for _,f in ipairs(fails) do print('SCSP_DSP FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SCSP_DSP FAIL '..tostring(err));m:exit() end
    end)()
end)
print('SCSP_DSP armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_DSP FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_DSP case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,32)] or
        len(re.findall(r'^SCSP_DSP PASS cases=31$',text,re.M))!=1):
        raise RuntimeError('SCSP DSP fixture failed:\n'+text[-12000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP DSP: 31 zero-tail/live-program cases passed live')

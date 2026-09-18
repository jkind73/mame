#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped DSP jump/MVI/loop programs exercise wrapped and nonwrapped slots.

No DSP register/debug-state mutation: all setup goes through SCU host ports.
"""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA

runner.LUA=COMMON_LUA+r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local function writecode(pc,words)
        sp:write_u32(control,0x8000|pc)
        for _,op in ipairs(words) do sp:write_u32(program,op) end
    end
    local function run(pc,flags)
        sp:write_u32(control,0x18000|pc|flags)
        for n=1,100 do
            emu.wait(emu.attotime.from_usec(10))
            if (sp:read_u32(control)&0x10000)==0 then return end
        end
        error('DSP program did not end')
    end
    local case=0
    for _,pc in ipairs({0x7f,0xff}) do
        for kind=1,6 do
            case=case+1
            local before=#fails
            sp:write_u32(addr,0)
            for i=1,4 do sp:write_u32(data,0xdeadbeef) end
            -- MOV #0,CT0; MOV #2,LOP; MOV #4,TOP; END.
            writecode(16,{0x1c00,0x1a02,0x1b04,0xf0000000});run(16,0)
            writecode((pc+1)&255,{0x1012,0xf0000000}) -- slot writes MC0, then END
            writecode(4,{0xf0000000})
            local ops={0xd0000004,0xd1080004,0xd1080004,0xb0000004,0xe0000000,0xe8000000}
            writecode(pc,{ops[kind]})
            run(pc,kind==2 and 0x200000 or 0)
            sp:write_u32(addr,0)
            local count=kind==6 and 3 or 1
            for i=1,4 do
                check('case'..case..'_word'..i,sp:read_u32(data),i<=count and 0x12 or 0xdeadbeef)
            end
            if #fails==before then print('DSP_PIPELINE case='..case..' PASS') end
        end
    end
    if #fails==0 then print('DSP_PIPELINE PASS cases=12')
    else for _,f in ipairs(fails) do print('DSP_PIPELINE FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_PIPELINE FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('DSP_PIPELINE armed')
'''

def validate_output(text,returncode):
    if (returncode or 'DSP_PIPELINE FAIL' in text or 'LUA ERROR' in text or
            [int(n) for n in re.findall(r'^DSP_PIPELINE case=(\d+) PASS$',text,re.M)]!=list(range(1,13)) or
            len(re.findall(r'^DSP_PIPELINE PASS cases=12$',text,re.M))!=1):
        raise RuntimeError('DSP pipeline fixture failed:\n'+text[-10000:])

runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP pipeline: 12 wrapped/nonwrapped control-flow programs passed live')

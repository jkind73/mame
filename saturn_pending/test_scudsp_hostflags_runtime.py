#!/usr/bin/env python3
# license:BSD-3-Clause
"""Read-only S/Z under full, halfword and byte host control-port writes."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local control,program=0x05fe0080,0x05fe0084
local function test()
    park();local case=0
    for preset=0,3 do for attempt=0,3 do for width=0,6 do
        case=case+1;local before=#fails
        sp:write_u32(control,0x8000)
        local value=preset==0 and 1 or (preset==1 and 0 or 0x1ffffff)
        local code={0x20000,0x94000000|value,preset==3 and 0x08000000 or 0x10000000,0xf0000000}
        for _,op in ipairs(code) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(10))
        assert((sp:read_u32(control)&0x10000)==0,'DSP did not stop')
        -- Preset3 uses the existing negative-OR Z workaround as a control,
        -- not an assertion that that workaround is hardware-correct.
        local flags=sp:read_u32(control)&0x600000
        local expected=({0,0x200000,0x400000,0x600000})[preset+1]
        check('guest_flags'..case,flags,expected)
        local value=attempt<<21
        if width==0 then sp:write_u32(control,value)
        elseif width<=2 then
            local off=(width-1)*2;sp:write_u16(control+off,(value>>(16-off*8))&0xffff)
        else
            local off=width-3;sp:write_u8(control+off,(value>>(24-off*8))&255)
        end
        check('read_only'..case,sp:read_u32(control)&0x600000,flags)
        if #fails==before then print('DSP_HOSTFLAGS case='..case..' PASS')
        else print('DSP_HOSTFLAGS case='..case..' FAIL') end
    end end end
    if #fails==0 then print('DSP_HOSTFLAGS PASS cases=112')
    else for _,f in ipairs(fails) do print('DSP_HOSTFLAGS FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_HOSTFLAGS FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_HOSTFLAGS armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_HOSTFLAGS FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^DSP_HOSTFLAGS case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,113)] or
        len(re.findall(r'^DSP_HOSTFLAGS PASS cases=112$',text,re.M))!=1):
        raise RuntimeError('DSP host flag fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP host flags: 112 guest-ALU/read-only/masked-write cases passed live')

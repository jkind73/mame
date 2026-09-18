#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped DSP read-DMA programs must treat all Work RAM-H mirrors identically."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local base=0x06010000
    local words={0x1234abcd,0x5678dcba,0x2468ace0}
    for i,word in ipairs(words) do sp:write_u32(base+(i-1)*4,word) end
    local case=0
    for mirror=0,31 do for mode=0,7 do for indirect=0,1 do for hold=0,1 do
        case=case+1
        local before=#fails
        local source=base+mirror*0x100000
        -- Confirm that the public memory map exposes the same physical RAM.
        for i,word in ipairs(words) do check('mirror'..mirror,sp:read_u32(source+(i-1)*4),word) end
        sp:write_u32(control,0x8000)
        sp:write_u32(addr,0)
        for i=1,3 do sp:write_u32(data,0xdeadbeef) end
        sp:write_u32(addr,64);sp:write_u32(data,3)
        local code={0x1c00,0x1d00,0x98000000|(source>>2),
            0xc0000000|(mode<<15)|(hold<<14)|(indirect<<13)|(indirect==1 and 1 or 3),0xf0000000}
        for _,op in ipairs(code) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000)
        local done=false
        for n=1,100 do
            emu.wait(emu.attotime.from_usec(10))
            if (sp:read_u32(control)&0x810000)==0 then done=true;break end
        end
        assert(done,'DSP read DMA completion timeout')
        sp:write_u32(addr,0)
        for i=1,3 do check('case'..case..'_word'..i,sp:read_u32(data),(mode&2)==0 and words[1] or words[i]) end
        if #fails==before then print('DSP_READ case='..case..' PASS') end
    end end end end
    if #fails==0 then print('DSP_READ PASS cases=1024')
    else for _,f in ipairs(fails) do print('DSP_READ FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_READ FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('DSP_READ armed')
'''

def validate_output(text,returncode):
    if (returncode or 'DSP_READ FAIL' in text or 'LUA ERROR' in text or
            [int(n) for n in re.findall(r'^DSP_READ case=(\d+) PASS$',text,re.M)]!=list(range(1,1025)) or
            len(re.findall(r'^DSP_READ PASS cases=1024$',text,re.M))!=1):
        raise RuntimeError('DSP read DMA fixture failed:\n'+text[-10000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP read DMA: 1024 Work RAM-H mirror/mode programs passed live')

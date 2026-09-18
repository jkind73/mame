#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped MVI/PRG-DMA/MVI-PC overlays must load and execute DSP instructions.

Covers the documented MVI-PC serialized sequence, not unrestricted self-modifying
code or alternate END/RA0/WA0 serialization. No private DSP state is written.
"""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local base=0x06010000
    local function writecode(pc,words)
        sp:write_u32(control,0x8000|pc)
        for _,op in ipairs(words) do sp:write_u32(program,op) end
    end
    local function run(pc)
        sp:write_u32(control,0x18000|pc)
        for n=1,100 do
            emu.wait(emu.attotime.from_usec(10))
            if (sp:read_u32(control)&0x810000)==0 then return end
        end
        error('DSP overlay did not finish')
    end
    local case=0
    for _,target in ipairs({3,64,128,255}) do for _,count in ipairs({2,4}) do
    for indirect=0,1 do for hold=0,1 do
        case=case+1
        local before=#fails
        -- Initialize CTs with real instructions before the three-op loader.
        writecode(32,{0x1c00,0x1d00,0xf0000000});run(32)
        sp:write_u32(addr,0)
        for i=1,5 do sp:write_u32(data,0xdeadbeef) end
        sp:write_u32(addr,64);sp:write_u32(data,count)
        local placeholders={}
        for i=1,count do
            local op=i==count and 0xf0000000 or (0x1000|0x10+i)
            sp:write_u32(base+(i-1)*4,op)
            placeholders[i]=0xf0000000
        end
        writecode(target,placeholders)
        -- Completion returns to TOP=3. Out-of-line overlays use a trampoline;
        -- an inline overlay replaces the old prefetched END at 3 itself.
        if target==3 then writecode(3,{0xf0000000})
        else writecode(3,{0xd0000000|target,0}) end
        writecode(0,{0x98000000|(base>>2),
            0xc0010400|(hold<<14)|(indirect<<13)|(indirect==1 and 1 or count),
            0xb0000000|target})
        run(0)
        sp:write_u32(addr,0)
        for i=1,5 do check('case'..case..'_word'..i,sp:read_u32(data),i<count and 0x10+i or 0xdeadbeef) end
        if #fails==before then print('DSP_PRAM case='..case..' PASS') end
    end end end end
    if #fails==0 then print('DSP_PRAM PASS cases=32')
    else for _,f in ipairs(fails) do print('DSP_PRAM FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_PRAM FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('DSP_PRAM armed')
'''

def validate_output(text,returncode):
    if (returncode or 'DSP_PRAM FAIL' in text or 'LUA ERROR' in text or
            [int(n) for n in re.findall(r'^DSP_PRAM case=(\d+) PASS$',text,re.M)]!=list(range(1,33)) or
            len(re.findall(r'^DSP_PRAM PASS cases=32$',text,re.M))!=1):
        raise RuntimeError('DSP program-RAM fixture failed:\n'+text[-10000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP program RAM: 32 mapped loader/overlay programs passed live')

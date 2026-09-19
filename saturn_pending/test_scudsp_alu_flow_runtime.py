#!/usr/bin/env python3
# license:BSD-3-Clause
"""Public-port ALU bypass/high-half programs with same-cycle result capture."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local function signed(n) return n>=0x80000000 and n-0x100000000 or n end
local function test()
    park();local case=0
    for _,seed in ipairs({{0,1},{0xffffffff,1},{0x7fffffff,0x10000},{0x80000000,0x10000}}) do
    for _,a in ipairs({0,1,0x80000000,0xffffffff}) do
    for _,op in ipairs({0,1,2,3,4,5,6,8,9,10,11,15}) do
        case=case+1;local before=#fails;local b=0x12345678
        sp:write_u32(control,0x8000)
        sp:write_u32(addr,0);sp:write_u32(data,seed[1])
        sp:write_u32(addr,64);sp:write_u32(data,seed[2])
        sp:write_u32(addr,128);sp:write_u32(data,a);sp:write_u32(data,b)
        sp:write_u32(addr,192);sp:write_u32(data,0xdeadbeef);sp:write_u32(data,0xdeadbeef)
        -- Seed a wide ALU/A value, replace A, then compute and capture the
        -- result on the SAME instruction. Latch A for the following ALH read.
        local code={0x1c00,0x1d00,0x1e00,0x1f00,0x20000,0x02084000,
            0x01000000,0x18040000,0x78000,0x3502,
            (op<<26)|0x40000|0x3309,0x330a,0xf0000000}
        for _,word in ipairs(code) do sp:write_u32(program,word) end
        sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(10))
        check('finished'..case,sp:read_u32(control)&0x810000,0)
        local lo=a
        if op==1 then lo=a&b elseif op==2 then lo=a|b elseif op==3 then lo=a~b
        elseif op==4 then lo=(a+b)&0xffffffff elseif op==5 then lo=(a-b)&0xffffffff
        elseif op==8 then lo=(a>>1)|(a&0x80000000)
        elseif op==9 then lo=((a>>1)|(a<<31))&0xffffffff
        elseif op==10 then lo=(a<<1)&0xffffffff
        elseif op==11 then lo=((a<<1)|(a>>31))&0xffffffff
        elseif op==15 then lo=((a<<8)|(a>>24))&0xffffffff end
        local result=(signed(a)&0xffff00000000)|lo
        if op==6 then result=(signed(a)+b)&0xffffffffffff end
        sp:write_u32(addr,192)
        check('low'..case,sp:read_u32(data),result&0xffffffff)
        check('high'..case,sp:read_u32(data),(result>>16)&0xffffffff)
        if #fails==before then print('DSP_ALU_FLOW case='..case..' PASS')
        else print('DSP_ALU_FLOW case='..case..' FAIL') end
    end end end
    if #fails==0 then print('DSP_ALU_FLOW PASS cases=192')
    else for _,f in ipairs(fails) do print('DSP_ALU_FLOW FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_ALU_FLOW FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_ALU_FLOW armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_ALU_FLOW FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^DSP_ALU_FLOW case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,193)] or
        len(re.findall(r'^DSP_ALU_FLOW PASS cases=192$',text,re.M))!=1):
        raise RuntimeError('DSP ALU dataflow fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP ALU dataflow: 192 entry-A/bypass/high-half programs passed live')

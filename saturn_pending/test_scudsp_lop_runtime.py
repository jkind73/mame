#!/usr/bin/env python3
# license:BSD-3-Clause
"""Observe the documented12-bit LOP through complete BTM/LPS iteration counts."""
import re
import test_smpc_save_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local done,frames=false,0
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local function test()
    park();local case=0
    for _,loop in ipairs({0,1}) do for mode=0,4 do
    for _,value in ipairs({0,1,0xfff,0x1000,0x1fff,0xffff,0x12345678,0xffffffff}) do
        case=case+1;local before=#fails
        sp:write_u32(control,0x8000)
        sp:write_u32(addr,0);sp:write_u32(data,value)
        sp:write_u32(addr,128);sp:write_u32(data,0xbad)
        local opcode,expected=0x3a00,value&0xfff
        if mode==1 then
            opcode=0x1a00|(value&0xff)
            local short=value&0xff;if short>=128 then short=short-256 end
            expected=short&0xfff
        elseif mode==2 then opcode=0xa8000000|(value&0x1ffffff)
        elseif mode==3 or mode==4 then
            opcode=0xab080000|(value&0x7ffff);if mode==4 then expected=3 end
        end
        local code={0x1c00,0x1e00,0x20000,mode==4 and 0x1501 or 0x1500,
            3<<26,0x1a03,opcode,0x1501,0x20000,0x1b0a}
        if loop==0 then
            -- TOP=10; increment A; BTM; harmless prefetched slot.
            for _,word in ipairs({0x10040000,0xe0000000,0,0x3209,0xf0000000}) do code[#code+1]=word end
        else
            -- Repeat the ADD/MOV-ALU,A instruction following LPS.
            for _,word in ipairs({0xe8000000,0x10040000,0x3209,0xf0000000}) do code[#code+1]=word end
        end
        for _,word in ipairs(code) do sp:write_u32(program,word) end
        sp:write_u32(control,0x18000)
        -- Also lets the broken16-bit counter finish; not a cycle-accuracy test.
        emu.wait(emu.attotime.from_msec(30))
        check('halt'..case,sp:read_u32(control)&0x10000,0)
        sp:write_u32(addr,128);check('iterations'..case,sp:read_u32(data),expected+1)
        if #fails==before then print('DSP_LOP case='..case..' PASS') end
    end end end
    if #fails==0 then print('DSP_LOP PASS cases=80')
    else for _,f in ipairs(fails) do print('DSP_LOP FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if done or frames<180 then return end;done=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_LOP FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_LOP armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_LOP FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_LOP case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,81)] or
            len(re.findall(r'^DSP_LOP PASS cases=80$',text,re.M))!=1):
        raise RuntimeError('DSP loop-counter fixture failed:\n'+text[-14000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP loop counter: 80 write-path/BTM/LPS programs passed live')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped arithmetic programs; a single post-execution PPAF read preserves V.

32-bit input boundaries, sign-extended AD2 inputs, sticky V and read-clear.
Multiplier-built P operands additionally exercise actual 48-bit overflow boundaries.
"""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local values={0,1,2,0x7fffffff,0x80000000,0x80000001,0xfffffffe,0xffffffff}
    local function signed(n) return n>=0x80000000 and n-0x100000000 or n end
    local case=0
    local function run(op,a,b,sticky,x,y)
        case=case+1
        local before=#fails
        sp:read_u32(control) -- clear V left by any prior program
        sp:write_u32(addr,0);sp:write_u32(data,a);sp:write_u32(data,0)
        sp:write_u32(addr,64);sp:write_u32(data,b)
        sp:write_u32(addr,128);sp:write_u32(data,0xdeadbeef)
        local code={0x1c00,0x1d00,0x1e00,sticky and 0x70000 or 0x60000,0x3501}
        if x then
            sp:write_u32(addr,64);sp:write_u32(data,x)
            sp:write_u32(addr,192);sp:write_u32(data,y)
            -- X=M1, Y=M3, settle multiplier, P=MUL (low48 bits).
            code={0x1c00,0x1d00,0x1e00,0x1f00,0x60000,0x2100000,0x8c000,0,0x1000000}
        end
        if sticky then
            code[#code+1]=4<<26 -- 7fffffff + 1 sets V
            code[#code+1]=0x60000 -- next M0 is zero, no flag change
            a=0
        end
        code[#code+1]=(op<<26)|0x40000 -- latch result in A before later observations
        code[#code+1]=0x3209;code[#code+1]=0x320a;code[#code+1]=0xf0000000
        sp:write_u32(control,0x8000)
        for _,word in ipairs(code) do sp:write_u32(program,word) end
        sp:write_u32(control,0x18000)
        emu.wait(emu.attotime.from_usec(10)) -- never poll PPAF: it clears V
        local flags=sp:read_u32(control)
        check('finished'..case,flags&0x810000,0)
        local result,carry,overflow,negative
        if op==8 then
            result=(a>>1)|(a&0x80000000);carry=(a&1)~=0;overflow=false
            negative=(result&0x80000000)~=0
        elseif op==6 then
            local left=signed(a);if left<0 then left=left+0x1000000000000 end
            local product=x and signed(x)*signed(y) or signed(b)
            local right=product&0xffffffffffff
            local wide=left+right
            result=wide&0xffffffffffff;carry=wide>0xffffffffffff
            negative=(result&0x800000000000)~=0
            local sum=signed(a)+product
            overflow=sum < -0x800000000000 or sum>0x7fffffffffff
        else
            local wide=op==4 and (a+b) or (a-b)
            local math=op==4 and (signed(a)+signed(b)) or (signed(a)-signed(b))
            result=wide&0xffffffff;carry=op==4 and wide>0xffffffff or op==5 and wide<0
            overflow=math < -0x80000000 or math>0x7fffffff
            negative=(result&0x80000000)~=0
        end
        local expected=(carry and 0x100000 or 0)|(negative and 0x400000 or 0)|
            (result==0 and 0x200000 or 0)|((overflow or sticky) and 0x80000 or 0)
        check('flags'..case,flags&0x780000,expected)
        check('read_clear'..case,sp:read_u32(control)&0x780000,expected&~0x80000)
        sp:write_u32(addr,128);check('result'..case,sp:read_u32(data),result&0xffffffff)
        if op==6 then check('result48'..case,sp:read_u32(data),(result>>16)&0xffffffff) end
        if #fails==before then print(string.format('DSP_ALU case=%d PASS',case)) end
    end
    for _,op in ipairs({4,5,6}) do for _,a in ipairs(values) do for _,b in ipairs(values) do
        run(op,a,b,false)
    end end end
    for _,a in ipairs(values) do run(8,a,0,false) end
    for _,op in ipairs({4,5,6}) do run(op,0x7fffffff,1,true) end
    for _,a in ipairs({0,0xffff,0x10000,0xffffffff}) do run(6,a,0,false,0x7fffffff,0x10000) end
    for _,a in ipairs({0,1,0xffffffff,0xffff0000}) do run(6,a,0,false,0x80000000,0x10000) end
end
local frames=0
emu.register_frame_done(function()
    frames=frames+1
    if frames==180 then coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then fails[#fails+1]=tostring(err) end
        if #fails==0 then print('DSP_ALU PASS cases=211')
        else for _,f in ipairs(fails) do print('DSP_ALU FAIL '..f) end end
        m:exit()
    end)() end
end)
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_ALU FAIL' in text or 'LUA ERROR' in text or
            [int(n) for n in re.findall(r'^DSP_ALU case=(\d+) PASS$',text,re.M)]!=list(range(1,212)) or
            len(re.findall(r'^DSP_ALU PASS cases=211$',text,re.M))!=1):
        raise RuntimeError('DSP arithmetic fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP ALU: 211 arithmetic/flag/read-clear programs passed live')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Public-port RX write-path/product probes; no private state or cycle oracle."""
import re
import test_smpc_save_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local done,frames=false,0
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local function signed(v,bits)
    local sign=1<<(bits-1);v=v&((1<<bits)-1)
    return v>=sign and v-(1<<bits) or v
end
local function run_all()
    park();local case=0
    local values={0,1,2,0x7fffffff,0x80000000,0xffffffff,0x12345678,0x87654321}
    for mode=0,7 do for index,a in ipairs(values) do
        case=case+1;local start=#fails
        local b=index%2==0 and 0x10000 or 0xfffffffd
        sp:write_u32(control,0x8000)
        for _,pair in ipairs({{0,a},{64,7},{128,0xbad},{129,0xbad},{130,0xbad},{131,0xbad},{192,b}}) do
            sp:write_u32(addr,pair[1]);sp:write_u32(data,pair[2])
        end
        local opcode,expected=0x2000000,signed(a,32) -- X-bus control
        if mode==1 then opcode=0x3400 -- D1 memory to RX
        elseif mode==2 then opcode=0x1400|(a&0xff);expected=signed(a,8)
        elseif mode==3 then opcode=0x90000000|(a&0x1ffffff);expected=signed(a,25)
        elseif mode==4 or mode==5 then opcode=0x93080000|(a&0x7ffff);expected=mode==5 and 7 or signed(a,19)
        elseif mode==6 then opcode=0x2103400 -- X=M1 and D1 RX=M0: D1 wins
        elseif mode==7 then opcode=0x1003400 -- old MUL to P while D1 updates RX
        end
        local code={0x1c00,0x1d00,0x1e00,0x1f00,0x2100000,0x8c000,0,
            0x20000,mode==5 and 0x1501 or 0x1500,3<<26,0x1000000,opcode,
            6<<26,0x3209,0x320a,0,0x1000000,6<<26,0x3209,0x320a,0xf0000000}
        for _,word in ipairs(code) do sp:write_u32(program,word) end
        sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(10))
        check('halt'..case,sp:read_u32(control)&0x10000,0)
        sp:write_u32(addr,128)
        for product,value in ipairs({7*signed(b,32),expected*signed(b,32)}) do
            value=value&0xffffffffffff
            check('product'..product..'_low'..case,sp:read_u32(data),value&0xffffffff)
            check('product'..product..'_shift16'..case,sp:read_u32(data),(value>>16)&0xffffffff)
        end
        if #fails==start then print(string.format('DSP_MUL case=%d PASS',case)) end
    end end
    if #fails==0 then print('DSP_MUL PASS cases=64')
    else for _,f in ipairs(fails) do print('DSP_MUL FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if done or frames<180 then return end;done=true
    coroutine.wrap(function()
        local ok,err=pcall(run_all)
        if not ok then print('DSP_MUL FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_MUL armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_MUL FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_MUL case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,65)] or
            len(re.findall(r'^DSP_MUL PASS cases=64$',text,re.M))!=1):
        raise RuntimeError('DSP multiplier fixture failed:\n'+text[-14000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP multiplier: 64 RX write-path/product programs passed live')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped count-source aliases and MC1 fetch increment/wrap, no private writes.

ST-097 pp.135–136 selects count source with bits0–2. Bit3 is unused.
A following MOV probes the counter RAM cursor independently of DMA length.
"""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local base,dest=0x06010000,0x05e40000
    local function run(words)
        sp:write_u32(control,0x8000)
        for _,op in ipairs(words) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000)
        for n=1,1000 do
            emu.wait(emu.attotime.from_usec(10))
            if (sp:read_u32(control)&0x810000)==0 then return end
        end
        error('bounded count test DMA wait expired')
    end
    local case=0
    for unused=0,1 do for increment=0,1 do for _,start in ipairs({0,63}) do
        for direction=0,1 do for hold=0,1 do
            case=case+1
            local before=#fails
            local n=3
            run({0x1c00,0x1d00|start,0x1e00,0xf0000000})
            sp:write_u32(addr,0)
            local want={}
            for i=0,63 do want[i]=0xdead0000|i;sp:write_u32(data,want[i]) end
            sp:write_u32(addr,64+start);sp:write_u32(data,3)
            sp:write_u32(addr,64+((start+1)&63));sp:write_u32(data,7)
            sp:write_u32(addr,128);sp:write_u32(data,0xbad)
            for i=0,511 do
                sp:write_u32(base+i*4,0xab000000|i)
                sp:write_u32(dest+i*4,0x76543210)
            end
            local size=0x2001|(increment<<2)|(unused<<3)
            local stride=direction==0 and 2 or 1
            local op=0xc0000000|(stride<<15)|(hold<<14)|(direction<<12)|size
            local set_address=direction==0 and (0x98000000|(base>>2)) or (0x9c000000|(dest>>2))
            run({set_address,op,0x3201,0xf0000000})
            sp:write_u32(addr,128)
            check("source_cursor"..case,sp:read_u32(data),increment==1 and 7 or 3)
            local wrong=0
            if direction==0 then
                for i=0,n-1 do want[i&63]=0xab000000|i end
                sp:write_u32(addr,0)
                for i=0,63 do if sp:read_u32(data)~=want[i] then wrong=wrong+1 end end
            else
                for i=0,511 do
                    local expected=i<n and (0xdead0000|(i&63)) or 0x76543210
                    if sp:read_u32(dest+i*4)~=expected then wrong=wrong+1 end
                end
            end
            check('count_case'..case,wrong,0)
            if #fails==before then print(string.format('DSP_OPERAND case=%d PASS',case)) end
        end end
    end end end
end
emu.register_frame_done(function()
    if frame==nil then frame=0 end;frame=frame+1
    if frame==180 then coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then fails[#fails+1]=tostring(err) end
        if #fails==0 then print('DSP_OPERAND PASS cases=32')
        else for _,f in ipairs(fails) do print('DSP_OPERAND FAIL '..f) end end
        m:exit()
    end)() end
end)
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_OPERAND FAIL' in text or 'LUA ERROR' in text or
            [int(n) for n in re.findall(r'^DSP_OPERAND case=(\d+) PASS$',text,re.M)]!=list(range(1,33)) or
            len(re.findall(r'^DSP_OPERAND PASS cases=32$',text,re.M))!=1):
        raise RuntimeError('DSP count operand fixture failed:\n'+text[-10000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP count operand: 32 source-alias/increment/wrap programs passed live')

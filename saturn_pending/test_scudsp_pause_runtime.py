#!/usr/bin/env python3
# license:BSD-3-Clause
"""Pause/resume public-port loops and independent active-DMA stall ownership."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local function command(width,pause)
    if width==0 then sp:write_u32(control,pause and 0x02010000 or 0x04000000)
    else sp:write_u8(control,pause and 2 or 4) end
end
local function snapshot()
    assert((sp:read_u32(control)&0x810000)==0,'unsafe active DSP RAM observation')
    sp:write_u32(addr,0);local image,filled={},0
    for i=0,63 do image[i]=sp:read_u32(data);if image[i]==1 then filled=filled+1 end end
    return image,filled
end
local function pause_checked(width,label)
    command(width,true);emu.wait(emu.attotime.from_usec(1))
    local status=sp:read_u32(control);check(label,status&0x10000,0)
    if (status&0x10000)~=0 then
        -- A failing old emulator must be stopped before any DSP RAM read.
        sp:write_u32(control,0);emu.wait(emu.attotime.from_usec(1))
    end
end
local function test()
    park();local case=0
    for width=0,1 do for _,start in ipairs({0,252}) do
        case=case+1;local before=#fails
        sp:write_u32(control,0x8000);sp:write_u32(addr,0)
        for i=0,63 do sp:write_u32(data,0) end
        for _,op in ipairs({0x1c00,0xf0000000}) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(2))
        sp:write_u32(control,0x8000|start)
        for _,op in ipairs({0x1001,0xd0000000|start,0}) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000|start);emu.wait(emu.attotime.from_usec(2))
        pause_checked(width,'pause'..case)
        local first,filled=snapshot();check('initial_progress'..case,filled>0 and filled<64 and 1 or 0,1)
        local pc=sp:read_u32(control)&255
        emu.wait(emu.attotime.from_usec(5));local still=snapshot()
        check('pc_frozen'..case,sp:read_u32(control)&255,pc)
        for i=0,63 do check('frozen'..case..'_'..i,still[i],first[i]) end
        command(width,false);emu.wait(emu.attotime.from_usec(2))
        pause_checked(width,'repause'..case);local later,more=snapshot()
        check('resumed_progress'..case,more>filled and more<64 and 1 or 0,1)
        sp:write_u32(control,0);emu.wait(emu.attotime.from_usec(1))
        if #fails==before then print('DSP_PAUSE case='..case..' PASS') end
    end end
    for width=0,1 do
        case=case+1;local before=#fails;local base=0x06080000
        sp:write_u32(control,0x8000);sp:write_u32(addr,0)
        for i=0,63 do sp:write_u32(data,0xa1230000|i) end
        sp:write_u32(addr,192);sp:write_u32(data,0xdeadbeef)
        for i=0,128 do sp:write_u32(base+i*4,0xdeadbeef) end
        for _,op in ipairs({0x1c00,0x1f00,0x9c000000|(base>>2),0xc0009000,0x1334,0xf8000000}) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(2))
        command(width,true);emu.wait(emu.attotime.from_nsec(100))
        check('paused_dma_busy'..case,sp:read_u32(control)&0x810000,0x800000)
        emu.wait(emu.attotime.from_usec(30))
        check('dma_done_still_paused'..case,sp:read_u32(control)&0x850000,0)
        -- Old ignored-pause execution has ended by this point; no active port read.
        assert((sp:read_u32(control)&0x810000)==0,'DMA completion timeout')
        sp:write_u32(addr,192);check('no_post_dma_instruction'..case,sp:read_u32(data),0xdeadbeef)
        for i=0,127 do check('dma_image'..case..'_'..i,sp:read_u32(base+i*4),0xa1230000|((2*i+1)%64)) end
        check('dma_guard'..case,sp:read_u32(base+512),0xdeadbeef)
        command(width,false);emu.wait(emu.attotime.from_usec(2))
        check('resumed_endi'..case,sp:read_u32(control)&0x850000,0x40000)
        sp:write_u32(addr,192);check('post_dma_instruction'..case,sp:read_u32(data),0x34)
        if #fails==before then print('DSP_PAUSE case='..case..' PASS') end
    end
    if #fails==0 then print('DSP_PAUSE PASS cases=6')
    else for _,f in ipairs(fails) do print('DSP_PAUSE FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_PAUSE FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_PAUSE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_PAUSE FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^DSP_PAUSE case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,7)] or
        len(re.findall(r'^DSP_PAUSE PASS cases=6$',text,re.M))!=1):
        raise RuntimeError('DSP pause fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP pause: six loop/command-width/active-DMA cases passed live')

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
    -- LE acceptance uses state before the write, including load-and-start.
    for _,start in ipairs({0,252}) do
        for width=0,1 do
            case=case+1;local before=#fails
            sp:write_u32(control,0);emu.wait(emu.attotime.from_usec(1))
            sp:write_u32(control,0x8000|start)
            sp:write_u32(program,0xd0000000|start);sp:write_u32(program,0)
            sp:write_u32(control,0x18000|start);emu.wait(emu.attotime.from_usec(2))
            local pc=sp:read_u32(control)&255
            if width==0 then sp:write_u32(control,0x18040) else sp:write_u16(control+2,0x8040) end
            check('active_load_ignored'..case,sp:read_u32(control)&0x100ff,0x10000|pc)
            sp:write_u32(control,0);emu.wait(emu.attotime.from_usec(1))
            if #fails==before then print('DSP_PAUSE case='..case..' PASS') end
        end
        for width=0,1 do
            case=case+1;local before=#fails
            sp:write_u32(addr,192);sp:write_u32(data,0xdeadbeef)
            sp:write_u32(control,0x8040)
            for _,op in ipairs({0x1f00,0x8c000034,0xf0000000}) do sp:write_u32(program,op) end
            sp:write_u32(control,0x8000|start)
            if width==0 then sp:write_u32(control,0x18040)
            else sp:write_u16(control+2,0x8040);sp:write_u32(control,0x10000) end
            emu.wait(emu.attotime.from_usec(2))
            assert((sp:read_u32(control)&0x10000)==0,'stopped load control did not end')
            sp:write_u32(addr,192);check('stopped_load'..case,sp:read_u32(data),0x34)
            if #fails==before then print('DSP_PAUSE case='..case..' PASS') end
        end
        for width=0,2 do
            case=case+1;local before=#fails
            sp:write_u32(control,0x8000)
            for _,op in ipairs({0x1f00,0xf0000000}) do sp:write_u32(program,op) end
            sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(2))
            assert((sp:read_u32(control)&0x10000)==0,'counter setup did not end')
            sp:write_u32(addr,192);sp:write_u32(data,0xdeadbeef);sp:write_u32(data,0xdeadbeef)
            sp:write_u32(control,0x8000|start)
            local code=start==0 and {0xd0000040,0x8c000012} or {0,0,0,0xd0000040,0x8c000012}
            for _,op in ipairs(code) do sp:write_u32(program,op) end
            for _,target in ipairs({64,80}) do
                sp:write_u32(control,0x8000|target)
                sp:write_u32(program,target==64 and 0x8c000034 or 0x8c000056);sp:write_u32(program,0xf0000000)
            end
            sp:write_u32(control,0x18000|start)
            local pending=false
            for n=1,100 do
                emu.wait(emu.attotime.from_nsec(20))
                if (sp:read_u32(control)&0x100ff)==0x10041 then
                    sp:write_u32(control,0x02010000);emu.wait(emu.attotime.from_nsec(0))
                    assert((sp:read_u32(control)&0x10000)==0,'branch pause failed')
                    sp:write_u32(addr,192);pending=sp:read_u32(data)==0xdeadbeef;break
                end
            end
            assert(pending,'did not capture pre-slot branch for LE')
            if width==0 then sp:write_u32(control,0x18050)
            elseif width==1 then sp:write_u16(control+2,0x8050)
            else sp:write_u8(control+2,0x80) end
            sp:write_u32(control,0x04000000);emu.wait(emu.attotime.from_usec(2))
            assert((sp:read_u32(control)&0x10000)==0,'loaded paused branch did not end')
            sp:write_u32(addr,192)
            check('loaded_entry_no_old_slot'..case,sp:read_u32(data),width==2 and 0x34 or 0x56)
            check('loaded_entry_guard'..case,sp:read_u32(data),0xdeadbeef)
            if #fails==before then print('DSP_PAUSE case='..case..' PASS') end
        end
    end
    if #fails==0 then print('DSP_PAUSE PASS cases=20')
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
        re.findall(r'^DSP_PAUSE case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,21)] or
        len(re.findall(r'^DSP_PAUSE PASS cases=20$',text,re.M))!=1):
        raise RuntimeError('DSP pause fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP pause: 20 pause/DMA/stopped-load/pending-slot cases passed live')

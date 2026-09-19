#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped DSP jump/MVI/loop programs exercise wrapped and nonwrapped slots.

No DSP register/debug-state mutation: setup uses SCU host ports and guest ALU
instructions. S/Z are read-only; never inject them through PPAF writes.
"""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA

runner.LUA=COMMON_LUA+r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local function writecode(pc,words)
        sp:write_u32(control,0x8000|pc)
        for _,op in ipairs(words) do sp:write_u32(program,op) end
    end
    local function run(pc)
        sp:write_u32(control,0x18000|pc)
        for n=1,100 do
            emu.wait(emu.attotime.from_usec(10))
            if (sp:read_u32(control)&0x10000)==0 then return end
        end
        error('DSP program did not end')
    end
    local case=0
    for _,pc in ipairs({0x7f,0xff}) do
        for kind=1,6 do
            case=case+1
            local before=#fails
            sp:write_u32(addr,0)
            for i=1,4 do sp:write_u32(data,0xdeadbeef) end
            sp:write_u32(addr,64);sp:write_u32(data,0xdeadbeef)
            -- Initialize counters and produce Z through actual ALU execution,
            -- then jump to the instruction under test with an inert slot.
            writecode(16,{0x1c00,0x1d00,0x1a02,0x1b04,0x20000,
                0x94000000|(kind==2 and 0 or 1),0x10000000,0xd0000000|pc,0})
            writecode((pc+1)&255,{0x1012,0xf0000000}) -- slot writes MC0, then END
            writecode(4,{0x1134,0xf0000000})
            local ops={0xd0000004,0xd1080004,0xd1080004,0xb0000004,0xe0000000,0xe8000000}
            writecode(pc,{ops[kind]})
            run(16)
            sp:write_u32(addr,0)
            local count=kind==6 and 3 or 1
            for i=1,4 do
                check('case'..case..'_word'..i,sp:read_u32(data),i<=count and 0x12 or 0xdeadbeef)
            end
            sp:write_u32(addr,64)
            check('branch_target'..case,sp:read_u32(data),(kind==3 or kind==6) and 0xdeadbeef or 0x34)
            if #fails==before then print('DSP_PIPELINE case='..case..' PASS') end
        end
    end
    for _,pc in ipairs({0x20,0xfe,0xff}) do for kind=1,5 do
        case=case+1;local before=#fails;local slot=(pc+1)&255
        sp:write_u32(addr,192);sp:write_u32(data,0xdeadbeef);sp:write_u32(data,0xdeadbeef)
        writecode(128,{0x1f00,0x20000,0x94000000|(kind==3 and 1 or 0),0x0c000000,
            0x1a01,0x1b00|slot,0xd0000000|pc,0})
        local ops={0xd0000000|slot,0xd1080000|slot,0xd0080000|slot,0xb0000000|slot,0xe0000000}
        writecode(pc,{ops[kind]});writecode(slot,{0x8c000012,0xf0000000})
        sp:write_u32(control,0x18080)
        local pending=false
        for n=1,100 do
            emu.wait(emu.attotime.from_nsec(20))
            -- Current core's PC+1 is a phase selector, not a hardware timing assertion.
            if (sp:read_u32(control)&0x100ff)==(0x10000|((slot+1)&255)) then
                sp:write_u32(control,0x02010000);emu.wait(emu.attotime.from_nsec(0))
                assert((sp:read_u32(control)&0x10000)==0,'slot latch pause failed')
                sp:write_u32(addr,192);pending=sp:read_u32(data)==0xdeadbeef;break
            end
        end
        assert(pending,'did not capture pending slot for program-RAM replacement')
        -- No LE: it would intentionally invalidate the slot. PC is already at slot.
        -- This legal paused program-port write changes RAM and increments PC.
        sp:write_u32(program,0x8c000034)
        sp:write_u32(control,0x04000000);emu.wait(emu.attotime.from_usec(2))
        assert((sp:read_u32(control)&0x10000)==0,'replaced-slot program did not end')
        sp:write_u32(addr,192)
        check('latched_slot'..case,sp:read_u32(data),0x12)
        check('latched_slot_guard'..case,sp:read_u32(data),0xdeadbeef)
        if #fails==before then print('DSP_PIPELINE case='..case..' PASS') end
    end end
    if #fails==0 then print('DSP_PIPELINE PASS cases=27')
    else for _,f in ipairs(fails) do print('DSP_PIPELINE FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_PIPELINE FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('DSP_PIPELINE armed')
'''

def validate_output(text,returncode):
    if (returncode or 'DSP_PIPELINE FAIL' in text or 'LUA ERROR' in text or
            [int(n) for n in re.findall(r'^DSP_PIPELINE case=(\d+) PASS$',text,re.M)]!=list(range(1,28)) or
            len(re.findall(r'^DSP_PIPELINE PASS cases=27$',text,re.M))!=1):
        raise RuntimeError('DSP pipeline fixture failed:\n'+text[-10000:])

runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP pipeline: 27 wrapped/control-flow/fetched-slot programs passed live')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Scheduled file replay at a wrapped DSP branch's pending address-00 slot.

Only mapped host ports are used. Public PC plus a RAM marker distinguishes the
pending slot from its completed state. JP/interpreter timing fixture, not a
hardware-prefetch timing measurement or private DSP-state injection.
"""
import re
import test_smpc_save_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local phase,frames,saved,loaded='setup',0,false,false
local subscribers={}
local state_path=assert(os.getenv('SMPC_SAVE_FILE'))
local save_clock=0
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('DSP_SLOT_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('DSP_SLOT_SAVE loaded')
end)
local function marker()
    sp:write_u32(addr,192);return sp:read_u32(data)
end
local function writecode(pc,words)
    sp:write_u32(control,0x8000|pc)
    for _,op in ipairs(words) do sp:write_u32(program,op) end
end
local function advance(label)
    emu.unpause()
    -- More than one and less than two DSP clocks in either JP dot-clock mode.
    -- The marker cannot be cleared again for at least five instructions.
    emu.wait(emu.attotime.from_nsec(90))
    check(label,marker(),0x12)
end
local function finish()
    if #fails==0 then print('DSP_SLOT_SAVE PASS wrapped=1 pending=1 replay=exact')
    else for _,f in ipairs(fails) do print('DSP_SLOT_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('DSP_SLOT_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('DSP_SLOT_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park()
        writecode(0xfc,{0x1f00,0x8c000000,0x1f00,0xd0000003})
        writecode(0,{0x8c000012})
        writecode(3,{0xd00000fc,0})
        sp:write_u32(control,0x180fc)
        local pending=false
        for n=1,500 do
            emu.wait(emu.attotime.from_nsec(90))
            -- Current core reports post-fetch PC+1 at the public port.
            if (sp:read_u32(control)&0x100ff)==0x10004 and marker()==0 then pending=true;break end
        end
        assert(pending,'did not observe wrapped pending slot through host ports')
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced time')
        advance('original_slot')
        -- Reset clears the pending flag and changes PC; poison the marker too.
        sp:write_u32(control,0x8040)
        emu.wait(emu.attotime.from_usec(1))
        sp:write_u32(addr,192);sp:write_u32(data,0x777)
        print('DSP_SLOT_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        check('restored_pc',sp:read_u32(control)&0x100ff,0x10004)
        check('restored_marker',marker(),0)
        advance('replayed_slot');finish()
    end)
    end
end)
print('DSP_SLOT_SAVE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_SLOT_SAVE FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_SLOT_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
            len(re.findall(r'^DSP_SLOT_SAVE PASS wrapped=1 pending=1 replay=exact$',text,re.M))!=1):
        raise RuntimeError('DSP pending-slot save fixture failed:\n'+text[-10000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP pending slot save: wrapped slot restored and executed exactly')

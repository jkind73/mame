#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real scheduled save/load during DSP DMA, using mapped SCU ports only.

A long RAM-count DMA leaves time to capture the timer while busy. Complete it,
poison the descriptor with a different transfer, load, and verify the saved DMA
finishes the original memory image. No hardware timing claim follows.
"""
import re
import test_smpc_save_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA

runner.LUA = COMMON_LUA + r'''
local phase,frames,saved,loaded='setup',0,false,false
local subscribers={}
local state_path=assert(os.getenv('SMPC_SAVE_FILE'))
local save_clock=0
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local base,count=0x05c40000,60000
local function pattern(i) return (0xa1230000|((i%64)*0x103)) end
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('DSP_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('DSP_SAVE loaded')
end)
local function upload(code)
    sp:write_u32(control,0x8000)
    for _,op in ipairs(code) do sp:write_u32(program,op) end
    sp:write_u32(control,0x18000)
end
local function complete()
    for n=1,200 do
        emu.wait(emu.attotime.from_usec(100))
        if (sp:read_u32(control)&0x810000)==0 then return end
    end
    error('DMA did not complete')
end
local function image(label)
    local mismatches=0
    for i=0,count-1 do
        if sp:read_u32(base+i*4)~=pattern(i) then mismatches=mismatches+1 end
    end
    check(label,mismatches,0)
end
local function finish()
    if #fails==0 then print('DSP_SAVE PASS words=60000 busy=1 replay=exact')
    else for _,f in ipairs(fails) do print('DSP_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('DSP_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('DSP_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park()
        for i=0,count-1 do sp:write_u32(base+i*4,0xdeadbeef) end
        sp:write_u32(addr,0)
        for i=0,63 do sp:write_u32(data,pattern(i)) end
        sp:write_u32(addr,64);sp:write_u32(data,count)
        -- CT0=CT1=0, WA0=base/4, DMA1 MC0,D0,M1, END.
        upload({0x1c00,0x1d00,0x9c000000|(base>>2),0xc000b001,0xf0000000})
        emu.wait(emu.attotime.from_usec(2))
        check('busy_before_save',sp:read_u32(control)&0x810000,0x810000)
        check('tail_not_yet_written',sp:read_u32(base+(count-1)*4),0xdeadbeef)
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced time')
        emu.unpause();complete();image('original_completion')
        -- A read-direction HOLD transfer poisons direction/count/stride/update.
        sp:write_u32(0x06010000,0x55667788)
        upload({0x1c00,0x98000000|(0x06010000>>2),0xc0014001,0xf0000000})
        complete()
        for i=0,count-1 do sp:write_u32(base+i*4,0xfeedface) end
        print('DSP_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        check('busy_restored',sp:read_u32(control)&0x810000,0x810000)
        check('saved_tail_restored',sp:read_u32(base+(count-1)*4),0xdeadbeef)
        emu.unpause();complete();image('replayed_completion');finish()
    end)
    end
end)
print('DSP_SAVE armed')
'''

def validate_output(text, returncode):
    if (returncode or 'DSP_SAVE FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
            len(re.findall(r'^DSP_SAVE PASS words=60000 busy=1 replay=exact$',text,re.M))!=1):
        raise RuntimeError('DSP save fixture failed:\n'+text[-10000:])

runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP save: busy transfer restored and 60000-word replay verified')

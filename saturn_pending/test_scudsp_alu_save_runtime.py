#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real file replay of a 48-bit ALU result and latched/read-cleared overflow."""
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
    saved=true;save_clock=emu.time();print('DSP_ALU_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('DSP_ALU_SAVE loaded')
end)
local function put(address,value) sp:write_u32(addr,address);sp:write_u32(data,value) end
local function upload(code)
    sp:write_u32(control,0x8000)
    for _,op in ipairs(code) do sp:write_u32(program,op) end
    sp:write_u32(control,0x18000)
    emu.wait(emu.attotime.from_usec(10)) -- do not poll away V
end
local function image(label,low,high)
    sp:write_u32(addr,128)
    check(label..'_low',sp:read_u32(data),low)
    check(label..'_shift16',sp:read_u32(data),high)
end
local function overflow(label)
    check(label,sp:read_u32(control)&0xf90000,0x480000)
    check(label..'_read_clear',sp:read_u32(control)&0xf90000,0x400000)
end
local function finish()
    if #fails==0 then print('DSP_ALU_SAVE PASS width=48 overflow=1 replay=exact')
    else for _,f in ipairs(fails) do print('DSP_ALU_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('DSP_ALU_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('DSP_ALU_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park();sp:read_u32(control)
        put(0,0x10000);put(64,0x7fffffff);put(192,0x10000)
        -- (7fffffff * 10000) + 10000 = 800000000000: signed48 overflow.
        upload({0x1c00,0x1d00,0x1e00,0x1f00,0x60000,0x2100000,0x8c000,0,
                0x1000000,6<<26,0x3209,0x320a,0xf0000000})
        image('original_image',0,0x80000000)
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced time')
        overflow('original_flags')
        emu.unpause();put(0,1);put(64,1)
        upload({0x1c00,0x1d00,0x1e00,0x60000,0x3501,4<<26,0x3209,0x320a,0xf0000000})
        image('poisoned_image',2,0x80000000)
        check('poisoned_v',sp:read_u32(control)&0x80000,0)
        print('DSP_ALU_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        overflow('restored_flags');image('restored_image',0,0x80000000)
        -- Poison only the output RAM, then observe restored ALU through MOVs.
        put(128,0xbad);put(129,0xbad)
        emu.unpause();upload({0x1e00,0x3209,0x320a,0xf0000000})
        image('restored_alu',0,0x80000000);finish()
    end)
    end
end)
print('DSP_ALU_SAVE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_ALU_SAVE FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_ALU_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
            len(re.findall(r'^DSP_ALU_SAVE PASS width=48 overflow=1 replay=exact$',text,re.M))!=1):
        raise RuntimeError('DSP arithmetic save fixture failed:\n'+text[-10000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP ALU save: 48-bit result and latched overflow restored through real file replay')

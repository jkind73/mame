#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real scheduled file replay of an active12-bit LPS loop and its output ring."""
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
    saved=true;save_clock=emu.time();print('DSP_LOP_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('DSP_LOP_SAVE loaded')
end)
local function fill()
    sp:write_u32(addr,128);for i=1,64 do sp:write_u32(data,0xdeadbeef) end
end
local function upload(code)
    sp:write_u32(control,0x8000)
    for _,op in ipairs(code) do sp:write_u32(program,op) end
    sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(10))
end
local function complete(label)
    emu.wait(emu.attotime.from_msec(30))
    check(label..'_halt',sp:read_u32(control)&0x10000,0)
    sp:write_u32(addr,128)
    for i=1,64 do check(label..'_word'..i,sp:read_u32(data),4032+i) end
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('DSP_LOP_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1;assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('DSP_LOP_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park();sp:write_u32(control,0x8000);fill()
        -- LOP=ffff must retainfff; LPS emits4096 increments to a64-word ring.
        upload({0x1e00,0x1501,0x20000,0xa800ffff,0xe8000000,0x10043209,0xf0000000})
        local status=sp:read_u32(control)
        check('active_before_save',status&0x10000,0x10000)
        -- ST-097 pp.53-54 forbids data-port access while EX=1. Observe
        -- only the control port: active execution is at the loop, not setup.
        assert((status&0xff)==4,'not an observed in-flight loop')
        print('DSP_LOP_SAVE observed partial loop')
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced time')
        emu.unpause();complete('original')
        fill()
        -- Poison LOP, ALU/AC/PL, program image and output ring.
        upload({0x1e00,0xa8000000,0x20000,0x1500,0x10043209,0xf0000000})
        sp:write_u32(addr,128);check('poisoned_output',sp:read_u32(data),0)
        print('DSP_LOP_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        check('restored_active',sp:read_u32(control)&0x10000,0x10000)
        emu.unpause();complete('restored')
        if #fails==0 then print('DSP_LOP_SAVE PASS iterations=4096 replay=exact')
        else for _,f in ipairs(fails) do print('DSP_LOP_SAVE FAIL '..f) end end
        phase='done';m:exit()
    end)
    end
end)
print('DSP_LOP_SAVE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_LOP_SAVE FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_LOP_SAVE (observed partial loop|saved|mutated|loaded)$',text,re.M)!=['observed partial loop','saved','mutated','loaded'] or
            len(re.findall(r'^DSP_LOP_SAVE observed partial loop$',text,re.M))!=1 or
            len(re.findall(r'^DSP_LOP_SAVE PASS iterations=4096 replay=exact$',text,re.M))!=1):
        raise RuntimeError('DSP loop save fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP loop save: active 4096-iteration loop and 64-word output replay restored')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real file replay at an observed odd transfer in C-bus two-byte-stride DMA.

Only external RAM and the DSP control port are observed while active. This
qualifies the saved address phase and WA0 continuation, not hardware timing.
"""
import re
import test_smpc_save_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA

runner.LUA = COMMON_LUA + r'''
local phase,frames,saved,loaded='setup',0,false,false
local subscribers={}
local state_path=assert(os.getenv('SMPC_SAVE_FILE'))
local save_clock=0
local cut_word,cut_value=-1,0
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local base,count=0x06080000,256
local function pattern(i) return (0xa1230000|((i%64)*0x103)) end
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('DSP_CBUS_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('DSP_CBUS_SAVE loaded')
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
local function odd_phase()
    for attempt=1,100 do
        cut_word=-1
        for i=0,127 do
            local value=sp:read_u32(base+i*4)
            if value==0xdeadbeef then break end
            cut_word=i;cut_value=value
        end
        if cut_word>=0 and (cut_value&1)==0 then return end
        emu.wait(emu.attotime.from_nsec(25))
    end
    error('could not observe an odd transfer phase')
end
local function image(label)
    local mismatches=0
    for i=0,count-1 do
        local expected=i<128 and pattern(2*i+1) or 0xdeadbeef
        if sp:read_u32(base+i*4)~=expected then mismatches=mismatches+1 end
    end
    check(label,mismatches,0)
    upload({0x1e00,0xc0005201,0xf0000000});complete()
    local probe_errors=0
    for i=0,count do
        local expected=i<128 and pattern(2*i+1) or (i==128 and 0xcafebabe or 0xdeadbeef)
        if sp:read_u32(base+i*4)~=expected then probe_errors=probe_errors+1 end
    end
    check(label..'_wa0_probe',probe_errors,0)
end
local function finish()
    if #fails==0 then print('DSP_CBUS_SAVE PASS words=256 busy=1 stride=2 phase=odd replay=exact')
    else for _,f in ipairs(fails) do print('DSP_CBUS_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('DSP_CBUS_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('DSP_CBUS_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park()
        for i=0,count do sp:write_u32(base+i*4,0xdeadbeef) end
        sp:write_u32(addr,0)
        for i=0,63 do sp:write_u32(data,pattern(i)) end
        sp:write_u32(addr,64);sp:write_u32(data,count&255)
        sp:write_u32(addr,128);sp:write_u32(data,0xcafebabe)
        -- CT0=CT1=0, WA0=base/4, DMA1 MC0,D0,M1, END.
        upload({0x1c00,0x1d00,0x9c000000|(base>>2),0xc000b001,0xf0000000})
        emu.wait(emu.attotime.from_usec(2));odd_phase()
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
        for i=0,count do sp:write_u32(base+i*4,0xfeedface) end
        print('DSP_CBUS_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        check('saved_phase_word',sp:read_u32(base+cut_word*4),cut_value)
        check('saved_phase_parity',cut_value&1,0)
        check('busy_restored',sp:read_u32(control)&0x810000,0x810000)
        check('saved_tail_restored',sp:read_u32(base+(count-1)*4),0xdeadbeef)
        emu.unpause();complete();image('replayed_completion');finish()
    end)
    end
end)
print('DSP_CBUS_SAVE armed')
'''

def validate_output(text, returncode):
    if (returncode or 'DSP_CBUS_SAVE FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_CBUS_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
            len(re.findall(r'^DSP_CBUS_SAVE PASS words=256 busy=1 stride=2 phase=odd replay=exact$',text,re.M))!=1):
        raise RuntimeError('DSP save fixture failed:\n'+text[-10000:])

runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP C-bus save: odd-phase cursor and WA0 replay verified')

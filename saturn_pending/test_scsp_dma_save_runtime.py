#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real-file replay of SCSP DMA parameters after forbidden self-target writes."""
import re
import test_smpc_save_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local phase,frames,saved,loaded='setup',0,false,false
local subscribers={};local save_clock=0
local state_path=assert(os.getenv('SMPC_SAVE_FILE'))
local base=0x05b00000
local baseline,original
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('SCSP_DMA_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('SCSP_DMA_SAVE loaded')
end)
local function image()
    return {sp:read_u16(base+0x418)&0x700,sp:read_u16(0x05a08006),sp:read_u16(base+0x700),sp:read_u16(base+0x416)&0x1000}
end
local function transfer(label)
    sp:write_u16(0x05a08006,0x100)
    sp:write_u16(base+0x416,0x1008)
    local now=image()
    check(label..'_cached_parameters',now[1],0x100)
    check(label..'_untouched_coefficient',now[3],0x7ff8)
    check(label..'_completed',now[4],0)
    return now
end
local function step(fn)
    phase='busy';coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('SCSP_DMA_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1;assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then print('SCSP_DMA_SAVE FAIL bounded wait expired');phase='done';emu.unpause();m:exit();return end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park();local snd=assert(m.devices[':audiocpu']);local ss=snd.spaces['program']
        ss:write_u16(0x70000,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
        sp:write_u16(base+0x41e,0);sp:write_u16(base+0x42a,0)
        sp:write_u16(base+0x700,0x7ff8)
        for i=0,3 do sp:write_u16(0x05a09000+i*2,0);sp:write_u16(0x05a09100+i*2,0) end
        sp:write_u16(0x05a08000,0x9000);sp:write_u16(0x05a08002,0x700)
        sp:write_u16(0x05a08004,0);sp:write_u16(0x05a08006,0x300)
        -- Non-executing payload: safe even when used as an old-core control.
        sp:write_u16(base+0x412,0x8000);sp:write_u16(base+0x414,0x412);sp:write_u16(base+0x416,0x1008)
        check('initial_following_register',image()[1],0x300)
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save advanced time')
        baseline=image();original=transfer('original')
        sp:write_u16(base+0x412,0x9100);sp:write_u16(base+0x414,0x780);sp:write_u16(base+0x416,0x1002)
        sp:write_u16(base+0x418,0x700);sp:write_u16(base+0x700,0);sp:write_u16(0x05a08006,0x700)
        local now=image();check('poisoned_control',now[1],0x700);check('poisoned_coefficient',now[3],0)
        print('SCSP_DMA_SAVE mutated');m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        local now=image();for i=1,4 do check('restored_state'..i,now[i],baseline[i]) end
        local replay=transfer('replayed');for i=1,4 do check('exact_replay'..i,replay[i],original[i]) end
        if #fails==0 then print('SCSP_DMA_SAVE PASS parameters=restored transfer=independent replay=exact')
        else for _,f in ipairs(fails) do print('SCSP_DMA_SAVE FAIL '..f) end end
        phase='done';emu.unpause();m:exit()
    end)
    end
end)
print('SCSP_DMA_SAVE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_DMA_SAVE FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_DMA_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
        len(re.findall(r'^SCSP_DMA_SAVE PASS parameters=restored transfer=independent replay=exact$',text,re.M))!=1):
        raise RuntimeError('SCSP DMA save fixture failed:\n'+text[-12000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP DMA save: programmed addresses and independent transfer restored through real file replay')

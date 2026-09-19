#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real-file replay of SCSP pending requests and byte acknowledgements."""
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
    saved=true;save_clock=emu.time();print('SCSP_IRQ_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('SCSP_IRQ_SAVE loaded')
end)
local function image()
    return {sp:read_u16(base+0x420)&0x7ff,sp:read_u16(base+0x42c)&0x7ff}
end
local function acknowledge(label)
    local prior=image()
    sp:write_u8(base+0x423,0x10);sp:write_u8(base+0x42f,0x10)
    local now=image()
    for i=1,2 do check(label..'_independent_ack'..i,now[i],prior[i]&~0x10) end
    return now
end
local function step(fn)
    phase='busy';coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('SCSP_IRQ_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1;assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then print('SCSP_IRQ_SAVE FAIL bounded wait expired');phase='done';emu.unpause();m:exit();return end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park();local snd=assert(m.devices[':audiocpu']);local ss=snd.spaces['program']
        ss:write_u16(0x70000,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
        sp:write_u16(base+0x41e,0);sp:write_u16(base+0x42a,0)
        for i=0,2 do sp:write_u16(base+0x418+i*2,0x700) end
        emu.wait(emu.attotime.from_msec(4))
        sp:write_u16(0x05a08000,0)
        sp:write_u16(base+0x412,0x8000);sp:write_u16(base+0x414,0x700);sp:write_u16(base+0x416,0x1002)
        sp:write_u16(base+0x420,0x20);sp:write_u16(base+0x42c,0x20)
        -- Seed an old high-byte command, then re-raise the sample request.
        sp:write_u16(base+0x422,0x400);sp:write_u16(base+0x42e,0x400)
        emu.wait(emu.attotime.from_usec(100))
        local now=image();for i=1,2 do assert((now[i]&0x430)==0x430,'pending source setup failed') end
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save advanced time')
        baseline=image();original=acknowledge('original')
        sp:write_u16(base+0x422,0x7ff);sp:write_u16(base+0x42e,0x7ff)
        local now=image();for i=1,2 do check('poisoned_pending'..i,now[i]&0x30,0) end
        print('SCSP_IRQ_SAVE mutated');m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        local now=image();for i=1,2 do check('restored_pending'..i,now[i],baseline[i]) end
        local replay=acknowledge('replayed');for i=1,2 do check('exact_replay'..i,replay[i],original[i]) end
        if #fails==0 then print('SCSP_IRQ_SAVE PASS pending=restored byte_ack=independent replay=exact')
        else for _,f in ipairs(fails) do print('SCSP_IRQ_SAVE FAIL '..f) end end
        phase='done';emu.unpause();m:exit()
    end)
    end
end)
print('SCSP_IRQ_SAVE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_IRQ_SAVE FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_IRQ_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
        len(re.findall(r'^SCSP_IRQ_SAVE PASS pending=restored byte_ack=independent replay=exact$',text,re.M))!=1):
        raise RuntimeError('SCSP IRQ save fixture failed:\n'+text[-12000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP IRQ save: pending requests and independent byte acknowledgements restored through real file replay')

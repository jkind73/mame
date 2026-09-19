#!/usr/bin/env python3
# license:BSD-3-Clause
"""Scheduled file replay of an active SCSP effect/read pipeline through mapped ports."""
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
    saved=true;save_clock=emu.time();print('SCSP_DSP_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('SCSP_DSP_SAVE loaded')
end)
local function blank()
    local c={};for i=1,512 do c[i]=0 end;return c
end
local function upload(c)
    for i=1,512 do sp:write_u16(base+0x800+(i-1)*2,c[i]) end
    sp:write_u16(base+0xbf0,c[505])
end
local function program(late)
    local c=blank()
    c[2]=0x20;c[3]=2
    c[6]=0xa021;c[7]=2
    c[11]=0xd002;c[12]=0x100
    c[15]=0xa000;c[16]=0x100
    c[18]=0xa040;c[19]=2;c[23]=0x1102
    -- Early read uses the ADRS latch established near the previous sample's end.
    c[31]=0xa000;c[32]=0x10a;c[38]=0x22
    c[487]=0xa000;c[488]=0x10c;c[494]=0x23
    c[503]=0xa000;c[504]=0x100 -- preserve the main ReadValue for next step0
    c[506]=0xc0;c[507]=0x80
    if late then c[511]=0xa000;c[512]=0x104 end
    return c
end
local function scaled(v)return (v*256*4095//4096)//256 end
local function image()
    local e0=sp:read_u16(base+0xec0) -- flush the SCSP stream to this time
    return {sp:read_u16(0x05a08000),e0,sp:read_u16(base+0xec2),
        sp:read_u32(base+0xe00)&0xffffff,sp:read_u32(base+0xe04)&0xffffff,sp:read_u32(base+0xe08)&0xffffff}
end
local function next_sample(label)
    local prior=image();emu.unpause()
    for i=1,100 do
        emu.wait(emu.attotime.from_usec(2))
        local now=image()
        if now[1]~=prior[1] then
            check(label..'_decay',now[1],scaled(prior[1]))
            check(label..'_effect',now[2],now[1])
            check(label..'_late_read_effect',now[3],scaled(0x123))
            check(label..'_main_input',now[4],prior[1]<<8)
            check(label..'_late_input',now[5],0x12300)
            check(label..'_signed_address',now[6],0x123400)
            return now
        end
    end
    error('SCSP sample progress timeout')
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('SCSP_DSP_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1;assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then print('SCSP_DSP_SAVE FAIL bounded wait expired');phase='done';emu.unpause();m:exit();return end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park();local snd=m.devices[':audiocpu']
        if snd then snd.spaces['program']:write_u16(0x100,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x100 end
        sp:write_u16(base+0x400,0);sp:write_u16(base+0x402,0)
        sp:write_u16(base+0x700,0x7ff8);sp:write_u16(base+0x702,0)
        sp:write_u16(base+0x780,0x4000);sp:write_u16(base+0x782,0x4001)
        sp:write_u16(base+0x784,0x5000);sp:write_u16(base+0x786,0x3000)
        sp:write_u16(0x05a06000,0xff00);sp:write_u16(0x05a09ffe,0x1234)
        sp:write_u16(0x05a0a000,0x5678);sp:write_u16(0x05a0bffe,0x9abc)
        local c=blank()
        for i=0,127 do c[i*4+1]=0x80|i;c[i*4+2]=0x2000;c[i*4+3]=2;c[i*4+4]=0x200 end
        upload(c);emu.wait(emu.attotime.from_msec(2))
        sp:write_u16(0x05a08000,0x6000);sp:write_u16(0x05a08002,0x123)
        c=blank();c[2]=0x20;c[7]=0xa000;c[8]=0x100
        upload(c);emu.wait(emu.attotime.from_usec(500))
        upload(program(true));emu.wait(emu.attotime.from_usec(500))
        local now=image();assert(now[1]>0 and now[1]<0x6000,'effect loop not progressing')
        check('initial_late_read',now[3],scaled(0x123))
        check('initial_signed_address',now[6],0x123400)
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save advanced time')
        baseline=image();original=next_sample('original')
        sp:write_u16(base+0x700,0);sp:write_u16(0x05a08002,0x2222)
        sp:write_u16(0x05a06000,0)
        upload(program(false));emu.wait(emu.attotime.from_usec(500))
        check('poisoned_effect',sp:read_u16(base+0xec0),0)
        check('poisoned_late_effect',sp:read_u16(base+0xec2),0)
        check('poisoned_signed_address',sp:read_u32(base+0xe08)&0xffffff,0x567800)
        print('SCSP_DSP_SAVE mutated');m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        local restored=image();for i=1,6 do check('restored_state'..i,restored[i],baseline[i]) end
        local replay=next_sample('replayed');for i=1,6 do check('exact_replay'..i,replay[i],original[i]) end
        if #fails==0 then print('SCSP_DSP_SAVE PASS active=1 late_read=1 signed_address=1 replay=exact')
        else for _,f in ipairs(fails) do print('SCSP_DSP_SAVE FAIL '..f) end end
        phase='done';emu.unpause();m:exit()
    end)
    end
end)
print('SCSP_DSP_SAVE armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_DSP_SAVE FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_DSP_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
        len(re.findall(r'^SCSP_DSP_SAVE PASS active=1 late_read=1 signed_address=1 replay=exact$',text,re.M))!=1):
        raise RuntimeError('SCSP DSP save fixture failed:\n'+text[-12000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP DSP save: active effect and late-read state restored through real file replay')

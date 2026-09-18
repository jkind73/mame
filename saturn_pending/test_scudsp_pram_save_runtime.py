#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real file save/load while a serialized program-RAM DMA is in flight.

SCU host ports perform all writes. The DSP program address space is a read-only
observer, checked against host-port uploads before testing the transfer.
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
local base,target,count=0x06010000,200,192
local prg,expected,captured
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('DSP_PRAM_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('DSP_PRAM_SAVE loaded')
end)
local function writecode(pc,words)
    sp:write_u32(control,0x8000|pc)
    for _,op in ipairs(words) do sp:write_u32(program,op) end
end
local function complete()
    for n=1,100 do
        emu.wait(emu.attotime.from_usec(10))
        if (sp:read_u32(control)&0x810000)==0 then return end
    end
    error('Program DMA did not complete')
end
local function image()
    local bytes={}
    for i=0,255 do bytes[i]=prg:read_u32(i) end
    return bytes
end
local function compare(label,want)
    local n=0
    for i=0,255 do if prg:read_u32(i)~=want[i] then n=n+1 end end
    check(label,n,0)
end
local function finish()
    if #fails==0 then print('DSP_PRAM_SAVE PASS words=192 wrap=1 busy=1 replay=exact')
    else for _,f in ipairs(fails) do print('DSP_PRAM_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('DSP_PRAM_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('DSP_PRAM_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park()
        prg=assert(m.devices[':scu:scudsp']).spaces['program']
        sp:write_u32(control,0x8000)
        for i=0,255 do sp:write_u32(program,0) end
        writecode(32,{0x1c00,0x1d00,0xf0000000})
        sp:write_u32(control,0x18020);complete()
        sp:write_u32(addr,64);sp:write_u32(data,count)
        -- Unique END instructions make completion safe even where the overlay
        -- replaces the TOP return address; low bits identify every copied word.
        for i=0,count-1 do sp:write_u32(base+i*4,0xf0000001+i) end
        local code={0x98000000|(base>>2),0xc0012401,0xb0000000|target,0xf0000000}
        writecode(0,code)
        for i,op in ipairs(code) do check('observer_word'..i,prg:read_u32(i-1),op) end
        assert(#fails==0,'program-space observer disagrees with mapped uploads')
        expected=image()
        for i=0,count-1 do expected[(target+i)&255]=0xf0000001+i end
        sp:write_u32(control,0x18000)
        emu.wait(emu.attotime.from_usec(2))
        check('busy_before_save',sp:read_u32(control)&0x810000,0x810000)
        check('first_word_written',prg:read_u32(target),0xf0000001)
        check('tail_pending',prg:read_u32((target+count-1)&255),0)
        captured=image()
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced time')
        emu.unpause();complete();compare('original_completion',expected)
        -- Poison DMA descriptor and instruction RAM using only mapped ports.
        writecode(0,{0x1c00,0x98000000|(base>>2),0xc0014001,0xf0000000})
        sp:write_u32(control,0x18000);complete()
        sp:write_u32(control,0x8000)
        for i=0,255 do sp:write_u32(program,0xf000dead) end
        print('DSP_PRAM_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore time')
        check('busy_restored',sp:read_u32(control)&0x810000,0x810000)
        compare('instruction_snapshot_restored',captured)
        emu.unpause();complete();compare('replayed_completion',expected);finish()
    end)
    end
end)
print('DSP_PRAM_SAVE armed')
'''

def validate_output(text,returncode):
    if (returncode or 'DSP_PRAM_SAVE FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_PRAM_SAVE (saved|mutated|loaded)$',text,re.M)!=['saved','mutated','loaded'] or
            len(re.findall(r'^DSP_PRAM_SAVE PASS words=192 wrap=1 busy=1 replay=exact$',text,re.M))!=1):
        raise RuntimeError('DSP program-RAM save fixture failed:\n'+text[-10000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP program RAM save: busy wrapped transfer and instruction image restored')

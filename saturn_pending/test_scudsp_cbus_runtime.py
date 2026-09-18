#!/usr/bin/env python3
# license:BSD-3-Clause
"""C-bus writes and subsequent WA0 use, through stopped DSP host ports only."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local function execute(code)
    sp:write_u32(control,0x8000)
    for _,op in ipairs(code) do sp:write_u32(program,op) end
    sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(10))
    assert((sp:read_u32(control)&0x810000)==0,'DMA/program did not finish')
end
local function pattern(i) return 0xa1230000|(i*0x103) end
local function test()
    park()
    -- Mirror-wrap tests overwrite the first RAM page. Park both SH-2s elsewhere.
    sp:write_u32(0x06040000,0xaffe0009)
    for _,tag in ipairs({':maincpu',':slave'}) do m.devices[tag].state['PC'].value=0x06040000 end
    local case=0
    for _,base in ipairs({0x06080000,0x060803fc,0x060ffffc,0x260803fc}) do
    for mode=0,7 do for memory=0,1 do for hold=0,1 do for _,count in ipairs({1,2,3,8}) do
        case=case+1;local before=#fails;local expected={}
        for off=-16,2080,4 do expected[off]=0xdeadbeef;sp:write_u32(base+off,expected[off]) end
        sp:write_u32(control,0x8000);sp:write_u32(addr,0)
        for i=0,63 do sp:write_u32(data,pattern(i)) end
        sp:write_u32(addr,64);sp:write_u32(data,base>>2)
        sp:write_u32(addr,128);sp:write_u32(data,0xcafebabe)
        sp:write_u32(addr,192);sp:write_u32(data,count)
        local code={0x1c00,0x1d00,0x1e00,0x1f00,0x3701,
            0xc0001000|(mode<<15)|(memory<<13)|(hold<<14)|(memory==1 and 3 or count),
            0x3300,0xf0000000}
        execute(code)
        local stride=mode==0 and 0 or 1<<mode
        for i=0,count-1 do expected[(i*stride)&~3]=pattern(i) end
        local function image(label)
            local errors=0
            for off=-16,2080,4 do if sp:read_u32(base+off)~=expected[off] then errors=errors+1 end end
            check(label..case,errors,0)
        end
        image('image')
        sp:write_u32(addr,192);check('counter'..case,sp:read_u32(data),pattern(count))
        -- Do not reinitialize WA0: this second program observes its first
        -- transfer's non-hold/hold result. DMAH0 writes one complete C-bus word.
        execute({0xc0005201,0xf0000000})
        local next=hold==1 and 0 or ((count*stride+2)&~3)
        expected[next]=0xcafebabe;image('continuation')
        if #fails==before then print('DSP_CBUS case='..case..' PASS')
        else print('DSP_CBUS case='..case..' FAIL errors='..(#fails-before)) end
    end end end end end
    if #fails==0 then print('DSP_CBUS PASS cases=512')
    else for _,f in ipairs(fails) do print('DSP_CBUS FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_CBUS FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_CBUS armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_CBUS FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^DSP_CBUS case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,513)] or
        len(re.findall(r'^DSP_CBUS PASS cases=512$',text,re.M))!=1):
        raise RuntimeError('C-bus DMA fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP C-bus: 512 mapped-program placement/WA0 cases passed live')

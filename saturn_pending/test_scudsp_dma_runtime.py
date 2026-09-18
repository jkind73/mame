#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Run DSP programs through SCU host ports and inspect B-bus DMA memory writes.

No private DSP state is patched. This qualifies beat addressing, not contention
or cycle accuracy. Missing binary/BIOS is a skip, never a native pass.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
from test_smpc_multitap_runtime import COMMON_LUA, ROOT

LUA = COMMON_LUA + r'''
local function test()
    park()
    local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
    local base=0x05c60000
    local words={0x1234abcd,0x5678dcba,0x2468ace0}
    local case=0
    for mode=0,7 do for indirect=0,1 do for hold=0,1 do
        case=case+1
        local before=#fails
        local expected={}
        for offset=0,1022,2 do
            sp:write_u16(base+offset,0xbeef);expected[offset]=0xbeef
        end
        sp:write_u32(control,0x8000)
        sp:write_u32(addr,0)
        for _,word in ipairs(words) do sp:write_u32(data,word) end
        sp:write_u32(addr,64);sp:write_u32(data,3)
        local code={0x1c00,0x1d00,0x9c000000|(base>>2),
            0xc0001000|(mode<<15)|(hold<<14)|(indirect<<13)|(indirect==1 and 1 or 3),
            0xf0000000}
        for _,op in ipairs(code) do sp:write_u32(program,op) end
        sp:write_u32(control,0x18000)
        local done=false
        for n=1,100 do
            emu.wait(emu.attotime.from_usec(10))
            if (sp:read_u32(control)&0x810000)==0 then done=true;break end
        end
        assert(done,'DSP completion timeout')
        local stride=mode==0 and 0 or (1<<mode)
        local offset=0
        for _,word in ipairs(words) do
            expected[offset]=(word>>16)&0xffff;offset=offset+stride
            expected[offset]=word&0xffff;offset=offset+stride
        end
        for off=0,1022,2 do
            check('case'..case..'_offset'..off,sp:read_u16(base+off),expected[off])
        end
        if #fails==before then print('DSP_DMA case='..case..' PASS') end
    end end end
    if #fails==0 then print('DSP_DMA PASS cases=32')
    else for _,f in ipairs(fails) do print('DSP_DMA FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_DMA FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('DSP_DMA armed')
'''

def validate_output(text, returncode):
    rows=[int(n) for n in re.findall(r'^DSP_DMA case=(\d+) PASS$',text,re.M)]
    if (returncode or 'DSP_DMA FAIL' in text or 'LUA ERROR' in text or
            rows!=list(range(1,33)) or len(re.findall(r'^DSP_DMA PASS cases=32$',text,re.M))!=1):
        raise RuntimeError('DSP DMA native fixture failed:\n'+text[-10000:])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,default=ROOT/'saturn')
    p.add_argument('--rompath',type=Path,default=ROOT/'regtests')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    exe=a.executable.resolve();rom=a.rompath.resolve();output=a.output.resolve()
    if not exe.is_file() or not (rom/'saturnjp.zip').is_file():
        print('SKIP: need native binary and saturnjp BIOS');return
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dsp-dma-live-') as tmp:
        d=Path(tmp);script=d/'test.lua';script.write_text(LUA)
        command=[str(exe),'saturnjp','-rompath',str(rom),'-noreadconfig','-skip_gameinfo',
                 '-nodrc','-video','none','-sound','none','-nothrottle','-seconds_to_run','30',
                 '-autoboot_delay','0','-autoboot_script',str(script)]
        for kind,folder in [('nvram','nvram'),('cfg','cfg'),('state','sta'),('snapshot','snap')]:
            command += ['-'+kind+'_directory',str(d/folder)]
        env=os.environ.copy();env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
        with (output/'runtime.log').open('w') as log:
            result=subprocess.run(command,cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        validate_output((output/'runtime.log').read_text(errors='replace'),result.returncode)
    print('DSP DMA: 32 mapped-program B-bus addressing cases passed live')

if __name__=='__main__':main()

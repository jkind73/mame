#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live CPU-mapped SMPC transport with two six-pad multitaps.

Six requests cover peripheral-only/status-first and each single-port omission.
Input patterns distinguish all 12 pads. Inputs are changed after page one to
check snapshot retention. A coroutine polls SF in 50us increments rather than
stretching CONTINUE across frames. This is not wire timing, extended-ID support,
VBlank timeout or live save-manager qualification. No binary/BIOS is a SKIP.
The unmodified pre-transport implementation is expected to FAIL, not be accepted.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [(38, 2), (38, 2), (19, 1), (19, 1), (19, 1), (19, 1)]
COMMON_LUA = r'''
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local screen = m.screens[":screen"]
local C = 0x00100000
local I0,I1,I2,COM,OREG,SR,SF = C+1,C+3,C+5,C+0x1f,C+0x21,C+0x61,C+0x63
local fails, pads = {}, {}
local function check(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%x want=%x",label,got,want) end
end
local function ready()
    for n=1,80 do
        if (sp:read_u8(SF)&1)==0 then return end
        emu.wait(emu.attotime.from_usec(50))
    end
    error("SMPC SF timeout")
end
local function park()
    sp:write_u32(0x06000000,0xaffe0009)
    for _,tag in ipairs({":maincpu",":slave"}) do
        local cpu=m.devices[tag]
        cpu.state["SR"].value=0xf0;cpu.state["PC"].value=0x06000000
    end
end
local buttons={{"A",0x0400},{"B",0x0100},{"X",0x0040},{"Y",0x0020}}
local function set_pad(index, pattern)
    local word=0xffff
    for bit,entry in ipairs(buttons) do
        local pressed=(pattern>>(bit-1))&1
        pads[index].fields[entry[1]]:set_value(pressed)
        if pressed==1 then word=word & ~entry[2] end
    end
    return word
end
'''
LUA = COMMON_LUA + r'''
local function test()
    park()
    for port=1,2 do for sub=1,6 do
        local tag=string.format(":ctrl%d:multitap:ctrl%d:joypad:JOY",port,sub)
        local p=m.ioport.ports[tag]
        assert(p,"missing pad "..tag)
        for _,entry in ipairs(buttons) do assert(p.fields[entry[1]],"missing button "..entry[1]) end
        pads[#pads+1]=p
    end end
    local case=0
    for _,modes in ipairs({{0,0},{3,0},{0,3}}) do
        for status=0,1 do
            case=case+1
            local before=#fails
            local want={}
            for port=1,2 do
                if modes[port]~=3 then want[#want+1]=0x16 end
                for sub=1,6 do
                    local index=(port-1)*6+sub
                    local word=set_pad(index,index)
                    if modes[port]~=3 then
                        want[#want+1]=2;want[#want+1]=(word>>8)&255;want[#want+1]=word&255
                    end
                end
            end
            -- Begin each independent request at VBlank, not a frame-paced
            -- continuation of the previous packet.
            emu.wait(screen:time_until_vblank_start())
            sp:write_u8(SF,1)
            sp:write_u8(I0,status);sp:write_u8(I1,(modes[2]<<6)|(modes[1]<<4)|8)
            sp:write_u8(I2,0xf0);sp:write_u8(COM,0x10)
            ready()
            local cont=status
            if status==1 then
                cont=cont~0x80;sp:write_u8(I0,cont);ready()
            end
            local pages=math.max(1,math.ceil(#want/32))
            for page=1,pages do
                local more=page<pages
                local flags=0x80|(page==1 and 0x40 or 0)|(more and 0x20 or 0)|(modes[2]<<2)|modes[1]
                check("case"..case.."_page"..page.."_SR",sp:read_u8(SR)&0xef,flags)
                local count=math.min(32,#want-(page-1)*32)
                for j=1,count do
                    check("case"..case.."_byte"..((page-1)*32+j),sp:read_u8(OREG+(j-1)*2),want[(page-1)*32+j])
                end
                if more then
                    for index=1,12 do set_pad(index,15-index) end
                    cont=cont~0x80;sp:write_u8(I0,cont);ready()
                end
            end
            -- Also cancel a stale stage in the old implementation so a
            -- negative baseline can complete all six independent requests.
            sp:write_u8(I0,cont|0x40)
            if #fails==before then
                print(string.format("SMPC_MULTITAP case=%d bytes=%d pages=%d PASS",case,#want,pages))
            end
        end
    end
    if #fails==0 then print("SMPC_MULTITAP PASS cases=6")
    else for _,f in ipairs(fails) do print("SMPC_MULTITAP FAIL "..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print("SMPC_MULTITAP FAIL "..tostring(err)) end
        m:exit()
    end)()
end)
print("SMPC_MULTITAP armed")
'''


def validate_output(text, returncode):
    records = [tuple(map(int, x)) for x in re.findall(
        r'^SMPC_MULTITAP case=(\d+) bytes=(\d+) pages=(\d+) PASS$', text, re.M)]
    expected = [(i, length, pages) for i, (length, pages) in enumerate(EXPECTED, 1)]
    if (returncode or 'SMPC_MULTITAP FAIL' in text or 'LUA ERROR' in text or
            records != expected or not re.search(r'^SMPC_MULTITAP PASS cases=6$', text, re.M)):
        raise RuntimeError('SMPC multitap fixture failed:\n' + text[-8000:])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT/'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT/'regtests')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.executable=a.executable.resolve();a.rompath=a.rompath.resolve();a.output=a.output.resolve()
    if not a.executable.is_file() or not (a.rompath/'saturnjp.zip').is_file():
        print('SKIP: need native executable and saturnjp BIOS')
        return
    a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='smpc-multitap-') as tmp:
        d=Path(tmp);script=d/'test.lua';script.write_text(LUA)
        env=os.environ.copy();env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
        command=[str(a.executable),'saturnjp','-rompath',str(a.rompath),
            '-ctrl1','multitap','-ctrl2','multitap','-noreadconfig','-skip_gameinfo','-nodrc',
            '-video','none','-sound','none','-nothrottle','-seconds_to_run','30',
            '-autoboot_delay','0','-autoboot_script',str(script),
            '-nvram_directory',str(d/'nvram'),'-cfg_directory',str(d/'cfg'),
            '-state_directory',str(d/'sta'),'-snapshot_directory',str(d/'snap')]
        with (a.output/'runtime.log').open('w') as log:
            result=subprocess.run(command,cwd=d,env=env,text=True,
                stdout=log,stderr=subprocess.STDOUT,timeout=180)
        validate_output((a.output/'runtime.log').read_text(errors='replace'),result.returncode)
    print('SMPC multitap: six live transport cases passed; not wire-timing/save-manager acceptance')


if __name__=='__main__':
    main()

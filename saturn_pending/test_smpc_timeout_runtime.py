#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live VBlank expiry of waiting and in-flight SMPC peripheral requests.

Four cases: waiting after status, waiting after a full peripheral page, CONTINUE
straddling VBlank, initial command straddling VBlank. Checks SF/PDL/NPE and no
late OREG overwrite; does not claim exact wire timing or IRQ latency.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

CASES = ('status-wait', 'report-wait', 'continue-pending', 'command-pending')
LUA = COMMON_LUA + r'''
local function submit(status)
    sp:write_u8(SF,1);sp:write_u8(I0,status);sp:write_u8(I1,8)
    sp:write_u8(I2,0xf0);sp:write_u8(COM,0x10)
end
local function report(status)
    emu.wait(screen:time_until_vblank_start())
    submit(status);ready()
    check('initial_pending_flags',sp:read_u8(SR)&0x60,0x60)
end
local function capture()
    local bytes={}
    for i=0,31 do bytes[i+1]=sp:read_u8(OREG+i*2) end
    return bytes
end
local function expired(label,bytes)
    check(label..'_SF',sp:read_u8(SF)&1,0)
    check(label..'_PDL_NPE',sp:read_u8(SR)&0x60,0)
    for i=0,31 do check(label..'_OREG'..i,sp:read_u8(OREG+i*2),bytes[i+1]) end
end
local function test()
    park()
    for _,name in ipairs({'status-wait','report-wait','continue-pending','command-pending'}) do
        local before=#fails
        local cont=0
        if name=='status-wait' or name=='report-wait' then
            local status=name=='status-wait' and 1 or 0
            report(status)
            local bytes=capture()
            -- Screen blank and the VDP2 callback can differ by a scanline.
            -- A 200us guard avoids pretending to measure that exact boundary.
            emu.wait(screen:time_until_vblank_start()+emu.attotime.from_usec(200))
            expired(name,bytes)
            cont=status~0x80;sp:write_u8(I0,cont)
            check(name..'_late_continue_ignored',sp:read_u8(SF)&1,0)
            emu.wait(emu.attotime.from_usec(1000))
            expired(name..'_late',bytes)
        elseif name=='continue-pending' then
            report(0)
            emu.wait(screen:time_until_vblank_start()-emu.attotime.from_usec(350))
            cont=0x80;sp:write_u8(I0,cont)
            check(name..'_armed',sp:read_u8(SF)&1,1)
            local bytes=capture()
            emu.wait(emu.attotime.from_usec(700))
            expired(name,bytes)
            emu.wait(emu.attotime.from_usec(1000))
            expired(name..'_late',bytes)
        else
            emu.wait(screen:time_until_vblank_start()-emu.attotime.from_usec(350))
            submit(0)
            check(name..'_armed',sp:read_u8(SF)&1,1)
            local bytes=capture()
            emu.wait(emu.attotime.from_usec(700))
            expired(name,bytes)
            emu.wait(emu.attotime.from_usec(1000))
            expired(name..'_late',bytes)
        end
        -- Let an unpatched negative baseline reach all four independent cases.
        sp:write_u8(I0,cont|0x40)
        if #fails==before then print('SMPC_TIMEOUT case='..name..' PASS') end
    end
    if #fails==0 then print('SMPC_TIMEOUT PASS cases=4')
    else for _,f in ipairs(fails) do print('SMPC_TIMEOUT FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SMPC_TIMEOUT FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('SMPC_TIMEOUT armed')
'''


def validate_output(text, returncode):
    cases = re.findall(r'^SMPC_TIMEOUT case=([a-z-]+) PASS$', text, re.M)
    if (returncode or 'SMPC_TIMEOUT FAIL' in text or 'LUA ERROR' in text or
            cases != list(CASES) or
            len(re.findall(r'^SMPC_TIMEOUT PASS cases=4$', text, re.M)) != 1):
        raise RuntimeError('SMPC timeout fixture failed:\n' + text[-10000:])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT/'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT/'regtests')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.executable = a.executable.resolve()
    a.rompath = a.rompath.resolve()
    a.output = a.output.resolve()
    if not a.executable.is_file() or not (a.rompath/'saturnjp.zip').is_file():
        print('SKIP: need native executable and saturnjp BIOS')
        return
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='smpc-timeout-live-') as tmp:
        d = Path(tmp)
        script = d/'test.lua'
        script.write_text(LUA)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        command = [str(a.executable), 'saturnjp', '-rompath', str(a.rompath),
                   '-ctrl1', 'multitap', '-ctrl2', 'multitap', '-noreadconfig',
                   '-skip_gameinfo', '-nodrc', '-video', 'none', '-sound', 'none',
                   '-nothrottle', '-seconds_to_run', '30', '-autoboot_delay', '0',
                   '-autoboot_script', str(script), '-nvram_directory', str(d/'nvram'),
                   '-cfg_directory', str(d/'cfg'), '-state_directory', str(d/'sta'),
                   '-snapshot_directory', str(d/'snap')]
        with (a.output/'runtime.log').open('w') as log:
            result = subprocess.run(command, cwd=d, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=180)
        validate_output((a.output/'runtime.log').read_text(errors='replace'), result.returncode)
    print('SMPC timeout: four waiting/in-flight expiry cases passed live; not wire-timing qualification')


if __name__ == '__main__':
    main()

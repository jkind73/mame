#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live Saturn CD block fixture: Init (04h) parameters, standby timeout and tray closing.

Contracts: ST-38 function 1.6 CDC_CdInit (standby time 0 = 180 s / FFFFh = no change,
"If the standby time passes while in the <PAUSE> state, it is regarded as <STANDBY>",
"If tray is open, this closes it") and Figure 4.1; init flag bit 7 (NCHG_INIT_FLAG in the SDK, "No change?" in
Mednafen cdb.cpp) suppresses the flag change. Uses the generated MODE1/2048 disc of test_cd_host_runtime.py.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile

import test_cd_host_runtime as host

MARKER = 'CD_INIT_PARAMS'

LUA_HEAD = host.LUA.split("local function test()")[0].replace(
    'CD_HOST_RUNTIME', MARKER)

LUA_TEST = r'''
local function check_true(label, cond)
    checks = checks + 1
    assert(cond, label)
end
local function state() return cmd(0,0,0,0)[1]&0x0f00 end
local function wait_state(want, ms)
    for _=1,ms//5 do
        if state()==want then return true end
        waitms(5)
    end
    error(string.format('drive did not reach %04x (now %04x)', want, state()))
end
local function test()
    sp:write_u32(0x06000000,0xaffe0009)
    for _,tag in ipairs({":maincpu",":slave"}) do
        m.devices[tag].state["SR"].value=0xf0
        m.devices[tag].state["PC"].value=0x06000000
    end
    wait_state(0x0100, 3000)

    -- Standby time of 2 s: still PAUSE after 1.5 s, STANDBY after 2.5 s.
    cmd(0x0400,2,0,0)
    wait_state(0x0100, 2000)
    waitms(1400)
    eq('PAUSE before the standby time',state(),0x0100)
    waitms(1100)
    eq('STANDBY after the standby time',state(),0x0200)

    -- FFFFh leaves the 2 s setting alone.
    cmd(0x0400,0xffff,0,0)
    wait_state(0x0100, 2000)
    waitms(1400)
    eq('unchanged time: PAUSE',state(),0x0100)
    waitms(1100)
    eq('unchanged time: STANDBY',state(),0x0200)

    -- 0 selects the default of 180 s: nothing happens within 4 s.
    cmd(0x0400,0,0,0)
    wait_state(0x0100, 2000)
    waitms(4000)
    eq('default time: still PAUSE',state(),0x0100)

    -- Init closes an open tray and the disc is read again.
    cmd(0x0500,0,0,0)
    wait_state(0x0600, 2000)
    cmd(0x0400,0,0,0)
    wait_state(0x0100, 3000)
    eq('tray closed by Init',state(),0x0100)

    -- Init flag bit 7: the fixed speed bit (4) only applies when bit 7 is clear. The drive speed is visible as the
    -- time a 100 sector Play takes: 100/75 s at single speed, half of that at double speed.
    local function play_time()
        sp:write_u16(HIRQ,0xffef)
        cmd(0x1080,150,0,100)
        local t0=emu.time()
        for _=1,2000 do
            if (sp:read_u16(HIRQ)&0x10)~=0 then return emu.time()-t0 end
            waitms(2)
        end
        error('Play did not end')
    end
    local function speed_after(flags)
        cmd(0x0400|flags,0,0,0);wait_state(0x0100,2000)
        local t=play_time()
        wait_state(0x0100,2000)
        return t
    end
    local single=speed_after(0x10)
    local kept=speed_after(0x80)
    local double=speed_after(0x00)
    local ignored=speed_after(0x90)
    local msg=string.format('single=%.3f no-change=%.3f double=%.3f no-change-2=%.3f',single,kept,double,ignored)
    -- The Play start-up latency is common, so compare the two speeds by ratio.
    check_true('double speed is clearly faster than single: '..msg, double<single*0.8)
    check_true('bit 7 keeps single speed: '..msg, math.abs(kept-single)<single*0.15)
    check_true('bit 7 keeps double speed: '..msg, math.abs(ignored-double)<double*0.15)

    print('CD_INIT_PARAMS PASS checks='..checks)
    m:exit()
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<30 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('CD_INIT_PARAMS FAIL '..tostring(err));m:exit() end
    end)()
end)
print('CD_INIT_PARAMS armed')
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=host.ROOT / 'saturn')
    p.add_argument('--rompath', type=Path, default=host.ROOT / 'regtests')
    p.add_argument('--require-runtime', action='store_true')
    a = p.parse_args()
    executable, rompath = a.executable.resolve(), a.rompath.resolve()
    missing = ([str(executable)] if not executable.is_file() else [])
    if not (rompath / 'saturnjp.zip').is_file():
        missing.append(str(rompath / 'saturnjp.zip'))
    if missing:
        message = 'missing runtime prerequisite: ' + ', '.join(missing)
        if a.require_runtime:
            raise SystemExit(message)
        print('SKIP: ' + message)
        return
    with tempfile.TemporaryDirectory(prefix='saturn-initparams-') as tmp:
        directory = Path(tmp)
        cue = host.build_disc(directory)
        script = directory / 'initparams.lua'
        script.write_text(LUA_HEAD + LUA_TEST)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        result = subprocess.run([
            str(executable), 'saturnjp', '-cdrom', str(cue),
            '-rompath', str(rompath), '-noreadconfig', '-skip_gameinfo', '-nodrc',
            '-video', 'none', '-sound', 'none', '-nothrottle',
            '-autoboot_delay', '0', '-autoboot_script', str(script), '-seconds_to_run', '120',
            '-nvram_directory', str(directory / 'nvram'),
            '-cfg_directory', str(directory / 'cfg'), '-state_directory', str(directory),
            '-snapshot_directory', str(directory),
        ], cwd=directory, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=600)
        text = result.stdout
        if result.returncode or 'LUA ERROR' in text or MARKER + ' FAIL' in text \
                or not re.search(r'^' + MARKER + r' PASS checks=\d+$', text, re.M):
            raise AssertionError(f'Runtime failure (exit {result.returncode}):\n{text}')
        print('\n'.join(l for l in text.splitlines() if MARKER in l))


if __name__ == '__main__':
    main()

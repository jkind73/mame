#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live Saturn CD block fixture: Copy/Move Sector Data command codes and Open Tray.

Uses the generated MODE1/2048 disc of test_cd_host_runtime.py; no third-party
content. Requires an existing saturn executable and saturnjp BIOS;
--require-runtime turns missing prerequisites into an error.

Contracts: ST-38 Table 8.1 (7.6 Copy Sector Data, 7.7 Move Sector Data in
command order; 1.7 Open Tray) and Mednafen cdb.cpp (COMMAND_COPY_SECDATA = 65h,
COMMAND_MOVE_SECDATA = 66h; the source sectors are freed only by the move).
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile

import test_cd_host_runtime as host

MARKER = 'CD_COPYMOVE_TRAY'

# Reuses the command helpers of the host fixture (same register addresses).
LUA_HEAD = host.LUA.split("local function test()")[0].replace(
    'CD_HOST_RUNTIME', MARKER)

LUA_TEST = r'''
local function test()
    sp:write_u32(0x06000000,0xaffe0009)
    for _,tag in ipairs({":maincpu",":slave"}) do
        m.devices[tag].state["SR"].value=0xf0
        m.devices[tag].state["PC"].value=0x06000000
    end
    cmd(0x0600,0,0,0)
    cmd(0x11ff,0xffff,0,0);waitms(100)
    reset();cmd(0x6003,0x0300,0,0)
    route(0,1,255)
    local a,b=bytes(11,7),bytes(93,8)
    local ab=pair(a,b)
    put(2);writebytes(ab,4704);finish(2352)
    eq('two sectors in partition 1',count(1),2)

    -- 48h Reset Selector bit 3 (ST-38 5.9) only disconnects the partition output connectors: the data stays.
    cmd(0x4808,0,0,0)
    eq('reset selector bit 3 keeps the partition data',count(1),2)

    -- 65h Copy Sector Data: destination filter 2, offset 0, two sectors.
    -- The source keeps its sectors and the destination receives copies.
    sp:write_u16(HIRQ,0xfeff)
    cmd(0x6502,0x0000,1<<8,2)
    eq('copy ECPY',sp:read_u16(HIRQ)&0x0100,0x0100)
    eq('copy keeps source',count(1),2)
    eq('copy fills destination',count(2),2)
    eq('copy consumes buffer',free(),196)

    -- 66h Move Sector Data: destination filter 3; the source loses them.
    sp:write_u16(HIRQ,0xfeff)
    cmd(0x6603,0x0000,1<<8,2)
    eq('move ECPY',sp:read_u16(HIRQ)&0x0100,0x0100)
    eq('move empties source',count(1),0)
    eq('move fills destination',count(3),2)
    eq('move does not allocate',free(),196)
    reset();eq('pool restored',free(),200)

    -- 05h Open Tray: BUSY answer, then OPEN; DCHG and EFLS raised.
    sp:write_u16(HIRQ,0xfdde)
    local r=cmd(0x0500,0,0,0)
    eq('open answers BUSY',r[1]&0x0f00,0x0000)
    eq('open CMOK',sp:read_u16(HIRQ)&1,1)
    eq('open DCHG',sp:read_u16(HIRQ)&0x20,0x20)
    eq('open EFLS',sp:read_u16(HIRQ)&0x200,0x200)
    local s
    for _=1,200 do
        waitms(5)
        s=cmd(0,0,0,0)
        if (s[1]&0x0f00)==0x0600 then break end
    end
    eq('drive reaches OPEN',s[1]&0x0f00,0x0600)
    -- A second Open Tray completes without leaving OPEN.
    local r2=cmd(0x0500,0,0,0)
    eq('reopen stays OPEN',r2[1]&0x0f00,0x0600)
    print('CD_COPYMOVE_TRAY PASS checks='..checks)
    m:exit()
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<30 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('CD_COPYMOVE_TRAY FAIL '..tostring(err));m:exit() end
    end)()
end)
print('CD_COPYMOVE_TRAY armed')
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
    with tempfile.TemporaryDirectory(prefix='saturn-copymove-') as tmp:
        directory = Path(tmp)
        cue = host.build_disc(directory)
        script = directory / 'copymove.lua'
        script.write_text(LUA_HEAD + LUA_TEST)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        result = subprocess.run([
            str(executable), 'saturnjp', '-cdrom', str(cue),
            '-rompath', str(rompath), '-noreadconfig', '-skip_gameinfo', '-nodrc',
            '-video', 'none', '-sound', 'none', '-nothrottle',
            '-autoboot_delay', '0', '-autoboot_script', str(script), '-seconds_to_run', '60',
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

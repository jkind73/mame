#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live Saturn SMPC fixture: SYSRES returns the system to its power-on state.

Contract: SMPC User's Manual p.29 (SYSRES resets all functions and starts the boot
ROM) and Table 1.1 (power-on: slave SH-2 OFF, sound CPU OFF, 320 clock mode).
The state is observed through INTBACK status OREG10 (bit 6 clock mode, bit 4
slave SH-2 on, bit 0 sound on; manual p.40), with no
private state or device calls. Requires an existing saturn executable and the
saturnjp BIOS; --require-runtime makes missing prerequisites an error.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MARKER = 'SMPC_SYSRES'

LUA = r'''
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local BASE = 0x20100000
local function reg(n) return BASE + n end
local checks = 0
local function eq(label, got, want)
    checks = checks + 1
    assert(got == want, string.format("%s got=%x want=%x", label, got, want))
end
local function waitms(n) emu.wait(emu.attotime.from_msec(n)) end
local function command(code, ireg0, ireg1, ireg2, limit)
    for _ = 1, 2000 do
        if (sp:read_u8(reg(0x63)) & 1) == 0 then break end
        waitms(1)
    end
    if ireg0 then
        sp:write_u8(reg(0x01), ireg0);sp:write_u8(reg(0x03), ireg1);sp:write_u8(reg(0x05), ireg2)
    end
    sp:write_u8(reg(0x63), 1)
    sp:write_u8(reg(0x1f), code)
    for _ = 1, limit or 2000 do
        waitms(1)
        if (sp:read_u8(reg(0x63)) & 1) == 0 then return end
    end
    error(string.format("SF not cleared for command %02x", code))
end
local function status()
    command(0x10, 1, 0x0f, 0xf0) -- INTBACK, status only, no peripheral data
    return sp:read_u8(reg(0x21 + 10 * 2))
end
local function test()
    -- Keep the SH-2s out of BIOS code while the SMPC is exercised.
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        m.devices[tag].state["SR"].value = 0xf0
        m.devices[tag].state["PC"].value = 0x06000000
    end
    command(0x0e, nil, nil, nil, 3000)      -- CKCHG352
    command(0x02);command(0x06)             -- SSHON, SNDON
    local s = status()
    eq('352 mode before SYSRES', s & 0x40, 0x40)
    eq('slave on before SYSRES', s & 0x10, 0x10)
    eq('sound on before SYSRES', s & 0x01, 0x01)
    command(0x0d, nil, nil, nil, 3000)      -- SYSRES
    local r = status()
    eq('320 mode after SYSRES', r & 0x40, 0)
    eq('slave off after SYSRES', r & 0x10, 0)
    eq('sound off after SYSRES', r & 0x01, 0)
    print('SMPC_SYSRES PASS checks=' .. checks)
    m:exit()
end
local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 30 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print('SMPC_SYSRES FAIL ' .. tostring(err));m:exit() end
    end)()
end)
print('SMPC_SYSRES armed')
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
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
    with tempfile.TemporaryDirectory(prefix='saturn-sysres-') as tmp:
        directory = Path(tmp)
        script = directory / 'sysres.lua'
        script.write_text(LUA)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        result = subprocess.run([
            str(executable), 'saturnjp',
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

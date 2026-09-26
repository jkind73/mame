#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live Saturn SMPC fixture: peripheral acquisition time optimization (IREG1 OPE).

Contract: SMPC User's Manual pp.55-57. With OPE=1 peripheral collection starts at
V-BLANK-OUT. With OPE=0 the first collection is measured and the following ones
start so that they finish 1 ms before V-BLANK-IN. Observed on the emulated
machine clock through the SF handshake and the VDP2 TVSTAT VBLANK bit.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MARKER = 'SMPC_OPE'

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
local TVSTAT = 0x05F80004
local function vblank() return (sp:read_u16(TVSTAT) & 8) ~= 0 end
local function now() return m.time:as_double() * 1e6 end
-- One peripheral-only INTBACK issued during V-BLANK; returns the completion
-- time relative to V-BLANK-OUT and to the following V-BLANK-IN (microseconds).
local function frame(ope)
    while not vblank() do emu.wait(emu.attotime.from_usec(20)) end
    while (sp:read_u8(reg(0x63)) & 1) ~= 0 do emu.wait(emu.attotime.from_usec(20)) end
    sp:write_u8(reg(0x01), 0);sp:write_u8(reg(0x03), 0x08 | (ope << 1));sp:write_u8(reg(0x05), 0xf0)
    sp:write_u8(reg(0x63), 1)
    sp:write_u8(reg(0x1f), 0x10)
    while vblank() do emu.wait(emu.attotime.from_usec(5)) end
    local vout = now()
    while (sp:read_u8(reg(0x63)) & 1) ~= 0 do emu.wait(emu.attotime.from_usec(5)) end
    local done = now() - vout
    -- leave SMPC interrupt state: break the (single page) command if it lingers
    sp:write_u8(reg(0x03), 0x40)
    while not vblank() do emu.wait(emu.attotime.from_usec(20)) end
    local vin = now() - vout
    return done, vin - done
end
local function test()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        m.devices[tag].state["SR"].value = 0xf0
        m.devices[tag].state["PC"].value = 0x06000000
    end
    waitms(5)
    sp:write_u16(0x05F80000, 0x8000) -- TVMD: DISP on, 320x224, so VBLANK toggles
    waitms(40)
    -- OPE=1: not optimized, done shortly after V-BLANK-OUT.
    for i = 1, 3 do
        local done, before_vin = frame(1)
        assert(done < 1500, string.format("OPE=1 done %.0f us after V-BLANK-OUT", done))
        checks = checks + 1
    end
    -- OPE=0: the first collection is measured (starts at V-BLANK-OUT) ...
    local first = frame(0)
    assert(first < 1500, string.format("first OPE=0 done %.0f us", first))
    checks = checks + 1
    -- ... and later ones finish about 1 ms before V-BLANK-IN.
    for i = 1, 3 do
        local done, before_vin = frame(0)
        assert(done > 5000, string.format("optimized done only %.0f us after V-BLANK-OUT", done))
        assert(before_vin > 700 and before_vin < 1400, string.format("optimized ends %.0f us before V-BLANK-IN", before_vin))
        checks = checks + 2
    end
    print('SMPC_OPE PASS checks=' .. checks)
    m:exit()
end
local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 30 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print('SMPC_OPE FAIL ' .. tostring(err));m:exit() end
    end)()
end)
print('SMPC_OPE armed')
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
    with tempfile.TemporaryDirectory(prefix='saturn-ope-') as tmp:
        directory = Path(tmp)
        script = directory / 'ope.lua'
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

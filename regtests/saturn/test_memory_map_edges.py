#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live Saturn memory map fixture: VDP1 register window, A-Bus dummy space.

Contract: docs/system/saturn_memory_map.md (from ST-013, ST-097): VDP1 registers
occupy 05D00000H-05D00017H (24 bytes, TVMR..MODR); A-Bus dummy space
05000000H-057FFFFFH is not chip-selected (writes have no effect, reads float
high). Accessed through the CPU program space of the emulated machine.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MARKER = 'MEMMAP_EDGES'

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
    -- MODR (05D00016H) reads the VDP1 version in bits 15-12
    eq('MODR version', sp:read_u16(0x05D00016) & 0xf000, 0x1000)
    -- Bytes 18h-1Fh are outside the 24-byte register window: not retained
    sp:write_u16(0x05D00018, 0x1234)
    sp:write_u16(0x05D0001E, 0x5678)
    assert(sp:read_u16(0x05D00018) ~= 0x1234, 'write to 05D00018 retained')
    assert(sp:read_u16(0x05D0001E) ~= 0x5678, 'write to 05D0001E retained')
    checks = checks + 2
    -- A-Bus dummy space ignores writes and floats high
    sp:write_u32(0x057FFFFC, 0x00000000)
    eq('dummy read after write', sp:read_u32(0x057FFFFC), 0xffffffff)
    sp:write_u32(0x05000000, 0x12345678)
    eq('dummy low read', sp:read_u32(0x05000000), 0xffffffff)
    print('MEMMAP_EDGES PASS checks=' .. checks)
    m:exit()
end
local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 30 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print('MEMMAP_EDGES FAIL ' .. tostring(err));m:exit() end
    end)()
end)
print('MEMMAP_EDGES armed')
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
    with tempfile.TemporaryDirectory(prefix='saturn-memmap-') as tmp:
        directory = Path(tmp)
        script = directory / 'memmap.lua'
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

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live RESET-port/RESB checks with NMI disabled; no debounce qualification."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

LABELS = ('released', 'press-before-edge', 'press-sampled', 'status-report',
          'peripheral-report', 'release-before-edge', 'release-sampled')
LUA = COMMON_LUA + r'''
local function test()
    park()
    local reset=m.ioport.ports[':RESET'];assert(reset,'missing RESET port')
    local button=reset.fields['Reset Button'];assert(button,'missing reset button')
    wait_vblank();ready()
    -- Exercise RESDISA through mapped registers, not a private-field write.
    sp:write_u8(SF,1);sp:write_u8(COM,0x1a);ready()
    button:set_value(0)
    local function sample()
        emu.wait(screen:time_until_vblank_start()+emu.attotime.from_usec(200))
    end
    local function observe(label,value)
        local before=#fails
        check(label,sp:read_u8(SR)&0x10,value)
        if #fails==before then print('SMPC_RESB case='..label..' PASS') end
    end
    sample();observe('released',0)
    emu.wait(screen:time_until_pos(24,16))
    button:set_value(1);observe('press-before-edge',0)
    sample();check('pressed_input_visible',reset:read()&1,1)
    observe('press-sampled',0x10)
    sp:write_u8(SF,1);sp:write_u8(I0,1);sp:write_u8(I1,0)
    sp:write_u8(I2,0xf0);sp:write_u8(COM,0x10);ready()
    observe('status-report',0x10)
    sp:write_u8(SF,1);sp:write_u8(I0,0);sp:write_u8(I1,8)
    sp:write_u8(I2,0xf0);sp:write_u8(COM,0x10);ready()
    observe('peripheral-report',0x10)
    button:set_value(0);observe('release-before-edge',0x10)
    sample();check('released_input_visible',reset:read()&1,0)
    observe('release-sampled',0)
    if #fails==0 then print('SMPC_RESB PASS cases=7')
    else for _,f in ipairs(fails) do print('SMPC_RESB FAIL '..f) end end
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<180 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SMPC_RESB FAIL '..tostring(err)) end
        m:exit()
    end)()
end)
print('SMPC_RESB armed')
'''


def validate_output(text, returncode):
    rows = re.findall(r'^SMPC_RESB case=([a-z-]+) PASS$', text, re.M)
    if (returncode or 'SMPC_RESB FAIL' in text or 'LUA ERROR' in text or
            rows != list(LABELS) or
            len(re.findall(r'^SMPC_RESB PASS cases=7$', text, re.M)) != 1):
        raise RuntimeError('SMPC RESB fixture failed:\n'+text[-10000:])


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
    with tempfile.TemporaryDirectory(prefix='smpc-resb-live-') as tmp:
        d = Path(tmp)
        script = d/'test.lua'
        script.write_text(LUA)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        command = [str(a.executable), 'saturnjp', '-rompath', str(a.rompath),
                   '-noreadconfig', '-skip_gameinfo', '-nodrc', '-video', 'none',
                   '-sound', 'none', '-nothrottle', '-seconds_to_run', '30',
                   '-autoboot_delay', '0', '-autoboot_script', str(script),
                   '-nvram_directory', str(d/'nvram'), '-cfg_directory', str(d/'cfg'),
                   '-state_directory', str(d/'sta'), '-snapshot_directory', str(d/'snap')]
        with (a.output/'runtime.log').open('w') as log:
            result = subprocess.run(command, cwd=d, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=180)
        validate_output((a.output/'runtime.log').read_text(errors='replace'), result.returncode)
    print('SMPC RESB: seven latched reset-button observations passed live; not NMI debounce qualification')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live H/V edge-history save/load with a mapped SCU interrupt-status oracle.

Save inside active display, advance naturally into HBlank+VBlank, then load.
At the first restored HBlank, expect HBlank status but no spurious VBlank-OUT.
Save items are read only for diagnostics/registration checks, never overwritten.
The test uses scheduled file save/load and frozen emulated time during host I/O.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

LUA = COMMON_LUA + r'''
local phase,frames,saved,loaded='setup',0,false,false
local state_path=assert(os.getenv('SYNC_SAVE_FILE'))
local save_clock=0
local items={}
local subscribers={}
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('SYNC_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('SYNC_SAVE loaded')
end)
local function levels(label,h,v)
    check(label..'_TVSTAT',sp:read_u16(0x05f80004)&12,(h<<2)|(v<<3))
    for field,value in pairs({m_prev_hint=h,m_prev_vint=v}) do
        if items[field] then check(label..'_'..field,items[field]:read(0),value) end
    end
end
local function finish()
    if #fails==0 then print('SYNC_SAVE PASS restored_HV=0 first_edge_IST=4')
    else for _,f in ipairs(fails) do print('SYNC_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('SYNC_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('SYNC_SAVE FAIL bounded wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park()
        local root_items=m.devices[':'].items
        local control=false
        for name,index in pairs(root_items) do
            local field=name:match('([^/]+)$')
            if field=='m_system_halt' then control=true end
            if field=='m_prev_hint' or field=='m_prev_vint' then items[field]=emu.item(index) end
        end
        assert(control,'wrong root save-item enumeration')
        for _,field in ipairs({'m_prev_hint','m_prev_vint'}) do
            if not items[field] then fails[#fails+1]='missing save item '..field end
        end
        sp:write_u16(0x05f80000,0x8000) -- enabled, 320x224 non-interlace
        sp:write_u32(0x05fe00a0,0xbfff) -- mask IRQ delivery, retain IST reporting
        emu.wait(screen:time_until_pos(24,16))
        levels('before_save',0,0)
        sp:write_u32(0x05fe00a4,0xfffffff9) -- W0C only HBlank/VBlank-OUT
        check('cleared_IST',sp:read_u32(0x05fe00a4)&6,0)
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced time')
        emu.unpause()
        -- Change edge history via real raster callbacks, not emu.item writes.
        emu.wait(screen:time_until_pos(240,400))
        levels('mutated',1,1)
        print('SYNC_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore frozen time')
        levels('restored',0,0)
        check('restored_IST',sp:read_u32(0x05fe00a4)&6,0)
        emu.unpause()
        -- Sample after the first HBlank callback, but before the next line.
        emu.wait(screen:time_until_pos(24,400))
        levels('first_edge',1,0)
        check('first_edge_IST',sp:read_u32(0x05fe00a4)&6,4)
        finish()
    end)
    end
end)
print('SYNC_SAVE armed')
'''


def validate_output(text, returncode):
    stages = re.findall(r'^SYNC_SAVE (saved|mutated|loaded)$', text, re.M)
    if (returncode or 'SYNC_SAVE FAIL' in text or 'LUA ERROR' in text or
            stages != ['saved', 'mutated', 'loaded'] or
            len(re.findall(r'^SYNC_SAVE PASS restored_HV=0 first_edge_IST=4$', text, re.M)) != 1):
        raise RuntimeError('Sync save fixture failed:\n' + text[-10000:])


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
    with tempfile.TemporaryDirectory(prefix='sync-save-live-') as tmp:
        d = Path(tmp)
        script = d/'test.lua'
        script.write_text(LUA)
        (d/'sta').mkdir()
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                   SYNC_SAVE_FILE=str(d/'sta/sync.sta'))
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
        state = d/'sta/sync.sta'
        if not state.is_file() or state.stat().st_size <= 32 or state.read_bytes()[:8] != b'MAMESAVE':
            raise RuntimeError('Missing or malformed scheduled save file')
    print('Sync save: H/V edge history and first restored SCU interrupt status passed live')


if __name__ == '__main__':
    main()

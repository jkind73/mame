#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live scheduled save/load of a partially consumed SMPC controller snapshot.

Save after byte 32 of a 38-byte two-multitap report. Drain it, overwrite the
snapshot with changed inputs, then use zero-byte modes to clear its size/cursor
and change its mode/state. Load through MAME's scheduled file save manager and
verify the original first page and remaining six bytes. Retained notifiers and
strict ordered markers reject missing saves/loads. No buffer_save shortcut,
private device-field mutation, or claims about wire timing/extended IDs.
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
local state_path=assert(os.getenv('SMPC_SAVE_FILE'))
local save_clock=0
local subscribers={}
subscribers[1]=emu.add_machine_pre_save_notifier(function()
    saved=true;save_clock=emu.time();print('SMPC_SAVE saved')
end)
subscribers[2]=emu.add_machine_post_load_notifier(function()
    loaded=true;print('SMPC_SAVE loaded')
end)
local original,changed={},{}
local function packet(invert)
    local bytes={}
    for port=1,2 do
        bytes[#bytes+1]=0x16
        for sub=1,6 do
            local index=(port-1)*6+sub
            local word=set_pad(index,invert and 15-index or index)
            bytes[#bytes+1]=2;bytes[#bytes+1]=(word>>8)&255;bytes[#bytes+1]=word&255
        end
    end
    return bytes
end
local function request(modes)
    wait_vblank()
    sp:write_u8(SF,1);sp:write_u8(I0,0);sp:write_u8(I1,modes|8)
    sp:write_u8(I2,0xf0);sp:write_u8(COM,0x10);ready()
end
local function page(label,bytes,start,count,flags)
    check(label..'_SR',sp:read_u8(SR)&0xef,flags)
    for j=1,count do check(label..'_byte'..j,sp:read_u8(OREG+(j-1)*2),bytes[start+j-1]) end
end
local function tail(label)
    sp:write_u8(I0,0x80);ready()
    page(label,original,33,6,0x80)
    -- The integrated implementation retains FF padding and a command marker
    -- on a short page. This also detects a missing restored size (underflow
    -- would incorrectly copy 32 bytes instead of six). Not a hardware oracle
    -- for unused OREG bytes.
    for j=7,31 do check(label..'_padding'..j,sp:read_u8(OREG+(j-1)*2),0xff) end
    check(label..'_marker',sp:read_u8(OREG+62),0x10)
end
local function finish()
    if #fails==0 then print('SMPC_SAVE PASS bytes=38 cursor=32 tail=6')
    else for _,f in ipairs(fails) do print('SMPC_SAVE FAIL '..f) end end
    phase='done';emu.unpause();m:exit()
end
local function step(fn)
    phase='busy'
    coroutine.wrap(function()
        local ok,err=pcall(fn)
        if not ok then print('SMPC_SAVE FAIL '..tostring(err));phase='done';emu.unpause();m:exit() end
    end)()
end
emu.register_frame_done(function()
    frames=frames+1
    assert(subscribers[1] and subscribers[2])
    if frames>600 and phase~='done' then
        print('SMPC_SAVE FAIL bounded save/load wait expired');phase='done';emu.unpause();m:exit();return
    end
    if frames<180 then return end
    if phase=='setup' then step(function()
        park()
        for port=1,2 do for sub=1,6 do
            local tag=string.format(':ctrl%d:multitap:ctrl%d:joypad:JOY',port,sub)
            local p=m.ioport.ports[tag];assert(p,'missing pad '..tag)
            for _,entry in ipairs(buttons) do assert(p.fields[entry[1]],'missing button '..entry[1]) end
            pads[#pads+1]=p
        end end
        original=packet(false);request(0)
        page('before_save',original,1,32,0xe0)
        -- Pause only after scheduling: schedule_save itself resumes the machine.
        -- UI frame callbacks still run while paused; no emulated VBlank can
        -- expire the packet while the host waits for disk I/O.
        m:save(state_path);emu.pause();phase='saved'
    end)
    elseif phase=='saved' and saved then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'save wait advanced emulated time')
        emu.unpause()
        tail('drained')
        sp:write_u8(I0,0xc0)
        changed=packet(true);request(0)
        page('changed_snapshot',changed,1,32,0xe0)
        -- BREAK cancels that packet; a zero-byte packet poisons modes, SR,
        -- size, cursor and stage while retaining the changed buffer bytes.
        sp:write_u8(I0,0x40);request(0xf0)
        check('zero_byte_SR',sp:read_u8(SR)&0xef,0xcf)
        print('SMPC_SAVE mutated')
        m:load(state_path);emu.pause();phase='loaded'
    end)
    elseif phase=='loaded' and loaded then step(function()
        assert(m.paused and math.abs(emu.time()-save_clock)<1e-9,'load did not restore frozen time')
        emu.unpause()
        page('restored_first',original,1,32,0xe0)
        tail('restored_tail')
        finish()
    end)
    end
end)
print('SMPC_SAVE armed')
'''


def validate_output(text, returncode):
    stages = re.findall(r'^SMPC_SAVE (saved|mutated|loaded)$', text, re.M)
    if (returncode or 'SMPC_SAVE FAIL' in text or 'LUA ERROR' in text or
            stages != ['saved', 'mutated', 'loaded'] or
            len(re.findall(r'^SMPC_SAVE PASS bytes=38 cursor=32 tail=6$', text, re.M)) != 1):
        raise RuntimeError('SMPC save fixture failed:\n' + text[-10000:])


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
    with tempfile.TemporaryDirectory(prefix='smpc-save-') as tmp:
        d = Path(tmp)
        script = d/'test.lua'
        script.write_text(LUA)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                   SMPC_SAVE_FILE=str(d/'sta/multitap.sta'))
        (d/'sta').mkdir()
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
        state = d/'sta/multitap.sta'
        if not state.is_file() or state.stat().st_size <= 32 or state.read_bytes()[:8] != b'MAMESAVE':
            raise RuntimeError('Missing or malformed scheduled save file')
    print('SMPC save: partial report snapshot/cursor/mode restored through scheduled file save/load')


if __name__ == '__main__':
    main()

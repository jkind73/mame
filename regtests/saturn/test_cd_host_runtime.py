#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live Saturn host-window PUT/GET, reservation, selector and discard fixture.

Generated MODE1/2048 disc, no third-party disc content. Requires an existing
saturn executable and saturnjp BIOS; --require-runtime makes missing prerequisites
an error instead of a skip. Does not build or download anything.

Contracts: ST-162-062094 pp.27-28 (FIFO/CSCT), 42-43 (disconnected discard),
95-97 (sector transfer/partial PUT). Command encodings follow the reviewed CD
command handlers. CPU parking and coroutine scheduling follow the independent
validator's test_cdda_runtime.py at a735e034. This newly authored fixture has no
native result yet. No private CD fields, direct device-method calls, mixer
capture, or modified existing expectations are used.
"""
from pathlib import Path
import argparse
import os
import re
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MARKER = 'CD_HOST_RUNTIME'


def both(value, width):
    return value.to_bytes(width, 'little') + value.to_bytes(width, 'big')


def record(name, lba, size, flags):
    out = bytearray(33 + len(name) + (len(name) % 2 == 0))
    out[0] = len(out)
    out[2:10] = both(lba, 4)
    out[10:18] = both(size, 4)
    out[18:25] = bytes([126, 1, 1, 0, 0, 0, 0])
    out[25] = flags
    out[28:32] = both(1, 2)
    out[32] = len(name)
    out[33:33 + len(name)] = name
    return bytes(out)


def build_disc(directory):
    sectors = [bytearray((lba * 13 + i * 7) & 255 for i in range(2048))
               for lba in range(128)]
    root = record(b'\0', 18, 2048, 2)
    pvd = bytearray(2048)
    pvd[:7] = b'\x01CD001\x01'
    pvd[8:40] = b'SATURN REGRESSION'.ljust(32)
    pvd[40:72] = b'GENERATED HOST FIXTURE'.ljust(32)
    pvd[80:88] = both(128, 4)
    pvd[120:124] = both(1, 2)
    pvd[124:128] = both(1, 2)
    pvd[128:132] = both(2048, 2)
    pvd[156:190] = root
    pvd[881] = 1
    sectors[16] = pvd
    sectors[17] = bytearray(b'\xffCD001\x01'.ljust(2048, b'\0'))
    entries = root + record(b'\1', 18, 2048, 2) + record(b'TEST.BIN;1', 40, 32 * 2048, 0)
    sectors[18] = bytearray(entries.ljust(2048, b'\0'))
    assert all(len(s) == 2048 for s in sectors)
    image = b''.join(sectors)
    assert len(image) == 128 * 2048
    assert image[16*2048+156:16*2048+190] == root
    assert struct.unpack_from('<I', root, 2)[0] == 18
    assert struct.unpack_from('>I', root, 6)[0] == 18
    (directory / 'host.bin').write_bytes(image)
    cue = directory / 'host.cue'
    cue.write_text('FILE "host.bin" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n')
    return cue


LUA = r'''
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local HIRQ, CR1, CR2, CR3, CR4 = 0x05880008, 0x05880018, 0x0588001c, 0x05880020, 0x05880024
local DATA = 0x05818000
local checks = 0
local function eq(label, got, want)
    checks = checks + 1
    assert(got == want, string.format("%s got=%x want=%x", label, got, want))
end
local function waitms(n) emu.wait(emu.attotime.from_msec(n)) end
local function cmd(a,b,c,d,allow_wait)
    sp:write_u16(HIRQ,0xfffe)
    sp:write_u16(CR1,a);sp:write_u16(CR2,b);sp:write_u16(CR3,c);sp:write_u16(CR4,d)
    local ready = false
    for _=1,500 do
        waitms(1)
        if (sp:read_u16(HIRQ)&1) ~= 0 then ready=true;break end
    end
    assert(ready,string.format("CMOK timeout command=%04x",a))
    local r={sp:read_u16(CR1),sp:read_u16(CR2),sp:read_u16(CR3),sp:read_u16(CR4)}
    assert((r[1]&0xff00)~=0xff00,string.format("REJECT command=%04x",a))
    if not allow_wait then eq('no WAIT '..string.format('%04x',a),r[1]&0x8000,0) end
    return r
end
local function free() return cmd(0x5000,0,0,0)[2] end
local function count(part) return cmd(0x5100,0,part<<8,0)[4] end
local function route(input,yes,no) cmd(0x4603,(yes<<8)|no,input<<8,0) end
local function finish(words)
    local r=cmd(0x0600,0,0,0)
    eq('End words',((r[1]&255)<<16)|r[2],words)
end
local function reset()
    cmd(0x48f4,0,0,0);eq('empty pool',free(),200)
end
local function bytes(seed,fid)
    local b={}
    for i=0,2351 do b[i]=(i*37+seed)&255 end
    b[0]=0;for i=1,10 do b[i]=255 end;b[11]=0
    b[12]=0;b[13]=2;b[14]=0;b[15]=2
    b[16]=fid;b[17]=0;b[18]=8;b[19]=0
    for i=0,3 do b[20+i]=b[16+i] end
    return b
end
local function pair(a,b)
    local out={};for i=0,2351 do out[i]=a[i];out[i+2352]=b[i] end;return out
end
local function word(b,i) return (b[i]<<8)|b[i+1] end
-- One leading word makes a later longword straddle the sector boundary.
-- Alternate halfword lanes as well as access widths; no mem_mask arguments.
local function writebytes(b,n)
    sp:write_u16(DATA+2,word(b,0))
    local i=2
    while i+4<=n do
        sp:write_u32(DATA,(word(b,i)<<16)|word(b,i+2));i=i+4
    end
    if i<n then sp:write_u16(DATA,word(b,i)) end
end
local function readbytes(b,n)
    eq('GET first low lane',sp:read_u16(DATA+2),word(b,0))
    local i=2
    while i+4<=n do
        eq('GET long at '..i,sp:read_u32(DATA),(word(b,i)<<16)|word(b,i+2));i=i+4
    end
    if i<n then eq('GET final high lane',sp:read_u16(DATA),word(b,i)) end
end
local function put(n) cmd(0x6400,0,0,n);eq('DRDY',sp:read_u16(HIRQ)&2,2) end
local function getdelete(part,n) cmd(0x6300,0,part<<8,n) end
local function drive_end()
    local r
    for _=1,500 do
        r=cmd(0,0,0,0)
        if (r[1]&0x0f00)==0x0100 and (sp:read_u16(HIRQ)&0x10)~=0 then return r end
        waitms(5)
    end
    error('drive did not reach PAUSE/PEND')
end
local function test()
    -- Park the SH-2s in a RAM loop, not the CD device or machine scheduler.
    sp:write_u32(0x06000000,0xaffe0009)
    for _,tag in ipairs({":maincpu",":slave"}) do
        m.devices[tag].state["SR"].value=0xf0
        m.devices[tag].state["PC"].value=0x06000000
    end
    cmd(0x0600,0,0,0) -- release any BIOS transfer; ignore undefined empty count
    cmd(0x11ff,0xffff,0,0);waitms(100)
    reset();cmd(0x6003,0x0300,0,0) -- GET and PUT views: 2352 bytes
    route(0,1,255)
    local a,b=bytes(11,7),bytes(93,8)
    local ab=pair(a,b)
    put(2)
    eq('private reservation capacity',free(),198)
    eq('private input partition',count(0),0);eq('private destination',count(1),0)
    cmd(0x4800,0,1<<8,0) -- public reset must not release private reservations
    eq('private survives public reset',free(),198)
    writebytes(ab,4704)
    eq('not published at FIFO EOF',count(1),0)
    local busy=cmd(0x6400,0,0,1,true);eq('ownership survives EOF',busy[1]&0x8000,0x8000)
    finish(2352);eq('routed to destination',count(1),2);eq('not input partition',count(0),0)
    getdelete(1,2);eq('GETDELETE detaches',count(1),0);eq('GETDELETE holds storage',free(),198)
    readbytes(ab,4704);eq('GETDELETE holds through EOF',free(),198)
    finish(2352);eq('GETDELETE End releases',free(),200)

    -- True output is partition2, false output traverses filter3 to partition3.
    cmd(0x4200,0,7,0);cmd(0x4401,0,0,0);route(0,2,3);route(3,3,255)
    put(2);writebytes(ab,4704);finish(2352)
    eq('matching file routed',count(2),1);eq('nonmatching file chain',count(3),1)
    getdelete(2,1);readbytes(a,2352);finish(1176)
    getdelete(3,1);readbytes(b,2352);finish(1176);eq('routing released',free(),200)

    -- Partial PUT routes every reservation; unwritten bytes are unspecified.
    cmd(0x4400,0,0,0);route(0,1,255);put(2);writebytes(a,64);finish(32)
    eq('partial PUT whole reservation',count(1),2)
    getdelete(1,2)
    for i=0,62,2 do eq('partial prefix '..i,sp:read_u16(DATA+(i%4)),word(a,i)) end
    finish(32);eq('unread GETDELETE released',free(),200)

    -- Full private pool, then End discards it: capacity/fullness must reflect routing.
    route(0,255,255);put(200);eq('full private pool',free(),0)
    sp:write_u16(HIRQ,0xfff7);finish(0)
    eq('discarded PUT frees pool',free(),200);eq('post-routing not full',sp:read_u16(HIRQ)&8,0)

    for mode=0,2 do
        reset();cmd(0x6000,0,0,0);route(0,1,255)
        if mode==0 then -- selector rejects every produced sector
            cmd(0x4000,300,0,1);cmd(0x4440,0,0,0);cmd(0x3000,0,0,0)
        elseif mode==1 then cmd(0x3000,0,0xff00,0) -- disconnected output
        else cmd(0x3000,0,0,0) end -- positive storage control
        sp:write_u16(HIRQ,0xffeb) -- clear PEND/CSCT before finite play
        cmd(0x1080,190,0x0080,8) -- FAD190, eight sectors, no repeat
        local r=drive_end()
        eq('drive progress '..mode,((r[3]&255)<<16)|r[4],198)
        eq('stream CSCT '..mode,sp:read_u16(HIRQ)&4,4)
        eq('produced partition count '..mode,count(1),mode==2 and 8 or 0)
        eq('produced capacity '..mode,free(),mode==2 and 192 or 200)
        if mode==2 then
            getdelete(1,8)
            eq('generated disc first word',sp:read_u16(DATA),((40*13)&255)<<8|((40*13+7)&255))
            finish(1);eq('storage control cleanup',free(),200)
        end
    end
    print('CD_HOST_RUNTIME PASS checks='..checks)
    m:exit()
end
local frames,started=0,false
emu.register_frame_done(function()
    frames=frames+1
    if started or frames<30 then return end
    started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('CD_HOST_RUNTIME FAIL '..tostring(err));m:exit() end
    end)()
end)
print('CD_HOST_RUNTIME armed')
'''


def check_result(code, text):
    if code or 'LUA ERROR' in text or MARKER + ' FAIL' in text:
        raise AssertionError(f'Runtime failure (exit {code}):\n{text}')
    if not re.search(r'^CD_HOST_RUNTIME PASS checks=\d+$', text, re.M):
        raise AssertionError(f'Missing runtime completion marker:\n{text}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
    p.add_argument('--require-runtime', action='store_true')
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if a.self_test:
        with tempfile.TemporaryDirectory() as tmp:
            build_disc(Path(tmp))
        check_result(0, 'CD_HOST_RUNTIME PASS checks=1\n')
        for code, text in [(1, 'CD_HOST_RUNTIME PASS checks=1'), (0, 'armed'),
                           (0, 'CD_HOST_RUNTIME FAIL injected'), (0, 'LUA ERROR injected')]:
            try:
                check_result(code, text)
            except AssertionError:
                continue
            raise AssertionError('runner accepted a failed/incomplete run')
        print('Host fixture generator/result-parser self-test only; no native runtime.')
        return
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
    with tempfile.TemporaryDirectory(prefix='saturn-host-') as tmp:
        directory = Path(tmp)
        cue = build_disc(directory)
        script = directory / 'host.lua'
        script.write_text(LUA)
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
        check_result(result.returncode, result.stdout)
        print('\n'.join(line for line in result.stdout.splitlines() if MARKER in line))


if __name__ == '__main__':
    main()

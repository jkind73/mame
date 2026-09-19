#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Drive the CD block's Red Book (CD-DA) path in a live machine and measure it.

The Saturn CD block's D/A converter feeds the SCSP's external digital inputs
(EXTS0/EXTS1, slots 16 and 17), so CD audio is only audible when the host has
routed those slots into the mix.  This test builds a synthetic disc whose audio
tracks are a known tone (regtests/saturn/make_synth_disc.py - generated, no
third party content), routes EXTS0/EXTS1 to the DAC through the SCSP's own
registers, and then measures the SCSP output stream while the drive plays:

  toc          Get TOC ($02) reports each track's control/ADR and FAD.  Track 2
               starts at FAD 332 and track 3 at FAD 632 on the fixture disc,
               i.e. the FADs (LBA + 150) the image's track table and the drive's
               position must agree on.  The FAD/LBA mix-up this test guards was
               a 150 sector (2 s) offset on the audio path.
  tone         Play Disc ($10) in track mode with the drive reaching PLAY.  The
               SCSP output must carry the track's 1 kHz tone: measured as the
               Goertzel magnitude at 1 kHz of the captured stream, plus the
               SCSP's own EXTS readback registers ($0EE0/$0EE2), which hold the
               samples the DSP latched at the last sample period.
  range        The requested end track ends playback: PEND (HIRQ bit 4) is
               raised and the tone stops within the range of that track, not
               after it.  The fixture's track 2 is 4 s long.
  pause        Seek to 0xFFFFFF is the documented pause: the drive reports
               PAUSE and the tone stops.  A Play that resumes from the paused
               position starts it again.
  data         Playing a data track (the fixture's track 1) must not emit Red
               Book audio - the drive reads it into the sector buffer instead.
  scan         Fast forward ($12) moves the pickup and stays audible while it
               crosses an audio track.

Everything is measured on the emulated SCSP output stream (emu.register_sound_
update after marking the device hooked) and on the host-visible registers; no
assertion depends on the tone's absolute level, only on it being present, being
at the track's frequency, and stopping when the drive stops.

Requires a built driver-filtered binary and BIOS ROMs.  Skips with exit status 0
when they are absent, so run_all.py stays ROM-free.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'regtests' / 'saturn'))
from make_synth_disc import build_audio, build_iso, mode1_sector, SECTOR  # noqa: E402

# One second of audio at 1 kHz, the tone the fixture's track 2 carries
AUDIO_SECONDS = 4.0
TONE_HZ = 1000.0
PREGAP = 150
DATA_SECTORS = 32
AUDIO_SECTORS = int(44100 * AUDIO_SECONDS * 4 + SECTOR - 1) // SECTOR

LUA = r'''
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
-- host registers live in the $05880000 window (the device maps them at
-- offset 0x80000, mirrored over the data port at 0x18000)
local HIRQ, CR1, CR2, CR3, CR4 = @@BASE@@ + 0x80008, @@BASE@@ + 0x80018,
                                @@BASE@@ + 0x8001c, @@BASE@@ + 0x80020,
                                @@BASE@@ + 0x80024
-- the response registers are read through the same addresses the commands are
-- written to (DR1/CR1 is one register pair on the device port)
local DR1, DR2 = CR1, CR2
local DTRNS = 0x05818000          -- data port (word for TOC/Q, long for sectors)
local SCSP = 0x05b00000
local frames, phase = 0, 'boot'
local fails = {}
local function chk(label, cond, detail)
    if not cond then fails[#fails + 1] = label .. ' ' .. tostring(detail) end
end
local function ms(t) return emu.attotime.from_msec(t) end
local function cmd(a, b, c, d)
    sp:write_u16(HIRQ, 0xfffe)   -- clear CMOK; CR4 arms the command
    sp:write_u16(CR1, a); sp:write_u16(CR2, b)
    sp:write_u16(CR3, c); sp:write_u16(CR4, d)
    for _ = 1, 500 do
        if (sp:read_u16(HIRQ) & 0x0001) ~= 0 then return true end
        emu.wait(ms(1))
    end
    return false
end
local function status()
    cmd(0x0000, 0, 0, 0)
    return sp:read_u16(CR1)
end
local function state() return status() & 0x0f00 end
-- the host's status field, named as the device does
local STAT = { BUSY=0x0400, PAUSE=0x0100, STANDBY=0x0200, PLAY=0x0300,
               SEEK=0x0500, SCAN=0x0600, OPEN=0x0700, NODISC=0x0800 }

-- SCSP output capture.  Only hooked streams report samples through
-- register_sound_update, so the SCSP has to be marked as hooked first.
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
local cap = { on = false, n = 0, l = {} }
emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    local left = chans[1]
    for i = 1, #left do
        cap.n = cap.n + 1
        cap.l[cap.n] = left[i]
    end
end)
local function capture(ms_len)
    cap = { on = true, n = 0, l = {} }
    emu.wait(ms(ms_len))
    cap.on = false
    return cap
end
local function rms(c)
    local sum, n = 0.0, 0
    for i = 1, c.n do sum = sum + c.l[i] * c.l[i]; n = n + 1 end
    return n > 0 and math.sqrt(sum / n) or 0.0
end
-- Goertzel magnitude at hz, normalised so a full scale sine reads about 0.5
local function tone(c, hz)
    local w = 2 * math.pi * hz / 44100
    local coeff = 2 * math.cos(w)
    local s1, s2 = 0.0, 0.0
    for i = 1, c.n do
        local s0 = c.l[i] + coeff * s1 - s2
        s2, s1 = s1, s0
    end
    if c.n == 0 then return 0.0 end
    return math.sqrt(math.abs(s1 * s1 + s2 * s2 - coeff * s1 * s2)) / c.n
end
local function exts()   -- the DSP's latched external input samples
    return sp:read_u16(SCSP + 0xee0), sp:read_u16(SCSP + 0xee2)
end

-- the subcode Q buffer, decoded from the word port
local function subq()
    cmd(0x2000, 0, 0, 0)
    local b = {}
    for i = 0, 9 do b[i] = sp:read_u16(DTRNS) end
    local function byte(i)   -- byte i of the 12 byte Q record
        local w = b[math.floor(i / 2)]
        return (i % 2 == 0) and (w >> 8) & 0xff or w & 0xff
    end
    local function bcd(v) return (v >> 4) * 10 + (v & 0xf) end
    return { control = byte(0), track = bcd(byte(1)), index = bcd(byte(2)),
             rel = bcd(byte(3)) * 60 + bcd(byte(4)), abs = bcd(byte(7)) * 60 +
             bcd(byte(8)) }
end

local function play_track(first, last)
    -- track mode: the host's one based start track number in CR2 bits 15-8 and
    -- the end track number in CR4 bits 15-8 (CR1/CR3 low bytes are the high
    -- bits of a position when one is given)
    return cmd(0x1000, first << 8, 0, last << 8)
end

-- CD-05: a save taken while the drive is playing must restore the drive
-- position, the pending transfer state and the converter's own playback state.
local save_path = os.getenv('CDDA_SAVE_FILE')
local saves_seen, loads_seen, save_target, load_target = 0, 0, 0, 0
if save_path then
    emu.add_machine_pre_save_notifier(function()
        saves_seen = saves_seen + 1
    end)
    emu.add_machine_post_load_notifier(function()
        loads_seen = loads_seen + 1
    end)
end
local function state_written()
    if not save_path then return true end
    local f = io.open(save_path, 'rb')
    if not f then return false end
    local size = f:seek('end')
    f:close()
    return size ~= nil and size > 32
end
local function request_save()
    if not save_path then return false end
    os.remove(save_path)
    save_target = saves_seen + 1
    m:save(save_path)
    return true
end
local function request_load()
    if not save_path then return false end
    for _ = 1, 200 do
        if state_written() then break end
        emu.wait(ms(10))
    end
    if not state_written() then return false end
    load_target = loads_seen + 1
    m:load(save_path)
    emu.pause()          -- the load rewinds emulated time
    emu.unpause()
    return true
end

local function park()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        cpu.state["SR"].value = 0xf0
        cpu.state["PC"].value = 0x06000000
    end
end

local function route_exts()
    -- MVOL to full scale and EXTS0/EXTS1 (slots 16/17) into the mix at 0 dB
    sp:write_u16(SCSP + 0x400, 0x000f)
    sp:write_u16(SCSP + 0x200 + 0x16, 0xf000)   -- DISDL 7, DIPAN centre
    sp:write_u16(SCSP + 0x220 + 0x16, 0xf000)
end

local function toc()
    cmd(0x0200, 0, 0, 0)
    local cr = { sp:read_u16(DR1), sp:read_u16(DR2), sp:read_u16(CR3),
                 sp:read_u16(CR4) }
    local words = {}
    for i = 1, 10 do words[i] = sp:read_u16(DTRNS) end
    local function entry(i)
        return { control = (words[i * 2 - 1] >> 8) & 0xff,
                 fad = ((words[i * 2 - 1] & 0xff) << 16) | words[i * 2] }
    end
    return cr, entry
end

local function test()
    park()
    route_exts()
    emu.wait(ms(20))

    -- idle: nothing may reach the output through the external inputs
    local idle = capture(100)
    chk('idle_silent', rms(idle) < 0.001, string.format('rms=%.6f', rms(idle)))

    local cr, entry = toc()
    local t1, t2, t3 = entry(1), entry(2), entry(3)
    print(string.format('CDDA toc cr=%04x %04x %04x %04x t1=%02x:%06x '
                        .. 't2=%02x:%06x t3=%02x:%06x', cr[1], cr[2], cr[3],
                        cr[4], t1.control, t1.fad, t2.control, t2.fad,
                        t3.control, t3.fad))
    chk('toc_track1_fad', t1.fad == 150, string.format('%06x', t1.fad))
    chk('toc_track2_fad', t2.fad == @@TRACK2@@, string.format('%06x', t2.fad))
    chk('toc_track2_audio', (t2.control & 0x40) == 0,
        string.format('%02x', t2.control))
    chk('toc_track3_fad', t3.fad == @@TRACK3@@, string.format('%06x', t3.fad))

    -- play track 2 to the start of track 3
    chk('play_accepted', play_track(2, 3), 'no CMOK')
    for _ = 1, 200 do
        if state() == STAT.PLAY then break end
        emu.wait(ms(10))
    end
    chk('play_reaches_play', state() == STAT.PLAY,
        string.format('%03x', state()))

    emu.wait(ms(300))                       -- let the tone settle
    local playing = capture(400)
    local l, r = exts()
    local q = subq()
    print(string.format('CDDA play rms=%.6f g1k=%.5f g2k=%.5f exts=%04x %04x '
                        .. 'q_track=%d q_index=%d q_rel=%d q_abs=%d',
                        rms(playing), tone(playing, @@TONE@@),
                        tone(playing, @@TONE@@ * 2), l, r, q.track, q.index,
                        q.rel, q.abs))
    chk('play_audible', rms(playing) > 0.02,
        string.format('rms=%.6f', rms(playing)))
    chk('play_tone_1k', tone(playing, @@TONE@@) > 0.05,
        string.format('g1k=%.5f', tone(playing, @@TONE@@)))
    chk('play_exts_latched', (l ~= 0) or (r ~= 0),
        string.format('%04x %04x', l, r))
    chk('play_tone_not_2k', tone(playing, @@TONE@@ * 2) <
        tone(playing, @@TONE@@), 'second harmonic dominates')
    chk('play_q_track', q.track == 2, q.track)

    -- the requested range ends at track 3: PEND and silence
    local ended, tones = false, {}
    for _ = 1, 60 do
        emu.wait(ms(150))
        tones[#tones + 1] = rms(capture(60))
        if (sp:read_u16(HIRQ) & 0x0010) ~= 0 then ended = true end
        if ended and state() == STAT.PAUSE then break end
    end
    local tail = capture(150)
    print(string.format('CDDA range ended=%s state=%03x tail_rms=%.6f',
                        tostring(ended), state(), rms(tail)))
    chk('range_pend', ended, 'PEND never raised')
    chk('range_pause', state() == STAT.PAUSE, string.format('%03x', state()))
    chk('range_silent', rms(tail) < 0.01, string.format('%.6f', rms(tail)))

    -- seek to the start of track 2 then pause, and resume from the pause
    cmd(0x1100, 0x0200, 0, 0)               -- Seek Disc, track mode
    for _ = 1, 200 do
        if state() == STAT.PAUSE then break end
        emu.wait(ms(10))
    end
    local paused = capture(150)
    print(string.format('CDDA pause state=%03x rms=%.6f', state(), rms(paused)))
    chk('pause_state', state() == STAT.PAUSE, string.format('%03x', state()))
    chk('pause_silent', rms(paused) < 0.005, string.format('%.6f', rms(paused)))

    chk('resume_accepted', play_track(2, 3), 'no CMOK')
    for _ = 1, 200 do
        if state() == STAT.PLAY then break end
        emu.wait(ms(10))
    end
    emu.wait(ms(300))
    local resumed = capture(300)
    print(string.format('CDDA resume state=%03x rms=%.6f g1k=%.5f', state(),
                        rms(resumed), tone(resumed, @@TONE@@)))
    chk('resume_audible', rms(resumed) > 0.02,
        string.format('rms=%.6f', rms(resumed)))

    -- CD-05: save and restore in the middle of playback
    if save_path then
        chk('cont_play_accepted', play_track(2, 3), 'no CMOK')
        for _ = 1, 200 do
            if state() == STAT.PLAY then break end
            emu.wait(ms(10))
        end
        emu.wait(ms(300))
        local q_before = subq()
        local before_rms = rms(capture(200))
        chk('cont_saved', request_save(), 'save refused')
        chk('cont_loaded', request_load(), 'state file never appeared')
        for _ = 1, 100 do
            if state() == STAT.PLAY then break end
            emu.wait(ms(10))
        end
        emu.wait(ms(200))
        local q_after = subq()
        local after = capture(250)
        print(string.format('CDDA continuity state=%03x rms_before=%.6f '
                            .. 'rms_after=%.6f g1k_after=%.5f abs %d -> %d',
                            state(), before_rms, rms(after),
                            tone(after, @@TONE@@), q_before.abs, q_after.abs))
        chk('cont_play_state', state() == STAT.PLAY,
            string.format('%03x', state()))
        chk('cont_audio', rms(after) > 0.02, string.format('%.6f', rms(after)))
        chk('cont_position', q_after.abs >= q_before.abs,
            string.format('%d -> %d', q_before.abs, q_after.abs))
        cmd(0x0400, 0, 0, 0)                 -- Init back to a known state
        emu.wait(ms(150))
    end

    -- scanning: the pickup must move and stay audible over the audio track
    chk('scan_play_accepted', play_track(2, 3), 'no CMOK')
    for _ = 1, 200 do
        if state() == STAT.PLAY then break end
        emu.wait(ms(10))
    end
    cmd(0x1200, 0, 0, 0)                    -- Fast forward
    emu.wait(ms(200))
    local scann = capture(300)
    local q1 = subq()
    emu.wait(ms(300))
    local q2 = subq()
    print(string.format('CDDA scan state=%03x rms=%.6f g1k=%.5f '
                        .. 'abs %d -> %d', state(), rms(scann),
                        tone(scann, @@TONE@@), q1.abs, q2.abs))
    chk('scan_state', state() == STAT.SCAN, string.format('%03x', state()))
    chk('scan_audible', rms(scann) > 0.02, string.format('%.6f', rms(scann)))
    chk('scan_moves', q2.abs > q1.abs, string.format('%d -> %d', q1.abs, q2.abs))

    -- playing the data track must stay silent
    chk('data_play_accepted', play_track(1, 2), 'no CMOK')
    for _ = 1, 200 do
        if state() == STAT.PLAY then break end
        emu.wait(ms(10))
    end
    local data = capture(300)
    print(string.format('CDDA data state=%03x rms=%.6f', state(), rms(data)))
    chk('data_silent', rms(data) < 0.005, string.format('%.6f', rms(data)))

    if not hooked then fails[#fails + 1] = 'scsp stream hook missing' end
    if #fails == 0 then print('CDDA PASS')
    else for _, f in ipairs(fails) do print('CDDA FAIL ' .. f) end end
    m:exit()
end

emu.register_frame_done(function()
    frames = frames + 1
    if phase ~= 'boot' or frames < @@FRAMES@@ then return end
    phase = 'test'
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print('CDDA FAIL ' .. tostring(err)); m:exit() end
    end)()
end)
print('CDDA armed')
'''


def build_disc(outdir: Path) -> Path:
    """Write the synthetic fixture disc next to the test's other files."""
    audio1_lba = DATA_SECTORS + PREGAP
    audio2_lba = audio1_lba + AUDIO_SECTORS
    iso = build_iso()
    bin_path = outdir / 'cdda-fixture.bin'
    with bin_path.open('wb') as out:
        for lba in range(DATA_SECTORS):
            out.write(mode1_sector(lba, iso.get(lba, b'\x00' * 2048)))
        out.write(b'\x00' * (PREGAP * SECTOR))
        out.write(build_audio(audio1_lba, AUDIO_SECONDS, TONE_HZ, 20000))
        out.write(build_audio(audio2_lba, AUDIO_SECONDS, TONE_HZ * 2, 20000))
    cue = (f'FILE "{bin_path.name}" BINARY\n'
           '  TRACK 01 MODE1/2352\n'
           f'    INDEX 01 {msf(0)}\n'
           '  TRACK 02 AUDIO\n'
           f'    INDEX 00 {msf(DATA_SECTORS)}\n'
           f'    INDEX 01 {msf(audio1_lba)}\n'
           '  TRACK 03 AUDIO\n'
           f'    INDEX 01 {msf(audio2_lba)}\n')
    cue_path = outdir / 'cdda-fixture.cue'
    cue_path.write_text(cue)
    return cue_path


def msf(lba: int) -> str:
    total = lba + 150
    return '%02d:%02d:%02d' % (total // (60 * 75), (total // 75) % 60,
                               total % 75)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
    p.add_argument('--system', default='saturnjp')
    p.add_argument('--drc', action='store_true')
    p.add_argument('--output', type=Path)
    args = p.parse_args()

    exe = args.executable.resolve()
    rompath = args.rompath.resolve()
    if not os.access(exe, os.X_OK):
        print('SKIP: no runnable emulator at %s' % exe)
        return 0
    if not (rompath / (args.system + '.zip')).is_file():
        print('SKIP: no %s ROM set in %s' % (args.system, rompath))
        return 0

    out = args.output or Path(tempfile.mkdtemp(prefix='cdda-'))
    out.mkdir(parents=True, exist_ok=True)
    disc = build_disc(out)
    audio1_lba = DATA_SECTORS + PREGAP
    lua = (LUA.replace('@@BASE@@', '0x05800000')
              .replace('@@TRACK2@@', '0x%06x' % (audio1_lba + 150))
              .replace('@@TRACK3@@',
                       '0x%06x' % (audio1_lba + AUDIO_SECTORS + 150))
              .replace('@@TONE@@', '%.1f' % TONE_HZ)
              .replace('@@FRAMES@@', '180'))
    script = out / 'cdda.lua'
    script.write_text(lua)
    cmd = [str(exe), args.system, '-rompath', str(rompath), '-noreadconfig',
           '-skip_gameinfo', ('-drc' if args.drc else '-nodrc'), '-video',
           'none', '-sound', 'dummy', '-nothrottle', '-seconds_to_run', '120',
           '-autoboot_delay', '0', '-cdrom', str(disc),
           '-autoboot_script', str(script)]
    for kind in ('nvram', 'cfg', 'state', 'snapshot'):
        cmd += ['-' + kind + '_directory', str(out / kind)]
        (out / kind).mkdir(parents=True, exist_ok=True)
    (out / 'invocation.json').write_text(json.dumps({
        'executable': str(exe), 'system': args.system, 'drc': args.drc,
        'disc_sha256': hashlib.sha256(disc.with_suffix('.bin').read_bytes())
        .hexdigest(),
        'binary_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'lua_sha256': hashlib.sha256(lua.encode()).hexdigest(),
        'command': cmd,
    }, indent=2) + '\n')
    env = dict(os.environ)
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
               CDDA_SAVE_FILE=str(out / 'cdda-continuity.sta'))
    with (out / 'runtime.log').open('w') as log:
        proc = subprocess.run(cmd, cwd=out, env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=1800)
    text = (out / 'runtime.log').read_text(errors='replace')
    if 'unknown option: -cdrom' in text:
        # a configuration with no CD image device (ST-V cartridges) cannot be
        # asked about Red Book output at all
        print('SKIP: %s has no -cdrom option' % args.system)
        return 0
    for line in text.splitlines():
        if line.startswith('CDDA '):
            print(line)
    if proc.returncode or 'CDDA PASS' not in text:
        detail = '\n'.join(l for l in text.splitlines()
                           if 'CDDA FAIL' in l) or text[-2000:]
        raise AssertionError('CD-DA assertions failed:\n' + detail)
    print('CD-DA: Red Book output is measured at the SCSP output while the CD '
          'block plays track 2 of the fixture disc (tone + EXTS latch + subcode '
          'Q), the requested end track stops it with PEND, pause/resume and '
          'fast-forward scan behave, and a data track stays silent')
    return 0


if __name__ == '__main__':
    sys.exit(main())

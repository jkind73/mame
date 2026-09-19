#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP LFO amplitude/phase-modulation measurement via the sound hook.

Drives one SCSP slot with a constant (DC) carrier and measures the amplitude
envelope the slot ALFO applies, plus a sine carrier to measure the pitch swing
the PLFO applies. The SCSP output stream is captured from Lua through the
per-device sound hook, so this observes the real mixer values without any OSD
audio device or private state patching.

Covers Table 4.21 (printed p.89) for all 32 LFOF settings, the LFORE reset
hold (p.89, with the p.37 noise-waveform exemption) and the depth-0 behaviour.
Missing binary/BIOS is a skip, never a native pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

# Table 4.21 (printed p.89) oscillation frequencies, straight from the manual.
LFOFREQ = [0.17, 0.19, 0.23, 0.27, 0.34, 0.39, 0.45, 0.55,
           0.68, 0.78, 0.92, 1.10, 1.39, 1.60, 1.87, 2.27,
           2.87, 3.31, 3.92, 4.79, 6.15, 7.18, 8.60, 10.8,
           14.4, 17.2, 21.5, 28.7, 43.1, 57.4, 86.1, 172.3]

LUA = COMMON_LUA + r'''
local FREQ = {0.17,0.19,0.23,0.27,0.34,0.39,0.45,0.55,0.68,0.78,0.92,1.10,
1.39,1.60,1.87,2.27,2.87,3.31,3.92,4.79,6.15,7.18,8.60,10.8,
14.4,17.2,21.5,28.7,43.1,57.4,86.1,172.3}
local base = 0x05b00000
local s0 = base
local s1 = base + 0x20
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_LFO hooked=" .. tostring(hooked))

local cap = {}
local function begin_capture(thr, win_samples)
    cap = { on = true, n = 0, sum = 0.0, min = 1e9, max = -1e9, rough = 0.0,
            prev = nil, trans = {}, thr = thr, above = nil,
            win_samples = win_samples, win = {}, wincount = 0, winnext = win_samples or 0, last = nil }
end

emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    local buf = chans[1]
    for i = 1, #buf do
        local v = buf[i]
        cap.n = cap.n + 1
        cap.sum = cap.sum + v
        if v < cap.min then cap.min = v end
        if v > cap.max then cap.max = v end
        if cap.prev then
            local d = v - cap.prev
            cap.rough = cap.rough + (d < 0 and -d or d)
        end
        cap.prev = v
        if cap.thr then
            local above = (v > cap.thr) and 1 or 0
            if cap.above ~= nil and above ~= cap.above then
                if #cap.trans < 400 then cap.trans[#cap.trans + 1] = cap.n end
            end
            cap.above = above
        end
        if cap.win_samples then
            local s = (v >= 0) and 1 or 0
            if cap.last ~= nil and s ~= cap.last then cap.wincount = cap.wincount + 1 end
            cap.last = s
            while cap.n >= cap.winnext do
                cap.win[#cap.win + 1] = cap.wincount
                cap.wincount = 0
                cap.winnext = cap.winnext + cap.win_samples
            end
        end
    end
end)

local function end_capture(kind)
    cap.on = false
    local mean = cap.n > 0 and (cap.sum / cap.n) or 0.0
    local rough = cap.n > 1 and (cap.rough / (cap.n - 1)) or 0.0
    local ts = {}
    for i = 1, #cap.trans do ts[#ts + 1] = tostring(cap.trans[i]) end
    local w = {}
    for i = 1, #cap.win do w[#w + 1] = tostring(cap.win[i]) end
    print(string.format("SCSP_LFO %s n=%d min=%.6f max=%.6f mean=%.6f rough=%.6f trans=%d t=[%s] w=[%s]",
        kind, cap.n, cap.min, cap.max, mean, rough, #cap.trans, table.concat(ts, ","), table.concat(w, ",")))
    return mean
end

local function test()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        cpu.state["SR"].value = 0xf0
        cpu.state["PC"].value = 0x06000000
    end
    local snd = assert(m.devices[":audiocpu"])
    local ss = snd.spaces["program"]
    ss:write_u16(0x70000, 0x60fe)
    snd.state["SR"].value = 0x2700
    snd.state["PC"].value = 0x70000

    sp:write_u16(base + 0x400, 0x000f)
    for i = 0, 63 do ss:write_u8(0x1000 + i, 0x40) end        -- DC carrier (slot 0)
    for i = 0, 63 do                                          -- sine carrier (slot 1)
        ss:write_u8(0x2000 + i, math.floor(127 * math.sin(2 * math.pi * i / 64)))
    end
    -- slot 0: DC, forward loop, EGHOLD, DISDL=7
    sp:write_u16(s0 + 0x00, 0x0830)
    sp:write_u16(s0 + 0x02, 0x1000)
    sp:write_u16(s0 + 0x04, 0x0000)
    sp:write_u16(s0 + 0x06, 0x003f)
    sp:write_u16(s0 + 0x08, 0x0020)
    sp:write_u16(s0 + 0x0a, 0x0000)
    sp:write_u16(s0 + 0x0c, 0x0200)
    sp:write_u16(s0 + 0x0e, 0x0000)
    sp:write_u16(s0 + 0x10, 0x0000)
    sp:write_u16(s0 + 0x12, 0x0000)
    sp:write_u16(s0 + 0x14, 0x0000)
    sp:write_u16(s0 + 0x16, 0xe000)
    sp:write_u16(s0 + 0x00, 0x1830)
    -- slot 1: sine, forward loop, EGHOLD, DISDL=7, initially muted
    sp:write_u16(s1 + 0x00, 0x0830)
    sp:write_u16(s1 + 0x02, 0x2000)
    sp:write_u16(s1 + 0x04, 0x0000)
    sp:write_u16(s1 + 0x06, 0x003f)
    sp:write_u16(s1 + 0x08, 0x0020)
    sp:write_u16(s1 + 0x0a, 0x0000)
    sp:write_u16(s1 + 0x0c, 0x0200)
    sp:write_u16(s1 + 0x0e, 0x0000)
    sp:write_u16(s1 + 0x10, 0x0000)
    sp:write_u16(s1 + 0x12, 0x0000)
    sp:write_u16(s1 + 0x14, 0x0000)
    sp:write_u16(s1 + 0x16, 0xe000)

    emu.wait(emu.attotime.from_msec(20))
    begin_capture(nil)
    emu.wait(emu.attotime.from_msec(100))
    local loud = end_capture("calibrate")
    if loud <= 0.0 then print("SCSP_LFO FAIL no-audio"); m:exit(); return end
    local rate = cap.n / 0.100
    local thr = loud * 0.3

    -- Amplitude LFO: square, depth 7, every Table 4.21 rate.
    for lfof = 0, 31 do
        local reg = (lfof << 10) | (1 << 3) | 7
        local dur = math.max(300, math.ceil(1300 / FREQ[lfof + 1]))
        sp:write_u16(s0 + 0x12, reg | 0x8000)
        emu.wait(emu.attotime.from_msec(2))
        sp:write_u16(s0 + 0x12, reg)
        emu.wait(emu.attotime.from_msec(150))
        begin_capture(thr)
        emu.wait(emu.attotime.from_msec(dur))
        end_capture("amp lfof=" .. lfof)
    end

    -- LFORE hold: square and saw both report their reset phase (index 0 = quiet).
    for _, spec in ipairs({ {"hold_sq", (0x1f << 10) | (1 << 3) | 7},
                            {"hold_saw", (0x0b << 10) | (0 << 3) | 7} }) do
        sp:write_u16(s0 + 0x12, spec[2] | 0x8000)
        emu.wait(emu.attotime.from_msec(150))
        begin_capture(thr)
        emu.wait(emu.attotime.from_msec(300))
        end_capture(spec[1])
    end

    -- Noise waveform is exempt from LFORE (p.37): it keeps fluctuating.
    for _, spec in ipairs({ {"noise_hold", 0x8000 | (0x1f << 10) | (3 << 3) | 7},
                            {"noise_run", (0x1f << 10) | (3 << 3) | 7} }) do
        sp:write_u16(s0 + 0x12, spec[2])
        emu.wait(emu.attotime.from_msec(150))
        begin_capture(thr)
        emu.wait(emu.attotime.from_msec(300))
        end_capture(spec[1])
    end

    -- Depth 0: no modulation at all, constant full level.
    sp:write_u16(s0 + 0x12, (0x1f << 10) | (1 << 3) | 0)
    emu.wait(emu.attotime.from_msec(150))
    begin_capture(thr)
    emu.wait(emu.attotime.from_msec(300))
    end_capture("depth0")

    -- Phase LFO: sine carrier, square PLFO depth 7 (494 cents). Mute slot 0 so
    -- the pitch swing is measured on a zero-centred tone, then key slot 1 on.
    sp:write_u16(s0 + 0x16, 0x0000)
    sp:write_u16(s1 + 0x16, 0xe000)
    sp:write_u16(s1 + 0x00, 0x1830)
    for _, spec in ipairs({ {0, 3}, {7, 4} }) do
        local lfof, periods = spec[1], spec[2]
        local reg = (lfof << 10) | (1 << 8) | (7 << 5)   -- PLFOWS=square, PLFOS=7
        local dur = math.ceil(1000 * periods / FREQ[lfof + 1]) + 500
        sp:write_u16(s1 + 0x12, reg | 0x8000)
        emu.wait(emu.attotime.from_msec(2))
        sp:write_u16(s1 + 0x12, reg)
        emu.wait(emu.attotime.from_msec(150))
        begin_capture(nil, math.floor(rate / 10 + 0.5))
        emu.wait(emu.attotime.from_msec(dur))
        end_capture("pitch lfof=" .. lfof)
    end
    print("SCSP_LFO rate=" .. string.format("%.1f", rate) .. " loud=" .. string.format("%.6f", loud))
    print("SCSP_LFO done")
    m:exit()
end

local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_LFO FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_LFO armed")
'''


def _parse(text):
    rows = []
    for m in re.finditer(r'^SCSP_LFO (\S.*)$', text, re.M):
        rows.append(m.group(1))
    return rows


def _case(rows, prefix):
    for r in rows:
        if r.startswith(prefix + ' '):
            return r
    raise RuntimeError('missing SCSP_LFO case ' + prefix)


def _field(row, name):
    m = re.search(r'\b' + name + r'=([^ ]+)', row)
    if not m:
        raise RuntimeError('missing field ' + name + ' in: ' + row)
    return m.group(1)


def _floats(row, name):
    m = re.search(r'\b' + name + r'=\[([^\]]*)\]', row)
    if not m or not m.group(1):
        return []
    return [float(x) for x in m.group(1).split(',')]


def validate_output(text, returncode):
    if returncode or 'SCSP_LFO FAIL' in text or 'LUA ERROR' in text:
        raise RuntimeError('SCSP LFO fixture failed:\n' + text[-16000:])
    rows = _parse(text)
    if len([r for r in rows if r == 'done']) != 1:
        raise RuntimeError('SCSP LFO transcript incomplete:\n' + text[-16000:])

    cal = _case(rows, 'calibrate')
    n = int(_field(cal, 'n'))
    loud = float(_field(cal, 'mean'))
    rate = n / 0.100
    if not (1000 < rate < 100000):
        raise RuntimeError('implausible SCSP rate ' + str(rate))
    # the DC carrier must produce a flat, non-zero calibration
    if not (abs(float(_field(cal, 'min')) - loud) < 1e-6 and
            abs(float(_field(cal, 'max')) - loud) < 1e-6 and loud > 0.05):
        raise RuntimeError('calibration not a flat DC level: ' + cal)

    def measured_hz(row):
        t = _floats(row, 't')
        if len(t) < 2:
            return 0.0, 0
        return rate * (len(t) - 1) / (2.0 * (t[-1] - t[0])), len(t)

    checked = 0
    # Amplitude sweep: every Table 4.21 rate must oscillate within 1% of the
    # quantized step and 2% of the printed manual value.
    for lfof, manual in enumerate(LFOFREQ):
        row = _case(rows, 'amp lfof=%d' % lfof)
        hz, trans = measured_hz(row)
        step = round(manual * 4294967296.0 / rate)
        expected = rate * step / 4294967296.0
        if trans < 2 or hz <= 0:
            raise RuntimeError('no modulation at lfof=%d: %s' % (lfof, row))
        if abs(hz - expected) / expected > 0.01:
            raise RuntimeError('lfof=%d measured %.4f Hz vs quantized %.4f Hz: %s'
                               % (lfof, hz, expected, row))
        if abs(hz - manual) / manual > 0.02:
            raise RuntimeError('lfof=%d measured %.4f Hz vs manual %.3f Hz: %s'
                               % (lfof, hz, manual, row))
        checked += 1

    # LFORE hold: held at the reset phase, a flat quiet level (index 0).
    for name in ('hold_sq', 'hold_saw'):
        row = _case(rows, name)
        lo, hi = float(_field(row, 'min')), float(_field(row, 'max'))
        if _floats(row, 't') or abs(lo - hi) > 1e-6:
            raise RuntimeError('LFORE hold %s not constant: %s' % (name, row))
        ratio = loud / lo
        if not (15.0 <= ratio <= 17.0):       # -24 dB attenuation of depth 7
            raise RuntimeError('LFORE hold %s not at reset level (ratio %.2f): %s'
                               % (name, ratio, row))
        checked += 1

    # Noise exemption: LFORE does not stop the noise-waveform LFO.
    for name in ('noise_hold', 'noise_run'):
        row = _case(rows, name)
        lo, hi = float(_field(row, 'min')), float(_field(row, 'max'))
        if not (hi > 0.8 * loud and lo < 0.4 * loud):
            raise RuntimeError('noise %s did not fluctuate: %s' % (name, row))
        checked += 1

    # Depth 0: constant full level, no modulation.
    row = _case(rows, 'depth0')
    lo, hi = float(_field(row, 'min')), float(_field(row, 'max'))
    if _floats(row, 't') or abs(lo - hi) > 1e-6 or abs(lo - loud) > 0.02:
        raise RuntimeError('depth0 not constant full level: ' + row)
    checked += 1

    # Phase LFO: the pitch swing alternates between the depth-7 extremes
    # (~-494 and ~+494 cents around the carrier), so per-window zero-crossing
    # counts step between two bands at the LFO rate. The two bands are a fixed
    # ratio apart, so classify relative to the median (rate independent).
    for lfof in (0, 7):
        row = _case(rows, 'pitch lfof=%d' % lfof)
        counts = _floats(row, 'w')
        if len(counts) < 6:
            raise RuntimeError('pitch lfof=%d too few windows: %s' % (lfof, row))
        manual = LFOFREQ[lfof]
        step = round(manual * 4294967296.0 / rate)
        expected = rate * step / 4294967296.0
        lo, hi = min(counts[1:-1]), max(counts[1:-1])
        mid = (lo + hi) / 2.0
        state = None
        edges = []
        for i, c in enumerate(counts):
            cls = 'H' if c > mid else 'L'
            if state is not None and cls != state:
                edges.append(i)
            state = cls
        if len(edges) < 2 or (hi - lo) < 0.3 * hi:
            raise RuntimeError('pitch lfof=%d no PLFO alternation: %s' % (lfof, row))
        span_windows = edges[-1] - edges[0]        # each window is 100 ms
        hz = (len(edges) - 1) / (2.0 * span_windows * 0.1)
        if abs(hz - expected) / expected > 0.03:
            raise RuntimeError('pitch lfof=%d measured %.4f Hz vs %.4f Hz: %s'
                               % (lfof, hz, expected, row))
        checked += 1

    return checked


def main(success_message=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--system', choices=('saturnjp', 'saturneu', 'stvbios'), default='saturnjp')
    p.add_argument('--drc', action='store_true')
    a = p.parse_args()
    exe = a.executable.resolve()
    rom = a.rompath.resolve()
    output = a.output.resolve()
    if not exe.is_file() or not (rom / (a.system + '.zip')).is_file():
        print('SKIP: need native binary and ' + a.system + ' BIOS')
        return
    output.mkdir(parents=True, exist_ok=True)
    (output / 'invocation.json').write_text(json.dumps({
        'system': a.system, 'engine': 'drc' if a.drc else 'interpreter',
        'binary_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'bios_sha256': hashlib.sha256((rom / (a.system + '.zip')).read_bytes()).hexdigest(),
        'lua_sha256': hashlib.sha256(LUA.encode()).hexdigest(),
    }, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='scsp-lfo-live-') as tmp:
        d = Path(tmp)
        script = d / 'test.lua'
        script.write_text(LUA)
        command = [str(exe), a.system, '-rompath', str(rom), '-noreadconfig', '-skip_gameinfo',
                   ('-drc' if a.drc else '-nodrc'), '-video', 'none', '-sound', 'none',
                   '-nothrottle', '-seconds_to_run', '360',
                   '-autoboot_delay', '0', '-autoboot_script', str(script)]
        for kind, folder in [('nvram', 'nvram'), ('cfg', 'cfg'), ('state', 'sta'), ('snapshot', 'snap')]:
            command += ['-' + kind + '_directory', str(d / folder)]
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        with (output / 'runtime.log').open('w') as log:
            result = subprocess.run(command, cwd=d, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=600)
        text = (output / 'runtime.log').read_text(errors='replace')
    checked = validate_output(text, result.returncode)
    print(success_message or ('SCSP LFO: %d native amplitude/phase-modulation cases passed live' % checked))


if __name__ == '__main__':
    main()

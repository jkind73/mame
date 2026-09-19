#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP sound-state continuity across a scheduled save/load.

SND-05 asks that a save/load taken while sound generation is *moving* leaves no
lost or duplicated interrupt and no discontinuity caused by unsaved state.  This
fixture measures the parts a save can catch mid-flight, each with a poison step
written between the save and the load that proves the load wins over the live
state.  Only SH-2 register accesses and the sound stream hook are used, and the
sound CPU stays in reset, so every observed change is the SCSP's own state.

  env   an envelope in slow decay when the save happens.  The level measured
        after the load must continue the saved decay (within the decay itself),
        not restart it: a slot whose EG level/state is not saved jumps back to
        full scale or to the attack start.  Poison: a fast decay is programmed
        while the state is saved.
  wave  a 4096 sample staircase ramp playing in a normal loop.  The ramp value
        is a fingerprint of the phase, so the sample right after the load has to
        continue from the sample right before the save (a phase that is not
        restored restarts at SA, which is a full-scale jump), and the measured
        slope has to stay the saved one.  Poison: one octave up (double rate)
        written while the state is saved.
  irq   the SCSP timer request and its handshake.  A request is pending at the
        save, acknowledged while the state is saved (poison), and must be
        pending again after the load; the interval between expiries measured
        after the load has to match the interval measured before it, so a lost
        timer phase (longer gap) or a duplicated expiry (immediate second one)
        both fail.

A missing binary or BIOS is a skip, never a native pass.
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

BOOT_FRAMES = 180

WS = 0x2000                  # 8 bit staircase ramp, 16 samples per level
WS_SQUARE = 0x2600           # 8 bit square, the level reference
LEA = 0x0fff                 # one pass over the whole 4096 sample ramp
PITCH = 0x7000               # OCT field 0xE: 0.25 words per sample
PITCH_UP = 0x7800            # one octave up: 0.5 words per sample
ENV_SETTLE_MS = 350          # the decay (D1R 4) spans about 1.3 s
POISON_MS = 100              # live playback at double rate before the load
WAVE_WANT = 2048             # samples per slope window
WAVE_MS = 46

LUA = COMMON_LUA + r'''
local base = 0x05b00000
local c0 = base
local SCIPD, SCIEB, SCIRE = base + 0x420, base + 0x41e, base + 0x422
local SCILV0, TACTL = base + 0x424, base + 0x418
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_CONT hooked=" .. tostring(hooked))

local phase, frames = 'env_setup', 0
local saves_seen, loads_seen, save_target, load_target = 0, 0, 0, 0
local case_index, save_path = 0, nil
local subscribers = {}
local state_path = assert(os.getenv('SCSP_CONT_SAVE_FILE'))
local save_clock = 0
subscribers[1] = emu.add_machine_pre_save_notifier(function()
    saves_seen = saves_seen + 1
    save_clock = emu.time(); print('SCSP_CONT saved')
end)
subscribers[2] = emu.add_machine_post_load_notifier(function()
    loads_seen = loads_seen + 1; print('SCSP_CONT loaded')
end)

-- slot registers are byte offsets inside a slot; the common page (TACTL,
-- SCIEB, SCIPD, SCIRE, SCILV0) starts at 0x400 in the window and is written
-- with absolute addresses, never through the slot helper
local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function wr(addr, val) sp:write_u16(addr, val) end
local function rd(addr) return sp:read_u16(addr) end
local function ms(t) return emu.attotime.from_msec(t) end

-- The sound 68000 owns the same registers.  Everything here runs with it held
-- in reset through the board's own path: SNDOFF (07H) on Saturn, SMPC PDR2 bit
-- 4 on ST-V, which stv.cpp drives and Saturn's sound_reset_handler does not.
local SMPC = 0x00100000
local STV = @@STV@@
local function smpc_ready()
    for _ = 1, 200 do
        if (sp:read_u8(SMPC + 0x63) & 1) == 0 then return true end
        emu.wait(emu.attotime.from_usec(50))
    end
    return false
end
local function smpc_command(com)
    if not smpc_ready() then return false end
    sp:write_u8(SMPC + 0x63, 1)
    sp:write_u8(SMPC + 0x1f, com)
    return smpc_ready()
end
local function sound_hold()
    if STV then
        sp:write_u8(SMPC + 0x7b, 0x30)
        sp:write_u8(SMPC + 0x77, 0x10)
        return true
    end
    return smpc_command(0x07)
end

local cap = { on = false }
emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    local left = chans[1]
    for i = 1, #left do
        if cap.n >= cap.want then break end
        cap.n = cap.n + 1
        cap.l[cap.n] = left[i]
    end
end)

local capture_times = { t0 = 0, t1 = 0 }
local function capture(want, duration_ms)
    cap = { on = true, n = 0, want = want, l = {} }
    local t0 = emu.time()
    emu.wait(ms(duration_ms))
    cap.on = false
    capture_times = { t0 = t0, t1 = emu.time() }
    local values = {}
    for i = 1, math.min(cap.n, cap.want) do values[i] = cap.l[i] or 0 end
    return values, capture_times
end

-- the staircase wraps at the end of its pass, where the value drops by a full
-- scale step; a window that contains a wrap says nothing about the playback
-- rate, so it is rejected and retried
local function capture_clean(want, duration_ms)
    for attempt = 1, 8 do
        local values, times = capture(want, duration_ms)
        local clean = true
        for i = 2, #values do
            if math.abs(values[i] - values[i - 1]) > 4.0 / 128.0 then
                clean = false; break
            end
        end
        if clean then return values, times end
        emu.wait(ms(30))
    end
    error('every capture window contained a loop wrap')
end

local function mean_abs(values, lo, hi)
    local sum, n = 0.0, 0
    for i = lo, math.min(hi, #values) do
        local v = values[i]; if v < 0 then v = -v end
        sum = sum + v; n = n + 1
    end
    return n > 0 and (sum / n) or 0.0
end

-- The sound hook hands out the SCSP stream in ~40 ms batches, so the number of
-- samples a window delivers does not follow the emulated time the window spans.
-- Everything is therefore measured per delivered sample, never per second.
local function per_sample(values)
    local n = #values
    if n < 2 then return 0.0 end
    return (values[n] - values[1]) / (n - 1)
end

local function key_reg(keyonb, keyonex)
    local v = sp:read_u16(c0 + 0x00)
    v = v & 0x07ff
    if keyonex then v = v | 0x1000 end
    if keyonb then v = v | 0x0800 end
    w(c0, 0x00, v)
end

local function config(sa, lsa, lea, lpctl, eg0, eg1, pitch, dipan)
    key_reg(false, true)
    emu.wait(ms(20))
    w(c0, 0x00, 0x0010 | ((lpctl & 3) << 5))
    w(c0, 0x02, sa)
    w(c0, 0x04, lsa)
    w(c0, 0x06, lea)
    w(c0, 0x08, eg0)
    w(c0, 0x0a, eg1)
    w(c0, 0x0c, 0x0200)                 -- STWINH
    w(c0, 0x0e, 0x0000)
    w(c0, 0x10, pitch)
    w(c0, 0x12, 0x0000)
    w(c0, 0x14, 0x0000)
    w(c0, 0x16, 0xe000 | ((dipan or 0x1f) << 8))
    emu.wait(ms(4))
    key_reg(true, true)
end

-- envelope: fast attack, slow decay (D1R 4), no hold, over a *looped* square
-- so the slot keeps sounding while the level moves.  Register 0x08 is
-- D2R<<11 | D1R<<6 | EGHOLD<<5 | AR, register 0x0a is KRS<<10 | DL<<5 | RR.
local function env_config()
    config(@@WS_SQUARE@@, 0x0000, 0x0040, 1, 0x011f, 0x3c1f, @@PITCH@@)
end

-- the wave form is a staircase whose value fingerprints the phase
local function wait_mid_ramp()
    for n = 1, 20 do
        local probe = capture(64, 3)
        local v = probe[#probe] or 0
        if v > -0.25 and v < 0.25 then return v end
    end
    error('the ramp never reached the middle of its pass')
end

local env, wave, irq = {}, {}, {}

local function report()
    print(string.format('SCSP_CONT env before=%.6f after=%.6f ratio=%.5f eg_after=%04x',
        env.before or 0, env.after or 0, (env.before or 0) > 0
            and ((env.after or 0) / env.before) or 0, env.eg_after or 0))
    print(string.format('SCSP_CONT wave slope_before=%.7f slope_after=%.7f '
        .. 'tail=%.6f head=%.6f delta=%.6f pitch_poisoned=%04x '
        .. 'pitch_after=%04x control_after=%04x',
        wave.slope_before or 0, wave.slope_after or 0, wave.tail or 0,
        wave.head or 0, wave.phase_delta or 0, wave.pitch_poisoned or 0,
        wave.pitch_after or 0, wave.control_after or 0))
    print(string.format('SCSP_CONT irq pending_before=%s pending_cleared=%s '
        .. 'pending_restored=%s med_before=%.1f med_after=%.1f '
        .. 'gaps_before=%s gaps_after=%s',
        tostring(irq.pending_before), tostring(irq.pending_cleared),
        tostring(irq.pending_restored), irq.med_before or 0,
        irq.med_after or 0, table.concat(irq.gaps_before or {}, ","),
        table.concat(irq.gaps_after or {}, ",")))
    if #fails == 0 then print('SCSP_CONT PASS cases=3')
    else for _, f in ipairs(fails) do print('SCSP_CONT FAIL ' .. f) end end
    phase = 'done'; emu.unpause(); m:exit()
end

local function scipd() return sp:read_u16(SCIPD) end

local function median(values)
    local sorted = {}
    for i, v in ipairs(values) do sorted[i] = v end
    table.sort(sorted)
    local n = #sorted
    if n == 0 then return 0.0 end
    if n % 2 == 1 then return sorted[(n + 1) / 2] end
    return (sorted[n / 2] + sorted[n / 2 + 1]) / 2
end

local function scipd_intervals(count)
    local times, gaps, t = {}, {}, 0.0
    local previous = nil
    for n = 1, 600 do
        if (scipd() & 0x40) ~= 0 then
            if previous then gaps[#gaps + 1] = t - previous end
            previous = t
            wr(SCIRE, 0x0040)
            if #gaps >= count then break end
        end
        emu.wait(ms(1)); t = t + 1.0
    end
    return gaps, median(gaps)
end

local function finish_step(next_phase)
    print('SCSP_CONT step=' .. (phase == 'busy' and '?' or phase) ..
        ' -> ' .. next_phase)
    phase = next_phase
end

-- MAME schedules the state file write, so the notifier can arrive a frame after
-- the request: a load step waits for the save it asked for by number, never for
-- a leftover flag from an earlier case.
-- MAME's scheduled save file write needs machine time and this core exposes no
-- post-save notifier, so each case uses its own file and the load waits until
-- that file is on disk with a plausible size.  A fresh name per case also means
-- a stale file from an earlier case can never be loaded by mistake.
local function state_written()
    if not save_path then return false end
    local handle = io.open(save_path, 'rb')
    if not handle then return false end
    local size = handle:seek('end')
    handle:close()
    return size ~= nil and size > 32
end

local function request_save()
    case_index = case_index + 1
    save_path = state_path .. '.' .. case_index
    os.remove(save_path)
    save_target = saves_seen + 1
    m:save(save_path)
end

local function request_load()
    if not state_written() then return false end
    load_target = loads_seen + 1
    m:load(save_path); emu.pause()      -- the load rewinds emulated time
    return true
end

local function run(fn)
    local ok, err = pcall(fn)
    if not ok then
        print('SCSP_CONT FAIL ' .. tostring(err)); phase = 'done'
        emu.unpause(); m:exit()
    end
end

local function step(fn)
    coroutine.wrap(function()
        local ok, err = pcall(fn)
        if not ok then
            print('SCSP_CONT FAIL ' .. tostring(err)); phase = 'done'
            emu.unpause(); m:exit()
        end
    end)()
end

local function setup_machine()
    sp:write_u32(0x06000000, 0xaffe0009)
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        cpu.state["SR"].value = 0xf0
        cpu.state["PC"].value = 0x06000000
    end
    if not sound_hold() then error('SMPC SNDOFF was refused') end
    emu.wait(ms(20))
    local snd = assert(m.devices[":audiocpu"])
    local ss = snd.spaces["program"]
    -- 4096 sample staircase: byte n steps by one every 16 samples, 8 bit signed
    for n = 0, 4095 do
        ss:write_u8(0x2000 + n, ((math.floor(n / 16) % 256) - 128) & 0xff)
    end
    -- 8 bit square, +/- 0x40
    for n = 0, 64 * 3 - 1 do
        ss:write_u8(0x2600 + n, ((n % 64) < 32) and 0x40 or 0xc0)
    end
end

local steps = {}
steps.env_setup = function()
    setup_machine()
    env_config()
    emu.wait(ms(@@ENV_SETTLE@@))
    local probe = capture(1024, 24)
    env.before = mean_abs(probe, 65, 1024)
    request_save()
    finish_step('env_load')
end
steps.env_load = function()
    if saves_seen < save_target or not state_written() then return end
    emu.unpause()
    -- poison: a fast decay (D1R 1F) heads for the floor immediately
    w(c0, 0x08, (0x1f << 6) | 0x1f)
    request_load()
    finish_step('env_after')
end
steps.env_after = function()
    if loads_seen < load_target then return end
    emu.unpause()
    local probe = capture(1024, 24)
    env.after = mean_abs(probe, 65, 1024)
    env.eg_after = rd(c0 + 0x08)
    finish_step('wave_setup')
end
steps.wave_setup = function()
    config(@@WS@@, 0x0000, @@LEA@@, 1, 0x0020, 0x3fe0, @@PITCH@@)
    emu.wait(ms(120))
    wait_mid_ramp()
    local probe = capture_clean(@@WAVE_WANT@@, @@WAVE_MS@@)
    wave.slope_before = per_sample(probe)
    wave.tail = probe[#probe] or 0
    request_save()
    finish_step('wave_load')
end
steps.wave_load = function()
    if saves_seen < save_target or not state_written() then return end
    w(c0, 0x10, @@PITCH_UP@@)           -- poison: double rate
    wave.pitch_poisoned = rd(c0 + 0x10)
    -- let the poisoned rate run for half a loop of the wave form, so a phase
    -- that is *not* restored lands about half a pass away from the saved sample
    -- instead of a few levels: at double rate half a 4096 sample pass is about
    -- 100 ms
    emu.wait(ms(@@POISON_MS@@))
    if not request_load() then return end
    finish_step('wave_after')
end
steps.wave_after = function()
    if loads_seen < load_target then return end
    emu.unpause()
    local probe = capture_clean(@@WAVE_WANT@@, @@WAVE_MS@@)
    wave.slope_after = per_sample(probe)
    -- the load rewinds the machine to the save point, so the first samples the
    -- hook hands out afterwards continue from the saved phase; one 40 ms hook
    -- batch of slack is allowed for the batch that straddles the load
    wave.head = probe[1] or 0
    wave.phase_delta = (probe[1] or 0) - (wave.tail or 0)
    wave.pitch_after = rd(c0 + 0x10)
    wave.control_after = rd(c0 + 0x00)
    finish_step('irq_setup')
end
-- SCIPD's timer A request re-pends by itself while the counter sits on 0xff,
-- so an acknowledgement only counts as applied once the bit has been seen
-- clear; the request is then required to come back with the load.
local function poison_request()
    for n = 1, 60 do
        wr(SCIRE, 0x0040)
        if (scipd() & 0x40) == 0 then return true end
        emu.wait(ms(1))
    end
    return false
end

steps.irq_setup = function()
    key_reg(false, true)
    wr(SCILV0, 0x0040)                  -- timer A requests level 6
    wr(SCIEB, 0x0040)                   -- enable timer A
    wr(TACTL, 0x0200)                   -- timer A, prescale 2
    local pending = false
    for n = 1, 400 do
        if (scipd() & 0x40) ~= 0 then pending = true; break end
        emu.wait(ms(1))
    end
    irq.pending_before = pending
    -- leave the counter away from 0xff so the poison below can take effect
    for n = 1, 40 do
        local counter = rd(TACTL) & 0xff
        if counter ~= 0xff and counter ~= 0xfe then break end
        emu.wait(ms(1))
    end
    request_save()
    finish_step('irq_load')
end
steps.irq_load = function()
    if saves_seen < save_target then return end
    emu.unpause()
    irq.pending_cleared = poison_request()
    request_load()
    finish_step('irq_after')
end
steps.irq_after = function()
    if loads_seen < load_target then return end
    emu.unpause()
    irq.pending_restored = (scipd() & 0x40) ~= 0
    local gaps_before, med_before = scipd_intervals(6)
    irq.gaps_before, irq.med_before = gaps_before, med_before
    request_save()
    finish_step('irq_reload')
end
steps.irq_reload = function()
    if saves_seen < save_target then return end
    irq.pending_again = (scipd() & 0x40) ~= 0
    request_load()
    finish_step('irq_after2')
end
steps.irq_after2 = function()
    if loads_seen < load_target then return end
    emu.unpause()
    local gaps_after, med_after = scipd_intervals(6)
    irq.gaps_after, irq.med_after = gaps_after, med_after
    finish_step('report')
end

emu.register_frame_done(function()
    frames = frames + 1
    assert(subscribers[1] and subscribers[2])
    if frames > 1500 and phase ~= 'done' then
        print('SCSP_CONT FAIL bounded save/load wait expired'); phase = 'done'
        emu.unpause(); m:exit(); return
    end
    if frames < @@FRAMES@@ then return end
    if phase == 'report' then
        local current = phase
        phase = 'busy'
        coroutine.wrap(function()
            run(report)
            if phase == 'busy' then phase = current end
        end)()
        return
    end
    local fn = steps[phase]
    if not fn then return end
    local current = phase
    phase = 'busy'
    coroutine.wrap(function()
        run(fn)
        -- a step that returned without choosing the next phase (it is waiting
        -- for a notifier) is retried on the next frame
        if phase == 'busy' then phase = current end
    end)()
end)
print('SCSP_CONT armed')
'''


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP continuity emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_CONT armed', 'SCSP_CONT hooked=true'):
        if marker not in stdout:
            raise RuntimeError('SCSP continuity transcript is missing "%s"' % marker)
    if 'LUA ERROR' in stdout or 'SCSP_CONT FAIL' in stdout:
        raise RuntimeError('SCSP continuity transcript reports a Lua failure')
    stages = re.findall(r'^SCSP_CONT (saved|loaded)$', stdout, re.M)
    if stages.count('saved') != 4 or stages.count('loaded') != 4:
        raise RuntimeError('save/load notifier sequence incomplete: %r' % stages)

    env = re.search(r'^SCSP_CONT env before=([\d.]+) after=([\d.]+) '
                    r'ratio=([\d.]+) eg_after=([0-9a-f]+)$', stdout, re.M)
    wave = re.search(r'^SCSP_CONT wave slope_before=([\d.]+) slope_after=([\d.]+) '
                     r'tail=(-?[\d.]+) head=(-?[\d.]+) delta=(-?[\d.]+) '
                     r'pitch_poisoned=([0-9a-f]+) pitch_after=([0-9a-f]+) '
                     r'control_after=([0-9a-f]+)$', stdout, re.M)
    irq = re.search(r'^SCSP_CONT irq pending_before=(\w+) pending_cleared=(\w+) '
                    r'pending_restored=(\w+) med_before=([\d.]+) med_after=([\d.]+) '
                    r'gaps_before=([\d.,]*) gaps_after=([\d.,]*)$', stdout, re.M)
    if not (env and wave and irq):
        raise RuntimeError('continuity report lines missing')

    failures, results = [], {}
    before, after = float(env.group(1)), float(env.group(2))
    results['env:before'] = before
    results['env:after'] = after
    if before <= 0.05:
        raise RuntimeError(
            'the decay envelope never reached a measurable level (%.6f), so the '
            'case is not measuring anything' % before)
    if not (0.9 < after / before < 1.1):
        failures.append(
            'env: the level after the load is %.6f against %.6f before it '
            '(ratio %.3f); a restored envelope continues its decay, a lost one '
            'restarts it' % (after, before, after / before))

    slope_before, slope_after = float(wave.group(1)), float(wave.group(2))
    tail, head = float(wave.group(3)), float(wave.group(4))
    pitch_poisoned = int(wave.group(6), 16)
    pitch_after = int(wave.group(7), 16)
    results['wave:slope_before'] = slope_before
    results['wave:slope_after'] = slope_after
    results['wave:phase_delta'] = head - tail
    if pitch_poisoned != PITCH_UP:
        failures.append(
            'wave: the poison write did not take (pitch reads %04x, expected '
            '%04x), so the restore check below proves nothing'
            % (pitch_poisoned, PITCH_UP))
    if pitch_after != PITCH:
        failures.append(
            'wave: the saved pitch register reads %04x after the load, not %04x '
            '(the slot register file is not restored)' % (pitch_after, PITCH))
    if slope_before <= 0:
        raise RuntimeError('the looped ramp measured no advance (%.7f per sample)'
                           % slope_before)
    if not (0.9 < slope_after / slope_before < 1.1):
        failures.append(
            'wave: the playback rate after the load is %.7f per sample against '
            '%.7f before it; the saved pitch was not restored (the poisoned one '
            'octave up doubles the rate)' % (slope_after, slope_before))
    # A level of the staircase is 1/128 and one 40 ms hook batch advances the
    # pass by about 0.2 of the value range, so a quarter of the range is the
    # honest window for "continues where the save left it".  A phase that
    # restarts at SA reads about -1.0 and the poisoned phase (half a pass of
    # live playback, not rewound) lands about +-1.0 away: both are far outside.
    band = 0.25
    results['wave:band'] = band
    if abs(head - tail) > band:
        failures.append(
            'wave: the ramp value after the load is %.6f against %.6f at the '
            'save (delta %.6f, band %.2f); the phase was not restored from the '
            'saved state' % (head, tail, head - tail, band))
    results['irq:median_before'] = med_before
    results['irq:median_after'] = med_after
    def gaps(text):
        return [float(v) for v in text.split(',') if v]
    before_gaps, after_gaps = gaps(irq.group(6)), gaps(irq.group(7))
    if irq.group(1) != 'true':
        failures.append('irq: no timer request was pending before the save')
    if irq.group(2) != 'true':
        failures.append('irq: the poison acknowledgement did not clear the '
                        'request, so the survival check below proves nothing')
    if irq.group(3) != 'true':
        failures.append(
            'irq: the request pending when the state was saved did not come back '
            'with the load (unsaved SCIPD handshake state)')
    if len(before_gaps) < 5 or len(after_gaps) < 5:
        failures.append('irq: only %d/%d expiry intervals were measured'
                        % (len(before_gaps), len(after_gaps)))
    elif med_before <= 0:
        failures.append('irq: the timer expiry intervals are zero')
    else:
        if not (0.9 < med_after / med_before < 1.1):
            failures.append(
                'irq: the median expiry interval after the load is %.1f ms '
                'against %.1f ms before it; a lost timer phase stretches the gap '
                'and a duplicated expiry shortens it' % (med_after, med_before))
        # the load restores the counter mid-tick, so the first interval after it
        # is legitimately partial; anything more than one short gap, or a gap
        # above the nominal period, is a lost or duplicated expiry
        short = [g for g in after_gaps if g < 0.6 * med_before]
        if len(short) > 1:
            failures.append(
                'irq: %d intervals after the load are shorter than 60%% of the '
                'nominal %.1f ms period (%s); more than the one partial interval '
                'the restored counter explains' % (len(short), med_before,
                                                   ','.join('%g' % g for g in short)))
        long = [g for g in after_gaps if g > 1.4 * med_before]
        if long:
            failures.append(
                'irq: intervals after the load exceed 140%% of the nominal '
                '%.1f ms period (%s); an expiry was lost'
                % (med_before, ','.join('%g' % g for g in long)))
    if failures:
        raise RuntimeError('SCSP continuity fixture failed:\n  ' +
                           '\n  '.join(failures))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    ap.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
    ap.add_argument('--system', default='saturnjp')
    ap.add_argument('--drc', action='store_true')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()

    exe = args.executable.resolve()
    if not os.access(exe, os.X_OK):
        print('SKIP: no runnable emulator at %s' % exe)
        return 0

    lua = (LUA.replace('@@STV@@', 'true' if args.system.startswith('stv')
                        else 'false')
              .replace('@@WS@@', hex(WS))
              .replace('@@WS_SQUARE@@', hex(WS_SQUARE))
              .replace('@@LEA@@', hex(LEA))
              .replace('@@PITCH@@', hex(PITCH))
              .replace('@@PITCH_UP@@', hex(PITCH_UP))
              .replace('@@FRAMES@@', str(BOOT_FRAMES))
              .replace('@@ENV_SETTLE@@', str(ENV_SETTLE_MS))
              .replace('@@POISON_MS@@', str(POISON_MS))
              .replace('@@WAVE_WANT@@', str(WAVE_WANT))
              .replace('@@WAVE_MS@@', str(WAVE_MS)))
    if '@@' in lua:
        raise RuntimeError('unsubstituted placeholder in the Lua script')
    out = args.output or Path(tempfile.mkdtemp(prefix='scsp-cont-'))
    out.mkdir(parents=True, exist_ok=True)
    script_path = out / 'test.lua'
    script_path.write_text(lua)
    rom = args.rompath.resolve()
    state_dir = out / 'state'
    state_dir.mkdir(exist_ok=True)
    cmd = [str(exe), args.system, '-rompath', str(rom), '-noreadconfig',
           '-skip_gameinfo', ('-drc' if args.drc else '-nodrc'), '-video',
           'none', '-sound', 'none', '-nothrottle', '-seconds_to_run', '900',
           '-autoboot_delay', '0', '-autoboot_script', str(script_path)]
    for kind in ('nvram', 'cfg', 'state', 'snapshot'):
        cmd += ['-' + kind + '_directory', str(out / kind)]
    (out / 'invocation.json').write_text(json.dumps({
        'executable': str(exe), 'system': args.system, 'drc': args.drc,
        'binary_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'bios_sha256': hashlib.sha256(
            (rom / (args.system + '.zip')).read_bytes()).hexdigest(),
        'lua_sha256': hashlib.sha256(lua.encode()).hexdigest(),
        'command': cmd,
    }, indent=2) + '\n')
    env = dict(os.environ)
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
               SCSP_CONT_SAVE_FILE=str(state_dir / 'cont.sta'))
    with (out / 'runtime.log').open('w') as log:
        proc = subprocess.run(cmd, cwd=out, env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=1800)
    text = (out / 'runtime.log').read_text(errors='replace')
    results = validate_output(text, proc.returncode)
    for tag in sorted(results):
        print('  %-22s %.6f' % (tag, results[tag]))
    print('SCSP continuity: PASS')
    print('SCSP continuity: envelope, loop phase and timer handshake survive a '
          'scheduled save/load; not analog audio, in-flight DMA timing or CD '
          'audio')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

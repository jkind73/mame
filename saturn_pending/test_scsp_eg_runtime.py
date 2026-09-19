#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP envelope-generator rate measurement through the sound hook.

Drives one SCSP slot with a constant (DC) carrier and captures the mixer
amplitude the slot produces.  The amplitude is reported in the chip's own
envelope resolution: the code multiplies the sample by a 12-bit attenuation
table entry, so the capture is quantised to that same 4096-step scale
(``q = round(amplitude / full_scale * 4096)``).  Comparing there keeps the
comparison in the domain the hardware actually uses instead of pretending to a
finer resolution than the table has.

The envelope is not free-running on the output sample clock: the chip gates one
EG update into every 2^shift samples (counter_shift[]) and applies an 8-phase
increment pattern (increment[]) selected by the key-rate-scaled segment rate.
The measurement is checked against a re-implementation of that tabulated model;
the only unobservable parameter - where the free-running sample counter sat
when the capture started - is recovered by search.  A wrong rate, a wrong
increment pattern, a wrong segment transition, a linear attack or a missing
slot-stop at 0x3C0 attenuation would all fail the comparison.

Covers AR/D1R/D2R/RR, EGHOLD, DL, KRS/octave rate scaling, the AR=0/D2R=0
"no change" cases and the release level retained from a decay plateau.
Missing binary/BIOS is a skip, never a native pass.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

# hardware tables (Ymir IncrementEG, re-checked against mednafen RunEG)
COUNTER_SHIFT = [12, 12, 12, 12, 11, 11, 11, 11, 10, 10, 10, 10, 9, 9, 9, 9,
                 8, 8, 8, 8, 7, 7, 7, 7, 6, 6, 6, 6, 5, 5, 5, 5,
                 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1,
                 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
INCREMENT = [
    [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 2, 1, 1, 1, 2],
    [2, 1, 2, 1, 2, 1, 2, 1], [1, 2, 2, 2, 1, 2, 2, 2],
    [2, 2, 2, 2, 2, 2, 2, 2], [2, 2, 2, 4, 2, 2, 2, 4],
    [4, 2, 4, 2, 4, 2, 4, 2], [2, 4, 4, 4, 2, 4, 4, 4],
    [4, 4, 4, 4, 4, 4, 4, 4], [4, 4, 4, 8, 4, 4, 4, 8],
    [8, 4, 8, 4, 8, 4, 8, 4], [4, 8, 8, 8, 4, 8, 8, 8],
    [8, 8, 8, 8, 8, 8, 8, 8], [8, 8, 8, 8, 8, 8, 8, 8],
    [8, 8, 8, 8, 8, 8, 8, 8], [8, 8, 8, 8, 8, 8, 8, 8]]

# 12-bit attenuation table as the chip builds it (3 dB per 32 level units);
# index 0 is the loudest entry, index 0x3FF the quietest
TABLE = [int(math.pow(10.0, (3.0 * (i - 0x3ff)) / 32.0 / 20.0) * 4096.0)
         for i in range(0x400)]

ATTACK, DECAY1, DECAY2, RELEASE = 0, 1, 2, 3
SILENT = 4095           # slot inactive (or never keyed on): no output at all
FULL = 0x000            # attenuation 000H = loudest
KEYON_LEVEL = 0x280     # documented key-on attenuation
STOP_LEVEL = 0x3c0      # level at which the slot goes inactive
# q-domain tolerances: the table is 12-bit, so 1 LSB of slew is accepted
# everywhere and the quiet end (where one level unit moves the table entry by
# less than an LSB) allows the documented quantisation step
def tolerance(q):
    return 2 + (round(0.03 * q) if q < 256 else 0)


# key-on cases (attack / decay / sustain) and key-off cases (release); "ms" is
# the capture window, the trigger is written immediately before the capture
# name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms
CASES = [
    ('ar1f', 'on', 0x1f, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 30),
    ('ar10', 'on', 0x10, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 80),
    ('ar08', 'on', 0x08, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 250),
    ('ar04', 'on', 0x04, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 1300),
    ('ar00', 'on', 0x00, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 120),
    ('ar08_krs0', 'on', 0x08, 0x00, 0x00, 0x1f, 0x1f, 0x0, 0x8, 0, 250),
    ('ar08_oct', 'on', 0x08, 0x00, 0x00, 0x1f, 0x1f, 0x2, 0xb, 0, 150),
    ('eg_hold', 'on', 0x10, 0x14, 0x00, 0x1f, 0x1f, 0xf, 0x8, 1, 120),
    ('d1r1f', 'on', 0x1f, 0x1f, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 40),
    ('d1r10', 'on', 0x1f, 0x10, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 400),
    ('d1r04', 'on', 0x1f, 0x04, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 1300),
    ('d1r00', 'on', 0x1f, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 0, 250),
    ('dl00', 'on', 0x1f, 0x1f, 0x00, 0x1f, 0x00, 0xf, 0x8, 0, 60),
    ('dl08', 'on', 0x1f, 0x1f, 0x00, 0x1f, 0x08, 0xf, 0x8, 0, 60),
    ('d2r16', 'on', 0x1f, 0x1f, 0x10, 0x1f, 0x04, 0xf, 0x8, 0, 400),
    ('rr1f', 'off', 0x00, 0x00, 0x00, 0x1f, 0x1f, 0xf, 0x8, 1, 20),
    ('rr10', 'off', 0x00, 0x00, 0x00, 0x10, 0x1f, 0xf, 0x8, 1, 400),
    ('rr08', 'off', 0x00, 0x00, 0x00, 0x08, 0x1f, 0xf, 0x8, 1, 400),
    ('rr08_krs', 'off', 0x00, 0x00, 0x00, 0x08, 0x1f, 0x3, 0xa, 1, 400),
    ('rr04', 'off', 0x00, 0x00, 0x00, 0x04, 0x1f, 0xf, 0x8, 1, 1300),
    ('rr00', 'off', 0x00, 0x00, 0x00, 0x00, 0x1f, 0xf, 0x8, 1, 120),
    ('rr_from_dl', 'off', 0x1f, 0x1f, 0x00, 0x0c, 0x10, 0xf, 0x8, 0, 500),
]
CASES_BY_NAME = {c[0]: c for c in CASES}


def octave_term(octave):
    return (octave ^ 8) - 8


def effective_rate(rate, krs, octave):
    eff = rate
    if krs != 0xf:
        eff += max(0, min(15, krs + octave_term(octave)))
    return min(eff << 1, 0x3f)


def attack_bug(ar, krs, octave):
    if krs == 0xf:
        return False
    return ar + max(0, min(15, krs + octave_term(octave))) >= 0x20


def table_q(level):
    """Attenuation level -> the 12-bit table entry the mixer applies."""
    return TABLE[0x3ff - min(level, 0x3ff)]


def simulate(case, phase, pattern, pre, n, rate_bias=0, linear_attack=False):
    """Re-implementation of the tabulated EG model.

    ``rate_bias`` and ``linear_attack`` are used by the result-parser controls
    to synthesise wrong-rate and wrong-attack-law transcripts; the native run
    always uses the defaults.

    ``phase`` is the sample counter (mod 2^shift) at capture index 0, ``pattern``
    the increment row index used by the first tick and ``pre`` the number of
    samples the capture starts after key-on (0 for key-on cases, or the settle
    interval for key-off cases, which the model replays to know the level the
    release starts from).  Returns the externally visible attenuation level for
    every sample of the capture window; SILENT marks samples after the slot
    went inactive.
    """
    name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms = case
    rates = {ATTACK: min(effective_rate(ar, krs, oct) + rate_bias, 0x3f),
             DECAY1: min(effective_rate(d1r, krs, oct) + rate_bias, 0x3f),
             DECAY2: min(effective_rate(d2r, krs, oct) + rate_bias, 0x3f),
             RELEASE: min(effective_rate(rr, krs, oct) + rate_bias, 0x3f)}
    bug = attack_bug(ar, krs, oct)
    out = [SILENT] * n
    if kind == 'on':
        keyon_at, keyoff_at = pre, None
    else:
        # the slot was keyed on long before the capture and is keyed off at 0
        keyon_at, keyoff_at = -pre, 0
    level, prev, state = STOP_LEVEL, SILENT, RELEASE
    active, stopping = False, False
    for i in range(-pre, n):
        stopping = False
        if i == keyon_at:
            state = ATTACK
            level = FULL if bug else KEYON_LEVEL
            prev = level
            active = True
        elif keyoff_at is not None and i == keyoff_at:
            state = RELEASE
        if active:
            # one EG update per sample, gated by the free-running sample counter
            e = rates[state]
            shift = COUNTER_SHIFT[e]
            if (i + phase) % (1 << shift) == 0:
                inc = INCREMENT[e][(((i + phase) >> shift) + pattern) & 7]
            else:
                inc = 0
            # the engine compares the level sampled before this update, so a
            # segment change takes effect on the next sample while the increment
            # already computed for this one is still applied
            curr = level
            prev = 0 if (state == ATTACK and eghold) else curr
            if state == ATTACK:
                if not bug and inc > 0 and curr > 0 and e > 0:
                    level = max(0, min(0x3ff, curr + ((inc if linear_attack
                                                       else (~curr * inc) >> 4))))
                if curr == 0:
                    state = DECAY1
            else:
                if state == DECAY1 and (curr >> 5) == dl:
                    state = DECAY2
                if e > 0:
                    level = min(0x3ff, curr + inc)
            # a slot whose visible attenuation reaches 0x3C0 goes inactive; the
            # crossing sample itself is still produced
            if prev >= STOP_LEVEL:
                stopping = True
        if i >= 0:
            out[i] = prev if (active or stopping) else SILENT
        if stopping:
            active = False
    return out


def model_q(case, phase, pattern, pre, n, **kwargs):
    return [0 if v == SILENT else table_q(v)
            for v in simulate(case, phase, pattern, pre, n, **kwargs)]


def parse_line(line):
    m = re.match(r'SCSP_EG case=(\S+) n=(\d+) rle=\[([^\]]*)\]', line)
    if not m:
        return None
    name, n, rle = m.group(1), int(m.group(2)), m.group(3)
    runs = []
    for part in rle.split(','):
        if not part:
            continue
        length, q = part.split(':')
        runs.append((int(length), int(q)))
    return name, n, runs


def expand(runs):
    out = []
    for length, q in runs:
        out.extend([q] * length)
    return out


def find_anchor(trace, case):
    """Index of the trigger's own visible edge in a trace.

    The audio buffers the sound hook receives can still hold samples generated
    just before the register write, so the trigger is located from the trace
    itself: the key-on jump out of silence, the key-off drop out of the EGHOLD
    level, or - when the level is continuous across the trigger (release from a
    decay plateau) - the first step of the release staircase.
    """
    name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms = case
    if kind == 'on':
        for i, v in enumerate(trace):
            if v >= 1:
                return i
        return None
    base = trace[0]
    if eghold:
        for i, v in enumerate(trace):
            if v < 0.5 * base:
                return i
        return None
    tol = tolerance(base)
    for i in range(1, len(trace)):
        if trace[i] < base - tol:
            return i
    return None


def check_case(case, q, n):
    """Align the model to the measurement; returns (max error, worst index)."""
    name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms = case
    # emu.wait() is frame-granular, so the capture is a whole number of audio
    # frames at or above the requested window
    if not 0.9 * ms * 44.1 <= n <= (ms + 40) * 44.1:
        raise RuntimeError('%s: capture is %d samples, expected %d..%d at '
                           '44.1 kHz' % (name, n, 0.9 * ms * 44.1,
                                         (ms + 40) * 44.1))
    e0 = find_anchor(q, case)
    if e0 is None:
        raise RuntimeError('%s: the trigger leaves no visible edge in the trace'
                           % name)
    measured = q[e0:]
    # key-on cases are triggered at the capture start; key-off cases were keyed
    # on one settle interval earlier, which the model replays to reach the
    # level the release starts from
    pre = 0 if kind == 'on' else int(round((ms + 400) * 44.1))
    # the sample counter is global, so one phase has to line up the gating grid
    # of every segment the envelope visits: search the widest period involved
    registers = {ATTACK: ar, DECAY1: d1r, DECAY2: d2r, RELEASE: rr}
    shifts = [COUNTER_SHIFT[effective_rate(regs, krs, oct)]
              for regs in registers.values() if regs > 0]
    if not shifts:
        phis = [0]
    else:
        wide = max(shifts)
        if wide <= 5:
            phis = list(range(1 << wide))
        else:
            # the slow rows only step on a wide grid, which pins the phase down:
            # a tick at model index t becomes visible one sample later
            steps = [i for i in range(1, len(measured))
                     if abs(measured[i] - measured[i - 1]) >= 1]
            # a release out of a decay plateau has no visible trigger edge, so
            # the model is anchored on its own first step there
            m0_prior = steps[0] if (kind == 'off' and not eghold) and steps else 0
            phis = sorted({(1 - steps[-1] - m0_prior + d) % (1 << wide)
                           for d in (-3, -2, -1, 0, 1, 2, 3)}) if steps else [0]
    best = None
    for phi in phis:
        for pat in range(8):
            model = model_q(case, phi, pat, pre, n)
            # the model's own trace starts at the trigger for every case except
            # a release out of a decay plateau, where the level is continuous
            if kind == 'off' and not eghold:
                m0 = find_anchor(model, case)
                if m0 is None:
                    continue
            else:
                m0 = 0
            model = model[m0:m0 + len(measured)]
            worst, worst_at = 0, 0
            for i, (m, v) in enumerate(zip(model, measured)):
                err = abs(m - v) / tolerance(m)
                if err > worst:
                    worst, worst_at = err, i
                    if best is not None and worst >= best[0]:
                        break
            if best is None or worst < best[0]:
                best = (worst, worst_at, phi, pat, m0)
    if best is None:
        raise RuntimeError('%s: no model alignment reproduces the trigger edge'
                           % name)
    return best


def require_documented_hold(name, q, e0):
    """Documented "change volume is minimum (0)" and EGHOLD behaviour.

    AR = 00H and RR = 00H are documented to leave the level unchanged, D1R =
    00H holds the decay-1 level, and EGHOLD is documented to hold the attack
    level at 000H for an AR-determined time before the segment moves on.  These
    are checked against the trace itself, not only through the model.
    """
    steps = [i for i in range(1, len(q) - e0)
             if abs(q[e0 + i] - q[e0 + i - 1]) >= 1]
    if name in ('ar00', 'rr00') and steps:
        raise RuntimeError('%s: documented no-change rate produced %d level '
                           'steps' % (name, len(steps)))
    if name == 'd1r00':
        tail = [i for i in steps if i > 0.4 * (len(q) - e0)]
        if tail:
            raise RuntimeError('d1r00: D1R=0 must hold the decay level, but the '
                               'tail still steps at %r' % tail[:4])
    if name == 'eg_hold' and [i for i in steps if i < 1500]:
        raise RuntimeError('eg_hold: EGHOLD must hold 000H while the AR ramp '
                           'runs; the level moved after %d samples'
                           % [i for i in steps if i < 1500][0])


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP EG emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_EG armed', 'SCSP_EG done'):
        if marker not in stdout:
            raise RuntimeError('SCSP EG transcript is missing "%s"' % marker)
    if 'LUA ERROR' in stdout or 'SCSP_EG FAIL' in stdout:
        raise RuntimeError('SCSP EG transcript reports a Lua failure')
    calib = re.search(r'SCSP_EG calib n=(\d+) mean=([0-9.]+)', stdout)
    if not calib or float(calib.group(2)) <= 0.0:
        raise RuntimeError('SCSP EG calibration is missing or silent')
    results, missing = {}, []
    for line in stdout.splitlines():
        parsed = parse_line(line)
        if not parsed:
            continue
        name, n, runs = parsed
        if name not in CASES_BY_NAME:
            raise RuntimeError('SCSP EG transcript reports unknown case "%s"' % name)
        case = CASES_BY_NAME[name]
        q = expand(runs)
        if len(q) != n:
            raise RuntimeError('%s: run-length table covers %d of %d samples'
                               % (name, len(q), n))
        worst, worst_at, phi, pat, m0 = check_case(case, q, n)
        if worst > 1.0:
            rate = case[2] if case[1] == 'on' else case[6]
            raise RuntimeError(
                '%s: measured envelope leaves the tabulated rate model by '
                '%.1f tolerance units at sample %d (phase=%d pattern=%d); the '
                'model gates an update every 2^%d samples, so a wrong rate '
                'moves the whole staircase'
                % (name, worst, worst_at, phi, pat,
                   COUNTER_SHIFT[effective_rate(rate, case[7], case[8])]))
        require_documented_hold(name, q, find_anchor(q, case))
        results[name] = (worst, worst_at, phi, pat, m0)
    missing = [c[0] for c in CASES if c[0] not in results]
    if missing:
        raise RuntimeError('SCSP EG transcript is missing cases: ' + ','.join(missing))
    return results


LUA = COMMON_LUA + r'''
local base = 0x05b00000
local s0 = base
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_EG hooked=" .. tostring(hooked))

local CASES = {
@@CASES@@
}

local cap = { on = false }
local K = nil

emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    local buf = chans[1]
    for i = 1, #buf do
        local v = buf[i]
        cap.n = cap.n + 1
        if cap.sum then cap.sum = cap.sum + v end
        if cap.rle then
            -- report in the chip's own 12-bit envelope resolution
            local q = 0
            if v > 1e-9 then
                q = math.floor(v / K * 4096 + 0.5)
                if q < 1 then q = 1 end
                if q > 4096 then q = 4096 end
            end
            if q == cap.last then
                cap.run = cap.run + 1
            else
                if cap.last ~= nil then
                    cap.rle[#cap.rle + 1] = cap.run .. ":" .. cap.last
                end
                cap.last = q
                cap.run = 1
            end
        end
    end
end)

local function begin_amp()
    cap = { on = true, n = 0, sum = 0.0 }
end

local function end_amp()
    cap.on = false
    return cap.sum / math.max(cap.n, 1)
end

local function begin_levels()
    cap = { on = true, n = 0, rle = {}, last = nil, run = 0 }
end

local function end_levels(name)
    cap.on = false
    if cap.last ~= nil then cap.rle[#cap.rle + 1] = cap.run .. ":" .. cap.last end
    print(string.format("SCSP_EG case=%s n=%d rle=[%s]",
        name, cap.n, table.concat(cap.rle, ",")))
end

local function w(off, val) sp:write_u16(s0 + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end

local function configure(c)
    w(0x00, 0x0030)                                   -- LPCTL=1, PCM8B=1, no KEYONB
    w(0x02, 0x1000)                                   -- SA
    w(0x04, 0x0000)                                   -- LSA
    w(0x06, 0x003f)                                   -- LEA
    w(0x08, (c.d2r << 11) | (c.d1r << 6) | (c.eghold << 5) | c.ar)
    w(0x0a, (c.krs << 10) | (c.dl << 5) | c.rr)
    w(0x0c, 0x0200)                                   -- STWINH
    w(0x0e, 0x0000)
    w(0x10, (c.oct << 11))
    w(0x12, 0x0000)
    w(0x14, 0x0000)
    w(0x16, 0xe000)                                   -- DISDL=7
end

local function key_on() sp:write_u16(s0 + 0x00, 0x3830) end
local function key_off() sp:write_u16(s0 + 0x00, 0x1030) end

local function settle()
    w(0x0a, (0xf << 10) | (0x1f << 5) | 0x1f)        -- fast release
    key_off()
    emu.wait(ms(30))
    cap = { on = false }
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
    for i = 0, 63 do ss:write_u8(0x1000 + i, 0x40) end

    -- full-volume reference: EGHOLD keeps the visible level at 000H
    configure({ar = 0, d1r = 0, d2r = 0, rr = 0, dl = 0x1f, krs = 0xf,
               oct = 8, eghold = 1})
    key_on()
    emu.wait(ms(60))
    begin_amp()
    emu.wait(ms(40))
    K = end_amp()
    if K <= 0.0 then print("SCSP_EG FAIL no-audio"); m:exit(); return end
    print(string.format("SCSP_EG calib n=%d mean=%.6f", 1764, K))
    settle()

    for _, c in ipairs(CASES) do
        configure(c)
        if c.kind == "on" then
            emu.wait(ms(10))
            begin_levels()
            key_on()
            emu.wait(ms(c.ms))
        else
            key_on()
            emu.wait(ms(c.ms + 400))
            begin_levels()
            key_off()
            emu.wait(ms(c.ms))
        end
        end_levels(c.name)
        settle()
    end
    print("SCSP_EG done")
    m:exit()
end

local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_EG FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_EG armed")
'''


def lua_table():
    rows = []
    for (name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms) in CASES:
        rows.append('  {name="%s", kind="%s", ar=0x%02x, d1r=0x%02x, d2r=0x%02x,'
                    ' rr=0x%02x, dl=0x%02x, krs=0x%x, oct=0x%x, eghold=%d, ms=%d}'
                    % (name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms))
    return ',\n'.join(rows)


def main(success_message=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', type=Path, default=ROOT / 'saturn')
    p.add_argument('--rompath', type=Path, default=ROOT / 'regtests')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--system', choices=('saturnjp', 'saturneu', 'stvbios'),
                   default='saturnjp')
    p.add_argument('--drc', action='store_true')
    a = p.parse_args()
    exe = a.executable.resolve()
    rom = a.rompath.resolve()
    output = a.output.resolve()
    if not exe.is_file() or not (rom / (a.system + '.zip')).is_file():
        print('SKIP: need native binary and ' + a.system + ' BIOS')
        return
    output.mkdir(parents=True, exist_ok=True)
    script_text = LUA.replace('@@CASES@@', lua_table())
    (output / 'invocation.json').write_text(json.dumps({
        'system': a.system, 'engine': 'drc' if a.drc else 'interpreter',
        'binary_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'bios_sha256': hashlib.sha256((rom / (a.system + '.zip')).read_bytes()).hexdigest(),
        'lua_sha256': hashlib.sha256(script_text.encode()).hexdigest(),
    }, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='scsp-eg-live-') as tmp:
        d = Path(tmp)
        script = d / 'test.lua'
        script.write_text(script_text)
        command = [str(exe), a.system, '-rompath', str(rom), '-noreadconfig',
                   '-skip_gameinfo', ('-drc' if a.drc else '-nodrc'),
                   '-video', 'none', '-sound', 'none', '-nothrottle',
                   '-seconds_to_run', '360', '-autoboot_delay', '0',
                   '-autoboot_script', str(script)]
        for kind, folder in [('nvram', 'nvram'), ('cfg', 'cfg'), ('state', 'sta'),
                             ('snapshot', 'snap')]:
            command += ['-' + kind + '_directory', str(d / folder)]
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        with (output / 'runtime.log').open('w') as log:
            result = subprocess.run(command, cwd=d, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=900)
        text = (output / 'runtime.log').read_text(errors='replace')
    results = validate_output(text, result.returncode)
    for name in sorted(results):
        worst, worst_at, phi, pat, m0 = results[name]
        print('  %-11s max model error %5.2f tolerance units  phase=%d '
              'pattern=%d model anchor=%d' % (name, worst, phi, pat, m0))
    print(success_message or
          ('SCSP EG: %d native envelope cases matched the tabulated rate model'
           % len(results)))


if __name__ == '__main__':
    main()

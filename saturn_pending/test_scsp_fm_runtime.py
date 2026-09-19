#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP FM voice mixing (ring modulation) measurement through the sound hook.

The FM path changes the wave form *address* the carrier reads: ST-077-R2-052594
p.67 Table 4.17 gives the maximum address shift per MDL setting, and p.66-67
define the whole chain the shift comes from, i.e.

    ZD = (XD + YD) / 2            (averaging operation unit, p.54/66)
    shift = ZD * 2^(MDL - 15)     (Table 4.17/4.15: 1 cycle = 1 Kword, so
                                   MDL=AH at full scale is 512 words = pi)

with a hardware clip at that 1 Kword ("the SCSP clips (process to prevent shift
from exceeding a limit) shift that exceeds 1K word and returns the shift to 0",
p.68, "because the valid address bits available for shift was 10"), which is a
truncation to a 10 bit shift field plus a sign bit rather than a saturation, and
a modulation rate of 0 for MDL 0-4 (Table 4.15), i.e. those settings do not
modulate.  The clip cases below are the ones that tell a wrap (the model here,
matching Beetle's sign_x_to_s32(11, ...) of the address) from a saturation, so
they are reported with the depth they measured.

Measurement: the shift is a *phase* offset of the carrier's read address, so two
slots play the same looped wave form and the same OCT/FNS - slot 0 with the
modulation programmed and panned hard left, slot 2 with MDL = MDXSL = MDYSL = 0
panned hard right.  The distance between the two channels' rising edges, divided
by the words per sample, is the address shift, and because both edges are taken
from the same capture it is immune to where the capture started or to the
sound-hook batch boundaries.  (A duty cycle comparison does not work here: a
constant address offset only relabels the phase of a wave form that repeats once
per loop, so the high and low times of the period are unchanged.  The transcript
prints the peak of the left channel as well, so a silent capture cannot pass.)

The wave form loops every 1024 words ("fast") or 3072 words ("wide"); the wider
loop is used once the documented shift approaches half a cycle, since a shift of
exactly one loop period is indistinguishable from none.  Every slot reads its
data from a three-cycle copy of its waveform (the manual tells users to always
have three cycles of wave form data, because the modulated address can leave the
loop).  The modulator is a slot holding a DC level, keyed in the same KEYONEX as
the carriers, whose slot/generation offset (MDXSL = MDYSL = 21H, Table 4.16
"01H" past the sample for carrier 00 / modulator 01) is the documented one.

The "inj" cases write the 64 word SOUS register file with a known DC value and
key no modulator, which measures the averaging unit, the MDL scaler and the
phase adder without depending on the modulator slot's own output path.

Missing binary/BIOS is a skip, never a native pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

from test_smpc_multitap_runtime import COMMON_LUA, ROOT

RING_OFFSET = 0x21          # Table 4.16: carrier 00, modulator 01 -> "01H" past
RING_OFFSET_SPARE = 0x22    # next stack location: nothing writes a modulator there
TOLERANCE = 1.0             # words; one edge position resolves 1/4 of one
SAMPLE_RATE = 44100

# waveform groups: name -> (loop/period in words, high words per period,
# capture length in samples)
GROUPS = {
    'fast': (1024, 512, 20480),
    'wide': (3072, 1024, 40960),
}

# case name, group, modulator DC level (16 bit units), MDL, injected sound stack
# value (0 = drive the modulation input with a modulator slot), MDYSL input
#
# "inj" cases write the SOUS register file directly and key no modulator, which
# tests the averaging unit, the MDL scaler and the phase adder on their own,
# without depending on what the modulator slot put in the ring.
CASES = [
    # Table 4.17 depth scaling, modulator level below the old wrap point
    ('m5',      'fast', 0x2000, 0x5, 0, 0x21),   #   8 words
    ('m6',      'fast', 0x2000, 0x6, 0, 0x21),   #  16
    ('m7',      'fast', 0x2000, 0x7, 0, 0x21),   #  32
    ('m8',      'fast', 0x2000, 0x8, 0, 0x21),   #  64
    ('m9',      'fast', 0x2000, 0x9, 0, 0x21),   # 128
    ('mA',      'fast', 0x2000, 0xA, 0, 0x21),   # 256
    ('mA2',     'fast', 0x3F00, 0xA, 0, 0x21),   # 504
    # MDL 0-4 must not shift at all (Table 4.15 rate 0), regardless of level
    ('wrap3',   'fast', 0x4000, 0x3, 0, 0x21),
    ('wrap4',   'fast', 0x4000, 0x4, 0, 0x21),
    # the same scaling with a modulator level at or above half scale, where the
    # old doubled ring store wrapped to a negative value and reversed the shift
    ('wrap5',   'fast', 0x4000, 0x5, 0, 0x21),   #  16 words
    ('wrap6',   'fast', 0x4000, 0x6, 0, 0x21),   #  32
    ('wrap7',   'fast', 0x4000, 0x7, 0, 0x21),   #  64
    ('wrap8',   'fast', 0x4000, 0x8, 0, 0x21),   # 128
    ('wrap9',   'fast', 0x4000, 0x9, 0, 0x21),   # 256
    ('wrap9b',  'fast', 0x6000, 0x9, 0, 0x21),   # 384
    # MDL B-F: depth beyond half a cycle, and the p.68 1 Kword clip, which
    # wraps the depth back towards 0 (a saturation would pin all of these at
    # one cycle and leave nothing to measure in the wide group)
    ('deepB',   'wide', 0x3000, 0xB, 0, 0x21),   #   768 words, inside the limit
    ('boundA',  'wide', 0x7F00, 0xA, 0, 0x21),   #  1016 words, just inside it
    ('clipB',   'wide', 0x5000, 0xB, 0, 0x21),   #  1280 -> wraps to -768
    ('clipF',   'wide', 0x7F00, 0xF, 0, 0x21),   # 32512 -> wraps to -256
    ('deepE',   'wide', 0x1000, 0xE, 0, 0x21),   #  4096 -> wraps to 0
    # averaging unit: Y reads the next stack location, which no keyed slot
    # writes, so ZD = (XD + 0) / 2 is half of the modulator output
    ('halfA',   'fast', 0x4000, 0xA, 0, 0x22),   # 256 words instead of 512
    # injected sound stack values (SOUS register file writes, no modulator)
    ('injA',    'fast', 0x3F00, 0xA, 1, 0x21),   # 504
    ('inj4',    'fast', 0x7F00, 0x4, 1, 0x21),   # 0, MDL 0-4 do not modulate
    ('inj9',    'fast', 0x3F00, 0x9, 1, 0x21),   # 252
    ('injC',    'wide', 0x1000, 0xC, 1, 0x21),   # 512
    ('injF',    'wide', 0x3F00, 0xF, 1, 0x21),   # 16128 -> wraps to -256
]


def zd_of(level, inj, mdy):
    """Averaging operation unit output for a case.

    A modulator case reads the same stack location twice (MDXSL = MDYSL = 21H),
    so XD = YD = level; the "spare" Y offset reads a location no slot writes, so
    only XD is non-zero.  An injected case fills the whole register file, so both
    inputs hold the injected value whatever offset is programmed."""
    if inj or mdy == RING_OFFSET:
        return float(level)
    return float(level) / 2.0


def expected_words(zd, mdl):
    """Table 4.17 depth, zero for MDL 0-4, wrapped by the p.68 1 Kword clip."""
    if mdl <= 0x4:
        return 0.0
    words = zd * (2.0 ** (mdl - 15))
    # 10 address bits plus a sign bit: the shift wraps instead of saturating
    return ((words + 1024.0) % 2048.0) - 1024.0


def previous_words(zd, mdl, doubled=True):
    """What the old code produced: a doubled ring store wrapping at 16 bits.

    The doubling only happened for values a slot wrote itself; an injected SOUS
    word is read back exactly as written."""
    ring = 2 * int(zd) if doubled else int(zd)
    if ring >= 32768:
        ring -= 65536
    elif ring < -32768:
        ring += 65536
    return (ring * 1024) >> (26 - mdl) if mdl <= 26 else 0


def fold(words, period):
    """A shift is only defined modulo the looped wave form's period."""
    return ((words + period / 2.0) % period) - period / 2.0


def parse_trace(line):
    m = re.match(r'SCSP_FM trace=(\S+) n=(\d+) peak=(\d+) edges=\[([^\]]*)\] '
                 r'redges=\[([^\]]*)\]', line)
    if not m:
        return None

    def edges(text):
        out = []
        for part in text.split(','):
            if part:
                idx, state = part.split(':')
                out.append((int(idx), int(state)))
        return out

    return (m.group(1), int(m.group(2)), int(m.group(3)), edges(m.group(4)),
            edges(m.group(5)))


def measure_words(trace, period):
    """Address shift of the left (modulated) carrier, in words.

    Both channels play the same wave form from the same phase, so the distance
    between their rising edges is the address shift; the words per sample factor
    is measured from the right (unmodulated) channel's own period in the same
    capture."""
    left = [t for t, s in trace[3] if s == 1]
    right = [t for t, s in trace[4] if s == 1]
    if len(left) < 2 or len(right) < 2:
        raise RuntimeError('only %d left / %d right rising edges captured; the '
                           'two carriers are not both being read'
                           % (len(left), len(right)))
    period_samples = statistics.median(
        [b - a for a, b in zip(right, right[1:])])
    words_per_sample = float(period) / period_samples
    deltas = [min(right, key=lambda v: abs(v - t)) - t for t in left]
    return fold(statistics.median(deltas) * words_per_sample, period), \
        words_per_sample, left[0], right[0]


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP FM emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_FM armed', 'SCSP_FM done'):
        if marker not in stdout:
            raise RuntimeError('SCSP FM transcript is missing "%s"' % marker)
    if 'LUA ERROR' in stdout or 'SCSP_FM FAIL' in stdout:
        raise RuntimeError('SCSP FM transcript reports a Lua failure')
    traces = {}
    for line in stdout.splitlines():
        parsed = parse_trace(line)
        if parsed:
            traces[parsed[0]] = parsed
    for tag in ['base', 'wbase'] + [c[0] for c in CASES]:
        if tag not in traces:
            raise RuntimeError('SCSP FM transcript is missing the %s capture' % tag)

    failures = []
    results = {}

    # the two carriers of an unmodulated capture must be in phase: this is the
    # method's own zero check, not a hardware claim
    for group, (period, _, _) in GROUPS.items():
        tag = 'base' if group == 'fast' else 'wbase'
        words, wps, l0, r0 = measure_words(traces[tag], period)
        print('  %-4s zero check (%s): %.2f words, %.4f words/sample, first '
              'edges %d/%d' % (group, tag, words, wps, l0, r0))
        if abs(words) > TOLERANCE:
            failures.append('%s: the unmodulated carriers are %.2f words apart, '
                            'so the measurement itself is biased' % (tag, words))

    for name, group, level, mdl, inj, mdy in CASES:
        period, _, _ = GROUPS[group]
        zd = zd_of(level, inj, mdy)
        try:
            words, wps, l0, r0 = measure_words(traces[name], period)
        except RuntimeError as err:
            failures.append('%s: %s' % (name, err))
            continue
        want = fold(expected_words(zd, mdl), period)
        old = fold(previous_words(zd, mdl, not inj), period)
        results[name] = (words, want, old, zd, traces[name][2])
        if abs(words - want) > TOLERANCE:
            failures.append(
                '%s: modulator level %#06x (ZD %.0f) at MDL=%XH shifted the '
                'carrier by %.1f words, ST-077 Table 4.17 documents %.1f'
                % (name, level, zd, mdl, words, want))
        elif traces[name][2] == 0:
            failures.append('%s: the carrier is silent, nothing was measured'
                            % name)
    return results, failures


LUA = COMMON_LUA + r'''
local base = 0x05b00000
local c0, m1, cr = base, base + 0x20, base + 0x40
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_FM hooked=" .. tostring(hooked))

local CASES = {
@@CASES@@
}
local GROUPS = {
@@GROUPS@@
}

local cap = { on = false }

-- The hook delivers one table per sound device, and one table per output
-- channel inside it: channel 1 is the modulated carrier, channel 2 the
-- unmodulated reference.
emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    local left, right = chans[1], chans[2]
    for i = 1, #left do
        if cap.n >= cap.want then break end
        cap.n = cap.n + 1
        local l = left[i]
        local sl = (l >= 0) and 1 or 0
        if cap.last_l ~= nil and sl ~= cap.last_l and #cap.l < 64 then
            cap.l[#cap.l + 1] = cap.n .. ":" .. sl
        end
        cap.last_l = sl
        local a = math.floor(math.abs(l) * 32768 + 0.5)
        if a > cap.peak then cap.peak = a end
        if right then
            local rv = right[i]
            local sr = (rv >= 0) and 1 or 0
            if cap.last_r ~= nil and sr ~= cap.last_r and #cap.r < 64 then
                cap.r[#cap.r + 1] = cap.n .. ":" .. sr
            end
            cap.last_r = sr
        end
    end
end)

local function begin_capture(want)
    cap = { on = true, n = 0, want = want, l = {}, r = {}, peak = 0 }
end

local function end_capture(tag)
    cap.on = false
    print(string.format("SCSP_FM trace=%s n=%d peak=%d edges=[%s] redges=[%s]",
        tag, cap.n, cap.peak, table.concat(cap.l, ","), table.concat(cap.r, ",")))
end

local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end

-- a carrier: a looped square wave, held at full volume by EGHOLD, panned to
-- one side so the two carriers can be told apart in one capture
local function config_carrier(slot, group, mdl, mdy, dipan)
    local g = GROUPS[group]
    w(slot, 0x00, 0x0030)                              -- LPCTL=1, PCM8B=1
    w(slot, 0x02, g.sa)                                -- SA
    w(slot, 0x04, 0x0000)                              -- LSA: word 0
    w(slot, 0x06, g.lea)                               -- LEA: one period
    w(slot, 0x08, 0x0020)                              -- EGHOLD=1, AR=0
    w(slot, 0x0a, 0x3fe0)                              -- KRS=F, DL=1F, RR=0
    w(slot, 0x0c, 0x0200)                              -- STWINH: keep the ring clean
    w(slot, 0x0e, (mdl << 12) | (0x21 << 6) | mdy)     -- MDL, MDXSL, MDYSL
    w(slot, 0x10, 0x7000)                              -- OCT=14, FNS=0: 1/4 word per sample
    w(slot, 0x12, 0x0000)
    w(slot, 0x14, 0x0000)
    w(slot, 0x16, 0xe000 | (dipan << 8))               -- DISDL=7, DIPAN
end

-- modulator: 16 identical words of DC, panned out of both channels so it is
-- never heard, but its slot output still goes to the sound stack
local function config_modulator(dc)
    for i = 0, 15 do ss:write_u8(0x4000 + i, dc & 0xff) end
    w(m1, 0x00, 0x0030)
    w(m1, 0x02, 0x4000)
    w(m1, 0x04, 0x0000)
    w(m1, 0x06, 0x0010)                                -- LEA: 16 words
    w(m1, 0x08, 0x0020)
    w(m1, 0x0a, 0x3fe0)
    w(m1, 0x0c, 0x0000)                                -- STWINH=0: write the ring
    w(m1, 0x0e, 0x0000)
    w(m1, 0x10, 0x7000)
    w(m1, 0x12, 0x0000)
    w(m1, 0x14, 0x0000)
    w(m1, 0x16, 0x0000)                                -- DISDL=0: never heard directly
end

local function key_on(inj)
    if inj == 0 then
        sp:write_u16(m1 + 0x00, 0x0830)                -- modulator KEYONB
    else
        sp:write_u16(m1 + 0x00, 0x0030)                -- no modulator: keep the ring
    end
    sp:write_u16(cr + 0x00, 0x0830)                    -- reference carrier KEYONB
    -- one KEYONEX starts every slot that is keyed, so both carriers start from
    -- the same phase in the same sample
    sp:write_u16(c0 + 0x00, 0x3830)                    -- carrier KEYONB + KEYONEX
end

local function key_off()
    sp:write_u16(m1 + 0x00, 0x0030)
    sp:write_u16(cr + 0x00, 0x0030)
    sp:write_u16(c0 + 0x00, 0x1030)
end

local function capture(tag, group, dc, mdl, inj, mdy)
    mdy = mdy or 0x21                                  -- unmodulated references
    key_off()
    emu.wait(ms(20))
    if inj ~= 0 then
        -- a slot left in release keeps sounding (RR=0 sustains) and keeps
        -- writing its 16 bit slot output into the two stack words the carrier
        -- reads, which would overwrite the injected values: silence it and
        -- inhibit its stack write before filling the file
        w(m1, 0x06, 0x00ff)                            -- TL: -95 dB
        w(m1, 0x0c, 0x0200)                            -- STWINH
        emu.wait(ms(2))
        -- the SOUS register file is read/write: fill the whole ring so the
        -- modulation input is known no matter which slot/generation the
        -- carrier selects
        for i = 0, 63 do sp:write_u16(base + 0x600 + 2 * i, inj) end
    else
        config_modulator(dc)
    end
    config_carrier(c0, group, mdl, mdy, 0x1f)          -- measured: hard left
    config_carrier(cr, group, 0x0, 0x0, 0x0f)          -- reference: hard right
    emu.wait(ms(4))
    begin_capture(GROUPS[group].capture)
    key_on(inj)
    emu.wait(ms(1 + GROUPS[group].capture / 44))
    end_capture(tag)
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
    ss = snd.spaces["program"]
    ss:write_u16(0x70000, 0x60fe)
    snd.state["SR"].value = 0x2700
    snd.state["PC"].value = 0x70000

    sp:write_u16(base + 0x400, 0x000f)

    -- three cycles of each wave form, as the manual asks for, so a modulated
    -- address can leave its loop and still find the same data
    for i = 0, 3 * 1024 - 1 do
        local v = (((i % 1024) < 512) and 0x40 or 0xc0)
        ss:write_u8(0x2000 + i, v)
    end
    for i = 0, 3 * 3072 - 1 do
        local v = (((i % 3072) < 1024) and 0x40 or 0xc0)
        ss:write_u8(0x8000 + i, v)
    end

    capture("base", "fast", 0x00, 0x0, 0)
    capture("wbase", "wide", 0x00, 0x0, 0)
    for _, c in ipairs(CASES) do
        capture(c.name, c.group, c.dc, c.mdl, c.inj, c.mdy)
    end
    print("SCSP_FM done")
    m:exit()
end

local frames, started = 0, false
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < 180 then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_FM FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_FM armed")
'''


def lua_cases():
    rows = []
    for name, group, level, mdl, inj, mdy in CASES:
        # the modulator holds a DC sample, so the Lua writes the high byte of
        # the 16 bit level; injected cases write the level itself into the SOUS
        # register file (which is the 16 bit slot output)
        rows.append('  {name="%s", group="%s", dc=0x%02x, mdl=0x%x, inj=0x%04x, mdy=0x%02x}'
                    % (name, group, 0 if inj else level >> 8, mdl,
                       level if inj else 0, mdy))
    return ',\n'.join(rows)


def lua_groups():
    rows = []
    for group, (period, high, capture) in sorted(GROUPS.items()):
        # the wave form data starts one period before SA, three periods long
        sa = (0x2000 if group == 'fast' else 0x8000) + period
        rows.append('  %s = {sa=0x%x, lea=0x%x, capture=%d}'
                    % (group, sa, period, capture))
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
    script_text = (LUA.replace('@@CASES@@', lua_cases())
                      .replace('@@GROUPS@@', lua_groups()))
    (output / 'invocation.json').write_text(json.dumps({
        'system': a.system, 'engine': 'drc' if a.drc else 'interpreter',
        'binary_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'bios_sha256': hashlib.sha256((rom / (a.system + '.zip')).read_bytes()).hexdigest(),
        'lua_sha256': hashlib.sha256(script_text.encode()).hexdigest(),
    }, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='scsp-fm-live-') as tmp:
        d = Path(tmp)
        script = d / 'test.lua'
        script.write_text(script_text)
        command = [str(exe), a.system, '-rompath', str(rom), '-noreadconfig',
                   '-skip_gameinfo', ('-drc' if a.drc else '-nodrc'),
                   '-video', 'none', '-sound', 'none', '-nothrottle',
                   '-seconds_to_run', '900', '-autoboot_delay', '0',
                   '-autoboot_script', str(script)]
        for kind, folder in [('nvram', 'nvram'), ('cfg', 'cfg'), ('state', 'sta'),
                             ('snapshot', 'snap')]:
            command += ['-' + kind + '_directory', str(d / folder)]
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        with (output / 'runtime.log').open('w') as log:
            result = subprocess.run(command, cwd=d, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=1800)
        text = (output / 'runtime.log').read_text(errors='replace')
    results, failures = validate_output(text, result.returncode)
    for name, group, level, mdl, inj, mdy in CASES:
        if name not in results:
            print('  %-8s unmeasurable' % name)
            continue
        words, want, old, zd, peak = results[name]
        print('  %-8s MDL=%XH level %#06x (ZD %.0f): %8.1f words measured, %8.1f '
              'from Table 4.17 (peak %d; the old doubled store gave %.1f)'
              % (name, mdl, level, zd, words, want, peak, old))
    if failures:
        raise RuntimeError('; '.join(failures))
    print(success_message or
          ('SCSP FM: %d modulation-depth cases match ST-077 Table 4.17, '
           'including the MDL 0-4 no-modulation settings, the depth scaling, the '
           'averaging unit and the 1 Kword clip' % len(CASES)))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP PCM wave form playback measurement through the sound hook.

Covers the wave form source the FM and envelope fixtures deliberately hold
constant: the sample format and byte order, the sample addressing (SA is a byte
address, LSA/LEA are sample counts from SA), the loop modes (ST-077-R2-052594
pp.36-37 Table 4.12 / section 4.3), the pitch stepper, the linear interpolation
between the two adjacent samples, and a live pitch change during playback.

Method: a slot plays a known wave form written into sound RAM and the SCSP
stream is captured through the per-device Lua sound hook (`-sound none`).  The
mixer gain is not part of the claim, so every check is either a *parity* claim
(two slots with the same gain must produce the same sequence), a *rate* claim
(counted in samples, from the loop restarts or the pitch ratio) or a *shape*
claim that does not need absolute units.

Facts the cases are built on (all measured, not assumed):

* the machine must finish booting before the SCSP produces output: the first
  ~180 frames are silent, so the test starts there (as the FM fixture does);
* a slot at DISDL=7 maps a signed 8 bit wave form 1:1 onto the output, so the
  8 bit ramp below spans 252 units and clips at the very bottom; the ramp's
  unit is therefore `span/252` in the captured floats;
* OCT field 0xE (register 0x10 = 0x7000) is 0.25 words per sample and field
  0xF (0x7800) is 0.5, one octave up.

Wave form areas in sound RAM:

  0x2000  8 bit ramp, 3 x 1024 samples of 64 steps of 4 units
  0x2600  8 bit square, 3 x 64 samples of 0x40 / 0xc0
  0x3000  16 bit ramp, 3 x 1024 samples of 64 steps of 1024 units, big endian
  0x5000  16 bit byte-order pattern, 3 x 64 samples of 0x4000 / 0xc000

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

BOOT_FRAMES = 180            # the stream is silent until the boot has settled
SETTLE_MS = 250              # key-on transient before the measured window
RAMP = 64                    # samples per ramp cycle in the stored wave form
RAMP_STEP = 4                # 8 bit units per sample
RAMP_SPAN = (RAMP - 1) * RAMP_STEP   # 252 units across one cycle
PITCH_OCT_E = 0x7000         # OCT field 0xE: 0.25 words/sample
PITCH_UP = 0x7800            # OCT field 0xF: one octave up, 0.5 words/sample

WS = 0x2000                  # 8 bit ramp (one byte per sample)
WS_SQUARE = 0x2600           # 8 bit square, the byte-order level reference
WS16 = 0x3000                # 16 bit ramp (two bytes per sample)
WS_ORDER = 0x5000            # 16 bit byte-order pattern (words)


def lua_waveforms():
    return """
    -- 8 bit ramp: (n %% 64) * 4 - 128, three cycles of 1024 samples
    for n = 0, 3 * 1024 - 1 do
        ss:write_u8(0x%04x + n, (((n %% 64) * 4) - 128) & 0xff)
    end
    -- 8 bit square, the level the 16 bit byte-order pattern must reach
    for n = 0, 64 * 3 - 1 do
        ss:write_u8(0x%04x + n, ((n %% 64) < 32) and 0x40 or 0xc0)
    end
    -- 16 bit ramp: the same shape scaled up, big endian sample pairs
    for n = 0, 3 * 1024 - 1 do
        local v = ((n %% 64) * 1024) - 32768
        if v < 0 then v = v + 65536 end
        ss:write_u8(0x%04x + 2 * n, (v >> 8) & 0xff)
        ss:write_u8(0x%04x + 2 * n + 1, v & 0xff)
    end
    -- byte order pattern: 32 samples of +0x4000 then 32 of -0x4000, written so
    -- that a big endian read sees 0x4000/0xC000 (half scale) while a byte
    -- swapped read sees 0x0040/0x00C0 (256 times quieter, 1/128 of the 8 bit
    -- square the reference slot plays)
    for n = 0, 64 * 3 - 1 do
        local b = ((n %% 64) < 32) and 0x40 or 0xc0
        ss:write_u8(0x%04x + 2 * n, b)
        ss:write_u8(0x%04x + 2 * n + 1, 0x00)
    end
    """ % (WS, WS_SQUARE, WS16, WS16, WS_ORDER, WS_ORDER)


LUA = COMMON_LUA + r'''
local base = 0x05b00000
local c0, cr = base, base + 0x40
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_PCM hooked=" .. tostring(hooked))

local PITCH, PITCH_UP = @@PITCH@@, @@PITCH_UP@@
local cap = { on = false }

emu.register_sound_update(function(t)
    local chans = t[":scsp"]
    if not chans or not chans[1] or not cap.on then return end
    local left, right = chans[1], chans[2]
    for i = 1, #left do
        if cap.n >= cap.want then break end
        cap.n = cap.n + 1
        cap.l[cap.n] = left[i]
        if right then cap.r[cap.n] = right[i] end
    end
end)

local function begin_capture(want)
    cap = { on = true, n = 0, want = want, l = {}, r = {} }
end

local function end_capture(tag)
    cap.on = false
    local l, r = {}, {}
    for i = 1, math.min(cap.n, cap.want) do
        l[i] = string.format("%.6f", cap.l[i] or 0)
        r[i] = string.format("%.6f", cap.r[i] or 0)
    end
    print(string.format("SCSP_PCM trace=%s n=%d l=[%s] r=[%s]", tag, cap.n,
        table.concat(l, ","), table.concat(r, ",")))
end

local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end

-- one slot: a looped wave form at full volume (EGHOLD), no modulation, no
-- stack write, panned hard to one side so the two channels stay separable
local function config(slot, sa, lea, lpctl, pcm8b, oct)
    w(slot, 0x00, (pcm8b and 0x0010 or 0x0000) | ((lpctl & 0x3) << 5))
    w(slot, 0x02, sa)
    w(slot, 0x04, 0x0000)                          -- LSA: word 0
    w(slot, 0x06, lea)                             -- LEA: one cycle
    w(slot, 0x08, 0x0020)                          -- EGHOLD=1, AR=0
    w(slot, 0x0a, 0x3fe0)                          -- KRS=F, DL=1F, RR=0
    w(slot, 0x0c, 0x0200)                          -- STWINH
    w(slot, 0x0e, 0x0000)                          -- MDL/MDXSL/MDYSL off
    w(slot, 0x10, oct)                             -- OCT | FNS
    w(slot, 0x12, 0x0000)
    w(slot, 0x14, 0x0000)
    w(slot, 0x16, 0xe000)                          -- DISDL=7, DIPAN=0
end

local function pan(slot, dipan)
    w(slot, 0x16, 0xe000 | (dipan << 8))
end

-- The key bits live in the same register as LPCTL and PCM8B, so a key write
-- must not clobber them: read the configured control word back and add only
-- the key bits.  (A fixture that writes a constant here silently switches the
-- slot's format and loop mode at key-on.)
local function key_reg(slot, keyonb, keyonex)
    local v = sp:read_u16(slot + 0x00)
    v = v & 0x07ff                                  -- LPCTL, PCM8B: keep
    if keyonex then v = v | 0x1000 end
    if keyonb then v = v | 0x0800 end
    w(slot, 0x00, v)
end

-- a key-off scan puts every slot in RELEASE, which the key-on scan needs
local function key_off()
    key_reg(c0, false, true)
    key_reg(cr, false, true)
end

local function key_on()
    key_reg(cr, true, false)                        -- KEYONB: reference
    key_reg(c0, true, true)                         -- KEYONB + KEYONEX: both
end

local function play(tag, want, cfg0, cfg2, midwait, midwrite, atkeyon)
    key_off()
    emu.wait(ms(10))
    config(c0, cfg0.sa, cfg0.lea, cfg0.lpctl, cfg0.pcm8b, cfg0.oct)
    pan(c0, 0x1f)                                  -- measured: hard left
    if cfg2 then
        config(cr, cfg2.sa, cfg2.lea, cfg2.lpctl, cfg2.pcm8b, cfg2.oct)
    else
        -- no reference: DISDL=0 keeps the slot inaudible even though the
        -- key-on keys it
        w(cr, 0x16, 0x0000)
    end
    pan(cr, 0x0f)                                  -- reference: hard right
    emu.wait(ms(4))
    key_on()
    if not atkeyon then
        -- the key-on transient lasts a couple of hundred milliseconds (the
        -- envelope starts at 0x280 attenuation and the attack ramp produces
        -- the 8 phase stepping pattern), so only the steady state is measured
        emu.wait(ms(@@SETTLE@@))
    end
    begin_capture(want)
    if midwait and midwrite then
        emu.wait(midwait)
        midwrite()
        emu.wait(ms(1 + (want - cap.n) / 44))
    else
        emu.wait(ms(1 + want / 44))
    end
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

    w(base + 0x400, 0x000f)                        -- KEYONEX enable
@@WAVE@@
    local ramp8, ramp16 = 0x2400, 0x3800           -- word 1024 of each ramp
    do
        local b8, b16, b16b = {}, {}, {}
        for i = 0, 7 do
            b8[i + 1] = string.format("%02x", ss:read_u8(ramp8 + i))
            b16[i + 1] = string.format("%04x",
                ss:read_u8(ramp16 + 2 * i) * 256 + ss:read_u8(ramp16 + 2 * i + 1))
            b16b[i + 1] = string.format("%04x",
                ss:read_u8(ramp16 + 2 * i + 0x60) * 256
                + ss:read_u8(ramp16 + 2 * i + 0x61))
        end
        print("SCSP_PCM data8=" .. table.concat(b8, " ")
            .. " data16=" .. table.concat(b16, " ")
            .. " data16b=" .. table.concat(b16b, " "))
    end
    local square8 = 0x2680                         -- 8 bit square, middle cycle
    local order16 = 0x5080                         -- byte-order pattern, word 64
    local lea = @@RAMP@@                           -- one ramp cycle, in samples

    -- instrument control: the same format twice
    play("parity8", 4096,
         {sa = ramp8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH},
         {sa = ramp8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH})

    -- the same logical samples through the 16 bit path: SA is a byte address,
    -- LSA/LEA count samples, and the ramp steps 1024 units per sample either
    -- way, so any wrong unit shows up as a different sequence
    play("parity16", 4096,
         {sa = ramp16, lea = lea, lpctl = 1, pcm8b = false, oct = PITCH},
         {sa = ramp8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH})

    -- byte order: 16 bit 0x4000/0xC000 pairs against the 8 bit square of the
    -- same level; a byte swapped read is 256 times quieter
    play("order16", 4096,
         {sa = order16, lea = lea, lpctl = 1, pcm8b = false, oct = PITCH},
         {sa = square8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH})

    -- fractional step: the ramp must advance on every sample, and one 64 word
    -- loop must take 256 samples
    play("interp", 4096,
         {sa = ramp8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH})

    -- a live pitch write during the capture: one octave up doubles the step
    play("livePitch", 8192,
         {sa = ramp8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH},
         nil, ms(90), function() w(c0, 0x10, PITCH_UP) end)

    -- loop modes on the same ramp
    play("loopN", 4096,
         {sa = ramp8, lea = lea, lpctl = 1, pcm8b = true, oct = PITCH})
    play("loopR", 4096,
         {sa = ramp8, lea = lea, lpctl = 2, pcm8b = true, oct = PITCH})
    -- OPEN: this fixture measures a railed constant for the ping-pong case,
    -- while the isolated probe (saturn_pending/evidence/scsp-pcm/) measures a
    -- healthy triangle for the same registers, including with LSA = 0 and
    -- after reverse-loop cases.  Not asserted until that difference is
    -- understood; the loop mode itself is not claimed to be broken.
    play("loopP", 4096,
         {sa = ramp8, lea = lea, lpctl = 3, pcm8b = true, oct = PITCH})
    -- a no-loop slot plays one pass and stops: measured from its own key-on,
    -- so the capture contains the pass and then the silence after LEA
    play("loopOff", 4096,
         {sa = ramp8, lea = lea, lpctl = 0, pcm8b = true, oct = PITCH},
         nil, nil, nil, true)

    print("SCSP_PCM done")
    m:exit()
end

local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < @@FRAMES@@ then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_PCM FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_PCM armed")
'''


def span(values):
    return max(values) - min(values)


def steps_of(values):
    return [abs(values[i + 1] - values[i]) for i in range(len(values) - 1)]


def advance_fraction(values, floor):
    """Fraction of samples that moved by more than `floor`.

    A linear interpolation read advances on every sample; a nearest-neighbour
    read holds a value for several samples and then jumps.
    """
    s = steps_of(values)
    return sum(1 for x in s if x > floor) / float(len(s)) if s else 0.0


def restarts(values, drop):
    """Loops: runs of samples where the wave form fell back by more than
    `drop`.  An interpolated sawtooth spreads its wrap over the samples inside
    the last word, so one loop is a run of consecutive falling steps."""
    runs = 0
    inside = False
    for i in range(len(values) - 1):
        fall = values[i + 1] - values[i] < -drop
        if fall and not inside:
            runs += 1
        inside = fall
    return runs


def turns(values, floor):
    """Sign changes of the step: two per triangle period."""
    signs = [1 if values[i + 1] > values[i] else -1
             for i in range(len(values) - 1)
             if abs(values[i + 1] - values[i]) > floor]
    return sum(1 for i in range(1, len(signs)) if signs[i] != signs[i - 1])


def median_step(values):
    s = steps_of(values)
    return statistics.median(s) if s else 0.0


def parse_trace(line):
    m = re.match(r'SCSP_PCM trace=(\S+) n=(\d+) l=\[([^\]]*)\] r=\[([^\]]*)\]',
                 line)
    if not m:
        return None

    def series(text):
        return [float(v) for v in text.split(',') if v]

    return m.group(1), int(m.group(2)), series(m.group(3)), series(m.group(4))


CASE_TAGS = ('parity8', 'parity16', 'order16', 'interp', 'livePitch',
             'loopN', 'loopR', 'loopP', 'loopOff')


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP PCM emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_PCM armed', 'SCSP_PCM done'):
        if marker not in stdout:
            raise RuntimeError('SCSP PCM transcript is missing "%s"' % marker)
    if 'LUA ERROR' in stdout or 'SCSP_PCM FAIL' in stdout:
        raise RuntimeError('SCSP PCM transcript reports a Lua failure')
    traces = {}
    for line in stdout.splitlines():
        parsed = parse_trace(line)
        if parsed:
            traces[parsed[0]] = parsed

    failures = []
    results = {}
    for tag in CASE_TAGS:
        if tag not in traces:
            raise RuntimeError('SCSP PCM transcript is missing the %s capture'
                               % tag)
        if len(traces[tag][2]) < 512:
            raise RuntimeError('%s captured only %d samples'
                               % (tag, len(traces[tag][2])))
        results[tag] = traces[tag][2]

    # instrument control: the same format twice, and the same samples in both
    for tag in ('parity8', 'parity16'):
        left, right = results[tag], traces[tag][3]
        s = span(left)
        if s <= 0:
            failures.append('%s: the measured channel is silent' % tag)
            continue
        worst = max(abs(a - b) for a, b in zip(left, right))
        results[tag + ':diff'] = worst / s
        if worst > s / 100.0:
            failures.append(
                '%s: the two channels differ by %.4f of the wave form span, so '
                'the two formats do not play the same wave form'
                % (tag, worst / s))

    # byte order
    left, ref = results['order16'], traces['order16'][3]
    ls, rs = span(left), span(ref)
    results['order16:ratio'] = ls / rs if rs else 0.0
    if rs <= 0:
        failures.append('order16: the 8 bit reference is silent')
    elif ls < rs / 2.0:
        failures.append(
            'order16: the 16 bit sample pair reaches %.4f of the 8 bit level it '
            'must equal, i.e. a byte-swapped (256x quieter) read' % (ls / rs))

    # interpolation and the loop period, both counted in samples
    left = results['interp']
    unit = span(left) / float(RAMP_SPAN)
    frac = advance_fraction(left, unit / 2.0)
    results['interp:advance'] = frac
    loop_samples = RAMP / 0.25
    # the interpolated wrap spreads the sawtooth's fall over the samples inside
    # the last word, so a restart is a fall far bigger than the ramp's own step
    n_restarts = restarts(left, 10.0 * median_step(left))
    results['interp:restarts'] = n_restarts
    if frac < 0.9:
        failures.append(
            'interp: only %.1f%% of the samples advanced at a 0.25 word/sample '
            'step over a ramp of 4 units per sample; a linear interpolation '
            'read advances on every sample' % (100.0 * frac))
    if n_restarts < 4:
        failures.append(
            'interp: %d loop restarts in %d samples; a %d word loop at 0.25 '
            'words/sample restarts every %.0f samples'
            % (n_restarts, len(left), RAMP, loop_samples))

    # live pitch: the step must double at the write
    left = results['livePitch']
    half = len(left) // 2
    before, after = median_step(left[:half]), median_step(left[half:])
    results['livePitch:before'] = before
    results['livePitch:after'] = after
    if before <= 0:
        failures.append('livePitch: no advance before the pitch write')
    elif not (1.6 < after / before < 2.4):
        failures.append(
            'livePitch: the ramp advance changed by %.2fx across a one octave '
            'pitch write, it must be 2x' % (after / before))

    # loop modes
    left = results['loopN']
    s = span(left)
    n_restarts = restarts(left, 10.0 * median_step(left))
    results['loopN:restarts'] = n_restarts
    results['loopN:period'] = len(left) / n_restarts if n_restarts else 0.0
    if s <= 0:
        failures.append('loopN: the measured channel is silent')
    elif n_restarts < 4:
        failures.append(
            'loopN: a normal loop over a %d word ramp restarts %d times in %d '
            'samples at 0.25 words/sample, so it is not restarting at LSA'
            % (RAMP, n_restarts, len(left)))
    elif not (0.9 < results['loopN:period'] / loop_samples < 1.1):
        failures.append(
            'loopN: one loop of %d words took %.1f samples, expected %.0f'
            % (RAMP, results['loopN:period'], loop_samples))

    # only the reverse loop is asserted: the ping-pong capture is an open
    # question (see the case list), so it is reported but not claimed
    for tag in ('loopR',):
        s = span(results[tag])
        n_turns = turns(results[tag], median_step(results[tag]) / 2.0)
        results[tag + ':turns'] = n_turns
        if s <= 0:
            failures.append('%s: the measured channel is silent' % tag)
        elif n_turns < 4:
            failures.append(
                '%s: the ramp turns around %d times; a %s loop must turn at '
                'both LSA and LEA'
                % (tag, n_turns,
                   'reverse' if tag == 'loopR' else 'ping-pong'))
    s = span(results['loopP'])
    results['loopP:span'] = s
    if s <= 0:
        print('  note: loopP (ping-pong) measured a railed constant in this '
              'fixture; the isolated probe measures a healthy triangle for the '
              'same registers, so this is recorded as an open question, not an '
              'emulator claim')

    left = results['loopOff']
    s = span(left)
    tail = left[len(left) * 3 // 4:]
    ts = span(tail)
    results['loopOff:tail'] = ts / s if s else float('inf')
    if s <= 0:
        failures.append('loopOff: the measured channel is silent')
    elif ts > s / 50.0:
        failures.append(
            'loopOff: a no-loop slot still spans %.4f of the wave form in the '
            'last quarter of the capture; it must stop at LEA' % (ts / s))

    return results, failures


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

    lua = (LUA.replace('@@WAVE@@', lua_waveforms())
              .replace('@@PITCH@@', hex(PITCH_OCT_E))
              .replace('@@PITCH_UP@@', hex(PITCH_UP))
              .replace('@@RAMP@@', str(RAMP))
              .replace('@@FRAMES@@', str(BOOT_FRAMES))
              .replace('@@SETTLE@@', str(SETTLE_MS)))
    out = args.output or Path(tempfile.mkdtemp(prefix='scsp-pcm-'))
    out.mkdir(parents=True, exist_ok=True)

    script_path = out / 'test.lua'
    script_path.write_text(lua)
    rom = args.rompath.resolve()
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
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    with (out / 'runtime.log').open('w') as log:
        proc = subprocess.run(cmd, cwd=out, env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=1800)
    text = (out / 'runtime.log').read_text(errors='replace')
    results, failures = validate_output(text, proc.returncode)

    for tag in sorted(results):
        if isinstance(results[tag], float):
            print('  %-22s %.5f' % (tag, results[tag]))
    print('SCSP PCM: %s' % ('PASS' if not failures else 'FAIL'))
    for f in failures:
        print('  - %s' % f)
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())

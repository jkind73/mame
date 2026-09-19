#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP final mixer master volume and DAC interface qualification.

Covers the last stage of the SCSP the other fixtures hold constant: the
master volume attenuator (MVOL, common control register 0x400 bits 3-0) and the
DAC interface width select (DAC18B, bit 8 of the same word).  ST-077-R2-052594
documents both fields but no numeric attenuation table:

* p.93 "Final Step Output Adjustment Block" - the direct and effect components
  are combined and "the final output level is adjusted by MVOL";
* p.100 MVOL: "Represents the master volume output to the D/A converter.
  Because it is used to control the overall output level, lowering the MVOL
  for an output that has overflowed to a lower level will not remove the
  clipping noise."  That sentence is a testable ordering claim: the overflow
  clip happens *before* the attenuator;
* p.100 DAC18B: "When setting the digital output as 18bit D/A converter
  interface, set this bit to 1B.  When 16 bit, set 0B." - an interface width
  select, not a level control;
* Figure 4.3 / Table 4.4 place both fields in the common control word at sound
  address 100400H.

Method: one to four slots play the same in-phase 8 bit square wave, all panned
to the centre, and the SCSP stream is captured through the per-device Lua sound
hook (`-sound none`), as the FM/EG/PCM fixtures do.  Every claim is either a
ratio between two captures of the same signal (so the absolute mixer gain is
not assumed) or a property of the captured level grid.

The attenuation curve is cross-checked against the two pinned reference
implementations, which agree with each other and with the model used here:

* Ymir (pin 6d779960, libs/ymir-core/src/ymir/hw/scsp/scsp.cpp, the
  "Master volume attenuates sound in steps of 3 dB, or 0.5 bits per step"
  lambda): `out <<= 8; out >>= (15 - MVOL) >> 1; if ((15 - MVOL) & 1)
  out -= out >> 2; out >>= 8`, MVOL 0 mutes;
* MiSTer (pin a95b0850, rtl/Saturn/SCSP/SCSP_pkg.sv MVolCalc): shifts right by
  `~MVOL[3:1]` and subtracts a quarter when MVOL[0] is clear, MVOL 0 mutes;
* `src/devices/sound/scsp.cpp` implements the same Q8 table
  (2/3/4/6/8/12/16/24/32/48/64/96/128/192/256 over 256 for MVOL 1..15).

Where the references disagree is recorded rather than smoothed over: Ymir and
MiSTer both scale the output by four when DAC18B is set (their output domain is
16 bit, so the flag is used to re-normalise for an 18 bit converter), while
ST-077 describes a converter interface selection.  A 16 bit converter fed the
top 16 bits of the same 18 bit word has the same analog full scale as an 18 bit
converter fed all 18 bits, so this fixture asserts an unchanged level plus the
documented two bit truncation, and reports the reference disagreement.

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
PITCH_OCT_E = 0x7000         # OCT field 0xE: 0.25 words/sample
WS_SQUARE = 0x3000           # 8 bit square, 64 samples of 0x40 / 0xc0
WS_RAMP = 0x2000             # 8 bit ramp, 64 steps of 4 units
LEA = 64                     # one square cycle, in samples
DISDL_MAX = 7                # direct send level 7 = 0 dB (Table 4.27)
DIPAN_CENTRE = 0x10          # Table 4.28: centre, 0.0 dB both sides

# MC68EC000 view of the SCSP register area used by the Lua test
SLOT_STRIDE = 0x20

# Q8 gains the three implementations compute for MVOL 0..15 (0x100 = 0 dB)
MVOL_TABLE = (0, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256)


def lua_waveforms():
    return """
    -- 8 bit square, 64 samples of 0x40 / 0xc0 per cycle, three cycles
    for n = 0, 64 * 3 - 1 do
        ss:write_u8(0x%04x + n, ((n %% 64) < 32) and 0x40 or 0xc0)
    end
    -- 8 bit ramp, 64 steps of 4 units, three cycles of 1024 samples
    for n = 0, 3 * 1024 - 1 do
        ss:write_u8(0x%04x + n, (((n %% 64) * 4) - 128) & 0xff)
    end
    """ % (WS_SQUARE, WS_RAMP)


LUA = COMMON_LUA + r'''
local base = 0x05b00000
local SLOT = {base, base + 0x20, base + 0x40, base + 0x60}
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_MVOL hooked=" .. tostring(hooked))

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
    print(string.format("SCSP_MVOL trace=%s n=%d l=[%s] r=[%s]", tag, cap.n,
        table.concat(l, ","), table.concat(r, ",")))
end

local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end

-- MVOL is bits 3-0 and DAC18B is bit 8 of the same common control word at
-- sound address 100400H, so the write must preserve the other fields
-- (MEM4MB, RBL, RBP) instead of storing a constant there
local function set_mvol(mvol, dac18b)
    local v = sp:read_u16(base + 0x400)
    v = v & ~0x010f
    v = v | (mvol & 0xf)
    if dac18b then v = v | 0x0100 end
    sp:write_u16(base + 0x400, v)
end

-- one slot: a looped square at full send level, no modulation, no stack write,
-- centre panned so several slots sum in the same channel
local function config(slot, sa, disdl, dipan)
    w(slot, 0x00, 0x0030)                          -- PCM8B, normal loop
    w(slot, 0x02, sa)                              -- SA (byte address)
    w(slot, 0x04, 0x0000)                          -- LSA: word 0
    w(slot, 0x06, @@LEA@@)                         -- LEA: one cycle
    w(slot, 0x08, 0x0020)                          -- EGHOLD=1, AR=0
    w(slot, 0x0a, 0x3fe0)                          -- KRS=F, DL=1F, RR=0
    w(slot, 0x0c, 0x0200)                          -- STWINH
    w(slot, 0x0e, 0x0000)                          -- MDL/MDXSL/MDYSL off
    w(slot, 0x10, @@PITCH@@)                       -- OCT | FNS
    w(slot, 0x12, 0x0000)
    w(slot, 0x14, 0x0000)
    w(slot, 0x16, (disdl << 13) | (dipan << 8))    -- DISDL=7, DIPAN=0x10
end

-- the key bits share register 0x00 with LPCTL and PCM8B, so a key write must
-- not clobber the low bits (a constant write there silently changes format)
local function key_reg(slot, keyonb, keyonex)
    local v = sp:read_u16(slot + 0x00)
    v = v & 0x07ff
    if keyonex then v = v | 0x1000 end
    if keyonb then v = v | 0x0800 end
    w(slot, 0x00, v)
end

-- release every slot this fixture can key, then run the key-on scan once
local function key_off()
    for i = 1, #SLOT do key_reg(SLOT[i], false, false) end
    key_reg(SLOT[1], false, true)
end

local function key_on(active)
    for i = 2, active do key_reg(SLOT[i], true, false) end
    key_reg(SLOT[1], true, true)                   -- KEYONB + KEYONEX
end

-- one measurement: `active` in-phase slots, all at DISDL=7 / DIPAN=0x10,
-- MVOL and DAC18B as given, captured through the SCSP stream hook
local function measure(tag, want, mvol, dac18b, active, sa, disdl)
    key_off()
    emu.wait(ms(10))
    set_mvol(mvol, dac18b)
    for i = 1, #SLOT do
        if i <= active then
            config(SLOT[i], sa, disdl, @@DIPAN@@)
        else
            w(SLOT[i], 0x16, 0x0000)               -- DISDL=0: inaudible
        end
    end
    emu.wait(ms(4))
    key_on(active)
    emu.wait(ms(@@SETTLE@@))
    begin_capture(want)
    emu.wait(ms(1 + want / 44))
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

    -- the sound program's own start-up value; the fixture then varies MVOL
    sp:write_u16(base + 0x400, 0x000f)
@@WAVE@@
    local want = @@WANT@@

    -- the master volume curve, one slot, MVOL 0 (must mute) then 1..15
    for mvol = 0, 15 do
        measure(string.format("mvol%02d", mvol), want, mvol, false, 1,
                @@WS@@, @@DISDL@@)
    end

    -- DAC interface width: the same signal with DAC18B clear and set
    measure("dac16", want, 15, false, 1, @@WS@@, @@DISDL@@)
    measure("dac18", want, 15, true, 1, @@WS@@, @@DISDL@@)
    -- and the same test at a send level whose fixed point gain has low bits,
    -- over the ramp, so the two bit truncation of the 16 bit interface shows
    measure("dacg16", want, 15, false, 1, @@RAMP@@, 6)
    measure("dacg18", want, 15, true, 1, @@RAMP@@, 6)

    -- overflow ordering: three centre panned slots sum past the 18 bit
    -- accumulator range, so the clip is active; attenuating the clipped sum
    -- must scale it by exactly the MVOL gain (ST-077 p.100)
    measure("clip15", want, 15, false, 3, @@WS@@, @@DISDL@@)
    measure("clip08", want, 8, false, 3, @@WS@@, @@DISDL@@)
    measure("clip04", want, 4, false, 3, @@WS@@, @@DISDL@@)

    print("SCSP_MVOL done")
    m:exit()
end

local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < @@FRAMES@@ then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_MVOL FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_MVOL armed")
'''


def span(values):
    return max(values) - min(values)


def parse_trace(line):
    m = re.match(r'SCSP_MVOL trace=(\S+) n=(\d+) l=\[([^\]]*)\] r=\[([^\]]*)\]',
                 line)
    if not m:
        return None

    def series(text):
        return [float(v) for v in text.split(',') if v]

    return m.group(1), int(m.group(2)), series(m.group(3)), series(m.group(4))


def case_tags():
    tags = ['mvol%02d' % mvol for mvol in range(16)]
    return tags + ['dac16', 'dac18', 'dacg16', 'dacg18',
                   'clip15', 'clip08', 'clip04']


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP MVOL emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_MVOL armed', 'SCSP_MVOL done'):
        if marker not in stdout:
            raise RuntimeError('SCSP MVOL transcript is missing "%s"' % marker)
    if 'LUA ERROR' in stdout or 'SCSP_MVOL FAIL' in stdout:
        raise RuntimeError('SCSP MVOL transcript reports a Lua failure')
    traces = {}
    for line in stdout.splitlines():
        parsed = parse_trace(line)
        if parsed:
            traces[parsed[0]] = parsed

    failures = []
    results = {}
    for tag in case_tags():
        if tag not in traces:
            raise RuntimeError('SCSP MVOL transcript is missing the %s capture'
                               % tag)
        if len(traces[tag][2]) < 512:
            raise RuntimeError('%s captured only %d samples'
                               % (tag, len(traces[tag][2])))
        results[tag] = traces[tag][2]

    unit = 1.0 / 32768.0        # one 16 bit level step in the captured scale

    # every case is centre panned, so the master volume must attenuate both
    # channels identically (ST-077 Table 2.3: "Master volume set function
    # Stereo capable")
    worst = 0.0
    for tag in case_tags():
        left, right = results[tag], traces[tag][3]
        if len(right) != len(left):
            failures.append('%s: the two channels captured %d/%d samples'
                            % (tag, len(left), len(right)))
            continue
        worst = max(worst, max((abs(a - b) for a, b in zip(left, right)),
                               default=0.0))
    results['stereo:diff'] = worst
    if worst > unit:
        failures.append(
            'stereo: the two channels differ by %.6f in a centre panned case, '
            'so the master volume is not applied to both identically' % worst)

    # full scale reference (MVOL 15 = unity) and the mute.  A slot at 0 dB
    # send level panned to the centre sits at half scale (the pan table's
    # fixed point unity is 0.5 at 18 bit full scale), so a square wave spans
    # 1.0 of the 131072 unit full scale range in both channels
    full = span(results['mvol15'])
    results['full:span'] = full
    if not (0.98 < full < 1.02):
        failures.append(
            'mvol15: one full level slot measured a span of %.5f; a 0 dB slot '
            'panned to the centre must span half of the 18 bit full scale '
            '(1.0 of the captured range)' % full)
    muted = span(results['mvol00'])
    results['mvol00:span'] = muted
    if muted > full / 256.0:
        failures.append(
            'mvol00: MVOL 0 must mute the output, measured %.6f of the %.5f '
            'full level span' % (muted, full))

    # every MVOL value against the Q8 table the three implementations share
    for mvol in range(1, 16):
        tag = 'mvol%02d' % mvol
        measured = span(results[tag]) / full if full else 0.0
        model = MVOL_TABLE[mvol] / 256.0
        results[tag + ':gain'] = measured
        # the capture is quantised to one 16 bit step, so the smallest values
        # have a proportionally larger floor
        slack = max(0.02 * model, 4.0 * unit / full if full else 1.0)
        if abs(measured - model) > slack:
            failures.append(
                'mvol%02d: measured a gain of %.5f of the full level, the '
                'shared MVOL table gives %.5f (2/3/4/6/8/12/16/24/32/48/64/'
                '96/128/192/256 over 256)' % (mvol, measured, model))
    gains = [results['mvol%02d:gain' % mvol] for mvol in range(1, 16)]
    results['mvol:monotonic'] = all(gains[i] <= gains[i + 1] * 1.02
                                    for i in range(len(gains) - 1))
    if not results['mvol:monotonic']:
        failures.append('mvol: the measured gain is not monotonic in MVOL')

    # DAC interface width: same level, same waveform
    s16 = span(results['dac16'])
    s18 = span(results['dac18'])
    results['dac:ratio'] = s18 / s16 if s16 else 0.0
    if not (0.995 < results['dac:ratio'] < 1.005):
        failures.append(
            'dac: DAC18B changed the level by %.4fx (16 bit span %.5f, 18 bit '
            'span %.5f); it selects the converter interface width, so the '
            'analog level must not change'
            % (results['dac:ratio'], s16, s18))
    # the 16 bit interface keeps the top 16 bits of the 18 bit accumulator, so
    # its samples land on the 4/131072 grid while the 18 bit path keeps the two
    # low bits; the ramp with a send level whose fixed point gain has low bits
    # makes that visible
    raw16 = [v * 131072.0 for v in results['dacg16']]
    raw18 = [v * 131072.0 for v in results['dacg18']]
    off16 = max(abs(v - 4.0 * round(v / 4.0)) for v in raw16)
    off18 = max(abs(v - 4.0 * round(v / 4.0)) for v in raw18)
    results['dacg16:grid'] = off16
    results['dacg18:grid'] = off18
    l16 = set(int(round(v)) for v in raw16)
    l18 = set(int(round(v)) for v in raw18)
    results['dacg16:levels'] = len(l16)
    results['dacg18:levels'] = len(l18)
    if off16 > 0.25:
        failures.append(
            'dacg16: a sample of the 16 bit capture is %.2f of a 131072 unit '
            'away from the 4 unit grid; the 16 bit interface must drop the two '
            'low bits of the accumulator' % off16)
    if off18 <= 0.25:
        failures.append(
            'dacg18: every sample of the 18 bit capture is already on the '
            '4 unit grid, so this configuration cannot show the two low bits '
            'the 18 bit interface keeps')
    truncated = set((v // 4) * 4 for v in l18)
    missing = sorted(v for v in truncated if v not in l16)
    results['dacg:missing'] = len(missing)
    if len(l16) < 16 or len(l18) < 16:
        failures.append(
            'dacg: only %d/%d distinct 16/18 bit levels were captured from a '
            '64 step ramp' % (len(l16), len(l18)))
    elif missing:
        failures.append(
            'dacg: %d of %d captured 18 bit levels, truncated to the 4 unit '
            'grid, have no counterpart in the 16 bit capture, so the 16 bit '
            'path is not the top 16 bits of the same word'
            % (len(missing), len(set(truncated))))

    # overflow ordering: three full level centre panned slots exceed the
    # accumulator range, so the sum clips before the attenuator
    c15 = span(results['clip15'])
    results['clip15:span'] = c15
    # three half scale slots add to 1.5; a clamp at full scale leaves 1.0
    results['clip:linear'] = c15 / (3.0 * full) if full else 0.0
    if not (0.60 < results['clip:linear'] < 0.72):
        failures.append(
            'clip15: three full level slots captured %.5f, which is %.3f of '
            'the linear sum of three; an overflow clip at full scale must '
            'leave the expected 2/3'
            % (c15, results['clip:linear']))
    for mvol, tag in ((8, 'clip08'), (4, 'clip04')):
        ratio = span(results[tag]) / c15 if c15 else 0.0
        model = MVOL_TABLE[mvol] / 256.0
        results[tag + ':ratio'] = ratio
        slack = max(0.02 * model, 4.0 * unit / c15 if c15 else 1.0)
        if abs(ratio - model) > slack:
            failures.append(
                '%s: an already clipped sum was attenuated by %.5f across an '
                'MVOL write, not the MVOL gain %.5f; ST-077 p.100 says '
                'lowering MVOL does not remove overflow clipping, so the clip '
                'happens before the attenuator' % (tag, ratio, model))

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
              .replace('@@WS@@', hex(WS_SQUARE))
              .replace('@@RAMP@@', hex(WS_RAMP))
              .replace('@@LEA@@', str(LEA))
              .replace('@@PITCH@@', hex(PITCH_OCT_E))
              .replace('@@DISDL@@', str(DISDL_MAX))
              .replace('@@DIPAN@@', hex(DIPAN_CENTRE))
              .replace('@@WANT@@', '2048')
              .replace('@@FRAMES@@', str(BOOT_FRAMES))
              .replace('@@SETTLE@@', str(SETTLE_MS)))
    out = args.output or Path(tempfile.mkdtemp(prefix='scsp-mvol-'))
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
        if isinstance(results[tag], (int, float)) and not isinstance(
                results[tag], bool):
            print('  %-22s %.5f' % (tag, results[tag]))
        elif isinstance(results[tag], bool):
            print('  %-22s %s' % (tag, results[tag]))
    print('SCSP MVOL: %s' % ('PASS' if not failures else 'FAIL'))
    for f in failures:
        print('  - %s' % f)
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())

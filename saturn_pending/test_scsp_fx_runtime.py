#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Native SCSP send-level tables and DSP effect return qualification.

Two mixer stages the other fixtures hold constant or do not reach:

* the **direct send level** (DISDL, slot register 0x16 bits 15-13) - ST-077-R2-052594
  Table 4.27 gives 0 = not sent, then 6 dB steps from -36 dB (1) to 0 dB (7);
  every earlier fixture pinned DISDL at 7;
* the **effect return**: a DSP program leaves a value in EFREG and the mixer
  returns it through the sending slot's EFSDL (bits 7-5) and EFPAN (bits 4-0),
  Tables 4.29 and 4.30.  The effect half of "effects-heavy playback" is
  reachable without the CD block, unlike the EXTS (external digital input) half
  which is fed by the CD device route.

Method: the direct send level is measured on an 8 bit square wave (spans scale
exactly with the table), and the effect return on a **constant** EFREG value -
the probe that established this fixture showed the return of a microprogram's
EFREG[0] is a DC level, so the static tables can be compared directly in the
captured floats instead of through span ratios.  All captures come from the
per-device Lua sound hook on the `:scsp` stream (`-sound none`), as the
FM/EG/PCM/MVOL fixtures do.

Tolerances are set so the documented curves are *discriminated*, not merely
matched, and the one reference disagreement is recorded rather than smoothed
over: ST-077 labels the send-level steps -6 dB (0.50119 per step) while the
MiSTer core's `LevelCalc` is a shift, `WAVE >>> (~SDL)`, i.e. 0.5 per step; the
two differ by 0.24% per step and 1.2% over the six steps below 0 dB, so the
0.6% model tolerance accepts the table ST-077 documents and rejects the shift.
For the same reason the pan check separates Table 4.30's -3 dB steps (0.70795)
from MiSTer's `PanLCalc` shift (0.75 at PAN 01H) by 5.6%.  The measured curve
sits 0.011% from the ideal -6 dB value, which is the emulator's fixed-point
table rounding, not model error.

The microprogram is the one already used by the mapped-DSP fixtures
(`test_scsp_dsp_runtime.py`): step 127 does EWT+EWA=0 with the accumulator fed
from sound RAM, so EFREG[0] = MEMS[0] scaled by the coefficient path.  The
fixture reads EFREG[0] back through the register file and refuses to measure the
tables unless it holds the expected value, so a broken setup cannot be mistaken
for a gain measurement.

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
CAPTURE = 1024               # samples per case
PITCH_OCT_E = 0x7000         # OCT field 0xE: 0.25 words/sample
WS_SQUARE = 0x3000           # 8 bit square, 64 samples of 0x40 / 0xc0
WS_DC = 0x05a08000           # full SH-2 address of the DSP effect source
LEA = 64                     # one square cycle, in samples
DISDL_MAX = 7                # direct send level 7 = 0 dB (Table 4.27)
EFSDL_MAX = 7                # effect send level 7 = 0 dB (Table 4.29)
DIPAN_CENTRE = 0x10          # Table 4.28: centre, 0.0 dB both sides

# 6 dB per table step as a linear gain: Tables 4.27 and 4.29 are the same curve
STEP = 10.0 ** (-6.0 / 20.0)     # 0.501187
TABLE_GAIN = [0.0] + [STEP ** (7 - level) for level in range(1, 8)]

# Table 4.30 pan steps are 3 dB per unit away from centre, 31 positions
PAN_STEP = 10.0 ** (-3.0 / 20.0)  # 0.707946

# effect return pan positions measured in both channels
PAN_CASES = (0x10, 0x1f, 0x0f, 0x01, 0x11)


def lua_waveforms():
    return """
    -- 8 bit square, 64 samples of 0x40 / 0xc0 per cycle, three cycles
    for n = 0, 64 * 3 - 1 do
        ss:write_u8(0x%04x + n, ((n %% 64) < 32) and 0x40 or 0xc0)
    end
    """ % WS_SQUARE


LUA = COMMON_LUA + r'''
local base = 0x05b00000
local slot0 = base
local hooked = false
for _, s in pairs(m.sounds) do
    if s.device.tag == ":scsp" then s.hook = true; hooked = true end
end
print("SCSP_FX hooked=" .. tostring(hooked))

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
    print(string.format("SCSP_FX trace=%s n=%d l=[%s] r=[%s]", tag, cap.n,
        table.concat(l, ","), table.concat(r, ",")))
end

local function w(slot, off, val) sp:write_u16(slot + off, val) end
local function ms(t) return emu.attotime.from_msec(t) end

local function blank()
    local c = {}
    for i = 1, 512 do c[i] = 0 end
    return c
end

local function upload(code)
    for i = 1, 512 do sp:write_u16(base + 0x800 + (i - 1) * 2, code[i]) end
    sp:write_u16(base + 0xbf0, code[505])
end

-- the mapped-DSP fixture's program: step 127 leaves the accumulator in
-- EFREG[0] through EWT+EWA=0, fed from sound RAM by an earlier step
local function code_for(last)
    local code = blank()
    code[3] = 0x1002; code[6] = 0x20; code[7] = 2
    code[last * 4 + 2] = 0xa000
    code[last * 4 + 3] = 0xa002
    code[last * 4 + 4] = 0x100
    return code
end

-- one slot: a looped wave form, no modulation, no stack write
local function config(slot, sa, disdl, dipan, efsdl)
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
    w(slot, 0x16, (disdl << 13) | (dipan << 8) | (efsdl << 5))  -- no EFPAN
end

-- the key bits share register 0x00 with LPCTL and PCM8B: preserve the low bits
local function key_reg(slot, keyonb, keyonex)
    local v = sp:read_u16(slot + 0x00)
    v = v & 0x07ff
    if keyonex then v = v | 0x1000 end
    if keyonb then v = v | 0x0800 end
    w(slot, 0x00, v)
end

local function key_off()
    key_reg(slot0, false, true)
end

local function key_on()
    key_reg(slot0, true, true)
end

local function measure(tag, want)
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

    sp:write_u16(base + 0x400, 0x000f)             -- MVOL 15: unity
@@WAVE@@
    local want = @@WANT@@
    -- Stop the 68000 BIOS sound program: it owns the SCSP while it runs and
    -- rewrites the DSP program, which would race the effect-return setup.
    ss:write_u16(0x70000, 0x60fe)
    snd.state["SR"].value = 0x2700
    snd.state["PC"].value = 0x70000
    emu.wait(ms(20))

    -- Section 1: direct send level.  Slot 0 plays the square at each DISDL
    -- value, the EFSDL bits stay 0 so the effect return contributes nothing.
    for disdl = 0, @@DISDL@@ do
        key_off()
        emu.wait(ms(10))
        config(slot0, @@WS@@, disdl, @@DIPAN@@, 0)
        emu.wait(ms(4))
        key_on()
        emu.wait(ms(@@SETTLE@@))
        measure(string.format("dsend%d", disdl), want)
    end

    -- Section 2: effect return.  No slot is keyed, so only the DSP path can
    -- reach the mixer; slot 0 carries the EFSDL/EFPAN gain under test.
    key_off()
    w(slot0, 0x16, 0)
    emu.wait(ms(10))
    sp:write_u16(base + 0x402, 0)                  -- RBL/RBP: ring buffer off
    do                                             -- clear TEMP/ACC/MEMS
        local clear = blank()                      -- through real steps
        for i = 0, 127 do
            clear[i * 4 + 1] = 0x80 | i
            clear[i * 4 + 2] = 0x2000
            clear[i * 4 + 3] = 2
            clear[i * 4 + 4] = 0x200
        end
        upload(clear)
        emu.wait(ms(2))
    end
    sp:write_u16(base + 0x700, 0x7ff8)             -- COEF: near unity
    sp:write_u16(base + 0x702, 0)
    sp:write_u16(base + 0x780, 0x4000)             -- MADRS[0]: the read address
    sp:write_u16(@@WS_DC@@, 0x1234)
    upload(code_for(127))
    emu.wait(ms(100))
    local efreg = sp:read_u16(base + 0xec0)
    print(string.format("SCSP_FX efreg=%04x", efreg))
    assert(efreg ~= 0, "no effect value in EFREG: the return tables cannot be measured")

    for efsdl = 0, @@EFSDL@@ do
        w(slot0, 0x16, (efsdl << 5) | 0x10)        -- EFPAN: centre
        emu.wait(ms(20))
        measure(string.format("efx%d", efsdl), want)
    end
    for _, pan in ipairs({@@PANS@@}) do
        w(slot0, 0x16, (@@EFSDL@@ << 5) | pan)     -- EFSDL: 0 dB
        emu.wait(ms(20))
        measure(string.format("efpan%02x", pan), want)
    end

    print("SCSP_FX done")
    m:exit()
end

local frames = 0
emu.register_frame_done(function()
    frames = frames + 1
    if started or frames < @@FRAMES@@ then return end
    started = true
    coroutine.wrap(function()
        local ok, err = pcall(test)
        if not ok then print("SCSP_FX FAIL " .. tostring(err)); m:exit() end
    end)()
end)
print("SCSP_FX armed")
'''


def span(values):
    return max(values) - min(values)


def level(values):
    """Static level of a capture: the median, after checking it is static."""
    return statistics.median(values)


def parse_trace(line):
    m = re.match(r'SCSP_FX trace=(\S+) n=(\d+) l=\[([^\]]*)\] r=\[([^\]]*)\]',
                 line)
    if not m:
        return None

    def series(text):
        return [float(v) for v in text.split(',') if v]

    return m.group(1), int(m.group(2)), series(m.group(3)), series(m.group(4))


def case_tags():
    tags = ['dsend%d' % d for d in range(0, DISDL_MAX + 1)]
    tags += ['efx%d' % e for e in range(0, EFSDL_MAX + 1)]
    tags += ['efpan%02x' % p for p in PAN_CASES]
    return tags


def validate_output(stdout, rc):
    if rc != 0:
        raise RuntimeError('SCSP FX emulator run failed with rc=%d' % rc)
    for marker in ('SCSP_FX armed', 'SCSP_FX done'):
        if marker not in stdout:
            raise RuntimeError('SCSP FX transcript is missing "%s"' % marker)
    if 'LUA ERROR' in stdout or 'SCSP_FX FAIL' in stdout:
        raise RuntimeError('SCSP FX transcript reports a Lua failure')
    m = re.search(r'SCSP_FX efreg=([0-9a-f]+)', stdout)
    if not m:
        raise RuntimeError('SCSP FX transcript has no EFREG read-back')
    efreg = int(m.group(1), 16)

    traces = {}
    for line in stdout.splitlines():
        parsed = parse_trace(line)
        if parsed:
            traces[parsed[0]] = parsed

    failures = []
    results = {}
    for tag in case_tags():
        if tag not in traces:
            raise RuntimeError('SCSP FX transcript is missing the %s capture'
                               % tag)
        if len(traces[tag][2]) < 512:
            raise RuntimeError('%s captured only %d samples'
                               % (tag, len(traces[tag][2])))
        left, right = traces[tag][2], traces[tag][3]
        results[tag + ':l'] = level(left)
        results[tag + ':r'] = level(right)
        results[tag + ':lspan'] = span(left)
        results[tag + ':rspan'] = span(right)

    results['efreg'] = float(efreg)

    # --- Section 1: direct send level ------------------------------------
    full = span(traces['dsend%d' % DISDL_MAX][2])
    results['dsend:full'] = full
    if full <= 0:
        failures.append('dsend%d: the 0 dB direct send level is silent'
                        % DISDL_MAX)
    for disdl in range(0, DISDL_MAX):
        tag = 'dsend%d' % disdl
        measured = span(traces[tag][2]) / full if full else 0.0
        model = TABLE_GAIN[disdl]
        results[tag + ':gain'] = measured
        if disdl == 0:
            if measured > 0.0:
                failures.append(
                    'dsend0: DISDL 0 must not send the slot to the D/A '
                    'converter (Table 4.27), measured %.6f of the 0 dB span'
                    % measured)
            continue
        # the capture is quantised to one 16 bit step over the full scale span;
        # the model tolerance is tight enough to reject a halving per step
        slack = max(0.006 * model, 6.0 / 32768.0 / full)
        if abs(measured - model) > slack:
            failures.append(
                'dsend%d: direct send level measured %.5f of the 0 dB level, '
                'Table 4.27 gives %.5f (-%d dB)' % (disdl, measured, model,
                                                    6 * (7 - disdl)))
    results['dsend%d:gain' % DISDL_MAX] = 1.0
    gains = [results['dsend%d:gain' % d] for d in range(1, DISDL_MAX + 1)]
    results['dsend:monotonic'] = all(gains[i] < gains[i + 1] * 1.02
                                     for i in range(len(gains) - 1))
    if not results['dsend:monotonic']:
        failures.append('dsend: the direct send level is not monotonic in DISDL')

    # --- Section 2: effect send level ------------------------------------
    fx_full = results['efx%d:l' % EFSDL_MAX]
    results['efx:full'] = fx_full
    if fx_full <= 0:
        failures.append('efx%d: the 0 dB effect return is silent'
                        % EFSDL_MAX)
    static = max(results['efx%d:lspan' % e] for e in range(1, EFSDL_MAX + 1))
    results['efx:static'] = static
    if static > 2.0 / 32768.0:
        failures.append(
            'efx: a constant EFREG return measured a span of %.6f; the effect '
            'return of a DC program must be a DC level' % static)
    for efsdl in range(0, EFSDL_MAX):
        measured = results['efx%d:l' % efsdl] / fx_full if fx_full else 0.0
        model = TABLE_GAIN[efsdl]
        results['efx%d:gain' % efsdl] = measured
        if efsdl == 0:
            if measured != 0.0:
                failures.append(
                    'efx0: EFSDL 0 must not send the effect return (Table '
                    '4.29), measured %.6f of the 0 dB level' % measured)
            continue
        slack = max(0.006 * model,
                    6.0 / 32768.0 / fx_full if fx_full else 1.0)
        if abs(measured - model) > slack:
            failures.append(
                'efx%d: effect send level measured %.5f of the 0 dB level, '
                'Table 4.29 gives %.5f (-%d dB)' % (efsdl, measured, model,
                                                    6 * (7 - efsdl)))

    # --- Section 2: effect pan -------------------------------------------
    # Table 4.30: 00H..0FH move the image right (left attenuates 3 dB per
    # step), 10H is centre, 11H..1FH move it left (right attenuates).
    centre_l, centre_r = results['efpan10:l'], results['efpan10:r']
    results['efpan:centre'] = centre_l
    if centre_l <= 0 or abs(centre_l - centre_r) > 2.0 / 32768.0:
        failures.append(
            'efpan10: the centre position measured %.6f/%.6f, the two channels '
            'must be equal and non-zero' % (centre_l, centre_r))
    pan_model = {
        0x1f: (1.0, 0.0), 0x0f: (0.0, 1.0), 0x10: (1.0, 1.0),
        0x01: (PAN_STEP, 1.0), 0x11: (1.0, PAN_STEP),
    }
    for pan in PAN_CASES:
        tag = 'efpan%02x' % pan
        ml, mr = pan_model[pan]
        el = results[tag + ':l'] / centre_l if centre_l else 0.0
        er = results[tag + ':r'] / centre_r if centre_r else 0.0
        results[tag + ':lratio'] = el
        results[tag + ':rratio'] = er
        for name, measured, model in (('left', el, ml), ('right', er, mr)):
            slack = max(0.02 * model,
                        6.0 / 32768.0 / centre_l if centre_l else 1.0)
            if abs(measured - model) > slack:
                failures.append(
                    '%s: EFPAN %02x measured %.5f of the centre level in the '
                    '%s channel, Table 4.30 gives %.5f'
                    % (tag, pan, measured, name, model))

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

    pans = ', '.join('0x%02x' % p for p in PAN_CASES)
    lua = (LUA.replace('@@WAVE@@', lua_waveforms())
              .replace('@@WS@@', hex(WS_SQUARE))
              .replace('@@WS_DC@@', hex(WS_DC))
              .replace('@@LEA@@', str(LEA))
              .replace('@@PITCH@@', hex(PITCH_OCT_E))
              .replace('@@DISDL@@', str(DISDL_MAX))
              .replace('@@EFSDL@@', str(EFSDL_MAX))
              .replace('@@DIPAN@@', hex(DIPAN_CENTRE))
              .replace('@@PANS@@', pans)
              .replace('@@WANT@@', str(CAPTURE))
              .replace('@@FRAMES@@', str(BOOT_FRAMES))
              .replace('@@SETTLE@@', str(SETTLE_MS)))
    out = args.output or Path(tempfile.mkdtemp(prefix='scsp-fx-'))
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
            print('  %-24s %.6f' % (tag, results[tag]))
    print('SCSP FX: %s' % ('PASS' if not failures else 'FAIL'))
    for f in failures:
        print('  - %s' % f)
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())

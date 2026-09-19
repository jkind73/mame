#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""SCSP envelope-generator result-parser controls; no emulator execution.

The fixture accepts a transcript only when every measured staircase matches the
tabulated rate model, so the controls here work in both directions:

* a transcript synthesised from the model itself must be accepted (the
  validator cannot merely reject everything), and
* the same transcript with one case's envelope replaced by a different rate,
  pattern, segment or hold must be rejected.

Each mutant is exactly the class of error the native run exists to catch: a
wrong gating shift (the pre-fix LFO scale error moved every step by 256), a
wrong attack law, a wrong segment transition, or a missing documented hold.
"""
import test_scsp_eg_runtime as fixture

PREFIX = 100


def rle(trace):
    runs = []
    for v in trace:
        if runs and runs[-1][1] == v:
            runs[-1][0] += 1
        else:
            runs.append([1, v])
    return ','.join('%d:%d' % (run, v) for run, v in runs)


def trace_for(case, **kwargs):
    name, kind, ar, d1r, d2r, rr, dl, krs, oct, eghold, ms = case
    n = int(round(ms * 44.1))
    pre = 0 if kind == 'on' else int(round((ms + 400) * 44.1))
    q = fixture.model_q(case, 0, 0, pre, n, **kwargs) if kwargs else \
        fixture.model_q(case, 0, 0, pre, n)
    if kind == 'off' and eghold:
        # the chip holds the attack level while keyed on, so the capture opens
        # with the held output before the key-off edge
        q = [4096] * PREFIX + q
    return q


def replace(case, **fields):
    names = ('name', 'kind', 'ar', 'd1r', 'd2r', 'rr', 'dl', 'krs', 'oct',
             'eghold', 'ms')
    return tuple(fields.get(k, v) for k, v in zip(names, case))


def transcript(overrides=None):
    lines = ['SCSP_EG hooked=true', 'SCSP_EG armed',
             'SCSP_EG calib n=1764 mean=0.500000']
    for case in fixture.CASES:
        q = (overrides or {}).get(case[0]) or trace_for(case)
        lines.append('SCSP_EG case=%s n=%d rle=[%s]' % (case[0], len(q), rle(q)))
    lines.append('SCSP_EG done')
    return '\n'.join(lines) + '\n'


def accepts(text, rc=0):
    results = fixture.validate_output(text, rc)
    assert len(results) == len(fixture.CASES), 'unexpected case count'
    return results


def rejects(text, rc=0, label=''):
    try:
        fixture.validate_output(text, rc)
    except RuntimeError:
        return
    raise AssertionError('mutated SCSP EG output accepted: %s' % label)


baseline = transcript()
accepts(baseline)
print('model-synthesised SCSP EG transcript accepted (%d cases)'
      % len(fixture.CASES))

# a non-zero exit status, missing markers and Lua failures are always fatal
rejects('', 1, 'exit status')
rejects(baseline.replace('SCSP_EG armed\n', ''), 0, 'missing armed marker')
rejects(baseline.replace('SCSP_EG done', ''), 0, 'missing done marker')
rejects(baseline + 'LUA ERROR x\n', 0, 'lua error')
rejects(baseline.replace('SCSP_EG calib n=1764 mean=0.500000\n', ''), 0,
        'missing calibration')
rejects(baseline.replace('mean=0.500000', 'mean=0.000000'), 0,
        'silent calibration')

# structural damage
rejects(baseline.replace('case=ar10', 'case=nosuch'), 0, 'unknown case')
rejects('\n'.join(line for line in baseline.splitlines()
                  if 'case=rr10 ' not in line) + '\n', 0, 'missing case')
rejects(baseline.replace('case=dl08 n=2646', 'case=dl08 n=9999'), 0,
        'run table does not cover the capture')

# wrong hardware behaviour with the same registers
MUTANTS = {
    # twice the attack rate: eff+1 halves the gating shift
    'ar08': lambda c: trace_for(c, rate_bias=1),
    # a linear attack instead of the geometric ramp
    'ar10': lambda c: trace_for(c, linear_attack=True),
    # the release the RR = 08H row produces, a whole table step slower
    'rr10': lambda c: trace_for(replace(fixture.CASES_BY_NAME['rr10'],
                                        name='rr10', rr=0x08)),
    # decay 2 entered at a level DL does not select
    'dl08': lambda c: [min(4096, v + 260) for v in trace_for(c)],
    # EGHOLD ignored: the attack level moves immediately
    'eg_hold': lambda c: trace_for(replace(c, eghold=0)),
    # the documented "change volume 0" rates drifting instead of holding
    'ar00': lambda c: trace_for(replace(c, ar=0x1f)),
    'rr00': lambda c: trace_for(replace(c, rr=0x1f)),
}
for name, mutate in MUTANTS.items():
    rejects(transcript({name: mutate(fixture.CASES_BY_NAME[name])}), 0,
            'wrong envelope for ' + name)

# silence everywhere is not a pass
rejects(transcript({c[0]: [0] * len(trace_for(c)) for c in fixture.CASES}), 0,
        'all-silent capture')

print('SCSP EG result-parser controls passed: %d mutants rejected'
      % (len(MUTANTS) + 9))

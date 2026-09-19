#!/usr/bin/env python3
# license:BSD-3-Clause
"""SCSP LFO result-parser controls; no emulator execution.

A fully valid transcript embeds measured transition indices that depend on the
emulator's exact phase at each capture start, so there is no synthetic
"positive" transcript. This exercises the negative path instead: malformed,
truncated, and inconsistent transcripts must all be rejected, never accepted.
"""
import test_scsp_lfo_runtime as fixture


def rejects(text, rc=0):
    try:
        fixture.validate_output(text, rc)
    except RuntimeError:
        return
    raise AssertionError('malformed SCSP LFO output accepted')


# non-zero exit must always fail
rejects('', 1)
# a LUA error / injected failure must fail
rejects('SCSP_LFO armed\nSCSP_LFO FAIL injected\n', 0)
rejects('SCSP_LFO armed\nLUA ERROR x\n', 0)
# missing the final done marker
rejects('SCSP_LFO armed\nSCSP_LFO calibrate n=4410 min=0.5 max=0.5 mean=0.5 rough=0 trans=0 t=[] w=[]\n', 0)
# calibration not a flat DC level
rejects('SCSP_LFO calibrate n=4410 min=0.1 max=0.5 mean=0.5 rough=0 trans=0 t=[] w=[]\n'
        'SCSP_LFO done\n', 0)
# a full-but-wrong transcript: every amp case reports no modulation, which the
# pre-fix (8.8 accumulator) binary actually produced at the slow end
rows = ['SCSP_LFO calibrate n=4410 min=0.500000 max=0.500000 mean=0.500000 rough=0.000000 trans=0 t=[] w=[]']
for lfof in range(32):
    rows.append('SCSP_LFO amp lfof=%d n=13230 min=0.031250 max=0.031250 mean=0.031250 rough=0.000000 trans=0 t=[] w=[]' % lfof)
rows.append('SCSP_LFO done')
rejects('\n'.join(rows), 0)
print('SCSP LFO result-parser negative controls passed (no emulator execution)')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""SCSP DSP result-parser controls; no emulator execution."""
from test_scsp_dsp_runtime import validate_output
rows=[f'SCSP_DSP case={i} PASS\n' for i in range(1,32)]
final='SCSP_DSP PASS cases=31\n';good=''.join(rows)+final
validate_output(good,0)
bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
     good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
     good.replace('cases=31','cases=30'),good+'SCSP_DSP FAIL injected\n',
     good+'LUA ERROR injected\n',good.replace('cases=31\n','cases=31 extra\n')]
for text in bad:
    try:validate_output(text,0)
    except RuntimeError:pass
    else:raise AssertionError('malformed output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('14 SCSP DSP result-parser controls passed (no emulator execution)')

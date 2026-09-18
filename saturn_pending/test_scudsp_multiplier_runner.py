#!/usr/bin/env python3
# license:BSD-3-Clause
"""DSP multiplier result-parser controls; not emulator qualification."""
from test_scudsp_multiplier_runtime import validate_output
rows=[f'DSP_MUL case={i} PASS\n' for i in range(1,65)]
final='DSP_MUL PASS cases=64\n'
good=''.join(rows)+final
validate_output(good,0)
for bad in [final,''.join(rows[:-1])+final,''.join(rows[::-1])+final,
            good+rows[0],good+final,''.join(rows),good.replace('case=1 ','case=0 '),
            good+'DSP_MUL FAIL deliberate\n',good+'LUA ERROR deliberate\n',
            good.replace('cases=64\n','cases=64 extra\n')]:
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('12 DSP multiplier result-parser controls passed (no emulator execution)')

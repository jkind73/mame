#!/usr/bin/env python3
# license:BSD-3-Clause
"""DSP read-DMA result-parser controls; not emulator qualification."""
from test_scudsp_read_runtime import validate_output
rows=[f'DSP_READ case={i} PASS\n' for i in range(1,1025)]
final='DSP_READ PASS cases=1024\n'
good=''.join(rows)+final
validate_output(good,0)
for bad in [final,''.join(rows[:-1])+final,''.join(rows[::-1])+final,
            good+rows[0],good+final,''.join(rows),good.replace('case=1 ','case=0 '),
            good+'DSP_READ FAIL deliberate\n',good+'LUA ERROR deliberate\n',
            good.replace('cases=1024\n','cases=1024 extra\n')]:
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('12 DSP read DMA result-parser controls passed (no emulator execution)')

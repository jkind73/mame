#!/usr/bin/env python3
# license:BSD-3-Clause
"""pause output parser controls, not emulator execution."""
from test_scudsp_pause_runtime import validate_output
rows=[f'DSP_PAUSE case={i} PASS\n' for i in range(1,7)]
final='DSP_PAUSE PASS cases=6\n';good=''.join(rows)+final
validate_output(good,0)
bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
     good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
     good.replace('cases=6','cases=5'),good+'DSP_PAUSE FAIL injected\n',
     good+'LUA ERROR injected\n',good.replace('cases=6\n','cases=6 extra\n')]
for text in bad:
    try: validate_output(text,0)
    except RuntimeError: pass
    else: raise AssertionError('malformed output accepted')
try: validate_output(good,1)
except RuntimeError: pass
else: raise AssertionError('nonzero exit accepted')
print('14 pause result-parser controls passed (no emulator execution)')

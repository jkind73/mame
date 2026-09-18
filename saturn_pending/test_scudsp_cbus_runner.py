#!/usr/bin/env python3
# license:BSD-3-Clause
"""C-bus output parser controls, not emulator execution."""
from test_scudsp_cbus_runtime import validate_output
rows=[f'DSP_CBUS case={i} PASS\n' for i in range(1,513)]
final='DSP_CBUS PASS cases=512\n';good=''.join(rows)+final
validate_output(good,0)
bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
     good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
     good.replace('cases=512','cases=511'),good+'DSP_CBUS FAIL injected\n',
     good+'LUA ERROR injected\n',good.replace('cases=512\n','cases=512 extra\n')]
for text in bad:
    try: validate_output(text,0)
    except RuntimeError: pass
    else: raise AssertionError('malformed output accepted')
try: validate_output(good,1)
except RuntimeError: pass
else: raise AssertionError('nonzero exit accepted')
print('14 C-bus result-parser controls passed (no emulator execution)')

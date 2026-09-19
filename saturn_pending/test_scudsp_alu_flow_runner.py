#!/usr/bin/env python3
# license:BSD-3-Clause
"""ALU-flow output parser controls, not emulator execution."""
from test_scudsp_alu_flow_runtime import validate_output
rows=[f'DSP_ALU_FLOW case={i} PASS\n' for i in range(1,193)]
final='DSP_ALU_FLOW PASS cases=192\n';good=''.join(rows)+final
validate_output(good,0)
bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
     good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
     good.replace('cases=192','cases=191'),good+'DSP_ALU_FLOW FAIL injected\n',
     good+'LUA ERROR injected\n',good.replace('cases=192\n','cases=192 extra\n')]
for text in bad:
    try: validate_output(text,0)
    except RuntimeError: pass
    else: raise AssertionError('malformed output accepted')
try: validate_output(good,1)
except RuntimeError: pass
else: raise AssertionError('nonzero exit accepted')
print('14 ALU-flow result-parser controls passed (no emulator execution)')

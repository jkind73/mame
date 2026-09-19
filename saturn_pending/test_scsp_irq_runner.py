#!/usr/bin/env python3
# license:BSD-3-Clause
"""SCSP IRQ result-parser controls; no emulator execution."""
from test_scsp_irq_runtime import validate_output
rows=[f'SCSP_IRQ case={i} PASS\n' for i in range(1,433)]
final='SCSP_IRQ PASS cases=432\n';good=''.join(rows)+final
validate_output(good,0)
bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
     good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
     good.replace('cases=432','cases=431'),good+'SCSP_IRQ FAIL injected\n',
     good+'LUA ERROR injected\n',good.replace('cases=432\n','cases=432 extra\n')]
for text in bad:
    assert text!=good, 'negative control must change the transcript'
    try:validate_output(text,0)
    except RuntimeError:pass
    else:raise AssertionError('malformed output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('14 SCSP IRQ result-parser controls passed (no emulator execution)')

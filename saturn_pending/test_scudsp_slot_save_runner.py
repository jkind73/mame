#!/usr/bin/env python3
# license:BSD-3-Clause
"""DSP pending-slot save result-parser controls; actual file handling uses the shared runner."""
from test_scudsp_slot_save_runtime import validate_output
stages=['DSP_SLOT_SAVE saved\n','DSP_SLOT_SAVE mutated\n','DSP_SLOT_SAVE loaded\n']
final='DSP_SLOT_SAVE PASS wrapped=1 pending=1 replay=exact\n'
good=''.join(stages)+final
validate_output(good,0)
for bad in [final, ''.join(stages[:-1])+final, ''.join(stages[::-1])+final,
            good+stages[0],good+final,''.join(stages),good.replace('pending=1','pending=0'),
            good.replace('wrapped=1','wrapped=0'),good+'DSP_SLOT_SAVE FAIL deliberate\n',
            good+'LUA ERROR deliberate\n',good.replace('replay=exact\n','replay=exact extra\n')]:
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid replay output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('13 DSP pending-slot save result-parser controls passed (no emulator execution)')

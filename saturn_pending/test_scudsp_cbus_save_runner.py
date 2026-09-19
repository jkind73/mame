#!/usr/bin/env python3
# license:BSD-3-Clause
"""DSP save result-parser controls; actual file handling uses the shared runner."""
from test_scudsp_cbus_save_runtime import validate_output
stages=['DSP_CBUS_SAVE saved\n','DSP_CBUS_SAVE mutated\n','DSP_CBUS_SAVE loaded\n']
final='DSP_CBUS_SAVE PASS words=256 busy=1 stride=2 phase=odd replay=exact\n'
good=''.join(stages)+final
validate_output(good,0)
for bad in [final, ''.join(stages[:-1])+final, ''.join(stages[::-1])+final,
            good+stages[0],good+final,''.join(stages),good.replace('busy=1','busy=0'),
            good.replace('words=256','words=1'),good.replace('phase=odd','phase=even'),good.replace('stride=2','stride=4'),good+'DSP_CBUS_SAVE FAIL deliberate\n',
            good+'LUA ERROR deliberate\n',good.replace('replay=exact\n','replay=exact extra\n')]:
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid replay output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('15 C-bus save result-parser controls passed (no emulator execution)')

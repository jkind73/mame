#!/usr/bin/env python3
# license:BSD-3-Clause
"""DSP parallel save result-parser controls; actual file handling uses the shared runner."""
from test_scudsp_parallel_save_runtime import validate_output
stages=['DSP_PARALLEL_SAVE saved\n','DSP_PARALLEL_SAVE mutated\n','DSP_PARALLEL_SAVE loaded\n']
final='DSP_PARALLEL_SAVE PASS words=64 replay=exact\n'
observed='DSP_PARALLEL_SAVE observed partial loop\n'
good=observed+''.join(stages)+final
validate_output(good,0)
for bad in [observed+final, observed+''.join(stages[:-1])+final, observed+''.join(stages[::-1])+final,
            good+stages[0],good+final,observed+''.join(stages),good.replace('words=64','words=0'),
            good.replace(observed,''),good+'DSP_PARALLEL_SAVE FAIL deliberate\n',
            good+'LUA ERROR deliberate\n',good.replace('replay=exact\n','replay=exact extra\n'),''.join(stages)+observed+final]:
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid replay output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('14 DSP parallel save result-parser controls passed (no emulator execution)')

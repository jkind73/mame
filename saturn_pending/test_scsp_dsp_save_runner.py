#!/usr/bin/env python3
# license:BSD-3-Clause
"""SCSP DSP save result-parser controls; actual file handling uses the shared runner."""
from test_scsp_dsp_save_runtime import validate_output
stages=['SCSP_DSP_SAVE saved\n','SCSP_DSP_SAVE mutated\n','SCSP_DSP_SAVE loaded\n']
final='SCSP_DSP_SAVE PASS active=1 late_read=1 signed_address=1 replay=exact\n'
good=''.join(stages)+final
validate_output(good,0)
for bad in [final, ''.join(stages[:-1])+final, ''.join(stages[::-1])+final,
            good+stages[0],good+final,''.join(stages),good.replace('late_read=1','late_read=0'),
            good.replace('active=1','active=0'),good.replace('signed_address=1','signed_address=0'),good+'SCSP_DSP_SAVE FAIL deliberate\n',
            good+'LUA ERROR deliberate\n',good.replace('replay=exact\n','replay=exact extra\n')]:
    assert bad!=good, 'negative control must change the transcript'
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid replay output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('14 SCSP DSP save result-parser controls passed (no emulator execution)')

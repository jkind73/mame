#!/usr/bin/env python3
# license:BSD-3-Clause
"""SCSP IRQ save result-parser controls; actual file handling uses the shared runner."""
from test_scsp_irq_save_runtime import validate_output
stages=['SCSP_IRQ_SAVE saved\n','SCSP_IRQ_SAVE mutated\n','SCSP_IRQ_SAVE loaded\n']
final='SCSP_IRQ_SAVE PASS pending=restored byte_ack=independent replay=exact\n'
good=''.join(stages)+final
validate_output(good,0)
for bad in [final, ''.join(stages[:-1])+final, ''.join(stages[::-1])+final,
            good+stages[0],good+final,''.join(stages),good.replace('byte_ack=independent','byte_ack=wrong'),
            good.replace('pending=restored','pending=wrong'),good.replace('replay=exact','replay=wrong'),good+'SCSP_IRQ_SAVE FAIL deliberate\n',
            good+'LUA ERROR deliberate\n',good.replace('replay=exact\n','replay=exact extra\n')]:
    assert bad!=good, 'negative control must change the transcript'
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid replay output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('14 SCSP IRQ save result-parser controls passed (no emulator execution)')

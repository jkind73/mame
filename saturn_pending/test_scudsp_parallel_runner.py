#!/usr/bin/env python3
# license:BSD-3-Clause
"""DSP parallel bus parser/runner-contract controls; not emulator qualification."""
from test_scudsp_parallel_runtime import validate_output, runner
assert runner.__name__=="test_scudsp_dma_runtime", "ordinary programs require the multi-configuration DSP runner, not a save-file runner"
rows=[f'DSP_PARALLEL case={i} PASS\n' for i in range(1,145)]
final='DSP_PARALLEL PASS cases=144\n'
good=''.join(rows)+final
validate_output(good,0)
for bad in [final,''.join(rows[:-1])+final,''.join(rows[::-1])+final,
            good+rows[0],good+final,''.join(rows),good.replace('case=1 ','case=0 '),
            good+'DSP_PARALLEL FAIL deliberate\n',good+'LUA ERROR deliberate\n',
            good.replace('cases=144\n','cases=144 extra\n')]:
    try:validate_output(bad,0)
    except RuntimeError:pass
    else:raise AssertionError('invalid output accepted')
try:validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('13 DSP parallel bus parser/runner-contract controls passed (no emulator execution)')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""SCSP MIDI FIFO result-parser controls; no emulator execution."""
import test_scsp_midi_fifo_runtime as fixture
rows=[f'SCSP_MIDI_FIFO case={i} PASS\n' for i in range(1,fixture.CASES+1)]
final=f'SCSP_MIDI_FIFO PASS cases={fixture.CASES}\n';good=''.join(rows)+final
fixture.validate_output(good,0)
bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
     good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
     good.replace(f'cases={fixture.CASES}',f'cases={fixture.CASES-1}'),
     good+'SCSP_MIDI_FIFO FAIL injected\n',good+'LUA ERROR injected\n',
     good.replace(final,final.rstrip()+' extra\n')]
for text in bad:
    assert text!=good,'negative control must change the transcript'
    try:fixture.validate_output(text,0)
    except RuntimeError:pass
    else:raise AssertionError('malformed output accepted')
try:fixture.validate_output(good,1)
except RuntimeError:pass
else:raise AssertionError('nonzero exit accepted')
print('14 SCSP MIDI FIFO result-parser controls passed (no emulator execution)')

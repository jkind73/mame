#!/usr/bin/env python3
# license:BSD-3-Clause
"""Both safe-negative and explicit self-execute output protocols; no emulator."""
import test_scsp_dma_runtime as fixture
for total in (40,48):
    fixture.CASES=total
    rows=[f'SCSP_DMA case={i} PASS\n' for i in range(1,total+1)]
    final=f'SCSP_DMA PASS cases={total}\n';good=''.join(rows)+final
    fixture.validate_output(good,0)
    bad=['',final,''.join(rows),''.join(rows[1:])+final,''.join(rows[::-1])+final,
         good+rows[0],good+final,good.replace('case=2 PASS','case=1 PASS'),
         good.replace(f'cases={total}',f'cases={total-1}'),good+'SCSP_DMA FAIL injected\n',
         good+'LUA ERROR injected\n',good.replace(final,final.rstrip()+' extra\n')]
    for text in bad:
        assert text!=good
        try:fixture.validate_output(text,0)
        except RuntimeError:pass
        else:raise AssertionError('malformed output accepted')
    try:fixture.validate_output(good,1)
    except RuntimeError:pass
    else:raise AssertionError('nonzero exit accepted')
print('28 SCSP DMA result-parser controls passed (no emulator execution)')

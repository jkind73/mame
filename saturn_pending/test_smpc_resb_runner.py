#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""RESB result-parser controls, not emulator/device evidence."""
from test_smpc_resb_runtime import LABELS, validate_output

rows = ['SMPC_RESB case='+name+' PASS\n' for name in LABELS]
final = 'SMPC_RESB PASS cases=7\n'
good = ''.join(rows)+final
checks = [
    (good, 0, True), (good, 1, False),
    (good+'SMPC_RESB FAIL deliberate\n', 0, False),
    (good+'LUA ERROR deliberate\n', 0, False),
    (final, 0, False), (''.join(rows[:-1])+final, 0, False),
    (''.join(rows+[rows[-1]])+final, 0, False),
    (''.join(reversed(rows))+final, 0, False),
    (good.replace('press-sampled', 'unknown'), 0, False),
    (good.replace('cases=7', 'cases=6'), 0, False),
    (good.rstrip()+' extra\n', 0, False), (good+final, 0, False),
]
for text, code, expected in checks:
    try:
        validate_output(text, code)
        passed = True
    except RuntimeError:
        passed = False
    assert passed == expected, (text, code)
print('12 SMPC RESB result-parser controls passed (no emulator execution)')

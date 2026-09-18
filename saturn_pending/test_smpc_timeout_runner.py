#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Timeout result-parser controls, not emulator/device evidence."""
from test_smpc_timeout_runtime import CASES, validate_output

rows = ['SMPC_TIMEOUT case='+name+' PASS\n' for name in CASES]
final = 'SMPC_TIMEOUT PASS cases=4\n'
good = ''.join(rows)+final
checks = [
    (good, 0, True), (good, 1, False),
    (good+'SMPC_TIMEOUT FAIL deliberate\n', 0, False),
    (good+'LUA ERROR deliberate\n', 0, False),
    (final, 0, False), (''.join(rows[:-1])+final, 0, False),
    (''.join(rows+[rows[-1]])+final, 0, False),
    (''.join(reversed(rows))+final, 0, False),
    (good.replace('status-wait', 'unknown'), 0, False),
    (good.replace('cases=4', 'cases=3'), 0, False),
    (good.rstrip()+' extra\n', 0, False), (good+final, 0, False),
]
for text, code, expected in checks:
    try:
        validate_output(text, code)
        passed = True
    except RuntimeError:
        passed = False
    assert passed == expected, (text, code)
print('12 SMPC timeout result-parser controls passed (no emulator execution)')

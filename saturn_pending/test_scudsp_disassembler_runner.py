#!/usr/bin/env python3
# license:BSD-3-Clause
"""Validate complete debugger dumps; no emulator execution."""
from test_scudsp_disassembler_runtime import validate_output,validate_trace,VECTORS
log='DSP_DASM dumped words=241\n'
rows=[f'{i:02X}: {expected}\n' for i,(_,expected) in enumerate(VECTORS)]
good=''.join(rows)
validate_output(log,good,0);cases=1
for text,dump,rc in [
    ('',good,0),(log+log,good,0),(log+'LUA ERROR bad\n',good,0),
    (log+'DSP_DASM FAIL bad\n',good,0),(log,good,1),(log,'',0),
    (log,''.join(rows[:-1]),0),(log,''.join(rows[::-1]),0),(log,good+rows[0],0),
    (log,good.replace('00:','FF:',1),0),
    (log,good.replace(',PC',',CT0',1),0),
    (log,good.replace(' MOV MUL,P','MOV MUL,P'),0)]:
    try:validate_output(text,dump,rc)
    except RuntimeError:pass
    else:raise AssertionError('invalid debugger output accepted')
    cases+=1
print(f'{cases} debugger dump parser controls passed (no emulator execution)')

trace='FF: JMP $10\n00: MVI #$12,MC3\n10: END\n'
validate_trace(trace);trace_cases=1
for bad in ('',trace.splitlines()[0]+'\n',trace.replace('00:','10:'),trace+trace,
            '\n'.join(reversed(trace.splitlines())),trace+'unexpected\n',trace.replace('#$12','#$34')):
    try:validate_trace(bad)
    except RuntimeError:pass
    else:raise AssertionError('invalid debugger trace accepted')
    trace_cases+=1
print(f'{trace_cases} debugger slot-trace parser controls passed (no emulator execution)')

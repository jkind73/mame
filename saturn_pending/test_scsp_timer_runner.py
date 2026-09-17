#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Failure-protocol tests only; the executable is fake, not SCSP emulation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
FAKE=r'''#!/usr/bin/env python3
import os,sys
mode=os.environ['SCSP_RUNNER_FAKE']
assert os.path.isabs(sys.argv[sys.argv.index('-rompath')+1])
if mode=='empty':sys.exit(0)
for t in range(3):
 for p in range(8):
  if mode=='missing' and (t,p)==(2,7):continue
  print(f'PRESCALE {t} {p} dt=0.05 predicted=1 measured(mod256)=1 window=1')
if mode=='duplicate':print('PRESCALE 0 0 dt=0.05 predicted=1 measured(mod256)=1 window=1')
for t in ([1,0,2] if mode=='order' else range(3)):
 if mode=='irq' and t==2:continue
 print(f'TIMER_IRQ {t} SCIPD=01c0')
print('SCSP_TIMER_RUNTIME PASS'+(' extra' if mode=='substring' else ''))
if mode=='fail':print('SCSP_TIMER_RUNTIME FAIL deliberate')
if mode=='lua':print('LUA ERROR deliberate')
if mode=='nonzero':sys.exit(7)
'''
with tempfile.TemporaryDirectory(prefix='scsp-runner-protocol-') as tmp:
 d=Path(tmp);exe=d/'fake';exe.write_text(FAKE);exe.chmod(0o755)
 (d/'saturnjp.zip').touch()
 modes=('good','empty','missing','duplicate','irq','order','substring','fail','lua','nonzero')
 for mode in modes:
  env=os.environ.copy();env['SCSP_RUNNER_FAKE']=mode
  result=subprocess.run([sys.executable,str(HERE/'test_scsp_timers.py'),
      '--executable',str(exe),'--rompath',str(d)],env=env,
      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=10)
  assert (result.returncode==0)==(mode=='good'),(mode,result.stdout)
print('10 SCSP runner protocol cases passed (fake executable, not hardware evidence)')

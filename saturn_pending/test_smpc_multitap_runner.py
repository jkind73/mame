#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Fake-executable protocol tests, not SMPC or controller validation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
FAKE=r'''#!/usr/bin/env python3
import os,sys
mode=os.environ['SMPC_FAKE_MODE']
assert sys.argv[sys.argv.index('-ctrl1')+1]=='multitap'
assert sys.argv[sys.argv.index('-ctrl2')+1]=='multitap'
assert os.path.isabs(sys.argv[sys.argv.index('-rompath')+1])
assert '-noreadconfig' in sys.argv
rows=[(1,38,2),(2,38,2),(3,19,1),(4,19,1),(5,19,1),(6,19,1)]
if mode=='bare':rows=[]
if mode=='missing':rows.pop()
if mode=='duplicate':rows[1]=rows[0]
if mode=='order':rows[0],rows[1]=rows[1],rows[0]
if mode=='length':rows[0]=(1,32,1)
for i,size,pages in rows:print(f'SMPC_MULTITAP case={i} bytes={size} pages={pages} PASS')
print('SMPC_MULTITAP PASS cases=6'+(' extra' if mode=='substring' else ''))
if mode=='fail':print('SMPC_MULTITAP FAIL deliberate')
if mode=='lua':print('LUA ERROR deliberate')
if mode=='nonzero':sys.exit(3)
'''
with tempfile.TemporaryDirectory(prefix='smpc-runner-protocol-') as tmp:
    d=Path(tmp);exe=d/'fake';exe.write_text(FAKE);exe.chmod(0o755)
    (d/'saturnjp.zip').touch()
    modes=('good','bare','missing','duplicate','order','length','substring','fail','lua','nonzero')
    for mode in modes:
        env=os.environ.copy();env['SMPC_FAKE_MODE']=mode
        output=d/mode
        r=subprocess.run([sys.executable,str(HERE/'test_smpc_multitap_runtime.py'),
            '--executable',str(exe),'--rompath',str(d),'--output',str(output)],
            env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        if (r.returncode==0)!=(mode=='good'):raise RuntimeError((mode,r.stdout))
        if not (output/'runtime.log').is_file():raise RuntimeError('Missing diagnostic log')
print('10 SMPC live-runner failure-protocol cases passed (fake executable only)')

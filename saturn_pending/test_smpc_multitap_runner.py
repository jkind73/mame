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
adapter=os.environ['SMPC_ADAPTER']
option='' if adapter=='none' else adapter
assert sys.argv[sys.argv.index('-ctrl1')+1]==option
assert sys.argv[sys.argv.index('-ctrl2')+1]==option
for empty in filter(None,os.environ['SMPC_EMPTY_PADS'].split(',')):
    port,slot=empty.split(':');key=f'-ctrl{port}:{adapter}:ctrl{slot}'
    assert sys.argv[sys.argv.index(key)+1]==''
assert os.path.isabs(sys.argv[sys.argv.index('-rompath')+1])
assert '-noreadconfig' in sys.argv
lengths=tuple(map(int,os.environ['SMPC_FAKE_LENGTHS'].split(',')))
rows=[(i,n,(n+31)//32) for i,n in enumerate((sum(lengths),)*2+(lengths[1],)*2+(lengths[0],)*2,1)]
if mode=='bare':rows=[]
if mode=='missing':rows.pop()
if mode=='duplicate':rows[1]=rows[0]
if mode=='order':rows[0],rows[1]=rows[1],rows[0]
if mode=='length':rows[0]=(1,32,1)
for i,size,pages in rows:print(f'SMPC_MULTITAP case={i} bytes={size} pages={pages} PASS')
if mode!='no-final':print('SMPC_MULTITAP PASS cases=6'+(' extra' if mode=='substring' else ''))
if mode=='duplicate-final':print('SMPC_MULTITAP PASS cases=6')
if mode=='fail':print('SMPC_MULTITAP FAIL deliberate')
if mode=='lua':print('LUA ERROR deliberate')
if mode=='nonzero':sys.exit(3)
'''
with tempfile.TemporaryDirectory(prefix='smpc-runner-protocol-') as tmp:
    d=Path(tmp);exe=d/'fake';exe.write_text(FAKE);exe.chmod(0o755)
    (d/'saturnjp.zip').touch()
    modes=('good','bare','missing','duplicate','order','length','substring','fail','lua','nonzero','no-final','duplicate-final')
    # Independent literal expected packet lengths for every live configuration.
    configs=(('multitap',(),(19,19)),('multitap',('1:2','2:5'),(17,17)),
             ('segatap',(),(13,13)),('segatap',('1:2','2:3'),(11,11)),
             ('none',(),(1,1)))
    for index,(adapter,empty,lengths) in enumerate(configs):
        for mode in modes:
            env=os.environ.copy();env['SMPC_FAKE_MODE']=mode
            env['SMPC_FAKE_LENGTHS']=','.join(map(str,lengths))
            output=d/(str(index)+'-'+mode)
            args=['--adapter',adapter]
            for slot in empty:args+=['--empty-pad',slot]
            r=subprocess.run([sys.executable,str(HERE/'test_smpc_multitap_runtime.py'),
                '--executable',str(exe),'--rompath',str(d),'--output',str(output),*args],
                env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
            if (r.returncode==0)!=(mode=='good'):raise RuntimeError((adapter,empty,mode,r.stdout))
            if not (output/'runtime.log').is_file():raise RuntimeError('Missing diagnostic log')
print('60 SMPC live-runner failure-protocol/configuration cases passed (fake executable only)')

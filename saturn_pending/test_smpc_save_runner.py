#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Fake-process controls for save-runner failure handling, not device evidence."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FAKE = r'''#!/usr/bin/env python3
import os,sys
from pathlib import Path
mode=os.environ['SMPC_FAKE_MODE']
assert sys.argv[sys.argv.index('-ctrl1')+1]=='multitap'
assert sys.argv[sys.argv.index('-ctrl2')+1]=='multitap'
assert '-noreadconfig' in sys.argv
assert os.path.isabs(sys.argv[sys.argv.index('-rompath')+1])
path=Path(os.environ['SMPC_SAVE_FILE']);assert path.is_absolute()
if mode!='missing-file':
    path.write_bytes(b'MAMESAVE'+b'\x00'*25 if mode!='bad-file' else b'bad')
rows=['saved','mutated','loaded']
if mode=='bare':rows=[]
if mode=='missing':rows.pop()
if mode=='duplicate':rows.insert(1,'saved')
if mode=='order':rows.reverse()
for stage in rows:print('SMPC_SAVE '+stage)
marker='SMPC_SAVE PASS bytes=38 cursor=32 tail=6'
if mode=='cursor':marker=marker.replace('cursor=32','cursor=0')
if mode=='substring':marker+=' extra'
if mode!='no-final':print(marker)
if mode=='duplicate-final':print(marker)
if mode=='fail':print('SMPC_SAVE FAIL deliberate')
if mode=='lua':print('LUA ERROR deliberate')
if mode=='nonzero':sys.exit(3)
'''
with tempfile.TemporaryDirectory(prefix='smpc-save-protocol-') as tmp:
    d = Path(tmp)
    exe = d/'fake'
    exe.write_text(FAKE)
    exe.chmod(0o755)
    (d/'saturnjp.zip').touch()
    modes = ('good', 'bare', 'missing', 'duplicate', 'order', 'cursor',
             'substring', 'no-final', 'duplicate-final', 'fail', 'lua',
             'nonzero', 'missing-file', 'bad-file')
    for mode in modes:
        env = os.environ.copy()
        env['SMPC_FAKE_MODE'] = mode
        output = d/mode
        result = subprocess.run([
            sys.executable, str(HERE/'test_smpc_save_runtime.py'),
            '--executable', str(exe), '--rompath', str(d), '--output', str(output)],
            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=10)
        if (result.returncode == 0) != (mode == 'good'):
            raise RuntimeError((mode, result.stdout))
        if not (output/'runtime.log').is_file():
            raise RuntimeError('Missing diagnostic log')
print('14 SMPC save-runner failure-protocol cases passed (fake executable only)')

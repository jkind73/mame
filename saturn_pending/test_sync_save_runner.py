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
mode=os.environ['SYNC_FAKE_MODE']
assert '-noreadconfig' in sys.argv
assert os.path.isabs(sys.argv[sys.argv.index('-rompath')+1])
path=Path(os.environ['SYNC_SAVE_FILE']);assert path.is_absolute()
if mode!='missing-file':
    path.write_bytes(b'MAMESAVE'+b'\x00'*25 if mode!='bad-file' else b'bad')
rows=['saved','mutated','loaded']
if mode=='bare':rows=[]
if mode=='missing':rows.pop()
if mode=='duplicate':rows.insert(1,'saved')
if mode=='order':rows.reverse()
for stage in rows:print('SYNC_SAVE '+stage)
marker='SYNC_SAVE PASS restored_HV=0 first_edge_IST=4'
if mode=='irq':marker=marker.replace('first_edge_IST=4','first_edge_IST=2')
if mode=='substring':marker+=' extra'
if mode!='no-final':print(marker)
if mode=='duplicate-final':print(marker)
if mode=='fail':print('SYNC_SAVE FAIL deliberate')
if mode=='lua':print('LUA ERROR deliberate')
if mode=='nonzero':sys.exit(3)
'''
with tempfile.TemporaryDirectory(prefix='sync-save-protocol-') as tmp:
    d = Path(tmp)
    exe = d/'fake'
    exe.write_text(FAKE)
    exe.chmod(0o755)
    (d/'saturnjp.zip').touch()
    modes = ('good', 'bare', 'missing', 'duplicate', 'order', 'irq',
             'substring', 'no-final', 'duplicate-final', 'fail', 'lua',
             'nonzero', 'missing-file', 'bad-file')
    for mode in modes:
        env = os.environ.copy()
        env['SYNC_FAKE_MODE'] = mode
        output = d/mode
        result = subprocess.run([
            sys.executable, str(HERE/'test_sync_save_runtime.py'),
            '--executable', str(exe), '--rompath', str(d), '--output', str(output)],
            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=10)
        if (result.returncode == 0) != (mode == 'good'):
            raise RuntimeError((mode, result.stdout))
        if not (output/'runtime.log').is_file():
            raise RuntimeError('Missing diagnostic log')
print('14 sync save-runner failure-protocol cases passed (fake executable only)')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check ST-V sound switch pins on the native Astra device graph."""
import argparse
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--binary', type=Path, default=Path('saturn'))
p.add_argument('--rompath', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parent.parent
out = a.output.resolve()
out.mkdir(exist_ok=False)
for core in ('drc', 'interpreter'):
    run = out / core
    run.mkdir()
    (run / 'diff').mkdir()
    cmd = ['nice', '-n', '10', str(a.binary.resolve()), 'astrass',
           '-noreadconfig', '-rompath', a.rompath, '-video', 'none', '-sound', 'none',
           '-nothrottle', '-seconds_to_run', '35', '-skip_gameinfo',
           '-autoboot_delay', '0', '-autoboot_script', str(root / 'scripts/stv_sound_io_test.lua')]
    if core == 'interpreter':
        cmd += ['-nodrc']
    for d in ('cfg', 'nvram', 'diff'):
        cmd += ['-' + d + '_directory', str(run / d)]
    with (run / 'run.log').open('w') as log:
        r = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=90)
    text = (run / 'run.log').read_text()
    if r.returncode or 'STV_SOUND_IO_PASS Astra startup' not in text or '_FAIL' in text or '[LUA ERROR]' in text:
        raise RuntimeError(text)
    print(core + ' ST-V sound switches PASS', flush=True)

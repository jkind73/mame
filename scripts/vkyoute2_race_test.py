#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run the real Virtual Kyoutei 2 disc with replayable two-controller input.

This captures VDP1 lists and frames; a successful exit alone is not a graphics pass.
During exploration, control.txt accepts: token p1_hex p2_hex duration_frames,
or 'exit'. Applied inputs are recorded as a CSV for replay on the other core.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--core', choices=('drc', 'interpreter'), required=True)
p.add_argument('--rompath', required=True)
p.add_argument('--seed-nvram', type=Path, required=True)
p.add_argument('--inputs', type=Path)
p.add_argument('--frames', type=int, default=36000)
p.add_argument('--every', type=int, default=180)
a = p.parse_args()
root = Path(__file__).resolve().parent.parent
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
for name in ('cfg', 'nvram', 'diff', 'state'):
    (out/name).mkdir()
shutil.copytree(a.seed_nvram, out/'nvram'/'saturnjp')
(out/'control.txt').write_text('0 0000 0000 0\n')
env = os.environ.copy()
env['VKYOUTE2_RACE_OUTPUT'] = str(out)
env['VKYOUTE2_RACE_FRAMES'] = str(a.frames)
env['VKYOUTE2_RACE_EVERY'] = str(a.every)
if a.inputs:
    env['VKYOUTE2_RACE_INPUTS'] = str(a.inputs.resolve())
else:
    env.pop('VKYOUTE2_RACE_INPUTS', None)
cmd = ['nice', '-n', '10', str(root/'saturn'), 'saturnjp', 'vkyoute2',
       '-noreadconfig', '-rompath', a.rompath, '-video', 'none', '-sound', 'none',
       '-nothrottle', '-frameskip', '0', '-rtc', '20000101000000',
       '-seconds_to_run', str(a.frames//60+10), '-skip_gameinfo',
       '-autoboot_delay', '0', '-autoboot_script', str(root/'scripts/vkyoute2_race_test.lua')]
for name in ('cfg', 'nvram', 'diff', 'state'):
    cmd += ['-'+name+'_directory', str(out/name)]
if a.core == 'interpreter':
    cmd += ['-nodrc']
(out/'command.json').write_text(json.dumps(cmd, indent=2)+'\n')
with (out/'run.log').open('w') as log:
    result = subprocess.run(cmd, cwd=root, env=env, stdout=log,
                            stderr=subprocess.STDOUT, timeout=max(240, a.frames//20))
text = (out/'run.log').read_text(errors='replace')
assert result.returncode == 0 and 'RACE_RUN_COMPLETE' in text and '[LUA ERROR]' not in text, text[-4000:]
assert 'BAD_INIT ' not in text, 'Invalid MINIT/SINIT writes; inspect run.log'
print(a.core, 'race capture completed; review frames and command lists', flush=True)

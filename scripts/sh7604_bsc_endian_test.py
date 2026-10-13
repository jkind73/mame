#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check actual SH7604 CPU and DMA CS2 endian conversion."""
import argparse
from pathlib import Path
import subprocess
from sh7604_device_test import diagnostic_roms

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--binary', type=Path, default=Path('saturn'))
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
diagnostic_roms(out / 'roms')
for core in ('drc', 'interpreter'):
    run = out / core
    run.mkdir()
    command = ['nice', '-n', '10', str(args.binary.resolve()), 'saturnjp',
               '-noreadconfig', '-rompath', str(out / 'roms'), '-video', 'none',
               '-sound', 'none', '-nothrottle', '-seconds_to_run', '3',
               '-skip_gameinfo', '-autoboot_delay', '0', '-autoboot_script',
               str(root / 'scripts/sh7604_bsc_endian_test.lua'),
               '-keyboardprovider', 'none', '-joystickprovider', 'none']
    for directory in ('cfg', 'nvram', 'diff', 'state'):
        command += ['-' + directory + '_directory', str(run / directory)]
    if core == 'interpreter':
        command += ['-nodrc']
    with (run / 'run.log').open('w') as log:
        result = subprocess.run(command, cwd=run, stdout=log,
                                stderr=subprocess.STDOUT, timeout=60)
    text = (run / 'run.log').read_text()
    if result.returncode or 'SH7604_BSC_ENDIAN_PASS' not in text or 'FAIL' in text or '[LUA ERROR]' in text:
        raise RuntimeError(f'{core}: see {run / "run.log"}\n{text}')
    print(core, 'BSC endian PASS', flush=True)

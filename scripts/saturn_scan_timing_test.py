#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run real VDP2 register timing diagnostics with both SH2 execution engines."""
import argparse
from pathlib import Path
import subprocess
from sh7604_device_test import diagnostic_roms

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=False)
diagnostic_roms(out/'roms')
for core in ('drc','interpreter'):
    run=out/core
    run.mkdir()
    cmd=['nice','-n','10',str(root/'saturn'),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),
         '-video','none','-sound','none','-nothrottle','-seconds_to_run','3','-skip_gameinfo',
         '-autoboot_delay','0','-autoboot_script',str(root/'scripts/saturn_scan_timing_test.lua')]
    for option in ('cfg','nvram','diff','state'):
        cmd += ['-'+option+'_directory',str(run/option)]
    if core=='interpreter':cmd.append('-nodrc')
    with (run/'run.log').open('w') as log:
        result=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    text=(run/'run.log').read_text()
    if result.returncode or 'SATURN_SCAN_TIMING_PASS' not in text or '[LUA ERROR]' in text:
        raise RuntimeError(text)
    print(core+' VDP2 register timing PASS',flush=True)

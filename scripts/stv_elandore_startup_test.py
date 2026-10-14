#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check Elan-Doree's real startup with both CPU engines and isolated state."""
import argparse
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',type=Path,default=ROOT/'saturn')
parser.add_argument('--rompath',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
output=args.output.resolve()
output.mkdir(parents=True,exist_ok=False)
for core in ('drc','interpreter'):
    run=output/core
    run.mkdir()
    command=['nice','-n','10',str(args.binary.resolve()),'elandore','-noreadconfig',
             '-rompath',args.rompath,'-video','none','-sound','none','-nothrottle',
             '-frameskip','0','-seconds_to_run','32','-rtc','20000101000000',
             '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',
             str(ROOT/'scripts/stv_elandore_startup_test.lua'),'-snapshot_directory',str(run)]
    for directory in ('cfg','nvram','diff','state'):
        command+=['-'+directory+'_directory',str(run/directory)]
    if core=='interpreter':
        command+=['-nodrc']
    with (run/'run.log').open('w')as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    text=(run/'run.log').read_text()
    assert result.returncode==0 and 'STV_ELANDORE_STARTUP_PASS' in text and '[LUA ERROR]' not in text,text
    print(core,'PASS',flush=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Verify ST-V sound RAM bounds using the real device maps in both engines."""
import argparse
from pathlib import Path
import subprocess
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',type=Path,default=Path('saturn'))
parser.add_argument('--rompath',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=Path(__file__).resolve().parent.parent
out=args.output.resolve();out.mkdir(exist_ok=False)
for core in ('drc','interpreter'):
 run=out/core;run.mkdir()
 command=['nice','-n','10',str(args.binary.resolve()),'stvbios','-noreadconfig','-rompath',args.rompath,'-video','none','-sound','none','-nothrottle','-seconds_to_run','3','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/saturn_sound_ram_boundary_test.lua')]
 if core=='interpreter':command.append('-nodrc')
 for option in ('cfg','nvram','diff','state'):command+=['-'+option+'_directory',str(run/option)]
 with (run/'run.log').open('w') as log:result=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=90)
 text=(run/'run.log').read_text()
 if result.returncode or 'SATURN_SOUND_RAM_BOUNDARY_PASS' not in text or '_FAIL' in text or '[LUA ERROR]' in text:raise RuntimeError(text)
 print(core+' ST-V sound RAM boundary PASS',flush=True)

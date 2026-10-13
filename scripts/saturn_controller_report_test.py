#!/usr/bin/env python3
# license:BSD-3-Clause
"""Verify real controller packets under both CPU engines, one run at a time."""
import argparse
import os
from pathlib import Path
import subprocess
from sh7604_device_test import diagnostic_roms

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--binary',type=Path,default=Path('saturn'))
args=parser.parse_args();root=Path(__file__).resolve().parent.parent
out=args.output.resolve();out.mkdir(exist_ok=False);diagnostic_roms(out/'roms')
for kind in ('analog','keyboard','multitap','twin_stick','segatap','multicontroller','multitap_saved'):
 for core in ('drc','interpreter'):
  run=out/(kind+'-'+core);run.mkdir()
  controller='multitap' if kind=='multitap_saved' else kind
  command=['nice','-n','10',str(args.binary.resolve()),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','3','-skip_gameinfo','-ctrl1',controller,'-ctrl2','','-autoboot_delay','0','-autoboot_script',str(root/'scripts/saturn_controller_report_test.lua')]
  if kind=='multitap':
   for i,value in enumerate(('joypad','','analog','','keyboard','joypad'),1):command+=['-ctrl1:multitap:ctrl'+str(i),value]
  if kind=='segatap':
   for i,value in enumerate(('joy_md3','joy_md6','mouse',''),1):command+=['-ctrl1:segatap:ctrl'+str(i),value]
  if kind=='multitap_saved':
   for i in range(1,7):command+=['-ctrl1:multitap:ctrl'+str(i),'multicontroller']
  if core=='interpreter':command.append('-nodrc')
  for option in ('cfg','nvram','diff','state'):command+=['-'+option+'_directory',str(run/option)]
  env=os.environ.copy();env['SATURN_CONTROLLER_TEST_KIND']=kind
  with (run/'run.log').open('w') as log:result=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
  text=(run/'run.log').read_text()
  if result.returncode or 'SATURN_CONTROLLER_REPORT_PASS' not in text or '_FAIL' in text or '[LUA ERROR]' in text:raise RuntimeError(text)
  print(kind+' '+core+' SMPC report PASS',flush=True)

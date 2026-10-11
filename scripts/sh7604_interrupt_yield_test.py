#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run SH7604 interrupt-yield diagnostics on the actual Saturn device graph."""
import argparse,subprocess
from pathlib import Path
from sh7604_device_test import diagnostic_roms
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--debug',action='store_true');p.add_argument('--ideal-bus',action='store_true');p.add_argument('--core',choices=('drc','interpreter'));a=p.parse_args()
root=Path(__file__).resolve().parent.parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);diagnostic_roms(out/'roms')
for core in ((a.core,) if a.core else ('drc','interpreter')):
 run=out/core;run.mkdir()
 if a.ideal_bus:
  (run/'cfg').mkdir()
  (run/'cfg'/'saturnjp.cfg').write_text('<mameconfig version="10"><system name="saturnjp"><input><port tag=":CONFIG" type="CONFIG" mask="1" defvalue="1" value="0"/></input></system></mameconfig>')
 cmd=['nice','-n','10',str(root/'saturn'),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),'-log','-video','none','-sound','none','-nothrottle','-seconds_to_run','5','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/sh7604_interrupt_yield_test.lua')]
 for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
 if core=='interpreter':cmd+=['-nodrc']
 if a.debug:cmd+=['-debug','-debugger','none']
 with (run/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=15)
 t=(run/'run.log').read_text();assert r.returncode==0 and 'SH7604_INTERRUPT_YIELD_PASS' in t and 'FAIL' not in t and '[LUA ERROR]' not in t,t
 print(core,'interrupt yield PASS',flush=True)

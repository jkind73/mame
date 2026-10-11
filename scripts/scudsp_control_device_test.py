#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run SCU DSP control diagnostics on the actual Saturn device graph."""
import argparse,subprocess
from pathlib import Path
from sh7604_device_test import diagnostic_roms
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--debug',action='store_true');p.add_argument('--debug-scheduler',action='store_true');p.add_argument('--debug-step',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parent.parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);diagnostic_roms(out/'roms')
for core in ('drc','interpreter'):
 run=out/core;run.mkdir()
 script='scudsp_debug_scheduler_test.lua' if a.debug_scheduler else 'scudsp_control_test.lua'
 token='SCUDSP_DEBUG_SCHEDULER_PASS' if a.debug_scheduler else 'SCUDSP_CONTROL_PASS'
 if a.debug_step:script='scudsp_debug_step_test.lua';token='SCUDSP_DEBUG_STEP_PASS'
 cmd=['nice','-n','10',str(root/'saturn'),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),'-log','-video','none','-sound','none','-nothrottle','-seconds_to_run','5','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts'/script)]
 for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
 if core=='interpreter':cmd+=['-nodrc']
 if a.debug or a.debug_scheduler or a.debug_step:cmd+=['-debug','-debugger','osx' if a.debug_step else 'none']
 with (run/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=120)
 t=(run/'run.log').read_text();assert r.returncode==0 and token in t and 'FAIL' not in t and '[LUA ERROR]' not in t,t
 print(core,token,flush=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run real CD selector commands and parse recovered Lua scripts on both cores."""
from pathlib import Path
import argparse, subprocess
from sh7604_device_test import diagnostic_roms
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);diagnostic_roms(out/'roms')
import json
files=sorted((root/'regtests/saturn/scratchpad').glob('*.lua'))
wrapper=out/'test.lua'
wrapper.write_text('\n'.join('assert(loadfile('+json.dumps(str(f))+'))' for f in files)+'\nprint("RECOVERED_LUA_PARSE_PASS")\ndofile('+json.dumps(str(root/'scripts/saturn_cd_selector_test.lua'))+')\n')
for core in ('drc','interpreter'):
 run=out/core;run.mkdir()
 cmd=['nice','-n','10',str(root/'saturn'),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','3','-autoboot_delay','0','-autoboot_script',str(wrapper),'-keyboardprovider','none','-joystickprovider','none']
 for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
 if core=='interpreter':cmd+=['-nodrc']
 with (run/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=60)
 text=(run/'run.log').read_text();assert r.returncode==0 and 'SATURN_CD_SELECTOR_RUNTIME_PASS' in text and 'RECOVERED_LUA_PARSE_PASS' in text and '[LUA ERROR]' not in text,text
 print(core,'CD_SELECTOR_RUNTIME_PASS',flush=True)

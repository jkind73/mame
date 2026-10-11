#!/usr/bin/env python3
# license:BSD-3-Clause
"""Measure VF2 with video enabled and isolated state, optionally with live audio."""
import argparse
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--binary',type=Path,default=root/'saturn')
p.add_argument('--seconds',type=int,default=90)
p.add_argument('--machine',default='saturnjp')
p.add_argument('--software',default='vf2j')
p.add_argument('--sound',choices=('none','auto'),default='none')
p.add_argument('--video',default='auto')
p.add_argument('--renderdriver')
p.add_argument('--throttle',action='store_true')
p.add_argument('--nvram-seed',type=Path)
p.add_argument('--cfg-seed',type=Path)
p.add_argument('--rompath')
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
if a.nvram_seed:shutil.copytree(a.nvram_seed,out/'nvram'/a.machine)
if a.cfg_seed:shutil.copytree(a.cfg_seed,out/'cfg')
cmd=['nice','-n','10',str(a.binary.resolve()),a.machine,a.software,'-video',a.video,
     '-sound',a.sound,'-throttle' if a.throttle else '-nothrottle',
     '-seconds_to_run',str(a.seconds),'-skip_gameinfo','-verbose','-autoboot_delay','0',
     '-autoboot_script',str(root/'scripts/saturn_vf2_performance_test.lua')]
if a.rompath:cmd+=['-rompath',a.rompath]
if a.renderdriver:cmd+=['-renderdriver',a.renderdriver]
for name in ('cfg','nvram','diff','state','snapshot'):cmd+=['-'+name+'_directory',str(out/name)]
with (out/'run.log').open('w') as log:
    result=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=a.seconds*6+120)
text=(out/'run.log').read_text(errors='replace')
assert result.returncode==0 and 'VF2_PERF' in text and 'Average speed:' in text and 'Fatal error' not in text and '[LUA ERROR]' not in text,text[-3000:]
for line in text.splitlines():
    if any(token in line for token in ('VF2_PERF','Average speed:','Flush count','underflow(s)')):print(line)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Optional linked pixel/save-manager or unmodified BIOS replay qualification.

Requires a linked executable and user-supplied BIOS ROMs. Not part of run_all.py.
Synthetic tests hold both SH-2s in RAM loops. Neither mode certifies hardware or games.
"""
import argparse
import os
import re
from pathlib import Path
import subprocess
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--executable',type=Path,required=True)
p.add_argument('--rompath',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--system',choices=('saturnjp','saturn','saturneu','stvbios'),default='saturnjp')
p.add_argument('--drc',action='store_true')
mode=p.add_mutually_exclusive_group()
mode.add_argument('--bios',action='store_true')
mode.add_argument('--composition',action='store_true',help='two-background priorities, ratios and additive calculation')
p.add_argument('--boot-frames',type=int,default=900)
p.add_argument('--timeout',type=int,default=300)
a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',SATURN_RUNTIME_OUTPUT=str(a.output),SATURN_BIOS_FRAMES=str(a.boot_frames),SATURN_RUNTIME_COMPOSITION='1' if a.composition else '0')
command=[str(a.executable.resolve()),a.system,'-rompath',str(a.rompath.resolve()),'-noreadconfig','-skip_gameinfo','-drc' if a.drc else '-nodrc','-video','none','-sound','none','-nothrottle','-autoboot_delay','0','-autoboot_script',str(HERE/('bios_runtime.lua' if a.bios else 'vdp2_runtime.lua')),'-seconds_to_run','120' if a.composition else '30','-nvram_directory',str(a.output/'nvram'),'-cfg_directory',str(a.output/'cfg'),'-state_directory',str(a.output),'-snapshot_directory',str(a.output)]
log=a.output/'runtime.log'
with log.open('w') as f:
 result=subprocess.run(command,cwd=a.output,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=a.timeout)
text=log.read_text(errors='replace');print(text)
marker='BIOS_RUNTIME' if a.bios else 'VDP2_RUNTIME'
if a.bios:
    expected=rf'^BIOS_RUNTIME PASS system={re.escape(a.system)} time=[0-9]+\.[0-9]+ pc=[0-9a-f]{{8}} full-image replay identical$'
    complete=re.search(expected,text,re.M) is not None
else:
    count=338 if a.composition else 46
    records=[int(m[1]) for m in re.finditer(r'^VDP2_RUNTIME case=(\d+) .* pixels/save/load PASS$',text,re.M)]
    complete=(records==list(range(1,count+1)) and
              re.search(rf'^VDP2_RUNTIME PASS cases={count}$',text,re.M) is not None)
if result.returncode or marker+' FAIL' in text or not complete:
    raise SystemExit(f'Linked fixture failed (exit {result.returncode}); see {log}')
print(f'Linked {marker} fixture passed; results: {a.output}')

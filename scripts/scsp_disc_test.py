#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run supplied SCSP test/demo discs serially, with isolated state and WAV capture."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import wave
from array import array

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--disc',type=Path,required=True)
parser.add_argument('--rompath',type=Path,required=True)
parser.add_argument('--nvram-seed',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--kind',choices=('suite','adpcm','cronsf'),default='suite')
parser.add_argument('--seconds',type=int,default=120)
parser.add_argument('--core',choices=('drc','interpreter'),help='select one engine instead of both for the suite')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
results=[]
for core in ((args.core,) if args.core else (('drc','interpreter') if args.kind=='suite' else ('drc',))):
    run=out/core;run.mkdir();(run/'snap').mkdir()
    shutil.copytree(args.nvram_seed,run/'nvram/saturnjp')
    cmd=['nice','-n','10',str(root/'saturn'),'saturnjp','-cdrom',str(args.disc.resolve()),
         '-rompath',str(args.rompath.resolve()),'-noreadconfig','-video','none','-sound','sdl',
         '-wavwrite',str(run/'audio.wav'),'-nothrottle','-seconds_to_run',str(args.seconds),
         '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/scsp_suite_test.lua'),
         '-snapshot_directory',str(run/'snap')]
    for option in ('cfg','nvram','diff','state'):cmd+=['-'+option+'_directory',str(run/option)]
    if core=='interpreter':cmd.append('-nodrc')
    env=dict(os.environ,SDL_AUDIODRIVER='dummy',SCSP_DISC_KIND=args.kind)
    with (run/'run.log').open('w') as log:
        process=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    text=(run/'run.log').read_text()
    assert process.returncode==0 and '[LUA ERROR]' not in text,text[-3000:]
    if args.kind=='suite':assert 'SCSP_SUITE_PASS' in text,text[-3000:]
    with wave.open(str(run/'audio.wav'),'rb') as wav:
        assert wav.getsampwidth()==2
        samples=array('h',wav.readframes(wav.getnframes()))
        stats={'core':core,'kind':args.kind,'channels':wav.getnchannels(),'rate':wav.getframerate(),
               'frames':wav.getnframes(),'peak':max(map(abs,samples),default=0),
               'nonzero_samples':sum(v!=0 for v in samples)}
    results.append(stats);print(json.dumps(stats),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')

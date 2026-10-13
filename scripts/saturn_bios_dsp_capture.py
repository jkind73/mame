#!/usr/bin/env python3
# license:BSD-3-Clause
"""Capture live VF2J BIOS DSP state without adding production tracing hooks."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',type=Path,default=Path('saturn'))
parser.add_argument('--rompath',required=True)
parser.add_argument('--nvram-source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=Path(__file__).resolve().parent.parent
out=args.output.resolve();out.mkdir(exist_ok=False);shutil.copytree(args.nvram_source.resolve(),out/'nvram')
command=['nice','-n','10',str(args.binary.resolve()),'saturnjp','vf2j','-noreadconfig','-rompath',args.rompath,'-video','none','-sound','none','-nothrottle','-samplerate','48000','-wavwrite',str(out/'audio.wav'),'-seconds_to_run','12','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/saturn_bios_dsp_capture.lua')]
for option in ('cfg','nvram','diff','state'):command+=['-'+option+'_directory',str(out/option)]
env=os.environ.copy();env['SATURN_DSP_CAPTURE_DIR']=str(out)
with (out/'run.log').open('w')as log:result=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
text=(out/'run.log').read_text()
if result.returncode or 'SATURN_BIOS_DSP_CAPTURE_PASS' not in text or '_FAIL' in text or '[LUA ERROR]' in text:raise RuntimeError(text)
files=sorted(out.glob('frame-*.bin'));assert len(files)==13 and all(p.stat().st_size==527644 for p in files)
print('Live BIOS DSP snapshots and 512KiB RAM PASS',flush=True)

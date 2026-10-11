#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run SCSP DMA and 1Fs diagnostics on the actual Saturn device graph."""
import argparse,os,subprocess
from pathlib import Path
from sh7604_device_test import diagnostic_roms
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);diagnostic_roms(out/'roms')
for core in ('drc','interpreter'):
 run=out/core;run.mkdir();env=dict(os.environ,SCSP_DMA_STATE=str(run/'mid-dma.sta'))
 cmd=['nice','-n','10',str(root/'saturn'),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),'-log','-video','none','-sound','none','-nothrottle','-seconds_to_run','5','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/scsp_dma_sample_test.lua')]
 for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
 if core=='interpreter':cmd+=['-nodrc']
 with (run/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
 t=(run/'run.log').read_text();assert r.returncode==0 and 'SCSP_DMA_SAMPLE_PASS' in t and 'FAIL' not in t and '[LUA ERROR]' not in t,t
 print(core,'SCSP DMA/sample PASS',flush=True)

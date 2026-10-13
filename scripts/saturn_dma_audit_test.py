#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run real-device SCU descriptor, transfer-rate and halt-release diagnostics."""
import argparse
from pathlib import Path
import subprocess,os
from sh7604_device_test import diagnostic_roms
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--binary',type=Path,default=Path('saturn'))
p.add_argument('--only',choices=('indirect','rate','halt','dsp','irq','rtc','reset','systemreset'))
a=p.parse_args();root=Path(__file__).resolve().parent.parent;out=a.output.resolve()
out.mkdir(parents=True,exist_ok=False);diagnostic_roms(out/'roms')
for kind,script,token in [('indirect','saturn_scu_indirect_test.lua','SCU_INDIRECT_PASS'),('rate','saturn_transfer_rate_test.lua','TRANSFER_RATE_PASS'),('halt','saturn_scu_halt_test.lua','SCU_HALT_RELEASE_PASS'),('dsp','saturn_scudsp_concurrency_test.lua','DSP_CONCURRENCY_PASS'),('irq','saturn_irq_queue_test.lua','SCU_IRQ_QUEUE_PASS'),('rtc','saturn_smpc_rtc_test.lua','SMPC_RTC_PASS'),('reset','saturn_smpc_reset_test.lua','SMPC_RESET_PASS'),('systemreset','saturn_system_reset_test.lua','SATURN_SYSTEM_RESET_PASS')]:
 if a.only and a.only!=kind:continue
 for core in ('drc','interpreter'):
  run=out/(kind+'-'+core);run.mkdir()
  cmd=['nice','-n','10',str(a.binary.resolve()),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),'-video','none','-sound','none','-nothrottle','-seconds_to_run',('12' if kind=='rtc' else '5'),'-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts'/script)]
  for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
  if core=='interpreter':cmd+=['-nodrc']
  env=os.environ.copy();env['SMPC_RTC_STATE_PATH']=str(run/'rtc.sta');env['SCU_IRQ_QUEUE_STATE_PATH']=str(run/'irq.sta')
  with (run/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
  t=(run/'run.log').read_text();assert r.returncode==0 and token in t and 'FAIL' not in t and '[LUA ERROR]' not in t,t
  print(kind,core,'PASS',flush=True)

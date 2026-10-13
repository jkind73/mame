#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run real VDP2 register timing diagnostics with both SH2 execution engines."""
import argparse
from pathlib import Path
import subprocess
import os
from sh7604_device_test import diagnostic_roms

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--binary',type=Path,default=Path('saturn'))
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--state',action='store_true',help='Verify scan-edge save/load continuity')
mode.add_argument('--timer1',action='store_true',help='Check SCU Timer 1 against scan-event positions')
mode.add_argument('--reset',action='store_true',help='Verify VDP2 register and decoded-mode reset')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=False)
diagnostic_roms(out/'roms')
for core in ('drc','interpreter'):
    run=out/core
    run.mkdir()
    cmd=['nice','-n','10',str(args.binary.resolve()),'saturnjp','-noreadconfig','-rompath',str(out/'roms'),
         '-video','none','-sound','none','-nothrottle','-seconds_to_run','3','-skip_gameinfo',
         '-autoboot_delay','0','-autoboot_script',str(root/'scripts'/('saturn_scan_state_test.lua' if args.state else 'saturn_timer1_scan_test.lua' if args.timer1 else 'saturn_vdp2_reset_test.lua' if args.reset else 'saturn_scan_timing_test.lua'))]
    for option in ('cfg','nvram','diff','state'):
        cmd += ['-'+option+'_directory',str(run/option)]
    if core=='interpreter':cmd.append('-nodrc')
    env=os.environ.copy();env['SATURN_SCAN_STATE_PATH']=str(run/'scan.sta')
    with (run/'run.log').open('w') as log:
        result=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    text=(run/'run.log').read_text()
    token='SATURN_SCAN_STATE_PASS' if args.state else 'SATURN_TIMER1_SCAN_PASS' if args.timer1 else 'SATURN_VDP2_RESET_PASS' if args.reset else 'SATURN_SCAN_TIMING_PASS'
    if result.returncode or token not in text or '[LUA ERROR]' in text or '_FAIL' in text:
        raise RuntimeError(text)
    print(core+' VDP2 register timing PASS',flush=True)

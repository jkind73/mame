#!/usr/bin/env python3
# license:BSD-3-Clause
"""Depth-guarded fixed-point DEXE payload; never execute it on an old native core.

Unlike the cached-parameter-corruption payload, this preserves DMEA/DRGA and
reissues the identical DMA indefinitely on the old implementation. Re-use the
actual-method harness and its depth assertion to stop at the first nested call.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
script=(ROOT/'regtests/saturn/test_scsp_irq_ports.py').read_text()
old='s.ram[0x8000]=0x9000;s.ram[0x8002]=0x700;'
assert script.count(old)==1
script=script.replace(old,'s.ram[0x8000]=0x8000;s.ram[0x8002]=0x412;')
env=os.environ.copy()
env.setdefault('SCSP_IRQ_SOURCE',str(ROOT/'src/devices/sound/scsp.cpp'))
with tempfile.TemporaryDirectory(prefix='scsp-fixedpoint-') as tmp:
    path=Path(tmp)/'test.py';path.write_text(script)
    subprocess.run([sys.executable,str(path)],env=env,check=True)
print('SCSP fixed-point DMA recursion control passed (actual methods, not native execution)')

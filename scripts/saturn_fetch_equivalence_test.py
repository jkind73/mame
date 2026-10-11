#!/usr/bin/env python3
# license:BSD-3-Clause
"""Verify the optimized VDP2 fetch traversal against its prior access/output trace."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='saturn-fetch-equivalence-') as tmp:
    binary=Path(tmp)/'test'
    subprocess.run(['clang++','-std=c++17','-O1','-fsanitize=address,undefined',
                    '-I',str(root/'src/mame/sega'),'-I',str(root/'tests/saturn'),
                    str(root/'tests/saturn/vdp2_fetch_equivalence_test.cpp'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

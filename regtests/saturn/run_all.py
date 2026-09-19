#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Run the ROM-free Saturn callback/renderer regression tests.

Requires Python 3, Git with the pinned baseline commits, and a C++ compiler
supporting ASan/UBSan. Set CXX to select the compiler. Does not build MAME.
"""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
for test in sorted(HERE.glob("test_*.py")):
    print(f"\n=== {test.name} ===", flush=True)
    subprocess.run([sys.executable, str(test)], check=True)
print("\nAll Saturn regression scripts passed.")

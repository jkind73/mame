#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compile controller units that previously depended on an implicit emu.h PCH."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
includes = ['src/osd', 'src/emu', 'src/lib', 'src/lib/util', 'src/devices',
            '3rdparty', '3rdparty/asio/include', '3rdparty/expat/lib',
            '3rdparty/softfloat3/source/include', '3rdparty/rapidjson/include']
for name in ('analog', 'ctrl', 'racing', 'gun', 'mission'):
    source = ROOT / 'src/devices/bus/sat_ctrl' / (name + '.cpp')
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-fsyntax-only',
                    *('-I' + str(ROOT / p) for p in includes), str(source)], check=True)
print('5 Saturn controller translation units compile without precompiled headers')

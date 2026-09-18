#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compile controller and sound-DSP units that previously depended on an implicit emu.h PCH."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
includes = ['src/osd', 'src/emu', 'src/lib', 'src/lib/util', 'src/devices',
            '3rdparty', '3rdparty/asio/include', '3rdparty/expat/lib',
            '3rdparty/softfloat3/source/include', '3rdparty/rapidjson/include']
sources = ['src/devices/bus/sat_ctrl/' + name + '.cpp'
           for name in ('analog', 'ctrl', 'racing', 'gun', 'mission')]
sources.append('src/devices/sound/scspdsp.cpp')
for name in sources:
    source = ROOT / name
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-fsyntax-only',
                    *('-I' + str(ROOT / p) for p in includes), str(source)], check=True)
print('6 Saturn controller/sound-DSP translation units compile without precompiled headers')

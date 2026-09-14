#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Run Saturn regressions and compile the changed translation units to objects.

--full additionally builds a focused SDL Saturn/ST-V executable and runs MAME's
ROM-free -validate command. Neither mode boots a game or validates real hardware.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--full", action="store_true", help="also link and run configuration validation")
parser.add_argument("--jobs", type=int, default=2, help="parallel full-build jobs (default: 2)")
args = parser.parse_args()
if args.jobs < 1:
    parser.error("--jobs must be positive")


def run(command):
    print("+ " + " ".join(map(str, command)), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


if args.full:
    for tool in ("make", "pkg-config"):
        if not shutil.which(tool):
            parser.error(f"{tool} is required for --full; see README.md build instructions")
    run(["pkg-config", "--exists", "sdl2", "SDL2_ttf", "fontconfig"])

run([sys.executable, str(ROOT / "regtests/saturn/run_all.py")])
flags = ["-std=c++20", "-O1", "-c", "-fno-strict-aliasing", "-DMAME_NOASM",
         "-D__STDC_CONSTANT_MACROS", "-D__STDC_FORMAT_MACROS", "-D__STDC_LIMIT_MACROS"]
for directory in ("src", "src/emu", "src/lib", "src/lib/util", "src/devices",
                  "src/mame", "src/osd", "src/osd/modules"):
    flags += ["-I", directory]
with tempfile.TemporaryDirectory(prefix="saturn-objects-") as directory:
    for name in ("saturn", "saturn_vdp2", "saturn_scu"):
        run([os.environ.get("CXX", "g++"), *flags, f"src/mame/sega/{name}.cpp",
             "-o", str(Path(directory) / (name + ".o"))])
print("Regressions and three object compilations passed (not a linked MAME build).", flush=True)

if args.full:
    run(["make", f"-j{args.jobs}", "SUBTARGET=saturn", "REGENIE=1", "SYMBOLS=0", "OPTIMIZE=1",
         "SOURCES=src/mame/sega/saturn.cpp,src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp",
         "USE_QTDEBUG=0", "NO_X11=1", "NO_USE_XINPUT=1", "NO_OPENGL=1",
         "NO_USE_MIDI=1", "NO_USE_PORTAUDIO=1", "NO_USE_PULSEAUDIO=1", "NO_USE_PIPEWIRE=1"])
    run([str(ROOT / "mamesaturn"), "-validate"])
    print("Focused executable linked and MAME configuration validation passed; no games booted.")

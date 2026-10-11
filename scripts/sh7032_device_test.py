#!/usr/bin/env python3
# license:BSD-3-Clause
"""Build/run an isolated diagnostic machine with the actual Saturn SH-1 CPU."""
import argparse
from pathlib import Path
import os, shutil, struct, subprocess, zipfile

ROOT=Path(__file__).resolve().parent.parent

def build(sanitize=False):
    fixture=ROOT/'src/mame/skeleton/sh1diag.cpp'
    listing=ROOT/'src/mame/mame.lst'
    assert not fixture.exists(), 'Refusing to overwrite an existing driver'
    original=listing.read_bytes()
    addition=b'\n@source:skeleton/sh1diag.cpp\nsh1diag\n'
    try:
        shutil.copyfile(ROOT/'tests/saturn/sh7032_device.cpp',fixture)
        listing.write_bytes(original+addition)
        # Make does not detect changed sanitizer options in generated projects.
        (ROOT/'build/projects/sdl3/mamesh1diag/gmake-osx-clang/Makefile').unlink(missing_ok=True)
        os.utime(ROOT/'src/devices/cpu/sh/sh7032.cpp',None)
        command=['make','SUBTARGET=sh1diag','SOURCES=src/mame/skeleton/sh1diag.cpp',
                 'OSD=sdl3','USE_LIBSDL=0','-j2']
        if sanitize:command+=['SANITIZE=address,undefined','SYMBOLS=0','PRECOMPILE=0']
        subprocess.run(command,cwd=ROOT,check=True)
    finally:
        current=listing.read_bytes()
        if current==original+addition:listing.write_bytes(original)
        else:listing.write_bytes(current.replace(addition,b'',1))
        fixture.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--build',action='store_true')
    p.add_argument('--sanitize',action='store_true',help='instrument the SH7032 and diagnostic-driver objects with ASan/UBSan')
    a=p.parse_args()
    if a.build or a.sanitize:build(a.sanitize)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rom=bytearray(0x10000)
    struct.pack_into('>IIII',rom,0,0x100,0x0ffffe00,0x180,0x0ffffd00)
    for vector in range(4,64):struct.pack_into('>I',rom,vector*4,0x100)
    struct.pack_into('>HH',rom,0x100,0xaffe,0x0009)
    struct.pack_into('>HH',rom,0x180,0xaffe,0x0009)
    (out/'roms').mkdir()
    with zipfile.ZipFile(out/'roms/sh1diag.zip','w',zipfile.ZIP_DEFLATED) as z:z.writestr('diagnostic.bin',rom)
    for core in ('drc','interpreter'):
        run=out/core;run.mkdir()
        cmd=['nice','-n','10',str(ROOT/'sh1diag'),'sh1diag','-noreadconfig',
             '-rompath',str(out/'roms'),'-video','none','-sound','none','-nothrottle',
             '-seconds_to_run','3','-autoboot_delay','0','-autoboot_script',str(ROOT/'scripts/sh7032_device_test.lua')]
        for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
        if core=='interpreter':cmd+=['-nodrc']
        with (run/'run.log').open('w') as log:
            env=os.environ.copy()
            if a.sanitize:env.update(ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            r=subprocess.run(cmd,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        text=(run/'run.log').read_text()
        assert r.returncode==0 and 'SH7032_DEVICE_PASS' in text and 'FAIL' not in text and '[LUA ERROR]' not in text,text
        print(core,'SH7032_DEVICE_PASS',flush=True)

if __name__=='__main__':main()

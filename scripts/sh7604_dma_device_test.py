#!/usr/bin/env python3
# license:BSD-3-Clause
"""Build/run the actual SH7604 with connected external DMA pins and data ports."""
import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parent.parent

def build():
    fixture=ROOT/'src/mame/skeleton/sh2dmadiag.cpp';listing=ROOT/'src/mame/mame.lst'
    assert not fixture.exists()
    original=listing.read_bytes();addition=b'\n@source:skeleton/sh2dmadiag.cpp\nsh2dmadiag\n'
    try:
        shutil.copyfile(ROOT/'tests/saturn/sh7604_dma_device.cpp',fixture)
        listing.write_bytes(original+addition)
        subprocess.run(['make','SUBTARGET=sh2dmadiag','SOURCES=src/mame/skeleton/sh2dmadiag.cpp','OSD=sdl3','USE_LIBSDL=0','-j2'],cwd=ROOT,check=True)
    finally:
        current=listing.read_bytes();listing.write_bytes(original if current==original+addition else current.replace(addition,b'',1))
        fixture.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--output',type=Path,required=True);p.add_argument('--script',type=Path,default=ROOT/'scripts/sh7604_dma_pins_test.lua');a=p.parse_args()
    if a.build:build()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);(out/'roms').mkdir()
    rom=bytearray(0x200);struct.pack_into('>IIII',rom,0,0x100,0x0601ff00,0x100,0x0601ff00)
    struct.pack_into('>HH',rom,0x100,0xaffe,9)
    for v in (9,11):struct.pack_into('>I',rom,v*4,0x100)
    with zipfile.ZipFile(out/'roms/sh2dmadiag.zip','w',zipfile.ZIP_DEFLATED) as z:z.writestr('diagnostic.bin',rom)
    for core in ('drc','interpreter'):
        run=out/core;run.mkdir();env=os.environ.copy();env['SH7604_DMA_PIN_STATE_PATH']=str(run/'dma.sta')
        cmd=['nice','-n','10',str(ROOT/'sh2dmadiag'),'sh2dmadiag','-noreadconfig','-rompath',str(out/'roms'),'-video','none','-sound','none','-nothrottle','-seconds_to_run','5','-autoboot_delay','0','-autoboot_script',str(a.script.resolve())]
        for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(run/d)]
        if core=='interpreter':cmd.append('-nodrc')
        with (run/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        text=(run/'run.log').read_text(errors='replace')
        assert r.returncode==0 and 'SH7604_DMA_PIN_PASS' in text and 'FAIL' not in text and '[LUA ERROR]' not in text,text
        print(core,'SH7604_DMA_PIN_PASS',flush=True)
if __name__=='__main__':main()

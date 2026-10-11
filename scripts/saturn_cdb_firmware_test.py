#!/usr/bin/env python3
# license:BSD-3-Clause
"""Build an isolated enabled real-firmware CD block and inspect its startup."""
import argparse,os,shutil,struct,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def build():
 fixture=ROOT/'src/mame/skeleton/cdbdiag.cpp';listing=ROOT/'src/mame/mame.lst'
 assert not fixture.exists();original=listing.read_bytes();addition=b'\n@source:skeleton/cdbdiag.cpp\ncdbdiag\n'
 try:
  shutil.copyfile(ROOT/'tests/saturn/cdb_firmware_device.cpp',fixture);listing.write_bytes(original+addition)
  for library in ('liboptional.a','libdasm.a'):(ROOT/'build/osx_clang/bin/x64/Release/mame_cdbdiag'/library).unlink(missing_ok=True)
  subprocess.run(['make','REGENIE=1','SUBTARGET=cdbdiag','SOURCES=src/mame/skeleton/cdbdiag.cpp','OSD=sdl3','USE_LIBSDL=0','-j2'],cwd=ROOT,check=True)
 finally:
  current=listing.read_bytes();listing.write_bytes(original if current==original+addition else current.replace(addition,b'',1));fixture.unlink(missing_ok=True)

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--output',type=Path,required=True);p.add_argument('--disc',type=Path);p.add_argument('--seconds',type=int,default=3);p.add_argument('--wav',action='store_true');p.add_argument('--core',choices=['drc','interpreter'],default='interpreter');p.add_argument('--script',type=Path,default=ROOT/'scripts/saturn_cdb_firmware_test.lua');a=p.parse_args()
if a.build:build()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);(out/'roms').mkdir()
rom=bytearray(512);struct.pack_into('>II',rom,0,0x100,0x1fc);struct.pack_into('>HH',rom,0x100,0xaffe,9)
with zipfile.ZipFile(out/'roms/cdbdiag.zip','w') as z:z.writestr('host.bin',rom)
shutil.copyfile('/Volumes/jkind73/mame/roms/satcdb.zip',out/'roms/satcdb.zip')
cmd=['nice','-n','10',str(ROOT/'cdbdiag'),'cdbdiag','-noreadconfig','-rompath',str(out/'roms'),'-video','none','-sound','none','-nothrottle','-seconds_to_run',str(a.seconds),'-autoboot_delay','0','-autoboot_script',str(a.script.resolve()),'-keyboardprovider','none','-joystickprovider','none']
for d in ('cfg','nvram','diff','state'):cmd+=['-'+d+'_directory',str(out/d)]
if a.wav:cmd+=['-wavwrite',str(out/'audio.wav')]
if a.disc:cmd+=['-cdrom',str(a.disc.resolve())]
if a.core=='interpreter':cmd+=['-nodrc']
with (out/'run.log').open('w') as log:r=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=120)
text=(out/'run.log').read_text(errors='replace');print(text);assert r.returncode==0 and '[LUA ERROR]' not in text and 'FIRMWARE_FAIL' not in text,text
if a.script.name=='saturn_cdb_sector_test.lua':assert 'SATURN_CDB_FIRMWARE_PASS' in text,text

if a.script.name=='saturn_cdb_mode2_test.lua':assert 'SATURN_CDB_MODE2_PASS' in text,text
if a.script.name=='saturn_cdb_audio_test.lua':assert 'SATURN_CDB_AUDIO_PASS' in text,text

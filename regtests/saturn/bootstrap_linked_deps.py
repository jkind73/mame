#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Optional Linux x86-64 linked-build dependencies in an external cache.

Requires Python/pip, gh, GCC, make, and system fontconfig runtime. No ROM downloads,
system-package installation or MAME OSD changes. Normal development packages are
preferred. This provisions dummy-video validation, not GPU qualification.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import tarfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--prefix',type=Path,required=True);a=p.parse_args()
base=a.prefix.resolve();root=Path(__file__).resolve().parents[2]
if base==root or root in base.parents:p.error('use a cache outside the repository')
if platform.system()!='Linux' or platform.machine()!='x86_64':p.error('Linux x86-64 required')
tools=base/'tools';deps=base/'deps';base.mkdir(parents=True,exist_ok=True)
for n in ('include/SDL2','include/fontconfig','include/X11','lib/pkgconfig','src'):(deps/n).mkdir(parents=True,exist_ok=True)
def run(args,**kw):
 print('+',shlex.join(map(str,args)),flush=True);subprocess.run(list(map(str,args)),check=True,**kw)
def archive(repo,ref,name):
 path=base/(name+'.tar.gz')
 if not path.exists():
  tmp=path.with_suffix('.download')
  with tmp.open('wb') as out:run(['gh','api',f'repos/{repo}/tarball/{ref}'],stdout=out)
  with tarfile.open(tmp):pass
  tmp.rename(path)
 return tarfile.open(path)
def content(repo,ref,path,dest):
 data=subprocess.check_output(['gh','api',f'repos/{repo}/contents/{path}?ref={ref}'])
 dest.write_bytes(base64.b64decode(json.loads(data)['content']))
def copy_member(tf,m,dest):
 if not dest.resolve().is_relative_to(deps.resolve()):raise RuntimeError('unsafe archive path')
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tf.extractfile(m).read())
run(['/usr/bin/python3','-m','pip','install','--upgrade','--target',tools,'pygame==2.6.1','pkgconf==3.0.1.post0','meson==1.12.0','ninja==1.13.2','mako==1.4.1'])
env=os.environ.copy();env['PYTHONPATH']=str(tools);env['PATH']=str(tools/'bin')+':'+env['PATH']
pkg=tools/'bin/pkg-config';pkg.write_text('#!/bin/sh\nexec /usr/bin/python3 -m pkgconf "$@"\n');pkg.chmod(0o755)
for repo,ref,name,target in [('libsdl-org/SDL','release-2.28.4','SDL-2.28.4','include/SDL2'),('mirror/libX11','libX11-1.8.4','libX11-1.8.4','include')]:
 with archive(repo,ref,name) as tf:
  for m in tf.getmembers():
   if '/include/' in m.name and m.isfile() and m.name.endswith('.h'):
    copy_member(tf,m,deps/target/m.name.split('/include/',1)[1])
content('libsdl-org/SDL_ttf','release-2.20.1','SDL_ttf.h',deps/'include/SDL2/SDL_ttf.h')
content('fontconfig/fontconfig','2.14.1','fontconfig/fontconfig.h',deps/'include/fontconfig/fontconfig.h')
with archive('freedesktop-unofficial-mirror/xorg__proto__xproto','70cf8acf06705097b009a488994b526832b0ef66','xproto') as tf:
 for m in tf.getmembers():
  if m.isfile() and (m.name.endswith('.h') or m.name.endswith('Xfuncproto.h.in')):
   copy_member(tf,m,deps/'include/X11'/Path(m.name).name.removesuffix('.in'))
with archive('NVIDIA/libglvnd','faa23f21fc677af5792825dc30cb1ccef4bf33a6','libglvnd-1.7.0') as tf:
 members=tf.getmembers();source=deps/'src'/members[0].name.split('/')[0]
 for m in members:
  if m.isfile():
   dest=deps/'src'/m.name;copy_member(tf,m,dest);dest.chmod(m.mode)
run(['/usr/bin/python3','-m','mesonbuild.mesonmain','setup',deps/'glvnd-build',source,'--prefix='+str(deps),'--libdir=lib','-Dx11=disabled','-Dglx=disabled','-Degl=true','-Dgles1=false','-Dgles2=false'],env=env)
run([tools/'bin/ninja','-j1','-C',deps/'glvnd-build','install'],env=env)
libs=tools/'pygame.libs'
for name,pattern in [('SDL2','libSDL2-2-*'),('SDL2_ttf','libSDL2_ttf-*')]:
 dest=deps/f'lib/lib{name}.so';dest.unlink(missing_ok=True);dest.symlink_to(next(libs.glob(pattern)))
font=Path('/lib/x86_64-linux-gnu/libfontconfig.so.1')
if not font.exists():raise RuntimeError('system fontconfig runtime required')
dest=deps/'lib/libfontconfig.so';dest.unlink(missing_ok=True);dest.symlink_to(font)
for name,version,lib,inc in [('sdl2','2.28.4','SDL2','/SDL2'),('SDL2_ttf','2.20.1','SDL2_ttf','/SDL2'),('fontconfig','2.14.1','fontconfig','')]:
 (deps/f'lib/pkgconfig/{name}.pc').write_text(f'prefix={deps}\nName: {name}\nDescription: Local validation dependency\nVersion: {version}\nLibs: -L{deps}/lib -l{lib}\nCflags: -I{deps}/include{inc}\n')
values={'PYTHONPATH':str(tools),'PKG_CONFIG_PATH':str(deps/'lib/pkgconfig'),'LIBRARY_PATH':str(deps/'lib'),'LD_LIBRARY_PATH':str(deps/'lib')+':'+str(libs),'CPATH':str(deps/'include'),'LDFLAGS':'-Wl,-rpath-link,'+str(libs)}
script='\n'.join('export '+k+'='+shlex.quote(v) for k,v in values.items())+'\nexport PATH='+shlex.quote(str(tools/'bin'))+':$PATH\n'
(base/'build-env.sh').write_text(script)
print('Source',base/'build-env.sh','before validate_build.py --full --jobs 1.')

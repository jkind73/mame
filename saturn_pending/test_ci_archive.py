#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Synthetic ZIP checks only; payloads are never executed."""
import hashlib
from pathlib import Path
import stat
import tempfile
import zipfile
from unpack_ci_artifact import REQUIRED, unpack_verified

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    for mode in ('good','cache-metadata','unknown-metadata','digest','size','path','symlink','missing','occupied'):
        archive=root/(mode+'.zip');out=root/mode
        with zipfile.ZipFile(archive,'w') as z:
            for name in sorted(REQUIRED):
                if mode=='missing' and name=='status.txt':continue
                if mode=='symlink' and name=='saturn':
                    info=zipfile.ZipInfo(name);info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'/tmp/target')
                else:z.writestr(name,b'fake data, never executed')
            if mode=='cache-metadata':
                for name in ('compiler-paths.txt','ccache-stats.txt','ccache-config.txt'):z.writestr(name,b'diagnostic only')
            if mode=='unknown-metadata':z.writestr('arbitrary.txt',b'no')
            if mode=='path':z.writestr('../escape',b'no')
        size=archive.stat().st_size;digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        if mode=='digest':digest='0'*64
        if mode=='size':size+=1
        if mode=='occupied':out.mkdir();(out/'existing').write_text('preserve')
        try:unpack_verified(archive,out,digest,size)
        except ValueError:
            if mode in ('good','cache-metadata'):raise
        else:
            if mode not in ('good','cache-metadata'):raise RuntimeError('bad archive accepted: '+mode)
    if (root/'escape').exists():raise RuntimeError('path escape')
print('9 synthetic CI archive transfer checks passed; no code execution')

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Unpack a user-transferred CI ZIP only after checking GitHub's artifact digest.

No credentials, ROM transfer, web listener or binary execution. The output must
also pass the existing source/run/executable provenance verifier before use.
"""
import argparse
import json
import subprocess
import sys
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ALLOWED = {'saturn', 'binary.sha256', 'source-commit.txt', 'input-trees.txt',
           'status.txt', 'build.log', 'compiler.txt', 'libc.txt', 'libraries.txt',
           'validate.log', 'regressions.log', 'compiler-paths.txt',
           'ccache-stats.txt', 'ccache-config.txt'}
REQUIRED = {'saturn', 'binary.sha256', 'source-commit.txt', 'input-trees.txt', 'status.txt'}


def unpack_verified(path, destination, digest, size):
    if path.stat().st_size != size:
        raise ValueError('wrong size')
    with path.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != digest:
            raise ValueError('wrong digest')
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or not REQUIRED.issubset(names):
            raise ValueError('duplicate or missing member')
        if sum(m.file_size for m in members) > 256 * 1024 * 1024:
            raise ValueError('oversized expansion')
        for m in members:
            name = PurePosixPath(m.filename)
            if m.filename not in ALLOWED or name.is_absolute() or '..' in name.parts:
                raise ValueError('unexpected member path')
            if stat.S_ISLNK(m.external_attr >> 16) or m.is_dir():
                raise ValueError('non-regular member')
        destination.mkdir(parents=True, exist_ok=True)
        # A fresh destination avoids following a pre-existing local symlink.
        if any(destination.iterdir()):
            raise ValueError('destination is not empty')
        z.extractall(destination)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('--run-id',type=int,required=True)
    p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args()
    if a.run_id<=0:raise ValueError('invalid run ID')
    run=json.loads(subprocess.check_output(['gh','run','view',str(a.run_id),
        '--repo','jkind73/mame','--json','status,conclusion,headSha,headBranch,workflowName'],text=True))
    if (run['status']!='completed' or run['conclusion']!='success' or
        run['headBranch']!='arena/01a09f50-mame' or run['workflowName']!='Saturn integration artifact'):
        raise ValueError('wrong or unsuccessful CI run')
    result=json.loads(subprocess.check_output(['gh','api',
        f'repos/jkind73/mame/actions/runs/{a.run_id}/artifacts'],text=True))
    matches=[m for m in result['artifacts'] if m['name']=='saturn-linux-'+run['headSha'] and not m['expired']]
    if len(matches)!=1:raise ValueError('need exactly one unexpired matching artifact')
    artifact=matches[0]
    match=re.fullmatch(r'sha256:([0-9a-f]{64})',artifact['digest'])
    if not match:raise ValueError('missing artifact digest')
    unpack_verified(a.archive.resolve(),a.destination.resolve(),match[1],artifact['size_in_bytes'])
    subprocess.run([sys.executable,str(Path(__file__).with_name('verify_ci_artifact.py')),
        str(a.destination.resolve()),'--run-id',str(a.run_id)],check=True)


if __name__=='__main__':
    main()

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare complete startup save files across builds and different heap fills.

No bytes are excluded. Named field differences are diagnostic output only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zlib


def differences(left, right, layout):
    a, b = zlib.decompress(left[32:]), zlib.decompress(right[32:])
    assert len(a) == len(b), 'Different serialized sizes'
    result = []
    for line in layout.read_text().splitlines():
        index, offset, size, name = line.split('\t', 3)
        offset, size = int(offset), int(size)
        count = sum(x != y for x, y in zip(a[offset:offset+size], b[offset:offset+size]))
        if count:
            result.append({'index': int(index), 'name': name, 'offset': offset, 'size': size, 'different_bytes': count})
    assert sum(int(line.split('\t')[2]) for line in layout.read_text().splitlines()) == len(a), 'Incomplete save layout'
    return {'header_equal': left[:32] == right[:32], 'payload_equal': a == b, 'fields': result}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-a', type=Path, required=True)
    p.add_argument('--build-b', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--rompath', required=True)
    p.add_argument('--vf2-disc', type=Path, required=True)
    p.add_argument('--seed-root', type=Path, required=True)
    p.add_argument('--games', nargs='+', choices=['diehard', 'vfkids', 'vf2'], default=['diehard', 'vfkids', 'vf2'])
    p.add_argument('--cores', nargs='+', choices=['drc', 'interpreter'], default=['drc', 'interpreter'])
    a = p.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    results = []
    for core in a.cores:
        for game in a.games:
            machine = 'saturneu' if game == 'vf2' else game
            runs = []
            for label, binary, fill in [('a', a.build_a, '0'), ('b', a.build_b, '1')]:
                run = out/core/game/label; run.mkdir(parents=True)
                for d in ['cfg', 'nvram', 'diff', 'state']: (run/d).mkdir()
                seed = a.seed_root/game/'nvram'/machine
                assert seed.is_dir(), 'Missing NVRAM seed: '+str(seed)
                shutil.copytree(seed, run/'nvram'/machine)
                cmd = ['nice', '-n', '10', str(binary.resolve()), machine,
                       '-noreadconfig', '-rompath', a.rompath, '-hashpath', str(root/'hash'),
                       '-video', 'none', '-sound', 'none', '-nothrottle', '-frameskip', '0',
                       '-keyboardprovider', 'none', '-mouseprovider', 'none',
                       '-joystickprovider', 'none', '-lightgunprovider', 'none',
                       '-seconds_to_run', '37', '-rtc', '20000101000000', '-skip_gameinfo',
                       '-autoboot_delay', '0', '-autoboot_script', str(root/'scripts/saturn_vdp_capture.lua'),
                       '-snapshot_directory', str(run)]
                for d in ['cfg', 'nvram', 'diff', 'state']: cmd += ['-'+d+'_directory', str(run/d)]
                if core == 'interpreter': cmd += ['-nodrc']
                if game == 'vf2': cmd += ['-cdrom', str(a.vf2_disc.resolve())]
                env = os.environ.copy(); env['MallocPreScribble'] = fill
                (run/'command.json').write_text(json.dumps({'command':cmd, 'MallocPreScribble':fill}, indent=2)+'\n')
                print(core, game, label, 'capturing', flush=True)
                with (run/'run.log').open('w') as log:
                    subprocess.run(cmd, env=env, cwd=run, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
                assert '[LUA ERROR]' not in (run/'run.log').read_text()
                runs.append(run)
            assert (runs[0]/'state-layout.tsv').read_bytes() == (runs[1]/'state-layout.tsv').read_bytes(), 'Different registered layouts'
            for frame in [1, 60, 300, 600, 1200, 1800]:
                name = f'frame-{frame:04d}'
                left, right = [(run/(name+'.sta')).read_bytes() for run in runs]
                entry = {'core':core, 'game':game, 'frame':frame, 'equal':left == right,
                         'sha256':[hashlib.sha256(x).hexdigest() for x in (left,right)],
                         'pixels_equal':(runs[0]/(name+'.pixels')).read_bytes() == (runs[1]/(name+'.pixels')).read_bytes()}
                if left != right: entry['differences'] = differences(left, right, runs[1]/'state-layout.tsv')
                results.append(entry)
                print(core, game, frame, 'full state equal:', entry['equal'], flush=True)
            (out/'comparison.json').write_text(json.dumps(results, indent=2)+'\n')
    assert all(r['equal'] and r['pixels_equal'] for r in results), 'Startup parity failed; see comparison.json (no byte masking)'
    print('SATURN_STARTUP_STATE_PASS complete save files and pixels match across builds/heaps', flush=True)


if __name__ == '__main__': main()

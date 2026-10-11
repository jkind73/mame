#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare a visually reviewed Virtual Kyoutei 2 race replay across CPU cores.

These checks establish replay consistency and valid command lists. They do not
replace visual review or establish agreement with physical Saturn hardware.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


def audit(directory, minimum_frame, race_start, race_end):
    log = (directory/'run.log').read_text(errors='replace')
    match = re.search(r'RACE_RUN_COMPLETE frame=(\d+) bad_init=(\d+)', log)
    assert match and int(match[1]) >= minimum_frame and int(match[2]) == 0, 'Incomplete or corrupt capture: '+str(directory)
    assert not any(s in log for s in ('BAD_INIT ', '[LUA ERROR]', 'emu_fatalerror')), 'Runtime failure: '+str(directory)
    records = re.findall(r'RACE_FRAME frame=(\d+).*?polygons=(\d+) invalid=(\d+) ended=(\w+) loop=(\w+) bad=(\d+)', log)
    assert records, 'Missing frame records'
    for f, polygons, invalid, ended, loop, bad in records:
        assert invalid == bad == '0' and ended == 'true' and loop == 'false', 'Invalid command list at frame '+f
    geometry, maxima = {}, []
    for path in sorted(directory.glob('frame-*-vdp1.csv')):
        frame = int(path.name.split('-')[1])
        with path.open() as source:
            rows = list(csv.DictReader(source))
        shapes = [r for r in rows if int(r['control'],16)&15 in (2,3,4) and not int(r['control'],16)&0xc000]
        if shapes:
            maxima.append(max(abs(int(r[k])) for r in shapes for k in ('xa','ya','xb','yb','xc','yc','xd','yd')))
        if race_start <= frame <= race_end:
            geometry[frame] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(geometry) >= 20 and len(set(geometry.values())) >= 10, 'Insufficient changing race geometry'
    return {'frames': len(records), 'max_polygons': max(int(r[1]) for r in records),
            'max_abs_coordinate': max(maxima), 'race_samples': len(geometry),
            'distinct_race_lists': len(set(geometry.values()))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('drc', type=Path)
    p.add_argument('interpreter', type=Path)
    p.add_argument('--minimum-frame', type=int, default=30000)
    p.add_argument('--race-start', type=int, default=20700)
    p.add_argument('--race-end', type=int, default=29520)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--require-exact', action='store_true', help='Fail if any capture differs between cores')
    a = p.parse_args()
    result = {name: audit(path, a.minimum_frame, a.race_start, a.race_end)
              for name, path in (('drc',a.drc), ('interpreter',a.interpreter))}
    for pattern, label in (('frame-*-vdp1.csv','command_lists'), ('frame-*.png','screenshots')):
        left = {p.name: p for p in a.drc.glob(pattern)}
        right = {p.name: p for p in a.interpreter.glob(pattern)}
        assert left.keys() == right.keys(), 'Different captured frame sets: '+label
        different = [name for name in left if left[name].read_bytes() != right[name].read_bytes()]
        result[label] = {'compared':len(left), 'different':different}
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('VKYOUTE2_RACE_CAPTURE_CHECKS_PASS valid changing command lists and normal completion; visual review and hardware comparison remain separate')
    for label in ('command_lists', 'screenshots'):
        print(f"{label}: {len(result[label]['different'])}/{result[label]['compared']} differ between cores")
    if a.require_exact:
        assert not any(result[label]['different'] for label in ('command_lists', 'screenshots')), 'CPU-core replay divergence; see comparison report'


if __name__ == '__main__':
    main()

"""fzdrive.py seed count out_prefix : run each fuzz case in its own vdp1fuzz process (some cases hang Ymir),
combine into <prefix>_cases.bin / _ymir.bin / _desc.txt; hung cases get a 0xFF-filled Ymir frame and are listed in _hung.txt"""
import os, subprocess, sys, tempfile

here = os.path.dirname(os.path.abspath(__file__))
exe = os.path.join(here, 'build', 'vdp1fuzz.exe')
seed, count, prefix = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
env = dict(os.environ)
env['PATH'] = r'C:\msys64\ucrt64\bin;' + env['PATH']
tmp = tempfile.mkdtemp(prefix='fz')
cases = open(prefix + '_cases.bin', 'wb')
ymir = open(prefix + '_ymir.bin', 'wb')
desc = open(prefix + '_desc.txt', 'w')
hung = []
for i in range(count):
    p = os.path.join(tmp, 'c')
    try:
        subprocess.run([exe, str(seed), str(i), '1', p], env=env, timeout=15, check=True,
                       stderr=subprocess.DEVNULL)
        ok = True
    except subprocess.TimeoutExpired:
        ok = False
    except subprocess.CalledProcessError:
        ok = False
    # the case image and description are written before drawing starts
    cases.write(open(p + '_cases.bin', 'rb').read())
    desc.write(open(p + '_desc.txt').read())
    if ok:
        ymir.write(open(p + '_ymir.bin', 'rb').read())
    else:
        hung.append(i)
        ymir.write(b'\xff' * 0x40000)
    for suf in ('_cases.bin', '_desc.txt', '_ymir.bin'):
        try:
            os.remove(p + suf)
        except OSError:
            pass
open(prefix + '_hung.txt', 'w').write(' '.join(map(str, hung)))
print('cases', count, 'hung', hung)

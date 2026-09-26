"""vd2tools.py gen <cap> <n> <seed> <mutfile>   |   vd2tools.py cmp <mutfile> <ymir.bin> <mame.bin> [dump_case]"""
import random, struct, sys


def load_cap(path):
    all_ = open(path, 'rb').read()
    p, m = 15, {}
    while p + 4 <= len(all_):
        nl = struct.unpack('>I', all_[p:p + 4])[0]; p += 4
        name = all_[p:p + nl].decode(); p += nl
        el, ln = struct.unpack('>II', all_[p:p + 8]); p += 8
        m[name] = all_[p:p + ln]; p += ln
    return m


def regs_of(cap):
    r = list(struct.unpack('<256H', cap['m_vdp2_regs'][:512]))
    r[0] = struct.unpack('<I', (cap['vdp2.m_tvmd'] + b'\0\0\0\0')[:4])[0] & 0xffff
    r[1] = struct.unpack('<I', (cap['vdp2.m_exten'] + b'\0\0\0\0')[:4])[0] & 0xffff
    return r


if sys.argv[1] == 'gen':
    cap = load_cap(sys.argv[2]); n = int(sys.argv[3]); rng = random.Random(int(sys.argv[4]))
    base = regs_of(cap)
    # register words 0x00..0x8F (byte offsets 0x000-0x11E); TVMD/EXTEN/VRSIZE/HCNT/VCNT/RAMCTL area is included
    cand = [i for i in range(0x90) if i not in (4, 5, 6, 7)]  # skip status/counter registers
    with open(sys.argv[5], 'w') as f:
        NOSPR = {120: 0, 121: 0, 122: 0, 123: 0}  # PRISA-PRISD: hide the sprite layer (VDP1 state differs)
        f.write(' '.join('%d=%d' % kv for kv in sorted(NOSPR.items())) + '\n')
        for _ in range(n):
            muts = dict(NOSPR)
            for _k in range(rng.choice((1, 1, 1, 2, 3))):
                i = rng.choice(cand)
                v = muts.get(i, base[i])
                if rng.random() < 0.8:
                    for _b in range(rng.choice((1, 1, 2))):
                        v ^= 1 << rng.randrange(16)
                else:
                    v = rng.randrange(65536)
                muts[i] = v & 0xffff
            f.write(' '.join('%d=%d' % kv for kv in sorted(muts.items())) + '\n')
    sys.exit()


def frames(path):
    d = open(path, 'rb').read()
    p, out = 0, []
    while p + 8 <= len(d):
        w, h = struct.unpack('<II', d[p:p + 8]); p += 8
        out.append((w, h, d[p:p + w * h * 4])); p += w * h * 4
    return out


mut = open(sys.argv[2]).read().splitlines()
ym = frames(sys.argv[3]); ma = frames(sys.argv[4])
n = min(len(ym), len(ma))
print('cases', len(mut), 'ymir frames', len(ym), 'mame frames', len(ma))
bad = []
for i in range(n):
    (w1, h1, a), (w2, h2, b) = ym[i], ma[i]
    if (w1, h1) != (w2, h2):
        bad.append((i, 'size %dx%d vs %dx%d' % (w1, h1, w2, h2))); continue
    diff = 0
    for k in range(0, len(a), 4):
        # ymir bytes r,g,b,a ; mame bytes b,g,r,a
        if abs(a[k] - b[k + 2]) > 8 or abs(a[k + 1] - b[k + 1]) > 8 or abs(a[k + 2] - b[k]) > 8:
            diff += 1
    if diff:
        bad.append((i, 'diff pixels %d of %d' % (diff, w1 * h1)))
print('differing cases', len(bad))
for i, s in bad:
    print(i, mut[i], '->', s)

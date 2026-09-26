import sys, re, collections
prefix = sys.argv[1]
N = 0x40000
y = open(prefix + '_ymir.bin', 'rb').read()
m = open(prefix + '_mame.bin', 'rb').read()
desc = open(prefix + '_desc.txt').read().splitlines()
count = len(y) // N
assert len(m) // N == count, (len(m) // N, count)


def words(b, big):
    return [int.from_bytes(b[i:i + 2], 'big' if big else 'little') for i in range(0, len(b), 2)]


# work out byte orders from all cases: pick the pairing with the fewest total differences
def total(ybig, mbig, cases):
    t = 0
    for c in cases:
        a = words(y[c * N:(c + 1) * N], ybig)
        b = words(m[c * N:(c + 1) * N], mbig)
        t += sum(1 for p, q in zip(a, b) if p != q)
    return t


probe = list(range(min(count, 12)))
best = min(((yb, mb) for yb in (0, 1) for mb in (0, 1)), key=lambda k: total(k[0], k[1], probe))
print('byte orders (ymir big, mame big):', best)
yb, mb = best
bad = []
stats = collections.Counter()
tot = collections.Counter()
for c in range(count):
    a = words(y[c * N:(c + 1) * N], yb)
    b = words(m[c * N:(c + 1) * N], mb)
    d = [i for i in range(len(a)) if a[i] != b[i]]
    kind = re.search(r'kind=(\d+)', desc[c]).group(1)
    tvmr = re.search(r'tvmr=(\d)', desc[c]).group(1)
    tot[(kind, tvmr)] += 1
    if d:
        stats[(kind, tvmr)] += 1
        bad.append((c, len(d), d[0]))
print('cases', count, 'differing', len(bad))
for k in sorted(tot):
    print('kind %s tvmr %s: %d/%d differ' % (k[0], k[1], stats[k], tot[k]))
with open(prefix + '_diff.txt', 'w') as f:
    for c, n, first in bad:
        f.write('%d ndiff=%d first=%d(word) %s\n' % (c, n, first, desc[c]))

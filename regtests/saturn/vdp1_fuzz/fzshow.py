import sys
prefix, c = sys.argv[1], int(sys.argv[2])
N = 0x40000
y = open(prefix + '_ymir.bin', 'rb').read()[c * N:(c + 1) * N]
m = open(prefix + '_mame.bin', 'rb').read()[c * N:(c + 1) * N]
desc = open(prefix + '_desc.txt').read().splitlines()[c]
print(desc)
tv = int(desc.split('tvmr=')[1][0])
W = 512
a = [int.from_bytes(y[i:i + 2], 'little') for i in range(0, N, 2)]
b = [int.from_bytes(m[i:i + 2], 'big') for i in range(0, N, 2)]
rows = {}
for i in range(len(a)):
    if a[i] != b[i]:
        rows.setdefault(i // W, []).append((i % W, a[i], b[i]))
n = 0
for r in sorted(rows):
    for x, p, q in rows[r]:
        print('y=%d x=%d ymir=%04x mame=%04x' % (r, x, p, q))
        n += 1
        if n > int(sys.argv[3]) if len(sys.argv) > 3 else n > 30:
            sys.exit()
# extents of drawn pixels
nzy = [i for i in range(len(a)) if a[i]]
nzm = [i for i in range(len(b)) if b[i]]
print('nz ymir', len(nzy), 'mame', len(nzm))

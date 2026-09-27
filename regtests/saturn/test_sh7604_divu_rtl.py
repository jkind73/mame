#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""DIVU results of the production SH7604 code against a cycle-level port of the MiSTer DIVU.sv divider.

The production dvdnt_w / dvdntl_w bodies are extracted from src/devices/cpu/sh/sh7604.cpp and compiled unchanged;
the reference is a step-by-step transcription of Saturn_MiSTer/rtl/SH/SH7604/DIVU.sv (same register update order,
overflow decision at step 5, result selection at step 38). Every case compares OVF, DVDNTH and DVDNTL.

Environment: SH7604_SOURCE overrides the source file (used to run the negative control on the old text),
DIVU_CASES the number of random cases (default 20000).
"""
import os, random, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = Path(os.environ.get('SH7604_SOURCE', ROOT / 'src/devices/cpu/sh/sh7604.cpp')).read_text()


def extract(sig):
    a = source.index(sig); b = source.index('{', a) + 1; d = 1
    while d:
        d += (source[b] == '{') - (source[b] == '}'); b += 1
    return source[a:b]


M = 0xFFFFFFFFFFFFFFFF


def rtl(dvdnth, dvdntl, dvsr, div64, ovfie):
    """Cycle-level port of DIVU.sv; returns (ovf, dvdnth, dvdntl)."""
    m65 = (1 << 65) - 1
    sext = lambda v, n: v - (1 << n) if v >> (n - 1) & 1 else v
    H, L = (dvdnth & 0xFFFFFFFF), (dvdntl & 0xFFFFFFFF)
    if not div64:
        H = 0xFFFFFFFF if L >> 31 else 0
    S = dict(step=0, R=0, D=0, Q=0, R64=0, D64=0, Rs=0, Ds=0, T64=0, OVF=0, OVF0=0, O33=0, VAL=0, NEG=0)
    ovf_flag = 0
    while S['step'] != 0x3F:
        # F phase
        st = S['step']
        if st == 1:
            S['VAL'] = ((H >> 31) << 64) | (H << 32) | L; S['NEG'] = H >> 31
        if st == 2:
            s = dvsr & 0xFFFFFFFF
            S['VAL'] = ((s >> 31) << 64) | (s << 32); S['NEG'] = s >> 31
        if st == 36:
            S['VAL'] = S['R']; S['NEG'] = S['Rs']
        if st == 37:
            q = S['Q']; S['VAL'] = ((((q >> 31) & 1) * ((1 << 33) - 1)) << 32) | q; S['NEG'] = S['Rs'] ^ S['Ds']
        # R phase (all right-hand sides use the values before this edge)
        o = dict(S); n = dict(S)
        VAL, NEG = o['VAL'], o['NEG']
        NRES = ((VAL ^ (m65 if NEG else 0)) + NEG) & m65
        n['step'] = (st + 1) & 0x3F if st != 0x3F else st
        SUM = (o['R'] - o['D']) & m65
        R64s = sext(o['R64'], 64)
        SUM64 = ((R64s - o['D64']) if o['T64'] else (R64s + o['D64'])) & m65
        if st == 0:
            n['Q'] = 0
        if st == 1:
            n['R'] = NRES; n['Rs'] = NEG; n['R64'] = VAL & M
        if st == 2:
            n['D'] = NRES; n['Ds'] = NEG; n['D64'] = VAL & M
            n['T64'] = 1 - (o['Rs'] ^ NEG)
            if (VAL >> 32) & 0xFFFFFFFF == 0:
                n['OVF0'] = 1
        newHL = None
        if 3 <= st <= 35:
            sb = (SUM >> 64) & 1
            n['R'] = o['R'] if sb else SUM
            n['Q'] = ((o['Q'] << 1) | (1 - sb)) & 0xFFFFFFFF
            n['D'] = (o['D'] >> 1) | (o['D'] & (1 << 64))
            if st <= 5:
                bit = 1 - (((SUM64 >> 63) & 1) ^ o['Ds'])
                n['R64'] = ((SUM64 << 1) & M) | bit
                n['T64'] = bit
            if st == 4:
                n['O33'] = o['T64']
            if st == 5:
                t = o['T64']  # the comparison reads the register, not the value assigned at this edge
                cond = o['OVF0'] or (((o['O33'] != t) or (o['O33'] != (o['Rs'] ^ o['Ds']) and t != (o['Rs'] ^ o['Ds']))) and div64)
                if cond:
                    n['OVF'] = 1; n['R'] = SUM; n['step'] = 38
            newHL = (((H << 1) | (L >> 31)) & 0xFFFFFFFF, ((L << 1) | ((1 - sb) ^ o['Rs'])) & 0xFFFFFFFF)
        if st == 36:
            n['R'] = NRES
        if st == 37:
            n['Q'] = NRES & 0xFFFFFFFF
        if st == 38:
            n['step'] = 0x3F
        # registers block
        if newHL:
            H, L = newHL
        if st == 37:
            H = o['R'] & 0xFFFFFFFF
        if st == 38:
            if o['OVF']:
                x = o['Rs'] ^ o['Ds']
                if not ovfie:
                    L = (x << 31) | ((0 if x else 0x7FFFFFFF)); L &= 0xFFFFFFFF
                    if div64:
                        H = (o['R64'] >> 32) & 0xFFFFFFFF
                else:
                    if div64:
                        L = o['R64'] & 0xFFFFFFFF
                        H = (o['R64'] >> 32) & 0xFFFFFFFF
                ovf_flag = 1
            else:
                L = o['Q']
        S = n
    return ovf_flag, H, L


harness = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <climits>
using offs_t = uint32_t;
#define BIT(x, n) (((x) >> (n)) & 1)
#define LOG(...)
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
struct dev {
 bool m_divu_ovf=false, m_divu_ovfie=false; uint32_t m_dvsr=0, m_dvdntl=0, m_dvdnth=0;
 void divu_latch_shadow(){} void sh2_recalc_irq(){}
 void dvdnt_w(uint32_t offset, uint32_t data, uint32_t mem_mask);
 void dvdntl_w(uint32_t offset, uint32_t data, uint32_t mem_mask);
};
#define sh7604_device dev
// METHODS
int main(int argc, char **argv) {
 uint32_t h, l, s; int mode, ie;
 while (scanf("%u %u %u %d %d", &h, &l, &s, &mode, &ie) == 5) {
  dev d; d.m_dvsr = s; d.m_dvdnth = h; d.m_divu_ovfie = ie;
  if (mode == 0) d.dvdnt_w(0, l, 0xffffffff);
  else { d.m_dvdntl = 0; d.dvdntl_w(0, l, 0xffffffff); }
  printf("%d %u %u\n", d.m_divu_ovf ? 1 : 0, d.m_dvdnth, d.m_dvdntl);
 }
}
'''

methods = '\n'.join(extract('void sh7604_device::' + n) for n in ('dvdnt_w(', 'dvdntl_w('))
methods = methods.replace('int64_t a = m_dvdntl | ((uint64_t)m_dvdnth << 32);', 'int64_t a = m_dvdntl | ((uint64_t)m_dvdnth << 32);')

cases = []
edges32 = [0, 1, 2, 3, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF, 0xFFFFFFFE, 0x40000000, 0xC0000000, 0x12345678, 0xFEDCBA98]
for a in edges32:
    for b in edges32:
        cases.append((0, a, b, 0))          # 32/32 (dvdnt_w)
# 64/32 edges around the +/-2^31 quotient boundary
for b in (1, 2, 3, 0xFFFFFFFF, 0xFFFFFFFE, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFF8000, 0x8000):
    sb = b - (1 << 32) if b >> 31 else b
    for q in (0x7FFFFFFF, 0x80000000, 0x80000001, 0x7FFFFFFE, -0x7FFFFFFF, -0x80000000, -0x80000001, 0, 1, -1):
        for r in (0, 1, -1):
            v = (q * sb + r) & M
            cases.append((v >> 32, v & 0xFFFFFFFF, b, 1))
rnd = random.Random(1)
for _ in range(int(os.environ.get('DIVU_CASES', '20000'))):
    kind = rnd.random()
    b = rnd.getrandbits(32) if kind < 0.5 else rnd.choice(edges32)
    if rnd.random() < 0.5:
        cases.append((0, rnd.getrandbits(32), b, 0))
    else:
        h = rnd.getrandbits(32) if rnd.random() < 0.6 else rnd.choice((0, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000))
        cases.append((h, rnd.getrandbits(32), b, 1))

with tempfile.TemporaryDirectory(prefix='divu-') as tmp:
    p = Path(tmp)
    (p / 'h.cpp').write_text(harness.replace('// METHODS', methods))
    cxx = os.environ.get('CXX', 'g++')
    subprocess.run([cxx, '-std=c++20', '-O1', str(p / 'h.cpp'), '-o', str(p / 'h')], check=True)
    inp = ''
    for h, l, b, m in cases:
        for ie in (0, 1):
            inp += '%d %d %d %d %d\n' % (h if m else 0, l, b, m, ie)
    out = subprocess.run([str(p / 'h')], input=inp, capture_output=True, text=True, check=True).stdout.split('\n')

bad = 0
k = 0
for h, l, b, m in cases:
    for ie in (0, 1):
        got = tuple(int(x) for x in out[k].split()); k += 1
        want = rtl(h, l, b, m, ie)
        if got != want:
            bad += 1
            if bad <= 12:
                print('MISMATCH %s dvdnth=%08x dvdntl=%08x dvsr=%08x ovfie=%d: code=%s rtl=%s' %
                      ('64/32' if m else '32/32', h if m else 0, l, b, ie,
                       (got[0], '%08x' % got[1], '%08x' % got[2]), (want[0], '%08x' % want[1], '%08x' % want[2])))
print('%d cases, %d mismatches' % (len(cases) * 2, bad))
sys.exit(1 if bad else 0)

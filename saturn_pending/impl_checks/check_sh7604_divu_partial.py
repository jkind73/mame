#!/usr/bin/env python3
"""Strict finite 64/32 overflow intermediate image; method-level, unvalidated.

The paired-32-bit oracle follows the pinned reference recurrence, not a
silicon trace. Signed-128 division supplies range/ordinary-result controls.
Exact-limit ambiguities, zero divisor and INT64_MIN/-1 are excluded.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
mock=Path(__file__).with_name('check_sh7604_divu_min64.py')
head=next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
match=re.search(r'^void sh7604_device::dvdntl_w\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
assert match
method=match[0].replace('sh7604_device::','')
tail=r'''
};
// Independent word-pair implementation: adding/subtracting D*2^32 only
// changes the high word; the following shift carries low[31] into high[0].
uint64_t partial_words(int64_t a,int32_t b) {
 uint32_t high=uint64_t(a)>>32,low=uint32_t(a);
 bool subtract=(a<0)==(b<0);
 for (unsigned cycle=0;cycle<3;++cycle) {
  const int64_t sum=int64_t(high)+(subtract?-int64_t(uint32_t(b)):int64_t(uint32_t(b)));
  const uint32_t wrapped=uint32_t(sum);
  subtract=bool(wrapped&0x80000000)==(b<0);
  high=uint32_t(uint64_t(wrapped)*2+(low>>31));
  low=uint32_t(uint64_t(low)*2+unsigned(subtract));
 }
 return (uint64_t(high)<<32)|low;
}
int main() {
 struct Example { uint64_t a; uint32_t b,high,low; };
 // Bit-pattern examples of the reference recurrence, NOT hardware captures.
 const Example examples[]={
  {0x0000000100000000ULL,0x00000001,0xfffffffe,0x00000004},
  {0xffffffff00000000ULL,0x00000001,0xfffffffe,0x00000004},
  {0x0000000080000001ULL,0xffffffff,0xfffffffe,0x0000000d},
  {0x7fffffffffffffffULL,0x80000000,0xffffffff,0xfffffffc},
  {0x8000000000000000ULL,0x00000001,0x0000000a,0x00000003},
  {0x1234567887654321ULL,0x00000011,0x91a2b2d6,0x3b2a190f},
  {0xedcba987789abcdfULL,0xffffffef,0x6e5d4d29,0xc4d5e6ff},
 };
 for (const auto &example:examples) {
  CHECK(partial_words(int64_t(example.a),int32_t(example.b))==((uint64_t(example.high)<<32)|example.low));
  Device d; d.m_dvsr=example.b; d.m_dvdnth=example.a>>32; d.m_divu_ovfie=true;
  d.dvdntl_w(0,uint32_t(example.a),0xffffffff);
  CHECK(d.m_dvdnth==example.high && d.m_dvdntl==example.low && d.m_divu_ovf);
 }
 unsigned partial=0,saturated=0,normal=0,replays=0,positive=0,negative=0;
 auto run=[&](int64_t a,int32_t b) {
  CHECK(b!=0);
  if (a==INT64_MIN && b==-1) return;
  const __int128 q=__int128(a)/b,r=__int128(a)%b;
  if (q==INT32_MIN || q==__int128(INT32_MAX)+1 || (q==INT32_MAX && r!=0)) return;
  const bool overflow=q<INT32_MIN || q>INT32_MAX;
  const uint64_t bits=overflow?partial_words(a,b):0;
  for (unsigned ie=0;ie<2;++ie) for (unsigned old_ovf=0;old_ovf<2;++old_ovf) {
   Device d; d.m_dvsr=uint32_t(b); d.m_dvdnth=uint64_t(a)>>32;
   d.m_divu_ovf=old_ovf; d.m_divu_ovfie=ie; Device replay=d;
   d.dvdntl_w(0,uint32_t(a),0xffffffff); replay.dvdntl_w(0,uint32_t(a),0xffffffff);
   CHECK(d.m_dvsr==uint32_t(b) && d.m_divu_ovfie==bool(ie));
   CHECK(d.m_divu_ovf==(overflow || bool(old_ovf)) && d.irq_refreshes==unsigned(overflow));
   if (overflow) {
    CHECK(d.m_dvdnth==uint32_t(bits>>32));
    if (ie) { CHECK(d.m_dvdntl==uint32_t(bits)); ++partial; }
    else { CHECK(d.m_dvdntl==(q<0?0x80000000U:0x7fffffffU)); ++saturated; }
    if (q<0) ++negative; else ++positive;
   } else { CHECK(d.m_dvdnth==uint32_t(r) && d.m_dvdntl==uint32_t(q)); ++normal; }
   CHECK(d.snapshot()==replay.snapshot()); ++replays;
  }
 };
 for (const auto &e:examples) run(int64_t(e.a),int32_t(e.b));
 for (int64_t q:std::initializer_list<int64_t>{-(1LL<<40),-2147483650LL,-2147483649LL,-2147483647LL,-1,0,1,2147483647LL,2147483649LL,1LL<<40})
 for (int64_t b:std::initializer_list<int64_t>{INT32_MIN,-17,-2,-1,1,2,17,INT32_MAX}) {
  const __int128 product=__int128(q)*b;
  for (unsigned rem=0;rem<2;++rem) {
   if (rem && (b==1 || b==-1)) continue;
   const __int128 a=product+(product<0?-int(rem):int(rem));
   if (a>=INT64_MIN && a<=INT64_MAX) run(int64_t(a),int32_t(b));
  }
 }
 uint32_t random=0x76040054;
 for (unsigned i=0;i<65536;++i) {
  random=random*1664525U+1013904223U; const uint64_t high=random;
  random=random*1664525U+1013904223U; const int64_t a=int64_t((high<<32)|random);
  random=random*1664525U+1013904223U; run(a,int32_t(random)|1);
 }
 CHECK(partial && saturated && normal && positive && negative);
 std::printf("method-level, unvalidated: 7 reference-pattern examples; %u enabled-overflow partial images; %u disabled-overflow remainder/saturation images; %u in-range results; %u state-copy replays (%u positive and %u negative overflow observations)\n",partial,saturated,normal,replays,positive,negative);
 std::puts("method-level, unvalidated: paired-word recurrence plus signed-128 ordinary oracle; excludes exact-limit detection, zero divisor, INT64_MIN/-1, 32-bit start, cycle/busy behavior and native IRQ/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-divu-partial-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

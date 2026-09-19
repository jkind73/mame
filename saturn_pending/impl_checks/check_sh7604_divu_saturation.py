#!/usr/bin/env python3
"""Disabled-interrupt 64/32 overflow saturates by quotient sign; method-level, unvalidated.

The 128-bit oracle excludes disputed exact-limit cases and never treats
legacy enabled-interrupt or overflow-remainder placeholders as hardware.
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
int main() {
 Device negative; negative.m_dvsr=1; negative.m_dvdnth=0xffffffff;
 negative.dvdntl_w(0,0x7fffffff,0xffffffff);
 CHECK(negative.m_divu_ovf && negative.m_dvdntl==0x80000000);
 unsigned negative_saturated=0,positive_saturated=0,normal=0,enabled=0,replays=0;
 auto run=[&](__int128 a,int64_t b) {
  CHECK(b && b>=INT32_MIN && b<=INT32_MAX && a>=INT64_MIN && a<=INT64_MAX);
  const __int128 q=a/b,r=a%b;
  // These boundaries need separate hardware evidence; do not assert their
  // overflow detection through an ordinary mathematical range oracle.
  if (q==INT32_MIN || q==__int128(INT32_MAX)+1 || (q==INT32_MAX && r!=0)) return;
  const bool overflow=q<INT32_MIN || q>INT32_MAX;
  for (unsigned ie=0;ie<2;++ie) for (unsigned sticky=0;sticky<2;++sticky) {
   Device d; d.m_dvsr=uint32_t(b); d.m_dvdnth=uint64_t(a)>>32;
   d.m_divu_ovf=sticky; d.m_divu_ovfie=ie; Device replay=d;
   d.dvdntl_w(0,uint32_t(a),0xffffffff); replay.dvdntl_w(0,uint32_t(a),0xffffffff);
   CHECK(d.m_dvsr==uint32_t(b) && d.m_divu_ovfie==bool(ie));
   CHECK(d.m_divu_ovf==(overflow || bool(sticky)) && d.irq_refreshes==unsigned(overflow));
   if (overflow) {
    if (!ie) {
     CHECK(d.m_dvdntl==(q<0?0x80000000U:0x7fffffffU));
     if (q<0) ++negative_saturated; else ++positive_saturated;
    } else ++enabled; // status/dispatch only; no intermediate-result oracle
   } else {
    CHECK(d.m_dvdntl==uint32_t(q) && d.m_dvdnth==uint32_t(r)); ++normal;
   }
   CHECK(d.snapshot()==replay.snapshot()); ++replays;
  }
 };
 for (int64_t q : std::initializer_list<int64_t>{-(1LL<<40),-2147483650LL,-2147483649LL,-2147483647LL,-1,0,1,2147483647LL,2147483649LL,1LL<<40})
 for (int64_t b : std::initializer_list<int64_t>{INT32_MIN,-2147483647LL,-3,-1,1,3,INT32_MAX}) {
  const __int128 a=__int128(q)*b;
  if (a>=INT64_MIN && a<=INT64_MAX) run(a,b);
 }
 run(INT64_MIN,-1); run(INT64_MIN,1); run(INT64_MAX,-1); run(INT64_MAX,1);
 uint32_t random=0x7604a55a;
 for (unsigned i=0;i<65536;++i) {
  random=random*1664525U+1013904223U; const uint64_t high=random;
  random=random*1664525U+1013904223U; const int64_t a=int64_t((high<<32)|random);
  random=random*1664525U+1013904223U; const int32_t b=int32_t(random)|1;
  run(a,b);
 }
 std::printf("method-level, unvalidated: %u negative saturations; %u positive saturation controls; %u in-range results; %u enabled-overflow status controls; %u operand-state-copy replays\n",negative_saturated,positive_saturated,normal,enabled,replays);
 std::puts("method-level, unvalidated: fail-fast UBSan; excludes exact-limit overflow detection, divisor zero, overflow remainders, enabled-interrupt results and native timing/IRQ delivery");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-divu-saturation-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

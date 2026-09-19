#!/usr/bin/env python3
"""64-bit minimum / -1 enters DIVU overflow without host UB; method-level, unvalidated.

Only the agreed 64-bit exceptional pair is newly covered. The 32-bit
minimum/-1 quirk, overflow intermediate results and operation latency are
not supplied by this fixture's scalar oracle.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
match=re.search(r'^void sh7604_device::dvdntl_w\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
assert match
method=match[0].replace('sh7604_device::','')
head=r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <tuple>
#define LOG(...) ((void)0)
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using offs_t=unsigned;
struct Device {
 uint32_t m_dvsr=0,m_dvdntl=0,m_dvdnth=0;
 bool m_divu_ovf=false,m_divu_ovfie=false;
 unsigned irq_refreshes=0;
 void sh2_recalc_irq() { ++irq_refreshes; }
 auto snapshot() const { return std::make_tuple(m_dvsr,m_dvdntl,m_dvdnth,m_divu_ovf,m_divu_ovfie,irq_refreshes); }
'''
tail=r'''
};
int main() {
 unsigned exceptional=0,normal=0,replays=0,zero=0;
 for (unsigned enable=0;enable<2;++enable) for (unsigned sticky=0;sticky<2;++sticky) {
  Device d; d.m_dvsr=0xffffffff; d.m_dvdnth=0x80000000; d.m_divu_ovf=sticky; d.m_divu_ovfie=enable;
  Device replay=d;
  d.dvdntl_w(0,0,0xffffffff); replay.dvdntl_w(0,0,0xffffffff);
  CHECK(d.m_divu_ovf && d.m_divu_ovfie==bool(enable) && d.m_dvsr==0xffffffff && d.irq_refreshes==1);
  // With OVFIE disabled, the documented positive-overflow quotient saturates.
  // Neither the intermediate remainder nor OVFIE=1 result is qualified here.
  if (!enable) CHECK(d.m_dvdntl==0x7fffffff);
  CHECK(d.snapshot()==replay.snapshot()); ++exceptional; ++replays;
 }
 // Unambiguous in-range signed divisions retain quotient, remainder and
 // sticky-OVF behavior. Products are formed in 128 bits by the oracle.
 uint32_t random=0x1847604;
 for (unsigned index=0;index<65536;++index) {
  random=random*1664525U+1013904223U; const int32_t b=int32_t(random)|1;
  random=random*1664525U+1013904223U; const int32_t q=int32_t(random)/16;
  random=random*1664525U+1013904223U;
  const uint64_t magnitude=b<0?-int64_t(b):int64_t(b);
  __int128 a=__int128(q)*b;
  const int64_t remainder=int64_t(random%magnitude)*(a<0?-1:1); a+=remainder;
  CHECK(a>=INT64_MIN && a<=INT64_MAX);
  Device d; d.m_dvsr=uint32_t(b); d.m_dvdnth=uint64_t(a)>>32;
  d.m_divu_ovf=index&1; d.m_divu_ovfie=index&2; Device replay=d;
  d.dvdntl_w(0,uint32_t(a),0xffffffff); replay.dvdntl_w(0,uint32_t(a),0xffffffff);
  CHECK(d.m_dvdntl==uint32_t(a/b) && d.m_dvdnth==uint32_t(a%b));
  CHECK(d.m_divu_ovf==bool(index&1) && d.m_divu_ovfie==bool(index&2) && d.irq_refreshes==0);
  CHECK(d.snapshot()==replay.snapshot()); ++normal; ++replays;
 }
 for (int64_t q : {int64_t(INT32_MIN)+1,-2LL,-1LL,0LL,1LL,2LL,int64_t(INT32_MAX)})
 for (int64_t b : {int64_t(INT32_MIN),-2147483647LL,-2LL,-1LL,1LL,2LL,int64_t(INT32_MAX)}) {
  const __int128 a=__int128(q)*b; Device d;
  d.m_dvsr=uint32_t(b); d.m_dvdnth=uint64_t(a)>>32; d.dvdntl_w(0,uint32_t(a),0xffffffff);
  CHECK(d.m_dvdntl==uint32_t(q) && d.m_dvdnth==0 && !d.m_divu_ovf && !d.irq_refreshes); ++normal;
 }
 // Existing divide-by-zero branch is untouched; only status/dispatch is
 // checked, not its known-incomplete output register values.
 for (uint32_t high : {0U,1U,0x7fffffffU,0x80000000U,0xffffffffU}) {
  Device d; d.m_dvdnth=high; d.dvdntl_w(0,0x12345678,0xffffffff);
  CHECK(d.m_divu_ovf && d.m_dvsr==0 && d.irq_refreshes==1); ++zero;
 }
 std::printf("method-level, unvalidated: %u INT64_MIN/-1 cases; %u in-range quotient/remainder controls; %u operand-state-copy replays; %u zero-divisor status controls\n",exceptional,normal,replays,zero);
 std::puts("method-level, unvalidated: fail-fast UBSan; overflow intermediate results, 32-bit min/-1, timing and native DIVU IRQ delivery not qualified");
}
'''
# int64_t is long on some hosts and long long on others; explicit lists
# avoid initializer-list deduction depending on that host typedef.
tail=tail.replace('for (int64_t q : {','for (int64_t q : std::initializer_list<int64_t>{').replace('for (int64_t b : {','for (int64_t b : std::initializer_list<int64_t>{')
with tempfile.TemporaryDirectory(prefix='impl-divu-min64-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

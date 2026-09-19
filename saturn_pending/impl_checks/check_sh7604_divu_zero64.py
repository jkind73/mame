#!/usr/bin/env python3
"""64-bit zero-divisor and host-limit overflow images; method-level, unvalidated."""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
head=next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name('check_sh7604_divu_min64.py').read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
m=re.search(r'^void sh7604_device::dvdntl_w\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
assert m
method=m[0].replace('sh7604_device::','')
tail=r'''
};
int main() {
 unsigned zero=0,limit=0,replays=0;
 auto run=[&](uint64_t bits) {
  // D=0 reduces the three-step recurrence to multiplication by eight,
  // with the complemented original top three bits entering the low word.
  const uint64_t image=uint64_t(__uint128_t(bits)*8+((~bits>>61)&7));
  for (unsigned ie=0;ie<2;++ie) for (unsigned old=0;old<2;++old) {
   Device d; d.m_dvdnth=bits>>32; d.m_dvdntl=~uint32_t(bits);
   d.m_divu_ovf=old; d.m_divu_ovfie=ie; Device replay=d;
   d.dvdntl_w(0,uint32_t(bits),0xffffffff); replay.dvdntl_w(0,uint32_t(bits),0xffffffff);
   CHECK(d.m_dvdnth==uint32_t(image>>32));
   CHECK(d.m_dvdntl==(ie?uint32_t(image):(bits>>63?0x80000000U:0x7fffffffU)));
   CHECK(d.m_dvsr==0 && d.m_divu_ovf && d.m_divu_ovfie==bool(ie) && d.irq_refreshes==1);
   CHECK(d.snapshot()==replay.snapshot()); ++zero; ++replays;
  }
 };
 for (uint64_t top=0;top<8;++top)
 for (uint64_t middle:{0ULL,1ULL,0x12345678ULL,0x1fffffffULL})
 for (uint64_t low:{0ULL,1ULL,7ULL,0x1fffffffULL,0x80000000ULL,0xffffffffULL})
  run((top<<61)|(middle<<32)|low);
 uint32_t random=0x76040056;
 for (unsigned i=0;i<65536;++i) {
  random=random*1664525U+1013904223U; const uint64_t high=random;
  random=random*1664525U+1013904223U; run((high<<32)|random);
 }
 // Reference-derived partial image for INT64_MIN/-1; not a silicon capture.
 for (unsigned ie=0;ie<2;++ie) for (unsigned old=0;old<2;++old) {
  Device d; d.m_dvsr=0xffffffff; d.m_dvdnth=0x80000000;
  d.m_divu_ovf=old; d.m_divu_ovfie=ie; Device replay=d;
  d.dvdntl_w(0,0,0xffffffff); replay.dvdntl_w(0,0,0xffffffff);
  CHECK(d.m_dvdnth==0x0000000a && d.m_dvdntl==(ie?0x00000004U:0x7fffffffU));
  CHECK(d.m_dvsr==0xffffffff && d.m_divu_ovf && d.m_divu_ovfie==bool(ie) && d.irq_refreshes==1);
  CHECK(d.snapshot()==replay.snapshot()); ++limit; ++replays;
 }
 std::printf("method-level, unvalidated: %u zero-divisor images; %u INT64_MIN/-1 images; %u operand-state-copy replays\n",zero,limit,replays);
 std::puts("method-level, unvalidated: fail-fast UBSan; reference-derived arithmetic, not hardware timing/IRQ/alias/save qualification; exact-limit classification remains excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-divu-zero64-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

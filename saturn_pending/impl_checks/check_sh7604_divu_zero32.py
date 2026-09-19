#!/usr/bin/env python3
"""32-bit DIVU zero-divisor output image; method-level, unvalidated.

Reference-derived partial results are not hardware captures. The unsafe,
unresolved signed-32 minimum/-1 pair is deliberately never executed.
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
methods=[]
for name in ('dvdnt_w','dvdnt_r','dvdnth_r','dvdntl_r','dvcr_r'):
    match=re.search(r'^(?:void|uint32_t) sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    methods.append(match[0].replace('sh7604_device::',''))
tail=r'''
};
int main() {
 unsigned zero=0,normal=0,replays=0;
 auto run_zero=[&](uint32_t bits) {
  const int64_t a=int32_t(bits);
  // Mathematical floor division supplies the high word without signed
  // shifts. Multiplication/modulo conversion independently supplies low.
  const int64_t high=(a-(a<0?((1LL<<29)-1):0))/(1LL<<29);
  const uint32_t low=uint32_t(a*8+(a<0?0:7));
  for (unsigned ie=0;ie<2;++ie) for (unsigned sticky=0;sticky<2;++sticky) {
   Device d; d.m_dvdnth=bits^0xa55a5aa5; d.m_dvdntl=~bits;
   d.m_divu_ovf=sticky; d.m_divu_ovfie=ie; Device replay=d;
   d.dvdnt_w(0,bits,0xffffffff); replay.dvdnt_w(0,bits,0xffffffff);
   const uint32_t quotient=ie?low:(a<0?0x80000000:0x7fffffff);
   CHECK(d.m_dvdnth==uint32_t(high) && d.m_dvdntl==quotient);
   CHECK(d.m_dvsr==0 && d.m_divu_ovf && d.m_divu_ovfie==bool(ie) && d.irq_refreshes==1);
   const auto before_reads=d.snapshot();
   CHECK(d.dvdnt_r()==quotient && d.dvdntl_r()==quotient && d.dvdnth_r()==uint32_t(high));
   CHECK(d.dvcr_r()==(1U|(ie<<1)) && d.snapshot()==before_reads);
   CHECK(d.snapshot()==replay.snapshot()); ++zero; ++replays;
  }
 };
 // All low-half words at both sides of each high-word/sign transition.
 for (uint32_t high:{0x0000U,0x1fffU,0x2000U,0x3fffU,0x4000U,0x5fffU,0x6000U,0x7fffU,
                    0x8000U,0x9fffU,0xa000U,0xbfffU,0xc000U,0xdfffU,0xe000U,0xffffU})
 for (uint32_t low=0;low<65536;++low) run_zero((high<<16)|low);
 auto run_normal=[&](int32_t a,int32_t b,unsigned ie,unsigned sticky) {
  CHECK(b && !(a==INT32_MIN && b==-1));
  Device d; d.m_dvsr=uint32_t(b); d.m_dvdnth=0xa55a5aa5;
  d.m_divu_ovf=sticky; d.m_divu_ovfie=ie; Device replay=d;
  d.dvdnt_w(0,uint32_t(a),0xffffffff); replay.dvdnt_w(0,uint32_t(a),0xffffffff);
  CHECK(d.m_dvdntl==uint32_t(int64_t(a)/b) && d.m_dvdnth==uint32_t(int64_t(a)%b));
  CHECK(d.m_dvsr==uint32_t(b) && d.m_divu_ovf==bool(sticky) && d.m_divu_ovfie==bool(ie) && !d.irq_refreshes);
  CHECK(d.snapshot()==replay.snapshot()); ++normal; ++replays;
 };
 for (int64_t a:std::initializer_list<int64_t>{INT32_MIN,INT32_MIN+1,-1,0,1,INT32_MAX})
 for (int64_t b:std::initializer_list<int64_t>{INT32_MIN,-3,-1,1,3,INT32_MAX})
 if (!(a==INT32_MIN && b==-1))
 for (unsigned ie=0;ie<2;++ie) for (unsigned sticky=0;sticky<2;++sticky)
  run_normal(int32_t(a),int32_t(b),ie,sticky);
 uint32_t random=0x76040055;
 for (unsigned i=0;i<65536;++i) {
  random=random*1664525U+1013904223U; const int32_t a=int32_t(random);
  random=random*1664525U+1013904223U; const int32_t b=int32_t(random)|1;
  if (!(a==INT32_MIN && b==-1)) run_normal(a,b,i&1,(i>>1)&1);
 }
 std::printf("method-level, unvalidated: %u zero-divisor register/status/readback images; %u ordinary signed-32 controls; %u operand-state-copy replays\n",zero,normal,replays);
 std::puts("method-level, unvalidated: fail-fast UBSan; formula oracle is reference-derived, not silicon; no signed-32 minimum/-1, native timing/bus/IRQ/save or separate alias qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-divu-zero32-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+'\n'.join(methods)+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

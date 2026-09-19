#!/usr/bin/env python3
"""BSC longword reads zero the upper half; method-level, unvalidated."""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
mock=Path(__file__).with_name('check_sh7604_bsc_access.py')
head=next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
head=head.replace('struct Device {','struct Device { bool m_is_slave=false;')
names=['bcr1','bcr2','wcr','mcr','rtcsr','rtcnt','rtcor']
functions=''
for name in names:
    for suffix,result in [('_r','uint32_t'),('_w','void')]:
        match=re.search(r'^'+result+r' sh7604_device::'+name+suffix+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
        assert match,name+suffix
        functions+=match[0].replace('sh7604_device::','')+'\n'
tail=r'''
};
int main() {
 Device key; key.wcr_w(0,0xa55a1234,0xffffffff); CHECK(key.wcr_r()==0x1234);
 using Reader=uint32_t (Device::*)();
 using Writer=void (Device::*)(offs_t,uint32_t,uint32_t);
 const Reader reads[]={&Device::bcr1_r,&Device::bcr2_r,&Device::wcr_r,&Device::mcr_r,&Device::rtcsr_r,&Device::rtcnt_r,&Device::rtcor_r};
 const Writer writes[]={&Device::bcr1_w,&Device::bcr2_w,&Device::wcr_w,&Device::mcr_w,&Device::rtcsr_w,&Device::rtcnt_w,&Device::rtcor_w};
 uint32_t Device::* const fields[]={&Device::m_bcr1,&Device::m_bcr2,&Device::m_wcr,&Device::m_mcr,&Device::m_rtcsr,&Device::m_rtcnt,&Device::m_rtcor};
 // Retain existing low-field semantics. This is not a new reserved-bit or
 // CMF acknowledgement oracle; upper-half width is the changed contract.
 const uint32_t lower_masks[]={0x1ff7,0xffff,0xffff,0xfefc,0xf8,0xff,0xff};
 // Keep lower reserved bits zero and CMF clear: their write semantics are
 // not part of this read-width contract.
 const uint32_t legal_payloads[]={0x1ff7,0xfc,0xffff,0xfefc,0x78,0xff,0xff};
 unsigned raw=0,keyed=0,replays=0;
 for (unsigned reg=0;reg<7;++reg) for (unsigned slave=0;slave<2;++slave)
 for (uint32_t input=0;input<65536;++input) {
  const uint32_t payload=input&legal_payloads[reg];
  const uint32_t expected=(payload&lower_masks[reg])|((reg==0 && slave)?0x8000:0);
  Device d; d.m_is_slave=slave; (d.*writes[reg])(0,0xa55a0000|payload,0xffffffff);
  const auto before=d.snapshot(); Device replay=d;
  CHECK((d.*reads[reg])()==expected && (replay.*reads[reg])()==expected && d.snapshot()==before);
  ++keyed; ++replays;
  for (uint32_t upper : {0U,1U,0xa55aU,0xffffU}) {
   d.*fields[reg]=(upper<<16)|payload; const auto stored=d.snapshot();
   CHECK((d.*reads[reg])()==expected && d.snapshot()==stored); ++raw;
  }
 }
 std::printf("method-level, unvalidated: %u raw-state read-width cases; %u keyed-write/read controls; %u state-copy replays\n",raw,keyed,replays);
 std::puts("method-level, unvalidated: getters mask upper half without changing storage or existing low-field masks; native word-lane reads and bus timing not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-bsc-read-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

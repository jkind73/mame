#!/usr/bin/env python3
"""RTCSR.CMF read-one/write-zero qualification; method-level, unvalidated.

Flag events are explicitly seeded: the refresh counter/request engine and
native CMI delivery are not supplied by this register-level fixture.
"""
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
functions=''
for name,result in [('rtcsr_r','uint32_t'),('rtcsr_w','void')]:
    match=re.search(r'^'+result+r' sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions+=match[0].replace('sh7604_device::','')+'\n'
# Historical read-body adaptation changes only its unused call signature.
functions=functions.replace('rtcsr_r()', 'rtcsr_r(offs_t offset, uint32_t mem_mask)')
tail=r'''
};
int main() {
 Device unread; unread.m_rtcsr=0x80; unread.rtcsr_w(0,0xa55a0000,0xffffffff);
 CHECK(unread.rtcsr_r(0,0xffff)&0x80);
 unsigned writes=0,replays=0,reads=0,rejected=0;
 for (unsigned flag=0;flag<2;++flag) for (unsigned seen=0;seen<2;++seen)
 for (unsigned one=0;one<2;++one) for (unsigned control=0;control<16;++control) {
  Device d; d.m_rtcsr=0x38|(flag<<7); d.m_rtcsr_read=seen; Device replay=d,expected=d;
  const uint32_t data=0xa55a0000|(one<<7)|(control<<3);
  const bool remains=flag && (!seen || one);
  expected.m_rtcsr=(data&~0x80U)|(remains?0x80:0);
  expected.m_rtcsr_read=seen && remains;
  d.rtcsr_w(0,data,0xffffffff); replay.rtcsr_w(0,data,0xffffffff);
  CHECK(d.snapshot()==expected.snapshot() && d.m_rtcsr_read==expected.m_rtcsr_read);
  CHECK(d.snapshot()==replay.snapshot() && d.m_rtcsr_read==replay.m_rtcsr_read); ++writes; ++replays;
 }
 for (unsigned flag=0;flag<2;++flag) for (unsigned seen=0;seen<2;++seen)
 for (unsigned inspect=0;inspect<2;++inspect)
 for (uint32_t mask : {0xffffffffU,0x0000ffffU,0xffff0000U,0x00ff0000U,0x0000ff00U,0x000000ffU,0U}) {
  Device d; d.m_rtcsr=0xa55a0078|(flag<<7); d.m_rtcsr_read=seen; d.inspect=inspect;
  const auto before=d.snapshot();
  CHECK(d.rtcsr_r(0,mask)==(0x78|(flag<<7)) && d.snapshot()==before);
  const bool qualifies=!inspect && (mask==0xffffffff || mask==0xffff);
  CHECK(d.m_rtcsr_read==(qualifies?bool(flag):bool(seen))); ++reads;
 }
 for (unsigned flag=0;flag<2;++flag) for (unsigned seen=0;seen<2;++seen)
 for (uint32_t mask : {0U,0xffff0000U,0xffffU,0xff000000U,0xffU,0xff00ff00U}) {
  Device d; d.m_rtcsr=0x78|(flag<<7); d.m_rtcsr_read=seen; const auto before=d.snapshot();
  d.rtcsr_w(0,0xa55a0000,mask); CHECK(d.snapshot()==before && d.m_rtcsr_read==bool(seen)); ++rejected;
  d.rtcsr_w(0,0xa55b0000,0xffffffff); CHECK(d.snapshot()==before && d.m_rtcsr_read==bool(seen)); ++rejected;
 }
 Device d; d.m_rtcsr=0x88; // Seed a match, not a refresh-engine simulation.
 d.rtcsr_r(0,0xffff0000); d.rtcsr_w(0,0xa55a0008,0xffffffff); CHECK(d.m_rtcsr&0x80);
 d.inspect=true; d.rtcsr_r(0,0xffff); d.inspect=false;
 d.rtcsr_w(0,0xa55a0008,0xffffffff); CHECK((d.m_rtcsr&0x80) && !d.m_rtcsr_read);
 d.rtcsr_r(0,0xffff); d.rtcsr_w(0,0xa55a0088,0xffffffff); CHECK((d.m_rtcsr&0x80) && d.m_rtcsr_read);
 d.rtcsr_w(0,0xa55a0008,0xffffffff); CHECK(!(d.m_rtcsr&0x80) && !d.m_rtcsr_read);
 d.m_rtcsr|=0x80; // A subsequent match must not reuse the consumed read.
 d.rtcsr_w(0,0xa55a0008,0xffffffff); CHECK(d.m_rtcsr&0x80);
 d.rtcsr_r(0,0xffffffff); d.rtcsr_w(0,0xa55a0008,0xffffffff); CHECK(!(d.m_rtcsr&0x80) && !d.m_rtcsr_read);
 std::printf("method-level, unvalidated: %u CMF write cases; %u state-copy replays; %u read-mask/debugger cases; %u rejected-command controls\n",writes,replays,reads,rejected);
 std::puts("method-level, unvalidated: seeded successive matches consume qualifications; refresh counting, requests, CMI delivery and native reset/save not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-rtcsr-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
assert 'm_rtcsr_read(false)' in source and 'save_item(NAME(m_rtcsr_read));' in source
print('method-level, unvalidated: cold read-history initialization and save registration present; save layout changed')

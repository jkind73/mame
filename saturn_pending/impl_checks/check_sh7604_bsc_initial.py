#!/usr/bin/env python3
"""Cold BSC register image from real constructor expressions; method-level, unvalidated.

Does not instantiate a native device or qualify reset-cause handling. Warm
manual reset must retain BSC settings; generic-reset behavior is separate.
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
head=head.replace('struct Device {','struct Device { bool m_is_slave=false;')
names=['bcr1','bcr2','wcr','mcr','rtcsr','rtcnt','rtcor']
constructor=source.split('sh7604_device::sh7604_device(',1)[1].split('\n{',1)[0]
initializers=[]
functions=''
for name in names:
    match=re.search(r'm_'+name+r'\(([^()]*)\)',constructor)
    assert match,name
    initializers.append('m_'+name+'('+match[1]+')')
    match=re.search(r'^uint32_t sh7604_device::'+name+r'_r\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions+=match[0].replace('sh7604_device::','')+'\n'
functions=functions.replace('rtcsr_r(offs_t offset, uint32_t mem_mask)', 'rtcsr_r(offs_t offset=0, uint32_t mem_mask=~0U)')
head+=' Device() : '+','.join(initializers)+' {}\n'
tail=r'''
};
int main() {
 unsigned reads=0,replays=0;
 for (unsigned slave=0;slave<2;++slave) {
  Device d; d.m_is_slave=slave; Device replay=d;
  CHECK(d.bcr1_r()==(0x03f0|(slave?0x8000:0)));
  CHECK(d.bcr2_r()==0x00fc && d.wcr_r()==0xaaff);
  CHECK(d.mcr_r()==0 && d.rtcsr_r()==0 && d.rtcnt_r()==0 && d.rtcor_r()==0);
  CHECK(d.snapshot()==replay.snapshot() && replay.bcr1_r()==d.bcr1_r());
  reads+=7; ++replays;
 }
 std::printf("method-level, unvalidated: %u cold BSC read images across master/slave selection; %u state-copy controls\n",reads,replays);
 std::puts("method-level, unvalidated: production constructor expressions and actual getters; native cold boot, warm power-on/manual reset distinction and timing not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-bsc-initial-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
for name in names:
    assert 'save_item(NAME(m_'+name+'));' in source,name
print('method-level, unvalidated: original BSC register save registrations retained')

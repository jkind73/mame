#!/usr/bin/env python3
"""Native-width WDT write selector; method-level, unvalidated.

Actual new map-boundary handler plus real keyed word handlers. Historical
negative explicitly models the old 16-bit mapping's lane decomposition;
neither version constructs a native MAME address_space.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/devices/cpu/sh/sh7604.cpp').read_text()
mock=Path(__file__).with_name('check_sh7604_wdt_access.py')
head=next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))

def extract(name):
    match=re.search(r'^void sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    return match[0].replace('sh7604_device::','')

functions=extract('wtcnt_w')+'\n'+extract('rstcsr_w')
if 'void sh7604_device::wdt_w(' in source:
    functions+='\n'+extract('wdt_w')
    assert 'map(0xfffffe80, 0xfffffe83).w(FUNC(sh7604_device::wdt_w));' in source
    assert 'map(0xfffffe80, 0xfffffe81).r(FUNC(sh7604_device::wtcnt_r));' in source
    assert 'map(0xfffffe82, 0xfffffe83).r(FUNC(sh7604_device::rstcsr_r));' in source
else:
    assert 'map(0xfffffe80, 0xfffffe81).rw(FUNC(sh7604_device::wtcnt_r), FUNC(sh7604_device::wtcnt_w));' in source
    assert 'map(0xfffffe82, 0xfffffe83).rw(FUNC(sh7604_device::rstcsr_r), FUNC(sh7604_device::rstcsr_w));' in source
    print('method-level, unvalidated: historical negative uses an explicit 32-to-16 lane-decomposition shim for the old mapping',flush=True)
    functions+=r'''
 void wdt_w(offs_t offset,uint32_t data,uint32_t mem_mask) {
  if (mem_mask>>16) wtcnt_w(0,data>>16,mem_mask>>16);
  if (mem_mask&0xffff) rstcsr_w(0,data,mem_mask);
 }
'''
assert re.search(r'm_program_config\("program",\s*ENDIANNESS_BIG,\s*32,',
                 (ROOT/'src/devices/cpu/sh/sh2.cpp').read_text())
tail=r'''
};
int main() {
 // Both halves contain valid keys. A CPU longword must execute neither,
 // even if overflow status was previously read and could be acknowledged.
 Device both; both.m_wdt_read=3; both.wdt_w(0,0x5a12a500,0xffffffff);
 CHECK(both.m_wtcnt==0x56 && both.m_rstcsr==0xe0 && both.m_wdt_read==3);
 unsigned rejected=0,words=0;
 for (uint32_t mask : {0xffffffffU,0xff000000U,0x00ff0000U,0x0000ff00U,0x000000ffU,0U,0xff00ff00U,0x0fff0000U})
 for (uint32_t word=0;word<65536;++word) {
  Device d; d.m_wdt_read=3; const auto before=d.snapshot();
  d.wdt_w(0,(word<<16)|(word^0x1234),mask);
  CHECK(d.snapshot()==before && d.m_wdt_read==3); ++rejected;
 }
 // All full-word values retain exactly the old per-register dispatch.
 // Inactive lanes deliberately carry another valid keyed command.
 for (unsigned target=0;target<2;++target) for (uint32_t word=0;word<65536;++word) {
  Device d, direct; d.m_wdt_read=direct.m_wdt_read=3;
  if (target) {
   d.wdt_w(0,0x5a120000|word,0x0000ffff); direct.rstcsr_w(0,word,0xffff);
  } else {
   d.wdt_w(0,(word<<16)|0x5a5f,0xffff0000); direct.wtcnt_w(0,word,0xffff);
  }
  CHECK(d.snapshot()==direct.snapshot() && d.m_wdt_read==direct.m_wdt_read); ++words;
 }
 // A series of native byte writes cannot synthesize a keyed command.
 Device split; split.m_wdt_read=3; const auto before=split.snapshot();
 for (unsigned lane=0;lane<4;++lane) split.wdt_w(0,0x5a12a500,0xff000000U>>(8*lane));
 CHECK(split.snapshot()==before && split.m_wdt_read==3);
 std::printf("method-level, unvalidated: %u rejected native/partial-mask writes; %u exact word-lane dispatch controls; split-byte assembly rejected\n",rejected,words);
 std::puts("method-level, unvalidated: write-map and 32-bit big-endian space declarations inspected; native CPU/DRC/DMA address-space dispatch not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-width-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

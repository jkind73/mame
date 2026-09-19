#!/usr/bin/env python3
"""Read-qualified OVF/WOVF with byte-lane/debugger isolation; method-level, unvalidated."""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock = Path(__file__).with_name('check_sh7604_wdt_access.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))
head = '#define BIT(v,n) (((v) >> (n)) & 1)\n'+head
head = head.replace('struct Device {', '''struct Device {
 bool inspect=false;
 Device &machine() { return *this; }
 bool side_effects_disabled() const { return inspect; }
 void rebind() { m_wdtimer=&timer; }
''')

def extract(name, result):
    match = re.search(r'^'+result+r' sh7604_device::'+name+r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    text = match[0].replace('sh7604_device::', '')
    if name in ('wtcnt_r','rstcsr_r'):
        text = text.replace(name+'()',name+'(offs_t offset, uint16_t mem_mask)')
    return text

functions = '\n'.join(extract(n,t) for n,t in (
    ('wtcnt_r','uint16_t'),('rstcsr_r','uint16_t'),('wtcnt_w','void'),('rstcsr_w','void')))
match = re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_wdtimer_callback\)\n\{.*?^\}', source, re.M | re.S)
assert match
functions += '\nvoid sh2_wdtimer_callback(int param)\n' + match[0].split('\n', 1)[1]
tail = r'''
};
int main() {
 Device unread; unread.wtcnt_w(0,0xa538,0xffff); CHECK(unread.m_wtcsr&0x80);
 unsigned writes=0,reads=0,replays=0;
 for (unsigned ovf=0;ovf<2;++ovf) for (unsigned wovf=0;wovf<2;++wovf)
 for (unsigned seen=0;seen<4;++seen) for (unsigned control=0;control<64;++control) {
  Device d; d.m_wtcsr=0x38|(ovf<<7); d.m_rstcsr=0x60|(wovf<<7); d.m_wdt_read=seen;
  const unsigned payload=0x18|(control&7)|((control&0x38)<<2);
  const bool remains=ovf && (!(seen&1) || (payload&0x80));
  const unsigned expected=(payload&0x7f)|(remains?0x80:0);
  Device replay=d; replay.rebind();
  d.wtcnt_w(0,0xa500|payload,0xffff); replay.wtcnt_w(0,0xa500|payload,0xffff);
  CHECK(d.m_wtcsr==expected && d.m_rstcsr==(0x60|(wovf<<7)));
  CHECK(d.m_wdt_read==(seen&(remains?3:2)));
  CHECK(d.snapshot()==replay.snapshot() && d.m_wdt_read==replay.m_wdt_read);
  ++writes; ++replays;
 }
 for (unsigned ovf=0;ovf<2;++ovf) for (unsigned wovf=0;wovf<2;++wovf)
 for (unsigned seen=0;seen<4;++seen)
 for (unsigned word : {0xa500U,0xa580U,0x5a1fU,0x5a3fU,0x5a5fU,0x5a7fU,0xa600U}) {
  Device d; d.m_wtcsr=0x38|(ovf<<7); d.m_rstcsr=0x60|(wovf<<7); d.m_wdt_read=seen;
  const bool clears=word==0xa500 && (seen&2);
  const unsigned level=wovf&&!clears?0x80:0;
  const unsigned control=(word>>8)==0x5a?(word&0x60):0x60;
  Device replay=d; replay.rebind();
  d.rstcsr_w(0,word,0xffff); replay.rstcsr_w(0,word,0xffff);
  CHECK(d.m_rstcsr==(level|control) && d.m_wtcsr==(0x38|(ovf<<7)));
  CHECK(d.m_wdt_read==(seen&(clears?1:3)));
  CHECK(d.snapshot()==replay.snapshot() && d.m_wdt_read==replay.m_wdt_read);
  ++writes; ++replays;
 }
 for (unsigned ovf=0;ovf<2;++ovf) for (unsigned wovf=0;wovf<2;++wovf)
 for (unsigned seen=0;seen<4;++seen) for (unsigned inspect=0;inspect<2;++inspect)
 for (unsigned mask : {0U,0xff00U,0x00ffU,0xffffU}) for (unsigned which=0;which<2;++which) {
  Device d; d.m_wtcsr=0x38|(ovf<<7); d.m_rstcsr=0x60|(wovf<<7); d.m_wdt_read=seen; d.inspect=inspect;
  unsigned expected=seen;
  if (which) {
   CHECK(d.rstcsr_r(0,mask)==(0x7f|(wovf<<7)));
   if (!inspect && (mask&0xff)) expected=(seen&1)|(wovf<<1);
  } else {
   CHECK(d.wtcnt_r(0,mask)==((0x38|(ovf<<7))<<8|0x56));
   if (!inspect && (mask&0xff00)) expected=(seen&2)|ovf;
  }
  CHECK(d.m_wdt_read==expected); ++reads;
 }
 // Actual interval-overflow callback, byte-lane isolation, debugger peeks,
 // acknowledgement consumption and protection of the next overflow.
 Device it; it.m_wtcsr=0x38; it.m_rstcsr=0; it.sh2_wdtimer_callback(0);
 CHECK(it.m_wtcsr&0x80); it.wtcnt_r(0,0xff); it.wtcnt_w(0,0xa538,0xffff);
 CHECK((it.m_wtcsr&0x80) && it.m_wdt_read==0);
 it.inspect=true; it.wtcnt_r(0,0xff00); it.inspect=false; it.wtcnt_w(0,0xa538,0xffff);
 CHECK(it.m_wtcsr&0x80); it.wtcnt_r(0,0xff00); it.wtcnt_w(0,0xa538,0xffff);
 CHECK(!(it.m_wtcsr&0x80) && !(it.m_wdt_read&1));
 it.sh2_wdtimer_callback(0); it.wtcnt_w(0,0xa538,0xffff); CHECK(it.m_wtcsr&0x80);
 // WOVF is independent: unrelated high-lane or WTCSR reads cannot arm it.
 Device wd; wd.m_wtcsr=0x78; wd.m_rstcsr=0; wd.sh2_wdtimer_callback(0);
 CHECK(wd.m_rstcsr&0x80); wd.rstcsr_r(0,0xff00); wd.wtcnt_r(0,0xff00);
 wd.rstcsr_w(0,0xa500,0xffff); CHECK(wd.m_rstcsr&0x80);
 wd.inspect=true; wd.rstcsr_r(0,0xff); wd.inspect=false; wd.rstcsr_w(0,0xa500,0xffff);
 CHECK(wd.m_rstcsr&0x80); wd.rstcsr_r(0,0xff); wd.rstcsr_w(0,0x5a1f,0xffff);
 CHECK((wd.m_rstcsr&0x80) && (wd.m_wdt_read&2));
 wd.rstcsr_w(0,0xa500,0xffff); CHECK(!(wd.m_rstcsr&0x80) && !(wd.m_wdt_read&2));
 wd.sh2_wdtimer_callback(0); wd.rstcsr_w(0,0xa500,0xffff); CHECK(wd.m_rstcsr&0x80);
 // The word-access guard also preserves qualification on rejected writes.
 for (unsigned mask : {0U,0xff00U,0xffU}) {
  Device d; d.m_wdt_read=3; const auto before=d.snapshot();
  d.wtcnt_w(0,0xa518,mask); d.rstcsr_w(0,0xa500,mask);
  CHECK(d.snapshot()==before && d.m_wdt_read==3);
 }
 std::printf("method-level, unvalidated: %u qualified watchdog writes; %u state-copy replays; %u status-lane/debugger read cases\n",writes,replays,reads);
 std::puts("method-level, unvalidated: real overflow callbacks, independent/consumed qualifications and rejected-write preservation exercised; native watchdog reset delivery not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-wdt-flags-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
assert 'save_item(NAME(m_wdt_read));' in source and 'm_wdt_read(0)' in source
reset = re.search(r'^void sh7604_device::device_reset\(\)\n\{.*?^\}',source,re.M|re.S)[0]
assert 'm_wdt_read = 0;' in reset
print('method-level, unvalidated: watchdog read-history constructor/reset/save registration present; save layout changed')

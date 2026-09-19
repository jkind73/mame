#!/usr/bin/env python3
"""Extracted SSR register checks; method-level, unvalidated, not MAME execution."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

head = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define BIT(v,n) (((v) >> (n)) & 1)
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
struct Device {
 static constexpr uint8_t SSR_TDRE=0x80, SSR_TEND=4, SSR_MPB=2;
 uint8_t m_scr=0, m_smr=0, m_ssr=0x84, m_sci_ssr_read=0, m_tsr=0, m_tdr=0;
 bool m_sci_tx_active=false, inspect=false;
 int starts=0, irq_recalcs=0;
 Device &machine() { return *this; }
 bool side_effects_disabled() const { return inspect; }
 void sci_transmit_start() { ++starts; m_sci_tx_active=true; }
 void sh2_recalc_irq() { ++irq_recalcs; }
'''
tail = r'''
};
int main() {
 // The oracle applies each documented bit's rule separately. Keep TX busy
 // here to isolate the register operation from the asynchronous TSR load.
 unsigned cases=0;
 for (unsigned te=0; te<2; ++te)
 for (unsigned old=0; old<256; ++old)
 for (unsigned observed=0; observed<256; ++observed)
 for (unsigned data=0; data<256; ++data) {
  Device d; d.m_scr=te<<5; d.m_ssr=old; d.m_sci_ssr_read=observed;
  d.m_sci_tx_active=true;
  unsigned expect=old;
  for (unsigned bit=3; bit<=7; ++bit)
   if ((bit!=7 || te) && BIT(observed,bit) && !BIT(data,bit)) expect &= ~(1U<<bit);
  if (te && BIT(old,7) && BIT(observed,7) && !BIT(data,7)) expect &= ~4U;
  expect=(expect & ~1U) | (data & 1);
  d.ssr_w(data);
  CHECK(d.m_ssr==expect);
  unsigned consumed=expect;
  // MPBT does not arm any acknowledge; keeping it in the read snapshot is harmless.
  CHECK(d.m_sci_ssr_read==(observed & consumed));
  CHECK(d.starts==0 && d.irq_recalcs==1);
  ++cases;
 }
 Device d; d.m_scr=0x20; d.m_tdr=0xa5;
 d.ssr_w(0x7f); CHECK(d.starts==0 && d.m_ssr==0x85); // unread TDRE
 d.inspect=true; CHECK(d.ssr_r()==0x85); d.ssr_w(0x7e);
 CHECK(d.starts==0 && d.m_ssr==0x84 && d.m_sci_ssr_read==0);
 d.inspect=false; CHECK(d.ssr_r()==0x84); d.ssr_w(0x7e);
 CHECK(d.starts==1 && d.m_tsr==0xa5 && d.m_ssr==0x80);
 // TSR loading re-raises TDRE, but its previous read has been consumed.
 d.ssr_w(0x7e); CHECK(d.m_ssr==0x80);
 CHECK(d.ssr_r()==0x80); d.ssr_w(0x7e); CHECK(d.m_ssr==0);
 // A new receive flag raised after reading zero cannot be acknowledged yet.
 Device rx; rx.m_ssr=0; rx.ssr_r(); rx.m_ssr=0x40; rx.ssr_w(0);
 CHECK(rx.m_ssr==0x40); rx.ssr_r(); rx.ssr_w(0); CHECK(rx.m_ssr==0);
 std::printf("method-level, unvalidated: %u SSR transitions; read/inspect/re-arm cases exercised\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='impl-ssr-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + extract('ssr_r', 'uint8_t') + extract('ssr_w', 'void') + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
# New device state must be reset and registered alongside the implementation.
assert 'save_item(NAME(m_sci_ssr_read));' in source
assert 'm_sci_ssr_read = 0;' in source
print('method-level, unvalidated: SSR read-latch reset/save registration present')

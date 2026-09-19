#!/usr/bin/env python3
"""SCI external synchronous TX/full duplex; method-level, unvalidated.

Reuses mock declarations only from the synchronous RX check. Output is
compared to a separate LSB-first bit stream; no MAME scheduler, real IRQ
arbiter or save manager is run.
"""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'src/devices/cpu/sh/sh7604.cpp').read_text()
mock_path = Path(__file__).with_name('check_sh7604_sync_rx.py')
head = next(ast.literal_eval(n.value) for n in ast.parse(mock_path.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'head' for t in n.targets))
head = '#include <vector>\n#include <initializer_list>\n' + head
head = head.replace('void sci_transmit_start() { std::abort(); }', '')
head = head.replace('void m_write_txd(int) {}', 'int txd=1; std::vector<int> wire; void m_write_txd(int bit) { txd=bit; wire.push_back(bit); }')

def extract(name, result):
    match = re.search(r'^' + result + r' sh7604_device::' + name + r'\([^)]*\)\n\{.*?^\}', source, re.M | re.S)
    assert match, name
    return match[0].replace('sh7604_device::', '')

functions = '\n'.join(extract(n, t) for n, t in (
    ('sck_w', 'void'), ('sci_sync_edge', 'void'), ('scr_w', 'void'), ('ssr_r', 'uint8_t'), ('ssr_w', 'void'),
    ('tdr_w', 'void'), ('sci_transmit_start', 'void'), ('sci_rx_complete', 'void')))
tail = r'''
 void queue(uint8_t data) { const auto status=ssr_r(); CHECK(status & 0x80); tdr_w(data); ssr_w(status & ~0x80); }
 void clocks(uint8_t data) { for (int i=0;i<8;++i) { line=(data>>i)&1; sck_w(0); sck_w(1); } }
 void acknowledge() { const auto status=ssr_r(); ssr_w(status & ~0x78); }
};
int main() {
 unsigned cases=0,replays=0;
 for (unsigned mode=0;mode<128;++mode) for (unsigned cke=2;cke<4;++cke)
 for (unsigned value=0;value<256;++value) {
  Device d; d.m_smr=mode|0x80; d.scr_w(0xa4|cke); d.wire.clear();
  d.queue(value); CHECK(d.m_ssr==0x80 && d.wire.empty());
  d.queue(value^0xff); CHECK(d.m_ssr==0 && d.wire.empty());
  const auto timers=d.timer.adjustments;
  for (int i=0;i<24;++i) {
   const unsigned data=i<8?value:(i<16?(value^0xff):(value^1));
   CHECK(!(d.m_ssr&4));
   d.sck_w(0); d.sck_w(0);
   CHECK(d.wire.size()==unsigned(i+1) && d.txd==int((data>>(i&7))&1));
   if (i==7) {
    CHECK(d.m_ssr==0x80 && d.m_tsr==(value^0xff));
    d.queue(value^1); // queue third byte while previous MSB remains on TxD
   } else if (i==15) CHECK(d.m_ssr==0x80 && d.m_tsr==(value^1));
   else if (i==23) CHECK(d.m_ssr==0x84 && !d.m_sci_tx_active);
   d.sck_w(1); d.sck_w(1);
   CHECK(d.wire.size()==unsigned(i+1));
  }
  d.clocks(0); // externally supplied idle clocks cannot manufacture data
  CHECK(d.wire.size()==24 && d.txd==int(((value^1)>>7)&1));
  CHECK(d.timer.adjustments==timers);
  ++cases;
 }
 for (unsigned value=0;value<256;++value) for (int edge=0;edge<16;++edge) {
  Device d; d.scr_w(0x22); d.wire.clear(); d.queue(value);
  for (int i=0;i<=edge;++i) d.sck_w(i&1);
  Device replay=d; replay.m_sci_rx_timer=&replay.timer; replay.m_sci_tx_timer=&replay.timer;
  replay.sck_w(edge&1);
  for (int i=edge+1;i<16;++i) { d.sck_w(i&1); replay.sck_w(i&1); }
  CHECK(d.wire==replay.wire && d.m_ssr==replay.m_ssr && d.m_sci_tx_bit==replay.m_sci_tx_bit);
  CHECK(d.wire.size()==8 && d.txd==int(value>>7)); ++replays;
 }
 // Independent simultaneous input/output, queued third byte stopped by ORER.
 Device duplex; duplex.scr_w(0xf6); duplex.wire.clear(); duplex.queue(0x12); duplex.queue(0x34);
 duplex.clocks(0x56); CHECK(duplex.m_rdr==0x56 && duplex.m_ssr==0xc0);
 duplex.queue(0x78); duplex.clocks(0x9a);
 CHECK(duplex.m_rdr==0x56 && duplex.m_ssr==0xe0 && duplex.m_sci_tx_active);
 const auto count=duplex.wire.size(); duplex.clocks(0xbc);
 CHECK(duplex.wire.size()==count && duplex.m_rdr==0x56);
 duplex.acknowledge(); duplex.clocks(0xde);
 CHECK(duplex.m_rdr==0xde && duplex.m_ssr==0xc4 && duplex.wire.size()==24);
 for (int i=0;i<24;++i) CHECK(duplex.wire[i]==((i<8?0x12:(i<16?0x34:0x78))>>(i&7)&1));
 // Receive errors inherited before TX starts keep TDR pending until cleared.
 for (unsigned error=8;error<=32;error<<=1) {
  Device d; d.scr_w(0x22); d.wire.clear(); d.m_ssr|=error; d.queue(0x69);
  CHECK(!d.m_sci_tx_active && !(d.m_ssr&0x80)); d.clocks(0);
  CHECK(d.wire.empty()); d.acknowledge(); CHECK(d.m_sci_tx_active && (d.m_ssr&0x80));
  d.clocks(0); CHECK(d.wire.size()==8 && d.m_ssr==0x84);
 }
 // A late TDR load after MSB output does not change TxD before next falling edge.
 Device late; late.scr_w(0x22); late.wire.clear(); late.queue(0x80); late.clocks(0);
 late.queue(0); CHECK(late.txd==1 && late.wire.size()==8);
 late.sck_w(1); CHECK(late.wire.size()==8); late.sck_w(0); CHECK(late.txd==0 && late.wire.size()==9);
 // TE cancellation drives mark and prevents queued data from restarting.
 Device abort; abort.scr_w(0x22); abort.wire.clear(); abort.queue(0x55); abort.queue(0xaa);
 abort.sck_w(0); abort.sck_w(1); abort.scr_w(2);
 CHECK(abort.txd==1 && abort.m_ssr==0x84 && !abort.m_sci_tx_active);
 const auto aborted=abort.wire.size(); abort.scr_w(0x22); abort.clocks(0);
 CHECK(abort.wire.size()==aborted);
 std::printf("method-level, unvalidated: %u synchronous three-frame TX cases; %u half-edge state-copy replays\n",cases,replays);
 std::puts("method-level, unvalidated: full duplex, MSB hold/reload, error recovery and TE cancellation exercised");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-sci-sync-tx-') as directory:
    cpp = Path(directory) / 'check.cpp'
    exe = Path(directory) / 'check'
    cpp.write_text(head + functions + tail)
    subprocess.run(['g++', '-std=c++20', '-O2', '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

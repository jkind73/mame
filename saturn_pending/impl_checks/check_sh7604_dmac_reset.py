#!/usr/bin/env python3
"""DMAC reset controls/deadline cancellation; method-level, unvalidated.

Real reset, control handlers, start/check, transfer and timer callback.
Memory, scheduler, CPU suspension, peripheral resets and IRQ refresh are
mocks; existing two-cycle scheduling is a regression control, not an oracle.
"""
import ast
from pathlib import Path
import re
import subprocess
import tempfile

helper=Path(__file__).with_name('check_sh7604_wdt_reset.py')
preamble=[]
for node in ast.parse(helper.read_text()).body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tail' for t in node.targets):
        break
    preamble.append(node)
namespace={'__file__':str(helper)}
exec(compile(ast.Module(body=preamble,type_ignores=[]),str(helper),'exec'),namespace)
head='#define LOG(...) ((void)0)\n#define ACCESSING_BITS_0_7 (mem_mask & 0xff)\n#define fatalerror(...) std::abort()\n'+namespace['head']
head=head.replace('struct Timer {','struct Timer {\n void adjust(attotime t,int) { adjust(t); }')
head=head.replace('struct Device : sh2_device {',r'''
static constexpr int SUSPEND_REASON_HALT=1;
struct DMAProgram {
 unsigned reads=0,writes=0;
 uint8_t read_byte(uint32_t) { ++reads; return 0xa5; }
 uint16_t read_word(uint32_t) { ++reads; return 0xa55a; }
 uint32_t read_dword(uint32_t) { ++reads; return 0xa55a6996; }
 void write_byte(uint32_t,uint32_t) { ++writes; }
 void write_word(uint32_t,uint32_t) { ++writes; }
 void write_dword(uint32_t,uint32_t) { ++writes; }
};
struct DMACallback {
 bool isnull() const { return true; }
 uint32_t operator()(uint32_t,uint32_t,uint32_t value,int) { return value; }
};
struct Device : sh2_device {
 DMAProgram memory; DMAProgram *m_program=&memory;
 DMACallback m_dma_fifo_data_available_cb,m_dma_kludge_cb;
 uint32_t m_am=0xc7ffffff;
 unsigned suspends=0,resumes=0,dma_callbacks=0;
 void suspend(int,int) { ++suspends; }
 void resume(int) { ++resumes; }
''')
functions=namespace['functions']
extract=namespace['extract']
for name,result in [('dmaor_r','uint32_t'),('dmaor_w','void'),('sh2_dmac_check','void'),('sh2_do_dma','void')]:
    functions+='\n'+extract(name,result)
for name,result in [('chcr_r','uint32_t'),('chcr_w','void')]:
    functions+='\ntemplate <int Channel>\n'+extract(name,result)
match=re.search(r'^TIMER_CALLBACK_MEMBER\(sh7604_device::sh2_dma_current_active_callback\)\n\{.*?^\}',namespace['source'],re.M|re.S)
assert match
functions+='\nvoid sh2_dma_current_active_callback(int param)\n'+match[0].split('\n',1)[1]
tail=r'''
 void rebind() {
  m_timer=&timer; m_wdtimer=&wdtimer; m_program=&memory;
  for (unsigned ch=0;ch<2;++ch) m_dma_current_active_timer[ch]=&dma_timer[ch];
 }
 void advance_dma(ticks end) {
  unsigned events=0;
  while (true) {
   const unsigned ch=dma_timer[1].due<dma_timer[0].due?1:0;
   if (dma_timer[ch].due>end) break;
   CHECK(++events<100); now=dma_timer[ch].due;
   dma_timer[ch].due=attotime::never.value; ++dma_callbacks;
   sh2_dma_current_active_callback(ch);
  }
  now=end;
 }
 void controls_clear() { CHECK(dmaor_r()==0 && chcr_r<0>()==0 && chcr_r<1>()==0); }
 void start(unsigned ch,unsigned size) {
  m_dmac[ch].sar=0x1000; m_dmac[ch].dar=0x2000; m_dmac[ch].tcr=size==3?4:1;
  // AR=1, dual-address, increment both, IE/DE=1. No endpoint or native
  // request-acceptance behavior is inferred from these memory-only controls.
  const uint32_t control=0x5205|(size<<10);
  dmaor_w(0,1,0xffffffff);
  if (ch) chcr_w<1>(0,control,0xffffffff); else chcr_w<0>(0,control,0xffffffff);
  CHECK(m_dma_timer_active[ch]==1 && dma_timer[ch].due==now+2);
 }
 void check_fresh(unsigned ch,unsigned size) {
  const unsigned old_reads=memory.reads,old_writes=memory.writes,old_callbacks=dma_callbacks;
  start(ch,size); advance_dma(now+4);
  const unsigned transfers=size==3?4:1;
  CHECK(memory.reads==old_reads+transfers && memory.writes==old_writes+transfers);
  CHECK(dma_callbacks==old_callbacks+2 && (m_dmac[ch].chcr&2) && m_dma_irq[ch]==1);
 }
};
int main() {
 unsigned resets=0,replays=0,quiet=0,restarts=0,controls=0;
 for (unsigned ch=0;ch<2;++ch) for (unsigned size=0;size<4;++size) {
  now=100; Device normal; normal.check_fresh(ch,size); ++controls;
 }
 // Both channels, sizes and three active phases: queued transfer, queued
 // completion, and seeded endpoint-stall state (endpoint model absent).
 for (unsigned mask=1;mask<4;++mask) for (unsigned size=0;size<4;++size)
 for (unsigned phase=0;phase<3;++phase) for (unsigned elapsed=0;elapsed<2;++elapsed) {
  now=100; Device d;
  for (unsigned ch=0;ch<2;++ch) if (mask&(1<<ch)) d.start(ch,size);
  if (phase==1) d.advance_dma(now+2); // transfer done, TE callback still pending
  if (phase==2) for (unsigned ch=0;ch<2;++ch) if (mask&(1<<ch)) {
   d.m_dma_timer_active[ch]=2; d.dma_timer[ch].adjust(attotime::never);
  }
  d.advance_dma(now+elapsed);
  Device replay=d; replay.rebind(); const ticks reset_time=now;
  auto reset_and_restart=[&](Device &x) {
   const auto before_reads=x.memory.reads,before_writes=x.memory.writes,before_callbacks=x.dma_callbacks;
   x.device_reset(); x.controls_clear();
   x.advance_dma(reset_time+20); x.controls_clear();
   CHECK(x.memory.reads==before_reads && x.memory.writes==before_writes && x.dma_callbacks==before_callbacks);
   for (unsigned ch=0;ch<2;++ch) {
    CHECK(x.m_dma_irq[ch]==0 && x.m_dma_timer_active[ch]==0 && x.m_active_dma_count[ch]==0);
    CHECK(x.dma_timer[ch].due==attotime::never.value);
   }
   ++quiet;
   x.check_fresh(0,size); ++restarts;
  };
  reset_and_restart(d); now=reset_time; reset_and_restart(replay);
  CHECK(d.memory.reads==replay.memory.reads && d.memory.writes==replay.memory.writes);
  CHECK(d.dma_callbacks==replay.dma_callbacks && d.dmaor_r()==replay.dmaor_r());
  ++resets; ++replays;
 }
 // Status flags are seeded events, not claims that software can set TE,
 // NMIF or AE. Check every DMAOR status/control image on otherwise idle DMA.
 unsigned flag_images=0;
 for (unsigned flags=0;flags<16;++flags) {
  now=100; Device d; d.m_dmaor=flags; d.m_dmac[0].chcr=2; d.m_dmac[1].chcr=6;
  d.device_reset(); d.controls_clear(); ++flag_images;
 }
 std::printf("method-level, unvalidated: %u queued/completion/stalled reset cases; %u quiet post-reset intervals; %u fresh-transfer controls; %u state-copy replays; %u no-reset completion controls; %u seeded flag reset images\n",resets,quiet,restarts,replays,controls,flag_images);
 std::puts("method-level, unvalidated: actual DMA callbacks exercised with mocked memory/scheduler; no native bus-cycle reset collision, HALT, IRQ acknowledgment, timing, standby or save/load qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-dmac-reset-') as directory:
    cpp=Path(directory)/'check.cpp'; exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
assert 'save_item(NAME(m_dmaor));' in namespace['source']
assert 'save_item(STRUCT_MEMBER(m_dmac, chcr));' in namespace['source']
print('method-level, unvalidated: existing DMA control save registrations retained; no new state fields')

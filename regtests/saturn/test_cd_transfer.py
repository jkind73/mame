#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute production CD long-port/EndTransfer/cleanup with recording IRQs.

These are sanitizer-backed port tests, not a CD drive or FIFO timing model.
"""
from pathlib import Path
import os, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header = (ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text, signature):
    start = text.index(signature); end = text.index('{', start)+1; depth = 1
    while depth:
        depth += (text[end]=='{')-(text[end]=='}'); end += 1
    return text[start:end]
functions = '\n'.join(extract(source, s) for s in (
    'uint16_t saturn_cd_hle_device::hirq_r()', 'void saturn_cd_hle_device::hirq_w(',
    'void saturn_cd_hle_device::trace_host_read(', 'void saturn_cd_hle_device::trace_boot_state(',
    'uint16_t saturn_cd_hle_device::dr1_r()', 'uint16_t saturn_cd_hle_device::dr2_r()',
    'uint16_t saturn_cd_hle_device::dr3_r()', 'uint16_t saturn_cd_hle_device::dr4_r()',
    'saturn_cd_hle_device::blockT *\nsaturn_cd_hle_device::xfer_block(',
    'void saturn_cd_hle_device::xfer_advance(',
    'inline u32 saturn_cd_hle_device::dataxfer_long_r()',
    'inline void saturn_cd_hle_device::dataxfer_long_w(',
    'inline u16 saturn_cd_hle_device::dataxfer_sector_word_r()',
    'inline void saturn_cd_hle_device::dataxfer_sector_word_w(',
    'u32 saturn_cd_hle_device::datatrns_r(',
    'void saturn_cd_hle_device::datatrns_w(',
    'inline u16 saturn_cd_hle_device::dataxfer_word_r()',
    'void saturn_cd_hle_device::finish_get_delete()',
    'void saturn_cd_hle_device::cmd_end_data_transfer()',
    'void saturn_cd_hle_device::cd_free_block(',
    'void saturn_cd_hle_device::cd_defragblocks('))
if os.environ.get('MUTATE_CD_HIRQ') == '1':
    functions = functions.replace('rv = hirqreg;', 'rv = hirqreg & ~DCHG;', 1)
types = '\n'.join(extract(header, s)+';' for s in ('struct blockT', 'struct partitionT', 'struct direntryT', 'enum transT', 'enum trans32T'))
harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <cstdio>
#include <string>
#include <vector>
using u8=uint8_t; using u16=uint16_t; using u32=uint32_t; using offs_t=uint32_t;
u16 get_u16be(const u8 *p){return u16(u16(p[0])<<8|p[1]);}
void put_u16be(u8 *p,u16 v){p[0]=v>>8;p[1]=v;}
constexpr int DCHG=0x20, CSCT=4;
constexpr int MAX_BLOCKS=200, EHST=0x80, CMOK=1, BFUL=8, CD_STAT_TRANS=0x4000;
constexpr int STATE_GENPC=0, CD_STAT_PERI=0x2000;
struct cpu_device { uint32_t state_int(int){return 0x06001234;} };
namespace cdrom_file { constexpr int MAX_SECTOR_DATA=2352; }
#define LOG(...) ((void)0)
#define LOGWARN(...) ((void)0)
#define LOGXFER(...) ((void)0)
u32 get_u32be(const u8 *p){return u32(p[0])<<24|u32(p[1])<<16|u32(p[2])<<8|p[3];}
void put_u32be(u8 *p,u32 v){for(int i=3;i>=0;--i){p[i]=v;v>>=8;}}
struct saturn_cd_hle_device {
// TYPES
 blockT blocks[MAX_BLOCKS]{};
 partitionT partition{}, *transpart=&partition;
 transT xfertype=XFERTYPE_INVALID;
 trans32T xfertype32=XFERTYPE32_INVALID;
 u32 xfersect=0,xfersectpos=0,xfersectnum=0,xferoffs=0,xferdnum=0;
 uint16_t cd_stat=CD_STAT_TRANS,cr1=0,cr2=0,cr3=0,cr4=0,hirqreg=0;
 int freeblocks=MAX_BLOCKS,buffull=0,sectorstore=1;
 bool debug=false; unsigned irqs=0;
 struct opts {bool enabled=false;bool verbose(){return enabled;}} opts_;
 struct clock {int64_t second=0;int64_t seconds(){return second;}const char *as_string(){return "test-time";}} clock_;
 cpu_device cpu_; bool present=true;
 auto &options(){return opts_;}auto &time(){return clock_;}auto &root_device(){return *this;}
 template<class T>T *subdevice(const char*){return present?&cpu_:nullptr;}
 std::vector<std::string> logs;
 template<class... T>void logerror(const char *fmt,T... args){char text[2048];std::snprintf(text,sizeof(text),fmt,args...);logs.emplace_back(text);}
 int64_t m_trace_second=-1;uint64_t m_trace_reads[5]{};uint16_t m_trace_last_read[5]{};
 uint16_t cd_next_stat=0,hirqmask=0;unsigned cmd_pending=15,cd_curfad=0xab,fadstoplay=18,playtype=1;
 void trace_host_read(unsigned,uint16_t);void trace_boot_state(const char*,bool=false);
 uint16_t hirq_r();void hirq_w(uint16_t);
 uint16_t dr1_r();uint16_t dr2_r();uint16_t dr3_r();uint16_t dr4_r();
 auto &machine(){return *this;} bool side_effects_disabled(){return debug;}
 void update_hirq(){++irqs;}
 u32 dataxfer_long_r();void dataxfer_long_w(u32);
 u16 dataxfer_sector_word_r();void dataxfer_sector_word_w(u16);
 u32 datatrns_r(offs_t,uint32_t);void datatrns_w(offs_t,uint32_t,uint32_t);
 u16 dataxfer_word_r();
 blockT *xfer_block(unsigned width);void xfer_advance(unsigned width);
 u8 tocbuf[102*4]{};u8 subqbuf[5*2]{};u8 subrwbuf[12*2]{};u8 finfbuf[256]{};
 u32 xfercount=0;std::vector<direntryT> curdir;
 void finish_get_delete();void cmd_end_data_transfer();
 void cd_free_block(blockT *);void cd_defragblocks(partitionT *);
 void setup(){
  for(unsigned i=0;i<4;++i){blocks[i].size=8+4*i;partition.blocks[i]=&blocks[i];partition.bnum[i]=i;partition.size+=blocks[i].size;}
  partition.numblks=4;freeblocks-=4;xfersectpos=1;xfersectnum=2;
 }
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 // ST-136-R2 printed p.50: software detects tray changes through DCHG.
 // Exercise the actual read/write handlers; update_hirq is a recording stub,
 // so this checks register semantics, not interrupt timing or drive mechanics.
 {
  auto t=std::make_unique<saturn_cd_hle_device>();
  for(unsigned bits=0;bits<65536;++bits)for(bool full:{false,true})for(bool sector:{false,true}){
   t->hirqreg=bits;t->buffull=full;t->sectorstore=sector;
   unsigned want=(bits&~unsigned(BFUL|CSCT))|(full?BFUL:0)|(sector?CSCT:0);
   t->debug=true;unsigned irq_before=t->irqs;
   assert(t->hirq_r()==want);assert(t->hirq_r()==want);
   assert(t->hirqreg==bits && t->irqs==irq_before);
   t->debug=false;
   assert(t->hirq_r()==want);assert(t->hirq_r()==want);
   t->hirq_w(uint16_t(~DCHG));assert(t->hirqreg==(want&~DCHG));
   t->hirq_w(0xffff);assert(t->hirqreg==(want&~DCHG));
   t->hirq_w(0);assert(!t->hirqreg);
  }
  std::cout<<"CD HIRQ: 262144 status-overlay/read/ack cases passed\n";
 }

 for(auto mode : {saturn_cd_hle_device::XFERTYPE32_INVALID,saturn_cd_hle_device::XFERTYPE32_PUTSECTOR,saturn_cd_hle_device::XFERTYPE32_MOVESECTOR}){
  auto s=std::make_unique<saturn_cd_hle_device>();s->xfertype32=mode;
  assert(s->dataxfer_long_r()==0xffffffff);assert(s->xferdnum==0&&s->irqs==0);++cases;
 }
 for(bool write : {false,true})for(unsigned pos : {0u,199u,200u,0xffffffffu})
 for(int size : {-1,0,1,3,4,8,2352,2353})for(unsigned off : {0u,1u,4u,2351u,0xffffffffu}){
  auto s=std::make_unique<saturn_cd_hle_device>();s->xfertype32=write?s->XFERTYPE32_PUTSECTOR:s->XFERTYPE32_GETSECTOR;
  s->xfersectpos=pos;s->xfersectnum=1;s->xferoffs=off;
  s->blocks[0].size=size;if(pos<200)s->partition.blocks[pos]=&s->blocks[0];
  if(write)s->dataxfer_long_w(0x12345678);else s->dataxfer_long_r();
  bool valid=pos<200&&size>=4&&size<=2352&&off<=unsigned(size-4);
  assert(s->xferdnum==(valid?4u:0u));++cases;
 }
 for(bool write : {false,true}){
  auto s=std::make_unique<saturn_cd_hle_device>();s->transpart=nullptr;s->xfersectnum=1;
  s->xfertype32=write?s->XFERTYPE32_PUTSECTOR:s->XFERTYPE32_GETSECTOR;
  if(write)s->dataxfer_long_w(0);else assert(s->dataxfer_long_r()==0xffffffff);
  assert(!s->xferdnum);++cases;
 }
 for(unsigned consumed : {0u,4u,12u,28u})for(bool excess : {false,true}){
  auto s=std::make_unique<saturn_cd_hle_device>();s->setup();s->xfertype32=s->XFERTYPE32_GETDELETESECTOR;s->xferdnum=consumed;
  if(excess){s->xfersect=2;assert(s->dataxfer_long_r()==0xffffffff);}
  s->cmd_end_data_transfer();
  assert(s->hirqreg&EHST);
  assert(s->partition.size==28&&s->partition.numblks==2&&s->freeblocks==198);
  assert(s->partition.blocks[0]==&s->blocks[0]&&s->partition.blocks[1]==&s->blocks[3]);
  assert(s->partition.bnum[0]==0&&s->partition.bnum[1]==3);
  assert(s->xfertype32==s->XFERTYPE32_INVALID&&s->xfertype==s->XFERTYPE_INVALID);
  assert(s->dataxfer_long_r()==0xffffffff);s->cmd_end_data_transfer();
  assert(s->freeblocks==198&&s->partition.size==28);++cases;
 }
 for(auto mode : {saturn_cd_hle_device::XFERTYPE32_GETSECTOR,saturn_cd_hle_device::XFERTYPE32_PUTSECTOR}){
  // ST-162-062094 printed p.81 (CDC_DataEnd): an interrupted read reports the
  // CD block's word number (the two buffered blocks hold 12+16 bytes = 14
  // words), a write reports the host's 4 bytes = 2 words.
  auto s=std::make_unique<saturn_cd_hle_device>();s->setup();s->xfertype32=mode;s->xferdnum=4;
  s->cmd_end_data_transfer();assert(s->cr2==(mode==saturn_cd_hle_device::XFERTYPE32_GETSECTOR?14:2)&&!(s->cd_stat&CD_STAT_TRANS)&&(s->hirqreg&EHST));
  assert(s->xfertype32==s->XFERTYPE32_INVALID);s->dataxfer_long_w(0xaabbccdd);
  assert(s->dataxfer_long_r()==0xffffffff&&s->xferdnum==0&&s->blocks[1].data[0]==0);++cases;
 }
 auto s=std::make_unique<saturn_cd_hle_device>();s->debug=true;s->xfertype32=s->XFERTYPE32_GETSECTOR;s->setup();
 assert(s->dataxfer_long_r()==0xffffffff&&s->xferoffs==0&&s->xferdnum==0);++cases;
 // Diagnostic reads are opt-in and ignore debugger accesses. Periodic
 // status is bounded, forced command/completion events don't suppress it.
 {
  auto t=std::make_unique<saturn_cd_hle_device>();t->cr1=1;t->cr2=2;t->cr3=3;t->cr4=4;
  t->trace_boot_state("periodic");t->trace_host_read(0,0x201);
  assert(t->logs.empty()&&t->m_trace_reads[0]==0&&t->m_trace_second==-1);
  t->opts_.enabled=true;t->debug=true;t->trace_host_read(0,0x201);
  assert(t->dr4_r()==4&&t->cmd_pending==15&&t->m_trace_reads[4]==0);
  t->debug=false;t->trace_host_read(0,0x201);
  assert(t->dr1_r()==1&&t->dr2_r()==2&&t->dr3_r()==3&&t->dr4_r()==4);
  assert(!t->cmd_pending&&(t->cd_stat&CD_STAT_PERI));
  for(unsigned i=0;i<5;++i)assert(t->m_trace_reads[i]==1&&t->m_trace_last_read[i]==(i?i:0x201));
  const auto status=t->cd_stat;t->trace_boot_state("command",true);assert(t->logs.size()==2&&t->m_trace_second==-1);
  assert(t->logs[0].find("mainpc=06001234")!=std::string::npos);
  t->trace_boot_state("periodic");t->trace_boot_state("periodic");assert(t->logs.size()==4);
  t->clock_.second=1;t->trace_boot_state("periodic");assert(t->logs.size()==6);
  t->present=false;t->trace_boot_state("file-complete",true);assert(t->logs.size()==8&&t->logs[6].find("mainpc=00000000")!=std::string::npos);
  t->trace_boot_state("periodic");assert(t->logs.size()==8&&t->cd_stat==status&&t->fadstoplay==18&&t->cd_curfad==0xab);
  std::cout<<"CD boot trace: opt-in, debugger, register, rate-limit and observational checks passed\n";
 }
 // ST-162-062094 printed p.27 (Table 3.1) makes the data port one 16 bit word
 // wide, so a 16 bit access moves two bytes and a 32 bit access moves four -
 // two word transfers.  Compare the two widths against each other on the same
 // data and check the cursor, the count and the sector advance.
 {
  auto s=std::make_unique<saturn_cd_hle_device>();
  u8 pattern[2*8];for(unsigned i=0;i<sizeof(pattern);++i)pattern[i]=u8(0x40+i);
  s->blocks[0].size=8;s->blocks[1].size=8;
  std::copy(pattern,pattern+8,s->blocks[0].data);
  std::copy(pattern+8,pattern+16,s->blocks[1].data);
  s->partition.blocks[0]=&s->blocks[0];s->partition.blocks[1]=&s->blocks[1];
  s->partition.numblks=2;s->partition.size=16;s->xfersectpos=0;s->xfersectnum=2;
  s->transpart=&s->partition;

  s->xfertype32=s->XFERTYPE32_GETSECTOR;
  // a longword read is two word reads: 0x40414243 then 0x44454647
  assert(s->datatrns_r(0,0xffffffffu)==0x40414243u&&s->xferdnum==4&&s->xferoffs==4&&s->xfersect==0);
  // the low half of the window hands over the next word
  assert(s->datatrns_r(0,0x0000ffffu)==0x4445u&&s->xferdnum==6&&s->xferoffs==6&&s->xfersect==0);
  assert(s->datatrns_r(0,0x0000ffffu)==0x4647u&&s->xferdnum==8&&s->xferoffs==0&&s->xfersect==1);
  // ... and so does the high half: the address does not select a byte
  assert(s->datatrns_r(0,0xffff0000u)==0x48490000u&&s->xferdnum==10&&s->xfersect==1);
  assert(s->datatrns_r(0,0x0000ffffu)==0x4a4bu&&s->xferdnum==12);

  assert(s->datatrns_r(0,0x0000ffffu)==0x4c4du&&s->xferdnum==14);
  assert(s->datatrns_r(0,0x0000ffffu)==0x4e4fu&&s->xferdnum==16&&s->xfersect==2);
  // a word read past the end of the range reports the idle value and leaves
  // the cursor where it was instead of walking off the end of the partition
  for(unsigned i=0;i<4;++i)assert(s->datatrns_r(0,0x0000ffffu)==0xffffu);
  assert(s->xferdnum==16&&s->xfersect==2&&s->xferoffs==0);++cases;

  // the write direction is symmetric
  auto w=std::make_unique<saturn_cd_hle_device>();
  w->blocks[0].size=8;w->partition.blocks[0]=&w->blocks[0];w->partition.numblks=1;
  w->xfersectpos=0;w->xfersectnum=1;w->transpart=&w->partition;
  w->xfertype32=w->XFERTYPE32_PUTSECTOR;
  w->datatrns_w(0,0x1234,0x0000ffffu);
  w->datatrns_w(0,0x5678,0x0000ffffu);
  w->datatrns_w(0,0x9abc,0xffff0000u);
  w->datatrns_w(0,0xdef0,0xffff0000u);
  assert(w->xferdnum==8&&w->xferoffs==0&&w->xfersect==1);
  assert(w->blocks[0].data[0]==0x12&&w->blocks[0].data[1]==0x34);
  assert(w->blocks[0].data[2]==0x56&&w->blocks[0].data[3]==0x78);
  assert(w->blocks[0].data[4]==0x9a&&w->blocks[0].data[5]==0xbc);
  assert(w->blocks[0].data[6]==0xde&&w->blocks[0].data[7]==0xf0);
  // and a word write during a read transfer is not a transfer at all
  w->xfertype32=w->XFERTYPE32_GETSECTOR;w->xferdnum=0;w->xferoffs=0;w->xfersect=0;
  w->datatrns_w(0,0x1111,0x0000ffffu);
  assert(w->xferdnum==0&&w->blocks[0].data[0]==0x12);++cases;
  std::cout<<"CD port width: 16 bit and 32 bit accesses move two and four \
bytes over the same cursor\n";
 }
 std::cout<<"CD transfer: "<<cases<<" cases passed\n";
}
'''.replace('// TYPES',types).replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-cd-') as tmp:
    src=Path(tmp)/'test.cpp'; exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

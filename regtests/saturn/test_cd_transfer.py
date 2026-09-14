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
    'inline u32 saturn_cd_hle_device::dataxfer_long_r()',
    'inline void saturn_cd_hle_device::dataxfer_long_w(',
    'void saturn_cd_hle_device::finish_get_delete()',
    'void saturn_cd_hle_device::cmd_end_data_transfer()',
    'void saturn_cd_hle_device::cd_free_block(',
    'void saturn_cd_hle_device::cd_defragblocks('))
types = '\n'.join(extract(header, s)+';' for s in ('struct blockT', 'struct partitionT', 'enum transT', 'enum trans32T'))
harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
using u8=uint8_t; using u32=uint32_t;
constexpr int MAX_BLOCKS=200, EHST=0x80, CMOK=1, BFUL=8, CD_STAT_TRANS=0x4000;
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
 auto &machine(){return *this;} bool side_effects_disabled(){return debug;}
 void update_hirq(){++irqs;}
 u32 dataxfer_long_r();void dataxfer_long_w(u32);
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
  auto s=std::make_unique<saturn_cd_hle_device>();s->setup();s->xfertype32=mode;s->xferdnum=4;
  s->cmd_end_data_transfer();assert(s->cr2==2&&!(s->cd_stat&CD_STAT_TRANS)&&(s->hirqreg&EHST));
  assert(s->xfertype32==s->XFERTYPE32_INVALID);s->dataxfer_long_w(0xaabbccdd);
  assert(s->dataxfer_long_r()==0xffffffff&&s->xferdnum==0&&s->blocks[1].data[0]==0);++cases;
 }
 auto s=std::make_unique<saturn_cd_hle_device>();s->debug=true;s->xfertype32=s->XFERTYPE32_GETSECTOR;s->setup();
 assert(s->dataxfer_long_r()==0xffffffff&&s->xferoffs==0&&s->xferdnum==0);++cases;
 std::cout<<"CD transfer: "<<cases<<" cases passed\n";
}
'''.replace('// TYPES',types).replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-cd-') as tmp:
    src=Path(tmp)/'test.cpp'; exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

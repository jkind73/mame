#!/usr/bin/env python3
# license:BSD-3-Clause
"""ASan/UBSan checks of actual CD word/long sector FIFO transfer methods."""
from pathlib import Path
import subprocess
import tempfile
from saturn_vdp_wip_test import method

root=Path(__file__).resolve().parent.parent
source=(root/'src/mame/sega/saturn_cd_hle.cpp').read_text()
def extract(name):
    return method(source.replace('saturn_cd_hle_device::','saturn_vdp1_device::'),name).replace('saturn_vdp1_device::','saturn_cd_hle_device::')
fixture=r'''
#include <array>
#include <cassert>
#include <cstdint>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;
#define LOG(...)
#define LOGWARN(...)
#define LOGXFER(...)
struct emu_fatalerror {template<class...T> emu_fatalerror(T...) {}};
u16 get_u16be(const u8*p){return (p[0]<<8)|p[1];}
void put_u32be(u8*p,u32 v){for(int i=0;i<4;i++)p[i]=v>>(24-8*i);}
enum {XFERTYPE_INVALID,XFERTYPE_TOC,XFERTYPE_FILEINFO_1,XFERTYPE_FILEINFO_254,XFERTYPE_SUBQ,XFERTYPE_SUBRW};
enum {XFERTYPE32_INVALID,XFERTYPE32_GETSECTOR,XFERTYPE32_GETDELETESECTOR,XFERTYPE32_PUTSECTOR};
constexpr unsigned CD_STAT_TRANS=0x4000,EHST=0x80,CMOK=1,MAX_BLOCKS=200;
struct saturn_cd_hle_device {
 struct blockT {std::array<u8,2352> data{};int size=0;};
 struct partition {std::array<blockT*,200> blocks{};std::array<u8,200>bnum{};int size=0,numblks=0;};
 struct file {u32 firstfad=0,length=0;u8 interleave_gap_size=0,file_unit_size=0,flags=0;};
 std::array<file,260>curdir{};
 int xfertype=XFERTYPE_INVALID,xfertype32=XFERTYPE32_INVALID,xfercount=0;
 int xfersect=0,xfersectnum=2,xfersectpos=1,xferoffs=0,xferdnum=0;
 int freeblocks=0,sectorstore=0;
 u16 cd_stat=CD_STAT_TRANS,hirqreg=0,cr1=0,cr2=0,cr3=0,cr4=0;
 std::array<u8,408>tocbuf{};std::array<u8,12>finfbuf{};
 std::array<u8,10>subqbuf{};std::array<u8,24>subrwbuf{};
 partition part;partition*transpart=&part;
 struct machine_stub {bool disabled=false;bool side_effects_disabled()const{return disabled;}} state;
 machine_stub& machine(){return state;}
 void cd_free_block(blockT*){++freeblocks;}
 void cd_defragblocks(partition*){}
 u16 dataxfer_word_r();u32 dataxfer_long_r();void cmd_end_data_transfer();
};
// METHODS
int main(){
 saturn_cd_hle_device d;
 saturn_cd_hle_device::blockT unused,a,b;
 unused.size=2048;a.size=4;b.size=6;
 a.data[0]=1;a.data[1]=2;a.data[2]=3;a.data[3]=4;
 for(unsigned i=0;i<6;++i)b.data[i]=5+i;
 d.part.blocks[0]=&unused;d.part.blocks[1]=&a;d.part.blocks[2]=&b;
 d.part.size=10;d.part.numblks=2;d.xfertype32=XFERTYPE32_GETSECTOR;
 d.state.disabled=true;assert(d.dataxfer_word_r()==0 && d.dataxfer_long_r()==0xffffffff && d.xferdnum==0);d.state.disabled=false;
 assert(d.dataxfer_word_r()==0x0102);
 assert(d.dataxfer_long_r()==0x03040506); // cross-sector, with nonzero first block
 assert(d.dataxfer_word_r()==0x0708);
 assert(d.dataxfer_word_r()==0x090a);
 assert(d.xfersect==2 && d.xferoffs==0 && d.xferdnum==10);
 assert(d.dataxfer_word_r()==0xffff && d.xferdnum==10);
 d.cmd_end_data_transfer();assert(d.cr2==5 && d.xfertype32==XFERTYPE32_INVALID);
 d.xfertype=XFERTYPE_TOC;d.xfercount=0;d.tocbuf[0]=0x41;d.tocbuf[3]=150;
 assert(d.dataxfer_word_r()==0x4100 && d.dataxfer_word_r()==150);
 d.cmd_end_data_transfer();assert(d.cr2==2 && d.xfertype==XFERTYPE_INVALID);
}
'''
fixture=fixture.replace('// METHODS','\n'.join(extract(name) for name in ('dataxfer_word_r','dataxfer_long_r','cmd_end_data_transfer')))
with tempfile.TemporaryDirectory(prefix='saturn-cd-word-') as directory:
    out=Path(directory);(out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('CD word/long FIFO ASan/UBSan checks passed')

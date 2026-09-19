#!/usr/bin/env python3
"""Advertised file-information transfer length/end boundaries; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=r'''
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <vector>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using emu_fatalerror=std::runtime_error;
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
#define LOGCMD(...) ((void)0)
#define LOGWARN(...) ((void)0)
#define LOGXFER(...) ((void)0)
#define LOG(...) ((void)0)
constexpr unsigned CMOK=1,DRDY=2,EHST=0x80,CD_STAT_TRANS=0x4000;
u16 get_u16be(const u8 *p){return unsigned(p[0])<<8|p[1];}
void put_u32be(u8 *p,u32 v){for(int i=3;i>=0;--i){p[i]=v;v>>=8;}}
struct saturn_cd_hle_device {
// TYPES
 std::vector<direntryT>curdir;
 u8 tocbuf[408]{},subqbuf[10]{},subrwbuf[24]{},finfbuf[256]{};
 u16 cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 u8 playtype=0,cdda_repeat_count=0;
 u32 xfercount=0,xferdnum=0;
 transT xfertype=XFERTYPE_INVALID;trans32T xfertype32=XFERTYPE32_INVALID;
 unsigned irqs=0;void update_hirq(){++irqs;}
 uint8_t m_put_filter=0xff;void finish_put(){CHECK(false);}
 void finish_get_delete(){CHECK(false);}
 void cmd_get_target_file_info();void cmd_end_data_transfer();u16 dataxfer_word_r();
};
'''
types='\n'.join(extract(header,s)+';' for s in ('struct direntryT','enum transT','enum trans32T'))
functions='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cmd_get_target_file_info()', 'inline u16 saturn_cd_hle_device::dataxfer_word_r()', 'void saturn_cd_hle_device::cmd_end_data_transfer()'))
tail=r'''
using D=saturn_cd_hle_device;
void seed(D &d,unsigned count){d.curdir.resize(count);for(unsigned i=0;i<count;++i){auto &f=d.curdir[i];f.firstfad=150+i*0x10001;f.length=12345*(i+1);f.file_unit_size=i+3;f.interleave_gap_size=i+7;f.flags=i&3;}}
std::vector<u16> finish(D &d,unsigned total,unsigned consumed){
 std::vector<u16> out;for(unsigned n=consumed;n<total;++n){CHECK(d.xfertype!=D::XFERTYPE_INVALID);out.push_back(d.dataxfer_word_r());}
 CHECK(d.xfertype==D::XFERTYPE_INVALID&&d.xfercount==0&&d.xferdnum==total*2);
 for(unsigned n=0;n<3;++n)d.dataxfer_word_r();CHECK(d.xferdnum==total*2&&d.xfercount==0);
 d.cmd_end_data_transfer();CHECK(d.cr2==total&&d.xferdnum==0&&!(d.cd_stat&CD_STAT_TRANS));return out;
}
int main(){unsigned streams=0,replays=0,controls=0;
 for(unsigned entries:{0U,2U,3U,256U})for(unsigned fid:{0U,2U,17U,255U,0xfffffeU,0xffffffU}){
  D base;seed(base,entries);base.cr1=0x7300;base.cr3=fid>>16;base.cr4=fid;base.cmd_get_target_file_info();
  const unsigned words=base.cr2;CHECK(words==(fid==0xffffff?254*6:6));
  D whole=base;const auto expected=finish(whole,words,0);++streams;
  D prefix=base;
  for(unsigned cut=0;cut<=words;++cut){
   D replay=prefix;const auto rest=finish(replay,words,cut);CHECK(std::equal(rest.begin(),rest.end(),expected.begin()+cut,expected.end()));
   if(cut<words)prefix.dataxfer_word_r();++replays;
  }
 }
 for(auto type:{D::XFERTYPE_TOC,D::XFERTYPE_SUBQ,D::XFERTYPE_SUBRW}){
  D base;base.xfertype=type;const unsigned words=type==D::XFERTYPE_TOC?204:type==D::XFERTYPE_SUBQ?5:12;
  D whole=base;const auto expected=finish(whole,words,0);D prefix=base;
  for(unsigned cut=0;cut<=words;++cut){D replay=prefix;const auto rest=finish(replay,words,cut);CHECK(std::equal(rest.begin(),rest.end(),expected.begin()+cut,expected.end()));if(cut<words)prefix.dataxfer_word_r();++controls;}
 }
 std::printf("method-level, unvalidated: %u advertised file-information streams; %u every-word state-copy continuations; %u TOC/subcode boundary controls; DataEnd counts and extra-read nonconsumption\n",streams,replays,controls);
 std::puts("method-level, unvalidated: actual file command/word-read/DataEnd methods, mocked IRQ; not native save, bus, short-directory content or idle bus-value qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-length-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head.replace('// TYPES',types)+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

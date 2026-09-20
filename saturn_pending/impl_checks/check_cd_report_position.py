#!/usr/bin/env python3
"""Current/seek CD reports and native image-index lookup; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
image=(ROOT/'src/lib/util/cdrom.cpp').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iterator>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
constexpr unsigned CD_STAT_SEEK=0x400;
template<unsigned N,class T,class... B>unsigned bitswap(T value,B... bits){unsigned out=0;((out=(out<<1)|((value>>bits)&1)),...);return out;}
struct cdrom_file {
 static constexpr unsigned CD_TRACK_AUDIO=0;
 struct Track{int32_t idx[100];};struct Info{Track track[99];}cdtrack_info;
 cdrom_file(){for(unsigned t=0;t<99;++t){const unsigned gap=(t%5)*17;cdtrack_info.track[t].idx[0]=0;
  for(unsigned i=1;i<100;++i)cdtrack_info.track[t].idx[i]=gap+5*(i-1);}}
 uint32_t get_track(uint32_t lba)const{CHECK(lba<99000);return lba/1000;}
 uint32_t get_track_start(uint32_t track)const{CHECK(track<100);return track*1000;}
 uint32_t get_track_index(uint32_t)const;
};
struct saturn_cd_hle_device {
 struct Media:cdrom_file {
  bool inserted=true;unsigned queries=0,last_index=0;
  bool exists(){return inserted;}
  uint32_t get_track(uint32_t lba){++queries;return cdrom_file::get_track(lba);}
  uint32_t get_track_index(uint32_t lba){++queries;last_index=lba;return cdrom_file::get_track_index(lba);}
  unsigned get_track_type(unsigned t){return t&1?CD_TRACK_AUDIO:1;}
  unsigned get_adr_control(unsigned t){CHECK(t<99);++queries;return t&1?0x10:0x14;}
 }media;
 Media *m_cdrom_image=&media;
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0;
 uint32_t cd_curfad=150,cd_fad_seek=150;uint8_t playtype=0,cdda_repeat_count=0,cur_track=0;
 int get_track_index(uint32_t);int sega_cdrom_get_adr_control(int);void cr_standard_return(uint16_t);
};
'''
functions=extract(image,'uint32_t cdrom_file::get_track_index(uint32_t frame) const')+'\n'
functions+='\n'.join(extract(source,s) for s in ('int saturn_cd_hle_device::get_track_index(', 'int saturn_cd_hle_device::sega_cdrom_get_adr_control(', 'void saturn_cd_hle_device::cr_standard_return('))
tail=r'''
int main(){saturn_cd_hle_device d;unsigned reports=0,indices=0,empty=0;
 for(unsigned t=0;t<99;++t){const unsigned gap=(t%5)*17;
  for(unsigned offset:{0U,1U,gap?gap-1:0U,gap,gap+44,gap+45,gap+49,gap+50,gap+309,gap+310,999U}){
   const unsigned lba=t*1000+offset,index=offset<gap?0:std::min(99U,1+(offset-gap)/5);
   CHECK(d.get_track_index(lba+150)==int(index)&&d.media.last_index==lba);++indices;
   for(unsigned status:{0x100U,0x300U,0x400U,0x500U})for(unsigned old:{0U,1U,50U,98U})
   for(unsigned flags:{0U,0x2000U,0x4000U,0x8000U})for(unsigned rep:{0U,9U,14U}){
    const unsigned other=((t+17)%99)*1000+27;
    d.cd_curfad=(status==CD_STAT_SEEK?other:lba)+150;d.cd_fad_seek=(status==CD_STAT_SEEK?lba:other)+150;
    d.cur_track=old;d.cd_stat=status;d.playtype=t&1;d.cdda_repeat_count=rep;
    const auto before=std::array<unsigned,6>{d.cd_stat,d.cd_curfad,d.cd_fad_seek,d.cur_track,d.playtype,d.cdda_repeat_count};
    d.cr_standard_return(status|flags);
    CHECK(d.cr1==((status|flags)|(d.playtype<<7)|rep));
    CHECK(d.cr2==(((t&1?1U:0x41U)<<8)|(t+1)));
    CHECK(d.cr3==((index<<8)|((lba+150)>>16))&&d.cr4==((lba+150)&0xffff));
    CHECK(d.media.last_index==lba);
    CHECK((before==std::array<unsigned,6>{d.cd_stat,d.cd_curfad,d.cd_fad_seek,d.cur_track,d.playtype,d.cdda_repeat_count}));++reports;
   }
  }
 }
 // Preserve the existing missing-image caller status/low-byte behavior;
 // this is not qualification of the hardware's all-FF invalid report policy.
 d.media.inserted=false;
 for(unsigned status:{0x600U,0x700U,0x8600U,0x8700U,0xff00U})for(unsigned low=0;low<256;++low){
  d.cr1=0x5500|low;d.cr2=0x1234;d.cr3=0x5678;d.cr4=0x9abc;const auto queries=d.media.queries;
  d.cr_standard_return(status);CHECK(d.cr1==(status|low)&&d.cr2==0x1234&&d.cr3==0x5678&&d.cr4==0x9abc&&d.media.queries==queries);++empty;
 }
 std::printf("method-level, unvalidated: %u current/seek binary track/control/index/FAD reports; %u image-index boundaries; %u unchanged missing-image controls\n",reports,indices,empty);
 std::puts("method-level, unvalidated: actual report/index/control helpers and cdrom_file index lookup; synthetic normalized index metadata and mock image wrappers, NOT native CUE/CHD parsing, raw subcode or bus/report timing qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-report-position-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

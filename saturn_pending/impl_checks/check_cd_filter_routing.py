#!/usr/bin/env python3
"""CD selector routing/metadata, actual methods with mock media; method-level, unvalidated."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text, signature):
    start=text.index(signature); end=text.index('{',start)+1; depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}'); end+=1
    return text[start:end]
types='\n'.join(extract(header,'struct '+name)+';' for name in ('filterT','blockT','partitionT'))
functions='\n'.join(extract(source,s) for s in (
    'saturn_cd_hle_device::blockT *\nsaturn_cd_hle_device::cd_alloc_block(',
    'saturn_cd_hle_device::partitionT *\nsaturn_cd_hle_device::cd_filterdata(',
    'saturn_cd_hle_device::partitionT *\nsaturn_cd_hle_device::cd_read_filtered_sector('))
has_helper='uint8_t saturn_cd_hle_device::cd_filter_destination(' in source
if has_helper:
    functions+='\n'+extract(source,'uint8_t saturn_cd_hle_device::cd_filter_destination(')
head=r'''
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <initializer_list>
constexpr unsigned MAX_BLOCKS=200,MAX_FILTERS=24;
namespace cdrom_file { constexpr unsigned MAX_SECTOR_DATA=2352; enum {CD_TRACK_AUDIO,CD_TRACK_MODE1,CD_TRACK_MODE1_RAW,CD_TRACK_MODE2_RAW}; }
#define LOG(...) ((void)0)
#define LOGWARN(...) ((void)0)
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
struct saturn_cd_hle_device {
// TYPES
 struct Media {
  int type=cdrom_file::CD_TRACK_MODE2_RAW,reads=0,last_lba=-1,last_format=-1;
  uint8_t bytes[2352]{};
  int get_track(int lba){return lba;}
  int get_track_type(int){return type;}
  void read_data(int lba,uint8_t *to,int format){++reads;last_lba=lba;last_format=format;std::memcpy(to,bytes,sizeof(bytes));}
 } media;
 Media *m_cdrom_image=&media;
 blockT blocks[MAX_BLOCKS]{},curblock{};
 partitionT partitions[MAX_FILTERS]{};
 filterT filters[MAX_FILTERS]{},*cddevice=&filters[0];
 int freeblocks=MAX_BLOCKS,buffull=0,sectlenin=2048;
 uint32_t cd_curfad=150,fadstoplay=20;
 uint8_t lastbuf=0xff;
 saturn_cd_hle_device(){
  for(auto &b:blocks)b.size=-1;
  for(unsigned i=0;i<MAX_FILTERS;++i){filters[i].condtrue=i;filters[i].condfalse=0xff;partitions[i].size=-1;std::fill(std::begin(partitions[i].bnum),std::end(partitions[i].bnum),0xff);}
 }
 uint8_t cd_filter_destination(uint8_t,const blockT&) const;
 blockT *cd_alloc_block(uint8_t*);
 partitionT *cd_filterdata(filterT*,int,uint8_t*);
 partitionT *cd_read_filtered_sector(int32_t,uint8_t*);
};
'''
tail=r'''
int main(){
 unsigned matrix=0,chains=0,media_cases=0;
 // Integration regression: the accepted filter's TRUE connector, not the
 // false-path filter index, names the destination partition.
 {
  auto d=std::make_unique<saturn_cd_hle_device>();
  d->filters[0].mode=1;d->filters[0].fid=1;d->filters[0].condfalse=1;
  d->filters[1].condtrue=7;d->curblock.size=2352;d->curblock.FAD=321;
  d->curblock.data[15]=2;d->curblock.fnum=2;
  uint8_t ok=0;auto *p=d->cd_filterdata(&d->filters[0],cdrom_file::CD_TRACK_MODE2_RAW,&ok);
  CHECK(ok && p==&d->partitions[7] && d->lastbuf==7 && p->numblks==1);
  CHECK(d->partitions[1].numblks==0 && p->blocks[0]->FAD==321);
 }
#ifdef HAS_FILTER_HELPER
 {
  auto d=std::make_unique<saturn_cd_hle_device>();auto &f=d->filters[3];auto &b=d->curblock;
  f.fid=7;f.chan=9;f.smmask=0x1f;f.smval=0x15;f.cimask=0x7f;f.cival=0x42;
  f.fad=100;f.range=3;f.condtrue=7;f.condfalse=5;d->filters[5].condtrue=9;
  for(unsigned mode=0;mode<128;++mode){
   if(mode&0x20)continue;f.mode=mode;
   for(unsigned matches=0;matches<16;++matches)
   for(unsigned fad:{99U,100U,102U,103U}){
    b.FAD=fad;b.fnum=(matches&1)?7:6;b.chan=(matches&2)?9:8;
    b.subm=(matches&4)?0x95:0x94;b.cinf=(matches&8)?0xc2:0xc3;
    bool accept=(matches&(mode&15))==(mode&15);
    if(mode&0x10)accept=!accept;
    if((mode&0x40) && (fad<100 || fad>=103))accept=false;
    CHECK(d->cd_filter_destination(3,b)==(accept?7:9));CHECK(d->lastbuf==0xff);++matrix;
   }
  }
 }
#endif
 for(unsigned length=1;length<=24;++length){
  auto d=std::make_unique<saturn_cd_hle_device>();d->curblock.size=2352;d->curblock.data[15]=2;
  for(unsigned i=0;i<length;++i){d->filters[i].mode=1;d->filters[i].fid=1;d->filters[i].condfalse=i+1;}
  d->filters[length-1].mode=0;d->filters[length-1].condtrue=23;
  uint8_t ok=0;auto *p=d->cd_filterdata(&d->filters[0],cdrom_file::CD_TRACK_MODE2_RAW,&ok);
  CHECK(ok && p==&d->partitions[23] && d->lastbuf==23 && d->freeblocks==199);++chains;
 }
 // Discard and full-buffer paths must retain the last successful CD target.
 for(bool full:{false,true}){
  auto d=std::make_unique<saturn_cd_hle_device>();d->lastbuf=17;d->curblock.size=2352;
  if(full){for(auto &b:d->blocks)b.size=2048;d->freeblocks=0;}
  else d->filters[0].condtrue=0xff;
  uint8_t ok=1;CHECK(d->cd_filterdata(&d->filters[0],cdrom_file::CD_TRACK_MODE2_RAW,&ok)==nullptr);
  CHECK(!ok && d->lastbuf==17);
 }
 // Legal media transition: a Mode 2 subheader must not leak into the next
 // Mode 1 or audio sector. Mode 1 now tests its zero-valued subheader.
 for(int type:{cdrom_file::CD_TRACK_MODE1,cdrom_file::CD_TRACK_MODE1_RAW,cdrom_file::CD_TRACK_AUDIO})
 for(unsigned prior=1;prior<256;++prior){
  auto d=std::make_unique<saturn_cd_hle_device>();d->sectlenin=2352;
  d->media.bytes[15]=2;d->media.bytes[16]=prior;d->media.bytes[17]=prior;
  d->media.bytes[18]=prior&0xdf;d->media.bytes[19]=prior;
  uint8_t ok=0;CHECK(d->cd_read_filtered_sector(150,&ok)==&d->partitions[0] && ok);
  CHECK(d->curblock.fnum==prior);
  d->media.type=type;if(type!=cdrom_file::CD_TRACK_AUDIO)d->media.bytes[15]=1;
  d->filters[0].mode=1;d->filters[0].fid=0;d->filters[0].condtrue=7;
  CHECK(d->cd_read_filtered_sector(151,&ok)==&d->partitions[7] && ok);
  const auto &b=*d->partitions[7].blocks[0];
  CHECK(b.FAD==151 && !b.fnum && !b.chan && !b.subm && !b.cinf);
  CHECK(d->media.reads==2 && d->media.last_lba==1 && d->lastbuf==7);
  // A nonzero FN predicate must reject Mode 1/audio, not bypass filtering.
  d->filters[0].fid=1;
  CHECK(d->cd_read_filtered_sector(152,&ok)==nullptr && !ok && d->lastbuf==7);
  ++media_cases;
 }
 std::printf("method-level, unvalidated: %u condition matrix cases; %u acyclic chain lengths; %u Mode 2 to Mode 1/audio transitions; nonidentity true connector and discard/full-buffer last-target controls\n",matrix,chains,media_cases);
 std::puts("method-level, unvalidated: mock media/synchronous allocation; no native CD timing, firmware, gameplay, copy/move or save-manager qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-filter-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(('#define HAS_FILTER_HELPER\n' if has_helper else '')+head.replace('// TYPES',types)+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

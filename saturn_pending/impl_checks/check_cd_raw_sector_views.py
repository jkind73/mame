#!/usr/bin/env python3
"""Raw media preservation and sector-boundary host views; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
# Reuse the registration/hook/transfer scaffold, not its tests or expectations.
fixture=Path(__file__).with_name('check_cd_buffer_save.py')
setup=fixture.read_text().split("tail=r'''",1)[0]
scope={'__file__':str(fixture),'__name__':'raw_sector_scaffold'}
exec(compile(setup,str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace(' void device_pre_save();',r'''
 uint32_t calcsize=0;
 void cmd_set_sector_length();void cmd_calculate_actual_data_size();
 void cmd_copy_sector_data();void cmd_move_sector_data();void cd_copy_move_sector_data(bool);
 void cmd_get_sector_data();void cmd_get_and_delete_sector_data();
 void cd_getsectoroffsetnum(uint32_t,uint32_t*,uint32_t*);
 void device_pre_save();''')
head+='\n#define LOGCMD(...) ((void)0)\nconstexpr unsigned ESEL=0x40,DRDY=2,ECPY=0x100,CD_STAT_REJECT=0xff00;\n#include <array>\n'
functions+='\n'+'\n'.join(extract(source,s) for s in (
 'saturn_cd_hle_device::blockT *\nsaturn_cd_hle_device::cd_alloc_block(',
 'saturn_cd_hle_device::partitionT *\nsaturn_cd_hle_device::cd_filterdata(',
 'saturn_cd_hle_device::partitionT *\nsaturn_cd_hle_device::cd_read_filtered_sector(',
 'void saturn_cd_hle_device::cmd_set_sector_length()',
 'void saturn_cd_hle_device::cmd_calculate_actual_data_size()',
 'void saturn_cd_hle_device::cmd_get_sector_data()',
 'void saturn_cd_hle_device::cmd_get_and_delete_sector_data()',
 'void saturn_cd_hle_device::cd_getsectoroffsetnum(',
 'void saturn_cd_hle_device::cmd_copy_sector_data()',
 'void saturn_cd_hle_device::cmd_move_sector_data()',
 'void saturn_cd_hle_device::cd_copy_move_sector_data('))
tail=r'''
using D=saturn_cd_hle_device;using Raw=std::array<uint8_t,2352>;
unsigned size(unsigned kind,unsigned format){return format==0?(kind==2?2324:2048):format==1?2336:format==2?2340:2352;}
unsigned offset(unsigned kind,unsigned format){return format==0?(kind==0?16:24):format==1?16:format==2?12:0;}
void format(D &d,unsigned f){d.cr1=0x6000|f;d.cr2=0xff00;d.cmd_set_sector_length();}
std::array<Raw,2> seed(D &d,unsigned first,unsigned second,unsigned ingest){
 format(d,ingest);d.cddevicenum=0;std::array<Raw,2> raw;
 for(unsigned n=0;n<2;++n){const unsigned kind=n?second:first;
  for(unsigned i=0;i<2352;++i)raw[n][i]=uint8_t(i*17+n*37+kind*3);
  raw[n][15]=kind==0?1:2;raw[n][16]=3;raw[n][17]=9;raw[n][18]=kind==2?0x20:4;raw[n][19]=0x42;
  d.media.type=kind==0?cdrom_file::CD_TRACK_MODE1_RAW:cdrom_file::CD_TRACK_MODE2_RAW;
  std::memcpy(d.media.bytes,raw[n].data(),2352);uint8_t ok=0;
  CHECK(d.cd_read_filtered_sector(150+n,&ok)==&d.partitions[0]&&ok);
  const auto &b=*d.partitions[0].blocks[n];CHECK(b.raw_data&&b.size==2352&&!std::memcmp(b.data,raw[n].data(),2352));
 }
 CHECK(d.partitions[0].numblks==2&&d.partitions[0].size==4704&&d.freeblocks==198);return raw;
}
std::vector<uint32_t> words(const std::array<Raw,2>&raw,unsigned first,unsigned second,unsigned f0,unsigned f1){
 std::vector<uint32_t> v;for(unsigned n=0;n<2;++n){const unsigned kind=n?second:first,fmt=n?f1:f0;
  for(unsigned pos=0;pos<size(kind,fmt);pos+=4)v.push_back(get_u32be(raw[n].data()+offset(kind,fmt)+pos));}
 return v;
}
void start(D &d,bool remove){d.cr1=remove?0x6300:0x6100;d.cr2=d.cr3=0;d.cr4=2;if(remove)d.cmd_get_and_delete_sector_data();else d.cmd_get_sector_data();}
void finish(D &d,const std::vector<uint32_t>&want,unsigned cut,bool remove){
 for(unsigned word=cut;word<want.size();++word)CHECK(d.dataxfer_long_r()==want[word]);
 CHECK(d.xfersect==2&&d.xferoffs==0&&d.xferdnum==want.size()*4);d.cmd_end_data_transfer();CHECK(d.cr2==want.size()*2);
 CHECK(d.freeblocks==(remove?200:198)&&d.partitions[0].numblks==(remove?0:2)&&d.partitions[0].size==(remove?0:4704));
}
int main(){unsigned views=0,replays=0,copies=0;
 for(unsigned first=0;first<3;++first)for(unsigned second=0;second<3;++second)
 for(unsigned ingest=0;ingest<4;++ingest)for(unsigned fetch=0;fetch<4;++fetch)for(bool remove:{false,true}){
  auto d=std::make_unique<D>();auto raw=seed(*d,first,second,ingest);format(*d,fetch);
  d->cr1=0x5200;d->cr2=d->cr3=0;d->cr4=2;d->cmd_calculate_actual_data_size();CHECK(d->calcsize==(size(first,fetch)+size(second,fetch))/2);
  start(*d,remove);finish(*d,words(raw,first,second,fetch,fetch),0,remove);++views;
 }
 for(unsigned first=0;first<3;++first)for(unsigned old=0;old<4;++old)for(unsigned next=0;next<4;++next)
 for(unsigned cut:{0U,1U,size(first,old)/8,size(first,old)/4-1})for(bool remove:{false,true}){
  const unsigned second=(first+1)%3;auto d=std::make_unique<D>();auto raw=seed(*d,first,second,0);format(*d,old);start(*d,remove);
  const auto want=words(raw,first,second,old,next);
  for(unsigned i=0;i<cut;++i)CHECK(d->dataxfer_long_r()==want[i]);
  format(*d,next);d->register_state();d->capture();finish(*d,want,cut,remove);
  for(auto &b:d->blocks){std::fill(std::begin(b.data),std::end(b.data),0xee);b.raw_data=false;b.size=-1;}
  d->m_xfer_raw_offset=d->m_xfer_raw_size=0;d->m_xfer_raw_sector=0xffffffff;d->sectlenin=0;d->xferoffs=d->xferdnum=d->xfersect=0;d->xfertype32=D::XFERTYPE32_INVALID;d->transpart=nullptr;
  const unsigned irqs=d->irqs;d->restore();CHECK(d->irqs==irqs&&d->blocks[0].raw_data&&d->blocks[1].raw_data);
  finish(*d,want,cut,remove);++replays;
 }
 for(unsigned first=0;first<3;++first)for(unsigned fetch=0;fetch<4;++fetch)for(bool move:{false,true}){
  const unsigned second=(first+1)%3;auto d=std::make_unique<D>();auto raw=seed(*d,first,second,0);format(*d,fetch);
  d->cr1=(move?0x6600:0x6500)|1;d->cr2=d->cr3=0;d->cr4=0xffff;if(move)d->cmd_move_sector_data();else d->cmd_copy_sector_data();
  CHECK(d->partitions[1].numblks==2&&d->partitions[1].size==4704&&d->freeblocks==(move?198:196));
  for(unsigned i=0;i<2;++i){auto *b=d->partitions[1].blocks[i];CHECK(b&&b->raw_data&&!std::memcmp(b->data,raw[i].data(),2352));}
  d->cr1=0x6100;d->cr2=0;d->cr3=1<<8;d->cr4=2;d->cmd_get_sector_data();const auto want=words(raw,first,second,fetch,fetch);
  for(auto word:want)CHECK(d->dataxfer_long_r()==word);d->cmd_end_data_transfer();CHECK(d->cr2==want.size()*2);++copies;
 }
 // Reused media allocation must not make a later cooked PUT look raw.
 auto d=std::make_unique<D>();d->blocks[0].raw_data=true;d->blocks[0].size=-1;uint8_t id=255;auto *b=d->cd_alloc_block(&id);CHECK(id==0&&b&&!b->raw_data);
 std::printf("method-level, unvalidated: %u raw media/view/size/GETDELETE images; %u mid-sector size-change registered replays; %u raw COPY/MOVE view controls; raw-allocation reuse control\n",views,replays,copies);
 std::puts("method-level, unvalidated: actual media routing/allocation/format/GET/size/cleanup/save methods with mock media/serializer/IRQ; no native bus, ECC, raw PUT or sector-boundary timing qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-raw-views-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

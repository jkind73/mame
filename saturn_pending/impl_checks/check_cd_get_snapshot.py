#!/usr/bin/env python3
"""GET physical slot identity across public compaction; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_sector_views.py')
scope={'__file__':str(fixture),'__name__':'get_snapshot_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace(' void cmd_get_sector_data();',' void cmd_delete_sector_data();void cmd_get_sector_data();')
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_delete_sector_data()')
tail=r'''
using D=saturn_cd_hle_device;
unsigned capacity(bool raw,unsigned id){return raw?2352:32+4*(id%5);}
uint8_t byte(unsigned id,unsigned pos,unsigned salt=0){
 if(pos==15)return id%3==0?1:2;
 if(pos==18)return id%3==2?0x20:4;
 return uint8_t(id*31+pos*7+(pos>>8)*11+salt);
}
void append(D &d,unsigned buf,bool raw,unsigned salt){
 uint8_t id=255;auto *b=d.cd_alloc_block(&id);CHECK(b&&id<200);
 b->size=capacity(raw,id);b->raw_data=raw;b->FAD=150+id;
 for(unsigned j=0;j<2352;++j)b->data[j]=byte(id,j,salt);
 auto &p=d.partitions[buf];if(p.size<0)p.size=0;
 p.blocks[p.numblks]=b;p.bnum[p.numblks]=id;++p.numblks;p.size+=b->size;
}
std::vector<uint32_t> oracle(unsigned first,unsigned count,bool raw,unsigned fmt){
 constexpr unsigned sizes[]={2048,2336,2340,2352},offsets[]={0,16,12,0};
 std::vector<uint32_t> out;
 for(unsigned id=first;id<first+count;++id){
  const unsigned offset=raw?(fmt?offsets[fmt]:id%3==0?16:24):0;
  const unsigned size=raw?(fmt==0&&id%3==2?2324:sizes[fmt]):capacity(false,id);
  for(unsigned j=0;j<size;j+=4){uint32_t word=0;for(unsigned k=0;k<4;++k)word=(word<<8)|byte(id,offset+j+k);out.push_back(word);}
 }
 return out;
}
unsigned cases=0,replays=0,waits=0,large=0;
void run(unsigned buf,unsigned first,unsigned count,unsigned remove,bool refill,bool raw,unsigned fmt,unsigned phase){
 auto device=std::make_unique<D>();auto &d=*device;const unsigned total=first+count;
 for(unsigned i=0;i<total;++i)append(d,buf,raw,0);
 const auto want=oracle(first,count,raw,fmt);const unsigned cut=phase==0?0:phase==1?1:phase==2?want.size()/2:want.size();
 const auto original_size=d.partitions[buf].size;
 d.cr1=0x6000|fmt;d.cr2=0xff00;d.cmd_set_sector_length();
 d.cr1=0x6100;d.cr2=first;d.cr3=buf<<8;d.cr4=count;d.cmd_get_sector_data();
 CHECK(d.m_host_transfer_active&&d.xfertype32==D::XFERTYPE32_GETSECTOR);
 CHECK(d.freeblocks==200-total);
 for(unsigned i=0;i<cut;++i)CHECK(d.dataxfer_long_r()==want[i]);
 d.cr1=0x6200;d.cr2=0;d.cr3=buf<<8;d.cr4=remove;d.cmd_delete_sector_data();
 CHECK(d.partitions[buf].numblks==total-remove&&d.freeblocks==200-total+remove&&d.m_host_transfer_active&&d.xferdnum==cut*4);
 if(refill)for(unsigned i=0;i<remove;++i)append(d,buf,raw,0xa5);
 CHECK(d.freeblocks==200-total+(refill?0:remove));
 // A replacement GET must WAIT, not overwrite the accepted snapshot.
 d.cr1=0x6100;d.cr2=0;d.cr3=buf<<8;d.cr4=1;d.cmd_get_sector_data();
 CHECK(d.cr1==(d.cd_stat|CD_STAT_WAIT)&&d.xferdnum==cut*4);++waits;
 if(buf==0||buf==23){
  d.register_state();d.capture();CHECK(d.m_saved_transpart==25);
  d.m_get_partition={};d.transpart=nullptr;d.m_host_transfer_active=false;
  d.xferoffs=d.xfersect=d.xfersectpos=d.xfersectnum=d.xferdnum=0;
  d.m_xfer_raw_offset=d.m_xfer_raw_size=0;d.m_xfer_raw_sector=0xffffffff;d.sectlenin=0;
  for(auto &p:d.partitions){p={};std::fill(std::begin(p.bnum),std::end(p.bnum),0xff);}
  for(auto &b:d.blocks){b.size=-1;b.raw_data=false;std::fill(std::begin(b.data),std::end(b.data),0xee);}
  const auto irq=d.irqs;d.restore();CHECK(d.irqs==irq&&d.m_host_transfer_active&&d.transpart==&d.m_get_partition&&d.xferdnum==cut*4);++replays;
 }
 for(unsigned i=cut;i<want.size();++i)CHECK(d.dataxfer_long_r()==want[i]);
 CHECK(d.m_get_partition.numblks==total&&d.m_get_partition.size==original_size);
 for(unsigned i=0;i<total;++i)CHECK(d.m_get_partition.bnum[i]==i&&d.m_get_partition.blocks[i]==&d.blocks[i]);
 CHECK(d.xfersect==count&&d.xferdnum==want.size()*4&&d.m_host_transfer_active);
 d.dataxfer_long_r();CHECK(d.xferdnum==want.size()*4&&d.m_host_transfer_active);
 const auto public_size=d.partitions[buf].size;d.cmd_end_data_transfer();
 CHECK(!d.m_host_transfer_active&&d.xfertype32==D::XFERTYPE32_INVALID);
 CHECK((((d.cr1&255)<<16)|d.cr2)==want.size()*2&&d.partitions[buf].size==public_size&&d.freeblocks==200-total+(refill?0:remove));
 ++cases;
}
int main(){
 // First control fails the historical implementation on actual returned data,
 // before any snapshot-layout or serialization assertion.
 run(1,1,1,1,false,true,0,0);
 for(unsigned buf=0;buf<24;++buf)for(unsigned first:{1U,3U,198U})
 for(unsigned count:{1U,std::min(3U,200-first)})for(unsigned choice=0;choice<2;++choice){
  if(first==1&&choice)continue;
  const unsigned remove=choice?first:1;
  for(bool refill:{false,true})for(bool raw:{false,true})for(unsigned fmt=0;fmt<4;++fmt)for(unsigned phase=0;phase<4;++phase)
   run(buf,first,count,remove,refill,raw,fmt,phase);
 }
 for(unsigned buf=0;buf<24;++buf)for(bool raw:{false,true})for(unsigned fmt:{0U,3U})for(unsigned phase:{0U,2U,3U}){
  run(buf,1,199,1,true,raw,fmt,phase);++large;
 }
 std::printf("method-level, unvalidated: %u compacted/refilled GET slot maps; %u registered continuations; %u replacement WAIT controls; %u 199-sector controls included\n",cases,replays,waits,large);
 std::puts("method-level, unvalidated: actual GET/Delete/port/End/allocation/save methods, mock IRQ/report/serializer; selected-buffer freeing/reuse, GETDELETE detachment, FIFO/prefetch and native save/bus timing excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-get-snapshot-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
# Hard-reset control uses the actual reset body and existing declaration adapter.
fixture=Path(__file__).with_name('check_cd_selector_reset.py')
scope={'__file__':str(fixture),'__name__':'get_reset_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions=(scope[k] for k in ('head','functions'))
if 'm_get_partition' not in head:
    head=head.replace(' partitionT m_put_partition{};',' partitionT m_get_partition{};partitionT m_put_partition{};')
tail=r'''
int main(){for(unsigned poison=0;poison<256;++poison){auto d=std::make_unique<saturn_cd_hle_device>();
 d->m_get_partition.size=2352;d->m_get_partition.numblks=200;d->transpart=&d->m_get_partition;d->m_saved_transpart=25;d->m_host_transfer_active=true;
 for(unsigned i=0;i<200;++i){d->m_get_partition.bnum[i]=poison;d->m_get_partition.blocks[i]=&d->blocks[i];}
 d->device_reset();CHECK(d->m_get_partition.size==-1&&!d->m_get_partition.numblks&&!d->transpart&&!d->m_host_transfer_active&&d->m_saved_transpart==-1&&d->freeblocks==200);
 for(unsigned i=0;i<200;++i)CHECK(d->m_get_partition.bnum[i]==255&&!d->m_get_partition.blocks[i]);
 }std::puts("method-level, unvalidated: 256 actual reset snapshot/ownership/pointer controls");}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-get-reset-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

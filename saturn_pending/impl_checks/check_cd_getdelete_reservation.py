#!/usr/bin/env python3
"""GETDELETE public detachment and private lifetime to DataEnd; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_put.py')
scope={'__file__':str(fixture),'__name__':'getdelete_reservation_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
at=head.rfind('};');head=head[:at]+r'''
 bool buffull_temp_pause=false,m_status_change_in_progress=false;
 uint16_t cd_next_stat=0;int m_seek_ticks_left=0;
 void cmd_abort_file();void cd_change_status(uint16_t);
 void cmd_get_buffer_size();void cmd_get_buffer_partition_sector_number();
 void cmd_delete_sector_data();void cmd_reset_selector();void cd_reset_filter_conditions(filterT&);
'''+head[at:]
head=head.replace('void update_hirq(){++irqs;}', 'void (*notice)(saturn_cd_hle_device&)=nullptr;void update_hirq(){++irqs;if(notice)notice(*this);}')
head+='\nusing u16=uint16_t;\n#define LOGSTATUS(...) ((void)0)\nconstexpr unsigned EFLS=0x200,CD_STAT_BUSY=0,CD_STAT_PAUSE=0x100,CD_STAT_SEEK=0x400,CD_STAT_NODISC=0x700,CD_STAT_OPEN=0x600,CD_STAT_PERI=0x2000;\ntemplate<class T>bool BIT(T value,unsigned bit){return (value>>bit)&1;}\n'
functions+='\n'+'\n'.join(extract(source,'void saturn_cd_hle_device::'+name+'(') for name in (
 'cmd_get_buffer_size','cmd_get_buffer_partition_sector_number','cmd_delete_sector_data','cmd_reset_selector','cd_reset_filter_conditions','cmd_abort_file','cd_change_status'))
helper=Path(__file__).with_name('check_cd_get_snapshot.py')
helpers=helper.read_text().split("\ntail=r'''",1)[1].split('unsigned cases=',1)[0]
tail=r'''
unsigned observed=0,seen_buf=0,seen_total=0,seen_count=0,seen_first=0;
void notice(D &d){CHECK(d.m_host_transfer_active&&(d.hirqreg&DRDY));
 CHECK(d.partitions[seen_buf].numblks==seen_total-seen_count&&d.partitions[seen_buf].size==2352*(seen_total-seen_count)&&d.freeblocks==200-seen_total);
 CHECK(d.transpart==&d.m_get_partition&&d.xfertype32==D::XFERTYPE32_GETDELETESECTOR);
 for(unsigned i=seen_first;i<seen_first+seen_count;++i)CHECK(d.m_get_partition.bnum[i]==i&&d.m_get_partition.blocks[i]==&d.blocks[i]&&d.blocks[i].size==2352);++observed;
}
uint64_t public_image(const D &d){uint64_t h=1469598103934665603ULL;
 auto add=[&](const auto &v){const auto *p=reinterpret_cast<const uint8_t*>(&v);for(unsigned i=0;i<sizeof(v);++i){h^=p[i];h*=1099511628211ULL;}};
 for(const auto &p:d.partitions){add(p.size);add(p.numblks);add(p.bnum);for(unsigned i=0;i<p.numblks;++i){const auto &b=*p.blocks[i];add(b.size);add(b.data);add(b.raw_data);add(b.FAD);}}
 return h;
}
void queries(D &d,unsigned buf,unsigned count,unsigned free){
 d.cr1=0x5100;d.cr2=d.cr4=0;d.cr3=buf<<8;d.cmd_get_buffer_partition_sector_number();CHECK(d.cr4==count);
 d.cr1=0x5000;d.cmd_get_buffer_size();CHECK(d.cr2==free);
}
void release(D &d,unsigned first,unsigned count,unsigned free,uint64_t image,bool full,unsigned words){
 CHECK(d.m_host_transfer_active&&d.freeblocks==free);d.cmd_end_data_transfer();
 CHECK(!d.m_host_transfer_active&&d.xfertype32==D::XFERTYPE32_INVALID&&d.freeblocks==free+count&&!d.buffull&&public_image(d)==image);
 if(full)CHECK((((d.cr1&255)<<16)|d.cr2)==words*2);
 for(unsigned i=first;i<first+count;++i)CHECK(d.blocks[i].size==-1);
 d.dataxfer_long_r();d.cmd_end_data_transfer();CHECK(d.freeblocks==free+count&&public_image(d)==image);
}
unsigned cases=0,replays=0,waits=0,edges=0;
void run(unsigned buf,unsigned total,unsigned first,unsigned count,unsigned fmt,unsigned pressure,unsigned phase){
 auto p=std::make_unique<D>();auto &d=*p;
 for(unsigned i=0;i<total;++i)append(d,buf,true,0);
 const auto want=oracle(first,count,true,fmt);const unsigned cut=phase==0?0:phase==1?1:phase==2?want.size()/2:want.size();
 d.cr1=0x6000|fmt;d.cr2=0xff00;d.cmd_set_sector_length();
 d.cr1=0x6300;d.cr2=first;d.cr3=buf<<8;d.cr4=count;
 seen_buf=buf;seen_total=total;seen_first=first;seen_count=count;d.notice=notice;d.cmd_get_and_delete_sector_data();d.notice=nullptr;
 queries(d,buf,total-count,200-total);
 for(unsigned i=0;i<total-count;++i)CHECK(d.partitions[buf].bnum[i]==(i<first?i:i+count));
 if(pressure==1&&total>count){d.cr1=0x6200;d.cr2=0;d.cr3=buf<<8;d.cr4=0xffff;d.cmd_delete_sector_data();}
 if(pressure>=2){d.cr1=0x4800;d.cr3=buf<<8;d.cmd_reset_selector();
  const unsigned destination=pressure==2?buf:(buf+1)%24;
  while(d.freeblocks)append(d,destination,true,0xa5);
 }
 const unsigned free=d.freeblocks;const auto image=public_image(d);
 for(unsigned i=0;i<cut;++i)CHECK(d.dataxfer_long_r()==want[i]);
 if(phase==3)for(unsigned i=0;i<3;++i)d.dataxfer_long_r();
 CHECK(d.m_host_transfer_active&&d.xferdnum==cut*4&&d.freeblocks==free&&public_image(d)==image);
 for(unsigned i=first;i<first+count;++i)CHECK(d.blocks[i].size==2352&&d.blocks[i].raw_data);
 d.cr1=0x7500;d.cmd_abort_file();
 CHECK(d.m_host_transfer_active&&d.xfertype32==D::XFERTYPE32_GETDELETESECTOR&&d.transpart==&d.m_get_partition&&d.xferdnum==cut*4&&d.freeblocks==free&&public_image(d)==image);
 for(unsigned cmd:{0x6100U,0x6300U,0x6400U}){
  d.cr1=cmd;d.cr2=0;d.cr3=buf<<8;d.cr4=1;
  if(cmd==0x6100)d.cmd_get_sector_data();else if(cmd==0x6300)d.cmd_get_and_delete_sector_data();else d.cmd_put_sector_data();
  CHECK(d.cr1==(d.cd_stat|CD_STAT_WAIT)&&d.freeblocks==free&&d.m_host_transfer_active&&d.xferdnum==cut*4&&public_image(d)==image);++waits;
 }
 const bool replay=buf==0||buf==23;
 if(replay){d.register_state();d.capture();CHECK(d.m_saved_transpart==25);}
 release(d,first,count,free,image,phase==3,want.size());
 if(replay){
  d.m_get_partition={};d.transpart=nullptr;d.m_host_transfer_active=false;d.xfertype32=D::XFERTYPE32_INVALID;
  d.xferoffs=d.xfersect=d.xfersectpos=d.xfersectnum=d.xferdnum=0;d.m_xfer_raw_offset=d.m_xfer_raw_size=0;d.m_xfer_raw_sector=0xffffffff;
  for(auto &part:d.partitions){part={};std::fill(std::begin(part.bnum),std::end(part.bnum),0xff);}
  for(auto &b:d.blocks){b.size=-1;b.raw_data=false;std::fill(std::begin(b.data),std::end(b.data),0xee);}
  const auto irq=d.irqs;d.restore();CHECK(d.irqs==irq&&d.m_host_transfer_active&&d.transpart==&d.m_get_partition&&d.xferdnum==cut*4&&d.freeblocks==free&&public_image(d)==image);
  for(unsigned i=cut;i<want.size();++i)CHECK(d.dataxfer_long_r()==want[i]);
  d.dataxfer_long_r();CHECK(d.freeblocks==free&&d.m_host_transfer_active&&d.xferdnum==want.size()*4);
  release(d,first,count,free,image,true,want.size());++replays;
 }
 ++cases;
}
int main(){
 for(unsigned buf=0;buf<24;++buf)for(unsigned total:{3U,5U})for(unsigned first:{0U,1U,total-1})for(unsigned choice=0;choice<2;++choice){
  if(choice&&first==total-1)continue;const unsigned count=choice?total-first:1;
  for(unsigned fmt=0;fmt<4;++fmt)for(unsigned pressure=0;pressure<4;++pressure)for(unsigned phase=0;phase<4;++phase)
   run(buf,total,first,count,fmt,pressure,phase);
 }
 for(unsigned buf:{0U,23U})for(unsigned first:{0U,1U,198U,199U})for(unsigned choice=0;choice<2;++choice){
  if(choice&&first==199)continue;const unsigned count=choice?200-first:1;
  for(unsigned fmt=0;fmt<4;++fmt)for(unsigned pressure=0;pressure<4;++pressure)for(unsigned phase=0;phase<4;++phase){
   run(buf,200,first,count,fmt,pressure,phase);++edges;
  }
 }
 std::printf("method-level, unvalidated: %u detached GETDELETE reservations; %u ready observations; %u registered private replays; %u replacement WAIT controls; %u full-pool/edge-slot cases included\n",cases,observed,replays,waits,edges);
 std::puts("method-level, unvalidated: actual GETDELETE/query/Delete/single-partition-reset/Abort/allocation/port/End/save methods; mocked report/IRQ/serializer; unread/partial/EOF release and no double free; no interrupted DataEnd-count, FIFO/prefetch, global-reset capacity or native timing qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-getdelete-reservation-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

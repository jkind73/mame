#!/usr/bin/env python3
"""Captured raw GET survives allocation release without pinning/copying; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_get_snapshot.py')
scope={'__file__':str(fixture),'__name__':'freed_backing_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace(' void cmd_delete_sector_data();',' void cmd_put_sector_data();void cmd_delete_sector_data();')
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_put_sector_data()')
helpers=fixture.read_text().split("\ntail=r'''",1)[1].split('unsigned cases=',1)[0]
tail=r'''
unsigned cases=0,replays=0,waits=0,edges=0;
void format(D &d,unsigned value){d.cr1=0x6000|value;d.cr2=0xff00;d.cmd_set_sector_length();}
void start(D &d,unsigned buf,unsigned first,unsigned count){d.cr1=0x6100;d.cr2=first;d.cr3=buf<<8;d.cr4=count;d.cmd_get_sector_data();}
void erase(D &d,unsigned buf,unsigned first,unsigned count){d.cr1=0x6200;d.cr2=first;d.cr3=buf<<8;d.cr4=count;d.cmd_delete_sector_data();}
void run(unsigned buf,unsigned first,unsigned count,bool all,unsigned old,unsigned next,unsigned phase){
 auto ptr=std::make_unique<D>();auto &d=*ptr;const unsigned total=first+count;
 for(unsigned i=0;i<total;++i)append(d,buf,true,0);
 auto want=oracle(first,count,true,old);const unsigned firstwords=oracle(first,1,true,old).size();
 unsigned cut=0;
 switch(phase){case 1:cut=1;break;case 2:cut=firstwords/2;break;case 3:cut=firstwords-1;break;case 4:cut=firstwords;break;case 5:cut=want.size();break;}
 if(phase!=5&&count>1){want.resize(firstwords);const auto rest=oracle(first+1,count-1,true,next);want.insert(want.end(),rest.begin(),rest.end());}
 format(d,old);start(d,buf,first,count);
 for(unsigned i=0;i<cut;++i)CHECK(d.dataxfer_long_r()==want[i]);
 erase(d,buf,all?0:first,all?total:count);const unsigned remaining=all?0:first;
 CHECK(d.partitions[buf].numblks==remaining&&d.freeblocks==200-remaining&&d.m_host_transfer_active&&d.xferdnum==cut*4&&!d.buffull);
 for(unsigned id=first;id<total;++id){CHECK(d.blocks[id].size==-1&&d.blocks[id].raw_data);for(unsigned j=0;j<2352;++j)CHECK(d.blocks[id].data[j]==byte(id,j));}
 format(d,next);
 // Free capacity does not release the host interface for another GET/PUT.
 start(d,buf,0,1);CHECK(d.cr1==(d.cd_stat|CD_STAT_WAIT)&&d.m_host_transfer_active&&d.xferdnum==cut*4);++waits;
 d.cr1=0x6400;d.cr2=0;d.cr3=buf<<8;d.cr4=1;d.cmd_put_sector_data();
 CHECK(d.cr1==(d.cd_stat|CD_STAT_WAIT)&&d.m_host_transfer_active&&!d.m_put_partition.numblks&&d.m_put_filter==255&&d.freeblocks==200-remaining&&d.xferdnum==cut*4);++waits;
 if(buf==0||buf==23){
  d.register_state();d.capture();d.m_get_partition={};d.transpart=nullptr;
  d.xfertype32=D::XFERTYPE32_INVALID;d.m_host_transfer_active=false;d.xferdnum=d.xferoffs=d.xfersect=d.xfersectpos=d.xfersectnum=0;
  d.m_xfer_raw_offset=d.m_xfer_raw_size=0;d.m_xfer_raw_sector=0xffffffff;d.sectlenin=0;
  for(auto &b:d.blocks){b.size=4;b.raw_data=false;std::fill(std::begin(b.data),std::end(b.data),0xee);}
  const unsigned irq=d.irqs;d.restore();CHECK(d.irqs==irq&&d.m_host_transfer_active&&d.transpart==&d.m_get_partition&&d.xferdnum==cut*4);++replays;
 }
 for(unsigned i=cut;i<want.size();++i)CHECK(d.dataxfer_long_r()==want[i]);
 CHECK(d.xferdnum==want.size()*4&&d.xfersect==count&&d.m_host_transfer_active);
 d.dataxfer_long_r();CHECK(d.xferdnum==want.size()*4&&d.freeblocks==200-remaining);
 d.cmd_end_data_transfer();CHECK((((d.cr1&255)<<16)|d.cr2)==want.size()*2&&!d.m_host_transfer_active&&d.freeblocks==200-remaining&&d.partitions[buf].numblks==remaining);
 for(unsigned id=first;id<total;++id)CHECK(d.blocks[id].size==-1&&d.blocks[id].raw_data);++cases;
}
int main(){unsigned modes=0,guards=0;
 for(unsigned buf=0;buf<24;++buf)for(unsigned first:{0U,2U})for(unsigned count:{1U,3U})for(bool all:{false,true})
 for(unsigned old=0;old<4;++old)for(unsigned next=0;next<4;++next)for(unsigned phase=0;phase<6;++phase)
  run(buf,first,count,all,old,next,phase);
 for(unsigned buf=0;buf<24;++buf)for(unsigned count:{1U,2U})for(bool all:{false,true})
 for(unsigned old:{0U,3U})for(unsigned next:{0U,3U})for(unsigned phase:{0U,2U,5U}){
  run(buf,198,count,all,old,next,phase);++edges;
 }
 for(unsigned buf:{0U,23U})for(unsigned old=0;old<4;++old)for(unsigned next=0;next<4;++next)for(unsigned phase:{0U,2U,5U}){
  run(buf,0,200,true,old,next,phase);++edges;
 }
 for(unsigned mode=0;mode<256;++mode)for(unsigned subm:{0U,32U})for(unsigned fmt=0;fmt<4;++fmt){
  auto p=std::make_unique<D>();auto &d=*p;append(d,0,true,0);auto &b=d.blocks[0];b.data[15]=mode;b.data[18]=subm;
  const unsigned sizes[]={2048,2336,2340,2352},offsets[]={mode==1?16U:24U,16,12,0};
  const unsigned size=fmt==0&&mode==2&&subm?2324:sizes[fmt],offset=offsets[fmt];std::vector<uint32_t>want;
  for(unsigned j=0;j<size;j+=4)want.push_back(get_u32be(b.data+offset+j));
  format(d,fmt);start(d,0,0,1);erase(d,0,0,1);CHECK(b.size==-1&&d.freeblocks==200);
  for(auto word:want)CHECK(d.dataxfer_long_r()==word);d.cmd_end_data_transfer();CHECK(d.cr2==size/2&&d.freeblocks==200);++modes;
 }
 // Bounds remain enforced. Non-raw legacy/cooked invalid sizes are not
 // reinterpreted as physical raw storage by this change.
 for(unsigned damage=0;damage<6;++damage){
  auto p=std::make_unique<D>();auto &d=*p;append(d,0,true,0);format(d,0);start(d,0,0,1);erase(d,0,0,1);
  if(damage==0)d.m_get_partition.blocks[0]=nullptr;
  if(damage==1)d.blocks[0].raw_data=false;
  if(damage==2){d.blocks[0].raw_data=false;d.blocks[0].size=2353;}
  if(damage==3)d.m_xfer_raw_size=2;
  if(damage==4)d.m_xfer_raw_offset=2353;
  if(damage==5)d.xferoffs=2352;
  d.dataxfer_long_r();CHECK(d.xferdnum==0&&d.m_host_transfer_active&&d.freeblocks==200);++guards;
 }
 std::printf("method-level, unvalidated: %u freed raw GET continuations; %u registered replays; %u retained-owner WAIT controls; %u slot198/199/full-pool cases included; %u all-mode/submode view controls; %u bounds/legacy guards\n",cases,replays,waits,edges,modes,guards);
 std::puts("method-level, unvalidated: actual GET/Delete/port/End/allocation/save methods, mocked report/IRQ/serializer; no selected-slot reuse, payload-copy guarantee, GETDELETE detachment, FIFO/prefetch, cooked/audio model change or native qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-freed-backing-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

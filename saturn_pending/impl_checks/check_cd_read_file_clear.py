#!/usr/bin/env python3
"""Read File clears only its admitted public work partition; method-level, unvalidated."""
from pathlib import Path
import runpy
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_buffer_reset_resume.py')
scope={'__file__':str(fixture),'__name__':'read_file_clear_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers=(scope[k] for k in ('source','head','functions','extract','helpers'))
header=(Path(__file__).resolve().parents[2]/'src/mame/sega/saturn_cd_hle.h').read_text()
dev=extract(head,'struct saturn_cd_hle_device')
head=head.replace(dev,dev[:-1]+'\n'+extract(header,'struct direntryT')+';\nstd::vector<direntryT> curdir;void cmd_read_file();\n}',1)
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_read_file()')
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)
tail=r'''
uint32_t word(unsigned pos){uint32_t v=0;for(unsigned i=0;i<4;++i)v=(v<<8)|byte(0,pos+i);return v;}
uint64_t partition_image(const D::partitionT &p){uint64_t h=1469598103934665603ULL;
 auto add=[&](const auto &v){const auto *p=reinterpret_cast<const uint8_t*>(&v);for(unsigned i=0;i<sizeof(v);++i){h^=p[i];h*=1099511628211ULL;}};
 add(p.size);add(p.numblks);add(p.bnum);
 for(unsigned i=0;i<p.numblks;++i){add(p.blocks[i]->size);add(p.blocks[i]->data);add(p.blocks[i]->FAD);add(p.blocks[i]->raw_data);}return h;
}
uint64_t partition_image(D &d,unsigned buf){return partition_image(d.partitions[buf]);}
void seed(D &d,unsigned work,unsigned kind,unsigned count){
 const unsigned other=(work+1)%24;d.cr1=0x6003;d.cr2=0x300;d.cmd_set_sector_length();
 if(kind==1){d.filters[other].condtrue=other;d.cr1=0x6400;d.cr2=0;d.cr3=other<<8;d.cr4=count;d.cmd_put_sector_data();d.dataxfer_long_w(0xcafebabe);}
 else if(kind){for(unsigned i=0;i<count;++i)append(d,work,true,0);d.cr1=kind==2?0x6300:0x6100;d.cr2=0;d.cr3=work<<8;d.cr4=count;
  if(kind==2)d.cmd_get_and_delete_sector_data();else d.cmd_get_sector_data();CHECK(d.dataxfer_long_r()==word(0));}
 for(unsigned i=0;i<3&&d.freeblocks;++i)append(d,work,true,0xa5);
 for(unsigned i=0;i<2&&d.freeblocks;++i)append(d,other,true,0x5a);
 d.curdir.resize(4);d.curdir[2].firstfad=1234;d.curdir[2].length=4096;d.curdir[2].file_number=0;
 d.media.type=cdrom_file::CD_TRACK_MODE1_RAW;d.media.bytes[15]=1;
}
void issue(D &d,unsigned work,unsigned fid=2){d.cr1=0x7400;d.cr2=0;d.cr3=(work<<8)|(fid>>16);d.cr4=fid;d.cmd_read_file();}
using Outcome=std::array<int64_t,7>;
Outcome finish(D &d,unsigned work,unsigned kind,unsigned count){
 const unsigned other=(work+1)%24;
 if(kind){
  if(kind==1){d.dataxfer_long_w(0xdeadbeef);CHECK(get_u32be(d.m_put_partition.blocks[0]->data)==0xcafebabe&&get_u32be(d.m_put_partition.blocks[0]->data+4)==0xdeadbeef);}
  else CHECK(d.dataxfer_long_r()==word(4));
  CHECK(d.xferdnum==8);const auto free=d.freeblocks;d.cmd_end_data_transfer();
  CHECK(!d.m_host_transfer_active&&d.freeblocks==free+(kind==2?count:0));
 }
 if(!d.freeblocks){CHECK(kind==1);d.cr1=0x6200;d.cr2=0;d.cr3=other<<8;d.cr4=1;d.cmd_delete_sector_data();}
 d.cd_playdata();d.cd_playdata();
 CHECK(d.media.reads==1&&d.cd_curfad==1235&&d.fadstoplay==1&&d.partitions[work].numblks==1&&d.partitions[work].blocks[0]->FAD==1234);
 return {d.cd_stat,d.cd_curfad,d.fadstoplay,d.freeblocks,d.partitions[other].numblks,d.xferdnum,d.m_host_transfer_active};
}
int main(){unsigned cases=0,replays=0,refusals=0;
 for(unsigned work=0;work<24;++work)for(unsigned kind=0;kind<4;++kind)for(unsigned count:{0U,1U,2U,17U,198U,200U}){
  if((kind==0&&count)||(kind==3&&count!=2)||((kind==1||kind==2)&&(count==0||count==2)))continue;
  auto p=std::make_unique<D>();auto &d=*p;seed(d,work,kind,count);const unsigned other=(work+1)%24;
  const auto keep=partition_image(d,other);const auto free=d.freeblocks;const auto public_count=d.partitions[work].numblks;
  const auto type=d.xfertype32;const auto *owner=d.transpart;const auto cursor=d.xferdnum;
  const auto reservation=kind==1?partition_image(d.m_put_partition):kind==2?partition_image(d.m_get_partition):0;
  issue(d,work);
  if(kind==1)CHECK(d.m_put_partition.numblks==count&&partition_image(d.m_put_partition)==reservation);
  if(kind==2)CHECK(d.m_get_partition.numblks==count&&partition_image(d.m_get_partition)==reservation);
  CHECK(d.freeblocks==free+public_count&&d.buffull==int(d.freeblocks==0)&&!d.partitions[work].numblks&&d.partitions[work].size==-1);
  for(unsigned i=0;i<200;++i)CHECK(!d.partitions[work].blocks[i]&&d.partitions[work].bnum[i]==255);
  CHECK(partition_image(d,other)==keep&&d.xfertype32==type&&d.transpart==owner&&d.xferdnum==cursor&&d.m_host_transfer_active==bool(kind));
  d.register_state();d.capture();const auto expected=finish(d,work,kind,count);
  d.cd_stat=0;d.cd_next_stat=0;d.cd_curfad=88;d.fadstoplay=0;d.m_host_transfer_active=false;d.transpart=nullptr;d.media.reads=0;
  d.restore();CHECK(finish(d,work,kind,count)==expected);++cases;++replays;
 }
 for(unsigned reason=0;reason<4;++reason)for(unsigned work:{0U,7U,23U}){
  auto p=std::make_unique<D>();auto &d=*p;seed(d,work,2,17);const auto own=partition_image(d,work),other=partition_image(d,(work+1)%24);const auto free=d.freeblocks;
  if(reason==2)d.m_file_info_invalidated=true;if(reason==3)d.curdir.clear();
  issue(d,reason==0?24:work,reason==1?99:2);
  CHECK(d.cr1==CD_STAT_REJECT&&d.freeblocks==free&&partition_image(d,work)==own&&partition_image(d,(work+1)%24)==other&&d.m_host_transfer_active&&d.xferdnum==4);++refusals;
 }
 std::printf("method-level, unvalidated: %u Read File/public-clear/private-reservation/host-continuation images; %u registered pool/host/drive replays; %u non-clearing refusal controls\n",cases,replays,refusals);
 std::puts("method-level, unvalidated: actual file admission/clear/allocator/host port/End/drive/filter/read/save methods; mock image/IRQ/serializer, retained metadata outside replay subset; no native FLS/timer/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-read-file-clear-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

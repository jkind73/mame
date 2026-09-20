#!/usr/bin/env python3
"""Directory work-buffer clearing with actual pool/parser and independent host ownership."""
from pathlib import Path
import runpy
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_read_file_clear.py')
scope={'__file__':str(fixture),'__name__':'directory_clear_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers=(scope[k] for k in ('source','head','functions','extract','helpers'))
head='#include <map>\n#include <array>\nconstexpr unsigned MAX_DIR_SIZE=256*1024;\n'+head
head=head.replace('uint8_t bytes[2352]{};', 'uint8_t bytes[2352]{};std::map<unsigned,std::array<uint8_t,2048>> directory;void (*on_read)(unsigned)=nullptr;')
head=head.replace('std::memcpy(to,bytes,sizeof(bytes));', 'if(format==cdrom_file::CD_TRACK_MODE1){if(on_read)on_read(lba+150);std::memcpy(to,directory[lba+150].data(),2048);}else std::memcpy(to,bytes,sizeof(bytes));')
dev=extract(head,'struct saturn_cd_hle_device')
head=head.replace(dev,dev[:-1]+r'''
 direntryT curroot{};int numfiles=0,firstfile=0;
 void cmd_change_directory();void cmd_read_directory();void cd_readblock(uint32_t,uint8_t*);
 void read_new_dir(uint32_t,uint8_t=0xff);void make_dir_current(uint32_t,uint32_t);
}''',1)
head+='\nuint32_t get_u32le(const uint8_t *p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}\nuint16_t get_u16le(const uint8_t *p){return p[0]|(p[1]<<8);}\n'
functions+='\n'+'\n'.join(extract(source,'void saturn_cd_hle_device::'+n+'(') for n in ('cmd_change_directory','cmd_read_directory','read_new_dir','make_dir_current','cd_readblock'))
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)
reserve=fixture.read_text().split("\ntail=r'''",1)[1].split('void issue(',1)[0]
p=Path(__file__).with_name('check_cd_directory_extent.py')
builders=p.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0].replace('d.media[','d.media.directory[')
tail=r'''
D *observed=nullptr;unsigned selected=0,observations=0;
void before_read(unsigned){CHECK(observed&&!observed->partitions[selected].numblks&&observed->partitions[selected].size==-1);++observations;}
void directory(D &d,unsigned action){root(d,2048);child(d,3,6144,2048);if(action==5)d.media.directory[1000][68]=0;
 const auto work=partition_image(d,selected);d.read_new_dir(0xffffff);if(action==2||action==4)d.read_new_dir(2);
 CHECK(partition_image(d,selected)==work);d.media.reads=0;
}
void command(D &d,unsigned work,bool hold,unsigned fid){d.cr1=hold?0x7100:0x7000;d.cr2=0;d.cr3=(work<<8)|(fid>>16);d.cr4=fid;if(hold)d.cmd_read_directory();else d.cmd_change_directory();}
using Outcome=std::array<int64_t,5>;
Outcome finish(D &d,unsigned work,unsigned kind,unsigned count){
 if(kind){
  if(kind==1){d.dataxfer_long_w(0xdeadbeef);CHECK(get_u32be(d.m_put_partition.blocks[0]->data)==0xcafebabe&&get_u32be(d.m_put_partition.blocks[0]->data+4)==0xdeadbeef);}
  else CHECK(d.dataxfer_long_r()==word(4));
  CHECK(d.xferdnum==8);const auto free=d.freeblocks;d.cmd_end_data_transfer();CHECK(!d.m_host_transfer_active&&d.freeblocks==free+(kind==2?count:0));
 }
 return {d.freeblocks,d.partitions[(work+1)%24].numblks,d.xferdnum,d.xfertype32,d.m_host_transfer_active};
}
int main(){unsigned moves=0,holds=0,replays=0,controls=0;
 for(unsigned work=0;work<24;++work)for(unsigned kind=0;kind<4;++kind)for(unsigned count:{0U,1U,2U,17U,198U}){
  if((kind==0&&count)||(kind==3&&count!=2)||((kind==1||kind==2)&&(count==0||count==2)))continue;
  for(unsigned action=0;action<6;++action){auto p=std::make_unique<D>();auto &d=*p;selected=work;seed(d,work,kind,count);directory(d,action);
   const auto keep=partition_image(d,(work+1)%24);const auto free=d.freeblocks;const auto public_count=d.partitions[work].numblks;
   const auto reservation=kind==1?partition_image(d.m_put_partition):kind==2?partition_image(d.m_get_partition):0;
   const auto type=d.xfertype32;const auto *owner=d.transpart;const auto cursor=d.xferdnum;
   const bool hold=action>=3;const unsigned fid=action==0?0xffffff:action==1?2:action==2?1:action==4?3:2;
   observed=&d;d.media.on_read=before_read;command(d,work,hold,fid);d.media.on_read=nullptr;observed=nullptr;
   CHECK(d.freeblocks==free+public_count&&!d.partitions[work].numblks&&d.partitions[work].size==-1);
   CHECK(partition_image(d,(work+1)%24)==keep&&d.xfertype32==type&&d.transpart==owner&&d.xferdnum==cursor&&d.m_host_transfer_active==bool(kind));
   if(kind==1)CHECK(d.m_put_partition.numblks==count&&partition_image(d.m_put_partition)==reservation);
   if(kind==2)CHECK(d.m_get_partition.numblks==count&&partition_image(d.m_get_partition)==reservation);
   CHECK(unsigned(d.media.reads)==(hold?0:action==0?2:action==1?3:1));
   CHECK(d.curdir.size()==(action==1||action==4?5:action==5?2:3)&&d.m_file_scope_start==(action==4?3:2));
   d.register_state();d.capture();const auto expected=finish(d,work,kind,count);d.m_host_transfer_active=false;d.transpart=nullptr;d.restore();CHECK(finish(d,work,kind,count)==expected);
   ++replays;if(hold)++holds;else ++moves;
  }
 }
 for(unsigned reason=0;reason<9;++reason)for(unsigned work:{0U,7U,23U}){
  auto p=std::make_unique<D>();auto &d=*p;selected=work;seed(d,work,2,17);directory(d,0);
  const auto own=partition_image(d,work),other=partition_image(d,(work+1)%24),reservation=partition_image(d.m_get_partition);const auto free=d.freeblocks;
  if(reason==3)d.curdir[2].flags=0;if(reason==4||reason==7)d.m_file_info_invalidated=true;if(reason==8)d.curdir.clear();
  const bool hold=reason>=5;const unsigned input=(reason==1||reason==6)?24:work;
  command(d,input,hold,reason==0?0:reason==2||reason==5?99:2);
  CHECK(d.freeblocks==free&&partition_image(d,work)==own&&partition_image(d,(work+1)%24)==other&&partition_image(d.m_get_partition)==reservation&&d.m_host_transfer_active&&d.xferdnum==4);
  if(reason!=0&&reason!=5)CHECK(d.cr1==CD_STAT_REJECT);++controls;
 }
 std::printf("method-level, unvalidated: %u directory-move and %u hold/public-clear/private-owner images; %u pre-IO empty-partition observations; %u pool/host replays; %u no-clear controls\n",moves,holds,observations,replays,controls);
 std::puts("method-level, unvalidated: actual directory commands/parser/readblock/pool/host/save methods; authored ISO records; metadata retained outside replay subset; no native FLS/scratch-allocation/timing/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-directory-clear-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+reserve+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

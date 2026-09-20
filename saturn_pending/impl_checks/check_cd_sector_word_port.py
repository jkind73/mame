#!/usr/bin/env python3
"""16-bit DATATRNS sector lanes and mixed-width continuations; method-level only."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_info_drive.py')
scope={'__file__':str(fixture),'__name__':'sector_word_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head='using offs_t=unsigned;\n'+head
head=head.replace('bool side_effects_disabled(){return false;}', 'bool suppress=false;bool side_effects_disabled(){return suppress;}')
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+r'''
 u32 datatrns_r(offs_t,uint32_t);void datatrns_w(offs_t,uint32_t,uint32_t);
}''',1)
for sig in ['u32 saturn_cd_hle_device::datatrns_r(', 'void saturn_cd_hle_device::datatrns_w(', 'void saturn_cd_hle_device::cmd_put_sector_data(']:
    if sig not in functions:functions+='\n'+extract(source,sig)
tail=r'''
using D=saturn_cd_hle_device;
unsigned sizes(unsigned kind,unsigned fmt){return fmt==0?(kind==2?2324:2048):fmt==1?2336:fmt==2?2340:2352;}
unsigned offsets(unsigned kind,unsigned fmt){return fmt==0?(kind==0?16:24):fmt==1?16:fmt==2?12:0;}
uint8_t byte(unsigned kind,unsigned pos){if(pos==15)return kind==0?1:2;if(pos==18)return kind==2?0x20:4;return uint8_t(kind*37+pos*11+(pos>>8));}
void seed(D &d,unsigned buf,unsigned kind){for(unsigned n=0;n<3;++n){uint8_t id=255;auto *b=d.cd_alloc_block(&id);CHECK(b);b->raw_data=true;b->size=2352;b->FAD=150+n;
 for(unsigned i=0;i<2352;++i)b->data[i]=byte(kind,i);auto &p=d.partitions[buf];if(p.size<0)p.size=0;p.blocks[p.numblks]=b;p.bnum[p.numblks++]=id;p.size+=2352;}}
void format(D &d,unsigned f,bool put){d.cr1=0x6000|(put?255:f);d.cr2=(put?f:255)<<8;d.cmd_set_sector_length();}
unsigned width(unsigned mode,unsigned pos){return mode<2||pos==0|| (mode==3&&pos%14<6)?2:4;}
uint32_t mask(unsigned mode,unsigned pos,unsigned bytes){return bytes==4?0xffffffff:mode==1|| (mode==3&&pos%4)?0xffff0000:0xffff;}
void read(D &d,const std::vector<uint8_t> &want,unsigned from,unsigned mode){
 for(unsigned pos=from;pos<want.size();){const auto bytes=width(mode,pos),lane=mask(mode,pos,bytes);uint32_t expected=0;
  for(unsigned n=0;n<bytes;++n)expected=(expected<<8)|(pos+n<want.size()?want[pos+n]:255);
  if(lane==0xffff0000)expected<<=16;
  CHECK(d.datatrns_r((pos&2)?1:0,lane)==expected);pos+=std::min<unsigned>(bytes,want.size()-pos);CHECK(d.xferdnum==pos&&d.m_host_transfer_active);
 }
 CHECK(d.xfersect==2&&d.xferoffs==0);CHECK(d.datatrns_r(0,0xffff)==0xffff&&d.xferdnum==want.size());
 d.cmd_end_data_transfer();CHECK(d.cr2==want.size()/2&&!d.m_host_transfer_active);
}
void write(D &d,unsigned total,unsigned from,unsigned mode){for(unsigned pos=from;pos<total;){const auto bytes=width(mode,pos),lane=mask(mode,pos,bytes);uint32_t data=0;
 for(unsigned n=0;n<bytes;++n)data=(data<<8)|uint8_t((pos+n)*7+(pos+n)/257);if(lane==0xffff0000)data<<=16;
 d.datatrns_w((pos&2)?1:0,data,lane);pos+=std::min(bytes,total-pos);CHECK(d.xferdnum==pos&&d.m_host_transfer_active);
 }CHECK(d.xfersect==2&&d.xferoffs==0);d.datatrns_w(0,0xcafe,0xffff);CHECK(d.xferdnum==total);
}
int main(){unsigned gets=0,puts=0,replays=0,controls=0;
 for(unsigned buf=0;buf<24;++buf)for(unsigned kind=0;kind<3;++kind)for(unsigned fmt=0;fmt<4;++fmt)for(unsigned mode=0;mode<4;++mode)for(bool remove:{false,true}){
  auto p=std::make_unique<D>();auto &d=*p;seed(d,buf,kind);format(d,fmt,false);d.cr1=remove?0x6300:0x6100;d.cr2=1;d.cr3=buf<<8;d.cr4=2;if(remove)d.cmd_get_and_delete_sector_data();else d.cmd_get_sector_data();
  std::vector<uint8_t> want;for(unsigned n=0;n<2;++n){const unsigned f=n?(fmt+1)%4:fmt;for(unsigned i=0;i<sizes(kind,f);++i)want.push_back(byte(kind,offsets(kind,f)+i));}
  d.suppress=true;d.datatrns_r(0,0xffff);d.datatrns_r(0,0xffff0000);CHECK(d.xferdnum==0&&d.xferoffs==0);d.suppress=false;
  const auto lane=mask(mode,0,2);const uint32_t first=(want[0]<<8)|want[1];CHECK(d.datatrns_r(0,lane)==(lane==0xffff0000?first<<16:first));CHECK(d.xferdnum==2&&d.xferoffs==2);
  format(d,(fmt+1)%4,false);d.register_state();d.capture();read(d,want,2,mode);CHECK(d.freeblocks==(remove?199:197));
  d.xferoffs=0;d.xferdnum=0;d.m_host_transfer_active=false;d.transpart=nullptr;d.m_xfer_raw_size=0;d.restore();CHECK(d.xferoffs==2&&d.xferdnum==2);read(d,want,2,mode);++gets;++replays;
 }
 for(unsigned buf=0;buf<24;++buf)for(unsigned fmt=0;fmt<4;++fmt)for(unsigned mode=0;mode<4;++mode){auto p=std::make_unique<D>();auto &d=*p;d.filters[buf].condtrue=buf;format(d,fmt,true);
  d.cr1=0x6400;d.cr2=0;d.cr3=buf<<8;d.cr4=2;d.cmd_put_sector_data();CHECK(d.transpart==&d.m_put_partition&&d.freeblocks==198);
  const unsigned s0=fmt==0?2048:sizes(0,fmt),s1=(fmt+1)%4==0?2048:sizes(0,(fmt+1)%4),total=s0+s1;
  const auto lane=mask(mode,0,2);d.datatrns_w(0,lane==0xffff0000?0x00070000:7,lane);CHECK(d.xferdnum==2&&d.xferoffs==2);format(d,(fmt+1)%4,true);d.register_state();d.capture();
  auto finish=[&](){write(d,total,2,mode);for(unsigned n=0;n<2;++n){const auto f=n?(fmt+1)%4:fmt;const unsigned off=f==0?24:2352-sizes(0,f),sz=n?s1:s0;for(unsigned i=0;i<sz;++i){const unsigned pos=(n?s0:0)+i;CHECK(d.m_put_partition.blocks[n]->data[off+i]==uint8_t(pos*7+pos/257));}}
   d.cmd_end_data_transfer();CHECK(d.cr2==total/2&&!d.m_host_transfer_active&&d.partitions[buf].numblks==2&&d.freeblocks==198);};
  finish();d.transpart=nullptr;d.xferoffs=0;d.xferdnum=0;d.m_host_transfer_active=false;d.restore();CHECK(d.xferoffs==2&&d.xferdnum==2);finish();++puts;++replays;
 }
 for(unsigned mode=0;mode<2;++mode){auto p=std::make_unique<D>();auto &d=*p;d.curdir.resize(3);d.curdir[2].firstfad=0x123456;d.curdir[2].length=0x23456;d.cr1=0x7300;d.cr3=0;d.cr4=2;d.cmd_get_target_file_info();
  const unsigned expected[]={0x12,0x3456,2,0x3456,0,0};for(unsigned n=0;n<6;++n)CHECK(d.datatrns_r(0,mode?0xffff0000:0xffff)==(mode?expected[n]<<16:expected[n]));CHECK(d.xferdnum==12);d.cmd_end_data_transfer();CHECK(d.cr2==6);++controls;}
 std::printf("method-level, unvalidated: %u GET/GETDELETE lane/view/mixed-width images; %u PUT lane/view images; %u word-offset registered continuations; %u metadata controls\n",gets,puts,replays,controls);
 std::puts("method-level, unvalidated: actual DATATRNS/commands/ports/pool/filter/End/save methods; mock bus/image/IRQ/serializer; no native aperture, FIFO prefetch/arbitration, byte-lane policy, timing or native save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-sector-word-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

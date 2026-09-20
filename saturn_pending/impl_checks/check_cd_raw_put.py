#!/usr/bin/env python3
"""Actual PUT reservation/writes/filter completion and registered replay; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_sector_views.py')
setup=fixture.read_text().split("\ntail=r'''",1)[0]
scope={'__file__':str(fixture),'__name__':'raw_put_scaffold'}
exec(compile(setup,str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head='#include <cassert>\n'+head
head=head.replace(' void cmd_set_sector_length();',' void cmd_put_sector_data();void cmd_get_sector_information();void cd_connect_cddevice(uint8_t);\n void cmd_set_sector_length();')
functions+='\n'+'\n'.join(extract(source,s) for s in (
 'void saturn_cd_hle_device::cmd_put_sector_data()',
 'void saturn_cd_hle_device::cmd_get_sector_information()',
 'void saturn_cd_hle_device::cd_connect_cddevice('))
tail=r'''
using D=saturn_cd_hle_device;using Raw=std::array<uint8_t,2352>;using Pair=std::array<Raw,2>;
constexpr unsigned lengths[]={2048,2336,2340,2352};
unsigned putoff(unsigned f){return f==0?24:f==1?16:f==2?12:0;}
unsigned getoff(const Raw &r,unsigned f){return f==0?(r[15]==1?16:24):f==1?16:f==2?12:0;}
unsigned getsize(const Raw &r,unsigned f){return f==0?(r[15]==2&&(r[18]&32)?2324:2048):lengths[f];}
void format(D &d,unsigned get,unsigned put){d.cr1=0x6000|get;d.cr2=put<<8;d.cmd_set_sector_length();}
Pair packets(unsigned kind){Pair p;for(unsigned n=0;n<2;++n){
 for(unsigned j=0;j<2352;++j)p[n][j]=uint8_t(j*17+n*37+kind*5);
 p[n][12]=0;p[n][13]=2;p[n][14]=n;p[n][15]=kind==0?1:2;
 p[n][16]=3+n;p[n][17]=9+n;p[n][18]=kind==2?0x20:4;p[n][19]=0x42;
 }return p;}
Pair expected(const Pair &input,unsigned first,unsigned next,unsigned words){Pair out{};
 const unsigned firstwords=lengths[first]/4;
 for(unsigned w=0;w<words;++w){const unsigned n=w>=firstwords,f=n?next:first,pos=putoff(f)+(n?w-firstwords:w)*4;
  std::copy_n(input[n].begin()+pos,4,out[n].begin()+pos);}
 return out;
}
void write(D &d,const Pair &input,unsigned first,unsigned next,unsigned begin,unsigned end){
 const unsigned firstwords=lengths[first]/4;
 for(unsigned w=begin;w<end;++w){const unsigned n=w>=firstwords,f=n?next:first,pos=putoff(f)+(n?w-firstwords:w)*4;
  d.dataxfer_long_w(get_u32be(input[n].data()+pos));}
 CHECK(d.xferdnum==end*4);
}
void seed(D &d,unsigned get,unsigned put){
 format(d,get,put);uint8_t id=255;auto *old=d.cd_alloc_block(&id);CHECK(old&&id==0);
 old->size=2048;old->FAD=77;std::fill(std::begin(old->data),std::end(old->data),0xcc);
 auto &p=d.partitions[7];p.size=2048;p.numblks=1;p.blocks[0]=old;p.bnum[0]=id;
 d.filters[0].condtrue=7;d.cddevicenum=0;d.cddevice=&d.filters[0];d.lastbuf=21;
}
void start(D &d,unsigned count=2,unsigned input=0){
 d.cr1=0x6400;d.cr2=0xfeed;d.cr3=input<<8;d.cr4=count;d.cmd_put_sector_data();
}
void pending(D &d){
 CHECK(d.xfertype32==D::XFERTYPE32_PUTSECTOR&&d.transpart==&d.m_put_partition);
 CHECK(d.m_put_partition.numblks==2&&d.m_put_partition.size==4704&&d.m_put_filter==0);
 CHECK(d.freeblocks==197&&d.partitions[7].numblks==1&&!d.partitions[0].numblks);
 CHECK(d.cddevicenum==0xff&&!d.cddevice&&d.lastbuf==21);
 for(unsigned i=0;i<2;++i){CHECK(d.m_put_partition.bnum[i]==i+1&&d.m_put_partition.blocks[i]==&d.blocks[i+1]);CHECK(d.blocks[i+1].raw_data&&d.blocks[i+1].size==2352);}
}
void end(D &d,unsigned words){
 d.cmd_end_data_transfer();CHECK(d.cr2==words*2&&!(d.cd_stat&CD_STAT_TRANS)&&(d.hirqreg&EHST));
 CHECK(d.xfertype32==D::XFERTYPE32_INVALID&&d.m_put_filter==0xff&&!d.m_put_partition.numblks&&d.m_put_partition.size==-1&&!d.transpart);
 for(unsigned i=0;i<200;++i)CHECK(!d.m_put_partition.blocks[i]&&d.m_put_partition.bnum[i]==0xff);
}
void check(D &d,const Pair &want,unsigned get,bool remove){
 auto &p=d.partitions[7];CHECK(p.numblks==3&&p.size==2048+4704&&d.freeblocks==197&&d.lastbuf==21);
 CHECK(p.bnum[0]==0&&p.blocks[0]->size==2048&&p.blocks[0]->FAD==77);
 for(unsigned i=0;i<2352;++i)CHECK(p.blocks[0]->data[i]==0xcc);
 for(unsigned n=0;n<2;++n){const auto &r=want[n];auto *b=p.blocks[n+1];
  CHECK(b&&b->raw_data&&b->size==2352&&!std::memcmp(b->data,r.data(),2352));
  const unsigned fad=((r[12]>>4)*10+(r[12]&15))*4500+((r[13]>>4)*10+(r[13]&15))*75+(r[14]>>4)*10+(r[14]&15);
  CHECK(b->FAD==fad&&b->fnum==(r[15]==2?r[16]:0)&&b->chan==(r[15]==2?r[17]:0)&&b->subm==(r[15]==2?r[18]:0)&&b->cinf==(r[15]==2?r[19]:0));
  d.cr1=0x5400;d.cr2=n+1;d.cr3=7<<8;d.cmd_get_sector_information();CHECK(d.cr2==fad);
 }
 format(d,get,0xff);d.cr1=0x5200;d.cr2=1;d.cr3=7<<8;d.cr4=2;d.cmd_calculate_actual_data_size();
 const unsigned bytes=getsize(want[0],get)+getsize(want[1],get);CHECK(d.calcsize==bytes/2);
 d.cr1=remove?0x6300:0x6100;d.cr2=1;d.cr3=7<<8;d.cr4=2;if(remove)d.cmd_get_and_delete_sector_data();else d.cmd_get_sector_data();
 for(const auto &r:want)for(unsigned pos=0;pos<getsize(r,get);pos+=4)CHECK(d.dataxfer_long_r()==get_u32be(r.data()+getoff(r,get)+pos));
 CHECK(d.xferdnum==bytes);d.cmd_end_data_transfer();CHECK(d.cr2==bytes/2);
 CHECK(p.numblks==(remove?1:3)&&p.size==(remove?2048:6752)&&d.freeblocks==(remove?199:197));
}
int main(){unsigned views=0,partials=0,replays=0,routes=0,refusals=0;
 for(unsigned kind=0;kind<3;++kind)for(unsigned put=0;put<4;++put)for(unsigned get=0;get<4;++get)for(bool remove:{false,true}){
  auto d=std::make_unique<D>();seed(*d,get,put);const auto input=packets(kind);start(*d);pending(*d);
  const unsigned words=lengths[put]/2;write(*d,input,put,put,0,words);pending(*d);
  d->dataxfer_long_w(0xdeadbeef);CHECK(d->xferdnum==words*4);end(*d,words);
  check(*d,expected(input,put,put,words),get,remove);++views;
 }
 for(unsigned kind=0;kind<3;++kind)for(unsigned put=0;put<4;++put)
 for(unsigned words:{0U,1U,lengths[put]/4-1,lengths[put]/4,lengths[put]/4+1,lengths[put]/2}){
  auto d=std::make_unique<D>();seed(*d,0,put);const auto input=packets(kind);start(*d);write(*d,input,put,put,0,words);pending(*d);end(*d,words);
  check(*d,expected(input,put,put,words),3,true);++partials;
 }
 for(unsigned kind=0;kind<3;++kind)for(unsigned old=0;old<4;++old)for(unsigned next=0;next<4;++next)
 for(unsigned cut:{0U,1U,lengths[old]/8,lengths[old]/4-1,lengths[old]/4}){
  auto d=std::make_unique<D>();seed(*d,0,old);const auto input=packets(kind);const unsigned words=(lengths[old]+lengths[next])/4;
  start(*d);write(*d,input,old,next,0,cut);format(*d,0xff,next);pending(*d);
  d->register_state();d->capture();CHECK(d->m_saved_transpart==24);
  write(*d,input,old,next,cut,words);end(*d,words);check(*d,expected(input,old,next,words),3,true);
  for(auto &b:d->blocks){b={};b.size=-1;std::fill(std::begin(b.data),std::end(b.data),0xee);}
  for(auto &p:d->partitions){p={};std::fill(std::begin(p.bnum),std::end(p.bnum),0xff);}
  d->m_put_partition={};d->m_put_filter=0xff;d->transpart=nullptr;d->sectlenin=d->sectlenout=0;
  d->m_xfer_raw_offset=d->m_xfer_raw_size=0;d->m_xfer_raw_sector=0xffffffff;d->xfertype32=D::XFERTYPE32_INVALID;
  d->freeblocks=200;d->xferdnum=d->xferoffs=d->xfersect=0;const auto irqs=d->irqs;d->restore();CHECK(d->irqs==irqs);pending(*d);
  write(*d,input,old,next,cut,words);end(*d,words);check(*d,expected(input,old,next,words),3,true);++replays;
 }
 for(unsigned route=0;route<4;++route){
  auto d=std::make_unique<D>();seed(*d,0,3);auto input=packets(2);
  d->cddevicenum=5;d->cddevice=&d->filters[5];d->filters[2].condfalse=0;
  if(route==1){d->filters[0].mode=1;d->filters[0].fid=3;d->filters[0].condfalse=1;d->filters[1].condtrue=8;}
  if(route==2)d->filters[0].condtrue=0xff;
  if(route==3){d->filters[0].mode=d->filters[1].mode=1;d->filters[0].fid=d->filters[1].fid=255;d->filters[0].condfalse=1;d->filters[1].condfalse=0;}
  start(*d);CHECK(d->filters[2].condfalse==0xff&&d->cddevicenum==5);write(*d,input,3,3,0,1176);
  d->cd_connect_cddevice(0);end(*d,1176);CHECK(!d->cddevice&&d->cddevicenum==0xff&&d->lastbuf==21);
  CHECK(d->partitions[7].numblks==(route==0?3:route==1?2:1)&&d->partitions[8].numblks==(route==1?1:0));
  CHECK(d->freeblocks==(route<2?197:199));++routes;
 }
 // Capacity/full-width counts and invalid selectors must leave reservations,
 // existing data, input ownership and latched lengths untouched.
 for(unsigned count:{0U,200U,201U,255U,256U,257U,65535U}){
  auto d=std::make_unique<D>();seed(*d,0,0);start(*d,count);CHECK((d->cr1&0x8000)&&d->freeblocks==199&&!d->m_put_partition.numblks&&d->m_put_filter==0xff&&d->cddevicenum==0&&d->cddevice==&d->filters[0]&&d->partitions[7].numblks==1);++refusals;
 }
 for(unsigned input=24;input<256;++input){auto d=std::make_unique<D>();seed(*d,0,0);start(*d,1,input);CHECK(d->cr1==0xff00&&d->freeblocks==199&&d->cddevicenum==0&&!d->m_put_partition.numblks);++refusals;}
 for(bool word:{false,true}){auto d=std::make_unique<D>();seed(*d,0,0);if(word)d->xfertype=D::XFERTYPE_TOC;else d->xfertype32=D::XFERTYPE32_GETSECTOR;
  start(*d);CHECK((d->cr1&0x8000)&&d->freeblocks==199&&!d->m_put_partition.numblks&&d->cddevicenum==0);++refusals;}
 {auto d=std::make_unique<D>();seed(*d,0,0);start(*d);write(*d,packets(0),0,0,0,1);start(*d,1);pending(*d);CHECK(d->xferdnum==4&&(d->cr1&0x8000));++refusals;}
 {auto d=std::make_unique<D>();format(*d,0,0);start(*d,200);CHECK(d->freeblocks==0&&d->buffull&&d->m_put_partition.numblks==200&&!d->partitions[0].numblks);
  end(*d,0);CHECK(d->partitions[0].numblks==200&&d->partitions[0].size==470400&&d->freeblocks==0);
  d->cr1=0x6300;d->cr2=d->cr3=0;d->cr4=200;d->cmd_get_and_delete_sector_data();d->cmd_end_data_transfer();CHECK(d->freeblocks==200&&!d->buffull&&!d->partitions[0].numblks);}
 std::printf("method-level, unvalidated: %u PUT/GET view images; %u partial/zero PUTs; %u registered raw-PUT replays; %u filter routes; %u refusal controls; full-pool release control\n",views,partials,replays,routes,refusals);
 std::puts("method-level, unvalidated: actual reservation/write/End/filter/metadata/GET/size/save methods; mock IRQ/media/serializer; unspecified unwritten bytes zeroed deterministically, no hardware zero-value, native FIFO/timing or overlapping-command qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-raw-put-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
"""CD copy/move command semantics and ownership; method-level, unvalidated."""
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
mock=Path(__file__).with_name('check_cd_filter_routing.py')
head=next(ast.literal_eval(n.value) for n in ast.parse(mock.read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
types='\n'.join(extract(header,s)+';' for s in ('struct filterT','struct blockT','struct partitionT','enum transT','enum trans32T'))
head=head.replace('// TYPES',types)
extra=r'''
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 bool m_host_transfer_active=false;
 int sectorstore=1,cddevicenum=0xff;unsigned irqs=0;
 transT xfertype=XFERTYPE_INVALID;trans32T xfertype32=XFERTYPE32_INVALID;
 void update_hirq(){++irqs;}
 void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
 void cd_defragblocks(partitionT*);void cd_free_block(blockT*);
 void cmd_move_sector_data();void cmd_copy_sector_data();
 void cd_copy_move_sector_data(bool);void cd_disconnect_filter_input(uint8_t);
};
'''
head=head[:head.rfind('};')]+extra
head='#include <vector>\n'+head.replace('#include <cstdint>','#include <cstdint>\nusing u8=uint8_t;')
head+='''\n#define LOGCMD(...) ((void)0)
constexpr unsigned CMOK=1,ECPY=0x100,BFUL=8,CD_STAT_REJECT=0xff00,CD_STAT_WAIT=0x8000;
'''
signatures=[
 'saturn_cd_hle_device::blockT *\nsaturn_cd_hle_device::cd_alloc_block(',
 'void saturn_cd_hle_device::cd_free_block(',
 'void saturn_cd_hle_device::cd_defragblocks(',
 'uint8_t saturn_cd_hle_device::cd_filter_destination(',
 'void saturn_cd_hle_device::cmd_copy_sector_data()',
 'void saturn_cd_hle_device::cmd_move_sector_data()',
]
if 'void saturn_cd_hle_device::cd_copy_move_sector_data(' in source:
    signatures.append('void saturn_cd_hle_device::cd_copy_move_sector_data(')
if 'void saturn_cd_hle_device::cd_disconnect_filter_input(' in source:
    signatures.append('void saturn_cd_hle_device::cd_disconnect_filter_input(')
functions='\n'.join(extract(source,s) for s in signatures)
tail=r'''
using Device=saturn_cd_hle_device;using Block=Device::blockT;
void seed(Device &d,unsigned p,unsigned n){
 auto &part=d.partitions[p];
 for(unsigned i=0;i<n;++i){
  uint8_t id;auto *b=d.cd_alloc_block(&id);CHECK(b);
  b->size=std::initializer_list<int>{2048,2324,2336,2352}.begin()[i%4];
  b->FAD=150+id;b->fnum=i&1;b->chan=id;b->subm=0x15;b->cinf=0x42;
  for(unsigned j=0;j<2352;++j)b->data[j]=uint8_t(id*17+j);
  if(part.size<0)part.size=0;part.size+=b->size;
  part.blocks[part.numblks]=b;part.bnum[part.numblks++]=id;
 }
}
bool equal(const Block &a,const Block &b){return a.size==b.size&&a.FAD==b.FAD&&a.fnum==b.fnum&&a.chan==b.chan&&a.subm==b.subm&&a.cinf==b.cinf&&!std::memcmp(a.data,b.data,2352);}
std::vector<Block> contents(const Device &d,unsigned p){std::vector<Block> v;for(unsigned i=0;i<d.partitions[p].numblks;++i)v.push_back(*d.partitions[p].blocks[i]);return v;}
void expect(const Device &d,unsigned p,const std::vector<Block>&v){CHECK(d.partitions[p].numblks==v.size());for(unsigned i=0;i<v.size();++i)CHECK(equal(*d.partitions[p].blocks[i],v[i]));}
void invariants(const Device &d){
 unsigned owned[200]={},used=0;
 for(const auto &p:d.partitions){
  CHECK(p.numblks<=200);int size=0;
  for(unsigned i=0;i<p.numblks;++i){CHECK(p.bnum[i]<200);CHECK(p.blocks[i]==&d.blocks[p.bnum[i]]);CHECK(!owned[p.bnum[i]]++);CHECK(p.blocks[i]->size>=0);size+=p.blocks[i]->size;}
  CHECK(p.numblks ? p.size==size : p.size==0||p.size==-1);
  for(unsigned i=p.numblks;i<200;++i)CHECK(!p.blocks[i]&&p.bnum[i]==0xff);
 }
 for(unsigned i=0;i<200;++i){CHECK(bool(owned[i])==(d.blocks[i].size>=0));used+=owned[i];}
 CHECK(d.freeblocks==int(200-used));
}
std::unique_ptr<Device> clone(const Device &d){
 auto r=std::make_unique<Device>(d);r->m_cdrom_image=&r->media;
 r->cddevice=r->cddevicenum<24?&r->filters[r->cddevicenum]:nullptr;
 for(auto &p:r->partitions)for(unsigned i=0;i<200;++i)p.blocks[i]=p.bnum[i]<200?&r->blocks[p.bnum[i]]:nullptr;
 return r;
}
void issue(Device &d,bool move,unsigned src,unsigned filter,unsigned offset,unsigned count){d.cr1=(move?0x6600:0x6500)|filter;d.cr2=offset;d.cr3=src<<8;d.cr4=count;if(move)d.cmd_move_sector_data();else d.cmd_copy_sector_data();}
void compare(const Device &a,const Device &b){
 CHECK(a.freeblocks==b.freeblocks&&a.hirqreg==b.hirqreg&&a.cr1==b.cr1&&a.cddevicenum==b.cddevicenum);
 for(unsigned p=0;p<24;++p){expect(b,p,contents(a,p));CHECK(a.filters[p].condfalse==b.filters[p].condfalse);}
 invariants(a);invariants(b);
}
int main(){
 unsigned ranges=0,replays=0,routes=0,waits=0,full=0;
 for(bool move:{false,true})for(unsigned src:{0U,7U,23U})for(bool self:{false,true})
 for(unsigned offset:{0U,1U,4U,0xffffU})for(unsigned count:{1U,2U,0xffffU}){
  const unsigned off=offset==0xffff?4:offset,num=count==0xffff?5-off:count;if(off+num>5)continue;
  const unsigned dst=self?src:(src==7?23:7);auto d=std::make_unique<Device>();seed(*d,src,5);if(!self)seed(*d,dst,3);
  d->filters[2].condtrue=dst;
  // Separate legal CD/false-output producers, plus a legacy dual-connection diagnostic.
  d->filters[19].condfalse=src==0?0xff:2;d->cddevicenum=src==7?0xff:2;
  d->cddevice=d->cddevicenum<24?&d->filters[d->cddevicenum]:nullptr;d->lastbuf=17;
  auto from=contents(*d,src),to=contents(*d,dst);std::vector<Block> selected(from.begin()+off,from.begin()+off+num);
  if(move)from.erase(from.begin()+off,from.begin()+off+num);
  if(self)to=from;to.insert(to.end(),selected.begin(),selected.end());
  auto replay=clone(*d);const int free=d->freeblocks;
  issue(*d,move,src,2,offset,count);issue(*replay,move,src,2,offset,count);
  expect(*d,dst,to);if(!self)expect(*d,src,from);
  CHECK(d->freeblocks==free-(move?0:int(num))&&d->lastbuf==17);
  CHECK(d->cr1==d->cd_stat&&(d->hirqreg&ECPY)&&d->cddevicenum==0xff&&!d->cddevice&&d->filters[19].condfalse==0xff);
  compare(*d,*replay);++ranges;++replays;
 }
 // Source fields split the batch across a true target and a false-chain target,
 // or discard the nonmatching sectors. Copy leaves its source intact.
 for(bool move:{false,true})for(bool discard:{false,true}){
  auto d=std::make_unique<Device>();seed(*d,0,6);auto before=contents(*d,0);
  d->filters[2].mode=1;d->filters[2].fid=1;d->filters[2].condtrue=7;
  d->filters[2].condfalse=discard?0xff:3;d->filters[3].condtrue=8;
  issue(*d,move,0,2,0,0xffff);
  std::vector<Block> odd,even;for(unsigned i=0;i<6;++i)(i&1?odd:even).push_back(before[i]);
  expect(*d,7,odd);if(!discard)expect(*d,8,even);expect(*d,0,move?std::vector<Block>{}:before);
  CHECK(d->freeblocks==(move?(discard?197:194):(discard?191:188)));invariants(*d);++routes;
 }
 // A full buffer can MOVE by ownership transfer; COPY waits atomically.
 for(bool move:{false,true})for(bool self:{false,true}){
  auto d=std::make_unique<Device>();seed(*d,0,200);auto original=contents(*d,0);
  d->filters[2].condtrue=self?0:7;d->cddevicenum=2;d->cddevice=&d->filters[2];
  issue(*d,move,0,2,0,0xffff);
  if(move){expect(*d,self?0:7,original);CHECK(!(d->cr1&CD_STAT_WAIT)&&(d->hirqreg&ECPY));}
  else{expect(*d,0,original);CHECK((d->cr1&CD_STAT_WAIT)&&!(d->hirqreg&ECPY)&&d->cddevicenum==2);}
  CHECK(d->freeblocks==0);invariants(*d);++full;
 }
 for(bool move:{false,true})for(unsigned kind=0;kind<7;++kind){
  auto d=std::make_unique<Device>();seed(*d,0,5);auto original=contents(*d,0);
  unsigned off=0,count=1;
  if(kind==0)count=0;if(kind==1)off=5;if(kind==2){off=4;count=2;}if(kind==3)count=0x100;
  if(kind==4)d->xfertype=d->XFERTYPE_TOC;if(kind==5)d->xfertype32=d->XFERTYPE32_GETSECTOR;
  if(kind==6){off=0xffff;count=2;}
  d->cddevicenum=2;d->cddevice=&d->filters[2];d->filters[19].condfalse=2;
  issue(*d,move,0,2,off,count);expect(*d,0,original);
  CHECK(d->cr1==(d->cd_stat|CD_STAT_WAIT)&&!(d->hirqreg&ECPY)&&d->freeblocks==195);
  CHECK(d->cddevicenum==2&&d->filters[19].condfalse==2);invariants(*d);++waits;
 }
 // Both sentinels on an empty partition wait, not underflow into a huge walk.
 for(bool move:{false,true}){
  auto d=std::make_unique<Device>();issue(*d,move,0,2,0xffff,0xffff);CHECK(d->cr1&CD_STAT_WAIT);invariants(*d);++waits;
  issue(*d,move,24,2,0,1);CHECK(d->cr1==CD_STAT_REJECT&&!(d->hirqreg&ECPY));
  issue(*d,move,0,24,0,1);CHECK(d->cr1==CD_STAT_REJECT&&!(d->hirqreg&ECPY));invariants(*d);
 }
 std::printf("method-level, unvalidated: %u range/self/append cases; %u state-copy replays; %u split/discard routes; %u full-buffer copy/move controls; %u range/overlap WAIT cases; invalid-selector REJECT controls\n",ranges,replays,routes,full,waits);
 std::puts("method-level, unvalidated: actual command/allocation/routing/free/compaction; stubbed response/IRQ; no native timing, async copy error, raw PUT metadata, firmware or save-manager qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-copy-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

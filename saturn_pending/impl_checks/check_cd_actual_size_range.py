#!/usr/bin/env python3
"""Actual-size ranges, atomic held result and host-writing WAIT; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_put.py')
setup=fixture.read_text().split("\ntail=r'''",1)[0]
scope={'__file__':str(fixture),'__name__':'actual_size_scaffold'}
exec(compile(setup,str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head='#include <array>\n'+head
head=head.replace(' uint32_t calcsize=0;', ' uint32_t calcsize=0,seen_size=0;std::array<uint16_t,4> seen{};\n void cmd_get_actual_data_size();')
head=head.replace('void update_hirq(){++irqs;}', 'void update_hirq(){++irqs;seen_size=calcsize;seen={cr1,cr2,cr3,cr4};}')
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_get_actual_data_size()')
tail=r'''
using D=saturn_cd_hle_device;constexpr unsigned lengths[]={2048,2336,2340,2352};
constexpr unsigned prior=3528;
void seed(D &d,unsigned partition,unsigned n){auto &p=d.partitions[partition];p.numblks=n;p.size=n*2352;d.freeblocks=200-n;
 for(unsigned i=0;i<200;++i){auto &b=d.blocks[i];b.size=2352;b.raw_data=true;b.FAD=150+i;b.data[15]=i%3==0?1:2;b.data[18]=i%3==2?0x20:4;p.bnum[i]=i;p.blocks[i]=&b;}
}
void issue(D &d,unsigned p,unsigned o,unsigned n){d.cr1=0x5200;d.cr2=o;d.cr3=(p<<8)|0xa5;d.cr4=n;d.cmd_calculate_actual_data_size();}
void held(D &d,unsigned value){auto causes=d.hirqreg;d.cmd_get_actual_data_size();CHECK(((uint32_t(d.cr1&255)<<16)|d.cr2)==value&&d.hirqreg==(causes|CMOK));}
int main(){unsigned ranges=0,invalid=0,guards=0;
 for(unsigned p=0;p<24;++p)for(unsigned n:{0U,1U,2U,3U,17U,199U,200U}){
  auto d=std::make_unique<D>();seed(*d,p,n);
  for(unsigned format=0;format<4;++format)for(unsigned offset:{0U,1U,2U,16U,17U,198U,199U,200U,255U,256U,257U,65534U,65535U})
  for(unsigned count:{0U,1U,2U,3U,16U,17U,198U,199U,200U,255U,256U,257U,65534U,65535U})
  for(unsigned pending:{0U,unsigned(ESEL),0x201U,0xffffU}){
   const unsigned o=offset==65535?(n?n-1:0):offset;
   const unsigned c=count==65535?(o<n?n-o:0):count;
   const bool valid=c&&o<n&&c<=n-o;unsigned expected=prior;
   if(valid){expected=0;for(unsigned j=0;j<c;++j)expected+=format==0?((o+j)%3==2?1162:1024):lengths[format]/2;}
   d->sectlenin=lengths[format];d->calcsize=prior;d->hirqreg=pending;const auto irqs=d->irqs;issue(*d,p,offset,count);
   CHECK(d->calcsize==expected&&d->seen_size==expected&&d->cr1==(valid?d->cd_stat:d->cd_stat|CD_STAT_WAIT));
   CHECK(d->hirqreg==(pending|CMOK|(valid?ESEL:0))&&d->irqs==irqs+1);
   CHECK((d->seen==std::array<uint16_t,4>{d->cr1,d->cr2,d->cr3,d->cr4}));
   CHECK(d->partitions[p].numblks==n&&d->partitions[p].size==n*2352&&d->freeblocks==200-int(n));held(*d,expected);++ranges;
  }
 }
 for(unsigned p=24;p<256;++p)for(unsigned pending:{0U,unsigned(ESEL),0xffffU}){
  auto d=std::make_unique<D>();d->calcsize=prior;d->hirqreg=pending;issue(*d,p,0,1);
  CHECK(d->cr1==CD_STAT_REJECT&&d->calcsize==prior&&d->hirqreg==(pending|CMOK)&&d->freeblocks==200);held(*d,prior);++invalid;
 }
 // Malformed ownership guards must not publish the first sector's partial sum.
 for(unsigned damage=0;damage<5;++damage){auto d=std::make_unique<D>();seed(*d,0,2);d->calcsize=prior;d->hirqreg=0;
  if(damage==0)d->partitions[0].blocks[1]=nullptr;
  if(damage==1)d->partitions[0].bnum[1]=255;
  if(damage==2)d->partitions[0].blocks[1]=&d->blocks[0];
  if(damage==3)d->blocks[1].size=-1;
  if(damage==4)d->blocks[1].size=2353;
  issue(*d,0,0,2);CHECK(d->cr1==(d->cd_stat|CD_STAT_WAIT)&&d->calcsize==prior&&d->hirqreg==CMOK);++guards;
 }
 {auto d=std::make_unique<D>();seed(*d,0,2);d->partitions[0].numblks=201;d->calcsize=prior;issue(*d,0,0,1);CHECK(d->calcsize==prior&&(d->cr1&CD_STAT_WAIT));++guards;}
 // Native PUT setup/EOF/End and GET coexistence, with coherent real pool IDs.
 {auto d=std::make_unique<D>();auto &p=d->partitions[3];p.numblks=2;p.size=4704;
  for(unsigned i=0;i<2;++i){auto *b=d->cd_alloc_block(&p.bnum[i]);CHECK(b);b->size=2352;b->raw_data=true;b->data[15]=1;p.blocks[i]=b;}
  d->sectlenin=2352;d->calcsize=prior;d->cr1=0x6400;d->cr2=0;d->cr3=7<<8;d->cr4=1;d->cmd_put_sector_data();
  for(bool eof:{false,true}){if(eof)for(unsigned w=0;w<512;++w)d->dataxfer_long_w(w);
   d->hirqreg=0;const auto bytes=d->xferdnum;issue(*d,3,0,2);CHECK(d->calcsize==prior&&d->cr1==(d->cd_stat|CD_STAT_WAIT)&&d->hirqreg==CMOK&&d->xferdnum==bytes&&d->m_put_partition.numblks==1);++guards;}
  d->cmd_end_data_transfer();issue(*d,3,0,2);CHECK(d->calcsize==2352&&!(d->cr1&CD_STAT_WAIT));
  d->cr1=0x6100;d->cr2=0;d->cr3=3<<8;d->cr4=2;d->cmd_get_sector_data();d->dataxfer_long_r();
  const auto bytes=d->xferdnum;issue(*d,3,0,2);CHECK(d->calcsize==2352&&!(d->cr1&CD_STAT_WAIT)&&d->m_host_transfer_active&&d->xferdnum==bytes);++guards;
 }
 std::printf("method-level, unvalidated: %u logical-range/END/view/pending-cause images; %u invalid-selector controls; %u ownership/PUT-WAIT/GET coexistence controls\n",ranges,invalid,guards);
 std::puts("method-level, unvalidated: actual calculation/getter/transfer methods; unused slots and malformed ownership are storage diagnostics; native partition-output/MPEG disconnection, asynchronous calculation latency and full WAIT report qualification excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-actual-size-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

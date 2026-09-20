#!/usr/bin/env python3
"""Filesystem abort versus independent host transfers; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_put.py')
setup=fixture.read_text().split("\ntail=r'''",1)[0]
scope={'__file__':str(fixture),'__name__':'file_abort_scaffold'}
exec(compile(setup,str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head='#include <array>\nusing u16=unsigned short;\n'+head
head=head.replace(' void cmd_put_sector_data();','''
 uint16_t cd_next_stat=0;bool m_status_change_in_progress=false;int m_seek_ticks_left=9;
 uint32_t xfercount=0;std::array<uint16_t,4> seen{};
 void cd_change_status(uint16_t);void cmd_abort_file();
 void cmd_put_sector_data();''')
head=head.replace('void update_hirq(){++irqs;}', 'void update_hirq(){++irqs;seen={cr1,cr2,cr3,cr4};}')
head+='''\n#define LOGSTATUS(...) ((void)0)
constexpr unsigned EFLS=0x200,CD_STAT_BUSY=0,CD_STAT_PAUSE=0x100,CD_STAT_SEEK=0x400,CD_STAT_NODISC=0x700,CD_STAT_OPEN=0x600,CD_STAT_PERI=0x2000;
'''
functions+='\n'+'\n'.join(extract(source,s) for s in (
 'void saturn_cd_hle_device::cmd_abort_file()',
 'void saturn_cd_hle_device::cd_change_status('))
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_audio_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using D=saturn_cd_hle_device;
void abort(D &d){d.cr1=0x7500;d.cmd_abort_file();}
void put(D &d){d.filters[0].condtrue=7;d.cr1=0x6400;d.cr2=d.cr3=0;d.cr4=2;d.cmd_put_sector_data();}
uint32_t value(unsigned n){return 0xa55a0000^n;}
int main(){unsigned flags=0,streams=0;
 auto d=std::make_unique<D>();
 for(unsigned status:{0x4300U,0x4600U,0x4700U})for(bool word:{false,true})for(unsigned pending=0;pending<65536;++pending){
  d->cd_stat=status;d->hirqreg=pending;d->sectorstore=1;d->xferdnum=68;d->xfercount=4;d->xferoffs=4;d->xfersect=1;
  d->xfertype=word?D::XFERTYPE_TOC:D::XFERTYPE_INVALID;d->xfertype32=word?D::XFERTYPE32_INVALID:D::XFERTYPE32_GETSECTOR;
  const auto kind=d->xfertype;const auto kind32=d->xfertype32;d->m_status_change_in_progress=false;d->cd_next_stat=0x4400;
  const auto irqs=d->irqs;abort(*d);
  CHECK(d->xfertype==kind&&d->xfertype32==kind32&&d->xferdnum==68&&d->xfercount==4&&d->xferoffs==4&&d->xfersect==1&&d->sectorstore==1);
  CHECK(d->hirqreg==(pending|CMOK|EFLS)&&d->irqs==irqs+1);
  CHECK((d->seen==std::array<uint16_t,4>{d->cr1,d->cr2,d->cr3,d->cr4}));
  CHECK(d->m_status_change_in_progress==(status==0x4300)&&d->cd_next_stat==(status==0x4300?CD_STAT_PAUSE:0x4400)&&d->m_seek_ticks_left==9);++flags;
 }
 for(unsigned cut:{0U,1U,511U,512U,513U,1024U})for(unsigned mode=0;mode<3;++mode){
  auto d=std::make_unique<D>();put(*d);
  if(mode==0){
   for(unsigned w=0;w<cut;++w)d->dataxfer_long_w(value(w));
   const auto *part=d->transpart;abort(*d);CHECK(d->xfertype32==D::XFERTYPE32_PUTSECTOR&&d->transpart==part&&d->xferdnum==cut*4&&d->m_put_partition.numblks==2);
   for(unsigned w=cut;w<1024;++w)d->dataxfer_long_w(value(w));d->cmd_end_data_transfer();CHECK(d->cr2==2048);
   for(unsigned n=0;n<2;++n)for(unsigned w=0;w<512;++w)CHECK(get_u32be(d->partitions[7].blocks[n]->data+24+w*4)==value(n*512+w));
  }else{
   for(unsigned w=0;w<1024;++w)d->dataxfer_long_w(value(w));d->cmd_end_data_transfer();
   d->cr1=mode==1?0x6100:0x6300;d->cr2=0;d->cr3=7<<8;d->cr4=2;if(mode==1)d->cmd_get_sector_data();else d->cmd_get_and_delete_sector_data();
   for(unsigned w=0;w<cut;++w)CHECK(d->dataxfer_long_r()==value(w));
   const auto kind=d->xfertype32;const auto *part=d->transpart;const auto free=d->freeblocks;
   abort(*d);CHECK(d->xfertype32==kind&&d->transpart==part&&d->xferdnum==cut*4&&d->freeblocks==free&&d->partitions[7].numblks==2&&d->filters[0].condtrue==7);
   for(unsigned w=cut;w<1024;++w)CHECK(d->dataxfer_long_r()==value(w));d->cmd_end_data_transfer();CHECK(d->cr2==2048);
   CHECK(d->freeblocks==(mode==1?198:200)&&d->partitions[7].numblks==(mode==1?2:0));
  }++streams;
 }
 std::printf("method-level, unvalidated: %u abort status/pending-cause/cursor images; %u live raw PUT/GET/GETDELETE continuations across six cuts\n",flags,streams);
 std::puts("method-level, unvalidated: actual abort/status transition and host transfer methods; mock IRQ/report/media, not native pause latency, filesystem held-table invalidation or gameplay qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-abort-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

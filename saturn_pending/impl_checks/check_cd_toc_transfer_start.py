#!/usr/bin/env python3
"""TOC preparation versus transfer activation, actual methods; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_put.py')
setup=fixture.read_text().split("\ntail=r'''",1)[0]
scope={'__file__':str(fixture),'__name__':'toc_start_scaffold'}
exec(compile(setup,str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace(' struct Media {',''' struct Media {
 bool inserted=true;int tracks=2;bool exists(){return inserted;}int get_last_track(){return tracks;}
 int get_track_start(int n){return n==0xaa?tracks*2000:n*2000;}''')
head=head.replace(' void cmd_put_sector_data();','''
 uint8_t tocbuf[408]{};uint32_t xfercount=0;
 int sega_cdrom_get_adr_control(int){return 0x41;}void cd_change_status(uint16_t status){cd_stat=status;}
 void cd_readTOC();void cmd_get_toc();void cmd_get_session_info();
 void cmd_put_sector_data();''')
head+='''\nconstexpr unsigned CD_STAT_PAUSE=0x100;
uint16_t get_u16be(const uint8_t *p){return unsigned(p[0])<<8|p[1];}
void put_u24be(uint8_t *p,uint32_t data){p[0]=data>>16;p[1]=data>>8;p[2]=data;}
'''
functions+='\n'+'\n'.join(extract(source,s) for s in (
 'void saturn_cd_hle_device::cd_readTOC(void)',
 'void saturn_cd_hle_device::cmd_get_toc()',
 'void saturn_cd_hle_device::cmd_get_session_info()'))
tail=r'''
using D=saturn_cd_hle_device;
int main(){unsigned queries=0,starts=0,puts=0;
 for(bool media:{false,true})for(unsigned tracks:{1U,2U,99U})for(unsigned session:{0U,1U,2U,99U,255U})
 for(auto type:{D::XFERTYPE_INVALID,D::XFERTYPE_TOC,D::XFERTYPE_FILEINFO_1,D::XFERTYPE_FILEINFO_254,D::XFERTYPE_SUBQ,D::XFERTYPE_SUBRW})
 for(unsigned cut:{0U,2U,10U,200U,406U}){
  auto d=std::make_unique<D>();d->media.inserted=media;d->media.tracks=tracks;d->xfertype=type;d->xfercount=cut;d->xferdnum=68;
  d->xfertype32=type==D::XFERTYPE_INVALID?D::XFERTYPE32_GETSECTOR:D::XFERTYPE32_INVALID;
  const auto kind32=d->xfertype32;d->xferoffs=12;d->xfersect=2;d->m_xfer_raw_size=2048;d->m_xfer_raw_offset=24;d->m_xfer_raw_sector=2;
  d->hirqreg=0x8c04;d->cr1=0x0300|session;d->cmd_get_session_info();
  CHECK(d->xfertype==type&&d->xfercount==cut&&d->xferdnum==68&&d->xfertype32==kind32);
  CHECK(d->xferoffs==12&&d->xfersect==2&&d->m_xfer_raw_size==2048&&d->m_xfer_raw_offset==24&&d->m_xfer_raw_sector==2);
  CHECK(d->hirqreg==(0x8c04|CMOK)&&d->irqs==1);++queries;
 }
 for(bool media:{false,true})for(unsigned tracks:{1U,2U,99U}){
  auto d=std::make_unique<D>();d->media.inserted=media;d->media.tracks=tracks;d->xfercount=206;d->xferdnum=876;d->cr1=0x0200;
  d->cmd_get_toc();CHECK(d->xfertype==D::XFERTYPE_TOC&&d->xfercount==0&&d->xferdnum==0);
  CHECK(d->cr2==204&&(d->cd_stat&CD_STAT_TRANS)&&d->hirqreg==(CMOK|DRDY)&&d->irqs==1);++starts;
 }
 for(unsigned session:{0U,1U})for(unsigned tracks:{1U,2U,99U}){
  auto d=std::make_unique<D>();d->media.tracks=tracks;d->cr1=0x0300|session;d->cmd_get_session_info();
  d->cr1=0x6400;d->cr2=d->cr3=0;d->cr4=1;d->cmd_put_sector_data();
  CHECK(d->xfertype==D::XFERTYPE_INVALID&&d->xfertype32==D::XFERTYPE32_PUTSECTOR&&d->m_put_partition.numblks==1&&d->freeblocks==199&&!(d->cr1&0x8000));
  d->cmd_end_data_transfer();CHECK(d->partitions[0].numblks==1&&d->cr2==0);++puts;
 }
 std::printf("method-level, unvalidated: %u session-query cursor images; %u explicit TOC starts; %u session-then-PUT reservations\n",queries,starts,puts);
 std::puts("method-level, unvalidated: actual TOC builder/query/start/PUT methods, mock media/status callback; cursor poison and absent-media cases are storage diagnostics; session metadata/status/timing remain separate");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-toc-start-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

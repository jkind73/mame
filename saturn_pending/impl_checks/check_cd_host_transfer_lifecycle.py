#!/usr/bin/env python3
"""Outstanding host-transfer ownership through EOF, DataEnd, save and reset; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
fixture=Path(__file__).with_name('check_cd_toc_transfer_start.py')
setup=fixture.read_text().split("\ntail=r'''",1)[0]
scope={'__file__':str(fixture),'__name__':'host_lifecycle_scaffold'}
exec(compile(setup,str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
extra=extract(header,'struct direntryT')+''';
 std::vector<direntryT> curdir;uint8_t subqbuf[10]{},subrwbuf[24]{},finfbuf[256]{};
 uint8_t playtype=0,cdda_repeat_count=0;
 int get_track_index(int){return 1;}
 uint16_t dataxfer_word_r();void cmd_get_subcode_q_rw_channel();void cmd_get_target_file_info();void cmd_abort_file();
 std::array<uint16_t,4> seen{};bool seen_active=false;
'''
head='#include <array>\n#include <stdexcept>\nusing emu_fatalerror=std::runtime_error;using u16=unsigned short;\n'+head
head=head.replace(' struct Media {',extra+'\n struct Media {')
head=head.replace('int get_track(int lba){return lba;}', 'int get_track(int){return 0;}')
head=head.replace('void update_hirq(){++irqs;}', 'void update_hirq(){++irqs;seen={cr1,cr2,cr3,cr4};seen_active=m_host_transfer_active;}')
head+='''\nconstexpr unsigned EFLS=0x200,CD_STAT_NODISC=0x700,CD_STAT_OPEN=0x600;
uint32_t dec_2_bcd(uint32_t v){return ((v/10)<<4)|(v%10);}
namespace cdrom_file {uint32_t lba_to_msf_alt(uint32_t lba){return ((lba/4500)<<16)|(((lba/75)%60)<<8)|(lba%75);}}
'''
functions+='\n'+'\n'.join(extract(source,s) for s in (
 'inline u16 saturn_cd_hle_device::dataxfer_word_r()',
 'void saturn_cd_hle_device::cmd_get_subcode_q_rw_channel()',
 'void saturn_cd_hle_device::cmd_get_target_file_info()',
 'void saturn_cd_hle_device::cmd_abort_file()'))
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using D=saturn_cd_hle_device;
void seed(D &d){uint8_t id=255;auto *b=d.cd_alloc_block(&id);CHECK(id==0&&b);b->size=2352;b->raw_data=true;b->FAD=150;
 for(unsigned j=0;j<2352;++j)b->data[j]=uint8_t(j*3);b->data[15]=1;
 auto &p=d.partitions[0];p.size=2352;p.numblks=1;p.bnum[0]=id;p.blocks[0]=b;
 d.curdir.resize(1);d.curdir[0].firstfad=150;d.curdir[0].length=2048;d.playtype=3;d.cdda_repeat_count=4;
 d.cddevicenum=3;d.cddevice=&d.filters[3];d.filters[4].condfalse=0;
}
void request(D &d,unsigned kind){d.cr1=d.cr2=d.cr3=d.cr4=0;
 switch(kind){
 case 0:d.cr1=0x0200;d.cmd_get_toc();break;
 case 1:case 2:d.cr1=0x2000|(kind-1);d.cmd_get_subcode_q_rw_channel();break;
 case 3:d.cr1=0x7300;d.cmd_get_target_file_info();break;
 case 4:d.cr1=0x6100;d.cr4=1;d.cmd_get_sector_data();break;
 case 5:d.cr1=0x6300;d.cr4=1;d.cmd_get_and_delete_sector_data();break;
 case 6:d.cr1=0x6400;d.cr4=1;d.cmd_put_sector_data();break;
 case 7:d.cr1=0x6501;d.cr4=1;d.cmd_copy_sector_data();break;
 case 8:d.cr1=0x6601;d.cr4=1;d.cmd_move_sector_data();break;
 }
}
unsigned units(unsigned kind){return kind==0?204:kind==1?5:kind==2?12:kind==3?6:512;}
void consume(D &d,unsigned kind,unsigned count){for(unsigned i=0;i<count;++i){if(kind<4)d.dataxfer_word_r();else if(kind<6)d.dataxfer_long_r();else d.dataxfer_long_w(0xa55a0000^i);}}
uint64_t image(const D &d){uint64_t h=1469598103934665603ULL;
 auto add=[&](const auto &v){const auto *p=reinterpret_cast<const uint8_t*>(&v);for(unsigned i=0;i<sizeof(v);++i){h^=p[i];h*=1099511628211ULL;}};
 add(d.m_host_transfer_active);add(d.xfertype);add(d.xfertype32);add(d.xfercount);add(d.xferoffs);add(d.xfersect);add(d.xfersectpos);add(d.xfersectnum);add(d.xferdnum);
 add(d.m_xfer_raw_offset);add(d.m_xfer_raw_size);add(d.m_xfer_raw_sector);add(d.sectlenin);add(d.sectlenout);add(d.cd_stat);
 add(d.freeblocks);add(d.buffull);add(d.sectorstore);add(d.lastbuf);add(d.cddevicenum);add(d.transpart);add(d.cddevice);
 add(d.playtype);add(d.cdda_repeat_count);add(d.tocbuf);add(d.subqbuf);add(d.subrwbuf);add(d.finfbuf);
 for(const auto &b:d.blocks){add(b.size);add(b.FAD);add(b.data);add(b.raw_data);add(b.fnum);add(b.chan);add(b.subm);add(b.cinf);}
 for(const auto &p:d.partitions){add(p.size);add(p.numblks);add(p.bnum);}
 for(const auto &f:d.filters){add(f.mode);add(f.fad);add(f.range);add(f.condtrue);add(f.condfalse);add(f.chan);add(f.fid);add(f.smmask);add(f.smval);add(f.cimask);add(f.cival);}
 add(d.m_put_filter);add(d.m_put_partition.size);add(d.m_put_partition.numblks);add(d.m_put_partition.bnum);return h;
}
int main(){unsigned refusals=0,ends=0,replays=0;
 for(unsigned active=0;active<7;++active)for(unsigned phase=0;phase<3;++phase){
  auto d=std::make_unique<D>();seed(*d);request(*d,active);CHECK(d->m_host_transfer_active&&d->seen_active);
  consume(*d,active,phase==0?0:phase==1?units(active)/2:units(active));
  if(phase==2)consume(*d,active,1); // drained readers may clear their interface type, but not ownership
  CHECK(d->m_host_transfer_active);
  const uint64_t expected=image(*d);
  for(unsigned candidate=0;candidate<9;++candidate)for(unsigned pending:{0U,unsigned(DRDY),0xffffU}){
   d->hirqreg=pending;const auto irqs=d->irqs;request(*d,candidate);
   CHECK(d->cr1==(d->cd_stat|CD_STAT_WAIT)&&d->hirqreg==(pending|CMOK)&&d->irqs==irqs+1);
   CHECK((d->seen==std::array<uint16_t,4>{d->cr1,d->cr2,d->cr3,d->cr4})&&d->seen_active);
   CHECK(image(*d)==expected);++refusals;
  }
  d->cmd_end_data_transfer();CHECK(!d->m_host_transfer_active);request(*d,0);CHECK(d->m_host_transfer_active&&d->cr2==204&&!(d->cr1&CD_STAT_WAIT));d->cmd_end_data_transfer();++ends;
 }
 // Saved ownership must survive even after the word interface itself goes idle.
 for(unsigned active=0;active<4;++active){
  auto d=std::make_unique<D>();seed(*d);request(*d,active);consume(*d,active,units(active));
  CHECK(d->xfertype==D::XFERTYPE_INVALID&&d->m_host_transfer_active);d->register_state();d->capture();
  d->cmd_end_data_transfer();CHECK(!d->m_host_transfer_active);const auto irqs=d->irqs;d->restore();
  CHECK(d->m_host_transfer_active&&d->xfertype==D::XFERTYPE_INVALID&&d->irqs==irqs);
  request(*d,6);CHECK(d->cr1==(d->cd_stat|CD_STAT_WAIT)&&d->freeblocks==199&&!d->m_put_partition.numblks);
  d->cmd_end_data_transfer();CHECK(!d->m_host_transfer_active);request(*d,6);CHECK(d->m_host_transfer_active&&d->m_put_partition.numblks==1);d->cmd_end_data_transfer();++replays;
 }
 // Session Info and Abort File are not replacement host transfers.
 for(unsigned active=0;active<7;++active){auto d=std::make_unique<D>();seed(*d);request(*d,active);consume(*d,active,units(active));
  d->cr1=0x0300;d->cmd_get_session_info();CHECK(d->m_host_transfer_active);
  d->cr1=0x7500;d->cmd_abort_file();CHECK(d->m_host_transfer_active);request(*d,6);CHECK(d->cr1==(d->cd_stat|CD_STAT_WAIT));d->cmd_end_data_transfer();CHECK(!d->m_host_transfer_active);
 }
 std::printf("method-level, unvalidated: %u replacement-start/copy/move refusals; %u DataEnd release controls; %u registered EOF ownership replays; seven query/Abort File coexistence controls\n",refusals,ends,replays);
 std::puts("method-level, unvalidated: actual host-start/word/long/End/save methods; mocked report/media/serializer; no native FIFO, soft-init cancellation or timing qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-host-lifecycle-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
# Separate real device_reset scaffold; existing reset assertions stay unchanged.
fixture=Path(__file__).with_name('check_cd_selector_reset.py')
scope={'__file__':str(fixture),'__name__':'host_reset_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
tail=r'''
int main(){unsigned resets=0;
 for(unsigned input=0;input<24;++input)for(unsigned count:{1U,200U})for(bool media:{false,true}){
  auto d=std::make_unique<saturn_cd_hle_device>();d->media.inserted=media;
  d->m_host_transfer_active=true;d->xfertype32=d->XFERTYPE32_PUTSECTOR;d->transpart=&d->m_put_partition;
  d->m_put_filter=input;d->m_put_partition.numblks=count;d->m_put_partition.size=count*2352;d->freeblocks=200-count;
  for(unsigned i=0;i<count;++i){d->blocks[i].size=2352;d->blocks[i].raw_data=true;d->m_put_partition.bnum[i]=i;d->m_put_partition.blocks[i]=&d->blocks[i];}
  d->xfercount=3;d->xferoffs=4;d->xfersect=1;d->xfersectpos=7;d->xfersectnum=count;d->xferdnum=0x123456;
  d->m_xfer_raw_offset=24;d->m_xfer_raw_size=2048;d->m_xfer_raw_sector=0;
  d->device_reset();
  CHECK(!d->m_host_transfer_active&&d->xfertype==d->XFERTYPE_INVALID&&d->xfertype32==d->XFERTYPE32_INVALID&&!d->transpart);
  CHECK(!d->xfercount&&!d->xferoffs&&!d->xfersect&&!d->xfersectpos&&!d->xfersectnum&&!d->xferdnum);
  CHECK(!d->m_xfer_raw_offset&&!d->m_xfer_raw_size&&d->m_xfer_raw_sector==0xffffffff);
  CHECK(d->m_put_filter==0xff&&!d->m_put_partition.numblks&&d->m_put_partition.size==-1&&d->freeblocks==200&&d->irqs==1);
  for(unsigned i=0;i<200;++i)CHECK(!d->m_put_partition.blocks[i]&&d->m_put_partition.bnum[i]==0xff&&!d->blocks[i].raw_data&&d->blocks[i].size==-1);++resets;
 }
 std::printf("method-level, unvalidated: %u hard-reset host/pending-PUT/cursor images; existing callback and full-pool release controls\n",resets);
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-host-reset-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(scope['head']+scope['functions']+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
"""Abort File must not auto-resume after capacity release; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_buffer_reset_resume.py')
scope={'__file__':str(fixture),'__name__':'abort_resume_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers=(scope[k] for k in ('source','head','functions','extract','helpers'))
head=head.replace(' void cmd_reset_selector();', ' void cmd_abort_file();void cmd_reset_selector();')
head+='\nconstexpr unsigned CD_STAT_OPEN=0x600,CD_STAT_NODISC=0x700;\n'
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_abort_file()')
tail=r'''
uint64_t storage(const D &d){uint64_t h=1469598103934665603ULL;
 auto add=[&](const auto &v){const auto *p=reinterpret_cast<const uint8_t*>(&v);for(unsigned i=0;i<sizeof(v);++i){h^=p[i];h*=1099511628211ULL;}};
 for(const auto &f:d.filters){add(f.mode);add(f.chan);add(f.smmask);add(f.cimask);add(f.fid);add(f.smval);add(f.cival);add(f.condtrue);add(f.condfalse);add(f.fad);add(f.range);}
 for(const auto &p:d.partitions){add(p.size);add(p.numblks);add(p.bnum);}
 for(const auto &b:d.blocks){add(b.size);add(b.FAD);add(b.data);add(b.raw_data);add(b.chan);add(b.fnum);add(b.subm);add(b.cinf);}
 add(d.cddevicenum);add(d.lastbuf);add(d.sectorstore);add(d.m_put_filter);return h;
}
uint32_t word(unsigned pos){uint32_t v=0;for(unsigned i=0;i<4;++i)v=(v<<8)|byte(0,pos+i);return v;}
void clear(D &d){d.cr1=0x4804;d.cr3=7<<8;d.cmd_reset_selector();}
void ticks(D &d,unsigned remaining){for(unsigned n=0;n<8;++n)d.cd_playdata();
 CHECK(d.cd_stat==CD_STAT_PAUSE&&d.cd_curfad==1234&&d.fadstoplay==remaining&&!d.media.reads);
}
using Outcome=std::array<int64_t,7>;
Outcome finish(D &d,unsigned kind,unsigned count,bool discarded,bool cleared,unsigned remaining){
 if(!cleared)clear(d);ticks(d,remaining);
 CHECK(d.freeblocks==200-((kind==1||kind==2)?count:0));
 if(kind){
  const auto free=d.freeblocks;
  if(kind==1){d.dataxfer_long_w(0xdeadbeef);CHECK(d.xferdnum==8);
   CHECK(get_u32be(d.m_put_partition.blocks[0]->data)==0xcafebabe&&get_u32be(d.m_put_partition.blocks[0]->data+4)==0xdeadbeef);}
  else CHECK(d.dataxfer_long_r()==word(4)&&d.xferdnum==8);
  d.cmd_end_data_transfer();CHECK(!d.m_host_transfer_active);
  CHECK(d.freeblocks==free+((kind==2||(kind==1&&discarded))?count:0));ticks(d,remaining);
  if(kind==1&&!discarded){CHECK(d.partitions[0].numblks==count);d.cr1=0x6200;d.cr2=d.cr3=0;d.cr4=0xffff;d.cmd_delete_sector_data();ticks(d,remaining);}
 }
 CHECK(d.freeblocks==200&&!d.buffull&&!d.m_host_transfer_active);
 return {d.cd_stat,d.cd_curfad,d.fadstoplay,d.freeblocks,d.hirqreg,d.xferdnum,d.xfertype32};
}
int main(){unsigned cases=0,replays=0,controls=0;
 for(unsigned kind=0;kind<4;++kind)for(unsigned count:{0U,1U,2U,17U,199U,200U}){
  if((kind==0&&count!=0)||(kind==3&&count!=2)||((kind==1||kind==2)&&(count==0||count==2)))continue;
  for(bool discard:{false,true}){if(kind!=1&&discard)continue;
   for(unsigned state:{CD_STAT_PAUSE,CD_STAT_PLAY,CD_STAT_SEEK,CD_STAT_BUSY})for(bool automatic:{false,true})
   for(bool cleared:{false,true})for(unsigned remaining:{1U,7U,0U})for(unsigned pending:{0U,0xffffU}){
    auto p=std::make_unique<D>();auto &d=*p;d.cr1=0x6003;d.cr2=0x300;d.cmd_set_sector_length();
    d.cddevicenum=7;d.cddevice=&d.filters[7];d.filters[0].condtrue=discard?255:0;
    if(kind==1){d.cr1=0x6400;d.cr2=d.cr3=0;d.cr4=count;d.cmd_put_sector_data();d.dataxfer_long_w(0xcafebabe);}
    else if(kind){for(unsigned i=0;i<count;++i)append(d,0,true,0);d.cr1=kind==2?0x6300:0x6100;d.cr2=d.cr3=0;d.cr4=count;
     if(kind==2)d.cmd_get_and_delete_sector_data();else d.cmd_get_sector_data();CHECK(d.dataxfer_long_r()==word(0));}
    while(d.freeblocks)append(d,7,true,0xa5);
    d.media.type=cdrom_file::CD_TRACK_MODE1_RAW;d.media.bytes[15]=1;
    d.cd_stat=state;d.cd_next_stat=d.cd_seek_stat=CD_STAT_PLAY;d.cd_curfad=1234;d.fadstoplay=remaining;d.buffull_temp_pause=automatic;
    if(cleared)clear(d);
    d.hirqreg=pending;const auto free=d.freeblocks;const auto type=d.xfertype32;const auto *owner=d.transpart;const auto transferred=d.xferdnum;
    const auto image=storage(d);d.cr1=0x7500;d.cmd_abort_file();CHECK(storage(d)==image);
    CHECK(d.hirqreg==(pending|CMOK|EFLS)&&d.freeblocks==free&&d.xfertype32==type&&d.transpart==owner&&d.xferdnum==transferred&&d.m_host_transfer_active==bool(kind));
    d.register_state();d.capture();const auto result=finish(d,kind,count,discard,cleared,remaining);
    d.cd_stat=CD_STAT_PLAY;d.cd_next_stat=CD_STAT_PLAY;d.cd_curfad=88;d.fadstoplay=99;d.buffull_temp_pause=true;
    d.m_host_transfer_active=false;d.transpart=nullptr;d.xferdnum=0;d.media.reads=0;d.restore();
    CHECK(finish(d,kind,count,discard,cleared,remaining)==result);++replays;++cases;
   }
  }
 }
 // Normal buffer-space release, without Abort, must still auto-resume.
 for(bool automatic:{false,true}){auto p=std::make_unique<D>();auto &d=*p;
  d.cddevicenum=7;d.cddevice=&d.filters[7];while(d.freeblocks)append(d,7,true,0xa5);
  d.media.type=cdrom_file::CD_TRACK_MODE1_RAW;d.media.bytes[15]=1;d.cd_stat=CD_STAT_PAUSE;d.cd_curfad=1234;d.fadstoplay=7;d.buffull_temp_pause=automatic;
  clear(d);for(unsigned i=0;i<3;++i)d.cd_playdata();CHECK(d.media.reads==unsigned(automatic)&&d.cd_curfad==1234+automatic&&d.fadstoplay==7-automatic);++controls;
 }
 std::printf("method-level, unvalidated: %u Abort/private-PUT/GET/GETDELETE/capacity-release images; %u registered pool/host/drive replays; %u non-Abort manual/auto controls\n",cases,replays,controls);
 std::puts("method-level, unvalidated: actual Abort/drive/reset/allocator/port/End/Delete/save methods; mock media/IRQ/audio/serializer; no native filesystem arbitration, timing or save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-abort-resume-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
"""Seek/pause/home retain repeat notification state independently of host info transfer."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_info_drive.py')
scope={'__file__':str(fixture),'__name__':'seek_repeat_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers,builders=(scope[k] for k in ('source','head','functions','extract','helpers','builders'))
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+'\nvoid cmd_seek_disc();\n}',1)
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_seek_disc()')
setup=fixture.read_text().split("\ntail=r'''",1)[1].split('using Outcome=',1)[0]
tail=r'''
void seek(D &d,uint32_t pos){d.cr1=0x1100|(pos>>16);d.cr2=pos;d.cmd_seek_disc();}
void settled(D &d){unsigned ticks=0;while((d.cd_stat&0xf00)==CD_STAT_BUSY||(d.cd_stat&0xf00)==CD_STAT_SEEK){CHECK(++ticks<256);d.cd_playdata();}}
using Outcome=std::array<int64_t,7>;
Outcome finish(D &d,unsigned pos,unsigned repeat,unsigned maximum,bool host){
 settled(d);
 if(!pos){CHECK((d.cd_stat&0xf00)==CD_STAT_STANDBY);seek(d,0x800096);settled(d);}
 CHECK((d.cd_stat&0xf00)==CD_STAT_PAUSE&&!d.fadstoplay&&!d.media.reads);
 d.cr_standard_return(d.cd_stat);CHECK((d.cr1&0xf)==repeat&&d.cdda_maxrepeat==maximum);
 if(host){const auto v=packet(d,2);for(unsigned i=1;i<v.size();++i)CHECK(d.dataxfer_word_r()==v[i]);CHECK(d.xferdnum==12&&d.m_host_transfer_active);d.cmd_end_data_transfer();CHECK(d.cr2==6&&!d.m_host_transfer_active);}
 return {d.cd_stat,d.cd_next_stat,d.cd_curfad,d.cd_fad_seek,d.cdda_repeat_count,d.cdda_maxrepeat,d.hirqreg};
}
int main(){unsigned images=0,replays=0,home=0;
 for(unsigned repeat=0;repeat<15;++repeat)for(unsigned maximum:{repeat,15U})for(unsigned pos:{0U,0xffffffU,0x80012cU,0x801194U,0x101U,0x201U})for(unsigned phase:{CD_STAT_PLAY,CD_STAT_PAUSE,CD_STAT_SEEK})for(bool host:{false,true}){
  auto p=std::make_unique<D>();auto &d=*p;setup(d,0,phase,repeat);d.cdda_maxrepeat=maximum;
  if(host){issue(d,2);CHECK(d.dataxfer_word_r()==packet(d,2)[0]);}
  seek(d,pos);CHECK(d.cdda_maxrepeat==maximum&&d.m_host_transfer_active==host&&d.xferdnum==unsigned(host)*2);
  if(pos){d.cr_standard_return(d.cd_stat);CHECK((d.cr1&0xf)==repeat);}
  d.register_state();d.capture();const auto expected=finish(d,pos,repeat,maximum,host);
  d.cdda_repeat_count=15;d.cdda_maxrepeat=0;d.cd_curfad=99999;d.cd_fad_seek=88;d.xfercount=0;d.m_host_transfer_active=false;d.media.reads=0;
  d.restore();CHECK(finish(d,pos,repeat,maximum,host)==expected);++images;++replays;if(!pos)++home;
 }
 std::printf("method-level, unvalidated: %u seek/pause/home/repeat/host images; %u registered drive/host replays; %u home-to-valid-position retention controls\n",images,replays,home);
 std::puts("method-level, unvalidated: actual Seek/drive/report/info/host/End/save methods, mock media metadata/audio/IRQ/serializer; no native timing, invalid-home report, complete range/repeat lifecycle or save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-seek-repeat-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+builders+setup+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

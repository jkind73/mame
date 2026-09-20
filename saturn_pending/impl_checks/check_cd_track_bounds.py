#!/usr/bin/env python3
"""Bound host track numbers before zero-based TOC lookup; method-level only."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_drive_address.py')
scope={'__file__':str(fixture),'__name__':'track_bounds_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
media=r'''struct Media{
 unsigned tracks=1,lookups=0;
 bool exists(){return true;}int get_last_track(){return tracks;}
 unsigned get_track(unsigned lba){return std::min(lba/1000,tracks-1);}
 unsigned get_track_type(unsigned t){CHECK(t<tracks);return 1;}
 unsigned get_track_start(unsigned t){++lookups;if(t==0xaa)t=tracks;CHECK(t<=tracks);return t*1000;}
}'''
head=head.replace(extract(head,'struct Media'),media)
start=extract(source,'void saturn_cd_hle_device::device_start()');reg=extract(functions,'void saturn_cd_hle_device::register_state()')
fields={'m_play_start_fad','m_play_end_fad','m_play_range_valid'}
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in fields and m[0] not in reg]
functions=functions.replace(reg,reg[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
using D=saturn_cd_hle_device;
void settle(D &d,unsigned phase){unsigned n=0;while((d.cd_stat&0xf00)!=phase){CHECK(++n<64);d.cd_playdata();}}
void seed(D &d,unsigned tracks){d.media.tracks=tracks;d.cd_stat=CD_STAT_PAUSE;d.cd_curfad=150;d.m_play_start_fad=150;d.m_play_end_fad=1150;d.m_play_range_valid=true;d.cdda_maxrepeat=5;d.cdda_repeat_count=3;}
int main(){unsigned plays=0,seeks=0,replays=0,homes=0;
 for(unsigned tracks:{1U,2U,3U,99U})for(unsigned first=0;first<256;++first)for(unsigned last:{0U,1U,tracks,tracks+1,255U}){
  D d;seed(d,tracks);const unsigned a=std::clamp(first,1U,tracks),b=last?std::min(last,tracks):tracks;
  const unsigned start=150+(a-1)*1000,end=150+b*1000,phase=end>start?CD_STAT_PLAY:CD_STAT_PAUSE,count=start==150&&end==1150?3:0;
  d.cr1=0x1000;d.cr2=first<<8;d.cr3=0x0500;d.cr4=last<<8;d.cmd_play_disc();
  CHECK(d.m_play_start_fad==start&&d.m_play_end_fad==end&&d.m_play_range_valid&&d.cdda_repeat_count==count&&d.cdda_maxrepeat==5&&d.cd_fad_seek==start);
  d.register_state();d.capture();settle(d,phase);CHECK(d.cd_curfad==start&&d.fadstoplay==(end>start?end-start:0)&&d.cur_track==int(a-1));
  d.m_play_range_valid=false;d.m_play_start_fad=d.m_play_end_fad=42;d.cd_fad_seek=43;d.cd_curfad=44;d.cdda_repeat_count=14;d.restore();settle(d,phase);
  CHECK(d.m_play_start_fad==start&&d.m_play_end_fad==end&&d.m_play_range_valid&&d.cdda_repeat_count==count&&d.cd_curfad==start&&d.fadstoplay==(end>start?end-start:0));++plays;++replays;
 }
 for(unsigned tracks:{1U,2U,3U,99U})for(unsigned tno=0;tno<256;++tno)for(unsigned index:{0U,1U}){
  D d;seed(d,tracks);d.cr1=0x1100;d.cr2=(tno<<8)|index;d.cmd_seek_disc();
  CHECK(d.cdda_maxrepeat==5&&d.cdda_repeat_count==3&&d.m_play_start_fad==150&&d.m_play_end_fad==1150&&!d.fadstoplay);
  if(!tno&&!index){settle(d,CD_STAT_STANDBY);CHECK(d.cd_curfad==0xffffffff&&d.cur_track==0xff);++homes;continue;}
  const unsigned track=std::clamp(tno,1U,tracks)-1,position=150+track*1000;CHECK(d.cur_track==int(track)&&d.cd_fad_seek==position);
  d.register_state();d.capture();settle(d,CD_STAT_PAUSE);CHECK(d.cd_curfad==position&&d.cur_track==int(track));
  d.cd_fad_seek=d.cd_curfad=42;d.cur_track=254;d.cdda_repeat_count=14;d.restore();settle(d,CD_STAT_PAUSE);CHECK(d.cd_curfad==position&&d.cur_track==int(track)&&d.cdda_repeat_count==3);++seeks;++replays;
 }
 std::printf("method-level, unvalidated: %u Play track-bound images; %u Seek track/index0-1 images; %u registered continuations; %u Home controls\n",plays,seeks,replays,homes);
 std::puts("method-level, unvalidated: actual Play/Seek/drive/save methods with bounded authored 1/2/3/99-track TOCs and mock report/media/audio/IRQ/serializer; no nontrivial indices, native TOC/seek timing, host overlap or save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-track-bounds-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

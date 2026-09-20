#!/usr/bin/env python3
"""Programmed range versus current progress; actual methods, non-native interval model."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_audio_range.py')
scope={'__file__':str(fixture),'__name__':'programmed_range_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
fields=[('m_play_start_fad','uint32_t','150'),('m_play_end_fad','uint32_t','150'),('m_play_range_valid','bool','false')]
dev=extract(head,'struct saturn_cd_hle_device');decl=''.join(f'{kind} {name}={value};' for name,kind,value in fields if name not in dev)
head=head.replace(dev,dev[:-1]+decl+'}',1)
start=extract(source,'void saturn_cd_hle_device::device_start()');reg=extract(functions,'void saturn_cd_hle_device::register_state()')
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in {f[0] for f in fields} and m[0] not in reg]
functions=functions.replace(reg,reg[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
using D=saturn_cd_hle_device;
constexpr unsigned NC=0xffffff;
void tick(D &d){++d.audio.now;d.cd_sector_cb(0);d.audio.flush();}
void settle(D &d,unsigned state){unsigned n=0;while((d.cd_stat&0xf00)!=state){CHECK(++n<96);tick(d);}}
void play(D &d,unsigned start,unsigned end,unsigned mode){d.cr1=0x1000|(start>>16);d.cr2=start;d.cr3=(mode<<8)|(end>>16);d.cr4=end;d.cmd_play_disc();}
void range(D &d,unsigned start,unsigned count,unsigned mode=0){play(d,0x800000|start,0x800000|count,mode);}
void seek(D &d,unsigned pos){d.cr1=0x1100|(pos>>16);d.cr2=pos;d.cmd_seek_disc();}
void stored(D &d,unsigned a,unsigned b){CHECK(d.m_play_range_valid&&d.m_play_start_fad==a&&d.m_play_end_fad==b);}
bool audible(unsigned fad,unsigned mask){unsigned t=fad<450?0:fad<850?1:2;return mask&(1U<<t);}
int main(){unsigned ranges=0,repeats=0,resumes=0,replays=0,controls=0,intervals=0;
 for(unsigned start:{150U,440U,449U,840U,849U,1300U})for(unsigned count:{1U,2U,17U,40U})for(unsigned maximum:{0U,1U,3U,15U})for(unsigned mask:{0U,2U,7U}){
  D d;d.cd_speed=1;d.cd_curfad=150;d.media.audio_mask=mask;range(d,start,count,maximum);stored(d,start,start+count);
  const unsigned rounds=maximum==15?4:maximum+1;std::vector<unsigned> expected_audio,expected_data;
  for(unsigned round=0;round<rounds;++round){settle(d,CD_STAT_PLAY);CHECK(d.cd_curfad==start&&d.fadstoplay==count);
   for(unsigned i=0;i<count;++i){if(audible(start+i,mask))expected_audio.push_back(start+i-150);else expected_data.push_back(start+i);tick(d);++intervals;}
   CHECK(d.audio.rendered==expected_audio&&d.read_fads==expected_data);stored(d,start,start+count);
   if(maximum!=15&&round+1==rounds){CHECK(!d.fadstoplay&&(d.hirqreg&PEND));settle(d,CD_STAT_PAUSE);}
   else {CHECK(d.cd_fad_seek==start&&d.fadstoplay==count&&d.cdda_repeat_count==round+1&&!(d.hirqreg&PEND));++repeats;}
  }++ranges;
 }
 for(unsigned cut:{0U,1U,7U,39U})for(unsigned position:{440U,447U,479U})for(unsigned command:{NC,0x800000|position}){
  D d;d.cd_speed=1;range(d,440,40,3);settle(d,CD_STAT_PLAY);for(unsigned i=0;i<cut;++i)tick(d);d.cdda_repeat_count=2;
  const unsigned stopped=command==NC?440+cut:position;seek(d,command);settle(d,CD_STAT_PAUSE);stored(d,440,480);CHECK(d.cdda_repeat_count==2);
  play(d,NC,NC,0xff);settle(d,CD_STAT_PLAY);CHECK(d.cd_curfad==stopped&&d.fadstoplay==480-stopped&&d.cdda_repeat_count==2);stored(d,440,480);
  // Actual registrations, including the new range fields. Audio is data-only
  // here; native converter phase and sample serialization are not modelled.
  d.register_state();d.capture();play(d,NC,NC,0x7f);settle(d,CD_STAT_PLAY);CHECK(d.cd_curfad==440&&d.fadstoplay==40&&d.cdda_repeat_count==2);
  d.m_play_start_fad=999;d.m_play_end_fad=1000;d.m_play_range_valid=false;d.cdda_repeat_count=0;d.fadstoplay=0;
  d.restore();stored(d,440,480);play(d,NC,NC,0x7f);settle(d,CD_STAT_PLAY);CHECK(d.cd_curfad==440&&d.fadstoplay==40&&d.cdda_repeat_count==2);++resumes;++replays;
 }
 // No-move while playing preserves the armed converter and actual position,
 // including endpoint shortening/extension across the old converter boundary.
 for(unsigned end:{20U,40U,60U}){D d;d.cd_speed=1;d.media.audio_mask=7;range(d,440,40);settle(d,CD_STAT_PLAY);for(unsigned i=0;i<7;++i)tick(d);
  const auto starts=d.audio.starts.size();range(d,440,end,0x80);CHECK(d.cd_stat==CD_STAT_PLAY&&d.cd_curfad==447&&d.fadstoplay==end-7&&d.audio.starts.size()==starts);
  for(unsigned i=7;i<end;++i)tick(d);CHECK(d.audio.rendered.size()==end);for(unsigned i=0;i<end;++i)CHECK(d.audio.rendered[i]==290+i);++controls;
 }
 {D d;d.cd_speed=1;d.media.audio_mask=7;d.cd_stat=CD_STAT_PLAY;d.cd_curfad=450;d.fadstoplay=0;
  range(d,440,40,0x80);CHECK(d.audio.playing&&d.audio.starts.size()==1);for(unsigned i=0;i<30;++i)tick(d);CHECK(d.audio.rendered.size()==30&&d.audio.rendered.front()==300&&d.audio.rendered.back()==329);++controls;}
 for(unsigned position:{150U,439U,440U,447U,479U,480U,900U}){D d;range(d,440,40,3);settle(d,CD_STAT_PLAY);seek(d,0x800000|position);settle(d,CD_STAT_PAUSE);
  play(d,NC,NC,0xff);const bool inside=position>=440&&position<480;settle(d,inside?CD_STAT_PLAY:CD_STAT_PAUSE);CHECK(d.cd_curfad==position&&d.fadstoplay==(inside?480-position:0));stored(d,440,480);++controls;
 }
 {D d;range(d,440,40,3);settle(d,CD_STAT_PLAY);seek(d,0x800000|460);tick(d);play(d,NC,NC,0xff);settle(d,CD_STAT_PLAY);CHECK(d.cd_curfad==460&&d.fadstoplay==20);++controls;}
 {D d;range(d,440,40,3);settle(d,CD_STAT_PLAY);d.cdda_repeat_count=2;
  range(d,440,40,0x83);CHECK(d.cdda_repeat_count==2);range(d,440,40,0x82);CHECK(!d.cdda_repeat_count);d.cdda_repeat_count=1;
  play(d,NC,0x80000d,0xff);stored(d,440,453);CHECK(!d.cdda_repeat_count);
  play(d,0x800000|460,NC,0x7f);settle(d,CD_STAT_PAUSE);stored(d,460,453);CHECK(!d.fadstoplay);
  play(d,NC,0x800014,0xff);settle(d,CD_STAT_PLAY);stored(d,460,480);CHECK(d.fadstoplay==20);++controls;
 }
 for(unsigned start:{0U,149U,150U,1349U,1350U,0x7ffffeU})for(unsigned count:{0U,1U,17U,0x100000U}){D d;range(d,start,count);const auto a=std::clamp(start,150U,1350U),b=std::min(a+count,1350U);stored(d,a,b);settle(d,a<b?CD_STAT_PLAY:CD_STAT_PAUSE);CHECK(d.cd_curfad==a&&d.fadstoplay==b-a);++controls;}
 {D d;play(d,0,0,0);stored(d,150,1350);settle(d,CD_STAT_PLAY);CHECK(d.fadstoplay==1200);++controls;}
 {D d;range(d,440,40);settle(d,CD_STAT_PLAY);d.media.inserted=false;range(d,500,20);stored(d,440,480);++controls;}
 std::printf("method-level, unvalidated: %u programmed ranges, %u repeat boundaries, %u modeled producer intervals; %u pause/seek resumes and registered replays; %u endpoint/no-move/counter controls\n",ranges,repeats,intervals,resumes,controls);
 std::puts("method-level, unvalidated: actual Play/Seek/drive/converter/periodic/save methods, synthetic track metadata and interval sink; no native PCM/IRQ/seek timing/media-change/save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-programmed-range-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

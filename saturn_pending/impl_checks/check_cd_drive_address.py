#!/usr/bin/env python3
"""Drive FAD/LBA and track-index boundaries; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_drive_phase_save.py')
scope={'__file__':str(fixture),'__name__':'drive_address_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
media=r'''struct Media{
 bool inserted=true;unsigned audio_mask=0;std::vector<unsigned> queries;
 static constexpr unsigned starts[]={0,300,700,1200};
 bool exists(){return inserted;}
 unsigned get_track(unsigned lba){queries.push_back(lba);for(unsigned i=0;i<3;++i)if(lba<starts[i+1])return i;return 0;}
 unsigned get_track_type(unsigned track){CHECK(track<3);return (audio_mask>>track)&1?0:1;}
 unsigned get_track_start(unsigned track){if(track==0xaa)track=3;CHECK(track<=3);return starts[track];}
}'''
audio=r'''struct Audio{
 unsigned calls=0;std::vector<std::array<unsigned,2>> starts;
 void pause_audio(int){++calls;}void stop_audio(){++calls;}
 void start_audio(unsigned lba,unsigned count){++calls;starts.push_back({lba,count});}
}'''
head=head.replace(extract(head,'struct Media'),media).replace(extract(head,'struct Audio'),audio)
head=head.replace('void cd_read_filtered_sector(unsigned,uint8_t *ok){++reads;*ok=!buffull;}',
                  'std::vector<unsigned> read_fads;void cd_read_filtered_sector(unsigned fad,uint8_t *ok){read_fads.push_back(fad);++reads;*ok=!buffull;}')
at=head.rfind('};');head=head[:at]+r'''
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0;unsigned cd_speed=2;
 void cr_standard_return(uint16_t status){cr1=status;}
 void cmd_play_disc();void cmd_seek_disc();void cd_sector_cb(int);
 struct Timer{unsigned hz=0;void adjust(unsigned rate){hz=rate;}}timer;Timer *m_sector_timer=&timer;
'''+head[at:]
head=head.replace('const char*,bool)', 'const char*,bool=false)')
head+='\nconstexpr unsigned CD_STAT_STANDBY=0x200,CD_STAT_SCAN=0x500,CMOK=1,SCDQ=0x400;\nstruct attotime{static unsigned from_hz(unsigned rate){return rate;}};\n#define TIMER_CALLBACK_MEMBER(name) void name(int)\n'
functions+='\n'+'\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cmd_play_disc()', 'void saturn_cd_hle_device::cmd_seek_disc()', 'TIMER_CALLBACK_MEMBER(saturn_cd_hle_device::cd_sector_cb)'))
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_audio_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using D=saturn_cd_hle_device;
void settle(D &d,unsigned state){unsigned n=0;while((d.cd_stat&0xf00)!=state){CHECK(++n<64);d.cd_playdata();}}
void play(D &d,unsigned first,unsigned last){d.cd_curfad=150;d.cr1=0x1000;d.cr2=first<<8;d.cr3=0;d.cr4=last<<8;d.cmd_play_disc();}
void first_sector(D &d,unsigned lba,unsigned mask){
 d.media.queries.clear();d.audio.starts.clear();d.read_fads.clear();d.cd_playdata();
 CHECK(d.media.queries.size()==1&&d.media.queries[0]==lba);
 unsigned track=0;while(lba>=D::Media::starts[track+1])++track;
 if((mask>>track)&1){CHECK(d.audio.starts.size()==1&&d.audio.starts[0][0]==lba&&d.audio.starts[0][1]==1&&d.read_fads.empty());}
 else CHECK(d.audio.starts.empty()&&d.read_fads.size()==1&&d.read_fads[0]==lba+150);
 CHECK(d.cd_curfad==lba+151);
}
int main(){unsigned ranges=0,seeks=0,sectors=0,repeats=0,replays=0,retained=0;
 for(unsigned mask=0;mask<8;++mask)for(unsigned first=1;first<=3;++first)for(unsigned last=first;last<=3;++last){
  D d;d.media.audio_mask=mask;play(d,first,last);settle(d,CD_STAT_PLAY);
  const unsigned lba=D::Media::starts[first-1],length=D::Media::starts[last]-lba;
  CHECK(d.cd_curfad==lba+150&&d.cur_track==int(first-1)&&d.fadstoplay==length);
  // Replay the actual saved drive phase, then observe the same image/audio
  // address on the next producer step. Media/audio and native timers are mocks.
  d.register_state();d.capture();first_sector(d,lba,mask);
  d.cd_stat=0;d.cd_curfad=42;d.fadstoplay=0;d.cur_track=99;d.restore();
  first_sector(d,lba,mask);++replays;++ranges;
 }
 for(unsigned mask=0;mask<8;++mask)for(unsigned track=1;track<=3;++track){
  D d;d.media.audio_mask=mask;d.cr1=0x1100;d.cr2=track<<8;d.cmd_seek_disc();settle(d,CD_STAT_PAUSE);
  CHECK(d.cd_curfad==D::Media::starts[track-1]+150&&d.cur_track==int(track-1));
  CHECK(!d.media.queries.empty()&&d.media.queries.back()==D::Media::starts[track-1]&&d.audio.starts.empty());++seeks;
 }
 for(unsigned mask=0;mask<8;++mask)for(unsigned lba:{0U,149U,150U,298U,299U,300U,549U,550U,698U,699U,700U,1049U,1050U,1198U}){
  D d;d.media.audio_mask=mask;d.cd_stat=CD_STAT_PLAY;d.cd_curfad=lba+150;d.fadstoplay=2;
  d.cd_sector_cb(0);CHECK(d.media.queries.size()==2&&d.media.queries[0]==lba&&d.media.queries[1]==lba+1);
  unsigned track=0;while(lba+1>=D::Media::starts[track+1])++track;
  CHECK(d.timer.hz==(((mask>>track)&1)?75:150));
  unsigned oldtrack=0;while(lba>=D::Media::starts[oldtrack+1])++oldtrack;
  if((mask>>oldtrack)&1)CHECK(d.audio.starts.size()==1&&d.audio.starts[0][0]==lba);
  else CHECK(d.read_fads.size()==1&&d.read_fads[0]==lba+150);
  ++sectors;
 }
 for(unsigned mask=0;mask<8;++mask)for(unsigned track=0;track<3;++track){
  D d;d.media.audio_mask=mask;d.cd_stat=CD_STAT_PLAY;d.cur_track=track;
  d.cd_curfad=D::Media::starts[track+1]+149;d.fadstoplay=1;d.cdda_maxrepeat=1;
  d.cd_playdata();settle(d,CD_STAT_PLAY);
  CHECK(d.cd_curfad==D::Media::starts[track]+150&&d.cur_track==int(track)&&d.cdda_repeat_count==1);
  CHECK(d.fadstoplay==D::Media::starts[track+1]-D::Media::starts[track]);++repeats;
 }
 // Existing pickup-retention/resume branches: test address/count units only,
 // not their unresolved programmed-range or no-change command semantics.
 for(unsigned track=0;track<3;++track)for(unsigned offset:{0U,149U,200U})for(unsigned mode=0;mode<3;++mode){
  D d;d.cur_track=track;d.cd_curfad=D::Media::starts[track]+150+offset;d.fadstoplay=0;
  d.cr1=mode==2?0x10ff:0x1000;d.cr2=mode==2?0xffff:0x100;d.cr3=0x8000;d.cr4=mode==0?0:(track+1)<<8;
  d.cmd_play_disc();CHECK(d.fadstoplay==D::Media::starts[mode==0?3:track+1]+150-d.cd_curfad);++retained;
 }
 std::printf("method-level, unvalidated: %u track ranges/%u registered drive replays; %u track seeks; %u boundary producer/cadence images; %u repeat targets; %u existing retained-position count controls\n",ranges,replays,seeks,sectors,repeats,retained);
 std::puts("method-level, unvalidated: actual Play/Seek/drive/status/periodic/save methods with mock mixed-track image, sector producer, audio sink, timer and serializer; no native tone/range/SCAN qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-drive-address-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

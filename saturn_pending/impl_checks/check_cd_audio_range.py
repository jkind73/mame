#!/usr/bin/env python3
"""Converter range lifecycle against drive intervals; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_drive_address.py')
scope={'__file__':str(fixture),'__name__':'audio_range_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
audio=r'''struct Audio {
 void set_output_gain(int,double){}
 unsigned calls=0,now=0,last=0,lba=0,left=0;bool playing=false,paused=false;
 std::vector<std::array<unsigned,2>> starts;std::vector<unsigned> rendered;
 void flush(){while(last<now){++last;if(playing&&!paused){CHECK(left);rendered.push_back(lba++);if(!--left)playing=false;}}}
 void pause_audio(int pause){flush();paused=pause;++calls;}
 void stop_audio(){flush();playing=false;++calls;}
 bool audio_active(){flush();return playing;}
 void start_audio(unsigned start,unsigned count){flush();CHECK(count);lba=start;left=count;playing=true;paused=false;starts.push_back({start,count});++calls;}
}'''
head=head.replace(extract(head,'struct Audio'),audio)
head=head.replace('void update_hirq(){++irqs;}', 'bool end_notified=false;void (*notice)(saturn_cd_hle_device&)=nullptr;void update_hirq(){++irqs;if(notice)notice(*this);}')
if 'void cd_update_cdda(' not in head:
    head=head.replace(' void cmd_play_disc();', ' void cd_update_cdda();void cmd_play_disc();')
sig='void saturn_cd_hle_device::cd_update_cdda()'
if sig in source and sig not in functions:functions+='\n'+extract(source,sig)
tail=r'''
using D=saturn_cd_hle_device;
unsigned end_notices=0,frames=0,runs=0;
void notice(D &d){if(d.hirqreg&PEND){CHECK(!d.audio.playing);if(!d.end_notified){d.end_notified=true;++end_notices;}}}
bool audio(unsigned lba,unsigned mask){unsigned track=0;while(lba>=D::Media::starts[track+1])++track;return (mask>>track)&1;}
void tick(D &d){++d.audio.now;d.cd_sector_cb(0);d.audio.flush();}
void arm(D &d,unsigned lba,unsigned count,unsigned mask){
 d.media.audio_mask=mask;d.cd_speed=1;d.cd_curfad=lba+150;d.fadstoplay=count;d.cd_stat=CD_STAT_BUSY;d.cd_next_stat=CD_STAT_PLAY;
 d.cd_sector_cb(0);CHECK(d.cd_stat==CD_STAT_PLAY&&d.cd_curfad==lba+150&&d.fadstoplay==count&&d.timer.hz==75);
 CHECK(d.audio.playing==audio(lba,mask)&&d.audio.rendered.empty());
}
void consume(D &d,unsigned start,unsigned count,unsigned mask){
 std::vector<unsigned> expected;unsigned starts=0;
 for(unsigned i=0;i<count;++i){
  const unsigned lba=start+i;if(audio(lba,mask)){expected.push_back(lba);if(!i||!audio(lba-1,mask))++starts;}
  const auto queries=d.media.queries.size();tick(d);
  CHECK(d.audio.rendered==expected&&d.cd_curfad==lba+151&&d.fadstoplay==count-i-1);
  CHECK(d.media.queries[queries]==lba); // actual producer classification
  CHECK(d.audio.playing==(i+1<count&&audio(lba+1,mask)));
  CHECK(d.timer.hz==(i+1<count?75:60)); // speed1: both data and audio intervals
  if(i+1<count)CHECK(d.media.queries.back()==lba+1); // actual timer classification
  ++frames;
 }
 CHECK(d.audio.starts.size()==starts&&!d.audio.playing&&(d.hirqreg&PEND));
 tick(d);CHECK(d.cd_stat==CD_STAT_PAUSE&&d.audio.rendered==expected);
 for(unsigned i=0;i<4;++i)tick(d);CHECK(d.audio.rendered==expected);runs+=starts;
}
int main(){unsigned ranges=0,commands=0,interrupts=0;
 for(unsigned mask=0;mask<8;++mask)for(unsigned start:{0U,149U,299U,300U,399U,699U,700U,1199U})
 for(unsigned requested:{1U,2U,3U,10U,149U,150U,300U}){
  const unsigned count=std::min(requested,1200-start);D d;d.notice=notice;arm(d,start,count,mask);
  consume(d,start,count,mask);++ranges;
 }
 // The original address/default probes retain their one-sector-restart and
 // fixed-query-count expectations. Recheck their command contracts here
 // without assuming that converter starts and logical sector steps coincide.
 for(unsigned mask=0;mask<8;++mask)for(unsigned first=0;first<=3;++first)for(unsigned last=0;last<=3;++last){
  const unsigned f=first?first:1,e=last?last:3;if(e<f)continue;
  D d;d.notice=notice;d.media.audio_mask=mask;d.cd_speed=1;d.cd_curfad=150;
  d.cr1=0x1000;d.cr2=first<<8;d.cr3=0;d.cr4=last<<8;d.cmd_play_disc();
  unsigned steps=0;while((d.cd_stat&0xf00)!=CD_STAT_PLAY){CHECK(++steps<64);tick(d);CHECK(d.audio.rendered.empty());}
  const unsigned start=D::Media::starts[f-1],count=D::Media::starts[e]-start;
  CHECK(d.cd_curfad==start+150&&d.fadstoplay==count&&d.cur_track==int(f-1));
  consume(d,start,count,mask);++commands;
 }
 for(unsigned cut=0;cut<12;++cut){
  D d;arm(d,300,12,7);for(unsigned i=0;i<cut;++i)tick(d);
  d.cr1=0x11ff;d.cr2=0xffff;d.cmd_seek_disc();CHECK(!d.audio.playing&&d.audio.rendered.size()==cut);
  for(unsigned i=0;i<32;++i)tick(d);CHECK(d.cd_stat==CD_STAT_PAUSE&&d.audio.rendered.size()==cut);++interrupts;
 }
 CHECK(end_notices==ranges+commands);
 std::printf("method-level, unvalidated: %u direct audio/data ranges; %u actual explicit/default track commands; %u modeled sector intervals; %u uninterrupted audio runs; %u pause interruptions; %u PEND stopped-output observations\n",ranges,commands,frames,runs,interrupts,end_notices);
 std::puts("method-level, unvalidated: actual Play/Seek/drive/status/periodic/converter-control methods; ideal interval-clocked audio sink, NOT native PCM samples, four-frame pre-start unmute, elapsed native timer or audio save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-audio-range-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

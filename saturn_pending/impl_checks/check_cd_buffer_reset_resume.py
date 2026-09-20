#!/usr/bin/env python3
"""All-public-buffer reset preserves real capacity and auto-pause intent; method-level, unvalidated."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_raw_put.py')
scope={'__file__':str(fixture),'__name__':'buffer_reset_resume_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace(' struct Media {', ' struct Media {bool exists(){return true;}unsigned get_track_start(unsigned t){return 150+t*10000;}')
at=head.rfind('};');head=head[:at]+r'''
 uint16_t cd_next_stat=0x100,cd_seek_stat=0x300;uint32_t cd_fad_seek=1234;
 int cur_track=0,m_seek_ticks_left=0;
 bool buffull_temp_pause=false,m_status_change_in_progress=false,m_seek_in_progress=false;
 uint8_t playtype=1,cdda_repeat_count=0,cdda_maxrepeat=0;
 struct Audio{void stop_audio(){}void start_audio(unsigned,unsigned){}void pause_audio(int){}}audio;Audio *m_cdda=&audio;
 void trace_boot_state(const char*,bool=true){}void trace_host_read(unsigned,uint16_t){}
 uint16_t hirq_r();void cd_playdata();void cd_change_status(uint16_t);
 void cmd_reset_selector();void cd_reset_filter_conditions(filterT&);void cmd_delete_sector_data();void cmd_get_buffer_size();
'''+head[at:]
head+='\nusing u16=uint16_t;\n#define LOGSTATUS(...) ((void)0)\n#define LOGSEEK(...) ((void)0)\n#define popmessage(...) ((void)0)\nconstexpr unsigned LIVE_CD_VIEW=0,CSCT=4,PEND=0x10,EFLS=0x200,CD_STAT_BUSY=0,CD_STAT_PAUSE=0x100,CD_STAT_PLAY=0x300,CD_STAT_SEEK=0x400,CD_STAT_PERI=0x2000;\ntemplate<class T>bool BIT(T value,unsigned bit){return (value>>bit)&1;}\n'
functions+='\n'+'\n'.join(extract(source,'void saturn_cd_hle_device::'+name+'(') for name in (
 'cd_playdata','cd_change_status','cmd_reset_selector','cd_reset_filter_conditions','cmd_delete_sector_data','cmd_get_buffer_size'))
functions+='\n'+extract(source,'uint16_t saturn_cd_hle_device::hirq_r()')
# Extend the actual registration subset to cover the drive phase as well as
# the already selected pool/host state. No invented registration statement.
wanted={'cd_next_stat','cd_seek_stat','cd_curfad','cd_fad_seek','fadstoplay','cur_track','m_seek_ticks_left','buffull_temp_pause','m_status_change_in_progress','m_seek_in_progress','playtype','cdda_repeat_count','cdda_maxrepeat'}
start=extract(source,'void saturn_cd_hle_device::device_start()')
registered=extract(functions,'void saturn_cd_hle_device::register_state()')
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in wanted and m[0] not in registered]
functions=functions.replace(registered,registered[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
helper=Path(__file__).with_name('check_cd_get_snapshot.py')
helpers=helper.read_text().split("\ntail=r'''",1)[1].split('unsigned cases=',1)[0]
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_audio_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using Frame=std::array<int64_t,9>;
Frame frame(D &d){return {d.cd_stat,d.cd_next_stat,d.freeblocks,d.buffull,d.buffull_temp_pause,d.cd_curfad,d.fadstoplay,d.media.reads,d.m_host_transfer_active};}
void reserve(D &d,unsigned kind,unsigned count,bool discard){
 d.cddevicenum=7;d.cddevice=&d.filters[7];
 if(kind==1){d.filters[0].condtrue=discard?255:0;d.cr1=0x6400;d.cr2=d.cr3=0;d.cr4=count;d.cmd_put_sector_data();}
 if(kind==2){for(unsigned i=0;i<count;++i)append(d,0,true,0);d.cr1=0x6300;d.cr2=d.cr3=0;d.cr4=count;d.cmd_get_and_delete_sector_data();}
 CHECK(d.freeblocks==200-count&&d.m_host_transfer_active==bool(kind));
}
std::vector<Frame> finish(D &d,unsigned kind,unsigned count,bool discard,bool automatic,unsigned remaining){
 std::vector<Frame> frames;
 auto ticks=[&](){for(unsigned i=0;i<3;++i){d.cd_playdata();frames.push_back(frame(d));}};
 ticks();const unsigned initial_reads=automatic&&remaining&&count<200?1:0;
 CHECK(unsigned(d.media.reads)==initial_reads&&d.cd_curfad==1234+initial_reads&&d.fadstoplay==remaining-initial_reads);
 CHECK(d.m_host_transfer_active==bool(kind)&&d.xferdnum==0);
 for(unsigned i=0;i<count;++i)CHECK(d.blocks[i].size==2352);
 if(kind){
  const auto free_before_end=d.freeblocks;d.cmd_end_data_transfer();
  CHECK(!d.m_host_transfer_active&&d.freeblocks==free_before_end+((kind==2||discard)?count:0));
  if(count==200){
   const unsigned space=kind==2||discard?200:0;CHECK(d.freeblocks==space);
   ticks();const unsigned after_end=automatic&&remaining&&space?1:0;CHECK(unsigned(d.media.reads)==after_end);
   if(!space){d.cr1=0x6200;d.cr2=d.cr3=0;d.cr4=1;d.cmd_delete_sector_data();CHECK(d.freeblocks==1);
    ticks();CHECK(unsigned(d.media.reads)==unsigned(automatic&&remaining));}
  }
 }
 return frames;
}
int main(){unsigned cases=0,replays=0,heldfull=0;
 for(unsigned count:{0U,1U,99U,199U,200U})for(unsigned kind=0;kind<3;++kind){
  if((count==0)!=(kind==0))continue;
  for(bool discard:{false,true}){if(kind!=1&&discard)continue;
   for(bool automatic:{false,true})for(unsigned public_buf:{0U,7U,23U})for(unsigned pending:{0U,8U,0xffffU})for(unsigned remaining:{1U,7U,0U}){
    auto p=std::make_unique<D>();auto &d=*p;reserve(d,kind,count,discard);
    while(d.freeblocks)append(d,public_buf,true,0xa5);CHECK(d.buffull&&d.freeblocks==0);
    d.media.type=cdrom_file::CD_TRACK_MODE1_RAW;d.media.bytes[15]=1;
    d.cd_stat=d.cd_next_stat=CD_STAT_PAUSE;d.cd_seek_stat=CD_STAT_PLAY;d.cd_curfad=1234;d.fadstoplay=remaining;
    d.buffull_temp_pause=automatic;d.hirqreg=pending;d.sectorstore=1;
    const auto type=d.xfertype32;const auto *part=d.transpart;
    d.cr1=0x4804;d.cr3=public_buf<<8;d.cmd_reset_selector();
    CHECK(d.freeblocks==200-count&&d.buffull==int(count==200)&&!d.sectorstore&&d.m_host_transfer_active==bool(kind)&&d.xfertype32==type&&d.transpart==part);
    for(const auto &part:d.partitions){CHECK(part.numblks==0&&part.size==-1);for(unsigned i=0;i<200;++i)CHECK(!part.blocks[i]&&part.bnum[i]==255);}
    d.cr1=0x5000;d.cmd_get_buffer_size();CHECK(d.cr2==200-count);
    CHECK(bool(d.hirq_r()&BFUL)==(count==200));if(count==200)++heldfull;
    d.register_state();d.capture();const auto expected=finish(d,kind,count,discard,automatic,remaining);
    d.m_get_partition={};d.m_put_partition={};d.m_put_filter=255;d.transpart=nullptr;d.cddevice=nullptr;
    for(auto &part:d.partitions){part={};std::fill(std::begin(part.bnum),std::end(part.bnum),255);}
    for(auto &b:d.blocks){b={};b.size=-1;}
    d.freeblocks=200;d.buffull=0;d.buffull_temp_pause=false;d.m_host_transfer_active=false;d.xfertype32=D::XFERTYPE32_INVALID;
    d.cd_stat=d.cd_next_stat=CD_STAT_BUSY;d.cd_curfad=d.fadstoplay=0;d.media.reads=0;
    const auto irqs=d.irqs;d.restore();CHECK(d.irqs==irqs&&d.freeblocks==200-count&&d.buffull==int(count==200)&&d.buffull_temp_pause==automatic&&d.m_host_transfer_active==bool(kind));
    CHECK(finish(d,kind,count,discard,automatic,remaining)==expected);++replays;++cases;
   }
  }
 }
 std::printf("method-level, unvalidated: %u all-buffer reset/manual-auto/empty-range images; %u registered pool+drive+host replays; %u privately full capacity/IRQ-read controls; delayed GETDELETE/discard-PUT/retained-PUT release controls\n",cases,replays,heldfull);
 std::puts("method-level, unvalidated: actual reset/allocator/private-transfer/End/Delete/drive/filter/media-read/IRQ-read/save methods, mocked image/IRQ/audio/serializer; existing phase timing and HIRQ overlays retained, no native latch-acknowledge/timer/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-buffer-reset-resume-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

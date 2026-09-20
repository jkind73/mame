#!/usr/bin/env python3
"""Drive auto-pause reason/seek-latch replay; method-level, unvalidated."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
using u8=uint8_t;using u16=uint16_t;
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
#define LOG(...) ((void)0)
#define LOGCMD(...) ((void)0)
#define LOGSTATUS(...) ((void)0)
#define LOGSEEK(...) ((void)0)
#define LOGXFER(...) ((void)0)
#define popmessage(...) ((void)0)
#define NAME(x) x,#x
constexpr unsigned LIVE_CD_VIEW=0,CD_STAT_BUSY=0,CD_STAT_PAUSE=0x100,CD_STAT_PLAY=0x300,CD_STAT_SEEK=0x400,CD_STAT_PERI=0x2000,CSCT=4,PEND=0x10,EFLS=0x200;
struct cdrom_file{static constexpr int CD_TRACK_AUDIO=0;};
struct saturn_cd_hle_device {
 struct Media{bool inserted=true;bool exists(){return inserted;}int get_track(unsigned){return 0;}int get_track_type(int){return 1;}unsigned get_track_start(int track){return 150+track*10000;}}media;
 struct Audio{unsigned calls=0;void pause_audio(int){++calls;}void stop_audio(){++calls;}void start_audio(unsigned,unsigned){++calls;}}audio;
 Media *m_cdrom_image=&media;Audio *m_cdda=&audio;
 uint16_t cd_stat=0x100,cd_next_stat=0x100,cd_seek_stat=0x100,hirqreg=0;
 uint32_t cd_curfad=1000,cd_fad_seek=1500,fadstoplay=5;
 int buffull=0,sectorstore=0,cur_track=0,m_seek_ticks_left=0;
 bool buffull_temp_pause=false,m_status_change_in_progress=false,m_seek_in_progress=false;
 uint8_t playtype=0,cdda_repeat_count=0,cdda_maxrepeat=0;
 unsigned reads=0,irqs=0;void update_hirq(){++irqs;}void trace_boot_state(const char*,bool){}
 void cd_read_filtered_sector(unsigned,uint8_t *ok){++reads;*ok=!buffull;}
 void cd_playdata();void cd_change_status(u16);void register_state();
 struct Entry{void *address;size_t bytes;std::vector<uint8_t> image;};std::vector<Entry> entries;
 template<class T>void save_item(T &value,const char*){entries.push_back({&value,sizeof(value),{}});}
 void capture(){for(auto &e:entries){e.image.resize(e.bytes);std::memcpy(e.image.data(),e.address,e.bytes);}}
 void restore(){for(auto &e:entries)std::memcpy(e.address,e.image.data(),e.bytes);}
};
'''
selected={'cd_stat','cd_next_stat','cd_seek_stat','cd_curfad','cd_fad_seek','fadstoplay','buffull','buffull_temp_pause','m_status_change_in_progress','m_seek_in_progress','m_seek_ticks_left','sectorstore','cur_track','hirqreg','playtype','cdda_repeat_count','cdda_maxrepeat'}
start=extract(source,'void saturn_cd_hle_device::device_start()')
regs=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in selected]
functions='void saturn_cd_hle_device::register_state(){\n'+'\n'.join(regs)+'\n}\n'
functions+='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cd_playdata()', 'void saturn_cd_hle_device::cd_change_status('))
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_audio_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using D=saturn_cd_hle_device;using Frame=std::array<int64_t,15>;
void tick(D &d,unsigned n){if(n==2)d.buffull=0;d.cd_playdata();}
std::vector<Frame> finish(D &d,unsigned start){
 d.reads=d.irqs=d.audio.calls=0;std::vector<Frame> frames;
 for(unsigned n=start;n<48;++n){tick(d,n);frames.push_back({d.cd_stat,d.cd_next_stat,d.cd_seek_stat,d.cd_curfad,d.cd_fad_seek,d.fadstoplay,d.buffull,d.buffull_temp_pause,d.m_status_change_in_progress,d.m_seek_in_progress,d.m_seek_ticks_left,d.hirqreg,d.reads,d.irqs,d.audio.calls});}
 return frames;
}
void replay(D &d,unsigned cut){
 for(unsigned n=0;n<cut;++n)tick(d,n);const bool pause=d.buffull_temp_pause,seek=d.m_seek_in_progress;
 d.register_state();d.capture();const auto expected=finish(d,cut);
 d.cd_stat=0;d.cd_next_stat=0;d.cd_curfad=1;d.cd_fad_seek=2;d.fadstoplay=0;d.hirqreg=0;d.m_seek_ticks_left=0;
 d.buffull_temp_pause=!pause;d.m_seek_in_progress=!seek;d.m_status_change_in_progress=true;d.buffull=1;
 const unsigned irqs=d.irqs;d.restore();CHECK(d.irqs==irqs&&d.buffull_temp_pause==pause&&d.m_seek_in_progress==seek);
 CHECK(finish(d,cut)==expected);
}
int main(){unsigned paused=0,seeking=0;
 for(bool auto_pause:{false,true})for(bool full:{false,true})for(bool remaining:{false,true})for(bool media:{false,true})
 for(bool seek_flag:{false,true})for(unsigned cut:{0U,1U,2U,3U,4U}){
  D d;d.buffull_temp_pause=auto_pause;d.buffull=full;d.fadstoplay=remaining?5:0;d.media.inserted=media;d.m_seek_in_progress=seek_flag;
  replay(d,cut);++paused;
 }
 for(unsigned distance:{500U,1500U})for(unsigned ticks=0;ticks<32;++ticks)for(bool seek_flag:{false,true})
 for(unsigned target:{CD_STAT_PAUSE,CD_STAT_PLAY})for(unsigned cut:{0U,1U,5U,16U,31U,39U}){
  D d;d.cd_stat=CD_STAT_SEEK;d.cd_seek_stat=target;d.cd_fad_seek=distance;d.m_seek_ticks_left=ticks;d.m_seek_in_progress=seek_flag;
  replay(d,cut);++seeking;
 }
 // A manual pause must not inherit an auto-resume reason from a later image.
 D d;d.buffull_temp_pause=false;replay(d,0);CHECK(d.cd_stat==CD_STAT_PAUSE);
 std::printf("method-level, unvalidated: %u auto/manual-pause registered replays; %u seek-phase replays; retained latch identities and no load-only IRQ callbacks\n",paused,seeking);
 std::puts("method-level, unvalidated: actual drive/status methods with mocked media/sector/audio and byte serializer; NOT native timers, physical seek timing or whole-CD save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-drive-save-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

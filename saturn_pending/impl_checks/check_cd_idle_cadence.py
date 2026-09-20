#!/usr/bin/env python3
"""Actual periodic callback's idle rate selection; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
def extract(signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]
head=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#define CHECK(x) assert(x)
#define TIMER_CALLBACK_MEMBER(name) void name(int)
constexpr unsigned CD_STAT_PAUSE=0x100,CD_STAT_PLAY=0x300,CD_STAT_SEEK=0x400,CD_STAT_SCAN=0x500,CD_STAT_PERI=0x2000,SCDQ=0x400;
struct attotime {unsigned hz;static attotime from_hz(unsigned hz){return {hz};}};
struct cdrom_file {enum {CD_TRACK_AUDIO=0,CD_TRACK_MODE1=1};};
struct saturn_cd_hle_device {
 uint16_t cd_stat=0,after=0,hirqreg=0,returned=0;
 unsigned cd_curfad=150,cd_speed=1,steps=0,irqs=0,reports=0,traces=0;
 struct Timer {unsigned hz=0,adjustments=0;void adjust(attotime t){hz=t.hz;++adjustments;}}timer;
 Timer *m_sector_timer=&timer;
 struct Media {unsigned queries=0,type=0;bool permitted=true;
  unsigned get_track(unsigned){CHECK(permitted);++queries;return 0;}
  unsigned get_track_type(unsigned){CHECK(permitted);++queries;return type;}
 }media;
 Media *m_cdrom_image=&media;
 void cd_playdata(){++steps;cd_stat=after;}
 void update_hirq(){++irqs;}
 void cr_standard_return(uint16_t status){++reports;returned=status;}
 void trace_boot_state(const char*){++traces;}
 void cd_sector_cb(int);
};
'''
tail=r'''
int main(){unsigned idle=0,active=0,transitions=0;
 // Active predecessor states ensure the callback uses the state AFTER the
 // producer step (end-of-range and buffer-full transitions included).
 for(unsigned before:{0U,0x100U,0x300U,0x400U,0x500U})
 for(unsigned state:{0U,0x100U,0x200U,0x600U,0x700U,0x800U,0x900U,0xa00U})
 for(unsigned flags:{0U,0x80U,0x2000U,0x4000U,0x608fU})
 for(unsigned speed:{1U,2U})for(unsigned type:{0U,1U})for(unsigned pending:{0U,4U,0x400U,0xffffU}){
  saturn_cd_hle_device d;d.cd_stat=before|flags;d.after=state|flags;d.cd_speed=speed;
  d.media.type=type;d.hirqreg=pending;d.cd_sector_cb(0);
  CHECK(d.timer.hz==60&&d.timer.adjustments==1&&d.steps==1);
  CHECK(!d.media.queries&&d.hirqreg==(pending|SCDQ)&&d.irqs==1&&d.traces==1);
  CHECK(d.reports==unsigned(bool(flags&CD_STAT_PERI)));
  if(d.reports)CHECK(d.returned==d.after);
  CHECK(d.cd_stat==d.after&&d.cd_speed==speed);
  if(before!=state)++transitions;++idle;
 }
 // Streaming and the existing physical SEEK/SCAN stepping remain controls,
 // not a new qualification of audio addressing, scan speed or seek timing.
 for(unsigned before:{0U,0x100U,0x300U})for(unsigned state:{0x300U,0x400U,0x500U})
 for(unsigned speed:{1U,2U})for(unsigned type:{0U,1U}){
  saturn_cd_hle_device d;d.cd_stat=before;d.after=state;d.cd_speed=speed;d.media.type=type;
  d.cd_sector_cb(0);CHECK(d.timer.hz==(state==CD_STAT_SEEK||type==0?75:75*speed));
  CHECK(d.media.queries==(state==CD_STAT_SEEK?0:2));++active;
 }
 std::printf("method-level, unvalidated: %u idle callback rate/flag images (%u producer-state transitions); %u unchanged PLAY/SEEK/SCAN controls\n",idle,transitions,active);
 std::puts("method-level, unvalidated: actual callback, mocked producer/media/timer/IRQ; requested frequency only, no native elapsed-time/audio/IRQ-edge/save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-idle-cadence-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+extract('TIMER_CALLBACK_MEMBER(saturn_cd_hle_device::cd_sector_cb)')+tail)
    subprocess.run(['g++','-std=c++20','-O2','-Wall','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

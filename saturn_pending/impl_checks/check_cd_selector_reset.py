#!/usr/bin/env python3
"""CD reset selector topology, actual reset with mocked media/timers; method-level, unvalidated."""
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name('check_cd_filter_routing.py').read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
head=head.replace('// TYPES','\n'.join(extract(header,s)+';' for s in ('struct filterT','struct blockT','struct partitionT','enum transT','enum trans32T')))
head=head.replace('#include <cstdint>','#include <cstdint>\n#include <vector>\nusing u8=uint8_t;\nstruct attotime{static int from_hz(int hz){return hz;}};\nconstexpr uint16_t CD_STAT_BUSY=0,CD_STAT_PAUSE=0x100,CD_STAT_NODISC=0x700,CD_STAT_OPEN=0x600;')
head=head.replace('int get_track(int lba)', 'bool inserted=false;bool exists(){return inserted;}\n  int get_track(int lba)')
head=head[:head.rfind('};')]+r'''
 uint16_t hirqmask=0,hirqreg=0,cr1=0,cr2=0,cr3=0,cr4=0,cd_seek_stat=0,cd_stat=0;
 int m_saved_transpart=-1,m_saved_cddevice=-1;
 uint16_t m_xfer_raw_offset=0,m_xfer_raw_size=0;
 uint32_t m_xfer_raw_sector=0xffffffff;
 int playtype=0,cur_track=0,calcsize=0,sectorstore=0,sectlenout=0,cddevicenum=0xff;
 bool buffull_temp_pause=false,m_status_change_in_progress=false,m_seek_in_progress=false;
 int m_seek_ticks_left=0;std::vector<int>curdir;
 transT xfertype=XFERTYPE_INVALID;trans32T xfertype32=XFERTYPE32_INVALID;
 unsigned xfercount=0,xferoffs=0,tray_is_closed=1,cd_speed=2,cdda_repeat_count=0;
 partitionT *transpart=nullptr;
 partitionT m_put_partition{};uint8_t m_put_filter=0xff;
 unsigned irqs=0,dir_reads=0,mpeg_resets=0;
 struct Timer{int hz=0;void adjust(int value){hz=value;}} timer;
 Timer *m_sector_timer=&timer;
 void update_hirq(){++irqs;}void read_new_dir(unsigned){++dir_reads;}
 void cd_change_status(uint16_t status){cd_stat=status;}void mpeg_reset(){++mpeg_resets;}
 void device_reset();
};
'''
functions='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::device_reset()', 'uint8_t saturn_cd_hle_device::cd_filter_destination('))
tail=r'''
int main(){
 unsigned resets=0,topologies=0;
 for(unsigned poison=0;poison<256;++poison)for(bool inserted:{false,true}){
  auto d=std::make_unique<saturn_cd_hle_device>();d->media.inserted=inserted;
  d->cddevicenum=poison%24;d->cddevice=&d->filters[d->cddevicenum];d->transpart=&d->partitions[poison%24];
  for(unsigned i=0;i<24;++i){auto &f=d->filters[i];f.mode=f.chan=f.smmask=f.cimask=f.fid=f.smval=f.cival=poison;f.condtrue=(i+1)%24;f.condfalse=(i+2)%24;f.fad=poison*301;f.range=0xffffff;}
  d->xfertype=d->XFERTYPE_SUBQ;d->xfertype32=d->XFERTYPE32_GETSECTOR;
  d->curdir={1,2,3};d->lastbuf=17;
  d->device_reset();
  CHECK(!d->cddevice&&d->cddevicenum==0xff&&!d->transpart&&d->lastbuf==0xff);
  for(unsigned i=0;i<24;++i){const auto &f=d->filters[i];const auto &p=d->partitions[i];
   CHECK(!f.mode&&!f.chan&&!f.smmask&&!f.cimask&&!f.fid&&!f.smval&&!f.cival&&!f.fad&&!f.range);
   CHECK(f.condtrue==i&&f.condfalse==0xff&&d->cd_filter_destination(i,d->curblock)==i);
   CHECK(!p.numblks&&p.size==-1);for(unsigned j=0;j<200;++j)CHECK(!p.blocks[j]&&p.bnum[j]==0xff);
   ++topologies;
  }
  CHECK(d->xfertype==d->XFERTYPE_INVALID&&d->xfertype32==d->XFERTYPE32_INVALID&&d->curdir.empty());
  CHECK(d->freeblocks==200&&d->irqs==1&&d->mpeg_resets==1&&d->timer.hz==150&&d->dir_reads==unsigned(inserted));
  for(const auto &b:d->blocks)CHECK(b.size==-1);
  ++resets;
 }
 std::printf("method-level, unvalidated: %u poisoned reset images; %u selector defaults/routes; transfer cancellation, empty ownership and legacy callback controls\n",resets,topologies);
 std::puts("method-level, unvalidated: real reset body, stubbed media/timer/MPEG/IRQ; software Init-CD command semantics and native reset/save/gameplay not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-reset-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

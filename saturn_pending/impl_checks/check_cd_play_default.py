#!/usr/bin/env python3
"""Default Play track/index positions and consumed range; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_drive_address.py')
scope={'__file__':str(fixture),'__name__':'play_default_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions=(scope[k] for k in ('source','head','functions'))
tail=r'''
using D=saturn_cd_hle_device;
int main(){unsigned defaults=0,explicit_ranges=0,sectors=0;
 for(unsigned mask=0;mask<8;++mask)for(unsigned first=0;first<=3;++first)for(unsigned last=0;last<=3;++last){
  const unsigned f=first?first:1,e=last?last:3;if(e<f)continue;
  D d;d.media.audio_mask=mask;d.cd_curfad=150;d.cr1=0x1000;d.cr2=first<<8;d.cr3=0;d.cr4=last<<8;d.cmd_play_disc();
  unsigned ticks=0;while((d.cd_stat&0xf00)!=CD_STAT_PLAY){CHECK(++ticks<64);d.cd_playdata();}
  const unsigned start=D::Media::starts[f-1],end=D::Media::starts[e];
  CHECK(d.cd_curfad==start+150&&d.fadstoplay==end-start&&d.cur_track==int(f-1));
  d.media.queries.clear();d.audio.starts.clear();d.read_fads.clear();
  for(unsigned lba=start;lba<end;++lba){
   const unsigned a=d.audio.starts.size(),r=d.read_fads.size();d.cd_playdata();
   CHECK(d.cd_curfad==lba+151&&d.fadstoplay==end-lba-1);
   CHECK(d.media.queries.back()==lba);
   unsigned track=0;while(lba>=D::Media::starts[track+1])++track;
   if((mask>>track)&1){CHECK(d.audio.starts.size()==a+1&&d.audio.starts.back()[0]==lba&&d.read_fads.size()==r);}
   else CHECK(d.read_fads.size()==r+1&&d.read_fads.back()==lba+150&&d.audio.starts.size()==a);
   ++sectors;
  }
  CHECK(d.hirqreg&PEND);d.cd_playdata();CHECK((d.cd_stat&0xf00)==CD_STAT_PAUSE);
  const auto reads=d.media.queries.size();d.cd_playdata();CHECK(d.media.queries.size()==reads&&d.cd_curfad==end+150);
  if(!first||!last)++defaults;else ++explicit_ranges;
 }
 std::printf("method-level, unvalidated: %u default-position ranges; %u explicit controls; %u exact physical sector dispatches; range-end PEND/PAUSE and no following read\n",defaults,explicit_ranges,sectors);
 std::puts("method-level, unvalidated: actual Play/drive/status methods, mock mixed-track image, accepting data sink and audio sink; no audible duration, native report/timer or unsupported-index qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-play-default-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

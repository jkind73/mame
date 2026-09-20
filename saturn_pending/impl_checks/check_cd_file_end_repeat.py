#!/usr/bin/env python3
"""File EOF is independent of the retained CD Play repeat setting."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_info_drive.py')
scope={'__file__':str(fixture),'__name__':'file_end_repeat_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,helpers,builders=(scope[k] for k in ('source','head','functions','helpers','builders'))
setup=fixture.read_text().split("\ntail=r'''",1)[1].split('using Outcome=',1)[0]
tail=r'''
using Outcome=std::array<int64_t,7>;
Outcome finish(D &d,unsigned total,unsigned cut,unsigned end,unsigned maximum,unsigned repeat,bool host,const std::vector<uint16_t> &v){
 for(unsigned i=cut;i<total;++i){d.cd_playdata();CHECK(d.media.reads==int(i+1)&&d.cd_curfad==end-total+i+1);}
 CHECK(!d.fadstoplay&&d.cd_next_stat==CD_STAT_PAUSE&&(d.hirqreg&EFLS)&&d.cdda_maxrepeat==maximum&&d.cdda_repeat_count==repeat);
 CHECK(d.partitions[0].numblks==total&&d.freeblocks==200-int(total)&&d.m_host_transfer_active==host);
 for(unsigned i=0;i<8;++i)d.cd_playdata();CHECK((d.cd_stat&0xf00)==CD_STAT_PAUSE&&d.cd_curfad==end&&d.media.reads==int(total));
 if(host){for(unsigned i=2;i<v.size();++i)CHECK(d.dataxfer_word_r()==v[i]);CHECK(d.m_host_transfer_active&&d.xferdnum==12);d.cmd_end_data_transfer();CHECK(d.cr2==6&&!d.m_host_transfer_active);}
 return {d.cd_stat,d.cd_curfad,d.fadstoplay,d.hirqreg,d.freeblocks,d.cdda_maxrepeat,d.cdda_repeat_count};
}
int main(){unsigned files=0,replays=0,overlaps=0,controls=0;
 for(unsigned maximum=0;maximum<16;++maximum)for(unsigned repeat=0;repeat<=std::min(maximum,14U);++repeat)for(unsigned bytes:{1U,2048U,2049U,8192U})for(unsigned offset:{0U,1U})for(bool host:{false,true}){
  const unsigned count=(bytes+2047)/2048;if(offset>=count)continue;const unsigned total=count-offset,cut=total>1?1:0;
  auto p=std::make_unique<D>();auto &d=*p;setup(d,1,CD_STAT_PAUSE,0);d.curdir[2].length=bytes;d.cdda_maxrepeat=maximum;
  d.cr1=0x7400;d.cr2=offset;d.cr3=0;d.cr4=2;d.cmd_read_file();CHECK(d.fadstoplay==total&&d.cd_curfad==4000+offset&&d.cdda_maxrepeat==maximum);
  // Counter seeds isolate EOF from the separately unfinished range-change policy.
  d.cdda_repeat_count=repeat;d.cd_playdata();CHECK((d.cd_stat&0xf00)==CD_STAT_PLAY);
  const auto v=packet(d,2);if(host){issue(d,2);CHECK(d.dataxfer_word_r()==v[0]&&d.dataxfer_word_r()==v[1]);}
  for(unsigned i=0;i<cut;++i)d.cd_playdata();CHECK(d.media.reads==int(cut));
  d.register_state();d.capture();const auto expected=finish(d,total,cut,4000+count,maximum,repeat,host,v);
  d.playtype=0;d.cdda_maxrepeat=0;d.cdda_repeat_count=15;d.fadstoplay=0;d.media.reads=cut;d.m_host_transfer_active=false;d.xfercount=0;std::memset(d.finfbuf,0xff,12);
  d.restore();CHECK(finish(d,total,cut,4000+count,maximum,repeat,host,v)==expected);++files;++replays;if(host)++overlaps;
 }
 // Ordinary CD Play must still choose its existing repeat path; this is not
 // a qualification of the currently track-based repeated span.
 for(unsigned maximum=0;maximum<16;++maximum)for(unsigned repeat=0;repeat<=std::min(maximum,14U);++repeat){
  auto p=std::make_unique<D>();auto &d=*p;setup(d,0,CD_STAT_PLAY,repeat);d.cdda_maxrepeat=maximum;d.cd_playdata();
  CHECK(!(d.hirqreg&EFLS)&&d.cdda_maxrepeat==maximum);
  if(repeat<maximum)CHECK(d.cd_next_stat==CD_STAT_SEEK&&d.fadstoplay&&d.cdda_repeat_count==std::min(repeat+1,14U));
  else CHECK(d.cd_next_stat==CD_STAT_PAUSE&&!d.fadstoplay&&(d.hirqreg&PEND));++controls;
 }
 std::printf("method-level, unvalidated: %u finite-file/range/offset/retained-repeat images; %u registered producer/host/pool replays; %u concurrent metadata owners; %u ordinary-repeat controls\n",files,replays,overlaps,controls);
 std::puts("method-level, unvalidated: actual Read File/info/parser/drive/filter/ports/End/save methods; authored metadata/raw image, diagnostic counters; no native FLS/IRQ/timing/save or general programmed-range qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-end-repeat-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+builders+setup+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

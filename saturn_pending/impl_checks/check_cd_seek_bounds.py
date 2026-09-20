#!/usr/bin/env python3
"""Explicit FAD seek clamping; pause/home remain separate commands."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_seek_repeat.py')
scope={'__file__':str(fixture),'__name__':'seek_bounds_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,helpers,builders,setup=(scope[k] for k in ('source','head','functions','helpers','builders','setup'))
old='unsigned get_track_start(unsigned t){return 150+t*10000;}'
assert old in head
head=head.replace(old,'unsigned leadout_fad=4500,leadout_queries=0;unsigned get_track_start(unsigned t){if(t==0xaa){++leadout_queries;return leadout_fad-150;}return 150+t*10000;}',1)
seek_helpers=fixture.read_text().split("\ntail=r'''",1)[1].split('using Outcome=',1)[0]
tail=r'''
void initial(D &d,unsigned leadout,unsigned current,unsigned phase,bool host){
 d.media.leadout_fad=leadout;d.cd_curfad=current;d.cd_fad_seek=current;d.cd_stat=phase;d.fadstoplay=37;d.cdda_repeat_count=7;d.cdda_maxrepeat=15;
 if(host){d.curdir.resize(3);d.curdir[2].firstfad=150;d.curdir[2].length=2048;issue(d,2);CHECK(d.dataxfer_word_r()==0);}
}
using Outcome=std::array<int64_t,5>;
Outcome finish(D &d,unsigned wanted,bool host){
 settled(d);CHECK((d.cd_stat&0xf00)==CD_STAT_PAUSE&&d.cd_curfad==wanted&&!d.fadstoplay&&!d.media.reads);
 d.cr_standard_return(d.cd_stat);CHECK((((d.cr3&0xff)<<16)|d.cr4)==wanted&&(d.cr1&0xf)==7&&d.cdda_maxrepeat==15);
 if(host){const auto v=packet(d,2);for(unsigned i=1;i<v.size();++i)CHECK(d.dataxfer_word_r()==v[i]);d.cmd_end_data_transfer();CHECK(d.cr2==6&&!d.m_host_transfer_active);}
 return {d.cd_stat,d.cd_curfad,d.cd_fad_seek,d.hirqreg,d.xferdnum};
}
int main(){unsigned images=0,replays=0,controls=0;
 for(unsigned leadout:{4500U,10000U,100000U})for(unsigned current:{150U,leadout-1})for(unsigned phase:{CD_STAT_PLAY,CD_STAT_PAUSE,CD_STAT_SEEK})for(bool host:{false,true}){
  for(unsigned fad:{0U,1U,149U,150U,151U,4499U,4500U,4501U,leadout-1,leadout,leadout+1,0x100000U,0x7ffffeU}){
   auto p=std::make_unique<D>();auto &d=*p;initial(d,leadout,current,phase,host);const unsigned wanted=std::min(std::max(fad,150U),leadout);
   seek(d,0x800000|fad);CHECK(d.cd_fad_seek==wanted&&d.media.leadout_queries==1&&d.m_host_transfer_active==host);
   d.cd_playdata();CHECK((d.cd_stat&0xf00)==CD_STAT_SEEK);d.cr_standard_return(d.cd_stat);CHECK((((d.cr3&0xff)<<16)|d.cr4)==wanted);
   d.register_state();d.capture();const auto expected=finish(d,wanted,host);d.cd_curfad=d.cd_fad_seek=99;d.cdda_repeat_count=0;d.xfercount=0;d.m_host_transfer_active=false;
   d.restore();CHECK(finish(d,wanted,host)==expected);++images;++replays;
  }
  for(unsigned special:{0U,0xffffffU}){auto p=std::make_unique<D>();auto &d=*p;initial(d,leadout,current,phase,host);seek(d,special);CHECK(!d.media.leadout_queries);
   if(special)CHECK(d.cd_fad_seek==current&&d.cd_seek_stat==CD_STAT_PAUSE);else CHECK(d.cd_next_stat==CD_STAT_STANDBY);
   CHECK(d.cdda_repeat_count==7&&d.cdda_maxrepeat==15&&d.m_host_transfer_active==host);++controls;
  }
 }
 std::printf("method-level, unvalidated: %u explicit-FAD boundary/phase/host images; %u registered seek/host replays; %u pause/home sentinel controls\n",images,replays,controls);
 std::puts("method-level, unvalidated: actual Seek/drive/FAD-report/host/save methods; synthetic lead-outs, fixed report track/index metadata; no native seek timing, lead-out TNO/index, absent-media or save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-seek-bounds-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+builders+setup+seek_helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

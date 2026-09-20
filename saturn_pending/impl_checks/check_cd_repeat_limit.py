#!/usr/bin/env python3
"""Programmed repeat limit/default/no-change; method-level, unvalidated."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_drive_address.py')
scope={'__file__':str(fixture),'__name__':'repeat_limit_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
# Execute ONLY the two actual scalar-reset statements. This is not a claim
# that the complete native device reset/media/parser path has been exercised.
reset=extract(source,'void saturn_cd_hle_device::device_reset()')
statements=re.findall(r'\bcdda_(?:maxrepeat|repeat_count)\s*=\s*\d+;',reset)
head=head.replace(' void cmd_play_disc();', ' void reset_repeat_subset();void cmd_play_disc();')
functions+='\nvoid saturn_cd_hle_device::reset_repeat_subset(){'+'\n'.join(statements)+'}\n'
tail=r'''
using D=saturn_cd_hle_device;
void issue(D &d,unsigned mode,bool nomove){
 d.cr1=0x1080;d.cr2=150;d.cr3=((mode|(nomove?0x80:0))<<8)|0x80;d.cr4=1;d.cmd_play_disc();
}
void finish(D &d,unsigned want){
 unsigned n=0;while((d.cd_stat&0xf00)!=CD_STAT_PLAY){CHECK(++n<64);d.cd_playdata();}
 d.cd_playdata();
 CHECK((d.cd_next_stat&0xf00)==(want?CD_STAT_SEEK:CD_STAT_PAUSE));
 CHECK(d.cdda_repeat_count==unsigned(bool(want))&&d.cdda_maxrepeat==want);
 CHECK(d.reads>0);
}
int main(){unsigned commands=0,replays=0,defaults=0;
 // A changed, explicit one-sector range legitimately resets the visible
 // repeat counter. No assertion about unchanged-range notification counts.
 for(unsigned old=0;old<16;++old)for(unsigned mode:{0x7fU,0U,1U,2U,3U,4U,5U,6U,7U,8U,9U,10U,11U,12U,13U,14U,15U})
 for(bool nomove:{false,true}){
  D d;d.cd_stat=CD_STAT_PAUSE;d.cd_curfad=d.cd_fad_seek=150;d.cdda_maxrepeat=old;d.cdda_repeat_count=3;d.fadstoplay=5;
  issue(d,mode,nomove);const unsigned want=mode==0x7f?old:mode;
  d.register_state();d.capture();finish(d,want);
  d.cdda_maxrepeat=want^15;d.cdda_repeat_count=14;d.cd_stat=0;d.cd_curfad=999;d.fadstoplay=0;d.restore();
  finish(d,want);++commands;++replays;
 }
 for(unsigned previous=0;previous<256;++previous)for(unsigned count=0;count<16;++count){
  D d;d.cdda_maxrepeat=previous;d.cdda_repeat_count=count;d.reset_repeat_subset();
  CHECK(d.cdda_maxrepeat==0&&d.cdda_repeat_count==0);++defaults;
 }
 std::printf("method-level, unvalidated: %u explicit/no-change repeat commands and actual range-end decisions; %u registered replays; %u actual scalar-reset subset controls\n",commands,replays,defaults);
 std::puts("method-level, unvalidated: real Play/drive/save methods, mock image/sector/audio/serializer; reset subset only, no native reset/tone/range timing or unchanged-range counter qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-repeat-limit-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

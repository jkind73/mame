#!/usr/bin/env python3
"""Extracted SCAN command/drive/audio control, not native PCM or timing qualification."""
from pathlib import Path
import argparse
import re
import sys
import subprocess
import tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutate',choices=['stationary','silent','pause-audible','direction','gain','range','save'])
a=p.parse_args()
fixture=Path(__file__).with_name('check_cd_audio_range.py')
scope={'__file__':str(fixture),'__name__':'scan_scaffold'}
args=sys.argv;sys.argv=sys.argv[:1]
try:exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
finally:sys.argv=args
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace('void set_output_gain(int,double){}','double gain[2]={1,1};void set_output_gain(int ch,double g){gain[ch]=g;}')
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+'void cmd_ffwd_rew_disc();}',1)
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_ffwd_rew_disc()')
regs=extract(functions,'void saturn_cd_hle_device::register_state()')
fields={'m_scan_reverse','m_scan_audible','m_play_start_fad','m_play_end_fad','m_play_range_valid'}
start=extract(source,'void saturn_cd_hle_device::device_start()')
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in fields and m[0] not in regs]
assert len(extra)==5
functions=functions.replace(regs,regs[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
mutations={
 'stationary':('  cd_curfad = next;', '  cd_curfad = current;'),
 'silent':('if (!m_scan_audible ||', 'if (true ||'),
 'pause-audible':('m_scan_audible = state == CD_STAT_PLAY;', 'm_scan_audible = true;'),
 'direction':('m_scan_reverse = (cr1 & 1) != 0;', 'm_scan_reverse = false;'),
 'gain':('constexpr double scan_gain = 0.251188643150958;', 'constexpr double scan_gain = 1.0;'),
 'range':('m_play_range_valid ? std::clamp(m_play_end_fad, first, leadout) : leadout;', 'leadout;'),
 'save':('save_item(NAME(m_scan_reverse));', '')}
if a.mutate:
 old,new=mutations[a.mutate];assert old in functions;functions=functions.replace(old,new,1)
tail=r'''
using D=saturn_cd_hle_device;
void tick(D &d){++d.audio.now;d.cd_sector_cb(0);d.audio.flush();}
bool audible(unsigned fad,unsigned mask){unsigned t=fad<450?0:fad<850?1:2;return (mask>>t)&1;}
void scan(D &d,bool reverse){d.cr1=0x1200|reverse;d.cmd_ffwd_rew_disc();CHECK(d.hirqreg&CMOK);CHECK(d.m_scan_reverse==reverse);}
int main(){unsigned images=0,intervals=0,replays=0;
 for(unsigned mask=0;mask<8;++mask)for(bool playing:{false,true})for(bool reverse:{false,true})
 for(unsigned first:{150U,443U,847U,1337U})for(unsigned count:{1U,2U,3U,9U}){
  D d;d.media.audio_mask=mask;d.cd_speed=2;d.m_play_range_valid=true;d.m_play_start_fad=first;d.m_play_end_fad=first+count;
  unsigned position=reverse?first+count-1:first;d.cd_curfad=position;d.fadstoplay=first+count-position;d.cd_stat=playing?CD_STAT_PLAY:CD_STAT_PAUSE;
  scan(d,reverse);CHECK(d.m_scan_audible==playing);tick(d);CHECK((d.cd_stat&0xf00)==CD_STAT_SCAN&&d.timer.hz==75);
  std::vector<unsigned> expected;
  unsigned budget=16;
  while((d.cd_stat&0xf00)==CD_STAT_SCAN){
   CHECK(budget--);const bool sound=playing&&audible(position,mask);
   CHECK(d.audio.playing==sound);
   if(sound){CHECK(d.audio.gain[0]>0.25118864&&d.audio.gain[0]<0.25118865&&d.audio.gain[1]==d.audio.gain[0]);expected.push_back(position-150);}
   unsigned next=reverse?position-std::min(2U,position-first):position+std::min(2U,first+count-position);
   tick(d);CHECK(d.cd_curfad==next&&d.fadstoplay==first+count-next);CHECK(d.audio.rendered==expected);position=next;++intervals;
  }
  CHECK(d.cd_next_stat==CD_STAT_PAUSE&&(d.hirqreg&PEND)&&!d.audio.playing&&d.read_fads.empty());
  CHECK(d.audio.gain[0]==1&&d.audio.gain[1]==1&&!d.m_scan_audible);tick(d);CHECK(d.timer.hz==60);++images;
 }
 // Mid-SCAN direction switches retain entry audibility. Save registrations
 // preserve direction, entry policy and programmed bounds before the next step.
 for(bool playing:{false,true})for(bool reverse:{false,true})for(unsigned mask=0;mask<8;++mask){
  D d;d.media.audio_mask=mask;d.m_play_range_valid=true;d.m_play_start_fad=440;d.m_play_end_fad=470;d.cd_curfad=455;d.cd_stat=playing?CD_STAT_PLAY:CD_STAT_PAUSE;
  scan(d,!reverse);tick(d);scan(d,reverse);CHECK(d.m_scan_audible==playing);tick(d);
  d.register_state();d.capture();d.cd_scan_step();const auto next=d.cd_curfad;
  d.m_scan_reverse=!reverse;d.m_scan_audible=!playing;d.m_play_start_fad=150;d.m_play_end_fad=1350;d.restore();
  CHECK(d.m_scan_reverse==reverse&&d.m_scan_audible==playing&&d.m_play_start_fad==440&&d.m_play_end_fad==470);
  d.cd_scan_step();CHECK(d.cd_curfad==next);++replays;
  d.cd_change_status(CD_STAT_PAUSE);CHECK(!d.audio.playing&&d.audio.gain[0]==1&&!d.m_scan_audible);
 }
 // Retarget SCAN while its BUSY transition is pending; entry policy is stable.
 {D d;d.media.audio_mask=7;d.cd_stat=CD_STAT_PLAY;scan(d,false);scan(d,true);CHECK(d.m_scan_audible&&d.m_scan_reverse);}
 std::printf("method-level, unvalidated: %u SCAN images, %u interval steps, %u registered direction/range replays; no data-sector reads\n",images,intervals,replays);
}
'''
with tempfile.TemporaryDirectory(prefix='cd-scan-') as tmp:
    cpp=Path(tmp)/'probe.cpp';exe=Path(tmp)/'probe';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
"""Held-info host transfer preserves drive producer/completion/repeat state."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_directory_clear.py')
scope={'__file__':str(fixture),'__name__':'file_info_drive_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers,builders=(scope[k] for k in ('source','head','functions','extract','helpers','builders'))
head='constexpr unsigned CD_STAT_STANDBY=0x200;\n#include <stdexcept>\nstruct emu_fatalerror:std::runtime_error{using std::runtime_error::runtime_error;};\n'+head
head=head.replace('void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}', 'void cr_standard_return(uint16_t);')
dev=extract(head,'struct saturn_cd_hle_device')
head=head.replace(dev,dev[:-1]+r'''
 uint8_t finfbuf[12]{},tocbuf[408]{},subqbuf[10]{},subrwbuf[24]{};uint32_t xfercount=0;
 void cmd_get_target_file_info();uint16_t dataxfer_word_r();
 int get_track_index(uint32_t){return 1;}int sega_cdrom_get_adr_control(int){return 0x41;}
}''',1)
head+='\nuint16_t get_u16be(const uint8_t *p){return (uint16_t(p[0])<<8)|p[1];}\n'
functions+='\n'+'\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cmd_get_target_file_info()', 'inline u16 saturn_cd_hle_device::dataxfer_word_r()', 'void saturn_cd_hle_device::cr_standard_return('))
start=extract(source,'void saturn_cd_hle_device::device_start()');registered=extract(functions,'void saturn_cd_hle_device::register_state()')
wanted={'finfbuf','xfercount','m_file_info_words'}
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in wanted and m[0] not in registered]
functions=functions.replace(registered,registered[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
void setup(D &d,unsigned producer,unsigned phase,unsigned repeat){
 root(d,2048);child(d,3,6144,2048);d.read_new_dir(0xffffff);d.read_new_dir(2);
 d.cr1=0x7400;d.cr2=d.cr3=0;d.cr4=2;d.cmd_read_file();
 d.media.type=cdrom_file::CD_TRACK_MODE1_RAW;d.media.bytes[15]=1;d.media.reads=0;
 d.cd_stat=phase;d.playtype=producer;d.cdda_repeat_count=repeat;d.cdda_maxrepeat=repeat;d.hirqreg=0;
}
std::vector<uint16_t> packet(D &d,unsigned fid){std::vector<uint16_t> v;
 for(unsigned i=fid==0xffffff?2:fid;i<(fid==0xffffff?d.curdir.size():fid+1);++i){const auto &f=d.curdir[i];
  v.push_back(f.firstfad>>16);v.push_back(f.firstfad);v.push_back(f.length>>16);v.push_back(f.length);v.push_back((f.file_unit_size<<8)|f.interleave_gap_size);v.push_back((f.file_number<<8)|f.flags);
 }return v;
}
void issue(D &d,unsigned fid){d.cr1=0x7300;d.cr2=0;d.cr3=fid>>16;d.cr4=fid;d.cmd_get_target_file_info();}
using Outcome=std::array<int64_t,7>;
Outcome finish(D &d,const std::vector<uint16_t> &v,unsigned producer,unsigned phase,unsigned repeat){
 if(phase==CD_STAT_PLAY){d.cd_playdata();CHECK(d.media.reads==1&&d.cd_curfad==4001&&d.fadstoplay==0&&(d.hirqreg&PEND));CHECK(bool(d.hirqreg&EFLS)==bool(producer));}
 for(unsigned i=2;i<v.size();++i)CHECK(d.dataxfer_word_r()==v[i]);
 CHECK(d.m_host_transfer_active&&d.xfertype==D::XFERTYPE_INVALID&&d.xferdnum==v.size()*2);
 d.cmd_end_data_transfer();CHECK(!d.m_host_transfer_active&&d.cr2==v.size()&&d.cdda_repeat_count==repeat&&d.playtype==producer);
 return {d.cd_stat,d.cd_next_stat,d.cd_curfad,d.fadstoplay,d.hirqreg,d.freeblocks,d.partitions[0].numblks};
}
int main(){unsigned images=0,replays=0,completions=0,controls=0;
 for(unsigned producer:{0U,1U})for(unsigned phase:{CD_STAT_PLAY,CD_STAT_PAUSE,CD_STAT_SEEK,CD_STAT_STANDBY})for(unsigned repeat=0;repeat<15;++repeat)for(unsigned fid:{0U,1U,2U,0xffffffU}){
  auto p=std::make_unique<D>();auto &d=*p;setup(d,producer,phase,repeat);const auto v=packet(d,fid);
  const auto target=d.cd_fad_seek;const auto next=d.cd_next_stat;const auto remaining=d.fadstoplay,position=d.cd_curfad;const auto free=d.freeblocks;
  issue(d,fid);CHECK(d.m_host_transfer_active&&d.cr2==v.size()&&d.cdda_maxrepeat==repeat);
  CHECK(d.cd_fad_seek==target&&d.cd_next_stat==next&&d.fadstoplay==remaining&&d.cd_curfad==position&&d.freeblocks==free&&!d.media.reads&&(d.cd_stat&0xf00)==phase);
  d.cr_standard_return(d.cd_stat);CHECK((d.cr1&0xf)==repeat&&bool(d.cr1&0x80)==bool(producer));
  CHECK(d.dataxfer_word_r()==v[0]&&d.dataxfer_word_r()==v[1]);
  d.register_state();d.capture();const auto expected=finish(d,v,producer,phase,repeat);
  d.playtype=producer^1;d.cdda_repeat_count=15;d.cdda_maxrepeat=15;d.fadstoplay=0;d.xfercount=0;d.m_file_info_words=0;std::memset(d.finfbuf,0xff,12);d.media.reads=0;
  d.restore();d.cr_standard_return(d.cd_stat);CHECK((d.cr1&0xf)==repeat&&bool(d.cr1&0x80)==bool(producer));CHECK(finish(d,v,producer,phase,repeat)==expected);++images;++replays;if(phase==CD_STAT_PLAY&&producer)++completions;
 }
 for(unsigned producer:{0U,1U})for(unsigned repeat=0;repeat<15;++repeat)for(unsigned reason=0;reason<3;++reason){auto p=std::make_unique<D>();auto &d=*p;setup(d,producer,CD_STAT_PLAY,repeat);
  if(reason==0){issue(d,2);d.dataxfer_word_r();}if(reason==1)d.m_file_info_invalidated=true;
  const auto cursor=d.xfercount;issue(d,reason==2?99:2);CHECK(d.playtype==producer&&d.cdda_repeat_count==repeat&&d.cdda_maxrepeat==repeat&&d.cd_curfad==4000&&d.fadstoplay==1&&!d.media.reads&&d.xfercount==cursor);
  CHECK(reason==0?(d.cr1&CD_STAT_WAIT):(d.cr1&0xff00)==CD_STAT_REJECT);++controls;
 }
 std::printf("method-level, unvalidated: %u file-info/producer/phase/repeat images; %u registered pool/host/drive replays; %u continuing-file EFLS completions; %u WAIT/rejection controls\n",images,replays,completions,controls);
 std::puts("method-level, unvalidated: actual metadata/parser/ports/report/drive/filter/End/save methods, fixed report track metadata and authored image; counter seeds diagnostic, no native IRQ/CDDA/filesystem arbitration/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-info-drive-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

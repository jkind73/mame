#!/usr/bin/env python3
"""Tray-open stop/notification order and resident host transfers; method-level, unvalidated."""
from pathlib import Path
import re
import subprocess
import tempfile

def prefix(name):
    fixture=Path(__file__).with_name(name)
    scope={'__file__':str(fixture),'__name__':'tray_stop_scaffold'}
    exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
    return fixture,scope

def run(head,functions,tail,label):
    with tempfile.TemporaryDirectory(prefix='impl-cd-tray-'+label+'-') as directory:
        cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
        subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)

fixture,scope=prefix('check_cd_drive_phase_save.py')
source,head,extract=(scope[k] for k in ('source','head','extract'))
head=head.replace('struct Media{bool inserted=true;', 'struct Media{unsigned unloads=0;void unload(){inserted=false;++unloads;}bool inserted=true;')
a=head.index(' struct Audio{');b=head.index('\n Media *',a)
head=head[:a]+''' struct Audio{unsigned calls=0,stops=0,starts=0;bool playing=true;
 void pause_audio(int){++calls;}void stop_audio(){++calls;++stops;playing=false;}void start_audio(unsigned,unsigned){++calls;++starts;playing=true;}}audio;'''+head[b:]
head=head.replace('void update_hirq(){++irqs;}', 'void (*notice)(saturn_cd_hle_device&)=nullptr;void update_hirq(){++irqs;if(notice)notice(*this);}')
at=head.rfind('};');head=head[:at]+'''
 bool m_file_info_invalidated=false,m_host_transfer_active=true;uint8_t tray_is_closed=1,cd_speed=2;
 void set_tray_open();void set_tray_close();
'''+head[at:]
head+='\nconstexpr unsigned DCHG=0x20,CD_STAT_OPEN=0x600,CD_STAT_NODISC=0x700;\n'
selected=scope['selected']|{'m_file_info_invalidated','tray_is_closed','cd_speed'}
regs=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',scope['start']) if m[1] in selected]
functions='void saturn_cd_hle_device::register_state(){\n'+'\n'.join(regs)+'\n}\n'
functions+='\n'.join(extract(source,'void saturn_cd_hle_device::'+name+'(') for name in ('cd_playdata','cd_change_status','set_tray_open','set_tray_close'))
tail=r'''
using D=saturn_cd_hle_device;
unsigned notices=0;uint16_t pending_causes=0;
void notice(D &d){
 CHECK(d.hirqreg==(pending_causes|DCHG|EFLS)&&(d.cd_stat&0xf00)!=CD_STAT_OPEN);
 CHECK(d.m_file_info_invalidated&&!d.fadstoplay&&!d.playtype&&!d.buffull_temp_pause&&!d.m_seek_in_progress&&!d.m_seek_ticks_left);
 CHECK(!d.audio.playing&&d.audio.stops==1);++notices;
}
int main(){unsigned cases=0,replays=0;
 for(unsigned status:{CD_STAT_BUSY,CD_STAT_PAUSE,CD_STAT_PLAY,CD_STAT_SEEK,CD_STAT_NODISC})
 for(unsigned next:{CD_STAT_PAUSE,CD_STAT_PLAY,CD_STAT_SEEK})for(bool paused:{false,true})
 for(unsigned remaining:{0U,1U,1234567U})for(unsigned full:{0U,1U})for(unsigned file:{0U,1U})
 for(unsigned seek_ticks:{0U,1U,789U})for(unsigned pending:{0U,4U,0x220U,0xffffU})for(bool inserted:{false,true}){
  D d;d.cd_stat=status;d.cd_next_stat=next;d.m_status_change_in_progress=status==CD_STAT_BUSY;
  d.m_seek_in_progress=status==CD_STAT_SEEK||next==CD_STAT_SEEK;d.m_seek_ticks_left=seek_ticks;
  d.fadstoplay=remaining;d.buffull=full;d.buffull_temp_pause=paused;d.playtype=file;
  d.cd_seek_stat=CD_STAT_PLAY;d.cdda_maxrepeat=15;d.hirqreg=pending;
  const unsigned fad=d.cd_curfad;d.notice=notice;pending_causes=pending;
  d.set_tray_open();d.notice=nullptr;
  CHECK(!d.tray_is_closed&&!d.media.inserted&&d.media.unloads==1&&d.cd_stat==CD_STAT_BUSY&&d.cd_next_stat==CD_STAT_OPEN&&d.m_status_change_in_progress);
  CHECK(d.buffull==full&&d.cd_curfad==fad&&d.irqs==1);
  d.set_tray_open();CHECK(d.irqs==1&&d.audio.stops==1&&d.media.unloads==1);
  d.register_state();d.capture();for(auto &e:d.entries)std::memset(e.address,0xa5,e.bytes);
  const unsigned irqs=d.irqs;d.restore();CHECK(d.irqs==irqs&&!d.tray_is_closed&&d.m_file_info_invalidated&&!d.fadstoplay&&!d.playtype&&!d.buffull_temp_pause&&!d.m_seek_in_progress&&!d.m_seek_ticks_left);++replays;
  for(unsigned i=0;i<4;++i)d.cd_playdata();CHECK(d.cd_stat==CD_STAT_OPEN&&!d.reads&&!d.audio.starts);
  d.media.inserted=inserted;d.hirqreg=0;d.set_tray_close();CHECK(d.tray_is_closed&&d.hirqreg==DCHG&&d.m_file_info_invalidated);
  d.buffull=0;for(unsigned i=0;i<32;++i)d.cd_playdata();
  CHECK(d.cd_stat==(inserted?CD_STAT_PAUSE:CD_STAT_NODISC)&&!d.reads&&!d.audio.starts&&!d.audio.playing&&d.audio.stops==1&&d.cd_curfad==fad);
  CHECK(!d.fadstoplay&&!d.playtype&&!d.buffull_temp_pause&&!d.m_seek_in_progress&&!d.m_seek_ticks_left);
  const auto closed_irqs=d.irqs;d.set_tray_close();CHECK(d.irqs==closed_irqs);++cases;
 }
 std::printf("method-level, unvalidated: %u tray stop/phase/reopen images; %u pre-OPEN dual-cause observations; %u registered stopped-drive replays; no autonomous sector/audio restart\n",cases,notices,replays);
 std::puts("method-level, unvalidated: actual tray/drive/status/registration methods, mocked media/sector/audio/serializer; existing BUSY staging retained; no native timer or audible-sample latency qualification");
}
'''
run(head,functions,tail,'drive')

# Exercise actual outstanding sector interfaces independently of the drive mock.
fixture,scope=prefix('check_cd_raw_put.py')
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace(' struct Media {',' struct Media {bool inserted=true;bool exists(){return inserted;}void unload(){inserted=false;}')
at=head.rfind('};');head=head[:at]+r'''
 struct Audio{unsigned stops=0;void stop_audio(){++stops;}}audio;Audio *m_cdda=&audio;
 uint8_t tray_is_closed=1,cd_speed=2,playtype=1,cdda_repeat_count=0;
 bool m_file_info_invalidated=false,buffull_temp_pause=true,m_seek_in_progress=true,m_status_change_in_progress=false;
 int m_seek_ticks_left=123;uint16_t cd_next_stat=0;
 void set_tray_open();void set_tray_close();void cd_change_status(uint16_t);
'''+head[at:]
head+='\nusing u16=uint16_t;\n#define LOGSTATUS(...) ((void)0)\n#define popmessage(...) ((void)0)\nconstexpr unsigned EFLS=0x200,DCHG=0x20,CD_STAT_OPEN=0x600,CD_STAT_NODISC=0x700,CD_STAT_PAUSE=0x100,CD_STAT_BUSY=0,CD_STAT_SEEK=0x400,CD_STAT_PERI=0x2000;\n'
functions+='\n'+'\n'.join(extract(source,'void saturn_cd_hle_device::'+name+'(') for name in ('set_tray_open','set_tray_close','cd_change_status'))
helpers=fixture.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0]
tail=r'''
void openclose(D &d,bool inserted){
 const auto type=d.xfertype32;const auto cursor=d.xferoffs;const auto sector=d.xfersect;const auto transferred=d.xferdnum;const auto *part=d.transpart;
 const auto words=d.xfersectnum;const auto first=d.xfersectpos;const auto free=d.freeblocks;const auto full=d.buffull;const auto causes=d.hirqreg;
 d.set_tray_open();CHECK(d.hirqreg==(causes|DCHG|EFLS)&&d.audio.stops==1);
 CHECK(d.m_host_transfer_active&&d.xfertype32==type&&d.xferoffs==cursor&&d.xfersect==sector&&d.xferdnum==transferred&&d.transpart==part&&d.xfersectnum==words&&d.xfersectpos==first&&d.freeblocks==free&&d.buffull==full);
 d.media.inserted=inserted;d.set_tray_close();CHECK(d.m_host_transfer_active&&d.m_file_info_invalidated&&!d.fadstoplay&&!d.playtype&&!d.buffull_temp_pause&&!d.m_seek_in_progress&&!d.m_seek_ticks_left);
}
int main(){unsigned puts=0,gets=0;
 for(unsigned kind=0;kind<3;++kind)for(unsigned fmt=0;fmt<4;++fmt)for(unsigned phase=0;phase<3;++phase)for(bool inserted:{false,true}){
  auto d=std::make_unique<D>();seed(*d,fmt,fmt);const auto input=packets(kind);start(*d);
  const unsigned count=lengths[fmt]/2,cut=phase==0?0:phase==1?1:count;
  write(*d,input,fmt,fmt,0,cut);openclose(*d,inserted);pending(*d);
  write(*d,input,fmt,fmt,cut,count);end(*d,count);check(*d,expected(input,fmt,fmt,count),fmt,true);++puts;
 }
 for(bool remove:{false,true})for(unsigned kind=0;kind<3;++kind)for(unsigned fmt=0;fmt<4;++fmt)
 for(unsigned phase=0;phase<3;++phase)for(bool inserted:{false,true}){
  auto d=std::make_unique<D>();seed(*d,fmt,3);const auto input=packets(kind);start(*d);write(*d,input,3,3,0,1176);end(*d,1176);
  format(*d,fmt,0xff);d->cr1=remove?0x6300:0x6100;d->cr2=1;d->cr3=7<<8;d->cr4=2;
  if(remove)d->cmd_get_and_delete_sector_data();else d->cmd_get_sector_data();
  std::vector<uint32_t>want;for(const auto &r:input)for(unsigned pos=0;pos<getsize(r,fmt);pos+=4)want.push_back(get_u32be(r.data()+getoff(r,fmt)+pos));
  const unsigned cut=phase==0?0:phase==1?1:want.size();for(unsigned i=0;i<cut;++i)CHECK(d->dataxfer_long_r()==want[i]);
  openclose(*d,inserted);for(unsigned i=cut;i<want.size();++i)CHECK(d->dataxfer_long_r()==want[i]);
  CHECK(d->xferdnum==want.size()*4);d->cmd_end_data_transfer();CHECK(d->cr2==want.size()*2&&!d->m_host_transfer_active&&d->freeblocks==(remove?199:197)&&d->partitions[7].numblks==(remove?1:3));++gets;
 }
 std::printf("method-level, unvalidated: %u outstanding raw PUT continuations; %u GET/GETDELETE continuations through tray stop/close\n",puts,gets);
 std::puts("method-level, unvalidated: actual host reservation/port/End/routing methods, mock media/report/IRQ/audio; no native transport timing or media-identity qualification");
}
'''
run(head,functions,helpers+tail,'host')

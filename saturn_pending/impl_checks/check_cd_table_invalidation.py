#!/usr/bin/env python3
"""Tray-invalidated command table with retained host backing; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_held_window.py')
scope={'__file__':str(fixture),'__name__':'table_invalidation_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions,builders,source,extract=(scope[k] for k in ('head','functions','builders','source','extract'))
head=head.replace('void update_hirq(){++irqs;}', 'void (*notice)(saturn_cd_hle_device&)=nullptr;void update_hirq(){++irqs;if(notice)notice(*this);}')
head=head.replace('reads.push_back(fad);','reads.push_back(fad);if(!image.exists())return;if(expect_invalid_reads)CHECK(m_file_info_invalidated);')
at=head.rfind('};');head=head[:at]+r'''
 struct Image{bool inserted=true;unsigned unloads=0;bool exists(){return inserted;}void unload(){inserted=false;++unloads;}}image;
 Image *m_cdrom_image=&image;uint8_t tray_is_closed=1,cd_speed=2;bool expect_invalid_reads=false;
 bool buffull_temp_pause=false,m_seek_in_progress=false;
 struct Audio{unsigned stops=0;void stop_audio(){++stops;}}audio;Audio *m_cdda=&audio;
 void set_tray_open();void set_tray_close();
'''+head[at:]
head+='\nconstexpr unsigned DCHG=0x20,CD_STAT_OPEN=0x600,CD_STAT_NODISC=0x700,CD_STAT_PAUSE=0x100;\n'
functions+='\n'+extract(source,'void saturn_cd_hle_device::set_tray_open()')+'\n'+extract(source,'void saturn_cd_hle_device::set_tray_close()')
helpers=fixture.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0]
tail=r'''
unsigned notices=0;
void notice(D &d){CHECK(d.m_file_info_invalidated&&(d.hirqreg&DCHG));++notices;}
void denied(D &d,unsigned command,unsigned fid,unsigned pending){const auto fad=d.cd_curfad;const auto next=d.cd_next_stat;const auto conn=d.cddevicenum;d.hirqreg=pending;issue(d,command,fid);
 CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==(pending|CMOK)&&d.cd_curfad==fad&&d.cd_next_stat==next&&d.cddevicenum==conn&&d.m_file_info_invalidated);}
int main(){unsigned streams=0,reloads=0,refusals=0;
 for(auto spec:std::array<std::pair<unsigned,unsigned>,4>{{{17,2},{600,2},{600,300},{600,599}}}){
  const unsigned size=spec.first,first=spec.second,count=std::min(254U,size-first),words=count*6;
  for(unsigned cut:{0U,1U,5U,6U,words/2,words-1,words})for(unsigned pending:{0U,2U,0x220U,0xffffU})for(bool inserted:{false,true}){
   auto ptr=std::make_unique<D>();D &d=*ptr;seed(d,size);issue(d,0x7100,first);std::vector<u16> expected;
   for(unsigned i=first;i<first+count;++i){const auto p=packet(d.curdir[i]);expected.insert(expected.end(),p.begin(),p.end());}
   const auto cache=d.curdir;const auto counts=std::array<int,2>{d.numfiles,d.firstfile};d.register_state();issue(d,0x7300,0xffffff);for(unsigned i=0;i<cut;++i)CHECK(d.dataxfer_word_r()==expected[i]);
   const auto cursor=d.xfercount;const auto type=d.xfertype;d.hirqreg=pending;d.notice=notice;d.set_tray_open();d.notice=nullptr;
   CHECK(d.m_file_info_invalidated&&d.hirqreg==(pending|DCHG)&&!d.tray_is_closed&&!d.image.exists()&&d.image.unloads==1);
   CHECK(d.curdir.size()==size&&d.m_file_scope_start==first&&d.m_file_info_words==words&&d.xfercount==cursor&&d.xferdnum==cut*2&&d.xfertype==type&&d.m_host_transfer_active&&(counts==std::array<int,2>{d.numfiles,d.firstfile}));
   for(unsigned i=0;i<size;++i)CHECK(equal(d.curdir[i],cache[i]));
   const auto irq=d.irqs;d.set_tray_open();CHECK(d.irqs==irq&&d.image.unloads==1);
   const unsigned causes=pending|DCHG;d.hirqreg=causes;d.cmd_get_file_scope();CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==(causes|CMOK));
   denied(d,0x7000,0,causes);denied(d,0x7100,first,causes);denied(d,0x7400,first,causes);refusals+=4;
   d.hirqreg=causes;issue(d,0x7300,first);CHECK(d.cr1==(d.cd_stat|CD_STAT_WAIT)&&d.hirqreg==(causes|CMOK)&&d.m_host_transfer_active); // owner arbitration still first
   d.capture();d.m_file_info_invalidated=false;d.curdir.clear();d.curdir.shrink_to_fit();d.m_file_scope_start=999;d.m_file_info_words=0;d.m_host_transfer_active=false;d.xfertype=D::XFERTYPE_INVALID;d.xfercount=d.xferdnum=0;std::memset(d.finfbuf,0xe5,sizeof(d.finfbuf));
   const auto before=d.irqs;d.restore();CHECK(d.irqs==before&&d.m_file_info_invalidated&&d.curdir.size()==size&&d.m_file_scope_start==first&&d.m_file_info_words==words&&d.m_host_transfer_active&&d.xferdnum==cut*2);
   for(unsigned i=cut;i<words;++i)CHECK(d.dataxfer_word_r()==expected[i]);end(d,words);CHECK(d.m_file_info_invalidated);denied(d,0x7300,0,causes);denied(d,0x7300,0xffffff,causes);refusals+=2;
   d.image.inserted=inserted;d.set_tray_close();CHECK(d.tray_is_closed&&d.m_file_info_invalidated&&d.curdir.size()==size);d.cmd_get_file_scope();CHECK(d.cr1==CD_STAT_REJECT);++refusals;
   const auto closed_irq=d.irqs;d.set_tray_close();CHECK(d.irqs==closed_irq&&d.m_file_info_invalidated);
   if(inserted){root(d,2048);child(d,1,2048,2048);d.expect_invalid_reads=true;issue(d,0x7000,0xffffff);d.expect_invalid_reads=false;
    CHECK(!d.m_file_info_invalidated&&d.curdir.size()==3&&d.m_file_scope_start==2);check_scope(d,2,1,true);++reloads;}
   ++streams;
  }
 }
 for(unsigned size:{0U,2U,3U,600U}){auto ptr=std::make_unique<D>();auto &d=*ptr;seed(d,size);d.set_tray_open();CHECK(d.m_file_info_invalidated&&d.curdir.size()==size&&!d.m_host_transfer_active);d.cmd_get_file_scope();CHECK(d.cr1==CD_STAT_REJECT);++refusals;}
 std::printf("method-level, unvalidated: %u partial/EOF host streams through tray invalidation and registered replay; %u rejected stale-table accesses; %u fresh-root recovery controls; %u pre-DCHG invalidation observations\n",streams,refusals,reloads,notices);
 std::puts("method-level, unvalidated: actual tray/filesystem/parser/word/End/registration methods; mock image lifecycle, sector IO, report and IRQ; native tray/EFLS timing, producer cancellation, media identity and live cache replacement excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-table-invalidation-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+builders+helpers+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
fixture=Path(__file__).with_name('check_cd_selector_reset.py')
scope={'__file__':str(fixture),'__name__':'table_invalidation_reset_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
tail=r'''
int main(){auto d=std::make_unique<saturn_cd_hle_device>();d->m_file_info_invalidated=true;d->curdir={1,2,3};d->device_reset();CHECK(!d->m_file_info_invalidated&&d->curdir.empty());std::puts("method-level, unvalidated: hard reset clears invalidation latch and cache together");}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-table-invalidation-reset-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(scope['head']+scope['functions']+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

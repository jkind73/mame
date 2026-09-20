#!/usr/bin/env python3
"""Held filesystem windows, bounded packets and registered continuation; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
fixture=Path(__file__).with_name('check_cd_directory_save.py')
scope={'__file__':str(fixture),'__name__':'held_window_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
head='#include <map>\n#define LOGSTATUS(...) ((void)0)\n#define popmessage(...) ((void)0)\n'+head
suffix=head[head.rfind('};')+2:]
head=head[:head.rfind('};')]+extract(header,'struct filterT')+r''';
 filterT filters[24]{};filterT *cddevice=nullptr;int cddevicenum=255;
 uint32_t cd_curfad=900,fadstoplay=17;uint16_t cd_next_stat=0;
 int sectlenin=2048,m_seek_ticks_left=0;bool m_status_change_in_progress=false;
 std::map<uint32_t,std::array<uint8_t,2048>>media;std::vector<uint32_t>reads;
 void cd_readblock(uint32_t fad,uint8_t *out){reads.push_back(fad);const auto it=media.find(fad);if(it!=media.end())std::copy(it->second.begin(),it->second.end(),out);}
 void cd_connect_cddevice(uint8_t);void cd_disconnect_filter_input(uint8_t);void cd_change_status(u16);
 void cmd_read_directory();void cmd_get_file_scope();void cmd_read_file();void cmd_change_directory();
 void read_new_dir(uint32_t);void make_dir_current(uint32_t,uint32_t);
};
constexpr unsigned MAX_FILTERS=24,MAX_DIR_SIZE=256*1024,EFLS=0x200,CD_STAT_BUSY=0,CD_STAT_PLAY=0x300,CD_STAT_SEEK=0x400,CD_STAT_PERI=0x2000;
uint32_t get_u32le(const uint8_t *p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
uint16_t get_u16le(const uint8_t *p){return p[0]|(p[1]<<8);}
'''
head+=suffix
for name in ('cmd_read_directory','cmd_get_file_scope','cmd_read_file','cmd_change_directory','cd_connect_cddevice','cd_disconnect_filter_input','cd_change_status','read_new_dir','make_dir_current'):
    functions+='\n'+extract(source,'void saturn_cd_hle_device::'+name+'(')
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)
builders=fixture.read_text().split("\ntail=r'''",1)[1].split('std::vector<u16> finish(',1)[0]
parser=Path(__file__).with_name('check_cd_directory_extent.py')
builders+='\n'+parser.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0]
tail=r'''
std::array<u16,6> packet(const D::direntryT &r){return {u16(r.firstfad>>16),u16(r.firstfad),u16(r.length>>16),u16(r.length),u16((r.file_unit_size<<8)|r.interleave_gap_size),u16((r.file_number<<8)|r.flags)};}
void seed(D &d,unsigned records){d.curdir.clear();for(unsigned i=0;i<records;++i){d.curdir.push_back(record(i,17));d.curdir.back().flags=i<2?2:0;}d.numfiles=records;d.firstfile=2;d.cd_stat=0x100;}
void issue(D &d,unsigned command,unsigned fid,unsigned input=3,unsigned offset=0){d.cr1=command|(offset>>16);d.cr2=offset;d.cr3=(input<<8)|(fid>>16);d.cr4=fid;
 switch(command){case 0x7100:d.cmd_read_directory();break;case 0x7300:d.cmd_get_target_file_info();break;case 0x7400:d.cmd_read_file();break;case 0x7000:d.cmd_change_directory();break;default:CHECK(false);}}
void check_scope(D &d,unsigned first,unsigned count,bool end){const auto status=d.cd_stat;d.hirqreg=0;d.cmd_get_file_scope();CHECK(d.cr1==status&&d.cr2==count&&d.cr3==((unsigned(end)<<8)|(first>>16))&&d.cr4==u16(first)&&d.hirqreg==CMOK);}
void end(D &d,unsigned words){CHECK(d.xfertype==D::XFERTYPE_INVALID&&d.m_host_transfer_active&&d.xfercount==0&&d.xferdnum==words*2);d.dataxfer_word_r();CHECK(d.xferdnum==words*2);d.cmd_end_data_transfer();CHECK(d.cr2==words&&!d.m_host_transfer_active&&d.xferdnum==0);}
int main(){unsigned windows=0,records=0,refusals=0,replays=0,controls=0;
 for(unsigned size:{2U,3U,17U,255U,256U,257U,511U,512U,600U,7680U}){
  auto ptr=std::make_unique<D>();D &d=*ptr;seed(d,size);d.register_state();check_scope(d,size>2?2:0,std::min(254U,size-2),size<=256);
  for(unsigned requested:{0U,1U,2U,3U,254U,255U,256U,300U,510U,7679U}){
   const unsigned first=std::max(2U,requested);if(first>=size&&size>2)continue;
   const unsigned count=first<size?std::min(254U,size-first):0;const unsigned words=count*6;
   d.playtype=0;d.hirqreg=0;issue(d,0x7100,requested);CHECK(d.hirqreg==(CMOK|EFLS)&&d.cddevicenum==3);check_scope(d,count?first:0,count,first+count>=size);++windows;
   for(unsigned fid:{0U,1U,first,first+count-1,first+count,2U,0x10002U}){
    const bool held=fid<size&&(fid<2||(fid>=first&&fid-first<count));d.hirqreg=0;issue(d,0x7300,fid);
    if(held){CHECK(d.cr2==6&&d.m_host_transfer_active);for(auto word:packet(d.curdir[fid]))CHECK(d.dataxfer_word_r()==word);end(d,6);++records;}
    else {CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK&&!d.m_host_transfer_active);++refusals;}
    const auto oldfad=d.cd_curfad;d.playtype=0;d.hirqreg=0;issue(d,0x7400,fid,3);
    if(held)CHECK(d.playtype==1&&d.cd_curfad==d.curdir[fid].firstfad&&d.filters[3].fid==d.curdir[fid].file_number);
    else {CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK&&!d.playtype&&d.cd_curfad==oldfad);++refusals;}
    d.playtype=0;
   }
   d.hirqreg=0;issue(d,0x7300,0xffffff);
   if(!count){CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK&&!d.m_host_transfer_active);++refusals;continue;}
   CHECK(d.cr2==words&&d.m_file_info_words==words&&d.m_host_transfer_active);
   // The existing host-owner WAIT must precede an unheld-ID rejection.
   d.hirqreg=0;issue(d,0x7300,0x10002);CHECK(d.cr1==(d.cd_stat|CD_STAT_WAIT)&&d.hirqreg==CMOK&&d.m_host_transfer_active&&d.m_file_info_words==words);++controls;
   std::vector<u16> expected;for(unsigned i=first;i<first+count;++i){const auto p=packet(d.curdir[i]);expected.insert(expected.end(),p.begin(),p.end());}
   for(auto word:expected)CHECK(d.dataxfer_word_r()==word);end(d,words);
   for(unsigned cut:{0U,1U,5U,6U,words/2,words-1,words}){
    issue(d,0x7300,0xffffff);CHECK(d.cr2==words);for(unsigned i=0;i<cut;++i)CHECK(d.dataxfer_word_r()==expected[i]);d.capture();
    d.curdir.clear();d.curdir.shrink_to_fit();d.curdir.push_back(record(999,255));d.m_file_scope_start=0xabcdef;d.m_file_info_words=0;d.xfertype=D::XFERTYPE_INVALID;d.xfercount=d.xferdnum=0;d.m_host_transfer_active=false;std::memset(d.finfbuf,0xe5,sizeof(d.finfbuf));
    const auto irqs=d.irqs;d.restore();CHECK(d.irqs==irqs&&d.curdir.size()==size&&d.m_file_scope_start==first&&d.m_file_info_words==words&&d.m_host_transfer_active);
    for(unsigned i=cut;i<words;++i)CHECK(d.dataxfer_word_r()==expected[i]);end(d,words);check_scope(d,first,count,first+count>=size);++replays;
   }
  }
 }
 // Empty table is not an empty directory. Self/parent alone is a valid table,
 // but provides no ordinary-record bulk transfer (checked above).
 {auto ptr=std::make_unique<D>();auto &d=*ptr;d.cmd_get_file_scope();CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK);issue(d,0x7300,0xffffff);CHECK(d.cr1==CD_STAT_REJECT&&!d.m_host_transfer_active);++controls;}
 // A held child directory is accessible; an unheld one is not. Actual parser
 // replacement restores the initial window and does not shift self/parent.
 {auto ptr=std::make_unique<D>();auto &d=*ptr;seed(d,600);d.curdir[2].flags=d.curdir[300].flags=2;d.curdir[300].firstfad=1000;d.curdir[300].length=2048;
  record(d.media[1000].data(),1000,2048,true,0);record(d.media[1000].data()+34,1000,2048,true,1);
  issue(d,0x7100,300);d.hirqreg=0;issue(d,0x7000,2);CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK&&d.curdir.size()==600&&d.m_file_scope_start==300&&d.reads.empty());
  issue(d,0x7000,0);CHECK(d.m_file_scope_start==300&&d.reads.empty());issue(d,0x7000,300);CHECK(d.m_file_scope_start==2&&d.curdir.size()==2&&d.reads.size()==1);check_scope(d,0,0,true);++controls;
  root(d,2048);child(d,3,6144,2048);d.m_file_scope_start=300;issue(d,0x7000,0xffffff);CHECK(d.m_file_scope_start==2&&d.curdir.size()==3);check_scope(d,2,1,true);++controls;
 }
 // Transfer length is latched, not recomputed from a later cache window.
 // Payload when the cache is replaced mid-transfer is deliberately not asserted.
 {auto ptr=std::make_unique<D>();auto &d=*ptr;seed(d,600);issue(d,0x7300,0xffffff);CHECK(d.cr2==1524);issue(d,0x7100,599);check_scope(d,599,1,true);for(unsigned i=0;i<1524;++i)d.dataxfer_word_r();end(d,1524);++controls;}
 std::printf("method-level, unvalidated: %u held windows; %u self/parent/single packets; %u unheld/empty refusals; %u actual registered scope/length/cache continuations; %u ownership/parser/latched-length controls\n",windows,records,refusals,replays,controls);
 std::puts("method-level, unvalidated: actual filesystem commands, parser, word/End and registered fields; mocked media/report/IRQ/serializer; beyond-directory holds, live-cache payload replacement, asynchronous FLS, buffer clearing and native save/title acceptance excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-held-window-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
# Exercise the actual hard reset separately, using the established reset scaffold.
fixture=Path(__file__).with_name('check_cd_selector_reset.py')
scope={'__file__':str(fixture),'__name__':'held_window_reset_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
tail=r'''
int main(){for(unsigned poison=0;poison<256;++poison){auto d=std::make_unique<saturn_cd_hle_device>();d->m_file_scope_start=0x10000+poison;d->m_file_info_words=1+poison;d->curdir={1,2,3};d->device_reset();CHECK(d->m_file_scope_start==2&&!d->m_file_info_words&&d->curdir.empty());}std::puts("method-level, unvalidated: 256 hard-reset window/length images");}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-held-window-reset-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(scope['head']+scope['functions']+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

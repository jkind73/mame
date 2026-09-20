#!/usr/bin/env python3
"""Registered root/cache save and bulk-word continuation; method-level, unvalidated."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_transfer_length.py')
scope={'__file__':str(fixture),'__name__':'directory_save_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head='#include <cassert>\n#include <memory>\n#include <type_traits>\n'+head.replace('// TYPES',scope['types'])
start=extract(source,'void saturn_cd_hle_device::device_start()')
pre='register_presave(save_prepost_delegate(FUNC(saturn_cd_hle_device::directory_pre_save)' in start
post='register_postload(save_prepost_delegate(FUNC(saturn_cd_hle_device::directory_post_load)' in start
head=head[:head.rfind('};')]+r'''
 static constexpr uint32_t MAX_DIR_ENTRIES=256*1024/34;
 direntryT curroot{},m_saved_dir[MAX_DIR_ENTRIES]{};uint32_t m_saved_dir_count=0;
 int numfiles=0,firstfile=0;
 struct Entry{uint8_t *base;size_t bytes,count,stride;std::vector<uint8_t> image;};std::vector<Entry>entries;
 template<class T>void save_item(T &v,const char*){entries.push_back({reinterpret_cast<uint8_t*>(&v),sizeof(v),1,0,{}});}
 template<class T,class S,class F>void save_item(T &v,F S::*member,const char*){
  if constexpr(std::is_array_v<T>)entries.push_back({reinterpret_cast<uint8_t*>(&(v[0].*member)),sizeof(F),std::size(v),sizeof(S),{}});
  else entries.push_back({reinterpret_cast<uint8_t*>(&(v.*member)),sizeof(F),1,0,{}});
 }
 void directory_pre_save();void directory_post_load();void register_state();
 void capture(){if(PRE)directory_pre_save();for(auto &e:entries){e.image.resize(e.bytes*e.count);for(size_t i=0;i<e.count;++i)std::memcpy(e.image.data()+i*e.bytes,e.base+i*e.stride,e.bytes);}}
 void restore(){for(auto &e:entries)for(size_t i=0;i<e.count;++i)std::memcpy(e.base+i*e.stride,e.image.data()+i*e.bytes,e.bytes);if(POST)directory_post_load();}
};
#define NAME(x) x,#x
#define STRUCT_MEMBER(s,m) s,&std::remove_extent_t<decltype(s)>::m,#s "." #m
'''.replace('if(PRE)',f'if({str(pre).lower()})').replace('if(POST)',f'if({str(post).lower()})')
selected={'m_file_scope_start','m_file_info_words','m_saved_dir_count','numfiles','firstfile','finfbuf','m_host_transfer_active','xfertype','xfertype32','xfercount','xferdnum','cr1','cr2','cr3','cr4','hirqreg','cd_stat','playtype','cdda_repeat_count'}
regs=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in selected]
regs+=re.findall(r'save_item\(STRUCT_MEMBER\((?:curroot|m_saved_dir), \w+\)\);',start)
functions+='\nvoid saturn_cd_hle_device::register_state(){\n'+'\n'.join(regs)+'\n}\n'
for name in ('directory_pre_save','directory_post_load'):
    sig='void saturn_cd_hle_device::'+name+'()'
    functions+='\n'+(extract(source,sig) if sig in source else sig+' {}')
tail=r'''
using D=saturn_cd_hle_device;
D::direntryT record(unsigned i,unsigned pattern){D::direntryT r{};r.record_size=34+2*(i%96);r.xa_record_size=pattern+i;r.file_number=i*17+pattern;r.firstfad=0x10000+i;r.length=i*2048+pattern;r.year=pattern+1;r.month=pattern+2;r.day=pattern+3;r.hour=pattern+4;r.minute=pattern+5;r.second=pattern+6;r.gmt_offset=pattern+7;r.flags=i+pattern;r.file_unit_size=i+2;r.interleave_gap_size=i+3;r.volume_sequencer_number=pattern*257+i;for(unsigned b=0;b<128;++b)r.name[b]=i*17+b*3+pattern;return r;}
bool equal(const D::direntryT &a,const D::direntryT &b){return a.record_size==b.record_size&&a.xa_record_size==b.xa_record_size&&a.file_number==b.file_number&&a.firstfad==b.firstfad&&a.length==b.length&&a.year==b.year&&a.month==b.month&&a.day==b.day&&a.hour==b.hour&&a.minute==b.minute&&a.second==b.second&&a.gmt_offset==b.gmt_offset&&a.flags==b.flags&&a.file_unit_size==b.file_unit_size&&a.interleave_gap_size==b.interleave_gap_size&&a.volume_sequencer_number==b.volume_sequencer_number&&!std::memcmp(a.name,b.name,128);}
std::vector<u16> finish(D &d,unsigned cut){std::vector<u16> words;for(unsigned i=cut;i<1524;++i)words.push_back(d.dataxfer_word_r());CHECK(d.xfertype==D::XFERTYPE_INVALID&&d.xferdnum==3048&&d.m_host_transfer_active);d.cmd_end_data_transfer();CHECK(d.cr2==1524&&!d.m_host_transfer_active);return words;}
int main(){unsigned images=0;
 for(unsigned count:{0U,1U,2U,3U,17U,256U,7680U})for(unsigned pattern:{0U,1U,85U,255U})for(unsigned cut:{0U,1U,5U,6U,7U,1523U,1524U}){
  auto d=std::make_unique<D>();d->curroot=record(8191,pattern);for(unsigned i=0;i<count;++i)d->curdir.push_back(record(i,pattern));d->numfiles=count;d->firstfile=count>2?2:0;
  const auto expected_root=d->curroot;const auto expected_dir=d->curdir;const auto scope=std::array<int,2>{d->numfiles,d->firstfile};
  d->hirqreg=0x280;d->cr1=0x7300;d->cr3=0xff;d->cr4=0xffff;d->cmd_get_target_file_info();for(unsigned i=0;i<cut;++i)d->dataxfer_word_r();d->register_state();d->capture();
  const auto expected_words=finish(*d,cut);const auto response=std::array<u16,5>{d->cr1,d->cr2,d->cr3,d->cr4,d->hirqreg};
  d->curdir.clear();d->curdir.shrink_to_fit();d->curdir.push_back(record(999,pattern^255));d->curroot=record(998,pattern^255);d->numfiles=d->firstfile=-1;
  std::memset(d->m_saved_dir,0xe5,sizeof(d->m_saved_dir));d->m_saved_dir_count=0;std::memset(d->finfbuf,0xe5,sizeof(d->finfbuf));d->xfertype=D::XFERTYPE_INVALID;d->xfertype32=D::XFERTYPE32_INVALID;d->m_host_transfer_active=false;d->xfercount=d->xferdnum=0;d->cr1=d->cr2=d->cr3=d->cr4=d->cd_stat=d->hirqreg=0;
  const auto irq=d->irqs;d->restore();CHECK(d->irqs==irq&&equal(d->curroot,expected_root)&&d->curdir.size()==expected_dir.size());CHECK((std::array<int,2>{d->numfiles,d->firstfile}==scope));
  for(unsigned i=0;i<count;++i)CHECK(equal(d->curdir[i],expected_dir[i]));CHECK(finish(*d,cut)==expected_words);CHECK((std::array<u16,5>{d->cr1,d->cr2,d->cr3,d->cr4,d->hirqreg}==response));++images;
 }
 std::printf("method-level, unvalidated: %u registered root/cache/table continuation images, 0..7680 records, seven word cuts and four byte patterns\n",images);
 std::puts("method-level, unvalidated: actual staged save hooks/registrations/word transfer with strided byte serializer; storage diagnostics, not native save-file, held-window, media, endian portability or game qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-dir-save-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
"""Directory work-selector setup before IO/completion; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_change_directory.py')
scope={'__file__':str(fixture),'__name__':'directory_filter_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions,source,header,extract=(scope[k] for k in ('head','functions','source','header','extract'))
head='namespace cdrom_file {constexpr unsigned MAX_SECTOR_DATA=2352;}\n'+head
head=head.replace('reads.push_back(fad);','if(on_read)on_read(*this,fad);reads.push_back(fad);')
block=extract(header,'struct blockT')+';'
if 'struct blockT' in head:
    head=head.replace(extract(head,'struct blockT')+';',block,1)
    block=''
at=head.rfind('};');head=head[:at]+block+'''
 void (*on_read)(saturn_cd_hle_device&,uint32_t)=nullptr;
 uint8_t cd_filter_destination(uint8_t,const blockT&) const;
 void cmd_read_directory();
'''+head[at:]
functions+='\n'+extract(source,'uint8_t saturn_cd_hle_device::cd_filter_destination(')+'\n'+extract(source,'void saturn_cd_hle_device::cmd_read_directory()')
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)
fixture=Path(__file__).with_name('check_cd_directory_extent.py')
builders=fixture.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0]
tail=r'''
unsigned wanted_input=0,wanted_fad=0,wanted_range=0,wanted_number=0,io_checks=0,notifications=0;
void check_filter(D &d,bool discovery){const auto &f=d.filters[wanted_input];CHECK(d.cddevicenum==int(wanted_input)&&d.cddevice==&d.filters[wanted_input]);
 CHECK(f.mode==(discovery?0:0x40)&&f.fad==(discovery?0:wanted_fad)&&f.range==(discovery?0:wanted_range)&&f.fid==(discovery?0:wanted_number));
 CHECK(f.condtrue==wanted_input&&f.condfalse==255&&!f.chan&&!f.smmask&&!f.smval&&!f.cimask&&!f.cival);
 for(unsigned i=0;i<24;++i)if(i!=wanted_input){const auto &o=d.filters[i];CHECK(o.mode==0x1f&&o.condtrue==(i+7)%24&&o.condfalse==((i+1)%24==wanted_input?255:(i+1)%24)&&o.fad==99&&o.range==7&&o.fid==0xea&&o.chan==3&&o.smmask==255&&o.smval==0x50&&o.cimask==0x3f&&o.cival==0x25);}
}
void on_read(D &d,uint32_t fad){check_filter(d,fad<200);++io_checks;}
void complete(D &d){CHECK(d.cr1==d.cd_stat&&d.hirqreg==(CMOK|EFLS));check_filter(d,false);++notifications;}
void poison(D &d,unsigned old){for(unsigned i=0;i<24;++i){auto &f=d.filters[i];f={};f.mode=0x1f;f.condtrue=(i+7)%24;f.condfalse=(i+1)%24;f.fid=0xea;f.chan=3;f.smmask=255;f.smval=0x50;f.cimask=0x3f;f.cival=0x25;f.fad=99;f.range=7;}d.cddevicenum=old;d.cddevice=old<24?&d.filters[old]:nullptr;}
void issue(D &d,bool hold,unsigned fid,unsigned input){d.cr1=hold?0x7100:0x7000;d.cr2=0;d.cr3=(input<<8)|(fid>>16);d.cr4=fid;d.hirqreg=0;if(hold)d.cmd_read_directory();else d.cmd_change_directory();}
int main(){unsigned images=0,controls=0,routes=0;
 for(unsigned action=0;action<5;++action)for(unsigned input=0;input<24;++input)for(unsigned old=0;old<=24;++old)for(unsigned rootbytes:{2048U,8192U,32768U})for(unsigned childbytes:{2048U,6144U,18432U})for(unsigned fetch:{2048U,2336U,2340U,2352U}){
  D d;root(d,rootbytes);child(d,childbytes/2048,childbytes,rootbytes);d.sectlenin=fetch;
  if(action)d.read_new_dir(0xffffff);if(action==2||action==4)d.read_new_dir(2);
  const unsigned number=(input*17+old*3+fetch)&255;const unsigned fid=action==0?0xffffff:action==1?2:action==2?1:2;
  if(action)d.curdir[action>=3?0:fid].file_number=number;
  poison(d,old==24?255:old);d.reads.clear();wanted_input=input;wanted_fad=(action==1||action==4)?2000:1000;wanted_range=((action==1||action==4)?childbytes:rootbytes)/2048;wanted_number=action?number:0;
  d.on_read=on_read;d.observe=complete;issue(d,action>=3,fid,input);d.observe=nullptr;d.on_read=nullptr;check_filter(d,false);CHECK(d.reads.size()==(action>=3?0:wanted_range+(action==0)));
  D::blockT b{};b.chan=255;b.subm=255;b.cinf=255;
  for(unsigned file=0;file<256;++file){b.fnum=file;b.FAD=wanted_fad;CHECK(d.cd_filter_destination(input,b)==input);b.FAD=wanted_fad+wanted_range-1;CHECK(d.cd_filter_destination(input,b)==input);++routes;}
  b.FAD=wanted_fad-1;CHECK(d.cd_filter_destination(input,b)==255);b.FAD=wanted_fad+wanted_range;CHECK(d.cd_filter_destination(input,b)==255);++images;
 }
 for(unsigned input=0;input<24;++input)for(unsigned old=0;old<=24;++old){D d;root(d,2048);child(d,1,2048,2048);poison(d,old==24?255:old);std::array<unsigned char,sizeof(d.filters)> before;std::memcpy(before.data(),d.filters,before.size());
  d.read_new_dir(0xffffff);CHECK(std::memcmp(before.data(),d.filters,before.size())==0&&d.cddevicenum==int(old==24?255:old));
  d.reads.clear();d.m_file_scope_start=200;issue(d,false,0,input);CHECK(std::memcmp(before.data(),d.filters,before.size())==0&&d.cddevicenum==int(old==24?255:old)&&d.reads.empty()&&d.m_file_scope_start==200);++controls;
 }
 std::printf("method-level, unvalidated: %u root/child/parent/hold selector images; %u pre-IO observations; %u ready notifications; %u all-file-number route pairs; %u passive-load/self-NOP controls\n",images,io_checks,notifications,routes,controls);
 std::puts("method-level, unvalidated: actual directory commands/selection/parser/setup/destination with mock sector IO and report/IRQ; sector-aligned directory extents; no buffer clear, PVD failure, asynchronous FLS, native save/timing/title qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-directory-filter-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

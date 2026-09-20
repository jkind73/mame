#!/usr/bin/env python3
"""Change-directory selection, rejection and completion; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_directory_extent.py')
scope={'__file__':str(fixture),'__name__':'change_directory_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions,extract,source,header=(scope[k] for k in ('head','functions','extract','source','header'))
head='#include <cassert>\n#define LOGCMD(...) ((void)0)\nconstexpr unsigned MAX_FILTERS=24,CMOK=1,EFLS=0x200,CD_STAT_REJECT=0xff00;\n'+head
head=head.replace(' direntryT curroot{};',extract(header,'struct filterT')+';\n direntryT curroot{};')
head=head[:head.rfind('};')]+r'''
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 filterT filters[24]{};filterT *cddevice=nullptr;int cddevicenum=0xff;
 unsigned irqs=0;void (*observe)(saturn_cd_hle_device&)=nullptr;
 void update_hirq(){++irqs;if(observe)observe(*this);}
 void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
 void cd_connect_cddevice(uint8_t);void cd_disconnect_filter_input(uint8_t);void cmd_change_directory();
};
'''
functions+='\n'+'\n'.join(extract(source,'void saturn_cd_hle_device::'+n+'(') for n in ('cmd_change_directory','cd_connect_cddevice','cd_disconnect_filter_input'))
# Reuse only authored-sector builders, not the extent probe's main/expectations.
builders=fixture.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0]
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)

tail=r'''
unsigned wanted_owner=0,wanted_records=0,wanted_reads=0,wanted_causes=0,wanted_status=0;
void observe(D &d){CHECK(d.irqs==1&&d.cr1==wanted_status&&d.cr2==0&&d.cr3==0&&d.cr4==0&&d.hirqreg==wanted_causes);
 CHECK(d.cddevicenum==int(wanted_owner)&&d.cddevice==(wanted_owner<24?&d.filters[wanted_owner]:nullptr));
 CHECK(d.curdir.size()==wanted_records&&d.reads.size()==wanted_reads);
}
void connect(D &d,unsigned old,unsigned input){d.cddevicenum=old;d.cddevice=old<24?&d.filters[old]:nullptr;for(unsigned i=0;i<24;++i){d.filters[i].condtrue=(i+7)%24;d.filters[i].condfalse=0xff;}d.filters[23].condfalse=input;}
void issue(D &d,unsigned input,unsigned fid){d.cr1=0x7000;d.cr2=0xaaaa;d.cr3=(input<<8)|(fid>>16);d.cr4=fid;d.observe=observe;d.cmd_change_directory();d.observe=nullptr;}
int main(){unsigned moves=0,refusals=0;
 for(unsigned input=0;input<24;++input)for(unsigned old=0;old<=24;++old)for(unsigned fid:{0U,1U,2U,0xffffffU})for(unsigned pending:{0U,0x200U,0x402U,0xffffU}){
  D d;root(d,2048);child(d,3,6144,2048);d.read_new_dir(0xffffff);d.reads.clear();const unsigned previous=old==24?255:old;connect(d,previous,input);
  wanted_owner=fid?input:previous;wanted_records=fid==2?5:3;wanted_reads=fid==0?0:fid==1?1:fid==2?3:2;wanted_causes=pending|CMOK|EFLS;wanted_status=d.cd_stat;d.hirqreg=pending;
  issue(d,input,fid);CHECK(d.curroot.firstfad==1000&&d.curroot.length==2048);for(unsigned i=0;i<24;++i){CHECK(d.filters[i].condtrue==(i+7)%24);CHECK(d.filters[i].condfalse==(!fid&&i==23?input:255));}++moves;
 }
 for(unsigned input=0;input<256;++input)for(unsigned fid:{0U,2U,3U,0x10000U,0x10001U,0x10002U,0xfffffeU,0xffffffU})for(unsigned pending:{0U,0x200U,0xffffU}){
  if(input<24&&(fid==0||fid==0xffffff))continue;
  D d;root(d,2048);child(d,3,6144,2048);d.read_new_dir(0xffffff);d.curdir[2].flags=fid==2?0:2;d.reads.clear();connect(d,5,input);
  wanted_owner=5;wanted_records=3;wanted_reads=0;wanted_causes=pending|CMOK;wanted_status=CD_STAT_REJECT;d.hirqreg=pending;
  issue(d,input,fid);CHECK(d.curdir[2].firstfad==2000&&d.curdir[2].length==6144&&d.filters[23].condfalse==input);++refusals;
 }
 std::printf("method-level, unvalidated: %u root/child/parent/self/connection/completion images; %u regular-file/invalid-ID/invalid-selector refusals\n",moves,refusals);
 std::puts("method-level, unvalidated: actual Change Directory/selector/selection/parser with mock response/IRQ/media; no FLS-active timing, selector buffer reset, held-window, XA directory-flag or native title qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-change-dir-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
"""Read Directory admission without routing/completion effects; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_read_file_admission.py')
scope={'__file__':str(fixture),'__name__':'read_directory_admission_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions=(scope[k] for k in ('head','functions'))
builders=fixture.read_text().split("\ntail=r'''",1)[1].split('int main()',1)[0]
tail=r'''
void issue_directory(D &d,unsigned input,unsigned fid){d.cr1=0x7100;d.cr2=0xabcd;d.cr3=(input<<8)|(fid>>16);d.cr4=fid;d.cmd_read_directory();}
int main(){D d;seed(d);std::array<unsigned char,sizeof(d.filters)> before;std::memcpy(before.data(),d.filters,before.size());unsigned refused=0,controls=0;
 auto reject=[&](unsigned input,unsigned fid,unsigned pending,bool owner){d.m_host_transfer_active=owner;d.xfertype=owner?D::XFERTYPE_TOC:D::XFERTYPE_INVALID;d.hirqreg=pending;const unsigned irqs=d.irqs;const auto records=d.curdir.size();issue_directory(d,input,fid);
  CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==(pending|CMOK)&&d.irqs==irqs+1&&d.seen_status==CD_STAT_REJECT&&d.seen_causes==(pending|CMOK));
  CHECK(d.cd_stat==0x4380&&d.cd_next_stat==0x400&&d.cd_curfad==900&&d.fadstoplay==17&&!d.playtype&&d.m_status_change_in_progress&&d.m_seek_ticks_left==3&&d.cddevicenum==5&&d.cddevice==&d.filters[5]);
  CHECK(d.m_host_transfer_active==owner&&d.xfertype==(owner?D::XFERTYPE_TOC:D::XFERTYPE_INVALID)&&d.xfertype32==D::XFERTYPE32_INVALID&&d.xfercount==17&&d.xferdnum==42&&d.finfbuf[0]==0xa5);
  CHECK(std::memcmp(before.data(),d.filters,before.size())==0&&d.curdir.size()==records);if(records)CHECK(d.curdir[2].firstfad==150&&d.curdir[2].length==4096&&d.curdir[2].file_number==17);++refused;
 };
 for(bool table:{true,false}){if(!table)d.curdir.clear();for(unsigned input=24;input<256;++input)for(unsigned pending=0;pending<65536;++pending)for(bool owner:{false,true})reject(input,2,pending,owner);}
 for(unsigned input=0;input<24;++input)for(unsigned fid:{0U,1U,2U,255U,0x10000U,0xffffffU})for(unsigned pending:{0U,2U,0x280U,0xffffU})for(bool owner:{false,true})reject(input,fid,pending,owner);
 for(unsigned input=0;input<24;++input)for(unsigned old=0;old<24;++old){seed(d);d.cddevicenum=old;d.cddevice=&d.filters[old];d.hirqreg=0;issue_directory(d,input,2);CHECK(d.cr1==d.cd_stat&&d.hirqreg==(CMOK|EFLS)&&d.cddevicenum==int(input)&&d.cddevice==&d.filters[input]&&d.curdir.size()==3);for(unsigned i=0;i<24;++i)CHECK(d.filters[i].condtrue==(i+7)%24&&d.filters[i].mode==0x1f&&d.filters[i].condfalse==((i+1)%24==input?255:(i+1)%24));++controls;}
 std::printf("method-level, unvalidated: %u invalid-selector/absent-table/HIRQ/host-owner rejection images; %u retained valid connection/completion controls\n",refused,controls);
 std::puts("method-level, unvalidated: actual Read Directory/connection methods with mock report/IRQ; accepted command still lacks actual held-window loading; no FLS-active WAIT or native timing/title qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-read-directory-admission-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

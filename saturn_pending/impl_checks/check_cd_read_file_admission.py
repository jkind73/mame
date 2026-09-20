#!/usr/bin/env python3
"""Read File invalid selectors/absent IDs reject before effects; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_connections.py')
scope={'__file__':str(fixture),'__name__':'read_file_admission_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions=(scope[k] for k in ('head','functions'))
head=head.replace('unsigned irqs=0;void update_hirq(){++irqs;}','unsigned irqs=0;uint16_t seen_status=0,seen_causes=0;void update_hirq(){++irqs;seen_status=cr1;seen_causes=hirqreg;}')
tail=r'''
using D=saturn_cd_hle_device;
void seed(D &d){for(unsigned i=0;i<24;++i){auto &f=d.filters[i];f={};f.mode=0x1f;f.condtrue=(i+7)%24;f.condfalse=(i+1)%24;f.fid=0xea;f.chan=3;f.smmask=255;f.smval=0x50;f.cimask=0x3f;f.cival=0x25;f.fad=99;f.range=7;}
 d.cddevicenum=5;d.cddevice=&d.filters[5];d.cd_stat=0x4380;d.cd_next_stat=0x400;d.cd_curfad=900;d.fadstoplay=17;d.playtype=0;d.m_status_change_in_progress=true;d.m_seek_ticks_left=3;d.xfercount=17;d.xferdnum=42;d.finfbuf[0]=0xa5;
 d.curdir.resize(3);d.curdir[2].firstfad=150;d.curdir[2].length=4096;d.curdir[2].file_number=17;
}
void issue(D &d,unsigned input,unsigned fid,unsigned offset){d.cr1=0x7400|(offset>>16);d.cr2=offset;d.cr3=(input<<8)|(fid>>16);d.cr4=fid;d.cmd_read_file();}
int main(){D d;seed(d);std::array<unsigned char,sizeof(d.filters)> before;std::memcpy(before.data(),d.filters,before.size());unsigned refused=0,controls=0;
 auto reject=[&](unsigned input,unsigned fid,unsigned pending,bool owner){d.m_host_transfer_active=owner;d.xfertype=owner?D::XFERTYPE_TOC:D::XFERTYPE_INVALID;d.hirqreg=pending;const unsigned irqs=d.irqs;const auto records=d.curdir.size();issue(d,input,fid,0xabcdef);
  CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==(pending|CMOK)&&d.irqs==irqs+1&&d.seen_status==CD_STAT_REJECT&&d.seen_causes==(pending|CMOK));
  CHECK(d.cd_stat==0x4380&&d.cd_next_stat==0x400&&d.cd_curfad==900&&d.fadstoplay==17&&!d.playtype&&d.m_status_change_in_progress&&d.m_seek_ticks_left==3&&d.cddevicenum==5&&d.cddevice==&d.filters[5]);
  CHECK(d.m_host_transfer_active==owner&&d.xfertype==(owner?D::XFERTYPE_TOC:D::XFERTYPE_INVALID)&&d.xfertype32==D::XFERTYPE32_INVALID&&d.xfercount==17&&d.xferdnum==42&&d.finfbuf[0]==0xa5);
  CHECK(std::memcmp(before.data(),d.filters,before.size())==0&&d.curdir.size()==records);if(records)CHECK(d.curdir[2].firstfad==150&&d.curdir[2].length==4096&&d.curdir[2].file_number==17);++refused;
 };
 for(unsigned input=24;input<256;++input)for(unsigned pending=0;pending<65536;++pending)for(bool owner:{false,true})reject(input,2,pending,owner);
 for(unsigned input=0;input<24;++input)for(unsigned fid:{3U,0x10000U,0x10002U,0xfffffeU,0xffffffU})for(unsigned pending:{0U,2U,0x280U,0xffffU})for(bool owner:{false,true})reject(input,fid,pending,owner);
 d.curdir.clear();for(unsigned input=0;input<24;++input)for(unsigned fid:{0U,1U,2U,3U,0x10002U,0xffffffU})for(unsigned pending:{0U,2U,0x280U,0xffffU})for(bool owner:{false,true})reject(input,fid,pending,owner);
 for(unsigned input=0;input<24;++input){seed(d);d.m_host_transfer_active=false;d.xfertype=D::XFERTYPE_INVALID;d.hirqreg=0;issue(d,input,2,1);CHECK(d.cddevicenum==int(input)&&d.cddevice==&d.filters[input]&&d.cd_curfad==151&&d.fadstoplay==1&&d.playtype==1&&d.cd_next_stat==0x380&&d.filters[input].mode==0x41&&d.filters[input].fid==17);++controls;}
 std::printf("method-level, unvalidated: %u selector/pending-HIRQ/host-owner and absent-ID rejection images; %u legal selector controls\n",refused,controls);
 std::puts("method-level, unvalidated: actual Read File/status/connection methods, mock report/IRQ; no FLS-active precedence, held-window validity, EOF error, native timing/title qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-read-file-admission-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

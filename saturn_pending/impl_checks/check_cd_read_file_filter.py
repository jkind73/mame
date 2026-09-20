#!/usr/bin/env python3
"""Read File installs its documented selector conditions; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_connections.py')
scope={'__file__':str(fixture),'__name__':'read_file_filter_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions,source,header,extract=(scope[k] for k in ('head','functions','source','header','extract'))
head='namespace cdrom_file {constexpr unsigned MAX_SECTOR_DATA=2352;}\n'+head
head=head.replace(' filterT filters[24]{};',extract(header,'struct blockT')+';\n uint8_t cd_filter_destination(uint8_t,const blockT&) const;\n filterT filters[24]{};')
functions+='\n'+extract(source,'uint8_t saturn_cd_hle_device::cd_filter_destination(')
tail=r'''
using D=saturn_cd_hle_device;
void seed(D &d,unsigned input){for(unsigned i=0;i<24;++i){auto &f=d.filters[i];f={};f.mode=0x1f;f.condtrue=(i+7)%24;f.condfalse=0xff;f.fid=0xea;f.chan=3;f.smmask=0xff;f.smval=0x50;f.cimask=0x3f;f.cival=0x25;f.fad=99;f.range=7;}d.filters[(input+1)%24].condfalse=input;d.cddevicenum=(input+5)%24;d.cddevice=&d.filters[d.cddevicenum];}
void issue(D &d,unsigned input,unsigned offset,unsigned fid=2){d.cr1=0x7400|(offset>>16);d.cr2=offset;d.cr3=(input<<8)|(fid>>16);d.cr4=fid;d.cmd_read_file();}
int main(){D d;d.curdir.resize(3);unsigned images=0,controls=0;
 for(unsigned input=0;input<24;++input)for(unsigned number=0;number<256;++number)for(unsigned bytes:{1U,2048U,2049U,7U*2048,70000U*2048})for(unsigned offset:{0U,1U,2U,65535U,65536U})for(unsigned fetch:{2048U,2336U,2340U,2352U}){
  const unsigned size=bytes/2048+(bytes%2048!=0);if(offset>=size)continue;seed(d,input);d.curdir[2].firstfad=150;d.curdir[2].length=bytes;d.curdir[2].file_number=number;d.sectlenin=fetch;issue(d,input,offset);
  const auto &f=d.filters[input];CHECK(f.mode==0x41&&f.fid==number&&f.fad==150+offset&&f.range==size-offset&&f.condtrue==input&&f.condfalse==255&&!f.chan&&!f.smmask&&!f.smval&&!f.cimask&&!f.cival);
  CHECK(d.cddevice==&d.filters[input]&&d.cddevicenum==int(input));
  for(unsigned i=0;i<24;++i)if(i!=input){const auto &o=d.filters[i];CHECK(o.mode==0x1f&&o.condtrue==(i+7)%24&&o.condfalse==255&&o.fad==99&&o.range==7&&o.fid==0xea&&o.chan==3&&o.smmask==255&&o.smval==0x50&&o.cimask==0x3f&&o.cival==0x25);}
  D::blockT b{};b.fnum=number;b.FAD=f.fad;CHECK(d.cd_filter_destination(input,b)==input);b.FAD=f.fad+f.range-1;CHECK(d.cd_filter_destination(input,b)==input);b.fnum=number^1;CHECK(d.cd_filter_destination(input,b)==255);b.fnum=number;b.FAD=f.fad-1;CHECK(d.cd_filter_destination(input,b)==255);b.FAD=f.fad+f.range;CHECK(d.cd_filter_destination(input,b)==255);++images;
 }
 for(unsigned input=0;input<24;++input){seed(d,input);issue(d,input,0,0x10002);const auto &f=d.filters[input];CHECK(f.mode==0x1f&&f.fid==0xea&&f.fad==99&&f.range==7&&d.cddevicenum==int((input+5)%24)&&d.filters[(input+1)%24].condfalse==input);++controls;}
 std::printf("method-level, unvalidated: %u selector/number/range/fetch images with actual destination routing; %u invalid-ID nonmutation controls\n",images,controls);
 std::puts("method-level, unvalidated: actual Read File/connection/status/filter methods; all-byte file numbers include diagnostics; destination buffer clearing, XA interleave extent/EOF, native media/timing/title qualification excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-read-file-filter-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

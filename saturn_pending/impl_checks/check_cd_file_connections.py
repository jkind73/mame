#!/usr/bin/env python3
"""File-command CD input ownership/readback; method-level, unvalidated."""
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name('check_cd_file_transfer_length.py').read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
head=head.replace('// TYPES','\n'.join(extract(header,s)+';' for s in ('struct direntryT','struct filterT','enum transT','enum trans32T')))
head=head[:head.rfind('};')]+r'''
 filterT filters[24]{};filterT *cddevice=nullptr;int cddevicenum=0xff;
 uint32_t cd_curfad=900,fadstoplay=17;uint16_t cd_next_stat=0;
 int sectlenin=2048,m_seek_ticks_left=0;bool m_status_change_in_progress=false;
 void cd_disconnect_filter_input(uint8_t);void cd_connect_cddevice(uint8_t);
 void cmd_read_file();void cmd_read_directory();void cmd_get_cddevice_connection();
 void cmd_set_filter_connection();void cd_change_status(u16);
};
#define LOGSTATUS(...) ((void)0)
constexpr unsigned MAX_FILTERS=24,CD_STAT_BUSY=0,CD_STAT_PLAY=0x300,CD_STAT_SEEK=0x400,CD_STAT_PERI=0x2000,ESEL=0x40,EFLS=0x200,CD_STAT_REJECT=0xff00;
'''
head='#include <cassert>\n'+head
names=['cmd_read_file','cmd_read_directory','cmd_get_cddevice_connection','cmd_set_filter_connection','cd_change_status','cd_disconnect_filter_input']
if 'void saturn_cd_hle_device::cd_connect_cddevice(' in source:names+=['cd_connect_cddevice']
functions='\n'.join(extract(source,'void saturn_cd_hle_device::'+s+'(') for s in names)
tail=r'''
using D=saturn_cd_hle_device;
unsigned endpoint(unsigned value){return value==24?0xff:value;}
void seed(D &d,unsigned old,unsigned rival,unsigned input){
 for(unsigned i=0;i<24;++i){d.filters[i]={};d.filters[i].condtrue=(i+7)%24;d.filters[i].condfalse=0xff;d.filters[i].fad=150+i;d.filters[i].mode=0x4f;}
 if(rival<24)d.filters[rival].condfalse=input;
 d.cddevicenum=old;d.cddevice=old<24?&d.filters[old]:nullptr;
 d.curdir.resize(3);d.curdir[2].firstfad=150;d.curdir[2].length=4096;
}
void issue(D &d,bool directory,unsigned input){d.cr1=directory?0x7100:0x7400;d.cr2=0;d.cr3=input<<8;d.cr4=2;if(directory)d.cmd_read_directory();else d.cmd_read_file();}
int main(){D d;unsigned connections=0,displacements=0,invalid_ids=0;
 for(bool directory:{false,true})for(unsigned old=0;old<=24;++old)for(unsigned input=0;input<=24;++input)for(unsigned rival=0;rival<=24;++rival){
  const unsigned dest=endpoint(input);seed(d,endpoint(old),rival,dest);issue(d,directory,dest);
  CHECK(d.cddevice==(dest<24?&d.filters[dest]:nullptr)&&d.cddevicenum==int(dest));
  for(unsigned i=0;i<24;++i){CHECK(d.filters[i].condfalse==0xff);if(i!=dest)CHECK(d.filters[i].condtrue==(i+7)%24&&d.filters[i].fad==150+i&&d.filters[i].mode==0x4f);}
  d.cmd_get_cddevice_connection();CHECK(d.cr3==(dest<<8));++connections;
 }
 for(bool directory:{false,true})for(unsigned input=0;input<24;++input){
  seed(d,5,2,input);issue(d,directory,input);
  d.cr1=0x4602;d.cr2=input;d.cr3=3<<8;d.cmd_set_filter_connection();d.cmd_get_cddevice_connection();
  CHECK(!d.cddevice&&d.cddevicenum==0xff&&d.cr3==0xff00&&d.filters[3].condfalse==input);++displacements;
 }
 for(unsigned input=0;input<24;++input){
  seed(d,5,2,input);d.cr1=0x7400;d.cr2=0;d.cr3=(input<<8)|1;d.cr4=2;d.cmd_read_file();
  CHECK(d.cddevice==&d.filters[5]&&d.cddevicenum==5&&d.filters[2].condfalse==input);++invalid_ids;
 }
 std::printf("method-level, unvalidated: %u file/directory connection images; %u subsequent false-output displacements; %u invalid-ID non-takeover controls\n",connections,displacements,invalid_ids);
 std::puts("method-level, unvalidated: actual file/connection methods, mocked response/IRQ; FF file selectors are legacy disconnection diagnostics, not legal-command or full file-system qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-connections-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
"""ASan/UBSan checks of the real HLE selector command handlers."""
from pathlib import Path
import subprocess, tempfile
from saturn_vdp_wip_test import method
ROOT=Path(__file__).resolve().parent.parent
source=(ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
names=('cmd_set_cddevice_connection','cmd_set_filter_range','cmd_get_filter_range',
       'cmd_set_filter_subheader_conditions','cmd_get_filter_subheader_conditions',
       'cmd_set_filter_mode','cmd_get_filter_mode','cmd_set_filter_connection',
       'cmd_get_filter_connection','cmd_get_sector_information')
methods='\n'.join(method(source.replace('saturn_cd_hle_device::','saturn_vdp1_device::'),n).replace('saturn_vdp1_device::','saturn_cd_hle_device::') for n in names)
fixture=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#define LOGCMD(...)
#define LOGWARN(...)
constexpr unsigned MAX_FILTERS=24,MAX_BLOCKS=200,CMOK=1,ESEL=0x40,CD_STAT_REJECT=0xff00;
struct saturn_cd_hle_device {
 struct filterT {uint8_t mode=0,chan=0,smmask=0,cimask=0,fid=0,smval=0,cival=0,condtrue=0,condfalse=0;uint32_t fad=0,range=0;};
 struct blockT {int FAD=0;uint8_t fnum=0,chan=0,subm=0,cinf=0;};
 struct partitionT {blockT*blocks[MAX_BLOCKS]{};unsigned numblks=0;};
 filterT filters[24]{};partitionT partitions[24]{};filterT*cddevice=nullptr;
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,hirqreg=0,cd_stat=0x100;uint8_t cddevicenum=255;
 struct context {const char*describe_context(){return "fixture";}} ctx;
 context&machine(){return ctx;}
 void popmessage(const char*,...){}
 void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
 // DECLARATIONS
};
// METHODS
int main(){
 saturn_cd_hle_device d;
 d.cr1=0x4012;d.cr2=0x3456;d.cr3=0x170a;d.cr4=0xbcde;d.cmd_set_filter_range();
 assert(d.filters[23].fad==0x123456 && d.filters[23].range==0xabcde && d.hirqreg==(CMOK|ESEL));
 d.cr3=0x1700;d.hirqreg=0;d.cmd_get_filter_range();
 assert(d.cr1==0x112 && d.cr2==0x3456 && d.cr3==0x170a && d.cr4==0xbcde && d.hirqreg==CMOK);
 d.cr1=0x4603;d.cr2=0x05ff;d.cr3=0x1700;d.cmd_set_filter_connection();
 d.cr1=0x44ff;d.cr3=0x1700;d.cmd_set_filter_mode(); // initialize conditions, retain connectors
 assert(d.filters[23].fad==0 && d.filters[23].range==0 && d.filters[23].condtrue==5 && d.filters[23].condfalse==255);
 d.cr3=0x1700;d.hirqreg=0;d.cmd_get_filter_connection();
 assert(d.cr1==0x100 && d.cr2==0x05ff && d.cr3==0x1700 && d.cr4==0 && d.hirqreg==CMOK);
 d.cr1=0x4223;d.cr2=0x4567;d.cr3=0x1789;d.cr4=0xabcd;d.cmd_set_filter_subheader_conditions();
 d.cr3=0x1700;d.hirqreg=0;d.cmd_get_filter_subheader_conditions();assert(d.cr1==0x123 && d.cr2==0x4567 && d.cr3==0x1789 && d.cr4==0xabcd && d.hirqreg==CMOK);
 d.cr3=0x1700;d.hirqreg=0;d.cmd_get_filter_mode();assert(d.cr1==0x100 && d.hirqreg==CMOK);
 d.cr1=0x4601;d.cr2=0x1800;d.cr3=0x1700;d.hirqreg=0;d.cmd_set_filter_connection();
 assert(d.cr1==CD_STAT_REJECT && d.filters[23].condtrue==5 && d.hirqreg==CMOK);
 using fn=void(saturn_cd_hle_device::*)();
 fn cmds[]={&saturn_cd_hle_device::cmd_set_cddevice_connection,&saturn_cd_hle_device::cmd_set_filter_range,&saturn_cd_hle_device::cmd_get_filter_range,&saturn_cd_hle_device::cmd_set_filter_subheader_conditions,&saturn_cd_hle_device::cmd_get_filter_subheader_conditions,&saturn_cd_hle_device::cmd_set_filter_mode,&saturn_cd_hle_device::cmd_get_filter_mode,&saturn_cd_hle_device::cmd_set_filter_connection,&saturn_cd_hle_device::cmd_get_filter_connection};
 for(auto f:cmds){d.cr1=0;d.cr2=0;d.cr3=0x1800;d.cr4=0;d.hirqreg=0;(d.*f)();assert(d.cr1==CD_STAT_REJECT && d.hirqreg==CMOK);}
 d.cr3=0;d.cr2=0xffff;d.hirqreg=0;d.cmd_get_sector_information();assert(d.cr1==CD_STAT_REJECT && d.hirqreg==CMOK);
 d.cr3=0xff00;d.cr2=0;d.hirqreg=0;d.cmd_get_sector_information();assert(d.cr1==CD_STAT_REJECT && d.hirqreg==CMOK);
}
'''
fixture=fixture.replace('// DECLARATIONS','\n'.join('void '+n+'();' for n in names)).replace('// METHODS',methods)
with tempfile.TemporaryDirectory(prefix='saturn-cd-selector-') as td:
 p=Path(td);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('CD selector commands ASan/UBSan PASS')

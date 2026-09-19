#!/usr/bin/env python3
"""Actual standard response with absent-media rejected commands; method-level, unvalidated."""
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
head=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
constexpr unsigned MAX_FILTERS=24,MAX_BLOCKS=200,CMOK=1,ESEL=0x40,CD_STAT_SEEK=0x400,CD_STAT_REJECT=0xff00;
struct cdrom_file{static constexpr unsigned MAX_SECTOR_DATA=2352;};
struct saturn_cd_hle_device {
// TYPES
 std::array<filterT,24> filters{};std::array<partitionT,24> partitions{};
 filterT *cddevice=nullptr;int cddevicenum=0xff;
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x700,hirqreg=0;
 uint8_t playtype=0,cdda_repeat_count=0,cur_track=3;
 uint32_t cd_curfad=0x123456,cd_fad_seek=0x654321;
 unsigned irqs=0;
 struct Media{bool inserted=false;unsigned reads=0;bool exists(){return inserted;}uint8_t get_track(int){++reads;return 1;}} media;
 Media *m_cdrom_image=&media;
 unsigned sega_cdrom_get_adr_control(unsigned){++media.reads;return 0x41;}
 unsigned get_track_index(unsigned){++media.reads;return 1;}
 void update_hirq(){++irqs;}
 void cr_standard_return(uint16_t);
 void cmd_set_cddevice_connection();void cmd_get_filter_connection();void cmd_get_sector_information();
 void cd_disconnect_filter_input(uint8_t);void cd_connect_cddevice(uint8_t);
};
'''
names=('cr_standard_return','cmd_set_cddevice_connection','cmd_get_filter_connection','cmd_get_sector_information','cd_disconnect_filter_input')
if 'void saturn_cd_hle_device::cd_connect_cddevice(' in source:names+=('cd_connect_cddevice',)
functions='\n'.join(extract(source,'void saturn_cd_hle_device::'+s+'(') for s in names)
tail=r'''
int main(){saturn_cd_hle_device d;unsigned images=0,commands=0,present=0;
 for(unsigned drive:{0x600U,0x700U})for(unsigned low=0;low<256;++low)for(unsigned result:{drive,drive|0x8000U,0xff00U}){
  d.cd_stat=drive;d.cr1=0x55'00|low;d.cr2=0x1234;d.cr3=0x5678;d.cr4=0x9abc;
  d.cr_standard_return(result);CHECK((d.cr1>>8)==(result>>8));
  CHECK((d.cr1&0xff)==low&&d.cr2==0x1234&&d.cr3==0x5678&&d.cr4==0x9abc&&!d.media.reads);++images;
 }
 for(unsigned filter=24;filter<256;++filter){
  d.cd_stat=0x700;d.cr1=0x4700;d.cr3=filter<<8;d.hirqreg=0;d.cmd_get_filter_connection();CHECK((d.cr1>>8)==0xff&&d.hirqreg==CMOK);++commands;
  d.cr1=0x5400;d.cr2=0xffff;d.cr3=filter<<8;d.hirqreg=0;d.cmd_get_sector_information();CHECK((d.cr1>>8)==0xff&&d.hirqreg==CMOK);++commands;
  if(filter!=255){d.cr1=0x3000;d.cr3=filter<<8;d.cmd_set_cddevice_connection();CHECK((d.cr1>>8)==0xff&&!d.cddevice&&d.cddevicenum==255);++commands;}
 }
 CHECK(!d.media.reads);d.media.inserted=true;
 for(unsigned drive:{0x100U,0x400U})for(unsigned play:{0U,1U})for(unsigned repeat=0;repeat<16;++repeat)
 for(unsigned track:{3U,255U})for(unsigned result:{drive,drive|0x8000U,0xff00U}){
  d.cd_stat=drive;d.playtype=play;d.cdda_repeat_count=repeat;d.cur_track=track;d.cr_standard_return(result);
  CHECK(d.cr1==(result|(play<<7)|repeat));const unsigned fad=drive==0x400?d.cd_fad_seek:d.cd_curfad;
  CHECK(d.cr2==(drive==0x400?0x4101:(track==255?0xffff:0x4102))&&d.cr3==(0x100|(fad>>16))&&d.cr4==(fad&0xffff));++present;
 }
 std::printf("method-level, unvalidated: %u empty-media status images; %u rejected commands using actual standard-return helper; %u media-present formatting controls\n",images,commands,present);
 std::puts("method-level, unvalidated: mock media metadata, actual command/response bodies; no native tray/IRQ/drive/report qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-empty-response-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head.replace('// TYPES','\n'.join(extract(header,'struct '+s)+';' for s in ('filterT','blockT','partitionT')))+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

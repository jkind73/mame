#!/usr/bin/env python3
"""Actual Set Sector Length command, operand atomicity and completion; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
a=source.index('void saturn_cd_hle_device::cmd_set_sector_length()');b=source.index('\nvoid ',a+1)
head=r'''
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define LOGCMD(...) ((void)0)
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
constexpr uint16_t CMOK=1,ESEL=0x40,CD_STAT_REJECT=0xff00;
struct saturn_cd_hle_device {
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x4100,hirqreg=0;
 int sectlenin=2048,sectlenout=2048;unsigned irqs=0;
 std::array<unsigned,7> seen{};
 auto response(){return std::array<unsigned,7>{cr1,cr2,cr3,cr4,hirqreg,unsigned(sectlenin),unsigned(sectlenout)};}
 void update_hirq(){++irqs;seen=response();}
 void cr_standard_return(uint16_t status){cr1=status;cr2=0x1234;cr3=0x5678;cr4=0x9abc;}
 void cmd_set_sector_length();
};
'''
tail=r'''
int main(){unsigned images=0;
 const unsigned lengths[]={2048,2336,2340,2352};
 for(unsigned oldget:lengths)for(unsigned oldput:lengths)for(unsigned get=0;get<256;++get)for(unsigned put=0;put<256;++put)
 for(unsigned pending:{0U,unsigned(CMOK),unsigned(ESEL),0xffffU}){
  saturn_cd_hle_device d;d.sectlenin=oldget;d.sectlenout=oldput;d.hirqreg=pending;
  d.cr1=0x6000|get;d.cr2=(put<<8)|0xa5;d.cr3=0x55aa;d.cr4=0x33cc;
  const bool valid=(get<4||get==0xff)&&(put<4||put==0xff);
  d.cmd_set_sector_length();
  CHECK(d.sectlenin==((valid&&get<4)?lengths[get]:oldget));
  CHECK(d.sectlenout==((valid&&put<4)?lengths[put]:oldput));
  CHECK(d.cr1==(valid?0x4100:CD_STAT_REJECT)&&d.cd_stat==0x4100);
  CHECK(d.hirqreg==(pending|CMOK|(valid?ESEL:0))&&d.irqs==1&&d.seen==d.response());++images;
 }
 std::printf("method-level, unvalidated: %u operand/previous-length/pending-cause images; exact atomic updates, NOCHG, response-before-callback and cause preservation\n",images);
 std::puts("method-level, unvalidated: actual setter, mock standard report and IRQ callback; reserved pending bits are storage diagnostics; no native timing or invalid-report payload claim");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-sector-length-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+source[a:b]+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

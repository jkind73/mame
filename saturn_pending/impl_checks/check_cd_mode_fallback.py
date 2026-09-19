#!/usr/bin/env python3
"""Sector mode-byte interpretation from the actual block helpers; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
header=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
a=header.index('  struct blockT {');b=header.index('\n  struct partitionT',a)
head='''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
namespace cdrom_file {constexpr unsigned MAX_SECTOR_DATA=2352;}
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"line %d: %s\\n",__LINE__,#x);std::exit(1);}}while(0)
'''+header[a:b]
tail=r'''
int main(){unsigned raw=0,cooked=0;
 const unsigned lengths[]={2048,2336,2340,2352};
 blockT block{};block.raw_data=true;block.size=2352;
 for(unsigned mode=0;mode<256;++mode)for(unsigned submode=0;submode<256;++submode)for(unsigned f=0;f<4;++f){
  block.data[15]=mode;block.data[18]=submode;
  CHECK(block.host_offset(lengths[f])==(f==0?(mode==1?16:24):f==1?16:f==2?12:0));
  CHECK(block.host_size(lengths[f])==(f==0&&mode==2&&(submode&0x20)?2324:lengths[f]));++raw;
 }
 block.raw_data=false;
 for(unsigned size:{2048,2324,2336,2340,2352})for(unsigned length:lengths){
  block.size=size;CHECK(block.host_offset(length)==0&&block.host_size(length)==size);++cooked;
 }
 std::printf("method-level, unvalidated: %u raw header/submode/view images and %u unchanged cooked-view controls\n",raw,cooked);
 std::puts("method-level, unvalidated: nonstandard header-byte cases are format/storage diagnostics, not a claim that every mode byte denotes legal media");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-mode-fallback-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

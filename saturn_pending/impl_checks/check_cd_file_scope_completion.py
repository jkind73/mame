#!/usr/bin/env python3
"""File-scope query completion causes; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=r'''
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
#define LOGCMD(...) ((void)0)
#define LOGWARN(...) ((void)0)
constexpr unsigned CMOK=1,EFLS=0x200;
struct saturn_cd_hle_device {
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 int numfiles=4,firstfile=2;unsigned irqs=0;
 std::array<uint16_t,4> callback_response{};
 void update_hirq(){++irqs;callback_response={cr1,cr2,cr3,cr4};}
 void cmd_get_file_scope();
};
'''
method=extract(source,'void saturn_cd_hle_device::cmd_get_file_scope()')
tail=r'''
int main(){saturn_cd_hle_device d;unsigned cases=0;
 for(unsigned status:{0x100U,0x380U,0x400U,0x4100U})for(unsigned pending=0;pending<65536;++pending){
  d.cd_stat=status;d.hirqreg=pending;d.cr1=0x7200;d.cr2=d.cr3=d.cr4=0xbeef;const unsigned old_irq=d.irqs;
  d.cmd_get_file_scope();CHECK(d.hirqreg==(pending|CMOK)&&d.irqs==old_irq+1);
  CHECK(d.callback_response==(std::array<uint16_t,4>{d.cr1,d.cr2,d.cr3,d.cr4}));
  CHECK(d.cd_stat==status&&d.numfiles==4&&d.firstfile==2);++cases;
 }
 std::printf("method-level, unvalidated: %u scope-query pending-cause/status images; no query-generated EFLS or lost pending causes; complete response before recording completion callback\n",cases);
 std::puts("method-level, unvalidated: actual query, mocked IRQ callback; scope contents/parser/held-window/active-filesystem timing and native bus/IRQ excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-scope-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

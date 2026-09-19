#!/usr/bin/env python3
"""CD command 47 response/dispatch arm; method-level, unvalidated."""
from pathlib import Path
import re
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
dispatch=extract(source,'void saturn_cd_hle_device::cd_exec_command()')
arm=re.search(r'case 0x47:\s*cmd_get_filter_connection\(\);\s*break;',dispatch)
if not arm:
    sys.exit('method-level, unvalidated: missing command 47 dispatch (historical source control)')
method=extract(source,'void saturn_cd_hle_device::cmd_get_filter_connection()')
head=r'''
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
constexpr unsigned MAX_FILTERS=24,CMOK=1,CD_STAT_REJECT=0xff00;
struct saturn_cd_hle_device {
// TYPE
 std::array<filterT,24> filters{};
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 unsigned irqs=0,rejections=0;
 void update_hirq(){++irqs;}
 void cr_standard_return(uint16_t status){CHECK(status==CD_STAT_REJECT);cr1=status;++rejections;}
 void cmd_get_filter_connection();
 void dispatch(){switch(cr1>>8){
// ARM
 default:CHECK(false);}}
};
'''
tail=r'''
int main(){
 saturn_cd_hle_device d;unsigned reads=0,rejections=0;
 for(unsigned i=0;i<24;++i){d.filters[i].mode=0x4f;d.filters[i].fid=i;d.filters[i].fad=150+i;d.filters[i].range=200+i;}
 for(unsigned f=0;f<24;++f)for(unsigned t=0;t<=24;++t)for(unsigned n=0;n<=24;++n)
 for(unsigned status:{0x100U,0x300U}){
  d.filters[f].condtrue=t==24?0xff:t;d.filters[f].condfalse=n==24?0xff:n;
  decltype(d.filters) before;std::memcpy(before.data(),d.filters.data(),sizeof(before));
  d.cd_stat=status;d.cr1=0x4700;d.cr2=0xa55a;d.cr3=f<<8;d.cr4=0xdead;
  const uint16_t old_hirq=uint16_t((f*73+t*7+n)&0xfffe);d.hirqreg=old_hirq;const unsigned irq=d.irqs;
  d.dispatch();CHECK(d.cr1==status&&d.cr2==((t==24?0xff:t)<<8|(n==24?0xff:n))&&d.cr3==(f<<8)&&d.cr4==0);
  CHECK(d.hirqreg==(old_hirq|CMOK)&&d.irqs==irq+1&&!d.rejections);
  CHECK(!std::memcmp(before.data(),d.filters.data(),sizeof(before)));++reads;
 }
 for(unsigned f=24;f<256;++f){
  decltype(d.filters) before;std::memcpy(before.data(),d.filters.data(),sizeof(before));
  d.cr1=0x4700;d.cr3=f<<8;d.hirqreg=0;d.dispatch();
  CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK&&!std::memcmp(before.data(),d.filters.data(),sizeof(before)));++rejections;
 }
 std::printf("method-level, unvalidated: %u legal connector/status readbacks via extracted dispatch arm; %u invalid-filter rejection controls; no selector mutation or new ESEL bit\n",reads,rejections);
 std::puts("method-level, unvalidated: actual handler/dispatch arm; command scheduler, mapped bus and native IRQ delivery not qualified");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-getconn-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head.replace('// TYPE',extract(header,'struct filterT')+';').replace('// ARM',arm[0])+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

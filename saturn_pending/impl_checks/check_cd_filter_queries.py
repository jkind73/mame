#!/usr/bin/env python3
"""Selector query response words/CMOK-only completion; method-level, unvalidated."""
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
methods=['cmd_'+operation+'_filter_'+field for field in ('range','subheader_conditions','mode') for operation in ('set','get')]+['cd_reset_filter_conditions']
dispatch=extract(source,'void saturn_cd_hle_device::cd_exec_command()')
arms=[re.search(r'case 0x'+f'{code:02x}'+r':\s*cmd_\w+\(\);\s*break;',dispatch)[0] for code in range(0x40,0x46)]
head=r'''
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
#define LOGCMD(...) ((void)0)
#define LOGWARN(...) ((void)0)
constexpr unsigned MAX_FILTERS=24,CMOK=1,ESEL=0x40,CD_STAT_REJECT=0xff00;
struct saturn_cd_hle_device {
// TYPE
 std::array<filterT,24> filters{};
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 unsigned irqs=0;
 void update_hirq(){++irqs;}
 void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
// DECLS
 void dispatch(){switch(cr1>>8){
// ARMS
 default:CHECK(false);}}
};
'''
functions='\n'.join(extract(source,'void saturn_cd_hle_device::'+s+'(') for s in methods)
decls='\n'.join(' void '+s+'('+('filterT&' if s=='cd_reset_filter_conditions' else '')+');' for s in methods)
tail=r'''
int main(){
 saturn_cd_hle_device d;unsigned queries=0,rejections=0,writes=0;
 for(unsigned filter=0;filter<24;++filter)for(unsigned value=0;value<256;++value){
  const unsigned fad=(0x123456^(value*0x10001))&0xffffff,range=0xffffff-value*0x10101;
  d.cr1=0x4000|(fad>>16);d.cr2=fad;d.cr3=filter<<8|(range>>16);d.cr4=range;d.dispatch();++writes;
  d.cr1=0x4200|value;d.cr2=(value^0xa5)<<8|(value^0x5a);d.cr3=filter<<8|(value^0xff);d.cr4=(value^0x17)<<8|(value^0x81);d.dispatch();++writes;
  d.cr1=0x4400|(value&0x5f);d.cr3=filter<<8;d.dispatch();++writes;
  decltype(d.filters) before;std::memcpy(before.data(),d.filters.data(),sizeof(before));
  for(unsigned code:{0x41U,0x43U,0x45U})for(unsigned pending:{0U,1U,0x40U,0x80U,0x8000U,0xffffU}){
   d.cr1=code<<8;d.cr2=d.cr4=0xdead;d.cr3=filter<<8;d.hirqreg=pending;const unsigned old_irq=d.irqs;
   d.dispatch();CHECK(d.hirqreg==(pending|CMOK)&&d.irqs==old_irq+1);
   CHECK(!std::memcmp(before.data(),d.filters.data(),sizeof(before)));
   if(code==0x41)CHECK(d.cr1==(0x100|(fad>>16))&&d.cr2==(fad&0xffff)&&d.cr3==(filter<<8|(range>>16))&&d.cr4==(range&0xffff));
   if(code==0x43)CHECK(d.cr1==(0x100|value)&&d.cr2==((value^0xa5)<<8|(value^0x5a))&&d.cr3==(filter<<8|(value^0xff))&&d.cr4==((value^0x17)<<8|(value^0x81)));
   if(code==0x45)CHECK(d.cr1==(0x100|(value&0x5f))&&d.cr2==0&&d.cr3==(filter<<8)&&d.cr4==0);
   ++queries;
  }
 }
 for(unsigned filter=24;filter<256;++filter)for(unsigned code:{0x41U,0x43U,0x45U}){
  decltype(d.filters) before;std::memcpy(before.data(),d.filters.data(),sizeof(before));
  d.cr1=code<<8;d.cr3=filter<<8;d.hirqreg=0;d.dispatch();
  CHECK(d.cr1==CD_STAT_REJECT&&d.hirqreg==CMOK&&!std::memcmp(before.data(),d.filters.data(),sizeof(before)));++rejections;
 }
 std::printf("method-level, unvalidated: %u setter operations; %u query/IRQ-image roundtrips; %u invalid-filter controls; actual handlers and extracted dispatch arms\n",writes,queries,rejections);
 std::puts("method-level, unvalidated: query response words and recording IRQ callbacks, not native transport, command scheduling or IRQ timing qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-queries-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head.replace('// TYPE',extract(header,'struct filterT')+';').replace('// DECLS',decls).replace('// ARMS','\n'.join(arms))+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

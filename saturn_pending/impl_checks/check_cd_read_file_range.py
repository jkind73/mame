#!/usr/bin/env python3
"""Read File packet widths/logical-sector geometry; method-level, unvalidated."""
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
 void cd_disconnect_filter_input(uint8_t);void cd_connect_cddevice(uint8_t);
 uint32_t cd_curfad=900,fadstoplay=17;uint16_t cd_next_stat=0;
 int sectlenin=2048,m_seek_ticks_left=0;bool m_status_change_in_progress=false;
 void cmd_read_file();void cd_change_status(u16);
};
#define LOGSTATUS(...) ((void)0)
constexpr unsigned MAX_FILTERS=24,CD_STAT_BUSY=0,CD_STAT_PLAY=0x300,CD_STAT_SEEK=0x400,CD_STAT_PERI=0x2000,CD_STAT_REJECT=0xff00;
'''
functions='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cmd_read_file()', 'void saturn_cd_hle_device::cd_change_status('))
head='#include <cassert>\n'+head
if 'void saturn_cd_hle_device::cd_connect_cddevice(' in source:
    functions+='\n'+extract(source,'void saturn_cd_hle_device::cd_connect_cddevice(')+'\n'+extract(source,'void saturn_cd_hle_device::cd_disconnect_filter_input(')
tail=r'''
using D=saturn_cd_hle_device;
void issue(D &d,unsigned filter,unsigned fid,unsigned offset){d.cr1=0x7400|(offset>>16);d.cr2=offset;d.cr3=(filter<<8)|(fid>>16);d.cr4=fid;d.cmd_read_file();}
int main(){D d;d.curdir.resize(3);unsigned ranges=0,identifiers=0;
 for(unsigned filter=0;filter<24;++filter)for(unsigned length:{1U,2048U,2049U,4096U,65535U*2048,65536U*2048,70000U*2048,0xffffffffU})
 for(unsigned fetch:{2048U,2336U,2340U,2352U})for(unsigned offset:{0U,1U,255U,256U,257U,4095U,65535U,65536U,70000U,0x1ffffU,0x1fffffU})
 for(unsigned fad:{150U,0xfffff0U}){
  const uint32_t sectors=length/2048+(length%2048!=0);if(offset>=sectors)continue;
  d.curdir[2].firstfad=fad;d.curdir[2].length=length;d.sectlenin=fetch;issue(d,filter,2,offset);
  CHECK(d.cd_curfad==((uint64_t(fad)+offset)%0x1000000)&&d.fadstoplay==sectors-offset);
  CHECK(d.cddevice==&d.filters[filter]&&d.playtype==1&&d.cd_next_stat==(CD_STAT_PLAY|0x80));++ranges;
 }
 for(unsigned high=1;high<256;++high)for(unsigned low:{0U,1U,2U,255U,65535U}){
  d.cd_curfad=900;d.fadstoplay=17;d.cd_next_stat=0x100;d.cddevice=&d.filters[7];d.playtype=0;
  issue(d,3,(high<<16)|low,0);CHECK(d.cd_curfad==900&&d.fadstoplay==17&&d.cd_next_stat==0x100&&d.cddevice==&d.filters[7]&&d.playtype==0);++identifiers;
 }
 std::printf("method-level, unvalidated: %u valid-offset logical-sector ranges, all selectors/fetch sizes; %u high-file-ID nonalias controls\n",ranges,identifiers);
 std::puts("method-level, unvalidated: actual Read File/status bodies; includes FAD-wrap and maximum-length storage diagnostics; EOF error policy, held-table mapping, filtering/IRQ/timing/native playback excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-read-file-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

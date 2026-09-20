#!/usr/bin/env python3
"""CD producer BFUL latching and masked callback without HIRQ polling."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_discard_progress.py')
scope={'__file__':str(fixture),'__name__':'buffer_full_irq_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head='using offs_t=unsigned;constexpr int ASSERT_LINE=1,CLEAR_LINE=0;\n'+head
head=head.replace('void update_hirq(){++irqs;}', 'void update_hirq();')
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+r'''
 uint16_t hirqmask=0;
 struct Callback{bool level=false;unsigned calls=0;bool isunset(){return false;}void operator()(int value){level=value;++calls;}}m_host_irq_cb;
 void hirqmask_w(offs_t,uint16_t,uint16_t);
}''',1)
head+='\n#define COMBINE_DATA(p) (*(p)=(*(p)&~mem_mask)|(data&mem_mask))\n'
functions+='\n'+extract(source,'void saturn_cd_hle_device::update_hirq()')+'\n'+extract(source,'void saturn_cd_hle_device::hirqmask_w(')
start=extract(source,'void saturn_cd_hle_device::device_start()');reg=extract(functions,'void saturn_cd_hle_device::register_state()')
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1]=='hirqmask' and m[0] not in reg]
functions=functions.replace(reg,reg[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
using D=saturn_cd_hle_device;
void fill(D &d,unsigned dest,unsigned count){for(unsigned i=0;i<count;++i){uint8_t id=255;auto *b=d.cd_alloc_block(&id);CHECK(b);b->size=2352;b->raw_data=true;b->FAD=150+i;auto &p=d.partitions[dest];if(p.size<0)p.size=0;p.blocks[p.numblks]=b;p.bnum[p.numblks++]=id;p.size+=2352;}}
void seed(D &d,unsigned dest,unsigned count,unsigned length,unsigned mask,bool disconnect){fill(d,dest,count);d.cd_connect_cddevice(disconnect?255:dest);d.filters[dest].condtrue=dest;d.media.type=cdrom_file::CD_TRACK_MODE1_RAW;d.media.bytes[15]=1;
 d.cd_stat=CD_STAT_PLAY;d.cd_curfad=1234;d.fadstoplay=length;d.cdda_maxrepeat=0;d.playtype=0;d.hirqreg=0;d.hirqmask=mask;d.m_host_irq_cb.level=false;}
void event(D &d,unsigned dest,unsigned before,unsigned length,unsigned mask){const auto calls=d.m_host_irq_cb.calls;d.cd_playdata();
 // No hirq_r() call precedes these checks: interrupt delivery cannot depend on polling.
 CHECK(d.hirqreg&BFUL);CHECK(d.m_host_irq_cb.level==bool(d.hirqreg&mask)&&d.m_host_irq_cb.calls>calls);
 CHECK(d.buffull&&d.freeblocks==0&&d.partitions[dest].numblks==200);
 if(before==199)CHECK(d.cd_curfad==1235&&d.fadstoplay==length-1&&(d.hirqreg&CSCT));
 else CHECK(d.cd_curfad==1234&&d.fadstoplay==length&&d.buffull_temp_pause&&d.cd_next_stat==CD_STAT_PAUSE&&!(d.hirqreg&CSCT));
 // A pending full cause becomes visible when its mask is enabled, without a
 // data read or HIRQ poll. Other causes stay masked for this check.
 d.hirqmask_w(0,0,0xffff);CHECK(!d.m_host_irq_cb.level&&(d.hirqreg&BFUL));
 d.hirqmask_w(0,BFUL,0xffff);CHECK(d.m_host_irq_cb.level);
 // Existing public-buffer deletion releases capacity and withdraws BFUL.
 d.cr1=0x6200;d.cr2=0;d.cr3=dest<<8;d.cr4=1;d.cmd_delete_sector_data();
 CHECK(d.freeblocks==1&&!d.buffull&&!(d.hirqreg&BFUL)&&!d.m_host_irq_cb.level);
}
int main(){unsigned images=0,replays=0,controls=0;
 for(unsigned dest:{0U,7U,23U})for(unsigned count:{199U,200U})for(unsigned length:{1U,2U})for(unsigned mask:{0U,1U,4U,8U,12U,65535U})for(bool disconnect:{false,true}){
  if(disconnect&&count==199)continue;auto p=std::make_unique<D>();auto &d=*p;seed(d,dest,count,length,mask,disconnect);d.register_state();d.capture();event(d,dest,count,length,mask);
  d.hirqmask=d.hirqreg=0;d.buffull=0;d.freeblocks=17;d.cd_curfad=42;d.fadstoplay=0;d.m_host_irq_cb.level=false;d.restore();event(d,dest,count,length,mask);++images;++replays;
 }
 for(unsigned dest:{0U,7U,23U})for(unsigned count:{0U,198U})for(bool discard:{false,true}){auto p=std::make_unique<D>();auto &d=*p;seed(d,dest,count,2,BFUL,false);if(discard)d.filters[dest].condtrue=255;d.cd_playdata();CHECK(!d.buffull&&!(d.hirqreg&BFUL)&&!d.m_host_irq_cb.level&&d.cd_curfad==1235&&d.freeblocks==200-int(count)-int(!discard));++controls;}
 std::printf("method-level, unvalidated: %u producer-full/mask/EOF/blocked images; %u registered pre-event replays; %u nonfull storage/discard controls\n",images,replays,controls);
 std::puts("method-level, unvalidated: actual producer/filter/pool/IRQ/mask/delete/save methods with callback recorder and mock image/audio/serializer; no native SCU line, partial host reservation policy, pending-line save, bus latency or hardware acknowledgement reassert qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-buffer-full-irq-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

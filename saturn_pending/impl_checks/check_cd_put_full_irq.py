#!/usr/bin/env python3
"""PUT End publishes BFUL after routing, without relying on drive or polling."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_buffer_full_irq.py')
scope={'__file__':str(fixture),'__name__':'put_full_irq_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions=(scope[k] for k in ('source','head','functions'))
tail=r'''
using D=saturn_cd_hle_device;
void fill(D &d,unsigned dest,unsigned count){for(unsigned i=0;i<count;++i){uint8_t id=255;auto *b=d.cd_alloc_block(&id);CHECK(b);b->size=2352;b->raw_data=true;auto &p=d.partitions[dest];if(p.size<0)p.size=0;p.blocks[p.numblks]=b;p.bnum[p.numblks++]=id;p.size+=2352;}}
void end(D &d,unsigned input,unsigned existing,unsigned count,bool discard,unsigned words,unsigned mask){
 const auto position=d.cd_curfad;d.cmd_end_data_transfer();
 CHECK(d.cr2==words&&!d.m_host_transfer_active&&d.xfertype32==D::XFERTYPE32_INVALID&&d.m_put_filter==255&&d.m_put_partition.numblks==0);
 CHECK(d.partitions[input].numblks==existing+(discard?0:count)&&d.freeblocks==(discard?200-existing:200-existing-count));
 CHECK(bool(d.hirqreg&BFUL)==(!discard&&existing+count==200));
 CHECK(d.m_host_irq_cb.level==bool(d.hirqreg&mask)&&d.cd_curfad==position&&(d.cd_stat&0xf00)==CD_STAT_PAUSE);
 // No producer step or HIRQ read is used to reveal a pending full cause.
 d.hirqmask_w(0,0,0xffff);CHECK(!d.m_host_irq_cb.level);d.hirqmask_w(0,BFUL,0xffff);CHECK(d.m_host_irq_cb.level==(!discard&&existing+count==200));
 if(!discard&&existing+count==200){d.cr1=0x6200;d.cr2=0;d.cr3=input<<8;d.cr4=1;d.cmd_delete_sector_data();CHECK(d.freeblocks==1&&!(d.hirqreg&BFUL)&&!d.m_host_irq_cb.level);}
}
int main(){unsigned images=0,replays=0;
 for(unsigned input:{0U,7U,23U})for(unsigned existing:{0U,198U,199U})for(unsigned count:{1U,200-existing})for(bool discard:{false,true})for(unsigned bytes:{0U,4U,2352U})for(unsigned mask:{0U,8U,128U,136U}){
  auto p=std::make_unique<D>();auto &d=*p;fill(d,input,existing);d.filters[input].condtrue=discard?255:input;d.cd_stat=CD_STAT_PAUSE;d.cd_curfad=1234;d.hirqreg=0;d.hirqmask=mask;
  d.cr1=0x60ff;d.cr2=0x300;d.cmd_set_sector_length();d.cr1=0x6400;d.cr2=0;d.cr3=input<<8;d.cr4=count;d.cmd_put_sector_data();CHECK(d.m_host_transfer_active&&d.freeblocks==200-existing-count);
  for(unsigned offset=0;offset<bytes;offset+=4)d.dataxfer_long_w(offset^0xdeadbeef);
  // Isolate End publication from the independent still-open reservation-
  // admission BFUL policy; do not infer an admission IRQ from this seed.
  d.hirqreg=0;d.update_hirq();d.register_state();d.capture();end(d,input,existing,count,discard,bytes/2,mask);
  d.m_host_transfer_active=false;d.hirqreg=d.hirqmask=0;d.freeblocks=42;d.m_put_filter=255;d.transpart=nullptr;d.xferdnum=0;d.m_host_irq_cb.level=false;d.restore();end(d,input,existing,count,discard,bytes/2,mask);++images;++replays;
 }
 std::printf("method-level, unvalidated: %u PUT End/capacity/route/payload/mask images; %u registered pre-End continuations\n",images,replays);
 std::puts("method-level, unvalidated: actual PUT reservation/port/End/filter/IRQ/mask/delete/save methods, callback recorder and mock serializer; existing whole-reservation/partial-PUT policy assumed, no admission BFUL timing, native FIFO/SCU or pending-line save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-put-full-irq-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

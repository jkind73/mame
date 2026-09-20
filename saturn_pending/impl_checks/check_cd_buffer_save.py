#!/usr/bin/env python3
"""Actual CD registrations/hooks/transfer replay with a byte serializer; method-level, unvalidated."""
import ast
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
head=next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name('check_cd_filter_routing.py').read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
head=head.replace('// TYPES','\n'.join(extract(header,s)+';' for s in ('struct filterT','struct blockT','struct partitionT','enum transT','enum trans32T')))
head=head.replace('#include <cstdint>','#include <cstdint>\n#include <vector>\n#include <type_traits>\nusing u8=uint8_t;using u32=uint32_t;')
head=head[:head.rfind('};')]+r'''
 partitionT *transpart=nullptr;int m_saved_transpart=-1,m_saved_cddevice=-1,cddevicenum=0xff,sectorstore=1;
 transT xfertype=XFERTYPE_INVALID;trans32T xfertype32=XFERTYPE32_INVALID;
 uint32_t xferoffs=0,xfersect=0,xfersectpos=0,xfersectnum=0,xferdnum=0;
 uint16_t cd_stat=0x4100,cr1=0,cr2=0,cr3=0,cr4=0,hirqreg=0;
 bool m_host_transfer_active=false;
 partitionT m_get_partition{};
 partitionT m_put_partition{};uint8_t m_put_filter=0xff;int sectlenout=2048;
 uint16_t m_xfer_raw_offset=0,m_xfer_raw_size=0;
 uint32_t m_xfer_raw_sector=0xffffffff;
 unsigned irqs=0;auto &machine(){return *this;}bool side_effects_disabled(){return false;}
 void update_hirq(){++irqs;}
 void device_pre_save();void device_post_load();void register_state();
 u32 dataxfer_long_r();void dataxfer_long_w(u32);void finish_get_delete();void cmd_end_data_transfer();
 void cd_free_block(blockT*);void cd_defragblocks(partitionT*);
 void finish_put();void cd_disconnect_filter_input(uint8_t);
 bool cd_transfer_wait();void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
 struct Entry{void *address;size_t bytes;std::vector<uint8_t> image;};std::vector<Entry> entries;
 template<class T>void save_item(T &value,const char*){entries.push_back({&value,sizeof(value),{}});}
 template<class T,class S,class F>void save_item(T &value,F S::*member,const char*){
  if constexpr(std::is_array_v<T>){for(auto &v:value)save_item(v.*member,"");}
  else save_item(value.*member,"");
 }
 void capture(){device_pre_save();for(auto &e:entries){e.image.resize(e.bytes);std::memcpy(e.image.data(),e.address,e.bytes);}}
 void restore(){for(auto &e:entries)std::memcpy(e.address,e.image.data(),e.bytes);device_post_load();}
};
#define NAME(x) x,#x
#define STRUCT_MEMBER(s,m) s,&std::remove_extent_t<decltype(s)>::m,#s "." #m
#define LOGXFER(...) ((void)0)
constexpr unsigned BFUL=8,CMOK=1,EHST=0x80,CD_STAT_TRANS=0x4000,CD_STAT_WAIT=0x8000;
u32 get_u32be(const u8 *p){return u32(p[0])<<24|u32(p[1])<<16|u32(p[2])<<8|p[3];}
u32 bcd_2_dec(u32 v){return (v>>4)*10+(v&15);}
void put_u32be(u8 *p,u32 v){for(int i=3;i>=0;--i){p[i]=v;v>>=8;}}
'''
start=extract(source,'void saturn_cd_hle_device::device_start()')
selected={'m_host_transfer_active','sectlenout','m_put_filter','sectlenin','m_xfer_raw_offset','m_xfer_raw_size','m_xfer_raw_sector','xfertype','xfertype32','xferoffs','xfersect','xfersectpos','xfersectnum','xferdnum','cddevicenum','lastbuf','freeblocks','buffull','sectorstore','cd_stat','cr1','cr2','cr3','cr4','hirqreg','m_saved_transpart','m_saved_cddevice'}
regs=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in selected]
regs+=re.findall(r'save_item\(STRUCT_MEMBER\((?:filters|partitions|blocks|curblock|m_put_partition|m_get_partition), \w+\)\);',start)
functions='void saturn_cd_hle_device::register_state(){\n'+'\n'.join(regs)+'\n}\n'
for name in ('device_pre_save','device_post_load'):
    signature='void saturn_cd_hle_device::'+name+'()'
    functions+=extract(source,signature) if signature in source else signature+' {}'
functions+='\n'+'\n'.join(extract(source,s) for s in (
 'inline u32 saturn_cd_hle_device::dataxfer_long_r()',
 'inline void saturn_cd_hle_device::dataxfer_long_w(',
 'void saturn_cd_hle_device::finish_get_delete()',
 'void saturn_cd_hle_device::cmd_end_data_transfer()',
 'void saturn_cd_hle_device::cd_free_block(',
 'void saturn_cd_hle_device::cd_defragblocks(',
 'uint8_t saturn_cd_hle_device::cd_filter_destination(',
 'void saturn_cd_hle_device::cd_disconnect_filter_input('))
sig='void saturn_cd_hle_device::finish_put()'
functions+='\n'+(extract(source,sig) if sig in source else sig+' {}')
sig='bool saturn_cd_hle_device::cd_transfer_wait()'
functions+='\n'+(extract(source,sig) if sig in source else sig+' {return false;}')
tail=r'''
using Device=saturn_cd_hle_device;
std::vector<uint8_t> image(const Device &d){
 std::vector<uint8_t> v;
 auto add=[&](const auto &value){auto *b=reinterpret_cast<const uint8_t*>(&value);v.insert(v.end(),b,b+sizeof(value));};
 for(const auto &b:d.blocks){add(b.size);add(b.FAD);add(b.data);add(b.chan);add(b.fnum);add(b.subm);add(b.cinf);}
 for(const auto &p:d.partitions){add(p.size);add(p.numblks);add(p.bnum);}
 for(const auto &f:d.filters){add(f.mode);add(f.fad);add(f.range);add(f.condtrue);add(f.condfalse);add(f.fid);add(f.chan);add(f.smmask);add(f.smval);add(f.cimask);add(f.cival);}
 add(d.freeblocks);add(d.xferdnum);add(d.xferoffs);add(d.xfersectnum);add(d.xfertype32);add(d.hirqreg);add(d.cr1);add(d.cr2);
 add(d.curblock.size);add(d.curblock.data);add(d.curblock.FAD);add(d.curblock.chan);add(d.curblock.fnum);add(d.curblock.subm);add(d.curblock.cinf);return v;
}
std::vector<uint32_t> finish(Device &d,bool put,unsigned consumed){
 std::vector<uint32_t> reads;
 for(unsigned word=consumed/4;word<4676/4;++word){if(put)d.dataxfer_long_w(word^0xa55a7604);else reads.push_back(d.dataxfer_long_r());}
 if(!put)d.dataxfer_long_r();d.cmd_end_data_transfer();return reads;
}
int main(){
 unsigned replays=0;
 for(unsigned p=0;p<24;++p)for(auto mode:{Device::XFERTYPE32_GETSECTOR,Device::XFERTYPE32_GETDELETESECTOR,Device::XFERTYPE32_PUTSECTOR})
 for(unsigned cut:{0U,4U,2320U,2324U,2328U,4672U,4676U}){
  auto d=std::make_unique<Device>();auto &part=d->partitions[p];part.size=0;part.numblks=3;
  const unsigned ids[]={0,67,199},sizes[]={2048,2324,2352};
  for(unsigned i=0;i<3;++i){auto &b=d->blocks[ids[i]];b.size=sizes[i];b.FAD=150+i;b.fnum=2+i;b.chan=5+i;b.subm=0x15;b.cinf=0x42;
   for(unsigned j=0;j<2352;++j)b.data[j]=uint8_t(i*37+j);
   part.blocks[i]=&b;part.bnum[i]=ids[i];part.size+=b.size;
  }
  d->freeblocks=197;d->transpart=&part;d->xfertype32=mode;d->xfersectpos=1;d->xfersectnum=2;
  d->cddevicenum=(p+7)%24;d->cddevice=&d->filters[d->cddevicenum];d->lastbuf=p;
  for(unsigned f=0;f<24;++f){d->filters[f].mode=0x45;d->filters[f].fid=f;d->filters[f].smmask=0x7f;d->filters[f].smval=0x15;d->filters[f].fad=150+f;d->filters[f].range=800;}
  d->curblock=d->blocks[67];const bool put=mode==Device::XFERTYPE32_PUTSECTOR;
  for(unsigned word=0;word<cut/4;++word){if(put)d->dataxfer_long_w(word^0xa55a7604);else d->dataxfer_long_r();}
  d->register_state();d->capture();const auto expected_reads=finish(*d,put,cut);const auto expected=image(*d);
  // Overwrite every backing family, including raw pointers. Restore from
  // the production registrations, not by copying the device struct.
  for(auto &b:d->blocks){b={};b.size=-1;std::fill(std::begin(b.data),std::end(b.data),0xee);}
  for(auto &part:d->partitions){part={};std::fill(std::begin(part.bnum),std::end(part.bnum),0xff);}
  for(auto &f:d->filters)f={};d->curblock={};d->transpart=nullptr;d->cddevice=nullptr;
  d->freeblocks=200;d->xfersectnum=0;d->xferoffs=0;d->xfertype32=Device::XFERTYPE32_INVALID;
  const unsigned old_irqs=d->irqs;d->restore();CHECK(d->irqs==old_irqs);
  CHECK(d->transpart==&d->partitions[p]&&d->cddevice==&d->filters[(p+7)%24]);
  for(unsigned i=0;i<3;++i)CHECK(d->partitions[p].blocks[i]==&d->blocks[ids[i]]);
  CHECK(finish(*d,put,cut)==expected_reads);CHECK(image(*d)==expected);++replays;
 }
 auto d=std::make_unique<Device>();d->cddevicenum=3;d->cddevice=nullptr;d->transpart=nullptr;
 d->register_state();d->capture();d->cddevice=&d->filters[2];d->transpart=&d->partitions[2];d->restore();
 CHECK(!d->cddevice&&!d->transpart&&d->cddevicenum==3);
 std::printf("method-level, unvalidated: %u registered-image GET/GETDELETE/PUT replays across 24 partitions and seven cuts; disconnected pointer and no-IRQ-edge controls\n",replays);
 std::puts("method-level, unvalidated: actual registrations/hooks/transfer bodies, mock byte serializer; NOT native MAME file save/load; other CD state families outside this probe");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-save-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

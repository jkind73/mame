#!/usr/bin/env python3
"""DATATRNS metadata word aggregation and nonconsuming inspection; method-level only."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_sector_word_port.py')
scope={'__file__':str(fixture),'__name__':'metadata_port_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+'void cmd_get_toc();void cd_readTOC();\n}',1)
head=head.replace('int get_last_track(){return 99;}', 'int get_last_track(){return 3;}')
head=head.replace('unsigned get_track_start(unsigned t){return 150+t*10000;}', 'unsigned get_track_start(unsigned t){return t==0xaa?10000:t*3000;}')
head+='\nvoid put_u24be(uint8_t *p,uint32_t d){p[0]=d>>16;p[1]=d>>8;p[2]=d;}\n'
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_get_toc()')+'\n'+extract(source,'void saturn_cd_hle_device::cd_readTOC(')
start=extract(source,'void saturn_cd_hle_device::device_start()');reg=extract(functions,'void saturn_cd_hle_device::register_state()')
fields={'tocbuf','subqbuf','subrwbuf','finfbuf','xfercount','m_file_info_words'}
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in fields and m[0] not in reg]
functions=functions.replace(reg,reg[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
using D=saturn_cd_hle_device;
std::vector<uint16_t> setup(D &d,unsigned kind,unsigned pattern,unsigned files){std::vector<uint16_t> words;
 d.cd_stat=CD_STAT_PAUSE;d.cd_curfad=150;d.xfertype32=D::XFERTYPE32_INVALID;d.xfercount=d.xferdnum=0;
 if(kind>=3){d.curdir.resize(files+2);for(unsigned id=2;id<files+2;++id){auto &e=d.curdir[id];e.firstfad=0x123400+id;e.length=0x87650000+id;e.file_unit_size=pattern;e.interleave_gap_size=7;e.file_number=id;e.flags=0x81;
  words.insert(words.end(),{uint16_t(e.firstfad>>16),uint16_t(e.firstfad),uint16_t(e.length>>16),uint16_t(e.length),uint16_t((e.file_unit_size<<8)|e.interleave_gap_size),uint16_t((e.file_number<<8)|e.flags)});}
  d.cr1=0x7300;d.cr3=kind==3?0:0xff;d.cr4=kind==3?2:0xffff;d.cmd_get_target_file_info();CHECK(d.cr2==words.size());
 }else{uint8_t *out=nullptr;unsigned count=0;
  if(kind==0){d.cr1=0x0200;d.cmd_get_toc();CHECK(d.cr2==204);out=d.tocbuf;count=204;}
  else{d.m_host_transfer_active=true;d.xfertype=kind==1?D::XFERTYPE_SUBQ:D::XFERTYPE_SUBRW;out=kind==1?d.subqbuf:d.subrwbuf;count=kind==1?5:12;}
  // Deliberate byte patterns exercise the port, not subcode content semantics.
  for(unsigned i=0;i<count*2;++i)out[i]=uint8_t(i*17+pattern*129);for(unsigned i=0;i<count;++i)words.push_back((uint16_t(out[i*2])<<8)|out[i*2+1]);
 }
 CHECK(d.m_host_transfer_active);return words;
}
unsigned inspections=0;
void inspect(D &d){const auto type=d.xfertype;const auto count=d.xfercount;const auto bytes=d.xferdnum,irqs=d.irqs;const auto flags=d.hirqreg;const auto owner=d.m_host_transfer_active;uint8_t saved[12];std::memcpy(saved,d.finfbuf,12);
 d.suppress=true;for(unsigned mask:{0xffffffffU,0xffff0000U,0xffffU}){d.datatrns_r(0,mask);CHECK(d.xfertype==type&&d.xfercount==count&&d.xferdnum==bytes&&d.irqs==irqs&&d.hirqreg==flags&&d.m_host_transfer_active==owner&&!std::memcmp(saved,d.finfbuf,12));++inspections;}d.suppress=false;
}
void finish(D &d,const std::vector<uint16_t> &words,unsigned cut,unsigned mode){for(unsigned pos=cut;pos<words.size();){inspect(d);
  const bool wide=mode==0 || (mode==1?pos%3!=0:pos%4==1);const unsigned mask=wide?0xffffffff:(pos&1)?0xffff0000:0xffff;
  uint32_t expected=words[pos];if(wide)expected=(expected<<16)|(pos+1<words.size()?words[pos+1]:0);else if(mask==0xffff0000)expected<<=16;
  CHECK(d.datatrns_r(pos&1,mask)==expected);pos+=std::min<unsigned>(wide?2:1,words.size()-pos);CHECK(d.xferdnum==pos*2&&d.m_host_transfer_active);
 }CHECK(d.xfertype==D::XFERTYPE_INVALID&&d.xfercount==0);inspect(d);const auto bytes=d.xferdnum;d.datatrns_r(0,0xffffffff);d.datatrns_r(0,0xffff);CHECK(d.xferdnum==bytes&&d.m_host_transfer_active);
 d.cmd_end_data_transfer();CHECK(d.cr2==words.size()&&!d.m_host_transfer_active);inspect(d);
}
int main(){unsigned images=0,replays=0;
 for(unsigned kind=0;kind<5;++kind)for(unsigned pattern:{0U,1U,128U,255U})for(unsigned mode=0;mode<3;++mode)for(unsigned files:{1U,2U,254U}){
  if(kind!=4&&files!=1)continue;const unsigned total=kind==0?204:kind==1?5:kind==2?12:files*6;
  for(unsigned cut=0;cut<=total;++cut){if(kind==4&&cut!=0&&cut!=1&&cut!=5&&cut!=6&&cut!=total-1&&cut!=total)continue;
   auto p=std::make_unique<D>();auto &d=*p;const auto words=setup(d,kind,pattern,files);CHECK(words.size()==total);
   for(unsigned i=0;i<cut;++i)CHECK(d.datatrns_r(0,0xffff)==words[i]);inspect(d);d.register_state();d.capture();finish(d,words,cut,mode);
   d.xfercount=d.xferdnum=0;d.xfertype=D::XFERTYPE_INVALID;d.m_host_transfer_active=false;d.m_file_info_words=0;std::memset(d.tocbuf,0xee,sizeof(d.tocbuf));std::memset(d.subqbuf,0xdd,sizeof(d.subqbuf));std::memset(d.subrwbuf,0xcc,sizeof(d.subrwbuf));std::memset(d.finfbuf,0xbb,sizeof(d.finfbuf));
   d.restore();CHECK(d.xferdnum==cut*2&&d.m_host_transfer_active);finish(d,words,cut,mode);++images;++replays;
  }
 }
 std::printf("method-level, unvalidated: %u metadata width/cut/payload images; %u registered port replays; %u nonconsuming masked inspections\n",images,replays,inspections);
 std::puts("method-level, unvalidated: actual DATATRNS/metadata/TOC/file-info/End/save methods; authored TOC, seeded Q/RW contexts, directory held outside replay, mock bus/image/IRQ/serializer; no subcode layout, native aperture/FIFO prefetch/timing/save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-metadata-port-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

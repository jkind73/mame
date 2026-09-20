#!/usr/bin/env python3
"""ISO/XA directory metadata through both file-info streams; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_transfer_length.py')
scope={'__file__':str(fixture),'__name__':'xa_file_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract=(scope[k] for k in ('source','head','functions','extract'))
head=head.replace('// TYPES',scope['types'])
head=head[:head.rfind('};')]+r'''
 std::array<uint8_t,2048> media{};int numfiles=0,firstfile=0;
 void cd_readblock(uint32_t fad,uint8_t *out){CHECK(fad==1000);std::copy(media.begin(),media.end(),out);}
 void make_dir_current(uint32_t,uint32_t);
};
constexpr uint32_t MAX_DIR_SIZE=256*1024;
uint32_t get_u32le(const uint8_t *p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
uint16_t get_u16le(const uint8_t *p){return p[0]|(p[1]<<8);}
'''
functions+='\n'+extract(source,'void saturn_cd_hle_device::make_dir_current(')
tail=r'''
using D=saturn_cd_hle_device;
void both32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;++i){p[i]=v>>(i*8);p[4+i]=v>>(24-i*8);}}
void check(D &d,unsigned name,unsigned kind,unsigned attr,unsigned file){
 d.media.fill(0);for(unsigned i=0;i<2;++i){auto *r=d.media.data()+i*34;r[0]=34;r[32]=1;r[33]=i;r[25]=2;both32(r+2,850);both32(r+10,2048);}
 auto *r=d.media.data()+68;const unsigned base=(33+name+1)&~1U;const unsigned extra=kind==0?0:kind==4?13:14;CHECK(base+extra<=255);
 r[0]=base+extra;r[32]=name;std::fill_n(r+33,name,'F');if(name>1){r[33]='X';r[34]='A';}if(name>=3){r[33+name-2]=';';r[33+name-1]='1';}
 both32(r+2,65536-150);both32(r+10,4096);r[25]=attr^file;
 if(extra){r[base+4]=attr;r[base+5]=0x55;r[base+6]=kind==2?'Y':'X';r[base+7]=kind==3?'B':'A';r[base+8]=file;}
 d.make_dir_current(1000,2048);CHECK(d.curdir.size()==3);
 const unsigned number=kind==1?file:0;const unsigned attributes=((attr^file)&2)|(kind==1?(attr&0xf8):0);
 CHECK(d.curdir[2].file_number==number&&d.curdir[2].flags==attributes);
 CHECK(d.curdir[2].name[std::min(name,127U)]==0);
 for(bool bulk:{false,true}){d.cr1=0x7300;d.cr3=bulk?0xff:0;d.cr4=bulk?0xffff:2;d.cmd_get_target_file_info();
  CHECK(d.dataxfer_word_r()==1&&d.dataxfer_word_r()==0&&d.dataxfer_word_r()==0&&d.dataxfer_word_r()==4096&&d.dataxfer_word_r()==0&&d.dataxfer_word_r()==((number<<8)|attributes));
  d.cmd_end_data_transfer();CHECK(d.cr2==6&&!d.m_host_transfer_active);
 }
}
int main(){D d;unsigned images=0,names=0;
 for(unsigned name:{3U,4U})for(unsigned kind=0;kind<5;++kind)for(unsigned attr=0;attr<256;++attr)for(unsigned file=0;file<256;++file){check(d,name,kind,attr,file);++images;}
 for(unsigned name:{1U,2U,31U,32U,127U,128U,200U,221U})for(unsigned kind=0;kind<5;++kind){if(name==221&&kind)continue;check(d,name,kind,0xf8,0xa5);++names;}
 std::printf("method-level, unvalidated: %u padded-name/signature/XA attribute/file-number images through single and table streams; %u long-name/system-use boundary controls\n",images,names);
 std::puts("method-level, unvalidated: actual sector-bounded parser/File Info/word/End; all-bit and long-name cases are storage diagnostics, not complete ISO images, XA playback/filtering, held-window or native title qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-xa-info-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

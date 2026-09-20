#!/usr/bin/env python3
"""Selected directory extent and record bounds; method-level, unvalidated."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text,signature):
    a=text.index(signature);b=text.index('{',a)+1;depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}');b+=1
    return text[a:b]
head=r'''
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <vector>
using u32=uint32_t;
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
#define LOGWARN(...) ((void)0)
#define popmessage(...) ((void)0)
constexpr uint32_t MAX_DIR_SIZE=256*1024;
uint32_t get_u32le(const uint8_t *p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
uint16_t get_u16le(const uint8_t *p){return p[0]|(p[1]<<8);}
using Sector=std::array<uint8_t,2048>;
struct saturn_cd_hle_device {
// TYPES
 direntryT curroot{};std::vector<direntryT>curdir;
 int sectlenin=2048,numfiles=0,firstfile=0;
 std::map<uint32_t,Sector>media;std::vector<uint32_t>reads;
 void cd_readblock(uint32_t fad,uint8_t *out){reads.push_back(fad);const auto it=media.find(fad);if(it!=media.end())std::copy(it->second.begin(),it->second.end(),out);}
 void read_new_dir(uint32_t);
 // DECLARE
};
'''
head=head.replace('// TYPES',extract(header,'struct direntryT')+';')
head=head.replace('// DECLARE','void make_dir_current(uint32_t,uint32_t);' if 'make_dir_current(uint32_t fad, uint32_t length)' in source else 'void make_dir_current(uint32_t);')
functions='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::read_new_dir(', 'void saturn_cd_hle_device::make_dir_current('))
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using D=saturn_cd_hle_device;
void both32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;++i){p[i]=v>>(i*8);p[4+i]=v>>(24-i*8);}}
void record(uint8_t *p,unsigned fad,unsigned bytes,bool directory,unsigned id){
 p[0]=directory?34:36;both32(p+2,fad-150);both32(p+10,bytes);p[18]=126;p[19]=9;p[20]=19;p[25]=directory?2:0;p[28]=1;p[31]=1;p[32]=directory?1:3;p[33]=id;if(!directory){p[34]=';';p[35]='1';}
}
void root(D &d,unsigned bytes){auto &pvd=d.media[166];pvd[0]=1;std::memcpy(&pvd[1],"CD001",5);pvd[6]=1;record(&pvd[156],1000,bytes,true,0);}
void child(D &d,unsigned sectors,unsigned bytes,unsigned rootbytes){
 auto &p=d.media[1000];record(&p[0],1000,rootbytes,true,0);record(&p[34],1000,rootbytes,true,1);record(&p[68],2000,bytes,true,'C');
 for(unsigned i=0;i<sectors;++i){auto &s=d.media[2000+i];unsigned at=0;if(i==0){record(&s[0],2000,bytes,true,0);record(&s[34],1000,rootbytes,true,1);at=68;}record(&s[at],4000+i,1234+i,false,'A'+i%26);}
 record(d.media[2000+sectors].data(),8000,777,false,'Z');
}
int main(){unsigned extents=0,bounds=0;
 for(unsigned r:{1U,2U,4U,128U})for(unsigned c:{1U,2U,3U,7U,128U})for(unsigned fetch:{2048U,2336U,2340U,2352U}){
  D d;d.sectlenin=fetch;root(d,r*2048);child(d,c,c*2048,r*2048);d.read_new_dir(0xffffff);CHECK(d.curdir.size()==3&&d.curroot.length==r*2048);
  d.reads.clear();d.read_new_dir(2);CHECK(d.curdir.size()==c+2&&d.numfiles==int(c+2)&&d.firstfile==2&&d.curroot.length==r*2048);
  CHECK(d.reads.size()==c);for(unsigned i=0;i<c;++i){CHECK(d.reads[i]==2000+i);const auto &f=d.curdir[i+2];CHECK(f.firstfad==4000+i&&f.length==1234+i&&f.flags==0&&f.record_size==36&&f.name[0]=='A'+i%26&&f.name[1]==';'&&f.name[2]=='1'&&f.name[3]==0);}
  ++extents;
 }
 // The existing HLE cap is a guard, not a Saturn directory-size claim.
 for(unsigned bytes:{0U,1U,33U,34U,68U,104U,2047U,2048U,2049U,MAX_DIR_SIZE+2048U,0xffffffffU}){
  D d;root(d,2048);const unsigned sectors=std::min<uint32_t>(bytes,MAX_DIR_SIZE)/2048+(std::min<uint32_t>(bytes,MAX_DIR_SIZE)%2048!=0);child(d,sectors,bytes,2048);d.read_new_dir(0xffffff);d.reads.clear();d.read_new_dir(2);CHECK(d.reads.size()==sectors);
  if(bytes<34)CHECK(d.curdir.empty());if(bytes==34)CHECK(d.curdir.size()==1);if(bytes==68)CHECK(d.curdir.size()==2);if(bytes==104)CHECK(d.curdir.size()==3);++bounds;
 }
 // Malformed record diagnostics: don't cross a logical block or trust names
 // beyond their record. A following block remains independently readable.
 for(unsigned damage=0;damage<5;++damage){D d;d.curdir.resize(1);d.curdir[0].firstfad=2000;d.curdir[0].length=4096;d.curroot.length=4096;auto &s=d.media[2000];
  record(s.data(),4000,100,false,'A');if(damage==0)s[0]=1;if(damage==1)s[0]=33;if(damage==2)s[32]=0;if(damage==3)s[32]=255;
  if(damage==4){s={};for(unsigned i=0;i<60;++i)record(&s[i*34],4000+i,100,true,'D');s[2040]=36;}
  record(d.media[2001].data(),9000,777,false,'Z');d.read_new_dir(0);CHECK(d.curdir.size()==(damage==4?61:1)&&d.curdir.back().firstfad==9000);++bounds;
 }
 std::printf("method-level, unvalidated: %u root/child extent/fetch images; %u partial-length/cap/malformed-record controls\n",extents,bounds);
 std::puts("method-level, unvalidated: actual directory selection/parser with authored sectors; no native media timing, held-window/XA/error-policy/oversize-directory/save qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-dir-extent-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

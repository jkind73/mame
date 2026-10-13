#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run the actual CD WAVE parser with checked chunk/padding fixtures."""
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parent.parent
source=Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/lib/util/cdrom.cpp'
s=source.read_text();a=s.index('uint32_t cdrom_file::parse_wav_sample(');b=s.index('\n/**',a)
code=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>
#include <memory>
#include <system_error>
#include <vector>
#include <cstdio>
#define OPEN_FLAG_READ 1
template<class... T> void osd_printf_error(const char*,T&&...){ }
uint32_t little_endianize_int32(uint32_t v){return v;}
uint16_t little_endianize_int16(uint16_t v){return v;}
struct osd_file {
 using ptr=std::unique_ptr<osd_file>;
 static inline std::vector<char> contents;
 static inline bool short_reads=false;
 static std::error_condition open(const std::string&,int,ptr &p,uint64_t &size){p=std::make_unique<osd_file>();size=contents.size();return {};}
 std::error_condition read(void *p,uint64_t offset,uint32_t size,uint32_t &actual){
  actual=offset<contents.size()?std::min<uint64_t>(size,contents.size()-offset):0;
  if(short_reads&&actual)--actual;
  if(actual)memcpy(p,contents.data()+offset,actual);return {};
 }
};
struct cdrom_file {static uint32_t parse_wav_sample(std::string_view,uint32_t*);};
METHOD
void put(std::vector<char> &v,uint32_t n){for(unsigned i=0;i<4;++i)v.push_back(n>>(8*i));}
void chunk(std::vector<char>&v,const char *name,const std::vector<char>&data){v.insert(v.end(),name,name+4);put(v,data.size());v.insert(v.end(),data.begin(),data.end());if(data.size()&1)v.push_back(0);}
int main(){
 std::vector<char> fmt={1,0,2,0};put(fmt,44100);put(fmt,176400);fmt.insert(fmt.end(),{4,0,16,0});
 auto riff=[](std::vector<char> body){std::vector<char> v={'R','I','F','F'};put(v,body.size()+4);v.insert(v.end(),{'W','A','V','E'});v.insert(v.end(),body.begin(),body.end());return v;};
 auto check=[](std::vector<char> v,uint32_t length,uint32_t offset=0){osd_file::contents=std::move(v);uint32_t o=0xdeadbeef;assert(cdrom_file::parse_wav_sample("test.wav",&o)==length);if(length)assert(o==offset);else assert(o==0);};
 std::vector<char> body;chunk(body,"fmt ",fmt);chunk(body,"data",std::vector<char>(2352));auto valid=riff(body);check(valid,2352,44);
 body.clear();chunk(body,"JUNK",{1,2,3});chunk(body,"fmt ",fmt);chunk(body,"LIST",{1});chunk(body,"data",std::vector<char>(8));check(riff(body),8,66);
 // All truncations, including incomplete chunk headers and payloads, fail.
 for(unsigned n=0;n<valid.size();++n)check(std::vector<char>(valid.begin(),valid.begin()+n),0);
 body.clear();chunk(body,"fmt ",{1,0,2,0});chunk(body,"data",std::vector<char>(8));check(riff(body),0);
 body.clear();chunk(body,"fmt ",fmt);chunk(body,"data",std::vector<char>(3));check(riff(body),0);
 body.clear();chunk(body,"fmt ",fmt);chunk(body,"data",{});check(riff(body),0);
 body.clear();chunk(body,"data",std::vector<char>(8));check(riff(body),0);
 osd_file::short_reads=true;check(valid,0);osd_file::short_reads=false;
 std::puts("CDROM_WAV_PASS padded chunks, PCM, all truncations, short reads and malformed lengths");
}
'''.replace('METHOD',s[a:b])
with tempfile.TemporaryDirectory(prefix='cdrom-wav-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise production CUE parsing and real TOC types under ASan/UBSan."""
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parent.parent
source=Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/lib/util/cdrom.cpp'
s=source.read_text()
def method(signature):
 a=s.index(signature);b=s.index('{',a);depth=1;i=b+1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
methods='\n'.join(method(signature) for signature in (
 'std::string cdrom_file::get_file_path(', 'int cdrom_file::tokenize(',
 'int cdrom_file::msf_to_frames(', 'void cdrom_file::get_info_from_type_string(',
 'void cdrom_file::convert_type_string_to_track_info(',
 'void cdrom_file::convert_subtype_string_to_track_info(',
 'std::error_condition cdrom_file::parse_cue('))
code=r'''
#include "cdrom.h"
#include <cassert>
#include <array>
#include <charconv>
#include <cctype>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
std::error_category const &chd_category() noexcept{return std::generic_category();}
std::string strmakelower(std::string_view in){std::string out(in);for(char &c:out)c=std::tolower(static_cast<unsigned char>(c));return out;}
template<class... T> void osd_printf_error(const char*,T&&...){ }
#define TOKENIZE i = tokenize(linebuffer,i,std::size(linebuffer),token,std::size(token));
uint64_t cdrom_file::get_file_size(std::string_view name){std::error_code ec;auto size=std::filesystem::file_size(std::string(name),ec);return ec?0:size;}
#define OTHER_PARSER(name) std::error_condition cdrom_file::name(std::string_view,toc&,track_input_info&){return chd_file::error::UNSUPPORTED_FORMAT;}
OTHER_PARSER(parse_gdi) OTHER_PARSER(parse_toc) OTHER_PARSER(parse_nero) OTHER_PARSER(parse_iso)
#define EXTRA_VERBOSE 0
template<class... T> void osd_printf_verbose(const char*,T&&...){ }
bool cdrom_file::is_gdicue(std::string_view){return false;}
uint32_t cdrom_file::parse_wav_sample(std::string_view,uint32_t*){return 0;}
bool core_filename_ends_with(std::string_view name,std::string_view suffix){return name.ends_with(suffix);}
METHODS
int main(){
 std::ofstream f("data.bin",std::ios::binary);f.seekp(2048*8-1);f.put(0);f.close();
 cdrom_file::toc toc;cdrom_file::track_input_info info;
 auto parse=[&](std::string text){std::ofstream("disc.cue")<<text;return cdrom_file::parse_cue("disc.cue",toc,info);};
 assert(!parse("FILE data.bin BINARY\nTRACK 01 MODE1/2048\nINDEX 01 00:00:00\n"));assert(toc.numtrks==1&&toc.tracks[0].frames==8);
 for(const char *bad:{"0","100","4294967296","-1","abc","2","1x"})assert(parse(std::string("FILE data.bin BINARY\nTRACK ")+bad+" MODE1/2048\nINDEX 01 00:00:00\n"));
 for(const char *bad:{"INDEX 01 00:00:00","PREGAP 00:02:00","POSTGAP 00:02:00","FLAGS PRE","REM LEAD-OUT 00:10:00"})assert(parse(bad));
 assert(parse(""));
 assert(parse("TRACK 01 MODE1/2048\nINDEX 01 00:00:00\n"));
 for(const char *bad:{"100","4294967296","abc","1x","-1"})assert(parse(std::string("FILE data.bin BINARY\nTRACK 01 MODE1/2048\nINDEX ")+bad+" 00:00:00\n"));
 assert(parse("FILE data.bin BINARY\nTRACK 01 MODE1/2048\nINDEX 01 00:00:00\nTRACK 01 MODE1/2048\nINDEX 01 00:00:00\n"));
 assert(!parse("FILE data.bin BINARY\nTRACK 01 MODE1/2048\nINDEX 01 00:00:00\nTRACK 02 MODE1/2048\nINDEX 01 00:00:04\n"));assert(toc.tracks[0].frames==4&&toc.tracks[1].frames==4&&info.track[1].offset==8192);
 assert(parse("FILE data.bin BINARY\nTRACK 01 MODE1/2048\nINDEX 01 00:00:04\nTRACK 02 MODE1/2048\nINDEX 01 00:00:00\n"));
 assert(parse("FILE data.bin BINARY\nTRACK 01 MODE1/2048\nINDEX 01 00:00:00\nTRACK 02 MODE1/2048\nINDEX 01 00:01:00\n"));
 std::string tracks;
 for(unsigned n=1;n<=99;++n){char num[16];std::snprintf(num,sizeof(num),"%02u",n);std::string name="data"+std::string(num)+".bin";std::filesystem::copy_file("data.bin",name);tracks+="FILE "+name+" BINARY\nTRACK "+std::string(num)+" MODE1/2048\nINDEX 01 00:00:00\n";}
 assert(!parse(tracks)&&toc.numtrks==99);
 assert(parse(tracks+"FILE data.bin BINARY\n"));
 assert(parse(tracks+"TRACK 100 MODE1/2048\nINDEX 01 00:00:00\n"));
 std::puts("CDROM_CUE_PASS track/index bounds, pre-track directives, numbering and 99-track limit");
}

'''.replace('METHODS',methods)
with tempfile.TemporaryDirectory(prefix='cdrom-cue-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(root/'src/lib/util'),'-I'+str(root/'src/osd'),str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],cwd=out,check=True)

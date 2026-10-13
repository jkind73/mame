#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise production CDRDAO parsing and real TOC types under ASan/UBSan."""
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
 'std::error_condition cdrom_file::parse_toc('))
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
#define osd_printf_error(...) std::fprintf(stderr,__VA_ARGS__)
#define TOKENIZE i = tokenize(linebuffer,i,std::size(linebuffer),token,std::size(token));
uint64_t cdrom_file::get_file_size(std::string_view name){std::error_code ec;auto size=std::filesystem::file_size(std::string(name),ec);return ec?0:size;}
#define OTHER_PARSER(name) std::error_condition cdrom_file::name(std::string_view,toc&,track_input_info&){return chd_file::error::UNSUPPORTED_FORMAT;}
OTHER_PARSER(parse_gdi) OTHER_PARSER(parse_cue) OTHER_PARSER(parse_nero) OTHER_PARSER(parse_iso)
METHODS
int main(){
 auto file=[](const char *name,size_t size){std::ofstream f(name,std::ios::binary);f.seekp(size-1);f.put(0);};
 file("data.bin",2048*8);file("audio.bin",2352*8);file("sub.bin",2448*8);file("partial.bin",2049);
 cdrom_file::toc toc;cdrom_file::track_input_info info;
 auto parse=[&](std::string text){std::ofstream("disc.toc")<<text;return cdrom_file::parse_toc("disc.toc",toc,info);};
 for(const char *command:{"NO COPY","COPY","PRE_EMPHASIS","TWO_CHANNEL_AUDIO","FOUR_CHANNEL_AUDIO","DATAFILE data.bin","AUDIOFILE audio.bin 0","FILE audio.bin 0","START 00:02:00"})assert(parse(command));
 assert(!parse("TRACK MODE1\nDATAFILE data.bin\n"));assert(toc.numtrks==1 && toc.tracks[0].frames==8 && info.track[0].offset==0);
 assert(!parse("TRACK MODE1\nDATAFILE data.bin 8192\n"));assert(toc.tracks[0].frames==4 && info.track[0].offset==0);
 assert(!parse("TRACK AUDIO\nFILE audio.bin 588 1176\n"));assert(toc.tracks[0].frames==2 && info.track[0].offset==2352);
 assert(!parse("TRACK AUDIO\nAUDIOFILE audio.bin 588\n"));assert(toc.tracks[0].frames==7 && info.track[0].offset==2352);
 assert(!parse("TRACK AUDIO\nFILE audio.bin 100 588\n"));assert(toc.tracks[0].frames==1 && info.track[0].offset==400);
 for(const char *command:{"FILE","AUDIOFILE"}){
  assert(!parse(std::string("TRACK AUDIO\n")+command+" audio.bin 00:00:02\n"));assert(toc.tracks[0].frames==6 && info.track[0].offset==2352*2);
  assert(!parse(std::string("TRACK AUDIO\n")+command+" audio.bin 00:00:02 00:00:00\n"));assert(toc.tracks[0].frames==6);
  assert(!parse(std::string("TRACK AUDIO\n")+command+" audio.bin 00:00:02 00:00:03\n"));assert(toc.tracks[0].frames==3 && info.track[0].offset==2352*2);
 }
 assert(!parse("TRACK MODE1\nDATAFILE data.bin 00:00:03\nTRACK MODE1\nDATAFILE data.bin 00:00:04\n"));assert(toc.tracks[0].frames==3 && toc.tracks[1].frames==4 && info.track[1].offset==0);
 assert(!parse("TRACK AUDIO\nFILE audio.bin #2352 00:00:02 00:00:03\n"));assert(info.track[0].offset==2352*3 && toc.tracks[0].frames==3);
 assert(!parse("TRACK AUDIO RW_RAW\nFILE sub.bin 00:00:02\n"));assert(info.track[0].offset==2448*2 && toc.tracks[0].frames==6);
 assert(!parse("TRACK AUDIO\nFILE audio.bin SWAP 0 00:00:03\n"));assert(info.track[0].swap && toc.tracks[0].frames==3);
 assert(parse("TRACK MODE1\nDATAFILE missing.bin\n"));
 assert(parse("TRACK MODE1\nDATAFILE partial.bin\n"));
 assert(parse("TRACK AUDIO\nFILE audio.bin 00:00:09\n"));
 for(const char *bad:{"00:60:00","00:00:75","-1","+1","00:00","00:00:00:00","18446744073709551616","#4294967296","SWAP nonsense"})assert(parse(std::string("TRACK AUDIO\nFILE audio.bin ")+bad+"\n"));
 assert(parse("TRACK AUDIO\nFILE audio.bin 0 1\n"));
 assert(parse("TRACK MODE1\nDATAFILE data.bin 204800\n"));
 assert(parse("TRACK MODE1\nDATAFILE data.bin 2048 2048 2048\n"));
 std::string tracks;for(unsigned i=0;i<99;++i)tracks+="TRACK MODE1\nDATAFILE data.bin\n";
 assert(!parse(tracks) && toc.numtrks==99);assert(parse(tracks+"TRACK MODE1\nDATAFILE data.bin\n"));
 std::puts("CDROM_TOC_PASS actual parser: track bounds, missing lengths, starts, subcode strides and explicit lengths");
}
'''.replace('METHODS',methods)
with tempfile.TemporaryDirectory(prefix='cdrom-toc-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(root/'src/lib/util'),'-I'+str(root/'src/osd'),str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],cwd=out,check=True)

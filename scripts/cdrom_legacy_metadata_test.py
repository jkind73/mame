#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise the actual legacy CD metadata decoder under ASan/UBSan."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'src/lib/util/cdrom.cpp').read_text()
start = source.index('\t/* reconstruct the TOC from it */')
end = source.index('\n\n/*-------------------------------------------------', start)
body = source[start:end].rstrip()
assert body.endswith('}')
header = (root / 'src/lib/util/cdrom.h').read_text()
track = header[header.index('\tstruct track_info'):header.index('\n\n\tstruct toc')]
fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>
#include <system_error>
constexpr unsigned MAX_TRACKS=99, METADATA_WORDS=595;
uint32_t swapendian_int32(uint32_t x) { return __builtin_bswap32(x); }
@@TRACK@@
struct table { uint32_t numtrks=0, numsessions=0; track_info tracks[100]{}; };
std::error_condition decode(std::vector<uint8_t> oldmetadata, table &toc) {
@@BODY@@
int main() {
 // Every truncated length must fail before reading beyond the metadata.
 for (unsigned size=0; size<METADATA_WORDS*4; ++size) {
  table t; assert(decode(std::vector<uint8_t>(size),t)); assert(t.numtrks==0);
 }
 for (bool swapped : {false,true}) {
  for (unsigned count : {1U,99U}) {
   std::vector<uint32_t> words(METADATA_WORDS);
   words[0]=count;
   for(unsigned i=0;i<99;++i) for(unsigned j=0;j<6;++j) words[1+i*6+j]=i*100+j+1;
   if(swapped) for(auto &w:words) w=swapendian_int32(w);
   std::vector<uint8_t> bytes(words.size()*4); memcpy(bytes.data(),words.data(),bytes.size());
   table t; assert(!decode(bytes,t)); assert(t.numtrks==count && t.numsessions==1);
   for(unsigned i=0;i<99;++i) {
    auto const &a=t.tracks[i];
    assert(a.trktype==i*100+1 && a.subtype==i*100+2 && a.datasize==i*100+3);
    assert(a.subsize==i*100+4 && a.frames==i*100+5 && a.extraframes==i*100+6);
    assert(a.session==0 && a.padframes==0 && a.pregap==0 && a.postgap==0);
   }
  }
  for(unsigned count : {0U,100U,0xffffffffU}) {
   std::vector<uint8_t> bytes(METADATA_WORDS*4); auto w=swapped?swapendian_int32(count):count;
   memcpy(bytes.data(),&w,4); table t; assert(decode(bytes,t)); assert(t.numtrks==0);
  }
 }
}
'''.replace('@@TRACK@@',track).replace('@@BODY@@',body)
with tempfile.TemporaryDirectory(prefix='cdrom-legacy-metadata-') as directory:
    out=Path(directory)
    (out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('Legacy CD metadata: truncated lengths, invalid counts and both byte orders PASS')

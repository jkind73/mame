#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run the actual sector-read method with short/error streams and buffer guards."""
from pathlib import Path
import tempfile,subprocess
from saturn_vdp_wip_test import method
source=(Path(__file__).resolve().parent.parent/'src/lib/util/cdrom.cpp').read_text()
body=method(source.replace('cdrom_file::','saturn_vdp1_device::'),'read_partial_sector').replace('saturn_vdp1_device::','cdrom_file::')
fixture=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <system_error>
#include <tuple>
#include <vector>
#define EXTRA_VERBOSE 0
#define osd_printf_verbose(...)
namespace util {struct random_read {std::vector<uint8_t> bytes;size_t pos=0;bool bad_seek=false;std::error_condition seek(uint64_t p,int){pos=p;return bad_seek?std::make_error_condition(std::errc::io_error):std::error_condition{};}};}
std::pair<std::error_condition,size_t> read(util::random_read &f,void *dst,size_t size){size_t n=f.pos<f.bytes.size()?std::min(size,f.bytes.size()-f.pos):0;memcpy(dst,f.bytes.data()+std::min(f.pos,f.bytes.size()),n);return {{},n};}
struct chd_file {std::error_condition read_bytes(uint64_t,void *p,uint32_t n){memset(p,0x12,n);return {};}};
struct cdrom_file {
 static constexpr unsigned FRAME_SIZE=2448,CD_FLAG_GDROMLE=1,CD_TRACK_AUDIO=0;
 struct track {unsigned pgdatasize=0,logframeofs=0,pregap=0,trktype=0,datasize=2352,subsize=0;};
 struct {track tracks[1];unsigned flags=0;} cdtoc;
 struct {struct {uint64_t offset=0;bool swap=false;}track[1];}cdtrack_info;
 chd_file *chd=nullptr;util::random_read *fhandle[1];
 std::error_condition read_partial_sector(void*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,bool);
};
// METHOD
int main(){
 util::random_read file;for(unsigned i=0;i<24;i++)file.bytes.push_back(i);
 cdrom_file cd;cd.fhandle[0]=&file;cd.cdtrack_info.track[0].swap=true;
 std::array<uint8_t,8> out;out.fill(0xa5);
 assert(!cd.read_partial_sector(out.data()+2,0,0,0,16,4,false));
 assert(out[0]==0xa5 && out[1]==0xa5 && out[6]==0xa5 && out[7]==0xa5);
 assert(out[2]==17 && out[3]==16 && out[4]==19 && out[5]==18);
 out.fill(0xa5);assert(!cd.read_partial_sector(out.data()+2,0,0,0,16,3,false));
 assert(out[2]==17 && out[3]==16 && out[4]==18 && out[5]==0xa5);
 file.bytes.resize(18);out.fill(0xa5);
 assert(cd.read_partial_sector(out.data()+2,0,0,0,16,4,false)==std::errc::io_error);
 assert(out[2]==16 && out[3]==17 && out[4]==0xa5 && out[6]==0xa5);
 file.bad_seek=true;out.fill(0xa5);assert(cd.read_partial_sector(out.data()+2,0,0,0,16,4,false));
 for(auto v:out)assert(v==0xa5);
 cd.cdtoc.tracks[0].logframeofs=1;out.fill(0xa5);assert(!cd.read_partial_sector(out.data()+2,0,0,0,16,4,false));
 assert(out[2]==0 && out[5]==0 && out[6]==0xa5);
}
'''.replace('// METHOD',body)
with tempfile.TemporaryDirectory(prefix='cd-partial-read-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('CD_PARTIAL_READ_PASS short reads, seek failures, bounded byte swapping and pregap')

#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual NVRAM I/O methods: Saturn byte-store roundtrip and short writes."""
from pathlib import Path
import tempfile,subprocess
from saturn_vdp_wip_test import method
source=(Path(__file__).resolve().parent.parent/'src/devices/machine/nvram.cpp').read_text()
def extract(name):
 return method(source.replace('nvram_device::','saturn_vdp1_device::'),name).replace('saturn_vdp1_device::','nvram_device::')
fixture=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <system_error>
#include <vector>
namespace util {struct read_stream{std::vector<uint8_t> data;};struct write_stream{std::vector<uint8_t> data;size_t limit=32768;bool fail=false;};}
std::pair<std::error_condition,size_t> read(util::read_stream &f,void *p,size_t n){n=std::min(n,f.data.size());memcpy(p,f.data.data(),n);return {{},n};}
std::pair<std::error_condition,size_t> write(util::write_stream &f,const void *p,size_t n){n=std::min(n,f.limit);auto b=static_cast<const uint8_t *>(p);f.data.assign(b,b+n);return {f.fail?std::make_error_condition(std::errc::io_error):std::error_condition{},n};}
struct nvram_device{void *m_base;size_t m_length;void determine_final_base(){}bool nvram_read(util::read_stream&);bool nvram_write(util::write_stream&);};
// METHODS
int main(){
 std::array<uint8_t,32768> bytes;for(size_t i=0;i<bytes.size();i++)bytes[i]=(i*31+7)&255;
 auto expected=bytes;nvram_device d{bytes.data(),bytes.size()};util::write_stream output;
 assert(d.nvram_write(output));assert(output.data==std::vector<uint8_t>(expected.begin(),expected.end()));
 bytes.fill(0);util::read_stream input{output.data};assert(d.nvram_read(input));assert(bytes==expected);
 output.limit=32767;assert(!d.nvram_write(output));output.limit=32768;output.fail=true;assert(!d.nvram_write(output));
 input.data.resize(32767);assert(!d.nvram_read(input));
}
'''.replace('// METHODS','\n'.join(extract(n) for n in ('nvram_read','nvram_write')))
with tempfile.TemporaryDirectory(prefix='saturn-nvram-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(fixture)
 subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('SATURN_NVRAM_IO_PASS byte-preserving 32KiB roundtrip and short/error I/O')

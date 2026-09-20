#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute DMA source buffering, fixed-address refill and byte realignment.

Snapshots copy registered channel fields, not a MAME save-manager round trip.
--baseline substitutes the old word-transfer functions and must fail.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', action='store_true')
args = parser.parse_args()
path = 'src/mame/sega/saturn_scu.cpp'
source = (ROOT / path).read_text()
old = subprocess.check_output(['git','show','e7cff8b86e6e028453d01fcffc862bb47be3c2ec:'+path], cwd=ROOT, text=True) if args.baseline else source
header = (ROOT / 'src/mame/sega/saturn_scu.h').read_text()
start = header.index('  struct dma_channel_t {')
channel = header[start:header.index('  using dma_transfer_func', start)]
for level in range(3):
    for field in ('read_buffer','read_address','read_offset','read_buffer_valid'):
        assert f'save_item(NAME(m_dma[{level}].{field}));' in source

def extract(text, signature):
    start = text.index(signature); end = text.index('{', start)+1; depth = 1
    while depth:
        depth += (text[end]=='{') - (text[end]=='}'); end += 1
    return text[start:end]
functions = extract(source, 'uint16_t saturn_scu_device::dma_read_word(')
functions += '\n' + extract(source, 'uint8_t saturn_scu_device::dma_read_byte(')
for name in ('dma_transfer_direct_default','dma_transfer_direct_cbus_write'):
    functions += '\n' + extract(old, 'void saturn_scu_device::'+name+'(')
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <utility>
#include <vector>
using u8=uint8_t; using u16=uint16_t; using u32=uint32_t;
u8 byte_at(u32 address, unsigned generation) { return u8((address ^ (address>>9)) + generation*17); }
struct memory {
  // Source-byte realignment still writes aligned destination words here.
  void write_byte(u32, u8) { assert(false && "unexpected byte write in aligned DMA fixture"); }

  unsigned generation=0;
  std::vector<u32> reads;
  std::vector<std::pair<u32,u16>> writes;
  u32 read_dword(u32 address) {
    assert(!(address & 3)); reads.push_back(address); ++generation;
    u32 result=0;
    for(unsigned i=0;i<4;++i) result=(result<<8)|byte_at(address+i,generation);
    return result;
  }
  u16 read_word(u32 address) { ++generation; return (u16(byte_at(address,generation))<<8)|byte_at(address+1,generation); }
  void write_word(u32 address,u16 data) { writes.emplace_back(address,data); }
};
struct saturn_scu_device {
// CHANNEL
  memory mem; memory *m_hostspace=&mem;
  uint16_t dma_read_word(dma_channel_t &);
  uint8_t dma_read_byte(dma_channel_t &);
  void dma_transfer_direct_default(dma_channel_t &);
  void dma_transfer_direct_cbus_write(dma_channel_t &);
};
// FUNCTIONS
int main() {
  unsigned cases=0;
  for(unsigned level=0;level<3;++level)
    for(bool cbus : {false,true})
      for(unsigned increment : {0u,4u})
        for(unsigned offset=0;offset<4;++offset)
          for(unsigned count : {2u,4u,6u,32u})
            for(u32 base : {0x02000000u,0x07fffffcu})
              for(u32 dst_add : {0u,2u,128u}) {
                saturn_scu_device s{};
                auto &ch=s.m_dma[level]; ch.live_src=base+offset;
                ch.live_dst=0x05a10000; ch.live_size=count; ch.src_add=increment; ch.dst_add=dst_add;
                u32 read_base=base; unsigned pos=offset, generation=1;
                for(unsigned done=0;done<count;done+=2) {
                  // Resume from a saved half-consumed source buffer and memory endpoint.
                  saturn_scu_device restored{};
                  restored.m_dma[level]=ch; restored.mem=s.mem;
                  u16 expected=0;
                  for(unsigned byte=0;byte<2;++byte) {
                    if(pos==4) {pos=0; read_base=(read_base+increment)&0x07ffffff; ++generation;}
                    expected=(expected<<8)|byte_at(read_base+pos,generation); ++pos;
                  }
                  if(cbus) {s.dma_transfer_direct_cbus_write(ch); restored.dma_transfer_direct_cbus_write(restored.m_dma[level]);}
                  else {s.dma_transfer_direct_default(ch); restored.dma_transfer_direct_default(restored.m_dma[level]);}
                  assert(s.mem.reads.size()==generation);
                  assert(s.mem.writes.back()==std::make_pair(0x05a10000u+(done/2)*(cbus?2:dst_add),expected));
                  assert(ch.live_src==((read_base+pos)&0x07ffffff) && ch.live_count==done+2);
                  assert(restored.mem.reads==s.mem.reads && restored.mem.writes==s.mem.writes);
                  assert(restored.m_dma[level].read_buffer==ch.read_buffer);
                }
                ++cases;
              }
  assert(cases==1152);
  std::cout << cases << " buffered DMA source/word-transfer scenarios passed, including snapshot continuation\n";
}
'''
with tempfile.TemporaryDirectory(prefix='saturn-dma-source-') as temp:
    cpp=Path(temp)/'source.cpp'; exe=Path(temp)/'source'
    cpp.write_text(harness.replace('// CHANNEL',channel).replace('// FUNCTIONS',functions))
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Test actual DMA address/count register lambdas, including masked readback.

--baseline src/dst substitutes that register's pre-fix handler and must fail.
Calls extracted handlers, not the full MAME address-map dispatcher.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "eca12b2a22c8448d76d38eaf6d8076b69a4d6b4d"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", choices=("src", "dst"))
args = parser.parse_args()
path = "src/mame/sega/saturn_scu.cpp"
source = (ROOT / path).read_text()
old = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
       if args.baseline else source)
header = (ROOT / "src/mame/sega/saturn_scu.h").read_text()
start = header.index("  struct dma_channel_t {")
channel = header[start:header.index("  using dma_transfer_func", start)]


def body(text, signature):
    start = text.index("{", text.index(signature))
    end, depth = start + 1, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


functions = []
for name, address in (("src", "0x00, 0x03"), ("dst", "0x04, 0x07"), ("size", "0x08, 0x0b")):
    text = old if args.baseline == name else source
    start = text.index("  map(" + address + ")", text.index("void saturn_scu_device::dma_map("))
    reg = text[start:text.index("}));", start) + 4]
    functions.append(f"template<unsigned Level> u32 read_{name}(offs_t offset = 0) "
                     + body(reg, "[this](offs_t offset)"))
    functions.append(f"template<unsigned Level> void write_{name}(offs_t offset, u32 data, u32 mem_mask) "
                     + body(reg, "[this](offs_t offset, u32 data, u32 mem_mask)"))
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
using u32 = uint32_t;
using offs_t = unsigned;
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
struct saturn_scu_device {
// PRODUCTION_CHANNEL
// PRODUCTION_HANDLERS
};
u32 byte_mask(unsigned lanes) {
  u32 mask = 0;
  for (unsigned byte = 0; byte < 4; ++byte)
    if (lanes & (1u << byte)) mask |= 0xffu << (8*byte);
  return mask;
}
template<unsigned Level> unsigned check() {
  unsigned cases = 0;
  // Single-bit probes plus boundary, alias and mixed values (40 data patterns).
  std::vector<u32> values = {0, 0xffffffff, 0x07ffffff, 0x08000000,
                            0x06012345, 0x26012345, 0xaaaaaaaa, 0x55555555};
  for (unsigned bit = 0; bit < 32; ++bit) values.push_back(1u << bit);
  for (unsigned reg = 0; reg < 3; ++reg)
    for (u32 initial : {0u, 0x01234567u, 0x05555555u, 0x07ffffffu})
      for (u32 data : values)
        for (unsigned lanes = 0; lanes < 16; ++lanes) {
          saturn_scu_device s{};
          constexpr u32 sentinel_src = 0x013579bd, sentinel_dst = 0x02468acf, sentinel_size = 0x123;
          for (auto &ch : s.m_dma) {
            ch.src = sentinel_src; ch.dst = sentinel_dst; ch.size = sentinel_size;
          }
          u32 defined = reg == 2 ? (Level == 0 ? 0xfffff : 0xfff) : 0x07ffffff;
          u32 seed = initial & defined, mask = byte_mask(lanes);
          auto &ch = s.m_dma[Level];
          u32 expected = ((seed & ~mask) | (data & mask)) & defined;
          u32 actual;
          if (reg == 0) {
            ch.src = seed;
            s.template write_src<Level>(0, data, mask);
            actual = s.template read_src<Level>();
          } else if (reg == 1) {
            ch.dst = seed;
            s.template write_dst<Level>(0, data, mask);
            actual = s.template read_dst<Level>();
          } else {
            ch.size = seed;
            s.template write_size<Level>(0, data, mask);
            actual = s.template read_size<Level>();
          }
          assert(actual == expected);
          assert(ch.src == (reg == 0 ? expected : sentinel_src));
          assert(ch.dst == (reg == 1 ? expected : sentinel_dst));
          assert(ch.size == (reg == 2 ? expected : sentinel_size));
          for (unsigned other = 0; other < 3; ++other) if (other != Level) {
            assert(s.m_dma[other].src == sentinel_src && s.m_dma[other].dst == sentinel_dst);
            assert(s.m_dma[other].size == sentinel_size);
          }
          ++cases;
        }
  // A CPU cache alias must program the same physical address, including bit 0.
  saturn_scu_device s{};
  s.template write_src<Level>(0, 0x26012345, 0xffffffff);
  s.template write_dst<Level>(0, 0x270abcdf, 0xffffffff);
  assert(s.template read_src<Level>() == 0x06012345);
  assert(s.template read_dst<Level>() == 0x070abcdf);
  return cases;
}
int main() {
  unsigned cases = check<0>() + check<1>() + check<2>();
  assert(cases == 23040);
  std::cout << "15360 DMA address and 7680 direct count register writes/readbacks passed; cache aliases normalized\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-dma-regs-") as temp:
    cpp = Path(temp) / "regs.cpp"
    exe = Path(temp) / "regs"
    cpp.write_text(harness.replace("// PRODUCTION_CHANNEL", channel)
                   .replace("// PRODUCTION_HANDLERS", "\n".join(functions)))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

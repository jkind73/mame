#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Test actual DMA address/count register lambdas, including masked readback.

--baseline src/dst substitutes that register's pre-fix handler and must fail.
--mutation applies a named test-only control-register fault.
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
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--baseline", choices=("src", "dst"))
mode.add_argument("--mutation", choices=("go-lane", "enable", "factor", "dispatch"))
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
for name, address in (("add", "0x0c, 0x0f"), ("enable", "0x10, 0x13"), ("mode", "0x14, 0x17")):
    start = source.index("  map(" + address + ")", source.index("void saturn_scu_device::dma_map("))
    reg = source[start:source.index("}));", start) + 4]
    functions.append(f"template<unsigned Level> void write_{name}(offs_t offset, u32 data, u32 mem_mask) "
                     + body(reg, "[this](offs_t offset, u32 data, u32 mem_mask)"))
handlers = "\n".join(functions)
if args.mutation:
    mutations = {
        "go-lane": ("ACCESSING_BITS_0_7 && m_dma[Level].enable_mask", "m_dma[Level].enable_mask"),
        "enable": ("m_dma[Level].enable_mask == true &&", ""),
        "factor": ("&& m_dma[Level].start_factor == DMA_EVENT_TRIGGER", ""),
        "dispatch": ("if (m_dma[Level].indirect_mode == true)", "if (m_dma[Level].indirect_mode == false)"),
    }
    before, after = mutations[args.mutation]
    assert handlers.count(before) == 1, "production mutation target changed"
    handlers = handlers.replace(before, after)
events = "enum dma_event_id_t : uint8_t " + body(header, "enum dma_event_id_t") + ";"
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
using u32 = uint32_t;
using offs_t = unsigned;
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
constexpr bool BIT(u32 data, unsigned bit) { return (data >> bit) & 1; }
#define ACCESSING_BITS_0_7 (mem_mask & 0xff)
#define ACCESSING_BITS_8_15 (mem_mask & 0xff00)
#define ACCESSING_BITS_16_23 (mem_mask & 0xff0000)
#define ACCESSING_BITS_24_31 (mem_mask & 0xff000000)
#define LOG(...) ((void)0)
struct saturn_scu_device {
  unsigned direct_calls = 0, indirect_calls = 0, last_level = 99;
  void trigger_dma_direct(unsigned level) { ++direct_calls; last_level = level; }
  void trigger_dma_indirect(unsigned level) { ++indirect_calls; last_level = level; }
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
template<unsigned Level> void isolated(const saturn_scu_device &s) {
  for (unsigned other = 0; other < 3; ++other) {
    const auto &ch = s.m_dma[other];
    assert(ch.src == 0 && ch.dst == 0 && ch.size == 0);
    if (other != Level) {
      assert(!ch.enable_mask && !ch.indirect_mode && !ch.rup && !ch.wup);
      assert(ch.src_add == 0 && ch.dst_add == 0 && ch.start_factor == 0);
    }
  }
}
template<unsigned Level> unsigned check_controls() {
  unsigned cases = 0;
  for (unsigned lanes = 0; lanes < 16; ++lanes) {
    u32 mask = byte_mask(lanes);
    for (bool initial : {false, true})
      for (bool written : {false, true})
        for (bool go : {false, true})
          for (unsigned factor = 0; factor < 8; ++factor)
            for (bool indirect : {false, true}) {
              saturn_scu_device s{};
              auto &ch = s.m_dma[Level];
              ch.enable_mask = initial; ch.start_factor = factor; ch.indirect_mode = indirect;
              // Reserved bits set deliberately; only bits 8 and 0 matter.
              s.template write_enable<Level>(0, 0xfffffefe | (written ? 0x100 : 0) | go, mask);
              bool enabled = (lanes & 2) ? written : initial;
              bool start = (lanes & 1) && enabled && go && factor == 7;
              assert(ch.enable_mask == enabled && ch.start_factor == factor && ch.indirect_mode == indirect);
              assert(s.direct_calls == unsigned(start && !indirect));
              assert(s.indirect_calls == unsigned(start && indirect));
              assert(s.last_level == (start ? Level : 99));
              // The start endpoint only records calls; no transfer is running here.
              // A later enable-byte write must not replay the previous GO bit.
              s.template write_enable<Level>(0, 0x100, 0xff00);
              assert(ch.enable_mask && s.direct_calls + s.indirect_calls == unsigned(start));
              isolated<Level>(s);
              ++cases;
            }
    for (bool initial : {false, true})
      for (unsigned code = 0; code < 16; ++code) {
        saturn_scu_device s{};
        auto &ch = s.m_dma[Level];
        ch.src_add = initial ? 4 : 0; ch.dst_add = initial ? 2 : 0;
        unsigned ra = code >> 3, wa = code & 7;
        s.template write_add<Level>(0, 0xfffffef8 | (ra << 8) | wa, mask);
        constexpr unsigned increments[] = {0,2,4,8,16,32,64,128};
        assert(ch.src_add == ((lanes & 2) ? ra*4 : initial ? 4u : 0u));
        assert(ch.dst_add == ((lanes & 1) ? increments[wa] : initial ? 2u : 0u));
        assert(s.direct_calls + s.indirect_calls == 0);
        isolated<Level>(s); ++cases;
      }
    for (bool initial : {false, true})
      for (unsigned code = 0; code < 64; ++code) {
        saturn_scu_device s{};
        auto &ch = s.m_dma[Level];
        ch.indirect_mode = initial; ch.rup = initial; ch.wup = initial;
        ch.start_factor = initial ? 7 : 0;
        bool indirect = code & 1, rup = code & 2, wup = code & 4;
        unsigned factor = code >> 3;
        u32 data = (u32(indirect) << 24) | (u32(rup) << 16) | (u32(wup) << 8) | factor;
        s.template write_mode<Level>(0, data | 0xfefefef8, mask);
        assert(ch.indirect_mode == ((lanes & 8) ? indirect : initial));
        assert(ch.rup == ((lanes & 4) ? rup : initial));
        assert(ch.wup == ((lanes & 2) ? wup : initial));
        assert(ch.start_factor == ((lanes & 1) ? factor : initial ? 7u : 0u));
        assert(s.direct_calls + s.indirect_calls == 0);
        isolated<Level>(s); ++cases;
      }
  }
  return cases;
}
int main() {
  unsigned cases = check<0>() + check<1>() + check<2>();
  assert(cases == 23040);
  unsigned controls = check_controls<0>() + check_controls<1>() + check_controls<2>();
  assert(controls == 13824);
  std::cout << "15360 DMA address and 7680 direct count register writes/readbacks passed; cache aliases normalized; 13824 control-register scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-dma-regs-") as temp:
    cpp = Path(temp) / "regs.cpp"
    exe = Path(temp) / "regs"
    cpp.write_text(harness.replace("// PRODUCTION_CHANNEL", events + channel)
                   .replace("// PRODUCTION_HANDLERS", handlers))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

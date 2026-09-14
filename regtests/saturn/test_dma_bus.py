#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Check C-Bus mirrored address classification and direct DMA setup/word steps.

Uses production decoder/setup/transfer bodies with recording memory and timer.
--baseline uses the pre-fix classifier and must fail on upper C-Bus mirrors.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "2cc26488273905f3623ef0b1d1e0fcd2e4a1e020"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_scu.cpp"
source = (ROOT / path).read_text()
old = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
       if args.baseline else source)
header = (ROOT / "src/mame/sega/saturn_scu.h").read_text()
bus = header[header.index("  static constexpr uint16_t A_BUS ="):header.index("\nprotected:")]
channel_start = header.index("  struct dma_channel_t {")
channel = header[channel_start:header.index("  using dma_transfer_func", channel_start)]


def extract(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


functions = extract(old, "std::tuple<u16, int> saturn_scu_device::get_address_flags(")
for signature in ("inline void saturn_scu_device::update_dma_status(",
                  "void saturn_scu_device::trigger_dma_direct(",
                  "void saturn_scu_device::dma_transfer_direct_default(",
                  "void saturn_scu_device::dma_transfer_direct_cbus_write("):
    functions += "\n" + extract(source, signature)
harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <tuple>
#include <vector>
using u16 = uint16_t;
using u32 = uint32_t;
template <typename... T> void ignore_log(T&&...) {}
#define LOG(...) ignore_log(__VA_ARGS__)
#define LOGMASKED(...) ignore_log(__VA_ARGS__)
constexpr int LOG_DMA_STATE=1, LOG_DMA_MOVE=2, LOG_DMA_MODE=4;
struct attotime {
  int ticks, rate;
  static attotime from_ticks(int ticks, int rate) { return {ticks, rate}; }
};
struct timer {
  int arms = 0;
  void adjust(attotime value) { assert(value.ticks == 8 && value.rate == 100); ++arms; }
};
struct memory {
  std::vector<u32> reads;
  std::vector<std::pair<u32, u16>> writes;
  u16 read_word(u32 address) { reads.push_back(address); return 0xabcd; }
  void write_word(u32 address, u16 data) { writes.emplace_back(address, data); }
};
struct saturn_scu_device {
// PRODUCTION_BUS_FLAGS
// PRODUCTION_CHANNEL
  enum dma_state_t : u32 { DMA_STATE_IDLE=0, DMA_STATE_MOVE=0x10, DMA_STATE_WAIT=0x20 };
  enum { DMA_MODE_RESET=0, DMA_MODE_CBUS_WRITE=1, DMA_MODE_CD=2 };
  static constexpr u32 IST_DMAILL = 1 << 12;
  u32 m_dma_status = 0, m_ist = 0, m_abus_asr[2]{};
  int m_dma_clock_ref = 100, irq_checks = 0;
  timer tim;
  timer *m_dma_tick_timer = &tim;
  memory mem;
  memory *m_hostspace = &mem;
  saturn_scu_device() { for (auto &ch : m_dma) ch = {}; }
  void test_pending_irqs() { ++irq_checks; }
  std::tuple<u16, int> get_address_flags(u32, bool);
  void update_dma_status(int, dma_state_t);
  void trigger_dma_direct(uint8_t);
  void dma_transfer_direct_default(dma_channel_t &);
  void dma_transfer_direct_cbus_write(dma_channel_t &);
};
// PRODUCTION_FUNCTIONS
int main() {
  unsigned classifications = 0, transfers = 0;
  for (unsigned mirror = 0; mirror < 32; ++mirror)
    for (u32 offset : {0u, 1u, 0x7ffffu, 0x80000u, 0xffffeu, 0xfffffu})
      for (u32 alias : {0u, 0x20000000u})
        for (bool write : {false, true}) {
          saturn_scu_device s;
          auto [flags, penalty] = s.get_address_flags(0x06000000 + (mirror << 20) + offset + alias, write);
          assert(flags == s.C_BUS && penalty == 0);
          ++classifications;
        }
  // All levels and mirrors must accept an A-Bus -> C-Bus transfer, and use
  // fixed word-step destinations regardless of the programmed write add.
  for (int level = 0; level < 3; ++level)
    for (unsigned mirror = 0; mirror < 32; ++mirror)
      for (u32 alias : {0u, 0x20000000u})
        for (u32 offset : {0u, 4u, 0x7ffcu, 0xffff8u})
          for (u32 add : {0u, 2u, 128u}) {
            u32 ram = 0x06000000 + (mirror << 20) + offset + alias;
            saturn_scu_device s;
            auto &ch = s.m_dma[level];
            ch.src = 0x02000000; ch.dst = ram;
            ch.size = 4; ch.src_add = 4; ch.dst_add = add;
            s.trigger_dma_direct(level);
            assert(s.m_ist == 0 && s.tim.arms == 1);
            assert(s.m_dma_status == (0x20u << (level * 4)));
            assert(ch.mode == s.DMA_MODE_CBUS_WRITE);
            assert(ch.live_src == ch.src && ch.live_dst == ram);
            assert(ch.live_size == 4 && ch.live_count == 0);
            assert(ch.transfer_penalty == 3 && !ch.bbus_sound_access);
            s.dma_transfer_direct_cbus_write(ch);
            s.dma_transfer_direct_cbus_write(ch);
            assert(ch.live_dst == ram + 4 && ch.live_count == 4);
            assert(s.mem.writes[0] == std::make_pair(ram & 0x07fffffe, u16(0xabcd)));
            assert(s.mem.writes[1].first == ((ram + 2) & 0x07fffffe));
            // Mirrored RAM is also a valid source for B-Bus destinations.
            saturn_scu_device read;
            auto &rc = read.m_dma[level];
            rc.src = ram; rc.dst = 0x05e00000; rc.size = 4;
            rc.src_add = 4; rc.dst_add = 2;
            read.trigger_dma_direct(level);
            assert(read.m_ist == 0 && rc.mode == read.DMA_MODE_RESET);
            read.dma_transfer_direct_default(rc);
            read.dma_transfer_direct_default(rc);
            assert(read.mem.reads[0] == (ram & 0x07fffffe));
            assert(read.mem.reads[1] == ((ram + 2) & 0x07fffffe));
            // Different mirrors still share one bus: direct C->C stays illegal.
            saturn_scu_device same;
            same.m_dma[level].src = 0x06000000;
            same.m_dma[level].dst = ram;
            same.m_dma[level].size = 4;
            same.trigger_dma_direct(level);
            assert(same.m_ist == same.IST_DMAILL && same.tim.arms == 0);
            ++transfers;
          }
  // Preserve neighboring bus classification and A-Bus wait-field handling.
  saturn_scu_device s;
  s.m_abus_asr[0] = (15u << 20) | (7u << 4);
  assert(s.get_address_flags(0x02000000, false) == std::make_tuple(s.A_BUS_CS0, 18));
  assert(s.get_address_flags(0x04000000, false) == std::make_tuple(s.A_BUS_CS1, 10));
  assert(std::get<0>(s.get_address_flags(0x05ffffff, false)) == s.B_BUS_SCU);
  assert(std::get<0>(s.get_address_flags(0x08000000, false)) == 0);
  assert(std::get<0>(s.get_address_flags(0x00200000, false)) == 0);
  std::cout << classifications << " C-Bus classifications and " << transfers
            << " mirrored DMA scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-dma-bus-") as temp:
    cpp = Path(temp) / "dma.cpp"
    exe = Path(temp) / "dma"
    cpp.write_text(harness.replace("// PRODUCTION_BUS_FLAGS", bus)
                   .replace("// PRODUCTION_CHANNEL", channel)
                   .replace("// PRODUCTION_FUNCTIONS", functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

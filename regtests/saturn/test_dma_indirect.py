#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Run production SCU DMA ticks from indirect start through completion.

Records memory/timer/IRQ endpoints, not CPU or bus timing. --baseline substitutes
pre-fix DMA ticks and must fail zero-count decoding; --baseline-wide isolates
the level 1/2 count-width regression. --arbitration-baseline uses pre-preemption
fix ticks and must fail the two-channel priority test.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "e718c19335be7944e183b3746966a82a518eb959"
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--baseline", action="store_true")
mode.add_argument("--baseline-wide", action="store_true")
mode.add_argument("--arbitration-baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_scu.cpp"
source = (ROOT / path).read_text()
baseline_revision = "317dc6b785e4d675db89485914e0f2aea407da69" if args.arbitration_baseline else BASE
old = (subprocess.check_output(["git", "show", baseline_revision + ":" + path], cwd=ROOT, text=True)
       if args.baseline or args.baseline_wide or args.arbitration_baseline else source)
header = (ROOT / "src/mame/sega/saturn_scu.h").read_text()


def extract(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


bus = header[header.index("  static constexpr uint16_t A_BUS ="):header.index("\nprotected:")]
channel_start = header.index("  struct dma_channel_t {")
channel = header[channel_start:header.index("  using dma_transfer_func", channel_start)]
enums = "\n".join(extract(header, "enum " + name) + ";" for name in
                  ("dma_status_t", "dma_state_t", "dma_mode_t"))
functions = extract(old, "TIMER_CALLBACK_MEMBER(saturn_scu_device::dma_tick_cb)")
for signature in ("std::tuple<u16, int> saturn_scu_device::get_address_flags(",
                  "inline void saturn_scu_device::update_dma_status(",
                  "std::tuple<int, int> saturn_scu_device::check_dma_level_round_robin()",
                  "void saturn_scu_device::dma_hog_bus(",
                  "void saturn_scu_device::trigger_dma_direct(",
                  "void saturn_scu_device::trigger_dma_indirect(",
                  "void saturn_scu_device::dma_transfer_direct_default(",
                  "void saturn_scu_device::dma_transfer_direct_cbus_write(",
                  "void saturn_scu_device::dma_transfer_direct_cd(",
                  "void saturn_scu_device::dma_transfer_direct_cd_cbus_write("):
    functions += "\n" + extract(source, signature)
start = source.index("const saturn_scu_device::dma_transfer_func")
functions += "\n" + source[start:source.index(";", start) + 1]
harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <tuple>
#include <unordered_map>
#include <vector>
using u8 = uint8_t;
using u16 = uint16_t;
using u32 = uint32_t;
constexpr bool BIT(u32 value, unsigned bit) { return (value >> bit) & 1; }
template <typename... T> void ignore_log(T&&...) {}
#define LOG(...) ignore_log(__VA_ARGS__)
#define LOGMASKED(...) ignore_log(__VA_ARGS__)
#define TIMER_CALLBACK_MEMBER(name) void name()
constexpr int LOG_DMA_STATE=1, LOG_DMA_MOVE=2, LOG_DMA_MODE=4, LOG_DMA_END=8, LOG_DMA_INDIRECT=16;
struct attotime {
  int ticks, rate;
  static const attotime never;
  static attotime from_ticks(int ticks, int rate) { assert(ticks > 0); return {ticks, rate}; }
};
const attotime attotime::never{-1, 0};
struct timer {
  bool stopped = true;
  void adjust(attotime value) { stopped = value.ticks == -1; }
};
struct memory {
  std::unordered_map<u32,u32> descriptors;
  std::vector<u32> descriptor_reads;
  u32 expected_src = 0, expected_dst = 0;
  unsigned words = 0;
  u16 last_read = 0;
  u32 read_dword(u32 address) {
    descriptor_reads.push_back(address);
    auto it = descriptors.find(address);
    assert(it != descriptors.end()); // catches reading beyond final descriptor
    return it->second;
  }
  u16 read_word(u32 address) {
    assert(address == (expected_src & 0x07fffffe));
    expected_src += 2;
    last_read = u16((address >> 1) ^ 0x5a5a);
    return last_read;
  }
  void write_word(u32 address, u16 data) {
    assert(address == (expected_dst & 0x07fffffe) && data == last_read);
    expected_dst += 2; ++words;
  }
  void write_dword(u32, u32) { assert(false); } // these scenarios do not use CD mode
};
struct callback {
  unsigned calls = 0;
  int last = -1;
  void operator()(int value) { ++calls; last = value; }
};
struct saturn_scu_device {
// PRODUCTION_TYPES
  using dma_transfer_func = void (saturn_scu_device::*)(dma_channel_t &);
  static const dma_transfer_func dma_transfer_table[4];
  static constexpr u32 IST_DMAILL = 1 << 12;
  u32 m_dma_status = 0, m_ist = 0, m_abus_asr[2]{};
  int m_dma_clock_ref = 100;
  unsigned irq_checks = 0;
  timer tim;
  timer *m_dma_tick_timer = &tim;
  memory mem;
  memory *m_hostspace = &mem;
  callback m_main_dtack_cb, m_sound_dtack_cb, m_main_steal_cb, m_sound_steal_cb;
  saturn_scu_device() { for (auto &ch : m_dma) ch = {}; }
  void test_pending_irqs() { ++irq_checks; }
  std::tuple<u16, int> get_address_flags(u32, bool);
  std::tuple<int, int> check_dma_level_round_robin();
  void update_dma_status(int, dma_state_t);
  void trigger_dma_direct(uint8_t);
  void trigger_dma_indirect(uint8_t);
  void dma_transfer_direct_default(dma_channel_t &);
  void dma_transfer_direct_cbus_write(dma_channel_t &);
  void dma_transfer_direct_cd(dma_channel_t &);
  void dma_transfer_direct_cd_cbus_write(dma_channel_t &);
  void dma_tick_cb();
  void dma_hog_bus(uint8_t);
};
// GCC 12 diagnoses an anonymous temporary in UBSan-instrumented pointer-to-
// member dispatch. Keep sanitizers enabled; suppress this warning only around
// the extracted production definitions, not the test assertions/setup.
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmaybe-uninitialized"
#endif
// PRODUCTION_FUNCTIONS
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic pop
#endif
int main() {
  unsigned scenarios = 0;
  for (int level = 0; level < 3; ++level)
    for (bool update : {false, true})
      for (u32 raw : {0u, 4u, 0x1004u, 0x23000u, 0x40000u, 0x80000u, 0xffffeu,
                      0x100000u, 0xfff00004u}) {
        if (wide_baseline && (level == 0 || raw != 0x80000)) continue;
        saturn_scu_device s;
        auto &ch = s.m_dma[level];
        const u32 table = 0x07000800; // upper RAM mirror; two descriptors fit 32-byte boundary
        u32 count = raw & 0xfffff;
        if (!count) count = 0x100000;
        const u32 first_src = 0x02000000, first_dst = 0x07000000;
        const u32 second_src = 0x07000000, second_dst = 0x05a00000;
        s.mem.descriptors = {{table,raw}, {table+4,first_dst}, {table+8,first_src},
                             {table+12,4}, {table+16,second_dst}, {table+20,second_src|0x80000000}};
        ch.dst = table; ch.src = 0x123456; ch.size = 0x456; // direct registers ignored
        ch.src_add = 4; ch.dst_add = 2; ch.indirect_mode = true; ch.wup = update;
        s.trigger_dma_indirect(level);
        assert(s.m_dma_status == (0x20u << (4*level)));
        s.dma_tick_cb(); // WAIT -> MOVE
        assert(s.m_dma_status == (0x10u << (4*level)));
        s.dma_tick_cb(); // fetch descriptor 1
        assert(ch.live_size == count && ch.live_count == 0);
        assert(ch.mode == (s.DMA_MODE_INDIRECT | s.DMA_MODE_CBUS_WRITE));
        assert(ch.live_src == first_src && ch.live_dst == first_dst);
        assert(!ch.indirect_end_flag && ch.index == table + 12);
        s.mem.expected_src = first_src; s.mem.expected_dst = first_dst;
        for (u32 transferred = 0; transferred < count; transferred += 2) {
          assert(!ch.indirect_fetch_phase && !ch.done && s.m_ist == 0);
          s.dma_tick_cb();
          assert(ch.live_count == transferred + 2);
        }
        assert(s.mem.words == count/2 && ch.indirect_fetch_phase && !ch.done);
        assert(s.m_ist == 0 && ch.dst == (update ? table + 12 : table));
        s.dma_tick_cb(); // fetch descriptor 2, final flag in source bit 31
        assert(ch.live_size == 4 && ch.live_count == 0 && ch.indirect_end_flag);
        assert(ch.live_src == second_src && ch.live_dst == second_dst);
        assert(ch.mode == s.DMA_MODE_INDIRECT && ch.bbus_sound_access);
        assert(ch.index == table + 24);
        s.mem.expected_src = second_src; s.mem.expected_dst = second_dst;
        s.dma_tick_cb();
        assert(!ch.done && s.m_ist == 0);
        s.dma_tick_cb();
        assert(ch.done && s.m_ist == 0 && !s.tim.stopped);
        assert(ch.dst == (update ? table + 24 : table));
        s.dma_tick_cb(); // completion interrupt and return to IDLE
        assert(s.m_ist == (1u << (11-level)) && s.irq_checks == 1);
        assert(s.m_dma_status == 0 && s.tim.stopped);
        assert(s.mem.words == count/2 + 2);
        assert(s.m_main_steal_cb.calls == s.mem.words && s.m_sound_steal_cb.calls == 2);
        assert(s.m_main_dtack_cb.last == 0 && s.m_sound_dtack_cb.last == 0);
        assert(s.mem.descriptor_reads == std::vector<u32>({table, table+4, table+8, table+12, table+16, table+20}));
        assert(ch.src == 0x123456 && ch.size == 0x456); // no direct register clobber
        ++scenarios;
      }
  unsigned arbitration_scenarios = 0;
  // Use supported channel pairs only. ST-210 item 35 prohibits starting
  // channel 2 while channel 1 runs; item 20 only guarantees two channels.
  for (int higher : {1, 2})
    for (bool preempt : {false, true})
      for (bool first_indirect : {false, true})
        for (bool second_indirect : {false, true})
          for (bool first_sound : {false, true})
            for (bool second_sound : {false, true}) {
              if (arbitration_baseline && !preempt) continue;
              saturn_scu_device s;
              const int first = preempt ? 0 : higher;
              const int second = preempt ? higher : 0;
              bool indirect[3]{}, sound[3]{};
              indirect[first] = first_indirect; indirect[second] = second_indirect;
              sound[first] = first_sound; sound[second] = second_sound;
              u32 size[3]{};
              size[first] = 8; size[second] = 4;
              auto setup = [&](int level) {
                auto &ch = s.m_dma[level];
                u32 src = 0x02000000 + level * 0x100;
                u32 dst = (sound[level] ? 0x05a10000 : 0x07010000) + level * 0x1000;
                ch.src_add = 4; ch.dst_add = 2;
                ch.indirect_mode = indirect[level];
                if (indirect[level]) {
                  ch.dst = 0x07000800 + level * 0x20;
                  s.mem.descriptors[ch.dst] = size[level];
                  s.mem.descriptors[ch.dst+4] = dst;
                  s.mem.descriptors[ch.dst+8] = src | 0x80000000;
                  s.trigger_dma_indirect(level);
                } else {
                  ch.src = src; ch.dst = dst; ch.size = size[level];
                  s.trigger_dma_direct(level);
                }
              };
              auto step = [&](int level) {
                assert(std::get<0>(s.check_dma_level_round_robin()) == level);
                s.mem.expected_src = s.m_dma[level].live_src;
                s.mem.expected_dst = s.m_dma[level].live_dst;
                s.dma_tick_cb();
              };
              auto ownership = [&](int level) {
                assert(s.m_main_dtack_cb.last == !indirect[level]);
                assert(s.m_sound_dtack_cb.last == (!indirect[level] && sound[level]));
              };
              setup(first);
              s.dma_tick_cb(); // start the first waiting channel
              if (indirect[first]) step(first); // fetch its single descriptor
              step(first); // first word
              assert(s.m_dma[first].live_count == 2);
              ownership(first);
              setup(second);
              step(first); // preserve current tick granularity, then arbitrate
              assert(s.m_dma[first].live_count == 4);
              const int winner = preempt ? second : first;
              const int loser = preempt ? first : second;
              auto [moving, waiting] = s.check_dma_level_round_robin();
              assert(moving == winner && waiting == loser);
              assert((s.m_dma_status & (0x30u << (first*4))) == ((preempt ? 0x20u : 0x10u) << (first*4)));
              if (preempt) assert(s.m_dma_status & (1u << (16+first)));
              ownership(winner);
              u32 paused_count = s.m_dma[loser].live_count;
              u32 paused_src = s.m_dma[loser].live_src;
              u32 paused_dst = s.m_dma[loser].live_dst;
              for (int ticks = 0; !s.m_dma[winner].done; ++ticks) {
                assert(ticks < 8);
                step(winner);
                assert(s.m_dma[loser].live_count == paused_count);
                assert(s.m_dma[loser].live_src == paused_src && s.m_dma[loser].live_dst == paused_dst);
              }
              assert(s.m_ist == 0); // no completion before final retirement tick
              step(winner);
              assert(s.m_ist == (1u << (11-winner)) && s.irq_checks == 1);
              assert(std::get<0>(s.check_dma_level_round_robin()) == loser);
              assert((s.m_dma_status & (7u << 16)) == 0);
              assert(!s.tim.stopped);
              ownership(loser); // restore direct halt or indirect cycle stealing
              for (int ticks = 0; !s.m_dma[loser].done; ++ticks) {
                assert(ticks < 8);
                step(loser);
              }
              step(loser);
              assert(s.m_ist == ((1u << (11-winner)) | (1u << (11-loser))));
              assert(s.irq_checks == 2 && s.m_dma_status == 0 && s.tim.stopped);
              assert(s.mem.words == 6 && s.m_main_steal_cb.calls == 6);
              assert(s.m_main_dtack_cb.last == 0 && s.m_sound_dtack_cb.last == 0);
              assert(s.mem.descriptor_reads.size() == unsigned(3 * (first_indirect + second_indirect)));
              for (int level : {first, second}) {
                assert(s.m_dma[level].live_src == 0x02000000u + level*0x100u + size[level]);
                assert(s.m_dma[level].live_dst == (sound[level] ? 0x05a10000u : 0x07010000u) + level*0x1000u + size[level]);
              }
              ++arbitration_scenarios;
            }
  std::cout << scenarios << " indirect DMA chains passed through completion; "
            << arbitration_scenarios << " two-channel arbitration scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-dma-indirect-") as temp:
    cpp = Path(temp) / "dma.cpp"
    exe = Path(temp) / "dma"
    cpp.write_text(harness.replace("// PRODUCTION_TYPES", bus + enums + channel)
                   .replace("// PRODUCTION_FUNCTIONS", "constexpr bool wide_baseline = "
                            + str(args.baseline_wide).lower() + ";\nconstexpr bool arbitration_baseline = "
                            + str(args.arbitration_baseline).lower() + ";\n" + functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

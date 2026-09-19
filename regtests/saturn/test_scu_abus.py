#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Check SCU A-Bus register reset, masked writes and existing static wait decode.

Uses complete production reset/handlers/classifier with recording timers.
--baseline-reset and --baseline-write independently substitute the pre-fix body.
No physical refresh cycles or CPU/scheduler behavior are modeled here.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "0d7e9fe416ef866951290d2816211eff0ffc32c4"
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--baseline-reset", action="store_true")
mode.add_argument("--baseline-write", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_scu.cpp"
source = (ROOT / path).read_text()
old = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
       if args.baseline_reset or args.baseline_write else source)
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
start = header.index("  struct dma_channel_t {")
channel = header[start:header.index("  using dma_transfer_func", start)]
enums = "\n".join(extract(header, "enum " + name) + ";" for name in
                  ("dma_mode_t", "dma_event_id_t"))
functions = extract(old if args.baseline_reset else source, "void saturn_scu_device::device_reset()")
functions += "\n" + extract(old if args.baseline_write else source, "void saturn_scu_device::abus_refresh_w(")
for signature in ("void saturn_scu_device::abus_set_w(",
                  "std::tuple<u16, int> saturn_scu_device::get_address_flags("):
    functions += "\n" + extract(source, signature)
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <tuple>
using u16 = uint16_t;
using u32 = uint32_t;
using offs_t = unsigned;
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
struct attotime { static constexpr int never = -1; };
struct timer {
  bool stopped = false;
  void adjust(int value) { assert(value == attotime::never); stopped = true; }
};
struct saturn_scu_device {
  void m_main_dtack_cb(int state) { assert(state == 0); }
  void m_sound_dtack_cb(int state) { assert(state == 0); }
// PRODUCTION_TYPES
  u32 m_ism = 0, m_ist = 0xffffffff, m_abus_pending_ack = 0xffff;
  u32 m_abus_asr[2]{}, m_abus_aref = 0;
  // Stand-in for the saturn_bus arbiter (production API in
  // src/mame/sega/saturn_bus.h): always present, recording ASR propagation.
  struct bus_stub {
    unsigned asr_calls = 0;
    void set_asr_regs(uint32_t, uint32_t, uint32_t) { ++asr_calls; }
  };
  struct bus_finder {
    bus_stub stub;
    bool found() const { return true; }
    bus_stub *operator->() { return &stub; }
    const bus_stub *operator->() const { return &stub; }
  };
  bus_finder m_bus;
  u32 m_dma_status = 0xffffffff, m_current_irq_level = 15, m_current_vector = 0x40;
  bool m_tenb = true, m_t1md = true;
  u16 m_timer0_counter = 123, m_t0c = 456, m_t1s = 123, m_t1md_reg = 0x101;
  timer dma_timer, timer1;
  timer *m_dma_tick_timer = &dma_timer, *m_timer1 = &timer1;
  void device_reset();
  void abus_set_w(offs_t, uint32_t, uint32_t);
  void abus_refresh_w(uint32_t, uint32_t);
  std::tuple<u16, int> get_address_flags(u32, bool);
};
// PRODUCTION_FUNCTIONS
u32 byte_mask(unsigned lanes) {
  u32 mask = 0;
  for (unsigned byte = 0; byte < 4; ++byte)
    if (lanes & (1u << byte)) mask |= 0xffu << (8*byte);
  return mask;
}
int main() {
  unsigned resets = 0, refresh_writes = 0, set_writes = 0, classifications = 0;
  for (u32 initial = 0; initial < 32; ++initial) {
    saturn_scu_device s;
    s.m_abus_aref = 0xffffffe0 | initial;
    s.m_abus_asr[0] = 0xffffffff; s.m_abus_asr[1] = 0x12345678;
    for (auto &ch : s.m_dma) {
      ch.pending_trigger = true; ch.enable_mask = true; ch.done = true;
    }
    s.device_reset(); // actual whole callback, not a copied AREF assignment
    assert(s.m_abus_aref == 0x10); // ST-210 item 33 overrides ST-097 figure 3.30
    assert(s.m_abus_asr[0] == 0 && s.m_abus_asr[1] == 0);
    assert(s.m_ist == 0 && s.m_ism == 0xbfff && s.m_abus_pending_ack == 0);
    assert(s.m_dma_status == 0 && s.dma_timer.stopped && s.timer1.stopped);
    for (auto &ch : s.m_dma) assert(!ch.pending_trigger && !ch.enable_mask && !ch.done);
    ++resets;
    for (unsigned lanes = 0; lanes < 16; ++lanes)
      for (u32 low = 0; low < 32; ++low)
        for (u32 reserved : {0u, 0xffffffe0u}) {
          u32 mask = byte_mask(lanes), data = low | reserved;
          s.m_abus_aref = initial;
          s.abus_refresh_w(data, mask);
          u32 expected = ((initial & ~mask) | (data & mask)) & 0x1f;
          assert(s.m_abus_aref == expected);
          ++refresh_writes;
        }
  }
  saturn_scu_device s;
  s.device_reset();
  for (unsigned index = 0; index < 2; ++index)
    for (unsigned lanes = 0; lanes < 16; ++lanes)
      for (u32 initial : {0u, 0x12345678u, 0x7fff7fffu})
        for (u32 data : {0u, 0x01234567u, 0xffffffffu}) {
          u32 mask = byte_mask(lanes);
          s.m_abus_asr[index] = initial;
          s.m_abus_asr[index^1] = 0x3456789a;
          s.abus_set_w(index, data, mask);
          assert(s.m_abus_asr[index] == (((initial & ~mask) | (data & mask)) & 0x7fff7fff));
          assert(s.m_abus_asr[index^1] == 0x3456789a);
          ++set_writes;
        }
  // Regression of the existing AnNW+3 approximation, not measured bus cycles.
  for (u32 a0 = 0; a0 < 16; ++a0)
    for (u32 a1 = 0; a1 < 16; ++a1)
      for (u32 a3 = 0; a3 < 16; ++a3) {
        s.abus_set_w(0, (a0 << 20) | (a1 << 4), 0xffffffff);
        s.abus_set_w(1, a3 << 4, 0xffffffff);
        for (bool write : {false, true}) {
          for (auto [address, flags, wait] : {
                 std::make_tuple(0x02000000u, s.A_BUS_CS0, a0),
                 std::make_tuple(0x04000000u, s.A_BUS_CS1, a1),
                 std::make_tuple(0x05800000u, s.A_BUS_CS2, a3)}) {
            auto [actual_flags, penalty] = s.get_address_flags(address, write);
            assert(actual_flags == flags && penalty == int(wait+3));
            ++classifications;
          }
        }
      }
  assert(resets == 32 && refresh_writes == 32768 && set_writes == 288 && classifications == 24576);
  std::cout << resets << " A-Bus resets, " << refresh_writes << " refresh writes, "
            << set_writes << " set-register writes and " << classifications << " static wait decodes passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-scu-abus-") as temp:
    cpp = Path(temp) / "abus.cpp"
    exe = Path(temp) / "abus"
    cpp.write_text(harness.replace("// PRODUCTION_TYPES", bus + enums + channel)
                   .replace("// PRODUCTION_FUNCTIONS", functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

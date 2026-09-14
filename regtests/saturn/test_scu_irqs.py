#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Exercise SCU interrupt arbitration, IMS/IST and A-Bus acknowledgement.

Extracts production functions with a recording CPU interrupt-line endpoint.
--baseline uses the pre-fix arbiter and must fail external-mask polarity.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "024d7e28b1c4a67e6f667f89e2999eaaf2e519d8"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
path = "src/mame/sega/saturn_scu.cpp"
source = (ROOT / path).read_text()
old = (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
       if args.baseline else source)
header = (ROOT / "src/mame/sega/saturn_scu.h").read_text()
mask = next(line for line in header.splitlines() if "constexpr" in line and "ISM_WRITE_MASK" in line)


def extract(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


functions = extract(old, "void saturn_scu_device::test_pending_irqs()")
for signature in ("uint32_t saturn_scu_device::irq_mask_r()",
                  "uint32_t saturn_scu_device::irq_status_r()",
                  "void saturn_scu_device::irq_mask_w(",
                  "void saturn_scu_device::irq_status_w(",
                  "void saturn_scu_device::abus_external_interrupt(",
                  "void saturn_scu_device::abus_irqack_w(",
                  "IRQ_CALLBACK_MEMBER(saturn_scu_device::irq_ack_cb)"):
    functions += "\n" + extract(source, signature)
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <utility>
#include <vector>
using u32 = uint32_t;
using offs_t = unsigned;
constexpr int ASSERT_LINE = 1, CLEAR_LINE = 0;
constexpr bool BIT(u32 value, unsigned bit) { return (value >> bit) & 1; }
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define IRQ_CALLBACK_MEMBER(name) int name(int irqline)
struct cpu {
  std::vector<std::pair<int,int>> lines;
  void set_input_line(int level, int state) {
    assert(level >= 1 && level <= 15);
    lines.emplace_back(level, state);
  }
};
struct saturn_scu_device {
// PRODUCTION_MASK
  u32 m_ism = 0xbfff, m_ist = 0, m_abus_pending_ack = 0;
  int m_current_irq_level = 0, m_current_vector = 0;
  cpu host;
  cpu *m_hostcpu = &host;
  void test_pending_irqs();
  uint32_t irq_mask_r();
  uint32_t irq_status_r();
  void irq_mask_w(offs_t, uint32_t, uint32_t);
  void irq_status_w(offs_t, uint32_t, uint32_t);
  void abus_external_interrupt(int, bool);
  void abus_irqack_w(offs_t, uint32_t, uint32_t);
  int irq_ack_cb(int);
};
// PRODUCTION_FUNCTIONS
u32 byte_mask(unsigned lanes) {
  u32 mask = 0;
  for (unsigned byte = 0; byte < 4; ++byte)
    if (lanes & (1u << byte)) mask |= 0xffu << (8*byte);
  return mask;
}
int main() {
  // ST-097 table 2.1: internal levels and three external level groups.
  constexpr int levels[] = {15,14,13,12,11,10,9,8,8,6,6,5,3,2};
  unsigned arbitration = 0, handshakes = 0, writes = 0;
  for (int internal = -1; internal < 14; ++internal)
    for (int external = 0; external < 16; ++external)
      for (bool internal_masked : {false, true})
        for (bool external_masked : {false, true})
          for (bool acknowledged : {false, true}) {
            saturn_scu_device s;
            u32 external_bit = 1u << (16+external);
            s.m_ist = external_bit | (internal < 0 ? 0 : 1u << internal);
            if (internal >= 0 && !internal_masked) s.m_ism &= ~(1u << internal);
            if (!external_masked) s.m_ism &= ~0x8000u;
            s.m_abus_pending_ack = acknowledged ? 1u << external : 0;
            u32 original = s.m_ist, original_ack = s.m_abus_pending_ack;
            int il = internal >= 0 && !internal_masked ? levels[internal] : 0;
            int el = external_masked || acknowledged ? 0 : external < 4 ? 7 : external < 8 ? 4 : 1;
            int level = il >= el ? il : el;
            int source = il >= el ? internal : external+16;
            s.test_pending_irqs();
            assert(s.m_current_irq_level == level);
            if (!level) {
              assert(s.host.lines.empty() && s.m_ist == original && s.m_abus_pending_ack == original_ack);
            } else {
              int vector = 0x40 + source;
              assert(s.m_current_vector == vector);
              assert(s.host.lines.size() == 1 && s.host.lines.back() == std::make_pair(level, ASSERT_LINE));
              assert(s.m_ist == (original & ~(1u << source)));
              assert(s.m_abus_pending_ack == (original_ack | (source >= 16 ? 1u << external : 0)));
              u32 remaining = s.m_ist;
              assert(s.irq_ack_cb(level) == vector);
              assert(s.m_current_irq_level == 0 && s.irq_mask_r() == 0xbfff);
              assert(s.irq_status_r() == remaining); // vector fetch leaves other requests pending
              assert(s.host.lines.size() == 2 && s.host.lines.back() == std::make_pair(level, CLEAR_LINE));
              s.test_pending_irqs(); // acknowledgement restored ALL masks, including IMS15
              assert(s.m_current_irq_level == 0 && s.host.lines.size() == 2);
            }
            ++arbitration;
          }
  for (int external = 0; external < 16; ++external) {
    saturn_scu_device s;
    u32 bit = 1u << (16+external);
    int level = external < 4 ? 7 : external < 8 ? 4 : 1;
    s.abus_external_interrupt(external, true);
    assert(s.host.lines.empty() && s.m_ist == bit); // default mask must block
    s.irq_mask_w(0, 0, 0x8000); // unmask only external sources
    assert(s.m_current_vector == 0x50+external && s.m_ist == 0);
    s.abus_external_interrupt(external, true); // another request during delivery
    s.m_ist |= 1; // queue a higher-priority internal request
    s.irq_mask_w(0, 0, 1); // cannot replace an already issued vector
    assert(s.host.lines.size() == 1 && s.m_current_irq_level == level);
    assert(s.irq_ack_cb(level) == 0x50+external);
    assert(s.m_ist == (bit | 1));
    s.irq_mask_w(0, 0, 0x8000);
    assert(s.m_current_irq_level == 0); // external pending-ack gate still holds
    s.abus_irqack_w(0, 1, 0xff00); // wrong byte
    s.abus_irqack_w(0, 0, 0xff); // zero doesn't release
    assert(s.m_current_irq_level == 0 && s.m_abus_pending_ack == (1u << external));
    s.abus_irqack_w(0, 1, 0xff);
    assert(s.m_current_irq_level == level && s.m_current_vector == 0x50+external);
    assert(s.m_ist == 1);
    assert(s.irq_ack_cb(level) == 0x50+external);
    s.irq_mask_w(0, 0, 1); // finally release the queued VBlank-IN
    assert(s.m_current_irq_level == 15 && s.m_current_vector == 0x40 && s.m_ist == 0);
    assert(s.irq_ack_cb(15) == 0x40);
    assert(s.host.lines.size() == 6 && s.m_ism == 0xbfff);
    ++handshakes;
  }
  for (unsigned lanes = 0; lanes < 16; ++lanes)
    for (u32 initial : {0u, 0xffffffffu, 0xffff0000u, 0x12345678u})
      for (u32 data : {0u, 0xffffffffu, 0xaaaaaaaau, 0x55555555u}) {
        saturn_scu_device s;
        u32 mask = byte_mask(lanes);
        s.m_ist = initial;
        s.irq_status_w(0, data, mask);
        assert(s.irq_status_r() == (initial & (data | ~mask)));
        assert(s.host.lines.empty()); // IMS reset value masks external too
        s.m_ist = 0;
        s.m_ism = initial & 0xbfff;
        u32 expected = (((initial & 0xbfff) & ~mask) | (data & mask)) & 0xbfff;
        s.irq_mask_w(0, data, mask);
        assert(s.irq_mask_r() == expected && s.host.lines.empty());
        writes += 2;
      }
  assert(arbitration == 1920 && handshakes == 16 && writes == 512);
  std::cout << arbitration << " interrupt arbitrations, " << handshakes
            << " acknowledgement sequences and " << writes << " masked register writes passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix="saturn-scu-irqs-") as temp:
    cpp = Path(temp) / "irqs.cpp"
    exe = Path(temp) / "irqs"
    cpp.write_text(harness.replace("// PRODUCTION_MASK", mask)
                   .replace("// PRODUCTION_FUNCTIONS", functions))
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O1", "-g",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

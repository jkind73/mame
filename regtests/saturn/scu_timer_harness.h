// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
// Recording stand-ins for callback tests, not an SCU or emu_timer implementation.
#include <cassert>
#include <cstdint>
#include <iostream>
using offs_t = unsigned;
constexpr unsigned DMA_EVENT_HBLANKIN=0, DMA_EVENT_TIMER0=1, DMA_EVENT_TIMER1=2;
constexpr unsigned IST_HBLANK_IN=1, IST_TIMER_0=2, IST_TIMER_1=4;
constexpr unsigned DMA_EVENT_VBLANKOUT=3, DMA_EVENT_VBLANKIN=4;
constexpr unsigned IST_VBLANK_OUT=8, IST_VBLANK_IN=16;
constexpr bool BIT(unsigned x, unsigned bit) { return (x >> bit) & 1; }
#define COMBINE_DATA(p) (*(p) = (*(p) & ~mem_mask) | (data & mem_mask))
#define TIMER_CALLBACK_MEMBER(name) void name()
struct attotime {
  int64_t ticks;
  static const attotime never;
  bool is_never() const { return ticks == -1; }
  static attotime from_ticks(int count, int rate) { assert(rate == 1); return {count}; }
};
const attotime attotime::never{-1};
struct timer {
  int64_t now = 0;
  attotime deadline = attotime::never;
  bool active = false;
  int arms = 0;
  bool enabled() const { return active; }
  attotime expire() const { return deadline; }
  void adjust(attotime delay) {
    // Mirrors emu_timer::adjust: even adjust(never) sets enabled=true.
    active = true;
    deadline = delay.is_never() ? delay : attotime{now + delay.ticks};
    if (!delay.is_never()) ++arms;
  }
};
struct saturn_scu_device {
  timer tim;
  timer *m_timer1 = &tim;
  bool m_tenb = false, m_t1md = false;
  uint32_t m_t1md_reg = 0, m_t1s = 0, m_t0c = 1023;
  uint32_t m_timer0_counter = 0, m_ist = 0;
  unsigned events[5]{};
  unsigned irq_checks = 0, irq_snapshot = 0;
  int clock() const { return 8; } // existing divisor gives one test tick per count
  void dma_start_factor_ack(unsigned event) { ++events[event]; }
  void test_pending_irqs() { ++irq_checks; irq_snapshot = m_ist; }
  void hblank_in_w(int);
  void vblank_out_w(int);
  void vblank_in_w(int);
  void t0_compare_w(offs_t, uint32_t, uint32_t = ~0u);
  void t1_setdata_w(offs_t, uint32_t, uint32_t = ~0u);
  void t1_mode_w(offs_t, uint32_t, uint32_t = ~0u);
  void timer1_irq_cb();
  void advance(int64_t target) {
    assert(target >= tim.now);
    if (tim.active && !tim.deadline.is_never() && tim.deadline.ticks <= target) {
      tim.now = tim.deadline.ticks;
      // Real scheduler disables one-shot before its callback, then retires it.
      tim.active = false;
      timer1_irq_cb();
      tim.deadline = attotime::never;
    }
    tim.now = target;
  }
};

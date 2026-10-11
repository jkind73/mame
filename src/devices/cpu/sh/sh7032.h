// license:BSD-3-Clause
// copyright-holders:Angelo Salese
#ifndef MAME_CPU_SH_SH7032_H
#define MAME_CPU_SH_SH7032_H
#pragma once
#include "sh2.h"

// SH7032/SH7034 peripherals, REJ09B0272-0700. CMT/MTU belong to SH7014,
// not this SH-1 family. External pin entry points use physical signal levels.
class sh7032_device : public sh2_device
{
  public:
	sh7032_device(const machine_config &, const char *, device_t *, uint32_t);
	template <unsigned N>
	auto txd_callback()
	{
		return m_txd[N].bind();
	}
	template <unsigned N>
	auto sck_callback()
	{
		return m_sck[N].bind();
	}
	template <unsigned N>
	auto dack_callback()
	{
		return m_dack[N].bind();
	}
	template <unsigned N>
	auto dma_read_callback()
	{
		return m_dma_read[N].bind();
	}
	template <unsigned N>
	auto dma_write_callback()
	{
		return m_dma_write[N].bind();
	}
	template <unsigned N>
	auto analog_callback()
	{
		return m_analog[N].bind();
	}
	template <unsigned N>
	auto port_read_callback()
	{
		return m_port_read[N].bind();
	}
	template <unsigned N>
	auto port_write_callback()
	{
		return m_port_write[N].bind();
	}
	auto wdtovf_callback()
	{
		return m_wdtovf.bind();
	}
	void sci_rxd_w(unsigned ch, int state);
	void sci_sck_w(unsigned ch, int state);
	void dreq_w(unsigned ch, int state);
	void wait_w(int state);
	void port_w(unsigned port, uint16_t data);
	void adtrg_w(int state);
	void tclk_w(unsigned input, int state);
	void tioc_w(unsigned ch, unsigned pin, int state);

  protected:
	void device_start() override ATTR_COLD;
	void device_reset() override ATTR_COLD;
	void execute_set_input(int inputnum, int state) override;
	void sh2_exception(const char *, int) override;
	void sleep_enter(unsigned pending_cycles) override;
	void state_import(const device_state_entry &) override;
	void state_export(const device_state_entry &) override;

  private:
	void sh7032_map(address_map &) ATTR_COLD;
	uint16_t peripheral_r(offs_t offset, uint16_t mem_mask = ~0);
	void peripheral_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint8_t reg_r(unsigned address);
	void reg_w(unsigned address, uint8_t data);
	void reset_modules(bool standby);
	void recalc_irq();
	void postload();
	unsigned irq_priority(unsigned vector) const;
	bool irq_requested(unsigned vector) const;
	uint64_t peripheral_clock() const;
	uint16_t word(unsigned r) const
	{
		return (uint16_t(m_regs[r]) << 8) | m_regs[r + 1];
	}
	uint32_t longword(unsigned r) const
	{
		return (uint32_t(word(r)) << 16) | word(r + 2);
	}
	void word(unsigned r, uint16_t v)
	{
		m_regs[r] = v >> 8;
		m_regs[r + 1] = v;
	}
	void longword(unsigned r, uint32_t v)
	{
		word(r, v >> 16);
		word(r + 2, v);
	}
	uint8_t m_regs[0x200]{};
	uint8_t m_flags_read[0x200]{};
	uint16_t m_port_input[3]{0xffff, 0xffff, 0xff};
	uint16_t m_standby_ports[2]{}, m_standby_mask[2]{};
	bool m_standby_serial_pads[2][3]{};
	uint8_t m_irq_input = 0, m_irq_latched = 0;
	bool m_nmi_pin = true, m_standby = false, m_settling = false, m_watchdog_reset = false;
	int m_pin_value = 0;
	devcb_read16::array<3> m_port_read;
	devcb_write16::array<2> m_port_write;
	devcb_read16::array<8> m_analog;
	devcb_write_line::array<2> m_txd, m_sck, m_dack;
	devcb_read16::array<2> m_dma_read;
	devcb_write16::array<2> m_dma_write;
	devcb_write_line m_wdtovf;
	void update_ports();
	uint16_t port_output_mask(unsigned port) const;
	unsigned pin_function(unsigned port, unsigned bit) const;
	uint16_t port_value(unsigned port);
	void route_port(unsigned port, uint16_t old, uint16_t value);

	struct serial_state
	{
		uint8_t smr = 0, brr = 255, scr = 0, tdr = 255, ssr = 0x84, rdr = 0, tsr = 0, ssr_read = 0;
		bool busy = false, tx_prefetched = false, rx_busy = false;
		uint32_t tx_frame = 0;
		uint8_t tx_bit = 0, tx_bits = 0, tx_stop = 0, tx_format = 0, tx_data = 0, tx_mpbt = 0, tx_ext_count = 0;
		uint8_t rsr = 0, rx_stage = 0, rx_format = 0, rx_parity = 0, rx_errors = 0, rx_mp = 0, rx_ext_count = 0;
		int rxd = 1, sck_in = 1, txd_level = 1, sck_level = 1;
	} m_sci[2];
	emu_timer *m_sci_timer[2]{}, *m_sci_rx_timer[2]{}, *m_sci_clock_timer[2]{};
	unsigned sci_bit_clocks(unsigned ch) const;
	void sci_drive_txd(unsigned ch, int state);
	void sci_drive_sck(unsigned ch, int state);
	void sci_reset(unsigned ch);
	void sci_update(unsigned ch);
	void sci_reclock(unsigned ch);
	void sci_start(unsigned ch);
	void sci_load_tsr(unsigned ch);
	void sci_tx_step(unsigned ch);
	void sci_transmit_complete(unsigned ch);
	void sci_rx_start(unsigned ch);
	void sci_sample_rx(unsigned ch);
	void sci_receive_byte(unsigned ch, uint8_t data, uint8_t errors, bool mpb);
	void sci_sync_edge(unsigned ch, bool rising);
	TIMER_CALLBACK_MEMBER(sci_tx_complete);
	TIMER_CALLBACK_MEMBER(sci_rx_tick);
	TIMER_CALLBACK_MEMBER(sci_clock_tick);
	uint8_t smr_r(unsigned ch);
	void smr_w(unsigned ch, uint8_t);
	uint8_t brr_r(unsigned ch);
	void brr_w(unsigned ch, uint8_t);
	uint8_t scr_r(unsigned ch);
	void scr_w(unsigned ch, uint8_t);
	uint8_t tdr_r(unsigned ch);
	void tdr_w(unsigned ch, uint8_t);
	uint8_t ssr_r(unsigned ch);
	void ssr_w(unsigned ch, uint8_t);
	uint8_t rdr_r(unsigned ch);

	bool m_dack_level[2]{};
	bool m_dreq[2]{true, true}, m_dreq_edge[2]{};
	uint8_t m_dma_order[4]{0, 3, 2, 1};
	int m_dma_channel = -1, m_dma_phase = 0, m_dma_access = -1;
	uint16_t m_dma_data = 0, m_dma_control = 0;
	uint32_t m_dma_src = 0, m_dma_dst = 0;
	bool m_wait_pin = true;
	bool m_dma_burst[4]{}, m_dma_halted = false;
	emu_timer *m_dma_timer = nullptr;
	bool dma_requested(unsigned ch) const;
	void dma_schedule();
	void dma_release();
	void dma_ack(unsigned ch, bool active);
	void dma_withdraw(unsigned ch);
	unsigned bus_cycles(uint32_t address, bool write, bool single, unsigned size) const;
	bool bus_waits(uint32_t address, bool write, bool single) const;
	TIMER_CALLBACK_MEMBER(dma_tick);

	uint8_t m_adc_channel = 0, m_adc_temp = 0;
	uint16_t m_adc_sample = 0;
	bool m_adtrg = true, m_adc_sampling = false;
	emu_timer *m_adc_timer = nullptr;
	void adc_start();
	TIMER_CALLBACK_MEMBER(adc_tick);
	uint64_t m_wdt_epoch = 0;
	emu_timer *m_wdt_timer = nullptr, *m_wdt_pulse_timer = nullptr, *m_reset_timer = nullptr;
	bool m_wdt_output = true;
	unsigned wdt_divider() const;
	void wdt_sync();
	void wdt_schedule();
	void wdt_write(unsigned reg, uint16_t data, uint16_t mem_mask);
	TIMER_CALLBACK_MEMBER(wdt_tick);
	TIMER_CALLBACK_MEMBER(wdt_pulse);
	TIMER_CALLBACK_MEMBER(reset_tick);
	TIMER_CALLBACK_MEMBER(standby_wake);
	emu_timer *m_standby_timer = nullptr;

	struct timer_state
	{
		uint64_t epoch = 0;
		uint16_t counter = 0;
		uint8_t read_flags = 0;
		bool output[2]{}, input[2]{}, down = false;
	} m_itu[5];
	bool m_tclk[4]{};
	bool m_pwm_negative[2]{};
	emu_timer *m_itu_timer[5]{};
	unsigned itu_base(unsigned ch) const;
	void itu_sync(unsigned ch);
	void itu_combined_step();
	void itu_schedule(unsigned ch);
	void itu_advance(unsigned ch, uint64_t count, bool down = false);
	void itu_event(unsigned ch, unsigned events);
	void itu_clear(unsigned ch);
	TIMER_CALLBACK_MEMBER(itu_tick);
};
DECLARE_DEVICE_TYPE(SH7032, sh7032_device)
#endif

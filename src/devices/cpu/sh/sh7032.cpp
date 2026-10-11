// license:BSD-3-Clause
// copyright-holders:Angelo Salese
// SH7032/SH7034 peripheral state machines, REJ09B0272-0700 chapters 5, 9-16, 19.
#include "emu.h"
#include "sh7032.h"

DEFINE_DEVICE_TYPE(SH7032, sh7032_device, "sh7032", "Hitachi SH-1 (SH7032)")

sh7032_device::sh7032_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: sh2_device(mconfig, SH7032, tag, owner, clock, CPU_TYPE_SH1, address_map_constructor(FUNC(sh7032_device::sh7032_map), this), 28, 0x0fffffff), m_port_read(*this, 0xffff), m_port_write(*this), m_analog(*this, 0), m_txd(*this), m_sck(*this), m_dack(*this), m_dma_read(*this, 0xffff), m_dma_write(*this), m_wdtovf(*this)
{
	m_track_pending = true;
}

void sh7032_device::sh7032_map(address_map &map)
{
	// Only A27-A24 and A8-A0 decode in the peripheral area (8.3.5).
	map(0x05000000, 0x050001ff).mirror(0x00fffe00).rw(FUNC(sh7032_device::peripheral_r), FUNC(sh7032_device::peripheral_w));
	map(0x0f000000, 0x0f001fff).mirror(0x00ffe000).ram();
}

void sh7032_device::device_start()
{
	sh2_device::device_start();
	save_item(NAME(m_regs));
	save_item(NAME(m_flags_read));
	save_item(NAME(m_port_input));
	save_item(NAME(m_standby_ports));
	save_item(NAME(m_standby_mask));
	save_item(NAME(m_standby_serial_pads));
	save_item(NAME(m_irq_input));
	save_item(NAME(m_irq_latched));
	save_item(NAME(m_nmi_pin));
	save_item(NAME(m_standby));
	save_item(NAME(m_settling));
	save_item(NAME(m_watchdog_reset));
	save_item(NAME(m_dack_level));
	save_item(NAME(m_dreq));
	save_item(NAME(m_dreq_edge));
	save_item(NAME(m_dma_order));
	save_item(NAME(m_dma_channel));
	save_item(NAME(m_dma_phase));
	save_item(NAME(m_dma_data));
	save_item(NAME(m_dma_control));
	save_item(NAME(m_dma_src));
	save_item(NAME(m_dma_dst));
	save_item(NAME(m_wait_pin));
	save_item(NAME(m_dma_burst));
	save_item(NAME(m_dma_halted));
	save_item(NAME(m_adc_channel));
	save_item(NAME(m_adc_temp));
	save_item(NAME(m_adc_sample));
	save_item(NAME(m_adc_sampling));
	save_item(NAME(m_adtrg));
	save_item(NAME(m_wdt_epoch));
	save_item(NAME(m_wdt_output));
	save_item(NAME(m_tclk));
	save_item(NAME(m_pwm_negative));
	save_item(STRUCT_MEMBER(m_itu, epoch));
	save_item(STRUCT_MEMBER(m_itu, counter));
	save_item(STRUCT_MEMBER(m_itu, read_flags));
	save_item(STRUCT_MEMBER(m_itu, output));
	save_item(STRUCT_MEMBER(m_itu, input));
	save_item(STRUCT_MEMBER(m_itu, down));
	save_item(STRUCT_MEMBER(m_sci, smr));
	save_item(STRUCT_MEMBER(m_sci, brr));
	save_item(STRUCT_MEMBER(m_sci, scr));
	save_item(STRUCT_MEMBER(m_sci, tdr));
	save_item(STRUCT_MEMBER(m_sci, ssr));
	save_item(STRUCT_MEMBER(m_sci, rdr));
	save_item(STRUCT_MEMBER(m_sci, tsr));
	save_item(STRUCT_MEMBER(m_sci, ssr_read));
	save_item(STRUCT_MEMBER(m_sci, busy));
	save_item(STRUCT_MEMBER(m_sci, tx_prefetched));
	save_item(STRUCT_MEMBER(m_sci, rx_busy));
	save_item(STRUCT_MEMBER(m_sci, tx_frame));
	save_item(STRUCT_MEMBER(m_sci, tx_bit));
	save_item(STRUCT_MEMBER(m_sci, tx_bits));
	save_item(STRUCT_MEMBER(m_sci, tx_stop));
	save_item(STRUCT_MEMBER(m_sci, tx_format));
	save_item(STRUCT_MEMBER(m_sci, tx_data));
	save_item(STRUCT_MEMBER(m_sci, tx_mpbt));
	save_item(STRUCT_MEMBER(m_sci, tx_ext_count));
	save_item(STRUCT_MEMBER(m_sci, rsr));
	save_item(STRUCT_MEMBER(m_sci, rx_stage));
	save_item(STRUCT_MEMBER(m_sci, rx_format));
	save_item(STRUCT_MEMBER(m_sci, rx_parity));
	save_item(STRUCT_MEMBER(m_sci, rx_errors));
	save_item(STRUCT_MEMBER(m_sci, rx_mp));
	save_item(STRUCT_MEMBER(m_sci, rx_ext_count));
	save_item(STRUCT_MEMBER(m_sci, rxd));
	save_item(STRUCT_MEMBER(m_sci, sck_in));
	save_item(STRUCT_MEMBER(m_sci, txd_level));
	save_item(STRUCT_MEMBER(m_sci, sck_level));
	for (unsigned ch = 0; ch < 2; ch++)
	{
		m_sci_timer[ch] = timer_alloc(FUNC(sh7032_device::sci_tx_complete), this);
		m_sci_rx_timer[ch] = timer_alloc(FUNC(sh7032_device::sci_rx_tick), this);
		m_sci_clock_timer[ch] = timer_alloc(FUNC(sh7032_device::sci_clock_tick), this);
	}
	for (unsigned ch = 0; ch < 5; ch++)
		m_itu_timer[ch] = timer_alloc(FUNC(sh7032_device::itu_tick), this);
	m_dma_timer = timer_alloc(FUNC(sh7032_device::dma_tick), this);
	m_adc_timer = timer_alloc(FUNC(sh7032_device::adc_tick), this);
	m_wdt_timer = timer_alloc(FUNC(sh7032_device::wdt_tick), this);
	m_wdt_pulse_timer = timer_alloc(FUNC(sh7032_device::wdt_pulse), this);
	m_reset_timer = timer_alloc(FUNC(sh7032_device::reset_tick), this);
	m_standby_timer = timer_alloc(FUNC(sh7032_device::standby_wake), this);
	machine().save().register_postload(save_prepost_delegate(FUNC(sh7032_device::postload), this));
	state_add(0x100, "RXD0", m_pin_value).mask(1).callimport().callexport();
	state_add(0x101, "SCK0", m_pin_value).mask(1).callimport().callexport();
	state_add(0x102, "TXD0", m_sci[0].txd_level).mask(1);
	state_add(0x103, "RXD1", m_pin_value).mask(1).callimport().callexport();
	state_add(0x104, "SCK1", m_pin_value).mask(1).callimport().callexport();
	state_add(0x105, "TXD1", m_sci[1].txd_level).mask(1);
	state_add(0x110, "DREQ0", m_pin_value).mask(1).callimport().callexport();
	state_add(0x111, "DREQ1", m_pin_value).mask(1).callimport().callexport();
	state_add(0x112, "ADTRG", m_pin_value).mask(1).callimport().callexport();
	state_add(0x120, "PORTA", m_pin_value).mask(0xffff).callimport().callexport();
	state_add(0x121, "PORTB", m_pin_value).mask(0xffff).callimport().callexport();
	state_add(0x122, "PORTC", m_pin_value).mask(0xff).callimport().callexport();
	state_add(0x130, "TCLKA", m_pin_value).mask(1).callimport().callexport();
	state_add(0x131, "TCLKB", m_pin_value).mask(1).callimport().callexport();
	state_add(0x132, "TCLKC", m_pin_value).mask(1).callimport().callexport();
	state_add(0x133, "TCLKD", m_pin_value).mask(1).callimport().callexport();
	state_add(0x140, "WDTOVF", m_wdt_output).mask(1);
	state_add(0x141, "WAIT", m_pin_value).mask(1).callimport().callexport();
	state_add(0x142, "DACK0", m_dack_level[0]).mask(1);
	state_add(0x143, "DACK1", m_dack_level[1]).mask(1);
}

uint64_t sh7032_device::peripheral_clock() const
{
	return (executing() ? local_time() + cycles_to_attotime(m_isdrc ? m_bus_pending : 0) : machine().time()).as_ticks(clock());
}

void sh7032_device::reset_modules(bool standby)
{
	for (unsigned ch = 0; ch < 2; ch++)
		sci_reset(ch);
	std::fill(m_regs + 0xe0, m_regs + 0xea, 0);
	m_regs[0xe9] = 0x7f;
	m_adc_timer->adjust(attotime::never);
	m_adc_channel = 0;
	m_adc_sample = 0;
	m_adc_sampling = false;
	m_adc_temp = 0;
	std::fill(m_regs + 0x100, m_regs + 0x180, 0);
	m_regs[0x100] = m_regs[0x101] = 0x60;
	m_regs[0x103] = 0x40;
	m_regs[0x131] = 0x7f;
	for (unsigned ch = 0; ch < 5; ch++)
	{
		unsigned b = itu_base(ch);
		m_regs[b + 1] = 8;
		m_regs[b + 2] = m_regs[b + 3] = 0x78;
		word(b + 6, 0xffff);
		word(b + 8, 0xffff);
		if (ch >= 3)
		{
			word(b + 10, 0xffff);
			word(b + 12, 0xffff);
		}
		m_itu[ch] = {};
		m_itu[ch].epoch = peripheral_clock();
		m_itu_timer[ch]->adjust(attotime::never);
	}
	m_pwm_negative[0] = m_pwm_negative[1] = false;
	m_dma_timer->adjust(attotime::never);
	m_dma_channel = -1;
	m_dma_phase = 0;
	std::fill(std::begin(m_dma_burst), std::end(m_dma_burst), false);
	m_dma_order[0] = 0;
	m_dma_order[1] = 3;
	m_dma_order[2] = 2;
	m_dma_order[3] = 1;
	dma_release();
	for (unsigned ch = 0; ch < 2; ch++)
	{
		m_dreq_edge[ch] = false;
		dma_ack(ch, false);
	}
	m_regs[0x1b8] = standby ? (m_regs[0x1b8] & 7) | 0x18 : 0x18;
	if (!standby)
		m_regs[0x1b9] = 0;
	m_regs[0x1bb] = 0x1f;
	m_wdt_epoch = peripheral_clock();
	m_wdt_timer->adjust(attotime::never);
}

void sh7032_device::device_reset()
{
	bool const manual = m_manual_reset, watchdog = m_watchdog_reset;
	uint8_t const reset_status = m_regs[0x1bb];
	sh2_device::device_reset();
	m_standby = m_settling = false;
	if (!manual)
	{
		std::fill(std::begin(m_regs), std::end(m_regs), 0);
		word(0x1a0, 0);
		word(0x1a2, 0xffff);
		word(0x1a4, 0xffff);
		word(0x1a6, 0xf800);
		word(0x1a8, 0);
		word(0x1aa, 0);
		word(0x1ac, 0);
		word(0x1ae, 0);
		word(0x1c8, 0x3302);
		word(0x1ca, 0xff95);
		word(0x1ee, 0x5fff);
		m_irq_latched = 0;
	}
	std::fill(std::begin(m_flags_read), std::end(m_flags_read), 0);
	std::fill(m_regs + 0x184, m_regs + 0x19a, 0);
	std::fill(m_regs + 0x1f0, m_regs + 0x1f8, 0);
	m_regs[0x1f0] = 0xf0;
	m_irq_latched = 0;
	reset_modules(false);
	m_regs[0x1bc] = 0x1f;
	if (watchdog)
		m_regs[0x1bb] = reset_status;
	else
	{
		m_wdt_output = true;
		m_wdtovf(1);
		m_wdt_pulse_timer->adjust(attotime::never);
	}
	m_watchdog_reset = false;
	m_reset_timer->adjust(attotime::never);
	m_standby_timer->adjust(attotime::never);
	resume(SUSPEND_REASON_SPIN);
	resume(SUSPEND_REASON_CLOCK);
	update_ports();
	recalc_irq();
}

void sh7032_device::postload()
{
	update_ports();
	m_wdtovf(m_wdt_output);
	for (unsigned ch = 0; ch < 2; ch++)
	{
		m_txd[ch](m_standby ? m_standby_serial_pads[ch][0] : m_sci[ch].txd_level);
		m_sck[ch](m_standby ? m_standby_serial_pads[ch][1] : m_sci[ch].sck_level);
		if (!m_standby)
			m_dack[ch](m_standby ? m_standby_serial_pads[ch][2] : m_dack_level[ch]);
	}
	recalc_irq();
}

void sh7032_device::state_import(const device_state_entry &e)
{
	unsigned id = e.index();
	if (id == SH_SR)
	{
		m_test_irq = 1;
		return;
	}
	if (id == 0x141)
		wait_w(m_pin_value);
	else if (id == 0x100 || id == 0x103)
		sci_rxd_w(id == 0x103, m_pin_value);
	else if (id == 0x101 || id == 0x104)
		sci_sck_w(id == 0x104, m_pin_value);
	else if (id == 0x110 || id == 0x111)
		dreq_w(id - 0x110, m_pin_value);
	else if (id == 0x112)
		adtrg_w(m_pin_value);
	else if (id >= 0x120 && id <= 0x122)
		port_w(id - 0x120, m_pin_value);
	else if (id >= 0x130 && id <= 0x133)
		tclk_w(id - 0x130, m_pin_value);
	else
		sh2_device::state_import(e);
}
void sh7032_device::state_export(const device_state_entry &e)
{
	unsigned id = e.index();
	if (id == 0x141)
		m_pin_value = m_wait_pin;
	else if (id == 0x100 || id == 0x103)
		m_pin_value = m_sci[id == 0x103].rxd;
	else if (id == 0x101 || id == 0x104)
		m_pin_value = m_sci[id == 0x104].sck_in;
	else if (id == 0x110 || id == 0x111)
		m_pin_value = m_dreq[id - 0x110];
	else if (id == 0x112)
		m_pin_value = m_adtrg;
	else if (id >= 0x120 && id <= 0x122)
		m_pin_value = m_port_input[id - 0x120];
	else if (id >= 0x130 && id <= 0x133)
		m_pin_value = m_tclk[id - 0x130];
	else
		sh2_device::state_export(e);
}
void sh7032_device::sci_reset(unsigned ch)
{
	m_sci[ch].smr = m_sci[ch].scr = m_sci[ch].rdr = m_sci[ch].ssr_read = 0;
	m_sci[ch].brr = m_sci[ch].tdr = 0xff;
	m_sci[ch].ssr = 0x84;
	m_sci[ch].busy = m_sci[ch].tx_prefetched = m_sci[ch].rx_busy = false;
	m_sci[ch].tx_frame = 0;
	m_sci[ch].tx_bit = m_sci[ch].tx_bits = m_sci[ch].tx_stop = m_sci[ch].tx_format = m_sci[ch].tx_data = m_sci[ch].tx_mpbt = m_sci[ch].tx_ext_count = 0;
	m_sci[ch].rsr = m_sci[ch].rx_stage = m_sci[ch].rx_format = m_sci[ch].rx_parity = m_sci[ch].rx_errors = m_sci[ch].rx_mp = m_sci[ch].rx_ext_count = 0;
	m_sci_timer[ch]->adjust(attotime::never, ch);
	m_sci_rx_timer[ch]->adjust(attotime::never, ch);
	m_sci_clock_timer[ch]->adjust(attotime::never, ch);
	sci_drive_txd(ch, 1);
	sci_drive_sck(ch, 1);
}

unsigned sh7032_device::sci_bit_clocks(unsigned ch) const
{
	// Tables 13.3/13.4: phi / (32 or 4 * (BRR+1) * 4^CKS).
	return ((m_sci[ch].smr & 0x80) ? 4U : 32U) * (unsigned(m_sci[ch].brr) + 1) * (1U << (2 * (m_sci[ch].smr & 3)));
}

void sh7032_device::sci_drive_txd(unsigned ch, int state)
{
	if (m_sci[ch].txd_level != state)
	{
		m_sci[ch].txd_level = state;
		if (!m_standby)
			m_txd[ch](state);
		update_ports();
	}
}

void sh7032_device::sci_drive_sck(unsigned ch, int state)
{
	if (m_sci[ch].sck_level != state)
	{
		m_sci[ch].sck_level = state;
		if (!m_standby)
			m_sck[ch](state);
		update_ports();
	}
}

void sh7032_device::sci_reclock(unsigned ch)
{
	if (m_standby)
	{
		m_sci_timer[ch]->adjust(attotime::never, ch);
		m_sci_rx_timer[ch]->adjust(attotime::never, ch);
		m_sci_clock_timer[ch]->adjust(attotime::never, ch);
		return;
	}

	if (m_sci[ch].smr & 0x80)
	{
		m_sci_clock_timer[ch]->adjust(attotime::never, ch);
		m_sci_rx_timer[ch]->adjust(attotime::never, ch);
		bool const active = !(m_sci[ch].scr & 2) && !(m_sci[ch].ssr & 0x38) &&
							((!(m_sci[ch].scr & 0x20) && (m_sci[ch].scr & 0x10)) || ((m_sci[ch].scr & 0x20) && (m_sci[ch].busy || m_sci[ch].tx_prefetched || !(m_sci[ch].ssr & 0x80))));
		if (active)
		{
			if (!m_sci_timer[ch]->enabled() || m_sci_timer[ch]->expire().is_never())
				m_sci_timer[ch]->adjust(cycles_to_attotime(sci_bit_clocks(ch) / 2), ch);
		}
		else
		{
			m_sci_timer[ch]->adjust(attotime::never, ch);
			if (!(m_sci[ch].scr & 2))
				sci_drive_sck(ch, 1);
		}
	}
	else
	{
		if (!m_sci[ch].busy || !(m_sci[ch].scr & 0x20) || (m_sci[ch].scr & 2))
			m_sci_timer[ch]->adjust(attotime::never, ch);
		else if (!m_sci_timer[ch]->enabled() || m_sci_timer[ch]->expire().is_never())
			m_sci_timer[ch]->adjust(cycles_to_attotime(sci_bit_clocks(ch)), ch);
		if ((m_sci[ch].scr & 3) == 1)
		{
			if (!m_sci_clock_timer[ch]->enabled() || m_sci_clock_timer[ch]->expire().is_never())
				m_sci_clock_timer[ch]->adjust(cycles_to_attotime(sci_bit_clocks(ch) / 2), ch);
		}
		else
		{
			m_sci_clock_timer[ch]->adjust(attotime::never, ch);
			sci_drive_sck(ch, 1);
		}
	}
}

void sh7032_device::sci_update(unsigned ch)
{
	sci_reclock(ch);
	recalc_irq();
	dma_schedule();
}

void sh7032_device::sci_load_tsr(unsigned ch)
{
	m_sci[ch].tsr = m_sci[ch].tdr;
	m_sci[ch].tx_mpbt = m_sci[ch].ssr & 1;
	m_sci[ch].tx_prefetched = true;
	m_sci[ch].ssr |= 0x80;
	m_sci[ch].ssr_read &= ~0x80;
}

// Pin clocks and framing replace the former byte-completion HACK.
void sh7032_device::sci_start(unsigned ch)
{
	if (m_standby || m_sci[ch].busy || !(m_sci[ch].scr & 0x20) ||
		((m_sci[ch].smr & 0x80) && (m_sci[ch].ssr & 0x38)) || (!m_sci[ch].tx_prefetched && (m_sci[ch].ssr & 0x80)))
		return;
	if (!m_sci[ch].tx_prefetched)
		sci_load_tsr(ch);
	m_sci[ch].tx_prefetched = false;
	m_sci[ch].busy = true;
	m_sci[ch].tx_format = m_sci[ch].smr;
	m_sci[ch].tx_bit = m_sci[ch].tx_ext_count = 0;
	m_sci[ch].tx_data = m_sci[ch].tsr;
	if (m_sci[ch].tx_format & 0x80)
	{
		m_sci[ch].tx_frame = m_sci[ch].tx_data;
		m_sci[ch].tx_bits = 8;
		m_sci[ch].tx_stop = 7;
	}
	else
	{
		unsigned const bits = (m_sci[ch].tx_format & 0x40) ? 7 : 8;
		m_sci[ch].tx_data &= (1U << bits) - 1;
		m_sci[ch].tx_frame = uint32_t(m_sci[ch].tx_data) << 1; // start bit is zero
		m_sci[ch].tx_stop = 1 + bits;
		if (m_sci[ch].tx_format & 0x24)
		{
			unsigned parity = 0;
			for (unsigned i = 0; i < bits; i++)
				parity ^= BIT(m_sci[ch].tx_data, i);
			unsigned const extra = (m_sci[ch].tx_format & 4) ? m_sci[ch].tx_mpbt : (parity ^ BIT(m_sci[ch].tx_format, 4));
			m_sci[ch].tx_frame |= extra << m_sci[ch].tx_stop++;
		}
		unsigned const stops = (m_sci[ch].tx_format & 8) ? 2 : 1;
		m_sci[ch].tx_frame |= ((1U << stops) - 1) << m_sci[ch].tx_stop;
		m_sci[ch].tx_bits = m_sci[ch].tx_stop + stops;
		if (!(m_sci[ch].scr & 2))
			sci_tx_step(ch);
	}
	sci_update(ch);
}

void sh7032_device::sci_tx_step(unsigned ch)
{
	if (!m_sci[ch].busy)
		return;
	if (m_sci[ch].tx_bit == m_sci[ch].tx_bits)
	{
		sci_transmit_complete(ch);
		return;
	}
	sci_drive_txd(ch, BIT(m_sci[ch].tx_frame, m_sci[ch].tx_bit));
	// 13.3.2/13.3.4: the queue is inspected when the stop bit/MSB is output,
	// not after its interval. Keep the old frame data while preloading TSR.
	if (m_sci[ch].tx_bit == m_sci[ch].tx_stop)
	{
		if (!(m_sci[ch].ssr & 0x80))
			sci_load_tsr(ch);
		else
			m_sci[ch].ssr |= 4;
		sci_update(ch);
	}
	m_sci[ch].tx_bit++;
}

void sh7032_device::sci_transmit_complete(unsigned ch)
{
	if (!m_sci[ch].busy)
		return;
	m_sci[ch].busy = false;

	if (!(m_sci[ch].tx_format & 0x80))
	{
		sci_drive_txd(ch, 1);
		sci_start(ch);
		if ((m_sci[ch].scr & 2) && m_sci[ch].busy)
			sci_tx_step(ch);
	}
	sci_update(ch);
}

void sh7032_device::sci_rx_start(unsigned ch)
{
	m_sci[ch].rx_busy = true;
	m_sci[ch].rx_format = m_sci[ch].smr;
	m_sci[ch].rsr = m_sci[ch].rx_stage = m_sci[ch].rx_parity = m_sci[ch].rx_errors = m_sci[ch].rx_mp = 0;
	m_sci[ch].rx_ext_count = 8; // external async clock is 16 times the bit rate
	if (!(m_sci[ch].rx_format & 0x80) && !(m_sci[ch].scr & 2))
		m_sci_rx_timer[ch]->adjust(cycles_to_attotime(sci_bit_clocks(ch) / 2), ch);
}

void sh7032_device::sci_sample_rx(unsigned ch)
{
	if (!m_sci[ch].rx_busy)
		return;
	if (m_sci[ch].rx_format & 0x80)
	{
		m_sci[ch].rsr |= m_sci[ch].rxd << m_sci[ch].rx_stage++;
		if (m_sci[ch].rx_stage < 8)
			return;
	}
	else
	{
		unsigned const bits = (m_sci[ch].rx_format & 0x40) ? 7 : 8;
		bool const extra = (m_sci[ch].rx_format & 0x24) != 0;
		if (!m_sci[ch].rx_stage)
		{
			if (m_sci[ch].rxd) // reject a short/false start
				m_sci[ch].rx_busy = false;
			else
				m_sci[ch].rx_stage = 1;
			return;
		}
		if (m_sci[ch].rx_stage <= bits)
		{
			m_sci[ch].rsr |= m_sci[ch].rxd << (m_sci[ch].rx_stage - 1);
			m_sci[ch].rx_parity ^= m_sci[ch].rxd;
			m_sci[ch].rx_stage++;
			return;
		}
		if (extra && m_sci[ch].rx_stage == bits + 1)
		{
			if (m_sci[ch].rx_format & 4)
				m_sci[ch].rx_mp = m_sci[ch].rxd;
			else if (m_sci[ch].rxd != (m_sci[ch].rx_parity ^ BIT(m_sci[ch].rx_format, 4)))
				m_sci[ch].rx_errors |= 8;
			m_sci[ch].rx_stage++;
			return;
		}
		if (!m_sci[ch].rxd)
			m_sci[ch].rx_errors |= 0x10;
	}
	m_sci[ch].rx_busy = false;
	sci_receive_byte(ch, m_sci[ch].rsr, m_sci[ch].rx_errors, m_sci[ch].rx_mp);
}

void sh7032_device::sci_receive_byte(unsigned ch, uint8_t data, uint8_t errors, bool mpb)
{
	if (m_standby || !(m_sci[ch].scr & 0x10) || (m_sci[ch].ssr & 0x38))
		return;
	if ((m_sci[ch].rx_format & 0x84) == 4)
	{
		m_sci[ch].ssr = (m_sci[ch].ssr & ~2) | (mpb ? 2 : 0);
		if ((m_sci[ch].scr & 8) && !mpb)
		{
			sci_update(ch); // MPIE suppresses data and errors until an address frame
			return;
		}
		if (mpb)
			m_sci[ch].scr &= ~8;
	}
	if (m_sci[ch].ssr & 0x40)
		errors |= 0x20;
	m_sci[ch].ssr |= errors & 0x38;
	if (!(errors & 0x20))
		m_sci[ch].rdr = data;
	if (!errors)
		m_sci[ch].ssr |= 0x40;
	sci_update(ch);
}

void sh7032_device::sci_sync_edge(unsigned ch, bool rising)
{
	if (m_sci[ch].ssr & 0x38)
		return;
	if (!rising)
	{
		sci_start(ch);
		if (m_sci[ch].busy)
			sci_tx_step(ch);
		if ((m_sci[ch].scr & 0x10) && !m_sci[ch].rx_busy)
			sci_rx_start(ch);
	}
	else
	{
		if (m_sci[ch].rx_busy)
			sci_sample_rx(ch);
		if (m_sci[ch].busy && m_sci[ch].tx_bit == 8)
			sci_transmit_complete(ch);
	}
}

TIMER_CALLBACK_MEMBER(sh7032_device::sci_tx_complete)
{
	unsigned const ch = param;
	if (m_sci[ch].smr & 0x80)
	{
		if (m_sci[ch].sck_level)
		{
			sci_sync_edge(ch, false);
			sci_drive_sck(ch, 0);
		}
		else
		{
			sci_drive_sck(ch, 1);
			sci_sync_edge(ch, true);
		}
	}
	else
		sci_tx_step(ch);
	sci_reclock(ch);
}

TIMER_CALLBACK_MEMBER(sh7032_device::sci_rx_tick)
{
	unsigned const ch = param;
	sci_sample_rx(ch);
	if (m_sci[ch].rx_busy && m_sci[ch].rx_stage)
		m_sci_rx_timer[ch]->adjust(cycles_to_attotime(sci_bit_clocks(ch)), ch);
}

TIMER_CALLBACK_MEMBER(sh7032_device::sci_clock_tick)
{
	unsigned const ch = param;
	sci_drive_sck(ch, !m_sci[ch].sck_level);
	sci_reclock(ch);
}

void sh7032_device::sci_rxd_w(unsigned ch, int state)
{
	int const old = m_sci[ch].rxd;
	m_sci[ch].rxd = !!state;
	if (!m_standby && !(m_sci[ch].smr & 0x80) && (m_sci[ch].scr & 0x10) &&
		old && !m_sci[ch].rxd && !m_sci[ch].rx_busy && !(m_sci[ch].ssr & 0x38))
		sci_rx_start(ch);
}

void sh7032_device::sci_sck_w(unsigned ch, int state)
{
	state = !!state;
	if (m_sci[ch].sck_in == state)
		return;
	m_sci[ch].sck_in = state;
	if (m_standby || !(m_sci[ch].scr & 2))
		return;
	if (m_sci[ch].smr & 0x80)
		sci_sync_edge(ch, state);
	else if (state)
	{
		if (m_sci[ch].busy)
		{
			if (!m_sci[ch].tx_ext_count)
				sci_tx_step(ch);
			m_sci[ch].tx_ext_count = (m_sci[ch].tx_ext_count + 1) & 15;
		}
		if (m_sci[ch].rx_busy && !--m_sci[ch].rx_ext_count)
		{
			sci_sample_rx(ch);
			m_sci[ch].rx_ext_count = 16;
		}
	}
}

uint8_t sh7032_device::smr_r(unsigned ch)
{
	return m_sci[ch].smr;
}

void sh7032_device::smr_w(unsigned ch, uint8_t data)
{
	m_sci[ch].smr = data;
	if (!(m_sci[ch].scr & 0x30))
	{
		m_sci_timer[ch]->adjust(attotime::never, ch);
		m_sci_clock_timer[ch]->adjust(attotime::never, ch);
		sci_reclock(ch);
	}
}

uint8_t sh7032_device::brr_r(unsigned ch)
{
	return m_sci[ch].brr;
}

void sh7032_device::brr_w(unsigned ch, uint8_t data)
{
	m_sci[ch].brr = data;
	if (!(m_sci[ch].scr & 0x30))
	{
		m_sci_clock_timer[ch]->adjust(attotime::never, ch);
		sci_reclock(ch);
	}
}

uint8_t sh7032_device::scr_r(unsigned ch)
{
	return m_sci[ch].scr;
}

void sh7032_device::scr_w(unsigned ch, uint8_t data)
{
	uint8_t const old = m_sci[ch].scr;
	m_sci[ch].scr = data;
	if (!(data & 0x20))
	{
		m_sci[ch].busy = m_sci[ch].tx_prefetched = false;
		m_sci[ch].ssr |= 0x84;
		sci_drive_txd(ch, 1);
	}
	if (!(data & 0x10))
	{
		m_sci[ch].rx_busy = false;
		m_sci_rx_timer[ch]->adjust(attotime::never, ch);
	}
	if (!(old & 0x10) && (data & 0x10) && !(m_sci[ch].smr & 0x80) && !m_sci[ch].rxd && !(m_sci[ch].ssr & 0x38))
		sci_rx_start(ch);
	sci_start(ch);
	sci_update(ch);
}

uint8_t sh7032_device::tdr_r(unsigned ch)
{
	return m_sci[ch].tdr;
}

void sh7032_device::tdr_w(unsigned ch, uint8_t data)
{
	m_sci[ch].tdr = data;
	if (m_dma_access >= 0)
	{
		m_sci[ch].ssr &= ~0x84;
		m_sci[ch].ssr_read &= ~0x80;
		sci_start(ch);
		sci_update(ch);
	}
}

uint8_t sh7032_device::ssr_r(unsigned ch)
{
	if (!machine().side_effects_disabled())
		m_sci[ch].ssr_read = m_sci[ch].ssr & 0xf8;
	return m_sci[ch].ssr;
}

void sh7032_device::ssr_w(unsigned ch, uint8_t data)
{
	uint8_t const cleared = m_sci[ch].ssr & m_sci[ch].ssr_read & ~data & 0xf8;
	m_sci[ch].ssr = (m_sci[ch].ssr & ~cleared & 0xfe) | (data & 1);
	m_sci[ch].ssr_read = 0;
	if (cleared & 0x80)
		m_sci[ch].ssr &= ~4;
	if (!(m_sci[ch].scr & 0x20))
		m_sci[ch].ssr |= 0x84;
	if ((cleared & 0x38) && !(m_sci[ch].ssr & 0x38) && (m_sci[ch].scr & 0x10) && !(m_sci[ch].smr & 0x80) && !m_sci[ch].rxd && !m_sci[ch].rx_busy)
		sci_rx_start(ch);
	sci_start(ch);
	sci_update(ch);
}

uint8_t sh7032_device::rdr_r(unsigned ch)
{
	if (m_dma_access >= 0 && !machine().side_effects_disabled())
	{
		m_sci[ch].ssr &= ~0x40;
		m_sci[ch].ssr_read &= ~0x40;
		sci_update(ch);
	}
	return m_sci[ch].rdr;
}

// Four-channel DMAC. One bus phase per event; a request cannot copy the
// whole transfer count synchronously or bypass DREQ qualification.
bool sh7032_device::dma_requested(unsigned ch) const
{
	unsigned const b = 0x140 + 16 * ch, c = word(b + 14), rs = (c >> 8) & 15;
	if (m_standby || (word(0x148) & 7) != 1 || (c & 3) != 1)
		return false;
	if (rs == 12)
		return true;
	if (rs == 0 || rs == 2 || rs == 3)
	{
		if (ch >= 2)
			return false;
		return m_dma_burst[ch] || ((c & 0x20) ? m_dreq_edge[ch] : !m_dreq[ch]);
	}
	if (rs >= 4 && rs <= 7)
	{
		auto const &s = m_sci[(rs - 4) / 2];
		return (rs & 1) ? ((s.scr & 0x80) && (s.ssr & 0x80)) : ((s.scr & 0x40) && (s.ssr & 0x40));
	}
	if (rs >= 8 && rs <= 11)
	{
		unsigned const t = itu_base(rs - 8);
		return (m_regs[t + 2] & m_regs[t + 3] & 1) != 0 || m_dma_burst[ch];
	}
	if (rs == 13)
		return (m_regs[0xe8] & 0xc0) == 0xc0 || m_dma_burst[ch];
	return false;
}
void sh7032_device::dreq_w(unsigned ch, int state)
{
	if (ch >= 2)
		return;
	bool const level = !!state;
	// External edge requests are accepted only while the channel and DMAC
	// are enabled (9.3.1). A pulse during a stopped transfer cannot become
	// a stale request when firmware enables the next sector.
	if (m_dreq[ch] && !level && (word(0x148) & 7) == 1 && (word(0x14e + 16 * ch) & 3) == 1)
		m_dreq_edge[ch] = true;
	m_dreq[ch] = level;
	dma_schedule();
}
void sh7032_device::dma_ack(unsigned ch, bool active)
{
	if (ch < 2)
	{
		m_dack_level[ch] = active ^ BIT(word(0x14e + 16 * ch), 6);
		if (!m_standby)
			m_dack[ch](m_dack_level[ch]);
	}
	update_ports();
}
void sh7032_device::dma_release()
{
	if (m_dma_halted)
	{
		m_dma_halted = false;
		resume(SUSPEND_REASON_HALT);
	}
}
void sh7032_device::dma_schedule()
{
	if (m_dma_channel >= 0)
		return;
	if (m_dma_timer->enabled() && !m_dma_timer->expire().is_never())
		return;
	for (unsigned ch = 0; ch < 4; ch++)
		if (dma_requested(ch))
		{
			m_dma_timer->adjust(cycles_to_attotime(1));
			return;
		}
	dma_release();
}
bool sh7032_device::bus_waits(uint32_t address, bool write, bool single) const
{
	address &= 0x0fffffff;
	unsigned const area = (address >> 24) & 7;
	if ((address >> 24) == 15 || (address >> 24) == 5)
		return false;
	if (area == 6 && BIT(word(0x1a0), 14))
		return true;
	if (single)
		return BIT(word(0x1a4), area + (write ? 0 : 8));
	if (!write)
		return BIT(word(0x1a2), area + 8);
	if (area == 1 && BIT(word(0x1a0), 15))
		return BIT(word(0x1a2), 1);
	return true;
}
unsigned sh7032_device::bus_cycles(uint32_t address, bool write, bool single, unsigned size) const
{
	address &= 0x0fffffff;
	if ((address >> 24) == 15)
		return 1;
	if ((address >> 24) == 5)
		return 3;
	unsigned const area = (address >> 24) & 7;
	bool const wait = bus_waits(address, write, single);
	unsigned count;
	if (area == 6 && BIT(word(0x1a0), 14))
		count = 4;
	else if (area == 1 && BIT(word(0x1a0), 15))
		count = 2 + BIT(word(0x1a8), 13) + (wait ? 2 : 1);
	else if (area == 0 || area == 2 || area == 6)
		count = 2 + ((word(0x1a6) >> (area == 6 ? 11 : 13)) & 3);
	else
		count = wait ? 2 : 1;
	return count * ((size == 2 && !BIT(address, 27)) ? 2 : 1);
}
void sh7032_device::wait_w(int state)
{
	m_wait_pin = !!state;
}
void sh7032_device::dma_withdraw(unsigned ch)
{
	unsigned const rs = (word(0x14e + 16 * ch) >> 8) & 15;
	if (rs >= 8 && rs <= 11)
		m_regs[itu_base(rs - 8) + 3] &= ~1;
	if (rs == 13)
		m_regs[0xe8] &= ~0x80;
	recalc_irq();
}
TIMER_CALLBACK_MEMBER(sh7032_device::dma_tick)
{
	if (m_dma_channel < 0)
	{
		unsigned const mode = (word(0x148) >> 8) & 3;
		static constexpr unsigned fixed[2][4] = {{0, 3, 2, 1}, {1, 3, 2, 0}};
		for (unsigned i = 0; i < 4; i++)
		{
			unsigned const ch = mode < 2 ? fixed[mode][i] : m_dma_order[i];
			if (dma_requested(ch))
			{
				m_dma_channel = ch;
				break;
			}
		}
		if (m_dma_channel < 0)
		{
			dma_release();
			return;
		}
		unsigned const ch = m_dma_channel, c = word(0x14e + 16 * ch), rs = (c >> 8) & 15;
		if (ch < 2 && BIT(c, 5))
			m_dreq_edge[ch] = false;
		if ((c & 0x10) && ((rs >= 8 && rs <= 13) || (rs <= 3 && BIT(c, 5))))
			m_dma_burst[ch] = true;
		if (!m_dma_halted)
		{
			m_dma_halted = true;
			suspend(SUSPEND_REASON_HALT, 1);
		}
		m_dma_phase = 0;
	}
	unsigned const ch = m_dma_channel, b = 0x140 + 16 * ch;
	if ((word(0x148) & 7) != 1 || (word(b + 14) & 3) != 1)
	{
		dma_ack(ch, false);
		m_dma_channel = -1;
		m_dma_burst[ch] = false;
		dma_release();
		dma_schedule();
		return;
	}
	if (!m_dma_phase)
	{
		m_dma_control = word(b + 14);
		unsigned const c = m_dma_control, rs = (c >> 8) & 15, size = BIT(c, 3) ? 2 : 1;
		uint32_t src = longword(b), dst = longword(b + 4);
		if (((c >> 12) & 3) == 3 || ((c >> 14) & 3) == 3 || (size == 2 && ((rs != 3 && (src & 1)) || (rs != 2 && (dst & 1)))))
		{
			word(0x148, word(0x148) | 4);
			m_flags_read[0x149] &= ~4;
			m_dma_channel = -1;
			dma_release();
			sh2_exception_internal("SH-1 DMA address error", 16, 10);
			if (m_isdrc)
				m_sh2_state->pending_nmi = 1;
			return;
		}
		if (((c >> 12) & 3) == 2 && rs != 3)
			src -= size;
		if (((c >> 14) & 3) == 2 && rs != 2)
			dst -= size;
		m_dma_src = src;
		m_dma_dst = dst;
		if (rs == 2 || rs == 3)
		{
			dma_ack(ch, true);
			m_dma_phase = 3;
			m_dma_timer->adjust(cycles_to_attotime(bus_cycles(rs == 2 ? src : dst, rs == 3, true, size)));
		}
		else
		{
			if (ch < 2 && !BIT(c, 7) && rs == 0)
				dma_ack(ch, true);
			m_dma_phase = 1;
			m_dma_timer->adjust(cycles_to_attotime(bus_cycles(src, false, false, size)));
		}
		return;
	}
	unsigned const c = m_dma_control, rs = (c >> 8) & 15, size = BIT(c, 3) ? 2 : 1;
	uint32_t const src = m_dma_src, dst = m_dma_dst;
	bool const single = m_dma_phase == 3;
	uint32_t const address = (m_dma_phase == 1 || rs == 2) ? src : dst;
	bool const write = m_dma_phase == 2 || rs == 3;
	if (!m_wait_pin && bus_waits(address, write, single))
	{
		m_dma_timer->adjust(cycles_to_attotime(1));
		return;
	}
	m_dma_access = ch;
	if (m_dma_phase == 1 || single)
		m_dma_data = rs == 3 ? m_dma_read[ch]() : size == 2 ? m_program->read_word(src & 0x0fffffff)
															: m_program->read_byte(src & 0x0fffffff);
	if (m_dma_phase == 1)
	{
		m_dma_access = -1;
		dma_ack(ch, false);
		if (ch < 2 && BIT(c, 7) && rs == 0)
			dma_ack(ch, true);
		m_dma_phase = 2;
		m_dma_timer->adjust(cycles_to_attotime(bus_cycles(dst, true, false, size)));
		return;
	}
	if (rs == 2)
		m_dma_write[ch](0, m_dma_data, size == 2 ? 0xffff : 0xff);
	else if (size == 2)
		m_program->write_word(dst & 0x0fffffff, m_dma_data);
	else
		m_program->write_byte(dst & 0x0fffffff, m_dma_data);
	m_dma_access = -1;
	dma_ack(ch, false);
	if (rs != 3 && ((c >> 12) & 3) != 0)
		longword(b, src + (((c >> 12) & 3) == 1 ? size : 0));
	if (rs != 2 && ((c >> 14) & 3) != 0)
		longword(b + 4, dst + (((c >> 14) & 3) == 1 ? size : 0));
	uint16_t const count = word(b + 10) - 1;
	word(b + 10, count);
	if (!count)
	{
		word(b + 14, word(b + 14) | 2);
		m_flags_read[b + 15] &= ~2;
		m_dma_burst[ch] = false;
		dma_withdraw(ch);
	}
	else if (!m_dma_burst[ch])
		dma_withdraw(ch);
	unsigned const mode = (word(0x148) >> 8) & 3;
	if (mode == 2)
	{
		unsigned i = 0;
		while (i < 4 && m_dma_order[i] != ch)
			i++;
		if (i < 4)
			std::rotate(std::begin(m_dma_order), std::begin(m_dma_order) + i + 1, std::end(m_dma_order));
	}
	else if (mode == 3 && ch < 2)
	{
		m_dma_order[0] = 3;
		m_dma_order[1] = 2;
		m_dma_order[2] = ch ^ 1;
		m_dma_order[3] = ch;
	}
	m_dma_channel = -1;
	if (!(c & 0x10) || !dma_requested(ch))
		dma_release();
	recalc_irq();
	dma_schedule();
}

// ADC samples and converts each selected input separately. Group 0/1 shares
// ADDRA-D; a CPU high-byte read latches the low byte in TEMP (14.3).
void sh7032_device::adc_start()
{
	if (m_standby || !(m_regs[0xe8] & 0x20))
		return;
	m_adc_channel = (m_regs[0xe8] & 0x10) ? (m_regs[0xe8] & 4) : (m_regs[0xe8] & 7);
	m_adc_sampling = true;
	m_adc_timer->adjust(cycles_to_attotime((m_regs[0xe8] & 8) ? 38 : 74));
}
void sh7032_device::adtrg_w(int state)
{
	bool const level = !!state;
	if (!m_standby && m_adtrg && !level && (m_regs[0xe9] & 0x80) && !(m_regs[0xe8] & 0x20))
	{
		m_regs[0xe8] |= 0x20;
		adc_start();
	}
	m_adtrg = level;
}
TIMER_CALLBACK_MEMBER(sh7032_device::adc_tick)
{
	if (m_standby || !(m_regs[0xe8] & 0x20))
		return;
	bool const fast = m_regs[0xe8] & 8;
	if (m_adc_sampling)
	{
		m_adc_sample = m_analog[m_adc_channel]() & 0x3ff;
		m_adc_sampling = false;
		m_adc_timer->adjust(cycles_to_attotime(fast ? 96 : 192));
		return;
	}
	word(0xe0 + 2 * (m_adc_channel & 3), m_adc_sample << 6);
	if (!(m_regs[0xe8] & 0x10) || m_adc_channel == (m_regs[0xe8] & 7))
	{
		m_regs[0xe8] |= 0x80;
		m_flags_read[0xe8] &= ~0x80;
		if (!(m_regs[0xe8] & 0x10))
			m_regs[0xe8] &= ~0x20;
		else
			m_adc_channel = m_regs[0xe8] & 4;
	}
	else
		m_adc_channel++;
	if (m_regs[0xe8] & 0x20)
	{
		m_adc_sampling = true;
		m_adc_timer->adjust(cycles_to_attotime(fast ? 32 : 64));
	}
	recalc_irq();
	dma_schedule();
}

unsigned sh7032_device::wdt_divider() const
{
	static constexpr unsigned shifts[8] = {1, 6, 7, 8, 9, 10, 12, 13};
	return 1U << shifts[m_regs[0x1b8] & 7];
}
void sh7032_device::wdt_sync()
{
	uint64_t const now = peripheral_clock();
	if (((m_regs[0x1b8] & 0x20) && !m_standby) || m_settling)
	{
		uint64_t const ticks = (now - m_wdt_epoch) / wdt_divider();
		m_regs[0x1b9] += ticks;
		m_wdt_epoch += ticks * wdt_divider();
	}
}
void sh7032_device::wdt_schedule()
{
	if (m_standby || !(m_regs[0x1b8] & 0x20))
	{
		m_wdt_timer->adjust(attotime::never);
		return;
	}
	uint64_t const now = peripheral_clock(), end = m_wdt_epoch + uint64_t(256 - m_regs[0x1b9]) * wdt_divider();
	m_wdt_timer->adjust(cycles_to_attotime(end > now ? end - now : 1));
}
void sh7032_device::wdt_write(unsigned r, uint16_t data, uint16_t mask)
{
	if (mask != 0xffff)
		return;
	if (r == 0x1b8)
	{
		wdt_sync();
		if ((data >> 8) == 0x5a)
		{
			m_regs[0x1b9] = data;
			m_wdt_epoch = peripheral_clock();
		}
		else if ((data >> 8) == 0xa5)
		{
			uint8_t const ovf = m_regs[r] & 0x80 & ~(m_flags_read[r] & ~data);
			m_regs[r] = ovf | (data & 0x67) | 0x18;
			m_flags_read[r] = 0;
			if (!(data & 0x20))
				m_regs[0x1b9] = 0;
			if (data & 0x20)
				m_regs[0x1bc] &= 0x1f;
			m_wdt_epoch = peripheral_clock();
		}
		wdt_schedule();
		recalc_irq();
	}
	else
	{
		if (data == 0xa500 && (m_flags_read[0x1bb] & 0x80))
			m_regs[0x1bb] &= ~0x80;
		else if ((data >> 8) == 0x5a)
			m_regs[0x1bb] = (m_regs[0x1bb] & 0x80) | (data & 0x60) | 0x1f;
		m_flags_read[0x1bb] = 0;
	}
}
TIMER_CALLBACK_MEMBER(sh7032_device::wdt_tick)
{
	m_regs[0x1b9] = 0;
	m_wdt_epoch = peripheral_clock();
	if (m_regs[0x1b8] & 0x40)
	{
		m_regs[0x1bb] |= 0x80;
		m_flags_read[0x1bb] &= ~0x80;
		m_regs[0x1b8] = 0x18;
		m_wdt_output = false;
		m_wdtovf(0);
		m_wdt_pulse_timer->adjust(cycles_to_attotime(128));
		if (m_regs[0x1bb] & 0x40)
		{
			m_watchdog_reset = true;
			suspend(SUSPEND_REASON_SPIN, 1);
			m_reset_timer->adjust(cycles_to_attotime(512));
		}
	}
	else
	{
		m_regs[0x1b8] |= 0x80;
		m_flags_read[0x1b8] &= ~0x80;
		wdt_schedule();
	}
	recalc_irq();
}
TIMER_CALLBACK_MEMBER(sh7032_device::wdt_pulse)
{
	m_wdt_output = true;
	m_wdtovf(1);
}
TIMER_CALLBACK_MEMBER(sh7032_device::reset_tick)
{
	m_manual_reset = BIT(m_regs[0x1bb], 5);
	reset();
}
void sh7032_device::sleep_enter(unsigned pending_cycles)
{
	if (!(m_regs[0x1bc] & 0x80) || (m_regs[0x1b8] & 0x20))
		return;
	for (unsigned port = 0; port < 2; port++)
	{
		m_standby_ports[port] = port_value(port);
		m_standby_mask[port] = port_output_mask(port);
	}
	for (unsigned ch = 0; ch < 2; ch++)
	{
		m_standby_serial_pads[ch][0] = m_sci[ch].txd_level;
		m_standby_serial_pads[ch][1] = m_sci[ch].sck_level;
		m_standby_serial_pads[ch][2] = m_dack_level[ch];
	}
	m_standby = true;
	reset_modules(true);
	update_ports();
	recalc_irq();
	suspend(SUSPEND_REASON_CLOCK, false);
}
TIMER_CALLBACK_MEMBER(sh7032_device::standby_wake)
{
	m_standby = m_settling = false;
	m_regs[0x1b9] = 0;
	m_wdt_epoch = peripheral_clock();
	resume(SUSPEND_REASON_CLOCK);
	update_ports();
	for (unsigned ch = 0; ch < 2; ch++)
	{
		m_txd[ch](m_sci[ch].txd_level);
		m_sck[ch](m_sci[ch].sck_level);
		m_dack[ch](m_dack_level[ch]);
	}
	sh2_device::execute_set_input(INPUT_LINE_NMI, CLEAR_LINE);
	sh2_device::execute_set_input(INPUT_LINE_NMI, ASSERT_LINE);
}

unsigned sh7032_device::itu_base(unsigned ch) const
{
	static constexpr unsigned base[5] = {0x104, 0x10e, 0x118, 0x122, 0x132};
	return base[ch];
}
void sh7032_device::itu_clear(unsigned ch)
{
	m_itu[ch].counter = 0;
	if (BIT(m_regs[0x101], ch))
		for (unsigned n = 0; n < 5; n++)
			if (n != ch && BIT(m_regs[0x101], n) && ((m_regs[itu_base(n)] >> 5) & 3) == 3)
			{
				m_itu[n].counter = 0;
				m_itu[n].epoch = peripheral_clock();
				itu_schedule(n);
			}
}
void sh7032_device::itu_event(unsigned ch, unsigned events)
{
	unsigned const b = itu_base(ch), clear = (m_regs[b] >> 5) & 3;
	m_regs[b + 3] |= events;
	m_itu[ch].read_flags &= ~events;
	bool const pwm = BIT(m_regs[0x102], ch);
	bool const combined = ch >= 3 && (m_regs[0x103] & 0x20);
	for (unsigned pin = 0; pin < 2; pin++)
		if (events & (1U << pin))
		{
			unsigned const mode = (m_regs[b + 1] >> (pin * 4)) & 7;
			if (combined)
				continue;
			if (pwm)
			{
				if ((events & 3) != 3)
					m_itu[ch].output[0] = pin == 0;
				if (pin == 1)
				{
					unsigned const output = mode & 3;
					if (output == 1)
						m_itu[ch].output[1] = false;
					if (output == 2 || (output == 3 && ch == 2))
						m_itu[ch].output[1] = true;
					if (output == 3 && ch != 2)
						m_itu[ch].output[1] = !m_itu[ch].output[1];
				}
			}
			else if (mode == 1)
				m_itu[ch].output[pin] = false;
			else if (mode == 2 || (mode == 3 && ch == 2))
				m_itu[ch].output[pin] = true;
			else if (mode == 3)
				m_itu[ch].output[pin] = !m_itu[ch].output[pin];
			if (ch >= 3 && BIT(m_regs[0x103], 2 * (ch - 3) + pin) && (pwm || mode < 4))
				word(b + 6 + pin * 2, word(b + 10 + pin * 2));
		}
	if (clear && clear < 3 && (events & (1U << (clear - 1))))
		itu_clear(ch);
	// TPC groups select ITU0-3 A as their pattern trigger; non-overlap clears
	// the current pattern at B and commits NDR at the following A event.
	for (unsigned group = 0; group < 4; group++)
		if (((m_regs[0x1f1] >> (group * 2)) & 3) == ch)
		{
			unsigned const enable = (group < 2 ? m_regs[0x1f3] : m_regs[0x1f2]) >> ((group & 1) * 4);
			unsigned const mask = (enable & 15) << (group * 4);
			unsigned const r = (group < 2 ? 0x1f5 : 0x1f4) + ((!(group & 1) && (((m_regs[0x1f1] >> (2 * (group + 1))) & 3) != ch)) ? 2 : 0);
			unsigned const pattern = (m_regs[r] >> ((group & 1) * 4)) & 15;
			uint16_t dr = word(0x1c2);
			if ((events & 2) && BIT(m_regs[0x1f0], group))
				dr &= ~(mask & ~(pattern << (group * 4)));
			if (events & 1)
				dr = (dr & ~mask) | ((pattern << (group * 4)) & mask);
			word(0x1c2, dr);
		}
	update_ports();
	recalc_irq();
	dma_schedule();
}
void sh7032_device::itu_advance(unsigned ch, uint64_t ticks, bool down)
{
	unsigned const b = itu_base(ch);
	while (ticks)
	{
		unsigned const modea = m_regs[b + 1] & 7, modeb = (m_regs[b + 1] >> 4) & 7;
		bool const pwm = BIT(m_regs[0x102], ch);
		bool const isolated = ch == 4 && ((m_regs[0x103] >> 4) & 3) == 3;
		uint32_t const a = (!isolated && (modea < 4 || pwm)) ? uint16_t(down ? m_itu[ch].counter - word(b + 6) : word(b + 6) - m_itu[ch].counter) + 1U : 0x10001;
		uint32_t const v = (!isolated && (modeb < 4 || pwm)) ? uint16_t(down ? m_itu[ch].counter - word(b + 8) : word(b + 8) - m_itu[ch].counter) + 1U : 0x10001;
		uint32_t const overflow = down ? uint32_t(m_itu[ch].counter) + 1 : 0x10000U - m_itu[ch].counter;
		uint32_t const next = std::min({a, v, overflow});
		if (ticks < next)
		{
			m_itu[ch].counter += down ? -int64_t(ticks) : ticks;
			break;
		}
		m_itu[ch].counter += down ? -int64_t(next) : next;
		ticks -= next;
		bool const simultaneous = pwm && next == a && next == v;
		unsigned const events = (next == a && !simultaneous ? 1 : 0) | (next == v && !simultaneous ? 2 : 0) | ((next == overflow && !(down && ch == 2 && BIT(m_regs[0x102], 5))) ? 4 : 0);
		itu_event(ch, events);
	}
}
void sh7032_device::itu_sync(unsigned ch)
{
	uint64_t const now = peripheral_clock();
	unsigned const b = itu_base(ch), select = m_regs[b] & 7;
	if (m_standby || !BIT(m_regs[0x100], ch) || select >= 4 || (ch == 2 && BIT(m_regs[0x102], 6)))
	{
		m_itu[ch].epoch = now;
		return;
	}
	// Combined 3/4 modes share channel 3's event timer.
	if (ch == 3 && (m_regs[0x103] & 0x20))
		return;
	if (ch == 4 && ((m_regs[0x103] >> 4) & 3) == 2)
		return;
	uint64_t const ticks = (now - m_itu[ch].epoch) >> select;
	m_itu[ch].epoch += ticks << select;
	itu_advance(ch, ticks);
}
void sh7032_device::itu_schedule(unsigned ch)
{
	unsigned const b = itu_base(ch), select = m_regs[b] & 7;
	if (m_standby || !BIT(m_regs[0x100], ch) || select >= 4 || (ch == 2 && BIT(m_regs[0x102], 6)))
	{
		m_itu_timer[ch]->adjust(attotime::never);
		return;
	}
	unsigned const combined = (m_regs[0x103] >> 4) & 3;
	if (ch == 4 && combined == 2)
	{
		m_itu_timer[ch]->adjust(attotime::never);
		return;
	}
	if (ch == 3 && combined >= 2)
	{
		m_itu_timer[ch]->adjust(cycles_to_attotime(1U << select), ch);
		return;
	}
	uint32_t const a = (ch == 4 && combined == 3) ? 0x10001 : ((m_regs[b + 1] & 4) && !BIT(m_regs[0x102], ch)) ? 0x10001
																											   : uint16_t(word(b + 6) - m_itu[ch].counter) + 1U;
	uint32_t const v = (ch == 4 && combined == 3) ? 0x10001 : ((m_regs[b + 1] & 0x40) && !BIT(m_regs[0x102], ch)) ? 0x10001
																												  : uint16_t(word(b + 8) - m_itu[ch].counter) + 1U;
	uint64_t const end = m_itu[ch].epoch + (uint64_t(std::min({a, v, 0x10000U - m_itu[ch].counter})) << select);
	uint64_t const now = peripheral_clock();
	m_itu_timer[ch]->adjust(cycles_to_attotime(end > now ? end - now : 1), ch);
}
void sh7032_device::itu_combined_step()
{
	unsigned const combined = (m_regs[0x103] >> 4) & 3;
	uint16_t const c3 = m_itu[3].counter, c4 = m_itu[4].counter;
	unsigned const b3 = itu_base(3), b4 = itu_base(4);
	if (combined == 3)
	{
		for (unsigned i = 0; i < 3; i++)
		{
			unsigned const gr = i ? word(b4 + 4 + 2 * i) : word(b3 + 8);
			if (c3 == gr)
			{
				if (i == 0)
				{
					m_itu[3].output[0] = !m_itu[3].output[0];
					m_itu[3].output[1] = !m_itu[3].output[0];
				}
				else
					m_itu[4].output[i - 1] = !m_itu[4].output[i - 1];
			}
		}
		m_itu[3].counter++;
		if (c3 == word(b3 + 6))
		{
			m_itu[3].counter = 0;
			itu_event(3, 1);
			m_itu[3].output[0] = !m_itu[3].output[0];
			m_itu[3].output[1] = !m_itu[3].output[0];
			m_itu[4].output[0] = !m_itu[4].output[0];
			m_itu[4].output[1] = !m_itu[4].output[1];
		}
	}
	else
	{
		bool const down = m_itu[3].down;
		for (unsigned i = 0; i < 3; i++)
		{
			unsigned const gr = i ? word(b4 + 4 + 2 * i) : word(b3 + 8);
			// On the leading counter edge turn one side off; only the delayed
			// counter edge can turn its complement on. This preserves dead time.
			if (c3 == gr)
			{
				if (i == 0)
					m_itu[3].output[1] = down;
				else
					m_pwm_negative[i - 1] = down;
			}
			if (c4 == gr)
			{
				if (i == 0)
					m_itu[3].output[0] = !down;
				else
					m_itu[4].output[i - 1] = !down;
			}
		}
		m_itu[3].counter += down ? -1 : 1;
		m_itu[4].counter += down ? -1 : 1;
		if (!down && c3 == word(b3 + 6))
		{
			m_itu[3].down = true;
			itu_event(3, 1);
		}
		if (down && !c4)
		{
			m_itu[3].down = false;
			itu_event(4, 4);
		}
	}
	if (combined == 2)
	{
		if (c3 == word(b3 + 8))
			itu_event(3, 2);
		unsigned const flags = (c4 == word(b4 + 6) ? 1 : 0) | (c4 == word(b4 + 8) ? 2 : 0);
		if (flags)
			itu_event(4, flags);
	}
	bool const transfer = combined == 3 ? (c3 == word(b3 + 6)) : (!m_itu[3].down && !c4) || (m_itu[3].down && c3 == word(b3 + 6));
	if (transfer)
		for (unsigned n = 3; n < 5; n++)
			for (unsigned pin = 0; pin < 2; pin++)
				if (BIT(m_regs[0x103], 2 * (n - 3) + pin))
					word(itu_base(n) + 6 + pin * 2, word(itu_base(n) + 10 + pin * 2));
	update_ports();
	m_itu[3].epoch = peripheral_clock();
	m_itu[4].epoch = m_itu[3].epoch;
}
TIMER_CALLBACK_MEMBER(sh7032_device::itu_tick)
{
	unsigned const ch = param;
	if (ch == 3 && (m_regs[0x103] & 0x20))
		itu_combined_step();
	else
		itu_sync(ch);
	itu_schedule(ch);
}
void sh7032_device::tclk_w(unsigned input, int state)
{
	if (input >= 4 || m_tclk[input] == bool(state))
		return;
	bool const level = !!state;
	m_tclk[input] = level;
	if (m_standby)
		return;
	if (input < 2 && BIT(m_regs[0x102], 6) && BIT(m_regs[0x100], 2))
	{
		bool const down = input == 0 ? (level != m_tclk[1]) : (level == m_tclk[0]);
		itu_advance(2, 1, down);
	}
	for (unsigned ch = 0; ch < 5; ch++)
	{
		unsigned const t = m_regs[itu_base(ch)];
		if (!BIT(m_regs[0x100], ch) || (ch == 2 && BIT(m_regs[0x102], 6)) || (t & 7) != input + 4)
			continue;
		unsigned const edge = (t >> 3) & 3;
		if (edge >= 2 || (edge == 0 && level) || (edge == 1 && !level))
		{
			if (ch == 3 && (m_regs[0x103] & 0x20))
				itu_combined_step();
			else if (ch != 4 || ((m_regs[0x103] >> 4) & 3) != 2)
				itu_advance(ch, 1);
		}
	}
}
void sh7032_device::tioc_w(unsigned ch, unsigned pin, int state)
{
	if (ch >= 5 || pin >= 2)
		return;
	bool const old = m_itu[ch].input[pin], level = !!state;
	m_itu[ch].input[pin] = level;
	if (old == level || m_standby || BIT(m_regs[0x102], ch))
		return;
	unsigned const b = itu_base(ch), mode = (m_regs[b + 1] >> (4 * pin)) & 7;
	if (mode < 4 || !((mode >= 6) || (mode == 4 && level) || (mode == 5 && !level)))
		return;
	itu_sync(ch);
	if (ch >= 3 && BIT(m_regs[0x103], 2 * (ch - 3) + pin))
		word(b + 10 + 2 * pin, word(b + 6 + 2 * pin));
	word(b + 6 + 2 * pin, m_itu[ch].counter);
	itu_event(ch, 1U << pin);
	itu_schedule(ch);
}

unsigned sh7032_device::irq_priority(unsigned vector) const
{
	if (vector < 72)
		return (word(0x184 + 2 * ((vector - 64) / 4)) >> (12 - 4 * ((vector - 64) % 4))) & 15;
	static constexpr unsigned base[12] = {72, 76, 80, 84, 88, 92, 96, 100, 104, 108, 112, 116};
	unsigned group = 0;
	while (group < 11 && vector >= base[group + 1])
		group++;
	return (word(0x188 + 2 * (group / 4)) >> (12 - 4 * (group % 4))) & 15;
}
bool sh7032_device::irq_requested(unsigned vector) const
{
	if (vector < 72)
	{
		unsigned const irq = vector - 64;
		return BIT(word(0x18e), 7 - irq) ? BIT(m_irq_latched, irq) : BIT(m_irq_input, irq);
	}
	if (vector == 72 || vector == 74 || vector == 76 || vector == 78)
		return (word(0x14e + 16 * ((vector - 72) / 2)) & 6) == 6;
	if (vector >= 80 && vector <= 98)
	{
		unsigned const ch = (vector - 80) / 4, pin = (vector - 80) % 4;
		return pin < 3 && (m_regs[itu_base(ch) + 2] & m_regs[itu_base(ch) + 3] & (1U << pin));
	}
	if (vector >= 100 && vector <= 107)
	{
		auto const &s = m_sci[(vector - 100) / 4];
		switch ((vector - 100) % 4)
		{
		case 0:
			return (s.scr & 0x40) && (s.ssr & 0x38);
		case 1:
			return (s.scr & s.ssr & 0x40);
		case 2:
			return (s.scr & s.ssr & 0x80);
		case 3:
			return (s.scr & 4) && (s.ssr & 4);
		}
	}
	if (vector == 109)
		return (m_regs[0xe8] & 0xc0) == 0xc0;
	if (vector == 112)
		return (m_regs[0x1b8] & 0xc0) == 0x80;
	if (vector == 113)
		return (m_regs[0x1af] & 0xc0) == 0xc0;
	return false;
}
void sh7032_device::recalc_irq()
{
	unsigned best = 0, vector = 0;
	if (!m_standby)
		for (unsigned v = 64; v <= 113; v++)
			if (irq_requested(v))
			{
				unsigned const level = irq_priority(v);
				if (level > best)
				{
					best = level;
					vector = v;
				}
			}
	m_sh2_state->internal_irq_level = best ? int(best) : -1;
	m_internal_irq_vector = vector;
	m_test_irq = 1;
}
void sh7032_device::sh2_exception(const char *message, int level)
{
	if (m_standby)
		return;
	if (level != 16 && level <= ((m_sh2_state->sr >> 4) & 15))
		return;
	unsigned const v = level == 16 ? 11 : m_internal_irq_vector;
	if (v >= 64 && v < 72)
	{
		m_irq_latched &= ~(1U << (v - 64));
		standard_irq_callback(v - 64, m_sh2_state->pc);
	}
	sh2_exception_internal(message, level, v);
	recalc_irq();
}
void sh7032_device::execute_set_input(int line, int state)
{
	if (line == INPUT_LINE_NMI)
	{
		bool const level = state != ASSERT_LINE, old = m_nmi_pin;
		m_nmi_pin = level;
		bool const edge = BIT(word(0x18e), 8) ? (!old && level) : (old && !level);
		if (!edge)
			return;
		word(0x148, word(0x148) | 2);
		m_flags_read[0x149] &= ~2;
		if (m_standby)
		{
			if (!m_settling)
			{
				m_settling = true;
				m_wdt_epoch = peripheral_clock();
				m_standby_timer->adjust(cycles_to_attotime(uint64_t(256 - m_regs[0x1b9]) * wdt_divider()));
			}
		}
		else
		{
			sh2_device::execute_set_input(INPUT_LINE_NMI, CLEAR_LINE);
			sh2_device::execute_set_input(INPUT_LINE_NMI, ASSERT_LINE);
		}
		return;
	}
	if (line < 0 || line >= 8)
		return;
	bool const asserted = state != CLEAR_LINE, old = BIT(m_irq_input, line);
	if (asserted && !old)
		m_irq_latched |= 1U << line;
	m_irq_input = (m_irq_input & ~(1U << line)) | (asserted ? (1U << line) : 0);
	recalc_irq();
}

unsigned sh7032_device::pin_function(unsigned port, unsigned bit) const
{
	return (word((port ? 0x1cc : 0x1c8) + (bit < 8 ? 2 : 0)) >> (2 * (bit & 7))) & 3;
}
uint16_t sh7032_device::port_value(unsigned port)
{
	uint16_t const input = m_port_read[port].isunset() ? m_port_input[port] : m_port_read[port]();
	if (port == 2)
		return input & 0xff;
	uint16_t const direction = word(0x1c4 + 2 * port), data = word(0x1c0 + 2 * port);
	uint16_t result = (data & direction) | (input & ~direction);
	if (m_standby)
		return BIT(m_regs[0x1bc], 6) ? input : m_standby_ports[port];
	for (unsigned bit = 0; bit < 16; bit++)
	{
		unsigned const function = pin_function(port, bit);
		bool value = BIT(result, bit);
		if (port == 0 && function == 3 && (bit == 12 || bit == 14))
		{
			unsigned const ch = bit == 14;
			value = m_dack_level[ch];
		}
		if (function == 2 && (direction & (1U << bit)))
		{
			if (port == 0 && (bit == 0 || bit == 2 || bit == 10 || bit == 11))
				value = m_itu[bit >= 10].output[(bit == 2 || bit == 11)];
			if (port == 1 && bit < 6)
				value = m_itu[2 + bit / 2].output[bit & 1];
			if (port == 1 && (bit == 6 || bit == 7))
				value = ((m_regs[0x103] >> 4) & 3) == 3 ? !m_itu[4].output[bit - 6] : m_pwm_negative[bit - 6];
			if (port == 1 && (bit == 12 || bit == 13))
				value = m_sci[bit - 12].sck_level;
			if (port == 1 && bit >= 2 && bit <= 7 && (m_regs[0x103] & 0x20))
			{
				bool const negative = bit == 3 || bit == 6 || bit == 7;
				if (!BIT(m_regs[0x131], negative ? 0 : 1))
					value = !value;
			}
		}
		if (port == 1 && function == 2 && (bit == 9 || bit == 11))
			value = m_sci[bit == 11].txd_level;
		if (port == 0 && function == 3 && bit == 9)
			value = m_sh2_state->internal_irq_level < 0;
		result = (result & ~(1U << bit)) | (value ? (1U << bit) : 0);
	}
	return result;
}
uint16_t sh7032_device::port_output_mask(unsigned port) const
{
	uint16_t result = word(0x1c4 + 2 * port);
	for (unsigned bit = 0; bit < 16; bit++)
	{
		unsigned const function = pin_function(port, bit);
		if (!function)
			continue;
		bool output = BIT(result, bit);
		if (port == 0)
		{
			if (function == 1)
				output = bit < 8 || bit == 9;
			if (function == 2 && bit == 1)
				output = true;
			if (function == 2 && (bit == 3 || bit == 9 || bit >= 12))
				output = false;
			if (function == 3)
				output = bit == 9 || bit == 12 || bit == 14;
		}
		else
		{
			if (function == 1)
				output = bit == 9;
			if (function == 2 && (bit == 8 || bit == 10))
				output = false;
			if (function == 2 && (bit == 6 || bit == 7 || bit == 9 || bit == 11))
				output = true;
		}
		result = (result & ~(1U << bit)) | (output ? (1U << bit) : 0);
	}
	return result;
}
void sh7032_device::update_ports()
{
	for (unsigned port = 0; port < 2; port++)
	{
		uint16_t const mask = m_standby ? (BIT(m_regs[0x1bc], 6) ? 0 : m_standby_mask[port]) : port_output_mask(port);
		m_port_write[port](0, port_value(port), mask);
	}
}
void sh7032_device::route_port(unsigned port, uint16_t old, uint16_t value)
{
	if (port >= 2)
		return;
	for (unsigned bit = 0; bit < 16; bit++)
	{
		unsigned const function = pin_function(port, bit);
		int const level = BIT(value, bit);
		// Re-evaluate selected functions after a PFC change even if the pad did not change.
		if (port == 0)
		{
			if (bit >= 12 && function == 1)
				execute_set_input(bit - 12, level ? CLEAR_LINE : ASSERT_LINE);
			if (function == 3 && (bit == 13 || bit == 15))
				dreq_w(bit == 15, level);
			if (function == 2 && (bit == 12 || bit == 13))
				tclk_w(bit - 12, level);
			if (function == 2 && bit == 9)
				adtrg_w(level);
			if (function == 2 && bit == 3)
				wait_w(level);
			if (function == 2 && (bit == 0 || bit == 2 || bit == 10 || bit == 11) && !BIT(word(0x1c4), bit))
				tioc_w(bit >= 10, bit == 2 || bit == 11, level);
		}
		else
		{
			if (function == 1 && bit >= 12)
				execute_set_input(bit - 8, level ? CLEAR_LINE : ASSERT_LINE);
			if (function == 1 && (bit == 6 || bit == 7))
				tclk_w(bit - 4, level);
			if (function == 2 && (bit == 8 || bit == 10))
				sci_rxd_w(bit == 10, level);
			if (function == 2 && (bit == 12 || bit == 13) && !BIT(word(0x1c6), bit))
				sci_sck_w(bit - 12, level);
			if (function == 2 && bit < 6 && !BIT(word(0x1c6), bit))
				tioc_w(2 + bit / 2, bit & 1, level);
		}
	}
}
void sh7032_device::port_w(unsigned port, uint16_t data)
{
	if (port >= 3)
		return;
	uint16_t const old = m_port_input[port];
	m_port_input[port] = data;
	route_port(port, old, data);
}

uint16_t sh7032_device::peripheral_r(offs_t offset, uint16_t mask)
{
	unsigned const a = offset * 2;
	if (a == 0x1b8 || a == 0x1ba)
	{ // WDT read instructions must be byte accesses.
		if (mask == 0xffff)
			return 0xffff;
	}
	uint16_t result = 0xffff;
	if (mask & 0xff00)
		result = (result & 0xff) | (uint16_t(reg_r(a)) << 8);
	if (mask & 0xff)
		result = (result & 0xff00) | reg_r(a + 1);
	return result;
}
void sh7032_device::peripheral_w(offs_t offset, uint16_t data, uint16_t mask)
{
	unsigned const a = offset * 2;
	if (a == 0x1b8 || a == 0x1ba)
	{
		wdt_write(a, data, mask);
		return;
	}
	// SAR/DAR/TCR require word/longword accesses; CHCR permits byte access.
	if (a >= 0x140 && a < 0x180 && (a & 15) < 12 && a != 0x148 && mask != 0xffff)
		return;
	if (mask & 0xff00)
		reg_w(a, data >> 8);
	if (mask & 0xff)
		reg_w(a + 1, data);
}
uint8_t sh7032_device::reg_r(unsigned a)
{
	if ((a >= 0xc0 && a <= 0xc5) || (a >= 0xc8 && a <= 0xcd))
	{
		unsigned const ch = a >= 0xc8;
		switch (a & 7)
		{
		case 0:
			return smr_r(ch);
		case 1:
			return brr_r(ch);
		case 2:
			return scr_r(ch);
		case 3:
			return tdr_r(ch);
		case 4:
			return ssr_r(ch);
		case 5:
			return rdr_r(ch);
		}
	}
	if (a >= 0xe0 && a < 0xe8)
	{
		if (!(a & 1))
		{
			if (!machine().side_effects_disabled())
				m_adc_temp = m_regs[a + 1];
			return m_regs[a];
		}
		if (m_dma_access >= 0)
		{
			m_regs[0xe8] &= ~0x80;
			recalc_irq();
			return m_regs[a];
		}
		return m_adc_temp;
	}
	if (a == 0xe8)
	{
		if (!machine().side_effects_disabled())
			m_flags_read[a] = m_regs[a] & 0x80;
		return m_regs[a];
	}
	if (a >= 0x100 && a < 0x140)
	{
		for (unsigned ch = 0; ch < 5; ch++)
		{
			unsigned const b = itu_base(ch), end = b + (ch >= 3 ? 14 : 10);
			if (a >= b && a < end)
			{
				itu_sync(ch);
				if (a == b + 3 && !machine().side_effects_disabled())
					m_itu[ch].read_flags = m_regs[a] & 7;
				if (a == b + 4 || a == b + 5)
					return a == b + 4 ? m_itu[ch].counter >> 8 : m_itu[ch].counter;
				return m_regs[a];
			}
		}
		if (a <= 0x103 || a == 0x131)
			return m_regs[a];
		return 0xff;
	}
	if (a >= 0x140 && a < 0x180)
	{
		unsigned const low = a & 15;
		if (a == 0x148 || a == 0x149)
		{
			if (!machine().side_effects_disabled() && a == 0x149)
				m_flags_read[a] = m_regs[a] & 6;
			return m_regs[a];
		}
		if (low == 8 || low == 9 || low == 12 || low == 13)
			return 0;
		if (low == 15 && !machine().side_effects_disabled())
			m_flags_read[a] = m_regs[a] & 2;
		return m_regs[a];
	}
	if (a == 0x18e)
		return (m_regs[a] & 1) | (m_nmi_pin ? 0x80 : 0);
	if (a == 0x1b8 || a == 0x1b9)
	{
		wdt_sync();
		if (a == 0x1b8 && !machine().side_effects_disabled())
			m_flags_read[a] = m_regs[a] & 0x80;
		return m_regs[a];
	}
	if (a == 0x1bb)
	{
		if (!machine().side_effects_disabled())
			m_flags_read[a] = m_regs[a] & 0x80;
		return m_regs[a];
	}
	if (a >= 0x1c0 && a <= 0x1c3)
	{
		uint16_t const v = port_value((a - 0x1c0) / 2);
		return (a & 1) ? v : v >> 8;
	}
	if (a == 0x1d0)
		return 0xff;
	if (a == 0x1d1)
		return port_value(2);
	if ((a >= 0x184 && a <= 0x199) || (a >= 0x1a0 && a <= 0x1b3) || a == 0x1bc ||
		(a >= 0x1c4 && a <= 0x1cf) || a == 0x1ee || a == 0x1ef || (a >= 0x1f0 && a <= 0x1f7))
		return m_regs[a];
	return 0xff;
}
void sh7032_device::reg_w(unsigned a, uint8_t data)
{
	if ((a >= 0xc0 && a <= 0xc5) || (a >= 0xc8 && a <= 0xcd))
	{
		unsigned const ch = a >= 0xc8;
		switch (a & 7)
		{
		case 0:
			smr_w(ch, data);
			break;
		case 1:
			brr_w(ch, data);
			break;
		case 2:
			scr_w(ch, data);
			break;
		case 3:
			tdr_w(ch, data);
			break;
		case 4:
			ssr_w(ch, data);
			break;
		}
		return;
	}
	if (a == 0xe8)
	{
		bool const running = m_regs[a] & 0x20;
		m_regs[a] = (m_regs[a] & 0x80 & ~(m_flags_read[a] & ~data)) | (data & 0x7f);
		m_flags_read[a] = 0;
		if (!running && (data & 0x20))
			adc_start();
		if (!(data & 0x20))
			m_adc_timer->adjust(attotime::never);
		recalc_irq();
		dma_schedule();
		return;
	}
	if (a == 0xe9)
	{
		m_regs[a] = data | 0x7f;
		return;
	}
	if (a >= 0x100 && a < 0x140)
	{
		uint8_t const old_start = m_regs[0x100];
		uint8_t const old_control = m_regs[a];
		for (unsigned ch = 0; ch < 5; ch++)
			itu_sync(ch);
		bool defined = a <= 0x103 || a == 0x131;
		for (unsigned ch = 0; ch < 5; ch++)
		{
			unsigned const b = itu_base(ch);
			if (a < b || a >= b + (ch >= 3 ? 14 : 10))
				continue;
			defined = true;
			if (a == b + 3)
			{
				m_regs[a] &= ~(m_itu[ch].read_flags & ~data);
				m_itu[ch].read_flags = 0;
				break;
			}
			if (a == b + 4 || a == b + 5)
			{
				uint16_t const c = (a & 1) ? (m_itu[ch].counter & 0xff00) | data : (m_itu[ch].counter & 0xff) | (uint16_t(data) << 8);
				m_itu[ch].counter = c;
				if (BIT(m_regs[0x101], ch))
					for (unsigned n = 0; n < 5; n++)
						if (BIT(m_regs[0x101], n))
							m_itu[n].counter = c;
			}
			if (a == b)
				data &= 0x7f;
			if (a == b + 1)
				data = (data & 0x77) | 8;
			if (a == b + 2)
				data = (data & 7) | 0x78;
		}
		if (!defined)
			return;
		if (a == 0x100 || a == 0x101)
			data = (data & 0x1f) | 0x60;
		if (a == 0x102)
			data &= 0x7f;
		if (a == 0x103)
			data = (data & 0x3f) | 0x40;
		if (a == 0x131)
			data = (data & 3) | 0x7c;
		bool const status = (a == 0x107 || a == 0x111 || a == 0x11b || a == 0x125 || a == 0x135);
		if (!status)
			m_regs[a] = data;
		for (unsigned ch = 0; ch < 5; ch++)
		{
			if ((a == 0x100 && BIT(old_start ^ data, ch)) || (a == itu_base(ch) && ((old_control ^ data) & 7)))
				m_itu[ch].epoch = peripheral_clock();
			itu_schedule(ch);
		}
		update_ports();
		recalc_irq();
		dma_schedule();
		return;
	}
	if (a >= 0x140 && a < 0x180)
	{
		unsigned const low = a & 15;
		if (a == 0x148)
		{
			m_regs[a] = data & 3;
			if ((data & 3) == 3)
			{
				m_dma_order[0] = 3;
				m_dma_order[1] = 2;
				m_dma_order[2] = 1;
				m_dma_order[3] = 0;
			}
		}
		else if (a == 0x149)
		{
			m_regs[a] = (m_regs[a] & 6 & ~(m_flags_read[a] & ~data)) | (data & 1);
			m_flags_read[a] = 0;
		}
		else if (low == 8 || low == 9 || low == 12 || low == 13)
			return;
		else if (low == 15)
		{
			bool const active = (a < 0x160) && (m_dack_level[(a - 0x140) / 16] != BIT(m_regs[a], 6));
			m_regs[a] = (m_regs[a] & 2 & ~(m_flags_read[a] & ~data)) | (data & 0xfd);
			m_flags_read[a] = 0;
			unsigned const ch = (a - 0x140) / 16;
			if (!(data & 1))
				m_dma_burst[ch] = false;
			if (ch < 2)
				dma_ack(ch, active);
		}
		else
			m_regs[a] = data;
		recalc_irq();
		dma_schedule();
		return;
	}
	if (a >= 0x184 && a <= 0x18d)
	{
		m_regs[a] = (a == 0x18d) ? data & 0xf0 : data;
		recalc_irq();
		return;
	}
	if (a == 0x18e || a == 0x18f)
	{
		m_regs[a] = a == 0x18e ? data & 1 : data;
		recalc_irq();
		return;
	}
	if (a >= 0x190 && a <= 0x199)
	{
		m_regs[a] = a == 0x198 ? 0 : data;
		return;
	}
	if (a >= 0x1a0 && a <= 0x1b3)
	{
		static constexpr uint16_t mask[10] = {0xf800, 0xff02, 0xffff, 0xf800, 0xff00, 0xf800, 0x00f0, 0x00f8, 0x00ff, 0x00ff};
		unsigned const i = (a - 0x1a0) / 2;
		if (i >= 10)
			return;
		unsigned const valid = (a & 1) ? mask[i] : mask[i] >> 8;
		m_regs[a] = (m_regs[a] & ~valid) | (data & valid);
		return;
	}
	if (a == 0x1bc)
	{
		if (!(m_regs[0x1b8] & 0x20))
			m_regs[a] = (data & 0xc0) | 0x1f;
		return;
	}
	if ((a >= 0x1c0 && a <= 0x1cf) || a == 0x1ee || a == 0x1ef)
	{
		m_regs[a] = data;
		if (a == 0x1c9)
			m_regs[a] |= 2;
		if (a == 0x1ca)
			m_regs[a] |= 0xaa;
		if (a == 0x1c6)
			m_regs[a] |= 0;
		if (a == 0x1ee)
			m_regs[a] = (data & 0xf0) | 0x0f;
		if (a == 0x1ef)
			m_regs[a] = 0xff;
		route_port(0, m_port_input[0], m_port_input[0]);
		route_port(1, m_port_input[1], m_port_input[1]);
		update_ports();
		return;
	}
	if (a >= 0x1f0 && a <= 0x1f7)
	{
		if (a == 0x1f0)
			m_regs[a] = (data & 15) | 0xf0;
		else if (a >= 0x1f4)
		{
			bool const upper = (a & 1) == 0;
			unsigned const shift = upper ? 4 : 0;
			bool const paired = ((m_regs[0x1f1] >> shift) & 3) == ((m_regs[0x1f1] >> (shift + 2)) & 3);
			if (a < 0x1f6)
				m_regs[a] = paired ? data : (data & 0xf0) | 0x0f;
			else if (!paired)
				m_regs[a] = (data & 15) | 0xf0;
		}
		else
			m_regs[a] = data;
		return;
	}
}

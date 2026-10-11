// license:BSD-3-Clause
// Actual SH-1 device diagnostic machine; selected explicitly by test builds.
#include "emu.h"
#include "cpu/sh/sh7032.h"

namespace
{
class sh1diag_state : public driver_device
{
  public:
	sh1diag_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag), m_cpu(*this, "maincpu") {}
	void config(machine_config &config);

  private:
	required_device<sh7032_device> m_cpu;
	uint32_t m_ack_count[2]{}, m_ack_level[2]{}, m_fifo_write_count[2]{}, m_fifo_write[2]{};
	uint16_t m_fifo_read[2]{0x1234, 0xabcd}, m_analog[8]{};
	uint16_t m_ports[2]{};
	bool m_loop = false;
	uint16_t m_trace[64]{};
	uint32_t m_trace_count = 0;
	void map(address_map &map);
	uint32_t fixture_r(offs_t offset);
	void fixture_w(offs_t offset, uint32_t data, uint32_t mask = ~0);
	template <unsigned N>
	void ack(int state)
	{
		if (state != m_ack_level[N])
			m_ack_count[N]++;
		m_ack_level[N] = state;
	}
	template <unsigned N>
	uint16_t fifo_r()
	{
		return m_fifo_read[N]++;
	}
	template <unsigned N>
	void fifo_w(uint16_t data)
	{
		m_fifo_write_count[N]++;
		m_fifo_write[N] = data;
	}
	template <unsigned N>
	uint16_t analog_r()
	{
		return m_analog[N];
	}
	template <unsigned N>
	void port_w(uint16_t data)
	{
		m_ports[N] = data;
	}
	void txd_w(int state)
	{
		if (m_loop)
			m_cpu->sci_rxd_w(1, state);
	}
	void sck_w(int state)
	{
		if (m_loop)
			m_cpu->sci_sck_w(1, state);
	}
	void machine_start() override;
};
void sh1diag_state::machine_start()
{
	save_item(NAME(m_ack_count));
	save_item(NAME(m_ack_level));
	save_item(NAME(m_fifo_write_count));
	save_item(NAME(m_fifo_write));
	save_item(NAME(m_fifo_read));
	save_item(NAME(m_analog));
	save_item(NAME(m_ports));
	save_item(NAME(m_loop));
	save_item(NAME(m_trace));
	save_item(NAME(m_trace_count));
}
void sh1diag_state::map(address_map &map)
{
	map(0, 0xffff).rom().region("maincpu", 0);
	map(0x01000000, 0x01000fff).mirror(0x08000000).ram();
	map(0x0a000000, 0x0a0003ff).rw(FUNC(sh1diag_state::fixture_r), FUNC(sh1diag_state::fixture_w));
}
uint32_t sh1diag_state::fixture_r(offs_t offset)
{
	if (offset == 32)
		return m_trace_count;
	if (offset >= 33 && offset < 97)
		return m_trace[offset - 33];
	if (offset < 2)
		return m_ack_count[offset];
	if (offset < 4)
		return m_ack_level[offset - 2];
	if (offset < 6)
		return m_fifo_write_count[offset - 4];
	if (offset < 8)
		return m_fifo_write[offset - 6];
	if (offset < 10)
		return m_ports[offset - 8];
	return 0;
}
void sh1diag_state::fixture_w(offs_t offset, uint32_t data, uint32_t mask)
{
	if (offset == 32)
	{
		if (m_trace_count < 64)
			m_trace[m_trace_count++] = (mask & 0xffff0000) ? data >> 16 : data;
		return;
	}
	if (offset == 33)
	{
		m_trace_count = 0;
		return;
	}
	if (offset < 2)
	{
		m_cpu->dreq_w(offset, data & 1);
		return;
	}
	if (offset == 2)
	{
		m_loop = data & 1;
		return;
	}
	if (offset >= 8 && offset < 16)
	{
		m_analog[offset - 8] = data & 0x3ff;
		return;
	}
	if (offset == 16)
	{
		m_cpu->adtrg_w(data & 1);
		return;
	}
	if (offset >= 17 && offset < 21)
	{
		m_cpu->tclk_w(offset - 17, data & 1);
		return;
	}
	if (offset >= 21 && offset < 31)
	{
		m_cpu->tioc_w((offset - 21) / 2, (offset - 21) & 1, data & 1);
		return;
	}
	if (offset == 31)
	{
		m_cpu->set_input_line(INPUT_LINE_NMI, data ? ASSERT_LINE : CLEAR_LINE);
		return;
	}
}
void sh1diag_state::config(machine_config &config)
{
	SH7032(config, m_cpu, 16000000);
	m_cpu->set_addrmap(AS_PROGRAM, &sh1diag_state::map);
	m_cpu->txd_callback<0>().set(FUNC(sh1diag_state::txd_w));
	m_cpu->sck_callback<0>().set(FUNC(sh1diag_state::sck_w));
	m_cpu->dack_callback<0>().set(FUNC(sh1diag_state::ack<0>));
	m_cpu->dack_callback<1>().set(FUNC(sh1diag_state::ack<1>));
	m_cpu->dma_read_callback<0>().set(FUNC(sh1diag_state::fifo_r<0>));
	m_cpu->dma_read_callback<1>().set(FUNC(sh1diag_state::fifo_r<1>));
	m_cpu->dma_write_callback<0>().set(FUNC(sh1diag_state::fifo_w<0>));
	m_cpu->dma_write_callback<1>().set(FUNC(sh1diag_state::fifo_w<1>));
	m_cpu->port_write_callback<0>().set(FUNC(sh1diag_state::port_w<0>));
	m_cpu->port_write_callback<1>().set(FUNC(sh1diag_state::port_w<1>));
	m_cpu->analog_callback<0>().set(FUNC(sh1diag_state::analog_r<0>));
	m_cpu->analog_callback<1>().set(FUNC(sh1diag_state::analog_r<1>));
	m_cpu->analog_callback<2>().set(FUNC(sh1diag_state::analog_r<2>));
	m_cpu->analog_callback<3>().set(FUNC(sh1diag_state::analog_r<3>));
	m_cpu->analog_callback<4>().set(FUNC(sh1diag_state::analog_r<4>));
	m_cpu->analog_callback<5>().set(FUNC(sh1diag_state::analog_r<5>));
	m_cpu->analog_callback<6>().set(FUNC(sh1diag_state::analog_r<6>));
	m_cpu->analog_callback<7>().set(FUNC(sh1diag_state::analog_r<7>));
}
static INPUT_PORTS_START(sh1diag)
	INPUT_PORTS_END
	ROM_START(sh1diag)
		ROM_REGION(0x10000, "maincpu", 0)
			ROM_LOAD("diagnostic.bin", 0, 0x10000, CRC(00000000) SHA1(0000000000000000000000000000000000000000))
				ROM_END
} // namespace
SYST(2026, sh1diag, 0, 0, config, sh1diag, sh1diag_state, empty_init, "MAME diagnostic", "SH7032 peripheral diagnostic", MACHINE_NO_SOUND_HW | MACHINE_SUPPORTS_SAVE)

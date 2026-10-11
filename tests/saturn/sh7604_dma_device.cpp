// license:BSD-3-Clause
// Explicit diagnostic machine for SH7604 external pins, data ports and bus order.
#include "emu.h"
#include "cpu/sh/sh7604.h"
namespace {
class sh2dmadiag_state : public driver_device
{
public:
	sh2dmadiag_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag), m_cpu(*this, "maincpu") { }
	void config(machine_config &config);
private:
	required_device<sh7604_device> m_cpu;
	uint32_t m_ram[0x8000]{}, m_trace[512][4]{}, m_count = 0;
	uint32_t m_wait[2]{11, 7}, m_fifo[2]{0x100, 0x200}, m_reads[2]{}, m_writes[2]{}, m_last[2]{};
	int m_ack[2]{1, 1}, m_high[2]{};
	uint32_t m_drop = 0, m_bad_ack = 0;
	void map(address_map &map);
	void machine_start() override;
	void record(uint32_t type, uint32_t address, uint32_t value)
	{
		if (m_count < 512)
		{
			m_trace[m_count][0] = machine().time().as_ticks(2'000'000);
			m_trace[m_count][1] = type; m_trace[m_count][2] = address; m_trace[m_count][3] = value;
			++m_count;
		}
	}
	uint32_t ram_r(offs_t offset, uint32_t mask)
	{
		record(1, 0x06000000 + offset * 4, m_ram[offset]);
		return m_ram[offset];
	}
	void ram_w(offs_t offset, uint32_t data, uint32_t mem_mask)
	{
		COMBINE_DATA(&m_ram[offset]);
		record(2, 0x06000000 + offset * 4, m_ram[offset]);
	}
	template <unsigned Ch> void ack_w(int level)
	{
		if (m_ack[Ch] == level) return;
		m_ack[Ch] = level;
		record(0x10 + Ch, 0, level);
		if (level == m_high[Ch])
		{
			if (m_drop & (1U << Ch))
			{
				m_drop &= ~(1U << Ch);
				m_cpu->dma_request_w(Ch, !BIT(m_cpu->space(AS_PROGRAM).read_dword(0xffffff8c + 16 * Ch), 5));
			}
			if (m_drop & 0x10) { m_drop &= ~0x10; m_cpu->space(AS_PROGRAM).write_dword(0xffffffb0, 0); }
			if (m_drop & 0x20) { m_drop &= ~0x20; m_cpu->set_input_line(INPUT_LINE_NMI, ASSERT_LINE); }
		}
	}
	template <unsigned Ch> uint32_t fifo_r(offs_t offset, uint32_t mask)
	{
		if (m_ack[Ch] != m_high[Ch]) ++m_bad_ack;
		++m_reads[Ch];
		uint32_t const value = m_fifo[Ch]++ & mask;
		record(3 + 2 * Ch, mask, value);
		return value;
	}
	template <unsigned Ch> void fifo_w(offs_t offset, uint32_t data, uint32_t mask)
	{
		if (m_ack[Ch] != m_high[Ch]) ++m_bad_ack;
		++m_writes[Ch]; m_last[Ch] = data & mask;
		record(4 + 2 * Ch, mask, data & mask);
	}
	int bus(offs_t address, unsigned size, bool write, bool fill, attotime now, bool dma)
	{
		return dma ? m_wait[write] : 0;
	}
	uint32_t fixture_r(offs_t offset)
	{
		if (offset >= 0x40 && offset < 0x840) return m_trace[(offset - 0x40) / 4][(offset - 0x40) % 4];
		switch (offset)
		{
		case 0: return m_count;
		case 1: return m_wait[0]; case 2: return m_wait[1];
		case 3: return m_fifo[0]; case 4: return m_fifo[1];
		case 5: return m_reads[0]; case 6: return m_reads[1];
		case 7: return m_writes[0]; case 8: return m_writes[1];
		case 9: return m_last[0]; case 10: return m_last[1];
		case 11: return m_bad_ack;
		default: return 0;
		}
	}
	void fixture_w(offs_t offset, uint32_t data)
	{
		switch (offset)
		{
		case 0: m_count = m_bad_ack = 0; m_reads[0] = m_reads[1] = m_writes[0] = m_writes[1] = 0; break;
		case 1: m_wait[0] = data; break; case 2: m_wait[1] = data; break;
		case 3: m_fifo[0] = data; break; case 4: m_fifo[1] = data; break;
		case 12: m_drop = data; break;
		case 13: m_cpu->dreq0_w(BIT(data, 0)); m_cpu->dreq1_w(BIT(data, 1)); break;
		case 14: m_high[0] = data & 1; break; case 15: m_high[1] = data & 1; break;
		case 16: m_cpu->set_input_line(INPUT_LINE_NMI, CLEAR_LINE); break;
		case 17: m_cpu->set_input_line(INPUT_LINE_HALT, data ? ASSERT_LINE : CLEAR_LINE); break;
		}
	}
};
void sh2dmadiag_state::machine_start()
{
	save_item(NAME(m_ram)); save_item(NAME(m_trace)); save_item(NAME(m_count));
	save_item(NAME(m_wait)); save_item(NAME(m_fifo)); save_item(NAME(m_reads));
	save_item(NAME(m_writes)); save_item(NAME(m_last)); save_item(NAME(m_ack));
	save_item(NAME(m_high)); save_item(NAME(m_drop)); save_item(NAME(m_bad_ack));
}
void sh2dmadiag_state::map(address_map &map)
{
	map(0, 0x1ff).rom().region("maincpu", 0);
	map(0x01000000, 0x010021ff).rw(FUNC(sh2dmadiag_state::fixture_r), FUNC(sh2dmadiag_state::fixture_w));
	map(0x06000000, 0x0601ffff).rw(FUNC(sh2dmadiag_state::ram_r), FUNC(sh2dmadiag_state::ram_w));
}
void sh2dmadiag_state::config(machine_config &config)
{
	SH7604(config, m_cpu, 1'000'000);
	m_cpu->set_addrmap(AS_PROGRAM, &sh2dmadiag_state::map);
	m_cpu->set_bus_timing_callback(FUNC(sh2dmadiag_state::bus));
	m_cpu->dma_ack_handler<0>().set(FUNC(sh2dmadiag_state::ack_w<0>));
	m_cpu->dma_ack_handler<1>().set(FUNC(sh2dmadiag_state::ack_w<1>));
	m_cpu->dma_read_handler<0>().set(FUNC(sh2dmadiag_state::fifo_r<0>));
	m_cpu->dma_read_handler<1>().set(FUNC(sh2dmadiag_state::fifo_r<1>));
	m_cpu->dma_write_handler<0>().set(FUNC(sh2dmadiag_state::fifo_w<0>));
	m_cpu->dma_write_handler<1>().set(FUNC(sh2dmadiag_state::fifo_w<1>));
}
ROM_START(sh2dmadiag)
	ROM_REGION(0x200, "maincpu", 0)
	ROM_LOAD("diagnostic.bin", 0, 0x200, CRC(00000000) SHA1(0000000000000000000000000000000000000000))
ROM_END
} // anonymous namespace
CONS(2026, sh2dmadiag, 0, 0, config, 0, sh2dmadiag_state, empty_init, "Diagnostic", "SH7604 DMA pins and arbitration diagnostic", MACHINE_NO_SOUND | MACHINE_SUPPORTS_SAVE)

// license:BSD-3-Clause
// copyright-holders:David Haywood
#include "emu.h"

#include "saturn_cdb.h"
DEFINE_DEVICE_TYPE(SATURN_CDB, saturn_cdb_device, "satcdb", "Saturn CDB (CD Block)")

saturn_cdb_device::saturn_cdb_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, SATURN_CDB, tag, owner, clock), m_cpu(*this, "cdbcpu"), m_cdrom(*this, finder_base::DUMMY_TAG),
	  m_cdda(*this, finder_base::DUMMY_TAG)
{
}

void saturn_cdb_device::device_start()
{
	if (!m_enabled)
		m_cpu->set_disable();
	save_item(NAME(m_command));
	save_item(NAME(m_response));
	save_item(NAME(m_hirq));
	save_item(NAME(m_hmask));
	save_item(NAME(m_trctl));
	save_item(NAME(m_irql));
	save_item(NAME(m_irqu));
	save_item(NAME(m_maskl));
	save_item(NAME(m_masku));
	save_item(NAME(m_reg1a));
	save_item(NAME(m_host_underflow));
	save_item(NAME(m_host_overflow));
	save_item(NAME(m_fifo));
	save_item(NAME(m_fifo_read));
	save_item(NAME(m_fifo_write));
	save_item(NAME(m_fifo_count));
	save_item(NAME(m_fifo_first));
	save_item(NAME(m_fifo_pending));
	save_item(NAME(m_portb));
	save_item(NAME(m_drive_status));
	save_item(NAME(m_drive_command));
	save_item(NAME(m_link_byte));
	save_item(NAME(m_link_bit));
	save_item(NAME(m_link_rx));
	save_item(NAME(m_txd));
	save_item(NAME(m_sck));
	save_item(NAME(m_link_active));
	save_item(NAME(m_drive_state));
	save_item(NAME(m_after_seek));
	save_item(NAME(m_speed));
	save_item(NAME(m_seek_frames));
	save_item(NAME(m_ring_phase));
	save_item(NAME(m_fad));
	save_item(NAME(m_toc_position));
	save_item(NAME(m_scan_step));
	save_item(NAME(m_tray_open));
	save_item(NAME(m_reading));
	save_item(NAME(m_sector_audio));
	save_item(NAME(m_sector));
	save_item(NAME(m_sector_offset));
	save_item(NAME(m_cd_word));
	m_sector_timer = timer_alloc(FUNC(saturn_cdb_device::sector_word), this);
	m_dreq_timer = timer_alloc(FUNC(saturn_cdb_device::sector_request_clear), this);
	m_frame_timer = timer_alloc(FUNC(saturn_cdb_device::drive_frame), this);
	m_request_timer = timer_alloc(FUNC(saturn_cdb_device::drive_request), this);
	machine().save().register_postload(save_prepost_delegate(FUNC(saturn_cdb_device::restore_lines), this));
}
void saturn_cdb_device::device_reset()
{
	std::fill(std::begin(m_command), std::end(m_command), 0);
	std::fill(std::begin(m_response), std::end(m_response), 0);
	m_host_underflow = m_host_overflow = 0;
	m_hirq = m_hmask = m_trctl = m_irql = m_irqu = m_maskl = m_masku = m_reg1a = 0;
	std::fill(std::begin(m_fifo), std::end(m_fifo), 0);
	m_fifo_read = m_fifo_write = m_fifo_count = 0;
	m_fifo_first = true;
	m_fifo_pending = false;
	m_portb = 0xc50f;
	m_link_byte = m_link_bit = m_link_rx = 0;
	m_txd = m_sck = 1;
	m_link_active = false;
	std::fill(std::begin(m_drive_command), std::end(m_drive_command), 0);
	std::fill(std::begin(m_drive_status), std::end(m_drive_status), 0);
	m_drive_status[0] = 0x83;
	m_frame_timer->adjust(m_enabled ? attotime::from_msec(100) : attotime::never);
	m_request_timer->adjust(attotime::never);
	m_drive_state = 0x12;
	m_after_seek = 0x46;
	m_speed = 2;
	m_seek_frames = m_ring_phase = 0;
	m_fad = 150;
	m_toc_position = 0;
	m_scan_step = 1;
	m_reading = m_sector_audio = false;
	m_sector_offset = 2352;
	m_cd_word = 0;
	std::fill(std::begin(m_sector), std::end(m_sector), 0);
	m_sector_timer->adjust(attotime::never);
	m_dreq_timer->adjust(attotime::never);
	update_irq();
	update_request();
}
void saturn_cdb_device::saturn_cdb_map(address_map &map)
{
	map(0x00000000, 0x0000ffff).rom().region("cdbcpu", 0);
	map(0x01000000, 0x0107ffff).mirror(0x08780000).ram();
	map(0x0a000000, 0x0a00001f).mirror(0x000fffe0).rw(FUNC(saturn_cdb_device::asic_r), FUNC(saturn_cdb_device::asic_w));
	map(0x0a100002, 0x0a100003).lr16(NAME([]() { return 0x006c; }));
	map(0x0e000000, 0x0e000003).lr32(NAME([]() { return 0xffffffffU; }));
}
void saturn_cdb_device::amap(address_map &map)
{
	map(0x18000, 0x18003).rw(FUNC(saturn_cdb_device::host_r), FUNC(saturn_cdb_device::host_w));
	map(0x80000, 0x8003f).mirror(0x18000).rw(FUNC(saturn_cdb_device::host_r), FUNC(saturn_cdb_device::host_w));
}
void saturn_cdb_device::device_add_mconfig(machine_config &config)
{
	SH7032(config, m_cpu, DERIVED_CLOCK(1, 1));
	m_cpu->set_addrmap(AS_PROGRAM, &saturn_cdb_device::saturn_cdb_map);
	m_cpu->dma_read_callback<0>().set([this]() { return m_cd_word; });
	m_cpu->dma_read_callback<1>().set(FUNC(saturn_cdb_device::dma_host_r));
	m_cpu->dma_write_callback<1>().set(FUNC(saturn_cdb_device::dma_host_w));
	m_cpu->port_read_callback<1>().set(FUNC(saturn_cdb_device::portb_r));
	m_cpu->port_read_callback<2>().set_constant(0);
	m_cpu->txd_callback<0>().set(FUNC(saturn_cdb_device::txd_w));
	m_cpu->sck_callback<0>().set(FUNC(saturn_cdb_device::sck_w));
}
void saturn_cdb_device::restore_lines()
{
	update_irq();
	update_request();
}

void saturn_cdb_device::update_irq()
{
	m_cpu->set_input_line(6, (m_irql & m_maskl) ? ASSERT_LINE : CLEAR_LINE);
	m_cpu->set_input_line(7, (m_irqu & m_masku) ? ASSERT_LINE : CLEAR_LINE);
}
bool saturn_cdb_device::host_bus_ready(u32 address, unsigned size, bool write) const
{
	u32 const a = address & 0x07ffffff;
	bool const fifo = (a >= 0x05818000 && a <= 0x05818003) || (a >= 0x05880000 && a <= 0x0589803f && (a & 0x7ffc) == 0);
	if (!fifo)
		return true;
	unsigned const words = (size + 1) / 2;
	return (write == bool(m_trctl & 1)) && (write ? m_fifo_count + words <= 6 : m_fifo_count >= words);
}

void saturn_cdb_device::update_request()
{
	if (m_host_wait_cb)
		m_host_wait_cb(m_enabled && (m_fifo_pending || m_fifo_count || (!(m_trctl & 8) && (m_trctl & 5))));
	if (m_host_notify_cb)
		m_host_notify_cb();
	bool request = false;
	if (m_trctl & 1)
		request = (m_fifo_count >= 4);
	else if (m_trctl & 4)
		request = (m_fifo_count < (m_fifo_first ? 4 : 2));
	m_cpu->dreq_w(1, request ? 0 : 1);
}
void saturn_cdb_device::fifo_push(uint16_t data)
{
	if (m_fifo_count == 6)
		return;
	m_fifo[m_fifo_write] = data;
	m_fifo_write = (m_fifo_write + 1) % 6;
	++m_fifo_count;
	if (m_trctl & 1)
		m_trctl &= ~4;
	update_request();
}
uint16_t saturn_cdb_device::fifo_pop(bool raw)
{
	if (!m_fifo_count && !raw)
		return 0xffff;
	uint16_t data = m_fifo[m_fifo_read];
	if (machine().side_effects_disabled())
		return data;
	m_fifo_read = (m_fifo_read + 1) % 6;
	if (m_fifo_count)
		--m_fifo_count;
	if (!m_fifo_count && (m_trctl & 1))
		m_trctl |= 4;
	update_request();
	return data;
}
uint16_t saturn_cdb_device::dma_host_r() { return fifo_pop(); }
void saturn_cdb_device::dma_host_w(uint16_t data)
{
	fifo_push(data);
	if (m_fifo_count >= 4)
		m_fifo_first = false;
	update_request();
}
uint16_t saturn_cdb_device::asic_r(offs_t offset)
{
	switch (offset * 2)
	{
	case 0:
		return fifo_pop(true);
	case 2:
		return m_trctl;
	case 4:
		return m_irql;
	case 6:
		return m_irqu;
	case 8:
		return m_maskl;
	case 10:
		return m_masku;
	case 16:
	case 18:
	case 20:
	case 22:
		return m_command[offset - 8];
	case 24:
		return m_cd_word;
	case 26:
		return m_reg1a;
	case 28:
		return 0x16;
	default:
		return 0;
	}
}
void saturn_cdb_device::asic_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	switch (offset * 2)
	{
	case 0:
		if ((m_trctl & 5) == 4)
			fifo_push(data);
		break;
	case 2:
		COMBINE_DATA(&m_trctl);
		m_trctl &= 15;
		if (m_trctl & 5)
			m_fifo_pending = false;
		if (data & 2)
		{
			m_fifo_read = m_fifo_write = m_fifo_count = 0;
			m_fifo_first = true;
		}
		break;
	case 4:
		m_irql &= data | ~mem_mask;
		break;
	case 6:
		m_irqu &= data | ~mem_mask;
		break;
	case 8:
		COMBINE_DATA(&m_maskl);
		m_maskl &= 3;
		break;
	case 10:
		COMBINE_DATA(&m_masku);
		m_masku &= 0x70;
		break;
	case 16:
	case 18:
	case 20:
	case 22:
		COMBINE_DATA(&m_response[offset - 8]);
		break;
	case 26:
		COMBINE_DATA(&m_reg1a);
		m_reg1a &= 255;
		break;
	case 30:
		m_hirq |= data & mem_mask;
		if ((data & mem_mask & 1) && !(m_response[0] & 0x4000))
			m_fifo_pending = false;
		break;
	default:
		break;
	}
	update_irq();
	update_request();
}
uint16_t saturn_cdb_device::host_r(offs_t offset)
{
	switch ((offset * 2) & 0x3c)
	{
	case 0:
		if (machine().side_effects_disabled())
			return m_fifo_count ? m_fifo[m_fifo_read] : 0xffff;
		if (!m_fifo_count)
			++m_host_underflow;
		return fifo_pop();
	case 4:
		return ((m_trctl & 1) ? 4 : 0) | (m_fifo_count == 6 ? 2 : 0) | (!m_fifo_count ? 1 : 0);
	case 8:
		return m_hirq;
	case 12:
		return m_hmask;
	case 24:
	case 28:
	case 32:
		return m_response[((offset * 2) & 0x3c) / 4 - 6];
	case 36:
		if (!machine().side_effects_disabled())
		{
			m_irql |= 2;
			update_irq();
		}
		return m_response[3];
	default:
		return 0;
	}
}
void saturn_cdb_device::host_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	unsigned const address = (offset * 2) & 0x3c;
	switch (address)
	{
	case 0:
		if (m_fifo_count == 6)
			++m_host_overflow;
		fifo_push(data);
		break;
	case 8:
		m_hirq &= data | ~mem_mask;
		break;
	case 12:
		COMBINE_DATA(&m_hmask);
		break;
	case 24:
	case 28:
	case 32:
	case 36:
		COMBINE_DATA(&m_command[address / 4 - 6]);
		if (address == 36)
		{
			m_fifo_pending = true;
			update_request();
			m_irql = (m_irql | 1) & ~2;
			update_irq();
		}
		break;
	default:
		break;
	}
}
TIMER_CALLBACK_MEMBER(saturn_cdb_device::drive_frame)
{
	if (!m_link_active && (m_cpu->space(AS_PROGRAM).read_byte(0x05fffec2) & 0x30) == 0x30)
	{
		drive_report();
		unsigned sum = 0;
		for (unsigned i = 0; i < 11; i++)
			sum += m_drive_status[i];
		m_drive_status[11] = ~sum;
		m_link_byte = m_link_bit = m_link_rx = 0;
		m_link_active = true;
		m_portb &= ~4;
		m_request_timer->adjust(attotime::from_usec(50));
	}
	m_frame_timer->adjust(attotime::from_hz(75));
}
TIMER_CALLBACK_MEMBER(saturn_cdb_device::drive_request)
{
	m_portb &= ~8;
	m_cpu->tioc_w(3, 1, 0);
}
void saturn_cdb_device::sck_w(int state)
{
	if (state == m_sck)
		return;
	m_sck = state;
	if (!m_link_active)
		return;
	if (!state)
	{
		m_cpu->sci_rxd_w(0, (m_link_byte < 12 ? BIT(m_drive_status[m_link_byte], m_link_bit) : 0));
	}
	else
	{
		m_portb |= 8;
		m_cpu->tioc_w(3, 1, 1);
		m_link_rx |= (m_txd ? 1 : 0) << m_link_bit;
		if (++m_link_bit == 8)
		{
			m_drive_command[m_link_byte] = m_link_rx;
			m_link_rx = m_link_bit = 0;
			m_portb |= 4;
			if (++m_link_byte == 13)
			{
				m_link_active = false;
				drive_command();
			}
			else
				m_request_timer->adjust(attotime::from_usec(50));
		}
	}
}

namespace
{
u8 cdb_q(unsigned value) { return (value << 4) | (value >> 4); }
u8 cdb_bcd(unsigned value) { return ((value / 10) << 4) | (value % 10); }
void cdb_msf(u8 *p, unsigned fad)
{
	p[0] = cdb_bcd(fad / 4500);
	p[1] = cdb_bcd((fad / 75) % 60);
	p[2] = cdb_bcd(fad % 75);
}
} // namespace
void saturn_cdb_device::drive_command()
{
	unsigned sum = 0;
	for (unsigned i = 0; i < 12; i++)
		sum += m_drive_command[i];
	if ((sum & 255) != 255)
		return;
	unsigned const opcode = m_drive_command[0];
	if (!opcode)
		return;
	u32 const fad = (u32(m_drive_command[1]) << 16) | (u32(m_drive_command[2]) << 8) | m_drive_command[3];
	m_speed = m_drive_command[10] == 1 ? 1 : 2;
	if (!m_cdrom || !m_cdrom->exists() || m_tray_open)
		return;
	switch (opcode)
	{
	case 2:
		m_fad = fad;
		m_ring_phase = 4;
		m_drive_state = 0xb2;
		m_reading = false;
		break;
	case 3:
		m_toc_position = 0;
		m_drive_state = 6;
		m_reading = false;
		break;
	case 4:
		m_drive_state = 0x12;
		m_reading = false;
		break;
	case 5:
		set_tray_open();
		break;
	case 6:
		m_fad = fad >= 4 ? fad - 4 : 0;
		m_seek_frames = 2;
		m_drive_state = 0x22;
		m_after_seek = 0x36;
		m_reading = false;
		break;
	case 8:
		m_drive_state = 0x46;
		m_reading = false;
		break;
	case 9:
		m_fad = fad;
		m_seek_frames = 2;
		m_drive_state = 0x22;
		m_after_seek = 0x46;
		m_reading = false;
		break;
	case 10:
	case 11:
		m_scan_step = opcode == 10 ? 20 : -20;
		m_drive_state = 0x36;
		m_reading = true;
		break;
	case 12:
		m_drive_state = 0x12;
		m_reading = false;
		break;
	default:
		break;
	}
	if (!m_reading)
		m_sector_timer->adjust(attotime::never);
	if (m_cdda)
	{
		if (opcode == 4 || opcode == 6 || opcode == 9 || opcode == 12)
			m_cdda->stop_audio();
		else if (!m_reading)
			m_cdda->pause_audio(1);
	}
}
void saturn_cdb_device::drive_report()
{
	std::fill(std::begin(m_drive_status), std::end(m_drive_status), 0);
	if (m_tray_open || !m_cdrom || !m_cdrom->exists())
	{
		m_drive_status[0] = m_tray_open ? 0x80 : 0x83;
		return;
	}
	unsigned const tracks = m_cdrom->get_last_track();
	unsigned const end = m_cdrom->get_track_start(0xaa) + 150;
	unsigned const track = m_cdrom->get_track(m_fad >= 150 ? std::min(m_fad - 150, end - 151) : 0);
	bool const audio = m_cdrom->get_track_type(track) == cdrom_file::CD_TRACK_AUDIO;
	m_drive_status[0] = m_drive_state;
	m_drive_status[1] = cdb_q(m_cdrom->get_adr_control(track));
	m_drive_status[2] = m_fad < end ? cdb_bcd(track + 1) : 0xaa;
	m_drive_status[3] = 1;
	cdb_msf(m_drive_status + 4,
			m_fad >= m_cdrom->get_track_start(track) + 150 ? m_fad - m_cdrom->get_track_start(track) : 150);
	cdb_msf(m_drive_status + 8, m_fad);
	if (m_drive_state == 6)
	{
		m_drive_status[2] = 0;
		if (m_toc_position < tracks)
		{
			m_drive_status[1] = cdb_q(m_cdrom->get_adr_control(m_toc_position));
			m_drive_status[3] = cdb_bcd(m_toc_position + 1);
			cdb_msf(m_drive_status + 8, m_cdrom->get_track_start(m_toc_position) + 150);
		}
		else
		{
			unsigned const n = m_toc_position - tracks;
			m_drive_status[3] = 0xa0 + n;
			m_drive_status[1] = n == 2 ? 1 : cdb_q(m_cdrom->get_adr_control(n == 0 ? 0 : tracks - 1));
			m_drive_status[8] = cdb_bcd(n == 0 ? 1 : tracks);
			m_drive_status[9] = m_drive_status[10] = 0;
			if (n == 2)
				cdb_msf(m_drive_status + 8, end);
		}
		std::fill(m_drive_status + 4, m_drive_status + 8, 0);
		if (++m_toc_position == tracks + 3)
			m_drive_state = 0x46;
	}
	else if (m_ring_phase)
	{
		unsigned const phase = m_ring_phase--;
		std::fill(m_drive_status + 1, m_drive_status + 11, 0);
		m_drive_status[0] = phase > 2 ? 0xb2 : 0xb6;
		m_drive_status[3] = m_fad >> 16;
		m_drive_status[4] = m_fad >> 8;
		m_drive_status[5] = m_fad;
		if (phase <= 2)
		{
			m_drive_status[1] = 0x48;
			m_drive_status[2] = 0x5a;
			m_drive_status[6] = m_drive_status[7] = 10;
			m_drive_status[8] = m_drive_status[9] = 9;
		}
		if (!m_ring_phase)
			m_drive_state = 0x46;
	}
	else if (m_seek_frames)
	{
		if (!--m_seek_frames)
		{
			m_drive_state = m_after_seek;
			m_reading = m_drive_state == 0x36;
			if (m_reading)
			{
				m_sector_offset = 2352;
				m_sector_timer->adjust(attotime::zero);
			}
		}
	}
	else if (m_reading)
	{
		m_drive_status[0] = audio ? 0x34 : 0x36;
	}
}
void saturn_cdb_device::set_tray_open()
{
	m_tray_open = true;
	m_reading = false;
	m_drive_state = 0x80;
	m_sector_timer->adjust(attotime::never);
	if (m_cdda)
		m_cdda->stop_audio();
}
void saturn_cdb_device::set_tray_close()
{
	m_tray_open = false;
	m_drive_state = 0x12;
}
void saturn_cdb_device::load_sector()
{
	bool synthetic = true;
	std::fill(std::begin(m_sector), std::end(m_sector), 0);
	unsigned const end = m_cdrom->get_track_start(0xaa) + 150;
	unsigned const track = m_cdrom->get_track(m_fad >= 150 ? std::min(m_fad - 150, end - 151) : 0);
	m_sector_audio = m_cdrom->get_track_type(track) == cdrom_file::CD_TRACK_AUDIO && m_fad < end;
	if (m_sector_audio)
	{
		m_speed = 1;
		if (m_cdda && !m_cdda->audio_active() && m_fad >= 150)
			m_cdda->start_audio(m_fad - 150, m_cdrom->get_track_start(track + 1) + 150 - m_fad);
		if (m_cdda && m_fad >= 150)
			m_cdda->pause_audio(0);
		return;
	}
	if (m_fad >= end)
	{
		// Security-ring carrier: alternating A8/59 descrambled by the CD-ROM
		// x^15+x+1 scrambler, with the mode-2 form-2 header supplied below.
		u16 lfsr = 1;
		for (unsigned i = 12; i < 2348; i++)
		{
			u8 stream = 0;
			for (unsigned bit = 0; bit < 8; bit++)
			{
				stream |= (lfsr & 1) << bit;
				lfsr = (lfsr >> 1) | (((lfsr ^ (lfsr >> 1)) & 1) << 14);
			}
			m_sector[i] = ((i & 1) ? 0x59 : 0xa8) ^ stream;
		}
		m_sector[15] = 2;
		m_sector[18] = m_sector[22] = 0x28;
		m_sector[16] = m_sector[17] = m_sector[19] = m_sector[20] = m_sector[21] = m_sector[23] = 0;
	}
	else if (m_fad >= 150)
	{
		unsigned const type = m_cdrom->get_track_type(track);
		if (type == cdrom_file::CD_TRACK_MODE1)
		{
			m_cdrom->read_data(m_fad - 150, m_sector + 16, cdrom_file::CD_TRACK_MODE1);
			m_sector[15] = 1;
		}
		else if (type == cdrom_file::CD_TRACK_MODE1_RAW || type == cdrom_file::CD_TRACK_MODE2_RAW)
		{
			synthetic = false;
			m_cdrom->read_data(m_fad - 150, m_sector, cdrom_file::CD_TRACK_RAW_DONTCARE);
		}
		else if (type == cdrom_file::CD_TRACK_MODE2_FORM1 || type == cdrom_file::CD_TRACK_MODE2_FORM2)
		{
			m_sector[15] = 2;
			if (type == cdrom_file::CD_TRACK_MODE2_FORM2)
				m_sector[18] = m_sector[22] = 0x20;
			m_cdrom->read_data(m_fad - 150, m_sector + 24, type);
		}
		else
		{
			m_sector[15] = 2;
			m_cdrom->read_data(m_fad - 150, m_sector + 16, cdrom_file::CD_TRACK_RAW_DONTCARE);
		}
	}
	else
		m_sector[15] = 1;
	if (synthetic)
	{
		std::fill(m_sector + 1, m_sector + 11, 0xff);
		cdb_msf(m_sector + 12, m_fad);
	}
	if (synthetic && (m_sector[15] == 1 || m_sector[15] == 2))
	{
		bool const form2 = m_sector[15] == 2 && (m_sector[18] & 0x20);
		unsigned const begin = m_sector[15] == 1 ? 0 : 16;
		unsigned const edc = m_sector[15] == 1 ? 2064 : form2 ? 2348 : 2072;
		u32 crc = 0;
		for (unsigned i = begin; i < edc; i++)
		{
			crc ^= m_sector[i];
			for (unsigned b = 0; b < 8; b++)
				crc = (crc >> 1) ^ ((crc & 1) ? 0xd8018001U : 0);
		}
		for (unsigned i = 0; i < 4; i++)
			m_sector[edc + i] = crc >> (i * 8);
		if (!form2)
			cdrom_file::ecc_generate(m_sector);
	}
}
TIMER_CALLBACK_MEMBER(saturn_cdb_device::sector_word)
{
	if (!m_reading || m_tray_open || !m_cdrom || !m_cdrom->exists())
		return;
	if (m_sector_offset == 2352)
	{
		load_sector();
		m_sector_offset = 0;
	}
	if (!m_sector_audio)
	{
		m_cd_word = (u16(m_sector[m_sector_offset]) << 8) | m_sector[m_sector_offset + 1];
		if (m_sector_offset == 12)
			m_reg1a |= 0x80;
		if (m_sector_offset == 14)
		{
			m_irqu |= 0x10;
			update_irq();
		}
		if (m_sector_offset >= 12 && (m_reg1a & 0x80))
		{
			m_cpu->dreq_w(0, 0);
			m_dreq_timer->adjust(m_cpu->cycles_to_attotime(3));
		}
	}
	m_sector_offset += 2;
	if (m_sector_offset == 2352)
		m_fad = std::max(0, int(m_fad) + m_scan_step);
	m_sector_timer->adjust(attotime::from_hz(88200 * m_speed));
}
TIMER_CALLBACK_MEMBER(saturn_cdb_device::sector_request_clear) { m_cpu->dreq_w(0, 1); }

ROM_START(satcdb)
ROM_REGION(0x10000, "cdbcpu", 0)
ROM_DEFAULT_BIOS("cdb106")
ROM_SYSTEM_BIOS(0, "cdb106", "Saturn CD Block 1.06")
ROMX_LOAD("cdb106.bin", 0x00000, 0x10000, CRC(3681d3b0) SHA1(b3c20fbe57cd2eb595e9edac86817e5948dccae4),
		  ROM_BIOS(0)) // for YGR019B?
ROM_SYSTEM_BIOS(1, "cdb105", "Saturn CD Block 1.05")
ROMX_LOAD("cdb105.bin", 0x00000, 0x10000, CRC(2a2ced5c) SHA1(eb8393058f324e922c11b43709b64fc6ca94ab86),
		  ROM_BIOS(1)) // for YGR019A?
ROM_SYSTEM_BIOS(2, "ygr022", "Saturn CD Block (YGR022 315-5962)")
ROMX_LOAD("ygr022.bin", 0x00000, 0x10000, CRC(1c8b9f38) SHA1(f4f6c2aac68c352814d396ae41f81f54ad228e68),
		  ROM_BIOS(2)) // combined package?
ROM_END

const tiny_rom_entry *saturn_cdb_device::device_rom_region() const { return ROM_NAME(satcdb); }

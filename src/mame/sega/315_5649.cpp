// license: BSD-3-Clause
// copyright-holders: Dirk Best
/***************************************************************************

    Sega 315-5649

    I/O Controller

***************************************************************************/

#include "emu.h"
#include "315_5649.h"

#define VERBOSE 0
#include "logmacro.h"


//**************************************************************************
//  DEVICE DEFINITIONS
//**************************************************************************

DEFINE_DEVICE_TYPE(SEGA_315_5649, sega_315_5649_device, "315_5649", "Sega 315-5649 I/O Controller")


//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

//-------------------------------------------------
//  sega_315_5649_device - constructor
//-------------------------------------------------

sega_315_5649_device::sega_315_5649_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, SEGA_315_5649, tag, owner, clock),
	m_in_port_cb(*this, 0xff),
	m_out_port_cb(*this),
	m_an_port_cb(*this, 0xff),
	m_serial_rd_cb(*this, 0),
	m_serial_wr_cb(*this),
	m_cnt_cb(*this, 0),
	m_cnt_reset_cb(*this),
	m_port_config(0),
	m_mode(0),
	m_analog_channel(0)
{
	std::fill(std::begin(m_port_value), std::end(m_port_value), 0xff);
	std::fill(std::begin(m_serial_rx_data), std::end(m_serial_rx_data), 0);
	std::fill(std::begin(m_serial_rx_valid), std::end(m_serial_rx_valid), 0);
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void sega_315_5649_device::device_start()
{
	// register for save states
	save_item(NAME(m_port_value));
	save_item(NAME(m_port_config));
	save_item(NAME(m_analog_channel));
	save_item(NAME(m_mode));
	save_item(NAME(m_serial_rx_data));
	save_item(NAME(m_serial_rx_valid));
}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void sega_315_5649_device::device_reset()
{
	// set all ports to input on reset
	m_port_config = 0xff;
	m_mode = 0;
}


//**************************************************************************
//  INTERFACE
//**************************************************************************

uint8_t sega_315_5649_device::read(offs_t offset)
{
	uint8_t data = 0xff;

	switch (offset)
	{
	// port a to g
	case 0x06:
		if (m_mode & 0x80) // port G counter mode - 4x 16bit counters, auto-increments
		{
			data = m_cnt_cb[(m_port_value[6] >> 1) & 3](0) >> (((m_port_value[6] & 1) ^ 1) * 8);
			if (!machine().side_effects_disabled())
				m_port_value[6] = (m_port_value[6] & 0xf8) | ((m_port_value[6] + 1) & 7);
			break;
		}
		[[fallthrough]];
	case 0x00:
	case 0x01:
	case 0x02:
	case 0x03:
	case 0x04:
	case 0x05:
		if (BIT(m_port_config, offset))
			data = m_in_port_cb[offset](0);
		else
			data = m_port_value[offset];
		break;

	// RS-422 channel 1/2 input.  A byte put into the channel locally by
	// loopback takes precedence over whatever the driver's callback reports,
	// and consuming it clears the matching RXxBF status bit.
	case 0x0b:
	case 0x0c:
		{
			int const ch = offset - 0x0b;
			if (m_serial_rx_valid[ch])
			{
				data = m_serial_rx_data[ch];
				if (!machine().side_effects_disabled())
					m_serial_rx_valid[ch] = 0;
			}
			else
			{
				data = m_serial_rd_cb[ch](0);
			}
		}
		break;

	// RS-422 status
	// 7--- ----  RX2IE
	// -6-- ----  RX1IE some I-error ?
	// --5- ----  RX2FE
	// ---4 ----  RX1FE framing error ?
	// ---- 3---  RX2BF
	// ---- -2--  RX1BF 1 = receive buffer full
	// ---- --1-  TX2BF
	// ---- ---0  TX1BF 1 = transmit buffer full
	//
	// Both receive-buffer-full bits read as 1 on a channel that has a byte
	// waiting, which is what loopback (mode bit 4) produces locally.  With no
	// peer wired up the historical "buffers always full" value is kept so the
	// Model 2/3 and ST-V drivers that poll this register see no change; a
	// cabinet link device is what has to drive it for real.  See
	// regtests/saturn/handoff/devices.md, STV-05.
	case 0x0d:
		data = (m_serial_rx_valid[1] ? 0x08 : 0x00)
			| (m_serial_rx_valid[0] ? 0x04 : 0x00);
		if (!(m_mode & 0x10))
			data |= 0x0c;
		break;

	// analog input, auto-increments
	case 0x0f:
		data = m_an_port_cb[m_analog_channel](0);
		if (!machine().side_effects_disabled())
			m_analog_channel = (m_analog_channel + 1) & 0x07;
		break;
	}

	LOG("RD %02x = %02x\n", offset, data);

	return data;
}

void sega_315_5649_device::write(offs_t offset, uint8_t data)
{
	LOG("WR %02x = %02x\n", offset, data);

	switch (offset)
	{
	// port a-g
	case 0x00:
	case 0x01:
	case 0x02:
	case 0x03:
	case 0x04:
	case 0x05:
		m_port_value[offset] = data;
		m_out_port_cb[offset](data);
		break;

	// port G doubles as the counter-mode control: with mode bit 7 set, the four
	// 16-bit counters are read at offset 6 and writing bit 7 low clears them.
	// The reset lines are optional - no current driver wires them, so leaving
	// them unbound keeps Model 2/3 and ST-V behaviour exactly as it was.
	case 0x06:
		m_port_value[offset] = data;
		m_out_port_cb[offset](data);
		if ((m_mode & 0x80) && !(data & 0x80))
		{
			for (int i = 0; i < 4; i++)
				m_cnt_reset_cb[i](ASSERT_LINE);
		}
		break;

	// port direction register (0 = output, 1 = input)
	case 0x08: m_port_config = data; break;

	// RS-422 channel 1/2 output.  In loopback (mode bit 4) the transmitter is
	// wired straight back to its own receiver, so the byte becomes immediately
	// readable at 0x0b/0x0c and raises RXxBF for that channel.
	case 0x09:
	case 0x0a:
		{
			int const ch = offset - 0x09;
			m_serial_wr_cb[ch](data);
			if (m_mode & 0x10)
			{
				m_serial_rx_data[ch] = data;
				m_serial_rx_valid[ch] = 1;
			}
		}
		break;

	// mode register
	// 7--- ----  port G counter mode
	// -6-- ----  ?
	// --5- ----  RS-422 satellite mode
	// ---4 ----  RS-422 loopback
	// ---- 3210  RS-422 satellite N#
	case 0x0e:
		// leaving loopback disconnects the local link, so a byte that was
		// looped back but never read must not survive into linked mode
		if ((m_mode & 0x10) && !(data & 0x10))
			m_serial_rx_valid[0] = m_serial_rx_valid[1] = 0;
		m_mode = data;
		break;

	// analog mux select
	case 0x0f:
		m_analog_channel = data & 0x07;
		break;
	}
}

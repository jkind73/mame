// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/**********************************************************************

    Sega Saturn Mission Stick emulation

**********************************************************************/

#include "emu.h"
#include "analog.h"
#include <cmath>

//**************************************************************************
//  DEVICE DEFINITIONS
//**************************************************************************

DEFINE_DEVICE_TYPE(SATURN_ANALOG, saturn_analog_device, "saturn_analog", "Sega Saturn Mission Stick")
DEFINE_DEVICE_TYPE(SATURN_MULTICONTROLLER, saturn_multicontroller_device, "saturn_multicontroller", "Sega Saturn Multi Controller")


static INPUT_PORTS_START( saturn_analog )
	PORT_START("JOY")
	// Direction bits are generated from the analog axes, not separate switches.
	PORT_BIT(0xf000, IP_ACTIVE_LOW, IPT_UNUSED)
	PORT_BIT(0x0800, IP_ACTIVE_LOW, IPT_START)
	PORT_BIT(0x0400, IP_ACTIVE_LOW, IPT_BUTTON1) PORT_NAME("A")
	PORT_BIT(0x0200, IP_ACTIVE_LOW, IPT_BUTTON3) PORT_NAME("C")
	PORT_BIT(0x0100, IP_ACTIVE_LOW, IPT_BUTTON2) PORT_NAME("B")
	PORT_BIT(0x0080, IP_ACTIVE_LOW, IPT_BUTTON8) PORT_NAME("R")
	PORT_BIT(0x0040, IP_ACTIVE_LOW, IPT_BUTTON4) PORT_NAME("X")
	PORT_BIT(0x0020, IP_ACTIVE_LOW, IPT_BUTTON5) PORT_NAME("Y")
	PORT_BIT(0x0010, IP_ACTIVE_LOW, IPT_BUTTON6) PORT_NAME("Z")
	PORT_BIT(0x0008, IP_ACTIVE_LOW, IPT_BUTTON7) PORT_NAME("L")
	// Note: unused bits must stay high, Bug 2 relies on this.
	PORT_BIT(0x0007, IP_ACTIVE_LOW, IPT_UNUSED)

	PORT_START("ANALOG_X")
	PORT_BIT( 0xff, 0x80, IPT_AD_STICK_X ) PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25) PORT_KEYDELTA(200) PORT_NAME("AD Stick X")

	PORT_START("ANALOG_Y")
	PORT_BIT( 0xff, 0x80, IPT_AD_STICK_Y ) PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25) PORT_KEYDELTA(200) PORT_NAME("AD Stick Y")

	PORT_START("ANALOG_Z")
	PORT_BIT( 0xff, 0x00, IPT_AD_STICK_Z ) PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25) PORT_KEYDELTA(200) PORT_NAME("AD Stick Z")
INPUT_PORTS_END

static INPUT_PORTS_START( saturn_multicontroller )
	PORT_INCLUDE(saturn_analog)
	PORT_MODIFY("JOY")
	PORT_BIT(0x8000, IP_ACTIVE_LOW, IPT_JOYSTICK_RIGHT)
	PORT_BIT(0x4000, IP_ACTIVE_LOW, IPT_JOYSTICK_LEFT)
	PORT_BIT(0x2000, IP_ACTIVE_LOW, IPT_JOYSTICK_DOWN)
	PORT_BIT(0x1000, IP_ACTIVE_LOW, IPT_JOYSTICK_UP)
	PORT_BIT(0x0088, IP_ACTIVE_LOW, IPT_UNUSED)
	PORT_MODIFY("ANALOG_Z")
	PORT_BIT(0xff, IP_ACTIVE_LOW, IPT_UNUSED)
	PORT_START("TRIGGER_R")
	PORT_BIT(0xff, 0, IPT_PEDAL) PORT_MINMAX(0, 255) PORT_SENSITIVITY(25) PORT_KEYDELTA(20) PORT_NAME("R Trigger")
	PORT_START("TRIGGER_L")
	PORT_BIT(0xff, 0, IPT_PEDAL2) PORT_MINMAX(0, 255) PORT_SENSITIVITY(25) PORT_KEYDELTA(20) PORT_NAME("L Trigger")
	PORT_START("MODE")
	PORT_CONFNAME(1, 1, "Controller Mode")
	PORT_CONFSETTING(0, "Digital")
	PORT_CONFSETTING(1, "Analog")
INPUT_PORTS_END

saturn_multicontroller_device::saturn_multicontroller_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, SATURN_MULTICONTROLLER, tag, owner, clock),
	device_saturn_control_port_interface(mconfig, *this),
	m_joy(*this, "JOY"), m_anx(*this, "ANALOG_X"), m_any(*this, "ANALOG_Y"),
	m_right(*this, "TRIGGER_R"), m_left(*this, "TRIGGER_L"), m_mode(*this, "MODE")
{
}

ioport_constructor saturn_multicontroller_device::device_input_ports() const
{
	return INPUT_PORTS_NAME(saturn_multicontroller);
}

void saturn_multicontroller_device::device_start()
{
	save_item(NAME(m_center_x)); save_item(NAME(m_center_y));
	save_item(NAME(m_zero_right)); save_item(NAME(m_zero_left));
	save_item(NAME(m_analog_mode)); save_item(NAME(m_triggers));
}

void saturn_multicontroller_device::calibrate()
{
	m_center_x = m_anx->read(); m_center_y = m_any->read();
	m_zero_right = m_right->read(); m_zero_left = m_left->read();
	m_triggers = 0x88;
}

void saturn_multicontroller_device::device_reset()
{
	m_analog_mode = BIT(m_mode->read(), 0);
	calibrate();
}

uint16_t saturn_multicontroller_device::sample(uint8_t &x, uint8_t &y, uint8_t &right, uint8_t &left)
{
	bool const analog = BIT(m_mode->read(), 0);
	if (analog != m_analog_mode)
	{
		m_analog_mode = analog;
		calibrate(); // STN-43: switching mode also recalibrates all four axes.
	}
	double dx = int(m_anx->read()) - m_center_x;
	double dy = int(m_any->read()) - m_center_y;
	double const radius = std::hypot(dx, dy);
	if (radius > 128)
	{
		dx *= 128 / radius;
		dy *= 128 / radius;
	}
	// STN-43: circular stick range about (128,128); zero is never output.
	x = std::clamp(int(std::lround(dx)) + 128, 1, 255);
	y = std::clamp(int(std::lround(dy)) + 128, 1, 255);
	right = std::clamp(int(m_right->read()) - m_zero_right, 0, 255);
	left = std::clamp(int(m_left->read()) - m_zero_left, 0, 255);
	// STN-43 trigger diagram: assert at 145, release at 85.
	if (right >= 145) m_triggers &= ~0x80;
	else if (right <= 85) m_triggers |= 0x80;
	if (left >= 145) m_triggers &= ~0x08;
	else if (left <= 85) m_triggers |= 0x08;
	return (m_joy->read() & ~0x0088) | m_triggers;
}

uint8_t saturn_multicontroller_device::read_id(int idx)
{
	uint8_t x, y, right, left;
	sample(x, y, right, left);
	return m_analog_mode ? 0x16 : 0x02;
}

uint16_t saturn_multicontroller_device::read_direct()
{
	uint8_t x, y, right, left;
	return sample(x, y, right, left);
}

uint8_t saturn_multicontroller_device::read_ctrl(uint8_t offset)
{
	uint8_t x, y, right, left;
	uint16_t const buttons = sample(x, y, right, left);
	if (offset == 0) return buttons >> 8;
	if (offset == 1) return buttons;
	if (!m_analog_mode) return 0xff;
	switch (offset)
	{
	case 2: return x;
	case 3: return y;
	case 4: return right;
	case 5: return left;
	default: return 0xff;
	}
}


//-------------------------------------------------
//  input_ports - device-specific input ports
//-------------------------------------------------

ioport_constructor saturn_analog_device::device_input_ports() const
{
	return INPUT_PORTS_NAME( saturn_analog );
}


//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

//-------------------------------------------------
//  saturn_analog_device - constructor
//-------------------------------------------------

saturn_analog_device::saturn_analog_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, SATURN_ANALOG, tag, owner, clock),
	device_saturn_control_port_interface(mconfig, *this),
	m_joy(*this, "JOY"),
	m_anx(*this, "ANALOG_X"),
	m_any(*this, "ANALOG_Y"),
	m_anz(*this, "ANALOG_Z")
{
	m_ctrl_id = 0x15;
}


//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void saturn_analog_device::device_start()
{
	save_item(NAME(m_directions));
}


//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void saturn_analog_device::device_reset()
{
	m_directions = 0xf0;
}


//-------------------------------------------------
//  read_ctrl
//-------------------------------------------------

uint8_t saturn_analog_device::read_ctrl(uint8_t offset)
{
	uint8_t res = 0;
	switch (offset)
	{
		case 0:
		default:
		{
			// SMPC manual Table 3.19: retain each digital direction within its
			// hysteresis band. Right/down assert at 170 and release at 149;
			// left/up assert at 86 and release at 107.
			uint8_t const x = m_anx->read();
			uint8_t const y = m_any->read();
			if (x >= 170) m_directions &= ~0x80;
			else if (x <= 149) m_directions |= 0x80;
			if (x <= 86) m_directions &= ~0x40;
			else if (x >= 107) m_directions |= 0x40;
			if (y >= 170) m_directions &= ~0x20;
			else if (y <= 149) m_directions |= 0x20;
			if (y <= 86) m_directions &= ~0x10;
			else if (y >= 107) m_directions |= 0x10;
			res = ((m_joy->read() >> 8) & 0x0f) | m_directions;
			break;
		}
		case 1:
			res = m_joy->read() & 0xff;
			break;
		case 2:
			res = m_anx->read();
			break;
		case 3:
			res = m_any->read();
			break;
		case 4:
			res = m_anz->read();
			break;
	}
	return res;
}

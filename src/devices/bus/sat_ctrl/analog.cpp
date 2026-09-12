// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/**********************************************************************

    Sega Saturn 3D Control Pad emulation

    The pad (bundled with NiGHTS into Dreams..., also sold on its own)
    can report in two ways:

    - analog mode, peripheral ID 0x16, six data bytes:
        [0] right, left, down, up, start, A, C, B
        [1] R, X, Y, Z, L, 1, 1, 1
        [2] analog stick X axis (0 = left, 0x80 = center, 0xff = right)
        [3] analog stick Y axis (0 = up, 0x80 = center, 0xff = down)
        [4] analog R trigger (0 = released, 0xff = pressed)
        [5] analog L trigger (0 = released, 0xff = pressed)

    - digital mode, peripheral ID 0x02, two data bytes holding the same
      button bits as above, i.e. the report is identical to the one of
      the standard pad.

    The R and L buttons have no switches of their own: they are reported
    as pressed once the corresponding analog trigger goes past a
    threshold.

    The pad powers up in digital mode, the "Analog Mode" input switches
    it to analog mode; some games only recognize the analog report when
    the mode is selected before they boot.

**********************************************************************/

#include "analog.h"
#include "emu.h"


//**************************************************************************
//  DEVICE DEFINITIONS
//**************************************************************************

DEFINE_DEVICE_TYPE(SATURN_ANALOG, saturn_analog_device, "saturn_analog",
                   "Sega Saturn 3D Control Pad")

// analog trigger thresholds for the digital R/L bits, with hysteresis
static constexpr u8 TRIGGER_OFF_THRESHOLD = 0x55;
static constexpr u8 TRIGGER_ON_THRESHOLD = 0x8e;

static INPUT_PORTS_START(saturn_analog) PORT_START("JOY")
    PORT_BIT(0x8000, IP_ACTIVE_LOW, IPT_JOYSTICK_RIGHT)
        PORT_BIT(0x4000, IP_ACTIVE_LOW, IPT_JOYSTICK_LEFT)
            PORT_BIT(0x2000, IP_ACTIVE_LOW, IPT_JOYSTICK_DOWN)
                PORT_BIT(0x1000, IP_ACTIVE_LOW, IPT_JOYSTICK_UP)
                    PORT_BIT(0x0800, IP_ACTIVE_LOW, IPT_START)
                        PORT_BIT(0x0400, IP_ACTIVE_LOW, IPT_BUTTON1)
                            PORT_NAME("A") PORT_BIT(0x0200, IP_ACTIVE_LOW,
                                                    IPT_BUTTON3) PORT_NAME("C")
                                PORT_BIT(0x0100, IP_ACTIVE_LOW, IPT_BUTTON2)
                                    PORT_NAME("B")
    // R and L are reported from the analog triggers, they have no switches
    PORT_BIT(0x0080, IP_ACTIVE_LOW, IPT_UNUSED)
        PORT_BIT(0x0040, IP_ACTIVE_LOW, IPT_BUTTON4) PORT_NAME("X")
            PORT_BIT(0x0020, IP_ACTIVE_LOW, IPT_BUTTON5) PORT_NAME("Y")
                PORT_BIT(0x0010, IP_ACTIVE_LOW, IPT_BUTTON6) PORT_NAME("Z")
                    PORT_BIT(0x0008, IP_ACTIVE_LOW, IPT_UNUSED)
    // Note: unused bits must stay high, Bug 2 relies on this.
    PORT_BIT(0x0007, IP_ACTIVE_LOW, IPT_UNUSED)

        PORT_START("ANALOG_X") PORT_BIT(0xff, 0x80,
                                        IPT_AD_STICK_X) PORT_MINMAX(0x00, 0xff)
            PORT_SENSITIVITY(25) PORT_KEYDELTA(200) PORT_NAME("Analog Stick X")

                PORT_START("ANALOG_Y") PORT_BIT(0xff, 0x80, IPT_AD_STICK_Y)
                    PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25) PORT_KEYDELTA(
                        200) PORT_NAME("Analog Stick Y")

                        PORT_START("ANALOG_R") PORT_BIT(0xff, 0x00,
                                                        IPT_AD_STICK_Z)
                            PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25)
                                PORT_KEYDELTA(200) PORT_NAME("Analog R Trigger")

                                    PORT_START("ANALOG_L") PORT_BIT(0xff, 0x00,
                                                                    IPT_PADDLE)
                                        PORT_MINMAX(0x00,
                                                    0xff) PORT_SENSITIVITY(25)
                                            PORT_KEYDELTA(200) PORT_CENTERDELTA(
                                                1) PORT_NAME("Analog L Trigger")

                                                PORT_START("MODE")
                                                    PORT_BIT(0x01,
                                                             IP_ACTIVE_HIGH,
                                                             IPT_BUTTON7)
                                                        PORT_NAME("Analog Mode")
                                                            PORT_TOGGLE
    INPUT_PORTS_END

    //-------------------------------------------------
    //  input_ports - device-specific input ports
    //-------------------------------------------------

    ioport_constructor saturn_analog_device::device_input_ports() const {
  return INPUT_PORTS_NAME(saturn_analog);
}

//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

//-------------------------------------------------
//  saturn_analog_device - constructor
//-------------------------------------------------

saturn_analog_device::saturn_analog_device(const machine_config &mconfig,
                                           const char *tag, device_t *owner,
                                           uint32_t clock)
    : device_t(mconfig, SATURN_ANALOG, tag, owner, clock),
      device_saturn_control_port_interface(mconfig, *this), m_joy(*this, "JOY"),
      m_anx(*this, "ANALOG_X"), m_any(*this, "ANALOG_Y"),
      m_anr(*this, "ANALOG_R"), m_anl(*this, "ANALOG_L"), m_mode(*this, "MODE"),
      m_r_pressed(false), m_l_pressed(false) {}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void saturn_analog_device::device_start() {
  save_item(NAME(m_r_pressed));
  save_item(NAME(m_l_pressed));
}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void saturn_analog_device::device_reset() {}

//-------------------------------------------------
//  digital_buttons
//-------------------------------------------------

u16 saturn_analog_device::digital_buttons() {
  u16 joy = m_joy->read();

  const u8 r = m_anr->read();
  if (r >= TRIGGER_ON_THRESHOLD)
    m_r_pressed = true;
  else if (r <= TRIGGER_OFF_THRESHOLD)
    m_r_pressed = false;

  const u8 l = m_anl->read();
  if (l >= TRIGGER_ON_THRESHOLD)
    m_l_pressed = true;
  else if (l <= TRIGGER_OFF_THRESHOLD)
    m_l_pressed = false;

  // buttons are active low
  if (m_r_pressed)
    joy &= ~0x0080;
  else
    joy |= 0x0080;

  if (m_l_pressed)
    joy &= ~0x0008;
  else
    joy |= 0x0008;

  return joy;
}

//-------------------------------------------------
//  read_id
//-------------------------------------------------

uint8_t saturn_analog_device::read_id(int idx) {
  // in digital mode the pad is indistinguishable from a standard one
  return analog_mode() ? 0x16 : 0x02;
}

//-------------------------------------------------
//  read_ctrl
//-------------------------------------------------

uint8_t saturn_analog_device::read_ctrl(uint8_t offset) {
  const u16 joy = digital_buttons();

  switch (offset) {
  case 0:
    return joy >> 8;

  case 1:
    return joy & 0xff;

  case 2:
    return m_anx->read();

  case 3:
    return m_any->read();

  case 4:
    return m_anr->read();

  case 5:
    return m_anl->read();

  default:
    return 0;
  }
}
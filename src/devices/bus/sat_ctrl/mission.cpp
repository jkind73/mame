// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/**********************************************************************

    Sega Saturn Mission Stick emulation

    The Mission Stick reports peripheral ID 0x15, i.e. five data bytes:
    two bytes of digital buttons followed by the X and Y axes of the
    stick and the throttle. The dual Mission Stick (used by Panzer
    Dragoon Zwei) reports ID 0x19 and is not emulated yet.

**********************************************************************/

#include "mission.h"
#include "emu.h"


//**************************************************************************
//  DEVICE DEFINITIONS
//**************************************************************************

DEFINE_DEVICE_TYPE(SATURN_MISSION, saturn_mission_device, "saturn_mission",
                   "Sega Saturn Mission Stick")

static INPUT_PORTS_START(saturn_mission) PORT_START("JOY") PORT_BIT(
    0x8000, IP_ACTIVE_LOW, IPT_JOYSTICK_RIGHT) PORT_BIT(0x4000, IP_ACTIVE_LOW,
                                                        IPT_JOYSTICK_LEFT)
    PORT_BIT(0x2000, IP_ACTIVE_LOW,
             IPT_JOYSTICK_DOWN) PORT_BIT(0x1000, IP_ACTIVE_LOW, IPT_JOYSTICK_UP)
        PORT_BIT(0x0800, IP_ACTIVE_LOW,
                 IPT_START) PORT_BIT(0x0400, IP_ACTIVE_LOW, IPT_BUTTON1)
            PORT_NAME("A") PORT_BIT(0x0200, IP_ACTIVE_LOW, IPT_BUTTON3)
                PORT_NAME("C") PORT_BIT(0x0100, IP_ACTIVE_LOW, IPT_BUTTON2)
                    PORT_NAME("B") PORT_BIT(0x0080, IP_ACTIVE_LOW, IPT_BUTTON8)
                        PORT_NAME("R") PORT_BIT(0x0040, IP_ACTIVE_LOW,
                                                IPT_BUTTON4) PORT_NAME("X")
                            PORT_BIT(0x0020, IP_ACTIVE_LOW, IPT_BUTTON5)
                                PORT_NAME("Y")
                                    PORT_BIT(0x0010, IP_ACTIVE_LOW, IPT_BUTTON6)
                                        PORT_NAME("Z")
                                            PORT_BIT(0x0008, IP_ACTIVE_LOW,
                                                     IPT_BUTTON7) PORT_NAME("L")
    // Note: unused bits must stay high, Bug 2 relies on this.
    PORT_BIT(0x0007, IP_ACTIVE_LOW, IPT_UNUSED)

        PORT_START("ANALOG_X") PORT_BIT(0xff, 0x80,
                                        IPT_AD_STICK_X) PORT_MINMAX(0x00, 0xff)
            PORT_SENSITIVITY(25) PORT_KEYDELTA(200) PORT_NAME("Stick X")

                PORT_START("ANALOG_Y") PORT_BIT(0xff, 0x80, IPT_AD_STICK_Y)
                    PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25)
                        PORT_KEYDELTA(200) PORT_NAME("Stick Y")

                            PORT_START("ANALOG_T") PORT_BIT(0xff, 0x00,
                                                            IPT_AD_STICK_Z)
                                PORT_MINMAX(0x00, 0xff) PORT_SENSITIVITY(25)
                                    PORT_KEYDELTA(200)
                                        PORT_NAME("Throttle") INPUT_PORTS_END

    //-------------------------------------------------
    //  input_ports - device-specific input ports
    //-------------------------------------------------

    ioport_constructor saturn_mission_device::device_input_ports() const {
  return INPUT_PORTS_NAME(saturn_mission);
}

//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

//-------------------------------------------------
//  saturn_mission_device - constructor
//-------------------------------------------------

saturn_mission_device::saturn_mission_device(const machine_config &mconfig,
                                             const char *tag, device_t *owner,
                                             uint32_t clock)
    : device_t(mconfig, SATURN_MISSION, tag, owner, clock),
      device_saturn_control_port_interface(mconfig, *this), m_joy(*this, "JOY"),
      m_anx(*this, "ANALOG_X"), m_any(*this, "ANALOG_Y"),
      m_ant(*this, "ANALOG_T") {
  m_ctrl_id = 0x15;
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void saturn_mission_device::device_start() {}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void saturn_mission_device::device_reset() {}

//-------------------------------------------------
//  read_ctrl
//-------------------------------------------------

uint8_t saturn_mission_device::read_ctrl(uint8_t offset) {
  uint8_t res = 0;
  switch (offset) {
  case 0: {
    res = m_joy->read() >> 8;

    // the stick is analog: the four direction bits are derived from the
    // A/D converter output, with the thresholds given in the SMPC manual
    // (right/down turn on at 170 and off at 149, left/up turn on at 86
    // and off at 107). Only force them on, MAME also exposes the
    // directions as digital inputs for keyboard users.
    const uint8_t x = m_anx->read();
    const uint8_t y = m_any->read();

    if (x >= 170)
      res &= ~0x80;
    if (x <= 86)
      res &= ~0x40;
    if (y >= 170)
      res &= ~0x20;
    if (y <= 86)
      res &= ~0x10;
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
    res = m_ant->read();
    break;
  }
  return res;
}
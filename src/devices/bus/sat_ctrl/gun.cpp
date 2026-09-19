// license:BSD-3-Clause
// copyright-holders:
/**********************************************************************

    Sega Saturn Virtua Gun (light gun) emulation

    The Virtua Gun is not driven through the SMPC peripheral protocol: as
    documented in the official "Virtual Gun User's Manual" (Sega developer
    notice STN-41) games switch the SMPC to SH-2 direct mode and talk to
    the gun through the parallel I/O registers:

    - INTBACK reports port status A0, that is an unknown (Megadrive style)
      device with zero connectors, so no ID or data bytes follow it.
    - With DDR = 40 the SH-2 drives bit 6 and reads the peripheral ID back
      from bits 3-0: ID3/ID2 with bit 6 high, ID1/ID0 with bit 6 low, which
      gives ID = A for the Virtua Gun.
    - With DDR = 00 every line is an input: bit 6 is the external latch
      line (routed to the VDP2 when the SMPC EXLE bit is set), bit 5 is the
      start button and bit 4 the trigger, all of them active low.
    - Trigger and start are the only controls the gun has. It detects the
      raster by itself: when the spot it aims at is bright enough it pulls
      the latch line, so that the VDP2 latches its H/V counters. Games
      whiten the screen for a frame after the trigger is pulled and then
      read the latched counters back through TVSTAT/HCNT/VCNT. Aiming at a
      dark area leaves the latch flag clear, which is how games recognise
      the off screen shots they use for reloading.

**********************************************************************/

#include "emu.h"
#include "gun.h"


#include "screen.h"

// #define VERBOSE 1
#include "logmacro.h"

//**************************************************************************
//  DEVICE DEFINITIONS
//**************************************************************************

DEFINE_DEVICE_TYPE(SATURN_GUN, saturn_gun_device, "saturn_gun",
                   "Sega Saturn Virtua Gun")

// the gun only reacts to the white flash games draw once the trigger is pulled
constexpr uint8_t SENSOR_MIN_BRIGHTNESS = 0x7f;

// how long a trigger pull keeps the sensor looking at the screen
constexpr attotime FIRE_DURATION = attotime::from_msec(50);

static INPUT_PORTS_START(saturn_gun) PORT_START("GUN_X")
    PORT_BIT(0xff, 0x80, IPT_LIGHTGUN_X) PORT_NAME("Gun X Axis") PORT_CROSSHAIR(
        X, 1.0, 0.0, 0) PORT_SENSITIVITY(50) PORT_KEYDELTA(15)
        PORT_CHANGED_MEMBER(DEVICE_SELF,
                            FUNC(saturn_gun_device::position_changed), 0)

            PORT_START("GUN_Y") PORT_BIT(0xff, 0x80, IPT_LIGHTGUN_Y)
                PORT_NAME("Gun Y Axis") PORT_CROSSHAIR(Y, 1.0, 0.0, 0)
                    PORT_SENSITIVITY(50) PORT_KEYDELTA(15) PORT_CHANGED_MEMBER(
                        DEVICE_SELF, FUNC(saturn_gun_device::position_changed),
                        0)

                        PORT_START("GUN_B")
                            PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_BUTTON1)
                                PORT_NAME("Trigger") PORT_CHANGED_MEMBER(
                                    DEVICE_SELF,
                                    FUNC(saturn_gun_device::trigger_changed), 0)
                                    PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_START)
                                        PORT_NAME("Start")
                                            PORT_BIT(0xfc, IP_ACTIVE_HIGH,
                                                     IPT_UNUSED) INPUT_PORTS_END

    //-------------------------------------------------
    //  input_ports - device-specific input ports
    //-------------------------------------------------

    ioport_constructor saturn_gun_device::device_input_ports() const {
  return INPUT_PORTS_NAME(saturn_gun);
}

//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

//-------------------------------------------------
//  saturn_gun_device - constructor
//-------------------------------------------------

saturn_gun_device::saturn_gun_device(const machine_config &mconfig,
                                     const char *tag, device_t *owner,
                                     uint32_t clock)
    : device_t(mconfig, SATURN_GUN, tag, owner, clock),
      device_saturn_control_port_interface(mconfig, *this),
      m_buttons(*this, "GUN_B"), m_lightx(*this, "GUN_X"),
      m_lighty(*this, "GUN_Y"), m_fire_timer(nullptr), m_sensor_timer(nullptr),
      m_sensor_state(1) {
  // port status: Megadrive peripheral ID A in the upper nibble and zero
  // connectors in the lower one, so that INTBACK reads no data at all
  m_ctrl_id = 0xa0;
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void saturn_gun_device::device_start() {
  m_fire_timer = timer_alloc(timer_expired_delegate());
  m_sensor_timer = timer_alloc(FUNC(saturn_gun_device::sensor_check), this);

  save_item(NAME(m_sensor_state));
}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void saturn_gun_device::device_reset() {
  m_sensor_state = 1;
  m_fire_timer->reset();
  m_sensor_timer->reset();
}

//-------------------------------------------------
//  trigger_changed - the trigger was pulled
//-------------------------------------------------

INPUT_CHANGED_MEMBER(saturn_gun_device::trigger_changed) {
  if (newval) {
    // keep sensing for a few frames, the game only whitens the screen
    // once it has seen the trigger
    m_fire_timer->adjust(FIRE_DURATION);
    arm_sensor();
  }
}

//-------------------------------------------------
//  position_changed - the gun was moved
//-------------------------------------------------

INPUT_CHANGED_MEMBER(saturn_gun_device::position_changed) { arm_sensor(); }

//-------------------------------------------------
//  aim coordinates
//-------------------------------------------------

int saturn_gun_device::aim_x(screen_device &scr) const {
  const rectangle &visarea = scr.visible_area();

  return visarea.min_x +
         (m_lightx->read() * (visarea.max_x - visarea.min_x)) / 0xff;
}

int saturn_gun_device::aim_y(screen_device &scr) const {
  const rectangle &visarea = scr.visible_area();

  return visarea.min_y +
         (m_lighty->read() * (visarea.max_y - visarea.min_y)) / 0xff;
}

//-------------------------------------------------
//  arm_sensor - wait for the beam at the aim point
//-------------------------------------------------

void saturn_gun_device::arm_sensor() {
  screen_device *const scr = gun_screen();

  if (scr && m_sensor_timer && m_fire_timer->enabled())
    m_sensor_timer->adjust(scr->time_until_pos(aim_y(*scr), aim_x(*scr)));
  else if (m_sensor_timer)
    m_sensor_timer->reset();
}

//-------------------------------------------------
//  sensor_check - the beam reached the aim point
//-------------------------------------------------

TIMER_CALLBACK_MEMBER(saturn_gun_device::sensor_check) {
  screen_device *const scr = gun_screen();
  if (!scr)
    return;

  const int x = aim_x(*scr);
  const int y = aim_y(*scr);

  scr->update_now();
  const rgb_t color = scr->pixel(x, y);

  // reference: http://www.w3.org/TR/AERT#color-contrast
  const uint8_t brightness =
      (color.r() * 0.299) + (color.g() * 0.587) + (color.b() * 0.114);

  if (brightness >= SENSOR_MIN_BRIGHTNESS) {
    if (m_sensor_state != 0)
      LOG("sensor sees the raster at %d,%d (brightness %02x)\n", x, y,
          brightness);

    m_sensor_state = 0;

    // pull the latch line, the SMPC routes it to the VDP2 when EXLE is set
    if (m_port)
      m_port->latch_cb();
  } else {
    if (m_sensor_state == 0)
      LOG("sensor lost the raster at %d,%d (brightness %02x)\n", x, y,
          brightness);

    m_sensor_state = 1;
  }

  // the beam comes back to the aim point once per frame, as long as the
  // trigger pull lasts
  arm_sensor();
}

//-------------------------------------------------
//  read_pdr - SMPC parallel I/O access
//-------------------------------------------------

bool saturn_gun_device::read_pdr(uint8_t ddr, uint8_t data, uint8_t &res) {
  switch (ddr & 0x7f) {
  case 0x40:
    // the SH-2 drives bit 6 and reads the peripheral ID back two bits at
    // a time: ID3 = bit3|bit2 and ID2 = bit1|bit0 with bit 6 high, ID1
    // and ID0 the same way with bit 6 low, which gives ID = A
    res = (data & 0x40) ? 0x7c : 0x3c;
    return true;

  case 0x00:
    // every line is an input: bit 6 is the latch, bit 5 the start button
    // and bit 4 the trigger, the other bits are undefined
    {
      const uint8_t buttons = m_buttons->read();

      res = ((m_sensor_state & 1) << 6) | (BIT(buttons, 1) ? 0x00 : 0x20) |
            (BIT(buttons, 0) ? 0x00 : 0x10) | 0x0c;
      return true;
    }
  }

  return false;
}
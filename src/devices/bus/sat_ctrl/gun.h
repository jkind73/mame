// license:BSD-3-Clause
// copyright-holders:
/**********************************************************************

    Sega Saturn Virtua Gun (light gun) emulation

    Also sold as "Stunner" (USA/Canada) and "Virtua Gun" (Europe).

**********************************************************************/

#ifndef MAME_BUS_SAT_CTRL_GUN_H
#define MAME_BUS_SAT_CTRL_GUN_H

#pragma once

#include "ctrl.h"

//**************************************************************************
//  TYPE DEFINITIONS
//**************************************************************************

// ======================> saturn_gun_device

class saturn_gun_device : public device_t,
                          public device_saturn_control_port_interface {
public:
  // construction/destruction
  saturn_gun_device(const machine_config &mconfig, const char *tag,
                    device_t *owner, uint32_t clock);

  // optional information overrides
  virtual ioport_constructor device_input_ports() const override ATTR_COLD;

  DECLARE_INPUT_CHANGED_MEMBER(trigger_changed);
  DECLARE_INPUT_CHANGED_MEMBER(position_changed);

protected:
  // device-level overrides
  virtual void device_start() override ATTR_COLD;
  virtual void device_reset() override ATTR_COLD;

  // device_saturn_control_port_interface overrides
  virtual uint8_t read_status() override { return m_ctrl_id; }
  virtual uint8_t read_id(int idx) override { return m_ctrl_id; }
  virtual uint8_t read_ctrl(uint8_t offset) override { return 0; }
  virtual bool read_pdr(uint8_t ddr, uint8_t data, uint8_t &res) override;

private:
  TIMER_CALLBACK_MEMBER(sensor_check);

  screen_device *gun_screen() const {
    return m_port ? m_port->m_screen.target() : nullptr;
  }

  // aim point, in screen coordinates
  int aim_x(screen_device &scr) const;
  int aim_y(screen_device &scr) const;

  // schedule the next sensor check for when the beam reaches the aim point
  void arm_sensor();

  required_ioport m_buttons;
  required_ioport m_lightx;
  required_ioport m_lighty;

  emu_timer *m_fire_timer;
  emu_timer *m_sensor_timer;
  int m_sensor_state;
};

// device type definition
DECLARE_DEVICE_TYPE(SATURN_GUN, saturn_gun_device)

#endif // MAME_BUS_SAT_CTRL_GUN_H
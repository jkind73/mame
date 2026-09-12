// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/**********************************************************************

    Sega Saturn Mission Stick emulation

**********************************************************************/

#ifndef MAME_BUS_SAT_CTRL_MISSION_H
#define MAME_BUS_SAT_CTRL_MISSION_H

#pragma once

#include "ctrl.h"

//**************************************************************************
//  TYPE DEFINITIONS
//**************************************************************************

// ======================> saturn_mission_device

class saturn_mission_device : public device_t,
                              public device_saturn_control_port_interface {
public:
  // construction/destruction
  saturn_mission_device(const machine_config &mconfig, const char *tag,
                        device_t *owner, uint32_t clock);

  // optional information overrides
  virtual ioport_constructor device_input_ports() const override ATTR_COLD;

protected:
  // device-level overrides
  virtual void device_start() override ATTR_COLD;
  virtual void device_reset() override ATTR_COLD;

  // device_saturn_control_port_interface overrides
  virtual uint8_t read_ctrl(uint8_t offset) override;
  virtual uint8_t read_status() override { return 0xf1; }
  virtual uint8_t read_id(int idx) override { return m_ctrl_id; }

private:
  required_ioport m_joy;
  required_ioport m_anx;
  required_ioport m_any;
  required_ioport m_ant;
};

// device type definition
DECLARE_DEVICE_TYPE(SATURN_MISSION, saturn_mission_device)

#endif // MAME_BUS_SAT_CTRL_MISSION_H
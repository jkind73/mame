// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/**********************************************************************

   Sega Saturn controller port emulation

**********************************************************************/

#ifndef MAME_BUS_SAT_CTRL_CTRL_H
#define MAME_BUS_SAT_CTRL_CTRL_H

#pragma once

#include "screen.h"

//**************************************************************************
//  TYPE DEFINITIONS
//**************************************************************************

class saturn_control_port_device;

// ======================> device_saturn_control_port_interface

class device_saturn_control_port_interface : public device_interface {
public:
  // construction/destruction
  virtual ~device_saturn_control_port_interface();

  virtual uint16_t read_direct() { return 0; }
  virtual uint8_t read_ctrl(uint8_t offset) { return 0; }
  virtual uint8_t read_status() { return 0xf0; }
  virtual uint8_t read_id(int idx) { return 0xff; }

  // SMPC parallel I/O access in SH-2 direct mode. Devices that speak their
  // own line protocol (cfr. the Virtua Gun) answer here and return true,
  // anything else is decoded as a control pad by the caller.
  virtual bool read_pdr(uint8_t ddr, uint8_t data, uint8_t &res) {
    return false;
  }

protected:
  device_saturn_control_port_interface(const machine_config &mconfig,
                                       device_t &device);

  uint8_t m_ctrl_id;
  saturn_control_port_device *m_port;
};

// ======================> saturn_control_port_device

class saturn_control_port_device : public device_t,
                                   public device_single_card_slot_interface<
                                       device_saturn_control_port_interface> {
public:
  // construction/destruction
  template <typename T>
  saturn_control_port_device(const machine_config &mconfig, const char *tag,
                             device_t *owner, T &&opts, char const *dflt)
      : saturn_control_port_device(mconfig, tag, owner, (uint32_t)0) {
    set_options(std::forward<T>(opts), dflt, false);
  }

  saturn_control_port_device(const machine_config &mconfig, const char *tag,
                             device_t *owner, uint32_t clock = 0);
  virtual ~saturn_control_port_device();

  typedef device_delegate<void()> latch_delegate;

  template <typename T> void set_screen_tag(T &&tag) {
    m_screen.set_tag(std::forward<T>(tag));
  }
  template <typename... T> void set_latch_callback(T &&...args) {
    m_latch_cb.set(std::forward<T>(args)...);
  }

  uint16_t read_direct();
  uint8_t read_ctrl(uint8_t offset);
  uint8_t read_status();
  uint8_t read_id(int idx);
  bool read_pdr(uint8_t ddr, uint8_t data, uint8_t &res);

  // external latch signal, driven by light guns towards the VDP2
  void latch_cb() { m_latch_cb(); }

  // device_t implementation
  virtual void device_start() override ATTR_COLD;

  optional_device<screen_device> m_screen;

protected:
  device_saturn_control_port_interface *m_device;
  latch_delegate m_latch_cb;
};

// device type declaration
DECLARE_DEVICE_TYPE(SATURN_CONTROL_PORT, saturn_control_port_device)

void saturn_controls(device_slot_interface &device);
void saturn_joys(device_slot_interface &device);

#endif // MAME_BUS_SAT_CTRL_CTRL_H

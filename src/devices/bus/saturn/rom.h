// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/***********************************************************************************************************

 Saturn ROM cart emulation

 ***********************************************************************************************************/

#include "emu.h"
#include "rom.h"

//-------------------------------------------------
//  saturn_rom_device - constructor
//-------------------------------------------------

DEFINE_DEVICE_TYPE(SATURN_ROM, saturn_rom_device, "sat_rom", "Saturn ROM Carts")

saturn_rom_device::saturn_rom_device(const machine_config &mconfig,
                                     device_type type, const char *tag,
                                     device_t *owner, uint32_t clock,
                                     int cart_type)
    : device_t(mconfig, type, tag, owner, clock),
      device_sat_cart_interface(mconfig, *this, cart_type) {}

saturn_rom_device::saturn_rom_device(const machine_config &mconfig,
                                     const char *tag, device_t *owner,
                                     uint32_t clock)
    // Data (ROM) cartridges have no type ID in the 24FFFFFFh register that the
    // DRAM (5Ah/5Ch) and battery RAM (21h-24h) carts report.  Technical
    // Bulletin #47 says that address is shared with "Power Memory", and
    // Technical Bulletin #46 identifies data cartridges by a System ID header
    // inside the cart ROM instead, beginning "SEGASATURN DATA" at offset 00H.
    // So 0xff is a "no ID" placeholder rather than a hardware value;
    // machine_start() keys the ROM window off it, and saturn_cart_type_r()
    // reporting it for a data cart is harmless because nothing identifies a
    // data cart that way.
    : saturn_rom_device(mconfig, SATURN_ROM, tag, owner, clock, 0xff) {}

//-------------------------------------------------
//  mapper specific start/reset
//-------------------------------------------------

void saturn_rom_device::device_start() {}

void saturn_rom_device::device_reset() {}

/*-------------------------------------------------
 mapper specific handlers
 -------------------------------------------------*/

uint32_t saturn_rom_device::read_rom(offs_t offset) {
  return m_rom[offset & (m_rom_size / 4 - 1)];
}

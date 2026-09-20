// license:BSD-3-Clause
// copyright-holders:Ryan Holtz

/*****************************************************************************
 *
 *   sh7021.cpp
 *   Portable Hitachi SH-1 (model SH7021) emulator
 *
 *   The CPU core and the on-chip peripherals live in the shared sh1_device;
 *   this part only adds the SH7021's own internal ROM and RAM.
 *
 *****************************************************************************/

#include "emu.h"
#include "sh7021.h"

DEFINE_DEVICE_TYPE(SH7021, sh7021_device, "sh7021", "Hitachi SH7021")


/*-------------------------------------------------
    internal_map - maps SH7021 built-ins
-------------------------------------------------*/

void sh7021_device::internal_map(address_map &map)
{
	map(0x00000000, 0x00007fff).rom().region(DEVICE_SELF, 0).mirror(0x00ff8000); // 32KB internal ROM

	sh1_peripheral_map(map);

	map(0x07000000, 0x070003ff).ram().mirror(0x00fffc00); // 1KB internal RAM, actually at 0xf000000
}

sh7021_device::sh7021_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: sh1_device(mconfig, SH7021, tag, owner, clock, CPU_TYPE_SH2,
			address_map_constructor(FUNC(sh7021_device::internal_map), this), 28, 0xc7ffffff)
{
}

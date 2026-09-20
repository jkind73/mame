// license:BSD-3-Clause
// copyright-holders:Angelo Salese

#include "emu.h"
#include "sh7032.h"

DEFINE_DEVICE_TYPE(SH7032,  sh7032_device,  "sh7032",  "Hitachi SH-1 (SH7032)")


sh7032_device::sh7032_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: sh1_device(mconfig, SH7032, tag, owner, clock, CPU_TYPE_SH1,
			address_map_constructor(FUNC(sh7032_device::sh7032_map), this), 28, 0xc7ffffff)
{
}

void sh7032_device::device_start()
{
	sh1_device::device_start();
}

void sh7032_device::device_reset()
{
	sh1_device::device_reset();
}

void sh7032_device::sh7032_map(address_map &map)
{
	// The SH7032 has no internal ROM, so the whole peripheral set comes from
	// the shared SH-1 map.  The earlier revision of this file mapped the
	// entire 0x05fffe00-0x05ffffff window as plain RAM, which meant the ITU,
	// the DMAC, the SCI channels and the interrupt controller did nothing;
	// the Saturn CD block firmware drives all of them (saturn_cdb.cpp).
	sh1_peripheral_map(map);

	// 4KB of on-chip RAM, physically at 0x0f000000 but reached at 0x07000000
	// because the SH-1 clears address bits 29-30 before the bus cycle (the same
	// 0xc7ffffff mask the SH7021's 1KB RAM is mapped through upstream).  The
	// CD block firmware's reset vector sets SP to 0x0f001000 - the top of
	// exactly this RAM - and runs its scheduler and command tasks out of it,
	// so a wrong address here loses the stack entirely.
	map(0x07000000, 0x07000fff).ram().mirror(0x00fff000);
}

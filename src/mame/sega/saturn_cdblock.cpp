// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont, David Haywood

// CD block implementation slot.  See saturn_cdblock.h for why it exists.

#include "emu.h"
#include "saturn_cdblock.h"

#include "saturn_cd_hle.h"
#include "saturn_cdb.h"

DEFINE_DEVICE_TYPE(SATURN_CDBLOCK_SLOT, saturn_cdblock_slot_device, "saturn_cdblock_slot", "Saturn CD block slot")

saturn_cdblock_slot_device::saturn_cdblock_slot_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, SATURN_CDBLOCK_SLOT, tag, owner, clock)
	, device_single_card_slot_interface<saturn_cdblock_interface>(mconfig, *this)
	, m_host_irq_cb(*this)
{
}

saturn_cdblock_slot_device::~saturn_cdblock_slot_device()
{
}

void saturn_cdblock_slot_device::device_start()
{
	m_cd_block = get_card_device();
	if (m_cd_block)
		m_cd_block->host_irq_cb().set(FUNC(saturn_cdblock_slot_device::cd_block_irq_w));
}

uint16_t saturn_cdblock_slot_device::host_r(offs_t offset, uint16_t mem_mask)
{
	if (!m_cd_block)
		return 0xffff;

	return m_cd_block->host_r(offset, mem_mask);
}

void saturn_cdblock_slot_device::host_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (m_cd_block)
		m_cd_block->host_w(offset, data, mem_mask);
}

void saturn_cdblocks(device_slot_interface &device)
{
	// The default is an empty slot, which leaves the driver's own HLE drive
	// model in charge.  Selecting this option hands the host window to the
	// real CD block firmware.
	// The block's SH-1 runs at 20 MHz (Sega's own Saturn overview manual lists
	// "SH-1 32-bit RISC chip 20.0 MHz" and 512KB of RAM for the CD block), and
	// the card has to be given that clock explicitly: a slot option's clock
	// defaults to zero, which would leave the CPU with no cycles to run.
	device.option_add("lle", SATURN_CDB).clock(20'000'000);
}

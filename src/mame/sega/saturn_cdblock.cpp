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
	device.option_add_internal("hle", SATURN_CD_HLE);
	device.option_add_internal("lle", SATURN_CDB);
}

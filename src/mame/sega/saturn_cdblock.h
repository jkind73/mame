// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont, David Haywood

// Saturn CD block implementations.
//
// The console needs a CD block behind the host register window at
// 0x05800000-0x058fffff.  Two implementations exist:
//
//   * the HLE drive model in saturn_cd_hle.cpp, which answers the host
//     command protocol directly and is what every existing qualification runs
//     against;
//   * the LLE core in saturn_cdb.cpp, which runs the real YGR019B/CD block
//     firmware (satcdb ROM set) and exposes the same host interface.
//
// The machine's "cdblock" slot selects between them: empty (the default) uses
// the HLE the driver instantiates itself, and "-cdblock lle" puts the
// firmware core in charge of the host window.  This is the arrangement MAME
// issue #5807 asked for.  ST-V keeps its direct HLE instance, because its CD
// sub-board has no dumped firmware.

#ifndef MAME_SEGA_SATURN_CDBLOCK_H
#define MAME_SEGA_SATURN_CDBLOCK_H

#pragma once

// ======================> saturn_cdblock_interface

class saturn_cdblock_interface : public device_interface
{
public:
	virtual ~saturn_cdblock_interface() = default;

	// Host (SH-2) register window access.  Offsets are relative to
	// 0x05800000, and the implementation is responsible for the mirroring
	// inside its window.
	virtual uint16_t host_r(offs_t offset, uint16_t mem_mask = ~0) = 0;
	virtual void host_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0) = 0;

	// CD block interrupt line to the main CPUs (SCU A-Bus external
	// interrupt 0).
	auto host_irq_cb() { return m_cd_host_irq_cb.bind(); }

protected:
	saturn_cdblock_interface(const machine_config &mconfig, device_t &device)
		: device_interface(device, "saturn_cdblock")
		, m_cd_host_irq_cb(device)
	{
	}

	devcb_write_line m_cd_host_irq_cb;
};

// ======================> saturn_cdblock_slot_device

class saturn_cdblock_slot_device : public device_t,
									public device_single_card_slot_interface<saturn_cdblock_interface>
{
public:
	template <typename T>
	saturn_cdblock_slot_device(const machine_config &mconfig, const char *tag, device_t *owner, T &&opts, char const *dflt)
		: saturn_cdblock_slot_device(mconfig, tag, owner, (uint32_t)0)
	{
		option_reset();
		opts(*this);
		set_default_option(dflt);
		set_fixed(false);
	}

	saturn_cdblock_slot_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);
	virtual ~saturn_cdblock_slot_device();

	// Selected implementation, or nullptr when the slot is empty.
	saturn_cdblock_interface *cd_block() const { return m_cd_block; }

	// host window access through the selected implementation
	uint16_t host_r(offs_t offset, uint16_t mem_mask = ~0);
	void host_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

	// interrupt line from the selected implementation
	auto host_irq_cb() { return m_host_irq_cb.bind(); }

	// CD block interrupt, forwarded once device resolution has happened
	void cd_block_irq_w(int state) { m_host_irq_cb(state); }

protected:
	virtual void device_start() override ATTR_COLD;

private:
	saturn_cdblock_interface *m_cd_block = nullptr;
	devcb_write_line m_host_irq_cb;
};

DECLARE_DEVICE_TYPE(SATURN_CDBLOCK_SLOT, saturn_cdblock_slot_device)

void saturn_cdblocks(device_slot_interface &device);

#endif // MAME_SEGA_SATURN_CDBLOCK_H

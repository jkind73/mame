// license:BSD-3-Clause
// copyright-holders:Fabio Priuli
/***********************************************************************************************************

 Saturn cart emulation

 ***********************************************************************************************************/


#include "emu.h"
#include "dram.h"


//-------------------------------------------------
//  constructor
//-------------------------------------------------

DEFINE_DEVICE_TYPE(SATURN_DRAM_8MB,  saturn_dram8mb_device,  "sat_dram_8mb",  "Saturn Data RAM 8Mbit Cart")
DEFINE_DEVICE_TYPE(SATURN_DRAM_32MB, saturn_dram32mb_device, "sat_dram_32mb", "Saturn Data RAM 32Mbit Cart")


saturn_dram_device::saturn_dram_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, int cart_type)
	: device_t(mconfig, type, tag, owner, clock)
	, device_sat_cart_interface(mconfig, *this, cart_type)
{
}

saturn_dram8mb_device::saturn_dram8mb_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: saturn_dram_device(mconfig, SATURN_DRAM_8MB, tag, owner, clock, 0x5a)
{
}

saturn_dram32mb_device::saturn_dram32mb_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: saturn_dram_device(mconfig, SATURN_DRAM_32MB, tag, owner, clock, 0x5c)
{
}


//-------------------------------------------------
//  mapper specific start/reset
//-------------------------------------------------

void saturn_dram_device::device_start()
{
}

void saturn_dram_device::device_reset()
{
}


/*-------------------------------------------------
 mapper specific handlers
 -------------------------------------------------*/

/*
  Two independent DRAM chips are present in the cart, and the console maps a
  fixed 2 MiB window to each of them (0x02400000-0x025fffff and
  0x02600000-0x027fffff, plus the cache-through aliases) no matter which
  capacity is fitted - see sat_console_state::machine_reset().  Software
  determines the real capacity from the cart ID (0x5a = 8 Mbit, 0x5c = 32 Mbit)
  rather than from the decode, so an 8 Mbit cart answers inside a window four
  times larger than its chip.

  What the hardware does past the end of a chip is not documented: sat_slot.cpp
  has flagged this as an open question since the cart was added.  Aliasing the
  chip over the whole window is retained here because that is the long-standing
  behaviour and nothing in the corpus contradicts it; it is a modelling choice,
  not measured behaviour.  The one thing that is certain is that a cart whose
  region was never allocated must not be dereferenced - taking offset modulo an
  empty vector is a division by zero, so report and return open bus instead.
*/

uint32_t saturn_dram_device::read_ext_dram0(offs_t offset)
{
	if (m_ext_dram0.empty())
	{
		logerror("%s: DRAM0 read with no region allocated (offs %X)\n", machine().describe_context(), offset);
		return 0xffffffff;
	}
	return m_ext_dram0[offset % m_ext_dram0.size()];
}

uint32_t saturn_dram_device::read_ext_dram1(offs_t offset)
{
	if (m_ext_dram1.empty())
	{
		logerror("%s: DRAM1 read with no region allocated (offs %X)\n", machine().describe_context(), offset);
		return 0xffffffff;
	}
	return m_ext_dram1[offset % m_ext_dram1.size()];
}

void saturn_dram_device::write_ext_dram0(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (m_ext_dram0.empty())
	{
		logerror("%s: DRAM0 write with no region allocated (offs %X data %08X & %08X)\n", machine().describe_context(), offset, data, mem_mask);
		return;
	}
	uint32_t &mem = m_ext_dram0[offset % m_ext_dram0.size()];
	COMBINE_DATA(&mem);
}

void saturn_dram_device::write_ext_dram1(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (m_ext_dram1.empty())
	{
		logerror("%s: DRAM1 write with no region allocated (offs %X data %08X & %08X)\n", machine().describe_context(), offset, data, mem_mask);
		return;
	}
	uint32_t &mem = m_ext_dram1[offset % m_ext_dram1.size()];
	COMBINE_DATA(&mem);
}

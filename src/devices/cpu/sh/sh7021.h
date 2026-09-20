// license:BSD-3-Clause
// copyright-holders:Ryan Holtz

/*****************************************************************************
 *
 *   sh7021.h
 *   Portable Hitachi SH-1 (model SH7021) emulator
 *
 *   The CPU core and the on-chip peripherals are shared with the rest of the
 *   SH-1 family in sh1_device; this part only declares its own internal
 *   memory layout (32KB mask ROM plus 1KB RAM).
 *
 *****************************************************************************/

#ifndef MAME_CPU_SH_SH7021_H
#define MAME_CPU_SH_SH7021_H

#pragma once

#include "sh1.h"

class sh7021_device : public sh1_device
{
public:
	// construction/destruction
	sh7021_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

	virtual void execute_run() override;

private:
	void internal_map(address_map &map) ATTR_COLD;
};

DECLARE_DEVICE_TYPE(SH7021, sh7021_device)

#endif // MAME_CPU_SH_SH7021_H

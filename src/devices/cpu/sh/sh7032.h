// license:BSD-3-Clause
// copyright-holders:Angelo Salese

// SH7032, sh1 variant

#ifndef MAME_CPU_SH_SH7032_H
#define MAME_CPU_SH_SH7032_H

#pragma once

#include "sh1.h"

// The SH7032 is an SH-1 with no internal ROM and 4KB of on-chip RAM at
// 0x0f000000.  It is the CPU of the Saturn CD block, where the firmware is
// held in the external 64KB ROM the CD block exposes at address 0.
class sh7032_device : public sh1_device
{
public:
	sh7032_device(const machine_config &mconfig, const char *_tag, device_t *_owner, uint32_t _clock);

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

private:
	void sh7032_map(address_map &map) ATTR_COLD;
};

DECLARE_DEVICE_TYPE(SH7032, sh7032_device)

#endif // MAME_CPU_SH_SH7032_H

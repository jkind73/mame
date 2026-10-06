// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont
/*
  Saturn / ST-V: types of the SH-2 external bus timing and arbitration
  (saturn_bus.cpp). The functions themselves are members of saturn_state.
*/

#ifndef MAME_SEGA_SATURN_BUS_H
#define MAME_SEGA_SATURN_BUS_H

#pragma once

namespace saturn_bus {

// an interval, in machine time, during which a requester held the shared external bus
struct interval
{
	attotime start, end;
};

// the requesters of the shared bus: each SH-2 and, later, its DMAC (requester = cpu * 2 + dma)
constexpr unsigned REQUESTERS = 4;

} // namespace saturn_bus

#endif // MAME_SEGA_SATURN_BUS_H

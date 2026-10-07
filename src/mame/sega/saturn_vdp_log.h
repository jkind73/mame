// license:BSD-3-Clause
// copyright-holders:

// Compile time diagnostics of the Saturn video chips. LOG_VDP_FRAME logs one line per VDP1 frame
// change (commands executed, dots plotted and clipped) and one per VDP2 frame (the registers and
// the dots of the sprite layer). Set SATURN_VDP_VERBOSE to LOG_VDP_FRAME and rebuild; with the
// default 0 the logging and the counters it needs are compiled out.

#ifndef MAME_SEGA_SATURN_VDP_LOG_H
#define MAME_SEGA_SATURN_VDP_LOG_H

#pragma once

#define LOG_VDP_FRAME (1U << 1)

#define SATURN_VDP_VERBOSE 0

// counts something for the frame log only
template <typename T> inline void vdp_stat(T &counter)
{
	if constexpr ((SATURN_VDP_VERBOSE & LOG_VDP_FRAME) != 0)
		counter++;
}

#endif // MAME_SEGA_SATURN_VDP_LOG_H

// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP2 dot composition: priority stack, colour calculation,
  extended colour calculation, colour offset and shadow.

  The hardware composes each dot from the layers' dots; it does not paint
  layer after layer. Per dot the priority resolver keeps the three
  highest-priority screen dots (first, second, third) with the background as
  the initial fill. Layers are offered in the order SPR, RBG0, NBG0, NBG1,
  NBG2, NBG3 and a later layer only displaces an earlier one when its
  priority is strictly greater, so earlier layers win ties. The colour
  calculator then mixes the first and second dots (or first, second, third
  and fourth in extended mode), adds the colour offset and halves shadowed
  dots.

  Derived from the MiSTer Saturn core's RTL (rtl/Saturn/VDP2/VDP2.sv
  3170-3411 for the stack, VDP2_pkg.sv 2384-2433 for the arithmetic); the
  line references are to that revision. Pure functions, no machine state.
*/

#ifndef MAME_SEGA_SATURN_VDP2_COMPOSE_H
#define MAME_SEGA_SATURN_VDP2_COMPOSE_H

#pragma once

#include <cstdint>

namespace saturn_vdp2_compose {

// VDP2_pkg.sv ScreenDot_t: a layer's dot after priority/attribute resolution.
struct screen_dot {
	uint32_t dc;          // resolved 24-bit RGB (0x00RRGGBB)
	uint8_t caos;         // colour RAM address offset (3 bits)
	uint8_t ccrt;         // colour calculation ratio (5 bits)
	uint16_t ccen:1;      // colour calculation enabled for this dot
	uint16_t ccm3:1;      // colour calculation mode 3 (per-dot CC bit)
	uint16_t coen:1;      // colour offset enable
	uint16_t cosl:1;      // colour offset select (A/B)
	uint16_t sden:1;      // shadow enable
	uint16_t boken:1;     // border-on colour calculation (extended mode)
	uint16_t lcen:1;      // line colour screen insertion
	uint16_t palette:1;   // colour came from colour RAM (not direct RGB)
	uint16_t msb:1;       // colour data MSB (colour RAM bit 15/31)

	screen_dot()
		: dc(0), caos(0), ccrt(0), ccen(0), ccm3(0), coen(0), cosl(0), sden(0), boken(0), lcen(0), palette(0), msb(0)
	{
	}
};

struct rgb {
	uint8_t r = 0, g = 0, b = 0;
};

// One layer's contribution to a dot, before the stack.
struct layer_input {
	bool on = false;
	uint8_t priority = 0; // 0 hides the dot
	screen_dot dot;
};

struct dot_stack {
	screen_dot dot[3]; // first, second, third
	uint8_t pri[3] = {0, 0, 0};
};

// VDP2.sv 3320-3411. `slot` selects the insertion rules the RTL applies:
// the sprite layer only takes the top slot, RBG0 the top two and every
// NBG layer all three.
enum class layer_kind { sprite, rbg0, nbg };

inline void insert_layer(dot_stack &s, layer_kind kind, layer_input const &l)
{
	if (!l.on || l.priority == 0)
		return;
	if (kind == layer_kind::sprite || l.priority > s.pri[0]) {
		s.dot[2] = s.dot[1]; s.pri[2] = s.pri[1];
		s.dot[1] = s.dot[0]; s.pri[1] = s.pri[0];
		s.dot[0] = l.dot;    s.pri[0] = l.priority;
	} else if (l.priority > s.pri[1]) {
		s.dot[2] = s.dot[1]; s.pri[2] = s.pri[1];
		s.dot[1] = l.dot;    s.pri[1] = l.priority;
	} else if (kind == layer_kind::nbg && l.priority > s.pri[2]) {
		s.dot[2] = l.dot;    s.pri[2] = l.priority;
	}
}

// VDP2_pkg.sv ColorCalcRatio: (a * ra + b * rb) / 32, saturating at 255.
inline uint8_t ratio_mix(uint8_t a, uint8_t b, unsigned ra, unsigned rb)
{
	unsigned const s = a * ra + b * rb;
	return (s >> 13) ? 0xff : uint8_t((s >> 5) & 0xff);
}

// VDP2_pkg.sv ColorCalc. ccmd 0 blends by the ratio register (first weighs
// 31 - ratio, second ratio + 1); ccmd 1 adds the two dots with saturation.
inline rgb color_calc(rgb first, rgb second, unsigned ccrt, bool ccen, bool ccmd)
{
	if (!ccen)
		return first;
	unsigned const ra = ccmd ? 32 : (~ccrt & 31);
	unsigned const rb = ccmd ? 32 : ((ccrt & 31) + 1);
	return { ratio_mix(first.r, second.r, ra, rb),
	         ratio_mix(first.g, second.g, ra, rb),
	         ratio_mix(first.b, second.b, ra, rb) };
}

// VDP2_pkg.sv ColorCalcExtRatio: sec/2 + thd/2 or sec/2 + thd/4 + fth/4.
inline uint8_t ext_mix(uint8_t sec, uint8_t thd, uint8_t fth, bool rt_sec, bool rt_thd)
{
	unsigned s = rt_sec ? (sec >> 1) : sec;
	if (rt_sec)
		s += rt_thd ? (thd >> 2) + (fth >> 2) : (thd >> 1);
	return uint8_t(s & 0xff);
}

// VDP2_pkg.sv ExtColorCalc. crmd is RAMCTL.CRMD, exccen already includes
// ~BOKEN as the RTL passes it.
inline rgb ext_color_calc(rgb sec, bool ccen_sec, rgb thd, bool palette_thd, bool ccen_thd,
                          rgb fth, bool palette_fth, bool lcen, bool boken, unsigned crmd, bool exccen)
{
	bool const rgb_mode = crmd != 0;
	bool const rt_sec = (ccen_sec && !(rgb_mode && palette_thd) && exccen) || (boken && !rgb_mode);
	// ST-058 Table 12.2: in colour RAM modes 1 and 2 a palette format fourth image
	// (the one below the line colour insertion) leaves 2:2:0 instead of 2:1:1
	bool const rt_thd = (ccen_thd && lcen && exccen && !(rgb_mode && palette_fth)) || (boken && !rgb_mode);
	return { ext_mix(sec.r, thd.r, fth.r, rt_sec, rt_thd),
	         ext_mix(sec.g, thd.g, fth.g, rt_sec, rt_thd),
	         ext_mix(sec.b, thd.b, fth.b, rt_sec, rt_thd) };
}

// VDP2_pkg.sv ColorOffset. `offset` is the 9-bit two's-complement register
// value already selected between A and B by the caller.
inline uint8_t color_offset(uint8_t c, unsigned offset, bool enable)
{
	if (!enable)
		return c;
	bool const neg = offset & 0x100;
	int const o = neg ? int(offset) - 0x200 : int(offset);
	int const sum = int(c) + o;
	if (sum < 0)
		return 0;
	if (sum > 255)
		return 255;
	return uint8_t(sum);
}

// VDP2_pkg.sv Shadow: a shadowed dot is halved.
inline uint8_t shadow(uint8_t c, bool sden)
{
	return sden ? (c >> 1) : c;
}

// VDP2_pkg.sv Color555To888: the low bits are zero, not replicated.
inline rgb color555(uint16_t w)
{
	return { uint8_t((w & 0x1f) << 3), uint8_t(((w >> 5) & 0x1f) << 3), uint8_t(((w >> 10) & 0x1f) << 3) };
}

} // namespace saturn_vdp2_compose

#endif // MAME_SEGA_SATURN_VDP2_COMPOSE_H

// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP1 drawing engine. See saturn_vdp1_draw.h.

  Accumulators are kept in the top 13 bits of a 32 bit word (shifted left by
  19), which is how the hardware's 13 bit error registers wrap for very long
  edges and lines.
*/

#include "saturn_vdp1_draw.h"

#include <algorithm>
#include <cstdlib>

namespace saturn_vdp1 {

namespace {

// Cost model, in VDP1 clocks (Mednafen's structure, verified against the Developer's
// Manual: one dot per clock, a dot that reads the frame buffer takes 6 times as long,
// pre-clipping costs up to 5 clocks per line). The values are the hardware ones.
// The MiSTer probe run of 2026-09-28 (pixel read +1, overhead 116/256, frame buffer
// row change +4) measured the FPGA core's own memory timing, not the silicon's, and
// contradicts the manual's 6x, so it is not used.
constexpr int32_t COMMAND_FETCH = 16;
constexpr int32_t GOURAUD_TABLE = 4;
constexpr int32_t LOOKUP_TABLE = 16;
constexpr int32_t LINE_COMMAND = 1;
constexpr int32_t LINE_GOURAUD = 2;
constexpr int32_t PRECLIP_TEST = 4;
constexpr int32_t LINE_SETUP = 8;
constexpr int32_t PIXEL = 1;
constexpr int32_t PIXEL_READ = 5;
constexpr int32_t FB_ROW = 0;
constexpr uint32_t OVERHEAD_16BPP = 48;   // /256, frame buffer and VRAM refresh overhead
constexpr uint32_t OVERHEAD_8BPP = 24;    // /256

constexpr int32_t sext13(int32_t v) { return int32_t(uint32_t(v) << 19) >> 19; }
constexpr uint32_t up(int32_t v) { return uint32_t(v) << 19; }   // into the top 13 bits

// Row stride shift of the texture per colour mode: words per texel row = width >> shift
constexpr unsigned row_shift(unsigned cm) { return (7 - cm) / 3; }

} // anonymous namespace

//**************************************************************************
//  Steppers
//**************************************************************************

void draw_engine::gouraud_stepper::setup(unsigned length, uint32_t start, uint32_t end)
{
	colour = start & 0x7fff;
	whole = 0;

	for (unsigned c = 0; c < 3; c++) {
		unsigned const sh = c * 5;
		int32_t const dg = int32_t((end >> sh) & 0x1f) - int32_t((start >> sh) & 0x1f);
		int32_t const adg = std::abs(dg);
		inc[c] = (dg >= 0 ? 1 : -1) * (1 << sh);

		int32_t e_inc, e_adj, e;
		if (int32_t(length) <= adg) {
			e_inc = (adg + 1) * 2;
			e_adj = int32_t(length) * 2;
			e = adg + 1 - (int32_t(length) * 2 + (dg < 0 ? 1 : 0));
			while (e >= 0) {
				colour += uint32_t(inc[c]);
				e -= e_adj;
			}
			while (e_inc >= e_adj) {
				whole += uint32_t(inc[c]);
				e_inc -= e_adj;
			}
		} else {
			e_inc = adg * 2;
			e_adj = (int32_t(length) - 1) * 2;
			e = int32_t(length) - (int32_t(length) * 2 - (dg < 0 ? 1 : 0));
			if (e >= 0) {
				colour += uint32_t(inc[c]);
				e -= e_adj;
			}
			if (e_inc >= e_adj) {
				whole += uint32_t(inc[c]);
				e_inc -= e_adj;
			}
		}
		error[c] = ~e;
		error_inc[c] = e_inc;
		error_adj[c] = e_adj;
	}
}

void draw_engine::gouraud_stepper::step()
{
	colour += whole;
	for (unsigned c = 0; c < 3; c++) {
		error[c] -= error_inc[c];
		if (error[c] < 0) {
			colour += uint32_t(inc[c]);
			error[c] += error_adj[c];
		}
	}
}

// Gouraud correction: each colour channel is offset by (gouraud - 16) and saturated
uint16_t draw_engine::gouraud_stepper::apply(uint16_t pix) const
{
	uint16_t out = pix & 0x8000;
	for (unsigned c = 0; c < 3; c++) {
		unsigned const sh = c * 5;
		int32_t const v = int32_t((pix >> sh) & 0x1f) + int32_t((colour >> sh) & 0x1f) - 16;
		out |= uint16_t(std::clamp(v, 0, 31) << sh);
	}
	return out;
}

void draw_engine::texture_stepper::setup(unsigned length, int32_t start, int32_t end, int32_t scale, int32_t fudge)
{
	int32_t const dt = end - start;
	int32_t const adt = std::abs(dt);
	t = (start * scale) | fudge;
	dir = dt >= 0 ? scale : -scale;
	if (int32_t(length) <= adt) {
		error_inc = (adt + 1) * 2;
		error_adj = int32_t(length) * 2;
		error = adt + 1 - (int32_t(length) * 2 + (dt < 0 ? 1 : 0));
	} else {
		error_inc = adt * 2;
		error_adj = (int32_t(length) - 1) * 2;
		error = int32_t(length) - (int32_t(length) * 2 - (dt < 0 ? 1 : 0));
	}
}

int32_t draw_engine::texture_stepper::pre_step()
{
	while (error >= 0) {
		t += dir;
		error -= error_adj;
	}
	error += error_inc;
	return t;
}

void draw_engine::edge_stepper::setup(bool gouraud, vertex const &p0, vertex const &p1, int32_t dmax)
{
	int32_t const dx = sext13(p1.x - p0.x);
	int32_t const dy = sext13(p1.y - p0.y);
	int32_t const adx = std::abs(dx), ady = std::abs(dy);
	int32_t const m = std::max(adx, ady);

	x = p0.x;
	x_inc = dx >= 0 ? 1 : -1;
	x_error = int32_t(up(m - 2 * m - 1));
	x_error_inc = int32_t(up(2 * adx));
	x_error_adj = int32_t(up(-2 * m));
	x_error_cmp = int32_t(up(dy < 0 ? -1 : 0));

	y = p0.y;
	y_inc = dy >= 0 ? 1 : -1;
	y_error = int32_t(up(m - 2 * m - 1));
	y_error_inc = int32_t(up(2 * ady));
	y_error_adj = int32_t(up(-2 * m));
	y_error_cmp = int32_t(up(dx < 0 ? -1 : 0));

	d_error = int32_t(up(dmax - 2 * dmax - 1));
	d_error_inc = int32_t(up(2 * m));
	d_error_adj = int32_t(up(-2 * dmax));
	d_error_cmp = int32_t(up(((ady > adx ? dy : dx) < 0) ? -1 : 0));

	if (gouraud)
		g.setup(m + 1, p0.g, p1.g);
}

void draw_engine::edge_stepper::step(bool gouraud)
{
	d_error = int32_t(uint32_t(d_error) + uint32_t(d_error_inc));
	if (d_error >= d_error_cmp) {
		d_error = int32_t(uint32_t(d_error) + uint32_t(d_error_adj));

		x_error = int32_t(uint32_t(x_error) + uint32_t(x_error_inc));
		if (x_error >= x_error_cmp) {
			x += x_inc;
			x_error = int32_t(uint32_t(x_error) + uint32_t(x_error_adj));
		}

		y_error = int32_t(uint32_t(y_error) + uint32_t(y_error_inc));
		if (y_error >= y_error_cmp) {
			y += y_inc;
			y_error = int32_t(uint32_t(y_error) + uint32_t(y_error_adj));
		}

		if (gouraud)
			g.step();
	}
}

//**************************************************************************
//  Texture and pixel access
//**************************************************************************

void draw_engine::reset()
{
	sys_x = sys_y = 0;
	user_x0 = user_y0 = user_x1 = user_y1 = 0;
	local_x = local_y = 0;
	m_dta_counter = 0;
}

// One texel by its coordinate along the line. Bit 31 of the result marks a
// transparent texel (or an end code that is to be skipped); the low 16 bits
// are the pixel value including the colour bank.
uint32_t draw_engine::tex_fetch(uint32_t x)
{
	unsigned const mode = m_prim.mode;
	unsigned const cm = (mode >> 3) & 7;
	bool const spd = mode & 0x40;
	bool const ecd = mode & 0x80;
	uint32_t const base = m_prim.tex_base;
	uint32_t rtd, or_bits = 0;

	switch (cm) {
	case 0:
	case 1:
		rtd = (vram[(base + (x >> 2)) & 0x3ffff] >> (((x & 3) ^ 3) << 2)) & 0xf;
		if (!ecd && rtd == 0xf) {
			m_prim.ec_count--;
			return ~0U;
		}
		if (cm == 0)
			or_bits = m_prim.colour_bank;
		if (!spd && rtd == 0)
			or_bits |= ~0U;
		return (cm == 0 ? rtd : m_prim.clut[rtd]) | or_bits;

	case 2:
	case 3:
	case 4: {
		rtd = (vram[(base + (x >> 1)) & 0x3ffff] >> (((x & 1) ^ 1) << 3)) & 0xff;
		if (!ecd && rtd == 0xff) {
			m_prim.ec_count--;
			return ~0U;
		}
		or_bits = m_prim.colour_bank;
		if (!spd && rtd == 0)
			or_bits |= ~0U;
		uint32_t const mask = cm == 2 ? 0x3f : cm == 3 ? 0x7f : 0xff;
		return (rtd & mask) | or_bits;
	}

	default:
		// DISAGREEMENT: colour modes 6 and 7 read VRAM word 0 (Mednafen, Ymir);
		// MiSTer reads the character data like mode 5.
		rtd = cm >= 6 ? vram[0] : vram[(base + x) & 0x3ffff];
		if (!ecd && (rtd & 0xc000) == 0x4000) {
			m_prim.ec_count--;
			return ~0U;
		}
		if (!spd && rtd < 0x4000)
			or_bits |= ~0U;
		return rtd | or_bits;
	}
}

// Draws one dot into the draw frame buffer; returns its cost in clocks
int32_t draw_engine::plot(int32_t x, int32_t y, uint16_t pix, bool transparent, gouraud_stepper *g)
{
	unsigned const mode = m_prim.mode;
	bool const bpp8 = tvmr & TVMR_8BPP;
	bool const msb_on = mode & 0x8000;
	bool const half_bg = !msb_on && (mode & 1);
	bool const half_fg = !bpp8 && !msb_on && (mode & 2);
	uint16_t *row;
	int32_t cost = 0;

	if (fbcr & FBCR_DIE) {
		row = fb + (((y >> 1) & 0xff) << 9);
		transparent |= ((y & 1) != ((fbcr & FBCR_DIL) ? 1 : 0));
	} else {
		row = fb + ((y & 0xff) << 9);
	}

	if (mode & 0x100)   // mesh
		transparent |= (x ^ y) & 1;

	if (bpp8) {
		if (msb_on) {
			// DISAGREEMENT: MON in 8 bpp follows Mednafen/Ymir (the pixel keeps its
			// value, shifted by the byte lane); MiSTer rewrites both byte lanes.
			pix = uint16_t((row[(x >> 1) & 0x1ff] | 0x8000) >> (((x & 1) ^ 1) << 3));
			cost += PIXEL_READ;
		} else if (half_bg) {
			cost += PIXEL_READ;
		}

		if (!transparent) {
			unsigned const pos = (tvmr & TVMR_ROTATE) ? unsigned((x & 0x1ff) | ((y & 0x100) << 1)) : unsigned(x & 0x3ff);
			unsigned const sh = ((pos & 1) ^ 1) << 3;
			uint16_t &w = row[pos >> 1];
			w = uint16_t((w & ~(0xffU << sh)) | ((pix & 0xffU) << sh));
		}
		cost += PIXEL;
		return cost;
	}

	uint16_t &p = row[x & 0x1ff];
	bool const gouraud = g != nullptr;

	if (msb_on) {
		pix = p | 0x8000;
		cost += PIXEL_READ;
	} else if (half_bg) {
		uint16_t const bg = p;
		cost += PIXEL_READ;

		if (bg & 0x8000) {
			if (half_fg) {
				if (gouraud)
					pix = g->apply(pix);
				pix = uint16_t(((uint32_t(pix) + bg) - ((pix ^ bg) & 0x8421)) >> 1);
			} else {
				// DISAGREEMENT: Gouraud + shadow (colour calculation 101) draws black
				// (Mednafen, Ymir); MiSTer adds the Gouraud value to the halved background.
				if (gouraud)
					pix = 0;
				else
					pix = uint16_t(((bg & 0x7bde) >> 1) | (bg & 0x8000));
			}
		} else {
			if (half_fg) {
				if (gouraud)
					pix = g->apply(pix);
			} else {
				if (gouraud)
					pix = 0;
				else
					pix = bg;
			}
		}
	} else {
		if (gouraud)
			pix = g->apply(pix);
		if (half_fg)
			pix = uint16_t(((pix & 0x7bde) >> 1) | (pix & 0x8000));
	}

	if (!transparent)
		p = pix;
	cost += PIXEL;
	return cost;
}

int32_t draw_engine::adjust_timing(int32_t cycles)
{
	m_dta_counter += uint32_t(cycles) * ((tvmr & TVMR_8BPP) ? OVERHEAD_8BPP : OVERHEAD_16BPP);
	int32_t const extra = int32_t(m_dta_counter >> 8);
	m_dta_counter &= 0xff;
	return cycles + extra;
}

//**************************************************************************
//  Line drawing
//**************************************************************************

// Prepares to draw the line p0 -> p1. Returns true if pre-clipping reduced it
// to a single point.
bool draw_engine::setup_line(line_state &l, int32_t &cycles, vertex p0, vertex p1, bool aa, bool textured)
{
	unsigned const mode = m_prim.mode;
	bool const hss = mode & 0x1000;
	bool const pcd = mode & 0x800;
	bool const user_en = mode & 0x400;
	bool const user_mode = mode & 0x200;
	bool clipped = false;

	p0.x &= 0x1fff; p0.y &= 0x1fff;
	p1.x &= 0x1fff; p1.y &= 0x1fff;

	if (!pcd) {
		bool swapped;
		cycles += PRECLIP_TEST;

		if (user_en && !user_mode) {
			// the system clip is ignored by the pre-clip test in this case
			clipped |= (((user_x1 - p0.x) & (user_x1 - p1.x)) | ((p0.x - user_x0) & (p1.x - user_x0))) & 0x1000;
			clipped |= (((user_y1 - p0.y) & (user_y1 - p1.y)) | ((p0.y - user_y0) & (p1.y - user_y0))) & 0x1000;
			swapped = (p0.y == p1.y) && (p0.x < user_x0 || p0.x > user_x1);
		} else {
			clipped |= (((sys_x - p0.x) & (sys_x - p1.x)) | (p0.x & p1.x)) & 0x1000;
			clipped |= (((sys_y - p0.y) & (sys_y - p1.y)) | (p0.y & p1.y)) & 0x1000;
			swapped = (p0.y == p1.y) && (p0.x > sys_x);
		}

		// the hardware reduces a clipped line to its first point, which can
		// still be seen in the frame buffer for some coordinates
		if (clipped)
			p1 = p0;
		else if (swapped)
			std::swap(p0, p1);
	}
	cycles += LINE_SETUP;

	int32_t const dx = sext13(p1.x - p0.x);
	int32_t const dy = sext13(p1.y - p0.y);
	int32_t const adx = std::abs(dx), ady = std::abs(dy);
	int32_t const major = std::max(adx, ady);
	int32_t const x_inc = dx >= 0 ? 1 : -1;
	int32_t const y_inc = dy >= 0 ? 1 : -1;

	l.x = uint32_t(p0.x) & 0x7ff;
	l.y = uint32_t(p0.y) & 0x7ff;
	l.term_x = uint32_t(p1.x) & 0x7ff;
	l.term_y = uint32_t(p1.y) & 0x7ff;
	l.drawn_ac = true;
	l.colour = m_prim.colour;

	if (m_prim.gouraud)
		l.g.setup(major + 1, p0.g, p1.g);

	if (textured) {
		m_prim.ec_count = 2;
		if (major < std::abs(p1.t - p0.t) && hss) {
			m_prim.ec_count = 0x7fffffff;
			l.t.setup(major + 1, p0.t >> 1, p1.t >> 1, 2, (fbcr & FBCR_EOS) ? 1 : 0);
		} else {
			l.t.setup(major + 1, p0.t, p1.t);
		}
		l.texel = tex_fetch(uint32_t(l.t.t));
	}

	// Extra pixel drawn by anti-aliasing beside the main one
	if (ady > adx) {
		if (y_inc < 0) {
			l.aa_x = x_inc < 0 ? -1 : 0;
			l.aa_y = x_inc < 0 ? 1 : 0;
		} else {
			l.aa_x = x_inc < 0 ? 0 : 1;
			l.aa_y = x_inc < 0 ? 0 : -1;
		}
	} else {
		if (x_inc < 0) {
			l.aa_x = l.aa_y = y_inc < 0 ? 0 : 1;
		} else {
			l.aa_x = l.aa_y = y_inc < 0 ? -1 : 0;
		}
	}

	int32_t error, error_inc, error_adj, error_cmp = 0;
	if (ady > adx) {
		error_inc = 2 * adx;
		error_adj = -2 * ady;
		error = (ady - 2 * ady) - 1;
		if (dy < 0 && !aa)
			error_cmp--;
		error -= error_inc;
		l.y = uint32_t(int32_t(l.y) - y_inc) & 0x7ff;
		l.major_x = 0; l.major_y = y_inc;
		l.minor_x = x_inc; l.minor_y = 0;
	} else {
		error_inc = 2 * ady;
		error_adj = -2 * adx;
		error = (adx - 2 * adx) - 1;
		if (dx < 0 && !aa)
			error_cmp--;
		error -= error_inc;
		l.x = uint32_t(int32_t(l.x) - x_inc) & 0x7ff;
		l.major_x = x_inc; l.major_y = 0;
		l.minor_x = 0; l.minor_y = y_inc;
	}
	if (aa) {
		error++;
		error_cmp++;
	}

	l.error = int32_t(up(error));
	l.error_inc = int32_t(up(error_inc));
	l.error_adj = int32_t(up(error_adj));
	l.error_cmp = int32_t(up(error_cmp));

	return clipped;
}

int32_t draw_engine::draw_line(line_state &l, bool aa, bool textured)
{
	unsigned const mode = m_prim.mode;
	bool const spd = mode & 0x40;
	bool const ecd = mode & 0x80;
	bool const user_en = mode & 0x400;
	bool const user_mode = mode & 0x200;
	bool const row_cost = m_prim.fb_row;   // normal and scaled sprites only
	int32_t cost = 0;

	// Clip test of one dot; returns false when the line has to end here
	auto body = [&](uint32_t px, uint32_t py, uint16_t pix, bool transparent, bool aa_pixel) -> bool {
		bool clipped;
		if (user_en && !user_mode)
			clipped = px > uint32_t(user_x1 & 0x3ff) || px < uint32_t(user_x0 & 0x3ff) || py > uint32_t(user_y1 & 0x3ff) || py < uint32_t(user_y0 & 0x3ff);
		else
			clipped = px > uint32_t(sys_x & 0x3ff) || py > uint32_t(sys_y & 0x3ff);

		// once the line has been inside the window, leaving it ends the line
		if (clipped && !l.drawn_ac)
			return false;
		l.drawn_ac = l.drawn_ac && clipped;

		if (user_en) {
			if (!user_mode)
				clipped |= px > uint32_t(sys_x & 0x3ff) || py > uint32_t(sys_y & 0x3ff);
			else
				clipped |= !(px > uint32_t(user_x1 & 0x3ff) || px < uint32_t(user_x0 & 0x3ff) || py > uint32_t(user_y1 & 0x3ff) || py < uint32_t(user_y0 & 0x3ff));
		}

		stat_dots++;
		if (clipped)
			stat_clipped++;

		// pixel positions are in the 11 bit wrapped space; the frame buffer sees the low bits
		cost += plot(int32_t(px), int32_t(py), pix, transparent || clipped, m_prim.gouraud ? &l.g : nullptr);
		if (row_cost && !aa_pixel && ((int32_t(px) - local_x) & 0xf) == 0xf)
			cost += FB_ROW;
		return true;
	};

	for (;;) {
		bool transparent;
		uint16_t pix;

		if (cost >= cost_cap)
			return cost;

		if (textured) {
			while (l.t.pending()) {
				int32_t const tx = l.t.advance();
				l.texel = tex_fetch(uint32_t(tx));
				if (!ecd && m_prim.ec_count <= 0)
					return cost;
			}
			l.t.add_error();

			transparent = (spd && ecd) ? false : bool(l.texel >> 31);
			pix = uint16_t(l.texel);
		} else {
			pix = l.colour;
			transparent = false;
		}

		l.x = (l.x + uint32_t(l.major_x)) & 0x7ff;
		l.y = (l.y + uint32_t(l.major_y)) & 0x7ff;
		l.error = int32_t(uint32_t(l.error) + uint32_t(l.error_inc));
		if (l.error >= l.error_cmp) {
			l.error = int32_t(uint32_t(l.error) + uint32_t(l.error_adj));

			if (aa) {
				uint32_t const ax = (l.x + uint32_t(l.aa_x)) & 0x7ff;
				uint32_t const ay = (l.y + uint32_t(l.aa_y)) & 0x7ff;
				if (!body(ax, ay, pix, transparent, true))
					return cost;
			}

			l.x = (l.x + uint32_t(l.minor_x)) & 0x7ff;
			l.y = (l.y + uint32_t(l.minor_y)) & 0x7ff;
		}

		if (!body(l.x, l.y, pix, transparent, false))
			return cost;

		if (m_prim.gouraud)
			l.g.step();

		if (l.x == l.term_x && l.y == l.term_y)
			return cost;
	}
}

//**************************************************************************
//  Commands
//**************************************************************************

// Draws the fan of lines between two edges of a sprite or polygon
int32_t draw_engine::draw_fan(edge_stepper &e0, edge_stepper &e1, int32_t dmax, bool textured)
{
	int32_t cycles = 0;

	for (int32_t iter = dmax; iter >= 0 && cycles < cost_cap; iter--) {
		line_state l;
		vertex p0, p1;
		p0.x = e0.x; p0.y = e0.y; p0.g = e0.g.colour;
		p1.x = e1.x; p1.y = e1.y; p1.g = e1.g.colour;
		if (textured) {
			p0.t = m_prim.t0;
			p1.t = m_prim.t1;
			m_prim.tex_base = m_prim.tex_origin + uint32_t(m_prim.row_t.pre_step());
		}

		// lines that pre-clip away are skipped, except the last one
		bool const clipped = setup_line(l, cycles, p0, p1, true, textured);
		if (!clipped || !iter)
			cycles += adjust_timing(draw_line(l, true, textured));

		e0.step(m_prim.gouraud);
		e1.step(m_prim.gouraud);
	}
	return cycles;
}

int32_t draw_engine::execute(const uint16_t *cmd)
{
	switch (cmd[0] & 0xf) {
	case 0: return cmd_sprite(cmd, 0);
	case 1: return cmd_sprite(cmd, 1);
	case 2:
	case 3: return cmd_sprite(cmd, 2);
	case 4: return cmd_polygon(cmd);
	case 5:
	case 6:
	case 7: return cmd_lines(cmd);
	case 8:
	case 0xb:
		user_x0 = cmd[6] & 0x3ff;
		user_y0 = cmd[7] & 0x3ff;
		user_x1 = cmd[10] & 0x3ff;
		user_y1 = cmd[11] & 0x3ff;
		return 0;
	case 9:
		sys_x = cmd[10] & 0x3ff;
		sys_y = cmd[11] & 0x3ff;
		// MiSTer: setting the system clip also moves the lower right of the user clip
		user_x1 = sys_x;
		user_y1 = sys_y;
		return 0;
	case 0xa:
		// 13-bit signed like the vertices; ST-013 only guarantees -1024..1023 (Ymir agrees)
		local_x = sext13(cmd[6]);
		local_y = sext13(cmd[7]);
		return 0;
	default:
		return 0;
	}
}

// Gouraud table of a command: four colours at CMDGRDA * 8 bytes
static void read_gouraud(const uint16_t *vram, const uint16_t *cmd, uint32_t g[4])
{
	for (unsigned i = 0; i < 4; i++)
		g[i] = vram[((uint32_t(cmd[0xe]) << 2) + i) & 0x3ffff];
}

int32_t draw_engine::cmd_sprite(const uint16_t *cmd, unsigned format)
{
	unsigned const dir = (cmd[0] >> 4) & 3;
	unsigned const mode = cmd[2];
	unsigned const cm = (mode >> 3) & 7;
	uint16_t const colour = cmd[3];
	int32_t const w = ((cmd[5] >> 8) & 0x3f) << 3;
	int32_t const h = cmd[5] & 0xff;
	vertex p[4];
	int32_t cycles = 0;

	m_prim = primitive();
	m_prim.mode = uint16_t(mode);
	m_prim.textured = true;
	m_prim.aa = true;
	m_prim.gouraud = (mode & 0x8004) == 0x4;
	m_prim.colour = colour;
	m_prim.fb_row = format < 2;

	if (format == 2) {
		for (unsigned i = 0; i < 4; i++) {
			p[i].x = sext13(cmd[6 + 2 * i]) + local_x;
			p[i].y = sext13(cmd[7 + 2 * i]) + local_y;
		}
	} else if (format == 0) {
		p[0].x = sext13(cmd[6]) + local_x;
		p[0].y = sext13(cmd[7]) + local_y;
		p[1].x = p[0].x + (std::max(w, 1) - 1);
		p[1].y = p[0].y;
		p[2].x = p[1].x;
		p[2].y = p[0].y + (std::max(h, 1) - 1);
		p[3].x = p[0].x;
		p[3].y = p[2].y;
	} else {
		unsigned const zp = (cmd[0] >> 8) & 0xf;
		int32_t const zx = sext13(cmd[6]), zy = sext13(cmd[7]);
		int32_t const dw = sext13(cmd[8]), dh = sext13(cmd[9]);
		int32_t const ax = sext13(cmd[10]), ay = sext13(cmd[11]);

		for (unsigned i = 0; i < 4; i++) {
			p[i].x = zx;
			p[i].y = zy;
		}

		switch (zp >> 2) {
		case 0:
			p[2].y = ay;
			p[3].y = ay;
			break;
		case 1:
			p[2].y += dh;
			p[3].y += dh;
			break;
		case 2:
			p[0].y -= dh >> 1;
			p[1].y -= dh >> 1;
			p[2].y += (dh + 1) >> 1;
			p[3].y += (dh + 1) >> 1;
			break;
		case 3:
			p[0].y -= dh;
			p[1].y -= dh;
			break;
		}

		switch (zp & 3) {
		case 0:
			p[1].x = ax;
			p[2].x = ax;
			break;
		case 1:
			p[1].x += dw;
			p[2].x += dw;
			break;
		case 2:
			p[0].x -= dw >> 1;
			p[1].x += (dw + 1) >> 1;
			p[2].x += (dw + 1) >> 1;
			p[3].x -= dw >> 1;
			break;
		case 3:
			p[0].x -= dw;
			p[3].x -= dw;
			break;
		}

		for (unsigned i = 0; i < 4; i++) {
			p[i].x += local_x;
			p[i].y += local_y;
		}
	}

	if (mode & 4) {
		uint32_t g[4];
		read_gouraud(vram, cmd, g);
		cycles += GOURAUD_TABLE;
		for (unsigned i = 0; i < 4; i++)
			p[i].g = g[i];
	}

	// texture coordinates across the line: 0 to width - 1, mirrored by the horizontal flip
	{
		bool const h_inv = dir & 1;
		int32_t t[2];
		t[0 ^ h_inv] = 0;
		t[1 ^ h_inv] = w ? (w - 1) : 0;
		m_prim.t0 = t[0];
		m_prim.t1 = t[1];
	}

	switch (cm) {
	case 0: m_prim.colour_bank = colour & ~0xfU; break;
	case 1:
		for (unsigned i = 0; i < 16; i++)
			m_prim.clut[i] = vram[(((colour & ~3U) << 2) | i) & 0x3ffff];
		cycles += LOOKUP_TABLE;
		break;
	case 2: m_prim.colour_bank = colour & ~0x3fU; break;
	case 3: m_prim.colour_bank = colour & ~0x7fU; break;
	case 4: m_prim.colour_bank = colour & ~0xffU; break;
	default: break;
	}

	int32_t dmax = std::abs(sext13(p[3].x - p[0].x));
	dmax = std::max(dmax, std::abs(sext13(p[3].y - p[0].y)));
	dmax = std::max(dmax, std::abs(sext13(p[2].x - p[1].x)));
	dmax = std::max(dmax, std::abs(sext13(p[2].y - p[1].y)));
	dmax &= 0xfff;

	uint32_t tex_base = uint32_t(cmd[4]) << 2;
	if (cm == 5)
		tex_base &= ~7U;
	m_prim.tex_origin = tex_base;

	{
		bool const v_inv = dir & 2;
		int32_t tv[2];
		tv[0 ^ v_inv] = 0;
		tv[1 ^ v_inv] = h ? (h - 1) : 0;
		m_prim.row_t.setup(dmax + 1, tv[0], tv[1], w >> row_shift(cm));
	}

	edge_stepper e0, e1;
	e0.setup(m_prim.gouraud, p[0], p[3], dmax);
	e1.setup(m_prim.gouraud, p[1], p[2], dmax);
	return cycles + draw_fan(e0, e1, dmax, true);
}

int32_t draw_engine::cmd_polygon(const uint16_t *cmd)
{
	unsigned const mode = cmd[2];
	vertex p[4];
	int32_t cycles = 0;

	m_prim = primitive();
	m_prim.mode = uint16_t(mode);
	m_prim.textured = false;
	m_prim.aa = true;
	m_prim.gouraud = (mode & 0x8004) == 0x4;
	m_prim.colour = cmd[3];

	for (unsigned i = 0; i < 4; i++) {
		p[i].x = sext13(cmd[6 + 2 * i]) + local_x;
		p[i].y = sext13(cmd[7 + 2 * i]) + local_y;
	}
	if (mode & 4) {
		uint32_t g[4];
		read_gouraud(vram, cmd, g);
		cycles += GOURAUD_TABLE;
		for (unsigned i = 0; i < 4; i++)
			p[i].g = g[i];
	}

	int32_t dmax = std::abs(sext13(p[3].x - p[0].x));
	dmax = std::max(dmax, std::abs(sext13(p[3].y - p[0].y)));
	dmax = std::max(dmax, std::abs(sext13(p[2].x - p[1].x)));
	dmax = std::max(dmax, std::abs(sext13(p[2].y - p[1].y)));
	dmax &= 0xfff;

	edge_stepper e0, e1;
	e0.setup(m_prim.gouraud, p[0], p[3], dmax);
	e1.setup(m_prim.gouraud, p[1], p[2], dmax);
	return cycles + draw_fan(e0, e1, dmax, false);
}

// Line (one segment A-B) and polyline (A-B-C-D-A); not anti-aliased
int32_t draw_engine::cmd_lines(const uint16_t *cmd)
{
	unsigned const mode = cmd[2];
	unsigned const count = (cmd[0] & 1) ? 4 : 1;
	int32_t cycles = LINE_COMMAND;
	uint32_t g[4] = {};

	m_prim = primitive();
	m_prim.mode = uint16_t(mode);
	m_prim.textured = false;
	m_prim.aa = false;
	m_prim.gouraud = (mode & 0x8004) == 0x4;
	m_prim.colour = cmd[3];
	if (mode & 4)
		read_gouraud(vram, cmd, g);

	for (unsigned i = 0; i < count && cycles < cost_cap; i++) {
		vertex p0, p1;
		unsigned const a = i & 3, b = (i + 1) & 3;
		p0.x = sext13(cmd[6 + 2 * a] & 0x1fff) + local_x;
		p0.y = sext13(cmd[7 + 2 * a] & 0x1fff) + local_y;
		p1.x = sext13(cmd[6 + 2 * b] & 0x1fff) + local_x;
		p1.y = sext13(cmd[7 + 2 * b] & 0x1fff) + local_y;
		if (mode & 4) {
			cycles += LINE_GOURAUD;
			p0.g = g[a];
			p1.g = g[b];
		}

		line_state l;
		setup_line(l, cycles, p0, p1, false, false);
		cycles += adjust_timing(draw_line(l, false, false));
	}
	return cycles;
}

} // namespace saturn_vdp1

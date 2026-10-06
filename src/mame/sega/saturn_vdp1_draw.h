// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP1 drawing engine.

  Executes one command table at a time against the sprite RAM and the draw
  frame buffer and returns how many VDP1 clocks the command took. Sprites
  and polygons are drawn as a fan of anti-aliased lines between their left
  (A-D) and right (B-C) edges; lines and polylines are plain lines. Edge,
  line, texture and Gouraud stepping are Bresenham-style error accumulators
  exactly as the VDP1 hardware does them, so the pixels land where the
  hardware puts them (MiSTer Saturn core rtl/Saturn/VDP1/VDP1.sv, cross
  checked against Mednafen's hardware-tested behaviour).

  Where the references disagree the choice is labelled "DISAGREEMENT" in
  the source. Timing follows the model of saturn_vdp1_timing.h (Mednafen's
  structure with the MiSTer probe refit).
*/

#ifndef MAME_SEGA_SATURN_VDP1_DRAW_H
#define MAME_SEGA_SATURN_VDP1_DRAW_H

#pragma once

#include <cstdint>

namespace saturn_vdp1 {

constexpr unsigned VRAM_WORDS = 0x40000;   // 512KB sprite RAM
constexpr unsigned FB_WORDS = 0x20000;     // 256KB per frame buffer

// TVMR bits
constexpr unsigned TVMR_8BPP = 1, TVMR_ROTATE = 2, TVMR_HDTV = 4, TVMR_VBE = 8;
// FBCR bits
constexpr unsigned FBCR_FCT = 1, FBCR_FCM = 2, FBCR_DIL = 4, FBCR_DIE = 8, FBCR_EOS = 16;

class draw_engine
{
public:
	uint16_t *vram = nullptr;   // VRAM_WORDS
	uint16_t *fb = nullptr;     // draw frame buffer, FB_WORDS
	unsigned tvmr = 0, fbcr = 0;

	// The most clocks one command may take. Drawing ends at the next frame change, so no command
	// of the chip can go on longer than a frame; a command that would (a line whose end point is
	// never reached, as junk in the table gives) is cut at the cap instead of looping forever.
	int32_t cost_cap = INT32_MAX;

	void reset();

	// Runs the command table at cmd (16 words); returns the VDP1 clocks used
	int32_t execute(const uint16_t *cmd);

	// Diagnostics: dots the commands of this frame tried to plot and how many of those the
	// clipping rejected; cleared by the device at every frame change
	uint32_t stat_dots = 0, stat_clipped = 0;

	// Clip and coordinate state, retained across commands within a frame
	int32_t sys_x = 0, sys_y = 0;
	int32_t user_x0 = 0, user_y0 = 0, user_x1 = 0, user_y1 = 0;
	int32_t local_x = 0, local_y = 0;

private:
	struct vertex {
		int32_t x = 0, y = 0;
		uint32_t g = 0;    // Gouraud colour (15 bit RGB)
		int32_t t = 0;     // texture coordinate along the line
	};

	// Per channel Gouraud colour interpolation along a run of pixels
	struct gouraud_stepper {
		uint32_t colour = 0;
		uint32_t whole = 0;         // per-step increment when the run is shorter than the colour change
		int32_t inc[3] = {}, error[3] = {}, error_inc[3] = {}, error_adj[3] = {};
		void setup(unsigned length, uint32_t start, uint32_t end);
		void step();
		uint16_t apply(uint16_t pix) const;
	};

	// Texture coordinate stepper (one coordinate along a run)
	struct texture_stepper {
		int32_t t = 0, dir = 1, error = 0, error_inc = 0, error_adj = 0;
		void setup(unsigned length, int32_t start, int32_t end, int32_t scale = 1, int32_t fudge = 0);
		bool pending() const { return error >= 0; }
		int32_t advance() { t += dir; error -= error_adj; return t; }
		void add_error() { error += error_inc; }
		int32_t pre_step();
	};

	// Polygon/sprite edge between two vertices, stepped once per line of the fan
	struct edge_stepper {
		int32_t x = 0, y = 0, x_inc = 1, y_inc = 1;
		int32_t d_error = 0, d_error_inc = 0, d_error_adj = 0, d_error_cmp = 0;
		int32_t x_error = 0, x_error_inc = 0, x_error_adj = 0, x_error_cmp = 0;
		int32_t y_error = 0, y_error_inc = 0, y_error_adj = 0, y_error_cmp = 0;
		gouraud_stepper g;
		void setup(bool gouraud, vertex const &p0, vertex const &p1, int32_t dmax);
		void step(bool gouraud);
	};

	// The line currently being drawn
	struct line_state {
		uint32_t x = 0, y = 0;                 // current position (11 bit)
		uint32_t term_x = 0, term_y = 0;       // last position
		int32_t major_x = 0, major_y = 0;      // step along the major axis
		int32_t minor_x = 0, minor_y = 0;      // step along the minor axis
		int32_t aa_x = 0, aa_y = 0;            // extra anti-aliasing pixel offset
		int32_t error = 0, error_inc = 0, error_adj = 0, error_cmp = 0;
		bool drawn_ac = true;                  // nothing drawn inside the clip window yet
		uint32_t texel = 0;
		texture_stepper t;
		gouraud_stepper g;
		uint16_t colour = 0;
	};

	// Per command values shared by the lines of a primitive
	struct primitive {
		uint16_t mode = 0;
		bool textured = false, aa = false, gouraud = false;
		uint16_t colour = 0;
		uint32_t tex_base = 0;
		uint16_t clut[16] = {};
		uint32_t colour_bank = 0;
		int32_t ec_count = 0;
		bool fb_row = false;           // normal/scaled sprite: frame buffer row change cost
		texture_stepper row_t;         // texture row selection across the fan of lines
		int32_t t0 = 0, t1 = 0;        // texture coordinate at the two ends of every line
		uint32_t tex_origin = 0;       // texture address of row 0
	};

	primitive m_prim;
	uint32_t m_dta_counter = 0;   // draw timing overhead accumulator

	uint32_t tex_fetch(uint32_t x);
	bool setup_line(line_state &l, int32_t &cycles, vertex p0, vertex p1, bool aa, bool textured);
	int32_t draw_line(line_state &l, bool aa, bool textured);
	int32_t plot(int32_t x, int32_t y, uint16_t pix, bool transparent, gouraud_stepper *g);
	int32_t adjust_timing(int32_t cycles);

	int32_t cmd_sprite(const uint16_t *cmd, unsigned format);
	int32_t cmd_polygon(const uint16_t *cmd);
	int32_t cmd_lines(const uint16_t *cmd);
	int32_t draw_fan(edge_stepper &e0, edge_stepper &e1, int32_t dmax, bool textured);
};

} // namespace saturn_vdp1

#endif // MAME_SEGA_SATURN_VDP1_DRAW_H

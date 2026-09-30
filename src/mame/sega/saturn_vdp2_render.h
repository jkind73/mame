// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP2 line renderer.

  Composes the picture one output line at a time, dot by dot: each layer
  produces its dots for the line, then the dots are stacked by priority and
  mixed (saturn_vdp2_compose.h). This replaces the legacy renderer that
  painted whole layers in priority passes.

  Register decoding, scroll/zoom stepping, pattern name and cell fetching,
  windows, sprite data decoding and the layer enable rules follow the MiSTer
  Saturn core's RTL (rtl/Saturn/VDP2/VDP2.sv, VDP2_pkg.sv) and ST-058.

  The renderer is stateful across the lines of a frame (vertical coordinate
  accumulators, line scroll table pointers, mosaic counters): call
  begin_frame() and then render_line() for consecutive lines from 0.
*/

#ifndef MAME_SEGA_SATURN_VDP2_RENDER_H
#define MAME_SEGA_SATURN_VDP2_RENDER_H

#pragma once

#include "saturn_vdp2_compose.h"
#include "saturn_vdp2_fetch.h"

#include <array>
#include <cstdint>

namespace saturn_vdp2_render {

// Views of the VDP2 memories as the driver stores them.
struct memory {
	const uint16_t *regs = nullptr;  // 0x100 halfwords, register at byte offset n is regs[n / 2]
	const uint32_t *vram = nullptr;  // big-endian 32-bit words
	const uint32_t *cram = nullptr;  // 0x400 big-endian 32-bit words
	uint32_t vram_mask = 0x7ffff;    // byte address mask (512KB or 1MB)
};

struct screen_config {
	unsigned width = 320;   // output dots per line
	bool hires = false;     // HRES[1]: 640/704 dot modes
	unsigned hreso = 0;     // TVMD.HRESO
	bool exclusive = false; // HRESO bit 2: exclusive monitor modes (no VRAM access model)
	unsigned lsmd = 0;      // TVMD.LSMD interlace mode
	bool disp = true;       // TVMD.DISP
	bool bdclmd = false;    // TVMD.BDCLMD: DISP=0 shows the back screen instead of black
	bool pal = false;
	bool fb_rotate = false; // VDP1 frame buffer rotation: sprite dots come from rotation parameter A's coordinates
};

// Sprite frame buffer readout, supplied by the driver: the 16-bit VDP1 word
// that VDP2 sees at output dot (x, y).
class sprite_source {
public:
	virtual ~sprite_source() = default;
	virtual uint16_t sprite_word(unsigned x, unsigned y) const = 0;
	// frame buffer rotation mode: the word at frame buffer position (x, y)
	virtual uint16_t sprite_word_rotated(int32_t x, int32_t y) const { (void)x; (void)y; return 0; }
};

// Decoded register state (implementation detail, public so helpers can use it)
struct window_ctl {
	bool w0e = false, w0a = false, w1e = false, w1a = false, swe = false, swa = false, logic_and = false;
};

struct layer_ctl {
	unsigned priority = 0;
	unsigned caos = 0;
	unsigned ccrt = 0;
	bool ccen = false, coen = false, cosl = false, sden = false, lcen = false;
	unsigned sprm = 0, sccm = 0;
	bool sfcs = false;
	bool tpon = false;
	window_ctl win;
};

struct nbg_params {
	layer_ctl ctl;
	bool on = false;
	bool bitmap = false;
	unsigned cf = 0;              // 0 16 colours, 1 256, 2 2048, 3 32768, 4 16M
	bool cell2x2 = false;
	bool one_word = false;
	bool ext_char = false;
	unsigned plsz = 0;
	uint32_t map_base[4] = {};
	unsigned page_shift = 13;
	unsigned supp_char = 0;       // SPCN
	unsigned supp_pal = 0;        // SPLT << 4
	bool supp_pr = false, supp_cc = false;
	unsigned bitmap_w = 512, bitmap_h = 256;
	uint32_t bitmap_base = 0;
	unsigned bitmap_pal = 0;      // palette number bits 6-4 << 8
	bool bitmap_pr = false, bitmap_cc = false;
	uint32_t scroll_x = 0, scroll_y = 0; // 1/256 dot
	uint32_t inc_x = 0x100, inc_y = 0x100;
	bool zmhf = false, zmqt = false;     // NBG0/1 horizontal reduction limits
	bool mosaic = false;
	bool vcell = false;
	bool lsx = false, lsy = false, lzm = false;
	unsigned lss = 0;
	uint32_t ls_base = 0;
};

// Rotation parameter set A or B
struct rot_params {
	bool kte = false;             // coefficient table enable
	bool kdbs = false;            // coefficient data size: false 2 words, true 1 word
	bool klce = false;            // coefficient line colour enable
	unsigned kmd = 0;             // coefficient mode: 0 kx+ky, 1 kx, 2 ky, 3 viewpoint X
	unsigned ktaos = 0;           // coefficient table address offset
	unsigned plsz = 0;
	unsigned over = 0;            // screen over: 0 repeat, 1 repeat character, 2 transparent, 3 fixed 512x512
	unsigned ovpn = 0;
	unsigned mpofr = 0;
	unsigned map_index[16] = {};  // (MPOFR << 6) | MPx
};

struct decoded {
	unsigned crmd = 0;
	bool crkte = false;           // coefficient tables live in colour RAM
	unsigned ramctl = 0;
	uint16_t cyc[8] = {};         // VRAM cycle pattern registers A0L..B1U
	nbg_params nbg[4];
	bool r0on = false, r1on = false;
	nbg_params rbg[2];            // RBG0 and RBG1 (RBG1 takes NBG0's settings)
	rot_params rot[2];
	uint32_t rbg_map_base[2][2][16] = {}; // [layer][parameter set][plane]
	unsigned rpmd = 0;
	window_ctl rpwin;
	uint32_t rpta = 0;

	// sprite
	unsigned sp_type = 0;
	bool sp_clmd = false, sp_winen = false;
	unsigned sp_cccs = 0, sp_ccn = 0, sp_caos = 0;
	unsigned sp_pri[8] = {}, sp_ccrt[8] = {};
	bool tpsdsl = false;
	layer_ctl sp;
	layer_ctl r0;

	// windows
	unsigned wsx[2] = {}, wsy[2] = {}, wex[2] = {}, wey[2] = {};
	bool lwe[2] = {};
	uint32_t lwta[2] = {};
	window_ctl ccwin;

	// colour calculation
	bool ccmd = false, ccrtmd = false, exccen = false, boken = false;
	unsigned bokn = 0;
	bool lccen = false;
	unsigned lccrt = 0, bkccrt = 0;
	bool bkcoen = false, bkcosl = false, bksden = false;
	unsigned coa[3] = {}, cob[3] = {}; // R, G, B

	uint8_t sfcd[2] = {};

	uint32_t lcta = 0, bkta = 0;
	bool lc_per_line = false, bk_per_line = false;
	unsigned mosaic_h = 1, mosaic_v = 1;
};

class renderer {
public:
	static constexpr unsigned MAX_WIDTH = 704;

	void begin_frame(memory const &mem, screen_config const &cfg);

	// diagnostics: sprite layer dots read (non transparent) and left visible by the sprite window, this frame
	unsigned stat_sprite_dots = 0, stat_sprite_shown = 0;
	// refresh the memory views and screen settings between lines of a frame
	void set_config(memory const &mem, screen_config const &cfg) { m_mem = mem; m_cfg = cfg; }
	// RPRCTL was written: re-read Xst/Yst/KAst from the parameter table on the next line
	void rprctl_written(uint16_t data) { m_rprctl_pending |= data; }
	// dest receives cfg.width dots as 0x00RRGGBB
	void render_line(unsigned y, sprite_source const &sprite, uint32_t *dest);

private:
	// A layer's dot before priority resolution.
	struct layer_dot {
		bool opaque = false;
		bool palette = false; // colour came from colour RAM
		bool msb = false;     // colour data MSB (CRAM bit 15 / 31)
		bool cc = false;      // pattern name special colour calculation bit
		bool pr = false;      // pattern name special priority bit
		uint8_t code = 0;     // low 4 bits of the colour code, for special function matching
		uint32_t rgb = 0;
	};

	struct sprite_dot {
		bool palette = false;
		bool tp = true;
		bool wn = false;
		bool sd = false;
		unsigned pr = 0, cc = 0;
		uint32_t dc = 0;
	};

	struct nbg_state {
		uint32_t frac_y = 0;       // accumulated vertical coordinate, 1/256 dot
		uint32_t frac_x = 0;       // line scroll horizontal offset
		uint32_t inc_x = 0x100;    // horizontal step
		uint32_t ls_addr = 0;      // line scroll table read pointer
		unsigned mosaic_y = 0;
		bool mosaic_odd = false;   // double density: second frame line of the current field line
		bool have_line = false;
		saturn_vdp2_fetch::carry_state carry;
		layer_dot line[MAX_WIDTH];
	};

	struct rot_state {
		int32_t xst = 0, yst = 0;  // 16.16 start coordinates for the current line
		int64_t ka_y = 0;          // 19.16 coefficient address accumulated per line
		int32_t spr_xst = 0, spr_yst = 0;   // frame buffer rotation start, 11.9 fixed point
	};

	struct rot_line {
		int32_t x[MAX_WIDTH], y[MAX_WIDTH];
		bool transparent[MAX_WIDTH];
		uint8_t lcsd[MAX_WIDTH];
	};

	memory m_mem;
	screen_config m_cfg;
	nbg_state m_nbg[4];
	rot_state m_rot_state[2];
	rot_line m_rot_line[2];
	layer_dot m_rbg[2][MAX_WIDTH];
	int16_t m_r0_lcsd[MAX_WIDTH];
	int32_t m_spr_x[MAX_WIDTH], m_spr_y[MAX_WIDTH];   // frame buffer rotation coordinates per dot
	bool m_w_hit[2][MAX_WIDTH];
	unsigned m_rprctl_pending = 0;
	uint32_t m_back = 0, m_line_rgb = 0;

	uint8_t vram8(uint32_t addr) const;
	uint16_t vram16(uint32_t addr) const;
	uint32_t vram32(uint32_t addr) const;
	uint32_t cram_rgb(unsigned crmd, unsigned index, bool &msb) const;

	void decode(decoded &d) const;
	struct geometry {
		unsigned plane_bits;        // log2 of planes per axis: 1 for NBG (2x2), 2 for RBG (4x4)
		const uint32_t *map_base;   // byte address of each plane
		unsigned plsz;              // plane size in pages: 0 1x1, 1 2x1, 3 2x2
		uint32_t bitmap_base;
	};

	struct char_info {
		unsigned num = 0, pal = 0;
		bool cc = false, pr = false, flip_h = false, flip_v = false;
	};

	std::array<saturn_vdp2_fetch::cycle_dots, 90> m_fetched;

	static char_info decode_pn(nbg_params const &p, uint32_t pn);
	static uint32_t pn_address(nbg_params const &p, struct geometry const &g, uint32_t sx, uint32_t sy);
	static saturn_vdp2_fetch::schedule fetch_schedule(decoded const &d);
	layer_dot make_dot(decoded const &d, nbg_params const &p, uint32_t raw, unsigned pal, bool pr, bool cc) const;
	void draw_nbg_fetched(decoded const &d, unsigned n, nbg_state &s);
	layer_dot nbg_dot(decoded const &d, nbg_params const &p, geometry const &g, uint32_t sx, uint32_t sy, int repeat_pn, bool rdbs_gated = false) const;
	static bool rdbs_allows(decoded const &d, uint32_t address, unsigned role);
	void draw_nbg(decoded const &d, unsigned n, unsigned y);
	void finish_nbg(decoded const &d, unsigned n);
	void calc_rotation(decoded const &d, unsigned y, bool need_lines);
	void draw_rbg(decoded const &d, unsigned layer, unsigned y, bool const *rpw_hit);
	sprite_dot decode_sprite(decoded const &d, uint16_t data) const;
};

} // namespace saturn_vdp2_render

#endif // MAME_SEGA_SATURN_VDP2_RENDER_H

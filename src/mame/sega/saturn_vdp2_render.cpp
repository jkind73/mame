// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP2 line renderer. See saturn_vdp2_render.h.

  Reference: MiSTer Saturn core rtl/Saturn/VDP2/VDP2.sv and VDP2_pkg.sv
  (dot composition 3170-3540, windows 2143-2190, sprite data decoding
  VDP2_pkg 2245-2292), ST-058 for register layout and the scroll screen
  memory layout.
*/

#include "saturn_vdp2_render.h"

#include <algorithm>

namespace saturn_vdp2_render {

using namespace saturn_vdp2_compose;

namespace {

constexpr unsigned bits(unsigned v, unsigned hi, unsigned lo) { return (v >> lo) & ((1U << (hi - lo + 1)) - 1); }
constexpr bool flag(unsigned v, unsigned n) { return (v >> n) & 1; }

// Register offsets (bytes)
enum : unsigned {
	TVMD = 0x00, RAMCTL = 0x0e, BGON = 0x20, MZCTL = 0x22, SFSEL = 0x24, SFCODE = 0x26,
	CHCTLA = 0x28, CHCTLB = 0x2a, BMPNA = 0x2c, BMPNB = 0x2e, PNCN0 = 0x30, PLSZ = 0x3a,
	MPOFN = 0x3c, MPABN0 = 0x40, SCRCTL = 0x9a, VCSTAU = 0x9c, LSTA0U = 0xa0, LSTA1U = 0xa4,
	LCTAU = 0xa8, BKTAU = 0xac, WPSX0 = 0xc0, WCTLA = 0xd0, LWTA0U = 0xd8, LWTA1U = 0xdc,
	SPCTL = 0xe0, SDCTL = 0xe2, CRAOFA = 0xe4, CRAOFB = 0xe6, LNCLEN = 0xe8, SFPRMD = 0xea,
	CCCTL = 0xec, SFCCMD = 0xee, PRISA = 0xf0, PRINA = 0xf8, PRIR = 0xfc, CCRSA = 0x100,
	ZMCTL = 0x98, CCRNA = 0x108, CCRR = 0x10c, CCRLB = 0x10e, CLOFEN = 0x110, CLOFSL = 0x112, COAR = 0x114
};

// ST-058 / kMapIndexMasks: [cell 2x2][two-word][plane size]
constexpr unsigned map_index_mask[2][2][4] = {
	{ { 0x7f, 0x7e, 0x7e, 0x7c }, { 0x3f, 0x3e, 0x3e, 0x3c } },
	{ { 0x1ff, 0x1fe, 0x1fe, 0x1fc }, { 0xff, 0xfe, 0xfe, 0xfc } },
};
// page size in bytes, log2: [cell 2x2][two-word]
constexpr unsigned page_shift_table[2][2] = { { 13, 14 }, { 11, 12 } };

} // anonymous namespace

//**************************************************************************
//  Memory access
//**************************************************************************

uint8_t renderer::vram8(uint32_t addr) const
{
	addr &= m_mem.vram_mask;
	return (m_mem.vram[addr >> 2] >> (24 - 8 * (addr & 3))) & 0xff;
}

uint16_t renderer::vram16(uint32_t addr) const
{
	addr &= m_mem.vram_mask & ~1U;
	return (m_mem.vram[addr >> 2] >> (16 - 16 * ((addr >> 1) & 1))) & 0xffff;
}

uint32_t renderer::vram32(uint32_t addr) const
{
	return m_mem.vram[(addr & m_mem.vram_mask & ~3U) >> 2];
}

// Colour RAM lookup. Returns 0x00RRGGBB; RGB555 entries are zero-extended
// (ST-058 p.43), not bit-replicated.
uint32_t renderer::cram_rgb(unsigned crmd, unsigned index, bool &msb) const
{
	if (crmd >= 2) {
		uint32_t const d = m_mem.cram[index & 0x3ff];
		msb = d & 0x80000000;
		return ((d & 0xff) << 16) | (d & 0xff00) | ((d >> 16) & 0xff);
	}
	unsigned const w = index & (crmd == 0 ? 0x3ff : 0x7ff);
	uint16_t const c = (m_mem.cram[w >> 1] >> (16 - 16 * (w & 1))) & 0xffff;
	msb = c & 0x8000;
	return ((c & 0x1f) << 19) | (((c >> 5) & 0x1f) << 11) | (((c >> 10) & 0x1f) << 3);
}

//**************************************************************************
//  Register decode
//**************************************************************************

static window_ctl decode_window(unsigned v)
{
	window_ctl c;
	c.w0e = flag(v, 1); c.w0a = flag(v, 0); c.w1e = flag(v, 3); c.w1a = flag(v, 2);
	c.swe = flag(v, 5); c.swa = flag(v, 4); c.logic_and = flag(v, 7);
	return c;
}

void renderer::decode(decoded &d) const
{
	auto const R = [this](unsigned off) -> unsigned { return m_mem.regs[off >> 1]; };

	d.crmd = bits(R(RAMCTL), 13, 12);

	unsigned const bgon = R(BGON);
	unsigned const chctla = R(CHCTLA), chctlb = R(CHCTLB);
	unsigned const sfsel = R(SFSEL), sfprmd = R(SFPRMD), sfccmd = R(SFCCMD);
	unsigned const ccctl = R(CCCTL), clofen = R(CLOFEN), clofsl = R(CLOFSL);
	unsigned const sdctl = R(SDCTL), lnclen = R(LNCLEN), mzctl = R(MZCTL);
	unsigned const mpofn = R(MPOFN), plsz = R(PLSZ), scrctl = R(SCRCTL);
	unsigned const wctl[4] = { R(WCTLA), R(WCTLA + 2), R(WCTLA + 4), R(WCTLA + 6) };

	d.r1on = flag(bgon, 5);
	d.mosaic_h = bits(mzctl, 11, 8) + 1;
	d.mosaic_v = bits(mzctl, 15, 12) + 1;

	unsigned const prin[4] = { bits(R(PRINA), 2, 0), bits(R(PRINA), 10, 8), bits(R(PRINA + 2), 2, 0), bits(R(PRINA + 2), 10, 8) };
	unsigned const ccrn[4] = { bits(R(CCRNA), 4, 0), bits(R(CCRNA), 12, 8), bits(R(CCRNA + 2), 4, 0), bits(R(CCRNA + 2), 12, 8) };
	unsigned const caos[4] = { bits(R(CRAOFA), 2, 0), bits(R(CRAOFA), 6, 4), bits(R(CRAOFA), 10, 8), bits(R(CRAOFA), 14, 12) };

	for (unsigned n = 0; n < 4; n++) {
		nbg_params &p = d.nbg[n];
		p.on = flag(bgon, n);
		p.ctl.tpon = flag(bgon, 8 + n);
		p.ctl.priority = prin[n];
		p.ctl.caos = caos[n];
		p.ctl.ccrt = ccrn[n];
		p.ctl.ccen = flag(ccctl, n);
		p.ctl.coen = flag(clofen, n);
		p.ctl.cosl = flag(clofsl, n);
		p.ctl.sden = flag(sdctl, n);
		p.ctl.lcen = flag(lnclen, n);
		p.ctl.sprm = bits(sfprmd, 2 * n + 1, 2 * n);
		p.ctl.sccm = bits(sfccmd, 2 * n + 1, 2 * n);
		p.ctl.sfcs = flag(sfsel, n);
		p.ctl.win = decode_window(bits(wctl[n / 2], 8 * (n & 1) + 7, 8 * (n & 1)));
		p.mosaic = flag(mzctl, n);

		bool bmen;
		unsigned bmsz = 0;
		switch (n) {
		case 0:
			p.cell2x2 = flag(chctla, 0); bmen = flag(chctla, 1); bmsz = bits(chctla, 3, 2); p.cf = bits(chctla, 6, 4);
			break;
		case 1:
			p.cell2x2 = flag(chctla, 8); bmen = flag(chctla, 9); bmsz = bits(chctla, 11, 10); p.cf = bits(chctla, 13, 12);
			break;
		case 2:
			p.cell2x2 = flag(chctlb, 0); bmen = false; p.cf = flag(chctlb, 1);
			break;
		default:
			p.cell2x2 = flag(chctlb, 4); bmen = false; p.cf = flag(chctlb, 5);
			break;
		}
		p.bitmap = bmen;
		p.bitmap_w = (bmsz & 2) ? 1024 : 512;
		p.bitmap_h = (bmsz & 1) ? 512 : 256;

		unsigned const pnc = R(PNCN0 + 2 * n);
		p.one_word = flag(pnc, 15);
		p.ext_char = flag(pnc, 14);
		p.supp_pr = flag(pnc, 9);
		p.supp_cc = flag(pnc, 8);
		p.supp_pal = bits(pnc, 7, 5) << 4;
		p.supp_char = bits(pnc, 4, 0);

		p.plsz = bits(plsz, 2 * n + 1, 2 * n);
		unsigned const offs = bits(mpofn, 4 * n + 2, 4 * n);
		p.page_shift = page_shift_table[p.cell2x2][!p.one_word];
		unsigned const mask = map_index_mask[p.cell2x2][!p.one_word][p.plsz];
		for (unsigned pl = 0; pl < 4; pl++) {
			unsigned const reg = R(MPABN0 + 4 * n + 2 * (pl >> 1));
			unsigned const mp = bits(reg, 8 * (pl & 1) + 5, 8 * (pl & 1));
			p.map_base[pl] = (((offs << 6) | mp) & mask) << p.page_shift;
		}
		p.bitmap_base = offs << 17;
		if (n < 2) {
			unsigned const bmp = R(BMPNA);
			unsigned const s = 8 * n;
			p.bitmap_pal = bits(bmp, s + 2, s) << 8;
			p.bitmap_cc = flag(bmp, s + 4);
			p.bitmap_pr = flag(bmp, s + 5);
		}

		// scroll and zoom
		if (n < 2) {
			unsigned const b = 0x70 + 0x10 * n;
			p.scroll_x = (bits(R(b), 10, 0) << 8) | bits(R(b + 2), 15, 8);
			p.scroll_y = (bits(R(b + 4), 10, 0) << 8) | bits(R(b + 6), 15, 8);
			p.inc_x = (bits(R(b + 8), 2, 0) << 8) | bits(R(b + 10), 15, 8);
			p.inc_y = (bits(R(b + 12), 2, 0) << 8) | bits(R(b + 14), 15, 8);
			unsigned const s = 8 * n;
			p.vcell = flag(scrctl, s);
			p.lsx = flag(scrctl, s + 1);
			p.lsy = flag(scrctl, s + 2);
			p.lzm = flag(scrctl, s + 3);
			p.lss = bits(scrctl, s + 5, s + 4);
			p.zmhf = flag(R(0x98), s);
			p.zmqt = flag(R(0x98), s + 1);
			unsigned const l = n ? LSTA1U : LSTA0U;
			p.ls_base = ((bits(R(l), 2, 0) << 16) | R(l + 2)) << 1;
		} else {
			unsigned const b = 0x90 + 4 * (n - 2);
			p.scroll_x = bits(R(b), 10, 0) << 8;
			p.scroll_y = bits(R(b + 2), 10, 0) << 8;
			p.inc_x = p.inc_y = 0x100;
		}
	}

	// sprite
	unsigned const spctl = R(SPCTL);
	d.sp_type = bits(spctl, 3, 0);
	d.sp_winen = flag(spctl, 4);
	d.sp_clmd = flag(spctl, 5);
	d.sp_ccn = bits(spctl, 10, 8);
	d.sp_cccs = bits(spctl, 13, 12);
	d.sp_caos = bits(R(CRAOFB), 6, 4);
	for (unsigned i = 0; i < 8; i++) {
		unsigned const s = 8 * (i & 1);
		d.sp_pri[i] = bits(R(PRISA + 2 * (i >> 1)), s + 2, s);
		d.sp_ccrt[i] = bits(R(CCRSA + 2 * (i >> 1)), s + 4, s);
	}
	d.tpsdsl = flag(sdctl, 8);
	d.sp.ccen = flag(ccctl, 6);
	d.sp.coen = flag(clofen, 6);
	d.sp.cosl = flag(clofsl, 6);
	d.sp.lcen = flag(lnclen, 5);
	d.sp.sden = true;
	d.sp.win = decode_window(bits(wctl[2], 15, 8));

	// RBG0 controls (dots are produced by the rotation renderer)
	d.r0.priority = bits(R(PRIR), 2, 0);
	d.r0.caos = bits(R(CRAOFB), 2, 0);
	d.r0.ccrt = bits(R(CCRR), 4, 0);
	d.r0.ccen = flag(ccctl, 4);
	d.r0.coen = flag(clofen, 4);
	d.r0.cosl = flag(clofsl, 4);
	d.r0.sden = flag(sdctl, 4);
	d.r0.lcen = flag(lnclen, 4);
	d.r0.sprm = bits(sfprmd, 9, 8);
	d.r0.sccm = bits(sfccmd, 9, 8);
	d.r0.sfcs = flag(sfsel, 4);
	d.r0.tpon = flag(bgon, 12);
	d.r0.win = decode_window(bits(wctl[2], 7, 0));

	// windows
	for (unsigned w = 0; w < 2; w++) {
		unsigned const b = WPSX0 + 8 * w;
		d.wsx[w] = bits(R(b), 9, 0);
		d.wsy[w] = bits(R(b + 2), 8, 0);
		d.wex[w] = bits(R(b + 4), 9, 0);
		d.wey[w] = bits(R(b + 6), 8, 0);
		unsigned const l = w ? LWTA1U : LWTA0U;
		d.lwe[w] = flag(R(l), 15);
		d.lwta[w] = ((bits(R(l), 2, 0) << 16) | (R(l + 2) & 0xfffe)) ;
	}
	d.ccwin = decode_window(bits(wctl[3], 15, 8));

	// colour calculation
	d.ccmd = flag(ccctl, 8);
	d.ccrtmd = flag(ccctl, 9);
	d.exccen = flag(ccctl, 10);
	d.bokn = bits(ccctl, 14, 12);
	d.boken = flag(ccctl, 15);
	d.lccen = flag(ccctl, 5);
	d.lccrt = bits(R(CCRLB), 4, 0);
	d.bkccrt = bits(R(CCRLB), 12, 8);
	d.bkcoen = flag(clofen, 5);
	d.bkcosl = flag(clofsl, 5);
	d.bksden = flag(sdctl, 5);
	for (unsigned c = 0; c < 3; c++) {
		d.coa[c] = bits(R(COAR + 2 * c), 8, 0);
		d.cob[c] = bits(R(COAR + 6 + 2 * c), 8, 0);
	}
	d.sfcd[0] = R(SFCODE) & 0xff;
	d.sfcd[1] = R(SFCODE) >> 8;

	d.lcta = (((bits(R(LCTAU), 2, 0) << 16) | R(LCTAU + 2)) << 1);
	d.lc_per_line = flag(R(LCTAU), 15);
	d.bkta = (((bits(R(BKTAU), 2, 0) << 16) | R(BKTAU + 2)) << 1);
	d.bk_per_line = flag(R(BKTAU), 15);
}

//**************************************************************************
//  Frame / line
//**************************************************************************

void renderer::begin_frame(memory const &mem, screen_config const &cfg)
{
	m_mem = mem;
	m_cfg = cfg;

	decoded d;
	decode(d);
	for (unsigned n = 0; n < 4; n++) {
		nbg_state &s = m_nbg[n];
		s.frac_y = 0;
		s.frac_x = 0;
		s.inc_x = d.nbg[n].inc_x;
		s.mosaic_y = 0;
		s.ls_addr = d.nbg[n].ls_base;
		s.have_line = false;
	}
}

//--------------------------------------------------------------------------
//  Normal scroll screen dot fetch
//--------------------------------------------------------------------------

renderer::layer_dot renderer::nbg_dot(decoded const &d, nbg_params const &p, uint32_t sx, uint32_t sy) const
{
	layer_dot out;

	uint32_t base;         // cell / bitmap byte address
	unsigned dot_x, dot_y; // within cell (8x8) or bitmap
	unsigned pitch;
	unsigned pal = 0;      // colour code high bits, already positioned
	bool pr = false, cc = false;

	if (p.bitmap) {
		dot_x = sx & (p.bitmap_w - 1);
		dot_y = sy & (p.bitmap_h - 1);
		base = p.bitmap_base;
		pitch = p.bitmap_w;
		pal = p.bitmap_pal;
		pr = p.bitmap_pr;
		cc = p.bitmap_cc;
	} else {
		unsigned const psh_h = p.plsz & 1, psh_v = p.plsz >> 1;
		unsigned const plane = ((sx >> (9 + psh_h)) & 1) | (((sy >> (9 + psh_v)) & 1) << 1);
		unsigned const page = ((sx >> 9) & psh_h) | (((sy >> 9) & psh_v) << 1);
		unsigned const c2 = p.cell2x2 ? 1 : 0;
		unsigned const cx = bits(sx, 8, 3) >> c2, cy = bits(sy, 8, 3) >> c2;
		unsigned const index = cx + (cy << (6 - c2));
		uint32_t const page_addr = p.map_base[plane] + (page << p.page_shift);

		unsigned char_num, flip_h, flip_v;
		if (!p.one_word) {
			uint32_t const pn = vram32(page_addr + index * 4);
			char_num = pn & 0x7fff;
			pal = bits(pn, 22, 16) << 4;
			cc = flag(pn, 28);
			pr = flag(pn, 29);
			flip_h = flag(pn, 30);
			flip_v = flag(pn, 31);
		} else {
			unsigned const pn = vram16(page_addr + index * 2);
			unsigned const ext = p.ext_char ? 1 : 0;
			unsigned const base_num = bits(pn, 9 + 2 * ext, 0);
			unsigned const supp_lo = 2 * c2 + 2 * ext;
			char_num = (base_num << (2 * c2)) | (bits(p.supp_char, 4, supp_lo) << (10 + supp_lo));
			if (c2)
				char_num |= p.supp_char & 3;
			if (p.cf == 0)
				pal = bits(pn, 15, 12) | p.supp_pal;
			else
				pal = bits(pn, 14, 12) << 4;
			pal <<= 4;
			cc = p.supp_cc;
			pr = p.supp_pr;
			flip_h = p.ext_char ? 0 : flag(pn, 10);
			flip_v = p.ext_char ? 0 : flag(pn, 11);
		}

		dot_x = sx & 7;
		dot_y = sy & 7;
		unsigned cell_x = c2 ? ((sx >> 3) & 1) : 0, cell_y = c2 ? ((sy >> 3) & 1) : 0;
		if (flip_h) { dot_x ^= 7; cell_x ^= c2; }
		if (flip_v) { dot_y ^= 7; cell_y ^= c2; }
		static constexpr unsigned cell_units_shift[5] = { 0, 1, 2, 2, 3 };
		base = (char_num + ((cell_x + (cell_y << 1)) << cell_units_shift[p.cf])) << 5;
		pitch = 8;
	}

	unsigned const off = dot_x + dot_y * pitch;
	unsigned code = 0;
	bool opaque = true;
	bool palette = true;
	uint32_t rgb = 0;

	switch (p.cf) {
	case 0: {
		unsigned const dot = (vram8(base + (off >> 1)) >> ((~dot_x & 1) * 4)) & 0xf;
		opaque = dot || p.ctl.tpon;
		code = pal | dot;
		out.code = dot;
		break;
	}
	case 1: {
		unsigned const dot = vram8(base + off);
		opaque = dot || p.ctl.tpon;
		code = (pal & 0x700) | dot;
		out.code = dot & 0xf;
		break;
	}
	case 2: {
		unsigned const dot = vram16(base + off * 2) & 0x7ff;
		opaque = dot || p.ctl.tpon;
		code = dot;
		out.code = dot & 0xf;
		break;
	}
	case 3: {
		unsigned const c = vram16(base + off * 2);
		opaque = (c & 0x8000) || p.ctl.tpon;
		rgb = ((c & 0x1f) << 19) | (((c >> 5) & 0x1f) << 11) | (((c >> 10) & 0x1f) << 3);
		palette = false;
		out.msb = true;
		out.code = rgb & 0xf;
		break;
	}
	default: {
		uint32_t const c = vram32(base + off * 4);
		opaque = (c & 0x80000000) || p.ctl.tpon;
		rgb = ((c & 0xff) << 16) | (c & 0xff00) | ((c >> 16) & 0xff);
		palette = false;
		out.msb = true;
		out.code = rgb & 0xf;
		break;
	}
	}

	out.opaque = opaque;
	out.palette = palette;
	out.pr = pr;
	out.cc = cc;
	if (opaque && palette) {
		bool msb;
		out.rgb = cram_rgb(d.crmd, (code + (p.ctl.caos << 8)) & 0x7ff, msb);
		out.msb = msb;
	} else {
		out.rgb = rgb;
	}
	return out;
}

//--------------------------------------------------------------------------
//  One normal scroll screen line
//--------------------------------------------------------------------------

void renderer::draw_nbg(decoded const &d, unsigned n, unsigned y)
{
	nbg_params const &p = d.nbg[n];
	nbg_state &s = m_nbg[n];

	// per line scroll / zoom table (NBG0/1): one entry per 1 << LSS lines
	if (!p.lzm)
		s.inc_x = p.inc_x;
	if (n < 2 && (p.lsx || p.lsy || p.lzm) && (y & ((1U << p.lss) - 1)) == 0) {
		if (p.lsx) { s.frac_x = bits(vram32(s.ls_addr), 26, 8); s.ls_addr += 4; }
		if (p.lsy) { s.frac_y = bits(vram32(s.ls_addr), 26, 8); s.ls_addr += 4; }
		if (p.lzm) { s.inc_x = bits(vram32(s.ls_addr), 18, 8); s.ls_addr += 4; }
	}

	// mosaic: the first line of a group is drawn, the others repeat it
	if (p.mosaic && s.mosaic_y > 0 && s.have_line)
		return;

	// vertical cell scroll table (NBG0/1); with both enabled the entries alternate
	bool const vcs = n < 2 && p.vcell;
	uint32_t vcs_addr = 0;
	unsigned vcs_stride = 4;
	if (vcs) {
		unsigned const vh = m_mem.regs[VCSTAU >> 1], vl = m_mem.regs[(VCSTAU + 2) >> 1];
		vcs_addr = (((vh & 7) << 16) | vl) << 1;
		if (d.nbg[0].vcell && d.nbg[1].vcell) {
			vcs_stride = 8;
			if (n == 1)
				vcs_addr += 4;
		}
	}

	uint32_t fx = s.frac_x + p.scroll_x;
	unsigned const first_cell = fx >> 11;
	unsigned last_cell = first_cell;
	uint32_t vcell_y = vcs ? bits(vram32(vcs_addr), 26, 8) : 0;
	unsigned mosaic_x = 0;

	for (unsigned x = 0; x < m_cfg.width; x++) {
		if (p.mosaic) {
			unsigned const cur = mosaic_x;
			mosaic_x = (mosaic_x + 1 >= d.mosaic_h) ? 0 : mosaic_x + 1;
			if (cur > 0) {
				s.line[x] = s.line[x - 1];
				fx += s.inc_x;
				continue;
			}
		}
		if (vcs) {
			unsigned const cell = fx >> 11;
			if (cell != last_cell) {
				last_cell = cell;
				vcell_y = bits(vram32(vcs_addr + ((cell - first_cell) & 0x7f) * vcs_stride), 26, 8);
			}
		}
		s.line[x] = nbg_dot(d, p, fx >> 8, (s.frac_y + p.scroll_y + vcell_y) >> 8);
		fx += s.inc_x;
	}
	s.have_line = true;
}

// End of line: advance the vertical coordinate and mosaic counter
void renderer::finish_nbg(decoded const &d, unsigned n)
{
	nbg_params const &p = d.nbg[n];
	nbg_state &s = m_nbg[n];
	s.frac_y += p.inc_y;
	if (p.mosaic)
		s.mosaic_y = (s.mosaic_y + 1 >= d.mosaic_v) ? 0 : s.mosaic_y + 1;
}

//--------------------------------------------------------------------------
//  Sprite dot (VDP2_pkg.sv SpriteData)
//--------------------------------------------------------------------------

renderer::sprite_dot renderer::decode_sprite(decoded const &d, uint16_t data) const
{
	unsigned const type = d.sp_type;
	bool msb = false, nsd = false, tpen = false;
	unsigned pr = 0, cc = 0, dc = 0;
	auto const bit = [data](unsigned n) -> unsigned { return (data >> n) & 1; };
	auto const all_ones = [data](unsigned hi, unsigned lo) { unsigned const m = ((1U << (hi - lo + 1)) - 1) << lo; return (data & m) == m; };

	switch (type) {
	case 0x0: msb = 0; nsd = all_ones(10, 1) && !bit(0); tpen = 0; pr = (bit(15) << 1) | bit(14); cc = bits(data, 13, 11); dc = data & 0x7ff; break;
	case 0x1: msb = 0; nsd = all_ones(10, 1) && !bit(0); tpen = 0; pr = bits(data, 15, 13); cc = bits(data, 12, 11); dc = data & 0x7ff; break;
	case 0x2: msb = bit(15); nsd = all_ones(10, 1) && !bit(0); tpen = bit(15); pr = bit(14); cc = bits(data, 13, 11); dc = data & 0x7ff; break;
	case 0x3: msb = bit(15); nsd = all_ones(10, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 13); cc = bits(data, 12, 11); dc = data & 0x7ff; break;
	case 0x4: msb = bit(15); nsd = all_ones(9, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 13); cc = bits(data, 12, 10); dc = data & 0x3ff; break;
	case 0x5: msb = bit(15); nsd = all_ones(10, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 12); cc = bit(11); dc = data & 0x7ff; break;
	case 0x6: msb = bit(15); nsd = all_ones(9, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 12); cc = bits(data, 11, 10); dc = data & 0x3ff; break;
	case 0x7: msb = bit(15); nsd = all_ones(8, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 12); cc = bits(data, 11, 9); dc = data & 0x1ff; break;
	case 0x8: msb = 0; nsd = all_ones(6, 1) && !bit(0); tpen = 1; pr = bit(7); cc = 0; dc = data & 0x7f; break;
	case 0x9: msb = 0; nsd = all_ones(5, 1) && !bit(0); tpen = 1; pr = bit(7); cc = bit(6); dc = data & 0x3f; break;
	case 0xa: msb = 0; nsd = all_ones(5, 1) && !bit(0); tpen = 1; pr = bits(data, 7, 6); cc = 0; dc = data & 0x3f; break;
	case 0xb: msb = 0; nsd = all_ones(5, 1) && !bit(0); tpen = 1; pr = 0; cc = bits(data, 7, 6); dc = data & 0x3f; break;
	case 0xc: msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = bit(7); cc = 0; dc = data & 0xff; break;
	case 0xd: msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = bit(7); cc = bit(6); dc = data & 0xff; break;
	case 0xe: msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = bits(data, 7, 6); cc = 0; dc = data & 0xff; break;
	default:  msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = 0; cc = bits(data, 7, 6); dc = data & 0xff; break;
	}

	bool const type8 = type & 8;
	bool const tp = !(((data & 0x7f00) && !type8) || (data & 0xff));
	bool const rgb_tp = type8 ? tp : (tp && tpen && d.sp_winen);
	bool const msd = msb && !tp && !d.sp_winen;
	bool const tsd = msb && tp && d.tpsdsl && !d.sp_winen;
	bool const pal_tp = tp || nsd || tsd;

	sprite_dot s;
	if (d.sp_clmd && bit(15)) {
		s.palette = false;
		s.tp = rgb_tp;
		s.wn = false;
		s.sd = false;
		s.pr = 0;
		s.cc = 0;
		s.dc = ((data & 0x1f) << 19) | (((data >> 5) & 0x1f) << 11) | (((data >> 10) & 0x1f) << 3);
	} else {
		s.palette = true;
		s.tp = pal_tp;
		s.wn = msb;
		s.sd = nsd || msd || tsd;
		s.pr = pr;
		s.cc = cc;
		s.dc = dc;
	}
	return s;
}

//--------------------------------------------------------------------------
//  Windows
//--------------------------------------------------------------------------

// VDP2_pkg.sv WinTest: a layer is hidden where this is true
static bool win_test(bool w0hit, bool w1hit, bool wshit, window_ctl const &c)
{
	if (!c.w0e && !c.w1e && !c.swe)
		return false;
	if (c.logic_and)
		return (!c.w0e || w0hit) && (!c.w1e || w1hit) && (!c.swe || wshit);
	return (c.w0e && w0hit) || (c.w1e && w1hit) || (c.swe && wshit);
}

// NBG0 CHCN[0] with half reduction, or quarter reduction (VDP2.sv 3193-3194)
static bool nbg_reduced(nbg_params const &p)
{
	return ((p.cf == 1 || p.cf == 3) && p.zmhf) || p.zmqt;
}

// Priority number of a layer's dot (VDP2.sv 3208-3214): special priority
// replaces bit 0 of the layer's priority per character or per dot
static unsigned layer_priority(decoded const &d, layer_ctl const &c, bool pr, unsigned code)
{
	if (c.sprm == 1)
		return (c.priority & 6) | pr;
	if (c.sprm == 2) {
		bool const sfc = (d.sfcd[c.sfcs] >> ((code >> 1) & 7)) & 1;
		return (c.priority & 6) | (pr && sfc);
	}
	return c.priority;
}

//--------------------------------------------------------------------------
//  Line composition
//--------------------------------------------------------------------------

void renderer::render_line(unsigned y, sprite_source const &sprite, uint32_t *dest)
{
	decoded d;
	decode(d);

	unsigned const width = m_cfg.width;
	bool const ddi = m_cfg.lsmd == 3;
	bool const hires = m_cfg.hires;

	// back screen and line colour screen for this line
	{
		unsigned const c = vram16(d.bkta + (d.bk_per_line ? y * 2 : 0));
		m_back = ((c & 0x1f) << 19) | (((c >> 5) & 0x1f) << 11) | (((c >> 10) & 0x1f) << 3);
		bool msb;
		m_line_rgb = cram_rgb(d.crmd, vram16(d.lcta + (d.lc_per_line ? y * 2 : 0)) & 0x7ff, msb);
	}

	if (!m_cfg.disp) {
		std::fill_n(dest, width, m_cfg.bdclmd ? m_back : 0U);
		for (unsigned n = 0; n < 4; n++)
			finish_nbg(d, n);
		return;
	}

	// scroll screens. NBG0 gives way to RBG1; the colour depth of NBG0/1
	// and the reduction settings decide which of NBG1-3 have VRAM cycles left.
	bool nbg_on[4];
	nbg_on[0] = d.nbg[0].on && !d.r1on;
	nbg_on[1] = d.nbg[1].on && d.nbg[0].cf < 4;
	nbg_on[2] = d.nbg[2].on && d.nbg[0].cf < 2 && !nbg_reduced(d.nbg[0]);
	nbg_on[3] = d.nbg[3].on && d.nbg[0].cf < 4 && d.nbg[1].cf < 2 && !nbg_reduced(d.nbg[1]);
	for (unsigned n = 0; n < 4; n++)
		if (nbg_on[n])
			draw_nbg(d, n, y);

	// window geometry for this line
	bool wy_hit[2];
	unsigned wsx[2], wex[2];
	for (unsigned w = 0; w < 2; w++) {
		wsx[w] = d.wsx[w];
		wex[w] = d.wex[w];
		if (d.lwe[w]) {
			uint32_t const e = vram32(d.lwta[w] + (ddi ? (y >> 1) : y) * 4);
			wsx[w] = bits(e, 25, 16);
			wex[w] = bits(e, 9, 0);
		}
		unsigned const sy = d.wsy[w], ey = d.wey[w];
		wy_hit[w] = (y >= sy && y <= ey && sy != 0x1fe && ey < 0x1fe) ||
				(ey >= (m_cfg.pal ? 0x100U : 0xf0U) && ey <= 0x1ed && !ddi);
	}

	// gradation neighbours (VDP2.sv 3452-3466)
	bool boken_prev1 = false, boken_prev2 = false;
	rgb csec_prev1, csec_prev2;
	bool const exccen = d.exccen && !d.boken;

	auto const to_rgb = [](uint32_t c) { return rgb{ uint8_t(c >> 16), uint8_t(c >> 8), uint8_t(c) }; };
	auto const from_rgb = [](rgb c) { return (uint32_t(c.r) << 16) | (uint32_t(c.g) << 8) | c.b; };
	unsigned const boken_layer_n[4] = { 2, 4, 5, 6 };

	for (unsigned x = 0; x < width; x++) {
		bool w_hit[2];
		for (unsigned w = 0; w < 2; w++) {
			// window coordinates are in half dots in the normal resolutions
			unsigned const px = hires ? x : (x << 1);
			unsigned const s = hires ? wsx[w] : (wsx[w] & ~1U);
			unsigned const e = hires ? wex[w] : (wex[w] & ~1U);
			w_hit[w] = (px >= s || wsx[w] >= 0x360) && px <= e && e < 0x360 && e != 0x2ec && wy_hit[w];
		}

		sprite_dot const sd = decode_sprite(d, sprite.sprite_word(x, y));
		bool const spwin = d.sp_winen;

		auto const hidden = [&](window_ctl c) {
			c.swe = c.swe && spwin;
			return win_test(w_hit[0] != c.w0a, w_hit[1] != c.w1a, sd.wn != c.swa, c);
		};
		bool const ccw = hidden(d.ccwin);
		bool const bok_ok = d.boken && d.crmd == 0;

		// sprite
		unsigned const sprin = d.sp_pri[sd.pr];
		layer_input in_spr;
		{
			screen_dot &t = in_spr.dot;
			in_spr.on = !sd.tp && !hidden(d.sp.win);
			in_spr.priority = sprin;
			t.caos = d.sp_caos;
			bool cond;
			switch (d.sp_cccs) {
			case 0: cond = sprin <= d.sp_ccn; break;
			case 1: cond = sprin == d.sp_ccn; break;
			case 2: cond = sprin >= d.sp_ccn; break;
			default: cond = true; break;
			}
			t.ccen = d.sp.ccen && !ccw && cond;
			t.ccm3 = d.sp_cccs == 3;
			t.ccrt = d.sp_ccrt[sd.cc];
			t.coen = d.sp.coen;
			t.cosl = d.sp.cosl;
			t.sden = sd.sd;
			t.boken = bok_ok && d.bokn == 0;
			t.lcen = d.sp.lcen;
			t.palette = sd.palette;
			if (sd.palette) {
				bool m;
				t.dc = cram_rgb(d.crmd, (sd.dc + (d.sp_caos << 8)) & 0x7ff, m);
				t.msb = m;
			} else {
				t.dc = sd.dc;
				t.msb = true;
			}
		}

		// scroll screens
		layer_input in_nbg[4];
		for (unsigned n = 0; n < 4; n++) {
			nbg_params const &p = d.nbg[n];
			layer_dot const &ld = m_nbg[n].line[x];
			layer_input &li = in_nbg[n];
			li.on = nbg_on[n] && ld.opaque && !hidden(p.ctl.win);
			li.priority = layer_priority(d, p.ctl, ld.pr, ld.code);
			screen_dot &t = li.dot;
			bool const sfc = (d.sfcd[p.ctl.sfcs] >> ((ld.code >> 1) & 7)) & 1;
			bool const ccen = p.ctl.sccm == 1 ? ld.cc : p.ctl.sccm == 2 ? (sfc && ld.cc) : true;
			t.caos = p.ctl.caos;
			t.ccen = ccen && p.ctl.ccen && !ccw;
			t.ccm3 = p.ctl.sccm == 3;
			t.ccrt = p.ctl.ccrt;
			t.coen = p.ctl.coen;
			t.cosl = p.ctl.cosl;
			t.sden = p.ctl.sden && sd.sd && sprin >= li.priority;
			t.boken = bok_ok && d.bokn == boken_layer_n[n];
			t.lcen = p.ctl.lcen;
			t.palette = ld.palette;
			t.msb = ld.msb;
			t.dc = ld.rgb;
		}
		layer_input in_r0; // RBG0/1 are not produced by this stage yet

		// priority stack; the back screen fills all three positions
		dot_stack st;
		{
			screen_dot b;
			b.ccrt = d.bkccrt;
			b.coen = d.bkcoen;
			b.cosl = d.bkcosl;
			b.sden = d.bksden && sd.sd;
			b.dc = m_back;
			for (auto &dot : st.dot)
				dot = b;
		}
		insert_layer(st, layer_kind::sprite, in_spr);
		insert_layer(st, layer_kind::rbg0, in_r0);
		for (unsigned n = 0; n < 4; n++)
			insert_layer(st, layer_kind::nbg, in_nbg[n]);

		// dots taking part in the mix (VDP2.sv 3396-3420)
		screen_dot const first = st.dot[0];
		screen_dot sec, thd, fth;
		if (first.boken) {
			sec = thd = fth = first;
		} else if (st.dot[1].boken) {
			sec = thd = fth = st.dot[1];
		} else if (first.lcen) {
			screen_dot lc;
			lc.ccen = d.lccen && !ccw;
			lc.ccrt = d.lccrt;
			lc.palette = true;
			lc.dc = m_line_rgb;
			sec = lc;
			thd = st.dot[1];
			fth = st.dot[2];
		} else {
			sec = st.dot[1];
			thd = st.dot[2];
		}

		// colour stage (VDP2.sv 3457-3520)
		rgb const cfst = to_rgb(first.dc);
		rgb csec = to_rgb(sec.dc);
		if (!hires) {
			rgb const cthd = boken_prev1 ? csec_prev1 : to_rgb(thd.dc);
			rgb const cfth = boken_prev2 ? csec_prev2 : to_rgb(fth.dc);
			csec = ext_color_calc(csec, sec.ccen, cthd, thd.palette, thd.ccen, cfth, first.lcen, sec.boken, d.crmd, exccen);
			boken_prev2 = boken_prev1;
			csec_prev2 = csec_prev1;
			boken_prev1 = sec.boken;
			csec_prev1 = to_rgb(sec.dc);
		}
		unsigned const ccrt = d.ccrtmd ? sec.ccrt : first.ccrt;
		bool ccen_first = !first.ccm3 ? first.ccen : (first.ccen && (first.msb || !first.palette));
		if (hires && d.crmd != 0 && sec.palette)
			ccen_first = false;
		rgb c = color_calc(cfst, csec, ccrt, ccen_first, d.ccmd);

		unsigned const *co = first.cosl ? d.cob : d.coa;
		c.r = shadow(color_offset(c.r, co[0], first.coen), first.sden);
		c.g = shadow(color_offset(c.g, co[1], first.coen), first.sden);
		c.b = shadow(color_offset(c.b, co[2], first.coen), first.sden);
		dest[x] = from_rgb(c);
	}

	for (unsigned n = 0; n < 4; n++)
		finish_nbg(d, n);
}

} // namespace saturn_vdp2_render

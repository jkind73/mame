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
	ZMCTL = 0x98, RPMD = 0xb0, KTCTL = 0xb4, KTAOF = 0xb6, OVPNRA = 0xb8, RPTAU = 0xbc, MPOFR = 0x3e, MPABRA = 0x50, PNCR = 0x38,
	CCRNA = 0x108, CCRR = 0x10c, CCRLB = 0x10e, CLOFEN = 0x110, CLOFSL = 0x112, COAR = 0x114
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
	d.crkte = flag(R(RAMCTL), 15);
	d.ramctl = R(RAMCTL);
	for (unsigned i = 0; i < 8; i++)
		d.cyc[i] = R(0x10 + 2 * i);

	unsigned const bgon = R(BGON);
	unsigned const chctla = R(CHCTLA), chctlb = R(CHCTLB);
	unsigned const sfsel = R(SFSEL), sfprmd = R(SFPRMD), sfccmd = R(SFCCMD);
	unsigned const ccctl = R(CCCTL), clofen = R(CLOFEN), clofsl = R(CLOFSL);
	unsigned const sdctl = R(SDCTL), lnclen = R(LNCLEN), mzctl = R(MZCTL);
	unsigned const mpofn = R(MPOFN), plsz = R(PLSZ), scrctl = R(SCRCTL);
	unsigned const wctl[4] = { R(WCTLA), R(WCTLA + 2), R(WCTLA + 4), R(WCTLA + 6) };

	d.r0on = flag(bgon, 4);
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
		if (p.plsz == 2)
			p.plsz = 3;
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

	// rotation parameter sets A and B: RPTA bit 6 is ignored, fixed to 0 for set A
	// and 1 for set B, so B follows A 0x80 bytes later (ST-058 6.3 rotation parameter
	// table address register; RTL: VDP2_pkg.sv RxRPAddr agrees)
	d.rpta = ((((bits(R(RPTAU), 2, 0)) << 16) | R(RPTAU + 2)) << 1) & ~0x83U;
	d.rpmd = bits(R(RPMD), 1, 0);
	d.rpwin = decode_window(bits(wctl[3], 7, 0));
	for (unsigned i = 0; i < 2; i++) {
		rot_params &rp = d.rot[i];
		unsigned const ktctl = R(KTCTL), ktaof = R(KTAOF), s8 = 8 * i;
		rp.kte = flag(ktctl, s8);
		rp.kdbs = flag(ktctl, s8 + 1);
		rp.kmd = bits(ktctl, s8 + 3, s8 + 2);
		rp.klce = flag(ktctl, s8 + 4);
		rp.ktaos = bits(ktaof, s8 + 2, s8);
		rp.plsz = bits(plsz, 4 * i + 9, 4 * i + 8);
		if (rp.plsz == 2)
			rp.plsz = 3;
		rp.over = bits(plsz, 4 * i + 11, 4 * i + 10);
		rp.ovpn = R(OVPNRA + 2 * i);
		rp.mpofr = bits(R(MPOFR), 4 * i + 2, 4 * i);
		for (unsigned pl = 0; pl < 16; pl++) {
			unsigned const reg = R(MPABRA + 0x10 * i + 2 * (pl >> 1));
			rp.map_index[pl] = (rp.mpofr << 6) | bits(reg, 8 * (pl & 1) + 5, 8 * (pl & 1));
		}
	}

	// RBG0 character settings; RBG1 takes NBG0's
	{
		nbg_params &r = d.rbg[0];
		r.ctl = d.r0;
		r.on = d.r0on;
		r.cell2x2 = flag(chctlb, 8);
		r.bitmap = flag(chctlb, 9);
		r.bitmap_w = 512;
		r.bitmap_h = flag(chctlb, 10) ? 512 : 256;
		r.cf = bits(chctlb, 14, 12);
		r.mosaic = flag(mzctl, 4);
		unsigned const pnc = R(PNCR);
		r.one_word = flag(pnc, 15);
		r.ext_char = flag(pnc, 14);
		r.supp_pr = flag(pnc, 9);
		r.supp_cc = flag(pnc, 8);
		r.supp_pal = bits(pnc, 7, 5) << 4;
		r.supp_char = bits(pnc, 4, 0);
		r.page_shift = page_shift_table[r.cell2x2][!r.one_word];
		unsigned const bmp = R(BMPNB);
		r.bitmap_pal = bits(bmp, 2, 0) << 8;
		r.bitmap_cc = flag(bmp, 4);
		r.bitmap_pr = flag(bmp, 5);
		d.rbg[1] = d.nbg[0];
		d.rbg[1].on = d.r1on;
		for (unsigned l = 0; l < 2; l++)
			for (unsigned i = 0; i < 2; i++) {
				nbg_params const &q = d.rbg[l];
				unsigned const mask = map_index_mask[q.cell2x2][!q.one_word][d.rot[i].plsz];
				for (unsigned pl = 0; pl < 16; pl++)
					d.rbg_map_base[l][i][pl] = (d.rot[i].map_index[pl] & mask) << q.page_shift;
			}
	}

	// windows
	for (unsigned w = 0; w < 2; w++) {
		unsigned const b = WPSX0 + 8 * w;
		d.wsx[w] = bits(R(b), 9, 0);
		d.wsy[w] = bits(R(b + 2), 8, 0);
		d.wex[w] = bits(R(b + 4), 9, 0);
		d.wey[w] = bits(R(b + 6), 8, 0);
		unsigned const l = w ? LWTA1U : LWTA0U;
		d.lwe[w] = flag(R(l), 15);
		// line window table address: the 18-bit register value (bits 18-1) times 4, the
		// same format as the line scroll table address (ST-058 8.1, p.187)
		d.lwta[w] = ((bits(R(l), 2, 0) << 16) | (R(l + 2) & 0xfffe)) << 1;
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
		s.mosaic_odd = false;
		s.ls_addr = d.nbg[n].ls_base;
		s.have_line = false;
		s.carry.pn_fetched = false;
	}
	for (auto &r : m_rot_state)
		r = rot_state();
	m_rprctl_pending = 0;
}

//--------------------------------------------------------------------------
//  Normal scroll screen dot fetch
//--------------------------------------------------------------------------

// Pattern name data to character number (in 32 byte units), flips, palette
// and the special priority / colour calculation bits (ST-058 pp.69-75).
// `pn` is the 32-bit word for two-word names and the 16-bit word otherwise.
renderer::char_info renderer::decode_pn(nbg_params const &p, uint32_t pn)
{
	char_info c;
	if (!p.one_word) {
		c.num = pn & 0x7fff;
		c.pal = bits(pn, 22, 16) << 4;
		c.cc = flag(pn, 28);
		c.pr = flag(pn, 29);
		c.flip_h = flag(pn, 30);
		c.flip_v = flag(pn, 31);
	} else {
		unsigned const c2 = p.cell2x2 ? 1 : 0;
		unsigned const ext = p.ext_char ? 1 : 0;
		unsigned const base_num = bits(pn, 9 + 2 * ext, 0);
		unsigned const supp_lo = 2 * c2 + 2 * ext;
		c.num = (base_num << (2 * c2)) | (bits(p.supp_char, 4, supp_lo) << (10 + supp_lo));
		if (c2)
			c.num |= p.supp_char & 3;
		unsigned pal;
		if (p.cf == 0)
			pal = bits(pn, 15, 12) | p.supp_pal;
		else
			pal = bits(pn, 14, 12) << 4;
		c.pal = pal << 4;
		c.cc = p.supp_cc;
		c.pr = p.supp_pr;
		c.flip_h = !ext && flag(pn, 10);
		c.flip_v = !ext && flag(pn, 11);
	}
	return c;
}

// Byte address of the pattern name covering source dot (sx, sy)
uint32_t renderer::pn_address(nbg_params const &p, geometry const &g, uint32_t sx, uint32_t sy)
{
	unsigned const psh_h = g.plsz & 1, psh_v = g.plsz >> 1;
	unsigned const plane_mask = (1U << g.plane_bits) - 1;
	unsigned const plane = ((sx >> (9 + psh_h)) & plane_mask) | (((sy >> (9 + psh_v)) & plane_mask) << g.plane_bits);
	unsigned const page = ((sx >> 9) & psh_h) | (((sy >> 9) & psh_v) << 1);
	unsigned const c2 = p.cell2x2 ? 1 : 0;
	unsigned const cx = bits(sx, 8, 3) >> c2, cy = bits(sy, 8, 3) >> c2;
	unsigned const index = cx + (cy << (6 - c2));
	return g.map_base[plane] + (page << p.page_shift) + index * (p.one_word ? 2 : 4);
}

// A dot from its raw cell data: `raw` is 4/8/11 bits of colour code, a 15 bit
// RGB word or a 24 bit RGB long (with the transparency bit) depending on the
// colour format; `pal` is the palette number already in colour code position.
renderer::layer_dot renderer::make_dot(decoded const &d, nbg_params const &p, uint32_t raw, unsigned pal, bool pr, bool cc) const
{
	layer_dot out;
	unsigned code = 0;
	bool opaque = true;
	bool palette = true;
	uint32_t rgb = 0;

	switch (p.cf) {
	case 0: {
		unsigned const dot = raw & 0xf;
		opaque = dot || p.ctl.tpon;
		code = pal | dot;
		out.code = dot;
		break;
	}
	case 1: {
		unsigned const dot = raw & 0xff;
		opaque = dot || p.ctl.tpon;
		code = (pal & 0x700) | dot;
		out.code = dot & 0xf;
		break;
	}
	case 2: {
		unsigned const dot = raw & 0x7ff;
		opaque = dot || p.ctl.tpon;
		code = dot;
		out.code = dot & 0xf;
		break;
	}
	case 3: {
		unsigned const c = raw & 0xffff;
		opaque = (c & 0x8000) || p.ctl.tpon;
		rgb = ((c & 0x1f) << 19) | (((c >> 5) & 0x1f) << 11) | (((c >> 10) & 0x1f) << 3);
		palette = false;
		out.msb = true;
		out.code = rgb & 0xf;
		break;
	}
	default: {
		opaque = (raw & 0x80000000) || p.ctl.tpon;
		rgb = ((raw & 0xff) << 16) | (raw & 0xff00) | ((raw >> 16) & 0xff);
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

// Ideal (unconstrained) dot lookup for source dot (sx, sy). Rotation screens
// use it directly; normal screens use it when the VRAM access model does not
// apply.
// RBG0 data bank ownership. The rotation data bank bits (RAMCTL 7-0) give each
// VRAM bank one role: 1 coefficient table, 2 pattern name table, 3 character
// pattern / bitmap. RBG0 accesses go only to banks holding the matching role;
// a read outside them is not performed (Developer's Manual ST-058-R2, VDP2
// 6.2 "Rotation data bank specification bit": "If the image data read address
// is not in the specified bank, the data will not be read"). VDP2.sv 739-760
// gates the same way. Only pattern names and characters are gated: Die Hard
// Arcade's floor and sky read coefficients (KTCTL, KTAOF = 1 -> bank A1) from a
// bank whose role bits are 00, so coefficient reads must not depend on them.
// Without bank division, bank A0 / B0 bits cover A / B.
bool renderer::rdbs_allows(decoded const &d, uint32_t address, unsigned role)
{
	unsigned const bank = (address >> 17) & 3;
	unsigned const effective = (d.ramctl & (0x100U << (bank / 2))) ? bank : (bank & ~1U);
	return ((d.ramctl >> (effective * 2)) & 3) == role;
}

renderer::layer_dot renderer::nbg_dot(decoded const &d, nbg_params const &p, geometry const &g, uint32_t sx, uint32_t sy, int repeat_pn, bool rdbs_gated) const
{
	uint32_t base;         // cell / bitmap byte address
	unsigned dot_x, dot_y; // within cell (8x8) or bitmap
	unsigned pitch;
	unsigned pal = 0;      // colour code high bits, already positioned
	bool pr = false, cc = false;

	if (p.bitmap) {
		dot_x = sx & (p.bitmap_w - 1);
		dot_y = sy & (p.bitmap_h - 1);
		base = g.bitmap_base;
		pitch = p.bitmap_w;
		pal = p.bitmap_pal;
		pr = p.bitmap_pr;
		cc = p.bitmap_cc;
	} else {
		unsigned const c2 = p.cell2x2 ? 1 : 0;
		char_info ch;
		if (repeat_pn >= 0) {
			nbg_params one_word = p;
			one_word.one_word = true;
			ch = decode_pn(one_word, unsigned(repeat_pn));
		} else {
			uint32_t const a = pn_address(p, g, sx, sy);
			ch = (rdbs_gated && !rdbs_allows(d, a, 2)) ? decode_pn(p, 0) : decode_pn(p, p.one_word ? vram16(a) : vram32(a));
		}
		pal = ch.pal;
		cc = ch.cc;
		pr = ch.pr;

		dot_x = sx & 7;
		dot_y = sy & 7;
		unsigned cell_x = (c2 && repeat_pn < 0) ? ((sx >> 3) & 1) : 0, cell_y = (c2 && repeat_pn < 0) ? ((sy >> 3) & 1) : 0;
		if (ch.flip_h) { dot_x ^= 7; cell_x ^= c2; }
		if (ch.flip_v) { dot_y ^= 7; cell_y ^= c2; }
		static constexpr unsigned cell_units_shift[5] = { 0, 1, 2, 2, 3 };
		base = (ch.num + ((cell_x + (cell_y << 1)) << cell_units_shift[p.cf])) << 5;
		pitch = 8;
	}

	unsigned const off = dot_x + dot_y * pitch;
	uint32_t raw;
	if (rdbs_gated && !rdbs_allows(d, base + off * 4, 3))
		return make_dot(d, p, 0, pal, pr, cc);
	switch (p.cf) {
	case 0: raw = (vram8(base + (off >> 1)) >> ((~dot_x & 1) * 4)) & 0xf; break;
	case 1: raw = vram8(base + off); break;
	case 2:
	case 3: raw = vram16(base + off * 2); break;
	default: raw = vram32(base + off * 4); break;
	}
	return make_dot(d, p, raw, pal, pr, cc);
}

//--------------------------------------------------------------------------
//  Normal scroll screen line through the VRAM access model
//--------------------------------------------------------------------------

// Access command schedule of the four VRAM banks (saturn_vdp2_fetch.h)
saturn_vdp2_fetch::schedule renderer::fetch_schedule(decoded const &d)
{
	std::array<bool, 4> rotation_owned;
	for (unsigned bank = 0; bank < 4; bank++) {
		unsigned const effective = (d.ramctl & (0x100U << (bank / 2))) ? bank : (bank & ~1U);
		rotation_owned[bank] = (bank >= 2 && d.r1on) || (d.r0on && ((d.ramctl >> (effective * 2)) & 3));
	}
	uint16_t cyc[8];
	for (unsigned i = 0; i < 8; i++)
		cyc[i] = d.cyc[i];
	return saturn_vdp2_fetch::make_schedule(cyc, d.ramctl & 0x100, d.ramctl & 0x200, rotation_owned);
}

// The scroll screen's dots for this line come from what the cycle pattern
// registers let the VDP2 read (pattern names, character patterns, vertical
// cell scroll entries), not from an ideal lookup: characters whose reads are
// not scheduled show the previous character's dots, and so on (MiSTer
// VDP2.sv, see saturn_vdp2_fetch.h).
void renderer::draw_nbg_fetched(decoded const &d, unsigned n, nbg_state &s)
{
	// the other field of a double density frame is not shown: the VDP2 only reads its VRAM for the
	// lines of the field being scanned, so nothing is fetched for these lines
	if (m_skip_output)
		return;

	namespace f = saturn_vdp2_fetch;
	nbg_params const &p = d.nbg[n];

	unsigned const slots = m_cfg.hires ? f::HIRES_SLOTS : f::SLOTS;
	int const cycles = ((m_cfg.hreso & 1) ? 360 : 328) / (m_cfg.hires ? 4 : 8);
	f::schedule const schedule = fetch_schedule(d);
	f::reduction const reduction{ n < 2 && p.zmhf, n < 2 && p.zmqt };

	int64_t const start_x = int64_t(s.frac_x + p.scroll_x) << 8;
	int64_t const start_y = int64_t(s.frac_y + p.scroll_y) << 8;
	uint32_t const inc_x = s.inc_x << 8;
	unsigned const mosaic_h = p.mosaic ? d.mosaic_h : 1;
	geometry const g{ 1, p.map_base, p.plsz, p.bitmap_base };

	struct access {
		renderer const &r;
		decoded const &d;
		nbg_params const &p;
		geometry const &g;
		int64_t x;
		uint32_t inc;
		std::array<int32_t, 90> const &y;
		uint32_t pn_address(unsigned sx, unsigned sy) const { return renderer::pn_address(p, g, sx, sy); }
		f::pattern_name read_pn(uint32_t address) const
		{
			char_info const c = decode_pn(p, p.one_word ? r.vram16(address) : r.vram32(address));
			f::pattern_name pn;
			pn.character = c.num;
			pn.palette = c.pal;
			pn.hflip = c.flip_h;
			pn.vflip = c.flip_v;
			pn.priority = c.pr;
			pn.colour_calc = c.cc;
			return pn;
		}
		uint32_t read32(uint32_t address) const { return r.vram32(address); }
		unsigned bank(uint32_t address) const { return (address >> 17) & 3; }
		unsigned cycle_x(int cycle) const { return unsigned((x + int64_t(cycle) * 8 * inc) >> 16); }
		unsigned cycle_y(int cycle) const { return unsigned(y[cycle]); }
	};
	struct vcs_access {
		renderer const &r;
		uint32_t base;
		uint32_t vcs_address(unsigned index) const { return (base + index * 4) & r.m_mem.vram_mask; }
		int32_t read_vcs(uint32_t address) const { return int32_t(uint32_t(r.vram32(address) & 0x07ffff00) << 5) >> 5; }
		unsigned bank(uint32_t address) const { return (address >> 17) & 3; }
	};

	f::carry_state &carry = s.carry;
	std::array<std::array<int32_t, 90>, 2> cell_offsets = {};
	bool const cell_scroll = n < 2 && p.vcell;
	if (cell_scroll) {
		unsigned const vh = m_mem.regs[VCSTAU >> 1], vl = m_mem.regs[(VCSTAU + 2) >> 1];
		vcs_access vcs{ *this, uint32_t((((vh & 7) << 16) | vl) << 1) & ~3U };
		std::array<bool, 2> const enabled{ d.nbg[0].vcell && d.nbg[0].on && !d.r1on, d.nbg[1].vcell && d.nbg[1].on };
		f::vertical_cell_scroll_line(schedule, enabled, cycles, vcs, carry.vcs_latch, cell_offsets, slots);
	}
	std::array<int32_t, 90> fetch_y;
	for (int c = 0; c < cycles; c++)
		fetch_y[c] = int32_t((start_y + ((cell_scroll && !p.mosaic) ? cell_offsets[n & 1][c] : 0)) >> 16);

	f::bitmap_config bitmap;
	if (p.bitmap && n < 2) {
		bitmap.enabled = true;
		bitmap.base = p.bitmap_base;
		bitmap.size = (p.bitmap_w == 1024 ? 2 : 0) | (p.bitmap_h == 512 ? 1 : 0);
		bitmap.attr.palette = p.bitmap_pal;
		bitmap.attr.colour_calc = p.bitmap_cc;
		bitmap.attr.priority = p.bitmap_pr;
	}

	access acc{ *this, d, p, g, start_x, inc_x, fetch_y };
	f::fetch_line(schedule, n, p.cf, p.cell2x2, reduction, bitmap, cycles, acc, carry,
			[this](int cycle, f::cycle_dots const &dots) { m_fetched[cycle] = dots; }, slots);

	// Output stage: dot j of screen cycle g reads the buffers of cycles g and g + 1
	// through an accumulator that starts at the cycle's source X modulo 8 and adds
	// the horizontal increment per dot (VDP2.sv 2997-3135).
	for (unsigned x = 0; x < m_cfg.width; x++) {
		unsigned const sample_x = x - x % mosaic_h;
		int const cycle = sample_x >> 3;
		int64_t const cycle_x = start_x + int64_t(cycle) * 8 * inc_x;
		uint32_t const offset = uint32_t(((cycle_x & 0x7ffff) + int64_t(sample_x & 7) * inc_x) >> 16);
		f::dot_ref const ref = f::select_dot(n, p.cf, reduction, offset);
		if (cycle + int(ref.buffer) < cycles) {
			f::cycle_dots const &dots = m_fetched[cycle + ref.buffer];
			f::pattern_name const &attr = dots.attr[ref.cell];
			s.line[x] = make_dot(d, p, dots.dot[ref.cell][ref.dot], attr.palette, attr.priority, attr.colour_calc);
		} else {
			s.line[x] = layer_dot();
		}
	}
	s.have_line = true;
}

//--------------------------------------------------------------------------
//  One normal scroll screen line
//--------------------------------------------------------------------------

void renderer::draw_nbg(decoded const &d, unsigned n, unsigned y)
{
	nbg_params const &p = d.nbg[n];
	nbg_state &s = m_nbg[n];

	// per line scroll / zoom table (NBG0/1): one entry per 1 << LSS lines. Lines are
	// the lines this renderer produces: field lines when not interlaced or single
	// density (whose table interval is twice as long in frame lines) and frame lines
	// in double density, so the interval is 1 << LSS in every mode (ST-058 chapter 5,
	// N0LSS/N1LSS table of the line & vertical cell scroll control register).
	if (!p.lzm)
		s.inc_x = p.inc_x;
	if (n < 2 && (p.lsx || p.lsy || p.lzm) && (y & ((1U << p.lss) - 1)) == 0) {
		if (p.lsx) { s.frac_x = bits(vram32(s.ls_addr), 26, 8); s.ls_addr += 4; }
		if (p.lsy) { s.frac_y = bits(vram32(s.ls_addr), 26, 8); s.ls_addr += 4; }
		if (p.lzm) { s.inc_x = bits(vram32(s.ls_addr), 18, 8); s.ls_addr += 4; }
	}

	// mosaic: the first line of a group is drawn, the others repeat it
	if (p.mosaic && (s.mosaic_y > 0 || s.mosaic_odd) && s.have_line)
		return;

	if (!m_cfg.exclusive) {
		draw_nbg_fetched(d, n, s);
		return;
	}

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
		s.line[x] = nbg_dot(d, p, geometry{ 1, p.map_base, p.plsz, p.bitmap_base }, fx >> 8, (s.frac_y + p.scroll_y + vcell_y) >> 8, -1);
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
	if (p.mosaic) {
		// The vertical mosaic size counts field lines: MiSTer VDP2.sv (MOSAIC_VCNT steps once
		// per rendered field line) and Ymir (VDP2FinishLine) agree, and ST-058 4.11 gives the
		// interlace sizes as twice the non-interlaced ones. In double density a field line is
		// two of the frame lines drawn here, and a mosaic screen is shown as single density
		// (the two lines are the same), so the counter steps on every second line.
		bool const pair_done = m_cfg.lsmd != 3 || s.mosaic_odd;
		if (m_cfg.lsmd == 3)
			s.mosaic_odd = !s.mosaic_odd;
		if (pair_done)
			s.mosaic_y = (s.mosaic_y + 1 >= d.mosaic_v) ? 0 : s.mosaic_y + 1;
	}
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
//  Rotation screens (RBG0 / RBG1)
//--------------------------------------------------------------------------

namespace {

// RotCoord arithmetic (VDP2_pkg.sv): 16.16 fixed point in 32 bits
inline int32_t sext(uint32_t v, unsigned nbits) { return int32_t(v << (32 - nbits)) >> (32 - nbits); }
inline int32_t rc(int32_t integer, uint32_t frac16) { return int32_t((uint32_t(integer) << 16) | frac16); }
inline int32_t mult_rc(int32_t a, int32_t b) { return int32_t((int64_t(a) * b) >> 16); }
inline int32_t add_rc(int32_t a, int32_t b) { return int32_t(uint32_t(a) + uint32_t(b)); }
inline int32_t sub_rc(int32_t a, int32_t b) { return int32_t(uint32_t(a) - uint32_t(b)); }

// Rotation parameter table words (ST-058, VDP2_pkg.sv 1932-2000)
inline int32_t scrn_start(uint32_t w) { return rc(sext((w >> 16) & 0x1fff, 13), ((w >> 6) & 0x3ff) << 6); }
inline int32_t scrn_inc(uint32_t w) { return rc(sext((w >> 16) & 7, 3), ((w >> 6) & 0x3ff) << 6); }
inline int32_t matr(uint32_t w) { return rc(sext((w >> 16) & 0xf, 4), ((w >> 6) & 0x3ff) << 6); }
inline int32_t coord(uint32_t v14) { return rc(sext(v14 & 0x3fff, 14), 0); }
inline int32_t shift_rc(uint32_t w) { return rc(sext((w >> 16) & 0x3fff, 14), ((w >> 6) & 0x3ff) << 6); }
inline int32_t scaling(uint32_t w) { return rc(sext((w >> 16) & 0xff, 8), w & 0xffff); }
inline int64_t addr_inc(uint32_t w) { return int64_t(sext((w >> 6) & 0xfffff, 20)) * 64; }

} // anonymous namespace

// Computes, for both parameter sets, the start coordinates for this line and
// (when a rotation screen is enabled) the source coordinates of every dot.
void renderer::calc_rotation(decoded const &d, unsigned y, bool need_lines)
{
	unsigned const rpx = m_cfg.hires ? (m_cfg.width >> 1) : m_cfg.width;

	for (unsigned i = 0; i < 2; i++) {
		rot_params const &rp = d.rot[i];
		rot_state &st = m_rot_state[i];
		uint32_t const t = d.rpta + i * 0x80;

		uint32_t const xw = vram32(t + 0x00), yw = vram32(t + 0x04);
		uint32_t const dxw = vram32(t + 0x0c), dyw = vram32(t + 0x10);
		int32_t const xst = scrn_start(xw);
		int32_t const yst = scrn_start(yw);
		int32_t const zst = scrn_start(vram32(t + 0x08));
		int32_t const dxst = scrn_inc(dxw);
		int32_t const dyst = scrn_inc(dyw);
		int32_t const dx = scrn_inc(vram32(t + 0x14));
		int32_t const dy = scrn_inc(vram32(t + 0x18));

		// start coordinates: read at the top of the frame or on request, otherwise stepped
		unsigned const pend = m_rprctl_pending >> (8 * i);
		if (y == 0 || (pend & 1))
			st.xst = xst;
		else
			st.xst = add_rc(st.xst, dxst);
		if (y == 0 || (pend & 2))
			st.yst = yst;
		else
			st.yst = add_rc(st.yst, dyst);
		// VDP1 frame buffer rotation (11.9 fixed point, the VDP1 readout of parameter set A)
		if (i == 0) {
			int32_t const sx = sext((((xw >> 28) & 1) << 10) | ((xw >> 16) & 0x3ff), 11) * 512 + int32_t((xw >> 7) & 0x1ff);
			int32_t const sy = sext((((yw >> 28) & 1) << 10) | ((yw >> 16) & 0x3ff), 11) * 512 + int32_t((yw >> 7) & 0x1ff);
			int32_t const isx = sext((dxw >> 16) & 7, 3) * 512 + int32_t((dxw >> 7) & 0x1ff);
			int32_t const isy = sext((dyw >> 16) & 7, 3) * 512 + int32_t((dyw >> 7) & 0x1ff);
			if (y == 0 || (pend & 1))
				st.spr_xst = sx;
			else
				st.spr_xst += isx;
			if (y == 0 || (pend & 2))
				st.spr_yst = sy;
			else
				st.spr_yst += isy;
			if (m_cfg.fb_rotate) {
				int32_t const dxa = sext((vram32(t + 0x14) >> 16) & 7, 3) * 512 + int32_t((vram32(t + 0x14) >> 7) & 0x1ff);
				int32_t const dya = sext((vram32(t + 0x18) >> 16) & 7, 3) * 512 + int32_t((vram32(t + 0x18) >> 7) & 0x1ff);
				for (unsigned x = 0; x < rpx; x++) {
					m_spr_x[x] = (st.spr_xst + int32_t(x) * dxa) >> 9;
					m_spr_y[x] = (st.spr_yst + int32_t(x) * dya) >> 9;
				}
			}
		}

		bool const kast_reread = y == 0 || (pend & 4);
		m_rprctl_pending &= ~(7U << (8 * i));

		int64_t const dkast = addr_inc(vram32(t + 0x58));
		if (kast_reread)
			st.ka_y = 0;
		else
			st.ka_y += dkast;

		if (!need_lines)
			continue;

		int32_t const a = matr(vram32(t + 0x1c)), b = matr(vram32(t + 0x20)), c = matr(vram32(t + 0x24));
		int32_t const dd = matr(vram32(t + 0x28)), e = matr(vram32(t + 0x2c)), f = matr(vram32(t + 0x30));
		uint32_t const pxy = vram32(t + 0x34), pzw = vram32(t + 0x38), cxy = vram32(t + 0x3c), czw = vram32(t + 0x40);
		int32_t const px = coord(pxy >> 16), py = coord(pxy), pz = coord(pzw >> 16);
		int32_t const cx = coord(cxy >> 16), cy = coord(cxy), cz = coord(czw >> 16);
		int32_t const mx = shift_rc(vram32(t + 0x44)), my = shift_rc(vram32(t + 0x48));
		int32_t const kx = scaling(vram32(t + 0x4c)), ky = scaling(vram32(t + 0x50));
		uint32_t const kast = vram32(t + 0x54) & 0xffffffc0U;
		int64_t const dkax = addr_inc(vram32(t + 0x5c));

		// start point in the transformed plane, per-dot step, and viewpoint
		int32_t xsp = add_rc(add_rc(mult_rc(a, sub_rc(st.xst, px)), mult_rc(b, sub_rc(st.yst, py))), mult_rc(c, sub_rc(zst, pz)));
		int32_t ysp = add_rc(add_rc(mult_rc(dd, sub_rc(st.xst, px)), mult_rc(e, sub_rc(st.yst, py))), mult_rc(f, sub_rc(zst, pz)));
		int32_t const dxsp = add_rc(mult_rc(a, dx), mult_rc(b, dy));
		int32_t const dysp = add_rc(mult_rc(dd, dx), mult_rc(e, dy));
		int32_t xp = add_rc(add_rc(add_rc(add_rc(cx, mult_rc(a, sub_rc(px, cx))), mult_rc(b, sub_rc(py, cy))), mult_rc(c, sub_rc(pz, cz))), mx);
		int32_t yp = add_rc(add_rc(add_rc(add_rc(cy, mult_rc(dd, sub_rc(px, cx))), mult_rc(e, sub_rc(py, cy))), mult_rc(f, sub_rc(pz, cz))), my);

		rot_line &ln = m_rot_line[i];
		int64_t const ka_base = (int64_t(rp.ktaos) << 32) + int64_t(kast) + st.ka_y;

		int32_t coeff = 0;
		bool coeff_tp = false;
		uint8_t coeff_lcsd = 0;
		bool have_coeff = false;

		for (unsigned x = 0; x < rpx; x++) {
			int32_t kx_x = kx, ky_x = ky, xp_x = xp;
			bool tp = false;
			uint8_t lcsd = 0;
			if (rp.kte) {
				// the coefficient address steps per dot; a zero step needs only one read per line
				if (!have_coeff || dkax != 0) {
					int64_t const sum = ka_base + dkax * int64_t(x);
					uint32_t const offs = uint32_t(sum >> 16) & 0x7ffff;
					uint32_t const byte_addr = rp.kdbs ? (offs << 1) : (offs << 2);
					uint32_t raw;
					if (d.crkte) {
						uint32_t const ca = (0x800 | byte_addr) & 0xffc;
						raw = m_mem.cram[ca >> 2];
						if (rp.kdbs)
							raw = (raw >> (16 - 16 * ((byte_addr >> 1) & 1))) & 0xffff;
					} else if (rp.kdbs) {
						raw = vram16(byte_addr);
					} else {
						raw = vram32(byte_addr);
					}
					if (rp.kdbs) {
						coeff_tp = raw & 0x8000;
						coeff_lcsd = 0;
						coeff = int32_t(int64_t(sext(raw & 0x7fff, 15)) * (rp.kmd == 3 ? (1 << 14) : (1 << 6)));
					} else {
						coeff_tp = raw & 0x80000000U;
						coeff_lcsd = (raw >> 24) & 0x7f;
						coeff = int32_t(int64_t(sext(raw & 0xffffff, 24)) * (rp.kmd == 3 ? (1 << 8) : 1));
					}
					have_coeff = true;
				}
				tp = coeff_tp;
				lcsd = coeff_lcsd;
				switch (rp.kmd) {
				case 0: kx_x = ky_x = coeff; break;
				case 1: kx_x = coeff; break;
				case 2: ky_x = coeff; break;
				default: xp_x = coeff; break;
				}
			}
			ln.x[x] = add_rc(xp_x, mult_rc(kx_x, xsp)) >> 16;
			ln.y[x] = add_rc(yp, mult_rc(ky_x, ysp)) >> 16;
			ln.transparent[x] = tp;
			ln.lcsd[x] = lcsd;
			xsp = add_rc(xsp, dxsp);
			ysp = add_rc(ysp, dysp);
		}
	}
}

// One rotation screen line. Layer 0 is RBG0 (selects between parameter sets
// A and B), layer 1 is RBG1 (always set B).
void renderer::draw_rbg(decoded const &d, unsigned layer, unsigned y, bool const *rpw_hit)
{
	(void)y;
	nbg_params const &p = d.rbg[layer];
	layer_dot *out = m_rbg[layer];
	unsigned const shift = m_cfg.hires ? 1 : 0;
	unsigned mosaic_x = 0;

	for (unsigned x = 0; x < m_cfg.width; x++) {
		if (p.mosaic) {
			unsigned const cur = mosaic_x;
			mosaic_x = (mosaic_x + 1 >= d.mosaic_h) ? 0 : mosaic_x + 1;
			if (cur > 0) {
				out[x] = out[x - 1];
				if (layer == 0)
					m_r0_lcsd[x] = m_r0_lcsd[x - 1];
				continue;
			}
		}

		unsigned const xr = x >> shift;
		unsigned sel = 1;
		if (layer == 0) {
			switch (d.rpmd) {
			case 0: sel = 0; break;
			case 1: sel = 1; break;
			case 2: sel = (d.rot[0].kte && m_rot_line[0].transparent[xr]) ? 1 : 0; break;
			default: sel = rpw_hit[x] ? 1 : 0; break;
			}
		}
		rot_params const &rp = d.rot[sel];
		rot_line const &ln = m_rot_line[sel];

		layer_dot dot;
		if (layer == 0) {
			// line colour data in the coefficient data (ST-058 6.4, p.164, p.168): only with
			// the coefficient table enabled and 2 word data; mode 2 takes it from table A
			// for both images, modes 0, 1 and 3 from the table of the selected image
			unsigned const lsel = d.rpmd == 2 ? 0 : sel;
			rot_params const &lrp = d.rot[lsel];
			m_r0_lcsd[x] = (lrp.klce && lrp.kte && !lrp.kdbs) ? int16_t(m_rot_line[lsel].lcsd[xr]) : int16_t(-1);
		}

		if (!(rp.kte && ln.transparent[xr])) {
			int32_t const sx = ln.x[xr], sy = ln.y[xr];
			geometry const g{ 2, d.rbg_map_base[layer][sel], rp.plsz, rp.mpofr << 17 };
			unsigned max_x, max_y;
			if (rp.over == 3) {
				max_x = max_y = 512;
			} else if (p.bitmap) {
				max_x = p.bitmap_w;
				max_y = p.bitmap_h;
			} else {
				max_x = 2048U << (rp.plsz & 1);
				max_y = 2048U << (rp.plsz >> 1);
			}
			bool const inside = sx >= 0 && sy >= 0 && unsigned(sx) < max_x && unsigned(sy) < max_y;
			if (inside || rp.over == 0)
				dot = nbg_dot(d, p, g, uint32_t(sx), uint32_t(sy), -1, layer == 0);
			else if (rp.over == 1 && !p.bitmap)
				dot = nbg_dot(d, p, g, uint32_t(sx), uint32_t(sy), int(rp.ovpn), layer == 0);
		}
		out[x] = dot;
	}
}

//--------------------------------------------------------------------------
//  Windows
//--------------------------------------------------------------------------

// VDP2_pkg.sv WinTest: a layer is hidden where this is true
static bool win_test(bool w0hit, bool w1hit, bool wshit, window_ctl const &c)
{
	// no window enabled: OR logic leaves the whole screen outside the window area, AND
	// logic makes the whole screen the window area (ST-058 8.2, xxLOG, p.194)
	if (!c.w0e && !c.w1e && !c.swe)
		return c.logic_and;
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

void renderer::render_line(unsigned y, sprite_source const &sprite, uint32_t *dest, bool skip_output)
{
	decoded d;
	decode(d);
	m_skip_output = skip_output;

	unsigned const width = m_cfg.width;
	bool const ddi = m_cfg.lsmd == 3;
	bool const hires = m_cfg.hires;

	// back screen and line colour screen for this line
	unsigned line_word;
	{
		unsigned const c = vram16(d.bkta + (d.bk_per_line ? y * 2 : 0));
		m_back = ((c & 0x1f) << 19) | (((c >> 5) & 0x1f) << 11) | (((c >> 10) & 0x1f) << 3);
		bool msb;
		line_word = vram16(d.lcta + (d.lc_per_line ? y * 2 : 0)) & 0x7ff;
		m_line_rgb = cram_rgb(d.crmd, line_word, msb);
	}

	bool const rbg_any = d.r0on || d.r1on;
	calc_rotation(d, y, rbg_any && m_cfg.disp && !skip_output);

	if (!m_cfg.disp) {
		std::fill_n(dest, width, m_cfg.bdclmd ? m_back : 0U);
		for (unsigned n = 0; n < 4; n++)
			finish_nbg(d, n);
		return;
	}

	// Scroll screens. NBG0 gives way to RBG1; the colour depth of NBG0/1
	// and the reduction settings decide which of NBG1-3 have VRAM cycles left.
	// With both rotation screens enabled no normal screen is displayed.
	bool nbg_on[4];
	nbg_on[0] = d.nbg[0].on || d.r1on;
	nbg_on[1] = d.nbg[1].on && d.nbg[0].cf < 4;
	nbg_on[2] = d.nbg[2].on && d.nbg[0].cf < 2 && !nbg_reduced(d.nbg[0]);
	nbg_on[3] = d.nbg[3].on && d.nbg[0].cf < 4 && d.nbg[1].cf < 2 && !nbg_reduced(d.nbg[1]);
	if (d.r0on && d.r1on)
		nbg_on[1] = nbg_on[2] = nbg_on[3] = false;
	for (unsigned n = 0; n < 4; n++)
		if (nbg_on[n] && !(n == 0 && d.r1on))
			draw_nbg(d, n, y);

	if (skip_output) {
		for (unsigned n = 0; n < 4; n++)
			finish_nbg(d, n);
		return;
	}

	// window geometry and hits for this line
	bool wy_hit[2];
	unsigned wsx[2], wex[2];
	for (unsigned w = 0; w < 2; w++) {
		wsx[w] = d.wsx[w];
		wex[w] = d.wex[w];
		if (d.lwe[w]) {
			// one entry per line; in double density the table holds the lines of both fields
			// together, so it is indexed by the frame line too (ST-058 Fig 8.4, MiSTer VDP2.sv
			// LW_ADDR adds one entry for the even field)
			uint32_t const e = vram32(d.lwta[w] + y * 4);
			wsx[w] = bits(e, 25, 16);
			wex[w] = bits(e, 9, 0);
		}
		unsigned const sy = d.wsy[w], ey = d.wey[w];
		// double density interlace: the registers hold the field V counter in bits 8-1
		// and bit 0 is not used (ST-058 Table 8.2), so compare field lines
		unsigned const wy = ddi ? (y >> 1) : y;
		unsigned const csy = ddi ? (sy >> 1) : sy, cey = ddi ? (ey >> 1) : ey;
		wy_hit[w] = (wy >= csy && wy <= cey && sy != 0x1fe && ey < 0x1fe) ||
				(ey >= (m_cfg.pal ? 0x100U : 0xf0U) && ey <= 0x1ed && !ddi);
	}
	for (unsigned x = 0; x < width; x++)
		for (unsigned w = 0; w < 2; w++) {
			// window coordinates are in half dots in the normal resolutions
			unsigned const px = hires ? x : (x << 1);
			unsigned const s = hires ? wsx[w] : (wsx[w] & ~1U);
			unsigned const e = hires ? wex[w] : (wex[w] & ~1U);
			m_w_hit[w][x] = (px >= s || wsx[w] >= 0x360) && px <= e && e < 0x360 && e != 0x2ec && wy_hit[w];
		}

	// rotation screens
	if (rbg_any) {
		bool rpw_hit[MAX_WIDTH];
		for (unsigned x = 0; x < width; x++)
			rpw_hit[x] = win_test(m_w_hit[0][x] != d.rpwin.w0a, m_w_hit[1][x] != d.rpwin.w1a, false, d.rpwin);
		if (d.r0on)
			draw_rbg(d, 0, y, rpw_hit);
		if (d.r1on)
			draw_rbg(d, 1, y, rpw_hit);
	}

	// gradation neighbours (VDP2.sv 3452-3466)
	bool boken_prev1 = false, boken_prev2 = false;
	rgb csec_prev1, csec_prev2;
	bool const exccen = d.exccen && !d.boken;

	auto const to_rgb = [](uint32_t c) { return rgb{ uint8_t(c >> 16), uint8_t(c >> 8), uint8_t(c) }; };
	auto const from_rgb = [](rgb c) { return (uint32_t(c.r) << 16) | (uint32_t(c.g) << 8) | c.b; };
	unsigned const boken_layer_n[5] = { 2, 4, 5, 6, 1 };

	for (unsigned x = 0; x < width; x++) {
		sprite_dot const sd = decode_sprite(d, m_cfg.fb_rotate ? sprite.sprite_word_rotated(m_spr_x[x >> (hires ? 1 : 0)], m_spr_y[x >> (hires ? 1 : 0)]) : sprite.sprite_word(x, y));
		bool const spwin = d.sp_winen;

		auto const hidden = [&](window_ctl c) {
			c.swe = c.swe && spwin;
			return win_test(m_w_hit[0][x] != c.w0a, m_w_hit[1][x] != c.w1a, sd.wn != c.swa, c);
		};
		bool const ccw = hidden(d.ccwin);
		bool const bok_ok = d.boken && d.crmd == 0;

		// sprite
		unsigned const sprin = d.sp_pri[sd.pr];
		layer_input in_spr;
		{
			screen_dot &t = in_spr.dot;
			in_spr.on = !sd.tp && !hidden(d.sp.win);
			if (!sd.tp)
				stat_sprite_dots++;
			if (in_spr.on)
				stat_sprite_shown++;
			if (in_spr.on) {
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
		}

		// a scroll or rotation screen's contribution
		auto const layer_in = [&](nbg_params const &p, layer_dot const &ld, bool enabled, unsigned boken_n) {
			layer_input li;
			if (!enabled || !ld.opaque)
				return li;   // an off or transparent dot does not take part in the stack
			li.on = !hidden(p.ctl.win);
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
			t.boken = bok_ok && d.bokn == boken_n;
			t.lcen = p.ctl.lcen;
			t.palette = ld.palette;
			t.msb = ld.msb;
			t.dc = ld.rgb;
			return li;
		};

		layer_input in_nbg[4];
		for (unsigned n = 0; n < 4; n++) {
			bool const rot = n == 0 && d.r1on;
			in_nbg[n] = layer_in(d.nbg[n], rot ? m_rbg[1][x] : m_nbg[n].line[x], nbg_on[n], boken_layer_n[n]);
		}
		layer_input const in_r0 = d.r0on ? layer_in(d.rbg[0], m_rbg[0][x], true, boken_layer_n[4]) : layer_input();

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
			if (d.r0on && m_r0_lcsd[x] >= 0) {
				// the selected rotation parameter set supplies the low 7 bits of the line colour address
				bool m;
				lc.dc = cram_rgb(d.crmd, (line_word & 0x780) | unsigned(m_r0_lcsd[x]), m);
			}
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
		// Extended colour calculation is unavailable in high resolution and dedicated
		// monitor modes, and normal colour calculation with a palette second image
		// only works with colour RAM mode 0 there (ST-058 12.1 / 12.2, Table 12.1)
		if (!hires && !m_cfg.exclusive) {
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
		if ((hires || m_cfg.exclusive) && d.crmd != 0 && sec.palette)
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

/*
  Game observations carried over from the legacy renderer, kept because they
  say which titles exercise which VDP2 corner cases:

  - batmanfr: resetting after the character selection screen and returning
    to it left garbage floating behind Batman.
  - elandore: priorities on the VS screen look wrong, but do so on the real
    Saturn version too.
  - hanagumi: ending screens had corrupt graphics; a red dragon logo sits in
    tile RAM (base 0x64000, 4bpp 8x8 tiles) but is not displayed because its
    priority is 0.
  - kiwames: the alpha blended flames on the title screen depend on a line
    scroll quirk; the VDP1 refresh must be fast enough for "draw by request".
  - pblbeach: sprites are offset because the game does not clear the VDP1
    local coordinates set by the BIOS.
  - prikura: attract mode graphics corrupt in places (framebuffer erase).
  - seabass: player sprite corruption came from framebuffer switching.
  - shienryu: level 2 statue background colours depend on per-dot special
    colour calculation.
  - scud (Saturn): zooming on the melee attack turns the background pink.
  - virtual hydlide (Saturn): transparent pens on most VDP1 items should be
    black, and the "press start button" text is the other way around.
  - The test mode / BIOS screen is drawn with NBG3.
  - The H-Blank bit is independent of the V-Blank bit; changing that during
    V-Blank breaks gameplay speed in Golden Axe: The Duel.
  - Bitmap screens use transparency pens (elandore energy bars, mausuke's
    playfield foreground, shanhigw's tile based sprites): dot code 0 for 16,
    256 and 2048 colours, MSB clear for 32768 and 16.7M colours.
  - Scroll values are masked by the screen resolution.
  - Double density interlace (LSMD == 3) changes several graphics sizes.
*/

/*
  Game observations carried over from the legacy VDP2 core (check list):

  - decathlt gameplay, dragndrm title, Data East logo in the Magical Drop
    games: colour calculation enabled where it should not be.
  - dokyuif title transition (reversed fade), shienryu stage 2 statues (per
    dot special colour calculation), scud zoom-in on melee attacks (pink
    background), dinoisl: colour calculation.
  - gpanicss gal select, cknight2j map transition: window effects.
  - kingbox gameplay, columns Sega Ages logo: VRAM cycle pattern effects.
  - Saturn BIOS memory screens, capgen2 map transitions: mosaic.
  - elevact2, ogrebatl, htheros crowd: per scanline register effects.
  - mfpool and voiceido gameplay: shadows.
  - gekkakis gameplay enables the undocumented BGON bit 6 (text layer alias).
  - biohaz: back screen not drawn; vhydlid and other T&E Soft games: title
    screen blinking.
  - batmanfr before the final boss: the complicated rotation setup of the
    Riddler screen; rsgun Xiga final boss: rotation read controls; sandor
    (ST-V) dry towel sub-game screen setup.
*/

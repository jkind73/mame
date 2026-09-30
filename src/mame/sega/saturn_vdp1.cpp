// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP1. See saturn_vdp1.h.

  Frame level behaviour follows the MiSTer core (rtl/Saturn/VDP1/VDP1.sv:
  frame change at the end of vblank, erase modes, end of draw flags) and
  Mednafen's hardware-tested handling of the register/erase interplay.
*/

#include "emu.h"
#include "saturn_vdp1.h"

#include <cstdlib>

using namespace saturn_vdp1;

DEFINE_DEVICE_TYPE(SATURN_VDP1, saturn_vdp1_device, "saturn_vdp1", "Sega Saturn VDP1 (315-5689)")

saturn_vdp1_device::saturn_vdp1_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, SATURN_VDP1, tag, owner, clock)
	, m_draw_end_cb(*this)
{
}

void saturn_vdp1_device::device_start()
{
	m_vram = make_unique_clear<uint16_t []>(VRAM_WORDS);
	m_fb[0] = make_unique_clear<uint16_t []>(FB_WORDS);
	m_fb[1] = make_unique_clear<uint16_t []>(FB_WORDS);
	m_field_copy[0] = make_unique_clear<uint16_t []>(FB_WORDS);
	m_field_copy[1] = make_unique_clear<uint16_t []>(FB_WORDS);

	m_engine.vram = m_vram.get();
	m_engine.fb = m_fb[0].get();
	m_engine.reset();
	m_last_time = machine().time();
	m_vbe_timer = timer_alloc(FUNC(saturn_vdp1_device::vbe_sample), this);
	m_log = std::getenv("SATURN_VDP1_LOG") != nullptr;

	save_pointer(NAME(m_vram), VRAM_WORDS);
	save_pointer(NAME(m_fb[0]), FB_WORDS);
	save_pointer(NAME(m_fb[1]), FB_WORDS);
	save_pointer(NAME(m_field_copy[0]), FB_WORDS);
	save_pointer(NAME(m_field_copy[1]), FB_WORDS);
	save_item(NAME(m_field_cur));
	save_item(NAME(m_disp_die));
	save_item(NAME(m_disp_dil));
	save_item(NAME(m_prev_die));
	save_item(NAME(m_prev_dil));
	save_item(NAME(m_tvmr));
	save_item(NAME(m_fbcr));
	save_item(NAME(m_ptmr));
	save_item(NAME(m_ewdr));
	save_item(NAME(m_ewlr));
	save_item(NAME(m_ewrr));
	save_item(NAME(m_edsr));
	save_item(NAME(m_lopr));
	save_item(NAME(m_die));
	save_item(NAME(m_dil));
	save_item(NAME(m_draw_fb));
	save_item(NAME(m_drawing));
	save_item(NAME(m_cmd_addr));
	save_item(NAME(m_ret_addr));
	save_item(NAME(m_budget));
	save_item(NAME(m_last_time));
	save_item(NAME(m_vblank));
	save_item(NAME(m_hblank));
	save_item(NAME(m_manual_pending));
	save_item(NAME(m_vb_erase_pending));
	save_item(NAME(m_vb_erase_active));
	save_item(NAME(m_vblank_start));
	save_item(NAME(m_erase_y));
	save_item(NAME(m_erase.x_start));
	save_item(NAME(m_erase.x_bound));
	save_item(NAME(m_erase.y_start));
	save_item(NAME(m_erase.y_end));
	save_item(NAME(m_erase.data));
	save_item(NAME(m_erase.x_mask));
	save_item(NAME(m_erase.rot8));
	save_item(NAME(m_cmd));
	save_item(NAME(m_engine.sys_x));
	save_item(NAME(m_engine.sys_y));
	save_item(NAME(m_engine.user_x0));
	save_item(NAME(m_engine.user_y0));
	save_item(NAME(m_engine.user_x1));
	save_item(NAME(m_engine.user_y1));
	save_item(NAME(m_engine.local_x));
	save_item(NAME(m_engine.local_y));
}

void saturn_vdp1_device::device_reset()
{
	m_tvmr = m_fbcr = m_ptmr = 0;
	m_edsr = 0;
	m_die = m_dil = false;
	m_disp_die = m_disp_dil = m_prev_die = m_prev_dil = false;
	m_drawing = false;
	m_budget = 0;
	m_last_time = machine().time();
	m_manual_pending = false;
	m_vb_erase_pending = false;
	m_vb_erase_active = false;
	m_erase_y = ~0U;
	m_cmd_addr = 0;
	m_ret_addr = -1;
	m_engine.reset();
}

void saturn_vdp1_device::system_reset()
{
	// SMPC system reset: everything is cleared
	std::fill_n(m_vram.get(), VRAM_WORDS, 0);
	std::fill_n(m_fb[0].get(), FB_WORDS, 0);
	std::fill_n(m_fb[1].get(), FB_WORDS, 0);
	reset();
}

//**************************************************************************
//  Drawing
//**************************************************************************

void saturn_vdp1_device::update()
{
	if (!clock())
		return;

	attotime const now = machine().time();
	if (now > m_last_time) {
		int64_t const ticks = (now - m_last_time).as_ticks(clock());
		if (ticks > 0) {
			m_last_time += attotime::from_ticks(ticks, clock());
			// idle time cannot be banked; while drawing every elapsed clock counts
			int64_t const budget = int64_t(m_budget) + ticks;
			m_budget = int32_t(m_drawing ? std::min<int64_t>(budget, INT32_MAX / 2) : std::min<int64_t>(budget, UPDATE_GRANULARITY));
		}
	}

	if (m_drawing && m_budget > 0)
		run();
}

void saturn_vdp1_device::start_drawing()
{
	m_edsr &= ~2;                     // CEF cleared when drawing starts
	m_cmd_addr = 0;
	m_ret_addr = -1;
	m_drawing = true;
	m_phase = phase::fetch;
	m_budget = UPDATE_GRANULARITY;
	m_last_time = machine().time();
	m_die = m_fbcr & FBCR_DIE;
	m_dil = m_fbcr & FBCR_DIL;
	m_engine.fb = m_fb[m_draw_fb].get();
}

void saturn_vdp1_device::stop_drawing()
{
	m_drawing = false;
	if (m_budget < 0)
		m_budget = 0;
}

void saturn_vdp1_device::run()
{
	m_engine.tvmr = m_tvmr;
	m_engine.fbcr = (m_fbcr & ~(FBCR_DIE | FBCR_DIL)) | (m_die ? FBCR_DIE : 0) | (m_dil ? FBCR_DIL : 0);
	m_engine.fb = m_fb[m_draw_fb].get();

	while (m_drawing && m_budget > 0) {
		switch (m_phase) {
		case phase::fetch:
			for (unsigned i = 0; i < 16; i++)
				m_cmd[i] = m_vram[(m_cmd_addr + i) & (VRAM_WORDS - 1)];
			m_budget -= 16;
			m_phase = phase::decode;
			break;

		case phase::decode:
			if (!(m_cmd[0] & 0xc000)) {
				if ((m_cmd[0] & 0xf) >= 0xc) {
					// not a command: drawing stops without the end flag
					m_stats.invalid++;
					stop_drawing();
					return;
				}
				m_stats.cmd[m_cmd[0] & 0xf]++;
				m_budget -= m_engine.execute(m_cmd);
			} else if (m_cmd[0] & 0x8000) {
				m_stats.ended++;
				stop_drawing();
				m_edsr |= 2;              // CEF
				m_draw_end_cb(1);
				return;
			} else {
				m_stats.skipped++;
			}
			m_phase = phase::next;
			break;

		case phase::next:
			m_cmd_addr = (m_cmd_addr + 0x10) & (VRAM_WORDS - 1);
			switch ((m_cmd[0] >> 12) & 3) {
			case 1:   // jump
				m_stats.jumps++;
				m_cmd_addr = (uint32_t(m_cmd[1]) << 2) & ~0xfU;
				break;
			case 2:   // call: the first call remembers the return address
				m_stats.calls++;
				if (m_ret_addr < 0)
					m_ret_addr = int32_t(m_cmd_addr);
				m_cmd_addr = (uint32_t(m_cmd[1]) << 2) & ~0xfU;
				break;
			case 3:   // return
				m_stats.returns++;
				if (m_ret_addr >= 0) {
					m_cmd_addr = uint32_t(m_ret_addr);
					m_ret_addr = -1;
				}
				break;
			default:
				break;
			}
			m_phase = phase::fetch;
			break;
		}
	}
}

//**************************************************************************
//  Frame handling
//**************************************************************************

void saturn_vdp1_device::latch_erase_params()
{
	m_erase.rot8 = (m_tvmr & (TVMR_8BPP | TVMR_ROTATE)) == (TVMR_8BPP | TVMR_ROTATE);
	m_erase.x_mask = m_erase.rot8 ? 0xff : 0x1ff;
	m_erase.y_start = m_ewlr & 0x1ff;
	m_erase.x_start = ((m_ewlr >> 9) & 0x3f) << 3;
	m_erase.y_end = m_ewrr & 0x1ff;
	m_erase.x_bound = ((m_ewrr >> 9) & 0x7f) << 3;
	m_erase.data = m_ewdr;
}

void saturn_vdp1_device::erase_row(unsigned y)
{
	uint16_t *row = display_buffer() + ((y & 0xff) << 9);
	if (m_erase.rot8)
		row += (y & 0x100);
	for (unsigned x = m_erase.x_start; x < m_erase.x_bound; x++)
		row[x & m_erase.x_mask] = m_erase.data;
}

// Vblank erase: the dots it can clear are limited by the time vblank lasts,
// (dots per raster - 200) * (vblank rasters) (ST-013 4.4 and Table 4.5); when it
// runs out the rest of the area is left as it was and games fill it with
// polygons. `budget` is in dots (VDP1 clocks).
void saturn_vdp1_device::erase_limited(int64_t budget)
{
	unsigned const width = m_erase.x_bound > m_erase.x_start ? m_erase.x_bound - m_erase.x_start : 1;
	for (unsigned y = m_erase.y_start; y <= m_erase.y_end && budget > 0; y++) {
		if (budget >= width) {
			erase_row(y);
			budget -= width;
		} else {
			uint16_t *row = display_buffer() + ((y & 0xff) << 9);
			if (m_erase.rot8)
				row += (y & 0x100);
			for (unsigned x = m_erase.x_start; budget > 0 && x < m_erase.x_start + width; x++, budget--)
				row[x & m_erase.x_mask] = m_erase.data;
			break;
		}
	}
}

// Vblank ends: erase for the vblank erase mode, then the frame buffer change
void saturn_vdp1_device::log_frame()
{
	auto const &st = m_stats;
	logerror("VDP1 frame: TVMR=%x FBCR=%02x PTMR=%x DIE/DIL latched=%d%d drawing=%d EDSR=%x COPR=%04x "
			"sysclip=%d,%d user=%d,%d-%d,%d local=%d,%d | cmds n=%u s=%u d=%u p=%u pl=%u l=%u uc=%u sc=%u lc=%u "
			"| skip=%u jump=%u call=%u ret=%u end=%u bad=%u | dots=%u clipped=%u\n",
			m_tvmr, m_fbcr, m_ptmr, m_die ? 1 : 0, m_dil ? 1 : 0, m_drawing ? 1 : 0, m_edsr, unsigned(m_cmd_addr >> 2),
			m_engine.sys_x, m_engine.sys_y, m_engine.user_x0, m_engine.user_y0, m_engine.user_x1, m_engine.user_y1,
			m_engine.local_x, m_engine.local_y,
			st.cmd[0], st.cmd[1], st.cmd[2] + st.cmd[3], st.cmd[4], st.cmd[5], st.cmd[6] + st.cmd[7],
			st.cmd[8] + st.cmd[0xb], st.cmd[9], st.cmd[0xa],
			st.skipped, st.jumps, st.calls, st.returns, st.ended, st.invalid,
			m_engine.stat_dots, m_engine.stat_clipped);
}

void saturn_vdp1_device::frame_change()
{
	update();
	if (m_log) {
		log_frame();
		m_stats = frame_stats();
		m_engine.stat_dots = m_engine.stat_clipped = 0;
	}
	latch_erase_params();

	if (m_vb_erase_active) {
		// 1708 clocks per raster at 320 dots, 1820 at 352 (ST-013 Table 4.4)
		int64_t const line_clocks = clock() > 27500000 ? 1820 : 1708;
		int64_t const clocks = (machine().time() - m_vblank_start).as_ticks(clock());
		int64_t const rasters = (clocks + line_clocks / 2) / line_clocks;
		erase_limited(rasters * (line_clocks - 200));
		m_vb_erase_active = false;
	}

	bool const swap = !(m_fbcr & FBCR_FCM) || (m_manual_pending && (m_fbcr & FBCR_FCT));
	if (swap) {
		if (m_drawing)
			stop_drawing();           // drawing is cut short by the frame buffer change

		m_draw_fb ^= 1;
		m_engine.fb = m_fb[m_draw_fb].get();

		// the buffer just drawn is displayed from now on: m_die/m_dil still hold what it was drawn with
		m_prev_die = m_disp_die;
		m_prev_dil = m_disp_dil;
		m_disp_die = m_die;
		m_disp_dil = m_dil;
		m_field_cur ^= 1;
		if (m_disp_die)
			std::copy_n(display_buffer(), FB_WORDS, m_field_copy[m_field_cur].get());

		m_edsr = m_edsr >> 1;         // BEF = CEF, CEF = 0
		m_lopr = uint16_t(m_cmd_addr >> 2);
		m_die = m_fbcr & FBCR_DIE;
		m_dil = m_fbcr & FBCR_DIL;

		if (m_ptmr & 2)               // automatic draw start on the frame change
			start_drawing();
	}

	m_erase_y = ~0U;
	if (!(m_fbcr & FBCR_FCM) || (m_manual_pending && !(m_fbcr & FBCR_FCT))) {
		if (m_tvmr & TVMR_ROTATE)
			m_vb_erase_pending = true;    // rotation forces erase during the next vblank
		else
			m_erase_y = m_erase.y_start;  // erased line by line while the picture is read
	}

	m_manual_pending = false;
}

void saturn_vdp1_device::vblank_w(int state)
{
	bool const old = m_vblank;
	m_vblank = state;
	if (old == m_vblank)
		return;

	if (m_vblank) {
		m_vblank_start = machine().time();
		// ST-013: VBE is set from the vblank-in handler and erase starts after it, so
		// it is looked at about a line after vblank starts, not at the edge
		m_vbe_timer->adjust(attotime::from_usec(VBE_SAMPLE_DELAY_US));
	} else {
		m_vbe_timer->adjust(attotime::never);
		frame_change();
	}
}

TIMER_CALLBACK_MEMBER(saturn_vdp1_device::vbe_sample)
{
	if (m_vblank && ((m_tvmr & TVMR_VBE) || m_vb_erase_pending)) {
		m_vb_erase_pending = false;
		m_vb_erase_active = true;
	}
}

void saturn_vdp1_device::hblank_w(int state)
{
	m_hblank = state;
}

// The VDP2 has read a line of the displayed frame buffer: erase moves on one row
void saturn_vdp1_device::display_line_done()
{
	if (m_erase_y <= m_erase.y_end) {
		erase_row(m_erase_y);
		m_erase_y++;
	}
}

uint16_t saturn_vdp1_device::display_pixel(unsigned x, unsigned y) const
{
	uint16_t const *row = display_buffer() + ((y & 0xff) << 9);
	if (bpp8()) {
		x &= 0x3ff;
		return 0xff00 | ((row[x >> 1] >> (((x & 1) ^ 1) << 3)) & 0xff);
	}
	return row[x & 0x1ff];
}

// A line of a double density interlace frame (0..447): one buffer row serves the two lines of a
// pair, and the line takes it from the field that was drawn for its parity (ST-013 4.2: DIL
// selects which lines a field plots; the two fields are different pictures). The field
// displayed now has its own parity; the other parity comes from the previous field.
uint16_t saturn_vdp1_device::display_pixel_field(unsigned x, unsigned line) const
{
	unsigned const row = line >> 1;
	bool const parity = line & 1;
	if (m_disp_die && parity != m_disp_dil && m_prev_die && parity == m_prev_dil) {
		uint16_t const *r = m_field_copy[m_field_cur ^ 1].get() + ((row & 0xff) << 9);
		if (bpp8()) {
			x &= 0x3ff;
			return 0xff00 | ((r[x >> 1] >> (((x & 1) ^ 1) << 3)) & 0xff);
		}
		return r[x & 0x1ff];
	}
	return display_pixel(x, row);
}

uint16_t saturn_vdp1_device::display_rotated_pixel(int32_t x, int32_t y) const
{
	uint16_t const *fb = display_buffer();
	if (bpp8()) {
		if ((x | y) & ~0x1ff)
			return 0;
		uint16_t const *row = fb + ((y & 0xff) << 9);
		unsigned const pos = (x & 0x1ff) | ((y & 0x100) << 1);
		return 0xff00 | ((row[pos >> 1] >> (((pos & 1) ^ 1) << 3)) & 0xff);
	}
	if ((x & ~0x1ff) | (y & ~0xff))
		return 0;
	return fb[(y << 9) + x];
}

//**************************************************************************
//  Bus interface
//**************************************************************************

uint16_t saturn_vdp1_device::regs_r(offs_t offset)
{
	if (!machine().side_effects_disabled())
		update();

	switch (offset) {
	case 0x10 / 2: return m_edsr;
	case 0x12 / 2: return m_lopr;
	case 0x14 / 2: return uint16_t(m_cmd_addr >> 2);
	case 0x16 / 2:   // MODR
		return 0x1000 | ((m_ptmr & 2) << 7) | ((m_fbcr & 0x1e) << 3) | (m_tvmr & 0xf);
	default:
		if (!machine().side_effects_disabled())
			logerror("%s: VDP1 read of write-only register %02x\n", machine().describe_context(), offset * 2);
		return 0;
	}
}

void saturn_vdp1_device::regs_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	update();

	auto const merge = [&](uint16_t old) { return uint16_t((old & ~mem_mask) | (data & mem_mask)); };

	switch (offset) {
	case 0x00 / 2:   // TVMR
		m_tvmr = merge(m_tvmr) & 0xf;
		break;

	case 0x02 / 2:   // FBCR
		m_fbcr = merge(m_fbcr) & 0x1f;
		if (data & mem_mask & 2)
			m_manual_pending = true;
		break;

	case 0x04 / 2: { // PTMR
		uint16_t const value = merge(0) & 3;
		// Bit 0 is the trigger. Writing 01 starts drawing without touching the
		// plot trigger mode selected by bit 1 (doom and exhumed write 10, then
		// start with 01, and expect the automatic start to stay armed).
		if (value != 1)
			m_ptmr = value & 2;
		if (value & 1)
			start_drawing();
		break;
	}

	case 0x06 / 2:   // EWDR
		m_ewdr = merge(m_ewdr);
		break;

	case 0x08 / 2:   // EWLR
		m_ewlr = merge(m_ewlr) & 0x7fff;
		break;

	case 0x0a / 2:   // EWRR
		m_ewrr = merge(m_ewrr);
		break;

	case 0x0c / 2:   // ENDR: forced termination of drawing
		if (m_drawing)
			stop_drawing();
		break;

	default:
		logerror("%s: VDP1 write of %04x to unknown register %02x\n", machine().describe_context(), data, offset * 2);
		break;
	}
}

// A CPU access to VRAM while the VDP1 is drawing waits for the VDP1's current
// burst: the system controller has priority over drawing, and the CPU "may
// have more than 10 wait cycles" at its 28 MHz clock (ST-013 "VRAM", VDP1
// User's Manual p.19). The manual gives only that lower bound, so it is used as
// the wait. The frame buffer is different: there drawing is interrupted and
// the CPU is not stalled (same manual, "Frame Buffer"), and draw time lost to
// such interruptions is not specified, so none is charged.
void saturn_vdp1_device::vram_access_wait()
{
	if (m_drawing && !machine().side_effects_disabled()) {
		if (device_execute_interface *const cpu = machine().scheduler().currently_executing())
			cpu->adjust_icount(-VRAM_CPU_WAIT);
	}
}

uint32_t saturn_vdp1_device::vram_r(offs_t offset)
{
	if (!machine().side_effects_disabled())
		update();
	vram_access_wait();
	offset &= (VRAM_WORDS / 2) - 1;
	return (uint32_t(m_vram[offset * 2]) << 16) | m_vram[offset * 2 + 1];
}

void saturn_vdp1_device::vram_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	update();
	vram_access_wait();
	offset &= (VRAM_WORDS / 2) - 1;
	if (ACCESSING_BITS_16_31)
		m_vram[offset * 2] = uint16_t((m_vram[offset * 2] & ~(mem_mask >> 16)) | ((data >> 16) & (mem_mask >> 16)));
	if (ACCESSING_BITS_0_15)
		m_vram[offset * 2 + 1] = uint16_t((m_vram[offset * 2 + 1] & ~mem_mask) | (data & mem_mask));
}

// Word index into the draw frame buffer for a CPU access. In the 8 bpp rotated
// mode the CPU sees the buffer as 1024 byte wide rows in two halves.
uint32_t saturn_vdp1_device::fb_word_index(uint32_t word) const
{
	uint32_t address = word << 1;
	if ((m_tvmr & (TVMR_8BPP | TVMR_ROTATE)) == (TVMR_8BPP | TVMR_ROTATE))
		address = (address & 0x1ff) | ((address << 1) & 0x3fc00) | ((address >> 8) & 0x200);
	return (address >> 1) & (FB_WORDS - 1);
}

uint32_t saturn_vdp1_device::fb_r(offs_t offset, uint32_t mem_mask)
{
	if (!machine().side_effects_disabled())
		update();
	uint16_t const *fb = m_fb[m_draw_fb].get();
	return (uint32_t(fb[fb_word_index(offset * 2)]) << 16) | fb[fb_word_index(offset * 2 + 1)];
}

void saturn_vdp1_device::fb_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	update();
	uint16_t *fb = m_fb[m_draw_fb].get();
	if (ACCESSING_BITS_16_31) {
		uint16_t &w = fb[fb_word_index(offset * 2)];
		w = uint16_t((w & ~(mem_mask >> 16)) | ((data >> 16) & (mem_mask >> 16)));
	}
	if (ACCESSING_BITS_0_15) {
		uint16_t &w = fb[fb_word_index(offset * 2 + 1)];
		w = uint16_t((w & ~mem_mask) | (data & mem_mask));
	}
}

/*
  Game observations carried over from the legacy VDP1 core, kept as a check
  list of the titles that exercise the corner cases:

  - kiwames (ST-V), blaztorn (VS screen in player-vs-player): erase too early
    while the game expects the idle/draw state to stay set.
  - batmanfr (ST-V) gameplay, nightstr (draws in automatic mode): draw end
    interrupt timing.
  - Illegal sprite entries (timing?): needs tests on real hardware.
  - Mixing with VDP2 priority per dot: basically any Mega Drive Sega Ages.
  - blaztorn match intro, twcup98 (ST-V) team select, sandor (ST-V) moai
    sub-game: polygon vertices in the wrong place.
  - capgen4 Yoko/Tate modes: frame buffer rotation shared with the VDP2.
  - groovef VS zoom-in animation, flag stripes in the Sega soccer/baseball
    games: scaling rounding.
  - gnine96 stadium select: stippled oblique polylines on wireframes.
  - jeworaclj, vhydlid: transparent pixel flag.
  - dariusg intro, 3dwarvesu after continue: colours.
  - suikoenb (ST-V): wrong pitch set in special cases.
  - Frame buffer erase/change: kiwames' "draw by request" needs a fast enough
    refresh; pblbeach does not clear the local coordinates set by the BIOS.
*/

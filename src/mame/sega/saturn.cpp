// license:LGPL-2.1+
// copyright-holders:David Haywood, Angelo Salese, Olivier Galibert, Mariusz Wojcieszek, R. Belmont
// Saturn/ST-V shared driver state: SCU/SMPC glue, VDP2 memories and the scanline hook.
// The VDP1 is in saturn_vdp1.cpp, the VDP2 picture in saturn_vdp2_render.cpp.
/**************************************************************************************************

    Sega Saturn (c) 1994 Sega

    @TODO List of things that needs to be implemented:
    - There's definitely an ack mechanism in SCU irqs. This is almost surely done via
      the ISM register (i.e. going 0->1 to the given bit acks it).
    - There might be a delay to exactly when SCU irqs happens. This is due to the basic
      fact that SCU runs at 14-ish MHz, so it needs some time before actually firing the
      irq.
    - Vblank-Out actually happens at the last screen line, not at 0.
    - VDP2 V counter has a similar roll-back as MD correspondent register:
      vpos line 0 == 0x1ff (Vblank-Out happens here)
      vpos line 1 == 0
      ...
      vpos line 241 == 0xf0 (Vblank-In happens here)
      vpos line 246 == 0xf5
      vpos line 247 == 0x1ef (rolls back here)
      vpos line 263 == 0x1ff again
    - HBlank bit seems to follow a normal logic instead.
    - Timer 0 doesn't work if the TENB bit isn't enabled (documentation is a bit fussy
      over this).
    - Timer 0 fires at the HBlank-In signal, not before.
    - VDP2 H Counter actually counts x2 in non Hi-Res mode.
    - Timer 1 is definitely annoying. Starts from H-Blank signal and starts counting from
      that position.
      H counter value 0x282 (642) -> timer 1 fires at setting 1
      H counter value 0x284 (644) -> 2
      H counter value 0x2a0 (672) -> 0x10
      H counter value 0x2c0 (704) -> 0x20
      H counter value 0x300 (768) -> 0x40
      H counter value 0x340 (832) -> 0x60
      H counter value 0x352 (850) -> 0x69
      H counter value 0x000 (0)   -> 0x6a, V counter goes +1 here (max range?)
      H counter value 0x02c (44)  -> 0x80
      H counter value 0x0ec (236) -> 0xe0
      H counter value 0x12c (300) -> 0x100
    - Timer 1 seems to count backwards compared to Timer 0 from setting 0x6b onward.
    - Yabause claims that if VDP2 DISP bit isn't enabled then vblank irqs (hblank too?)
      doesn't happen.

**************************************************************************************************/



#include "emu.h"
#include "saturn.h"

#include "cpu/scudsp/scudsp.h"

#include <cstdlib>


void saturn_state::machine_start()
{
	// a loaded state starts with a free SH-2 bus
	machine().save().register_postload(save_prepost_delegate(FUNC(saturn_state::sh2_bus_reset), this));
}


void saturn_state::machine_reset()
{
	m_scsp_last_line = 0;

	sh2_bus_reset();

	// don't let the slave cpu and the 68k go anywhere
	m_slave->set_input_line(INPUT_LINE_RESET, ASSERT_LINE);
	m_audiocpu->set_input_line(INPUT_LINE_RESET, ASSERT_LINE);

	// the 320 dot mode clocks, NTSC or PAL (Overview Manual Rel.2.5, Table 3.1.1)
	XTAL const reset_clock = m_vdp2->is_pal() ? MASTER_CLOCK_320_PAL : MASTER_CLOCK_320;
	m_maincpu->set_unscaled_clock(reset_clock / 2);
	m_slave->set_unscaled_clock(reset_clock / 2);

	m_en_68k = 0;

}


void saturn_state::soundram_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	//machine().scheduler().synchronize(); // force resync

	COMBINE_DATA(&m_sound_ram[offset]);
}

uint16_t saturn_state::soundram_r(offs_t offset)
{
	//machine().scheduler().synchronize(); // force resync

	return m_sound_ram[offset];
}

uint8_t saturn_state::backupram_r(offs_t offset)
{
	if(!(offset & 1))
		return 0; // yes, it makes sure the "holes" are there.

	return m_backupram[offset >> 1] & 0xff;
}

void saturn_state::backupram_w(offs_t offset, uint8_t data)
{
	if(!(offset & 1))
		return;

	m_backupram[offset >> 1] = data;
}


void saturn_state::m68k_reset_callback(int state)
{
	logerror("m68k RESET opcode triggered\n");
	m_smpc_hle->m68k_reset_trigger();
}

void saturn_state::scsp_irq(offs_t offset, uint8_t data)
{
	// don't bother the 68k if it's off
	if (!m_en_68k)
	{
		return;
	}

	if (offset != 0)
	{
		if (data == ASSERT_LINE) m_scsp_last_line = offset;
		m_audiocpu->set_input_line(offset, data);
	}
	else
	{
		m_audiocpu->set_input_line(m_scsp_last_line, data);
	}
}


/*
(Preliminary) explanation about this:
VBLANK-OUT is used at the start of the vblank period. It also sets the timer zero
variable to 0.
If the Timer Compare register is zero too,the Timer 0 irq is triggered.

HBLANK-IN is used at the end of each scanline except when in VBLANK-IN/OUT periods.

The timer 0 is also incremented by one at each HBLANK and checked with the value
of the Timer Compare register;if equal,the timer 0 irq is triggered here too.
Notice that the timer 0 compare register can be more than the VBLANK maximum range,in
this case the timer 0 irq is simply never triggered.This is a known Sega Saturn/ST-V "bug".

VBLANK-IN is used at the end of the vblank period.

SCU register[36] is the timer zero compare register.
SCU register[40] is for IRQ masking.

TODO:
- VDP1 timing and CEF emulation isn't accurate at all.
*/

void saturn_state::vint_callback(int state)
{
	if (m_prev_vint != state)
	{
		if (state)
		{
			m_scu->vblank_in_w(1);
			m_slave->set_input_line(0x6, ASSERT_LINE);
		}
		else
		{
			m_scu->vblank_out_w(1);
			m_slave->set_input_line(0x4, ASSERT_LINE);
		}
	}

	m_prev_vint = state;
	m_vdp1->vblank_w(state);

	// the SMPC collects the peripheral data relative to the blanking
	if (state)
		m_smpc_hle->vblank_in_w(1);
	else
		m_smpc_hle->vblank_out_w(1);
}

void saturn_state::hint_callback(int state)
{
	if (!m_prev_hint && state)
	{
		m_scu->hblank_in_w(1);
		m_slave->set_input_line(0x2, ASSERT_LINE);
	}
	else if (m_prev_hint && !state)
	{
		// Essentially clears?
		m_slave->set_input_line(0x0, ASSERT_LINE);
	}

	m_prev_hint = state;
	m_vdp1->hblank_w(state);
}

TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)
{
	m_vdp1->update();
	vdp2_scanline(param);
}

void saturn_state::master_sh2_reset_w(int state)
{
	m_maincpu->set_input_line(INPUT_LINE_RESET, state ? ASSERT_LINE : CLEAR_LINE);
}

void saturn_state::master_sh2_nmi_w(int state)
{
	m_maincpu->set_input_line(INPUT_LINE_NMI, state ? ASSERT_LINE : CLEAR_LINE);
}

void saturn_state::slave_sh2_reset_w(int state)
{
	m_slave->set_input_line(INPUT_LINE_RESET, state ? ASSERT_LINE : CLEAR_LINE);
//  m_smpc.slave_on = state;
}

void saturn_state::sound_68k_reset_w(int state)
{
	m_audiocpu->set_input_line(INPUT_LINE_RESET, state ? ASSERT_LINE : CLEAR_LINE);
	m_en_68k = state ^ 1;
}

// TODO: edge triggered?
void saturn_state::system_reset_w(int state)
{
	if(!state)
		return;

	// TODO: actually send a device reset signal to the connected devices
	/*Only backup ram and SMPC ram are retained after that this command is issued.*/
	m_scu->reset();
	memset(m_sound_ram,0x00,0x080000);
	memset(m_workram_h,0x00,0x100000);
	memset(m_workram_l,0x00,0x100000);
	memset(m_vdp2_regs.get(),0x00,0x040000);
	memset(m_vdp2_vram.get(),0x00,0x100000);
	memset(m_vdp2_cram.get(),0x00,0x080000);
	m_vdp1->system_reset();
	//A-Bus
}

void saturn_state::system_halt_w(int state)
{
	m_maincpu->set_input_line(INPUT_LINE_HALT, state ? ASSERT_LINE : CLEAR_LINE);
	m_slave->set_input_line(INPUT_LINE_HALT, state ? ASSERT_LINE : CLEAR_LINE);
	m_audiocpu->set_input_line(INPUT_LINE_HALT, state ? ASSERT_LINE : CLEAR_LINE);
}

void saturn_state::dot_select_w(int state)
{
	// the PAL clocks are those of the same two modes at the PAL line rate (Overview Manual Rel.2.5, Table 3.1.1)
	const bool pal = m_vdp2->is_pal();
	const XTAL xtal = state ? (pal ? MASTER_CLOCK_320_PAL : MASTER_CLOCK_320) : (pal ? MASTER_CLOCK_352_PAL : MASTER_CLOCK_352);

	m_maincpu->set_unscaled_clock(xtal / 2);
	m_slave->set_unscaled_clock(xtal / 2);
	m_dcc->set_unscaled_clock(xtal / 2);

	m_scu->set_unscaled_clock(xtal);

	m_vdp1->set_unscaled_clock(xtal / 2);
	m_vdp2->set_unscaled_clock(xtal);
	m_vdp2->set_dotsel(!state);

	m_scsp->reset();
	m_scu->reset();
	m_vdp1->reset();
	m_vdp2->reset();
}


/* Sega Saturn VDP2: memories and the video start hook. The picture is drawn by saturn_vdp2_render. */

uint32_t saturn_state::vdp2_vram_r(offs_t offset)
{
	return m_vdp2_vram[offset];
}

void saturn_state::vdp2_vram_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_vdp2_vram[offset]);
}

uint16_t saturn_state::vdp2_regs_r(offs_t offset)
{
	return m_vdp2_regs[offset];
}

// Extra SCU clocks a write to a 128KB VDP2 VRAM bank takes while the screen is being displayed: the
// display uses some of the bank's access slots (cycle pattern types 0-7 and 0xc/0xd of the enabled
// scroll screens, or the whole cycle for rotation), and the write waits for what is left. Table from
// Mednafen's hardware measurements, indexed by the number of display slots in use (0..8).
uint8_t saturn_state::vdp2_vram_write_penalty(offs_t bank)
{
	if (m_vdp2->is_blanking())
		return 0;

	const uint16_t bgon = m_vdp2_regs[0x20 / 2] & 0x1f3f;
	const unsigned ramctl = m_vdp2_regs[0x0e / 2];
	const unsigned vram_mode = (ramctl >> 8) & 3;
	const unsigned rdbs_mode = ramctl & 0xff;
	const unsigned sh = (m_vdp2->get_hreso() & 6) ? 0 : 4;

	// cycle pattern type of slot i of a bank
	auto const cycle_type = [this](unsigned b, unsigned i) -> unsigned
	{
		const uint16_t reg = m_vdp2_regs[(0x10 + b * 4 + (i >> 2) * 2) / 2];
		return (reg >> (12 - 4 * (i & 3))) & 0xf;
	};
	auto const slot_penalty = [&](unsigned type) -> unsigned
	{
		if (type < 0x8 || type == 0xc || type == 0xd)
			return BIT(bgon, type & 3);
		return 0;
	};

	// a split bank has its own cycle pattern, otherwise the pair uses the first one
	const unsigned esb = bank & (2 | ((vram_mode >> (bank >> 1)) & 1));
	const unsigned rdbs = (rdbs_mode >> (esb << 1)) & 3;   // 0: unused for rotation
	unsigned used = 0;

	if (BIT(bgon, 5))
	{
		if (bank >= 2 || (BIT(bgon, 4) && rdbs != 0))
			used = 8;
	}
	else if (BIT(bgon, 4) && rdbs != 0)
	{
		used = 8;
	}
	else if (bgon & 0x0f)
	{
		for (unsigned i = 0; i < 4; i++)
			used += slot_penalty(cycle_type(esb, i)) + slot_penalty(cycle_type(esb, sh + i));
	}

	static const uint8_t PENALTY[9] = { 0, 0, 0, 0, 1, 1, 2, 3, 4 };
	return PENALTY[used];
}

uint32_t saturn_state::vdp2_cram_r(offs_t offset)
{
	offset &= 0xfff >> 2;
	return m_vdp2_cram[offset];
}

void saturn_state::vdp2_cram_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	offset &= 0xfff >> 2;
	COMBINE_DATA(&m_vdp2_cram[offset]);

	// colour RAM mode 0 holds 1024 entries: a write reaches both halves of the 4KB window
	if (!BIT(m_vdp2_regs[0x00e / 2], 12, 2))
		m_vdp2_cram[offset ^ 0x200] = m_vdp2_cram[offset];
}

void saturn_state::vdp2_regs_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_vdp2_regs[offset]);

	if (offset == 0x0b2 / 2)
		m_vdp2_renderer.rprctl_written(m_vdp2_regs[offset]);
}

int saturn_state::vdp2_start()
{
	m_vdp2_regs = make_unique_clear<uint16_t[]>(0x040000 / 2);
	m_vdp2_vram = make_unique_clear<uint32_t[]>(0x100000 / 4);
	m_vdp2_cram = make_unique_clear<uint32_t[]>(0x080000 / 4);
	m_vdp2_frame = make_unique_clear<uint32_t[]>(saturn_vdp2_render::renderer::MAX_WIDTH * 512);

	save_pointer(NAME(m_vdp2_regs), 0x040000 / 2);
	save_pointer(NAME(m_vdp2_vram), 0x100000 / 4);
	save_pointer(NAME(m_vdp2_cram), 0x080000 / 4);

	return 0;
}

VIDEO_START_MEMBER(saturn_state, vdp2_video_start)
{
	vdp2_start();
}

// Diagnostics: SATURN_LEGACY_DDI=<hex mask> turns off the double density interlace behaviours added
// on top of the original renderer, to find which one a game depends on:
// 1 field rendering (every line each frame), 2 erase of the displayed buffer once per frame line,
// 4 weave of the two sprite fields (one buffer row for both lines), 8 rotation parameters stepped
// per frame line
static unsigned legacy_ddi()
{
	static unsigned const mask = std::getenv("SATURN_LEGACY_DDI") ? unsigned(std::strtoul(std::getenv("SATURN_LEGACY_DDI"), nullptr, 16)) : 0;
	return mask;
}

// VDP1 frame buffer as the VDP2 reads it for the sprite layer. The VDP2 dot
// maps to the frame buffer dot: doubled horizontally when the buffer is 16 bit
// and the screen is hi-res, read at twice the pitch when the buffer is 8 bit
// and the screen is low resolution, and every buffer row is used for two
// lines of a double density screen.
class saturn_state::vdp2_sprite_fb : public saturn_vdp2_render::sprite_source
{
public:
	vdp2_sprite_fb(saturn_vdp1_device const &vdp1, bool half_lines, bool half_res, bool double_res)
		: m_vdp1(vdp1), m_half_lines(half_lines), m_half_res(half_res), m_double_res(double_res)
	{
	}

	virtual uint16_t sprite_word(unsigned x, unsigned y) const override
	{
		unsigned const dx = (x << (m_half_res ? 1 : 0)) >> (m_double_res ? 1 : 0);
		return (m_half_lines && !(legacy_ddi() & 4)) ? m_vdp1.display_pixel_field(dx, y) : m_vdp1.display_pixel(dx, y >> (m_half_lines ? 1 : 0));
	}

	virtual uint16_t sprite_word_rotated(int32_t x, int32_t y) const override
	{
		return m_vdp1.display_rotated_pixel(x, y);
	}

private:
	saturn_vdp1_device const &m_vdp1;
	bool m_half_lines;
	bool m_half_res;
	bool m_double_res;
};

// Called at the start of every scanline: draws that line of the VDP2 picture
// with the registers and memories as they are now, so raster effects done by
// changing registers between lines show up.
void saturn_state::vdp2_scanline(int scanline)
{
	static constexpr unsigned widths[4] = { 320, 352, 640, 704 };
	if (scanline < 0 || scanline >= 512 || scanline > m_screen->visible_area().bottom())
		return;

	uint8_t const hreso = m_vdp2->get_hreso();

	saturn_vdp2_render::memory mem;
	mem.regs = m_vdp2_regs.get();
	mem.vram = m_vdp2_vram.get();
	mem.cram = m_vdp2_cram.get();
	mem.vram_mask = 0x7ffff;

	saturn_vdp2_render::screen_config cfg;
	cfg.width = widths[hreso & 3];
	cfg.hires = BIT(hreso, 1);
	cfg.hreso = hreso;
	cfg.exclusive = BIT(hreso, 2);
	cfg.lsmd = m_vdp2->get_lsmd();
	cfg.disp = m_vdp2->get_disp();
	cfg.bdclmd = m_vdp2->get_bdclmd();
	cfg.pal = m_vdp2->is_pal();
	cfg.fb_rotate = m_vdp1->rotate();

	if (scanline == 0)
	{
		unsigned const prev_dots = m_vdp2_renderer.stat_sprite_dots, prev_shown = m_vdp2_renderer.stat_sprite_shown;
		m_vdp2_renderer.stat_sprite_dots = m_vdp2_renderer.stat_sprite_shown = 0;
		m_vdp2_renderer.begin_frame(mem, cfg);

		// diagnostics (environment variable SATURN_VDP1_LOG): what the VDP2 shows of the sprite layer
		static bool const log = std::getenv("SATURN_VDP1_LOG") != nullptr;
		if (log)
		{
			auto const r = [&mem](unsigned off) { return unsigned(mem.regs[off >> 1]); };
			logerror("VDP2 frame: TVMD=%04x (lsmd=%u hreso=%u vreso=%u disp=%u) RAMCTL=%04x BGON=%04x SPCTL=%04x "
					"PRISA=%04x,%04x,%04x,%04x CCCTL=%04x WCTL=%04x,%04x,%04x,%04x TVSTAT sprite fb: bpp8=%d rotate=%d hdtv=%d | PRINA=%04x PRINB=%04x PRIR=%04x CRAOFB=%04x SDCTL=%04x LNCLEN=%04x | prev frame sprite dots=%u shown=%u\n",
					r(0x00), cfg.lsmd, cfg.hreso, m_vdp2->get_vreso(), cfg.disp ? 1 : 0, r(0x0e), r(0x20), r(0xe0),
					r(0xf0), r(0xf2), r(0xf4), r(0xf6), r(0xec), r(0xd0), r(0xd2), r(0xd4), r(0xd6),
					m_vdp1->bpp8() ? 1 : 0, m_vdp1->rotate() ? 1 : 0, m_vdp1->hdtv() ? 1 : 0,
					r(0xf8), r(0xfa), r(0xfc), r(0xe6), r(0xe2), r(0xe8), prev_dots, prev_shown);
		}
	}
	else
		m_vdp2_renderer.set_config(mem, cfg);

	bool const plain = !m_vdp1->hdtv() && !m_vdp1->rotate();
	vdp2_sprite_fb const sprites(
			*m_vdp1,
			cfg.lsmd == 3,
			plain && m_vdp1->bpp8() && (hreso & 6) == 0,
			(plain && !m_vdp1->bpp8() && (hreso & 6) == 2) || BIT(hreso, 2));

	// double density interlace: each 1/60 s field shows the lines of one parity, the lines of the
	// other parity keep what the previous field drew (the two fields are different pictures)
	bool const other_field = cfg.lsmd == 3 && !cfg.exclusive && ((scanline & 1) != int(m_screen->frame_number() & 1)) && !(legacy_ddi() & 1);
	m_vdp2_renderer.legacy_rotation_step = legacy_ddi() & 8;
	m_vdp2_renderer.render_line(scanline, sprites, &m_vdp2_frame[scanline * saturn_vdp2_render::renderer::MAX_WIDTH], other_field);
	// the erase of the displayed buffer follows the read-out one buffer row at a time; in double
	// density two frame lines read the same row, so it advances on every second line
	if (cfg.lsmd != 3 || (scanline & 1) || (legacy_ddi() & 2))
		m_vdp1->display_line_done();
}

uint32_t saturn_state::screen_update_vdp2(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect)
{
	for (int y = cliprect.top(); y <= cliprect.bottom() && y < 512; y++)
	{
		uint32_t const *const src = &m_vdp2_frame[y * saturn_vdp2_render::renderer::MAX_WIDTH];
		uint32_t *const dest = &bitmap.pix(y);
		for (int x = cliprect.left(); x <= cliprect.right() && x < int(saturn_vdp2_render::renderer::MAX_WIDTH); x++)
			dest[x] = 0xff000000 | src[x];
	}

	return 0;
}

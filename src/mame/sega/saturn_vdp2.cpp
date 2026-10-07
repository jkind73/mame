// license:BSD-3-Clause
// copyright-holders:Angelo Salese
/**************************************************************************************************

Sega Saturn VDP2 (c) 1995 Sega/Yamaha

TODO:
- stub overlay for screen timings and not much else

**************************************************************************************************/

#include "emu.h"
#include "saturn_vdp2.h"

#define VERBOSE 0
//#define LOG_OUTPUT_FUNC osd_printf_info

#include "logmacro.h"

DEFINE_DEVICE_TYPE(SATURN_VDP2, saturn_vdp2_device, "saturn_vdp2", "Sega Saturn VDP2 (Yamaha 315-5690)")

saturn_vdp2_device::saturn_vdp2_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, SATURN_VDP2, tag, owner, clock)
	, m_screen(*this, finder_base::DUMMY_TAG)
	, m_vint_cb(*this)
	, m_hint_cb(*this)
	, m_is_pal(false)
{
}


void saturn_vdp2_device::device_start()
{
	m_hblank_timer = timer_alloc(FUNC(saturn_vdp2_device::hblank_timer_cb), this);
	m_vblank_timer = timer_alloc(FUNC(saturn_vdp2_device::vblank_timer_cb), this);
	m_hblank_rising = true;
	m_vblank_next_in = true;
	init_vcounter_table();

	save_item(NAME(m_tvmd));
	save_item(NAME(m_old_tvmd));
	save_item(NAME(m_disp));
	save_item(NAME(m_bdclmd));
	save_item(NAME(m_lsmd));
	save_item(NAME(m_vreso));
	save_item(NAME(m_hreso));
	save_item(NAME(m_odd_bit));
	save_item(NAME(m_hdisplay));
	save_item(NAME(m_vdisplay));
	save_item(NAME(m_dotsel_352));
	save_item(NAME(m_hblank_rising));
	save_item(NAME(m_vblank_next_in));

	save_item(NAME(m_exten));
	save_item(NAME(m_exlten));
	save_item(NAME(m_exsyen));
	save_item(NAME(m_dasel));
	save_item(NAME(m_exbgen));

	save_item(NAME(m_exltfg));
	save_item(NAME(m_exsyfg));

	save_item(NAME(m_hcounter_latch));
	save_item(NAME(m_vcounter_latch));

	m_hreso = 0;
	m_vreso = 0;
	m_dotsel_352 = false;

}

void saturn_vdp2_device::device_reset()
{
	m_odd_bit = 1;
	// shouldn't really matter
	m_old_tvmd = 0xffff;
//	m_hreso = 0;
//	m_vreso = 0;
//	m_dotsel_352 = true;
	reconfigure_crtc();
}

void saturn_vdp2_device::init_vcounter_table()
{
	// put vcounter inside a table
	// 224 mode
	for(u16 i = 0; i < 263; i++)
	{
		true_vcount[i][0] = i;
		if(i > 0xec)
			true_vcount[i][0] += 0xf9;
	}

	// 240 mode
	for(u16 i = 0; i < 263; i++)
	{
		true_vcount[i][1] = i;
		if(i > 0xf5)
			true_vcount[i][1] += 0xf9;
	}

	// TODO: PAL only 256 mode
	for(u16 i = 0; i < 313; i++)
	{
		true_vcount[i][2] = i;
		true_vcount[i][3] = i;
	}
}


/*
 *
 * Register Map
 *
 */

// $5f80000 base
void saturn_vdp2_device::regs_map(address_map &map)
{
	// $5f80000 TVMD TV Mode
	// x--- ---- ---- ---- DISP (0 = blanked)
	// ---- ---x ---- ---- BDCLMD (1 = back screen, 0 = black)
	// ---- ---- xx-- ---- LSMD interlace mode
	// ---- ---- --xx ---- VRESO vertical resolution
	// ---- ---- ---- -xxx HRESO horizontal resolution
	map(0x0000, 0x0001).lrw16(
		NAME([this] () { return m_tvmd; }),
		NAME([this] (offs_t offset, u16 data, u16 mem_mask) {
			COMBINE_DATA(&m_tvmd);
			m_disp = BIT(m_tvmd, 15);
			m_bdclmd = BIT(m_tvmd, 8);
			m_lsmd = (m_tvmd >> 6) & 3;
			m_vreso = (m_tvmd >> 4) & 3;
			m_hreso = (m_tvmd >> 0) & 7;
			if (ACCESSING_BITS_0_7 && (m_tvmd & 0xff) != (m_old_tvmd & 0xff))
				reconfigure_crtc();
			m_old_tvmd = m_tvmd;
		})
	);

	// $5f80002 EXTEN External Signal Enable
	map(0x0002, 0x0003).lrw16(
		NAME([this] (offs_t offset) {
			// latch HV counters when reading this register
			if (!machine().side_effects_disabled() && !m_exlten)
			{
				m_hcounter_latch = get_hcounter();
				m_vcounter_latch = get_vcounter();

				m_exltfg |= 1;
			}

			return m_exten;
		}),
		NAME([this] (offs_t offset, u16 data, u16 mem_mask) {
			// may be triggered a whole ton by games that DMA over this region
			if (data & 0x0303)
				LOG("5f80002h: EXTEN External Signal Enable %04x & %04x\n", data, mem_mask);
			COMBINE_DATA(&m_exten);
			m_exlten = BIT(m_exten, 9);
			m_exsyen = BIT(m_exten, 8);
			m_dasel = BIT(m_exten, 1);
			m_exbgen = BIT(m_exten, 0);
		})
	);

	// $5f80004 TVSTAT Screen Status (r/o)
	map(0x004, 0x005).lr16(NAME([this] () {
		// Doc claims odd bit to be always '1' for non-interlace but:
		// - stv:seabass (BIOS to game transition wants this to be 0)
		// - stv:grdforce (tests this bit to be 1 from title screen to gameplay)
		// - stv:finlarch/sasissu/magzun
		// Exclusive modes force this to '1'
		const bool odd_flag = m_odd_bit | BIT(m_hreso, 2);

		// if DISP off then return '1'
		const bool vblank_flag = get_vblank() | (!m_disp);

		// TODO: is hblank supposed to return '1' on DISP off as well?

		const u16 res = ((m_exltfg << 9)
			| (m_exsyfg << 8)
			| (vblank_flag << 3)
			| (get_hblank() << 2)
			| (odd_flag << 1)
			| m_is_pal);

		// clear these flags if this register is read
		if (!machine().side_effects_disabled())
		{
			m_exltfg &= ~1;
			m_exsyfg &= ~1;
		}

		return res;
	}));

	// $5f80006 VRSIZE VRAM Size
	// x--- ---- ---- ---- VRAMSZ (0 = 4MB mode 1 = 8MB mode)
	// ---- ---- ---- xxxx VER silicon version (r/o)
	map(0x006, 0x007).lrw16(
		NAME([this] () {
			// TODO: version
			return (m_vramsz << 15) | (0 & 0xf);
		}),
		NAME([this] (offs_t offset, u16 data, u16 mem_mask) {
			// TODO: probably akin to YM7101 equivalent on stock Saturn
			if (ACCESSING_BITS_8_15)
				m_vramsz = BIT(data, 15);
		})
	);

	// $5f80008 HCNT (r/o)
	map(0x008, 0x009).lr16(NAME([this] () { return m_hcounter_latch; }));
	// $5f8000a VCNT (r/o)
	map(0x00a, 0x00b).lr16(NAME([this] () { return m_vcounter_latch; }));

}


/*
 *
 * CRTC
 *
 */

void saturn_vdp2_device::device_clock_changed()
{
	reconfigure_crtc();
}

int saturn_vdp2_device::get_hblank_duration()
{
	const int base_htotal[2] = { 427, 455 };

	int res = base_htotal[BIT(m_hreso, 0)];

	// x2 horizontal resolution in 640/704 modes
	if(BIT(m_hreso, 1))
		res <<= 1;

	return res;
}

// some vblank lines measurements (according to Charles MacDonald)
// TODO: interlace mode "eats" one line, should be 262.5
int saturn_vdp2_device::get_vblank_duration()
{
	const int base_vtotal[2] = { 263, 313 };
	int res = base_vtotal[m_is_pal];

	// compensate for double density interlace
	if(m_lsmd == 3)
		res <<= 1;

	// Exclusive modes
	if(BIT(m_hreso, 2))
	{
		res = BIT(m_hreso, 0) ? 561 : 525;
	}

	return res;
}

int saturn_vdp2_device::get_pixel_clock()
{
	int res, divider;

	res = this->clock();
	// TODO: divider is always 8, need to compensate out of lack of MAME interlace support
	divider = 8;

	if(BIT(m_hreso, 1))
		divider >>= 1;

	if(m_lsmd == 3)
		divider >>= 1;

	 // TODO: Unknown for Exclusive modes
	if(BIT(m_hreso, 2))
		divider >>= 1;

	return res / divider;
}


void saturn_vdp2_device::reconfigure_crtc()
{
	const int d_vres[4] = { 224, 240, 256, 256 };
	const int d_hres[4] = { 320, 352, 640, 704 };
	int horz_res, vert_res;

	// TODO: guard against the wrong DOTSEL being configured from SMPC.
	// on real HW this causes monitor instability and unusable vblank IRQs.
	// astrass will throw a fuss if we do this in scan timer, also hot path ...
	//if (BIT(m_hreso, 0) != m_dotsel_352)
	//	return;

	// reset odd bit if a dynamic resolution change occurs, stv:seabass cares
	m_odd_bit = 1;
	// NTSC can't set 256 modes
	const u8 vres_mask = (m_is_pal << 1) | 1;
	vert_res = d_vres[m_vreso & vres_mask];

	// TODO: this should just be reserved and return VRESO == 2
	//if((m_vreso & 3) == 3)
	//	popmessage("Illegal VRES MODE");

	// In double density interlace bump by x2 the vertical resolution
	if(m_lsmd == 3) { vert_res *= 2;  }

	horz_res = d_hres[m_hreso & 3];
	// Exclusive modes (31kHz and Hi-Vision) sets a vertical resolution of 480 regardless of what
	// VRESO says
	// TODO: find a software that makes use of this
	if(BIT(m_hreso, 2))
		vert_res = 480;

	int vblank_period, hblank_period;
	rectangle visarea(0, horz_res - 1, 0, vert_res - 1);

	vblank_period = get_vblank_duration();
	hblank_period = get_hblank_duration();
	attotime refresh  = attotime::from_ticks(hblank_period * vblank_period, get_pixel_clock());
	//printf("%d %d %d %d\n",horz_res,vert_res,horz_res+hblank_period,vblank_period);

	// save these to reuse them in scan timer
	m_hdisplay = horz_res;
	m_vdisplay = vert_res;

	m_screen->configure(hblank_period, vblank_period, visarea, refresh);
	schedule_hblank();
	schedule_vblank();
}

int saturn_vdp2_device::get_hcounter()
{
	int hcount;

	hcount = m_screen->hpos();

	switch(m_hreso & 6)
	{
		// Normal
		case 0:
			hcount &= 0x1ff;
			hcount <<= 1;
			break;
		// Hi-Res
		case 2:
			hcount &= 0x3ff;
			break;
		// Exclusive Normal
		case 4:
			hcount &= 0x1ff;
			break;
		// Exclusive Hi-Res
		case 6:
			hcount >>= 1;
			hcount &= 0x1ff;
			break;
	}

	return hcount;
}

int saturn_vdp2_device::get_vcounter()
{
	int vcount;

	vcount = m_screen->vpos();

	// Exclusive Monitor
	if(BIT(m_hreso, 2))
		return vcount & 0x3ff;

	// Double Density Interlace
	if(m_lsmd == 3)
		return (vcount & ~1) | (m_screen->frame_number() & 1);

	// docs says << 1, but according to HW tests it's a typo.
	assert((vcount & 0x1ff) < std::size(true_vcount));
	return (true_vcount[vcount & 0x1ff][m_vreso]); // Non-interlace
}

// The TVSTAT HBLANK flag is set from dot 0x144 (0x164 in a 352 dot mode) until dot 4 of the
// next line, in low resolution dots (MiSTer VDP2.sv HBLANK_START). The vertical blank flag is
// set from the first line of the interval to the line before the last.
int saturn_vdp2_device::get_hblank()
{
	if (BIT(m_hreso, 2))
		return m_screen->hpos() > m_screen->visible_area().right() ? 1 : 0; // TODO: exclusive monitor modes

	int const dot = m_screen->hpos() / dot_scale();
	int const start = BIT(m_hreso, 0) ? 0x164 : 0x144;
	return dot >= start || dot < 4 ? 1 : 0;
}

int saturn_vdp2_device::get_vblank()
{
	int const cur_v = m_screen->vpos();
	int const first = get_vblank_start_position() * get_ystep_count();

	return cur_v >= first && cur_v < m_screen->height() - 1 ? 1 : 0;
}

int saturn_vdp2_device::get_vblank_start_position()
{
	// The vertical blank starts after the displayed lines: 224 in the 224 line mode (the 16 lines
	// below it are overscan the monitor may show, but they are blanking: MiSTer VDP2.sv and Ymir
	// agree), 240 in the 240 line mode. Batman Forever (ST-V) needs the long blank: it erases a
	// 352x224 window with the vertical blank erase and covers only the last rows with a polygon,
	// and that erase is limited by how long the vertical blank lasts (ST-013 4.4); with the blank
	// at line 240 it cleared about 100 rows and left video of an earlier scene in the others.
	// TODO: test says that second setting happens at 241, might need further investigation ...
	const int d_vres[4] = { 224, 240, 256, 256 };
	int vblank_line;

	const u8 vres_mask = (m_is_pal << 1) | 1;
	vblank_line = d_vres[m_vreso & vres_mask];

	return vblank_line;
}

int saturn_vdp2_device::get_ystep_count()
{
	int max_y = m_screen->height();
	int y_step;

	y_step = 2;

	// TODO: 263 & 313 needs to be static constexpr
	if((max_y == 263 && m_is_pal == 0) || (max_y == 313 && m_is_pal == 1))
		y_step = 1;

	return y_step;
}

// The line and frame events of the display. The horizontal ones follow the H counter of the
// chip: the HBLANK-IN signal rises at dot 0x143 of a 320 dot line and at 0x163 of a 352 dot line
// (one dot earlier in the hi-res modes) and drops at dot 2 of the next line (1 in hi-res); the
// TVSTAT HBLANK flag is set from dot 0x144 or 0x164 until dot 4. The signal comes on every line,
// the lines of the vertical blank interval too, because the SCU counts them. The vertical blank
// interval begins where it always did here and ends at the start of the last line of the
// frame, not at the first (MiSTer VDP2.sv: VBLANK-OUT is raised at the last dot of the line
// before the last one; Ymir's last line phase). The SCU documentation
// agrees: timer 0 is cleared by V-BLANK-OUT, and a compare value of 1 interrupts at the
// HBLANK-IN right before the first active line.
// Dots are counted in the units of the low resolution dot clock: hi-res pixels are two per dot.
int saturn_vdp2_device::dot_scale() const
{
	return BIT(m_hreso, 1) && !BIT(m_hreso, 2) ? 2 : 1;
}

int saturn_vdp2_device::hblank_in_dot() const
{
	if (BIT(m_hreso, 2))
		return m_hdisplay + 3; // TODO: exclusive monitor modes
	return ((BIT(m_hreso, 0) ? 0x163 : 0x143) - (BIT(m_hreso, 1) ? 1 : 0)) * dot_scale();
}

int saturn_vdp2_device::hblank_out_dot() const
{
	if (BIT(m_hreso, 2))
		return 2; // TODO: exclusive monitor modes
	return (BIT(m_hreso, 1) ? 1 : 2) * dot_scale();
}

void saturn_vdp2_device::schedule_hblank()
{
	// the signal is high from its dot to the early dots of the next line
	int const height = m_screen->height();
	int const vpos = m_screen->vpos();
	int const hpos = m_screen->hpos();
	int const in_x = hblank_in_dot();
	int const out_x = hblank_out_dot();
	bool const high = hpos >= in_x || hpos < out_x;
	m_hblank_rising = !high;
	if (!high)
		m_hblank_timer->adjust(m_screen->time_until_pos(vpos, in_x));
	else
		m_hblank_timer->adjust(m_screen->time_until_pos(hpos < out_x ? vpos : (vpos + 1) % height, out_x));
}

TIMER_CALLBACK_MEMBER(saturn_vdp2_device::hblank_timer_cb)
{
	int const height = m_screen->height();
	int const vpos = m_screen->vpos();
	int const in_x = hblank_in_dot();
	int const out_x = hblank_out_dot();

	m_hint_cb(m_hblank_rising ? 1 : 0);
	if (m_hblank_rising)
	{
		// the signal drops early on the next line
		m_hblank_rising = false;
		m_hblank_timer->adjust(m_screen->time_until_pos((vpos + 1) % height, out_x));
	}
	else
	{
		m_hblank_rising = true;
		m_hblank_timer->adjust(m_screen->time_until_pos(vpos, in_x));
	}
}

void saturn_vdp2_device::schedule_vblank()
{
	// the blank interval runs from its first line to the line before the last
	int const height = m_screen->height();
	int const vpos = m_screen->vpos();
	int const first = get_vblank_start_position() * get_ystep_count();
	int const last = height - 1;
	bool const inside = vpos >= first && vpos < last;
	m_vblank_next_in = !inside;
	m_vblank_timer->adjust(m_screen->time_until_pos(inside ? last : first, 0));
}

TIMER_CALLBACK_MEMBER(saturn_vdp2_device::vblank_timer_cb)
{
	if (m_vblank_next_in)
	{
		// flip odd bit here
		m_odd_bit ^= 1;
		m_vint_cb(1);
	}
	else
		m_vint_cb(0);

	m_vblank_next_in = !m_vblank_next_in;
	int const height = m_screen->height();
	int const first = get_vblank_start_position() * get_ystep_count();
	m_vblank_timer->adjust(m_screen->time_until_pos(m_vblank_next_in ? first : height - 1, 0));
}

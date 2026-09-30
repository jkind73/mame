// license:LGPL-2.1+
// copyright-holders:David Haywood, Angelo Salese, Olivier Galibert, Mariusz Wojcieszek, R. Belmont
// Contains VDP1 and VDP2 code. Use "Sega Saturn VDP2" marker for start of VDP2 code
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

TODO (VDP1):
- Decidedly too fast in drawing. Real HW has serious penalties in the pipeline;
- Off with CEF/BEF handling, several entries hangs;
- Correct FB erase/swap timings,
  i.e. stuff that erases too soon and expect the idle bit to stay in draw state
  cfr. kiwames (STV), blaztorn VS screen in PvP env;
- Given the above, SCU VDP1 end irq event should probably be corrected and
  internalized to fire at will. Pinpoint exactly when and the likely HW
  implications involved.
  also cfr. batmanfr (STV) gameplay, nightstr (draws in auto mode), others;
- Illegal sprite entries, most of them are actually off with timing?
  Needs serious tests on real HW about behaviour;
- Mixing with VDP2 (has priority per dot mode and other caveats)
  also cfr. basically any MD Sega Ages;
- Polygon vertices goes wrong place in some places,
  cfr. blaztorn match intro, twcup98 (STV) team select world cup,
  sandor (STV) match moai sub-game, other places;
- FB rotation framebuffer (shared with VDP2)
  cfr. capgen4 Yoko/Tate Modes;
- Zooming rounding errors in some places
  cfr. groovef VS Zoom-In animation, flag stripes in Sega soccer/baseball games;
- Some if not all wireframes sports stippled oblique polylines
  cfr. gnine96 stadium select;
- Off with transparent pixel flag in some places
  cfr. jeworaclj, vhydlid;
- Investigate bad colors in some places
  cfr. dariusg intro, 3dwarvesu after continue;
- Some places are known to effectively glitch out in special cases with wrong pitch set
  cfr. suikoenb (STV), fill others;
- 8 bpp support - now we always draw as 16 bpp, but this is not a problem since
  VDP2 interprets framebuffer as 8 bpp in these cases (ETA: verify this statement);

TODO (VDP2):
- Mixing with VDP1;
- Blending is incorrectly enabled on some places
  cfr. decathlt gameplay, dragndrm title screen, Data East logo in the Magical Drop games;
- Incomplete/buggy Color Calculation
  cfr. reversed fade in/out for dokyuif title transition,
  shienryu stage 2 background colors on statues (caused by special color calculation usage,
  per dot ...),
  scud zoom-in on melee attacks with pink backgrounds (TODO: reinvestigate this),
  dinoisl;
- Incomplete/buggy window effects
  cfr. gpanicss gal select, one of the Wangan games (TODO: find which),
  cknight2j bugged map transition;
- VRAM cycle pattern section needs to be better encapsulated and investigated thru real HW
  also cfr. several "minor GFX" glitches scattered across, kingbox on gameplay, columns Sega Ages
  logo;
- Missing mosaic effect
  cfr. Saturn BIOS memory screens, capgen2 Choh Makai Mura map transitions (obviously);
- Per-scanline raster effects, at very least Color Offset section is eligible to those
  cfr. elevact2, ogrebatl, probably htheros missing crowd;
- ODD and H/V Counters needs to be fine tuned with real HW tests.
  Also PAL modes are wrong and basically untested;
- Interlace Modes should be better emulated;
- Verify Exclusive Screen Modes a.k.a. "VGA";
- Missing "Reduction Enable", a.k.a. zooming limiters;
- A plethora of other miscellaneous missing effects here and there,
  cfr. most correlated notes near popmessage fns;
- Shadow code handling, checkout portions marked with code smell
  (double conditional over contradicting conditions!?)
  also cfr. mfpool & voiceido gameplay;
- Performance gets quite dire in some selected places, may be shared with VDP1,
  may be useful to investigate culprit
  cfr. decathlt gameplay, kingobox main menu, htheros intro;
- EXBG a.k.a. MPEG/Genlock layer source;
- gekkakis gameplay enables undocumented BGON bit 6 as an alias for text layer (currently hidden),
  investigate;
- Back layer isn't drawn in biohaz, investigate;
- Bogus Title Screen blinking for vhydlid and probably other T&E Soft games, investigate;
- Verify batmanfr crashing before final boss (assuming it's reproducible),
  prime suspect VDP2 overrunning a buffer on the complicated ROZ setup it does for Riddler screen;
- Verify hanagumi ending (there are sources sporting bad tiles, it's most likely fixed a long
  time ago);
- Verify rsgun Xiga final boss implications with rotation read controls
  (should still be wrong as per current);
- Verify sandor (STV) martial artist dry towel sub-game (overall screen setup looked
  wrong, saw from a thuntk playthrough with unknown MAME version used);


**************************************************************************************************/
/*

STV - VDP1

the vdp1 draws to the FRAMEBUFFER which is mapped in memory

-------------------------- WARNING WARNING WARNING --------------------------
This is a legacy core, all game based notes are for a future device rewrite.
Please don't remove them if for no reason you truly want to mess with this.
-------------------------- WARNING WARNING WARNING --------------------------

Framebuffer TODO:
- finish manual erase
- add proper framebuffer erase
- 8 bpp support - now we always draw as 16 bpp, but this is not a problem since
  VDP2 interprets framebuffer as 8 bpp in these cases

*/


#include "emu.h"
#include "saturn.h"

#include "cpu/scudsp/scudsp.h"

#include "input.h" // for video debug keys

#define LOG_VDP2 (1U << 1)
#define LOG_ROZ  (1U << 2)

#define DEBUG_MODE 0

#if DEBUG_MODE
#define VERBOSE (LOG_VDP2)
#else
#define VERBOSE (0)
#endif

#include "logmacro.h"


#define VDP1_LOG 0


namespace {

enum { FRAC_SHIFT = 16 };

struct shaded_point
{
	int32_t x,y;
	int32_t r,g,b;
};

constexpr uint16_t RGB_R(uint16_t color) { return color & 0x1f; }
constexpr uint16_t RGB_G(uint16_t color) { return (color >> 5) & 0x1f; }
constexpr uint16_t RGB_B(uint16_t color) { return (color >> 10) & 0x1f; }

} // anonymous namespace



void saturn_state::machine_reset()
{
	m_scsp_last_line = 0;

	// don't let the slave cpu and the 68k go anywhere
	m_slave->set_input_line(INPUT_LINE_RESET, ASSERT_LINE);
	m_audiocpu->set_input_line(INPUT_LINE_RESET, ASSERT_LINE);

	m_maincpu->set_unscaled_clock(MASTER_CLOCK_320/2);
	m_slave->set_unscaled_clock(MASTER_CLOCK_320/2);

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
}

// TODO: stuff that should really be in VDP1
TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline)
{
	int scanline = param;
	int y_step, vblank_line;

	vblank_line = m_vdp2->get_vblank_start_position();
	y_step = m_vdp2->get_ystep_count();

	//popmessage("%08x %d T0 %d T1 %d %08x",m_scu.ism ^ 0xffffffff,max_y,m_scu_regs[36],m_scu_regs[37],m_scu_regs[38]);

	if(scanline == vblank_line*y_step)
	{
		/* TODO: when Automatic Draw actually happens? Night Striker S is very fussy on this, and it looks like that VDP1 starts at more or less vblank-in time ... */
		vdp1_video_update();
	}

	if(scanline == (vblank_line + 1) * y_step)
	{
		/* docs mentions that VBE happens one line after vblank-in. */
		if(VDP1_VBE())
			m_vdp1_legacy.framebuffer_clear_on_next_frame = 1;
	}

	// TODO: temporary for Batman Forever, presumably anonymous timer not behaving well.
	//       VDP1 timing needs some HW work anyway so I'm currently firing VDP1 after 8 scanlines for now, will de-anon the timers in a later stage.
	if(scanline == (vblank_line+8) * y_step)
	{
		m_scu->vdp1_end_w(1);
	}

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
	memset(m_vdp1_vram.get(),0x00,0x100000);
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
	const XTAL &xtal = state ? MASTER_CLOCK_320 : MASTER_CLOCK_352;

	m_maincpu->set_unscaled_clock(xtal / 2);
	m_slave->set_unscaled_clock(xtal / 2);
	m_dcc->set_unscaled_clock(xtal / 2);

	m_scu->set_unscaled_clock(xtal);

//	m_vdp1->set_unscaled_clock(xtal);
	m_vdp2->set_unscaled_clock(xtal);
	m_vdp2->set_dotsel(!state);

	m_scsp->reset();
	m_scu->reset();
//  m_vdp1->reset();
	m_vdp2->reset();
}


/*TV Mode Selection Register */
/*
   xxxx xxxx xxxx ---- | UNUSED
   ---- ---- ---- x--- | VBlank Erase/Write (VBE)
   ---- ---- ---- -xxx | TV Mode (TVM)
   TV-Mode:
   This sets the Frame Buffer size,the rotation of the Frame Buffer & the bit width.
   bit 2 HDTV disable(0)/enable(1)
   bit 1 non-rotation/rotation(1)
   bit 0 16(0)/8(1) bits per pixel
   Size of the Frame Buffer:
   7 invalid
   6 invalid
   5 invalid
   4 512x256
   3 512x512
   2 512x256
   1 1024x256
   0 512x256
*/

/*Frame Buffer Change Mode Register*/
/*
   xxxx xxxx xxx- ---- | UNUSED
   ---- ---- ---x ---- | Even/Odd Coordinate Select Bit (EOS)
   ---- ---- ---- x--- | Double Interlace Mode (DIE)
   ---- ---- ---- -x-- | Double Interlace Draw Line (DIL)
   ---- ---- ---- --x- | Frame Buffer Change Trigger (FCM)
   ---- ---- ---- ---x | Frame Buffer Change Mode (FCT)
*/
#define VDP1_FBCR ((m_vdp1_regs[0x002/2] >> 0)&0xffff)
#define VDP1_EOS ((VDP1_FBCR & 0x0010) >> 4)
#define VDP1_DIE ((VDP1_FBCR & 0x0008) >> 3)
#define VDP1_DIL ((VDP1_FBCR & 0x0004) >> 2)
#define VDP1_FCM ((VDP1_FBCR & 0x0002) >> 1)
#define VDP1_FCT ((VDP1_FBCR & 0x0001) >> 0)

/*Plot Trigger Register*/
/*
   xxxx xxxx xxxx xx-- | UNUSED
   ---- ---- ---- --xx | Plot Trigger Mode (PTM)

   Plot Trigger Mode:
   3 Invalid
   2 Automatic draw
   1 VDP1 draw by request
   0 VDP1 Idle (no access)
*/
#define VDP1_PTMR ((m_vdp1_regs[0x004/2])&0xffff)
#define VDP1_PTM  ((VDP1_PTMR & 0x0003) >> 0)
#define PTM_0         m_vdp1_regs[0x004/2]&=~0x0001

/*
    Erase/Write Data Register
    16 bpp = data
    8 bpp = erase/write data for even/odd X coordinates
*/
#define VDP1_EWDR ((m_vdp1_regs[0x006/2])&0xffff)

/*Erase/Write Upper-Left register*/
/*
   x--- ---- ---- ---- | UNUSED
   -xxx xxx- ---- ---- | X1 register
   ---- ---x xxxx xxxx | Y1 register

*/
#define VDP1_EWLR ((m_vdp1_regs[0x008/2])&0xffff)
#define VDP1_EWLR_X1 ((VDP1_EWLR & 0x7e00) >> 9)
#define VDP1_EWLR_Y1 ((VDP1_EWLR & 0x01ff) >> 0)
/*Erase/Write Lower-Right register*/
/*
   xxxx xxx- ---- ---- | X3 register
   ---- ---x xxxx xxxx | Y3 register

*/
#define VDP1_EWRR ((m_vdp1_regs[0x00a/2])&0xffff)
#define VDP1_EWRR_X3 ((VDP1_EWRR & 0xfe00) >> 9)
#define VDP1_EWRR_Y3 ((VDP1_EWRR & 0x01ff) >> 0)
/*Transfer End Status Register*/
/*
   xxxx xxxx xxxx xx-- | UNUSED
   ---- ---- ---- --x- | CEF
   ---- ---- ---- ---x | BEF

*/
#define VDP1_EDSR ((m_vdp1_regs[0x010/2])&0xffff)
#define VDP1_CEF  (VDP1_EDSR & 2)
#define VDP1_BEF  (VDP1_EDSR & 1)
/**/



uint16_t saturn_state::vdp1_regs_r(offs_t offset)
{
	//logerror ("%s VDP1: Read from Registers, Offset %04x\n", machine().describe_context(), offset);

	switch(offset)
	{
		case 0x02/2:
			return 0;
		case 0x10/2:
			break;
		case 0x12/2: return m_vdp1_legacy.lopr;
		case 0x14/2: return m_vdp1_legacy.copr;
		/* MODR register, read register for the other VDP1 regs
		   (Shienryu SS version abuses of this during intro) */
		case 0x16/2:
			uint16_t modr;

			modr = 0x1000; //vdp1 VER
			modr |= (VDP1_PTM >> 1) << 8; // PTM1
			modr |= VDP1_EOS << 7; // EOS
			modr |= VDP1_DIE << 6; // DIE
			modr |= VDP1_DIL << 5; // DIL
			modr |= VDP1_FCM << 4; //FCM
			modr |= VDP1_VBE() << 3; //VBE
			modr |= VDP1_TVM() & 7; //TVM

			return modr;
		default:
			if(!machine().side_effects_disabled())
				logerror("%s VDP1: Read from Registers, Offset %04x\n", machine().describe_context(), offset*2);
			break;
	}

	return m_vdp1_regs[offset]; //TODO: write-only regs should return open bus or zero
}

/* TODO: TVM & 1 is just a kludgy work-around, the VDP1 actually needs to be rewritten from scratch. */
/* Daisenryaku Strong Style (daisenss) uses it */
void saturn_state::vdp1_clear_framebuffer( int which_framebuffer )
{
	int start_x, end_x, start_y, end_y;

	start_x = VDP1_EWLR_X1 * ((VDP1_TVM() & 1) ? 16 : 8);
	start_y = VDP1_EWLR_Y1 * (m_vdp1_legacy.framebuffer_double_interlace+1);
	end_x = VDP1_EWRR_X3 * ((VDP1_TVM() & 1) ? 16 : 8);
	end_y = (VDP1_EWRR_Y3+1) * (m_vdp1_legacy.framebuffer_double_interlace+1);
//  popmessage("%d %d %d %d %d",VDP1_EWLR_X1,VDP1_EWLR_Y1,VDP1_EWRR_X3,VDP1_EWRR_Y3,m_vdp1_legacy.framebuffer_double_interlace);

	if(VDP1_TVM() & 1)
	{
		for(int y=start_y;y<end_y;y++)
			for(int x=start_x;x<end_x;x++)
				m_vdp1_legacy.framebuffer[ which_framebuffer ][((x&1023)+(y&511)*1024)] = m_vdp1_legacy.ewdr;
	}
	else
	{
		for(int y=start_y;y<end_y;y++)
			for(int x=start_x;x<end_x;x++)
				m_vdp1_legacy.framebuffer[ which_framebuffer ][((x&511)+(y&511)*512)] = m_vdp1_legacy.ewdr;
	}

	if ( VDP1_LOG ) logerror( "Clearing %d framebuffer\n", m_vdp1_legacy.framebuffer_current_draw );
//  memset( m_vdp1_legacy.framebuffer[ which_framebuffer ], m_vdp1_legacy.ewdr, 1024 * 256 * sizeof(uint16_t) * 2 );
}


void saturn_state::vdp1_prepare_framebuffers()
{
	int i,rowsize;

	rowsize = m_vdp1_legacy.framebuffer_width;
	if ( m_vdp1_legacy.framebuffer_current_draw == 0 )
	{
		for ( i = 0; i < m_vdp1_legacy.framebuffer_height; i++ )
		{
			m_vdp1_legacy.framebuffer_draw_lines[i] = &m_vdp1_legacy.framebuffer[0][ i * rowsize ];
			m_vdp1_legacy.framebuffer_display_lines[i] = &m_vdp1_legacy.framebuffer[1][ i * rowsize ];
		}
		for ( ; i < 512; i++ )
		{
			m_vdp1_legacy.framebuffer_draw_lines[i] = &m_vdp1_legacy.framebuffer[0][0];
			m_vdp1_legacy.framebuffer_display_lines[i] = &m_vdp1_legacy.framebuffer[1][0];
		}
	}
	else
	{
		for ( i = 0; i < m_vdp1_legacy.framebuffer_height; i++ )
		{
			m_vdp1_legacy.framebuffer_draw_lines[i] = &m_vdp1_legacy.framebuffer[1][ i * rowsize ];
			m_vdp1_legacy.framebuffer_display_lines[i] = &m_vdp1_legacy.framebuffer[0][ i * rowsize ];
		}
		for ( ; i < 512; i++ )
		{
			m_vdp1_legacy.framebuffer_draw_lines[i] = &m_vdp1_legacy.framebuffer[1][0];
			m_vdp1_legacy.framebuffer_display_lines[i] = &m_vdp1_legacy.framebuffer[0][0];
		}

	}

	for ( ; i < 512; i++ )
	{
		m_vdp1_legacy.framebuffer_draw_lines[i] = &m_vdp1_legacy.framebuffer[0][0];
		m_vdp1_legacy.framebuffer_display_lines[i] = &m_vdp1_legacy.framebuffer[1][0];
	}

}

void saturn_state::vdp1_change_framebuffers()
{
	m_vdp1_legacy.framebuffer_current_display ^= 1;
	m_vdp1_legacy.framebuffer_current_draw ^= 1;
	// "this bit is reset to 0 when the frame buffers are changed"
	CEF_0();
	if ( VDP1_LOG ) logerror( "Changing framebuffers: %d - draw, %d - display\n", m_vdp1_legacy.framebuffer_current_draw, m_vdp1_legacy.framebuffer_current_display );
	vdp1_prepare_framebuffers();
}

void saturn_state::vdp1_set_framebuffer_config()
{
	if ( m_vdp1_legacy.framebuffer_mode == VDP1_TVM() &&
			m_vdp1_legacy.framebuffer_double_interlace == VDP1_DIE ) return;

	if ( VDP1_LOG ) logerror( "Setting framebuffer config\n" );
	m_vdp1_legacy.framebuffer_mode = VDP1_TVM();
	m_vdp1_legacy.framebuffer_double_interlace = VDP1_DIE;
	switch( m_vdp1_legacy.framebuffer_mode )
	{
		case 0: m_vdp1_legacy.framebuffer_width = 512; m_vdp1_legacy.framebuffer_height = 256; break;
		case 1: m_vdp1_legacy.framebuffer_width = 1024; m_vdp1_legacy.framebuffer_height = 256; break;
		case 2: m_vdp1_legacy.framebuffer_width = 512; m_vdp1_legacy.framebuffer_height = 256; break;
		case 3: m_vdp1_legacy.framebuffer_width = 512; m_vdp1_legacy.framebuffer_height = 512; break;
		case 4: m_vdp1_legacy.framebuffer_width = 512; m_vdp1_legacy.framebuffer_height = 256; break;
		default: logerror( "Invalid framebuffer config %x\n", VDP1_TVM() ); m_vdp1_legacy.framebuffer_width = 512; m_vdp1_legacy.framebuffer_height = 256; break;
	}
	if ( VDP1_DIE ) m_vdp1_legacy.framebuffer_height *= 2; /* double interlace */

	m_vdp1_legacy.framebuffer_current_draw = 0;
	m_vdp1_legacy.framebuffer_current_display = 1;
	vdp1_prepare_framebuffers();
}

void saturn_state::vdp1_regs_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	// PTM = 01 starts drawing immediately, while 00/10 only change the plot trigger mode at the
	// next frame buffer change, so a 01 write leaves the mode from the last 00/10 write in effect.
	// - doom and exhumed set 10 then draw with 01, and hang unless the next change draws again (CEF)
	if (offset == 0x04/2 && ACCESSING_BITS_0_7 && (data & 3) == 1)
	{
		if ( VDP1_LOG ) logerror( "VDP1: Access to register PTMR = %1X\n", data );
		vdp1_process_list();
		return;
	}

	COMBINE_DATA(&m_vdp1_regs[offset]);

	switch(offset)
	{
		case 0x00/2:
			vdp1_set_framebuffer_config();
			if ( VDP1_LOG ) logerror( "VDP1: Access to register TVMR = %1X\n", data );

			break;
		case 0x02/2:
			vdp1_set_framebuffer_config();
			if ( VDP1_LOG ) logerror( "VDP1: Access to register FBCR = %1X\n", data );
			m_vdp1_legacy.fbcr_accessed = 1;
			break;
		case 0x04/2:
			if ( VDP1_LOG ) logerror( "VDP1: Access to register PTMR = %1X\n", data );
			break;
		case 0x06/2:
			if ( VDP1_LOG ) logerror( "VDP1: Erase data set %08X\n", data );

			m_vdp1_legacy.ewdr = VDP1_EWDR;
			break;
		case 0x08/2:
			if ( VDP1_LOG ) logerror( "VDP1: Erase upper-left coord set: %08X\n", data );
			break;
		case 0x0a/2:
			if ( VDP1_LOG ) logerror( "VDP1: Erase lower-right coord set: %08X\n", data );
			break;
		case 0x0c/2:
		case 0x0e/2: // After Burner 2 / Out Run / Fantasy Zone writes here with a dword ...
			if ( VDP1_LOG ) logerror( "VDP1: Draw forced termination register write: %08X %08X\n", offset*2, data );
			break;
		default:
			logerror("Warning: write to unknown VDP1 reg %08x %08x\n",offset*2,data);
			break;
	}

}

uint32_t saturn_state::vdp1_vram_r(offs_t offset)
{
	return m_vdp1_vram[offset];
}


void saturn_state::vdp1_vram_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	uint8_t *vdp1 = m_vdp1_legacy.gfx_decode.get();

	COMBINE_DATA (&m_vdp1_vram[offset]);

//  if (((offset * 4) > 0xdf) && ((offset * 4) < 0x140))
//  {
//      logerror("%s: VRAM dword write to %08X = %08X & %08X\n", machine().describe_context(), offset*4, data, mem_mask);
//  }

	data = m_vdp1_vram[offset];
	/* put in gfx region for easy decoding */
	vdp1[offset*4+0] = (data & 0xff000000) >> 24;
	vdp1[offset*4+1] = (data & 0x00ff0000) >> 16;
	vdp1[offset*4+2] = (data & 0x0000ff00) >> 8;
	vdp1[offset*4+3] = (data & 0x000000ff) >> 0;
}

void saturn_state::vdp1_framebuffer0_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	//popmessage ("STV VDP1 Framebuffer 0 WRITE offset %08x data %08x",offset, data);
	if ( VDP1_TVM() & 1 )
	{
		/* 8-bit mode */
		//printf("VDP1 8-bit mode %08x %02x\n",offset,data);
		if ( ACCESSING_BITS_24_31 )
		{
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] &= 0x00ff;
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] |= data & 0xff00;
		}
		if ( ACCESSING_BITS_16_23 )
		{
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] &= 0xff00;
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] |= data & 0x00ff;
		}
		if ( ACCESSING_BITS_8_15 )
		{
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] &= 0x00ff;
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] |= data & 0xff00;
		}
		if ( ACCESSING_BITS_0_7 )
		{
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] &= 0xff00;
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] |= data & 0x00ff;
		}
	}
	else
	{
		/* 16-bit mode */
		if ( ACCESSING_BITS_16_31 )
		{
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] = (data >> 16) & 0xffff;
		}
		if ( ACCESSING_BITS_0_15 )
		{
			m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] = data & 0xffff;
		}
	}
}

uint32_t saturn_state::vdp1_framebuffer0_r(offs_t offset, uint32_t mem_mask)
{
	uint32_t result = 0;
	//popmessage ("STV VDP1 Framebuffer 0 READ offset %08x",offset);
	if ( VDP1_TVM() & 1 )
	{
		/* 8-bit mode */
		//printf("VDP1 8-bit mode %08x\n",offset);
		if ( ACCESSING_BITS_24_31 )
			result |= ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] & 0xff00) << 16);
		if ( ACCESSING_BITS_16_23 )
			result |= ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] & 0x00ff) << 16);
		if ( ACCESSING_BITS_8_15 )
			result |= ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] & 0xff00));
		if ( ACCESSING_BITS_0_7 )
			result |= ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1] & 0x00ff));
	}
	else
	{
		/* 16-bit mode */
		if ( ACCESSING_BITS_16_31 )
		{
			result |= (m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2] << 16);
		}
		if ( ACCESSING_BITS_0_15 )
		{
			result |= (m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset*2+1]);
		}

	}

	return result;
}


/*

there is a command every 0x20 bytes
the first word is the control word
the rest are data used by it

---
00 CMDCTRL
   e--- ---- ---- ---- | end bit (15)
   -jjj ---- ---- ---- | jump select bits (12-14)
   ---- zzzz ---- ---- | zoom point / hotspot (8-11)
   ---- ---- 00-- ---- | UNUSED
   ---- ---- --dd ---- | character read direction (4,5)
   ---- ---- ---- cccc | command bits (0-3)

02 CMDLINK
   llll llll llll ll-- | link
   ---- ---- ---- --00 | UNUSED

04 CMDPMOD
   m--- ---- ---- ---- | MON (looks at MSB and apply shadows etc.)
   -00- ---- ---- ---- | UNUSED
   ---h ---- ---- ---- | HSS (High Speed Shrink)
   ---- p--- ---- ---- | PCLIP (Pre Clipping Disable)
   ---- -c-- ---- ---- | CLIP (Clipping Mode Bit)
   ---- --m- ---- ---- | CMOD (User Clipping Enable Bit)
   ---- ---M ---- ---- | MESH (Mesh Enable Bit)
   ---- ---- e--- ---- | ECD (End Code Disable)
   ---- ---- -S-- ---- | SPD (Transparent Pixel Disable)
   ---- ---- --cc c--- | Colour Mode
   ---- ---- ---- -CCC | Colour Calculation bits
   ---- ---- ---- -1-- | Gouraud shading enable
   ---- ---- ---- --1- | 1/2 original GFX enable
   ---- ---- ---- ---1 | 1/2 background enable

06 CMDCOLR
   mmmm mmmm mmmm mmmm | Colour Bank, Colour Lookup /8

08 CMDSRCA (Character Address)
   aaaa aaaa aaaa aa-- | Character Address
   ---- ---- ---- --00 | UNUSED

0a CMDSIZE (Character Size)
   00-- ---- ---- ---- | UNUSED
   --xx xxxx ---- ---- | Character Size (X)
   ---- ---- yyyy yyyy | Character Size (Y)

0c CMDXA (used for normal sprite)
   eeee ee-- ---- ---- | extension bits
   ---- --xx xxxx xxxx | x position

0e CMDYA (used for normal sprite)
   eeee ee-- ---- ---- | extension bits
   ---- --yy yyyy yyyy | y position

10 CMDXB
12 CMDYB
14 CMDXC
16 CMDYC
18 CMDXD
1a CMDYD
1c CMDGRDA (Gouraud Shading Table)
1e UNUSED
---


*/

void saturn_state::clear_gouraud_shading()
{
	gouraud_shading = decltype(gouraud_shading)();
}

uint8_t saturn_state::read_gouraud_table()
{
	int gaddr;

	if ( current_sprite.CMDPMOD & 0x4 )
	{
		gaddr = current_sprite.CMDGRDA * 8;
		gouraud_shading.GA = (m_vdp1_vram[gaddr/4] >> 16) & 0xffff;
		gouraud_shading.GB = (m_vdp1_vram[gaddr/4] >> 0) & 0xffff;
		gouraud_shading.GC = (m_vdp1_vram[gaddr/4 + 1] >> 16) & 0xffff;
		gouraud_shading.GD = (m_vdp1_vram[gaddr/4 + 1] >> 0) & 0xffff;
		return 1;
	}
	else
	{
		return 0;
	}
}

static inline int32_t _shading( int32_t color, int32_t correction )
{
	correction = (correction >> 16) & 0x1f;
	color += (correction - 16);

	if ( color < 0 ) color = 0;
	if ( color > 0x1f ) color = 0x1f;

	return color;
}

uint16_t saturn_state::vdp1_apply_gouraud_shading( int x, int y, uint16_t pix )
{
	int32_t r,g,b, msb;

	msb = pix & 0x8000;

#ifdef MAME_DEBUG
	if ( (vdp1_shading_data->scanline[y].x[0] >> 16) != x )
	{
		logerror( "ERROR in computing x coordinates (line %d, x = %x, %d, xc = %x, %d)\n", y, x, x, vdp1_shading_data->scanline[y].x[0], vdp1_shading_data->scanline[y].x[0] >> 16 );
	};
#endif

	b = RGB_B(pix);
	g = RGB_G(pix);
	r = RGB_R(pix);

	b = _shading( b, vdp1_shading_data->scanline[y].b[0] );
	g = _shading( g, vdp1_shading_data->scanline[y].g[0] );
	r = _shading( r, vdp1_shading_data->scanline[y].r[0] );

	vdp1_shading_data->scanline[y].b[0] += vdp1_shading_data->scanline[y].db;
	vdp1_shading_data->scanline[y].g[0] += vdp1_shading_data->scanline[y].dg;
	vdp1_shading_data->scanline[y].r[0] += vdp1_shading_data->scanline[y].dr;

	vdp1_shading_data->scanline[y].x[0] += 1 << FRAC_SHIFT;

	return msb | b << 10 | g << 5 | r;
}

void saturn_state::vdp1_setup_shading_for_line(
		int32_t y, int32_t x1, int32_t x2,
		int32_t r1, int32_t g1, int32_t b1,
		int32_t r2, int32_t g2, int32_t b2)
{
	int xx1 = x1>>FRAC_SHIFT;
	int xx2 = x2>>FRAC_SHIFT;


	if ( xx1 > xx2 )
	{
		using std::swap;
		swap(xx1, xx2);
		swap(r1, r2);
		swap(g1, g2);
		swap(b1, b2);
	}

	if ( (y >= 0) && (y < 512) )
	{
		int32_t  dx;
		int32_t   gbd, ggd, grd;

		dx = xx2 - xx1;

		if ( dx == 0 )
		{
			gbd = ggd = grd = 0;
		}
		else
		{
			gbd = abs(b2 - b1) / dx;
			if (b2 < b1) gbd = -gbd;
			ggd = abs(g2 - g1) / dx;
			if (g2 < g1) ggd = -ggd;
			grd = abs(r2 - r1) / dx;
			if (r2 < r1) grd = -grd;
		}

		vdp1_shading_data->scanline[y].x[0] = x1;
		vdp1_shading_data->scanline[y].x[1] = x2;

		vdp1_shading_data->scanline[y].b[0] = b1;
		vdp1_shading_data->scanline[y].g[0] = g1;
		vdp1_shading_data->scanline[y].r[0] = r1;
		vdp1_shading_data->scanline[y].b[1] = b2;
		vdp1_shading_data->scanline[y].g[1] = g2;
		vdp1_shading_data->scanline[y].r[1] = r2;

		vdp1_shading_data->scanline[y].db = gbd;
		vdp1_shading_data->scanline[y].dg = ggd;
		vdp1_shading_data->scanline[y].dr = grd;

	}
}

void saturn_state::vdp1_setup_shading_for_slope(
		int32_t x1, int32_t x2, int32_t sl1, int32_t sl2, int32_t *nx1, int32_t *nx2,
		int32_t r1, int32_t r2, int32_t slr1, int32_t slr2, int32_t *nr1, int32_t *nr2,
		int32_t g1, int32_t g2, int32_t slg1, int32_t slg2, int32_t *ng1, int32_t *ng2,
		int32_t b1, int32_t b2, int32_t slb1, int32_t slb2, int32_t *nb1, int32_t *nb2,
		int32_t _y1, int32_t y2)
{
	if(x1 > x2 || (x1==x2 && sl1 > sl2)) {
		using std::swap;
		swap(x1,x2);
		swap(sl1,sl2);
		swap(nx1, nx2);
		swap(r1,r2);
		swap(slr1, slr2);
		swap(nr1, nr2);
		swap(g1, g2);
		swap(slg1, slg2);
		swap(ng1, ng2);
		swap(b1, b2);
		swap(slb1, slb2);
		swap(nb1, nb2);
	}

	while(_y1 < y2)
	{
		vdp1_setup_shading_for_line(_y1, x1, x2, r1, g1, b1, r2, g2, b2);
		x1 += sl1;
		r1 += slr1;
		g1 += slg1;
		b1 += slb1;

		x2 += sl2;
		r2 += slr2;
		g2 += slg2;
		b2 += slb2;
		_y1++;
	}
	*nx1 = x1;
	*nr1 = r1;
	*ng1 = g1;
	*nb1 = b1;

	*nx2 = x2;
	*nr2 = r2;
	*nb2 = b2;
	*ng2 = g2;
}

void saturn_state::vdp1_setup_shading(const struct spoint* q, const rectangle &cliprect)
{
	int32_t x1, x2, delta, cury, limy;
	int32_t r1, g1, b1, r2, g2, b2;
	int32_t sl1, slg1, slb1, slr1;
	int32_t sl2, slg2, slb2, slr2;
	int pmin, pmax, i, ps1, ps2;
	struct shaded_point p[8];
	uint16_t gd[4];

	if ( read_gouraud_table() == 0 ) return;

	gd[0] = gouraud_shading.GA;
	gd[1] = gouraud_shading.GB;
	gd[2] = gouraud_shading.GC;
	gd[3] = gouraud_shading.GD;

	for(i=0; i<4; i++) {
		p[i].x = p[i+4].x = q[i].x << FRAC_SHIFT;
		p[i].y = p[i+4].y = q[i].y;
		p[i].r = p[i+4].r = RGB_R(gd[i]) << FRAC_SHIFT;
		p[i].g = p[i+4].g = RGB_G(gd[i]) << FRAC_SHIFT;
		p[i].b = p[i+4].b = RGB_B(gd[i]) << FRAC_SHIFT;
	}

	pmin = pmax = 0;
	for(i=1; i<4; i++) {
		if(p[i].y < p[pmin].y)
			pmin = i;
		if(p[i].y > p[pmax].y)
			pmax = i;
	}

	cury = p[pmin].y;
	limy = p[pmax].y;

	vdp1_shading_data->sy = cury;
	vdp1_shading_data->ey = limy;

	if(cury == limy) {
		x1 = x2 = p[0].x;
		ps1 = ps2 = 0;
		for(i=1; i<4; i++) {
			if(p[i].x < x1) {
				x1 = p[i].x;
				ps1 = i;
			}
			if(p[i].x > x2) {
				x2 = p[i].x;
				ps2 = i;
			}
		}
		vdp1_setup_shading_for_line(cury, x1, x2, p[ps1].r, p[ps1].g, p[ps1].b, p[ps2].r, p[ps2].g, p[ps2].b);
		goto finish;
	}

	ps1 = pmin+4;
	ps2 = pmin;

	goto startup;

	for(;;) {
		if(p[ps1-1].y == p[ps2+1].y) {
			vdp1_setup_shading_for_slope(
							x1, x2, sl1, sl2, &x1, &x2,
							r1, r2, slr1, slr2, &r1, &r2,
							g1, g2, slg1, slg2, &g1, &g2,
							b1, b2, slb1, slb2, &b1, &b2,
							cury, p[ps1-1].y);
			cury = p[ps1-1].y;
			if(cury >= limy)
				break;
			ps1--;
			ps2++;

		startup:
			while(p[ps1-1].y == cury)
				ps1--;
			while(p[ps2+1].y == cury)
				ps2++;
			x1 = p[ps1].x;
			r1 = p[ps1].r;
			g1 = p[ps1].g;
			b1 = p[ps1].b;
			x2 = p[ps2].x;
			r2 = p[ps2].r;
			g2 = p[ps2].g;
			b2 = p[ps2].b;

			delta = cury-p[ps1-1].y;
			sl1 = (x1-p[ps1-1].x)/delta;
			slr1 = (r1-p[ps1-1].r)/delta;
			slg1 = (g1-p[ps1-1].g)/delta;
			slb1 = (b1-p[ps1-1].b)/delta;

			delta = cury-p[ps2+1].y;
			sl2 = (x2-p[ps2+1].x)/delta;
			slr2 = (r2-p[ps2+1].r)/delta;
			slg2 = (g2-p[ps2+1].g)/delta;
			slb2 = (b2-p[ps2+1].b)/delta;
		} else if(p[ps1-1].y < p[ps2+1].y) {
			vdp1_setup_shading_for_slope(
							x1, x2, sl1, sl2, &x1, &x2,
							r1, r2, slr1, slr2, &r1, &r2,
							g1, g2, slg1, slg2, &g1, &g2,
							b1, b2, slb1, slb2, &b1, &b2,
							cury, p[ps1-1].y);
			cury = p[ps1-1].y;
			if(cury >= limy)
				break;
			ps1--;
			while(p[ps1-1].y == cury)
				ps1--;
			x1 = p[ps1].x;
			r1 = p[ps1].r;
			g1 = p[ps1].g;
			b1 = p[ps1].b;

			delta = cury-p[ps1-1].y;
			sl1 = (x1-p[ps1-1].x)/delta;
			slr1 = (r1-p[ps1-1].r)/delta;
			slg1 = (g1-p[ps1-1].g)/delta;
			slb1 = (b1-p[ps1-1].b)/delta;
		} else {
			vdp1_setup_shading_for_slope(
							x1, x2, sl1, sl2, &x1, &x2,
							r1, r2, slr1, slr2, &r1, &r2,
							g1, g2, slg1, slg2, &g1, &g2,
							b1, b2, slb1, slb2, &b1, &b2,
							cury, p[ps2+1].y);
			cury = p[ps2+1].y;
			if(cury >= limy)
				break;
			ps2++;
			while(p[ps2+1].y == cury)
				ps2++;
			x2 = p[ps2].x;
			r2 = p[ps2].r;
			g2 = p[ps2].g;
			b2 = p[ps2].b;

			delta = cury-p[ps2+1].y;
			sl2 = (x2-p[ps2+1].x)/delta;
			slr2 = (r2-p[ps2+1].r)/delta;
			slg2 = (g2-p[ps2+1].g)/delta;
			slb2 = (b2-p[ps2+1].b)/delta;
		}
	}
	if(cury == limy)
		vdp1_setup_shading_for_line(cury, x1, x2, r1, g1, b1, r2, g2, b2 );

finish:

	if ( vdp1_shading_data->sy < 0 ) vdp1_shading_data->sy = 0;
	if ( vdp1_shading_data->sy >= 512 ) return;
	if ( vdp1_shading_data->ey < 0 ) return;
	if ( vdp1_shading_data->ey >= 512 ) vdp1_shading_data->ey = 511;

	for ( cury = vdp1_shading_data->sy; cury <= vdp1_shading_data->ey; cury++ )
	{
		while( (vdp1_shading_data->scanline[cury].x[0] >> 16) < cliprect.min_x )
		{
			vdp1_shading_data->scanline[cury].x[0] += (1 << FRAC_SHIFT);
			vdp1_shading_data->scanline[cury].b[0] += vdp1_shading_data->scanline[cury].db;
			vdp1_shading_data->scanline[cury].g[0] += vdp1_shading_data->scanline[cury].dg;
			vdp1_shading_data->scanline[cury].r[0] += vdp1_shading_data->scanline[cury].dr;
		}
	}

}

/* note that if we're drawing
to the framebuffer we CAN'T frameskip the vdp1 drawing as the hardware can READ the framebuffer
and if we skip the drawing the content could be incorrect when it reads it, although i have no idea
why they would want to */



void saturn_state::drawpixel_poly(int x, int y, int patterndata, int offsetcnt)
{
	/* Capcom Collection Dai 4 uses a dummy polygon to clear VDP1 framebuffer that goes over our current max size ... */
	if(x >= 1024 || y >= 512)
		return;

	m_vdp1_legacy.framebuffer_draw_lines[y][x] = current_sprite.CMDCOLR;
}

void saturn_state::drawpixel_8bpp_trans(int x, int y, int patterndata, int offsetcnt)
{
	uint16_t pix;

	pix = m_vdp1_legacy.gfx_decode[patterndata+offsetcnt] & 0xff;
	if ( pix != 0 )
	{
		m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix | m_sprite_colorbank;
	}
}

void saturn_state::drawpixel_4bpp_notrans(int x, int y, int patterndata, int offsetcnt)
{
	uint16_t pix;

	pix = m_vdp1_legacy.gfx_decode[patterndata+offsetcnt/2];
	pix = offsetcnt&1 ? (pix & 0x0f) : ((pix & 0xf0)>>4);
	m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix | m_sprite_colorbank;
}

void saturn_state::drawpixel_4bpp_trans(int x, int y, int patterndata, int offsetcnt)
{
	uint16_t pix;

	pix = m_vdp1_legacy.gfx_decode[patterndata+offsetcnt/2];
	pix = offsetcnt&1 ? (pix & 0x0f) : ((pix & 0xf0)>>4);
	if ( pix != 0 )
		m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix | m_sprite_colorbank;
}

void saturn_state::drawpixel_generic(int x, int y, int patterndata, int offsetcnt)
{
	int pix,transpen, spd = current_sprite.CMDPMOD & 0x40;
//  int mode;
	int mesh = current_sprite.CMDPMOD & 0x100;
	int raw,endcode;

	if ( mesh && !((x ^ y) & 1) )
	{
		return;
	}

	if(x >= 1024 || y >= 512)
		return;

	if ( current_sprite.ispoly )
	{
		raw = pix = current_sprite.CMDCOLR&0xffff;

		transpen = 0;
		endcode = 0xffff;
		#if 0
		if ( pix & 0x8000 )
		{
			mode = 5;
		}
		else
		{
			mode = 1;
		}
		#endif
	}
	else
	{
		switch (current_sprite.CMDPMOD&0x0038)
		{
			case 0x0000: // mode 0 16 colour bank mode (4bits) (hanagumi blocks)
				// most of the shienryu sprites use this mode
				raw = m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt/2) & 0xfffff];
				raw = offsetcnt&1 ? (raw & 0x0f) : ((raw & 0xf0)>>4);
				pix = raw+((current_sprite.CMDCOLR&0xfff0));
				//mode = 0;
				transpen = 0;
				endcode = 0xf;
				break;
			case 0x0008: // mode 1 16 colour lookup table mode (4bits)
				// shienryu explosions (and some enemies) use this mode
				raw = m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt/2) & 0xfffff];
				raw = offsetcnt&1 ? (raw & 0x0f) : ((raw & 0xf0)>>4);
				pix = raw&1 ?
				((((m_vdp1_vram[(((current_sprite.CMDCOLR&0xffff)*8)>>2)+((raw&0xfffe)/2)])) & 0x0000ffff) >> 0):
				((((m_vdp1_vram[(((current_sprite.CMDCOLR&0xffff)*8)>>2)+((raw&0xfffe)/2)])) & 0xffff0000) >> 16);
				//mode = 5;
				transpen = 0;
				endcode = 0xf;
				break;
			case 0x0010: // mode 2 64 colour bank mode (8bits) (character select portraits on hanagumi)
				raw = m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt) & 0xfffff] & 0xff;
				//mode = 2;
				pix = raw+(current_sprite.CMDCOLR&0xffc0);
				transpen = 0;
				endcode = 0xff;
				// Notes of interest:
				// Scud: the disposable assassin wants transparent pen on 0
				// sasissu: racing stage background clouds
				break;
			case 0x0018: // mode 3 128 colour bank mode (8bits) (little characters on hanagumi use this mode)
				raw = m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt) & 0xfffff] & 0xff;
				pix = raw+(current_sprite.CMDCOLR&0xff80);
				transpen = 0;
				endcode = 0xff;
				//mode = 3;
				break;
			case 0x0020: // mode 4 256 colour bank mode (8bits) (hanagumi title)
				raw = m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt) & 0xfffff] & 0xff;
				pix = raw+(current_sprite.CMDCOLR&0xff00);
				transpen = 0;
				endcode = 0xff;
				//mode = 4;
				break;
			case 0x0028: // mode 5 32,768 colour RGB mode (16bits)
				raw = m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt*2+1) & 0xfffff] | (m_vdp1_legacy.gfx_decode[(patterndata+offsetcnt*2) & 0xfffff]<<8);
				//mode = 5;
				// TODO: 0x1-0x7ffe reserved (color bank)
				pix = raw;
				transpen = 0;
				endcode = 0x7fff;
				break;
			case 0x0038: // invalid
				// game tengoku uses this on hi score screen (tate mode)
				// according to Charles, reads from VRAM address 0
				raw = pix = m_vdp1_legacy.gfx_decode[1] | (m_vdp1_legacy.gfx_decode[0]<<8) ;
				// TODO: check transpen
				transpen = 0;
				endcode = -1;
				break;
			default: // other settings illegal
				pix = machine().rand();
				raw = pix & 0xff; // just mimic old driver behavior
				//mode = 0;
				transpen = 0;
				endcode = 0xff;
				popmessage("Illegal Sprite Mode %02x",current_sprite.CMDPMOD&0x0038);
		}


		// preliminary end code disable support
		if ( ((current_sprite.CMDPMOD & 0x80) == 0) &&
			(raw == endcode) )
		{
			return;
		}
	}

	/* MSBON */
	// TODO: does this always applies to the frame buffer regardless of the mode?
	pix |= current_sprite.CMDPMOD & 0x8000;
	/*
	TODO: from docs:
	"Except for the color calculation of replace and shadow, color calculation can only be performed when the color code of the original picture is RGB code.
	Color calculation can be executed when the color code is color bank code, but the results are not guaranteed."
	Currently no idea about the "result not guaranteed" part, let's disable this branch for the time being ...
	*/
	#if 0
	if ( mode != 5 )
	{
		if ( (raw != transpen) || spd )
		{
			m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix;
		}
	}
	else
	#endif
	{
		if ( (raw != transpen) || spd )
		{
			if ( current_sprite.CMDPMOD & 0x4 ) /* Gouraud shading */
				pix = vdp1_apply_gouraud_shading( x, y, pix );

			switch( current_sprite.CMDPMOD & 0x3 )
			{
				case 0: /* replace */
					m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix;
					break;
				case 1: /* shadow */
					if ( m_vdp1_legacy.framebuffer_draw_lines[y][x] & 0x8000 )
					{
						m_vdp1_legacy.framebuffer_draw_lines[y][x] = ((m_vdp1_legacy.framebuffer_draw_lines[y][x] & ~0x8421) >> 1) | 0x8000;
					}
					break;
				case 2: /* half luminance */
					m_vdp1_legacy.framebuffer_draw_lines[y][x] = ((pix & ~0x8421) >> 1) | 0x8000;
					break;
				case 3: /* half transparent */
					if ( m_vdp1_legacy.framebuffer_draw_lines[y][x] & 0x8000 )
					{
						m_vdp1_legacy.framebuffer_draw_lines[y][x] = alpha_blend_r16( m_vdp1_legacy.framebuffer_draw_lines[y][x], pix, 0x80 ) | 0x8000;
					}
					else
					{
						m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix;
					}
					break;
				//case 4: /* Gouraud shading */
				// TODO: proyakts (during team creation, on PR girl select)
				//case 6:
				//  break;
				//case 7: /* Gouraud-shading + half-transparent */
					// lupinpy enemy shadows
					// deathcri lives indicators
					// TODO: latter looks really bad.
				default:
					// TODO: mode 5: prohibited, mode 6: gouraud shading + half-luminance, mode 7: gouraud-shading + half-transparent
					popmessage("VDP1 PMOD = %02x",current_sprite.CMDPMOD & 0x7);
					m_vdp1_legacy.framebuffer_draw_lines[y][x] = pix;
					break;
			}
		}
	}
}


void saturn_state::vdp1_set_drawpixel()
{
	int sprite_type = current_sprite.CMDCTRL & 0x000f;
	int sprite_mode = current_sprite.CMDPMOD&0x0038;
	int spd = current_sprite.CMDPMOD & 0x40;
	int mesh = current_sprite.CMDPMOD & 0x100;
	int ecd = current_sprite.CMDPMOD & 0x80;

	if ( mesh || !ecd || ((current_sprite.CMDPMOD & 0x7) != 0) )
	{
		drawpixel = &saturn_state::drawpixel_generic;
		return;
	}

	if(current_sprite.CMDPMOD & 0x8000)
	{
		drawpixel = &saturn_state::drawpixel_generic;
		return;
	}

	// polygon / polyline / line with replace case
	if (sprite_type & 4 && ((current_sprite.CMDPMOD & 0x7) == 0))
	{
		drawpixel = &saturn_state::drawpixel_poly;
	}
	else if ( (sprite_mode == 0x20) && !spd )
	{
		m_sprite_colorbank = (current_sprite.CMDCOLR&0xff00);
		drawpixel = &saturn_state::drawpixel_8bpp_trans;
	}
	else if ((sprite_mode == 0x00) && spd)
	{
		m_sprite_colorbank = (current_sprite.CMDCOLR&0xfff0);
		drawpixel = &saturn_state::drawpixel_4bpp_notrans;
	}
	else if (sprite_mode == 0x00 && !spd )
	{
		m_sprite_colorbank = (current_sprite.CMDCOLR&0xfff0);
		drawpixel = &saturn_state::drawpixel_4bpp_trans;
	}
	else
	{
		drawpixel = &saturn_state::drawpixel_generic;
	}
}


void saturn_state::vdp1_fill_slope(const rectangle &cliprect, int patterndata, int xsize,
							int32_t x1, int32_t x2, int32_t sl1, int32_t sl2, int32_t *nx1, int32_t *nx2,
							int32_t u1, int32_t u2, int32_t slu1, int32_t slu2, int32_t *nu1, int32_t *nu2,
							int32_t v1, int32_t v2, int32_t slv1, int32_t slv2, int32_t *nv1, int32_t *nv2,
							int32_t _y1, int32_t y2)
{
	if(_y1 > cliprect.max_y)
		return;

	if(y2 <= cliprect.min_y) {
		int delta = y2-_y1;
		*nx1 = x1+delta*sl1;
		*nu1 = u1+delta*slu1;
		*nv1 = v1+delta*slv1;
		*nx2 = x2+delta*sl2;
		*nu2 = u2+delta*slu2;
		*nv2 = v2+delta*slv2;
		return;
	}

	if(y2 > cliprect.max_y)
		y2 = cliprect.max_y+1;

	if(_y1 < cliprect.min_y) {
		int delta = cliprect.min_y - _y1;
		x1 += delta*sl1;
		u1 += delta*slu1;
		v1 += delta*slv1;
		x2 += delta*sl2;
		u2 += delta*slu2;
		v2 += delta*slv2;
		_y1 = cliprect.min_y;
	}

	if(x1 > x2 || (x1==x2 && sl1 > sl2)) {
		int32_t t, *tp;
		t = x1;
		x1 = x2;
		x2 = t;
		t = sl1;
		sl1 = sl2;
		sl2 = t;
		tp = nx1;
		nx1 = nx2;
		nx2 = tp;

		t = u1;
		u1 = u2;
		u2 = t;
		t = slu1;
		slu1 = slu2;
		slu2 = t;
		tp = nu1;
		nu1 = nu2;
		nu2 = tp;

		t = v1;
		v1 = v2;
		v2 = t;
		t = slv1;
		slv1 = slv2;
		slv2 = t;
		tp = nv1;
		nv1 = nv2;
		nv2 = tp;
	}

	while(_y1 < y2) {
		if(_y1 >= cliprect.min_y) {
			int32_t slux = 0, slvx = 0;
			int xx1 = x1>>FRAC_SHIFT;
			int xx2 = x2>>FRAC_SHIFT;
			int32_t u = u1;
			int32_t v = v1;
			if(xx1 != xx2) {
				int delta = xx2-xx1;
				slux = (u2-u1)/delta;
				slvx = (v2-v1)/delta;
			}
			if(xx1 <= cliprect.max_x || xx2 >= cliprect.min_x) {
				if(xx1 < cliprect.min_x) {
					int delta = cliprect.min_x-xx1;
					u += slux*delta;
					v += slvx*delta;
					xx1 = cliprect.min_x;
				}
				if(xx2 > cliprect.max_x)
					xx2 = cliprect.max_x;

				while(xx1 <= xx2) {
					(this->*drawpixel)(xx1,_y1, patterndata, (v>>FRAC_SHIFT)*xsize+(u>>FRAC_SHIFT));
					xx1++;
					u += slux;
					v += slvx;
				}
			}
		}

		x1 += sl1;
		u1 += slu1;
		v1 += slv1;
		x2 += sl2;
		u2 += slu2;
		v2 += slv2;
		_y1++;
	}
	*nx1 = x1;
	*nu1 = u1;
	*nv1 = v1;
	*nx2 = x2;
	*nu2 = u2;
	*nv2 = v2;
}

void saturn_state::vdp1_fill_line(const rectangle &cliprect, int patterndata, int xsize, int32_t y,
							int32_t x1, int32_t x2, int32_t u1, int32_t u2, int32_t v1, int32_t v2)
{
	int xx1 = x1>>FRAC_SHIFT;
	int xx2 = x2>>FRAC_SHIFT;

	if(y > cliprect.max_y || y < cliprect.min_y)
		return;

	if(xx1 <= cliprect.max_x || xx2 >= cliprect.min_x) {
		int32_t slux = 0, slvx = 0;
		int32_t u = u1;
		int32_t v = v1;
		if(xx1 != xx2) {
			int delta = xx2-xx1;
			slux = (u2-u1)/delta;
			slvx = (v2-v1)/delta;
		}
		if(xx1 < cliprect.min_x) {
			int delta = cliprect.min_x-xx1;
			u += slux*delta;
			v += slvx*delta;
			xx1 = cliprect.min_x;
		}
		if(xx2 > cliprect.max_x)
			xx2 = cliprect.max_x;

		while(xx1 <= xx2) {
			(this->*drawpixel)(xx1,y,patterndata,(v>>FRAC_SHIFT)*xsize+(u>>FRAC_SHIFT));
			xx1++;
			u += slux;
			v += slvx;
		}
	}
}

void saturn_state::vdp1_fill_quad(const rectangle &cliprect, int patterndata, int xsize, const struct spoint *q)
{
	int32_t sl1, sl2, slu1, slu2, slv1, slv2, cury, limy, x1, x2, u1, u2, v1, v2, delta;
	int pmin, pmax, i, ps1, ps2;
	struct spoint p[8];

	for(i=0; i<4; i++) {
		p[i].x = p[i+4].x = q[i].x << FRAC_SHIFT;
		p[i].y = p[i+4].y = q[i].y;
		p[i].u = p[i+4].u = q[i].u << FRAC_SHIFT;
		p[i].v = p[i+4].v = q[i].v << FRAC_SHIFT;
	}

	pmin = pmax = 0;
	for(i=1; i<4; i++) {
		if(p[i].y < p[pmin].y)
			pmin = i;
		if(p[i].y > p[pmax].y)
			pmax = i;
	}

	cury = p[pmin].y;
	limy = p[pmax].y;

	if(cury == limy) {
		x1 = x2 = p[0].x;
		u1 = u2 = p[0].u;
		v1 = v2 = p[0].v;
		for(i=1; i<4; i++) {
			if(p[i].x < x1) {
				x1 = p[i].x;
				u1 = p[i].u;
				v1 = p[i].v;
			}
			if(p[i].x > x2) {
				x2 = p[i].x;
				u2 = p[i].u;
				v2 = p[i].v;
			}
		}
		vdp1_fill_line(cliprect, patterndata, xsize, cury, x1, x2, u1, u2, v1, v2);
		return;
	}

	if(cury > cliprect.max_y)
		return;
	if(limy <= cliprect.min_y)
		return;

	if(limy > cliprect.max_y)
		limy = cliprect.max_y;

	ps1 = pmin+4;
	ps2 = pmin;

	goto startup;

	for(;;) {
		if(p[ps1-1].y == p[ps2+1].y) {
			vdp1_fill_slope(cliprect, patterndata, xsize,
							x1, x2, sl1, sl2, &x1, &x2,
							u1, u2, slu1, slu2, &u1, &u2,
							v1, v2, slv1, slv2, &v1, &v2,
							cury, p[ps1-1].y);
			cury = p[ps1-1].y;
			if(cury >= limy)
				break;
			ps1--;
			ps2++;

		startup:
			while(p[ps1-1].y == cury)
				ps1--;
			while(p[ps2+1].y == cury)
				ps2++;
			x1 = p[ps1].x;
			u1 = p[ps1].u;
			v1 = p[ps1].v;
			x2 = p[ps2].x;
			u2 = p[ps2].u;
			v2 = p[ps2].v;

			delta = cury-p[ps1-1].y;
			sl1 = (x1-p[ps1-1].x)/delta;
			slu1 = (u1-p[ps1-1].u)/delta;
			slv1 = (v1-p[ps1-1].v)/delta;

			delta = cury-p[ps2+1].y;
			sl2 = (x2-p[ps2+1].x)/delta;
			slu2 = (u2-p[ps2+1].u)/delta;
			slv2 = (v2-p[ps2+1].v)/delta;
		} else if(p[ps1-1].y < p[ps2+1].y) {
			vdp1_fill_slope(cliprect, patterndata, xsize,
							x1, x2, sl1, sl2, &x1, &x2,
							u1, u2, slu1, slu2, &u1, &u2,
							v1, v2, slv1, slv2, &v1, &v2,
							cury, p[ps1-1].y);
			cury = p[ps1-1].y;
			if(cury >= limy)
				break;
			ps1--;
			while(p[ps1-1].y == cury)
				ps1--;
			x1 = p[ps1].x;
			u1 = p[ps1].u;
			v1 = p[ps1].v;

			delta = cury-p[ps1-1].y;
			sl1 = (x1-p[ps1-1].x)/delta;
			slu1 = (u1-p[ps1-1].u)/delta;
			slv1 = (v1-p[ps1-1].v)/delta;
		} else {
			vdp1_fill_slope(cliprect, patterndata, xsize,
							x1, x2, sl1, sl2, &x1, &x2,
							u1, u2, slu1, slu2, &u1, &u2,
							v1, v2, slv1, slv2, &v1, &v2,
							cury, p[ps2+1].y);
			cury = p[ps2+1].y;
			if(cury >= limy)
				break;
			ps2++;
			while(p[ps2+1].y == cury)
				ps2++;
			x2 = p[ps2].x;
			u2 = p[ps2].u;
			v2 = p[ps2].v;

			delta = cury-p[ps2+1].y;
			sl2 = (x2-p[ps2+1].x)/delta;
			slu2 = (u2-p[ps2+1].u)/delta;
			slv2 = (v2-p[ps2+1].v)/delta;
		}
	}
	if(cury == limy)
		vdp1_fill_line(cliprect, patterndata, xsize, cury, x1, x2, u1, u2, v1, v2);
}

int saturn_state::x2s(int v)
{
	return (int32_t)(int16_t)v + m_vdp1_legacy.local_x;
}

int saturn_state::y2s(int v)
{
	return (int32_t)(int16_t)v + m_vdp1_legacy.local_y;
}

void saturn_state::vdp1_draw_line(const rectangle &cliprect)
{
	struct spoint q[4];

	q[0].x = x2s(current_sprite.CMDXA);
	q[0].y = y2s(current_sprite.CMDYA);
	q[1].x = x2s(current_sprite.CMDXB);
	q[1].y = y2s(current_sprite.CMDYB);
	q[2].x = x2s(current_sprite.CMDXA);
	q[2].y = y2s(current_sprite.CMDYA);
	q[3].x = x2s(current_sprite.CMDXB);
	q[3].y = y2s(current_sprite.CMDYB);

	q[0].u = q[3].u = q[1].u = q[2].u = 0;
	q[0].v = q[1].v = q[2].v = q[3].v = 0;

	vdp1_fill_quad(cliprect, 0, 1, q);
}

void saturn_state::vdp1_draw_poly_line(const rectangle &cliprect)
{
	struct spoint q[4];

	q[0].x = x2s(current_sprite.CMDXA);
	q[0].y = y2s(current_sprite.CMDYA);
	q[1].x = x2s(current_sprite.CMDXB);
	q[1].y = y2s(current_sprite.CMDYB);
	q[2].x = x2s(current_sprite.CMDXA);
	q[2].y = y2s(current_sprite.CMDYA);
	q[3].x = x2s(current_sprite.CMDXB);
	q[3].y = y2s(current_sprite.CMDYB);

	q[0].u = q[3].u = q[1].u = q[2].u = 0;
	q[0].v = q[1].v = q[2].v = q[3].v = 0;

	vdp1_fill_quad(cliprect, 0, 1, q);

	q[0].x = x2s(current_sprite.CMDXB);
	q[0].y = y2s(current_sprite.CMDYB);
	q[1].x = x2s(current_sprite.CMDXC);
	q[1].y = y2s(current_sprite.CMDYC);
	q[2].x = x2s(current_sprite.CMDXB);
	q[2].y = y2s(current_sprite.CMDYB);
	q[3].x = x2s(current_sprite.CMDXC);
	q[3].y = y2s(current_sprite.CMDYC);

	q[0].u = q[3].u = q[1].u = q[2].u = 0;
	q[0].v = q[1].v = q[2].v = q[3].v = 0;

	vdp1_fill_quad(cliprect, 0, 1, q);

	q[0].x = x2s(current_sprite.CMDXC);
	q[0].y = y2s(current_sprite.CMDYC);
	q[1].x = x2s(current_sprite.CMDXD);
	q[1].y = y2s(current_sprite.CMDYD);
	q[2].x = x2s(current_sprite.CMDXC);
	q[2].y = y2s(current_sprite.CMDYC);
	q[3].x = x2s(current_sprite.CMDXD);
	q[3].y = y2s(current_sprite.CMDYD);

	q[0].u = q[3].u = q[1].u = q[2].u = 0;
	q[0].v = q[1].v = q[2].v = q[3].v = 0;

	vdp1_fill_quad(cliprect, 0, 1, q);

	q[0].x = x2s(current_sprite.CMDXD);
	q[0].y = y2s(current_sprite.CMDYD);
	q[1].x = x2s(current_sprite.CMDXA);
	q[1].y = y2s(current_sprite.CMDYA);
	q[2].x = x2s(current_sprite.CMDXD);
	q[2].y = y2s(current_sprite.CMDYD);
	q[3].x = x2s(current_sprite.CMDXA);
	q[3].y = y2s(current_sprite.CMDYA);

	q[0].u = q[3].u = q[1].u = q[2].u = 0;
	q[0].v = q[1].v = q[2].v = q[3].v = 0;

	vdp1_setup_shading(q, cliprect);
	vdp1_fill_quad(cliprect, 0, 1, q);

}

void saturn_state::vdp1_draw_distorted_sprite(const rectangle &cliprect)
{
	struct spoint q[4];

	int xsize, ysize;
	int direction;
	int patterndata;

	direction = (current_sprite.CMDCTRL & 0x0030)>>4;

	if ( current_sprite.ispoly )
	{
		xsize = ysize = 1;
		patterndata = 0;
	}
	else
	{
		xsize = (current_sprite.CMDSIZE & 0x3f00) >> 8;
		xsize = xsize * 8;
		if (xsize == 0) return; /* setting prohibited */

		ysize = (current_sprite.CMDSIZE & 0x00ff);
		if (ysize == 0) return; /* setting prohibited */

		patterndata = (current_sprite.CMDSRCA) & 0xffff;
		patterndata = patterndata * 0x8;

	}


	q[0].x = x2s(current_sprite.CMDXA);
	q[0].y = y2s(current_sprite.CMDYA);
	q[1].x = x2s(current_sprite.CMDXB);
	q[1].y = y2s(current_sprite.CMDYB);
	q[2].x = x2s(current_sprite.CMDXC);
	q[2].y = y2s(current_sprite.CMDYC);
	q[3].x = x2s(current_sprite.CMDXD);
	q[3].y = y2s(current_sprite.CMDYD);

	if(direction & 1) { // xflip
		q[0].u = q[3].u = xsize-1;
		q[1].u = q[2].u = 0;
	} else {
		q[0].u = q[3].u = 0;
		q[1].u = q[2].u = xsize-1;
	}
	if(direction & 2) { // yflip
		q[0].v = q[1].v = ysize-1;
		q[2].v = q[3].v = 0;
	} else {
		q[0].v = q[1].v = 0;
		q[2].v = q[3].v = ysize-1;
	}

	vdp1_setup_shading(q, cliprect);
	vdp1_fill_quad(cliprect, patterndata, xsize, q);
}

void saturn_state::vdp1_draw_scaled_sprite(const rectangle &cliprect)
{
	struct spoint q[4];

	int xsize, ysize;
	int direction;
	int patterndata;
	int zoompoint;
	int x,y;
	int x2,y2;
	int screen_width,screen_height,screen_height_negative = 0;

	direction = (current_sprite.CMDCTRL & 0x0030)>>4;

	xsize = (current_sprite.CMDSIZE & 0x3f00) >> 8;
	xsize = xsize * 8;

	ysize = (current_sprite.CMDSIZE & 0x00ff);

	patterndata = (current_sprite.CMDSRCA) & 0xffff;
	patterndata = patterndata * 0x8;

	zoompoint = (current_sprite.CMDCTRL & 0x0f00)>>8;

	x = current_sprite.CMDXA;
	y = current_sprite.CMDYA;

	screen_width = (int16_t)current_sprite.CMDXB;
	if ( (screen_width < 0) && zoompoint)
	{
		screen_width = -screen_width;
		direction |= 1;
	}

	screen_height = (int16_t)current_sprite.CMDYB;
	if ( (screen_height < 0) && zoompoint )
	{
		screen_height_negative = 1;
		screen_height = -screen_height;
		direction |= 2;
	}

	x2 = current_sprite.CMDXC; // second co-ordinate set x
	y2 = current_sprite.CMDYC; // second co-ordinate set y

	switch (zoompoint)
	{
		case 0x0: // specified co-ordinates
			break;
		case 0x5: // up left
			break;
		case 0x6: // up center
			x -= screen_width/2 ;
			break;
		case 0x7: // up right
			x -= screen_width;
			break;

		case 0x9: // center left
			y -= screen_height/2 ;
			break;
		case 0xa: // center center
			y -= screen_height/2 ;
			x -= screen_width/2 ;

			break;

		case 0xb: // center right
			y -= screen_height/2 ;
			x -= screen_width;
			break;

		case 0xd: // center left
			y -= screen_height;
			break;

		case 0xe: // center center
			y -= screen_height;
			x -= screen_width/2 ;
			break;

		case 0xf: // center right
			y -= screen_height;
			x -= screen_width;
			break;

		default: // illegal
			break;

	}

	/*  0----1
	    |    |
	    |    |
	    3----2   */

	if (zoompoint)
	{
		q[0].x = x2s(x);
		q[0].y = y2s(y);
		q[1].x = x2s(x)+screen_width;
		q[1].y = y2s(y);
		q[2].x = x2s(x)+screen_width;
		q[2].y = y2s(y)+screen_height;
		q[3].x = x2s(x);
		q[3].y = y2s(y)+screen_height;

		if ( screen_height_negative )
		{
			q[0].y += screen_height;
			q[1].y += screen_height;
			q[2].y += screen_height;
			q[3].y += screen_height;
		}
	}
	else
	{
		q[0].x = x2s(x);
		q[0].y = y2s(y);
		q[1].x = x2s(x2);
		q[1].y = y2s(y);
		q[2].x = x2s(x2);
		q[2].y = y2s(y2);
		q[3].x = x2s(x);
		q[3].y = y2s(y2);
	}


	if(direction & 1) { // xflip
		q[0].u = q[3].u = xsize-1;
		q[1].u = q[2].u = 0;
	} else {
		q[0].u = q[3].u = 0;
		q[1].u = q[2].u = xsize-1;
	}
	if(direction & 2) { // yflip
		q[0].v = q[1].v = ysize-1;
		q[2].v = q[3].v = 0;
	} else {
		q[0].v = q[1].v = 0;
		q[2].v = q[3].v = ysize-1;
	}

	vdp1_setup_shading(q, cliprect);
	vdp1_fill_quad(cliprect, patterndata, xsize, q);
}




void saturn_state::vdp1_draw_normal_sprite(const rectangle &cliprect, int sprite_type)
{
	int y, ysize, drawypos;
	int x, xsize, drawxpos;
	int direction;
	int patterndata;
	uint8_t shading;
	int su, u, dux, duy;
	int maxdrawypos, maxdrawxpos;

	x = x2s(current_sprite.CMDXA);
	y = y2s(current_sprite.CMDYA);

	direction = (current_sprite.CMDCTRL & 0x0030)>>4;

	xsize = (current_sprite.CMDSIZE & 0x3f00) >> 8;
	xsize = xsize * 8;

	ysize = (current_sprite.CMDSIZE & 0x00ff);

	patterndata = (current_sprite.CMDSRCA) & 0xffff;
	patterndata = patterndata * 0x8;

	if (VDP1_LOG) logerror ("Drawing Normal Sprite x %04x y %04x xsize %04x ysize %04x patterndata %06x\n",x,y,xsize,ysize,patterndata);

	if ( x > cliprect.max_x ) return;
	if ( y > cliprect.max_y ) return;

	shading = read_gouraud_table();
	if ( shading )
	{
		struct spoint q[4];
		q[0].x = x; q[0].y = y;
		q[1].x = x + xsize; q[1].y = y;
		q[2].x = x + xsize; q[2].y = y + ysize;
		q[3].x = x; q[3].y = y + ysize;

		vdp1_setup_shading( q, cliprect );
	}

	u = 0;
	dux = 1;
	duy = xsize;
	if ( direction & 0x1 ) //xflip
	{
		dux = -1;
		u = xsize - 1;
	}
	if ( direction & 0x2 ) //yflip
	{
		duy = -xsize;
		u += xsize*(ysize-1);
	}
	if ( y < cliprect.min_y ) //clip y
	{
		// draculax user clips a 320x240 sprite for inverted castle map (obviously x & y flipped)
		// we need to adjust U calculation only to make it align properly,
		// adjusting ysize will already glitch out flipped doors in gameplay.
		const int adjust_y = direction & 2 ? y - cliprect.min_y : cliprect.min_y - y;
		u += xsize * (adjust_y);
		ysize -= (cliprect.min_y - y);
		y = cliprect.min_y;
	}
	if ( x < cliprect.min_x ) //clip x
	{
		u += dux*(cliprect.min_x - x);
		xsize -= (cliprect.min_x - x);
		x = cliprect.min_x;
	}
	maxdrawypos = std::min(y+ysize-1,cliprect.max_y);
	maxdrawxpos = std::min(x+xsize-1,cliprect.max_x);
	for (drawypos = y; drawypos <= maxdrawypos; drawypos++ )
	{
		//destline = m_vdp1_legacy.framebuffer_draw_lines[drawypos];
		su = u;
		for (drawxpos = x; drawxpos <= maxdrawxpos; drawxpos++ )
		{
			(this->*drawpixel)( drawxpos, drawypos, patterndata, u );
			u += dux;
		}
		u = su + duy;
	}
}

TIMER_CALLBACK_MEMBER(saturn_state::vdp1_draw_end )
{
	/* set CEF to 1*/
	CEF_1();

	// TODO: temporary for Batman Forever, presumably anonymous timer not behaving well.
	#if 0
	if(!(m_scu.ism & IRQ_VDP1_END))
	{
		m_maincpu->set_input_line_and_vector(0x2, HOLD_LINE, 0x4d); // SH2
		scu_do_transfer(6);
	}
	else
		m_scu.ist |= (IRQ_VDP1_END);
	#endif
}


void saturn_state::vdp1_process_list()
{
	int position;
	int spritecount;
	int vdp1_nest;
	rectangle *cliprect;

	spritecount = 0;
	position = 0;

	if (VDP1_LOG) logerror ("Sprite List Process START\n");

	vdp1_nest = -1;

	clear_gouraud_shading();

	/*Set CEF bit to 0*/
	CEF_0();

	// TODO: is there an actual limit for this?
	while (spritecount < 16383) // max 16383 with texture or max 16384 without texture - virtually unlimited
	{
		int draw_this_sprite;

		draw_this_sprite = 1;

	//  if (position >= ((0x80000/0x20)/4)) // safety check
	//  {
	//      if (VDP1_LOG) logerror ("Sprite List Position Too High!\n");
	//      position = 0;
	//  }

		spritecount++;

		current_sprite.CMDCTRL = (m_vdp1_vram[position * (0x20/4)+0] & 0xffff0000) >> 16;

		if (current_sprite.CMDCTRL == 0x8000)
		{
			if (VDP1_LOG) logerror ("List Terminator (0x8000) Encountered, Sprite List Process END\n");
			goto end; // end of list
		}

		current_sprite.CMDLINK = (m_vdp1_vram[position * (0x20/4)+0] & 0x0000ffff) >> 0;
		current_sprite.CMDPMOD = (m_vdp1_vram[position * (0x20/4)+1] & 0xffff0000) >> 16;
		current_sprite.CMDCOLR = (m_vdp1_vram[position * (0x20/4)+1] & 0x0000ffff) >> 0;
		current_sprite.CMDSRCA = (m_vdp1_vram[position * (0x20/4)+2] & 0xffff0000) >> 16;
		current_sprite.CMDSIZE = (m_vdp1_vram[position * (0x20/4)+2] & 0x0000ffff) >> 0;
		current_sprite.CMDXA   = (m_vdp1_vram[position * (0x20/4)+3] & 0xffff0000) >> 16;
		current_sprite.CMDYA   = (m_vdp1_vram[position * (0x20/4)+3] & 0x0000ffff) >> 0;
		current_sprite.CMDXB   = (m_vdp1_vram[position * (0x20/4)+4] & 0xffff0000) >> 16;
		current_sprite.CMDYB   = (m_vdp1_vram[position * (0x20/4)+4] & 0x0000ffff) >> 0;
		current_sprite.CMDXC   = (m_vdp1_vram[position * (0x20/4)+5] & 0xffff0000) >> 16;
		current_sprite.CMDYC   = (m_vdp1_vram[position * (0x20/4)+5] & 0x0000ffff) >> 0;
		current_sprite.CMDXD   = (m_vdp1_vram[position * (0x20/4)+6] & 0xffff0000) >> 16;
		current_sprite.CMDYD   = (m_vdp1_vram[position * (0x20/4)+6] & 0x0000ffff) >> 0;
		current_sprite.CMDGRDA = (m_vdp1_vram[position * (0x20/4)+7] & 0xffff0000) >> 16;
//      current_sprite.UNUSED  = (m_vdp1_vram[position * (0x20/4)+7] & 0x0000ffff) >> 0;

		/* proecess jump / skip commands, set position for next sprite */
		switch (current_sprite.CMDCTRL & 0x7000)
		{
			case 0x0000: // jump next
				if (VDP1_LOG) logerror ("Sprite List Process + Next (Normal)\n");
				position++;
				break;
			case 0x1000: // jump assign
				if (VDP1_LOG) logerror ("Sprite List Process + Jump Old %06x New %06x\n", position, (current_sprite.CMDLINK>>2));
				position= (current_sprite.CMDLINK>>2);
				break;
			case 0x2000: // jump call
				if (vdp1_nest == -1)
				{
					if (VDP1_LOG) logerror ("Sprite List Process + Call Old %06x New %06x\n",position, (current_sprite.CMDLINK>>2));
					vdp1_nest = position+1;
					position = (current_sprite.CMDLINK>>2);
				}
				else
				{
					if (VDP1_LOG) logerror ("Sprite List Nested Call, ignoring\n");
					position++;
				}
				break;
			case 0x3000:
				if (vdp1_nest != -1)
				{
					if (VDP1_LOG) logerror ("Sprite List Process + Return\n");
					position = vdp1_nest;
					vdp1_nest = -1;
				}
				else
				{
					if (VDP1_LOG) logerror ("Attempted return from no subroutine, aborting\n");
					position++;
					goto end; // end of list
				}
				break;
			case 0x4000:
				draw_this_sprite = 0;
				position++;
				break;
			case 0x5000:
				if (VDP1_LOG) logerror ("Sprite List Skip + Jump Old %06x New %06x\n", position, (current_sprite.CMDLINK>>2));
				draw_this_sprite = 0;
				position= (current_sprite.CMDLINK>>2);

				break;
			case 0x6000:
				draw_this_sprite = 0;
				if (vdp1_nest == -1)
				{
					if (VDP1_LOG) logerror ("Sprite List Skip + Call To Subroutine Old %06x New %06x\n",position, (current_sprite.CMDLINK>>2));

					vdp1_nest = position+1;
					position = (current_sprite.CMDLINK>>2);
				}
				else
				{
					if (VDP1_LOG) logerror ("Sprite List Nested Call, ignoring\n");
					position++;
				}
				break;
			case 0x7000:
				draw_this_sprite = 0;
				if (vdp1_nest != -1)
				{
					if (VDP1_LOG) logerror ("Sprite List Skip + Return from Subroutine\n");

					position = vdp1_nest;
					vdp1_nest = -1;
				}
				else
				{
					if (VDP1_LOG) logerror ("Attempted return from no subroutine, aborting\n");
					position++;
					goto end; // end of list
				}
				break;
		}

		/* continue to draw this sprite only if the command wasn't to skip it */
		if (draw_this_sprite == 1)
		{
			if ( current_sprite.CMDPMOD & 0x0400 )
			{
				//if(current_sprite.CMDPMOD & 0x0200) /* TODO: Bio Hazard inventory screen uses outside cliprect */
				//  cliprect = &m_vdp1_legacy.system_cliprect;
				//else
					cliprect = &m_vdp1_legacy.user_cliprect;
			}
			else
			{
				cliprect = &m_vdp1_legacy.system_cliprect;
			}

			vdp1_set_drawpixel();

			switch (current_sprite.CMDCTRL & 0x000f)
			{
				case 0x0000:
					if (VDP1_LOG) logerror ("Sprite List Normal Sprite (%d %d)\n",current_sprite.CMDXA,current_sprite.CMDYA);
					current_sprite.ispoly = 0;
					vdp1_draw_normal_sprite(*cliprect, 0);
					break;

				case 0x0001:
					if (VDP1_LOG) logerror ("Sprite List Scaled Sprite (%d %d)\n",current_sprite.CMDXA,current_sprite.CMDYA);
					current_sprite.ispoly = 0;
					vdp1_draw_scaled_sprite(*cliprect);
					break;

				case 0x0002:
				case 0x0003: // used by Hardcore 4x4
					if (VDP1_LOG) logerror ("Sprite List Distorted Sprite\n");
					if (VDP1_LOG) logerror ("(A: %d %d)\n",current_sprite.CMDXA,current_sprite.CMDYA);
					if (VDP1_LOG) logerror ("(B: %d %d)\n",current_sprite.CMDXB,current_sprite.CMDYB);
					if (VDP1_LOG) logerror ("(C: %d %d)\n",current_sprite.CMDXC,current_sprite.CMDYC);
					if (VDP1_LOG) logerror ("(D: %d %d)\n",current_sprite.CMDXD,current_sprite.CMDYD);
					if (VDP1_LOG) logerror ("CMDPMOD = %04x\n",current_sprite.CMDPMOD);

					current_sprite.ispoly = 0;
					vdp1_draw_distorted_sprite(*cliprect);
					break;

				case 0x0004:
					if (VDP1_LOG) logerror ("Sprite List Polygon\n");
					current_sprite.ispoly = 1;
					vdp1_draw_distorted_sprite(*cliprect);
					break;

				case 0x0005:
				case 0x0007: // mirror? baroque/samsho4
					if (VDP1_LOG) logerror ("Sprite List Polyline\n");
					current_sprite.ispoly = 1;
					vdp1_draw_poly_line(*cliprect);
					break;

				case 0x0006:
					if (VDP1_LOG) logerror ("Sprite List Line\n");
					current_sprite.ispoly = 1;
					vdp1_draw_line(*cliprect);
					break;

				case 0x0008:
//              case 0x000b: // mirror? Bug 2
					if (VDP1_LOG) logerror ("Sprite List Set Command for User Clipping (%d,%d),(%d,%d)\n", current_sprite.CMDXA, current_sprite.CMDYA, current_sprite.CMDXC, current_sprite.CMDYC);
					m_vdp1_legacy.user_cliprect.set(current_sprite.CMDXA, current_sprite.CMDXC, current_sprite.CMDYA, current_sprite.CMDYC);
					break;

				case 0x0009:
					if (VDP1_LOG) logerror ("Sprite List Set Command for System Clipping (0,0),(%d,%d)\n", current_sprite.CMDXC, current_sprite.CMDYC);
					m_vdp1_legacy.system_cliprect.set(0, current_sprite.CMDXC, 0, current_sprite.CMDYC);
					break;

				case 0x000a:
					if (VDP1_LOG) logerror ("Sprite List Local Co-Ordinate Set (%d %d)\n",(int16_t)current_sprite.CMDXA,(int16_t)current_sprite.CMDYA);
					m_vdp1_legacy.local_x = (int16_t)current_sprite.CMDXA;
					m_vdp1_legacy.local_y = (int16_t)current_sprite.CMDYA;
					break;

				default:
					// asenna 0x0c or 0x0d (transition from title screen)
					// raymanj 0x0d (at startup)
					// choroqpk 0x0e (when selecting island in main menu)
					// albodysj 0x0f (always)
					if ((current_sprite.CMDCTRL & 0x000f) < 0xc)
						popmessage ("VDP1: Sprite List Illegal %02x (%d)",current_sprite.CMDCTRL & 0xf,spritecount);
					m_vdp1_legacy.lopr = (position * 0x20) >> 3;
					//m_vdp1_legacy.copr = (position * 0x20) >> 3;
					// prematurely kill the VDP1 process if an illegal opcode is executed
					// sexyparo calls multiple illegals and expects VDP1 irq to be fired anyway!
					goto end;
			}
		}

	}


	end:
	m_vdp1_legacy.copr = (position * 0x20) >> 3;


	/* TODO: what's the exact formula? Guess it should be a mix between number of pixels written and actual command data fetched. */
	// if spritecount = 10000 don't send a vdp1 draw end
//  if(spritecount < 10000)
	m_vdp1_legacy.draw_end_timer->adjust(m_maincpu->cycles_to_attotime(spritecount*16));

	if (VDP1_LOG) logerror ("End of list processing!\n");
}

void saturn_state::vdp1_video_update()
{
	int framebuffer_changed = 0;

//  int enable;
//  if (machine.input().code_pressed (KEYCODE_R)) VDP1_LOG = 1;
//  if (machine.input().code_pressed (KEYCODE_T)) VDP1_LOG = 0;

//  if (machine.input().code_pressed (KEYCODE_Y)) VDP1_LOG = 0;
//  {
//      FILE *fp;
//
//      fp=fopen("vdp1_ram.dmp", "w+b");
//      if (fp)
//      {
//          fwrite(stv_vdp1, 0x00100000, 1, fp);
//          fclose(fp);
//      }
//  }
	if (VDP1_LOG) logerror("vdp1_video_update called\n");
	if (VDP1_LOG) logerror( "FBCR = %0x, accessed = %d\n", VDP1_FBCR, m_vdp1_legacy.fbcr_accessed );

	if(VDP1_CEF)
		BEF_1();
	else
		BEF_0();

	if ( m_vdp1_legacy.framebuffer_clear_on_next_frame )
	{
		if ( ((VDP1_FBCR & 0x3) == 3) &&
			m_vdp1_legacy.fbcr_accessed )
		{
			vdp1_clear_framebuffer(m_vdp1_legacy.framebuffer_current_display);
			m_vdp1_legacy.framebuffer_clear_on_next_frame = 0;
		}
	}

	switch( VDP1_FBCR & 0x3 )
	{
		case 0: /* Automatic mode */
			vdp1_change_framebuffers();
			vdp1_clear_framebuffer(m_vdp1_legacy.framebuffer_current_draw);
			framebuffer_changed = 1;
			break;
		case 1: /* Setting prohibited */
			break;
		case 2: /* Manual mode - erase */
			if (m_vdp1_legacy.fbcr_accessed)
			{
				m_vdp1_legacy.framebuffer_clear_on_next_frame = 1;
			}
			break;
		case 3: /* Manual mode - change */
			if (m_vdp1_legacy.fbcr_accessed)
			{
				vdp1_change_framebuffers();
				if (VDP1_VBE())
				{
					vdp1_clear_framebuffer(m_vdp1_legacy.framebuffer_current_draw);
				}
				/* TODO: Slam n Jam 96 & Cross Romance doesn't like this, investigate. */
				framebuffer_changed = 1;
			}
	//      framebuffer_changed = 1;
			break;
	}
	m_vdp1_legacy.fbcr_accessed = 0;

	if (VDP1_LOG) logerror("PTM = %0x, TVM = %x\n", VDP1_PTM, VDP1_TVM());
	/*Set CEF bit to 0*/
	//CEF_0();
	switch (VDP1_PTM & 3)
	{
		case 0:/*Idle Mode*/
			/*Set CEF bit to 0*/
			//CEF_0();
			break;
		case 1:/*Draw by request*/
			/*Set CEF bit to 0*/
			//CEF_0();
			break;
		case 2:/*Automatic Draw*/
			if ( framebuffer_changed || VDP1_LOG )
			{
				/*set CEF to 1*/
				vdp1_process_list();
			}
			break;
		case 3: /*<invalid>*/
			logerror("Warning: Invalid PTM mode set for VDP1!\n");
			break;
	}
	//popmessage("%04x %04x",VDP1_EWRR_X3,VDP1_EWRR_Y3);
}

void saturn_state::vdp1_state_save_postload()
{
	uint8_t *vdp1 = m_vdp1_legacy.gfx_decode.get();
	int offset;
	uint32_t data;

	m_vdp1_legacy.framebuffer_mode = -1;
	m_vdp1_legacy.framebuffer_double_interlace = -1;

	vdp1_set_framebuffer_config();

	for (offset = 0; offset < 0x80000/4; offset++ )
	{
		data = m_vdp1_vram[offset];
		/* put in gfx region for easy decoding */
		vdp1[offset*4+0] = (data & 0xff000000) >> 24;
		vdp1[offset*4+1] = (data & 0x00ff0000) >> 16;
		vdp1[offset*4+2] = (data & 0x0000ff00) >> 8;
		vdp1[offset*4+3] = (data & 0x000000ff) >> 0;
	}
}

int saturn_state::vdp1_start()
{
	m_vdp1_regs = make_unique_clear<uint16_t[]>(0x020/2 );
	m_vdp1_vram = make_unique_clear<uint32_t[]>(0x100000/4 );
	m_vdp1_legacy.gfx_decode = std::make_unique<uint8_t[]>(0x100000 );

	vdp1_shading_data = std::make_unique<struct vdp1_poly_scanline_data>();

	m_vdp1_legacy.framebuffer[0] = std::make_unique<uint16_t[]>(1024 * 256 * 2 ); /* *2 is for double interlace */
	m_vdp1_legacy.framebuffer[1] = std::make_unique<uint16_t[]>(1024 * 256 * 2 );

	m_vdp1_legacy.framebuffer_display_lines = std::make_unique<uint16_t * []>(512);
	m_vdp1_legacy.framebuffer_draw_lines = std::make_unique<uint16_t * []>(512);

	m_vdp1_legacy.framebuffer_width = m_vdp1_legacy.framebuffer_height = 0;
	m_vdp1_legacy.framebuffer_mode = -1;
	m_vdp1_legacy.framebuffer_double_interlace = -1;
	m_vdp1_legacy.fbcr_accessed = 0;
	m_vdp1_legacy.framebuffer_current_display = 0;
	m_vdp1_legacy.framebuffer_current_draw = 1;
	vdp1_clear_framebuffer(m_vdp1_legacy.framebuffer_current_draw);
	m_vdp1_legacy.framebuffer_clear_on_next_frame = 0;

	m_vdp1_legacy.system_cliprect.set(0, 0, 0, 0);
	/* Kidou Senshi Z Gundam - Zenpen Zeta no Kodou loves to use the user cliprect vars in an undefined state ... */
	m_vdp1_legacy.user_cliprect.set(0, 512, 0, 256);

	m_vdp1_legacy.draw_end_timer = timer_alloc(FUNC(saturn_state::vdp1_draw_end), this);
	// save state
	save_pointer(NAME(m_vdp1_regs), 0x020/2);
	save_pointer(NAME(m_vdp1_vram), 0x100000/4);
	save_item(NAME(m_vdp1_legacy.fbcr_accessed));
	save_item(NAME(m_vdp1_legacy.framebuffer_current_display));
	save_item(NAME(m_vdp1_legacy.framebuffer_current_draw));
	save_item(NAME(m_vdp1_legacy.framebuffer_clear_on_next_frame));
	save_item(NAME(m_vdp1_legacy.local_x));
	save_item(NAME(m_vdp1_legacy.local_y));
	machine().save().register_postload(save_prepost_delegate(FUNC(saturn_state::vdp1_state_save_postload), this));
	return 0;
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

	save_pointer(NAME(m_vdp2_regs), 0x040000 / 2);
	save_pointer(NAME(m_vdp2_vram), 0x100000 / 4);
	save_pointer(NAME(m_vdp2_cram), 0x080000 / 4);

	return 0;
}

VIDEO_START_MEMBER(saturn_state, vdp2_video_start)
{
	vdp2_start();
	vdp1_start();
}

// VDP1 frame buffer as VDP2 reads it for the sprite layer: one 16-bit word per
// dot, doubled horizontally in the low resolution VDP1 mode on a hi-res
// screen, and read at half the line rate for a non-interlaced buffer on a
// double-density screen.
class saturn_state::vdp2_sprite_fb : public saturn_vdp2_render::sprite_source
{
public:
	vdp2_sprite_fb(uint16_t *const *lines, unsigned pitch, bool half_lines, bool double_x)
		: m_lines(lines), m_pitch(pitch), m_half_lines(half_lines), m_double_x(double_x)
	{
	}

	virtual uint16_t sprite_word(unsigned x, unsigned y) const override
	{
		unsigned const fx = x >> (m_double_x ? 1 : 0);
		unsigned const fy = std::min(y >> (m_half_lines ? 1 : 0), 511U);
		uint16_t const *const line = m_lines ? m_lines[fy] : nullptr;
		if (!line || fx >= m_pitch)
			return 0;
		return line[fx];
	}

private:
	uint16_t *const *m_lines;
	unsigned m_pitch;
	bool m_half_lines;
	bool m_double_x;
};

uint32_t saturn_state::screen_update_vdp2(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect)
{
	static constexpr unsigned widths[4] = { 320, 352, 640, 704 };
	uint8_t const hreso = m_vdp2->get_hreso();

	saturn_vdp2_render::memory mem;
	mem.regs = m_vdp2_regs.get();
	mem.vram = m_vdp2_vram.get();
	mem.cram = m_vdp2_cram.get();
	mem.vram_mask = 0x7ffff;

	saturn_vdp2_render::screen_config cfg;
	cfg.width = widths[hreso & 3];
	cfg.hires = BIT(hreso, 1);
	cfg.lsmd = m_vdp2->get_lsmd();
	cfg.disp = m_vdp2->get_disp();
	cfg.bdclmd = m_vdp2->get_bdclmd();
	cfg.pal = m_vdp2->is_pal();

	vdp2_sprite_fb const sprites(
			m_vdp1_legacy.framebuffer_display_lines.get(),
			m_vdp1_legacy.framebuffer_width ? m_vdp1_legacy.framebuffer_width : 1,
			cfg.lsmd == 3 && m_vdp1_legacy.framebuffer_double_interlace == 0,
			VDP1_TVM() == 0 && cfg.hires);

	m_vdp2_renderer.begin_frame(mem, cfg);
	uint32_t line[saturn_vdp2_render::renderer::MAX_WIDTH];
	for (int y = 0; y <= cliprect.bottom(); y++)
	{
		m_vdp2_renderer.render_line(y, sprites, line);
		if (y >= cliprect.top())
		{
			uint32_t *const dest = &bitmap.pix(y);
			for (int x = cliprect.left(); x <= cliprect.right() && x < int(cfg.width); x++)
				dest[x] = 0xff000000 | line[x];
		}
	}

	return 0;
}

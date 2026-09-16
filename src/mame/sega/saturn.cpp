// license:LGPL-2.1+
// copyright-holders:David Haywood, Angelo Salese, Olivier Galibert, Mariusz
// Wojcieszek, R. Belmont Contains VDP1 and VDP2 code. Use "Sega Saturn VDP2"
// marker for start of VDP2 code
/**************************************************************************************************

    Sega Saturn (c) 1994 Sega

    @TODO List of things that needs to be implemented:
    - There's definitely an ack mechanism in SCU irqs. This is almost surely
done via the ISM register (i.e. going 0->1 to the given bit acks it).
    - There might be a delay to exactly when SCU irqs happens. This is due to
the basic fact that SCU runs at 14-ish MHz, so it needs some time before
actually firing the irq.
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
    - Timer 0 doesn't work if the TENB bit isn't enabled (documentation is a bit
fussy over this).
    - Timer 0 fires at the HBlank-In signal, not before.
    - VDP2 H Counter actually counts x2 in non Hi-Res mode.
    - Timer 1 is definitely annoying. Starts from H-Blank signal and starts
counting from that position. H counter value 0x282 (642) -> timer 1 fires at
setting 1 H counter value 0x284 (644) -> 2 H counter value 0x2a0 (672) -> 0x10
      H counter value 0x2c0 (704) -> 0x20
      H counter value 0x300 (768) -> 0x40
      H counter value 0x340 (832) -> 0x60
      H counter value 0x352 (850) -> 0x69
      H counter value 0x000 (0)   -> 0x6a, V counter goes +1 here (max range?)
      H counter value 0x02c (44)  -> 0x80
      H counter value 0x0ec (236) -> 0xe0
      H counter value 0x12c (300) -> 0x100
    - Timer 1 seems to count backwards compared to Timer 0 from setting 0x6b
onward.
    - Yabause claims that if VDP2 DISP bit isn't enabled then vblank irqs
(hblank too?) doesn't happen.

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
- Some places are known to effectively glitch out in special cases with wrong
pitch set cfr. suikoenb (STV), fill others;
- Packed 8-bpp drawing/CPU access/erase/readout is implemented. Interlace field
  selection, rotated VDP2 readout and mismatched VDP1/VDP2 dot formats need work;

TODO (VDP2):
- Mixing with VDP1;
- Blending is incorrectly enabled on some places
  cfr. decathlt gameplay, dragndrm title screen, Data East logo in the Magical
Drop games;
- Incomplete/buggy Color Calculation
  cfr. reversed fade in/out for dokyuif title transition,
  shienryu stage 2 background colors on statues (caused by special color
calculation usage, per dot ...), scud zoom-in on melee attacks with pink
backgrounds (TODO: reinvestigate this), dinoisl;
- Incomplete/buggy window effects
  cfr. gpanicss gal select, one of the Wangan games (TODO: find which),
  cknight2j bugged map transition;
- VRAM cycle pattern section needs to be better encapsulated and investigated
thru real HW also cfr. several "minor GFX" glitches scattered across, kingbox on
gameplay, columns Sega Ages logo;
- Missing mosaic effect
  cfr. Saturn BIOS memory screens, capgen2 Choh Makai Mura map transitions
(obviously);
- Per-scanline raster effects, at very least Color Offset section is eligible to
those cfr. elevact2, ogrebatl, probably htheros missing crowd;
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
- gekkakis gameplay enables undocumented BGON bit 6 as an alias for text layer
(currently hidden), investigate;
- Back layer isn't drawn in biohaz, investigate;
- Bogus Title Screen blinking for vhydlid and probably other T&E Soft games,
investigate;
- Verify batmanfr crashing before final boss (assuming it's reproducible),
  prime suspect VDP2 overrunning a buffer on the complicated ROZ setup it does
for Riddler screen;
- Verify hanagumi ending (there are sources sporting bad tiles, it's most likely
fixed a long time ago);
- Verify rsgun Xiga final boss implications with rotation read controls
  (should still be wrong as per current);
- Verify sandor (STV) martial artist dry towel sub-game (overall screen setup
looked wrong, saw from a thuntk playthrough with unknown MAME version used);


**************************************************************************************************/
/*

STV - VDP1

the vdp1 draws to the FRAMEBUFFER which is mapped in memory

-------------------------- WARNING WARNING WARNING --------------------------
This is a legacy core, all game based notes are for a future device rewrite.
Please don't remove them if for no reason you truly want to mess with this.
-------------------------- WARNING WARNING WARNING --------------------------

Framebuffer TODO:
- qualify scanline-level manual/one-cycle erase against hardware
- implement within-raster erase/readout/CPU bus arbitration
- packed 8-bit storage, interlace fields and rotated readout are implemented;
  verify remaining erase/transfer timing against hardware

*/

#include "emu.h"
#include "emuopts.h"
#include "saturn.h"


#include "cpu/scudsp/scudsp.h"

#include "input.h" // for video debug keys

#define LOG_VDP2 (1U << 1)
#define LOG_ROZ (1U << 2)

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

struct shaded_point {
  int32_t x, y;
  int32_t r, g, b;
};

constexpr uint16_t RGB_R(uint16_t color) { return color & 0x1f; }
constexpr uint16_t RGB_G(uint16_t color) { return (color >> 5) & 0x1f; }
constexpr uint16_t RGB_B(uint16_t color) { return (color >> 10) & 0x1f; }

} // anonymous namespace

void saturn_state::machine_start() {
  save_item(NAME(m_system_halt));
  save_item(NAME(m_main_dma_halt));
  save_item(NAME(m_sound_dma_halt));
  machine().save().register_postload(save_prepost_delegate(
      FUNC(saturn_state::update_halt_lines), this));
}

void saturn_state::reset_halt_state() {
  m_system_halt = m_main_dma_halt = m_sound_dma_halt = false;
  update_halt_lines();
}

void saturn_state::machine_reset() {
  vdp2_reset_rotation_latches();
  vdp1_reset_framebuffers();
  vdp1_abort_draw();
  vdp1_cancel_erase();
  reset_halt_state();
  m_scsp_last_line = 0;

  // don't let the slave cpu and the 68k go anywhere
  m_slave->set_input_line(INPUT_LINE_RESET, ASSERT_LINE);
  m_audiocpu->set_input_line(INPUT_LINE_RESET, ASSERT_LINE);

  m_maincpu->set_unscaled_clock(MASTER_CLOCK_320 / 2);
  m_slave->set_unscaled_clock(MASTER_CLOCK_320 / 2);

  m_en_68k = 0;

  m_vdp2_legacy.old_crmd = -1;

  // rebuild the faded palette tables for the new frame
  mark_fade_effects_dirty();
}

void saturn_state::soundram_w(offs_t offset, uint16_t data, uint16_t mem_mask) {
  // machine().scheduler().synchronize(); // force resync

  COMBINE_DATA(&m_sound_ram[offset]);
}

uint16_t saturn_state::soundram_r(offs_t offset) {
  // machine().scheduler().synchronize(); // force resync

  return m_sound_ram[offset];
}

uint8_t saturn_state::backupram_r(offs_t offset) {
  if (!(offset & 1))
    return 0; // yes, it makes sure the "holes" are there.

  return m_backupram[offset >> 1] & 0xff;
}

void saturn_state::backupram_w(offs_t offset, uint8_t data) {
  if (!(offset & 1))
    return;

  m_backupram[offset >> 1] = data;
}

void saturn_state::m68k_reset_callback(int state) {
  logerror("m68k RESET opcode triggered\n");
  m_smpc_hle->m68k_reset_trigger();
}

void saturn_state::scsp_irq(offs_t offset, uint8_t data) {
  // SNDON/SNDOFF control the 68000 RESET input, not the SCSP's IPL
  // output. Keep tracking both assertions and clears while reset is held:
  // the SCSP reports level changes, so dropping one here can leave a lost
  // or stale interrupt after SNDON without another transition to repair it.

  if (offset != 0) {
    if (data == ASSERT_LINE)
      m_scsp_last_line = offset;
    m_audiocpu->set_input_line(offset, data);
  } else {
    m_audiocpu->set_input_line(m_scsp_last_line, data);
  }
}

/*
(Preliminary) explanation about this:
VBLANK-OUT is used at the start of the vblank period. It also sets the timer
zero variable to 0. If the Timer Compare register is zero too,the Timer 0 irq is
triggered.

HBLANK-IN is used at the end of each scanline except when in VBLANK-IN/OUT
periods.

The timer 0 is also incremented by one at each HBLANK and checked with the value
of the Timer Compare register;if equal,the timer 0 irq is triggered here too.
Notice that the timer 0 compare register can be more than the VBLANK maximum
range,in this case the timer 0 irq is simply never triggered.This is a known
Sega Saturn/ST-V "bug".

VBLANK-IN is used at the end of the vblank period.

SCU register[36] is the timer zero compare register.
SCU register[40] is for IRQ masking.

TODO:
- VDP1 timing and CEF emulation isn't accurate at all.
*/

void saturn_state::vint_callback(int state) {
  if (m_prev_vint != state) {
    if (state) {
      m_scu->vblank_in_w(1);
      m_slave->set_input_line(0x6, ASSERT_LINE);
    } else {
      m_scu->vblank_out_w(1);
      m_slave->set_input_line(0x4, ASSERT_LINE);
    }
  }

  m_prev_vint = state;
}

void saturn_state::hint_callback(int state) {
  if (!m_prev_hint && state) {
    m_scu->hblank_in_w(1);
    // The SCU still receives HBlank during VBlank (timers and DMA), but
    // the slave SH-2 horizontal interrupt is gated by vertical blanking.
    if (!m_prev_vint)
      m_slave->set_input_line(0x2, ASSERT_LINE);
  } else if (m_prev_hint && !state && !m_prev_vint) {
    // Essentially clears?
    m_slave->set_input_line(0x0, ASSERT_LINE);
  }

  m_prev_hint = state;
}

// TODO: stuff that should really be in VDP1
TIMER_DEVICE_CALLBACK_MEMBER(saturn_state::saturn_scanline) {
  int scanline = param;
  vdp2_latch_rotation_parameters(scanline);
  int y_step, vblank_line;

  vblank_line = m_vdp2->get_vblank_start_position();
  y_step = m_vdp2->get_ystep_count();

  // popmessage("%08x %d T0 %d T1 %d %08x",m_scu.ism ^
  // 0xffffffff,max_y,m_scu_regs[36],m_scu_regs[37],m_scu_regs[38]);

  // Bank change and automatic drawing follow VBlank OUT, not VBlank IN.
  // VDP2's screen coordinate zero is the field-start transition.
  if (scanline == 0)
    vdp1_video_update();
  else
    vdp1_advance_display_erase(scanline);

  if (scanline == (vblank_line + 1) * y_step &&
      (VDP1_VBE() || m_vdp1_legacy.vblank_erase_pending))
    vdp1_begin_vblank_erase();
  else if (scanline && m_vdp1_legacy.vblank_erase_active &&
           scanline % m_vdp1_legacy.vblank_erase_step == 0)
    vdp1_advance_vblank_erase(m_vdp1_legacy.vblank_erase_words_per_line);
}

static const gfx_layout tiles8x8x4_layout = {
    8,
    8,
    0x100000 / (32 * 8 / 8),
    4,
    {0, 1, 2, 3},
    {0, 4, 8, 12, 16, 20, 24, 28},
    {0 * 32, 1 * 32, 2 * 32, 3 * 32, 4 * 32, 5 * 32, 6 * 32, 7 * 32},
    32 * 8};

static const gfx_layout tiles16x16x4_layout = {
    16,
    16,
    0x100000 / (32 * 32 / 8),
    4,
    {0, 1, 2, 3},
    {
        0,
        4,
        8,
        12,
        16,
        20,
        24,
        28,
        32 * 8 + 0,
        32 * 8 + 4,
        32 * 8 + 8,
        32 * 8 + 12,
        32 * 8 + 16,
        32 * 8 + 20,
        32 * 8 + 24,
        32 * 8 + 28,

    },
    {0 * 32, 1 * 32, 2 * 32, 3 * 32, 4 * 32, 5 * 32, 6 * 32, 7 * 32, 32 * 16,
     32 * 17, 32 * 18, 32 * 19, 32 * 20, 32 * 21, 32 * 22, 32 * 23

    },
    32 * 32};

static const gfx_layout tiles8x8x8_layout = {
    8,
    8,
    0x100000 / (32 * 8 / 8),
    8,
    {0, 1, 2, 3, 4, 5, 6, 7},
    {0, 8, 16, 24, 32, 40, 48, 56},
    {0 * 64, 1 * 64, 2 * 64, 3 * 64, 4 * 64, 5 * 64, 6 * 64, 7 * 64},
    32 * 8 /* really 64*8, but granularity is 32 bytes */
};

static const gfx_layout tiles16x16x8_layout = {
    16,
    16,
    0x100000 / (64 * 16 / 8),
    8,
    {0, 1, 2, 3, 4, 5, 6, 7},
    {0, 8, 16, 24, 32, 40, 48, 56, 64 * 8 + 0, 65 * 8, 66 * 8, 67 * 8, 68 * 8,
     69 * 8, 70 * 8, 71 * 8

    },
    {0 * 64, 1 * 64, 2 * 64, 3 * 64, 4 * 64, 5 * 64, 6 * 64, 7 * 64, 64 * 16,
     64 * 17, 64 * 18, 64 * 19, 64 * 20, 64 * 21, 64 * 22, 64 * 23},
    64 * 16 /* really 128*16, but granularity is 32 bytes */
};

GFXDECODE_START(gfx_stv)
GFXDECODE_ENTRY(nullptr, 0, tiles8x8x4_layout, 0x00, (0x80 * (2 + 1)))
GFXDECODE_ENTRY(nullptr, 0, tiles16x16x4_layout, 0x00, (0x80 * (2 + 1)))
GFXDECODE_ENTRY(nullptr, 0, tiles8x8x8_layout, 0x00, (0x08 * (2 + 1)))
GFXDECODE_ENTRY(nullptr, 0, tiles16x16x8_layout, 0x00, (0x08 * (2 + 1)))
GFXDECODE_END

void saturn_state::master_sh2_reset_w(int state) {
  m_maincpu->set_input_line(INPUT_LINE_RESET, state ? ASSERT_LINE : CLEAR_LINE);
}

void saturn_state::master_sh2_nmi_w(int state) {
  m_maincpu->set_input_line(INPUT_LINE_NMI, state ? ASSERT_LINE : CLEAR_LINE);
}

void saturn_state::slave_sh2_reset_w(int state) {
  m_slave->set_input_line(INPUT_LINE_RESET, state ? ASSERT_LINE : CLEAR_LINE);
  //  m_smpc.slave_on = state;
}

void saturn_state::sound_68k_reset_w(int state) {
  m_audiocpu->set_input_line(INPUT_LINE_RESET,
                             state ? ASSERT_LINE : CLEAR_LINE);
  m_en_68k = state ^ 1;
}

// TODO: edge triggered?
void saturn_state::system_reset_w(int state) {
  if (!state)
    return;

  // TODO: actually send a device reset signal to the connected devices
  /*Only backup ram and SMPC ram are retained after that this command is
   * issued.*/
  m_scu->reset();
  vdp1_abort_draw();
  vdp1_cancel_erase();
  vdp1_reset_framebuffers();
  memset(m_sound_ram, 0x00, 0x080000);
  memset(m_workram_h, 0x00, 0x100000);
  memset(m_workram_l, 0x00, 0x100000);
  vdp2_reset_rotation_latches();
  memset(m_vdp2_regs.get(), 0x00, 0x000200);
  memset(m_vdp2_vram.get(), 0x00, 0x100000);
  memset(m_vdp2_cram.get(), 0x00, 0x001000);
  memset(m_vdp1_vram.get(), 0x00, 0x100000);
  // A-Bus

  // CRAM and the color offset registers were cleared behind the VDP2's back
  mark_fade_effects_dirty();
  vdp2_window_cache_invalidate();
}

// SMPC clock switching and SCU stalls share CPU HALT inputs.  Releasing
// one source must not release a CPU still held by the other source.
void saturn_state::update_halt_lines() {
  const bool main_halt = m_system_halt || m_main_dma_halt;
  const bool sound_halt = m_system_halt || m_sound_dma_halt;
  m_maincpu->set_input_line(INPUT_LINE_HALT, main_halt ? ASSERT_LINE : CLEAR_LINE);
  m_slave->set_input_line(INPUT_LINE_HALT, main_halt ? ASSERT_LINE : CLEAR_LINE);
  m_audiocpu->set_input_line(INPUT_LINE_HALT, sound_halt ? ASSERT_LINE : CLEAR_LINE);
}

void saturn_state::system_halt_w(int state) {
  m_system_halt = bool(state);
  update_halt_lines();
}

void saturn_state::main_dma_halt_w(int state) {
  m_main_dma_halt = bool(state);
  update_halt_lines();
}

void saturn_state::sound_dma_halt_w(int state) {
  m_sound_dma_halt = bool(state);
  update_halt_lines();
}

void saturn_state::dot_select_w(int state) {
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
   This sets the Frame Buffer size,the rotation of the Frame Buffer & the bit
   width. bit 2 HDTV disable(0)/enable(1) bit 1 non-rotation/rotation(1) bit 0
   16(0)/8(1) bits per pixel Size of the Frame Buffer: 7 invalid 6 invalid 5
   invalid 4 512x256 3 512x512 2 512x256 1 1024x256 0 512x256
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
#define VDP1_FBCR ((m_vdp1_regs[0x002 / 2] >> 0) & 0xffff)
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
#define VDP1_PTMR ((m_vdp1_regs[0x004 / 2]) & 0xffff)
#define VDP1_PTM ((VDP1_PTMR & 0x0003) >> 0)
#define PTM_0 m_vdp1_regs[0x004 / 2] &= ~0x0001

/*
    Erase/Write Data Register
    16 bpp = data
    8 bpp = erase/write data for even/odd X coordinates
*/
#define VDP1_EWDR ((m_vdp1_regs[0x006 / 2]) & 0xffff)

/*Erase/Write Upper-Left register*/
/*
   x--- ---- ---- ---- | UNUSED
   -xxx xxx- ---- ---- | X1 register
   ---- ---x xxxx xxxx | Y1 register

*/
#define VDP1_EWLR ((m_vdp1_regs[0x008 / 2]) & 0xffff)
#define VDP1_EWLR_X1 ((VDP1_EWLR & 0x7e00) >> 9)
#define VDP1_EWLR_Y1 ((VDP1_EWLR & 0x01ff) >> 0)
/*Erase/Write Lower-Right register*/
/*
   xxxx xxx- ---- ---- | X3 register
   ---- ---x xxxx xxxx | Y3 register

*/
#define VDP1_EWRR ((m_vdp1_regs[0x00a / 2]) & 0xffff)
#define VDP1_EWRR_X3 ((VDP1_EWRR & 0xfe00) >> 9)
#define VDP1_EWRR_Y3 ((VDP1_EWRR & 0x01ff) >> 0)
/*Transfer End Status Register*/
/*
   xxxx xxxx xxxx xx-- | UNUSED
   ---- ---- ---- --x- | CEF
   ---- ---- ---- ---x | BEF

*/
#define VDP1_EDSR ((m_vdp1_regs[0x010 / 2]) & 0xffff)
#define VDP1_CEF (VDP1_EDSR & 2)
#define VDP1_BEF (VDP1_EDSR & 1)
/**/

uint16_t saturn_state::vdp1_regs_r(offs_t offset) {
  // logerror ("%s VDP1: Read from Registers, Offset %04x\n",
  // machine().describe_context(), offset);

  switch (offset) {
  case 0x02 / 2:
    return 0;
  case 0x10 / 2:
    break;
  case 0x12 / 2:
    return m_vdp1_legacy.lopr;
  case 0x14 / 2:
    return m_vdp1_legacy.copr;
  /* MODR register, read register for the other VDP1 regs
     (Shienryu SS version abuses of this during intro) */
  case 0x16 / 2:
    uint16_t modr;

    modr = 0x1000;                // vdp1 VER
    modr |= (VDP1_PTM >> 1) << 8; // PTM1
    modr |= VDP1_EOS << 7;        // EOS
    modr |= VDP1_DIE << 6;        // DIE
    modr |= VDP1_DIL << 5;        // DIL
    modr |= VDP1_FCM << 4;        // FCM
    modr |= VDP1_VBE() << 3;      // VBE
    modr |= VDP1_TVM() & 7;       // TVM

    return modr;
  default:
    if (!machine().side_effects_disabled())
      logerror("%s VDP1: Read from Registers, Offset %04x\n",
               machine().describe_context(), offset * 2);
    break;
  }

  return m_vdp1_regs[offset]; // TODO: write-only regs should return open bus or
                              // zero
}

// Opt-in regression diagnostics: use -verbose -log and capture a short run.
// This is observational only; never alter emulated timing or register state.
// Debug-only raw RAM inspection: never access MMIO, advance a peripheral,
// or use the CPU address-space handlers (which may charge bus wait states).
bool saturn_state::boot_trace_word(u32 address, bool sound, u16 &word) {
  if (sound) {
    if (address >= 0x00080000)
      return false; // uninstalled expansion area is not a sound-CPU RAM alias
    word = m_sound_ram[address >> 1];
    return true;
  }
  if (address >= 0x40000000)
    return false; // cache arrays/purge space are not physical RAM aliases
  address &= 0x1fffffff; // SH-2 cache-through alias
  if (address >= 0x06000000 && address < 0x08000000) {
    word = m_workram_h[(address & 0xfffff) >> 2] >> ((address & 2) ? 0 : 16);
    return true;
  }
  if (address >= 0x00200000 && address < 0x00300000) {
    word = m_workram_l[(address & 0xfffff) >> 2] >> ((address & 2) ? 0 : 16);
    return true;
  }
  if (address >= 0x05a00000 && address < 0x05b00000) {
    word = m_sound_ram[(address & 0x7ffff) >> 1];
    return true;
  }
  return false;
}

void saturn_state::trace_boot_cpu() {
  if (!machine().options().verbose())
    return;
  const int64_t second = machine().time().seconds();
  if (m_boot_trace_second == second)
    return;
  m_boot_trace_second = second;
  logerror("BOOTCPU t=%s mainpc=%08x sr=%08x pr=%08x soundpc=%08x soundsr=%04x "
           "soundsp=%08x soundcycles=%llu enabled=%d lastirq=%d "
           "soundreset=%d soundhalt=%d systemhalt=%d dmahalt=%d\n",
           machine().time().as_string(), u32(m_maincpu->pc()),
           u32(m_maincpu->state_int(SH_SR)), u32(m_maincpu->state_int(SH4_PR)),
           u32(m_audiocpu->pc()), u32(m_audiocpu->state_int(M68K_SR)),
           u32(m_audiocpu->state_int(M68K_SP)),
           (unsigned long long)m_audiocpu->total_cycles(), m_en_68k, m_scsp_last_line,
           m_audiocpu->suspended(SUSPEND_REASON_RESET),
           m_audiocpu->suspended(SUSPEND_REASON_HALT), m_system_halt, m_sound_dma_halt);
  for (unsigned sound = 0; sound < 2; ++sound) {
    const u32 pc = sound ? m_audiocpu->pc() : m_maincpu->pc();
    const u32 base = pc & ~u32(15);
    logerror("BOOTCPU %s code @%08x:", sound ? "sound" : "main", base);
    for (unsigned i = 0; i < 16; ++i) {
      u16 word;
      if (boot_trace_word(base + i * 2, sound, word))
        logerror(" %04x", word);
      else
        logerror(" ----");
    }
    logerror("\n");
  }
  for (unsigned i = 0; i < 16; ++i) {
    const u32 value = m_maincpu->state_int(SH4_R0 + i);
    logerror("BOOTCPU R%u=%08x ram @%08x:", i, value, value & ~u32(1));
    for (unsigned j = 0; j < 4; ++j) {
      u16 word;
      if (boot_trace_word((value & ~u32(1)) + j * 2, false, word))
        logerror(" %04x", word);
      else
        logerror(" ----");
    }
    logerror("\n");
  }
}

void saturn_state::vdp1_trace(const char *event, int reg, const spoint *bounds) {
  if (!machine().options().verbose())
    return;
  if (!strcmp(event, "field"))
    trace_boot_cpu();
  const auto &v = m_vdp1_legacy;
  logerror("VDP1TRACE t=%s event=%s TVMR=%04x FBCR=%04x PTMR=%04x EDSR=%04x "
           "draw=%d display=%d busy=%d COPR=%04x LOPR=%04x pc=%04x "
           "span=%d/%d dot=%d HRESO=%u LSMD=%u width=%d height=%d DIE=%d DIL=%u\n",
           machine().time().as_string(), event, m_vdp1_regs[0], m_vdp1_regs[1],
           m_vdp1_regs[2], m_vdp1_regs[8], v.framebuffer_current_draw,
           v.framebuffer_current_display, v.drawing, v.copr, v.lopr, v.command_position,
           m_vdp1_raster.index, m_vdp1_raster.count, m_vdp1_raster.dot,
           m_vdp2->get_hreso(), m_vdp2->get_lsmd(), v.framebuffer_width,
           v.framebuffer_height, v.framebuffer_double_interlace, v.draw_field);
  if (!strcmp(event, "field")) {
    const auto rp = vdp1_rotation_parameters();
    logerror("VDP1TRACE readout RPTA=%04x:%04x A=%08x,%08x,%08x,%08x,%08x,%08x "
             "SPCTL=%04x BGON=%04x CHCTLA=%04x "
             "N0SC=%04x:%04x,%04x:%04x N0Z=%04x:%04x,%04x:%04x "
             "N1SC=%04x:%04x,%04x:%04x N1Z=%04x:%04x,%04x:%04x\n",
             m_vdp2_regs[0xbc / 2], m_vdp2_regs[0xbe / 2],
             rp[0], rp[1], rp[2], rp[3], rp[4], rp[5],
             m_vdp2_regs[0xe0 / 2], m_vdp2_regs[0x20 / 2], m_vdp2_regs[0x28 / 2],
             m_vdp2_regs[0x70 / 2], m_vdp2_regs[0x72 / 2],
             m_vdp2_regs[0x74 / 2], m_vdp2_regs[0x76 / 2],
             m_vdp2_regs[0x78 / 2], m_vdp2_regs[0x7a / 2],
             m_vdp2_regs[0x7c / 2], m_vdp2_regs[0x7e / 2],
             m_vdp2_regs[0x80 / 2], m_vdp2_regs[0x82 / 2],
             m_vdp2_regs[0x84 / 2], m_vdp2_regs[0x86 / 2],
             m_vdp2_regs[0x88 / 2], m_vdp2_regs[0x8a / 2],
             m_vdp2_regs[0x8c / 2], m_vdp2_regs[0x8e / 2]);
  }
  if (reg >= 0)
    logerror("VDP1TRACE register offset=%02x value=%04x\n", reg * 2, m_vdp1_regs[reg]);
  if (bounds) {
    const auto &c = current_sprite;
    logerror("VDP1TRACE %s COPR=%04x CTRL=%04x PMOD=%04x COLR=%04x SRCA=%04x SIZE=%04x "
             "A=(%04x,%04x) B=(%04x,%04x) C=(%04x,%04x) local=(%d,%d) "
             "bounds=(%d,%d)-(%d,%d) destination=%dx%d source=%dx%d\n",
             event, v.copr, c.CMDCTRL, c.CMDPMOD, c.CMDCOLR, c.CMDSRCA, c.CMDSIZE,
             c.CMDXA, c.CMDYA, c.CMDXB, c.CMDYB, c.CMDXC, c.CMDYC,
             v.local_x, v.local_y, bounds[0].x, bounds[0].y, bounds[2].x, bounds[2].y,
             std::abs(bounds[2].x - bounds[0].x) + 1,
             std::abs(bounds[2].y - bounds[0].y) + 1,
             ((c.CMDSIZE >> 8) & 63) * 8, c.CMDSIZE & 255);
  }
}

// Nominal progress per physical raster from ST-013 Table 4.4 / p.49.
uint32_t saturn_state::vdp1_vblank_erase_line_capacity() const {
  const unsigned hreso = m_vdp2->get_hreso();
  const int clocks = (hreso & 4) ? ((hreso & 1) ? 848 : 852) : ((hreso & 1) ? 1820 : 1708);
  return clocks - 200;
}

// VBlank erase has a finite field budget, independent of command drawing.
uint32_t saturn_state::vdp1_vblank_erase_capacity() const {
  // ST-013 pp.49-50, Tables 4.4/4.5. X erase coordinates count groups of
  // eight framebuffer words (sixteen dots in 8-bit modes). The available
  // budget therefore counts words, not packed dots or register X units.
  const unsigned hreso = m_vdp2->get_hreso();
  const bool exclusive = hreso & 4;
  const int field_rasters = exclusive ? ((hreso & 1) ? 562 : 525) :
      (m_vdp2->is_pal() ? 313 : 263);
  const int display_rasters = exclusive ? 480 : m_vdp2->get_vblank_start_position() - 1;
  return vdp1_vblank_erase_line_capacity() * std::max(0, field_rasters - display_rasters);
}

void saturn_state::vdp1_begin_vblank_erase() {
  auto &v = m_vdp1_legacy;
  v.vblank_erase_pending = false;
  v.vblank_erase_active = true;
  v.vblank_erase_bank = v.framebuffer_current_display;
  v.vblank_erase_stride = VDP1_TVM() == 3 ? 256 : 512;
  v.vblank_erase_data = v.ewdr;
  v.vblank_erase_left = ((v.erase_upper_left >> 9) & 0x3f) * 8;
  v.vblank_erase_right = ((v.erase_lower_right >> 9) & 0x7f) * 8;
  v.vblank_erase_top = v.erase_upper_left & 0x1ff;
  v.vblank_erase_bottom = v.erase_lower_right & 0x1ff;
  v.vblank_erase_budget = vdp1_vblank_erase_capacity();
  v.vblank_erase_x = v.vblank_erase_left;
  v.vblank_erase_y = v.vblank_erase_top;
  v.vblank_erase_words_per_line = vdp1_vblank_erase_line_capacity();
  // Interlaced screen coordinates have two output rows per physical raster;
  // exclusive 31-kHz/HDTV output has one, regardless of LSMD.
  v.vblank_erase_step = (m_vdp2->get_hreso() & 4) ? 1 : m_vdp2->get_ystep_count();
}

void saturn_state::vdp1_advance_vblank_erase(uint32_t words) {
  auto &v = m_vdp1_legacy;
  if (!v.vblank_erase_active)
    return;
  if (v.vblank_erase_left >= v.vblank_erase_right ||
      v.vblank_erase_y > v.vblank_erase_bottom) {
    v.vblank_erase_active = false;
    return;
  }
  unsigned remaining = std::min(words, v.vblank_erase_budget);
  while (remaining && v.vblank_erase_y <= v.vblank_erase_bottom) {
    const unsigned address = ((v.vblank_erase_y * v.vblank_erase_stride) +
        (v.vblank_erase_x & (v.vblank_erase_stride - 1))) & 0x1ffff;
    v.framebuffer[v.vblank_erase_bank][address] = v.vblank_erase_data;
    --remaining;
    --v.vblank_erase_budget;
    if (++v.vblank_erase_x == v.vblank_erase_right) {
      v.vblank_erase_x = v.vblank_erase_left;
      ++v.vblank_erase_y;
    }
  }
  if (!v.vblank_erase_budget || v.vblank_erase_y > v.vblank_erase_bottom)
    v.vblank_erase_active = false;
}

void saturn_state::vdp1_finish_vblank_erase() {
  // Flush only the residual published field budget before bank exchange.
  // Scanline callbacks expose progress during blanking; the existing VBlank
  // edge convention can leave a few raster quotas here. This remains a
  // scanline model, not exact within-raster CPU/erase bus arbitration.
  vdp1_advance_vblank_erase(m_vdp1_legacy.vblank_erase_budget);
  m_vdp1_legacy.vblank_erase_active = false;
}

void saturn_state::vdp1_begin_display_erase() {
  auto &e = m_vdp1_display_erase;
  const auto &v = m_vdp1_legacy;
  e.pending = true;
  e.bank = v.framebuffer_current_display;
  e.data = v.ewdr;
  e.left = ((v.erase_upper_left >> 9) & 0x3f) * 8;
  e.right = ((v.erase_lower_right >> 9) & 0x7f) * 8;
  e.top = v.erase_upper_left & 0x1ff;
  e.bottom = v.erase_lower_right & 0x1ff;
  // ST-013 p.49: erase follows display readout, with only four extra
  // words (four 16-bit dots / eight packed dots) after active horizontal data.
  e.right = std::min<unsigned>(e.right, ((m_vdp2->get_hreso() & 1) ? 352 : 320) + 4);
  e.bottom = std::min<unsigned>(e.bottom, m_vdp2->get_vblank_start_position() - 2);
  e.next_row = e.top;
  e.step = m_vdp2->get_ystep_count();
  vdp1_trace("display-erase-begin");
}

void saturn_state::vdp1_advance_display_erase(int scanline) {
  auto &e = m_vdp1_display_erase;
  if (!e.pending || scanline <= 0)
    return;
  if (e.left >= e.right || e.next_row > e.bottom) {
    e.pending = false;
    return;
  }
  // At the start of the next physical raster, both output rows of an
  // interlaced raster must have been presented before its stored row is erased.
  const unsigned completed_rows = unsigned(scanline) / e.step;
  if (e.next_row >= completed_rows)
    return;
  const unsigned last_row = std::min<unsigned>(e.bottom, completed_rows - 1);
  m_screen->update_partial((last_row + 1) * e.step - 1);
  for (; e.next_row <= last_row; ++e.next_row)
    for (unsigned x = e.left; x < e.right; ++x)
      m_vdp1_legacy.framebuffer[e.bank][(e.next_row & 255) * 512 + (x & 511)] = e.data;
  if (e.next_row > e.bottom) {
    e.pending = false;
    vdp1_trace("display-erase-end");
  }
}

void saturn_state::vdp1_finish_display_erase() {
  // Field end must not erase unscanned rows or replay an already erased prefix.
  // Normal scheduler execution presents/erases eligible rows during display.
  m_vdp1_display_erase.pending = false;
}

void saturn_state::vdp1_cancel_erase() {
  m_vdp1_display_erase.pending = false;
  m_vdp1_legacy.vblank_erase_active = false;
  m_vdp1_legacy.vblank_erase_pending = false;
}

// Daisenryaku Strong Style (daisenss) uses erase/write.
void saturn_state::vdp1_clear_framebuffer(int which_framebuffer) {
  int start_x, end_x, start_y, end_y;

  start_x = ((m_vdp1_legacy.erase_upper_left >> 9) & 0x3f) * ((VDP1_TVM() & 1) ? 16 : 8);
  // Erase Y registers address stored field rows. DIE doubles the logical
  // coordinate but halves it again for the physical bank (ST-013 p.47-49).
  start_y = (m_vdp1_legacy.erase_upper_left & 0x1ff);
  end_x = ((m_vdp1_legacy.erase_lower_right >> 9) & 0x7f) * ((VDP1_TVM() & 1) ? 16 : 8);
  end_y = (m_vdp1_legacy.erase_lower_right & 0x1ff) + 1;
  //  popmessage("%d %d %d %d
  //  %d",((m_vdp1_legacy.erase_upper_left >> 9) & 0x3f),(m_vdp1_legacy.erase_upper_left & 0x1ff),((m_vdp1_legacy.erase_lower_right >> 9) & 0x7f),(m_vdp1_legacy.erase_lower_right & 0x1ff),m_vdp1_legacy.framebuffer_double_interlace);

  if (VDP1_TVM() & 1) {
    // EWDR supplies the even/odd byte pair. Erase X units are 16 dots, so
    // boundaries are word-aligned in both high-resolution and rotation-8.
    const unsigned width = (VDP1_TVM() == 3) ? 512 : 1024;
    const unsigned stride = width / 2;
    for (int y = start_y; y < end_y; y++)
      for (int x = start_x; x < end_x; x += 2)
        m_vdp1_legacy.framebuffer[which_framebuffer]
            [(((y * stride) + ((x & (width - 1)) >> 1)) & 0x1ffff)] =
            m_vdp1_legacy.ewdr;
  } else {
    for (int y = start_y; y < end_y; y++)
      for (int x = start_x; x < end_x; x++)
        m_vdp1_legacy
            .framebuffer[which_framebuffer][((x & 511) + (y & 255) * 512)] =
            m_vdp1_legacy.ewdr;
  }

  if (VDP1_LOG)
    logerror("Clearing %d framebuffer\n",
             m_vdp1_legacy.framebuffer_current_draw);
  //  memset( m_vdp1_legacy.framebuffer[ which_framebuffer ],
  //  m_vdp1_legacy.ewdr, 1024 * 256 * sizeof(uint16_t) * 2 );
}

void saturn_state::vdp1_reset_framebuffers() {
  // ST-013 p.20 defines bank zero as drawing and bank one as display after
  // reset. Reset ownership/views without inventing a framebuffer RAM clear.
  m_vdp1_legacy.framebuffer_current_draw = 0;
  m_vdp1_legacy.framebuffer_current_display = 1;
  m_vdp1_legacy.field_valid[0] = m_vdp1_legacy.field_valid[1] = false;
  m_vdp1_legacy.draw_field = 0;
  if (m_vdp1_legacy.framebuffer_draw_lines && m_vdp1_legacy.framebuffer_display_lines)
    vdp1_prepare_framebuffers();
}

void saturn_state::vdp1_prepare_framebuffers() {
  const unsigned stride = m_vdp1_legacy.framebuffer_width >> (m_vdp1_legacy.framebuffer_mode & 1);
  const bool interlace = m_vdp1_legacy.framebuffer_double_interlace > 0;
  for (unsigned y = 0; y < 512; ++y) {
    // Each bank is 2 Mbit. Double interlace stores just one field, not an
    // oversized 512-line bank; the other parity is drawn into the other bank.
    const unsigned row = interlace ? y >> 1 : y;
    const unsigned offset = (row * stride) & 0x1ffff;
    m_vdp1_legacy.framebuffer_draw_lines[y] =
        m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw].get() + offset;
    m_vdp1_legacy.framebuffer_display_lines[y] =
        m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_display].get() + offset;
  }
}

void saturn_state::vdp1_change_framebuffers() {
  vdp1_trace("swap-before");
  if (m_vdp1_legacy.framebuffer_double_interlace > 0) {
    // Weave completed display fields for MAME's full-frame bitmap. Never read
    // the bank currently being drawn to as though it were the previous field.
    const unsigned field = m_vdp1_legacy.draw_field & 1;
    std::copy_n(m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw].get(),
                0x20000, m_vdp1_legacy.field_framebuffer[field].get());
    m_vdp1_legacy.field_valid[field] = true;
  }
  // ST-013 p.43: DIL selects drawing after the next framebuffer change.
  vdp1_latch_framebuffer_config();
  // BEF records the previous drawing bank, not every VBlank callback.
  // In manual mode a VBlank without a bank change must leave it latched.
  if (VDP1_CEF)
    BEF_1();
  else
    BEF_0();
  // ST-013 section 4.7: latch the current command address on bank change.
  m_vdp1_legacy.lopr = m_vdp1_legacy.copr;
  m_vdp1_legacy.framebuffer_current_display ^= 1;
  m_vdp1_legacy.framebuffer_current_draw ^= 1;
  // "this bit is reset to 0 when the frame buffers are changed"
  CEF_0();
  if (VDP1_LOG)
    logerror("Changing framebuffers: %d - draw, %d - display\n",
             m_vdp1_legacy.framebuffer_current_draw,
             m_vdp1_legacy.framebuffer_current_display);
  vdp1_prepare_framebuffers();
  vdp1_trace("swap-after");
}

void saturn_state::vdp1_latch_framebuffer_config() {
  // ST-013 p.35: these drawing/erase settings take effect on bank change.
  const bool geometry_changed = m_vdp1_legacy.framebuffer_double_interlace != VDP1_DIE;
  m_vdp1_legacy.framebuffer_double_interlace = VDP1_DIE;
  m_vdp1_legacy.draw_field = VDP1_DIL;
  m_vdp1_legacy.draw_eos = VDP1_EOS;
  m_vdp1_legacy.ewdr = VDP1_EWDR;
  m_vdp1_legacy.erase_upper_left = m_vdp1_regs[4];
  m_vdp1_legacy.erase_lower_right = m_vdp1_regs[5];
  if (geometry_changed) {
    m_vdp1_legacy.framebuffer_mode = -1;
    vdp1_set_framebuffer_config();
  }
}

void saturn_state::vdp1_set_framebuffer_config() {
  if (m_vdp1_legacy.framebuffer_mode == VDP1_TVM())
    return;

  if (VDP1_LOG)
    logerror("Setting framebuffer config\n");
  m_vdp1_legacy.field_valid[0] = m_vdp1_legacy.field_valid[1] = false;
  m_vdp1_legacy.framebuffer_mode = VDP1_TVM();
  if (m_vdp1_legacy.framebuffer_double_interlace < 0)
    m_vdp1_legacy.framebuffer_double_interlace = 0;
  switch (m_vdp1_legacy.framebuffer_mode) {
  case 0:
    m_vdp1_legacy.framebuffer_width = 512;
    m_vdp1_legacy.framebuffer_height = 256;
    break;
  case 1:
    m_vdp1_legacy.framebuffer_width = 1024;
    m_vdp1_legacy.framebuffer_height = 256;
    break;
  case 2:
    m_vdp1_legacy.framebuffer_width = 512;
    m_vdp1_legacy.framebuffer_height = 256;
    break;
  case 3:
    m_vdp1_legacy.framebuffer_width = 512;
    m_vdp1_legacy.framebuffer_height = 512;
    break;
  case 4:
    m_vdp1_legacy.framebuffer_width = 512;
    m_vdp1_legacy.framebuffer_height = 256;
    break;
  default:
    logerror("Invalid framebuffer config %x\n", VDP1_TVM());
    m_vdp1_legacy.framebuffer_width = 512;
    m_vdp1_legacy.framebuffer_height = 256;
    break;
  }
  if (m_vdp1_legacy.framebuffer_double_interlace)
    m_vdp1_legacy.framebuffer_height *= 2; /* double interlace */

  // TVM/DIE change interpretation, not ownership. Only a framebuffer change
  // exchanges banks or latches the DIL selection for the next drawing field.
  vdp1_prepare_framebuffers();
}

void saturn_state::vdp1_regs_w(offs_t offset, uint16_t data,
                               uint16_t mem_mask) {
  // EDSR, LOPR, COPR and MODR are read-only (ST-013 sections 4.6-4.9).
  if (offset >= 0x10 / 2 && offset <= 0x16 / 2)
    return;
  if (!mem_mask)
    return;
  COMBINE_DATA(&m_vdp1_regs[offset]);
  vdp1_trace("register-write", offset);

  switch (offset) {
  case 0x00 / 2:
    vdp1_set_framebuffer_config();
    if (VDP1_LOG)
      logerror("VDP1: Access to register TVMR = %1X\n", data);

    break;
  case 0x02 / 2:
    vdp1_set_framebuffer_config();
    if (VDP1_LOG)
      logerror("VDP1: Access to register FBCR = %1X\n", data);
    m_vdp1_legacy.fbcr_accessed = 1;
    break;
  case 0x04 / 2:
    if (VDP1_LOG)
      logerror("VDP1: Access to register PTMR = %1X\n", data);
    if (VDP1_PTMR == 1)
      vdp1_process_list();

    break;
  case 0x06 / 2:
    if (VDP1_LOG)
      logerror("VDP1: Erase data set %08X\n", data);

    // The erase payload is latched at framebuffer change.
    break;
  case 0x08 / 2:
    if (VDP1_LOG)
      logerror("VDP1: Erase upper-left coord set: %08X\n", data);
    break;
  case 0x0a / 2:
    if (VDP1_LOG)
      logerror("VDP1: Erase lower-right coord set: %08X\n", data);
    break;
  case 0x0c / 2:
    if (mem_mask)
      vdp1_request_termination();
    break;
  case 0x0e / 2: // unused halfword of a longword access at ENDR
    if (VDP1_LOG)
      logerror("VDP1: Draw forced termination register write: %08X %08X\n",
               offset * 2, data);
    break;
  default:
    logerror("Warning: write to unknown VDP1 reg %08x %08x\n", offset * 2,
             data);
    break;
  }
}

uint32_t saturn_state::vdp1_vram_r(offs_t offset) {
  return m_vdp1_vram[offset];
}

void saturn_state::vdp1_vram_w(offs_t offset, uint32_t data,
                               uint32_t mem_mask) {
  uint8_t *vdp1 = m_vdp1_legacy.gfx_decode.get();

  COMBINE_DATA(&m_vdp1_vram[offset]);

  //  if (((offset * 4) > 0xdf) && ((offset * 4) < 0x140))
  //  {
  //      logerror("%s: VRAM dword write to %08X = %08X & %08X\n",
  //      machine().describe_context(), offset*4, data, mem_mask);
  //  }

  data = m_vdp1_vram[offset];
  /* put in gfx region for easy decoding */
  vdp1[offset * 4 + 0] = (data & 0xff000000) >> 24;
  vdp1[offset * 4 + 1] = (data & 0x00ff0000) >> 16;
  vdp1[offset * 4 + 2] = (data & 0x0000ff00) >> 8;
  vdp1[offset * 4 + 3] = (data & 0x000000ff) >> 0;
}

void saturn_state::vdp1_framebuffer0_w(offs_t offset, uint32_t data,
                                       uint32_t mem_mask) {
  offset &= 0xffff; // 2-Mbit drawing bank; the upper CPU window is a mirror.
  // popmessage ("STV VDP1 Framebuffer 0 WRITE offset %08x data %08x",offset,
  // data);
  if (VDP1_TVM() & 1) {
    /* 8-bit mode */
    // printf("VDP1 8-bit mode %08x %02x\n",offset,data);
    if (ACCESSING_BITS_24_31) {
      m_vdp1_legacy
          .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2] &=
          0x00ff;
      m_vdp1_legacy
          .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2] |=
          (data >> 16) & 0xff00;
    }
    if (ACCESSING_BITS_16_23) {
      m_vdp1_legacy
          .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2] &=
          0xff00;
      m_vdp1_legacy
          .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2] |=
          (data >> 16) & 0x00ff;
    }
    if (ACCESSING_BITS_8_15) {
      m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                               [offset * 2 + 1] &= 0x00ff;
      m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                               [offset * 2 + 1] |= data & 0xff00;
    }
    if (ACCESSING_BITS_0_7) {
      m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                               [offset * 2 + 1] &= 0xff00;
      m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                               [offset * 2 + 1] |= data & 0x00ff;
    }
  } else {
    /* 16-bit mode */
    if (ACCESSING_BITS_16_31) {
      m_vdp1_legacy
          .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2] =
          (data >> 16) & 0xffff;
    }
    if (ACCESSING_BITS_0_15) {
      m_vdp1_legacy
          .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2 + 1] =
          data & 0xffff;
    }
  }
}

uint32_t saturn_state::vdp1_framebuffer0_r(offs_t offset, uint32_t mem_mask) {
  offset &= 0xffff;
  uint32_t result = 0;
  // popmessage ("STV VDP1 Framebuffer 0 READ offset %08x",offset);
  if (VDP1_TVM() & 1) {
    /* 8-bit mode */
    // printf("VDP1 8-bit mode %08x\n",offset);
    if (ACCESSING_BITS_24_31)
      result |=
          ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                                     [offset * 2] &
            0xff00)
           << 16);
    if (ACCESSING_BITS_16_23)
      result |=
          ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                                     [offset * 2] &
            0x00ff)
           << 16);
    if (ACCESSING_BITS_8_15)
      result |=
          ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                                     [offset * 2 + 1] &
            0xff00));
    if (ACCESSING_BITS_0_7)
      result |=
          ((m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                                     [offset * 2 + 1] &
            0x00ff));
  } else {
    /* 16-bit mode */
    if (ACCESSING_BITS_16_31) {
      result |=
          (m_vdp1_legacy
               .framebuffer[m_vdp1_legacy.framebuffer_current_draw][offset * 2]
           << 16);
    }
    if (ACCESSING_BITS_0_15) {
      result |=
          (m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_draw]
                                    [offset * 2 + 1]);
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

void saturn_state::clear_gouraud_shading() {
  gouraud_shading = decltype(gouraud_shading)();
}

uint8_t saturn_state::read_gouraud_table() {
  int gaddr;

  if (current_sprite.CMDPMOD & 0x4) {
    gaddr = current_sprite.CMDGRDA * 8;
    gouraud_shading.GA = (m_vdp1_vram[gaddr / 4] >> 16) & 0xffff;
    gouraud_shading.GB = (m_vdp1_vram[gaddr / 4] >> 0) & 0xffff;
    gouraud_shading.GC = (m_vdp1_vram[gaddr / 4 + 1] >> 16) & 0xffff;
    gouraud_shading.GD = (m_vdp1_vram[gaddr / 4 + 1] >> 0) & 0xffff;
    return 1;
  } else {
    return 0;
  }
}

static inline int32_t _shading(int32_t color, int64_t correction) {
  correction = (correction >> 16) & 0x1f;
  color += (correction - 16);

  if (color < 0)
    color = 0;
  if (color > 0x1f)
    color = 0x1f;

  return color;
}

uint16_t saturn_state::vdp1_apply_gouraud_shading(int x, int y, uint16_t pix) {
  // Evaluate at the destination coordinate, not at the number of dots written.
  // Mesh, transparency and user clipping can suppress writes without stopping
  // the Gouraud interpolator (ST-013 section 6.3).
  const auto &line = vdp1_shading_data->scanline[y];
  if (line.integer) {
    const int origin = line.x[0] >> FRAC_SHIFT;
    const int columns = std::abs((line.x[1] >> FRAC_SHIFT) - origin) + 1;
    const auto channel = [&](int original, const int32_t *ends) {
      const int a = ends[0] >> FRAC_SHIFT, b = ends[1] >> FRAC_SHIFT;
      const int correction = std::min(a, b) + vdp1_scaled_coordinate(
          std::abs(b - a) + 1, columns, std::abs(x - origin), b < a);
      return std::clamp(original + correction - 16, 0, 31);
    };
    return (pix & 0x8000) | channel(RGB_R(pix), line.r) |
        (channel(RGB_G(pix), line.g) << 5) | (channel(RGB_B(pix), line.b) << 10);
  }
  const int64_t dx = int64_t(x) - (line.x[0] >> FRAC_SHIFT);
  const int r = _shading(RGB_R(pix), line.r[0] + dx * line.dr);
  const int g = _shading(RGB_G(pix), line.g[0] + dx * line.dg);
  const int b = _shading(RGB_B(pix), line.b[0] + dx * line.db);
  return (pix & 0x8000) | (b << 10) | (g << 5) | r;
}

void saturn_state::vdp1_setup_rectangle_shading(const spoint *q, const rectangle &cliprect) {
  if (!read_gouraud_table())
    return;
  // ST-013 sections 6.8 and 7.4/7.5: the table belongs to vertices A/B/C/D,
  // independently of texture DIR. Include both scaled destination endpoints.
  // Use the same quantized edge-then-span recurrence as native primitives;
  // clipping skips positions rather than restarting the gradient.
  const int rows = std::abs(q[3].y - q[0].y) + 1;
  const int top = std::max({std::min(q[0].y, q[3].y), cliprect.min_y, 0});
  const int bottom = std::min({std::max(q[0].y, q[3].y), cliprect.max_y, 511});
  const uint16_t colors[4] = {gouraud_shading.GA, gouraud_shading.GB,
                            gouraud_shading.GC, gouraud_shading.GD};
  for (int y = top; y <= bottom; ++y) {
    auto &line = vdp1_shading_data->scanline[y];
    line = {};
    line.integer = true;
    // Multiplication is defined for negative offscreen coordinates as well.
    line.x[0] = q[0].x * (1 << FRAC_SHIFT);
    line.x[1] = q[1].x * (1 << FRAC_SHIFT);
    for (int edge = 0; edge < 2; ++edge) {
      int32_t *channels[3] = {line.r, line.g, line.b};
      for (int component = 0; component < 3; ++component) {
        const int a = (colors[edge] >> (component * 5)) & 31;
        const int b = (colors[3 - edge] >> (component * 5)) & 31;
        channels[component][edge] = (std::min(a, b) + vdp1_scaled_coordinate(
            std::abs(b - a) + 1, rows, std::abs(y - q[0].y), b < a)) << FRAC_SHIFT;
      }
    }
  }
}

void saturn_state::vdp1_setup_shading_for_line(int32_t y, int32_t x1,
                                               int32_t x2, int32_t r1,
                                               int32_t g1, int32_t b1,
                                               int32_t r2, int32_t g2,
                                               int32_t b2) {
  int xx1 = x1 >> FRAC_SHIFT;
  int xx2 = x2 >> FRAC_SHIFT;

  if (xx1 > xx2) {
    using std::swap;
    swap(xx1, xx2);
    swap(x1, x2);
    swap(r1, r2);
    swap(g1, g2);
    swap(b1, b2);
  }

  if ((y >= 0) && (y < 512)) {
    int32_t dx;
    int32_t gbd, ggd, grd;

    dx = xx2 - xx1;

    if (dx == 0) {
      gbd = ggd = grd = 0;
    } else {
      gbd = abs(b2 - b1) / dx;
      if (b2 < b1)
        gbd = -gbd;
      ggd = abs(g2 - g1) / dx;
      if (g2 < g1)
        ggd = -ggd;
      grd = abs(r2 - r1) / dx;
      if (r2 < r1)
        grd = -grd;
    }

    vdp1_shading_data->scanline[y].integer = false;
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
    int32_t x1, int32_t x2, int32_t sl1, int32_t sl2, int32_t *nx1,
    int32_t *nx2, int32_t r1, int32_t r2, int32_t slr1, int32_t slr2,
    int32_t *nr1, int32_t *nr2, int32_t g1, int32_t g2, int32_t slg1,
    int32_t slg2, int32_t *ng1, int32_t *ng2, int32_t b1, int32_t b2,
    int32_t slb1, int32_t slb2, int32_t *nb1, int32_t *nb2, int32_t _y1,
    int32_t y2) {
  if (x1 > x2 || (x1 == x2 && sl1 > sl2)) {
    using std::swap;
    swap(x1, x2);
    swap(sl1, sl2);
    swap(nx1, nx2);
    swap(r1, r2);
    swap(slr1, slr2);
    swap(nr1, nr2);
    swap(g1, g2);
    swap(slg1, slg2);
    swap(ng1, ng2);
    swap(b1, b2);
    swap(slb1, slb2);
    swap(nb1, nb2);
  }

  while (_y1 < y2) {
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

void saturn_state::vdp1_setup_shading(const struct spoint *q,
                                      const rectangle &cliprect) {
  int32_t x1, x2, delta, cury, limy;
  int32_t r1, g1, b1, r2, g2, b2;
  int32_t sl1, slg1, slb1, slr1;
  int32_t sl2, slg2, slb2, slr2;
  int pmin, pmax, i, ps1, ps2;
  struct shaded_point p[8];
  uint16_t gd[4];

  if (read_gouraud_table() == 0)
    return;

  gd[0] = gouraud_shading.GA;
  gd[1] = gouraud_shading.GB;
  gd[2] = gouraud_shading.GC;
  gd[3] = gouraud_shading.GD;

  for (i = 0; i < 4; i++) {
    p[i].x = p[i + 4].x = q[i].x << FRAC_SHIFT;
    p[i].y = p[i + 4].y = q[i].y;
    p[i].r = p[i + 4].r = RGB_R(gd[i]) << FRAC_SHIFT;
    p[i].g = p[i + 4].g = RGB_G(gd[i]) << FRAC_SHIFT;
    p[i].b = p[i + 4].b = RGB_B(gd[i]) << FRAC_SHIFT;
  }

  pmin = pmax = 0;
  for (i = 1; i < 4; i++) {
    if (p[i].y < p[pmin].y)
      pmin = i;
    if (p[i].y > p[pmax].y)
      pmax = i;
  }

  cury = p[pmin].y;
  limy = p[pmax].y;

  vdp1_shading_data->sy = cury;
  vdp1_shading_data->ey = limy;

  if (cury == limy) {
    x1 = x2 = p[0].x;
    ps1 = ps2 = 0;
    for (i = 1; i < 4; i++) {
      if (p[i].x < x1) {
        x1 = p[i].x;
        ps1 = i;
      }
      if (p[i].x > x2) {
        x2 = p[i].x;
        ps2 = i;
      }
    }
    vdp1_setup_shading_for_line(cury, x1, x2, p[ps1].r, p[ps1].g, p[ps1].b,
                                p[ps2].r, p[ps2].g, p[ps2].b);
    goto finish;
  }

  ps1 = pmin + 4;
  ps2 = pmin;

  goto startup;

  for (;;) {
    if (p[ps1 - 1].y == p[ps2 + 1].y) {
      vdp1_setup_shading_for_slope(x1, x2, sl1, sl2, &x1, &x2, r1, r2, slr1,
                                   slr2, &r1, &r2, g1, g2, slg1, slg2, &g1, &g2,
                                   b1, b2, slb1, slb2, &b1, &b2, cury,
                                   p[ps1 - 1].y);
      cury = p[ps1 - 1].y;
      if (cury >= limy)
        break;
      ps1--;
      ps2++;

    startup:
      while (p[ps1 - 1].y == cury)
        ps1--;
      while (p[ps2 + 1].y == cury)
        ps2++;
      x1 = p[ps1].x;
      r1 = p[ps1].r;
      g1 = p[ps1].g;
      b1 = p[ps1].b;
      x2 = p[ps2].x;
      r2 = p[ps2].r;
      g2 = p[ps2].g;
      b2 = p[ps2].b;

      delta = cury - p[ps1 - 1].y;
      sl1 = (x1 - p[ps1 - 1].x) / delta;
      slr1 = (r1 - p[ps1 - 1].r) / delta;
      slg1 = (g1 - p[ps1 - 1].g) / delta;
      slb1 = (b1 - p[ps1 - 1].b) / delta;

      delta = cury - p[ps2 + 1].y;
      sl2 = (x2 - p[ps2 + 1].x) / delta;
      slr2 = (r2 - p[ps2 + 1].r) / delta;
      slg2 = (g2 - p[ps2 + 1].g) / delta;
      slb2 = (b2 - p[ps2 + 1].b) / delta;
    } else if (p[ps1 - 1].y < p[ps2 + 1].y) {
      vdp1_setup_shading_for_slope(x1, x2, sl1, sl2, &x1, &x2, r1, r2, slr1,
                                   slr2, &r1, &r2, g1, g2, slg1, slg2, &g1, &g2,
                                   b1, b2, slb1, slb2, &b1, &b2, cury,
                                   p[ps1 - 1].y);
      cury = p[ps1 - 1].y;
      if (cury >= limy)
        break;
      ps1--;
      while (p[ps1 - 1].y == cury)
        ps1--;
      x1 = p[ps1].x;
      r1 = p[ps1].r;
      g1 = p[ps1].g;
      b1 = p[ps1].b;

      delta = cury - p[ps1 - 1].y;
      sl1 = (x1 - p[ps1 - 1].x) / delta;
      slr1 = (r1 - p[ps1 - 1].r) / delta;
      slg1 = (g1 - p[ps1 - 1].g) / delta;
      slb1 = (b1 - p[ps1 - 1].b) / delta;
    } else {
      vdp1_setup_shading_for_slope(x1, x2, sl1, sl2, &x1, &x2, r1, r2, slr1,
                                   slr2, &r1, &r2, g1, g2, slg1, slg2, &g1, &g2,
                                   b1, b2, slb1, slb2, &b1, &b2, cury,
                                   p[ps2 + 1].y);
      cury = p[ps2 + 1].y;
      if (cury >= limy)
        break;
      ps2++;
      while (p[ps2 + 1].y == cury)
        ps2++;
      x2 = p[ps2].x;
      r2 = p[ps2].r;
      g2 = p[ps2].g;
      b2 = p[ps2].b;

      delta = cury - p[ps2 + 1].y;
      sl2 = (x2 - p[ps2 + 1].x) / delta;
      slr2 = (r2 - p[ps2 + 1].r) / delta;
      slg2 = (g2 - p[ps2 + 1].g) / delta;
      slb2 = (b2 - p[ps2 + 1].b) / delta;
    }
  }
  if (cury == limy)
    vdp1_setup_shading_for_line(cury, x1, x2, r1, g1, b1, r2, g2, b2);

finish:

  if (vdp1_shading_data->sy < 0)
    vdp1_shading_data->sy = 0;
  if (vdp1_shading_data->sy >= 512)
    return;
  if (vdp1_shading_data->ey < 0)
    return;
  if (vdp1_shading_data->ey >= 512)
    vdp1_shading_data->ey = 511;

  for (cury = vdp1_shading_data->sy; cury <= vdp1_shading_data->ey; cury++) {
    while ((vdp1_shading_data->scanline[cury].x[0] >> 16) < cliprect.min_x) {
      vdp1_shading_data->scanline[cury].x[0] += (1 << FRAC_SHIFT);
      vdp1_shading_data->scanline[cury].b[0] +=
          vdp1_shading_data->scanline[cury].db;
      vdp1_shading_data->scanline[cury].g[0] +=
          vdp1_shading_data->scanline[cury].dg;
      vdp1_shading_data->scanline[cury].r[0] +=
          vdp1_shading_data->scanline[cury].dr;
    }
  }
}

/* note that if we're drawing
to the framebuffer we CAN'T frameskip the vdp1 drawing as the hardware can READ
the framebuffer and if we skip the drawing the content could be incorrect when
it reads it, although i have no idea why they would want to */

std::array<uint32_t, 6> saturn_state::vdp1_rotation_parameters() const {
  std::array<uint32_t, 6> result{};
  if (VDP1_TVM() != 2 && VDP1_TVM() != 3)
    return result;

  // ST-058 section 6.3: sprite readout always uses parameter A; RPTA6 and
  // RPTA0 are ignored. Addresses are words and VRAMSZ selects 512 KiB/1 MiB.
  const uint32_t rpta = ((m_vdp2_regs[0xbc / 2] & 7) << 16) |
                        (m_vdp2_regs[0xbe / 2] & 0xffbe);
  const uint32_t mask = m_vdp2->get_vramsz() ? 0x3ffff : 0x1ffff;
  static constexpr unsigned offsets[6] = {0, 1, 3, 4, 5, 6};
  for (unsigned i = 0; i < result.size(); ++i)
    result[i] = m_vdp2_vram[((rpta >> 1) + offsets[i]) & mask];
  return result;
}

int saturn_state::vdp1_rotation_coordinate(uint32_t start, uint32_t line_step,
                                          uint32_t dot_step, int x, int y) {
  // ST-058 p.159: 20-bit signed accumulator with 9 fractional bits; the
  // increment has 12 bits. Discard input precision BEFORE accumulation.
  // Preserve the start sign (bit28) separately from its low ten integer bits.
  // This is also MiSTer's ScrnStartToRC/ScrnIncToRC bit selection.
  const uint32_t origin = ((start >> 7) & 0x7ffff) | ((start >> 9) & 0x80000);
  const auto increment = [](uint32_t raw) {
    const int value = (raw >> 7) & 0xfff;
    return (value ^ 0x800) - 0x800;
  };
  const uint32_t value = (int64_t(origin) + int64_t(y) * increment(line_step) +
                           int64_t(x) * increment(dot_step)) & 0xfffff;
  return ((int(value) ^ 0x80000) - 0x80000) >> 9;
}

uint16_t saturn_state::vdp1_display_pixel(int x, int y,
                                         const std::array<uint32_t, 6> &rotation) const {
  const unsigned mode = VDP1_TVM();
  const unsigned hreso = m_vdp2->get_hreso();
  // Output-screen coordinates enter here, including partial-update clips.
  // ST-013 section 1.2: HDTV/31-kHz repeats every dot in a 2x2 block.
  // Ymir VDP2DrawSpriteLayer also models normal-16/high-res doubling and
  // high-res-8/normal-output decimation. MiSTer's VOUTO emits the two byte
  // lanes on opposite dot-clock phases in mode 1.
  if (mode == 4) {
    x >>= 1;
    y >>= 1;
  } else {
    if ((hreso & 4) || (mode == 0 && (hreso & 6) == 2))
      x >>= 1;
    else if (mode == 1 && (hreso & 6) == 0)
      x <<= 1;
    if (m_vdp2->get_lsmd() == 3 && m_vdp1_legacy.framebuffer_double_interlace == 0)
      y >>= 1;
  }
  if (mode != 2 && mode != 3) {
    if (m_vdp1_legacy.framebuffer_double_interlace > 0) {
      if (m_vdp2->get_lsmd() != 3) {
        const uint16_t *const row = m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_display].get() +
                                     (unsigned(y) & 255) * 512;
        return vdp1_read_pixel(row, x);
      }
      const unsigned field = y & 1;
      if (!m_vdp1_legacy.field_valid[field])
        return 0;
      const uint16_t *const row = m_vdp1_legacy.field_framebuffer[field].get() +
                                   ((unsigned(y) >> 1) & 255) * 512;
      return vdp1_read_pixel(row, x);
    }
    return vdp1_read_pixel(m_vdp1_legacy.framebuffer_display_lines[y], x);
  }

  const int sx = vdp1_rotation_coordinate(rotation[0], rotation[2], rotation[4], x, y);
  const int sy = vdp1_rotation_coordinate(rotation[1], rotation[3], rotation[5], x, y);
  // ST-013 section 1.2: out-of-plane coordinates are transparent, not wrapped.
  if (sx < 0 || sx >= 512 || sy < 0 || sy >= (mode == 3 ? 512 : 256))
    return 0;
  const uint16_t *const row = m_vdp1_legacy.framebuffer[m_vdp1_legacy.framebuffer_current_display].get() +
                               sy * (mode == 3 ? 256 : 512);
  return vdp1_read_pixel(row, sx);
}

uint16_t saturn_state::vdp1_read_pixel(const uint16_t *line, int x) const {
  if (VDP1_TVM() & 1) {
    x &= (VDP1_TVM() == 3) ? 511 : 1023;
    return (line[x >> 1] >> ((x & 1) ? 0 : 8)) & 0xff;
  }
  return line[x & 511];
}

void saturn_state::vdp1_write_pixel(int x, int y, uint16_t value) {
  uint16_t *const line = m_vdp1_legacy.framebuffer_draw_lines[y];
  if (VDP1_TVM() & 1) {
    // ST-013 section 1.1: an 8-bit dot occupies one byte, even X first.
    // Preserve the adjacent dot in the shared CPU-visible word.
    x &= (VDP1_TVM() == 3) ? 511 : 1023;
    const unsigned shift = (x & 1) ? 0 : 8;
    line[x >> 1] = (line[x >> 1] & ~(0xff << shift)) | ((value & 0xff) << shift);
  } else {
    line[x & 511] = value;
  }
}

bool saturn_state::vdp1_pixel_visible(int x, int y) const {
  if (x < 0 || y < 0 || x >= 1024 || y >= 512 ||
      !m_vdp1_legacy.system_cliprect.contains(x, y))
    return false;

  if (m_vdp1_legacy.framebuffer_double_interlace > 0 &&
      unsigned(y & 1) != m_vdp1_legacy.draw_field)
    return false;

  // Technical Bulletin 15: Clip=bit10, Cmod=bit9 (corrected manual prose).
  if (!(current_sprite.CMDPMOD & 0x0400))
    return true;
  const bool inside = m_vdp1_legacy.user_cliprect.contains(x, y);
  return (current_sprite.CMDPMOD & 0x0200) ? !inside : inside;
}

void saturn_state::drawpixel_poly(int x, int y, int patterndata,
                                  int offsetcnt) {
  /* Capcom Collection Dai 4 uses a dummy polygon to clear VDP1 framebuffer that
   * goes over our current max size ... */
  if (!vdp1_pixel_visible(x, y))
    return;

  vdp1_write_pixel(x, y, current_sprite.CMDCOLR);
}

void saturn_state::drawpixel_8bpp_trans(int x, int y, int patterndata,
                                        int offsetcnt) {
  uint16_t pix;

  // the user clip rectangle comes from 13-bit command fields and can be far
  // larger than the framebuffer, so bound the pixel like the other variants do
  if (!vdp1_pixel_visible(x, y))
    return;

  pix = m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt) & 0x7ffff] & 0xff;
  if (pix != 0) {
    vdp1_write_pixel(x, y, pix | m_sprite_colorbank);
  }
}

void saturn_state::drawpixel_4bpp_notrans(int x, int y, int patterndata,
                                          int offsetcnt) {
  uint16_t pix;

  // the user clip rectangle comes from 13-bit command fields and can be far
  // larger than the framebuffer, so bound the pixel like the other variants do
  if (!vdp1_pixel_visible(x, y))
    return;

  pix = m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt / 2) & 0x7ffff];
  pix = offsetcnt & 1 ? (pix & 0x0f) : ((pix & 0xf0) >> 4);
  vdp1_write_pixel(x, y, pix | m_sprite_colorbank);
}

void saturn_state::drawpixel_4bpp_trans(int x, int y, int patterndata,
                                        int offsetcnt) {
  uint16_t pix;

  // the user clip rectangle comes from 13-bit command fields and can be far
  // larger than the framebuffer, so bound the pixel like the other variants do
  if (!vdp1_pixel_visible(x, y))
    return;

  pix = m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt / 2) & 0x7ffff];
  pix = offsetcnt & 1 ? (pix & 0x0f) : ((pix & 0xf0) >> 4);
  if (pix != 0)
    vdp1_write_pixel(x, y, pix | m_sprite_colorbank);
}

uint16_t saturn_state::vdp1_color_calculate(uint16_t src, uint16_t dst, unsigned mode) {
  // Gouraud saturation is applied to src before this operation. Mode 5 is
  // prohibited; retain the component-bit interpretation for that setting.
  switch (mode & 3) {
  case 0: return src;
  case 1: return (dst & 0x8000) ? ((dst & 0x7bde) >> 1) | 0x8000 : dst;
  case 2: return ((src & 0x7bde) >> 1) | (src & 0x8000);
  case 3:
    if (!(dst & 0x8000))
      return src;
    // Per-component floor((source + background) / 2), including the carry
    // when both inputs are odd. Background MSB remains set.
    return 0x8000 | (((src & 0x7bde) >> 1) + ((dst & 0x7bde) >> 1) + (src & dst & 0x0421));
  }
  return src;
}

void saturn_state::vdp1_draw_color(int x, int y, uint16_t src) {
  uint16_t *const line = m_vdp1_legacy.framebuffer_draw_lines[y];
  if (current_sprite.CMDPMOD & 0x8000) {
    // MON changes the existing framebuffer, not the source color. In 8-bit
    // mode the word-aligned behavior follows Ymir; silicon detail is unverified.
    const unsigned word = (VDP1_TVM() & 1) ?
        ((unsigned(x) >> 1) & (VDP1_TVM() == 3 ? 255 : 511)) : (x & 511);
    line[word] |= 0x8000;
    return;
  }
  if (VDP1_TVM() & 1) {
    // Replace is the only supported 8-bit color calculation (ST-013 p.94).
    vdp1_write_pixel(x, y, src);
    return;
  }
  if (current_sprite.CMDPMOD & 4)
    src = vdp1_apply_gouraud_shading(x, y, src);
  const uint16_t dst = vdp1_read_pixel(line, x);
  vdp1_write_pixel(x, y, vdp1_color_calculate(src, dst, current_sprite.CMDPMOD));
}

void saturn_state::drawpixel_generic(int x, int y, int patterndata,
                                     int offsetcnt) {
  int pix, transpen, spd = current_sprite.CMDPMOD & 0x40;
  //  int mode;
  int mesh = current_sprite.CMDPMOD & 0x100;
  int raw, endcode;

  /* Mesh is a checkerboard stipple.  VDP1 User's Manual sec 6.3 "Mesh Enable"
     (Figure 6.8, "Mesh Processing") states the rule exactly: "Only pixels for
     which (X coordinate value + Y coordinate value) is even (XLSB XOR YLSB = 0)
     are drawn, and odd pixels are skipped and not drawn."  So the pixel is
     dropped when the parities of x and y differ; x and y are framebuffer
     coordinates, the same space the rule is stated in.  The test here used to
     be inverted, drawing the complementary pattern. */
  if (mesh && ((x ^ y) & 1)) {
    return;
  }

  if (!vdp1_pixel_visible(x, y))
    return;

  if (current_sprite.ispoly) {
    raw = pix = current_sprite.CMDCOLR & 0xffff;

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
  } else {
    switch (current_sprite.CMDPMOD & 0x0038) {
    case 0x0000: // mode 0 16 colour bank mode (4bits) (hanagumi blocks)
      // most of the shienryu sprites use this mode
      raw = m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt / 2) & 0x7ffff];
      raw = offsetcnt & 1 ? (raw & 0x0f) : ((raw & 0xf0) >> 4);
      pix = raw + ((current_sprite.CMDCOLR & 0xfff0));
      // mode = 0;
      transpen = 0;
      endcode = 0xf;
      break;
    case 0x0008: // mode 1 16 colour lookup table mode (4bits)
      // shienryu explosions (and some enemies) use this mode
      raw = m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt / 2) & 0x7ffff];
      raw = offsetcnt & 1 ? (raw & 0x0f) : ((raw & 0xf0) >> 4);
      {
        const unsigned address = ((current_sprite.CMDCOLR * 8) + raw * 2) & 0x7ffff;
        pix = (m_vdp1_legacy.gfx_decode[address] << 8) |
              m_vdp1_legacy.gfx_decode[(address + 1) & 0x7ffff];
      }
      // mode = 5;
      transpen = 0;
      endcode = 0xf;
      break;
    case 0x0010: // mode 2 64 colour bank mode (8bits) (character select
                 // portraits on hanagumi)
      raw =
          m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt) & 0x7ffff] & 0xff;
      // mode = 2;
      /* only the low six bits of the dot data select a colour here - the top
         two are ignored (they still count for the 0xff end code and for the
         transparent pen test below, which both use the unmasked value) */
      pix = (raw & 0x3f) + (current_sprite.CMDCOLR & 0xffc0);
      transpen = 0;
      endcode = 0xff;
      // Notes of interest:
      // Scud: the disposable assassin wants transparent pen on 0
      // sasissu: racing stage background clouds
      break;
    case 0x0018: // mode 3 128 colour bank mode (8bits) (little characters on
                 // hanagumi use this mode)
      raw =
          m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt) & 0x7ffff] & 0xff;
      /* seven bits of colour data, see mode 2 */
      pix = (raw & 0x7f) + (current_sprite.CMDCOLR & 0xff80);
      transpen = 0;
      endcode = 0xff;
      // mode = 3;
      break;
    case 0x0020: // mode 4 256 colour bank mode (8bits) (hanagumi title)
      raw =
          m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt) & 0x7ffff] & 0xff;
      pix = raw + (current_sprite.CMDCOLR & 0xff00);
      transpen = 0;
      endcode = 0xff;
      // mode = 4;
      break;
    case 0x0028: // mode 5 32,768 colour RGB mode (16bits)
      /* character data is fetched two bytes at a time in this mode and the
         hardware forces the character address onto a 16 byte boundary first,
         so an odd CMDSRCA loses its low bit here - mednafen (tex_base &= ~0x7
         on a word address) and Ymir (charAddr &= ~0xF) do the same */
      patterndata &= ~0xf;
      raw = m_vdp1_legacy
                .gfx_decode[(patterndata + offsetcnt * 2 + 1) & 0x7ffff] |
            (m_vdp1_legacy.gfx_decode[(patterndata + offsetcnt * 2) & 0x7ffff]
             << 8);
      // mode = 5;
      pix = raw;
      // ST-013 pp.86-88 keeps END and transparent-pixel controls separate.
      // The RGB MSB test is corroborated by MiSTer's GetPattern (TP=!MSB,
      // EC=7fff) and Ymir's VDP1PlotTexturedLine. In particular, ECD=1 must
      // not make 7fff opaque when SPD=0, including HSS-reduced sprites.
      // Preserve raw for the independent END comparison below; matching
      // transpen to an MSB-clear value makes it transparent without changing
      // the original pixel that SPD=1 may write.
      transpen = (raw & 0x8000) ? 0 : raw;
      endcode = 0x7fff;
      break;
    case 0x0030: // mode 6 invalid
    case 0x0038: // mode 7 invalid
      // game tengoku uses this on hi score screen (tate mode)
      // according to Charles, reads from VRAM address 0
      /* both illegal colour modes behave the same way: the dot data comes from
         VRAM word 0 instead of from the character data (mednafen does the same,
         and its VRAM usage counter attributes the access to address 0 as well)
       */
      raw = pix =
          m_vdp1_legacy.gfx_decode[1] | (m_vdp1_legacy.gfx_decode[0] << 8);
      // TODO: check transpen
      transpen = 0;
      endcode = -1;
      break;
    default: // other settings illegal
      pix = machine().rand();
      raw = pix & 0xff; // just mimic old driver behavior
      // mode = 0;
      transpen = 0;
      endcode = 0xff;
      popmessage("Illegal Sprite Mode %02x", current_sprite.CMDPMOD & 0x0038);
    }

    // preliminary end code disable support
    if (((current_sprite.CMDPMOD & 0x80) == 0) && (raw == endcode)) {
      return;
    }
  }

  if ((raw != transpen) || spd)
    vdp1_draw_color(x, y, pix);
}

void saturn_state::vdp1_set_drawpixel() {
  int sprite_type = current_sprite.CMDCTRL & 0x000f;
  int sprite_mode = current_sprite.CMDPMOD & 0x0038;
  int spd = current_sprite.CMDPMOD & 0x40;
  int mesh = current_sprite.CMDPMOD & 0x100;
  int ecd = current_sprite.CMDPMOD & 0x80;

  if (mesh || !ecd || ((current_sprite.CMDPMOD & 0x7) != 0)) {
    drawpixel = &saturn_state::drawpixel_generic;
    return;
  }

  if (current_sprite.CMDPMOD & 0x8000) {
    drawpixel = &saturn_state::drawpixel_generic;
    return;
  }

  // polygon / polyline / line with replace case
  if (sprite_type & 4 && ((current_sprite.CMDPMOD & 0x7) == 0)) {
    drawpixel = &saturn_state::drawpixel_poly;
  } else if ((sprite_mode == 0x20) && !spd) {
    m_sprite_colorbank = (current_sprite.CMDCOLR & 0xff00);
    drawpixel = &saturn_state::drawpixel_8bpp_trans;
  } else if ((sprite_mode == 0x00) && spd) {
    m_sprite_colorbank = (current_sprite.CMDCOLR & 0xfff0);
    drawpixel = &saturn_state::drawpixel_4bpp_notrans;
  } else if (sprite_mode == 0x00 && !spd) {
    m_sprite_colorbank = (current_sprite.CMDCOLR & 0xfff0);
    drawpixel = &saturn_state::drawpixel_4bpp_trans;
  } else {
    drawpixel = &saturn_state::drawpixel_generic;
  }
}

void saturn_state::vdp1_fill_slope(const rectangle &cliprect, int patterndata,
                                   int xsize, int32_t x1, int32_t x2,
                                   int32_t sl1, int32_t sl2, int32_t *nx1,
                                   int32_t *nx2, int32_t u1, int32_t u2,
                                   int32_t slu1, int32_t slu2, int32_t *nu1,
                                   int32_t *nu2, int32_t v1, int32_t v2,
                                   int32_t slv1, int32_t slv2, int32_t *nv1,
                                   int32_t *nv2, int32_t _y1, int32_t y2) {
  if (_y1 > cliprect.max_y)
    return;

  if (y2 <= cliprect.min_y) {
    int delta = y2 - _y1;
    *nx1 = x1 + delta * sl1;
    *nu1 = u1 + delta * slu1;
    *nv1 = v1 + delta * slv1;
    *nx2 = x2 + delta * sl2;
    *nu2 = u2 + delta * slu2;
    *nv2 = v2 + delta * slv2;
    return;
  }

  if (y2 > cliprect.max_y)
    y2 = cliprect.max_y + 1;
  // the framebuffer is 1024x512, the clip rectangle is not
  if (y2 > 512)
    y2 = 512;

  if (_y1 < cliprect.min_y) {
    int delta = cliprect.min_y - _y1;
    x1 += delta * sl1;
    u1 += delta * slu1;
    v1 += delta * slv1;
    x2 += delta * sl2;
    u2 += delta * slu2;
    v2 += delta * slv2;
    _y1 = cliprect.min_y;
  }

  if (x1 > x2 || (x1 == x2 && sl1 > sl2)) {
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

  while (_y1 < y2) {
    if (_y1 >= cliprect.min_y) {
      vdp1_fill_line(cliprect, patterndata, xsize, _y1, x1, x2, u1, u2, v1, v2);
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

void saturn_state::vdp1_fill_line(const rectangle &cliprect, int patterndata,
                                  int xsize, int32_t y, int32_t x1, int32_t x2,
                                  int32_t u1, int32_t u2, int32_t v1,
                                  int32_t v2) {
  int xx1 = x1 >> FRAC_SHIFT;
  int xx2 = x2 >> FRAC_SHIFT;

  if (y >= 512 || y > cliprect.max_y || y < cliprect.min_y)
    return;

  if (xx1 <= cliprect.max_x || xx2 >= cliprect.min_x) {
    int32_t slux = 0, slvx = 0;
    int32_t u = u1;
    int32_t v = v1;
    if (xx1 != xx2) {
      int delta = xx2 - xx1;
      slux = (u2 - u1) / delta;
      slvx = (v2 - v1) / delta;
    }
    if (xx1 < cliprect.min_x) {
      int delta = cliprect.min_x - xx1;
      u += slux * delta;
      v += slvx * delta;
      xx1 = cliprect.min_x;
    }
    if (xx2 > cliprect.max_x)
      xx2 = cliprect.max_x;
    // the framebuffer is 1024x512, the clip rectangle is not
    if (xx2 >= 1024)
      xx2 = 1023;

    while (xx1 <= xx2) {
      const int texel = (v >> FRAC_SHIFT) * xsize + (u >> FRAC_SHIFT);
      if (vdp1_texture_sample_visible(patterndata, xsize, texel))
        (this->*drawpixel)(xx1, y, patterndata, texel);
      xx1++;
      u += slux;
      v += slvx;
    }
  }
}

void saturn_state::vdp1_fill_quad(const rectangle &cliprect, int patterndata,
                                  int xsize, const struct spoint *q) {
  // The legacy affine fallback is still atomic; native queued primitives
  // save their source-row cutoff cache across scheduler boundaries.
  m_vdp1_texture_end.fill(-1);
  int32_t sl1, sl2, slu1, slu2, slv1, slv2, cury, limy, x1, x2, u1, u2, v1, v2,
      delta;
  int pmin, pmax, i, ps1, ps2;
  struct spoint p[8];

  for (i = 0; i < 4; i++) {
    p[i].x = p[i + 4].x = q[i].x << FRAC_SHIFT;
    p[i].y = p[i + 4].y = q[i].y;
    p[i].u = p[i + 4].u = q[i].u << FRAC_SHIFT;
    p[i].v = p[i + 4].v = q[i].v << FRAC_SHIFT;
  }

  pmin = pmax = 0;
  for (i = 1; i < 4; i++) {
    if (p[i].y < p[pmin].y)
      pmin = i;
    if (p[i].y > p[pmax].y)
      pmax = i;
  }

  cury = p[pmin].y;
  limy = p[pmax].y;

  if (cury == limy) {
    x1 = x2 = p[0].x;
    u1 = u2 = p[0].u;
    v1 = v2 = p[0].v;
    for (i = 1; i < 4; i++) {
      if (p[i].x < x1) {
        x1 = p[i].x;
        u1 = p[i].u;
        v1 = p[i].v;
      }
      if (p[i].x > x2) {
        x2 = p[i].x;
        u2 = p[i].u;
        v2 = p[i].v;
      }
    }
    vdp1_fill_line(cliprect, patterndata, xsize, cury, x1, x2, u1, u2, v1, v2);
    return;
  }

  if (cury > cliprect.max_y)
    return;
  if (limy <= cliprect.min_y)
    return;

  if (limy > cliprect.max_y)
    limy = cliprect.max_y;

  ps1 = pmin + 4;
  ps2 = pmin;

  goto startup;

  for (;;) {
    if (p[ps1 - 1].y == p[ps2 + 1].y) {
      vdp1_fill_slope(cliprect, patterndata, xsize, x1, x2, sl1, sl2, &x1, &x2,
                      u1, u2, slu1, slu2, &u1, &u2, v1, v2, slv1, slv2, &v1,
                      &v2, cury, p[ps1 - 1].y);
      cury = p[ps1 - 1].y;
      if (cury >= limy)
        break;
      ps1--;
      ps2++;

    startup:
      while (p[ps1 - 1].y == cury)
        ps1--;
      while (p[ps2 + 1].y == cury)
        ps2++;
      x1 = p[ps1].x;
      u1 = p[ps1].u;
      v1 = p[ps1].v;
      x2 = p[ps2].x;
      u2 = p[ps2].u;
      v2 = p[ps2].v;

      delta = cury - p[ps1 - 1].y;
      sl1 = (x1 - p[ps1 - 1].x) / delta;
      slu1 = (u1 - p[ps1 - 1].u) / delta;
      slv1 = (v1 - p[ps1 - 1].v) / delta;

      delta = cury - p[ps2 + 1].y;
      sl2 = (x2 - p[ps2 + 1].x) / delta;
      slu2 = (u2 - p[ps2 + 1].u) / delta;
      slv2 = (v2 - p[ps2 + 1].v) / delta;
    } else if (p[ps1 - 1].y < p[ps2 + 1].y) {
      vdp1_fill_slope(cliprect, patterndata, xsize, x1, x2, sl1, sl2, &x1, &x2,
                      u1, u2, slu1, slu2, &u1, &u2, v1, v2, slv1, slv2, &v1,
                      &v2, cury, p[ps1 - 1].y);
      cury = p[ps1 - 1].y;
      if (cury >= limy)
        break;
      ps1--;
      while (p[ps1 - 1].y == cury)
        ps1--;
      x1 = p[ps1].x;
      u1 = p[ps1].u;
      v1 = p[ps1].v;

      delta = cury - p[ps1 - 1].y;
      sl1 = (x1 - p[ps1 - 1].x) / delta;
      slu1 = (u1 - p[ps1 - 1].u) / delta;
      slv1 = (v1 - p[ps1 - 1].v) / delta;
    } else {
      vdp1_fill_slope(cliprect, patterndata, xsize, x1, x2, sl1, sl2, &x1, &x2,
                      u1, u2, slu1, slu2, &u1, &u2, v1, v2, slv1, slv2, &v1,
                      &v2, cury, p[ps2 + 1].y);
      cury = p[ps2 + 1].y;
      if (cury >= limy)
        break;
      ps2++;
      while (p[ps2 + 1].y == cury)
        ps2++;
      x2 = p[ps2].x;
      u2 = p[ps2].u;
      v2 = p[ps2].v;

      delta = cury - p[ps2 + 1].y;
      sl2 = (x2 - p[ps2 + 1].x) / delta;
      slu2 = (u2 - p[ps2 + 1].u) / delta;
      slv2 = (v2 - p[ps2 + 1].v) / delta;
    }
  }
  if (cury == limy)
    vdp1_fill_line(cliprect, patterndata, xsize, cury, x1, x2, u1, u2, v1, v2);
}

// VDP1 vertex and local coordinates are 13-bit signed fields, not 16-bit ones.
// mednafen masks every coordinate it reads out of a command with 0x1fff and
// uses bit 12 as the sign, and Ymir's notes record that the Virtua Fighter 2
// fight intro writes vertices whose bits 13-15 are not a sign extension of bit
// 12: the VDP1 ignores them, but taking all sixteen bits turned those into
// polygons thousands of pixels across, which is what made the intro crawl.
// For a correctly sign-extended value this is a no-op.
static inline int vdp1_coord(int v) {
  return (v & 0x1000) ? (v | ~0x1fff) : (v & 0x1fff);
}

int saturn_state::x2s(int v) { return vdp1_coord(v) + m_vdp1_legacy.local_x; }

int saturn_state::y2s(int v) { return vdp1_coord(v) + m_vdp1_legacy.local_y; }

void saturn_state::vdp1_draw_segment(const rectangle &cliprect, const spoint &a,
                                      const spoint &b, uint16_t color_a, uint16_t color_b,
                                      bool edge_coverage, int texture_row, int texture_width) {
  const int dx = b.x - a.x, dy = b.y - a.y;
  const int ax = std::abs(dx), ay = std::abs(dy);
  const bool horizontal = ax >= ay;
  const int major = std::max(ax, ay), minor = std::min(ax, ay);
  const int sx = dx < 0 ? -1 : 1, sy = dy < 0 ? -1 : 1;
  // Pre-clipping can reject a wholly separated span. Pclp=1 must retain
  // its traversal, even when all pixel writes will be clipped. Keep a one-dot
  // coverage margin and avoid assuming straight bounds if the error wraps.
  if (!(current_sprite.CMDPMOD & 0x0800) && major < 2048 && (std::max(a.x, b.x) < cliprect.min_x - 1 ||
      std::min(a.x, b.x) > cliprect.max_x + 1 || std::max(a.y, b.y) < cliprect.min_y - 1 ||
      std::min(a.y, b.y) > cliprect.max_y + 1))
    return;
  if (m_vdp1_raster_building) {
    assert(m_vdp1_raster.count < vdp1_raster_state::max_segments);
    const std::array<int32_t, vdp1_raster_state::segment_words> segment = {
        a.x, a.y, b.x, b.y, color_a, color_b,
        cliprect.min_x, cliprect.max_x, cliprect.min_y, cliprect.max_y,
        edge_coverage, texture_row, texture_width};
    std::copy(segment.begin(), segment.end(), m_vdp1_raster.segments.begin() +
              vdp1_raster_state::segment_words * m_vdp1_raster.count++);
    return;
  }
  // The line error datapath is signed 13-bit. Unlike textured/polygon lines,
  // standalone lines do not emit the extra edge-coverage pixel.
  const auto wrap = [](int v) { return int((unsigned(v) & 0x1fff) ^ 0x1000) - 0x1000; };
  int error = wrap(major + (edge_coverage ? 0 : 1));
  const int target = edge_coverage ? -1 : ((horizontal ? dx : dy) < 0 ? 1 : 0);
  const bool textured = texture_row >= 0;
  const bool hss = textured && (current_sprite.CMDPMOD & 0x1000) && major + 1 < texture_width;
  const uint16_t mode = current_sprite.CMDPMOD;
  if (textured)
    current_sprite.CMDPMOD = (mode & ~0x1000) | (hss ? 0x1000 : 0);
  const int address = (current_sprite.CMDSRCA & 0xffff) * 8;
  bool extra = false;
  int x = a.x, y = a.y;
  if (m_vdp1_raster_running && m_vdp1_raster.dot) {
    x = m_vdp1_raster.x;
    y = m_vdp1_raster.y;
    error = m_vdp1_raster.error;
    extra = m_vdp1_raster.extra;
  }
  for (int dot = m_vdp1_raster_running ? m_vdp1_raster.dot : 0; dot <= major; ++dot) {
    if (m_vdp1_raster_running && !m_vdp1_raster_budget)
      break;
    int texel = 0;
    if (textured) {
      int u = vdp1_scaled_coordinate(std::max(1, hss ? texture_width / 2 : texture_width),
                                      major + 1, dot, current_sprite.CMDCTRL & 0x10);
      if (hss) u = u * 2 + m_vdp1_legacy.draw_eos;
      texel = texture_row * texture_width + u;
    }
    const auto plot = [&](int x, int y) {
    if (x >= cliprect.min_x && x <= cliprect.max_x && y >= cliprect.min_y &&
        y <= cliprect.max_y && y >= 0 && y < 512) {
      if (current_sprite.CMDPMOD & 4) {
        const auto shade = [=](int ca, int cb) {
          return (std::min(ca, cb) + vdp1_scaled_coordinate(std::abs(cb - ca) + 1,
                                                             major + 1, dot, cb < ca)) << FRAC_SHIFT;
        };
        const int r = shade(RGB_R(color_a), RGB_R(color_b));
        const int g = shade(RGB_G(color_a), RGB_G(color_b));
        const int blue = shade(RGB_B(color_a), RGB_B(color_b));
        vdp1_setup_shading_for_line(y, x * (1 << FRAC_SHIFT), x * (1 << FRAC_SHIFT),
                                    r, g, blue, r, g, blue);
      }
      if (!textured || vdp1_texture_sample_visible(address, texture_width, texel))
        (this->*drawpixel)(x, y, textured ? address : 0, texel);
    }
    };
    plot(x, y);
    if (extra) {
      // VDP1's extra coverage dot shares the current texel and shade value.
      // It is not filtered antialiasing and can blend a destination twice.
      const bool same_sign = (dx < 0) == (dy < 0);
      plot(x - (same_sign ? 0 : sx), y - (same_sign ? sy : 0));
    }
    extra = false;
    if (horizontal) x += sx; else y += sy;
    error = wrap(error - 2 * minor);
    if (error <= target) {
      error = wrap(error + 2 * major);
      if (horizontal) y += sy; else x += sx;
      extra = edge_coverage;
    }
    if (m_vdp1_raster_running) {
      --m_vdp1_raster_budget;
      m_vdp1_raster.dot = dot + 1;
      m_vdp1_raster.x = x;
      m_vdp1_raster.y = y;
      m_vdp1_raster.error = error;
      m_vdp1_raster.extra = extra;
    }
  }
  current_sprite.CMDPMOD = mode;
}

void saturn_state::vdp1_reset_raster_queue() {
  // Inactive records are irrelevant. Avoid clearing the full bounded span
  // array on every command/restart (only indices and live cursor are reset).
  m_vdp1_raster.count = m_vdp1_raster.index = m_vdp1_raster.dot = 0;
  m_vdp1_raster.x = m_vdp1_raster.y = m_vdp1_raster.error = m_vdp1_raster.end_codes = 0;
  m_vdp1_raster.extra = false;
  m_vdp1_texture_end.fill(-1);
}

int saturn_state::vdp1_raster_slice_cycles() const {
  if (m_vdp1_raster.index == m_vdp1_raster.count)
    return 16; // Next command fetch, not another raster slice.
  int dots = 0;
  for (int i = m_vdp1_raster.index; i < m_vdp1_raster.count && dots < 16; ++i) {
    const int32_t *const data = m_vdp1_raster.segments.data() + vdp1_raster_state::segment_words * i;
    dots += std::max(std::abs(data[2] - data[0]), std::abs(data[3] - data[1])) + 1;
    if (i == m_vdp1_raster.index)
      dots -= m_vdp1_raster.dot;
  }
  return std::min(16, dots);
}

void saturn_state::vdp1_draw_raster_slice() {
  // Bound host work and yield to ENDR/CPU events within a primitive. ST-013
  // describes nominal one-dot-per-clock drawing. A quantum covers at most
  // 16 raster positions and their coverage dots, not exact bus wait states.
  // A normal-sprite END may shorten work after the quantum was scheduled;
  // its unused time is not retroactively removed from the elapsed interval.
  m_vdp1_raster_budget = 16;
  m_vdp1_raster_running = true;
  vdp1_set_drawpixel(); // Reconstruct the dispatch pointer, including postload.
  while (m_vdp1_raster.index < m_vdp1_raster.count && m_vdp1_raster_budget) {
    const int32_t *const data = m_vdp1_raster.segments.data() + vdp1_raster_state::segment_words * m_vdp1_raster.index;
    const spoint a{data[0], data[1], 0, 0}, b{data[2], data[3], 0, 0};
    const rectangle cliprect(data[6], data[7], data[8], data[9]);
    if (data[10] < 0)
      vdp1_draw_rectangle_slice(data);
    else
      vdp1_draw_segment(cliprect, a, b, data[4], data[5], data[10], data[11], data[12]);
    const int length = std::max(std::abs(b.x - a.x), std::abs(b.y - a.y)) + 1;
    if (m_vdp1_raster.dot >= length) {
      ++m_vdp1_raster.index;
      m_vdp1_raster.dot = 0;
      m_vdp1_raster.extra = false;
      m_vdp1_raster.end_codes = 0;
    }
  }
  m_vdp1_raster_running = false;
}

void saturn_state::vdp1_draw_rectangle_slice(const int32_t *data) {
  // Negative span kinds select the existing rectangular texture traversals.
  // Normal sprites count fetched END texels; scaled sprites retain the source
  // row cutoff and integer resampling, including skipped source END markers.
  const bool scaled = data[10] == -2;
  const int width = data[12], columns = data[5];
  const int address = current_sprite.CMDSRCA * 8;
  const uint16_t mode = current_sprite.CMDPMOD;
  const bool hss = scaled && (mode & 0x1000) && columns < width;
  if (scaled)
    current_sprite.CMDPMOD = (mode & ~0x1000) | (hss ? 0x1000 : 0);
  const int length = data[2] - data[0] + 1;
  while (m_vdp1_raster.dot < length && m_vdp1_raster_budget) {
    const int x = data[0] + m_vdp1_raster.dot;
    int texel;
    if (scaled) {
      const int u = vdp1_scaled_coordinate(std::max(1, hss ? width / 2 : width),
          columns, std::abs(x - data[4]), current_sprite.CMDCTRL & 0x10);
      texel = data[11] * width + (hss ? u * 2 + m_vdp1_legacy.draw_eos : u);
    } else {
      texel = data[11] + m_vdp1_raster.dot * data[4];
    }
    ++m_vdp1_raster.dot;
    --m_vdp1_raster_budget;
    if (!scaled && !(mode & 0x80) && vdp1_is_end_code(address, texel) &&
        ++m_vdp1_raster.end_codes == 2) {
      m_vdp1_raster.dot = length;
      break;
    }
    if (!scaled || vdp1_texture_sample_visible(address, width, texel))
      (this->*drawpixel)(x, data[1], address, texel);
  }
  current_sprite.CMDPMOD = mode;
}

void saturn_state::vdp1_draw_line(const rectangle &cliprect) {
  spoint a{}, b{};
  a.x = x2s(current_sprite.CMDXA); a.y = y2s(current_sprite.CMDYA);
  b.x = x2s(current_sprite.CMDXB); b.y = y2s(current_sprite.CMDYB);
  read_gouraud_table();
  vdp1_draw_segment(cliprect, a, b, gouraud_shading.GA, gouraud_shading.GB);
}

void saturn_state::vdp1_draw_poly_line(const rectangle &cliprect) {
  spoint q[4]{};
  q[0].x = x2s(current_sprite.CMDXA); q[0].y = y2s(current_sprite.CMDYA);
  q[1].x = x2s(current_sprite.CMDXB); q[1].y = y2s(current_sprite.CMDYB);
  q[2].x = x2s(current_sprite.CMDXC); q[2].y = y2s(current_sprite.CMDYC);
  q[3].x = x2s(current_sprite.CMDXD); q[3].y = y2s(current_sprite.CMDYD);
  read_gouraud_table();
  const uint16_t colors[4] = {gouraud_shading.GA, gouraud_shading.GB, gouraud_shading.GC, gouraud_shading.GD};
  for (int i = 0; i < 4; ++i)
    vdp1_draw_segment(cliprect, q[i], q[(i + 1) & 3], colors[i], colors[(i + 1) & 3]);
}

void saturn_state::vdp1_draw_quad_pixels(const rectangle &cliprect, int width, int height, const spoint *q) {
  const auto wrap = [](int v) { return int((unsigned(v) & 0x1fff) ^ 0x1000) - 0x1000; };
  struct edge_state {
    spoint point;
    int dx, dy, length, phase, ex, ey, position = 0;
  } edges[2];
  int longest = 0;
  for (int i = 0; i < 2; ++i) {
    auto &e = edges[i];
    e.point = q[i];
    e.dx = wrap(q[3 - i].x - q[i].x);
    e.dy = wrap(q[3 - i].y - q[i].y);
    e.length = std::max(std::abs(e.dx), std::abs(e.dy));
    longest = std::max(longest, e.length);
    e.ex = e.ey = wrap(~e.length);
  }
  longest &= 0xfff;
  for (auto &e : edges) e.phase = wrap(~longest);
  read_gouraud_table();
  const uint16_t colors[4] = {gouraud_shading.GA, gouraud_shading.GB, gouraud_shading.GC, gouraud_shading.GD};
  m_vdp1_texture_end.fill(-1);
  for (int row = 0; row <= longest; ++row) {
    uint16_t edge_color[2]{};
    if (current_sprite.CMDPMOD & 4) {
      for (int i = 0; i < 2; ++i) {
        for (int shift : {0, 5, 10}) {
          const int a = (colors[i] >> shift) & 31, b = (colors[3 - i] >> shift) & 31;
          const int value = std::min(a, b) + vdp1_scaled_coordinate(std::abs(b - a) + 1,
                                         edges[i].length + 1, edges[i].position, b < a);
          edge_color[i] |= value << shift;
        }
      }
    }
    const int v = current_sprite.ispoly ? -1 : width ?
        vdp1_scaled_coordinate(std::max(1, height), longest + 1, row, current_sprite.CMDCTRL & 0x20) : 0;
    vdp1_draw_segment(cliprect, edges[0].point, edges[1].point, edge_color[0], edge_color[1], true, v, width);
    for (auto &e : edges) {
      const int tx = e.dy < 0 ? -1 : 0, ty = e.dx < 0 ? -1 : 0;
      const int target = std::abs(e.dx) >= std::abs(e.dy) ? ty : tx;
      e.phase = wrap(e.phase + 2 * e.length);
      if (e.phase >= target) {
        e.phase = wrap(e.phase - 2 * longest);
        ++e.position;
        e.ex = wrap(e.ex + 2 * std::abs(e.dx));
        e.ey = wrap(e.ey + 2 * std::abs(e.dy));
        if (e.ex >= tx) { e.ex = wrap(e.ex - 2 * e.length); e.point.x += e.dx < 0 ? -1 : 1; }
        if (e.ey >= ty) { e.ey = wrap(e.ey - 2 * e.length); e.point.y += e.dy < 0 ? -1 : 1; }
      }
    }
  }
}

void saturn_state::vdp1_draw_distorted_sprite(const rectangle &cliprect) {
  const int width = current_sprite.ispoly ? 1 : ((current_sprite.CMDSIZE >> 8) & 0x3f) * 8;
  const int height = current_sprite.ispoly ? 1 : current_sprite.CMDSIZE & 0xff;
  if (!height)
    return; // prohibited character height
  spoint q[4]{};
  q[0].x = x2s(current_sprite.CMDXA); q[0].y = y2s(current_sprite.CMDYA);
  q[1].x = x2s(current_sprite.CMDXB); q[1].y = y2s(current_sprite.CMDYB);
  q[2].x = x2s(current_sprite.CMDXC); q[2].y = y2s(current_sprite.CMDYC);
  q[3].x = x2s(current_sprite.CMDXD); q[3].y = y2s(current_sprite.CMDYD);
  vdp1_draw_quad_pixels(cliprect, width, height, q);
}

void saturn_state::vdp1_draw_scaled_sprite(const rectangle &cliprect) {
  struct spoint q[4];

  int xsize, ysize;
  int direction;
  int patterndata;
  int zoompoint;
  direction = (current_sprite.CMDCTRL >> 4) & 3;
  xsize = ((current_sprite.CMDSIZE >> 8) & 0x3f) * 8;
  ysize = current_sprite.CMDSIZE & 0xff;
  patterndata = (current_sprite.CMDSRCA & 0xffff) * 8;
  zoompoint = (current_sprite.CMDCTRL >> 8) & 0xf;

  // Decode coordinates before anchor arithmetic. Re-decoding an adjusted
  // coordinate wraps it at bit 12, and taking abs(width) incorrectly combines
  // extent inversion with the independent texture read-direction bits.
  int left = x2s(current_sprite.CMDXA);
  int top = y2s(current_sprite.CMDYA);
  int right, bottom;
  if (zoompoint) {
    const int width = vdp1_coord(current_sprite.CMDXB);
    const int height = vdp1_coord(current_sprite.CMDYB);
    switch (zoompoint & 3) {
    case 2: left -= width >> 1; break;
    case 3: left -= width; break;
    }
    switch ((zoompoint >> 2) & 3) {
    case 2: top -= height >> 1; break;
    case 3: top -= height; break;
    }
    // Width/height are endpoint distances: zero still describes one dot.
    right = left + width;
    bottom = top + height;
  } else {
    right = x2s(current_sprite.CMDXC);
    bottom = y2s(current_sprite.CMDYC);
  }
  q[0].x = q[3].x = left;
  q[1].x = q[2].x = right;
  q[0].y = q[1].y = top;
  q[2].y = q[3].y = bottom;

  if (xsize == 0) {
    // see vdp1_draw_distorted_sprite: CMDSIZE.H = 0 means the pattern has
    // no width and only the first texel is ever fetched
    q[0].u = q[1].u = q[2].u = q[3].u = 0;
  } else if (direction & 1) { // xflip
    q[0].u = q[3].u = xsize - 1;
    q[1].u = q[2].u = 0;
  } else {
    q[0].u = q[3].u = 0;
    q[1].u = q[2].u = xsize - 1;
  }
  if (direction & 2) { // yflip
    q[0].v = q[1].v = ysize - 1;
    q[2].v = q[3].v = 0;
  } else {
    q[0].v = q[1].v = 0;
    q[2].v = q[3].v = ysize - 1;
  }

  if (ysize <= 0 && xsize > 0)
    vdp1_setup_shading(q, cliprect);
  else
    vdp1_setup_rectangle_shading(q, cliprect);
  vdp1_trace("scaled", -1, q);
  vdp1_draw_scaled_pixels(cliprect, patterndata, xsize, ysize, q);
}

int saturn_state::vdp1_scaled_coordinate(int source, int destination, int pixel, bool reverse) {
  if (source <= 1)
    return 0;
  // Closed form of the integer texture-error accumulator. Reduction advances
  // over all source texels; enlargement repeats them. Direction affects ties.
  // ST-013 pp.81-82, cross-checked with MiSTer TEXT_ERROR and Ymir's stepper.
  const bool shrink = destination < source;
  const int increment = 2 * (shrink ? source : source - 1);
  const int adjustment = 2 * (shrink ? destination : destination - 1);
  const int initial = shrink ? source - 2 * destination - int(reverse) : -destination + int(reverse);
  const int64_t error = int64_t(initial) + int64_t(pixel) * increment;
  const int steps = error < 0 ? 0 : int(error / adjustment) + 1;
  return reverse ? source - 1 - steps : steps;
}

void saturn_state::vdp1_draw_scaled_pixels(const rectangle &cliprect, int address,
                                            int width, int height, const spoint *q) {
  if (height <= 0 && width > 0) {
    // Preserve the legacy fallback for the unspecified zero-height pattern.
    vdp1_fill_quad(cliprect, address, width, q);
    return;
  }
  const bool preclip_enabled = !(current_sprite.CMDPMOD & 0x0800);
  const int columns = std::abs(q[1].x - q[0].x) + 1;
  const int rows = std::abs(q[3].y - q[0].y) + 1;
  const int left = preclip_enabled ? std::max({std::min(q[0].x, q[1].x), cliprect.min_x, 0}) : std::min(q[0].x, q[1].x);
  const int right = preclip_enabled ? std::min({std::max(q[0].x, q[1].x), cliprect.max_x, 1023}) : std::max(q[0].x, q[1].x);
  const int top = preclip_enabled ? std::max({std::min(q[0].y, q[3].y), cliprect.min_y, 0}) : std::min(q[0].y, q[3].y);
  const int bottom = preclip_enabled ? std::min({std::max(q[0].y, q[3].y), cliprect.max_y, 511}) : std::max(q[0].y, q[3].y);
  if (left > right || top > bottom)
    return;

  if (m_vdp1_raster_building) {
    for (int y = top; y <= bottom; ++y) {
      const int v = width ? vdp1_scaled_coordinate(height, rows, std::abs(y - q[0].y),
          current_sprite.CMDCTRL & 0x20) : 0;
      const std::array<int32_t, vdp1_raster_state::segment_words> span = {
          left, y, right, y, q[0].x, columns, 0, 0, 0, 0, -2, v, width};
      assert(m_vdp1_raster.count < vdp1_raster_state::max_segments);
      std::copy(span.begin(), span.end(), m_vdp1_raster.segments.begin() +
          vdp1_raster_state::segment_words * m_vdp1_raster.count++);
    }
    return;
  }

  const bool hss = (current_sprite.CMDPMOD & 0x1000) && columns < width;
  const bool flip_x = current_sprite.CMDCTRL & 0x10;
  const bool flip_y = current_sprite.CMDCTRL & 0x20;
  const int source_columns = std::max(1, hss ? width / 2 : width);
  // Synchronous reference/fallback only: queued execution returned above.
  // Index relative to the span, since Pclp=1 permits negative/offscreen X.
  std::vector<int> source_x(right - left + 1);
  for (int x = left; x <= right; ++x) {
    const int u = vdp1_scaled_coordinate(source_columns, columns, std::abs(x - q[0].x), flip_x);
    source_x[x - left] = hss ? u * 2 + m_vdp1_legacy.draw_eos : u;
  }

  // Effective mode for this atomic primitive, not a write to guest VRAM.
  // HSS reduction bypasses two-END row termination, not the ECD-controlled
  // rejection of an individual END texel. Keep effective HSS for the row
  // helper, but never force ECD: LUT END entries can contain opaque black.
  // Ymir VDP1PlotTexturedLine and MiSTer IS_PAT_EC/FB_DRAW_WE agree. This
  // differs from the HSS-reduction wording in the ST-013 p.86 table.
  const uint16_t mode = current_sprite.CMDPMOD;
  current_sprite.CMDPMOD = (mode & ~0x1000) | (hss ? 0x1000 : 0);
  m_vdp1_texture_end.fill(-1);
  for (int y = top; y <= bottom; ++y) {
    const int v = width ? vdp1_scaled_coordinate(height, rows, std::abs(y - q[0].y), flip_y) : 0;
    for (int x = left; x <= right; ++x) {
      const int texel = v * width + source_x[x - left];
      if (vdp1_texture_sample_visible(address, width, texel))
        (this->*drawpixel)(x, y, address, texel);
    }
  }
  current_sprite.CMDPMOD = mode;
}

bool saturn_state::vdp1_texture_sample_visible(int address, int width, int texel) {
  // ST-013 p.86: END acts in source-row order, not destination-dot order.
  // Scan each referenced row once, including texels skipped during reduction;
  // enlargement must not count repeated samples of the same END twice.
  // HSS reduction has no two-END cutoff. The pixel writer still rejects
  // each sampled END when ECD=0; HSS must not imply ECD=1.
  if (current_sprite.ispoly || (current_sprite.CMDPMOD & 0x1080) || width <= 0)
    return true;
  const int row = texel / width;
  if (texel < 0 || row >= 256)
    return true; // no specified row semantics for an invalid character size
  const bool reverse = current_sprite.CMDCTRL & 0x10;
  int16_t &limit = m_vdp1_texture_end[row];
  if (limit < 0) {
    limit = width;
    unsigned count = 0;
    for (int i = 0; i < width; ++i) {
      const int u = reverse ? width - 1 - i : i;
      if (vdp1_is_end_code(address, row * width + u) && ++count == 2) {
        limit = i;
        break;
      }
    }
  }
  const int u = texel % width;
  return (reverse ? width - 1 - u : u) < limit;
}

bool saturn_state::vdp1_is_end_code(int address, int texel) const {
  switch ((current_sprite.CMDPMOD >> 3) & 7) {
  case 0:
  case 1: {
    const uint8_t value = m_vdp1_legacy.gfx_decode[(address + texel / 2) & 0x7ffff];
    return ((value >> ((texel & 1) ? 0 : 4)) & 0xf) == 0xf;
  }
  case 2:
  case 3:
  case 4:
    return m_vdp1_legacy.gfx_decode[(address + texel) & 0x7ffff] == 0xff;
  case 5:
    address = ((address & ~0xf) + texel * 2) & 0x7ffff;
    return m_vdp1_legacy.gfx_decode[address] == 0x7f &&
           m_vdp1_legacy.gfx_decode[(address + 1) & 0x7ffff] == 0xff;
  default:
    return false; // prohibited color modes have no documented end code
  }
}

void saturn_state::vdp1_draw_normal_sprite(const rectangle &cliprect,
                                           int sprite_type) {
  int y, ysize, drawypos;
  int x, xsize, drawxpos;
  int direction;
  int patterndata;
  uint8_t shading;
  int su, u, dux, duy;
  int maxdrawypos, maxdrawxpos;
  // ST-013 p.83: Pclp=1 disables advance rejection/skipping, not pixel
  // clipping. Fetch/count END markers even before entering the drawing area.
  // CMDSIZE bounds this traversal to 504 by 255 positions per command.
  const bool preclip = !(current_sprite.CMDPMOD & 0x0800);

  x = x2s(current_sprite.CMDXA);
  y = y2s(current_sprite.CMDYA);

  direction = (current_sprite.CMDCTRL & 0x0030) >> 4;

  xsize = (current_sprite.CMDSIZE & 0x3f00) >> 8;
  xsize = xsize * 8;

  ysize = (current_sprite.CMDSIZE & 0x00ff);

  patterndata = (current_sprite.CMDSRCA) & 0xffff;
  patterndata = patterndata * 0x8;

  if (xsize > 0 && ysize > 0) {
    const spoint bounds[4] = {{x, y, 0, 0}, {},
        {x + xsize - 1, y + ysize - 1, 0, 0}, {}};
    vdp1_trace("normal", -1, bounds);
  }

  if (VDP1_LOG)
    logerror("Drawing Normal Sprite x %04x y %04x xsize %04x ysize %04x "
             "patterndata %06x\n",
             x, y, xsize, ysize, patterndata);

  if (preclip && x > cliprect.max_x)
    return;
  if (preclip && y > cliprect.max_y)
    return;

  shading = read_gouraud_table();
  if (shading) {
    struct spoint q[4];
    q[0].x = x;
    q[0].y = y;
    q[1].x = x + xsize - 1;
    q[1].y = y;
    q[2].x = x + xsize - 1;
    q[2].y = y + ysize - 1;
    q[3].x = x;
    q[3].y = y + ysize - 1;

    if (xsize > 0 && ysize > 0)
      vdp1_setup_rectangle_shading(q, cliprect);
  }

  u = 0;
  dux = 1;
  duy = xsize;
  if (direction & 0x1) // xflip
  {
    dux = -1;
    u = xsize - 1;
  }
  if (direction & 0x2) // yflip
  {
    duy = -xsize;
    u += xsize * (ysize - 1);
  }
  if (preclip && y < cliprect.min_y) // clip y
  {
    // draculax user clips a 320x240 sprite for inverted castle map (obviously x
    // & y flipped) we need to adjust U calculation only to make it align
    // properly, adjusting ysize will already glitch out flipped doors in
    // gameplay.
    const int adjust_y =
        direction & 2 ? y - cliprect.min_y : cliprect.min_y - y;
    u += xsize * (adjust_y);
    ysize -= (cliprect.min_y - y);
    y = cliprect.min_y;
  }
  if (preclip && x < cliprect.min_x) // clip x
  {
    u += dux * (cliprect.min_x - x);
    xsize -= (cliprect.min_x - x);
    x = cliprect.min_x;
  }
  // Only the pre-clipped path shortens traversal to visible bounds. Pixel
  // writers still enforce framebuffer/system/user clipping in either mode.
  maxdrawypos = preclip ? std::min({y + ysize - 1, cliprect.max_y, 511}) : y + ysize - 1;
  maxdrawxpos = preclip ? std::min({x + xsize - 1, cliprect.max_x, 1023}) : x + xsize - 1;
  for (drawypos = y; drawypos <= maxdrawypos; drawypos++) {
    // destline = m_vdp1_legacy.framebuffer_draw_lines[drawypos];
    su = u;
    if (m_vdp1_raster_building) {
      if (x <= maxdrawxpos) {
        const std::array<int32_t, vdp1_raster_state::segment_words> span = {
            x, drawypos, maxdrawxpos, drawypos, dux, 0, 0, 0, 0, 0, -1, u, 0};
        assert(m_vdp1_raster.count < vdp1_raster_state::max_segments);
        std::copy(span.begin(), span.end(), m_vdp1_raster.segments.begin() +
            vdp1_raster_state::segment_words * m_vdp1_raster.count++);
      }
      u = su + duy;
      continue;
    }
    unsigned end_codes = 0;
    for (drawxpos = x; drawxpos <= maxdrawxpos; drawxpos++) {
      // ST-013 section 6.3: the second fetched end code terminates this
      // texture row, independently of SPD. Count source texels, not writes.
      if (!(current_sprite.CMDPMOD & 0x80) && vdp1_is_end_code(patterndata, u)) {
        if (++end_codes == 2)
          break;
      }
      (this->*drawpixel)(drawxpos, drawypos, patterndata, u);
      u += dux;
    }
    u = su + duy;
  }
}

void saturn_state::vdp1_abort_draw() {
  if (m_vdp1_legacy.drawing)
    vdp1_trace("abort");
  // Cancel both command dispatch and any delayed ENDR request. No completion
  // IRQ is manufactured; COPR remains at the last fetched command.
  m_vdp1_legacy.drawing = false;
  vdp1_reset_raster_queue();
  m_vdp1_raster_building = m_vdp1_raster_running = false;
  m_vdp1_raster_budget = 0;
  if (m_vdp1_legacy.draw_end_timer)
    m_vdp1_legacy.draw_end_timer->adjust(attotime::never);
  if (m_vdp1_legacy.terminate_timer)
    m_vdp1_legacy.terminate_timer->adjust(attotime::never);
}

void saturn_state::vdp1_request_termination() {
  // ST-013 section 4.5 specifies approximately 30 VDP1 clocks. Keep command
  // execution live during that interval rather than stopping at the write.
  // Legal nonzero-height primitive paths yield in saved raster slices.
  if (m_vdp1_legacy.drawing)
    m_vdp1_legacy.terminate_timer->adjust(m_maincpu->cycles_to_attotime(30));
}

TIMER_CALLBACK_MEMBER(saturn_state::vdp1_terminate) {
  vdp1_abort_draw();
}

void saturn_state::vdp1_process_list() {
  vdp1_abort_draw();
  m_vdp1_legacy.command_position = 0;
  m_vdp1_legacy.command_return = -1;
  m_vdp1_legacy.copr = 0;
  m_vdp1_legacy.drawing = true;
  clear_gouraud_shading();
  CEF_0();
  vdp1_trace("start");
  // Fetch cost as in Ymir VDP1ProcessCommand. All legal primitives then
  // advance in bounded raster slices. Bus arbitration costs remain incomplete.
  m_vdp1_legacy.draw_end_timer->adjust(m_maincpu->cycles_to_attotime(16));
}

TIMER_CALLBACK_MEMBER(saturn_state::vdp1_draw_end) {
  // This timer now advances the command engine, rather than estimating the
  // completion of a whole synchronously rendered list. Loops yield to the
  // scheduler and see CPU VRAM edits on the next fetch, with no host list cap.
  if (!m_vdp1_legacy.drawing)
    return;

  if (m_vdp1_raster.index < m_vdp1_raster.count) {
    vdp1_draw_raster_slice();
    m_vdp1_legacy.draw_end_timer->adjust(m_maincpu->cycles_to_attotime(vdp1_raster_slice_cycles()));
    return; // Never fetch END or another command while a segment is pending.
  }

  int &position = m_vdp1_legacy.command_position;
  int &vdp1_nest = m_vdp1_legacy.command_return;
  rectangle *cliprect;

  {
    int draw_this_sprite = 1;
    position &= 0x3fff;
    m_vdp1_legacy.copr = position << 2;
    current_sprite.CMDCTRL = m_vdp1_vram[position * 8] >> 16;
    if (current_sprite.CMDCTRL & 0x8000) {
      m_vdp1_legacy.drawing = false;
      m_vdp1_legacy.terminate_timer->adjust(attotime::never);
      CEF_1();
      vdp1_trace("end");
      m_scu->vdp1_end_w(1);
      return;
    }

    current_sprite.CMDLINK =
        (m_vdp1_vram[position * (0x20 / 4) + 0] & 0x0000ffff) >> 0;
    current_sprite.CMDPMOD =
        (m_vdp1_vram[position * (0x20 / 4) + 1] & 0xffff0000) >> 16;
    current_sprite.CMDCOLR =
        (m_vdp1_vram[position * (0x20 / 4) + 1] & 0x0000ffff) >> 0;
    current_sprite.CMDSRCA =
        (m_vdp1_vram[position * (0x20 / 4) + 2] & 0xffff0000) >> 16;
    current_sprite.CMDSIZE =
        (m_vdp1_vram[position * (0x20 / 4) + 2] & 0x0000ffff) >> 0;
    current_sprite.CMDXA =
        (m_vdp1_vram[position * (0x20 / 4) + 3] & 0xffff0000) >> 16;
    current_sprite.CMDYA =
        (m_vdp1_vram[position * (0x20 / 4) + 3] & 0x0000ffff) >> 0;
    current_sprite.CMDXB =
        (m_vdp1_vram[position * (0x20 / 4) + 4] & 0xffff0000) >> 16;
    current_sprite.CMDYB =
        (m_vdp1_vram[position * (0x20 / 4) + 4] & 0x0000ffff) >> 0;
    current_sprite.CMDXC =
        (m_vdp1_vram[position * (0x20 / 4) + 5] & 0xffff0000) >> 16;
    current_sprite.CMDYC =
        (m_vdp1_vram[position * (0x20 / 4) + 5] & 0x0000ffff) >> 0;
    current_sprite.CMDXD =
        (m_vdp1_vram[position * (0x20 / 4) + 6] & 0xffff0000) >> 16;
    current_sprite.CMDYD =
        (m_vdp1_vram[position * (0x20 / 4) + 6] & 0x0000ffff) >> 0;
    current_sprite.CMDGRDA =
        (m_vdp1_vram[position * (0x20 / 4) + 7] & 0xffff0000) >> 16;
    //      current_sprite.UNUSED  = (m_vdp1_vram[position * (0x20/4)+7] &
    //      0x0000ffff) >> 0;

    /* proecess jump / skip commands, set position for next sprite */
    switch (current_sprite.CMDCTRL & 0x7000) {
    case 0x0000: // jump next
      if (VDP1_LOG)
        logerror("Sprite List Process + Next (Normal)\n");
      position++;
      break;
    case 0x1000: // jump assign
      if (VDP1_LOG)
        logerror("Sprite List Process + Jump Old %06x New %06x\n", position,
                 (current_sprite.CMDLINK >> 2));
      position = (current_sprite.CMDLINK >> 2);
      break;
    case 0x2000: // jump call
      if (vdp1_nest == -1) {
        if (VDP1_LOG)
          logerror("Sprite List Process + Call Old %06x New %06x\n", position,
                   (current_sprite.CMDLINK >> 2));
        vdp1_nest = position + 1;
        position = (current_sprite.CMDLINK >> 2);
      } else {
        if (VDP1_LOG)
          logerror("Sprite List Nested Call, ignoring\n");
        position++;
      }
      break;
    case 0x3000:
      if (vdp1_nest != -1) {
        if (VDP1_LOG)
          logerror("Sprite List Process + Return\n");
        position = vdp1_nest;
        vdp1_nest = -1;
      } else {
        if (VDP1_LOG)
          logerror("Attempted return from no subroutine, aborting\n");
        position++;
        goto end; // end of list
      }
      break;
    case 0x4000:
      draw_this_sprite = 0;
      position++;
      break;
    case 0x5000:
      if (VDP1_LOG)
        logerror("Sprite List Skip + Jump Old %06x New %06x\n", position,
                 (current_sprite.CMDLINK >> 2));
      draw_this_sprite = 0;
      position = (current_sprite.CMDLINK >> 2);

      break;
    case 0x6000:
      draw_this_sprite = 0;
      if (vdp1_nest == -1) {
        if (VDP1_LOG)
          logerror("Sprite List Skip + Call To Subroutine Old %06x New %06x\n",
                   position, (current_sprite.CMDLINK >> 2));

        vdp1_nest = position + 1;
        position = (current_sprite.CMDLINK >> 2);
      } else {
        if (VDP1_LOG)
          logerror("Sprite List Nested Call, ignoring\n");
        position++;
      }
      break;
    case 0x7000:
      draw_this_sprite = 0;
      if (vdp1_nest != -1) {
        if (VDP1_LOG)
          logerror("Sprite List Skip + Return from Subroutine\n");

        position = vdp1_nest;
        vdp1_nest = -1;
      } else {
        if (VDP1_LOG)
          logerror("Attempted return from no subroutine, aborting\n");
        position++;
        goto end; // end of list
      }
      break;
    }

    /* continue to draw this sprite only if the command wasn't to skip it */
    if (draw_this_sprite == 1) {
      // Outside clipping needs the system rectangle for rasterization;
      // vdp1_pixel_visible rejects pixels inside the excluded user rectangle.
      if ((current_sprite.CMDPMOD & 0x0600) == 0x0400)
        cliprect = &m_vdp1_legacy.user_cliprect;
      else
        cliprect = &m_vdp1_legacy.system_cliprect;

      vdp1_set_drawpixel();

      switch (current_sprite.CMDCTRL & 0x000f) {
      case 0x0000:
        if (VDP1_LOG)
          logerror("Sprite List Normal Sprite (%d %d)\n", current_sprite.CMDXA,
                   current_sprite.CMDYA);
        current_sprite.ispoly = 0;
        vdp1_reset_raster_queue();
        m_vdp1_raster_building = true;
        vdp1_draw_normal_sprite(*cliprect, 0);
        m_vdp1_raster_building = false;
        break;

      case 0x0001:
        if (VDP1_LOG)
          logerror("Sprite List Scaled Sprite (%d %d)\n", current_sprite.CMDXA,
                   current_sprite.CMDYA);
        current_sprite.ispoly = 0;
        vdp1_reset_raster_queue();
        m_vdp1_raster_building = true;
        vdp1_draw_scaled_sprite(*cliprect);
        m_vdp1_raster_building = false;
        break;

      case 0x0002:
      case 0x0003: // used by Hardcore 4x4
        if (VDP1_LOG)
          logerror("Sprite List Distorted Sprite\n");
        if (VDP1_LOG)
          logerror("(A: %d %d)\n", current_sprite.CMDXA, current_sprite.CMDYA);
        if (VDP1_LOG)
          logerror("(B: %d %d)\n", current_sprite.CMDXB, current_sprite.CMDYB);
        if (VDP1_LOG)
          logerror("(C: %d %d)\n", current_sprite.CMDXC, current_sprite.CMDYC);
        if (VDP1_LOG)
          logerror("(D: %d %d)\n", current_sprite.CMDXD, current_sprite.CMDYD);
        if (VDP1_LOG)
          logerror("CMDPMOD = %04x\n", current_sprite.CMDPMOD);

        current_sprite.ispoly = 0;
        vdp1_reset_raster_queue();
        m_vdp1_raster_building = true;
        vdp1_draw_distorted_sprite(*cliprect);
        m_vdp1_raster_building = false;
        break;

      case 0x0004:
        if (VDP1_LOG)
          logerror("Sprite List Polygon\n");
        current_sprite.ispoly = 1;
        vdp1_reset_raster_queue();
        m_vdp1_raster_building = true;
        vdp1_draw_distorted_sprite(*cliprect);
        m_vdp1_raster_building = false;
        break;

      case 0x0005:
      case 0x0007: // mirror? baroque/samsho4
        if (VDP1_LOG)
          logerror("Sprite List Polyline\n");
        current_sprite.ispoly = 1;
        vdp1_reset_raster_queue();
        m_vdp1_raster_building = true;
        vdp1_draw_poly_line(*cliprect);
        m_vdp1_raster_building = false;
        break;

      case 0x0006:
        if (VDP1_LOG)
          logerror("Sprite List Line\n");
        current_sprite.ispoly = 1;
        vdp1_reset_raster_queue();
        m_vdp1_raster_building = true;
        vdp1_draw_line(*cliprect);
        m_vdp1_raster_building = false;
        break;

      case 0x0008:
        //              case 0x000b: // mirror? Bug 2
        if (VDP1_LOG)
          logerror(
              "Sprite List Set Command for User Clipping (%d,%d),(%d,%d)\n",
              current_sprite.CMDXA, current_sprite.CMDYA, current_sprite.CMDXC,
              current_sprite.CMDYC);
        // clip coordinates are 13-bit fields as well, but unsigned
        m_vdp1_legacy.user_cliprect.set(
            current_sprite.CMDXA & 0x1fff, current_sprite.CMDXC & 0x1fff,
            current_sprite.CMDYA & 0x1fff, current_sprite.CMDYC & 0x1fff);
        break;

      case 0x0009:
        if (VDP1_LOG)
          logerror(
              "Sprite List Set Command for System Clipping (0,0),(%d,%d)\n",
              current_sprite.CMDXC, current_sprite.CMDYC);
        m_vdp1_legacy.system_cliprect.set(0, current_sprite.CMDXC & 0x1fff, 0,
                                          current_sprite.CMDYC & 0x1fff);
        break;

      case 0x000a:
        if (VDP1_LOG)
          logerror("Sprite List Local Co-Ordinate Set (%d %d)\n",
                   (int16_t)current_sprite.CMDXA,
                   (int16_t)current_sprite.CMDYA);
        m_vdp1_legacy.local_x = vdp1_coord(current_sprite.CMDXA);
        m_vdp1_legacy.local_y = vdp1_coord(current_sprite.CMDYA);
        break;

      default:
        // asenna 0x0c or 0x0d (transition from title screen)
        // raymanj 0x0d (at startup)
        // choroqpk 0x0e (when selecting island in main menu)
        // albodysj 0x0f (always)
        if ((current_sprite.CMDCTRL & 0x000f) < 0xc)
          popmessage("VDP1: Sprite List Illegal %02x at %04x",
                     current_sprite.CMDCTRL & 0xf, m_vdp1_legacy.copr);
        // Abort this unsupported command, but do not claim END was fetched.
        // Exact illegal-command progression remains unimplemented.
        goto end;
      }
    }
  }

  m_vdp1_legacy.draw_end_timer->adjust(m_maincpu->cycles_to_attotime(vdp1_raster_slice_cycles()));
  return;

end:
  // Undocumented/prohibited command flow is not a successful END fetch.
  vdp1_abort_draw();
}

void saturn_state::vdp1_video_update() {
  vdp1_trace("field");
  vdp1_finish_display_erase();
  vdp1_finish_vblank_erase();
  const bool blank_only = (VDP1_TVM() & 2) || VDP1_TVM() == 4;
  bool framebuffer_changed = false;
  switch (VDP1_FBCR & 3) {
  case 0: // One-cycle mode
    vdp1_change_framebuffers();
    if (blank_only)
      m_vdp1_legacy.vblank_erase_pending = true;
    else
      vdp1_begin_display_erase();
    framebuffer_changed = true;
    break;
  case 2: // One-field manual erase request, without exchanging banks
    if (m_vdp1_legacy.fbcr_accessed) {
      if (blank_only)
        m_vdp1_legacy.vblank_erase_pending = true;
      else
        vdp1_begin_display_erase();
    }
    break;
  case 3: // One-field manual change request; VBE erase ran during blanking
    if (m_vdp1_legacy.fbcr_accessed) {
      vdp1_change_framebuffers();
      framebuffer_changed = true;
    }
    break;
  default: // FCM=0,FCT=1 is prohibited
    break;
  }
  m_vdp1_legacy.fbcr_accessed = 0;
  if (framebuffer_changed && (VDP1_PTM & 3) == 2)
    vdp1_process_list();
}

void saturn_state::vdp1_state_save_postload() {
  uint8_t *vdp1 = m_vdp1_legacy.gfx_decode.get();
  int offset;
  uint32_t data;

  // Restore derived views only. Do not latch pending register writes across
  // a framebuffer boundary that has not happened in the restored machine.
  vdp1_prepare_framebuffers();

  for (offset = 0; offset < 0x80000 / 4; offset++) {
    data = m_vdp1_vram[offset];
    /* put in gfx region for easy decoding */
    vdp1[offset * 4 + 0] = (data & 0xff000000) >> 24;
    vdp1[offset * 4 + 1] = (data & 0x00ff0000) >> 16;
    vdp1[offset * 4 + 2] = (data & 0x0000ff00) >> 8;
    vdp1[offset * 4 + 3] = (data & 0x000000ff) >> 0;
  }
}

int saturn_state::vdp1_start() {
  m_vdp1_regs = make_unique_clear<uint16_t[]>(0x020 / 2);
  m_vdp1_vram = make_unique_clear<uint32_t[]>(0x100000 / 4);
  m_vdp1_legacy.gfx_decode = std::make_unique<uint8_t[]>(0x100000);

  vdp1_shading_data = std::make_unique<struct vdp1_poly_scanline_data>();

  // Two physical 2-Mbit banks, plus host-only completed-field weave caches.
  for (unsigned bank = 0; bank < 2; ++bank) {
    m_vdp1_legacy.framebuffer[bank] = std::make_unique<uint16_t[]>(0x20000);
    m_vdp1_legacy.field_framebuffer[bank] = std::make_unique<uint16_t[]>(0x20000);
  }

  m_vdp1_legacy.framebuffer_display_lines = std::make_unique<uint16_t *[]>(512);
  m_vdp1_legacy.framebuffer_draw_lines = std::make_unique<uint16_t *[]>(512);

  m_vdp1_legacy.framebuffer_width = m_vdp1_legacy.framebuffer_height = 0;
  m_vdp1_legacy.framebuffer_mode = -1;
  m_vdp1_legacy.framebuffer_double_interlace = -1;
  m_vdp1_legacy.fbcr_accessed = 0;
  vdp1_reset_framebuffers();
  vdp1_clear_framebuffer(m_vdp1_legacy.framebuffer_current_draw);

  m_vdp1_legacy.system_cliprect.set(0, 0, 0, 0);
  /* Kidou Senshi Z Gundam - Zenpen Zeta no Kodou loves to use the user cliprect
   * vars in an undefined state ... */
  m_vdp1_legacy.user_cliprect.set(0, 512, 0, 256);

  m_vdp1_legacy.draw_end_timer =
      timer_alloc(FUNC(saturn_state::vdp1_draw_end), this);
  m_vdp1_legacy.terminate_timer =
      timer_alloc(FUNC(saturn_state::vdp1_terminate), this);
  // save state
  save_item(NAME(m_vdp1_raster.segments));
  save_item(NAME(m_vdp1_raster.count));
  save_item(NAME(m_vdp1_raster.index));
  save_item(NAME(m_vdp1_raster.dot));
  save_item(NAME(m_vdp1_raster.x));
  save_item(NAME(m_vdp1_raster.y));
  save_item(NAME(m_vdp1_raster.error));
  save_item(NAME(m_vdp1_raster.extra));
  save_item(NAME(m_vdp1_raster.end_codes));
  // Rectangular Gouraud interpolation is prepared at command fetch. Preserve
  // those coefficients, rather than re-reading a possibly edited VRAM table.
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, integer));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, x));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, r));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, g));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, b));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, dr));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, dg));
  save_item(STRUCT_MEMBER(vdp1_shading_data->scanline, db));

  save_item(NAME(m_vdp1_display_erase.pending));
  save_item(NAME(m_vdp1_display_erase.bank));
  save_item(NAME(m_vdp1_display_erase.data));
  save_item(NAME(m_vdp1_display_erase.left));
  save_item(NAME(m_vdp1_display_erase.right));
  save_item(NAME(m_vdp1_display_erase.top));
  save_item(NAME(m_vdp1_display_erase.bottom));
  save_item(NAME(m_vdp1_display_erase.next_row));
  save_item(NAME(m_vdp1_display_erase.step));

  save_item(NAME(m_vdp1_texture_end));
  save_item(NAME(current_sprite.CMDCTRL));
  save_item(NAME(current_sprite.CMDLINK));
  save_item(NAME(current_sprite.CMDPMOD));
  save_item(NAME(current_sprite.CMDCOLR));
  save_item(NAME(current_sprite.CMDSRCA));
  save_item(NAME(current_sprite.CMDSIZE));
  save_item(NAME(current_sprite.CMDXA));
  save_item(NAME(current_sprite.CMDYA));
  save_item(NAME(current_sprite.CMDXB));
  save_item(NAME(current_sprite.CMDYB));
  save_item(NAME(current_sprite.CMDXC));
  save_item(NAME(current_sprite.CMDYC));
  save_item(NAME(current_sprite.CMDXD));
  save_item(NAME(current_sprite.CMDYD));
  save_item(NAME(current_sprite.CMDGRDA));
  save_item(NAME(current_sprite.ispoly));
  save_pointer(NAME(m_vdp1_legacy.framebuffer[0]), 0x20000);
  save_pointer(NAME(m_vdp1_legacy.framebuffer[1]), 0x20000);
  save_pointer(NAME(m_vdp1_legacy.field_framebuffer[0]), 0x20000);
  save_pointer(NAME(m_vdp1_legacy.field_framebuffer[1]), 0x20000);
  save_item(NAME(m_vdp1_legacy.draw_field));
  save_item(NAME(m_vdp1_legacy.field_valid));
  save_pointer(NAME(m_vdp1_regs), 0x020 / 2);
  save_pointer(NAME(m_vdp1_vram), 0x100000 / 4);
  save_item(NAME(m_vdp1_legacy.fbcr_accessed));
  save_item(NAME(m_vdp1_legacy.framebuffer_current_display));
  save_item(NAME(m_vdp1_legacy.framebuffer_current_draw));
  save_item(NAME(m_vdp1_legacy.local_x));
  save_item(NAME(m_vdp1_legacy.local_y));

  // VDP1 state cached outside m_vdp1_regs: EWDR is the pixel value the erase
  // function actually writes, and LOPR/COPR are what the 0x12/0x14 register
  // reads return, so these are live state rather than derived copies
  save_item(NAME(m_vdp1_legacy.ewdr));
  save_item(NAME(m_vdp1_legacy.erase_upper_left));
  save_item(NAME(m_vdp1_legacy.erase_lower_right));
  save_item(NAME(m_vdp1_legacy.vblank_erase_pending));
  save_item(NAME(m_vdp1_legacy.vblank_erase_active));
  save_item(NAME(m_vdp1_legacy.vblank_erase_bank));
  save_item(NAME(m_vdp1_legacy.vblank_erase_stride));
  save_item(NAME(m_vdp1_legacy.vblank_erase_data));
  save_item(NAME(m_vdp1_legacy.vblank_erase_left));
  save_item(NAME(m_vdp1_legacy.vblank_erase_right));
  save_item(NAME(m_vdp1_legacy.vblank_erase_top));
  save_item(NAME(m_vdp1_legacy.vblank_erase_bottom));
  save_item(NAME(m_vdp1_legacy.vblank_erase_budget));
  save_item(NAME(m_vdp1_legacy.vblank_erase_x));
  save_item(NAME(m_vdp1_legacy.vblank_erase_y));
  save_item(NAME(m_vdp1_legacy.vblank_erase_words_per_line));
  save_item(NAME(m_vdp1_legacy.vblank_erase_step));

  save_item(NAME(m_vdp1_legacy.draw_eos));
  save_item(NAME(m_vdp1_legacy.lopr));
  save_item(NAME(m_vdp1_legacy.copr));
  save_item(NAME(m_vdp1_legacy.drawing));
  save_item(NAME(m_vdp1_legacy.command_position));
  save_item(NAME(m_vdp1_legacy.command_return));

  // framebuffer geometry latched from TVMR/DIE; double_interlace is also read
  // back outside the reconfiguration guard
  save_item(NAME(m_vdp1_legacy.framebuffer_mode));
  save_item(NAME(m_vdp1_legacy.framebuffer_double_interlace));
  save_item(NAME(m_vdp1_legacy.framebuffer_width));
  save_item(NAME(m_vdp1_legacy.framebuffer_height));

  // clipping programmed by the System/User Clipping commands and applied to
  // every subsequent draw; rectangle is not an atom so save the bounds directly
  save_item(NAME(m_vdp1_legacy.system_cliprect.min_x));
  save_item(NAME(m_vdp1_legacy.system_cliprect.max_x));
  save_item(NAME(m_vdp1_legacy.system_cliprect.min_y));
  save_item(NAME(m_vdp1_legacy.system_cliprect.max_y));
  save_item(NAME(m_vdp1_legacy.user_cliprect.min_x));
  save_item(NAME(m_vdp1_legacy.user_cliprect.max_x));
  save_item(NAME(m_vdp1_legacy.user_cliprect.min_y));
  save_item(NAME(m_vdp1_legacy.user_cliprect.max_y));
  machine().save().register_postload(save_prepost_delegate(
      FUNC(saturn_state::vdp1_state_save_postload), this));
  return 0;
}

/**********************************************************************************************************************/

/* Sega Saturn VDP2 */

/*

-------------------------- WARNING WARNING WARNING --------------------------
This is a legacy core, all game based notes are for a future device rewrite.
Please don't remove them if for no reason you truly want to mess with this.
-------------------------- WARNING WARNING WARNING --------------------------

the dirty marking stuff and tile decoding will probably be removed in the end
anyway as we'll need custom rendering code since mame's drawgfx / tilesytem
don't offer everything st-v needs

this system seems far too complex to use Mame's tilemap system

4 'scroll' planes (scroll screens)

the scroll planes have slightly different capabilities

NBG0
NBG1
NBG2
NBG3

2 'rotate' planes

RBG0
RBG1

-- other crap
EXBG (external)

-----------------------------------------------------------------------------------------------------------

Video emulation TODO:
-all games:
 \-priorities (check myfairld,thunt)
 \-complete windows effects
 \-mosaic effect
 \-ODD bit/H/V Counter not yet emulated properly
 \-Reduction enable bits (zooming limiters)
 \-Check if there are any remaining video registers that are yet to be macroized
& added to the rumble. -batmanfr:
 \-If you reset the game after the character selection screen,when you get again
to it there's garbage floating behind Batman. -elandore:
 \-(BTANB) priorities at the VS. screen apparently is wrong,but it's like this
on the Saturn version too. -hanagumi:
 \-ending screens have corrupt graphics. (*untested*)
-kiwames:
 \-(fixed) incorrect color emulation for the alpha blended flames on the title
screen,it's caused by a schizoid linescroll emulation quirk.
 \-the VDP1 sprites refresh is too slow,causing the "Draw by request" mode to
   flicker. Moved back to default ATM.
-pblbeach:
 \-Sprites are offset, because it doesn't clear vdp1 local coordinates set by
bios, I guess that they are cleared when some vdp1 register is written (kludged
for now) -prikura:
 \-Attract mode presentation has corrupted graphics in various places,probably
caused by incomplete framebuffer data delete. -seabass:
 \-(fixed) Player sprite is corrupt/missing during movements,caused by
incomplete framebuffer switching. -shienryu:
 \-level 2 background colors on statues, caused by special color calculation
usage (per dot); (Saturn games)
- scud the disposable assassin:
 \- when zooming on melee attack background gets pink, color calculation issue?
- virtual hydlide:
 \- transparent pens usage on most vdp1 items should be black instead.
 \- likewise "press start button" is the other way around, i.e. black pen where
it should be transparent instead.

Notes of Interest & Unclear features:

-the test mode / bios is drawn with layer NBG3;
-hanagumi puts a 'RED' dragon logo in tileram (base 0x64000, 4bpp, 8x8 tiles)
but its not displayed because its priority value is 0.Left-over?

-scrolling is screen display wise,meaning that a scrolling value is masked with
the screen resolution size values;

-H-Blank bit is INDIPENDENT of the V-Blank bit...trying to fix enable/disable it
during V-Blank period causes wrong gameplay speed in Golden Axe:The Duel.

-Bitmaps uses transparency pens,examples are:
\-elandore's energy bars;
\-mausuke's foreground(the one used on the playfield)
\-shanhigw's tile-based sprites;
The transparency pen table is like this:

|------------------|---------------------|
| Character count  | Transparency code   |
|------------------|---------------------|
| 16 colors        |=0x0 (4 bits)        |
| 256 colors       |=0x00 (8 bits)       |
| 2048 colors      |=0x000 (11 bits)     |
| 32,768 colors    |MSB=0 (bit 15)       |
| 16,770,000 colors|MSB=0 (bit 31)       |
|------------------|---------------------|
In other words,the first three types uses the offset and not the color
allocated.

-double density interlace setting (LSMD == 3) apparently does a lot of fancy
stuff in the graphics sizes.

-Debug key list(only if you enable the debug mode on top of this file):
    \-T: NBG3 layer toggle
    \-Y: NBG2 layer toggle
    \-U: NBG1 layer toggle
    \-I: NBG0 layer toggle
    \-O: SPRITE toggle
    \-K: RBG0 layer toggle
    \-W Decodes the graphics for F4 menu.
    \-M Stores VDP1 ram contents from a file.
    \-N Stores VDP1 ram contents into a file.
*/

#define TEST_FUNCTIONS 0
#define POPMESSAGE_DEBUG 0

enum {
  STV_TRANSPARENCY_PEN = 0x0,
  STV_TRANSPARENCY_NONE = 0x1,
  STV_TRANSPARENCY_ADD_BLEND = 0x2,
  STV_TRANSPARENCY_ALPHA = 0x4
};

#define DEBUG_DRAW_ROZ (0)

/*

-------------------------------------------------|-----------------------------|------------------------------
|  Function        |  Normal Scroll Screen                                     |
Rotation Scroll Screen     | |
|-----------------------------|-----------------------------|------------------------------
|                  | NBG0         | NBG1         | NBG2         | NBG3         |
RBG0         | RBG1         |
-------------------------------------------------|-----------------------------|------------------------------
| Character Colour | 16 colours   | 16 colours   | 16 colours   | 16 colours   |
16 colours   | 16 colours   | | Count            | 256 " "      | 256 " "      |
256 " "      | 256 " "      | 256 " "      | 256 " "      | |                  |
2048 " "     | 2048 " "     |              |              | 2048 " "     | 2048
" "     | |                  | 32768 " "    | 32768 " "    |              | |
32768 " "    | 32768 " "    | |                  | 16770000 " " |              |
|              | 16770000 " " | 16770000 " " |
-------------------------------------------------|-----------------------------|------------------------------
| Character Size   | 1x1 Cells , 2x2 Cells |
-------------------------------------------------|-----------------------------|------------------------------
| Pattern Name     | 1 word , 2 words | | Data Size        | |
-------------------------------------------------|-----------------------------|------------------------------
| Plane Size       | 1 H x 1 V 1 Pages ; 2 H x 1 V 1 Pages ; 2 H x 2 V Pages |
-------------------------------------------------|-----------------------------|------------------------------
| Plane Count      | 4                                                         |
16                          |
-------------------------------------------------|-----------------------------|------------------------------
| Bitmap Possible  | Yes                         | No                          |
Yes          | No           |
-------------------------------------------------|-----------------------------|------------------------------
| Bitmap Size      | 512 x 256                   | N/A                         |
512x256      | N/A          | |                  | 512 x 512                   |
| 512x512      |              | |                  | 1024 x 256 | | | | | | 1024
x 512                  |                             |              | |
-------------------------------------------------|-----------------------------|------------------------------
| Scale            | 0.25 x - 256 x              | None                        |
Any ?                       |
-------------------------------------------------|-----------------------------|------------------------------
| Rotation         | No                                                        |
Yes                         |
-------------------------------------------------|-----------------------------|-----------------------------|
| Linescroll       | Yes                         | No |
-------------------------------------------------|-----------------------------|------------------------------
| Column Scroll    | Yes                         | No |
-------------------------------------------------|-----------------------------|------------------------------
| Mosaic           | Yes                                                       |
Horizontal Only             |
-------------------------------------------------|-----------------------------|------------------------------

*/

/* 18000C - RESERVED
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

/* 18000E - r/w - RAMCTL - RAM Control
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |  CRKTE   |    --    | CRMD1    | CRMD0    |    --    |    --    | VRBMD
 | VRAMD    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | RDBSB11  | RDBSB10  | RDBSB01  | RDBSB00  | RDBSA11  | RDBSA10  |
 RDBSA01  | RDBSA00  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_RAMCTL (m_vdp2_regs[0x00e / 2])

#define VDP2_CRKTE ((VDP2_RAMCTL & 0x8000) >> 15)
#define VDP2_CRMD ((VDP2_RAMCTL & 0x3000) >> 12)
#define VDP2_RDBSB1 ((VDP2_RAMCTL & 0x00c0) >> 6)
#define VDP2_RDBSB0 ((VDP2_RAMCTL & 0x0030) >> 4)
#define VDP2_RDBSA1 ((VDP2_RAMCTL & 0x000c) >> 2)
#define VDP2_RDBSA0 ((VDP2_RAMCTL & 0x0003) >> 0)

/* 180010 - r/w - -CYCA0L - VRAM CYCLE PATTERN (BANK A0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP0A03  | VCP0A02  | VCP0A01  | VCP0A00  | VCP1A03  | VCP1A02  |
 VCP1A01  | VCP1A00  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP2A03  | VCP2A02  | VCP2A01  | VCP2A00  | VCP3A03  | VCP3A02  |
 VCP3A01  | VCP3A00  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA0L (m_vdp2_regs[0x010 / 2])

/* 180012 - r/w - -CYCA0U - VRAM CYCLE PATTERN (BANK A0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP4A03  | VCP4A02  | VCP4A01  | VCP4A00  | VCP5A03  | VCP5A02  |
 VCP5A01  | VCP5A00  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP6A03  | VCP6A02  | VCP6A01  | VCP6A00  | VCP7A03  | VCP7A02  |
 VCP7A01  | VCP7A00  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA0U (m_vdp2_regs[0x012 / 2])

/* 180014 - r/w - -CYCA1L - VRAM CYCLE PATTERN (BANK A1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP0A13  | VCP0A12  | VCP0A11  | VCP0A10  | VCP1A13  | VCP1A12  |
 VCP1A11  | VCP1A10  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP2A13  | VCP2A12  | VCP2A11  | VCP2A10  | VCP3A13  | VCP3A12  |
 VCP3A11  | VCP3A10  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA1L (m_vdp2_regs[0x014 / 2])

/* 180016 - r/w - -CYCA1U - VRAM CYCLE PATTERN (BANK A1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP4A13  | VCP4A12  | VCP4A11  | VCP4A10  | VCP5A13  | VCP5A12  |
 VCP5A11  | VCP5A10  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP6A13  | VCP6A12  | VCP6A11  | VCP6A10  | VCP7A13  | VCP7A12  |
 VCP7A11  | VCP7A10  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA1U (m_vdp2_regs[0x016 / 2])

/* 180018 - r/w - -CYCB0L - VRAM CYCLE PATTERN (BANK B0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP0B03  | VCP0B02  | VCP0B01  | VCP0B00  | VCP1B03  | VCP1B02  |
 VCP1B01  | VCP1B00  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP2B03  | VCP2B02  | VCP2B01  | VCP2B00  | VCP3B03  | VCP3B02  |
 VCP3B01  | VCP3B00  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA2L (m_vdp2_regs[0x018 / 2])

/* 18001A - r/w - -CYCB0U - VRAM CYCLE PATTERN (BANK B0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP4B03  | VCP4B02  | VCP4B01  | VCP4B00  | VCP5B03  | VCP5B02  |
 VCP5B01  | VCP5B00  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP6B03  | VCP6B02  | VCP6B01  | VCP6B00  | VCP7B03  | VCP7B02  |
 VCP7B01  | VCP7B00  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA2U (m_vdp2_regs[0x01a / 2])

/* 18001C - r/w - -CYCB1L - VRAM CYCLE PATTERN (BANK B1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP0B13  | VCP0B12  | VCP0B11  | VCP0B10  | VCP1B13  | VCP1B12  |
 VCP1B11  | VCP1B10  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP2B13  | VCP2B12  | VCP2B11  | VCP2B10  | VCP3B13  | VCP3B12  |
 VCP3B11  | VCP3B10  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA3L (m_vdp2_regs[0x01c / 2])

/* 18001E - r/w - -CYCB1U - VRAM CYCLE PATTERN (BANK B1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | VCP4B13  | VCP4B12  | VCP4B11  | VCP4B10  | VCP5B13  | VCP5B12  |
 VCP5B11  | VCP5B10  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | VCP6B13  | VCP6B12  | VCP6B11  | VCP6B10  | VCP7B13  | VCP7B12  |
 VCP7B11  | VCP7B10  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CYCA3U (m_vdp2_regs[0x01e / 2])

/* 180020 - r/w - BGON - SCREEN DISPLAY ENABLE

 this register allows each tilemap to be enabled or disabled and also which
 layers are solid

 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    | R0TPON   | N3TPON   | N2TPON   |
 N1TPON   | N0TPON   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    | R1ON     | R0ON     | N3ON     | N2ON     | N1ON
 | N0ON     |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_BGON (m_vdp2_regs[0x020 / 2])

// NxOn - Layer Enable Register
#define VDP2_xxON                                                              \
  ((VDP2_BGON & 0x001f) >> 0) /* to see if anything is enabled */

#define VDP2_N0ON ((VDP2_BGON & 0x0001) >> 0) /* N0On = NBG0 Enable */
#define VDP2_N1ON ((VDP2_BGON & 0x0002) >> 1) /* N1On = NBG1 Enable */
#define VDP2_N2ON ((VDP2_BGON & 0x0004) >> 2) /* N2On = NBG2 Enable */
#define VDP2_N3ON ((VDP2_BGON & 0x0008) >> 3) /* N3On = NBG3 Enable */
#define VDP2_R0ON ((VDP2_BGON & 0x0010) >> 4) /* R0On = RBG0 Enable */
#define VDP2_R1ON ((VDP2_BGON & 0x0020) >> 5) /* R1On = RBG1 Enable */

// NxTPON - Transparency Pen Enable Registers
#define VDP2_N0TPON                                                            \
  ((VDP2_BGON & 0x0100) >> 8) /*  N0TPON = NBG0 Draw Transparent Pen (as       \
                                 solid) /or/ RBG1 Draw Transparent Pen */
#define VDP2_N1TPON                                                            \
  ((VDP2_BGON & 0x0200) >> 9) /*  N1TPON = NBG1 Draw Transparent Pen (as       \
                                 solid) /or/ EXBG Draw Transparent Pen */
#define VDP2_N2TPON                                                            \
  ((VDP2_BGON & 0x0400) >>                                                     \
   10) /*  N2TPON = NBG2 Draw Transparent Pen (as solid) */
#define VDP2_N3TPON                                                            \
  ((VDP2_BGON & 0x0800) >>                                                     \
   11) /*  N3TPON = NBG3 Draw Transparent Pen (as solid) */
#define VDP2_R0TPON                                                            \
  ((VDP2_BGON & 0x1000) >>                                                     \
   12) /*  R0TPON = RBG0 Draw Transparent Pen (as solid) */

/*
180022 - MZCTL - Mosaic Control
bit->
/----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
|    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
|    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MZCTL (m_vdp2_regs[0x022 / 2])

#define VDP2_MZSZV ((VDP2_MZCTL & 0xf000) >> 12)
#define VDP2_MZSZH ((VDP2_MZCTL & 0x0f00) >> 8)
#define VDP2_R0MZE ((VDP2_MZCTL & 0x0010) >> 4)
#define VDP2_N3MZE ((VDP2_MZCTL & 0x0008) >> 3)
#define VDP2_N2MZE ((VDP2_MZCTL & 0x0004) >> 2)
#define VDP2_N1MZE ((VDP2_MZCTL & 0x0002) >> 1)
#define VDP2_N0MZE ((VDP2_MZCTL & 0x0001) >> 0)

/*180024 - Special Function Code Select

*/

#define VDP2_SFSEL (m_vdp2_regs[0x024 / 2])

/*180026 - Special Function Code

*/

#define VDP2_SFCODE (m_vdp2_regs[0x026 / 2])

/*
180028 - CHCTLA - Character Control (NBG0, NBG1)
 bit->
/----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    | N1CHCN1  | N1CHCN0  | N1BMSZ1  | N1BMSZ0  |
N1BMEN   | N1CHSZ   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    | N0CHCN2  | N0CHCN1  | N0CHCN0  | N0BMSZ1  | N0BMSZ0  |
N0BMEN   | N0CHSZ   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CHCTLA (m_vdp2_regs[0x028 / 2])

/* -------------------------- NBG0 Character Control Registers
 * -------------------------- */

/*  N0CHCNx  NBG0 (or RGB1) Colour Depth
    000 - 16 Colours
    001 - 256 Colours
    010 - 2048 Colours
    011 - 32768 Colours (RGB5)
    100 - 16770000 Colours (RGB8)
    101 - invalid
    110 - invalid
    111 - invalid   */
#define VDP2_N0CHCN ((VDP2_CHCTLA & 0x0070) >> 4)

/*  N0BMSZx - NBG0 Bitmap Size *guessed*
    00 - 512 x 256
    01 - 512 x 512
    10 - 1024 x 256
    11 - 1024 x 512   */
#define VDP2_N0BMSZ ((VDP2_CHCTLA & 0x000c) >> 2)

/*  N0BMEN - NBG0 Bitmap Enable
    0 - use cell mode
    1 - use bitmap mode   */
#define VDP2_N0BMEN ((VDP2_CHCTLA & 0x0002) >> 1)

/*  N0CHSZ - NBG0 Character (Tile) Size
    0 - 1 cell  x 1 cell  (8x8)
    1 - 2 cells x 2 cells (16x16)  */
#define VDP2_N0CHSZ ((VDP2_CHCTLA & 0x0001) >> 0)

/* -------------------------- NBG1 Character Control Registers
 * -------------------------- */

/*  N1CHCNx - NBG1 (or EXB1) Colour Depth
    00 - 16 Colours
    01 - 256 Colours
    10 - 2048 Colours
    11 - 32768 Colours (RGB5)  */
#define VDP2_N1CHCN ((VDP2_CHCTLA & 0x3000) >> 12)

/*  N1BMSZx - NBG1 Bitmap Size *guessed*
    00 - 512 x 256
    01 - 512 x 512
    10 - 1024 x 256
    11 - 1024 x 512   */
#define VDP2_N1BMSZ ((VDP2_CHCTLA & 0x0c00) >> 10)

/*  N1BMEN - NBG1 Bitmap Enable
    0 - use cell mode
    1 - use bitmap mode   */
#define VDP2_N1BMEN ((VDP2_CHCTLA & 0x0200) >> 9)

/*  N1CHSZ - NBG1 Character (Tile) Size
    0 - 1 cell  x 1 cell  (8x8)
    1 - 2 cells x 2 cells (16x16)  */
#define VDP2_N1CHSZ ((VDP2_CHCTLA & 0x0100) >> 8)

/*
18002A - CHCTLB - Character Control (NBG2, NBG1, RBG0)
 bit->
/----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    | R0CHCN2  | R0CHCN1  | R0CHCN0  |    --    | R0BMSZ   |
R0BMEN   | R0CHSZ   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    | N3CHCN   | N3CHSZ   |    --    |    --    |
N2CHCN   | N2CHSZ   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CHCTLB (m_vdp2_regs[0x02a / 2])

/* -------------------------- RBG0 Character Control Registers
 * -------------------------- */

/*  R0CHCNx  RBG0  Colour Depth
    000 - 16 Colours
    001 - 256 Colours
    010 - 2048 Colours
    011 - 32768 Colours (RGB5)
    100 - 16770000 Colours (RGB8)
    101 - invalid
    110 - invalid
    111 - invalid   */
#define VDP2_R0CHCN ((VDP2_CHCTLB & 0x7000) >> 12)

/*  R0BMSZx - RBG0 Bitmap Size *guessed*
    00 - 512 x 256
    01 - 512 x 512  */
#define VDP2_R0BMSZ ((VDP2_CHCTLB & 0x0400) >> 10)

/*  R0BMEN - RBG0 Bitmap Enable
    0 - use cell mode
    1 - use bitmap mode   */
#define VDP2_R0BMEN ((VDP2_CHCTLB & 0x0200) >> 9)

/*  R0CHSZ - RBG0 Character (Tile) Size
    0 - 1 cell  x 1 cell  (8x8)
    1 - 2 cells x 2 cells (16x16)  */
#define VDP2_R0CHSZ ((VDP2_CHCTLB & 0x0100) >> 8)

#define VDP2_N3CHCN ((VDP2_CHCTLB & 0x0020) >> 5)
#define VDP2_N3CHSZ ((VDP2_CHCTLB & 0x0010) >> 4)
#define VDP2_N2CHCN ((VDP2_CHCTLB & 0x0002) >> 1)
#define VDP2_N2CHSZ ((VDP2_CHCTLB & 0x0001) >> 0)

/*
18002C - BMPNA - Bitmap Palette Number (NBG0, NBG1)
 bit->
/----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
|    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
|    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_BMPNA (m_vdp2_regs[0x02c / 2])

#define VDP2_N1BMP ((VDP2_BMPNA & 0x0700) >> 8)
#define VDP2_N0BMP ((VDP2_BMPNA & 0x0007) >> 0)

/* 18002E - Bitmap Palette Number (RBG0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_BMPNB (m_vdp2_regs[0x02e / 2])

#define VDP2_R0BMP ((VDP2_BMPNB & 0x0007) >> 0)

/* 180030 - PNCN0 - Pattern Name Control (NBG0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | N0PNB    | N0CNSM   |    --    |    --    |    --    |    --    | N0SPR
 | N0SCC    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | N0SPLT6  | N0SPLT5  | N0SPLT4  | N0SPCN4  | N0SPCN3  | N0SPCN2  |
 N0SPCN1  | N0SPCN0  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PNCN0 (m_vdp2_regs[0x030 / 2])

/*  Pattern Data Size
    0 = 2 bytes
    1 = 1 byte */
#define VDP2_N0PNB ((VDP2_PNCN0 & 0x8000) >> 15)

/*  Character Number Supplement (in 1 byte mode)
    0 = Character Number = 10bits + 2bits for flip
    1 = Character Number = 12 bits, no flip  */
#define VDP2_N0CNSM ((VDP2_PNCN0 & 0x4000) >> 14)

/*  NBG0 Special Priority Register (in 1 byte mode) */
#define VDP2_N0SPR ((VDP2_PNCN0 & 0x0200) >> 9)

/*  NBG0 Special Colour Control Register (in 1 byte mode) */
#define VDP2_N0SCC ((VDP2_PNCN0 & 0x0100) >> 8)

/*  Supplementary Palette Bits (in 1 byte mode) */
#define VDP2_N0SPLT ((VDP2_PNCN0 & 0x00e0) >> 5)

/*  Supplementary Character Bits (in 1 byte mode) */
#define VDP2_N0SPCN ((VDP2_PNCN0 & 0x001f) >> 0)

/* 180032 - Pattern Name Control (NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PNCN1 (m_vdp2_regs[0x032 / 2])

/*  Pattern Data Size
    0 = 2 bytes
    1 = 1 byte */
#define VDP2_N1PNB ((VDP2_PNCN1 & 0x8000) >> 15)

/*  Character Number Supplement (in 1 byte mode)
    0 = Character Number = 10bits + 2bits for flip
    1 = Character Number = 12 bits, no flip  */
#define VDP2_N1CNSM ((VDP2_PNCN1 & 0x4000) >> 14)

/*  NBG0 Special Priority Register (in 1 byte mode) */
#define VDP2_N1SPR ((VDP2_PNCN1 & 0x0200) >> 9)

/*  NBG0 Special Colour Control Register (in 1 byte mode) */
#define VDP2_N1SCC ((VDP2_PNCN1 & 0x0100) >> 8)

/*  Supplementary Palette Bits (in 1 byte mode) */
#define VDP2_N1SPLT ((VDP2_PNCN1 & 0x00e0) >> 5)

/*  Supplementary Character Bits (in 1 byte mode) */
#define VDP2_N1SPCN ((VDP2_PNCN1 & 0x001f) >> 0)

/* 180034 - Pattern Name Control (NBG2)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PNCN2 (m_vdp2_regs[0x034 / 2])

/*  Pattern Data Size
    0 = 2 bytes
    1 = 1 byte */
#define VDP2_N2PNB ((VDP2_PNCN2 & 0x8000) >> 15)

/*  Character Number Supplement (in 1 byte mode)
    0 = Character Number = 10bits + 2bits for flip
    1 = Character Number = 12 bits, no flip  */
#define VDP2_N2CNSM ((VDP2_PNCN2 & 0x4000) >> 14)

/*  NBG0 Special Priority Register (in 1 byte mode) */
#define VDP2_N2SPR ((VDP2_PNCN2 & 0x0200) >> 9)

/*  NBG0 Special Colour Control Register (in 1 byte mode) */
#define VDP2_N2SCC ((VDP2_PNCN2 & 0x0100) >> 8)

/*  Supplementary Palette Bits (in 1 byte mode) */
#define VDP2_N2SPLT ((VDP2_PNCN2 & 0x00e0) >> 5)

/*  Supplementary Character Bits (in 1 byte mode) */
#define VDP2_N2SPCN ((VDP2_PNCN2 & 0x001f) >> 0)

/* 180036 - Pattern Name Control (NBG3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       | N3PNB    | N3CNSM   |    --    |    --    |    --    |    --    | N3SPR
 | N3SCC    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | N3SPLT6  | N3SPLT5  | N3SPLT4  | N3SPCN4  | N3SPCN3  | N3SPCN2  |
 N3SPCN1  | N3SPCN0  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PNCN3 (m_vdp2_regs[0x036 / 2])

/*  Pattern Data Size
    0 = 2 bytes
    1 = 1 byte */
#define VDP2_N3PNB ((VDP2_PNCN3 & 0x8000) >> 15)

/*  Character Number Supplement (in 1 byte mode)
    0 = Character Number = 10bits + 2bits for flip
    1 = Character Number = 12 bits, no flip  */
#define VDP2_N3CNSM ((VDP2_PNCN3 & 0x4000) >> 14)

/*  NBG0 Special Priority Register (in 1 byte mode) */
#define VDP2_N3SPR ((VDP2_PNCN3 & 0x0200) >> 9)

/*  NBG0 Special Colour Control Register (in 1 byte mode) */
#define VDP2_N3SCC ((VDP2_PNCN3 & 0x0100) >> 8)

/*  Supplementary Palette Bits (in 1 byte mode) */
#define VDP2_N3SPLT ((VDP2_PNCN3 & 0x00e0) >> 5)

/*  Supplementary Character Bits (in 1 byte mode) */
#define VDP2_N3SPCN ((VDP2_PNCN3 & 0x001f) >> 0)

/* 180038 - Pattern Name Control (RBG0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PNCR (m_vdp2_regs[0x038 / 2])

/*  Pattern Data Size
    0 = 2 bytes
    1 = 1 byte */
#define VDP2_R0PNB ((VDP2_PNCR & 0x8000) >> 15)

/*  Character Number Supplement (in 1 byte mode)
    0 = Character Number = 10bits + 2bits for flip
    1 = Character Number = 12 bits, no flip  */
#define VDP2_R0CNSM ((VDP2_PNCR & 0x4000) >> 14)

/*  NBG0 Special Priority Register (in 1 byte mode) */
#define VDP2_R0SPR ((VDP2_PNCR & 0x0200) >> 9)

/*  NBG0 Special Colour Control Register (in 1 byte mode) */
#define VDP2_R0SCC ((VDP2_PNCR & 0x0100) >> 8)

/*  Supplementary Palette Bits (in 1 byte mode) */
#define VDP2_R0SPLT ((VDP2_PNCR & 0x00e0) >> 5)

/*  Supplementary Character Bits (in 1 byte mode) */
#define VDP2_R0SPCN ((VDP2_PNCR & 0x001f) >> 0)

/* 18003A - PLSZ - Plane Size
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       | N3PLSZ1  | N3PLSZ0  |    --    |    --    | N1PLSZ1  | N1PLSZ0  |
 N0PLSZ1  | N0PLSZ0  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PLSZ (m_vdp2_regs[0x03a / 2])

/* NBG0 Plane Size
00 1H Page x 1V Page
01 2H Pages x 1V Page
10 invalid
11 2H Pages x 2V Pages  */
#define VDP2_RBOVR ((VDP2_PLSZ & 0xc000) >> 14)
#define VDP2_RBPLSZ ((VDP2_PLSZ & 0x3000) >> 12)
#define VDP2_RAOVR ((VDP2_PLSZ & 0x0c00) >> 10)
#define VDP2_RAPLSZ ((VDP2_PLSZ & 0x0300) >> 8)
#define VDP2_N3PLSZ ((VDP2_PLSZ & 0x00c0) >> 6)
#define VDP2_N2PLSZ ((VDP2_PLSZ & 0x0030) >> 4)
#define VDP2_N1PLSZ ((VDP2_PLSZ & 0x000c) >> 2)
#define VDP2_N0PLSZ ((VDP2_PLSZ & 0x0003) >> 0)

/* 18003C - MPOFN - Map Offset (NBG0, NBG1, NBG2, NBG3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    | N3MP8    | N3MP7    | N3MP6    |    --    | N2MP8    | N2MP7
 | N2MP6    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    | N1MP8    | N1MP7    | N1MP6    |    --    | N0MP8    | N0MP7
 | N0MP6    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPOFN_ (m_vdp2_regs[0x03c / 2])

/* Higher 3 bits of the map offset for each layer */
#define VDP2_N3MP_ ((VDP2_MPOFN_ & 0x3000) >> 12)
#define VDP2_N2MP_ ((VDP2_MPOFN_ & 0x0300) >> 8)
#define VDP2_N1MP_ ((VDP2_MPOFN_ & 0x0030) >> 4)
#define VDP2_N0MP_ ((VDP2_MPOFN_ & 0x0003) >> 0)

/* 18003E - Map Offset (Rotation Parameter A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPOFR_ (m_vdp2_regs[0x03e / 2])

#define VDP2_RBMP_ ((VDP2_MPOFR_ & 0x0030) >> 4)
#define VDP2_RAMP_ ((VDP2_MPOFR_ & 0x0003) >> 0)

/* 180040 - MPABN0 - Map (NBG0, Plane A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    | N0MPB5   | N0MPB4   | N0MPB3   | N0MPB2   |
 N0MPB1   | N0MPB0   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    | N0MPA5   | N0MPA4   | N0MPA3   | N0MPA2   |
 N0MPA1   | N0MPA0   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPABN0 (m_vdp2_regs[0x040 / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap NBG0 */
#define VDP2_N0MPB ((VDP2_MPABN0 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap NBG0 */
#define VDP2_N0MPA ((VDP2_MPABN0 & 0x003f) >> 0)

/* 180042 - MPCDN0 - (NBG0, Plane C,D)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    | N0MPD5   | N0MPD4   | N0MPD3   | N0MPD2   |
 N0MPD1   | N0MPD0   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    | N0MPC5   | N0MPC4   | N0MPC3   | N0MPC2   |
 N0MPC1   | N0MPC0   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPCDN0 (m_vdp2_regs[0x042 / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane D of Tilemap NBG0 */
#define VDP2_N0MPD ((VDP2_MPCDN0 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane C of Tilemap NBG0 */
#define VDP2_N0MPC ((VDP2_MPCDN0 & 0x003f) >> 0)

/* 180044 - Map (NBG1, Plane A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPABN1 (m_vdp2_regs[0x044 / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap NBG1 */
#define VDP2_N1MPB ((VDP2_MPABN1 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap NBG1 */
#define VDP2_N1MPA ((VDP2_MPABN1 & 0x003f) >> 0)

/* 180046 - Map (NBG1, Plane C,D)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPCDN1 (m_vdp2_regs[0x046 / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane D of Tilemap NBG0 */
#define VDP2_N1MPD ((VDP2_MPCDN1 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane C of Tilemap NBG0 */
#define VDP2_N1MPC ((VDP2_MPCDN1 & 0x003f) >> 0)

/* 180048 - Map (NBG2, Plane A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPABN2 (m_vdp2_regs[0x048 / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap NBG2 */
#define VDP2_N2MPB ((VDP2_MPABN2 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap NBG2 */
#define VDP2_N2MPA ((VDP2_MPABN2 & 0x003f) >> 0)

/* 18004a - Map (NBG2, Plane C,D)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPCDN2 (m_vdp2_regs[0x04a / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane D of Tilemap NBG2 */
#define VDP2_N2MPD ((VDP2_MPCDN2 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane C of Tilemap NBG2 */
#define VDP2_N2MPC ((VDP2_MPCDN2 & 0x003f) >> 0)

/* 18004c - Map (NBG3, Plane A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPABN3 (m_vdp2_regs[0x04c / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap NBG1 */
#define VDP2_N3MPB ((VDP2_MPABN3 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap NBG1 */
#define VDP2_N3MPA ((VDP2_MPABN3 & 0x003f) >> 0)

/* 18004e - Map (NBG3, Plane C,D)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPCDN3 (m_vdp2_regs[0x04e / 2])

/* N0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap NBG0 */
#define VDP2_N3MPD ((VDP2_MPCDN3 & 0x3f00) >> 8)

/* N0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap NBG0 */
#define VDP2_N3MPC ((VDP2_MPCDN3 & 0x003f) >> 0)

/* 180050 - Map (Rotation Parameter A, Plane A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPABRA (m_vdp2_regs[0x050 / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap RBG0 */
#define VDP2_RAMPB ((VDP2_MPABRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap RBG0 */
#define VDP2_RAMPA ((VDP2_MPABRA & 0x003f) >> 0)

/* 180052 - Map (Rotation Parameter A, Plane C,D)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPCDRA (m_vdp2_regs[0x052 / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane D of Tilemap RBG0 */
#define VDP2_RAMPD ((VDP2_MPCDRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane C of Tilemap RBG0 */
#define VDP2_RAMPC ((VDP2_MPCDRA & 0x003f) >> 0)

/* 180054 - Map (Rotation Parameter A, Plane E,F)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPEFRA (m_vdp2_regs[0x054 / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane F of Tilemap RBG0 */
#define VDP2_RAMPF ((VDP2_MPEFRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane E of Tilemap RBG0 */
#define VDP2_RAMPE ((VDP2_MPEFRA & 0x003f) >> 0)

/* 180056 - Map (Rotation Parameter A, Plane G,H)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPGHRA (m_vdp2_regs[0x056 / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane H of Tilemap RBG0 */
#define VDP2_RAMPH ((VDP2_MPGHRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane G of Tilemap RBG0 */
#define VDP2_RAMPG ((VDP2_MPGHRA & 0x003f) >> 0)

/* 180058 - Map (Rotation Parameter A, Plane I,J)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPIJRA (m_vdp2_regs[0x058 / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane J of Tilemap RBG0 */
#define VDP2_RAMPJ ((VDP2_MPIJRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane I of Tilemap RBG0 */
#define VDP2_RAMPI ((VDP2_MPIJRA & 0x003f) >> 0)

/* 18005a - Map (Rotation Parameter A, Plane K,L)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPKLRA (m_vdp2_regs[0x05a / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane L of Tilemap RBG0 */
#define VDP2_RAMPL ((VDP2_MPKLRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane K of Tilemap RBG0 */
#define VDP2_RAMPK ((VDP2_MPKLRA & 0x003f) >> 0)

/* 18005c - Map (Rotation Parameter A, Plane M,N)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPMNRA (m_vdp2_regs[0x05c / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane N of Tilemap RBG0 */
#define VDP2_RAMPN ((VDP2_MPMNRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane M of Tilemap RBG0 */
#define VDP2_RAMPM ((VDP2_MPMNRA & 0x003f) >> 0)

/* 18005e - Map (Rotation Parameter A, Plane O,P)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_MPOPRA (m_vdp2_regs[0x05e / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane P of Tilemap RBG0 */
#define VDP2_RAMPP ((VDP2_MPOPRA & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane O of Tilemap RBG0 */
#define VDP2_RAMPO ((VDP2_MPOPRA & 0x003f) >> 0)

/* 180060 - Map (Rotation Parameter B, Plane A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPABRB (m_vdp2_regs[0x060 / 2])

/* R0MPB5 = lower 6 bits of Map Address of Plane B of Tilemap RBG0 */
#define VDP2_RBMPB ((VDP2_MPABRB & 0x3f00) >> 8)

/* R0MPA5 = lower 6 bits of Map Address of Plane A of Tilemap RBG0 */
#define VDP2_RBMPA ((VDP2_MPABRB & 0x003f) >> 0)

/* 180062 - Map (Rotation Parameter B, Plane C,D)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPCDRB (m_vdp2_regs[0x062 / 2])

/* R0MPD5 = lower 6 bits of Map Address of Plane D of Tilemap RBG0 */
#define VDP2_RBMPD ((VDP2_MPCDRB & 0x3f00) >> 8)

/* R0MPc5 = lower 6 bits of Map Address of Plane C of Tilemap RBG0 */
#define VDP2_RBMPC ((VDP2_MPCDRB & 0x003f) >> 0)

/* 180064 - Map (Rotation Parameter B, Plane E,F)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPEFRB (m_vdp2_regs[0x064 / 2])

/* R0MPF5 = lower 6 bits of Map Address of Plane F of Tilemap RBG0 */
#define VDP2_RBMPF ((VDP2_MPEFRB & 0x3f00) >> 8)

/* R0MPE5 = lower 6 bits of Map Address of Plane E of Tilemap RBG0 */
#define VDP2_RBMPE ((VDP2_MPEFRB & 0x003f) >> 0)

/* 180066 - Map (Rotation Parameter B, Plane G,H)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPGHRB (m_vdp2_regs[0x066 / 2])

/* R0MPH5 = lower 6 bits of Map Address of Plane H of Tilemap RBG0 */
#define VDP2_RBMPH ((VDP2_MPGHRB & 0x3f00) >> 8)

/* R0MPG5 = lower 6 bits of Map Address of Plane G of Tilemap RBG0 */
#define VDP2_RBMPG ((VDP2_MPGHRB & 0x003f) >> 0)

/* 180068 - Map (Rotation Parameter B, Plane I,J)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPIJRB (m_vdp2_regs[0x068 / 2])

/* R0MPJ5 = lower 6 bits of Map Address of Plane J of Tilemap RBG0 */
#define VDP2_RBMPJ ((VDP2_MPIJRB & 0x3f00) >> 8)

/* R0MPI5 = lower 6 bits of Map Address of Plane E of Tilemap RBG0 */
#define VDP2_RBMPI ((VDP2_MPIJRB & 0x003f) >> 0)

/* 18006a - Map (Rotation Parameter B, Plane K,L)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPKLRB (m_vdp2_regs[0x06a / 2])

/* R0MPL5 = lower 6 bits of Map Address of Plane L of Tilemap RBG0 */
#define VDP2_RBMPL ((VDP2_MPKLRB & 0x3f00) >> 8)

/* R0MPK5 = lower 6 bits of Map Address of Plane K of Tilemap RBG0 */
#define VDP2_RBMPK ((VDP2_MPKLRB & 0x003f) >> 0)

/* 18006c - Map (Rotation Parameter B, Plane M,N)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPMNRB (m_vdp2_regs[0x06c / 2])

/* R0MPN5 = lower 6 bits of Map Address of Plane N of Tilemap RBG0 */
#define VDP2_RBMPN ((VDP2_MPMNRB & 0x3f00) >> 8)

/* R0MPM5 = lower 6 bits of Map Address of Plane M of Tilemap RBG0 */
#define VDP2_RBMPM ((VDP2_MPMNRB & 0x003f) >> 0)

/* 18006e - Map (Rotation Parameter B, Plane O,P)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_MPOPRB (m_vdp2_regs[0x06e / 2])

/* R0MPP5 = lower 6 bits of Map Address of Plane P of Tilemap RBG0 */
#define VDP2_RBMPP ((VDP2_MPOPRB & 0x3f00) >> 8)

/* R0MPO5 = lower 6 bits of Map Address of Plane O of Tilemap RBG0 */
#define VDP2_RBMPO ((VDP2_MPOPRB & 0x003f) >> 0)

/* 180070 - SCXIN0 - Screen Scroll (NBG0, Horizontal Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCXIN0 (m_vdp2_regs[0x070 / 2])

/* 180072 - Screen Scroll (NBG0, Horizontal Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCXDN0 (m_vdp2_regs[0x072 / 2])

/* 180074 - SCYIN0 - Screen Scroll (NBG0, Vertical Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_SCYIN0 (m_vdp2_regs[0x074 / 2])

/* 180076 - Screen Scroll (NBG0, Vertical Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCYDN0 (m_vdp2_regs[0x076 / 2])

/* 180078 - Coordinate Inc (NBG0, Horizontal Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMXIN0 (m_vdp2_regs[0x078 / 2])

#define VDP2_N0ZMXI ((VDP2_ZMXIN0 & 0x0007) >> 0)

/* 18007a - Coordinate Inc (NBG0, Horizontal Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMXDN0 (m_vdp2_regs[0x07a / 2])

#define VDP2_N0ZMXD ((VDP2_ZMXDN0 >> 8) & 0xff)
#define VDP2_ZMXN0 (((VDP2_N0ZMXI << 16) | (VDP2_N0ZMXD << 8)) & 0x0007ff00)

/* 18007c - Coordinate Inc (NBG0, Vertical Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMYIN0 (m_vdp2_regs[0x07c / 2])

#define VDP2_N0ZMYI ((VDP2_ZMYIN0 & 0x0007) >> 0)

/* 18007e - Coordinate Inc (NBG0, Vertical Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMYDN0 (m_vdp2_regs[0x07e / 2])

#define VDP2_N0ZMYD ((VDP2_ZMYDN0 >> 8) & 0xff)
#define VDP2_ZMYN0 (((VDP2_N0ZMYI << 16) | (VDP2_N0ZMYD << 8)) & 0x0007ff00)

/* 180080 - SCXIN1 - Screen Scroll (NBG1, Horizontal Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCXIN1 (m_vdp2_regs[0x080 / 2])

/* 180082 - Screen Scroll (NBG1, Horizontal Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCXDN1 (m_vdp2_regs[0x082 / 2])

/* 180084 - SCYIN1 - Screen Scroll (NBG1, Vertical Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCYIN1 (m_vdp2_regs[0x084 / 2])

/* 180086 - Screen Scroll (NBG1, Vertical Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCYDN1 (m_vdp2_regs[0x086 / 2])

/* 180088 - Coordinate Inc (NBG1, Horizontal Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMXIN1 (m_vdp2_regs[0x088 / 2])

#define VDP2_N1ZMXI ((VDP2_ZMXIN1 & 0x0007) >> 0)

/* 18008a - Coordinate Inc (NBG1, Horizontal Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMXDN1 (m_vdp2_regs[0x08a / 2])

#define VDP2_N1ZMXD ((VDP2_ZMXDN1 >> 8) & 0xff)
#define VDP2_ZMXN1 (((VDP2_N1ZMXI << 16) | (VDP2_N1ZMXD << 8)) & 0x0007ff00)

/* 18008c - Coordinate Inc (NBG1, Vertical Integer Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMYIN1 (m_vdp2_regs[0x08c / 2])

#define VDP2_N1ZMYI ((VDP2_ZMYIN1 & 0x0007) >> 0)

/* 18008e - Coordinate Inc (NBG1, Vertical Fractional Part)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMYDN1 (m_vdp2_regs[0x08e / 2])

#define VDP2_N1ZMYD ((VDP2_ZMYDN1 >> 8) & 0xff)
#define VDP2_ZMYN1 (((VDP2_N1ZMYI << 16) | (VDP2_N1ZMYD << 8)) & 0x007ff00)

/* 180090 - SCXN2 - Screen Scroll (NBG2, Horizontal)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCXN2 (m_vdp2_regs[0x090 / 2])

/* 180092 - SCYN2 - Screen Scroll (NBG2, Vertical)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCYN2 (m_vdp2_regs[0x092 / 2])

/* 180094 - SCXN3 - Screen Scroll (NBG3, Horizontal)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCXN3 (m_vdp2_regs[0x094 / 2])

/* 180096 - SCYN3 - Screen Scroll (NBG3, Vertical)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCYN3 (m_vdp2_regs[0x096 / 2])

/* 180098 - Reduction Enable
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |
 N1ZMQT   | N1ZMHF   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |
 N0ZMQT   | N0ZMHF   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_ZMCTL (m_vdp2_regs[0x098 / 2])

#define VDP2_N1ZMQT ((VDP2_ZMCTL & 0x0200) >> 9)
#define VDP2_N1ZMHF ((VDP2_ZMCTL & 0x0100) >> 8)
#define VDP2_N0ZMQT ((VDP2_ZMCTL & 0x0002) >> 1)
#define VDP2_N0ZMHF ((VDP2_ZMCTL & 0x0001) >> 0)

/* 18009a - Line and Vertical Cell Scroll Control (NBG0, NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SCRCTL (m_vdp2_regs[0x09a / 2])

#define VDP2_N1LSS ((VDP2_SCRCTL & 0x3000) >> 12)
#define VDP2_N1LZMX ((VDP2_SCRCTL & 0x0800) >> 11)
#define VDP2_N1LSCY ((VDP2_SCRCTL & 0x0400) >> 10)
#define VDP2_N1LSCX ((VDP2_SCRCTL & 0x0200) >> 9)
#define VDP2_N1VCSC ((VDP2_SCRCTL & 0x0100) >> 8)
#define VDP2_N0LSS ((VDP2_SCRCTL & 0x0030) >> 4)
#define VDP2_N0LZMX ((VDP2_SCRCTL & 0x0008) >> 3)
#define VDP2_N0LSCY ((VDP2_SCRCTL & 0x0004) >> 2)
#define VDP2_N0LSCX ((VDP2_SCRCTL & 0x0002) >> 1)
#define VDP2_N0VCSC ((VDP2_SCRCTL & 0x0001) >> 0)

/* 18009c - Vertical Cell Table Address (NBG0, NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_VCSTAU (m_vdp2_regs[0x09c / 2] & 7)

/* 18009e - Vertical Cell Table Address (NBG0, NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_VCSTAL (m_vdp2_regs[0x09e / 2])

/* 1800a0 - LSTA0U - Line Scroll Table Address (NBG0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

/*bit 2 unused when VRAM = 4 Mbits*/
#define VDP2_LSTA0U (m_vdp2_regs[0x0a0 / 2] & 7)

/* 1800a2 - LSTA0L - Line Scroll Table Address (NBG0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LSTA0L (m_vdp2_regs[0x0a2 / 2])

/* 1800a4 - LSTA1U - Line Scroll Table Address (NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

/*bit 2 unused when VRAM = 4 Mbits*/
#define VDP2_LSTA1U (m_vdp2_regs[0x0a4 / 2] & 7)

/* 1800a6 - LSTA1L - Line Scroll Table Address (NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LSTA1L (m_vdp2_regs[0x0a6 / 2])

/* 1800a8 - LCTAU - Line Colour Screen Table Address
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LCTAU (m_vdp2_regs[0x0a8 / 2])
#define VDP2_LCCLMD ((VDP2_LCTAU & 0x8000) >> 15)

/* 1800aa - LCTAL - Line Colour Screen Table Address
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_LCTAL (m_vdp2_regs[0x0aa / 2])

#define VDP2_LCTA (((VDP2_LCTAU & 0x0007) << 16) | (VDP2_LCTAL & 0xffff))

/* 1800ac - Back Screen Table Address
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |  BKCLMD  |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |  BKTA18  |
 BKTA17  |  BKTA16  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_BKTAU (m_vdp2_regs[0x0ac / 2])

#define VDP2_BKCLMD ((VDP2_BKTAU & 0x8000) >> 15)

/* 1800ae - Back Screen Table Address
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |  BKTA15  |  BKTA14  |  BKTA13  |  BKTA12  |  BKTA11  |  BKTA10  | BKTA9
 |  BKTA8   |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |  BKTA7   |  BKTA7   |  BKTA6   |  BKTA5   |  BKTA4   |  BKTA3   | BKTA2
 |  BKTA0   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_BKTAL (m_vdp2_regs[0x0ae / 2])

#define VDP2_BKTA (((VDP2_BKTAU & 0x0007) << 16) | (VDP2_BKTAL & 0xffff))

/* 1800b0 - RPMD - Rotation Parameter Mode
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_RPMD ((m_vdp2_regs[0x0b0 / 2]) & 0x0003)

/* 1800b2 - RPRCTL - Rotation Parameter Read Control
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    | RBKASTRE |
 RBYSTRE  | RBXSTRE  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    | RAKASTRE |
 RAYSTRE  | RBXSTRE  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_RPRCTL (m_vdp2_regs[0x0b2 / 2])
#define VDP2_RBKASTRE ((VDP2_RPRCTL & 0x0400) >> 10)
#define VDP2_RBYSTRE ((VDP2_RPRCTL & 0x0200) >> 9)
#define VDP2_RBXSTRE ((VDP2_RPRCTL & 0x0100) >> 8)
#define VDP2_RAKASTRE ((VDP2_RPRCTL & 0x0004) >> 2)
#define VDP2_RAYSTRE ((VDP2_RPRCTL & 0x0002) >> 1)
#define VDP2_RAXSTRE ((VDP2_RPRCTL & 0x0001) >> 0)

/* 1800b4 - KTCTL - Coefficient Table Control
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |  RBKLCE  |  RBKMD1  |  RBKMD0  |
 RBKDBS  |   RBKTE  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |  RAKLCE  |  RAKMD1  |  RAKMD0  |
 RAKDBS  |   RAKTE  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_KTCTL (m_vdp2_regs[0x0b4 / 2])
#define VDP2_RBUNK ((VDP2_KTCTL & 0x6000) >> 13)
#define VDP2_RBKLCE ((VDP2_KTCTL & 0x1000) >> 12)
#define VDP2_RBKMD ((VDP2_KTCTL & 0x0c00) >> 10)
#define VDP2_RBKDBS ((VDP2_KTCTL & 0x0200) >> 9)
#define VDP2_RBKTE ((VDP2_KTCTL & 0x0100) >> 8)
#define VDP2_RAUNK ((VDP2_KTCTL & 0x0060) >> 5)
#define VDP2_RAKLCE ((VDP2_KTCTL & 0x0010) >> 4)
#define VDP2_RAKMD ((VDP2_KTCTL & 0x000c) >> 2)
#define VDP2_RAKDBS ((VDP2_KTCTL & 0x0002) >> 1)
#define VDP2_RAKTE ((VDP2_KTCTL & 0x0001) >> 0)

/* 1800b6 - KTAOF - Coefficient Table Address Offset (Rotation Parameter A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    | RBKTAOS2 |
 RBKTAOS1 | RBKTAOS0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    | RAKTAOS2 |
 RAKTAOS1 | RAKTAOS0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_KTAOF (m_vdp2_regs[0x0b6 / 2])
#define VDP2_RBKTAOS ((VDP2_KTAOF & 0x0700) >> 8)
#define VDP2_RAKTAOS ((VDP2_KTAOF & 0x0007) >> 0)

/* 1800b8 - OVPNRA - Screen Over Pattern Name (Rotation Parameter A)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_OVPNRA (m_vdp2_regs[0x0b8 / 2])

/* 1800ba - Screen Over Pattern Name (Rotation Parameter B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_OVPNRB (m_vdp2_regs[0x0ba / 2])

/* 1800bc - RPTAU - Rotation Parameter Table Address (Rotation Parameter A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |  RPTA18  |
 RPTA17  |  RPTA16  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_RPTAU (m_vdp2_regs[0x0bc / 2] & 7)

/* 1800be - RPTAL - Rotation Parameter Table Address (Rotation Parameter A,B)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |  RPTA15  |  RPTA14  |  RPTA13  |  RPTA12  |  RPTA11  |  RPTA10  | RPTA9
 |   RPTA8  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |   RPTA7  |   RPTA6  |   RPTA5  |   RPTA4  |   RPTA3  |   RPTA2  | RPTA1
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_RPTAL (m_vdp2_regs[0x0be / 2] & 0x0000ffff)

/* 1800c0 - Window Position (W0, Horizontal Start Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPSX0 (m_vdp2_regs[0x0c0 / 2])

#define VDP2_W0SX ((VDP2_WPSX0 & 0x03ff) >> 0)

/* 1800c2 - Window Position (W0, Vertical Start Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPSY0 (m_vdp2_regs[0x0c2 / 2])

#define VDP2_W0SY ((VDP2_WPSY0 & 0x07ff) >> 0)

/* 1800c4 - Window Position (W0, Horizontal End Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPEX0 (m_vdp2_regs[0x0c4 / 2])

#define VDP2_W0EX ((VDP2_WPEX0 & 0x03ff) >> 0)

/* 1800c6 - Window Position (W0, Vertical End Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPEY0 (m_vdp2_regs[0x0c6 / 2])

#define VDP2_W0EY ((VDP2_WPEY0 & 0x07ff) >> 0)

/* 1800c8 - Window Position (W1, Horizontal Start Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPSX1 (m_vdp2_regs[0x0c8 / 2])

#define VDP2_W1SX ((VDP2_WPSX1 & 0x03ff) >> 0)

/* 1800ca - Window Position (W1, Vertical Start Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPSY1 (m_vdp2_regs[0x0ca / 2])

#define VDP2_W1SY ((VDP2_WPSY1 & 0x07ff) >> 0)

/* 1800cc - Window Position (W1, Horizontal End Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPEX1 (m_vdp2_regs[0x0cc / 2])

#define VDP2_W1EX ((VDP2_WPEX1 & 0x03ff) >> 0)

/* 1800ce - Window Position (W1, Vertical End Point)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WPEY1 (m_vdp2_regs[0x0ce / 2])

#define VDP2_W1EY ((VDP2_WPEY1 & 0x07ff) >> 0)

/* 1800d0 - Window Control (NBG0, NBG1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WCTLA (m_vdp2_regs[0x0d0 / 2])
#define VDP2_N1LOG ((VDP2_WCTLA & 0x8000) >> 15)
#define VDP2_N1SWE ((VDP2_WCTLA & 0x2000) >> 13)
#define VDP2_N1SWA ((VDP2_WCTLA & 0x1000) >> 12)
#define VDP2_N1W1E ((VDP2_WCTLA & 0x0800) >> 11)
#define VDP2_N1W1A ((VDP2_WCTLA & 0x0400) >> 10)
#define VDP2_N1W0E ((VDP2_WCTLA & 0x0200) >> 9)
#define VDP2_N1W0A ((VDP2_WCTLA & 0x0100) >> 8)
#define VDP2_N0LOG ((VDP2_WCTLA & 0x0080) >> 7)
#define VDP2_N0SWE ((VDP2_WCTLA & 0x0020) >> 5)
#define VDP2_N0SWA ((VDP2_WCTLA & 0x0010) >> 4)
#define VDP2_N0W1E ((VDP2_WCTLA & 0x0008) >> 3)
#define VDP2_N0W1A ((VDP2_WCTLA & 0x0004) >> 2)
#define VDP2_N0W0E ((VDP2_WCTLA & 0x0002) >> 1)
#define VDP2_N0W0A ((VDP2_WCTLA & 0x0001) >> 0)

/* 1800d2 - Window Control (NBG2, NBG3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WCTLB (m_vdp2_regs[0x0d2 / 2])
#define VDP2_N3LOG ((VDP2_WCTLB & 0x8000) >> 15)
#define VDP2_N3SWE ((VDP2_WCTLB & 0x2000) >> 13)
#define VDP2_N3SWA ((VDP2_WCTLB & 0x1000) >> 12)
#define VDP2_N3W1E ((VDP2_WCTLB & 0x0800) >> 11)
#define VDP2_N3W1A ((VDP2_WCTLB & 0x0400) >> 10)
#define VDP2_N3W0E ((VDP2_WCTLB & 0x0200) >> 9)
#define VDP2_N3W0A ((VDP2_WCTLB & 0x0100) >> 8)
#define VDP2_N2LOG ((VDP2_WCTLB & 0x0080) >> 7)
#define VDP2_N2SWE ((VDP2_WCTLB & 0x0020) >> 5)
#define VDP2_N2SWA ((VDP2_WCTLB & 0x0010) >> 4)
#define VDP2_N2W1E ((VDP2_WCTLB & 0x0008) >> 3)
#define VDP2_N2W1A ((VDP2_WCTLB & 0x0004) >> 2)
#define VDP2_N2W0E ((VDP2_WCTLB & 0x0002) >> 1)
#define VDP2_N2W0A ((VDP2_WCTLB & 0x0001) >> 0)

/* 1800d4 - Window Control (RBG0, Sprite)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WCTLC (m_vdp2_regs[0x0d4 / 2])
#define VDP2_SPLOG ((VDP2_WCTLC & 0x8000) >> 15)
#define VDP2_SPSWE ((VDP2_WCTLC & 0x2000) >> 13)
#define VDP2_SPSWA ((VDP2_WCTLC & 0x1000) >> 12)
#define VDP2_SPW1E ((VDP2_WCTLC & 0x0800) >> 11)
#define VDP2_SPW1A ((VDP2_WCTLC & 0x0400) >> 10)
#define VDP2_SPW0E ((VDP2_WCTLC & 0x0200) >> 9)
#define VDP2_SPW0A ((VDP2_WCTLC & 0x0100) >> 8)
#define VDP2_R0LOG ((VDP2_WCTLC & 0x0080) >> 7)
#define VDP2_R0SWE ((VDP2_WCTLC & 0x0020) >> 5)
#define VDP2_R0SWA ((VDP2_WCTLC & 0x0010) >> 4)
#define VDP2_R0W1E ((VDP2_WCTLC & 0x0008) >> 3)
#define VDP2_R0W1A ((VDP2_WCTLC & 0x0004) >> 2)
#define VDP2_R0W0E ((VDP2_WCTLC & 0x0002) >> 1)
#define VDP2_R0W0A ((VDP2_WCTLC & 0x0001) >> 0)

/* 1800d6 - Window Control (Parameter Window, Colour Calc. Window)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_WCTLD (m_vdp2_regs[0x0d6 / 2])
#define VDP2_CCLOG ((VDP2_WCTLD & 0x8000) >> 15)
#define VDP2_CCSWE ((VDP2_WCTLD & 0x2000) >> 13)
#define VDP2_CCSWA ((VDP2_WCTLD & 0x1000) >> 12)
#define VDP2_CCW1E ((VDP2_WCTLD & 0x0800) >> 11)
#define VDP2_CCW1A ((VDP2_WCTLD & 0x0400) >> 10)
#define VDP2_CCW0E ((VDP2_WCTLD & 0x0200) >> 9)
#define VDP2_CCW0A ((VDP2_WCTLD & 0x0100) >> 8)
#define VDP2_RPLOG ((VDP2_WCTLD & 0x0080) >> 7)
#define VDP2_RPSWE ((VDP2_WCTLD & 0x0020) >> 5)
#define VDP2_RPSWA ((VDP2_WCTLD & 0x0010) >> 4)
#define VDP2_RPW1E ((VDP2_WCTLD & 0x0008) >> 3)
#define VDP2_RPW1A ((VDP2_WCTLD & 0x0004) >> 2)
#define VDP2_RPW0E ((VDP2_WCTLD & 0x0002) >> 1)
#define VDP2_RPW0A ((VDP2_WCTLD & 0x0001) >> 0)

/* 1800d8 - Line Window Table Address (W0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LWTA0U (m_vdp2_regs[0x0d8 / 2])

#define VDP2_W0LWE ((VDP2_LWTA0U & 0x8000) >> 15)

/* 1800da - Line Window Table Address (W0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LWTA0L (m_vdp2_regs[0x0da / 2])

/* bit 19 isn't used when VRAM = 4 Mbit */
#define VDP2_W0LWTA (((VDP2_LWTA0U & 0x0007) << 16) | (VDP2_LWTA0L & 0xfffe))

/* 1800dc - Line Window Table Address (W1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LWTA1U (m_vdp2_regs[0x0dc / 2])

#define VDP2_W1LWE ((VDP2_LWTA1U & 0x8000) >> 15)

/* 1800de - Line Window Table Address (W1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LWTA1L (m_vdp2_regs[0x0de / 2])

/* bit 19 isn't used when VRAM = 4 Mbit */
#define VDP2_W1LWTA (((VDP2_LWTA1U & 0x0007) << 16) | (VDP2_LWTA1L & 0xfffe))

/* 1800e0 - Sprite Control
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    | SPCCCS1  | SPCCCS0  |    --    |  SPCCN2  |
 SPCCN1  |  SPCCN0  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |  SPCLMD  | SPWINEN  |  SPTYPE3 |  SPTYPE2 |
 SPTYPE1 |  SPTYPE0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SPCTL (m_vdp2_regs[0x0e0 / 2])
#define VDP2_SPCCCS ((VDP2_SPCTL & 0x3000) >> 12)
#define VDP2_SPCCN ((VDP2_SPCTL & 0x700) >> 8)
#define VDP2_SPCLMD ((VDP2_SPCTL & 0x20) >> 5)
#define VDP2_SPWINEN ((VDP2_SPCTL & 0x10) >> 4)
#define VDP2_SPTYPE (VDP2_SPCTL & 0xf)

/* 1800e2 - Shadow Control
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SDCTL (m_vdp2_regs[0x0e2 / 2])

/* 1800e4 - CRAOFA - Colour Ram Address Offset (NBG0 - NBG3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    | N0CAOS2  | N3CAOS1  | N3CAOS0  |    --    | N2CAOS2  |
 N2CAOS1  | N2CAOS0  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    | N1CAOS2  | N1CAOS1  | N1CAOS0  |    --    | N0CAOS2  |
 N0CAOS1  | N0CAOS0  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CRAOFA (m_vdp2_regs[0x0e4 / 2])

/* NxCAOS =  */
#define VDP2_N0CAOS ((VDP2_CRAOFA & 0x0007) >> 0)
#define VDP2_N1CAOS ((VDP2_CRAOFA & 0x0070) >> 4)
#define VDP2_N2CAOS ((VDP2_CRAOFA & 0x0700) >> 8)
#define VDP2_N3CAOS ((VDP2_CRAOFA & 0x7000) >> 12)

/* 1800e6 - Colour Ram Address Offset (RBG0, SPRITE)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_CRAOFB (m_vdp2_regs[0x0e6 / 2])
#define VDP2_R0CAOS ((VDP2_CRAOFB & 0x0007) >> 0)
#define VDP2_SPCAOS ((VDP2_CRAOFB & 0x0070) >> 4)

/* 1800e8 - LNCLEN - Line Colour Screen Enable
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |  SPLCEN  |  R0LCEN  |  N3LCEN  |  N2LCEN  |
 N1LCEN  | N0LCEN   |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_LNCLEN (m_vdp2_regs[0x0e8 / 2])
#define VDP2_SPLCEN ((VDP2_LNCLEN & 0x0020) >> 5)
#define VDP2_R0LCEN ((VDP2_LNCLEN & 0x0010) >> 4)
#define VDP2_N3LCEN ((VDP2_LNCLEN & 0x0008) >> 3)
#define VDP2_N2LCEN ((VDP2_LNCLEN & 0x0004) >> 2)
#define VDP2_N1LCEN ((VDP2_LNCLEN & 0x0002) >> 1)
#define VDP2_N0LCEN ((VDP2_LNCLEN & 0x0001) >> 0)

/* 1800ea - Special Priority Mode
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SFPRMD (m_vdp2_regs[0x0ea / 2])

/* 1800ec - Colour Calculation Control
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |  BOKEN   |  BOKN2   |  BOKN1   |   BOKN0  |    --    |  EXCCEN  |
 CCRTMD  |  CCMD    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |  SPCCEN  |  LCCCEN  |  R0CCEN  |  N3CCEN  |  N2CCEN  |
 N1CCEN  |  N0CCEN  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCCR (m_vdp2_regs[0x0ec / 2])
#define VDP2_CCMD ((VDP2_CCCR & 0x100) >> 8)
#define VDP2_SPCCEN ((VDP2_CCCR & 0x40) >> 6)
#define VDP2_LCCCEN ((VDP2_CCCR & 0x20) >> 5)
#define VDP2_R0CCEN ((VDP2_CCCR & 0x10) >> 4)
#define VDP2_N3CCEN ((VDP2_CCCR & 0x8) >> 3)
#define VDP2_N2CCEN ((VDP2_CCCR & 0x4) >> 2)
#define VDP2_N1CCEN ((VDP2_CCCR & 0x2) >> 1)
#define VDP2_N0CCEN ((VDP2_CCCR & 0x1) >> 0)

/* 1800ee - Special Colour Calculation Mode
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_SFCCMD (m_vdp2_regs[0x0ee / 2])

/* 1800f0 - Priority Number (Sprite 0,1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |  S1PRIN2 |
 S1PRIN1 |  S1PRIN0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |  S0PRIN2 |
 S0PRIN1 |  S0PRIN0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PRISA (m_vdp2_regs[0x0f0 / 2])
#define VDP2_S1PRIN ((VDP2_PRISA & 0x0700) >> 8)
#define VDP2_S0PRIN ((VDP2_PRISA & 0x0007) >> 0)

/* 1800f2 - Priority Number (Sprite 2,3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |  S3PRIN2 |
 S3PRIN1 |  S3PRIN0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |  S2PRIN2 |
 S2PRIN1 |  S2PRIN0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PRISB (m_vdp2_regs[0x0f2 / 2])
#define VDP2_S3PRIN ((VDP2_PRISB & 0x0700) >> 8)
#define VDP2_S2PRIN ((VDP2_PRISB & 0x0007) >> 0)

/* 1800f4 - Priority Number (Sprite 4,5)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |  S5PRIN2 |
 S5PRIN1 |  S5PRIN0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |  S4PRIN2 |
 S4PRIN1 |  S4PRIN0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PRISC (m_vdp2_regs[0x0f4 / 2])
#define VDP2_S5PRIN ((VDP2_PRISC & 0x0700) >> 8)
#define VDP2_S4PRIN ((VDP2_PRISC & 0x0007) >> 0)

/* 1800f6 - Priority Number (Sprite 6,7)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |  S7PRIN2 |
 S7PRIN1 |  S7PRIN0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |  S6PRIN2 |
 S6PRIN1 |  S6PRIN0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PRISD (m_vdp2_regs[0x0f6 / 2])
#define VDP2_S7PRIN ((VDP2_PRISD & 0x0700) >> 8)
#define VDP2_S6PRIN ((VDP2_PRISD & 0x0007) >> 0)

/* 1800f8 - PRINA - Priority Number (NBG 0,1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PRINA (m_vdp2_regs[0x0f8 / 2])

#define VDP2_N1PRIN ((VDP2_PRINA & 0x0700) >> 8)
#define VDP2_N0PRIN ((VDP2_PRINA & 0x0007) >> 0)

/* 1800fa - PRINB - Priority Number (NBG 2,3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_PRINB (m_vdp2_regs[0x0fa / 2])

#define VDP2_N3PRIN ((VDP2_PRINB & 0x0700) >> 8)
#define VDP2_N2PRIN ((VDP2_PRINB & 0x0007) >> 0)

/* 1800fc - Priority Number (RBG0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_PRIR (m_vdp2_regs[0x0fc / 2])

#define VDP2_R0PRIN ((VDP2_PRIR & 0x0007) >> 0)

/* 1800fe - Reserved
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

/* 180100 - Colour Calculation Ratio (Sprite 0,1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |  S1CCRT4 |  S1CCRT3 |  S1CCRT2 |
 S1CCRT1 |  S1CCRT0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |  S0CCRT4 |  S0CCRT3 |  S0CCRT2 |
 S0CCRT1 |  S0CCRT0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRSA (m_vdp2_regs[0x100 / 2])
#define VDP2_S1CCRT ((VDP2_CCRSA & 0x1f00) >> 8)
#define VDP2_S0CCRT ((VDP2_CCRSA & 0x001f) >> 0)

/* 180102 - Colour Calculation Ratio (Sprite 2,3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |  S3CCRT4 |  S3CCRT3 |  S3CCRT2 |
 S3CCRT1 |  S3CCRT0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |  S2CCRT4 |  S2CCRT3 |  S2CCRT2 |
 S2CCRT1 |  S2CCRT0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRSB (m_vdp2_regs[0x102 / 2])
#define VDP2_S3CCRT ((VDP2_CCRSB & 0x1f00) >> 8)
#define VDP2_S2CCRT ((VDP2_CCRSB & 0x001f) >> 0)

/* 180104 - Colour Calculation Ratio (Sprite 4,5)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |  S5CCRT4 |  S5CCRT3 |  S5CCRT2 |
 S5CCRT1 |  S5CCRT0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |  S4CCRT4 |  S4CCRT3 |  S4CCRT2 |
 S4CCRT1 |  S4CCRT0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRSC (m_vdp2_regs[0x104 / 2])
#define VDP2_S5CCRT ((VDP2_CCRSC & 0x1f00) >> 8)
#define VDP2_S4CCRT ((VDP2_CCRSC & 0x001f) >> 0)

/* 180106 - Colour Calculation Ratio (Sprite 6,7)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |  S7CCRT4 |  S7CCRT3 |  S7CCRT2 |
 S7CCRT1 |  S7CCRT0 |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |  S6CCRT4 |  S6CCRT3 |  S6CCRT2 |
 S6CCRT1 |  S6CCRT0 |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRSD (m_vdp2_regs[0x106 / 2])
#define VDP2_S7CCRT ((VDP2_CCRSD & 0x1f00) >> 8)
#define VDP2_S6CCRT ((VDP2_CCRSD & 0x001f) >> 0)

/* 180108 - Colour Calculation Ratio (NBG 0,1)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    | N1CCRT4  | N1CCRT3  | N1CCRT2  |
 N1CCRT1  | N1CCRT0  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    | N0CCRT4  | N0CCRT3  | N0CCRT2  |
 N0CCRT1  | N0CCRT0  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRNA (m_vdp2_regs[0x108 / 2])
#define VDP2_N1CCRT ((VDP2_CCRNA & 0x1f00) >> 8)
#define VDP2_N0CCRT (VDP2_CCRNA & 0x1f)

/* 18010a - Colour Calculation Ratio (NBG 2,3)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    | N3CCRT4  | N3CCRT3  | N3CCRT2  |
 N3CCRT1  | N3CCRT0  |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    | N2CCRT4  | N2CCRT3  | N2CCRT2  |
 N2CCRT1  | N2CCRT0  |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRNB (m_vdp2_regs[0x10a / 2])
#define VDP2_N3CCRT ((VDP2_CCRNB & 0x1f00) >> 8)
#define VDP2_N2CCRT (VDP2_CCRNB & 0x1f)

/* 18010c - Colour Calculation Ratio (RBG 0)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRR (m_vdp2_regs[0x10c / 2])
#define VDP2_R0CCRT (VDP2_CCRR & 0x1f)

/* 18010e - Colour Calculation Ratio (Line Colour Screen, Back Colour Screen)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CCRLB (m_vdp2_regs[0x10e / 2])

/* 180110 - Colour Offset Enable
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CLOFEN (m_vdp2_regs[0x110 / 2])
#define VDP2_N0COEN ((VDP2_CLOFEN & 0x01) >> 0)
#define VDP2_N1COEN ((VDP2_CLOFEN & 0x02) >> 1)
#define VDP2_N2COEN ((VDP2_CLOFEN & 0x04) >> 2)
#define VDP2_N3COEN ((VDP2_CLOFEN & 0x08) >> 3)
#define VDP2_R0COEN ((VDP2_CLOFEN & 0x10) >> 4)
#define VDP2_BKCOEN ((VDP2_CLOFEN & 0x20) >> 5)
#define VDP2_SPCOEN ((VDP2_CLOFEN & 0x40) >> 6)

/* 180112 - Colour Offset Select
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_CLOFSL (m_vdp2_regs[0x112 / 2])
#define VDP2_N0COSL ((VDP2_CLOFSL & 0x01) >> 0)
#define VDP2_N1COSL ((VDP2_CLOFSL & 0x02) >> 1)
#define VDP2_N2COSL ((VDP2_CLOFSL & 0x04) >> 2)
#define VDP2_N3COSL ((VDP2_CLOFSL & 0x08) >> 3)
#define VDP2_R0COSL ((VDP2_CLOFSL & 0x10) >> 4)
#define VDP2_BKCOSL ((VDP2_CLOFSL & 0x20) >> 5)
#define VDP2_SPCOSL ((VDP2_CLOFSL & 0x40) >> 6)

/* 180114 - Colour Offset A (Red)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_COAR (m_vdp2_regs[0x114 / 2])

/* 180116 - Colour Offset A (Green)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_COAG (m_vdp2_regs[0x116 / 2])

/* 180118 - Colour Offset A (Blue)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/

#define VDP2_COAB (m_vdp2_regs[0x118 / 2])

/* 18011a - Colour Offset B (Red)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_COBR (m_vdp2_regs[0x11a / 2])

/* 18011c - Colour Offset B (Green)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_COBG (m_vdp2_regs[0x11c / 2])

/* 18011e - Colour Offset B (Blue)
 bit->
 /----15----|----14----|----13----|----12----|----11----|----10----|----09----|----08----\
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       |----07----|----06----|----05----|----04----|----03----|----02----|----01----|----00----|
       |    --    |    --    |    --    |    --    |    --    |    --    |    --
 |    --    |
       \----------|----------|----------|----------|----------|----------|----------|---------*/
#define VDP2_COBB (m_vdp2_regs[0x11e / 2])

#define VDP2_RBG_ROTATION_PARAMETER_A 1
#define VDP2_RBG_ROTATION_PARAMETER_B 2

#define mul_fixed32(a, b) mul_32x32_shift(a, b, 16)

void saturn_state::vdp2_fill_rotation_parameter_table(uint8_t rot_parameter) {
  uint32_t address;

  address = (((VDP2_RPTAU << 16) | VDP2_RPTAL) << 1);
  if (rot_parameter == 1) {
    address &= ~0x00000080;
  } else if (rot_parameter == 2) {
    address |= 0x00000080;
  }

  /* RPTA is masked to 19 bits and doubled, so address/4 can already be the last
     word of VRAM before the 24-word table is stepped through, and selecting
     parameter B by forcing bit 7 of the byte address can push it over on its
     own; wrap each access inside VRAM, as the other table reads do and as the
     address lines do on the hardware. */
  current_rotation_table.xst =
      (m_vdp2_vram[(address / 4) & 0x3ffff] & 0x1fffffc0) |
      ((m_vdp2_vram[(address / 4) & 0x3ffff] & 0x10000000) ? 0xe0000000
                                                           : 0x00000000);
  current_rotation_table.yst =
      (m_vdp2_vram[(address / 4 + 1) & 0x3ffff] & 0x1fffffc0) |
      ((m_vdp2_vram[(address / 4 + 1) & 0x3ffff] & 0x10000000) ? 0xe0000000
                                                               : 0x00000000);
  current_rotation_table.zst =
      (m_vdp2_vram[(address / 4 + 2) & 0x3ffff] & 0x1fffffc0) |
      ((m_vdp2_vram[(address / 4 + 2) & 0x3ffff] & 0x10000000) ? 0xe0000000
                                                               : 0x00000000);
  current_rotation_table.dxst =
      (m_vdp2_vram[(address / 4 + 3) & 0x3ffff] & 0x0007ffc0) |
      ((m_vdp2_vram[(address / 4 + 3) & 0x3ffff] & 0x00040000) ? 0xfff80000
                                                               : 0x00000000);
  current_rotation_table.dyst =
      (m_vdp2_vram[(address / 4 + 4) & 0x3ffff] & 0x0007ffc0) |
      ((m_vdp2_vram[(address / 4 + 4) & 0x3ffff] & 0x00040000) ? 0xfff80000
                                                               : 0x00000000);
  current_rotation_table.dx =
      (m_vdp2_vram[(address / 4 + 5) & 0x3ffff] & 0x0007ffc0) |
      ((m_vdp2_vram[(address / 4 + 5) & 0x3ffff] & 0x00040000) ? 0xfff80000
                                                               : 0x00000000);
  current_rotation_table.dy =
      (m_vdp2_vram[(address / 4 + 6) & 0x3ffff] & 0x0007ffc0) |
      ((m_vdp2_vram[(address / 4 + 6) & 0x3ffff] & 0x00040000) ? 0xfff80000
                                                               : 0x00000000);
  current_rotation_table.A =
      (m_vdp2_vram[(address / 4 + 7) & 0x3ffff] & 0x000fffc0) |
      ((m_vdp2_vram[(address / 4 + 7) & 0x3ffff] & 0x00080000) ? 0xfff00000
                                                               : 0x00000000);
  current_rotation_table.B =
      (m_vdp2_vram[(address / 4 + 8) & 0x3ffff] & 0x000fffc0) |
      ((m_vdp2_vram[(address / 4 + 8) & 0x3ffff] & 0x00080000) ? 0xfff00000
                                                               : 0x00000000);
  current_rotation_table.C =
      (m_vdp2_vram[(address / 4 + 9) & 0x3ffff] & 0x000fffc0) |
      ((m_vdp2_vram[(address / 4 + 9) & 0x3ffff] & 0x00080000) ? 0xfff00000
                                                               : 0x00000000);
  current_rotation_table.D =
      (m_vdp2_vram[(address / 4 + 10) & 0x3ffff] & 0x000fffc0) |
      ((m_vdp2_vram[(address / 4 + 10) & 0x3ffff] & 0x00080000) ? 0xfff00000
                                                                : 0x00000000);
  current_rotation_table.E =
      (m_vdp2_vram[(address / 4 + 11) & 0x3ffff] & 0x000fffc0) |
      ((m_vdp2_vram[(address / 4 + 11) & 0x3ffff] & 0x00080000) ? 0xfff00000
                                                                : 0x00000000);
  current_rotation_table.F =
      (m_vdp2_vram[(address / 4 + 12) & 0x3ffff] & 0x000fffc0) |
      ((m_vdp2_vram[(address / 4 + 12) & 0x3ffff] & 0x00080000) ? 0xfff00000
                                                                : 0x00000000);
  current_rotation_table.px =
      (m_vdp2_vram[(address / 4 + 13) & 0x3ffff] & 0x3fff0000) |
      ((m_vdp2_vram[(address / 4 + 13) & 0x3ffff] & 0x20000000) ? 0xc0000000
                                                                : 0x00000000);
  current_rotation_table.py =
      (m_vdp2_vram[(address / 4 + 13) & 0x3ffff] & 0x00003fff) << 16;
  if (current_rotation_table.py & 0x20000000)
    current_rotation_table.py |= 0xc0000000;
  current_rotation_table.pz =
      (m_vdp2_vram[(address / 4 + 14) & 0x3ffff] & 0x3fff0000) |
      ((m_vdp2_vram[(address / 4 + 14) & 0x3ffff] & 0x20000000) ? 0xc0000000
                                                                : 0x00000000);
  current_rotation_table.cx =
      (m_vdp2_vram[(address / 4 + 15) & 0x3ffff] & 0x3fff0000) |
      ((m_vdp2_vram[(address / 4 + 15) & 0x3ffff] & 0x20000000) ? 0xc0000000
                                                                : 0x00000000);
  current_rotation_table.cy =
      (m_vdp2_vram[(address / 4 + 15) & 0x3ffff] & 0x00003fff) << 16;
  if (current_rotation_table.cy & 0x20000000)
    current_rotation_table.cy |= 0xc0000000;
  current_rotation_table.cz =
      (m_vdp2_vram[(address / 4 + 16) & 0x3ffff] & 0x3fff0000) |
      ((m_vdp2_vram[(address / 4 + 16) & 0x3ffff] & 0x20000000) ? 0xc0000000
                                                                : 0x00000000);
  current_rotation_table.mx =
      (m_vdp2_vram[(address / 4 + 17) & 0x3ffff] & 0x3fffffc0) |
      ((m_vdp2_vram[(address / 4 + 17) & 0x3ffff] & 0x20000000) ? 0xc0000000
                                                                : 0x00000000);
  current_rotation_table.my =
      (m_vdp2_vram[(address / 4 + 18) & 0x3ffff] & 0x3fffffc0) |
      ((m_vdp2_vram[(address / 4 + 18) & 0x3ffff] & 0x20000000) ? 0xc0000000
                                                                : 0x00000000);
  current_rotation_table.kx =
      (m_vdp2_vram[(address / 4 + 19) & 0x3ffff] & 0x00ffffff) |
      ((m_vdp2_vram[(address / 4 + 19) & 0x3ffff] & 0x00800000) ? 0xff000000
                                                                : 0x00000000);
  current_rotation_table.ky =
      (m_vdp2_vram[(address / 4 + 20) & 0x3ffff] & 0x00ffffff) |
      ((m_vdp2_vram[(address / 4 + 20) & 0x3ffff] & 0x00800000) ? 0xff000000
                                                                : 0x00000000);
  current_rotation_table.kast =
      (m_vdp2_vram[(address / 4 + 21) & 0x3ffff] & 0xffffffc0);
  current_rotation_table.dkast =
      (m_vdp2_vram[(address / 4 + 22) & 0x3ffff] & 0x03ffffc0) |
      ((m_vdp2_vram[(address / 4 + 22) & 0x3ffff] & 0x02000000) ? 0xfc000000
                                                                : 0x00000000);
  current_rotation_table.dkax =
      (m_vdp2_vram[(address / 4 + 23) & 0x3ffff] & 0x03ffffc0) |
      ((m_vdp2_vram[(address / 4 + 23) & 0x3ffff] & 0x02000000) ? 0xfc000000
                                                                : 0x00000000);

  // Xst/Yst/KAst are raw table values here. RPRCTL is consumed by the
  // scanline latch, not interpreted as an enable/disable mask for data.

#define RP current_rotation_table

  LOGMASKED(LOG_ROZ, "Rotation parameter table (%d)\n", rot_parameter);
  LOGMASKED(LOG_ROZ, "xst = %x, yst = %x, zst = %x\n", RP.xst, RP.yst, RP.zst);
  LOGMASKED(LOG_ROZ, "dxst = %x, dyst = %x\n", RP.dxst, RP.dyst);
  LOGMASKED(LOG_ROZ, "dx = %x, dy = %x\n", RP.dx, RP.dy);
  LOGMASKED(LOG_ROZ, "A = %x, B = %x, C = %x, D = %x, E = %x, F = %x\n", RP.A,
            RP.B, RP.C, RP.D, RP.E, RP.F);
  LOGMASKED(LOG_ROZ, "px = %x, py = %x, pz = %x\n", RP.px, RP.py, RP.pz);
  LOGMASKED(LOG_ROZ, "cx = %x, cy = %x, cz = %x\n", RP.cx, RP.cy, RP.cz);
  LOGMASKED(LOG_ROZ, "mx = %x, my = %x\n", RP.mx, RP.my);
  LOGMASKED(LOG_ROZ, "kx = %x, ky = %x\n", RP.kx, RP.ky);
  LOGMASKED(LOG_ROZ, "kast = %x, dkast = %x, dkax = %x\n", RP.kast, RP.dkast,
            RP.dkax);

  /*Attempt to show on screen the rotation table*/
  if (DEBUG_DRAW_ROZ) {
    if (machine().input().code_pressed_once(JOYCODE_Y_UP_SWITCH))
      m_vdpdebug_roz++;

    if (machine().input().code_pressed_once(JOYCODE_Y_DOWN_SWITCH))
      m_vdpdebug_roz--;

    if (m_vdpdebug_roz > 10)
      m_vdpdebug_roz = 10;

    switch (m_vdpdebug_roz) {
    case 0:
      popmessage("Rotation parameter Table (%d)", rot_parameter);
      break;
    case 1:
      popmessage("xst = %x, yst = %x, zst = %x", RP.xst, RP.yst, RP.zst);
      break;
    case 2:
      popmessage("dxst = %x, dyst = %x", RP.dxst, RP.dyst);
      break;
    case 3:
      popmessage("dx = %x, dy = %x", RP.dx, RP.dy);
      break;
    case 4:
      popmessage("A = %x, B = %x, C = %x, D = %x, E = %x, F = %x", RP.A, RP.B,
                 RP.C, RP.D, RP.E, RP.F);
      break;
    case 5:
      popmessage("px = %x, py = %x, pz = %x", RP.px, RP.py, RP.pz);
      break;
    case 6:
      popmessage("cx = %x, cy = %x, cz = %x", RP.cx, RP.cy, RP.cz);
      break;
    case 7:
      popmessage("mx = %x, my = %x", RP.mx, RP.my);
      break;
    case 8:
      popmessage("kx = %x, ky = %x", RP.kx, RP.ky);
      break;
    case 9:
      popmessage("kast = %x, dkast = %x, dkax = %x", RP.kast, RP.dkast,
                 RP.dkax);
      break;
    case 10:
      break;
    }
  }
}

void saturn_state::vdp2_reset_rotation_latches() {
  std::fill(std::begin(m_rotation_line_valid), std::end(m_rotation_line_valid), false);
  m_rotation_latch_valid = false;
}

void saturn_state::vdp2_latch_rotation_parameters(int scanline) {
  if (scanline == 0)
    vdp2_reset_rotation_latches();
  int const step = m_vdp2->get_ystep_count();
  if (scanline < 0 || scanline >= ROTATION_SCANLINES || scanline % step ||
      scanline >= m_vdp2->get_vblank_start_position() * step || !(VDP2_R0ON || VDP2_R1ON))
    return;
  rotation_table const saved = current_rotation_table;
  unsigned const control = VDP2_RPRCTL;
  unsigned const counter = scanline / step;
  for (unsigned p = 0; p < 2; ++p) {
    vdp2_fill_rotation_parameter_table(p + 1);
    auto &r = current_rotation_table;
    unsigned const reload = control >> (p * 8);
    // ST-058 pp.152/158: the first parameter fetch loads all starts. A
    // subsequent request reloads once; otherwise accumulate the current
    // table's delta. Request bits are not coordinate-enable bits.
    if (!m_rotation_latch_valid || (reload & 1)) m_rotation_x[p] = r.xst;
    else m_rotation_x[p] += uint32_t(r.dxst);
    if (!m_rotation_latch_valid || (reload & 2)) m_rotation_y[p] = r.yst;
    else m_rotation_y[p] += uint32_t(r.dyst);
    if (!m_rotation_latch_valid || (reload & 4)) m_rotation_k[p] = r.kast;
    else m_rotation_k[p] += uint32_t(r.dkast);
    // The compositor uses absolute output counters. Normalize the latched
    // starts back to that origin, preserving the existing interlace stepping.
    r.xst = m_rotation_x[p] - uint32_t(int64_t(r.dxst) * counter);
    r.yst = m_rotation_y[p] - uint32_t(int64_t(r.dyst) * counter);
    r.kast = m_rotation_k[p] - uint32_t(int64_t(r.dkast) * counter);
    for (int row = scanline; row < std::min(scanline + step, ROTATION_SCANLINES); ++row)
      m_rotation_lines[row][p] = r;
  }
  for (int row = scanline; row < std::min(scanline + step, ROTATION_SCANLINES); ++row)
    m_rotation_line_valid[row] = true;
  m_rotation_latch_valid = true;
  m_vdp2_regs[0xb2 / 2] &= ~0x0707; // consumed at this parameter read
  current_rotation_table = saved;
}

void saturn_state::vdp2_load_rotation_line(uint8_t parameter, int line) {
  if (line >= 0 && line < ROTATION_SCANLINES && m_rotation_line_valid[line])
    current_rotation_table = m_rotation_lines[line][parameter - 1];
  else
    vdp2_fill_rotation_parameter_table(parameter);
}

/* check if RGB layer has rotation applied */
uint8_t saturn_state::vdp2_is_rotation_applied(uint8_t rot_parameter) {
#define _FIXED_1 (0x00010000)
#define _FIXED_0 (0x00000000)

  if (RP.A == _FIXED_1 && RP.B == _FIXED_0 && RP.C == _FIXED_0 &&
      RP.D == _FIXED_0 && RP.E == _FIXED_1 && RP.F == _FIXED_0 &&
      RP.dxst == _FIXED_0 && RP.dyst == _FIXED_1 && RP.dx == _FIXED_1 &&
      RP.dy == _FIXED_0 && RP.kx == _FIXED_1 && RP.ky == _FIXED_1 &&
      RP.xst == _FIXED_0 && RP.yst == _FIXED_0 &&
      !(rot_parameter == 1 ? VDP2_RAKTE : VDP2_RBKTE) &&
      m_vdp2->get_lsmd() != 3 && !(m_vdp2->get_hreso() & 2) &&
      !(rot_parameter == 1 ? VDP2_RAOVR : VDP2_RBOVR) &&
      current_tilemap.layer_name != 0x81 && !current_tilemap.line_screen_enabled &&
      !current_tilemap.mosaic_screen_enabled && !VDP2_R0SWE &&
      VDP2_RPMD < 2) // only a unit-step, coefficient-free translation
  {
    return 0;
  } else {
    return 1;
  }
}

uint8_t saturn_state::vdp2_are_map_registers_equal() {
  int i;

  for (i = 1; i < current_tilemap.map_count; i++) {
    if (current_tilemap.map_offset[i] != current_tilemap.map_offset[0]) {
      return 0;
    }
  }
  return 1;
}

void saturn_state::vdp2_check_fade_control_for_layer() {
  if (current_tilemap.fade_control & 1) {
    if (current_tilemap.fade_control & 2) {
      if ((VDP2_COBR & 0x1ff) == 0 && (VDP2_COBG & 0x1ff) == 0 &&
          (VDP2_COBB & 0x1ff) == 0) {
        current_tilemap.fade_control = 0;
      }
    } else {
      if ((VDP2_COAR & 0x1ff) == 0 && (VDP2_COAG & 0x1ff) == 0 &&
          (VDP2_COAB & 0x1ff) == 0) {
        current_tilemap.fade_control = 0;
      }
    }
  }
}

#define VDP2_CP_NBG0_PNMDR 0x0
#define VDP2_CP_NBG1_PNMDR 0x1
#define VDP2_CP_NBG2_PNMDR 0x2
#define VDP2_CP_NBG3_PNMDR 0x3
#define VDP2_CP_NBG0_CPDR 0x4
#define VDP2_CP_NBG1_CPDR 0x5
#define VDP2_CP_NBG2_CPDR 0x6
#define VDP2_CP_NBG3_CPDR 0x7

uint8_t saturn_state::vdp2_check_vram_cycle_pattern_registers(
    uint8_t access_command_pnmdr, uint8_t access_command_cpdr,
    uint8_t bitmap_enable) {
  // ST-058 pp.31-32,149: unpartitioned memories use only A0/B0;
  // high-resolution/exclusive modes use T0-T3, not the upper registers.
  // Rotation-owned banks do not execute normal-screen access commands.
  uint16_t const cycles[] = {VDP2_CYCA0L, VDP2_CYCA0U, VDP2_CYCA1L, VDP2_CYCA1U,
                            VDP2_CYCA2L, VDP2_CYCA2U, VDP2_CYCA3L, VDP2_CYCA3U};
  unsigned const slots = (m_vdp2->get_hreso() & 6) ? 4 : 8;
  unsigned found = bitmap_enable ? 1 : 0;
  for (unsigned bank = 0; bank < 4; ++bank) {
    if ((bank & 1) && !(VDP2_RAMCTL & (0x100U << (bank / 2))))
      continue;
    if ((bank >= 2 && VDP2_R1ON) || (VDP2_R0ON && ((VDP2_RAMCTL >> (bank * 2)) & 3)))
      continue;
    for (unsigned slot = 0; slot < slots; ++slot) {
      unsigned const command = (cycles[bank * 2 + slot / 4] >> (12 - (slot % 4) * 4)) & 15;
      if (command == access_command_pnmdr)
        found |= 1;
      if (command == access_command_cpdr)
        found |= 2;
    }
  }
  // This is a presence gate, not fetch-address matching or a slot arbiter.
  return found == 3;
}

/* The colour calculation ratio register (CCRSx/CCRNA/CCRNB/CCRR) holds a 5-bit
   value whose top image : second image weights are (31 - ratio) : (ratio + 1)
   out of 32, which maps exactly onto alpha_blend_r32()'s 256 level blend. */
static constexpr uint8_t vdp2_cc_blend_level(uint8_t ratio) {
  return uint8_t((0x1f - ratio) * 8);
}

void saturn_state::vdp2_compute_color_offset(int *r, int *g, int *b, int cor) {
  if (cor == 0) {
    *r = (VDP2_COAR & 0x100) ? (*r - (0x100 - (VDP2_COAR & 0xff)))
                             : ((VDP2_COAR & 0xff) + *r);
    *g = (VDP2_COAG & 0x100) ? (*g - (0x100 - (VDP2_COAG & 0xff)))
                             : ((VDP2_COAG & 0xff) + *g);
    *b = (VDP2_COAB & 0x100) ? (*b - (0x100 - (VDP2_COAB & 0xff)))
                             : ((VDP2_COAB & 0xff) + *b);
  } else {
    *r = (VDP2_COBR & 0x100) ? (*r - (0x100 - (VDP2_COBR & 0xff)))
                             : ((VDP2_COBR & 0xff) + *r);
    *g = (VDP2_COBG & 0x100) ? (*g - (0x100 - (VDP2_COBG & 0xff)))
                             : ((VDP2_COBG & 0xff) + *g);
    *b = (VDP2_COBB & 0x100) ? (*b - (0x100 - (VDP2_COBB & 0xff)))
                             : ((VDP2_COBB & 0xff) + *b);
  }
  if (*r < 0) {
    *r = 0;
  }
  if (*r > 0xff) {
    *r = 0xff;
  }
  if (*g < 0) {
    *g = 0;
  }
  if (*g > 0xff) {
    *g = 0xff;
  }
  if (*b < 0) {
    *b = 0;
  }
  if (*b > 0xff) {
    *b = 0xff;
  }
}

void saturn_state::vdp2_compute_color_offset_UINT32(rgb_t *rgb, int cor) {
  int _r = rgb->r();
  int _g = rgb->g();
  int _b = rgb->b();
  if (cor == 0) {
    _r = (VDP2_COAR & 0x100) ? (_r - (0x100 - (VDP2_COAR & 0xff)))
                             : ((VDP2_COAR & 0xff) + _r);
    _g = (VDP2_COAG & 0x100) ? (_g - (0x100 - (VDP2_COAG & 0xff)))
                             : ((VDP2_COAG & 0xff) + _g);
    _b = (VDP2_COAB & 0x100) ? (_b - (0x100 - (VDP2_COAB & 0xff)))
                             : ((VDP2_COAB & 0xff) + _b);
  } else {
    _r = (VDP2_COBR & 0x100) ? (_r - (0x100 - (VDP2_COBR & 0xff)))
                             : ((VDP2_COBR & 0xff) + _r);
    _g = (VDP2_COBG & 0x100) ? (_g - (0x100 - (VDP2_COBG & 0xff)))
                             : ((VDP2_COBG & 0xff) + _g);
    _b = (VDP2_COBB & 0x100) ? (_b - (0x100 - (VDP2_COBB & 0xff)))
                             : ((VDP2_COBB & 0xff) + _b);
  }
  if (_r < 0) {
    _r = 0;
  }
  if (_r > 0xff) {
    _r = 0xff;
  }
  if (_g < 0) {
    _g = 0;
  }
  if (_g > 0xff) {
    _g = 0xff;
  }
  if (_b < 0) {
    _b = 0;
  }
  if (_b > 0xff) {
    _b = 0xff;
  }

  *rgb = rgb_t(_r, _g, _b);
}

void saturn_state::vdp2_drawgfxzoom(bitmap_rgb32 &dest_bmp,
                                    const rectangle &clip, gfx_element *gfx,
                                    uint32_t code, uint32_t color, int flipx,
                                    int flipy, int sx, int sy, int transparency,
                                    int scalex, int scaley,
                                    int sprite_screen_width,
                                    int sprite_screen_height, int alpha) {
  rectangle myclip;

  if (!scalex || !scaley)
    return;

  if (gfx->has_pen_usage() && !(transparency & STV_TRANSPARENCY_NONE)) {
    int transmask;

    transmask = 1 << (0 & 0xff);

    if ((gfx->pen_usage(code) & ~transmask) == 0) {
      // character is totally transparent, no need to draw
      return;
    } else if ((gfx->pen_usage(code) & transmask) == 0) {
      // character is totally opaque, can disable transparency
      transparency |= STV_TRANSPARENCY_NONE;
    }
  }

  /*
  scalex and scaley are 16.16 fixed point numbers
  1<<15 : shrink to 50%
  1<<16 : uniform scale
  1<<17 : double to 200%
  */

  // force clip to bitmap boundary
  myclip = clip;
  myclip &= dest_bmp.cliprect();

  if (gfx) {
    const pen_t *pal = &m_palette->pen(
        gfx->colorbase() + gfx->granularity() * (color % gfx->colors()));
    const uint8_t *source_base = gfx->get_data(code % gfx->elements());

    // int sprite_screen_height = (scaley*gfx->height()+0x8000)>>16;
    // int sprite_screen_width = (scalex*gfx->width()+0x8000)>>16;

    if (sprite_screen_width && sprite_screen_height) {
      // compute sprite increment per screen pixel
      // int dx = (gfx->width()<<16)/sprite_screen_width;
      // int dy = (gfx->height()<<16)/sprite_screen_height;
      /* dx and dy are 16.16 zoom increments copied out of a uint32_t
         register pair, so a product with a pixel count does not fit in
         int32_t and signed overflow is undefined; widen it and truncate
         back, which is the value two's complement wrapping gives */
      int dx = current_tilemap.incx;
      int dy = current_tilemap.incy;

      int ex = sx + sprite_screen_width;
      int ey = sy + sprite_screen_height;

      int x_index_base;
      int y_index;

      if (flipx) {
        x_index_base = s32(s64(sprite_screen_width - 1) * dx);
        dx = -dx;
      } else {
        x_index_base = 0;
      }

      if (flipy) {
        y_index = s32(s64(sprite_screen_height - 1) * dy);
        dy = -dy;
      } else {
        y_index = 0;
      }

      if (sx < myclip.left()) {
        // clip left
        int pixels = myclip.left() - sx;
        sx += pixels;
        x_index_base += s32(s64(pixels) * dx);
      }
      if (sy < myclip.top()) {
        // clip top
        int pixels = myclip.top() - sy;
        sy += pixels;
        y_index += s32(s64(pixels) * dy);
      }
      if (ex > myclip.right() + 1) {
        // clip right
        int pixels = ex - myclip.right() - 1;
        ex -= pixels;
      }
      if (ey > myclip.bottom() + 1) {
        // clip bottom
        int pixels = ey - myclip.bottom() - 1;
        ey -= pixels;
      }

      // skip if inner loop doesn't draw anything
      if (ex > sx) {
        if (transparency & STV_TRANSPARENCY_ALPHA) {
          // case : STV_TRANSPARENCY_ALPHA
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source =
                source_base + (y_index >> 16) * gfx->rowbytes();
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              if (vdp2_window_process(x, y)) {
                int c = source[x_index >> 16];
                if ((transparency & STV_TRANSPARENCY_NONE) || (c != 0))
                  dest[x] = alpha_blend_r32(dest[x], pal[c], alpha);
              }
              x_index += dx;
            }

            y_index += dy;
          }
        } else if (transparency & STV_TRANSPARENCY_ADD_BLEND) {
          // case : STV_TRANSPARENCY_ADD_BLEND
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source =
                source_base + (y_index >> 16) * gfx->rowbytes();
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              if (vdp2_window_process(x, y)) {
                int c = source[x_index >> 16];
                if ((transparency & STV_TRANSPARENCY_NONE) || (c != 0))
                  dest[x] = add_blend_r32(dest[x], pal[c]);
              }
              x_index += dx;
            }

            y_index += dy;
          }
        } else {
          // case : STV_TRANSPARENCY_PEN
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source =
                source_base + (y_index >> 16) * gfx->rowbytes();
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              if (vdp2_window_process(x, y)) {
                int c = source[x_index >> 16];
                if ((transparency & STV_TRANSPARENCY_NONE) || (c != 0))
                  dest[x] = pal[c];
              }
              x_index += dx;
            }

            y_index += dy;
          }
        }
      }
    }
  }
}

void saturn_state::vdp2_drawgfxzoom_rgb555(
    bitmap_rgb32 &dest_bmp, const rectangle &clip, uint32_t code,
    uint32_t color, int flipx, int flipy, int sx, int sy, int transparency,
    int scalex, int scaley, int sprite_screen_width, int sprite_screen_height,
    int alpha) {
  rectangle myclip;
  uint8_t *gfxdata;

  gfxdata = m_vdp2_legacy.gfx_decode.get() + code * 0x20;

  if (!scalex || !scaley)
    return;

#if 0
	if (gfx->has_pen_usage() && !(transparency & STV_TRANSPARENCY_NONE))
	{
		int transmask = 0;

		transmask = 1 << (0 & 0xff);

		if ((gfx->pen_usage(code) & ~transmask) == 0)
			/* character is totally transparent, no need to draw */
			return;
		else if ((gfx->pen_usage(code) & transmask) == 0)
			/* character is totally opaque, can disable transparency */
			transparency |= STV_TRANSPARENCY_NONE;
	}
#endif

  /*
  scalex and scaley are 16.16 fixed point numbers
  1<<15 : shrink to 50%
  1<<16 : uniform scale
  1<<17 : double to 200%
  */

  // force clip to bitmap boundary
  myclip = clip;
  myclip &= dest_bmp.cliprect();

  //  if( gfx )
  {
    //      const uint8_t *source_base = gfx->get_data(code % gfx->elements());

    // int sprite_screen_height = (scaley*gfx->height()+0x8000)>>16;
    // int sprite_screen_width = (scalex*gfx->width()+0x8000)>>16;

    if (sprite_screen_width && sprite_screen_height) {
      /* compute sprite increment per screen pixel */
      // int dx = (gfx->width()<<16)/sprite_screen_width;
      // int dy = (gfx->height()<<16)/sprite_screen_height;
      /* dx and dy are 16.16 zoom increments copied out of a uint32_t
         register pair, so a product with a pixel count does not fit in
         int32_t and signed overflow is undefined; widen it and truncate
         back, which is the value two's complement wrapping gives */
      int dx = current_tilemap.incx;
      int dy = current_tilemap.incy;

      int ex = sx + sprite_screen_width;
      int ey = sy + sprite_screen_height;

      int x_index_base;
      int y_index;

      if (flipx) {
        x_index_base = s32(s64(sprite_screen_width - 1) * dx);
        dx = -dx;
      } else {
        x_index_base = 0;
      }

      if (flipy) {
        y_index = s32(s64(sprite_screen_height - 1) * dy);
        dy = -dy;
      } else {
        y_index = 0;
      }

      if (sx < myclip.left()) {
        // clip left
        int pixels = myclip.left() - sx;
        sx += pixels;
        x_index_base += s32(s64(pixels) * dx);
      }
      if (sy < myclip.top()) {
        // clip top
        int pixels = myclip.top() - sy;
        sy += pixels;
        y_index += s32(s64(pixels) * dy);
      }
      if (ex > myclip.right() + 1) {
        // clip right
        int pixels = ex - myclip.right() - 1;
        ex -= pixels;
      }
      if (ey > myclip.bottom() + 1) {
        // clip bottom
        int pixels = ey - myclip.bottom() - 1;
        ey -= pixels;
      }

      // skip if inner loop doesn't draw anything
      if (ex > sx) {
        if (transparency & STV_TRANSPARENCY_ALPHA) {
          // case : STV_TRANSPARENCY_ALPHA
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source = gfxdata + (y_index >> 16) * 16;
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              int data = (source[(x_index >> 16) * 2] << 8) |
                         source[(x_index >> 16) * 2 + 1];
              int b = pal5bit((data & 0x7c00) >> 10);
              int g = pal5bit((data & 0x03e0) >> 5);
              int r = pal5bit(data & 0x001f);
              if (current_tilemap.fade_control & 1)
                vdp2_compute_color_offset(&r, &g, &b,
                                          current_tilemap.fade_control & 2);

              if (vdp2_window_process(x, y) &&
                  ((transparency & STV_TRANSPARENCY_NONE) || (data & 0x8000)))
                dest[x] = alpha_blend_r32(dest[x], rgb_t(r, g, b), alpha);

              x_index += dx;
            }

            y_index += dy;
          }
        } else if (transparency & STV_TRANSPARENCY_ADD_BLEND) {
          // case : STV_TRANSPARENCY_ADD_BLEND
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source = gfxdata + (y_index >> 16) * 16;
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              int data = (source[(x_index >> 16) * 2] << 8) |
                         source[(x_index >> 16) * 2 + 1];
              int b = pal5bit((data & 0x7c00) >> 10);
              int g = pal5bit((data & 0x03e0) >> 5);
              int r = pal5bit(data & 0x001f);
              if (current_tilemap.fade_control & 1)
                vdp2_compute_color_offset(&r, &g, &b,
                                          current_tilemap.fade_control & 2);

              if (vdp2_window_process(x, y) &&
                  ((transparency & STV_TRANSPARENCY_NONE) || (data & 0x8000)))
                dest[x] = add_blend_r32(dest[x], rgb_t(r, g, b));

              x_index += dx;
            }

            y_index += dy;
          }
        } else {
          // case : STV_TRANSPARENCY_PEN
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source = gfxdata + (y_index >> 16) * 16;
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              int data = (source[(x_index >> 16) * 2] << 8) |
                         source[(x_index >> 16) * 2 + 1];
              int b = pal5bit((data & 0x7c00) >> 10);
              int g = pal5bit((data & 0x03e0) >> 5);
              int r = pal5bit(data & 0x001f);
              if (current_tilemap.fade_control & 1)
                vdp2_compute_color_offset(&r, &g, &b,
                                          current_tilemap.fade_control & 2);

              if (vdp2_window_process(x, y) &&
                  ((transparency & STV_TRANSPARENCY_NONE) || (data & 0x8000)))
                dest[x] = rgb_t(r, g, b);

              x_index += dx;
            }

            y_index += dy;
          }
        }
      }
    }
  }
}

void saturn_state::vdp2_drawgfxzoom_rgb888(
    bitmap_rgb32 &dest_bmp, const rectangle &clip, uint32_t code,
    uint32_t color, int flipx, int flipy, int sx, int sy, int transparency,
    int scalex, int scaley, int sprite_screen_width, int sprite_screen_height,
    int alpha) {
  rectangle myclip;
  uint8_t *gfxdata;

  gfxdata = m_vdp2_legacy.gfx_decode.get() + code * 0x20;

  if (!scalex || !scaley)
    return;

#if 0
	if (gfx->has_pen_usage() && !(transparency & STV_TRANSPARENCY_NONE))
	{
		int transmask = 0;

		transmask = 1 << (0 & 0xff);

		if ((gfx->pen_usage(code) & ~transmask) == 0)
			/* character is totally transparent, no need to draw */
			return;
		else if ((gfx->pen_usage(code) & transmask) == 0)
			/* character is totally opaque, can disable transparency */
			transparency |= STV_TRANSPARENCY_NONE;
	}
#endif

  /*
  scalex and scaley are 16.16 fixed point numbers
  1<<15 : shrink to 50%
  1<<16 : uniform scale
  1<<17 : double to 200%
  */

  // force clip to bitmap boundary
  myclip = clip;
  myclip &= dest_bmp.cliprect();

  //  if( gfx )
  {
    //      const uint8_t *source_base = gfx->get_data(code % gfx->elements());

    // int sprite_screen_height = (scaley*gfx->height()+0x8000)>>16;
    // int sprite_screen_width = (scalex*gfx->width()+0x8000)>>16;

    if (sprite_screen_width && sprite_screen_height) {
      /* compute sprite increment per screen pixel */
      // int dx = (gfx->width()<<16)/sprite_screen_width;
      // int dy = (gfx->height()<<16)/sprite_screen_height;
      /* dx and dy are 16.16 zoom increments copied out of a uint32_t
         register pair, so a product with a pixel count does not fit in
         int32_t and signed overflow is undefined; widen it and truncate
         back, which is the value two's complement wrapping gives */
      int dx = current_tilemap.incx;
      int dy = current_tilemap.incy;

      int ex = sx + sprite_screen_width;
      int ey = sy + sprite_screen_height;

      int x_index_base;
      int y_index;

      if (flipx) {
        x_index_base = s32(s64(sprite_screen_width - 1) * dx);
        dx = -dx;
      } else {
        x_index_base = 0;
      }

      if (flipy) {
        y_index = s32(s64(sprite_screen_height - 1) * dy);
        dy = -dy;
      } else {
        y_index = 0;
      }

      if (sx < myclip.left()) {
        // clip left
        int pixels = myclip.left() - sx;
        sx += pixels;
        x_index_base += s32(s64(pixels) * dx);
      }
      if (sy < myclip.top()) {
        // clip top
        int pixels = myclip.top() - sy;
        sy += pixels;
        y_index += s32(s64(pixels) * dy);
      }
      if (ex > myclip.right() + 1) {
        // clip right
        int pixels = ex - myclip.right() - 1;
        ex -= pixels;
      }
      if (ey > myclip.bottom() + 1) {
        // clip bottom
        int pixels = ey - myclip.bottom() - 1;
        ey -= pixels;
      }

      // skip if inner loop doesn't draw anything
      if (ex > sx) {
        if (transparency & STV_TRANSPARENCY_ALPHA) {
          // case : STV_TRANSPARENCY_ALPHA
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source = gfxdata + (y_index >> 16) * 32;
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              uint32_t data = (source[(x_index >> 16) * 4 + 0] << 24) |
                              (source[(x_index >> 16) * 4 + 1] << 16) |
                              (source[(x_index >> 16) * 4 + 2] << 8) |
                              (source[(x_index >> 16) * 4 + 3] << 0);
              int b = (data & 0xff0000) >> 16;
              int g = (data & 0x00ff00) >> 8;
              int r = (data & 0x0000ff) >> 0;
              if (current_tilemap.fade_control & 1)
                vdp2_compute_color_offset(&r, &g, &b,
                                          current_tilemap.fade_control & 2);

              if (vdp2_window_process(x, y) &&
                  ((transparency & STV_TRANSPARENCY_NONE) ||
                   (data & 0x80000000)))
                dest[x] = alpha_blend_r32(dest[x], rgb_t(r, g, b), alpha);

              x_index += dx;
            }

            y_index += dy;
          }
        } else if (transparency & STV_TRANSPARENCY_ADD_BLEND) {
          // case : STV_TRANSPARENCY_ADD_BLEND
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source = gfxdata + (y_index >> 16) * 32;
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              uint32_t data = (source[(x_index >> 16) * 4 + 0] << 24) |
                              (source[(x_index >> 16) * 4 + 1] << 16) |
                              (source[(x_index >> 16) * 4 + 2] << 8) |
                              (source[(x_index >> 16) * 4 + 3] << 0);
              int b = (data & 0xff0000) >> 16;
              int g = (data & 0x00ff00) >> 8;
              int r = (data & 0x0000ff) >> 0;
              if (current_tilemap.fade_control & 1)
                vdp2_compute_color_offset(&r, &g, &b,
                                          current_tilemap.fade_control & 2);

              if (vdp2_window_process(x, y) &&
                  ((transparency & STV_TRANSPARENCY_NONE) ||
                   (data & 0x80000000)))
                dest[x] = add_blend_r32(dest[x], rgb_t(r, g, b));

              x_index += dx;
            }

            y_index += dy;
          }
        } else {
          // case : STV_TRANSPARENCY_PEN
          for (int y = sy; y < ey; y++) {
            uint8_t const *const source = gfxdata + (y_index >> 16) * 32;
            uint32_t *const dest = &dest_bmp.pix(y);

            int x_index = x_index_base;
            for (int x = sx; x < ex; x++) {
              uint32_t data = (source[(x_index >> 16) * 4 + 0] << 24) |
                              (source[(x_index >> 16) * 4 + 1] << 16) |
                              (source[(x_index >> 16) * 4 + 2] << 8) |
                              (source[(x_index >> 16) * 4 + 3] << 0);
              int b = (data & 0xff0000) >> 16;
              int g = (data & 0x00ff00) >> 8;
              int r = (data & 0x0000ff) >> 0;
              if (current_tilemap.fade_control & 1)
                vdp2_compute_color_offset(&r, &g, &b,
                                          current_tilemap.fade_control & 2);

              if (vdp2_window_process(x, y) &&
                  ((transparency & STV_TRANSPARENCY_NONE) ||
                   (data & 0x80000000)))
                dest[x] = rgb_t(r, g, b);

              x_index += dx;
            }

            y_index += dy;
          }
        }
      }
    }
  }
}

void saturn_state::vdp2_drawgfx_rgb555(bitmap_rgb32 &dest_bmp,
                                       const rectangle &clip, uint32_t code,
                                       int flipx, int flipy, int sx, int sy,
                                       int transparency, int alpha) {
  rectangle myclip;
  uint8_t *gfxdata;
  int sprite_screen_width, sprite_screen_height;

  gfxdata = m_vdp2_legacy.gfx_decode.get() + code * 0x20;
  sprite_screen_width = sprite_screen_height = 8;

  // force clip to bitmap boundary
  myclip = clip;
  myclip &= dest_bmp.cliprect();

  {
    /* dx and dy are 16.16 zoom increments copied out of a uint32_t
       register pair, so a product with a pixel count does not fit in
       int32_t and signed overflow is undefined; widen it and truncate
       back, which is the value two's complement wrapping gives */
    int dx = current_tilemap.incx;
    int dy = current_tilemap.incy;

    int ex = sx + sprite_screen_width;
    int ey = sy + sprite_screen_height;

    int x_index_base;
    int y_index;

    if (flipx) {
      x_index_base = s32(s64(sprite_screen_width - 1) * dx);
      dx = -dx;
    } else {
      x_index_base = 0;
    }

    if (flipy) {
      y_index = s32(s64(sprite_screen_height - 1) * dy);
      dy = -dy;
    } else {
      y_index = 0;
    }

    if (sx < myclip.left()) {
      // clip left
      int pixels = myclip.left() - sx;
      sx += pixels;
      x_index_base += s32(s64(pixels) * dx);
    }
    if (sy < myclip.top()) {
      // clip top
      int pixels = myclip.top() - sy;
      sy += pixels;
      y_index += s32(s64(pixels) * dy);
    }
    if (ex > myclip.right() + 1) {
      // clip right
      int pixels = ex - myclip.right() - 1;
      ex -= pixels;
    }
    if (ey > myclip.bottom() + 1) {
      // clip bottom
      int pixels = ey - myclip.bottom() - 1;
      ey -= pixels;
    }

    // skip if inner loop doesn't draw anything
    if (ex > sx) {
      for (int y = sy; y < ey; y++) {
        uint8_t const *const source = gfxdata + (y_index >> 16) * 16;
        uint32_t *const dest = &dest_bmp.pix(y);

        int x_index = x_index_base;
        for (int x = sx; x < ex; x++) {
          uint16_t data = (source[(x_index >> 16) * 2] << 8) |
                          source[(x_index >> 16) * 2 + 1];
          if (vdp2_window_process(x, y) &&
              ((data & 0x8000) || (transparency & STV_TRANSPARENCY_NONE))) {
            int b = pal5bit((data & 0x7c00) >> 10);
            int g = pal5bit((data & 0x03e0) >> 5);
            int r = pal5bit(data & 0x001f);
            if (current_tilemap.fade_control & 1)
              vdp2_compute_color_offset(&r, &g, &b,
                                        current_tilemap.fade_control & 2);

            if (transparency & STV_TRANSPARENCY_ALPHA)
              dest[x] = alpha_blend_r32(dest[x], rgb_t(r, g, b), alpha);
            else
              dest[x] = rgb_t(r, g, b);
          }
          x_index += dx;
        }

        y_index += dy;
      }
    }
  }
}

void saturn_state::vdp2_drawgfx_rgb888(bitmap_rgb32 &dest_bmp,
                                       const rectangle &clip, uint32_t code,
                                       int flipx, int flipy, int sx, int sy,
                                       int transparency, int alpha) {
  rectangle myclip;
  uint8_t *gfxdata;
  int sprite_screen_width, sprite_screen_height;

  gfxdata = m_vdp2_legacy.gfx_decode.get() + code * 0x20;
  sprite_screen_width = sprite_screen_height = 8;

  // force clip to bitmap boundary
  myclip = clip;
  myclip &= dest_bmp.cliprect();

  {
    /* dx and dy are 16.16 zoom increments copied out of a uint32_t
       register pair, so a product with a pixel count does not fit in
       int32_t and signed overflow is undefined; widen it and truncate
       back, which is the value two's complement wrapping gives */
    int dx = current_tilemap.incx;
    int dy = current_tilemap.incy;

    int ex = sx + sprite_screen_width;
    int ey = sy + sprite_screen_height;

    int x_index_base;
    int y_index;

    if (flipx) {
      x_index_base = s32(s64(sprite_screen_width - 1) * dx);
      dx = -dx;
    } else {
      x_index_base = 0;
    }

    if (flipy) {
      y_index = s32(s64(sprite_screen_height - 1) * dy);
      dy = -dy;
    } else {
      y_index = 0;
    }

    if (sx < myclip.left()) {
      // clip left
      int pixels = myclip.left() - sx;
      sx += pixels;
      x_index_base += s32(s64(pixels) * dx);
    }
    if (sy < myclip.top()) {
      // clip top
      int pixels = myclip.top() - sy;
      sy += pixels;
      y_index += s32(s64(pixels) * dy);
    }
    if (ex > myclip.right() + 1) {
      // clip right
      int pixels = ex - myclip.right() - 1;
      ex -= pixels;
    }
    if (ey > myclip.bottom() + 1) {
      // clip bottom
      int pixels = ey - myclip.bottom() - 1;
      ey -= pixels;
    }

    // skip if inner loop doesn't draw anything
    if (ex > sx) {
      for (int y = sy; y < ey; y++) {
        uint8_t const *const source = gfxdata + (y_index >> 16) * 32;
        uint32_t *const dest = &dest_bmp.pix(y);

        int x_index = x_index_base;

        for (int x = sx; x < ex; x++) {
          uint32_t data = (source[(x_index >> 16) * 4 + 0] << 24) |
                          (source[(x_index >> 16) * 4 + 1] << 16) |
                          (source[(x_index >> 16) * 4 + 2] << 8) |
                          (source[(x_index >> 16) * 4 + 3] << 0);
          if (vdp2_window_process(x, y) &&
              ((data & 0x80000000) || (transparency & STV_TRANSPARENCY_NONE))) {
            int b = (data & 0xff0000) >> 16;
            int g = (data & 0x00ff00) >> 8;
            int r = (data & 0x0000ff);

            if (current_tilemap.fade_control & 1)
              vdp2_compute_color_offset(&r, &g, &b,
                                        current_tilemap.fade_control & 2);

            if (transparency & STV_TRANSPARENCY_ALPHA)
              dest[x] = alpha_blend_r32(dest[x], rgb_t(r, g, b), alpha);
            else
              dest[x] = rgb_t(r, g, b);
          }
          x_index += dx;
        }

        y_index += dy;
      }
    }
  }
}

void saturn_state::vdp2_drawgfx_alpha(bitmap_rgb32 &dest_bmp,
                                      const rectangle &clip, gfx_element *gfx,
                                      uint32_t code, uint32_t color, int flipx,
                                      int flipy, int offsx, int offsy,
                                      int transparency, int alpha) {
  const pen_t *pal = &m_palette->pen(
      gfx->colorbase() + gfx->granularity() * (color % gfx->colors()));
  const uint8_t *source_base = gfx->get_data(code % gfx->elements());
  int x_index_base, y_index, sx, sy, ex, ey;
  int xinc, yinc;

  xinc = flipx ? -1 : 1;
  yinc = flipy ? -1 : 1;

  x_index_base = flipx ? gfx->width() - 1 : 0;
  y_index = flipy ? gfx->height() - 1 : 0;

  // start coordinates
  sx = offsx;
  sy = offsy;

  // end coordinates
  ex = sx + gfx->width();
  ey = sy + gfx->height();

  if (sx < clip.left()) {
    // clip left
    int pixels = clip.left() - sx;
    sx += pixels;
    x_index_base += xinc * pixels;
  }
  if (sy < clip.top()) {
    // clip top
    int pixels = clip.top() - sy;
    sy += pixels;
    y_index += yinc * pixels;
  }
  if (ex > clip.right() + 1) {
    // clip right
    ex = clip.right() + 1;
  }
  if (ey > clip.bottom() + 1) {
    // clip bottom
    ey = clip.bottom() + 1;
  }

  // skip if inner loop doesn't draw anything
  if (ex > sx) {
    for (int y = sy; y < ey; y++) {
      uint8_t const *const source = source_base + y_index * gfx->rowbytes();
      uint32_t *const dest = &dest_bmp.pix(y);
      int x_index = x_index_base;
      for (int x = sx; x < ex; x++) {
        if (vdp2_window_process(x, y)) {
          int c = (source[x_index]);
          if ((transparency & STV_TRANSPARENCY_NONE) || (c != 0))
            dest[x] = alpha_blend_r32(dest[x], pal[c], alpha);
        }

        x_index += xinc;
      }
      y_index += yinc;
    }
  }
}

void saturn_state::vdp2_drawgfx_transpen(bitmap_rgb32 &dest_bmp,
                                         const rectangle &clip,
                                         gfx_element *gfx, uint32_t code,
                                         uint32_t color, int flipx, int flipy,
                                         int offsx, int offsy,
                                         int transparency) {
  const pen_t *pal = &m_palette->pen(
      gfx->colorbase() + gfx->granularity() * (color % gfx->colors()));
  const uint8_t *source_base = gfx->get_data(code % gfx->elements());
  int x_index_base, y_index, sx, sy, ex, ey;
  int xinc, yinc;

  xinc = flipx ? -1 : 1;
  yinc = flipy ? -1 : 1;

  x_index_base = flipx ? gfx->width() - 1 : 0;
  y_index = flipy ? gfx->height() - 1 : 0;

  // start coordinates
  sx = offsx;
  sy = offsy;

  // end coordinates
  ex = sx + gfx->width();
  ey = sy + gfx->height();

  if (sx < clip.left()) {
    // clip left
    int pixels = clip.left() - sx;
    sx += pixels;
    x_index_base += xinc * pixels;
  }
  if (sy < clip.top()) {
    // clip top
    int pixels = clip.top() - sy;
    sy += pixels;
    y_index += yinc * pixels;
  }
  if (ex > clip.right() + 1) {
    // clip right
    ex = clip.right() + 1;
  }
  if (ey > clip.bottom() + 1) {
    // clip bottom
    ey = clip.bottom() + 1;
  }

  // skip if inner loop doesn't draw anything
  if (ex > sx) {
    for (int y = sy; y < ey; y++) {
      uint8_t const *const source = source_base + y_index * gfx->rowbytes();
      uint32_t *const dest = &dest_bmp.pix(y);
      int x_index = x_index_base;
      for (int x = sx; x < ex; x++) {
        if (vdp2_window_process(x, y)) {
          int c = (source[x_index]);
          if ((transparency & STV_TRANSPARENCY_NONE) || (c != 0))
            dest[x] = pal[c];
        }

        x_index += xinc;
      }
      y_index += yinc;
    }
  }
}

// - arcadegh uses incy zoom for most games but Joust
void saturn_state::draw_4bpp_bitmap(bitmap_rgb32 &bitmap,
                                    const rectangle &cliprect) {
  int xsize, ysize, xsize_mask, ysize_mask;
  int xsrc, ysrc, xdst, ydst;
  int src_offs;
  uint8_t *vram = m_vdp2_legacy.gfx_decode.get();
  uint32_t map_offset = current_tilemap.bitmap_map * 0x20000;
  // Match the point sampler: wrap in configured VRAM, not always 4 Mbits.
  unsigned const vram_mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  int scrollx = current_tilemap.scrollx;
  int scrolly = current_tilemap.scrolly;
  uint16_t dot_data;
  uint16_t pal_bank;
  int xf, yf;

  xsize = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
  ysize = (current_tilemap.bitmap_size & 1) ? 512 : 256;

  xsize_mask = (current_tilemap.linescroll_enable) ? 1024 : xsize;
  ysize_mask = (current_tilemap.vertical_linescroll_enable) ? 512 : ysize;

  pal_bank = current_tilemap.bitmap_palette_number;
  pal_bank += current_tilemap.colour_ram_address_offset;
  pal_bank &= 7;
  pal_bank <<= 8;
  if (current_tilemap.fade_control & 1)
    pal_bank += ((current_tilemap.fade_control & 2) ? (2 * 2048) : (2048));

  for (ydst = cliprect.top(); ydst <= cliprect.bottom(); ydst++) {
    for (xdst = cliprect.left(); xdst <= cliprect.right(); xdst++) {
      if (!vdp2_window_process(xdst, ydst))
        continue;

      xf = uint32_t(uint64_t(current_tilemap.incx) * xdst + current_tilemap.scrollx_fraction);
      xf >>= 16;
      yf = uint32_t(uint64_t(current_tilemap.incy) * ydst + current_tilemap.scrolly_fraction);
      yf >>= 16;

      xsrc = (xf + scrollx) & (xsize_mask - 1);
      ysrc = (yf + scrolly) & (ysize_mask - 1);
      src_offs = (xsrc + (ysrc * xsize));
      src_offs /= 2;
      src_offs += map_offset;
      src_offs &= vram_mask;

      dot_data = vram[src_offs] >> ((xsrc & 1) ? 0 : 4);
      dot_data &= 0xf;

      if ((dot_data != 0) ||
          (current_tilemap.transparency & STV_TRANSPARENCY_NONE)) {
        dot_data += pal_bank;

        if (current_tilemap.colour_calculation_enabled == 0)
          bitmap.pix(ydst, xdst) = m_palette->pen(dot_data);
        else if (VDP2_CCMD)
          bitmap.pix(ydst, xdst) = add_blend_r32(bitmap.pix(ydst, xdst), m_palette->pen(dot_data));
        else
          bitmap.pix(ydst, xdst) =
              alpha_blend_r32(bitmap.pix(ydst, xdst), m_palette->pen(dot_data),
                              current_tilemap.alpha);
      }
    }
  }
}

void saturn_state::draw_8bpp_bitmap(bitmap_rgb32 &bitmap,
                                    const rectangle &cliprect) {
  int xsize, ysize, xsize_mask, ysize_mask;
  int xsrc, ysrc, xdst, ydst;
  int src_offs;
  uint8_t *vram = m_vdp2_legacy.gfx_decode.get();
  uint32_t map_offset = current_tilemap.bitmap_map * 0x20000;
  // Match the point sampler: wrap in configured VRAM, not always 4 Mbits.
  unsigned const vram_mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  int scrollx = current_tilemap.scrollx;
  int scrolly = current_tilemap.scrolly;
  uint16_t dot_data;
  uint16_t pal_bank;
  int xf, yf;

  xsize = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
  ysize = (current_tilemap.bitmap_size & 1) ? 512 : 256;

  xsize_mask = (current_tilemap.linescroll_enable) ? 1024 : xsize;
  ysize_mask = (current_tilemap.vertical_linescroll_enable) ? 512 : ysize;

  pal_bank = current_tilemap.bitmap_palette_number;
  pal_bank += current_tilemap.colour_ram_address_offset;
  pal_bank &= 7;
  pal_bank <<= 8;
  if (current_tilemap.fade_control & 1)
    pal_bank += ((current_tilemap.fade_control & 2) ? (2 * 2048) : (2048));

  for (ydst = cliprect.top(); ydst <= cliprect.bottom(); ydst++) {
    for (xdst = cliprect.left(); xdst <= cliprect.right(); xdst++) {
      if (!vdp2_window_process(xdst, ydst))
        continue;

      xf = uint32_t(uint64_t(current_tilemap.incx) * xdst + current_tilemap.scrollx_fraction);
      xf >>= 16;
      yf = uint32_t(uint64_t(current_tilemap.incy) * ydst + current_tilemap.scrolly_fraction);
      yf >>= 16;

      xsrc = (xf + scrollx) & (xsize_mask - 1);
      ysrc = (yf + scrolly) & (ysize_mask - 1);
      src_offs = (xsrc + (ysrc * xsize));
      src_offs += map_offset;
      src_offs &= vram_mask;

      dot_data = vram[src_offs];

      if ((dot_data != 0) ||
          (current_tilemap.transparency & STV_TRANSPARENCY_NONE)) {
        dot_data += pal_bank;

        if (current_tilemap.colour_calculation_enabled == 0)
          bitmap.pix(ydst, xdst) = m_palette->pen(dot_data);
        else if (VDP2_CCMD)
          bitmap.pix(ydst, xdst) = add_blend_r32(bitmap.pix(ydst, xdst), m_palette->pen(dot_data));
        else
          bitmap.pix(ydst, xdst) =
              alpha_blend_r32(bitmap.pix(ydst, xdst), m_palette->pen(dot_data),
                              current_tilemap.alpha);
      }
    }
  }
}

void saturn_state::draw_11bpp_bitmap(bitmap_rgb32 &bitmap,
                                     const rectangle &cliprect) {
  int xsize, ysize, xsize_mask, ysize_mask;
  int xsrc, ysrc, xdst, ydst;
  int src_offs;
  uint8_t *vram = m_vdp2_legacy.gfx_decode.get();
  uint32_t map_offset = current_tilemap.bitmap_map * 0x20000;
  // Match the point sampler: wrap in configured VRAM, not always 4 Mbits.
  unsigned const vram_mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  int scrollx = current_tilemap.scrollx;
  int scrolly = current_tilemap.scrolly;
  uint16_t dot_data;
  uint16_t pal_bank;
  int xf, yf;

  xsize = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
  ysize = (current_tilemap.bitmap_size & 1) ? 512 : 256;

  xsize_mask = (current_tilemap.linescroll_enable) ? 1024 : xsize;
  ysize_mask = (current_tilemap.vertical_linescroll_enable) ? 512 : ysize;

  pal_bank = 0;
  if (current_tilemap.fade_control & 1)
    pal_bank = ((current_tilemap.fade_control & 2) ? (2 * 2048) : (2048));

  for (ydst = cliprect.top(); ydst <= cliprect.bottom(); ydst++) {
    for (xdst = cliprect.left(); xdst <= cliprect.right(); xdst++) {
      if (!vdp2_window_process(xdst, ydst))
        continue;

      xf = uint32_t(uint64_t(current_tilemap.incx) * xdst + current_tilemap.scrollx_fraction);
      xf >>= 16;
      yf = uint32_t(uint64_t(current_tilemap.incy) * ydst + current_tilemap.scrolly_fraction);
      yf >>= 16;

      xsrc = (xf + scrollx) & (xsize_mask - 1);
      ysrc = (yf + scrolly) & (ysize_mask - 1);
      src_offs = (xsrc + (ysrc * xsize));
      src_offs *= 2;
      src_offs += map_offset;
      src_offs &= vram_mask;

      dot_data = ((vram[src_offs] << 8) | (vram[src_offs + 1] << 0)) & 0x7ff;

      if ((dot_data != 0) ||
          (current_tilemap.transparency & STV_TRANSPARENCY_NONE)) {
        dot_data += pal_bank;

        if (current_tilemap.colour_calculation_enabled == 0)
          bitmap.pix(ydst, xdst) = m_palette->pen(dot_data);
        else if (VDP2_CCMD)
          bitmap.pix(ydst, xdst) = add_blend_r32(bitmap.pix(ydst, xdst), m_palette->pen(dot_data));
        else
          bitmap.pix(ydst, xdst) =
              alpha_blend_r32(bitmap.pix(ydst, xdst), m_palette->pen(dot_data),
                              current_tilemap.alpha);
      }
    }
  }
}

void saturn_state::draw_rgb15_bitmap(bitmap_rgb32 &bitmap,
                                     const rectangle &cliprect) {
  int xsize, ysize, xsize_mask, ysize_mask;
  int xsrc, ysrc, xdst, ydst;
  int src_offs;
  uint8_t *vram = m_vdp2_legacy.gfx_decode.get();
  uint32_t map_offset = current_tilemap.bitmap_map * 0x20000;
  // Match the point sampler: wrap in configured VRAM, not always 4 Mbits.
  unsigned const vram_mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  int scrollx = current_tilemap.scrollx;
  int scrolly = current_tilemap.scrolly;
  int r, g, b;
  uint16_t dot_data;
  int xf, yf;

  xsize = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
  ysize = (current_tilemap.bitmap_size & 1) ? 512 : 256;

  xsize_mask = (current_tilemap.linescroll_enable) ? 1024 : xsize;
  ysize_mask = (current_tilemap.vertical_linescroll_enable) ? 512 : ysize;

  for (ydst = cliprect.top(); ydst <= cliprect.bottom(); ydst++) {
    for (xdst = cliprect.left(); xdst <= cliprect.right(); xdst++) {
      if (!vdp2_window_process(xdst, ydst))
        continue;

      xf = uint32_t(uint64_t(current_tilemap.incx) * xdst + current_tilemap.scrollx_fraction);
      xf >>= 16;
      yf = uint32_t(uint64_t(current_tilemap.incy) * ydst + current_tilemap.scrolly_fraction);
      yf >>= 16;

      xsrc = (xf + scrollx) & (xsize_mask - 1);
      ysrc = (yf + scrolly) & (ysize_mask - 1);
      src_offs = (xsrc + (ysrc * xsize));
      src_offs *= 2;
      src_offs += map_offset;
      src_offs &= vram_mask;

      dot_data = (vram[src_offs] << 8) | (vram[src_offs + 1] << 0);

      if ((dot_data & 0x8000) ||
          (current_tilemap.transparency & STV_TRANSPARENCY_NONE)) {
        b = pal5bit((dot_data & 0x7c00) >> 10);
        g = pal5bit((dot_data & 0x03e0) >> 5);
        r = pal5bit((dot_data & 0x001f) >> 0);

        if (current_tilemap.fade_control & 1)
          vdp2_compute_color_offset(&r, &g, &b,
                                    current_tilemap.fade_control & 2);

        if (current_tilemap.colour_calculation_enabled == 0)
          bitmap.pix(ydst, xdst) = rgb_t(r, g, b);
        else if (VDP2_CCMD)
          bitmap.pix(ydst, xdst) = add_blend_r32(bitmap.pix(ydst, xdst), rgb_t(r, g, b));
        else
          bitmap.pix(ydst, xdst) = alpha_blend_r32(
              bitmap.pix(ydst, xdst), rgb_t(r, g, b), current_tilemap.alpha);
      }
    }
  }
}

void saturn_state::draw_rgb32_bitmap(bitmap_rgb32 &bitmap,
                                     const rectangle &cliprect) {
  int xsize, ysize, xsize_mask, ysize_mask;
  int xsrc, ysrc, xdst, ydst;
  int src_offs;
  uint8_t *vram = m_vdp2_legacy.gfx_decode.get();
  uint32_t map_offset = current_tilemap.bitmap_map * 0x20000;
  // Match the point sampler: wrap in configured VRAM, not always 4 Mbits.
  unsigned const vram_mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  int scrollx = current_tilemap.scrollx;
  int scrolly = current_tilemap.scrolly;
  int r, g, b;
  uint32_t dot_data;
  int xf, yf;

  xsize = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
  ysize = (current_tilemap.bitmap_size & 1) ? 512 : 256;

  xsize_mask = (current_tilemap.linescroll_enable) ? 1024 : xsize;
  ysize_mask = (current_tilemap.vertical_linescroll_enable) ? 512 : ysize;

  for (ydst = cliprect.top(); ydst <= cliprect.bottom(); ydst++) {
    for (xdst = cliprect.left(); xdst <= cliprect.right(); xdst++) {
      if (!vdp2_window_process(xdst, ydst))
        continue;

      xf = uint32_t(uint64_t(current_tilemap.incx) * xdst + current_tilemap.scrollx_fraction);
      xf >>= 16;
      yf = uint32_t(uint64_t(current_tilemap.incy) * ydst + current_tilemap.scrolly_fraction);
      yf >>= 16;

      xsrc = (xf + scrollx) & (xsize_mask - 1);
      ysrc = (yf + scrolly) & (ysize_mask - 1);
      src_offs = (xsrc + (ysrc * xsize));
      src_offs *= 4;
      src_offs += map_offset;
      src_offs &= vram_mask;

      dot_data = (vram[src_offs + 0] << 24) | (vram[src_offs + 1] << 16) |
                 (vram[src_offs + 2] << 8) | (vram[src_offs + 3] << 0);

      if ((dot_data & 0x80000000) ||
          (current_tilemap.transparency & STV_TRANSPARENCY_NONE)) {
        b = ((dot_data & 0x00ff0000) >> 16);
        g = ((dot_data & 0x0000ff00) >> 8);
        r = ((dot_data & 0x000000ff) >> 0);

        if (current_tilemap.fade_control & 1)
          vdp2_compute_color_offset(&r, &g, &b,
                                    current_tilemap.fade_control & 2);

        if (current_tilemap.colour_calculation_enabled == 0)
          bitmap.pix(ydst, xdst) = rgb_t(r, g, b);
        else if (VDP2_CCMD)
          bitmap.pix(ydst, xdst) = add_blend_r32(bitmap.pix(ydst, xdst), rgb_t(r, g, b));
        else
          bitmap.pix(ydst, xdst) = alpha_blend_r32(
              bitmap.pix(ydst, xdst), rgb_t(r, g, b), current_tilemap.alpha);
      }
    }
  }
}

void saturn_state::vdp2_draw_basic_bitmap(bitmap_rgb32 &bitmap,
                                          const rectangle &cliprect) {
  if (!current_tilemap.enabled)
    return;

  if (current_tilemap.layer_name & 0x80) {
    // A cached bitmap has no pattern-name table. Cover its complete source
    // surface, not stale watch ranges from a previously rendered tilemap.
    // ST-058 table 4.11: 4/8/16/16/32 bits per dot, 20000H base alignment.
    unsigned const width = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
    unsigned const height = (current_tilemap.bitmap_size & 1) ? 512 : 256;
    unsigned const shift = current_tilemap.colour_depth < 3 ? current_tilemap.colour_depth : current_tilemap.colour_depth - 1;
    unsigned const bytes = (width * height / 2) << shift;
    unsigned const memory = m_vdp2->get_vramsz() ? 0x100000 : 0x80000;
    unsigned const start = (current_tilemap.bitmap_map * 0x20000) & (memory - 1);
    bool const wraps = bytes >= memory || start + bytes > memory;
    vdp2_layer_data.map_offset_min = vdp2_layer_data.map_offset_max = 0;
    // A wrapped range has two pieces. Conservatively watch the physical
    // allocation, as for wrapping character data; never miss its low part.
    vdp2_layer_data.tile_offset_min = wraps ? 0 : start / 4;
    vdp2_layer_data.tile_offset_max = wraps ? memory / 4 : (start + bytes) / 4;
  }

  /* new bitmap code, supposed to rewrite the old one. Not supposed to be clean,
   * but EFFICIENT! */
  if (current_tilemap.incx == 0x10000 && current_tilemap.incy == 0x10000) {
    switch (current_tilemap.colour_depth) {
    case 0:
      draw_4bpp_bitmap(bitmap, cliprect);
      return;
    case 1:
      draw_8bpp_bitmap(bitmap, cliprect);
      return;
    case 2:
      draw_11bpp_bitmap(bitmap, cliprect);
      return;
    case 3:
      draw_rgb15_bitmap(bitmap, cliprect);
      return;
    case 4:
      draw_rgb32_bitmap(bitmap, cliprect);
      return;
    }

    /* intentional fall-through*/
    popmessage(
        "%d %s %s %s", current_tilemap.colour_depth,
        current_tilemap.transparency & STV_TRANSPARENCY_NONE ? "no trans"
                                                             : "trans",
        current_tilemap.colour_calculation_enabled ? "cc" : "no cc",
        (current_tilemap.incx == 0x10000 && current_tilemap.incy == 0x10000)
            ? "no zoom"
            : "zoom");
  } else {
    switch (current_tilemap.colour_depth) {
    case 0:
      draw_4bpp_bitmap(bitmap, cliprect);
      return;
    case 1:
      draw_8bpp_bitmap(bitmap, cliprect);
      return;
    case 2:
      draw_11bpp_bitmap(bitmap, cliprect);
      return;
    case 3:
      draw_rgb15_bitmap(bitmap, cliprect);
      return;
    case 4:
      draw_rgb32_bitmap(bitmap, cliprect);
      return;
    }

    /* intentional fall-through*/
    popmessage(
        "%d %s %s %s", current_tilemap.colour_depth,
        current_tilemap.transparency & STV_TRANSPARENCY_NONE ? "no trans"
                                                             : "trans",
        current_tilemap.colour_calculation_enabled ? "cc" : "no cc",
        (current_tilemap.incx == 0x10000 && current_tilemap.incy == 0x10000)
            ? "no zoom"
            : "zoom");
  }
}

/*---------------------------------------------------------------------------
| Plane Size | Pattern Name Data Size | Character Size | Map Bits / Address |
----------------------------------------------------------------------------|
|            |                        | 1 H x 1 V      | bits 6-0 * 0x02000 |
|            | 1 word                 |-------------------------------------|
|            |                        | 2 H x 2 V      | bits 8-0 * 0x00800 |
| 1 H x 1 V  ---------------------------------------------------------------|
|            |                        | 1 H x 1 V      | bits 5-0 * 0x04000 |
|            | 2 words                |-------------------------------------|
|            |                        | 2 H x 2 V      | bits 7-0 * 0x01000 |
-----------------------------------------------------------------------------
|            |                        | 1 H x 1 V      | bits 6-1 * 0x04000 |
|            | 1 word                 |-------------------------------------|
|            |                        | 2 H x 2 V      | bits 8-1 * 0x01000 |
| 2 H x 1 V  ---------------------------------------------------------------|
|            |                        | 1 H x 1 V      | bits 5-1 * 0x08000 |
|            | 2 words                |-------------------------------------|
|            |                        | 2 H x 2 V      | bits 7-1 * 0x02000 |
-----------------------------------------------------------------------------
|            |                        | 1 H x 1 V      | bits 6-2 * 0x08000 |
|            | 1 word                 |-------------------------------------|
|            |                        | 2 H x 2 V      | bits 8-2 * 0x02000 |
| 2 H x 2 V  ---------------------------------------------------------------|
|            |                        | 1 H x 1 V      | bits 5-2 * 0x10000 |
|            | 2 words                |-------------------------------------|
|            |                        | 2 H x 2 V      | bits 7-2 * 0x04000 |
--the-highest-bit-is-ignored-if-vram-is-only-4mbits------------------------*/

/*
4.2 Sega's Cell / Character Pattern / Page / Plane / Map system, aka a rather
annoying thing that makes optimizations hard (this is only for the normal
tilemaps at the moment, i haven't even thought about the ROZ ones)

Tiles:

Cells are 8x8 gfx stored in video ram, they can be of various colour depths

Character Patterns can be 8x8 or 16x16 (1 hcell x 1 vcell or 2 hcell x 2 vcell)
  (a 16x16 character pattern is 4 8x8 cells put together)

A page is made up of 64x64 cells, thats 64x64 character patterns in 8x8 mode or
32x32 character patterns in 16x16 mode. 64 * 8  = 512 (0x200) 32 * 16 = 512
(0x200) A page is _always_ 512 (0x200) pixels in each direction

in 1 word mode a 32*16 x 32*16 page is 0x0800 bytes
in 1 word mode a 64*8  x 64*8  page is 0x2000 bytes
in 2 word mode a 32*16 x 32*16 page is 0x1000 bytes
in 2 word mode a 64*8  x 64*8  page is 0x4000 bytes

either 1, 2 or 4 pages make each plane depending on the plane size register (per
tilemap) therefore each plane is either 64 * 8 * 1 x 64 * 8 * 1 (512 x 512) 64 *
8 * 2 x 64 * 8 * 1 (1024 x 512) 64 * 8 * 2 x 64 * 8 * 2 (1024 x 1024)

  32 * 16 * 1 x 32 * 16 * 1 (512 x 512)
  32 * 16 * 2 x 32 * 16 * 1 (1024 x 512)
  32 * 16 * 2 x 32 * 16 * 2 (1024 x 1024)

map is always enabled?
  map is a 2x2 arrangement of planes, all 4 of the planes can be the same.

*/

void saturn_state::vdp2_get_map_page(int x, int y, int *_map, int *_page) {
  int page = 0;
  int map;

  if (current_tilemap.map_count == 4) {
    if (current_tilemap.tile_size == 0) {
      if (current_tilemap.plane_size & 1) {
        page = ((x >> 6) & 1);
        map = (x >> 7) & 1;
      } else {
        map = (x >> 6) & 1;
      }

      if (current_tilemap.plane_size & 2) {
        page |= ((y >> (6 - 1)) & 2);
        map |= ((y >> (7 - 1)) & 2);
      } else {
        map |= ((y >> (6 - 1)) & 2);
      }
    } else {
      if (current_tilemap.plane_size & 1) {
        page = ((x >> 5) & 1);
        map = (x >> 6) & 1;
      } else {
        map = (x >> 5) & 1;
      }

      if (current_tilemap.plane_size & 2) {
        page |= ((y >> (5 - 1)) & 2);
        map |= ((y >> (6 - 1)) & 2);
      } else {
        map |= ((y >> (5 - 1)) & 2);
      }
    }
  } else // 16
  {
    if (current_tilemap.tile_size == 0) {
      if (current_tilemap.plane_size & 1) {
        page = ((x >> 6) & 1);
        map = (x >> 7) & 3;
      } else {
        map = (x >> 6) & 3;
      }

      if (current_tilemap.plane_size & 2) {
        page |= ((y >> (6 - 1)) & 2);
        map |= ((y >> (7 - 2)) & 12);
      } else {
        map |= ((y >> (6 - 2)) & 12);
      }
    } else {
      if (current_tilemap.plane_size & 1) {
        page = ((x >> 5) & 1);
        map = (x >> 6) & 3;
      } else {
        map = (x >> 5) & 3;
      }

      if (current_tilemap.plane_size & 2) {
        page |= ((y >> (5 - 1)) & 2);
        map |= ((y >> (6 - 2)) & 12);
      } else {
        map |= ((y >> (5 - 2)) & 12);
      }
    }
  }
  *_page = page;
  *_map = map;
}

void saturn_state::vdp2_draw_basic_tilemap(bitmap_rgb32 &bitmap,
                                           const rectangle &cliprect) {
  /* hopefully this is easier to follow than it is efficient .. */

  /* I call character patterns tiles .. even if they represent up to 4 tiles */

  /* Page variables */
  int pgtiles_x, pgpixels_x;
  int pgtiles_y, pgpixels_y;
  int pgsize_bytes, pgsize_dwords;

  /* Plane Variables */
  int pltiles_x, plpixels_x;
  int pltiles_y, plpixels_y;
  int plsize_bytes /*, plsize_dwords*/;

  /* Map Variables */
  int mptiles_x, mppixels_x;
  int mptiles_y, mppixels_y;
  int mpsize_bytes, mpsize_dwords;

  /* work Variables */
  int i, x, y;
  int base[16];

  int scalex, scaley;
  int tilesizex, tilesizey;
  int drawypos, drawxpos;

  int tilecodemin = 0x10000000, tilecodemax = 0;

  if (current_tilemap.incx == 0 || current_tilemap.incy == 0)
    return;

  if (current_tilemap.colour_calculation_enabled == 1) {
    if (VDP2_CCMD) {
      current_tilemap.transparency |= STV_TRANSPARENCY_ADD_BLEND;
    } else {
      current_tilemap.transparency |= STV_TRANSPARENCY_ALPHA;
    }
  }

  scalex = s32(s64(0x100000000U) / s64(current_tilemap.incx));
  scaley = s32(s64(0x100000000U) / s64(current_tilemap.incy));
  /* scalex and scaley are 0x100000000 / inc, so a zoomed-in layer gives them
     values up to 2^30 and inc == 2 gives INT_MIN; both this product and the
     scroll products below are signed and overflow, which is undefined rather
     than wrapped.  Widen and truncate, which is the value wrapping gives.
     The negation is done in 64 bits so that -(INT_MIN) is not itself an
     overflow. */
  tilesizex = s32(s64(scalex) * 8);
  tilesizey = s32(s64(scaley) * 8);
  drawypos = drawxpos = 0;

  /* Calculate the Number of tiles for x / y directions of each page (actually
   * these will be the same */
  /* (2-current_tilemap.tile_size) << 5) */
  pgtiles_x = ((2 - current_tilemap.tile_size)
               << 5); // 64 (8x8 mode) or 32 (16x16 mode)
  pgtiles_y = ((2 - current_tilemap.tile_size)
               << 5); // 64 (8x8 mode) or 32 (16x16 mode)

  /* Calculate the Page Size in BYTES */
  /* 64 * 64 * (1 * 2) = 0x2000 bytes
     32 * 32 * (1 * 2) = 0x0800 bytes
     64 * 64 * (2 * 2) = 0x4000 bytes
     32 * 32 * (2 * 2) = 0x1000 bytes */

  pgsize_bytes =
      (pgtiles_x * pgtiles_y) * ((2 - current_tilemap.pattern_data_size) * 2);

  /*---------------------------------------------------------------------------
  | Plane Size | Pattern Name Data Size | Character Size | Map Bits / Address |
  ----------------------------------------------------------------------------|
  |            |                        | 1 H x 1 V      | bits 6-0 * 0x02000 |
  |            | 1 word                 |-------------------------------------|
  |            |                        | 2 H x 2 V      | bits 8-0 * 0x00800 |
  | 1 H x 1 V  ---------------------------------------------------------------|
  |            |                        | 1 H x 1 V      | bits 5-0 * 0x04000 |
  |            | 2 words                |-------------------------------------|
  |            |                        | 2 H x 2 V      | bits 7-0 * 0x01000 |
  ---------------------------------------------------------------------------*/

  /* Page Dimensions are always 0x200 pixes (512x512) */
  pgpixels_x = 0x200;
  pgpixels_y = 0x200;

  /* Work out the Plane Size in tiles and Plane Dimensions (pixels) */
  switch (current_tilemap.plane_size & 3) {
  case 0: // 1 page * 1 page
    pltiles_x = pgtiles_x;
    plpixels_x = pgpixels_x;
    pltiles_y = pgtiles_y;
    plpixels_y = pgpixels_y;
    break;

  case 1: // 2 pages * 1 page
    pltiles_x = pgtiles_x * 2;
    plpixels_x = pgpixels_x * 2;
    pltiles_y = pgtiles_y;
    plpixels_y = pgpixels_y;
    break;

  case 3: // 2 pages * 2 pages
    pltiles_x = pgtiles_x * 2;
    plpixels_x = pgpixels_x * 2;
    pltiles_y = pgtiles_y * 2;
    plpixels_y = pgpixels_y * 2;
    break;

  default:
    // illegal
    pltiles_x = pgtiles_x;
    plpixels_x = pgpixels_x;
    pltiles_y = pgtiles_y * 2;
    plpixels_y = pgpixels_y * 2;
    break;
  }

  /* Plane Size in BYTES */
  /* still the same as before
     (64 * 1) * (64 * 1) * (1 * 2) = 0x02000 bytes
     (32 * 1) * (32 * 1) * (1 * 2) = 0x00800 bytes
     (64 * 1) * (64 * 1) * (2 * 2) = 0x04000 bytes
     (32 * 1) * (32 * 1) * (2 * 2) = 0x01000 bytes
     changed
     (64 * 2) * (64 * 1) * (1 * 2) = 0x04000 bytes
     (32 * 2) * (32 * 1) * (1 * 2) = 0x01000 bytes
     (64 * 2) * (64 * 1) * (2 * 2) = 0x08000 bytes
     (32 * 2) * (32 * 1) * (2 * 2) = 0x02000 bytes
     changed
     (64 * 2) * (64 * 1) * (1 * 2) = 0x08000 bytes
     (32 * 2) * (32 * 1) * (1 * 2) = 0x02000 bytes
     (64 * 2) * (64 * 1) * (2 * 2) = 0x10000 bytes
     (32 * 2) * (32 * 1) * (2 * 2) = 0x04000 bytes
  */

  plsize_bytes =
      (pltiles_x * pltiles_y) * ((2 - current_tilemap.pattern_data_size) * 2);

  /*---------------------------------------------------------------------------
  | Plane Size | Pattern Name Data Size | Character Size | Map Bits / Address |
  -----------------------------------------------------------------------------
  | 1 H x 1 V   see above, nothing has changed                                |
  -----------------------------------------------------------------------------
  |            |                        | 1 H x 1 V      | bits 6-1 * 0x04000 |
  |            | 1 word                 |-------------------------------------|
  |            |                        | 2 H x 2 V      | bits 8-1 * 0x01000 |
  | 2 H x 1 V  ---------------------------------------------------------------|
  |            |                        | 1 H x 1 V      | bits 5-1 * 0x08000 |
  |            | 2 words                |-------------------------------------|
  |            |                        | 2 H x 2 V      | bits 7-1 * 0x02000 |
  -----------------------------------------------------------------------------
  |            |                        | 1 H x 1 V      | bits 6-2 * 0x08000 |
  |            | 1 word                 |-------------------------------------|
  |            |                        | 2 H x 2 V      | bits 8-2 * 0x02000 |
  | 2 H x 2 V  ---------------------------------------------------------------|
  |            |                        | 1 H x 1 V      | bits 5-2 * 0x10000 |
  |            | 2 words                |-------------------------------------|
  |            |                        | 2 H x 2 V      | bits 7-2 * 0x04000 |
  --the-highest-bit-is-ignored-if-vram-is-only-4mbits------------------------*/

  /* Work out the Map Sizes in tiles, Map Dimensions */
  /* maps are always enabled? */
  if (current_tilemap.map_count == 4) {
    mptiles_x = pltiles_x * 2;
    mptiles_y = pltiles_y * 2;
    mppixels_x = plpixels_x * 2;
    mppixels_y = plpixels_y * 2;
  } else {
    mptiles_x = pltiles_x * 4;
    mptiles_y = pltiles_y * 4;
    mppixels_x = plpixels_x * 4;
    mppixels_y = plpixels_y * 4;
  }

  /* Map Size in BYTES */
  mpsize_bytes =
      (mptiles_x * mptiles_y) * ((2 - current_tilemap.pattern_data_size) * 2);

  /*-----------------------------------------------------------------------------------------------------------
  |            |                        | 1 H x 1 V      | bits 6-1 (upper mask
  0x07f) (0x1ff >> 2) * 0x04000 | |            | 1 word
  |---------------------------------------------------------------------| | | |
  2 H x 2 V      | bits 8-1 (upper mask 0x1ff) (0x1ff >> 0) * 0x01000 | | 2 H x
  1 V
  -----------------------------------------------------------------------------------------------|
  |            |                        | 1 H x 1 V      | bits 5-1 (upper mask
  0x03f) (0x1ff >> 3) * 0x08000 | |            | 2 words
  |---------------------------------------------------------------------| | | |
  2 H x 2 V      | bits 7-1 (upper mask 0x0ff) (0x1ff >> 1) * 0x02000 |
  -------------------------------------------------------------------------------------------------------------
  lower mask = ~current_tilemap.plane_size
  -----------------------------------------------------------------------------------------------------------*/

  /* Precalculate bases from MAP registers */
  for (i = 0; i < current_tilemap.map_count; i++) {
    static const int shifttable[4] = {0, 1, 2, 2};

    int uppermask, uppermaskshift;

    uppermaskshift = (1 - current_tilemap.pattern_data_size) |
                     ((1 - current_tilemap.tile_size) << 1);
    uppermask = 0x1ff >> uppermaskshift;

    base[i] = ((current_tilemap.map_offset[i] & uppermask) >>
               shifttable[current_tilemap.plane_size]) *
              plsize_bytes;

    base[i] &=
        0x7ffff; /* shienryu needs this for the text layer, is there a problem
                    elsewhere or is it just right without the ram cart */

    base[i] = base[i] / 4; // convert bytes to DWORDS
  }

  /* other bits */
  // current_tilemap.trans_enabled = current_tilemap.trans_enabled ?
  // STV_TRANSPARENCY_NONE : STV_TRANSPARENCY_PEN;
  current_tilemap.scrollx &= mppixels_x - 1;
  current_tilemap.scrolly &= mppixels_y - 1;

  pgsize_dwords = pgsize_bytes / 4;
  // plsize_dwords = plsize_bytes /4;
  mpsize_dwords = mpsize_bytes / 4;

  if (!current_tilemap.enabled)
    return; // stop right now if its disabled ...

  /* most things we need (or don't need) to work out are now worked out */

  for (y = 0; y < mptiles_y; y++) {
    int ypageoffs;
    int page, map, newbase, offs, data;
    int tilecode, flipyx, pal, gfx = 0;

    map = 0;
    page = 0;
    if (y == 0) {
      int drawyposinc =
          s32(s64(tilesizey) * (current_tilemap.tile_size ? 2 : 1));
      drawypos = s32(-s64(current_tilemap.scrolly) * scaley);
      while (((drawypos + drawyposinc) >> 16) < cliprect.top()) {
        drawypos += drawyposinc;
        y++;
      }
      mptiles_y += y;
    } else {
      drawypos += s32(s64(tilesizey) * (current_tilemap.tile_size ? 2 : 1));
    }
    if ((drawypos >> 16) > cliprect.bottom())
      break;

    ypageoffs = y & (pgtiles_y - 1);

    for (x = 0; x < mptiles_x; x++) {
      int xpageoffs;
      int tilecodespacing = 1;

      if (x == 0) {
        int drawxposinc =
            s32(s64(tilesizex) * (current_tilemap.tile_size ? 2 : 1));
        drawxpos = s32(-s64(current_tilemap.scrollx) * scalex);
        while (((drawxpos + drawxposinc) >> 16) < cliprect.left()) {
          drawxpos += drawxposinc;
          x++;
        }
        mptiles_x += x;
      } else {
        drawxpos += s32(s64(tilesizex) * (current_tilemap.tile_size ? 2 : 1));
      }
      if ((drawxpos >> 16) > cliprect.right())
        break;

      xpageoffs = x & (pgtiles_x - 1);

      vdp2_get_map_page(x, y, &map, &page);

      newbase = base[map] + page * pgsize_dwords;
      offs = (ypageoffs * pgtiles_x) + xpageoffs;

      /* GET THE TILE INFO ... */
      /* 1 word per tile mode with supplement bits */
      if (current_tilemap.pattern_data_size == 1) {
        data = m_vdp2_vram[newbase + offs / 2];
        data = (offs & 1) ? (data & 0x0000ffff) : ((data & 0xffff0000) >> 16);

        /* Supplement Mode 12 bits, no flip */
        if (current_tilemap.character_number_supplement == 1) {
          /* no flip */ flipyx = 0;
          /* 8x8 */ if (current_tilemap.tile_size == 0)
            tilecode =
                (data & 0x0fff) +
                ((current_tilemap.supplementary_character_bits & 0x1c) << 10);
          /* 16x16 */ else
            tilecode =
                ((data & 0x0fff) << 2) +
                (current_tilemap.supplementary_character_bits & 0x03) +
                ((current_tilemap.supplementary_character_bits & 0x10) << 10);
        }
        /* Supplement Mode 10 bits, with flip */
        else {
          /* flip bits */ flipyx = (data & 0x0c00) >> 10;
          /* 8x8 */ if (current_tilemap.tile_size == 0)
            tilecode = (data & 0x03ff) +
                       ((current_tilemap.supplementary_character_bits) << 10);
          /* 16x16 */ else
            tilecode =
                ((data & 0x03ff) << 2) +
                (current_tilemap.supplementary_character_bits & 0x03) +
                ((current_tilemap.supplementary_character_bits & 0x1c) << 10);
        }

        /*>16cols*/ if (current_tilemap.colour_depth != 0)
          pal = ((data & 0x7000) >> 8);
        /*16 cols*/ else
          pal = ((data & 0xf000) >> 12) +
                ((current_tilemap.supplementary_palette_bits) << 4);

      }
      /* 2 words per tile, no supplement bits */
      else {
        data = m_vdp2_vram[newbase + offs];
        tilecode = (data & 0x00007fff);
        pal = (data & 0x007f0000) >> 16;
        //          specialc = (data & 0x10000000)>>28;
        flipyx = (data & 0xc0000000) >> 30;
      }
      /* WE'VE GOT THE TILE INFO ... */


      /* DECODE ANY TILES WE NEED TO DECODE */

      pal += current_tilemap.colour_ram_address_offset
             << 4; // bios uses this ..

      /*Enable fading bit*/
      if (current_tilemap.fade_control & 1) {
        /*Select fading bit*/
        pal += ((current_tilemap.fade_control & 2) ? (0x100) : (0x80));
      }

      if (current_tilemap.colour_depth == 1) {
        gfx = 2;
        pal = pal >> 4;
        tilecode &= 0x7fff;
        if (tilecode == 0x7fff)
          tilecode--; /* prevents crash but unsure what should happen; wrapping?
                       */
        tilecodespacing = 2;
      } else if (current_tilemap.colour_depth == 0) {
        gfx = 0;
        tilecode &= 0x7fff;
        tilecodespacing = 1;
      } else if (current_tilemap.colour_depth == 3) {
        /* 32768 colour: an 8x8 cell is 8 rows of 8 dots at two bytes per
           dot, so the four cells of a 16x16 character sit four character
           numbers apart - the same step the unzoomed path hardcodes */
        tilecodespacing = 4;
      } else if (current_tilemap.colour_depth == 4) {
        /* 16M colour: four bytes per dot, so eight character numbers */
        tilecodespacing = 8;
      }
      /* TILES ARE NOW DECODED */

      if (!m_vdp2->get_vramsz())
        tilecode &= 0x3fff;

      if (tilecode < tilecodemin)
        tilecodemin = tilecode;
      if (tilecode > tilecodemax)
        tilecodemax = tilecode;

      /* DRAW! */
      if (current_tilemap.incx != 0x10000 || current_tilemap.incy != 0x10000 ||
          current_tilemap.transparency & STV_TRANSPARENCY_ADD_BLEND) {
#define SCR_TILESIZE_X (((drawxpos + tilesizex) >> 16) - (drawxpos >> 16))
#define SCR_TILESIZE_X1(startx)                                                \
  (((drawxpos + (startx) + tilesizex) >> 16) - ((drawxpos + (startx)) >> 16))
#define SCR_TILESIZE_Y (((drawypos + tilesizey) >> 16) - (drawypos >> 16))
#define SCR_TILESIZE_Y1(starty)                                                \
  (((drawypos + (starty) + tilesizey) >> 16) - ((drawypos + (starty)) >> 16))
        if (current_tilemap.tile_size == 1) {
          if (current_tilemap.colour_depth == 4) {
            /* RGB888 */
            vdp2_drawgfxzoom_rgb888(
                bitmap, cliprect,
                tilecode + (0 + (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos >> 16, drawypos >> 16,
                current_tilemap.transparency, scalex, scaley, SCR_TILESIZE_X,
                SCR_TILESIZE_Y, current_tilemap.alpha);
            vdp2_drawgfxzoom_rgb888(
                bitmap, cliprect,
                tilecode + (1 - (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, (drawxpos + tilesizex) >> 16,
                drawypos >> 16, current_tilemap.transparency, scalex, scaley,
                SCR_TILESIZE_X1(tilesizex), SCR_TILESIZE_Y,
                current_tilemap.alpha);
            vdp2_drawgfxzoom_rgb888(
                bitmap, cliprect,
                tilecode + (2 + (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos >> 16,
                (drawypos + tilesizey) >> 16, current_tilemap.transparency,
                scalex, scaley, SCR_TILESIZE_X, SCR_TILESIZE_Y1(tilesizey),
                current_tilemap.alpha);
            vdp2_drawgfxzoom_rgb888(
                bitmap, cliprect,
                tilecode + (3 - (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, (drawxpos + tilesizex) >> 16,
                (drawypos + tilesizey) >> 16, current_tilemap.transparency,
                scalex, scaley, SCR_TILESIZE_X1(tilesizex),
                SCR_TILESIZE_Y1(tilesizey), current_tilemap.alpha);
          } else if (current_tilemap.colour_depth == 3) {
            /* RGB555 */
            vdp2_drawgfxzoom_rgb555(
                bitmap, cliprect,
                tilecode + (0 + (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos >> 16, drawypos >> 16,
                current_tilemap.transparency, scalex, scaley, SCR_TILESIZE_X,
                SCR_TILESIZE_Y, current_tilemap.alpha);
            vdp2_drawgfxzoom_rgb555(
                bitmap, cliprect,
                tilecode + (1 - (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, (drawxpos + tilesizex) >> 16,
                drawypos >> 16, current_tilemap.transparency, scalex, scaley,
                SCR_TILESIZE_X1(tilesizex), SCR_TILESIZE_Y,
                current_tilemap.alpha);
            vdp2_drawgfxzoom_rgb555(
                bitmap, cliprect,
                tilecode + (2 + (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos >> 16,
                (drawypos + tilesizey) >> 16, current_tilemap.transparency,
                scalex, scaley, SCR_TILESIZE_X, SCR_TILESIZE_Y1(tilesizey),
                current_tilemap.alpha);
            vdp2_drawgfxzoom_rgb555(
                bitmap, cliprect,
                tilecode + (3 - (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, (drawxpos + tilesizex) >> 16,
                (drawypos + tilesizey) >> 16, current_tilemap.transparency,
                scalex, scaley, SCR_TILESIZE_X1(tilesizex),
                SCR_TILESIZE_Y1(tilesizey), current_tilemap.alpha);
          } else {
            /* normal */
            vdp2_drawgfxzoom(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (0 + (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos >> 16, drawypos >> 16,
                current_tilemap.transparency, scalex, scaley, SCR_TILESIZE_X,
                SCR_TILESIZE_Y, current_tilemap.alpha);
            vdp2_drawgfxzoom(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (1 - (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, (drawxpos + tilesizex) >> 16,
                drawypos >> 16, current_tilemap.transparency, scalex, scaley,
                SCR_TILESIZE_X1(tilesizex), SCR_TILESIZE_Y,
                current_tilemap.alpha);
            vdp2_drawgfxzoom(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (2 + (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos >> 16,
                (drawypos + tilesizey) >> 16, current_tilemap.transparency,
                scalex, scaley, SCR_TILESIZE_X, SCR_TILESIZE_Y1(tilesizey),
                current_tilemap.alpha);
            vdp2_drawgfxzoom(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (3 - (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, (drawxpos + tilesizex) >> 16,
                (drawypos + tilesizey) >> 16, current_tilemap.transparency,
                scalex, scaley, SCR_TILESIZE_X1(tilesizex),
                SCR_TILESIZE_Y1(tilesizey), current_tilemap.alpha);
          }
        } else {
          if (current_tilemap.colour_depth == 4) {
            vdp2_drawgfxzoom_rgb888(bitmap, cliprect, tilecode, pal, flipyx & 1,
                                    flipyx & 2, drawxpos >> 16, drawypos >> 16,
                                    current_tilemap.transparency, scalex,
                                    scaley, SCR_TILESIZE_X, SCR_TILESIZE_Y,
                                    current_tilemap.alpha);
          } else if (current_tilemap.colour_depth == 3) {
            vdp2_drawgfxzoom_rgb555(bitmap, cliprect, tilecode, pal, flipyx & 1,
                                    flipyx & 2, drawxpos >> 16, drawypos >> 16,
                                    current_tilemap.transparency, scalex,
                                    scaley, SCR_TILESIZE_X, SCR_TILESIZE_Y,
                                    current_tilemap.alpha);
          } else
            vdp2_drawgfxzoom(bitmap, cliprect, m_gfxdecode->gfx(gfx), tilecode,
                             pal, flipyx & 1, flipyx & 2, drawxpos >> 16,
                             drawypos >> 16, current_tilemap.transparency,
                             scalex, scaley, SCR_TILESIZE_X, SCR_TILESIZE_Y,
                             current_tilemap.alpha);
        }
      } else {
        int olddrawxpos, olddrawypos;
        olddrawxpos = drawxpos;
        drawxpos >>= 16;
        olddrawypos = drawypos;
        drawypos >>= 16;
        if (current_tilemap.tile_size == 1) {
          if (current_tilemap.colour_depth == 4) {
            /* normal */
            vdp2_drawgfx_rgb888(
                bitmap, cliprect,
                tilecode + (0 + (flipyx & 1) + (flipyx & 2)) * 8, flipyx & 1,
                flipyx & 2, drawxpos, drawypos, current_tilemap.transparency,
                current_tilemap.alpha);
            vdp2_drawgfx_rgb888(
                bitmap, cliprect,
                tilecode + (1 - (flipyx & 1) + (flipyx & 2)) * 8, flipyx & 1,
                flipyx & 2, drawxpos + 8, drawypos,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_rgb888(
                bitmap, cliprect,
                tilecode + (2 + (flipyx & 1) - (flipyx & 2)) * 8, flipyx & 1,
                flipyx & 2, drawxpos, drawypos + 8,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_rgb888(
                bitmap, cliprect,
                tilecode + (3 - (flipyx & 1) - (flipyx & 2)) * 8, flipyx & 1,
                flipyx & 2, drawxpos + 8, drawypos + 8,
                current_tilemap.transparency, current_tilemap.alpha);
          } else if (current_tilemap.colour_depth == 3) {
            /* normal */
            vdp2_drawgfx_rgb555(
                bitmap, cliprect,
                tilecode + (0 + (flipyx & 1) + (flipyx & 2)) * 4, flipyx & 1,
                flipyx & 2, drawxpos, drawypos, current_tilemap.transparency,
                current_tilemap.alpha);
            vdp2_drawgfx_rgb555(
                bitmap, cliprect,
                tilecode + (1 - (flipyx & 1) + (flipyx & 2)) * 4, flipyx & 1,
                flipyx & 2, drawxpos + 8, drawypos,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_rgb555(
                bitmap, cliprect,
                tilecode + (2 + (flipyx & 1) - (flipyx & 2)) * 4, flipyx & 1,
                flipyx & 2, drawxpos, drawypos + 8,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_rgb555(
                bitmap, cliprect,
                tilecode + (3 - (flipyx & 1) - (flipyx & 2)) * 4, flipyx & 1,
                flipyx & 2, drawxpos + 8, drawypos + 8,
                current_tilemap.transparency, current_tilemap.alpha);
          } else if (current_tilemap.transparency & STV_TRANSPARENCY_ALPHA) {
            /* alpha */
            vdp2_drawgfx_alpha(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (0 + (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos, drawypos,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_alpha(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (1 - (flipyx & 1) + (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos + 8, drawypos,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_alpha(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (2 + (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos, drawypos + 8,
                current_tilemap.transparency, current_tilemap.alpha);
            vdp2_drawgfx_alpha(
                bitmap, cliprect, m_gfxdecode->gfx(gfx),
                tilecode + (3 - (flipyx & 1) - (flipyx & 2)) * tilecodespacing,
                pal, flipyx & 1, flipyx & 2, drawxpos + 8, drawypos + 8,
                current_tilemap.transparency, current_tilemap.alpha);
          } else {
            /* normal */
            vdp2_drawgfx_transpen(bitmap, cliprect, m_gfxdecode->gfx(gfx),
                                  tilecode + (0 + (flipyx & 1) + (flipyx & 2)) *
                                                 tilecodespacing,
                                  pal, flipyx & 1, flipyx & 2, drawxpos,
                                  drawypos, current_tilemap.transparency);
            vdp2_drawgfx_transpen(bitmap, cliprect, m_gfxdecode->gfx(gfx),
                                  tilecode + (1 - (flipyx & 1) + (flipyx & 2)) *
                                                 tilecodespacing,
                                  pal, flipyx & 1, flipyx & 2, drawxpos + 8,
                                  drawypos, current_tilemap.transparency);
            vdp2_drawgfx_transpen(bitmap, cliprect, m_gfxdecode->gfx(gfx),
                                  tilecode + (2 + (flipyx & 1) - (flipyx & 2)) *
                                                 tilecodespacing,
                                  pal, flipyx & 1, flipyx & 2, drawxpos,
                                  drawypos + 8, current_tilemap.transparency);
            vdp2_drawgfx_transpen(bitmap, cliprect, m_gfxdecode->gfx(gfx),
                                  tilecode + (3 - (flipyx & 1) - (flipyx & 2)) *
                                                 tilecodespacing,
                                  pal, flipyx & 1, flipyx & 2, drawxpos + 8,
                                  drawypos + 8, current_tilemap.transparency);
          }
        } else {
          if (current_tilemap.colour_depth == 4) {
            vdp2_drawgfx_rgb888(
                bitmap, cliprect, tilecode, flipyx & 1, flipyx & 2, drawxpos,
                drawypos, current_tilemap.transparency, current_tilemap.alpha);
          } else if (current_tilemap.colour_depth == 3) {
            vdp2_drawgfx_rgb555(
                bitmap, cliprect, tilecode, flipyx & 1, flipyx & 2, drawxpos,
                drawypos, current_tilemap.transparency, current_tilemap.alpha);
          } else {
            if (current_tilemap.transparency & STV_TRANSPARENCY_ALPHA)
              vdp2_drawgfx_alpha(
                  bitmap, cliprect, m_gfxdecode->gfx(gfx), tilecode, pal,
                  flipyx & 1, flipyx & 2, drawxpos, drawypos,
                  current_tilemap.transparency, current_tilemap.alpha);
            else
              vdp2_drawgfx_transpen(bitmap, cliprect, m_gfxdecode->gfx(gfx),
                                    tilecode, pal, flipyx & 1, flipyx & 2,
                                    drawxpos, drawypos,
                                    current_tilemap.transparency);
          }
        }
        drawxpos = olddrawxpos;
        drawypos = olddrawypos;
      }
      /* DRAWN?! */
    }
  }
  if (current_tilemap.layer_name & 0x80) {
    static const int shifttable[4] = {0, 1, 2, 2};
    int uppermask, uppermaskshift;
    int mapsize;
    uppermaskshift = (1 - current_tilemap.pattern_data_size) |
                     ((1 - current_tilemap.tile_size) << 1);
    uppermask = 0x1ff >> uppermaskshift;

    LOGMASKED(LOG_VDP2, "Layer RBG%d, size %d x %d\n",
              current_tilemap.layer_name & 0x7f, cliprect.right() + 1,
              cliprect.bottom() + 1);
    LOGMASKED(LOG_VDP2, "Tiles: min %08X, max %08X\n", tilecodemin,
              tilecodemax);
    LOGMASKED(LOG_VDP2, "MAP size in dwords %08X\n", mpsize_dwords);
    for (i = 0; i < current_tilemap.map_count; i++) {
      LOGMASKED(LOG_VDP2, "Map register %d: base %08X\n",
                current_tilemap.map_offset[i], base[i]);
    }

    // store map information
    vdp2_layer_data.map_offset_min = 0x7fffffff;
    vdp2_layer_data.map_offset_max = 0x00000000;

    for (i = 0; i < current_tilemap.map_count; i++) {
      uint32_t max_base;

      if (base[i] < vdp2_layer_data.map_offset_min)
        vdp2_layer_data.map_offset_min = base[i];

      // Head On in Sega Memorial Collection 1 cares (uses RBG0 with all map
      // regs equal to 0x20)
      max_base = (base[i] + plsize_bytes / 4);
      if (max_base > vdp2_layer_data.map_offset_max)
        vdp2_layer_data.map_offset_max = max_base;
    }

    mapsize = ((1 & uppermask) >> shifttable[current_tilemap.plane_size]) *
                  plsize_bytes -
              ((0 & uppermask) >> shifttable[current_tilemap.plane_size]) *
                  plsize_bytes;
    mapsize /= 4;

    vdp2_layer_data.map_offset_max += mapsize;

    // Character numbers are 32-byte units, not character lengths. Watch
    // every cell and every byte of the selected color format, including the
    // tail of the highest-numbered character (ST-058 character pattern data).
    unsigned const cell_bytes = 32U << (current_tilemap.colour_depth == 4 ? 3 :
        current_tilemap.colour_depth >= 2 ? 2 : current_tilemap.colour_depth);
    unsigned const character_bytes = cell_bytes * (current_tilemap.tile_size ? 4 : 1);
    unsigned const vram_words = m_vdp2->get_vramsz() ? 0x40000 : 0x20000;
    vdp2_layer_data.tile_offset_min = tilecodemin * 0x20 / 4;
    vdp2_layer_data.tile_offset_max = (tilecodemax * 0x20 + character_bytes) / 4;
    if (vdp2_layer_data.tile_offset_max > vram_words) {
      // A wrapping character has two disjoint ranges. Conservatively watch
      // the whole decode allocation rather than miss its wrapped head or
      // an access through the upper VRAM aperture in the existing renderer.
      vdp2_layer_data.tile_offset_min = 0;
      vdp2_layer_data.tile_offset_max = 0x40000;
    }
  }
}

void saturn_state::vdp2_check_tilemap_with_linescroll(
    bitmap_rgb32 &bitmap, const rectangle &cliprect) {
  // ST-058 pp.131-138: entries are packed H, V, zoom and held for the
  // selected interval. Table position and vertical interpolation are anchored
  // to the screen origin, never to the current partial-update rectangle.
  int const interval = std::max<int>(1, current_tilemap.linescroll_interval);
  int const main_scrollx = current_tilemap.scrollx;
  int const main_scrolly = current_tilemap.scrolly;
  uint16_t const fraction_x = current_tilemap.scrollx_fraction;
  uint16_t const fraction_y = current_tilemap.scrolly_fraction;
  int32_t const main_incx = current_tilemap.incx;
  unsigned const stride = bool(current_tilemap.linescroll_enable) +
      bool(current_tilemap.vertical_linescroll_enable) + bool(current_tilemap.linezoom_enable);
  unsigned const word_mask = m_vdp2->get_vramsz() ? 0x3ffff : 0x1ffff;
  auto const values_at = [&](int first_line) {
    unsigned address = current_tilemap.linescroll_table_address / 4 +
        (first_line / interval) * stride;
    auto const read = [&]() { return m_vdp2_vram[address++ & word_mask]; };
    std::array<int32_t, 5> values{main_scrollx, main_scrolly, main_incx, fraction_x, fraction_y};
    if (current_tilemap.linescroll_enable) {
      uint32_t const horizontal = uint32_t(main_scrollx) * 65536 + fraction_x +
          uint32_t(util::sext(read() & 0x07ffff00, 27));
      values[0] = int32_t(horizontal) >> 16;
      values[3] = horizontal & 0xff00;
    }
    if (current_tilemap.vertical_linescroll_enable) {
      int32_t const vertical = util::sext(read() & 0x07ffff00, 27);
      // Basic renderers add screen Y * incy. Cancel it at the entry's
      // first line, not at the beginning of this rendering pass.
      uint32_t const origin = uint32_t(main_scrolly) * 65536 + fraction_y +
          uint32_t(vertical) - uint32_t(int64_t(first_line) * current_tilemap.incy);
      values[1] = int32_t(origin) >> 16;
      values[4] = origin & 0xff00;
    }
    if (current_tilemap.linezoom_enable)
      values[2] = read() & 0x0007ff00; // unsigned 3.8 increment, not signed
    return values;
  };

  for (int line = cliprect.top(); line <= cliprect.bottom();) {
    int const first_line = (line / interval) * interval;
    auto const values = values_at(first_line);
    int end = first_line + interval;
    // Keep the existing batching benefit when adjacent entries produce the
    // same renderer state, but do not fetch past the final needed entry.
    while (end <= cliprect.bottom() && values_at(end) == values)
      end += interval;
    rectangle clip = cliprect;
    clip.sety(line, std::min(end - 1, cliprect.bottom()));
    current_tilemap.scrollx = values[0];
    current_tilemap.scrolly = values[1];
    current_tilemap.incx = values[2];
    current_tilemap.scrollx_fraction = values[3];
    current_tilemap.scrolly_fraction = values[4];
    if (current_tilemap.bitmap_enable)
      vdp2_draw_basic_bitmap(bitmap, clip);
    else
      vdp2_draw_basic_tilemap(bitmap, clip);
    line = end;
  }
  // Downstream renderers can normalize these fields. Do not leak the last
  // entry into a later partial update or vertical-cell-scroll column.
  current_tilemap.scrollx = main_scrollx;
  current_tilemap.scrolly = main_scrolly;
  current_tilemap.incx = main_incx;
  current_tilemap.scrollx_fraction = fraction_x;
  current_tilemap.scrolly_fraction = fraction_y;
}

void saturn_state::vdp2_draw_line(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  int x, y;
  uint8_t *gfxdata = m_vdp2_legacy.gfx_decode.get();
  uint32_t base_offs, base_mask;
  uint32_t pix;
  uint8_t interlace;

  interlace = (m_vdp2->get_lsmd() == 3) + 1;

  {
    base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;

    for (y = cliprect.top(); y <= cliprect.bottom(); y++) {
      base_offs = (VDP2_LCTA & base_mask) << 1;

      if (VDP2_LCCLMD)
        base_offs += (y / interlace) << 1;

      /* LCTA is masked to 19 bits and doubled, which already lets the base
         reach the last byte of the decode buffer, so the per-line offset can
         run off the end of it; wrap inside the buffer, which is what the
         address lines do on the hardware */
      base_offs &= 0xfffff;

      for (x = cliprect.left(); x <= cliprect.right(); x++) {
        uint16_t pen;

        pen = (gfxdata[base_offs + 0] << 8) | gfxdata[base_offs + 1];
        pix = bitmap.pix(y, x);

        bitmap.pix(y, x) = add_blend_r32(m_palette->pen(pen & 0x7ff), pix);
      }
    }
  }
}

void saturn_state::vdp2_draw_mosaic(bitmap_rgb32 &bitmap,
                                    const rectangle &cliprect, uint8_t is_roz) {
  uint8_t h_size = VDP2_MZSZH + 1;
  uint8_t v_size = VDP2_MZSZV + 1;

  if (is_roz)
    v_size = 1;

  if (h_size == 1 && v_size == 1)
    return; // don't bother

  if (m_vdp2->get_lsmd() == 3)
    v_size <<= 1;

  for (int y = cliprect.top(); y <= cliprect.bottom(); y += v_size) {
    for (int x = cliprect.left(); x <= cliprect.right(); x += h_size) {
      uint32_t pix = bitmap.pix(y, x);

      // The final block may extend past the clip rectangle, including the
      // bitmap edge.  Do not overwrite pixels outside this rendering pass.
      const int block_height = std::min<int>(v_size, cliprect.bottom() - y + 1);
      const int block_width = std::min<int>(h_size, cliprect.right() - x + 1);
      for (int yi = 0; yi < block_height; yi++)
        for (int xi = 0; xi < block_width; xi++)
          bitmap.pix(y + yi, x + xi) = pix;
    }
  }
}

void saturn_state::vdp2_check_tilemap(bitmap_rgb32 &bitmap,
                                      const rectangle &cliprect) {
  /* the idea is here we check the tilemap capabilities / whats enabled and call
    an appropriate tilemap drawing routine, or at the very list throw up a few
    errors if the tilemaps want to do something we don't support yet */
  //  int window_applied = 0;
  rectangle mycliprect = cliprect;

  // Normal-scroll point sampler: a single bounded output pass handles zoom,
  // fractions, line/cell combinations and mosaic before final composition.
  // Rotation source caches continue to use their unscrolled tile/bitmap path.
  if (current_tilemap.layer_name < 4 &&
      (m_vdp2_composition_active || current_tilemap.scrollx_fraction || current_tilemap.scrolly_fraction ||
       current_tilemap.incx != 0x10000 || current_tilemap.incy != 0x10000 ||
       current_tilemap.linescroll_enable || current_tilemap.vertical_linescroll_enable ||
       current_tilemap.linezoom_enable || current_tilemap.vertical_cell_scroll_enable ||
       current_tilemap.mosaic_screen_enabled ||
       (current_tilemap.line_screen_enabled && current_tilemap.colour_calculation_enabled) ||
       (current_tilemap.colour_calculation_enabled && vdp2_special_color_mode()) ||
       vdp2_special_priority_mode())) {
    vdp2_draw_scroll_screen(bitmap, cliprect);
    return;
  }

  //	if (current_tilemap.vertical_cell_scroll_enable)
  //		popmessage("%d %d %d %d", current_tilemap.linescroll_enable,
  //current_tilemap.vertical_linescroll_enable, current_tilemap.linezoom_enable,
  //current_tilemap.vertical_cell_scroll_enable);

  // check for vertical cell scroll enable (sonicjamj)
  // TODO: it is unknown how this works with vertical linescroll enable too (it
  // may not work?)
  // TODO: support a subset only for now, given batmanfr The Riddler stage also
  // sets linezoom_enable Would make the background rounded to the Dome, but
  // o(n*m) nested loop causes a performance nosedive
  // https://mametesters.org/view.php?id=7203
  // ST-058 p.134: vertical cell scroll is independent of horizontal line
  // scroll. Keep the existing exclusions for the unqualified combinations.
  if (current_tilemap.vertical_cell_scroll_enable &&
      !current_tilemap.vertical_linescroll_enable &&
      !current_tilemap.linezoom_enable) {
    if (cliprect.empty())
      return;

    uint32_t vcsc_address;
    uint32_t base_mask;
    int base_offset, base_multiplier;
    int16_t base_scrollx, base_scrolly;
    // uint32_t base_incx, base_incy;
    // Keep column/table addressing anchored at screen X=0, but do not
    // render columns wholly to the left of this partial update.
    int cur_char = cliprect.left() & ~7;

    base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;
    vcsc_address = (((VDP2_VCSTAU << 16) | VDP2_VCSTAL) & base_mask) * 2;
    vcsc_address >>= 2;

    base_offset = 0;
    base_multiplier = 1;
    // offset for both enabled
    if (VDP2_N0VCSC && VDP2_N1VCSC) {
      // NBG1
      if (current_tilemap.layer_name & 1)
        base_offset = 1;

      base_multiplier = 2;
    }

    base_scrollx = current_tilemap.scrollx;
    base_scrolly = current_tilemap.scrolly;
    // base_incx = current_tilemap.incx;
    // base_incy = current_tilemap.incy;

    while (cur_char <= cliprect.right()) {
      mycliprect.setx(std::max(cur_char, cliprect.left()),
                      std::min(cur_char + 7, cliprect.right()));

      uint32_t cur_address;
      int16_t char_scroll;

      cur_address = vcsc_address;
      cur_address += ((cur_char >> 3) * base_multiplier) + base_offset;

      /* vcsc_address is (VCSTA & base_mask) * 2 >> 2, so it can already be
         the last word of VRAM before the per-character offset is added;
         wrap inside VRAM as the other table reads do */
      char_scroll = m_vdp2_vram[cur_address & (base_mask >> 1)] >> 16;
      char_scroll &= 0x07ff;
      if (char_scroll & 0x0400)
        char_scroll |= 0xf800;
      current_tilemap.scrollx = base_scrollx;
      current_tilemap.scrolly = base_scrolly + (char_scroll);
      // current_tilemap.incx = base_incx;
      // current_tilemap.incy = base_incy;

      if (current_tilemap.linescroll_enable)
        vdp2_check_tilemap_with_linescroll(bitmap, mycliprect);
      else if (current_tilemap.bitmap_enable)
        vdp2_draw_basic_bitmap(bitmap, mycliprect);
      else
        vdp2_draw_basic_tilemap(bitmap, mycliprect);

      // TODO: + 16 for tilemap and char size = 16?
      cur_char += 8;
    }

    current_tilemap.scrollx = base_scrollx;
    current_tilemap.scrolly = base_scrolly;
    return;
  } else if (current_tilemap.linescroll_enable ||
             current_tilemap.vertical_linescroll_enable ||
             current_tilemap.linezoom_enable) {
    vdp2_check_tilemap_with_linescroll(bitmap, cliprect);

    return;
  }

  if (current_tilemap.bitmap_enable) // this layer is a bitmap
  {
    vdp2_draw_basic_bitmap(bitmap, mycliprect);
  } else {
    // vdp2_apply_window_on_layer(mycliprect);
    vdp2_draw_basic_tilemap(bitmap, mycliprect);
  }

  /* post-processing functions */
  // (TODO: needs layer bitmaps to be individual planes to work correctly)
  if (current_tilemap.line_screen_enabled && TEST_FUNCTIONS)
    vdp2_draw_line(bitmap, cliprect);

  if (current_tilemap.mosaic_screen_enabled && TEST_FUNCTIONS)
    vdp2_draw_mosaic(bitmap, cliprect, current_tilemap.layer_name & 0x80);

  {
    if (current_tilemap.colour_depth == 2 && !current_tilemap.bitmap_enable)
      popmessage("2048 color mode used on a non-bitmap plane");

    //      if(VDP2_SCXDN0 || VDP2_SCXDN1 || VDP2_SCYDN0 || VDP2_SCYDN1)
    //          popmessage("Fractional part scrolling write");

    /* capgen2 - Choh Makaimura (obviously) */
    if (VDP2_MZCTL & 0x1f && POPMESSAGE_DEBUG)
      popmessage("Mosaic control enabled = %04x\n", VDP2_MZCTL);

    /* revil/biohaz bit 1 */
    /* airsadve 0x3e */
    /* bakhunt */
    if (VDP2_LNCLEN & ~2 && POPMESSAGE_DEBUG)
      popmessage("Line Colour screen enabled %04x %08x", VDP2_LNCLEN,
                 VDP2_LCTAU << 16 | VDP2_LCTAL);

    /* revil/biohaz 0x400 = extended color calculation enabled */
    /* aww 0x200 = color calculation ratio mode */
    /* whizz/whizzj = 0x8100 */
    /* darksavu = 0x9051 on save select screen (the one with a Saturn in the
     * background) */
    if (VDP2_CCCR & 0x6000)
      popmessage("Gradation enabled %04x", VDP2_CCCR);

    /* Advanced VG, Shining Force III */
    if (VDP2_SFCCMD && POPMESSAGE_DEBUG)
      popmessage("Special Color Calculation enable %04x", VDP2_SFCCMD);

    /* cleopatr Transparent Shadow */
    /* prettyx Back & Transparent Shadow*/
    // if(VDP2_SDCTL & 0x0120)
    //   popmessage("%s shadow select bit enabled",VDP2_SDCTL & 0x100 ?
    //   "Transparent" : "Back");

    /* lengris3 bit 3 normal, bit 1 during battle field */
    /* mslug bit 0 during gameplay */
    /* bugu Sega Away Logo onward 0x470 */
    /* cncu 0x0004 0xc000, azelpanztai 0x0004 0x0000 (FMV) */
    if (VDP2_SFSEL & ~0x47f)
      popmessage("Special Function Code Select enable %04x %04x", VDP2_SFSEL,
                 VDP2_SFCODE);

    /* albodys 0x0001 */
    /* asuka120 0x0101 */
    /* slamnjamu 0x0003 */
    if (VDP2_ZMCTL & 0x0200)
      popmessage("Reduction enable %04x", VDP2_ZMCTL);

    /* burningru based FMVs, jltsuk backgrounds */
    if (VDP2_SCRCTL & 0x0101 && POPMESSAGE_DEBUG)
      popmessage("Vertical cell scroll enable %04x", VDP2_SCRCTL);

    /* magdrop3 0x200 -> color calculation window */
    /* ideyusmj 0x0303 */
    /* decathlt 0x088 */
    /* sexyparo 0x2300 */
    //      if(VDP2_WCTLD & 0x2000)
    //          popmessage("Special window enabled %04x",VDP2_WCTLD);

    /* shinfrc3u, aburner2 (doesn't make a proper use tho?) */
    /* layersec */
    // if(VDP2_W0LWE || VDP2_W1LWE)
    //   popmessage("Line Window %s %08x enabled",VDP2_W0LWE ? "0" :
    //   "1",VDP2_W0LWTA);

    /* draculax bits 2-4 */
    /* acstrike bit 5 */
    /* capgen2 - Choh Makaimura 0x0055 */
    /* srallycu 0x0155 */
    /* findlove 0x4400 */
    /* dbzsbuto 0x3800 - 0x2c00 */
    /* leynos2 0x0200*/
    /* bugu 0x8800 */
    /* wonder3 0x0018 */
    if (VDP2_SFPRMD & ~0xff7f)
      popmessage("Special Priority Mode enabled %04x", VDP2_SFPRMD);
  }
}

/* The rotation coefficient deltas are sign-extended from bit 25, so they reach
   +/- 2^25, and the counters they are scaled by run into the hundreds, which
   puts the product well past 32 bits.  Plain int32_t multiplication overflows
   there, and that is undefined behaviour; multiply in 64 bits and truncate
   instead.  The truncated result is the same value two's complement wrapping
   produces, so nothing observable changes, and it matches the 32-bit
   accumulator the hardware uses - vdp2_copy_roz_bitmap() already multiplies
   its rotation matrix terms this way, through mul_fixed32(). */
// MiSTer RotCoord_t/MultRC and the existing Q16 compositor use wrapping
// 32-bit coordinates. Make additions/subtractions explicit rather than relying
// on signed C++ overflow when legal parameter fields approach their limits.
static inline int32_t vdp2_wrap_sum(int32_t a, int32_t b, int32_t c = 0, int32_t d = 0, int32_t e = 0) {
  return uint32_t(a) + uint32_t(b) + uint32_t(c) + uint32_t(d) + uint32_t(e);
}

static inline int32_t vdp2_wrap_sub(int32_t a, int32_t b) {
  return uint32_t(a) - uint32_t(b);
}

// ST-058 pp.150/163: per-line VRAM coefficients need no dedicated bank;
// per-dot coefficients require CRAM or an effective coefficient-data bank.
static constexpr bool vdp2_per_dot_coefficients(uint16_t ramctl) {
  return (ramctl & 0x8000) || (ramctl & 3) == 1 || ((ramctl >> 4) & 3) == 1 ||
      ((ramctl & 0x100) && ((ramctl >> 2) & 3) == 1) ||
      ((ramctl & 0x200) && ((ramctl >> 6) & 3) == 1);
}

static inline uint32_t coef_delta(int32_t delta, int32_t count) {
  return uint32_t(s64(delta) * count);
}

// ST-058 pp.237-238: fixed-ratio calculation of the second input. Each
// component is truncated before addition (also MiSTer ColorCalcExtRatio).
// The mode-0 2:1:0 table entry contradicts figure 12.3's fourth input;
// use 2:1:1 as in that figure and both pinned Ymir/MiSTer implementations.
static uint32_t vdp2_extended_color(uint32_t second, uint32_t third, uint32_t fourth,
                                  bool second_cc, bool third_cc, bool third_palette,
                                  bool fourth_palette, bool line, unsigned cram_mode) {
  if (!second_cc || (cram_mode && third_palette))
    return second;
  bool const four = line && third_cc && (!cram_mode || !fourth_palette);
  uint32_t result = 0;
  for (unsigned shift : {0U, 8U, 16U}) {
    unsigned const a = (second >> shift) & 255;
    unsigned const b = (third >> shift) & 255;
    unsigned const c = (fourth >> shift) & 255;
    result |= ((a >> 1) + (four ? (b >> 2) + (c >> 2) : (b >> 1))) << shift;
  }
  return result;
}

// ST-058 pp.235/241-244: calculate the top against the raw second image,
// not against a lower layer's already-calculated displayed result. These are
// derived partial-render buffers; no image history survives screen_update.
void saturn_state::vdp2_begin_composition(bitmap_rgb32 &bitmap, const rectangle &cliprect) {
  m_vdp2_composition_active = false;
  // With no possible top-image calculation, keep ordinary cached/fast paths.
  m_vdp2_gradation_capture = false;
  static constexpr unsigned layers[] = {6, 4, 0, 7, 1, 2, 3, 7};
  m_vdp2_gradation_layer = layers[(VDP2_CCCR >> 12) & 7];
  m_vdp2_gradation_active = (VDP2_CCCR & 0x8000) && !VDP2_CRMD && !(m_vdp2->get_hreso() & 6) && m_vdp2_gradation_layer != 7;
  m_vdp2_extended_active = (VDP2_CCCR & 0x8400) == 0x400 && !(m_vdp2->get_hreso() & 6);
  if (!(VDP2_CCCR & 0x5f) && !(VDP2_SDCTL & 0x3f))
    return;
  if (m_vdp2_raw_top.width() != bitmap.width() || m_vdp2_raw_top.height() != bitmap.height()) {
    m_vdp2_raw_top.allocate(bitmap.width(), bitmap.height());
    m_vdp2_raw_alpha.allocate(bitmap.width(), bitmap.height());
    m_vdp2_raw_meta.allocate(bitmap.width(), bitmap.height());
  }
  if (m_vdp2_extended_active && (m_vdp2_raw_under.width() != bitmap.width() || m_vdp2_raw_under.height() != bitmap.height())) {
    m_vdp2_raw_under.allocate(bitmap.width(), bitmap.height());
    m_vdp2_under_meta.allocate(bitmap.width(), bitmap.height());
  }
  if (m_vdp2_gradation_active && (m_vdp2_gradation_source.width() != bitmap.width() || m_vdp2_gradation_source.height() != bitmap.height()))
    m_vdp2_gradation_source.allocate(bitmap.width(), bitmap.height());
  unsigned const alpha = vdp2_cc_blend_level((VDP2_CCRLB >> 8) & 31);
  for (int y = cliprect.top(); y <= cliprect.bottom(); ++y)
    for (int x = cliprect.left(); x <= cliprect.right(); ++x) {
      m_vdp2_raw_top.pix(y, x) = bitmap.pix(y, x);
      m_vdp2_raw_alpha.pix(y, x) = alpha;
      m_vdp2_raw_meta.pix(y, x) = 5; // back: direct RGB, no calculation enable
      if (m_vdp2_extended_active) {
        m_vdp2_raw_under.pix(y, x) = bitmap.pix(y, x);
        m_vdp2_under_meta.pix(y, x) = 5;
      }
    }
  // Back offsets affect the visible back only, never a later second input.
  if (VDP2_CLOFEN & 0x20) {
    for (int y = cliprect.top(); y <= cliprect.bottom(); ++y) {
      rgb_t color = bitmap.pix(y, cliprect.left());
      vdp2_compute_color_offset_UINT32(&color, (VDP2_CLOFSL & 0x20) ? 2 : 0);
      for (int x = cliprect.left(); x <= cliprect.right(); ++x)
        bitmap.pix(y, x) = color;
    }
  }
  m_vdp2_composition_active = true;
}

// Gradation needs the designated screen's two previous horizontal dots, not
// the displayed neighbors. Capture that one raw screen once, with a two-dot
// left halo for partial clips. Never rebuild every layer or composite history.
void saturn_state::vdp2_capture_gradation(const rectangle &cliprect) {
  if (!m_vdp2_composition_active || !m_vdp2_gradation_active)
    return;
  rectangle area = cliprect;
  area.min_x = std::max(0, area.min_x - 2);
  m_vdp2_gradation_source.fill(0, area);
  m_vdp2_gradation_capture = true;
  m_vdp2_priority_pass = -1;
  switch (m_vdp2_gradation_layer) {
  case 0: vdp2_draw_NBG0(m_vdp2_gradation_source, area); break;
  case 1: vdp2_draw_NBG1(m_vdp2_gradation_source, area); break;
  case 2: vdp2_draw_NBG2(m_vdp2_gradation_source, area); break;
  case 3: vdp2_draw_NBG3(m_vdp2_gradation_source, area); break;
  case 4: vdp2_draw_RBG0(m_vdp2_gradation_source, area); break;
  case 6:
    vdp1_sprite_priorities_usage_valid = 0;
    memset(vdp1_sprite_priorities_used, 0, sizeof(vdp1_sprite_priorities_used));
    memset(vdp1_sprite_priorities_in_fb_line, 0, sizeof(vdp1_sprite_priorities_in_fb_line));
    for (unsigned priority = 1; priority < 8; ++priority)
      draw_sprites(m_vdp2_gradation_source, area, priority);
    break;
  }
  m_vdp2_gradation_capture = false;
}

static uint32_t vdp2_gradation_color(uint32_t current, uint32_t left, uint32_t left2, int x) {
  // ST-058 p.238: 2:1:1, with truncation before adding. Pixels outside
  // the left display edge are unspecified; retain Ymir's 0/1 edge policy.
  if (!x)
    return current;
  uint32_t result = 0;
  for (unsigned shift : {0U, 8U, 16U}) {
    unsigned const a = (current >> shift) & 255, b = (left >> shift) & 255, c = (left2 >> shift) & 255;
    result |= (x == 1 ? (a + b) / 2 : a / 2 + b / 4 + c / 4) << shift;
  }
  return result;
}

bool saturn_state::vdp2_calculation_window(int x, int y) {
  // ST-058 p.190: the effective area suppresses calculation, not coverage.
  unsigned const control = VDP2_WCTLD >> 8;
  bool const logic_or = control & 0x80;
  bool keep = !logic_or;
  if (control & 0x0a)
    vdp2_roz_window_prepare(y);
  for (unsigned window = 0; window < 3; ++window) {
    if (!(control & (2U << (2 * window))))
      continue;
    bool const inside = window == 2 ? vdp2_sprite_window(x, y) :
        x >= m_roz_win_s_x[window] && x <= m_roz_win_e_x[window] &&
        y >= m_roz_win_s_y[window] && y <= m_roz_win_e_y[window];
    bool const value = inside == bool(control & (1U << (2 * window)));
    keep = logic_or ? keep || value : keep && value;
  }
  return keep;
}

void saturn_state::vdp2_compose_pixel(bitmap_rgb32 &bitmap, int x, int y, rgb_t color,
                                      bool calculate, unsigned alpha, bool insert_line, rgb_t line_color, unsigned source) {
  uint32_t &dest = bitmap.pix(y, x);
  unsigned const layer = source & 7;
  if (m_vdp2_gradation_capture) {
    dest = color;
    return;
  }
  bool const source_calculate = calculate;
  bool const gradation = m_vdp2_composition_active && m_vdp2_gradation_active;
  if (gradation)
    insert_line = false; // BOKEN excludes line insertion as well as EXCCEN
  if (calculate && m_vdp2_composition_active) {
    // ST-058 table 12.1: high/exclusive modes cannot calculate with a
    // palette second input in CRAM modes 1/2 (line insertion is palette).
    if ((m_vdp2->get_hreso() & 6) && VDP2_CRMD && (insert_line || (m_vdp2_raw_meta.pix(y, x) & 8)))
      calculate = false;
    else if (!vdp2_calculation_window(x, y))
      calculate = false;
  }
  if (!calculate) {
    dest = color;
  } else {
    rgb_t second = insert_line ? line_color : rgb_t(m_vdp2_composition_active
        ? m_vdp2_raw_top.pix(y, x) : dest);
    if (m_vdp2_composition_active && m_vdp2_extended_active) {
      unsigned const meta = m_vdp2_raw_meta.pix(y, x), under = m_vdp2_under_meta.pix(y, x);
      second = vdp2_extended_color(second,
          insert_line ? m_vdp2_raw_top.pix(y, x) : m_vdp2_raw_under.pix(y, x),
          m_vdp2_raw_under.pix(y, x),
          insert_line ? bool(VDP2_CCCR & 0x20) : bool(meta & 16),
          bool(meta & 16), (insert_line ? meta : under) & 8, under & 8, insert_line, VDP2_CRMD);
    }
    bool const use_gradation = gradation && (layer == m_vdp2_gradation_layer ||
        (m_vdp2_raw_meta.pix(y, x) & 7) == m_vdp2_gradation_layer);
    if (use_gradation)
      second = vdp2_gradation_color(m_vdp2_gradation_source.pix(y, x),
          m_vdp2_gradation_source.pix(y, std::max(0, x - 1)),
          m_vdp2_gradation_source.pix(y, std::max(0, x - 2)), x);
    unsigned const selected_alpha = use_gradation && layer == m_vdp2_gradation_layer ? alpha : !(VDP2_CCCR & 0x200) ? alpha : insert_line
        ? vdp2_cc_blend_level(VDP2_CCRLB & 31) : m_vdp2_composition_active
        ? m_vdp2_raw_alpha.pix(y, x) : alpha;
    dest = VDP2_CCMD ? add_blend_r32(second, color) : alpha_blend_r32(second, color, selected_alpha);
  }
  if (m_vdp2_composition_active) {
    // Store the source and its own ratio even if its calculation is disabled.
    // A line-color insertion belongs only to the current top image, not to
    // this layer when a later higher-priority source makes it the second.
    if (m_vdp2_extended_active) {
      m_vdp2_raw_under.pix(y, x) = m_vdp2_raw_top.pix(y, x);
      m_vdp2_under_meta.pix(y, x) = m_vdp2_raw_meta.pix(y, x);
    }
    // ST-058 pp.250-252: only the top screen's offset applies, after calculation.
    if (VDP2_CLOFEN & (1U << layer)) {
      rgb_t adjusted = dest;
      vdp2_compute_color_offset_UINT32(&adjusted, (VDP2_CLOFSL & (1U << layer)) ? 2 : 0);
      dest = adjusted;
    }
    bool const source_cc = layer < 5 ? bool(VDP2_CCCR & (1U << layer)) : layer == 6 && source_calculate;
    m_vdp2_raw_meta.pix(y, x) = source | (source_cc ? 16 : 0);
    m_vdp2_raw_top.pix(y, x) = color;
    m_vdp2_raw_alpha.pix(y, x) = alpha;
  }
}

void saturn_state::vdp2_shadow_pixel(bitmap_rgb32 &bitmap, int x, int y, bool layer_select) {
  // ST-058 pp.256-260: normal/transparent shadows use the underlying
  // screen's SDCTL bit; a sprite shadow always darkens its own sprite.
  if (m_vdp2_gradation_capture)
    return;
  unsigned const mask = m_vdp2_composition_active ? 1U << (m_vdp2_raw_meta.pix(y, x) & 7) : 0x3f;
  if (layer_select && !(VDP2_SDCTL & mask & 0x3f))
    return;
  rgb_t p = bitmap.pix(y, x);
  bitmap.pix(y, x) = rgb_t(p.r() >> 1, p.g() >> 1, p.b() >> 1);
  // Shadows are a final output operation, not a color-calculation input.
  // If a higher background wins later, it must see the unshadowed raw source.
}

unsigned saturn_state::vdp2_special_color_mode() const {
  unsigned const layer = current_tilemap.layer_name == 0x81 ? 0 :
      current_tilemap.layer_name == 0x80 ? 4 : current_tilemap.layer_name;
  return layer < 5 ? (VDP2_SFCCMD >> (layer * 2)) & 3 : 0;
}

unsigned saturn_state::vdp2_special_priority_mode() const {
  unsigned const layer = current_tilemap.layer_name == 0x81 ? 0 :
      current_tilemap.layer_name == 0x80 ? 4 : current_tilemap.layer_name;
  unsigned const mode = layer < 5 ? (VDP2_SFPRMD >> (layer * 2)) & 3 : 0;
  return mode == 1 || mode == 2 ? mode : 0; // mode 3 is prohibited
}

// ST-058 pp.228-229: replace only the priority LSB, then suppress priority 0.
// The raw-dot code match is carried from the color decoder in metadata bit 1.
rgb_t saturn_state::vdp2_special_priority_pixel(rgb_t pixel, bool attribute) {
  unsigned const mode = vdp2_special_priority_mode();
  if (!mode || !pixel.a())
    return pixel;
  unsigned const layer = current_tilemap.layer_name == 0x81 ? 0 :
      current_tilemap.layer_name == 0x80 ? 4 : current_tilemap.layer_name;
  unsigned const priorities[] = {VDP2_N0PRIN, VDP2_N1PRIN, VDP2_N2PRIN, VDP2_N3PRIN, VDP2_R0PRIN};
  bool const low = attribute && (mode == 1 ||
      (current_tilemap.colour_depth < 3 && (pixel.a() & 2)));
  unsigned const priority = (priorities[layer] & 6) | unsigned(low);
  if (!priority)
    return rgb_t::transparent();
  return rgb_t((uint32_t(pixel) & ~0x1c000000U) | (priority << 26));
}

static constexpr bool vdp2_priority_pass_matches(unsigned base, unsigned mode, unsigned pass) {
  // At most two passes per special-priority layer; retain the ordinary fast
  // path and established same-priority layer/sprite order for all other layers.
  return mode == 1 || mode == 2 ? (base & 6) == (pass & 6) : base == pass;
}

// Private decoded-dot metadata: zero alpha is uncovered; FE/FF are covered
// with calculation disabled/enabled when priority is ordinary. Special-priority
// dots use bit 7 for coverage, bit 0 for calculation, bit 1 for code match and
// bits 2-4 for priority. Restore opaque alpha at final composition.
// Do not store already-calculated colors in rotation caches (ST-058 p.245).
rgb_t saturn_state::vdp2_special_color_pixel(rgb_t color, unsigned raw, unsigned pen) {
  unsigned const mode = vdp2_special_color_mode();
  bool calculate = true;
  if (mode == 2) {
    unsigned const layer = current_tilemap.layer_name == 0x81 ? 0 :
        current_tilemap.layer_name == 0x80 ? 4 : current_tilemap.layer_name;
    unsigned const codes = VDP2_SFCODE >> (((VDP2_SFSEL >> layer) & 1) * 8);
    // RGB mode 2 is prohibited; preserve Ymir's code-7 fallback, not a
    // hardware guarantee for an invalid register combination.
    unsigned const code = current_tilemap.colour_depth < 3 ? (raw >> 1) & 7 : 7;
    calculate = (codes >> code) & 1;
  } else if (mode == 3 && current_tilemap.colour_depth < 3) {
    // Read the physical CRAM MSB, which the RGB palette cache discards.
    if (VDP2_CRMD < 2) {
      pen &= VDP2_CRMD == 0 ? 0x3ff : 0x7ff;
      calculate = (m_vdp2_cram[pen >> 1] >> ((pen & 1) ? 15 : 31)) & 1;
    } else {
      calculate = (vdp2_cram_r(pen & 0x3ff) >> 31) & 1;
    }
  }
  unsigned metadata = calculate ? 0xff : 0xfe;
  if (vdp2_special_priority_mode()) {
    unsigned const layer = current_tilemap.layer_name == 0x81 ? 0 :
        current_tilemap.layer_name == 0x80 ? 4 : current_tilemap.layer_name;
    unsigned const codes = VDP2_SFCODE >> (((VDP2_SFSEL >> layer) & 1) * 8);
    bool const match = current_tilemap.colour_depth < 3 && ((codes >> ((raw >> 1) & 7)) & 1);
    metadata = 0x80 | unsigned(calculate) | (unsigned(match) << 1);
  }
  return rgb_t((uint32_t(color) & 0xffffff) | (metadata << 24));
}

// ST-058 pp.115-116: OVPNR always uses the one-word pattern-name format,
// regardless of the ordinary map's pattern_data_size. Decode an unblended dot;
// the rotation compositor applies windows, color offset and calculation once.
rgb_t saturn_state::vdp2_dot_pixel(uint32_t address, int x, unsigned palette) {
  unsigned const depth = current_tilemap.colour_depth;
  unsigned const mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  auto const read = [this, mask](unsigned a) { return m_vdp2_legacy.gfx_decode[a & mask]; };
  uint32_t raw = read(address);
  if (depth == 0)
    raw = (raw >> ((~x & 1) * 4)) & 15;
  else if (depth >= 2) {
    raw = (raw << 8) | read(address + 1);
    if (depth == 4)
      raw = (raw << 16) | (read(address + 2) << 8) | read(address + 3);
    else if (depth == 2)
      raw &= 0x7ff;
  }
  bool const covered = depth < 3 ? raw != 0 : (raw & (depth == 3 ? 0x8000 : 0x80000000)) != 0;
  if (!covered && !(current_tilemap.transparency & STV_TRANSPARENCY_NONE))
    return rgb_t::transparent();
  if (depth == 3)
    return vdp2_special_color_pixel(rgb_t(pal5bit(raw), pal5bit(raw >> 5), pal5bit(raw >> 10)), raw, 0);
  if (depth == 4)
    return vdp2_special_color_pixel(rgb_t(raw & 255, (raw >> 8) & 255, (raw >> 16) & 255), raw, 0);
  if (depth == 1) palette &= 0x700;
  if (depth == 2) palette = 0;
  unsigned const pen = ((palette | raw) + (current_tilemap.colour_ram_address_offset << 8)) & 0x7ff;
  return vdp2_special_color_pixel(m_palette->pen(pen), raw, pen);
}

rgb_t saturn_state::vdp2_pattern_pixel(uint32_t data, bool one_word, int x, int y) {
  unsigned code;
  if (!one_word) {
    code = data & 0x7fff;
    if (data & 0x40000000) x = ~x;
    if (data & 0x80000000) y = ~y;
  } else if (current_tilemap.character_number_supplement) {
    code = current_tilemap.tile_size
        ? ((data & 0x0fff) << 2) | (current_tilemap.supplementary_character_bits & 3) |
              ((current_tilemap.supplementary_character_bits & 0x10) << 10)
        : (data & 0x0fff) | ((current_tilemap.supplementary_character_bits & 0x1c) << 10);
  } else {
    code = current_tilemap.tile_size
        ? ((data & 0x03ff) << 2) | (current_tilemap.supplementary_character_bits & 3) |
              ((current_tilemap.supplementary_character_bits & 0x1c) << 10)
        : (data & 0x03ff) | (current_tilemap.supplementary_character_bits << 10);
    if (data & 0x0400) x = ~x;
    if (data & 0x0800) y = ~y;
  }
  unsigned const depth = current_tilemap.colour_depth;
  if (depth > 4)
    return rgb_t::transparent(); // prohibited color format
  unsigned const bytes_per_cell = 32U << (depth == 4 ? 3 : depth >= 2 ? 2 : depth);
  unsigned const cell = current_tilemap.tile_size ? ((x & 8) >> 3) + ((y & 8) >> 2) : 0;
  unsigned const dot = (y & 7) * 8 + (x & 7);
  unsigned const address = code * 32 + cell * bytes_per_cell + dot * bytes_per_cell / 64;
  unsigned const palette = !one_word ? ((data >> 16) & 0x7f) << 4 : depth == 0
      ? ((data >> 12) | (current_tilemap.supplementary_palette_bits << 4)) << 4
      : (data & 0x7000) >> 4;
  rgb_t pixel = vdp2_dot_pixel(address, x, palette);
  unsigned const mode = vdp2_special_color_mode();
  bool const attribute = one_word ? bool(current_tilemap.special_colour_control_register) : bool(data & 0x10000000);
  if (pixel.a() && (mode == 1 || mode == 2) && !attribute)
    pixel = rgb_t(uint32_t(pixel) & ~0x01000000U);
  bool const priority_attribute = one_word ? bool(current_tilemap.special_priority_register) : bool(data & 0x20000000);
  return vdp2_special_priority_pixel(pixel, priority_attribute);
}

rgb_t saturn_state::vdp2_screen_over_pattern_pixel(uint16_t data, int x, int y) {
  return vdp2_pattern_pixel(data, true, x, y);
}

// ST-058 pp.164/172: coefficient bits replace the low seven palette-address
// bits. Line color has no CRAO addition and is the inserted second image.
rgb_t saturn_state::vdp2_line_color(int y, bool use_coefficient, uint8_t coefficient_color) {
  unsigned const mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  unsigned const index = VDP2_LCCLMD
      ? (m_vdp2->get_lsmd() == 2 ? y / 2 : y)
      : (m_vdp2->get_lsmd() == 3 ? y & 1 : 0);
  unsigned const address = (VDP2_LCTA * 2 + index * 2) & mask;
  uint8_t const *const data = m_vdp2_legacy.gfx_decode.get();
  unsigned color = ((data[address] << 8) | data[(address + 1) & mask]) & 0x7ff;
  if (use_coefficient)
    color = (color & 0x780) | (coefficient_color & 0x7f);
  return m_palette->pen(color);
}

// Point sampling avoids inverse-zoom tile placement rounding and the nested
// column-by-line redraw used by the legacy paths. All coordinate fractions are
// retained until the final source dot is selected (ST-058 sections 5.1-5.3).
rgb_t saturn_state::vdp2_scroll_pixel(int32_t x, int32_t y) {
  unsigned const depth = current_tilemap.colour_depth;
  if (depth > 4)
    return rgb_t::transparent();
  if (current_tilemap.bitmap_enable) {
    unsigned const width = (current_tilemap.bitmap_size & 2) ? 1024 : 512;
    unsigned const height = (current_tilemap.bitmap_size & 1) ? 512 : 256;
    unsigned const dot = (unsigned(y) & (height - 1)) * width + (unsigned(x) & (width - 1));
    unsigned const bytes = depth == 4 ? 4 : depth >= 2 ? 2 : 1;
    unsigned const address = current_tilemap.bitmap_map * 0x20000 +
        (depth == 0 ? dot / 2 : dot * bytes);
    rgb_t pixel = vdp2_dot_pixel(address, x, current_tilemap.bitmap_palette_number << 8);
    unsigned const mode = vdp2_special_color_mode();
    unsigned const bitmap_flags = current_tilemap.layer_name == 0x80 ? VDP2_BMPNB :
        VDP2_BMPNA >> (current_tilemap.layer_name == 1 ? 8 : 0);
    if (pixel.a() && (mode == 1 || mode == 2) && !(bitmap_flags & 0x10))
      pixel = rgb_t(uint32_t(pixel) & ~0x01000000U);
    return vdp2_special_priority_pixel(pixel, bool(bitmap_flags & 0x20));
  }

  unsigned const cell_size = current_tilemap.tile_size ? 16 : 8;
  unsigned const page_columns = 512 / cell_size;
  unsigned const name_bytes = current_tilemap.pattern_data_size ? 2 : 4;
  unsigned const page_bytes = page_columns * page_columns * name_bytes;
  unsigned const pages_x = (current_tilemap.plane_size & 1) ? 2 : 1;
  unsigned const pages_y = (current_tilemap.plane_size & 2) ? 2 : 1;
  unsigned const plane_x = pages_x * 512, plane_y = pages_y * 512;
  unsigned const map_columns = current_tilemap.map_count == 16 ? 4 : 2;
  unsigned const sx = unsigned(x) & (plane_x * map_columns - 1);
  unsigned const sy = unsigned(y) & (plane_y * map_columns - 1);
  unsigned const map = sx / plane_x + (sy / plane_y) * map_columns;
  unsigned const page = ((sx & (plane_x - 1)) / 512) +
      ((sy & (plane_y - 1)) / 512) * pages_x;
  unsigned const upper_mask = 0x1ff >> ((1 - current_tilemap.pattern_data_size) |
      ((1 - current_tilemap.tile_size) << 1));
  unsigned const base_page = (current_tilemap.map_offset[map] & upper_mask) & ~(pages_x * pages_y - 1);
  unsigned const name_index = ((sy & 511) / cell_size) * page_columns + ((sx & 511) / cell_size);
  unsigned const address = (base_page + page) * page_bytes + name_index * name_bytes;
  unsigned const word_mask = m_vdp2->get_vramsz() ? 0x3ffff : 0x1ffff;
  uint32_t data = m_vdp2_vram[(address / 4) & word_mask];
  if (name_bytes == 2)
    data = (address & 2) ? data & 0xffff : data >> 16;
  return vdp2_pattern_pixel(data, name_bytes == 2, x, y);
}

void saturn_state::vdp2_draw_scroll_screen(bitmap_rgb32 &bitmap, const rectangle &cliprect) {
  if (!current_tilemap.enabled || cliprect.empty())
    return;
  auto const &t = current_tilemap;
  bool const special_priority = vdp2_special_priority_mode() != 0;
  unsigned const word_mask = m_vdp2->get_vramsz() ? 0x3ffff : 0x1ffff;
  int const interval = std::max<int>(1, t.linescroll_interval);
  unsigned const stride = bool(t.linescroll_enable) + bool(t.vertical_linescroll_enable) + bool(t.linezoom_enable);
  bool const mosaic = t.mosaic_screen_enabled;
  unsigned const mosaic_x = mosaic ? VDP2_MZSZH + 1 : 1;
  unsigned const mosaic_y = mosaic ? (VDP2_MZSZV + 1) * (m_vdp2->get_lsmd() == 3 ? 2 : 1) : 1;
  bool const cell_scroll = t.vertical_cell_scroll_enable && !mosaic;
  unsigned const cell_stride = VDP2_N0VCSC && VDP2_N1VCSC ? 2 : 1;
  unsigned const cell_base = ((((VDP2_VCSTAU << 16) | VDP2_VCSTAL) * 2) / 4) +
      (cell_stride == 2 ? (t.layer_name & 1) : 0);
  bool have_pixel = false;
  int32_t last_x = 0, last_y = 0;
  rgb_t pixel;
  for (int y = cliprect.top(); y <= cliprect.bottom(); ++y) {
    int const sample_y = y - y % mosaic_y;
    int const first_line = sample_y / interval * interval;
    unsigned table = t.linescroll_table_address / 4 + (first_line / interval) * stride;
    auto const read = [&]() { return m_vdp2_vram[table++ & word_mask]; };
    int64_t start_x = int64_t(t.scrollx) * 65536 + t.scrollx_fraction;
    int64_t start_y = int64_t(t.scrolly) * 65536 + t.scrolly_fraction;
    uint32_t incx = t.incx;
    if (t.linescroll_enable)
      start_x += util::sext(read() & 0x07ffff00, 27);
    if (t.vertical_linescroll_enable)
      start_y += util::sext(read() & 0x07ffff00, 27) + int64_t(sample_y - first_line) * t.incy;
    else
      start_y += int64_t(sample_y) * t.incy;
    if (t.linezoom_enable)
      incx = read() & 0x0007ff00;
    // The first entry belongs to the first source cell encountered at screen
    // X=0. Count source-cell boundaries, not fixed eight-dot output columns.
    int64_t const first_cell = start_x >> 19;
    unsigned last_cell = ~0U;
    int32_t cell_y = 0;
    for (int x = cliprect.left(); x <= cliprect.right(); ++x) {
      int const sample_x = x - x % mosaic_x;
      int64_t const source_x = start_x + int64_t(sample_x) * incx;
      if (cell_scroll) {
        unsigned const cell = unsigned((source_x >> 19) - first_cell);
        if (cell != last_cell) {
          cell_y = util::sext(m_vdp2_vram[(cell_base + cell * cell_stride) & word_mask] & 0x07ffff00, 27);
          last_cell = cell;
        }
      }
      if (!vdp2_window_process(x, y))
        continue;
      int32_t const sx = int32_t(source_x >> 16);
      int32_t const sy = int32_t((start_y + cell_y) >> 16);
      if (!have_pixel || sx != last_x || sy != last_y) {
        pixel = vdp2_scroll_pixel(sx, sy);
        if (!m_vdp2_composition_active && pixel.a() && (t.fade_control & 1)) {
          unsigned const metadata = uint32_t(pixel) & 0xff000000;
          vdp2_compute_color_offset_UINT32(&pixel, t.fade_control & 2);
          pixel = rgb_t((uint32_t(pixel) & 0xffffff) | metadata);
        }
        last_x = sx;
        last_y = sy;
        have_pixel = true;
      }
      if (!pixel.a())
        continue;
      if (special_priority && m_vdp2_priority_pass >= 0 &&
          ((pixel.a() >> 2) & 7) != unsigned(m_vdp2_priority_pass))
        continue;
      rgb_t const color = rgb_t(uint32_t(pixel) | 0xff000000);
      bool const calculate = t.colour_calculation_enabled && (pixel.a() & 1);
      vdp2_compose_pixel(bitmap, x, y, color, calculate, t.alpha, t.line_screen_enabled,
          calculate && t.line_screen_enabled ? vdp2_line_color(y, false, 0) : rgb_t(0),
          t.layer_name | (t.colour_depth < 3 ? 8 : 0));
    }
  }
}

void saturn_state::vdp2_copy_roz_bitmap(bitmap_rgb32 &bitmap,
                                        bitmap_rgb32 &roz_bitmap,
                                        const rectangle &cliprect, int iRP,
                                        int planesizex, int planesizey,
                                        int planerenderedsizex,
                                        int planerenderedsizey) {
  int32_t xsp, ysp, xp, yp, dx, dy, x, y, xs, ys, dxs, dys;
  int32_t vcnt, hcnt;
  int32_t kx, ky;
  int8_t use_coeff_table, coeff_table_mode, coeff_table_size, coeff_table_shift;
  int8_t screen_over_process;
  uint8_t vcnt_shift, hcnt_shift;
  uint8_t coeff_msb;
  uint32_t coeff_table_offset;
  int32_t coeff_table_val;
  uint32_t address;
  // Source writers set rgb_t alpha on every drawn dot, including black.
  // Transparent dots leave the cleared cache untouched. Coverage must not
  // be inferred from RGB intensity or applied a second time after decoding.
  rgb_t pix;
  uint8_t coeff_line_color_screen_data = 0;
  int32_t clipxmask = 0, clipymask = 0;

  vcnt_shift = m_vdp2->get_lsmd() == 3;
  hcnt_shift = BIT(m_vdp2->get_hreso(), 1);
  // ST-058 pp.117-119: RBG0/RBG1 mosaic is horizontal only. Sample the
  // layer before blending, never copy an already-composited destination dot.
  // Rotation dots are doubled in high-resolution output (Ymir rotation path).
  int const mosaic_width = current_tilemap.mosaic_screen_enabled
      ? (VDP2_MZSZH + 1) << hcnt_shift : 1;
  auto const mosaic_x = [mosaic_width](int x) { return x - x % mosaic_width; };

  planesizex--;
  planesizey--;
  planerenderedsizex--;
  planerenderedsizey--;

  kx = RP.kx;
  ky = RP.ky;

  use_coeff_table = coeff_table_mode = coeff_table_size = coeff_table_shift = 0;
  coeff_table_offset = 0;
  coeff_table_val = 0;

  LOGMASKED(LOG_ROZ, "Rendering RBG with parameter %s\n", iRP == 1 ? "A" : "B");
  LOGMASKED(LOG_ROZ, "RPMD (parameter mode) = %x\n", VDP2_RPMD);
  LOGMASKED(LOG_ROZ, "RPRCTL (parameter read control) = %04x\n", VDP2_RPRCTL);
  LOGMASKED(LOG_ROZ, "KTCTL (coefficient table control) = %04x\n", VDP2_KTCTL);
  LOGMASKED(LOG_ROZ, "KTAOF (coefficient table address offset) = %04x\n",
            VDP2_KTAOF);
  LOGMASKED(LOG_ROZ, "RAOVR (screen-over process) = %x\n", VDP2_RAOVR);
  if (iRP == 1) {
    use_coeff_table = VDP2_RAKTE;
    if (use_coeff_table == 1) {
      coeff_table_mode = VDP2_RAKMD;
      coeff_table_size = VDP2_RAKDBS;
      coeff_table_offset = VDP2_RAKTAOS;
    }
    screen_over_process = VDP2_RAOVR;
  } else {
    use_coeff_table = VDP2_RBKTE;
    if (use_coeff_table == 1) {
      coeff_table_mode = VDP2_RBKMD;
      coeff_table_size = VDP2_RBKDBS;
      coeff_table_offset = VDP2_RBKTAOS;
    }
    screen_over_process = VDP2_RBOVR;
  }
  if (use_coeff_table) {
    /* the table lives in VRAM, or in the upper half of CRAM when CRKTE is set
     */
    if (coeff_table_size == 0) {
      coeff_table_offset = (coeff_table_offset & 0x0003) * 0x40000;
      coeff_table_shift = 2;
    } else {
      coeff_table_offset = (coeff_table_offset & 0x0007) * 0x20000;
      coeff_table_shift = 1;
    }
  }

  if (current_tilemap.colour_calculation_enabled == 1) {
    if (VDP2_CCMD) {
      current_tilemap.transparency |= STV_TRANSPARENCY_ADD_BLEND;
    } else {
      current_tilemap.transparency |= STV_TRANSPARENCY_ALPHA;
    }
  }

  // Rebuild this small character each output pass, so OVPNR, palette and
  // character VRAM writes cannot leave a stale pattern in the map cache.
  rgb_t over_pattern[16 * 16];
  bool const repeat_pattern = screen_over_process == 1 && !current_tilemap.bitmap_enable;
  int const over_mask = current_tilemap.tile_size ? 15 : 7;
  if (repeat_pattern) {
    uint16_t const name = iRP == 1 ? VDP2_OVPNRA : VDP2_OVPNRB;
    for (int py = 0; py <= over_mask; ++py)
      for (int px = 0; px <= over_mask; ++px)
        over_pattern[py * 16 + px] = vdp2_screen_over_pattern_pixel(name, px, py);
  }

  bool const special_priority = vdp2_special_priority_mode() != 0;
  bool const sample_attributes = special_priority || (current_tilemap.colour_calculation_enabled && vdp2_special_color_mode());
  bool have_source = false;
  int last_source_x = 0, last_source_y = 0;
  rgb_t source_pixel;
  auto const source = [&](int sx, int sy) {
    if (!sample_attributes)
      return rgb_t(roz_bitmap.pix(sy & planerenderedsizey, sx & planerenderedsizex));
    sx &= planesizex;
    sy &= planesizey;
    if (!have_source || sx != last_source_x || sy != last_source_y) {
      source_pixel = vdp2_scroll_pixel(sx, sy);
      last_source_x = sx;
      last_source_y = sy;
      have_source = true;
    }
    return source_pixel;
  };

  // RPMD 2 selects a parameter before transparency/color calculation. B is
  // not a second background beneath A (ST-058 Table 6.4). In particular an
  // absent A dot must expose the previous screen, not a pre-rendered B dot.
  rotation_table parameter_a = current_rotation_table;
  if (iRP == 2 && (VDP2_RPMD == 2 || (current_tilemap.line_screen_enabled && VDP2_R1ON))) {
    rotation_table const parameter_b = current_rotation_table;
    vdp2_load_rotation_line(1, cliprect.top());
    parameter_a = current_rotation_table;
    current_rotation_table = parameter_b;
  }
  // When A reads coefficients per dot in mode 2, B may only read per line.
  bool const per_dot_coefficients = vdp2_per_dot_coefficients(VDP2_RAMCTL);
  int32_t const coefficient_dx = !per_dot_coefficients ? 0 : VDP2_RPMD == 2 && iRP == 2 &&
      VDP2_RAKTE && parameter_a.dkax != 0 ? 0 : RP.dkax;
  uint32_t last_a_address = 0, last_a_entry = 0;
  bool have_a_entry = false;
  auto const selected = [&](int hx, int vy) {
    if (VDP2_RPMD != 2 || iRP == 1)
      return true;
    if (!VDP2_RAKTE)
      return false;
    uint32_t const index = (parameter_a.kast +
        coef_delta(parameter_a.dkast, vy >> vcnt_shift) +
        coef_delta(per_dot_coefficients ? parameter_a.dkax : 0, mosaic_x(hx))) >> 16;
    uint32_t const a_address = VDP2_RAKDBS
        ? (VDP2_RAKTAOS & 7) * 0x20000 + index * 2
        : (VDP2_RAKTAOS & 3) * 0x40000 + index * 4;
    // A line coefficient is shared by all its output dots. Cache only for
    // this pass; register/VRAM writes cannot leave a persistent stale entry.
    if (!have_a_entry || last_a_address != a_address) {
      last_a_entry = vdp2_read_rotation_coefficient(a_address);
      last_a_address = a_address;
      have_a_entry = true;
    }
    return VDP2_RAKDBS ? bool(last_a_entry & ((a_address & 2) ? 0x8000 : 0x80000000))
                      : bool(last_a_entry & 0x80000000);
  };

  auto const second_image = [&](int hx, int vy) -> rgb_t {
    if (!current_tilemap.line_screen_enabled)
      return rgb_t(bitmap.pix(vy, hx));
    bool const from_a = VDP2_RPMD == 2 || VDP2_R1ON || iRP == 1;
    bool const enabled = from_a ? VDP2_RAKTE && VDP2_RAKLCE && !VDP2_RAKDBS
                               : VDP2_RBKTE && VDP2_RBKLCE && !VDP2_RBKDBS;
    uint8_t color = coeff_line_color_screen_data;
    if (enabled && from_a && iRP == 2) {
      uint32_t const index = (parameter_a.kast + coef_delta(parameter_a.dkast, vy >> vcnt_shift) +
          coef_delta(per_dot_coefficients ? parameter_a.dkax : 0, mosaic_x(hx))) >> 16;
      uint32_t const a_address = (VDP2_RAKTAOS & 3) * 0x40000 + index * 4;
      if (!have_a_entry || last_a_address != a_address) {
        last_a_entry = vdp2_read_rotation_coefficient(a_address);
        last_a_address = a_address;
        have_a_entry = true;
      }
      color = (last_a_entry >> 24) & 0x7f;
    }
    return vdp2_line_color(vy, enabled, color);
  };


  /* clipping */
  switch (screen_over_process) {
  case 0:
    /* repeated */
    clipxmask = clipymask = 0;
    break;
  case 1:
    /* screen over pattern */
    clipxmask = ~planesizex;
    clipymask = ~planesizey;
    break;
  case 2:
    /* outside display area, scroll screen is transparent */
    clipxmask = ~planesizex;
    clipymask = ~planesizey;
    break;
  case 3:
    /* display area is 512x512, outside is transparent */
    clipxmask = ~511;
    clipymask = ~511;
    break;
  }

  dx = vdp2_wrap_sum(mul_fixed32(RP.A, RP.dx), mul_fixed32(RP.B, RP.dy));
  dy = vdp2_wrap_sum(mul_fixed32(RP.D, RP.dx), mul_fixed32(RP.E, RP.dy));
  xp = vdp2_wrap_sum(mul_fixed32(RP.A, vdp2_wrap_sub(RP.px, RP.cx)),
      mul_fixed32(RP.B, vdp2_wrap_sub(RP.py, RP.cy)),
      mul_fixed32(RP.C, vdp2_wrap_sub(RP.pz, RP.cz)), RP.cx, RP.mx);
  yp = vdp2_wrap_sum(mul_fixed32(RP.D, vdp2_wrap_sub(RP.px, RP.cx)),
      mul_fixed32(RP.E, vdp2_wrap_sub(RP.py, RP.cy)),
      mul_fixed32(RP.F, vdp2_wrap_sub(RP.pz, RP.cz)), RP.cy, RP.my);

  // Mosaic repeats a source coefficient, not a VRAM read for each output
  // dot. This pass-local memo also covers equal per-line addresses; no state
  // survives an intervening register/VRAM write or a partial render pass.
  bool have_coefficient = false;
  uint32_t last_coefficient_address = 0, last_coefficient = 0;
  auto const read_coefficient = [&](uint32_t addr) {
    if (!have_coefficient || addr != last_coefficient_address) {
      last_coefficient = vdp2_read_rotation_coefficient(addr);
      last_coefficient_address = addr;
      have_coefficient = true;
    }
    return last_coefficient;
  };

  for (vcnt = cliprect.top(); vcnt <= cliprect.bottom(); vcnt++) {
    int32_t const start_x = vdp2_wrap_sub(vdp2_wrap_sum(RP.xst,
        mul_fixed32(RP.dxst, vcnt << (16 - vcnt_shift))), RP.px);
    int32_t const start_y = vdp2_wrap_sub(vdp2_wrap_sum(RP.yst,
        mul_fixed32(RP.dyst, vcnt << (16 - vcnt_shift))), RP.py);
    xsp = vdp2_wrap_sum(mul_fixed32(RP.A, start_x), mul_fixed32(RP.B, start_y),
        mul_fixed32(RP.C, vdp2_wrap_sub(RP.zst, RP.pz)));
    ysp = vdp2_wrap_sum(mul_fixed32(RP.D, start_x), mul_fixed32(RP.E, start_y),
        mul_fixed32(RP.F, vdp2_wrap_sub(RP.zst, RP.pz)));


    // TODO: nuke this spaghetti code
    if (!use_coeff_table || coefficient_dx == 0) {
      if (use_coeff_table) {
        switch (coeff_table_size) {
        case 0:
          address =
              coeff_table_offset +
              ((RP.kast + coef_delta(RP.dkast, vcnt >> vcnt_shift)) >> 16) * 4;
          coeff_table_val = read_coefficient(address);
          coeff_line_color_screen_data = (uint32_t(coeff_table_val) >> 24) & 0x7f;
          coeff_msb = (coeff_table_val & 0x80000000) > 0;
          if (coeff_table_val & 0x00800000) {
            coeff_table_val |= 0xff000000;
          } else {
            coeff_table_val &= 0x007fffff;
          }
          break;
        case 1:
          address =
              coeff_table_offset +
              ((RP.kast + coef_delta(RP.dkast, vcnt >> vcnt_shift)) >> 16) * 2;
          coeff_table_val = read_coefficient(address);
          if ((address & 2) == 0) {
            coeff_table_val >>= 16;
          }
          coeff_table_val &= 0xffff;
          coeff_line_color_screen_data = 0;
          coeff_msb = (coeff_table_val & 0x8000) > 0;
          if (coeff_table_val & 0x4000) {
            coeff_table_val |= 0xffff8000;
          } else {
            coeff_table_val &= 0x3fff;
          }
          coeff_table_val = uint32_t(coeff_table_val) << 6; /* to form 16.16 fixed point val */
          break;
        default:
          coeff_msb = 1;
          break;
        }
        if (coeff_msb)
          continue;

        switch (coeff_table_mode) {
        case 0:
          kx = ky = coeff_table_val;
          break;
        case 1:
          kx = coeff_table_val;
          break;
        case 2:
          ky = coeff_table_val;
          break;
        case 3:
          xp = uint32_t(coeff_table_val) << 8; // mode 3: .8, not .16 (ST-058 p.165)
          break;
        }
      }

      // x = RP.kx * ( xsp + dx * (hcnt << 16)) + xp;
      // y = RP.ky * ( ysp + dy * (hcnt << 16)) + yp;
      xs = vdp2_wrap_sum(mul_fixed32(kx, xsp), xp);
      ys = vdp2_wrap_sum(mul_fixed32(ky, ysp), yp);
      dxs = mul_fixed32(kx, mul_fixed32(dx, 1 << (16 - hcnt_shift)));
      dys = mul_fixed32(ky, mul_fixed32(dy, 1 << (16 - hcnt_shift)));
      // Partial updates retain the screen-left coordinate origin. Advance
      // both accumulators to the first output pixel, with 32-bit wrapping.
      xs = uint32_t(xs) + uint32_t(int64_t(dxs) * cliprect.left());
      ys = uint32_t(ys) + uint32_t(int64_t(dys) * cliprect.left());

      for (hcnt = cliprect.left(); hcnt <= cliprect.right();
           xs = vdp2_wrap_sum(xs, dxs), ys = vdp2_wrap_sum(ys, dys), hcnt++) {
        int const sample_h = mosaic_x(hcnt);
        x = int32_t(uint32_t(xs) + uint32_t(int64_t(dxs) * (sample_h - hcnt))) >> 16;
        y = int32_t(uint32_t(ys) + uint32_t(int64_t(dys) * (sample_h - hcnt))) >> 16;

        bool const outside = (x & clipxmask) || (y & clipymask);
        if ((outside && !repeat_pattern) || !selected(sample_h, vcnt))
          continue;
        if (vdp2_roz_window(hcnt, vcnt) == false)
          continue;

        if (current_tilemap.roz_mode3 == true) {
          if (vdp2_roz_mode3_window(sample_h, vcnt, iRP - 1) == false)
            continue;
        }

        pix = outside ? over_pattern[(y & over_mask) * 16 + (x & over_mask)]
                      : source(x, y);
        if (!pix.a())
          continue;
        if (special_priority && m_vdp2_priority_pass >= 0 &&
            ((pix.a() >> 2) & 7) != unsigned(m_vdp2_priority_pass))
          continue;
        bool const calculate = pix.a() & 1;
        pix = rgb_t(uint32_t(pix) | 0xff000000);
        if (!m_vdp2_composition_active && (current_tilemap.fade_control & 1))
          vdp2_compute_color_offset_UINT32(&pix, current_tilemap.fade_control & 2);
        bool const blend = current_tilemap.colour_calculation_enabled && calculate;
        vdp2_compose_pixel(bitmap, hcnt, vcnt, pix, blend, current_tilemap.alpha,
            current_tilemap.line_screen_enabled,
            blend && current_tilemap.line_screen_enabled ? second_image(hcnt, vcnt) : rgb_t(0),
            (current_tilemap.layer_name == 0x81 ? 0 : 4) | (current_tilemap.colour_depth < 3 ? 8 : 0));
      }
    } else {
      for (hcnt = cliprect.left(); hcnt <= cliprect.right(); hcnt++) {
        int const sample_h = mosaic_x(hcnt);
        switch (coeff_table_size) {
        case 0:
          address = coeff_table_offset +
                    ((RP.kast + coef_delta(RP.dkast, vcnt >> vcnt_shift) +
                      coef_delta(coefficient_dx, sample_h)) >>
                     16) *
                        4;
          coeff_table_val = read_coefficient(address);
          coeff_line_color_screen_data = (uint32_t(coeff_table_val) >> 24) & 0x7f;
          coeff_msb = (coeff_table_val & 0x80000000) > 0;
          if (coeff_table_val & 0x00800000) {
            coeff_table_val |= 0xff000000;
          } else {
            coeff_table_val &= 0x007fffff;
          }
          break;
        case 1:
          address = coeff_table_offset +
                    ((RP.kast + coef_delta(RP.dkast, vcnt >> vcnt_shift) +
                      coef_delta(coefficient_dx, sample_h)) >>
                     16) *
                        2;
          coeff_table_val = read_coefficient(address);
          if ((address & 2) == 0) {
            coeff_table_val >>= 16;
          }
          coeff_table_val &= 0xffff;
          coeff_line_color_screen_data = 0;
          coeff_msb = (coeff_table_val & 0x8000) > 0;
          if (coeff_table_val & 0x4000) {
            coeff_table_val |= 0xffff8000;
          } else {
            coeff_table_val &= 0x3fff;
          }
          coeff_table_val = uint32_t(coeff_table_val) << 6; /* to form 16.16 fixed point val */
          break;
        default:
          coeff_msb = 1;
          break;
        }
        if (coeff_msb)
          continue;
        switch (coeff_table_mode) {
        case 0:
          kx = ky = coeff_table_val;
          break;
        case 1:
          kx = coeff_table_val;
          break;
        case 2:
          ky = coeff_table_val;
          break;
        case 3:
          xp = uint32_t(coeff_table_val) << 8; // mode 3: .8, not .16 (ST-058 p.165)
          break;
        }

        // x = RP.kx * ( xsp + dx * (hcnt << 16)) + xp;
        // y = RP.ky * ( ysp + dy * (hcnt << 16)) + yp;
        x = vdp2_wrap_sum(mul_fixed32(kx, vdp2_wrap_sum(xsp,
            mul_fixed32(dx, (sample_h >> hcnt_shift) << 16))), xp);
        y = vdp2_wrap_sum(mul_fixed32(ky, vdp2_wrap_sum(ysp,
            mul_fixed32(dy, (sample_h >> hcnt_shift) << 16))), yp);

        x >>= 16;
        y >>= 16;

        bool const outside = (x & clipxmask) || (y & clipymask);
        if ((outside && !repeat_pattern) || !selected(sample_h, vcnt))
          continue;
        // Coefficient lookup granularity does not bypass either window.
        if (!vdp2_roz_window(hcnt, vcnt))
          continue;
        if (current_tilemap.roz_mode3 &&
            !vdp2_roz_mode3_window(sample_h, vcnt, iRP - 1))
          continue;

        pix = outside ? over_pattern[(y & over_mask) * 16 + (x & over_mask)]
                      : source(x, y);
        if (!pix.a())
          continue;
        if (special_priority && m_vdp2_priority_pass >= 0 &&
            ((pix.a() >> 2) & 7) != unsigned(m_vdp2_priority_pass))
          continue;
        bool const calculate = pix.a() & 1;
        pix = rgb_t(uint32_t(pix) | 0xff000000);
        if (!m_vdp2_composition_active && (current_tilemap.fade_control & 1))
          vdp2_compute_color_offset_UINT32(&pix, current_tilemap.fade_control & 2);
        bool const blend = current_tilemap.colour_calculation_enabled && calculate;
        vdp2_compose_pixel(bitmap, hcnt, vcnt, pix, blend, current_tilemap.alpha,
            current_tilemap.line_screen_enabled,
            blend && current_tilemap.line_screen_enabled ? second_image(hcnt, vcnt) : rgb_t(0),
            (current_tilemap.layer_name == 0x81 ? 0 : 4) | (current_tilemap.colour_depth < 3 ? 8 : 0));
      }
    }
  }
}

// The rotation screen tests its window once per destination pixel, but the
// window rectangles only depend on the line: fetch them once per line and let
// the pixel test be a few integer compares. Both the RBG0 window and the
// rotation parameter window share window 0 and window 1, so one memo serves
// both.
void saturn_state::vdp2_roz_window_prepare(int y) {
  if (m_roz_window_cache_y == y)
    return;

  m_roz_window_cache_y = y;
  vdp2_get_window0_coordinates(&m_roz_win_s_x[0], &m_roz_win_e_x[0],
                               &m_roz_win_s_y[0], &m_roz_win_e_y[0], y);
  vdp2_get_window1_coordinates(&m_roz_win_s_x[1], &m_roz_win_e_x[1],
                               &m_roz_win_s_y[1], &m_roz_win_e_y[1], y);
}

// ST-058 pp.187-188: the sprite window is the displayed framebuffer MSB,
// for palette-only sprite types 2-7. Reuse the real VDP1 scanout addressing
// (bank, interlace, resolution and rotation), not command RAM or RGB output.
// This derived row is invalidated at every partial render and register write.
bool saturn_state::vdp2_sprite_window(int x, int y) {
  if (!VDP2_SPWINEN || VDP2_SPCLMD || VDP2_SPTYPE < 2 || VDP2_SPTYPE > 7 ||
      unsigned(x) >= WINDOW_CACHE_WIDTH || unsigned(y) >= 512)
    return false;
  if (m_sprite_window_y != y) {
    auto const rotation = vdp1_rotation_parameters();
    for (int sx = 0; sx < WINDOW_CACHE_WIDTH; ++sx)
      m_sprite_window_line[sx] = (vdp1_display_pixel(sx, y, rotation) & 0x8000) != 0;
    m_sprite_window_y = y;
  }
  return m_sprite_window_line[x];
}

inline bool saturn_state::vdp2_roz_window(int x, int y) {
  int res;
  bool const rbg1 = current_tilemap.layer_name == 0x81;
  uint8_t logic = rbg1 ? VDP2_N0LOG : VDP2_R0LOG;
  uint8_t w0_enable = rbg1 ? VDP2_N0W0E : VDP2_R0W0E;
  uint8_t w1_enable = rbg1 ? VDP2_N0W1E : VDP2_R0W1E;
  uint8_t w0_area = rbg1 ? VDP2_N0W0A : VDP2_R0W0A;
  uint8_t w1_area = rbg1 ? VDP2_N0W1A : VDP2_R0W1A;

  uint8_t const sw_enable = rbg1 ? VDP2_N0SWE : VDP2_R0SWE;
  uint8_t const sw_area = rbg1 ? VDP2_N0SWA : VDP2_R0SWA;
  if (w0_enable == 0 && w1_enable == 0 && !sw_enable)
    return !(logic & 1);

  if (w0_enable || w1_enable)
    vdp2_roz_window_prepare(y);

  const int logic_or = logic & 1;
  res = logic_or ? 0 : 1;

  if (w0_enable) {
    const int w0_pix = get_roz_window_pixel(m_roz_win_s_x[0], m_roz_win_e_x[0],
                                            m_roz_win_s_y[0], m_roz_win_e_y[0],
                                            x, y, w0_enable, w0_area);
    res = logic_or ? (res | w0_pix) : (res & w0_pix);
  }

  if (w1_enable) {
    const int w1_pix = get_roz_window_pixel(m_roz_win_s_x[1], m_roz_win_e_x[1],
                                            m_roz_win_s_y[1], m_roz_win_e_y[1],
                                            x, y, w1_enable, w1_area);
    res = logic_or ? (res | w1_pix) : (res & w1_pix);
  }

  if (sw_enable) {
    bool const keep = vdp2_sprite_window(x, y) == bool(sw_area);
    res = logic_or ? (res | keep) : (res & keep);
  }
  return res;
}

inline bool saturn_state::vdp2_roz_mode3_window(int x, int y,
                                                int rot_parameter) {
  int res;
  uint8_t logic = VDP2_RPLOG;
  uint8_t w0_enable = VDP2_RPW0E;
  uint8_t w1_enable = VDP2_RPW1E;
  uint8_t w0_area = VDP2_RPW0A;
  uint8_t w1_area = VDP2_RPW1A;

  if (w0_enable == 0 && w1_enable == 0 && !VDP2_RPSWE)
    return (logic & 1) ? rot_parameter : (rot_parameter ^ 1);

  if (w0_enable || w1_enable)
    vdp2_roz_window_prepare(y);

  const int logic_or = logic & 1;
  res = logic_or ? 0 : 1;

  if (w0_enable) {
    const int w0_pix = get_roz_window_pixel(m_roz_win_s_x[0], m_roz_win_e_x[0],
                                            m_roz_win_s_y[0], m_roz_win_e_y[0],
                                            x, y, w0_enable, w0_area);
    res = logic_or ? (res | w0_pix) : (res & w0_pix);
  }

  if (w1_enable) {
    const int w1_pix = get_roz_window_pixel(m_roz_win_s_x[1], m_roz_win_e_x[1],
                                            m_roz_win_s_y[1], m_roz_win_e_y[1],
                                            x, y, w1_enable, w1_area);
    res = logic_or ? (res | w1_pix) : (res & w1_pix);
  }

  if (VDP2_RPSWE) {
    bool const keep = vdp2_sprite_window(x, y) == bool(VDP2_RPSWA);
    res = logic_or ? (res | keep) : (res & keep);
  }
  return res ^ rot_parameter;
}

inline int saturn_state::get_roz_window_pixel(int s_x, int e_x, int s_y,
                                              int e_y, int x, int y,
                                              uint8_t winenable,
                                              uint8_t winarea) {
  int res;

  res = 1;
  if (winenable) {
    if (winarea)
      res = (y >= s_y && y <= e_y && x >= s_x && x <= e_x);
    else
      res = (y >= s_y && y <= e_y && x >= s_x && x <= e_x) ^ 1;
  }

  return res;
}

void saturn_state::vdp2_draw_NBG0(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  uint32_t base_mask;

  base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;

  /*
     Colours           : 16, 256, 2048, 32768, 16770000
     Char Size         : 1x1 cells, 2x2 cells
     Pattern Data Size : 1 word, 2 words
     Plane Layouts     : 1 x 1, 2 x 1, 2 x 2
     Planes            : 4
     Bitmap            : Possible
     Bitmap Sizes      : 512 x 256, 512 x 512, 1024 x 256, 1024 x 512
     Scale             : 0.25 x - 256 x
     Rotation          : No
     Linescroll        : Yes
     Column Scroll     : Yes
     Mosaic            : Yes
  */

  current_tilemap.enabled = VDP2_N0ON | VDP2_R1ON;

  //  if (!current_tilemap.enabled) return; // stop right now if its disabled
  //  ...

  // current_tilemap.trans_enabled = VDP2_N0TPON;
  current_tilemap.alpha = vdp2_cc_blend_level(VDP2_N0CCRT);
  if (VDP2_N0CCEN) {
    current_tilemap.colour_calculation_enabled = 1;

  } else {
    current_tilemap.colour_calculation_enabled = 0;
  }
  if (VDP2_N0TPON == 0) {
    current_tilemap.transparency = STV_TRANSPARENCY_PEN;
  } else {
    current_tilemap.transparency = STV_TRANSPARENCY_NONE;
  }
  current_tilemap.colour_depth = VDP2_N0CHCN;
  current_tilemap.tile_size = VDP2_N0CHSZ;
  current_tilemap.bitmap_enable = VDP2_N0BMEN;
  current_tilemap.bitmap_size = VDP2_N0BMSZ;
  current_tilemap.bitmap_palette_number = VDP2_N0BMP;
  current_tilemap.bitmap_map = VDP2_N0MP_;
  current_tilemap.map_offset[0] = VDP2_N0MPA | (VDP2_N0MP_ << 6);
  current_tilemap.map_offset[1] = VDP2_N0MPB | (VDP2_N0MP_ << 6);
  current_tilemap.map_offset[2] = VDP2_N0MPC | (VDP2_N0MP_ << 6);
  current_tilemap.map_offset[3] = VDP2_N0MPD | (VDP2_N0MP_ << 6);
  current_tilemap.map_count = 4;

  current_tilemap.pattern_data_size = VDP2_N0PNB;
  current_tilemap.character_number_supplement = VDP2_N0CNSM;
  current_tilemap.special_priority_register = VDP2_N0SPR;
  current_tilemap.special_colour_control_register = VDP2_N0SCC;
  current_tilemap.supplementary_palette_bits = VDP2_N0SPLT;
  current_tilemap.supplementary_character_bits = VDP2_N0SPCN;

  current_tilemap.scrollx = VDP2_SCXIN0;
  current_tilemap.scrolly = VDP2_SCYIN0;
  current_tilemap.scrollx_fraction = VDP2_SCXDN0 & 0xff00;
  current_tilemap.scrolly_fraction = VDP2_SCYDN0 & 0xff00;
  current_tilemap.incx = VDP2_ZMXN0;
  current_tilemap.incy = VDP2_ZMYN0;

  current_tilemap.linescroll_enable = VDP2_N0LSCX;
  current_tilemap.linescroll_interval = ((m_vdp2->get_lsmd() == 2) ? (2) : (1))
                                        << (VDP2_N0LSS);
  current_tilemap.linescroll_table_address =
      (((VDP2_LSTA0U << 16) | VDP2_LSTA0L) & base_mask) * 2;
  current_tilemap.vertical_linescroll_enable = VDP2_N0LSCY;
  current_tilemap.linezoom_enable = VDP2_N0LZMX;
  current_tilemap.vertical_cell_scroll_enable = VDP2_N0VCSC;

  current_tilemap.plane_size = (VDP2_R1ON) ? VDP2_RBPLSZ : VDP2_N0PLSZ;
  current_tilemap.colour_ram_address_offset = VDP2_N0CAOS;
  current_tilemap.fade_control = (VDP2_N0COEN * 1) | (VDP2_N0COSL * 2);
  vdp2_check_fade_control_for_layer();
  current_tilemap.window_control.logic = VDP2_N0LOG;
  current_tilemap.window_control.enabled[0] = VDP2_N0W0E;
  current_tilemap.window_control.enabled[1] = VDP2_N0W1E;
  current_tilemap.window_control.sprite_window = VDP2_N0SWE ? 1 | (VDP2_N0SWA << 1) : 0;
  current_tilemap.window_control.area[0] = VDP2_N0W0A;
  current_tilemap.window_control.area[1] = VDP2_N0W1A;
  //  current_tilemap.window_control.? = VDP2_N0SWA;

  current_tilemap.line_screen_enabled = VDP2_N0LCEN;
  current_tilemap.mosaic_screen_enabled = VDP2_N0MZE;

  current_tilemap.layer_name = (VDP2_R1ON) ? 0x81 : 0;

  if (current_tilemap.enabled &&
      (!(VDP2_R1ON))) /* TODO: check cycle pattern for RBG1 */
  {
    current_tilemap.enabled = vdp2_check_vram_cycle_pattern_registers(
        VDP2_CP_NBG0_PNMDR, VDP2_CP_NBG0_CPDR, current_tilemap.bitmap_enable);
  }

  current_tilemap.roz_mode3 = false;
  if (VDP2_R1ON) {
    // RBG1 shares format/color controls with NBG0, not its normal-scroll
    // coordinate or line/cell-scroll controls (ST-058 sections 5 and 6).
    current_tilemap.scrollx = current_tilemap.scrolly = 0;
    current_tilemap.incx = current_tilemap.incy = 0x10000;
    current_tilemap.linescroll_enable = 0;
    current_tilemap.vertical_linescroll_enable = 0;
    current_tilemap.vertical_cell_scroll_enable = 0;
    current_tilemap.linezoom_enable = 0;
    current_tilemap.window_control = {}; // evaluated on the rotated output
    vdp2_draw_rotation_screen(bitmap, cliprect, 2);
  } else
    vdp2_check_tilemap(bitmap, cliprect);
}

void saturn_state::vdp2_draw_NBG1(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  uint32_t base_mask;

  base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;

  /*
     Colours           : 16, 256, 2048, 32768
     Char Size         : 1x1 cells, 2x2 cells
     Pattern Data Size : 1 word, 2 words
     Plane Layouts     : 1 x 1, 2 x 1, 2 x 2
     Planes            : 4
     Bitmap            : Possible
     Bitmap Sizes      : 512 x 256, 512 x 512, 1024 x 256, 1024 x 512
     Scale             : 0.25 x - 256 x
     Rotation          : No
     Linescroll        : Yes
     Column Scroll     : Yes
     Mosaic            : Yes
  */
  current_tilemap.enabled = VDP2_N1ON;

  // ST-058 p.148: two rotation screens exclude the normal screens.
  if (VDP2_R0ON && VDP2_R1ON)
    current_tilemap.enabled = 0;

  // ST-058 p.61: RGB888 NBG0 excludes all other normal screens.
  if (VDP2_N0CHCN == 0x04)
    current_tilemap.enabled = 0;

  //  if (!current_tilemap.enabled) return; // stop right now if its disabled
  //  ...

  // current_tilemap.trans_enabled = VDP2_N1TPON;
  current_tilemap.alpha = vdp2_cc_blend_level(VDP2_N1CCRT);
  if (VDP2_N1CCEN) {
    current_tilemap.colour_calculation_enabled = 1;

  } else {
    current_tilemap.colour_calculation_enabled = 0;
  }
  if (VDP2_N1TPON == 0) {
    current_tilemap.transparency = STV_TRANSPARENCY_PEN;
  } else {
    current_tilemap.transparency = STV_TRANSPARENCY_NONE;
  }
  current_tilemap.colour_depth = VDP2_N1CHCN;
  current_tilemap.tile_size = VDP2_N1CHSZ;
  current_tilemap.bitmap_enable = VDP2_N1BMEN;
  current_tilemap.bitmap_size = VDP2_N1BMSZ;
  current_tilemap.bitmap_palette_number = VDP2_N1BMP;
  current_tilemap.bitmap_map = VDP2_N1MP_;
  current_tilemap.map_offset[0] = VDP2_N1MPA | (VDP2_N1MP_ << 6);
  current_tilemap.map_offset[1] = VDP2_N1MPB | (VDP2_N1MP_ << 6);
  current_tilemap.map_offset[2] = VDP2_N1MPC | (VDP2_N1MP_ << 6);
  current_tilemap.map_offset[3] = VDP2_N1MPD | (VDP2_N1MP_ << 6);
  current_tilemap.map_count = 4;

  current_tilemap.pattern_data_size = VDP2_N1PNB;
  current_tilemap.character_number_supplement = VDP2_N1CNSM;
  current_tilemap.special_priority_register = VDP2_N1SPR;
  current_tilemap.special_colour_control_register = VDP2_N1SCC;
  current_tilemap.supplementary_palette_bits = VDP2_N1SPLT;
  current_tilemap.supplementary_character_bits = VDP2_N1SPCN;

  current_tilemap.scrollx = VDP2_SCXIN1;
  current_tilemap.scrolly = VDP2_SCYIN1;
  current_tilemap.scrollx_fraction = VDP2_SCXDN1 & 0xff00;
  current_tilemap.scrolly_fraction = VDP2_SCYDN1 & 0xff00;
  current_tilemap.incx = VDP2_ZMXN1;
  current_tilemap.incy = VDP2_ZMYN1;

  current_tilemap.linescroll_enable = VDP2_N1LSCX;
  current_tilemap.linescroll_interval = ((m_vdp2->get_lsmd() == 2) ? (2) : (1))
                                        << (VDP2_N1LSS);
  current_tilemap.linescroll_table_address =
      (((VDP2_LSTA1U << 16) | VDP2_LSTA1L) & base_mask) * 2;
  current_tilemap.vertical_linescroll_enable = VDP2_N1LSCY;
  current_tilemap.linezoom_enable = VDP2_N1LZMX;
  current_tilemap.vertical_cell_scroll_enable = VDP2_N1VCSC;

  current_tilemap.plane_size = VDP2_N1PLSZ;
  current_tilemap.colour_ram_address_offset = VDP2_N1CAOS;
  current_tilemap.fade_control = (VDP2_N1COEN * 1) | (VDP2_N1COSL * 2);
  vdp2_check_fade_control_for_layer();
  current_tilemap.window_control.logic = VDP2_N1LOG;
  current_tilemap.window_control.enabled[0] = VDP2_N1W0E;
  current_tilemap.window_control.enabled[1] = VDP2_N1W1E;
  current_tilemap.window_control.sprite_window = VDP2_N1SWE ? 1 | (VDP2_N1SWA << 1) : 0;
  current_tilemap.window_control.area[0] = VDP2_N1W0A;
  current_tilemap.window_control.area[1] = VDP2_N1W1A;
  //  current_tilemap.window_control.? = VDP2_N1SWA;

  current_tilemap.line_screen_enabled = VDP2_N1LCEN;
  current_tilemap.mosaic_screen_enabled = VDP2_N1MZE;

  current_tilemap.layer_name = 1;

  if (current_tilemap.enabled) {
    current_tilemap.enabled = vdp2_check_vram_cycle_pattern_registers(
        VDP2_CP_NBG1_PNMDR, VDP2_CP_NBG1_CPDR, current_tilemap.bitmap_enable);
  }

  vdp2_check_tilemap(bitmap, cliprect);
}

void saturn_state::vdp2_draw_NBG2(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  /*
     NBG2 is the first of the 2 more basic tilemaps, it has exactly the same
     capabilities as NBG3

     Colours           : 16, 256
     Char Size         : 1x1 cells, 2x2 cells
     Pattern Data Size : 1 word, 2 words
     Plane Layouts     : 1 x 1, 2 x 1, 2 x 2
     Planes            : 4
     Bitmap            : No
     Bitmap Sizes      : N/A
     Scale             : No
     Rotation          : No
     Linescroll        : No
     Column Scroll     : No
     Mosaic            : Yes
  */

  current_tilemap.enabled = VDP2_N2ON;

  // ST-058 p.148: two rotation screens exclude the normal screens.
  if (VDP2_R0ON && VDP2_R1ON)
    current_tilemap.enabled = 0;

  // ST-058 Table 5.2: quarter reduction on NBG0, or half reduction
  // with 256 colors, consumes the resources otherwise used by NBG2.
  // This follows the configured reduction range, not the current increment.
  if (VDP2_N0ZMQT || (VDP2_N0ZMHF && VDP2_N0CHCN == 1))
    current_tilemap.enabled = 0;

  // ST-058 p.61: 2048-color and both RGB formats exclude NBG2.
  if (VDP2_N0CHCN == 0x02 || VDP2_N0CHCN == 0x03 || VDP2_N0CHCN == 0x04)
    current_tilemap.enabled = 0;

  //  if (!current_tilemap.enabled) return; // stop right now if its disabled
  //  ...

  // current_tilemap.trans_enabled = VDP2_N2TPON;
  current_tilemap.alpha = vdp2_cc_blend_level(VDP2_N2CCRT);
  if (VDP2_N2CCEN) {
    current_tilemap.colour_calculation_enabled = 1;

  } else {
    current_tilemap.colour_calculation_enabled = 0;
  }
  if (VDP2_N2TPON == 0) {
    current_tilemap.transparency = STV_TRANSPARENCY_PEN;
  } else {
    current_tilemap.transparency = STV_TRANSPARENCY_NONE;
  }
  current_tilemap.colour_depth = VDP2_N2CHCN;
  current_tilemap.tile_size = VDP2_N2CHSZ;
  /* this layer can't be a bitmap,so ignore these registers*/
  current_tilemap.bitmap_enable = 0;
  current_tilemap.bitmap_size = 0;
  current_tilemap.bitmap_palette_number = 0;
  current_tilemap.bitmap_map = 0;
  current_tilemap.map_offset[0] = VDP2_N2MPA | (VDP2_N2MP_ << 6);
  current_tilemap.map_offset[1] = VDP2_N2MPB | (VDP2_N2MP_ << 6);
  current_tilemap.map_offset[2] = VDP2_N2MPC | (VDP2_N2MP_ << 6);
  current_tilemap.map_offset[3] = VDP2_N2MPD | (VDP2_N2MP_ << 6);
  current_tilemap.map_count = 4;

  current_tilemap.pattern_data_size = VDP2_N2PNB;
  current_tilemap.character_number_supplement = VDP2_N2CNSM;
  current_tilemap.special_priority_register = VDP2_N2SPR;
  current_tilemap.special_colour_control_register = VDP2_N2SCC;
  current_tilemap.supplementary_palette_bits = VDP2_N2SPLT;
  current_tilemap.supplementary_character_bits = VDP2_N2SPCN;

  current_tilemap.scrollx = VDP2_SCXN2;
  current_tilemap.scrolly = VDP2_SCYN2;
  current_tilemap.scrollx_fraction = current_tilemap.scrolly_fraction = 0;
  /*This layer can't be scaled*/
  current_tilemap.incx = 0x10000;
  current_tilemap.incy = 0x10000;

  current_tilemap.linescroll_enable = 0;
  current_tilemap.linescroll_interval = 0;
  current_tilemap.linescroll_table_address = 0;
  current_tilemap.vertical_linescroll_enable = 0;
  current_tilemap.linezoom_enable = 0;
  current_tilemap.vertical_cell_scroll_enable = 0;

  current_tilemap.colour_ram_address_offset = VDP2_N2CAOS;
  current_tilemap.fade_control = (VDP2_N2COEN * 1) | (VDP2_N2COSL * 2);
  vdp2_check_fade_control_for_layer();
  current_tilemap.window_control.logic = VDP2_N2LOG;
  current_tilemap.window_control.enabled[0] = VDP2_N2W0E;
  current_tilemap.window_control.enabled[1] = VDP2_N2W1E;
  current_tilemap.window_control.sprite_window = VDP2_N2SWE ? 1 | (VDP2_N2SWA << 1) : 0;
  current_tilemap.window_control.area[0] = VDP2_N2W0A;
  current_tilemap.window_control.area[1] = VDP2_N2W1A;
  //  current_tilemap.window_control.? = VDP2_N2SWA;

  current_tilemap.line_screen_enabled = VDP2_N2LCEN;
  current_tilemap.mosaic_screen_enabled = VDP2_N2MZE;

  current_tilemap.layer_name = 2;

  current_tilemap.plane_size = VDP2_N2PLSZ;

  if (current_tilemap.enabled) {
    current_tilemap.enabled = vdp2_check_vram_cycle_pattern_registers(
        VDP2_CP_NBG2_PNMDR, VDP2_CP_NBG2_CPDR, current_tilemap.bitmap_enable);
  }

  vdp2_check_tilemap(bitmap, cliprect);
}

void saturn_state::vdp2_draw_NBG3(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  /*
     NBG3 is the second of the 2 more basic tilemaps, it has exactly the same
     capabilities as NBG2

     Colours           : 16, 256
     Char Size         : 1x1 cells, 2x2 cells
     Pattern Data Size : 1 word, 2 words
     Plane Layouts     : 1 x 1, 2 x 1, 2 x 2
     Planes            : 4
     Bitmap            : No
     Bitmap Sizes      : N/A
     Scale             : No
     Rotation          : No
     Linescroll        : No
     Column Scroll     : No
     Mosaic            : Yes
  */

  current_tilemap.enabled = VDP2_N3ON;

  // ST-058 p.148: two rotation screens exclude the normal screens.
  if (VDP2_R0ON && VDP2_R1ON)
    current_tilemap.enabled = 0;

  // The corresponding NBG1 reduction settings disable NBG3 (Table 5.2).
  if (VDP2_N1ZMQT || (VDP2_N1ZMHF && VDP2_N1CHCN == 1))
    current_tilemap.enabled = 0;

  //  if (!current_tilemap.enabled) return; // stop right now if its disabled
  //  ...

  // ST-058 p.61: RGB888 NBG0, or 2048-color/RGB555 NBG1, excludes NBG3.
  if (VDP2_N0CHCN == 0x04 || VDP2_N1CHCN == 0x02 || VDP2_N1CHCN == 0x03)
    current_tilemap.enabled = 0;

  // current_tilemap.trans_enabled = VDP2_N3TPON;
  current_tilemap.alpha = vdp2_cc_blend_level(VDP2_N3CCRT);
  if (VDP2_N3CCEN) {
    current_tilemap.colour_calculation_enabled = 1;

  } else {
    current_tilemap.colour_calculation_enabled = 0;
  }
  if (VDP2_N3TPON == 0) {
    current_tilemap.transparency = STV_TRANSPARENCY_PEN;
  } else {
    current_tilemap.transparency = STV_TRANSPARENCY_NONE;
  }
  current_tilemap.colour_depth = VDP2_N3CHCN;
  current_tilemap.tile_size = VDP2_N3CHSZ;
  /* this layer can't be a bitmap,so ignore these registers*/
  current_tilemap.bitmap_enable = 0;
  current_tilemap.bitmap_size = 0;
  current_tilemap.bitmap_palette_number = 0;
  current_tilemap.bitmap_map = 0;
  current_tilemap.map_offset[0] = VDP2_N3MPA | (VDP2_N3MP_ << 6);
  current_tilemap.map_offset[1] = VDP2_N3MPB | (VDP2_N3MP_ << 6);
  current_tilemap.map_offset[2] = VDP2_N3MPC | (VDP2_N3MP_ << 6);
  current_tilemap.map_offset[3] = VDP2_N3MPD | (VDP2_N3MP_ << 6);
  current_tilemap.map_count = 4;

  current_tilemap.pattern_data_size = VDP2_N3PNB;
  current_tilemap.character_number_supplement = VDP2_N3CNSM;
  current_tilemap.special_priority_register = VDP2_N3SPR;
  current_tilemap.special_colour_control_register = VDP2_N3SCC;
  current_tilemap.supplementary_palette_bits = VDP2_N3SPLT;
  current_tilemap.supplementary_character_bits = VDP2_N3SPCN;

  current_tilemap.scrollx = VDP2_SCXN3;
  current_tilemap.scrolly = VDP2_SCYN3;
  current_tilemap.scrollx_fraction = current_tilemap.scrolly_fraction = 0;
  /*This layer can't be scaled*/
  current_tilemap.incx = 0x10000;
  current_tilemap.incy = 0x10000;

  current_tilemap.linescroll_enable = 0;
  current_tilemap.linescroll_interval = 0;
  current_tilemap.linescroll_table_address = 0;
  current_tilemap.vertical_linescroll_enable = 0;
  current_tilemap.linezoom_enable = 0;
  current_tilemap.vertical_cell_scroll_enable = 0;

  current_tilemap.colour_ram_address_offset = VDP2_N3CAOS;
  current_tilemap.fade_control = (VDP2_N3COEN * 1) | (VDP2_N3COSL * 2);
  vdp2_check_fade_control_for_layer();
  current_tilemap.window_control.logic = VDP2_N3LOG;
  current_tilemap.window_control.enabled[0] = VDP2_N3W0E;
  current_tilemap.window_control.enabled[1] = VDP2_N3W1E;
  current_tilemap.window_control.sprite_window = VDP2_N3SWE ? 1 | (VDP2_N3SWA << 1) : 0;
  current_tilemap.window_control.area[0] = VDP2_N3W0A;
  current_tilemap.window_control.area[1] = VDP2_N3W1A;
  //  current_tilemap.window_control.? = VDP2_N3SWA;

  current_tilemap.line_screen_enabled = VDP2_N3LCEN;
  current_tilemap.mosaic_screen_enabled = VDP2_N3MZE;

  current_tilemap.layer_name = 3;

  current_tilemap.plane_size = VDP2_N3PLSZ;

  if (current_tilemap.enabled) {
    current_tilemap.enabled = vdp2_check_vram_cycle_pattern_registers(
        VDP2_CP_NBG3_PNMDR, VDP2_CP_NBG3_CPDR, current_tilemap.bitmap_enable);
  }

  vdp2_check_tilemap(bitmap, cliprect);
}

uint32_t saturn_state::vdp2_read_rotation_coefficient(uint32_t address) {
  /* with CRKTE set the rotation coefficient table is read from color RAM
     instead of VRAM: address bit 11 is forced and the 4 KiB of CRAM are wrapped
     around, so the table always lands in the upper half of CRAM (cfr. FIFA Road
     to World Cup 98) */
  if (VDP2_CRKTE)
    return m_vdp2_cram[((address | 0x800) & 0xfff) >> 2];

  unsigned const physical_mask = m_vdp2->get_vramsz() ? 0xfffff : 0x7ffff;
  address &= physical_mask;
  if (vdp2_per_dot_coefficients(VDP2_RAMCTL)) {
    unsigned bank = address >> (m_vdp2->get_vramsz() ? 18 : 17);
    if (!(VDP2_RAMCTL & (bank < 2 ? 0x100 : 0x200)))
      bank &= 2; // unpartitioned A/B use A0/B0's designation
    if (((VDP2_RAMCTL >> (bank * 2)) & 3) != 1)
      // Sega specifies a failed fetch, not its dot value. Use Ymir's
      // transparent fallback for this invalid setup; no bus-latch claim.
      return 0x80008000; // transparent in both short halves and long format
  }

  /* the address is built from the rotation parameters, whose kast/dkast are
     signed, so it can come out negative and wrap to a huge unsigned index;
     wrap it inside VRAM the same way the CRAM branch above wraps inside CRAM */
  return m_vdp2_vram[(address >> 2) & 0x3ffff];
}

void saturn_state::vdp2_draw_rotation_screen(bitmap_rgb32 &bitmap,
                                             const rectangle &cliprect,
                                             int iRP) {
  // A frame can contain different latched matrices/starts. Split only
  // output work; the untransformed source cache is shared across these rows.
  if (cliprect.top() < cliprect.bottom()) {
    bool latched = false;
    for (int y = std::max(0, cliprect.top()); y <= std::min(ROTATION_SCANLINES - 1, cliprect.bottom()); ++y)
      latched |= m_rotation_line_valid[y];
    if (latched) {
      for (int y = cliprect.top(); y <= cliprect.bottom(); ++y) {
        rectangle row = cliprect;
        row.sety(y, y);
        vdp2_draw_rotation_screen(bitmap, row, iRP);
      }
      return;
    }
  }

  if (iRP == 1) {
    current_tilemap.bitmap_map = VDP2_RAMP_;
    current_tilemap.map_offset[0] = VDP2_RAMPA | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[1] = VDP2_RAMPB | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[2] = VDP2_RAMPC | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[3] = VDP2_RAMPD | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[4] = VDP2_RAMPE | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[5] = VDP2_RAMPF | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[6] = VDP2_RAMPG | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[7] = VDP2_RAMPH | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[8] = VDP2_RAMPI | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[9] = VDP2_RAMPJ | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[10] = VDP2_RAMPK | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[11] = VDP2_RAMPL | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[12] = VDP2_RAMPM | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[13] = VDP2_RAMPN | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[14] = VDP2_RAMPO | (VDP2_RAMP_ << 6);
    current_tilemap.map_offset[15] = VDP2_RAMPP | (VDP2_RAMP_ << 6);
    current_tilemap.map_count = 16;
  } else {
    current_tilemap.bitmap_map = VDP2_RBMP_;
    current_tilemap.map_offset[0] = VDP2_RBMPA | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[1] = VDP2_RBMPB | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[2] = VDP2_RBMPC | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[3] = VDP2_RBMPD | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[4] = VDP2_RBMPE | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[5] = VDP2_RBMPF | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[6] = VDP2_RBMPG | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[7] = VDP2_RBMPH | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[8] = VDP2_RBMPI | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[9] = VDP2_RBMPJ | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[10] = VDP2_RBMPK | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[11] = VDP2_RBMPL | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[12] = VDP2_RBMPM | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[13] = VDP2_RBMPN | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[14] = VDP2_RBMPO | (VDP2_RBMP_ << 6);
    current_tilemap.map_offset[15] = VDP2_RBMPP | (VDP2_RBMP_ << 6);
    current_tilemap.map_count = 16;
  }

  vdp2_load_rotation_line(iRP, cliprect.top());
  current_tilemap.scrollx_fraction = current_tilemap.scrolly_fraction = 0;

  if (iRP == 1) {
    current_tilemap.plane_size = VDP2_RAPLSZ;
  } else {
    current_tilemap.plane_size = VDP2_RBPLSZ;
  }

  int planesizex = 0, planesizey = 0;
  if (current_tilemap.bitmap_enable) {
    switch (current_tilemap.bitmap_size) {
    case 0:
      planesizex = 512;
      planesizey = 256;
      break;
    case 1:
      planesizex = 512;
      planesizey = 512;
      break;
    case 2:
      planesizex = 1024;
      planesizey = 256;
      break;
    case 3:
      planesizex = 1024;
      planesizey = 512;
      break;
    }
  } else {
    switch (current_tilemap.plane_size) {
    case 0:
      planesizex = planesizey = 2048;
      break;
    case 1:
      planesizex = 4096;
      planesizey = 2048;
      break;
    case 2:
      planesizex = 0;
      planesizey = 0;
      break;
    case 3:
      planesizex = planesizey = 4096;
      break;
    }
  }

  // Special functions need dot attributes that the RGB-only source cache
  // cannot retain. Decode bounded output samples directly, including all 16
  // rotation maps, rather than rebuilding a full multi-megapixel cache.
  if (vdp2_special_priority_mode() ||
      (current_tilemap.colour_calculation_enabled && vdp2_special_color_mode())) {
    vdp2_copy_roz_bitmap(bitmap, m_vdp2_legacy.roz_bitmap[iRP - 1], cliprect,
        iRP, planesizex, planesizey, planesizex, planesizey);
    return;
  }

  if (!m_vdp2_composition_active && vdp2_is_rotation_applied(iRP) == 0) {
    current_tilemap.scrollx = current_rotation_table.mx >> 16;
    current_tilemap.scrolly = current_rotation_table.my >> 16;

    // Keep ordinary per-pixel window evaluation. A single clip rectangle
    // cannot represent outside areas, line windows or two-window logic.
    current_tilemap.window_control.logic = VDP2_R0LOG;
    current_tilemap.window_control.enabled[0] = VDP2_R0W0E;
    current_tilemap.window_control.enabled[1] = VDP2_R0W1E;
    current_tilemap.window_control.sprite_window = VDP2_R0SWE ? 1 | (VDP2_R0SWA << 1) : 0;
    current_tilemap.window_control.area[0] = VDP2_R0W0A;
    current_tilemap.window_control.area[1] = VDP2_R0W1A;
    //      current_tilemap.window_control.? = VDP2_R0SWA;

    vdp2_check_tilemap(bitmap, cliprect);
  } else {
    if (!m_vdp2_legacy.roz_bitmap[iRP - 1].valid())
      m_vdp2_legacy.roz_bitmap[iRP - 1].allocate(4096, 4096);

    rectangle roz_clip_rect;
    roz_clip_rect.min_x = roz_clip_rect.min_y = 0;
    int planerenderedsizex, planerenderedsizey;
    if ((iRP == 1 && VDP2_RAOVR == 3) || (iRP == 2 && VDP2_RBOVR == 3)) {
      roz_clip_rect.max_x = roz_clip_rect.max_y = 511;
      planerenderedsizex = planerenderedsizey = 512;
    } else if (vdp2_are_map_registers_equal() &&
               !current_tilemap.bitmap_enable) {
      roz_clip_rect.max_x = (planesizex / 4) - 1;
      roz_clip_rect.max_y = (planesizey / 4) - 1;
      planerenderedsizex = planesizex / 4;
      planerenderedsizey = planesizey / 4;
    } else {
      roz_clip_rect.max_x = planesizex - 1;
      roz_clip_rect.max_y = planesizey - 1;
      planerenderedsizex = planesizex;
      planerenderedsizey = planesizey;
    }

    uint8_t const colour_calculation_enabled =
        current_tilemap.colour_calculation_enabled;
    current_tilemap.colour_calculation_enabled = 0;
    // The cached source is unblended. Select the final operation only when
    // copying it to the output, rather than retaining a previous pass's flags.
    current_tilemap.transparency &= ~(STV_TRANSPARENCY_ALPHA | STV_TRANSPARENCY_ADD_BLEND);
    //      window_control = current_tilemap.window_control;
    //      current_tilemap.window_control = 0;
    uint8_t const fade_control = current_tilemap.fade_control;
    current_tilemap.fade_control = 0;
    {
      auto profile1 = g_profiler.start(PROFILER_USER1);
      LOGMASKED(
          LOG_VDP2,
          "Checking for cached RBG bitmap, cache_dirty = %d, memcmp() = %d\n",
          RBG0_cache_data.is_cache_dirty,
          memcmp(&RBG0_cache_data.layer_data[iRP - 1], &current_tilemap,
                 sizeof(current_tilemap)));
      if ((RBG0_cache_data.is_cache_dirty & iRP) ||
          RBG0_cache_data.vram_size[iRP - 1] != m_vdp2->get_vramsz() ||
          memcmp(&RBG0_cache_data.layer_data[iRP - 1], &current_tilemap,
                 sizeof(current_tilemap)) != 0) {
        m_vdp2_legacy.roz_bitmap[iRP - 1].fill(rgb_t::transparent(),
                                               roz_clip_rect);
        vdp2_check_tilemap(m_vdp2_legacy.roz_bitmap[iRP - 1], roz_clip_rect);
        // prepare cache data
        RBG0_cache_data.watch_vdp2_vram_writes |= iRP;
        RBG0_cache_data.is_cache_dirty &= ~iRP;
        RBG0_cache_data.vram_size[iRP - 1] = m_vdp2->get_vramsz();
        memcpy(&RBG0_cache_data.layer_data[iRP - 1], &current_tilemap,
               sizeof(current_tilemap));
        RBG0_cache_data.map_offset_min[iRP - 1] =
            vdp2_layer_data.map_offset_min;
        RBG0_cache_data.map_offset_max[iRP - 1] =
            vdp2_layer_data.map_offset_max;
        RBG0_cache_data.tile_offset_min[iRP - 1] =
            vdp2_layer_data.tile_offset_min;
        RBG0_cache_data.tile_offset_max[iRP - 1] =
            vdp2_layer_data.tile_offset_max;
        LOGMASKED(LOG_VDP2,
                  "Cache watch: map = %06X - %06X, tile = %06X - %06X\n",
                  RBG0_cache_data.map_offset_min[iRP - 1],
                  RBG0_cache_data.map_offset_max[iRP - 1],
                  RBG0_cache_data.tile_offset_min[iRP - 1],
                  RBG0_cache_data.tile_offset_max[iRP - 1]);
      }
      // stop profiling USER1
    }

    current_tilemap.colour_calculation_enabled = colour_calculation_enabled;
    // vdp2_copy_roz_bitmap selects ratio or additive calculation from CCMD.

#if 0
		// old reference code
		mycliprect = cliprect;

		if ( current_tilemap.window_control.enabled[0] || current_tilemap.window_control.enabled[1] )
		{
			//popmessage("Window control for RBG");
			vdp2_apply_window_on_layer(mycliprect);
			current_tilemap.window_control.enabled[0] = 0;
			current_tilemap.window_control.enabled[1] = 0;
		}
#endif

    current_tilemap.fade_control = fade_control;

    auto profile2 = g_profiler.start(PROFILER_USER2);
    vdp2_copy_roz_bitmap(bitmap, m_vdp2_legacy.roz_bitmap[iRP - 1], cliprect,
                         iRP, planesizex, planesizey, planerenderedsizex,
                         planerenderedsizey);
  }
}

void saturn_state::vdp2_draw_RBG0(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  /*
     Colours           : 16, 256, 2048, 32768, 16770000
     Char Size         : 1x1 cells, 2x2 cells
     Pattern Data Size : 1 word, 2 words
     Plane Layouts     : 1 x 1, 2 x 1, 2 x 2
     Planes            : 4
     Bitmap            : Possible
     Bitmap Sizes      : 512 x 256, 512 x 512, 1024 x 256, 1024 x 512
     Scale             : 0.25 x - 256 x
     Rotation          : Yes
     Linescroll        : Yes
     Column Scroll     : Yes
     Mosaic            : Yes
  */

  current_tilemap.enabled = VDP2_R0ON;

  //  if (!current_tilemap.enabled) return; // stop right now if its disabled
  //  ...

  // current_tilemap.trans_enabled = VDP2_R0TPON;
  current_tilemap.alpha = vdp2_cc_blend_level(VDP2_R0CCRT);
  if (VDP2_R0CCEN) {
    current_tilemap.colour_calculation_enabled = 1;

  } else {
    current_tilemap.colour_calculation_enabled = 0;
  }
  if (VDP2_R0TPON == 0) {
    current_tilemap.transparency = STV_TRANSPARENCY_PEN;
  } else {
    current_tilemap.transparency = STV_TRANSPARENCY_NONE;
  }
  current_tilemap.colour_depth = VDP2_R0CHCN;
  current_tilemap.tile_size = VDP2_R0CHSZ;
  current_tilemap.bitmap_enable = VDP2_R0BMEN;
  current_tilemap.bitmap_size = VDP2_R0BMSZ;
  current_tilemap.bitmap_palette_number = VDP2_R0BMP;

  current_tilemap.pattern_data_size = VDP2_R0PNB;
  current_tilemap.character_number_supplement = VDP2_R0CNSM;
  current_tilemap.special_priority_register = VDP2_R0SPR;
  current_tilemap.special_colour_control_register = VDP2_R0SCC;
  current_tilemap.supplementary_palette_bits = VDP2_R0SPLT;
  current_tilemap.supplementary_character_bits = VDP2_R0SPCN;

  current_tilemap.colour_ram_address_offset = VDP2_R0CAOS;
  current_tilemap.fade_control = (VDP2_R0COEN * 1) | (VDP2_R0COSL * 2);
  vdp2_check_fade_control_for_layer();
  // disable these, we apply them in the roz routines (they were interfering
  // with vdp2_roz_window() ?)
  current_tilemap.window_control.logic = 0;      // VDP2_R0LOG;
  current_tilemap.window_control.enabled[0] = 0; // VDP2_R0W0E;
  current_tilemap.window_control.enabled[1] = 0; // VDP2_R0W1E;
  current_tilemap.window_control.sprite_window = 0;
  current_tilemap.window_control.area[0] = 0; // VDP2_R0W0A;
  current_tilemap.window_control.area[1] = 0; // VDP2_R0W1A;
  //  current_tilemap.window_control.? = VDP2_R0SWA;

  current_tilemap.scrollx = 0;
  current_tilemap.scrolly = 0;
  current_tilemap.incx = 0x10000;
  current_tilemap.incy = 0x10000;

  current_tilemap.linescroll_enable = 0;
  current_tilemap.linescroll_interval = 0;
  current_tilemap.linescroll_table_address = 0;
  current_tilemap.vertical_linescroll_enable = 0;
  current_tilemap.linezoom_enable = 0;
  current_tilemap.vertical_cell_scroll_enable = 0;

  current_tilemap.line_screen_enabled = VDP2_R0LCEN;
  current_tilemap.mosaic_screen_enabled = VDP2_R0MZE;

  /*Use 0x80 as a normal/rotate switch*/
  current_tilemap.layer_name = 0x80;

  if (!current_tilemap.enabled)
    return;

  switch (VDP2_RPMD) {
  case 0: // Rotation Parameter A
    current_tilemap.roz_mode3 = false;
    vdp2_draw_rotation_screen(bitmap, cliprect, 1);
    break;
  case 1: // Rotation Parameter B
    // case 2:
    current_tilemap.roz_mode3 = false;
    vdp2_draw_rotation_screen(bitmap, cliprect, 2);
    break;
  case 2: // Rotation Parameter A & B CKTE
    current_tilemap.roz_mode3 = false;
    vdp2_draw_rotation_screen(bitmap, cliprect, 2);
    vdp2_draw_rotation_screen(bitmap, cliprect, 1);
    break;
  case 3: // Rotation Parameter A & B Window
    current_tilemap.roz_mode3 = true;
    vdp2_draw_rotation_screen(bitmap, cliprect, 2);
    vdp2_draw_rotation_screen(bitmap, cliprect, 1);
    break;
  }
}

rgb_t saturn_state::vdp2_back_screen_color(uint8_t const *gfxdata,
                                           uint32_t base_offs) {
  uint16_t const dot = (gfxdata[base_offs + 0] << 8) | gfxdata[base_offs + 1];
  int b = pal5bit((dot & 0x7c00) >> 10);
  int g = pal5bit((dot & 0x03e0) >> 5);
  int r = pal5bit(dot & 0x001f);
  if (VDP2_BKCOEN && (!m_vdp2->get_disp() || (!(VDP2_CCCR & 0x5f) && !(VDP2_SDCTL & 0x3f))))
    vdp2_compute_color_offset(&r, &g, &b, VDP2_BKCOSL);

  return rgb_t(r, g, b);
}

void saturn_state::vdp2_draw_back(bitmap_rgb32 &bitmap,
                                  const rectangle &cliprect) {
  uint8_t const *const gfxdata = m_vdp2_legacy.gfx_decode.get();

  uint8_t interlace = (m_vdp2->get_lsmd() == 3) + 1;

  //  popmessage("Back screen %08x %08x
  //  %08x",m_vdp2->get_bdclmd(),VDP2_BKCLMD,VDP2_BKTA);

  /* draw black if BDCLMD and DISP are cleared */
  if (!(m_vdp2->get_bdclmd()) && !(m_vdp2->get_disp()))
    bitmap.fill(m_palette->black_pen(), cliprect);
  else {
    uint32_t base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;
    uint32_t base_offs = ((VDP2_BKTA)&base_mask) << 1;

    /* the back screen is either a single colour or one colour per line, so
       decode (and apply the colour offset to) each dot only once */
    if (!VDP2_BKCLMD) {
      bitmap.fill(vdp2_back_screen_color(gfxdata, base_offs), cliprect);
    } else {
      for (int y = cliprect.top(); y <= cliprect.bottom(); y++) {
        // ST-058 p.177: the high address bit is ignored in 4-Mbit mode.
        // Wrap the complete row address, not just the initial BKTA value.
        rgb_t const color = vdp2_back_screen_color(
            gfxdata, (base_offs + ((y / interlace) << 1)) & ((base_mask << 1) | 1));

        for (int x = cliprect.left(); x <= cliprect.right(); x++)
          bitmap.pix(y, x) = color;
      }
    }
  }
}

uint32_t saturn_state::vdp2_vram_r(offs_t offset) {
  return m_vdp2_vram[offset];
}

void saturn_state::vdp2_vram_w(offs_t offset, uint32_t data,
                               uint32_t mem_mask) {
  uint8_t *gfxdata = m_vdp2_legacy.gfx_decode.get();

  if ((m_vdp2_vram[offset] ^ data) & mem_mask)
    m_vdp2->preserve_scanned_output();
  COMBINE_DATA(&m_vdp2_vram[offset]);

  data = m_vdp2_vram[offset];
  /* put in gfx region for easy decoding */
  gfxdata[offset * 4 + 0] = (data & 0xff000000) >> 24;
  gfxdata[offset * 4 + 1] = (data & 0x00ff0000) >> 16;
  gfxdata[offset * 4 + 2] = (data & 0x0000ff00) >> 8;
  gfxdata[offset * 4 + 3] = (data & 0x000000ff) >> 0;

  m_gfxdecode->gfx(0)->mark_dirty(offset / 8);
  m_gfxdecode->gfx(1)->mark_dirty(offset / 8);
  m_gfxdecode->gfx(2)->mark_dirty(offset / 8);
  m_gfxdecode->gfx(3)->mark_dirty(offset / 8);

  /* 8-bit tiles overlap, so this affects the previous one as well */
  if (offset / 8 != 0) {
    m_gfxdecode->gfx(2)->mark_dirty(offset / 8 - 1);
    m_gfxdecode->gfx(3)->mark_dirty(offset / 8 - 1);
  }

  if (RBG0_cache_data.watch_vdp2_vram_writes) {
    if (RBG0_cache_data.watch_vdp2_vram_writes &
        VDP2_RBG_ROTATION_PARAMETER_A) {
      if ((offset >= RBG0_cache_data.map_offset_min[0] &&
           offset < RBG0_cache_data.map_offset_max[0]) ||
          (offset >= RBG0_cache_data.tile_offset_min[0] &&
           offset < RBG0_cache_data.tile_offset_max[0])) {
        LOGMASKED(LOG_VDP2,
                  "RBG Cache: dirtying for RP = 1, write at offset = %06X\n",
                  offset);
        RBG0_cache_data.is_cache_dirty |= VDP2_RBG_ROTATION_PARAMETER_A;
        RBG0_cache_data.watch_vdp2_vram_writes &=
            ~VDP2_RBG_ROTATION_PARAMETER_A;
      }
    }
    if (RBG0_cache_data.watch_vdp2_vram_writes &
        VDP2_RBG_ROTATION_PARAMETER_B) {
      if ((offset >= RBG0_cache_data.map_offset_min[1] &&
           offset < RBG0_cache_data.map_offset_max[1]) ||
          (offset >= RBG0_cache_data.tile_offset_min[1] &&
           offset < RBG0_cache_data.tile_offset_max[1])) {
        LOGMASKED(LOG_VDP2,
                  "RBG Cache: dirtying for RP = 2, write at offset = %06X\n",
                  offset);
        RBG0_cache_data.is_cache_dirty |= VDP2_RBG_ROTATION_PARAMETER_B;
        RBG0_cache_data.watch_vdp2_vram_writes &=
            ~VDP2_RBG_ROTATION_PARAMETER_B;
      }
    }
  }
}

uint16_t saturn_state::vdp2_regs_r(offs_t offset) {
  // the register file is 0x200 bytes and repeats across the whole 4MB window
  offset &= 0xff;

  return m_vdp2_regs[offset];
}

// Mode 0 broadcasts writes, not reads: mode changes can leave the two
// physical halves different until the guest writes the corresponding words.
uint32_t saturn_state::vdp2_cram_r(offs_t offset) {
  offset &= (0xfff) >> (2);
  if (VDP2_CRMD & 2) {
    // Physical CRAM is two 1K-word banks. In 24-bit mode address bit 1
    // selects the bank instead of bit 11 (MiSTer IO_PAL_RD/IO_PAL_A;
    // Ymir MapCRAMAddress). Keep storage in mode-1 physical-bank order.
    const unsigned shift = (offset & 1) ? 0 : 16;
    return ((m_vdp2_cram[offset >> 1] >> shift) & 0xffff) << 16 |
           ((m_vdp2_cram[(offset >> 1) | 0x200] >> shift) & 0xffff);
  }
  return m_vdp2_cram[offset];
}

// TODO: byte writes are goofy
void saturn_state::vdp2_cram_w(offs_t offset, uint32_t data,
                               uint32_t mem_mask) {
  if (!mem_mask)
    return;

  int r, g, b;
  uint8_t cmode0;

  cmode0 = (VDP2_CRMD & 3) == 0;

  offset &= (0xfff) >> (2);
  if (((vdp2_cram_r(offset) ^ data) & mem_mask) ||
      (cmode0 && ((vdp2_cram_r(offset ^ 0x200) ^ data) & mem_mask)))
    m_vdp2->preserve_scanned_output();
  if (VDP2_CRMD & 2) {
    const unsigned shift = (offset & 1) ? 0 : 16;
    auto &bank0 = m_vdp2_cram[offset >> 1];
    auto &bank1 = m_vdp2_cram[(offset >> 1) | 0x200];
    const uint32_t mask0 = (mem_mask >> 16) << shift;
    const uint32_t mask1 = (mem_mask & 0xffff) << shift;
    bank0 = (bank0 & ~mask0) | (((data >> 16) << shift) & mask0);
    bank1 = (bank1 & ~mask1) | (((data & 0xffff) << shift) & mask1);
  } else {
    COMBINE_DATA(&m_vdp2_cram[offset]);
  }
  // ST-058 section 3.4: mode-0 writes reach both 1K-word halves.
  // Ymir WriteCRAM and MiSTer IO_PAL0/1_WE also broadcast upper-half
  // accesses. Merge each half separately: unwritten lanes may differ after
  // a mode change, and must not be copied from the addressed half.
  if (cmode0)
    COMBINE_DATA(&m_vdp2_cram[offset ^ 0x200]);

  mark_fade_effects_dirty();

  switch (VDP2_CRMD) {
  /*Mode 2/3*/
  case 2:
  case 3: {
    // offset &= (0xfff) >> 2;

    const uint32_t color = vdp2_cram_r(offset);
    b = (color >> 16) & 0xff;
    g = (color >> 8) & 0xff;
    r = color & 0xff;
    m_palette->set_pen_color(offset, rgb_t(r, g, b));
    m_palette->set_pen_color(offset ^ 0x400, rgb_t(r, g, b));
  } break;
  /*Mode 0*/
  case 0:
  case 1: {
    offset &= (0xfff) >> (cmode0 + 2);

    b = ((m_vdp2_cram[offset] & 0x00007c00) >> 10);
    g = ((m_vdp2_cram[offset] & 0x000003e0) >> 5);
    r = ((m_vdp2_cram[offset] & 0x0000001f) >> 0);
    m_palette->set_pen_color((offset * 2) + 1, pal5bit(r), pal5bit(g),
                             pal5bit(b));
    if (cmode0)
      m_palette->set_pen_color(((offset * 2) + 1) ^ 0x400, pal5bit(r),
                               pal5bit(g), pal5bit(b));

    b = ((m_vdp2_cram[offset] & 0x7c000000) >> 26);
    g = ((m_vdp2_cram[offset] & 0x03e00000) >> 21);
    r = ((m_vdp2_cram[offset] & 0x001f0000) >> 16);
    m_palette->set_pen_color(offset * 2, pal5bit(r), pal5bit(g), pal5bit(b));
    if (cmode0)
      m_palette->set_pen_color((offset * 2) ^ 0x400, pal5bit(r), pal5bit(g),
                               pal5bit(b));
  } break;
  }
}

void saturn_state::refresh_palette_data() {
  int r, g, b;
  int c_i;

  // the faded copies are derived from these pens
  mark_fade_effects_dirty();

  switch (VDP2_CRMD) {
  case 2:
  case 3: {
    for (c_i = 0; c_i < 0x400; c_i++) {
      const uint32_t color = vdp2_cram_r(c_i);
      b = (color >> 16) & 0xff;
      g = (color >> 8) & 0xff;
      r = color & 0xff;
      m_palette->set_pen_color(c_i, rgb_t(r, g, b));
      m_palette->set_pen_color(c_i + 0x400, rgb_t(r, g, b));
    }
  } break;
  case 0: {
    /* mode 0 holds 1024 colours and the most significant bit of the color
       RAM address is ignored, so the upper half mirrors the lower half */
    for (c_i = 0; c_i < 0x200; c_i++) {
      b = ((m_vdp2_cram[c_i] & 0x00007c00) >> 10);
      g = ((m_vdp2_cram[c_i] & 0x000003e0) >> 5);
      r = ((m_vdp2_cram[c_i] & 0x0000001f) >> 0);
      m_palette->set_pen_color((c_i * 2) + 1, pal5bit(r), pal5bit(g),
                               pal5bit(b));
      m_palette->set_pen_color(((c_i * 2) + 1) ^ 0x400, pal5bit(r), pal5bit(g),
                               pal5bit(b));
      b = ((m_vdp2_cram[c_i] & 0x7c000000) >> 26);
      g = ((m_vdp2_cram[c_i] & 0x03e00000) >> 21);
      r = ((m_vdp2_cram[c_i] & 0x001f0000) >> 16);
      m_palette->set_pen_color(c_i * 2, pal5bit(r), pal5bit(g), pal5bit(b));
      m_palette->set_pen_color((c_i * 2) ^ 0x400, pal5bit(r), pal5bit(g),
                               pal5bit(b));
    }
  } break;
  case 1: {
    /* mode 1 holds the full 2048 colours */
    for (c_i = 0; c_i < 0x400; c_i++) {
      b = ((m_vdp2_cram[c_i] & 0x00007c00) >> 10);
      g = ((m_vdp2_cram[c_i] & 0x000003e0) >> 5);
      r = ((m_vdp2_cram[c_i] & 0x0000001f) >> 0);
      m_palette->set_pen_color((c_i * 2) + 1, pal5bit(r), pal5bit(g),
                               pal5bit(b));
      b = ((m_vdp2_cram[c_i] & 0x7c000000) >> 26);
      g = ((m_vdp2_cram[c_i] & 0x03e00000) >> 21);
      r = ((m_vdp2_cram[c_i] & 0x001f0000) >> 16);
      m_palette->set_pen_color(c_i * 2, pal5bit(r), pal5bit(g), pal5bit(b));
    }
  } break;
  }
}

void saturn_state::vdp2_regs_w(offs_t offset, uint16_t data,
                               uint16_t mem_mask) {
  // as above, the 4MB window mirrors the 0x200 byte register file
  offset &= 0xff;

  // RAMCTL through color-offset registers affect rendering. Device-owned
  // TVMD/VRSIZE handlers preserve their old decoded state separately.
  if (offset >= 0x00e / 2 && offset <= 0x11e / 2 && ((m_vdp2_regs[offset] ^ data) & mem_mask))
    m_vdp2->preserve_scanned_output();
  COMBINE_DATA(&m_vdp2_regs[offset]);

  // window coordinates may have changed
  vdp2_window_cache_invalidate();

  // COAR/COAG/COAB/COBR/COBG/COBB feed the fade tables
  if ((offset >= 0x114 / 2) && (offset <= 0x11e / 2))
    mark_fade_effects_dirty();

  if (m_vdp2_legacy.old_crmd != VDP2_CRMD) {
    m_vdp2_legacy.old_crmd = VDP2_CRMD;
    refresh_palette_data();
  }
}

void saturn_state::vdp2_state_save_postload() {
  // These flags select in-progress rendering, not emulated hardware state.
  // In particular, capture bypasses the ordinary compositor even when the
  // composition-active flag is false. Never retain it across a state load.
  m_vdp2_composition_active = false;
  m_vdp2_extended_active = false;
  m_vdp2_gradation_active = false;
  m_vdp2_gradation_capture = false;
  m_vdp2_gradation_layer = 7;
  m_vdp2_priority_pass = -1;
  vdp2_window_cache_invalidate();
  uint8_t *gfxdata = m_vdp2_legacy.gfx_decode.get();
  int offset;
  uint32_t data;

  for (offset = 0; offset < 0x100000 / 4; offset++) {
    data = m_vdp2_vram[offset];
    /* put in gfx region for easy decoding */
    gfxdata[offset * 4 + 0] = (data & 0xff000000) >> 24;
    gfxdata[offset * 4 + 1] = (data & 0x00ff0000) >> 16;
    gfxdata[offset * 4 + 2] = (data & 0x0000ff00) >> 8;
    gfxdata[offset * 4 + 3] = (data & 0x000000ff) >> 0;

    m_gfxdecode->gfx(0)->mark_dirty(offset / 8);
    m_gfxdecode->gfx(1)->mark_dirty(offset / 8);
    m_gfxdecode->gfx(2)->mark_dirty(offset / 8);
    m_gfxdecode->gfx(3)->mark_dirty(offset / 8);

    /* 8-bit tiles overlap, so this affects the previous one as well */
    if (offset / 8 != 0) {
      m_gfxdecode->gfx(2)->mark_dirty(offset / 8 - 1);
      m_gfxdecode->gfx(3)->mark_dirty(offset / 8 - 1);
    }
  }

  RBG0_cache_data = _RBG0_cache_data();
  RBG0_cache_data.is_cache_dirty = 3;
  vdp2_layer_data = _vdp2_layer_data();

  refresh_palette_data();
}

void saturn_state::vdp2_exit() {
  m_vdp2_legacy.roz_bitmap[0].reset();
  m_vdp2_legacy.roz_bitmap[1].reset();
}

int saturn_state::vdp2_start() {
  machine().add_notifier(
      MACHINE_NOTIFY_EXIT,
      machine_notify_delegate(&saturn_state::vdp2_exit, this));

  /* the VDP2 register file is 0x200 bytes and colour RAM is 4 KiB, each
     mirrored across a much larger address window, so vdp2_regs_r/w() and
     vdp2_cram_r/w() mask the offset down to the real size before indexing
     (& 0xff and & 0x3ff words respectively).  These were allocated to cover
     the whole window instead - 256 KiB and 512 KiB, of which only 0x100 and
     0x400 words were reachable - and the unreachable part was zeroed at every
     reset and carried in every save state.  Size them to what the hardware
     has, as m_vdp1_regs and m_vdp2_vram already are. */
  m_vdp2_regs = make_unique_clear<uint16_t[]>(0x000200 / 2);
  m_vdp2_vram = make_unique_clear<uint32_t[]>(0x100000 / 4);
  m_vdp2_cram = make_unique_clear<uint32_t[]>(0x001000 / 4);
  m_vdp2_legacy.gfx_decode = std::make_unique<uint8_t[]>(0x100000);

  //  m_gfxdecode->gfx(0)->granularity()=4;
  //  m_gfxdecode->gfx(1)->granularity()=4;

  RBG0_cache_data = _RBG0_cache_data();
  RBG0_cache_data.is_cache_dirty = 3;
  vdp2_layer_data = _vdp2_layer_data();

  save_pointer(NAME(m_vdp2_regs), 0x000200 / 2);
  save_pointer(NAME(m_vdp2_vram), 0x100000 / 4);
  save_pointer(NAME(m_vdp2_cram), 0x001000 / 4);
  save_item(STRUCT_MEMBER(m_rotation_lines, xst));
  save_item(STRUCT_MEMBER(m_rotation_lines, yst));
  save_item(STRUCT_MEMBER(m_rotation_lines, zst));
  save_item(STRUCT_MEMBER(m_rotation_lines, dxst));
  save_item(STRUCT_MEMBER(m_rotation_lines, dyst));
  save_item(STRUCT_MEMBER(m_rotation_lines, dx));
  save_item(STRUCT_MEMBER(m_rotation_lines, dy));
  save_item(STRUCT_MEMBER(m_rotation_lines, A));
  save_item(STRUCT_MEMBER(m_rotation_lines, B));
  save_item(STRUCT_MEMBER(m_rotation_lines, C));
  save_item(STRUCT_MEMBER(m_rotation_lines, D));
  save_item(STRUCT_MEMBER(m_rotation_lines, E));
  save_item(STRUCT_MEMBER(m_rotation_lines, F));
  save_item(STRUCT_MEMBER(m_rotation_lines, px));
  save_item(STRUCT_MEMBER(m_rotation_lines, py));
  save_item(STRUCT_MEMBER(m_rotation_lines, pz));
  save_item(STRUCT_MEMBER(m_rotation_lines, cx));
  save_item(STRUCT_MEMBER(m_rotation_lines, cy));
  save_item(STRUCT_MEMBER(m_rotation_lines, cz));
  save_item(STRUCT_MEMBER(m_rotation_lines, mx));
  save_item(STRUCT_MEMBER(m_rotation_lines, my));
  save_item(STRUCT_MEMBER(m_rotation_lines, kx));
  save_item(STRUCT_MEMBER(m_rotation_lines, ky));
  save_item(STRUCT_MEMBER(m_rotation_lines, kast));
  save_item(STRUCT_MEMBER(m_rotation_lines, dkast));
  save_item(STRUCT_MEMBER(m_rotation_lines, dkax));
  save_item(NAME(m_rotation_line_valid));
  save_item(NAME(m_rotation_latch_valid));
  save_item(NAME(m_rotation_x));
  save_item(NAME(m_rotation_y));
  save_item(NAME(m_rotation_k));
  machine().save().register_postload(save_prepost_delegate(
      FUNC(saturn_state::vdp2_state_save_postload), this));

  return 0;
}

/* maybe we should move this to video/stv.c */
VIDEO_START_MEMBER(saturn_state, vdp2_video_start) {
  m_screen->register_screen_bitmap(m_tmpbitmap);
  vdp2_start();
  vdp1_start();
  m_vdpdebug_roz = 0;
  m_gfxdecode->gfx(0)->set_source(m_vdp2_legacy.gfx_decode.get());
  m_gfxdecode->gfx(1)->set_source(m_vdp2_legacy.gfx_decode.get());
  m_gfxdecode->gfx(2)->set_source(m_vdp2_legacy.gfx_decode.get());
  m_gfxdecode->gfx(3)->set_source(m_vdp2_legacy.gfx_decode.get());
}

/*This is for calculating the rgb brightness*/
/*TODO: Optimize this...*/
void saturn_state::vdp2_fade_effects() {
  /*
  Note:We have to use temporary storages because palette_get_color must use
  variables setted with unsigned int8
  */
  int16_t t_r, t_g, t_b;
  uint8_t r, g, b;
  rgb_t color;
  int i;

  // nothing to do unless CRAM or the color offset registers changed since
  // the last rebuild
  if (!m_fade_effects_dirty)
    return;

  // popmessage("%04x %04x",VDP2_CLOFEN,VDP2_CLOFSL);
  for (i = 0; i < 2048; i++) {
    /*Fade A*/
    color = m_palette->pen_color(i);
    t_r = (VDP2_COAR & 0x100) ? (color.r() - (0x100 - (VDP2_COAR & 0xff)))
                              : ((VDP2_COAR & 0xff) + color.r());
    t_g = (VDP2_COAG & 0x100) ? (color.g() - (0x100 - (VDP2_COAG & 0xff)))
                              : ((VDP2_COAG & 0xff) + color.g());
    t_b = (VDP2_COAB & 0x100) ? (color.b() - (0x100 - (VDP2_COAB & 0xff)))
                              : ((VDP2_COAB & 0xff) + color.b());
    if (t_r < 0) {
      t_r = 0;
    }
    if (t_r > 0xff) {
      t_r = 0xff;
    }
    if (t_g < 0) {
      t_g = 0;
    }
    if (t_g > 0xff) {
      t_g = 0xff;
    }
    if (t_b < 0) {
      t_b = 0;
    }
    if (t_b > 0xff) {
      t_b = 0xff;
    }
    r = t_r;
    g = t_g;
    b = t_b;
    m_palette->set_pen_color(i + (2048 * 1), rgb_t(r, g, b));

    /*Fade B*/
    color = m_palette->pen_color(i);
    t_r = (VDP2_COBR & 0x100) ? (color.r() - (0x100 - (VDP2_COBR & 0xff)))
                              : ((VDP2_COBR & 0xff) + color.r());
    t_g = (VDP2_COBG & 0x100) ? (color.g() - (0x100 - (VDP2_COBG & 0xff)))
                              : ((VDP2_COBG & 0xff) + color.g());
    t_b = (VDP2_COBB & 0x100) ? (color.b() - (0x100 - (VDP2_COBB & 0xff)))
                              : ((VDP2_COBB & 0xff) + color.b());
    if (t_r < 0) {
      t_r = 0;
    }
    if (t_r > 0xff) {
      t_r = 0xff;
    }
    if (t_g < 0) {
      t_g = 0;
    }
    if (t_g > 0xff) {
      t_g = 0xff;
    }
    if (t_b < 0) {
      t_b = 0;
    }
    if (t_b > 0xff) {
      t_b = 0xff;
    }
    r = t_r;
    g = t_g;
    b = t_b;
    m_palette->set_pen_color(i + (2048 * 2), rgb_t(r, g, b));
  }

  m_fade_effects_dirty = false;
  // popmessage("%04x %04x %04x %04x %04x
  // %04x",VDP2_COAR,VDP2_COAG,VDP2_COAB,VDP2_COBR,VDP2_COBG,VDP2_COBB);
}

// Window X coordinates are handled as signed 16 bit values: several games
// program out of range parameters and expect them to work (the Panzer
// Dragoon II Zwei and Panzer Dragoon Saga line window tables, Radiant
// Silvergun, Snatcher). A negative end point leaves the window empty, a
// negative start point is clamped to the left edge.
static void fixup_window_x(int *s_x, int *e_x) {
  if (*s_x < 0)
    *s_x = 0;

  if (*e_x < 0) {
    if (*s_x >= *e_x)
      *s_x = 0x3ff;
    *e_x = 0;
  }
}

void saturn_state::vdp2_get_window0_coordinates(int *s_x, int *e_x, int *s_y,
                                                int *e_y, int y) {
  /*W0*/
  switch (m_vdp2->get_lsmd()) {
  case 0:
  case 1:
  case 2:
    *s_y = ((VDP2_W0SY & 0x3ff) >> 0);
    *e_y = ((VDP2_W0EY & 0x3ff) >> 0);
    break;
  case 3:
    *s_y = ((VDP2_W0SY & 0x7ff) >> 0);
    *e_y = ((VDP2_W0EY & 0x7ff) >> 0);
    break;
  }

  int raw_s_x, raw_e_x;

  // check if line window is enabled
  if (VDP2_W0LWE) {
    uint32_t base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;
    uint32_t address = (VDP2_W0LWTA & base_mask) * 2;
    // double density makes the line window to fetch data every two lines
    uint8_t interlace = (m_vdp2->get_lsmd() == 3);
    // Apply the physical-size mask after adding the row offset. Masking
    // only LWTA lets a 512 KiB table spill into the unused upper half.
    // ST-058 pp.186-187: the high address bit is ignored in 4-Mbit mode.
    uint32_t vram_data =
        m_vdp2_vram[((address >> 2) + (y >> interlace)) & (base_mask >> 1)];

    raw_s_x = (int16_t)(vram_data >> 16);
    raw_e_x = (int16_t)(vram_data & 0xffff);
  } else {
    raw_s_x = (int16_t)VDP2_WPSX0;
    raw_e_x = (int16_t)VDP2_WPEX0;
  }

  fixup_window_x(&raw_s_x, &raw_e_x);

  // the line window table holds coordinates in the same format as WPSX/WPEX
  switch (m_vdp2->get_hreso() & 6) {
  /*Normal*/
  case 0:
    *s_x = ((raw_s_x & 0x3fe) >> 1);
    *e_x = ((raw_e_x & 0x3fe) >> 1);
    break;
  /*Hi-Res*/
  case 2:
    *s_x = ((raw_s_x & 0x3ff) >> 0);
    *e_x = ((raw_e_x & 0x3ff) >> 0);
    break;
  /*Exclusive Normal*/
  case 4:
    *s_x = ((raw_s_x & 0x1ff) >> 0);
    *e_x = ((raw_e_x & 0x1ff) >> 0);
    *s_y = ((VDP2_W0SY & 0x3ff) >> 0);
    *e_y = ((VDP2_W0EY & 0x3ff) >> 0);
    break;
  /*Exclusive Hi-Res*/
  case 6:
    *s_x = ((raw_s_x & 0x1ff) << 1);
    *e_x = ((raw_e_x & 0x1ff) << 1);
    *s_y = ((VDP2_W0SY & 0x3ff) >> 0);
    *e_y = ((VDP2_W0EY & 0x3ff) >> 0);
    break;
  }
}

void saturn_state::vdp2_get_window1_coordinates(int *s_x, int *e_x, int *s_y,
                                                int *e_y, int y) {
  /*W1*/
  switch (m_vdp2->get_lsmd()) {
  case 0:
  case 1:
  case 2:
    *s_y = ((VDP2_W1SY & 0x3ff) >> 0);
    *e_y = ((VDP2_W1EY & 0x3ff) >> 0);
    break;
  case 3:
    *s_y = ((VDP2_W1SY & 0x7ff) >> 0);
    *e_y = ((VDP2_W1EY & 0x7ff) >> 0);
    break;
  }

  int raw_s_x, raw_e_x;

  // check if line window is enabled
  if (VDP2_W1LWE) {
    uint32_t base_mask = m_vdp2->get_vramsz() ? 0x7ffff : 0x3ffff;
    uint32_t address = (VDP2_W1LWTA & base_mask) * 2;
    // double density makes the line window to fetch data every two lines
    uint8_t interlace = (m_vdp2->get_lsmd() == 3);
    // Apply the physical-size mask after adding the row offset. Masking
    // only LWTA lets a 512 KiB table spill into the unused upper half.
    // ST-058 pp.186-187: the high address bit is ignored in 4-Mbit mode.
    uint32_t vram_data =
        m_vdp2_vram[((address >> 2) + (y >> interlace)) & (base_mask >> 1)];

    raw_s_x = (int16_t)(vram_data >> 16);
    raw_e_x = (int16_t)(vram_data & 0xffff);
  } else {
    raw_s_x = (int16_t)VDP2_WPSX1;
    raw_e_x = (int16_t)VDP2_WPEX1;
  }

  fixup_window_x(&raw_s_x, &raw_e_x);

  // the line window table holds coordinates in the same format as WPSX/WPEX
  switch (m_vdp2->get_hreso() & 6) {
  /*Normal*/
  case 0:
    *s_x = ((raw_s_x & 0x3fe) >> 1);
    *e_x = ((raw_e_x & 0x3fe) >> 1);
    break;
  /*Hi-Res*/
  case 2:
    *s_x = ((raw_s_x & 0x3ff) >> 0);
    *e_x = ((raw_e_x & 0x3ff) >> 0);
    break;
  /*Exclusive Normal*/
  case 4:
    *s_x = ((raw_s_x & 0x1ff) >> 0);
    *e_x = ((raw_e_x & 0x1ff) >> 0);
    *s_y = ((VDP2_W1SY & 0x3ff) >> 0);
    *e_y = ((VDP2_W1EY & 0x3ff) >> 0);
    break;
  /*Exclusive Hi-Res*/
  case 6:
    *s_x = ((raw_s_x & 0x1ff) << 1);
    *e_x = ((raw_e_x & 0x1ff) << 1);
    *s_y = ((VDP2_W1SY & 0x3ff) >> 0);
    *e_y = ((VDP2_W1EY & 0x3ff) >> 0);
    break;
  }
}

int saturn_state::get_window_pixel(int s_x, int e_x, int s_y, int e_y, int x,
                                   int y, uint8_t win_num) {
  int res;

  res = 1;
  if (current_tilemap.window_control.enabled[win_num]) {
    if (current_tilemap.window_control.area[win_num])
      res = (y >= s_y && y <= e_y && x >= s_x && x <= e_x);
    else
      res = (y >= s_y && y <= e_y && x >= s_x && x <= e_x) ^ 1;
  }

  return res;
}

int saturn_state::vdp2_window_process_pixel(int x, int y) {
  int s_x = 0, e_x = 0, s_y = 0, e_y = 0;
  int res;

  if (current_tilemap.window_control.enabled[0] == 0 &&
      current_tilemap.window_control.enabled[1] == 0 && !current_tilemap.window_control.sprite_window)
    return vdp2_window_all_disabled();

  // a disabled window must not influence the result, so start from the
  // neutral value of the selected logic: inside for AND, outside for OR
  const int logic_or = current_tilemap.window_control.logic & 1;
  res = logic_or ? 0 : 1;

  if (current_tilemap.window_control.enabled[0]) {
    vdp2_get_window0_coordinates(&s_x, &e_x, &s_y, &e_y, y);
    const int w0_pix = get_window_pixel(s_x, e_x, s_y, e_y, x, y, 0);
    res = logic_or ? (res | w0_pix) : (res & w0_pix);
  }

  if (current_tilemap.window_control.enabled[1]) {
    vdp2_get_window1_coordinates(&s_x, &e_x, &s_y, &e_y, y);
    const int w1_pix = get_window_pixel(s_x, e_x, s_y, e_y, x, y, 1);
    res = logic_or ? (res | w1_pix) : (res & w1_pix);
  }

  if (current_tilemap.window_control.sprite_window) {
    bool const keep = vdp2_sprite_window(x, y) == bool(current_tilemap.window_control.sprite_window & 2);
    res = logic_or ? (res | keep) : (res & keep);
  }
  return res;
}

// window configuration of the layer currently being drawn
uint32_t saturn_state::vdp2_window_config() const {
  auto const &win = current_tilemap.window_control;

  return (win.enabled[0] ? 0x01u : 0x00u) | (win.enabled[1] ? 0x02u : 0x00u) |
         (win.area[0] ? 0x04u : 0x00u) | (win.area[1] ? 0x08u : 0x00u) |
         ((win.logic & 1) ? 0x10u : 0x00u) |
         ((win.sprite_window & 1) ? 0x20u : 0x00u) | ((win.sprite_window & 2) ? 0x40u : 0x00u);
}

void saturn_state::vdp2_window_cache_line(int y) {
  m_window_cache_y = y;
  m_window_cache_cfg = vdp2_window_config();

  for (int x = 0; x < WINDOW_CACHE_WIDTH; x++)
    m_window_cache_line[x] = vdp2_window_process_pixel(x, y) ? 1 : 0;
}

inline int saturn_state::vdp2_window_process(int x, int y) {
  // no W0/W1 window at all on this layer, the logic bit decides the outcome
  if (current_tilemap.window_control.enabled[0] == 0 &&
      current_tilemap.window_control.enabled[1] == 0 && !current_tilemap.window_control.sprite_window)
    return vdp2_window_all_disabled();

  if (unsigned(x) >= unsigned(WINDOW_CACHE_WIDTH))
    return vdp2_window_process_pixel(x, y);

  if ((y != m_window_cache_y) || (vdp2_window_config() != m_window_cache_cfg))
    vdp2_window_cache_line(y);

  return m_window_cache_line[x];
}

/* TODO: remove this crap. */
int saturn_state::vdp2_apply_window_on_layer(rectangle &cliprect) {
  int s_x = 0, e_x = 0, s_y = 0, e_y = 0;

  if (current_tilemap.window_control.enabled[0] &&
      (!current_tilemap.window_control.area[0])) {
    /* w0, transparent outside supported */
    vdp2_get_window0_coordinates(&s_x, &e_x, &s_y, &e_y, 0);

    if (s_x > cliprect.min_x)
      cliprect.min_x = s_x;
    if (e_x < cliprect.max_x)
      cliprect.max_x = e_x;
    if (s_y > cliprect.min_y)
      cliprect.min_y = s_y;
    if (e_y < cliprect.max_y)
      cliprect.max_y = e_y;

    return 1;
  } else if (current_tilemap.window_control.enabled[1] &&
             (!current_tilemap.window_control.area[1])) {
    /* w1, transparent outside supported */
    vdp2_get_window1_coordinates(&s_x, &e_x, &s_y, &e_y, 0);

    if (s_x > cliprect.min_x)
      cliprect.min_x = s_x;
    if (e_x < cliprect.max_x)
      cliprect.max_x = e_x;
    if (s_y > cliprect.min_y)
      cliprect.min_y = s_y;
    if (e_y < cliprect.max_y)
      cliprect.max_y = e_y;

    return 1;
  } else {
    return 0;
  }
}

void saturn_state::draw_sprites(bitmap_rgb32 &bitmap, const rectangle &cliprect,
                                uint8_t pri) {
  int x, y, r, g, b;
  int i;
  uint16_t pix;
  const auto rotation = vdp1_rotation_parameters();
  static const uint16_t sprite_colormask_table[] = {
      0x07ff, 0x07ff, 0x07ff, 0x07ff, 0x03ff, 0x07ff, 0x03ff, 0x01ff,
      0x007f, 0x003f, 0x003f, 0x003f, 0x00ff, 0x00ff, 0x00ff, 0x00ff};
  static const uint16_t priority_shift_table[] = {
      14, 13, 14, 13, 13, 12, 12, 12, 7, 7, 6, 0, 7, 7, 6, 0};
  static const uint16_t priority_mask_table[] = {3, 7, 1, 3, 3, 7, 7, 7,
                                                 1, 1, 3, 0, 1, 1, 3, 0};
  static const uint16_t ccrr_shift_table[] = {11, 11, 11, 11, 10, 11, 10, 9,
                                              0,  6,  0,  6,  0,  6,  0,  6};
  static const uint16_t ccrr_mask_table[] = {7, 3, 7, 3, 7, 1, 3, 7,
                                             0, 1, 0, 3, 0, 1, 0, 3};
  static const uint16_t shadow_mask_table[] = {
      0, 0, 0x8000, 0x8000, 0x8000, 0x8000, 0x8000, 0x8000,
      0, 0, 0,      0,      0,      0,      0,      0};
  uint16_t alpha_enabled;

  int sprite_type;
  int sprite_colormask;
  int color_offset_pal;
  int sprite_shadow;
  uint16_t sprite_priority_shift, sprite_priority_mask, sprite_ccrr_shift,
      sprite_ccrr_mask;
  uint8_t priority;
  uint8_t ccr = 0;
  uint8_t sprite_priorities[8];
  uint8_t sprite_ccr[8];
  int sprite_color_mode = VDP2_SPCLMD;

  if ((vdp1_sprite_priorities_usage_valid == 1) &&
      (vdp1_sprite_priorities_used[pri] == 0))
    return;

  sprite_priorities[0] = VDP2_S0PRIN;
  sprite_priorities[1] = VDP2_S1PRIN;
  sprite_priorities[2] = VDP2_S2PRIN;
  sprite_priorities[3] = VDP2_S3PRIN;
  sprite_priorities[4] = VDP2_S4PRIN;
  sprite_priorities[5] = VDP2_S5PRIN;
  sprite_priorities[6] = VDP2_S6PRIN;
  sprite_priorities[7] = VDP2_S7PRIN;

  sprite_ccr[0] = VDP2_S0CCRT;
  sprite_ccr[1] = VDP2_S1CCRT;
  sprite_ccr[2] = VDP2_S2CCRT;
  sprite_ccr[3] = VDP2_S3CCRT;
  sprite_ccr[4] = VDP2_S4CCRT;
  sprite_ccr[5] = VDP2_S5CCRT;
  sprite_ccr[6] = VDP2_S6CCRT;
  sprite_ccr[7] = VDP2_S7CCRT;

  sprite_type = VDP2_SPTYPE;
  sprite_colormask = sprite_colormask_table[sprite_type];
  sprite_priority_shift = priority_shift_table[sprite_type];
  sprite_priority_mask = priority_mask_table[sprite_type];
  sprite_ccrr_shift = ccrr_shift_table[sprite_type];
  sprite_ccrr_mask = ccrr_mask_table[sprite_type];
  sprite_shadow = shadow_mask_table[sprite_type];

  for (i = 0; i < (sprite_priority_mask + 1); i++)
    if (sprite_priorities[i] == pri)
      break;
  if (i == (sprite_priority_mask + 1))
    return;

  /* color offset (RGB brightness) */
  color_offset_pal = 0;
  if (!m_vdp2_composition_active && VDP2_SPCOEN) {
    if (VDP2_SPCOSL == 0) {
      color_offset_pal = 2048;
    } else {
      color_offset_pal = 2048 * 2;
    }
  }

  /* color calculation (alpha blending)*/
  if (VDP2_SPCCEN) {
    alpha_enabled = 0;
    switch (VDP2_SPCCCS) {
    case 0x0:
      if (pri <= VDP2_SPCCN)
        alpha_enabled = 1;
      break;
    case 0x1:
      if (pri == VDP2_SPCCN)
        alpha_enabled = 1;
      break;
    case 0x2:
      if (pri >= VDP2_SPCCN)
        alpha_enabled = 1;
      break;
    case 0x3:
      alpha_enabled = 2;
      break;
    }
  } else {
    alpha_enabled = 0;
  }

  /* window control */
  current_tilemap.window_control.logic = VDP2_SPLOG;
  current_tilemap.window_control.enabled[0] = VDP2_SPW0E;
  current_tilemap.window_control.enabled[1] = VDP2_SPW1E;
  current_tilemap.window_control.sprite_window = VDP2_SPSWE ? 1 | (VDP2_SPSWA << 1) : 0;
  current_tilemap.window_control.area[0] = VDP2_SPW0A;
  current_tilemap.window_control.area[1] = VDP2_SPW1A;
  //  current_tilemap.window_control.? = VDP2_SPSWA;

  const bool sprite_window = VDP2_SPWINEN && !sprite_color_mode && sprite_type >= 2 && sprite_type <= 7;
  for (y = cliprect.top(); y <= cliprect.bottom(); ++y) {
    if (vdp1_sprite_priorities_usage_valid && !vdp1_sprite_priorities_in_fb_line[y][pri])
      continue;
    for (x = cliprect.left(); x <= cliprect.right(); ++x) {
      if (!vdp2_window_process(x, y))
        continue;
      pix = vdp1_display_pixel(x, y, rotation);
      bool const direct = (pix & 0x8000) && sprite_color_mode;
      priority = sprite_priorities[direct ? 0 : (pix >> sprite_priority_shift) & sprite_priority_mask];
      if (priority != pri) {
        vdp1_sprite_priorities_used[priority] = 1;
        vdp1_sprite_priorities_in_fb_line[y][priority] = 1;
        continue;
      }
      bool const calculate = alpha_enabled && (alpha_enabled != 2 || (pix & 0x8000));
      bool const self_shadow = !direct && !sprite_window && (pix & sprite_shadow) && (pix & 0x7fff);
      rgb_t color;
      if (direct) {
        b = pal5bit((pix >> 10) & 31);
        g = pal5bit((pix >> 5) & 31);
        r = pal5bit(pix & 31);
        if (color_offset_pal)
          vdp2_compute_color_offset(&r, &g, &b, VDP2_SPCOSL);
        color = rgb_t(r, g, b);
        ccr = sprite_ccr[0];
      } else {
        unsigned const dot = pix & sprite_colormask;
        // Normal shadow has precedence over MSB shadow, including mixed mode.
        if (dot == unsigned(sprite_colormask - 1)) {
          vdp2_shadow_pixel(bitmap, x, y, true);
          continue;
        }
        if (!sprite_window && (pix & sprite_shadow) && !(pix & 0x7fff)) {
          if (VDP2_SDCTL & 0x100)
            vdp2_shadow_pixel(bitmap, x, y, true);
          continue;
        }
        if (!dot)
          continue;
        ccr = sprite_ccr[(pix >> sprite_ccrr_shift) & sprite_ccrr_mask];
        color = m_palette->pen(((dot + (VDP2_SPCAOS << 8)) & 0x7ff) + color_offset_pal);
      }
      bool const line = VDP2_SPLCEN;
      vdp2_compose_pixel(bitmap, x, y, color, calculate, vdp2_cc_blend_level(ccr),
          line, calculate && line ? vdp2_line_color(y, false, 0) : rgb_t(0), direct ? 6 : 14);
      if (self_shadow)
        vdp2_shadow_pixel(bitmap, x, y, false);
    }
  }

  vdp1_sprite_priorities_usage_valid = 1;
}

uint32_t saturn_state::screen_update_vdp2(screen_device &screen,
                                          bitmap_rgb32 &bitmap,
                                          const rectangle &cliprect) {
  m_vdp2_composition_active = false;
  vdp2_window_cache_invalidate();

  vdp2_fade_effects();

  vdp2_draw_back(m_tmpbitmap, cliprect);

  if (m_vdp2->get_disp()) {
    vdp2_begin_composition(m_tmpbitmap, cliprect);
    vdp2_capture_gradation(cliprect);
    uint8_t pri;

    vdp1_sprite_priorities_usage_valid = 0;
    memset(vdp1_sprite_priorities_used, 0, sizeof(vdp1_sprite_priorities_used));
    memset(vdp1_sprite_priorities_in_fb_line, 0,
           sizeof(vdp1_sprite_priorities_in_fb_line));

    // Special priority can produce priority 1 even when the register is 0.
    // The sampler suppresses effective-priority-zero dots.
    for (pri = 1; pri < 8; pri++) {
      m_vdp2_priority_pass = pri;
      if (vdp2_priority_pass_matches(VDP2_N3PRIN, (VDP2_SFPRMD >> 6) & 3, pri)) {
        vdp2_draw_NBG3(m_tmpbitmap, cliprect);
      }
      if (vdp2_priority_pass_matches(VDP2_N2PRIN, (VDP2_SFPRMD >> 4) & 3, pri)) {
        vdp2_draw_NBG2(m_tmpbitmap, cliprect);
      }
      if (vdp2_priority_pass_matches(VDP2_N1PRIN, (VDP2_SFPRMD >> 2) & 3, pri)) {
        vdp2_draw_NBG1(m_tmpbitmap, cliprect);
      }
      if (vdp2_priority_pass_matches(VDP2_N0PRIN, (VDP2_SFPRMD >> 0) & 3, pri)) {
        vdp2_draw_NBG0(m_tmpbitmap, cliprect);
      }
      if (vdp2_priority_pass_matches(VDP2_R0PRIN, (VDP2_SFPRMD >> 8) & 3, pri)) {
        vdp2_draw_RBG0(m_tmpbitmap, cliprect);
      }
      {
        draw_sprites(m_tmpbitmap, cliprect, pri);
      }
    }
  }

  m_vdp2_priority_pass = -1;
  m_vdp2_composition_active = false;
  copybitmap(bitmap, m_tmpbitmap, 0, 0, 0, 0, cliprect);

#if 0
	/* Do NOT remove me, used to test video code performance. */
	if(machine().input().code_pressed(KEYCODE_Q))
	{
		popmessage("Halt CPUs");
		m_maincpu->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
		m_slave->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
		m_audiocpu->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
	}
#endif
  return 0;
}

// license:BSD-3-Clause
// copyright-holders:Angelo Salese
/**************************************************************************************************

Sega Saturn VDP2 (c) 1995 Sega/Yamaha

TODO:
- stub overlay for screen timings and not much else

**************************************************************************************************/

#include "saturn_vdp2.h"
#include "emu.h"


#define VERBOSE 0
// #define LOG_OUTPUT_FUNC osd_printf_info

#include "logmacro.h"

DEFINE_DEVICE_TYPE(SATURN_VDP2, saturn_vdp2_device, "saturn_vdp2",
                   "Sega Saturn VDP2 (Yamaha 315-5690)")

saturn_vdp2_device::saturn_vdp2_device(const machine_config &mconfig,
                                       const char *tag, device_t *owner,
                                       uint32_t clock)
    : device_t(mconfig, SATURN_VDP2, tag, owner, clock),
      m_screen(*this, finder_base::DUMMY_TAG), m_vint_cb(*this),
      m_hint_cb(*this), m_is_pal(false) {}

void saturn_vdp2_device::device_start() {
  m_video_sync_timer =
      timer_alloc(FUNC(saturn_vdp2_device::sync_timer_cb), this);
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
  // VRAMSZ is writable through VRSIZE, so it is live machine state
  save_item(NAME(m_vramsz));

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

void saturn_vdp2_device::device_reset() {
  m_video_sync_timer->adjust(m_screen->time_until_pos(0), 0);

  m_odd_bit = 1;
  // shouldn't really matter
  m_old_tvmd = 0xffff;
  //	m_hreso = 0;
  //	m_vreso = 0;
  //	m_dotsel_352 = true;

  // VRAMSZ and EXSLT/EXTEN are only ever written when the guest programs
  // them, but both are read back - VRAMSZ also feeds get_vramsz() - so they
  // need a defined power-on value rather than whatever the allocation held
  m_vramsz = false;
  m_exten = 0;
  reconfigure_crtc();
}

void saturn_vdp2_device::init_vcounter_table() {
  // put vcounter inside a table
  /* Both NTSC and PAL modes are filled for all 313 rows: a PAL frame runs to
     line 312 and may still be set to a 224 or 240 line mode, so stopping at
     the 263 rows an NTSC frame reaches left the PAL vblank lines reading
     whatever the allocation held.  The jump threshold belongs to the mode
     rather than the region, so the extra lines continue the same ramp.

     Correct timings are taken from Ymir (vTimingsNormal) and MiSTer
     (BREAK_LINE/JUMP_LINE) with verification against Charles MacDonald
     hardware tests noted in saturn.cpp TODO:

       vpos 0 == 0x1ff (VBE, VBlank-Out)
       vpos 1 == 0
       vpos 241 == 0xf0 (VBI, VBlank-In for 240 mode)
       vpos 246 == 0xf5
       vpos 247 == 0x1ef (rollback)
       vpos 263 == 0x1ff

     The Saturn V counter does not simply increment; it jumps from BREAK
     to JUMP (VCNTSkip = 0x200 - base).  Base is 263 NTSC, 313 PAL.
     MiSTer defines:

       NTSC 224: BREAK 0xED (237) -> JUMP 0x1E6 (486)  [Ymir BBd 224, BSy 232,
     VCS 237] NTSC 240: BREAK 0xF5 (245) -> JUMP 0x1EE (494)  [Ymir BBd 240, BSy
     240, VCS 245] Adjusted to 0x1EF (495) to match documented rollback at 247
       PAL 224 : BREAK 0x103 (259) -> JUMP 0x1CA (458)
       PAL 240 : BREAK 0x10B (267) -> JUMP 0x1D2 (466)
       PAL 256 : BREAK 0x113 (275) -> JUMP 0x1DA (474)

     MAME's screen vpos 0 is the last line (0x1ff), vpos 1 is first active
     (0), so the table is offset by 1 compared to raw VCNT.

     Exclusive (VGA) modes use a 10-bit counter up to 525/561 lines and
     are handled directly in get_vcounter().
  */

  // NTSC 224: BREAK 236 (0xEC) -> JUMP 486 (0x1E6)
  // This gives: 0=0x1ff, 1=0, 225=0xE0 (224) VBI, 237=0xEC (236), 238=0x1E6
  // (486) rollback, 263=0x1ff
  for (u16 i = 0; i < 313; i++) {
    if (i == 0)
      true_vcount[i][0] = 0x1ff;
    else if (i >= 1 && i <= 236)
      true_vcount[i][0] = i - 1;
    else if (i >= 237 && i <= 262)
      true_vcount[i][0] = 0x1e6 + (i - 237); // 486..511
    else if (i == 263)
      true_vcount[i][0] = 0x1ff;
    else
      true_vcount[i][0] = i; // beyond NTSC, keep identity for safety
  }

  // NTSC 240: BREAK 245 (0xF5) -> JUMP 495 (0x1EF) to match documented
  // 247=0x1EF Gives: 0=0x1ff, 1=0, 241=0xF0 VBI, 246=0xF5, 247=0x1EF rollback,
  // 263=0x1FF
  for (u16 i = 0; i < 313; i++) {
    if (i == 0)
      true_vcount[i][1] = 0x1ff;
    else if (i >= 1 && i <= 246)
      true_vcount[i][1] = i - 1; // 0..245
    else if (i >= 247 && i <= 262)
      true_vcount[i][1] = 0x1ef + (i - 247); // 495..510
    else if (i == 263)
      true_vcount[i][1] = 0x1ff;
    else
      true_vcount[i][1] = i;
  }

  // PAL 224: BREAK 257 (0x101) -> JUMP 458 (0x1CA)
  // 0=0x1ff, 1=0, 225=224 VBI, 259=258? Actually VBI at 225, rollback at
  // 259=0x1CA
  for (u16 i = 0; i < 313; i++) {
    if (i == 0)
      true_vcount[i][2] = 0x1ff;
    else if (i >= 1 && i <= 258)
      true_vcount[i][2] = i - 1; // 0..257
    else if (i >= 259 && i <= 312)
      true_vcount[i][2] = 0x1ca + (i - 259); // 458..511
    else
      true_vcount[i][2] = i;
  }

  // PAL 240/256 share 256 timing for 240? Use PAL 240: BREAK 265, JUMP 466
  // and PAL 256: BREAK 273, JUMP 474.  We use PAL 256 for both 2 and 3 to match
  // original intent (256 modes).  For simplicity, fill [3] same as [2] but
  // with PAL 256 break/jump.
  for (u16 i = 0; i < 313; i++) {
    if (i == 0)
      true_vcount[i][3] = 0x1ff;
    else if (i >= 1 && i <= 274)
      true_vcount[i][3] = i - 1; // 0..273 for 256 mode
    else if (i >= 275 && i <= 312)
      true_vcount[i][3] = 0x1da + (i - 275); // 474..511
    else
      true_vcount[i][3] = i;
  }

  // Also fix PAL 240 separately if needed: overwrite index 1? No, index 1 is
  // NTSC 240. For PAL region with VRESO 1 (240), the mask (m_is_pal<<1)|1 gives
  // 3 when PAL, so it uses true_vcount[*][3] which is PAL 256 timing.  To
  // correctly support PAL 240, we need a distinct table.  Since we have only 4
  // slots, we repurpose: [0]=NTSC 224, [1]=NTSC 240, [2]=PAL 224, [3]=PAL
  // 240/256. For PAL 240, use BREAK 265, JUMP 466:
  if (m_is_pal) {
    // Override [1] slot when PAL: actually PAL 240 should be in [1]? No, mask
    // gives 3. Let's keep [2]=PAL 224, [3]=PAL 240 (with 256 fallback).
    // Recompute [3] as PAL 240 for better accuracy, and [2] as PAL 224.
    // PAL 240: 0=511, 1..266=0..265, 267..312=466..511
    for (u16 i = 0; i < 313; i++) {
      if (i == 0)
        true_vcount[i][3] = 0x1ff;
      else if (i >= 1 && i <= 266)
        true_vcount[i][3] = i - 1;
      else if (i >= 267 && i <= 312)
        true_vcount[i][3] = 0x1d2 + (i - 267); // 466..511
    }
    // Keep [2] as PAL 224 already.
    // For PAL 256, we don't have slot, but 256 mode also uses [3] (since VRESO
    // 2,3 mask 3) so it will get PAL 240 timing, which is close (267 vs 275).
    // Acceptable for now; ideally we'd have separate table, but true_vcount is
    // [4] only. To improve, if VRESO is 2/3 (256), use 275 break: We can store
    // PAL 256 in [2]?? Let's just keep [2]=PAL 224, [3]=PAL 256 as most common.
    // Actually for PAL, VRESO 0=224,1=240,2=256,3=256. So we need:
    // [0]=PAL 224? No, NTSC mask limits.
    // Simpler: when PAL, [0]=PAL 224, [1]=PAL 240, [2]=PAL 256, [3]=PAL 256
    // But then NTSC table lost. Since init is called at start with m_is_pal
    // known, we can fill based on region.
    if (m_is_pal) {
      // PAL region: fill all 4 as PAL timings
      // [0]=PAL 224
      for (u16 i = 0; i < 313; i++) {
        if (i == 0)
          true_vcount[i][0] = 0x1ff;
        else if (i >= 1 && i <= 258)
          true_vcount[i][0] = i - 1;
        else if (i >= 259)
          true_vcount[i][0] = 0x1ca + (i - 259);
      }
      // [1]=PAL 240
      for (u16 i = 0; i < 313; i++) {
        if (i == 0)
          true_vcount[i][1] = 0x1ff;
        else if (i >= 1 && i <= 266)
          true_vcount[i][1] = i - 1;
        else if (i >= 267)
          true_vcount[i][1] = 0x1d2 + (i - 267);
      }
      // [2]=PAL 256
      for (u16 i = 0; i < 313; i++) {
        if (i == 0)
          true_vcount[i][2] = 0x1ff;
        else if (i >= 1 && i <= 274)
          true_vcount[i][2] = i - 1;
        else if (i >= 275)
          true_vcount[i][2] = 0x1da + (i - 275);
      }
      // [3]=PAL 256 duplicate
      for (u16 i = 0; i < 313; i++)
        true_vcount[i][3] = true_vcount[i][2];
    }
  }
}

/*
 *
 * Register Map
 *
 */

// $5f80000 base
void saturn_vdp2_device::regs_map(address_map &map) {
  // $5f80000 TVMD TV Mode
  // x--- ---- ---- ---- DISP (0 = blanked)
  // -x-- ---- ---- ---- BDCLMD (1 = back screen, 0 = black)
  // ---- ---- xx-- ---- LSMD interlace mode
  // ---- ---- --xx ---- VRESO vertical resolution
  // ---- ---- ---- -xxx HRESO horizontal resolution
  map(0x0000, 0x0001)
      .lrw16(NAME([this]() { return m_tvmd; }),
             NAME([this](offs_t offset, u16 data, u16 mem_mask) {
               COMBINE_DATA(&m_tvmd);
               m_disp = BIT(m_tvmd, 15);
               m_bdclmd = BIT(m_tvmd, 8);
               m_lsmd = (m_tvmd >> 6) & 3;
               m_vreso = (m_tvmd >> 4) & 3;
               m_hreso = (m_tvmd >> 0) & 7;
               if (ACCESSING_BITS_0_7 && (m_tvmd & 0xff) != (m_old_tvmd & 0xff))
                 reconfigure_crtc();
               m_old_tvmd = m_tvmd;
             }));

  // $5f80002 EXTEN External Signal Enable
  map(0x0002, 0x0003)
      .lrw16(NAME([this](offs_t offset) {
               // latch HV counters when reading this register
               if (!machine().side_effects_disabled() && !m_exlten) {
                 m_hcounter_latch = get_hcounter();
                 m_vcounter_latch = get_vcounter();

                 m_exltfg |= 1;
               }

               return m_exten;
             }),
             NAME([this](offs_t offset, u16 data, u16 mem_mask) {
               // may be triggered a whole ton by games that DMA over this
               // region
               if (data & 0x0303)
                 LOG("5f80002h: EXTEN External Signal Enable %04x & %04x\n",
                     data, mem_mask);
               COMBINE_DATA(&m_exten);
               m_exlten = BIT(m_exten, 9);
               m_exsyen = BIT(m_exten, 8);
               m_dasel = BIT(m_exten, 1);
               m_exbgen = BIT(m_exten, 0);
             }));

  // $5f80004 TVSTAT Screen Status (r/o)
  map(0x004, 0x005).lr16(NAME([this]() {
    // Doc claims odd bit to be always '1' for non-interlace but:
    // - stv:seabass (BIOS to game transition wants this to be 0)
    // - stv:grdforce (tests this bit to be 1 from title screen to gameplay)
    // - stv:finlarch/sasissu/magzun
    // Exclusive modes force this to '1'
    const bool odd_flag = m_odd_bit | BIT(m_hreso, 2);

    // if DISP off then return '1'
    // Sega Saturn Technical Bulletin #12 ("SCU DMA, Boot ROM, and Vblank
    // Precautions", item 3) scopes this to the VBLANK bit alone: "VBLANK bit of
    // the screen status register (TVSTAT: 180004H) becomes valid, only when
    // DISP bit of TV screen mode register (TVMD: 180000H) is 1. When DISP bit
    // is 0, VBLANK bit will always be 1."  HBLANK is deliberately not
    // mentioned, so it keeps reporting the real horizontal state while DISP is
    // off.
    const bool vblank_flag = get_vblank() | (!m_disp);

    const u16 res = ((m_exltfg << 9) | (m_exsyfg << 8) | (vblank_flag << 3) |
                     (get_hblank() << 2) | (odd_flag << 1) | m_is_pal);

    // clear these flags if this register is read
    if (!machine().side_effects_disabled()) {
      m_exltfg &= ~1;
      m_exsyfg &= ~1;
    }

    return res;
  }));

  // $5f80006 VRSIZE VRAM Size
  // x--- ---- ---- ---- VRAMSZ (0 = 4MB mode 1 = 8MB mode)
  // ---- ---- ---- xxxx VER silicon version (r/o)
  map(0x006, 0x007)
      .lrw16(NAME([this]() {
               // TODO: version
               return (m_vramsz << 15) | (0 & 0xf);
             }),
             NAME([this](offs_t offset, u16 data, u16 mem_mask) {
               // TODO: probably akin to YM7101 equivalent on stock Saturn
               if (ACCESSING_BITS_8_15)
                 m_vramsz = BIT(data, 15);
             }));

  // $5f80008 HCNT (r/o)
  map(0x008, 0x009).lr16(NAME([this]() { return m_hcounter_latch; }));
  // $5f8000a VCNT (r/o)
  map(0x00a, 0x00b).lr16(NAME([this]() { return m_vcounter_latch; }));
}

/*
 *
 * CRTC
 *
 */

void saturn_vdp2_device::device_clock_changed() { reconfigure_crtc(); }

int saturn_vdp2_device::get_hblank_duration() {
  const int base_htotal[2] = {427, 455};

  int res = base_htotal[BIT(m_hreso, 0)];

  // x2 horizontal resolution in 640/704 modes
  if (BIT(m_hreso, 1))
    res <<= 1;

  return res;
}

// some vblank lines measurements (according to Charles MacDonald)
// TODO: interlace mode "eats" one line, should be 262.5
int saturn_vdp2_device::get_vblank_duration() {
  const int base_vtotal[2] = {263, 313};
  int res = base_vtotal[m_is_pal];

  // compensate for double density interlace
  if (m_lsmd == 3)
    res <<= 1;

  // Exclusive modes
  if (BIT(m_hreso, 2)) {
    res = BIT(m_hreso, 0) ? 561 : 525;
  }

  return res;
}

int saturn_vdp2_device::get_pixel_clock() {
  int res, divider;

  res = this->clock();
  // TODO: divider is always 8, need to compensate out of lack of MAME interlace
  // support
  divider = 8;

  if (BIT(m_hreso, 1))
    divider >>= 1;

  if (m_lsmd == 3)
    divider >>= 1;

  // TODO: Unknown for Exclusive modes
  if (BIT(m_hreso, 2))
    divider >>= 1;

  return res / divider;
}

void saturn_vdp2_device::reconfigure_crtc() {
  const int d_vres[4] = {224, 240, 256, 256};
  const int d_hres[4] = {320, 352, 640, 704};
  int horz_res, vert_res;

  // TODO: guard against the wrong DOTSEL being configured from SMPC.
  // on real HW this causes monitor instability and unusable vblank IRQs.
  // astrass will throw a fuss if we do this in scan timer, also hot path ...
  // if (BIT(m_hreso, 0) != m_dotsel_352)
  //	return;

  // reset odd bit if a dynamic resolution change occurs, stv:seabass cares
  m_odd_bit = 1;
  // NTSC can't set 256 modes
  const u8 vres_mask = (m_is_pal << 1) | 1;
  vert_res = d_vres[m_vreso & vres_mask];

  // TODO: this should just be reserved and return VRESO == 2
  // if((m_vreso & 3) == 3)
  //	popmessage("Illegal VRES MODE");

  // In double density interlace bump by x2 the vertical resolution
  if (m_lsmd == 3) {
    vert_res *= 2;
  }

  horz_res = d_hres[m_hreso & 3];
  // Exclusive modes (31kHz and Hi-Vision) sets a vertical resolution of 480
  // regardless of what VRESO says
  // TODO: find a software that makes use of this
  if (BIT(m_hreso, 2))
    vert_res = 480;

  int vblank_period, hblank_period;
  rectangle visarea(0, horz_res - 1, 0, vert_res - 1);

  vblank_period = get_vblank_duration();
  hblank_period = get_hblank_duration();
  attotime refresh =
      attotime::from_ticks(hblank_period * vblank_period, get_pixel_clock());
  // printf("%d %d %d
  // %d\n",horz_res,vert_res,horz_res+hblank_period,vblank_period);

  // save these to reuse them in scan timer
  m_hdisplay = horz_res;
  m_vdisplay = vert_res;

  m_screen->configure(hblank_period, vblank_period, visarea, refresh);
}

void saturn_vdp2_device::external_latch() {
  // EXLTEN selects the external signal as the HV counter latch source;
  // EXLTFG is cleared by the next TVSTAT read
  if (!m_exlten)
    return;

  m_hcounter_latch = get_hcounter();
  m_vcounter_latch = get_vcounter();

  m_exltfg |= 1;
}

int saturn_vdp2_device::get_hcounter() {
  int hcount;

  hcount = m_screen->hpos();

  switch (m_hreso & 6) {
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

int saturn_vdp2_device::get_vcounter() {
  int vcount;

  vcount = m_screen->vpos();

  // Exclusive Monitor: 10-bit counter, up to 525/561 lines
  if (BIT(m_hreso, 2))
    return vcount & 0x3ff;

  // Double Density Interlace: Ymir shows VCNTShift=1, VCNTSkip, and ODD
  // handling VCNTLatch = (VCNT<<1)+skip, LSB = ODD^1 For MAME, approximate with
  // vcount>>1 and ODD bit.
  if (m_lsmd == 3) {
    int base =
        true_vcount[vcount & 0x1ff][m_vreso & ((m_is_pal << 1) | 1)] & 0x1ff;
    // Double density: VCNT is (base>>1) with ODD in LSB
    // ODD toggles each field (m_odd_bit)
    return ((base & ~1) | (m_odd_bit ^ 1)) & 0x1ff;
  }

  /* NTSC cannot select the 256 line modes, so mask VRESO exactly as
     reconfigure_crtc() and get_vblank_line() do.  Without it an NTSC machine
     with VRESO 2 or 3 programmed in TVMD reported the flat identity counter
     while the CRTC was still configured for 224 or 240 lines. */
  const u8 vres_mask = (m_is_pal << 1) | 1;

  // docs says << 1, but according to HW tests it's a typo.
  assert((vcount & 0x1ff) < std::size(true_vcount));
  return (true_vcount[vcount & 0x1ff][m_vreso & vres_mask]); // Non-interlace
}

// Refined H/V blank positions based on Ymir vTimingsNormal and MiSTer VBL_START
// Ymir: BBd = Bottom Border (VBlank IN), BSy = Blanking/Sync, VCS =
// VCounterSkip,
//       TBd = Top Border, LLn = Last Line, ADp = Active Display (next frame)
// MiSTer: VBL_START_224=0xE0=224, VBL_START_240=0xF0=240,
// VBL_START_256=0x100=256
//         BREAK/JUMP define the V counter skip (rollback).
// MAME's vpos 0 is the last line (0x1FF), so VBI (VBlank In) appears at vpos+1.
int saturn_vdp2_device::get_hblank() {
  // HBlank: Ymir sets HBLANK=1 at Right Border phase, 0 at Left Border.
  // For MAME, approximate with visible area, but use hdisplay as threshold
  // to match MiSTer HBLANK_START (320->324, 352->356).
  // The pixel clock and htotal are 427/455, active 320/352, so HBlank
  // starts 4 pixels after active in 320 mode, 4 pixels after in 352?
  // Use visarea.right() as before but also account for exclusive modes.
  int cur_h = m_screen->hpos();
  // In exclusive modes, H counter counts differently, but HBlank still
  // after active. Use m_hdisplay as active width.
  if (cur_h >= m_hdisplay)
    return 1;
  return 0;
}

int saturn_vdp2_device::get_vblank() {
  int cur_v = m_screen->vpos();
  int vblank_line = get_vblank_start_position() * get_ystep_count();

  // VBlank is active from VBI (Bottom Border) through last line inclusive.
  // Hardware: VBI at 241=0xF0 for 240 mode, VBE (VBlank-Out) at line 0=0x1FF
  // (last line).  In MAME's screen, vpos 0 is first active line, but we keep
  // true_vcount[0]=0x1FF to match documented rollback.  VBlank flag is 1
  // when vpos >= VBI (241..262) and 0 otherwise (0..240), so VBE (1->0)
  // happens at vpos 0, which is last line -> first active transition.
  // This gives 22 lines VBlank for 240 mode (241..262) plus the 0 line
  // handling via true_vcount, total 23 lines (263-240).
  if (cur_v >= vblank_line)
    return 1;
  return 0;
}

int saturn_vdp2_device::get_vblank_start_position() {
  // VBlank-In positions (VBI) based on Ymir/MiSTer VBL_START:
  // NTSC 224: 224 active, VBI at 225 (MAME vpos, accounting for 0=last line)
  // NTSC 240: 240 active, VBI at 241
  // PAL  256: 256 active, VBI at 257
  // For simplicity, return VBI = active+1, which matches documented
  // 241=0xF0 for 240 mode and gives 225 for 224 mode.
  const int d_vres_active[4] = {224, 240, 256, 256};
  const u8 vres_mask = (m_is_pal << 1) | 1;
  int active = d_vres_active[m_vreso & vres_mask];
  // VBI is active+1 due to vpos0 being last line
  return active + 1;
}

int saturn_vdp2_device::get_ystep_count() {
  int max_y = m_screen->height();
  int y_step;

  y_step = 2;

  // TODO: 263 & 313 needs to be static constexpr
  if ((max_y == 263 && m_is_pal == 0) || (max_y == 313 && m_is_pal == 1))
    y_step = 1;

  return y_step;
}

TIMER_CALLBACK_MEMBER(saturn_vdp2_device::sync_timer_cb) {
  int vpos = m_screen->vpos();
  int hsync = get_hblank();
  int vsync = get_vblank();

  m_vint_cb(vsync);
  m_hint_cb(hsync);

  // VBlank handling: Ymir/MiSTer show VBlank IN at BottomBorder (BBd),
  // VBlank OUT at LastLine (LLn).  Previously MAME jumped to 0,0 as soon
  // as VBlank started, skipping the VBlank period.  Now we walk through
  // VBlank lines and only flip ODD and wrap at the last line.
  if (vsync) {
    int ystep = get_ystep_count();
    int vtotal = get_vblank_duration();
    // If we are at last line (vtotal-1), wrap to 0 and flip ODD
    if (vpos >= vtotal - ystep) {
      m_odd_bit ^= 1;
      m_video_sync_timer->adjust(m_screen->time_until_pos(0, 0));
    } else {
      m_video_sync_timer->adjust(m_screen->time_until_pos(vpos + ystep, 0));
    }
  } else {
    if (hsync) {
      int ystep = get_ystep_count();
      m_video_sync_timer->adjust(m_screen->time_until_pos(vpos + ystep, 0));
    } else
      m_video_sync_timer->adjust(m_screen->time_until_pos(vpos, m_hdisplay));
  }
}

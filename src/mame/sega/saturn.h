// license:LGPL-2.1+
// copyright-holders:David Haywood, Angelo Salese, Olivier Galibert, Mariusz Wojcieszek, R. Belmont
#ifndef MAME_SEGA_SATURN_H
#define MAME_SEGA_SATURN_H

#pragma once

#include "315-5881_crypt.h"
#include "315-5838_317-0229_comp.h"
#include "saturn_dcc.h"
#include "saturn_scu.h"
//#include "saturn_vdp1.h"
#include "saturn_vdp2.h"
#include "saturn_vdp2_render.h"
#include "smpc.h"

#include "bus/generic/slot.h"
#include "bus/generic/carts.h"

#include "cpu/m68000/m68000.h"
#include "cpu/sh/sh7604.h"
#include "machine/timer.h"
#include "sound/scsp.h"

#include "emupal.h"
#include "screen.h"

class saturn_state : public driver_device
{
public:
	saturn_state(const machine_config &mconfig, device_type type, const char *tag) :
		driver_device(mconfig, type, tag),
		m_rom(*this, "bios"),
		m_workram_l(*this, "workram_l"),
		m_workram_h(*this, "workram_h"),
		m_sound_ram(*this, "sound_ram"),
		m_maincpu(*this, "maincpu"),
		m_slave(*this, "slave"),
		m_audiocpu(*this, "audiocpu"),
		m_dcc(*this, "dcc"),
		m_scsp(*this, "scsp"),
		m_smpc_hle(*this, "smpc"),
		m_scu(*this, "scu"),
		//m_vdp1(*this, "vdp1"),
		m_vdp2(*this, "vdp2"),
		m_screen(*this, "screen")
	{
	}

protected:
	required_region_ptr<uint32_t> m_rom;
	required_shared_ptr<uint32_t> m_workram_l;
	required_shared_ptr<uint32_t> m_workram_h;
	required_shared_ptr<uint16_t> m_sound_ram;

	memory_region *m_cart_reg[4];
	std::unique_ptr<uint8_t[]>     m_backupram;
	std::unique_ptr<uint16_t[]>    m_vdp2_regs;
	std::unique_ptr<uint32_t[]>    m_vdp2_vram;
	std::unique_ptr<uint32_t[]>    m_vdp2_cram;
	std::unique_ptr<uint32_t[]>    m_vdp1_vram;
	std::unique_ptr<uint16_t[]>    m_vdp1_regs;

	uint8_t     m_en_68k = 0;

	struct spoint {
		int32_t x, y;
		int32_t u, v;
	};

	struct {
		std::unique_ptr<uint16_t * []> framebuffer_display_lines;
		int         framebuffer_mode = 0;
		int         framebuffer_double_interlace = 0;
		int         fbcr_accessed = 0;
		int         framebuffer_width = 0;
		int         framebuffer_height = 0;
		int         framebuffer_current_display = 0;
		int         framebuffer_current_draw = 0;
		int         framebuffer_clear_on_next_frame = 0;
		rectangle system_cliprect;
		rectangle user_cliprect;
		std::unique_ptr<uint16_t []> framebuffer[2];
		std::unique_ptr<uint16_t * []> framebuffer_draw_lines;
		std::unique_ptr<uint8_t []> gfx_decode;
		uint16_t    lopr = 0;
		uint16_t    copr = 0;
		uint16_t    ewdr = 0;

		int         local_x = 0;
		int         local_y = 0;

		emu_timer * draw_end_timer = nullptr;
	} m_vdp1_legacy;


	required_device<sh7604_device> m_maincpu;
	required_device<sh7604_device> m_slave;
	required_device<m68000_base_device> m_audiocpu;
	required_device<saturn_dcc_device> m_dcc;
	required_device<scsp_device> m_scsp;
	required_device<smpc_hle_device> m_smpc_hle;
	required_device<saturn_scu_device> m_scu;
//  required_device<saturn_vdp1_device> m_vdp1;
	required_device<saturn_vdp2_device> m_vdp2;
	required_device<screen_device> m_screen;

	saturn_vdp2_render::renderer m_vdp2_renderer;
	std::unique_ptr<uint32_t[]> m_vdp2_frame;
	void vdp2_scanline(int scanline);

	class vdp2_sprite_fb;

	int m_scsp_last_line = 0;

	virtual void machine_reset() override ATTR_COLD;

	void scsp_irq(offs_t offset, uint8_t data);

	// SMPC HLE delegates
	void master_sh2_reset_w(int state);
	void master_sh2_nmi_w(int state);
	void slave_sh2_reset_w(int state);
	void sound_68k_reset_w(int state);
	void system_reset_w(int state);
	void system_halt_w(int state);
	void dot_select_w(int state);

	void m68k_reset_callback(int state);

	void CEF_1() { m_vdp1_regs[0x010/2] |= 0x0002; }
	void CEF_0() { m_vdp1_regs[0x010/2] &= ~0x0002; }
	void BEF_1() { m_vdp1_regs[0x010/2] |= 0x0001; }
	void BEF_0() { m_vdp1_regs[0x010/2] &= ~0x0001; }
	uint16_t VDP1_TVMR() const { return m_vdp1_regs[0x000/2] & 0xffff; }
	uint16_t VDP1_VBE() const { return (VDP1_TVMR() & 0x0008) >> 3; }
	uint16_t VDP1_TVM() const { return (VDP1_TVMR() & 0x0007) >> 0; }

	DECLARE_VIDEO_START(vdp2_video_start);
	uint32_t screen_update_vdp2(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect);
	TIMER_DEVICE_CALLBACK_MEMBER(saturn_scanline);
	void vint_callback(int state);
	void hint_callback(int state);
	int m_prev_hint, m_prev_vint;

	TIMER_CALLBACK_MEMBER(vdp1_draw_end);
	void soundram_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t soundram_r(offs_t offset);
	uint8_t backupram_r(offs_t offset);
	void backupram_w(offs_t offset, uint8_t data);

	uint16_t vdp1_regs_r(offs_t offset);
	uint32_t vdp1_vram_r(offs_t offset);
	uint32_t vdp1_framebuffer0_r(offs_t offset, uint32_t mem_mask = ~0);

	void vdp1_regs_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void vdp1_vram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void vdp1_framebuffer0_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);

	uint32_t vdp2_vram_r(offs_t offset);
	uint32_t vdp2_cram_r(offs_t offset);
	uint16_t vdp2_regs_r(offs_t offset);

	void vdp2_vram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void vdp2_cram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void vdp2_regs_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);


	/* VDP1 */
	void vdp1_set_framebuffer_config();
	void vdp1_prepare_framebuffers();
	void vdp1_change_framebuffers();
	void vdp1_video_update();
	void vdp1_process_list();
	void vdp1_set_drawpixel();

	void vdp1_draw_normal_sprite(const rectangle &cliprect, int sprite_type);
	void vdp1_draw_scaled_sprite(const rectangle &cliprect);
	void vdp1_draw_distorted_sprite(const rectangle &cliprect);
	void vdp1_draw_poly_line(const rectangle &cliprect);
	void vdp1_draw_line(const rectangle &cliprect);
	int x2s(int v);
	int y2s(int v);
	void vdp1_fill_quad(const rectangle &cliprect, int patterndata, int xsize, const struct spoint *q);
	void vdp1_fill_line(const rectangle &cliprect, int patterndata, int xsize, int32_t y, int32_t x1, int32_t x2, int32_t u1, int32_t u2, int32_t v1, int32_t v2);
	void (saturn_state::*drawpixel)(int x, int y, int patterndata, int offsetcnt);
	void drawpixel_poly(int x, int y, int patterndata, int offsetcnt);
	void drawpixel_8bpp_trans(int x, int y, int patterndata, int offsetcnt);
	void drawpixel_4bpp_notrans(int x, int y, int patterndata, int offsetcnt);
	void drawpixel_4bpp_trans(int x, int y, int patterndata, int offsetcnt);
	void drawpixel_generic(int x, int y, int patterndata, int offsetcnt);
	void vdp1_fill_slope(const rectangle &cliprect, int patterndata, int xsize,
							int32_t x1, int32_t x2, int32_t sl1, int32_t sl2, int32_t *nx1, int32_t *nx2,
							int32_t u1, int32_t u2, int32_t slu1, int32_t slu2, int32_t *nu1, int32_t *nu2,
							int32_t v1, int32_t v2, int32_t slv1, int32_t slv2, int32_t *nv1, int32_t *nv2,
							int32_t _y1, int32_t y2);
	void vdp1_setup_shading_for_line(int32_t y, int32_t x1, int32_t x2,
												int32_t r1, int32_t g1, int32_t b1,
												int32_t r2, int32_t g2, int32_t b2);
	void vdp1_setup_shading_for_slope(
							int32_t x1, int32_t x2, int32_t sl1, int32_t sl2, int32_t *nx1, int32_t *nx2,
							int32_t r1, int32_t r2, int32_t slr1, int32_t slr2, int32_t *nr1, int32_t *nr2,
							int32_t g1, int32_t g2, int32_t slg1, int32_t slg2, int32_t *ng1, int32_t *ng2,
							int32_t b1, int32_t b2, int32_t slb1, int32_t slb2, int32_t *nb1, int32_t *nb2,
							int32_t _y1, int32_t y2);
	uint16_t vdp1_apply_gouraud_shading(int x, int y, uint16_t pix);
	void vdp1_setup_shading(const struct spoint* q, const rectangle &cliprect);
	uint8_t read_gouraud_table();
	void clear_gouraud_shading();

	void vdp1_clear_framebuffer(int which_framebuffer);
	void vdp1_state_save_postload();
	int vdp1_start();

	struct vdp1_poly_scanline
	{
		int32_t   x[2]{};
		int32_t   b[2]{};
		int32_t   g[2]{};
		int32_t   r[2]{};
		int32_t   db = 0;
		int32_t   dg = 0;
		int32_t   dr = 0;
	};

	struct vdp1_poly_scanline_data
	{
		int32_t   sy = 0, ey = 0;
		struct  vdp1_poly_scanline scanline[512];
	};

	std::unique_ptr<struct vdp1_poly_scanline_data> vdp1_shading_data;

	struct vdp1_sprite_list
	{
		int CMDCTRL = 0, CMDLINK = 0, CMDPMOD = 0, CMDCOLR = 0, CMDSRCA = 0, CMDSIZE = 0, CMDGRDA = 0;
		int CMDXA = 0, CMDYA = 0;
		int CMDXB = 0, CMDYB = 0;
		int CMDXC = 0, CMDYC = 0;
		int CMDXD = 0, CMDYD = 0;

		int ispoly = 0;

	} current_sprite;

	/* Gouraud shading */

	struct _gouraud_shading
	{
		/* Gouraud shading table */
		uint16_t  GA = 0;
		uint16_t  GB = 0;
		uint16_t  GC = 0;
		uint16_t  GD = 0;
	} gouraud_shading;

	uint16_t m_sprite_colorbank = 0;

	/* VDP2 */
	int vdp2_start();

//  void scudsp_end_w(int state);
//  uint16_t scudsp_dma_r(offs_t offset);
//  void scudsp_dma_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
};


// These two clocks are synthesized by the 315-5746
#define MASTER_CLOCK_352 XTAL(14'318'181)*4
#define MASTER_CLOCK_320 XTAL(14'318'181)*3.75


#endif // MAME_SEGA_SATURN_H

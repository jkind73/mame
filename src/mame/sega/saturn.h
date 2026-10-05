// license:LGPL-2.1+
// copyright-holders:David Haywood, Angelo Salese, Olivier Galibert, Mariusz Wojcieszek, R. Belmont
#ifndef MAME_SEGA_SATURN_H
#define MAME_SEGA_SATURN_H

#pragma once

#include "315-5881_crypt.h"
#include "315-5838_317-0229_comp.h"
#include "saturn_dcc.h"
#include "saturn_scu.h"
#include "saturn_vdp1.h"
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
		m_vdp1(*this, "vdp1"),
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

	uint8_t     m_en_68k = 0;

	required_device<sh7604_device> m_maincpu;
	required_device<sh7604_device> m_slave;
	required_device<m68000_base_device> m_audiocpu;
	required_device<saturn_dcc_device> m_dcc;
	required_device<scsp_device> m_scsp;
	required_device<smpc_hle_device> m_smpc_hle;
	required_device<saturn_scu_device> m_scu;
	required_device<saturn_vdp1_device> m_vdp1;
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

	DECLARE_VIDEO_START(vdp2_video_start);
	uint32_t screen_update_vdp2(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect);
	TIMER_DEVICE_CALLBACK_MEMBER(saturn_scanline);
	void vint_callback(int state);
	void hint_callback(int state);
	int m_prev_hint, m_prev_vint;

	void soundram_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t soundram_r(offs_t offset);
	uint8_t backupram_r(offs_t offset);
	void backupram_w(offs_t offset, uint8_t data);

	uint32_t vdp2_vram_r(offs_t offset);
	uint32_t vdp2_cram_r(offs_t offset);
	uint16_t vdp2_regs_r(offs_t offset);
	uint8_t vdp2_vram_write_penalty(offs_t bank);

	void vdp2_vram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void vdp2_cram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void vdp2_regs_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);


	/* VDP2 */
	int vdp2_start();

//  void scudsp_end_w(int state);
//  uint16_t scudsp_dma_r(offs_t offset);
//  void scudsp_dma_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
};


// These two clocks are synthesized by the 315-5746
#define MASTER_CLOCK_352 XTAL(14'318'181)*4
// 320 dot mode: SH-2 26.8741 MHz, SCU DSP 13.4371 MHz (Sega Saturn Overview Manual Rel.2.5, Tables 3.1.1 and 3.2.1),
// i.e. 1708 clocks per line at the NTSC line rate of 15734.27 Hz (colour burst clock / 910); 352 dot mode is
// 28.6364 MHz, 1820 clocks per line. Both are the colour burst clock times clocks per line / 455.
#define MASTER_CLOCK_320 XTAL(14'318'181) * 1708.0 / 455.0
// PAL: SH-2 26.6877 MHz in 320 dot mode and 28.4377 MHz in 352 dot mode (Tables 3.1.1 and 3.2.1), the clocks
// per line of the NTSC modes at the PAL line rate of 15625 Hz (the manual rounds the clocks, as above)
#define MASTER_CLOCK_320_PAL (MASTER_CLOCK_320 * (26.6877 / 26.8741))
#define MASTER_CLOCK_352_PAL (MASTER_CLOCK_352 * (28.4377 / 28.6364))


#endif // MAME_SEGA_SATURN_H

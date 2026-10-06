// license:BSD-3-Clause
// copyright-holders:Angelo Salese

#ifndef MAME_SEGA_SATURN_VDP2_H
#define MAME_SEGA_SATURN_VDP2_H

#pragma once

#include "screen.h"

class saturn_vdp2_device : public device_t
{
public:
	// construction/destruction
	saturn_vdp2_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	void regs_map(address_map &map) ATTR_COLD;

	void set_is_pal(bool is_pal) { m_is_pal = is_pal; }
	bool is_pal() const { return m_is_pal; }
	void set_dotsel(bool is_352_mode) { m_dotsel_352 = is_352_mode; }

	template <typename T> void set_screen_tag(T &&tag) { m_screen.set_tag(std::forward<T>(tag)); }

	auto vint_cb() { return m_vint_cb.bind(); }
	auto hint_cb() { return m_hint_cb.bind(); }

	// TODO: follows stuff that eventually needs to be privatized
	u8 get_hreso() { return m_hreso; }
	u8 get_vreso() { return m_vreso; }
	bool get_disp() { return m_disp; }
	bool get_bdclmd() { return m_bdclmd; }
	u8 get_lsmd() { return m_lsmd; }
	int get_vblank_start_position();
	int get_ystep_count();
	bool get_vramsz() { return m_vramsz; }
	bool is_blanking() { return get_vblank() || !m_disp; }

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_clock_changed() override;

private:
	required_device<screen_device> m_screen;
	devcb_write_line m_vint_cb;
	devcb_write_line m_hint_cb;

	// CRTC
	emu_timer *m_hblank_timer;
	emu_timer *m_vblank_timer;
	bool m_hblank_rising;  // the next HBLANK-IN event raises the signal; otherwise it drops it
	bool m_vblank_next_in; // the next vertical event is VBLANK-IN; otherwise it is VBLANK-OUT

	bool m_is_pal;
	bool m_dotsel_352;

	u16 m_tvmd, m_old_tvmd;
	u8 m_disp, m_bdclmd, m_lsmd, m_vreso, m_hreso;
	bool m_odd_bit;
	u16 m_exten;
	bool m_exlten, m_exsyen, m_dasel, m_exbgen;

	u16 m_hcounter_latch, m_vcounter_latch;

	bool m_exltfg, m_exsyfg;

	u16 m_hdisplay, m_vdisplay;
	// size = 313 for PAL
	u16 true_vcount[313][4];

	bool m_vramsz;

	TIMER_CALLBACK_MEMBER( hblank_timer_cb );
	TIMER_CALLBACK_MEMBER( vblank_timer_cb );
	void schedule_hblank();
	void schedule_vblank();
	int dot_scale() const;
	int hblank_in_dot() const;
	int hblank_out_dot() const;

	void init_vcounter_table();
	void reconfigure_crtc();

	int get_vblank();
	int get_hblank();
	int get_hcounter();
	int get_vcounter();
	int get_vblank_duration();
	int get_hblank_duration();
	int get_pixel_clock();
};

DECLARE_DEVICE_TYPE(SATURN_VDP2, saturn_vdp2_device)


#endif // MAME_SEGA_SATURN_VDP2_H

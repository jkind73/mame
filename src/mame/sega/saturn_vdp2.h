// license:BSD-3-Clause
// copyright-holders:Angelo Salese

#ifndef MAME_SEGA_SATURN_VDP2_H
#define MAME_SEGA_SATURN_VDP2_H

#pragma once

#include "screen.h"

class saturn_vdp2_device : public device_t {
public:
  // construction/destruction
  saturn_vdp2_device(const machine_config &mconfig, const char *tag,
                     device_t *owner, uint32_t clock);

  void regs_map(address_map &map) ATTR_COLD;

  void set_is_pal(bool is_pal) { m_is_pal = is_pal; }
  void set_dotsel(bool is_352_mode) { m_dotsel_352 = is_352_mode; }

  template <typename T> void set_screen_tag(T &&tag) {
    m_screen.set_tag(std::forward<T>(tag));
  }

  // HV counter latch driven by an external signal (light gun), EXTEN bit 9
  void external_latch();

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

protected:
  virtual void device_start() override ATTR_COLD;
  virtual void device_reset() override ATTR_COLD;
  virtual void device_clock_changed() override;

private:
  required_device<screen_device> m_screen;
  devcb_write_line m_vint_cb;
  devcb_write_line m_hint_cb;

  // CRTC
  emu_timer *m_video_sync_timer;

  bool m_is_pal;
  bool m_dotsel_352;

  // The startup clock notification can configure the CRTC before reset.
  u16 m_tvmd = 0, m_old_tvmd = 0xffff;
  u8 m_disp = 0, m_bdclmd = 0, m_lsmd = 0, m_vreso = 0, m_hreso = 0;
  bool m_odd_bit;
  u16 m_exten;
  bool m_exlten, m_exsyen, m_dasel, m_exbgen;

  u16 m_hcounter_latch, m_vcounter_latch;

  bool m_exltfg, m_exsyfg;

  u16 m_hdisplay, m_vdisplay;
  // size = 313 for PAL
  u16 true_vcount[313][4]{};

  bool m_vramsz;

  TIMER_CALLBACK_MEMBER(sync_timer_cb);

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

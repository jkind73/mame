// license:LGPL-2.1+
// copyright-holders:David Haywood, Angelo Salese, Olivier Galibert, Mariusz
// Wojcieszek, R. Belmont
#ifndef MAME_SEGA_SATURN_H
#define MAME_SEGA_SATURN_H

#pragma once

#include "315-5838_317-0229_comp.h"
#include "315-5881_crypt.h"
#include "saturn_dcc.h"
#include "saturn_scu.h"

// #include "saturn_vdp1.h"
#include "saturn_vdp2.h"
#include "smpc.h"

#include "bus/generic/carts.h"
#include "bus/generic/slot.h"


#include "cpu/m68000/m68000.h"
#include "cpu/sh/sh7604.h"
#include "machine/timer.h"
#include "sound/scsp.h"

#include "emupal.h"
#include "screen.h"

class saturn_state : public driver_device {
public:
  saturn_state(const machine_config &mconfig, device_type type, const char *tag)
      : driver_device(mconfig, type, tag), m_rom(*this, "bios"),
        m_workram_l(*this, "workram_l"), m_workram_h(*this, "workram_h"),
        m_sound_ram(*this, "sound_ram"), m_maincpu(*this, "maincpu"),
        m_slave(*this, "slave"), m_audiocpu(*this, "audiocpu"),
        m_dcc(*this, "dcc"), m_scsp(*this, "scsp"), m_smpc_hle(*this, "smpc"),
        m_scu(*this, "scu"),
        // m_vdp1(*this, "vdp1"),
        m_vdp2(*this, "vdp2"), m_gfxdecode(*this, "gfxdecode"),
        m_screen(*this, "screen"), m_palette(*this, "palette") {}

protected:
  required_region_ptr<uint32_t> m_rom;
  required_shared_ptr<uint32_t> m_workram_l;
  required_shared_ptr<uint32_t> m_workram_h;
  required_shared_ptr<uint16_t> m_sound_ram;

  memory_region *m_cart_reg[4];
  std::unique_ptr<uint8_t[]> m_backupram;
  std::unique_ptr<uint16_t[]> m_vdp2_regs;
  std::unique_ptr<uint32_t[]> m_vdp2_vram;
  std::unique_ptr<uint32_t[]> m_vdp2_cram;
  std::unique_ptr<uint32_t[]> m_vdp1_vram;
  std::unique_ptr<uint16_t[]> m_vdp1_regs;

  uint8_t m_en_68k = 0;

  struct spoint {
    int32_t x, y;
    int32_t u, v;
  };

  // Native quads emit at most 4096 spans. A scaled rectangle between signed
  // 13-bit endpoints can span 8192 rows with pre-clipping disabled.
  // Native records: xa,ya,xb,yb,ca,cb,clip[4],coverage,texture row,width.
  // Rectangle kinds -1/-2 occupy coverage: normal uses ca=U step,row=first
  // texel; scaled uses ca=original X,cb=destination columns,row=source V.
  // Rectangle clip slots are unused; pixel writers enforce live clip state.
  struct vdp1_raster_state {
    static constexpr unsigned segment_words = 13;
    static constexpr unsigned max_segments = 8192;
    std::array<int32_t, segment_words * max_segments> segments{};
    int count = 0, index = 0, dot = 0;
    int x = 0, y = 0, error = 0, end_codes = 0;
    bool extra = false;
  } m_vdp1_raster;
  // Display-period erase follows presentation of each physical raster.
  struct vdp1_display_erase_state {
    bool pending = false;
    uint8_t bank = 0;
    uint16_t data = 0, left = 0, right = 0, top = 0, bottom = 0;
    uint16_t next_row = 0;
    uint8_t step = 1;
  } m_vdp1_display_erase;
  // Host dispatch guards only; never live across an emulated timer boundary.
  bool m_vdp1_raster_building = false, m_vdp1_raster_running = false;
  int m_vdp1_raster_budget = 0;

  struct {
    std::unique_ptr<uint16_t *[]> framebuffer_display_lines;
    int framebuffer_mode = 0;
    int framebuffer_double_interlace = 0;
    int fbcr_accessed = 0;
    int framebuffer_width = 0;
    int framebuffer_height = 0;
    int framebuffer_current_display = 0;
    int framebuffer_current_draw = 0;
    rectangle system_cliprect;
    rectangle user_cliprect;
    std::unique_ptr<uint16_t[]> framebuffer[2];
    std::unique_ptr<uint16_t[]> field_framebuffer[2];
    bool field_valid[2] = {false, false};
    uint8_t draw_field = 0;
    uint8_t draw_eos = 0;
    uint16_t erase_upper_left = 0, erase_lower_right = 0;
    bool vblank_erase_pending = false, vblank_erase_active = false;
    uint8_t vblank_erase_bank = 0;
    uint16_t vblank_erase_stride = 512, vblank_erase_data = 0;
    uint16_t vblank_erase_left = 0, vblank_erase_right = 0;
    uint16_t vblank_erase_top = 0, vblank_erase_bottom = 0;
    uint32_t vblank_erase_budget = 0;
    uint16_t vblank_erase_x = 0, vblank_erase_y = 0;
    uint16_t vblank_erase_words_per_line = 0;
    uint8_t vblank_erase_step = 1;
    std::unique_ptr<uint16_t *[]> framebuffer_draw_lines;
    std::unique_ptr<uint8_t[]> gfx_decode;
    uint16_t lopr = 0;
    uint16_t copr = 0;
    uint16_t ewdr = 0;

    int local_x = 0;
    int local_y = 0;

    bool drawing = false;
    int command_position = 0;
    int command_return = -1;
    emu_timer *draw_end_timer = nullptr;
    emu_timer *terminate_timer = nullptr;
  } m_vdp1_legacy;

  struct {
    std::unique_ptr<uint8_t[]> gfx_decode;
    bitmap_rgb32 roz_bitmap[2];
    int old_crmd = 0;
  } m_vdp2_legacy;

  required_device<sh7604_device> m_maincpu;
  required_device<sh7604_device> m_slave;
  required_device<m68000_base_device> m_audiocpu;
  required_device<saturn_dcc_device> m_dcc;
  required_device<scsp_device> m_scsp;
  required_device<smpc_hle_device> m_smpc_hle;
  required_device<saturn_scu_device> m_scu;
  //  required_device<saturn_vdp1_device> m_vdp1;
  required_device<saturn_vdp2_device> m_vdp2;
  required_device<gfxdecode_device> m_gfxdecode;
  required_device<screen_device> m_screen;
  required_device<palette_device> m_palette;

  bitmap_rgb32 m_tmpbitmap;

  int m_scsp_last_line = 0;

  bool m_system_halt = false;
  bool m_main_dma_halt = false;
  bool m_sound_dma_halt = false;
  virtual void machine_start() override ATTR_COLD;
  virtual void machine_reset() override ATTR_COLD;
  void reset_halt_state();
  void update_halt_lines();
  void main_dma_halt_w(int state);
  void sound_dma_halt_w(int state);

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

  void CEF_1() { m_vdp1_regs[0x010 / 2] |= 0x0002; }
  void CEF_0() { m_vdp1_regs[0x010 / 2] &= ~0x0002; }
  void BEF_1() { m_vdp1_regs[0x010 / 2] |= 0x0001; }
  void BEF_0() { m_vdp1_regs[0x010 / 2] &= ~0x0001; }
  uint16_t VDP1_TVMR() const { return m_vdp1_regs[0x000 / 2] & 0xffff; }
  uint16_t VDP1_VBE() const { return (VDP1_TVMR() & 0x0008) >> 3; }
  uint16_t VDP1_TVM() const { return (VDP1_TVMR() & 0x0007) >> 0; }

  DECLARE_VIDEO_START(vdp2_video_start);
  uint32_t screen_update_vdp2(screen_device &screen, bitmap_rgb32 &bitmap,
                              const rectangle &cliprect);
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
  void vdp1_framebuffer0_w(offs_t offset, uint32_t data,
                           uint32_t mem_mask = ~0);

  uint32_t vdp2_vram_r(offs_t offset);
  uint32_t vdp2_cram_r(offs_t offset);
  uint16_t vdp2_regs_r(offs_t offset);

  void vdp2_vram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
  void vdp2_cram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
  void vdp2_regs_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

  /* VDP1 */
  void vdp1_latch_framebuffer_config();
  void vdp1_set_framebuffer_config();
  void vdp1_reset_framebuffers();
  void vdp1_prepare_framebuffers();
  void vdp1_change_framebuffers();
  void vdp1_video_update();
  void vdp1_process_list();
  void vdp1_abort_draw();
  void vdp1_request_termination();
  TIMER_CALLBACK_MEMBER(vdp1_terminate);
  void vdp1_set_drawpixel();

  static int vdp1_scaled_coordinate(int source, int destination, int pixel, bool reverse);
  void vdp1_draw_scaled_pixels(const rectangle &cliprect, int address, int width, int height, const spoint *q);
  std::array<int16_t, 256> m_vdp1_texture_end{};
  bool vdp1_texture_sample_visible(int address, int width, int texel);
  bool vdp1_is_end_code(int address, int texel) const;
  void vdp1_draw_normal_sprite(const rectangle &cliprect, int sprite_type);
  void vdp1_draw_scaled_sprite(const rectangle &cliprect);
  void vdp1_draw_quad_pixels(const rectangle &cliprect, int width, int height, const spoint *q);
  void vdp1_draw_distorted_sprite(const rectangle &cliprect);
  void vdp1_draw_poly_line(const rectangle &cliprect);
  void vdp1_draw_segment(const rectangle &cliprect, const spoint &a, const spoint &b, uint16_t color_a, uint16_t color_b,
                         bool edge_coverage = false, int texture_row = -1, int texture_width = 0);
  int vdp1_raster_slice_cycles() const;
  // Host-only diagnostics; deliberately not part of emulated save state.
  int64_t m_boot_trace_second = -1;
  bool boot_trace_word(u32 address, bool sound, u16 &word);
  void trace_boot_cpu();
  void vdp1_trace(const char *event, int reg = -1, const spoint *bounds = nullptr);
  void vdp1_reset_raster_queue();
  void vdp1_draw_raster_slice();
  void vdp1_draw_rectangle_slice(const int32_t *data);
  void vdp1_draw_line(const rectangle &cliprect);
  int x2s(int v);
  int y2s(int v);
  void vdp1_fill_quad(const rectangle &cliprect, int patterndata, int xsize,
                      const struct spoint *q);
  void vdp1_fill_line(const rectangle &cliprect, int patterndata, int xsize,
                      int32_t y, int32_t x1, int32_t x2, int32_t u1, int32_t u2,
                      int32_t v1, int32_t v2);
  void (saturn_state::*drawpixel)(int x, int y, int patterndata, int offsetcnt);
  std::array<uint32_t, 6> vdp1_rotation_parameters() const;
  static int vdp1_rotation_coordinate(uint32_t start, uint32_t line_step, uint32_t dot_step, int x, int y);
  uint16_t vdp1_display_pixel(int x, int y, const std::array<uint32_t, 6> &rotation) const;
  uint16_t vdp1_read_pixel(const uint16_t *line, int x) const;
  void vdp1_write_pixel(int x, int y, uint16_t value);
  bool vdp1_pixel_visible(int x, int y) const;
  void drawpixel_poly(int x, int y, int patterndata, int offsetcnt);
  void drawpixel_8bpp_trans(int x, int y, int patterndata, int offsetcnt);
  void drawpixel_4bpp_notrans(int x, int y, int patterndata, int offsetcnt);
  void drawpixel_4bpp_trans(int x, int y, int patterndata, int offsetcnt);
  static uint16_t vdp1_color_calculate(uint16_t src, uint16_t dst, unsigned mode);
  void vdp1_draw_color(int x, int y, uint16_t src);
  void drawpixel_generic(int x, int y, int patterndata, int offsetcnt);
  void vdp1_fill_slope(const rectangle &cliprect, int patterndata, int xsize,
                       int32_t x1, int32_t x2, int32_t sl1, int32_t sl2,
                       int32_t *nx1, int32_t *nx2, int32_t u1, int32_t u2,
                       int32_t slu1, int32_t slu2, int32_t *nu1, int32_t *nu2,
                       int32_t v1, int32_t v2, int32_t slv1, int32_t slv2,
                       int32_t *nv1, int32_t *nv2, int32_t _y1, int32_t y2);
  void vdp1_setup_shading_for_line(int32_t y, int32_t x1, int32_t x2,
                                   int32_t r1, int32_t g1, int32_t b1,
                                   int32_t r2, int32_t g2, int32_t b2);
  void vdp1_setup_shading_for_slope(int32_t x1, int32_t x2, int32_t sl1,
                                    int32_t sl2, int32_t *nx1, int32_t *nx2,
                                    int32_t r1, int32_t r2, int32_t slr1,
                                    int32_t slr2, int32_t *nr1, int32_t *nr2,
                                    int32_t g1, int32_t g2, int32_t slg1,
                                    int32_t slg2, int32_t *ng1, int32_t *ng2,
                                    int32_t b1, int32_t b2, int32_t slb1,
                                    int32_t slb2, int32_t *nb1, int32_t *nb2,
                                    int32_t _y1, int32_t y2);
  uint16_t vdp1_apply_gouraud_shading(int x, int y, uint16_t pix);
  void vdp1_setup_shading(const struct spoint *q, const rectangle &cliprect);
  void vdp1_setup_rectangle_shading(const spoint *q, const rectangle &cliprect);
  uint8_t read_gouraud_table();
  void clear_gouraud_shading();

  void vdp1_clear_framebuffer(int which_framebuffer);
  uint32_t vdp1_vblank_erase_capacity() const;
  uint32_t vdp1_vblank_erase_line_capacity() const;
  void vdp1_advance_vblank_erase(uint32_t words);
  void vdp1_begin_vblank_erase();
  void vdp1_finish_vblank_erase();
  void vdp1_cancel_erase();
  void vdp1_begin_display_erase();
  void vdp1_finish_display_erase();
  void vdp1_advance_display_erase(int scanline);
  void vdp1_state_save_postload();
  int vdp1_start();

  struct vdp1_poly_scanline {
    bool integer = false;
    int32_t x[2]{};
    int32_t b[2]{};
    int32_t g[2]{};
    int32_t r[2]{};
    int32_t db = 0;
    int32_t dg = 0;
    int32_t dr = 0;
  };

  struct vdp1_poly_scanline_data {
    int32_t sy = 0, ey = 0;
    struct vdp1_poly_scanline scanline[512];
  };

  std::unique_ptr<struct vdp1_poly_scanline_data> vdp1_shading_data;

  struct vdp1_sprite_list {
    int CMDCTRL = 0, CMDLINK = 0, CMDPMOD = 0, CMDCOLR = 0, CMDSRCA = 0,
        CMDSIZE = 0, CMDGRDA = 0;
    int CMDXA = 0, CMDYA = 0;
    int CMDXB = 0, CMDYB = 0;
    int CMDXC = 0, CMDYC = 0;
    int CMDXD = 0, CMDYD = 0;

    int ispoly = 0;

  } current_sprite;

  /* Gouraud shading */

  struct _gouraud_shading {
    /* Gouraud shading table */
    uint16_t GA = 0;
    uint16_t GB = 0;
    uint16_t GC = 0;
    uint16_t GD = 0;
  } gouraud_shading;

  uint16_t m_sprite_colorbank = 0;

  /* VDP1 Framebuffer handling */
  int vdp1_sprite_priorities_used[8]{};
  int vdp1_sprite_priorities_usage_valid = 0;
  uint8_t vdp1_sprite_priorities_in_fb_line[512][8]{};

  /* VDP2 */

  void refresh_palette_data();
  inline int vdp2_window_process(int x, int y);
  int vdp2_window_process_pixel(int x, int y);
  uint32_t vdp2_window_config() const;
  // Per the manual, when the W0, W1 and SW enable bits of a screen are all zero
  // the logic bit alone decides the outcome: OR (0) leaves the whole screen
  // outside of the window effective area, AND (1) puts the whole screen inside
  // of it. The sprite window is not emulated as a window source, so when it is
  // the only window in use keep drawing the screen instead of blanking it.
  // Inline: this is the common case, most layers run without any window.
  int vdp2_window_all_disabled() const {
    if (current_tilemap.window_control.sprite_window)
      return 1;

    return (current_tilemap.window_control.logic & 1) ? 0 : 1;
  }
  uint32_t vdp2_read_rotation_coefficient(uint32_t address);
  void vdp2_window_cache_line(int y);
  void vdp2_window_cache_invalidate() {
    m_window_cache_y = -1;
    m_sprite_window_y = -1;
    m_roz_window_cache_y = -1;
  }
  void vdp2_roz_window_prepare(int y);
  void vdp2_get_window0_coordinates(int *s_x, int *e_x, int *s_y, int *e_y,
                                    int y);
  void vdp2_get_window1_coordinates(int *s_x, int *e_x, int *s_y, int *e_y,
                                    int y);
  int get_window_pixel(int s_x, int e_x, int s_y, int e_y, int x, int y,
                       uint8_t win_num);
  int vdp2_apply_window_on_layer(rectangle &cliprect);

  void vdp2_draw_basic_tilemap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void vdp2_draw_basic_bitmap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void draw_4bpp_bitmap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void draw_8bpp_bitmap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void draw_11bpp_bitmap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void draw_rgb15_bitmap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void draw_rgb32_bitmap(bitmap_rgb32 &bitmap, const rectangle &cliprect);

  void vdp2_drawgfxzoom(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                        gfx_element *gfx, uint32_t code, uint32_t color,
                        int flipx, int flipy, int sx, int sy, int transparency,
                        int scalex, int scaley, int sprite_screen_width,
                        int sprite_screen_height, int alpha);
  void vdp2_drawgfxzoom_rgb555(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                               uint32_t code, uint32_t color, int flipx,
                               int flipy, int sx, int sy, int transparency,
                               int scalex, int scaley, int sprite_screen_width,
                               int sprite_screen_height, int alpha);
  void vdp2_drawgfxzoom_rgb888(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                               uint32_t code, uint32_t color, int flipx,
                               int flipy, int sx, int sy, int transparency,
                               int scalex, int scaley, int sprite_screen_width,
                               int sprite_screen_height, int alpha);
  void vdp2_drawgfx_rgb555(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                           uint32_t code, int flipx, int flipy, int sx, int sy,
                           int transparency, int alpha);
  void vdp2_drawgfx_rgb888(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                           uint32_t code, int flipx, int flipy, int sx, int sy,
                           int transparency, int alpha);

  void vdp2_drawgfx_alpha(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                          gfx_element *gfx, uint32_t code, uint32_t color,
                          int flipx, int flipy, int offsx, int offsy,
                          int transparency, int alpha);
  void vdp2_drawgfx_transpen(bitmap_rgb32 &dest_bmp, const rectangle &clip,
                             gfx_element *gfx, uint32_t code, uint32_t color,
                             int flipx, int flipy, int offsx, int offsy,
                             int transparency);

  void vdp2_draw_rotation_screen(bitmap_rgb32 &bitmap,
                                 const rectangle &cliprect, int iRP);
  void vdp2_check_tilemap_with_linescroll(bitmap_rgb32 &bitmap,
                                          const rectangle &cliprect);
  void vdp2_check_tilemap(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  rgb_t vdp2_line_color(int y, bool use_coefficient, uint8_t coefficient_color);
  unsigned vdp2_special_color_mode() const;
  rgb_t vdp2_special_color_pixel(rgb_t color, unsigned raw, unsigned pen);
  rgb_t vdp2_dot_pixel(uint32_t address, int x, unsigned palette);
  rgb_t vdp2_pattern_pixel(uint32_t data, bool one_word, int x, int y);
  rgb_t vdp2_scroll_pixel(int32_t x, int32_t y);
  void vdp2_draw_scroll_screen(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  rgb_t vdp2_screen_over_pattern_pixel(uint16_t data, int x, int y);
  void vdp2_copy_roz_bitmap(bitmap_rgb32 &bitmap, bitmap_rgb32 &roz_bitmap,
                            const rectangle &cliprect, int iRP, int planesizex,
                            int planesizey, int planerenderedsizex,
                            int planerenderedsizey);
  inline bool vdp2_roz_window(int x, int y);
  inline bool vdp2_roz_mode3_window(int x, int y, int rot_parameter);
  inline int get_roz_window_pixel(int s_x, int e_x, int s_y, int e_y, int x,
                                  int y, uint8_t winenable, uint8_t winarea);
  void vdp2_reset_rotation_latches();
  void vdp2_latch_rotation_parameters(int scanline);
  void vdp2_load_rotation_line(uint8_t parameter, int line);
  void vdp2_fill_rotation_parameter_table(uint8_t rot_parameter);
  uint8_t vdp2_check_vram_cycle_pattern_registers(uint8_t access_command_pnmdr,
                                                  uint8_t access_command_cpdr,
                                                  uint8_t bitmap_enable);
  uint8_t vdp2_is_rotation_applied(uint8_t rot_parameter);
  uint8_t vdp2_are_map_registers_equal();
  void vdp2_get_map_page(int x, int y, int *_map, int *_page);

  void vdp2_draw_mosaic(bitmap_rgb32 &bitmap, const rectangle &cliprect,
                        uint8_t is_roz);
  void vdp2_fade_effects();
  void vdp2_compute_color_offset(int *r, int *g, int *b, int cor);
  void vdp2_compute_color_offset_UINT32(rgb_t *rgb, int cor);
  void vdp2_check_fade_control_for_layer();

  void vdp2_draw_line(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  rgb_t vdp2_back_screen_color(uint8_t const *gfxdata, uint32_t base_offs);
  void vdp2_draw_back(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void vdp2_draw_NBG0(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void vdp2_draw_NBG1(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void vdp2_draw_NBG2(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void vdp2_draw_NBG3(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void vdp2_draw_RBG0(bitmap_rgb32 &bitmap, const rectangle &cliprect);
  void draw_sprites(bitmap_rgb32 &bitmap, const rectangle &cliprect,
                    uint8_t pri);

  void vdp2_state_save_postload();
  void vdp2_exit();
  int vdp2_start();

  uint8_t m_vdpdebug_roz = 0;

  struct vdp2_tilemap_capabilities {
    uint8_t enabled = 0;
    uint8_t transparency = 0;
    uint8_t colour_calculation_enabled = 0;
    uint8_t colour_depth = 0;
    uint8_t alpha = 0;
    uint8_t tile_size = 0;
    uint8_t bitmap_enable = 0;
    uint8_t bitmap_size = 0;
    uint8_t bitmap_palette_number = 0;
    uint8_t bitmap_map = 0;
    uint16_t map_offset[16]{};
    uint8_t map_count = 0;

    uint8_t pattern_data_size = 0;
    uint8_t character_number_supplement = 0;
    uint8_t special_priority_register = 0;
    uint8_t special_colour_control_register = 0;
    uint8_t supplementary_palette_bits = 0;
    uint8_t supplementary_character_bits = 0;

    int16_t scrollx = 0;
    int16_t scrolly = 0;
    uint16_t scrollx_fraction = 0, scrolly_fraction = 0;
    uint32_t incx = 0, incy = 0;

    uint8_t linescroll_enable = 0;
    uint8_t linescroll_interval = 0;
    uint32_t linescroll_table_address = 0;
    uint8_t vertical_linescroll_enable = 0;
    uint8_t vertical_cell_scroll_enable = 0;
    uint8_t linezoom_enable = 0;

    uint8_t plane_size = 0;
    uint8_t colour_ram_address_offset = 0;
    uint8_t fade_control = 0;
    struct {
      uint8_t logic = 0;
      uint8_t enabled[2]{};
      uint8_t area[2]{};
      uint8_t sprite_window = 0;
    } window_control;

    uint8_t line_screen_enabled = 0;
    uint8_t mosaic_screen_enabled = 0;
    bool roz_mode3 = false;

    int layer_name = 0; /* just to keep track */
  } current_tilemap;

  // The 2048-entry fade A/B palette tables are rebuilt from CRAM and the
  // color offset registers, so track when either of them changes instead of
  // recomputing all 4096 pens every frame.
  bool m_fade_effects_dirty = true;
  void mark_fade_effects_dirty() { m_fade_effects_dirty = true; }

  // Per scanline window mask cache: neither the VDP2 registers nor VRAM can
  // change while a frame is being rendered, so the (expensive) window
  // evaluation is done once per line and window configuration instead of
  // once per pixel, per layer and per priority pass.
  static constexpr int WINDOW_CACHE_WIDTH = 1024;
  int m_sprite_window_y = -1;
  uint8_t m_sprite_window_line[WINDOW_CACHE_WIDTH]{};
  bool vdp2_sprite_window(int x, int y);
  int m_window_cache_y = -1;
  int m_roz_window_cache_y = -1;
  int m_roz_win_s_x[2]{};
  int m_roz_win_e_x[2]{};
  int m_roz_win_s_y[2]{};
  int m_roz_win_e_y[2]{};
  uint32_t m_window_cache_cfg = 0;
  uint8_t m_window_cache_line[WINDOW_CACHE_WIDTH]{};

  struct rotation_table {
    int32_t xst = 0;
    int32_t yst = 0;
    int32_t zst = 0;
    int32_t dxst = 0;
    int32_t dyst = 0;
    int32_t dx = 0;
    int32_t dy = 0;
    int32_t A = 0;
    int32_t B = 0;
    int32_t C = 0;
    int32_t D = 0;
    int32_t E = 0;
    int32_t F = 0;
    int32_t px = 0;
    int32_t py = 0;
    int32_t pz = 0;
    int32_t cx = 0;
    int32_t cy = 0;
    int32_t cz = 0;
    int32_t mx = 0;
    int32_t my = 0;
    int32_t kx = 0;
    int32_t ky = 0;
    uint32_t kast = 0;
    int32_t dkast = 0;
    int32_t dkax = 0;

  } current_rotation_table;

  static constexpr int ROTATION_SCANLINES = 1024;
  rotation_table m_rotation_lines[ROTATION_SCANLINES][2]{};
  bool m_rotation_line_valid[ROTATION_SCANLINES]{};
  bool m_rotation_latch_valid = false;
  uint32_t m_rotation_x[2]{}, m_rotation_y[2]{}, m_rotation_k[2]{};


  struct _vdp2_layer_data {
    uint32_t map_offset_min = 0;
    uint32_t map_offset_max = 0;
    uint32_t tile_offset_min = 0;
    uint32_t tile_offset_max = 0;
  } vdp2_layer_data;

  struct _RBG0_cache_data {
    uint8_t watch_vdp2_vram_writes = 0;
    uint8_t is_cache_dirty = 0;

    uint32_t map_offset_min[2]{0, 0};
    uint32_t map_offset_max[2]{0, 0};
    uint32_t tile_offset_min[2]{0, 0};
    uint32_t tile_offset_max[2]{0, 0};

    struct vdp2_tilemap_capabilities layer_data[2];

  } RBG0_cache_data;

  //  void scudsp_end_w(int state);
  //  uint16_t scudsp_dma_r(offs_t offset);
  //  void scudsp_dma_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
};

// These two clocks are synthesized by the 315-5746
#define MASTER_CLOCK_352 XTAL(14'318'181) * 4
#define MASTER_CLOCK_320 XTAL(14'318'181) * 3.75

extern gfx_decode_entry const gfx_stv[];

#endif // MAME_SEGA_SATURN_H
// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  Sega Saturn VDP1 (Hitachi HD64440 / 315-5689) sprite processor.

  Owns the sprite RAM, the two frame buffers and the registers, runs the
  command list in time (a command is executed when its predecessor's drawing
  time has elapsed, see saturn_vdp1_draw.h for the per-command costs) and
  handles the frame level behaviour: frame buffer swap, erase (frame erase
  while the picture is read, vblank erase), automatic draw start, end of
  draw flags and interrupt.
*/

#ifndef MAME_SEGA_SATURN_VDP1_H
#define MAME_SEGA_SATURN_VDP1_H

#pragma once

#include "saturn_vdp1_draw.h"

class saturn_vdp1_device : public device_t
{
public:
	saturn_vdp1_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	// pulsed (1) when a command list finishes with an end command
	auto draw_end_cb() { return m_draw_end_cb.bind(); }

	// bus interface (offsets in the units of each handler's width)
	uint16_t regs_r(offs_t offset);
	void regs_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint32_t vram_r(offs_t offset);
	void vram_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t fb_r(offs_t offset, uint32_t mem_mask = ~0);
	void fb_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);

	// SMPC system reset: clears the memories as well as the state
	void system_reset();

	// video timing inputs from the VDP2
	void vblank_w(int state);
	void hblank_w(int state);
	// advances drawing to the current time; call at the start of every scanline
	void update();

	// frame buffer readout for the VDP2 sprite layer
	bool bpp8() const { return m_tvmr & saturn_vdp1::TVMR_8BPP; }
	bool rotate() const { return m_tvmr & saturn_vdp1::TVMR_ROTATE; }
	bool hdtv() const { return m_tvmr & saturn_vdp1::TVMR_HDTV; }
	// pixel x of line y of the displayed frame buffer (16 bit word, or 0xff00 | byte in 8bpp)
	uint16_t display_pixel(unsigned x, unsigned y) const;
	uint16_t display_pixel_field(unsigned x, unsigned line) const;
	// the VDP2 has read display line y: the frame erase steps on
	void display_line_done();
	// a word of the displayed buffer addressed by its rotated position (rotation mode readout)
	uint16_t display_rotated_pixel(int32_t x, int32_t y) const;

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

private:
	static constexpr int32_t UPDATE_GRANULARITY = 64;   // clocks of drawing time that can be banked
	static constexpr int VRAM_CPU_WAIT = 10;             // CPU clocks lost per VRAM access while drawing (ST-013 p.19)
	static constexpr int VBE_SAMPLE_DELAY_US = 64;      // about one scanline

	devcb_write_line m_draw_end_cb;

	std::unique_ptr<uint16_t []> m_vram;
	std::unique_ptr<uint16_t []> m_fb[2];
	// double density interlace: each field of a displayed frame holds only the lines of one parity, so
	// a copy of the field that was displayed before is kept (the erase follows the display)
	std::unique_ptr<uint16_t []> m_field_copy[2];
	unsigned m_field_cur = 0;
	bool m_disp_die = false, m_disp_dil = false;   // DIE/DIL the displayed buffer was drawn with
	bool m_prev_die = false, m_prev_dil = false;   // the same for the copy of the previous field
	saturn_vdp1::draw_engine m_engine;

	// registers
	uint16_t m_tvmr = 0, m_fbcr = 0, m_ptmr = 0;
	uint16_t m_ewdr = 0, m_ewlr = 0, m_ewrr = 0;
	uint16_t m_edsr = 0;          // bit 1 CEF, bit 0 BEF
	uint16_t m_lopr = 0;
	bool m_die = false, m_dil = false;   // latched at draw start and frame change

	unsigned m_draw_fb = 0;       // frame buffer being drawn into; the other one is displayed

	// command list execution
	enum class phase { fetch, decode, next };
	bool m_drawing = false;
	uint32_t m_cmd_addr = 0;      // word address of the current command table
	int32_t m_ret_addr = -1;
	phase m_phase = phase::fetch;
	uint16_t m_cmd[16] = {};
	int32_t m_budget = 0;         // VDP1 clocks of drawing time available
	attotime m_last_time;

	// diagnostics (environment variable SATURN_VDP1_LOG): one line per frame change
	struct frame_stats {
		unsigned cmd[16] = {};     // commands executed, by command code
		unsigned skipped = 0, jumps = 0, calls = 0, returns = 0, ended = 0, invalid = 0;
	} m_stats;
	bool m_log = false;
	void log_frame();

	// frame handling
	bool m_vblank = false, m_hblank = false;
	bool m_manual_pending = false;
	bool m_vb_erase_pending = false;
	bool m_vb_erase_active = false;
	attotime m_vblank_start;

	struct erase_params {
		unsigned x_start = 0, x_bound = 0, y_start = 0, y_end = 0;
		uint16_t data = 0;
		unsigned x_mask = 0x1ff;
		bool rot8 = false;
	} m_erase;
	unsigned m_erase_y = ~0U;     // next row of the frame erase, ~0 when none is running

	emu_timer *m_vbe_timer = nullptr;
	TIMER_CALLBACK_MEMBER(vbe_sample);

	void vram_access_wait();
	void start_drawing();
	void stop_drawing();
	void run();
	void frame_change();
	void latch_erase_params();
	void erase_row(unsigned y);
	void erase_limited(int64_t budget);
	uint32_t fb_word_index(uint32_t word) const;
	uint16_t *display_buffer() const { return m_fb[m_draw_fb ^ 1].get(); }
};

DECLARE_DEVICE_TYPE(SATURN_VDP1, saturn_vdp1_device)

#endif // MAME_SEGA_SATURN_VDP1_H

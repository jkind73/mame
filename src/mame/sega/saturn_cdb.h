// license:BSD-3-Clause
// copyright-holders:David Haywood
#ifndef MAME_SEGA_SATURN_CDB_H
#define MAME_SEGA_SATURN_CDB_H
#pragma once
#include "cpu/sh/sh7032.h"
#include "imagedev/cdromimg.h"
#include "sound/cdda.h"
DECLARE_DEVICE_TYPE(SATURN_CDB, saturn_cdb_device)

// Firmware executes host commands. These registers model the YGR019 bridge,
// not a second command interpreter. Drive mechanics are a separate serial peer.
class saturn_cdb_device : public device_t
{
  public:
	saturn_cdb_device(const machine_config &, const char *, device_t *, uint32_t);
	template <typename T> void set_cdrom_tag(T &&tag)
	{
		m_cdrom.set_tag(std::forward<T>(tag));
	}
	template <typename T> void set_cdda_tag(T &&tag)
	{
		m_cdda.set_tag(std::forward<T>(tag));
	}
	void set_tray_open();
	void set_tray_close();
	void set_host_wait_callback(std::function<void(bool)> cb)
	{
		m_host_wait_cb = std::move(cb);
	}
	void set_host_notify_callback(std::function<void()> cb)
	{
		m_host_notify_cb = std::move(cb);
	}
	bool host_bus_ready(u32 address, unsigned size, bool write) const;
	void set_lle(bool enabled)
	{
		m_enabled = enabled;
	}
	void saturn_cdb_map(address_map &map) ATTR_COLD;
	void amap(address_map &map) ATTR_COLD;

  protected:
	void device_start() override ATTR_COLD;
	void device_reset() override ATTR_COLD;
	const tiny_rom_entry *device_rom_region() const override ATTR_COLD;
	void device_add_mconfig(machine_config &config) override ATTR_COLD;

  private:
	std::function<void(bool)> m_host_wait_cb;
	std::function<void()> m_host_notify_cb;
	required_device<sh7032_device> m_cpu;
	optional_device<cdrom_image_device> m_cdrom;
	optional_device<cdda_device> m_cdda;
	u8 m_drive_state = 0x12, m_after_seek = 0x46, m_speed = 2, m_seek_frames = 0, m_ring_phase = 0;
	u32 m_fad = 150, m_toc_position = 0;
	int m_scan_step = 1;
	bool m_tray_open = false, m_reading = false, m_sector_audio = false;
	u8 m_sector[2352]{};
	u16 m_sector_offset = 2352, m_cd_word = 0;
	emu_timer *m_sector_timer = nullptr, *m_dreq_timer = nullptr;
	void drive_command();
	void drive_report();
	void load_sector();
	TIMER_CALLBACK_MEMBER(sector_word);
	TIMER_CALLBACK_MEMBER(sector_request_clear);
	bool m_enabled = false;
	uint16_t m_command[4]{}, m_response[4]{}, m_hirq = 0, m_hmask = 0;
	uint16_t m_trctl = 0, m_irql = 0, m_irqu = 0, m_maskl = 0, m_masku = 0, m_reg1a = 0;
	uint32_t m_host_underflow = 0, m_host_overflow = 0;
	uint16_t m_fifo[6]{};
	uint8_t m_fifo_read = 0, m_fifo_write = 0, m_fifo_count = 0;
	bool m_fifo_first = true;
	bool m_fifo_pending = false;
	uint16_t m_portb = 0xc50f;
	uint8_t m_drive_status[12]{}, m_drive_command[13]{};
	uint8_t m_link_byte = 0, m_link_bit = 0, m_link_rx = 0;
	int m_txd = 1, m_sck = 1;
	bool m_link_active = false;
	emu_timer *m_frame_timer = nullptr, *m_request_timer = nullptr;
	void restore_lines();
	void update_irq();
	void update_request();
	void fifo_push(uint16_t data);
	uint16_t fifo_pop(bool raw = false);
	uint16_t asic_r(offs_t offset);
	void asic_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t host_r(offs_t offset);
	void host_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t dma_host_r();
	void dma_host_w(uint16_t data);
	uint16_t portb_r()
	{
		return m_portb;
	}
	void txd_w(int state)
	{
		m_txd = state;
	}
	void sck_w(int state);
	TIMER_CALLBACK_MEMBER(drive_frame);
	TIMER_CALLBACK_MEMBER(drive_request);
};
#endif

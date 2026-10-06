// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  SH7604 cache (SH7604 hardware manual, section 8).

  4 KB, four-way set associative, mixed instruction/data: 64 entries
  selected by address bits 9-4, 16-byte lines, a 19-bit tag (address bits
  28-10) and a valid bit per way, and six pseudo-LRU bits per entry. The
  cache has no snoop function (8.5.2-8.5.3).

  This file holds the cache state and its operations; the CPU core decides
  when to use them. The behaviour follows the manual and MiSTer's
  SH7604/CACHE.sv (Saturn_MiSTer), which agree on every point used here:
  - LRU update on read hits, write hits and replacement (Table 8.3), and the
    replaced way (Table 8.4). The four conditions of Table 8.4 are mutually
    exclusive; LRU values that match none (possible only after an address
    array write, 8.4.5) replace nothing.
  - Two-way mode (TW) replaces only ways 2 and 3, chosen by LRU bit 0
    (8.4.5; CACHE.sv WayFromLRU), while tags are still compared in all four
    ways.
  - A line fill reads four longwords starting after the one that holds the
    requested address, so that longword comes last (8.4.1, Figure 8.4).
  - CP clears every valid bit and all LRU bits (8.2, 8.4.6).
  - An associative purge clears the valid bit of each way whose tag matches
    (8.4.7; CACHE.sv compares the tag only).
  - Address array read: tag in bits 28-10, LRU in bits 9-4, valid in bit 2,
    for the way selected by CCR W1/W0. Write: tag from address bits 28-10,
    valid from address bit 2, LRU from data bits 9-4 (8.4.9, Figure 8.11).
  - Data array: way from address bits 11-10, entry from 9-4, byte from 3-0
    (8.4.8, Figure 8.10).
*/

#ifndef MAME_CPU_SH_SH7604_CACHE_H
#define MAME_CPU_SH_SH7604_CACHE_H

#pragma once

#include <cstdint>

class sh7604_cache
{
public:
	static constexpr unsigned ENTRIES = 64;
	static constexpr unsigned WAYS = 4;

	// CCR bits (Table 8.1)
	static constexpr uint8_t CCR_CE = 0x01; // cache enable
	static constexpr uint8_t CCR_ID = 0x02; // instruction replacement disable
	static constexpr uint8_t CCR_OD = 0x04; // data replacement disable
	static constexpr uint8_t CCR_TW = 0x08; // two-way mode
	static constexpr uint8_t CCR_CP = 0x10; // cache purge (write only)

	uint32_t ccr = 0;                     // 8-bit register; 32 bits so the DRC can test it in place
	uint32_t tag[ENTRIES][WAYS] = {};     // address bits 28-10
	uint8_t valid[ENTRIES][WAYS] = {};
	uint8_t lru[ENTRIES] = {};
	uint32_t line[ENTRIES][WAYS][4] = {}; // longwords; byte 0 of a line is bits 31-24 of line[..][0]

	static unsigned entry(uint32_t address) { return (address >> 4) & 0x3f; }
	static uint32_t tag_of(uint32_t address) { return (address >> 10) & 0x7ffff; }

	bool enabled() const { return ccr & CCR_CE; }

	// CCR write: CP purges and always reads back 0; bit 5 is reserved.
	void write_ccr(uint8_t data)
	{
		if (data & CCR_CP)
			purge_all();
		ccr = data & ~(CCR_CP | 0x20);
	}

	// The way holding address, or -1 on a miss.
	int find(uint32_t address) const
	{
		unsigned const e = entry(address);
		uint32_t const t = tag_of(address);
		for (unsigned w = 0; w < WAYS; w++)
			if (valid[e][w] && tag[e][w] == t)
				return w;
		return -1;
	}

	// Table 8.3: LRU information after an access to way w.
	void touch(unsigned e, unsigned w)
	{
		static constexpr uint8_t keep[WAYS] = { 0x07, 0x19, 0x2a, 0x34 };
		static constexpr uint8_t set[WAYS] = { 0x00, 0x20, 0x14, 0x0b };
		lru[e] = (lru[e] & keep[w]) | set[w];
	}

	// Table 8.4: the way to replace, or -1 when the LRU bits select none.
	int replacement(unsigned e) const
	{
		uint8_t const l = lru[e];
		if (ccr & CCR_TW)
			return (l & 0x01) ? 2 : 3;
		if ((l & 0x38) == 0x38)
			return 0;
		if ((l & 0x26) == 0x06)
			return 1;
		if ((l & 0x15) == 0x01)
			return 2;
		if ((l & 0x0b) == 0x00)
			return 3;
		return -1;
	}

	void purge_all()
	{
		for (unsigned e = 0; e < ENTRIES; e++)
		{
			lru[e] = 0;
			for (unsigned w = 0; w < WAYS; w++)
				valid[e][w] = 0;
		}
	}

	void purge_line(uint32_t address)
	{
		unsigned const e = entry(address);
		uint32_t const t = tag_of(address);
		for (unsigned w = 0; w < WAYS; w++)
			if (tag[e][w] == t)
				valid[e][w] = 0;
	}

	// Allocates way w of address's entry and fills it; bus_read(address)
	// returns the longword at a longword-aligned address. The requested
	// longword is read last.
	template <typename Read>
	void fill(uint32_t address, unsigned w, Read &&bus_read)
	{
		unsigned const e = entry(address);
		uint32_t const base = address & ~uint32_t(0xf);
		tag[e][w] = tag_of(address);
		valid[e][w] = 1;
		for (unsigned i = 1; i <= 4; i++)
		{
			unsigned const index = ((address >> 2) + i) & 3;
			line[e][w][index] = bus_read(base + index * 4);
		}
	}

	// A read of size 1, 2 or 4 bytes from way w's line.
	uint32_t read_line(unsigned e, unsigned w, uint32_t address, unsigned size) const
	{
		uint32_t const l = line[e][w][(address >> 2) & 3];
		unsigned const shift = (4 - size - (address & 3)) * 8;
		return size == 4 ? l : (l >> shift) & ((1U << (size * 8)) - 1);
	}

	void write_line(unsigned e, unsigned w, uint32_t address, unsigned size, uint32_t data)
	{
		uint32_t &l = line[e][w][(address >> 2) & 3];
		if (size == 4)
		{
			l = data;
			return;
		}
		unsigned const shift = (4 - size - (address & 3)) * 8;
		uint32_t const mask = ((1U << (size * 8)) - 1) << shift;
		l = (l & ~mask) | ((data << shift) & mask);
	}

	// Address array (8.4.9): the way is CCR W1/W0.
	uint32_t read_address_array(uint32_t address) const
	{
		unsigned const e = entry(address);
		unsigned const w = ccr >> 6;
		return (tag[e][w] << 10) | (uint32_t(lru[e]) << 4) | (uint32_t(valid[e][w]) << 2);
	}

	void write_address_array(uint32_t address, uint32_t data)
	{
		unsigned const e = entry(address);
		unsigned const w = ccr >> 6;
		tag[e][w] = tag_of(address);
		valid[e][w] = (address >> 2) & 1;
		lru[e] = (data >> 4) & 0x3f;
	}

	// Data array (8.4.8): a longword of way bits 11-10, entry bits 9-4.
	uint32_t &data_array(uint32_t address)
	{
		return line[entry(address)][(address >> 10) & 3][(address >> 2) & 3];
	}
};

#endif // MAME_CPU_SH_SH7604_CACHE_H

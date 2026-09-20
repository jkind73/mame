// license:BSD-3-Clause
// copyright-holders:David Haywood, Angelo Salese

/* Notes

YGR019B - Hitachi YGR019B CD-Subsystem LSI. Earlier revision is YGR019A. Later revision combines this IC and the SH1 together
        into one IC (YGR022 315-5962). The SH1 and the YGR019B make up the 'CD Block' CD Authentication and CD I/O data controller.
        Another of it's functions is to prevent copied CDs from being played

The YGR019B ("OCU") is an address decoder, a host interface and a set of
registers around a Hitachi SH-1 (SH7032).  It does not hold firmware itself:
the CD block ROM is a separate 64KB mask ROM that the SH-1 executes from
address 0, and the SH-1's own 4KB of on-chip RAM at 0x0f000000 holds the
firmware's scheduler, task queue and command state.  The block also has 512KB
of DRAM at 0x09000000 for the TOC, the filter/partition tables and the sector
buffers.

Register map (the SH-1 sees the YGR registers at 0x0a000000, the SH-2 hosts
see the same registers in the 0x05800000-0x058fffff window):

    SH-1            host offset   register
    +0x00           0x00          DATA      host <-> CD block transfer FIFO
    +0x02                         TRCTL     bit 0 DIR (0 = CD block to host,
                                            1 = host to CD block), bit 1 RES
                                            (reset FIFO), bit 2 TE (transfer
                                            enable)
    +0x04                         CDIRQL    bit 0 CMD (host wrote the command
                                            registers), bit 1 RESP (host read
                                            the response registers)
    +0x06                         CDIRQU    bit 4 DET (sector transfer done)
    +0x08, +0x0a                  CDMSKL/U  interrupt masks for the two SH-1
                                            interrupt lines
    +0x0c, +0x0e                  REG0C/0E
    +0x10..+0x16                  CR1-CR4   command registers, written by the
                                            host and read by the firmware
    +0x18, +0x1a, +0x1c           REG18/1A/1C
    +0x1e           0x08          HIRQ      interrupt requests to the host
                    0x0c          HIRQMASK  host interrupt mask
                    0x18,0x1c,0x20,0x24     RR1-RR4 response registers, written
                                            by the firmware and read by the host
                    0x28                    MPEG express registers (Video CD card)

The register window is mirrored every 64 bytes inside a 4KB block, and those
blocks repeat every 32KB across 0x05800000-0x058fffff.

Interrupts: the two YGR lines arrive on the SH-1's IRQ6 (CDIRQL & CDMSKL) and
IRQ7 (CDIRQU & CDMSKU); HIRQ & HIRQMASK drives the CD block interrupt to the
main CPUs.  The transfer FIFO drives the SH-1's DMAC channel 1 external DREQ
input, which is how the firmware moves sectors in and out of DRAM.

Sources: srg320/Saturn_hw CDB/cdb105.inc (the firmware's own register and RAM
map, from the disassembled cdb105 ROM) and CDB/YGR.xlsx (bit assignments),
cross-checked against Ymir's LLE CD block (libs/ymir-core/src/ymir/hw/cdblock/
ygr.cpp) and the Saturn CD interface manual.
*/

#ifndef MAME_SEGA_SATURN_CDB_H
#define MAME_SEGA_SATURN_CDB_H

#pragma once

#include "cpu/sh/sh7032.h"
#include "saturn_cdblock.h"

class saturn_cdb_device : public device_t, public saturn_cdblock_interface
{
public:
	// construction/destruction
	saturn_cdb_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	// Memory map of the SH-1's own bus.
	void cdb_map(address_map &map) ATTR_COLD;

	// saturn_cdblock_interface: host (SH-2) register window access.  The
	// window is mirrored every 0x8000 from 0x05800000 (YGR register sheet).
	virtual uint16_t host_r(offs_t offset, uint16_t mem_mask = ~0) override;
	virtual void host_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0) override;

	// Sector transfer completion, to be driven by the drive once it is
	// emulated: raises CDIRQU's DET request.
	void sector_transfer_done();

protected:
	// device-level overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_add_mconfig(machine_config &config) override ATTR_COLD;
	virtual const tiny_rom_entry *device_rom_region() const override ATTR_COLD;

private:
	required_device<sh7032_device> m_cdbcpu;
	required_shared_ptr<uint16_t> m_dram;

	static constexpr int FIFO_SIZE = 8; // "depth 6-8 words" (YGR register sheet)

	// YGR registers
	struct
	{
		uint16_t trctl = 0;
		uint16_t cdirql = 0;
		uint16_t cdirqu = 0;
		uint16_t cdmskl = 0;
		uint16_t cdmsku = 0;
		uint16_t reg0c = 0;
		uint16_t reg0e = 0;
		uint16_t reg18 = 0;
		uint16_t reg1a = 0;
		uint16_t reg1c = 0;
		uint16_t hirq = 0;
		uint16_t hirqmask = 0;
		uint16_t cr[4] = { 0, 0, 0, 0 }; // host command registers
		uint16_t rr[4] = { 0, 0, 0, 0 }; // firmware response registers
	} m_ygr;

	// Transfer FIFO between the host and the SH-1
	uint16_t m_fifo[FIFO_SIZE] = { 0, };
	int m_fifo_head = 0;
	int m_fifo_tail = 0;
	int m_fifo_count = 0;

	// SH-1 side of the YGR registers
	uint16_t ygr_r(offs_t offset, uint16_t mem_mask);
	void ygr_w(offs_t offset, uint16_t data, uint16_t mem_mask);

	void fifo_clear();
	void fifo_push(uint16_t data);
	uint16_t fifo_pop();
	bool fifo_empty() const { return m_fifo_count == 0; }
	bool fifo_full() const { return m_fifo_count == FIFO_SIZE; }

	void update_irq();
	void update_dreq();
};

DECLARE_DEVICE_TYPE(SATURN_CDB, saturn_cdb_device)

#endif // MAME_SEGA_SATURN_CDB_H

// license:BSD-3-Clause
// copyright-holders:David Haywood, Angelo Salese

// Saturn CD block (YGR019B "OCU" plus its SH-1) low level emulation.
// See saturn_cdb.h for the register map and its provenance.

#include "emu.h"
#include "saturn_cdb.h"

#define LOG_YGR (1U << 1)
#define LOG_FIFO (1U << 2)

#define VERBOSE (0)
#include "logmacro.h"

DEFINE_DEVICE_TYPE(SATURN_CDB, saturn_cdb_device, "satcdb", "Saturn CDB (CD Block)")

saturn_cdb_device::saturn_cdb_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, SATURN_CDB, tag, owner, clock)
	, m_cdbcpu(*this, "cdbcpu")
	, m_dram(*this, "dram")
	, m_host_irq_cb(*this)
{
}

// ---------------------------------------------------------------------------
// Host (SH-2) interface
// ---------------------------------------------------------------------------

uint16_t saturn_cdb_device::host_r(offs_t offset, uint16_t mem_mask)
{
	offset &= 0x3c;

	switch (offset)
	{
	case 0x00: // DATA
		// A read only makes sense for a CD block to host transfer.
		if (BIT(m_ygr.trctl, 0))
			return 0;
		return fifo_pop();

	case 0x08: // HIRQ
		return m_ygr.hirq;

	case 0x0c: // HIRQMASK
		return m_ygr.hirqmask;

	case 0x18:
	case 0x1c:
	case 0x20:
		return m_ygr.rr[offset >> 2 & 3];

	case 0x24:
		// Reading the last response register latches the "periodic response"
		// request for the firmware (YGR register sheet: bit 1 of CDIRQL).
		m_ygr.cdirql |= 0x0002;
		update_irq();
		return m_ygr.rr[3];

	case 0x28: // MPEG express registers, Video CD card only
		return 0;

	default:
		LOGMASKED(LOG_YGR, "%s: unhandled host read from %02x\n", machine().describe_context(), offset);
		return 0;
	}
}

void saturn_cdb_device::host_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	offset &= 0x3c;

	switch (offset)
	{
	case 0x00: // DATA
		// The FIFO has a direction: a host write only takes effect for a
		// host to CD block transfer (TRCTL DIR = 1).
		if (BIT(m_ygr.trctl, 0))
			fifo_push(data);
		break;

	case 0x08: // HIRQ: the host clears requests by writing zeroes
		m_ygr.hirq &= data;
		update_irq();
		break;

	case 0x0c: // HIRQMASK
		m_ygr.hirqmask = data;
		update_irq();
		break;

	case 0x18:
	case 0x1c:
	case 0x20:
		m_ygr.cr[offset >> 2 & 3] = data;
		break;

	case 0x24:
		m_ygr.cr[3] = data;
		// Command delivered: the write to the last command register raises
		// the CMD request for the firmware (YGR register sheet p.2, and the
		// trigger point the HLE device uses as well).
		m_ygr.cdirql |= 0x0001;
		update_irq();
		break;

	case 0x28: // MPEG express registers, Video CD card only
		break;

	default:
		LOGMASKED(LOG_YGR, "%s: unhandled host write to %02x = %04x\n", machine().describe_context(), offset, data);
		break;
	}
}

// ---------------------------------------------------------------------------
// SH-1 side of the YGR registers
// ---------------------------------------------------------------------------

uint16_t saturn_cdb_device::ygr_r(offs_t offset, uint16_t mem_mask)
{
	switch (offset & 0x1e)
	{
	case 0x00: // DATA
	{
		// Draining the last word of a host to CD block transfer re-arms the
		// transfer enable (YGR register sheet: TE is released by hardware).
		if (!BIT(m_ygr.trctl, 2) && BIT(m_ygr.trctl, 0) && m_fifo_count == 1)
			m_ygr.trctl |= 0x0004;
		return fifo_pop();
	}

	case 0x02:
		return m_ygr.trctl;
	case 0x04:
		return m_ygr.cdirql;
	case 0x06:
		return m_ygr.cdirqu;
	case 0x08:
		return m_ygr.cdmskl;
	case 0x0a:
		return m_ygr.cdmsku;
	case 0x0c:
		return m_ygr.reg0c;
	case 0x0e:
		return m_ygr.reg0e;
	case 0x10:
	case 0x12:
	case 0x14:
	case 0x16:
		return m_ygr.cr[offset >> 1 & 3];
	case 0x18:
		return m_ygr.reg18;
	case 0x1a:
		return m_ygr.reg1a;
	case 0x1c:
		return m_ygr.reg1c;
	case 0x1e:
		return m_ygr.hirq;
	}

	return 0;
}

void saturn_cdb_device::ygr_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	LOGMASKED(LOG_YGR, "%s: YGR %02x = %04x & %04x\n", machine().describe_context(), offset & 0x1e, data, mem_mask);

	switch (offset & 0x1e)
	{
	case 0x00: // DATA
		fifo_push(data);
		// Writing the FIFO ends the fill phase of a host to CD block transfer.
		if (BIT(m_ygr.trctl, 2) && BIT(m_ygr.trctl, 0))
			m_ygr.trctl &= ~0x0004;
		update_dreq();
		break;

	case 0x02: // TRCTL
		m_ygr.trctl = data & 0x000f;
		if (BIT(m_ygr.trctl, 1))
			fifo_clear();
		update_dreq();
		break;

	case 0x04: // CDIRQL: the firmware writes zeroes to clear the requests
		m_ygr.cdirql = data & 0x0003;
		update_irq();
		break;

	case 0x06: // CDIRQU: write zero to clear
		m_ygr.cdirqu &= data;
		update_irq();
		break;

	case 0x08:
		m_ygr.cdmskl = data & 0x0003;
		update_irq();
		break;

	case 0x0a:
		m_ygr.cdmsku = data & 0x0070;
		update_irq();
		break;

	case 0x0c:
		m_ygr.reg0c = data & 0x0003;
		break;

	case 0x0e:
		m_ygr.reg0e = data;
		break;

	case 0x10:
	case 0x12:
	case 0x14:
	case 0x16: // RR1-RR4, read back by the host as DR1-DR4
		m_ygr.rr[offset >> 1 & 3] = data;
		break;

	case 0x18:
		m_ygr.reg18 = data & 0x003f;
		break;

	case 0x1a:
		m_ygr.reg1a = data & 0x00d7;
		break;

	case 0x1c:
		m_ygr.reg1c = data & 0x00ff;
		break;

	case 0x1e: // HIRQ: the firmware raises requests to the host
		m_ygr.hirq |= data & 0x3fff;
		update_irq();
		break;
	}
}

// ---------------------------------------------------------------------------
// Interrupts and the transfer FIFO
// ---------------------------------------------------------------------------

void saturn_cdb_device::update_irq()
{
	// Two SH-1 lines: the "low" bank on IRQ6 and the "high" bank on IRQ7.
	m_cdbcpu->set_input_line(6, (m_ygr.cdirql & m_ygr.cdmskl) ? ASSERT_LINE : CLEAR_LINE);
	m_cdbcpu->set_input_line(7, (m_ygr.cdirqu & m_ygr.cdmsku) ? ASSERT_LINE : CLEAR_LINE);

	// HIRQ & HIRQMASK is the CD block interrupt line to the main CPUs.
	m_host_irq_cb((m_ygr.hirq & m_ygr.hirqmask) ? 1 : 0);
}

void saturn_cdb_device::update_dreq()
{
	// The FIFO drives the SH-1's DMAC channel 1 external request input.  A
	// transfer can proceed while the FIFO has room in the direction it is
	// being used (YGR register sheet; the same condition Ymir's
	// UpdateFIFODREQ uses).
	bool const allowed = BIT(m_ygr.trctl, 2) && !(BIT(m_ygr.trctl, 0) ? fifo_empty() : fifo_full());
	m_cdbcpu->set_dreq_input(1, allowed ? 1 : 0);
}

void saturn_cdb_device::fifo_clear()
{
	m_fifo_head = m_fifo_tail = m_fifo_count = 0;
}

void saturn_cdb_device::fifo_push(uint16_t data)
{
	if (fifo_full())
	{
		LOGMASKED(LOG_FIFO, "%s: FIFO overrun, dropping %04x\n", machine().describe_context(), data);
		return;
	}

	m_fifo[m_fifo_tail] = data;
	m_fifo_tail = (m_fifo_tail + 1) % FIFO_SIZE;
	m_fifo_count++;
	update_dreq();
}

uint16_t saturn_cdb_device::fifo_pop()
{
	if (fifo_empty())
	{
		LOGMASKED(LOG_FIFO, "%s: FIFO underrun\n", machine().describe_context());
		return 0;
	}

	uint16_t const data = m_fifo[m_fifo_head];
	m_fifo_head = (m_fifo_head + 1) % FIFO_SIZE;
	m_fifo_count--;
	update_dreq();
	return data;
}

void saturn_cdb_device::sector_transfer_done()
{
	// Set by the drive interface once a sector lands in the block's DRAM.
	// The request is level-held until the firmware clears it.
	m_ygr.cdirqu |= 0x0010;
	update_irq();
}

// ---------------------------------------------------------------------------
// Device plumbing
// ---------------------------------------------------------------------------

// The CD block's own bus: 64KB firmware ROM at 0, 512KB of DRAM at 0x09000000
// and the YGR register file at 0x0a000000 (srg320/Saturn_hw CDB/cdb105.inc).
void saturn_cdb_device::cdb_map(address_map &map)
{
	map(0x00000000, 0x0000ffff).rom().region("cdbcpu", 0);
	map(0x09000000, 0x097fffff).ram().share("dram");
	map(0x0a000000, 0x0a00001f).rw(FUNC(saturn_cdb_device::ygr_r), FUNC(saturn_cdb_device::ygr_w));
}

void saturn_cdb_device::device_add_mconfig(machine_config &config)
{
	// The CD block's SH-1 now executes the real firmware instead of being
	// held disabled.
	SH7032(config, m_cdbcpu, DERIVED_CLOCK(1, 1));
	m_cdbcpu->set_addrmap(AS_PROGRAM, &saturn_cdb_device::cdb_map);
}

void saturn_cdb_device::device_start()
{
	save_item(NAME(m_ygr.trctl));
	save_item(NAME(m_ygr.cdirql));
	save_item(NAME(m_ygr.cdirqu));
	save_item(NAME(m_ygr.cdmskl));
	save_item(NAME(m_ygr.cdmsku));
	save_item(NAME(m_ygr.reg0c));
	save_item(NAME(m_ygr.reg0e));
	save_item(NAME(m_ygr.reg18));
	save_item(NAME(m_ygr.reg1a));
	save_item(NAME(m_ygr.reg1c));
	save_item(NAME(m_ygr.hirq));
	save_item(NAME(m_ygr.hirqmask));
	save_item(NAME(m_ygr.cr));
	save_item(NAME(m_ygr.rr));
	save_item(NAME(m_fifo));
	save_item(NAME(m_fifo_head));
	save_item(NAME(m_fifo_tail));
	save_item(NAME(m_fifo_count));
}

void saturn_cdb_device::device_reset()
{
	m_ygr.trctl = 0x0000;
	m_ygr.cdirql = 0x0000;
	m_ygr.cdirqu = 0x0000;
	m_ygr.cdmskl = 0x0000;
	m_ygr.cdmsku = 0x0000;
	m_ygr.reg0c = 0x0000;
	m_ygr.reg0e = 0x0000;
	m_ygr.reg18 = 0x0000;
	m_ygr.reg1a = 0x0000;
	m_ygr.reg1c = 0x0000;
	m_ygr.hirq = 0x0000;
	m_ygr.hirqmask = 0x0000;
	for (int i = 0; i < 4; ++i)
	{
		m_ygr.cr[i] = 0x0000;
		m_ygr.rr[i] = 0x0000;
	}
	fifo_clear();
	update_irq();
	update_dreq();
}

/* The ROM region is named after the CPU tag because the SH-1 fetches it
   straight through its own address space.  Three revisions are dumped:
   cdb105/cdb106 are the standalone YGR019A/YGR019B pairing and ygr022 is the
   combined package. */
ROM_START( satcdb )
	ROM_REGION( 0x10000, "cdbcpu", 0 )
	ROM_DEFAULT_BIOS("cdb106")
	ROM_SYSTEM_BIOS( 0, "cdb106", "Saturn CD Block 1.06" )
	ROMX_LOAD( "cdb106.bin", 0x00000, 0x10000, CRC(3681d3b0) SHA1(b3c20fbe57cd2eb595e9edac86817e5948dccae4), ROM_BIOS(0) ) // for YGR019B?
	ROM_SYSTEM_BIOS( 1, "cdb105", "Saturn CD Block 1.05" )
	ROMX_LOAD( "cdb105.bin", 0x00000, 0x10000, CRC(2a2ced5c) SHA1(eb8393058f324e922c11b43709b64fc6ca94ab86), ROM_BIOS(1) ) // for YGR019A?
	ROM_SYSTEM_BIOS( 2, "ygr022", "Saturn CD Block (YGR022 315-5962)" )
	ROMX_LOAD( "ygr022.bin", 0x00000, 0x10000, CRC(1c8b9f38) SHA1(f4f6c2aac68c352814d396ae41f81f54ad228e68), ROM_BIOS(2) ) // combined package?
ROM_END

const tiny_rom_entry *saturn_cdb_device::device_rom_region() const
{
	return ROM_NAME(satcdb);
}

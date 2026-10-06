// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont
/*
  Saturn / ST-V: time the two SH-2s spend on the shared external bus.

  The SH-2 core calls sh2_bus_cycles() for every access that leaves the chip:
  uncached and cache-through reads and writes, write-through writes of the
  cache area, instruction fetches outside the cache and cache line fills
  (fill: four longwords). Cache hits and on-chip accesses cost nothing. The
  result is the number of SH-2 cycles the access takes beyond the one the
  core's instruction timing already counts for it.

  Sources, in order of preference:
  - Sega's documents say what exists: "When external access conflicts between
    the master CPU and slave CPU, one of the CPUs is forced to wait for
    access, resulting in a decrease in execution speed" (STN-28, How to use
    dual CPU), and the SH7604 manual 7.10 describes the bus arbitration (a
    pending request is granted when the bus cycle ends). They give no cycle
    counts.
  - The hardware probe (a real console, NTSC 320 dot mode) measured what an
    access to the chips behind the SCU costs the SH-2 over a plain one: see
    cpu_bus_waits().
  - Mednafen 1.32.1 (ss.cpp BusRW_DB_CS0/CS3, sh7095.inc BSC_BusRead /
    BSC_BusWrite), whose author measured the rest on hardware: the CS0 area
    (BIOS, SMPC, backup RAM, Work RAM-L, 16 bit bus), Work RAM-H (SDRAM), the
    bus controller's idle cycle and the slave's bus request. Only measured
    numbers were used, none of its code.
*/

#include "emu.h"
#include "saturn.h"

#include <algorithm>
#include <cstdlib>
#include <utility>


// Extra SH-2 clocks an access to the SCU's buses and chips takes over a plain one, measured on a
// real console (hardware probe log "sav1", NTSC 320 mode; the timer ticks are FRT phi/32, so
// clocks per access = (ticks - baseline ticks) * 32 / count of each BUS_* result):
//   reads:  SCSP regs and sound RAM 47, VDP1 VRAM 28, VDP1 frame buffer 26, VDP1 registers 24,
//           VDP2 VRAM 40 (8 bit), VDP2 CRAM 19, VDP2 registers 39, SCU registers 7,
//           A-Bus CS0 50, CD block (CS2) 16
//   writes: SCSP 15 (29 for 32 bit), VDP1 7 (8 for 32 bit), VDP2 VRAM 1 (2 for 32 bit, 28 for 8 bit),
//           VDP2 CRAM 1 (2 for 32 bit)
// Writes to the work RAMs and the on-chip registers are the other end: 0 and 1. Virtua Fighter 2
// loses its sound effects when the SH-2s get to the SCSP and the video chips too quickly (Ymir
// notes), reads being the slow direction there.
// Not measured by the probe and left out: writes to the SCU registers, the A-Bus areas and the
// SMPC.
unsigned saturn_state::cpu_bus_waits(uint32_t address, bool write, unsigned bits)
{
	address &= 0x07ffffff;
	switch ((address >> 20) & 0x7f)
	{
	case 0x20: case 0x21: case 0x22: case 0x23: case 0x24: case 0x25: case 0x26: case 0x27:
	case 0x28: case 0x29: case 0x2a: case 0x2b: case 0x2c: case 0x2d: case 0x2e: case 0x2f:
	case 0x30: case 0x31: case 0x32: case 0x33: case 0x34: case 0x35: case 0x36: case 0x37:
	case 0x38: case 0x39: case 0x3a: case 0x3b: case 0x3c: case 0x3d: case 0x3e: case 0x3f:
	case 0x40: case 0x41: case 0x42: case 0x43: case 0x44: case 0x45: case 0x46: case 0x47:
	case 0x48: case 0x49: case 0x4a: case 0x4b: case 0x4c: case 0x4d: case 0x4e: case 0x4f:
		return write ? 0 : 50;                                   // A-Bus CS0, CS1
	case 0x58:
		return write ? 0 : 16;                                   // CS2: CD block
	case 0x5a:
	case 0x5b:
		return write ? (bits > 16 ? 29 : 15) : 47;               // SCSP
	case 0x5c:
		if (address < 0x05c80000)
			return write ? (bits > 16 ? 8 : 7) : 28;             // VDP1 VRAM
		return write ? (bits > 16 ? 8 : 7) : 26;                 // VDP1 frame buffer
	case 0x5d:
		return write ? 7 : 24;                                   // VDP1 registers
	case 0x5e:
		return write ? (bits <= 8 ? 28 : bits > 16 ? 2 : 1) : 40;   // VDP2 VRAM
	case 0x5f:
		if (address < 0x05f80000)
			return write ? (bits > 16 ? 2 : 1) : 19;             // VDP2 CRAM
		if (address < 0x05fc0000)
			return write ? 1 : 39;                               // VDP2 registers
		if (address >= 0x05fe0000 && address < 0x05ff0000)
			return write ? 0 : 7;                                // SCU registers
		return 0;
	default:
		return 0;
	}
}


/*
  The cost of one access in SH-2 cycles from the time it starts, bus waits
  included, before the arbitration with the other CPU. The SDRAM stays busy
  for a little while after a write: the CPU's next SDRAM access waits for it.
  The finish times are machine times, since a CPU's cycle count restarts when
  the CPU is reset.
*/
int saturn_state::sh2_bus_cycles(unsigned cpu, offs_t address, unsigned size, bool write, bool fill, attotime now)
{
	sh7604_device &exec = cpu ? *m_slave : *m_maincpu;
	auto const until = [&exec, &now] (const attotime &free) -> uint64_t
	{
		return free > now ? exec.attotime_to_cycles(free - now) : 0;
	};
	uint64_t t = 0;
	uint32_t const a = address & 0x07ffffff;

	if (a < 0x02000000)
	{
		// CS0, a 16 bit bus: a longword is two accesses and a line fill eight. Per 16 bit access:
		// BIOS ROM 8, SMPC 0, backup RAM 8, Work RAM-L 7, MINIT/SINIT 8, anything else 4
		unsigned per = 4;
		if (a < 0x00100000)
			per = 8;
		else if (a < 0x00180000)
			per = 0;
		else if (a < 0x00200000)
			per = 8;
		else if (a < 0x00400000)
			per = 7;
		else if (a >= 0x01000000)
			per = 8;
		else if (m_stv_ioga && a < 0x00400080)
			per = 0;
		t = per * (fill ? 8 : size == 4 ? 2 : 1);
	}
	else if (a >= 0x06000000)
	{
		// CS3, Work RAM-H: a read takes 7 (a whole line fill too, the SDRAM bursts), a write 2,
		// and the SDRAM stays busy for 2 more after a write
		t = until(m_sh2_sdram_free[cpu]);
		if (write)
		{
			t += 2;
			m_sh2_sdram_free[cpu] = now + exec.cycles_to_attotime(t + 2);
		}
		else
			t += 7;
	}
	else
	{
		// the chips behind the SCU, as measured by the probe (they are the extra clocks, so one
		// is added for the access itself)
		t = 1 + cpu_bus_waits(address, write, size * 8) * (fill ? 4 : 1);
	}

	uint64_t const total = sh2_bus_arbitrate(cpu * 2, now, t, address, write);
	return int(std::min<uint64_t>(total, 0x7fff'ffff)) - (total ? 1 : 0);
}


// On by default (it restores the Virtua Fighter 2 sound effects); SATURN_BUS_TIMING=0 turns it off.
// Ymir notes that some games need fast and others slow timings.
bool saturn_state::sh2_bus_timing_enabled()
{
	char const *const env = std::getenv("SATURN_BUS_TIMING");
	return !(env && std::strtol(env, nullptr, 0) == 0);
}


// A loaded state starts with a free bus: the logs of the time before the load would otherwise
// hold the bus into the restored time.
void saturn_state::sh2_bus_reset()
{
	for (unsigned i = 0; i < BUS_REQUESTERS; i++)
	{
		m_sh2_bus_log[i].clear();
		m_sh2_bus_debt[i] = attotime::zero;
		m_sh2_bus_debt_from[i] = attotime::never;
	}
	for (unsigned i = 0; i < 2; i++)
	{
		m_bsc_last_end[i] = attotime::zero;
		m_sh2_sdram_free[i] = attotime::zero;
	}
}


/*
  The two SH-2s share one external bus (and each SH-2's on-chip DMAC uses it
  too). The master owns it and the slave requests it; whichever holds the bus
  completes its bus cycle before another requester gets it, and a pending
  request is granted when the bus cycle ends (SH7604 manual 7.10; the DMAC
  drives the same bus controller as its CPU). Mednafen serialises every
  access on one bus timestamp, a CPU's own accesses included.

  MAME runs the CPUs in turn, a slice each (the master first), so no shared
  "bus busy until" time can be used: it would make a CPU that is behind wait
  for the whole gap to one that ran ahead. Every access instead records the
  interval it holds the bus, in machine time, per requester; it starts no
  earlier than the requester's own previous bus cycle ends, and when it meets
  an interval of another requester it
  - waits for its end when the other requester got the bus first;
  - otherwise keeps the bus: it got there first, or it was waiting while the
    other requester held the bus and is granted it before that requester's
    next, back to back, bus cycle. The other requester has already run past
    that point: it is charged the delay at its next access, and its logged
    intervals from there on count as delayed by it, so later accesses see the
    bus where the other requester really held it.
  The result does not depend on the order in which MAME runs the requesters.
  The posted-write tails (SDRAM busy after a write) and the bus controller
  state stay per CPU. Returns the cycles the access takes from now, waits
  included.
*/
uint64_t saturn_state::sh2_bus_arbitrate(unsigned requester, const attotime &now, uint64_t cycles, offs_t address, bool write)
{
	unsigned const cpu = requester >> 1;
	sh7604_device &exec = cpu ? *m_slave : *m_maincpu;
	auto &log = m_sh2_bus_log[requester];

	// A delay owed pushes this requester's bus work since the late access back by that much, the
	// intervals already logged included, so the others see the bus where this one really held it,
	// gaps and all.
	attotime start = now;
	if (attotime const delay = std::exchange(m_sh2_bus_debt[requester], attotime::zero); !delay.is_zero())
	{
		start += delay;
		auto late = std::lower_bound(log.begin(), log.end(), m_sh2_bus_debt_from[requester],
				[] (const bus_interval &i, const attotime &t) { return i.start < t; });
		for (; late != log.end(); ++late)
		{
			late->start += delay;
			late->end += delay;
		}
	}
	m_sh2_bus_debt_from[requester] = attotime::never;
	if (!log.empty() && log.back().end > start)
		start = log.back().end;

	// Per-CPU bus controller costs (Mednafen 1.32.1 sh7095.inc BSC_BusRead, BSC_BusWrite):
	// - master: an access that starts right as its previous one ended costs an idle cycle more
	//   when it is a read of another area (CS0-CS3, address bits 26-25) or a write after a read;
	// - slave: every access first requests the bus from the master, 2 cycles when it has not held
	//   the bus in the last cycle, else 1, before a read and 1 before a write; a read releases it
	//   in 1 more cycle, a write in 1 more after the SDRAM busy time that follows an SDRAM write.
	//   (The idle cycle never applies to the slave: its request moves it past the end of its
	//   previous access.)
	unsigned const area = (address >> 25) & 3;
	bool const sdram = (address & 0x07ff'ffff) >= 0x0600'0000;
	attotime const one = exec.cycles_to_attotime(1);
	auto const bsc_extra = [&] (const attotime &at) -> uint64_t
	{
		if (cpu == 0)
			return (at == m_bsc_last_end[0] && (write ? m_bsc_last_read[0] : area != m_bsc_last_area[0])) ? 1 : 0;
		uint64_t const request = write ? 1 : (at > m_bsc_last_end[1] + one ? 2 : 1);
		uint64_t const release = write ? (sdram ? 3 : 1) : 1;
		return request + release;
	};
	uint64_t extra = bsc_extra(start);
	attotime length = exec.cycles_to_attotime(cycles + extra);

	// an interval of requester o, with the delay o owes applied
	auto const shifted = [this] (unsigned o, const bus_interval &i)
	{
		attotime const late = i.start >= m_sh2_bus_debt_from[o] ? m_sh2_bus_debt[o] : attotime::zero;
		return bus_interval{ i.start + late, i.end + late };
	};
	auto const first_meeting = [&] (unsigned o)
	{
		auto &other = m_sh2_bus_log[o];
		return std::lower_bound(other.begin(), other.end(), start - m_sh2_bus_debt[o],
				[] (const bus_interval &i, const attotime &t) { return i.end <= t; });
	};

	// first wait for every interval that got the bus first; waiting for one can move the access
	// into another's
	bool held[BUS_REQUESTERS] = {}; // requester o held the bus until start
	for (bool moved = true; moved; )
	{
		moved = false;
		for (unsigned o = 0; o < BUS_REQUESTERS; o++)
		{
			if (o == requester)
				continue;
			for (auto it = first_meeting(o); it != m_sh2_bus_log[o].end(); ++it)
			{
				bus_interval const i = shifted(o, *it);
				if (i.end <= start)
					continue;
				if (i.start >= start + length || i.start > start || (i.start == start && held[o]))
					break;
				start = i.end; // o had the bus first
				held[o] = true;
				moved = true;
				// waiting changes whether the access follows this CPU's previous one directly
				extra = bsc_extra(start);
				length = exec.cycles_to_attotime(cycles + extra);
			}
		}
	}

	// then the access keeps the bus against every requester that ran past it
	for (unsigned o = 0; o < BUS_REQUESTERS; o++)
	{
		if (o == requester)
			continue;
		for (auto it = first_meeting(o); it != m_sh2_bus_log[o].end(); ++it)
		{
			bus_interval const i = shifted(o, *it);
			if (i.end <= start)
				continue;
			if (i.start >= start + length)
				break;
			m_sh2_bus_debt[o] += start + length - i.start;
			if (m_sh2_bus_debt_from[o] == attotime::never)
				m_sh2_bus_debt_from[o] = it->start;
			break;
		}
	}

	cycles += extra;
	if (cycles)
	{
		log.push_back({ start, start + length });
		m_bsc_last_end[cpu] = start + length;
		m_bsc_last_area[cpu] = area;
		m_bsc_last_read[cpu] = !write;
	}

	// only the other requesters' current slices can meet these intervals
	attotime const horizon = now - attotime::from_msec(2);
	while (!log.empty() && log.front().end < horizon)
		log.pop_front();

	// a wait ends on a clock edge
	attotime const wait = start - now;
	uint64_t waited = exec.attotime_to_cycles(wait);
	if (exec.cycles_to_attotime(waited) < wait)
		++waited;
	return waited + cycles;
}

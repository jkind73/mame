// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont
// Frozen pre-optimization arbitration method for differential checks.
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

// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont
/*
  Saturn / ST-V: types of the SH-2 external bus timing and arbitration
  (saturn_bus.cpp). The functions themselves are members of saturn_state.
*/

#ifndef MAME_SEGA_SATURN_BUS_H
#define MAME_SEGA_SATURN_BUS_H

#pragma once

#include <vector>

namespace saturn_bus {

// an interval, in machine time, during which a requester held the shared external bus
struct interval
{
	attotime start, end;
};

// Arbitration searches recent intervals repeatedly. Keep them contiguous so
// binary searches do not resolve a deque block for every inspected interval.
// Expiry advances a head; occasional compaction amortizes removal costs.
class interval_history
{
public:
	auto begin() { return m_intervals.begin() + m_head; }
	auto end() { return m_intervals.end(); }
	bool empty() const { return m_head == m_intervals.size(); }
	interval const &front() const { return m_intervals[m_head]; }
	interval const &back() const { return m_intervals.back(); }
	void push_back(interval const &i) { m_intervals.push_back(i); }
	void clear() { m_intervals.clear(); m_head = 0; }
	void pop_front()
	{
		++m_head;
		if (empty())
			clear();
		else if (m_head >= 4096 && m_head >= m_intervals.size() / 2)
		{
			m_intervals.erase(m_intervals.begin(), m_intervals.begin() + m_head);
			m_head = 0;
		}
	}

private:
	std::vector<interval> m_intervals;
	std::size_t m_head = 0;
};

// the requesters of the shared bus: each SH-2 and, later, its DMAC (requester = cpu * 2 + dma)
constexpr unsigned REQUESTERS = 4;

} // namespace saturn_bus

#endif // MAME_SEGA_SATURN_BUS_H

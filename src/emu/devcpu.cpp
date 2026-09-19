// license:BSD-3-Clause
// copyright-holders:Aaron Giles
/***************************************************************************

    devcpu.cpp

    CPU device definitions.

***************************************************************************/

#include "emu.h"
#include "emuopts.h"
#include <cctype>


//**************************************************************************
//  CPU RUNNING DEVICE
//**************************************************************************

//-------------------------------------------------
//  cpu_device - constructor
//-------------------------------------------------

cpu_device::cpu_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, u32 clock) :
	device_t(mconfig, type, tag, owner, clock),
	device_execute_interface(mconfig, *this),
	device_memory_interface(mconfig, *this),
	device_state_interface(mconfig, *this),
	device_disasm_interface(mconfig, *this),
	m_force_no_drc(false),
	m_access_to_be_redone(false),
	m_access_before_delay_tag(nullptr)
{
}


//-------------------------------------------------
//  cpu_device - destructor
//-------------------------------------------------

cpu_device::~cpu_device()
{
}


//-------------------------------------------------
//  allow_drc - return true if DRC is allowed
//-------------------------------------------------

bool cpu_device::allow_drc() const
{
	return mconfig().options().drc() && !m_force_no_drc;
}



bool cpu_device::cpu_is_interruptible() const
{
	return false;
}

bool cpu_device::access_before_time(u64 access_time, u64 current_time) noexcept
{
	s32 delta = access_time - current_time;
	if(*m_icountptr <= delta) {
		defer_access();
		return true;
	}

	*m_icountptr -= delta;

	return false;
}

bool cpu_device::access_before_delay(u32 cycles, const void *tag) noexcept
{
	if(tag == m_access_before_delay_tag) {
		m_access_before_delay_tag = nullptr;
		return false;
	}

	// For Saturn/ST-V BUS-01/04 faithful retry: cycles >=1024 indicates forced retry
	// (bus owned or device not ready). Must abort timeslice regardless of remaining icount
	// so that SH2 interpreter snapshot restore (sh2.cpp) and DRC icount guard (sh.cpp)
	// rewind R15 pre-decrement / post-inc side-effects and retry the transaction.
	if(cycles >= 1024) {
		// Force abort: ensure icount <=0 so both interpreter and DRC exit current block
		if(*m_icountptr > 0)
			*m_icountptr = 0;
		else
			*m_icountptr -= cycles; // keep negative for accounting
		m_access_before_delay_tag = tag;
		m_access_to_be_redone = true;
		return true;
	}

	*m_icountptr -= cycles;

	if(*m_icountptr <= 0) {
		m_access_before_delay_tag = tag;
		m_access_to_be_redone = true;
		return true;
	}

	m_access_before_delay_tag = nullptr;
	return false;
}

void cpu_device::access_after_delay(u32 cycles) noexcept
{
	*m_icountptr -= cycles;
}

void cpu_device::defer_access() noexcept
{
	if(*m_icountptr > 0)
		*m_icountptr = 0;
	m_access_to_be_redone = true;
}

void cpu_device::retry_access() noexcept
{
	abort_timeslice();
	m_access_to_be_redone = true;
}

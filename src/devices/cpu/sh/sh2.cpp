// license:BSD-3-Clause
// copyright-holders:Juergen Buchmueller, R. Belmont
/*****************************************************************************
 *
 *   sh2.cpp
 *   Portable Hitachi SH-2 (SH7600 family) emulator
 *
 *  This work is based on <tiraniddo@hotmail.com> C/C++ implementation of
 *  the SH-2 CPU core and was adapted to the MAME CPU core requirements.
 *  Thanks also go to Chuck Mason <chukjr@sundail.net> and Olivier Galibert
 *  <galibert@pobox.com> for letting me peek into their SEMU code :-)
 *
 *****************************************************************************/


#include "emu.h"
#include "sh2.h"

#include "sh2fe.h"
#include "sh_dasm.h"

#include "cpu/drcumlsh.h"

#include "endianness.h"

#include <bit>

//#define VERBOSE 1
#include "logmacro.h"

constexpr int SH2_INT_15 = 15;

sh2_device::sh2_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, int cpu_type, address_map_constructor internal_map, int addrlines, uint32_t address_mask, size_t code_cache_size)
	: sh_common_execution(mconfig, type, tag, owner, clock, ENDIANNESS_BIG, internal_map, code_cache_size)
	, m_bus_ready(*this)
	, m_bus_observer(*this)
	, m_bus_timing(*this)
	, m_program_config("program", ENDIANNESS_BIG, 32, addrlines, 0, internal_map)
	, m_decrypted_program_config("decrypted_opcodes", ENDIANNESS_BIG, 32, addrlines, 0)
	, m_drcfe(nullptr)
{
	m_cpu_type = cpu_type;
	m_am = address_mask;
	m_isdrc = allow_drc();
}

sh2_device::~sh2_device()
{
}

void sh2_device::device_start()
{
	m_bus_ready.resolve();
	save_item(NAME(m_bus_wait_monitor));
	m_bus_observer.resolve();
	m_bus_observed = !m_bus_observer.isnull();
	m_bus_timing.resolve();
	m_bus_timed = !m_bus_timing.isnull();

	sh_common_execution::device_start();

	m_decrypted_program = has_space(AS_OPCODES) ? &space(AS_OPCODES) : &space(AS_PROGRAM);
	m_decrypted_program->cache(m_cache32);
	m_pr16 = [this](offs_t address) -> u16 { return m_cache32.read_word(address); };
	if (m_decrypted_program->endianness() != ENDIANNESS_NATIVE)
		m_prptr = [this](offs_t address) -> const void * {
			const u16 *ptr = reinterpret_cast<u16 *>(m_cache32.read_ptr(address & ~3));
			if (!(address & 2))
				ptr++;
			return ptr;
		};
	else
		m_prptr = [this](offs_t address) -> const void * {
			const u16 *ptr = reinterpret_cast<u16 *>(m_cache32.read_ptr(address & ~3));
			if (address & 2)
				ptr++;
			return ptr;
		};

	// internals
	save_item(NAME(m_cpu_off));
	save_item(NAME(m_test_irq));
	save_item(NAME(m_zero_delay_pending));
	save_item(NAME(m_irq_line_state));
	save_item(NAME(m_nmi_line_state));
	save_item(NAME(m_internal_irq_vector));

	state_add(STATE_GENPC, "PC", m_sh2_state->pc).mask(m_am).callimport();
	state_add(STATE_GENPCBASE, "CURPC", m_sh2_state->pc).callimport().noshow();

	m_nmi_line_state = 0;

	drc_start();
}

void sh2_device::device_reset()
{
	std::fill(std::begin(m_sh2_state->r), std::end(m_sh2_state->r), 0);
	std::fill(std::begin(m_irq_line_state), std::end(m_irq_line_state), 0);

	m_sh2_state->pc = m_sh2_state->pr = m_sh2_state->sr = m_sh2_state->gbr = m_sh2_state->vbr = m_sh2_state->mach = m_sh2_state->macl = 0;
	m_sh2_state->evec = m_sh2_state->irqsr = 0;
	m_sh2_state->ea = m_sh2_state->m_delay = 0;
	m_zero_delay_pending = false;
	m_sh2_state->pending_irq = 0;
	m_sh2_state->pending_nmi = 0;
	m_sh2_state->sleep_mode = 0;
	m_sh2_state->internal_irq_level = -1;
	m_sh2_state->sr = SH_I;
	m_sh2_state->pc = read_long(m_manual_reset ? 8 : 0);
	m_sh2_state->r[15] = read_long(m_manual_reset ? 12 : 4);
	m_manual_reset = false;

	m_test_irq = 0;
	m_cpu_off = 0;
	m_internal_irq_vector = 0;
	m_cache_dirty = true;
}

device_memory_interface::space_config_vector sh2_device::memory_space_config() const
{
	if (has_configured_map(AS_OPCODES))
		return space_config_vector
		{
			std::make_pair(AS_PROGRAM, &m_program_config),
			std::make_pair(AS_OPCODES, &m_decrypted_program_config)
		};
	else
		return space_config_vector
		{
			std::make_pair(AS_PROGRAM, &m_program_config)
		};
}

std::unique_ptr<util::disasm_interface> sh2_device::create_disassembler()
{
	return std::make_unique<sh_disassembler>(false);
}

static void cfunc_cache_access(void *param) { ((sh2_device *)param)->func_cache_access(); }
static void cfunc_cached_instruction(void *param) { ((sh2_device *)param)->execute_monitored(); }

// SH7604 cache (section 8), when the driver enables the model. A read of
// the cache area with CE set is served from the cache; a miss replaces the
// way the LRU selects and fills its line from the bus, unless OD (data) or
// ID (instruction fetch) disables replacement or the LRU selects no way, in
// which case the access goes to the bus as is (8.4.1, 8.4.5). The LRU is
// updated on hits and replacements (Table 8.3).
uint32_t sh2_device::cache_read(offs_t address, unsigned size, bool instruction)
{
	unsigned const e = sh7604_cache::entry(address);
	int w = m_cache.find(address);
	if (w < 0)
	{
		if ((m_cache.ccr & (instruction ? sh7604_cache::CCR_ID : sh7604_cache::CCR_OD)) || (w = m_cache.replacement(e)) < 0)
		{
			bus_charge(address, size, false);
			switch (size)
			{
			case 1: return external_data_read(address & m_am, 1);
			case 2: return external_data_read(address & m_am, 2);
			default: return external_data_read(address & m_am, 4);
			}
		}
		bus_charge(address, 16, false, true);
		m_cache.fill(address, w, [this] (uint32_t a) { return external_data_read(a & m_am, 4); });
	}
	m_cache.touch(e, w);
	return m_cache.read_line(e, w, address, size);
}

// Writes go through to the bus whether or not they hit; a hit also updates
// the cached copy and the LRU (8.4.2). Cache-through writes do not touch
// the cache (8.4.3), which is how a cached copy goes stale.
void sh2_device::cache_write(offs_t address, unsigned size, uint32_t data)
{
	int const w = m_cache.find(address);
	if (w >= 0)
	{
		unsigned const e = sh7604_cache::entry(address);
		m_cache.touch(e, w);
		m_cache.write_line(e, w, address, size, data);
	}
}

// DRC side of the cache: m_cache_op 0 reads m_cache_size bytes at
// m_cache_addr into m_cache_data, 1 updates the cache for a write of
// m_cache_data, 2 is an instruction fetch.
void sh2_device::func_cache_access()
{
	switch (m_cache_op)
	{
	case 0:
		m_cache_data = cache_read(m_cache_addr, m_cache_size, false);
		break;
	case 1:
		cache_write(m_cache_addr, m_cache_size, m_cache_data);
		bus_charge(m_cache_addr, m_cache_size, true);
		break;
	case 2:
		m_fetch_data = cache_read(m_cache_addr, 4, true);
		m_fetch_cached = 1;
		break;
	case 5: // CS2 endian conversion uses the same path as the interpreter
		if (m_bus_write)
		{
			if (m_cache_size == 1) write_byte(m_cache_addr, m_cache_data);
			else if (m_cache_size == 2) write_word(m_cache_addr, m_cache_data);
			else write_long(m_cache_addr, m_cache_data);
		}
		else
			m_cache_data = m_cache_size == 1 ? read_byte(m_cache_addr) : m_cache_size == 2 ? read_word(m_cache_addr) : read_long(m_cache_addr);
		break;
	case 3: // an access that goes straight to the bus
		if (m_tas_read && !m_bus_write)
			m_tas_read = 0;
		bus_charge(m_cache_addr, m_cache_size, m_bus_write);
		break;
	default: // an instruction fetch from the bus: CE clear or cache-through
		m_fetch_cached = cache_area(m_cache_addr);
		if (m_fetch_cached)
			m_fetch_data = cache_read(m_cache_addr, 4, true);
		else
			bus_charge(m_cache_addr, 4, false);
		break;
	}
}

// Cache mismatch is rare, but saving every mapped guest register at every
// instruction site bloats the translated working set. Share the identical exit.
void sh2_device::static_generate_cpu_helpers()
{
	// Keep the uncommon instruction-boundary exit out of every translated
	// instruction. I1 supplies its uncharged cycles without changing the bus clock
	// bookkeeping on a path that never starts the instruction.
	alloc_handle(m_slice_exhausted, "slice_exhausted");
	drcuml_block &slice(m_drcuml->begin_block(16));
	UML_HANDLE(slice, *m_slice_exhausted);
	UML_GETEXP(slice, I0);
	UML_MOV(slice, mem(&m_sh2_state->pc), I0);
	save_fast_iregs(slice);
	UML_SUB(slice, mem(&m_sh2_state->icount), mem(&m_sh2_state->icount), I1);
	UML_EXIT(slice, EXECUTE_OUT_OF_CYCLES);
	slice.end();

	alloc_handle(m_bus_instruction, "bus_instruction");
	drcuml_block &bus(m_drcuml->begin_block(32));
	UML_HANDLE(bus, *m_bus_instruction);
	UML_GETEXP(bus, I0);
	save_fast_iregs(bus);
	UML_MOV(bus, mem(&m_sh2_state->pc), I0);
	UML_SUB(bus, mem(&m_sh2_state->icount), mem(&m_sh2_state->icount), mem(&m_bus_pending));
	UML_MOV(bus, mem(&m_fetch_reuse), 0);
	UML_CALLC(bus, cfunc_cached_instruction, this);
	UML_EXIT(bus, EXECUTE_OUT_OF_CYCLES);
	bus.end();

	alloc_handle(m_cached_instruction, "cached_instruction");
	drcuml_block &block(m_drcuml->begin_block(32));
	UML_HANDLE(block, *m_cached_instruction);
	UML_GETEXP(block, I0);
	save_fast_iregs(block);
	UML_MOV(block, mem(&m_sh2_state->pc), I0);
	UML_SUB(block, mem(&m_sh2_state->icount), mem(&m_sh2_state->icount), mem(&m_bus_pending));
	UML_MOV(block, mem(&m_fetch_reuse), 1);
	UML_CALLC(block, cfunc_cached_instruction, this);
	UML_EXIT(block, EXECUTE_OUT_OF_CYCLES);
	block.end();

	// Instruction fetches dominate cache traffic. A hit needs only the tag
	// comparisons, the documented LRU update and a cached longword load.
	// Misses and uncached fetches retain the shared bus/fill implementation.
	alloc_handle(m_instruction_fetch, "instruction_fetch");
	drcuml_block &fetch(m_drcuml->begin_block(160));
	UML_HANDLE(fetch, *m_instruction_fetch);
	constexpr int slow = 1;
	if (!m_cache_model)
		UML_JMP(fetch, slow);
	UML_TEST(fetch, mem(&m_cache.ccr), sh7604_cache::CCR_CE);
	UML_JMPc(fetch, COND_Z, slow);
	UML_MOV(fetch, I0, mem(&m_cache_addr));
	UML_CMP(fetch, I0, 0x20000000);
	UML_JMPc(fetch, COND_AE, slow);
	UML_SHR(fetch, I1, I0, 10);
	UML_AND(fetch, I1, I1, 0x7ffff);
	UML_SHR(fetch, I0, I0, 4);
	UML_AND(fetch, I0, I0, 0x3f);
	static constexpr uint8_t keep[4] = { 0x07, 0x19, 0x2a, 0x34 };
	static constexpr uint8_t set[4] = { 0x00, 0x20, 0x14, 0x0b };
	for (unsigned w = 0; w < 4; ++w)
	{
		int const next = 2 + w;
		UML_SHL(fetch, I3, I0, 2);
		UML_ADD(fetch, I3, I3, w);
		UML_LOAD(fetch, I2, &m_cache.valid[0][0], I3, SIZE_BYTE, SCALE_x1);
		UML_CMP(fetch, I2, 0);
		UML_JMPc(fetch, COND_E, next);
		UML_LOAD(fetch, I2, &m_cache.tag[0][0], I3, SIZE_DWORD, SCALE_x4);
		UML_CMP(fetch, I2, I1);
		UML_JMPc(fetch, COND_NE, next);
		UML_LOAD(fetch, I2, &m_cache.lru[0], I0, SIZE_BYTE, SCALE_x1);
		UML_AND(fetch, I2, I2, keep[w]);
		UML_OR(fetch, I2, I2, set[w]);
		UML_STORE(fetch, &m_cache.lru[0], I0, I2, SIZE_BYTE, SCALE_x1);
		UML_SHL(fetch, I3, I3, 2);
		UML_SHR(fetch, I2, mem(&m_cache_addr), 2);
		UML_AND(fetch, I2, I2, 3);
		UML_ADD(fetch, I3, I3, I2);
		UML_LOAD(fetch, I2, &m_cache.line[0][0][0], I3, SIZE_DWORD, SCALE_x4);
		UML_MOV(fetch, mem(&m_fetch_data), I2);
		UML_MOV(fetch, mem(&m_fetch_cached), 1);
		UML_RET(fetch);
		UML_LABEL(fetch, next);
	}
	UML_LABEL(fetch, slow);
	UML_CALLC(fetch, cfunc_cache_access, this);
	UML_RET(fetch);
	fetch.end();
}

// Instruction fetches (DRC), by the interpreter's rule: a fetch for every
// instruction that starts a longword, and for one in the second half of a
// longword when the previous instruction was not the one just before it
// (after a jump, an exception or a block entry). m_fetch_pc holds the PC of
// the previous instruction at run time; only the second-half instructions
// that can be reached out of sequence (sequence starts and branch targets)
// test it. Cached opcodes that differ from the compiled RAM sequence are
// executed by the shared interpreter for the remainder of the slice.
void sh2_device::generate_instruction_fetch(drcuml_block &block, compiler_state &compiler, const opcode_desc *desc, bool sequence_start, uint32_t ovrpc)
{
	// Bus waits can exhaust the slice before the end of a compiled sequence.
	// Stop before starting another instruction, as the interpreter does, rather
	// than performing its memory side effects before the next cycle update.
	// Native delayed branches finish their slot before returning to the scheduler.
	if (m_bus_timed && !desc->in_delay_slot())
	{
		uml::code_label const running = compiler.labelnum++;
		int const pending = compiler.cycles - desc->cycles;
		UML_CMP(block, mem(&m_sh2_state->icount), pending);
		UML_JMPc(block, COND_G, running);
		UML_MOV(block, I1, pending);
		UML_EXH(block, *m_slice_exhausted, desc->pc);
		UML_LABEL(block, running);
	}
	bool const timed = (m_bus_timed || m_bus_observed) && desc->pc < 0x40000000;
	bool const cached = m_cache_model && desc->pc < 0x20000000;
	if (m_bus_timed || m_bus_observed || m_track_pending)
		UML_MOV(block, mem(&m_bus_pending), compiler.cycles - desc->cycles);
	// CS2 opcode storage may be lane-converted. Its raw front-end decode
	// cannot be used as a native instruction; fetch it through the bus model.
	if (desc->pc < 0x40000000 && (desc->pc & 0x06000000) == 0x04000000)
	{
		int const ordinary = compiler.labelnum++;
		UML_CMP(block, mem(&m_bus_endian_width), 0);
		UML_JMPc(block, COND_E, ordinary);
		UML_MOV(block, mem(&m_bus_pending), compiler.cycles - desc->cycles);
		if (ovrpc == SH_OVRPC_DYNAMIC)
			UML_MOV(block, mem(&m_sh2_state->m_delay), mem(&m_sh2_state->target));
		else if (ovrpc != SH_OVRPC_NONE)
			UML_MOV(block, mem(&m_sh2_state->m_delay), ovrpc + 2);
		UML_EXH(block, *m_bus_instruction, desc->pc);
		UML_LABEL(block, ordinary);
	}
	if (!timed && !cached)
		return;
	uml::code_label const skip = compiler.labelnum++;
	if (desc->pc & 2)
	{
		uml::code_label const fetch = compiler.labelnum++;
		if (cached)
		{
			uml::code_label const ordinary = compiler.labelnum++;
			UML_TEST(block, mem(&m_cache.ccr), sh7604_cache::CCR_CE);
			UML_JMPc(block, COND_Z, ordinary);
			UML_TEST(block, mem(&m_fetch_cached), 1);
			UML_JMPc(block, COND_Z, fetch);
			UML_LABEL(block, ordinary);
		}
		if (!sequence_start && !desc->is_branch_target())
			UML_JMP(block, skip);
		else
		{
			UML_CMP(block, mem(&m_fetch_pc), desc->pc - 2);
			UML_JMPc(block, COND_E, skip);
		}
		UML_LABEL(block, fetch);
	}
	if (!timed)
	{
		// cache only: a fetch touches the cache when it is on
		UML_TEST(block, mem(&m_cache.ccr), sh7604_cache::CCR_CE);
		UML_JMPc(block, COND_Z, skip);
	}
	UML_MOV(block, mem(&m_cache_addr), desc->pc & ~3);
	UML_MOV(block, mem(&m_cache_op), timed ? 4 : 2);  // 4: from the cache when it is on, else from the bus
	UML_CALLH(block, *m_instruction_fetch);
	UML_LABEL(block, skip);
	UML_MOV(block, mem(&m_fetch_pc), desc->pc);
	if (cached)
	{
		uml::code_label const uncached = compiler.labelnum++;
		uml::code_label const matches = compiler.labelnum++;
		UML_TEST(block, mem(&m_cache.ccr), sh7604_cache::CCR_CE);
		UML_JMPc(block, COND_Z, uncached);
		UML_SHR(block, I0, mem(&m_fetch_data), (desc->pc & 2) ? 0 : 16);
		UML_AND(block, I0, I0, 0xffff);
		UML_CMP(block, I0, desc->opptr);
		UML_JMPc(block, COND_E, matches);
		UML_MOV(block, mem(&m_bus_pending), compiler.cycles - desc->cycles);
		// A native branch may already have executed before its cached delay slot
		// differs. Preserve that branch's target when handing the slot to the interpreter.
		if (ovrpc == SH_OVRPC_DYNAMIC)
			UML_MOV(block, mem(&m_sh2_state->m_delay), mem(&m_sh2_state->target));
		else if (ovrpc != SH_OVRPC_NONE)
			UML_MOV(block, mem(&m_sh2_state->m_delay), ovrpc + 2);
		UML_EXH(block, *m_cached_instruction, desc->pc);
		UML_LABEL(block, uncached);
		UML_MOV(block, mem(&m_fetch_cached), 0);
		UML_LABEL(block, matches);
	}
}

// BCR1.ENDIAN changes data lanes within each external bus beat, not the
// address. Bytes keep their lane; words reverse two lanes; a 16-bit bus
// transfers the high longword half first and reverses each half separately.
uint32_t sh2_device::external_data_read(uint32_t address, unsigned size)
{
	bool const little = m_bus_endian_width && address < 0x40000000 && (address & 0x06000000) == 0x04000000;
	if (size == 1)
		return m_program->read_byte(address);
	if (size == 2)
	{
		uint16_t const data = m_program->read_word(address);
		return little ? swapendian_int16(data) : data;
	}
	if (little && m_bus_endian_width == 2)
	{
		uint16_t const high = m_program->read_word(address);
		uint16_t const low = m_program->read_word(address + 2);
		return (uint32_t(swapendian_int16(high)) << 16) | swapendian_int16(low);
	}
	uint32_t const data = m_program->read_dword(address);
	return little ? swapendian_int32(data) : data;
}

void sh2_device::external_data_write(uint32_t address, unsigned size, uint32_t data)
{
	bool const little = m_bus_endian_width && address < 0x40000000 && (address & 0x06000000) == 0x04000000;
	if (size == 1)
		m_program->write_byte(address, data);
	else if (size == 2)
		m_program->write_word(address, little ? swapendian_int16(uint16_t(data)) : data);
	else if (little && m_bus_endian_width == 2)
	{
		m_program->write_word(address, swapendian_int16(uint16_t(data >> 16)));
		m_program->write_word(address + 2, swapendian_int16(uint16_t(data)));
	}
	else
		m_program->write_dword(address, little ? swapendian_int32(data) : data);
}

uint8_t sh2_device::read_byte(offs_t offset)
{
	// TAS.B reads memory directly, even in the cache area (8.4.4)
	bool const tas = m_tas_read;
	m_tas_read = 0;
	if (!tas && cache_area(offset))
		return cache_read(offset, 1, false);
	if (offset < 0x40000000)
	{
		bus_charge(offset, 1, false);
		return external_data_read(offset & m_am, 1);
	}

	return m_program->read_byte(offset);
}

uint16_t sh2_device::read_word(offs_t offset)
{
	if (cache_area(offset))
		return cache_read(offset, 2, false);
	if (offset < 0x40000000)
	{
		bus_charge(offset, 2, false);
		return external_data_read(offset & m_am, 2);
	}

	return m_program->read_word(offset);
}

uint32_t sh2_device::read_long(offs_t offset)
{
	if (cache_area(offset))
		return cache_read(offset, 4, false);
	// The cached (0x00000000) and cache-through (0x20000000) windows
	// end up mirroring each other
	if (offset < 0x40000000)
	{
		bus_charge(offset, 4, false);
		return external_data_read(offset & m_am, 4);
	}
	return m_program->read_dword(offset);
}

uint16_t sh2_device::decrypted_read_word(offs_t offset)
{
	if (m_bus_endian_width && offset < 0x40000000 && (offset & 0x06000000) == 0x04000000)
		return swapendian_int16(m_decrypted_program->read_word(offset));
	return m_decrypted_program->read_word(offset);
}

void sh2_device::write_byte(offs_t offset, uint8_t data)
{
	if (cache_area(offset))
		cache_write(offset, 1, data);
	if (offset < 0x40000000)
	{
		bus_charge(offset, 1, true);
		external_data_write(offset & m_am, 1, data);
		return;
	}

	m_program->write_byte(offset, data);
}

void sh2_device::write_word(offs_t offset, uint16_t data)
{
	if (cache_area(offset))
		cache_write(offset, 2, data);
	if (offset < 0x40000000)
	{
		bus_charge(offset, 2, true);
		external_data_write(offset & m_am, 2, data);
		return;
	}

	m_program->write_word(offset, data);
}

void sh2_device::write_long(offs_t offset, uint32_t data)
{
	if (cache_area(offset))
		cache_write(offset, 4, data);
	if (offset < 0x40000000)
	{
		bus_charge(offset, 4, true);
		external_data_write(offset & m_am, 4, data);
		return;
	}

	m_program->write_dword(offset, data);
}

void sh2_device::check_pending_irq(const char *message)
{
	if (m_sh2_state->pending_nmi)
	{
		sh2_exception(message, 16);
		m_sh2_state->pending_nmi = 0;
	}
	else
	{
		int irq = m_sh2_state->internal_irq_level;
		if (m_sh2_state->pending_irq)
		{
			int external_irq = std::bit_width(m_sh2_state->pending_irq) - 1;
			if (external_irq >= irq)
			{
				irq = external_irq;
			}
		}

		if (irq >= 0)
		{
			sh2_exception(message, irq);
		}
	}
}

/*  LDC.L   @Rm+,SR */
inline void sh2_device::LDCMSR(const uint16_t opcode) // passes Rn
{
	const uint32_t rn = REG_N;
	m_sh2_state->ea = m_sh2_state->r[rn];
	m_sh2_state->sr = read_long(m_sh2_state->ea) & SH_FLAGS;
	m_sh2_state->r[rn] += 4;
	m_sh2_state->icount -= 2;
	m_test_irq = 1;
}

/*  LDC     Rm,SR */
inline void sh2_device::LDCSR(const uint16_t opcode) // passes Rn
{
	m_sh2_state->sr = m_sh2_state->r[REG_N] & SH_FLAGS;
	m_test_irq = 1;
}

/*  RTE */
inline void sh2_device::RTE()
{
	m_sh2_state->ea = m_sh2_state->r[15];
	m_sh2_state->m_delay = read_long(m_sh2_state->ea);
	m_sh2_state->r[15] += 4;
	m_sh2_state->ea = m_sh2_state->r[15];
	m_sh2_state->sr = read_long(m_sh2_state->ea) & SH_FLAGS;
	m_sh2_state->r[15] += 4;
	m_sh2_state->icount -= 3;
	m_test_irq = 1;
}

/*  TRAPA   #imm */
inline void sh2_device::TRAPA(uint32_t i)
{
	uint32_t imm = i & 0xff;
	debugger_exception_hook(imm);

	m_sh2_state->ea = m_sh2_state->vbr + imm * 4;

	m_sh2_state->r[15] -= 4;
	write_long(m_sh2_state->r[15], m_sh2_state->sr);
	m_sh2_state->r[15] -= 4;
	write_long(m_sh2_state->r[15], m_sh2_state->pc);

	m_sh2_state->pc = read_long(m_sh2_state->ea);

	m_sh2_state->icount -= 7;
}

/*  ILLEGAL */
inline void sh2_device::ILLEGAL()
{
	//logerror("Illegal opcode at %08x\n", m_sh2_state->pc - 2);
	unsigned const vector = m_in_delay_slot ? 6 : 4;
	debugger_exception_hook(vector);

	m_sh2_state->r[15] -= 4;
	write_long(m_sh2_state->r[15], m_sh2_state->sr);     /* push SR onto stack */
	m_sh2_state->r[15] -= 4;
	write_long(m_sh2_state->r[15], m_in_delay_slot ? m_sh2_state->pc : m_sh2_state->pc - 2); /* slot saves the delayed jump address (4.5.3) */

	/* fetch PC */
	m_sh2_state->pc = read_long(m_sh2_state->vbr + vector * 4) & m_am;

	/* TODO: timing is a guess */
	m_sh2_state->icount -= 5;
}

bool sh2_device::is_slot_illegal(uint16_t op) const
{
	if (m_cpu_type != CPU_TYPE_SH2)
		return false;
	// SH7604 Table 4.9: every PC-writing instruction, even an untaken BT/BF.
	return (op >> 12) == 0xa || (op >> 12) == 0xb
		|| (op & 0xff00) == 0x8900 || (op & 0xff00) == 0x8b00
		|| (op & 0xff00) == 0x8d00 || (op & 0xff00) == 0x8f00
		|| (op & 0xff00) == 0xc300
		// Reserved aliases accepted by the legacy group decoders are also
		// illegal in a slot; they must not reintroduce recursive branch decoding.
		|| (op & 0xf03f) == 0x0003 || (op & 0xf03f) == 0x0023
		|| (op & 0xf03f) == 0x400b || (op & 0xf03f) == 0x402b
		|| (op & 0xf03f) == 0x000b || (op & 0xf03f) == 0x002b;
}

void sh2_device::execute_one_f000(uint16_t opcode)
{
	ILLEGAL();
}

void sh2_device::execute_run()
{
	if (m_isdrc)
	{
		execute_run_drc();
		return;
	}

	if (m_cpu_off)
	{
		debugger_wait_hook();
		m_sh2_state->icount = 0;
		return;
	}

	do
	{
		debugger_instruction_hook(m_sh2_state->pc);

		// Fetch actual cached instructions, including private cache-array patches.
		// A DRC mismatch has already fetched this instruction; do not charge it twice.
		bool const cached = cache_area(m_sh2_state->pc);
		bool const reuse = m_fetch_reuse && m_fetch_pc == m_sh2_state->pc;
		m_fetch_reuse = false;
		if (!reuse && m_sh2_state->pc < 0x40000000
				&& (!(m_sh2_state->pc & 2) || m_fetch_pc != m_sh2_state->pc - 2 || (cached && !m_fetch_cached)))
		{
			m_fetch_cached = cached;
			if (cached)
				m_fetch_data = cache_read(m_sh2_state->pc & ~3, 4, true);
			else
				bus_charge(m_sh2_state->pc & ~3, 4, false);
		}
		m_fetch_pc = m_sh2_state->pc;
		const uint16_t opcode = cached
				? uint16_t(m_fetch_data >> ((m_sh2_state->pc & 2) ? 0 : 16))
				: decrypted_read_word(m_sh2_state->pc >= 0x40000000 ? m_sh2_state->pc : m_sh2_state->pc & m_am);
		if (!cached)
			m_fetch_cached = false;

		uint32_t const instruction_pc = m_sh2_state->pc;
		if (!instruction_before(instruction_pc, opcode))
			continue;

		m_in_delay_slot = delay_pending();
		if (m_in_delay_slot)
		{
			m_sh2_state->pc = m_sh2_state->m_delay;
			m_sh2_state->m_delay = 0;
		}
		else
			m_sh2_state->pc += 2;

		if (m_in_delay_slot && is_slot_illegal(opcode))
			ILLEGAL();
		else
			execute_one(opcode);
		// Legacy branch helpers use m_delay == 0 as their inactive sentinel.
		// Retain an explicit pending bit for a valid zero destination, including
		// across timeslices, bus waits and saves. Untaken BT/S and BF/S have no slot.
		m_zero_delay_pending = !m_in_delay_slot && !m_sh2_state->m_delay &&
			((opcode >> 12) == 0xa || (opcode >> 12) == 0xb ||
			 (opcode & 0xf03f) == 0x0003 || (opcode & 0xf03f) == 0x0023 ||
			 (opcode & 0xf03f) == 0x400b || (opcode & 0xf03f) == 0x402b ||
			 (opcode & 0xf03f) == 0x000b || (opcode & 0xf03f) == 0x002b ||
			 ((opcode & 0xff00) == 0x8d00 && (m_sh2_state->sr & SH_T)) ||
			 ((opcode & 0xff00) == 0x8f00 && !(m_sh2_state->sr & SH_T)));
		m_in_delay_slot = false;
		instruction_after(instruction_pc, opcode);

		if (m_test_irq && !delay_pending())
		{
			check_pending_irq("mame_sh2_execute");
			m_test_irq = 0;
		}
		m_sh2_state->icount--;
	} while (m_sh2_state->icount > 0);
}

// Check before register updates or memory side effects. AWAIT repeats the same
// instruction after one clock; other devices and their timers can run meanwhile.
// The DRC uses this interpreter boundary only during an active waited transfer.
bool sh2_device::instruction_before(uint32_t pc, uint16_t opcode)
{
	// Decode the illegal slot before checking its would-be operand accesses.
	if (delay_pending() && is_slot_illegal(opcode))
		return true;
	if (instruction_bus_ready(pc, opcode))
		return true;
	if (m_sh2_state->pc != pc)
		return false; // The access check took a CPU address-error exception.
	spin_until_time(cycles_to_attotime(1));
	return false;
}

bool sh2_device::instruction_bus_ready(uint32_t pc, uint16_t op)
{
	if (m_bus_ready.isnull() && !m_onchip_width_checks)
		return true;
	auto const &r = m_sh2_state->r;
	u32 const relative_pc = delay_pending() ? m_sh2_state->m_delay + 2 : pc + 4;
	unsigned const n = (op >> 8) & 15, m = (op >> 4) & 15, lo = op & 15, group = op >> 12;
	auto ready = [this](u32 a, unsigned size, bool write)
	{ return instruction_access_valid(a, size) && (a >= 0x40000000 || m_bus_ready.isnull() || m_bus_ready(a & m_am, size, write)); };
	switch (group)
	{
	case 0:
		if (lo >= 4 && lo <= 6)
			return ready(r[n] + r[0], 1U << (lo - 4), true);
		if (lo >= 12 && lo <= 14)
			return ready(r[m] + r[0], 1U << (lo - 12), false);
		if (lo == 15)
			return ready(r[m], 4, false) && ready(r[n], 4, false);
		break;
	case 1:
		return ready(r[n] + 4 * lo, 4, true);
	case 2:
		if (lo <= 2)
			return ready(r[n], 1U << lo, true);
		if (lo >= 4 && lo <= 6)
			return ready(r[n] - (1U << (lo - 4)), 1U << (lo - 4), true);
		break;
	case 4:
		if (lo == 15)
			return ready(r[m], 2, false) && ready(r[n], 2, false);
		if ((op & 0xff) == 0x1b)
			return ready(r[n], 1, false) && ready(r[n], 1, true);
		if ((op & 0xcf) == 2 || (op & 0xcf) == 3)
			return ready(r[n] - 4, 4, true);
		if ((op & 0xcf) == 6 || (op & 0xcf) == 7)
			return ready(r[n], 4, false);
		break;
	case 5:
		return ready(r[m] + 4 * lo, 4, false);
	case 6:
		if (lo <= 2)
			return ready(r[m], 1U << lo, false);
		if (lo >= 4 && lo <= 6)
			return ready(r[m], 1U << (lo - 4), false);
		break;
	case 8:
		switch ((op >> 8) & 15)
		{
		case 0:
		case 1:
			return ready(r[m] + lo * (1U << n), 1U << n, true);
		case 4:
		case 5:
			return ready(r[m] + lo * (1U << (n - 4)), 1U << (n - 4), false);
		}
		break;
	case 9:
		return ready(relative_pc + 2 * (op & 255), 2, false);
	case 12:
		switch (n)
		{
		case 0:
		case 1:
		case 2:
			return ready(m_sh2_state->gbr + (op & 255) * (1U << n), 1U << n, true);
		case 4:
		case 5:
		case 6:
			return ready(m_sh2_state->gbr + (op & 255) * (1U << (n - 4)), 1U << (n - 4), false);
		case 12:
			return ready(m_sh2_state->gbr + r[0], 1, false);
		case 13:
		case 14:
		case 15:
			return ready(m_sh2_state->gbr + r[0], 1, false) && ready(m_sh2_state->gbr + r[0], 1, true);
		}
		break;
	case 13:
		return ready((relative_pc & ~3U) + 4 * (op & 255), 4, false);
	}
	return true;
}

// Rare illegal on-chip widths use the shared interpreter boundary before any
// instruction side effect. Ordinary RAM/peripheral accesses stay compiled.
void sh2_device::generate_invalid_access_branch(drcuml_block &block, compiler_state &compiler, const opcode_desc *desc, int target)
{
	if (!m_onchip_width_checks)
		return;
	// A fault in a branch delay slot must enter at the branch boundary so
	// the interpreter retains the branch PC/target when building the frame.
	if (desc->delay.first())
		generate_invalid_access_branch(block, compiler, desc->delay.first(), target);
	uint16_t const op = desc->opptr;
	unsigned const n = (op >> 8) & 15, m = (op >> 4) & 15, lo = op & 15;
	auto const check = [&] (uml::parameter base, unsigned bytes, int displacement = 0, bool indexed = false)
	{
		if (bytes == 2)
			return;
		if (indexed)
			UML_ADD(block, I0, base, R32(0));
		else if (displacement)
			UML_ADD(block, I0, base, displacement);
		else
			UML_MOV(block, I0, base);
		if (bytes == 1)
		{
			UML_CMP(block, I0, 0xffffff00);
			UML_JMPc(block, COND_AE, target);
		}
		else
		{
			int const valid = compiler.labelnum++;
			UML_CMP(block, I0, 0xfffffe00);
			UML_JMPc(block, COND_B, valid);
			UML_CMP(block, I0, 0xffffff00);
			UML_JMPc(block, COND_B, target);
			UML_LABEL(block, valid);
		}
	};
	switch (op >> 12)
	{
	case 0:
		if (lo >= 4 && lo <= 6) check(R32(n), 1U << (lo - 4), 0, true);
		else if (lo >= 12 && lo <= 14) check(R32(m), 1U << (lo - 12), 0, true);
		else if (lo == 15) { check(R32(m), 4); check(R32(n), 4); }
		break;
	case 1: check(R32(n), 4, 4 * lo); break;
	case 2:
		if (lo <= 2) check(R32(n), 1U << lo);
		else if (lo >= 4 && lo <= 6) check(R32(n), 1U << (lo - 4), -(1 << (lo - 4)));
		break;
	case 4:
		if ((op & 255) == 0x1b) check(R32(n), 1);
		else if ((op & 0xcf) == 2 || (op & 0xcf) == 3) check(R32(n), 4, -4);
		else if ((op & 0xcf) == 6 || (op & 0xcf) == 7) check(R32(n), 4);
		break;
	case 5: check(R32(m), 4, 4 * lo); break;
	case 6:
		if (lo <= 2) check(R32(m), 1U << lo);
		else if (lo >= 4 && lo <= 6) check(R32(m), 1U << (lo - 4));
		break;
	case 8:
		if (n <= 1) check(R32(m), 1U << n, lo * (1U << n));
		else if (n == 4 || n == 5) check(R32(m), 1U << (n - 4), lo * (1U << (n - 4)));
		break;
	case 12:
		if (n <= 2) check(uml::mem(&m_sh2_state->gbr), 1U << n, (op & 255) * (1U << n));
		else if (n >= 4 && n <= 6) check(uml::mem(&m_sh2_state->gbr), 1U << (n - 4), (op & 255) * (1U << (n - 4)));
		else if (n >= 12) check(uml::mem(&m_sh2_state->gbr), 1, 0, true);
		break;
	}
}

void sh2_device::init_drc_frontend()
{
	m_drcfe = std::make_unique<sh2_frontend>(this, COMPILE_BACKWARDS_BYTES, COMPILE_FORWARDS_BYTES,
											 SINGLE_INSTRUCTION_MODE ? 1 : COMPILE_MAX_SEQUENCE);
}

void sh2_device::state_string_export(const device_state_entry &entry, std::string &str) const
{
	switch (entry.index())
	{
	case STATE_GENFLAGS:
		str = string_format("%c%c%d%c%c", m_sh2_state->sr & SH_M ? 'M' : '.', m_sh2_state->sr & SH_Q ? 'Q' : '.',
							(m_sh2_state->sr & SH_I) >> 4, m_sh2_state->sr & SH_S ? 'S' : '.',
							m_sh2_state->sr & SH_T ? 'T' : '.');
		break;
	}
}

void sh2_device::state_import(const device_state_entry &entry)
{
	switch (entry.index())
	{
		case SH4_PC: // shared register entry named "PC"
		case STATE_GENPC:
		case STATE_GENPCBASE:
			m_sh2_state->m_delay = 0;
			m_zero_delay_pending = false;
			break;

		case SH_SR:
			check_pending_irq("sh2_set_reg");
			break;
	}
}

void sh2_device::execute_set_input(int irqline, int state)
{
	if (irqline == INPUT_LINE_NMI)
	{
		if (m_nmi_line_state == state)
			return;

		m_nmi_line_state = state;

		if (state == CLEAR_LINE)
		{
			LOG("SH-2 cleared NMI\n");
		}
		else
		{
			LOG("SH-2 asserted NMI\n");

			m_sh2_state->pending_nmi = 1;

			if (m_isdrc)
			{
				sh2_exception("Set IRQ line", 16);
			}
			else
			{
				if (delay_pending())
					m_test_irq = 1;
				else
					check_pending_irq("sh2_set_nmi_line");
			}
		}
	}
	else
	{
		if (m_irq_line_state[irqline] == state)
			return;

		m_irq_line_state[irqline] = state;

		if (state == CLEAR_LINE)
		{
			LOG("SH-2 cleared irq #%d\n", irqline);
			m_sh2_state->pending_irq &= ~(1 << irqline);
		}
		else
		{
			LOG("SH-2 asserted irq #%d\n", irqline);
			m_sh2_state->pending_irq |= 1 << irqline;

			if (m_isdrc)
			{
				m_test_irq = 1;
			}
			else
			{
				if (delay_pending())
					m_test_irq = 1;
				else
					check_pending_irq("sh2_set_irq_line");
			}
		}
	}
}

void sh2_device::sh2_exception(const char *message, int irqline)
{
	// override this at the individual CPU level when special logic is required
	int vector;

	if (irqline != 16)
	{
		if (irqline <= ((m_sh2_state->sr >> 4) & 15)) /* If the cpu forbids this interrupt */
			return;

		// if this is an sh2 internal irq, use its vector
		if (m_sh2_state->internal_irq_level == irqline)
		{
			vector = m_internal_irq_vector;
			/* avoid spurious irqs with this (TODO: needs a better fix) */
			m_sh2_state->internal_irq_level = -1;
			LOG("SH-2 exception #%d (internal vector: $%x) after [%s]\n", irqline, vector, message);
		}
		else
		{
			standard_irq_callback(irqline, m_sh2_state->pc);
			vector = 64 + irqline/2;
			LOG("SH-2 exception #%d (autovector: $%x) after [%s]\n", irqline, vector, message);
		}
	}
	else
	{
		vector = 11;
		LOG("SH-2 nmi exception (autovector: $%x) after [%s]\n", vector, message);
	}

	sh2_exception_internal(message, irqline, vector);
}

void sh2_device::sh2_exception_internal(const char *message, int irqline, int vector)
{
	debugger_exception_hook(vector);

	// an exception cancels sleep mode and returns to the instruction following the SLEEP
	// (the handler doesn't necessarily come back: the Saturn BIOS clock change one drops
	// the exception frame, which left the next SLEEP falling through)
	if (m_sh2_state->sleep_mode == 1)
	{
		m_sh2_state->pc += 2;
		m_sh2_state->sleep_mode = 0;
	}

	if (m_isdrc)
	{
		m_sh2_state->evec = read_long(m_sh2_state->vbr + vector * 4);
		m_sh2_state->evec &= m_am;
		m_sh2_state->irqsr = m_sh2_state->sr;

		/* set I flags in SR */
		if (irqline > SH2_INT_15)
			m_sh2_state->sr = m_sh2_state->sr | SH_I;
		else
			m_sh2_state->sr = (m_sh2_state->sr & ~SH_I) | (irqline << 4);

//  printf("sh2_exception [%s] irqline %x evec %x save SR %x new SR %x\n", message, irqline, m_sh2_state->evec, m_sh2_state->irqsr, m_sh2_state->sr);
	}
	else
	{
		m_sh2_state->r[15] -= 4;
		write_long(m_sh2_state->r[15], m_sh2_state->sr);     /* push SR onto stack */
		m_sh2_state->r[15] -= 4;
		write_long(m_sh2_state->r[15], m_sh2_state->pc);     /* push PC onto stack */

		/* set I flags in SR */
		if (irqline > SH2_INT_15)
			m_sh2_state->sr = m_sh2_state->sr | SH_I;
		else
			m_sh2_state->sr = (m_sh2_state->sr & ~SH_I) | (irqline << 4);

		/* fetch PC */
		m_sh2_state->pc = read_long(m_sh2_state->vbr + vector * 4) & m_am;
	}
}

/////////
// DRC

const sh2_device::opcode_desc* sh2_device::get_desclist(offs_t pc)
{
	return m_drcfe->describe_code(pc);
}

void sh2_device::func_fastirq()
{
	sh2_exception("fastirq", m_sh2_state->irqline);
}
static void cfunc_fastirq(void *param) { ((sh2_device *)param)->func_fastirq(); };

/*-------------------------------------------------
    static_generate_entry_point - generate a
    static entry point
-------------------------------------------------*/

void sh2_device::static_generate_entry_point()
{
	uml::code_label const skip = 1;

	/* begin generating */
	drcuml_block &block(m_drcuml->begin_block(200));

	/* forward references */
	alloc_handle(m_nocode, "nocode");
	alloc_handle(m_write32, "write32");     // necessary?
	alloc_handle(m_entry, "entry");
	UML_HANDLE(block, *m_entry);                         // handle  entry

	/* load fast integer registers */
	load_fast_iregs(block);

	/* check for interrupts */
	UML_MOV(block, mem(&m_sh2_state->irqline), 0xffffffff);     // mov irqline, #-1
	UML_CMP(block, mem(&m_sh2_state->pending_nmi), 0);          // cmp pending_nmi, #0
	UML_JMPc(block, COND_Z, skip+2);                    // jz skip+2

	UML_MOV(block, mem(&m_sh2_state->pending_nmi), 0);          // zap pending_nmi
	UML_JMP(block, skip+1);                     // and then go take it (evec is already set)

	UML_LABEL(block, skip+2);                   // skip+2:
	UML_MOV(block, mem(&m_sh2_state->evec), 0xffffffff);        // mov evec, -1
	UML_MOV(block, I0, 0xffffffff);         // mov r0, -1 (r0 = irq)
	UML_AND(block, I1,  I0, 0xffff);                // and r1, 0xffff

	UML_LZCNT(block, I1, mem(&m_sh2_state->pending_irq));       // lzcnt r1, r1
	UML_CMP(block, I1, 32);             // cmp r1, #32
	UML_JMPc(block, COND_Z, skip+4);                    // jz skip+4

	UML_SUB(block, mem(&m_sh2_state->irqline), 31, I1);     // sub irqline, #31, r1

	UML_LABEL(block, skip+4);                   // skip+4:
	UML_CMP(block, mem(&m_sh2_state->internal_irq_level), 0xffffffff);  // cmp internal_irq_level, #-1
	UML_JMPc(block, COND_Z, skip+3);                    // jz skip+3
	UML_CMP(block, mem(&m_sh2_state->internal_irq_level), mem(&m_sh2_state->irqline));      // cmp internal_irq_level, irqline
	UML_JMPc(block, COND_LE, skip+3);                   // jle skip+3

	UML_MOV(block, mem(&m_sh2_state->irqline), mem(&m_sh2_state->internal_irq_level));      // mov r0, internal_irq_level

	UML_LABEL(block, skip+3);                   // skip+3:
	UML_CMP(block, mem(&m_sh2_state->irqline), 0xffffffff);     // cmp irqline, #-1
	UML_JMPc(block, COND_Z, skip+1);                    // jz skip+1
	UML_CALLC(block, cfunc_fastirq, this);               // callc fastirq

	UML_LABEL(block, skip+1);                   // skip+1:

	UML_CMP(block, mem(&m_sh2_state->evec), 0xffffffff);        // cmp evec, 0xffffffff
	UML_JMPc(block, COND_Z, skip);                  // jz skip

	UML_SUB(block, R32(15), R32(15), 4);            // sub R15, R15, #4
	UML_MOV(block, I0, R32(15));                // mov r0, R15
	UML_MOV(block, I1, mem(&m_sh2_state->irqsr));           // mov r1, irqsr
	UML_CALLH(block, *m_write32);                    // call write32

	UML_SUB(block, R32(15), R32(15), 4);            // sub R15, R15, #4
	UML_MOV(block, I0, R32(15));                // mov r0, R15
	UML_MOV(block, I1, mem(&m_sh2_state->pc));              // mov r1, pc
	UML_CALLH(block, *m_write32);                    // call write32

	UML_MOV(block, mem(&m_sh2_state->pc), mem(&m_sh2_state->evec));             // mov pc, evec

	UML_LABEL(block, skip);                         // skip:

	/* generate a hash jump via the current mode and PC */
	UML_HASHJMP(block, 0, mem(&m_sh2_state->pc), *m_nocode);     // hashjmp <mode>,<pc>,nocode

	block.end();
}


/*-------------------------------------------------
    generate_update_cycles - generate code to
    subtract cycles from the icount and generate
    an exception if out
-------------------------------------------------*/

void sh2_device::generate_update_cycles(drcuml_block &block, compiler_state &compiler, uml::parameter param, bool allow_exception)
{
	/* check full interrupts if pending */
	if (compiler.checkints)
	{
		uml::code_label const skip = compiler.labelnum++;

		compiler.checkints = false;
		compiler.labelnum += 4;

		/* check for interrupts */
		UML_MOV(block, mem(&m_sh2_state->irqline), 0xffffffff);     // mov irqline, #-1
		UML_CMP(block, mem(&m_sh2_state->pending_nmi), 0);          // cmp pending_nmi, #0
		UML_JMPc(block, COND_Z, skip+2);                    // jz skip+2

		UML_MOV(block, mem(&m_sh2_state->pending_nmi), 0);          // zap pending_nmi
		UML_JMP(block, skip+1);                     // and then go take it (evec is already set)

		UML_LABEL(block, skip+2);                   // skip+2:
		UML_MOV(block, mem(&m_sh2_state->evec), 0xffffffff);        // mov evec, -1
		UML_MOV(block, I0, 0xffffffff);         // mov r0, -1 (r0 = irq)
		UML_AND(block, I1,  I0, 0xffff);                // and r1, r0, 0xffff

		UML_LZCNT(block, I1, mem(&m_sh2_state->pending_irq));       // lzcnt r1, pending_irq
		UML_CMP(block, I1, 32);             // cmp r1, #32
		UML_JMPc(block, COND_Z, skip+4);                    // jz skip+4

		UML_SUB(block, mem(&m_sh2_state->irqline), 31, I1);     // sub irqline, #31, r1

		UML_LABEL(block, skip+4);                   // skip+4:
		UML_CMP(block, mem(&m_sh2_state->internal_irq_level), 0xffffffff);  // cmp internal_irq_level, #-1
		UML_JMPc(block, COND_Z, skip+3);                    // jz skip+3
		UML_CMP(block, mem(&m_sh2_state->internal_irq_level), mem(&m_sh2_state->irqline));      // cmp internal_irq_level, irqline
		UML_JMPc(block, COND_LE, skip+3);                   // jle skip+3

		UML_MOV(block, mem(&m_sh2_state->irqline), mem(&m_sh2_state->internal_irq_level));      // mov r0, internal_irq_level

		UML_LABEL(block, skip+3);                   // skip+3:
		UML_CMP(block, mem(&m_sh2_state->irqline), 0xffffffff);     // cmp irqline, #-1
		UML_JMPc(block, COND_Z, skip+1);                    // jz skip+1
		UML_CALLC(block, cfunc_fastirq, this);               // callc fastirq

		UML_LABEL(block, skip+1);                   // skip+1:
		UML_CMP(block, mem(&m_sh2_state->evec), 0xffffffff);        // cmp evec, 0xffffffff
		UML_JMPc(block, COND_Z, skip);                  // jz skip

		UML_SUB(block, R32(15), R32(15), 4);            // sub R15, R15, #4
		UML_MOV(block, I0, R32(15));                // mov r0, R15
		UML_MOV(block, I1, mem(&m_sh2_state->irqsr));           // mov r1, irqsr
		UML_CALLH(block, *m_write32);                    // call write32

		UML_SUB(block, R32(15), R32(15), 4);            // sub R15, R15, #4
		UML_MOV(block, I0, R32(15));                // mov r0, R15
		UML_MOV(block, I1, param);              // mov r1, nextpc
		UML_CALLH(block, *m_write32);                    // call write32

		// An accepted interrupt bypasses the ordinary cycle update below.
		// Account for this sequence and yield before entering the handler when
		// exhausted, including a persistent request accepted after every RTE.
		// Use the constant here: changing MAPVAR_CYCLES would also change the
		// mapping used by the non-interrupt path at the following label.
		UML_SUB(block, mem(&m_sh2_state->icount), mem(&m_sh2_state->icount), compiler.cycles);
		if (allow_exception)
			UML_EXHc(block, COND_S, *m_out_of_cycles, mem(&m_sh2_state->evec));
		UML_HASHJMP(block, 0, mem(&m_sh2_state->evec), *m_nocode);       // hashjmp m_sh2_state->evec

		UML_LABEL(block, skip);                         // skip:
	}

	/* account for cycles */
	if (compiler.cycles > 0)
	{
		UML_SUB(block, mem(&m_sh2_state->icount), mem(&m_sh2_state->icount), MAPVAR_CYCLES);    // sub     icount,icount,cycles
		UML_MAPVAR(block, MAPVAR_CYCLES, 0);                                        // mapvar  cycles,0
		if (allow_exception)
			UML_EXHc(block, COND_S, *m_out_of_cycles, param);
																					// exh     out_of_cycles,nextpc
	}
	compiler.cycles = 0;
}

/*------------------------------------------------------------------
    static_generate_memory_accessor
------------------------------------------------------------------*/

void sh2_device::static_generate_memory_accessor(int size, int iswrite, const char *name, uml::code_handle *&handleptr)
{
	/* on entry, address is in I0; data for writes is in I1 */
	/* on exit, read result is in I0 */
	/* routine trashes I0 */
	int label = 1;

	/* begin generating */
	drcuml_block &block(m_drcuml->begin_block(1024));

	/* add a global entry for this */
	alloc_handle(handleptr, name);
	UML_HANDLE(block, *handleptr);                         // handle  *handleptr

	// Converted CS2 data cannot use a raw address-space or fast-RAM access.
	int const ordinary = label++;
	UML_CMP(block, mem(&m_bus_endian_width), 0);
	UML_JMPc(block, COND_E, ordinary);
	UML_CMP(block, I0, 0x40000000);
	UML_JMPc(block, COND_AE, ordinary);
	UML_AND(block, I2, I0, 0x06000000);
	UML_CMP(block, I2, 0x04000000);
	UML_JMPc(block, COND_NE, ordinary);
	UML_MOV(block, mem(&m_cache_addr), I0);
	if (iswrite)
		UML_MOV(block, mem(&m_cache_data), I1);
	UML_MOV(block, mem(&m_cache_size), size);
	UML_MOV(block, mem(&m_bus_write), iswrite ? 1 : 0);
	UML_MOV(block, mem(&m_cache_op), 5);
	UML_CALLC(block, cfunc_cache_access, this);
	if (!iswrite)
		UML_MOV(block, I0, mem(&m_cache_data));
	UML_RET(block);
	UML_LABEL(block, ordinary);

	// SH7604 cache (8.4): a read of the cache area with CE set is served by
	// the cache helper; a write updates the cache on a hit, then goes to the
	// bus as usual. Done before the address is masked: the masked cached and
	// cache-through addresses are the same.
	int const timed = label++;
	if (m_cache_model)
	{
		int const nocache = label++;
		UML_CMP(block, I0, 0x20000000);                     // cache area: address bits 31-29 = 000
		UML_JMPc(block, COND_AE, nocache);
		UML_TEST(block, mem(&m_cache.ccr), sh7604_cache::CCR_CE);
		UML_JMPc(block, COND_Z, nocache);
		if (!iswrite && size == 1)
		{
			UML_TEST(block, mem(&m_tas_read), 1);           // TAS.B reads memory directly (8.4.4)
			UML_JMPc(block, COND_NZ, nocache);
		}
		UML_MOV(block, mem(&m_cache_addr), I0);
		UML_MOV(block, mem(&m_cache_size), size);
		UML_MOV(block, mem(&m_cache_op), iswrite ? 1 : 0);
		if (iswrite)
		{
			UML_MOV(block, mem(&m_cache_data), I1);
			UML_CALLC(block, cfunc_cache_access, this);  // updates the cache and charges the write
			UML_MOV(block, I0, mem(&m_cache_addr));
			UML_MOV(block, I1, mem(&m_cache_data));
			UML_JMP(block, timed);
		}
		else
		{
			// Preserve the accessor's scratch-register contract while serving
			// data hits in generated code, just as instruction hits are served.
			UML_DMOV(block, mem(&m_cache_scratch[0]), I1);
			UML_DMOV(block, mem(&m_cache_scratch[1]), I2);
			UML_DMOV(block, mem(&m_cache_scratch[2]), I3);
			UML_SHR(block, I1, I0, 10);
			UML_AND(block, I1, I1, 0x7ffff);
			UML_SHR(block, I0, I0, 4);
			UML_AND(block, I0, I0, 0x3f);
			int const cache_done = label++;
			static constexpr uint8_t keep[4] = { 0x07, 0x19, 0x2a, 0x34 };
			static constexpr uint8_t set[4] = { 0x00, 0x20, 0x14, 0x0b };
			for (unsigned w = 0; w < 4; ++w)
			{
				int const next = label++;
				UML_SHL(block, I3, I0, 2);
				UML_ADD(block, I3, I3, w);
				UML_LOAD(block, I2, &m_cache.valid[0][0], I3, SIZE_BYTE, SCALE_x1);
				UML_CMP(block, I2, 0);
				UML_JMPc(block, COND_E, next);
				UML_LOAD(block, I2, &m_cache.tag[0][0], I3, SIZE_DWORD, SCALE_x4);
				UML_CMP(block, I2, I1);
				UML_JMPc(block, COND_NE, next);
				UML_LOAD(block, I2, &m_cache.lru[0], I0, SIZE_BYTE, SCALE_x1);
				UML_AND(block, I2, I2, keep[w]);
				UML_OR(block, I2, I2, set[w]);
				UML_STORE(block, &m_cache.lru[0], I0, I2, SIZE_BYTE, SCALE_x1);
				UML_SHL(block, I3, I3, 2);
				UML_SHR(block, I2, mem(&m_cache_addr), 2);
				UML_AND(block, I2, I2, 3);
				UML_ADD(block, I3, I3, I2);
				UML_LOAD(block, I0, &m_cache.line[0][0][0], I3, SIZE_DWORD, SCALE_x4);
				if (size != 4)
				{
					UML_AND(block, I2, mem(&m_cache_addr), 3);
					UML_SUB(block, I2, 4 - size, I2);
					UML_SHL(block, I2, I2, 3);
					UML_SHR(block, I0, I0, I2);
					UML_AND(block, I0, I0, size == 1 ? 0xff : 0xffff);
				}
				UML_MOV(block, mem(&m_cache_data), I0);
				UML_JMP(block, cache_done);
				UML_LABEL(block, next);
			}
			UML_CALLC(block, cfunc_cache_access, this);
			UML_MOV(block, I0, mem(&m_cache_data));
			UML_LABEL(block, cache_done);
			UML_DMOV(block, I1, mem(&m_cache_scratch[0]));
			UML_DMOV(block, I2, mem(&m_cache_scratch[1]));
			UML_DMOV(block, I3, mem(&m_cache_scratch[2]));
			UML_RET(block);
		}
		UML_LABEL(block, nocache);
		if (!iswrite && size == 1)
			UML_MOV(block, mem(&m_tas_read), 0);
	}

	// external bus timing for an access that goes straight to the bus
	if (m_bus_timed || m_bus_observed)
	{
		UML_CMP(block, I0, 0x40000000);
		UML_JMPc(block, COND_AE, timed);
		UML_MOV(block, mem(&m_cache_addr), I0);
		if (iswrite)
			UML_MOV(block, mem(&m_cache_data), I1);
		UML_MOV(block, mem(&m_cache_size), size);
		UML_MOV(block, mem(&m_bus_write), iswrite ? 1 : 0);
		UML_MOV(block, mem(&m_cache_op), 3);
		UML_CALLC(block, cfunc_cache_access, this);
		UML_MOV(block, I0, mem(&m_cache_addr));
		if (iswrite)
			UML_MOV(block, I1, mem(&m_cache_data));
	}
	UML_LABEL(block, timed);

	// with internal handlers this becomes easier.
	// if addr < 0x40000000 AND it with AM and do the read/write, else just do the read/write
	UML_TEST(block, I0, 0x80000000);        // test r0, #0x80000000
	UML_JMPc(block, COND_NZ, label);                // if high bit is set, don't mask

	UML_CMP(block, I0, 0x40000000);     // cmp #0x40000000, r0
	UML_JMPc(block, COND_AE, label);            // bae label

	UML_AND(block, I0, I0, m_am);     // and r0, r0, #AM (0xc7ffffff)

	UML_LABEL(block, label++);              // label:

	if (!debugger_enabled())
	{
		for (auto & elem : m_fastram)
		{
			if (elem.base != nullptr && (!iswrite || !elem.readonly))
			{
				void *fastbase = (uint8_t *)elem.base - elem.start;
				uint32_t skip = label++;
				if (elem.end != 0xffffffff)
				{
					UML_CMP(block, I0, elem.end);   // cmp     i0,end
					UML_JMPc(block, COND_A, skip);                                      // ja      skip
				}
				if (elem.start != 0x00000000)
				{
					UML_CMP(block, I0, elem.start);// cmp     i0,fastram_start
					UML_JMPc(block, COND_B, skip);                                      // jb      skip
				}

				if (!iswrite)
				{
					if (size == 1)
					{
						UML_XOR(block, I0, I0, BYTE4_XOR_BE(0));
						UML_LOAD(block, I0, fastbase, I0, SIZE_BYTE, SCALE_x1);             // load    i0,fastbase,i0,byte
					}
					else if (size == 2)
					{
						UML_XOR(block, I0, I0, WORD_XOR_BE(0));
						UML_LOAD(block, I0, fastbase, I0, SIZE_WORD, SCALE_x1);         // load    i0,fastbase,i0,word_x1
					}
					else if (size == 4)
					{
						UML_LOAD(block, I0, fastbase, I0, SIZE_DWORD, SCALE_x1);            // load    i0,fastbase,i0,dword_x1
					}
					UML_RET(block);                                                     // ret
				}
				else
				{
					if (size == 1)
					{
						UML_XOR(block, I0, I0, BYTE4_XOR_BE(0));
						UML_STORE(block, fastbase, I0, I1, SIZE_BYTE, SCALE_x1);// store   fastbase,i0,i1,byte
					}
					else if (size == 2)
					{
						UML_XOR(block, I0, I0, WORD_XOR_BE(0));
						UML_STORE(block, fastbase, I0, I1, SIZE_WORD, SCALE_x1);// store   fastbase,i0,i1,word_x1
					}
					else if (size == 4)
					{
						UML_STORE(block, fastbase, I0, I1, SIZE_DWORD, SCALE_x1);       // store   fastbase,i0,i1,dword_x1
					}
					UML_RET(block);                                                     // ret
				}

				UML_LABEL(block, skip);                                             // skip:
			}
		}
	}

	if (iswrite)
	{
		switch (size)
		{
			case 1:
				UML_WRITE(block, I0, I1, SIZE_BYTE, SPACE_PROGRAM); // write r0, r1, program_byte
				break;

			case 2:
				UML_WRITE(block, I0, I1, SIZE_WORD, SPACE_PROGRAM); // write r0, r1, program_word
				break;

			case 4:
				UML_WRITE(block, I0, I1, SIZE_DWORD, SPACE_PROGRAM);    // write r0, r1, program_dword
				break;
		}
	}
	else
	{
		switch (size)
		{
			case 1:
				UML_READ(block, I0, I0, SIZE_BYTE, SPACE_PROGRAM);  // read r0, program_byte
				break;

			case 2:
				UML_READ(block, I0, I0, SIZE_WORD, SPACE_PROGRAM);  // read r0, program_word
				break;

			case 4:
				UML_READ(block, I0, I0, SIZE_DWORD, SPACE_PROGRAM); // read r0, program_dword
				break;
		}
	}

	UML_RET(block);                         // ret

	block.end();
}

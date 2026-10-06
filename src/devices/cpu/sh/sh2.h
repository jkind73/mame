// license:BSD-3-Clause
// copyright-holders:Juergen Buchmueller
/*****************************************************************************
 *
 *   sh2.h
 *   Portable Hitachi SH-2 (SH7600 family) emulator interface
 *
 *  This work is based on <tiraniddo@hotmail.com> C/C++ implementation of
 *  the SH-2 CPU core and was heavily changed to the MAME CPU requirements.
 *  Thanks also go to Chuck Mason <chukjr@sundail.net> and Olivier Galibert
 *  <galibert@pobox.com> for letting me peek into their SEMU code :-)
 *
 *****************************************************************************/

#ifndef MAME_CPU_SH_SH2_H
#define MAME_CPU_SH_SH2_H

#pragma once

#include "sh.h"
#include "sh7604_cache.h"

class sh2_device : public sh_common_execution
{
public:
	void set_frt_input(int state) override {} // not every CPU needs this, let the ones that do override it

	void func_fastirq(); // required for DRC, needs to be public to be accessible through non-classed static trampoline function
	void func_cache_access();       // DRC cache helper (m_cache_op on m_cache_addr/m_cache_data)

protected:
	class sh2_frontend;

	sh2_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, int cpu_type, address_map_constructor internal_map, int addrlines, uint32_t address_mask);
	virtual ~sh2_device();

	void check_pending_irq(const char *message);

	// device-level overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;

	// device_execute_interface overrides
	virtual uint32_t execute_min_cycles() const noexcept override { return 1; }
	virtual uint32_t execute_max_cycles() const noexcept override { return 4; }
	virtual uint32_t execute_default_irq_vector(int inputnum) const noexcept override { return 0; }
	virtual bool execute_input_edge_triggered(int inputnum) const noexcept override { return inputnum == INPUT_LINE_NMI; }
	virtual void execute_run() override;
	virtual void execute_set_input(int inputnum, int state) override;

	// device_memory_interface overrides
	virtual space_config_vector memory_space_config() const override;

	// device_state_interface overrides
	virtual void state_import(const device_state_entry &entry) override;
	virtual void state_string_export(const device_state_entry &entry, std::string &str) const override;

	// device_disasm_interface overrides
	virtual std::unique_ptr<util::disasm_interface> create_disassembler() override;

	virtual void sh2_exception(const char *message, int irqline) override;
	virtual void sh2_exception_internal(const char *message, int irqline, int vector);

	address_space *m_decrypted_program;

	uint32_t m_test_irq;
	int32_t m_internal_irq_vector;
	int8_t m_nmi_line_state;

	// SH7604 cache (section 8). Its registers and array windows always
	// exist; m_cache_model, set by the driver, makes the core look up and
	// fill the cache on cache-area accesses.
	sh7604_cache m_cache;
	bool m_cache_model = false;
	uint32_t m_cache_op = 0, m_cache_size = 0, m_cache_addr = 0, m_cache_data = 0; // DRC helper arguments
	uint32_t m_fetch_pc = ~0U;      // interpreter: PC of the previous instruction fetch

	bool cache_area(offs_t address) const { return m_cache_model && address < 0x20000000 && m_cache.enabled(); }

	// External bus timing, supplied by the driver: the cycles an access to
	// the external bus (addresses below 40000000H) costs beyond the one the
	// instruction timing already counts. size is 1, 2 or 4; fill marks a
	// cache line fill (four longwords, 8.4.1); now is the CPU's local time at
	// the access (machine time, so it stays monotonic across CPU resets);
	// dma marks an access of the on-chip DMAC, a requester of its own.
	using bus_timing_delegate = device_delegate<int (offs_t address, unsigned size, bool write, bool fill, attotime now, bool dma)>;
	bus_timing_delegate m_bus_timing;
	bool m_bus_timed = false;
	uint32_t m_bus_write = 0;       // DRC helper argument
	// DRC: base cycles of the current sequence that are not yet taken off
	// icount (the DRC applies them at the end of the sequence; the
	// interpreter after each instruction), so both cores see the same time.
	uint32_t m_bus_pending = 0;
	// the DRC keeps m_bus_pending up to date even without bus timing, for the devices that wait for
	// the CPU's time on an access of their own (the division unit)
	bool m_track_pending = false;
	void bus_charge(offs_t address, unsigned size, bool write, bool fill = false)
	{
		if (m_bus_timed)
			m_sh2_state->icount -= m_bus_timing(address, size, write, fill, local_time() + cycles_to_attotime(m_bus_pending), false);
	}
	uint32_t cache_read(offs_t address, unsigned size, bool instruction);
	void cache_write(offs_t address, unsigned size, uint32_t data);

private:
	virtual uint8_t read_byte(offs_t A) override;
	virtual uint16_t read_word(offs_t A) override;
	virtual uint32_t read_long(offs_t A) override;
	virtual uint16_t decrypted_read_word(offs_t offset) override;
	virtual void write_byte(offs_t A, uint8_t V) override;
	virtual void write_word(offs_t A, uint16_t V) override;
	virtual void write_long(offs_t A, uint32_t V) override;

	virtual void LDCMSR(const uint16_t opcode) override;
	virtual void LDCSR(const uint16_t opcode) override;
	virtual void TRAPA(uint32_t i) override;
	virtual void RTE() override;
	virtual void ILLEGAL() override;

	virtual void execute_one_f000(uint16_t opcode) override;

	virtual void init_drc_frontend() override;
	virtual const opcode_desc* get_desclist(offs_t pc) override;

	virtual void generate_update_cycles(drcuml_block &block, compiler_state &compiler, uml::parameter param, bool allow_exception) override;
	virtual void generate_instruction_fetch(drcuml_block &block, compiler_state &compiler, const opcode_desc *desc, bool sequence_start) override;
	virtual void static_generate_entry_point() override;
	virtual void static_generate_memory_accessor(int size, int iswrite, const char *name, uml::code_handle *&handleptr) override;

	address_space_config m_program_config, m_decrypted_program_config;

	std::unique_ptr<sh2_frontend> m_drcfe; /* pointer to the DRC front-end state */

	uint32_t m_cpu_off;
	int8_t m_irq_line_state[17];
};

#endif // MAME_CPU_SH_SH2_H

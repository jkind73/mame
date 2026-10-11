// license:BSD-3-Clause
// copyright-holders:Angelo Salese, Mariusz Wojcieszek
/**************************************************************************************************
 *
 * scudsp.cpp
 * Sega SCUDSP emulator version 1.00
 *
 *
 * Changelog:
 * 131010: Angelo Salese
 * - Converted to CPU structure
 *
 * 110807: Angelo Salese
 * - Allow the Program Counter to be read-backable from SH-2, needed by Virtua Fighter to not
 *   get stuck on "round 1" announcement;
 *
 * 110806: Angelo Salese
 * - Allows reading from non-work ram h areas;
 * - Fixed DMA add values;
 * - Fixed a MVI condition shift flag bug, now Sega Saturn produces sound during splash screen;
 * - Removed left-over IRQ;
 *
 * 110722: Angelo Salese
 * - Added DSP IRQ command, tested with "The King of Boxing"
 *
 * 110527: Angelo Salese
 * - Fixed incorrectly setted execute flag clearance, allows animation of the Sega Saturn
 *   splash screen;
 *
 * 051129: Mariusz Wojcieszek
 * - Fixed parallel instructions which increment CT registers to update CT register only
 *   once, after dsp operation is finished. This fixes instructions like
 *   MOV MC0,X MOV MC0,Y used by vfremix
 * - Changed ALU 32bit instructions to not sign extend their result when loaded to ALU.
 *   This matches Sega's dspsim behaviour.
 * - Changed DMA addnumber handling to match Sega's dspsim.
 *
 * 050813: Mariusz Wojcieszek
 * - Fixed add number in DSP DMA
 *
 * 050412: Angelo Salese
 * - Fixed the T0F behaviour in the DMA operation,it was causing an hang in Treasure Hunt
 *   due of that.
 * - Removed the dsp.log file creation when you are not using the debug build
 *
 * 041114: Angelo Salese
 * - Finished flags in ALU opcodes
 * - SR opcode: MSB does not change.
 *
 * 040328: Mariusz Wojcieszek
 * - rewritten ALU and MUL operations using signed arithmetics
 * - improved DMA
 * - fixed MOV ALH,x
 *
 * 031211: Mariusz Wojcieszek
 * - result of ALU command is stored into ALU register
 * - X-Bus command: MOV [s],X can be executed in parallel to other X-Bus commands
 * - Y-Bus command: MOV [s],Y can be executed in parallel to other Y-Bus commands
 * - Jump and LPS/BTM support:
 *   jump addresses are absolute,
 *   prefetched instructions are executed before jump is taken
 * - after each instruction, X and Y is multiplied and contents are loaded into MUL register
 * - fixed RL8
 * - fixed MVI
 * - MVI/JMP conditions are verified against ST-97 Tables 4.2-4.4.
 * - added reading DSP mem from SH2 side
 * - overworked disassembler
 *
 *  Timing: one instruction per DSP clock (master / 4); parallel bus moves
 *  share that instruction clock. DMA acknowledges asynchronously using the
 *  SCU bus wait model. Absolute bus timing has not been checked on hardware.
 *  Control, debugger scheduling and vkyoute2 regressions are recorded in
 *  SCU_DSP_CORE_AUDIT.md.
 *
 *
 *************************************************************************************************/

#include "emu.h"
#include "scudsp.h"
#include "scudspdasm.h"

#define LOG_RULE (1U << 1)
#define VERBOSE (0)
#include "logmacro.h"


DEFINE_DEVICE_TYPE(SCUDSP, scudsp_cpu_device, "scudsp", "Sega SCUDSP")

/* FLAGS */

#define SET_C(_val) (m_flags = ((m_flags & ~0x00100000) | ((_val) ? 0x00100000 : 0)))
#define SET_S(_val) (m_flags = ((m_flags & ~0x00400000) | ((_val) ? 0x00400000 : 0)))
#define SET_Z(_val) (m_flags = ((m_flags & ~0x00200000) | ((_val) ? 0x00200000 : 0)))
#define SET_V(_val) (m_flags = ((m_flags & ~0x00080000) | ((_val) ? 0x00080000 : 0)))


#define FLAGS_MASK 0x00fd0000 // T0, S, Z, C, V, E and EX; the other control bits are write-only

#define scudsp_readop(A) m_program->read_dword(A)
#define scudsp_writeop(A, B) m_program->write_dword(A, B)
#define scudsp_readmem(A,MD) m_data->read_dword(A | (MD << 6))
#define scudsp_writemem(A,MD,B) m_data->write_dword(A | (MD << 6), B)

constexpr uint64_t concat_64(uint32_t hi, uint32_t lo) { return (uint64_t(hi) << 32) | lo; }

uint32_t scudsp_cpu_device::get_source_mem_reg_value( uint32_t mode )
{
	if ( mode < 0x8 )
	{
		return get_source_mem_value( mode );
	}
	else
	{
		switch( mode )
		{
			case 0x9:
				return u32((m_alu & 0x00000000ffffffffU) >> 0);
			case 0xA:
				return u32((m_alu & 0x0000ffffffff0000U) >> 16);
		}
	}
	return 0;
}

uint32_t scudsp_cpu_device::get_source_mem_value(uint8_t mode)
{
	uint32_t value = 0;

	switch( mode )
	{
		case 0x0:   /* M0 */
			value = scudsp_readmem(m_ct[0],0);
			break;
		case 0x1:   /* M1 */
			value = scudsp_readmem(m_ct[1],1);
			break;
		case 0x2:   /* M2 */
			value = scudsp_readmem(m_ct[2],2);
			break;
		case 0x3:   /* M3 */
			value = scudsp_readmem(m_ct[3],3);
			break;
		case 0x4:   /* MC0 */
			value = scudsp_readmem(m_ct[0]++,0);
			m_ct[0] &= 0x3f;
			break;
		case 0x5:   /* MC1 */
			value = scudsp_readmem(m_ct[1]++,1);
			m_ct[1] &= 0x3f;
			break;
		case 0x6:   /* MC2 */
			value = scudsp_readmem(m_ct[2]++,2);
			m_ct[2] &= 0x3f;
			break;
		case 0x7:   /* MC3 */
			value = scudsp_readmem(m_ct[3]++,3);
			m_ct[3] &= 0x3f;
			break;
	}

	return value;
}

void scudsp_cpu_device::set_dest_mem_reg( uint32_t mode, uint32_t value )
{
	switch( mode )
	{
		case 0x0:   /* MC0 */
			scudsp_writemem(m_ct[0]++,0,value);
			m_ct[0] &= 0x3f;
			break;
		case 0x1:   /* MC1 */
			scudsp_writemem(m_ct[1]++,1,value);
			m_ct[1] &= 0x3f;
			break;
		case 0x2:   /* MC2 */
			scudsp_writemem(m_ct[2]++,2,value);
			m_ct[2] &= 0x3f;
			break;
		case 0x3:   /* MC3 */
			scudsp_writemem(m_ct[3]++,3,value);
			m_ct[3] &= 0x3f;
			break;
		case 0x4:   /* RX */
			// the multiplier works on whatever is in RX, however it got there
			// - vkyoute2 loads RX with MVI #$10000 for the translation column of its transform
			m_rx.ui = value;
			m_update_mul = 1;
			break;
		case 0x5:   /* PL */
			m_pl.ui = value;
			m_ph.si = (m_pl.si < 0) ? -1 : 0;
			break;
		case 0x6:   /* RA0 */
			m_ra0 = value;
			break;
		case 0x7:   /* WA0 */
			m_wa0 = value;
			break;
		case 0x8:
		case 0x9:
			/* ??? */
			break;
		case 0xa:   /* LOP */
			if (!m_loop_active)
				m_lop = value & 0x0fff;
			break;
		case 0xb:   /* TOP */
			m_top = value;
			break;
		case 0xc:   /* CT0 */
			m_ct[0] = value & 0x3f;
			break;
		case 0xd:   /* CT1 */
			m_ct[1] = value & 0x3f;
			break;
		case 0xe:   /* CT2 */
			m_ct[2] = value & 0x3f;
			break;
		case 0xf:   /* CT3 */
			m_ct[3] = value & 0x3f;
			break;
	}
}

void scudsp_cpu_device::set_dest_mem_reg_2( uint32_t mode, uint32_t value )
{
	if ( mode < 0xb )
	{
		set_dest_mem_reg( mode, value );
	}
	else
	{
		switch( mode )
		{
			case 0xc:   /* PC */
				m_delay = m_pc;
				m_delay_pending = true;  /* address next after this command will be executed twice */
				m_top = m_pc;
				m_pc = value;
				break;
		}
	}
}

uint32_t scudsp_cpu_device::compute_condition( uint32_t condition ) const
{
	// ST-97 Tables 4.2-4.4: bit 0 Z, bit 1 S, bit 2 C, bit 3 T0 select the flags that are ORed together;
	// bit 5 set tests for the flags being 1, clear tests for all of them being 0 (NZ, NS, NZS, NC, NT0)
	uint32_t result = 0;
	result |= BIT(condition, 0) & BIT(m_flags, ZF);
	result |= BIT(condition, 1) & BIT(m_flags, SF);
	result |= BIT(condition, 2) & BIT(m_flags, CF);
	result |= BIT(condition, 3) & BIT(m_flags, T0F);

	return BIT(condition, 5) ? result : !result;
}

// DMA CTx r/ws follows MC increment rules
void scudsp_cpu_device::set_dest_dma_mem( uint32_t memcode, uint32_t value )
{
	if ( memcode < 4 )
	{
		switch(memcode)
		{
			case 0x0:   /* MC0 */
				scudsp_writemem(m_ct[0], 0, value);
				m_ct[0] ++;
				m_ct[0] &= 0x3f;
				break;
			case 0x1:   /* MC1 */
				scudsp_writemem(m_ct[1], 1, value);
				m_ct[1] ++;
				m_ct[1] &= 0x3f;
				break;
			case 0x2:   /* MC2 */
				scudsp_writemem(m_ct[2], 2, value);
				m_ct[2] ++;
				m_ct[2] &= 0x3f;
				break;
			case 0x3:   /* MC3 */
				scudsp_writemem(m_ct[3], 3, value);
				m_ct[3] ++;
				m_ct[3] &= 0x3f;
				break;
		}
	}
}

uint32_t scudsp_cpu_device::get_mem_source_dma( uint32_t memcode )
{
	uint32_t value = 0;
	switch( memcode & 0x3 )
	{
		case 0x0:
			value = scudsp_readmem(m_ct[0], 0);
			m_ct[0] ++;
			m_ct[0] &= 0x3f;
			break;
		case 0x1:
			value = scudsp_readmem(m_ct[1], 1);
			m_ct[1] ++;
			m_ct[1] &= 0x3f;
			break;
		case 0x2:
			value = scudsp_readmem(m_ct[2], 2);
			m_ct[2] ++;
			m_ct[2] &= 0x3f;
			break;
		case 0x3:
			value = scudsp_readmem(m_ct[3], 3);
			m_ct[3] ++;
			m_ct[3] &= 0x3f;
			break;
	}
	return value;
}


uint32_t scudsp_cpu_device::program_control_r()
{
	// The EX latch permits PR to resume the program, but a paused program is
	// reported as not running (DSP.sv EX & ~EP; ST-97 3.3).
	const u32 flags = (m_flags & FLAGS_MASK) & ~(m_paused ? (1U << EXF) : 0U);

	if (!machine().side_effects_disabled())
	{
		// Rel.2.5 warns that polling here while executing can suppress the end interrupt.
		if (BIT(m_flags, EXF))
			LOGMASKED(LOG_RULE, "%s: DSP control read while executing may suppress its end interrupt\n",
				machine().describe_context());
		// clear overflow and end flag on host reads of this port
		m_flags &= ~(1 << VF);
		m_flags &= ~(1 << EF);
		m_out_irq_cb(0);
	}

	// Execution already advances m_pc past the instruction, including END.
	// The port reports that address, not a second increment (ST-97 4.3).
	return m_pc | flags;
}

void scudsp_cpu_device::program_control_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	bool const was_running = BIT(m_flags, EXF);
	bool const pause_command = ACCESSING_BITS_24_31 && (BIT(data, EPF) || BIT(data, PRF));
	// PR/EP (bits 26/25) resume and pause a running program (ST-97 3.3)
	if (pause_command && was_running)
	{
		if (BIT(data, EPF))
			m_paused = true;
		else if (BIT(data, PRF))
			m_paused = false;
	}

	// set new PC if transfer enable is set, not while the program is executing
	// NOTE: doesn't get transfered in flags
	if (BIT(data, LEF) && ACCESSING_BITS_0_15 && !BIT(m_flags, EXF))
	{
		m_pc = data & 0xff;
		m_delay_pending = false;
		m_loop_active = false;
	}

	// Pause/resume commands take precedence over EX/ES, including full-width
	// host writes with EX=0. They must not stop the program they are pausing.
	if (ACCESSING_BITS_16_23 && !pause_command)
	{
		// EX starts/stops the program
		m_flags = (m_flags & ~(1 << EXF)) | (data & (1 << EXF));

		// ES executes one step while the program is stopped, ignored while executing
		if (BIT(data, ESF) && !was_running && !BIT(m_flags, EXF))
		{
			const int icount = m_icount;
			m_update_mul = 0;
			execute_one();
			m_icount = icount;
		}
	}

	// EX controls instruction execution, not the device reset input. Releasing
	// RESET calls device_reset(), which would cancel an independent active DMA.
	// Release the SCU's physical startup reset; stopping through EX never asserts it.
	if (BIT(m_flags, EXF))
		set_input_line(INPUT_LINE_RESET, CLEAR_LINE);
}

void scudsp_cpu_device::program_w(uint32_t data)
{
	//printf("%02x %08x PRG\n",m_pc,data);
	scudsp_writeop(m_pc++, data);
}

void scudsp_cpu_device::ram_address_control_w(uint32_t data)
{
	//printf("%02x %08x PRG\n",m_pc,data);
	// NOTE: RA has no relationship with CT0 ~ CT3, can upload out of high 2 bits bounds
	m_ra = data & 0xff;
}

uint32_t scudsp_cpu_device::ram_address_r()
{
	uint32_t data = m_data->read_dword(m_ra);

	if (!machine().side_effects_disabled())
		m_ra = (m_ra + 1) & 0xff;

	return data;
}

void scudsp_cpu_device::ram_address_w(uint32_t data)
{
//  set_dest_mem_reg( (m_ra & 0xc0) >> 6, data );
	m_data->write_dword(m_ra, data);

	m_ra = (m_ra + 1) & 0xff;

}

void scudsp_cpu_device::op_alu(uint32_t opcode)
{
	int update_ct[4] = {0,0,0,0};
	int dsp_mem;


	/* ALU */
	// The ALU output register starts from the accumulator, so the 32-bit operations leave [ACH] in the
	// upper 16 bits (ST-97 4.5 ALU commands: only AD2 works on the full 48 bits).
	// Flags follow the per-command descriptions of the manual:
	// - AND/OR/XOR: S = result MSB, Z = result is 0, C = 0
	// - ADD/SUB/AD2: S, Z, C = carry out, V = overflow (sticky until the host reads the control port)
	// - SR/RR/SL/RL/RL8: C = bit shifted out of the input (b0, b0, b31, b31, b24)
	m_alu = (uint64_t(m_ach.ui) << 32) | m_acl.ui;
	{
		const uint32_t acl = m_acl.ui;
		const uint32_t pl = m_pl.ui;
		const auto set_alu32 = [this] (uint32_t result)
		{
			m_alu = (m_alu & 0xffff'0000'0000) | result;
			SET_Z(result == 0);
			SET_S(s32(result) < 0);
		};

		switch( (opcode & 0x3c000000) >> 26 )
		{
			case 0x0:   /* NOP */
			default:    /* unrecognized, treated as NOP */
				break;

			case 0x1:   /* AND */
				set_alu32(acl & pl);
				SET_C(0);
				break;

			case 0x2:   /* OR */
				set_alu32(acl | pl);
				SET_C(0);
				break;

			case 0x3:   /* XOR */
				set_alu32(acl ^ pl);
				SET_C(0);
				break;

			case 0x4:   /* ADD */
			{
				const uint64_t result = uint64_t(acl) + pl;
				set_alu32(uint32_t(result));
				SET_C(BIT(result, 32));
				if (BIT((~(uint64_t(acl) ^ pl)) & (uint64_t(acl) ^ result), 31))
					m_flags |= 1 << VF;
				break;
			}

			case 0x5:   /* SUB */
			{
				const uint64_t result = uint64_t(acl) - pl;
				set_alu32(uint32_t(result));
				SET_C(BIT(result, 32));
				if (BIT((uint64_t(acl) ^ pl) & (uint64_t(acl) ^ result), 31))
					m_flags |= 1 << VF;
				break;
			}

			case 0x6:   /* AD2 */
			{
				const uint64_t op1 = (uint64_t(m_ach.ui) << 32) | acl;
				const uint64_t op2 = (uint64_t(m_ph.ui) << 32) | pl;
				const uint64_t result = op1 + op2;
				SET_Z((result << 16) == 0);
				SET_S(s64(result << 16) < 0);
				SET_C(BIT(result, 48));
				if (BIT((~(op1 ^ op2)) & (op1 ^ result), 47))
					m_flags |= 1 << VF;
				m_alu = result & 0xffff'ffff'ffff;
				break;
			}

			case 0x8:   /* SR */
				// MSB does not change
				set_alu32(uint32_t(s32(acl) >> 1));
				SET_C(BIT(acl, 0));
				break;

			case 0x9:   /* RR */
				set_alu32(std::rotr(acl, 1));
				SET_C(BIT(acl, 0));
				break;

			case 0xa:   /* SL */
				set_alu32(acl << 1);
				SET_C(BIT(acl, 31));
				break;

			case 0xb:   /* RL */
				set_alu32(std::rotl(acl, 1));
				SET_C(BIT(acl, 31));
				break;

			case 0xf:   /* RL8 */
				set_alu32(std::rotl(acl, 8));
				SET_C(BIT(acl, 24));
				break;
		}
	}

	/* X-Bus */
	if (opcode & 0x2000000)
	{
		/* MOV [s],X */
		dsp_mem = (opcode & 0x700000) >> 20;
		if (dsp_mem & 4)
		{
			dsp_mem &= 3;
			update_ct[dsp_mem] = 1;
		}
		m_rx.ui = get_source_mem_value( dsp_mem );
		m_update_mul = 1;
	}
	switch ((opcode & 0x1800000) >> 23)
	{
		case 0x0:   /* NOP */
		case 0x1:   /* NOP ? */
			break;
		case 0x2:   /* MOV MUL,P */
			m_ph.ui = u16((m_mul & 0x0000ffff00000000U) >> 32);
			m_pl.ui = u32((m_mul & 0x00000000ffffffffU) >> 0);
			break;
		case 0x3:   /* MOV [s],P */
			dsp_mem = (opcode & 0x700000) >> 20;
			if (dsp_mem & 4)
			{
				dsp_mem &= 3;
				update_ct[dsp_mem] = 1;
			}
			m_pl.ui = get_source_mem_value(  dsp_mem );
			m_ph.si = (m_pl.si < 0) ? -1 : 0;
			break;
	}

	/* Y-Bus */
	if (opcode & 0x80000)
	{
		/* MOV [s],Y */
		dsp_mem = (opcode & 0x1C000 ) >> 14;
		if (dsp_mem & 4)
		{
			dsp_mem &= 3;
			update_ct[dsp_mem] = 1;
		}
		m_ry.ui = get_source_mem_value( dsp_mem );
		m_update_mul = 1;
	}
	switch ((opcode & 0x60000) >> 17)
	{
		case 0x0:   /* NOP */
			break;
		case 0x1:   /* CLR A */
			m_acl.ui = 0;
			m_ach.ui = 0;
			break;
		case 0x2:   /* MOV ALU,A */
			m_ach.ui = u16((m_alu & 0x0000ffff00000000U) >> 32);
			m_acl.ui = u32((m_alu & 0x00000000ffffffffU) >> 0);
			break;
		case 0x3:   /* MOV [s], A */
			dsp_mem = (opcode & 0x1C000 ) >> 14;
			if (dsp_mem & 4)
			{
				dsp_mem &= 3;
				update_ct[dsp_mem] = 1;
			}
			m_acl.ui = get_source_mem_value( dsp_mem );
			m_ach.si = ((m_acl.si < 0) ? -1 : 0);
			break;
	}


	// All parallel reads use the original CT address. Commit each bank's increment
	// once, after the D1 move too; an explicit CT write takes precedence.
	unsigned const d1_dest = (opcode >> 8) & 0xf;
	auto const d1_write = [this, &update_ct] (unsigned dest, uint32_t value)
	{
		if (dest < 4)
		{
			scudsp_writemem(m_ct[dest], dest, value);
			update_ct[dest] = 1;
		}
		else
			set_dest_mem_reg(dest, value);
	};
	/* D1-Bus */
	switch( (opcode & 0x3000) >> 12 )
	{
		case 0x0:   /* NOP */
			break;
		case 0x1:   /* MOV SImm,[d] */
			d1_write((opcode & 0xf00) >> 8, int32_t(int8_t(opcode & 0xff)));
			break;
		case 0x2:
			/* ??? */
			break;
		case 0x3:   /* MOV [s],[d] */
		{
			unsigned source = opcode & 0xf;
			if (source >= 4 && source < 8)
			{
				source &= 3;
				update_ct[source] = 1;
			}
			d1_write((opcode & 0xf00) >> 8, get_source_mem_reg_value(source));
			break;
		}
	}

	for (unsigned bank = 0; bank < 4; ++bank)
		if (update_ct[bank] && !((((opcode >> 12) & 3) == 1 || ((opcode >> 12) & 3) == 3) && d1_dest == 12 + bank))
			m_ct[bank] = (m_ct[bank] + 1) & 0x3f;
	m_icount -= 1;
}

void scudsp_cpu_device::op_move_immediate( uint32_t opcode )
{
	uint32_t value;

	if ( opcode & 0x2000000 )
	{
		if ( compute_condition( (opcode & 0x3F80000 ) >> 19 ) )
		{
			value = util::sext( opcode, 19 );
			set_dest_mem_reg_2( (opcode & 0x3C000000) >> 26, value );
		}
	}
	else
	{
		value = util::sext( opcode, 25 );
		set_dest_mem_reg_2( (opcode & 0x3C000000) >> 26, value );
	}
	m_icount -= 1;
}

// DMA instructions (SCU manual 5, DMA): the transfer counter is the 8 bit immediate or the low byte of
// a data RAM word, 0 meaning 256 (MiSTer DSP.sv TN0: the transfer ends when the decremented
// counter reaches 0). The address addition field is the raw bits 17-15 of both forms (the BIOS'
// sound upload uses bit 16 in the form with the counter in RAM; MiSTer SCU.sv takes DSP_DSO[17:15]
// whatever the form). A read steps its source by a longword when the field is not 0 and bit 1 is set,
// or the source is on the B-Bus; a write adds the SCU's write add value of the field (0, 2, 4, 8 ...
// 128 bytes) after each B-Bus halfword or C-Bus longword (SCU.sv DMA_RA_NEW, DMA_WA_NEW). RA0 follows each unit of a
// read when bit 1 is set and WA0 each unit but the last of a write, unless the instruction holds
// them; at the end of the transfer a read that did not step RA0 and every write add a longword
// (SCU.sv DMA_END && DMA_DSP).
void scudsp_cpu_device::op_dma( uint32_t opcode )
{
	uint8_t const hold = (opcode & 0x4000) >> 14;
	bool const counter_in_ram = BIT(opcode, 13);
	uint8_t const field = (opcode & 0x38000) >> 15;
	m_dma.dir = BIT(opcode, 12);
	m_dma.bank = (opcode & 0x700) >> 8;
	m_dma.field = field;

	unsigned size = counter_in_ram ? (get_source_mem_value(opcode & 7) & 0xff) : (opcode & 0xff);
	m_dma.size = size ? size : 256;

	if (m_dma.dir == 0)
	{
		m_dma.src = (m_ra0 << 2) & 0x07ff'ffff;
		m_dma.dst = m_dma.bank;
	}
	else
	{
		m_dma.src = m_dma.bank;
		m_dma.dst = (m_wa0 << 2) & 0x07ff'ffff;
	}

	m_dma.update = ( hold == 0 );
	m_dma.ex = 1;
	m_dma.count = 0;
	m_flags |= 1 << T0F;

	// take some time to actually set above, push in wait state
	m_dma_state = DMA_STATE_WAIT;
	m_dma_wait_ready = false;
	m_dma_forced = false;
	m_dma_force_cost = attotime::zero;
	m_out_ddwt_cb(1);
	m_out_ddmv_cb(0);
	m_dma_timer->adjust(attotime::from_ticks(4, this->clock()));

	m_icount -= 1;
}

void scudsp_cpu_device::op_jump( uint32_t opcode )
{
	if ( opcode & 0x3f80000 )
	{
		if ( compute_condition( (opcode & 0x3f80000) >> 19 ) )
		{
			m_delay = m_pc;
			m_delay_pending = true;
			m_pc = opcode & 0xff;
		}
	}
	else
	{
		m_delay = m_pc;
		m_delay_pending = true;
		m_pc = opcode & 0xff;
	}

	m_icount -= 1;
}

void scudsp_cpu_device::op_loop(uint32_t opcode)
{
	if ( opcode & 0x8000000 )
	{
		// LPS repeats the prefetched instruction, not the LPS instruction itself.
		// Reexecuting LPS between iterations doubled the repetition's cycle cost.
		m_loop_pc = m_pc;
		m_loop_opcode = scudsp_readop(m_pc++);
		m_loop_active = true;
	}
	else
	{
		/* BTM */
		if ( m_lop != 0 )
		{
			m_lop--;
			m_delay = m_pc;
			m_delay_pending = true;
			m_pc = m_top;
		}
	}
	m_icount -= 1;
}

void scudsp_cpu_device::op_end(uint32_t opcode)
{
	if(opcode & 0x08000000)
	{
		// set program end irq flag
		m_flags |= (1 << EF);
		m_out_irq_cb(1);
	}

	// clear the execute control flag (not running anymore)
	m_loop_active = false;
	m_flags &= ~(1 << EXF);
	m_icount -= 1;
}

void scudsp_cpu_device::op_illegal(uint32_t opcode)
{
	throw emu_fatalerror("scudsp illegal opcode at 0x%04x\n", m_pc);
	// m_icount -= 1;
}

// The end of a transfer: the flag drops, the buses are free and a program that waited for the DMA's
// RAM goes on. A program RAM transfer ends with the program counter back at the top (DSP.sv
// DMA_END_PEND && PRGW: PC <= TOP).
void scudsp_cpu_device::dma_end()
{
	// a read that did not step RA0 and every write move their register on by a longword (SCU.sv
	// DMA_END && DMA_DSP)
	if (m_dma_state != DMA_STATE_IDLE && m_dma.update)
	{
		if (m_dma.dir == 0 && !BIT(m_dma.field, 1))
			m_ra0 = (m_ra0 + 1) & 0x01ff'ffff;
		else if (m_dma.dir == 1)
			m_wa0 = (m_wa0 + 1) & 0x01ff'ffff;
	}

	m_out_ddwt_cb(0);
	m_out_ddmv_cb(0);
	m_dma.ex = 0;
	m_flags &= ~(1 << T0F);
	m_dma_state = DMA_STATE_IDLE;
	m_dma_wait_ready = false;
	m_dma_forced = false;
	m_dma_force_cost = attotime::zero;
	if (m_dma.dir == 0 && m_dma.bank == 4)
		m_pc = m_top;
	if (m_stalled)
	{
		m_stalled = false;
		set_input_line(INPUT_LINE_HALT, CLEAR_LINE);
	}
}

TIMER_CALLBACK_MEMBER(scudsp_cpu_device::dma_tick_cb)
{
	switch(m_dma_state)
	{
		case DMA_STATE_IDLE:
		case DMA_STATE_END:
			dma_end();
			break;
		case DMA_STATE_WAIT:
			if (m_dma_start_cb && !m_dma_start_cb())
			{
				m_dma_wait_ready = true;
				m_dma_timer->adjust(attotime::never);
				break;
			}
			m_dma_wait_ready = false;
			m_out_ddwt_cb(0);
			m_out_ddmv_cb(1);
			m_dma_state = m_dma_forced ? DMA_STATE_END : DMA_STATE_MOVE;
			m_dma_timer->adjust(m_dma_forced ? m_dma_force_cost : attotime::from_ticks(1, this->clock()));
			break;
		case DMA_STATE_MOVE:
		{
			if (m_dma_ready_cb && !m_dma_ready_cb(m_dma.dir ? m_dma.dst : m_dma.src, m_dma.dir != 0))
			{
				m_dma_timer->adjust(attotime::from_ticks(1, clock()));
				break;
			}
			exec_dma();
			m_dma.count++;
			if (m_dma.count >= m_dma.size)
				m_dma_state = DMA_STATE_END;

			// Completion, like the next unit, follows after this unit's bus accesses,
			// with a minimum of one DSP tick (70 nsec a.k.a. 1/~14 MHz).
			attotime wait = !m_dma_wait_cb ? attotime::zero : m_dma_wait_cb();
			attotime const tick = attotime::from_ticks(1, this->clock());
			m_dma_timer->adjust(wait > tick ? wait : tick);
			break;
		}
	}
}

// The SCU signals that the current DMA owner released the engine. Do not shorten
// the instruction's initial request delay if it has not expired yet.
void scudsp_cpu_device::dma_resume()
{
	if (m_dma_state == DMA_STATE_WAIT && m_dma_wait_ready)
		m_dma_timer->adjust(attotime::zero);
}

// The host asks for the buses while the DMA runs: its remaining units are carried out at once
attotime scudsp_cpu_device::dma_finish(attotime prior_wait)
{
	if (m_dma_state == DMA_STATE_IDLE)
		return attotime::zero;

	attotime const pending = m_dma_wait_ready ? attotime::zero : m_dma_timer->remaining();
	if (m_dma_forced)
		return pending + (m_dma_state == DMA_STATE_WAIT ? m_dma_force_cost : attotime::zero);

	// Fast-forward payload ordering for a host access, but preserve busy/ownership until
	// the scheduled acknowledgement. A queued request starts only after the prior owner.
	if (m_dma_state == DMA_STATE_WAIT && prior_wait == attotime::zero
			&& m_dma_start_cb && !m_dma_start_cb())
		return attotime::zero;

	attotime const tick = attotime::from_ticks(1, this->clock());
	attotime cost = m_dma_state == DMA_STATE_WAIT ? tick : attotime::zero;
	while (m_dma.count < m_dma.size)
	{
		if (m_dma_ready_cb && !m_dma_ready_cb(m_dma.dir ? m_dma.dst : m_dma.src, m_dma.dir != 0))
		{
			attotime const delay = pending + cost + tick;
			m_dma_timer->adjust(delay);
			return delay;
		}
		exec_dma();
		m_dma.count++;
		attotime const wait = !m_dma_wait_cb ? attotime::zero : m_dma_wait_cb();
		cost += wait > tick ? wait : tick;
	}
	m_dma_forced = true;
	if (m_dma_state == DMA_STATE_WAIT)
	{
		m_dma_force_cost = cost;
		attotime const start = prior_wait > pending ? prior_wait : pending;
		m_dma_wait_ready = false;
		m_dma_timer->adjust(start);
		return start + cost;
	}

	m_dma_state = DMA_STATE_END;
	m_dma_timer->adjust(pending + cost);
	return pending + cost;
}

// One transfer unit of a longword. The external side is a pair of 16 bit accesses; on the B-Bus a
// write moves the address by the write add value after each of them; on the other buses a longword
// is written and the address moves by the value once. The external
// address registers follow unless the instruction holds them (DMAH).
void scudsp_cpu_device::exec_dma()
{
	static constexpr uint32_t half_add[8] = { 0, 2, 4, 8, 16, 32, 64, 128 };
	uint32_t data;
	if ( m_dma.dir == 0 )
	{
		data = (m_in_dma_cb(m_dma.src)<<16) | m_in_dma_cb(m_dma.src+2);
		if (m_dma.bank == 4)
		{
			// the program RAM is written at the program counter
			scudsp_writeop(m_pc++, data);
		}
		else
			set_dest_dma_mem( m_dma.bank, data );

		// the source steps by a longword when bit 1 of the field is set, or always on the B-Bus, and
		// stays where it is when the field is 0; RA0 follows a stepping read
		bool const bbus = (m_dma.src & 0x07f0'0000) >= 0x05a0'0000 && (m_dma.src & 0x07f0'0000) < 0x05fe'0000;
		if (m_dma.field)
			m_dma.src += (bbus || BIT(m_dma.field, 1)) ? 4 : 0;
		if (m_dma.update && BIT(m_dma.field, 1))
			m_ra0 = (m_dma.src >> 2) & 0x01ff'ffff;
	}
	else
	{
		data = get_mem_source_dma( m_dma.bank );

		bool const bbus = (m_dma.dst & 0x07f0'0000) >= 0x05a0'0000 && (m_dma.dst & 0x07f0'0000) < 0x05fe'0000;
		uint32_t const half = half_add[m_dma.field];
		if (bbus)
		{
			m_out_dma_cb(m_dma.dst, data >> 16 );
			m_dma.dst += half;
			m_out_dma_cb(m_dma.dst, data & 0xffff );
			m_dma.dst += half;
		}
		else
		{
			m_out_dma_cb(m_dma.dst, data >> 16 );
			m_out_dma_cb(m_dma.dst + 2, data & 0xffff );
			m_dma.dst += half;
		}

		// WA0 follows every unit but the last (the end of the transfer adds its own longword)
		if (m_dma.update && m_dma.field && m_dma.count + 1 < m_dma.size)
			m_wa0 = (m_dma.dst >> 2) & 0x01ff'ffff;
	}
}

// A program that touches what a running DMA works with waits for its end (MiSTer DSP.sv sets
// PAUSED when an instruction reads or writes the data RAM of the transfer, writes or increments its
// CT, starts another DMA, or writes RA0 or WA0). The DSP is not stopped otherwise.
bool scudsp_cpu_device::dma_conflict(uint32_t opcode) const
{
	unsigned const bank = m_dma.bank & 3;
	// Conditional MVI with a false condition decodes no destination write.
	if ((opcode >> 30) == 2 && BIT(opcode, 25) && !compute_condition((opcode >> 19) & 0x7f))
		return false;

	auto const source = [bank] (unsigned s) { return (s & 3) == bank && (s < 8); };
	auto const dest = [bank] (unsigned d) { return d == bank || d == 0xc + bank || d == 6 || d == 7; };

	switch (opcode >> 30)
	{
		case 0: // an ALU instruction with its parallel moves
		{
			if (opcode & 0x2000000)
				if (source((opcode >> 20) & 7))
					return true;
			if (((opcode >> 23) & 3) == 3)
				if (source((opcode >> 20) & 7))
					return true;
			if (opcode & 0x80000)
				if (source((opcode >> 14) & 7))
					return true;
			if (((opcode >> 17) & 3) == 3)
				if (source((opcode >> 14) & 7))
					return true;
			switch ((opcode >> 12) & 3)
			{
				case 1:
					return dest((opcode >> 8) & 0xf);
				case 3:
					return source(opcode & 0xf) || dest((opcode >> 8) & 0xf);
			}
			return false;
		}
		case 2: // MVI
			return ((opcode >> 26) & 0xf) == bank || ((opcode >> 26) & 0xf) == 6
				|| ((opcode >> 26) & 0xf) == 7 || (m_dma.bank == 4 && ((opcode >> 26) & 0xf) == 0xc);
		case 3:
			return ((opcode >> 28) & 3) == 0;   // another DMA
	}
	return false;
}

/* Execute one instruction */
void scudsp_cpu_device::execute_one()
{
	uint32_t opcode;

	m_update_mul = 0;

	uint8_t const instruction_pc = m_loop_active ? m_loop_pc : (m_delay_pending ? m_delay : m_pc);

	// a program that needs what the running DMA uses waits for its end
	if (m_dma_state != DMA_STATE_IDLE && !m_stalled)
	{
		uint32_t const next = m_loop_active ? m_loop_opcode : scudsp_readop(instruction_pc);
		if (dma_conflict(next))
		{
			m_stalled = true;
			set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
			m_icount = 0;
			return;
		}
	}

	m_instruction_pc = instruction_pc;
	debugger_instruction_hook(instruction_pc);

	if (m_loop_active)
	{
		opcode = m_loop_opcode;
		if (m_lop)
			--m_lop;
		else
			m_loop_active = false;
	}
	else if (m_delay_pending)
	{
		opcode = scudsp_readop(m_delay);
		m_delay = 0;
		m_delay_pending = false;
	}
	else
	{
		opcode = scudsp_readop(m_pc);
		m_pc++;
	}

	switch( (opcode & 0xc0000000) >> 30 )
	{
		case 0x00: /* 00 */
			op_alu(opcode);
			break;
		case 0x01: /* 01 */
			op_illegal(opcode);
			break;
		case 0x02: /* 10 */
			op_move_immediate(opcode);
			break;
		case 0x03: /* 11 */
			switch( (opcode & 0x30000000) >> 28 )
			{
				case 0x00:
					op_dma(opcode);
					break;
				case 0x01:
					op_jump(opcode);
					break;
				case 0x02:
					op_loop(opcode);
					break;
				case 0x03:
					op_end(opcode);
					break;
			}
			break;
	}

	if ( m_update_mul == 1 )
	{
		m_mul = (int64_t)m_rx.si * (int64_t)m_ry.si;
		m_update_mul = 0;
	}
}

/* Execute cycles */
void scudsp_cpu_device::execute_run()
{
	// execution is paused by the host through the program control port
	if (m_paused || !BIT(m_flags, EXF))
	{
		m_icount = 0;
		return;
	}

	do
	{
		execute_one();
	} while (m_icount > 0 && BIT(m_flags, EXF));
}

device_memory_interface::space_config_vector scudsp_cpu_device::memory_space_config() const
{
	return space_config_vector {
		std::make_pair(AS_PROGRAM, &m_program_config),
		std::make_pair(AS_DATA,    &m_data_config)
	};
}

void scudsp_cpu_device::device_start()
{
	m_dma_timer = timer_alloc(FUNC(scudsp_cpu_device::dma_tick_cb), this);

	m_pc = 0;
	m_instruction_pc = 0;
	m_flags = 0;
	m_paused = false;
	m_delay = 0;
	m_delay_pending = false;
	m_loop_active = false;
	m_loop_pc = 0;
	m_loop_opcode = 0;
	m_top = 0;
	m_lop = 0;
	memset(&m_rx, 0x00, sizeof(m_rx));
	m_mul = 0;
	memset(&m_ry, 0x00, sizeof(m_ry));
	m_alu = 0;
	memset(&m_ph, 0x00, sizeof(m_ph));
	memset(&m_pl, 0x00, sizeof(m_pl));
	memset(&m_ach, 0x00, sizeof(m_ach));
	memset(&m_acl, 0x00, sizeof(m_acl));
	m_ra0 = 0;
	m_wa0 = 0;
	m_ra = 0;
	m_ct[0] = 0;
	m_ct[1] = 0;
	m_ct[2] = 0;
	m_ct[3] = 0;
	memset(&m_dma, 0x00, sizeof(m_dma));
	m_stalled = false;

	m_program = &space(AS_PROGRAM);
	m_data = &space(AS_DATA);

	save_item(NAME(m_pc));
	save_item(NAME(m_instruction_pc));
	save_item(NAME(m_ra));

	save_item(NAME(m_ct));

	save_item(NAME(m_flags));
	save_item(NAME(m_delay));
	save_item(NAME(m_delay_pending));
	save_item(NAME(m_loop_active));
	save_item(NAME(m_loop_pc));
	save_item(NAME(m_loop_opcode));
	save_item(NAME(m_paused));

	save_item(NAME(m_top));
	save_item(NAME(m_lop));
	save_item(NAME(m_rx.ui));

	save_item(NAME(m_mul));

	save_item(NAME(m_ry.ui));

	save_item(NAME(m_alu));
	save_item(NAME(m_ph.ui));
	save_item(NAME(m_pl.ui));
	save_item(NAME(m_ach.ui));
	save_item(NAME(m_acl.ui));
	save_item(NAME(m_ra0));
	save_item(NAME(m_wa0));

	save_item(NAME(m_dma.src));
	save_item(NAME(m_dma.dst));
	save_item(NAME(m_dma.size));
	save_item(NAME(m_dma.field));
	save_item(NAME(m_dma.bank));
	save_item(NAME(m_dma.update));
	save_item(NAME(m_dma.ex));
	save_item(NAME(m_dma.dir));
	save_item(NAME(m_dma.count));
	save_item(NAME(m_dma_state));
	save_item(NAME(m_dma_wait_ready));
	save_item(NAME(m_dma_forced));
	save_item(NAME(m_dma_force_cost));
	save_item(NAME(m_stalled));

	// Register state for debugger
	state_add( SCUDSP_PC, "PC", m_pc ).formatstr("%02X");
	state_add( SCUDSP_FLAGS, "SR", m_flags ).formatstr("%08X");
	state_add( SCUDSP_DELAY, "DELAY", m_delay ).formatstr("%02X").noshow();
	state_add( SCUDSP_TOP, "TOP", m_top).formatstr("%02X");
	state_add( SCUDSP_LOP, "LOP", m_lop).formatstr("%03X");
	state_add( SCUDSP_RX, "RX", m_rx.ui).formatstr("%08X");
	state_add( SCUDSP_MUL, "MUL", m_mul).formatstr("%012X");
	state_add( SCUDSP_RY, "RY", m_ry.ui).formatstr("%08X");
	state_add( SCUDSP_ALU, "ALU", m_alu).formatstr("%012X");
	state_add( SCUDSP_PH, "PH", m_ph.ui).formatstr("%04X");
	state_add( SCUDSP_PL, "PL", m_pl.ui).formatstr("%08X");
	state_add( SCUDSP_ACH, "ACH", m_ach.ui).formatstr("%04X");
	state_add( SCUDSP_ACL, "ACL", m_acl.ui).formatstr("%08X");
	state_add( SCUDSP_RA0, "RA0", m_ra0).formatstr("%08X");
	state_add( SCUDSP_WA0, "WA0", m_wa0).formatstr("%08X");
	state_add( SCUDSP_RA, "RA", m_ra ).formatstr("%02X");
	state_add( SCUDSP_CT0, "CT0", m_ct[0] ).formatstr("%02X");
	state_add( SCUDSP_CT1, "CT1", m_ct[1] ).formatstr("%02X");
	state_add( SCUDSP_CT2, "CT2", m_ct[2] ).formatstr("%02X");
	state_add( SCUDSP_CT3, "CT3", m_ct[3] ).formatstr("%02X");
	state_add( STATE_GENPC, "GENPC", m_pc ).noshow();
	state_add( STATE_GENPCBASE, "CURPC", m_instruction_pc ).noshow();
	state_add( STATE_GENFLAGS, "GENFLAGS", m_flags ).formatstr("%17s").noshow();

	set_icountptr(m_icount);
}

void scudsp_cpu_device::device_reset()
{
	m_out_ddwt_cb(0);
	m_out_ddmv_cb(0);
	m_dma_timer->adjust(attotime::never);
	m_dma_state = DMA_STATE_IDLE;
	m_dma_wait_ready = false;
	m_dma_forced = false;
	m_dma_force_cost = attotime::zero;
	if (m_stalled)
		set_input_line(INPUT_LINE_HALT, CLEAR_LINE);
	m_stalled = false;
}

void scudsp_cpu_device::program_map(address_map &map)
{
	map(0x00, 0xff).ram();
}

void scudsp_cpu_device::data_map(address_map &map)
{
	map(0x00, 0xff).ram();
}

scudsp_cpu_device::scudsp_cpu_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: cpu_device(mconfig, SCUDSP, tag, owner, clock)
	, m_out_irq_cb(*this)
	, m_in_dma_cb(*this, 0)
	, m_out_dma_cb(*this)
	, m_out_ddwt_cb(*this)
	, m_out_ddmv_cb(*this)
	, m_program_config("program", ENDIANNESS_BIG, 32, 8, -2, address_map_constructor(FUNC(scudsp_cpu_device::program_map), this))
	, m_data_config("data", ENDIANNESS_BIG, 32, 8, -2, address_map_constructor(FUNC(scudsp_cpu_device::data_map), this))
{
}


void scudsp_cpu_device::state_string_export(const device_state_entry &entry, std::string &str) const
{
	switch (entry.index())
	{
		case STATE_GENFLAGS:
			str = string_format("%s%s%s%c%c%c%c%c%s%s%s",
				m_flags & 0x4000000 ? "PR":"..",
				m_paused ? "EP":"..",
				m_flags & 0x800000 ? "T0":"..",
				m_flags & 0x400000 ? 'S':'.',
				m_flags & 0x200000 ? 'Z':'.',
				m_flags & 0x100000 ? 'C':'.',
				m_flags & 0x80000 ? 'V':'.',
				m_flags & 0x40000 ? 'E':'.',
				m_flags & 0x20000 ? "ES":"..",
				m_flags & 0x10000 ? "EX":"..",
				m_flags & 0x8000 ? "LE":"..");
			break;
	}
}


std::unique_ptr<util::disasm_interface> scudsp_cpu_device::create_disassembler()
{
	return std::make_unique<scudsp_disassembler>();
}

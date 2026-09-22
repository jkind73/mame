// license:BSD-3-Clause
// copyright-holders:Angelo Salese
/**************************************************************************************************

Sega Saturn System Control Unit (c) 1995 Sega/Yamaha

TODO:
- implement penalties for attached devices when DMA-ing from/to;
- implement additional DMA rulesets
\- can't access same bus in direct mode;
\- indirect mode can actually access same bus with some quirks, specifics TBD;
\- avoid cross country DMA-ing from one region to the other, i.e. gunblaze;
\- Road Blaster shifted 1-byte quirk, cfr. currently unused function
(intentionally broken);
- Verify Timer 1 (seems unaffected even after rewriting it?)
- A-Bus external interrupts;
- A-Bus waitstates;
- PAD irq signal from SMPC (lightgun and some mice);

===================================================================================================

Interesting use cases (i.e. non-sloppy programming plaguing this system):
- 3dlemminj: title screen "3d" logo going fast and glitchy (wants VDP1 timing
down everything else)
- burningrj: transfers FMV in VDP2 (cached) in display area (delayed one frame
and done later? Current performance is quite bad right now)

A-Bus: $0200'0000 - $058f'ffff
B-Bus: $0590'0000 - $05ff'ffff
C-Bus: $0600'0000 - $07ff'ffff (Work RAM-H, mirrored)

**************************************************************************************************/

#include "emu.h"
#include "saturn_scu.h"


#define LOG_DMA_MOVE                                                           \
  (1 << 1) // log the initial values prior to a DMA WAIT -> MOVE
#define LOG_DMA_END (1 << 2)      // log the values at end of DMA
#define LOG_DMA_STATE (1 << 3)    // log state changes
#define LOG_DMA_MODE (1 << 4)     // log accepted transfer state
#define LOG_DMA_INDIRECT (1 << 5) // log indirect fetches (verbose)

#define VERBOSE (LOG_GENERAL)
// #define LOG_OUTPUT_FUNC osd_printf_info

#include "logmacro.h"

// device type definition
DEFINE_DEVICE_TYPE(SATURN_SCU, saturn_scu_device, "saturn_scu",
                   "Sega Saturn System Control Unit (Yamaha FH3007 315-5688)")

//-------------------------------------------------
//  saturn_scu_device - constructor
//-------------------------------------------------

saturn_scu_device::saturn_scu_device(const machine_config &mconfig,
                                     const char *tag, device_t *owner,
                                     uint32_t clock)
    : device_t(mconfig, SATURN_SCU, tag, owner, clock),
      m_scudsp(*this, "scudsp"), m_hostcpu(*this, finder_base::DUMMY_TAG),
      m_main_dtack_cb(*this), m_main_steal_cb(*this), m_sound_dtack_cb(*this),
      m_sound_steal_cb(*this) {}

//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

template <unsigned Level> void saturn_scu_device::dma_map(address_map &map) {
  // ST-097 section 3.2: DxR/DxW store bits 26:0, not SH-2 cache aliases.
  map(0x00, 0x03)
      .lrw32(NAME([this](offs_t offset) { return m_dma[Level].src; }),
             NAME([this](offs_t offset, u32 data, u32 mem_mask) {
               COMBINE_DATA(&m_dma[Level].src);
               m_dma[Level].src &= 0x07ff'ffff;
             }));
  map(0x04, 0x07)
      .lrw32(NAME([this](offs_t offset) { return m_dma[Level].dst; }),
             NAME([this](offs_t offset, u32 data, u32 mem_mask) {
               COMBINE_DATA(&m_dma[Level].dst);
               m_dma[Level].dst &= 0x07ff'ffff;
             }));
  map(0x08, 0x0b)
      .lrw32(NAME([this](offs_t offset) { return m_dma[Level].size; }),
             NAME([this](offs_t offset, u32 data, u32 mem_mask) {
               COMBINE_DATA(&m_dma[Level].size);
               m_dma[Level].size &= ((Level == 0) ? 0x000fffff : 0xfff);
             }));
  // everything else is write only
  map(0x0c, 0x17).nopr();
  // DxAD: add values
  map(0x0c, 0x0f).lw32(NAME([this](offs_t offset, u32 data, u32 mem_mask) {
    if (ACCESSING_BITS_8_15)
      m_dma[Level].src_add = BIT(data, 8) * 4;
    if (ACCESSING_BITS_0_7) {
      m_dma[Level].dst_add = 1 << (data & 7);
      if (m_dma[Level].dst_add == 1) {
        m_dma[Level].dst_add = 0;
      }
    }
  }));
  // DxEN / DxGO: enable and trigger
  map(0x10, 0x13).lw32(NAME([this](offs_t offset, u32 data, u32 mem_mask) {
    if (ACCESSING_BITS_8_15)
      m_dma[Level].enable_mask = BIT(data, 8);

    // check if DxGO is enabled for start factor = 7
    if (ACCESSING_BITS_0_7 && m_dma[Level].enable_mask == true &&
        BIT(data, 0) && m_dma[Level].start_factor == DMA_EVENT_TRIGGER) {
      if (m_dma[Level].indirect_mode == true)
        trigger_dma_indirect(Level);
      else
        trigger_dma_direct(Level);
    }
  }));
  // DxMOD / DxRUP / DxWUP / DxFT: indirect mode, RUP, WUP, start factor
  map(0x14, 0x17).lw32(NAME([this](offs_t offset, u32 data, u32 mem_mask) {
    if (ACCESSING_BITS_24_31)
      m_dma[Level].indirect_mode = BIT(data, 24);
    if (ACCESSING_BITS_16_23)
      m_dma[Level].rup = BIT(data, 16);
    if (ACCESSING_BITS_8_15)
      m_dma[Level].wup = BIT(data, 8);
    if (ACCESSING_BITS_0_7) {
      m_dma[Level].start_factor = data & 7;
      if (m_dma[Level].start_factor != 7)
        LOG("DMA%d start factor set %02x\n", Level, m_dma[Level].start_factor);
    }
  }));
}

// Instantiate DMA maps
template void saturn_scu_device::dma_map<0>(address_map &map);
template void saturn_scu_device::dma_map<1>(address_map &map);
template void saturn_scu_device::dma_map<2>(address_map &map);

void saturn_scu_device::regs_map(address_map &map) {
  map(0x0000, 0x0017).m(*this, FUNC(saturn_scu_device::dma_map<0>));
  map(0x0020, 0x0037).m(*this, FUNC(saturn_scu_device::dma_map<1>));
  map(0x0040, 0x0057).m(*this, FUNC(saturn_scu_device::dma_map<2>));
  // stv:smleague and shinmtaz reads from $005c (undocumented), DMA status
  // mirror?
  map(0x005c, 0x005f).r(FUNC(saturn_scu_device::dma_status_r));
  map(0x0060, 0x0063).w(FUNC(saturn_scu_device::dma_force_stop_w));
  map(0x007c, 0x007f).r(FUNC(saturn_scu_device::dma_status_r));
  map(0x0080, 0x0083)
      .rw(m_scudsp, FUNC(scudsp_cpu_device::program_control_r),
          FUNC(scudsp_cpu_device::program_control_w));
  map(0x0084, 0x0087).w(m_scudsp, FUNC(scudsp_cpu_device::program_w));
  map(0x0088, 0x008b)
      .w(m_scudsp, FUNC(scudsp_cpu_device::ram_address_control_w));
  map(0x008c, 0x008f)
      .rw(m_scudsp, FUNC(scudsp_cpu_device::ram_address_r),
          FUNC(scudsp_cpu_device::ram_address_w));
  map(0x0090, 0x0093).w(FUNC(saturn_scu_device::t0_compare_w));
  map(0x0094, 0x0097).w(FUNC(saturn_scu_device::t1_setdata_w));
  // T1MD is at $0098 (bit 8 T1MD, bit 0 TENB); it was mapped at $009a, which in
  // this 32-bit space left $0098-$0099 unmapped and delivered the *upper* half
  // of a longword write to $05fe0098 to the handler, so the SCU timers were
  // never enabled
  map(0x0098, 0x009b).w(FUNC(saturn_scu_device::t1_mode_w));
  map(0x00a0, 0x00a3)
      .rw(FUNC(saturn_scu_device::irq_mask_r),
          FUNC(saturn_scu_device::irq_mask_w));
  map(0x00a4, 0x00a7)
      .rw(FUNC(saturn_scu_device::irq_status_r),
          FUNC(saturn_scu_device::irq_status_w));
  map(0x00a8, 0x00ab).w(FUNC(saturn_scu_device::abus_irqack_w));
  // ASR0/ASR1 (A-Bus access settings) and AREF (A-Bus refresh): Sega's SCU
  // register table and the memory-map notes both place them here, and TB47
  // describes the wait-state fields they carry
  map(0x00b0, 0x00b7).w(FUNC(saturn_scu_device::abus_set_w));
  map(0x00b8, 0x00bb).w(FUNC(saturn_scu_device::abus_refresh_w));
  //  map(0x00c4, 0x00c7).rw(FUNC(saturn_scu_device::sdram_r),
  //  FUNC(saturn_scu_device::sdram_w));
  map(0x00c8, 0x00cb).r(FUNC(saturn_scu_device::version_r));
}

//-------------------------------------------------
//  add_device_mconfig - device-specific machine
//  configuration addiitons
//-------------------------------------------------

uint16_t saturn_scu_device::scudsp_dma_r(offs_t offset, uint16_t mem_mask) {
  // address_space &program = m_maincpu->space(AS_PROGRAM);
  offs_t addr = offset & 0x07ff'ffff;

  //  printf("%08x\n", offset);

  return m_hostspace->read_word(addr, mem_mask);
}

void saturn_scu_device::scudsp_dma_w(offs_t offset, uint16_t data,
                                     uint16_t mem_mask) {
  // address_space &program = m_maincpu->space(AS_PROGRAM);
  offs_t addr = offset & 0x07ff'ffff;

  //  printf("%08x %02x\n",offset,data);

  m_hostspace->write_word(addr, data, mem_mask);
}

void saturn_scu_device::device_add_mconfig(machine_config &config) {
  SCUDSP(config, m_scudsp, XTAL(57'272'727) / 4); // 14 MHz
  m_scudsp->out_irq_callback().set(DEVICE_SELF,
                                   FUNC(saturn_scu_device::scudsp_end_w));
  m_scudsp->in_dma_callback().set(FUNC(saturn_scu_device::scudsp_dma_r));
  m_scudsp->out_dma_callback().set(FUNC(saturn_scu_device::scudsp_dma_w));
  m_scudsp->out_ddwt_callback().set([this](int state) {
    if (state)
      m_dma_status |= DMA_DSP_WAIT;
    else
      m_dma_status &= ~(DMA_DSP_WAIT);
  });
  m_scudsp->out_ddmv_callback().set([this](int state) {
    // m_main_dtack_cb(state);
    if (state)
      m_dma_status |= DMA_DSP_MOVE;
    else
      m_dma_status &= ~(DMA_DSP_MOVE);
  });
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void saturn_scu_device::device_start() {
  save_item(NAME(m_ist));
  save_item(NAME(m_ism));
  save_item(NAME(m_abus_pending_ack));
  save_item(NAME(m_abus_asr));
  save_item(NAME(m_abus_aref));
  save_item(NAME(m_t0c));
  save_item(NAME(m_t1s));
  save_item(NAME(m_t1md_reg));
  save_item(NAME(m_dma_status));
  save_item(NAME(m_current_vector));
  save_item(NAME(m_timer0_counter));
  save_item(NAME(m_t1md));
  // m_tenb is derived from m_t1md_reg but is not recomputed on load, so it has
  // to be saved in its own right or the timers stay disabled after a restore
  save_item(NAME(m_tenb));

  save_item(NAME(m_dma[0].src));
  save_item(NAME(m_dma[0].dst));
  save_item(NAME(m_dma[0].src_add));
  save_item(NAME(m_dma[0].dst_add));
  save_item(NAME(m_dma[0].size));
  save_item(NAME(m_dma[0].index));
  save_item(NAME(m_dma[0].start_factor));
  save_item(NAME(m_dma[0].enable_mask));
  save_item(NAME(m_dma[0].indirect_mode));
  save_item(NAME(m_dma[0].indirect_fetch_phase));
  save_item(NAME(m_dma[0].indirect_end_flag));
  save_item(NAME(m_dma[0].rup));
  save_item(NAME(m_dma[0].wup));
  save_item(NAME(m_dma[0].mode));
  save_item(NAME(m_dma[0].done));
  save_item(NAME(m_dma[0].pending_trigger));
  save_item(NAME(m_dma[0].live_src));
  save_item(NAME(m_dma[0].live_dst));
  save_item(NAME(m_dma[0].live_size));
  save_item(NAME(m_dma[0].live_count));
  save_item(NAME(m_dma[0].read_buffer));
  save_item(NAME(m_dma[0].read_address));
  save_item(NAME(m_dma[0].read_offset));
  save_item(NAME(m_dma[0].read_buffer_valid));
  save_item(NAME(m_dma[0].bbus_sound_access));
  save_item(NAME(m_dma[0].transfer_penalty));

  save_item(NAME(m_dma[1].src));
  save_item(NAME(m_dma[1].dst));
  save_item(NAME(m_dma[1].src_add));
  save_item(NAME(m_dma[1].dst_add));
  save_item(NAME(m_dma[1].size));
  save_item(NAME(m_dma[1].index));
  save_item(NAME(m_dma[1].start_factor));
  save_item(NAME(m_dma[1].enable_mask));
  save_item(NAME(m_dma[1].indirect_mode));
  save_item(NAME(m_dma[1].indirect_fetch_phase));
  save_item(NAME(m_dma[1].indirect_end_flag));
  save_item(NAME(m_dma[1].rup));
  save_item(NAME(m_dma[1].wup));
  save_item(NAME(m_dma[1].mode));
  save_item(NAME(m_dma[1].done));
  save_item(NAME(m_dma[1].pending_trigger));
  save_item(NAME(m_dma[1].live_src));
  save_item(NAME(m_dma[1].live_dst));
  save_item(NAME(m_dma[1].live_size));
  save_item(NAME(m_dma[1].live_count));
  save_item(NAME(m_dma[1].read_buffer));
  save_item(NAME(m_dma[1].read_address));
  save_item(NAME(m_dma[1].read_offset));
  save_item(NAME(m_dma[1].read_buffer_valid));
  save_item(NAME(m_dma[1].bbus_sound_access));
  save_item(NAME(m_dma[1].transfer_penalty));

  save_item(NAME(m_dma[2].src));
  save_item(NAME(m_dma[2].dst));
  save_item(NAME(m_dma[2].src_add));
  save_item(NAME(m_dma[2].dst_add));
  save_item(NAME(m_dma[2].size));
  save_item(NAME(m_dma[2].index));
  save_item(NAME(m_dma[2].start_factor));
  save_item(NAME(m_dma[2].enable_mask));
  save_item(NAME(m_dma[2].indirect_mode));
  save_item(NAME(m_dma[2].indirect_fetch_phase));
  save_item(NAME(m_dma[2].indirect_end_flag));
  save_item(NAME(m_dma[2].rup));
  save_item(NAME(m_dma[2].wup));
  save_item(NAME(m_dma[2].mode));
  save_item(NAME(m_dma[2].done));
  save_item(NAME(m_dma[2].pending_trigger));
  save_item(NAME(m_dma[2].live_src));
  save_item(NAME(m_dma[2].live_dst));
  save_item(NAME(m_dma[2].live_size));
  save_item(NAME(m_dma[2].live_count));
  save_item(NAME(m_dma[2].read_buffer));
  save_item(NAME(m_dma[2].read_address));
  save_item(NAME(m_dma[2].read_offset));
  save_item(NAME(m_dma[2].read_buffer_valid));
  save_item(NAME(m_dma[2].bbus_sound_access));
  save_item(NAME(m_dma[2].transfer_penalty));

  save_item(NAME(m_current_irq_level));

  m_hostspace = &m_hostcpu->space(AS_PROGRAM);

  m_dma_tick_timer = timer_alloc(FUNC(saturn_scu_device::dma_tick_cb), this);
  m_timer1 = timer_alloc(FUNC(saturn_scu_device::timer1_irq_cb), this);
}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void saturn_scu_device::device_reset() {
  m_ism = 0xbfff;
  m_ist = 0;
  m_abus_pending_ack = 0;
  m_abus_asr[0] = 0;
  m_abus_asr[1] = 0;
  // ST-210 No.33 supersedes the original AREF reset value: ARFEN starts set.
  m_abus_aref = 0x10;

  // every dma_channel_t member has to be given a value here: the device
  // constructor leaves them indeterminate, and the DMA logic reads the flags
  // as soon as a channel leaves DMA_MODE_RESET, so an unset bool was being
  // loaded with a non-0/1 value (UBSAN invalid-bool-load, see mamedev/mame
  // issue 15773)
  for (int i = 0; i < 3; i++) {
    m_dma[i].src = 0;
    m_dma[i].dst = 0;
    m_dma[i].src_add = 4;
    m_dma[i].dst_add = 2;
    m_dma[i].size = 0;
    m_dma[i].index = 0;
    m_dma[i].live_src = 0;
    m_dma[i].live_dst = 0;
    m_dma[i].live_size = 0;
    m_dma[i].live_count = 0;
    m_dma[i].read_buffer = 0;
    m_dma[i].read_address = 0;
    m_dma[i].read_offset = 0;
    m_dma[i].read_buffer_valid = false;
    m_dma[i].start_factor = DMA_EVENT_TRIGGER;
    m_dma[i].mode = DMA_MODE_RESET;
    m_dma[i].enable_mask = false;
    m_dma[i].indirect_mode = false;
    m_dma[i].indirect_fetch_phase = false;
    m_dma[i].indirect_end_flag = false;
    m_dma[i].rup = false;
    m_dma[i].wup = false;
    m_dma[i].done = false;
    m_dma[i].pending_trigger = false;
    m_dma[i].bbus_sound_access = false;
    m_dma[i].transfer_penalty = 0;
  }

  m_dma_tick_timer->adjust(attotime::never);
  m_dma_status = 0;
  m_current_irq_level = 0;
  m_current_vector = 0;

  // Release only SCU-owned stalls; the driver preserves SMPC HALT separately.
  m_sound_dtack_cb(0);
  m_main_dtack_cb(0);

  m_tenb = false;
  m_t1md = false;
  m_timer0_counter = 0;
  // timer 0 compares against m_t0c and timer 1 is armed for m_t1s ticks, so
  // both latches need a defined value before anything enables the timers
  m_t0c = 0;
  m_t1s = 0;
  m_t1md_reg = 0;
  m_timer1->adjust(attotime::never);
}

void saturn_scu_device::device_clock_changed() {
  m_scudsp->set_unscaled_clock(this->clock() / 4);
  // FIXME: should be /4 but saturn BIOS already disagrees
  // (or /2 if the doc claims 70 nsec in dword unit)
  m_dma_clock_ref = this->clock() / 1;
  LOG("New ref DMA clock %u\n", m_dma_clock_ref);
}

//**************************************************************************
//  DMA logic
//**************************************************************************

inline void saturn_scu_device::update_dma_status(int level,
                                                 dma_state_t new_state) {
  char const *const status_names[] = {"IDLE", "MOVE", "WAIT", "????"};
  constexpr int log_shifts[] = {4, 8, 12};
  assert(level >= 0);

  LOGMASKED(LOG_DMA_STATE, "DMA%d state change %s -> ", level,
            status_names[(m_dma_status >> log_shifts[level]) & 0x3]);

  m_dma_status &= ~(0x30 << 4 * level);
  m_dma_status |= (new_state << 4 * level);

  LOGMASKED(LOG_DMA_STATE, "%s (%08x)\n",
            status_names[(m_dma_status >> log_shifts[level]) & 0x3],
            m_dma_status);
}

std::tuple<u16, int> saturn_scu_device::get_address_flags(u32 address,
                                                          bool write_op) {
  // can't use .flags for now:
  // 1. has a noticeable performance penalty
  // 2. A-Bus in clients needs modernizing
  // 3. .m type address maps with flags are ignored and really propagates
  // downstream
  //    i.e. need to repeat .flags declarations inside every single device .rw
  //  std::tie(std::ignore, flags) = m_bus_space.read_word_flags(address &
  //  0x07ff'ffff);

  u16 flags = 0;
  // TODO: waitstate penalties needs HW tests
  // Also eventually needs to be in client address_maps as .before_delay
  int penalty = 0;

  /* A-Bus wait counts come from the ASR0/ASR1 registers ($B0-$B7): A0NW is
     bits 23-20 of ASR0, A1NW bits 7-4 of ASR0 and A3NW bits 7-4 of ASR1.  The
     MiSTer core's A-Bus sequencer builds the wait counter as
     "AnNW + 3 (+ ARWT when a refresh falls inside the access)"; the refresh
     term is per-access and dynamic, so only the fixed part is modelled
     here. */
  int const a0nw = (m_abus_asr[0] >> 20) & 0x0f;
  int const a1nw = (m_abus_asr[0] >> 4) & 0x0f;
  int const a3nw = (m_abus_asr[1] >> 4) & 0x0f;

  switch (address & 0x0700'0000) {
  case 0x0200'0000:
  case 0x0300'0000:
    flags = saturn_scu_device::A_BUS_CS0;
    penalty = a0nw + 3;
    break;
  case 0x0400'0000:
    flags = saturn_scu_device::A_BUS_CS1;
    penalty = a1nw + 3;
    break;
  case 0x0500'0000: {
    switch (address & 0x00f0'0000) {
    case 0x0080'0000:
      flags = saturn_scu_device::A_BUS_CS2;
      penalty = a3nw + 3;
      break;
    case 0x00a0'0000:
    case 0x00b0'0000:
      flags = saturn_scu_device::B_BUS_SCSP;
      // penalty = write_op ? 13 : 24;
      break;
    case 0x00c0'0000:
    case 0x00d0'0000:
      flags = saturn_scu_device::B_BUS_VDP1;
      // penalty = write_op ? 9 : 14;
      break;
    case 0x00e0'0000:
      flags = saturn_scu_device::B_BUS_VDP2;
      // penalty = write_op ? 3 : 20;
      break;
    case 0x00f0'0000:
      if ((address & 0x000f'0000) < 0x000e'0000) {
        flags = saturn_scu_device::B_BUS_VDP2;
        // penalty = write_op ? 3 : 20;
      } else {
        flags = saturn_scu_device::B_BUS_SCU;
        // penalty = write_op ? 4 : 8;
      }
      break;

    default:
      if ((address & 0x0080'0000) == 0) {
        flags = saturn_scu_device::A_BUS_DUMMY;
      }
    }
    break;
  }
  case 0x0600'0000:
  case 0x0700'0000: {
    // Work RAM H occupies the C-Bus window through $07ffffff; the 1 MiB
    // RAM is mirrored throughout it in both Saturn and ST-V address maps.
    flags = saturn_scu_device::C_BUS;
    // TODO: overhead due of SDRAM refresh?
  }
  }

  return std::make_tuple(flags, penalty);
}

void saturn_scu_device::trigger_dma_direct(uint8_t level) {
  // registers are DxR, DxW etc.
  LOGMASKED(LOG_DMA_MOVE,
            "DMA%d direct R %08x W %08x C %08x RA %d WA %d %s %s\n", level,
            m_dma[level].src, m_dma[level].dst, m_dma[level].size,
            m_dma[level].src_add, m_dma[level].dst_add,
            m_dma[level].rup ? "RUP" : "", m_dma[level].wup ? "WUP" : "");

  // stv:vmahjong loads game IPL twice at startup, one with cache the other
  // without.
  /* each level's status field is the two bits at 4 + level * 4 - see the
     DMA_LVn_MOVE/WAIT values in dma_status_t, update_dma_status() and
     check_dma_level_round_robin() - so shifting the pair mask by level
     rather than by level * 4 tested DMA0's wait bit for level 1 and two
     bits nothing ever sets for level 2. */
  if (m_dma_status & (0x30 << (level * 4))) {
    /* SCU Final Specifications and Precautions (ST-210-110194) No.22: a
       start trigger that arrives while the transfer is executing is held
       (once) and the DMA is activated again after it ends. */
    LOG("In-flight DMA%d attempt, holding trigger\n", level);
    m_dma[level].pending_trigger = true;
    return;
  }

  auto const [src_flags, src_penalty] =
      get_address_flags(m_dma[level].src, false);
  auto const [dst_flags, dst_penalty] =
      get_address_flags(m_dma[level].dst, true);

  //  printf("%04x %04x\n", src_flags, dst_flags);

  // check if params are well formed:
  // - can't transfer from BIOS, Work RAM L, backup RAM (gamebas, wc98,
  // batmanfu)
  // - SCU also can't do same bus transfers
  // - the controller has no path to its own register space at all
  // - SCU Final Specifications and Precautions (ST-210-110194): No.01 makes the
  //   A-Bus a read source only, never a DMA destination, and No.02 makes the
  //   VDP2 area a destination only, never a source.  Either violation is the
  //   same DMA-illegal condition: the interrupt is raised and nothing moves.
  if (src_flags == 0 || dst_flags == 0 ||
      (src_flags & 0x0300) == (dst_flags & 0x0300) || src_flags == B_BUS_SCU ||
      dst_flags == B_BUS_SCU || (dst_flags & 0x0300) == 0x0100 ||
      src_flags == B_BUS_VDP2) {
    LOG("DMA%d illegal setup (ignored): R %08x W %08x\n", level,
        m_dma[level].src, m_dma[level].dst);
    m_ist |= IST_DMAILL;
    test_pending_irqs();
    return;
  }

  // Keep the programmed 20-bit/12-bit count separate from the expanded
  // live byte total, so each activation decodes zero as the maximum again.
  // ST-210 No.15 supersedes ST-097 p.42: DxC readback is not guaranteed.
  uint32_t transfer_size = m_dma[level].size;
  if (transfer_size == 0)
    transfer_size = (level == 0) ? 0x00100000 : 0x1000;

  // Keep the existing VDP1 boundary workaround confined to this transfer.
  // gunblaze: during startup tries to do a max sized DMA transfer to VDP1 that
  // would eventually hit fb/regs
  if ((m_dma[level].dst & 0x07f0'0000) == 0x05c0'0000 &&
      transfer_size >= 0x80000)
    transfer_size = 0x80000 - (m_dma[level].dst & 0x7fffe);

  m_dma[level].mode = DMA_MODE_RESET;

  // CD transfers are special even without the hack below
  if (m_dma[level].src_add == 0 &&
      (m_dma[level].src & 0x07ff'ffff) == 0x0581'8000) {
    LOGMASKED(LOG_DMA_MODE, "Mode select: CD\n");
    m_dma[level].mode |= DMA_MODE_CD;
  }

  // if target is Work RAM H, the add value is fixed.
  // behaviour confirmed by astrass, fromanc2, stv:vmahjong and burningr*
  if (dst_flags == C_BUS) {
    LOGMASKED(LOG_DMA_MODE, "Mode select: C-Bus Write\n");
    m_dma[level].mode |= DMA_MODE_CBUS_WRITE;
  }

  m_dma[level].bbus_sound_access =
      src_flags == B_BUS_SCSP || dst_flags == B_BUS_SCSP;

  m_dma[level].live_src = m_dma[level].src;
  m_dma[level].live_dst = m_dma[level].dst;
  m_dma[level].live_size = transfer_size;
  m_dma[level].live_count = 0;
  m_dma[level].read_buffer_valid = false;
  m_dma[level].done = false;
  m_dma[level].transfer_penalty = src_penalty + dst_penalty;

  update_dma_status(level, DMA_STATE_WAIT);

  // yield a bunch of cycles between WAIT and actual execution.
  // Some games will set a buffer at $60ffcbd and expects that the irq happens
  // *after* it.
  // - avg (character selection)
  // - dejig* (main menu moving cursor)
  // - stv:danchih/danchiq (title screen)
  m_dma_tick_timer->adjust(attotime::from_ticks(2 * 4, m_dma_clock_ref));
}

void saturn_scu_device::trigger_dma_indirect(uint8_t level) {
  LOGMASKED(LOG_DMA_MOVE, "DMA%d indirect W %08x RA %d WA %d\n", level,
            m_dma[level].dst, m_dma[level].src_add, m_dma[level].dst_add);

  /* each level's status field is the two bits at 4 + level * 4 - see the
     DMA_LVn_MOVE/WAIT values in dma_status_t, update_dma_status() and
     check_dma_level_round_robin() - so shifting the pair mask by level
     rather than by level * 4 tested DMA0's wait bit for level 1 and two
     bits nothing ever sets for level 2. */
  if (m_dma_status & (0x30 << (level * 4))) {
    /* SCU Final Specifications and Precautions (ST-210-110194) No.22: a
       start trigger that arrives while the transfer is executing is held
       (once) and the DMA is activated again after it ends. */
    LOG("In-flight DMA%d attempt, holding trigger\n", level);
    m_dma[level].pending_trigger = true;
    return;
  }

  // aligned in dword units
  // TODO: check if other buses can be used
  m_dma[level].index = m_dma[level].dst & 0x07ff'fffc;
  m_dma[level].done = false;
  m_dma[level].mode = DMA_MODE_INDIRECT;
  m_dma[level].indirect_fetch_phase = true;
  m_dma[level].indirect_end_flag = false;

  update_dma_status(level, DMA_STATE_WAIT);

  m_dma_tick_timer->adjust(attotime::from_ticks(2 * 4, m_dma_clock_ref));
}

std::tuple<int, int> saturn_scu_device::check_dma_level_round_robin() {
  int move_level = -1, wait_level = -1;
  // this returns the highest move/wait level currently set
  for (int level = 0; level < 3; level++) {
    if (m_dma_status & (0x10 << (level * 4)))
      move_level = level;
    if (m_dma_status & (0x20 << (level * 4)))
      wait_level = level;
  }

  return std::make_tuple(move_level, wait_level);
}

/* Charge the bus masters for the access the DMA performs on the shared bus:
   one cycle plus the wait-state penalty of the endpoints, capped at what the
   8-bit steal callback can carry. */
void saturn_scu_device::dma_hog_bus(uint8_t level) {
  int const hog = std::min<int>(255, 1 + m_dma[level].transfer_penalty);
  m_main_steal_cb(u8(hog));
  if (m_dma[level].bbus_sound_access)
    m_sound_steal_cb(u8(hog));
}

TIMER_CALLBACK_MEMBER(saturn_scu_device::dma_tick_cb) {
  // guess: yield until DSP do its thing
  if (m_dma_status & DMA_DSP_MOVE) {
    m_dma_tick_timer->adjust(attotime::from_ticks(1, m_dma_clock_ref));
    return;
  }

  auto [level, wait_level] = check_dma_level_round_robin();
  int extra_penalty = 0;

  // printf("%d %d\n", level, wait_level);

  if (level != -1) {
    if (m_dma[level].done) {
      // burningru doesn't want to zero existing size
      //  m_scu.size[dma_ch] = 0;

      m_dma[level].done = false;
      m_dma[level].live_count = 0;
      m_main_dtack_cb(0);
      m_sound_dtack_cb(0);

      const uint16_t irqmask = 1 << (11 - level);

      m_ist |= irqmask;
      test_pending_irqs();

      update_dma_status(level, DMA_STATE_IDLE);

      // ST-210-110194 No.22: a start trigger that arrived while this
      // level was still transferring is held (once) and the activation
      // is executed after the DMA ends
      bool const held_trigger = m_dma[level].pending_trigger;
      m_dma[level].pending_trigger = false;

      if (wait_level != -1) {
        update_dma_status(wait_level, DMA_STATE_MOVE);
        // Restore the resumed channel's bus ownership after releasing the
        // completed transfer. This model uses cycle stealing for indirect DMA.
        const bool direct = !(m_dma[wait_level].mode & DMA_MODE_INDIRECT);
        m_main_dtack_cb(direct);
        m_sound_dtack_cb(direct && m_dma[wait_level].bbus_sound_access);

        LOGMASKED(LOG_DMA_STATE, "Push DMA%d in foreground\n", wait_level);
        if (wait_level == 1)
          m_dma_status &= ~(DMA_LV1_BK);
        else
          m_dma_status &= ~(DMA_LV0_BK);
        m_dma_tick_timer->adjust(attotime::from_ticks(1, m_dma_clock_ref));
      } else if (!held_trigger)
        m_dma_tick_timer->adjust(attotime::never);

      if (held_trigger) {
        if (m_dma[level].indirect_mode)
          trigger_dma_indirect(level);
        else
          trigger_dma_direct(level);
      }
      return;
    }

    if (m_dma[level].mode & DMA_MODE_INDIRECT) {
      if (m_dma[level].indirect_fetch_phase) {
        u32 indirect_src, indirect_dst, indirect_size;
        indirect_size = m_hostspace->read_dword(m_dma[level].index);
        indirect_dst = m_hostspace->read_dword(m_dma[level].index + 4);
        indirect_src = m_hostspace->read_dword(m_dma[level].index + 8);
        m_dma[level].indirect_end_flag = BIT(indirect_src, 31);

        LOGMASKED(LOG_DMA_INDIRECT,
                  "DMA%d indirect entry %08x: R %08x W %08x C %08x %s\n", level,
                  m_dma[level].index, indirect_src, indirect_dst, indirect_size,
                  m_dma[level].indirect_end_flag ? "END" : "");

        auto const [src_flags, src_penalty] =
            get_address_flags(indirect_src, false);
        auto const [dst_flags, dst_penalty] =
            get_address_flags(indirect_dst, true);

        m_dma[level].bbus_sound_access =
            src_flags == B_BUS_SCSP || dst_flags == B_BUS_SCSP;

        m_dma[level].live_src = indirect_src & 0x07ff'ffff;
        m_dma[level].live_dst = indirect_dst & 0x07ff'ffff;
        // Indirect descriptors carry a 20-bit count on every DMA level,
        // unlike the level 1/2 direct count registers. Zero encodes 1 MiB
        // (Ymir DMAReadIndirectTransfer / Mednafen NextIndirect).
        m_dma[level].live_size = indirect_size & 0xf'ffff;
        if (m_dma[level].live_size == 0)
          m_dma[level].live_size = 0x10'0000;
        m_dma[level].live_count = 0;
        m_dma[level].read_buffer_valid = false;
        m_dma[level].transfer_penalty = src_penalty + dst_penalty;

        m_dma[level].mode = DMA_MODE_INDIRECT;

        // if (m_dma[level].bbus_sound_access)
        //{
        //	m_sound_dtack_cb(1);
        // }

        // TODO: other rules still applies
        if (dst_flags == C_BUS) {
          LOGMASKED(LOG_DMA_MODE, "Mode select: C-Bus Write\n");
          m_dma[level].mode |= DMA_MODE_CBUS_WRITE;
        }

        m_dma[level].index += 0x0c;
        m_dma[level].indirect_fetch_phase = false;
        // yield 3 clock cycles out of fetching the new data
        m_dma_tick_timer->adjust(attotime::from_ticks(3, m_dma_clock_ref));
        return;
      }

      (this->*dma_transfer_table[m_dma[level].mode & 3])(m_dma[level]);

      // in indirect mode we steal cycles from the CPUs
      // - stv:finlarch/smleague (where it sure checks the DMA status)
      dma_hog_bus(level);

      // DxW is 27 bits even when the descriptor cursor carries out.
      if (m_dma[level].wup)
        m_dma[level].dst = m_dma[level].index & 0x07ff'ffff;

      if (m_dma[level].live_count >= m_dma[level].live_size) {
        LOGMASKED(LOG_DMA_END, "DMA%d indirect ended at %08x %08x\n", level,
                  m_dma[level].live_src, m_dma[level].live_dst);

        if (m_dma[level].indirect_end_flag)
          m_dma[level].done = true;
        else
          m_dma[level].indirect_fetch_phase = true;
      }
    } else {
      // direct mode

      (this->*dma_transfer_table[m_dma[level].mode & 3])(m_dma[level]);

      // direct mode definitely looks burst, where stopping CPUs is a liability
      // to avoid back-to-back transfers
      // - saturn BIOS
      // - stv:gaxeduel
      // - sonicjamj Sonic 1 (at least)
      extra_penalty = m_dma[level].transfer_penalty;

      /* ...but the DMA still owns the bus for the tick: steal the access
         cost from the CPUs instead of hard-halting them.  Without this
         the masters run at full speed alongside the transfer, which is
         exactly what jungrythm (VDP2 NBG1 filled with garbage),
         powerslave/Exhumed (uncleared VDP1 frame data flickering) and
         virtualon (3D flicker) cannot tolerate - Ymir's scu-dma note
         lists them as requiring the DMA to stall every other bus
         master.  One SCU tick is ~0.8 SH-2 cycles, so a tick of steal
         approximates the stall without the INPUT_LINE_HALT deadlock
         liability the comment above describes. */
      dma_hog_bus(level);

      // ST-097 p.41: hardware address updates have the same 27-bit
      // register width as CPU writes, including the final cursor carry.
      if (m_dma[level].rup)
        m_dma[level].src = m_dma[level].live_src & 0x07ff'ffff;

      if (m_dma[level].wup)
        m_dma[level].dst = m_dma[level].live_dst & 0x07ff'ffff;

      if (m_dma[level].live_count >= m_dma[level].live_size) {
        LOGMASKED(LOG_DMA_END,
                  "DMA%d direct ended at %08x %08x (RUP %d WUP %d)\n", level,
                  m_dma[level].live_src, m_dma[level].live_dst,
                  m_dma[level].rup, m_dma[level].wup);
        m_dma[level].done = true;
      }
    }
  }

  if (wait_level > level) {
    // clear wait, set move
    update_dma_status(wait_level, DMA_STATE_MOVE);

    const bool direct = !(m_dma[wait_level].mode & DMA_MODE_INDIRECT);
    m_main_dtack_cb(direct);
    m_sound_dtack_cb(direct && m_dma[wait_level].bbus_sound_access);

    if (level != -1) {
      // Suspend the old, lower-priority channel, not the channel just
      // promoted to MOVE. Keep its live transfer state for resumption.
      update_dma_status(level, DMA_STATE_WAIT);
      LOGMASKED(LOG_DMA_STATE, "Push DMA%d in background\n", level);

      m_dma_status |= (1 << (16 + level));
    }
  }

  m_dma_tick_timer->adjust(
      attotime::from_ticks(1 + extra_penalty, m_dma_clock_ref));
}

// CD services retain longword FIFO reads; C-bus destination heads/tails
// use the source buffer to split writes. DRDY/backpressure remains TODO.
const saturn_scu_device::dma_transfer_func
    saturn_scu_device::dma_transfer_table[4] = {
        &saturn_scu_device::dma_transfer_direct_default,
        &saturn_scu_device::dma_transfer_direct_cbus_write,
        &saturn_scu_device::dma_transfer_direct_cd,
        &saturn_scu_device::dma_transfer_direct_cd_cbus_write};

uint16_t saturn_scu_device::dma_read_word(dma_channel_t &ch) {
  // SCU reads a longword into its source buffer, then supplies bytes to the
  // destination. DxRA advances the longword base, not each output halfword
  // (ST-097 section 3.2; Ymir doRead / Mednafen DMA_Read).
  if (!ch.read_buffer_valid) {
    ch.read_address = ch.live_src & 0x07ff'fffc;
    ch.read_offset = ch.live_src & 3;
    ch.read_buffer = m_hostspace->read_dword(ch.read_address);
    ch.read_buffer_valid = true;
  }

  uint16_t result = 0;
  for (unsigned byte = 0; byte < 2; ++byte) {
    if (ch.read_offset == 4) {
      ch.read_address = (ch.read_address + ch.src_add) & 0x07ff'ffff;
      ch.read_buffer = m_hostspace->read_dword(ch.read_address);
      ch.read_offset = 0;
    }
    result = (result << 8) | ((ch.read_buffer >> (24 - 8 * ch.read_offset)) & 0xff);
    ++ch.read_offset;
  }
  ch.live_src = (ch.read_address + ch.read_offset) & 0x07ff'ffff;
  return result;
}

uint8_t saturn_scu_device::dma_read_byte(dma_channel_t &ch) {
  // Same longword-buffer discipline as dma_read_word, one byte per call
  // (ST-097 p.16: byte-unit accesses at the region head/tail).
  if (!ch.read_buffer_valid) {
    ch.read_address = ch.live_src & 0x07ff'fffc;
    ch.read_offset = ch.live_src & 3;
    ch.read_buffer = m_hostspace->read_dword(ch.read_address);
    ch.read_buffer_valid = true;
  }

  if (ch.read_offset == 4) {
    ch.read_address = (ch.read_address + ch.src_add) & 0x07ff'ffff;
    ch.read_buffer = m_hostspace->read_dword(ch.read_address);
    ch.read_offset = 0;
  }
  uint8_t const result = (ch.read_buffer >> (24 - 8 * ch.read_offset)) & 0xff;
  ++ch.read_offset;
  ch.live_src = (ch.read_address + ch.read_offset) & 0x07ff'ffff;
  return result;
}

void saturn_scu_device::dma_transfer_direct_default(dma_channel_t &ch) {
  // ST-097 p.16: "DMA is basically long word access through the DMA
  // controller buffer, but if the start address and end address are not
  // in long word boundaries, reads and writes are made in byte units"
  // (Figure 2.1). This engine moves a 16-bit unit per tick; a byte unit
  // is moved when the remaining count is odd (tail beyond the last
  // full unit) or the destination cursor is not halfword-aligned (head
  // /odd destination, which must not clobber the neighbouring byte).
  if ((ch.live_size - ch.live_count) < 2 || (ch.live_dst & 1)) {
    m_hostspace->write_byte(ch.live_dst & 0x07ff'ffff, dma_read_byte(ch));
    ch.live_dst += ch.dst_add ? (ch.dst_add >> 1) : 0;
    ch.live_count += 1;
    return;
  }

  const u32 dst_address = ch.live_dst & 0x07ff'fffe;
  m_hostspace->write_word(dst_address, dma_read_word(ch));
  ch.live_dst += ch.dst_add;
  ch.live_count += 2;
}

void saturn_scu_device::dma_transfer_direct_cbus_write(dma_channel_t &ch) {
  // Same byte-unit head/tail rule as dma_transfer_direct_default; the
  // Work RAM-H destination streams by halfwords (dst_add fixed at 2).
  if ((ch.live_size - ch.live_count) < 2 || (ch.live_dst & 1)) {
    m_hostspace->write_byte(ch.live_dst & 0x07ff'ffff, dma_read_byte(ch));
    ch.live_dst += 1;
    ch.live_count += 1;
    return;
  }

  const u32 dst_address = ch.live_dst & 0x07ff'fffe;
  m_hostspace->write_word(dst_address, dma_read_word(ch));
  ch.live_dst += 2;
  ch.live_count += 2;
}

void saturn_scu_device::dma_transfer_direct_cd(dma_channel_t &ch) {
  const u32 dst_add = ch.dst_add << 1;

  const u32 src_address = ch.live_src & 0x07ff'fffc;
  const u32 dst_address = ch.live_dst & 0x07ff'fffc;

  m_hostspace->write_dword(dst_address, m_hostspace->read_dword(src_address));
  if (dst_add == 8)
    m_hostspace->write_dword(dst_address + 4,
                             m_hostspace->read_dword(src_address));

  ch.live_src += ch.src_add;
  ch.live_dst += dst_add;
  // Count bytes actually read/written, not the distance to the next write.
  // A fixed destination must still finish; gaps from larger strides do not
  // consume source bytes. The existing +4 case performs two longword writes.
  ch.live_count += (dst_add == 8) ? 8 : 4;
}

void saturn_scu_device::dma_transfer_direct_cd_cbus_write(dma_channel_t &ch) {
  // ST-097 p.16: a C-bus head/tail need not lie on a longword boundary.
  // Keep the four-byte bulk service, but do not round its destination down
  // or overwrite bytes beyond the requested end. The shared source buffer
  // retains unused FIFO bytes between partial writes and across state loads.
  if ((ch.live_dst & 3) || (ch.live_size - ch.live_count) < 4) {
    dma_transfer_direct_cbus_write(ch);
    return;
  }

  // Sequence the reads explicitly: a head may leave the source buffer at
  // any byte offset, so this longword can span two source-buffer fills.
  u32 data = u32(dma_read_word(ch)) << 16;
  data |= dma_read_word(ch);
  m_hostspace->write_dword(ch.live_dst & 0x07ff'fffc, data);
  ch.live_dst += 4;
  ch.live_count += 4;
}

inline void saturn_scu_device::dma_start_factor_ack(dma_event_id_t event) {
  for (int i = 0; i < 3; i++) {
    if (m_dma[i].enable_mask == true && m_dma[i].start_factor == event) {
      if (m_dma[i].indirect_mode == true) {
        trigger_dma_indirect(i);
      } else {
        trigger_dma_direct(i);
      }
    }
  }
}

void saturn_scu_device::dma_force_stop_w(uint32_t data, uint32_t mem_mask) {
  // ST-097 section 3.2, DSTP: writing DSTOP=1 cancels CPU-programmed DMA.
  if (!(data & mem_mask & 1))
    return;

  bool release_main = false, release_sound = false;
  for (int level = 0; level < 3; ++level) {
    // Only release halt lines owned by a running direct transfer. An idle
    // stop write must not release a CPU halted for some other reason.
    if ((m_dma_status & (DMA_LV0_MOVE << (4 * level))) &&
        !(m_dma[level].mode & DMA_MODE_INDIRECT)) {
      release_main = true;
      release_sound |= m_dma[level].bbus_sound_access;
    }
    update_dma_status(level, DMA_STATE_IDLE);
    m_dma[level].done = false;
    m_dma[level].pending_trigger = false;
    m_dma[level].indirect_fetch_phase = false;
    m_dma[level].read_buffer_valid = false;
  }
  m_dma_status &= ~(DMA_LV0_BK | DMA_LV1_BK);
  m_dma_tick_timer->adjust(attotime::never);
  if (release_main)
    m_main_dtack_cb(0);
  if (release_sound)
    m_sound_dtack_cb(0);

  // No completion IRQ is manufactured. Keep programmed registers and the
  // enable bits: a later start is a new transfer, not a resumed/held one.
  // DSP DMA state belongs to the DSP and is not reset by this handler.
}

uint32_t saturn_scu_device::dma_status_r() { return m_dma_status; }

//**************************************************************************
// Timers
//**************************************************************************

void saturn_scu_device::t0_compare_w(offs_t offset, uint32_t data,
                                     uint32_t mem_mask) {
  COMBINE_DATA(&m_t0c);
  m_t0c &= 0x3ff;
}

void saturn_scu_device::t1_setdata_w(offs_t offset, uint32_t data,
                                     uint32_t mem_mask) {
  COMBINE_DATA(&m_t1s);
  m_t1s &= 0x1ff;
}

/*
 * ---- ---x ---- ---- T1MD Timer 1 mode (0=each line, 1=only at timer 0 lines)
 * ---- ---- ---- ---x TENB Timers enable
 */
void saturn_scu_device::t1_mode_w(offs_t offset, uint32_t data,
                                  uint32_t mem_mask) {
  COMBINE_DATA(&m_t1md_reg);
  m_t1md = BIT(m_t1md_reg, 8);
  m_tenb = BIT(m_t1md_reg, 0);
  if (!m_tenb) {
    m_timer0_counter = 0;
    m_timer1->adjust(attotime::never);
  }
}

TIMER_CALLBACK_MEMBER(saturn_scu_device::timer1_irq_cb) {
  // ST-097 pp.31-32/56: T1MD qualifies expiry on the timer-0 line;
  // it does not gate the HBlank load. A count can cross into another line.
  if (!m_tenb || (m_t1md && m_timer0_counter != m_t0c))
    return;

  dma_start_factor_ack(DMA_EVENT_TIMER1);

  m_ist |= IST_TIMER_1;
  test_pending_irqs();
}

//**************************************************************************
//  Interrupt
//**************************************************************************

uint32_t saturn_scu_device::irq_mask_r() { return m_ism; }

uint32_t saturn_scu_device::irq_status_r() { return m_ist; }

void saturn_scu_device::irq_mask_w(offs_t offset, uint32_t data,
                                   uint32_t mem_mask) {
  COMBINE_DATA(&m_ism);
  m_ism &= ISM_WRITE_MASK; // bit 14 isn't writable
  test_pending_irqs();
}

void saturn_scu_device::irq_status_w(offs_t offset, uint32_t data,
                                     uint32_t mem_mask) {
  //  if(mem_mask != 0xffffffff)
  //      LOG("%s IST write %08x with %08x\n", this->tag(), data, mem_mask);

  // burningr* uses byte writes when clearing SMPC irqs
  m_ist &= data | (~mem_mask);
  test_pending_irqs();
}

void saturn_scu_device::test_pending_irqs() {
  // ignore if current irq still serviced
  if (m_current_irq_level != 0)
    return;

  // interrupt level per IST bit, indexed by source:
  // 15: vblank-in
  // 14: vblank-out
  // 13: hblank-in
  // 12: timer 0
  // 11: timer 1
  // 10: DSP end
  //  9: SCSP
  //  8: SMPC & PAD
  //  6: DMA end LV2 & LV1
  //  5: DMA end LV0
  //  3: DMA illegal
  //  2: VDP1 draw end
  //  7: A-Bus external interrupts 0-3  (IST bits 16-19, vectors 0x50-0x53)
  //  4: A-Bus external interrupts 4-7  (IST bits 20-23, vectors 0x54-0x57)
  //  1: A-Bus external interrupts 8-15 (IST bits 24-31, vectors 0x58-0x5f)
  const int irq_level[32] = {0xf, 0xe, 0xd, 0xc, 0xb, 0xa, 0x9, 0x8,
                             0x8, 0x6, 0x6, 0x5, 0x3, 0x2, 0,   0,
                             0x7, 0x7, 0x7, 0x7, 0x4, 0x4, 0x4, 0x4,
                             0x1, 0x1, 0x1, 0x1, 0x1, 0x1, 0x1, 0x1};

  // highest priority pending internal source (the bit order matches the
  // descending level order, so the first hit is the highest level)
  int internal = -1;
  for (int i = 0; i < 14; i++) {
    if (!BIT(m_ism, i) && BIT(m_ist, i)) {
      internal = i;
      break;
    }
  }

  // ST-097 section 3.5: IMS15 is an active-high mask, just like the
  // internal source masks. AIACK independently gates repeated delivery.
  int external = -1;
  if (!BIT(m_ism, 15)) {
    for (int i = 0; i < 16; i++) {
      if (BIT(m_ist, 16 + i) && !BIT(m_abus_pending_ack, i)) {
        external = i;
        break;
      }
    }
  }

  // the higher level wins, ties going to the internal source
  int const internal_level = (internal >= 0) ? irq_level[internal] : 0;
  int const external_level = (external >= 0) ? irq_level[16 + external] : 0;

  if (internal_level >= external_level) {
    if (internal < 0)
      return;

    m_current_irq_level = irq_level[internal];
    m_current_vector = 0x40 + internal;
    m_hostcpu->set_input_line(m_current_irq_level, ASSERT_LINE);
    m_ist &= ~(1 << internal);
  } else {
    m_current_irq_level = irq_level[16 + external];
    m_current_vector = 0x50 + external;
    m_hostcpu->set_input_line(m_current_irq_level, ASSERT_LINE);
    m_ist &= ~(1 << (16 + external));
    m_abus_pending_ack |= 1 << external;
  }
}

IRQ_CALLBACK_MEMBER(saturn_scu_device::irq_ack_cb) {
  m_hostcpu->set_input_line(irqline, CLEAR_LINE);
  m_current_irq_level = 0;

  /* The SCU resets the interrupt mask register to its power-on default
     (0000BFFFH per the SCU User's Manual ST-097-R5, figure 3.21) when the
     master SH-2 fetches the interrupt vector, so every source is masked
     again after each acknowledged interrupt and software has to re-arm the
     mask - mednafen's SCU_MSH2VectorFetch() and Ymir's
     AcknowledgeExternalInterrupt() both model this, and the slave SH-2's
     fixed vectors (0x41/0x43, served by the DCC callback) do not touch it.
     Pending status bits in IST survive the reset: Rayman masks the SMPC
     interrupt again inside its VBlank-OUT handler after an issued interrupt
     has been marked pending, and relies on both properties - the pending
     delivery surviving the re-mask (m_current_irq_level gates re-evaluation)
     and the IST bit surviving while masked - to process INTBACK responses. */
  m_ism = 0xbfff;

  return m_current_vector;
}

void saturn_scu_device::vblank_out_w(int state) {
  if (!state)
    return;

  dma_start_factor_ack(DMA_EVENT_VBLANKOUT);

  m_ist |= IST_VBLANK_OUT;
  m_timer0_counter = 0;
  // ST-210 precaution 30: compare zero occurs at VBlank-OUT, not at the
  // following HBlank. Timer 1 is still loaded only by HBlank (precaution 31).
  if (m_tenb && m_t0c == 0) {
    dma_start_factor_ack(DMA_EVENT_TIMER0);
    m_ist |= IST_TIMER_0;
  }
  test_pending_irqs();
}

void saturn_scu_device::vblank_in_w(int state) {
  if (!state)
    return;

  dma_start_factor_ack(DMA_EVENT_VBLANKIN);

  m_ist |= IST_VBLANK_IN;
  test_pending_irqs();
}

void saturn_scu_device::hblank_in_w(int state) {
  if (!state)
    return;

  dma_start_factor_ack(DMA_EVENT_HBLANKIN);
  m_ist |= IST_HBLANK_IN;

  // check if timer enabled first (diehard cares for sound, sets T0C = 0)
  if (m_tenb) {
    // ST-097 section 3.4 / ST-210 precaution 30: the first HBlank after
    // VBlank-OUT compares against 1. TENB gates counting as well as matches.
    m_timer0_counter = (m_timer0_counter + 1) & 0x1ff;
    const bool timer0_hit = m_timer0_counter == m_t0c;
    if (timer0_hit) {
      dma_start_factor_ack(DMA_EVENT_TIMER0);
      m_ist |= IST_TIMER_0;
    }

    // ST-097 pp.31-32 and ST-210 precaution 31: HBlank loads timer 1
    // whenever it is stopped, in either T1MD mode. T1MD selects interrupt
    // occurrence at expiry, not which line may start the countdown.
    // adjust(never) leaves an emu_timer enabled, so check its deadline too.
    // A running count may span several lines and must not be postponed by
    // the next HBlank.
    if (!m_timer1->enabled() || m_timer1->expire().is_never()) {
      // A count of 0 is specified to mean 512 (SCU Final Specifications:
      // Precautions, No. 31), which also makes the 9 bit mask applied to
      // m_t1s self consistent: a write of 512 masks down to 0 and has to
      // come back out as 512.  512 is more counts than fit in one line
      // (1AA H for 320 dots, 1C6 H for 352), so this is the case the
      // manual describes as "Timer 1 interrupt no longer occurs for each
      // line"; arming a zero duration timer instead fired it every line.
      const uint32_t count = m_t1s ? m_t1s : 512;
      m_timer1->adjust(attotime::from_ticks(count, this->clock() / 8));
    }
  }
  test_pending_irqs();
}

void saturn_scu_device::vdp1_end_w(int state) {
  if (!state)
    return;

  dma_start_factor_ack(DMA_EVENT_VDP1);

  m_ist |= IST_VDP1_END;
  test_pending_irqs();
}

void saturn_scu_device::sound_req_w(int state) {
  if (!state)
    return;

  dma_start_factor_ack(DMA_EVENT_SCSP);

  m_ist |= IST_SOUND_REQ;
  test_pending_irqs();
}

void saturn_scu_device::smpc_irq_w(int state) {
  if (!state)
    return;

  m_ist |= IST_SMPC;
  test_pending_irqs();
}

void saturn_scu_device::scudsp_end_w(int state) {
  if (!state)
    return;

  m_ist |= IST_DSP_END;
  test_pending_irqs();
}

//**************************************************************************
//  A-Bus section
//**************************************************************************

// an A-Bus device (currently only the CD block) requests an external
// interrupt, latching the matching IST bit until it is delivered
void saturn_scu_device::abus_external_interrupt(int index, bool state) {
  if ((index < 0) || (index > 15))
    return;

  if (state)
    m_ist |= 1 << (16 + index);
  else
    m_ist &= ~(1 << (16 + index));

  test_pending_irqs();
}

// AIACK: bit 0 of the low byte releases the A-Bus acknowledge latch, so a
// still asserted line can trigger another interrupt
void saturn_scu_device::abus_irqack_w(offs_t offset, uint32_t data,
                                      uint32_t mem_mask) {
  if ((mem_mask & 0x00ff) && BIT(data, 0)) {
    m_abus_pending_ack = 0;
    test_pending_irqs();
  }
}

//**************************************************************************
//  Miscellanea
//**************************************************************************

//-------------------------------------------------
//  A-Bus Set / Refresh registers (ASR0, ASR1, AREF)
//
//  Write-only configuration of the A-Bus chip-select timing; the wait
//  counts they hold are picked up by get_address_flags().
//-------------------------------------------------

void saturn_scu_device::abus_set_w(offs_t offset, uint32_t data,
                                   uint32_t mem_mask) {
  COMBINE_DATA(&m_abus_asr[offset & 1]);
  // ST-210-110194 No.09: the A-Bus preread function was deleted, so the
  // preread significant bits (31 and 15) of ASR0/ASR1 must be set to 0 and
  // are not stored
  m_abus_asr[offset & 1] &= ~0x8000'8000;
}

void saturn_scu_device::abus_refresh_w(uint32_t data, uint32_t mem_mask) {
  COMBINE_DATA(&m_abus_aref);
  // Only ARFEN (bit 4) and ARWT (bits 3:0) are implemented.
  m_abus_aref &= 0x1f;
}

uint32_t saturn_scu_device::version_r() {
  return 4; // correct for stock Saturn at least
}

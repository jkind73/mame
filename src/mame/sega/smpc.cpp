// license:BSD-3-Clause
// copyright-holders:Angelo Salese, R. Belmont
/************************************************************************************

Sega Saturn SMPC - System Manager and Peripheral Control MCU simulation

The SMPC is actually a 4-bit Hitachi HD404920FS MCU (HD404358, HMCS400
compatible), labeled with a Sega custom 315-5744 (binary decap available)

TODO:
- timings;
- fix intback issue with inputs (according to the docs, it should fall in
between VBLANK-IN and OUT, for obvious reasons);
- clean-ups;
- Does ST-V even has a battery backed NVRAM?

The RTC is a custom type internal to the SMPC (ST-169 chapter 2.5): 7 bytes of
BCD (year 100s/1s, day-of-week|month, day, hour, minute, second), counted up
once per second with leap-year correction until 2099, initialized to
12/31/93 Friday 23:59:59 by SMPC cold reset, set by SETTIME and reported in
INTBACK OREG1-7.  Since it is CR2032-backed it is wired into the core's
battery-backed RTC machinery, which seeds it from the host clock at startup.

Notes:
SMPC NVRAM contents:
[0] unknown (always 0)
[1] unknown (always 0)
[2] ---- -x-- Button Labels (0=enable)
    ---- --x- Audio Out (1=Mono 0=Stereo)
    ---- ---x BIOS audio SFXs enable (0=enable)
[3] language select (0=English, 5=Japanese)

*************************************************************************************/

#include "emu.h"
#include "smpc.h"


#include "coreutil.h"
#include "screen.h"


#define LOG_COMMAND (1U << 1)
#define LOG_PAD_CMD (1U << 2)

#define VERBOSE (LOG_COMMAND)
// #define LOG_OUTPUT_FUNC osd_printf_info

#include "logmacro.h"

//**************************************************************************
//  GLOBAL VARIABLES
//**************************************************************************

// device type definition
DEFINE_DEVICE_TYPE(SMPC_HLE, smpc_hle_device, "smpc_hle",
                   "Sega Saturn SMPC HLE (Hitachi HD404920FS 315-5744)")

void smpc_hle_device::io_map(address_map &map) {
  map(0x00, 0x7f).lr8(NAME([this](offs_t offset) {
    // TODO: undefined odd addresses really latches whatever was last written
    logerror("%s: Read to [%02x] open bus address\n",
             machine().describe_context(), offset & 0x7f);
    return offset & 1 ? 0x00 : 0xff;
  }));
  map(0x00, 0x0d).w(FUNC(smpc_hle_device::ireg_w));
  map(0x1f, 0x1f).w(FUNC(smpc_hle_device::command_register_w));
  map(0x20, 0x5f).r(FUNC(smpc_hle_device::oreg_r));
  map(0x61, 0x61).r(FUNC(smpc_hle_device::status_register_r));
  map(0x63, 0x63)
      .rw(FUNC(smpc_hle_device::status_flag_r),
          FUNC(smpc_hle_device::status_flag_w));
  map(0x75, 0x75)
      .rw(FUNC(smpc_hle_device::pdr1_r), FUNC(smpc_hle_device::pdr1_w));
  map(0x77, 0x77)
      .rw(FUNC(smpc_hle_device::pdr2_r), FUNC(smpc_hle_device::pdr2_w));
  map(0x79, 0x79).w(FUNC(smpc_hle_device::ddr1_w));
  map(0x7b, 0x7b).w(FUNC(smpc_hle_device::ddr2_w));
  map(0x7d, 0x7d).w(FUNC(smpc_hle_device::iosel_w));
  map(0x7f, 0x7f).w(FUNC(smpc_hle_device::exle_w));
}

//**************************************************************************
//  LIVE DEVICE
//**************************************************************************

//-------------------------------------------------
//  smpc_hle_device - constructor
//-------------------------------------------------

smpc_hle_device::smpc_hle_device(const machine_config &mconfig, const char *tag,
                                 device_t *owner, uint32_t clock)
    : device_t(mconfig, SMPC_HLE, tag, owner, clock),
      device_rtc_interface(mconfig, *this), m_mini_nvram(*this, "smem"),
      m_mshres(*this), m_mshnmi(*this), m_sshres(*this), m_sndres(*this),
      m_sysres(*this), m_syshalt(*this), m_dotsel(*this),
      m_pdr1_read(*this, 0xff), m_pdr2_read(*this, 0xff), m_pdr1_write(*this),
      m_pdr2_write(*this), m_irq_line(*this), m_reset_button_read(*this, 0),
      m_ctrl1(*this, finder_base::DUMMY_TAG),
      m_ctrl2(*this, finder_base::DUMMY_TAG),
      m_screen(*this, finder_base::DUMMY_TAG) {
  m_has_ctrl_ports = false;
}

//-------------------------------------------------
//  device_add_mconfig - device-specific machine
//  configuration addiitons
//-------------------------------------------------

void smpc_hle_device::device_add_mconfig(machine_config &config) {
  NVRAM(config, "smem", nvram_device::DEFAULT_ALL_0);
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void smpc_hle_device::device_start() {
  //  check if SMEM has valid data via byte 4 in the array, if not then simulate
  //  a battery backup fail
  //  (-> call the RTC / Language select menu for Saturn)
  m_mini_nvram->set_base(&m_smem, 5);

  save_item(NAME(m_sf));
  save_item(NAME(m_sr));
  save_item(NAME(m_ddr1));
  save_item(NAME(m_ddr2));
  save_item(NAME(m_pdr1_readback));
  save_item(NAME(m_pdr2_readback));
  save_item(NAME(m_iosel1));
  save_item(NAME(m_iosel2));
  save_item(NAME(m_exle1));
  save_item(NAME(m_exle2));
  save_item(NAME(m_ireg));
  save_item(NAME(m_oreg));
  save_item(NAME(m_comreg));
  save_item(NAME(m_command_in_progress));
  save_item(NAME(m_intback_buf));
  save_item(NAME(m_peripheral_data));
  save_item(NAME(m_peripheral_size));
  save_item(NAME(m_peripheral_pos));
  save_item(NAME(m_intback_stage));
  save_item(NAME(m_pmode));
  save_item(NAME(m_rtc_data));
  save_item(NAME(m_smem));
  save_item(NAME(m_ckchg_tick));
  save_item(NAME(m_prev_sshoff));
  save_item(NAME(m_prev_sndoff));
  save_item(NAME(m_prev_cdoff));
  // latches driven by SMPC commands (CDON/CDOFF, SETSZONE, NMIRESET),
  // not by device_reset, so they must survive a state load
  save_item(NAME(m_cd_sf));
  save_item(NAME(m_cur_dotsel));
  save_item(NAME(m_NMI_reset));
  save_item(NAME(m_resb));
  save_item(NAME(m_reset_button_count));

  m_cmd_timer = timer_alloc(FUNC(smpc_hle_device::handle_command), this);
  m_rtc_timer = timer_alloc(FUNC(smpc_hle_device::handle_rtc_increment), this);
  m_intback_timer =
      timer_alloc(FUNC(smpc_hle_device::intback_continue_request), this);
  m_sndres_timer = timer_alloc(FUNC(smpc_hle_device::sound_reset), this);

  // ST-169: the RTC is initialized to "12/31/93 Friday 23:59:59" and starts
  // counting during SMPC cold reset (reset switch pressed, battery missing or
  // dead at power-on, or battery installed while powered off).  If the RTC is
  // battery-backed the core overwrites this with the host time right after
  // NVRAM load; mednafen's SMPC_SetRTC uses the same power-on values.
  static constexpr uint8_t cold_reset_rtc[7] = {0x19, 0x93, 0x5c, 0x31,
                                                0x23, 0x59, 0x59};
  memcpy(m_rtc_data, cold_reset_rtc, sizeof(m_rtc_data));
  // The battery-backed clock runs independently of machine resets. Its
  // first count follows a full second, not a zero-delay timer callback.
  m_rtc_timer->adjust(attotime::from_seconds(1), 0, attotime::from_seconds(1));
}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void smpc_hle_device::device_reset() {
  m_sr = 0x40; // this bit is always on according to docs (?)
  m_sf = false;
  m_cd_sf = false;
  m_ddr1 = 0;
  m_ddr2 = 0;
  // ST-169 table 3.1: SMPC control mode, external latches disabled.
  m_iosel1 = m_iosel2 = false;
  m_exle1 = m_exle2 = false;
  m_pdr1_readback = 0;
  m_pdr2_readback = 0;

  memset(m_ireg, 0, 7);
  memset(m_oreg, 0, 32);

  m_cmd_timer->reset();
  m_intback_timer->reset();
  m_sndres_timer->reset();
  m_comreg = 0xff;
  m_command_in_progress = false;
  m_NMI_reset = false;
  m_resb = false;
  m_reset_button_count = 0;
  m_cur_dotsel = false;
  m_ckchg_tick = 0;
  m_prev_sndoff = m_prev_sshoff = 0xff;
  m_prev_cdoff = 0;

  // ireg_w() tests m_intback_stage on any IREG1 write, which the guest can do
  // long before the first INTBACK sets it, and m_pmode is echoed back into SR
  // once an INTBACK completes
  m_intback_stage = 0;
  m_peripheral_size = m_peripheral_pos = 0;
  m_pmode = 0;

  // Keep the battery-backed RTC value and its in-progress second intact.
}

//-------------------------------------------------
//  rtc_clock_updated - update clock with real time
//-------------------------------------------------

void smpc_hle_device::rtc_clock_updated(int year, int month, int day,
                                        int day_of_week, int hour, int minute,
                                        int second) {
  m_rtc_data[0] = DectoBCD(year / 100);
  m_rtc_data[1] = DectoBCD(year % 100);
  m_rtc_data[2] = ((day_of_week - 1) << 4) | month;
  m_rtc_data[3] = DectoBCD(day);
  m_rtc_data[4] = DectoBCD(hour);
  m_rtc_data[5] = DectoBCD(minute);
  m_rtc_data[6] = DectoBCD(second);
}

//**************************************************************************
//  READ/WRITE HANDLERS
//**************************************************************************

void smpc_hle_device::ireg_w(offs_t offset, uint8_t data) {
  if (!(offset & 1)) // avoid writing to even bytes
    return;

  const uint8_t previous = m_ireg[offset >> 1];
  m_ireg[offset >> 1] = data;

  if (offset == 1) // check if we are under intback
  {
    if (m_intback_stage) {
      if (data & 0x40) {
        LOGMASKED(LOG_PAD_CMD, "SMPC: BREAK request\n");
        m_intback_timer->reset();
        sr_ack();
        sf_ack(false);
        m_intback_stage = 0;
        m_peripheral_size = m_peripheral_pos = 0;
      } else if ((previous ^ data) & 0x80) {
        LOGMASKED(LOG_PAD_CMD, "SMPC: CONTINUE request\n");

        m_intback_timer->adjust(
            attotime::from_usec(700)); // TODO: is timing correct?

        // TODO: following looks wrong here
        m_oreg[31] = 0x10;
        sf_set();
      }
    }
  }
}

uint8_t smpc_hle_device::oreg_r(offs_t offset) {
  if (!(offset & 1))
    return 0xff;

  return m_oreg[offset >> 1];
}

uint8_t smpc_hle_device::status_register_r() {
  // ST-169 pp.34/66: RESB is valid independently of INTBACK and NMI enable.
  // Command/status writes must not erase the VBlank-sampled button state.
  return (m_sr & ~0x10) | (m_resb ? 0x10 : 0);
}

uint8_t smpc_hle_device::status_flag_r() {
  // bit 3: CD enable related?
  return (m_sf << 0) | (m_cd_sf << 3);
}

void smpc_hle_device::status_flag_w(uint8_t data) {
  // ST-169 p.6: the SH-2 can only set SF; the SMPC clears it on completion.
  // The write strobe sets the latch regardless of the data byte.
  m_sf = true;
  m_cd_sf = false;
}

uint8_t smpc_hle_device::pdr1_r() {
  // ST-169 pp.7-8: only current output pins read back the stored data.
  // Preserve the existing bit7 behavior outside the seven physical pins.
  uint8_t res = (m_pdr1_read() & ~m_ddr1) |
                (m_pdr1_readback & (m_ddr1 | 0x80));

  return res;
}

uint8_t smpc_hle_device::pdr2_r() {
  // ST-169 pp.7-8: only current output pins read back the stored data.
  // Preserve the existing bit7 behavior outside the seven physical pins.
  uint8_t res = (m_pdr2_read() & ~m_ddr2) |
                (m_pdr2_readback & (m_ddr2 | 0x80));

  return res;
}

void smpc_hle_device::pdr1_w(uint8_t data) {
  //  pins defined as output returns in input
  m_pdr1_readback = (data & m_ddr1);
  m_pdr1_readback &= 0x7f;
  m_pdr1_write(m_pdr1_readback);
  //  bit 7 can be read back apparently
  m_pdr1_readback |= data & 0x80;
}

void smpc_hle_device::pdr2_w(uint8_t data) {
  //  pins defined as output returns in input
  m_pdr2_readback = (data & m_ddr2);
  m_pdr2_readback &= 0x7f;
  m_pdr2_write(m_pdr2_readback);
  //  bit 7 can be read back apparently
  m_pdr2_readback |= data & 0x80;
}

void smpc_hle_device::ddr1_w(uint8_t data) { m_ddr1 = data & 0x7f; }

void smpc_hle_device::ddr2_w(uint8_t data) { m_ddr2 = data & 0x7f; }

void smpc_hle_device::iosel_w(uint8_t data) {
  m_iosel1 = BIT(data, 0);
  m_iosel2 = BIT(data, 1);
}

void smpc_hle_device::exle_w(uint8_t data) {
  m_exle1 = BIT(data, 0);
  m_exle2 = BIT(data, 1);
}

inline void smpc_hle_device::sr_ack() { m_sr &= 0x0f; }

inline void smpc_hle_device::sr_set(uint8_t data) { m_sr = data; }

inline void smpc_hle_device::sf_ack(bool cd_enable) {
  m_sf = false;
  m_cd_sf = cd_enable;
}

inline void smpc_hle_device::sf_set() { m_sf = true; }

// Saturn Direct Mode polling check for delegate
bool smpc_hle_device::get_iosel(bool which) {
  return which == true ? m_iosel2 : m_iosel1;
}

uint8_t smpc_hle_device::get_ddr(bool which) {
  return which == true ? m_ddr2 : m_ddr1;
}

bool smpc_hle_device::get_exle(bool which) {
  return which == true ? m_exle2 : m_exle1;
}

inline void smpc_hle_device::master_sh2_nmi() {
  m_mshnmi(1);
  m_mshnmi(0);
}

inline void smpc_hle_device::irq_request() {
  m_irq_line(1);
  m_irq_line(0);
}

//**************************************************************************
//  Command simulation
//**************************************************************************

void smpc_hle_device::command_register_w(uint8_t data) {
  //  don't send a command if previous one is still in progress
  //  ST-V tries to send a sysres command if OREG31 doesn't return the ack
  //  command
  if (m_command_in_progress == true) {
    logerror("SMPC: double issuing %02x!\n", data);
    return;
  }

  m_comreg = data & 0x1f;

  if (data & 0xe0)
    logerror("SMPC: COMREG = %02x!?\n", data);

  m_command_in_progress = true;
  switch (m_comreg) {
  // gnine97/gnine98 and spinoffs wants two consecutive SSHON to resolve as a
  // NOP 3dbball* is more finicky: uses two SSHOFF commands after (skipping) FMV
  case 0x02:
  case 0x03:
    m_cmd_timer->adjust(attotime::from_usec(
        m_prev_sshoff == (m_comreg & 1) ? 1 : m_cmd_table_timing[m_comreg]));
    break;
  case 0x06:
  case 0x07:
    m_cmd_timer->adjust(attotime::from_usec(
        m_prev_sndoff == (m_comreg & 1) ? 1 : m_cmd_table_timing[m_comreg]));
    break;
  case 0x0e:
  case 0x0f:
    // A PLL change makes the SMPC to stop everything until it can resync
    // everything again. This takes the equivalent of 3~4 frame cycles. (cfr.
    // diagram on page 3 of SMPC manual)
    // - shanhigw/sokyugrt/prikura (would otherwise set 2 credits at startup)
    m_syshalt(1);

    m_ckchg_tick = 5;

    m_cmd_timer->adjust(
        m_screen->time_until_pos(m_screen->visible_area().max_y, 0));

    break;
  case 0x10: {
    // Peripheral collection must finish by the next VBlank-IN (ST-169 p.50).

    // copy ireg to our intback buffer
    for (int i = 0; i < 3; i++)
      m_intback_buf[i] = m_ireg[i];

    // calculate the timing for intback command
    int timing;

    timing = 8;

    if (m_ireg[0] != 0) // non-peripheral data
      timing += 8;

    // TODO: OPE scheduling and per-device wire timing (ST-169 pp.55-57).
    if (m_ireg[1] & 8) // peripheral data
      timing += 700;

    // TODO: check against ireg2, must be 0xf0

    m_cmd_timer->adjust(attotime::from_usec(timing));
    break;
  }
  default:
    m_cmd_timer->adjust(attotime::from_usec(m_cmd_table_timing[m_comreg]));
    break;
  }
}

TIMER_CALLBACK_MEMBER(smpc_hle_device::handle_command) {
  switch (m_comreg) {
  case 0x00: // MSHON
    LOGMASKED(LOG_COMMAND, "SMPC: %02x MSHON\n", m_comreg);
    // enable Master SH2
    m_mshres(m_comreg & 1);
    break;

  case 0x02: // SSHON
  case 0x03: // SSHOFF
    LOGMASKED(LOG_COMMAND, "SMPC: %02x SSH%s\n", m_comreg,
              m_comreg & 1 ? "OFF" : "ON");
    // enable or disable Slave SH2
    m_prev_sshoff = m_comreg & 1;
    m_sshres(m_comreg & 1);
    break;

  case 0x06: // SNDON
  case 0x07: // SNDOFF
    LOGMASKED(LOG_COMMAND, "SMPC: %02x SND%s\n", m_comreg,
              m_comreg & 1 ? "OFF" : "ON");
    // enable or disable 68k
    m_prev_sndoff = m_comreg & 1;
    m_sndres(m_comreg & 1);
    break;

  case 0x08: // CDON
  case 0x09: // CDOFF
    // ...
    LOGMASKED(LOG_COMMAND, "SMPC: %02x CD%s\n", m_comreg,
              m_comreg & 1 ? "OFF" : "ON");
    m_prev_cdoff = m_comreg & 1;
    m_command_in_progress = false;
    m_oreg[31] = m_comreg;
    // TODO: diagnostic also wants this to have bit 3 high
    sf_ack(true); // set hand-shake flag
    return;

  case 0x0a: // NETLINKON / COPON
    // TODO: understand where NetLink actually lies and implement delegation
    // accordingly (is it really an SH1 device like suggested by the space
    // access or it overlays on CS2 bus?)
    popmessage("%s: NetLink enabled", this->tag());
    [[fallthrough]];
  case 0x0b: // NETLINKOFF / COPOFF
    LOGMASKED(LOG_COMMAND, "SMPC: %02x NETLINK%s\n", m_comreg,
              m_comreg & 1 ? "OFF" : "ON");
    break;

  case 0x0d: // SYSRES
    LOGMASKED(LOG_COMMAND, "SMPC: %02x SYSRES\n", m_comreg);
    // send a 1 -> 0 to device reset lines
    m_sysres(1);
    m_sysres(0);

    // send a 1 -> 0 transition to reset line (was PULSE_LINE)
    m_mshres(1);
    m_mshres(0);
    break;

  case 0x0e: // CKCHG352
  case 0x0f: // CKCHG320
    LOGMASKED(LOG_COMMAND, "SMPC: %02x CKCHG%s\n", m_comreg,
              m_comreg & 1 ? "320" : "352");
    m_ckchg_tick--;
    if (m_ckchg_tick == 4) {
      // VDP1, VDP2 and SCU are also reset by this (done in client)
      m_dotsel(m_comreg & 1);

      // assert Slave SH2 and sound CPU lines
      m_prev_sshoff = 1;
      m_sshres(1);

      m_prev_sndoff = 1;
      m_sndres(1);

      // setup the new dot select
      m_cur_dotsel = (m_comreg & 1) ^ 1;
    }

    if (m_ckchg_tick >= 1)
      m_cmd_timer->adjust(
          m_screen->time_until_pos(m_screen->visible_area().max_y, 0));
    else {
      // send an unconditional NMI to Master SH2
      // - bigichig, capgen1, capgen4 and capgen5 triggers a SLEEP opcode from
      // BIOS call
      //   and expects this to wake them up.
      master_sh2_nmi();

      // clear PLL system halt
      m_syshalt(0);
    }

    break;

  case 0x10: // INTBACK
    // ignore logging, very verbose
    resolve_intback();
    return;

  case 0x16: // SETTIME
  {
    LOGMASKED(LOG_COMMAND, "SMPC: %02x SETTIME\n", m_comreg);

    for (int i = 0; i < 7; i++)
      m_rtc_data[i] = m_ireg[i];

    // ST-169: INTBACK OREG0 bit 7 (STE) reads 1 once SETTIME has been
    // issued after an SMPC cold reset, so the BIOS stops presenting the
    // clock-setting screen. Restart the per-second phase too, matching
    // Mednafen's sub-second accumulator reset, without an immediate tick.
    m_smem[4] |= 0x80;
    m_rtc_timer->adjust(attotime::from_seconds(1), 0, attotime::from_seconds(1));
    break;
  }

  case 0x17: // SETSMEM
  {
    LOGMASKED(LOG_COMMAND, "SMPC: %02x SETSMEM\n", m_comreg);

    for (int i = 0; i < 4; i++)
      m_smem[i] = m_ireg[i];

    // ST-169 p.32: STE records SETTIME since cold reset. SETSMEM only
    // replaces the four SMEM bytes; it must not mark the RTC as set.
    break;
  }

  case 0x18: // NMIREQ
    LOGMASKED(LOG_COMMAND, "SMPC: %02x NMIREQ\n", m_comreg);
    // NMI is unconditionally requested
    master_sh2_nmi();
    break;

  case 0x19: // RESENAB
  case 0x1a: // RESDISA
    LOGMASKED(LOG_COMMAND, "SMPC: %02x RES%s\n", m_comreg,
              m_comreg & 1 ? "DISA" : "ENAB");
    m_NMI_reset = (m_comreg & 1);
    break;

  // TODO: undocumented commands SEC_GETSEED (0x1e) and SEC_VERIFY (0x1f)
  default:
    popmessage("%s: unemulated %02x command", this->tag(), m_comreg);
    return;
  }

  //	LOGMASKED(LOG_COMMAND, "acknowledge for command %02x\n", m_comreg);
  m_command_in_progress = false;
  m_oreg[31] = m_comreg;
  sf_ack(false);
}

TIMER_CALLBACK_MEMBER(smpc_hle_device::sound_reset) {
  // from m68k reset opcode trigger
  m_sndres(1);
  m_sndres(0);
}

// ST-169-R1 p.50: peripheral INTBACK terminates at VBlank-IN if it
// has not finished. Pending command completion and CONTINUE are distinct
// timers. Do not cancel an unrelated system command sharing the SF register.
void smpc_hle_device::vblank_in() {
  // Leave the legacy no-controller/ST-V handshake unchanged.
  if (!m_has_ctrl_ports)
    return;

  // Sample the hardwired switch every VBlank-IN, including idle/RESDISA.
  // Read the physical port rather than relying on a change callback, so a
  // button held across machine reset is sampled again on the next edge.
  m_resb = bool(m_reset_button_read());

  // ST-169 pp.19/33-34: RESB follows the first VBlank sample, but the
  // reset-button NMI is qualified over three VINTs to reject chatter.
  // Count even while RESDISA is active; 3 is qualified and 4 means an NMI
  // has already been sent for this hold. A sampled release rearms it.
  if (!m_resb)
    m_reset_button_count = 0;
  else if (m_reset_button_count < 3)
    ++m_reset_button_count;

  if (m_reset_button_count == 3 && m_NMI_reset) {
    m_reset_button_count = 4;
    master_sh2_nmi();
  }

  bool const pending = m_command_in_progress && m_comreg == 0x10 &&
                       (m_intback_buf[1] & 8);
  if (!pending && !m_intback_stage)
    return;

  if (pending) {
    m_cmd_timer->reset();
    m_command_in_progress = false;
  }
  m_intback_timer->reset();
  m_intback_stage = 0;
  m_peripheral_size = m_peripheral_pos = 0;
  // No new report or interrupt. Clear PDL/NPE, retain the last report's
  // type, reset-button indication and port modes (Ymir cross-check).
  m_sr &= ~0x60;
  if (!m_command_in_progress)
    sf_ack(false);
}

void smpc_hle_device::resolve_intback() {
  int i;

  m_command_in_progress = false;
  m_peripheral_size = m_peripheral_pos = 0;
  // Port modes are in IREG1, for both forms of peripheral INTBACK.
  m_pmode = m_intback_buf[1] >> 4;

  if (m_intback_buf[0] != 0) {
    m_oreg[0] = ((m_smem[4] & 0x80) | ((!m_NMI_reset & 1) << 6));

    for (i = 0; i < 7; i++)
      m_oreg[1 + i] = m_rtc_data[i];

    m_oreg[8] = 0; // CTG0 / CTG1?

    m_oreg[9] = m_region_code; // TODO: system region on Saturn

    /*
     * 0-1- -1-- unknown
     * -x-- ---- VDP2 dot select
     * ---x ---- SSHON
     * ---- x--- MSHNMI
     * ---- --x- SYSRES
     * ---- ---x SOUNDRES
     */
    m_oreg[10] = 0 << 7 | m_cur_dotsel << 6 | 1 << 5 |
                 ((m_prev_sshoff & 1) ^ 1) << 4 | 0 << 3 | 1 << 2 | 0 << 1 |
                 ((m_prev_sndoff & 1) ^ 1) << 0;

    /*
     * -x-- ---- CDON
     * ---- --1- <unknown>
     */
    m_oreg[11] = ((m_prev_cdoff & 1) ^ 1) << 6 | (1 << 1);

    for (i = 0; i < 4; i++)
      m_oreg[12 + i] = m_smem[i];

    for (i = 0; i < 15; i++)
      m_oreg[16 + i] = 0xff; // undefined

    m_intback_stage = (m_intback_buf[1] & 8) >> 3; // first peripheral
    sr_set(0x40 | (m_intback_stage << 5));

    irq_request();

    // put issued command in OREG31
    m_oreg[31] = 0x10; // TODO: doc says 0?
    /* clear hand-shake flag */
    sf_ack(false);
  } else if (m_intback_buf[1] & 8) {
    m_intback_stage = (m_intback_buf[1] & 8) >> 3; // first peripheral
    sr_set(0x40);
    m_oreg[31] = 0x10;
    intback_continue_request(0);
  } else {
    /* Shienryu calls this, it would be plainly illegal on Saturn, I'll just
     * return the command and clear the hs flag for now. */
    m_oreg[31] = 0x10;
    sf_ack(false);
  }
}

TIMER_CALLBACK_MEMBER(smpc_hle_device::intback_continue_request) {
  // BREAK/reset may have canceled collection before a queued callback runs.
  if (!m_intback_stage)
    return;

  if (m_has_ctrl_ports) {
    bool const first = m_intback_stage == 1;
    if (first)
      read_saturn_ports();

    // OREG31 may contain peripheral data (ST-169 p.41). Set the command
    // marker before the copy, never over the final byte of a full page.
    std::fill(std::begin(m_oreg), std::end(m_oreg), 0xff);
    m_oreg[31] = 0x10;
    unsigned const count = std::min<unsigned>(sizeof(m_oreg), m_peripheral_size - m_peripheral_pos);
    std::copy_n(m_peripheral_data + m_peripheral_pos, count, m_oreg);
    m_peripheral_pos += count;
    bool const more = m_peripheral_pos < m_peripheral_size;
    // PDL marks the first page; NPE describes remaining data, not port #.
    sr_set(0x80 | (first ? 0x40 : 0) | (more ? 0x20 : 0) | m_pmode);
    m_intback_stage = more ? 2 : 0;
  } else {
    // Keep the existing no-controller/ST-V handshake path unchanged.
    if (m_intback_stage == 2) {
      sr_set(0x80 | m_pmode);
      m_intback_stage = 0;
    } else {
      sr_set(0xc0 | m_pmode);
      m_intback_stage++;
    }
    m_oreg[31] = 0x10;
  }
  irq_request();
  sf_ack(false);
}

int smpc_hle_device::DectoBCD(int num) {
  int i, cnt = 0, tmp, res = 0;

  while (num > 0) {
    tmp = num;
    while (tmp >= 10)
      tmp %= 10;
    for (i = 0; i < cnt; i++)
      tmp *= 16;
    res += tmp;
    cnt++;
    num /= 10;
  }

  return res;
}

//**************************************************************************
//  RTC handling
//**************************************************************************

TIMER_CALLBACK_MEMBER(smpc_hle_device::handle_rtc_increment) {
  const uint8_t dpm[12] = {0x31, 0x28, 0x31, 0x30, 0x31, 0x30,
                           0x31, 0x31, 0x30, 0x31, 0x30, 0x31};
  int year_num, year_count;

  /*
      m_smpc.rtc_data[0] = DectoBCD(systime.local_time.year /100);
      m_smpc.rtc_data[1] = DectoBCD(systime.local_time.year %100);
      m_smpc.rtc_data[2] = (systime.local_time.weekday << 4) |
     (systime.local_time.month+1); m_smpc.rtc_data[3] =
     DectoBCD(systime.local_time.mday); m_smpc.rtc_data[4] =
     DectoBCD(systime.local_time.hour); m_smpc.rtc_data[5] =
     DectoBCD(systime.local_time.minute); m_smpc.rtc_data[6] =
     DectoBCD(systime.local_time.second);
  */

  m_rtc_data[6]++;

  /* seconds from 9 -> 10*/
  if ((m_rtc_data[6] & 0x0f) >= 0x0a) {
    m_rtc_data[6] += 0x10;
    m_rtc_data[6] &= 0xf0;
  }
  /* seconds from 59 -> 0 */
  if ((m_rtc_data[6] & 0xf0) >= 0x60) {
    m_rtc_data[5]++;
    m_rtc_data[6] = 0;
  }
  /* minutes from 9 -> 10 */
  if ((m_rtc_data[5] & 0x0f) >= 0x0a) {
    m_rtc_data[5] += 0x10;
    m_rtc_data[5] &= 0xf0;
  }
  /* minutes from 59 -> 0 */
  if ((m_rtc_data[5] & 0xf0) >= 0x60) {
    m_rtc_data[4]++;
    m_rtc_data[5] = 0;
  }
  /* hours from 9 -> 10 */
  if ((m_rtc_data[4] & 0x0f) >= 0x0a) {
    m_rtc_data[4] += 0x10;
    m_rtc_data[4] &= 0xf0;
  }
  /* hours from 23 -> 0 */
  if ((m_rtc_data[4] & 0xff) >= 0x24) {
    m_rtc_data[3]++;
    m_rtc_data[2] += 0x10;
    m_rtc_data[4] = 0;
  }
  /* week day name sunday -> monday */
  if ((m_rtc_data[2] & 0xf0) >= 0x70) {
    m_rtc_data[2] &= 0x0f;
  }
  /* day number 9 -> 10 */
  if ((m_rtc_data[3] & 0x0f) >= 0x0a) {
    m_rtc_data[3] += 0x10;
    m_rtc_data[3] &= 0xf0;
  }

  // year BCD to dec conversion (for the leap year stuff)
  {
    year_num = (m_rtc_data[1] & 0xf);

    for (year_count = 0; year_count < (m_rtc_data[1] & 0xf0);
         year_count += 0x10)
      year_num += 0xa;

    year_num += (m_rtc_data[0] & 0xf) * 0x64;

    for (year_count = 0; year_count < (m_rtc_data[0] & 0xf0);
         year_count += 0x10)
      year_num += 0x3e8;
  }

  /* month +1 check */
  /* the RTC have a range of 1980 - 2100, so we don't actually need to support
   * the leap year special conditions */
  if (((year_num % 4) == 0) && (m_rtc_data[2] & 0xf) == 2) {
    if ((m_rtc_data[3] & 0xff) >= dpm[(m_rtc_data[2] & 0xf) - 1] + 1 + 1) {
      m_rtc_data[2]++;
      m_rtc_data[3] = 0x01;
    }
  } else if ((m_rtc_data[3] & 0xff) >= dpm[(m_rtc_data[2] & 0xf) - 1] + 1) {
    m_rtc_data[2]++;
    m_rtc_data[3] = 0x01;
  }
  /* year +1 check */
  if ((m_rtc_data[2] & 0x0f) > 12) {
    m_rtc_data[1]++;
    m_rtc_data[2] = (m_rtc_data[2] & 0xf0) | 0x01;
  }
  /* year from 9 -> 10 */
  if ((m_rtc_data[1] & 0x0f) >= 0x0a) {
    m_rtc_data[1] += 0x10;
    m_rtc_data[1] &= 0xf0;
  }
  /* year from 99 -> 100 */
  if ((m_rtc_data[1] & 0xf0) >= 0xa0) {
    // Both year bytes are BCD (ST-169 pp.32/46): 1999 must carry
    // into 0x20, not the binary increment 0x19 -> 0x1a.
    m_rtc_data[0] = DectoBCD(year_num / 100 + 1);
    m_rtc_data[1] = 0;
  }
}

/********************************************
 *
 * Saturn handlers
 *
 *******************************************/

/*
    Port status contains the multitap ID and physical connector count:
      04 = SegaTap, 16 = six-player multitap, F0 = empty, F1 = direct device.
    Each connector contributes an ID followed by its payload. For types 0-E,
    a nonzero low nibble is the payload length; zero selects an extra length
    byte. Type F represents an unknown or empty tap and has no payload.
    Keep physical slot indices even when earlier slots have no data.
*/

void smpc_hle_device::read_saturn_ports() {
  m_peripheral_size = m_peripheral_pos = 0;
  for (unsigned port = 0; port < 2; ++port) {
    unsigned const mode = (m_pmode >> (port * 2)) & 3;
    // 0-byte mode must not query the port, including its connection status.
    if (mode == 3)
      continue;
    auto &ctrl = port ? m_ctrl2 : m_ctrl1;
    uint8_t const status = ctrl ? ctrl->read_status() : 0xf0;
    m_peripheral_data[m_peripheral_size++] = status;
    for (unsigned i = 0; i < (status & 0xf); ++i) {
      uint8_t const id = ctrl->read_id(i);
      m_peripheral_data[m_peripheral_size++] = id;
      // ST-169 p.73: FF is unconnected; F0-FE are unknown taps whose
      // low nibble is an MD peripheral ID, not a payload length.
      if ((id & 0xf0) == 0xf0)
        continue;

      unsigned size = id & 0xf;
      if (!size) {
        // ST-169 pp.70-73, figs.3.17-3.18: extended reports retain
        // their zero size nibble and insert a separate length byte.
        // 15-byte mode truncates both the length and returned payload.
        size = ctrl->read_ext_size(i);
        if (mode == 0)
          size = std::min<unsigned>(size, 15);
        m_peripheral_data[m_peripheral_size++] = size;
      }
      for (unsigned j = 0; j < size; ++j)
        m_peripheral_data[m_peripheral_size++] = ctrl->read_ctrl_slot(i, j);
    }
  }
  // Snapshot once: continuation must not reread relative-motion devices or
  // replace later bytes with input from a different polling instant.
  // The length query is separate from payload reads so the extension byte
  // cannot consume a relative-motion sample or shift the payload offsets.
}

/* Official documentation says that the "RESET/TAS opcodes aren't supported",
   but Out Run definitely contradicts with it. Since that m68k can't reset
   itself via the RESET opcode I suppose that the SMPC actually do it by reading
   an i/o connected to this opcode. */
void smpc_hle_device::m68k_reset_trigger() {
  m_sndres_timer->adjust(attotime::from_usec(100));
}

// license:BSD-3-Clause
// copyright-holders:ElSemi, R. Belmont
// thanks-to: kingshriek
/*
    Sega/Yamaha YMF292-F (SCSP = Saturn Custom Sound Processor) emulation
    By ElSemi
    MAME/M1 conversion and cleanup by R. Belmont
    Additional code and bugfixes by kingshriek

    This chip has 32 voices.  Each voice can play a sample or be part of
    an FM construct.  Unlike traditional Yamaha FM chips, the base waveform
    for the FM still comes from the wavetable RAM.

    ChangeLog:
    * November 25, 2003  (ES) Fixed buggy timers and envelope overflows.
                         (RB) Improved sample rates other than 44100, multiple
                             chips now works properly.
    * December 02, 2003  (ES) Added DISDL register support, improves mix.
    * April 28, 2004     (ES) Corrected envelope rates, added key-rate scaling,
                             added ringbuffer support.
    * January 8, 2005    (RB) Added ability to specify region offset for RAM.
    * January 26, 2007   (ES) Added on-board DSP capability
    * September 24, 2007 (RB+ES) Removed fake reverb.  Rewrote timers and IRQ
   handling. Fixed case where voice frequency is updated while looping. Enabled
   DSP again.
    * December 16, 2007  (kingshriek) Many EG bug fixes, implemented effects
   mixer, implemented FM.
    * January 5, 2008    (kingshriek+RB) Working, good-sounding FM, removed
   obsolete non-USEDSP code.
    * April 22, 2009     ("PluginNinja") Improved slot monitor, misc cleanups
    * June 6, 2011       (AS) Rewrote DMA from scratch, Darius 2 relies on it.
*/

#include "scsp.h"
#include "emu.h"


#include <algorithm>

// fixed-width enum, safe to save/restore directly
ALLOW_SAVE_TYPE(scsp_device::SCSP_STATE);

/* Chip clocking (ST-077 chapter 2):
   - the sound generator re-sampling frequency is fixed at 44.1 kHz, so one
     output sample (1Fs) is 512 master clocks wide and drivers must feed the
     device 512 * fs (22.5792 MHz on Saturn/ST-V, where the sound 68EC000
     runs at half that)
   - the eight timers count at fs divided by their prescaler (1, 2, 4, 8),
     i.e. one tick per (512 << prescale) master clocks
   - the envelope engine and LFO phase steps are driven by the output sample
     counter (see EG_Update / LFO_ComputeStep), so both track any legal
     master clock instead of assuming a 44100 Hz stream */
static constexpr u32 SAMPLE_CLOCKS = 512;

#define SHIFT 12
#define LFO_SHIFT 8
#define FIX(v) ((u32)((float)(1 << SHIFT) * (v)))

/*
    SCSP features 32 programmable slots
    that can generate FM and PCM (from ROM/RAM) sound
*/

// SLOT PARAMETERS
#define KEYONEX(slot) ((slot->udata.data[0x0] >> 0x0) & 0x1000)
#define KEYONB(slot) ((slot->udata.data[0x0] >> 0x0) & 0x0800)
#define SBCTL(slot) ((slot->udata.data[0x0] >> 0x9) & 0x0003)
#define SSCTL(slot) ((slot->udata.data[0x0] >> 0x7) & 0x0003)
#define LPCTL(slot) ((slot->udata.data[0x0] >> 0x5) & 0x0003)
#define PCM8B(slot) ((slot->udata.data[0x0] >> 0x0) & 0x0010)

#define SA(slot)                                                               \
  (((slot->udata.data[0x0] & 0xF) << 16) | (slot->udata.data[0x1]))

#define LSA(slot) (slot->udata.data[0x2])

#define LEA(slot) (slot->udata.data[0x3])

#define D2R(slot) ((slot->udata.data[0x4] >> 0xB) & 0x001F)
#define D1R(slot) ((slot->udata.data[0x4] >> 0x6) & 0x001F)
#define EGHOLD(slot) ((slot->udata.data[0x4] >> 0x0) & 0x0020)
#define AR(slot) ((slot->udata.data[0x4] >> 0x0) & 0x001F)

#define LPSLNK(slot) ((slot->udata.data[0x5] >> 0x0) & 0x4000)
// undocumented EG bypass (slot register 0x0A bit 15): forces the envelope to
// full volume; both Ymir and mednafen model it
#define EGBYP(slot) ((slot->udata.data[0x5] >> 0xf) & 0x0001)
#define KRS(slot) ((slot->udata.data[0x5] >> 0xA) & 0x000F)
#define DL(slot) ((slot->udata.data[0x5] >> 0x5) & 0x001F)
#define RR(slot) ((slot->udata.data[0x5] >> 0x0) & 0x001F)

#define STWINH(slot) ((slot->udata.data[0x6] >> 0x0) & 0x0200)
#define SDIR(slot) ((slot->udata.data[0x6] >> 0x0) & 0x0100)
#define TL(slot) ((slot->udata.data[0x6] >> 0x0) & 0x00FF)

#define MDL(slot) ((slot->udata.data[0x7] >> 0xC) & 0x000F)
#define MDXSL(slot) ((slot->udata.data[0x7] >> 0x6) & 0x003F)
#define MDYSL(slot) ((slot->udata.data[0x7] >> 0x0) & 0x003F)

#define OCT(slot) ((slot->udata.data[0x8] >> 0xB) & 0x000F)
#define FNS(slot) ((slot->udata.data[0x8] >> 0x0) & 0x03FF)

#define LFORE(slot) ((slot->udata.data[0x9] >> 0x0) & 0x8000)
#define LFOF(slot) ((slot->udata.data[0x9] >> 0xA) & 0x001F)
#define PLFOWS(slot) ((slot->udata.data[0x9] >> 0x8) & 0x0003)
#define PLFOS(slot) ((slot->udata.data[0x9] >> 0x5) & 0x0007)
#define ALFOWS(slot) ((slot->udata.data[0x9] >> 0x3) & 0x0003)
#define ALFOS(slot) ((slot->udata.data[0x9] >> 0x0) & 0x0007)

#define ISEL(slot) ((slot->udata.data[0xA] >> 0x3) & 0x000F)
#define IMXL(slot) ((slot->udata.data[0xA] >> 0x0) & 0x0007)

#define DISDL(slot) ((slot->udata.data[0xB] >> 0xD) & 0x0007)
#define DIPAN(slot) ((slot->udata.data[0xB] >> 0x8) & 0x001F)
#define EFSDL(slot) ((slot->udata.data[0xB] >> 0x5) & 0x0007)
#define EFPAN(slot) ((slot->udata.data[0xB] >> 0x0) & 0x001F)

#define MEM4B() ((m_udata.data[0] >> 0x0) & 0x0200)
#define DAC18B() ((m_udata.data[0] >> 0x0) & 0x0100)
#define MVOL() ((m_udata.data[0] >> 0x0) & 0x000F)
#define RBL() ((m_udata.data[1] >> 0x7) & 0x0003)
#define RBP() ((m_udata.data[1] >> 0x0) & 0x003F)
#define MOFULL() ((m_udata.data[2] >> 0x0) & 0x1000)
#define MOEMPTY() ((m_udata.data[2] >> 0x0) & 0x0800)
#define MIOVF() ((m_udata.data[2] >> 0x0) & 0x0400)
#define MIFULL() ((m_udata.data[2] >> 0x0) & 0x0200)
#define MIEMPTY() ((m_udata.data[2] >> 0x0) & 0x0100)

#define SCILV0() ((m_udata.data[0x24 / 2] >> 0x0) & 0xff)
#define SCILV1() ((m_udata.data[0x26 / 2] >> 0x0) & 0xff)
#define SCILV2() ((m_udata.data[0x28 / 2] >> 0x0) & 0xff)

#define SCIEX0 0
#define SCIEX1 1
#define SCIEX2 2
#define SCIMID 3
#define SCIDMA 4
#define SCIIRQ 5
#define SCITMA 6
#define SCITMB 7

#define USEDSP

static const float SDLT[8] = {-1000000.0f, -36.0f, -30.0f, -24.0f,
                              -18.0f,      -12.0f, -6.0f,  0.0f};

DEFINE_DEVICE_TYPE(SCSP, scsp_device, "scsp", "Yamaha YMF292-F SCSP")

scsp_device::scsp_device(const machine_config &mconfig, const char *tag,
                         device_t *owner, u32 clock)
    : device_t(mconfig, SCSP, tag, owner, clock),
      device_sound_interface(mconfig, *this),
      device_rom_interface(mconfig, *this),
      device_serial_interface(mconfig, *this), m_irq_cb(*this),
      m_main_irq_cb(*this), m_midi_out_cb(*this), m_BUFPTR(0),
      m_stream(nullptr), m_current_level(0), m_MidiOutW(0), m_MidiOutR(0),
      m_MidiW(0), m_MidiR(0), m_master_volume(0), m_mcieb(0), m_mcipd(0),
      m_RBUFDST(nullptr), m_lfsr(1) {
  std::fill(std::begin(m_RINGBUF), std::end(m_RINGBUF), 0);
  std::fill(std::begin(m_MidiStack), std::end(m_MidiStack), 0);
  std::fill(std::begin(m_MidiOutStack), std::end(m_MidiOutStack), 0);
  std::fill(std::begin(m_LPANTABLE), std::end(m_LPANTABLE), 0);
  std::fill(std::begin(m_RPANTABLE), std::end(m_RPANTABLE), 0);
  m_eg_clock = 0;
  std::fill(std::begin(m_EG_TABLE), std::end(m_EG_TABLE), 0);
  std::fill(std::begin(m_PLFO_TRI), std::end(m_PLFO_TRI), 0);
  std::fill(std::begin(m_PLFO_SQR), std::end(m_PLFO_SQR), 0);
  std::fill(std::begin(m_PLFO_SAW), std::end(m_PLFO_SAW), 0);
  std::fill(std::begin(m_ALFO_TRI), std::end(m_ALFO_TRI), 0);
  std::fill(std::begin(m_ALFO_SQR), std::end(m_ALFO_SQR), 0);
  std::fill(std::begin(m_ALFO_SAW), std::end(m_ALFO_SAW), 0);
  memset(m_PSCALES, 0, sizeof(m_PSCALES));
  memset(m_ASCALES, 0, sizeof(m_ASCALES));
  memset(&m_Slots, 0, sizeof(m_Slots));
  memset(&m_udata.data, 0, sizeof(m_udata.data));
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void scsp_device::device_start() {
  // Stereo output with EXTS0,1 Input (External digital audio output)
  // The stream must be allocated before init() because init() calls
  // update_master_volume() which does set_output_gain(0/1, 1.0) and that
  // requires the sound streams to exist — otherwise we trip
  // \"Requested output 0 on sound device :scsp which only has 0\" during
  // start_all_devices (seen at 2aedb4de/55b318be).  The bug has been latent
  // since ab377921 which introduced update_master_volume() in init().
  u32 rate = clock() / SAMPLE_CLOCKS;
  if (rate == 0)
    rate = 44100;
  m_stream = stream_alloc(2, 2, rate);

  // init the emulation
  init();

  for (int slot = 0; slot < 32; slot++) {
    for (int i = 0; i < 0x10; i++)
      save_item(NAME(m_Slots[slot].udata.data[i]), (i << 8) | slot);

    save_item(NAME(m_Slots[slot].Backwards), slot);
    save_item(NAME(m_Slots[slot].active), slot);
    save_item(NAME(m_Slots[slot].cur_addr), slot);
    save_item(NAME(m_Slots[slot].nxt_addr), slot);
    save_item(NAME(m_Slots[slot].step), slot);
    save_item(NAME(m_Slots[slot].EG.level), slot);
    save_item(NAME(m_Slots[slot].EG.prev_level), slot);
    save_item(NAME(m_Slots[slot].EG.state), slot);
    save_item(NAME(m_Slots[slot].EG.attack_bug), slot);
    save_item(NAME(m_Slots[slot].PLFO.phase), slot);
    save_item(NAME(m_Slots[slot].PLFO.phase_step), slot);
    save_item(NAME(m_Slots[slot].ALFO.phase), slot);
    save_item(NAME(m_Slots[slot].ALFO.phase_step), slot);
  }

  for (int i = 0; i < 0x30 / 2; i++) {
    save_item(NAME(m_udata.data[i]), i);
  }

  save_item(NAME(m_RINGBUF));
  save_item(NAME(m_BUFPTR));
  save_item(NAME(m_eg_clock));
#if SCSP_FM_DELAY
  save_item(NAME(m_DELAYBUF));
  save_item(NAME(m_DELAYPTR));
#endif

  save_item(NAME(m_latched_MSLC));
  save_item(NAME(m_latched_MSLC_data));

  save_item(NAME(m_current_level));

  save_item(NAME(m_MidiOutStack));
  save_item(NAME(m_MidiOutW));
  save_item(NAME(m_MidiOutR));
  save_item(NAME(m_MidiStack));
  save_item(NAME(m_MidiW));
  save_item(NAME(m_MidiR));

  for (int i = 0; i < 3; i++) {
    save_item(NAME(m_timers[i].counter), i);
    save_item(NAME(m_timers[i].prescale), i);
    save_item(NAME(m_timers[i].reload), i);
    save_item(NAME(m_timers[i].reload_pending), i);
  }

  save_item(NAME(m_dma.dmea));
  save_item(NAME(m_dma.drga));
  save_item(NAME(m_dma.dtlg));
  save_item(NAME(m_dma.dgate));
  save_item(NAME(m_dma.ddir));

  save_item(NAME(m_mcieb));
  save_item(NAME(m_mcipd));

  save_item(NAME(m_lfsr));

  save_item(NAME(m_DSP.RBP));
  save_item(NAME(m_DSP.RBL));
  save_item(NAME(m_DSP.COEF));
  save_item(NAME(m_DSP.MADRS));
  save_item(NAME(m_DSP.MPRO));
  save_item(NAME(m_DSP.TEMP));
  save_item(NAME(m_DSP.MEMS));
  save_item(NAME(m_DSP.DEC));
  save_item(NAME(m_DSP.MIXS));
  save_item(NAME(m_DSP.INPUTS));
  save_item(NAME(m_DSP.ACC));
  save_item(NAME(m_DSP.FRC_REG));
  save_item(NAME(m_DSP.Y_REG));
  save_item(NAME(m_DSP.ADRS_REG));
  save_item(NAME(m_DSP.RWAddr));
  save_item(NAME(m_DSP.ReadValue));
  save_item(NAME(m_DSP.ReadPending));
  save_item(NAME(m_DSP.WritePending));
  save_item(NAME(m_DSP.WriteValue));
  save_item(NAME(m_DSP.EXTS));
  save_item(NAME(m_DSP.EFREG));
  save_item(NAME(m_DSP.Stopped));
  save_item(NAME(m_DSP.LastStep));
}

//-------------------------------------------------
//  device_reset - device-specific reset
//-------------------------------------------------

void scsp_device::device_reset() {
  set_data_frame(1, 8, PARITY_NONE, STOP_BITS_1);
  set_rate(31250);

  // no interrupt is being requested to the sound CPU after a reset
  m_current_level = 0;

  // the noise generator restarts from a known state
  m_lfsr = 1;
}

//-------------------------------------------------
//  device_post_load - called after loading a saved state
//-------------------------------------------------

void scsp_device::device_post_load() {
  for (int slot = 0; slot < 32; slot++)
    Compute_LFO(&m_Slots[slot]);

  update_master_volume();

  // timers are scheduled against machine time, rebase and reschedule them
  for (int i = 0; i < 3; i++) {
    m_timers[i].base_time = machine().time();
    timer_arm(i);
  }
}

//-------------------------------------------------
//  device_clock_changed - called if the clock
//  changes
//-------------------------------------------------

void scsp_device::device_clock_changed() {
  m_stream->set_sample_rate(clock() / SAMPLE_CLOCKS);
  // LFO phase steps are per output sample, so they must be recomputed when
  // the sample rate changes
  for (int i = 0; i < 32; ++i)
    Compute_LFO(&m_Slots[i]);
}

void scsp_device::rom_bank_pre_change() { m_stream->update(); }

//-------------------------------------------------
//  sound_stream_update - handle a stream update
//-------------------------------------------------

void scsp_device::sound_stream_update(sound_stream &stream) {
  DoMasterSamples(stream);

  // MSLC     |  CA   |SGC|EG
  // f e d c b a 9 8 7 6 5 4 3 2 1 0

  // latch the new MSLC, updates every 44.1 kHz
  // cfr. vstriker (GK reflecting ball with heavy shots) and srallyc (PowerGames
  // BGM bleeps at end)
  u8 MSLC = m_latched_MSLC;
  SCSP_SLOT *slot = m_Slots + MSLC;
  u32 SGC = (slot->EG.state) & 3;
  u32 CA = (slot->cur_addr >> (SHIFT + 12)) & 0xf;
  u32 EG = (slot->EG.prev_level >> 5) & 0x1f;
  // NOTE: according to the manual MSLC is write only, CA, SGC and EG read only.
  // saturn:toughtrk will hang on Human logo otherwise
  m_latched_MSLC_data = /*(MSLC << 11) |*/ (CA << 7) | (SGC << 5) | EG;

  // 1Fs: one output sample has been produced.  Hardware requests this every
  // sample (44.1 kHz); samples are generated in batches here, so request it
  // once per update, like Yabause does.
  if (stream.samples() > 0) {
    m_udata.data[0x20 / 2] |= 0x400;
    CheckPendingIRQ();
    MainCheckPendingIRQ(0x400);
  }
}

void scsp_device::CheckPendingIRQ() {
  u32 pend = m_udata.data[0x20 / 2];
  u32 const en = m_udata.data[0x1e / 2];

  // MIDI input non-empty is derived from the input FIFO state
  if (m_MidiW != m_MidiR) {
    m_udata.data[0x20 / 2] |= 0x08;
    pend |= 0x08;
  }

  u32 mask = pend & en;

  // sources 8 to 10 (timer C, MIDI output empty and sample tick) have no
  // level of their own in SCILV0-2, they share the one of source 7
  if (mask & ~0xff)
    mask = (mask & 0xff) | 0x80;

  // SCILV0/1/2 hold bit 0/1/2 of the level assigned to every source, the
  // level driven to the sound CPU is the highest one currently requested
  u32 level = 0;
  if (mask) {
    u32 lv0 = SCILV0() & mask;
    u32 lv1 = SCILV1() & mask;
    u32 lv2 = SCILV2() & mask;

    if (lv2) {
      level |= 0x4;
      lv1 &= lv2;
      lv0 &= lv2;
    }
    if (lv1) {
      level |= 0x2;
      lv0 &= lv1;
    }
    if (lv0)
      level |= 0x1;
  }

  if (level == m_current_level)
    return;

  // drop the previously requested level before raising the new one
  if (m_current_level != 0)
    m_irq_cb(m_current_level, CLEAR_LINE);

  m_current_level = level;

  if (level != 0)
    m_irq_cb(level, ASSERT_LINE);
  else
    m_irq_cb((offs_t)0, CLEAR_LINE);
}

void scsp_device::MainCheckPendingIRQ(u16 irq_type) {
  m_mcipd |= irq_type;

  // machine().scheduler().synchronize(); // force resync

  update_main_irq();
}

// re-drive the main CPU interrupt line from whatever is pending and enabled
void scsp_device::update_main_irq() {
  m_main_irq_cb((m_mcipd & m_mcieb) ? 1 : 0);
}

void scsp_device::ResetInterrupts() {
  // SCIRE drops the requested bits, the sound CPU level is recomputed from
  // whatever is still pending afterwards
  m_udata.data[0x20 / 2] &= ~m_udata.data[0x22 / 2];

  CheckPendingIRQ();
}

//-------------------------------------------------
//  timer_sync - lazily advance a timer counter up
//  to the current machine time
//-------------------------------------------------

void scsp_device::timer_sync(int idx) {
  SCSP_TIMER &t = m_timers[idx];
  attotime const now = machine().time();

  if (now <= t.base_time)
    return;

  u64 const inc_clocks = u64(SAMPLE_CLOCKS) << t.prescale;
  u32 steps = u32((now - t.base_time).as_ticks(clock()) / inc_clocks);
  if (steps == 0)
    return;

  t.base_time += attotime::from_ticks(u64(steps) * inc_clocks, clock());

  // a pending TIMx write is loaded on the next tick instead of incrementing
  if (t.reload_pending) {
    t.counter = t.reload;
    t.reload_pending = false;
    steps--;
  }

  t.counter = u8(t.counter + steps);
}

//-------------------------------------------------
//  timer_arm - schedule the next 0xff crossing
//-------------------------------------------------

void scsp_device::timer_arm(int idx) {
  SCSP_TIMER &t = m_timers[idx];

  if (t.timer == nullptr)
    return;

  timer_sync(idx);

  // ticks left before the counter reaches 0xff and requests an interrupt
  u32 incs =
      t.reload_pending ? (0x100 - t.reload) : ((0xff - t.counter) & 0xff);
  if (incs == 0)
    incs = 0x100;

  t.timer->adjust(attotime::from_ticks(
                      u64(incs) * (u64(SAMPLE_CLOCKS) << t.prescale), clock()),
                  idx);
}

//-------------------------------------------------
//  timer_write - TxCTL / TIMx register write
//-------------------------------------------------

void scsp_device::timer_write(int idx, u16 data, u16 mem_mask) {
  SCSP_TIMER &t = m_timers[idx];

  timer_sync(idx);

  // TIMx doesn't touch the counter directly, it is loaded on the next tick
  if (mem_mask & 0x00ff) {
    t.reload = data & 0xff;
    t.reload_pending = true;
  }

  if (mem_mask & 0x0700)
    t.prescale = (data >> 8) & 0x7;

  timer_arm(idx);
}

//-------------------------------------------------
//  timer_read - current counter value
//-------------------------------------------------

u8 scsp_device::timer_read(int idx) {
  timer_sync(idx);
  return m_timers[idx].counter;
}

TIMER_CALLBACK_MEMBER(scsp_device::timer_cb) {
  int const idx = param;

  timer_sync(idx);

  // the counter has hit 0xff: request the interrupt on both the sound CPU
  // (SCIPD) and the main CPU (MCIPD) side, then keep counting
  m_udata.data[0x20 / 2] |= 0x40 << idx;
  m_udata.data[(0x18 + idx * 2) / 2] =
      (m_udata.data[(0x18 + idx * 2) / 2] & 0xff00) | m_timers[idx].counter;

  CheckPendingIRQ();
  MainCheckPendingIRQ(0x40 << idx);

  timer_arm(idx);
}

//-------------------------------------------------
//  update_master_volume - MVOL is a logarithmic
//  attenuator, 0 mutes the output entirely
//-------------------------------------------------

void scsp_device::update_master_volume() {
  u32 const mvol = MVOL();

  // the output gain is applied by hand in DoMasterSamples()
  set_output_gain(0, 1.0);
  set_output_gain(1, 1.0);

  if (mvol == 0) {
    m_master_volume = 0;
    return;
  }

  // roughly 2.5dB per step, Q8 fixed point (0x100 == unity)
  u32 mv = 0x2 << (mvol >> 1);
  if (!(mvol & 1))
    mv -= (mv >> 2);

  m_master_volume = mv;
}

// hardware bug (Ymir CheckAttackBug): with key rate scaling active, an attack
// rate plus the scaled KRS/octave adjustment of 0x20 or more stalls the attack
// ramp; KRS = 0xF is immune.  Re-checked on writes to the AR/KRS registers,
// so the flag tracks them live rather than being latched only at key-on.
void scsp_device::Check_Attack_Bug(SCSP_SLOT *slot) {
  if (KRS(slot) != 0xf) {
    int const oct = (OCT(slot) ^ 8) - 8;
    slot->EG.attack_bug =
        (AR(slot) + std::clamp<int>(int(KRS(slot)) + oct, 0, 0xf)) >= 0x20;
  } else
    slot->EG.attack_bug = false;
}

/* Hardware envelope engine.

   The chip works in the attenuation domain (0x000 loudest .. 0x3FF silent).
   The 5-bit segment rate (AR/D1R/D2R/RR) is adjusted by key rate scaling and
   the octave, doubled and clamped to 6 bits; the effective rate selects a
   sample-counter shift and an 8-phase increment pattern, so the envelope
   only advances on samples whose low counter bits are zero - the EG is
   clocked by the global sample counter rather than ramping a fractional
   amount every sample.  Attack attenuates geometrically (the addend is
   proportional to the current level), decay/release linearly.  Model, tables
   and the attack-rate bug follow Ymir's IncrementEG (hardware-tested) with
   mednafen's RunEG and SaturnRecomp's env_tick as second and third sources;
   this replaces millisecond-based tables that assumed a 44100 Hz stream and
   a linear amplitude ramp. */
int scsp_device::EG_Update(SCSP_SLOT *slot, u64 eg_clock) {
  static constexpr u8 counter_shift[64] = {
      12, 12, 12, 12, 11, 11, 11, 11, 10, 10, 10, 10, 9, 9, 9, 9,
      8,  8,  8,  8,  7,  7,  7,  7,  6,  6,  6,  6,  5, 5, 5, 5,
      4,  4,  4,  4,  3,  3,  3,  3,  2,  2,  2,  2,  1, 1, 1, 1,
      1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 1, 1, 1};

  static constexpr u8 increment[64][8] = {
      {0, 0, 0, 0, 0, 0, 0, 0}, /* 0x00 */
      {0, 0, 0, 0, 0, 0, 0, 0}, /* 0x01 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x02 */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x03 */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x04 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x05 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x06 */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x07 */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x08 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x09 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x0A */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x0B */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x0C */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x0D */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x0E */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x0F */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x10 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x11 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x12 */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x13 */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x14 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x15 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x16 */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x17 */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x18 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x19 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x1A */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x1B */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x1C */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x1D */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x1E */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x1F */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x20 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x21 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x22 */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x23 */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x24 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x25 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x26 */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x27 */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x28 */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x29 */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x2A */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x2B */
      {0, 1, 0, 1, 0, 1, 0, 1}, /* 0x2C */
      {0, 1, 0, 1, 1, 1, 0, 1}, /* 0x2D */
      {0, 1, 1, 1, 0, 1, 1, 1}, /* 0x2E */
      {0, 1, 1, 1, 1, 1, 1, 1}, /* 0x2F */
      {1, 1, 1, 1, 1, 1, 1, 1}, /* 0x30 */
      {1, 1, 1, 2, 1, 1, 1, 2}, /* 0x31 */
      {2, 1, 2, 1, 2, 1, 2, 1}, /* 0x32 */
      {1, 2, 2, 2, 1, 2, 2, 2}, /* 0x33 */
      {2, 2, 2, 2, 2, 2, 2, 2}, /* 0x34 */
      {2, 2, 2, 4, 2, 2, 2, 4}, /* 0x35 */
      {4, 2, 4, 2, 4, 2, 4, 2}, /* 0x36 */
      {2, 4, 4, 4, 2, 4, 4, 4}, /* 0x37 */
      {4, 4, 4, 4, 4, 4, 4, 4}, /* 0x38 */
      {4, 4, 4, 8, 4, 4, 4, 8}, /* 0x39 */
      {8, 4, 8, 4, 8, 4, 8, 4}, /* 0x3A */
      {4, 8, 8, 8, 4, 8, 8, 8}, /* 0x3B */
      {8, 8, 8, 8, 8, 8, 8, 8}, /* 0x3C */
      {8, 8, 8, 8, 8, 8, 8, 8}, /* 0x3D */
      {8, 8, 8, 8, 8, 8, 8, 8}, /* 0x3E */
      {8, 8, 8, 8, 8, 8, 8, 8}  /* 0x3F */
  };
  // rate register of the current segment
  unsigned rate;
  switch (slot->EG.state) {
  case SCSP_ATTACK:
    rate = AR(slot);
    break;
  case SCSP_DECAY1:
    rate = D1R(slot);
    break;
  case SCSP_DECAY2:
    rate = D2R(slot);
    break;
  default:
    rate = RR(slot);
    break;
  }

  // effective rate: KRS/octave adjustment (unless KRS = 0xF), doubled, 6-bit
  unsigned eff = rate;
  if (KRS(slot) != 0xf)
    eff += std::clamp<int>(int(KRS(slot)) + ((OCT(slot) ^ 8) - 8), 0, 0xf);
  eff = std::min<unsigned>(eff << 1, 0x3f);

  // the EG only advances when the low counter bits are zero
  const u32 shift = counter_shift[eff];
  const u32 inc = (u32(eg_clock) & ((1u << shift) - 1u))
                      ? 0u
                      : increment[eff][(eg_clock >> shift) & 7];

  const u32 prev_out = slot->EG.prev_level;
  const u32 curr = slot->EG.level;

  // externally visible level for this tick; EG hold (in attack) and the
  // undocumented bypass bit both force full volume
  slot->EG.prev_level =
      (EGBYP(slot) || (slot->EG.state == SCSP_ATTACK && EGHOLD(slot))) ? 0u
                                                                       : curr;

  switch (slot->EG.state) {
  case SCSP_ATTACK:
    // geometric attack: level += (~level * inc) >> 4, with the level
    // sampled before the update
    if (!slot->EG.attack_bug && inc > 0 && curr > 0 && rate > 0)
      slot->EG.level =
          std::clamp<s32>(s32(curr) + ((~s32(curr) * s32(inc)) >> 4), 0, 0x3ff);
    // LPSLNK slots make the attack -> decay 1 transition from the loop
    // start crossing in UpdateSlot instead
    if (!LPSLNK(slot) && curr == 0)
      slot->EG.state = SCSP_DECAY1;
    break;

  case SCSP_DECAY1:
    if ((curr >> 5) == DL(slot))
      slot->EG.state = SCSP_DECAY2;
    [[fallthrough]];

  case SCSP_DECAY2:
  case SCSP_RELEASE:
    // rate 0 sustains (D2R = 0 holds the sound per the manual)
    if (rate > 0)
      slot->EG.level = std::min<u32>(curr + inc, 0x3ff);
    break;

  default:
    break;
  }

  // a slot whose externally visible attenuation reached 0x3C0 goes inactive
  // in ANY segment, not just release - the previous output level feeds the
  // test, and the bypass bit suppresses it
  if (prev_out >= 0x3c0 && !EGBYP(slot)) {
    StopSlot(slot, 0);
    slot->Backwards = 0;
  }

  // consumers index the dB table with a 10-bit amplitude value
  return (0x3ff - slot->EG.prev_level) << (SHIFT - 10);
}

u32 scsp_device::Step(SCSP_SLOT *slot) {
  int octave = (OCT(slot) ^ 8) - 8 + SHIFT - 10;
  u32 Fn = FNS(slot) + (1 << 10);
  if (octave >= 0) {
    Fn <<= octave;
  } else {
    Fn >>= -octave;
  }

  return Fn;
}

void scsp_device::Compute_LFO(SCSP_SLOT *slot) {
  if (PLFOS(slot) != 0)
    LFO_ComputeStep(&(slot->PLFO), LFOF(slot), PLFOWS(slot), PLFOS(slot), 0);
  if (ALFOS(slot) != 0)
    LFO_ComputeStep(&(slot->ALFO), LFOF(slot), ALFOWS(slot), ALFOS(slot), 1);
}

void scsp_device::StartSlot(SCSP_SLOT *slot) {
  slot->active = 1;
  slot->cur_addr = 0;
  slot->nxt_addr = 1 << SHIFT;
  slot->step = Step(slot);
  slot->EG.state = SCSP_ATTACK;
  Check_Attack_Bug(slot);
  // when the attack bug strikes the key-on starts at full volume (0x000
  // attenuation) instead of the usual 0x280
  slot->EG.level = slot->EG.attack_bug ? 0x000 : 0x280;
  slot->EG.prev_level = slot->EG.level;
  slot->Prev = 0;
  slot->Backwards = 0;

  Compute_LFO(slot);

  //  printf("StartSlot[%p]: SA %x PCM8B %x LPCTL %x ALFOS %x STWINH %x TL %x
  //  EFSDL %x\n", slot, SA(slot), PCM8B(slot), LPCTL(slot), ALFOS(slot),
  //  STWINH(slot), TL(slot), EFSDL(slot));
}

void scsp_device::StopSlot(SCSP_SLOT *slot, int keyoff) {
  if (keyoff /*&& slot->EG.state!=SCSP_RELEASE*/) {
    slot->EG.state = SCSP_RELEASE;
  } else {
    slot->active = 0;
  }
  slot->udata.data[0] &= ~0x800;
}

void scsp_device::init() {
  int i;

  m_DSP.Init();

  m_current_level = 0;
  m_MidiR = m_MidiW = 0;
  m_MidiOutR = m_MidiOutW = 0;

  m_DSP.space = &this->space();
  for (i = 0; i < 3; i++)
    m_timers[i].timer = timer_alloc(FUNC(scsp_device::timer_cb), this);

  for (i = 0; i < 0x400; ++i) {
    float envDB = ((float)(3 * (i - 0x3ff))) / 32.0f;
    float scale = (float)(1 << SHIFT);
    m_EG_TABLE[i] = (s32)(powf(10.0f, envDB / 20.0f) * scale);
  }

  for (i = 0; i < 0x10000; ++i) {
    int iTL = (i >> 0x0) & 0xff;
    int iPAN = (i >> 0x8) & 0x1f;
    int iSDL = (i >> 0xD) & 0x07;
    float TL;
    float SegaDB = 0.0f;
    float fSDL;
    float PAN;
    float LPAN, RPAN;

    if (iTL & 0x01)
      SegaDB -= 0.4f;
    if (iTL & 0x02)
      SegaDB -= 0.8f;
    if (iTL & 0x04)
      SegaDB -= 1.5f;
    if (iTL & 0x08)
      SegaDB -= 3.0f;
    if (iTL & 0x10)
      SegaDB -= 6.0f;
    if (iTL & 0x20)
      SegaDB -= 12.0f;
    if (iTL & 0x40)
      SegaDB -= 24.0f;
    if (iTL & 0x80)
      SegaDB -= 48.0f;

    TL = powf(10.0f, SegaDB / 20.0f);

    SegaDB = 0;
    if (iPAN & 0x1)
      SegaDB -= 3.0f;
    if (iPAN & 0x2)
      SegaDB -= 6.0f;
    if (iPAN & 0x4)
      SegaDB -= 12.0f;
    if (iPAN & 0x8)
      SegaDB -= 24.0f;

    if ((iPAN & 0xf) == 0xf)
      PAN = 0.0;
    else
      PAN = powf(10.0f, SegaDB / 20.0f);

    if (iPAN < 0x10) {
      LPAN = PAN;
      RPAN = 1.0;
    } else {
      RPAN = PAN;
      LPAN = 1.0;
    }

    if (iSDL)
      fSDL = powf(10.0f, (SDLT[iSDL]) / 20.0f);
    else
      fSDL = 0.0;

    m_LPANTABLE[i] = FIX((4.0f * LPAN * TL * fSDL));
    m_RPANTABLE[i] = FIX((4.0f * RPAN * TL * fSDL));
  }

  m_eg_clock = 0;

  // make sure all the slots are off
  for (i = 0; i < 32; ++i) {
    m_Slots[i].slot = i;
    m_Slots[i].active = 0;
    m_Slots[i].EG.state = SCSP_RELEASE;
    m_Slots[i].EG.level = 0x3ff;
    m_Slots[i].EG.prev_level = 0x3ff;
    m_Slots[i].EG.attack_bug = false;
  }

  LFO_Init();
  // no "pend"
  m_udata.data[0x20 / 2] = 0;
  m_mcipd = 0;
  for (i = 0; i < 3; i++) {
    m_timers[i].counter = 0;
    m_timers[i].prescale = 0;
    m_timers[i].reload = 0;
    m_timers[i].reload_pending = false;
    m_timers[i].base_time = machine().time();
    if (m_timers[i].timer != nullptr)
      m_timers[i].timer->reset();
  }

  update_master_volume();
}

void scsp_device::UpdateSlotReg(int s, int r) {
  SCSP_SLOT *slot = m_Slots + s;
  switch (r & 0x3f) {
  case 0:
  case 1:
    if (KEYONEX(slot)) {
      for (int sl = 0; sl < 32; ++sl) {
        SCSP_SLOT *s2 = m_Slots + sl;
        {
          if (KEYONB(s2) && s2->EG.state == SCSP_RELEASE /*&& !s2->active*/) {
            StartSlot(s2);
          }
          if (!KEYONB(s2) /*&& s2->active*/) {
            StopSlot(s2, 1);
          }
        }
      }
      slot->udata.data[0] &= ~0x1000;
    }
    break;
  case 0x10:
  case 0x11:
    slot->step = Step(slot);
    break;
  case 8:
  case 9:
  case 0xA:
  case 0xB:
    // EG_Update reads AR/D1R/D2R/RR/DL/KRS/LPSLNK/EGBYP live from the
    // register file; only the attack-bug flag needs recomputing here,
    // matching Ymir's CheckAttackBug on reg 0x08/0x0A writes
    Check_Attack_Bug(slot);
    break;
  case 0x12:
  case 0x13:
    Compute_LFO(slot);
    break;
  }
}

void scsp_device::UpdateReg(int reg, u16 mem_mask) {
  switch (reg & 0x3f) {
  case 0x0:
    update_master_volume();
    break;
  case 0x2:
  case 0x3: {
    m_DSP.RBL = (8 * 1024) << RBL(); // 8 / 16 / 32 / 64 kwords
    m_DSP.RBP = RBP();
  } break;
  case 0x6:
  case 0x7: {
    u8 data = m_udata.data[0x6 / 2] & 0xff;
    if (m_MidiOutR == m_MidiOutW) {
      // not busy, so start transmission
      transmit_register_setup(data);
    }
    m_MidiOutStack[m_MidiOutW++] = data;
    m_MidiOutW &= 31;

    // the buffer is no longer empty, drop the pending request
    m_udata.data[0x20 / 2] &= ~0x200;
    m_mcipd &= ~0x200;
    CheckPendingIRQ();
    update_main_irq();
  } break;
  case 8:
  case 9:
    /* Only MSLC could be written.  */
    // docs claims MSLC to be 0x7800 but saturn:jikkparo doesn't agree,
    // assume doc mistake out of being 0~31 slots
    m_latched_MSLC = (m_udata.data[0x8 / 2] & 0xf800) >> 11;
    break;
  case 0x12:
  case 0x13:
    m_dma.dmea = (m_udata.data[0x12 / 2] & 0xfffe) | (m_dma.dmea & 0xf0000);
    break;
  case 0x14:
  case 0x15:
    m_dma.dmea =
        ((m_udata.data[0x14 / 2] & 0xf000) << 4) | (m_dma.dmea & 0xfffe);
    m_dma.drga = (m_udata.data[0x14 / 2] & 0x0ffe);
    break;
  case 0x16:
  case 0x17:
    m_dma.dtlg = (m_udata.data[0x16 / 2] & 0x0ffe);
    m_dma.ddir = (m_udata.data[0x16 / 2] & 0x2000) >> 13;
    m_dma.dgate = (m_udata.data[0x16 / 2] & 0x4000) >> 14;
    if (m_udata.data[0x16 / 2] & 0x1000) // dexe
      exec_dma();
    break;
  case 0x18:
  case 0x19:
    if (!m_irq_cb.isunset())
      timer_write(0, m_udata.data[0x18 / 2], mem_mask);
    break;
  case 0x1a:
  case 0x1b:
    if (!m_irq_cb.isunset())
      timer_write(1, m_udata.data[0x1a / 2], mem_mask);
    break;
  case 0x1c:
  case 0x1d:
    if (!m_irq_cb.isunset())
      timer_write(2, m_udata.data[0x1c / 2], mem_mask);
    break;
  case 0x1e: // SCIEB
  case 0x1f:
    if (!m_irq_cb.isunset())
      CheckPendingIRQ();
    break;
  case 0x20: // SCIPD
  case 0x21:
    if (!m_irq_cb.isunset()) {
      if (m_udata.data[0x1e / 2] & m_udata.data[0x20 / 2] & 0x20) {
        // SCIPD is read-only except for bit 5: writing 1 there applies a CPU
        // interrupt (source 5, level 7 - which ST-077 says "not to use
        // because tied to dev board irq"), writing 0 is invalid.  The OR into
        // the pending register happens in w16(), matching mednafen.  Software
        // requesting its own level-7 interrupt is unusual enough to keep
        // logging (Arcade's Greatest Hits does it).
        logerror("%s: SCSP SCIPD write CPU irq 0x20\n",
                 machine().describe_context());
        CheckPendingIRQ();
      }
    }
    break;
  case 0x22: // SCIRE
  case 0x23:
    if (!m_irq_cb.isunset()) {
      ResetInterrupts();

      // behavior from real hardware: if you SCIRE a timer that's expired,
      // it'll immediately pop up again in SCIPD.  cfr. saturn:sakurat
      // Note that this only lasts for as long as the counter sits on 0xff,
      // i.e. one timer tick, so it doesn't turn into an interrupt storm
      // (cfr. crocj).
      bool repend = false;
      for (int i = 0; i < 3; i++) {
        if (timer_read(i) == 0xff) {
          m_udata.data[0x20 / 2] |= 0x40 << i;
          repend = true;
        }
      }
      if (repend)
        CheckPendingIRQ();
    }
    break;
  case 0x24:
  case 0x25:
  case 0x26:
  case 0x27:
  case 0x28:
  case 0x29:
    // SCILV0-2 assign a 3 bit level to every interrupt source, they
    // are resolved against the pending requests on the fly
    if (!m_irq_cb.isunset())
      CheckPendingIRQ();
    break;
  case 0x2a:
  case 0x2b:
    m_mcieb = m_udata.data[0x2a / 2];

    MainCheckPendingIRQ(0);

    // the external INT0N/INT1N/INT2N pins (bits 0-2) are marked
    // "currently not used" in the ST-077 pinout and are not wired up by
    // any current user of this device; log their enablement so software
    // relying on them can be spotted
    if (m_mcieb & 0x007)
      logerror("%s: SCSP MCIEB enabled %04x\n", machine().describe_context(),
               m_mcieb);
    break;
  case 0x2c:
  case 0x2d:
    if (m_udata.data[0x2c / 2] & 0x20)
      MainCheckPendingIRQ(0x20);
    break;
  case 0x2e:
  case 0x2f:
    m_mcipd &= ~m_udata.data[0x2e / 2];
    MainCheckPendingIRQ(0);
    break;
  }
}

void scsp_device::UpdateSlotRegR(int slot, int reg) {}

void scsp_device::UpdateRegR(int reg) {
  switch (reg & 0x3f) {
  case 4:
  case 5: {
    u16 v = m_udata.data[0x4 / 2];
    v &= 0xff00;
    v |= m_MidiStack[m_MidiR];
    logerror("Read %x from SCSP MIDI\n", v);
    if (m_MidiR != m_MidiW) {
      ++m_MidiR;
      m_MidiR &= 31;
    }
    if (m_MidiR == m_MidiW) // if the input FIFO is empty, clear the IRQ
    {
      m_udata.data[0x20 / 2] &= ~0x08;
      m_mcipd &= ~0x08;
      CheckPendingIRQ();
      update_main_irq();
    }
    m_udata.data[0x4 / 2] = v;
  } break;
  case 8:
  case 9: {
    m_udata.data[0x8 / 2] = m_latched_MSLC_data;
  } break;

  case 0x18:
  case 0x19:
  case 0x1a:
  case 0x1b:
  case 0x1c:
  case 0x1d:
    // the manual claims the timer registers to be write only, report
    // the live counter value anyway
    {
      int const idx = ((reg & 0x3f) - 0x18) >> 1;
      u16 &data = m_udata.data[(0x18 + idx * 2) / 2];
      data = (data & 0xff00) | timer_read(idx);
    }
    break;

  case 0x2a:
  case 0x2b:
    m_udata.data[0x2a / 2] = m_mcieb;
    break;

  case 0x2c:
  case 0x2d:
    m_udata.data[0x2c / 2] = m_mcipd;
    break;
  }
}

void scsp_device::w16(u32 addr, u16 val, u16 mem_mask) {
  addr &= 0xffff;
  if (addr < 0x400) {
    int slot = addr / 0x20;
    addr &= 0x1f;
    *((u16 *)(m_Slots[slot].udata.datab + (addr))) = val;
    UpdateSlotReg(slot, addr & 0x1f);
  } else if (addr < 0x600) {
    if (addr < 0x430) {
      // SCIPD and MCIPD are r/o except for bit 5 CPU irqs
      if (addr == 0x420 || addr == 0x42e) {
        *((u16 *)(m_udata.datab + ((addr & 0x3f)))) |= val & 0x20;
      } else
        *((u16 *)(m_udata.datab + ((addr & 0x3f)))) = val;
      UpdateReg(addr & 0x3f, mem_mask);
    }
  } else if (addr < 0x700)
    m_RINGBUF[(addr - 0x600) / 2] = val;
  else {
    // DSP
    if (addr < 0x780) // COEF
      *((u16 *)(m_DSP.COEF + (addr - 0x700) / 2)) = val;
    else if (addr < 0x7c0)
      *((u16 *)(m_DSP.MADRS + (addr - 0x780) / 2)) = val;
    else if (addr < 0x800) // MADRS is mirrored twice
      *((u16 *)(m_DSP.MADRS + (addr - 0x7c0) / 2)) = val;
    else if (addr < 0xC00) {
      *((uint16_t *)(m_DSP.MPRO + (addr - 0x800) / 2)) = val;

      if (addr == 0xBF0) {
        m_DSP.Start();
      }
    }
  }
}

u16 scsp_device::r16(u32 addr) {
  u16 v = 0;
  addr &= 0xffff;
  if (addr < 0x400) {
    int slot = addr / 0x20;
    addr &= 0x1f;
    UpdateSlotRegR(slot, addr & 0x1f);
    v = *((u16 *)(m_Slots[slot].udata.datab + (addr)));
  } else if (addr < 0x600) {
    if (addr < 0x430) {
      UpdateRegR(addr & 0x3f);
      v = *((u16 *)(m_udata.datab + ((addr & 0x3f))));
    }
  } else if (addr < 0x700)
    v = m_RINGBUF[(addr - 0x600) / 2];
  else {
    // DSP
    if (addr < 0x780) // COEF
      v = *((u16 *)(m_DSP.COEF + (addr - 0x700) / 2));
    else if (addr < 0x7c0)
      v = *((u16 *)(m_DSP.MADRS + (addr - 0x780) / 2));
    else if (addr < 0x800)
      v = *((u16 *)(m_DSP.MADRS + (addr - 0x7c0) / 2));
    else if (addr < 0xC00)
      v = *((u16 *)(m_DSP.MPRO + (addr - 0x800) / 2));
    else if (addr < 0xE00) {
      if (addr & 2)
        v = m_DSP.TEMP[(addr >> 2) & 0x7f] & 0xffff;
      else
        v = m_DSP.TEMP[(addr >> 2) & 0x7f] >> 16;
    } else if (addr < 0xE80) {
      if (addr & 2)
        v = m_DSP.MEMS[(addr >> 2) & 0x1f] & 0xffff;
      else
        v = m_DSP.MEMS[(addr >> 2) & 0x1f] >> 16;
    } else if (addr < 0xEC0) {
      if (addr & 2)
        v = m_DSP.MIXS[(addr >> 2) & 0xf] & 0xffff;
      else
        v = m_DSP.MIXS[(addr >> 2) & 0xf] >> 16;
    } else if (addr < 0xEE0)
      v = *((u16 *)(m_DSP.EFREG + (addr - 0xec0) / 2));
    else {
      // saturn Multiplayer Audio CDs and kyutnkai (68k PC=004A3A) reads from
      // 0xee0/0xee2 EXTS returns back current sample, makes the balloons in
      // former to inflate.
      logerror("%s: SCSP Reading from EXTS register %08x\n",
               machine().describe_context(), addr);
      if (addr < 0xEE4)
        v = *((u16 *)(m_DSP.EXTS + (addr - 0xee0) / 2));
    }
  }
  return v;
}

inline s32 scsp_device::UpdateSlot(SCSP_SLOT *slot) {
  if (SSCTL(slot) == 3) // manual says cannot be used
  {
    logerror("SCSP: Invaild SSCTL setting at slot %02x\n", slot->slot);
    return 0;
  }

  s32 sample = 0; // NB: Shouldn't be necessary, but GCC 8.2.1 claims otherwise.
  int step = slot->step;
  u32 addr1, addr2, addr_select;   // current and next sample addresses
  u32 *addr[2] = {&addr1, &addr2}; // used for linear interpolation
  u32 *slot_addr[2] = {&(slot->cur_addr), &(slot->nxt_addr)}; //

  if (PLFOS(slot) != 0) {
    step = step * PLFO_Step(&(slot->PLFO));
    step >>= SHIFT;
  }

  if (PCM8B(slot)) {
    addr1 = slot->cur_addr >> SHIFT;
    addr2 = slot->nxt_addr >> SHIFT;
  } else {
    addr1 = (slot->cur_addr >> (SHIFT - 1)) & ~1;
    addr2 = (slot->nxt_addr >> (SHIFT - 1)) & ~1;
  }

  if (MDL(slot) != 0 || MDXSL(slot) != 0 || MDYSL(slot) != 0) {
    s32 smp = (m_RINGBUF[(m_BUFPTR + MDXSL(slot)) & 63] +
               m_RINGBUF[(m_BUFPTR + MDYSL(slot)) & 63]) /
              2;

    smp <<= 0xA; // associate cycle with 1024
    smp >>= 0x1A -
            MDL(slot); // ex. for MDL=0xF, sample range corresponds to +/- 64 pi
                       // (32=2^5 cycles) so shift by 11 (16-5 == 0x1A-0xF)
    if (!PCM8B(slot))
      smp <<= 1;

    addr1 += smp;
    addr2 += smp;
  }

  if (SSCTL(slot) == 0) // External DRAM data
  {
    if (PCM8B(slot)) // 8 bit signed
    {
      int8_t p1 = read_byte(SA(slot) + addr1);
      int8_t p2 = read_byte(SA(slot) + addr2);
      s32 s;
      s32 fpart = slot->cur_addr & ((1 << SHIFT) - 1);
      s = (int)(p1 << 8) * ((1 << SHIFT) - fpart) + (int)(p2 << 8) * fpart;
      sample = (s >> SHIFT);
    } else // 16 bit signed (endianness?)
    {
      s16 p1 = read_word(SA(slot) + addr1);
      s16 p2 = read_word(SA(slot) + addr2);
      s32 s;
      s32 fpart = slot->cur_addr & ((1 << SHIFT) - 1);
      s = (int)(p1) * ((1 << SHIFT) - fpart) + (int)(p2)*fpart;
      sample = (s >> SHIFT);
    }
  } else if (SSCTL(slot) == 1) // Internally generated data (Noise)
    sample = (s16)((m_lfsr & 0xff)
                   << 8);    // low byte of the LFSR, as Mednafen and Ymir do
  else if (SSCTL(slot) >= 2) // Internally generated data (All 0)
    sample = 0;

  if (SBCTL(slot) & 0x1)
    sample ^= 0x7FFF;
  if (SBCTL(slot) & 0x2)
    sample = (s16)(sample ^ 0x8000);

  if (slot->Backwards)
    slot->cur_addr -= step;
  else
    slot->cur_addr += step;
  slot->nxt_addr = slot->cur_addr + (1 << SHIFT);

  addr1 = slot->cur_addr >> SHIFT;
  addr2 = slot->nxt_addr >> SHIFT;

  if (addr1 >= LSA(slot) && !(slot->Backwards)) {
    if (LPSLNK(slot) && slot->EG.state == SCSP_ATTACK)
      slot->EG.state = SCSP_DECAY1;
  }

  for (addr_select = 0; addr_select < 2; addr_select++) {
    s32 rem_addr;
    switch (LPCTL(slot)) {
    case 0: // no loop
      if (*addr[addr_select] >= LSA(slot) && *addr[addr_select] >= LEA(slot)) {
        // slot->active=0;
        StopSlot(slot, 0);
      }
      break;
    case 1: // normal loop
      if (*addr[addr_select] >= LEA(slot)) {
        rem_addr = *slot_addr[addr_select] - (LEA(slot) << SHIFT);
        *slot_addr[addr_select] = (LSA(slot) << SHIFT) + rem_addr;
      }
      break;
    case 2: // reverse loop
      if ((*addr[addr_select] >= LSA(slot)) && !(slot->Backwards)) {
        rem_addr = *slot_addr[addr_select] - (LSA(slot) << SHIFT);
        *slot_addr[addr_select] = (LEA(slot) << SHIFT) - rem_addr;
        slot->Backwards = 1;
      } else if ((*addr[addr_select] < LSA(slot) ||
                  (*slot_addr[addr_select] & 0x80000000)) &&
                 slot->Backwards) {
        rem_addr = (LSA(slot) << SHIFT) - *slot_addr[addr_select];
        *slot_addr[addr_select] = (LEA(slot) << SHIFT) - rem_addr;
      }
      break;
    case 3:                                // ping-pong
      if (*addr[addr_select] >= LEA(slot)) // reached end, reverse till start
      {
        rem_addr = *slot_addr[addr_select] - (LEA(slot) << SHIFT);
        *slot_addr[addr_select] = (LEA(slot) << SHIFT) - rem_addr;
        slot->Backwards = 1;
      } else if ((*addr[addr_select] < LSA(slot) ||
                  (*slot_addr[addr_select] & 0x80000000)) &&
                 slot->Backwards) // reached start or negative
      {
        rem_addr = (LSA(slot) << SHIFT) - *slot_addr[addr_select];
        *slot_addr[addr_select] = (LSA(slot) << SHIFT) + rem_addr;
        slot->Backwards = 0;
      }
      break;
    }
  }

  if (!SDIR(slot)) {
    if (ALFOS(slot) != 0) {
      sample = sample * ALFO_Step(&(slot->ALFO));
      sample >>= SHIFT;
    }

    sample =
        (sample * m_EG_TABLE[EG_Update(slot, m_eg_clock) >> (SHIFT - 10)]) >>
        SHIFT;
  }

  if (!STWINH(slot)) {
    if (!SDIR(slot)) {
      u16 Enc = ((TL(slot)) << 0x0) | (0x7 << 0xd);
      *m_RBUFDST = (sample * m_LPANTABLE[Enc]) >> (SHIFT + 1);
    } else {
      u16 Enc = (0 << 0x0) | (0x7 << 0xd);
      *m_RBUFDST = (sample * m_LPANTABLE[Enc]) >> (SHIFT + 1);
    }
  }

  return sample;
}

void scsp_device::DoMasterSamples(sound_stream &stream) {
  for (int s = 0; s < stream.samples(); ++s) {
    s32 smpl = 0, smpr = 0;

    // the envelope engine is clocked by the global sample counter: its
    // phase gates (counter_shift / 8-phase increment patterns) advance
    // only on samples whose low counter bits are zero
    ++m_eg_clock;

    // The DSP runs first and consumes the MIXS values written by the slots
    // during the *previous* sample: the chip interleaves slot processing and
    // DSP steps inside one sample period, so the effect input of a given
    // slot is only visible to the DSP one sample later.
    // Step() also zeroes MIXS, leaving a clean accumulator for the slots.
    m_DSP.Step();

    for (int i = 0; i < 16; ++i) {
      SCSP_SLOT *slot = m_Slots + i;
      if (EFSDL(slot)) {
        u16 Enc = ((EFPAN(slot)) << 0x8) | ((EFSDL(slot)) << 0xd);
        smpl += (m_DSP.EFREG[i] * m_LPANTABLE[Enc]) >> SHIFT;
        smpr += (m_DSP.EFREG[i] * m_RPANTABLE[Enc]) >> SHIFT;
      }
    }

    for (int i = 0; i < 2; ++i) {
      SCSP_SLOT *slot =
          m_Slots + i + 16; // 100217, 100237 EFSDL, EFPAN for EXTS0/1
      // !EFSDL case testable in saturn Multiplayer with Audio CD with default
      // values.
      u16 Enc = EFSDL(slot) ? ((EFPAN(slot)) << 0x8) | ((EFSDL(slot)) << 0xd)
                            : (((DIPAN(slot)) << 0x8) | ((DISDL(slot)) << 0xd));
      {
        // EXTS is latched at the end of a sample period on hardware, so
        // the DSP picks it up on the next one
        m_DSP.EXTS[i] = s32(stream.get(i, s) * 32768.0);
        smpl += (m_DSP.EXTS[i] * m_LPANTABLE[Enc]) >> SHIFT;
        smpr += (m_DSP.EXTS[i] * m_RPANTABLE[Enc]) >> SHIFT;
      }
    }

    for (int sl = 0; sl < 32; ++sl) {
#if SCSP_FM_DELAY
      m_RBUFDST = m_DELAYBUF + m_DELAYPTR;
#else
      m_RBUFDST = m_RINGBUF + m_BUFPTR;
#endif
      // the noise generator is a 17-bit LFSR clocked once per slot step,
      // active slot or not (Mednafen and Ymir both clock it per slot)
      m_lfsr = (m_lfsr >> 1) | (((m_lfsr >> 5) ^ m_lfsr) & 1) << 16;

      if (m_Slots[sl].active) {
        SCSP_SLOT *slot = m_Slots + sl;
        u16 Enc;

        s32 sample = UpdateSlot(slot);

        // SDIR ("sound direct") sends the raw sample straight to the output,
        // bypassing the envelope generator AND the TL attenuator (the EG/ALFO
        // bypass is handled in UpdateSlot). BOTH downstream mixes -- the DSP
        // input feed here and the direct-output mix below -- must therefore
        // zero TL when SDIR is set, otherwise a slot programmed with SDIR=1 +
        // a large TL is wrongly muted.
        // (Flash Beats keys its SFX with SDIR=1, TL=0xff = -95 dB; in
        // particular its in-game/"Voice" SFX route only through the DSP
        // (DISDL=0, IMXL>0), so without this the effect path is starved to
        // near-silence.)
        u16 eff_tl = SDIR(slot) ? 0 : TL(slot);
        Enc = ((eff_tl) << 0x0) | ((IMXL(slot)) << 0xd);
        m_DSP.SetSample((sample * m_LPANTABLE[Enc]) >> (SHIFT - 2), ISEL(slot),
                        IMXL(slot));
        u16 dir_tl = SDIR(slot) ? 0 : TL(slot);
        Enc =
            ((dir_tl) << 0x0) | ((DIPAN(slot)) << 0x8) | ((DISDL(slot)) << 0xd);
        {
          smpl += (sample * m_LPANTABLE[Enc]) >> SHIFT;
          smpr += (sample * m_RPANTABLE[Enc]) >> SHIFT;
        }
      }

#if SCSP_FM_DELAY
      m_RINGBUF[(m_BUFPTR + 64 - (SCSP_FM_DELAY - 1)) & 63] =
          m_DELAYBUF[(m_DELAYPTR + SCSP_FM_DELAY - (SCSP_FM_DELAY - 1)) %
                     SCSP_FM_DELAY];
#endif
      ++m_BUFPTR;
      m_BUFPTR &= 63;
#if SCSP_FM_DELAY
      ++m_DELAYPTR;
      if (m_DELAYPTR > SCSP_FM_DELAY - 1)
        m_DELAYPTR = 0;
#endif
    }

    // MVOL is a logarithmic attenuator applied to the 18 bit accumulator
    // right before the DAC
    smpl = (std::clamp<s32>(smpl, -131072, 131071) * s32(m_master_volume)) >> 8;
    smpr = (std::clamp<s32>(smpr, -131072, 131071) * s32(m_master_volume)) >> 8;

    if (DAC18B()) {
      stream.put_int_clamp(0, s, smpl, 131072);
      stream.put_int_clamp(1, s, smpr, 131072);
    } else {
      stream.put_int_clamp(0, s, smpl >> 2, 32768);
      stream.put_int_clamp(1, s, smpr >> 2, 32768);
    }
  }
}

/* The DMA controller is not a fixed-rate engine: ST-077 3.2 gives it a
   memory-access priority (below PCM/DSP fetches and DRAM refresh, above both
   CPUs) without specifying a transfer rate, and both Ymir and mednafen run
   the whole transfer as a burst when DEXE is written, so do the same here.
   The wait states DMA imposes on the sound CPU are not modelled.
   darius2j uses this at startup with DGATE enabled. */
void scsp_device::exec_dma() {
  // work from snapshots: a mem->reg transfer can walk into the DMA's own
  // parameter registers (0x12-0x17), and the loop must not have its
  // addresses/count clobbered mid-transfer (mednafen snapshots the same
  // way).  The register-file copies are restored afterwards so the DMA
  // can't overwrite its own parameters; the references disagree here
  // (mednafen leaves the written values behind, Ymir mutates its live
  // parameters mid-transfer) and ST-077 declares DMEA/DRGA/DTLG
  // write-only without describing self-targeting transfers, so there is
  // no documented winner - keep MAME's long-standing behavior
  u16 tmp_dma[3];
  if (!(m_dma.ddir)) {
    for (int i = 0; i < 3; i++)
      tmp_dma[i] = m_udata.data[(0x12 + (i * 2)) / 2];
  }

  u32 mem_addr = m_dma.dmea;
  u32 reg_addr = m_dma.drga;
  u32 length = m_dma.dtlg;
  bool const dir = m_dma.ddir;
  bool const gate = m_dma.dgate;

  /* note: we don't use space.read_word / write_word because it can happen that
   * SH-2 enables the DMA instead of m68k. */
  while (length) {
    if (dir) {
      // reg->mem: the register read still occurs when gated (register
      // reads have side effects, e.g. popping the MIDI input buffer -
      // mednafen observed the same); the gate only forces the stored
      // value to 0
      u16 const tmp = r16(reg_addr);
      this->space().write_word(mem_addr, gate ? 0 : tmp);
    } else {
      u16 const tmp = read_word(mem_addr);
      w16(reg_addr, gate ? 0 : tmp);
    }
    // both addresses always advance and wrap: the memory address stays
    // word-aligned inside the 1 MB sound RAM window, the register
    // address inside the 4 KB register window (as in mednafen/Ymir)
    mem_addr = (mem_addr + 2) & 0xffffe;
    reg_addr = (reg_addr + 2) & 0xffe;
    length -= 2;
  }

  /*Resume the values*/
  if (!(m_dma.ddir)) {
    for (int i = 0; i < 3; i++)
      m_udata.data[(0x12 + (i * 2)) / 2] = tmp_dma[i];
  }

  /* Job done */
  m_udata.data[0x16 / 2] &= ~0x1000;

  /* request a dma end irq, it's a regular interrupt source (bit 4) */
  m_udata.data[0x20 / 2] |= 0x10;
  CheckPendingIRQ();
  MainCheckPendingIRQ(0x10);
}

u16 scsp_device::read(offs_t offset) {
  m_stream->update();
  return r16(offset * 2);
}

void scsp_device::write(offs_t offset, u16 data, u16 mem_mask) {
  m_stream->update();

  u16 tmp = r16(offset * 2);
  COMBINE_DATA(&tmp);
  w16(offset * 2, tmp, mem_mask);
}

void scsp_device::tra_callback() {
  m_midi_out_cb(transmit_register_get_data_bit());
}

void scsp_device::tra_complete() {
  m_MidiOutR++;
  m_MidiOutR &= 31;

  // if buffer not empty, transmit next byte
  if (m_MidiOutR != m_MidiOutW) {
    transmit_register_setup(m_MidiOutStack[m_MidiOutR]);
  } else {
    // the output buffer has drained, request the MIDI out empty interrupt
    // on both the sound CPU (SCIPD) and the main CPU (MCIPD) side
    m_udata.data[0x20 / 2] |= 0x200;
    CheckPendingIRQ();
    MainCheckPendingIRQ(0x200);
  }
}

void scsp_device::rcv_complete() {
  receive_register_extract();
  m_MidiStack[m_MidiW++] = get_received_char();
  m_MidiW &= 31;

  CheckPendingIRQ();
  MainCheckPendingIRQ(0x08);
}

// LFO handling

#define LFIX(v) ((u32)((float)(1 << LFO_SHIFT) * (v)))

// Convert DB to multiply amplitude
#define DB(v) LFIX(powf(10.0f, v / 20.0f))

// Convert cents to step increment
#define CENTS(v) LFIX(powf(2.0f, v / 1200.0f))

static const float LFOFreq[32] = {
    0.17f, 0.19f, 0.23f, 0.27f, 0.34f, 0.39f, 0.45f, 0.55f, 0.68f, 0.78f, 0.92f,
    1.10f, 1.39f, 1.60f, 1.87f, 2.27f, 2.87f, 3.31f, 3.92f, 4.79f, 6.15f, 7.18f,
    8.60f, 10.8f, 14.4f, 17.2f, 21.5f, 28.7f, 43.1f, 57.4f, 86.1f, 172.3f};
static const float ASCALE[8] = {0.0f, 0.4f, 0.8f,  1.5f,
                                3.0f, 6.0f, 12.0f, 24.0f};
static const float PSCALE[8] = {0.0f,  7.0f,   13.5f,  27.0f,
                                55.0f, 112.0f, 230.0f, 494.0f};

void scsp_device::LFO_Init() {
  for (int i = 0; i < 256; ++i) {
    int a, p;
    //      float TL;
    // Saw
    a = 255 - i;
    if (i < 128)
      p = i;
    else
      p = i - 256;
    m_ALFO_SAW[i] = a;
    m_PLFO_SAW[i] = p;

    // Square
    if (i < 128) {
      a = 255;
      p = 127;
    } else {
      a = 0;
      p = -128;
    }
    m_ALFO_SQR[i] = a;
    m_PLFO_SQR[i] = p;

    // Tri
    if (i < 128)
      a = 255 - (i * 2);
    else
      a = (i * 2) - 256;
    if (i < 64)
      p = i * 2;
    else if (i < 128)
      p = 255 - i * 2;
    else if (i < 192)
      p = 256 - i * 2;
    else
      p = i * 2 - 511;
    m_ALFO_TRI[i] = a;
    m_PLFO_TRI[i] = p;

    // the noise waveform is not a table, it comes from the LFSR
  }

  for (int s = 0; s < 8; ++s) {
    float limit = PSCALE[s];
    for (int i = -128; i < 128; ++i) {
      m_PSCALES[s][i + 128] = CENTS(((limit * (float)i) / 128.0f));
    }
    limit = -ASCALE[s];
    for (int i = 0; i < 256; ++i) {
      m_ASCALES[s][i] = DB(((limit * (float)i) / 256.0f));
    }
  }
}

s32 scsp_device::PLFO_Step(SCSP_LFO_t *LFO) {
  int p;
  LFO->phase += LFO->phase_step;
#if LFO_SHIFT != 8
  LFO->phase &= (1 << (LFO_SHIFT + 8)) - 1;
#endif
  p = LFO->noise ? (int)(s8)(m_lfsr & ~1) : LFO->table[LFO->phase >> LFO_SHIFT];
  p = LFO->scale[p + 128];
  return p << (SHIFT - LFO_SHIFT);
}

s32 scsp_device::ALFO_Step(SCSP_LFO_t *LFO) {
  int p;
  LFO->phase += LFO->phase_step;
#if LFO_SHIFT != 8
  LFO->phase &= (1 << (LFO_SHIFT + 8)) - 1;
#endif
  p = LFO->noise ? (int)(u8)(m_lfsr & ~1) : LFO->table[LFO->phase >> LFO_SHIFT];
  p = LFO->scale[p];
  return p << (SHIFT - LFO_SHIFT);
}

void scsp_device::LFO_ComputeStep(SCSP_LFO_t *LFO, u32 LFOF, u32 LFOWS,
                                  u32 LFOS, int ALFO) {
  // steps are per output sample: use the actual stream rate instead of
  // assuming 44100 (ST-V runs the chip slightly faster, and the rate is
  // programmable through the clock)
  float step = (float)LFOFreq[LFOF] * 256.0f / (float)(clock() / SAMPLE_CLOCKS);
  LFO->phase_step = (u32)((float)(1 << LFO_SHIFT) * step);
  if (ALFO) {
    switch (LFOWS) {
    case 0:
      LFO->table = m_ALFO_SAW;
      break;
    case 1:
      LFO->table = m_ALFO_SQR;
      break;
    case 2:
      LFO->table = m_ALFO_TRI;
      break;
    case 3:
      LFO->table = nullptr;
      break; // taken from the LFSR
    }
    LFO->noise = (LFOWS == 3);
    LFO->scale = m_ASCALES[LFOS];
  } else {
    switch (LFOWS) {
    case 0:
      LFO->table = m_PLFO_SAW;
      break;
    case 1:
      LFO->table = m_PLFO_SQR;
      break;
    case 2:
      LFO->table = m_PLFO_TRI;
      break;
    case 3:
      LFO->table = nullptr;
      break; // taken from the LFSR
    }
    LFO->noise = (LFOWS == 3);
    LFO->scale = m_PSCALES[LFOS];
  }
}

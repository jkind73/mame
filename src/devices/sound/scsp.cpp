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

// TODO : Envelope/LFO times are based on 44100Hz case?
#include "scsp.h"
#include "emu.h"


#include <algorithm>

#define SHIFT 12
#define LFO_SHIFT 8
#define FIX(v) ((u32)((float)(1 << SHIFT) * (v)))

#define EG_SHIFT 16

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

// Envelope times in ms
static const double ARTimes[64] = {100000 /*infinity*/,
                                   100000 /*infinity*/,
                                   8100.0,
                                   6900.0,
                                   6000.0,
                                   4800.0,
                                   4000.0,
                                   3400.0,
                                   3000.0,
                                   2400.0,
                                   2000.0,
                                   1700.0,
                                   1500.0,
                                   1200.0,
                                   1000.0,
                                   860.0,
                                   760.0,
                                   600.0,
                                   500.0,
                                   430.0,
                                   380.0,
                                   300.0,
                                   250.0,
                                   220.0,
                                   190.0,
                                   150.0,
                                   130.0,
                                   110.0,
                                   95.0,
                                   76.0,
                                   63.0,
                                   55.0,
                                   47.0,
                                   38.0,
                                   31.0,
                                   27.0,
                                   24.0,
                                   19.0,
                                   15.0,
                                   13.0,
                                   12.0,
                                   9.4,
                                   7.9,
                                   6.8,
                                   6.0,
                                   4.7,
                                   3.8,
                                   3.4,
                                   3.0,
                                   2.4,
                                   2.0,
                                   1.8,
                                   1.6,
                                   1.3,
                                   1.1,
                                   0.93,
                                   0.85,
                                   0.65,
                                   0.53,
                                   0.44,
                                   0.40,
                                   0.35,
                                   0.0,
                                   0.0};
static const double DRTimes[64] = {100000 /*infinity*/,
                                   100000 /*infinity*/,
                                   118200.0,
                                   101300.0,
                                   88600.0,
                                   70900.0,
                                   59100.0,
                                   50700.0,
                                   44300.0,
                                   35500.0,
                                   29600.0,
                                   25300.0,
                                   22200.0,
                                   17700.0,
                                   14800.0,
                                   12700.0,
                                   11100.0,
                                   8900.0,
                                   7400.0,
                                   6300.0,
                                   5500.0,
                                   4400.0,
                                   3700.0,
                                   3200.0,
                                   2800.0,
                                   2200.0,
                                   1800.0,
                                   1600.0,
                                   1400.0,
                                   1100.0,
                                   920.0,
                                   790.0,
                                   690.0,
                                   550.0,
                                   460.0,
                                   390.0,
                                   340.0,
                                   270.0,
                                   230.0,
                                   200.0,
                                   170.0,
                                   140.0,
                                   110.0,
                                   98.0,
                                   85.0,
                                   68.0,
                                   57.0,
                                   49.0,
                                   43.0,
                                   34.0,
                                   28.0,
                                   25.0,
                                   22.0,
                                   18.0,
                                   14.0,
                                   12.0,
                                   11.0,
                                   8.5,
                                   7.1,
                                   6.1,
                                   5.4,
                                   4.3,
                                   3.6,
                                   3.1};

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

/* TODO */
// #define dma_transfer_end  ((scsp_regs[0x24/2] & 0x10) >> 4) |
// (((scsp_regs[0x26/2] & 0x10) >> 4) << 1) | (((scsp_regs[0x28/2] & 0x10) >> 4)
// << 2)

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
      m_RBUFDST(nullptr) {
  std::fill(std::begin(m_RINGBUF), std::end(m_RINGBUF), 0);
  std::fill(std::begin(m_MidiStack), std::end(m_MidiStack), 0);
  std::fill(std::begin(m_MidiOutStack), std::end(m_MidiOutStack), 0);
  std::fill(std::begin(m_LPANTABLE), std::end(m_LPANTABLE), 0);
  std::fill(std::begin(m_RPANTABLE), std::end(m_RPANTABLE), 0);
  std::fill(std::begin(m_ARTABLE), std::end(m_ARTABLE), 0);
  std::fill(std::begin(m_DRTABLE), std::end(m_DRTABLE), 0);
  std::fill(std::begin(m_EG_TABLE), std::end(m_EG_TABLE), 0);
  std::fill(std::begin(m_PLFO_TRI), std::end(m_PLFO_TRI), 0);
  std::fill(std::begin(m_PLFO_SQR), std::end(m_PLFO_SQR), 0);
  std::fill(std::begin(m_PLFO_SAW), std::end(m_PLFO_SAW), 0);
  std::fill(std::begin(m_PLFO_NOI), std::end(m_PLFO_NOI), 0);
  std::fill(std::begin(m_ALFO_TRI), std::end(m_ALFO_TRI), 0);
  std::fill(std::begin(m_ALFO_SQR), std::end(m_ALFO_SQR), 0);
  std::fill(std::begin(m_ALFO_SAW), std::end(m_ALFO_SAW), 0);
  std::fill(std::begin(m_ALFO_NOI), std::end(m_ALFO_NOI), 0);
  std::fill(std::begin(m_ALFO_NOI), std::end(m_ALFO_NOI), 0);
  memset(m_PSCALES, 0, sizeof(m_PSCALES));
  memset(m_ASCALES, 0, sizeof(m_ASCALES));
  memset(&m_Slots, 0, sizeof(m_Slots));
  memset(&m_udata.data, 0, sizeof(m_udata.data));
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void scsp_device::device_start() {
  // init the emulation
  init();

  // Stereo output with EXTS0,1 Input (External digital audio output)
  m_stream = stream_alloc(2, 2, clock() / 512);

  for (int slot = 0; slot < 32; slot++) {
    for (int i = 0; i < 0x10; i++)
      save_item(NAME(m_Slots[slot].udata.data[i]), (i << 8) | slot);

    save_item(NAME(m_Slots[slot].Backwards), slot);
    save_item(NAME(m_Slots[slot].active), slot);
    save_item(NAME(m_Slots[slot].cur_addr), slot);
    save_item(NAME(m_Slots[slot].nxt_addr), slot);
    save_item(NAME(m_Slots[slot].step), slot);
    save_item(NAME(m_Slots[slot].EG.volume), slot);
    save_item(NAME(m_Slots[slot].EG.step), slot);
    save_item(NAME(m_Slots[slot].EG.AR), slot);
    save_item(NAME(m_Slots[slot].EG.D1R), slot);
    save_item(NAME(m_Slots[slot].EG.D2R), slot);
    save_item(NAME(m_Slots[slot].EG.RR), slot);
    save_item(NAME(m_Slots[slot].EG.DL), slot);
    save_item(NAME(m_Slots[slot].EG.EGHOLD), slot);
    save_item(NAME(m_Slots[slot].EG.LPLINK), slot);
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

  save_item(NAME(m_DSP.RBP));
  save_item(NAME(m_DSP.RBL));
  save_item(NAME(m_DSP.COEF));
  save_item(NAME(m_DSP.MADRS));
  save_item(NAME(m_DSP.MPRO));
  save_item(NAME(m_DSP.TEMP));
  save_item(NAME(m_DSP.MEMS));
  save_item(NAME(m_DSP.DEC));
  save_item(NAME(m_DSP.MIXS));
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
  m_stream->set_sample_rate(clock() / 512);
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
  u32 EG = (0x1f - (slot->EG.volume >> (EG_SHIFT + 5))) & 0x1f;
  // NOTE: according to the manual MSLC is write only, CA, SGC and EG read only.
  // saturn:toughtrk will hang on Human logo otherwise
  m_latched_MSLC_data = /*(MSLC << 11) |*/ (CA << 7) | (SGC << 5) | EG;

  // TODO: 1 sample (1Fs) 44.1 kHz irq here.
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
    if (lv1)

    {
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

  if (m_mcipd & m_mcieb)
    m_main_irq_cb(1);
  else
    m_main_irq_cb(0);
}

void scsp_device::ResetInterrupts() {
  // SCIRE drops the requested bits, the sound CPU level is recomputed from
  // whatever is still pending afterwards
  m_udata.data[0x20 / 2] &= ~m_udata.data[0x22 / 2];

  CheckPendingIRQ();
}

// One output sample (1Fs) is 512 SCSP clocks wide
static constexpr u32 SAMPLE_CLOCKS = 512;

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

int scsp_device::Get_AR(int base, int R) {
  int Rate = base + (R << 1);
  return m_ARTABLE[std::clamp(Rate, 0, 63)];
}

int scsp_device::Get_DR(int base, int R) {
  int Rate = base + (R << 1);
  return m_DRTABLE[std::clamp(Rate, 0, 63)];
}

void scsp_device::Compute_EG(SCSP_SLOT *slot) {
  int octave = (OCT(slot) ^ 8) - 8;
  int rate;
  if (KRS(slot) != 0xf)
    rate = octave + 2 * KRS(slot) + ((FNS(slot) >> 9) & 1);
  else
    rate = 0; // rate = ((FNS(slot) >> 9) & 1);

  slot->EG.volume = 0x17F << EG_SHIFT;
  slot->EG.AR = Get_AR(rate, AR(slot));
  slot->EG.D1R = Get_DR(rate, D1R(slot));
  slot->EG.D2R = Get_DR(rate, D2R(slot));
  slot->EG.RR = Get_DR(rate, RR(slot));
  slot->EG.DL = 0x1f - DL(slot);
  slot->EG.EGHOLD = EGHOLD(slot);
}

int scsp_device::EG_Update(SCSP_SLOT *slot) {
  switch (slot->EG.state) {
  case SCSP_ATTACK:
    slot->EG.volume += slot->EG.AR;
    if (slot->EG.volume >= (0x3ff << EG_SHIFT)) {
      if (!LPSLNK(slot)) {
        slot->EG.state = SCSP_DECAY1;
        if (slot->EG.D1R >=
            (1024 << EG_SHIFT)) // Skip SCSP_DECAY1, go directly to SCSP_DECAY2
          slot->EG.state = SCSP_DECAY2;
      }
      slot->EG.volume = 0x3ff << EG_SHIFT;
    }
    if (slot->EG.EGHOLD)
      return 0x3ff << (SHIFT - 10);
    break;
  case SCSP_DECAY1:
    slot->EG.volume -= slot->EG.D1R;
    if (slot->EG.volume <= 0)
      slot->EG.volume = 0;
    if (slot->EG.volume >> (EG_SHIFT + 5) <= slot->EG.DL)
      slot->EG.state = SCSP_DECAY2;
    break;
  case SCSP_DECAY2:
    if (D2R(slot) == 0)
      return (slot->EG.volume >> EG_SHIFT) << (SHIFT - 10);
    slot->EG.volume -= slot->EG.D2R;
    if (slot->EG.volume <= 0)
      slot->EG.volume = 0;

    break;
  case SCSP_RELEASE:
    slot->EG.volume -= slot->EG.RR;
    if (slot->EG.volume <= 0) {
      slot->EG.volume = 0;
      StopSlot(slot, 0);
      // slot->EG.volume = 0x17F << EG_SHIFT;
      // slot->EG.state = SCSP_ATTACK;
    }
    break;
  default:
    return 1 << SHIFT;
  }
  return (slot->EG.volume >> EG_SHIFT) << (SHIFT - 10);
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
  Compute_EG(slot);
  slot->EG.state = SCSP_ATTACK;
  slot->EG.volume = 0x17F << EG_SHIFT;
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

  m_ARTABLE[0] = m_DRTABLE[0] = 0; // Infinite time
  m_ARTABLE[1] = m_DRTABLE[1] = 0; // Infinite time
  for (i = 2; i < 64; ++i) {
    double step, scale;
    double t = ARTimes[i]; // In ms
    if (t != 0.0) {
      step = (1023 * 1000.0) / (44100.0 * t);
      scale = (double)(1 << EG_SHIFT);
      m_ARTABLE[i] = (int)(step * scale);
    } else
      m_ARTABLE[i] = 1024 << EG_SHIFT;

    t = DRTimes[i]; // In ms
    step = (1023 * 1000.0) / (44100.0 * t);
    scale = (double)(1 << EG_SHIFT);
    m_DRTABLE[i] = (int)(step * scale);
  }

  // make sure all the slots are off
  for (i = 0; i < 32; ++i) {
    m_Slots[i].slot = i;
    m_Slots[i].active = 0;
    m_Slots[i].EG.state = SCSP_RELEASE;
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
  case 0xA:
  case 0xB:
    slot->EG.RR = Get_DR(0, RR(slot));
    slot->EG.DL = 0x1f - DL(slot);
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
    if (!m_irq_cb.isunset()) {
      CheckPendingIRQ();
      // TODO: sample tick (bit 10), MIDI out empty (bit 9) and DMA end (bit 4)
      // interrupts are not fully implemented, log their enablement so that
      // software relying on them can be spotted
      if (m_udata.data[0x1e / 2] & 0x610)
        logerror("%s: SCSP SCIEB enabled %04x\n", machine().describe_context(),
                 m_udata.data[0x1e / 2]);
    }
    break;
  case 0x20: // SCIPD
  case 0x21:
    if (!m_irq_cb.isunset()) {
      if (m_udata.data[0x1e / 2] & m_udata.data[0x20 / 2] & 0x20) {
        // TODO: our use case (arcadegh) still doesn't have sound (but clearly
        // executes irq 7s) log it anyway so we can validate the behaviour with
        // anything else using this
        // - documentation claims 7 to "not use because tied to dev board irq",
        //   that doesn't stop this game using it anyway.
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

    // TODO: external INT0-2, MIDI in/out and sample tick are not routed
    // to the main CPU yet, log their enablement so that software relying
    // on them can be spotted
    if (m_mcieb & ~0x1f0)
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
      CheckPendingIRQ();
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

    // case 0x20:
    //   m_udata.data[0x20/2] ^= 0x400;
    //   break;

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
    sample = (s16)(machine().rand() & 0xffff); // Unknown algorithm
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

    if (slot->EG.state == SCSP_ATTACK)
      sample = (sample * EG_Update(slot)) >> SHIFT;
    else
      sample = (sample * m_EG_TABLE[EG_Update(slot) >> (SHIFT - 10)]) >> SHIFT;
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

// TODO: this needs to be timer-ized
// Very likely this is burst too.
// - darius2j uses this at startup with DGATE enabled
void scsp_device::exec_dma() {
  static u16 tmp_dma[3];
  int i;

  logerror("SCSP: DMA transfer START\n"
           "DMEA: %04x DRGA: %04x DTLG: %04x\n"
           "DGATE: %d  DDIR: %d\n",
           m_dma.dmea, m_dma.drga, m_dma.dtlg, m_dma.dgate ? 1 : 0,
           m_dma.ddir ? 1 : 0);

  /* Copy the dma values in a temp storage for resuming later */
  /* (DMA *can't* overwrite its parameters).                  */
  if (!(m_dma.ddir)) {
    for (i = 0; i < 3; i++)
      tmp_dma[i] = m_udata.data[(0x12 + (i * 2)) / 2];
  }

  /* note: we don't use space.read_word / write_word because it can happen that
   * SH-2 enables the DMA instead of m68k. */
  /* TODO: don't know if params auto-updates, I guess not ... */
  if (m_dma.ddir) {
    if (m_dma.dgate) {
      for (i = 0; i < m_dma.dtlg; i += 2) {
        this->space().write_word(m_dma.dmea, 0);
        m_dma.dmea += 2;
      }
    } else {
      for (i = 0; i < m_dma.dtlg; i += 2) {
        u16 tmp;
        tmp = r16(m_dma.drga);
        this->space().write_word(m_dma.dmea, tmp);
        m_dma.dmea += 2;
        m_dma.drga += 2;
      }
    }
  } else {
    if (m_dma.dgate) {
      for (i = 0; i < m_dma.dtlg; i += 2) {
        w16(m_dma.drga, 0);
        m_dma.drga += 2;
      }
    } else {
      for (i = 0; i < m_dma.dtlg; i += 2) {
        u16 tmp = read_word(m_dma.dmea);
        w16(m_dma.drga, tmp);
        m_dma.dmea += 2;
        m_dma.drga += 2;
      }
    }
  }

  /*Resume the values*/
  if (!(m_dma.ddir)) {
    for (i = 0; i < 3; i++)
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
  }
}

void scsp_device::rcv_complete() {
  receive_register_extract();
  m_MidiStack[m_MidiW++] = get_received_char();
  m_MidiW &= 31;

  CheckPendingIRQ();
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

    // noise
    // a=lfo_noise[i];
    a = machine().rand() & 0xff;
    p = 128 - a;
    m_ALFO_NOI[i] = a;
    m_PLFO_NOI[i] = p;
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
  p = LFO->table[LFO->phase >> LFO_SHIFT];
  p = LFO->scale[p + 128];
  return p << (SHIFT - LFO_SHIFT);
}

s32 scsp_device::ALFO_Step(SCSP_LFO_t *LFO) {
  int p;
  LFO->phase += LFO->phase_step;
#if LFO_SHIFT != 8
  LFO->phase &= (1 << (LFO_SHIFT + 8)) - 1;
#endif
  p = LFO->table[LFO->phase >> LFO_SHIFT];
  p = LFO->scale[p];
  return p << (SHIFT - LFO_SHIFT);
}

void scsp_device::LFO_ComputeStep(SCSP_LFO_t *LFO, u32 LFOF, u32 LFOWS,
                                  u32 LFOS, int ALFO) {
  float step = (float)LFOFreq[LFOF] * 256.0f / 44100.0f;
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
      LFO->table = m_ALFO_NOI;
      break;
    }
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
      LFO->table = m_PLFO_NOI;
      break;
    }
    LFO->scale = m_PSCALES[LFOS];
  }
}

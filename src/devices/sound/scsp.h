// license:BSD-3-Clause
// copyright-holders:ElSemi, R. Belmont
/*
    SCSP (YMF292-F) header
*/

#ifndef MAME_SOUND_SCSP_H
#define MAME_SOUND_SCSP_H

#pragma once

#include "scspdsp.h"

#include "dirom.h"
#include "diserial.h"

#define SCSP_FM_DELAY                                                          \
  0 // delay in number of slots processed before samples are written to the FM
    // ring buffer driver code indicates should be 4, but sounds distorted then

class scsp_device : public device_t,
                    public device_sound_interface,
                    public device_rom_interface<20, 1, 0, ENDIANNESS_BIG>,
                    public device_serial_interface {
public:
  static constexpr feature_type imperfect_features() {
    return feature::SOUND;
  } // DSP / EG incorrections, etc

  scsp_device(const machine_config &mconfig, const char *tag, device_t *owner,
              u32 clock = 22'579'200);

  auto irq_cb() { return m_irq_cb.bind(); }
  auto main_irq_cb() { return m_main_irq_cb.bind(); }
  auto midi_out_cb() { return m_midi_out_cb.bind(); }

  // SCSP register access
  u16 read(offs_t offset);
  void write(offs_t offset, u16 data, u16 mem_mask = ~0);

  // MIDI I/O access (used for comms on Model 2/3)
  void midi_in(int state) { rx_w(state); }

protected:
  // device-level overrides
  virtual void device_start() override ATTR_COLD;
  virtual void device_reset() override ATTR_COLD;
  virtual void device_post_load() override;
  virtual void device_clock_changed() override;

  virtual void rom_bank_pre_change() override;

  // sound stream update overrides
  virtual void sound_stream_update(sound_stream &stream) override;

  // serial interface overrides
  virtual void tra_callback() override;
  virtual void tra_complete() override;
  virtual void rcv_complete() override;

private:
  enum SCSP_STATE : u32 { SCSP_ATTACK, SCSP_DECAY1, SCSP_DECAY2, SCSP_RELEASE };

  struct SCSP_EG_t {
    // attenuation domain like the hardware: 0x000 loudest .. 0x3FF silent
    u32 level;
    // externally visible level of the previous sample; the attack formula
    // and the deactivation test both use it
    u32 prev_level;
    SCSP_STATE state;
    // hardware bug: with key rate scaling active, an attack rate plus the
    // scaled KRS/octave adjustment of 0x20 or more stalls the attack ramp
    bool attack_bug;
  };

  struct SCSP_LFO_t {
    u16 phase;
    u32 phase_step;
    int *table;
    int *scale;
    bool noise; // noise waveform, taken from the LFSR instead of a table
  };

  struct SCSP_SLOT {
    union {
      u16 data[0x10]; // only 0x1a bytes used
      u8 datab[0x20];
    } udata;

    u8 Backwards;    // the wave is playing backwards
    u8 active;       // this slot is currently playing
    u32 cur_addr;    // current play address (24.8)
    u32 nxt_addr;    // next play address
    u32 step;        // pitch step (24.8)
    SCSP_EG_t EG;    // Envelope
    SCSP_LFO_t PLFO; // Phase LFO
    SCSP_LFO_t ALFO; // Amplitude LFO
    int slot;
    s16 Prev; // Previous sample (for interpolation)
  };

  devcb_write8 m_irq_cb; /* irq callback */
  devcb_write_line m_main_irq_cb;
  devcb_write_line m_midi_out_cb;

  union {
    u16 data[0x30 / 2];
    u8 datab[0x30];
  } m_udata;

  SCSP_SLOT m_Slots[32];
  s16 m_RINGBUF[128];
  u8 m_BUFPTR;
#if SCSP_FM_DELAY
  s16 m_DELAYBUF[SCSP_FM_DELAY];
  u8 m_DELAYPTR;
#endif
  sound_stream *m_stream;

  // level currently requested to the sound CPU, 0 when none
  u32 m_current_level;

  u8 m_latched_MSLC;
  u16 m_latched_MSLC_data;
  u8 m_MidiOutStack[32];
  u8 m_MidiOutW, m_MidiOutR;
  u8 m_MidiStack[32];
  u8 m_MidiW, m_MidiR;

  s32 m_EG_TABLE[0x400];

  int m_LPANTABLE[0x10000];
  int m_RPANTABLE[0x10000];

  // Timers A/B/C are plain 8-bit up-counters: they are clocked once every
  // (1 << TxCTL) output samples and request an interrupt every time the
  // counter reaches 0xff, then keep counting (i.e. they are periodic).
  // Writing TIMx doesn't change the counter immediately, it schedules the
  // value to be loaded on the next clock tick.
  struct SCSP_TIMER {
    emu_timer *timer = nullptr;
    attotime base_time; // machine time the current state refers to
    u8 counter = 0;     // 8-bit up counter
    u8 prescale = 0;    // TxCTL, clocked every (1 << prescale) samples
    u8 reload = 0;      // TIMx, loaded into counter on the next tick
    bool reload_pending = false;
  };

  SCSP_TIMER m_timers[3];

  // MVOL derived master volume, Q8 fixed point (0x100 == unity gain)
  u32 m_master_volume;

  // DMA stuff
  struct {
    u32 dmea;
    u16 drga;
    u16 dtlg;
    u8 dgate;
    u8 ddir;
  } m_dma;

  u16 m_mcieb;
  u16 m_mcipd;

  // global EG sample counter: the envelope engine only advances on samples
  // whose low counter bits are zero (rate-dependent), like the hardware
  u64 m_eg_clock;

  SCSPDSP m_DSP;

  s16 *m_RBUFDST; // this points to where the sample will be stored in the
                  // RingBuf

  // LFO
  int m_PLFO_TRI[256], m_PLFO_SQR[256], m_PLFO_SAW[256];
  int m_ALFO_TRI[256], m_ALFO_SQR[256], m_ALFO_SAW[256];
  int m_PSCALES[8][256];
  int m_ASCALES[8][256];

  // noise generator: 17-bit LFSR, clocked once per slot step
  u32 m_lfsr;

  void exec_dma(); /*state DMA transfer function*/
  void reset_irq_timers();
  void CheckPendingIRQ();
  void MainCheckPendingIRQ(u16 irq_type);
  void update_main_irq();
  void ResetInterrupts();
  TIMER_CALLBACK_MEMBER(timer_cb);
  void timer_sync(int idx);
  void timer_arm(int idx);
  void timer_write(int idx, u16 data, u16 mem_mask);
  u8 timer_read(int idx);
  void update_master_volume();
  int EG_Update(SCSP_SLOT *slot, u64 eg_clock);
  void Check_Attack_Bug(SCSP_SLOT *slot);
  u32 Step(SCSP_SLOT *slot);
  void Compute_LFO(SCSP_SLOT *slot);
  void StartSlot(SCSP_SLOT *slot);
  void StopSlot(SCSP_SLOT *slot, int keyoff);
  void init();
  void UpdateSlotReg(int s, int r);
  void UpdateReg(int reg, u16 mem_mask = ~0);
  void UpdateSlotRegR(int slot, int reg);
  void UpdateRegR(int reg);
  void w16(u32 addr, u16 val, u16 mem_mask = ~0);
  u16 r16(u32 addr);
  inline s32 UpdateSlot(SCSP_SLOT *slot);
  void DoMasterSamples(sound_stream &stream);

  // LFO
  void LFO_Init();
  s32 PLFO_Step(SCSP_LFO_t *LFO);
  s32 ALFO_Step(SCSP_LFO_t *LFO);
  void LFO_ComputeStep(SCSP_LFO_t *LFO, u32 LFOF, u32 LFOWS, u32 LFOS,
                       int ALFO);
};

DECLARE_DEVICE_TYPE(SCSP, scsp_device)

#endif // MAME_SOUND_SCSP_H

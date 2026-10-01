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


#define SCSP_FM_DELAY    0    // delay in number of slots processed before samples are written to the FM ring buffer
				// driver code indicates should be 4, but sounds distorted then


class scsp_device : public device_t,
	public device_sound_interface,
	public device_rom_interface<20, 1, 0, ENDIANNESS_BIG>,
	public device_serial_interface
{
public:
	static constexpr feature_type imperfect_features() { return feature::SOUND; } // DSP / EG incorrections, etc

	scsp_device(const machine_config &mconfig, const char *tag, device_t *owner, u32 clock = 22'579'200);

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
	double master_gain() const;
	u16 monitor_slot_data() const;
	virtual void device_clock_changed() override;

	virtual void rom_bank_pre_change() override;

	// sound stream update overrides
	virtual void sound_stream_update(sound_stream &stream) override;

	// serial interface overrides
	virtual void tra_callback() override;
	virtual void tra_complete() override;
	virtual void rcv_complete() override;

private:
	enum SCSP_STATE { SCSP_ATTACK, SCSP_DECAY1, SCSP_DECAY2, SCSP_RELEASE };

	struct SCSP_EG_t
	{
		SCSP_STATE state;
		int att;    // attenuation, 0x000 (loudest) to 0x3ff, 3/32 dB a step
	};

	struct SCSP_LFO_t
	{
		u16 phase;
		u32 phase_step;
		int *table;
		int *scale;
	};

	struct SCSP_SLOT
	{
		union
		{
			u16 data[0x10];  //only 0x1a bytes used
			u8 datab[0x20];
		} udata;

		u8 Backwards;    //the wave is playing backwards
		u8 active;   //this slot is currently playing
		u32 cur_addr;    //current play address (24.8)
		u32 nxt_addr;    //next play address
		u32 step;        //pitch step (24.8)
		SCSP_EG_t EG;            //Envelope
		SCSP_LFO_t PLFO;     //Phase LFO
		SCSP_LFO_t ALFO;     //Amplitude LFO
		int slot;
		s16 Prev;  //Previous sample (for interpolation)
		s32 log_peak;  // SCSP_LOG: loudest direct output of the slot since it was keyed on
	};

	devcb_write8       m_irq_cb;  /* irq callback */
	devcb_write_line   m_main_irq_cb;
	devcb_write_line   m_midi_out_cb;

	union
	{
		u16 data[0x30/2];
		u8 datab[0x30];
	} m_udata;

	SCSP_SLOT m_Slots[32];
	s16 m_RINGBUF[128];
	u8 m_BUFPTR;
#if SCSP_FM_DELAY
	s16 m_DELAYBUF[SCSP_FM_DELAY];
	u8 m_DELAYPTR;
#endif
	sound_stream * m_stream;

	u32 m_IrqTimA;
	u32 m_IrqTimBC;
	u32 m_IrqMidi;
	u32 m_IrqCPU;
	u32 m_IrqDMA;
	u8 m_cur_irq_level;    // level currently asserted to the sound CPU, 0 when none

	u8 m_latched_MSLC;
	u16 m_latched_MSLC_data;
	u8 m_MidiOutStack[32];
	u8 m_MidiOutW, m_MidiOutR;
	u8 m_MidiStack[32];
	u8 m_MidiW, m_MidiR;
	bool m_MidiOverflow;

	s32 m_EG_TABLE[0x400];

	int m_LPANTABLE[0x10000];
	int m_RPANTABLE[0x10000];

	int m_TimPris[3];
	int m_TimCnt[3];

	// timers
	emu_timer *m_timerA, *m_timerB, *m_timerC;
	emu_timer *m_timerS;   // 1 Fs sample interrupt, armed only while it is enabled

	// DMA stuff
	struct
	{
		u32 dmea;
		u16 drga;
		u16 dtlg;
		u8 dgate;
		u8 ddir;
	} m_dma;

	u16 m_mcieb;
	u16 m_mcipd;

	u32 m_eg_counter;    // envelope generator sample counter
	u32 m_lfsr;          // noise generator, 17 bit LFSR advanced once per slot
	s32 m_log_peak[2];   // SCSP_LOG: output peak of the last second
	u32 m_log_count;
	s32 m_log_exts_peak; // SCSP_LOG: peak of the external (CD audio) input of the last second

	SCSPDSP m_DSP;

	s16 *m_RBUFDST;   //this points to where the sample will be stored in the RingBuf

	//LFO
	int m_PLFO_TRI[256], m_PLFO_SQR[256], m_PLFO_SAW[256], m_PLFO_NOI[256];
	int m_ALFO_TRI[256], m_ALFO_SQR[256], m_ALFO_SAW[256], m_ALFO_NOI[256];
	int m_PSCALES[8][256];
	int m_ASCALES[8][256];

	void exec_dma();       /*state DMA transfer function*/
	u8 DecodeSCI(u8 irq);
	void CheckPendingIRQ();
	void SetPending(u16 mask);
	void StartTimer(int n);
	void TimerExpired(int n);
	void UpdateSampleTimer();
	void MainCheckPendingIRQ(u16 irq_type);
	void ResetInterrupts();
	TIMER_CALLBACK_MEMBER(timerA_cb);
	TIMER_CALLBACK_MEMBER(timerB_cb);
	TIMER_CALLBACK_MEMBER(timerC_cb);
	TIMER_CALLBACK_MEMBER(timerS_cb);
	unsigned EG_EffectiveRate(SCSP_SLOT *slot, unsigned rate, bool &overflow);
	int EG_Update(SCSP_SLOT *slot);
	u32 Step(SCSP_SLOT *slot);
	void Compute_LFO(SCSP_SLOT *slot);
	void StartSlot(SCSP_SLOT *slot);
	void StopSlot(SCSP_SLOT *slot, int keyoff);
	void init();
	void UpdateSlotReg(int s, int r);
	void UpdateReg(int reg);
	void UpdateSlotRegR(int slot, int reg);
	void UpdateRegR(int reg);
	void w16(u32 addr, u16 val);
	u16 r16(u32 addr);
	inline s32 UpdateSlot(SCSP_SLOT *slot);
	void DoMasterSamples(sound_stream &stream);

	//LFO
	void LFO_Init();
	s32 PLFO_Step(SCSP_LFO_t *LFO);
	s32 ALFO_Step(SCSP_LFO_t *LFO);
	void LFO_ComputeStep(SCSP_LFO_t *LFO, u32 LFOF, u32 LFOWS, u32 LFOS, int ALFO);
};

DECLARE_DEVICE_TYPE(SCSP, scsp_device)

#endif // MAME_SOUND_SCSP_H

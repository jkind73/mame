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
    * September 24, 2007 (RB+ES) Removed fake reverb.  Rewrote timers and IRQ handling.
                             Fixed case where voice frequency is updated while looping.
                             Enabled DSP again.
    * December 16, 2007  (kingshriek) Many EG bug fixes, implemented effects mixer,
                             implemented FM.
    * January 5, 2008    (kingshriek+RB) Working, good-sounding FM, removed obsolete non-USEDSP code.
    * April 22, 2009     ("PluginNinja") Improved slot monitor, misc cleanups
    * June 6, 2011       (AS) Rewrote DMA from scratch, Darius 2 relies on it.
*/

// TODO : Envelope/LFO times are based on 44100Hz case?
#include "emu.h"
#include "scsp.h"

#include <algorithm>

#define SHIFT   12
#define LFO_SHIFT   8
#define FIX(v)  ((u32) ((float) (1 << SHIFT) * (v)))




/*
    SCSP features 32 programmable slots
    that can generate FM and PCM (from ROM/RAM) sound
*/

//SLOT PARAMETERS
#define KEYONEX(slot)   ((slot->udata.data[0x0] >> 0x0) & 0x1000)
#define KEYONB(slot)    ((slot->udata.data[0x0] >> 0x0) & 0x0800)
#define SBCTL(slot)     ((slot->udata.data[0x0] >> 0x9) & 0x0003)
#define SSCTL(slot)     ((slot->udata.data[0x0] >> 0x7) & 0x0003)
#define LPCTL(slot)     ((slot->udata.data[0x0] >> 0x5) & 0x0003)
#define PCM8B(slot)     ((slot->udata.data[0x0] >> 0x0) & 0x0010)

#define SA(slot)        (((slot->udata.data[0x0] & 0xF) << 16) | (slot->udata.data[0x1]))

#define LSA(slot)       (slot->udata.data[0x2])

#define LEA(slot)       (slot->udata.data[0x3])

#define D2R(slot)       ((slot->udata.data[0x4] >> 0xB) & 0x001F)
#define D1R(slot)       ((slot->udata.data[0x4] >> 0x6) & 0x001F)
#define EGHOLD(slot)    ((slot->udata.data[0x4] >> 0x0) & 0x0020)
#define AR(slot)        ((slot->udata.data[0x4] >> 0x0) & 0x001F)

#define LPSLNK(slot)    ((slot->udata.data[0x5] >> 0x0) & 0x4000)
#define EGBP(slot)      ((slot->udata.data[0x5] >> 0x0) & 0x8000)
#define KRS(slot)       ((slot->udata.data[0x5] >> 0xA) & 0x000F)
#define DL(slot)        ((slot->udata.data[0x5] >> 0x5) & 0x001F)
#define RR(slot)        ((slot->udata.data[0x5] >> 0x0) & 0x001F)

#define STWINH(slot)    ((slot->udata.data[0x6] >> 0x0) & 0x0200)
#define SDIR(slot)      ((slot->udata.data[0x6] >> 0x0) & 0x0100)
#define TL(slot)        ((slot->udata.data[0x6] >> 0x0) & 0x00FF)

#define MDL(slot)       ((slot->udata.data[0x7] >> 0xC) & 0x000F)
#define MDXSL(slot)     ((slot->udata.data[0x7] >> 0x6) & 0x003F)
#define MDYSL(slot)     ((slot->udata.data[0x7] >> 0x0) & 0x003F)

#define OCT(slot)       ((slot->udata.data[0x8] >> 0xB) & 0x000F)
#define FNS(slot)       ((slot->udata.data[0x8] >> 0x0) & 0x03FF)

#define LFORE(slot)     ((slot->udata.data[0x9] >> 0x0) & 0x8000)
#define LFOF(slot)      ((slot->udata.data[0x9] >> 0xA) & 0x001F)
#define PLFOWS(slot)    ((slot->udata.data[0x9] >> 0x8) & 0x0003)
#define PLFOS(slot)     ((slot->udata.data[0x9] >> 0x5) & 0x0007)
#define ALFOWS(slot)    ((slot->udata.data[0x9] >> 0x3) & 0x0003)
#define ALFOS(slot)     ((slot->udata.data[0x9] >> 0x0) & 0x0007)

#define ISEL(slot)      ((slot->udata.data[0xA] >> 0x3) & 0x000F)
#define IMXL(slot)      ((slot->udata.data[0xA] >> 0x0) & 0x0007)

#define DISDL(slot)     ((slot->udata.data[0xB] >> 0xD) & 0x0007)
#define DIPAN(slot)     ((slot->udata.data[0xB] >> 0x8) & 0x001F)
#define EFSDL(slot)     ((slot->udata.data[0xB] >> 0x5) & 0x0007)
#define EFPAN(slot)     ((slot->udata.data[0xB] >> 0x0) & 0x001F)

#define MEM4B()     ((m_udata.data[0] >> 0x0) & 0x0200)
#define DAC18B()    ((m_udata.data[0] >> 0x0) & 0x0100)
#define MVOL()      ((m_udata.data[0] >> 0x0) & 0x000F)
#define RBL()       ((m_udata.data[1] >> 0x7) & 0x0003)
#define RBP()       ((m_udata.data[1] >> 0x0) & 0x003F)
#define MOFULL()    ((m_udata.data[2] >> 0x0) & 0x1000)
#define MOEMPTY()   ((m_udata.data[2] >> 0x0) & 0x0800)
#define MIOVF()     ((m_udata.data[2] >> 0x0) & 0x0400)
#define MIFULL()    ((m_udata.data[2] >> 0x0) & 0x0200)
#define MIEMPTY()   ((m_udata.data[2] >> 0x0) & 0x0100)

#define SCILV0()    ((m_udata.data[0x24/2] >> 0x0) & 0xff)
#define SCILV1()    ((m_udata.data[0x26/2] >> 0x0) & 0xff)
#define SCILV2()    ((m_udata.data[0x28/2] >> 0x0) & 0xff)

#define SCIEX0  0
#define SCIEX1  1
#define SCIEX2  2
#define SCIMID  3
#define SCIDMA  4
#define SCIIRQ  5
#define SCITMA  6
#define SCITMB  7

#define USEDSP

/* TODO */
//#define dma_transfer_end  ((scsp_regs[0x24/2] & 0x10) >> 4) | (((scsp_regs[0x26/2] & 0x10) >> 4) << 1) | (((scsp_regs[0x28/2] & 0x10) >> 4) << 2)

static const float SDLT[8] = {-1000000.0f,-36.0f,-30.0f,-24.0f,-18.0f,-12.0f,-6.0f,0.0f};

DEFINE_DEVICE_TYPE(SCSP, scsp_device, "scsp", "Yamaha YMF292-F SCSP")

scsp_device::scsp_device(const machine_config &mconfig, const char *tag, device_t *owner, u32 clock)
	: device_t(mconfig, SCSP, tag, owner, clock),
		device_sound_interface(mconfig, *this),
		device_rom_interface(mconfig, *this),
		device_serial_interface(mconfig, *this),
		m_irq_cb(*this),
		m_main_irq_cb(*this),
		m_midi_out_cb(*this),
		m_BUFPTR(0),
		m_stream(nullptr),
		m_IrqTimA(0),
		m_IrqTimBC(0),
		m_IrqMidi(0),
		m_MidiOutW(0),
		m_MidiOutR(0),
		m_MidiW(0),
		m_MidiR(0),
		m_timerA(nullptr),
		m_timerB(nullptr),
		m_timerC(nullptr),
		m_mcieb(0),
		m_mcipd(0),
		m_RBUFDST(nullptr)
{
	std::fill(std::begin(m_RINGBUF), std::end(m_RINGBUF), 0);
	std::fill(std::begin(m_MidiStack), std::end(m_MidiStack), 0);
	std::fill(std::begin(m_MidiOutStack), std::end(m_MidiOutStack), 0);
	std::fill(std::begin(m_LPANTABLE), std::end(m_LPANTABLE), 0);
	std::fill(std::begin(m_RPANTABLE), std::end(m_RPANTABLE), 0);
	std::fill(std::begin(m_TimPris), std::end(m_TimPris), 0);
	m_eg_counter = 0;
	m_lfsr = 1;
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
	m_TimCnt[0] = 0;
	m_TimCnt[1] = 0;
	m_TimCnt[2] = 0;
	m_cur_irq_level = 0;
	m_timerS = nullptr;
}

//-------------------------------------------------
//  device_start - device-specific startup
//-------------------------------------------------

void scsp_device::device_start()
{
	// init the emulation
	init();

	// Stereo output with EXTS0,1 Input (External digital audio output)
	m_stream = stream_alloc(2, 2, clock() / 512);

	for (int slot = 0; slot < 32; slot++)
	{
		for (int i = 0; i < 0x10; i++)
			save_item(NAME(m_Slots[slot].udata.data[i]), (i << 8) | slot);

		save_item(NAME(m_Slots[slot].Backwards), slot);
		save_item(NAME(m_Slots[slot].active), slot);
		save_item(NAME(m_Slots[slot].cur_addr), slot);
		save_item(NAME(m_Slots[slot].nxt_addr), slot);
		save_item(NAME(m_Slots[slot].step), slot);
		save_item(NAME(m_Slots[slot].EG.att), slot);
		save_item(NAME(m_Slots[slot].PLFO.phase), slot);
		save_item(NAME(m_Slots[slot].PLFO.phase_step), slot);
		save_item(NAME(m_Slots[slot].ALFO.phase), slot);
		save_item(NAME(m_Slots[slot].ALFO.phase_step), slot);
	}

	for (int i = 0; i < 0x30/2; i++)
	{
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

	save_item(NAME(m_IrqTimA));
	save_item(NAME(m_IrqTimBC));
	save_item(NAME(m_IrqMidi));
	save_item(NAME(m_IrqCPU));
	save_item(NAME(m_IrqDMA));
	save_item(NAME(m_cur_irq_level));

	save_item(NAME(m_MidiOutStack));
	save_item(NAME(m_MidiOutW));
	save_item(NAME(m_MidiOutR));
	save_item(NAME(m_MidiStack));
	save_item(NAME(m_MidiW));
	save_item(NAME(m_MidiR));

	save_item(NAME(m_TimPris));
	save_item(NAME(m_TimCnt));
	save_item(NAME(m_eg_counter));
	save_item(NAME(m_lfsr));

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

void scsp_device::device_reset()
{
	set_data_frame(1, 8, PARITY_NONE, STOP_BITS_1);
	set_rate(31250);
}

//-------------------------------------------------
//  device_post_load - called after loading a saved state
//-------------------------------------------------

void scsp_device::device_post_load()
{
	for (int slot = 0; slot < 32; slot++)
		Compute_LFO(&m_Slots[slot]);

	set_output_gain(0, MVOL() / 15.0);
	set_output_gain(1, MVOL() / 15.0);
}

//-------------------------------------------------
//  device_clock_changed - called if the clock
//  changes
//-------------------------------------------------

void scsp_device::device_clock_changed()
{
	m_stream->set_sample_rate(clock() / 512);
}

void scsp_device::rom_bank_pre_change()
{
	m_stream->update();
}

//-------------------------------------------------
//  sound_stream_update - handle a stream update
//-------------------------------------------------

void scsp_device::sound_stream_update(sound_stream &stream)
{
	DoMasterSamples(stream);

	// MSLC     |  CA   |SGC|EG
	// f e d c b a 9 8 7 6 5 4 3 2 1 0

	// latch the new MSLC, updates every 44.1 kHz
	// cfr. vstriker (GK reflecting ball with heavy shots) and srallyc (PowerGames BGM bleeps at end)
	u8 MSLC = m_latched_MSLC;
	SCSP_SLOT *slot = m_Slots + MSLC;
	u32 SGC = (slot->EG.state) & 3;
	u32 CA = (slot->cur_addr >> (SHIFT + 12)) & 0xf;
	u32 EG = (slot->EG.att >> 5) & 0x1f;
	// NOTE: according to the manual MSLC is write only, CA, SGC and EG read only.
	// saturn:toughtrk will hang on Human logo otherwise
	m_latched_MSLC_data =  /*(MSLC << 11) |*/ (CA << 7) | (SGC << 5) | EG;
}

u8 scsp_device::DecodeSCI(u8 irq)
{
	u8 SCI = 0;
	u8 v;
	v = (SCILV0() & (1 << irq)) ? 1 : 0;
	SCI |= v;
	v = (SCILV1() & (1 << irq)) ? 1 : 0;
	SCI |= v << 1;
	v = (SCILV2() & (1 << irq)) ? 1 : 0;
	SCI |= v << 2;
	return SCI;
}

// Sound CPU interrupt. Every source that is pending and enabled asks for its own level
// (SCILV0-2) and the CPU sees the highest one (ST-77 4.2 Interrupt Control Register).
// Timer B, timer C, MIDI out and the 1 Fs interrupt share the level bits of bit 7.
void scsp_device::CheckPendingIRQ()
{
	u32 pend = m_udata.data[0x20/2];
	u32 const en = m_udata.data[0x1e/2];
	if (m_MidiW != m_MidiR)
	{
		m_udata.data[0x20/2] |= 8;
		pend |= 8;
	}

	u32 const active = pend & en;
	u32 level = 0;
	if (active & 0x008) level = std::max(level, m_IrqMidi);   // MIDI in
	if (active & 0x010) level = std::max(level, m_IrqDMA);    // DMA transfer end
	if (active & 0x020) level = std::max(level, m_IrqCPU);    // CPU interrupt
	if (active & 0x040) level = std::max(level, m_IrqTimA);   // timer A
	if (active & 0x780) level = std::max(level, m_IrqTimBC);  // timer B, C, MIDI out, 1 Fs

	if (level != m_cur_irq_level)
	{
		// lower the line that was asserted by its own level: not every driver tracks the last one
		if (m_cur_irq_level)
			m_irq_cb((offs_t)m_cur_irq_level, CLEAR_LINE);
		m_cur_irq_level = level;
		if (level)
			m_irq_cb((offs_t)level, ASSERT_LINE);
	}
}

// Interrupt to the main CPU (SCU): pending flags are always kept, the enable register decides
// whether the SCU is told (MCIEB)
void scsp_device::MainCheckPendingIRQ(u16 irq_type)
{
	m_mcipd |= irq_type;

	//machine().scheduler().synchronize(); // force resync

	if (m_mcipd & m_mcieb)
		m_main_irq_cb(1);
	else
		m_main_irq_cb(0);
}

// An interrupt source fires: it is pending for both CPUs, each of them has its own enable
// and level (ST-77: "all interrupts that can be applied to the sound CPU can be used as
// interrupts for the main CPU")
void scsp_device::SetPending(u16 mask)
{
	m_udata.data[0x20/2] |= mask;
	CheckPendingIRQ();
	MainCheckPendingIRQ(mask);
}

void scsp_device::ResetInterrupts()
{
	// the pending flags were cleared by SCIRE, drop the lines that have nothing left
	CheckPendingIRQ();
}

// The timers are free running 8 bit up counters: the first overflow comes (255 - TIM) count
// cycles after the write (ST-77 Timer Register), then every 256 cycles. A count cycle is
// 1, 2, 4 ... 128 samples (TxCTL). MiSTer SCSP.sv and Ymir scsp_timer.hpp do the same.
void scsp_device::StartTimer(int n)
{
	static constexpr int regs[3] = { 0x18, 0x1a, 0x1c };
	u16 const reg = m_udata.data[regs[n] / 2];
	m_TimPris[n] = 1 << ((reg >> 8) & 0x7);
	m_TimCnt[n] = (reg & 0xff) << 8;

	emu_timer *const timer = n == 0 ? m_timerA : n == 1 ? m_timerB : m_timerC;
	attotime const cycle = attotime::from_ticks(512 * u64(m_TimPris[n]), clock());
	timer->adjust(cycle * std::max(1, 255 - int(reg & 0xff)));
}

void scsp_device::TimerExpired(int n)
{
	static constexpr int regs[3] = { 0x18, 0x1a, 0x1c };
	emu_timer *const timer = n == 0 ? m_timerA : n == 1 ? m_timerB : m_timerC;

	// keeps counting from 0: next overflow after 256 count cycles
	timer->adjust(attotime::from_ticks(512 * u64(256) * u64(m_TimPris[n]), clock()));

	m_TimCnt[n] = 0xFFFF;
	m_udata.data[regs[n] / 2] = (m_udata.data[regs[n] / 2] & 0xff00) | 0xff;
	SetPending(0x40 << n);
}

TIMER_CALLBACK_MEMBER(scsp_device::timerA_cb)
{
	TimerExpired(0);
}

TIMER_CALLBACK_MEMBER(scsp_device::timerB_cb)
{
	TimerExpired(1);
}

TIMER_CALLBACK_MEMBER(scsp_device::timerC_cb)
{
	TimerExpired(2);
}

// 1 Fs interrupt, once per sample. Only generated while one of the CPUs has it enabled
// (running it all the time would cost a timer event per sample for everything using the chip).
void scsp_device::UpdateSampleTimer()
{
	if ((m_udata.data[0x1e/2] | m_mcieb) & 0x400)
	{
		attotime const sample = attotime::from_ticks(512, clock());
		m_timerS->adjust(sample, 0, sample);
	}
	else
		m_timerS->adjust(attotime::never);
}

TIMER_CALLBACK_MEMBER(scsp_device::timerS_cb)
{
	SetPending(0x400);
}

// Envelope generator. ST-77 (4.2, EG registers) describes the four states and what the rate,
// decay level, key rate scaling and hold bits do, but gives no rates. They are those of MiSTer's
// SCSP.sv and Ymir's scsp_slot.hpp, which agree: the EG is a 10 bit attenuation (0 loudest) and
// each sample a counter decides whether it steps. The effective rate is the register rate plus the
// key rate scaling (KRS + octave, clamped to 0-15, none when KRS = 15), doubled; it picks how often
// (every 2^n samples, n = 12 down to 1) and by how much (a pattern of 0-8) the level moves.
// Attack is exponential (att -= (att + 1) * step / 16), the decays and the release are linear.
unsigned scsp_device::EG_EffectiveRate(SCSP_SLOT *slot, unsigned rate, bool &overflow)
{
	unsigned eff = rate;
	if (KRS(slot) != 0xf)
	{
		int const oct = (OCT(slot) ^ 8) - 8;
		eff += std::clamp<int>(KRS(slot) + oct, 0, 15);
	}
	overflow = eff >= 0x20;   // the attack does not run: it starts at, and stays at, full level
	return std::min<unsigned>(eff << 1, 63);
}

static unsigned eg_step(unsigned rate2, u32 counter)
{
	if (rate2 < 2)
		return 0;
	unsigned const shift = rate2 < 44 ? 12 - (rate2 >> 2) : 1;
	if (counter & ((1U << shift) - 1))
		return 0;
	unsigned const phase = (counter >> shift) & 7;
	if (rate2 < 48)
	{
		static constexpr u8 pattern[4][8] = {
			{ 0, 1, 0, 1, 0, 1, 0, 1 }, { 0, 1, 0, 1, 1, 1, 0, 1 }, { 0, 1, 1, 1, 0, 1, 1, 1 }, { 0, 1, 1, 1, 1, 1, 1, 1 } };
		return pattern[rate2 & 3][phase];
	}
	if (rate2 >= 60)
		return 8;
	static constexpr u8 fast[4][8] = {
		{ 1, 1, 1, 1, 1, 1, 1, 1 }, { 1, 1, 1, 2, 1, 1, 1, 2 }, { 2, 1, 2, 1, 2, 1, 2, 1 }, { 1, 2, 2, 2, 1, 2, 2, 2 } };
	return fast[rate2 & 3][phase] << ((rate2 - 48) >> 2);
}

// Steps the envelope of a slot for one sample and returns the volume index (0x3ff is no attenuation)
int scsp_device::EG_Update(SCSP_SLOT *slot)
{
	SCSP_EG_t &eg = slot->EG;
	int const prev = eg.att;
	bool overflow;
	unsigned rate;
	switch (eg.state)
	{
		case SCSP_ATTACK:  rate = AR(slot);  break;
		case SCSP_DECAY1:  rate = D1R(slot); break;
		case SCSP_DECAY2:  rate = D2R(slot); break;
		default:           rate = RR(slot);  break;
	}
	unsigned const step = rate ? eg_step(EG_EffectiveRate(slot, rate, overflow), m_eg_counter) : 0;
	(void)overflow;

	// what this sample is played at: the hold mode keeps the attack at full level, the bypass has no envelope
	int const level = (EGBP(slot) || (eg.state == SCSP_ATTACK && EGHOLD(slot))) ? 0 : prev;

	switch (eg.state)
	{
		case SCSP_ATTACK:
		{
			bool ovr;
			EG_EffectiveRate(slot, rate, ovr);
			if (!ovr && step && prev > 0)
				eg.att = std::max(prev + ((-(prev + 1) * int(step)) >> 4), 0);
			if (!LPSLNK(slot) && prev == 0)
				eg.state = SCSP_DECAY1;   // with the loop start link the loop start decides (UpdateSlot)
			break;
		}
		case SCSP_DECAY1:
			if ((prev >> 5) == (int)DL(slot))
				eg.state = SCSP_DECAY2;
			[[fallthrough]];
		default:
			if (step)
				eg.att = std::min(prev + int(step), 0x3ff);
			break;
	}

	// a silent slot is switched off
	if (prev >= 0x3c0 && !EGBP(slot))
		StopSlot(slot, 0);

	return 0x3ff - level;
}

u32 scsp_device::Step(SCSP_SLOT *slot)
{
	int octave = (OCT(slot) ^ 8) - 8 + SHIFT - 10;
	u32 Fn = FNS(slot) + (1 << 10);
	if (octave >= 0)
	{
		Fn <<= octave;
	}
	else
	{
		Fn >>= -octave;
	}

	return Fn;
}


void scsp_device::Compute_LFO(SCSP_SLOT *slot)
{
	if (PLFOS(slot) != 0)
		LFO_ComputeStep(&(slot->PLFO), LFOF(slot), PLFOWS(slot), PLFOS(slot), 0);
	if (ALFOS(slot) != 0)
		LFO_ComputeStep(&(slot->ALFO), LFOF(slot), ALFOWS(slot), ALFOS(slot), 1);
}

void scsp_device::StartSlot(SCSP_SLOT *slot)
{
	slot->active = 1;
	slot->cur_addr = 0;
	slot->nxt_addr = 1 << SHIFT;
	slot->step = Step(slot);
	slot->EG.state = SCSP_ATTACK;
	{
		bool overflow;
		EG_EffectiveRate(slot, AR(slot), overflow);
		slot->EG.att = overflow ? 0x000 : 0x280;
	}
	slot->Prev = 0;
	slot->Backwards = 0;

	Compute_LFO(slot);

//  printf("StartSlot[%p]: SA %x PCM8B %x LPCTL %x ALFOS %x STWINH %x TL %x EFSDL %x\n", slot, SA(slot), PCM8B(slot), LPCTL(slot), ALFOS(slot), STWINH(slot), TL(slot), EFSDL(slot));
}

void scsp_device::StopSlot(SCSP_SLOT *slot,int keyoff)
{
	if (keyoff /*&& slot->EG.state!=SCSP_RELEASE*/)
	{
		slot->EG.state = SCSP_RELEASE;
	}
	else
	{
		slot->active = 0;
	}
	slot->udata.data[0] &= ~0x800;
}

void scsp_device::init()
{
	int i;

	m_DSP.Init();

	m_IrqTimA = m_IrqTimBC = m_IrqMidi = m_IrqCPU = m_IrqDMA = 0;
	m_MidiR = m_MidiW = 0;
	m_MidiOutR = m_MidiOutW = 0;

	m_DSP.space = &this->space();
	m_timerA = timer_alloc(FUNC(scsp_device::timerA_cb), this);
	m_timerB = timer_alloc(FUNC(scsp_device::timerB_cb), this);
	m_timerC = timer_alloc(FUNC(scsp_device::timerC_cb), this);
	m_timerS = timer_alloc(FUNC(scsp_device::timerS_cb), this);
	m_cur_irq_level = 0;

	for (i = 0; i < 0x400; ++i)
	{
		float envDB = ((float)(3 * (i - 0x3ff))) / 32.0f;
		float scale = (float)(1 << SHIFT);
		m_EG_TABLE[i] = (s32)(powf(10.0f, envDB / 20.0f) * scale);
	}

	for (i = 0; i < 0x10000; ++i)
	{
		int iTL  = (i >> 0x0) & 0xff;
		int iPAN = (i >> 0x8) & 0x1f;
		int iSDL = (i >> 0xD) & 0x07;
		float TL;
		float SegaDB = 0.0f;
		float fSDL;
		float PAN;
		float LPAN,RPAN;

		if (iTL & 0x01) SegaDB -= 0.4f;
		if (iTL & 0x02) SegaDB -= 0.8f;
		if (iTL & 0x04) SegaDB -= 1.5f;
		if (iTL & 0x08) SegaDB -= 3.0f;
		if (iTL & 0x10) SegaDB -= 6.0f;
		if (iTL & 0x20) SegaDB -= 12.0f;
		if (iTL & 0x40) SegaDB -= 24.0f;
		if (iTL & 0x80) SegaDB -= 48.0f;

		TL=powf(10.0f, SegaDB / 20.0f);

		SegaDB=0;
		if (iPAN & 0x1) SegaDB -= 3.0f;
		if (iPAN & 0x2) SegaDB -= 6.0f;
		if (iPAN & 0x4) SegaDB -= 12.0f;
		if (iPAN & 0x8) SegaDB -= 24.0f;

		if ((iPAN & 0xf) == 0xf) PAN = 0.0;
		else PAN=powf(10.0f, SegaDB / 20.0f);

		if (iPAN < 0x10)
		{
			LPAN = PAN;
			RPAN = 1.0;
		}
		else
		{
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

	// make sure all the slots are off
	for (i = 0; i < 32; ++i)
	{
		m_Slots[i].slot = i;
		m_Slots[i].active = 0;
		m_Slots[i].EG.state = SCSP_RELEASE;
		m_Slots[i].EG.att = 0x3ff;
	}

	LFO_Init();
	// no "pend"
	m_udata.data[0x20/2] = 0;
	m_TimCnt[0] = 0xffff;
	m_TimCnt[1] = 0xffff;
	m_TimCnt[2] = 0xffff;
}

void scsp_device::UpdateSlotReg(int s,int r)
{
	SCSP_SLOT *slot = m_Slots + s;
	switch (r & 0x3f)
	{
		case 0:
		case 1:
			if (KEYONEX(slot))
			{
				for (int sl=0; sl < 32; ++sl)
				{
					SCSP_SLOT *s2 = m_Slots + sl;
					{
						if (KEYONB(s2) && s2->EG.state == SCSP_RELEASE/*&& !s2->active*/)
						{
							StartSlot(s2);
						}
						if (!KEYONB(s2) /*&& s2->active*/)
						{
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
		case 0x12:
		case 0x13:
			Compute_LFO(slot);
			break;
	}
}

void scsp_device::UpdateReg(int reg)
{
	switch (reg & 0x3f)
	{
		case 0x0:
			set_output_gain(0, MVOL() / 15.0);
			set_output_gain(1, MVOL() / 15.0);
			break;
		case 0x2:
		case 0x3:
			{
				m_DSP.RBL = (8 * 1024) << RBL(); // 8 / 16 / 32 / 64 kwords
				m_DSP.RBP = RBP();
			}
			break;
		case 0x6:
		case 0x7:
			{
				u8 data = m_udata.data[0x6 / 2] & 0xff;
				if (m_MidiOutR == m_MidiOutW)
				{
					// not busy, so start transmission
					transmit_register_setup(data);
				}
				m_MidiOutStack[m_MidiOutW++] = data;
				m_MidiOutW &= 31;

				// MIDI out interrupt (bit 9) is cancelled by writing the buffer (ST-77)
				m_udata.data[0x20/2] &= ~0x200;
				m_mcipd &= ~0x200;
				CheckPendingIRQ();
				MainCheckPendingIRQ(0);
			}
			break;
		case 8:
		case 9:
			/* Only MSLC could be written.  */
			// docs claims MSLC to be 0x7800 but saturn:jikkparo doesn't agree,
			// assume doc mistake out of being 0~31 slots
			m_latched_MSLC = (m_udata.data[0x8/2] & 0xf800) >> 11;
			break;
		case 0x12:
		case 0x13:
			m_dma.dmea = (m_udata.data[0x12/2] & 0xfffe) | (m_dma.dmea & 0xf0000);
			break;
		case 0x14:
		case 0x15:
			m_dma.dmea = ((m_udata.data[0x14/2] & 0xf000) << 4) | (m_dma.dmea & 0xfffe);
			m_dma.drga = (m_udata.data[0x14/2] & 0x0ffe);
			break;
		case 0x16:
		case 0x17:
			m_dma.dtlg = (m_udata.data[0x16/2] & 0x0ffe);
			m_dma.ddir = (m_udata.data[0x16/2] & 0x2000) >> 13;
			m_dma.dgate = (m_udata.data[0x16/2] & 0x4000) >> 14;
			if (m_udata.data[0x16/2] & 0x1000) // dexe
				exec_dma();
			break;
		case 0x18:
		case 0x19:
			if (!m_irq_cb.isunset())
				StartTimer(0);
			break;
		case 0x1a:
		case 0x1b:
			if (!m_irq_cb.isunset())
				StartTimer(1);
			break;
		case 0x1c:
		case 0x1d:
			if (!m_irq_cb.isunset())
				StartTimer(2);
			break;
		case 0x1e: // SCIEB
		case 0x1f:
			if (!m_irq_cb.isunset())
			{
				CheckPendingIRQ();
				UpdateSampleTimer();

				// external interrupts INT0N-INT2N are not connected in Saturn
				if (m_udata.data[0x1e/2] & 0x7)
					popmessage("SCSP SCIEB enabled %04x",m_udata.data[0x1e/2]);
			}
			break;
		case 0x20: // SCIPD
		case 0x21:
			// only bit 5 can be written (w16), it applies a CPU interrupt to the sound CPU.
			// NOTE: arcadegh uses level 7, which the documentation reserves for the
			// development board, and still has no sound
			if (!m_irq_cb.isunset())
				CheckPendingIRQ();
			break;
		case 0x22:  //SCIRE
		case 0x23:
			if (!m_irq_cb.isunset())
			{
				m_udata.data[0x20/2] &= ~m_udata.data[0x22/2];
				ResetInterrupts();

				// NOTE: the timers used to be one-shot and an expired one was put back into
				// SCIPD here to imitate saturn:sakurat (while saturn:crocj kept getting
				// spurious interrupts from it). They run freely now, so the next overflow
				// sets the flag again by itself.
			}
			break;
		case 0x24:
		case 0x25:
		case 0x26:
		case 0x27:
		case 0x28:
		case 0x29:
			if (!m_irq_cb.isunset())
			{
				m_IrqTimA = DecodeSCI(SCITMA);
				m_IrqTimBC = DecodeSCI(SCITMB);
				m_IrqMidi = DecodeSCI(SCIMID);
				m_IrqCPU = DecodeSCI(SCIIRQ);
				m_IrqDMA = DecodeSCI(SCIDMA);
				CheckPendingIRQ();
			}
			break;
		case 0x2a:
		case 0x2b:
			m_mcieb = m_udata.data[0x2a/2];

			MainCheckPendingIRQ(0);
			UpdateSampleTimer();
			if (m_mcieb & 0x7)
				popmessage("SCSP MCIEB enabled %04x",m_mcieb);
			break;
		case 0x2c:
		case 0x2d:
			if (m_udata.data[0x2c/2] & 0x20)
				MainCheckPendingIRQ(0x20);
			break;
		case 0x2e:
		case 0x2f:
			m_mcipd &= ~m_udata.data[0x2e/2];
			MainCheckPendingIRQ(0);
			break;

	}
}

void scsp_device::UpdateSlotRegR(int slot,int reg)
{
}

void scsp_device::UpdateRegR(int reg)
{
	switch (reg & 0x3f)
	{
		case 4:
		case 5:
			{
				u16 v = m_udata.data[0x4/2];
				v &= 0xff00;
				v |= m_MidiStack[m_MidiR];
				logerror("Read %x from SCSP MIDI\n", v);
				if (m_MidiR != m_MidiW)
				{
					++m_MidiR;
					m_MidiR &= 31;
				}
				if (m_MidiR == m_MidiW)     // if the input FIFO is empty, clear the IRQ
				{
					m_udata.data[0x20 / 2] &= ~8;
					m_mcipd &= ~8;
					CheckPendingIRQ();
					MainCheckPendingIRQ(0);
				}
				m_udata.data[0x4/2] = v;
			}
			break;
		case 8:
		case 9:
			{
				m_udata.data[0x8/2] = m_latched_MSLC_data;
			}
			break;

		case 0x18:
		case 0x19:
			break;

		case 0x1a:
		case 0x1b:
			break;

		case 0x1c:
		case 0x1d:
			break;

		//case 0x20:
		//  m_udata.data[0x20/2] ^= 0x400;
		//  break;

		case 0x2a:
		case 0x2b:
			m_udata.data[0x2a/2] = m_mcieb;
			break;

		case 0x2c:
		case 0x2d:
			m_udata.data[0x2c/2] = m_mcipd;
			break;
	}
}

void scsp_device::w16(u32 addr, u16 val)
{
	addr &= 0xffff;
	if (addr < 0x400)
	{
		int slot = addr / 0x20;
		addr &= 0x1f;
		*((u16 *) (m_Slots[slot].udata.datab + (addr))) = val;
		UpdateSlotReg(slot, addr & 0x1f);
	}
	else if (addr < 0x600)
	{
		if (addr < 0x430)
		{
			// SCIPD and MCIPD are r/o except for bit 5 CPU irqs
			if (addr == 0x420 || addr == 0x42c)
			{
				*((u16 *) (m_udata.datab + ((addr & 0x3f)))) |= val & 0x20;
			}
			else
				*((u16 *) (m_udata.datab + ((addr & 0x3f)))) = val;
			UpdateReg(addr & 0x3f);
		}
	}
	else if (addr < 0x700)
		m_RINGBUF[(addr - 0x600)/2] = val;
	else
	{
		//DSP
		if (addr < 0x780)  //COEF
			*((u16 *) (m_DSP.COEF + (addr - 0x700) / 2)) = val;
		else if (addr < 0x7c0)
			*((u16 *) (m_DSP.MADRS + (addr - 0x780) / 2)) = val;
		else if (addr < 0x800) // MADRS is mirrored twice
			*((u16 *) (m_DSP.MADRS + (addr - 0x7c0) / 2)) = val;
		else if (addr < 0xC00)
		{
			*((uint16_t *) (m_DSP.MPRO + (addr - 0x800) / 2)) = val;

			if (addr == 0xBF0)
			{
				m_DSP.Start();
			}
		}
	}
}

u16 scsp_device::r16(u32 addr)
{
	u16 v = 0;
	addr &= 0xffff;
	if (addr < 0x400)
	{
		int slot = addr / 0x20;
		addr &= 0x1f;
		UpdateSlotRegR(slot, addr & 0x1f);
		v = *((u16 *) (m_Slots[slot].udata.datab + (addr)));
	}
	else if (addr < 0x600)
	{
		if (addr < 0x430)
		{
			UpdateRegR(addr & 0x3f);
			v = *((u16 *) (m_udata.datab + ((addr & 0x3f))));
		}
	}
	else if (addr < 0x700)
		v = m_RINGBUF[(addr-0x600)/2];
	else
	{
		//DSP
		if (addr < 0x780)  //COEF
			v= *((u16 *) (m_DSP.COEF + (addr - 0x700) / 2));
		else if (addr < 0x7c0)
			v= *((u16 *) (m_DSP.MADRS + (addr - 0x780) / 2));
		else if (addr < 0x800)
			v= *((u16 *) (m_DSP.MADRS + (addr - 0x7c0) / 2));
		else if (addr < 0xC00)
			v= *((u16 *) (m_DSP.MPRO + (addr - 0x800) / 2));
		else if (addr < 0xE00)
		{
			if (addr & 2)
				v = m_DSP.TEMP[(addr >> 2) & 0x7f] & 0xffff;
			else
				v = m_DSP.TEMP[(addr >> 2) & 0x7f] >> 16;
		}
		else if (addr < 0xE80)
		{
			if (addr & 2)
				v = m_DSP.MEMS[(addr >> 2) & 0x1f] & 0xffff;
			else
				v = m_DSP.MEMS[(addr >> 2) & 0x1f] >> 16;
		}
		else if (addr < 0xEC0)
		{
			if (addr & 2)
				v = m_DSP.MIXS[(addr >> 2) & 0xf] & 0xffff;
			else
				v = m_DSP.MIXS[(addr >> 2) & 0xf] >> 16;
		}
		else if (addr < 0xEE0)
			v = *((u16 *) (m_DSP.EFREG + (addr - 0xec0) / 2));
		else
		{
			// saturn Multiplayer Audio CDs and kyutnkai (68k PC=004A3A) reads from 0xee0/0xee2 EXTS
			// returns back current sample, makes the balloons in former to inflate.
			logerror("%s: SCSP Reading from EXTS register %08x\n", machine().describe_context(), addr);
			if (addr < 0xEE4)
				v = *((u16 *) (m_DSP.EXTS + (addr - 0xee0) / 2));
		}
	}
	return v;
}


inline s32 scsp_device::UpdateSlot(SCSP_SLOT *slot)
{
	if (SSCTL(slot) == 3) // manual says cannot be used
	{
		logerror("SCSP: Invaild SSCTL setting at slot %02x\n", slot->slot);
		return 0;
	}

	s32 sample = 0; // NB: Shouldn't be necessary, but GCC 8.2.1 claims otherwise.
	int step = slot->step;
	u32 addr1, addr2, addr_select;                                   // current and next sample addresses
	u32 *addr[2]      = {&addr1, &addr2};                          // used for linear interpolation
	u32 *slot_addr[2] = {&(slot->cur_addr), &(slot->nxt_addr)};    //

	if (PLFOS(slot) != 0)
	{
		step = step * PLFO_Step(&(slot->PLFO));
		step >>= SHIFT;
	}

	if (PCM8B(slot))
	{
		addr1 = slot->cur_addr >> SHIFT;
		addr2 = slot->nxt_addr >> SHIFT;
	}
	else
	{
		addr1 = (slot->cur_addr >> (SHIFT - 1)) & ~1;
		addr2 = (slot->nxt_addr >> (SHIFT - 1)) & ~1;
	}

	if (MDL(slot) != 0 || MDXSL(slot) != 0 || MDYSL(slot) != 0)
	{
		s32 smp = (m_RINGBUF[(m_BUFPTR + MDXSL(slot)) & 63] + m_RINGBUF[(m_BUFPTR + MDYSL(slot)) & 63]) / 2;

		smp <<= 0xA; // associate cycle with 1024
		smp >>= 0x1A - MDL(slot); // ex. for MDL=0xF, sample range corresponds to +/- 64 pi (32=2^5 cycles) so shift by 11 (16-5 == 0x1A-0xF)
		if (!PCM8B(slot)) smp <<= 1;

		addr1 += smp; addr2 += smp;
	}

	if (SSCTL(slot) == 0) // External DRAM data
	{
		if (PCM8B(slot)) //8 bit signed
		{
			int8_t p1 = read_byte(SA(slot) + addr1);
			int8_t p2 = read_byte(SA(slot) + addr2);
			s32 s;
			s32 fpart=slot->cur_addr & ((1 << SHIFT) - 1);
			s = (int) (p1 << 8) * ((1 << SHIFT) - fpart) + (int) (p2 << 8) * fpart;
			sample = (s >> SHIFT);
		}
		else    //16 bit signed (endianness?)
		{
			s16 p1 = read_word(SA(slot) + addr1);
			s16 p2 = read_word(SA(slot) + addr2);
			s32 s;
			s32 fpart = slot->cur_addr & ((1 << SHIFT) - 1);
			s = (int)(p1) * ((1 << SHIFT) - fpart) + (int)(p2) * fpart;
			sample = (s >> SHIFT);
		}
	}
	else if (SSCTL(slot) == 1)  // Internally generated data (Noise)
		sample = (s16)((m_lfsr & 0xff) << 8);   // the noise generator's low byte as the upper byte of the sample
	else if (SSCTL(slot) >= 2)  // Internally generated data (All 0)
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

	if (addr1 >= LSA(slot) && !(slot->Backwards))
	{
		if (LPSLNK(slot) && slot->EG.state == SCSP_ATTACK)
			slot->EG.state = SCSP_DECAY1;
	}

	for (addr_select = 0; addr_select < 2; addr_select++)
	{
		s32 rem_addr;
		switch (LPCTL(slot))
		{
		case 0: //no loop
			if (*addr[addr_select] >= LSA(slot) && *addr[addr_select] >= LEA(slot))
			{
				//slot->active=0;
				StopSlot(slot, 0);
			}
			break;
		case 1: //normal loop
			if (*addr[addr_select] >= LEA(slot))
			{
				rem_addr = *slot_addr[addr_select] - (LEA(slot) << SHIFT);
				*slot_addr[addr_select] = (LSA(slot) << SHIFT) + rem_addr;
			}
			break;
		case 2: //reverse loop
			if ((*addr[addr_select] >= LSA(slot)) && !(slot->Backwards))
			{
				rem_addr = *slot_addr[addr_select] - (LSA(slot) << SHIFT);
				*slot_addr[addr_select] = (LEA(slot) << SHIFT) - rem_addr;
				slot->Backwards = 1;
			}
			else if ((*addr[addr_select] < LSA(slot) || (*slot_addr[addr_select] & 0x80000000)) && slot->Backwards)
			{
				rem_addr = (LSA(slot) << SHIFT) - *slot_addr[addr_select];
				*slot_addr[addr_select] = (LEA(slot) << SHIFT) - rem_addr;
			}
			break;
		case 3: //ping-pong
			if (*addr[addr_select] >= LEA(slot)) //reached end, reverse till start
			{
				rem_addr = *slot_addr[addr_select] - (LEA(slot) << SHIFT);
				*slot_addr[addr_select] = (LEA(slot) << SHIFT) - rem_addr;
				slot->Backwards = 1;
			}
			else if ((*addr[addr_select] < LSA(slot) || (*slot_addr[addr_select] & 0x80000000)) && slot->Backwards)//reached start or negative
			{
				rem_addr = (LSA(slot) << SHIFT) - *slot_addr[addr_select];
				*slot_addr[addr_select] = (LSA(slot) << SHIFT) + rem_addr;
				slot->Backwards = 0;
			}
			break;
		}
	}

	if (!SDIR(slot))
	{
		if (ALFOS(slot) != 0)
		{
			sample = sample * ALFO_Step(&(slot->ALFO));
			sample >>= SHIFT;
		}

		sample = (sample * m_EG_TABLE[EG_Update(slot)]) >> SHIFT;
	}

	if (!STWINH(slot))
	{
		if (!SDIR(slot))
		{
			u16 Enc = ((TL(slot)) << 0x0) | (0x7 << 0xd);
			*m_RBUFDST = (sample * m_LPANTABLE[Enc]) >> (SHIFT + 1);
		}
		else
		{
			u16 Enc = (0 << 0x0) | (0x7 << 0xd);
			*m_RBUFDST = (sample * m_LPANTABLE[Enc]) >> (SHIFT + 1);
		}
	}

	return sample;
}

void scsp_device::DoMasterSamples(sound_stream &stream)
{
	for (int s = 0; s < stream.samples(); ++s)
	{
		s32 smpl = 0, smpr = 0;

		for (int sl = 0; sl < 32; ++sl)
		{
			// the noise generator (MiSTer SCSP.sv NOISE, Ymir m_lfsr) steps once per slot time
			m_lfsr = (m_lfsr >> 1) | ((((m_lfsr >> 5) ^ m_lfsr) & 1) << 16);
#if SCSP_FM_DELAY
			m_RBUFDST = m_DELAYBUF + m_DELAYPTR;
#else
			m_RBUFDST = m_RINGBUF + m_BUFPTR;
#endif
			if (m_Slots[sl].active)
			{
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
				m_DSP.SetSample((sample*m_LPANTABLE[Enc]) >> (SHIFT-2), ISEL(slot), IMXL(slot));
				u16 dir_tl = SDIR(slot) ? 0 : TL(slot);
				Enc = ((dir_tl) << 0x0) | ((DIPAN(slot)) << 0x8) | ((DISDL(slot)) << 0xd);
				{
					smpl += (sample * m_LPANTABLE[Enc]) >> SHIFT;
					smpr += (sample * m_RPANTABLE[Enc]) >> SHIFT;
				}
			}

#if SCSP_FM_DELAY
			m_RINGBUF[(m_BUFPTR + 64 - (SCSP_FM_DELAY - 1)) & 63] = m_DELAYBUF[(m_DELAYPTR + SCSP_FM_DELAY - (SCSP_FM_DELAY - 1)) % SCSP_FM_DELAY];
#endif
			++m_BUFPTR;
			m_BUFPTR &= 63;
#if SCSP_FM_DELAY
			++m_DELAYPTR;
			if (m_DELAYPTR > SCSP_FM_DELAY-1) m_DELAYPTR = 0;
#endif
		}

		m_DSP.Step();

		for (int i = 0; i < 16; ++i)
		{
			SCSP_SLOT *slot = m_Slots + i;
			if (EFSDL(slot))
			{
				u16 Enc = ((EFPAN(slot)) << 0x8) | ((EFSDL(slot)) << 0xd);
				smpl += (m_DSP.EFREG[i] * m_LPANTABLE[Enc]) >> SHIFT;
				smpr += (m_DSP.EFREG[i] * m_RPANTABLE[Enc]) >> SHIFT;
			}
		}

		for (int i = 0; i < 2; ++i)
		{
			SCSP_SLOT *slot = m_Slots + i + 16; // 100217, 100237 EFSDL, EFPAN for EXTS0/1
			// !EFSDL case testable in saturn Multiplayer with Audio CD with default values.
			u16 Enc = EFSDL(slot) ? ((EFPAN(slot)) << 0x8) | ((EFSDL(slot)) << 0xd) : (((DIPAN(slot)) << 0x8) | ((DISDL(slot)) << 0xd));
			{
				m_DSP.EXTS[i] = s32(stream.get(i, s) * 32768.0);
				smpl += (m_DSP.EXTS[i] * m_LPANTABLE[Enc]) >> SHIFT;
				smpr += (m_DSP.EXTS[i] * m_RPANTABLE[Enc]) >> SHIFT;
			}
		}

		if (DAC18B())
		{
			stream.put_int_clamp(0, s, smpl, 131072);
			stream.put_int_clamp(1, s, smpr, 131072);
		}
		else
		{
			stream.put_int_clamp(0, s, smpl >> 2, 32768);
			stream.put_int_clamp(1, s, smpr >> 2, 32768);
		}

		++m_eg_counter;
	}
}

// TODO: this needs to be timer-ized
// Very likely this is burst too.
// - darius2j uses this at startup with DGATE enabled
void scsp_device::exec_dma()
{
	static u16 tmp_dma[3];
	int i;

	logerror("SCSP: DMA transfer START\n"
				"DMEA: %04x DRGA: %04x DTLG: %04x\n"
				"DGATE: %d  DDIR: %d\n", m_dma.dmea, m_dma.drga, m_dma.dtlg, m_dma.dgate ? 1 : 0, m_dma.ddir ? 1 : 0);

	/* Copy the dma values in a temp storage for resuming later */
	/* (DMA *can't* overwrite its parameters).                  */
	if (!(m_dma.ddir))
	{
		for (i = 0; i < 3; i++)
			tmp_dma[i] = m_udata.data[(0x12 + (i * 2)) / 2];
	}

	/* note: we don't use space.read_word / write_word because it can happen that SH-2 enables the DMA instead of m68k. */
	/* TODO: don't know if params auto-updates, I guess not ... */
	if (m_dma.ddir)
	{
		if (m_dma.dgate)
		{
			for (i = 0; i < m_dma.dtlg; i += 2)
			{
				this->space().write_word(m_dma.dmea, 0);
				m_dma.dmea += 2;
			}
		}
		else
		{
			for (i = 0; i < m_dma.dtlg; i += 2)
			{
				u16 tmp;
				tmp = r16(m_dma.drga);
				this->space().write_word(m_dma.dmea, tmp);
				m_dma.dmea += 2;
				m_dma.drga += 2;
			}
		}
	}
	else
	{
		if (m_dma.dgate)
		{
			for (i = 0; i < m_dma.dtlg; i += 2)
			{
				w16(m_dma.drga, 0);
				m_dma.drga += 2;
			}
		}
		else
		{
			for (i = 0; i < m_dma.dtlg; i += 2)
			{
				u16 tmp = read_word(m_dma.dmea);
				w16(m_dma.drga, tmp);
				m_dma.dmea += 2;
				m_dma.drga += 2;
			}
		}
	}

	/*Resume the values*/
	if (!(m_dma.ddir))
	{
		for (i = 0; i < 3; i++)
			m_udata.data[(0x12 + (i * 2)) / 2] = tmp_dma[i];
	}

	/* Job done */
	m_udata.data[0x16/2] &= ~0x1000;
	/* DMA transfer end interrupt: pending for both CPUs, SCIEB / MCIEB decide who is told */
	SetPending(0x10);
}


u16 scsp_device::read(offs_t offset)
{
	m_stream->update();
	return r16(offset * 2);
}

void scsp_device::write(offs_t offset, u16 data, u16 mem_mask)
{
	m_stream->update();

	u16 tmp = r16(offset * 2);
	COMBINE_DATA(&tmp);
	w16(offset * 2, tmp);
}

void scsp_device::tra_callback()
{
	m_midi_out_cb(transmit_register_get_data_bit());
}

void scsp_device::tra_complete()
{
	m_MidiOutR++;
	m_MidiOutR &= 31;

	// if buffer not empty, transmit next byte
	if (m_MidiOutR != m_MidiOutW)
	{
		transmit_register_setup(m_MidiOutStack[m_MidiOutR]);
	}
	else
	{
		// MIDI out buffer emptied: interrupt (bit 9), cancelled by the next write
		SetPending(0x200);
	}
}

void scsp_device::rcv_complete()
{
	receive_register_extract();
	m_MidiStack[m_MidiW++] = get_received_char();
	m_MidiW &= 31;

	SetPending(0x8);
}

//LFO handling

#define LFIX(v) ((u32) ((float) (1 << LFO_SHIFT) * (v)))

//Convert DB to multiply amplitude
#define DB(v)   LFIX(powf(10.0f, v / 20.0f))

//Convert cents to step increment
#define CENTS(v) LFIX(powf(2.0f, v / 1200.0f))


static const float LFOFreq[32] =
{
	0.17f,0.19f,0.23f,0.27f,0.34f,0.39f,0.45f,0.55f,0.68f,0.78f,0.92f,1.10f,1.39f,1.60f,1.87f,2.27f,
	2.87f,3.31f,3.92f,4.79f,6.15f,7.18f,8.60f,10.8f,14.4f,17.2f,21.5f,28.7f,43.1f,57.4f,86.1f,172.3f
};
static const float ASCALE[8] = {0.0f,0.4f,0.8f,1.5f,3.0f,6.0f,12.0f,24.0f};
static const float PSCALE[8] = {0.0f,7.0f,13.5f,27.0f,55.0f,112.0f,230.0f,494.0f};


void scsp_device::LFO_Init()
{
	for (int i = 0; i < 256; ++i)
	{
		int a,p;
//      float TL;
		//Saw
		a = 255-i;
		if (i < 128)
			p = i;
		else
			p = i - 256;
		m_ALFO_SAW[i] = a;
		m_PLFO_SAW[i] = p;

		//Square
		if (i < 128)
		{
			a = 255;
			p = 127;
		}
		else
		{
			a = 0;
			p = -128;
		}
		m_ALFO_SQR[i] = a;
		m_PLFO_SQR[i] = p;

		//Tri
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

		//noise: taken from the noise generator when the LFO runs (ALFO_Step, PLFO_Step)
		m_ALFO_NOI[i] = 0;
		m_PLFO_NOI[i] = 0;
	}

	for (int s = 0; s < 8; ++s)
	{
		float limit = PSCALE[s];
		for (int i = -128; i < 128; ++i)
		{
			m_PSCALES[s][i+128] = CENTS(((limit * (float) i) / 128.0f));
		}
		limit = -ASCALE[s];
		for (int i = 0; i < 256; ++i)
		{
			m_ASCALES[s][i] = DB(((limit * (float) i) / 256.0f));
		}
	}
}

s32 scsp_device::PLFO_Step(SCSP_LFO_t *LFO)
{
	int p;
	LFO->phase += LFO->phase_step;
#if LFO_SHIFT!=8
	LFO->phase &= (1 << (LFO_SHIFT + 8)) - 1;
#endif
	p=LFO->table[LFO->phase >> LFO_SHIFT];
	if (LFO->table == m_PLFO_NOI)
		p = (s8)((m_lfsr ^ 0x80) & 0xfe);
	p=LFO->scale[p+128];
	return p << (SHIFT - LFO_SHIFT);
}

s32 scsp_device::ALFO_Step(SCSP_LFO_t *LFO)
{
	int p;
	LFO->phase += LFO->phase_step;
#if LFO_SHIFT!=8
	LFO->phase &= (1 << (LFO_SHIFT + 8)) - 1;
#endif
	p=LFO->table[LFO->phase >> LFO_SHIFT];
	if (LFO->table == m_ALFO_NOI)
		p = m_lfsr & 0xfe;
	p=LFO->scale[p];
	return p << (SHIFT - LFO_SHIFT);
}

void scsp_device::LFO_ComputeStep(SCSP_LFO_t *LFO,u32 LFOF,u32 LFOWS,u32 LFOS,int ALFO)
{
	float step = (float) LFOFreq[LFOF] * 256.0f / 44100.0f;
	LFO->phase_step = (u32) ((float) (1 << LFO_SHIFT) * step);
	if (ALFO)
	{
		switch (LFOWS)
		{
			case 0: LFO->table = m_ALFO_SAW; break;
			case 1: LFO->table = m_ALFO_SQR; break;
			case 2: LFO->table = m_ALFO_TRI; break;
			case 3: LFO->table = m_ALFO_NOI; break;
		}
		LFO->scale = m_ASCALES[LFOS];
	}
	else
	{
		switch (LFOWS)
		{
			case 0: LFO->table = m_PLFO_SAW; break;
			case 1: LFO->table = m_PLFO_SQR; break;
			case 2: LFO->table = m_PLFO_TRI; break;
			case 3: LFO->table = m_PLFO_NOI; break;
		}
		LFO->scale = m_PSCALES[LFOS];
	}
}

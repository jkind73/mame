// license:BSD-3-Clause
// copyright-holders:Juergen Buchmueller, R. Belmont
/*****************************************************************************
 *
 *   sh7604.cpp
 *   Portable Hitachi SH-2 (SH7600 family) emulator
 *
 *  This work is based on <tiraniddo@hotmail.com> C/C++ implementation of
 *  the SH-2 CPU core and was adapted to the MAME CPU core requirements.
 *  Thanks also go to Chuck Mason <chukjr@sundail.net> and Olivier Galibert
 *  <galibert@pobox.com> for letting me peek into their SEMU code :-)
 *
 *****************************************************************************/
/*
The on-chip SCI, WDT and BSC share this CPU's clock, interrupt controller and reset state.
*/


#include "emu.h"

#include "sh7604.h"

//#define VERBOSE 1
#include "logmacro.h"


static constexpr int div_tab[4] = { 3, 5, 7, 0 };
static constexpr int wdtclk_tab[8] = { 1, 6, 7, 8, 9, 10, 12, 13 };


DEFINE_DEVICE_TYPE(SH7604,  sh7604_device,  "sh2_7604",  "Hitachi SH-2 (SH7604)")


// Cache/fetch monitoring enlarges translated code. VF2 exceeds a 32 MiB host
// cache and repeatedly recompiles its working set; this is not the guest cache.
sh7604_device::sh7604_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: sh2_device(mconfig, SH7604, tag, owner, clock, CPU_TYPE_SH2, address_map_constructor(FUNC(sh7604_device::sh7604_map), this), 32, 0xc7ffffff, 256 * 1024 * 1024)
	, m_smr(0), m_brr(0), m_scr(0), m_tdr(0), m_ssr(0)
	, m_sci_tx(*this), m_sci_txd(*this), m_sci_sck(*this)
	, m_ftoa(*this), m_ftob(*this)
	, m_tier(0), m_ftcsr(0), m_ftcsr_read_flags(0), m_frc_tcr(0), m_tocr(0), m_frc(0), m_ocra(0), m_ocrb(0), m_frc_icr(0)
	, m_ipra(0), m_iprb(0), m_vcra(0), m_vcrb(0), m_vcrc(0), m_vcrd(0), m_vcrwdt(0), m_vcrdiv(0), m_intc_icr(0), m_vecmd(false), m_nmie(false)
	, m_divu_ovf(false), m_divu_ovfie(false), m_dvsr(0), m_dvdntl(0), m_dvdnth(0)
	, m_wtcnt(0), m_wtcsr(0), m_rstcsr(0)
	, m_dma_dack{{*this}, {*this}}, m_dma_read{{*this, 0xffffffff}, {*this, 0xffffffff}}, m_dma_write{{*this}, {*this}}
	, m_dmaor(0)
	, m_sbycr(0)
	, m_standby_hiz(*this), m_ckpack(*this)
	, m_bcr1(0), m_bcr2(0), m_wcr(0), m_mcr(0), m_rtcsr(0), m_rtcor(0), m_rtcnt(0)
	, m_frc_base(0), m_frt_input(0)
	, m_timer(nullptr), m_wdtimer(nullptr)
	, m_is_slave(0)
	, m_dma_kludge_cb(*this)
	, m_dma_fifo_data_available_cb(*this)
	, m_ftcsr_read_cb(*this)
{
	m_frt_clockrate = clock;
	std::fill(std::begin(m_vcrdma), std::end(m_vcrdma), 0);
	std::fill(std::begin(m_dma_timer_active), std::end(m_dma_timer_active), 0);
	m_onchip_width_checks = true;
	std::fill(std::begin(m_active_dma_incs), std::end(m_active_dma_incs), 0);
	std::fill(std::begin(m_active_dma_incd), std::end(m_active_dma_incd), 0);
	std::fill(std::begin(m_active_dma_size), std::end(m_active_dma_size), 0);
	std::fill(std::begin(m_active_dma_steal), std::end(m_active_dma_steal), 0);
	std::fill(std::begin(m_active_dma_src), std::end(m_active_dma_src), 0);
	std::fill(std::begin(m_active_dma_dst), std::end(m_active_dma_dst), 0);
	std::fill(std::begin(m_active_dma_count), std::end(m_active_dma_count), 0);
	std::fill(std::begin(m_wtcw), std::end(m_wtcw), 0);
	std::fill(std::begin(m_dma_current_active_timer), std::end(m_dma_current_active_timer), nullptr);

	m_irq_vector.fic = m_irq_vector.foc = m_irq_vector.fov = m_irq_vector.divu = 0;
	std::fill(std::begin(m_irq_vector.dmac), std::end(m_irq_vector.dmac), 0);

	m_irq_level.frc = m_irq_level.sci = m_irq_level.divu = m_irq_level.dmac = m_irq_level.wdt = 0;

	for (int i = 0; i < 2; i++)
		m_dmac[i].drcr = m_dmac[i].sar = m_dmac[i].dar = m_dmac[i].tcr = m_dmac[i].chcr = 0;
}

void sh7604_device::device_start()
{
	sh2_device::device_start();

	m_timer = timer_alloc(FUNC(sh7604_device::sh2_timer_callback), this);
	m_timer->adjust(attotime::never);
	m_wdtimer = timer_alloc(FUNC(sh7604_device::sh2_wdtimer_callback), this);
	m_wdtimer->adjust(attotime::never);

	m_dma_current_active_timer[0] = timer_alloc(FUNC(sh7604_device::sh2_dma_current_active_callback), this);
	m_dma_current_active_timer[0]->adjust(attotime::never);

	m_dma_current_active_timer[1] = timer_alloc(FUNC(sh7604_device::sh2_dma_current_active_callback), this);
	m_dma_current_active_timer[1]->adjust(attotime::never);

	for (unsigned ch = 0; ch < 2; ++ch)
	{
		m_dma_dack_timer[ch] = timer_alloc(FUNC(sh7604_device::dma_dack_tick), this);
		m_dma_dack_timer[ch]->adjust(attotime::never);
	}
	m_divu_timer = timer_alloc(FUNC(sh7604_device::divu_timer_cb), this);
	m_divu_timer->adjust(attotime::never);
	m_standby_timer = timer_alloc(FUNC(sh7604_device::standby_wake), this);
	m_standby_timer->adjust(attotime::never);
	m_refresh_timer = timer_alloc(FUNC(sh7604_device::refresh_tick), this);
	m_refresh_timer->adjust(attotime::never);
	m_refresh_clockrate = clock();
	m_refresh_epoch = machine().time();
	m_frt_capture_timer = timer_alloc(FUNC(sh7604_device::frt_capture_callback), this);
	m_frt_capture_timer->adjust(attotime::never);
	m_sci_timer = timer_alloc(FUNC(sh7604_device::sci_tx_complete), this);
	m_sci_timer->adjust(attotime::never);
	m_sci_rx_timer = timer_alloc(FUNC(sh7604_device::sci_rx_tick), this);
	m_sci_clock_timer = timer_alloc(FUNC(sh7604_device::sci_clock_tick), this);
	m_sci_rx_timer->adjust(attotime::never);
	m_sci_clock_timer->adjust(attotime::never);
	state_add(0x100, "RXD", m_sci_pin_value).mask(1).callimport().callexport();
	state_add(0x101, "SCK", m_sci_pin_value).mask(1).callimport().callexport();
	state_add(0x102, "TXD", m_sci_txd_level).mask(1).readonly();
	state_add(0x103, "SCKOUT", m_sci_sck_level).mask(1).readonly();
	state_add(0x104, "FTCI", m_sci_pin_value).mask(1).callimport().callexport();
	state_add(0x105, "FTOA", m_frt_output[0]).mask(1).readonly();
	state_add(0x106, "FTOB", m_frt_output[1]).mask(1).readonly();
	state_add(0x107, "FTI", m_sci_pin_value).mask(1).callimport().callexport();
	machine().save().register_postload(save_prepost_delegate(FUNC(sh7604_device::power_postload), this));
	state_add(0x108, "DREQ0", m_sci_pin_value).mask(1).callimport().callexport();
	state_add(0x109, "DREQ1", m_sci_pin_value).mask(1).callimport().callexport();
	state_add(0x10a, "DACK0", m_sci_pin_value).mask(1).readonly().callexport();
	state_add(0x10b, "DACK1", m_sci_pin_value).mask(1).readonly().callexport();
	state_add(0x10c, "DMADATA0", m_dma_io_data[0]);
	state_add(0x10d, "DMADATA1", m_dma_io_data[1]);
	m_track_pending = true;

	/* resolve callbacks */
	m_dma_kludge_cb.resolve();
	m_dma_fifo_data_available_cb.resolve();
	m_ftcsr_read_cb.resolve();

	// SCI
	save_item(NAME(m_tx_frame));
	save_item(NAME(m_tx_bit));
	save_item(NAME(m_tx_bits));
	save_item(NAME(m_tx_stop));
	save_item(NAME(m_tx_format));
	save_item(NAME(m_tx_data));
	save_item(NAME(m_tx_mpbt));
	save_item(NAME(m_tx_ext_count));
	save_item(NAME(m_tx_prefetched));
	save_item(NAME(m_rx_busy));
	save_item(NAME(m_rsr));
	save_item(NAME(m_rx_stage));
	save_item(NAME(m_rx_format));
	save_item(NAME(m_rx_parity));
	save_item(NAME(m_rx_errors));
	save_item(NAME(m_rx_mp));
	save_item(NAME(m_rx_ext_count));
	save_item(NAME(m_sci_rxd));
	save_item(NAME(m_sci_sck_in));
	save_item(NAME(m_sci_txd_level));
	save_item(NAME(m_sci_sck_level));
	save_item(NAME(m_rdr));
	save_item(NAME(m_tsr));
	save_item(NAME(m_ssr_read));
	save_item(NAME(m_sci_busy));
	save_item(NAME(m_smr));
	save_item(NAME(m_brr));
	save_item(NAME(m_scr));
	save_item(NAME(m_tdr));
	save_item(NAME(m_ssr));

	// FRT / FRC
	save_item(NAME(m_tier));
	save_item(NAME(m_ftcsr));
	save_item(NAME(m_ftcsr_read_flags));
	save_item(NAME(m_frc_tcr));
	save_item(NAME(m_tocr));
	save_item(NAME(m_frc));
	save_item(NAME(m_frt_temp));
	save_item(NAME(m_ocra));
	save_item(NAME(m_ocrb));
	save_item(NAME(m_frc_icr));
	save_item(NAME(m_frc_base));
	save_item(NAME(m_frt_input));
	save_item(NAME(m_frt_clock_input));
	save_item(NAME(m_frt_output));
	save_item(NAME(m_frt_epoch));
	save_item(NAME(m_frt_clockrate));
	save_item(NAME(m_frt_generation));
	save_item(NAME(m_frt_capture_pending));
	save_item(NAME(m_frt_capture_clock_delay));
	save_item(NAME(m_frt_icr_read_cycle));
	save_item(NAME(m_frt_clear_cycle));

	// INTC
	save_item(NAME(m_irq_level.frc));
	save_item(NAME(m_irq_level.sci));
	save_item(NAME(m_irq_level.divu));
	save_item(NAME(m_irq_level.dmac));
	save_item(NAME(m_irq_level.wdt));
	save_item(NAME(m_irq_vector.fic));
	save_item(NAME(m_irq_vector.foc));
	save_item(NAME(m_irq_vector.fov));
	save_item(NAME(m_irq_vector.divu));
	save_item(NAME(m_irq_vector.dmac));

	save_item(NAME(m_ipra));
	save_item(NAME(m_iprb));
	save_item(NAME(m_vcra));
	save_item(NAME(m_vcrb));
	save_item(NAME(m_vcrc));
	save_item(NAME(m_vcrd));
	save_item(NAME(m_vcrwdt));
	save_item(NAME(m_vcrdiv));
	save_item(NAME(m_intc_icr));
	save_item(NAME(m_vcrdma));

	save_item(NAME(m_vecmd));
	save_item(NAME(m_nmie));

	// DIVU
	save_item(NAME(m_divu_shadow));
	save_item(NAME(m_divu_ovf));
	save_item(NAME(m_divu_ovfie));
	save_item(NAME(m_divu_busy));
	save_item(NAME(m_divu_ovf_pending));
	save_item(NAME(m_divu_done));
	save_item(NAME(m_dvsr));
	save_item(NAME(m_dvdntl));
	save_item(NAME(m_dvdnth));

	// WTC
	save_item(NAME(m_wtcnt));
	save_item(NAME(m_wtcsr));
	save_item(NAME(m_rstcsr));
	save_item(NAME(m_wtcw));

	// UBC
	save_item(NAME(m_ubc));
	save_item(NAME(m_ubc_live));
	save_item(NAME(m_ubc_fetch));
	save_item(NAME(m_ubc_previous_pc));
	save_item(NAME(m_ubc_ready));
	save_item(NAME(m_ubc_dirty));
	save_item(NAME(m_ubc_pending));
	save_item(NAME(m_ubc_sequence));
	save_item(NAME(m_ubc_inhibit));
	save_item(NAME(m_ubc_fetch_sequence));
	save_item(NAME(m_instruction_monitor));

	// DMAC
	save_item(NAME(m_dma_timer_active));
	save_item(NAME(m_active_dma_incs));
	save_item(NAME(m_active_dma_incd));
	save_item(NAME(m_active_dma_size));
	save_item(NAME(m_active_dma_steal));
	save_item(NAME(m_active_dma_src));
	save_item(NAME(m_active_dma_dst));
	save_item(NAME(m_active_dma_count));
	save_item(NAME(m_dma_dreq));
	save_item(NAME(m_dma_dack_level));
	save_item(NAME(m_dma_dreq_driven));
	save_item(NAME(m_dma_edge));
	save_item(NAME(m_dma_edge_burst));
	save_item(NAME(m_dma_ack_high));
	save_item(NAME(m_dma_requests));
	save_item(NAME(m_dma_ack_count));
	save_item(NAME(m_dma_io_data));
	save_item(NAME(m_dma_ready));
	save_item(NAME(m_dma_detect_after));
	save_item(NAME(m_dma_ack_start));
	save_item(NAME(m_dma_ack_end));
	save_item(NAME(m_dma_owner));
	save_item(NAME(m_dma_priority));
	save_item(NAME(m_dma_step));
	save_item(NAME(m_dma_step_count));
	save_item(NAME(m_dma_count_delta));
	save_item(NAME(m_dma_src_delta));
	save_item(NAME(m_dma_dst_delta));
	save_item(NAME(m_dma_unit_control));
	save_item(NAME(m_dma_unit_src));
	save_item(NAME(m_dma_unit_dst));
	save_item(NAME(m_dma_data));
	save_item(NAME(m_dma_committed));
	save_item(NAME(m_dma_cancelled));
	save_item(NAME(m_dma_staged));
	save_item(NAME(m_dma_bus_end));
	save_item(NAME(m_dma_pause_time));
	save_item(STRUCT_MEMBER(m_dma_steps, address));
	save_item(STRUCT_MEMBER(m_dma_steps, bytes));
	save_item(STRUCT_MEMBER(m_dma_steps, word));
	save_item(STRUCT_MEMBER(m_dma_steps, shift));
	save_item(STRUCT_MEMBER(m_dma_steps, write));
	for (unsigned i = 0; i < 32; ++i)
	{
		save_item(NAME(m_dma_steps[i].start), i);
		save_item(NAME(m_dma_steps[i].end), i);
	}
	save_item(NAME(m_dmaor));
	save_item(NAME(m_dma_te_read));
	save_item(NAME(m_dmaor_read_flags));
	save_item(STRUCT_MEMBER(m_dmac, drcr));
	save_item(STRUCT_MEMBER(m_dmac, sar));
	save_item(STRUCT_MEMBER(m_dmac, dar));
	save_item(STRUCT_MEMBER(m_dmac, tcr));
	save_item(STRUCT_MEMBER(m_dmac, chcr));

	// misc
	save_item(NAME(m_module_div_remaining));
	save_item(NAME(m_module_dma_remaining));
	save_item(NAME(m_clock_pause));
	save_item(NAME(m_standby));
	save_item(NAME(m_standby_waking));
	save_item(NAME(m_nmi_pin));
	save_item(NAME(m_standby_entry));
	save_item(NAME(m_sbycr));
	save_item(NAME(m_cache.ccr));
	save_item(NAME(m_cache.tag));
	save_item(NAME(m_cache.valid));
	save_item(NAME(m_cache.lru));
	save_item(NAME(m_cache.line));
	save_item(NAME(m_fetch_pc));
	save_item(NAME(m_fetch_data));
	save_item(NAME(m_fetch_cached));
	save_item(NAME(m_fetch_reuse));

	// BSC
	save_item(NAME(m_bcr1));
	save_item(NAME(m_bcr2));
	save_item(NAME(m_wcr));
	save_item(NAME(m_mcr));
	save_item(NAME(m_rtcsr));
	save_item(NAME(m_rtcsr_cmf_read));
	save_item(NAME(m_rtcor));
	save_item(NAME(m_rtcnt));
	save_item(NAME(m_refresh_epoch));
	save_item(NAME(m_refresh_clockrate));
	save_item(NAME(m_refresh_phase));
}

void sh7604_device::device_reset()
{
	refresh_resync();
	bool const manual = m_manual_reset;
	uint8_t const rstcsr = m_rstcsr;
	m_standby = m_standby_waking = m_clock_pause = false;
	m_standby_hiz(0);
	m_ckpack(1);
	m_standby_timer->adjust(attotime::never);
	resume(SUSPEND_REASON_CLOCK);
	m_nmi_pin = CLEAR_LINE;
	m_sci_dma_access = -1;
	m_sbycr = 0;
	m_module_div_remaining = attotime::never;
	for (auto &remaining : m_module_dma_remaining)
		remaining = attotime::never;
	sh2_device::device_reset();

	// The registers of the on-chip modules take their initial values (Hardware Manual, the register
	// chapters): the FRT, SCI, DMAC control registers and WDT as for standby mode, then the rest.
	// RSTCSR is only initialized by the RES input, not by the WDT's own reset (12.2.3).
	standby_init();
	m_rstcsr = m_wdt_reset ? rstcsr : 0;
	for (int i = 0; i < 2; i++)
	{
		m_dmac[i].drcr = 0;
		m_dma_current_active_timer[i]->adjust(attotime::never);
	}
	m_divu_ovf = m_divu_ovfie = false;
	m_divu_ovf_pending = false;
	m_ipra = m_iprb = 0;
	m_vcra = m_vcrb = m_vcrc = m_vcrd = m_vcrwdt = 0;
	std::fill(std::begin(m_vcrdma), std::end(m_vcrdma), 0);
	m_irq_level.frc = m_irq_level.sci = m_irq_level.divu = m_irq_level.dmac = m_irq_level.wdt = 0;
	m_irq_vector.fic = m_irq_vector.foc = m_irq_vector.fov = m_irq_vector.divu = 0;
	m_irq_vector.dmac[0] = m_irq_vector.dmac[1] = 0;
	m_intc_icr = 0;
	m_nmie = false;
	m_vecmd = false;
	m_sbycr = 0;
	// a power-on reset initializes the BSC as well; a manual reset leaves it alone (4.2.3)
	if (!manual)
	{
		m_bcr1 = 0x03f0;
		m_bcr2 = 0x00fc;
		m_wcr = 0xaaff;
		m_mcr = 0;
		m_rtcsr = 0;
		m_rtcsr_cmf_read = false;
		m_rtcnt = 0;
		m_rtcor = 0;
		m_refresh_phase = 0;
	}
	m_refresh_epoch = machine().time();
	m_refresh_clockrate = clock();
	refresh_activate();
	sh2_recalc_irq();

	// CCR resets to zero (section 8.2); this disables the cache without implying a purge
	// of cache memory, which reset does not initialize (8.5.1).
	m_cache.ccr = 0;
	m_fetch_pc = ~0U;
	m_fetch_data = 0;
	m_fetch_cached = false;
	m_fetch_reuse = false;

	m_divu_busy = false;
	m_divu_ovf_pending = false;
	m_divu_timer->adjust(attotime::never);

	m_frc = 0;
	m_ocra = 0xffff;
	m_ocrb = 0xffff;
	m_frc_icr = 0;
	m_frc_base = m_frt_epoch = frt_cycles();
	frt_drive(0, 0);
	frt_drive(1, 0);
	sh2_timer_activate();

	for (int i = 0; i < 2; i++)
	{
		m_dma_timer_active[i] = 0;
		m_active_dma_incs[i] = 0;
		m_active_dma_incd[i] = 0;
		m_active_dma_size[i] = 0;
		m_active_dma_steal[i] = 0;
		m_active_dma_src[i] = 0;
		m_active_dma_dst[i] = 0;
		m_active_dma_count[i] = 0;
	}

	m_wtcnt = 0;
	m_wtcsr = 0;
	m_wtcsr_ovf_read = false;
	m_rstcsr_wovf_read = false;
	if (!m_wdt_reset)
		m_rstcsr = 0;
	m_wdt_reset = false;

	m_ubc_inhibit = m_ubc_fetch_sequence = false;
	m_ubc_previous_pc = 0xffffffff;

	// a manual reset leaves the BSC and UBC alone (Hardware Manual 4.2.3)
	if (!manual)
	{
		std::fill(std::begin(m_ubc), std::end(m_ubc), 0);
		std::fill(std::begin(m_ubc_live), std::end(m_ubc_live), 0);
		m_ubc_dirty = m_ubc_pending = m_ubc_sequence = m_ubc_inhibit = false;
		m_instruction_monitor = 0;
		std::fill(std::begin(m_ubc_fetch), std::end(m_ubc_fetch), 0);
		m_ubc_previous_pc = 0xffffffff;
	}
	bsc_endian_update();
}

// on-chip modules initialized in standby mode (SH7604 hardware manual table 14.3), the
// INTC, UBC and BSC retain their registers and the DIVU ones are undefined
// - saturn:madden98u leaves a slave FRT input capture pending on the master when it changes
//   the system clock (the BIOS enters standby while the SMPC switches the PLL), it would
//   otherwise dispatch to the slave SH2 that the clock change turned off
void sh7604_device::device_clock_changed()
{
	if (m_refresh_timer)
		refresh_resync();
	uint32_t const old_clock = m_frt_clockrate;
	attotime const capture_remaining = m_frt_capture_timer ? m_frt_capture_timer->remaining() : attotime::never;
	if (m_frt_capture_pending && !capture_remaining.is_never() && old_clock)
		m_frt_capture_clock_delay = capture_remaining * old_clock;
	sh2_device::device_clock_changed();
	m_frt_clockrate = clock();
	m_refresh_clockrate = clock();
	m_refresh_epoch = machine().time();
	if (m_refresh_timer)
		refresh_activate();
	if (m_timer)
	{
		sh2_timer_resync();
		sh2_timer_activate();
	}
	if (m_frt_capture_pending)
		m_frt_capture_timer->adjust(clock() ? m_frt_capture_clock_delay / clock() : attotime::never);
	// The execute interface resumes CLOCK on a frequency change. Full standby
	// must survive the BIOS/SMPC PLL switch until its qualified NMI wake.
	if (m_standby)
		suspend(SUSPEND_REASON_CLOCK, false);
}

void sh7604_device::power_postload()
{
	bsc_endian_update();
	m_ftoa(m_frt_output[0]);
	m_ftob(m_frt_output[1]);
	if (m_standby)
		suspend(SUSPEND_REASON_CLOCK, false);
	m_sci_txd(m_sci_txd_level);
	m_sci_sck(m_sci_sck_level);
	m_standby_hiz(m_standby && BIT(m_sbycr, 6));
	m_ckpack(!m_clock_pause);
	for (unsigned ch = 0; ch < 2; ++ch)
		m_dma_dack[ch](dma_dack_level(ch));
}

void sh7604_device::sleep_enter(unsigned pending_cycles)
{
	if (!BIT(m_sbycr, 7) || BIT(m_wtcsr, 5))
		return;

	refresh_resync();
	// Table 14.3 initialization belongs to entry, before clocks stop.
	sh2_wtcnt_recalc();
	standby_init();
	m_standby = true;
	m_standby_waking = false;
	m_standby_entry = local_time() + cycles_to_attotime(pending_cycles);
	refresh_activate();
	m_standby_hiz(BIT(m_sbycr, 6));
	m_timer->adjust(attotime::never);
	m_divu_timer->adjust(attotime::never);
	m_divu_busy = false; // DIVU contents are undefined in standby.
	if (suspended(SUSPEND_REASON_DMA)) resume(SUSPEND_REASON_DMA);
	suspend(SUSPEND_REASON_CLOCK, false);
}

void sh7604_device::ckpreq_w(int state)
{
	// In clock-input mode the host changes/stops CKIO after CKPACK goes low.
	// Internal state remains full standby until the qualified NMI settles (14.4.4).
	if (!state && m_standby && !(m_wtcsr & 0x20))
	{
		m_clock_pause = true;
		m_ckpack(0);
	}
}

void sh7604_device::execute_set_input(int inputnum, int state)
{
	if (inputnum != INPUT_LINE_NMI)
	{
		sh2_device::execute_set_input(inputnum, state);
		return;
	}

	// ASSERT_LINE is the low level of the active-low NMI pin.
	if (state == m_nmi_pin)
		return;
	m_nmi_pin = state;
	if ((state == CLEAR_LINE) != m_nmie)
		return;

	if (m_standby)
	{
		// NMI is not sampled during SLEEP or the following five clocks (14.4.1).
		if (!m_standby_waking && machine().time() >= m_standby_entry + cycles_to_attotime(6))
		{
			m_standby_waking = true;
			m_standby_timer->adjust(cycles_to_attotime((256U - m_wtcnt) << wdtclk_tab[m_wtcsr & 7]));
		}
		return;
	}

	// Outside full standby, NMI inhibits both channels even when idle (9.2.7).
	// In full standby the DMAC registers are initialized and its clock is
	// stopped (Table 14.3); the wake edge belongs to the INTC/WDT path above.
	m_dmaor |= 2;
	sh2_dmac_check(0);
	sh2_dmac_check(1);

	// Base SH2 consumes an interrupt assertion rather than physical pin edges.
	sh2_device::execute_set_input(INPUT_LINE_NMI, CLEAR_LINE);
	sh2_device::execute_set_input(INPUT_LINE_NMI, ASSERT_LINE);
}

TIMER_CALLBACK_MEMBER(sh7604_device::standby_wake)
{
	m_standby = m_standby_waking = false;
	m_refresh_epoch = machine().time();
	refresh_activate();
	m_wtcnt = 0;
	m_standby_hiz(0);
	if (m_clock_pause)
	{
		m_clock_pause = false;
		m_ckpack(1);
	}
	m_frc_base = m_frt_epoch = frt_cycles();
	sh2_timer_activate();
	resume(SUSPEND_REASON_CLOCK);
	sh2_device::execute_set_input(INPUT_LINE_NMI, CLEAR_LINE);
	sh2_device::execute_set_input(INPUT_LINE_NMI, ASSERT_LINE);
}

void sh7604_device::frt_reset()
{
	sh2_timer_resync();
	m_frt_generation++;
	m_frt_capture_pending = false;
	m_frt_capture_clock_delay = attotime::never;
	m_frt_icr_read_cycle = m_frt_clear_cycle = ~uint64_t(0);
	m_frt_capture_timer->adjust(attotime::never);
	m_frc_base = m_frt_epoch = frt_cycles();
	frt_drive(0, 0);
	frt_drive(1, 0);
	m_tier = 0x01;
	m_ftcsr = 0;
	m_ftcsr_read_flags = 0;
	m_frc = 0;
	m_ocra = 0xffff;
	m_ocrb = 0xffff;
	m_frc_tcr = 0;
	m_tocr = 0xe0;
	m_frc_icr = 0;
	m_frt_temp = 0;
	sh2_timer_activate();
}

void sh7604_device::module_standby(uint8_t old)
{
	uint8_t const stopped = m_sbycr & ~old;
	uint8_t const restarted = old & ~m_sbycr;
	if (stopped & 1)
		sci_reset();
	if (stopped & 2)
		frt_reset();
	if (restarted & 2)
	{
		m_frc_base = m_frt_epoch = frt_cycles();
		sh2_timer_activate();
	}
	if (stopped & 4)
	{
		m_module_div_remaining = m_divu_timer->remaining();
		m_divu_timer->adjust(attotime::never);
	}
	if ((restarted & 4) && m_divu_busy)
	{
		m_divu_done = machine().time() + m_module_div_remaining;
		m_divu_timer->adjust(m_module_div_remaining);
	}
	if (stopped & 0x10)
	{
		m_dma_pause_time = machine().time();
		for (unsigned ch = 0; ch < 2; ++ch) m_dma_dack_timer[ch]->adjust(attotime::never);
	}
	if (restarted & 0x10)
	{
		attotime const pause = machine().time() - m_dma_pause_time;
		if (m_dma_owner >= 0)
		{
			m_dma_bus_end += pause;
			for (unsigned i = 0; i < m_dma_step_count; ++i) { m_dma_steps[i].start += pause; m_dma_steps[i].end += pause; }
		}
		for (unsigned ch = 0; ch < 2; ++ch)
		{
			m_dma_ready[ch] += pause;
			m_dma_detect_after[ch] += pause;
			for (unsigned i = 0; i < m_dma_ack_count[ch]; ++i) { m_dma_ack_start[ch][i] += pause; m_dma_ack_end[ch][i] += pause; }
			if (!m_dma_dack[ch].isunset()) dma_dack_tick(ch);
		}
	}
	for (int channel = 0; channel < 2; channel++)
	{
		if (stopped & 0x10)
		{
			m_module_dma_remaining[channel] = m_dma_current_active_timer[channel]->remaining();
			m_dma_current_active_timer[channel]->adjust(attotime::never);
		}
		if (restarted & 0x10)
		{
			if (m_dma_timer_active[channel] == 1 && !m_module_dma_remaining[channel].is_never())
				m_dma_current_active_timer[channel]->adjust(m_module_dma_remaining[channel], channel);
			else
				sh2_dmac_check(channel);
		}
	}
	sci_update();
}

void sh7604_device::standby_init()
{
	frt_reset();

	// SCI
	sci_reset();

	m_dma_owner = -1;
	m_dma_priority = m_dma_step = m_dma_step_count = m_dma_count_delta = 0;
	m_dma_src_delta = m_dma_dst_delta = 0;
	m_dma_unit_control = m_dma_unit_src = m_dma_unit_dst = 0;
	m_dma_committed = m_dma_cancelled = m_dma_staged = false;
	m_dma_bus_end = m_dma_pause_time = attotime::zero;
	std::fill(std::begin(m_dma_data), std::end(m_dma_data), 0);
	for (auto &step : m_dma_steps) step = {};
	for (unsigned ch = 0; ch < 2; ++ch)
	{
		m_dma_edge[ch] = m_dma_edge_burst[ch] = false;
		m_dma_requests[ch] = m_dma_ack_count[ch] = 0;
		m_dma_ready[ch] = m_dma_detect_after[ch] = attotime::zero;
		m_dma_io_data[ch] = 0xffffffff;
		m_dma_ack_high[ch] = false;
		std::fill(std::begin(m_dma_ack_start[ch]), std::end(m_dma_ack_start[ch]), attotime::zero);
		std::fill(std::begin(m_dma_ack_end[ch]), std::end(m_dma_ack_end[ch]), attotime::zero);
		m_dma_dack_timer[ch]->adjust(attotime::never);
		dma_dack_drive(ch, 1);
	}
	// DMAC channel control and operation registers
	for (int i = 0; i < 2; i++)
	{
		m_dmac[i].chcr = 0;
		m_dma_te_read[i] = false;
		m_dma_current_active_timer[i]->adjust(attotime::never);
		m_dma_timer_active[i] = 0;
	}
	m_dmaor = 0;
	m_dmaor_read_flags = 0;

	// WDT overflow flag, timer mode and enable bits, reset control/status
	m_wtcsr &= 0x1f;
	m_wdtimer->adjust(attotime::never);
	m_rstcsr = 0;
	dma_update_halt();

	sh2_recalc_irq();
}

void sh7604_device::sh7604_map(address_map &map)
{
	if (m_cache_model)
	{
		// Table 8.2 partitions by address bits 31-29. MiSTer's CACHE.sv also
		// decodes 100 as the data array; 101 is not listed and keeps the
		// previous read value.
		map(0x40000000, 0x5fffffff).rw(FUNC(sh7604_device::cache_purge_r), FUNC(sh7604_device::cache_purge_w));
		map(0x60000000, 0x7fffffff).rw(FUNC(sh7604_device::cache_address_r), FUNC(sh7604_device::cache_address_w));
		map(0x80000000, 0x9fffffff).rw(FUNC(sh7604_device::cache_data_r), FUNC(sh7604_device::cache_data_w));
		map(0xa0000000, 0xbfffffff).r(FUNC(sh7604_device::sh2_internal_a5));
		map(0xc0000000, 0xdfffffff).rw(FUNC(sh7604_device::cache_data_r), FUNC(sh7604_device::cache_data_w));
	}
	else
	{
		map(0x40000000, 0xbfffffff).r(FUNC(sh7604_device::sh2_internal_a5));
	}

//  TODO: cps3boot breaks with this enabled. Needs callback
//  map(0xc0000000, 0xc0000fff).ram(); // cache data array

//  map(0xe0000000, 0xe00001ff).mirror(0x1ffffe00).rw(FUNC(sh7604_device::sh7604_r), FUNC(sh7604_device::sh7604_w));
	// TODO: internal map takes way too much resources if mirrored with 0x1ffffe00
	//       we eventually internalize again via trampoline & sh7604_device
	//       Also area 0xffff8000-0xffffbfff is for synchronous DRAM mode,
	//       so this isn't actually a full mirror
	// SCI
	map(0xfffffe00, 0xfffffe00).rw(FUNC(sh7604_device::smr_r), FUNC(sh7604_device::smr_w));
	map(0xfffffe01, 0xfffffe01).rw(FUNC(sh7604_device::brr_r), FUNC(sh7604_device::brr_w));
	map(0xfffffe02, 0xfffffe02).rw(FUNC(sh7604_device::scr_r), FUNC(sh7604_device::scr_w));
	map(0xfffffe03, 0xfffffe03).rw(FUNC(sh7604_device::tdr_r), FUNC(sh7604_device::tdr_w));
	map(0xfffffe04, 0xfffffe04).rw(FUNC(sh7604_device::ssr_r), FUNC(sh7604_device::ssr_w));
	map(0xfffffe05, 0xfffffe05).r(FUNC(sh7604_device::rdr_r));

	// FRC
	map(0xfffffe10, 0xfffffe10).rw(FUNC(sh7604_device::tier_r), FUNC(sh7604_device::tier_w));
	map(0xfffffe11, 0xfffffe11).rw(FUNC(sh7604_device::ftcsr_r), FUNC(sh7604_device::ftcsr_w));
	map(0xfffffe12, 0xfffffe13).rw(FUNC(sh7604_device::frc_r), FUNC(sh7604_device::frc_w));
	map(0xfffffe14, 0xfffffe15).rw(FUNC(sh7604_device::ocra_b_r), FUNC(sh7604_device::ocra_b_w));
	map(0xfffffe16, 0xfffffe16).rw(FUNC(sh7604_device::frc_tcr_r), FUNC(sh7604_device::frc_tcr_w));
	map(0xfffffe17, 0xfffffe17).rw(FUNC(sh7604_device::tocr_r), FUNC(sh7604_device::tocr_w));
	map(0xfffffe18, 0xfffffe19).r(FUNC(sh7604_device::frc_icr_r));

	// INTC
	map(0xfffffe60, 0xfffffe61).rw(FUNC(sh7604_device::iprb_r), FUNC(sh7604_device::iprb_w));
	map(0xfffffe62, 0xfffffe63).rw(FUNC(sh7604_device::vcra_r), FUNC(sh7604_device::vcra_w));
	map(0xfffffe64, 0xfffffe65).rw(FUNC(sh7604_device::vcrb_r), FUNC(sh7604_device::vcrb_w));
	map(0xfffffe66, 0xfffffe67).rw(FUNC(sh7604_device::vcrc_r), FUNC(sh7604_device::vcrc_w));
	map(0xfffffe68, 0xfffffe69).rw(FUNC(sh7604_device::vcrd_r), FUNC(sh7604_device::vcrd_w));

	map(0xfffffe71, 0xfffffe71).rw(FUNC(sh7604_device::drcr_r<0>), FUNC(sh7604_device::drcr_w<0>));
	map(0xfffffe72, 0xfffffe72).rw(FUNC(sh7604_device::drcr_r<1>), FUNC(sh7604_device::drcr_w<1>));

	// WTC
	map(0xfffffe80, 0xfffffe81).rw(FUNC(sh7604_device::wtcnt_r), FUNC(sh7604_device::wtcnt_w));
	map(0xfffffe82, 0xfffffe83).rw(FUNC(sh7604_device::rstcsr_r), FUNC(sh7604_device::rstcsr_w));

	// standby and cache control
	map(0xfffffe90, 0xfffffe91).rw(FUNC(sh7604_device::fmr_sbycr_r), FUNC(sh7604_device::fmr_sbycr_w));
	map(0xfffffe92, 0xfffffe92).rw(FUNC(sh7604_device::ccr_r), FUNC(sh7604_device::ccr_w));

	// INTC second section
	map(0xfffffee0, 0xfffffee1).rw(FUNC(sh7604_device::intc_icr_r), FUNC(sh7604_device::intc_icr_w));
	map(0xfffffee2, 0xfffffee3).rw(FUNC(sh7604_device::ipra_r), FUNC(sh7604_device::ipra_w));
	map(0xfffffee4, 0xfffffee5).rw(FUNC(sh7604_device::vcrwdt_r), FUNC(sh7604_device::vcrwdt_w));

	// DIVU
	map(0xffffff00, 0xffffff03).mirror(0x20).rw(FUNC(sh7604_device::dvsr_r), FUNC(sh7604_device::dvsr_w));
	map(0xffffff04, 0xffffff07).mirror(0x20).rw(FUNC(sh7604_device::dvdnt_r), FUNC(sh7604_device::dvdnt_w));
	map(0xffffff08, 0xffffff0b).mirror(0x20).rw(FUNC(sh7604_device::dvcr_r), FUNC(sh7604_device::dvcr_w));
	// INTC third section
	map(0xffffff0c, 0xffffff0f).mirror(0x20).rw(FUNC(sh7604_device::vcrdiv_r), FUNC(sh7604_device::vcrdiv_w));
	// DIVU continued. YabauseUT sh2.c div_mirror_test exercises both windows.
	map(0xffffff10, 0xffffff13).mirror(0x20).rw(FUNC(sh7604_device::dvdnth_r), FUNC(sh7604_device::dvdnth_w));
	map(0xffffff14, 0xffffff17).mirror(0x20).rw(FUNC(sh7604_device::dvdntl_r), FUNC(sh7604_device::dvdntl_w));
	map(0xffffff18, 0xffffff1f).mirror(0x20).rw(FUNC(sh7604_device::divu_shadow_r), FUNC(sh7604_device::divu_shadow_w));

	// UBC
	map(0xffffff40, 0xffffff4b).rw(FUNC(sh7604_device::ubc_r), FUNC(sh7604_device::ubc_w));
	map(0xffffff60, 0xffffff79).rw(FUNC(sh7604_device::ubc_b_r), FUNC(sh7604_device::ubc_b_w));

	// DMAC
	map(0xffffff80, 0xffffff83).rw(FUNC(sh7604_device::sar_r<0>), FUNC(sh7604_device::sar_w<0>));
	map(0xffffff84, 0xffffff87).rw(FUNC(sh7604_device::dar_r<0>), FUNC(sh7604_device::dar_w<0>));
	map(0xffffff88, 0xffffff8b).rw(FUNC(sh7604_device::dmac_tcr_r<0>), FUNC(sh7604_device::dmac_tcr_w<0>));
	map(0xffffff8c, 0xffffff8f).rw(FUNC(sh7604_device::chcr_r<0>), FUNC(sh7604_device::chcr_w<0>));

	map(0xffffff90, 0xffffff93).rw(FUNC(sh7604_device::sar_r<1>), FUNC(sh7604_device::sar_w<1>));
	map(0xffffff94, 0xffffff97).rw(FUNC(sh7604_device::dar_r<1>), FUNC(sh7604_device::dar_w<1>));
	map(0xffffff98, 0xffffff9b).rw(FUNC(sh7604_device::dmac_tcr_r<1>), FUNC(sh7604_device::dmac_tcr_w<1>));
	map(0xffffff9c, 0xffffff9f).rw(FUNC(sh7604_device::chcr_r<1>), FUNC(sh7604_device::chcr_w<1>));

	map(0xffffffa0, 0xffffffa3).rw(FUNC(sh7604_device::vcrdma_r<0>), FUNC(sh7604_device::vcrdma_w<0>));
	map(0xffffffa8, 0xffffffab).rw(FUNC(sh7604_device::vcrdma_r<1>), FUNC(sh7604_device::vcrdma_w<1>));
	map(0xffffffb0, 0xffffffb3).rw(FUNC(sh7604_device::dmaor_r), FUNC(sh7604_device::dmaor_w));

	// BSC
	map(0xffffffe0, 0xffffffe3).rw(FUNC(sh7604_device::bcr1_r), FUNC(sh7604_device::bcr1_w));
	map(0xffffffe4, 0xffffffe7).rw(FUNC(sh7604_device::bcr2_r), FUNC(sh7604_device::bcr2_w));
	map(0xffffffe8, 0xffffffeb).rw(FUNC(sh7604_device::wcr_r), FUNC(sh7604_device::wcr_w));
	map(0xffffffec, 0xffffffef).rw(FUNC(sh7604_device::mcr_r), FUNC(sh7604_device::mcr_w));
	map(0xfffffff0, 0xfffffff3).rw(FUNC(sh7604_device::rtcsr_r), FUNC(sh7604_device::rtcsr_w));
	map(0xfffffff4, 0xfffffff7).rw(FUNC(sh7604_device::rtcnt_r), FUNC(sh7604_device::rtcnt_w));
	map(0xfffffff8, 0xfffffffb).rw(FUNC(sh7604_device::rtcor_r), FUNC(sh7604_device::rtcor_w));
}


void sh7604_device::sh2_exception(const char *message, int irqline)
{
	int vector;

	// Full standby accepts only a qualified NMI after its settling timer.
	if (m_standby)
		return;

	if (irqline != 16)
	{
		if (irqline <= ((m_sh2_state->sr >> 4) & 15)) /* If the cpu forbids this interrupt */
			return;

		if (irqline == 15 && m_ubc_pending)
		{
			if (m_ubc_inhibit || delay_pending())
				return;
			m_ubc_pending = false;
			sh2_exception_internal(message, 15, 12);
			sh2_recalc_irq();
			return;
		}

		// an on-chip source takes the interrupt when no IRL input of the same level is pending: the
		// IRL inputs rank above the on-chip sources (Hardware Manual table 5.4). The source stays
		// requested until the program clears its flag, so the interrupt can be taken again once
		// the mask allows it
		if (m_sh2_state->internal_irq_level == irqline && !BIT(m_sh2_state->pending_irq, irqline))
		{
			vector = m_internal_irq_vector;
			LOG("SH-2 exception #%d (internal vector: $%x) after [%s]\n", irqline, vector, message);
		}
		else
		{
			if (m_vecmd)
			{
				vector = standard_irq_callback(irqline, m_sh2_state->pc);
				LOG("SH-2 exception #%d (external vector: $%x) after [%s]\n", irqline, vector, message);
			}
			else
			{
				standard_irq_callback(irqline, m_sh2_state->pc);
				vector = 64 + irqline/2;
				LOG("SH-2 exception #%d (autovector: $%x) after [%s]\n", irqline, vector, message);
			}
		}
	}
	else
	{
		vector = 11;
		LOG("SH-2 nmi exception (autovector: $%x) after [%s]\n", vector, message);
	}

	sh2_exception_internal(message, irqline, vector);
}

uint32_t sh7604_device::sh2_internal_a5()
{
	return 0xa5a5a5a5;
}

// Associative purge (8.4.7): a write to 40000000H + address invalidates the
// line holding address in every way whose tag matches. MiSTer's CACHE.sv
// purges on reads of the area too. What a read returns is not documented
// (CACHE.sv returns data array output, Mednafen all ones); the previous
// value is kept.
uint32_t sh7604_device::cache_purge_r(offs_t offset)
{
	if (!machine().side_effects_disabled())
		m_cache.purge_line(offset << 2);
	return sh2_internal_a5();
}

void sh7604_device::cache_purge_w(offs_t offset, uint32_t data)
{
	if (!machine().side_effects_disabled())
		m_cache.purge_line(offset << 2);
}

// Address array (8.4.9), longword access only. CACHE.sv returns the low
// half in both halves of a narrower read.
uint32_t sh7604_device::cache_address_r(offs_t offset, uint32_t mem_mask)
{
	uint32_t const value = m_cache.read_address_array(offset << 2);
	return mem_mask == 0xffffffff ? value : (value & 0xffff) * 0x10001;
}

void sh7604_device::cache_address_w(offs_t offset, uint32_t data)
{
	m_cache.write_address_array(offset << 2, data);
}

// Data array (8.4.8): byte, word or longword; in two-way mode ways 0 and 1
// are the 2 KB RAM, and with the cache off all four ways are 4 KB of RAM.
uint32_t sh7604_device::cache_data_r(offs_t offset)
{
	return m_cache.data_array(offset << 2);
}

void sh7604_device::cache_data_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_cache.data_array(offset << 2));
}

uint64_t sh7604_device::frt_cycles() const
{
	return total_cycles() + ((m_isdrc && executing()) ? m_bus_pending : 0);
}

void sh7604_device::frt_drive(unsigned channel, int level)
{
	level = !!level;
	if (m_frt_output[channel] != level)
	{
		m_frt_output[channel] = level;
		if (channel)
			m_ftob(level);
		else
			m_ftoa(level);
	}
}

void sh7604_device::frt_advance(uint64_t ticks, bool internal, int write_kind)
{
	uint32_t const generation = m_frt_generation;
	uint64_t const now = frt_cycles();
	unsigned const divider = div_tab[m_frc_tcr & 3];
	uint64_t const period = internal ? (1U << divider) : 0;
	uint64_t const end = internal ? now - ((now - m_frt_epoch) & (period - 1)) : now;
	while (ticks && clock() && generation == m_frt_generation && !m_standby && !BIT(m_sbycr, 1))
	{
		// Count clocks even when no flag or pin can change. In clear-on-A
		// mode the counter still cycles while OCFA remains asserted.
		bool const quiet_a = (m_ftcsr & OCFA) && m_frt_output[0] == BIT(m_tocr, 1);
		bool const quiet_b = (m_ftcsr & OCFB) && m_frt_output[1] == BIT(m_tocr, 0);
		if ((!write_kind || end != now) && quiet_a)
		{
			if ((m_ftcsr & CCLRA) && m_frc <= m_ocra && (m_ocrb > m_ocra || quiet_b))
			{
				uint64_t const first = uint32_t(m_ocra) - m_frc + 1;
				if (ticks < first)
					m_frc += ticks;
				else
				{
					uint64_t const residual = (ticks - first) % (uint32_t(m_ocra) + 1);
					m_frt_clear_cycle = end - residual * period;
					m_frc = residual;
				}
				return;
			}
			if (!(m_ftcsr & CCLRA) && quiet_b && (m_ftcsr & OVF))
			{
				m_frc += ticks;
				return;
			}
		}

		// 11.4.6: match is signalled on the clock leaving the matching count.
		uint32_t const a = uint16_t(m_ocra - m_frc) + 1U;
		uint32_t const b = uint16_t(m_ocrb - m_frc) + 1U;
		uint32_t const overflow = 0x10000U - m_frc;
		uint32_t const next = std::min({a, b, overflow});
		if (ticks < next)
		{
			m_frc += ticks;
			break;
		}
		uint16_t const preceding = m_frc + next - 1;
		uint64_t const event_cycle = end - (ticks - next) * period;
		bool const collision = event_cycle == now;
		// 11.7: an OCR low write suppresses its concurrent match. An FRC
		// write defeats increment, while compare-A clear defeats that write.
		bool const match_a = next == a && !(collision && write_kind == 2);
		bool const match_b = next == b && !(collision && write_kind == 3);
		bool const clear = match_a && BIT(m_ftcsr, 0);
		int const level_a = BIT(m_tocr, 1), level_b = BIT(m_tocr, 0);
		bool const increment = !(collision && write_kind == 1);
		m_frc = clear ? 0 : uint16_t(preceding + (increment ? 1 : 0));
		if (clear)
			m_frt_clear_cycle = event_cycle;
		if (match_a)
			m_ftcsr |= OCFA;
		if (match_b)
			m_ftcsr |= OCFB;
		if (!clear && increment && next == overflow)
			m_ftcsr |= OVF;
		ticks -= next;
		if (match_a)
			frt_drive(0, level_a);
		if (generation != m_frt_generation || m_standby || BIT(m_sbycr, 1))
			return;
		if (match_b)
			frt_drive(1, level_b);
		if (generation != m_frt_generation || m_standby || BIT(m_sbycr, 1))
			return;
		sh2_recalc_irq();
	}
}

void sh7604_device::frt_clock_w(int state)
{
	state = !!state;
	if (state == m_frt_clock_input)
		return;
	int const previous = m_frt_clock_input;
	m_frt_clock_input = state;
	// The legacy external-clock HACK mistook divider zero for a stopped clock.
	if (!previous && state && clock() && (m_frc_tcr & 3) == 3 && !m_standby && !BIT(m_sbycr, 1))
		frt_advance(1);
}

void sh7604_device::sh2_timer_resync(int write_kind)
{
	uint64_t const now = frt_cycles();
	if (m_standby || BIT(m_sbycr, 1) || (m_frc_tcr & 3) == 3)
	{
		m_frc_base = now;
		return;
	}
	unsigned const divider = div_tab[m_frc_tcr & 3];
	uint64_t const ticks = ((now - m_frt_epoch) >> divider) - ((m_frc_base - m_frt_epoch) >> divider);
	m_frc_base = now;
	frt_advance(ticks, true, write_kind);
}

void sh7604_device::sh2_timer_activate()
{
	m_timer->adjust(attotime::never);
	if (!clock() || m_standby || BIT(m_sbycr, 1) || (m_frc_tcr & 3) == 3)
		return;
	// The legacy flagged-match HACK skipped recurring output and clear events.
	// Wake for flag/pin changes; resync maintains all intervening counter clears.
	uint32_t delta = 0x10001;
	if (!(m_ftcsr & OCFA) || m_frt_output[0] != BIT(m_tocr, 1))
		delta = uint16_t(m_ocra - m_frc) + 1U;
	bool const reachable_b = !(m_ftcsr & CCLRA) || m_ocrb <= m_ocra || (m_frc > m_ocra && m_ocrb >= m_frc);
	if (reachable_b && (!(m_ftcsr & OCFB) || m_frt_output[1] != BIT(m_tocr, 0)))
		delta = std::min(delta, uint16_t(m_ocrb - m_frc) + 1U);
	if (!(m_ftcsr & OVF) && (!(m_ftcsr & CCLRA) || m_frc > m_ocra))
		delta = std::min(delta, 0x10000U - m_frc);
	if (delta == 0x10001)
		return;
	unsigned const divider = div_tab[m_frc_tcr & 3];
	uint64_t const phase = (frt_cycles() - m_frt_epoch) & ((1U << divider) - 1);
	uint64_t const clocks = (uint64_t(delta) << divider) - phase;
	attotime const now = executing() ? local_time() + cycles_to_attotime(m_isdrc ? m_bus_pending : 0) : machine().time();
	m_timer->adjust(now + cycles_to_attotime(clocks) - machine().time());
}

TIMER_CALLBACK_MEMBER(sh7604_device::sh2_timer_callback)
{
	sh2_timer_resync();
	sh2_timer_activate();
}

void sh7604_device::sh2_wtcnt_recalc()
{
	if (m_wdtimer->expire() != attotime::never)
		m_wtcnt = 0x100 - (attotime_to_cycles(m_wdtimer->remaining()) >> wdtclk_tab[m_wtcsr & 7]);
}

void sh7604_device::sh2_wdt_activate()
{
	m_wdtimer->adjust(cycles_to_attotime((0x100 - m_wtcnt) << wdtclk_tab[m_wtcsr & 7]));
}

TIMER_CALLBACK_MEMBER(sh7604_device::sh2_wdtimer_callback)
{
	m_wtcnt = 0;
	if (!(m_wtcsr & 0x40))  // timer mode
	{
		m_wtcsr |= 0x80;
		sh2_recalc_irq();
		sh2_wdt_activate();
	}
	else // watchdog mode
	{
		// WOVF is set and WDTOVF is output (not wired on the Saturn). WTCNT and WTCSR are reset
		// within the WDT; with RSTE set the chip is reset too, a power-on reset or a manual one as
		// RSTS says, for 512 clocks (Hardware Manual 12.3.1, 12.4.5). RSTCSR survives it.
		m_rstcsr |= 0x80;
		m_wtcnt = 0;
		m_wtcsr = 0;
		if (m_rstcsr & 0x40)
		{
			m_wdt_reset = true;
			m_manual_reset = BIT(m_rstcsr, 5);
			pulse_input_line(INPUT_LINE_RESET, cycles_to_attotime(512));
		}
	}
}

/*
  We have to do DMA on a timer (or at least, in chunks) due to the way some systems use it.
  The 32x is a difficult case, they set the SOURCE of the DMA to a FIFO buffer, which at most
  can have 8 words in it.  Attempting to do an 'instant DMA' in this scenario is impossible
  because the game is expecting the 68k of the system to feed data into the FIFO at the same
  time as the SH2 is transfering it out via DMA

  There are two ways we can do this

  a) with a high frequency timer (more accurate, but a large performance hit)

  or

  b) in the CPU_EXECUTE loop


  we're currently doing a)

  b) causes problems with ST-V games

*/



void sh7604_device::sh2_notify_dma_data_available()
{
	// A FIFO adapter can have no request at initial enable as well as stall an
	// existing transfer. Reconsider both states when the board supplies data.
	for (unsigned ch = 0; ch < 2; ++ch)
		sh2_dmac_check(ch);
}

// The bus controller charges a unit once; acknowledgement callbacks and
// single-address ports need its individual bus beats as well. Unconnected pins
// keep the existing one-callback-per-unit path used by Saturn.
attotime sh7604_device::dma_unit_time(uint32_t src, uint32_t dst, unsigned bytes, bool burst)
{
	int const ch = m_dma_owner;
	uint32_t const control = m_dma_unit_control;
	bool const single = BIT(control, 3), input = single && BIT(control, 8);
	attotime cursor = machine().time();
	attotime const cycle = cycles_to_attotime(1);
	m_dma_step_count = m_dma_step = 0;
	m_dma_ack_count[ch] = 0;
	auto const cost = [&] (uint32_t address, unsigned size, bool write, bool fill)
	{
		if (m_bus_observed && address < 0x40000000)
			m_bus_observer(address, size, write, fill);
		return (m_bus_timed && address < 0x40000000)
			? cycles_to_attotime(m_bus_timing(address, size, write, fill, cursor, true) + 1) : cycle;
	};
	auto const append = [&] (uint32_t address, unsigned size, unsigned word, bool write, attotime duration)
	{
		unsigned const area = (address >> 25) & 3;
		unsigned const memory = m_bcr1 & 7;
		bool const synchronous = (area == 2 && (memory == 4 || memory == 5)) || (area == 3 && (memory == 1 || memory == 5));
		bool const special = (area == 2 && (memory == 4 || memory == 5)) || (area == 3 && memory >= 1 && memory <= 5 && memory != 4);
		unsigned const width_code = area ? (m_bcr2 >> (area * 2)) & 3 : 3;
		unsigned const width = address >= 0xe0000000 ? size : special ? (BIT(m_mcr, 6) ? 4 : 2) : (width_code ? 1U << (width_code - 1) : 4);
		unsigned const beat = std::min(size, width), count = size / beat;
		duration = std::max(duration, cycle * count);
		for (unsigned i = 0; i < count; ++i)
		{
			auto &step = m_dma_steps[m_dma_step_count++];
			step.address = address + i * beat;
			step.bytes = beat;
			step.word = word;
			step.shift = (size - (i + 1) * beat) * 8;
			step.write = write;
			step.start = cursor;
			cursor += duration / count;
			step.end = cursor;
			if (single || (write == bool(BIT(control, 8))))
			{
				if (synchronous && !write && m_dma_ack_count[ch] && m_dma_ack_end[ch][m_dma_ack_count[ch] - 1] + cycle / 2 == step.start)
					m_dma_ack_end[ch][m_dma_ack_count[ch] - 1] = step.end - cycle / 2;
				else
				{
					unsigned const ack = m_dma_ack_count[ch]++;
					m_dma_ack_start[ch][ack] = step.start;
					m_dma_ack_end[ch][ack] = step.end - cycle / 2;
				}
			}
		}
	};
	if (single)
		append(input ? dst : src, bytes, 0, input, cost(input ? dst : src, bytes, input, false));
	else if (burst)
	{
		attotime const read = std::max(cost(src, 4, false, true), cycle * 4);
		for (unsigned i = 0; i < 4; ++i)
			append(src + i * 4, 4, i, false, i ? cycle : read - cycle * 3);
		for (unsigned i = 0; i < bytes / 4; ++i)
			append(dst + i * 4, 4, i, true, cost(dst + i * 4, 4, true, false));
	}
	else
	{
		append(src, bytes, 0, false, cost(src, bytes, false, false));
		append(dst, bytes, 0, true, cost(dst, bytes, true, false));
	}
	return cursor - machine().time();
}

void sh7604_device::dma_dack_drive(unsigned ch, int level)
{
	if (m_dma_dack_level[ch] != level)
	{
		m_dma_dack_level[ch] = level;
		m_dma_dack[ch](level);
	}
}

int sh7604_device::dma_dack_level(unsigned ch) const
{
	attotime const now = BIT(m_sbycr, 4) ? m_dma_pause_time : machine().time();
	bool active = false;
	for (unsigned i = 0; i < m_dma_ack_count[ch]; ++i)
		active |= now >= m_dma_ack_start[ch][i] && now < m_dma_ack_end[ch][i];
	return active == m_dma_ack_high[ch];
}

TIMER_CALLBACK_MEMBER(sh7604_device::dma_dack_tick)
{
	unsigned const ch = param & 1;
	dma_dack_drive(ch, dma_dack_level(ch));
	attotime next = attotime::never;
	for (unsigned i = 0; i < m_dma_ack_count[ch]; ++i)
	{
		if (m_dma_ack_start[ch][i] > machine().time()) next = std::min(next, m_dma_ack_start[ch][i]);
		if (m_dma_ack_end[ch][i] > machine().time()) next = std::min(next, m_dma_ack_end[ch][i]);
	}
	m_dma_dack_timer[ch]->adjust(next.is_never() ? next : next - machine().time(), ch);
}

void sh7604_device::dma_run_step(unsigned ch, unsigned index)
{
	auto const &step = m_dma_steps[index];
	unsigned const bytes = step.bytes;
	uint32_t const mask = bytes == 4 ? 0xffffffff : (1U << (bytes * 8)) - 1;
	bool const single = BIT(m_dma_unit_control, 3);
	if (!m_dma_dack[ch].isunset())
		dma_dack_drive(ch, dma_dack_level(ch));
	m_sci_dma_access = ch;
	if (step.write)
	{
		uint32_t value;
		if (single)
			value = m_dma_read[ch].isunset() ? m_dma_io_data[ch] & mask : m_dma_read[ch](0, mask);
		else
		{
			if (!m_dma_kludge_cb.isnull() && step.shift + bytes * 8 == (m_active_dma_size[ch] == 3 ? 32U : (8U << m_active_dma_size[ch])))
				m_dma_data[step.word] = m_dma_kludge_cb(m_dma_unit_src, m_dma_unit_dst, m_dma_data[step.word], m_active_dma_size[ch]);
			value = (m_dma_data[step.word] >> step.shift) & mask;
		}
		external_data_write(step.address, bytes, value);
		if (m_instruction_monitor)
			ubc_compare(step.address, value, bytes, true, false, true);
	}
	else
	{
		uint32_t const value = external_data_read(step.address, bytes);
		m_dma_data[step.word] |= (value & mask) << step.shift;
		if (m_instruction_monitor)
			ubc_compare(step.address, value, bytes, false, false, true);
		if (single)
		{
			m_dma_io_data[ch] = value & mask;
			m_dma_write[ch](0, value, mask);
		}
	}
	m_sci_dma_access = -1;
}

void sh7604_device::dma_commit_unit(unsigned ch)
{
	m_active_dma_src[ch] += m_dma_src_delta;
	m_active_dma_dst[ch] += m_dma_dst_delta;
	m_active_dma_count[ch] -= m_dma_count_delta;
	m_dmac[ch].sar += m_dma_src_delta;
	m_dmac[ch].dar += m_dma_dst_delta;
	m_dmac[ch].tcr = m_active_dma_count[ch] & 0xffffff;
	m_dma_committed = true;
}

void sh7604_device::dma_update_halt()
{
	bool burst = m_dma_owner >= 0 && m_active_dma_steal[m_dma_owner];
	for (unsigned ch = 0; ch < 2; ++ch)
		burst |= m_dma_timer_active[ch] == 1 && m_active_dma_steal[ch] && sci_dma_requested(ch);
	if (burst != suspended(SUSPEND_REASON_DMA))
	{
		if (burst) suspend(SUSPEND_REASON_DMA, true);
		else resume(SUSPEND_REASON_DMA);
	}
	if (m_dma_owner < 0 && !m_dma_timer_active[0] && !m_dma_timer_active[1] && !BIT(m_dmaor, 3))
		m_dma_priority = 0;
}

void sh7604_device::sh2_do_dma(int ch)
{
	if (m_standby || BIT(m_sbycr, 4)) return;
	unsigned const size = m_active_dma_size[ch], bytes = 1U << std::min(size, 2U);
	uint32_t const control = m_dmac[ch].chcr;
	bool const single = BIT(control, 3), input = single && BIT(control, 8);
	uint32_t const src = m_active_dma_src[ch] - ((!input && size != 3 && m_active_dma_incs[ch] == 2) ? bytes : 0);
	uint32_t const dst = m_active_dma_dst[ch] - ((!single || input) && m_active_dma_incd[ch] == 2 ? (size == 3 ? 16 : bytes) : 0);
	auto const invalid = [bytes] (uint32_t address)
	{
		return (address & (bytes - 1)) || (address >= 0xffffff00 && bytes == 1) || (address >= 0xfffffe00 && address < 0xffffff00 && bytes == 4);
	};
	if ((!input && invalid(src)) || ((!single || input) && invalid(dst)))
	{
		m_dmaor |= 4;
		sh2_dmac_check(0); sh2_dmac_check(1);
		return;
	}
	if (!m_dma_fifo_data_available_cb.isnull() && !m_dma_fifo_data_available_cb(src, dst, 0, size))
	{
		m_dma_timer_active[ch] = 2;
		m_dma_current_active_timer[ch]->adjust(attotime::never);
		dma_update_halt();
		return;
	}
	m_dma_owner = ch;
	m_dma_unit_control = control;
	m_dma_unit_src = src; m_dma_unit_dst = dst;
	m_dma_src_delta = input ? 0 : size == 3 ? 16 : m_active_dma_incs[ch] == 1 ? int(bytes) : m_active_dma_incs[ch] == 2 ? -int(bytes) : 0;
	m_dma_dst_delta = single && !input ? 0 : m_active_dma_incd[ch] == 1 ? int(size == 3 ? 16 : bytes) : m_active_dma_incd[ch] == 2 ? -int(size == 3 ? 16 : bytes) : 0;
	m_dma_count_delta = size == 3 ? std::min(m_active_dma_count[ch], 4U) : 1;
	std::fill(std::begin(m_dma_data), std::end(m_dma_data), 0);
	m_dma_committed = m_dma_cancelled = false;
	m_dma_ack_high[ch] = BIT(control, 7);
	m_dma_bus_end = machine().time() + dma_unit_time(src, dst, size == 3 ? m_dma_count_delta * 4 : bytes, size == 3);
	// A level burst has already accepted requests ahead of its first DACK
	// (9.3.7 figs. 9.46/47: three single; 9.50/51: two dual).
	if (!BIT(control, 9) && !m_dmac[ch].drcr && !BIT(control, 6))
	{
		if (m_dma_dreq[ch] == BIT(control, 5) && BIT(control, 4))
			m_dma_requests[ch] = single ? 3 : 2;
		if (m_dma_requests[ch]) --m_dma_requests[ch];
	}
	else m_dma_requests[ch] = 0;
	if (!BIT(control, 9) && !m_dmac[ch].drcr && BIT(control, 6))
	{
		m_dma_edge[ch] = false;
		m_dma_edge_burst[ch] = BIT(control, 4);
	}
	m_dma_detect_after[ch] = (m_dma_ack_count[ch] ? m_dma_ack_start[ch][0] : machine().time()) + cycles_to_attotime(2);
	if (!m_dma_dack[ch].isunset()) dma_dack_tick(ch);
	m_dma_staged = !m_dma_dack[ch].isunset() || (single && (!m_dma_read[ch].isunset() || !m_dma_write[ch].isunset()));
	if (!m_dma_staged)
	{
		while (m_dma_step < m_dma_step_count) dma_run_step(ch, m_dma_step++);
		dma_commit_unit(ch);
	}
	for (unsigned other = 0; other < 2; ++other)
		m_dma_current_active_timer[other]->adjust(attotime::never);
	m_dma_current_active_timer[ch]->adjust(m_dma_staged ? attotime::zero : m_dma_bus_end - machine().time(), ch);
	dma_update_halt();
}

TIMER_CALLBACK_MEMBER(sh7604_device::sh2_dma_current_active_callback)
{
	attotime const now = machine().time();
	if (m_standby || BIT(m_sbycr, 4)) return;
	if (m_dma_owner >= 0)
	{
		unsigned const ch = m_dma_owner;
		while (!m_dma_committed && m_dma_step < m_dma_step_count && m_dma_steps[m_dma_step].start <= now)
			dma_run_step(ch, m_dma_step++);
		if (!m_dma_committed && m_dma_step == m_dma_step_count) dma_commit_unit(ch);
		if (now < m_dma_bus_end)
		{
			attotime const next = m_dma_committed ? m_dma_bus_end : m_dma_steps[m_dma_step].start;
			m_dma_current_active_timer[ch]->adjust(std::max(attotime::zero, next - now), ch);
			return;
		}
		m_dma_owner = -1;
		m_dma_priority = ch ^ 1;
		m_dma_ack_count[ch] = 0;
		dma_dack_drive(ch, !m_dma_ack_high[ch]);
		if (!m_active_dma_count[ch])
		{
			// A final completed unit still sets TE if NMIF/AE/DME ended the
			// transfer at this boundary (9.3.8); DE forced stop does not.
			if (BIT(m_dmac[ch].chcr, 0)) m_dmac[ch].chcr |= 2;
			m_dma_timer_active[ch] = 0;
			m_dma_edge_burst[ch] = false;
			m_dma_requests[ch] = 0;
			sh2_recalc_irq();
		}
		else if (m_dma_cancelled) m_dma_timer_active[ch] = 0;
		else
		{
			m_dma_ready[ch] = now;
			if (!BIT(m_dmac[ch].chcr, 9) && !m_dmac[ch].drcr && !BIT(m_dmac[ch].chcr, 4))
				m_dma_ready[ch] = std::max(now, m_dma_detect_after[ch] + cycles_to_attotime(3));
		}
	}
	bool ready[2]{};
	attotime next = attotime::never;
	for (unsigned ch = 0; ch < 2; ++ch)
	{
		m_dma_current_active_timer[ch]->adjust(attotime::never);
		if (!m_dma_timer_active[ch]) continue;
		if (!(m_dmac[ch].chcr & m_dmaor & 1) || (m_dmaor & 6)) { sh2_dmac_check(ch); continue; }
		if (!sci_dma_requested(ch) || (!m_dma_fifo_data_available_cb.isnull() &&
			!m_dma_fifo_data_available_cb(m_active_dma_src[ch], m_active_dma_dst[ch], 0, m_active_dma_size[ch])))
		{ m_dma_timer_active[ch] = 2; continue; }
		m_dma_timer_active[ch] = 1;
		if (m_dma_ready[ch] <= now) ready[ch] = true;
		else next = std::min(next, m_dma_ready[ch]);
	}
	if (ready[0] || ready[1])
	{
		unsigned const preferred = BIT(m_dmaor, 3) ? m_dma_priority : (m_active_dma_steal[0] ? 0 : m_dma_priority);
		unsigned const ch = ready[preferred] ? preferred : preferred ^ 1;
		sh2_do_dma(ch);
		// An unavailable FIFO/error must not prevent the other channel running.
		if (m_dma_owner < 0)
			m_dma_current_active_timer[ch ^ 1]->adjust(attotime::zero, ch ^ 1);
	}
	else if (!next.is_never()) m_dma_current_active_timer[0]->adjust(next - now, 0);
	dma_update_halt();
}

void sh7604_device::sh2_dmac_check(int ch)
{
	bool const enabled = (m_dmac[ch].chcr & m_dmaor & 1) && !(m_dmaor & 6) && !(m_dmac[ch].chcr & 2);
	if (!enabled)
	{
		m_dma_edge[ch] = m_dma_edge_burst[ch] = false;
		m_dma_requests[ch] = 0;
		if (m_dma_owner == ch)
			m_dma_cancelled = true; // finish the accepted read/write unit, then stop
		else { m_dma_timer_active[ch] = 0; m_dma_current_active_timer[ch]->adjust(attotime::never); }
		dma_update_halt();
		return;
	}
	if (m_standby || BIT(m_sbycr, 4)) return;
	if (!sci_dma_requested(ch)) return;
	if (!m_dma_timer_active[ch])
	{
		uint32_t const control = m_dmac[ch].chcr;
		bool const single = BIT(control, 3), input = single && BIT(control, 8);
		m_active_dma_incs[ch] = input ? 0 : (control >> 12) & 3;
		m_active_dma_incd[ch] = single && !input ? 0 : (control >> 14) & 3;
		m_active_dma_size[ch] = (control >> 10) & 3;
		m_active_dma_steal[ch] = BIT(control, 4); // TB=1 is burst, not cycle-steal.
		if (m_active_dma_incs[ch] == 3 || m_active_dma_incd[ch] == 3 || (single && (m_active_dma_size[ch] == 3 || BIT(control, 9) || m_dmac[ch].drcr)))
		{
			LOG("SH7604 DMA: prohibited address/request configuration on channel %d\n", ch);
			return;
		}
		m_active_dma_src[ch] = m_dmac[ch].sar < 0xe0000000 ? m_dmac[ch].sar & m_am : m_dmac[ch].sar;
		m_active_dma_dst[ch] = m_dmac[ch].dar < 0xe0000000 ? m_dmac[ch].dar & m_am : m_dmac[ch].dar;
		m_active_dma_count[ch] = m_dmac[ch].tcr ? m_dmac[ch].tcr : 0x1000000;
		m_dma_ready[ch] = machine().time() + cycles_to_attotime(BIT(control, 9) || m_dmac[ch].drcr ? 2 : 3);
		m_dma_timer_active[ch] = 1;
	}
	else if (m_dma_timer_active[ch] == 2)
	{
		m_dma_timer_active[ch] = 1;
		m_dma_ready[ch] = std::max(m_dma_ready[ch], machine().time() + cycles_to_attotime(BIT(m_dmac[ch].chcr, 9) || m_dmac[ch].drcr ? 2 : 3));
	}
	if (m_dma_owner < 0 && m_dma_timer_active[ch] == 1)
		m_dma_current_active_timer[ch]->adjust(std::max(attotime::zero, m_dma_ready[ch] - machine().time()), ch);
	dma_update_halt();
}

void sh7604_device::dma_request_w(unsigned ch, int level)
{
	assert(ch < 2);
	level = !!level;
	m_dma_dreq_driven[ch] = true;
	if (m_dma_dreq[ch] == level) return;
	m_dma_dreq[ch] = level;
	uint32_t const control = m_dmac[ch].chcr;
	if (m_standby || BIT(m_sbycr, 4) || !(control & m_dmaor & 1) || (m_dmaor & 6) || BIT(control, 1) || BIT(control, 9) || m_dmac[ch].drcr || level != BIT(control, 5)) return;
	if (BIT(control, 6))
	{
		if (m_dma_edge_burst[ch] || machine().time() < m_dma_detect_after[ch]) return;
		m_dma_edge[ch] = true;
	}
	else m_dma_requests[ch] = std::max(m_dma_requests[ch], 1U);
	sh2_dmac_check(ch);
}

// Request/acknowledgement is independent of the CPU interrupt mask (9.3.2).
bool sh7604_device::sci_dma_requested(int ch) const
{
	if (BIT(m_dmac[ch].chcr, 9)) return true;
	switch (m_dmac[ch].drcr)
	{
	case 0:
		// Preserve the existing 32X FIFO connection as a board request adapter;
		// a real pin connection supersedes it. Unconnected Saturn pins are high.
		if (!m_dma_dreq_driven[ch] && !m_dma_fifo_data_available_cb.isnull())
			return m_dma_fifo_data_available_cb(m_dmac[ch].sar & m_am, m_dmac[ch].dar & m_am, 0, (m_dmac[ch].chcr >> 10) & 3) != 0;
		return BIT(m_dmac[ch].chcr, 6) ? m_dma_edge[ch] || m_dma_edge_burst[ch] : m_dma_requests[ch] || m_dma_dreq[ch] == BIT(m_dmac[ch].chcr, 5);
	case 1: return !m_standby && !BIT(m_sbycr, 0) && (m_scr & m_ssr & 0x40);
	case 2: return !m_standby && !BIT(m_sbycr, 0) && (m_scr & m_ssr & 0x80);
	default: return false;
	}
}

void sh7604_device::sci_reset()
{
	m_smr = m_scr = m_rdr = m_ssr_read = 0;
	m_brr = m_tdr = 0xff;
	m_ssr = 0x84;
	m_sci_busy = m_tx_prefetched = m_rx_busy = false;
	m_tx_frame = 0;
	m_tx_bit = m_tx_bits = m_tx_stop = m_tx_format = m_tx_data = m_tx_mpbt = m_tx_ext_count = 0;
	m_rsr = m_rx_stage = m_rx_format = m_rx_parity = m_rx_errors = m_rx_mp = m_rx_ext_count = 0;
	m_sci_timer->adjust(attotime::never);
	m_sci_rx_timer->adjust(attotime::never);
	m_sci_clock_timer->adjust(attotime::never);
	sci_drive_txd(1);
	sci_drive_sck(1);
}

unsigned sh7604_device::sci_bit_clocks() const
{
	// Tables 13.3/13.4: phi / (128 or 16 * (BRR+1) * 4^CKS).
	return ((m_smr & 0x80) ? 16U : 128U) * (unsigned(m_brr) + 1) * (1U << (2 * (m_smr & 3)));
}

void sh7604_device::sci_drive_txd(int state)
{
	if (m_sci_txd_level != state)
	{
		m_sci_txd_level = state;
		m_sci_txd(state);
	}
}

void sh7604_device::sci_drive_sck(int state)
{
	if (m_sci_sck_level != state)
	{
		m_sci_sck_level = state;
		m_sci_sck(state);
	}
}

void sh7604_device::sci_reclock()
{
	if (m_standby || BIT(m_sbycr, 0))
	{
		m_sci_timer->adjust(attotime::never);
		m_sci_rx_timer->adjust(attotime::never);
		m_sci_clock_timer->adjust(attotime::never);
		return;
	}

	if (m_smr & 0x80)
	{
		m_sci_clock_timer->adjust(attotime::never);
		m_sci_rx_timer->adjust(attotime::never);
		bool const active = !(m_scr & 2) && !(m_ssr & 0x38) &&
			((m_scr & 0x10) || ((m_scr & 0x20) && (m_sci_busy || m_tx_prefetched || !(m_ssr & 0x80))));
		if (active)
		{
			if (!m_sci_timer->enabled() || m_sci_timer->expire().is_never())
				m_sci_timer->adjust(cycles_to_attotime(sci_bit_clocks() / 2));
		}
		else
		{
			m_sci_timer->adjust(attotime::never);
			if (!(m_scr & 2))
				sci_drive_sck(1);
		}
	}
	else
	{
		if (!m_sci_busy || !(m_scr & 0x20) || (m_scr & 2))
			m_sci_timer->adjust(attotime::never);
		else if (!m_sci_timer->enabled() || m_sci_timer->expire().is_never())
			m_sci_timer->adjust(cycles_to_attotime(sci_bit_clocks()));
		if ((m_scr & 3) == 1)
		{
			if (!m_sci_clock_timer->enabled() || m_sci_clock_timer->expire().is_never())
				m_sci_clock_timer->adjust(cycles_to_attotime(sci_bit_clocks() / 2));
		}
		else
		{
			m_sci_clock_timer->adjust(attotime::never);
			sci_drive_sck(1);
		}
	}
}

void sh7604_device::sci_update()
{
	sci_reclock();
	sh2_recalc_irq();
	for (int channel = 0; channel < 2; channel++)
		sh2_dmac_check(channel);
}

void sh7604_device::sci_load_tsr()
{
	m_tsr = m_tdr;
	m_tx_mpbt = m_ssr & 1;
	m_tx_prefetched = true;
	m_ssr |= 0x80;
	m_ssr_read &= ~0x80;
}

// Pin clocks and framing replace the former byte-completion HACK.
void sh7604_device::sci_start()
{
	if (m_standby || BIT(m_sbycr, 0) || m_sci_busy || !(m_scr & 0x20) ||
		((m_smr & 0x80) && (m_ssr & 0x38)) || (!m_tx_prefetched && (m_ssr & 0x80)))
		return;
	if (!m_tx_prefetched)
		sci_load_tsr();
	m_tx_prefetched = false;
	m_sci_busy = true;
	m_tx_format = m_smr;
	m_tx_bit = m_tx_ext_count = 0;
	m_tx_data = m_tsr;
	if (m_tx_format & 0x80)
	{
		m_tx_frame = m_tx_data;
		m_tx_bits = 8;
		m_tx_stop = 7;
	}
	else
	{
		unsigned const bits = (m_tx_format & 0x40) ? 7 : 8;
		m_tx_data &= (1U << bits) - 1;
		m_tx_frame = uint32_t(m_tx_data) << 1; // start bit is zero
		m_tx_stop = 1 + bits;
		if (m_tx_format & 0x24)
		{
			unsigned parity = 0;
			for (unsigned i = 0; i < bits; i++)
				parity ^= BIT(m_tx_data, i);
			unsigned const extra = (m_tx_format & 4) ? m_tx_mpbt : (parity ^ BIT(m_tx_format, 4));
			m_tx_frame |= extra << m_tx_stop++;
		}
		unsigned const stops = (m_tx_format & 8) ? 2 : 1;
		m_tx_frame |= ((1U << stops) - 1) << m_tx_stop;
		m_tx_bits = m_tx_stop + stops;
		if (!(m_scr & 2))
			sci_tx_step();
	}
	sci_update();
}

void sh7604_device::sci_tx_step()
{
	if (!m_sci_busy)
		return;
	if (m_tx_bit == m_tx_bits)
	{
		sci_transmit_complete();
		return;
	}
	sci_drive_txd(BIT(m_tx_frame, m_tx_bit));
	// 13.3.2/13.3.4: the queue is inspected when the stop bit/MSB is output,
	// not after its interval. Keep the old frame data while preloading TSR.
	if (m_tx_bit == m_tx_stop)
	{
		if (!(m_ssr & 0x80))
			sci_load_tsr();
		else
			m_ssr |= 4;
		sci_update();
	}
	m_tx_bit++;
}

void sh7604_device::sci_transmit_complete()
{
	if (!m_sci_busy)
		return;
	m_sci_busy = false;
	m_sci_tx(m_tx_data);
	if (!(m_tx_format & 0x80))
	{
		sci_drive_txd(1);
		sci_start();
		if ((m_scr & 2) && m_sci_busy)
			sci_tx_step();
	}
	sci_update();
}

void sh7604_device::sci_rx_start()
{
	m_rx_busy = true;
	m_rx_format = m_smr;
	m_rsr = m_rx_stage = m_rx_parity = m_rx_errors = m_rx_mp = 0;
	m_rx_ext_count = 8; // external async clock is 16 times the bit rate
	if (!(m_rx_format & 0x80) && !(m_scr & 2))
		m_sci_rx_timer->adjust(cycles_to_attotime(sci_bit_clocks() / 2));
}

void sh7604_device::sci_sample_rx()
{
	if (!m_rx_busy)
		return;
	if (m_rx_format & 0x80)
	{
		m_rsr |= m_sci_rxd << m_rx_stage++;
		if (m_rx_stage < 8)
			return;
	}
	else
	{
		unsigned const bits = (m_rx_format & 0x40) ? 7 : 8;
		bool const extra = (m_rx_format & 0x24) != 0;
		if (!m_rx_stage)
		{
			if (m_sci_rxd) // reject a short/false start
				m_rx_busy = false;
			else
				m_rx_stage = 1;
			return;
		}
		if (m_rx_stage <= bits)
		{
			m_rsr |= m_sci_rxd << (m_rx_stage - 1);
			m_rx_parity ^= m_sci_rxd;
			m_rx_stage++;
			return;
		}
		if (extra && m_rx_stage == bits + 1)
		{
			if (m_rx_format & 4)
				m_rx_mp = m_sci_rxd;
			else if (m_sci_rxd != (m_rx_parity ^ BIT(m_rx_format, 4)))
				m_rx_errors |= 8;
			m_rx_stage++;
			return;
		}
		if (!m_sci_rxd)
			m_rx_errors |= 0x10;
	}
	m_rx_busy = false;
	sci_receive_byte(m_rsr, m_rx_errors, m_rx_mp);
}

void sh7604_device::sci_receive_byte(uint8_t data, uint8_t errors, bool mpb)
{
	if (m_standby || BIT(m_sbycr, 0) || !(m_scr & 0x10) || (m_ssr & 0x38))
		return;
	if ((m_rx_format & 0x84) == 4)
	{
		m_ssr = (m_ssr & ~2) | (mpb ? 2 : 0);
		if ((m_scr & 8) && !mpb)
		{
			sci_update(); // MPIE suppresses data and errors until an address frame
			return;
		}
		if (mpb)
			m_scr &= ~8;
	}
	if (m_ssr & 0x40)
		errors |= 0x20;
	m_ssr |= errors & 0x38;
	if (!(errors & 0x20))
		m_rdr = data;
	if (!errors)
		m_ssr |= 0x40;
	sci_update();
}

void sh7604_device::sci_sync_edge(bool rising)
{
	if (m_ssr & 0x38)
		return;
	if (!rising)
	{
		sci_start();
		if (m_sci_busy)
			sci_tx_step();
		if ((m_scr & 0x10) && !m_rx_busy)
			sci_rx_start();
	}
	else
	{
		if (m_rx_busy)
			sci_sample_rx();
		if (m_sci_busy && m_tx_bit == 8)
			sci_transmit_complete();
	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::sci_tx_complete)
{
	if (m_smr & 0x80)
	{
		if (m_sci_sck_level)
		{
			sci_sync_edge(false);
			sci_drive_sck(0);
		}
		else
		{
			sci_drive_sck(1);
			sci_sync_edge(true);
		}
	}
	else
		sci_tx_step();
	sci_reclock();
}

TIMER_CALLBACK_MEMBER(sh7604_device::sci_rx_tick)
{
	sci_sample_rx();
	if (m_rx_busy && m_rx_stage)
		m_sci_rx_timer->adjust(cycles_to_attotime(sci_bit_clocks()));
}

TIMER_CALLBACK_MEMBER(sh7604_device::sci_clock_tick)
{
	sci_drive_sck(!m_sci_sck_level);
	sci_reclock();
}

void sh7604_device::sci_rxd_w(int state)
{
	int const old = m_sci_rxd;
	m_sci_rxd = !!state;
	if (!m_standby && !BIT(m_sbycr, 0) && !(m_smr & 0x80) && (m_scr & 0x10) &&
		old && !m_sci_rxd && !m_rx_busy && !(m_ssr & 0x38))
		sci_rx_start();
}

void sh7604_device::sci_sck_w(int state)
{
	state = !!state;
	if (m_sci_sck_in == state)
		return;
	m_sci_sck_in = state;
	if (m_standby || BIT(m_sbycr, 0) || !(m_scr & 2))
		return;
	if (m_smr & 0x80)
		sci_sync_edge(state);
	else if (state)
	{
		if (m_sci_busy)
		{
			if (!m_tx_ext_count)
				sci_tx_step();
			m_tx_ext_count = (m_tx_ext_count + 1) & 15;
		}
		if (m_rx_busy && !--m_rx_ext_count)
		{
			sci_sample_rx();
			m_rx_ext_count = 16;
		}
	}
}

void sh7604_device::state_import(const device_state_entry &entry)
{
	if (entry.index() == STATE_GENPC || entry.index() == STATE_GENPCBASE)
		m_ubc_previous_pc = 0xffffffff;
	// Accept debugger SR changes at an instruction boundary, outside delay slots,
	// and without creating an unstacked exception that DRC entry discards.
	if (entry.index() == SH_SR)
	{
		m_test_irq = 1;
		return;
	}

	if (entry.index() == 0x108 || entry.index() == 0x109)
		dma_request_w(entry.index() - 0x108, m_sci_pin_value);
	else if (entry.index() == 0x104)
		frt_clock_w(m_sci_pin_value);
	else if (entry.index() == 0x107)
		set_frt_input(m_sci_pin_value);
	else if (entry.index() == 0x100)
		sci_rxd_w(m_sci_pin_value);
	else if (entry.index() == 0x101)
		sci_sck_w(m_sci_pin_value);
	else
		sh2_device::state_import(entry);
}

void sh7604_device::state_export(const device_state_entry &entry)
{
	if (entry.index() == 0x108 || entry.index() == 0x109)
		m_sci_pin_value = m_dma_dreq[entry.index() - 0x108];
	else if (entry.index() == 0x10a || entry.index() == 0x10b)
		m_sci_pin_value = dma_dack_level(entry.index() - 0x10a);
	else if (entry.index() == 0x104)
		m_sci_pin_value = m_frt_clock_input;
	else if (entry.index() == 0x107)
		m_sci_pin_value = m_frt_input;
	else if (entry.index() == 0x100)
		m_sci_pin_value = m_sci_rxd;
	else if (entry.index() == 0x101)
		m_sci_pin_value = m_sci_sck_in;
	else
		sh2_device::state_export(entry);
}

uint8_t sh7604_device::smr_r()
{
	return m_smr;
}

void sh7604_device::smr_w(uint8_t data)
{
	m_smr = data;
	if (!(m_scr & 0x30))
	{
		m_sci_timer->adjust(attotime::never);
		m_sci_clock_timer->adjust(attotime::never);
		sci_reclock();
	}
}

uint8_t sh7604_device::brr_r()
{
	return m_brr;
}

void sh7604_device::brr_w(uint8_t data)
{
	m_brr = data;
	if (!(m_scr & 0x30))
	{
		m_sci_clock_timer->adjust(attotime::never);
		sci_reclock();
	}
}

uint8_t sh7604_device::scr_r()
{
	return m_scr;
}

void sh7604_device::scr_w(uint8_t data)
{
	uint8_t const old = m_scr;
	m_scr = data;
	if (!(data & 0x20))
	{
		m_sci_busy = m_tx_prefetched = false;
		m_ssr |= 0x84;
		sci_drive_txd(1);
	}
	if (!(data & 0x10))
	{
		m_rx_busy = false;
		m_sci_rx_timer->adjust(attotime::never);
	}
	if (!(old & 0x10) && (data & 0x10) && !(m_smr & 0x80) && !m_sci_rxd && !(m_ssr & 0x38))
		sci_rx_start();
	sci_start();
	sci_update();
}

uint8_t sh7604_device::tdr_r()
{
	return m_tdr;
}

void sh7604_device::tdr_w(uint8_t data)
{
	m_tdr = data;
	if (m_sci_dma_access >= 0)
	{
		m_ssr &= ~0x84;
		m_ssr_read &= ~0x80;
		sci_start();
		sci_update();
	}
}

uint8_t sh7604_device::ssr_r()
{
	if (!machine().side_effects_disabled())
		m_ssr_read = m_ssr & 0xf8;
	return m_ssr;
}

void sh7604_device::ssr_w(uint8_t data)
{
	uint8_t const cleared = m_ssr & m_ssr_read & ~data & 0xf8;
	m_ssr = (m_ssr & ~cleared & 0xfe) | (data & 1);
	m_ssr_read = 0;
	if (cleared & 0x80)
		m_ssr &= ~4;
	if (!(m_scr & 0x20))
		m_ssr |= 0x84;
	if ((cleared & 0x38) && !(m_ssr & 0x38) && (m_scr & 0x10) && !(m_smr & 0x80) && !m_sci_rxd && !m_rx_busy)
		sci_rx_start();
	sci_start();
	sci_update();
}

uint8_t sh7604_device::rdr_r()
{
	if (m_sci_dma_access >= 0 && !machine().side_effects_disabled())
	{
		m_ssr &= ~0x40;
		m_ssr_read &= ~0x40;
		sci_update();
	}
	return m_rdr;
}

/*
 * FRC
 */

uint8_t sh7604_device::tier_r()
{
	return (m_tier & 0x8e) | 1;
}

void sh7604_device::tier_w(uint8_t data)
{
	sh2_timer_resync();
	m_tier = (data & 0x8e) | 1;
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint8_t sh7604_device::ftcsr_r()
{
	sh2_timer_resync();
	// The legacy status-observer HACK sees synchronized flags and counter.
	if (!m_ftcsr_read_cb.isnull() && !machine().side_effects_disabled())
		m_ftcsr_read_cb((((m_tier << 24) | (m_ftcsr << 16)) & 0xffff0000) | m_frc);

	// a status flag can only be cleared after it has been read as 1
	if (!machine().side_effects_disabled())
		m_ftcsr_read_flags = m_ftcsr & (ICF | OCFA | OCFB | OVF);

	return m_ftcsr;
}

void sh7604_device::ftcsr_w(uint8_t data)
{
	// writing 0 clears a status flag only if it was read as 1 beforehand
	// (saturn:doom slave does a word write to TIER/FTCSR, then polls ICF)
	const uint8_t clear = m_ftcsr_read_flags & ~data;
	m_ftcsr_read_flags &= ~clear;

	sh2_timer_resync();
	m_ftcsr = (m_ftcsr & ~clear & (ICF | OCFA | OCFB | OVF)) | (data & CCLRA);
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint16_t sh7604_device::frc_r(offs_t offset, uint16_t mem_mask)
{
	sh2_timer_resync();
	if (machine().side_effects_disabled())
		return m_frc;
	if (ACCESSING_BITS_8_15)
		m_frt_temp = m_frc;
	return (m_frc & 0xff00) | m_frt_temp;
}

void sh7604_device::frc_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	sh2_timer_resync(ACCESSING_BITS_0_7 ? 1 : 0);
	// High-byte writes only load TEMP; low-byte writes commit both bytes.
	if (ACCESSING_BITS_8_15)
		m_frt_temp = data >> 8;
	if (ACCESSING_BITS_0_7 && m_frt_clear_cycle != frt_cycles())
		m_frc = (uint16_t(m_frt_temp) << 8) | (data & 0xff);
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint16_t sh7604_device::ocra_b_r()
{
	return (m_tocr & 0x10) ? m_ocrb : m_ocra;
}

void sh7604_device::ocra_b_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	sh2_timer_resync(ACCESSING_BITS_0_7 ? ((m_tocr & 0x10) ? 3 : 2) : 0);
	if (ACCESSING_BITS_8_15)
		m_frt_temp = data >> 8;
	if (ACCESSING_BITS_0_7)
	{
		uint16_t const value = (uint16_t(m_frt_temp) << 8) | (data & 0xff);
		if (m_tocr & 0x10)
			m_ocrb = value;
		else
			m_ocra = value;
	}
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint8_t sh7604_device::frc_tcr_r()
{
	return m_frc_tcr & 0x83;
}

void sh7604_device::frc_tcr_w(uint8_t data)
{
	sh2_timer_resync();
	uint64_t const now = frt_cycles() - m_frt_epoch;
	auto const clock_level = [this, now](unsigned select) { return select == 3 ? !m_frt_clock_input : BIT(now, div_tab[select] - 1); };
	bool const before = clock_level(m_frc_tcr & 3);
	m_frc_tcr = data & 0x83;
	// 11.7(5): changing a high selected clock to a low clock is an edge.
	if (before && !clock_level(m_frc_tcr & 3))
		frt_advance(1);
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint8_t sh7604_device::tocr_r()
{
	return (m_tocr & 0x13) | 0xe0;
}

void sh7604_device::tocr_w(uint8_t data)
{
	sh2_timer_resync();
	// The legacy output-level HACK stored OLVL without driving the compare pins.
	m_tocr = data & 0x13;
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint16_t sh7604_device::frc_icr_r(offs_t offset, uint16_t mem_mask)
{
	if (machine().side_effects_disabled())
		return m_frc_icr;
	if (ACCESSING_BITS_8_15)
	{
		m_frt_icr_read_cycle = frt_cycles();
		m_frt_temp = m_frc_icr;
	}
	return (m_frc_icr & 0xff00) | m_frt_temp;
}

/*
 * INTC
 */

uint16_t sh7604_device::intc_icr_r()
{
	uint16_t const nmilv = m_nmi_pin == ASSERT_LINE ? 0 : 0x8000;
	return nmilv | (m_intc_icr & 0x0101);
}

void sh7604_device::intc_icr_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_intc_icr);
	m_nmie = BIT(m_intc_icr, 8);
	m_vecmd = BIT(m_intc_icr, 0);
}

uint16_t sh7604_device::ipra_r()
{
	return m_ipra & 0xfff0;
}

void sh7604_device::ipra_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_ipra);
	m_irq_level.divu = (m_ipra >> 12) & 0xf;
	m_irq_level.dmac = (m_ipra >> 8) & 0xf;
	m_irq_level.wdt = (m_ipra >> 4) & 0xf;
	sh2_recalc_irq();
}

uint16_t sh7604_device::iprb_r()
{
	return m_iprb & 0xff00;
}

void sh7604_device::iprb_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_iprb);
	m_irq_level.sci = (m_iprb >> 12) & 0xf;
	m_irq_level.frc = (m_iprb >> 8) & 0xf;
	sh2_recalc_irq();
}

uint16_t sh7604_device::vcra_r()
{
	return m_vcra & 0x7f7f;
}

void sh7604_device::vcra_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_vcra);
	// ...
	sh2_recalc_irq();
}

uint16_t sh7604_device::vcrb_r()
{
	return m_vcrb & 0x7f7f;
}

void sh7604_device::vcrb_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_vcrb);
	// ...
	sh2_recalc_irq();
}

uint16_t sh7604_device::vcrc_r()
{
	return m_vcrc & 0x7f7f;
}

void sh7604_device::vcrc_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_vcrc);
	m_irq_vector.fic = (m_vcrc >> 8) & 0x7f;
	m_irq_vector.foc = (m_vcrc >> 0) & 0x7f;
	sh2_recalc_irq();
}

uint16_t sh7604_device::vcrd_r()
{
	return m_vcrd & 0x7f00;
}

void sh7604_device::vcrd_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_vcrd);
	m_irq_vector.fov = (m_vcrd >> 8) & 0x7f;
	sh2_recalc_irq();
}

uint16_t sh7604_device::vcrwdt_r()
{
	return m_vcrwdt & 0x7f7f;
}

void sh7604_device::vcrwdt_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_vcrwdt);
	// ...
	sh2_recalc_irq();
}

// 10.2.4/B.2 charts and YabauseUT div_mirror_test support 16-bit read-back.
// Only bits 6-0 select the vector; 10.2.4 reserved-read-zero prose conflicts.
uint32_t sh7604_device::vcrdiv_r()
{
	divu_wait();
	return m_vcrdiv & 0xffff;
}

void sh7604_device::vcrdiv_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	COMBINE_DATA(&m_vcrdiv);
	// The DIVU priority comes from IPRA; only the vector comes from VCRDIV.
	m_irq_vector.divu = m_vcrdiv & 0x7f;
	sh2_recalc_irq();
}

/*
 * DIVU
 */

uint32_t sh7604_device::dvcr_r()
{
	divu_wait();
	return (m_divu_ovfie << 1) | (m_divu_ovf << 0);
}

void sh7604_device::dvcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	if (ACCESSING_BITS_0_7)
	{
		// both bits are regular r/w
		// - vblokbrk/sarukani writes a '0' to clear a divide by zero OVF when beating
		//   a stage with game timer <= 10
		m_divu_ovf = BIT(data, 0);
		m_divu_ovfie = BIT(data, 1);
		sh2_recalc_irq();
	}
}

uint32_t sh7604_device::dvsr_r()
{
	divu_wait();
	return m_dvsr;
}

void sh7604_device::dvsr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	COMBINE_DATA(&m_dvsr);
}

uint32_t sh7604_device::dvdnt_r()
{
	divu_wait();
	return m_dvdntl;
}

void sh7604_device::dvdnt_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	// writing DVDNT also writes DVDNTL, and its MSB is extended into DVDNTH (Hardware Manual 10.2.2)
	COMBINE_DATA(&m_dvdntl);
	LOG("SH2 div32+mod %d/%d\n", int32_t(m_dvdntl), int32_t(m_dvsr));
	// the dividend is sign-extended into DVDNTH, so this is a 64-bit division of a 32-bit value
	divu_start(int32_t(m_dvdntl));
}

uint32_t sh7604_device::dvdnth_r()
{
	divu_wait();
	return m_dvdnth;
}

uint32_t sh7604_device::dvdntl_r()
{
	divu_wait();
	return m_dvdntl;
}

void sh7604_device::dvdnth_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	COMBINE_DATA(&m_dvdnth);
}

void sh7604_device::dvdntl_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	COMBINE_DATA(&m_dvdntl);
	const int64_t dividend = int64_t((uint64_t(m_dvdnth) << 32) | m_dvdntl);
	LOG("SH2 div64+mod %d/%d\n", dividend, int32_t(m_dvsr));
	divu_start(dividend);
}

// These are writable result copies, not alternate dividend/start ports.
// YabauseUT checks their write/read access and replacement by both divisions;
// Yabause and Mednafen retain them separately from the dividend registers.
uint32_t sh7604_device::divu_shadow_r(offs_t offset)
{
	divu_wait();
	return m_divu_shadow[offset & 1];
}

void sh7604_device::divu_shadow_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	divu_wait();
	COMBINE_DATA(&m_divu_shadow[offset & 1]);
}

// The unit takes 39 cycles from the write of the dividend (Hardware Manual 10.3), 6 when the
// operation overflows. An access to any of its registers while it runs waits for the end of the
// operation (10.4.1; MiSTer DIVU.sv holds the bus with IBUS_BUSY while STEP is running), so the
// result is computed at once and the CPU pays the time when it comes for it. The overflow flag,
// and the interrupt it requests, appear when the operation ends. The time is the CPU's own,
// including the cycles of the running sequence that the DRC has not taken off yet.
void sh7604_device::divu_wait()
{
	if (!m_divu_busy)
		return;
	attotime const now = local_time() + cycles_to_attotime(m_bus_pending);
	if (m_divu_done > now)
	{
		attotime const wait = m_divu_done - now;
		uint64_t cycles = attotime_to_cycles(wait);
		if (cycles_to_attotime(cycles) < wait)
			cycles++;
		m_sh2_state->icount -= int(cycles);
	}
	divu_finish();
}

void sh7604_device::divu_finish()
{
	m_divu_busy = false;
	m_divu_timer->adjust(attotime::never);
	if (m_divu_ovf_pending)
	{
		m_divu_ovf_pending = false;
		m_divu_ovf = true;
		sh2_recalc_irq();
	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::divu_timer_cb)
{
	divu_finish();
}

void sh7604_device::divu_start(int64_t dividend)
{
	divu_finish();
	const int32_t divisor = m_dvsr;
	if (divisor && ((dividend != std::numeric_limits<int64_t>::min()) || (divisor != -1)))
	{
		const int64_t quotient = dividend / divisor;
		if (quotient == int32_t(quotient))
		{
			m_dvdntl = uint32_t(quotient);
			m_dvdnth = uint32_t(dividend % divisor);
			divu_run(39);
			return;
		}
	}

	// Overflow (zero divisor, or a quotient outside the signed 32-bit range): the operation
	// ends after three steps of division, leaving the partial remainder in DVDNTH. With OVFIE
	// clear, DVDNTL is set to the maximum value when a positive quotient overflows and to the
	// minimum value when a negative one does (SH7604 manual 10.3.3 and table 10.2).
	int64_t remainder = dividend >> 32;
	uint32_t quotient = uint32_t(dividend);
	for (int i = 0; i < 3; i++)
	{
		const bool subtract = (remainder < 0) == (divisor < 0);
		remainder = (remainder << 1) | BIT(quotient, 31);
		quotient <<= 1;
		remainder += subtract ? -int64_t(divisor) : int64_t(divisor);
		quotient |= ((remainder < 0) == (divisor < 0)) ? 1 : 0;
	}
	const bool negative = (dividend < 0) != (divisor < 0);
	m_dvdnth = uint32_t(remainder);
	m_dvdntl = m_divu_ovfie ? quotient : negative ? 0x80000000 : 0x7fffffff;
	m_divu_ovf_pending = true;
	divu_run(6);
}

void sh7604_device::divu_run(unsigned cycles)
{
	m_divu_shadow[0] = m_dvdnth;
	m_divu_shadow[1] = m_dvdntl;
	m_divu_busy = true;
	m_divu_done = local_time() + cycles_to_attotime(m_bus_pending + cycles);
	m_divu_timer->adjust(m_divu_done - machine().time());
}

/*
 * UBC
 */

// The former buffer-storage HACK is replaced by chapter 6 bus comparisons.
// Chapter 6: UBC registers are CPU-only, and byte accesses are prohibited.
uint16_t sh7604_device::ubc_r(offs_t offset, uint16_t mem_mask)
{
	if (mem_mask != 0xffff || m_sci_dma_access >= 0 || (offset >= 21 && offset <= 23) || offset == 5)
		return 0;
	if (!machine().side_effects_disabled())
		ubc_commit(); // documented dummy read synchronizes changed settings
	return m_ubc[offset];
}

void sh7604_device::ubc_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (mem_mask != 0xffff || m_sci_dma_access >= 0 || (offset >= 21 && offset <= 23) || offset == 5)
		return;
	uint16_t const mask = (offset == 4 || offset == 20) ? 0x00ff : offset == 28 ? 0xf4dc : 0xffff;
	m_ubc[offset] = data & mask;
	m_ubc_dirty = true;
	m_ubc_ready = local_time() + cycles_to_attotime(3 + (m_isdrc ? m_bus_pending : 0));
	// Gate generated code immediately; comparison settings retain their latency.
	m_instruction_monitor = 1;
}

void sh7604_device::ubc_commit()
{
	if (m_ubc_dirty)
	{
		std::copy(std::begin(m_ubc), std::end(m_ubc), std::begin(m_ubc_live));
		m_ubc_dirty = false;
		if (!(m_ubc_live[28] & 0xc000))
			m_ubc_sequence = false;
	}
	m_instruction_monitor = (m_ubc_live[4] || ((m_ubc_live[28] & 0x1000) && m_ubc_live[20]) || m_ubc_pending || m_ubc_fetch[4] || ((m_ubc_fetch[28] & 0x1000) && m_ubc_fetch[20]));
}

bool sh7604_device::ubc_compare(uint32_t address, uint32_t data, unsigned size, bool write, bool fetch, bool peripheral, bool external, bool after)
{
	// This gate includes live and prefetched comparisons, pending exceptions,
	// and unsynchronized register writes. With all of them inactive there is
	// no comparator work to perform on a CPU or peripheral bus access.
	if (!m_instruction_monitor)
		return false;
	if (m_standby)
		return false;
	if (m_ubc_dirty && local_time() >= m_ubc_ready)
		ubc_commit();
	uint16_t const *const settings = fetch ? m_ubc_fetch : m_ubc_live;
	bool const modern = BIT(settings[28], 12);
	if (external && (!modern || !BIT(settings[28], 13)))
		return false;
	bool matched[2]{};
	bool const sequenced = modern && BIT(settings[28], 4);
	bool const prior_sequence = (fetch && after) ? m_ubc_fetch_sequence : m_ubc_sequence;
	for (unsigned channel = 0; channel < (modern ? 2U : 1U); channel++)
	{
		unsigned const base = channel * 16;
		uint16_t const bus = settings[base + 4];
		if (!(bus & (peripheral ? 0x80 : 0x40)) || !(bus & (fetch ? 0x10 : 0x20)) || !(bus & (write ? 8 : 4)))
			continue;
		unsigned const operand = bus & 3;
		if (!external && operand && operand != (size == 4 ? 3 : size))
			continue;
		if (fetch && modern && BIT(settings[28], channel ? 2 : 10) != after)
			continue;
		uint32_t const bar = (uint32_t(settings[base]) << 16) | settings[base + 1];
		uint32_t mask = (uint32_t(settings[base + 2]) << 16) | settings[base + 3];
		if (modern && !fetch && !external)
			mask |= size - 1;
		if ((bar ^ address) & ~mask)
			continue;
		if (channel && BIT(settings[28], 3) && !fetch && !external)
		{
			if (!operand)
				continue; // data comparison requires an explicitly selected size
			uint32_t const expected = (uint32_t(settings[24]) << 16) | settings[25];
			uint32_t const ignored = (uint32_t(settings[26]) << 16) | settings[27];
			uint32_t const actual = size == 1 ? (data & 0xff) * 0x101 : data;
			uint32_t const valid = size == 4 ? 0xffffffff : 0xffff;
			if ((expected ^ actual) & ~ignored & valid)
				continue;
		}
		matched[channel] = true;
	}
	bool interrupt = false;
	for (unsigned channel = 0; channel < 2; channel++)
	{
		if (!matched[channel] || (sequenced && channel && !prior_sequence))
			continue;
		if (modern)
		{
			uint16_t const flag = (peripheral ? 0x4000 : 0x8000) >> (channel * 8);
			m_ubc[28] |= flag;
			m_ubc_live[28] |= flag;
		}
		if (sequenced && !channel)
			m_ubc_sequence = true;
		else
			interrupt = true;
	}
	if (interrupt)
	{
		m_ubc_pending = true;
		m_instruction_monitor = 1;
		sh2_recalc_irq();
	}
	return interrupt;
}

void sh7604_device::ubc_accept()
{
	if (m_ubc_pending && !m_standby && !delay_pending() && !m_ubc_inhibit &&
		!m_sh2_state->pending_nmi && (m_sh2_state->sr & SH_I) < SH_I)
	{
		m_ubc_pending = false;
		sh2_exception_internal("UBC", 15, 12);
		sh2_recalc_irq();
	}
}

bool sh7604_device::instruction_access_valid(uint32_t address, unsigned size)
{
	// Table 4.6: bytes in the word/longword module area and longwords in
	// the byte/word module area are CPU address errors, not peripheral writes.
	if (!((size == 1 && address >= 0xffffff00) ||
		(size == 4 && address >= 0xfffffe00 && address < 0xffffff00)))
		return true;
	debugger_exception_hook(9);
	uint32_t const pc = delay_pending() ? m_sh2_state->pc - 2 : m_sh2_state->pc;
	m_sh2_state->m_delay = 0;
	m_zero_delay_pending = false;
	m_sh2_state->r[15] -= 4;
	write_long(m_sh2_state->r[15], m_sh2_state->sr);
	m_sh2_state->r[15] -= 4;
	write_long(m_sh2_state->r[15], pc);
	m_sh2_state->pc = read_long(m_sh2_state->vbr + 9 * 4) & m_am;
	m_sh2_state->icount -= 5;
	return false;
}

bool sh7604_device::instruction_before(uint32_t pc, uint16_t opcode)
{
	if (!sh2_device::instruction_before(pc, opcode))
		return false;
	if (m_ubc_dirty && local_time() >= m_ubc_ready)
		ubc_commit();
	bool const new_fetch = !(pc & 2) || m_ubc_previous_pc != pc - 2;
	if (new_fetch)
		std::copy(std::begin(m_ubc_live), std::end(m_ubc_live), std::begin(m_ubc_fetch));
	m_ubc_previous_pc = pc;
	if (!m_ubc_dirty)
		ubc_commit();
	if (!m_instruction_monitor)
		return true;
	m_ubc_fetch_sequence = m_ubc_sequence;
	bool const delayed = delay_pending();
	if (BIT(m_ubc_fetch[28], 12))
		ubc_compare(pc, opcode, 2, false, true, false);
	else if (new_fetch)
	{
		// SH7000 mode compares fetched instructions, including the other half
		// of the longword that a subsequent branch may never execute (6.3.8).
		ubc_compare(pc & ~3U, 0, 2, false, true, false);
		ubc_compare((pc & ~3U) + 2, 0, 2, false, true, false);
	}
	uint32_t const oldpc = m_sh2_state->pc;
	if (!delayed)
		ubc_accept();
	return oldpc == m_sh2_state->pc;
}

void sh7604_device::instruction_after(uint32_t pc, uint16_t opcode)
{
	if (!m_instruction_monitor)
		return;
	if (BIT(m_ubc_fetch[28], 12))
		ubc_compare(pc, opcode, 2, false, true, false, false, true);
	// LDC (including memory forms) inhibits interrupts through the next instruction.
	bool const ldc = ((opcode & 0xf00f) == 0x400e && ((opcode >> 4) & 15) <= 2) ||
		((opcode & 0xf00f) == 0x4007 && ((opcode >> 4) & 15) <= 2);
	m_ubc_inhibit = ldc;
	ubc_accept();
}

void sh7604_device::execute_run()
{
	// Finish an interpreter delay slot before returning to compiled code.
	if (m_instruction_monitor || (m_isdrc && delay_pending()))
		execute_monitored();
	else
		sh2_device::execute_run();
}

void sh7604_device::execute_monitored()
{
	bool const drc = m_isdrc;
	m_isdrc = false;
	m_bus_pending = 0;
	sh2_device::execute_run();
	m_isdrc = drc;
}

void sh7604_device::ubc_external_cycle(uint32_t address, bool write)
{
	if (m_instruction_monitor)
		ubc_compare(address & 0x07ffffff, 0, 1, write, false, true, true);
}

uint8_t sh7604_device::read_byte(offs_t offset)
{
	uint8_t const data = sh2_device::read_byte(offset);
	if (m_instruction_monitor)
		ubc_compare(offset, data, 1, false, false, false);
	return data;
}

uint16_t sh7604_device::read_word(offs_t offset)
{
	uint16_t const data = sh2_device::read_word(offset);
	if (m_instruction_monitor)
		ubc_compare(offset, data, 2, false, false, false);
	return data;
}

uint32_t sh7604_device::read_long(offs_t offset)
{
	uint32_t const data = sh2_device::read_long(offset);
	if (m_instruction_monitor)
		ubc_compare(offset, data, 4, false, false, false);
	return data;
}

void sh7604_device::write_byte(offs_t offset, uint8_t data)
{
	sh2_device::write_byte(offset, data);
	if (m_instruction_monitor)
		ubc_compare(offset, data, 1, true, false, false);
}

void sh7604_device::write_word(offs_t offset, uint16_t data)
{
	sh2_device::write_word(offset, data);
	if (m_instruction_monitor)
		ubc_compare(offset, data, 2, true, false, false);
}

void sh7604_device::write_long(offs_t offset, uint32_t data)
{
	sh2_device::write_long(offset, data);
	if (m_instruction_monitor)
		ubc_compare(offset, data, 4, true, false, false);
}

/*
 * WTC
 */

uint16_t sh7604_device::wtcnt_r(offs_t offset, uint16_t mem_mask)
{
	sh2_wtcnt_recalc();
	if (ACCESSING_BITS_8_15 && !machine().side_effects_disabled())
		m_wtcsr_ovf_read = BIT(m_wtcsr, 7);
	return ((m_wtcsr | 0x18) << 8) | (m_wtcnt & 0xff);
}

uint16_t sh7604_device::rstcsr_r(offs_t offset, uint16_t mem_mask)
{
	if (ACCESSING_BITS_0_7 && !machine().side_effects_disabled())
		m_rstcsr_wovf_read = BIT(m_rstcsr, 7);
	return (m_rstcsr & 0xe0) | 0x1f;
}

void sh7604_device::wtcnt_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	// The key and value must arrive in one word write (12.2.4).
	if (mem_mask != 0xffff)
		return;
	m_wtcw[0] = data;
	switch (m_wtcw[0] & 0xff00)
	{
		case 0x5a00:
			m_wtcnt = m_wtcw[0] & 0xff;
			if (m_wtcsr & 0x20)
				sh2_wdt_activate();
			break;
		case 0xa500:
			/*
			WTCSR
			x--- ---- Overflow in IT mode
			-x-- ---- Timer mode (0: IT 1: watchdog)
			--x- ---- Timer enable
			---1 1---
			---- -xxx Clock select
			*/
			sh2_wtcnt_recalc();
			// OVF is cleared by writing 0 after reading it as 1; a 1 leaves it as it is
			if (!(m_wtcw[0] & 0x80) && m_wtcsr_ovf_read)
				m_wtcsr &= 0x7f;
			m_wtcsr_ovf_read = false;
			m_wtcsr = (m_wtcsr & 0x80) | (m_wtcw[0] & 0x7f);
			if (m_wtcsr & 0x20)
				sh2_wdt_activate();
			else
			{
				m_wtcnt = 0;
				m_wdtimer->adjust(attotime::never);
			}
			sh2_recalc_irq();
			break;
	}
}

void sh7604_device::rstcsr_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	// The key and value must arrive in one word write (12.2.4).
	if (mem_mask != 0xffff)
		return;
	m_wtcw[1] = data;
	switch (m_wtcw[1] & 0xff00)
	{
		case 0xa500:
			// WOVF is cleared by writing 0 after reading it as 1
			if ((m_wtcw[1] & 0x80) == 0 && m_rstcsr_wovf_read)
				m_rstcsr &= 0x7f;
			m_rstcsr_wovf_read = false;
			break;
		case 0x5a00:
			m_rstcsr = (m_rstcsr & 0x80) | (m_wtcw[1] & 0x60);
			break;
	}
}

uint16_t sh7604_device::fmr_sbycr_r()
{
	return m_sbycr;
}

void sh7604_device::fmr_sbycr_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	switch (mem_mask)
	{
	case 0xff00: // FMR 8bit
		logerror("SH2 set clock multiplier x%d\n", 1 << ((data >> 8) & 3));
		break;
	case 0xffff: // FMR 16bit
		// SH7604 docs says FMR register must be set using 8-bit write, however at practice 16-bit works too.
		// has been verified for CPS3 custom SH2, SH7604 and SH7095 (clock multiplier feature is not officially documented for SH7095).
		logerror("SH2 set clock multiplier x%d\n", 1 << (data & 3));
		break;
	case 0x00ff: // SBYCR
	{
		uint8_t const old = m_sbycr;
		m_sbycr = (data & 0xdf) & ((m_wtcsr & 0x20) ? 0x7f : 0xff);
		module_standby(old);
		break;
	}
	}
}

uint8_t sh7604_device::ccr_r()
{
	return m_cache.ccr;
}

void sh7604_device::ccr_w(uint8_t data)
{
	/*
	    xx-- ---- Way 0/1
	    ---x ---- Cache Purge (CP), write only
	    ---- x--- Two-Way Mode (TW)
	    ---- -x-- Data Replacement Disable (OD)
	    ---- --x- Instruction Replacement Disable (ID)
	    ---- ---x Cache Enable (CE)
	*/
	m_cache.write_ccr(data);
}

// BCR1/BCR2 are really 16-bit wide, when accessed as dword the upper part is used as unlock
// method (0xa55axxxx) and reads back 0.
void sh7604_device::bsc_endian_update()
{
	unsigned const mode = m_bcr1 & 7;
	unsigned const width = (mode == 4 || mode == 5) ? (BIT(m_mcr, 6) ? 4 : 2) :
		((m_bcr2 >> 4) & 3) ? 1U << (((m_bcr2 >> 4) & 3) - 1) : 0;
	// Section 7.3.2 explicitly excludes eight-bit devices from endian mode.
	m_bus_endian_width = BIT(m_bcr1, 12) && width > 1 ? width : 0;
}

uint32_t sh7604_device::bcr1_r()
{
	return (m_bcr1 & 0x1ff7) | (m_is_slave ? 0x8000 : 0);
}

void sh7604_device::bcr1_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
	{
		m_bcr1 = data & 0x1ff7;
		bsc_endian_update();
	}
}

uint32_t sh7604_device::bcr2_r()
{
	return m_bcr2 & 0xfc;
}

void sh7604_device::bcr2_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
	{
		m_bcr2 = data & 0xfc;
		bsc_endian_update();
	}
}

uint32_t sh7604_device::wcr_r()
{
	return m_wcr & 0xffff;
}

void sh7604_device::wcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
		m_wcr = data & 0xffff;
}

uint32_t sh7604_device::mcr_r()
{
	return m_mcr & 0xfefc;
}

void sh7604_device::mcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
	{
		m_mcr = data & 0xfefc;
		bsc_endian_update();
	}
}

uint32_t sh7604_device::rtcsr_r()
{
	refresh_resync();
	if (!machine().side_effects_disabled())
		m_rtcsr_cmf_read = BIT(m_rtcsr, 7);
	return m_rtcsr & 0xf8;
}

void sh7604_device::rtcsr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
	{
		refresh_resync();
		uint32_t const old_select = m_rtcsr & 0x38;
		uint32_t const cmf = m_rtcsr & 0x80;
		m_rtcsr = (data & 0x78) | ((m_rtcsr_cmf_read && !(data & 0x80)) ? 0 : cmf);
		m_rtcsr_cmf_read = false;
		if ((m_rtcsr & 0x38) != old_select)
			m_refresh_phase = 0;
		refresh_activate();
		sh2_recalc_irq();
	}
}

uint32_t sh7604_device::rtcnt_r()
{
	refresh_resync();
	return m_rtcnt & 0xff;
}

void sh7604_device::rtcnt_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
	{
		refresh_resync();
		m_rtcnt = data & 0xff;
		refresh_activate();
	}
}

uint32_t sh7604_device::rtcor_r()
{
	return m_rtcor & 0xff;
}

void sh7604_device::rtcor_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// BSC registers accept only keyed longword writes (Hardware Manual 7.1.4).
	if (mem_mask == 0xffffffff && (data >> 16) == 0xa55a)
	{
		refresh_resync();
		m_rtcor = data & 0xff;
		refresh_activate();
	}
}

// Chapter 7.2: the refresh interval timer runs even with MCR.RFSH clear.
// Keep its counter lazy; only an unlatched enabled interrupt needs a scheduler
// event. SDRAM refresh polling must not introduce millions of host callbacks.
void sh7604_device::refresh_resync()
{
	// DRC sequence cycles are committed after the sequence. Include them at
	// a register access, as FRT/DIVU do, so both engines sample the same time.
	attotime const now = executing() ? local_time() + cycles_to_attotime(m_isdrc ? m_bus_pending : 0) : machine().time();
	unsigned const select = (m_rtcsr >> 3) & 7;
	static constexpr unsigned divisors[8] = { 0, 4, 16, 64, 256, 1024, 2048, 4096 };
	if (!select || !m_refresh_clockrate || m_standby)
	{
		m_refresh_epoch = now;
		return;
	}
	if (now <= m_refresh_epoch)
		return;
	attotime const elapsed = now - m_refresh_epoch;
	uint64_t const cycles = uint64_t(elapsed.seconds()) * m_refresh_clockrate + elapsed.attoseconds() / HZ_TO_ATTOSECONDS(m_refresh_clockrate);
	m_refresh_epoch += attotime::from_ticks(cycles, m_refresh_clockrate);
	uint64_t const total = cycles + m_refresh_phase;
	m_refresh_phase = total % divisors[select];
	uint64_t ticks = total / divisors[select];
	unsigned const distance = uint8_t(m_rtcor - m_rtcnt) ? uint8_t(m_rtcor - m_rtcnt) : 256;
	if (ticks >= distance)
	{
		ticks -= distance;
		m_rtcnt = ticks % (m_rtcor ? m_rtcor : 256);
		bool const new_match = !(m_rtcsr & 0x80);
		m_rtcsr |= 0x80;
		if (new_match)
			sh2_recalc_irq();
	}
	else
		m_rtcnt = (m_rtcnt + ticks) & 0xff;
}

void sh7604_device::refresh_activate()
{
	unsigned const select = (m_rtcsr >> 3) & 7;
	static constexpr unsigned divisors[8] = { 0, 4, 16, 64, 256, 1024, 2048, 4096 };
	if (!select || !clock() || m_standby || (m_rtcsr & 0xc0) != 0x40)
		m_refresh_timer->adjust(attotime::never);
	else
	{
		unsigned const distance = uint8_t(m_rtcor - m_rtcnt) ? uint8_t(m_rtcor - m_rtcnt) : 256;
		attotime const edge = m_refresh_epoch + attotime::from_ticks(distance * divisors[select] - m_refresh_phase, clock());
		m_refresh_timer->adjust(std::max(attotime::zero, edge - machine().time()));
	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::refresh_tick)
{
	refresh_resync();
	refresh_activate();
}

void sh7604_device::set_frt_input(int state)
{
	if (m_frt_input == state)
		return;

	m_frt_input = state;
	if (!clock() || m_standby || BIT(m_sbycr, 1))
		return;

	if (m_frc_tcr & 0x80)
	{
		if (state == CLEAR_LINE)
			return;
	}
	else
	{
		if (state == ASSERT_LINE)
			return;
	}

	if (frt_cycles() == m_frt_icr_read_cycle)
	{
		// 11.4.4: an upper ICR read delays capture by one f/4 drive clock.
		m_frt_capture_pending = true;
		m_frt_capture_clock_delay = cycles_to_attotime(4) * clock();
		attotime const now = executing() ? local_time() + cycles_to_attotime(m_isdrc ? m_bus_pending : 0) : machine().time();
		m_frt_capture_timer->adjust(now + cycles_to_attotime(4) - machine().time());
	}
	else
		frt_capture();
}

void sh7604_device::frt_capture()
{
	sh2_timer_resync();
	m_frc_icr = m_frc;
	m_ftcsr |= ICF;
	sh2_recalc_irq();
}

TIMER_CALLBACK_MEMBER(sh7604_device::frt_capture_callback)
{
	if (m_frt_capture_pending && clock() && !m_standby && !BIT(m_sbycr, 1))
	{
		m_frt_capture_pending = false;
		m_frt_capture_clock_delay = attotime::never;
		frt_capture();
	}
}

// The interrupt controller (Hardware Manual 5.2.5, table 5.4). Every on-chip source is a level
// held by its flag and enable bits; the highest priority level goes to the CPU with its vector
// number. Sources of the same level rank in the default priority order: DIVU, DMAC0, DMAC1, WDT,
// SCI (ERI, RXI, TXI, TEI), FRT (ICI, OCI, OVI). The first source of a level wins, so a later
// one needs a strictly higher level to replace it.
void sh7604_device::sh2_recalc_irq()
{
	int irq = 0;
	int vector = -1;
	auto const request = [&irq, &vector] (int level, int number)
	{
		if ((level & 15) > irq)
		{
			irq = level & 15;
			vector = number & 0x7f;
		}
	};

	if (m_ubc_pending)
		request(15, 12);

	// DIVU overflow
	if (m_divu_ovf && m_divu_ovfie)
		request(m_irq_level.divu, m_irq_vector.divu);

	// DMAC transfer end: requested while TE and IE are both set
	for (int ch = 0; ch < 2; ch++)
	{
		if ((m_dmac[ch].chcr & 6) == 6)
			request(m_irq_level.dmac, m_irq_vector.dmac[ch]);
	}

	// WDT interval
	if (m_wtcsr & 0x80)
		request(m_irq_level.wdt, (m_vcrwdt >> 8) & 0x7f);

	// BSC refresh compare shares the WDT priority, below WDT on a tie.
	if ((m_rtcsr & 0xc0) == 0xc0)
		request(m_irq_level.wdt, m_vcrwdt & 0x7f);

	// SCI default source priority: ERI, RXI, TXI, TEI.
	if ((m_scr & 0x40) && (m_ssr & 0x38))
		request(m_irq_level.sci, m_vcra >> 8);
	if ((m_scr & m_ssr & 0x40))
		request(m_irq_level.sci, m_vcra);
	if ((m_scr & m_ssr & 0x80))
		request(m_irq_level.sci, m_vcrb >> 8);
	if ((m_scr & m_ssr & 4))
		request(m_irq_level.sci, m_vcrb);

	// FRT: input capture, output compare, overflow
	uint8_t const frt = m_tier & m_ftcsr;
	if (frt & ICF)
		request(m_irq_level.frc, m_irq_vector.fic);
	if (frt & (OCFA | OCFB))
		request(m_irq_level.frc, m_irq_vector.foc);
	if (frt & OVF)
		request(m_irq_level.frc, m_irq_vector.fov);

	m_sh2_state->internal_irq_level = irq;
	m_internal_irq_vector = vector;
	m_test_irq = 1;
}

/*
 * DMAC
 */

template <int Channel>
uint32_t sh7604_device::vcrdma_r()
{
	return m_vcrdma[Channel] & 0x7f;
}

template <int Channel>
void sh7604_device::vcrdma_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_vcrdma[Channel]);
	m_irq_vector.dmac[Channel] = m_vcrdma[Channel] & 0x7f;
	sh2_recalc_irq();
}

template <int Channel>
uint8_t sh7604_device::drcr_r()
{
	return m_dmac[Channel].drcr & 3;
}

template <int Channel>
void sh7604_device::drcr_w(uint8_t data)
{
	m_dmac[Channel].drcr = data & 3;
	sh2_dmac_check(Channel);
	sh2_recalc_irq();
}

template <int Channel>
uint32_t sh7604_device::sar_r()
{
	return m_dmac[Channel].sar;
}

template <int Channel>
void sh7604_device::sar_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_dmac[Channel].sar);
}

template <int Channel>
uint32_t sh7604_device::dar_r()
{
	return m_dmac[Channel].dar;
}

template <int Channel>
void sh7604_device::dar_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_dmac[Channel].dar);
}

template <int Channel>
uint32_t sh7604_device::dmac_tcr_r()
{
	return m_dmac[Channel].tcr;
}

template <int Channel>
void sh7604_device::dmac_tcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_dmac[Channel].tcr);
	m_dmac[Channel].tcr &= 0xffffff;
}

template <int Channel>
uint32_t sh7604_device::chcr_r()
{
	if (!machine().side_effects_disabled())
		m_dma_te_read[Channel] = BIT(m_dmac[Channel].chcr, 1);
	return m_dmac[Channel].chcr & 0xffff;
}

template <int Channel>
void sh7604_device::chcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	uint32_t const old = m_dmac[Channel].chcr;
	uint32_t const merged = (old & ~mem_mask) | (data & mem_mask);
	bool const clear_te = (mem_mask & 2) && !(data & 2) && m_dma_te_read[Channel];
	m_dmac[Channel].chcr = (merged & 0xfffd) | (clear_te ? 0 : old & 2);
	if (mem_mask & 2)
		m_dma_te_read[Channel] = false;
	if (m_dma_owner != Channel)
	{
		m_dma_ack_high[Channel] = BIT(m_dmac[Channel].chcr, 7);
		dma_dack_drive(Channel, !m_dma_ack_high[Channel]);
	}
	sh2_dmac_check(Channel);
	// TE cleared or IE changed: the request follows the bits
	sh2_recalc_irq();
}

uint32_t sh7604_device::dmaor_r()
{
	if (!machine().side_effects_disabled())
		m_dmaor_read_flags = m_dmaor & 6;
	return m_dmaor & 0xf;
}

void sh7604_device::dmaor_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (ACCESSING_BITS_0_7)
	{
		uint8_t old = m_dmaor & 0xf;
		uint8_t const clear = m_dmaor_read_flags & mem_mask & ~data;
		m_dmaor = (data & 9) | (old & 6 & ~clear);
		m_dmaor_read_flags = 0;
		sh2_dmac_check(0);
		sh2_dmac_check(1);
	}
}

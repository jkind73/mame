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
TODO: Test and use sh7604_wdt_device, sh7604_sci_device, and sh7604_bus_device as appropriate
*/


#include "emu.h"

#include "sh7604.h"

//#define VERBOSE 1
#include "logmacro.h"

#include <bit>


static constexpr int div_tab[4] = { 3, 5, 7, 0 };
static constexpr int wdtclk_tab[8] = { 1, 6, 7, 8, 9, 10, 12, 13 };


DEFINE_DEVICE_TYPE(SH7604,  sh7604_device,  "sh2_7604",  "Hitachi SH-2 (SH7604)")


sh7604_device::sh7604_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: sh2_device(mconfig, SH7604, tag, owner, clock, CPU_TYPE_SH2, address_map_constructor(FUNC(sh7604_device::sh7604_map), this), 32, 0xc7ffffff)
	, m_test_irq(0), m_internal_irq_vector(0)
	, m_smr(0), m_brr(0), m_scr(0), m_tdr(0), m_ssr(0)
	, m_write_txd(*this)
	, m_read_rxd(*this, 1)
	, m_write_sck(*this)
	, m_tier(0), m_ftcsr(0), m_ftcsr_read(0), m_frc_tcr(0), m_tocr(0), m_frt_temp(0), m_frc(0), m_ocra(0), m_ocrb(0), m_frc_icr(0)
	, m_frt_out_a(false), m_frt_out_b(false)
	, m_write_ftoa(*this), m_write_ftob(*this)
	, m_ipra(0), m_iprb(0), m_vcra(0), m_vcrb(0), m_vcrc(0), m_vcrd(0), m_vcrwdt(0), m_vcrdiv(0), m_intc_icr(0), m_vecmd(false), m_nmie(false)
	, m_divu_ovf(false), m_divu_ovfie(false), m_dvsr(0), m_dvdntl(0), m_dvdnth(0)
	, m_wtcnt(0), m_wtcsr(0), m_rstcsr(0), m_wdt_read(0)
	, m_dmaor(0)
	, m_sbycr(0), m_ccr(0)
	, m_bcr1(0x03f0), m_bcr2(0x00fc), m_wcr(0xaaff), m_mcr(0), m_rtcsr(0), m_rtcor(0), m_rtcnt(0)
	, m_rtcsr_read(false)
	, m_frc_base(0), m_frt_input(0), m_frt_clock_input(false)
	, m_timer(nullptr), m_wdtimer(nullptr)
	, m_is_slave(0)
	, m_dma_kludge_cb(*this)
	, m_dma_fifo_data_available_cb(*this)
	, m_ftcsr_read_cb(*this)
{
	std::fill(std::begin(m_vcrdma), std::end(m_vcrdma), 0);
	std::fill(std::begin(m_dma_timer_active), std::end(m_dma_timer_active), 0);
	std::fill(std::begin(m_dma_irq), std::end(m_dma_irq), 0);
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
	m_sci_tx_timer = timer_alloc(FUNC(sh7604_device::sci_tx_tick), this);
	m_sci_tx_timer->adjust(attotime::never);
	m_sci_clock_timer = timer_alloc(FUNC(sh7604_device::sci_clock_tick), this);
	m_sci_clock_timer->adjust(attotime::never);
	m_sci_rx_timer = timer_alloc(FUNC(sh7604_device::sci_rx_tick), this);
	m_sci_rx_timer->adjust(attotime::never);

	m_dma_current_active_timer[0] = timer_alloc(FUNC(sh7604_device::sh2_dma_current_active_callback), this);
	m_dma_current_active_timer[0]->adjust(attotime::never);

	m_dma_current_active_timer[1] = timer_alloc(FUNC(sh7604_device::sh2_dma_current_active_callback), this);
	m_dma_current_active_timer[1]->adjust(attotime::never);

	/* resolve callbacks */
	m_dma_kludge_cb.resolve();
	m_dma_fifo_data_available_cb.resolve();
	m_ftcsr_read_cb.resolve();

	// SCI
	save_item(NAME(m_smr));
	save_item(NAME(m_brr));
	save_item(NAME(m_scr));
	save_item(NAME(m_tdr));
	save_item(NAME(m_ssr));
	save_item(NAME(m_sci_ssr_read));
	save_item(NAME(m_rdr));
	save_item(NAME(m_tsr));
	save_item(NAME(m_rsr));
	save_item(NAME(m_sci_tx_bit));
	save_item(NAME(m_sci_tx_phase));
	save_item(NAME(m_sci_tx_active));
	save_item(NAME(m_sci_tx_loaded));
	save_item(NAME(m_sci_rx_enabled));
	save_item(NAME(m_sci_rx_state));
	save_item(NAME(m_sci_rx_shift));
	save_item(NAME(m_sci_rx_parity_error));
	save_item(NAME(m_sci_rx_mp));
	save_item(NAME(m_sci_rx_bitcnt));
	save_item(NAME(m_sci_rx_phase));
	save_item(NAME(m_sci_rx_vote));
	save_item(NAME(m_sci_sck));
	save_item(NAME(m_sci_sck_out));
	save_item(NAME(m_sci_clock_running));

	// FRT / FRC
	save_item(NAME(m_tier));
	save_item(NAME(m_ftcsr));
	save_item(NAME(m_ftcsr_read));
	save_item(NAME(m_frc_tcr));
	save_item(NAME(m_tocr));
	save_item(NAME(m_frt_temp));
	save_item(NAME(m_frc));
	save_item(NAME(m_ocra));
	save_item(NAME(m_ocrb));
	save_item(NAME(m_frc_icr));
	save_item(NAME(m_frt_out_a));
	save_item(NAME(m_frt_out_b));
	save_item(NAME(m_frc_base));
	save_item(NAME(m_frt_input));
	save_item(NAME(m_frt_clock_input));

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
	save_item(NAME(m_divu_ovf));
	save_item(NAME(m_divu_ovfie));
	save_item(NAME(m_dvsr));
	save_item(NAME(m_dvdntl));
	save_item(NAME(m_dvdnth));

	// WTC
	save_item(NAME(m_wtcnt));
	save_item(NAME(m_wtcsr));
	save_item(NAME(m_rstcsr));
	save_item(NAME(m_wdt_read));
	save_item(NAME(m_wtcw));

	// UBC
	save_item(NAME(m_barah));
	save_item(NAME(m_baral));
	save_item(NAME(m_barbh));
	save_item(NAME(m_barbl));

	// DMAC
	save_item(NAME(m_dmaor));
	save_item(STRUCT_MEMBER(m_dmac, drcr));
	save_item(STRUCT_MEMBER(m_dmac, sar));
	save_item(STRUCT_MEMBER(m_dmac, dar));
	save_item(STRUCT_MEMBER(m_dmac, tcr));
	save_item(STRUCT_MEMBER(m_dmac, chcr));

	// misc
	save_item(NAME(m_sbycr));
	save_item(NAME(m_ccr));

	// BSC
	save_item(NAME(m_bcr1));
	save_item(NAME(m_bcr2));
	save_item(NAME(m_wcr));
	save_item(NAME(m_mcr));
	save_item(NAME(m_rtcsr));
	save_item(NAME(m_rtcor));
	save_item(NAME(m_rtcnt));
	save_item(NAME(m_rtcsr_read));
}

void sh7604_device::device_reset()
{
	sh2_device::device_reset();

	// ICR control bits reset to falling-edge NMI detection and auto-vector
	// mode (section 5.3.8). NMIL continues to reflect the external input.
	m_intc_icr = 0;
	m_nmie = m_vecmd = false;

	// IPRA/IPRB reset to priority zero on power-on and manual reset
	// (sections 5.3.1-5.3.2). Clear the decoded levels before peripherals reset.
	m_ipra = m_iprb = 0;
	m_irq_level.frc = m_irq_level.sci = m_irq_level.divu = m_irq_level.dmac = m_irq_level.wdt = 0;

	// Only the INTC vectors in sections 5.3.3-5.3.7 have a zero reset value.
	// DIVU/DMAC vector registers have undefined reset values; leave them alone.
	m_vcra = m_vcrb = m_vcrc = m_vcrd = m_vcrwdt = 0;
	m_irq_vector.fic = m_irq_vector.foc = m_irq_vector.fov = 0;

	// Reset releases module standby before starting the free-running timer.
	m_sbycr = 0;
	m_frt_input = 0;
	m_frt_clock_input = false;
	frt_reset();
	sh2_timer_activate();

	for (int i = 0; i < 2; i++)
	{
		m_dma_timer_active[i] = 0;
		m_dma_irq[i] = 0;
		m_active_dma_incs[i] = 0;
		m_active_dma_incd[i] = 0;
		m_active_dma_size[i] = 0;
		m_active_dma_steal[i] = 0;
		m_active_dma_src[i] = 0;
		m_active_dma_dst[i] = 0;
		m_active_dma_count[i] = 0;
	}

	// DVCR is initialized by power-on/manual reset, not module standby
	// (section 10.2.3). Dividend/divisor registers have undefined reset values.
	m_divu_ovf = false;
	m_divu_ovfie = false;

	// RES-style device reset initializes WDT control/status and cancels
	// any old deadline. A WDT-generated internal reset must preserve
	// RSTCSR instead (section 12.2.3); its delivery remains separate.
	m_wtcnt = 0;
	m_wtcsr = 0;
	m_rstcsr = 0;
	m_wdt_read = 0;
	m_wdtimer->adjust(attotime::never);

	sci_reset();

	m_barah = 0;
	m_baral = 0;
	m_barbh = 0;
	m_barbl = 0;
}

void sh7604_device::sh7604_map(address_map &map)
{
	map(0x40000000, 0xbfffffff).r(FUNC(sh7604_device::sh2_internal_a5));

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
	map(0xfffffe80, 0xfffffe81).r(FUNC(sh7604_device::wtcnt_r));
	map(0xfffffe82, 0xfffffe83).r(FUNC(sh7604_device::rstcsr_r));
	map(0xfffffe80, 0xfffffe83).w(FUNC(sh7604_device::wdt_w));

	// standby and cache control
	map(0xfffffe90, 0xfffffe91).rw(FUNC(sh7604_device::fmr_sbycr_r), FUNC(sh7604_device::fmr_sbycr_w));
	map(0xfffffe92, 0xfffffe92).rw(FUNC(sh7604_device::ccr_r), FUNC(sh7604_device::ccr_w));

	// INTC second section
	map(0xfffffee0, 0xfffffee1).rw(FUNC(sh7604_device::intc_icr_r), FUNC(sh7604_device::intc_icr_w));
	map(0xfffffee2, 0xfffffee3).rw(FUNC(sh7604_device::ipra_r), FUNC(sh7604_device::ipra_w));
	map(0xfffffee4, 0xfffffee5).rw(FUNC(sh7604_device::vcrwdt_r), FUNC(sh7604_device::vcrwdt_w));

	// DIVU
	map(0xffffff00, 0xffffff03).rw(FUNC(sh7604_device::dvsr_r), FUNC(sh7604_device::dvsr_w));
	map(0xffffff04, 0xffffff07).rw(FUNC(sh7604_device::dvdnt_r), FUNC(sh7604_device::dvdnt_w));
	map(0xffffff08, 0xffffff0b).rw(FUNC(sh7604_device::dvcr_r), FUNC(sh7604_device::dvcr_w));
	// INTC third section
	map(0xffffff0c, 0xffffff0f).rw(FUNC(sh7604_device::vcrdiv_r), FUNC(sh7604_device::vcrdiv_w));
	// DIVU continued (64-bit plus mirrors)
	map(0xffffff10, 0xffffff13).rw(FUNC(sh7604_device::dvdnth_r), FUNC(sh7604_device::dvdnth_w));
	map(0xffffff14, 0xffffff17).rw(FUNC(sh7604_device::dvdntl_r), FUNC(sh7604_device::dvdntl_w));
	map(0xffffff18, 0xffffff1b).r(FUNC(sh7604_device::dvdnth_r));
	map(0xffffff1c, 0xffffff1f).r(FUNC(sh7604_device::dvdntl_r));

	// UBC
	map(0xffffff40, 0xffffff41).rw(FUNC(sh7604_device::barah_r), FUNC(sh7604_device::barah_w));
	map(0xffffff42, 0xffffff43).rw(FUNC(sh7604_device::baral_r), FUNC(sh7604_device::baral_w));
//  map(0xffffff44, 0xffffff45).rw(FUNC(sh7604_device::bamrah_r), FUNC(sh7604_device::bamrah_w));
//  map(0xffffff46, 0xffffff47).rw(FUNC(sh7604_device::bamral_r), FUNC(sh7604_device::bamral_w));
//  map(0xffffff48, ).rw(FUNC(sh7604_device::bbra_r), FUNC(sh7604_device::bbra_w));

	map(0xffffff60, 0xffffff61).rw(FUNC(sh7604_device::barbh_r), FUNC(sh7604_device::barbh_w));
	map(0xffffff62, 0xffffff63).rw(FUNC(sh7604_device::barbl_r), FUNC(sh7604_device::barbl_w));
//  map(0xffffff64, 0xffffff65).rw(FUNC(sh7604_device::bamrbh_r), FUNC(sh7604_device::bamrbh_w));
//  map(0xffffff66, 0xffffff67).rw(FUNC(sh7604_device::bamrbl_r), FUNC(sh7604_device::bamrbl_w));
//  map(0xffffff68, ).rw(FUNC(sh7604_device::bbrb_r), FUNC(sh7604_device::bbrb_w));
//  map(0xffffff70, 0xffffff71).rw(FUNC(sh7604_device::bdrbh_r), FUNC(sh7604_device::bdrbh_w));
//  map(0xffffff72, 0xffffff73).rw(FUNC(sh7604_device::bdrbl_r), FUNC(sh7604_device::bdrbl_w));
//  map(0xffffff74, 0xffffff75).rw(FUNC(sh7604_device::bdmrbh_r), FUNC(sh7604_device::bdmrbh_w));
//  map(0xffffff76, 0xffffff77).rw(FUNC(sh7604_device::bdmrbl_r), FUNC(sh7604_device::bdmrbl_w));
//  map(0xffffff78, 0xffffff79).rw(FUNC(sh7604_device::brcr_r), FUNC(sh7604_device::brcr_w));

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

	if (irqline != 16)
	{
		if (irqline <= ((m_sh2_state->sr >> 4) & 15)) /* If the cpu forbids this interrupt */
			return;

		// if this is an sh2 internal irq, use its vector
		if (m_sh2_state->internal_irq_level == irqline)
		{
			vector = m_internal_irq_vector;
			/* avoid spurious irqs with this (TODO: needs a better fix) */
			m_sh2_state->internal_irq_level = -1;
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

void sh7604_device::frt_reset()
{
	// Table 11.2 (p.297), section 14.2.1 (p.388): reset and MSTP1
	// initialize the FRT, but module stop leaves its INTC vectors intact.
	m_tier = 0x01;
	m_ftcsr = 0;
	m_ftcsr_read = 0;
	m_frc_tcr = 0;
	m_tocr = 0xe0;
	m_frt_temp = 0;
	m_frc = 0;
	m_ocra = 0xffff;
	m_ocrb = 0xffff;
	m_frc_icr = 0;
	m_frc_base = total_cycles();
	m_timer->adjust(attotime::never);
	m_frt_out_a = false;
	m_frt_out_b = false;
	m_write_ftoa(0);
	m_write_ftob(0);
}

void sh7604_device::sh2_timer_resync()
{
	if (BIT(m_sbycr, 1))
		return;

	// External mode advances only through ftci_w, never CPU elapsed time.
	int divider = div_tab[m_frc_tcr & 3];
	uint64_t cur_time = total_cycles();
	uint64_t add = (cur_time - m_frc_base) >> divider;

	if (divider)
	{
		m_frc += add;
		// Keep the fractional divider interval: reading FRC must not
		// change the phi/8, phi/32 or phi/128 clock (section 11.4.1).
		m_frc_base += add << divider;
	}
	else
		m_frc_base = cur_time;
}

void sh7604_device::sh2_timer_activate()
{
	int max_delta = 0xfffff;

	m_timer->adjust(attotime::never);
	if (BIT(m_sbycr, 1))
		return;

	uint16_t frc = m_frc;
	// Compare uses the count before its update (Figure 11.11, p.311).
	// Equality alone is not an event: even OCR == FRC waits one tick.
	// Clear-on-A must keep running after software leaves OCFA latched.
	if (!(m_ftcsr & OCFA) || (m_ftcsr & CCLRA) || (m_frt_out_a != BIT(m_tocr, 1)))
	{
		int delta = uint16_t(m_ocra - frc) + 1;
		if (delta < max_delta)
			max_delta = delta;
	}

	if (!(m_ftcsr & OCFB) || (m_frt_out_b != BIT(m_tocr, 0)))
	{
		int delta = uint16_t(m_ocrb - frc) + 1;
		if (delta < max_delta)
			max_delta = delta;
	}

	if (!(m_ftcsr & OVF))
	{
		int delta = 0x10000 - frc;
		if (delta < max_delta)
			max_delta = delta;
	}

	if (max_delta != 0xfffff)
	{
		int divider = div_tab[m_frc_tcr & 3];
		if (divider)
		{
			uint64_t const delta = uint64_t(max_delta) << divider;
			uint64_t const elapsed = total_cycles() - m_frc_base;
			// Scheduling is not a prescaler reset. Account for the partial
			// interval already elapsed since the last counter tick.
			m_timer->adjust(cycles_to_attotime(delta > elapsed ? delta - elapsed : 0));
		}
	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::sh2_timer_callback)
{
	if (BIT(m_sbycr, 1))
		return;

	sh2_timer_resync();
	// Resync has advanced to this count edge. Compare the value held
	// before that edge; overflow still describes FFFF -> 0000.
	uint16_t const previous = m_frc - 1;

	frt_compare_tick(previous);

	sh2_recalc_irq();
	sh2_timer_activate();
}

// Shared count-edge behavior for internal and external FRT clocks.
void sh7604_device::frt_compare_tick(uint16_t previous)
{
	bool const old_a = m_frt_out_a;
	bool const old_b = m_frt_out_b;
	if (previous == m_ocrb)
	{
		m_ftcsr |= OCFB;
		m_frt_out_b = BIT(m_tocr, 0);
	}

	if (previous == 0xffff)
		m_ftcsr |= OVF;

	if (previous == m_ocra)
	{
		m_ftcsr |= OCFA;
		m_frt_out_a = BIT(m_tocr, 1);

		if (m_ftcsr & CCLRA)
			m_frc = 0;
	}

	// Publish after committing both levels and the counter clear. OLVLA/B
	// select the level at compare, not a toggle or an immediate write effect.
	if (old_a != m_frt_out_a)
		m_write_ftoa(m_frt_out_a);
	if (old_b != m_frt_out_b)
		m_write_ftob(m_frt_out_b);
}

void sh7604_device::ftci_w(int state)
{
	bool const level = state != 0;
	bool const rising = level && !m_frt_clock_input;
	m_frt_clock_input = level;
	// Keep pin history even when another clock is selected or MSTP1 is set.
	if (!rising || (m_frc_tcr & 3) != 3 || BIT(m_sbycr, 1))
		return;

	uint16_t const previous = m_frc++;
	uint8_t const old_flags = m_ftcsr;
	frt_compare_tick(previous);
	if (old_flags != m_ftcsr)
		sh2_recalc_irq();
}

void sh7604_device::sh2_wtcnt_recalc()
{
	if (m_wdtimer->expire() != attotime::never)
	{
		// A partially elapsed selected-clock period has not incremented
		// WTCNT yet: round the number of remaining counter ticks upward.
		uint64_t const remaining = attotime_to_cycles(m_wdtimer->remaining());
		unsigned const shift = wdtclk_tab[m_wtcsr & 7];
		m_wtcnt = 0x100 - ((remaining + (1U << shift) - 1) >> shift);
	}
}

void sh7604_device::sh2_wdt_activate()
{
	uint64_t const divider = 1U << wdtclk_tab[m_wtcsr & 7];
	uint64_t clocks = (0x100 - m_wtcnt) * divider;
	if (m_wdtimer->expire() != attotime::never)
	{
		// Register writes while enabled do not restart the selected clock.
		// Retain its partial period from the old deadline. CKS/mode changes
		// must be made with TME=0 (sections 12.4.2 and 12.4.3).
		uint64_t const remaining = attotime_to_cycles(m_wdtimer->remaining());
		clocks -= (divider - remaining % divider) % divider;
	}
	m_wdtimer->adjust(cycles_to_attotime(clocks));
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
		m_rstcsr |= 0x80;
		if (!(m_rstcsr & 0x40))
		{
			// With RSTE=0, only WTCNT/WTCSR reset on watchdog overflow
			// (section 12.4.5). RSTCSR, including WOVF, is preserved.
			m_wtcsr = 0;
			m_wdt_read &= ~1;
			m_wdtimer->adjust(attotime::never);
			sh2_recalc_irq();
		}
		// TODO RSTE=1 internal reset and /WDTOVF out
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
	//printf("call notify\n");

	for (int dmach=0;dmach<2;dmach++)
	{
		//printf("m_dma_timer_active[dmach] %04x\n", m_dma_timer_active[dmach]);

		if (m_dma_timer_active[dmach]==2) // 2 = stalled
		{
			//printf("resuming stalled dma\n");
			m_dma_timer_active[dmach]=1;
			m_dma_current_active_timer[dmach]->adjust(attotime::zero, dmach);
		}
	}

}

void sh7604_device::sh2_do_dma(int dmach)
{
	if (m_active_dma_count[dmach] > 0)
	{
		// process current DMA
		switch (m_active_dma_size[dmach])
		{
		case 0:
		{
			// we need to know the src / dest ahead of time without changing them
			// to allow for the callback to check if we can process the DMA at this
			// time (we need to know where we're reading / writing to/from)

			uint32_t tempsrc = m_active_dma_src[dmach];
			if (m_active_dma_incs[dmach] == 2)
				tempsrc--;

			uint32_t tempdst = m_active_dma_dst[dmach];
			if (m_active_dma_incd[dmach] == 2)
				tempdst--;

			if (!m_dma_fifo_data_available_cb.isnull())
			{
				int available = m_dma_fifo_data_available_cb(tempsrc, tempdst, 0, m_active_dma_size[dmach]);

				if (!available)
				{
					//printf("dma stalled\n");
					m_dma_timer_active[dmach] = 2; // mark as stalled
					return;
				}
			}

			//schedule next DMA callback
			m_dma_current_active_timer[dmach]->adjust(cycles_to_attotime(2), dmach);

			uint32_t dmadata = m_program->read_byte(tempsrc);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_byte(tempdst, dmadata);

			if (m_active_dma_incs[dmach] == 2)
				m_active_dma_src[dmach]--;
			if (m_active_dma_incd[dmach] == 2)
				m_active_dma_dst[dmach]--;

			if (m_active_dma_incs[dmach] == 1)
				m_active_dma_src[dmach]++;
			if (m_active_dma_incd[dmach] == 1)
				m_active_dma_dst[dmach]++;

			m_active_dma_count[dmach]--;
			break;
		}

		case 1:
		{
			uint32_t tempsrc = m_active_dma_src[dmach];
			if (m_active_dma_incs[dmach] == 2)
				tempsrc -= 2;

			uint32_t tempdst = m_active_dma_dst[dmach];
			if (m_active_dma_incd[dmach] == 2)
				tempdst -= 2;

			if (!m_dma_fifo_data_available_cb.isnull())
			{
				int available = m_dma_fifo_data_available_cb(tempsrc, tempdst, 0, m_active_dma_size[dmach]);

				if (!available)
				{
					//printf("dma stalled\n");
					m_dma_timer_active[dmach] = 2; // mark as stalled
					return;
				}
			}

			//schedule next DMA callback
			m_dma_current_active_timer[dmach]->adjust(cycles_to_attotime(2), dmach);

			// check: should this really be using read_word_32 / write_word_32?
			uint32_t dmadata = m_program->read_word(tempsrc);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_word(tempdst, dmadata);

			if (m_active_dma_incs[dmach] == 2)
				m_active_dma_src[dmach] -= 2;
			if (m_active_dma_incd[dmach] == 2)
				m_active_dma_dst[dmach] -= 2;

			if (m_active_dma_incs[dmach] == 1)
				m_active_dma_src[dmach] += 2;
			if (m_active_dma_incd[dmach] == 1)
				m_active_dma_dst[dmach] += 2;

			m_active_dma_count[dmach]--;
			break;
		}

		case 2:
		{
			uint32_t tempsrc = m_active_dma_src[dmach];
			if (m_active_dma_incs[dmach] == 2)
				tempsrc -= 4;

			uint32_t tempdst = m_active_dma_dst[dmach];
			if (m_active_dma_incd[dmach] == 2)
				tempdst -= 4;

			if (!m_dma_fifo_data_available_cb.isnull())
			{
				int available = m_dma_fifo_data_available_cb(tempsrc, tempdst, 0, m_active_dma_size[dmach]);

				if (!available)
				{
					//printf("dma stalled\n");
					m_dma_timer_active[dmach] = 2; // mark as stalled
					return;
				}
			}

			//schedule next DMA callback
			m_dma_current_active_timer[dmach]->adjust(cycles_to_attotime(2), dmach);

			uint32_t dmadata = m_program->read_dword(tempsrc);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_dword(tempdst, dmadata);

			if (m_active_dma_incs[dmach] == 2)
				m_active_dma_src[dmach] -= 4;
			if (m_active_dma_incd[dmach] == 2)
				m_active_dma_dst[dmach] -= 4;

			if (m_active_dma_incs[dmach] == 1)
				m_active_dma_src[dmach] += 4;
			if (m_active_dma_incd[dmach] == 1)
				m_active_dma_dst[dmach] += 4;

			m_active_dma_count[dmach]--;
			break;
		}

		case 3:
		{
			// shouldn't this really be 4 calls here instead?

			uint32_t tempsrc = m_active_dma_src[dmach];

			uint32_t tempdst = m_active_dma_dst[dmach];
			if (m_active_dma_incd[dmach] == 2)
				tempdst -= 16;

			if (!m_dma_fifo_data_available_cb.isnull())
			{
				int available = m_dma_fifo_data_available_cb(tempsrc, tempdst, 0, m_active_dma_size[dmach]);

				if (!available)
				{
					//printf("dma stalled\n");
					m_dma_timer_active[dmach] = 2; // mark as stalled
					fatalerror("SH2 dma_callback_fifo_data_available == 0 in unsupported mode\n");
				}
			}

			//schedule next DMA callback
			m_dma_current_active_timer[dmach]->adjust(cycles_to_attotime(2), dmach);

			uint32_t dmadata = m_program->read_dword(tempsrc);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_dword(tempdst, dmadata);

			dmadata = m_program->read_dword(tempsrc + 4);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_dword(tempdst + 4, dmadata);

			dmadata = m_program->read_dword(tempsrc + 8);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_dword(tempdst + 8, dmadata);

			dmadata = m_program->read_dword(tempsrc + 12);
			if (!m_dma_kludge_cb.isnull())
				dmadata = m_dma_kludge_cb(tempsrc, tempdst, dmadata, m_active_dma_size[dmach]);
			m_program->write_dword(tempdst + 12, dmadata);

			if (m_active_dma_incd[dmach] == 2)
				m_active_dma_dst[dmach] -= 16;

			m_active_dma_src[dmach] += 16;
			if (m_active_dma_incd[dmach] == 1)
				m_active_dma_dst[dmach] += 16;

			m_active_dma_count[dmach] -= 4;
			break;
		}
		}
	}
	else // the dma is complete
	{
		// int dma = param & 1;

		// fever soccer uses cycle-stealing mode, resume the CPU now DMA has finished
		if (m_active_dma_steal[dmach])
		{
			resume(SUSPEND_REASON_HALT);
		}

		LOG("SH2: DMA %d complete\n", dmach);
		m_dmac[dmach].tcr = 0;
		m_dmac[dmach].chcr |= 2;
		m_dma_timer_active[dmach] = 0;
		m_dma_irq[dmach] |= 1;
		sh2_recalc_irq();

	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::sh2_dma_current_active_callback)
{
	sh2_do_dma(param & 1);
}


void sh7604_device::sh2_dmac_check(int dmach)
{
	if (m_dmac[dmach].chcr & m_dmaor & 1)
	{
		if (!m_dma_timer_active[dmach] && !(m_dmac[dmach].chcr & 2))
		{
			m_active_dma_incd[dmach] = (m_dmac[dmach].chcr >> 14) & 3;
			m_active_dma_incs[dmach] = (m_dmac[dmach].chcr >> 12) & 3;
			m_active_dma_size[dmach] = (m_dmac[dmach].chcr >> 10) & 3;
			m_active_dma_steal[dmach] = (m_dmac[dmach].chcr & 0x10);

			if (m_active_dma_incd[dmach] == 3 || m_active_dma_incs[dmach] == 3)
			{
				LOG("SH2: DMA: bad increment values (%d, %d, %d, %04x)\n", m_active_dma_incd[dmach], m_active_dma_incs[dmach], m_active_dma_size[dmach], m_dmac[dmach].chcr);
				return;
			}
			m_active_dma_src[dmach]   = m_dmac[dmach].sar;
			m_active_dma_dst[dmach]   = m_dmac[dmach].dar;
			m_active_dma_count[dmach] = m_dmac[dmach].tcr;
			if (!m_active_dma_count[dmach])
				m_active_dma_count[dmach] = 0x1000000;

			LOG("SH2: DMA %d start %x, %x, %x, %04x, %d, %d, %d\n", dmach, m_active_dma_src[dmach], m_active_dma_dst[dmach], m_active_dma_count[dmach], m_dmac[dmach].chcr, m_active_dma_incs[dmach], m_active_dma_incd[dmach], m_active_dma_size[dmach]);

			m_dma_timer_active[dmach] = 1;

			m_active_dma_src[dmach] &= m_am;
			m_active_dma_dst[dmach] &= m_am;

			switch (m_active_dma_size[dmach])
			{
			case 0:
				break;
			case 1:
				m_active_dma_src[dmach] &= ~1;
				m_active_dma_dst[dmach] &= ~1;
				break;
			case 2:
				m_active_dma_src[dmach] &= ~3;
				m_active_dma_dst[dmach] &= ~3;
				break;
			case 3:
				m_active_dma_src[dmach] &= ~3;
				m_active_dma_dst[dmach] &= ~3;
				m_active_dma_count[dmach] &= ~3;
				break;
			}

			// start DMA timer

			// fever soccer uses cycle-stealing mode, requiring the CPU to be halted
			if (m_active_dma_steal[dmach])
			{
				//printf("cycle stealing DMA\n");
				suspend(SUSPEND_REASON_HALT, 1);
			}

			m_dma_current_active_timer[dmach]->adjust(cycles_to_attotime(2), dmach);
		}
	}
	else
	{
		if (m_dma_timer_active[dmach])
		{
			LOG("SH2: DMA %d cancelled in-flight\n", dmach);
			//m_dma_complete_timer[dmach]->adjust(attotime::never);
			m_dma_current_active_timer[dmach]->adjust(attotime::never, dmach);

			m_dma_timer_active[dmach] = 0;
		}
	}
}

/*
 * SCI
 *
 * Register behaviour and the transfer engine follow the SH7604 Hardware
 * Manual (ADE-602-085C) section 13: SMR/BRR/SCR/TDR/SSR/RDR at H'FFFFFE00-05
 * (p.335 Table 13.2), bit-rate generator formulas (p.349), interrupt sources
 * TXI/RXI/ERI/TEI with ERI>RXI>TXI>TEI priority (p.~360 Table 13.13) and
 * vectors in VCRA/VCRB (p.91-92).
 */
// TODO: SCI DMA request/ack routing and whole-chip standby integration

void sh7604_device::sci_reset()
{
	// SCI: H'FFFFFE00 SMR=0, BRR=H'FF, SCR=0, TDR=H'FF, SSR=H'84, RDR=0
	// (SH7604 Hardware Manual Table 13.2)
	m_smr = 0;
	m_brr = 0xff;
	m_scr = 0;
	m_tdr = 0xff;
	m_ssr = SSR_TDRE | SSR_TEND;
	m_sci_ssr_read = 0;
	m_rdr = 0;
	m_tsr = 0;
	m_rsr = 0;
	m_sci_tx_bit = 0;
	m_sci_tx_phase = 0;
	m_sci_tx_active = false;
	m_sci_tx_loaded = false;
	m_sci_rx_enabled = false;
	m_sci_rx_state = 0;
	m_sci_rx_shift = 0;
	m_sci_rx_parity_error = false;
	m_sci_rx_mp = false;
	m_sci_rx_bitcnt = 0;
	m_sci_rx_phase = 0;
	m_sci_rx_vote = 0;
	m_sci_sck = true;
	m_sci_sck_out = true;
	m_sci_clock_running = false;
	m_sci_clock_timer->adjust(attotime::never);
	m_sci_tx_timer->adjust(attotime::never);
	m_sci_rx_timer->adjust(attotime::never);
	m_write_txd(1); // TxD idles high
	m_write_sck(1); // logical idle; the callbacks do not model high impedance
}

uint8_t sh7604_device::smr_r()
{
	return m_smr;
}

void sh7604_device::smr_w(uint8_t data)
{
	m_smr = data;
	sci_recalc_rates();
}

uint8_t sh7604_device::brr_r()
{
	return m_brr;
}

void sh7604_device::brr_w(uint8_t data)
{
	m_brr = data;
	sci_recalc_rates();
}

uint8_t sh7604_device::scr_r()
{
	return m_scr;
}

void sh7604_device::scr_w(uint8_t data)
{
	uint8_t const old_scr = m_scr;
	bool const old_re = BIT(old_scr, 4);
	m_scr = data;

	// TE=0 locks TDRE at 1, sets TEND and initializes TSR; TE=1 alone does
	// not start a transfer, only the TDRE clear does (pp.340, 345, 372-373)
	if (!BIT(m_scr, 5))
	{
		m_ssr |= SSR_TDRE;
		m_ssr |= SSR_TEND;
		m_sci_tx_active = false;
		m_sci_tx_phase = 0;
		m_sci_tx_loaded = false;
		m_sci_tx_timer->adjust(attotime::never);
		m_write_txd(1);
	}
	if (!BIT(m_scr, 4))
	{
		m_sci_rx_enabled = false;
		m_sci_rx_state = 0;
		m_sci_rx_timer->adjust(attotime::never);
		// clearing RE does not affect RDRF/FER/PER/ORER (p.340)
	}
	else if (!old_re)
	{
		m_sci_rx_state = 0; // a synchronous receiver waits for a new falling edge
		// Async reception uses either the timer or external 16x SCK pulses.
		if (!BIT(m_smr, 7))
		{
			m_sci_rx_enabled = true;
			m_sci_rx_state = 0;
			m_sci_rx_phase = 0;
			if (!BIT(m_scr, 1))
				m_sci_rx_timer->adjust(sci_bit_period() / 16, 0);
		}
	}

	// Interrupt-enable writes must not restart the in-flight bit period.
	if ((old_scr ^ m_scr) & 3)
		sci_recalc_rates();
	sci_update_clock();
	sh2_recalc_irq();
}

uint8_t sh7604_device::tdr_r()
{
	return m_tdr;
}

void sh7604_device::tdr_w(uint8_t data)
{
	// TDR write alone does not start a transfer: the SCI watches TDRE
	// (Figure 13.15 step 1, p.372)
	m_tdr = data;
}

uint8_t sh7604_device::ssr_r()
{
	// Only a CPU status read arms write-zero acknowledgements. Debugger
	// inspection must not make a later write consume a newly raised flag.
	if (!machine().side_effects_disabled())
		m_sci_ssr_read = m_ssr;
	return m_ssr;
}

void sh7604_device::ssr_w(uint8_t data)
{
	// SH7604 manual section 13.2.7, pp.342-345: flags 7-3 can only be
	// cleared after being read as one. TEND/MPB are read-only; MPBT is
	// ordinary read/write. TE=0 locks TDRE at one (section 13.2.6).
	bool const tdre_clear = BIT(m_scr, 5) &&
		(m_ssr & m_sci_ssr_read & SSR_TDRE) && !BIT(data, 7);
	if (tdre_clear)
		m_ssr &= ~(SSR_TDRE | SSR_TEND);
	m_ssr = (m_ssr & (~m_sci_ssr_read | data | SSR_TDRE | SSR_TEND | SSR_MPB) & 0xfe)
		| (data & 0x01);
	// Consume acknowledgements before TSR loading can raise TDRE again.
	m_sci_ssr_read &= m_ssr;

	// Section 13.3.2, p.359 steps 1-2: loading TSR makes TDR available
	// again. A running transmitter consumes queued data at the stop bit.
	// In synchronous mode, a queued character can also
	// start after receive errors are acknowledged (section 13.5, p.381).
	if (BIT(m_scr, 5) && !m_sci_tx_active && !(m_ssr & SSR_TDRE) &&
		(!BIT(m_smr, 7) || !(m_ssr & (SSR_ORER | SSR_FER | SSR_PER))))
	{
		m_tsr = m_tdr;
		m_ssr |= SSR_TDRE;
		sci_transmit_start();
	}
	sci_update_clock();
	sh2_recalc_irq();
}

uint8_t sh7604_device::rdr_r()
{
	return m_rdr;
}

void sh7604_device::sck_w(int state)
{
	bool const level = state != 0;
	bool const previous = m_sci_sck;
	m_sci_sck = level;
	if (level == previous || !BIT(m_scr, 1))
		return;

	if (BIT(m_smr, 7))
		sci_sync_edge(level);
	else if (level)
	{
		// External async SCK is the 16x base clock (section 13.3.2 p.356).
		// TX advances once per sixteen rising edges, independently of RX.
		if (m_sci_tx_active && BIT(m_scr, 5) && ++m_sci_tx_phase == 16)
		{
			m_sci_tx_phase = 0;
			sci_tx_tick(m_sci_tx_bit);
		}
		sci_rx_tick(0);
	}
}

void sh7604_device::sci_sync_edge(bool level)
{
	// SH7604 section 13.3.4, pp.372, 375-378: synchronous
	// receive starts on a falling SCK edge and samples on rising edges.
	// A character is always eight data bits, without start/parity/stop/MP.
	if (m_ssr & (SSR_ORER | SSR_FER | SSR_PER))
	{
		m_sci_rx_state = 0;
		return;
	}

	// Section 13.3.4, pp.372-373: TX changes on falling SCK edges. Load
	// the next byte or set TEND when the MSB is output; TxD then holds
	// that MSB until another byte starts (or TE is cleared).
	if (!level && BIT(m_scr, 5) && m_sci_tx_active)
	{
		m_write_txd(BIT(m_tsr, m_sci_tx_bit));
		if (++m_sci_tx_bit == 8)
		{
			m_sci_tx_bit = 0;
			if (!(m_ssr & SSR_TDRE))
			{
				m_tsr = m_tdr;
				m_ssr |= SSR_TDRE;
			}
			else
			{
				m_sci_tx_active = false;
				m_ssr |= SSR_TEND;
			}
			sh2_recalc_irq();
		}
	}

	if (!BIT(m_scr, 4))
		return;

	if (!level)
	{
		if (!m_sci_rx_state)
		{
			m_sci_rx_state = 1;
			m_sci_rx_bitcnt = 0;
			m_sci_rx_shift = 0;
		}
	}
	else if (m_sci_rx_state)
	{
		m_sci_rx_shift |= (m_read_rxd(0) != 0) << m_sci_rx_bitcnt;
		if (++m_sci_rx_bitcnt == 8)
		{
			m_sci_rx_state = 0;
			sci_rx_complete(m_sci_rx_shift, false, false);
		}
	}
}

void sh7604_device::sci_update_clock()
{
	bool const synchronous = BIT(m_smr, 7);
	bool const internal = !BIT(m_scr, 1) && (synchronous || BIT(m_scr, 0));
	bool const error = m_ssr & (SSR_ORER | SSR_FER | SSR_PER);
	bool const enabled = BIT(m_scr, 5) || BIT(m_scr, 4);
	// Receive-only mode clocks while RE is set. In full duplex, TX starts
	// the shared clock and RX must finish sampling the final transmitted bit.
	bool const work = (BIT(m_scr, 5) && m_sci_tx_active) ||
		(BIT(m_scr, 4) && (!BIT(m_scr, 5) || m_sci_rx_state));
	// Async CKE=01 outputs a continuous baud-rate clock, even with TE/RE
	// clear (section 13.3.2 p.356, initialization step 3).
	if (!internal || (synchronous && (!enabled || error || (!work && m_sci_sck_out))))
	{
		m_sci_clock_running = false;
		m_sci_clock_timer->adjust(attotime::never);
		if (!m_sci_sck_out)
		{
			m_sci_sck_out = true;
			m_write_sck(1);
		}
	}
	else if (!m_sci_clock_running)
	{
		m_sci_clock_running = true;
		m_sci_clock_timer->adjust(sci_bit_period() / 2);
	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::sci_clock_tick)
{
	if (!m_sci_clock_running)
		return;

	m_sci_sck_out = !m_sci_sck_out;
	// Make TX data valid before notifying the peer of a falling edge.
	// On rising edges, notify the peer before sampling its receive data.
	if (!m_sci_sck_out)
	{
		if (BIT(m_smr, 7))
			sci_sync_edge(false);
		else if (m_sci_tx_active)
		{
			// Figure 13.3: async data boundaries are falling SCK edges,
			// placing each rising edge at the center of the transmitted bit.
			sci_tx_tick(m_sci_tx_bit);
			// A completed stop interval may have armed the next frame.
			// Emit its start on this edge, not one bit period later.
			if (m_sci_tx_active && m_sci_tx_bit == 0)
				sci_tx_tick(0);
		}
	}
	m_write_sck(m_sci_sck_out);
	if (m_sci_sck_out && BIT(m_smr, 7))
		sci_sync_edge(true);

	// Always finish the last low half-period: TEND rises on MSB output,
	// but its rising sample edge still belongs to this character (p.373).
	sci_update_clock();
	if (m_sci_clock_running)
		m_sci_clock_timer->adjust(sci_bit_period() / 2);
}

attotime sh7604_device::sci_bit_period() const
{
	// B = phi / ((N+1) * 2^(7+2n)) in asynchronous mode and
	// B = phi / ((N+1) * 2^(4+2n)) in clocked synchronous mode.
	// Verified against Tables 13.3/13.4/13.6 (pp.347-350): f=4MHz n=0 N=0
	// async gives 31250 baud, f=14.7456MHz n=0 N=0 gives 115200, and the
	// per-row N values of Tables 13.3/13.4 reproduce with these divisors.
	uint32_t const ticks = (uint32_t)(m_brr + 1)
		<< (((m_smr & 0x80) ? 4 : 7) + 2 * (m_smr & 3));
	return attotime::from_ticks(ticks, clock());
}

void sh7604_device::sci_recalc_rates()
{
	// Sync and async clock-output modes use the shared SCK generator.
	sci_update_clock();
	if (BIT(m_smr, 7))
		return;
	if (m_sci_tx_active && BIT(m_scr, 5) && (m_scr & 3) == 0)
		m_sci_tx_timer->adjust(sci_bit_period(), m_sci_tx_bit);
	else
		m_sci_tx_timer->adjust(attotime::never);
	if (m_sci_rx_enabled && !BIT(m_scr, 1))
		m_sci_rx_timer->adjust(sci_bit_period() / 16, m_sci_rx_phase);
	else
		m_sci_rx_timer->adjust(attotime::never);
}

void sh7604_device::sci_transmit_start()
{
	// TDR is already in TSR. Sync and async SCK-output modes wait for
	// a falling edge. Other async modes emit the start bit immediately.
	m_sci_tx_bit = BIT(m_smr, 7) ? 0 : 1; // next sync data bit / async timer event
	m_sci_tx_phase = 0;
	m_sci_tx_active = true;
	m_sci_tx_loaded = false;
	if (BIT(m_smr, 7) || (m_scr & 3) == 1)
	{
		m_sci_tx_bit = 0; // async zero denotes the pending start bit
		sci_update_clock();
	}
	else if (BIT(m_scr, 5))
	{
		m_write_txd(0); // start bit
		if (!BIT(m_scr, 1))
			m_sci_tx_timer->adjust(sci_bit_period(), m_sci_tx_bit);
	}
}

TIMER_CALLBACK_MEMBER(sh7604_device::sci_tx_tick)
{
	if (!m_sci_tx_active || !BIT(m_scr, 5) || BIT(m_smr, 7))
		return;

	uint8_t const data_bits = BIT(m_smr, 6) ? 7 : 8;
	bool const parity_enable = BIT(m_smr, 5) && !BIT(m_smr, 2);
	bool const mp_mode = BIT(m_smr, 2);
	uint8_t const stop_bits = BIT(m_smr, 3) ? 2 : 1;
	// bit positions after the start bit: data + (parity|MP) + stop
	uint8_t const frame_bits = data_bits
		+ (mp_mode ? 1 : (parity_enable ? 1 : 0))
		+ stop_bits;

	// Retain ownership of TxD for the entire last stop bit, even when
	// TEND has already risen. Software may queue a byte during that bit.
	if (param > frame_bits)
	{
		if (!m_sci_tx_loaded && !BIT(m_ssr, 7))
		{
			m_tsr = m_tdr;
			m_ssr |= SSR_TDRE;
			m_sci_tx_loaded = true;
			sh2_recalc_irq();
		}
		if (m_sci_tx_loaded)
			sci_transmit_start();
		else
			m_sci_tx_active = false;
		return;
	}

	int bit;
	if (param == 0)
	{
		bit = 0; // start bit deferred to a falling SCK output edge
	}
	else if (param <= data_bits)
	{
		// data bits, LSB first; 7-bit characters do not transmit the MSB
		bit = (m_tsr >> (param - 1)) & 1;
	}
	else if (mp_mode && param == data_bits + 1)
	{
		bit = BIT(m_ssr, 0); // MPBT
	}
	else if (parity_enable && param == data_bits + 1)
	{
		uint8_t const mask = (1 << data_bits) - 1;
		bit = (std::popcount(unsigned(m_tsr & mask)) & 1) ^ BIT(m_smr, 4);
	}
	else
	{
		bit = 1; // stop bit(s)
	}

	m_write_txd(bit);

	// Asynchronous transmission checks TDRE at the last stop bit, not
	// at the data MSB (SH7604 manual section 13.3.2, p.359 step 3).
	// Keep the current TSR intact through parity; only then load the next
	// character, raise TXI, and start it after a full stop-bit interval.
	if (param == frame_bits)
	{
		m_sci_tx_loaded = !BIT(m_ssr, 7);
		if (m_sci_tx_loaded)
		{
			m_tsr = m_tdr;
			m_ssr |= SSR_TDRE;
		}
		else
			m_ssr |= SSR_TEND;
		sh2_recalc_irq();
	}

	m_sci_tx_bit = param + 1;
	if ((m_scr & 3) == 0)
		m_sci_tx_timer->adjust(sci_bit_period(), m_sci_tx_bit);
}

TIMER_CALLBACK_MEMBER(sh7604_device::sci_rx_tick)
{
	if (!m_sci_rx_enabled || !BIT(m_scr, 4) || BIT(m_smr, 7))
		return;

	// a latched error stops reception until the flag is cleared (pp.344-345)
	if (m_ssr & (SSR_ORER | SSR_FER | SSR_PER))
	{
		if (!BIT(m_scr, 1))
			m_sci_rx_timer->adjust(sci_bit_period() / 16, m_sci_rx_phase);
		return;
	}

	bool const line = m_read_rxd(0) != 0;

	switch (m_sci_rx_state)
	{
	case 0: // idle: look for a start bit edge
		if (!line)
		{
			m_sci_rx_state = 1;
			// The next timer pulse is the first after synchronization.
			// Sample eight pulses later (section 13.5, Figure 13.21).
			m_sci_rx_phase = 1;
			m_sci_rx_shift = 0;
			m_sci_rx_parity_error = false;
			m_sci_rx_mp = false;
			m_sci_rx_bitcnt = 0;
		}
		break;

	case 1: // inside a frame, oversampling at 16x the bit rate
		{
			uint8_t const data_bits = BIT(m_smr, 6) ? 7 : 8;
			bool const parity_enable = BIT(m_smr, 5) && !BIT(m_smr, 2);
			bool const mp_mode = BIT(m_smr, 2);
			uint8_t const total_bits = data_bits
				+ (mp_mode || parity_enable ? 1 : 0)
				+ 1; // first stop bit

			if (m_sci_rx_phase == 8)
			{
				// "The SCI samples each data bit on the eighth pulse of a
				// clock with a frequency 16 times the bit rate" (p.354)
				bool const bit = line;

				if (m_sci_rx_bitcnt == 0 && bit == 0)
				{
					// start bit confirmed
				}
				else if (m_sci_rx_bitcnt == 0 && bit == 1)
				{
					// false start: back to idle
					m_sci_rx_state = 0;
				}
				else if (m_sci_rx_bitcnt <= data_bits)
				{
					m_sci_rx_shift |= bit << (m_sci_rx_bitcnt - 1);
				}
				else if (m_sci_rx_bitcnt == data_bits + 1 && mp_mode)
				{
					m_sci_rx_mp = bit;
				}
				else if (m_sci_rx_bitcnt == data_bits + 1 && parity_enable)
				{
					uint8_t const mask = (1 << data_bits) - 1;
					// Defer publication until the stop-bit sample so PER, FER
					// and ORER can be reported together (Table 13.14).
					m_sci_rx_parity_error =
						((std::popcount(unsigned(m_sci_rx_shift & mask)) & 1) ^ BIT(m_smr, 4)) != bit;
				}
				else if (m_sci_rx_bitcnt == total_bits)
				{
					// first stop bit must be 1 (only the first is checked, p.338)
					// Section 13.2.6 p.341 / Figure 13.13: in MP mode,
					// MPIE discards data/error results until an address
					// character (MPB=1) wakes the receiver. MPB is the
					// received value, not a sticky one-bit flag.
					if (mp_mode)
					{
						m_ssr = (m_ssr & ~SSR_MPB) | (m_sci_rx_mp ? SSR_MPB : 0);
						if (m_sci_rx_mp)
							m_scr &= ~0x08; // hardware clears MPIE
					}
					if (!mp_mode || !BIT(m_scr, 3))
						sci_rx_complete(m_sci_rx_shift, m_sci_rx_parity_error, !bit);
					m_sci_rx_state = 0;
					if (!BIT(m_scr, 1))
						m_sci_rx_timer->adjust(sci_bit_period() / 16, 0);
					return;
				}
				m_sci_rx_bitcnt++;
			}

			m_sci_rx_phase = (m_sci_rx_phase + 1) & 15;
		}
		break;
	}

	if (!BIT(m_scr, 1))
		m_sci_rx_timer->adjust(sci_bit_period() / 16, 0);
}

void sh7604_device::sci_rx_complete(uint8_t data, bool parity_error, bool framing_error)
{
	// SH7604 manual section 13.5, p.381 Table 13.14: errors latch
	// independently. An overrun preserves the unread RDR even when the
	// incoming character also has a parity and/or framing error.
	if (framing_error)
		m_ssr |= SSR_FER;
	if (parity_error)
		m_ssr |= SSR_PER;
	if (m_ssr & SSR_RDRF)
		m_ssr |= SSR_ORER;
	else
	{
		m_rdr = data;
		if (!parity_error && !framing_error)
			m_ssr |= SSR_RDRF;
	}
	sh2_recalc_irq();
}

/*
 * FRC
 */

uint8_t sh7604_device::tier_r()
{
	return m_tier;
}

void sh7604_device::tier_w(uint8_t data)
{
	sh2_timer_resync();
	m_tier = data;
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint8_t sh7604_device::ftcsr_r()
{
	// Section 11.2.5 pp.300-301: only flags read as one may be cleared.
	// Debugger inspection must neither arm acknowledgements nor invoke
	// the legacy CPU-read callback.
	if (!machine().side_effects_disabled())
	{
		if (!m_ftcsr_read_cb.isnull())
			m_ftcsr_read_cb((((m_tier << 24) | (m_ftcsr << 16)) & 0xffff0000) | m_frc);
		m_ftcsr_read = m_ftcsr & (ICF | OCFA | OCFB | OVF);
	}
	return m_ftcsr;
}

void sh7604_device::ftcsr_w(uint8_t data)
{
	sh2_timer_resync();
	// ICF/OCFA/OCFB/OVF are read-one/write-zero flags. CCLRA is ordinary
	// read/write; reserved bits 6-4 remain zero. A consumed acknowledgement
	// must not clear a later event without another status read.
	m_ftcsr = (m_ftcsr & (ICF | OCFA | OCFB | OVF) & (~m_ftcsr_read | data))
		| (data & CCLRA);
	m_ftcsr_read &= m_ftcsr;
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint16_t sh7604_device::frc_r(offs_t offset, uint16_t mem_mask)
{
	sh2_timer_resync();
	if (machine().side_effects_disabled())
		return m_frc;

	// Section 11.3: the high-byte read snapshots the low byte in the
	// single TEMP latch shared by FRC, ICR and OCR accesses.
	if (mem_mask & 0xff00)
		m_frt_temp = m_frc;
	return (m_frc & 0xff00) | m_frt_temp;
}

void sh7604_device::frc_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	// High-byte writes only stage TEMP. The low-byte write commits the
	// full counter; a full-width access executes both steps in order.
	if (mem_mask & 0xff00)
		m_frt_temp = data >> 8;
	if (mem_mask & 0x00ff)
	{
		sh2_timer_resync();
		m_frc = (uint16_t(m_frt_temp) << 8) | (data & 0xff);
		sh2_timer_activate();
		sh2_recalc_irq();
	}
}

uint16_t sh7604_device::ocra_b_r()
{
	return (m_tocr & 0x10) ? m_ocrb : m_ocra;
}

void sh7604_device::ocra_b_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (mem_mask & 0xff00)
		m_frt_temp = data >> 8;
	if (mem_mask & 0x00ff)
	{
		sh2_timer_resync();
		// OCRS selects the destination at commit; TEMP has no register tag.
		if (m_tocr & 0x10)
			m_ocrb = (uint16_t(m_frt_temp) << 8) | (data & 0xff);
		else
			m_ocra = (uint16_t(m_frt_temp) << 8) | (data & 0xff);
		sh2_timer_activate();
		sh2_recalc_irq();
	}
}

uint8_t sh7604_device::frc_tcr_r()
{
	return m_frc_tcr & 0x83;
}

void sh7604_device::frc_tcr_w(uint8_t data)
{
	sh2_timer_resync();
	// Retain the existing fresh-interval convention when changing clocks;
	// writes to the input edge selector alone must preserve divider phase.
	if ((m_frc_tcr ^ data) & 3)
		m_frc_base = total_cycles();
	m_frc_tcr = data & 0x83;
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
	// Output levels A/B (bits 1-0) take effect on their next compare.
	m_tocr = data & 0x13;
	sh2_timer_activate();
	sh2_recalc_irq();
}

uint16_t sh7604_device::frc_icr_r(offs_t offset, uint16_t mem_mask)
{
	if (machine().side_effects_disabled())
		return m_frc_icr;
	if (mem_mask & 0xff00)
		m_frt_temp = m_frc_icr;
	return (m_frc_icr & 0xff00) | m_frt_temp;
}

/*
 * INTC
 */

uint16_t sh7604_device::intc_icr_r()
{
	// TODO: flip meaning based off NMI edge select bit (NMIE)
	uint16_t nmilv = m_nmi_line_state == ASSERT_LINE ? 0 : 0x8000;
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

// VCRDIV is a word register where bits 6-0 have a meaning, reads back written word value
uint32_t sh7604_device::vcrdiv_r()
{
	return m_vcrdiv & 0xffff;
}

void sh7604_device::vcrdiv_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_vcrdiv);
	// TODO: unemulated, level is seemingly not documented/settable?
	m_irq_vector.divu = m_vcrdiv & 0x7f;
	sh2_recalc_irq();
}

/*
 * DIVU
 */

uint32_t sh7604_device::dvcr_r()
{
	return (m_divu_ovfie << 1) | (m_divu_ovf << 0);
}

void sh7604_device::dvcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (ACCESSING_BITS_0_7)
	{
		// both bits are regular r/w
		// - vblokbrk/sarukani writes a '0' to clear a divide by zero OVF when beating
		//   a stage with game timer <= 10
		m_divu_ovf = BIT(data, 0);
		m_divu_ovfie = BIT(data, 1);
		if (m_divu_ovfie)
			LOG("SH2: unemulated DIVU OVF interrupt enable\n");
		sh2_recalc_irq();
	}
}

uint32_t sh7604_device::dvsr_r()
{
	return m_dvsr;
}

void sh7604_device::dvsr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_dvsr);
}

uint32_t sh7604_device::dvdnt_r()
{
	return m_dvdntl;
}

void sh7604_device::dvdnt_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// TODO: this is really a separate register that happens to be shared with DVDNTL
	COMBINE_DATA(&m_dvdntl);
	int32_t a = m_dvdntl;
	int32_t b = m_dvsr;
	LOG("SH2 div32+mod %d/%d\n", a, b);
	if (b)
	{
		m_dvdntl = a / b;
		m_dvdnth = a % b;
		// TODO: 40 cycles
	}
	else
	{
		m_divu_ovf = true;
		m_dvdntl = 0x7fffffff;
		m_dvdnth = 0x7fffffff;
		sh2_recalc_irq();
		// TODO: 8 cycles
	}
}

uint32_t sh7604_device::dvdnth_r()
{
	return m_dvdnth;
}

uint32_t sh7604_device::dvdntl_r()
{
	return m_dvdntl;
}

void sh7604_device::dvdnth_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_dvdnth);
}

void sh7604_device::dvdntl_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	COMBINE_DATA(&m_dvdntl);
	int64_t a = m_dvdntl | ((uint64_t)m_dvdnth << 32);
	int64_t b = (int32_t)m_dvsr;
	LOG("SH2 div64+mod %d/%d\n", a, b);
	// This positive quotient exceeds even the host signed 64-bit range.
	// Enter the existing DIVU overflow path without evaluating undefined / or %.
	if (b && !(a == INT64_MIN && b == -1))
	{
		int64_t q = a / b;
		if (q != (int32_t)q)
		{
			m_divu_ovf = true;
			// With OVFIE=0, the quotient saturates according to its sign
			// (section 10.3.3). OVFIE=1 intermediate results remain TODO.
			m_dvdntl = (!m_divu_ovfie && q < 0) ? 0x80000000 : 0x7fffffff;
			m_dvdnth = 0x7fffffff;
			sh2_recalc_irq();
			// TODO: 6 cycles, plenty of these in saturn:vkyoute2
		}
		else
		{
			m_dvdntl = q;
			m_dvdnth = a % b;
			// TODO: 39 cycles
		}
	}
	else
	{
		m_divu_ovf = true;
		m_dvdntl = 0x7fffffff;
		m_dvdnth = 0x7fffffff;
		sh2_recalc_irq();
		// TODO: 6 cycles
	}
}

/*
 * UBC
 */

// TODO: bare-bones, used for proper 32x:aburnerju sound (on slave side) as buffer storage

uint16_t sh7604_device::barah_r()
{
	return m_barah;
}

uint16_t sh7604_device::baral_r()
{
	return m_baral;
}

void sh7604_device::barah_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_barah);
}

void sh7604_device::baral_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_baral);
}

uint16_t sh7604_device::barbh_r()
{
	return m_barbh;
}

uint16_t sh7604_device::barbl_r()
{
	return m_barbl;
}

void sh7604_device::barbh_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_barbh);
}

void sh7604_device::barbl_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	COMBINE_DATA(&m_barbl);
}

/*
 * WTC
 */

uint16_t sh7604_device::wtcnt_r(offs_t offset, uint16_t mem_mask)
{
	sh2_wtcnt_recalc();
	// WTCSR occupies the high read lane; a WTCNT-only or debugger read
	// must not qualify an overflow acknowledgement (section 12.2.2).
	if ((mem_mask & 0xff00) && !machine().side_effects_disabled())
		m_wdt_read = (m_wdt_read & ~1) | BIT(m_wtcsr, 7);
	return ((m_wtcsr | 0x18) << 8) | (m_wtcnt & 0xff);
}

uint16_t sh7604_device::rstcsr_r(offs_t offset, uint16_t mem_mask)
{
	// RSTCSR is the low read lane, at H'FFFFFE83 (section 12.2.4).
	if ((mem_mask & 0x00ff) && !machine().side_effects_disabled())
		m_wdt_read = (m_wdt_read & ~2) | (BIT(m_rstcsr, 7) << 1);
	return (m_rstcsr & 0xe0) | 0x1f;
}

void sh7604_device::wdt_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	// Section 12.2.4 requires a keyed word, not a byte or longword write.
	// Check at the native 32-bit map boundary before a longword can be
	// decomposed into two apparently valid word commands. SH-2 is big-endian.
	if (mem_mask == 0xffff0000)
		wtcnt_w(0, data >> 16, 0xffff);
	else if (mem_mask == 0x0000ffff)
		rstcsr_w(0, data, 0xffff);
}

void sh7604_device::wtcnt_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	// Section 12.2.4 pp.324-325: the key and payload must arrive in
	// one word write. Byte writes cannot reuse or assemble a prior key.
	if (mem_mask != 0xffff)
		return;

	COMBINE_DATA(&m_wtcw[0]);
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
			// OVF is read-one/write-zero, not an unconditional write-zero
			// flag. Consume the read when cleared so a new event is protected.
			m_wtcsr = (m_wtcsr & 0x80 & ((m_wdt_read & 1) ? m_wtcw[0] : 0x80))
				| (m_wtcw[0] & 0x7f);
			if (!(m_wtcsr & 0x80))
				m_wdt_read &= ~1;
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
	// Section 12.2.4 pp.324-325: the key and payload must arrive in
	// one word write. Byte writes cannot reuse or assemble a prior key.
	if (mem_mask != 0xffff)
		return;

	COMBINE_DATA(&m_wtcw[1]);
	switch (m_wtcw[1] & 0xff00)
	{
		case 0xa500:
			// clear WOVF flag
			if ((m_wdt_read & 2) && (m_wtcw[1] & 0x80) == 0)
			{
				m_rstcsr &= 0x7f;
				m_wdt_read &= ~2;
			}
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
		uint8_t const old_sbycr = m_sbycr;
		m_sbycr = data;
		// MSTP0 initializes the SCI, but not its INTC vector registers
		// (section 14.2.1 p.388). Clearing it leaves SCI at reset state.
		// Section 14.5 forbids SCI accesses while stopped and switching
		// a running module to standby; no paused-frame resume is implied.
		if (BIT(m_sbycr, 0) && !BIT(old_sbycr, 0))
		{
			sci_reset();
			sh2_recalc_irq();
		}
		if (BIT(old_sbycr ^ m_sbycr, 1))
		{
			if (BIT(m_sbycr, 1))
				frt_reset();
			else
			{
				// Do not charge the stopped interval to FRC on release.
				m_frc_base = total_cycles();
				sh2_timer_activate();
			}
			sh2_recalc_irq();
		}
		if (data & 0x1c)
			logerror("SH2 module stop selected %02x\n", data);
		break;
	}
	}
}

uint8_t sh7604_device::ccr_r()
{
	return m_ccr & ~0x30;
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
	m_ccr = data;
}

// BSC registers permit 16-bit reads, but writes require a complete 32-bit
// access with A55A in the upper half (section 7.1.4, Table 7.2).
// Longword reads return zero in the upper half.
uint32_t sh7604_device::bcr1_r()
{
	return (m_bcr1 & 0x1ff7) | (m_is_slave ? 0x8000 : 0);
}

void sh7604_device::bcr1_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	COMBINE_DATA(&m_bcr1);
	m_bcr1 &= 0xffff;
}

uint32_t sh7604_device::bcr2_r()
{
	// Only A3SZ, A2SZ and A1SZ are readable; reserved bits read zero.
	return m_bcr2 & 0x00fc;
}

void sh7604_device::bcr2_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	COMBINE_DATA(&m_bcr2);
	m_bcr2 &= 0xffff;
}

uint32_t sh7604_device::wcr_r()
{
	return m_wcr & 0xffff;
}

void sh7604_device::wcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	COMBINE_DATA(&m_wcr);
}

uint32_t sh7604_device::mcr_r()
{
	return m_mcr & 0xfefc;
}

void sh7604_device::mcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	COMBINE_DATA(&m_mcr);
}

uint32_t sh7604_device::rtcsr_r(offs_t offset, uint32_t mem_mask)
{
	// CMF clearing requires a status read as one (section 7.2.5).
	// Only the permitted longword/low-word reads qualify, not an upper
	// word, unsupported partial read, or debugger inspection.
	if ((mem_mask == 0xffffffff || mem_mask == 0x0000ffff) && !machine().side_effects_disabled())
		m_rtcsr_read = bool(m_rtcsr & 0x80);
	return m_rtcsr & 0xf8;
}

void sh7604_device::rtcsr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	// Software cannot set CMF; a read-one/write-zero sequence clears it.
	// Consume the qualification so a subsequent match needs a fresh read.
	m_rtcsr = (data & ~0x80U) | (m_rtcsr & 0x80 & (m_rtcsr_read ? data : 0x80U));
	if (!(m_rtcsr & 0x80))
		m_rtcsr_read = false;
}

uint32_t sh7604_device::rtcnt_r()
{
	return m_rtcnt & 0xff;
}

void sh7604_device::rtcnt_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	COMBINE_DATA(&m_rtcnt);
	m_rtcnt &= 0xff;
}

uint32_t sh7604_device::rtcor_r()
{
	return m_rtcor & 0xff;
}

void sh7604_device::rtcor_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (mem_mask != 0xffffffff || (data >> 16) != 0xa55a)
		return;

	COMBINE_DATA(&m_rtcor);
	m_rtcor &= 0xff;
}

void sh7604_device::set_frt_input(int state)
{
	if (m_frt_input == state)
		return;

	m_frt_input = state;
	// Keep pin history, but no input capture is clocked during module stop.
	if (BIT(m_sbycr, 1))
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

	sh2_timer_resync();
	m_frc_icr = m_frc;
	m_ftcsr |= ICF;
	//logerror("SH2.%s: ICF activated (%x)\n", tag(), m_sh2_state->pc & AM);
	sh2_recalc_irq();
}

void sh7604_device::sh2_recalc_irq()
{
	int irq = 0;
	int vector = -1;
	int level;

	// Timer irqs
	if (m_tier & m_ftcsr & (ICF | OCFA | OCFB | OVF))
	{
		level = (m_irq_level.frc & 15);
		if (level > irq)
		{
			int mask = m_tier & m_ftcsr;
			irq = level;
			if (mask & ICF)
				vector = m_irq_vector.fic & 0x7f;
			else if (mask & (OCFA | OCFB))
				vector = m_irq_vector.foc & 0x7f;
			else
				vector = m_irq_vector.fov & 0x7f;
		}
	}

	// WDT irqs
	if (m_wtcsr & 0x80)
	{
		level = m_irq_level.wdt & 15;
		if (level > irq)
		{
			irq = level;
			vector = (m_vcrwdt >> 8) & 0x7f;
		}
	}

	// DMA irqs
	if ((m_dmac[0].chcr & 6) == 6 && m_dma_irq[0])
	{
		level = m_irq_level.dmac & 15;
		if (level > irq)
		{
			irq = level;
			m_dma_irq[0] &= ~1;
			vector = m_irq_vector.dmac[0] & 0x7f;
		}
	}
	else if ((m_dmac[1].chcr & 6) == 6 && m_dma_irq[1])
	{
		level = m_irq_level.dmac & 15;
		if (level > irq)
		{
			irq = level;
			m_dma_irq[1] &= ~1;
			vector = m_irq_vector.dmac[1] & 0x7f;
		}
	}

	// SCI irqs: ERI > RXI > TXI > TEI, vectors in VCRA/VCRB, level in IPRB
	// (SH7604 Hardware Manual pp.91-92, Table 13.13)
	level = m_irq_level.sci & 15;
	if (level > irq)
	{
		if ((m_ssr & (SSR_ORER | SSR_FER | SSR_PER)) && (m_scr & 0x40))
		{
			irq = level;
			vector = m_vcra & 0x7f; // SERV: ERI
		}
		else if ((m_ssr & SSR_RDRF) && (m_scr & 0x40))
		{
			irq = level;
			vector = (m_vcra >> 8) & 0x7f; // SRXV: RXI
		}
		else if ((m_ssr & SSR_TDRE) && (m_scr & 0x80))
		{
			irq = level;
			vector = m_vcrb & 0x7f; // STXV: TXI
		}
		else if ((m_ssr & SSR_TEND) && (m_scr & 0x04))
		{
			irq = level;
			vector = (m_vcrb >> 8) & 0x7f; // STEV: TEI
		}
	}

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
	return m_dmac[Channel].chcr;
}

template <int Channel>
void sh7604_device::chcr_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	uint32_t old;
	old = m_dmac[Channel].chcr;
	COMBINE_DATA(&m_dmac[Channel].chcr);
	m_dmac[Channel].chcr = (data & ~2) | (old & m_dmac[Channel].chcr & 2);
	sh2_dmac_check(Channel);
}

uint32_t sh7604_device::dmaor_r()
{
	return m_dmaor & 0xf;
}

void sh7604_device::dmaor_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (ACCESSING_BITS_0_7)
	{
		uint8_t old = m_dmaor & 0xf;
		m_dmaor = (data & ~6) | (old & data & 6);
		sh2_dmac_check(0);
		sh2_dmac_check(1);
	}
}

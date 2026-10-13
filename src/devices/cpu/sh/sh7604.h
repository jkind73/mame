// license:BSD-3-Clause
// copyright-holders:Juergen Buchmueller, R. Belmont

// sh7604, sh2 variant

#ifndef MAME_CPU_SH_SH7604_H
#define MAME_CPU_SH_SH7604_H

#pragma once

#include "sh2.h"

#define SH2_DMA_KLUDGE_CB(name)  int name(uint32_t src, uint32_t dst, uint32_t data, int size)
#define SH2_DMA_FIFO_DATA_AVAILABLE_CB(name)  int name(uint32_t src, uint32_t dst, uint32_t data, int size)
#define SH2_FTCSR_READ_CB(name)  void name(uint32_t data)


class sh7604_device : public sh2_device
{
public:
	typedef device_delegate<int (uint32_t src, uint32_t dst, uint32_t data, int size)> dma_kludge_delegate;
	typedef device_delegate<int (uint32_t src, uint32_t dst, uint32_t data, int size)> dma_fifo_data_available_delegate;
	typedef device_delegate<void (uint32_t data)> ftcsr_read_delegate;

	sh7604_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	void set_is_slave(int slave) { m_is_slave = slave; }
	// Model the cache (section 8): the associative purge, address array and
	// data array windows, and cache lookups on cache-area accesses.
	void set_cache_emulation(bool enable) { m_cache_model = enable; }
	// Cost of external bus accesses (see sh2_device::bus_timing_delegate).
	template <typename... T> void set_bus_timing_callback(T &&... args) { m_bus_timing.set(std::forward<T>(args)...); }

	template <typename... T> void set_dma_kludge_callback(T &&... args) { m_dma_kludge_cb.set(std::forward<T>(args)...); }

	template <typename... T> void set_dma_fifo_data_available_callback(T &&... args) { m_dma_fifo_data_available_cb.set(std::forward<T>(args)...); }

	template <typename... T> void set_ftcsr_read_callback(T &&... args) { m_ftcsr_read_cb.set(std::forward<T>(args)...); }

	void dma_request_w(unsigned channel, int level);
	void dreq0_w(int level) { dma_request_w(0, level); }
	void dreq1_w(int level) { dma_request_w(1, level); }
	template <unsigned Channel> auto dma_ack_handler() { return m_dma_dack[Channel].bind(); }
	template <unsigned Channel> auto dma_read_handler() { return m_dma_read[Channel].bind(); }
	template <unsigned Channel> auto dma_write_handler() { return m_dma_write[Channel].bind(); }
	void sh2_notify_dma_data_available();
	void frt_clock_w(int state);
	auto frt_output_a_handler() { return m_ftoa.bind(); }
	auto frt_output_b_handler() { return m_ftob.bind(); }
	void sci_rxd_w(int state);
	void sci_sck_w(int state);
	auto sci_txd_handler() { return m_sci_txd.bind(); }
	auto sci_sck_handler() { return m_sci_sck.bind(); }
	auto sci_tx_handler() { return m_sci_tx.bind(); }
	auto standby_hiz_handler() { return m_standby_hiz.bind(); }
	auto ckpack_handler() { return m_ckpack.bind(); }
	void ckpreq_w(int state);
	void ubc_external_cycle(uint32_t address, bool write);

protected:
	void bsc_endian_update();
	sh7604_device(const machine_config &mconfig, device_type type, const char *tag, device_t *owner, uint32_t clock, int cpu_type, address_map_constructor internal_map, int addrlines);

	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_clock_changed() override;

	virtual void sh2_exception(const char *message, int irqline) override;
	virtual void sleep_enter(unsigned pending_cycles) override;
	virtual void execute_set_input(int inputnum, int state) override;
	virtual void state_import(const device_state_entry &entry) override;
	virtual void state_export(const device_state_entry &entry) override;

private:
	// Keep internal DMA bus tenure independent of the external HALT input.
	static constexpr uint32_t SUSPEND_REASON_DMA = 0x0080;
	enum
	{
		ICF  = 0x80,
		OCFA = 0x08,
		OCFB = 0x04,
		OVF  = 0x02,
		CCLRA = 0x01
	};

	void sh7604_map(address_map &map) ATTR_COLD;

	uint32_t sh2_internal_a5();
	attotime dma_unit_time(uint32_t src, uint32_t dst, unsigned bytes, bool burst);
	uint32_t cache_purge_r(offs_t offset);
	void cache_purge_w(offs_t offset, uint32_t data);
	uint32_t cache_address_r(offs_t offset, uint32_t mem_mask);
	void cache_address_w(offs_t offset, uint32_t data);
	uint32_t cache_data_r(offs_t offset);
	void cache_data_w(offs_t offset, uint32_t data, uint32_t mem_mask);

	// SCI
	uint8_t smr_r();
	void smr_w(uint8_t data);
	uint8_t brr_r();
	void brr_w(uint8_t data);
	uint8_t scr_r();
	void scr_w(uint8_t data);
	uint8_t tdr_r();
	void tdr_w(uint8_t data);
	uint8_t ssr_r();
	void ssr_w(uint8_t data);
	uint8_t rdr_r();

	// FRT / FRC
	uint8_t tier_r();
	void tier_w(uint8_t data);
	uint16_t frc_r(offs_t offset, uint16_t mem_mask);
	void frc_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint8_t ftcsr_r();
	void ftcsr_w(uint8_t data);
	uint16_t ocra_b_r();
	void ocra_b_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint8_t frc_tcr_r();
	void frc_tcr_w(uint8_t data);
	uint8_t tocr_r();
	void tocr_w(uint8_t data);
	uint16_t frc_icr_r(offs_t offset, uint16_t mem_mask);

	// INTC
	uint16_t ipra_r();
	void ipra_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t iprb_r();
	void iprb_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t vcra_r();
	void vcra_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t vcrb_r();
	void vcrb_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t vcrc_r();
	void vcrc_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t vcrd_r();
	void vcrd_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t vcrwdt_r();
	void vcrwdt_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint32_t vcrdiv_r();
	void vcrdiv_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint16_t intc_icr_r();
	void intc_icr_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

	// DIVU
	uint32_t dvsr_r();
	void dvsr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t dvdnt_r();
	void dvdnt_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t dvdnth_r();
	void dvdnth_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t dvdntl_r();
	void dvdntl_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);

	uint32_t divu_shadow_r(offs_t offset);
	void divu_shadow_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);

	uint32_t dvcr_r();
	void dvcr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void divu_start(int64_t dividend);

	// UBC
	uint16_t ubc_r(offs_t offset, uint16_t mem_mask = ~0);
	void ubc_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t ubc_b_r(offs_t offset, uint16_t mem_mask) { return ubc_r(offset + 16, mem_mask); }
	void ubc_b_w(offs_t offset, uint16_t data, uint16_t mem_mask) { ubc_w(offset + 16, data, mem_mask); }
	void ubc_commit();
	bool ubc_compare(uint32_t address, uint32_t data, unsigned size, bool write, bool fetch, bool peripheral, bool external = false, bool after = false);
	void ubc_accept();
	virtual bool instruction_before(uint32_t pc, uint16_t opcode) override;
	virtual void instruction_after(uint32_t pc, uint16_t opcode) override;
	virtual void execute_monitored() override;
	virtual bool instruction_access_valid(uint32_t address, unsigned size) override;
	virtual void execute_run() override;
	virtual uint8_t read_byte(offs_t offset) override;
	virtual uint16_t read_word(offs_t offset) override;
	virtual uint32_t read_long(offs_t offset) override;
	virtual void write_byte(offs_t offset, uint8_t data) override;
	virtual void write_word(offs_t offset, uint16_t data) override;
	virtual void write_long(offs_t offset, uint32_t data) override;

	// DMAC
	template <int Channel> uint32_t vcrdma_r();
	template <int Channel> void vcrdma_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	template <int Channel> uint8_t drcr_r();
	template <int Channel> void drcr_w(uint8_t data);
	template <int Channel> uint32_t sar_r();
	template <int Channel> void sar_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	template <int Channel> uint32_t dar_r();
	template <int Channel> void dar_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	template <int Channel> uint32_t dmac_tcr_r();
	template <int Channel> void dmac_tcr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	template <int Channel> uint32_t chcr_r();
	template <int Channel> void chcr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t dmaor_r();
	void dmaor_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);

	// WTC
	uint16_t wtcnt_r(offs_t offset, uint16_t mem_mask = ~0);
	void wtcnt_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t rstcsr_r(offs_t offset, uint16_t mem_mask = ~0);
	void rstcsr_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

	// misc
	uint16_t fmr_sbycr_r();
	void fmr_sbycr_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint8_t ccr_r();
	void ccr_w(uint8_t data);

	// BSC
	uint32_t bcr1_r();
	void bcr1_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t bcr2_r();
	void bcr2_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t wcr_r();
	void wcr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t mcr_r();
	void mcr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	void refresh_resync();
	void refresh_activate();
	TIMER_CALLBACK_MEMBER(refresh_tick);
	uint32_t rtcsr_r();
	void rtcsr_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t rtcor_r();
	void rtcor_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	uint32_t rtcnt_r();
	void rtcnt_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);

	virtual void set_frt_input(int state) override;

	// SCI
	uint8_t m_smr, m_brr, m_scr, m_tdr, m_ssr;
	uint8_t m_rdr = 0, m_tsr = 0, m_ssr_read = 0;
	bool m_sci_busy = false;
	int m_sci_dma_access = -1; // transient transfer origin; never set for CPU/debugger access
	emu_timer *m_sci_timer = nullptr;
	devcb_write8 m_sci_tx;
	devcb_write_line m_sci_txd, m_sci_sck;
	uint32_t m_tx_frame = 0;
	uint8_t m_tx_bit = 0, m_tx_bits = 0, m_tx_stop = 0, m_tx_format = 0, m_tx_data = 0, m_tx_mpbt = 0, m_tx_ext_count = 0;
	bool m_tx_prefetched = false, m_rx_busy = false;
	uint8_t m_rsr = 0, m_rx_stage = 0, m_rx_format = 0, m_rx_parity = 0, m_rx_errors = 0, m_rx_mp = 0, m_rx_ext_count = 0;
	int m_sci_rxd = 1, m_sci_sck_in = 1, m_sci_txd_level = 1, m_sci_sck_level = 1, m_sci_pin_value = 0;
	emu_timer *m_sci_rx_timer = nullptr, *m_sci_clock_timer = nullptr;
	unsigned sci_bit_clocks() const;
	void sci_drive_txd(int state);
	void sci_drive_sck(int state);
	void sci_reclock();
	void sci_load_tsr();
	void sci_tx_step();
	void sci_transmit_complete();
	void sci_rx_start();
	void sci_sample_rx();
	void sci_receive_byte(uint8_t data, uint8_t errors = 0, bool mpb = false);
	void sci_sync_edge(bool rising);
	TIMER_CALLBACK_MEMBER(sci_rx_tick);
	TIMER_CALLBACK_MEMBER(sci_clock_tick);
	void sci_reset();
	void sci_update();
	void sci_start();
	bool sci_dma_requested(int channel) const;
	TIMER_CALLBACK_MEMBER(sci_tx_complete);

	// FRT / FRC
	devcb_write_line m_ftoa, m_ftob;
	int m_frt_clock_input = 0, m_frt_output[2]{};
	uint64_t m_frt_epoch = 0;
	uint32_t m_frt_clockrate = 0, m_frt_generation = 0;
	uint64_t frt_cycles() const;
	void frt_drive(unsigned channel, int level);
	void frt_advance(uint64_t ticks, bool internal = false, int write_kind = 0);
	void frt_capture();
	TIMER_CALLBACK_MEMBER(frt_capture_callback);
	emu_timer *m_frt_capture_timer = nullptr;
	bool m_frt_capture_pending = false;
	attotime m_frt_capture_clock_delay = attotime::never;
	uint64_t m_frt_icr_read_cycle = ~uint64_t(0), m_frt_clear_cycle = ~uint64_t(0);
	uint8_t m_tier, m_ftcsr, m_ftcsr_read_flags, m_frc_tcr, m_tocr;
	uint16_t m_frc;
	uint8_t m_frt_temp = 0; // shared byte-access latch (Hardware Manual 11.3)
	uint16_t m_ocra, m_ocrb, m_frc_icr;

	// INTC
	struct
	{
		uint8_t frc;
		uint8_t sci;
		uint8_t divu;
		uint8_t dmac;
		uint8_t wdt;
	} m_irq_level;

	struct
	{
		uint8_t fic;
		uint8_t foc;
		uint8_t fov;
		uint8_t divu;
		uint8_t dmac[2];
	} m_irq_vector;

	uint16_t m_ipra, m_iprb;
	uint16_t m_vcra, m_vcrb, m_vcrc, m_vcrd, m_vcrwdt, m_vcrdiv, m_intc_icr, m_vcrdma[2];
	bool m_vecmd, m_nmie;

	// DIVU
	bool m_divu_ovf, m_divu_ovfie;
	bool m_divu_busy = false;       // an operation is running
	bool m_divu_ovf_pending = false; // it overflows: the flag is set when it ends
	attotime m_divu_done;           // when the operation ends
	emu_timer *m_divu_timer;
	void divu_wait();
	void divu_run(unsigned cycles);
	void divu_finish();
	TIMER_CALLBACK_MEMBER(divu_timer_cb);
	uint32_t m_dvsr, m_dvdntl, m_dvdnth;
	uint32_t m_divu_shadow[2]{}; // writable result copies; updated by division, not dividend storage writes

	// WTC
	uint8_t m_wtcnt, m_wtcsr;
	uint8_t m_rstcsr;
	uint16_t m_wtcw[2];
	bool m_wtcsr_ovf_read = false;   // OVF has been read as 1: a following write of 0 clears it
	bool m_rstcsr_wovf_read = false; // the same for WOVF
	bool m_wdt_reset = false;        // the reset in progress comes from the WDT: RSTCSR survives it

	// UBC
	uint16_t m_ubc[32]{}, m_ubc_live[32]{}, m_ubc_fetch[32]{};
	uint32_t m_ubc_previous_pc = 0xffffffff;
	attotime m_ubc_ready;
	bool m_ubc_dirty = false, m_ubc_pending = false, m_ubc_sequence = false;
	bool m_ubc_inhibit = false, m_ubc_fetch_sequence = false;

	// DMAC
	struct
	{
		uint8_t drcr;
		uint32_t sar;
		uint32_t dar;
		uint32_t tcr;
		uint32_t chcr;
	} m_dmac[2];
	devcb_write_line m_dma_dack[2];
	devcb_read32 m_dma_read[2];
	devcb_write32 m_dma_write[2];
	int m_dma_dreq[2]{1, 1}, m_dma_dack_level[2]{1, 1};
	bool m_dma_dreq_driven[2]{}, m_dma_edge[2]{}, m_dma_edge_burst[2]{}, m_dma_ack_high[2]{};
	unsigned m_dma_requests[2]{}, m_dma_ack_count[2]{};
	uint32_t m_dma_io_data[2]{0xffffffff, 0xffffffff};
	attotime m_dma_ready[2]{}, m_dma_detect_after[2]{}, m_dma_ack_start[2][16]{}, m_dma_ack_end[2][16]{};
	emu_timer *m_dma_dack_timer[2]{};
	int m_dma_owner = -1;
	unsigned m_dma_priority = 0, m_dma_step = 0, m_dma_step_count = 0, m_dma_count_delta = 0;
	int m_dma_src_delta = 0, m_dma_dst_delta = 0;
	uint32_t m_dma_unit_control = 0, m_dma_unit_src = 0, m_dma_unit_dst = 0, m_dma_data[4]{};
	bool m_dma_committed = false, m_dma_cancelled = false, m_dma_staged = false;
	attotime m_dma_bus_end = attotime::zero, m_dma_pause_time = attotime::zero;
	struct dma_step
	{
		uint32_t address = 0;
		unsigned bytes = 0, word = 0, shift = 0;
		bool write = false;
		attotime start = attotime::zero, end = attotime::zero;
	} m_dma_steps[32];
	void dma_dack_drive(unsigned channel, int level);
	int dma_dack_level(unsigned channel) const;
	void dma_run_step(unsigned channel, unsigned index);
	void dma_commit_unit(unsigned channel);
	void dma_update_halt();
	TIMER_CALLBACK_MEMBER(dma_dack_tick);
	uint8_t m_dmaor;
	bool m_dma_te_read[2]{};
	uint8_t m_dmaor_read_flags = 0;

	// misc
	uint8_t m_sbycr; // CCR lives in m_cache
	devcb_write_line m_standby_hiz, m_ckpack;
	bool m_clock_pause = false;
	bool m_standby = false;
	bool m_standby_waking = false;
	int m_nmi_pin = CLEAR_LINE;
	attotime m_standby_entry;
	emu_timer *m_standby_timer = nullptr;
	TIMER_CALLBACK_MEMBER(standby_wake);

	// BSC
	uint32_t m_bcr1, m_bcr2, m_wcr, m_mcr, m_rtcsr, m_rtcor, m_rtcnt;
	bool m_rtcsr_cmf_read = false;
	emu_timer *m_refresh_timer = nullptr;
	attotime m_refresh_epoch = attotime::zero;
	uint32_t m_refresh_clockrate = 0;
	unsigned m_refresh_phase = 0;

	uint64_t m_frc_base;

	int m_frt_input;

	emu_timer *m_timer;
	emu_timer *m_wdtimer;
	emu_timer *m_dma_current_active_timer[2];
	int m_dma_timer_active[2];

	int m_active_dma_incs[2];
	int m_active_dma_incd[2];
	int m_active_dma_size[2];
	int m_active_dma_steal[2];
	uint32_t m_active_dma_src[2];
	uint32_t m_active_dma_dst[2];
	uint32_t m_active_dma_count[2];

	int m_is_slave;

	dma_kludge_delegate              m_dma_kludge_cb;
	dma_fifo_data_available_delegate m_dma_fifo_data_available_cb;
	ftcsr_read_delegate              m_ftcsr_read_cb;

	TIMER_CALLBACK_MEMBER(sh2_timer_callback);
	TIMER_CALLBACK_MEMBER(sh2_wdtimer_callback);
	TIMER_CALLBACK_MEMBER(sh2_dma_current_active_callback);
	void sh2_timer_resync(int write_kind = 0);
	void sh2_timer_activate();
	void sh2_wtcnt_recalc();
	void sh2_wdt_activate();
	void sh2_do_dma(int dmach);
	void sh2_dmac_check(int dma);
	void sh2_recalc_irq();
	void standby_init();
	void power_postload();
	void frt_reset();
	void module_standby(uint8_t old);
	attotime m_module_div_remaining;
	attotime m_module_dma_remaining[2];
};

DECLARE_DEVICE_TYPE(SH7604, sh7604_device)

#endif // MAME_CPU_SH_SH7604_H

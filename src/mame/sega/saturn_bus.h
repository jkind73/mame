// license:BSD-3-Clause
// copyright-holders:Agent A (Saturn bus arbiter, based on MAME core)
// Saturn/ST-V coherent bus arbiter — BUS-01/02/03
// Implements A/B/C bus ownership, wait-state penalties, and device readiness
// vs committed access. Uses devices/delegates, no host sleeps.

#ifndef MAME_SEGA_SATURN_BUS_H
#define MAME_SEGA_SATURN_BUS_H

#pragma once

#include "saturn_scu.h" // for bus flag constants

enum saturn_bus_master : uint8_t {
    SATURN_MASTER_NONE = 0xff,
    SATURN_MASTER_MAIN_SH2 = 0,
    SATURN_MASTER_SLAVE_SH2,
    SATURN_MASTER_SCU_DMA0,
    SATURN_MASTER_SCU_DMA1,
    SATURN_MASTER_SCU_DMA2,
    SATURN_MASTER_SCU_DSP,
    SATURN_MASTER_SOUND_68K,
    SATURN_MASTER_VDP1,
    SATURN_MASTER_VDP2,
    SATURN_MASTER_CD_BLOCK,
    SATURN_MASTER_COUNT
};

enum saturn_bus_type : uint8_t {
    SATURN_BUS_A = 0,
    SATURN_BUS_B,
    SATURN_BUS_C,
    SATURN_BUS_SCU_REG,
    SATURN_BUS_DSP,
    SATURN_BUS_COUNT
};

struct saturn_bus_transaction {
    uint32_t address;       // 27-bit masked physical
    uint8_t  size;          // 1,2,4
    bool     is_write;
    bool     is_fetch;
    bool     is_burst;
    saturn_bus_master master;
    saturn_bus_type   bus;
    uint16_t flags;         // from SCU get_address_flags
    int      penalty;       // AnNW+3 etc
    bool     committed;
};

// Readiness callback: true if device can accept transaction now
// Use std::function to avoid device_delegate default-ctor issues
using saturn_bus_ready_cb = std::function<bool (const saturn_bus_transaction &)>;

class saturn_bus_device : public device_t
{
public:
    saturn_bus_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

    // Arbiter core
    bool request_bus(saturn_bus_type bus, saturn_bus_master master, bool burst = false);
    void release_bus(saturn_bus_type bus, saturn_bus_master master);
    void release_all(saturn_bus_master master);
    bool is_bus_owned(saturn_bus_type bus, saturn_bus_master *owner = nullptr) const;
    saturn_bus_master bus_owner(saturn_bus_type bus) const { return (saturn_bus_master)m_owner[bus]; }

    // Penalty / readiness for CPU before_delay
    // Returns wait cycles to stall CPU. 0 = immediate grant.
    // If bus owned by other master, returns stall cycles that will cause retry.
    uint32_t get_cpu_wait(offs_t offset, bool is_write, saturn_bus_master cpu_master);

    // Device readiness registration (optional, not used in initial BUS-01)
    void set_ready_cb(saturn_bus_type bus, saturn_bus_ready_cb cb) { m_ready_cb[bus] = std::move(cb); }

    // SCU integration: called by SCU DMA to acquire both source and dest buses
    bool acquire_dma_buses(uint8_t level, uint16_t src_flags, uint16_t dst_flags, int src_penalty, int dst_penalty);
    void release_dma_buses(uint8_t level);

    // For save/load
    void set_host_space(address_space *space) { m_hostspace = space; }

    // Configuration helpers for before_delay binding
    template <typename T> void set_asr(T &&asr0_tag, T &&asr1_tag) { /* not needed, SCU provides */ }

    // For debugging/logging
    uint32_t bus_status_r() const;

protected:
    void device_start() override;
    void device_reset() override;

private:
    uint8_t           m_owner[SATURN_BUS_COUNT]; // saturn_bus_master
    bool              m_burst[SATURN_BUS_COUNT];
    int               m_penalty[SATURN_BUS_COUNT];
    saturn_bus_ready_cb m_ready_cb[SATURN_BUS_COUNT];

    // DMA level -> owned buses tracking
    struct dma_bus_own {
        bool active = false;
        uint8_t src_bus = SATURN_BUS_COUNT;
        uint8_t dst_bus = SATURN_BUS_COUNT;
        bool src_owned = false;
        bool dst_owned = false;
    } m_dma_own[3];

    address_space *m_hostspace;

    saturn_bus_type flags_to_bus(uint16_t flags) const;
    uint16_t address_to_flags(uint32_t address) const;
    int flags_to_penalty(uint16_t flags, bool is_write) const;

    // ASR shadow for A-Bus wait calculation (copied from SCU via delegate or direct)
    uint32_t m_asr[2];
    uint32_t m_aref;

public:
    // Called by SCU when ASR/AREF changes
    void set_asr_regs(uint32_t asr0, uint32_t asr1, uint32_t aref) { m_asr[0]=asr0; m_asr[1]=asr1; m_aref=aref; }
};

DECLARE_DEVICE_TYPE(SATURN_BUS, saturn_bus_device)

#endif // MAME_SEGA_SATURN_BUS_H

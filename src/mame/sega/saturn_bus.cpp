// license:BSD-3-Clause
// copyright-holders:Agent A
// Saturn/ST-V bus arbiter implementation — BUS-01/02/03
// Provides coherent A/B/C ownership and wait-state handling.

#include "emu.h"
#include "saturn_bus.h"

#define LOG_BUS (1U << 1)
#define VERBOSE (0)
#include "logmacro.h"

DEFINE_DEVICE_TYPE(SATURN_BUS, saturn_bus_device, "saturn_bus", "Saturn Bus Arbiter")

saturn_bus_device::saturn_bus_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
    : device_t(mconfig, SATURN_BUS, tag, owner, clock)
    , m_hostspace(nullptr)
{
    for (int i=0;i<SATURN_BUS_COUNT;i++) {
        m_owner[i]=SATURN_MASTER_NONE;
        m_burst[i]=false;
        m_penalty[i]=0;
    }
    for (int i=0;i<3;i++) {
        m_dma_own[i].active=false;
        m_dma_own[i].src_bus=SATURN_BUS_COUNT;
        m_dma_own[i].dst_bus=SATURN_BUS_COUNT;
        m_dma_own[i].src_owned=false;
        m_dma_own[i].dst_owned=false;
    }
    m_asr[0]=0; m_asr[1]=0; m_aref=0x10;
}

void saturn_bus_device::device_start()
{
    save_item(NAME(m_owner));
    save_item(NAME(m_burst));
    save_item(NAME(m_penalty));
    save_item(NAME(m_asr));
    save_item(NAME(m_aref));
    save_item(NAME(m_dma_own[0].active));
    save_item(NAME(m_dma_own[0].src_bus));
    save_item(NAME(m_dma_own[0].dst_bus));
    save_item(NAME(m_dma_own[0].src_owned));
    save_item(NAME(m_dma_own[0].dst_owned));
    save_item(NAME(m_dma_own[1].active));
    save_item(NAME(m_dma_own[1].src_bus));
    save_item(NAME(m_dma_own[1].dst_bus));
    save_item(NAME(m_dma_own[1].src_owned));
    save_item(NAME(m_dma_own[1].dst_owned));
    save_item(NAME(m_dma_own[2].active));
    save_item(NAME(m_dma_own[2].src_bus));
    save_item(NAME(m_dma_own[2].dst_bus));
    save_item(NAME(m_dma_own[2].src_owned));
    save_item(NAME(m_dma_own[2].dst_owned));

    // ready_cb are std::function, not saved
}

void saturn_bus_device::device_reset()
{
    for (int i=0;i<SATURN_BUS_COUNT;i++) {
        m_owner[i]=SATURN_MASTER_NONE;
        m_burst[i]=false;
        m_penalty[i]=0;
    }
    for (int i=0;i<3;i++) {
        m_dma_own[i].active=false;
        m_dma_own[i].src_bus=SATURN_BUS_COUNT;
        m_dma_own[i].dst_bus=SATURN_BUS_COUNT;
        m_dma_own[i].src_owned=false;
        m_dma_own[i].dst_owned=false;
    }
}

saturn_bus_type saturn_bus_device::flags_to_bus(uint16_t flags) const
{
    // flags from saturn_scu_device::get_address_flags
    // A_BUS =0x0100, B_BUS=0x0200, C_BUS=0x0300
    uint16_t bus = flags & 0x0300;
    switch(bus) {
        case 0x0100: return SATURN_BUS_A;
        case 0x0200: return SATURN_BUS_B;
        case 0x0300: return SATURN_BUS_C;
        default: break;
    }
    // SCU reg space is B_BUS_SCU =0x0204, treat as B but with special illegal
    if (flags == saturn_scu_device::B_BUS_SCU)
        return SATURN_BUS_SCU_REG;
    // A_BUS_DUMMY also A
    if ((flags & 0x0100)==0x0100) return SATURN_BUS_A;
    return SATURN_BUS_COUNT;
}

uint16_t saturn_bus_device::address_to_flags(uint32_t address) const
{
    // Simplified decode mirroring saturn_scu_device::get_address_flags without penalty
    // Uses same logic as SCU but without host dependency
    uint32_t a = address & 0x07FFFFFF;
    // Work RAM H mirror
    if ((a & 0x07000000) == 0x06000000 || (a & 0x07000000) == 0x07000000)
        return saturn_scu_device::C_BUS;
    switch (a & 0x07000000) {
        case 0x02000000:
        case 0x03000000:
            return saturn_scu_device::A_BUS_CS0;
        case 0x04000000:
            return saturn_scu_device::A_BUS_CS1;
        case 0x05000000: {
            switch (a & 0x00F00000) {
                case 0x00800000: return saturn_scu_device::A_BUS_CS2;
                case 0x00A00000:
                case 0x00B00000: return saturn_scu_device::B_BUS_SCSP;
                case 0x00C00000:
                case 0x00D00000: return saturn_scu_device::B_BUS_VDP1;
                case 0x00E00000: return saturn_scu_device::B_BUS_VDP2;
                case 0x00F00000:
                    if ((a & 0x000F0000) < 0x000E0000)
                        return saturn_scu_device::B_BUS_VDP2;
                    else
                        return saturn_scu_device::B_BUS_SCU;
                default:
                    if ((a & 0x00800000)==0)
                        return saturn_scu_device::A_BUS_DUMMY;
                    break;
            }
            break;
        }
    }
    return 0;
}

int saturn_bus_device::flags_to_penalty(uint16_t flags, bool is_write) const
{
    // A-Bus penalties from ASR
    int a0nw = (m_asr[0] >> 20) & 0x0f;
    int a1nw = (m_asr[0] >> 4) & 0x0f;
    int a3nw = (m_asr[1] >> 4) & 0x0f;
    switch(flags) {
        case saturn_scu_device::A_BUS_CS0: return a0nw + 3;
        case saturn_scu_device::A_BUS_CS1: return a1nw + 3;
        case saturn_scu_device::A_BUS_CS2: return a3nw + 3;
        case saturn_scu_device::A_BUS_DUMMY: return 3;
        case saturn_scu_device::B_BUS_VDP1: return is_write ? 14 : 9;
        case saturn_scu_device::B_BUS_VDP2: return is_write ? 20 : 3;
        case saturn_scu_device::B_BUS_SCSP: return is_write ? 24 : 13;
        case saturn_scu_device::B_BUS_SCU:  return is_write ? 8 : 4;
        case saturn_scu_device::B_BUS: return is_write ? 8 : 4;
        case saturn_scu_device::C_BUS: return 0;
        default: break;
    }
    // Generic fallback based on bus
    uint16_t bus = flags & 0x0300;
    if (bus == 0x0200) return is_write ? 8 : 4;
    return 0;
}

bool saturn_bus_device::request_bus(saturn_bus_type bus, saturn_bus_master master, bool burst)
{
    if (bus >= SATURN_BUS_COUNT) return false;
    if (m_owner[bus]==SATURN_MASTER_NONE || m_owner[bus]==(uint8_t)master) {
        m_owner[bus]=(uint8_t)master;
        m_burst[bus]=burst;
        return true;
    }
    // Bus owned by other master
    LOGMASKED(LOG_BUS, "Bus %d owned by %d, request by %d denied\n", bus, m_owner[bus], master);
    return false;
}

void saturn_bus_device::release_bus(saturn_bus_type bus, saturn_bus_master master)
{
    if (bus >= SATURN_BUS_COUNT) return;
    if (m_owner[bus]==(uint8_t)master) {
        m_owner[bus]=SATURN_MASTER_NONE;
        m_burst[bus]=false;
        m_penalty[bus]=0;
    }
}

void saturn_bus_device::release_all(saturn_bus_master master)
{
    for (int i=0;i<SATURN_BUS_COUNT;i++) {
        if (m_owner[i]==(uint8_t)master)
            release_bus((saturn_bus_type)i, master);
    }
}

bool saturn_bus_device::is_bus_owned(saturn_bus_type bus, saturn_bus_master *owner) const
{
    if (bus >= SATURN_BUS_COUNT) return false;
    if (owner) *owner = (saturn_bus_master)m_owner[bus];
    return m_owner[bus]!=SATURN_MASTER_NONE;
}

bool saturn_bus_device::acquire_dma_buses(uint8_t level, uint16_t src_flags, uint16_t dst_flags, int src_penalty, int dst_penalty)
{
    if (level>=3) return false;
    saturn_bus_type src_bus = flags_to_bus(src_flags);
    saturn_bus_type dst_bus = flags_to_bus(dst_flags);
    if (src_bus>=SATURN_BUS_COUNT || dst_bus>=SATURN_BUS_COUNT) return false;

    // Check if buses are free or already owned by same DMA level (allow re-acquire)
    saturn_bus_master dma_master = (saturn_bus_master)(SATURN_MASTER_SCU_DMA0 + level);
    bool src_free = (m_owner[src_bus]==SATURN_MASTER_NONE || m_owner[src_bus]==(uint8_t)dma_master);
    bool dst_free = (m_owner[dst_bus]==SATURN_MASTER_NONE || m_owner[dst_bus]==(uint8_t)dma_master);

    // Same-bus illegal already handled in SCU, but we still check ownership
    if (!src_free || !dst_free) {
        LOGMASKED(LOG_BUS, "DMA%d cannot acquire buses src=%d (%d) dst=%d (%d)\n", level, src_bus, m_owner[src_bus], dst_bus, m_owner[dst_bus]);
        return false;
    }

    // Acquire
    m_owner[src_bus]=(uint8_t)dma_master;
    m_owner[dst_bus]=(uint8_t)dma_master;
    m_penalty[src_bus]=src_penalty;
    m_penalty[dst_bus]=dst_penalty;
    // Direct is burst, indirect is cycle-steal (not burst)
    // Caller tells us burst via is_burst flag, but we store per bus as true for direct
    // For simplicity, mark burst true for direct mode
    m_dma_own[level].active=true;
    m_dma_own[level].src_bus=(uint8_t)src_bus;
    m_dma_own[level].dst_bus=(uint8_t)dst_bus;
    m_dma_own[level].src_owned=true;
    m_dma_own[level].dst_owned=(src_bus!=dst_bus);

    LOGMASKED(LOG_BUS, "DMA%d acquired src bus %d dst bus %d\n", level, src_bus, dst_bus);
    return true;
}

void saturn_bus_device::release_dma_buses(uint8_t level)
{
    if (level>=3) return;
    if (!m_dma_own[level].active) return;
    saturn_bus_master dma_master = (saturn_bus_master)(SATURN_MASTER_SCU_DMA0 + level);
    if (m_dma_own[level].src_owned)
        release_bus((saturn_bus_type)m_dma_own[level].src_bus, dma_master);
    if (m_dma_own[level].dst_owned)
        release_bus((saturn_bus_type)m_dma_own[level].dst_bus, dma_master);
    m_dma_own[level].active=false;
    m_dma_own[level].src_bus=SATURN_BUS_COUNT;
    m_dma_own[level].dst_bus=SATURN_BUS_COUNT;
    m_dma_own[level].src_owned=false;
    m_dma_own[level].dst_owned=false;
    LOGMASKED(LOG_BUS, "DMA%d released buses\n", level);
}

uint32_t saturn_bus_device::get_cpu_wait(offs_t offset, bool is_write, saturn_bus_master cpu_master)
{
    uint32_t addr = offset & 0x07FFFFFF;
    uint16_t flags = address_to_flags(addr);
    saturn_bus_type bus = flags_to_bus(flags);
    if (bus>=SATURN_BUS_COUNT) return 0;

    // If bus owned by other master, stall – CPU-04 deferred via before_delay
    // With SH2 snapshot restore (sh2.cpp execute_run saving r/ea/pr/sr/gbr/vbr/mach/macl/pc),
    // pre-decrement/post-increment side-effects (MOV.L Rm,@-Rn stack push) are rewound,
    // so C-BUS can also force retry without double R15 (choroqpk fix now in CPU core).
    if (m_owner[bus]!=SATURN_MASTER_NONE && m_owner[bus]!=(uint8_t)cpu_master) {
        // For burst DMA (direct), CPU is already halted via main_dtack_cb, this path is mainly for indirect cycle-steal
        // All buses including C-BUS force retry to prevent access while DMA owns bus (faithful)
        int base = m_penalty[bus] + 4;
        if (m_burst[bus]) base += 8;
        base += flags_to_penalty(flags, is_write);
        if (base < 1024) base = 1024;
        if (base > 10000) base = 10000;
        LOGMASKED(LOG_BUS, "CPU %d wait %d on bus %d owned by %d addr %08x flags %04x (FORCE RETRY)\n", cpu_master, base, bus, m_owner[bus], addr, flags);
        return base;
    }

    // Check device readiness (VDP1/VDP2)
    if (m_ready_cb[bus]) {
        saturn_bus_transaction trans;
        trans.address = addr;
        trans.size = is_write ? 4 : 4;
        trans.is_write = is_write;
        trans.is_fetch = false;
        trans.is_burst = false;
        trans.master = cpu_master;
        trans.bus = bus;
        trans.flags = flags;
        trans.penalty = flags_to_penalty(flags, is_write);
        trans.committed = false;
        bool ready = m_ready_cb[bus](trans);
        if (!ready) {
            // Device not ready (VDP1 drawing, VDP2 slot) – force retry, no double side effect for VRAM/FB (no R15)
            int base = trans.penalty + 1024;
            if (base < 1024) base = 1024;
            if (base > 10000) base = 10000;
            LOGMASKED(LOG_BUS, "CPU %d device not ready on bus %d addr %08x (FORCE RETRY %d)\n", cpu_master, bus, addr, base);
            return base;
        }
    }

    // No ownership stall, no readiness stall – just wait-state penalty as steal
    int penalty = flags_to_penalty(flags, is_write);
    if (penalty>0) {
        return penalty;
    }
    return 0;
}

uint32_t saturn_bus_device::bus_status_r() const
{
    uint32_t status = 0;
    for (int i=0;i<SATURN_BUS_COUNT;i++) {
        if (m_owner[i]!=SATURN_MASTER_NONE)
            status |= (1 << i) | ((uint32_t)m_owner[i] << (8 + i*4));
    }
    return status;
}

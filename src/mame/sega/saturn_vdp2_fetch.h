// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
/*
  VDP2 normal-screen (NBG0-3) VRAM fetch pipeline.

  Real VDP2 hardware does not decide per pixel whether a VRAM read is
  allowed. In each 8-dot character period (one cycle of access slots T0-T7)
  it issues the pattern-name (PN) and character-pattern (CP) reads scheduled
  by the cycle pattern registers into per-layer latches and an 8-position dot
  buffer; screen dots come from whatever the buffer holds. A CP read that
  does not happen leaves its buffer positions holding the previous
  character's dots, and a CP read outside its valid window uses the previous
  or next cell's pattern name.

  This model follows the MiSTer Saturn core's RTL (rtl/Saturn/VDP2/VDP2.sv
  and VDP2_pkg.sv, commit c02cd26885c2d0cc330e1d9e60861b0b92a31574); the
  line references below are to that revision. saturn_master_plan.md section
  S records the derivation and the cross-checks against ST-058 Table 3.4,
  Mednafen 1.32.1 and Ymir.

  Scope: normal (8 slots per cycle) and high resolution (4 slots per
  cycle, two dots per slot: HRES[1]), tile and bitmap mode, any horizontal
  scale including the NBG0/1 reduction modes, and NBG0/1 vertical cell
  scroll table reads. The exclusive-monitor modes (HRES[2]) are not
  modelled.
*/

#ifndef MAME_SEGA_SATURN_VDP2_FETCH_H
#define MAME_SEGA_SATURN_VDP2_FETCH_H

#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace saturn_vdp2_fetch {

// ST-058 Table 3.5 access command codes
constexpr uint8_t CMD_PN0 = 0x0; // NBG0-3 pattern name read: 0x0-0x3
constexpr uint8_t CMD_CP0 = 0x4; // NBG0-3 character pattern read: 0x4-0x7
constexpr uint8_t CMD_VCS0 = 0xc; // NBG0/1 vertical cell scroll table read: 0xc-0xd
constexpr uint8_t CMD_NONE = 0xf;

constexpr unsigned SLOTS = 8;       // access slots per cycle, normal resolution
constexpr unsigned HIRES_SLOTS = 4; // high resolution: T0-T3 (CELLX & 3, VDP2.sv 667)

struct pattern_name {
  uint32_t character = 0; // in 32-byte units
  uint16_t palette = 0;
  bool hflip = false;
  bool vflip = false;
  bool priority = false;
  bool colour_calc = false;

  bool operator==(const pattern_name &o) const {
    return character == o.character && palette == o.palette && hflip == o.hflip &&
        vflip == o.vflip && priority == o.priority && colour_calc == o.colour_calc;
  }
};

// Access commands per bank (A0, A1, B0, B1) and slot, after resolving VRAM
// partitioning. `command` omits banks that hold rotation-screen data, which
// do not serve normal-screen reads (VDP2.sv 691-723); `raw` keeps them,
// because the "layer has a PN slot" test uses the ungated values (817-820).
struct schedule {
  std::array<std::array<uint8_t, SLOTS>, 4> command;
  std::array<std::array<uint8_t, SLOTS>, 4> raw;
  schedule() {
    for (auto &bank : command)
      bank.fill(CMD_NONE);
    for (auto &bank : raw)
      bank.fill(CMD_NONE);
  }
};

// cycle[] holds CYCA0L, CYCA0U, CYCA1L, CYCA1U, CYCB0L, CYCB0U, CYCB1L, CYCB1U.
// An unpartitioned VRAM's second bank runs the first bank's pattern (MiSTer
// VDP2.sv 674-688: VCPA1 = VRAMD ? CYCA1 : CYCA0).
inline schedule make_schedule(const uint16_t cycle[8], bool partition_a, bool partition_b,
                              const std::array<bool, 4> &rotation_owned) {
  schedule s;
  for (unsigned bank = 0; bank < 4; ++bank) {
    bool const partitioned = bank < 2 ? partition_a : partition_b;
    unsigned const source = partitioned ? bank : (bank & ~1U);
    for (unsigned slot = 0; slot < SLOTS; ++slot) {
      s.raw[bank][slot] = (cycle[source * 2 + slot / 4] >> (12 - (slot % 4) * 4)) & 15;
      if (!rotation_owned[bank])
        s.command[bank][slot] = s.raw[bank][slot];
    }
  }
  return s;
}

// Slots from a PN read until CP addresses use its value. NBG0/1 read the
// latch through PN_PIPE[1] after a DOTCLK_DIV==3 write; NBG2/3 through
// NBGx_PN_PIPE[0] after a DOTCLK_DIV==1 write, one slot sooner; the second
// 256-colour NBG2/3 read uses NBGx_PN_PIPE[1], one slot later again
// (VDP2.sv 2323-2346, 2806-2835, 969-974; VDP2_pkg.sv NxCHAddr2 1844-1848).
inline unsigned pn_latency(unsigned layer, unsigned colour_depth, unsigned cp_count) {
  if (layer < 2)
    return 4;
  return (colour_depth == 1 && (cp_count & 1)) ? 4 : 3;
}

// Number of 32-bit slices per character row: 16/256/2048/32768/16.7M colours.
inline unsigned slices_per_row(unsigned colour_depth) {
  static constexpr unsigned slices[5] = {1, 2, 4, 4, 8};
  return colour_depth < 5 ? slices[colour_depth] : 1;
}

// Byte address of one 32-bit slice of a character row (VDP2_pkg.sv NxCHAddr
// 1790-1832): character base, 2x2 cell select from the flipped X/Y bit 3,
// flipped row, and slice index = CP count XOR horizontal flip.
inline uint32_t cp_address(const pattern_name &pn, unsigned colour_depth, bool cell_2x2,
                           unsigned x, unsigned y, unsigned cp_count) {
  unsigned const slices = slices_per_row(colour_depth);
  unsigned const row_bytes = slices * 4;
  unsigned const x_offs = (x ^ (pn.hflip ? 15 : 0)) & 15;
  unsigned const y_offs = (y ^ (pn.vflip ? 15 : 0)) & 15;
  unsigned const cell = cell_2x2 ? ((y_offs >> 3) << 1) | (x_offs >> 3) : 0;
  unsigned const slice = (cp_count ^ (pn.hflip ? slices - 1 : 0)) & (slices - 1);
  return pn.character * 32 + cell * row_bytes * 8 + (y_offs & 7) * row_bytes + slice * 4;
}

// Horizontal reduction enables for NBG0/1 (ZMCTL N0ZMHF/N0ZMQT, N1ZMHF/N1ZMQT).
struct reduction {
  bool half = false;
  bool quarter = false;
};

// Cells covered by one fetch cycle's pattern-name and character reads: the
// PN counter and CP count select cell X + 8 * (count & mask), mask
// {ZMQT, ZMQT | ZMHF} (VDP2_pkg.sv NxPNAddr 1772-1773, NxCHAddr 1801-1812).
inline unsigned cell_mask(reduction r) { return r.quarter ? 3 : r.half ? 1 : 0; }

// Which cell a character read fetches: 16 colours one read per cell, 256
// colours two reads per cell; other depths never step cells.
inline unsigned cp_cell(unsigned colour_depth, reduction r, unsigned cp_count) {
  if (colour_depth == 0)
    return cp_count & cell_mask(r);
  if (colour_depth == 1)
    return (cp_count >> 1) & cell_mask(r) & 1;
  return 0;
}

// Whether issued character read `cp_count` of a window writes the latch.
// NBG2/NBG3 and unreduced NBG0/NBG1: 16 colours read 0, 256 colours reads
// 0-1, 2048/32768 colours reads 0-3, 16.7M colours every read. Reduced
// NBG0/NBG1 at 16 colours: read 0 and odd reads (ZMHF), or reads 0-3 and 5
// (ZMQT); at 256 colours with ZMHF reads 0-3, two per cell (VDP2.sv
// 2401-2600 and 2601-2800: the NEN gating and NCNT tests).
inline bool cp_writes(unsigned layer, unsigned colour_depth, reduction r, unsigned cp_count) {
  unsigned const k = cp_count & 7;
  switch (colour_depth) {
  case 0:
    if (layer >= 2 || !(r.half || r.quarter))
      return k == 0;
    if (r.quarter)
      return k <= 3 || k == 5;
    return k == 0 || (k & 1);
  case 1:
    return k < ((layer < 2 && r.half) ? 4U : 2U);
  case 2:
  case 3:
    return k < 4;
  case 4:
    return true;
  default:
    return false;
  }
}

struct cycle_dots {
  // Raw dots per cell of the cycle (only cell 0 unless reduced). Reduced
  // cells 1-3 are the other nibble of NBG_CDC[n] and the borrowed NBG2/NBG3
  // buffers (VDP2.sv 2401-2600).
  std::array<std::array<uint32_t, 8>, 4> dot{};
  std::array<pattern_name, 4> attr;  // attributes of the last read that wrote each cell
  uint8_t written = 0;               // cell 0 positions written during this cycle's window
  int pn_cycle = 0;                  // cycle whose PN the first writing read used
  bool any_write = false;
};

// State that survives from one line to the next: the dot buffer is not
// cleared at line start (the clear at VDP2.sv 2373-2378 is commented out)
// and the PN latches (PN_PIPE, one per reduced cell) keep their last values.
struct carry_state {
  cycle_dots buffer;
  std::array<pattern_name, 4> last_pn;
  bool pn_fetched = false; // NBG_PN_FETCH, cleared only at frame end (1461)
  std::array<int32_t, 2> vcs_latch{}; // VS[0..1]: last cell scroll values read (2350-2358)
};

// Output stage: screen dots of fetch cycle g read buffers g and g+1 through
// an accumulator that starts at the cycle's source X modulo 8 and adds the
// horizontal increment per dot (NCX, VDP2.sv 2997-3042). Its integer part
// selects the buffer, the reduced cell and the dot (3062-3135); higher bits
// are dropped, as in the RTL.
struct dot_ref {
  unsigned buffer; // 0: this cycle, 1: the next
  unsigned cell;
  unsigned dot;
};
inline dot_ref select_dot(unsigned layer, unsigned colour_depth, reduction r, uint32_t offset) {
  if (layer < 2 && colour_depth == 0 && r.half)
    return {(offset >> 4) & 1, (offset >> 3) & 1, offset & 7};
  if (layer < 2 && colour_depth == 0 && r.quarter)
    return {(offset >> 5) & 1, (offset >> 3) & 3, offset & 7};
  if (layer < 2 && colour_depth == 1 && r.half)
    return {(offset >> 4) & 1, (offset >> 3) & 1, offset & 7};
  return {(offset >> 3) & 1, 0, offset & 7};
}

// Vertical cell scroll: NBG0/NBG1 read their table entries on command 0xc /
// 0xd slots from eight slots before the PN reads (NVCS_FETCH, VDP2.sv
// 532-536): one cycle in normal resolution, two in high resolution. Both
// layers share one entry counter that starts at the table base each line
// and steps on every issued read (VS_OFFS, 983, 1310, 1354-1433); a read
// issues only if its entry lies in the slot's bank. The value is latched at
// the read's BG_PIPE[2] edge, two slots later, and moves into NVCSY at each
// CELLX == 7 edge (1683-1684) - every eight slots in both resolutions - where
// it is added to the Y of the following PN and CP addresses (919-920). So in
// normal resolution reads at T0-T4 apply to the next cycle and T5-T7 one
// cycle later; in high resolution NVCSY changes every second cycle.
constexpr int VCS_LATCH_SLOTS = 2;
constexpr int VCS_SAMPLE_SLOTS = 8;

// VcsAccess must provide:
//   uint32_t vcs_address(unsigned index) - byte address of table entry `index`
//   int32_t read_vcs(uint32_t address) - the entry as a 16.16 Y offset
//   unsigned bank(uint32_t address)
// offsets[layer][c] receives NVCSY during fetch cycle c, 0 <= c < cycles.
template <typename VcsAccess, size_t N>
void vertical_cell_scroll_line(const schedule &s, const std::array<bool, 2> &enabled, int cycles,
                               VcsAccess &access, std::array<int32_t, 2> &latch,
                               std::array<std::array<int32_t, N>, 2> &offsets, unsigned slots = SLOTS) {
  struct landing {
    int slot;
    unsigned layer;
    int32_t value;
  };
  std::array<landing, 2 * SLOTS + 2> pending;
  unsigned pending_count = 0;
  unsigned index = 0;
  std::array<int32_t, 2> nvcsy = latch;
  int const end = cycles * int(slots);
  for (int slot = -VCS_SAMPLE_SLOTS; slot < end; ++slot) {
    unsigned const t = unsigned(slot + VCS_SAMPLE_SLOTS) % slots;
    uint32_t const address = access.vcs_address(index);
    uint8_t const command = s.command[access.bank(address)][t];
    if ((command == CMD_VCS0 || command == CMD_VCS0 + 1) && enabled[command - CMD_VCS0]) {
      pending[pending_count++] = {slot + VCS_LATCH_SLOTS, unsigned(command - CMD_VCS0), access.read_vcs(address)};
      ++index;
    }
    // CELLX == 7 edge: values latched before it move into NVCSY.
    if ((slot + VCS_SAMPLE_SLOTS) % VCS_SAMPLE_SLOTS == VCS_SAMPLE_SLOTS - 1) {
      unsigned kept = 0;
      for (unsigned i = 0; i < pending_count; ++i) {
        if (pending[i].slot < slot)
          latch[pending[i].layer] = pending[i].value;
        else
          pending[kept++] = pending[i];
      }
      pending_count = kept;
      nvcsy = latch;
    }
    int const next = slot + 1;
    if (next >= 0 && next % int(slots) == 0 && next / int(slots) < cycles)
      for (unsigned layer = 0; layer < 2; ++layer)
        offsets[layer][next / int(slots)] = nvcsy[layer];
  }
  for (unsigned i = 0; i < pending_count; ++i)
    latch[pending[i].layer] = pending[i].value; // lands during the following cycles
}

// Bitmap mode (NBG0/NBG1): no pattern names; attributes come from BMPNA/B.
struct bitmap_config {
  bool enabled = false;
  uint32_t base = 0;  // MPOFN map * 0x20000 bytes
  unsigned size = 0;  // BMSZ: bit 1 1024 dots wide, bit 0 512 lines high
  pattern_name attr;  // BMP palette, BMPR priority, BMCC colour calculation
};

// Byte address of bitmap character read `bm_count` of a cycle whose source X
// is x (VDP2_pkg.sv NxBMAddr 1876-1897): the 8-dot group X[..:3] of row Y,
// plus four bytes per scheduled read. The count carries into the row bits.
inline uint32_t bm_address(const bitmap_config &b, unsigned colour_depth, unsigned x, unsigned y, unsigned bm_count) {
  unsigned const xbits = (b.size & 2) ? 7 : 6;
  unsigned const ybits = (b.size & 1) ? 9 : 8;
  uint32_t const offs = ((y & ((1U << ybits) - 1)) << xbits) | ((x >> 3) & ((1U << xbits) - 1));
  switch (colour_depth) {
  case 0: return b.base + offs * 4 + (bm_count & 3) * 4;
  case 1: return b.base + offs * 8 + (bm_count & 3) * 4;
  case 2:
  case 3: return b.base + offs * 16 + (bm_count & 3) * 4;
  case 4: return b.base + (offs & 0x7fff) * 32 + (bm_count & 7) * 4;
  default: return b.base;
  }
}

// Latches one issued character read: which dot positions it fills depends on
// the colour depth and the read's count (VDP2.sv 2362-2800).
inline void write_dots(cycle_dots &live, unsigned colour_depth, unsigned cell, unsigned cp_count, uint32_t data,
                       const pattern_name &pn, int used_cycle) {
  auto &dots = live.dot[cell];
  switch (colour_depth) {
  case 0: // 4 bits/dot: all eight dots of the cell (2427-2444)
    for (unsigned i = 0; i < 8; ++i)
      dots[i ^ (pn.hflip ? 7 : 0)] = (data >> (28 - i * 4)) & 15;
    if (cell == 0)
      live.written = 0xff;
    break;
  case 1: { // 8 bits/dot: slice k&1 to positions 4(k&1)..+3 (2447-2451)
    unsigned const base = (cp_count & 1) * 4;
    for (unsigned i = 0; i < 4; ++i)
      dots[base + (i ^ (pn.hflip ? 3 : 0))] = (data >> (24 - i * 8)) & 0xff;
    if (cell == 0)
      live.written |= 0x0f << base;
    break;
  }
  case 2:
  case 3: { // 16 bits/dot: read k writes positions 2k, 2k+1 (2454-2458)
    unsigned const base = (cp_count & 3) * 2;
    for (unsigned i = 0; i < 2; ++i)
      dots[base + (i ^ (pn.hflip ? 1 : 0))] = (data >> (16 - i * 16)) & 0xffff;
    live.written |= 3 << base;
    break;
  }
  case 4: // 32 bits/dot: read k writes position k (2460-2461)
    dots[cp_count & 7] = data;
    live.written |= 1 << (cp_count & 7);
    break;
  default:
    return;
  }
  live.attr[cell] = pn;
  if (!live.any_write)
    live.pn_cycle = used_cycle;
  live.any_write = true;
}

// Access must provide:
//   uint32_t pn_address(unsigned x, unsigned y) - byte address of the PN for source X, Y
//   pattern_name read_pn(uint32_t address)
//   uint32_t read32(uint32_t address) - big-endian 32-bit read, 4-byte aligned
//   unsigned bank(uint32_t address) - 0..3 (A0, A1, B0, B1)
//   unsigned cycle_x(int cycle) - source X at the start of the cycle (constant within it, 1671-1681)
//   unsigned cycle_y(int cycle) - source Y of the cycle: line Y plus its cell scroll offset (919-920)
template <typename Access, typename Out>
void fetch_line(const schedule &s, unsigned layer, unsigned colour_depth, bool cell_2x2, reduction r,
                const bitmap_config &bitmap, int cycles, Access &access, carry_state &state, Out &&out,
                unsigned slots = SLOTS) {
  uint8_t const pn_command = CMD_PN0 + layer;
  uint8_t const cp_command = CMD_CP0 + layer;
  if (layer >= 2)
    r = reduction(); // NBG2/NBG3 have no reduction (VDP2_pkg.sv 1320-1326)
  unsigned const mask = cell_mask(r);

  bool has_pn_slot = false; // NxPN_CYC (817-843), from the ungated commands of the mode's slots
  for (auto const &bank : s.raw)
    for (unsigned t = 0; t < slots; ++t)
      has_pn_slot |= bank[t] == pn_command;

  struct pn_read {
    int slot;
    int cycle;
    unsigned cell;
    pattern_name value;
  };
  // A CP read sees the newest PN read of its cell at least `latency` slots
  // old. Each slot issues at most one PN read and a CP read never looks back
  // further than its window plus the latency, so 24 entries suffice.
  constexpr unsigned HISTORY = 24;
  std::array<pn_read, HISTORY> history;
  unsigned history_count = 0;
  std::array<pattern_name, 4> const line_start_pn = state.last_pn; // latches before this line's reads
  auto const visible_pn = [&](int slot, unsigned latency, unsigned cell, int &cycle) {
    pattern_name value = line_start_pn[cell];
    cycle = -1000; // before this line
    for (unsigned i = 0; i < history_count; ++i)
      if (history[i].cell == cell && history[i].slot + int(latency) <= slot) {
        value = history[i].value;
        cycle = history[i].cycle;
      }
    return value;
  };

  cycle_dots &live = state.buffer;
  unsigned cp_count = 0;
  unsigned bm_count = 0; // NBG_BM_CNT: every scheduled bitmap CP slot (1343-1349)
  unsigned pn_count = 0; // NBG_PN_CNT: every scheduled NBG0/1 PN slot (1335-1338)
  // CP reads of cycle w start four slots after its PN reads (527-531): T4 of
  // w through T3 of w+1 in normal resolution, T0-T3 of w+1 in high
  // resolution. Both counters reset at the cycle's last slot (1440-1446).
  int const last_slot = cycles * int(slots) + 4 + int(slots) - 1;
  for (int slot = 0; slot <= last_slot; ++slot) {
    int const cycle = slot / int(slots);
    unsigned const t = unsigned(slot) % slots;
    if (t == 0)
      pn_count = 0; // reset at the last slot (1444)

    // PN reads: the PN for cell X + 8 * (count & mask), issued only on the
    // bank holding it (1144-1148); the counter steps even when not issued.
    if (cycle < cycles && !bitmap.enabled) {
      bool scheduled = false;
      for (auto const &bank : s.command)
        scheduled |= bank[t] == pn_command;
      if (scheduled) {
        unsigned const cell = pn_count & mask;
        uint32_t const address = access.pn_address(access.cycle_x(cycle) + cell * 8, access.cycle_y(cycle));
        if (s.command[access.bank(address)][t] == pn_command) {
          pn_read const read{slot, cycle, cell, access.read_pn(address)};
          if (history_count < history.size()) {
            history[history_count++] = read;
          } else {
            for (unsigned i = 1; i < history.size(); ++i)
              history[i - 1] = history[i];
            history[history.size() - 1] = read;
          }
          state.last_pn[cell] = read.value;
          state.pn_fetched = true;
        }
        if (layer < 2)
          ++pn_count;
      }
    }

    // CP reads: the window of cycle w starts four slots after its first PN
    // slot; addresses use the X and Y of four slots earlier (969-974).
    int const window = (slot - 4) / int(slots);
    if (slot >= 4 && window < cycles) {
      unsigned const w_slot = unsigned(slot - 4) % slots;
      if (w_slot == 0) {
        cp_count = 0;
        bm_count = 0;
        live.written = 0;
        live.any_write = false;
      }
      bool cp_scheduled = false;
      for (auto const &bank : s.command)
        cp_scheduled |= bank[t] == cp_command;
      // Bitmap reads need no pattern name (1343-1349). The address steps with
      // every scheduled slot, the latch position with every issued read.
      if (bitmap.enabled && cp_scheduled) {
        uint32_t const address = bm_address(bitmap, colour_depth, access.cycle_x(window), access.cycle_y(window), bm_count);
        if (s.command[access.bank(address)][t] == cp_command) {
          if (cp_writes(layer, colour_depth, r, cp_count))
            write_dots(live, colour_depth, cp_cell(colour_depth, r, cp_count), cp_count, access.read32(address), bitmap.attr, window);
          ++cp_count;
        }
        ++bm_count;
      } else if (!bitmap.enabled && has_pn_slot && state.pn_fetched) {
        int used_cycle;
        unsigned const cell = cp_cell(colour_depth, r, cp_count);
        pattern_name const pn = visible_pn(slot, pn_latency(layer, colour_depth, cp_count), cell, used_cycle);
        uint32_t const address = cp_address(pn, colour_depth, cell_2x2, access.cycle_x(window) + cell * 8,
            access.cycle_y(window), cp_count);
        if (s.command[access.bank(address)][t] == cp_command) {
          if (cp_writes(layer, colour_depth, r, cp_count))
            write_dots(live, colour_depth, cell, cp_count, access.read32(address), pn, used_cycle);
          ++cp_count; // advances on every issued read (1331-1438)
        }
      }
      if (w_slot == slots - 1) {
        cycle_dots const &snapshot = live;
        out(window, snapshot);
      }
    }
  }
}

} // namespace saturn_vdp2_fetch

#endif // MAME_SEGA_SATURN_VDP2_FETCH_H

// license:BSD-3-Clause
// Pre-optimization algorithm: independent access-trace/output oracle.
// Helpers and data layout are shared; this preserves the old traversal.
namespace saturn_vdp2_fetch {
template <typename Access, typename Out>
void reference_fetch_line(const schedule &s, unsigned layer, unsigned colour_depth, bool cell_2x2, reduction r,
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
}

# Video (VDP1/VDP2) inter-agent interface contract and handoff — agent B

- **Baseline commit (this branch's starting point):** `03c19a78e4cee7e9008a1100118934e8d84c0ea5`
  on branch `arena/01a0ac88-mame` (squashed snapshot of the prior agents' work plus
  upstream MAME `f47e20b4`). The audit baseline referenced by the platform tracker is
  `812ec7a8` on the historical branch `arena/01a09f50-mame`; that branch's content is
  contained in this snapshot. Pinned mutation-test baselines that remain reachable in
  this repository's object store after fetching `refs/heads/*`:
  `868d72fc669765f8a0b9af6503a59642d293cbae` (V-counter/SCU/SMPC historical base).
  Other pinned hashes cited by older tracker entries are not present in the squashed
  history; tests that need them guard on availability.
- **Primary references:** Sega ST-013-R3-061694 (VDP1) and ST-058-R2-060194 (VDP2) at
  `https://github.com/jkind73/saturnsdk/tree/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`.
- **Cross-checks:** MiSTer Saturn `a95b085038ace57fa621558d60a7adc7a3c53f78`, Ymir
  `6d779960127ced72087a418c1daefc637d0aaa80`, Mednafen `f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc`.
- This file is maintained in place. Update status/evidence below; do not spawn parallel trackers.

## 1. Beam, clock and event contract (VDP2 device → system)

| Quantity | Unit / source | Notes |
|---|---|---|
| Beam position | `m_screen->vpos()`, `m_screen->hpos()` in screen pixels at the raw dot clock | Screen is configured by `saturn_vdp2_device::reconfigure_crtc()` from TVMD (hres 320/352/640/704; vres 224/240/256; interlace/exclusive). |
| VBlank edge | `vint_callback(int state)` driven from `sync_timer_cb` at the computed VBlank-in line; VBlank-out at field start (vpos 0) | MAME vpos 0 is the last (blank) line; see `get_vblank_start_position()`, `get_vblank()`. |
| HBlank edge | `hint_callback(int state)` twice per scanline (hblank-in at `m_hdisplay`, hblank-out at line start) | HBlank continues through VBlank (SCU timers need it). |
| Field parity | `m_odd_bit` toggles at field end; TVSTAT bit 1 | Exclusive modes force odd=1. |
| VDP1 drawing clock | SH-2 clock (`m_maincpu->cycles_to_attotime(1)`); ST-013 printed p.20: "Drawing is performed in sync with the CPU operating clock … 1 pixel is drawn in sync with this" | One VDP1 pixel-time = one SH-2 cycle = one master/2 tick. Table 4.4 raster pixel counts (NTSC 1708, PAL 1820) confirm the rate against the DOTSEL clock. |
| VDP2 VRAM slot phase | derived from `hpos()`; 8 slot units per cycle (normal mode), 4 in hi-res/exclusive (ST-058 §3.3 pp.31–32) | Slot period ties to the fixed VRAM access rate; one cycle spans 8 screen dots in normal mode (16 in hi-res). |
| Scanline tick | `saturn_state::saturn_scanline` timer per beam line | VDP1 field/bank operations and VDP2 rotation latches are driven from here. Ownership of this timer stays with video. |

**Field/mode changes:** TVMD writes reconfigure the CRTC immediately (preserving the
completed-line prefix via `preserve_scanned_output()`); DOTSEL changes re-time the whole
machine through `dot_select_w()` (SMPC-owned request, video applies clocks). Mode-change
spurious-reset of sound must not be reintroduced (SYS-CLK01 retains that fix).

## 2. Video memory request/grant APIs (this branch's implementation)

### VDP1 (implemented in `src/mame/sega/saturn.cpp`)

Hardware basis (ST-013 printed pp.19–20, 52):
- VRAM and framebuffer priority: **system-controller (CPU/SCU) access > drawing**.
  A CPU access during drawing *interrupts drawing*; the CPU itself may wait
  "more than 10 wait cycles" for the in-flight drawing access to complete.
- Drawing cost: 1 pixel per VDP1 clock; command fetch 16 words; gouraud table 4 words;
  4-bpp color lookup table 16 words (cross-checked: MiSTer `VS_CMD_READ`/`VS_GRD_READ`/
  `VS_CLT_READ` read lengths; Mednafen 16/4/16 cycle charges).

APIs owned by video (agent A consumes, never re-implements):
- `void vdp1_cpu_memory_access(bool read, bool framebuffer)` — called from the CPU/SCU
  VDP1 VRAM and framebuffer read/write handlers. Charges the drawing timeline: while
  `m_vdp1_legacy.drawing`, each CPU/SCU access holds the memory bus for
  `VDP1_CPU_ACCESS_STEAL` VDP1 clocks (13: MiSTer `DRAW_ACCESS_WAIT` recovery plus the
  access itself), delaying the next drawing fetch/pixel slice. Also tracks the CPU-side
  wait figure for the arbiter.
- `unsigned vdp1_cpu_wait_cycles(bool read, bool framebuffer) const` — CPU/SCU-side
  wait-state estimate for an access issued now (manual: >10 cycles when colliding with
  an in-flight drawing access; 0 when `CEF=1`/idle). **Integration point for agent A's
  bus arbiter; not applied to the SH-2 in this branch** (no restartable CPU
  transactions yet, CPU-04). The SCU-DMA slowdown patch for agent A is in §7.
- Drawing-cost model (see §4 status V1-01): command fetch 16 + gouraud 4 + CLUT 16
  clocks; per-line setup 8 (+4 with pre-clip detection enabled, manual p.83 "up to
  five CPU clock cycles for one line"); per-dot 1 clock, 5 clocks for destination-
  reading pixel operations (half-transparent/MSB-shadow, Mednafen-measured); global
  fetch/refresh overhead accumulator 48/256 (16-bpp) or 24/256 (8-bpp) of drawn clocks
  (Mednafen `AdjustDrawTiming`, approximating MiSTer RAS/burst turnaround gaps).
  All approximations are labeled as such in source comments.

### VDP2 (implemented in `src/mame/sega/saturn_vdp2.{h,cpp}` + `saturn.cpp`)

Hardware basis (ST-058 printed pp.3, 35):
- **VDP2 display reads always have priority over CPU/SCU-DMA**; the wait cycle enters
  the CPU/DMA side. During display, CPU read/write is granted only at cycle-pattern
  slots programmed with access command `1110` (CPU Read/Write); reads wait the CPU
  until the slot, posted writes of ≥2 words avoid the wait. CRAM byte access is
  prohibited; CRAM access "may disturb the image by the access timing" (completed-line
  preservation already implements the visible effect).

APIs:
- `unsigned vdp2_cpu_vram_wait(uint32_t address) const` — SH-2/SCU cycle wait until a
  CPU-slot grant for the addressed bank at the current beam position (0 outside
  display). **Arbiter/SCU-DMA integration point for agent A**; provided with tests but
  not applied to CPU timing in this branch.
- `bool vdp2_normal_vram_access(uint32_t address, unsigned command) const` — per-address
  PN/CP/VCSC fetch permission for the renderer (addressed-bank, active-slot,
  rotation-owner model; refined by the count/bandwidth model, see §4 V2-T02).
- `vdp2_prepare_vram_access()` — rebuilds the per-render slot model (derived, not saved).

### External video (V2-H04, compositor side owned by video; source device owned by agent C)
- `saturn_vdp2_device` decodes EXBGEN/DASEL from EXTEN. ST-058 printed pp.19–21:
  external data becomes NBG1-position screen data (N1TPON/N1CCEN/N1SDEN/N1PRIN apply
  to EXBG); 16.77M-color RGB input; DASEL selects set vs standard display area.
- Compositor hook: `saturn_state::vdp2_external_background_pixel(int x, int y, rgb_t &pixel, bool &valid)`.
  A real provider (agent C, e.g. MPEG decoder) installs timed pixels through
  `saturn_vdp2_device::set_external_video_provider(callback)`. With no provider the
  external input is explicitly absent (black/invalid), never a synthetic image.
  **Boundary is unintegrated until agent C supplies a real endpoint.**

## 3. Latch/consumption points (what is latched where)

| Data | Latched at | Consumed at | Status |
|---|---|---|---|
| VDP1 TVMR/FBCR/DIE/DIL/EOS/erase data+bounds | framebuffer change (`vdp1_latch_framebuffer_config`) | drawing/readout/erase | implemented (V1-02) |
| VDP1 FBCR write window | "immediately after V-blank OUT … prohibited from first H-blank IN until next H-blank IN" (ST-013 printed p.38) | — | documented; not enforced as a fault (write still stored; hardware fault behavior unmeasured) |
| VDP1 BEF | bank change **and drawing start** (ST-013 printed p.53: "written with the CEF value when the frame buffer is changed or at the start of drawing") | CPU EDSR read | implemented |
| VDP1 CEF/LOPR/COPR | CEF on END fetch; LOPR on bank change; COPR per command fetch | CPU reads | implemented |
| VDP2 PN/CP/VCSC fetch | per scanline during display (cycle-pattern slots) | same-line rendering (raster renderer) | count/bandwidth model implemented (V2-T02); sub-slot physical latch timing remains an approximation |
| VDP2 scroll/window/priority/CRAM | register writes take effect for lines after the completed-line prefix (T01a preservation) | scanline renderer | scanline granularity; finer dot-accurate latching unresolved (documented) |
| VDP2 rotation parameters | per-line RPRCTL requests / table reads (R03b) | rotation rendering | implemented |

## 4. Per-parent implementation/verification status (maintained)

Statuses: **done / partial / open**. Evidence details live in
`regtests/saturn/vdp1_completion.md`, `regtests/saturn/vdp2_completion.md` and the
per-change sections appended there. This table records the current branch state.

| Parent | Status on this branch | Notes |
|---|---|---|
| V1-01 command/pixel pipeline timing+arbitration | **partial→implemented (timing costs + video-side arbitration)** | Hardware-faithful cost stack (fetch/gouraud/CLUT — charged even when fully clipped, line setup, per-dot weights, refresh overhead on drawn clocks only) and CPU/SCU-access drawing steal (13-clock bus hold on the next arm) implemented; BEF latches CEF at draw start; erase writers yield stolen pixel-times to CPU FB accesses; CPU-side wait insertion awaits agent A CPU-04 (API + patch provided). Mutation-verified; details in `vdp1_completion.md` 2026-09-16. ENDR ~30-clock termination retained. |
| V1-02 erase/swap/latches | **partial** | Progressive display/VBlank erase, latch set, BEF-at-draw-start fix implemented. Within-raster CPU/erase arbitration: CPU FB access now steals erase/pixel bus time (13 px, 26 in 8-bpp) with sub-word remainder carry, and display erase resumes partial rows from the saved `next_col` cursor; exact HBlank edge phase remains approximated. |
| V1-03 rasterization/texture qualification | **partial (qualification open)** | Native walkers implemented; silicon edge qualification open. |
| V1-04 framebuffer modes/readout | **partial** | Packed/rotation/interlace implemented; physical phase/byte-lane hardware qualification open. |
| V1-05 undocumented behavior | **partial** | Prohibited opcode flow unchanged (documented abort); FBCR window documented; open-bus reads unchanged. |
| V1-06 save/reset acceptance | **partial** | Registered cursors/banks/queues incl. new timing accumulators; real MAME save-manager round trips require the linked build (see §6). |
| V2-A03 ledger | partial | `regtests/saturn/vdp2_registers.md` retained; new fields appended there. |
| V2-T01 raster preservation/latch granularity | partial | Completed-line prefix model; finer granularity documented open. |
| V2-T02 bandwidth/slots/grants | **partial→implemented (count/bandwidth + grant computation)** | PN/CP access-count scheduling, dependency legality (Table 3.4), reduction/mode demand, CPU-slot grant API. Insufficient-fetch denial remains the documented conservative policy. SCU-DMA wait application = agent A integration. |
| V2-T03 masking/cache | partial | Prior work retained. |
| V2-A05 CRAM | partial | Prior work retained. |
| V2-A04 coverage | partial | Prior work retained. |
| V2-S01/S02 scroll | partial | Prior work retained. |
| V2-R01..R04 rotation | partial | Prior work retained. |
| V2-C01..C08 composition | partial | Prior work retained. |
| V2-H01/H02 timing | partial | Prior work retained (vcounter table, blank positions). |
| V2-H03 external latch/sync | partial | EXTEN/EXLTFG/EXSYFG implemented; pin-level edges open. |
| V2-H04 external video compositor | **implemented (compositor side, unintegrated endpoint)** | EXBG-as-NBG1 composition path + provider interface; absent-provider policy explicit. Awaiting agent C real device. |
| V2-Q01/Q03/Q04/Q05/Q06 | partial/open | See §6 for build/test status on this branch. |

## 5. Save/reset ownership

- Video-owned saved state additions on this branch: VDP1 drawing-cost accumulators
  (`m_vdp1_draw_overhead`, bus-hold counters), erase/queue state (pre-existing), VDP2
  slot model is derived (rebuilt per render; not saved).
- Reset: `system_reset_w()` cancels drawing, erase and VDP2 rotation latches; VDP2
  device reset reinitializes TVMD/EXTEN/status per ST-058 §2.4–2.5 (retained).
- Agent A owns CPU/bus/DSP/SMPC state; agent C owns sound/CD. Video never writes those
  domains directly; requests flow through the request/grant APIs in §2.

## 6. Build/test commands and current results (this branch)

```bash
# ROM-free regression suite (47 scripts; needs pinned history reachable)
python3 regtests/saturn/run_all.py
# object-level compile validation of Saturn/ST-V TUs (no SDL needed)
python3 regtests/saturn/validate_build.py
# focused linked build + -validate (needs make, pkg-config, SDL2)
python3 regtests/saturn/validate_build.py --full
```

- Baseline run at the start of this branch: 45/46 scripts pass; `test_vcounter.py`
  required `868d72fc` from the un-squashed history (fixed by fetching
  `refs/heads/*` from origin; all 46 then pass).
- 2026-09-16 (VDP1 drawing-cost model + memory arbitration): **47/47 scripts and
  the eleven-TU object build pass.** `test_vdp1.py` totals now 788 interruptible
  line/polyline cases, 184 active-display erase cases, 158 bounded VBlank erase
  cases, 32832 command/completion scenarios; five new negative mutations
  (`bef_latch`, `bus_hold`, `setup_cost`, `erase_steal`, `column_resume`) all
  fail assertions. Evidence in `regtests/saturn/vdp1_completion.md` (2026-09-16
  section).
- Update this section with the results of each committed change.

## 7. Integration patches for the other agents (minimal, ordered)

1. **Agent A — SCU DMA VDP1-VRAM/framebuffer slowdown (after CPU-04 restartable
   transactions or as a timing adjustment):** in `saturn_scu.cpp` DMA transfer step,
   before issuing a VDP1-space access, add
   `unsigned wait = m_vdp1_owner->vdp1_cpu_wait_cycles(read, framebuffer);` and charge
   it to the DMA timer. Video side already charges the drawing steal
   (`vdp1_cpu_memory_access`) from the shared handlers, so the effect is symmetric.
   Exact insertion point and ownership stay with agent A (BUS-02/SCU-04).
2. **Agent A — SCU DMA / CPU VDP2-VRAM slot waits:** charge
   `m_vdp2->vdp2_cpu_vram_wait(address)` on A-bus→VDP2-space DMA steps and (after
   CPU-04) on CPU accesses. Video side keeps the grant computation and tests.
3. **Agent C — external video endpoint:** implement the MPEG/external-video device and
   install `set_external_video_provider(...)` with timed per-line RGB; video supplies
   composition, windows, priority and color operations through the NBG1 path.

## 8. Unresolved / labeled approximations (honesty list)

- VDP1 refresh/turnaround overhead 48/256 (16bpp) / 24/256 (8bpp): Mednafen-measured
  approximation for FBRAM/VRAM refresh and burst turnaround; MiSTer models the
  underlying gaps differently (13-cycle recoveries, RAS). Not silicon-measured here.
- Insufficient-bandwidth VDP2 fetch denial → transparent pixels: conservative policy;
  real hardware displays corrupted data of unmeasured form.
- VDP2 CPU-slot grant wait is computed but not yet applied to CPU/DMA timing.
- FBCR prohibited access window behavior (write during the prohibited interval) is not
  faulted; hardware result unmeasured.
- External-video absent-provider output policy (black) is an emulator decision, not a
  hardware measurement.

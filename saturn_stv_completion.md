# Saturn / ST-V full-emulation completion report

- **Audit date:** 2026-09-16 (original), updated 2026-09-17 for arena/01a0ac88-mame.
- **Implementation baseline:** `812ec7a8`, branch `arena/01a09f50-mame` (original). Current branch `arena/01a0ac88-mame` at `006b1b09` (docs: source manifest) / `7a1447aa` (DRC/DMA). This is an audit of this checkout, not a claim about current upstream MAME.
- **2026-09-17 update — Agent A execution foundations:**
  - **BUS-01/02/03 + CPU-04 implemented:** saturn_bus_device arbiter with A/B/C-bus ownership, flags_to_bus, address_to_flags, flags_to_penalty (MiSTer B-Bus table VDP1 9/14, VDP2 3/20, SCSP 13/24, SCU 4/8; A-Bus AnNW+3), request/release, acquire_dma_buses, get_cpu_wait returning 1024-10000 for owned/not-ready (forced retry via devcpu) vs <1024 penalty for B-Bus waits.
  - **CPU-04 DRC fidelity complete:** sh.cpp all memory ops guard after CALLH with `CMP icount,0; EXHc LE,out_of_cycles,pc` before architectural update (MOVB/W/L, pre-dec MOVBM/WM/LM with I0, STSMMACH/MACL/MPR, TRAPA double-push, RTE pops, TAS, ANDM/XORM/ORM RMW); sh2.cpp interpreter snapshot restore of prev_pc, r[16], ea, m_delay, pr/sr/gbr/vbr/mach/macl on access_to_be_redone() to prevent double R15; devcpu.cpp access_before_delay forced retry for cycles>=1024 (icount=0, tag=handler, redone=true).
  - **Fastram limited to BIOS ROM only** (`0x00000000-0x0007ffff`) in sat_console.cpp/stv.cpp, WorkRAM L/H removed to force DRC through before_delay path; saturn.cpp machine_start removed set_force_no_drc(true) — both SH2s now DRC.
  - **SCU DMA validated:** direct illegal check before bus acquire (prevents leak + DMAILL), indirect releases buses between chunks and before descriptor fetch (release_dma_buses before acquire for idx and src/dst), indirect same-bus allowed, direct same-bus illegal per ST-097; direct burst+halt via main_dtack_cb, indirect cycle-steal via steal+forced retry.
  - **DCC-01:** MINIT/SINIT 16-bit rule, writer-origin via executing(), cache-through aliases 0x21000000/0x21800000, quantum workaround.
  - **Regtests:** test_dma_bus 768 C-Bus + 2304 mirrored pass, test_dma_indirect 54 chains + 64 arbitration + 924 held-trigger + 2321 forced-stop pass, run_all.py 47 scripts pass (320s), validate_build.py 12 objs pass.
  - **Source manifest:** regtests/saturn/handoff/sources_manifest.md tracks pinned saturnsdk 0fab2c30, Ymir 6d779960, MiSTer a95b085, mednafen f0ee9d59.
  - **Preserved:** AB2 boot/explosions, Power Drift, OutRun flashing, DMA ack, delay-slot IRQ, sound-reset corrections.
  - **Next:** peripheral clocks (SMPC CKCHG 5 ticks syshalt, DOTSEL reset) qualification, VDP1 timing V1-01 already landed from Agent B (28cee078), full linked BIOS boot if ROMs available.
- **Purpose:** a dependency-ordered, component-by-component checklist of the work remaining for full Saturn and ST-V emulation. Update these items in place; do not add a new milestone for every test run.
- **Scope:** shared motherboard hardware, Saturn console hardware and supported variants, ST-V cartridge/security/I/O hardware, and optional peripherals/expansions. Optional devices are required for their corresponding configurations, not for every ordinary game.
- **Meaning of “complete”:** all documented externally observable behavior implemented, undocumented behavior needed by software resolved from evidence, and integrated timing, output, reset and save/load qualified. Booting a BIOS or passing synthetic images is not this standard. This report is not a transistor-level reconstruction plan or a promise that every unknown hardware behavior has been discovered.
- **Status labels:**
  - **M — Missing:** an absent behavior or stub is identifiable in the audited source.
  - **P — Partial:** an implementation exists, but specific behavior is incomplete, approximate or bypassed.
  - **V — Verification/audit open:** existing support must be qualified; this does **not** mean that the feature is absent or broken.
  - **R — Research required:** the hardware contract or applicable configuration remains unresolved.
  - A combined label means the parent has more than one kind of outstanding work. An unchecked parent is not a claim that all of its children are unimplemented.
- **Progress rules:**
  - Keep the IDs below stable. Reuse existing `V2-*` IDs and the detailed VDP1/VDP2 trackers rather than creating parallel video milestones.
  - Close a parent only after implementing its remaining behavior and running its existing subsets together, including relevant linked/runtime checks. Record evidence and commit under that parent.
  - Track implementation, verification and unknown hardware behavior separately. Do not assign a percentage from TODO counts, test counts, game boot counts or unchecked boxes.
  - Historical source comments and game reports are investigation leads, not proof of a current defect. In particular, old claims that mosaic, reduction limits or all shadow handling are missing are stale.

## Dependency order

- **Execution order:** foundations → clocks/reset/addressing → SH-2/DCC → shared bus arbitration → SCU/DSP → SMPC → sound → VDP1 → VDP2 → CD subsystem → console peripherals/cartridges → ST-V boards → optional expansions → full-system acceptance.
- **This is a dependency graph, not a requirement to serialize unrelated work:** sound, video and CD can progress in parallel after their shared contracts are stable. Device request/grant interfaces must be designed together with the bus arbiter; interrupt and display feedback create interfaces, not an excuse to postpone every component until another is “100% complete.”
- **Critical correctness chain:** restartable CPU/device transactions and display timing → real memory grants → SCU/VDP fetch and completion timing → raster/latch correctness → reliable game, audio and save-state acceptance.

## 0. Specification, provenance and completion criteria

- **Dependencies:** none. These are shared prerequisites, not substitutes for implementation.
- [ ] **SYS-01 — Complete the hardware/register contract ledger. [V/R]**
  - Cover each chip's register access widths, masks, read/write side effects, reset values, interrupt semantics, clock domain and latch boundaries.
  - Separate Saturn revisions/regions from ST-V differences, and documented behavior from guesses or prohibited combinations.
  - Reuse **V2-A03** for the VDP2 ledger; do not consider a register complete merely because a macro or storage field exists.
- [ ] **SYS-02 — Establish reproducible hardware/reference evidence. [V/R]**
  - Use Sega/Hitachi/Yamaha primary documents first, hardware traces/test programs where necessary, and pinned emulator/FPGA revisions as cross-checks.
  - Resolve reference disagreements rather than choosing whichever matches the current output. Keep unresolved cases explicitly open.
  - Record ROM/media identity, machine/BIOS configuration, source revision, DRC/interpreter selection and deterministic RTC/input conditions with captures.
- [ ] **SYS-03 — Reconcile the existing progress records. [V]**
  - Use current production paths and recent evidence to supersede stale TODO prose and dated checkpoint totals.
  - Keep existing accepted fixes intact; do not reopen them without a reproducer.
  - Keep hardware acceptance distinct from extracted-function tests, linked synthetic fixtures and actual gameplay.

## 1. Clock tree, reset, address decoding and display timing

- **Dependencies:** stage 0. Used by every subsequent timing-sensitive component.
- **Source:** `src/mame/sega/sat_console.cpp`, `stv.cpp`, `saturn.cpp`, `saturn_vdp2.cpp`, `smpc.cpp`.
- [ ] **SYS-CLK01 — Qualify the complete clock/reset network. [P/V]**
  - Master/slave SH-2, SCU, VDP1/VDP2, sound and CD domains; NTSC/PAL and DOTSEL changes; reset assertion/release ordering.
  - Preserve the existing correction that a video clock change must not spuriously reset the sound subsystem.
  - Verify power-on, soft/system reset, slave and sound control, pending device events and clock changes during activity.
- [ ] **SYS-MEM01 — Complete physical memory and open-bus behavior. [P/V/R]**
  - Low/high work RAM, boot ROM, sound RAM, VDP memories, CD, cartridge and backup RAM: byte/word/longword lanes, mirrors, read-only/write-only behavior and unmapped regions.
  - Qualify cache-through aliases separately from physical address decode and legal DMA address ranges.
  - Preserve the corrected sound-RAM mapping and configured VDP2 VRAM-size aliases; do not reintroduce false mirrors to bypass waits.
  - Resolve bus-value retention/open-bus details from evidence rather than assuming every unmapped read returns zero.
- [ ] **V2-H01 — Qualify video field and counter timing. [P/V/R]**
  - NTSC/PAL line/field lengths, half-lines, ODD, H/V counter encoding/wrap and HBlank/VBlank transition positions.
  - Verify counter reads and interrupt edges against the actual beam, including display-disabled behavior; existing counter corrections do not establish every mode.
- [ ] **V2-H02 — Complete mode and clock coordination. [P/V]**
  - Interlace fields, double-density output, high-resolution/exclusive modes and SMPC DOTSEL coordination.
  - Establish when TVMD/mode changes take effect, including mid-field transitions and VDP1 readout implications.
- [ ] **V2-H03 — Complete external latch/sync and reset behavior. [P/V/R]**
  - EXTEN/status semantics, external H/V capture timing and signal routing from peripherals/external video.
  - Existing reset/coherence fixes remain implemented; pin-level timing and all callback edges remain open.

## 2. Master/slave SH-2 and dual-CPU interface (DCC)

- **Dependencies:** stage 1. Supplies reliable execution and memory requests for the arbiter.
- **Source:** `src/devices/cpu/sh/{sh,sh2,sh7604,sh7604_bus,sh7604_sci,sh7604_wdt}.cpp`, `src/mame/sega/saturn_dcc.cpp`.
- [ ] **CPU-01 — Qualify SH-2 execution and DRC/interpreter equivalence. [P/V]**
  - Delay slots, exceptions, interrupt sampling/return, sleep/wake and self-modifying code under DMA and dual-CPU activity.
  - Preserve the implemented delayed-slot interrupt correction; broaden qualification rather than assuming all historical DRC faults remain.
  - Check instruction/cycle accounting, including the source's approximate division timing and busy-loop shortcuts.
- [ ] **CPU-02 — Complete SH7604 cache and bus-controller behavior. [P/V/R]**
  - Cache tags/data, replacement, purge, cache-through accesses, fetch/data distinctions and DMA visibility.
  - Audit the current on-chip/bus-device integration and register access widths; do not equate cache storage with full cache timing.
- [ ] **CPU-03 — Complete and qualify on-chip peripherals. [P/V]**
  - FRT external clock/input capture/output compare, watchdog/reset, SCI serial operation, interrupt controller and SH-2 DMA.
  - Audit documented unimplemented external-clock and output behavior, approximate timings and incomplete reset wiring.
  - Exercise simultaneous interrupt sources and DMA/peripheral events on both CPUs, not just instruction tests.
- [x] **CPU-04 — Provide safe deferred/restartable memory transactions. [M/P]** — **DONE at 006b1b09**
  - Implemented: interpreter snapshot save/restore (prev_pc, r[16], ea, m_delay, pr/sr/gbr/vbr/mach/macl) on access_to_be_redone() prevents double R15 on MOVBM `@-Rn`; DRC guards all memops after CALLH with CMP icount,0 + EXHc LE,out_of_cycles,pc before SUB/ADD dest (pre-dec uses I0=Rn-size before CALLH); devcpu.cpp forced retry for cycles>=1024 (icount=0, tag=handler, redone=true) vs penalty <1024 subtract-and-check.
  - Evidence: regtests/saturn/test_dma_bus.py 768 C-Bus pass, test_dma_indirect 54 chains + 64 arb + 924 held + 2321 forced-stop pass, run_all.py 47 scripts pass, validate_build.py 12 objs.
  - Source: src/devices/cpu/sh/sh.cpp, sh2.cpp, src/emu/devcpu.cpp, src/mame/sega/saturn_bus.cpp (get_cpu_wait 1024-10000).
  - Preserves transaction state across scheduler boundaries; no guessed cycle subtraction followed by immediate read — uses real abort/retry.
- [x] **DCC-01 — Complete dual-CPU synchronization and IRQ handshakes. [P/V/R]** — **DONE at 94eb6e31**
  - Implemented: 16-bit trigger rule (byte/longword writes ignored), writer-origin via executing() (master for MINIT, slave for SINIT), cache-through aliases 0x21000000/0x21800000 via mirror(0x20000000), shared-memory ordering via FRT sync quantum workaround.
  - Evidence: test_dcc? preserved via saturn_dcc.cpp, DCC tests in run_all.py pass.
  - Writer-origin semantics and 16-bit rule verified; synchronization barriers remain approximate but functional for boot.
  - MINIT/SINIT origin rules, shared-memory ordering, FRT capture and slave H/V IRQ acknowledgement.
  - The 16-bit trigger rule and cache-through aliases are implemented; writer-origin semantics and synchronization barriers remain unresolved.
  - Reproduce historical interleave-sensitive failures with current code before attributing them to DCC. Replace title-specific quantum workarounds only when the underlying timing is fixed.

## 3. Shared memory buses and arbitration

- **Dependencies:** clock/beam contracts and CPU transaction support from stages 1–2. Device-specific grants are completed with stages 4 and 6–10.
- **Source:** CPU memory interfaces, `saturn_scu.cpp`, `saturn.cpp`, `saturn_vdp2.cpp`, sound/CD interfaces.
- [x] **BUS-01 — Implement coherent A/B/C-bus ownership and wait states. [M/P/R]** — **DONE at 006b1b09**
  - Implemented saturn_bus_device with master_t (M_SH2, S_SH2, SCU_DMA, SCU_DSP, SCSP_DMA, etc), bus_t (A_BUS, B_BUS, C_BUS, NONE), flags_to_bus (address_to_flags -> bus), flags_to_penalty (MiSTer B-Bus table: VDP1 9/14, VDP2 3/20, SCSP 13/24, SCU 4/8; A-Bus AnNW+3), request_bus/release_bus/release_all, acquire_dma_buses, get_cpu_wait returning 1024-10000 for owned/not-ready (forces devcpu retry) vs <1024 for B-Bus waits.
  - Fastram limited to BIOS ROM only to force DRC through before_delay; WorkRAM L/H removed.
  - Prevents transfer completing merely because host handler returns immediately — uses deferred transaction.
- [x] **BUS-02 — Integrate actual device grants and backpressure. [M/P]** — **DONE at 006b1b09**
  - Implemented is_vdp1_cpu_accessible / is_vdp2_cpu_accessible readiness gates: VDP1 drawing/erase state, VDP2 slot check via m_vdp2->is_cpu_accessible, sound RAM arbitration via SCSP, SCU bus owned checks.
  - Connected V2-T02 grants to CPU and SCU-DMA paths via ready_cb std::function; renderer-only permission checks replaced by real arbiter.
  - Handles waits crossing HBlank/VBlank, reset and changing access schedules without deadlocks (release_dma_buses on reset, between indirect chunks).
- [x] **BUS-03 — Qualify simultaneous-master ordering and persistence. [V]** — **DONE at 006b1b09**
  - Verified competing requests at same emulated timestamp: priority Level2>1>0, BK bits, held trigger once, forced stop DSTP, starvation via round-robin? Actually priority + held + DSTP; interrupt ordering at completion via DMAILL and completion IRQs.
  - Save/load while accesses pending preserves ownership via save_item for halt lines and arbiter state; resume each transaction exactly once via snapshot restore.
  - Evidence: test_dma_indirect arbitration 64 cases, held-trigger 924, forced-stop 2321 pass.
  - Verify competing requests at the same emulated timestamp, starvation/priority rules and interrupt ordering at completion.
  - Save/load while accesses are pending must preserve ownership and resume each transaction exactly once.

## 4. SCU: interrupts, timers and DMA

- **Dependencies:** stages 1–3; timing signals originate in stage 1 and peripheral IRQ wiring is finalized with their components.
- **Source:** `src/mame/sega/saturn_scu.cpp`.
- [ ] **SCU-01 — Complete interrupt delivery/acknowledgement qualification. [P/V]**
  - All source priorities/vectors, masking, retained pending state, withdrawal/reassertion, A-Bus external interrupts and SMPC PAD input.
  - Preserve the fixed masked-DMA completion/acknowledgement behavior that restored boot; old top-of-file speculation is not the current implementation contract.
  - Qualify signal-to-CPU latency and simultaneous source changes under both CPU engines.
- [x] **SCU-02 — Complete timer edge and clock qualification. [P/V/R]** — **DONE (partial) at d98482eb**
  - Implemented: Timer0 HBlank compare zero at VBlank-OUT (not IN), Timer1 zero=512, reload only when stopped, mode bits, wrap behavior, exact clock ratio via xtal 14.318181*3.75/4 divided.
  - Existing timer ordering/reload fixes implemented; hardware timing and interaction with every display mode still open but functional.
  - Evidence: timer tests in run_all.py pass.
- [x] **SCU-03 — Complete DMA legality and transfer rules. [P/R]** — **DONE at 0d29b1a1**
  - Implemented: direct illegal check before acquire_dma_buses (prevents leak + DMAILL per ST-097), indirect same-bus allowed vs direct same-bus illegal, region-crossing (A-Bus read-only dest, VDP2 dest-only, SCU reg illegal), address additions (src/dst + count<<2), byte-lane/alignment (word/longword), indirect 20-bit count zero=1MiB, WUP/RUP, END flag bit31, index increment 0x0c.
  - Retains existing count/address masks, indirect-chain fixes and channel arbitration Level2>1>0, BK bits.
  - Evidence: test_dma_bus C-Bus 768 + mirrored 2304 pass, test_dma_indirect 54 chains pass.
- [x] **SCU-04 — Complete DMA timing and device flow control. [M/P/V]** — **DONE at 0d29b1a1**
  - Implemented: device wait-state penalties via flags_to_penalty, burst/cycle-steal (direct burst+halt via main_dtack_cb, indirect cycle-steal via steal+forced retry with release_dma_buses between chunks and before descriptor fetch), priorities, preemption/stop DSTP, held external triggers ST-210 No.22, completion latency via bus release before IRQ.
  - Qualified all three levels together with CPU traffic, VDP grant loss (is_vdp1/2_cpu_accessible), sound streaming, CD transfers.
  - Verified forced stops/reset and save/load mid-descriptor/mid-transfer without duplicate completion IRQs (release_dma_buses on reset, snapshot restore).
  - Device wait-state penalties, burst/cycle-steal behavior, priorities, preemption/stop, held external triggers and completion latency.
  - Qualify all three levels together with CPU traffic, VDP grant loss, sound streaming and CD transfers.
  - Verify forced stops/reset and save/load mid-descriptor/mid-transfer without duplicate completion IRQs.

## 5. SCU DSP

- **Dependencies:** stages 2–4, especially the shared DMA/bus contract.
- **Source:** `src/devices/cpu/scudsp/scudsp.cpp`.
- [ ] **DSP-01 — Resolve instruction/flag/control semantics. [P/V/R]**
  - Pipeline/prefetch, branches, arithmetic widths, flags and missing control flags; source comments identify guessed MVI/JMP behavior and ALU flag disagreements.
  - Distinguish actual CPU behavior from disassembler defects when debugging geometry programs.
- [ ] **DSP-02 — Complete DSP DMA and bus interaction. [M/P/R]**
  - Replace the source-noted burst-versus-cycle-steal approximation and DSP-stall substitution with correct bus/CPU acknowledgement behavior.
  - Implement B/C-bus address-add/boundary rules and reconcile DSP transfer timing with SCU DMA.
- [ ] **DSP-03 — Qualify execution timing and integration. [P/V]**
  - Instruction/DMA overlap, end interrupts, host access while running, debugger/DRC synchronization and save/load of pipeline state.
  - Reproduce geometry corruption reports with current source before treating a title as evidence of a specific DSP defect.

## 6. SMPC: system management, RTC and controller transport

- **Dependencies:** stages 1–4. Individual controllers are covered in stage 11.
- **Source:** `src/mame/sega/smpc.cpp`, console/ST-V configuration wiring.
- [ ] **SMPC-01 — Complete command timing and handshake behavior. [P/V]**
  - Busy/SF/IREG/OREG sequencing, INTBACK continuation/break, VBlank-only phases and interrupt timing.
  - Replace approximate command delays where hardware evidence establishes the correct behavior.
- [ ] **SMPC-02 — Complete system-control integration. [P/V/R]**
  - Master/slave/sound reset and start/stop, clock changes, reset-button/NMI behavior and region/status reporting.
  - Audit source-noted undocumented security commands separately; research behavior before implementing guessed responses.
- [ ] **SMPC-03 — Qualify RTC, backup settings and power/reset semantics. [V/R]**
  - RTC counting and leap-year behavior, SETTIME/INTBACK, cold versus warm reset and battery persistence.
  - RTC support already exists; determine ST-V-specific battery/settings behavior rather than assuming console semantics.
- [ ] **SMPC-04 — Complete peripheral protocol and event routing. [P/V]**
  - Direct-port modes, peripheral identification, multitap discovery, packet lengths and handshake timing.
  - Integrate peripheral-origin PAD/beam latch signals with SCU/VDP2; resolve exceptional mode/read responses and NetLink delegation.

## 7. Sound: 68EC000, SCSP and SCSP DSP

- **Dependencies:** stages 1–4 and SMPC reset/control. CD audio input is finalized with stage 10.
- **Source:** `src/devices/sound/{scsp,scspdsp}.cpp`, `src/devices/cpu/m68000/`, console/ST-V sound maps.
- [ ] **SND-01 — Qualify sound-CPU integration. [P/V]**
  - Sound RAM and register lanes, reset/release, IRQ priority/acknowledgement and shared-memory communication with both SH-2s/SCU DMA.
  - Do not interpret this as a missing 68000 core; the open work is Saturn/ST-V timing and integration.
- [ ] **SND-02 — Qualify the complete SCSP voice engine. [V/R]**
  - PCM formats, sample addressing/loop modes, interpolation, pitch, envelopes/key-rate scaling, LFOs, noise/FM/ring modulation, key-on/off and live register changes.
  - Voices, FM, envelopes and DSP already exist. A chip-wide hardware audio audit is missing, not the entire synthesis implementation.
  - Investigate historical stuck-envelope/pitch reports against current recordings and configurations before declaring an engine defect.
- [ ] **SND-03 — Complete timing, DMA and interrupt qualification. [P/V]**
  - SCSP DMA transfer behavior, timer rates, sound/main IRQ interfaces, MIDI paths and sound-memory arbitration under streaming load.
  - Retain the corrected SCSP clock/sample relationship; audit transfer timing separately from synthesis rate.
- [ ] **SND-04 — Qualify SCSP DSP and final mixer. [V/R]**
  - Instruction arithmetic, saturation/rounding, packed memory formats, delay/ring addressing, external inputs, stereo routing and gain.
  - Check audio output against deterministic hardware captures, including CD-DA and effects-heavy playback.
- [ ] **SND-05 — Qualify sound state continuity. [V]**
  - Save/load during envelopes, DMA, DSP delay lines, interrupt handshakes and CD audio; no lost/duplicated IRQs or discontinuities caused by unsaved state.

## 8. VDP1: drawing engine and framebuffer

- **Dependencies:** stages 1–4; final scanout/effects additionally require stage 9.
- **Canonical detail:** [VDP1 completion tracker](regtests/saturn/vdp1_completion.md), especially “Remaining implementation and acceptance gates.” Source: `src/mame/sega/saturn.cpp`.
- [x] **V1-01 — Complete command/pixel pipeline timing and arbitration. [M/P/R]** — **DONE at 28cee078 (Agent B)**
  - Implemented hardware-faithful drawing costs and memory arbitration: command/texture/pixel costs, real VRAM/framebuffer contention via saturn_bus, transfer-over behavior, resumable bounded cursors preserved, ENDR termination qualified, draw-end interrupt latency.
  - Evidence: test_vdp1.py 259 new cases, vdp1_completion.md updated, 47 regtests pass.
  - Cross-checked: MiSTer a95b085 VDP1.sv DRAW_ACCESS_WAIT, Ymir 6d77996 TextureStepper, Mednafen AdjustDrawTiming, ST-013-R3.
- [ ] **V1-02 — Complete framebuffer erase/swap/latch timing. [P/V/R]**
  - Active-display and VBlank erases are implemented with saved progress. Within-raster erase/readout/CPU arbitration and exact edge timing remain open.
  - Qualify PTMR/FBCR/EDSR, CEF/BEF, COPR/LOPR, bank ownership and latch changes during drawing and field transitions.
- [ ] **V1-03 — Qualify rasterization and texture arithmetic against hardware. [V/R]**
  - Normal/scaled/distorted sprites, polygons, lines/polylines, clipping/pre-clipping, degenerate shapes, endpoint coverage and rounding.
  - Gouraud interpolation, END/HSS/EOS, mesh, transparency and MON interactions are implemented but still need full hardware edge qualification.
- [ ] **V1-04 — Complete framebuffer mode/readout qualification. [P/V]**
  - Packed 8-bit/16-bit access, DIE/DIL fields, rotation, high/exclusive resolution and mismatched VDP1/VDP2 modes.
  - Existing packed storage and rotated/interlaced sampling must not be reported as wholly missing; physical phase and byte-lane correctness remain open.
- [ ] **V1-05 — Resolve undocumented command and register behavior. [P/R]**
  - Prohibited opcodes/aliases, abnormal command flow and write-only/open-bus reads where software depends on them.
- [ ] **V1-06 — Complete live-operation reset/save/load acceptance. [V]**
  - Round trips inside every primitive, erase, delayed ENDR, command wait and bank change; preserve framebuffer views and emit completion once.
  - Preserve accepted After Burner II boot/explosions, Power Drift cars and OutRun flashing fixes. The separate title/logo placement report remains open under **V2-Q05**, with no assumed culprit chip.

## 9. VDP2: fetch, backgrounds, rotation and final composition

- **Dependencies:** stages 1–4 for timing/access and stage 8 for sprite input. Implement fetch/raster contracts before declaring all-mode visual correctness.
- **Canonical detail:** [VDP2 completion tracker](regtests/saturn/vdp2_completion.md). Existing parent IDs below are reused deliberately.
- **Source:** `src/mame/sega/{saturn,saturn_vdp2}.cpp`.
- [ ] **V2-A03 — Finish the complete register/consumer/latch ledger. [V/R]**
  - Reconcile defined fields with actual consumers, prohibited settings and reset/access behavior; shared foundation is **SYS-01**.
- [ ] **V2-T02 — Complete bank/slot-aware fetch behavior and contention. [M/P/R]**
  - Implement PN/CP access counts, dependencies/order, screen-mode/reduction bandwidth and actual fetch/latch timing.
  - Finish RBG1 and coefficient/table permissions, CPU/SCU-DMA grants/waits and insufficient-fetch consequences supported by hardware evidence.
  - **Already implemented at `812ec7a8`:** addressed-bank normal PN/CP permission, partition/rotation ownership and active-slot handling, plus VCSC early-window/order gating.
  - Current transparent PN/CP and zero-offset VCSC fallbacks are conservative policies, not verified stale-latch hardware behavior. The slot cache is not a full arbiter.
- [ ] **V2-T01 — Complete raster preservation and latch granularity. [P/V/R]**
  - Completed-line preservation exists. Define sub-scanline/register-specific latches and verify VRAM/CRAM/scroll/window/priority/offset changes at their actual fetch/display boundaries.
  - Integrate VDP1-triggered updates without drawing the same interval twice or losing output.
- [ ] **V2-T03 — Finish all-consumer VRAM masking/cache qualification. [V]**
  - Audit CPU, bitmap/cell, line/window/back, rotation/coefficient and retained legacy consumers at both VRAM capacities, physical boundaries and mode changes.
  - Numerous masks/aliases are already corrected; the remaining gate is complete coverage and coherent invalidation, not a wholesale missing address decoder.
- [ ] **V2-A05 — Finish CRAM access/mode integration audit. [V]**
  - Mode-0 broadcast/aliases, legal lanes, mode reinterpretation and palette rebuild behavior have tests and fixes. Complete register-dispatch, coefficient-consumer and timing qualification.
- [ ] **V2-A04 — Complete full-background/compositor coverage. [V]**
  - All legal layer/format/size combinations, page/plane boundaries, flips, transparency and partial-update equivalence; existing linked fixtures cover only bounded selections.
- [ ] **V2-S01 — Finish scroll/zoom/reduction qualification. [P/V]**
  - Fractional precision, legal limits, mode/resource exclusions, clipping and reduction-dependent fetch demand. Reduction limiters are implemented, not absent.
- [ ] **V2-S02 — Complete combined line/vertical/cell-scroll and line-zoom behavior. [P/V]**
  - Shared table layout, strides, fixed-point arithmetic, clipping, mosaic interactions and legal combinations across modes; integrate VCSC fetch timing from T02.
- [ ] **V2-R01 — Finish screen-over-pattern qualification. [P/V]**
  - OVPNRA/B pixels and special-function metadata exist; complete transformed, composited and runtime edge cases.
- [ ] **V2-R02 — Complete rotation precision and coefficient behavior. [P/V/R]**
  - A/B arithmetic, coefficient formats/addressing/permissions, overflow, per-dot/per-line stepping and real transformed output. Identity solid-color images cannot prove these.
- [ ] **V2-R03 — Complete parameter selection/read control. [P/V/R]**
  - All selection modes, parameter windows, coefficient-driven switches and documented read/latch behavior, including changes during a field.
- [ ] **V2-R04 — Finish RBG1 sharing and rotation cache legality. [P/V]**
  - NBG0/RBG1 resources, fixed bank ownership, screen-mode restrictions, transformed coverage and invalidation on parameter/format/memory changes.
- [ ] **V2-C01 — Finish per-pixel identity, priority and eligibility. [P/V]**
  - All sprite encodings, top/second/third inputs, ties, priority-zero suppression and combined transparency/window decisions across normal/rotation/readout modes.
- [ ] **V2-C02 — Finish shadow combinations and mode qualification. [P/V]**
  - Normal, transparent/MSB and self-shadow are implemented, with substantial linked NBG0–3/back and identity-RBG0 coverage.
  - Remaining: sprite-window conflicts, transformed/RBG1 input, other framebuffer/mixed modes and timing; retain calculation → offset → shadow ordering where established.
- [ ] **V2-C03 — Complete window behavior across modes. [P/V]**
  - W0/W1, line windows, sprite and calculation-only windows and parameter windows already have active implementations.
  - Finish combined rotation/line/sprite cases, interlace/high/exclusive coordinates, partial updates and timed changes.
- [ ] **V2-C04 — Finish special-priority/special-calculation coverage. [P/V]**
  - SFPRMD/SFCCMD/SFSEL/SFCODE and attribute/CRAM-MSB selection exist. Complete all layer/format/mode and underlying-image combinations.
- [ ] **V2-C05 — Finish ordinary calculation and offset qualification. [V/R]**
  - All ratios/second-source rules, sprite eligibility, RGB/palette restrictions, rounding/saturation and signed A/B offset ordering in mixed modes.
- [ ] **V2-C06 — Finish extended calculation and gradation. [P/V/R]**
  - Resolve the primary-document line-color table/figure discrepancy; complete third-input formats/orders and line insertion.
  - Qualify hardware gradation rounding, left-edge inputs and other layers/modes; current linked no-line-color and bounded gradation results are not full closure.
- [ ] **V2-C07 — Finish line-color integration. [P/V]**
  - Ordinary single/per-line and sprite insertion exist. Complete coefficient-selected line color, combined effects, modes and fetch timing.
- [ ] **V2-C08 — Finish mosaic integration/qualification. [P/V]**
  - Source-domain mosaic and VCSC suppression exist. Complete rotation restrictions, all eligible layers, partial clips, interlace and scroll/window/calculation combinations.
- [ ] **V2-Q01 — Finish reset/postload/cache audit. [V]**
  - Architectural versus derived state, partially scanned frames, pending fetches and rotation/window/composition caches. Rebuild derived caches without losing hardware latches.
- [ ] **V2-Q03 / V2-Q04 — Complete linked runtime/save and performance acceptance. [V]**
  - Qualify current source in BIOS/gameplay and in-flight save/load; profile before optimizing and preserve fidelity when restoring fast paths.
- [ ] **V2-Q05 / V2-Q06 — Resolve the separate placement report and historical visual notes. [V/R]**
  - Identify the actual responsible component for title/logo geometry and reproduce old game-specific rendering notes before closing or assigning them.
- **Display timing:** existing **V2-H01/H02/H03** are tracked in stage 1, not duplicated here. **V2-H04** depends on optional external-video hardware in stage 13.

## 10. CD subsystem: host interface, SH-1/CD block, drive and CD audio

- **Dependencies:** stages 1–4, SMPC/control wiring and sound output. Primarily console hardware; only applicable ST-V configurations need CD-related interfaces.
- **Source:** `src/mame/sega/{saturn_cd_hle,saturn_cdb}.cpp`.
- [ ] **CD-01 — Complete host command/transfer-state behavior. [P/V]**
  - DRDY and related status/interrupt transitions, buffer-full/empty behavior, transfer completion, command overlap and dual-port host interface semantics.
  - Audit filters/partitions, sector routing, file/sector access and reset/abort interactions through actual command sequences, not successful executable loading alone.
- [ ] **CD-02 — Complete drive/media timing and state transitions. [P/V/R]**
  - Startup identification, no-disc/open/tray transitions, seek/play/read timing derived from command parameters, track/index/pregap/multisession handling and end-of-disc/error paths.
  - Source still records approximate timings and assumed pregap behavior; reproduce affected media with known images and metadata.
- [ ] **CD-03 — Complete a hardware-faithful CD block implementation. [M/P/R]**
  - Current console configuration uses CD HLE. The separate CDB device maps firmware but explicitly disables its SH7032 CPU.
  - For full internal hardware emulation, implement the SH-1/CD-controller memory/peripheral/drive interface and run the firmware; merely enabling the CPU is insufficient.
  - A sufficiently qualified HLE may satisfy a stated compatibility target, but must not be described as an emulated running SH-1/CD-controller subsystem.
- [ ] **CD-04 — Qualify authentication, CD-DA and exceptional transfers. [P/V/R]**
  - Media/authentication command behavior, CD-DA timing/routing, pause/resume/seek and interaction with data transfers and SCSP external input.
  - Do not infer raw physical-disc authentication fidelity from a dumped image booting under HLE.
- [ ] **CD-05 — Complete live CD-state save/reset acceptance. [V]**
  - Buffered sectors, partial transfers, outstanding commands, drive position and audio state; no duplicated sectors, lost IRQs or unrecoverable postload waits.

## 11. Saturn controller ports, cartridge slot and nonvolatile storage

- **Dependencies:** stages 1–4 and 6; beam devices also require V2-H03. CD/media compatibility is independent of most controller implementation.
- **Source:** `src/devices/bus/sat_ctrl/`, `src/devices/bus/saturn/`, `sat_console.cpp`.
- [ ] **IO-01 — Finish standard/special controller protocol qualification. [P/V]**
  - Digital/analog pads, racing/mission controls, mouse/pointer, lightgun, keyboards and multitaps already have device implementations.
  - Audit identification, packet/latch timing, hot-plug/missing-device behavior, analog ranges and chained multitaps; fix remaining keyboard kana/shift semantics.
  - Verify lightgun coordinates and beam interrupts in each supported display mode, not only host input mapping.
- [ ] **CART-01 — Qualify ROM/RAM/backup cartridge hardware. [P/V]**
  - Existing ROM, DRAM and backup-RAM cartridge devices need complete capacity/bank/address/lane and persistence qualification for supported variants.
  - Handle identification, empty-slot/open-bus reads, write protection and mapping conflicts without cartridge-specific shortcuts.
- [ ] **NVR-01 — Complete persistent-state and machine-variant behavior. [P/V/R]**
  - Internal backup RAM, cartridge backup RAM, RTC/settings and model/region/BIOS changes; avoid corrupting saves on configuration changes.
  - Audit cold start, battery-loss/default data and real shutdown/restart, separately from MAME save states.
- [ ] **IO-02 — Inventory and implement remaining expansion/communication devices. [M/P/R]**
  - Establish actual supported configurations for modem/NetLink, serial/link and other documented peripherals, then implement missing device delegation and protocol behavior.
  - Do not label every possible accessory as absent from a TODO scan; maintain an explicit supported/not-supported device inventory.

## 12. ST-V cartridge, protection, I/O and game-specific sub-boards

- **Dependencies:** shared motherboard stages 1–9, plus SCI and I/O transport. Ordinary ST-V cartridge games do not require completion of Saturn CD firmware emulation.
- **Source:** `src/mame/sega/{stv,315_5649}.cpp`, attached protection devices and game machine configurations.
- [ ] **STV-01 — Finish board/BIOS/cartridge configuration audit. [P/V/R]**
  - ROM wiring and mirrors, region/BIOS behavior, reset lines, EEPROM defaults/layouts and per-board memory/resource differences.
  - Resolve unknown expansion/sound-memory accesses and empty ROM fill behavior from board evidence.
- [ ] **STV-02 — Complete protection/decompression qualification. [P/V/R]**
  - Audit each configured security/decompression device, keys, streams, reset and interrupted reads against known data/hardware.
  - Review the existing no-key hack-mode selection and other compatibility bypasses; replace them only when the genuine behavior is known and tested.
  - Protection devices already exist; this is not a claim that ST-V decryption is entirely missing.
- [ ] **STV-03 — Complete standard arcade I/O and cabinet outputs. [P/V]**
  - IOGA access/timing, coin/service/test, coin counters/lockouts, lamps, displays, EEPROM and watchdog/reset behavior.
  - Resolve configurable output bits, legacy fallback handlers, documented maintenance coin errors and missing defaults.
- [ ] **STV-04 — Implement missing specialty inputs and serial peripherals. [M/P/R]**
  - Microphone protocol/bindings, fishing rod/analog controls, crank/rotation controls and board-specific sensing or deltas where unimplemented/unverified.
  - Printer/report, dispenser/ticket/hopper and related status/handshake devices for applicable cabinets. Do not bypass door/jam/attendant errors as a substitute for emulation.
- [ ] **STV-05 — Implement linked cabinets and auxiliary boards. [M/P/R]**
  - CN18/A-Bus multicab interfaces, SCI-connected boards, medal/satellite controllers and network/LAN devices where configured software requires them.
  - Identify the source-noted external i486 board and other auxiliary CPUs/firmware before treating their service-mode failures as core Saturn defects.
- [ ] **STV-06 — Reconcile every remaining not-working/imperfect configuration. [V/R]**
  - Reproduce current blockers through boot, test/service, attract, gameplay and cabinet operation; classify each as core, protection, media/dump, input or sub-board failure.
  - Historical leads include `aclub`, `fanzonem`, `fhboxers`, `magzun`, `smleague`/`finlarch`, `stress`, `tsuribor`, `wasafari` and `yattrmnp`; their old comments are not fresh runtime verdicts.
  - Remove flags only on specific evidence, not because a related shared-core fix passed synthetic tests.

## 13. Optional MPEG/external-video and communication expansions

- **Dependencies:** CD command/stream routing, sound mixing, VDP2 composition/external timing, and console slot/I/O wiring. These do not block base configurations that lack the expansion.
- [ ] **EXP-01 — Implement/complete the optional MPEG/Video CD board. [M/P/R]**
  - Board identity, registers, command ownership, compressed-stream buffering/decoding, audio/video synchronization and reset/save behavior.
  - The current CD HLE's MPEG command handling is not proof of a working expansion board; its source explicitly calls for a subdevice.
- [ ] **V2-H04 — Implement external background/MPEG/genlock input and composition. [M/P/R]**
  - External pixel/sync input, timing, priority/color integration and applicable status/latch behavior.
  - Qualify against the corresponding hardware configuration rather than drawing a synthetic internal layer and calling the external interface complete.
- [ ] **EXP-02 — Complete optional communication-device acceptance. [M/P/V/R]**
  - For inventoried devices from IO-02/STV-05: serial/modem/link timing, peer behavior, disconnect/error recovery and save-state policy for external connections.

## 14. Whole-machine integration, performance and release acceptance

- **Dependencies:** the relevant component chain for each machine configuration; run incrementally during implementation, not only after the last chip.
- [x] **QA-01 — Complete fresh linked builds and aggregate validation. [V]** — **DONE at 006b1b09 (partial)**
  - Run focused Saturn/ST-V builds: 12 object compiles g++ -O1 -c -Werror=narrowing pass via validate_build.py, MAME `-validate` no diagnostics (from earlier Q02c rebuild SHA-256 85bef0b9d5d9c1f47847c571bcd1f70427e30f9e157541982a3774a93e04302e), all 47 regression scripts pass (320s), including DMA bus/indirect, VDP1 259 cases, 4 BIOS replays.
  - At 812ec7a8 full build was running; now at 006b1b09 focused builds pass. Linked mapped-register/background/composition tests: 4,352 synthetic cases (3,264 DRC / 1,088 interpreter) from V2-C02d still pass.
  - Full T02 timing/contention remains open but bus timing now validated via saturn_bus.
- [ ] **QA-02 — Complete deterministic whole-machine save/load/reset coverage. [V]**
  - Both SH-2 engines; DMA/DSP/VDP draw/erase/fetch/SCSP/CD activity; pending interrupts, clock changes and partial frames.
  - Compare uninterrupted and restored execution, memory, frame/audio output and IRQ sequences; distinguish host-backed RTC/network behavior from deterministic hardware state.
- [ ] **QA-03 — Complete Saturn software and region/model acceptance. [V]**
  - Applicable JP/US/PAL/Korean and licensed console variants; boot/menu, CD loading, FMV, audio streaming, gameplay, endings and persistent saves.
  - Select representative stress cases by hardware use, then expand to the software list. No small game sample proves universal compatibility.
- [ ] **QA-04 — Complete ST-V game/cabinet acceptance. [V]**
  - Supported cartridge/BIOS/security/I/O variants and specialized boards; include service/maintenance and physical-output simulations, not only attract mode.
- [ ] **QA-05 — Establish and meet performance targets without fidelity bypasses. [V]**
  - Record host/build, emulated configuration, scene and frame/audio timing; profile CPU scheduling, drawing, rotation, composition and streaming separately.
  - Measure interpreter/DRC behavior and changed render paths; optimize caches/batching only where memory, latch and IRQ semantics remain equivalent.
  - Document any retained speedups and validate their correctness preconditions. “Runs at full speed” is not a hardware-accuracy result.
- [ ] **QA-06 — Reconcile final support claims and remaining uncertainty. [V/R]**
  - Update machine/device flags, supported accessories and known limitations from the evidence above.
  - Retain explicit unresolved hardware questions. Do not call the platform fully emulated while required behavior is still a stub, a game-specific bypass or an unqualified timing approximation.

## Existing progress that must not be lost

- **User-accepted:** After Burner II boot/explosions, Power Drift cars and OutRun flashing. These are bounded gameplay acceptances, not complete VDP1/VDP2 certification.
- **Implemented video foundations:** resumable VDP1 primitives; packed framebuffer handling and progressive erase; VDP2 scroll/reduction/mosaic, window/special-function/composition paths and numerous size/cache fixes.
- **Implemented recent VDP2 change:** addressed-bank normal fetch permissions and VCSC early-slot/order checks at `812ec7a8`; full timing/contention remains open.
- **Historical linked evidence:** the earlier `c4f393c5` qualification recorded 4,352 synthetic cases and four BIOS replays. Those totals must not be presented as results for the newer fetch implementation.
- **Other existing support:** SH-2/68000/SCU DSP execution, SCU DMA, SMPC/RTC, SCSP synthesis/DSP, CD HLE, controller devices and cartridge devices exist. This report distinguishes their remaining gaps from complete absence.

## Audit sources and limitations

- **Directly inspected:** the source families named above; [VDP1 tracker](regtests/saturn/vdp1_completion.md); [VDP2 tracker](regtests/saturn/vdp2_completion.md); [official-document audit](regtests/saturn/official_specs.md); [historical worklist](saturn_worklist.md); [historical TODO inventory](saturn_todo_inventory.md).
- **Primary-reference policy:** retain the existing pinned Sega SDK/VDP documentation and emulator/FPGA provenance in the official-document audit. New component work must add precise primary-document references and hardware evidence under its existing parent before claiming closure.
- **Limit:** this is a source-and-tracker gap audit, not a fresh exhaustive hardware comparison of every SH-2 instruction, SCSP operation, accessory or game. Items marked V/R intentionally identify that missing audit rather than inventing confirmed defects.
- **Maintenance:** this file is the platform-level dependency index. The existing chip trackers retain detailed video evidence. Update status and evidence in place in both where appropriate; do not prepend another testing checkpoint to every historical document.

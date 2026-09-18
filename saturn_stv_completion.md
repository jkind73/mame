# Saturn / ST-V full-emulation completion report

- **Audit date:** 2026-09-16.
- **Implementation baseline:** `812ec7a8`, branch `arena/01a09f50-mame`. This is an audit of this checkout, not a claim about current upstream MAME.
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
- [ ] **CPU-04 — Provide safe deferred/restartable memory transactions. [M/P]**
  - The audited SH execution paths do not currently provide the memory-access replay support needed by the proposed VDP bus waits.
  - Implement or establish an equivalent correct mechanism in both interpreter and DRC: resume at a granted access without duplicating instruction side effects, writes or interrupts.
  - Preserve transaction state across scheduler boundaries and save/load; a guessed cycle subtraction followed by an immediate read is not a complete substitute.
- [ ] **DCC-01 — Complete dual-CPU synchronization and IRQ handshakes. [P/V/R]**
  - MINIT/SINIT origin rules, shared-memory ordering, FRT capture and slave H/V IRQ acknowledgement.
  - The 16-bit trigger rule and cache-through aliases are implemented; writer-origin semantics and synchronization barriers remain unresolved.
  - Reproduce historical interleave-sensitive failures with current code before attributing them to DCC. Replace title-specific quantum workarounds only when the underlying timing is fixed.

## 3. Shared memory buses and arbitration

- **Dependencies:** clock/beam contracts and CPU transaction support from stages 1–2. Device-specific grants are completed with stages 4 and 6–10.
- **Source:** CPU memory interfaces, `saturn_scu.cpp`, `saturn.cpp`, `saturn_vdp2.cpp`, sound/CD interfaces.
- [ ] **BUS-01 — Implement coherent A/B/C-bus ownership and wait states. [M/P/R]**
  - Main/slave CPU requests, SCU DMA, DSP DMA, sound-side accesses and attached devices must contend for the correct resources.
  - Model bus widths, turnaround, programmable waits, refresh effects and bridge restrictions where documented.
  - Prevent a transfer from completing merely because a host memory handler can return a value immediately.
- [ ] **BUS-02 — Integrate actual device grants and backpressure. [M/P]**
  - VDP1 command/texture/framebuffer traffic, VDP2 display/CPU traffic, sound RAM and CD FIFO/transfer readiness.
  - Connect **V2-T02** grants to CPU and SCU-DMA paths; renderer-only permission checks are not bus arbitration.
  - Handle waits crossing HBlank/VBlank, reset and changing access schedules without deadlocks or dropped requests.
- [ ] **BUS-03 — Qualify simultaneous-master ordering and persistence. [V]**
  - Verify competing requests at the same emulated timestamp, starvation/priority rules and interrupt ordering at completion.
  - Save/load while accesses are pending must preserve ownership and resume each transaction exactly once.

## 4. SCU: interrupts, timers and DMA

- **Dependencies:** stages 1–3; timing signals originate in stage 1 and peripheral IRQ wiring is finalized with their components.
- **Source:** `src/mame/sega/saturn_scu.cpp`.
- [ ] **SCU-01 — Complete interrupt delivery/acknowledgement qualification. [P/V]**
  - All source priorities/vectors, masking, retained pending state, withdrawal/reassertion, A-Bus external interrupts and SMPC PAD input.
  - Preserve the fixed masked-DMA completion/acknowledgement behavior that restored boot; old top-of-file speculation is not the current implementation contract.
  - Qualify signal-to-CPU latency and simultaneous source changes under both CPU engines.
- [ ] **SCU-02 — Complete timer edge and clock qualification. [P/V/R]**
  - Timer 0 HBlank compare/order, Timer 1 start/reload/stop and exact clock ratio, mode bits and wrap behavior.
  - Existing timer ordering/reload fixes are implemented; hardware timing and interaction with every display mode remain open.
- [ ] **SCU-03 — Complete DMA legality and transfer rules. [P/R]**
  - Direct/indirect same-bus restrictions, region-crossing behavior, address additions, byte-lane/alignment cases and documented exceptional transfers.
  - Resolve source-noted additional rules and shifted-byte behavior instead of retaining unexplained transfer hacks.
  - Retain existing count/address masks, indirect-chain fixes and implemented channel arbitration.
- [ ] **SCU-04 — Complete DMA timing and device flow control. [M/P/V]**
  - Device wait-state penalties, burst/cycle-steal behavior, priorities, preemption/stop, held external triggers and completion latency.
  - Qualify all three levels together with CPU traffic, VDP grant loss, sound streaming and CD transfers.
  - Verify forced stops/reset and save/load mid-descriptor/mid-transfer without duplicate completion IRQs.

## 5. SCU DSP

- **Dependencies:** stages 2–4, especially the shared DMA/bus contract.
- **Source:** `src/devices/cpu/scudsp/scudsp.cpp`.
- [ ] **DSP-01 — Resolve instruction/flag/control semantics. [P/V/R]**
  - Pipeline/prefetch, branches, arithmetic widths, flags and missing control flags; source comments identify guessed MVI/JMP behavior and ALU flag disagreements.
  - Integrated an explicit saved/reset delay-slot-valid flag: PC wrap FF→00 no longer treats address 00 as no pending slot. All 393,216 extracted PC/target/control combinations pass. Both historical234c and rebuilt b5caa488 reproduce five real wrapped-program failures, with seven controls passing. 89764c08 now passes all 48 real control-flow programs across JP/interpreter, JP/DRC, PAL/DRC and ST-V/DRC, plus the complete native gate; full opcode-prefetch timing is not claimed.
  - ADD/SUB/AD2/SR corrections are integrated and native-qualified in ea9a7a7c. Old8881caa1 fails118 of203 real arithmetic programs, and old ADD triggers signed-overflow UBSan. Corrected actual methods pass80,968 boundary/random/sticky/read-clear cases and seven mutants; existing DSP suites and full-TU syntax pass. Overflow-latch/32-bit ADD semantics follow convergent pinned Ymir/Mednafen with primary wording caveats documented in `saturn_pending/evidence/dsp-alu/README.md`. The negative-OR Z correction is tracked below. Full61-script local/CI batches pass (build35363539017). Expanded211-case native negative includes eight multiplier-built48-bit boundaries (90 pass/121 flag failures, zero result mismatches); actual48-bit ALU/latched-V file replay control passes on the old binary. Build35363539017/export35364567357 and the complete native consumer pass:844 arithmetic programs/four configurations, actual48-bit ALU/latched-V save replay and all earlier gates. Both provenance checks pass; evidence `saturn_pending/evidence/ea9a7a7c-live/`. This does not complete the ALU or parent.
  - RX writes through D1/MVI now refresh the cached multiplier at the existing instruction boundary (25f13c07, native-qualified). Qualified ea9a7a7c passes24 controls/fails40 new-product programs; all64 old-P observations pass. Corrected actual fetch/ALU/MVI/bus methods pass34,816 UBSan cases; full-TU syntax and parser controls pass. Build35365374912/export35366355244, full62-script local/CI batches and complete native consumer pass:256 multiplier programs/four configurations plus all earlier gates and both provenance checks. Evidence `saturn_pending/evidence/25f13c07-live/`. Reference/contract: `saturn_pending/evidence/dsp-multiplier/README.md`. Exact multiply timing and broader parallel-bus semantics remain open.
  - The documented12-bit LOP input width is now enforced at the shared destination setter (280c40e1, native-qualified). Actual methods pass991,232 width/conditional/full-countdown cases under UBSan. Qualified25f13c07 passes42 controls/fails38 real BTM/LPS counts, and active file replay reproduces65536 rather than4096 iterations. Build35366921336/export35367861840, full63-script local/CI and complete legal-port native consumer pass:320 programs/four configurations, actual active4096-iteration loop file replay, every preceding gate and both provenance checks. Evidence `saturn_pending/evidence/280c40e1-live/`. Contract: `saturn_pending/evidence/dsp-lop/README.md`; looped-instruction writes and exact timing remain open.
  - Parallel X/Y/D1 accesses now share entry CT addresses, merge increments once after D1, honor explicit CT writes, and suppress same-bank/read-bank D1 RAM writes (2e14f275, native-qualified for the selected contract). Qualified280c40e1 passes36/fails108 guest programs with all multiplier controls intact. Corrected actual methods pass729,000 UBSan transitions; build35369703506/export35370407444, full64-script local/CI and complete native consumer pass:576 programs/four configurations, active parallel-copy file replay, all earlier gates and both provenance checks. Evidence `saturn_pending/evidence/2e14f275-live/`. `saturn_pending/evidence/dsp-parallel/README.md` explicitly records Ymir/Beetle disagreements on register priority and an immediate-collision CT quirk; those are not hardware-qualified.
  - Control-port S/Z now ignore host writes, matching ST-097 p.51 and both pinned references (dacd1f99, native-qualified). The actual-method mask correction passes28672 UBSan transitions; native ff717b2e passes76/fails36 of112 masked-write programs with all guest flag controls correct. The existing pipeline fixture's invalid host Z injection is replaced by guest ALU setup plus an explicit branch-target marker; all12 revised programs pass on ff717b2e. Prior conditional-flag coverage is superseded. Full67-script local/CI, build35373461692/export35374507751 and the complete native consumer pass:448 host-flag programs/four configurations, every previous gate and both provenance checks. Native evidence: `saturn_pending/evidence/dacd1f99-live/`. Evidence: `saturn_pending/evidence/dsp-hostflags/README.md`; pause/step and other control semantics remain open.
  - ALU output now starts from entry A: NOP bypasses A and32-bit operations retain ACH rather than unrelated old ALU high bits (f8022878, native-qualified). This follows both pinned references and the documented datapath, with explicit primary-bypass wording limitations.147456 actual-method transitions pass, three mutants fail, all targeted DSP suites/full-TU syntax pass. Old dacd1f99 passes58/fails134 of192 native dataflow programs (all16 AD2 controls pass). Affected fixtures now latch operation results explicitly; old f944ce85 still passes211 ALU,64 multiplier,144 parallel cases and parallel-copy file replay, while revised ALU save replay isolates one stale poisoned-high failure. Full69-script local/CI, build35378445239/export35379200969 and the complete native consumer pass:768 dataflow programs/four configurations, revised accumulator/V replay and preceding gates/provenance checks. The old pending-slot fixture is separately corrected and passes on the same binary; see DSP-03. Native evidence: `saturn_pending/evidence/f8022878-live/`. Evidence: `saturn_pending/evidence/dsp-alu-flow/README.md`. Older output-lifetime/high-half assumptions are superseded; the negative-OR correction is tracked below; exact timings remain open.
  - Negative OR now follows ST-097 p.95 and both pinned references: S=1,Z=0,C=0 (c33fe0da, native-qualified). The existing ALU suites expand to222662 actual-method cases and438 native programs, covering every defined flag-changing operation. Old f944ce85 passes390/fails48 programs, solely negative-OR flags/read-clear (all result observations match). The host read-only test no longer expects the legacy impossible S=Z=1 preset. Full69-script local/CI, build35379801144/export35380818303 and the complete native consumer pass:1752 ALU programs/four configurations,448 corrected host-flag programs, the corrected legal paused-slot file replay and all preceding gates/provenance checks. Native evidence: `saturn_pending/evidence/c33fe0da-live/`. Evidence: `saturn_pending/evidence/dsp-logic/README.md`. The old Croc/Psygnosis comment lacks hardware evidence; those titles' compatibility remains unqualified without their media.
  - Disassembler now distinguishes MVI PC/reserved destinations from D1 TOP/CT destinations and separates parallel command text (ff717b2e, native-qualified). Actual complete decoder/interface/formatter pass337 UBSan cases; the old real MAME debugger has184 mismatches in241 rows. Build35370828718/export35371877378, full65-script local/CI and the complete native consumer pass, including all241 debugger rows, previous runtime gates and both provenance checks. Evidence: `saturn_pending/evidence/ff717b2e-live/`. This is diagnostic decoding, not a CPU register-write fix. Source/evidence: `saturn_pending/evidence/dsp-disassembler/README.md`; broader step metadata/debugger synchronization remains open.
- [ ] **DSP-02 — Complete DSP DMA and bus interaction. [M/P/R]**
  - Replace the source-noted burst-versus-cycle-steal approximation and DSP-stall substitution with correct bus/CPU acknowledgement behavior.
  - B-bus per-halfword write increments implemented for all eight modes and both count forms (ST-097 pp.134/136/138/140). A real 79f36021 binary passes only the four stride-one cases out of 32; other modes corrupt the mapped destination. Rebuilt b5caa488 now passes all 32 real DSP addressing programs and the complete native integration gate. A/C-bus quirks, program-RAM DMA and shared-bus acknowledgement remain open.
  - Read-side bus classification now matches the existing complete C-bus mirror aperture and separates B-bus from A-bus/CS2. On native 89764c08, 372/1,024 read-DMA mirror/mode programs fail despite identical CPU-visible RAM. New extracted mirror/isolation checks and 4,096 rebuilt ca63041f native cases across four configurations pass, together with the full integration consumer.
  - Program-RAM DMA's dropped selector/fatal stub is replaced by the MVI-PC serialized loader in cd074b71, integrated after read-DMA native qualification. All 32 old-binary loader tests and actual wrapped 192-word save replay reproduce the missing feature; 4,096 extracted cases plus replay, five compiled mutants and full-TU syntax pass. cd074b71 build35344168780 and the expanded native consumer pass all128 overlays across four configurations and real192-word wrapped save replay. Alternate RA0/WA0/END serialization and exact timing remain open.
  - Eight-bit counter / zero-as-256 behavior is native-qualified in f1a65715:96 count programs across four configurations and actual zero-encoded256-word data/program save replay pass with the full consumer. Earlier60,000-word replay was implementation stress, not a valid single hardware transfer. Six no-PCH include-order dependencies were repaired; full59-script local/CI batches pass. See `saturn_pending/evidence/dsp-count/README.md` for the reference limitations. The subsequent count-source selector correction in8881caa1 is also native-qualified:16 canonical controls pass/16 aliases fail before the fix,131,072 extracted cases pass after it, and all128 real operand/increment/wrap programs pass across four configurations with the full native consumer. Full60-script local/CI batches pass; no broader parent closed.
  - C-bus writes now use aligned longword placement, byte strides0/2/4/8/16/32/64/128 for both count forms, and cumulative WA0 updates preserving the saved halfword phase (f1fe8e09, native-qualified for the selected contract). Old2e14f275 passes212/fails300 of512 mapped programs; all source-counter controls match. Actual old-binary odd-phase file replay fails both completion images and continuation probes. Corrected actual methods pass6912 UBSan cases with five replay cuts; four mutants fail, existing DMA suites and full-TU syntax pass. Full66-script local/CI, build35372231634/export35373125204 and the complete expanded native consumer pass:2048 C-bus programs/four configurations, odd-phase file replay with WA0 probes, all earlier gates (including legal guest-ALU branch setup), and both provenance checks. Native evidence: `saturn_pending/evidence/f1fe8e09-live/`. Contract/evidence: `saturn_pending/evidence/dsp-cbus/README.md`. Ymir/Beetle agree on placement/stride but disagree on some final non-HOLD addresses; existing MAME/Beetle cumulative behavior is retained, not declared hardware-proven.
  - Remaining A-bus rules, disputed C-bus final-address/page effects, whole-bus-boundary behavior and transfer timing/shared grants remain open.
- [ ] **DSP-03 — Qualify execution timing and integration. [P/V]**
  - Instruction/DMA overlap, end interrupts, host access while running, debugger/DRC synchronization and save/load of pipeline state.
  - Registered the missing DMA stride/mode/direction/progress/state fields; reset now clears the private DMA HALT and T0 busy state. Extracted replay at WAIT/MOVE/completion and reset checks pass; b5caa488 historically passed a60,000-word implementation stress replay, which was subsequently retracted as a legal hardware transfer; current native acceptance uses the zero-encoded256-word transfer described under DSP-02. The earlier pending-slot file fixture read DSP data RAM while EX=1, contrary to ST-097; its claimed access legality is retracted. The corrected fixture selects via PPAF, pauses with EP, asserts EX=0 before every marker read, saves/restores the paused pending slot and resumes with PR. It passes on f944ce85 and f8022878 (JP/interpreter). Historical full-consumer output is retained, not silently replaced; `saturn_pending/evidence/dsp-pipeline/README.md` records the correction. Broader instruction/DMA overlap and bus arbitration remain open.
  - Pending control-flow slots now retain a registered32-bit fetched word rather than rereading changed program RAM; the debugger instruction hook reports the actual slot address (9b596f90, native-qualified).393216 flow cases assert retired words/addresses, plus1280 mutation/replay cases; eight compiled mutants are rejected. Existing pipeline/native save/debugger fixtures expand without new parent IDs:27 programs (108/four configurations), cached-word file replay,241 static debugger rows and the live FF→00→10 trace. Old c33fe0da passes12 controls/fails15 word observations and both save markers; qualified1ee15ef8 reproduces the incorrect FF→10→10 trace. Source/tests were reconstructed after workspace recovery; the interrupted full local batch's result is unknown. Fresh69-script local/CI, build35385651294/export35386786221 and the complete native consumer pass:108 pipeline programs/four configurations, actual cached-word replay,241 static debugger rows and correct FF→00→10 trace, all previous gates and provenance/BIOS checks. Native evidence: `saturn_pending/evidence/9b596f90-live/`. Contract: `saturn_pending/evidence/dsp-slot-latch/README.md`. Ordinary prefetch, ES, LPS timing, PC readback and full debugger/DRC synchronization remain open.
  - LE is now a masked strobe accepted only when stopped/paused on entry, allowing stopped load-and-start while rejecting active loads; accepted loads discard the old pending slot (1ee15ef8, native-qualified). Primary p.52/Ymir support the guard; Beetle lacks it, while both references clear the prefetched instruction. The existing host-control model expands to262144 cases with four rejected mutants. The existing pause suite expands to20 programs: old f8022878 passes10/fails10, with four active-load and six old-slot failures; all prior pause/DMA and stopped-start controls pass. Targeted suites/full-TU syntax pass; full69-script local/CI, build35381311374/export35382269649 and the complete native consumer pass:80 expanded programs/four configurations and all preceding runtime/save/provenance gates. The full consumer was repeated after workspace recovery. Evidence: `saturn_pending/evidence/1ee15ef8-live/`. Evidence: `saturn_pending/evidence/dsp-pc-load/README.md`. This is not a full prefetch, ES, loop-pipeline or hardware PC-edge completion.
  - EP/PR pause/resume is native-qualified in f944ce85, with independent saved pause and DMA-stall latches, masked command strobes, EX readback while paused and reset cleanup.4480 actual-method cases plus four resume-during-DMA compositions pass; five mutants fail. Qualified f1fe8e09 reproduces16 control failures across six native scenarios and four paused-DMA file-replay failures, with C-bus images and WA0 probes intact. The full68-script local batch passes; checkpoint f944ce85 is now pushed and remote-verified after authentication was restored. Build35376996618/export35377759991 and the complete expanded native consumer pass:24 programs/four configurations, paused odd-phase file replay, all preceding gates and both provenance checks. Native evidence: `saturn_pending/evidence/f944ce85-live/`. Contract/evidence: `saturn_pending/evidence/dsp-pause/README.md`. ES, exact pause edges/prefetch, whole-host-stop semantics and shared grants remain open.
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
  - Multi-page transport and partial-report file save/load pass live on 234c7abc. Integrated VBlank timeout plus initialized/reset/save-registered H/V edge history after live negative reproduction; native 2781 timeout/edge-save positives pass. Physical slot addressing/FF-empty ports and VBlank-sampled RESB now pass the expanded 79f36021 live gate, including both tap types, empty root ports and real sampled-RESB save/load. Extended-size IDs, OPE and wire timing remain open.
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
  - Current integration: Integrated timer phase-preserving rearm and attotime-boundary fix; extracted deadline/reset checks and the live24 timer/divisor plus three clear/reassert paths pass in the complete native consumer. Fractional hardware phase and broader sound acceptance remain open. See `regtests/saturn/handoff/integration.md`.
  - Interrupt command-port correction6aa9e3d8 is native-qualified: distinguish MCIPD42c from MCIRE42e and acknowledge only active bus lanes, without replaying stale clear commands.851968 extracted acknowledgement plus114688 pending-port cases, seven compiled mutants and14 parser controls pass. Old35f5d58b native passes161/fails271 of432 SH-2/68000 mapped cases seeded by actual timers/DMA/MIDI-output/CPU/sample events. Full71-script local/CI, build35398923424/export35399526933 and the complete native consumer PASS:1728 IRQ cases/four profiles, real pending-IRQ file replay, previous3036 DSP programs/effect-address replay and preceding runtime/save/BIOS/provenance gates; evidence `saturn_pending/evidence/scsp-irq-ports/README.md`.
  - MIDI byte-lane/read-side-effect correction2f54b074 has native output and method-level input qualification: high-byte/debugger reads and write merging no longer consume input; read-only input/status writes are ignored; only low-byte output writes transmit.2176 new method cases and twelve mutants pass; old6aa9e3d8 passes1024/fails512 of1536 mapped output cases. Full71-script local/CI, build35400396608/export35401015382 and complete native consumer PASS:6144 output cases/four profiles and all preceding IRQ/DSP/save/BIOS/provenance gates. RX pin sampling, wire bytes and four-byte FIFO/status fidelity remain unqualified. Evidence: `saturn_pending/evidence/scsp-midi-access/README.md`.
  - DMA self-target safety53f73010 is native-qualified as an emulator safety policy: ignore writes to the DMA control registers, preventing recursive DEXE and keeping cached parameters consistent with visible registers. Primary p.101 explicitly forbids these accesses; this is emulator safety policy, not hardware fidelity or a proven cause of the reported host crash.74 actual-method cases and17 mutants pass; old2f54b074 passes32 ordinary native controls and fails8 safe cached-parameter cases. Full71-script local/CI, build35402288912/export35402954230 and complete native consumer PASS:192 DMA cases/four profiles, actual completed-transfer parameter save/replay, all preceding MIDI/IRQ/DSP/file-replay/BIOS/provenance gates. Evidence: `saturn_pending/evidence/scsp-dma-safety/README.md`.
  - SCSP DMA transfer behavior, timer rates, sound/main IRQ interfaces, MIDI paths and sound-memory arbitration under streaming load.
  - Retain the corrected SCSP clock/sample relationship; audit transfer timing separately from synthesis rate.
- [ ] **SND-04 — Qualify SCSP DSP and final mixer. [V/R]**
  - Instruction arithmetic, saturation/rounding, packed memory formats, delay/ring addressing, external inputs, stereo routing and gain.
  - SCSP Step now executes all128 microinstructions per sample rather than truncating at the last nonzero word (9baba980, native-qualified). Zero words still update MAC/input state and drain reads; live program writes beyond a cached endpoint must execute. Primary ST-077 p.11 and pinned Beetle support128 steps; Ymir instead updates its bound on every write and includes an extra zero step for side effects.6531 actual-method cases/stopped control pass; five compiled mutants fail. Native9b596f90 passes10/fails21 of31 public-register programs, with all memory/zero/full-length controls intact. The default suite adds one generic SCSP DSP script (70 total); full70-script local/CI, build35388269809/export35389080640 and the complete native consumer pass:124 programs/four configurations, actual effect/late-read file replay, all preceding gates and provenance/BIOS checks. Native evidence: `saturn_pending/evidence/9baba980-live/`. Evidence: `saturn_pending/evidence/scsp-dsp-tail/README.md`. No waveform, game-performance or full DSP timing/save closure is claimed.
  - Signed ADREB correction66e351f7 is native-qualified: add the signed twelve-bit ADRS_REG displacement before TABLE/ring masking. Pinned MiSTer/Ymir/Beetle agree; primary register documentation does not explicitly establish this microinstruction rule.69632 additional actual-method address/latch/read-write cases pass, four address mutants are rejected, and previous native9baba980 passes199/fails48 of247 mapped programs (the original31 all pass). Full70-script local/CI, build35391990957/export35393028889 and the complete native consumer pass:988 SCSP programs/four profiles plus actual saved signed-address latch replay before next-sample refresh, all preceding gates and provenance checks. No full DSP or sound closure; see `saturn_pending/evidence/scsp-dsp-address/README.md`.
  - MEMS input/write ordering correction35f5d58b is native-qualified: remove same-instruction IWT bypass, retaining entry INPUTS for MAC/YRL/ADRL and exposing the committed value to subsequent instructions.73728 new actual-method cases and eleven mutants pass; old native66e351f7 passes631/fails128 of759 mapped programs with all previous247 intact. Full70-script local/CI, build35393858442/export35395365686 and the complete native consumer pass:3036 programs/four profiles, actual effect/late-read/signed-address file replay, preceding runtime/save gates and source/binary/BIOS provenance checks. Broader sound and hardware timing remain open. Evidence: `saturn_pending/evidence/scsp-dsp-input/README.md`.
  - Check audio output against deterministic hardware captures, including CD-DA and effects-heavy playback.
- [ ] **SND-05 — Qualify sound state continuity. [V]**
  - Current integration: Timer origins now save and restore without losing fractional phase; extracted restore checks pass, real save-manager/audio replay pending. See `regtests/saturn/handoff/integration.md`.
  - Actual SCSP effect/read-pipeline file replay is now a consumer gate: mapped RAM/EFREG/MEMS observations must reproduce the first changed sample after restoring COEF/MPRO/RAM and a step127 read, with intervening guest-program poisoning. Qualified9b596f90 passes the full-length-program control; rebuilt9baba980 also passes the actual replay with the complete consumer. This tests digital effect/read-state continuity, not analog waveforms, audio-buffer continuity, pending writes or all DSP state. Evidence: `saturn_pending/evidence/scsp-dsp-tail/README.md`.
  - Pending IRQ state and byte-command replay are native-qualified at6aa9e3d8: actual save/mutate/load restores both pending banks, and replayed low-byte acknowledgements preserve unrelated DMA/CPU/sample requests. This does not qualify in-flight DMA timing, timer fractional phase or audio-buffer continuity. Evidence: `saturn_pending/evidence/scsp-irq-ports/README.md`.
  - Completed-transfer DMA parameter save/replay passes at53f73010, including address reuse after forbidden self-target writes and intervening parameter/RAM/coefficient poisoning. This qualifies the safe emulator policy and parameter persistence, not in-flight DMA timing. Evidence: `saturn_pending/evidence/scsp-dma-safety/README.md`.
  - Save/load during envelopes, DMA, DSP delay lines, interrupt handshakes and CD audio; no lost/duplicated IRQs or discontinuities caused by unsaved state.

## 8. VDP1: drawing engine and framebuffer

- **Dependencies:** stages 1–4; final scanout/effects additionally require stage 9.
- **Canonical detail:** [VDP1 completion tracker](regtests/saturn/vdp1_completion.md), especially “Remaining implementation and acceptance gates.” Source: `src/mame/sega/saturn.cpp`.
- [ ] **V1-01 — Complete command/pixel pipeline timing and arbitration. [M/P/R]**
  - Current primitives have resumable bounded cursors and nominal fetch/pixel scheduling. Missing: calibrated command/texture/pixel costs, real VRAM/framebuffer contention and transfer-over behavior.
  - Qualify ENDR termination and actual draw-end interrupt latency rather than introducing game-specific delays.
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
  - Current integration: Inspection reads now avoid HIRQ mutation/IRQ callbacks; CPU read behavior retained. Extracted debugger/CPU matrix passes; linked acceptance pending. See `regtests/saturn/handoff/integration.md`.
  - Current integration: DCHG read/ack correction is now an implementation WIP; extracted read/ack and old-behavior negative tests pass, live tray/boot acceptance pending. See `regtests/saturn/handoff/integration.md`.
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
  - Current integration: Reviewed empty-DRAM guards and backup-RAM write-count checking are now an implementation WIP; extracted tests pass, linked acceptance pending. See `regtests/saturn/handoff/integration.md`.
  - Existing ROM, DRAM and backup-RAM cartridge devices need complete capacity/bank/address/lane and persistence qualification for supported variants.
  - Handle identification, empty-slot/open-bus reads, write protection and mapping conflicts without cartridge-specific shortcuts.
- [ ] **NVR-01 — Complete persistent-state and machine-variant behavior. [P/V/R]**
  - Current integration: Internal console backup RAM now registers for save states; persistence and save/mutate/load fixture prepared, live acceptance pending. See `regtests/saturn/handoff/integration.md`.
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
  - Current integration: Legacy IOGA inspection now preserves the counter cursor; 5,124 extracted cases pass, cabinet acceptance remains open. See `regtests/saturn/handoff/integration.md`.
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
- [ ] **QA-01 — Complete fresh linked builds and aggregate validation. [V]**
  - Run focused Saturn/ST-V builds, MAME `-validate`, all existing regression subsets together, and linked mapped-register/background/composition tests with exact source/binary provenance.
  - Fresh native build, MAME `-validate`, and the ROM-free regression batch passed in [CI run 35287467065](https://github.com/jkind73/mame/actions/runs/35287467065), source `5008a92331e4bf6698b7a9e53116c2167ddcc673` (Ubuntu 22.04/GCC 12). Receipt: `saturn_pending/ci-35287467065.json`.
  - User-transferred artifact verified and live baseline passed: CD/cart/backup RAM, 24 SCSP timer/divisor combinations, and four BIOS/background replay configurations. See `saturn_pending/evidence/5008-live/`. ST-V showed its no-cartridge BIOS error screen, not game boot.
  - The rebuilt 234c7abc transport passes six live packet cases and partial-report file save/load; its full runtime consumer passes. The 5008a923 composition baseline now passes all four configurations (4,168 cases). The next timeout/edge-history revision awaits native qualification; QA-01 stays open for this and real software.
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

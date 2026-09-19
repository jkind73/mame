# Three-agent Saturn / ST-V implementation assignment

Use each prompt below in a separate agent session with an isolated writable checkout. Start all three from the same recorded baseline containing `saturn_stv_completion.md`. Each agent must use its own platform-assigned branch; never have multiple agents edit the same writable checkout or change another session's branch.

These are three balanced workstreams, not a claim that hardware effort can be divided into exactly equal thirds. They can develop independently against explicit interfaces, but cannot independently certify the complete machine. A fourth agent owns final reconciliation, real cross-component integration and whole-system acceptance.

Each prompt is self-contained. Copy its fenced text into the corresponding session.

## Prompt 1 — Core execution, clocks, buses, SCU/DSP and SMPC

```text
You are implementation agent A for the Saturn/ST-V completion project in this MAME fork. You own the shared execution and timing foundations, not merely an audit or a collection of tests.

MISSION
Complete your assigned implementation and its validation autonomously. Do not stop after a feature subset, a passing unit test, a commit, a push or a progress report. Those are checkpoints, not completion. Continue to the next remaining assigned parent without asking for routine permission. Do not expand the project with endless test-only milestone IDs.

Read saturn_stv_completion.md, regtests/saturn/official_specs.md, the VDP1/VDP2 completion trackers, and applicable source. Treat current code as authoritative; dated notes can be stale. Record your starting commit and branch. Use only your platform-assigned branch and isolated checkout; do not switch/create branches or edit another agent's workspace. Follow the environment's git/authentication rules.

OWNERSHIP
You own these existing parent IDs:
- SYS-01, SYS-02, SYS-03: platform specification/evidence contracts, with component evidence supplied by the other agents. Do not block implementation waiting for a globally finished ledger.
- SYS-CLK01 and SYS-MEM01: system clock/reset coordination, motherboard address decoding, bus-value behavior and physical/cache-through aliases.
- CPU-01 through CPU-04 and DCC-01: both SH-2 execution modes, SH7604 peripherals/cache/bus controller, safe deferred/restartable accesses, dual-CPU synchronization and interrupts.
- BUS-01 through BUS-03: A/B/C-bus request/grant, wait states, priorities, competing-master ordering and saved pending transactions.
- SCU-01 through SCU-04: interrupts, timers, DMA legality, timing, stop/preemption and flow control.
- DSP-01 through DSP-03: SCU DSP instruction/control behavior, DMA, pipeline/timing and integration.
- SMPC-01 through SMPC-04: command timing, reset/control, RTC/settings and peripheral transport/event routing.
You also own the core share of QA-01, QA-02 and QA-05. The fourth agent owns final whole-platform QA closure.

BOUNDARIES
Agent B owns VDP1/VDP2, beam/counter timing, video fetch/erase/readout and external-video composition. You own clock distribution and bus arbitration; B supplies video demand and timing signals.
Agent C owns sound, CD, controllers/cartridges, persistence integration, ST-V boards and optional expansion devices. You own SMPC transport and the shared CPU/bus mechanisms; C supplies device protocols and endpoints.
Likely primary files are src/devices/cpu/sh/*, src/devices/cpu/scudsp/*, src/mame/sega/saturn_scu.*, saturn_dcc.* and smpc.*. Driver/wiring changes may touch shared files: keep them minimal and in separate integration commits. Do not replace whole saturn.cpp, saturn.h, sat_console.cpp or stv.cpp files from another agent's work.

EXECUTION ORDER
1. Verify the actual remaining gaps and write precise clock/reset/memory transaction contracts.
2. Implement correct SH-2 deferred/restartable transactions in interpreter and DRC, including side-effect-once and save/load semantics.
3. Implement shared arbitration and device backpressure with explicit request/grant/completion ordering.
4. Complete SCU DMA/interrupt/timer and DSP behavior against that model.
5. Complete DCC/SMPC/peripheral-clock integration and remaining assigned CPU semantics.
6. Run all assigned parent subsets together, then full existing regressions and relevant linked/runtime/save tests. Fix failures; do not stop at the first passing subset.
This is dependency order, not permission to postpone legal instruction fixes or independent work while another interface is being developed.

INTERFACE CONTRACT
Create regtests/saturn/handoff/core.md early and maintain it in place. Publish exact proposed API signatures and include:
- time units and clock conversion;
- master/resource identities, address/width/byte enables;
- side-effect-free readiness versus committed access;
- ownership of reads/writes and completion;
- arbitration priority, wait/retry/cancel/reset semantics;
- IRQ/event ordering and serialized pending state.
Use devices/delegates consistent with MAME. Do not use host sleeps, game-name tests, unconditional guessed delays or immediate memory operations disguised as waits.
Develop against the baseline with real available endpoints. Where another agent's implementation is not yet present, test the contract with explicitly identified fixtures, but do not count fixtures or permissive stubs as production integration. Deliver concrete integration patches and list unexercised endpoints.

QUALITY AND TRUTHFULNESS
Use Sega/Hitachi/Yamaha primary documents first, then hardware evidence and pinned emulator/FPGA cross-checks. Resolve disagreements; do not wholesale merge another emulator. Do not turn every old TODO into a claimed current defect.
Preserve accepted AB2 boot/explosions, Power Drift cars and OutRun flashing fixes, including prior DMA acknowledgement, delay-slot IRQ and sound-reset corrections.
Missing bus mechanisms are implementation gaps, not “just verification.” Conversely, unverified existing behavior must not be called absent without inspecting it.
Test instruction side effects, competing masters, live mode/reset changes and actual in-flight save/load. Extracted tests alone do not certify hardware or integrated correctness.

AUTONOMY AND STOP CONDITION
Keep implementing until every owned parent is implemented and validated to its stated scope. Use commits/pushes as frequent recoverable backups; exclude SDKs, ROMs, caches, build output and unrelated user logs. Run syntax/build checks before commits; push only your assigned branch; maintain its PR if applicable.
If a test or build fails, investigate and repair it. If one item requires unavailable evidence, continue all other actionable owned work and explicitly identify the unresolved behavior. Never invent hardware results, mark an unavailable test passed, or claim an unresolved parent complete.
If an external dependency, unavailable hardware/firmware, access failure or execution limit truly prevents further work, preserve and push the work and report BLOCKED, not DONE. Do not ask for routine authorization to continue; ask only for indispensable missing access/input. Do not promise invisible work after the session ends.

HANDOFF TO AGENT FOUR
Your final handoff must contain:
- exact baseline, final commit, branch and ordered commit list;
- owned-ID implementation/verification status, with evidence and genuine blockers;
- API contract and minimal shared-file/integration patches;
- exact build/test commands, source/binary hashes and results;
- reset/save-state schema changes and backward-compatibility implications;
- performance measurements where applicable, risks and tests not executed;
- the precise remaining cross-agent integration tasks.
Update existing progress entries in place. Do not mark whole Saturn/ST-V emulation complete; agent four must integrate the real video/audio/CD endpoints and perform whole-system acceptance.
```

## Prompt 2 — VDP1, VDP2 and the complete video path

```text
You are implementation agent B for the Saturn/ST-V completion project in this MAME fork. You own VDP1 and VDP2 end to end. Your assignment is to finish the hardware implementation, not merely add rendering examples or qualification milestones.

MISSION
Work autonomously through all owned parents without stopping after a subset, a test batch, a commit or a progress report. Checkpoints are backups, not endpoints. Do not ask permission to move to the next item. Do not repeatedly add test-only bullets instead of completing the existing implementation bullets.

Read saturn_stv_completion.md, regtests/saturn/vdp1_completion.md, regtests/saturn/vdp2_completion.md, regtests/saturn/official_specs.md and the actual source. Record your baseline and assigned branch. Work only in your isolated checkout and platform-assigned branch; do not switch/create branches or edit another agent's workspace. Respect environment git/authentication rules.

IMPORTANT HISTORICAL CORRECTION
Previous work implemented substantial VDP1 rendering and passed specific game tests, but full VDP1 was NOT completed. Hardware-faithful drawing costs and VRAM/framebuffer arbitration, within-raster erase/readout contention and latch timing remain real implementation work.
VDP2 addressed-bank normal PN/CP permissions and VCSC early-slot/order gating exist at implementation baseline 812ec7a8. They are NOT PN/CP bandwidth scheduling, hardware fetch latches or CPU/SCU-DMA arbitration. Transparent/zero-offset denial fallbacks are not established hardware stale-latch behavior.
Do not repeat the earlier mistake of describing these gaps as “only verification.”

OWNERSHIP
You own:
- V1-01 through V1-06: command/pixel pipeline, texture/VRAM/framebuffer arbitration, erase/swap/latches, legal rasterization and texture/color behavior, all framebuffer/readout modes, undocumented behavior needed by software, and live save/reset correctness.
- Every open VDP2 parent: V2-A03/A04/A05; V2-T01/T02/T03; V2-S01/S02; V2-R01/R02/R03/R04; V2-C01 through C08; V2-H01 through H04; V2-Q01/Q03/Q04/Q05/Q06.
- Video-related portions of QA-01, QA-02 and QA-05. Final platform acceptance belongs to agent four.
Use the existing IDs; do not manufacture another suffix for each test run.

BOUNDARIES
Agent A owns SH-2/DCC, shared bus arbitration, SCU/DSP, system clock/reset coordination and SMPC. You own video beam/counter timing and video requests/grants/latches. Coordinate their interfaces, not their entire implementation.
Agent C owns sound/CD/peripherals/ST-V boards and optional MPEG decoder hardware. You own the external-video input/compositor side of V2-H04; C supplies timed pixels/sync from a real device implementation.
Primary files include src/mame/sega/saturn.cpp, saturn.h and saturn_vdp2.*. Keep non-video changes minimal. Separate driver/wiring/API adaptations into integration commits so agent four can merge shared files without losing another agent's work.

EXECUTION ORDER
1. Reconcile the register/memory/clock/beam contracts and the actual implemented paths.
2. Complete video-local command/fetch/erase/readout timing and integrate explicit shared-bus transactions.
3. Complete VDP1 remaining pipeline, framebuffer/latch and readout behavior; finish its owned validation rather than postponing it behind VDP2 visual tests.
4. Complete VDP2 slot counts/order/bandwidth, fetch latches, CPU/DMA availability and raster-write boundaries.
5. Complete scroll/reduction/line/cell combinations, rotation precision/coefficient permissions, selection/read control and RBG1 sharing.
6. Complete per-pixel identity, all windows, shadows, special/ordinary/extended/gradation calculation, line color, mosaic and external input.
7. Qualify all display modes, live reset/save/load and performance, then current game regressions.
Independent fixes may proceed in parallel, but do not declare downstream effects complete using an unimplemented fetch model.

INTERFACE CONTRACT
Create regtests/saturn/handoff/video.md early and maintain it in place. Specify exact APIs and:
- beam/clock units, field/mode changes and blanking events;
- video resource requests, slot grants and CPU/DMA access completion;
- when PN/CP/coefficient/table data is latched and consumed;
- framebuffer ownership and drawing/erase/readout ordering;
- pixel/coverage/priority metadata and timed external-video input;
- reset, pending-event cancellation and save-state ownership.
Use real production consumers. Where another agent's bus/decoder implementation is absent, build explicit contract fixtures and integration patches, but label that boundary unintegrated. Never treat permissive stubs as a finished bus or external-video device. Do not implement a second incompatible global arbiter.

EVIDENCE AND VALIDATION
Use Sega primary documents first, hardware measurements/test programs where required, and pinned MiSTer/Ymir or other accurate cross-checks. Resolve arithmetic and table/figure disagreements explicitly. Do not invent undocumented results or copy another emulator wholesale.
Preserve user-accepted After Burner II boot/explosions, Power Drift cars and OutRun flashing fixes. The separate title/logo placement report is unresolved and has no preassigned culprit chip.
Run each parent's subsets together. Include real mapped-register rendering, all relevant formats/layers/modes, partial versus full updates, live writes, actual CPU/DMA contention, save/load mid-operation and negative tests that prove changed logic is exercised.
A constant-color identity rotation image cannot prove rotation precision. An injected framebuffer cannot prove VDP1 drawing timing. Extracted helper tests cannot prove complete linked behavior. Old linked totals do not validate your changed binary.
Profile before optimizing; keep fidelity when changing samplers/caches. No game-specific rendering or delay hacks.

AUTONOMY AND STOP CONDITION
Continue until all owned implementation and validation gates are satisfied, not until a visually attractive subset works. Commit/push recoverable checkpoints after appropriate syntax/build checks, only to your assigned branch; maintain its PR if applicable. Exclude downloaded SDKs/ROMs, build artifacts and unrelated user logs.
Fix failures and continue. If hardware evidence or another endpoint is unavailable, complete every other actionable item and state precisely which behavior remains unresolved. Do not claim full VDP1/VDP2 completion with missing arbitration/latches or unintegrated device boundaries.
If genuinely blocked by missing access/evidence or an execution limit, preserve/push the work and report BLOCKED, not DONE. Ask only for indispensable access/input, not routine authorization. Do not promise invisible work after the session ends.

HANDOFF TO AGENT FOUR
Maintain regtests/saturn/handoff/video.md with baseline/final commits and ordered patches, per-ID implementation/verification status, exact API contract, shared-file integration patches, save/reset schema changes, build/test commands and hashes, hardware/reference evidence, performance results, unexecuted tests and genuine blockers.
Provide the minimal steps and acceptance tests for integrating agent A's real arbiter and agent C's real external-video endpoint. Agent four owns final cross-component acceptance; your handoff must not disguise fixtures or approximations as completed production interfaces.
```

## Prompt 3 — Sound, CD, peripherals, cartridges, ST-V boards and expansions

```text
You are implementation agent C for the Saturn/ST-V completion project in this MAME fork. You own sound, storage/media, peripheral devices, ST-V board hardware and optional expansion devices. Your goal is complete device behavior and validated integration—not game-specific error bypasses.

MISSION
Proceed autonomously through the whole assignment. Do not stop after one device, one passing fixture, a commit/push or a status report. Those are checkpoints, not completion. Continue to the next remaining owned parent without routine permission. Implement missing behavior rather than adding endless testing milestone IDs.

Read saturn_stv_completion.md, regtests/saturn/official_specs.md, relevant existing trackers and source. Record your starting commit and branch. Use only your platform-assigned branch and isolated writable checkout; never switch/create branches or edit another session's workspace. Follow environment git/authentication rules.

OWNERSHIP
You own:
- SND-01 through SND-05: 68EC000 integration, SCSP voices/DSP/mixer, sound DMA/timers/IRQs/MIDI, external audio and live state continuity.
- CD-01 through CD-05: host commands/status/buffers, drive/media timing, hardware-faithful CD block, authentication/CD-DA and save/reset.
- IO-01/IO-02, CART-01 and NVR-01: real controller protocols, cartridge variants, persistent storage integration and communication device inventory/implementation.
- STV-01 through STV-06: board/BIOS/cart wiring, protection/decompression, IOGA/EEPROM/outputs, specialty inputs, serial devices, auxiliary boards and per-configuration acceptance.
- EXP-01 and EXP-02: MPEG/Video CD board and optional communication-device implementation/acceptance.
- Device-related portions of QA-01 through QA-05, including local Saturn software and ST-V cabinet checks. Final whole-platform QA closure belongs to agent four.
Supply your component register/evidence ledger to agent A without waiting for a global ledger to be finished.

BOUNDARIES
Agent A owns SH-2/DCC, global bus arbitration, SCU/DSP and SMPC command/transport/RTC core. You own attached device protocols, sound/CD transaction endpoints and storage/driver integration. Coordinate SMPC transport versus controller semantics explicitly.
Agent B owns VDP1/VDP2, beam latches and V2-H04 external-video composition. You own decoder/expansion hardware producing timed pixels/sync/audio; publish the endpoint contract.
Likely files include src/devices/sound/scsp.*, scspdsp.*, src/mame/sega/saturn_cd_hle.*, saturn_cdb.*, src/devices/bus/sat_ctrl/*, src/devices/bus/saturn/*, ST-V I/O/protection devices and relevant driver wiring. Changes to saturn.h, sat_console.cpp, stv.cpp or other shared files must be minimal, explicitly scoped and separated into integration commits.

EXECUTION ORDER
1. Inventory the actual devices/configurations and their documented interfaces. Existing SCSP, CD HLE, controllers, carts and security devices are not all missing; identify concrete gaps.
2. Complete sound CPU/memory/control and SCSP timing/DMA/IRQ integration, then voice/DSP arithmetic and audio qualification.
3. Complete CD host state transitions, transfer/backpressure and drive timing. Implement the hardware interfaces required to run the currently disabled CD-block firmware CPU; merely enabling it is insufficient.
4. Complete standard controller/cart/persistence behavior, then specialized protocols and device-event routing.
5. Complete ST-V security, I/O, serial/auxiliary boards and cabinet outputs. Implement required hardware handshakes rather than bypassing door/jam/attendant errors.
6. Complete optional decoder/communication boards and connect their defined video/audio endpoints.
7. Run all owned parent subsets together, actual device/software/cabinet checks, streaming stress, live reset/save/load and performance measurements.
Base ST-V cartridge work does not need to wait for Saturn CD firmware completion. Optional expansions block only configurations that require them.

INTERFACE CONTRACT
Create regtests/saturn/handoff/devices.md early and maintain it in place. Specify exact APIs and:
- device clocks/reset and command/IRQ timing;
- memory access widths, byte lanes, bus readiness and transfer completion;
- FIFO/DMA backpressure and cancellation;
- controller packet/event transport and beam-latch requests;
- persistent storage ownership and power/reset semantics;
- external-video pixels/sync, audio timing and expansion slot wiring;
- save/load state for in-flight operations and external connections.
Use existing MAME device conventions. Develop concrete production endpoints plus explicit fixtures where another agent's arbiter/compositor is unavailable. Such fixtures validate contracts only; list the missing integration and provide minimal wiring patches. Do not invent another global bus scheduler or call a fake decoder frame real MPEG support.

EVIDENCE AND VALIDATION
Use Sega/Hitachi/Yamaha documents and actual board/media evidence first, then pinned independent implementations. Audit historical comments and protection bypasses against current source. Do not wholesale merge another emulator or add game-name conditionals to suppress symptoms.
Preserve existing correct sound clocking, sound reset and sound-RAM mapping, plus accepted AB2/Power Drift/OutRun behavior. Do not change shared CPU timing to mask a device handshake defect.
Verify deterministic audio, command/status sequences, FIFO limits, abort/reset/error paths, concurrent streaming, physical storage restart and save/load mid-operation. Distinguish MAME save state from battery-backed storage.
Test supported controller and cabinet configurations, including service/maintenance behavior. A game reaching attract mode does not prove its dispenser, link or auxiliary CPU is emulated.
The CD HLE may satisfy a bounded compatibility target, but it is not proof of a running SH-1/CD-controller subsystem. Likewise, an MPEG command response is not a decoder board.
Do not treat every historical TODO, undumped component or untested accessory as a confirmed current failure. Label missing, partial, unverified and research-required work accurately.

AUTONOMY AND STOP CONDITION
Continue through all actionable owned work until implementation and stated validation gates are met. Use syntax/build-checked commits and pushes as frequent backups on your assigned branch; maintain its PR if applicable. Exclude ROMs, downloads, SDKs, caches, build output and unrelated user logs.
If unavailable firmware/hardware/access or another agent's interface blocks an item, investigate available evidence, finish other actionable parents and preserve an exact blocker. Do not fabricate dumps/results or mark an unavailable test passed.
Only stop short of completion for a genuine external blocker or execution limit, with work preserved/pushed and status BLOCKED rather than DONE. Ask only for indispensable missing access/input, not routine permission. Do not promise invisible work after the session ends.

HANDOFF TO AGENT FOUR
Maintain regtests/saturn/handoff/devices.md with exact baseline/final commits, ordered patches, per-ID status, primary/reference evidence, API contracts, minimal driver/wiring changes, device/ROM requirements, reset/save-state schema changes, build/test commands and binary hashes, performance results, unexecuted tests and blockers.
List every endpoint awaiting agent A's real bus/SMPC wiring or agent B's external-video/latch wiring, with concrete acceptance tests. The fourth agent must integrate and qualify the whole system; do not claim full Saturn/ST-V completion from your isolated device results.
```

## Contract for the fourth agent's collection phase

- Collect all three handoff manifests and exact commit ranges; do not copy whole trees over one another.
- Reconcile interface contracts first, then merge core mechanisms, real device/video endpoints and minimal driver wiring. Inspect shared-file conflicts semantically rather than choosing one side wholesale.
- Replace contract fixtures/stubs with real production connections. Resolve request/grant, clock, IRQ, ownership and save-state mismatches.
- Own QA-01 through QA-06 across the integrated source, including full build/regressions, current linked rendering/audio/media tests, live save/reset, actual game/cabinet coverage and performance.
- Reject unsupported completion claims. An agent handoff can be complete as a delivery while its subsystem is still BLOCKED; do not silently convert that into full emulation.
- Update the existing platform/chip parent entries in place and publish the integrated commit, exact evidence and remaining hardware uncertainty.
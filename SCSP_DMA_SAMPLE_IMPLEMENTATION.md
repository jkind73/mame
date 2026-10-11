# SCSP DMA wait states and 1Fs interrupt — 2026-10-10

The requested DMA/sample-interrupt implementation is in place. SCSP DMA is now an asynchronous, saved-state-aware device timer rather than an immediate block copy. DMA contention reaches Saturn and ST-V's 68000, both SH-2 bus timing paths, ordinary SCU DMA, and SCU DSP DMA. The existing per-sample interrupt was verified and its polling/clear behavior was made independent of whether a sound-CPU IRQ callback is connected.

No physical Saturn was used to validate this implementation. Bus-grant edges and absolute DMA throughput are modeled, not hardware-measured.

## References and timing model

Sega SCSP User's Manual ST-77, sections 3.2, 4.2.12 and 4.2.13, specifies 128 memory cycles per 512-clock sample, two refresh cycles, PCM/DSP priority above built-in DMA, and both CPUs below DMA. It specifies one 1Fs event per sample, independent pending latches and enables, automatic DEXE clearing on completion, increasing word addresses, and prohibition of DMA access to its own controller registers.

Local references: `segahtml/hard/scsp/hon/p03_10.htm`, `p04_2c.htm`, `p04_2d.htm`.

[MiSTer's SCSP.sv](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a23bbb22c8c9a43926ee2196875e257d225291b7/rtl/Saturn/SCSP/SCSP.sv), pinned at `a23bbb22c8c9a43926ee2196875e257d225291b7`, separates register and memory handshakes, alternates PCM/DSP memory opportunities, protects DMA parameter writes while active, and uses an 11-bit word counter. Ymir's current implementation still executes its whole DMA block synchronously and does not establish transfer timing.

Each DMA word now has separate source and destination phases on a four-chip-clock grid. Memory phases yield to active PCM slots, DSP memory operations and two refresh reservations per sample. PCM/DSP phase allocation follows the FPGA implementation; refresh reservations are evenly spaced at cycles 0 and 64 as a model choice. The original chip's exact refresh/grant positions and pipeline offsets have not been measured. This is not a claim of electrical or cycle-exact hardware validation.

The host waits for a conflicting DMA phase; the other SCSP bus remains accessible. At a scheduler tie, DMA has priority rather than receiving a zero-duration grant. The 68000 delay rounds up to a CPU clock and preserves its existing base cost. SH-2, SCU and SCU DSP accesses retain their existing base costs and add the SCSP contention wait. DSP calculations preserve ordinary SCU accumulators.

## Transfer and interrupt behavior

* DEXE remains set while the transfer is active; the payload moves over scheduled phases. Only the final destination acknowledgement clears DEXE and sets both CPUs' DMA-completion pending bits.
* Both transfer directions and DGATE zero-fill work. Zero-fill does not read or disturb the source. DMA writes cannot change its own controller registers, and CPU parameter writes cannot restart or abort an active transfer.
* Working addresses advance internally; a subsequent DEXE reloads the original register parameters instead of inadvertently continuing from the previous block's final address. The 11-bit counter's zero encoding wraps to 2048 words, following MiSTer; software must obey Sega's documented register-area bounds.
* The active flag, remaining count, source/destination phase and latched data are saved. Reset cancels the timer; clock changes reschedule an active phase at the new clock.
* 1Fs remains free running at chip clock/512, with separate SCIPD/MCIPD latches. Enable writes preserve its phase. Sound-CPU level selection uses the shared bit-7 SCILV controls. SCIRE clears pending flags even without a connected sound-CPU IRQ callback; timer sources also run independently of that callback.

## Verification

The macOS SDL3 Saturn build succeeds. Source whitespace checks pass.

`python3 scripts/scsp_dma_sample_test.py --output /private/tmp/new-scsp-dma-run` runs the real Saturn device graph with both SH-2 DRC and interpreter. It verifies timed payload movement, both directions and zero-fill modes, source preservation, protected controller registers, completion pending bits, independent 1Fs latches and enable phase, real 68000 autovector delivery, CPU contention, and save/load of a genuinely active DMA. A pre-save callback starts the transfer so the saved state cannot accidentally contain an already completed block. The generated parking BIOS/CD placeholders produce intentional checksum warnings.

In the final DRC diagnostic, the 68000 completed 73 loop iterations without DMA and 57 while contending. Across 16 windows the SH-2 completed 1303 versus 1290. These show that the wait paths affect actual execution; they are not measurements of original-hardware transfer rates.

`python3 scripts/scsp_dma_phase_test.py` compiles actual SCSP DMA methods under ASan/UBSan. It checks phase transitions, source preservation, zero-fill reads, final completion, protected controller writes, zero count, refresh/PCM/DSP reservations, and bus-specific waits including scheduler ties.

`python3 scripts/saturn_dsp_bus_cost_test.py` compiles actual SCU and host wait methods under ASan/UBSan. It checks SCSP waits reaching DSP DMA, restoration of shared accumulators, wait rounding and independent CPU halt ownership.

The full SCU regression harness passes all indirect-descriptor, transfer-rate, halt-release and DSP concurrency cases on both SH-2 cores. The supplied August 2024 SCSP audio suite reaches Done with all 20 enabled tests passing in both modes; both WAV captures contain 1,682,881 stereo frames at 48 kHz, with peak 26,880 and 696,819 nonzero samples. Captures and logs are under `/private/tmp/scsp-dma-suite-20261010/`; DMA/sample logs are under `/private/tmp/scsp-dma-sample-20261010-final/`.

The generated TODO inventory remains stale: regenerating it would rewrite checklist/inventory content forbidden by the user. Only the requested original completion marker is eligible to change.

Darius II Japan, the game named in the old SCSP DMA note, was run for 60 emulated seconds with dummy audio output. Its two observed DGATE starts at 11.542951 and 11.543138 seconds completed; DEXE was clear at every later sample. It reached an attract/game scene and produced audio. This is a startup regression check, not a claim that the game's graphics or audio are fully accurate. Logs, screenshots and WAV are under `/private/tmp/scsp-darius-dma-20261010-2/`.

## Closure of the scsp.cpp source notes — 2026-10-10

All three notes cited in checklist section 12.8 are resolved. The obsolete empty TODO and commented-out DMA interrupt-level macro were removed: the active implementation decodes DMA source bit 4 through SCILV0–2 and routes the resulting level through CheckPendingIRQ. DMA runs through scheduled read/write phases, and working parameters advance internally while programmed registers retain their values; every new DEXE reloads those registers.

The real-device diagnostic now explicitly verifies retained address/count read-back, a second transfer started by DEXE alone copying from the original programmed addresses, and DMA completion delivering exactly one level-4 68000 autovector whose handler clears SCIPD through SCIRE. These additions pass on both SH-2 cores in `/private/tmp/scsp-notes-20261010/`. The actual-method DMA fixture also passes ASan/UBSan. The only production-source change in this closure is removal of dead commented code, so the previously verified release executable exercises the same implementation. No hardware verification was performed; the timing qualifications above still apply.

Only the two original scsp.cpp-notes completion markers were changed. The separate CDDA synchronization item remains untouched.

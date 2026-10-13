# Saturn DMA and DSP audit — 2026-10-09

The six requested checklist entries were checked against the current source, the local Sega SCU Rel.2.5 manual and FAQ, the project memory describing the old regressions, and MiSTer's SCU/DSP implementation. This is not a hardware-verified timing model.

MiSTer reference revision: `a23bbb22c8c9a43926ee2196875e257d225291b7`. Relevant sources: [SCU.sv](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a23bbb22c8c9a43926ee2196875e257d225291b7/rtl/Saturn/SCU/SCU.sv), [DSP.sv](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a23bbb22c8c9a43926ee2196875e257d225291b7/rtl/Saturn/SCU/DSP.sv).

## Fixes implemented

* Indirect descriptors now use 20 count bits on every level. The old level-1/2 mask was 18 bits. A valid descriptor with count zero transfers 1 MiB; it does not terminate or skip the chain. The source address's EC bit determines chain termination. This follows the manual's descriptor flow and MiSTer's 20-bit decrement/wrap implementation; the manual text alone does not explicitly spell out zero's encoding.
* Invalid indirect source/destination regions now raise DMA-illegal and terminate the channel. A wholly zeroed descriptor is therefore an illegal address pair, rather than an endless sequence of maximum-sized transfers. BIOS, Work RAM-L and SCU register addresses remain outside the legal DMA regions. Same-bus indirect quirks are not newly specified by this change.
* An abort with no runnable/waiting channels stops the SCU timer and releases its CPU halt. A newly tested abort path otherwise rescheduled at zero time.
* DSP DMA now retains T0/DDMV until the final unit's bus wait finishes. Previously the final unit cleared busy immediately and left its cost accumulator unconsumed, potentially charging it to the next transfer. A separate completion phase consumes that wait.
* DSP `dma_finish()` charges the current scheduled phase as well as subsequent units, including a final beat whose payload has already moved and a pending startup phase.
* MVI disassembly uses the correct destination table: encoding C is PC, not the D1 bus CT0. Reserved destinations no longer acquire D1-only register names. Both conditional and unconditional MVI were corrected.

## FAQ transfer-rate comparison

Sega's local `segahtml/faq/prog/p07_10.htm` reports measured 256-byte transfers with VDP1 idle, unrestricted VDP2 access, and the 68000/SCSP DSP stopped. Setup register writes are excluded. It also notes substantial startup/teardown overhead and different 16-byte rates.

`scripts/saturn_transfer_rate_test.lua` executes a cached five-instruction longword-copy loop, 16-byte-burst SH-2 DMA, and SCU DMA in an isolated synthetic Saturn. It verifies all 64 destination longwords. Clocks are normalized to the actual NTSC reset clock, `14318181 * 1708 / 455 / 2` Hz. CPU timings end at a completion-port write and include polling/marker overhead. SCU timings end at the first write to its last destination longword and are consequently a lower bound, not the exact interrupt/busy-release latency.

| Path/destination | Sega clk/4B | Model DRC | Model interpreter |
|---|---:|---:|---:|
| Program loop → VDP1 | 15.40 | 16.8438 | 16.8750 |
| Program loop → VDP2 | 15.40 | 10.8281 | 10.8438 |
| Program loop → SCSP RAM | 32.80 | 37.8125 | 37.8281 |
| CPU DMA → VDP1 | 12.40 | 11.3750 | 11.4062 |
| CPU DMA → VDP2 | 7.60 | 5.4062 | 5.3750 |
| CPU DMA → SCSP RAM | 32.70 | 32.4063 | 32.4063 |
| SCU DMA → VDP1 | 2.25 | 2.1524 | 2.1524 |
| SCU DMA → VDP2 | 2.20 | 2.1524 | 2.1524 |
| SCU DMA → SCSP RAM | 26.80 | 25.6524 | 25.6524 |

### Architectural cross-check analysis

1. **SCU DMA (VDP1, VDP2, SCSP)**:
   - For 256-byte bulk transfers (64 longwords), the SCU DMA model closely matches Sega's hardware measurements.
   - In MAME (`saturn_scu.cpp`), transfers to VDP1 and VDP2 execute in 16-bit word units (`dma_write_unit`), each costing 1 cycle (`dma_write_cost`, `per=1`), giving a base write cost of 2.0 cycles per longword. SDRAM source reads from Work RAM-H are pipelined with zero base wait, adding a 6-cycle penalty every 31 longwords (`dma_read_cost`, line 756), or $+0.1935$ clocks per longword. The theoretical throughput is $(64 \times 2 + 12) / 64 = 2.1875$ clocks/4B, matching Sega's measured **2.20** clocks/4B for VDP2. The synthetic test fixture (`saturn_transfer_rate_test.lua`) captures the interval ending at the first write to the final longword (leaving out the 128th halfword write beat), reporting 2.1524 clocks/4B after clock normalization. The earlier expression `138 / 64 = 2.1524` was incorrect (`138 / 64 = 2.15625`); the measured normalized interval must not be replaced by that integer-cycle approximation.
   - For VDP1, Sega measured **2.25** clocks/4B ($5.36\ \mu\text{s}$ vs $5.20\ \mu\text{s}$ for VDP2). MAME models B-bus writes uniformly at 1 cycle across `0x05c00000`–`0x05fc0000`, so it does not add the $\approx 0.05$ clock hardware elongation present on the VDP1 bus interface.
   - For SCSP RAM, MAME charges 13 clocks per 16-bit word write (`per=13`), giving $2 \times 13 = 26$ clocks per longword. Combined with SDRAM read overhead and bus arbitration, this yields **25.65** clocks/4B vs Sega's measured **26.80** clocks/4B (a 4.3% difference).
   - For small transfers (e.g. 16 bytes), the FAQ documents that SCU-DMA throughput drops to 5.00 clocks/4B (VDP2) and 5.97 clocks/4B (VDP1) due to $\ge 20$ clocks preprocessing and $\ge 12$ clocks postprocessing fixed overhead ($\ge 32$ clocks total). MAME models direct channel start delay (`DMA_START_DELAY = 12`) but does not implement the full destination-dependent fixed overhead curve for short transfers.

2. **CPU-DMA (SH-2 on-chip DMAC)**:
   - CPU-DMA to SCSP RAM closely matches hardware: **32.41** clocks/4B in MAME vs **32.70** clocks/4B in the FAQ (0.9% variance).
   - CPU-DMA to VDP1 is **11.38** clocks/4B in MAME vs **12.40** clocks/4B in the FAQ. MAME charges 8 wait clocks on 32-bit writes to VDP1 VRAM (`saturn_bus.cpp`), resulting in $(7\text{ SDRAM read burst} + 4 \times (1 + 8)\text{ writes}) / 4 \approx 10.75$ plus arbitration.
   - CPU-DMA to VDP2 is **5.41** clocks/4B in MAME vs **7.60** clocks/4B in the FAQ. MAME charges 2 wait clocks on 32-bit writes to VDP2 VRAM, giving $(7 + 4 \times (1 + 2)) / 4 = 4.75$ plus arbitration. Bus acquisition and BSC handshaking are possible contributors; these results alone do not prove which mechanism supplies the missing cycles.

3. **Program copy loop**:
   - In Sega's hardware measurements, software copy loops to VDP1 and VDP2 took identical time ($36.75\ \mu\text{s}$ and $36.58\ \mu\text{s}$, exactly **15.40** clocks/4B).
   - In MAME, the synthetic cached copy loop yields **16.84** clocks/4B for VDP1 and **10.83** clocks/4B for VDP2. This disparity occurs because MAME stalls the CPU synchronously on every single peripheral write based on probe wait constants (8 for VDP1, 2 for VDP2). The measurement establishes a discrepancy, but does not establish its hardware cause. A posted-write-buffer explanation is unproven and must not drive a timing change without primary evidence. The exact Sega loop, cache state, arbitration and timing endpoints need comparison before assigning a cause.

The comparison is complete, but timing parity is not. SCU measurements are lower bounds, CPU tests include completion-marker/polling costs, and CPU-to-VDP2 differs substantially. These are emulated-time measurements, not host emulation-speed benchmarks. Hardware mechanisms behind the remaining differences are not established by this table. No artificial constants should be tuned merely to force a match. Commit `55014f670e5` contains documentation/checklist/inventory changes, not transfer-timing implementation fixes.

## Named game regressions

Golden Axe Duel, European Resident Evil, and Japanese Pu Li Ru La were each run for 60 emulated seconds with isolated state under both DRC and interpreter. Screenshots and master/slave/68000 PCs plus SCU status were captured every 600 fields. Golden Axe Duel reaches attract, Resident Evil reaches its title, and Pu Li Ru La reaches its story sequence with its slave running. None of these runs exhibits a permanently busy SCU DMA.

These are startup smoke checks, not exhaustive gameplay or an instruction-level replay of each historical race. In particular they do not establish precise mailbox-write timestamps, descriptor initialization order, or the exact old slave exception/restart trace. The broad game-retest checklist entry remains incomplete until those exact triggers are traced. Artifacts: `/private/tmp/saturn-dma-audit-20261009/games/`.

## Rel.2.5 software rules

The manual's DSP-control warning concerns read side effects, not an access that should be rejected. `program_control_r()` already clears V/E and deasserts the DSP end request on a side-effecting read; debugger reads leave them intact. Those semantics were retained and tested. Reads while EX is set can optionally log through `LOG_RULE` in `scudsp.cpp`.

The prohibition on writing IST warns that software can lose pending events. MiSTer nevertheless implements write-zero clearing. MAME retains that behavior, including byte masks required by games, and optionally logs such writes through `LOG_RULE` in `saturn_scu.cpp`. These logs are compile-time opt-in and silent in the ordinary build. No undocumented timing race was invented to model the caution.

## Remaining section 12.4 findings

The current tree already models A-bus normal/burst/precharge waits, SDRAM refresh overhead, direct same-bus rejection, and ordinary SCU C-bus CPU halts. Several introductory notes consequently describe work partly present in the code.

The follow-up [SCU DSP DMA implementation audit](SCU_DSP_DMA_IMPLEMENTATION.md) replaces the DSP/channel polling approximation with ownership grants and completion events, provides DSP C-bus CPU holds, and fixes accumulated waits and resource conflicts. Exact shared-bus acknowledgement timing is not hardware-established. Indirect same-bus and cross-region quirks, Road Blaster's byte case, A-bus external interrupt timing, attached-device contention, lightgun PAD input, and short-transfer overhead are not closed by this audit. DSP debugger/DRC scheduling, all arithmetic/control flags and vkyoute2 vertex behavior also lack comprehensive coverage. Converting the four CTx fields to an array is a structural cleanup, not evidence of an emulation fix. The DSP cost/bus-wait audit is implemented and software-tested; the broad section-12.4 notes entry remains incomplete.

## Verification and reproducibility

`python3 scripts/scudsp_dma_wait_test.py` and `python3 scripts/scudsp_disasm_test.py` compile actual implementation methods under ASan/UBSan. They check final-beat delay, sequential transfers, remaining host waits, debugger/control-read side effects and every MVI destination in both forms.

`python3 scripts/saturn_dma_audit_test.py --output /private/tmp/new-dma-audit-run` runs the real-device descriptor, transfer-rate and halt-release fixtures serially under both CPU engines. The intentionally generated parking BIOS/CD placeholder produces expected checksum warnings; this harness does not validate retail BIOS boot.

The halt/ordering fixture verifies CPU progress after direct C-bus DMA, preservation of a subsequent master mailbox write after A-to-B DMA to SCSP RAM, and completion polling with cached guest code using the uncached SCU register alias. All pass in DRC and interpreter. An earlier polling fixture used cached `0x05FE007C` and retained an old busy value; Sega explicitly requires the cache-through `0x25FE007C` alias. Replacing that address makes the loop exit. This was a fixture error, not evidence that the CPU remained halted.

The descriptor fixture tests all three levels: zero-count terminal descriptors, zero-count continuation followed by an EC descriptor, bit-18 counts, and invalid all-zero address pairs. Tests observe actual destination accesses and IRQ/status behavior, not just a copied decoder expression.

The macOS Saturn build and whitespace checks pass. The source-note inventory still contains 208 notes in 114 files. The generated inventory validator remains stale because source line references changed; it was not regenerated because the user forbids rewriting the checklist/inventory content. Only selected completion markers may change.

Checklist changes in this audit: only the existing indirect-zero-descriptor and Rel.2.5 game-side-rule markers changed to `[x]`. Their item text was preserved byte-for-byte. The other four requested markers remain unchanged.

Follow-up 2026-10-10: the existing SCU DSP DMA cost/bus-wait marker was completed after the implementation and both-core tests described in SCU_DSP_DMA_IMPLEMENTATION.md. No checklist item text was changed.

Follow-up 2026-10-10: Cross-check of the FAQ transfer-rate table against the model is completed with architectural breakdown above. The checklist entry is marked [x] without changing item text.


## SH7604 request/arbitration follow-up — 2026-10-11

The active DMAC now implements external DREQ/DACK, single-address ports and
shared channel ownership, including fixed and retained round-robin priority.
See [SH7604_DMAC_IMPLEMENTATION.md](SH7604_DMAC_IMPLEMENTATION.md). The existing
chapter-9 remainder is complete as an implementation/software validation item.
No absolute real-hardware timing verification is claimed.

Rebuilt real-device FAQ fixture, 256 bytes, clocks per four bytes:

| Path | DRC VDP1 / VDP2 / SCSP | Interpreter VDP1 / VDP2 / SCSP |
|---|---|---|
| Program loop | 16.8438 / 10.8281 / 37.8125 | 16.8750 / 10.8438 / 37.8281 |
| SH-2 DMAC | 10.9062 / 5.0000 / 32.0000 | 10.9375 / 4.9062 / 31.9375 |
| SCU DMA | 2.1524 / 2.1524 / 25.6524 | 2.1524 / 2.1524 / 25.6524 |

All nine payloads pass on both cores. CPU-DMA rates changed with the replacement
unit/grant scheduler and independent DMA suspension; the older table remains a
historical measurement of the previous implementation. Program-loop and SCU
results are unchanged. The measured CPU-DMA rates still differ from Sega's
reference; these measurements do not establish cycle-exact bus timing.
Artifacts: `/private/tmp/sh7604-dmac-rate-final-20261011`.

## SMPC saved status regression, 2026-10-13

The reset-button NMI enable, current clock-selection status and CD handshake
latches were absent from the SMPC save registration. They are now serialized.
The RTC diagnostic enables reset NMI with RESENAB, saves, disables it with
RESDISA, and loads the original state. It also changes the clock and CD status
latches between save and load, then checks SF and INTBACK's public status bytes.
Both DRC and interpreter pass, including calendar rollover and oscillator phase.
The previous binary fails because reset NMI state is absent from its saved items.
Artifacts: `/private/tmp/smpc-save-positive-20261013` and
`/private/tmp/smpc-save-negative-20261013`.

This repairs save/load behavior; it does not complete the broad Rel.2.5 SMPC
errata item. The additional peripheral formats and remaining reset behavior
still require review. No checklist text or marker changes accompany this fix.

# SH7604 BSC remainder — 2026-10-11

The original BSC remainder is **incomplete**. The refresh interval timer is
implemented and tested, but generic BCR/WCR/MCR interface effects are not fully
implemented. Register read-back and a board-specific Saturn timing callback do
not establish those effects.

## Implemented refresh behavior and correction

The active device supplies all seven RTCSR clock divisors, disabled counting,
eight-bit wrap, increment/compare/reset, compare-match flag permissions,
CMIE/CMI routing at WDT priority with the VCRWDT vector, saved counter phase,
standby/PLL handling and power/manual reset behavior. The counter runs without
MCR.RFSH, as section 7.2 specifies; counting is not proof that an external
memory refresh operation occurs.

This audit found and corrected a DRC sampling error. Register accesses now
include pending sequence cycles in the refresh sample time, matching the FRT
and DIVU convention. Previously the refresh sample could lag the interpreter
until the DRC committed its sequence. The actual-method sanitizer fixture
checks the value one cycle before compare, the compare boundary, DRC/interpreter
equality, and no double counting after commit. Its existing 7000 independent
increment-by-increment traces still pass.

## Source-level interface findings

| Control | Documented effect | Active implementation |
|---|---|---|
| BCR1.ENDIAN | CS2 little-endian alignment/conversion, section 7.3.2 | Implemented for CPU data, instruction fetch, cache fills/write-through and DMAC. Conversion is per physical beat: 32-bit beats reverse four bytes; 16-bit beats reverse each half separately; byte accesses retain their lane. Eight-bit devices do not support this mode. Both CPU engines and save/load pass the native regression. |
| BCR1.BSTROM | CS0 burst ROM cycles | Stored; no generic burst-ROM controller. |
| BCR1.PSHR | Only CS2 requests shared bus ownership in partial-share master mode | Stored; Saturn arbitration does not select its behavior from PSHR. |
| BCR1 long waits | Three to six programmed waits when WCR selects long wait | Stored; CPU cost callback uses board constants. |
| BCR2 widths / MCR.SZ | Split external data accesses by connected bus width | DMAC beat planner uses these for CS1–3; CPU memory/cache/fetch paths do not implement the generic splitter. CS0 pin-selected width also lacks a generic configuration path. |
| WCR waits and idle fields | Programmed waits, WAIT input gating, prior-area idle cycles | No generic stateful implementation. |
| MCR.DRAM mode, BE, RASD | Ordinary/SDRAM/DRAM/pseudo-SRAM cycles, page/burst/row retention | Partial classification in the DMAC planner; no complete controller. |
| MCR.TRP/RCD/TRWL/TRAS | Precharge, activation, write recovery and refresh timing | No generic interface state machine consumes them. |
| MCR.AMX | Physical row/column/bank address multiplexing | Not modeled by the logical address-space accesses. |
| MCR.RFSH/RMD | Memory refresh requests, pending requests, self-refresh and slave-mode exclusion | Counter/CMI exist; external refresh/self-refresh operations are absent. |

Evidence: `src/devices/cpu/sh/sh7604.cpp` BSC register handlers and DMA planner;
`src/devices/cpu/sh/sh2.cpp` memory/cache/DRC access helpers;
`src/mame/sega/saturn_bus.cpp` board timing/arbitration. The latter supplies
measured Saturn device costs but does not consume the BSC register fields.

The local Hitachi SH7604 manual sections 7.2–7.10 specify the required effects.
MiSTer BSC.sv contains a bus/pin state machine; copying only its register storage
or timer does not implement that controller in MAME. Generic external WAIT and
bus ownership must stall the actual CPU/DMAC access, not complete it and merely
change a register value afterward. Memory-interface modeling must cover both
CPU engines, cache fills, instruction reads and DMAC beats consistently.

No new wait constants, bus wiring or unsupported memory behavior was guessed.
The existing checklist item and marker are preserved; there is no closure claim
for the generic-interface scope and no hardware-verification claim.

## Verification

- `python3 scripts/sh7604_refresh_test.py`: actual methods under ASan/UBSan,
  including the new pending-cycle regression and 7000 tick traces.
- `python3 scripts/sh7604_register_test.py`: actual keyed access/mask/flag
  methods under ASan/UBSan.
- Rebuilt native `scripts/sh7604_device_test.py --only bsc`: both engines,
  all divisors, wrap/compare, CMI delivery, widths and scheduled pending save/load.

Native BSC results: `/private/tmp/sh7604-bsc-remainder-fixed-20261011`.
Build log: `/private/tmp/sh7604-bsc-remainder-build-20261011.log`.

## CS2 conversion implementation — 2026-10-13

The previous BCR1 handler stored ENDIAN without applying it. The implementation
now derives the CS2 physical width from BCR2 for ordinary memory and MCR.SZ for
synchronous DRAM. Keyed writes and postload/reset rebuild this derived state.
Raw DMA transfers and CPU memory/cache transactions use the same physical data
conversion. A 16-bit longword read is explicitly sequenced high half first; it
does not depend on C++ operand evaluation order.

Native DRC memory helpers use the shared CPU path for converted CS2 accesses,
so raw fast RAM and address-space loads cannot bypass conversion. Converted
CS2 instructions run through the shared interpreter rather than the raw DRC
front-end decode. Cache-through instruction fetching reverses word lanes. The
manual recommends the through area for little-endian sharing and matching
access sizes; the conversion does not make mismatched sizes interchangeable.

`scripts/sh7604_bsc_endian_test.py` runs the real CPU/device graph with generated
parked ROMs. It verifies CPU byte/word/longword reads and writes, ordinary and
SDRAM width selection, CS3 exclusion, DMAC reads/writes, cache fill/write-through,
save/load restoration, and converted instruction execution on both engines.
The preserved pre-change executable fails its word-lane check. Instruction-cache,
slice-boundary, BSC refresh and DMA regressions also pass on both engines.
The register, refresh and SCI/standby actual-method sanitizer fixtures pass.

Evidence: Hitachi SH7604 manual ADE-602-085C Rev.4.0 section 7.3.2,
Figures 7.5 and 7.6 (printed pages 150–151), and BCR2/MCR width definitions.
There is no new physical hardware verification. Logs are under
`/private/tmp/sh7604-bsc-endian-final-20261013` and related `sh7604-bsc-*` runs.
The broad checklist item remains incomplete: this implementation does not
claim programmed waits, external WAIT/grant handshakes, memory-interface
row/page state or physical refresh/self-refresh operations are finished.

Normal VF2J video/live-audio validation completed 130 emulated seconds without
a crash or render error: 95.91% average, 538 underflows and 11 overflows.
Combat dips remain; this is a functional validation, not a controlled speed
comparison. Output is under `/private/tmp/sh7604-bsc-vf2-final-20261013`.

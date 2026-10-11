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
| BCR1.ENDIAN | CS2 little-endian alignment/conversion, section 7.3.2 | Stored; not applied by CPU or DMAC data paths. |
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

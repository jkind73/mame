# SH7604 bus/SCI/WDT reconciliation — 2026-10-11

The original standalone-module checklist item is implemented and verified. The
CPU's existing `sh7604.cpp` implementation is the sole owner of these on-chip
modules. The unused `sh7604_bus`, `sh7604_sci` and `sh7604_wdt` classes and their
six build-list entries were removed after checking for users throughout `src`
and `scripts`. None were instantiated by a machine or included by another
source file. Their stub maps, fatal-error paths and duplicate register state
therefore no longer offer an alternative incomplete implementation.

The normal Saturn remains CD HLE, with no extra executing CPU.

## Behavior

BSC registers accept atomic A55A-keyed longword writes. Word reads use the low
halfword at register address +2; reserved bits and the CPU-configured master/slave
identity retain their documented read-back. CPU byte accesses in the word/longword
module area now take address-error vector 9 before memory or operand side effects.
Longword accesses in the byte/word module area likewise take vector 9. Both CPU
engines use the same exception boundary; the DRC checks an illegal delay-slot
access at the branch boundary to preserve the fault PC. Debugger/raw address-space
inspection does not execute a CPU instruction and does not raise a CPU exception.

The BSC refresh timer now implements all seven CPU clock divisors, disabled
counting, eight-bit rollover, RTCOR compare/counter clear and CMF. RTCOR zero
matches on rollover. It counts independently of MCR.RFSH. CMIE requests CMI at
the WDT priority from IPRA, using VCRWDT's low seven bits; WDT wins a priority
tie. Reading CMF as one then writing zero clears the interrupt, and a debugger
read does not qualify a clear. CPU configuration supplies the clock and slave
identity directly, so an external host-CPU setter is unnecessary.

Counter, divider phase and clock epoch are saved. A scheduler event is needed
only while an enabled CMI has not yet latched; other counter reads are calculated
lazily. This avoids a host callback for every SDRAM refresh interval. Full standby
stops the timer and preserves its BSC state; wake and PLL clock changes resume
it with the CPU clock. Manual reset retains BSC registers, while power reset
initializes them.

The active SCI already provides timed TXD/RXD/SCK shifting, byte-completion
observation, asynchronous/synchronous/multiprocessor formats, errors, qualified
status acknowledgement, DMA handshakes and interrupt requests. It is retained and
verified, rather than replaced by the former fatal-error stub or a second generic
serial engine. Its external inputs and bound output callbacks remain available.

The active WDT owns its keyed register map, CPU-clock counter, interval interrupt
and chip reset. Native tests verify keyed writes, rejected byte/invalid-key writes,
counter progress/disable, actual ITI delivery and qualified clear, watchdog overflow
without CPU reset, and RSTS-selected manual/power-on resets with RSTCSR retention.

## Validation

- The macOS SDL3 Saturn/ST-V subtarget builds after deleting the unused classes.
- `scripts/sh7604_refresh_test.py` passes ASan/UBSan against the actual refresh
  methods, compared with 7,000 independent tick traces covering every divisor,
  arbitrary counter/constants, rollover and multiple matches. It also checks
  interrupt scheduling, divider phase, disabled/standby behavior and clear rules.
- Register, SCI/standby, FRT and UBC actual-method sanitizer fixtures pass.
  Fixture dependency stubs were updated for the shared CPU refresh integration;
  their existing behavioral assertions were retained.
- `scripts/sh7604_device_test.py` passes all ten groups under both DRC and
  interpreter: SCI/standby power, queued SCI state, PLL, reset, serial pins,
  UBC, DMA errors, active WDT, BSC and FRT. The BSC test covers all seven clocks,
  real CMI handler execution, fourteen illegal access instruction forms, a
  branch delay-slot fault, and scheduled save/load with a compare pending.
  PLL tests verify that BSC counting stops throughout full standby and restarts
  after both 352/320 clock switches. Results:
  `/private/tmp/sh7604-reconciliation-all-20261011`. Final BSC master/slave
  identity checks also pass both engines in `/private/tmp/sh7604-bsc-final-20261011`.
- All seven DMA burst-count cases pass under both engines, alongside DMA errors:
  `/private/tmp/sh7604-reconcile-dma-20261011`.
- Normal HLE PAL VF2 reaches title/attract over 40 emulated seconds. All seven
  snapshot files match the preceding build byte for byte. Headless speed is
  195.13% versus the preceding 195.02%, with video/sound disabled; this is a smoke
  comparison, not a claim of full-speed interactive gameplay. Results:
  `/private/tmp/sh7604-reconcile-vf2-20261011`.

ST-V `gaxeduel` also completes an isolated eight-second smoke run without fatal
errors: `/private/tmp/sh7604-reconcile-stv-20261011`.

The local Hitachi SH7604 hardware manual, sections 4.2/4.6, 5.2/5.3, 7.1.4/7.2,
12 and 13 supplies the access, interrupt and timer rules. MiSTer BSC.sv independently
uses the same seven clock divisors and increment-then-compare counter behavior;
its register/CMF handling is not substituted for the manual's qualified-clear rule.
No real-hardware validation was performed. Generic BCR/WCR/MCR external memory
interface effects belong to the existing broader BSC audit item; they are not
claimed by this obsolete-module reconciliation.

Only the original checklist marker for `sh7604_bus.cpp` / `sh7604_sci.cpp` /
`sh7604_wdt.cpp` is changed. Its text, list membership and order remain intact.

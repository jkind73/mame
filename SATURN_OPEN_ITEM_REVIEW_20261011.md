# Six requested open items — 2026-10-11

The normal Saturn configuration remains HLE. No extra executing chip was added.
Only the existing IST/IMS, standalone SH7604 module and DMAC checklist markers were changed; item text,
membership and order are preserved. The FAQ comparison was already checked.
The SMPC and miscellaneous-module markers remain incomplete because their complete scopes are not yet
implemented or verified. This report does not turn partial repairs into closure.
No new commit was created, and unrelated working-tree changes were preserved.

| Original ID | Verdict | Evidence / remaining scope |
|---|---|---|
| 11 | Complete as a comparison | Both-core FAQ fixture repeated; all nine transfer payloads checked. Timing discrepancies remain. Arithmetic and unproven architectural claims corrected in SATURN_DMA_AUDIT.md. |
| 45 | Complete | IST clears when a request is issued, retained requests are masked/queued, vector fetch acknowledges, and pending interrupts now dispatch after acknowledgement. IMS reserved bits masked. Current vector initialized and saved. Unit ASan/UBSan and scheduled full-device pending save/load pass. An IMS 0-to-1 write alone is not the vector acknowledgement in the inspected RTL. |
| 16 | Incomplete | Internal one-Hz RTC subdevice implemented; century BCD carry fixed, warm resets no longer schedule an immediate extra RTC tick, and OREG31 identifies an accepted command during processing. Calendar and scheduled save/load tests pass both cores. Entire Rel.2.5 SMPC errata coverage is not claimed from the RTC repair alone. |
| 65 | Incomplete | Saturn backup RAM uses an explicit 32768-byte u8 buffer, so raw persistence needs no word byte swap. Actual NVRAM methods preserve every byte; short writes now fail. CD short reads now fail and byte swapping is bounded to the requested buffer. Legacy metadata endian handling, ticket output naming, string-view API and omitted TOC track-length handling still require complete review/implementation. Generic multi-byte NVRAM portability is not repaired by the Saturn byte-array test. |
| 58 | Complete | Unused standalone classes/build entries removed; active SCI/WDT retained and tested. BSC refresh counter, seven clocks, compare/CMI, saved phase and standby/PLL handling implemented. Illegal on-chip CPU widths take vector 9 without operand side effects under both engines. Full native and sanitizer regressions pass; see SH7604_MODULE_RECONCILIATION.md. |
| 04 | Complete | AE/NMI inhibition retained; external level/edge DREQ, DACK phase/polarity, single-address ports, accepted-ahead burst requests, fixed/round-robin channel arbitration, preemption, accepted-unit aborts and live saved state implemented. DMA uses an independent CPU suspension reason, preserving external HALT. Connected regressions and all 34 Saturn device cases pass both engines; actual-method ASan/UBSan passes. See SH7604_DMAC_IMPLEMENTATION.md. Absolute hardware timing is not verified. |

## Fixes and validation

SCU acknowledgement previously cleared its current-request flag without
reconsidering queued IST bits. A saved, scheduler-managed timer now dispatches
pending requests after vector fetch. This avoids depending on another unrelated
source event/register write and avoids changing the vector inside its own fetch.
The current vector is also explicitly initialized and serialized.

`scripts/saturn_irq_ack_test.py` extracts the actual mask/status/arbitration/vector
methods and passes ASan/UBSan. `scripts/saturn_irq_queue_test.lua`, run by
`scripts/saturn_dma_audit_test.py --only irq`, queues actual DSP and SMPC sources
while SH-2 SR masks them, runs both handlers without extra register writes, and
repeats after a scheduled save/load with both requests pending. Both cores pass.

`scripts/sh7604_dma_error_test.lua`, run with
`scripts/sh7604_device_test.py --only dma-errors`, checks misaligned source and
destination word/longword accesses, illegal on-chip widths, unchanged destination
memory/count/TE, and NMI during an active transfer. Both cores pass. The existing
SCI/standby/NMI/wake/save regression (`--only power`) and all seven DMA burst-count cases also pass on both cores.
Address alignment is no longer silently corrected; 16-byte source alignment
beyond the documented longword-access requirement remains explicitly undefined
by the manual rather than being assigned invented behavior.

The SMPC RTC is an internal HLE calendar device, advanced once per second. It
executes no CPU instructions. Calendar state and oscillator timer are saved, and
soft resets preserve the clock instead of rephasing it. Host-time initialization occurs only at startup; the saved initialization flag prevents the framework's warm-reset RTC update from overwriting SETTIME. SETTIME reaches the
calendar; INTBACK reads it. `scripts/saturn_smpc_rtc_test.lua` checks 1999/2000,
leap and non-leap February, OREG31 during command execution, INTBACK time bytes,
scheduled save/load of the oscillator phase, saved mono/language settings, and retained SETTIME/oscillator phase after an actual machine soft reset under both cores. Invalid month
values cannot index past the calendar table; Sega calls invalid input undefined.

Immediate Lua `buffer_load` inside an active timer callback is documented as
unsafe by MAME and produced a misleading extra RTC tick. The final IRQ/RTC
save validations use scheduled save/load at safe boundaries instead. This is a
fixture correction, not a fabricated RTC timing adjustment.

`scripts/saturn_cd_partial_read_test.py` exercises the actual sector-read method
under ASan/UBSan with short streams, seek errors, guarded partial audio buffers,
odd-length reads and virtual pregap. `scripts/saturn_nvram_io_test.py` exercises
actual NVRAM I/O for all 32768 Saturn backup bytes and rejects short/error I/O.

The initial FAQ repeat matched historical rates on both cores, including 2.1524
SCU clocks/4B and 5.4062 DRC CPU-DMA clocks/4B to VDP2. After the DMAC follow-up,
CPU-DMA VDP2 measures 5.0000 DRC / 4.9062 interpreter; other new rates are in
SATURN_DMA_AUDIT.md. It remains a comparison,
not proof of cycle-exact hardware parity or a host-speed benchmark.

The rebuilt normal HLE Saturn boots PAL VF2 and reaches its title/attract sequence
in a 40-emulated-second isolated run. Evidence:
`/private/tmp/saturn-six-items-vf2-20261011`; IRQ/RTC scheduled-save results:
`/private/tmp/scu-irq-scheduled-final-20261011` and
`/private/tmp/scu-smpc-rtc-warm-reset-final-20261011`.

## References and limits

- [Sega SCU 3.5](https://www.infochunk.com/saturn/segahtml_en/hard/scu_/hon/p03_05.htm): mask/status bits and reserved fields.
- [Sega system library](https://www.infochunk.com/saturn/segahtml_en/prgg/sysg/prog/hon/p02_11.htm): separate IMS, IST and A-bus acknowledge writes.
- Local MiSTer `rtl/Saturn/SCU/SCU.sv`: IST cleared on issue and delivered request cleared by IVECF_RISE; no IMS 0-to-1 vector acknowledgement.
- Local Renesas SH7604 manual, table 4.6 and sections 9.2.7/9.3.8: address errors, qualified AE/NMIF clears, NMI inhibition and abort without TE.
- [Sega SMPC 2.5](https://www.infochunk.com/saturn/segahtml_en/hard/smpc/hon/p02_50.htm): BCD calendar, weekday/month encodings, leap-year correction through 2099, and OREG31 command reporting.
- [STN-27](https://www.infochunk.com/saturn/segahtml_en/info/hon/stn27.htm) and [STN-42](https://www.infochunk.com/saturn/segahtml_en/info/hon/stn42.htm) are application usage rules. They do not justify disabling physical direct-mode operation, changing reserved saved settings, or inventing a hardware-enforced access prohibition.

No real-hardware timing verification has been performed. Software regressions
establish the listed behavior; generic memory-bus arbitration timing and complete
SMPC errata parity remain separate evidence requirements within the open items.

# SCU DSP DMA cost and bus wait — 2026-10-10

The audit against MiSTer revision `a23bbb22c8c9a43926ee2196875e257d225291b7` is implemented. This is software verification, not validation against a physical Saturn. Absolute bus durations retain MAME's existing calibrated cost model; MiSTer's FPGA SDRAM acknowledgement FSM is not a numerical timing specification for the original chip.

## Execution during DMA

MiSTer's `DSP.sv` separates `RUN = (EX || ES) && ~EP && ~PAUSED` from `DMA_EN = T0 && DMA_ACK`: T0 alone does not stop execution. Its pause decoder waits on the transfer's RAM bank, that bank's CT reads/increments/writes, another DMA, RA0/WA0 writes, and a PC write during program-RAM DMA. `DSP_PKG.sv` gates conditional MVI destination writes by the condition. Sega SCU manual chapter 5 describes clearing T0 on the external END signal; this is compatible with asynchronous execution, but is not a hardware measurement of the precise overlap timing.

MAME retains independent execution and now ignores a false conditional MVI when checking resource conflicts. Program-RAM DMA also checks PC and address-register conflicts. The tests exercise the real instruction engine, not only the conflict predicate.

References: [DSP.sv](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a23bbb22c8c9a43926ee2196875e257d225291b7/rtl/Saturn/SCU/DSP.sv), [DSP_PKG.sv](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a23bbb22c8c9a43926ee2196875e257d225291b7/rtl/Saturn/SCU/DSP_PKG.sv), [SCU.sv](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a23bbb22c8c9a43926ee2196875e257d225291b7/rtl/Saturn/SCU/SCU.sv).

## Bus ownership and costs

An active ordinary channel retains ownership through its final acknowledgement. DSP requests wait for its completion, then take priority over queued ordinary channels, as in SCU.sv's IDLE arbitration. Parked requests resume from completion events instead of polling every clock. The four-DSP-clock initial request delay is preserved.

DSP transfers using Work RAM-H hold the SH-2s until acknowledgement. SCU DMA and SMPC system halt reasons are tracked independently, so releasing one does not release the other. SCU holds do not halt the 68000.

Every transferred longword consumes its read cost once and its two halfword write costs. VDP2 write-slot waits now accumulate for both halfwords instead of discarding one. Scratch calculations preserve the ordinary channel's cost accumulators. Existing A-bus configuration waits, SCSP waits and SDRAM refresh costs remain in use.

The final payload beat schedules an END phase; T0/DDMV remain asserted until that phase completes. Host-access ordering includes the pending beat, startup delay and any preceding owner. Repeated host waits do not copy the payload twice or extend the deadline. MAME's existing host contention path copies remaining payload atomically before charging the host its wait; this architecture is retained, with busy state and completion deferred to the acknowledgement time. It is not a cycle-by-cycle electrical bus simulation.

## Verification

The macOS SDL3 Saturn build succeeds.

* `python3 scripts/scudsp_dma_wait_test.py`: actual timer/host-wait/control/conflict methods pass ASan/UBSan, including final-beat waits, parked grants, repeat host waits, conditional MVI and program-RAM conflicts.
* `python3 scripts/saturn_dsp_bus_cost_test.py`: actual SCU methods pass ASan/UBSan for SCSP and A-bus reads, per-halfword SCSP writes, accumulated VDP2 waits, SDRAM refresh, scratch accumulator preservation and independent CPU halt ownership.
* `python3 scripts/saturn_dma_audit_test.py --output /private/tmp/new-dma-audit`: real-device indirect descriptors, transfer rates, halt release and DSP concurrency pass with both SH-2 DRC and interpreter. The generated parking BIOS/CD placeholders have expected checksum warnings.
* The DSP program queues behind an active A-to-SCSP transfer, executes an independent RX write and a false conditional RAM write while waiting, then polls T0. A second program stalls on a conflicting MC0 write and resumes after the DMA, preserving all 32 transferred words. A third case verifies DSP priority over a queued ordinary channel by observing real destination writes.

No real-hardware capture validates these changes. The audit closes the identified implementation defects; it does not establish cycle-exact absolute transfer rates or close the separate FAQ-rate and broad section-12.4 checklist entries.

## Follow-up: external write address stride

The Virtual Kyoutei 2 freeze investigation found a remaining payload-address defect, separate from the cost/acknowledgement checks above. DSP output DMA advanced Work RAM-H destinations twice per longword. The C bus transfers the longword as one unit: MiSTer's `SCU.sv` `DMA_WA_NEW` and Mednafen 1.32.1 agree that its address increment applies once. Only the 16-bit B bus applies it after each halfword. The corrected `exec_dma` preserves B-bus stepping and applies one increment on the external 32-bit write path.

The actual-device `scudsp_dma_stride_test.py` fails before the correction and passes on both CPU cores afterward, checking address fields 0 and 2–7, held/non-held WA0, payload words, untouched neighbours, CT counts and WA0 completion. The fresh Virtual Kyoutei 2 title/3D sequence now runs through 120 emulated seconds without the corrupt slave copy, scheduler freeze or eventual CD-port exception. Full findings are in `SCU_DSP_CORE_AUDIT.md`. No physical Saturn was used.

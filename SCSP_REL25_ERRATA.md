# SCSP Rel.2.5 errata implementation — 2026-10-10

All nine entries in the official Rel.1-to-Rel.2.5 SCSP errata were checked against the current implementation. Defined runtime corrections are implemented and tested. Renamed tables and firmware restrictions are accounted for without inventing hardware behavior for prohibited operations. No physical Saturn trace validates these changes.

The primary source is the SCSP section of `segahtml/xhistory/ver250/hard.htm`. The replacement chapter and corrected descriptions are in `segahtml/hard/scsp/hon/p01_10.htm`, `p01_20.htm`, `p01_30.htm`, `p04_12.htm`, `p04_21.htm`, and `p04_29.htm`. RESET/TAS restrictions are also explained in `segahtml/info/hon/stn51.htm`.

| Official entry | Correction and disposition |
|---|---|
| 1 | Replaces chapter 1. The sound block has one installed 4Mbit/512KiB RAM chip. Saturn and ST-V's sound CPU and SCSP previously allocated 1MiB, supplying nonexistent storage in the second-chip region. Both maps now expose the installed 512KiB; the unpopulated bank remains unmapped. The main SH-2 map already covered 512KiB. The revised reset procedure's 30us access exclusion and MEM4MB setup have opt-in diagnostics. Existing autovectors, independent sound CPU, SCSP/CD-DA routing, panning and master volume match the replacement chapter. Interrupt level 7 remains supported in hardware but has an opt-in warning because Sega reserves it for development tools. |
| 2 | Prohibits RESET and TAS in Saturn software. This specifies no illegal-instruction exception, ignored-write result or exact failure behavior. The existing 68000 fallback and Out Run RESET compatibility path remain; tests verify RESET does not reset the SCSP. The source records the restriction and why undefined opcode behavior was not fabricated. |
| 3 | Removes the input-empty bit from the common-register diagram. MIDI status bit 8 reads zero. Verified even after an attempted write of all ones. Other FIFO flags remain implemented. |
| 4 | Renames a common-register table as a register list. This has no runtime behavior to implement. The current register layout was checked against the corrected list. |
| 5 | Deletes MIEMP from that register list. Already applied; the obsolete unused MIEMPTY macro was also removed. |
| 6 | Renames a source-register allocation table as allocation data. This changes documentation labeling, not register encoding or runtime behavior. |
| 7 | Clarifies source bit inversion. SBCTL0 XORs the lower 15 bits while preserving the sign; SBCTL1 independently inverts the sign as stated in the revised detailed description. The existing renderer applies this before interpolation. Real-device tests verify all four combinations with positive, negative and boundary data in both PCM widths. |
| 8 | Requires MEM4MB=1 for this system. Saturn/ST-V now enable board-specific diagnostics for writes selecting the unsupported configuration. The bit is not forced to one: firmware must set it, and Sega does not guarantee incorrect-mode operation on Saturn. Generic SCSP machines retain their independent configuration. |
| 9 | Deletes the MIDI input-empty description. Same implemented and verified bit removal as entries 3/5; no replacement empty flag was invented. |

## Additional correction found during the audit

The DMA reservation predicate now accounts for direct PCM slots whose envelope is fully attenuated. SDIR bypasses that envelope, so an active direct PCM slot still fetches sound RAM and must reserve its PCM memory opportunities. The actual-method sanitizer fixture verifies this case. This fixes the arbitration predicate without changing the already-correct SBCTL renderer.

## Diagnostics and undefined operations

`LOG_RULE` in `scsp.cpp` is compile-time opt-in through `VERBOSE`, default zero. It diagnoses Saturn register accesses during the documented 30us initialization interval, MEM4MB=0 writes, and interrupt level 7 use. The reset-ready deadline is saved. These diagnostics do not impose guessed bus errors, silently repair firmware settings or suppress hardware interrupt levels.

The documented firmware sequence writes `0200H` after initialization, setting MEM4MB and selecting the initial 16-bit DAC mode. The tests exercise that configuration. DAC18B remains programmable afterward; it was not disabled because games use it and the register defines its behavior.

Byte accesses from the main side, early reset access and the prohibited CPU instructions remain outside the documented valid software contract. Neither the errata nor STN-51 provides numerical results for every invalid access. Existing compatibility behavior is retained rather than represented as hardware-verified behavior.

## Verification

* The macOS SDL3 Saturn build succeeds; changed-source whitespace checks pass.
* `python3 scripts/scsp_errata_test.py --output /private/tmp/new-scsp-errata-run` passes with both SH-2 DRC and interpreter. It exercises the real device graph: 48 SBCTL cases, MIEMP removal, shared RAM boundaries, unmapped-bank writes, MEM4MB/DAC18B setup, and RESET/TAS compatibility. It deliberately makes initial software-rule probes but asserts no hardware result for those undefined accesses.
* `python3 scripts/scsp_dma_phase_test.py` passes under ASan/UBSan, including the direct-slot reservation correction.
* `python3 scripts/scsp_dsp_bank_test.py` passes under ASan/UBSan.
* The real-device DMA/sample regression passes on both cores, including timed transfers, CPU waits, recurring 1Fs autovectors and save/load of an active transfer.
* The supplied August 2024 SCSP suite reaches Done with all 20 enabled tests passing on both cores. Each capture contains 1,682,881 stereo frames at 48kHz, peak 26,880 and 696,819 nonzero samples. This establishes diagnostic behavior, not waveform accuracy against a real Saturn.

Logs: `/private/tmp/scsp-errata-20261010-final/`, `/private/tmp/scsp-errata-dma-regression-20261010/`, and `/private/tmp/scsp-errata-suite-20261010/`.

The RAM allocation and saved reset deadline change the save-state schema: save states from the preceding layout require a fresh state in this build. The current active-DMA save/load tests pass.

Only the existing requested checklist marker changes to completed. No checklist item text or structure is changed; the generated inventory is not rewritten.

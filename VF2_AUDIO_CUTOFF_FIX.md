# VF2J first-attract movie cutoff

The early cutoff is corrected by `33ef6afa041` (SH2 instruction-boundary scheduling). Normal Saturn configuration remains CD HLE. No checklist items or text were changed.

## Reproduction and cause

The Windows backup RAM supplied by the user reproduces the first-play cutoff with DRC on macOS as well as Windows build `74c94d4f59d53954f33dac9a565d546487e1e84c`. The same backup RAM plays the full movie with the interpreter. A preserved DRC binary from before the recent cache performance changes also reproduces the cutoff.

The DRC charged instruction cycles in batches. Bus waits could exhaust its time slice while ordinary instructions in that batch continued executing. A generated eight-clock FRT interrupt diagnostic demonstrates the problem without retail ROMs: the previous DRC executes all 32 foreground increments before delivering the interrupt. The corrected DRC captures one increment; the interpreter captures two. This verifies removal of the large overrun, not exact agreement of all CPU timing.

The guest trace identifies the consequence in VF2J:

- Foreground buffer-wrap division at `060B3A42` writes divisor `000675D4` to `FFFFFF00`.
- VBLANK-IN IRQ 15 interrupts at `060B3A44`, before the dividend writes. Its BIOS callback uses the same divider with divisor 2.
- Foreground division resumes with dividend `007BD80C` and receives quotient `003DEC06`, rather than 19.
- The guest consequently stores buffer position `F831A514` at `002ED0C8`. Frame requests stop succeeding, the movie starvation counter expires, and the guest sends seek/pause command `11FF FFFF 0000 0000` at 57.753622 seconds.

The scheduling correction checks the remaining budget before starting another ordinary instruction in a timed SH2 DRC sequence. Native delayed branches finish their slot before returning to the scheduler. It changes CPU scheduling generally; the implementation contains no VF2 addresses or game-specific divider protection.

## Validation

Build: `make SUBTARGET=saturn SOURCES=src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp -j8`.

All real-device diagnostics pass under DRC and interpreter:

- `scripts/sh7604_slice_boundary_test.py`: cached and uncached ALU sequences interrupted by the FRT; preserved pre-fix DRC fails with count 32.
- `scripts/sh7604_instruction_cache_test.py`: private executable cache, cache-through execution, cache patches, delay-slot fallback and CCR changes.
- `scripts/sh7604_interrupt_yield_test.py`: persistent interrupts and interrupt returns continue yielding to the scheduler.
- `scripts/sh7604_device_test.py --only divu`: division register behavior.

A 110-second internal 48 kHz stereo recording with the supplied backup RAM restores the full movie section:

| Capture | Audible movie section | Duration |
| --- | --- | --- |
| Previous DRC | 28.39–57.76 s | 29.37 s |
| Corrected DRC | 28.36–79.09 s | 50.73 s |
| Interpreter control | 28.39–79.12 s | 50.73 s |

One-second mono waveform comparisons at 32, 45, 60 and 75 seconds correlate above 0.9983 with the interpreter after a constant 0.033375-second alignment. These comparisons establish agreement with the interpreter control, not SCSP fidelity against hardware or Ymir.

The normal video/live-audio run completed 130 emulated seconds without a crash or render errors. The intro played through its full sequence. Average speed was 96.89%, with 420 CoreAudio underflows and 16 overflows. Five-second combat intervals reached 79.93% and 84.10%; the remaining real-time performance/audio-underflow problem is not closed. Logs and thirteen screenshots are under `/private/tmp/vf2-boundary-live`. Prior cutoff runs execute a different sequence of scenes, so their average speed does not provide a controlled measurement of the scheduling change’s cost.

The recorded output and diagnostic logs are retained under `/private/tmp/vf2-boundary`; real-device logs are under `/private/tmp/vf2-boundary-device`, `/private/tmp/vf2-boundary-cache-check`, `/private/tmp/vf2-boundary-irq-check` and `/private/tmp/vf2-boundary-divu-check`.

## Separate CD status correction

`9b192cb5dd8` keeps SCDQ status events active when the HLE sector buffer is full. The new `scripts/saturn_cd_full_buffer_test.py` passes on both cores and fails on the preserved pre-fix binary. Local Mednafen `src/ss/cdb.cpp` and Ymir `cdblock.cpp` also generate subcode/status events independently of full-buffer storage pauses. The SCDQ change alone did **not** resolve the VF2 cutoff; it is committed separately.

## Limits

The corrected game run and CPU diagnostics were executed on macOS arm64. A new Windows build has not yet been tested. There is no new physical Saturn hardware verification. Other audio differences relative to Ymir are not declared resolved by this fix.

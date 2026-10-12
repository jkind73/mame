# SH-2 translated slice-exit optimization

The timed SH-2 instruction-budget check still runs before every ordinary instruction. Its uncommon cycle-subtraction path now shares one generated handler instead of repeating the memory operation at every instruction site. The calling site passes the uncharged cycle count in scratch register I1; the handler saves guest registers, charges those cycles and returns to the scheduler at the same guest PC. Bus-clock bookkeeping and delayed-branch behavior are preserved. Normal Saturn configuration remains CD HLE. Checklist files are untouched.

This reduces generated-code storage, but the completed benchmark does not establish a speed improvement.

## Validation

Built the Saturn/ST-V subtarget on macOS arm64 with the usual `-j8` command. These real-device tests pass on both DRC and interpreter:

- `scripts/sh7604_slice_boundary_test.py`: cached and uncached instruction budgets at a timer edge.
- `scripts/sh7604_instruction_cache_test.py`: cached code, cache-through execution, patching, delay-slot fallback and CCR changes.
- `scripts/sh7604_interrupt_yield_test.py`: interrupts and interrupt returns yield to the scheduler.

Serial 130-second VF2J runs used identical copied backup RAM/configuration, normal video, no sound output and no throttling. Neither final run was profiled or run alongside a build or another emulator.

| Measurement | Baseline | Shared exit |
| --- | ---: | ---: |
| Average unthrottled speed | 164.11% | 163.72% |
| Combat speed, six equal five-second intervals, harmonic mean | 96.44% | 95.62% |
| Slowest measured combat interval | 82.44% | 82.21% |
| Slave maximum transient generated-code bytes | 76,601,760 | 75,436,760 |
| Main/slave cache flushes | 2 / 1 | 2 / 1 |

The slave code footprint falls by 1,165,000 bytes (1.52%). The small speed differences are slightly negative and are not evidence of improved performance. The main CPU still fills its translation cache. This change does not eliminate combat slowdowns, establish steady real-time speed or predict a Windows speed gain.

All thirteen periodic screenshots are byte-identical to the baseline. Matching-options 110-second internal 48 kHz stereo captures contain exactly identical PCM: all 10,560,002 signed 16-bit channel samples match. The middle movie audio still runs from 28.36 to 79.09 seconds (50.73 seconds), retaining the scheduling fix for the early cutoff.

## Investigation notes

A variant using the pending bus-cycle field reduced code but changed the captured PCM, so it was discarded. A second variant recovered cycles from compiler metadata and preserved PCM, but its runtime lookup reduced average speed to 151.09%, so it was also discarded. The committed implementation passes the constant directly and preserves the prior bus bookkeeping.

A three-second baseline combat CPU sample continues to show bus arbitration and VDP2 rendering as substantial costs. No emulated wait-state constants were removed or reduced. There was no physical Saturn hardware validation or new Windows validation.

Logs and captures are under `/private/tmp/vf2-opt-20261012`: `before-final`, `after-direct`, `audio-before`, `audio-direct`, `direct-boundary`, `direct-cache`, and `direct-irq`. Earlier exploratory baselines overlapped compilation or included profiling; neither is used in the table.

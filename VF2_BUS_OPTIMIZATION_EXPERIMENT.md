# Rejected bus conversion shortcuts

Two host-side shortcuts were tested in `saturn_state::sh2_bus_arbitrate` on macOS arm64:

1. Return `cycles` before wait-clock conversion when `start - now` is zero.
2. Calculate `exec.cycles_to_attotime(1)` only for slave accesses, since the master branch never uses that value.

The candidate passed 20,000 actual-method arbitration comparisons under ASan/UBSan. All thirteen periodic VF2J screenshots matched the baseline, and all 10,560,002 PCM samples in a matching-options 110-second internal 48 kHz stereo capture were identical.

Serial 130-second, unthrottled, normal-video/no-sound runs used identical copied configuration and backup RAM. No compilation or profiling ran alongside these measurements.

| Version | Overall speed | Combat speed |
| --- | ---: | ---: |
| Initial baseline | 159.70% | 93.65% |
| Zero-wait shortcut | 161.94% | 94.89% |
| Both shortcuts | 160.30% | 93.71% |
| Repeated baseline | 161.46% | 94.55% |

Combat speed is the harmonic mean of the six equal five-second intervals ending at approximately 100–125 seconds. The repeated baseline is faster than the combined candidate. The small improvements in the first pair do not establish a reproducible speed benefit. Both code changes were therefore reverted; no emulated timing, renderer behavior or checklist files were changed.

For traceability, the discarded implementation consisted of:

```cpp
// Instead of the unconditional conversion:
attotime const one = cpu ? exec.cycles_to_attotime(1) : attotime::zero;

// Immediately before the existing wait-clock conversion:
if (wait.is_zero())
    return cycles;
```

Baseline/candidate binaries, build logs, four benchmark runs and screenshots are under `/private/tmp/vf2-bus-opt-20261012`. Audio captures are under `/private/tmp/vf2-opt-20261012/audio-direct`, `audio-bus`, and `audio-bus-final`. No Windows or physical Saturn validation was performed for this experiment.

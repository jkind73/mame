# VF2 performance regression — 2026-10-11

The user's video/audio run of `./saturn saturnjp vf2j -verbose` averaged 56.04%
over 233 seconds and recorded 17169 CoreAudio underflows, with no reported
freeze or graphical fault. Short headless startup tests did not establish
playable video-enabled speed.

## Findings and changes

A matched Japanese VF2 run with video enabled and audio disabled averaged
89.51% over 90 emulated seconds. In a five-second combat sample, over half the
main-thread samples were in the SH-2 code compiler. The 32 MiB host translation
cache repeatedly discarded compiled code. Cache/fetch monitoring also emitted
an identical slow mismatch exit, including mapped-register saves, at every
instruction site.

SH7604 now allocates a 256 MiB host translation cache, while other SH-2-family
constructors retain their default. Its guest cache remains unchanged. For the
two Saturn CPUs this reserves 448 MiB more virtual address space; the actual
resident use depends on generated code. The cache-mismatch exit is generated
once and shared. Pending cycles, guest registers, prefetched instruction and
branch delay-slot target follow the same fallback behavior.

The larger cache exposed ARM64's unconditional branch range: an intermediate
trial aborted after 75 seconds with `InvalidDisplacement`. The backend's jumps
to the permanent exit/end-of-block handlers now use a register-indirect long
jump when outside the signed 28-bit byte displacement, matching its existing
range-aware call handling. The corrected 90-second run completes beyond that
point. Near jumps retain the same direct form.

VDP2 fetch no longer searches every old pattern-name entry when the newest
eligible one is sufficient, and skips address selection when no bank schedules
a character-pattern read. Its 24-entry history is now a ring rather than being
shifted on every name read. Issued memory reads, dot buffers and line-to-line
latches remain identical. The compositor also bypasses unused second-image
work when mixing, offsets, shadow and extended/gradation history cannot affect
the dot. Interlaced field handling and presentation settings remain in effect.

## Verification

- `scripts/saturn_fetch_equivalence_test.py`: 24000 randomized lines under
  ASan/UBSan, compared with the frozen prior traversal's complete read traces,
  every output buffer and final carry state. Covers normal/hi-res slots,
  bank schedules, depths, tile/bitmap and reductions across consecutive lines.
- `scripts/saturn_render_equivalence_test.py --reference /private/tmp/vf2-performance-before-render.cpp`:
  identical digest `ab833a46f12de50d` over 4096 varied real-renderer lines,
  including normal/dedicated/hi-res modes, priorities, colour mixing, offsets,
  shadows and gradation. Both sources compiled under ASan/UBSan.
- `scripts/saturn_vdp_wip_test.py`: windows, rotation and physical erase fixtures
  pass ASan/UBSan.
- Actual native instruction-cache/branch-delay mismatch tests pass DRC and
  interpreter: `/private/tmp/vf2-performance-cache-regression-20261011`.
- All 36 SH7604 device cases pass, including IRQ, DMA, peripheral and saved
  state behavior: `/private/tmp/vf2-performance-device-suite-20261011`.
- Nine VF2 snapshots from the successful 256 MiB/long-jump/fetch run match
  the preceding 128 MiB build byte-for-byte. A later live-audio run also checks
  screenshots after the final renderer refinements.

## Measurements and reproducibility

Initial intermediate measurements with video enabled, audio disabled and
90-emulated-second runs on this Mac:

| Build | Average speed | Master/slave cache resets including initialization |
|---|---|---|
| Original 32 MiB | 89.51% | Original user run had 870/97 over a longer 233-second session |
| 128 MiB | 127.24% | 2/1 |
| 256 MiB + long jumps + initial fetch changes | 136.22% | 1/1 |
| Also sharing mismatch exits | 147.38% | 1/1 |

These stage measurements include startup and compilation; some combat samples
still fell below 100%, so averages alone were not accepted as proof of smooth
playback. The first three runs used stack sampling; they are diagnostic
measurements rather than a controlled statistical benchmark. The final
ring/compositor refinements are assessed with live audio and video below.

`scripts/saturn_vf2_performance_test.py --output /private/tmp/new-vf2-run
--seconds 230 --sound auto --throttle --nvram-seed nvram/saturnjp --cfg-seed cfg`
reproduces the normal configured renderer/audio output with isolated mutable
state, per-stage speeds, screenshots, final DRC statistics and audio sink
underflow counts. It needs the existing VF2 software/ROM paths. Omit throttle
and select sound none for headroom measurements. No personal configuration or
NVRAM is overwritten.

No checklist completion marker was changed for this work. Normal Saturn
continues to use CD HLE. The preserved LLE patch passes `git apply --check`.

## Final live-audio results and remaining limitation

The final build completed 230 emulated seconds with normal configured OpenGL
video, CoreAudio and throttling. Average speed was 89.23%, with 2,637 audio
underflows, 20 overflows and no audio render errors. Both CPUs recorded only
their initial translation-cache reset. Log and captures are in
`/private/tmp/saturn-vf2j-live-audio-20261011`.

The user's original interactive run reported 56.04% and 17,169 underflows over
233 seconds. These are useful practical observations, not a controlled paired
benchmark: the automated run follows attract mode and interactive inputs may
select different scenes. Many final-run intervals maintained 100%, but the
210–225 second combat segment still ran at about 67%. Smooth real-time
emulation and uninterrupted audio are therefore **not fixed completely**.

A separate 90-second test with `-video accel -renderdriver metal`, live audio
and throttling averaged 95.28%, with 434 underflows. Its 80/85-second samples
were 85.49%/74.38%, so changing the renderer alone did not remove the combat
slowdown. Results are in `/private/tmp/saturn-vf2j-metal-audio-20261011`.
Personal renderer/audio preferences were not changed.

Eight early live-audio screenshots matched the preceding audio-disabled
128 MiB run; the ninth differed. Different audio settings and scene timing
prevent treating that comparison as proof of complete system equivalence.
The isolated renderer comparison is stronger evidence for the rendering
optimizations: all 4,096 randomized rendered lines produced the identical
digest, and all 24,000 fetch lines retained identical reads and outputs.


## Combat hot-path work (2026-10-11)

A follow-up profile sampled the slow combat interval at 70, 80 and 90 emulated
seconds. Shared-bus arbitration and VDP2 fetched-dot output were the largest
named hot paths; instruction/data cache callbacks were another substantial
cost. These profiles are in `/private/tmp/vf2-hotpath-20261011`.

Implemented host-side optimizations:

- Bus histories use contiguous storage with amortized expiry instead of a
  deque. Searches return immediately at either endpoint and reuse the final
  wait-pass result for the ownership pass. The same intervals, debt shifts,
  ownership rules and clock rounding are retained.
- Instruction and data cache hits execute in generated CPU code. All four
  ways, lowest-way selection, valid/tag checks, LRU updates and endian lanes
  are retained. Misses use the original C++ fill and bus implementation.
  Read accessors preserve their UML scratch-register contract.
- Adjacent UBC/wait monitoring flags are tested with one word load. Both
  conditions still trigger the interpreter boundary; a fallback handles a
  host layout where the bytes are not adjacent.
- VDP2 slot schedules are decoded once per line. PN/CP slot counters advance
  directly rather than dividing an absolute slot number at every iteration.
- Mosaic groups sample once and repeat the result. Dot output is specialized
  by colour depth, including equivalent reduction buffer selection.
- Colour-effect-free, unshadowed dots select the highest-priority image
  without constructing unused second/third-image metadata. Effects, shadows,
  windows and priority ties retain their original behavior.

Verification includes 20,000 actual-method arbitration comparisons with every
interval and debt field compared; 24,000 fetch-line read traces and carried
buffers; and 4,096 rendered lines with mosaic enabled/disabled, colour depths,
resolutions and effects. The expanded renderer digest is `116ae492e69189c0`
for both reference and optimized code. ASan/UBSan checks pass.

Both CPU engines pass stale/private instruction tests, cache-array changes,
save/load, delay slots, all four data-cache ways and endian lanes, and a CCR
store that disables CE inside a sequence. All 36 device cases pass on the final binary, with the original checksum path restored. The usual subtarget rebuild succeeds.
The existing deprecated-sprintf compiler warning is unrelated to this work.

An unsampled, isolated-state 100-second paired comparison before the last
monitor/checksum refinements measured 137.00% versus 162.65% average speed.
The 80/85/90-second samples changed from 83.57/72.14/74.80% to
104.66/76.34/92.59%. All ten screenshots match byte-for-byte. These single-run
samples vary with compilation and host scheduling; they are not guarantees
for every scene or interactive input sequence.

A 230-second live-audio test of that intermediate build averaged 97.22%, with
650 underflows, 17 overflows and no audio render errors. Its late 210–225
second combat intervals averaged 86–92%, versus about 67% in the preceding
build. It had only the initial translation-cache reset on each CPU. The final combined monitor check is measured separately below.

No checklist marker or item text was changed during this performance work.
CD HLE remains the normal configuration; the preserved LLE patch still applies.


A trial that skipped backing-RAM checksums for read-only cached sequences was
rejected and removed: although isolated device tests passed, five later VF2
screenshots differed and the apparent 211% speed could not be accepted. The
full checksum path is retained. The combined monitoring check was also changed
to a direct memory test so it preserves all UML scratch registers.


Final rebuild/live-audio result: 97.33% average over 229 measured seconds,
634 underflows, 24 overflows and zero render errors. The late 220/225-second
intervals averaged 89.89/89.75%. Each CPU recorded only its initial translation
cache reset. All 23 screenshots match the preceding verified live-audio build
byte-for-byte. The final cache suite and all 36 device cases pass. Logs are in
`/private/tmp/vf2-hotpath-20261011/final-live` and the sibling test directories.

The expensive named CPU cache callbacks and bus-history searches have been
substantially reduced, and rendered output is preserved. This is not a claim
of steady 100% in every scene: the late combat still needs roughly 11% more
headroom. No emulated clock or bus wait was reduced, and video, audio, cache
semantics, effects and interrupt monitoring remain enabled.

## Additional combat fixes (2026-10-11)

Three further changes are committed separately:

- `72584573f0d`: fetched NBG output computes each eight-dot cycle origin once
  and advances the source accumulator by addition. Mosaic keeps its original
  sampling path. The renderer comparison now also covers fractional scroll,
  accumulator carries and stationary through maximum horizontal increments.
- `4a6b217296b`: CPU, DMA and external bus accesses bypass inactive UBC
  comparisons using the existing monitor gate. Live/prefetched comparisons,
  pending exceptions and unsynchronized writes keep the gate enabled.
- `b734c4dd96d`: arbitration selects nonempty peer histories once per access,
  rather than revisiting empty histories during both passes. All four requester
  slots remain supported; interval ownership and debt calculations are unchanged.

Validation: 4096 varied real-renderer lines match the saved pre-change renderer
under ASan/UBSan (expanded digest `5ff1d20ea938dd4e`); all 13 screenshots in paired
130-second renderer runs match. The UBC actual-method sanitizer fixture and
real-device DRC/interpreter tests pass. All interval histories, timing debts,
BSC state and returned cycle costs match the unchanged four-requester reference
over 20000 randomized arbitration accesses under ASan/UBSan.

The rebuilt executable completed an unsampled 230-emulated-second VF2J run with
normal video and live CoreAudio output: **98.98% average speed, 257 underflows,
17 overflows, zero render errors**. All 23 screenshots match the preceding
two-fix live-audio run. That preceding run measured 98.31%, 408 underflows and
30 overflows, and included a five-second combat profile. The earlier reported
build measured 97.33% and 634 underflows; its screenshots have a different scene
phase, so these older totals are indicative measurements rather than a strictly
identical-state benchmark. The paired renderer-only runs measured 167.46% and
170.18% average speed, with a small combat gain (103.41% to 103.82%).

Late-combat five-second intervals mostly reach approximately 100% in the final
run; the 220-second interval measures 96.12%, and initial combat compilation
still causes dips. These changes reduce overhead and playback starvation; they
do not establish uninterrupted 100% speed or zero audio underflows. Normal
Saturn still uses CD HLE. Checklist contents and completion markers are unchanged.
Logs, frozen sources/binaries and captures: `/private/tmp/vf2-output-20261011/`.

# Fighters Megamix B-bank latency experiment

Tested 2026-10-09. The proposed NBG2/3 B-bank pattern-name latency change from three slots to four does **not change the recorded B0/T1 PN, A0/T0 CP case in the current fetch implementation**. It is not a demonstrated fix. Production fetch code was restored and rebuilt; the Megamix checklist marker remains incomplete.

## Candidate and minimized test

The candidate records the bank of each pattern-name read and requires four slots before NBG2/3 can use a B0/B1 result. A-bank behavior and NBG0/1 behavior stay unchanged. This corresponds to the alternative timing under discussion; it does not add Mednafen's pattern-specific offset workaround.

`scripts/saturn_megamix_latency_test.py` compiles baseline and candidate copies of the actual fetch header with ASan/UBSan. It compares character-pattern read addresses across eight access cycles:

- B0/T1 pattern name, A0/T0 character data: identical traces.
- B0/T5 pattern name, A0/T0 character data: different traces (positive control proving the modified latency is exercised).
- A0/T5 pattern name, A0/T0 character data: identical traces (A-bank control).

For the recorded T1-to-next-T0 schedule the PN result is already seven slots old, so both latency thresholds accept it. The earlier memory claim that changing this threshold would fix that schedule does not hold for the current implementation. This does not exclude a different issue in stage alignment, output-buffer selection, or the interpretation of the original captured schedule.

## Real game comparison

Built separate baseline and candidate Saturn binaries. Booted the Japanese Megamix CHD using retail Saturn ROMs and isolated configuration/NVRAM/output directories. Saved the baseline at frame 1800 (about 30.04 emulated seconds), then loaded that identical state into each binary.

Six corresponding replay captures at approximately 30.07, 31.02, 35.04, 40.05, 50.08 and 60.11 seconds are pixel-identical. All captured register sets have BGON=0x0001: NBG2 is disabled, so those matching startup images are not evidence about the affected NBG2 scene.

An extended baseline replay with Start-button input reached approximately 120 seconds, still with BGON=0x0001. It did not reach an affected NBG2 scene. No claim is made that these runs validate actual gameplay or reproduce the original in-game defect.

Artifacts: `/private/tmp/megamix-latency-experiment/`, including both binaries, candidate build log, original save state, baseline/candidate pixels and register dumps, and extended-run log. The local ROM/CHD copies are test inputs, not repository artifacts.

## Validation and conclusion

Candidate macOS build passed, and existing renderer/compositor ASan/UBSan fixtures passed. The restored production build also passed. No real-hardware verification was performed.

The useful negative result is specific: **latency four alone does not alter the recorded schedule and has not fixed the issue**. Closure needs an affected scene/state or a minimized trace showing the original incorrect output and the correct replacement behavior. The positive control also demonstrates that this candidate changes other schedules, so adopting it without an improvement would introduce behavior changes with no demonstrated benefit.

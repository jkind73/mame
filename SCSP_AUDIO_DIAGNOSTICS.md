# SCSP audio diagnostics — 2026-10-09

The supplied scsptest August 2024 disc, ADPCM April 2021 demo and CroNSF 0.02 binary/source were examined. Archives and isolated captures are under `/private/tmp/saturn-audio-diagnostics-20261009/`.

## Implemented corrections

* The 1Fs interrupt pending flag now advances with its interrupt enables off; enable writes preserve sample-clock phase.
* SCSP timer overflow uses 256 counts, a shared prescaler phase and live count readback, including byte writes.
* Slot and DSP coefficient register masks match the diagnostic expectations.
* Pitch bit 10 supports stationary phase; stack samples retain their actual 16-bit amplitude. FM writeback has five-slot delay and honors inhibited writes.
* Noise/zero sources do not terminate through PCM loop logic. PCM retains its final sample, and inactive direct slots retain their specified bias.
* DSP MIXS uses two persistent banks. The first contribution replaces a channel, subsequent contributions accumulate, and untouched channels retain CPU writes.
* Saturn HLE CD sector transfers now accept 16-bit reads as well as mixed 16/32-bit reads. Transfer completion releases sector mode for subsequent metadata reads. Debug reads do not consume sector data.

## Validation

The supplied SCSP suite reaches Done with all 20 enabled tests passing in both DRC and interpreter builds. This covers register/memory access, timers, sample sources, FM and DSP operations. `scripts/scsp_disc_test.py` and `scripts/scsp_suite_test.lua` reproduce real-disc runs with isolated state and WAV capture. The actual DSP and CD transfer methods also pass ASan/UBSan fixtures in `scripts/scsp_dsp_bank_test.py` and `scripts/saturn_cd_word_test.py`.

The additional `scspadpcm-test-april3-2021.zip` supplies the previously missing built disc. A 70-second DRC run executes the demo and produces sustained audio: 48 kHz stereo, 3,360,001 frames, 6,206,860 nonzero samples. About 3.26% of samples reach a clipping limit. This is a playback smoke test; waveform accuracy and whether clipping is intentional remain unverified. Capture: `/private/tmp/saturn-audio-diagnostics-20261009/adpcm-final/drc/audio.wav`.

CroNSF exposed the CD word-transfer defect: before the fix it reported “Missing PVD/EVD”; afterward it displays its Tests directory. Automated controller input still fails to select/play the bundled NSFs in both CPU modes. Its slave remains at interrupt mask E0, suggesting a watchdog/interrupt handoff issue. Its source headers write the watchdog at FFFFFE88, while the SH7604 manual specifies FFFFFE80; the binary contains no literal FFFFFE88, so this source discrepancy does not establish the binary cause. No undocumented register alias was added. CroNSF music playback has not passed.

No results have been compared with recordings or traces from real Saturn hardware. These tests establish diagnostic behavior and executable playback, not complete audio fidelity. No checklist item was added, removed or reworded for this work.

Follow-up 2026-10-10: built-in SCSP DMA now uses scheduled transfer phases and contention waits, and 1Fs interrupt behavior is verified through the actual CPU paths. The August 2024 suite again passes all 20 enabled tests on both SH-2 cores. See [SCSP DMA/sample implementation](SCSP_DMA_SAMPLE_IMPLEMENTATION.md) for implementation, tests and the explicit hardware-timing limitations.

The Rel.2.5 SCSP errata follow-up corrects the physical RAM allocation, checks all nine official entries, and verifies SBCTL, MIDI status and existing RESET/TAS behavior on the real device graph. The supplied audio suite remains passing on both cores. See [SCSP Rel.2.5 errata](SCSP_REL25_ERRATA.md) for the complete disposition and hardware-verification limits.

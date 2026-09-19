# SCSP envelope generator: native rate qualification (SND-02)

## What was already implemented

`scsp_device::EG_Update` models the chip envelope as the hardware does: the
attenuation domain 0x000 (loudest) to 0x3FF (silent), a segment rate
(AR/D1R/D2R/RR) adjusted by key-rate scaling and the octave, doubled and
clamped to six bits, an update gated into every `2^counter_shift[eff]` samples
and an eight-phase increment pattern `increment[eff][phase]`. The tables follow
Ymir's `IncrementEG` (hardware-tested) with mednafen `RunEG` and
SaturnRecomp `env_tick` as second and third sources; the 2003/2004/2007 source
comments about "corrected envelope rates" describe the earlier
millisecond-based tables this replaced.

The primary manual documents the behaviour but **not** the rates: ST-077-R2
§4.5 describes the states, EGHOLD, DL, KRS/0FH scaling, LPSLNK and the
"change volume is minimum (0)" meaning of a 00H rate register, and shows the
attenuation shape in Figure 4.14 - no numeric table. The rates therefore rest
on the emulator cross-check, which is what this fixture qualifies.

## What was missing

There was no runtime evidence that the emulator's envelope actually advances on
that gating grid: an extracted-method check of the tables cannot see a wrong
counter (the pre-fix LFO defect - a 256x scale error - passed exactly such a
method harness), a wrong sample-clock source, a wrong segment transition or a
slot that never goes inactive.

## Native measurement

`saturn_pending/test_scsp_eg_runtime.py` drives one SCSP slot with a constant
(DC) carrier and captures the SCSP stream through the per-device Lua sound hook
(`-sound none`, so no OSD audio device is involved). The caption is reduced to
the chip's own resolution: the slot multiplies the sample by a 12-bit
attenuation table entry, so the capture is reported as
`q = round(amplitude / full_scale * 4096)` and compared against the same table
computed in Python - the comparison happens in the domain the hardware uses.

The model is a re-implementation of `EG_Update`; the only unobservable
parameter is where the free-running sample counter sat when the capture began,
recovered by search (all phases where the widest segment period is small,
otherwise the step grid pins it down). Because the trigger's first visible
audio sample can lag the register write inside an audio buffer, both traces are
anchored on their own trigger edge (key-on jump, key-off drop, or - for a
release out of a decay plateau, where the level is continuous - the first
release step).

### Cases (22)

* attack AR = 1F/10/08/04 (geometric ramp), AR = 00 documented hold
* KRS = 0F scaling off, KRS = 0 octave-neutral, KRS = 2 with OCT = B (+5 steps)
* decay D1R = 1F/10/04, D1R = 00 hold, DL = 08 and DL = 00 plateau selection
* decay-2 D2R = 10 after a DL = 04 plateau, D2R = 00 sustain
* release RR = 1F/10/08/04, RR = 00 hold, RR = 08 with KRS = 3/OCT = A, and a
  release continuing from a decay plateau (KRS-scaled RR = 0C)
* EGHOLD = 1 with a live AR ramp and D1R decay behind the held 000H

The documented holds (AR=0, D1R=0, RR=0, D2R=0, EGHOLD) are additionally
asserted against the trace itself, not only through the model.

### Result

All 22 cases match the tabulated model **exactly** (0.00 tolerance units) on all
four profiles - `saturnjp` interpreter, `saturnjp` DRC, `saturneu` (PAL) DRC and
`stvbios` (ST-V) DRC - against CI build 35411489296,
binary SHA256 26eef1e732ab77460c3cf4b5c05f7c10fad12693a4f6308fc9ffe60a64d01e4d.
No emulator change was needed: the envelope engine was already correct.

One finding came out of writing the model: the engine samples the level *before*
the update, so a segment change takes effect on the next sample while the
increment already computed for the current one is still applied. The first
draft of the model transitioned one sample early and the DL = 00 case exposed
it (the measurement rises by one D1R increment and then holds, the early model
held at 000H). The model was corrected to mirror the source; this is a fixture
defect, not an emulator defect.

## Controls

* `saturn_pending/test_scsp_eg_runner.py` (no emulator execution): a transcript
  synthesised from the model is **accepted**, and 16 mutants are rejected -
  non-zero exit status, missing armed/done markers, a Lua error, missing or
  silent calibration, unknown case, missing case, a run-length table that does
  not cover the capture, a doubled attack rate, a linear attack, a release one
  table step slower, a wrong DL plateau, EGHOLD ignored, the documented AR=0 and
  RR=0 holds drifting, and an all-silent capture.

## Files

* `live-saturnjp-interpreter.log`, `live-saturnjp-drc.log`,
  `live-saturneu-drc.log`, `live-stvbios-drc.log` - full live transcripts
  (per-case model error in tolerance units).
* `invocation-*.json` - system, engine, binary/BIOS/Lua digests per profile.

## Limits

The fixture qualifies the envelope *rate structure* (gating grid, increment
patterns, segment transitions, holds) at 44.1 kHz on four profiles. It is not a
claim about per-game audio, about the dB law of the 12-bit attenuation table
beyond its own resolution, or about envelopes under SCSP DMA/DSP contention.

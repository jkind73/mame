# SND-02 SCSP slot LFO: LFORE reset semantics and phase precision

Two documented defects in the slot LFO block, fixed together because they share
one code path (`LFO_ResetHold`, `PLFO_Step`, `ALFO_Step`, `LFO_ComputeStep`) and
one harness.

## 1. LFORE was decoded but never acted on

`#define LFORE(slot)` existed with **zero call sites**, so writing LFORE=1 did
nothing and the documented key-on phase-reset idiom (set LFORE=1, clear it to
start the oscillator) could not work.

Primary ST-077-R2-052594 p.89 (SDK pin
`0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, PDF blob
`9383eb13fe65c807e3ec48f32e284b9999cd71b8`):

> LFORE (R/W) ;LFO REset — Sets the LFO reset to yes or no. If this bit is set
> to "1", the LFO is reset. If "0" is written then operation starts.

and p.37:

> when using LFO in low-frequency modulation with the LFO wave form selection at
> noise (ALFOWS="3H", or PLFOWS="3H") …, reset with the "LFORE" will not
> function. The frequency also cannot be changed.

Cross-checks (inspection only, no code copied):

- Beetle `1382b85dcad2e98ef9a67426a775ba548eaf0c68`, `mednafen/ss/scsp.inc` blob
  `79ac3c31102f740b0faf432de696062f25e90485`: `SS_SCSP_RunLFO` parses
  `s->LFOReset` from bit 15 and forces `s->LFOCounter = 0` while it is set.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`, `rtl/Saturn/SCSP/SCSP.sv`
  blob `402dcb6eedca98547c34a799fea3dc56eddbca5a`: `if (OP1_SCR6.LFORE)` forces
  both `NEW_LFO_DIV` and `NEW_LFO_DATA` to zero.
- Ymir has no LFORE handling.

Implementation: `LFO_ResetHold(slot)` is evaluated once per sample in
`UpdateSlot`, before either modulation path, and zeroes the phase of each LFO
whose waveform is not noise. Both step functions take the resulting flag and do
not advance a held accumulator, so a held LFO reports its reset-phase output
exactly as Beetle and MiSTer do. The hold also applies when the modulation depth
is zero, because the LFO *block* is held reset: `Compute_LFO` deliberately does
not recompute anything at depth 0, so without the per-sample hold a later depth
change would start from a stale accumulator instead of the reset phase.

The p.37 noise exemption is modelled (neither cross-check does): with
ALFOWS/PLFOWS = 3 the phase keeps running and the output keeps following the
LFSR. The second half of that sentence ("the frequency also cannot be changed")
needs no code: in noise mode the output ignores the accumulator entirely.

## 2. Every LFOF setting below 0.68 Hz produced no modulation at all

`LFO_ComputeStep` computed an 8.8 increment,
`(u32)(256 * LFOFreq[LFOF] * 256 / rate)`. At 44.1 kHz that is
`LFOFreq * 1.4861`, so Table 4.21's slowest eight settings truncate to **zero**:

| LFOF | Hz | old increment (8.8) | new increment (8.24, 2^32 wrap) |
| --- | --- | --- | --- |
| 00H | 0.17 | 0 | 16557 |
| 01H | 0.19 | 0 | 18504 |
| 02H | 0.23 | 0 | 22400 |
| 03H | 0.27 | 0 | 26296 |
| 04H | 0.34 | 0 | 33113 |
| 05H | 0.39 | 0 | 37983 |
| 06H | 0.45 | 0 | 43826 |
| 07H | 0.55 | 0 | 53565 |
| 08H | 0.68 | 1 | 66226 |

A zero increment freezes the phase, so slow vibrato/tremolo never happened.
Beetle (`LFOTimeCounter = (((8 - (LFOFreq & 3)) << 7) >> (LFOFreq >> 2)) - 4`,
i.e. ~1020 samples per phase step at LFOF=0) and MiSTer (`LFOFreqDiv`, a 10-bit
divider) both reach the slow end; MAME did not.

Fix: the phase accumulator is now 8.24 (`u32 phase`, one wrap = one cycle, and
the 8-bit table index is the top byte, `phase >> LFO_PHASE_SHIFT`), so one cycle
is 2^32 phase units and the per-sample increment is `frequency * 2^32 / rate`,
rounded to nearest with `std::llround`. Every Table 4.21 setting then oscillates
within 0.1% of its documented frequency (asserted in the harness and measured
natively, see below). The rate still derives from `clock()/SAMPLE_CLOCKS`,
preserving the earlier ST-V/clock correction; residual error is the rounding,
≤0.5 unit per sample (≈0.003% at 0.17 Hz).

> A first draft used `frequency * 2^24 / rate` (256× too small, i.e. the old
> 8-bit index shift retained while the accumulator widened to 32 bits). It made
> every rate run 256× slow — 172.3 Hz became ~0.67 Hz and the slow end sat at the
> reset phase. The method harness encoded the same wrong scale, so it passed.
> Native audio capture (below) exposed it; both the code and the harness are now
> pinned to `frequency * 2^32 / rate`.

`LFO_SHIFT` (output scaling, `p << (SHIFT - LFO_SHIFT)`) is unchanged, and the
dead `#if LFO_SHIFT != 8` masking is gone because the u32 accumulator wraps
naturally at exactly one cycle.

Also removed in this change: the unused `MOFULL/MOEMPTY/MIOVF/MIFULL/MIEMPTY`
macros, which read stale register-file bits and were superseded by the derived
MIDI status in `ea928158`. Their old definitions are useful corroboration for
that work — they place MOFULL at 0x1000, MOEMP 0x0800, MIOVF 0x0400, MIFULL
0x0200 and MIEMP 0x0100, exactly the bit positions recovered from Figure 4.3's
geometry and from Beetle's flag shift.

## Tests

`regtests/saturn/test_scsp_lfo.py` compiles and executes the real
`LFO_Init`, `Compute_LFO`, `LFO_ComputeStep`, `LFO_ResetHold`, `PLFO_Step` and
`ALFO_Step` bodies plus the extracted static tables and slot-register macros
under UBSan — **328578 cases**:

- the 256-entry saw/square/triangle tables for both LFOs and the flat depth-0
  scale tables;
- Table 4.21's 32 frequencies compared against values hardcoded from the
  printed manual;
- **all 65536 LFO register words**: waveform→table mapping, depth→scale
  mapping, the noise flag, "no depth means no recomputation" (sentinel state
  must survive), `Compute_LFO` must not touch the phase, per-setting increment
  within 1% of the documented frequency and correctly rounded, monotonic in
  LFOF, and identical increments for the phase and amplitude LFOs;
- **all 65536 register words × both noise flags** for `LFO_ResetHold`: return
  value equals LFORE, phases zeroed only for non-noise LFOs, and
  increment/table/scale/noise left untouched;
- step behaviour for all 32 frequencies × 4 waveforms × 7 depths: a held LFO
  returns the reset-phase output and stays there over repeated samples, the
  released oscillator restarts from zero and accumulates exactly, the
  accumulator wraps to index 0 after precisely one cycle, and in noise mode the
  reset does not function while the output keeps following the LFSR.

Source-structure checks pin the per-sample wiring that the extracted functions
cannot show on their own: `UpdateSlot` evaluates `LFO_ResetHold(slot)` exactly
once, before both step calls, and passes the flag to both.

Twelve compiled mutants are rejected by behavioural assertions:
`lfore-ignored` and `lfore-return-inverted` (the pre-fix behaviour),
`lfore-always`, `lfore-hold-noise`, `lfore-step-noise`, `lfore-step-advance`,
`lfo-saw-square-swap`, `lfo-scale-swap`, `lfo-noise-flag`,
`lfo-depth-zero-refresh`, `lfo-lowfreq-truncate` (restores the 8.8 increment)
and `lfo-truncate-not-round`. The pre-change source
(`SCSP_LFO_SOURCE=<HEAD scsp.cpp>`) also fails, first at the low-frequency
oscillation assertion; the harness adapts its old no-flag step signatures so the
control fails an assertion rather than the build.

Full-translation-unit `g++ -fsyntax-only` on `scsp.cpp` passes, and the whole
local regression batch passes with this harness included (`regressions.log`:
72 scripts, "All Saturn regression scripts passed").

## Native qualification (audio capture)

The Saturn/ST-V drivers previously exposed no audio capture path, so the change
was originally method-level only. A native path was added for this work: the
per-device Lua sound hook (`emu.register_sound_update`, driven by the `:scsp`
device's own output stream) captures the real mixer values without any OSD audio
device or private-state patching, and works with `-sound none`.

`saturn_pending/test_scsp_lfo_runtime.py` keys one slot on a constant (DC)
carrier and measures the amplitude envelope the slot ALFO applies, plus a sine
carrier to measure the pitch swing the PLFO applies:

- **all 32 Table 4.21 rates** (square ALFO, depth 7): each oscillates within
  0.1% of the printed manual value (e.g. 0.1700 vs 0.17, 172.2918 vs 172.3 Hz),
  and within 1% of the quantized `round(f * 2^32 / rate)` step;
- **LFORE hold** (square and saw): flat at the reset-phase level (index 0), a
  −24 dB attenuation of the unmodulated level;
- **noise exemption** (p.37): with ALFOWS=3 the output keeps fluctuating under
  LFORE=1, and runs under LFORE=0;
- **depth 0**: constant full level, no modulation;
- **phase LFO** (square PLFO, depth 7 = ±494 cents, sine carrier): the
  windowed zero-crossing rate alternates between the two pitch bands at the
  documented rate for LFOF 00H and 07H (both previously dead).

The same fixture is a differential control: the pre-fix binary (build
`35409599120`, commit `7a86f4b7`) reports **no modulation** for LFOF ≤ 07H,
**continues modulating under LFORE=1**, and measures the mid-range rates 256×
slow — exactly the three defects above — while the fixed build
(`803be0ad`, build `35411489296`) passes all 39 cases × 4 profiles
(saturnjp interpreter + saturnjp/saturneu/stvbios DRC). A result-parser
negative-control harness rejects malformed/truncated/inconsistent transcripts.

Full consumer: `saturn_pending/validate_ci_runtime.sh` re-runs every prior gate
plus the four BIOS/background replay configurations with the `scsp-lfo` phase
added. Save states from before this change are not loadable: `SCSP_LFO_t::phase`
widened from u16 to u32 (as with the MIDI arrays in `ea928158`, MAME reports the
mismatch rather than mis-restoring).

## What this is not

This qualifies the LFO block's *oscillation* (rate, reset hold, noise
exemption, depth gating) against the documented register model. It is not a
claim that any specific game's audio is now correct: per-game timing, the DSP
effect chain and the overall mix are still exercised only through the existing
BIOS/background replay gates, and no game waveform has been captured. LFORE is
write-only and the LFO phase is not register-readable, so the reset-phase
*level* (not the internal phase) is what is observed natively.

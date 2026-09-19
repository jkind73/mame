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

| LFOF | Hz | old increment | new increment (8.24) |
| --- | --- | --- | --- |
| 00H | 0.17 | 0 | 65 |
| 01H | 0.19 | 0 | 72 |
| 02H | 0.23 | 0 | 87 |
| 03H | 0.27 | 0 | 103 |
| 04H | 0.34 | 0 | 129 |
| 05H | 0.39 | 0 | 148 |
| 06H | 0.45 | 0 | 171 |
| 07H | 0.55 | 0 | 209 |
| 08H | 0.68 | 1 | 258 |

A zero increment freezes the phase, so slow vibrato/tremolo never happened.
Beetle (`LFOTimeCounter = (((8 - (LFOFreq & 3)) << 7) >> (LFOFreq >> 2)) - 4`,
i.e. ~1020 samples per phase step at LFOF=0) and MiSTer (`LFOFreqDiv`, a 10-bit
divider) both reach the slow end; MAME did not.

Fix: the phase accumulator is now 8.24 (`u32 phase`, one wrap = one cycle,
index = `phase >> LFO_PHASE_SHIFT`), and the increment is rounded to nearest
with `std::llround`, so every Table 4.21 setting oscillates within 1% of its
documented frequency (asserted in the harness for all 32 settings). The rate
still derives from `clock()/SAMPLE_CLOCKS`, preserving the earlier ST-V/clock
correction. Residual error is the accumulator's rounding, ≤0.5 unit per sample
(≈0.5% at 0.17 Hz), not an exact integer divider.

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

Full-translation-unit `g++ -fsyntax-only` on `scsp.cpp` passes.

## What this is not

LFO state is not readable through any SCSP register and the Saturn/ST-V drivers
expose no audio capture path, so this is **method-level evidence only** — there
is no native or waveform qualification, and no claim that any specific game's
audio is now correct. The change alters audible output wherever software uses
LFORE or an LFOF below 08H, so the full native consumer (BIOS/background
replays and every prior gate) is still required to show nothing else regressed.
Save states from before this change are not loadable: `SCSP_LFO_t::phase`
widened from u16 to u32 (as with the MIDI arrays in `ea928158`, MAME reports the
mismatch rather than mis-restoring).

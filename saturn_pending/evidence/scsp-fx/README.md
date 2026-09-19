# SCSP send-level tables and DSP effect return (SND-02)

Fixture: `saturn_pending/test_scsp_fx_runtime.py`, run against the CI build of
7bebd197 (binary sha256 `9a7d21c9...513cbd4`, the same binary as the FM/PCM/MVOL
evidence) on four profiles: saturnjp interpreter, saturnjp DRC, saturneu (PAL)
DRC and stvbios (ST-V) DRC. All four report `SCSP FX: PASS` with identical
numbers; summaries in `summary.txt`, raw captures in `live-*.log`.

This closes the *effect half* of "effects-heavy playback": the DSP effect return
path through EFSDL/EFPAN is now measured natively. The *external digital input*
half (EXTS0/1) is still open: it is fed by the CD device route, so it cannot be
driven until the CD block exists.

## Fixture hardening (the logs in this directory)

The first version of the fixture did not stop the 68000 BIOS sound program, and
one run of it measured `efreg=0000` on the very same binary - the BIOS sound
driver had replaced the DSP microprogram between the fixture's upload and its
read. The fixture now parks the sound CPU (`0x70000: bra *`, `SR=0x2700`) and
clears TEMP/ACC/MEMS through 128 real microinstructions before the effect
program, exactly as the mapped-DSP fixture does. The four logs here are that
hardened version and measure the same numbers as the original qualification;
the values below are unchanged.

## Qualified (measured on the emulator, not assumed)

| claim | measurement |
|---|---|
| direct send level (DISDL, Table 4.27) | 0.501160 / 0.251160 / 0.125854 / 0.063050 / 0.031616 / 0.015808 for levels 6..1 against 0 dB, i.e. 6.014 / 12.01 / 18.01 / 24.01 / 30.01 / 36.01 dB; DISDL 0 measured exactly silent |
| effect send level (EFSDL, Table 4.29) | same curve on the DSP return: 0.501073 / 0.250966 / 0.125803 / 0.062905 / 0.031558 / 0.015673, level 0 exactly silent |
| effect return is the DSP's EFREG value | EFREG[0] read back as 0x1232 and the return measured as a static level (span 0.000000) of 0.142151 at EFSDL 0 dB - a DC program must give a DC return |
| effect pan (EFPAN, Table 4.30) | 0x10 centre equal and non-zero (0.142151/0.142151); 0x1f hard left (0.0 in the right channel); 0x0f hard right (0.0 in the left); 0x01 = left x 0.707811; 0x11 = right x 0.707811 |

## What the tolerances discriminate

The send-level tolerance is 0.6% of the model, which is tighter than the spread
between the two readings in the field:

* ST-077 Table 4.27/4.29 label the step **-6 dB** = 0.501187 per step;
* the MiSTer core's `LevelCalc` (`rtl/Saturn/SCSP/SCSP_pkg.sv:578`) is a shift,
  `WAVE >>> (~SDL)`, i.e. **0.5 per step**.

The two differ by 0.24% at one step and 1.2% across the six steps below 0 dB, so
the measured 0.015808 (level 1) / 0.501160 (level 6) selects the dB table and
rejects the shift. `src/devices/sound/scsp.cpp` builds `m_LPANTABLE` from
`powf(10.0f, SDLT[iSDL] / 20.0f)`, and the residual 0.011% from the ideal -6 dB
value is that table's fixed-point rounding (`FIX(4.0f * LPAN * TL * fSDL)`), not
model error. The pan check separates Table 4.30's -3 dB steps (0.707946, measured
0.707811) from MiSTer's `PanLCalc` shift, which gives 0.75 at EFPAN 01H - a 5.6%
difference, far outside the 2% pan tolerance.

## Method

One slot at a time, centre-panned, captured through the per-device Lua sound
hook on the `:scsp` stream (`-sound none`), as the FM/EG/PCM/MVOL fixtures do.
The direct send level is measured as a span ratio on an 8 bit square wave; the
effect return is measured as a **static level**, because a microprogram that
leaves a constant in EFREG produces a DC return (the probe that established this
recorded no other way to observe the tables, since the mixer's effect half has
no other input).

The effect source is the microprogram already used by the mapped-DSP fixtures
(`test_scsp_dsp_runtime.py`): step 127 writes EFREG[0] from the accumulator,
which is fed from sound RAM at 0x05a08000 (`COEF[0] = 0x7ff8`, `MADRS[0] =
0x4000`, ring buffer off). The fixture requires the EFREG read-back to be
non-zero before it measures anything, so a broken DSP setup cannot be reported
as a gain result.

## Traps recorded so they are not repeated

* The Lua template used the DSP source **word offset** (0x8000) where a full
  SH-2 address was needed, so the DSP read zeros and the return was silent while
  every other part of the setup looked correct. The constant is now
  `WS_DC = 0x05a08000` and the fixture asserts a non-zero EFREG to catch it.
* Slot register 0x16 packs DISDL (bits 15-13), DIPAN (12-8), EFSDL (7-5) and
  EFPAN (4-0). Writing a DISDL-only constant silently clears the effect return
  fields, which the earlier MVOL/DSP fixtures did not care about.
* The key bits live in slot register 0x00 with LPCTL/PCM8B: `key_reg()` preserves
  the low bits, as in the PCM/MVOL fixtures.

## Not covered

EXTS0/1 (external digital input, CD-fed) and therefore the CD-DA path; the DSP
return under a *live* program (this fixture uses a static EFREG); and the mixer's
behaviour when many slots return at once.

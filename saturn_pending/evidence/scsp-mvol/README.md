# SCSP final mixer: master volume (MVOL) and DAC interface width (SND-02)

Fixture: `saturn_pending/test_scsp_mvol_runtime.py`, run against the CI build of
7bebd197 (binary sha256 `9a7d21c9...513cbd4`, the same binary as the FM and PCM
evidence) on four profiles: saturnjp interpreter, saturnjp DRC, saturneu (PAL)
DRC and stvbios (ST-V) DRC. All four report `SCSP MVOL: PASS`; the summaries are
in `summary.txt` and the raw captures in `live-*.log`.

## Qualified (measured on the emulator, not assumed)

| claim | measurement |
|---|---|
| master volume curve | all fifteen non-zero MVOL values measured exactly the shared Q8 table over 256: 2/3/4/6/8/12/16/24/32/48/64/96/128/192/256 (mvol08 = 0.09375 of the full level, mvol13 = 0.50000, mvol14 = 0.75000, mvol15 = 1.00000), monotonic |
| MVOL 0 mutes | span 0.00000 (exactly, both channels) |
| MVOL is applied to the final mix | with one to three slots the attenuator scales the whole captured sum |
| MVOL is stereo | every centre panned case has identical left and right captures (0.00000 difference) |
| overflow is clipped before MVOL (ST-077 p.100) | three full level centre panned slots sum past the 18 bit range: the measured span is 1.99997, i.e. 2/3 of the linear sum of three (0.66666), and attenuating that clipped sum scales it by exactly the MVOL gain (clip08 = 0.09374, clip04 = 0.02342 of the clipped level) |
| DAC18B selects the interface width, not a gain | the same signal measures a span ratio of 1.00000 with the bit clear and set |
| the 16 bit interface keeps the top 16 bits | on a 64 step ramp at a send level whose fixed point gain has low bits, all 16 bit samples lie on the 4/131072 grid (worst deviation 0.0655 of a 131072 unit), the 18 bit samples do not (1.9976), both captures hold 253 distinct levels, and every 18 bit level truncated to the 4 unit grid appears in the 16 bit capture (0 missing) |

## Why these numbers discriminate

The fixture is built so that the plausible wrong implementations fail it, not
just the current one passing:

* a *linear* MVOL field would measure mvol08 = 8/15 = 0.533 where the curve
  requires 0.09375 (5.7x);
* a plain 3 dB per step table would measure mvol08 = 0.25 (2.7x);
* a table with the MVOL nibble inverted (the shift is on `15 - MVOL`) would
  measure mvol08 = 0.75 and mvol14 = 0.09375, i.e. the monotonic check and every
  low value would fail;
* clipping *after* the attenuator would make clip08/clip15 1.5x the MVOL gain
  (0.1406 instead of 0.09375), which is what the ST-077 p.100 sentence about
  clipping noise forbids;
* a four times gain change on DAC18B, or a 16 bit path that does not truncate,
  fails the ratio and grid checks respectively.

## Sources and the one recorded disagreement

* ST-077-R2-052594 p.93 (final output block: direct and effect combined,
  "the final output level is adjusted by MVOL"), p.100 (MVOL and DAC18B field
  descriptions, the clipping sentence), Figure 4.3 / Table 4.4 (both fields in
  the common control word at sound address 100400H). The manual has no numeric
  MVOL table, so the curve itself rests on the implementations below.
* Ymir (pin 6d779960, `libs/ymir-core/src/ymir/hw/scsp/scsp.cpp`) and MiSTer
  (pin a95b0850, `rtl/Saturn/SCSP/SCSP_pkg.sv` `MVolCalc`) compute the same Q8
  table as this checkout (`update_master_volume()` in
  `src/devices/sound/scsp.cpp`); the fixture's MVOL_TABLE is that table.
* **Recorded disagreement:** Ymir (line 1033) and MiSTer (`MVolCalc TEMP1`)
  multiply the output by four when DAC18B is set, because their output domains
  are 16 bit and they re-normalise for an 18 bit converter. This fixture asserts
  ST-077's reading instead - a converter interface select cannot change the
  analog full scale - and the two bit truncation is measured directly. If a
  future change adopts the reference gain, this fixture fails on purpose and the
  decision must be re-argued from hardware.
* Not covered: CD-DA and effects-heavy mixes (stage 10/EXTS paths), the
  ping-pong loop question, and any analog behaviour past the DAC18B/16 bit
  interface.

## Method notes

* MVOL and DAC18B share the common control word with MEM4MB/RBL/RBP, so the
  fixture reads the word back and writes `(v & ~0x010f) | mvol | dac18b << 8`
  instead of storing a constant there.
* The key bits share slot register 0x00 with LPCTL/PCM8B; `key_reg()` preserves
  the low bits (a constant key-on write silently changes the slot's format).
* One slot at 0 dB, centre panned, spans 1.0 of the captured range (the pan
  table's fixed point unity is half of the 18 bit full scale), so the fixture's
  unit for the Q8 table and for the 4/131072 DAC grid is exactly 131072 counts.
* Wave form areas: 0x2000 8 bit ramp (64 steps of 4 units, three cycles),
  0x3000 8 bit square (0x40/0xC0). The two areas must not overlap: an earlier
  revision wrote the square at 0x2600, inside the ramp's 3072 byte extent, and
  measured the ramp while believing it was measuring the square (the ratio
  based MVOL checks still passed, the absolute span check exposed it).

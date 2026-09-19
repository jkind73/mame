# SCSP PCM wave form playback (SND-02): what is qualified and what is not

Fixture: `saturn_pending/test_scsp_pcm_runtime.py`, run against the CI build of
7bebd197 (binary sha256 in the invocation files, the same binary as the FM
evidence) on four profiles: saturnjp interpreter, saturnjp DRC, saturneu (PAL)
DRC and stvbios (ST-V) DRC. All four report `SCSP PCM: PASS`.

## Qualified (measured on the emulator, not assumed)

| claim | measurement |
|---|---|
| PCM8B and PCM16B play the same wave form | two slots, byte identical captures (0.00000 of the span) |
| SA is a byte address and 16 bit samples are big endian | 0x4000/0xC000 sample pairs reach the level of an 8 bit 0x40/0xC0 square (ratio 1.00000), while a byte swapped DC reaches 0.00196 (1/256) |
| linear interpolation | at 0.25 words/sample over a ramp of 4 units per sample every sample advances (1.00000) |
| loop period | one 64 word loop at 0.25 words/sample takes 256.00 samples |
| reverse loop (LPCTL=2) | the ramp turns at both ends |
| no loop (LPCTL=0) | the slot plays its pass and stops at LEA (tail span 0.00000) |
| live register change | a one octave pitch write during playback changes the ramp advance by 2.00x |
| mixer pan table | DIPAN 0x1f hard left (0.50000/0.00000), 0x0f hard right (0.00049/0.50000), 0x10 centre (0.50000/0.50000); the idle capture is silent |

## Open question (recorded, deliberately not asserted)

The ping-pong case (LPCTL=3, LSA=0, LEA=64) captures a railed constant in the
fixture, while the isolated probe `probe-isolated-cases.lua` measures a healthy
triangle for the same registers - with LSA=0, with LSA=16 and after reverse-loop
cases, five times in a row. The case is reported and not asserted: it is a
difference between two test harnesses until it is understood, not evidence about
the chip.

## Method notes (traps this fixture hit)

* The key bits share register 0x00 with LPCTL and PCM8B. A key-on write of a
  constant (0x3830) silently switched every slot back to PCM8B + normal loop and
  produced a convincing but false "16 bit read is broken" signal. `key_reg()`
  now reads the configured control word back and adds only the key bits.
* The key-on transient lasts a couple of hundred milliseconds (the envelope
  starts at 0x280 attenuation), so captures start 250 ms after key-on except
  where a case deliberately measures the first pass (`loopOff`).
* A voice released with RR=0 keeps sounding: slots must be keyed off and allowed
  to settle, or the previous case contaminates the next measurement.
* DIPAN 0x00-0x0e pan right (0x0f hard right), 0x10-0x1e pan left (0x1f hard
  left); this matches `m_LPANTABLE`/`m_RPANTABLE` in `src/devices/sound/scsp.cpp`
  and the measurements above.

## Probes kept as evidence

* `probe-square-and-ramp.lua` - square and ramp wave forms at 0.25 and 1 word
  per sample, 16 bit periods counted in samples.
* `probe-isolated-cases.lua` - the loop-mode and format cases in isolation,
  which is where the ping-pong loop was measured healthy.
* `probe-pan-table.lua` - the pan table, one slot at a time, with an idle
  control before every measurement.

The DC level/byte-order probe and the spike/address probe lived in a scratch
directory and are not archived; their measurements are reproduced by the
fixture's `order16`, `parity16` and `interp` cases, and the register level
statements they produced are in the table above.

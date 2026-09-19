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

## Resolved: the ping-pong case, both harnesses measured

The ping-pong case (LPCTL=3, LSA=0, LEA=64) captured a railed constant while the
isolated probe `probe-isolated-cases.lua` measured a healthy triangle for the
same registers. Both observations are now explained, and neither was what it
looked like:

* The probe's "ping" cases never played ping-pong. Its key-on write is the
  constant `0x3830`, whose LPCTL field is 1, so the slot was re-configured to a
  *normal loop* at key-on - the exact trap this fixture's method notes record.
  The probe's triangle is a normal loop, measured on the slot before the key
  write took effect.
* The fixture's rail was real, and so was the earlier claim that the registers
  were fine: an address watermark in sound RAM (byte value = `(offset % 64) + 1`
  so a decoded sample gives the byte offset from SA, and a second 16 bit version
  with 32 units per word) showed the slot reading *one* address for 1200
  samples, or alternating between two, instead of sweeping LSA..LEA. With
  LSA = 16 the same code sweeps correctly and turns at LSA, which locates the
  defect exactly: the ping-pong fold tested `addr >= LEA` before the
  direction-selected boundary, and a phase that ran below LSA wraps to a huge
  unsigned address, so that test fired and mirrored the phase about LEA instead
  of LSA. With LSA = 0 the loop could never come back.

The fold now follows the direction first (forward leg turns at LEA, backward leg
at LSA), matching MiSTer `SCSP.sv` ("Alternative loop": `CUR_SO - (LEA<<1)` out,
`CUR_SO + (LSA<<1)` back, selected by `CUR_SADIR`) and ST-077-R2-052594 section
4.3. A standalone model of the corrected arithmetic holds the address inside
LSA..LEA with one pass per 256 samples at 0.25 words/sample; the native
re-qualification on the rebuilt binary is the assertion in
`test_scsp_pcm_runtime.py` (`loopP: the measured channel is silent or railed`,
`loopP:turns` and `loopP:period`).

## Native qualification after the fold fix

The fix is measured on the rebuilt binary from CI run 35431997823 (source
`5bd7f203ebf`, binary `bb872c6215bdcb406222407bc47ced61d43624846575eaaaa4a01db8c787cc16`)
on all four profiles - saturnjp interpreter, saturnjp DRC, saturneu DRC, stvbios
DRC: `SCSP PCM: PASS` on each, with the ping-pong case at `loopP:period 252.00`
(JP interpreter, JP DRC, ST-V DRC) or `256.00` (PAL DRC) against a one-pass
expectation of 256.00 samples at 0.25 words/sample, and `loopP:span 1.96875`
(the ramp spans 252 of its 256 levels on a sweep, so the captured span is 252/128).
The same runs keep every earlier measurement at its qualified value
(`loopN:period 252.00-256.00`, `loopOff:tail 0.00000`, `parity8/16:diff 0.00000`,
`order16:ratio 1.00000`, `interp:advance 1.00000`).  The pre-fix binary of the
same source line failed exactly on `loopP` ("the measured channel is silent or
railed"), so the case discriminates the defect.  Per-profile logs, summaries and
invocations are the `live-*`, `summary-*` and `invocation-*` files here.

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

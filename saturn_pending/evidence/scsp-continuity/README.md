# SCSP sound-state continuity (SND-05)

`saturn_pending/test_scsp_continuity_runtime.py` takes a **scheduled save and
load while sound generation is moving** and measures whether the SCSP's own
state comes back. Each case poisons the live state between the save and the
load, so a load that does not restore the state it saved cannot pass.

| case | what moves | measurement | poison | result |
| --- | --- | --- | --- | --- |
| `env` | envelope in slow decay (AR 1F, D1R 4, DL 0, square wave in a loop) | mean level of a 1024 sample window before and after the load | D1R is set to 1F (fast decay) while the state is saved | level ratio 0.99752 / 1.00203 / 1.00249; the EG register reads `011f` after the load, not the poisoned `07df` |
| `wave` | 4096 sample staircase ramp in a normal loop at OCT 0xE | per-sample slope of the ramp, and the ramp value at the head of the first window after the load against the value at the save | one octave up (OCT 0xF) while the state is saved, and then **100 ms of live playback at twice the rate** before the load | slope 0.0001241 -> 0.0001196 per sample (0.96x); the value at the load differs from the saved one by 0.000000 (JP) / 0.001953 (EU, ST-V, one staircase level of 1/128); the pitch register reads `7000` after the load, not the poisoned `7800` |
| `irq` | SCSP timer A requesting level 6 through SCIEB/SCILV0 | interval between expiries, read as the SCIPD request bit and acknowledged through SCIRE | the request is acknowledged while the state is saved | the request is pending before the save and pending again after the load; the median expiry interval is 23.0 ms both times, with exactly **one** partial interval after the load (`23,23,1,23,23,23`) |

The `wave` poison is chosen so that the two failure modes are far apart: a phase
that restarts at SA reads about -1.0, and a phase that is not restored at all
would have run 100 ms at double rate and land about a whole sign of the range
away. The value at the load is asserted within a quarter of the range.

## Method notes (learned while building this fixture, and why they matter)

* **The sound hook hands out ~40 ms batches.** A 46 ms capture window can
  deliver 1764 samples (40 ms) or 2048 samples (a window that straddles two
  batches). Rates measured per *emulated second* therefore differ by up to 15%
  between windows of the same length; everything here is measured **per
  delivered sample** instead. The first version of this fixture reported a 1.14x
  rate change across the load that was entirely this artefact.
* **MAME's state file write and read are scheduled.** `m:save()` returns before
  the file exists (the fixture waits for it and uses a fresh file name per case
  so a stale file can never be loaded), and the *saved phase* is the phase at
  serialisation, a frame or two after the notifier fires. `m:load()` likewise
  applies a frame later, which is why the post-load window is only read after
  the post-load notifier.
* **The sound 68000 must be held.** It owns the same registers, and with it
  running it re-programmed the slot under test within 100 ms of the load. The
  fixture holds it through the board's own path: SMPC SNDOFF (07H) on Saturn,
  SMPC PDR2 bit 4 on ST-V.
* **The pending timer request re-pends by itself** while the counter sits on
  0xff, so the ack poison is only counted as applied once the bit has been seen
  clear, and the counter is deliberately left away from 0xff before the save.

## Limits (what this does not claim)

* Not analog audio, not the audio buffer contents across the load, not audio
  latency; the measurement is the SCSP's digital stream through the device hook.
* Not in-flight DMA timing, not the CD audio path (the CD block does not exist
  yet, see SND-02), not the SCSP's MIDI transfer in flight.
* The `irq` case asserts the *request* and the expiry cadence, not the sound
  CPU's exception latency; the sound CPU is held in reset for all three cases so
  that nothing else acknowledges the request.

## Runs

Binary `9a7d21c93dd45316933e610193766e66bbc996216a505b2f4855fd761a51cbd4`
(pre-ping-pong-fix build) on all four profiles - saturnjp interpreter, saturnjp
DRC, saturneu DRC, stvbios DRC: all `SCSP_CONT PASS cases=3` with the numbers in
the table. Per-profile logs, the exact Lua and the invocation are in the
directories next to this file; `report.txt` in each holds just the report lines.

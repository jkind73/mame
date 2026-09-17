# Integrated follow-up patches

Both patches in this directory are now applied to production source and their
regression tests. They are retained as historical review artifacts against
`8f2c12ff`; **do not apply them again**. The native build that was measuring that
revision was lost during workspace restoration and has no completion result.
The integrated revision is being rebuilt and must earn its own live acceptance.

Current checks on the actual checkout:

- `python regtests/saturn/test_ioga_legacy.py`: 5,124 counter, inspection,
  alias and input cases pass.
- `python regtests/saturn/test_scsp_phase.py`: 49,152 ideal-clock and 49,152
  real-MAME-attotime rearm, restore and IRQ-deadline cases pass.
- `python regtests/saturn/test_scsp_reset.py`: 24 dirty reset, IRQ and
  re-enable cases pass.
- Rearm, load and quantization mutations each compile and assertion-fail.
- Production SCSP and ST-V translation units pass C++20 syntax checking with
  narrowing errors enabled. Existing CD and runner checks also pass.

The phase fixture uses real `attotime` conversion code, but its event queue and
save restoration are stand-ins, not a linked MAME save manager. LFO and volume
callbacks are stand-ins. No live audio, cabinet or software acceptance follows
from these checks. Full integration status is in
`regtests/saturn/handoff/integration.md`.

## Scope and reference

The IOGA change makes legacy inspection reads preserve the counter-byte cursor,
matching the existing 315-5649 device. Ordinary CPU reads are unchanged.

The SCSP change saves timer time origins, preserves restored sub-tick phase,
rearms from the counter's tick origin, and reconciles the quantization of
`attotime::from_ticks` with `as_ticks` at a scheduled boundary. The first reviewed
candidate passed ideal-clock tests but produced a zero-delay rearm with real
MAME time conversion; that defect was caught and corrected before integration.

Primary: Sega ST-077-R2-052594, SDK revision
`0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, PDF blob
`9383eb13fe65c807e3ec48f32e284b9999cd71b8`, printed pp.93–94 (PDF 105–106),
https://github.com/jkind73/saturnsdk/ . The manual's longest-time table implies
256 cycles at reload zero whereas its formula says 255. The reload-on-next-tick
policy is therefore retained rather than silently replaced by a guessed timing
policy. This is scheduling/save consistency work, not resolution of that
hardware discrepancy. STV-03, SND-03 and SND-05 remain open.

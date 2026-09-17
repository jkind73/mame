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


## Current regression batch and auxiliary live timer fixture

The full ROM-free batch on `10579b9c` completed: **53 scripts**, final
`All Saturn regression scripts passed.` marker present. The three optional
live-device scripts skipped because the native binary is not yet built; these
skips are not CD/cart/backup acceptance. The gated native run must execute them
again and require their actual completion markers. Its source inputs remain
unchanged by this documentation/auxiliary-tool checkpoint.

`test_scsp_timers.py` in this directory adapts the supplied live fixture to all
three timers and eight prescalers, correct SCIRE acknowledgement, explicit
clear-before-reassert assertions, absolute executable/ROM paths and strict
completion/error checking. It isolates NVRAM/configuration in temporary folders.
Python syntax and `test_scsp_timer_runner.py`'s 10 fake-executable protocol cases
pass; **the live fixture has not run against MAME yet**. Frame-rate sampling
cannot establish sub-tick reload or restore phase, and no such claim is made.

After the integrated native binary is built:

```sh
python saturn_pending/test_scsp_timers.py --executable ./saturn --rompath ./regtests
```

This auxiliary fixture lives outside the frozen build/test input trees so it
can be prepared and preserved while the baseline run continues. It is not part
of the gated run's automatic acceptance; record its separate execution result.

## Build persistence after repeated workspace resets

The native build started at `10579b9c` was lost during another workspace reset;
its logs and dependencies are absent. It has **no completion result**. Production
changes remain recovered from GitHub. Do not inherit runtime acceptance from it.

`.github/workflows/saturn-integration.yml` prepares a durable Ubuntu 22.04 build
and artifact, restricted to this session branch. It uses real SDL dependencies,
two compiler jobs, a compiler cache, pinned checkout/artifact actions, and
read-only repository permissions. No BIOS or game images are uploaded. The
artifact includes the executable, source/tree IDs, binary hash, linked-library
list and build/validation/regression logs. A `status.txt` PASS only certifies
build/configuration/ROM-free checks; optional BIOS fixtures still skip on CI.
Ubuntu 22.04 is used for a glibc baseline compatible with the Debian 12 sandbox.

This requires GitHub Actions to be enabled for the repository. A pushed workflow
is not evidence of an executing job. Record the actual run ID/status before
claiming the durable build is running. Failed jobs may retain diagnostic-only
artifacts without an executable or success marker.

# Reviewed follow-ups, not yet applied

`ioga-inspection.patch` is based on the ST-V source at `8f2c12ff` and fixes
inspection reads advancing the legacy counter-byte cursor. The 315-5649 device
already guards the same action with `side_effects_disabled()`; this brings the
legacy handlers used by specialized ST-V configurations into agreement without
changing ordinary CPU reads, mappings, counter math or callbacks.

The patch includes a production-function extraction test. Fresh results:
5,124 counter/peek/alias/input cases pass with the fix. The original production
function compiles and assertion-fails on cursor preservation during a peek.
This is MAME debugger API correctness, not new silicon/cabinet timing evidence.

This work is preserved as a patch while the native integration run measures the
unchanged active source. Do not mistake it for an applied or linked-validated
feature. Review and apply after that run with:

```sh
git apply --check --unidiff-zero saturn_pending/ioga-inspection.patch
git apply --unidiff-zero saturn_pending/ioga-inspection.patch
python regtests/saturn/test_ioga_legacy.py
```

STV-03 remains open. The supplied broader serial/counter-reset patch remains
separate and unapproved; this patch does not import it. Keep pending work on the
assigned branch and push it before long-running validation, rather than leaving
it only in an external sandbox directory.

## SCSP timer phase and save restoration (SND-03/SND-05)

`scsp-timer-phase.patch` is a reviewed, syntax-checked candidate against the
active `8f2c12ff` source; it is **not applied or linked-validated**. It includes:

- Saving each timer's `base_time` alongside its counter/reload/prescaler, and
  preserving it at post-load rather than replacing it with restored machine
  time. MAME's save manager explicitly supports `attotime` (`save.h:258–266`).
- Rearming from the last counter-tick origin rather than adding whole periods
  to an arbitrary current time. A fractional rearm must not delay the IRQ.
- Reconciling `as_ticks` with `from_ticks` at a quantized scheduler boundary.
  The first candidate passed ideal-clock tests but failed with real MAME
  `attotime`: the counter stayed one oscillator clock short and rearmed with
  zero delay. The revised candidate uses the scheduled quantized boundary
  before deciding whether another counter increment is due.

Fresh checks: **49,152 cases with ideal oscillator clocks plus 49,152 with real
MAME attotime conversions**, spanning all three counters, all eight divisors,
all counter/reload values, pending/nonpending loads and four fractional phases.
They check no-op rearm, restore, no premature IRQ, IRQ at the expected boundary,
and the next periodic deadline. The existing 24 dirty reset/IRQ/re-enable cases
also pass. Three mutations (relative-to-now rearm, post-load rebase, omitted
quantization reconciliation) compile and fail assertions. The unmodified source
also assertion-fails the initial deadline regression. The full candidate SCSP
translation unit passes C++20 syntax checking with narrowing errors enabled.

The test queue is a stand-in; restore copies the registered fields and machine
time, not the actual save manager. LFO/volume callbacks are stand-ins too. This is
not live audio, boot, software or hardware acceptance. A linked save/load and
sound regression run is still required before applying/promoting this change.

Primary research: Sega ST-077-R2-052594, SDK commit
`0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, PDF blob
`9383eb13fe65c807e3ec48f32e284b9999cd71b8`, printed pp.93–94 (PDF 105–106),
read freshly from https://github.com/jkind73/saturnsdk/ . The manual gives the
8 divisors and FF interrupt condition, but the longest-time table implies 256
cycles at reload zero whereas the formula says 255. The supplied review's
one-cycle discrepancy is therefore not silently turned into a new hardware
policy here. Reload-on-next-tick behavior is retained; this patch addresses
internal scheduling and restoration consistency only.

After the frozen baseline run, review/apply with:

```sh
git apply --check --unidiff-zero saturn_pending/scsp-timer-phase.patch
git apply --unidiff-zero saturn_pending/scsp-timer-phase.patch
python regtests/saturn/test_scsp_phase.py
python regtests/saturn/test_scsp_reset.py
```

Both sound parents remain open, and this patch makes no working-flag change.

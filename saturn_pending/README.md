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

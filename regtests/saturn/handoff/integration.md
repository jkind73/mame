# Single-agent integration status

## Reviewed cartridge/CD changes — WIP, 2026-09-17

Baseline: `4edfe4bc` (production unchanged from `125e3048`). Adapted from the
user-supplied `01a0ac86-f1f7-74c0-81dd-287e6f103c11 (1).patch`, SHA-256
`351216925207e399591f162b14c0c138e5ce9559e9988a3dbee5714b9a352567`.
The `(2)` patch is identical and was not applied. Original source license and
copyright headers are retained.

Production changes: guard empty cartridge DRAM allocations before modulo/index
access, retain existing allocated DRAM aliasing, replace cartridge boundary UI
popups with logging, check backup-RAM write counts, and preserve CD HIRQ DCHG
until acknowledgement instead of discarding it on read.

Primary CD basis: Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`,
ST-136-R2-093094, printed p.50 / PDF p.58, section 6: software detects a tray-open
condition through HIRQREQ DCHG bit 5. PDF blob:
`7e6f189f4d34cf1d79cd58e61a190e621042e5ed`. This passage was read during the
preceding review. DRAM aliasing and out-of-range bus values remain modeling
policies, not new hardware measurements.

Fresh checks for this WIP:
- 262,144 extracted HIRQ status-overlay/read/ack cases pass. Restoring the old
  DCHG-clearing read compiles and fails its assertion.
- Existing 336 extracted CD transfer cases and boot-trace tests pass.
- 24 extracted cartridge cases pass; the original empty-allocation handler
  compiles and is rejected by the sanitizer with a division-by-zero/FPE.
- 44 existing and 12 added fake-executable runner protocol cases pass.
- Python syntax and `git diff --check` pass.

The imported live CD/cart runners now reject nonzero exits, FAIL/Lua-error output
and malformed PASS markers, and use the actual `saturn` subtarget with absolute
paths. Their fake-executable tests are NOT live MAME/device acceptance.

**Pending:** full regression batch, native linked build, old/new binary tray
negative control, actual cartridge execution, BIOS/gameplay and save/load replay.
Earlier background builds and external logs did not survive workspace recovery;
no completed baseline boot or new linked result is claimed. This is a pushed
implementation WIP, not a validated release. CART-01 and CD-01 remain open.

IOGA, the incremental video patch, Agent1 CPU/bus changes and working/save-flag
promotion are excluded. A separately reviewed IOGA follow-up must discard local
receive-valid state on reset before that patch can be considered for integration.

Reproduce the remaining integrated checks with:

```sh
LOG_DIR=/home/user/saturn-validation bash regtests/saturn/validate_integration.sh
```

The checked-in runner builds with one compiler job, requires the supplied BIOS
files, rejects silent CD/cart skips, records source/binary provenance, and runs
JP DRC/interpreter, PAL DRC and ST-V DRC BIOS/background save-replay checks. It
never edits sources, commits, pushes or changes driver flags. A failed or missing
`status.txt` PASS is not acceptance. SDKs, binaries and large logs stay external;
source and the reproducible command are pushed before starting the long run.


Additional CD-01/NVR-01 implementation WIP:

- Debugger/inspection HIRQ reads now expose the live overlay without modifying
  stored HIRQ or invoking the IRQ-update callback. Real CPU reads retain their
  existing behavior. The extended 262,144-row extracted matrix includes two
  debugger reads, no-mutation/IRQ checks, CPU reads and acknowledgements. It
  fails against the preceding implementation and passes with the guard.
- Console internal backup RAM is explicitly registered with the save manager.
  `nvram_device::set_base` only handles file persistence; it does not register
  the allocation for save states. Existing cartridge allocations already do
  register their memory in `sat_slot.cpp`. This change does not alter file
  formats, hardware address decoding or ST-V's separate board configuration.
- The supplied backup-RAM fixture is extended with real save/mutate/load,
  notifier checks, and a following process checking that restored bytes persist
  at shutdown. All six runner modes use isolated temporary NVRAM directories.
  Its Python syntax and failure protocol are checked; actual save/load is
  **pending the linked build**, not reported as passed.
- The candidate console translation unit passed `-fsyntax-only` with narrowing
  errors enabled; 44 existing plus 18 CD/cart/backup runner protocol controls
  pass. These are not hardware tests. Full current-revision acceptance remains
  pending and neither CD-01 nor NVR-01 is closed.

The validation script now compares build/test input trees and BIOS checksums,
retaining its starting commit and binary hash. Checkpoint-only commits outside
those inputs do not relabel or invalidate the measured binary. Source/test/build
input changes still invalidate the result. Resume the single-job incremental
build after this implementation checkpoint; do not infer success from an earlier
interrupted build.


## Integrated IOGA and SCSP follow-ups after workspace restoration

The workspace was restored to `868d72fc` with the older mixed local patchset;
remote `1a23cf6c` was intact. The restored tracked diff and non-ROM untracked
files were archived locally before recovering the pushed branch. No unrelated
restored changes were imported. The earlier native build and its logs were
lost: **there is no linked result for that run**.

The previously reviewed `saturn_pending` IOGA and SCSP patches are now applied.
Their tests were rerun on production paths: 5,124 legacy IOGA cases; 49,152
ideal-clock plus 49,152 actual-attotime SCSP phase cases; 24 SCSP reset cases;
262,144 CD HIRQ cases, 336 CD transfer cases and boot-trace checks; 44+18 runner
protocol controls. All pass. Three SCSP mutations compile then assertion-fail.
SCSP and ST-V translation units pass C++20 syntax checking. These are extracted,
syntax and protocol results, **not linked device or gameplay acceptance**.

The SCSP fix registers timer origins for saving, preserves restored fractional
ticks, and schedules interrupts from tick origins using consistent attotime
quantization. It does not change reload policy, sound-reset wiring or working
flags. The legacy IOGA change only guards inspection cursor advancement.
Detailed scope and the unresolved primary-reference timing discrepancy remain
in `saturn_pending/README.md`. Start a new gated native validation against this
integrated revision; no result is inherited from the lost build.


## Integrated SMPC transport and VBlank boundary follow-up

- Source `234c7abc`: native build/configuration/ROM-free checks and the complete
  live consumer passed. Six mapped two-multitap packets and a scheduled partial
  packet save/mutate/load passed with unchanged source/binary provenance.
- `smpc_hle_device::vblank_in()` is now wired to the driver's rising VDP2 edge.
  It cancels pending initial peripheral completion and CONTINUE, clears PDL/NPE
  and saved packet cursor/size, and leaves unrelated commands and the legacy
  no-controller/ST-V path alone. The callback emits no new report or IRQ.
- The driver's previous H/V edge levels are explicitly initialized, reset, and
  save-registered. Live inspection confirmed these registrations were absent
  in the 5008 baseline. Real edge-history restoration still needs qualification.
- Four live negative expiry cases were reproduced on the transport-fixed 234c
  binary before integrating timeout. 73,728 extracted combinations, four edge/
  ordering cases, eight rejected compiled mutants, and full-TU syntax checks
  support the new code but are not native timeout acceptance. The new binary
  must pass `saturn_pending/test_smpc_timeout_runtime.py` plus the other gates.
- Baseline `5008a923` now passes all four 1,042-case composition configurations
  (4,168 total). That result is not attributed to a newly compiled revision.
- Artifact transfer is available through the checksum-verified temporary GitHub
  API blob exported alongside an unpublished draft release. No firmware,
  sandbox token, or binary source-tree commit is involved. Native receipts and
  text logs are under `saturn_pending/`; no working flags are promoted.

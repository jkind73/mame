# Integrated follow-up patches

The IOGA inspection and SCSP timer-phase patches are now applied to production
source and their regression tests. The later SMPC port-mode patch is still pending. They are retained as historical review artifacts against
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

The first durable run is now confirmed executing:
https://github.com/jkind73/mame/actions/runs/35287036055
at source `31266601e27c2c44719d58591c57b6576a9dd61e`. Dependency installation,
source provenance and cache setup completed; native compilation started. This
is a running job, not a passed build. Push triggering worked; manual workflow
dispatch is not authorized by this session's GitHub integration and is not
needed for this run.

### Consume the artifact without another full native rebuild

After that run succeeds, download its named artifact into an external directory:

```sh
gh run download 35287036055 --repo jkind73/mame \
  --name saturn-linux-31266601e27c2c44719d58591c57b6576a9dd61e \
  --dir /home/user/saturn-ci-artifact
python3 saturn_pending/verify_ci_artifact.py /home/user/saturn-ci-artifact \
  --run-id 35287036055
bash saturn_pending/validate_ci_runtime.sh /home/user/saturn-ci-artifact 35287036055
```

The verifier requires a successful run from the named workflow/session branch,
matching run/artifact source IDs, identical local production/build/test input
trees, a complete CI success record, and a matching executable checksum. Its
checks remain active under Python optimization. Twelve synthetic positive and
failure controls pass; this does not authenticate a signed supply-chain
attestation or establish emulator behavior.

The local runtime command never rebuilds MAME. It prepares real runtime
libraries, checks local configuration, requires actual CD/cart/backup and SCSP
completion markers, and runs the JP DRC/interpreter, PAL DRC and ST-V DRC
BIOS/background replay matrix. It rechecks source/binary provenance and local
BIOS hashes at the end. Logs stay outside the checkout, stale success status is
removed, and any failure records the failing phase. Shell syntax checks pass;
**end-to-end artifact consumption and live execution are still pending**.

**First CI outcome:** run 35287036055 failed before Saturn compilation in
`3rdparty/bimg/3rdparty/astc-encoder/source/astcenc_block_sizes.cpp:1168–1169`:
GCC 11's `-Werror=maybe-uninitialized` reported `quant_mode`, `weight_bits` and
`is_dual_plane`. The log was retrieved through the web fetch tool when `gh`
redirected log/artifact downloads returned EOF. No emulator or vendor source
was changed to silence this. The workflow now explicitly installs/selects GCC
12 (the local validation compiler family), retains partial compiler caches on
failure, and exposes the final compiler diagnostics as check annotations.
The original run is failed, not running or validated; a new push-triggered run
must be checked separately.

## Pending SMPC-04 / IO-01 port-mode correction

`smpc-port-mode.patch` is **not applied** and is superseded by the combined
`smpc-transport.patch` below. Keep it as a historical review artifact only. It captures port modes from
IREG1[7:4] before either INTBACK request path. Current production code instead
reads IREG0[7:4] in the status path and leaves the previous mode unchanged in
the peripheral-only path. This makes the low SR mode bits incorrect except in
the common default-mode case.

Primary source freshly read: ST-169-R1-072694, SDK revision
`0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, blob
`943930551f755c68431847d23dfb6a6fad60e0c6`, printed pp.37,59,62 (PDF 47,69,72).
IREG0 is the status-acquisition switch; IREG1 carries P2MD/P1MD; the peripheral
SR format echoes those modes in bits 3:0. Source: https://github.com/jkind73/saturnsdk/ .

Fresh candidate checks: 576 request/mode/previous-mode/OPE cases pass, covering
both status-plus-peripheral and peripheral-only requests, legal mode values
0/1/3 for each port, both OPE choices and all 16 prior cached nibbles. The existing
1,173 handshake/cancel/reset cases pass. Wrong-register and missing-peripheral-
only-capture mutants compile and fail. Original production code also compiled
and failed the new test. Candidate SMPC translation-unit syntax passes.

These are extracted control-path tests with recording endpoints, not real
controllers, packet transport, clock timing or BIOS acceptance. In particular,
this does not fix the existing truncated multitap report or implement 255-byte
transport. The current CI production inputs stay unchanged; review/apply after
that measured revision is available:

```sh
git apply --check --unidiff-zero saturn_pending/smpc-port-mode.patch
git apply --unidiff-zero saturn_pending/smpc-port-mode.patch
python regtests/saturn/test_smpc_port_mode.py
python regtests/saturn/test_smpc_handshake.py
```

The GCC12 replacement CI run is
https://github.com/jkind73/mame/actions/runs/35287467065 at source
`5008a92331e4bf6698b7a9e53116c2167ddcc673`. Use that run's actual final outcome;
the earlier GCC11 run is failed. For a successful replacement artifact, substitute
this run ID and full SHA in the download/verification commands above.


## Pending combined SMPC transport correction (SMPC-04 / IO-01)

`smpc-transport.patch` includes the port-mode fix and replaces truncation/repeated
sampling with a saved report buffer and a cursor over 32-byte OREG pages. Apply
this combined patch **instead of** the earlier port-mode patch, not after it.
Production/CI inputs remain unchanged until the current build is measured.

Implemented in the isolated candidate:

- Snapshot both included ports once, then preserve subsequent bytes across
  CONTINUE requests. Two standard six-pad multitaps produce 38 bytes and now
  return the tail instead of losing it. Relative-motion callbacks are not
  repeatedly sampled while draining a report.
- Derive PDL from the first page and NPE from actual bytes remaining. End a
  short report immediately rather than pretending every response has two pages.
- Use all 32 output bytes. Initialize the command marker before copying data,
  so it cannot overwrite payload at OREG31 on a full page.
- Skip the complete port in 0-byte mode, including its status callback. Treat
  the documented FF unconnected-tap ID as ID-only, not 15 data bytes.
- Register buffer, size and cursor for save states; clear cursors on reset,
  BREAK and a new request. Preserve the existing no-controller/ST-V callback
  behavior, including its command marker.

The buffer is bounded for the existing controller interface: two status bytes
plus up to 15 devices per port, each an ID and at most 15 data bytes = 482 bytes.
The fixture includes 15-connector capacity stress, not a claim of a supported
15-device physical tap. Existing multitap slot configuration remains unchanged.
Extended-size peripheral IDs, bit-serial acquisition/timing, RESB sampling and
VBlank collection timeout are not implemented by this patch; the parents remain
open. Filling unused output bytes is a deterministic emulator policy, not a
hardware measurement.

Fresh checks against actual candidate functions:

- **5,402** packet/page/mode/OREG31/snapshot/cancel cases pass: varying port
  counts and payload sizes, gaps, legal port-mode encodings, and both INTBACK
  request forms. Save restoration copies the registered fields in the fixture;
  it does not execute MAME's save manager. Port/timer/IRQ endpoints are stand-ins.
- **1,175** handshake/cancel/reset/no-controller cases pass in the adapted
  handshake fixture. The adaptation stops requiring OREG31 to equal a command
  marker when it legitimately holds payload, and counts a snapshot only once.
- Six compiled negative controls are rejected: OREG31 clobber, page resampling,
  missing NPE, querying a disabled port, FF-as-payload and stale BREAK cursors.
  The original implementation also compiles and fails the new completion test.
- Candidate SMPC translation-unit C++20 syntax checking passes. Save field
  registration is source-checked; real save/load and live peripherals are pending.

Primary ST-169-R1-072694, SDK revision and PDF blob as above, freshly read:
pp.41 (OREG31 can be overwritten by peripheral data), 50–53 (continuation and
termination), 63–66 (port omission and PDL/NPE), and 73 (FF unconnected tap).
Pinned Ymir `6d779960127ced72087a418c1daefc637d0aaa80`,
`libs/ymir-core/src/ymir/hw/smpc/smpc.cpp:837–865`, independently corroborates a
single snapshot, 32-byte pages and separate first/remaining flags. Its unused
OREG filler policy differs; it is a cross-check, not a hardware oracle. No Ymir
code is imported.

```sh
git apply --check --unidiff-zero saturn_pending/smpc-transport.patch
git apply --unidiff-zero saturn_pending/smpc-transport.patch
python regtests/saturn/test_smpc_transport.py
python regtests/saturn/test_smpc_handshake.py
```

## General-CI checkpoint scheduling

The repository's ordinary workflows started overlapping full Linux/macOS/Windows
and shader runs for earlier session checkpoints while the targeted GCC12 run
remained queued. General workflows now group superseded runs **only for this
session branch** and cancel obsolete revisions. Their triggers, permissions,
matrices and job steps are unchanged; the latest revision still runs all checks.
Other branches receive unique run-ID groups and keep independent execution.
The dedicated Saturn workflow retains `cancel-in-progress: false` so its long
measured build is not discarded by preservation pushes. YAML structure checks
confirmed no existing workflow content changed except the added concurrency map.
Already-running jobs created before this policy do not inherit the new grouping;
this is not a claim that the current backlog has been canceled or cleared.

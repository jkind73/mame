## Current integration status

- **Artifact transfer solved:** the export workflow retains the exact CI ZIP in
  a draft release and provides a temporary GitHub API blob for clients whose
  binary download hosts fail. No binary is committed to the branch, no sandbox
  access token is used, and the source/run/ZIP/executable checks are unchanged.
- **234c7abc live PASS:** all six multitap transport cases and scheduled partial
  report save/mutate/load passed in the rebuilt executable, along with CD/cart/
  backup-RAM, SCSP timers, four BIOS/background replay configurations. Evidence:
  `evidence/234c-live/`. This is not whole-hardware or gameplay acceptance.
- **5008a923 baseline:** all four configurations now pass the 1,042-case
  composition suite (4,168 total), besides the previous 184 background cases.
  Live save-item enumeration also confirms the missing H/V edge-history entries.
- The VBlank timeout and edge-history fix is now **integrated** after its four
  live negative cases were reproduced on 234c. 73,728 extracted state cases,
  four edge/order cases, eight mutation controls and full-TU syntax checks pass.
  Its own new native build/live expiry and replay gates are still pending.
- Historical patch files are review artifacts; **do not reapply them**.

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

## Prepared live multitap transport check

`test_smpc_multitap_runtime.py` configures two real six-pad multitap devices and
writes the CPU-visible SMPC registers. It gives all twelve pads distinct button
patterns, checks 38-byte two-port reports and 19-byte single-port reports for
both INTBACK request forms, and changes physical input values after page one to
verify the retained tail. Its coroutine polls SF at 50-microsecond intervals;
it does not stretch each continuation across an entire video frame. Each new
request starts at VBlank. This does not qualify exact wire timing, collection
latency, VBlank timeout, extended IDs or real save/load.

Python syntax, Lua syntax using the repository's Lua compiler, and ten
fake-executable runner controls pass. **Live execution has not happened yet.**
The pre-transport binary is expected to fail this test; preserve that negative
result before applying `smpc-transport.patch` and rerunning on a rebuilt binary.
The runner keeps its full runtime log, including partial output on timeout.
It uses isolated temporary NVRAM/configuration and does not upload BIOS files.

```sh
python saturn_pending/test_smpc_multitap_runtime.py \
  --executable /home/user/saturn-ci-artifact/saturn --rompath ./regtests \
  --output /home/user/multitap-before
```

The GCC12 CI run 35287467065 has left the queue and is compiling Saturn/ST-V.
There is still no linked completion result. Another restored local checkout was
archived and recovered without affecting that remote build or importing the
mixed old workspace; the new live fixtures were preserved across recovery.

### CI binary runtime-library compatibility preparation

The Debian sandbox has fontconfig but no system SDL2 runtime. CI binaries use
Ubuntu's standard SDL2/SDL2_ttf SONAMEs, whereas the existing local SDK exposes
real pygame-wheel libraries with auditwheel-hashed SONAMEs. The no-rebuild
runtime validator now creates standard-name loader aliases in its external log
directory and retains the SDK library search path for transitive dependencies.
No substitute library implementation is used.

Fresh SDK preparation succeeded. Loading the actual libraries through those
standard names and calling their version APIs returned SDL **2.28.4** and
SDL_ttf **2.20.1**; `ldd` found no missing SDL_ttf dependencies. Shell syntax
passes. This establishes loader readiness for those libraries only, not successful
execution of the pending MAME artifact or BIOS/software acceptance.


## Successful native CI and current live-execution boundary

Run **35287467065 succeeded** at source
`5008a92331e4bf6698b7a9e53116c2167ddcc673`: native Saturn/ST-V build,
configuration validation, and the ROM-free regression batch all completed.
`ci-35287467065.json` records the GitHub API receipt and individual step outcomes.
It is not a substitute for BIOS/software or live save-manager evidence.

Artifact ID **10526830262**, name
`saturn-linux-5008a92331e4bf6698b7a9e53116c2167ddcc673`, compressed size
**16,305,765 bytes**, ZIP SHA-256:
`25ac71bd57e42f29048effa4b87eb88f6f7f6b232a9d17021c16df51692d3801`.
These values came from GitHub's API, not from an unverified local file.

The sandbox's artifact-host HTTPS connection still terminates with TLS EOF.
A temporary inbound receiver was considered and stopped when the public preview
required a traffic-access token. No token was disclosed, no access restriction
was bypassed, and no artifact was received. No relay workflow was published.

For a ZIP attached by the user after downloading it from the successful run:

```sh
python3 saturn_pending/unpack_ci_artifact.py /path/to/attached-artifact.zip   --run-id 35287467065 --destination /home/user/saturn-ci-artifact
bash saturn_pending/validate_ci_runtime.sh /home/user/saturn-ci-artifact 35287467065
```

The unpacker obtains the expected ZIP digest and length independently from
GitHub, rejects traversal/symlink/duplicate/unexpected members and oversized
expansion, requires an empty destination, then invokes the existing source/run/
executable verifier. Seven synthetic archive acceptance/rejection tests pass.
It starts no listener and executes no uploaded binary. **Live execution is
BLOCKED on artifact transfer**, not on a claimed successful BIOS boot.

The integrated SMPC source `234c7abc` has now passed the full **54-script**
regression batch; three optional live runners skipped their absent default
binary and are not counted as live acceptance. The durable native rebuild is
https://github.com/jkind73/mame/actions/runs/35291979814 and has started compiling.
The already-verified `5008a923` binary remains separate. An additional JP DRC
composition run is measuring that baseline, not the new SMPC source.

The additional JP DRC composition run on verified baseline `5008a923` completed:
**1,042 composition cases passed**, including pixel and save/mutate/load checks.
Its log is now preserved alongside the earlier 184 background cases and four
BIOS replay configurations. This result belongs to the baseline executable;
the new SMPC transport's native build/live-positive check is still pending.

## Rebuilt SMPC artifact and partial-report save/load

CI **35291979814 succeeded** for `234c7abc`; native build, configuration validation,
and ROM-free regressions passed (`ci-35291979814.json`). Fresh download still
fails with EOF at the Azure artifact host. Artifact `10527228938` is 16,305,741
bytes, ZIP SHA-256 `7129a6434f59db271254f515c3f1a9fef7d00d862c9347f8f44f563c76c966f8`.
The user has been asked to transfer this ZIP as with the previous artifact.

`test_smpc_save_runtime.py` now checks a scheduled file save after byte 32 of a
38-byte report, drains and overwrites its buffer, poisons modes/size/cursor with
a zero-byte request, loads, then verifies the original page and six-byte tail.
It uses retained MAME save/load notifiers, checks their order and requires a
MAMESAVE file; it does not use the unsafe synchronous Lua buffer-save shortcut.
The new helper shares register/input primitives with the six-case live fixture.
Its 14 fake-process failure controls and the existing 10 controls pass. Running
it on the original 5008 binary reaches real saved/mutated/loaded notifications
without Lua errors and fails the expected transport assertions. Positive
partial-report save-manager acceptance is still blocked on the rebuilt binary.
The runtime consumer now requires this test as well as the six transport cases.

## VBlank timeout development record (now integrated; new native acceptance pending)

`smpc-vblank-timeout.patch` applies on the integrated transport source without
reapplying the historical transport patches. It terminates unfinished console
peripheral requests at the existing VDP2 rising VBlank callback, cancels both
an initial pending command and a pending CONTINUE, clears PDL/NPE and the
snapshot cursor/length, and suppresses a new report/IRQ. It does not cancel an
unrelated system command or its SF and leaves legacy ST-V/no-controller behavior
unchanged. OPE scheduling and serial wire timing are still not implemented.

Primary rechecked: Sega ST-169-R1, printed p.50/PDF p.60, SDK PDF blob
`943930551f755c68431847d23dfb6a6fad60e0c6`. Ymir `6d779960127ced72087a418c1daefc637d0aaa80`,
`INTBACKBreak`/`TriggerVBlankIN`, corroborates timeout and clearing PDL/NPE while
retaining other SR bits. This is an independent implementation, not imported
code. Existing BREAK's broader SR clearing is not changed by this candidate.

The hook audit found that the driver's `m_prev_hint` and `m_prev_vint` have no
explicit initialization, reset assignment, or save registration in current
production. The candidate supplies all three, so edge detection is deterministic
and can be restored. This is not claimed as the cause of Agent1's reported crash.

`regtests/saturn/test_smpc_timeout.py --source-root PATCHED_COPY` compiled the actual candidate
helper and driver callback with recording endpoints: **73,728 state combinations
and four edge/order checks passed**, with eight compiled/assertion-rejected
mutants. The candidate SMPC and Saturn translation units pass C++20 syntax
checking. The field init/reset/registration assertions are source checks, not
live save-manager evidence. Neither timeout nor edge-state restoration has
native acceptance yet. The patch was subsequently integrated after the 234c transport/save gates
passed and its missing timeout was reproduced live. It now needs a new binary.

The partial-report save fixture now pauses after scheduling save/load (those
APIs resume internally), pumps host UI callbacks while paused, and asserts that
emulated time remains frozen/restores exactly. It resumes before CONTINUE. This
avoids accidentally holding a report across a VBlank deadline just to wait for
host disk I/O. The old-binary negative run was repeated: actual save/load
notifications complete without Lua errors or clock failures, with only the
expected transport assertions failing. Fourteen fake protocol controls pass.

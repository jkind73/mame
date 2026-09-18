# Integrated DSP program-RAM loader — native WIP

The documented MVI-PC serialized loader is now implemented: PRG selector,
saved wrapping program cursor, following-MVI serialization, TOP resume and
pending-slot flush. All 32 old-binary overlays and the 192-word wrapped actual
save replay reproduce the missing feature. Extracted suites, five mutants and
full-TU syntax pass. Native positives remain pending; exact scope and remaining
serialization/timing gaps: `evidence/dsp-pram/README.md`.

**Latest fully native-qualified source: ca63041f.** Build 35341486010 and export
35343850525 passed. The expanded consumer passed all 4,096 read-mirror programs
across JP/interpreter, JP/DRC, PAL/DRC and ST-V/DRC, plus 48 control-flow programs,
128 DMA programs, actual 60,000-word save replay and all earlier integration
gates. Binary SHA256:
`642af2f549c682ec391aa78109cfa732a727bd06b93fddb5a6d52b4d44162312`.
Evidence: `evidence/ca63041f-live/`. No whole-hardware or gameplay completion.


A separate actual ca63041f file save/reset/mutate/load now restores the pending
address-00 branch slot (JP/interpreter); the next consumer requires this gate.
Evidence: `evidence/dsp-pipeline/live-slot-save/`.

The next counter correction is prepared, **not applied**:
`scudsp-count.patch`, with 16/24 actual before-fix failures and 20,480 extracted
count cases. This also replaces the out-of-range 60,000-word save stress with
legal zero-encoded 256-word save replay. Reference/acceptance distinctions:
`evidence/dsp-count/README.md`. Current loader build 35344168780 is running; its
58-script local batch passed (three optional live skips excluded).

---

# Current native baseline and read-DMA work

**89764c08 passes the complete native gate**, including all 48 wrapped-control
programs across four machine/engine configurations, 128 DMA addressing cases
and real 60,000-word save replay. Source/binary provenance checks passed before
and after execution. CI 35308649438, binary SHA256
`f13ae2266ff6cf254198e1a3c725768fa3cd3c9aa37dd180771144d1c3bbf7de`.
Evidence: `evidence/89764c08-live/`. Older pending-pipeline statements below are
historical and superseded by this result.

**New production WIP:** DSP read-DMA physical bus classification now preserves
C-bus behavior across all high-RAM mirrors and excludes A-bus/CS2 from B-bus
advancement. Real 89764c08 fails 372/1,024 mirror/mode programs; expanded extracted
checks and full-TU syntax pass. The full 58-script local batch passed (three
optional live skips excluded). Native-positive passed in CI 35341486010 and the expanded consumer above.
Exact reference basis and limitations: `evidence/dsp-read/README.md`.

---

# Latest native qualification and execution fix

**b5caa488 passes the entire native consumer**, including all 32 DSP B-bus DMA
addressing cases and exact replay of a saved busy 60,000-word transfer. Source,
ZIP and binary provenance were verified; no build inputs changed during the gate.
CI 35306849889, binary SHA256
`5d5f978c7938a0553c21009885f5a995f0fbd5e73604d3d594c7d5205d88b8f2`.
Evidence: `evidence/b5caa488-live/`. This supersedes older pending-DMA statements.

**New production WIP (89764c08):** explicit DSP pending-delay validity preserves address 00
across PC wrap, state restore and reset. Five real before-fix programs fail on
both 234c and b5caa488; 393,216 extracted PC/target/control cases, three rejected
mutants, the existing DMA suite and full-TU syntax pass. The complete local 58-script batch passed, with three optional live skips
excluded. Native-positive for this revision is pending in CI 35308649438. `scudsp-delay-slot.patch` is integrated; do not reapply.
See `evidence/dsp-pipeline/`. Full prefetch timing and program-RAM DMA remain open.

---

# Latest integration update

**79f36021 now passes the complete expanded native gate**: both full/sparse tap
adapters, disconnected root ports, seven RESB observations, actual sampled-RESB
and peripheral snapshot save/load, plus earlier CD/cart/backup, timer, timeout,
H/V restore and BIOS/background checks. Evidence: `evidence/79f36021-live/`.
The first run's final provenance check correctly failed when DSP source editing
began during execution; a clean-source rerun passed both provenance checks and
all runtime phases. This is not full game acceptance.

**New production DSP work (native WIP):** B-bus per-halfword DMA strides, complete
DMA state registration, reset cancellation/private-stall release. See
`evidence/dsp-dma/README.md` for primary references, extracted cases, compiled
mutants and a genuine before-fix native failure. The gate now requires 32 actual
DSP programs and real 60,000-word in-flight save replay to pass. The full local
57-script batch passed, excluding three optional live skips. A/C quirks, program-RAM DMA and bus arbitration remain open.

The dated acceptance records below describe earlier checkpoints; this update
supersedes their pending-79f36021 statements.

---

# Saturn integration status and runtime delivery

## Current acceptance boundary

| Source | Result | Evidence |
| --- | --- | --- |
| `5008a923` | Native CI and live CD/cart/backup-RAM/timer checks passed; four BIOS/background replay configurations and all four 1,042-case composition configurations passed. | `ci-35287467065.json`, `evidence/5008-live/` |
| `234c7abc` | Rebuilt SMPC transport passed six live two-multitap cases and scheduled partial-report save/mutate/load. The complete CD/cart/backup/timer/BIOS/background runtime gate passed again. | `ci-35291979814.json`, `evidence/234c-live/` |
| `2781f96b` | VBlank timeout and H/V edge-history initialization/reset/save registration integrated. Full 55-script local regression batch passed (three missing-default-binary live skips). Native CI and full live consumer pass, including all four timeout cases and first restored H/V edge IST=4; see `evidence/2781-live/`. | `evidence/2781-timeout/`, [CI 35299792272](https://github.com/jkind73/mame/actions/runs/35299792272) |

The original transport faults, then the missing VBlank cancellation, were
reproduced with real binaries before their respective fixes. A further linked
negative test on 234c shows the edge-history save bug: after loading an active
raster state from HBlank+VBlank, the first restored SCU interrupt status is **2
(spurious VBlank-OUT), not 4 (HBlank)**. Its real save/load callbacks complete;
there are no Lua errors. The rebuilt 2781 binary now passes this test with IST=4.

Baseline composition totals are **4,168 cases**: JP DRC, JP interpreter, PAL DRC,
and ST-V DRC. Background totals are 184 per four-configuration gate. These are
synthetic pixel/save-replay checks, not complete software or hardware acceptance.
JP BIOS captures reach date/time setup. ST-V without a game cartridge reaches
the expected cartridge-error screen, **not a game boot**. No working flags have
been promoted; AB2/Power Drift/OutRun code fixes are retained, not freshly
requalified by these fixtures.

## Production changes and remaining scope

### SMPC/controller transport — SMPC-04 / IO-01

- Port modes come from IREG1 for both INTBACK forms. Zero-byte modes omit the
  corresponding port section. Unconnected `FF` peripheral IDs are ID-only.
- The existing short-ID interface is bounded to 482 bytes in a 512-byte saved
  buffer. Reports are captured once, paged over all 32 OREG bytes, with PDL/NPE
  representing first/remaining data. OREG31 is not overwritten after a full-page
  copy. The retained short-page padding policy is not a hardware measurement.
- BREAK/reset cancel pending continuation and packet state. Live 234c checks
  validate six mode/status combinations, changed input between pages, and a
  real file save after byte 32 of a 38-byte report, mutation, load and six-byte
  tail replay. This does not qualify every in-flight timer save point.
- The 2781 timeout hook runs on the existing rising VDP2 VBlank callback. It
  cancels pending initial peripheral completion and CONTINUE, clears PDL/NPE and
  cursor/length, preserves unrelated commands/SF, and emits no new report/IRQ.
  The legacy no-controller/ST-V handshake is deliberately unchanged.
- Previous H/V edge levels now have explicit initial values, reset assignment,
  and save registration. Their absence was confirmed in live save metadata;
  the subsequent mapped-SCU test demonstrates the actual restoration fault.
  This is not asserted to explain Agent1's reported host crash.
- Extended-size IDs, OPE scheduling, serial wire timing, reset debounce and wider
  peripheral-origin event routing remain open. The parent is not DONE.

Primary: Sega ST-169-R1-072694, SDK commit
`0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, PDF blob
`943930551f755c68431847d23dfb6a6fad60e0c6`: printed p.41 allows peripheral data
to overwrite OREG31; p.50 specifies CONTINUE/BREAK and VBlank-IN termination;
pp.59–70 describe modes/streams/PDL/NPE/extended IDs; p.73 defines unconnected
IDs. Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, SMPC report/INTBACKBreak/
TriggerVBlankIN methods, provides an independent cross-check. No Ymir code was
imported. The existing BREAK SR policy is not changed by the timeout fix.

Focused compiled checks: 5,402 transport cases, 1,175 handshake cases, 73,728
timeout combinations, four edge/order checks, six transport and eight timeout
mutation controls; SMPC and Saturn full translation units pass C++20 syntax.
Recording endpoints/source registration checks are **not** native save-manager
or hardware timing evidence. Native evidence is explicitly source-labelled.

### Earlier integrated CD/cart/NVR/IOGA/SCSP work

Cart/CD and internal backup-RAM persistence/save registration have linked
coverage in the evidence above. IOGA inspection preserves the legacy byte
cursor (5,124 focused recording-endpoint cases, not cabinet acceptance).
SCSP timer phase uses saved tick origins and real MAME attotime quantization:
49,152 ideal-clock plus 49,152 actual-attotime model checks, 24 reset cases and
three rejected mutations. The native fixture separately measures 24 timer/
divisor rates and three IRQ clear/reassert paths.

Primary SCSP ST-077-R2, PDF blob
`9383eb13fe65c807e3ec48f32e284b9999cd71b8`, printed pp.93–94: the longest-period
table and formula disagree about 256 versus 255 reload cycles. The pre-existing
reload policy is retained; timer-phase results do not resolve that discrepancy
or qualify audio waveforms. CD/ST-V/software/concurrency parents remain open.

## Native artifacts without manual re-upload

Direct Actions/Azure and release-asset downloads fail in this sandbox. The
successful alternative is a temporary GitHub Git-blob API transfer. The original
ZIP is also retained in an **unpublished draft release**, not presented as a
finished emulator release. There is no sandbox listener or traffic-token use.
The export workflow never commits a binary to the branch. `artifact-transfer-234c.json` records
the successful export, transfer blob, original ZIP and executable digests.

After the native CI run succeeds:

1. Set `SOURCE_RUN`/`SOURCE_SHA` in
   `.github/workflows/saturn-artifact-export.yml` to that successful run and push
   on this session branch. Its path-filtered job validates the run identity and
   original ZIP digest, updates only the matching draft and an unreferenced
   transport blob. It refuses to overwrite a published release.
2. With matching source/build/test input trees, run:

   ```sh
   python3 saturn_pending/fetch_ci_artifact.py --run-id RUN_ID --destination /home/user/saturn-ci-RUN_ID
   bash saturn_pending/validate_ci_runtime.sh /home/user/saturn-ci-RUN_ID RUN_ID
   ```

The helper checks draft/source/blob identities and then invokes the existing
unpacker, which independently obtains the Actions ZIP digest/size and verifies
source/run/executable provenance. A genuine old-binary/new-source mismatch was
correctly rejected after transfer. The blob can eventually be garbage-collected;
export it again while the original Actions artifact is available. Draft storage
is separate from that temporary transport. CI artifacts currently retain 14 days.

For an attached or repository-provided original ZIP, use
`unpack_ci_artifact.py ARCHIVE --run-id RUN_ID --destination EXTERNAL_DIRECTORY`.
The source/run/binary verifier is not a signed software attestation. It accepts
neither failed builds nor mismatched local input trees. Temporary and downloaded
binaries are outside Git. Firmware is neither downloaded nor committed by these
tools. The user replaced the earlier 5008 upload with the matching 234c ZIP;
it is preserved at the repository root, outside the regression-input tree.

Runtime dependencies are genuine SDL/SDL_ttf/fontconfig libraries, provisioned
by `regtests/saturn/bootstrap_linked_deps.py` in an external cache if necessary.
Standard SDL SONAME aliases point to the actual libraries; no stubs are used.
Archives/caches can disappear on workspace reset, so source, receipts and text
evidence—not cache paths—are authoritative.

## Live gates and their controls

`validate_ci_runtime.sh` checks provenance before/after execution, executable
and BIOS identities, configuration, CD/cart/backup RAM, SCSP timers, SMPC
transport/save/timeout, H/V edge restoration, and four BIOS/background replay
configurations. Missing prerequisites cannot satisfy its positive markers.

- `test_smpc_multitap_runtime.py`: six live transport cases per configuration; sixty fake-process
  failure controls in `test_smpc_multitap_runner.py`.
- `test_smpc_save_runtime.py`: partial report file save/mutate/load; seventeen
  fake-process controls. The current fixture additionally restores sampled RESB=1
  against a released live button and checks its next-VBlank clearing. It pauses after scheduling and verifies frozen/restored
  time, avoiding a VBlank deadline while waiting on host disk I/O.
- `test_smpc_timeout_runtime.py`: four waiting/in-flight expiry cases; twelve
  parser controls. It uses guarded raster positions, not a wire-timing oracle.
- `test_sync_save_runtime.py`: active-display save, natural H/V blank mutation,
  load, and first restored HBlank/SCU status; fourteen fake-process controls.
  Save items are read only. No private state is overwritten to manufacture a
  result. Positive execution on 2781 passes.
- Transfer/archive/provenance controls: nineteen/seven/twelve synthetic cases.
  They test tooling, not native emulation.

Historical `.patch` files are review records: IOGA, SCSP, combined transport
and timeout changes are integrated; the mode-only patch is superseded. Do not
apply these patches again. `history.md` preserves earlier checkpoint narratives
and references; `pr-history.md` preserves the pre-consolidation PR description.
Neither superseded pending/blocked statements nor old extracted totals should
be mistaken for fresh acceptance of the latest revision.

## Integrated WIP: RESB and sparse physical sockets

`smpc-resb.patch` independently implements the hardwired reset-button status
latch. ST-169 printed p.34/PDF p.44 explicitly says RESDISA suppresses NMI but
RESB still shows the switch at VBlank-IN; printed p.66/PDF p.76 makes RESB valid
outside INTBACK. Production now binds only RESET port bit 0, samples every console
VBlank (including idle/NMI-disabled periods), exposes the saved latch through SR
independently of command writes, and initializes/resets/registers it. Reading the
port at VBlank also covers a button held across machine reset. ST-V remains on
its existing path. The three-VINT NMI/debounce behavior is **not** implemented
by this change.

The live 234c negative control confirms four missing pressed-state observations
while verifying the actual input bit. The implementation passes 6,144 compiled latch/
read/command/enable combinations, ST-V isolation, four compiled/assertion-rejected
mutants, the existing 73,728 timeout + 5,402 transport + 1,175 handshake checks,
and SMPC/console full-TU C++20 syntax. Twelve result-parser controls pass. These
are not native-positive or real RESB save-manager acceptance. The patch is now
integrated; do not reapply it. Native rebuild is required for these new changes.
Use `test_smpc_resb.py --source-root .` and `test_smpc_resb_runtime.py`.

Physical socket selection is now separate from packed report offsets, through
`read_ctrl_slot(index, offset)` on the interface/port and both tap adapters.
Empty ports return status F0 and ID FF instead of 00. The legacy flattened
API remains for existing consumers. Actual adapter/port/SMPC methods pass 9,216
ASan/UBSan topology/mode reports, direct/empty/bounds checks and four compiled
negative controls. A genuine sparse-socket failure on 234c is retained in
`evidence/234c-live/sparse-before.log`. The native gate now requires full/sparse six-pad and four-pad adapters, empty root ports,
RESB status checks and real RESB latch save/load; these are NOT yet native-positive.

Normal live requests use the mapped SCU VBlank-IN event, not the screen boundary
one scanline before it. This corrected fixture qualified 2781 without relaxing
the production deadline. Source-labelled first failure is preserved as well.

Additional native 2781 controls: fully populated SegaTap passes all six cases;
sparse SegaTap slots 1:2/2:3 fail with shifted/zero bytes. The extended scheduled
save/load test completes all three notifications but fails the expected missing
RESB latch before save and after load. Logs are retained under
`evidence/2781-live/additional-controls/`. No new-source positive is inferred.

Production source **79f36021**: the complete **56-script local batch exited zero**,
with three optional missing-default-binary live skips excluded from acceptance.
See `evidence/79f36021-local/`. Native build **35303949227** is queued behind
35301252871. The latter has the same build-input trees as qualified 2781;
attempted cancellation returned HTTP 403, while push/read/PR APIs work.
Empty root ports on 2781 independently reproduce status **00 instead of F0**.
The current native gate must reject that result. Its negative log is preserved.

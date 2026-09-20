# Validator record: branch `arena/01a0b897-mame` (implementation agent)

- Reviewed revision: **1354cfdad** (branch tip at the time of review), shared
  ancestor with this branch `f47e20b46fc`.
- Scope reviewed: the CD work only — 25 commits touching
  `src/mame/sega/saturn_cd_hle.cpp` since 2026-09-19, 4057 insertions /
  2713 deletions against their pre-CD base, plus the candidates recorded as
  IMPL-0074..0078 in `saturn_pending/IMPL_HANDOFF.md`.
- Validator: this branch. Nothing in this file changes the branch under review;
  every claim below is either a re-run of their own check or a measurement made
  with a locally built binary.

## What was run, and what it showed

### Their own method-level checks (run on their tree, unmodified)

| check | result |
|---|---|
| `saturn_pending/impl_checks/check_cd_toc_transfer_start.py` (IMPL-0078) | reproduces: 900 session-query cursor images, 6 explicit TOC starts, 6 session-then-PUT reservations |
| `saturn_pending/impl_checks/check_cd_raw_put.py` (IMPL-0077) | reproduces: 96 PUT/GET view images, 72 partial/zero PUTs, 240 registered raw-PUT replays, 4 filter routes, 242 refusal controls, full-pool release |
| `saturn_pending/impl_checks/check_cd_raw_sector_views.py` (IMPL-0074) | reproduces: 288 raw media/view/size/GETDELETE images, 384 mid-sector size-change replays, 24 raw COPY/MOVE controls |

Their self-descriptions are accurate: these are method-level harnesses with mock
media/IRQ/serializer, and the scripts say so.

### Native graft (their CD implementation on this branch's tree)

Their `saturn_cd_hle.{cpp,h}` is self-contained: it compiles on this branch's
tree with only a 20-line `host_r`/`host_w` adapter (this branch's driver calls
the CD block through `saturn_cdblock_interface`, their file predates that seam
and still exposes the address-map entry points). No other file from their branch
is needed to build it.

| fixture (live machine) | this branch's own binary | their CD implementation |
|---|---|---|
| `test_cd_hirq.py` | PASS | **PASS** — command/CMOK handshake, write-to-clear and DCHG still verified live |
| `test_cdda_runtime.py` distinct failures | 4 | **9** |

Distinct live failures with their implementation: `play_tone_1k`,
`play_tone_not_2k`, `put_error_buffer_intact`, `scan_state` (shared with this
branch) **plus** `range_silent`, `scan_audible`, `scan_moves`,
`periodic_idle_17ms`, `periodic_cadence_differs` (these five pass on this
branch's binary).

Reading of that measurement, stated carefully: it is their CD file *on this
branch's tree*, so it is not a statement about their branch's own runtime.
What it does establish is that their `saturn_cd_hle.cpp` is **not a superset**
of this branch's HLE: the Play Disc range end, SCAN rate/audibility and the
periodic 13.3/16.7 ms cadence that were qualified here are absent in their
file. A merge must reconcile those behaviours with their new command semantics
rather than take either file wholesale.

## Verdicts

- **IMPL-0078 — ACCEPTED (code review + method-level reproduction).** The change
  moves exactly `xfertype = XFERTYPE_TOC; xfercount = 0;` out of the shared
  `cd_readTOC()` into `cmd_get_toc()`. Only two callers exist
  (`cmd_get_toc()`, `cmd_get_session_info()`), so nothing else loses the side
  effect. Their primary-source reading (ST-162-062094 p.77 §8.2.1 / functions
  1.5-1.6 separates the 408-byte TOC data transfer from the four-byte session
  information) and their Mednafen/Ymir cross-checks agree with the code.
- **IMPL-0074..0077 — UNVALIDATED, unchanged (method-level only).** Their own
  harnesses reproduce the claimed case counts; there is no native runtime run
  for raw PUT reservation, selector routing, sector views or file-scope
  semantics. Their handoff already marks each of these UNVALIDATED and states
  "no full build", which is consistent with what this review found.
- **Full-branch native gate: NOT ESTABLISHED.** `.github/workflows/
  saturn-integration.yml` describes the right gate (driver-filtered build,
  `-validate`, `regtests/saturn/run_all.py`, tree-diff check), and their handoff
  does not cite any green run of it. Replicating that build here is not possible
  at useful speed: the agent's tree needs a cold build of the whole MAME core
  (~3000 translation units) and this sandbox has two cores, where even
  single-threaded low-priority compilation made tool calls time out. The gate
  has to run on a CI runner or a bigger machine.
- **Branch state: REJECTED for merge-readiness**, on hygiene and on the still
  open native gate, not on the CD work itself:
  - committed build artifacts (policy: no binaries/downloads in the tree):
    `saturn-linux-234c7abcfc9a222978a7545a8491e568cf1781cf.zip` (16.3 MB, repo
    root), `regtests/saturn/error.zip` (17.3 MB, one 233 MB debug log), the
    `regtests/saturn/` screenshots, ~13 MB `afterburner2-boot*.log`, and stray
    `*.patch` / `error.log` files in the repo root. These also make the branch
    expensive to fetch and diff.  On this branch the same class of file was
    present (`saturn-linux-*.zip`, a root `error.log`); both are now removed
    here, and the ABII boot logs are kept because the boot analysis cites their
    line numbers and SHA-256.
  - every CD candidate is still UNVALIDATED with no native result; merging now
    would import method-level claims as if they were runtime behaviour.

## Merge plan implied by the above

1. Drop the committed artifacts.
2. Run the branch's own CI gate to get a native result for the command semantics
   (IMPL-0074..0078 and the earlier selector/filter/file commits).
3. Reconcile, don't replace: keep this branch's CD-DA range/SCAN/periodic
   behaviour and host-window/LLE contract, and layer their command semantics
   (raw PUT/GET views, selector routing, file commands) on top; re-run
   `test_cdda_runtime.py`, `test_cd_hirq.py`, `test_cd_transfer.py` and
   `test_cd_lle.py` on the merged tree.

---

# Second review: candidates 0117-0130, with the native gate they were missing

Reviewed revision: **b3eece68ae1** (branch tip; 91 commits since `1354cfdad13`,
candidates 0117-0130). Their tree was built natively for this review in a
worktree of `refs/remotes/agent1` (1220 TUs, `-O0 -j2`, exit 0, 202426872-byte
`saturn`), so the recurring caveat "no full build" is now closed.

## Native results (measured here, on their tree)

| gate | result |
|---|---|
| `./saturn -validate` | **exit 0** |
| `regtests/saturn/run_all.py` (72 scripts, run individually so one failure cannot mask the rest) | **68 pass / 4 fail** |
| `test_cd_transfer.py` | FAIL - harness only: extracted `cmd_end_data_transfer()` references `m_host_transfer_active`, `m_put_filter`, `finish_put()`, none of which the scaffold declares, although all three exist in their `src/mame/sega/saturn_cd_hle.cpp` (21 references) |
| `test_dma_bus.py`, `test_dma_indirect.py`, `test_dma_source.py` | FAIL - harness only: the extracts copy `saturn_scu.cpp` bodies that call `memory::write_byte`/`dma_read_byte` (3 references in that file), which the mock `struct memory` in the harness does not provide |
| their own 10 method-level checks (`check_cd_track_bounds`, `check_cd_discard_progress`, `check_cd_buffer_full_irq`, `check_cd_put_full_irq`, `check_cd_metadata_port`, `check_cd_programmed_range`, `check_cd_sector_word_port`, `check_cd_raw_put`, `check_cd_raw_sector_views`, `check_cd_toc_transfer_start`) | all reproduce, exit 0, and are honestly self-labelled `method-level, unvalidated` |

`run_all.py` aborts on the first failure, so the batch cannot go green until those
four harness scaffolds are updated; nothing in `src/mame/sega` is at fault for
them (the same tree links and passes `-validate`).

## Live-machine cross-check with this branch's fixtures against their binary

| fixture (real running Saturn) | their binary | this branch's binary |
|---|---|---|
| `test_cd_hirq.py` | **PASS** | PASS |
| `test_cdda_runtime.py` distinct failures | **5** | 2 |

Their extra failures relative to this branch: `play_q_track`, `scan_audible`,
`scan_moves` - i.e. subcode Q track reporting during Play, and a SCAN that stays
audible while the pickup moves. Those are genuine gaps on their side, not harness
noise. The two shared failures (`play_tone_1k`, `play_tone_not_2k`) must not be
chased by either branch as device faults: both are measured at the mixer output,
which in a headless run has no sink, so the captured block repeats bit-identically
(30 successive 50 ms slices of the machine's own `-wavwrite` capture give
`g1k=0.01404 g2k=0.07241 rms=0.62543` while the drive's FAD advances normally;
two binaries whose drives sit 113 sectors apart produce identical numbers; the
captured samples match no bytes of the fixture disc at any sector offset, stride
or endianness).

## Verdicts on the pending candidates

Accepted on code review, primary-source citation and (where applicable) the live
cross-check above. Expectations were not edited.

- **IMPL-0123/0124** (bound Play/Seek track numbers before the image TOC lookup;
  TNO=IDX=0 is Home, TNO=0 with an index defaults to track 1, above-last clamps):
  **ACCEPTED**. The bounds part is unambiguously right - an unclamped host TNO fed
  to `get_track_start(tno - 1)` is an out-of-range read. I also checked the
  suspected duplicate `cd_default_play_range()` call: sites 2507, 2533 and 2660
  are three distinct guarded paths, not one path twice.
- **IMPL-0127/0128** (a sector discarded by the selector advances the drive and
  raises CSCT; a disconnected CD output discards its stream instead of pinning the
  pickup at one FAD; storage failure still retries): **ACCEPTED**. `p_ok` keeps its
  existing meaning for the other callers, and the discard-vs-pause split matches
  ST-162 p.38/p.42-43. A pickup pinned at one FAD is exactly the game-visible
  hang class this parent is for.
- **IMPL-0129/0130** (BFUL latched as a cause by the producer and published
  without an HIRQ read; PUT End latches BFUL from post-routing capacity):
  **ACCEPTED, corroborated independently**. This branch reached the same reading
  from the same pages and latches BFUL in `cd_alloc_block()`, so the two branches
  agree on the hardware and differ only on placement. Merge note: reconcile into
  one cause-and-clear rule (producer alloc, drive tick, End arm) rather than
  three `hirqreg |= BFUL` sites.
- **IMPL-0120/0121/0122 and 0125/0126** (16-bit DATATRNS FIFO on both halfword
  lanes with a shared byte cursor; longword continuation straddling an odd word
  count; per-access bounds parameterised by width; debugger inspection consumes
  nothing): **ACCEPTED on review, with a merge hazard that must be handled
  deliberately**. This branch folds the window in `sat_console_state::cd_reg_offset()`
  and dispatches `host_r`/`host_w` as 16-bit handlers, so a file-level merge would
  silently drop the 32-bit straddle path (this branch never issues a 32-bit access
  on that window, so the `mem_mask == 0xffff0000` / `0x0000ffff` arms never fire).
  Port the *cursor and straddle semantics* into the folded path, then re-run
  `test_cd_hirq.py`, `test_cd_transfer.py` and `test_cd_lle.py` here.

Still **UNVALIDATED (no native runtime)**, unchanged from their own labels:
`IMPL-0117/0118/0119` and the raw-PUT/selector semantics - their evidence is
method-level only, and this branch has no live fixture that drives a raw PUT
roundtrip through a running Saturn. No afterburner2/outrun media exists in either
workspace, so gameplay acceptance for those paths cannot be produced locally.

## What this branch needs from the implementation agent next

1. Update the four stale harness scaffolds so `run_all.py` is green end to end.
2. Add a live-machine fixture for the raw PUT reservation/selector routing and the
   discard-progress behaviour (a Lua script driving the host window in a running
   machine, like `test_cd_hirq.py`), which converts their strongest new semantics
   from method-level to runtime.
3. Reconcile the CD-DA gaps this branch already qualifies: subcode Q track during
   Play, and SCAN audibility/advance.
4. Do not re-open `play_tone_1k`/`play_tone_not_2k` against the mixer output; fix
   the capture point (converter-state-level assertion, or a host with an audio
   sink) first.

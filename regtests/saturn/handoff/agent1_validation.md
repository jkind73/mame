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

# Saturn CD candidate promotion status

Updated: 2026-09-20. Scope: the validator's second review of **b3eece68ae156aa90ad25c6c6308194a32e15348**.

## Decision

**Record IMPL-0120 through IMPL-0130 as ACCEPTED by the validator (11 candidates).** These are accepted implementation contracts, not a declaration that every behavior has individual live-machine coverage or that the entire branch is merge-ready.

**Keep IMPL-0117 through IMPL-0119 and the broader raw-PUT/selector runtime work UNVALIDATED.** No unmentioned candidate or CD milestone is promoted by inference.

This document transcribes the independent validator's decisions. The implementation agent has not rerun or independently certified the native results. The append-only status update in `IMPL_HANDOFF.md` supersedes the earlier blanket UNVALIDATED labels only for the accepted IDs below.

## Authoritative evidence

- [Validator report, second review, lines 102–194](https://github.com/jkind73/mame/blob/a735e0340a64a5a9369650165e3d423e2a6b9f86/regtests/saturn/handoff/agent1_validation.md#L102-L194).
- Validator revision: `a735e0340a64a5a9369650165e3d423e2a6b9f86`.
- Exact report blob: `066ba4ba5668ab007bfa55a855fbead51adc161f`.
- Reviewed implementation: `b3eece68ae156aa90ad25c6c6308194a32e15348`.
- This promotion-record update changes documentation only. Production source remains the reviewed source; it is not a newly tested implementation revision.

| Evidence at the reviewed implementation | Validator result | What it establishes |
|---|---|---|
| Native build, 1220 translation units, `-O0 -j2` | Exit 0 | The native build blocker is closed for this source revision |
| `./saturn -validate` | Exit 0 | MAME validation succeeded; not complete hardware/gameplay qualification |
| 72 regression scripts, executed individually | 68 pass / 4 harness-only failures | Broad regression evidence, but **not** a green end-to-end `run_all.py` |
| Live `test_cd_hirq.py` | PASS | Live coverage of that fixture; not every new CD transfer contract |
| Ten implementation method-level probes | Exit 0, independently reproduced | Method-level evidence remains method-level |
| Live `test_cdda_runtime.py` | Five failures, two shared capture problems | Three genuine implementation gaps remain: `play_q_track`, `scan_audible`, `scan_moves` |

The earlier implementation-only batch (65 probes, 55 exit-zero results and ten conflicts) is a different suite. The validator reproduced ten selected implementation probes; this record does not claim the other method-level conflicts were resolved.

Do not continue citing “no native build/result exists” for this reviewed source. Conversely, do not translate these results into a green CI run or a fully passing regression suite: neither is reported.

## Accepted candidates: promotion ledger

Source commits identify provenance **within the reviewed tree**, not individually tested or dependency-free cherry-picks.

| Candidate | Parent | Source commit | Recorded status | Accepted contract |
|---|---|---|---|---|
| IMPL-0120 | CD-01 | `b70549aa` | ACCEPTED — validator review | Sector FIFO word reads on both halfword lanes |
| IMPL-0121 | CD-01 | `b70549aa` | ACCEPTED — validator review | Sector FIFO word writes on both halfword lanes |
| IMPL-0122 | CD-01 | `b70549aa` | ACCEPTED — validator review | Mixed-width continuation across sector boundaries |
| IMPL-0123 | CD-02 | `ca86d951` | ACCEPTED — validator review | Bound Play track numbers before image lookup |
| IMPL-0124 | CD-02 | `ca86d951` | ACCEPTED — validator review | Bound Seek tracks and distinguish default track from Home |
| IMPL-0125 | CD-01 | `650e9468fab` | ACCEPTED — validator review | Ordered metadata FIFO word aggregation |
| IMPL-0126 | CD-01 | `650e9468fab` | ACCEPTED — validator review | Inspection reads consume no transfer state |
| IMPL-0127 | CD-01/CD-02 | `61504f0efdb` | ACCEPTED — validator review | Selector discard advances the stream and raises CSCT |
| IMPL-0128 | CD-01/CD-02 | `61504f0efdb` | ACCEPTED — validator review | Disconnected output discards rather than pinning the pickup |
| IMPL-0129 | CD-01/CD-02 | `b2b164b2e2b` | ACCEPTED — independently corroborated by validator | Producer BFUL publication without polling |
| IMPL-0130 | CD-01 | `19d9a83b670` | ACCEPTED — independently corroborated by validator | PUT End BFUL from post-routing capacity |

Acceptance grounds are code review, primary-source citation and, where applicable, the report's live cross-check. **The report does not assign a separate live pass to each row.** In particular, acceptance of discard logic does not eliminate the request for a live discard-progress fixture, and acceptance of PUT End BFUL does not qualify the whole raw-PUT transaction.

### Conditions for integration/promotion

1. **FIFO group (0120–0122, 0125–0126):** port the cursor, ordering and straddle semantics into the destination's folded `cd_reg_offset()` / 16-bit `host_r` / `host_w` path. A file-level replacement or an adapter that drops width semantics is not acceptable. Re-run `test_cd_hirq.py`, `test_cd_transfer.py` and `test_cd_lle.py` on the integrated tree.
2. **Bounds group (0123–0124):** preserve the reviewed normalized-track and Home distinctions alongside the destination's Play/Seek implementation. Do not infer that arbitrary indices, pregaps or multisession behavior are complete.
3. **Discard group (0127–0128):** retain the distinction between consumed stream progress and successful storage, including the full-buffer pause. Obtain the requested live host-window discard-progress coverage.
4. **BFUL group (0129–0130):** reconcile the destination's allocator latch with the producer and PUT End paths into one consistent cause-and-clear rule. Do not blindly stack three competing notification policies. Check masked delivery and post-routing capacity on the integrated tree.

These are semantic integration groups, not permission to replace either branch's HLE wholesale. Earlier raw-buffer and programmed-range dependencies retain their own evidence status.

## Not promoted

| Scope | Status / required evidence |
|---|---|
| IMPL-0117/0118/0119, filesystem resets of programmed Play range | UNVALIDATED — no native runtime acceptance in the report |
| Broader raw-PUT reservation / selector routing | UNVALIDATED — needs a live host-window roundtrip fixture |
| Discard-progress runtime coverage | Still requested despite code-level acceptance of 0127/0128 |
| Other candidates without an explicit verdict in this second review | Unchanged; reproduced probes alone do not confer acceptance |
| CD-01, CD-02, CD-03, CD-04, CD-05 parent milestones | Remain open; candidate acceptance does not close a subsystem |
| After Burner II / OutRun gameplay acceptance for these paths | Not established; the validator reports no required media in either workspace |

The earlier, narrower acceptance of IMPL-0078 remains historical code-review/method-level acceptance; it is not enlarged by this update.

## Remaining release / full-branch gates

- The four **scaffold-only** failures have implementation-side repairs in `45dab461`; original assertions/expected values are unchanged. The local end-to-end runner exited 0 with **69 non-skipped scripts and 3 live skips**, not 72 native passes (details below). Obtain the validator's rerun with a native executable before closing the native regression gate. These were not identified production defects.
- Add the requested live raw-PUT/selector/discard fixture and obtain validator results.
- Resolve the three genuine CD-DA gaps: Q track during Play, SCAN audibility and SCAN movement.
- Do **not** treat `play_tone_1k` / `play_tone_not_2k` as device defects using the present headless mixer capture. First use an appropriate capture point or an audio sink.
- Obtain the destination-tree integration runs above. Acceptance on the reviewed implementation is not acceptance of an unmeasured merge.

## Source identity for the reviewed evidence

| File | Git blob at `b3eece68ae1` |
|---|---|
| `src/mame/sega/saturn_cd_hle.cpp` | `0346dbe37889023f303110dcf2091b99da761f75` |
| `src/mame/sega/saturn_cd_hle.h` | `ab09861a9a04277851fcac4d40d62952197576b2` |
| `src/mame/sega/saturn_scu.cpp` | `325282dc10e96d3c0e252e3bcbdd5235d56781d2` |

No validator assets, expected values, production code, milestone IDs or milestone checkboxes are changed by this promotion record. No merge, release or whole-branch approval is implied.


## Implementation-side scaffold follow-up — 2026-09-20

Repair commit: `45dab461` on `arena/01a0b897-mame`, based on `e9d734d9`.
This is a test-harness update, not a change to the independently reviewed
production source or the acceptance decisions above.

- Three DMA scaffolds now extract/declare the production `dma_read_byte`
  dependency. Their mock byte-write endpoint asserts if called; the original
  scenarios have aligned destinations/even counts and do not qualify byte tails.
- The CD scaffold now extracts current sector/PUT/admission dependencies and
  declares private reservations, raw-view/ownership fields and filter types.
  GET+DELETE setup invokes the real command to create its private reservation
  instead of only assigning a mode. This is a fixture-construction change,
  **not merely declarations**. Response formatting remains mocked/out of scope.
- All **169 original C++ assertions** (36 CD, 21 DMA bus, 105 DMA indirect,
  7 DMA source) remain verbatim and in order; all three Python assertions
  remain AST-identical. Manual diff review found no expected-value changes.
- `python3 regtests/saturn/run_all.py`: exit 0 after fetching its missing pinned
  V-counter history object `868d72fc669765f8a0b9af6503a59642d293cbae`.
  **72 scripts discovered: 69 non-skipped exit-zero scripts, 3 skipped**:
  `test_backup_ram.py`, `test_cart_runtime.py`, `test_cd_hirq.py` (no local
  native executable). The initial run stopped at that missing Git object;
  neither the baseline nor the runner was changed to make the retry succeed.
- Seven existing negative controls compiled and failed at assertions:
  `MUTATE_CD_HIRQ=1` for CD transfer; DMA indirect `--hold-mutation`
  `drop`, `sticky`, `enable`, `factor`, `stride`; and `--stop-noop`.
- No full build was run. No validator evidence/validation scripts were changed.
  These are implementation method-level results, **not validator acceptance**.

The validator's earlier 68/72 result and live HIRQ result remain historical
facts at their pinned revisions. This local run is a different evidence event,
with native skips explicitly retained. Folded host-path/BFUL integration,
live raw-PUT/selector/discard coverage, the three CDDA gaps and broader method
probe conflicts remain open; no parent milestone or whole branch is promoted.

# Saturn CD candidate promotion status

## Current decision — independent third review received

**IMPL-0120–0132 are ACCEPTED as promotion candidates by the validator.**
0120–0130 retain the second-review verdict; **0131/0132 and scaffold repair
`45dab461` are now explicitly accepted in the third review of
`dd21cbcf194775da984b8e401de8799cc8d461d5`.**

The earlier “awaiting independent review/native runtime” language is superseded.
The native build, native regression run and new live host fixture have been run
by the validator. Local absence of an executable is not an outstanding evidence
gap for that reviewed revision. Candidate acceptance is not a completed
cross-tree port or whole-branch release authorization.

## Evidence pins

- Third-review report: [validator record at c6fc1b2](https://github.com/jkind73/mame/blob/c6fc1b264e9862c7db9c1a8e9ff01687d5835b4a/regtests/saturn/handoff/agent1_validation.md).
- Validator revision: `c6fc1b264e9862c7db9c1a8e9ff01687d5835b4a`.
- Exact report blob: `26ddb6af665e5c23908acb62a56ca6e9f578fdf9`.
- Third review introduced by `f8eafb040424c42df0dd0b8defa1f31367d27c11`;
  reviewed implementation: `dd21cbcf194775da984b8e401de8799cc8d461d5`.
- Historical second review: [a735e034](https://github.com/jkind73/mame/blob/a735e0340a64a5a9369650165e3d423e2a6b9f86/regtests/saturn/handoff/agent1_validation.md#L102-L194),
  report blob `066ba4ba5668ab007bfa55a855fbead51adc161f`, reviewed source
  `b3eece68ae156aa90ad25c6c6308194a32e15348`.

All measured results below are **attributed to the independent validator**,
not new native measurements by the implementation agent.

| Gate at reviewed dd21cbcf | Validator result | Status/scope |
|---|---|---|
| Native build | Exit0, 1218 TUs, approximately202MB binary | Closed for reviewed source |
| `./saturn -validate` | Exit0 | Closed for reviewed source |
| `regtests/saturn/run_all.py` | Exit0, **73 scripts, zero skips** | Closes earlier four local live skips |
| `test_cd_host_runtime.py --require-runtime` | **PASS, 2638 checks** | Requested raw-PUT/reservation/selector/discard fixture is measured, not pending |
| Validator live `test_cd_hirq.py` | PASS | No HIRQ regression; read/ack/masked-delivery review accepted |
| CDDA SCAN | State/boundary/audibility accepted | Scan rms0.223951; programmed -12dB gain accepted; not analog waveform qualification |
| Periodic cadence | Play13.00ms / idle17.00ms | Validator accepts against documented nominal cadence |
| Additional fixtures | Backup RAM, cartridge, sound_boot, SMPC transport exit0 | Results attributed at the report's stated coverage, not all reclassified as sample-level live tests |
| BIOS save/load/replay | PASS, full-image replay identical | Measured BIOS roundtrip, not every active CD transaction/save phase |
| Implementation CD probes | **56 exit0 /11 assertion conflicts**, independently reproduced | Not a green method-probe batch |
| Validator CDDA fixture overall | Exit1, four labels remain | Not an overall CDDA pass; Q instrument and shared tone/capture issues remain |
| Validator `test_cd_lle.py` on this tree | Unknown `-cdblock` option | Harness-incompatible; not a measured device failure |

## Accepted candidates

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
| IMPL-0131 | CD-02 | `1c8e03d4` | ACCEPTED — third review | Q current-position track/control image addressing; not complete Q encoding/readout |
| IMPL-0132 | CD-02/CD-05 | `c4eb8b4d` | ACCEPTED — third review | Bounded SCAN, entry-dependent audibility and saved scan state |

The scaffold repair `45dab461` is independently accepted for preserving existing
assertions/expectations and adding three mock tripwires. The third review accepts
the SCAN-cadence policy and adjudicates `check_cd_idle_cadence.py`'s conflict
**against the stale fixture**, not against0132. Its expectation remains unedited.
The stride2/75Hz scan policy remains an explicitly labelled HLE approximation.

The validator **withdraws `play_q_track` and `scan_moves` as defect evidence**
because its Q readout is not trustworthy. That does not establish a live movement
pass: the movement falsifier remains unadjudicated pending a repaired instrument.
Acceptance of0131/0132 is explicit despite that limitation.

## Remaining integration work — do not reopen completed native gates

1. **Destination folded host path:** semantically port shared-cursor, raw-view,
   word ordering, longword straddle and nonconsuming inspection behavior into
   `cd_reg_offset()` /16-bit `host_r`/`host_w`. Do not replace either HLE wholesale.
   No destination port/merge has been performed by this update. Then rerun
   HIRQ, transfer, LLE (on the branch with that slot) and live host fixtures.
2. **Residual BFUL rule:** the validator closes the normal-path equivalence
   concern, but flags reset/Home clearing `buffull` while capacity can remain
   exhausted. Reconcile allocator/producer/End cause-and-clear behavior with
   the destination rule; do not infer this edge was covered by the2638 checks.
3. **Q follow-up:** repair/qualify Q observation and audit encoding/track/index
   inputs against the actual reviewed source, not the invalid165/10065 readout.
   The report's illustrative `cd_track_at`/index expressions do not literally
   match this implementation's handler; they are not a patch specification.
   The validator's `msf_abs = lba_to_msf_alt(cd_curfad)` correction in f8eafb04
   is source-reviewed, **not runtime remeasured**, and is not applied here.
   Binary/FAD versus inherited BCD/MSF format, pregaps and multisession remain
   explicit scope limits. Do not chase the shared mixer tone labels as faults.
4. **Preserve measured cross-tree delta:** candidate BIOS checkpoint
   time15.560998664/PC06040226 versus destination10.541321676/PC06040228.
   Both replay identically. Record this behavioral difference during the fold;
   the timer explanation is a hypothesis, not an isolated measurement.
5. **Acceptance scope:** do not turn the fixture result into blanket acceptance
   of every raw-PUT/filesystem/active-save/gameplay case.0131/0132 are named in
   the third-review verdict;0117–0119 are not separately adjudicated there.
   Their individual filesystem-reset contracts retain their evidence limits.
   CD-01 through CD-05 and other parent milestones remain open.

## Save compatibility and accounting notes

SCAN adds saved direction/audibility fields. The validator measured a current
BIOS save/load/replay, but did not test an old pre-0132 save file. Compatibility
warning is grounded in the loader: at reviewed dd21cbcf,
`src/emu/save.cpp:502–520` hashes entry names/type sizes/counts and
`:554–559` rejects differing signatures. No old-save runtime result is claimed;
no golden `.sta` or media is committed.

Original assertions remain verbatim and ordered. The validator requests a tally
correction to168 before /171 after (36/21/104/7 before). A fresh local AST-literal
count instead finds169/172 (36/21/105/7 before;36/22/106/8 after). The ledger no
longer uses that disputed total as a gate: **preservation and three added
tripwires are agreed; the one-assert counting discrepancy remains documented**.
No assertion was deleted or modified to force either total.

This update records acceptance and corrects an orphaned field comment only.
No device behavior, fixture expectation, validator asset, milestone ID or
checkbox is changed. Earlier implementation logs remain in the append-only
handoff; their local skips are historical, not pending third-review gates.

# Saturn verification and housekeeping — 2026-10-10

The six requested existing entries are completed as housekeeping and audit work. Their checklist wording and membership are preserved; only the six completion markers change. The CD command audit completion is a completed review, not a declaration that CD HLE implements every operation; remaining implementation findings are explicit in `SATURN_CD_COMMAND_AUDIT.md`.

## Evidence

| Requested entry | Result |
|---|---|
| No environment hooks | The inventory generator searches 114 source files and finds zero `getenv` note entries. `SATURN_TODO_INVENTORY.md` was regenerated from current source and independently compared with the generator output. Its introductory description of the search is not a source hook. |
| Old shared stash | `git stash list` is empty. There were no entries to drop; no stash deletion was performed. |
| Recover standalone tests | Seventeen original files were recovered byte-for-byte into `regtests/saturn/scratchpad`, including both DMAC diagnostics, all four bustest files, four SCU DMA files, hash scripts, WAV transient analysis and sound/key-on diagnostics. The manifest records original paths and SHA-256. Sixteen Lua files parse in the actual MAME Lua runtime; the audio-analysis script runs on a generated stereo 16-bit PCM silence WAV. Historical model assertions and partial-hash limits are documented in `regtests/saturn/README.md`; these are not falsely presented as newly passing current-model timing tests. |
| Source headers | `saturn.cpp` now states actual VDP2 event/counter and SCU timer ownership; the obsolete VBLANK/H-counter claims are gone. Its unresolved DISP interrupt question remains. `saturn_vdp2.cpp` describes implemented timing, latching and arbitration instead of “stub overlay”, retaining the lack of hardware measurement for dedicated-mode edges. |
| Memory notes | The five named notes in the user's `.claude/.../memory` directory have current 2026-10-10 status sections. They retain historical text, state the marker-only checklist rule, locate current reports/tests, correct the old firmware/peripheral scope and preserve outstanding audio/hardware limits. Written files were compared with the prepared updates. |
| ST-162 command audit | Every dispatched command is accounted for in `SATURN_CD_COMMAND_AUDIT.md`. Missing filter queries and several response/selector defects were fixed and tested; unresolved command engines, buffer/connector rules and firmware work are identified explicitly. |

## Validation

The normal SDL3 Saturn target builds; Saturn JP and Die Hard driver validation produce no diagnostics. Selector command methods and existing CD FIFO methods pass ASan/UBSan. Actual CD command register dispatch and no-disc rejection pass on DRC and interpreter cores, including syntax loading the recovered Lua files; logs are in `/private/tmp/saturn-cd-selector-runtime-final-20261010`.

PAL VF2 CD-game regression compares the preceding binary with the corrected binary at frames 1, 60, 300, 600, 1200 and 1800. All six complete save files and pixel buffers match, without byte masking. Runs use isolated directories, the same NVRAM seed and RTC, disabled host input and sequential execution. Logs: `/private/tmp/saturn-cd-housekeeping-vf2-20261010`. This is DRC regression coverage, not a claim of complete game/audio/hardware qualification.

No real-hardware testing was available. CD firmware LLE remains disabled, and the audit documents the remaining HLE mismatches.

## Inventory/checklist constraint

`python3 scripts/saturn_checklist.py scan --inventory-only` is the new explicit option to refresh the separate inventory while preserving the checklist. The normal `check` still fails on the old generated count table in `SATURN_REWRITE_CHECKLIST.md`; this is reported rather than suppressed. The user permits only marker changes in that file, so its count table was not rewritten. The separate inventory matches source exactly and contains no environment-hook entries.

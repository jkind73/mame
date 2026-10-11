# Saturn CD HLE command audit — 2026-10-10

The audit covers every command dispatched by `saturn_cd_hle_device::cd_exec_command`, including the previously missing 47h query. The baseline is Sega ST-162-062094, section 8 (CD interface), especially the function catalogue and specifications on printed pages 75–101. The local Rel.2.5 `segahtml/prgg/sysg/cdif/hon/p08_*.htm` descriptions were checked for revised end-flag and initialization rules. ST-162 describes library operations rather than every command-register byte; register packing was corroborated against local Mednafen/Ymir command definitions without copying their implementation code.

**The command audit is finished. This does not mean the HLE CD block implements every documented operation.** The concrete defects below remain implementation findings, and the existing CD firmware-LLE checklist item remains open. No checklist items were added or split to hold these findings.

## Corrections implemented and tested

- 41h Get Filter Range returns the selected filter's 24-bit start/count and selector number; it was a stub.
- 47h Get Filter Connection is now dispatched and returns pass/fail connections and selector number.
- Filter getters and setters, CD-device input connection, and filter output connections reject out-of-range indices before changing/indexing state. FFh remains the disconnect sentinel. Rejected operations raise CMOK, not ESEL.
- 44h initialization clears conditions while retaining the filter's connectors. 48h reset conditions use a zero FAD count, as specified, rather than FFFFFFFFh.
- 43h subheader readback includes the filter number in CR3. 43h/45h/54h getters raise CMOK without inventing an ESEL completion operation.
- 54h checks sector position against partition occupancy before dereferencing it.
- With no disc inserted, the standard-return helper now preserves the supplied REJECT/WAIT status instead of replacing it with the current drive status. The actual-device diagnostic exposed this defect after the extracted selector methods passed.

## Complete dispatch review

Each row records source behavior or a remaining mismatch. “Implemented” means there is functional source handling; it does not assert hardware-qualified timing or exhaustive game compatibility.

| Code | Operation | Audit result |
|---|---|---|
| 00 | Status | Implemented; asynchronous periodic responses and command response ownership share the legacy pending/CMOK machinery. |
| 01 | Hardware info | Fixed synthetic version/capability response; not derived from firmware. |
| 02 | TOC | Transfers 204 words; no-disc TOC construction still needs safe handling of zero tracks/lead-out. |
| 03 | Session info | Single-session approximation; rereads TOC and forces PAUSE, so session querying is not neutral and multi-session data is absent. |
| 04 | Initialize | Legacy implementation seeks/resets selected state and reports completion immediately. Soft-reset exclusion, delayed ESEL, no-change flag and full initialization/standby/retry parameters are not faithfully modeled. |
| 05 | Open tray | Stops via OPEN status and raises completion flags; HIRQ reads still forcibly clear DCHG, contrary to retaining the event until acknowledgment. |
| 06 | End transfer | FIFO word count and transfer teardown exist, including get/delete; interrupted transfer bookkeeping and host-connector semantics need further implementation work. |
| 10 | Play | FAD/track/resume/repeat handling exists; preservation of prior end position and some track/index combinations remain legacy approximations. |
| 11 | Seek/pause/stop | Implemented status transitions; timed standby entry from PAUSE is absent. |
| 12 | Scan forward/reverse | Acknowledgment-only stub; no pickup scanning. |
| 20, subcode 0 | Subcode Q | Synthesized from track/time information; track indexing and absolute-time construction are not fully qualified against raw subcode. |
| 20, subcode 1 | Subcode R–W | Returns fabricated FF bytes; no decoded pack queue or subcode flags. |
| 30 | CD input connection | Functional, with invalid-selector rejection corrected. |
| 31 | Input connection query | Functional saved selector readback; does not run an ESEL operation. |
| 32 | Last buffer destination | Functional saved destination readback; filter-chain destination bookkeeping below remains a risk. |
| 40 | Set filter range | Functional 24-bit start/count, with bounds validation added. |
| 41 | Get filter range | Implemented in this audit. |
| 42 | Set subheader conditions | Functional six condition bytes; bounds validation added. |
| 43 | Get subheader conditions | Filter echo and completion flags corrected. |
| 44 | Set/reset mode | Condition reset now preserves connectors; invalid selector rejected. |
| 45 | Get mode | Validated readback; no spurious ESEL. |
| 46 | Set filter connections | Selected pass/fail connections updated; selector and destination validation added. |
| 47 | Get filter connections | Implemented in this audit. |
| 48 | Reset selector | Data/conditions/input/pass/fail reset branches exist; partition-output disconnection (bit 3) is unmodeled, and CD input pointer disconnection does not consistently update its saved selector number. |
| 50 | Buffer size | Reports 200 sectors/24 partitions/free storage. System-reserved storage is not separately modeled. |
| 51 | Partition count | Functional valid-selector count; invalid selector still lacks rejection before indexing. |
| 52 | Calculate actual size | Sums stored block sizes; special end-position/count values and invalid/range parameters lack adequate validation; partition-output disconnection is absent. |
| 53 | Actual size query | Functional saved 24-bit word count. |
| 54 | Sector info | Readback works for occupied sectors; bounds and end flags corrected. Last-sector sentinel still needs implementation. |
| 55 | FAD search | Selects greatest eligible FAD at/after position; no-match sentinel exists. Partition-output connector disconnection is absent. |
| 56 | FAD search result | Functional saved result readback. |
| 60 | Sector lengths | Supports 2048/2336/2340/2352; invalid lengths and no-change semantics need explicit validation. |
| 61 | Get sector data | FIFO transfer exists; last-sector sentinel, range-relative WAIT handling and host output connector exclusivity are incomplete. |
| 62 | Delete sector data | Deallocation/compaction exists; special positions, range validation and partial-partition accounting need correction. |
| 63 | Get/delete data | FIFO/deletion handling exists; shares sector-range and connector deficiencies of 61h/62h. |
| 64 | Put sector data | Allocates directly in a partition; should input through a filter, reserve storage/WAIT safely and handle partial transfers. Invalid selector/capacity/null allocation paths are not safe. |
| 65 | Copy sector data | Acknowledgment-only stub, no copy or ECPY result. |
| 66 | Move sector data | Copies through new allocations then frees source; destination treated as a partition rather than an input filter. Full-buffer move, block identity/metadata and invalid source ranges can fail. |
| 67 | Copy/move error | Always reports success; no retained error state for disconnected selector or exhausted buffer. |
| 70 | Change directory | Reads directory records; invalid IDs/directory type and selector routing need validation. |
| 71 | Hold/read directory info | Does not perform the requested directory-window read; only sets an input pointer. |
| 72 | File scope | Legacy count/first-file response; does not fully separate retained self/parent entries from the reported file window. |
| 73 | File info | Single/all-record transfers exist; invalid IDs can index out of range or throw a host fatal error. |
| 74 | Read file | Sector read stream exists; directory/offset validation and logical-sector size accounting are incomplete; EHST is used where the documented file operation completes through EFLS. |
| 75 | Abort file | Pauses/ends some transfer state and raises EFLS; retains or destroys directory information without tracking the operation-specific rule. |
| 90 | MPEG status | Synthetic response; not an emulated MPEG device. |
| 91 | MPEG IRQ | Constant response; no real pending register. |
| 92 | MPEG IRQ mask | Acknowledgment only; no saved mask/state machine. |
| 93 | MPEG init | Synthetic completion flags and register values. |
| 94 | MPEG mode | Synthetic status; no mode engine. |
| E0 | Authenticate | BIOS compatibility behavior, not specified by this ST-162 CD operation catalogue; not firmware authentication. |
| E1 | Disc authentication/type | Synthetic classification; not actual region/media authentication. |
| E2 | MPEG boot ROM | Acknowledgment only; no ROM transfer. |

Library helper operations for issuing commands, transferring data and acquiring register pointers are host-side APIs, not additional missing command codes. MPEG decoding/authorization extensions are not established by the base CD interface manual.

The shared `cd_filterdata` engine also needs review: it limits false-connector traversal to two hops, does not consistently choose the successful filter's true connector, and reverses combined match state rather than only subheader conditions. These affect host/filter and copy/move correctness, not just parameter readback. The source retains these findings; this audit does not conceal them with a complete-CD claim.

## Verification and evidence

- `scripts/saturn_cd_selector_test.py`: actual extracted selector methods, positive readbacks, connector retention, invalid selector/destination/sector boundaries, ASan/UBSan; passes.
- `scripts/saturn_cd_word_test.py`: actual FIFO/End Transfer methods, mixed-width sector crossing and word counts, ASan/UBSan; passes.
- `scripts/saturn_cd_selector_runtime_test.py`: command register dispatch/readback and no-disc rejection in the actual Saturn device graph, DRC and interpreter; both pass. Uses generated diagnostic BIOS contents, not a firmware boot test.
- Normal SDL3 Saturn target builds successfully. Game regression results are recorded in the housekeeping report.
- No real-hardware validation. The audit identifies behavior from manuals and current code; it does not measure firmware command latencies.

Primary reference: [Sega ST-162-062094](https://antime.kapsi.fi/sega/files/ST-162-062094.pdf). Revised reference: local Rel.2.5 CD interface function specifications, especially p08_10 (end flags), p08_15 (selector), p08_16 (buffer), p08_17 (transfers), p08_18 (files).

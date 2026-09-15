# VDP2 implementation report and progress tracker

## A03–A05: CRAM broadcast and palette fixture — 2026-09-15

Mode-0 CRAM writes now merge into **both physical 1K-word halves**, rather than
writing one location and updating pens from another. Each masked word lane is
merged independently into each half; reads remain independent. A mode change
alone must not destroy differing unwritten data. Masked-out writes have no effect.

Primary: ST-058 §3.4, printed pp.43–46 (especially p.46), specifies simultaneous
writes to the two halves. Ymir `VDP2Memory::WriteCRAM` in `vdp_state.hpp` at
6d779960127ced72087a418c1daefc637d0aaa80 and MiSTer `IO_PAL0_WE`/`IO_PAL1_WE` at
a95b085038ace57fa621558d60a7adc7a3c53f78 also broadcast accesses addressed through
the upper half. The manual explicitly describes lower-half writes; upper-half
broadcast and independent reads are cross-implementation evidence, not a new
hardware measurement. No byte-write ignore rule is invented.

`test_vdp2_palette.py` extracts production CRAM reads/writes and palette rebuilds:
**9,216 address/lane/palette cases** plus mode-transition and zero-mask checks pass
under ASan/UBSan. The prior c43dded9 implementation compiles and fails the raw-memory
oracle. All **24 regression scripts and eleven production object builds pass**.
No linked runtime or real save/load acceptance is claimed.

[A03 register ledger](vdp2_registers.md) now inventories all halfwords through 0x11E
and the remaining backing-file range. Per-bit hardware masks/reset/latch verification
is still open. A04 has a real palette fixture, not yet a full-background/window
fixture. A05's mode-0 write defect is fixed; mode-2 physical layout across mode
changes, coefficient interactions and physical color-output precision remain open.
Current MAME `pal5bit` expansion is preserved; the manual's zero-filled low bits
require a separate pipeline audit. None of the parent A03–A05 tasks is marked done.


**Audit date:** 2026-09-15  
**Audited implementation:** `ad5ae529` on `arena/01a09f50-mame`  
**Scope:** Saturn/ST-V VDP2 device, background renderer, VDP1-to-VDP2 composition, memory/register integration and validation. This is a source-level baseline, not hardware certification. No emulation code changes are included in this report.

## 1. Executive summary

VDP2 is **substantially implemented but not feature-complete**. Normal backgrounds, bitmap/tile rendering, rotation backgrounds, scroll tables, basic priorities, RGB/palette output, ordinary blending, color offsets, windows, timing/status and framebuffer composition have working code paths. Several important effects are partial, gated off, or missing.

The largest functional gaps are:

- **Complete per-pixel composition:** special priority, special color calculation, sprite-window masking, destination-layer-aware shadows and additional color-calculation modes.
- **Line-color screen and mosaic integration:** helper functions exist, but their normal background postprocessing calls are disabled by `TEST_FUNCTIONS == 0`. The mosaic test does not mean the feature is enabled.
- **Rotation edge cases:** screen-over-pattern mode is explicitly unsupported; parameter switching and window behavior have incomplete paths.
- **Scroll combinations and reduction controls:** only a subset of combined vertical cell scroll/line scroll is handled; reduction-enable controls are defined but not applied by a complete limiter implementation.
- **Raster-visible register/memory changes:** the renderer supports clip rectangles, but generic VDP2 writes do not first preserve the already-scanned image. The new VDP1 erase-driven partial updates are not a general VDP2 raster-effects implementation.
- **VRAM access scheduling:** cycle patterns are checked for access-command presence, not modeled as a bank/slot-accurate fetch and CPU-contention system.
- **Timing and qualification:** true interlace/half-lines, PAL/exclusive modes, physical counter edges, real save/load and linked runtime/performance testing remain open.

Do **not** assign a completion percentage: individual features have very different scopes, and most combinations have not been qualified. Likewise, the old source comment calling the device a “stub overlay” describes the separate timing device, not the entire renderer.

## 2. Status definitions and tracking rules

- **Implemented:** an active production path exists. This does not certify every legal combination.
- **Partial:** a useful subset exists, with identified omissions or approximations.
- **Missing/gated:** no effective complete path was found, or the path is disabled in normal builds.
- **Qualification open:** code exists, but sufficient hardware or linked-runtime evidence is absent.
- `[x]` records a completed, narrowly stated baseline fact or task. It does not close the parent feature.
- `[ ]` records remaining implementation or verification work. Keep stable IDs when updating this report.

Every future implementation entry should record: primary-document section, independent cross-checks and disagreements, production-code changes, positive tests, a failing old-code/mutation test, object/build validation, commit and runtime acceptance where available. Never mark a feature complete merely because a register macro exists or its TODO disappeared.

## 3. Architecture and source map

| Component | Current responsibility | Main source anchors |
|---|---|---|
| VDP2 device | TVMD/EXTEN/TVSTAT/VRSIZE/HCNT/VCNT, CRTC, sync callbacks, field state | `src/mame/sega/saturn_vdp2.cpp`, `.h` |
| Legacy renderer | Register backing, VRAM/CRAM, all background drawing, rotation, windows, color operations | `src/mame/sega/saturn.cpp` |
| Normal planes | NBG0–NBG3 configuration and tile/bitmap dispatch | `vdp2_draw_NBG0` through `vdp2_draw_NBG3` |
| Rotation planes | Parameter decoding, coefficient fetch, cached source maps, transformed sampling | `vdp2_fill_rotation_parameter_table`, `vdp2_copy_roz_bitmap`, `vdp2_draw_rotation_screen`, `vdp2_draw_RBG0` |
| Sprite composition | VDP1 framebuffer interpretation, priority, window and color/shadow operations | `draw_sprites`, `vdp1_display_pixel`, `screen_update_vdp2` |
| Memory and derived state | Register/VRAM/CRAM handlers, palette rebuilds, cache invalidation and postload | `vdp2_regs_*`, `vdp2_vram_*`, `vdp2_cram_*`, `vdp2_state_save_postload` |
| Regression framework | Extracted production functions with stand-ins, full object compilation | `regtests/saturn/test_*.py`, `run_all.py`, `validate_build.py` |

Function names are the durable anchors; line numbers move as implementation progresses. A later device extraction may be useful, but it is not a prerequisite for correcting behavior and must not be counted as a hardware feature.

## 4. Feature-by-feature assessment

| Feature group | Already present | Missing, partial, or not qualified |
|---|---|---|
| Normal backgrounds | NBG0, NBG1, NBG2 and NBG3 enable/configuration and drawing paths | Exhaustive layer/color-depth/resource-conflict matrix; special-function behavior |
| Character backgrounds | Tilemap/page/plane addressing, pattern-name handling, character-size and flip paths | Per-layer format restrictions, supplementary fields, boundaries and address wrapping need dedicated image oracles |
| Bitmap backgrounds | Bitmap-size/map/palette selection; palette and direct-color drawing paths | Complete legal per-layer combinations and wrap/clip/zoom/window qualification |
| Color formats | Palette-based paths and RGB555/RGB888 helpers | This is not proof all 16/256/2048-color and direct-color combinations work on every eligible layer; a non-bitmap 2048-color diagnostic remains |
| Ordinary scroll/zoom | Scroll registers, coordinate increments and zoom drawing helpers | Fractional precision, wrapping and zoom limits need systematic verification |
| Line scroll/line zoom | Horizontal/vertical line-scroll and line-zoom table processing | All interval/combination/format interactions and raster writes are not covered |
| Vertical cell scroll | An implemented combined branch with table addressing and partial-clip fixes | Branch requires horizontal line scroll and excludes vertical line scroll and line zoom; unsupported combinations remain |
| Reduction enable | ZMCTL reduction bits are defined | Complete enforcement of reduction limits is not present |
| RBG0 | Rotation A/B parameter loading, transformed sampling and coefficient processing | Rounding, coefficient transitions, read-control latches and all parameter-mode combinations need qualification |
| RBG1 | Routed through the NBG0 configuration/rotation path | Resource conflicts, priority/window integration and cycle-pattern checks are incomplete; not equivalent to a separately qualified full RBG1 implementation |
| Rotation coefficients | VRAM and CRAM coefficient-source paths; coefficient-size/mode handling | Addressing, signed stepping, coefficient flags, line-color use and all modes need independent image tests |
| Rotation parameter switching | Multiple parameter paths and rotation-window preparation exist | Mode-3/no-transform path has a documented limitation; parameter switching/read-control edge cases remain |
| Screen-over processing | Repeat and transparent-outside paths, including 512×512 restriction | Mode 1 does not draw OVPNRA/OVPNRB screen-over characters; it falls back to clipping behavior |
| Back screen | Single-color and per-line color, DISP/BDCLMD handling and color offsets | Dedicated partial-update/table-wrap tests and the historical Biohazard symptom need verification |
| Line-color screen | `vdp2_draw_line`, table access and configuration fields exist | Ordinary postprocessing invocation is gated off; correct insertion into the color-calculation pipeline is incomplete |
| Mosaic | Bounds-aware helper and focused clipping tests exist | Production invocation is gated off; per-layer source sampling/composition and rotation behavior are not complete |
| Ordinary priorities | Layer priorities and eight sprite priority selectors feed ordered composition | Tie rules and all sprite types need exhaustive tests; final RGB output does not retain sufficient layer identity for all effects |
| Special priority | Register definitions and layer configuration fields exist | A complete SFPRMD/SFSEL/SFCODE-driven per-dot priority implementation was not found |
| Ordinary color calculation | Ratio and additive helpers, per-layer enables, sprite conditions and color offsets | Exact selection of eligible second image, rounding and interaction with windows/shadows are not fully qualified |
| Special color calculation | Register definitions and some related pattern configuration | Complete SFCCMD/per-dot special-function eligibility is missing/incomplete |
| Extended calculation / gradation | Control bits are described in the register comments | Complete EXCCEN, CCRTMD and BOKEN-related operation paths were not found; require explicit implementation audit and tests |
| Color offset A/B | Signed RGB offsets, clamps, enable/select handling and cached faded palettes | Mid-display changes and ordering relative to calculation and special effects need verification |
| Window 0/1 | Coordinate/table reads, inside/outside evaluation, AND/OR combination and per-line caching | Boundary/resolution combinations and differences between basic and rotation paths need dedicated tests |
| Sprite window | Control fields and limited sprite pixel rejection exist | Generic window evaluation uses window 0/1 but does not combine a complete sprite-derived mask; end-to-end support is incomplete |
| Color-calculation window | Some shared window infrastructure exists | A complete independently qualified calculation-only window/eligibility path was not established |
| Shadows | Normal-shadow and opaque-path MSB-shadow behavior exists | Alpha-path MSB shadows and underlying-layer eligibility are incomplete; code comments acknowledge this |
| VDP1 scanout integration | Normal/packed output, interlace caches, rotation input and HDTV replication; output-coordinate compositor | Full sprite-type/window/shadow matrix and hardware readout phases remain open |
| Raster effects | Clip-aware rendering; recent VDP1 active-erase callbacks force partial presentation | VDP2 register, VRAM and CRAM changes are not generally sequenced against already-presented output |
| VRAM | Allocated storage, CPU handlers, decode updates and cache invalidation | All VRSIZE/bank/partition/address-mask interactions need audit; physical access-slot effects and contention are incomplete |
| Cycle patterns | Presence checks for character/pattern-name access commands | Slot counts/order, bank ownership, bandwidth, fetch denial/corruption and CPU waits are not modeled comprehensively |
| CRAM | 4 KiB storage; 15-bit/24-bit palette paths; palette rebuilds and mode-0 palette mirroring | Mode-0 backing/read alias behavior is a TODO; byte-write behavior is unresolved. Mode 3 falls through to the 24-bit path and must not be certified as a legal mode |
| Registers | Backing register file mirrors, masked writes, decoded device status/control paths | Per-register masks, access widths, read-only/write-only behavior, reset values and latch times require a complete inventory |
| TV modes | Display enable, horizontal/vertical resolution and CRTC reconfiguration | Interlace half-lines, PAL, DOTSEL coordination and exclusive-mode timing retain explicit uncertainty |
| Counters/status | H/V latches, ODD state, V-counter table, TVSTAT behavior and external latch callback | Physical beam accuracy, wrap edges, exclusive modes and external sync qualification |
| External inputs | EXTEN fields, latch control and flags | External background/MPEG/genlock rendering is missing; actual external synchronization is not established as complete |
| Reset/save | Device fields and backing memories registered; decoded graphics/palette/rotation caches rebuilt after load | Full reset coverage, every derived cache and real MAME round trips mid-raster remain unqualified |
| Performance | Cached rotation maps, windows, palettes and decode invalidation | No current linked benchmark; large rotation maps and combined scroll/partial-update workloads remain risks |

## 5. What has actually been tested

The latest implementation baseline passed **23 Saturn regression scripts and eleven production object compilations**. That is the whole Saturn suite, **not 23 dedicated VDP2 tests**. This documentation audit does not claim a new linked build or hardware run.

| Test | Evidence provided | Important limit |
|---|---|---|
| `test_tvmd.py` | Actual reset/register/CRTC helper behavior using recording devices | Not physical timing or every TV-mode transition |
| `test_exten.py` | Actual reset/read/write and external latch callback | Not genlock, external video or physical beam verification |
| `test_vcounter.py` | Table equivalence, field-line indexing and counter encoding | Historical lookup equivalence is not silicon proof |
| `test_sync.py` | Production sync callback control flow and scheduling | Not real timer/CPU interrupt delivery or exact clocks |
| `test_cell_scroll.py` | Clip containment, table addressing and column-call counts | Nested renderer, hardware column width and unsupported combinations are not certified |
| `test_mosaic.py` | Production helper clipping/bounds | Helper is not enabled in the normal pipeline; alignment and multi-layer composition are not certified |
| `test_sprite_scanout.py` | 3,036 compositor/readout image cases across modes, clips and selected effects | Palette/window evaluation and devices are stand-ins; full shadow/window/color hardware behavior is not certified |
| `test_vdp1.py` | Additional rotation/field integration and erase-driven presentation sequencing | Primarily VDP1; the recording screen is not a complete VDP2 render/save round trip |
| SCU timer/IRQ tests | Related timing-consumer integration | Not a substitute for VDP2 raster accuracy |

Not currently established by dedicated end-to-end image suites: all NBG formats, all RBG modes, actual window logic combined with layer rendering, special priorities/calculation, line-color insertion, sprite-window masks, underlying-layer shadows, VRAM scheduling and mid-display CRAM changes.

Runtime acceptance from earlier work remains narrowly scoped to the user's AB2 boot/explosions, Power Drift cars and OutRun flashing observations. These are **not VDP2-wide acceptance**. The separately reported title/logo placement issue remains open and is not assigned to VDP2 without evidence.

## 6. Prioritized multi-level implementation checklist

### P0 — Establish trustworthy pixel and register baselines

- [x] **V2-A01** Audit both device and legacy-renderer ownership, rather than treating one file as the entire VDP2.
- [x] **V2-A02** Record active paths, gated helpers, source TODOs and test limitations in this report.
- [ ] **V2-A03** Build a complete register ledger against ST-058: offset, bit mask, access type/width, reset, latch boundary, active consumer, tests.
  - [ ] Distinguish defined-but-unused fields from implemented fields.
  - [ ] Separate prohibited combinations and undocumented aliases from legal features.
  - [ ] Reconcile RAMCTL, VRSIZE, TVMD/EXTEN and CRAM-mode behavior.
- [ ] **V2-A04** Add extracted full-background/compositor image fixtures, with real production palette and window evaluation where practical.
  - [ ] NBG0–3, bitmap/cell, legal color formats, page/plane boundaries, flips and transparency.
  - [ ] Clipped updates versus an equivalent full-frame reference.
  - [ ] Layer-over-layer scenes preserving which source should win and which should blend.
  - [ ] Negative mutations for each newly covered behavior.
- [x] **V2-A05a** Correct mode-0 write broadcast and test legal word/longword lanes, independent reads and immediate/rebuilt palette agreement.
- [ ] **V2-A05** Audit CRAM mode-0 storage/read aliases and legal word/longword writes before relying on the palette as an oracle.

### P1 — Correct composition and ordinary visual effects

- [ ] **V2-C01** Establish per-pixel source identity/priority/eligibility sufficient for correct effect selection.
  - [ ] Top image and eligible second image selection.
  - [ ] Same-priority tie order and priority-zero suppression.
  - [ ] All sprite types and palette/direct-RGB encodings.
- [ ] **V2-C02** Implement/qualify normal and MSB shadows across opaque and calculation paths.
  - [ ] SDCTL eligibility based on the actual underlying layer.
  - [ ] Sprite-window conflicts, transparent shadow codes and priority interactions.
- [ ] **V2-C03** Complete window behavior.
  - [ ] Window 0/1 boundaries, line windows, AND/OR and disabled-window neutral values.
  - [ ] Sprite-derived mask as a real window input.
  - [ ] Calculation-only windows and rotation-parameter windows.
  - [ ] Partial clips, interlace and high/exclusive resolution coordinates.
- [ ] **V2-C04** Complete special priority and special color calculation.
  - [ ] SFPRMD, SFCCMD, SFSEL/SFCODE and pattern-name/dot attributes.
  - [ ] Eligibility before blending, rather than a late RGB-only approximation.
- [ ] **V2-C05** Qualify ordinary ratio/additive calculation and color-offset ordering.
  - [ ] Ratio extremes, integer rounding and overflow/clamping.
  - [ ] Correct second-image eligibility and sprite condition modes.
  - [ ] A/B signed offsets before/after each operation as specified.
- [ ] **V2-C06** Implement/qualify extended calculation, ratio-source selection and gradation controls.
- [ ] **V2-C07** Integrate line-color screen as a proper calculation input.
  - [ ] Single/per-line tables, enables, coefficients and ratio behavior.
  - [ ] Remove the production gate only after image tests prove placement.
- [ ] **V2-C08** Integrate mosaic per eligible layer.
  - [ ] Source-sample origin, horizontal/vertical sizes and partial clips.
  - [ ] Prevent mosaic from modifying already-composited unrelated layers.
  - [ ] Rotation constraints and scroll/window/calculation combinations.
  - [ ] Remove the production gate only after qualification.

### P2 — Scroll and rotation completeness

- [ ] **V2-S01** Qualify ordinary fractional scroll/zoom and implement reduction-enable limits.
- [ ] **V2-S02** Complete line-scroll, vertical line-scroll, line-zoom and vertical cell-scroll combinations.
  - [ ] Table stride/interval, simultaneous NBG0/NBG1, screen-left anchoring and wrapping.
  - [ ] Correct per-dot/column behavior without an uncontrolled nested-render cost.
- [ ] **V2-R01** Implement screen-over-pattern mode using OVPNRA/OVPNRB.
- [ ] **V2-R02** Qualify rotation A/B parameters, fixed-point precision and coefficient tables.
  - [ ] VRAM/CRAM, short/long coefficient entries, signed increments and flags.
  - [ ] Repeat, transparent and 512×512 screen-over modes.
- [ ] **V2-R03** Complete parameter-selection modes and read-control behavior.
  - [ ] Window selection with and without a geometric transform.
  - [ ] Coefficient-based switching and line-color interaction.
- [ ] **V2-R04** Qualify RBG1/NBG0 sharing, resource restrictions and rotation caches.

### P3 — Raster state and VRAM bus behavior

- [ ] **V2-T01** Preserve scanned output before render-affecting register/CRAM/VRAM writes.
  - [ ] Define latch granularity from primary documentation, not an unconditional flush on every write.
  - [ ] Verify memory changes, color offsets, windows, scroll and priority changes independently.
  - [ ] Ensure active VDP1 erase-triggered updates do not duplicate or lose rendering.
- [ ] **V2-T02** Implement bank/slot-aware cycle-pattern validation and fetch behavior.
  - [ ] Bank partitioning, access-command counts/order and screen-mode bandwidth.
  - [ ] RBG1 and coefficient/table fetch restrictions.
  - [ ] CPU availability/contention and insufficient-fetch consequences, supported by hardware evidence.
- [ ] **V2-T03** Qualify VRAM size/address masking and cache invalidation for all consumers.

### P4 — Display timing and external interfaces

- [ ] **V2-H01** Qualify NTSC/PAL field lengths, half-lines, ODD and H/V counter wrap/latch edges.
- [ ] **V2-H02** Qualify interlace and exclusive modes, clock changes and SMPC DOTSEL coordination.
- [ ] **V2-H03** Audit external latch/sync flags and reset behavior against real callback timing.
- [ ] **V2-H04** Implement external-background/MPEG/genlock input and composition where supported.
  - [ ] Keep external-device input provisioning separate from the VDP2 mixer.
  - [ ] Explicitly identify any configuration for which the external source is absent.

### P5 — Save/reset, performance and acceptance

- [ ] **V2-Q01** Audit register, memory, decoded state and all derived caches across reset/postload.
  - [ ] Window/fade/rotation caches and any new per-pixel/raster state.
  - [ ] Mid-line and mid-field save/load with no stale picture or duplicate event.
- [ ] **V2-Q02** Link the focused Saturn/ST-V executable and run `-validate`.
  - [ ] Resolve the SDL/pkg-config dependency blocker; prior Debian fetch attempts failed.
- [ ] **V2-Q03** Run real MAME save/load and BIOS/Saturn/ST-V visual smoke tests.
  - [ ] Preserve user-accepted prior fixes; record the exact build and scene.
  - [ ] Obtain independent expected images or traces for the new VDP2 features.
- [ ] **V2-Q04** Profile before optimizing.
  - [ ] Large rotation maps and invalidation frequency.
  - [ ] Combined scroll effects, windows and repeated partial updates.
  - [ ] Prove image equivalence for every optimization.
- [ ] **V2-Q05** Investigate the separate title/logo placement report without assuming the responsible chip.
- [ ] **V2-Q06** Close historical game notes only with current reproducible evidence.

## 7. Recommended work order and acceptance gates

1. **Register/palette and pixel fixtures (A03–A05).** Needed to avoid “fixing” the compositor against an incorrect palette or mocked window oracle.
2. **Composition core, shadows and windows (C01–C03).** This enables reliable special-function, line-color and mosaic work.
3. **Special calculation and gated effects (C04–C08).** Do not simply turn on `TEST_FUNCTIONS`.
4. **Scroll combinations and rotation gaps (S01–R04).** In particular screen-over-pattern is a bounded implementation target.
5. **Raster-write and bus accuracy (T01–T03), with timing work (H01–H03) as needed.** Source the latch model before broad write-handler changes.
6. **External video and final qualification (H04, Q01–Q06).** Save/load, runtime and performance checks should also accompany earlier increments whenever a linked build is available.

An item closes only when its implementation and test evidence are recorded. Hardware-sensitive items may remain “implemented; qualification open” after the code lands. A passing extracted test is not a substitute for a linked game or real save-manager test.

## 8. Historical notes requiring care

The source lists examples involving Decathlete, dragndrm, Magical Drop logos, Dokyusei/dokyuif, Shienryu stage 2, Scud, window transitions, Batman Forever's Riddler scene, Radiant Silvergun, Biohazard and others. These are **historical investigation leads**, not freshly reproduced defects on the audited commit.

Two particularly misleading completion signals:

- “Mosaic missing” is not wholly obsolete: clipping in the helper was fixed, but its ordinary production integration remains disabled.
- “ODD/H/V counters not emulated” is too broad: counter/status code and regression fixes exist, while physical timing qualification remains open.

Do not delete old evidence merely to make the checklist appear shorter, and do not assign every title-position issue to VDP2 without tracing its source coordinates and composition.

## 9. Reference and evidence policy

Primary baseline: [Sega VDP2 User's Manual, ST-058-R2-060194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-058-R2-060194.pdf), plus relevant SDK supplements/bulletins. Existing section-specific audit notes are in [official_specs.md](official_specs.md).

Independent cross-check baselines already used in this project:

- Ymir revision `6d779960127ced72087a418c1daefc637d0aaa80` — device timing and software renderer.
- MiSTer Saturn revision `a95b085038ace57fa621558d60a7adc7a3c53f78` — VDP2 and VDP1 interface RTL.

This report audits local production code and existing test scope; it is **not** a fresh line-by-line comparison of the entire Sega manual against both independent implementations. Each future item must pin the actual source sections consulted and document disagreements rather than silently selecting a convenient emulator behavior.

## 10. Progress log

| Date | Change | Evidence | Status |
|---|---|---|---|
| 2026-09-15 | Initial VDP2 source audit and stable-ID tracker against `ad5ae529` | Both production components, renderer gates, selected function bodies and all current test descriptions inspected | Documentation baseline; no new VDP2 implementation or runtime acceptance |

For future rows: include checklist IDs, commit, tests/mutations, object/linked-build result, source references and any remaining acceptance gate.

# Sega SDK hardware-document audit

Date: 2026-09-14. Repository: `jkind73/saturnsdk`.
Pinned revision: `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`.

## Coverage and provenance

The complete, non-truncated Git tree contains 3,968 files, including 106 paths
ending in `.pdf`. Three are `._` metadata companions; excluding those leaves
**103 PDF documents** (65,492,354 bytes). See [sdk_documents.csv](sdk_documents.csv)
for paths, Git blob hashes, byte sizes, and text-extraction status. The manifest
covers PDFs, not the repository's additional DOC/TXT files or compressed archives.

95 PDFs were converted to searchable text with pypdf. Eight have no extracted
text in this pass; see the manifest. The batch encountered a null encryption
entry parsing error; that error is not a finding about document contents, and
we have not classified the individual remaining failures. PDF page counts in
the manifest come from successful text extraction. **Extraction/indexing is not
reading or validating every document.** Selected sections actually read are below.
Diagrams/tables extracted as text may lose layout; ambiguous diagrams require
visual review before implementing their behavior.

Manuals and extracted text are cached outside the repository, not committed.
Only bibliographic metadata and original analysis are added. Repository hosting
does not imply redistribution permission for Sega manuals, SDK code or libraries.
The cache is disposable; pinned links and blob hashes are the durable references.

## Core reference map

All links below point to the pinned SDK revision. PDF page numbers are one-based
file pages, distinct from the manual's printed page numbers.

| Document | Role | Review in this pass |
|---|---|---|
| [ST-058-R2-060194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-058-R2-060194.pdf) — VDP2 User's Manual v1.1 | Registers, counters, scroll and compositing | Selected sections listed below |
| [ST-013-R3-061694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf) — VDP1 User's Manual | Drawing, framebuffer control | Indexed; behavior sections not yet audited |
| [ST-013-SP1-052794](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-SP1-052794.pdf) — VDP1 supplement | Supplementary VDP1 information | Indexed only |
| [ST-097-R5-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-097-R5-072694.pdf) — SCU User's Manual, third version | DMA, interrupts, DSP, timers | Timer registers §3.4, printed pp.55–56 / PDF pp.71–72; interrupt masks/status PDF p.74 |
| [ST-210-110194](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-210-110194.pdf) — SCU Final Specifications: Precautions | Corrections and hardware restrictions | Items 20–24, PDF p.11; items 29–32, PDF p.13 |
| [ST-077-R2-052594](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-077-R2-052594.pdf) — Saturn SCSP User's Manual | Audio hardware | Indexed; earlier source citations not revalidated yet |
| [ST-169-R1-072694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-169-R1-072694.pdf) — SMPC User's Manual | System manager and peripherals | Indexed only |
| [Sattechs.pdf](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/Sattechs.pdf) — technical bulletin collection | Corrections and programming guidance | Bulletin #12 PDF p.54; #14 PDF pp.56–59; slave interrupt discussion PDF p.88 |
| [ST-202-R1-120994](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-202-R1-120994.pdf) — Dual CPU User's Guide | CPU coordination | Indexed only; use alongside DCC and slave-IRQ investigation |
| [sh7604.pdf](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/sh7604.pdf) | SH-2 reference candidate | Located, text not extracted; not yet reviewed |

## Findings affecting the current branch

### 1. SCU timer work is not complete

ST-210 item 30 (printed p.9, PDF p.13) explicitly places timer-0 compare value
**0 at VBlank-OUT**, and lists positive compare values against HBlank-IN, including
263 for the NTSC example. ST-097 §3.4 says the counter increases on HBlank-IN and
clears at VBlank-END.

Current `vblank_out_w()` clears the counter but does not check timer 0. Current
`hblank_in_w()` compares before incrementing. This needs an event-order fix and
trace tests; the earlier scheduler fix restored missing edges but did not fix
these compare semantics. TENB gating and exact frame phase must be considered
before changing ordering.

ST-210 item 31 explicitly says timer 1 reloads on HBlank **when stopped**. It also
confirms that a programmed zero represents 512 counts. Current `hblank_in_w()`
re-arms `m_timer1` on every eligible HBlank, even if it is still running. A count
longer than one line can therefore be perpetually postponed instead of completing.
This is the highest-priority next behavioral fix, with tests for repeated HBlank,
expiry, disable, reload-register writes and T1MD. The existing zero-to-512 conversion
is supported, but by itself is insufficient.

ST-210 item 24 says DMA-illegal status does not occur during indirect DMA execution.
Audit this against the inherited directional validation before claiming DMA rules
complete. Items 21–22 document enable-gated start factors and one held trigger;
they provide concrete future DMA test cases.

### 2. V-counter bounds fix versus counter encoding

ST-058 §2.2, printed p.24 / PDF p.42, table 2.4 describes a **10-bit** double-density
counter: field count in bits 9:1, odd/even indication in bit 0 (0 odd, 1 even).
The current approximate expression replaces bit 0 of an unshifted field count and
masks to nine bits. That is not the documented encoding. The same manual table's
non-interlace encoding conflicts with the hardware-test note inherited in MAME.
Do not silently change all modes based on the table alone: obtain the hardware
trace behind that note and cross-check interlace separately.

Our `vpos / 2` change fixes table addressing within MAME's doubled screen geometry;
it does not establish the register's real encoded value or rollback positions.
The prior table-equivalence tests are preservation tests, not hardware oracles.

### 3. Vertical cell scroll: confirmed layout, missing fractional behavior

ST-058 §5.1, printed pp.134–136 / PDF pp.152–154, documents screen-left table order,
relative vertical offsets, and alternating NBG0/NBG1 entries when both are enabled.
This supports preserving screen-anchored addressing in our clip fix. Bitmap format
uses eight-dot units. It does **not** by itself justify the proposed unconditional
16-dot width change for larger character patterns.

Figure 5.7 includes an **eight-bit fractional part** alongside the eleven-bit
integer part. The current path reads only the upper halfword and drops the
fraction. Bulletin #14 (PDF pp.56–59) gives a bitmap technique combining vertical
cell scroll and line scroll, with fractional values. The current branch expressly
excludes combined vertical-line-scroll/line-zoom cases. Clipping safety tests do
not cover those missing hardware functions.

### 4. Mosaic remains incomplete even with safe bounds

ST-058 §4.11, printed pp.117–119 / PDF pp.135–137, describes upper-left sampling
per mosaic block, sizes, horizontal-only rotation mosaic, and mosaic priority over
vertical cell scroll. The current helper's interlace/rotation handling and block
origin need a hardware-level review; preserving existing output in the bounds test
is not validation of these rules. Keep the incomplete post-processing paths gated
until per-layer transparency/compositing is correct.

### 5. Screen-over pattern has a cell-format restriction

ST-058 screen-over discussion, printed p.115 / PDF p.133, confirms the one-word
pattern-name interpretation, supplementary bits, and per-rotation-parameter A/B
selection. It also explicitly excludes the repeated over-pattern mode for bitmap
format. The supplied candidate patch lacked that restriction, in addition to the
previously identified decoding and address-wrap problems. Do not apply it wholesale.

### 6. CRAM byte writes are prohibited, not documented as ignored

ST-058 §1.2, printed pp.3–4 / PDF pp.21–22, permits word/longword accesses to CRAM
and registers and prohibits byte access. This supports a software restriction,
not the proposed implementation claim that all byte writes have no effect.
ST-210 item 32 (PDF p.13) distinguishes external longword reads from byte-sized
writes on the A/B buses; it does not specify the VDP2's response to an illegal
CRAM byte write. Hardware tests are still required for that response.

### 7. TVSTAT citation verified; slave timing needs separate care

Bulletin #12 item 3 (PDF p.54) confirms that DISP=0 forces the TVSTAT VBLANK bit to
one. It does not say to force HBLANK or suppress SCU interrupts. The existing
TVSTAT comment correctly limits the claim to that flag.

The slave-interrupt discussion in Sattechs PDF p.88 confirms level-sensitive
blank interrupts through DCC, with HBlank vector 0x41 and VBlank vector 0x43.
It does not by itself prove the exact VBlank gating adopted from Ymir. Keep that
emulator comparison distinct from the official-document evidence.

## Next implementation and validation order

1. Fix timer-1 running/reload behavior against ST-210 item 31, cross-check Ymir
   and another implementation, and add event-order tests.
2. Resolve timer-0 compare-zero/increment order against item 30 and actual CRTC
   phase; test both NTSC and PAL plus TENB/T1MD interactions.
3. Verify interlace register encoding and field transitions with independent
   traces before altering the preserved rollback tables.
4. Implement missing scroll/compositing behavior with per-pixel tests derived
   from manual rules and bulletin #14 examples, not just existing MAME output.

No emulation behavior changed in this documentation pass. All new findings are
open until implemented and validated. Official Saturn documents establish shared
chip behavior, but ST-V board-specific wiring still needs separate evidence.

## Implementation update: timer-1 reload

The stopped-only reload issue identified in finding 1 is now fixed and covered by
`test_timer1.py`; see the [test report](README.md#scu-timer-1-stopped-only-reload-fix).
The earlier findings describe the code as inspected during the document audit.
Timer-0 ordering, T1MD interrupt qualification, hardware timer rate, and the other
open findings are not resolved by this narrowly scoped fix.

## Implementation update: timer-0 event order

The compare-zero and increment-order discrepancies in finding 1 are now fixed:
TENB gates counting, zero is checked at VBlank-OUT, and positive compares follow
the HBlank increment. See the timer-0 section in README.md for 8,192 tested
scenarios and remaining limitations. Current CRTC phase, mid-line register-write
behavior and full timer-1 mode qualification have not been hardware-validated.
The original findings and next-work list above are the historical audit, not the
current completion status; these implementation updates supersede them narrowly.

## Implementation update: double-density V-counter encoding

Finding 2's double-density bit-layout discrepancy is now corrected: nine field
count bits in VCT9..1, inverse ODD in VCT0, ten bits retained. The ST-058 table 2.4
interpretation was cross-checked with Ymir and Mednafen. Tests independently cover
all count/field combinations and external-latch storage; see the README report.
The non-interlace manual/hardware-note discrepancy, field geometry and rollback
values remain unresolved. Earlier statements describing the approximate encoding
refer to the pre-fix audit, not the current getter.

## Additional reset audit: EXTEN

Read ST-058 §2.5, printed p.19 / PDF p.37, covering EXTEN reset and latch-source
selection. Confirmed the all-zero reset against Ymir and Mednafen. Corrected the
MAME reset's stale decoded control bits; register readback now agrees with the
external-latch enable and other controls. See `test_exten.py` and README.md for
64 tested scenarios and limits. This does not validate the whole VDP2 reset or
TVMD initialization; those remain separate audit items.

## Additional reset audit: TVMD

Read ST-058 §2.4, printed p.16 / PDF p.34, confirming TVMD clears on power-on/reset.
Verified with Ymir/Mednafen. TVMD and decoded display/mode controls now initialize
before the startup clock callback and clear on device reset before CRTC setup.
3,072 scenarios cover initializers, register handlers and reset/CRTC helpers.
This supersedes the previous note that TVMD initialization remains unaddressed;
other reset registers, actual screen scheduling and SMPC reset wiring remain open.

## Address-map audit update: C-Bus mirrors

The missing `0x07xxxxxx` C-Bus decode was corrected using the existing Saturn/ST-V
memory maps plus Ymir GetBusID and Mednafen AddressToBus/DMA_ReadCBus. The README
records 768 classification checks and 2,304 direct DMA scenarios. This is an
explicit source/emulator cross-check: a precise official mirror-aperture section
has not yet been established, and no hardware measurement is claimed.

## Indirect descriptor audit update

Read ST-097 §2.1, printed pp.19–20 (PDF pp.35–36), §3.2 printed p.42 (PDF p.58),
and ST-210 item 25, printed p.8 (PDF p.12). These distinguish indirect descriptor
execution/format from direct count registers. The all-channel twenty-bit descriptor
width and zero-to-1-MiB rule are supported by Ymir/Mednafen, with MiSTer confirming
the width, not explicitly by the inspected manual prose. Corrected the narrower
channel-1/2 mask and zero handling; 54 legal two-entry chains now pass through
completion. Runtime/clock/arbitration and unusual transfer cases remain open.

## Two-channel DMA priority audit update

Re-read ST-097 §3.2, printed p.41 / PDF p.57, and ST-210 items 20 and 35 (printed
pp.7/10, PDF pp.11/14). Fixed the tick state update that suspended the new winner
rather than the lower-priority previous owner. Ymir and Mednafen independently
select active channels in descending priority. 64 supported two-channel scenarios
cover preemption/resume; the separate halt handoff fix preserves MAME's existing
approximate policy, not Mednafen's bus-dependent implementation or proven physical
CPU-halt behavior. Exact latency and unsupported overlaps remain open.

## Held external DMA trigger audit update

ST-210 printed p.7 / PDF p.11, items 21–23, establish enabled matching events,
one held activation and the prohibition on rewriting active registers. ST-097
printed pp.45–46 / PDF pp.61–62 supplies the enable/start/update definitions.
Mednafen's `GoGoGadget`/`CheckDMAStart`/`SCU_DoDMAEnd` path corroborates one-slot
external-event holding. Ymir's pinned `TriggerDMATransfer` excludes active channels
and does not corroborate that behavior; the documented MAME behavior was retained.
924 external-event scenarios pass; five explicit test-only mutations fail. No
production change was needed. Exact hardware event timing, DxGO MMIO and held-
state reset/save-load are not established by this test.

## AREF audit update

ST-097 figure 3.30 / table 3.24 (printed p.72, PDF p.88) defines AREF bits 4:0
but prints the older zero initial value. ST-210 item 33 (printed p.10, PDF p.14)
explicitly changes ARFEN to 1 on power-on reset. Corrected the device reset value
to 0x10 and masked stored writes to 0x1f. MiSTer/Mednafen corroborate the mask,
not the corrected reset; Ymir ignores AREF writes. The primary erratum takes
precedence. No dynamic refresh timing or hardware write-protection behavior was
inferred. Independent pre-fix reset and write controls fail; 32 resets, 32,768
AREF writes, 288 ASR writes and 24,576 existing static wait decodes pass.

## A-Bus interrupt mask audit update

ST-097 §3.5, printed p.57 / PDF p.73, explicitly defines IMS15 as a mask with
one blocking and zero allowing interrupts. Corrected the reversed external condition.
Table 2.1 (printed p.27 / PDF p.43) supplies the tested priorities/vectors; table
3.8 (printed p.59 / PDF p.75) defines status write clearing. Mednafen sign-extends
IMask bit 15 to mask external requests and corroborates polarity. Pinned Ymir uses
the opposite external condition despite a direct bit-15 field; it was not treated
as authoritative over the manual. 1,920 arbitration cases, 16 acknowledgement
sequences and 512 register writes pass; pre-fix arbitration fails. Actual CPU/CD
runtime and full external-acknowledgement bus behavior remain unvalidated.

## DMA programmed address width audit update

ST-097 §3.2, printed p.41 / PDF p.57, defines DxR/DxW bits 26:0 for every channel.
Removed incorrectly stored cache-alias bit 29 from both write masks. Ymir extracts
bits 0..26; Mednafen and MiSTer use 0x07ffffff. Direct count widths on the following
page remain unchanged. 15,360 address and 7,680 count writes/readbacks pass with
separate failing pre-fix source/destination controls. End-of-transfer address-update
wrapping, MMIO routing and CPU/cache runtime are outside this increment.

## DMA control-register audit update

ST-097 §3.2 printed pp.43/45/46 (PDF pp.59/61/62) supplies increment decoding,
enable/GO and mode/update/factor fields. Cross-checked with Ymir's WriteRegLong /
TriggerImmediateDMA and Mednafen's masked control writes. Existing handlers pass
13,824 new field/byte-lane/start-gate scenarios; no production correction warranted.
Four test-only mutations fail. Dispatch endpoints are recorders, so full MMIO-to-
transfer/IRQ integration, active-register restrictions and bus-specific increment
behavior remain outside this test.

## Build coverage update (no hardware behavior change)

Validation now compiles six core/driver translation units, adding Saturn console,
ST-V and DCC. Corrected emu.h include ordering in DCC/ST-V; pre-fix files fail with
otherwise complete shared/layout include paths. Layout headers are generated with
MAME's own tool in temporary storage. All thirteen scripts/six objects pass.
This is build evidence only, not additional primary-document or runtime validation.

## CD build coverage update (no hardware behavior change)

Routine object validation now includes CD HLE and the CD block wrapper, bringing
the total to eight. Corrected CD HLE's emu.h include order after reproducing the
header/incomplete-type errors; the CD block wrapper compiled unchanged. All
thirteen scripts/eight objects pass. No primary hardware interpretation or CD
runtime correctness claim follows from this build-only change.

## DMA forced-stop control implementation

ST-097 §3.2, printed p.47 / PDF p.63, defines DSTP bit 0 at $05fe0060. Previously
unmapped, it now cancels CPU-programmed DMA including waiting/held work, preserving
programmed registers and existing IRQs. Ymir/Mednafen corroborate three-channel
cancellation without completion IRQ; Mednafen's stop case remains marked untested.
2,321 standalone scenarios pass; a no-op control models the old missing mapping
and fails. Physical stop latency and actual game compatibility remain unestablished.

## Four-priority implementation evidence — 2026-09-14

- **SCU source buffering:** ST-097 §3.2, printed pp.41–43 (PDF pp.57–59),
  supplies source address and 0/4 increment controls. Pinned Ymir SCU `doRead`
  and Mednafen `DMA_Read` corroborate longword buffering/byte position. New
  source-buffer tests pass 1,152 scenarios; baseline e7cff8b8 fails. This is not
  verification of every alignment/count configuration or the separate CD path.
- **CD DataEnd/deletion:**
  [ST-162-062094](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-162-062094.pdf),
  CD Communication Interface, printed p.32/PDF p.20 requires DataEnd after an
  accepted transfer; printed p.81/PDF p.69 specifies stopping, dummy excess
  data and effective CD word counts; printed p.96/PDF p.84 specifies deleting
  the entire Get-and-Delete range even when not fetched. Printed p.97/PDF p.85
  says interrupted PUT retains designated sector count, with unspecified tail
  bytes. Pinned Ymir CD `EndTransfer` and Mednafen `COMMAND_END_DATAXFER` both
  deactivate transfers; they disagree on some deletion/dummy details, so the
  primary full-range rule governs. Existing idle value and deletion timing
  are retained, not claimed as hardware measurements. Partial GET count needs
  a prefetch model; zero-data error reporting is also not fixed in this pass.
- **SMPC:** ST-169-R1-072694 printed p.49/PDF p.59 resets IOSEL/EXLE;
  printed pp.50/52/58 (PDF pp.60/62/68) defines CONTINUE as reversing IREG0 bit7,
  BREAK termination, and prohibits simultaneous CONTINUE/BREAK. Mednafen's
  alternating `NextContBit` corroborates the toggle; Ymir's level-based check
  disagrees and was not copied. Ymir does corroborate clearing SF/canceling
  pending collection on BREAK. Neither current 700us delay nor VBlank timeout
  is validated by these tests.
- **HALT ownership:** this is host-emulator signal composition, not a new Sega
  timing claim. Both Saturn/ST-V wired SMPC and SCU directly to the same HALT
  lines; independent saved sources prevent one callback clearing the other.
  1,296 event sequences verify composition/reset with recording CPU endpoints.

PDF extraction correction: both ST-162 files have a malformed `/Encrypt null`
trailer, not actual encryption. Ignoring only that null entry lets pypdf extract
ST-162-062094 (91 pages) and ST-162-R1-092994 (53 pages). The latter is System
Library, not the CD Communication Interface. The earlier SDK extraction manifest
is historical and still records these two failures; six other failures have not
been retried. No downloaded SDK documents were added to Git.

All 17 scripts/nine objects pass. CD pointer/payload/directory/MPEG saves and ISO
parser bounds remain open; copied-state tests are not real MAME save/load proof.
See `game_blockers.md` for scope and the remaining runtime dependency blocker.

## VDP1 implementation pass — 2026-09-14

Fixed END-bit recognition, VRAM command wrap, completion-driven SCU IRQs (removed
periodic scanline IRQ workaround), 8-bit CPU framebuffer byte lanes, and outside
user clipping across fast/generic pixel writers. 32,775 command, 288 framebuffer
and 24,500 clipping cases pass; three independent baseline substitutions fail.
All 18 scripts/nine object builds pass. This is **not complete VDP1**: synchronous
drawing, ENDR, exact draw/erase/swap timing, BEF/pointer details, full framebuffer
formats, rasterization/texture/color edge cases and real save/load/runtime proof
remain. See `regtests/saturn/vdp1_completion.md` for evidence and acceptance gates.

## VDP1 sequencer and packed framebuffer implementation — 2026-09-14

Replaced whole-list synchronous dispatch with saved, timer-driven command
execution. Lists no longer stop at a host iteration cap; CPU edits to looping
lists are seen on subsequent fetches. ENDR cancels at command boundaries, reset
cancels pending work, and a new PTMR start restarts at command zero. COPR tracks
the fetched command; LOPR latches on framebuffer changes; read-only status
register writes are ignored. Legal jump/skip/CALL/RETURN controls are tested;
nested CALLs and main-routine RETURNs are prohibited by Sega, not legal features.

Packed 8-bit drawing now shares CPU-visible words with scanout and erase, with
neighbor-byte preservation and correct word stride for high-resolution and
rotation-8 storage. All five pixel writers use shared pixel accessors. Postload
rebuilds line pointers without resetting the restored drawing bank/geometry.

18 scripts/nine object compilations pass. VDP1 coverage is now 32,814 command/
lifecycle, 532 framebuffer and 24,500 clipping scenarios. Pre-sequencer and
pre-packed-rendering substitutions fail independently, as do the older baseline
controls. Timer/CPU/raster endpoints and copied state are not runtime proof.
Primitive rendering remains synchronous; the sequencer uses a 16-cycle fetch
allowance without pixel/bus costs. ENDR's ~30-clock pipeline behavior, interlace
fields, rotated VDP2 readout, texture end-code traversal and raster/color accuracy
remain open. See `regtests/saturn/vdp1_completion.md` for the updated audit.

### Primary sections and reference qualifications for the sequencer/packed pass

ST-013-R3-061694 §4.3 (printed p.45/PDF p.60) specifies PTMR=1 restarts drawing
from the top even while drawing. §4.5 (p.51/PDF p.66) specifies ENDR, no resume,
and approximately 30 clocks to terminate; this pass implements command-boundary
cancellation, **not** that pixel-pipeline latency. §§4.7–4.8 (pp.54–55/PDF69–70)
specify LOPR at framebuffer change and live COPR. The command jump table lists
all eight jump/skip controls; precautions pp.158–159/PDF173–174 prohibit nested
CALL and RETURN in the main routine. These prohibited cases remain distinct
from the valid sequencer paths, without claiming a primary-defined result.

§1.1 p.13/PDF28 defines low-eight-bit pixel writes; the framebuffer is two
2-Mbit banks, and §4.4/EWDR defines even-X/odd-X byte pairs. The packed tests
cover replace rendering, not prohibited 8-bit color calculations (§6.3).
Pinned Ymir `VDP1ProcessCommand` uses 16-cycle command fetches and persistent
command/return addresses. Its software renderer `VDP1PlotPixel` stores byte dots
for 8-bit mode and derives byte offsets from framebuffer width. This supports
the layout change, not a complete hardware timing claim. Ymir also has an ENDR
30-cycle TODO and a game-dependent start-delay workaround; neither was imported.
The mere presence of a feature in a reference emulator is not proof of all its
edge cases. No unreviewed source or title-specific delay was copied.

## VDP1 rendering/status audit — 2026-09-14

Implemented destination-preserving MON, coordinate-based Gouraud evaluation
(which does not stall on skipped mesh/transparent/clipped dots), explicit
component-wise color calculations, bounded color-lookup fetches, and two-end-code
row termination in the production normal-sprite loop. BEF now latches on an actual
framebuffer change rather than every VBlank in manual mode. This does not complete
scaled/distorted texture traversal, interlace, rotated scanout or pixel timing.

Tests pass: 92,420 color/shading cases, 2,689 normal-texture/boundary cases,
32,816 command/lifecycle cases, 532 framebuffer cases and 24,500 clipping cases.
Four independent render mutations (MON source replacement, dropped odd carry,
fixed Gouraud coordinate, disabled second-END termination) fail their assertions.
All 18 scripts/nine objects pass. Shader tests do not establish polygon edge or
interpolation precision on silicon; callbacks use recording timer/CPU endpoints.
Full chip completion and BIOS/game/runtime/save-manager proof are not claimed.

### Rendering evidence and disagreements

Primary ST-013-R3-061694 §6.3 printed pp.86–87/PDF101–102 defines the second
horizontal source end code and independence from SPD. The normal-sprite tests
cover all six documented texture formats, four read directions, ECD/SPD and
pairs of end positions on two rows. They do not cover scaled/distorted sampling
or pre-clipping inversion. Lookup address wrap includes a deliberately unaligned
(outside Sega's legal alignment requirements) table as a memory-boundary test,
not evidence of a supported guest configuration.

§6.3 pp.94–97/PDF109–112 defines replace/shadow/half-luminance/half-transparency,
Gouraud saturation before combination, and MON modifying the existing framebuffer.
The arithmetic tests include exhaustive component pairs, both MSBs and legal
operation selectors. MSB-clear RGB arithmetic cases test the chosen model, not a
hardware guarantee where Sega says results cannot be guaranteed.

Pinned Ymir `VDP1PlotPixel` and Mednafen `PlotPixel` support destination-preserving
MON and average-then-truncate blending. Ymir's line traversal also advances Gouraud
through suppressed dots and counts end codes on newly fetched texels. Pinned
MiSTer `VDP1.sv` selects the background for MON and ORs the top framebuffer bit;
`VDP1_pkg.sv` confirms saturation and component operations. **MiSTer's ColorCalc
halves each operand before addition, unlike the Ymir/Mednafen odd+odd result.**
This implementation follows the manual's average wording and Ymir/Mednafen, not
an assertion that all three references agree. 8-bit MON word-alignment is still
reference-modeled and not independently hardware-verified.

BEF's bank-change latch is supported by §4.6 printed p.53/PDF68 and Ymir's
`VDP1SwapFramebuffer`; main-list start still clears CEF without overwriting BEF.
The manual's start-of-drawing wording needs hardware qualification; no complete
frame timing claim follows from correcting the unconditional VBlank overwrite.

The version supplement ST-013-SP1-052794 was also read (14 PDF pages); it describes
version-0 versus version-1 EOS/HSS/pre-clipping differences, not missing rounding
or pipeline timing details. No source code was imported from any reference.

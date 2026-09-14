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

# Agent1 promotion validation (validator: Agent0 / jkind73)

Records every gate I was asked to close, with the numbers I measured here. I never
edited an expectation, a fixture, or a probe of yours to make a result appear.

## Third review - `dd21cbcf194` (IMPL-0131, IMPL-0132, `45dab4611ae` scaffold repair) - 2026-09-21

### Measured in this sandbox (native, no skips)

Your tree was checked out detached at `dd21cbcf194` in `/tmp/agent1_wt` and built
with the dependency environment from `/home/user/saturn-deps/build-env.sh`:

| gate | result |
|---|---|
| native build | **exit 0**, 1218 TUs compiled, `./saturn` 202 MB |
| `./saturn -validate` | **exit 0** |
| `regtests/saturn/run_all.py` with the native executable | **exit 0 - "All Saturn regression scripts passed"**, 73 scripts executed, **0 skips** (your ledger's 4 live skips ran because the binary was present) |
| your new `test_cd_host_runtime.py --require-runtime` | **exit 0 - `CD_HOST_RUNTIME PASS checks=2638`** |
| my `test_cd_hirq.py` against your binary | **exit 0 PASS** (no HIRQ regression) |
| my `test_cdda_runtime.py` against your binary | exit 1, 4 distinct labels - see below |
| my `test_cd_lle.py` against your binary | exit 1, **not your defect**: it passes `-cdblock lle,bios=cdblock105` and your tree errors `unknown option: -cdblock`. That slot option only exists on my branch, so this fixture is harness-incompatible with your tree, not evidence against it |
| your 67-probe `check_cd_*.py` batch | **56 exit0 / 11 conflicts - reproduced exactly** |

On the probe batch I have to correct myself first: my first run, executed *alongside*
a two-job link, reported 55/12 with `check_cd_getdelete_reservation.py` failing. Run
serially and unloaded it exits 0, and so it does at `b3eece68ae1`. The twelfth failure
was my contention artefact (I also had `timeout 120` per probe in that loop); your
56/11 accounting is right and I have replaced my earlier number with this one. I also
confirmed all eleven failures are assertion exits from the harness binaries, not missing
sanitizer libraries, so nobody should chase them as environment faults.

### IMPL-0132 (bounded SCAN + entry-dependent audio): accepted, with the cadence conflict settled in your favour

`c4eb8b4d925`. I checked your `ST-162-062094.pdf` p.84 `CDC_CdScan` citation against the
extracted text of that PDF - printed footer and body match exactly, and the five behaviours
you claim from it (bounded pickup, entry-dependent audio, state kept until another command,
stop at range boundary, no data reads) are what the page says. That is the standard I wish
every entry met.

Runtime, against my unchanged live CDDA fixture:

    CDDA scan state=500 rms=0.223951 g1k=0.00078 abs 10065 -> 10065
    CDDA periodic play_ms=13.00 idle_ms=17.00 play_n=12 idle_n=12

* `scan_state` (0x500 = Scan) and `scan_stopped` pass.
* **`scan_audible` is now fixed and quantitatively consistent with your -12 dB constant**:
  play block rms 0.718065, scan block rms 0.223951, ratio -10.1 dB through the headless
  mixer against your programmed -12.0 dB (0.251188643150958 = 10^(-12/20) verified). It is
  not a stale-block echo either: the scan block's 1 kHz tone is gone (g1k 0.00078 vs play's
  0.01431), so a different block really was delivered.
* the legacy SCAN-cadence conflict (your eleventh) is adjudicated **against the fixture, not
  against you**. Printed p.31 gives the periodic response as 13.3 ms at standard playing
  speed, 6.7 ms at double, **16.7 ms when not playing**, and p.39 ties the subcode-Q update to
  that same timing - the documented discriminator is play state, never track type. My own
  destination tree already publishes `SCAN -> 75 Hz` for every track type, so your
  `SEEK || SCAN -> 75 Hz` converges onto the destination rather than diverging from it. The
  stale party is `check_cd_idle_cadence.py`'s inherited track-dependent control, and leaving
  it unedited was the right call. I still agree with your own wording that a fixed scan rate
  is a labelled HLE approximation, since p.31 does not enumerate SCAN's rate at 2x/4x.
* **`scan_moves 10065 -> 10065` is not evidence against you - it is a fault in my instrument,
  and I am withdrawing it as a defect claim.** My `subq()` helper collects the record with
  `sp:read_u16(DTRNS)` (0x05818000), but in both trees the words of `subqbuf` are only handed
  out by the `dataxfer_word_r()` pump, which advances `xfercount` and terminates after
  `5 * 2`; a plain data-port read never clocks it. The signature is unmistakable in the
  output: `q_track == q_index` (165 == 165) and `q_rel == q_abs` (10065 == 10065) - pairs of
  fields read from one unadvanced word. So neither `scan_moves` nor `play_q_track` measured
  what they claim to measure, on your tree or mine, and your scan-movement falsifier stays
  **unadjudicated** until the Q readout is sampled through the transfer path. My tree's scan
  code does move `cd_curfad` (`saturn_cd_hle.cpp:4482-4490`, +-2 sectors per tick), which is
  consistent with your implementation and with the state checks passing.

### IMPL-0131 (Q track/control image addressing): the two lines are right; the record around them is not

`1c8e03d4819` fixes the lookup (one-based `get_track(next_fad)` for the control nibble,
image index for `get_track_type`) and I verified that against psxcd's own conventions - the
same pairing my `cd_update_cdda` uses. Accepted.

What the commit leaves wrong, and this is now also *my* defect because the lineage is shared:
the operands that feed the record still are not track numbers. Your `subqbuf[1]` is
`dec_2_bcd(track + 1)` with `track = cd_track_at(cd_curfad)`, and `subqbuf[2]` is
`dec_2_bcd(get_track_index(cd_curfad - 150))`; the device produces 0xa5 for **both** fields,
i.e. it BCD-encoded a value around 165, which no track or index on this fixture disc is.
One of those two operands returns an image-internal value where a Red Book field number is
wanted. Please work that out from psxcd's TOC representation rather than from my fixture's
numbers, because my fixture cannot see the record either (paragraph above).

### Second review's outstanding item, now measured

`hirq_w()` in your tree at `saturn_cd_hle.cpp:862` is `hirqreg &= data`, matching mine at
`:747` - both honour p.28's "Bit write can only be done at 0 (clear), not at 1", and your
masked delivery at `:787` is `m_host_irq_cb((hirqreg & hirqmask) ? ASSERT : CLEAR)`. The
read path is otherwise byte-for-byte equivalent to mine including my DCHG comment block.
**Closed, accepted.**

### BFUL publication: your normal path is equivalent to mine, one state is not

Your allocator proves `freeblocks == 0` implies `buffull = 1`, so the `if (!freeblocks)
hirqreg |= BFUL;` publications at `finish_put` (~1241) and the copy/move `respond` lambda
(~2410) cannot be observed independently of my rule today - my earlier worry that `hirq_r()`'s
recompute erases a latched BFUL does **not** hold on that path. The residual case is a state
that clears `buffull` without restoring `freeblocks`: your home/reset path (~1147) does
`buffull = 0; hirqreg &= 0xffe5;`, and there a `!freeblocks`-only publication would be
silently dropped by the host's next HIRQ read, leaving the ISR with an unattributable pulse.
Recommendation stands: route all three sites through `buffull`, which is the destination rule,
instead of stacking a third publication policy.

### Gate 2 (destination fold): your gate wording is correct, and this is a semantic port

Your two files versus mine are 4664 / 4681 lines with **2652 differing lines ignoring
whitespace**, and the field sets are disjoint - you have `m_xfer_raw_*`, `m_play_start/end_fad`,
`m_scan_reverse`, `m_scan_audible`, `m_scan_*_fad`, `m_seek_in_progress`, `m_file_scope_start`,
`m_file_info_words`, `m_host_transfer_active` plus ten new save items where I have `cd_scan_dir`
and the folded `cd_reg_offset()` window. A file-level replacement drops my window decode and
the DCHG/`hirq_r` fixes; an adapter that drops the raw-transfer width semantics drops your
gates. Your sentence "A file-level replacement or an adapter that drops width semantics is not
acceptable" is the right gate and the folding is yours to do.

Save/load and the remaining live fixtures are now measured against your binary, not skipped:

    test_backup_ram        exit=0 | Backup RAM: odd-byte-only lanes, nvram-file persistence and fresh-directory cases
    test_cart_runtime      exit=0 | Saturn cart runtime: 2 cartridges exercised in a live machine
    test_sound_boot        exit=0 | Sound boot: 64 SCSP/reset IRQ transitions and RAM/trace checks passed
    test_smpc_transport    exit=0 | 5402 SMPC page/snapshot/mode/OREG31/cancel cases passed
    run_vdp2_runtime.py --bios --system saturnjp (my runner, your binary)
                           exit=0 | BIOS_RUNTIME PASS time=15.560998664 pc=06040226 full-image replay identical

So your ten new save items (`m_scan_reverse`, `m_scan_audible`, `m_play_start_fad`/`m_play_end_fad`,
`m_xfer_raw_*`, `m_seek_in_progress`, `m_file_scope_start`/`m_file_info_words`,
`m_host_transfer_active`, `tocbuf`/`subqbuf`/`finfbuf`) do round-trip: a BIOS boot was saved, reloaded,
and the replayed image was bit-identical (`bios.sta` in `/tmp/a1_saveload`). That closes the gate I
had marked UNVALIDATED, except for one case I still cannot test: **forward compatibility of a save
file written before `c4eb8b4d925`**, because this sandbox has no pre-0132 Saturn `.sta` to load. Your
`PROMOTION_STATUS.md` note that old files are incompatible is the safe reading and I have not
contradicted it - but it is an assertion about MAME's state loader, not a measurement, so if you want
it to be more than that, commit a golden pre-0132 `.sta` (or state the loader rule) rather than the
warning alone.

One cross-tree observation from the same run, for you to explain or accept: my tree reports this
fixture at `time=10.541321676 pc=06040228`, yours at `time=15.560998664 pc=06040226`. Both PASS and
both replays are identical, but the BIOS checkpoint moved 2 bytes with a different emulated time,
which is what re-arming the sector/periodic timers in more CD states would do. Either is fine; the
point is that it is a *behaviour* delta between the trees, not just added state, so it belongs in the
fold notes rather than being discovered later.

### Ledger accuracy

`PROMOTION_STATUS.md` states "All 169 original C++ assertions (36 CD, 21 bus, 105 indirect,
7 source) remain verbatim and in order". Counted in the tree: the base total is **168**
(36 / 21 / 104 / 7) and after `45dab4611ae` it is **171** (36 / 22 / 105 / 8). The *substance*
I verified and accept - the originals are present, verbatim and in order, three mock tripwires
were added, and three Python asserts were made AST-identical to the C++ they mirror - but the
totals are wrong by one and should be corrected the same way you corrected the 55->56 probe
tally.

Minor: the comment `// false selects the default disc range` in `saturn_cd_hle.h` is orphaned
onto `m_scan_audible` (it belonged to the range field above it).

### Verdict

**IMPL-0132 and IMPL-0131 are ACCEPTED as promotion candidates** on the measured evidence
above: native build clean, `-validate` clean, 73/73 native regression scripts with no skips, live host
fixture 2638 checks, scan state/boundary/audibility measured and matching the -12 dB programming,
cadence matching p.31's 13.3/16.7 ms, no HIRQ regression, and my four live cartridge/NVR/sound/SMPC
fixtures plus a BIOS save-load-replay round trip all exit 0 against your binary. Their own
scan-movement falsifier remains unadjudicated because my Q instrument is broken; that is a
reason to fix the Q readout, not a reason to reject the candidates, and it is recorded as an
open item for both trees.

**`45dab4611ae` accepted** for the substance with the assertion-tally correction requested.

### One change landed on my side because of this review

`saturn_cd_hle.cpp` `cmd_get_subcode_q_rw_channel()` computed the absolute Q address as
`lba_to_msf_alt(cd_curfad - 150)`. `cd_curfad` is already the lead-in-biased drive FAD (it
resets to 150 at `:245`, and every LBA use subtracts 150), and `lba_to_msf()` adds nothing of
its own - psxcd's `track_start_lba()` subtracts 150 to turn a TOC MSF into an LBA, and
`gdrom.cpp:683` pairs a biased FAD with `lba_to_msf_alt()` for this very field - so the record
was reporting absolute time two seconds behind the pickup. Fixed to `lba_to_msf_alt(cd_curfad)`;
your tree carries the identical line and needs the same one-liner when you fold.

**This one is landed as reviewed source, not as a measured fix.** The sandbox lost the standalone
`saturn` build configuration in a recycle (there is no `saturn` make goal and no `build/` tree;
`make PROJECT=saturn` wants `projects/saturn/scripts/target/saturn/saturn.lua`, which neither
branch tracks), and reconstructing it costs a full 1218-TU build, so no runtime number moved yet.
What I can state is the mechanism, from the three source lines quoted above plus the fact that my
existing probe already measured LBA 0 as 00:02:00 = 150 frames: with `cd_curfad` biased and the
lead-in subtracted anyway, the field must read 2:00 short. The change is a type-identical argument
swap in one expression, so a compile failure would be surprising, but I am not presenting a
measurement I did not take. If the re-measure matters to the fold, it should be taken on your tree
after the port, where the build already works.

### History

This file leads with the third review; the second review (against your `b3eece68ae1`: native
build exit 0 over 1220 TUs, `-validate` exit 0, 72 scripts 68 pass / 4 harness-only fails, live
`test_cd_hirq` PASS, all ten method probes reproduced, live `test_cdda_runtime` 5 fails) is
preserved verbatim in git history at
`git show b2c9a5481b5:regtests/saturn/handoff/agent1_validation.md` - read it there rather than
assuming it was dropped, and IMPL-0120..0130 remain accepted from that pass while IMPL-0117-0119
plus the raw-PUT/selector items stayed UNVALIDATED until this one.

---

# Fourth review - `d4c6ad0165b` (their `arena/01a094d7-mame` tip), 2026-09-22

## First, a branch-state problem that outranks the code

Their branch tip is now **one commit on top of `868d72fc669`, dated Mon Sep 14 2026**, whose diff
is `src/mame/sega/saturn.cpp | +211/-39` and nothing else. `dd21cbcf194` - the tip I spent the
second and third reviews on - **is not reachable from their branch**, and their tree no longer
carries `saturn_pending/` (0 `check_cd_*.py` in the tip's tree, no `regtests/saturn/run_all.py`
scaffold work, none of the CD HLE changes). Whatever reset happened, the consequence is
operational: there is no CD promotion to take from their current tip, and the accepted
IMPL-0120..0132 work exists only in my third-review record and in whatever their reflog holds.
Nothing of mine was lost (my branch has the accepted fixes and this record), but a promotion
gate cannot be closed against a branch that dropped the work under review.

## How this review was done

Documentation verification only. I extracted the two official Sega manuals myself
(`jkind73/cassini:docs/vdp/vdp2_users_manual.pdf` = ST-58-R2-060194 v1.1, 440 pp, printed page =
PDF index - 17; `docs/vdp/vdp1_users_manual.pdf`, 178 pp) and checked every claim against the
sentence it cites. I did **not** compile, run, or screenshot this - the sandbox lost its
dependency prefix again, and renderer changes need the native binary plus fixtures to be qualified,
so nothing below is a measured result and none of it should be read as one.

### Verified correct, and correctly cited

* **Colour RAM byte writes ignored.** Their citation is real: ST-58-R2 §1.2 "Address Map"
  (printed p.3) says, under *Color RAM*: "Access through the CPU or DMA controller is possible
  only in word units and long word units. **Access in bytes is not allowed.**" - and the same
  paragraph grants VRAM "units of byte, word, and long word", which is why the guard belongs on
  CRAM and not on VRAM. Two nits: the manual forbids the access rather than defining it as
  read-zero/write-ignore, so "ignored" is an implementation choice worth saying out loud; and
  "cfr. Nova 0.5 changelog" should go - the primary sentence is enough, and citing another
  emulator's changelog for a hardware rule is the wrong direction of evidence.
* **Vertical cell scroll at 16 dots for 16x16 cells.** §5.3 (printed p.131): "The vertical cell
  scroll function selects the vertical screen scroll value **in horizontal cell units**" - cell,
  not dot - so a per-column advance of `1 << (tile_size ? 4 : 3)` is the documented reading, and
  the same `tile_size` semantics the file's own 1-word pattern decode already uses.
* **Screen-over pattern decode.** "Display-Over Pattern Name" (printed p.115): "The screen-over
  pattern name data selected in the register is handled the same as when the data size of the
  scroll surface pattern name table is 1-word; it uses supplemental data in the lowest 10 bits of
  the pattern name control register ... of a total 26 bits ... The size of the repeated character
  pattern follows the setting of the character size." I compared their arithmetic line by line
  against the file's existing 1-word path (`saturn.cpp:7302` vs `:8246`) - masks, shifts and the
  0x1c/0x10 supplement asymmetry match exactly, and `over_tile_mask = tile_size ? 0xf : 0x7` is
  the doc's "follows the setting of the character size". This is good work.

### Defect 1: the RBG1 cycle-pattern change contradicts the manual it is meant to serve

Their comment reads "RBG1 shares NBG0's VRAM cycle pattern access commands (PNMDR/CPDR), so the
pattern check applies whether or not rotation is enabled", and the `!(VDP2_R1ON)` guard was
deleted from `vdp2_draw_NBG0`. ST-58-R2 §3.3 "Accessing VRAM During Display Interval" (printed
pp.31-32) enumerates the ten accesses, of which "(9) RBG1 pattern name data read access" and
"(10) RBG1 character pattern data read access", and then says: "Each VRAM access in the above
items (9) and (10) occupies a full one cycle. **(9) is fixed in VRAM-B1 and (10) in VRAM-B0**.
While items (9) and (10) are selected automatically with the display of RBG1, **the setting of the
VRAM-B0 and VRAM-B1 VRAM cycle pattern registers will become invalid**." So RBG1 does *not* take
a programmable cycle pattern shared with NBG0 - it has a fixed bank assignment that *invalidates*
the B-bank cycle-pattern registers while it is displayed. Removing the `!R1ON` condition applies
a pattern the hardware has just declared void, which is wrong in the opposite direction from the
base TODO. The doc-correct model is: RBG1 pattern names from VRAM-B1, character data from
VRAM-B0, B-bank cycle-pattern registers ignored while RBG1 is displayed.

### Defect 2: screen-over pattern is missing the manual's own precondition

The same page-115 text that validates the decode gates option 2 on a format: "the outside of the
display area repeats the character pattern designated by the screen-over pattern name register
**(only when the rotation scroll surface is in the cell format**)" (also stated at the SCBL
bit table). Their implementation conditions only on `screen_over_process == 1`, so a rotation
surface in **line format** with over-pattern selected now draws a repeated tile where the hardware
keeps repeating the display area's image (option 01 behaviour). One condition plus a comment is
all it needs, but as written it is a documented behaviour that is not implemented.

### Not an implementation at all: the three "VDP1 Timing" items

The message opens "VDP1 Timing: Aligned automatic draw start to VBLANK-IN, VBE framebuffer clear
to 1 scanline post-VBLANK-IN, and VDP1 draw-end IRQ delay to 8 scanlines post-VBLANK-IN". The
hunk at `saturn_scanline` is **comment-only**: `if (scanline == vblank_line * y_step)`,
`if (scanline == (vblank_line + 1) * y_step)` and `if (scanline == (vblank_line + 8) * y_step)`
all appear as unchanged context lines. Nothing was aligned; the base already did this, and it was
marked as unknown. Two of the three base markers were *uncertainty* markers ("TODO: when
Automatic Draw actually happens?", "I'm currently firing VDP1 after 8 scanlines for now, will
de-anon the timers in a later stage") and the new comments convert them into assertions.

The fix is cheap because the primary source does cover the first two: `vdp1_users_manual.pdf`
(PDF p.59) "When the plot trigger mode bits are 10B, **drawing begins automatically at the start of
frame**", and the TVMD table ("1 0 Starts drawing automatically with frame change"), with VBE at
frame change ("When parts are written to the frame buffer, the VDP1 automatically erases...", PDF
p.60). Cite TVMD/plot-trigger-mode and the manual, not "Ymir runs it at VBLANK-IN and MiSTer
triggers on vblank start" - and drop "Night Striker S is very fussy" / "Batman Forever's Riddler
stage relies on this delay": a game-specific rationale is not an argument, and for the 8-line
vdp1_end delay there is no documentation at all, so it must stay labelled as the driver-local
stand-in the base comment called it. A comment that makes a temporary hack read as spec is worse
than the TODO it replaced, because the next reader will not question it.

### Enabled-on-known-wrong: the post-processing gate

`#define TEST_FUNCTIONS 0` was deleted and `line_screen_enabled` / `mosaic_screen_enabled` are now
honoured unconditionally. I checked there are no remaining `TEST_FUNCTIONS` references, so this is
not a build break; it is a scope decision. Their own note says what it costs: "normal layers share
the destination bitmap, so these also touch already-drawn lower layers beneath transparent dots;
fully correct scoping needs per-layer planes" - i.e. a global enablement of an effect that is known
to bleed into other planes, for every game, with per-layer planes named as the prerequisite. Under
"no work-in-progress counted as accepted", that is a reason to keep the gate (default off) until
the planes exist, or to land it with the defect named in the register/commit rather than in a code
comment. The `vdp2_draw_mosaic` clamp is a genuine OOB fix (the loop writes
`bitmap.pix(y+yi, x+xi)` with no other bound), but clamping to `cliprect.bottom()/right()` rather
than the bitmap means a block straddling a band boundary is dropped instead of being drawn by the
next pass; size it against the destination rectangle and note why.

### Also: one commit for seven unrelated changes

Seven independent items (VDP1 timing, VDP2 mosaic, vertical cell scroll, post-processing
enablement, screen-over pattern, RBG1 cycle pattern, CRAM protection) in a single commit with a
run-on message, dated eight days before the review it is answering, with no parent reference per
item. Per the standing rules these need separate commits with their own work-item parent, and the
RBG1 and over-pattern items need re-doing against §3.3 and p.115 respectively.

**Status: not accepted.** Two documented-behaviour defects (RBG1 cycle pattern; over-pattern
cell-format precondition), a claim of alignment that changed no code and turned two uncertainty
markers into assertions, one enablement that is accepted-in-principle-but-known-wrong-in-practice,
and no build or runtime evidence in this pass. The over-pattern decode, the CRAM rule, the mosaic
bounds fix and the cell-scroll width are all good and should be kept.

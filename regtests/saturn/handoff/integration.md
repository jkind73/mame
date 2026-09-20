# Current integration qualification — 2026-09-17

GitHub access is restored. Source 2781f96b built in CI 35299792272 and passes the
full device-aligned native consumer, including timeout and actual H/V edge save
restoration (IST=4), on the verified binary SHA256
`4a151988ca60d0c16d9f3c3fc4505cf2d72b7e54a869b9b7fca7d60bfddf9ac5`.

New production WIP: VBlank-sampled, saved RESB independent of NMI enable;
explicit physical-slot payload addressing through SMPC/controller/tap endpoints;
empty ports return F0 status/FF ID. Five full TUs pass C++20 syntax. Focused
RESB 6,144, physical-topology/mode 9,216, transport 5,402, handshake 1,175 and
timeout 73,728 + four edge checks pass. Native positives for this new source
are pending. Three-VINT NMI debounce, wire timing, extended IDs and wider
software/game/concurrent-transfer acceptance remain open. No working flags changed.

The earlier sections below are historical implementation checkpoints; current
acceptance is maintained in `saturn_pending/README.md` and the parent checklist.

---

# Single-agent integration status

## Reviewed cartridge/CD changes — WIP, 2026-09-17

Baseline: `4edfe4bc` (production unchanged from `125e3048`). Adapted from the
user-supplied `01a0ac86-f1f7-74c0-81dd-287e6f103c11 (1).patch`, SHA-256
`351216925207e399591f162b14c0c138e5ce9559e9988a3dbee5714b9a352567`.
The `(2)` patch is identical and was not applied. Original source license and
copyright headers are retained.

Production changes: guard empty cartridge DRAM allocations before modulo/index
access, retain existing allocated DRAM aliasing, replace cartridge boundary UI
popups with logging, check backup-RAM write counts, and preserve CD HIRQ DCHG
until acknowledgement instead of discarding it on read.

Primary CD basis: Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`,
ST-136-R2-093094, printed p.50 / PDF p.58, section 6: software detects a tray-open
condition through HIRQREQ DCHG bit 5. PDF blob:
`7e6f189f4d34cf1d79cd58e61a190e621042e5ed`. This passage was read during the
preceding review. DRAM aliasing and out-of-range bus values remain modeling
policies, not new hardware measurements.

Fresh checks for this WIP:
- 262,144 extracted HIRQ status-overlay/read/ack cases pass. Restoring the old
  DCHG-clearing read compiles and fails its assertion.
- Existing 336 extracted CD transfer cases and boot-trace tests pass.
- 24 extracted cartridge cases pass; the original empty-allocation handler
  compiles and is rejected by the sanitizer with a division-by-zero/FPE.
- 44 existing and 12 added fake-executable runner protocol cases pass.
- Python syntax and `git diff --check` pass.

The imported live CD/cart runners now reject nonzero exits, FAIL/Lua-error output
and malformed PASS markers, and use the actual `saturn` subtarget with absolute
paths. Their fake-executable tests are NOT live MAME/device acceptance.

**Pending:** full regression batch, native linked build, old/new binary tray
negative control, actual cartridge execution, BIOS/gameplay and save/load replay.
Earlier background builds and external logs did not survive workspace recovery;
no completed baseline boot or new linked result is claimed. This is a pushed
implementation WIP, not a validated release. CART-01 and CD-01 remain open.

IOGA, the incremental video patch, Agent1 CPU/bus changes and working/save-flag
promotion are excluded. A separately reviewed IOGA follow-up must discard local
receive-valid state on reset before that patch can be considered for integration.

Reproduce the remaining integrated checks with:

```sh
LOG_DIR=/home/user/saturn-validation bash regtests/saturn/validate_integration.sh
```

The checked-in runner builds with one compiler job, requires the supplied BIOS
files, rejects silent CD/cart skips, records source/binary provenance, and runs
JP DRC/interpreter, PAL DRC and ST-V DRC BIOS/background save-replay checks. It
never edits sources, commits, pushes or changes driver flags. A failed or missing
`status.txt` PASS is not acceptance. SDKs, binaries and large logs stay external;
source and the reproducible command are pushed before starting the long run.


Additional CD-01/NVR-01 implementation WIP:

- Debugger/inspection HIRQ reads now expose the live overlay without modifying
  stored HIRQ or invoking the IRQ-update callback. Real CPU reads retain their
  existing behavior. The extended 262,144-row extracted matrix includes two
  debugger reads, no-mutation/IRQ checks, CPU reads and acknowledgements. It
  fails against the preceding implementation and passes with the guard.
- Console internal backup RAM is explicitly registered with the save manager.
  `nvram_device::set_base` only handles file persistence; it does not register
  the allocation for save states. Existing cartridge allocations already do
  register their memory in `sat_slot.cpp`. This change does not alter file
  formats, hardware address decoding or ST-V's separate board configuration.
- The supplied backup-RAM fixture is extended with real save/mutate/load,
  notifier checks, and a following process checking that restored bytes persist
  at shutdown. All six runner modes use isolated temporary NVRAM directories.
  Its Python syntax and failure protocol are checked; actual save/load is
  **pending the linked build**, not reported as passed.
- The candidate console translation unit passed `-fsyntax-only` with narrowing
  errors enabled; 44 existing plus 18 CD/cart/backup runner protocol controls
  pass. These are not hardware tests. Full current-revision acceptance remains
  pending and neither CD-01 nor NVR-01 is closed.

The validation script now compares build/test input trees and BIOS checksums,
retaining its starting commit and binary hash. Checkpoint-only commits outside
those inputs do not relabel or invalidate the measured binary. Source/test/build
input changes still invalidate the result. Resume the single-job incremental
build after this implementation checkpoint; do not infer success from an earlier
interrupted build.


## Integrated IOGA and SCSP follow-ups after workspace restoration

The workspace was restored to `868d72fc` with the older mixed local patchset;
remote `1a23cf6c` was intact. The restored tracked diff and non-ROM untracked
files were archived locally before recovering the pushed branch. No unrelated
restored changes were imported. The earlier native build and its logs were
lost: **there is no linked result for that run**.

The previously reviewed `saturn_pending` IOGA and SCSP patches are now applied.
Their tests were rerun on production paths: 5,124 legacy IOGA cases; 49,152
ideal-clock plus 49,152 actual-attotime SCSP phase cases; 24 SCSP reset cases;
262,144 CD HIRQ cases, 336 CD transfer cases and boot-trace checks; 44+18 runner
protocol controls. All pass. Three SCSP mutations compile then assertion-fail.
SCSP and ST-V translation units pass C++20 syntax checking. These are extracted,
syntax and protocol results, **not linked device or gameplay acceptance**.

The SCSP fix registers timer origins for saving, preserves restored fractional
ticks, and schedules interrupts from tick origins using consistent attotime
quantization. It does not change reload policy, sound-reset wiring or working
flags. The legacy IOGA change only guards inspection cursor advancement.
Detailed scope and the unresolved primary-reference timing discrepancy remain
in `saturn_pending/README.md`. Start a new gated native validation against this
integrated revision; no result is inherited from the lost build.


## Integrated SMPC transport and VBlank boundary follow-up

- Source `234c7abc`: native build/configuration/ROM-free checks and the complete
  live consumer passed. Six mapped two-multitap packets and a scheduled partial
  packet save/mutate/load passed with unchanged source/binary provenance.
- `smpc_hle_device::vblank_in()` is now wired to the driver's rising VDP2 edge.
  It cancels pending initial peripheral completion and CONTINUE, clears PDL/NPE
  and saved packet cursor/size, and leaves unrelated commands and the legacy
  no-controller/ST-V path alone. The callback emits no new report or IRQ.
- The driver's previous H/V edge levels are explicitly initialized, reset, and
  save-registered. Live inspection confirmed these registrations were absent
  in the 5008 baseline. Real edge-history restoration still needs qualification.
- Four live negative expiry cases were reproduced on the transport-fixed 234c
  binary before integrating timeout. 73,728 extracted combinations, four edge/
  ordering cases, eight rejected compiled mutants, and full-TU syntax checks
  support the new code but are not native timeout acceptance. The new binary
  must pass `saturn_pending/test_smpc_timeout_runtime.py` plus the other gates.
- Baseline `5008a923` now passes all four 1,042-case composition configurations
  (4,168 total). That result is not attributed to a newly compiled revision.
- Artifact transfer is available through the checksum-verified temporary GitHub
  API blob exported alongside an unpublished draft release. No firmware,
  sandbox token, or binary source-tree commit is involved. Native receipts and
  text logs are under `saturn_pending/`; no working flags are promoted.

## Qualified SCSP microprogram and address contract

Source66e351f7 executes all128 steps and adds sign-extended twelve-bit ADRS_REG
only with ADREB, before TABLE/ring masking and RBP. Simultaneous ADRL affects
the next instruction, not the current address.69632 new method cases plus6531
previous cases/stopped control, nine compiled mutants,70-script local/CI and
build35391990957/export35393028889 pass. Complete native consumer passes988
programs/four profiles and actual effect/late-read/signed-address file replay,
including the first sample before the address latch can refresh. Evidence and
precise source pins: `saturn_pending/evidence/scsp-dsp-address/README.md` and
`../66e351f7-live/`. Consumer revision is separate from compiled source.
No change to IWT forwarding, memory arbitration, write flushing, whole sound
timing, game-performance acceptance or working flags is implied.

## CD block host interface reached the firmware — contract and receipts (b68f89e7)

The console's CD block window at `0x05800000-0x0589ffff` was dead from the
moment the HLE drive model moved behind `saturn_cdblock_interface`: MAME hands a
16-bit handler the address as a 16-bit **word index** in the SH-2's 32-bit
space, so `0x05890018` (CR1) arrives as `0x04800c`, while both implementations
decode byte offsets. Every BIOS command write landed on no register and its
response poll read zero forever.

Contract now published in the source and honoured by both cores:

- `sat_console_state::cd_reg_offset()` folds word index to byte offset, folds
  the register block's address-bit aliases (`+0x80000`, `+0x90000`, `+0x98000`)
  and maps the bottom of the window to the data-port alias, so the
  implementations only decode register-block offsets: `0x00/0x02` DATA,
  `0x08` HIRQ, `0x0c` HIRQMASK, `0x10..0x16` SH-1 side RR/CR, `0x18..0x24`
  CR1-4 (host write) / DR1-4 (host read), `0x28` MPEG express, `0x5029` the
  NetLink status byte (HLE only, the byte `dragndrm` reads).
- The CD block SH-1 side has the same word-index convention: `ygr_r`/`ygr_w`
  decode `(offset & 0x0f) << 1`. The previous `offset & 0x1e` shifted the whole
  YGR register file by one register (CDMSKL landed in CDIRQL, CR1 in CDMSKL).
- The slot option carries the block's 20 MHz clock
  (`option_add("lle", SATURN_CDB).clock(20'000'000)`): a slot option's clock
  defaults to zero, which leaves the CPU with no cycles (`clocks_to_attotime`
  returns `attotime::never`).
- The SH7032's 4KB on-chip RAM is at the masked address `0x07000000`; the
  firmware's stack (`SP = 0x0F000FFC`) folds there. The boot path's
  `/COMSYNC` pin is PB10 (`0x05FFFFC2` bit 2), the pause path's is PB2; both are
  driven from `device_reset_after_children()`.

Verified on the `b68f89e7` binary with `regtests/saturn/test_cd_lle.py` (PASS,
5.7 s): the firmware's SH-1 runs inside its ROM, raises its own boot HIRQ
pattern (read out of the image at `0x1F30` = `0x0BE1`) in the host window, sees
a host HIRQ acknowledge, and completes a host command (Get Hardware Info,
written CR1..CR4 with CR4 last) with CMOK within one frame after the host
cleared it. Response words for the record: `00ff ffff ffff ffff`. The firmware's
identity response `"\0CDBLOCK"` (from `0x1F38`) is visible in the window during
boot but is transient (the BIOS consumes it), so the fixture reports rather than
asserts it.

Host-interface effect on the HLE drive fixtures, measured with the same
`test_cdda_runtime.py` on two binaries built from the same tree (parent
`a17ec0d691b` vs `b68f89e7`):

    parent:  23 of 23 CDDA checks fail (TOC FADs `ffffff`, Play never reaches
             PLAY, no EXTS latch, pause/range/scan/periodic all dead)
    b68f89e7: 4 of 23 fail - play_tone_1k g1k=0.01431, play_tone_not_2k
             (second harmonic dominates), put_error_buffer_intact 200 -> 16640,
             scan_state 500

i.e. the window fix restored TOC, Play, pause/resume, range, SCAN, Q-track,
periodic cadence and the EXTS latch; the four that remain are the open
CD-DA/EXTS items (SND-02/SND-04), not window decoding. `test_cd_hirq.py` and
`test_cd_transfer.py` (338 cases) still pass on the same binary. No boot-to-game
claim: the LLE core has no CD drive (CDD serial link) behind it yet.

## SH-2 CPU-DMAC: transfer-request gating and the 16-byte-unit stall (2026-09-20)

Sources, official first.  `jkind73/saturnsdk`:`SATURN/INCLUDE/SEGA_DMA.H` gives the CPU-DMAC
register/field contract actually used on the Saturn (`REG_SAR 0xffffff80`, `DAR 0x84`,
`TCR 0x88`, `CHCR 0x8c`, `REG_DRCR 0xfffffe71` one byte per channel, `DMAOR 0xffffffb0`;
CHCR DE0/TE1/IE2/TA3/TB4/DL5/DS6/AL7/AM8/AR9/TS10-11/SM12-13/DM14-15 with TS = 0 byte,
1 word, 2 longword, 3 = 16-byte; DMAOR DME0/NMIF1/AE2/PR3).  `SBL6/SEGALIB/DMA/DMA_CPU0.C`
adds the behavioural contract the library enforces: `DMA_CpuSetPrm` pins TB (cycle steal) and
TA (dual address) to 0, `DMA_CpuStart()` is just `CHCR |= DE`, `DMA_CpuGetStatus()` reports
`CHCR.TE`, and `DMA_CpuSetCause()` refuses everything but RXI/TXI -
`DRDCR0/DRCR1のDREQ指定禁止への対応 '95-11/14` - i.e. on the Saturn the only usable
module-request sources are the SCI's RXI (receive data full) and TXI (transmit data empty).
The register text quoted verbatim in the reference implementation Ymir's
`hw/sh2/sh2_dmac.hpp` supplies the two sentences needed for the fix: "The DMAC determines
that a transfer is active by checking that DE = 1, DME = 1, TE = 0, NMIF = 0, AE = 0", and
for AR: "0 = Module request mode - external or on-chip SCI / 1 = Auto request mode -
generated within DMAC".  Nothing here is inferred from behaviour; anything the docs do not
state (DTCR reload rules, what sets `DMAOR.AE`, the DREQ edge-detection timing, `PR`
arbitration order) is left alone rather than guessed.

MAME's `sh7604_device` before the change:

* `sh2_dmac_check()` started a channel from `DE && DME && !TE` only - neither DMAOR status
  flag took part in the condition, and `CHCR.AR` was never read, so a channel programmed for
  module-request mode transferred immediately instead of waiting for its request.
* `m_dmac[].drcr` was written and saved but never read, so RXI/TXI selection was inert.
* the 16-byte unit path (`TS = 3`, `DMA_CPU_16`, a documented transfer size) called
  `fatalerror("SH2 dma_callback_fifo_data_available == 0 in unsupported mode")` when the
  destination FIFO could not take data, while the byte, word and longword paths mark the
  channel stalled (`m_dma_timer_active = 2`) and return, to be resumed by
  `sh2_notify_dma_data_available()`.

Change (`src/devices/cpu/sh/sh7604.{h,cpp}`): the active-transfer condition becomes
`DE && DME && TE == 0 && NMIF == 0 && AE == 0`; a channel with `AR = 0` now holds off until
the request selected by its `DRCR` is asserted, through three modelled lines (`m_dma_request`:
external DREQ pin, SCI RXI, SCI TXI) with `CHCR.DL` giving the DREQ active level as documented
(`CHCR.DS` edge detection is left unmodelled and commented, since no Saturn hardware drives
the pin); the SCI's flags feed those lines from `ssr_w()`/`tdr_w()` so a real SCI engine only
has to keep `SSR` honest; `drcr_w()` re-evaluates the channel instead of recomputing an
unrelated INTC priority; and the 16-byte unit stall returns like the other three sizes.
`dreq_w(int)` is exposed for machines with a wired requestor.  The `dreq` lines are saved.

Measured on the rebuilt `a735e0340a6`+patch binary (`saturnjp`, `-video none -sound none`), with
a scratch Lua probe driving the master SH-2's own DMAC registers through its program space
(`m.devices[":maincpu"].spaces["program"]`, the API the committed fixtures already use), 4 bytes
of a `0xa0..0xa3` pattern from `0x06180000` to `0x06180100`, so a completed transfer reads back
646 and a held-off channel reads back 0:

    ar1_auto        got=646 want=646 OK | auto request mode: transfers at once (unchanged)
    ar0_rxi_nodata  got=  0 want=  0 OK | AR=0 DRCR=RXI with RDRF clear: holds off (was 646 pre-fix)
    ar0_rxi_ready   got=646 want=646 OK | SSR.RDRF set: request asserted, transfer runs
    ar0_txi         got=646 want=646 OK | DRCR=TXI: SCI can accept data, so the request stands
    ar0_dreq_high   got=  0 want=  0 OK | DREQ active-high while the pin idles low: holds off
    ar0_dreq_low    got=646 want=646 OK | DREQ active-low while the pin idles low: transfers

No game-visible behaviour changes for auto-request channels, which is what the Saturn library
programs; the two new hold-offs are the module-request cases hardware would hold.  Regression
sweep on the same binary: `test_dma_source` (1152), `test_dma_bus` (768 + 2304), `test_dma_indirect`
(54 + 64), `test_dma_regs` (15360 + 7680), `test_sh_delay_irq` (72), `test_scu_abus` (32/32768/288/24576),
`test_scu_irqs` (1920 + 16 + 512), `test_sound_boot` (64 IRQ transitions), `test_smpc_transport`
(5402), `test_cd_hirq`, `test_cd_lle` - all exit 0 - and `run_vdp2_runtime.py --bios` reports
`BIOS_RUNTIME PASS system=saturnjp time=10.541321676 pc=06040228 full-image replay identical`,
which also round-trips the new `m_dma_request` state through MAME's real save manager.

Left alone on purpose, because no document in the two supplied sources settles it: what asserts
`DMAOR.AE` (the flag is now *honoured*, still never set), `DMAOR.PR` fixed-priority versus
round-robin arbitration between the two channels, `CHCR.DS` edge detection for DREQ, whether
`DTCR` reloads in module-request mode, and the SCI's bit-timed transmit/receive engine itself
(`sh7604_sci_device` remains un-instantiated and `ssr_r()` still force-ORs `0x84` for EGWord -
the DMAC side is now wired so a real SCI only has to keep `SSR` honest).

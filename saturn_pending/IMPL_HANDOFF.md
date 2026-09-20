# IMPL_HANDOFF — implementation agent → validation agent

- **Branch:** `arena/01a09f50-mame` is the validator's; per this sandbox's
  session policy all work is committed to **`arena/01a0b897-mame`**
  (fork of the same lineage, base `82152a8b` = tip of the accepted SCSP
  MVOL/DAC18B qualification). Fetch entries by the commit SHAs below from
  `origin/arena/01a0b897-mame`.
- **Append-only.** Newest entries at the bottom. Rejections: append a
  `REJECTED` line under the entry; fixes come as new entries.
- **Status labels in this file are implementation claims only.** Nothing in
  this file is verified; verification happens only in validator evidence.

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0001 | STV-04/STV-05 | d5f8416e | UNVALIDATED | 315-5649 RS-422 channels have real holding registers: FLAG reports occupancy, RX reads pop, loopback routes TX→RX |
| IMPL-0002 | CPU-03/IO-02 | 5a03df1d | UNVALIDATED | SH7604 SCI runs the documented async engine: (N+1)·2^(7+2n)·φ bit clock, TDRE/TEND/RDRF flow, TXI/RXI/ERI/TEI on VCRA/VCRB vectors |
| IMPL-0003 | DSP-02 | — | BLOCKED(pacing contract) | DSP DMA longword pacing follows the external data-ready signal (ST-097 pp.87-88); needs the BUS-01/02 grant/backpressure contract first |
| IMPL-0004 | CD-03 | — | BLOCKED(artifacts) | hardware-faithful CD block needs the cdb firmware dump + YGR019B register information before the SH-1 subsystem can be implemented |
| IMPL-0005 | SCU-03/BUS-01 | 13845208 | UNVALIDATED | SCU DMA head/tail bytes outside longword boundaries move in byte units: odd destinations don't clobber neighbours, odd sizes move exactly the programmed count |
| IMPL-0006 | STV-03/STV-04 | d6043a22 | UNVALIDATED | 315-5649 PORT-G counter reset latches a difference base; counter inputs wired to PORTG.0-3 ioports (patocar trackball path) |
| IMPL-0007 | CPU-03/IO-02 | e860f29a | UNVALIDATED | SCI SSR flags require a prior CPU read; TEND/MPB remain read-only, MPBT writes replace bit 0 |
| IMPL-0008 | CPU-03/IO-02 | 23eb938a | UNVALIDATED | SCI asynchronous TX reloads at the final stop bit, chains queued frames and preserves a full stop interval |
| IMPL-0009 | CPU-03/IO-02 | ca0432ea | UNVALIDATED | SCI receives parity/framing/overrun errors together at stop; unread RDR survives every overrun |
| IMPL-0010 | CPU-03/IO-02 | 3d18666d | UNVALIDATED | SCI MP receive mode discards non-address frames under MPIE and wakes on MPB=1 |
| IMPL-0011 | CPU-03/IO-02 | 25302858 | UNVALIDATED | SCI async RX samples eight 16x clock pulses after start detection, then every sixteen |
| IMPL-0012 | CPU-03/IO-02 | 7f895a95 | UNVALIDATED | SCI callback constructor initializers follow declaration order without suppressing reorder diagnostics |
| IMPL-0013 | CPU-03/IO-02 | ef6a191e | UNVALIDATED | External SCK clocks synchronous SCI receive: eight LSB-first rising-edge samples per character |
| IMPL-0014 | CPU-03/IO-02 | 5a128134 | UNVALIDATED | External synchronous SCI TX changes on falling SCK, chains at MSB and supports concurrent RX |
| IMPL-0015 | CPU-03/IO-02 | 01374a7d | UNVALIDATED | Internal synchronous SCI emits baud-derived SCK pulses, idles high and clocks TX/RX together |
| IMPL-0016 | CPU-03/IO-02 | 520b3f8a | UNVALIDATED | External asynchronous receive advances only on rising 16x SCK edges, without RX timer pacing |
| IMPL-0017 | CPU-03/IO-02 | ac368a39 | UNVALIDATED | External asynchronous TX advances once per sixteen rising SCK edges and never arms the internal bit timer |
| IMPL-0018 | CPU-03/IO-02 | a515c1a4 | UNVALIDATED | Async CKE=01 outputs continuous baud-rate SCK, with rising edges at transmitted-bit centers |

---

### IMPL-0001 — STV-04/STV-05 — 315-5649 RS-422 holding buffers, FLAG occupancy, loopback

- branch/commit: `arena/01a0b897-mame` @ **d5f8416e** (base: 82152a8b)
- files: `src/mame/sega/315_5649.cpp:63-79 (ctor), 88-113 (save/reset), 178-206 (read path), 239-241 (write path), 253-306 (serial_pop_rx/serial_rx_w/serial_transmit)`, `src/mame/sega/315_5649.h:57-62 (serial_rx_w API), 88-99 (state)`
- contract: each RS-422 channel of the 315-5649 I/O controller has a
  single-byte TX holding register and a single-byte RX holding register.
  The FLAG register (offset 0x0d) reports live buffer occupancy:
  RX2BF=bit3, RX1BF=bit2, TX2BF=bit1, TX1BF=bit0. Reading RXD1/RXD2
  (0x0b/0x0c) pops the holding register; when empty, the read falls back
  to the polled external-link callback. Mode register bit 4
  (RS-422 loopback, in-source register documentation) routes transmitted
  bytes back into the same channel's receiver without driving the
  external link. The mode register (0x0e) reads back its written value.
  This replaces the previous hardcoded status `0x0c`
  ("HACK, recv buffers always full").
- primary source: **none public for the 315-5649 register block.** The
  register map and bit names are the in-tree reverse-engineered
  documentation: `src/mame/sega/stv.cpp:115-129` (offsets, "0x001b RS422
  FLAG", "0x001d MODE ... RS422 satellite mode and node#") and
  `src/mame/sega/315_5649.h:55-61` (RXnFE/RXnBF/TXnBF bit layout). The
  CN18 connector is "SERIAL COMMUNICATION" per the ST-V service-manual
  excerpt quoted at `stv.cpp:94-98`. **Flagged limitation:** no primary
  document has been located for this chip; if the validator has the ST-V
  service manual section covering CN18/RS-422, its FLAG/bit semantics
  take precedence.
- cross-checks: in-tree sibling Sega I/O serial model
  `src/mame/sega/315_5338a.cpp:84-90` (single serial byte with read-back,
  callback-fed input); no pinned emulator (Ymir/MiSTer/mednafen) models
  this arcade I/O chip at all — cross-check set is empty, which is itself
  recorded here.
- expected observable: on any ST-V machine config using the `ioga` device
  map (default `stv*` maps install the device at `0x00400000`, see
  `stv.cpp:1155-1158`): (1) with mode=0, FLAG reads 0x00 and RXD1 reads
  the channel-1 rd-callback value (0 for unbound); (2) after writing
  mode=0x10 (loopback) and TXD1=0xa5, FLAG reads 0x04 and RXD1 reads
  0xa5 exactly once, then FLAG reads 0x00 again; (3) TXD writes without
  loopback assert the ch1 wr-callback and leave TX1BF=0 after the write
  completes (byte-level transmit, no bit timing modelled).
  Tolerance: exact register values, no timing component.
- suggested method: native fixture writing the IOGA registers through the
  SH-2 program space at 0x00400000 (umask 0x00ff00ff) and reading FLAG/
  RXD back, or a per-device Lua/Lua-less register probe on `:ioga`;
  save/load replay mid-occupancy (all new state is save-stated).
- falsifier: a hardware capture (or service-manual text) showing FLAG
  bits static (e.g. always 0x0c as the old hack assumed), loopback not
  routing TX into RX, or RX reads not consuming the holding register
  would each prove this change wrong. Behaviour delta to watch: games
  polling FLAG for satellite data now see "empty" instead of an infinite
  stream of always-full/zero-data bytes.
- self-check run: `python3 saturn_pending/impl_checks/check_3155649_serial.py`
  → `all checks passed` (extracted serial_pop_rx/serial_rx_w/serial_transmit
  + status arms driven in a C++ harness: occupancy per channel, loopback
  routing, external-link TX, overrun drop, read-back; method-level,
  unvalidated). TU syntax: `g++ -fsyntax-only ... src/mame/sega/315_5649.cpp`
  → exit 0.
- state: UNVALIDATED
- not covered / known doubts: satellite mode (bit 5) and node# are stored
  but no satellite/medal link device exists yet (STV-05 continuation);
  framing-error/IE bits (7,6,5,4) have no modelled source and read 0;
  receive overrun replaces the pending byte (no error latch); TX has no
  bit-level timing (byte-granular, matching the callback link design).
  Disagreement flagged: `stv.cpp:121-122` says mode bits 0-5 are
  "satellite mode and node#" while the device header assigns bit 4 to
  loopback — both readings preserved here (bit 4 written through to the
  stored mode either way).

### IMPL-0002 — CPU-03/IO-02 — SH7604 SCI transfer engine, SSR semantics, interrupt vectors

- branch/commit: `arena/01a0b897-mame` @ **5a03df1d** (base: 82152a8b)
- files: `src/devices/cpu/sh/sh7604.cpp:834-975 (register handlers + reset), 979-1176 (bit rate, TX/RX engines), 1537-1568 (sh2_recalc_irq SCI branch)`, `src/devices/cpu/sh/sh7604.h:22-26, 60-82, 205-224 (SSR bits, engine state, TxD/RxD callbacks)`
- contract: the SH7604 on-chip SCI (registers at H'FFFFFE00-FE05) runs
  the documented asynchronous transfer model: SMR/BRR/SCR select format
  and rate with bit period = (N+1)·2^(7+2n)·φ ticks in async mode and
  (N+1)·2^(4+2n)·φ in clocked synchronous mode (Tables 13.3/13.4/13.6
  pp.347-350; verified against table rows: f=4MHz n=0 N=0 → 31250 baud,
  f=14.7456MHz n=0 N=0 → 115200, f=28.7MHz n=0 N=22 → 9600±1.55%);
  clearing TDRE to 0 in SSR makes the SCI load TDR→TSR and re-set TDRE
  (p.372 steps 1-2); TEND is decided at MSB output time (p.373 step 3);
  TE=0 locks TDRE=1, sets TEND=1 and initializes TSR (pp.340, 373);
  the receiver samples each bit at the eighth pulse of a 16× clock
  (p.354), checks only the first stop bit (p.338), and sets
  RDRF/FER/PER/ORER per pp.344-345 with FER/PER transferring data to RDR
  without RDRF; SSR is write-0-to-clear for flags 7-2 with MPB read-only
  and MPBT read-write (pp.344-345), TDRE not clearable while TE=0;
  interrupts ERI>RXI>TXI>TEI are level-held at the IPRB bits 15-12 level
  with vectors VCRA bits 14-8 (ERI) / 6-0 (RXI) and VCRB bits 14-8 (TXI) /
  6-0 (TEI) (pp.91-92, Table 5.6, Table 13.13). SSR reset value H'84,
  TDR H'FF, BRR H'FF (Table 13.2 p.335). The old forced `m_ssr | 0x84`
  EGWord hack on ssr_r is removed — 0x84 is now the genuine idle state.
- primary source: SH7604 Hardware Manual, ADE-602-085C Rev 4.0 (Hitachi),
  pinned blob `4c1697421398cef77c7b52defda94ef5fead7372`
  (jkind73/saturnsdk `sh7604.pdf`): pp.333-352 (section 13), pp.372-373
  (transmit flow, Figures 13.15/13.20), pp.354 (16× sampling), pp.344-345
  (SSR flags), pp.91-94 (VCRA/VCRB vectors, Table 5.6), p.103 Table 5.4
  (SCI priority in IPRB).
- cross-checks: in-tree SH-2 DMAC text documents the SCI RXI/TXI DMA
  request linkage (`sh7604.cpp` manual text Section 9.4.1 Table 9.9 in
  the same manual); the standalone `src/devices/cpu/sh/sh7604_sci.cpp`
  stub (unused by any driver) is superseded for the live SH7604 core but
  left untouched; no pinned emulator implements the SH7604 SCI transfer
  level (Ymir models SCI registers only), so the cross-check set for the
  engine is empty — flagged.
- expected observable: on any Saturn/ST-V config, master or slave SH-2
  (φ = 28.6364 MHz, `sat_console.cpp:1081,1090`): (1) after reset
  SSR(0xfffffe04) reads 0x84; (2) with SMR=0, BRR=12, SCR=0x20, writing
  TDR=0x55 then clearing SSR bit 7 emits a 10-bit 8N1 frame on the TxD
  callback with first-data-edge exactly (N+1)·2^7/φ = 58.14 µs after the
  start-bit edge (tolerance ±1 φ tick), and re-sets TDRE; (3) with SCR
  bit 4 (RE) also set and the TxD waveform looped to RxD, RDR
  (0xfffffe05) ends holding the transmitted byte with RDRF set and
  FER/PER clear; (4) enabling TIE with TDRE=1 raises the CPU interrupt
  at the IPRB level with vector = VCRB bits 6-0; clearing TDRE drops it.
  All register values exact; timing tolerance ±1 φ tick per bit.
- suggested method: per-device fixture driving the internal SH-2 space at
  0xfffffe00-05 on a spare machine config (or the `sh7604` device directly
  in a minimal machine), Lua register hook on the CPU for SSR/TDR/RDR and
  a looped TxD/RxD callback pair; save/load replay mid-frame.
- falsifier: measured bit period not matching (N+1)·2^(7+2n)·φ (e.g. if
  the true silicon divides by 256·2^2n as the garbled ST-097-family
  formula text suggested), TDRE not re-set after the clear-write, RX
  bytes not delivered at the eighth 16× pulse, or vectors taken from
  registers other than VCRA/VCRB would each falsify the change. Watch
  Saturn titles that touch 0xfffffe04 in their boot (the removed 0x84
  force is only observable if software writes SSR first).
- self-check run: `python3 saturn_pending/impl_checks/check_sh7604_sci.py`
  → `all checks passed` (extracted sci_bit_period/sci_transmit_start/
  sci_tx_tick/sci_rx_tick/register write paths driven on a virtual clock:
  8N1 frame shape and spacing for 0x55, TDRE load/re-set flow, full
  TX→RX round trip delivering 0xa7 with RDRF, SSR write-0-clear with
  TDRE lock, both bit-period formulas; method-level, unvalidated). TU
  syntax: `sh7604.cpp`, `sh2.cpp`, `sh7604_sci.cpp`, `saturn.cpp` all
  exit 0 under the standard `-fsyntax-only` line.
- state: UNVALIDATED
- not covered / known doubts: clocked synchronous mode (C/A=1) is stored
  but not implemented (registers only, no transfer) and the tx/rx engines
  refuse it; external SCK clock (CKE1=1) has no input path yet;
  multiprocessor wake filtering (MPIE/MPB latching is modelled as flag
  storage only); DMAC request handshake from RXI/TXI (DRCR) is not wired;
  RX false-start resync granularity is 1/16 bit by construction of the
  oversample loop. `stv.cpp` cannot be fully syntax-checked in this
  sandbox (generated `critcrsh.lh`/`segabill*.lh` layout headers absent);
  the header change is covered by sh7604.cpp/sh2.cpp/saturn.cpp TUs.

### IMPL-0003 — DSP-02 — DSP DMA pacing is blocked on the shared-bus contract

- branch/commit: n/a (no code this entry)
- files: n/a
- contract: ST-097 pp.87-88 (Tables 4.6/4.7) define DSP DMA start/end as
  **"Follows the data ready signal from outside. Transfer is done by this
  signal in 1 long word units"**, with the T0 flag reset "by this timing"
  of the external end signal. Correct per-longword pacing therefore
  cannot be a free-running timer approximation inside the DSP: it must be
  driven by destination/source device readiness, i.e. the BUS-01/BUS-02
  grant and backpressure contract. The existing `scudsp.cpp:822-829`
  CPU-halt condition is labelled a hack in-source and **ST-097 contains no
  halt/acknowledgement wording** (searched the full pinned document for
  halt/busy: zero hits) — changing it without the bus contract or a
  hardware trace would be a guess and risks the vfremix behaviour the
  hack was added for.
- primary source: ST-097-R5-072694 (pinned blob
  `ffa8932249634ebd98947dad123621cebe3f24fa`) pp.87-88, Tables 4.6/4.7.
- cross-checks: none consulted beyond the primary, by design of this
  entry — no change is proposed yet.
- expected observable: n/a until a stage is implemented.
- suggested method: n/a.
- falsifier: n/a.
- self-check run: document search only: `python3` text extraction of all
  189 ST-097 pages, keyword scan `halt|Halt|HALT|busy|Busy` → 0 hits;
  DMA Command Execution text and Tables 4.6/4.7 extracted verbatim into
  this entry.
- state: **BLOCKED(pacing contract)** — unblocked by: (a) the BUS-01/02
  device-grant interface landing (validator-qualified or at least
  designed with measurement points), or (b) a hardware trace of DSP DMA
  longword cadence and CPU behaviour during DSP DMA. Neither artifact
  exists in this sandbox.
- not covered / known doubts: the burst-vs-cycle-steal approximation and
  the conditional INPUT_LINE_HALT stay untouched this session; the
  already-qualified B-bus increment work and program-RAM loader are
  preserved.

### IMPL-0004 — CD-03 — hardware-faithful CD block is blocked on external artifacts

- branch/commit: n/a (no code this entry)
- files: current state reviewed only: `src/mame/sega/saturn_cdb.cpp`
  (52 lines: YGR019B note, SH7032 instantiated with `set_disable()`,
  firmware ROM region `cdb106/cdb105/ygr022` declared).
- contract: per the report, full internal hardware emulation means
  implementing the SH-1/CD-controller memory/peripheral/drive interface
  and running the firmware; merely enabling the CPU is insufficient. The
  YGR019B (SH-1 + CD controller) register-level behaviour is not defined
  by any document in the pinned SDK set, and the firmware dumps declared
  in-tree are external ROM artifacts not present in this repository
  (ROMs are excluded from git by policy).
- primary source: none available for YGR019B registers; `SATMAN.pdf` in
  the SDK set is the Psy-Q debugger manual, not a hardware manual (title
  page verified this session).
- cross-checks: saturn_cd_hle.cpp implements the host-interface level
  only (CD-01/CD-02 scope).
- expected observable: n/a.
- suggested method: n/a.
- falsifier: n/a.
- self-check run: source inspection + ROM declaration review
  (`saturn_cdb.cpp:32-40`), method-level, unvalidated.
- state: **BLOCKED(artifacts)** — unblocked by: (a) a `cdb106`/`cdb105`/
  `ygr022` firmware dump available to the validator's runtime for
  measurement (MAME ROM set artifact), plus (b) register-level
  documentation or a firmware disassembly of the YGR019B
  host/DSP/drive interfaces. Until then any SH-1-side implementation
  would be unverifiable guesswork against the frozen CD HLE.
- not covered / known doubts: staging plan (for when artifacts land):
  stage 1 map the SH-1 internal peripherals and enable execution with
  the dual-port host interface delegated to the HLE device; stage 2
  route HIRQ/transfer FIFOs through the real firmware; stage 3 drive
  authentication. Each stage needs its own validator fixtures.

---

## Session notes for the validator (not entries)

1. **Branch naming deviation:** the prompt asked for `impl/saturn-gaps`;
   this sandbox pins the session to `arena/01a0b897-mame` and forbids
   pushing other branches. All commits are on `origin/arena/01a0b897-mame`
   (d5f8416e, 5a03df1d), never on the validator's `arena/01a09f50-mame`.
2. **Dependency-order M items not started this session, with the staged
   plan and why:** CPU-04 (restartable memory transactions) requires
   coordinated interpreter+DRC changes in `src/devices/cpu/sh/sh2.cpp`
   and the DRC front end; a dormant-infrastructure-only stage has no
   observable without its BUS-02 consumer, so queueing it would violate
   the readiness rule. BUS-01/BUS-02 need the arbiter design agreed with
   the measured wait-state table (the B-bus penalty numbers commented out
   in `saturn_scu.cpp:472-489` are the obvious first measurement targets
   for the validator). V1-01/V2-T02 remaining pieces are contention
   timing in the same family. SCU-04's wait-state penalties share that
   dependency (`saturn_scu.cpp:451` TODO).
3. **Primary-document extraction this session:** ST-097 pp.87-88
   (Tables 4.6/4.7), instruction format p.132 (Figure 4.8/4.9), and the
   full SH7604 SCI section were extracted from the pinned blobs via
   `gh api repos/jkind73/saturnsdk/git/blobs/<sha>`. The SCU manual text
   has no "halt"/"busy" wording anywhere (relevant to IMPL-0003).
4. **Frozen work untouched:** DMA acknowledgement handling, delay-slot
   IRQ behaviour, sound-reset/video-clock fix, SCSP corrections, AB2/
   Power Drift/OutRun acceptances — no commit this session modifies
   those code paths (diffs limited to 315_5649.{h,cpp} and
   sh7604.{h,cpp}).
5. **Sandbox build limitation:** full builds OOM here (per prompt);
   syntax-only checks were run for every touched TU with the documented
   include set. `stv.cpp` additionally needs generated `.lh` layout
   headers that are absent from the checkout (pre-existing).

### IMPL-0005 — SCU-03/BUS-01 — SCU DMA byte-unit head/tail transfers

- branch/commit: `arena/01a0b897-mame` @ **13845208** (base: 0cd84e36)
- files: `src/mame/sega/saturn_scu.cpp:900-930 (dma_read_byte, dma_transfer_direct_default), 932-952 (dma_transfer_direct_cbus_write)`, `src/mame/sega/saturn_scu.h:214-219`; deleted dead `dma_single_transfer` (was cpp:655-675, header:223-224)
- contract: ST-097 p.16: "This DMA is basically long word access through the
  DMA controller buffer, but if the start address and end address are not in
  long word boundaries, reads and writes are made in byte units" — Figure 2.1
  works the example src 1H-50H → dst 6H-55H with head bytes (dst 6H-7H, src
  1H-3H) and tail bytes (src 50H, dst 54H-55H) in byte units. In this engine's
  pre-existing 16-bit-per-tick cadence: a byte unit is moved when (a) the
  remaining count is odd (tail: exactly the programmed byte count moves) or
  (b) the destination cursor is not halfword-aligned (head/odd destination:
  single byte writes, the byte before the region is never touched). The
  source side already streamed from an offset longword buffer
  (dma_read_word, src & 3 honored); dma_read_byte shares that buffer
  discipline. Byte-unit destination cursor advance is dst_add>>1 for
  streaming adds (2→1), 0 for fixed (dst_add=0). Even aligned transfers are
  unchanged: same memory result, still exactly one 16-bit write per tick.
  The dead `dma_single_transfer()` shifted-byte hack ("TODO: reimplement
  me", Road Blaster workaround, unreferenced by the dispatch table) is
  removed.
- primary source: ST-097-R5-072694 (pinned blob
  `ffa8932249634ebd98947dad123621cebe3f24fa`) p.16 "Basic Operation of DMA"
  + Figure 2.1 (PDF text extracted verbatim this session).
- cross-checks: Ymir `libs/ymir-core/src/ymir/hw/scu/scu.cpp:797-811` (8-bit
  write when destination offset & 1), `:813-833` (16-bit realignment when
  offset & 2), `:847-861` (final 16-bit when count & 2), `:864-882` (final
  8-bit when count & 1) — same head-realignment + count-driven tail-unit
  rule; Ymir uses 32-bit ticks vs this engine's 16-bit ticks (pre-existing
  cadence, not changed here).
- expected observable: direct/indirect word-mode DMA (all three levels) on
  any Saturn/ST-V config: (1) even-size, halfword-aligned transfers:
  byte-identical memory to the previous engine and identical word-write
  granularity; (2) odd destination (DxW & 1 == 1): the byte at dst-1 reads
  back unchanged after the transfer and the stream lands at dst, dst+1...
  (3) odd size (DxC = 2n+1): exactly 2n+1 bytes move, one byte per tail
  tick (+1 DMA tick ≈ 4 SCU clocks vs the old over-move), completion IRQ
  after the last byte.
  Tolerance: exact memory values; tick count ±0 for odd tails (one extra
  tick vs old behaviour is part of the contract).
- suggested method: scripted DMA setup via the SCU registers (D0R/D0W/D0C/
  D0AD/D0MD + enable) with probe buffers in Work RAM-L at odd/even
  addresses and odd/even sizes, comparing memory images before/after and
  counting completion IRQ ticks; save/load replay mid-transfer (read-buffer
  state was already saved).
- falsifier: a hardware measurement showing odd-destination DMA clobbering
  dst-1 (i.e. hardware really does a read-modify-write word at dst&~1), or
  moving size+1 bytes for odd counts, or byte-unit reads at unaligned
  *source* behaving differently from the longword-buffer stream (all three
  would falsify the change). Ymir/Beetle disagreement on B-Bus write
  quirks is out of this entry's scope (see not-covered).
- self-check run: `python3 saturn_pending/impl_checks/check_scu_dma_bytetail.py`
  → `sweep 1: 6x6x17x2 byte-stream cases passed / sweep 2: aligned 16-byte
  case passed (8 word writes) / sweep 3: fixed-destination case passed /
  all checks passed` (extracted dma_read_word/dma_read_byte/both word-mode
  transfer functions on a fake big-endian space: 1,224 size/offset/
  cbus-streaming cases vs a reference byte-stream model, pre/post guards
  untouched, exact-count termination, aligned case still exactly 8 word
  writes; method-level, unvalidated). TU syntax: saturn_scu.cpp and
  saturn.cpp both exit 0.
- state: UNVALIDATED
- not covered / known doubts: CD-mode transfers
  (dma_transfer_direct_cd*, xfertype32) intentionally unchanged — CD block
  transfer is its own documented mode and needs CD-01/CD-02 acceptance;
  B-Bus-specific write quirks (Ymir scu.cpp:884+ "B-Bus writes are
  incredibly buggy... only +2 increments produce useful write patterns")
  are NOT modelled — if the validator can measure B-Bus DMA write patterns
  on hardware, that is a separate entry against BUS-01/BUS-02; dst_add
  values ≥4 (strided) in a byte-unit tick advance dst_add>>1 — no primary
  or cross-check defines strided byte units (Figure 2.10's strided example
  is aligned); DMA-illegal/ack/round-robin paths untouched (frozen DMA
  acknowledgement handling preserved).

### IMPL-0006 — STV-03/STV-04 — 315-5649 PORT-G counter reset latch + counter input wiring

- branch/commit: `arena/01a0b897-mame` @ **d6043a22** (base: 13845208)
- files: `src/mame/sega/315_5649.cpp:160-172 (counter read), 226-242 (counter reset latch on write), 46-90 (ctor/save/reset)`, `src/mame/sega/315_5649.h:87-91 (m_cnt_base)`, `src/mame/sega/stv.cpp:1371-1375 (in_counter_callback wiring)`
- contract: port G counter mode (mode register bit 7): four 16-bit
  external counter inputs; a port G write with bit 7 == 0 resets the
  counters, i.e. latches the current input values as the difference base
  (in-source register documentation `315_5649.cpp` old write case 0x06
  comment "bit 7 - 0 reset counters (not implemented)"; legacy ST-V
  handler `stv.cpp:196-202` snapshots all four on the same condition).
  Counter reads return (input − base) with the high/low byte selected by
  port G bit 0, and the port-G cursor auto-increments through the four
  counters (sel = bits 1-2, advance every read). Previously the device
  returned the raw input (and its input callbacks were unwired → 0), so
  any machine routed through the device read constant 0 in counter mode;
  the legacy three machines kept their own duplicate state.
- primary source: in-source register documentation only (as IMPL-0001);
  the counter-mode semantics live in the legacy handler
  `src/mame/sega/stv.cpp:146-156, 196-202` and the device comment. No
  primary document for the 315-5649 register block is available; the ST-V
  service manual's PORT-G/CN20 description (quoted at stv.cpp:93-97
  "PORT-G I/O 3 CN20 ... EXTENSION INPUT 8bit") is the nearest public
  text. **Flagged limitation:** same provenance caveat as IMPL-0001.
- cross-checks: formula-level equivalence with the legacy handler verified
  exhaustively (see self-check); trackball usage: patocar input mapping
  `stv.cpp:2237-2241` (PORTG.0/1 = IPT_TRACKBALL_X/Y, "sense/delta values
  seems wrong" note) is the only in-tree counter-mode consumer.
- expected observable: patocar (or any counter-mode title) with the IOGA
  device map: (1) writing port G = 0x00 (counter reset, cursor 0) then
  reading 0x0040000c four times returns bytes {high,input-base(counter0)},
  {low,...}, {high,input-base(counter1)}, {low,...} — i.e. the accumulated
  trackball delta since the reset write, instead of 0; (2) a further port G
  write with bit 7 == 0 re-latches: subsequent reads restart from the new
  base; (3) cursor sequence cycles (c0 high, c0 low, c1 high, c1 low, ...).
  Values exact; trackball sensitivity vs hardware remains the pre-existing
  open note.
- suggested method: machine fixture on patocar driving the IOGA registers
  at 0x00400000 with the trackball ioport forced to known values between
  reset-write and reads; save/load replay between reset and read
  (m_cnt_base is save-stated).
- falsifier: hardware/service-manual evidence that counter reads return
  the raw external counter (no difference base) or that the reset write
  clears an internal accumulator instead of latching a base would falsify
  the latch model; a patocar attract-mode regression where the trackball
  stops responding (delta reads stuck) would falsify the wiring.
- self-check run: `python3 saturn_pending/impl_checks/check_3155649_counter.py`
  → `all checks passed (formula equivalence, 8 cursor states, wiring)`
  (source-level formula comparison against the legacy handler, exhaustive
  8-state cursor table, wiring presence; method-level, unvalidated). TU
  syntax: 315_5649.cpp exit 0; stv.cpp not fully checkable here
  (pre-existing missing generated .lh headers; its change is four
  set_ioport lines mirroring the adjacent lines).
- state: UNVALIDATED
- not covered / known doubts: the legacy stv_state handler and its
  duplicated state remain for the critcrsh/stvmp/hop machines —
  consolidating them onto the device is the follow-up stage (regression
  surface: their lightgun/mahjong/hopper overrides); the counter *input*
  rate/timing (how fast the external counter increments per trackball
  tick) is ioport-driven and unqualified; counter-mode + satellite-mode
  bit interaction unmodelled.

---

## Session addendum (second batch)

6. **EXP-01 document lead closed:** ST-240-A/B in the SDK set are the
   **SCU DSP Assembler** manuals (title page verified from blob
   `288d9605cd090e017230c26176aa5b91ba1a81d7` this session), not the
   Video CD/MPEG board manuals. No primary MPEG-board documentation is
   present in the pinned SDK set; EXP-01 remains R/blocked on either the
   correct Sega document or a board trace.
7. **CPU-04 status:** confirmed this session that the SH-2 core
   (`sh2.h`/`sh2.cpp`) has no deferred/restartable memory-access
   infrastructure at all (no delayed-access members). The remaining work
   is a coordinated interpreter+DRC design; no dormant stage is
   queueable without its BUS-02 consumer and a stated observable.
8. **Regression guard for IMPL-0005:** aligned/even DMA was verified to
   keep identical memory results and identical word-write counts
   (sweep 2 of the check script), so the frozen DMA-acknowledgement and
   accepted-game behaviours should be untouched; the falsifier covers
   the case where that assumption is wrong on hardware.


### IMPL-0007 — CPU-03/IO-02 — SCI SSR acknowledgements and writable-bit contract

- branch/commit: `arena/01a0b897-mame` @ **e860f29a** (base: 4e046da1).
- files: `src/devices/cpu/sh/sh7604.cpp:108,233` (save/reset),
  `:949-983` (SSR read/write), `src/devices/cpu/sh/sh7604.h:201`
  (read snapshot), `saturn_pending/impl_checks/check_sh7604_ssr.py`.
- contract: SSR bits 7-3 can be cleared by software only after being read
  as one. A status inspection with side effects disabled does not arm an
  acknowledgement. TE=0 prevents software clearing TDRE. TEND and MPB
  cannot be directly written; an accepted TDRE clear also clears TEND.
  MPBT is ordinary read/write, including 1-to-0 writes. Consumed read
  permissions are removed before TDR-to-TSR loading raises TDRE anew.
  This supersedes IMPL-0002's incorrect flags-7-2 write-mask description.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.2.7, printed pp.342-346 (PDF pp.358-362), SSR bit table and
  TDRE/TEND/MPB/MPBT descriptions; section 13.2.6 p.340 TE=0 lock;
  section 13.3.2 p.359 steps 1-2 for TDR/TSR handshake. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MAME upstream pinned at
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:202-222`: this candidate adapts its
  read-qualified acknowledgement/mask pattern for the SH7604 SCI. H8 is
  a related implementation, not independent SH7604 silicon evidence.
  Upstream `src/devices/cpu/sh/sh7604.cpp:872-879` still stores SSR
  directly/returns zero RDR, so it supplies no working SH7604 engine to
  port. Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_sci.hpp:25-28` documents the
  write-zero-only flags/reset value but not the read qualification.
- expected observable: exact byte values (tolerance zero). Starting
  SSR=0x84, TE=1: unread SSR write 0x7e leaves 0x84 and emits no start
  bit; CPU read then write 0x7e starts an idle asynchronous transmitter,
  clears TEND and reloads TDRE, leaving 0x80. Repeating the write without
  another CPU read must not queue another byte. With TE=0 and reset SSR,
  writes 0x01 then 0x00 leave 0x85 then 0x84. MPB retains its hardware
  value across either write. No timing tolerance asserted by this entry.
- suggested method: legal mapped-register probes at H'FFFFFE04 on both
  CPU engines; interleave debugger inspection and CPU reads with writes;
  inject a receive flag between read and acknowledgement. Save/load
  between the CPU read and write, then between TDRE reload and next read.
- falsifier: a write without a qualifying CPU read clearing a flag,
  an inspection enabling such a clear, direct modification of TEND/MPB,
  MPBT stuck high, or reuse of a consumed TDRE read to queue another
  byte contradicts this candidate. A hardware trace showing the opposite
  read-qualification rule would falsify the implemented model.
- self-check run: `python3 saturn_pending/impl_checks/check_sh7604_ssr.py`
  raw output (method-level, unvalidated):
  ```text
  method-level, unvalidated: 33554432 SSR transitions; read/inspect/re-arm cases exercised
  method-level, unvalidated: SSR read-latch reset/save registration present
  ```
  `g++ -fsyntax-only -std=c++20 -w` with the session include set on
  `src/devices/cpu/sh/sh7604.cpp`: exit 0. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: no linked/native execution. New
  `m_sci_ssr_read` is saved/reset in the same production commit; save
  files from earlier revisions are not layout-compatible. SH-DMAC SCI
  request/implicit-ack routing is still absent. This entry does not
  implement clocked synchronous/external SCK operation or repair queued
  asynchronous frames; the latter is a separate follow-up. The older
  IMPL-0002 extracted harness lacks the new read-latch/mock-machine
  fields and is not an acceptance gate for this revision; its source
  and expected values were not edited.


### IMPL-0008 — CPU-03/IO-02 — SCI asynchronous queued-frame transmission

- branch/commit: `arena/01a0b897-mame` @ **23eb938a** (base: 78124cf3;
  depends on IMPL-0007's read-qualified SSR handshake).
- files: `src/devices/cpu/sh/sh7604.cpp:114,241` (save/reset),
  `:903-942` (SCR/TE cancellation and interrupt-enable writes),
  `:1018-1105` (TX frame start/bit timer),
  `src/devices/cpu/sh/sh7604.h:203-205` (next-event index/queued-TSR flag),
  `saturn_pending/impl_checks/check_sh7604_tx_chain.py`.
- contract: internally clocked asynchronous TX keeps the current data in
  TSR through parity/MP output. At the final stop-bit output, pending
  TDR data loads into TSR and TDRE rises; IRQ state is recalculated then.
  The next start bit follows one full bit period later. Without pending
  data, TEND rises at that stop-bit output, but the transmitter keeps
  the line high until the full stop interval expires. A byte submitted
  during that interval waits until the interval ends. TE=0 cancels both
  current and queued work. TIE/TEIE-only SCR writes do not restart the
  bit timer. No additional inter-frame idle bit is inserted.
  This supersedes IMPL-0002's MSB-based asynchronous reload assumption
  (that manual passage belongs to clocked synchronous mode).
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.3.2 pp.354-360, Table 13.11, p.359 steps 1-3 and Figure
  13.6; section 13.3.3 pp.366-367/Figure 13.11 for MP format; section
  13.2.7 p.345 specifies TEND at the last bit of a character. TE=0
  initialization is in section 13.2.6 p.340. Source SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. The former p.373 citation
  describes synchronous operation and is not the async contract.
- cross-checks: MAME upstream pinned at
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:517-535,548-625`, independently stages
  start/data/parity/stop and loads TDR only after the last stop output,
  before the next start. This related Hitachi device is a structural
  cross-check, not SH7604 hardware evidence. **Difference:** H8's
  `ST_LAST_TICK` sets TEND after the last stop interval; this SH7604
  candidate follows the SH7604 manual's stop-bit-output wording instead.
  The exact TEND/TEI edge therefore remains an explicit silicon target.
  Pinned upstream SH7604 remains a register stub (see IMPL-0007);
  Ymir's pinned SH2 SCI header supplies no transmission engine.
- expected observable: with 8N1 and bit period B CPU phi ticks, submit
  byte A at t=0 and byte B before t=9B. A's start/data/stop occupy
  t=0..10B; TDRE rises for the second TSR load at 9B, not 8B; B's
  start occurs at 10B, and its data is not lost. With no third byte,
  TEND rises at 19B and TxD stays high through 20B. For 8E1, parity
  at 9B uses A, reload occurs at 10B and next start at 11B. For two
  stops the next start is delayed by one additional B. A write halfway
  through the final stop cannot truncate it. Tolerance: exact bit values
  and periods for this model; allow one scheduler attosecond rounding
  per bit for a native timer probe. Silicon edge/baud qualification is
  not inferred from that software tolerance.
- suggested method: record TxD callbacks and SSR/TXI/TEI through mapped
  SH7604 register accesses, with queued data before MSB, between parity
  and stop, and during stop. Include 7/8 data bits, parity none/even/odd,
  1/2 stops, constant-MP-bit frames and TE cancellation. Save/load at
  final-stop midpoint with one byte already in TSR and another in TDR;
  compare uninterrupted suffixes and IRQs on both CPU engines.
- falsifier: missing or duplicated queued bytes, parity calculated from
  the next byte, TDRE rising at MSB, a shortened stop bit, lost TXI
  recalculation, an extra start after TE=0, or TIE-only writes changing
  bit spacing contradicts this candidate. A hardware trace showing
  a different TEND edge or two-stop reload point falsifies that timing
  assumption even if the extracted-method checks still agree.
- self-check run: `python3 saturn_pending/impl_checks/check_sh7604_tx_chain.py`
  raw output (method-level, unvalidated):
  ```text
  method-level, unvalidated: 4096 three-frame format/data cases; exact bit traces and state-copy replay
  method-level, unvalidated: late queue, stop-bit hold, IRQ refresh and TE cancellation exercised
  method-level, unvalidated: queued-TSR reset/save registration present
  ```
  Re-ran `check_sh7604_ssr.py` unchanged:
  ```text
  method-level, unvalidated: 33554432 SSR transitions; read/inspect/re-arm cases exercised
  method-level, unvalidated: SSR read-latch reset/save registration present
  ```
  Both compile extracted methods with `-fsanitize=undefined`.
  `g++ -fsyntax-only -std=c++20 -w` with the session include set on
  `src/devices/cpu/sh/sh7604.cpp`: exit 0. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: no native MAME execution, real interrupt
  vector/priority test, or save-manager replay. `m_sci_tx_loaded` is
  saved/reset in this change, and `m_sci_tx_bit` now means the next
  timer event, not the last event; older save files are incompatible.
  MPBT changes while a different MP character is in flight are not
  covered (the existing live MPBT sampling remains). RX simultaneous
  parity/framing/overrun semantics, external SCK, synchronous transfer,
  SCI DMA routing and real peripheral wiring remain incomplete.
  No claim is made about external communication-device acceptance.


### IMPL-0009 — CPU-03/IO-02 — SCI simultaneous receive errors

- branch/commit: `arena/01a0b897-mame` @ **ca0432ea** (base: b3c853cc).
- files: `src/devices/cpu/sh/sh7604.cpp:118,247` (save/reset),
  `:1109-1215` (RX timer/completion), `src/devices/cpu/sh/sh7604.h:212`
  (pending parity), `saturn_pending/impl_checks/check_sh7604_rx_errors.py`.
- contract: the parity sample records a pending result, not a completed
  receive operation. At the first stop-bit sample, latch PER, FER and
  ORER independently, according to SH7604 Table 13.14. If RDRF was set,
  retain unread RDR regardless of other errors; otherwise load received
  data even on parity/framing errors, but set RDRF only for a good frame.
  Recalculate IRQ status once at completion. Latched errors continue to
  block further reception until acknowledged. This replaces IMPL-0002's
  early parity-error completion and mutually exclusive error handling.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.3.2 printed p.363 (PDF379), steps 3-4 and Table 13.12;
  section 13.5 printed p.381 (PDF397), Table 13.14 explicitly enumerates
  all seven error combinations and RSR-to-RDR transfer rules. Section
  13.2.7 pp.343-344 describes error flags and retaining unread data.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:677-701,743-762`: parity is collected
  before STOP and reception finishes at STOP, corroborating staging.
  **Disagreement:** its H8 implementation prioritizes FER/PER and does
  not implement SH7604 Table 13.14's independent flags/data transfer.
  MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:297-320` (blob
  `14012b0605b00431137629d1cdd3f3ed63bfbe61`), records PER/FER
  separately and checks RDRF before loading RDR. Its early PER/FER and
  unconditional RDRF on non-overrun REC_END differ from the primary table;
  those behaviors are not adopted. No reference code imported.
- expected observable: exact values, no tolerance. Mask SSR by 0x78:
  normal=0x40; PER=0x08; FER=0x10; FER+PER=0x18; overrun alone=0x60;
  overrun+PER=0x68; overrun+FER=0x70; all three=0x78. For every overrun,
  old RDR remains unchanged; for other rows RDR becomes the received
  byte (7-bit reception clears bit7). No visible receive error/IRQ at
  the parity sample; completion occurs at the first stop sample.
- suggested method: drive RxD with independent 7/8-bit parity frames,
  corrupt parity and/or stop and prefill RDRF independently. Observe
  RDR/SSR/ERI before parity, after parity, and after stop. Save/load
  between parity and stop, including all-three-error cases, then clear
  errors through the read-qualified SSR handshake and send a clean frame.
- falsifier: any missing combined error bit, overwrite of unread RDR on
  overrun, RDRF set on a non-overrun bad frame, completion at parity
  before stop, or pending parity lost across save/load contradicts this
  candidate. A silicon trace differing from Table 13.14 is an explicit
  reason to reject or revise the model, not adjust fixture expectations.
- self-check run: `python3 saturn_pending/impl_checks/check_sh7604_rx_errors.py`
  raw output (method-level, unvalidated):
  ```text
  method-level, unvalidated: 524288 Table 13.14 data/status cases; 16384 received parity frames
  method-level, unvalidated: deferred errors, RDR retention, state-copy replay, stall/recovery exercised
  method-level, unvalidated: pending parity reset/save registration present
  ```
  The same new script with a `git show b3c853cc:src/devices/cpu/sh/sh7604.cpp`
  source copy exits 1: `line 185: d.m_ssr==(0x84|flags[error])`.
  Current `check_sh7604_ssr.py` and `check_sh7604_tx_chain.py` rerun
  unchanged, exit 0 (33,554,432 SSR transitions / 4,096 TX cases).
  All extracted checks use UBSan. TU `sh7604.cpp` syntax with the
  standard session include set: exit 0; `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: native IRQ delivery, actual save-manager
  replay and physical sampling phase remain open. One new saved/reset
  field `m_sci_rx_parity_error` changes the save layout; older save files
  are incompatible. Multiprocessor wake filtering is still absent in
  this commit. External clock/synchronous RX and SCI DMA remain absent.
  No frozen DMA acknowledgement, delay-slot IRQ, sound or video path is
  changed. Method-level state-copy replay is not a save-manager claim.


### IMPL-0010 — CPU-03/IO-02 — SCI multiprocessor receive filtering

- branch/commit: `arena/01a0b897-mame` @ **3d18666d** (base: ca06f866;
  depends on IMPL-0009's receive-completion/error behavior).
- files: `src/devices/cpu/sh/sh7604.cpp:119,249` (save/reset),
  `:1124-1134,1167-1196` (MP capture and completion filter),
  `src/devices/cpu/sh/sh7604.h:213` (pending MP bit),
  `saturn_pending/impl_checks/check_sh7604_multiprocessor.py`.
  `check_sh7604_rx_errors.py` gains only a mock state declaration;
  no existing expected values or validator assets were changed.
- contract: in asynchronous MP format, latch the received multiprocessor
  bit and publish it in SSR.MPB at character completion (both 0 and 1).
  While SCR.MPIE=1, an MPB=0 character does not modify RDR, set RDRF,
  generate receive errors, or request RXI/ERI. MPB=1 automatically clears
  MPIE and that address character undergoes normal receive/error handling.
  Software may inspect the ID and re-arm MPIE; hardware does not compare
  the ID itself. MPIE has no filtering effect when SMR.MP=0.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.2.6 printed pp.340-341 (SCR.MPIE), section 13.2.7 p.345
  (SSR.MPB), section 13.3.3 pp.367-371, Figure 13.12 receive procedure
  and Figure 13.13's ID-match/mismatch streams. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. The manual's MPIE paragraph
  mentions TIE/RIE together; receive interrupt enabling here follows the
  explicit RIE descriptions and receive flow, not transmit enable TIE.
- cross-checks: MAME upstream pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:102,150,202-222` names MP/MPIE and
  preserves software-read-only MPB, but has no receive wake filter to
  port. MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:232-341`, resets MPB but likewise supplies no
  MPIE receive-filter implementation. These checks expose reference
  omissions, not independent corroboration of filter timing. Primary
  SCR semantics and Figure 13.13 are the implementation basis.
- expected observable: exact register bytes, tolerance zero. With MP=1,
  RE=RIE=MPIE=1 (SCR=0x58), old RDR=0xa5 and no RX flags: receiving
  data 0x23 with MPB=0 leaves RDR=0xa5, MPIE=1 and flags clear, even
  if its stop bit is bad. Receiving 0x23 with MPB=1 and good stop
  gives SCR=0x50, RDR=0x23, RDRF=MPB=1 and an RXI request. After
  acknowledging RDRF, a normal MPB=0 data frame is received and clears
  MPB. Re-arming MPIE restores the discard behavior. With MP=0, setting
  MPIE must not filter ordinary asynchronous frames.
- suggested method: independent RxD address/data streams plus mapped SSR,
  SCR and RDR reads, 7/8-bit formats and 1/2 stops; include pending RDRF,
  bad stop, software re-arm and non-MP controls. Save/load between MP
  sampling and stop while asleep and waking. Compare actual ERI/RXI
  delivery with RIE=0/1; TIE must not control receive interrupt delivery.
- falsifier: a non-address frame changing RDR/RDRF or reporting an error
  while MPIE=1, address reception failing to clear MPIE, MPB stuck at 1,
  filtering when MP=0, or loss of the pending MP bit on save/load
  contradicts this candidate. Silicon showing MPB publication or MPIE
  clearing before the stop sample would falsify that chosen latch edge;
  exact edge qualification remains open even if byte-level results agree.
- self-check run: `python3 saturn_pending/impl_checks/check_sh7604_multiprocessor.py`
  raw output (method-level, unvalidated):
  ```text
  method-level, unvalidated: 32768 MP-format/filter/error/data cases and state-copy replay
  method-level, unvalidated: address/data, software re-arm and non-MP controls exercised
  method-level, unvalidated: pending MP bit reset/save registration present
  ```
  Pre-change `ca06f866` source copy with the same new script exits 1:
  `line 194: d.m_ssr==expected`. RX-error/SSR/TX-chain scripts rerun
  with unchanged expected values, exit 0 (524,288 table cases plus
  16,384 RX frames; 33,554,432 SSR transitions; 4,096 TX cases).
  Extracted checks use UBSan. TU `sh7604.cpp` syntax with the standard
  include set: exit 0; `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: exact MPB/MPIE sub-bit latch timing is
  not specified by the byte-level descriptions; completion-edge choice
  needs a hardware capture. No native IRQ or save-manager execution.
  `m_sci_rx_mp` is saved/reset in this production commit; old save files
  are incompatible. TX MPBT update timing, external SCK/synchronous
  operation, SCI DMA and actual external peripherals remain incomplete.
  Configuration inventory is now explicit in
  `saturn_pending/IO_DEVICE_INVENTORY.md`: present controller/cart/arcade
  devices are distinguished from missing modem, cable and peer support;
  SCI progress is not an external-device acceptance claim.


### IMPL-0011 — CPU-03/IO-02 — SCI asynchronous RX sample phase

- branch/commit: `arena/01a0b897-mame` @ **25302858** (base: 4c10d3f3).
- files: `src/devices/cpu/sh/sh7604.cpp:1126-1138` (start detection),
  `saturn_pending/impl_checks/check_sh7604_rx_phase.py`.
- contract: after detecting low at a receiver oversampling tick, confirm
  the start at the eighth following tick; sample each successive frame
  bit sixteen ticks later. Initialize the phase of the next callback to
  one rather than zero, since the existing callback checks the phase
  before incrementing. Former behavior sampled nine ticks after detection.
  A high line at the start sample rejects the false start without RDRF
  or an error. No other register or bit-period behavior is changed.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.3.2 printed p.354, section 13.5 pp.381-382 and Figure
  13.21: synchronization is sampled on the 16x base clock, the first
  sample is eight clocks later and subsequent samples sixteen apart.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MAME upstream pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:705-709,718-725`, uses phase eight
  of sixteen and rejects a high start sample. Its counter is incremented
  before the phase check, unlike this SH7604 callback. Its pin-edge and
  clock-start scheduling (`:457-489`) differ, so those lines are not
  evidence of an identical edge-to-first-pulse latency. MiSTer's pinned
  SH7604 SCI (`a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:275-307`) uses SCE_R and supplies no directly
  comparable 16x asynchronous start-detection counter. Primary Figure
  13.21 governs this candidate's phase; no external code imported.
- expected observable: let t0 be the first 16x clock tick observing a
  low start bit, Q=B/16 be one oversampling interval. Start validation
  occurs at t0+8Q; data bit0 at t0+24Q; bit7 at t0+136Q; 8N1 receive
  completion at t0+152Q. The old engine was one Q late at each point.
  Tolerance: exact tick index in the model; a physical falling edge may
  precede t0 by up to one Q due to asynchronous detection. Native
  attotime probes may accumulate one attosecond of rounding per tick.
- suggested method: independently drive RxD transitions around sample
  instants, rather than loopback through the same transmitter. Probe
  SSR/RDR before and after the first-stop sample; include 7/8 data,
  parity none/even/odd, MP format, both STOP settings, false starts and
  one-oversample pulses on each side of data midpoints. A serial hardware
  trace should distinguish detection quantization from sampling delay.
- falsifier: start confirmation at the ninth rather than eighth pulse,
  or data bit n sampled at t0+(25+16n)Q instead of t0+(24+16n)Q is the
  prior defect. A high start sample accepted as a frame or a seventh/
  ninth-pulse-only glitch sampled as data also contradicts this candidate.
  Hardware requiring a different synchronization delay would falsify
  the chosen phase model.
- self-check run: `python3 saturn_pending/impl_checks/check_sh7604_rx_phase.py`
  raw output (method-level, unvalidated):
  ```text
  method-level, unvalidated: 4096 frame sample schedules; 24 midpoint glitch probes; false-start edge
  ```
  Pre-change `4c10d3f3` source copy exits 1 with the same new script:
  `line 149: rejected.m_sci_rx_state==0 && rejected.irqs==0`.
  RX-error, multiprocessor, SSR and TX-chain checks rerun unchanged,
  exit 0. These are extracted methods with UBSan and mock timers, not
  native execution. TU `sh7604.cpp` syntax with the session include set:
  exit 0; `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: no hardware edge-margin, native timer,
  clock-change or external-SCK qualification. Existing periodic sampling
  starts when RE is enabled; physical falling-edge detection is quantized
  to that timer, not a new pin-edge device. No state field or save layout
  added by this commit; IMPL-0009/0010 already changed the save layout.
  Freeze rules and validator assets remain untouched.


### IMPL-0012 — CPU-03/IO-02 — SCI constructor build correction

- branch/commit: `arena/01a0b897-mame` @ **7f895a95** (base: 08e65756).
- files: `src/devices/cpu/sh/sh7604.cpp:36-55` (constructor only).
- contract: place `m_write_txd` and `m_read_rxd` initializers after the
  SCI register initializers and before FRT initializers, matching their
  header declaration order. Retain callback arguments and RxD idle=1.
  No warning suppression or device behavior change is introduced.
- primary source: user-supplied MinGW `-Werror=reorder` build failure;
  C++ member initialization rule [class.base.init], which initializes
  members in declaration order regardless of initializer-list order.
  No new hardware contract is involved.
- cross-checks: pinned pre-change `08e65756`,
  `src/devices/cpu/sh/sh7604.h:217-224,299-301` declares the SCI
  callbacks before FRT and the FRT read delegate. Constructor lines
  53-55 previously listed the SCI callbacks after that delegate.
  `scripts/genie.lua:945` supplies MAME's existing
  `-Wno-sign-compare`; no build configuration is modified here.
- expected observable: `sh7604.cpp` compiles with reorder diagnostics
  treated as errors (zero reorder diagnostics). Callback configuration,
  register/reset behavior and save layout remain unchanged.
- suggested method: rerun the reported Windows build; also syntax-check
  the full translation unit using `-Werror=reorder` without `-w`.
- falsifier: the reported constructor reorder diagnostic persists,
  or the patch changes callback constructor arguments/member layout.
- self-check run (compiler-level, unvalidated):
  ```text
  pre-change g++ -fsyntax-only -std=c++20 -Werror=reorder: exit 1
  m_ftcsr_read_cb will be initialized after m_write_txd [-Werror=reorder]
  post-change same command: exit 0, no diagnostics
  post-change -Wall -Werror: exit 1, existing sign-compare diagnostics
  post-change -Wall -Werror -Wno-sign-compare: exit 0, no diagnostics
  git diff --check: exit 0
  ```
  Include arguments for each compiler invocation:
  ```text
  -Isrc -Isrc/emu -Isrc/devices -Isrc/lib -Isrc/lib/util
  -Isrc/lib/netlist/devices -Isrc/frontend -Isrc/frontend/mame
  -Isrc/mame -Isrc/osd -Isrc/osd/modules/lib
  src/devices/cpu/sh/sh7604.cpp
  ```
  The plain `-Wall -Werror` errors are in existing signed comparisons
  in shared headers and `sh2_exception`; the repository already disables
  that warning. Reorder diagnostics were never disabled in these runs.
- state: UNVALIDATED
- not covered / known doubts: no Windows/MinGW compiler or full linked
  build run here. Earlier syntax checks used `-w`, which hid this defect;
  future checks must retain reorder diagnostics. This is a build-only
  correction to the earlier SCI callback addition, not SCI hardware
  acceptance. No added state, save-layout change or validator asset edit.


### IMPL-0013 — CPU-03/IO-02 — external-clock synchronous SCI receiver

- branch/commit: `arena/01a0b897-mame` @ **ef6a191e** (base: 2953c777).
- files: `src/devices/cpu/sh/sh7604.h:37,215` (SCK input API/history),
  `src/devices/cpu/sh/sh7604.cpp:123,253` (save/reset), `:925-947`
  (RE disable/re-enable), `:1003-1039` (SCK receive path),
  `saturn_pending/impl_checks/check_sh7604_sync_rx.py`.
- contract: `sck_w(int)` tracks external pin transitions. With C/A=1,
  CKE1=1 and RE=1, a falling edge synchronizes the receiver; each rising
  edge then samples RxD. After exactly eight samples, the LSB-first byte
  goes through the existing completion/overrun path. CHR, PE, O/E, STOP,
  MP and MPIE do not change synchronous character framing. Repeated pin
  levels do not advance the transfer. RE=0 discards partial input; after
  re-enable a new falling edge is required. ORER/PER/FER block reception
  until acknowledged. No internal timer synthesizes these external edges.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.3.4 pp.372-378, Figure 13.14 (data valid on rising clock,
  falling-edge synchronization, fixed eight-bit format), Figure 13.19
  (receive/overrun), p.378 receive steps 1-3; Table 13.9 pp.341-342 for
  clock selection. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:275-286,311-320` samples synchronous data on
  SCE_R, completes eight bits and preserves RDR on overrun. Upstream
  MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:769-797` also samples on rising clock
  phase and assembles eight bits. The related H8 is only a structural
  cross-check. Upstream SH7604 remains a register stub; no code imported.
- expected observable: with SMR=0x80, SCR=0x52 and clear RX flags, input
  data 0x96 held at eight successive rising SCK edges yields RDR=0x96,
  SSR=0xc4 and a receive IRQ recalculation only at edge eight. A second
  byte without RDRF acknowledgement leaves RDR=0x96, SSR=0xe4. Repeated
  high/low writes never add samples. All lower SMR format bits leave the
  eight-bit framing unchanged. Tolerance: exact edge count/data/status;
  setup/hold and synchronizer delay in phi cycles are not asserted.
- suggested method: linked per-device fixture binds RxD, calls `sck_w`
  and accesses real mapped SCI registers on both CPU engines. Drive
  opposite data on falling vs rising edges; exercise CKE=2/3, RE=0,
  asynchronous/internal-clock controls, all format bits, overrun and
  error recovery. Save/load at both polarities between any two bit edges.
- falsifier: an extra sample from a repeated level or falling edge,
  reception without RE/external synchronous selection, fewer/more than
  eight samples, framing controlled by asynchronous format bits, lost
  RDR on overrun, or duplicate/missing data after save/load contradicts
  this candidate. Hardware showing a different sample edge falsifies
  the chosen pin contract.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 262144 sync RX format/control/data cases; 4096 half-edge state-copy replays
  method-level, unvalidated: repeated levels, stop/resume, error stall, overrun and mode gates exercised
  method-level, unvalidated: SCK edge-history reset/save registration present
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_sync_rx.py`.
  Existing SSR/TX-chain/RX-error/MP/RX-phase extracted checks rerun with
  unchanged expected values: exit 0. Full `sh7604.cpp` TU syntax with
  `-std=c++20 -Wall -Werror -Wno-sign-compare` and the session includes:
  exit 0, no diagnostics. Reorder warnings enabled. `git diff --check`:
  exit 0. These are compiler/extracted-method results, not native proof.
- state: UNVALIDATED
- not covered / known doubts: native CPU/IRQ/save-manager behavior and
  physical pin setup/hold are open. One saved/reset field `m_sci_sck`
  changes the save layout; old save files are incompatible. Synchronous
  transmit, internal synchronous clock generation, external-clock async,
  SCI DMA and actual modem/cable wiring remain absent in this commit.
  No Saturn/ST-V configuration is claimed to have an attached SCI peer.


### IMPL-0014 — CPU-03/IO-02 — external synchronous SCI TX/full duplex

- branch/commit: `arena/01a0b897-mame` @ **5a128134** (base: 30d94d4e;
  depends on IMPL-0013's external SCK edge input).
- files: `src/devices/cpu/sh/sh7604.cpp:987-998` (pending TX start),
  `:1006-1068` (SCK edges), `:1088-1110` (rate/start handling),
  `src/devices/cpu/sh/sh7604.h:91,205` (comments),
  `saturn_pending/impl_checks/check_sh7604_sync_tx.py`. Existing SSR,
  async TX and sync RX mocks gain declarations only; no existing expected
  value or validator asset is changed.
- contract: in C/A=1, CKE1=1 mode, read-qualified TDRE clear loads TSR
  when TE=1 and receive errors are clear. No TxD change happens until a
  falling SCK edge. Eight falling edges emit bits 0..7; CHR/PE/OE/STOP/MP
  do not add framing. At MSB output, pending TDR reloads TSR and raises
  TDRE, or TEND rises and TxD holds that MSB. Rising edges concurrently
  sample the independent receiver when RE=1. Receive errors inhibit
  synchronous transfers; clearing them allows pending data to resume.
  TE=0 cancels queued/current TX and returns TxD to mark. No internal
  timer supplies clocks for this external mode.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.3.4 pp.372-373/Figures 13.14-13.15 (falling-edge output,
  eight-bit format, MSB reload/TEND/hold), pp.375-378/Figures 13.19-13.20
  (error handling and simultaneous TX/RX); section 13.5 p.381 prohibits
  synchronous transfer with receive errors set. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:171-180,193-206` emits synchronous LSB-first
  data at SCE_F and implements LAST_BIT reload/TEND; its status decisions
  occur at SCE_R, unlike this candidate's MSB-output-edge decision from
  p.373. This phase difference requires hardware qualification. Upstream
  MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:626-659` emits data at the falling
  clock phase; it returns TxD high after completion, unlike SH7604's
  explicitly documented MSB hold. That H8 behavior is not adopted.
  Upstream SH7604 still provides no transfer engine to port.
- expected observable: in SMR=0x80/SCR=0x22, queue 0x96 and then 0x69
  through the SSR handshake. Falling edges 1..8 emit 0,1,1,0,1,0,0,1;
  edge 8 reloads TSR and raises TDRE, with TEND=0. Edges 9..16 emit
  1,0,0,1,0,1,1,0; edge 16 sets TEND and TxD stays at 0 even if
  additional idle clocks arrive. No start/parity/stop bit is inserted.
  With RE enabled, RDR updates after the eighth rising edge independently
  of the transmitted value. Tolerance: exact edge/data/status counts;
  physical pin propagation delay is not claimed.
- suggested method: mapped-register fixture plus bound TxD/RxD endpoints
  and an independent SCK driver; queue before MSB and just after MSB,
  drive a distinct simultaneous receive byte, cause RX overrun, then
  acknowledge/restart. Capture actual TXI/TEI/RXI/ERI under both CPU
  engines. Save/load at each half-edge with both TSR and TDR occupied.
- falsifier: TxD changing on a rising edge or before the first falling
  edge, a non-eight-bit frame, dropped/duplicated queued byte, early TEND,
  forced mark instead of MSB hold, corrupted independent RX, transmission
  through a latched receive error, or extra output after TE=0 contradicts
  this candidate. A hardware status edge matching MiSTer's alternate
  phase rather than the primary-text interpretation falsifies that edge.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 65536 synchronous three-frame TX cases; 4096 half-edge state-copy replays
  method-level, unvalidated: full duplex, MSB hold/reload, error recovery and TE cancellation exercised
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_sync_tx.py`.
  Same script with pre-change `30d94d4e` source copy exits 1:
  `line 185: d.m_ssr==0x80 && d.wire.empty()`.
  Sync RX, SSR, async TX-chain, RX-error, MP and RX-phase scripts rerun
  with unchanged expected values: exit 0. Extracted checks use UBSan.
  Full `sh7604.cpp` TU syntax with
  `-std=c++20 -Wall -Werror -Wno-sign-compare` and session includes:
  exit 0, no diagnostics; reorder warnings enabled. `git diff --check`:
  exit 0. No full build or native runtime run.
- state: UNVALIDATED
- not covered / known doubts: physical SCK setup/hold and status-edge
  phase, native interrupt delivery and save-manager replay remain open.
  Mid-frame injected receive-error recovery beyond natural byte-boundary
  overrun is not hardware-qualified. Existing saved TX index/TSR/active
  fields are reused; no new save field in this commit (IMPL-0013 changed
  layout). Internal synchronous clock generation, external-clock async,
  SCI DMA, and actual cable/modem/peer devices remain absent. Inventory
  updated separately to avoid continuing to describe all sync operation
  as absent; this is not optional-device acceptance.


### IMPL-0015 — CPU-03/IO-02 — internal synchronous SCI clock output

- branch/commit: `arena/01a0b897-mame` @ **01374a7d** (base: a64e7847;
  builds on IMPL-0013/0014's synchronous edge/transfer semantics).
- files: `src/devices/cpu/sh/sh7604.cpp:42,89-90,127-128,258-265`
  (callback/timer/save/reset), `:920-961,997-1012` (register triggers),
  `:1031-1083` (shared edge engine), `:1085-1170` (clock/start control),
  `src/devices/cpu/sh/sh7604.h:37,91-93,220-229` (API/state),
  `saturn_pending/impl_checks/check_sh7604_internal_sync.py`.
- contract: C/A=1 and CKE1=0 generate SCK on `sck_wr_callback()`;
  CKE0 is ignored in synchronous mode. With BRR=N and CKS=n the bit
  period is (N+1)*2^(4+2n) CPU phi ticks, divided into low/high halves.
  SCK idles high, emits eight pulses per transmitted/received character,
  and preserves the final rising edge after TX has raised TEND at MSB
  output. Queued TX characters continue without an inserted idle pulse.
  Receive-only RE=1 starts the shared clock; full duplex waits for TX
  data and completes its paired RX character. An overrun stops clocks
  high; acknowledging errors permits pending work to restart. Disabling
  both TE/RE cancels the clock. Interrupt-enable-only writes do not
  restart an active half-period. External pin transitions do not clock
  the internal-mode engine.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.2.6 pp.341-342 (CKE table), section 13.2.8 p.349 Table
  13.4/formula, section 13.3.4 pp.372-378/Figures 13.14-13.20 (eight
  clocks, high idle, receive-only procedure, simultaneous transfer),
  section 13.5 p.381 (error inhibition). SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
  Citation clarification for IMPL-0013: the CKE table is in section
  13.2.6 p.342; **Table 13.9** is the SMR format table on p.353,
  not that clock-selection table.
- cross-checks: MAME upstream pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:132-136,457-489,517-535,702,626-637`
  supplies a related implementation of receive-only restart, shared-clock
  duplex start and alternating SCK. MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:83-103,347` corroborates BRR/CKS division and
  high idle but gates SCKO with TX_RUN; its receiver-only coverage is not
  a corroboration of the primary receive procedure. No reference code
  imported. Upstream SH7604 still has no clock engine to port.
- expected observable: for N=1,n=0, SCK low/high widths are each 16 phi
  ticks (bit period 32). One TX byte emits exactly 8 falling plus 8
  rising edges, with data bit0..7 on falling edges and receive samples
  on rising edges. The final low half-period is not discarded at TEND.
  Two queued bytes emit 16 pulses; without further work SCK stays high.
  Receive-only mode with unread first RDR emits a second byte's clocks,
  then sets ORER, retains old RDR and stops high. Tolerance: exact pulse
  count and phi-tick periods in the model; native attotime rounding may
  accumulate one attosecond per half-period. Absolute phase from the
  initiating register write is explicitly outside the hardware claim.
- suggested method: linked two-device fixture connects internal master's
  SCK output to external slave's `sck_w`, cross-connects TxD/RxD and
  drives real mapped registers; also independent receive-only data.
  Capture SCK/TxD and status/IRQ edge times, BRR/CKS changes while
  disabled, CKE0 equivalence, queueing at MSB, RX overrun/recovery and
  disabling during a low half-period. Save/load with the final rising
  edge pending and with both TSR/TDR occupied. Use legal rates/formats.
- falsifier: incorrect pulse width/count, SCK stopping low or dropping
  the last rising edge, RX-only not clocking, TX/RX clocks diverging,
  an extra pulse between queued bytes, external input advancing internal
  mode, or interrupt-enable writes stretching the current half-period
  contradicts this candidate. A hardware trace requiring a different
  receive-only/full-duplex start rule would reject that gating model.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 8192 rate/clock-select/TX cases; 3072 two-device duplex streams; 4096 half-edge state-copy replays
  method-level, unvalidated: receive-only, eight-pulse termination, error recovery, cancellation and no-retime controls exercised
  method-level, unvalidated: clock level/running reset/save registration present
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_internal_sync.py`.
  Extracts actual clock, edge, register and transfer methods, uses UBSan
  and a virtual phi clock. Seven prior focused SCI scripts rerun with
  unchanged expected values: exit 0. Their mock declarations/extraction
  lists were adapted to the shared helper; they stub internal-clock
  scheduling and do not test that behavior. This new script extracts
  the real helper instead. TU syntax with
  `-std=c++20 -Wall -Werror -Wno-sign-compare` and session includes:
  exit 0, no diagnostics; reorder enabled. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: first SCK edge is scheduled one half-bit
  after an idle engine starts; divider reset/free-running phase versus
  the CPU clock needs a trace and is not a silicon timing assertion.
  Table 13.4 marks the highest-rate N=0,n=0 setting as unsuitable for
  continuous transmission/reception; the broad method-level sweep also
  includes that setting, but those continuous-stream cases are software
  consistency probes, not legal hardware expectations. No workaround or
  invented silicon failure mode is added for prohibited operation.
  Mid-transfer BRR/SMR/CKE changes, CPU clock changes, module standby,
  native IRQ/save-manager behavior and physical pin delay remain open.
  New fields `m_sci_sck_out` and `m_sci_clock_running` are saved/reset
  with the implementation; the new emu_timer owns its scheduled event.
  Old save files are incompatible. Externally clocked asynchronous mode,
  asynchronous SCK output, SCI DMA and configured modem/cable/peer devices
  remain absent. Frozen accepted paths and validator assets are untouched.


### IMPL-0016 — CPU-03/IO-02 — externally clocked asynchronous SCI receive

- branch/commit: `arena/01a0b897-mame` @ **520b3f8a** (base: 60bc961f).
- files: `src/devices/cpu/sh/sh7604.cpp:939-951` (RE initialization),
  `:1018-1033` (SCK dispatch), `:1150-1162` (rate recalculation),
  `:1255-1356` (RX timer guards), `src/devices/cpu/sh/sh7604.h:88`
  (scope comment), `saturn_pending/impl_checks/check_sh7604_external_async_rx.py`.
  Existing synchronous fixture mocks gain only an unused async callback
  stub; their expected values are unchanged.
- contract: with C/A=0, CKE1=1 and RE=1, rising SCK edges provide the
  receiver's 16x base-clock pulses. Falling edges and repeated levels do
  not advance the sampler. Start validation is eight rising pulses after
  detection; subsequent samples are sixteen rising pulses apart, using
  the existing framing/MP/error engine. BRR/CKS do not pace external RX.
  No RX timer is armed on enable, error stall, completion or recalculation
  in external mode. RE=0 abandons partial input; a legal disable/change/
  re-enable sequence restores internal-clock sampling when CKE1=0.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.2.6 pp.341-342 CKE table (both CKE=2/3 select external
  input), section 13.3.1 p.352 (baud generator unused for external clock),
  section 13.3.2 pp.354,356 (16x external input), section 13.5 pp.381-382
  / Figure 13.21 (rising-eighth-pulse sample). SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:391-410,705-709` routes an external
  clock into the async sampler and uses a 16-phase counter. Its external
  edge dispatch/counter interpretation differs (both changed levels call
  the sampler), so it is not evidence of the same physical-edge contract.
  MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:138-139` selects internal SCE for async mode
  even with external CKE; that omission is not adopted. The primary
  clock-frequency/sampling descriptions govern this candidate.
- expected observable: for a complete external 8N1 frame, RDRF/receive
  completion occurs at rising pulse 152 after the pulse detecting start
  (start sample at 8, data bit0 at 24, bit7 at 136). BRR=0 vs 255,
  all CKS values and CKE=2 vs 3 give identical pulse-indexed results.
  No positive RX timer scheduling occurs. Exact edge counts/register
  bytes, tolerance zero; physical setup/hold and synchronizer delay in
  CPU cycles are outside this contract.
- suggested method: drive independent 16x SCK and RxD pins through a
  linked per-device fixture; read mapped SCI registers before/after stop
  sampling. Include 7/8-bit data, parity/MP, false starts, both stops,
  combined errors, repeated pin levels and receive-disable/restart.
  Compare native save/load at start detection, mid-bit and pending stop.
- falsifier: reception driven by BRR/internal timers in external mode,
  a falling/repeated SCK level advancing the sampler, wrong 16x sample
  count, missing receive completion, a partial frame surviving RE=0,
  or lost/duplicated samples on save/load contradicts this candidate.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 32768 external-clock async format/data frames; 2560 phase state-copy replays
  method-level, unvalidated: BRR independence, edge filtering, no RX timer arms, errors and clock-mode controls exercised
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_external_async_rx.py`.
  Same script with pre-change `60bc961f` source exits 1:
  `line 281: d.m_sci_rx_enabled && d.timer.arms==0`.
  Eight earlier focused SCI checks rerun with unchanged expectations:
  exit 0. Extracted checks use UBSan. Full `sh7604.cpp` TU syntax with
  `-std=c++20 -Wall -Werror -Wno-sign-compare` and session includes:
  exit 0, no diagnostics; reorder enabled. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: no native execution, physical timing or
  save-manager run. Existing saved SCK/phase/shift/error state is reused;
  no new field/save-layout change. The manual warns not to stop the
  external clock during operation, so deterministic pin-step/state-copy
  checks are not a hardware pause/resume claim. External-clock async TX
  is not implemented in this commit: its older internal-timer path is
  not a supported external-mode transmitter. Async SCK output, SCI DMA
  and actual peripheral wiring also remain absent.


### IMPL-0017 — CPU-03/IO-02 — externally clocked asynchronous SCI transmit

- branch/commit: `arena/01a0b897-mame` @ **ac368a39** (base: 5ff90af5;
  uses IMPL-0016's asynchronous SCK routing for simultaneous RX).
- files: `src/devices/cpu/sh/sh7604.cpp` (TX divider save/reset, SCR
  cancellation, `sck_w`, `sci_recalc_rates`, `sci_transmit_start`,
  `sci_tx_tick`), `src/devices/cpu/sh/sh7604.h` (`m_sci_tx_phase`),
  `saturn_pending/impl_checks/check_sh7604_external_async_tx.py`.
  Existing mocks gain divider state/unused callback declarations only;
  no existing expected values or validator assets changed.
- contract: C/A=0 and CKE1=1 pace TX with the external 16x input clock.
  Once a read-qualified TDRE clear starts an async frame, each group of
  sixteen rising SCK edges advances one transmitted bit. Falling or
  repeated levels do not advance the divider. Preserve existing data,
  parity/MP, stop-bit, queued-frame and TEND semantics; BRR/CKS do not
  control bit duration in external mode. No internal TX timer is armed
  by start, continuation or rate recalculation. TE=0 discards partial
  TX and clears the divider. Async receive errors do not stop transmit.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.2.6 pp.340-342 (TE and CKE), section 13.3.1 p.352
  (external source does not use baud generator), section 13.3.2
  pp.354-360, especially p.356 (external clock frequency 16 times bit
  rate) and p.359/Figure 13.6 (frame/queue semantics). Section 13.5
  p.381 limits receive-error TX inhibition to synchronous mode.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:391-410,538-547` has external-clock
  TX/RX dispatch and a 16-phase TX counter. Its both-level edge dispatch
  is not evidence of the same physical input-clock interpretation;
  this candidate follows the SH7604 16x-frequency contract. MiSTer
  pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:138-139` still selects internal SCE for async
  mode, so that missing external behavior is not adopted. No external
  reference code imported. Initial external-clock phase remains open.
- expected observable: in external-clock 8N1 mode, start=0 at frame
  initiation; data bit0 after 16 input rising edges, bit7 after 128,
  stop=1 after 144; a queued frame's start after 160. Every complete
  stop interval lasts sixteen input periods. BRR=0 vs 255, all CKS
  settings and CKE=2 vs 3 give identical pulse-counted frames. With no
  queued byte, further SCK edges cause no new TxD frame. Tolerance:
  exact pulse counts/bit values within this model; absolute start-bit
  phase relative to the free-running external input is not qualified.
- suggested method: linked independent external-clock driver plus two
  SH7604 devices exchanging distinct data. Use legal asynchronous
  formats and continuous SCK; compare mapped SSR with pin traces.
  Include queued bytes before/after the final stop decision, TIE/TEIE
  writes, BRR variation, receive overruns while TX continues and TE
  cancellation. Save/load at every divider phase with TDR/TSR occupied.
- falsifier: an internal bit timer advancing external TX, BRR-dependent
  pacing, non-sixteen-pulse bit duration, falling/repeated levels shifting
  data, missing queued frames, shortened stop interval, RX error halting
  async TX, or duplicate data after restoring a partial divider phase
  contradicts this candidate. A hardware trace differing in start/divider
  alignment would require revising that explicitly provisional phase.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 8192 external asynchronous three-frame streams; 256 two-device duplex cases; 4096 divider state-copy replays
  method-level, unvalidated: no internal timers, BRR independence, late queue, RX-overrun isolation and TE cancellation exercised
  method-level, unvalidated: external TX divider reset/save registration present
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_external_async_tx.py`.
  Same script on pre-change `5ff90af5` source exits 1:
  `line 482: tx.due==attotime::never.value && rx.due==attotime::never.value && clock_timer.due==attotime::never.value`.
  Nine prior focused SCI scripts rerun with unchanged expectations:
  exit 0. Extracted checks use UBSan. Full `sh7604.cpp` TU syntax with
  `-std=c++20 -Wall -Werror -Wno-sign-compare` and session includes:
  exit 0, no diagnostics; reorder enabled. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: the candidate retains immediate start-bit
  output on TSR loading and counts sixteen rising edges to the next bit.
  Exact synchronization from a register write to the free-running SCK
  phase needs a trace; this is not a physical edge-to-output latency
  claim. Stopping the external clock during operation is prohibited by
  p.356; deterministic state-copy checks do not qualify hardware pauses.
  No native CPU/IRQ/save-manager execution. New `m_sci_tx_phase` is
  saved/reset in this commit; old save files are incompatible. Async SCK
  output, SCI DMA, standby/CPU-clock transitions, physical margins and
  real modem/cable/peer configuration remain open. Frozen accepted work
  and validator assets are untouched.


### IMPL-0018 — CPU-03/IO-02 — asynchronous SCK output and TX phase

- branch/commit: `arena/01a0b897-mame` @ **a515c1a4** (base: 1777a8b2).
- files: `src/devices/cpu/sh/sh7604.cpp` (`sci_update_clock`,
  `sci_clock_tick`, `sci_recalc_rates`, `sci_transmit_start`,
  `sci_tx_tick` and renamed helper callers),
  `src/devices/cpu/sh/sh7604.h` (helper names/state comments),
  `saturn_pending/impl_checks/check_sh7604_async_clock_out.py`.
  Six prior extraction/mock files follow the helper renames only;
  no existing expected values or validator assets changed.
- contract: C/A=0 and CKE=01 output a continuous SCK at the programmed
  bit rate, even with TE and RE clear. Async receive errors and TE
  cancellation do not stop that clock. TX in this mode waits for a
  falling SCK edge to emit its start bit and changes each subsequent
  bit on falling edges, placing rising edges at bit centers. The
  final stop interval remains a full bit; a queued next character
  starts on the same falling edge that ends that interval. There is
  no competing async TX timer in clock-output mode. CKE=00 internal
  TX and CKE=10/11 external TX retain their prior pacing paths.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 13.2.6 pp.341-342 CKE selection, section 13.3.2 p.356 and
  Figure 13.3 (output frequency equals bit rate; rising edge at center
  of transmit data), p.356 initialization step 3 (clock output starts
  on SCR configuration with TE/RE still zero), p.357 initialization
  step 4 (wait one bit before enabling transfers), p.359/Figure 13.6
  for continuous frames. Bit period follows Table 13.3 pp.347-348 and
  formula p.349. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/h8/h8_sci.cpp:538-547,548-566` emits async data
  at clock phase zero and raises SCK at phase eight, corroborating
  center alignment. Its clock_start/clock_stop gating (`:457-514`)
  is tied to transfers and is not evidence for the SH7604's documented
  clock-only initialization. MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/SCI.sv:105-139,193-226,347` generates the baud clock
  and transmits on SCE_F, but SCKO is gated by TX_RUN; that idle-clock
  difference is not adopted. Primary initialization text governs it.
  No reference code imported.
- expected observable: for BRR=0, CKS=0 the bit period is 128 CPU phi
  ticks and SCK toggles every 64 ticks, without enabling TX/RX. After
  enabling TX and queuing a byte, start/data/parity/stop transitions
  occur only at falling SCK edges; each corresponding rising edge
  follows 64 ticks later. An 8N1 frame occupies ten full output-clock
  periods; back-to-back frames add no idle period. Clock output remains
  active after TEND or TE=0 until its mode is deselected. Exact bit
  values/pulse counts; period tolerance is one accumulated attosecond
  rounding per half-cycle in a native attotime probe. Initial divider
  phase relative to the SCR write is not a silicon timing assertion.
- suggested method: initialize SMR/BRR and CKE=01 with TE/RE clear;
  observe free-running SCK before enabling TX. Queue at several phases
  of an already-running clock and capture TxD/SCK together. Include
  all frame formats, pending next bytes, late stop-interval writes,
  independent/looped-back RX, error flags, interrupt-enable writes,
  TE cancellation and disabling clock output. Save/load while a start
  bit waits for a falling edge and between consecutive frames.
- falsifier: no clock while TE/RE are zero, 16x rather than baud-rate
  output, a rising edge not centered in an ordinary transmitted bit,
  duplicate data from a second TX timer, truncated stop or extra idle
  bit between queued frames, or TE/receive-error gating the async clock
  contradicts this candidate. Silicon requiring a different launch
  phase after register writes would revise the provisional first edge.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 1024 clock-divider cases; 16384 phase-aligned three-frame streams; 512 RX loopbacks; 4096 state-copy replays
  method-level, unvalidated: idle clock, bit-center rising edges, no competing TX timer, continuous queueing and TE/error independence exercised
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_async_clock_out.py`.
  Same new script with pre-change `1777a8b2` source, normalizing helper
  names only, exits 1:
  `line 543: d.m_sci_clock_running && d.sci_bit_period().value==bit`.
  Ten preceding focused SCI scripts rerun with unchanged expected
  values: exit 0. Extracted checks use UBSan. Full `sh7604.cpp` syntax
  with `-std=c++20 -Wall -Werror -Wno-sign-compare` and session includes:
  exit 0, no diagnostics; reorder enabled. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: no native CPU/IRQ/save-manager or hardware
  capture. Exact initial baud-divider phase and simultaneous CPU-write/
  SCK-edge ordering remain open. Clock-source/BRR changes mid-transfer
  and clock-pin GPIO behavior outside SCI output mode are not qualified.
  Output SCK is **1x** baud; external asynchronous SCK input is **16x**
  baud, so directly wiring these two pins is not a valid async clock
  link. No actual cable/modem device is claimed. Existing saved clock
  level/running state, timer and TX bit index are reused, but bit index
  zero now represents an async pending start and the timer callback was
  renamed. Do not reuse pre-change active-SCI saves across this change;
  cross-version save compatibility is not established. SCI DMA, standby,
  CPU clock transitions and physical pin margins remain open. Frozen
  accepted paths and validator assets remain untouched.

#### IMPL-0018 locator/provenance addendum

- Production locators at `a515c1a4`: `src/devices/cpu/sh/sh7604.cpp:89`
  (timer callback registration), `:1101-1162` (shared clock),
  `:1176-1211` (rate selection and deferred launch), `:1213-1296`
  (async bit output/chaining); `src/devices/cpu/sh/sh7604.h:90-95`
  (helper declarations). Method fixture:
  `saturn_pending/impl_checks/check_sh7604_async_clock_out.py:1-139`.
- Fork history through base `1777a8b2` contains the existing internal
  synchronous clock candidate `01374a7d` and external async candidates
  `520b3f8a`/`ac368a39`; this change extends their shared inline engine,
  rather than enabling the unused standalone SCI device or importing
  another implementation. Upstream pinned `398bba74ed7997d29c2316316da230f6d85fda0d`
  `src/devices/cpu/sh/sh7604.cpp:872-879` has register stubs, not an
  asynchronous clock-output engine to adopt. The H8 phase relation and
  MiSTer TX_RUN gate cited above were inspected directly; neither
  establishes native SH7604 startup phase or save-state behavior.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0019 | CPU-03/IO-02 | 20c1e822 | UNVALIDATED | SBYCR.MSTP0 initializes SCI registers/engine without clearing its INTC vectors; reset releases module standby |

### IMPL-0019 — CPU-03/IO-02 — SCI module-stop initialization

- branch/commit: `arena/01a0b897-mame` @ **20c1e822** (base: c101ca5a).
- files: `src/devices/cpu/sh/sh7604.cpp:237-239` (device-reset release),
  `:865-898` (shared SCI reset), `:1869-1896` (SBYCR byte-write handler);
  `src/devices/cpu/sh/sh7604.h:89` (helper declaration);
  `saturn_pending/impl_checks/check_sh7604_module_stop.py:1-180`.
- contract: a byte write taking SBYCR.MSTP0 from zero to one initializes
  the SCI registers and internal transfer bookkeeping, cancels its three
  timers, and clears its interrupt enables/requests through IRQ
  recalculation. SCI vectors in VCRA/VCRB and IPRB remain unchanged.
  Clearing MSTP0 leaves the SCI in its initial state, not a paused-frame
  state: software must initialize it again. Device reset clears SBYCR
  and uses the same SCI initialization. No new saved state is introduced;
  existing `m_sbycr` save registration and all SCI registrations remain.
  Existing FMR byte/word routing is unchanged. The scope is legal,
  halted-module entry and release, not whole-chip standby or sleep.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 14.2.1 pp.387-389 (SBYCR reset value H'00; MSTP0 initializes
  SCI but preserves its INTC vectors; clearing it starts from initial
  state); sections 14.5.1/14.5.2 p.393 (module-stop entry and release by
  bit clear or power/manual reset; no SCI reads/writes while stopped;
  do not switch a running module to standby). Section 13.2/Table 13.2
  p.335 and register descriptions pp.335-345 give reset values. Table
  A.1 p.564 gives reset TXD=high and SCK=high impedance; **the latter is
  not represented by the current one-bit callbacks**. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_power.hpp:8-26` documents
  MSTP0 as halt-and-reset, while
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:379,1451` resets/stores SBYCR
  without implementing SCI module reset. This is a register-description
  cross-check, not an independent functioning engine. Blobs:
  `e8526b57f8f8ecad0282e11d3d53d8be1c1d642f` and
  `9746b438b8a71de63ff65cd2d4325bc582a5114b`.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1328-1345`, merely stores/logs module
  stop. Inspected fork history through `c101ca5a`: the existing SCI
  reset was inline in `device_reset`; SBYCR still had that upstream
  store/log path. Reused the fork's initialization verbatim except for
  the clarified SCK callback comment; no outside code imported.
- expected observable: after legal stop/release, read SMR=H'00,
  BRR=H'FF, SCR=H'00, TDR=H'FF, SSR=H'84, RDR=H'00. VCRA/VCRB/IPRB
  retain their pre-stop values. With no new initialization, advancing
  simulated time or providing external SCK edges produces no new SCI
  transmission/reception/interrupt request. Device reset yields
  SBYCR=H'00 even if MSTP0 was previously set. Register comparisons and
  event counts are exact, with no time tolerance or silicon propagation
  latency asserted. TxD callback reports logical high; SCK logical idle
  is not an electrical high-impedance measurement.
- suggested method: finish a transfer, disable TX/RX and deselect clock
  output, leaving unread RDR/errors and a prior SSR-read qualification;
  record vectors/priority, set MSTP0 via H'FFFFFE91 byte access, advance
  time and external SCK, then clear MSTP0 before reading SCI registers.
  Reinitialize and exchange a fresh byte in each internal/external
  async/sync mode. Repeat with a saved stopped-state snapshot and with
  manual/power reset. Confirm FMR accesses and unrelated SBYCR bits do
  not trigger SCI reset. Use a native peer/IRQ probe for delivery and a
  pin-direction-capable model for electrical reset claims.
- falsifier: residual RDR/error flags after legal release, changed
  VCRA/VCRB/IPRB, stale SSR-read qualification acknowledging a fresh
  flag, a pre-stop timer/character resuming without reinitialization,
  or MSTP0 remaining set after reset contradicts this candidate.
  A reset caused solely by FMR access or another module-stop bit also
  contradicts its scope. Forbidden SCI access while stopped or active
  module entry is not a hardware acceptance scenario.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 16384 halted-entry cases; 194 access-width/other-bit controls; 2048 fresh transfers and 2048 state-copy replays; 128 reset-release cases
  method-level, unvalidated: 384 forbidden-active-entry cleanup probes (software robustness only)
  method-level, unvalidated: register/read-latch reset, vector preservation, timer cancellation and no stale resume exercised; no native IRQ/save or high-impedance model
  method-level, unvalidated: existing SBYCR save registration retained; no new state fields
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_module_stop.py`.
  Same script against pre-change `c101ca5a` source, without rewriting
  method bodies, exits 1 at the reset-register assertion:
  `line 655: m_smr==0 && m_brr==0xff && m_scr==0 && m_tdr==0xff && m_ssr==0x84 && m_rdr==0`.
  All eleven preceding SCI scripts rerun unchanged: exit 0. Method
  binaries use UBSan. Full `sh7604.cpp` syntax check with session include
  paths and `-std=c++20 -Wall -Werror -Wno-sign-compare`: exit 0,
  no diagnostics, reorder enabled. `git diff --check`: exit 0.
- state: UNVALIDATED
- not covered / known doubts: native scheduler, CPU reset, IRQ arbitration,
  and save-manager behavior are not qualified by mock method checks.
  State-copy replay is not an on-disk save test. No new save fields or
  timer callbacks were added; cross-version snapshot compatibility is
  not established. Existing boolean TxD/SCK callbacks cannot represent
  SCK high impedance or pin contention; no electrical reset completion
  claim. Prohibited reads/writes during module stop remain unsupported
  (not newly defined as ignored writes or specified read values).
  Active-entry cleanup probes only constrain deterministic software
  cleanup and do not invent a hardware abort protocol. SBY/HIZ, MSTP1-4,
  reserved-bit access semantics, and whole-chip sleep/standby are not
  implemented here. SCI DMA request/ack routing and actual external
  peripherals remain absent. Frozen DMA, delay-slot, sound and game
  paths and validator assets/expectations are untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0020 | CPU-03 | 85306c62 | UNVALIDATED | FRT reset/MSTP1 initialize documented registers; module stop suppresses counting/capture and release excludes stopped time |

### IMPL-0020 — CPU-03 — FRT reset and module-standby lifecycle

- branch/commit: `arena/01a0b897-mame` @ **85306c62** (base: 235c9f52).
- files: `src/devices/cpu/sh/sh7604.cpp:210-218` (reset entry),
  `:398-449` (FRT reset, resync and activation guards), `:480-503`
  (timer callback guard), `:1890-1934` (MSTP1 entry/release),
  `:2044-2052` (input-capture gate);
  `src/devices/cpu/sh/sh7604.h:318` (helper declaration);
  `saturn_pending/impl_checks/check_sh7604_frt_stop.py:1-185`.
  The existing SCI module-stop method fixture gained mock declarations
  for the shared SBYCR/reset handler's FRT calls, not changed expectations.
- contract: device reset and SBYCR.MSTP1 entry initialize TIER=H'01,
  FTCSR=H'00, TCR=H'00, TOCR=H'E0, FRC/ICR=H'0000 and OCRA/OCRB=H'FFFF.
  MSTP1 stops the timer and suppresses counting and FTI capture. Incoming
  FTI levels are tracked without generating capture events while stopped.
  Module stop preserves FRT INTC vectors and priority. Clearing MSTP1
  resumes from the initialized counter, with a fresh CPU-cycle epoch so
  the stopped interval is not charged to FRC. Reset clears SBYCR and
  activates the initialized free-running timer. Other SBYCR/FMR access
  routing and the SCI MSTP0 behavior remain separate.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  Table 11.2 p.297 (complete initial register image), section 11.2
  pp.298-303 (register initialization on reset/module standby, input
  capture edge, default phi/8 counter clock), section 14.2.1 pp.387-388
  (SBYCR reset value; MSTP1 resets FRT but preserves its INTC vector),
  sections 14.5.1/14.5.2 p.393 (module stop/release and no register
  accesses while stopped; halt the module or disable interrupts before
  effecting a stop). SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:23-35,101-107,118-126,299-302,340-344`
  resets the FRT counter/capture/compare and control fields consistently
  with that initial image; blob `22868cc7792ede743d834dca5624c6cb5102f04e`.
  `libs/ymir-core/include/ymir/hw/sh2/sh2_power.hpp:17` describes MSTP1
  as halt-and-reset, but its `src/ymir/hw/sh2/sh2.cpp:1451` only stores
  SBYCR; no independent running MSTP1 implementation is claimed.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-189,367-383,1328-1345,1458-1483`
  has zero compare reset values and no stop/capture gating. Inspected
  fork history and base `235c9f52`: it inherits those FRT paths, with
  IMPL-0019 adding SCI-only module reset. This extends the inline FRT
  engine; no reference implementation was imported.
- expected observable: immediately on reset or after legal MSTP1 release,
  the register image above is exact. No FTI pulse during the stopped
  interval changes ICR/ICF or raises an FRT interrupt. With default TCR
  after release, FRC advances one count per eight CPU phi cycles and does
  not include time spent stopped. Without reprogramming or captures,
  compare A/B flag at count H'FFFF and overflow at the following count
  H'0000; default TIER disables their interrupts. The method model
  schedules these at release+524280 and +524288 phi ticks respectively.
  Absolute first-divider phase is provisional: hardware comparison must
  allow up to one prescaler period (8 phi ticks) relative to the register
  write, then require the 8-tick spacing and exact counts/registers.
- suggested method: disable timer interrupts, configure nondefault FRC,
  compares/control and leave prior capture/status flags. Record vectors
  and priority. Set MSTP1 via the SBYCR byte address, advance time and
  send FTI pulses of at least six phi ticks (section 11.2.3), then clear
  MSTP1 before reading timer registers. Check initial values, subsequent
  phi/8 counting, compare/overflow ordering and new capture operation.
  Repeat at nonzero CPU-cycle epochs, through reset and save/load during
  stop. Include FMR byte/word and other-module bit controls. Native
  validation should also exercise DCC input-capture handshakes with the
  FRT running versus intentionally module-stopped on both SH-2s.
- falsifier: stale control/compare/capture values after reset/release,
  counter accumulation or ICF from a stopped interval, changed interrupt
  vectors/priority on MSTP1, a spurious capture from a repeated held
  level at release, or failure to resume the default-rate counter
  contradicts this candidate. First-event phase differing by more than
  one prescaler period would also reject its proposed timing bound.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 4096 MSTP1 entry/release cases; 4096 state-copy replays; 256 reset cases; 194 access-width/other-bit controls; 256 input-capture cases
  method-level, unvalidated: initial register image, stopped-time exclusion, compare/overflow restart, vector preservation and capture gating exercised
  method-level, unvalidated: existing FRT/SBYCR save registrations retained; no new state fields
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_frt_stop.py`.
  Same new script against pre-change `235c9f52`, with method bodies
  unchanged, exits 1:
  `line 311: m_tier==1 && m_ftcsr==0 && m_frc_tcr==0 && m_tocr==0xe0`.
  All twelve preceding SCI scripts rerun with unchanged expectations:
  exit 0. Extracted method binaries use UBSan. Full `sh7604.cpp` syntax
  check with session include paths and
  `-std=c++20 -Wall -Werror -Wno-sign-compare`: exit 0, no diagnostics,
  reorder enabled. `git diff --check`: exit 0. No full build run.
- state: UNVALIDATED
- not covered / known doubts: the method clock is CPU cycles, not a
  native scheduler/DRC/interpreter timing qualification. Input synchronizer
  latency, first-divider phase, CPU halt/clock transitions, native IRQ
  arbitration/delivery, reset integration and on-disk save replay remain
  open. All affected fields were already saved; no new fields or timer
  callback identities were added, but cross-version save compatibility
  is not asserted. External FTCI clock input, FTOA/FTOB output pins,
  TEMP byte-access protocol, FTCSR read-before-clear qualification and
  the existing normal-operation prescaler remainder behavior are not
  completed by this change. Whole-chip sleep/standby and MSTP2-4 remain
  outside scope. No behavior is specified for prohibited register accesses
  while module-stopped. The general DMA request/grant/ack engine and
  frozen delay-slot, sound and game paths were not edited; native game
  regression acceptance remains with the validation agent. IO-02's
  external-device inventory is unchanged: this does not add a peripheral
  peer or imply serial DMA support.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0021 | CPU-03 | 7c6b9dfe | UNVALIDATED | FTCSR event flags require read-one/write-zero acknowledgement; debugger reads do not arm clears |

### IMPL-0021 — CPU-03 — FRT status read-qualified acknowledgements

- branch/commit: `arena/01a0b897-mame` @ **7c6b9dfe** (base: ae5ece72).
- files: `src/devices/cpu/sh/sh7604.cpp:43,134,405` (read-history
  initialization/save/reset), `:1463-1488` (FTCSR read/write handlers);
  `src/devices/cpu/sh/sh7604.h:234` (saved byte);
  `saturn_pending/impl_checks/check_sh7604_ftcsr.py:1-157`.
  The existing FRT module-stop fixture only gained mock declarations
  for the new field/debugger accessor and a clarified save-audit output
  label; its expected values and scenarios were not changed.
- contract: FTCSR ICF/OCFA/OCFB/OVF (bits 7,3,2,1) are cleared only by
  writing zero after a CPU status read observed that flag set. Writing
  one cannot set a flag. Clearing a flag consumes its qualification, so
  a later event needs a fresh status read. CCLRA bit 0 remains ordinary
  read/write; reserved bits 6-4 remain zero. Debugger inspection returns
  the status without changing read history or invoking the legacy
  CPU-read callback. Reset/MSTP1 entry clears read history together with
  FTCSR. Counter resynchronization, event scheduling and IRQ refresh
  remain in the write path.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 11.2.5 pp.300-302, especially p.301's per-flag clear conditions
  (read one, then write zero), flag set conditions and reserved-bit rule;
  p.302 CCLRA read/write behavior. Table 11.2 p.297 and section 11.2.5
  p.300 specify the reset/module-standby image. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:153-170,173-202`
  maintains a read mask, distinguishes peek reads, and qualifies/consumes
  each flag's clear with that mask. Blob
  `22868cc7792ede743d834dca5624c6cb5102f04e`. The implementation here
  keeps only the four flags in its mask; it does not import Ymir's
  debugger-poke interface. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:899-916`, has no read qualification and
  invokes the read callback unconditionally. Fork history through base
  `ae5ece72` retains those handlers; IMPL-0020 supplies the shared reset
  entry now extended for the read-history byte. No reference code
  imported. An in-tree search for `set_ftcsr_read_callback` found only
  its declaration, not a configured consumer.
- expected observable: after a capture sets ICF=1, writing FTCSR=0
  without a qualifying read leaves ICF=1. A debugger status inspection
  followed by that write also leaves ICF=1. A CPU read followed by the
  write clears ICF; a subsequent capture remains pending until another
  CPU read/write-zero sequence. The same rule applies independently
  to OCFA, OCFB and OVF. Selectively clearing one observed flag preserves
  the others and their unconsumed qualifications. CCLRA changes without
  any read prerequisite. All observations are exact bits/callback counts;
  this change asserts no additional latency or hardware timing tolerance.
- suggested method: generate capture, compare and overflow flags; attempt
  unread and read-qualified writes, including a flag first raised after
  a read of zero. Exercise selective acknowledgements while multiple
  sources are pending. Insert debugger status inspection before a clear
  and compare with a CPU status read. Save/load between the read and
  write, and between acknowledgement and the next event. Repeat after
  device reset and legal MSTP1 entry/release. Check native IRQ delivery
  separately; the method harness only observes recalculation/state.
- falsifier: an unread event flag clearing, debugger inspection arming a
  clear, writing one creating a flag, a previously consumed qualification
  clearing a new event, one flag's acknowledgement consuming another's,
  or stale read history surviving reset/module stop contradicts this
  candidate. A save/load that loses an outstanding qualification also
  contradicts its state contract.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 16384 status/read-history/write transitions; 16385 state-copy replays; 512 CPU/debugger read cases; 32 reset/module-stop cases
  method-level, unvalidated: real compare/overflow/capture producers, selective clear, consumed acknowledgements, CPU-read callback and reserved-bit mask controls exercised
  method-level, unvalidated: FTCSR read-history constructor/reset/save registration present; save layout changed
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_ftcsr.py`.
  Same script against pre-change `ae5ece72` source, without changing its
  method bodies, exits 1:
  `line 344: d.m_ftcsr==expected && d.m_ftcsr_read==qualified`.
  All thirteen preceding focused SCI/FRT scripts rerun with unchanged
  expected values: exit 0. Extracted binaries use UBSan. Full
  `sh7604.cpp` syntax with session includes and
  `-std=c++20 -Wall -Werror -Wno-sign-compare`: exit 0, no diagnostics,
  reorder enabled. `git diff --check`: exit 0. No full build run.
- state: UNVALIDATED
- not covered / known doubts: **save-state layout break** — new byte
  `m_ftcsr_read` is initialized in the constructor and shared FRT reset
  and registered by `save_item` in this change. Do not assume old saves
  are compatible. State-copy replay is not native save-manager evidence.
  Native CPU/DRC/IRQ/debugger execution and hardware captures remain
  unqualified. Same-cycle event/write ordering, first prescaler phase,
  the existing remainder-loss/scheduling behavior, TEMP byte accesses,
  FTCI input and FTOA/FTOB pins are not repaired by this patch. Direct
  method probes of reserved-bit writes only constrain the stored mask;
  they do not qualify prohibited silicon accesses. Register accesses
  while module-stopped remain outside the contract. The frozen DMA
  acknowledgement, delay-slot, sound and game paths and validator assets
  were not edited. No new external-device availability or completion
  status is claimed; IO-02's inventory remains unchanged.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0022 | CPU-03 | bbdb90a5 | UNVALIDATED | FRT internal-clock counting and event deadlines preserve prescaler phase across polling and non-clock-changing accesses |

### IMPL-0022 — CPU-03 — FRT prescaler remainder preservation

- branch/commit: `arena/01a0b897-mame` @ **bbdb90a5** (base: cbb50769).
- files: `src/devices/cpu/sh/sh7604.cpp:416-434` (counter synchronization),
  `:467-476` (event delay), `:1529-1538` (TCR clock-change handling);
  `src/devices/cpu/sh/sh7604.h:291` (cycle-epoch meaning);
  `saturn_pending/impl_checks/check_sh7604_frt_phase.py:1-165`.
  Existing fixture expectations and validator assets were not edited.
- contract: for a fixed internal CKS selection, FRC advances at phi/8,
  phi/32 or phi/128 regardless of the cadence of software counter reads.
  Counter synchronization consumes only whole divider intervals and
  preserves the remaining fractional interval. Scheduling a pending
  compare/overflow subtracts the already elapsed fraction instead of
  restarting the divider. Writes that leave the clock selection unchanged
  (including IEDG-only TCR writes) and input-capture events preserve the
  running phase. An actual CKS change explicitly establishes the existing
  fresh-interval software convention; its silicon startup phase is not
  newly specified or qualified. This candidate addresses the steady-clock
  remainder-loss item left open in IMPL-0020/0021, not every timer issue.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 11.2.6 p.302 (independent IEDG and CKS fields; internal clock
  selections), section 11.4.1 p.307/Figure 11.4 (one FRC increment per
  divided clock input). This is the basis for a continuous internal
  clock, not a clock whose rate depends on CPU register-read partitioning.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`. No explicit
  clock-selection transition phase is inferred from these passages.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:38-51` counts the
  difference between divided absolute cycle timestamps, preserving phase
  across arbitrary advances. Blob `22868cc7792ede743d834dca5624c6cb5102f04e`.
  Its absolute-cycle phase differs from this fork's reset/release-relative
  epoch, so it supports partition independence, not first-edge alignment.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:367-381,420-428` resets the epoch to
  current cycles on synchronization/activation, discarding a remainder.
  Inspected fork history through `cbb50769`: those arithmetic paths
  remain, with IMPL-0020 adding module-stop guards. No reference code
  imported; existing event selection/flag-setting logic is unchanged.
- expected observable: with phi/8 and an established epoch at cycle zero,
  reads at cycles 9, 18 and 24 return counts 1, 2 and 3, rather than
  allowing the read at 9 to discard one cycle. With OCRA=37, a TIER write
  at cycle 9 leaves the candidate's compare deadline at cycle 296, not
  297. Similarly, TOCR changes, unchanged OCR writes and IEDG-only writes
  retain the existing divider phase. Polled and unpolled instances with
  identical initialization produce identical counts and event times.
  Virtual-cycle comparisons are exact; native measurements should use
  CPU-phi resolution (at most one phi tick observation granularity).
  Absolute reset/clock-change startup phase remains provisional and must
  not be confused with cumulative drift caused by accesses.
- suggested method: run each internal divider with a known count and
  nonzero compare targets. Poll at cadences not divisible by that divider,
  then compare with an otherwise identical unpolled run. At every residual
  phase, write interrupt enables, output-control or IEDG while keeping CKS
  constant, and capture the next compare/overflow timestamp. Include
  counter wraparound and already-latched flags with no timer callback
  scheduled. Save/load at a fractional interval and continue. Exercise
  clock switches separately as software-convention controls; physical
  divider-switch transients need independent hardware evidence.
- falsifier: a counter value or pending-event deadline differing between
  polled and unpolled runs solely because of read cadence, non-clock-
  changing writes delaying the divider, lost fractional time after a
  capture or save/load, or an unsigned far-future delay from an already-due
  compare contradicts this candidate. Silicon showing access-dependent
  prescaler reset would require revising this contract rather than
  silently adjusting fixture expectations.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 684 polling partitions; 1008 fractional-phase register/capture cases; 1008 state-copy replays; 171 unscheduled-counter cases; 171 wraparound schedules
  method-level, unvalidated: 528 clock-switch software-convention controls; three zero-distance delay-underflow controls
  method-level, unvalidated: absolute count/event oracles and no-polling comparison exercised; native timing and clock-switch silicon phase not qualified
  method-level, unvalidated: existing saved/reset cycle epoch reused; no new state fields
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_frt_phase.py`.
  Same script against pre-change `cbb50769` source, without modifying
  method bodies, exits 1 on the observable counter value:
  `line 308: polled.frc_r()==t/period`.
  All fourteen preceding focused SCI/FRT scripts rerun with unchanged
  expected values: exit 0. Extracted binaries use UBSan. Full
  `sh7604.cpp` syntax with session includes and
  `-std=c++20 -Wall -Werror -Wno-sign-compare`: exit 0, no diagnostics,
  reorder enabled. `git diff --check`: exit 0. No full build run.
- state: UNVALIDATED
- not covered / known doubts: native scheduler/CPU cycle accounting,
  DRC/interpreter consistency, clock changes/halt behavior, physical
  capture synchronizers and on-disk save replay are not qualified.
  The saved `m_frc_base` now retains the last whole-tick epoch rather than
  dropping the fractional interval; there are no new fields or save-layout
  additions, but cross-version save phase compatibility is not assumed.
  Actual CKS switches retain a provisional fresh-period convention;
  absolute phase is not established by the Ymir cross-check. The existing
  immediate zero-distance compare behavior is retained and guarded against
  delay underflow, not accepted as silicon timing. Compare flag/clear-on-
  match semantics, FRC-write count inhibition, TEMP accesses, FTCI input
  and FTOA/FTOB outputs remain separate work. This is not a full FRT timing
  qualification. Frozen DMA acknowledgement, delay-slot, sound and game
  paths were not edited. No milestone status or external-device inventory
  claim changes; validation remains with the separate agent.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0023 | CPU-03 | 463278aa | UNVALIDATED | Shared FRT TEMP stages high-byte writes and snapshots low-byte reads; OCR reads bypass the latch |

### IMPL-0023 — CPU-03 — shared FRT TEMP byte-access latch

- branch/commit: `arena/01a0b897-mame` @ **463278aa** (base: 646965b8).
- files: `src/devices/cpu/sh/sh7604.cpp:43,137,409` (TEMP constructor,
  save and reset), `:1496-1544` (FRC and OCR accesses), `:1577-1584`
  (ICR reads); `src/devices/cpu/sh/sh7604.h:102,112,234` (masked-read
  signatures and state); `saturn_pending/impl_checks/check_sh7604_frt_temp.py:1-171`.
  The FRT stop/phase fixtures gained the mock field and default parameters
  for the new read signatures; all prior expected values are unchanged.
- contract: FRC and OCRA/OCRB high-byte writes stage an 8-bit TEMP value,
  without updating the destination or its compare deadline. The following
  low-byte write commits `(TEMP << 8) | low` to FRC or the currently
  selected OCR. FRC/ICR high-byte reads return the high byte and snapshot
  the low byte in TEMP; subsequent low-byte reads use that snapshot even
  if counting/capture changes the live register in between. There is one
  shared TEMP, not separate read/write or per-register latches. OCR reads
  bypass TEMP. Debugger reads return live register values without changing
  TEMP. Full-width handler accesses retain compatibility by performing
  the high/low steps together; the hardware contract is byte access only.
- primary source: Hitachi SH7604 Hardware Manual ADE-602-085C Rev.4,
  section 11.3 p.304 (shared TEMP CPU interface, high-before-low writes
  and reads, OCR read exception, byte access requirement including DMAC),
  Figure 11.2 p.305 (FRC write staging/commit), Figure 11.3 p.306 (read
  snapshot). Table 11.2 p.297 gives register byte addresses; section
  11.2.7 p.303 defines OCRS selection. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:209-242,245-280,369-389,404,409-432`
  implements shared TEMP, direct OCR reads, peek bypass and TEMP save/load.
  Blob `22868cc7792ede743d834dca5624c6cb5102f04e`.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:919-951,976-979`, reads live words and
  combines partial writes directly, without TEMP. Fork history through
  `646965b8` retains those access paths despite the earlier timer fixes.
  This changes the inline handlers, not an unused standalone peripheral;
  no reference code imported.
- expected observable: writing H'AA to FRC H leaves the running counter
  unchanged until writing H'55 to FRC L commits H'AA55. Likewise an OCR
  high-byte write leaves the previous compare active until low-byte
  commit. Reading FRC H at H'12FF, letting FRC advance to H'1300, then
  reading FRC L returns H'FF: the byte pair reconstructs H'12FF, not
  H'1200. ICR has the same stability across a later capture. Reading OCR
  or inspecting FRC/ICR in the debugger does not destroy staged TEMP.
  Values and callback counts are exact; no new pin/bus-cycle latency or
  timing tolerance is asserted by this byte-interface candidate.
- suggested method: use actual SH-2 byte accesses at H'FFFFFE12/13,
  H'FFFFFE14/15 and H'FFFFFE18/19. Separate write bytes while an existing
  compare is pending; separate read bytes across counter rollover or a
  new capture. Exercise both OCRS choices and its selection at low-byte
  commit. Check that intervening OCR reads do not change TEMP, whereas
  another TEMP-using access does; software must protect its paired
  accesses from such interference. Inspect through the debugger between
  bytes, and save/load between the high and low accesses. Validate native
  big-endian byte-mask dispatch separately from extracted method calls.
- falsifier: an isolated high-byte write changing FRC/OCR or its timer
  deadline, a low read returning a later live value instead of the high-
  read snapshot, OCR reads or debugger inspection overwriting TEMP, a
  distinct per-register latch preventing documented shared-latch behavior,
  or save/load losing staged data contradicts this candidate. Qualifying
  word accesses as equivalent physical SH7604 bus cycles would require
  evidence beyond the compatibility path provided here.
- self-check run (method-level, unvalidated):
  ```text
  method-level, unvalidated: 196608 byte-pair writes; 131072 changing-register read snapshots; 327680 state-copy replays; 512 shared-latch/OCR-read cases; 1536 debugger inspections; 512 reset cases
  method-level, unvalidated: 65536 full-width compatibility controls and eight between-byte timer-event probes; native byte-lane dispatch and save-manager not qualified
  method-level, unvalidated: TEMP constructor/reset/save registration present; save layout changed
  ```
  Command: `python3 saturn_pending/impl_checks/check_sh7604_frt_temp.py`.
  Same new script against pre-change `646965b8` source, adapting only
  the old read signatures (not method bodies), exits 1:
  `line 326: d.value(target)==before && d.timer.due==due && d.irqs.size()==irqs`.
  All fifteen preceding focused SCI/FRT scripts rerun with unchanged
  expected values: exit 0. Extracted binaries use UBSan. Full
  `sh7604.cpp` syntax with session includes and
  `-std=c++20 -Wall -Werror -Wno-sign-compare`: exit 0, no diagnostics,
  reorder enabled. `git diff --check`: exit 0. No full build run.
- state: UNVALIDATED
- not covered / known doubts: **save-state layout break** — new byte
  `m_frt_temp` is initialized in the constructor/shared FRT reset and
  registered with `save_item` in this change. Old saves are not assumed
  compatible. Zeroing TEMP on reset/module stop is a deterministic internal
  convention, consistent with Ymir, not a silicon claim about a low-only
  first access. The manual requires ordered byte pairs; interference probes
  illustrate the shared latch, not a recommended software access protocol.
  Full-width handler compatibility is not hardware word-access acceptance.
  Native address-space masks, CPU/DRC/DMA byte-access sequencing, debugger
  behavior and on-disk save replay remain unqualified. FRC-write count
  inhibition and the extra capture delay for coincident ICR-high reads
  (section 11.4.4 p.309/Figure 11.9) are not implemented here. Existing
  compare/clear-on-match timing limitations, external FTCI and FTOA/FTOB
  pins remain separate work. Frozen DMA acknowledgement, delay-slot,
  sound and game paths and validator assets were not edited. This adds
  no external peripheral and changes no milestone status; IO-02's
  supported/not-supported inventory remains unchanged.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0024 | CPU-03 | 61268a62 | UNVALIDATED | FRT compares the pre-update count on a count edge; CCLRA keeps clearing even with OCFA latched |

### IMPL-0024 — CPU-03 — compare edge and recurrent clear-on-A

- branch/commit: `arena/01a0b897-mame` @ **61268a62** (base: 4044c049).
- files: `src/devices/cpu/sh/sh7604.cpp:437-520` (event selection and
  callback); `saturn_pending/impl_checks/check_sh7604_frt_compare.py:1-122`.
- contract: compare flags are generated at the count-update edge after
  FRC equals OCR, not when FRC first arrives at OCR or asynchronously on
  programming an equal value. Compare distance is therefore unsigned
  16-bit `(OCR-FRC)` plus one. CCLRA schedules every compare A regardless
  of OCFA acknowledgement. B and overflow are eligible before the first
  A clear when software starts FRC above OCRA; earliest-event scheduling,
  rather than a static OCRA/OCRB ordering filter, handles reachability.
  Overflow remains FFFF-to-0000; simultaneous A/B comparisons are retained.
- primary source: SH7604 ADE-602-085C Rev.4, section 11.4.6 p.310 and
  Figure 11.11 p.311 (match in the last state of equality on count update),
  section 11.4.3 p.308/Figure 11.7 (counter clear), section 11.2.5
  pp.301-302 (CCLRA separate from OCFA), section 11.4.7 p.311/Figure 11.12
  (overflow), section 11.6 p.312/Figure 11.13 (recurrent pulse example).
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/FRT.sv:91-103,194-195,223-225`, compares pre-increment
  FRC on FRC_CE and clears independently of the latched OCFA flag; blob
  `5998fa70b8146b2791b6c26f983de0b173420393`. Ymir pinned
  `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:54-78`, uses distance
  less than elapsed steps (not less-than-or-equal); its bulk clear path
  is not adopted as a multiple-period oracle. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:384-448`, and fork base `4044c049`
  retain arrival-at-OCR scheduling and OCFA gating. No source imported.
- expected observable: with initial FRC=0, OCRA=3 and phi/8, equality
  occurs at tick 24 and the compare flag/CCLRA clear at tick 32, not 24.
  With CCLRA=1, FRC repeats 0,1,2,3,0 with period 32 phi ticks even if
  OCFA stays set. OCRA=0 clears on each count edge, never in a zero-time
  callback loop. OCRA=B=FFFF from zero yields both compares and overflow
  at count update 65536. Exact virtual counts/timestamps; native first
  divider phase and observation granularity remain unqualified.
- suggested method: run zero, ordinary and FFFF targets, with equal and
  distinct A/B, CCLRA both clear/set, flags acknowledged and left latched.
  Start above OCRA to expose B/overflow before the first clear. Check
  reassertion after qualified flag acknowledgement and save/load across
  repeated clear periods. Use an independent per-count-step reference.
- falsifier: immediate equality-triggered compare, a match one count edge
  early, a latched OCFA stopping periodic clear, a missed reachable B or
  overflow before the first clear, or zero-time recurring events rejects
  this candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `262144 full-range compare-edge windows; 9216 repeated-clear streams;
  9216 state-copy replays; 9 first-pass wrap streams; 30 acknowledgement/reassertion cases`.
  Same script with unmodified pre-change `4044c049` method bodies exits 1:
  `line 315: d.timer.due>now`.
  Fourteen prior SCI/FRT scripts exit 0. **Two prior scripts exit 1 and
  their expectations are deliberately unchanged:**
  - `check_sh7604_frt_stop.py`: `line 408: timer.due==release+65535*8`.
    Initial FFFF compares now occur on update 65536, with overflow.
  - `check_sh7604_frt_phase.py`: `line 344: polled.timer.due==epoch+(t<37*period?37:t<53*period?53:65536)*period`.
    Targets 37/53 now compare on updates 38/54; this also supersedes its
    immediate zero-distance timing control, not the phase-preservation rule.
  These conflicts require validator review; they are not reported as
  passing regressions. New method binary uses UBSan. Warning-enabled TU
  syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare` and session include
  paths) and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no native CPU/scheduler/IRQ or save-manager
  qualification. No new saved fields; existing timer deadlines from old
  saves cannot be assumed compatible with the changed match phase.
  Same-cycle CPU register accesses versus timer updates and the write/
  compare contention rules in section 11.7 are not implemented. CKS-switch
  transients, FTCI/FTO pins and physical synchronization remain separate.
  IMPL-0020/0022's earlier compare timestamp examples are superseded by
  this candidate, not retroactively edited or qualified. Frozen DMA,
  delay-slot, sound, game paths and validator assets/expectations untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0025 | CPU-03/IO-02 | 3fbbe2fe | UNVALIDATED | External FTCI rising edges clock FRC and its compare/clear/overflow logic without internal timer pacing |

### IMPL-0025 — CPU-03/IO-02 — external FTCI clock input

- branch/commit: `arena/01a0b897-mame` @ **3fbbe2fe** (base: 235bd161);
  shared-reset mock declaration follow-up **83412e4c**.
- files: `src/devices/cpu/sh/sh7604.cpp:50,144,220` (pin-history state),
  `:425-538` (timer/shared compare/pin clock); `src/devices/cpu/sh/sh7604.h:39,295,321`;
  `saturn_pending/impl_checks/check_sh7604_frt_external.py`.
  Prior extracted fixtures only gain helper extraction/mock declarations,
  never changed expected values.
- contract: TCR.CKS=11 selects rising-edge FTCI counting. Each distinct
  rising edge increments FRC and runs the same pre-update compare/CCLRA/
  overflow behavior as IMPL-0024. Falling/repeated levels do not count;
  internal CKS selections and MSTP1 suppress counting while retaining pin
  history. FTI remains a separate capture input. Elapsed CPU time does not
  pace external mode, and no positive FRT timer arm occurs while that mode
  stays selected. No Saturn/ST-V board wiring or new peer device is added.
- primary source: SH7604 ADE-602-085C Rev.4, section 11.2.6 p.302
  (external rising-edge CKS selection), section 11.4.1 p.307/Figure 11.5
  (external clock counting and minimum pulse width of six system clocks),
  section 11.1.3/Table 11.1 p.297 (FTCI versus FTI pins), sections
  11.4.3/11.4.6/11.4.7 pp.308-311 (common counter events), section
  14.2.1 p.388 (module stop). SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/FRT.sv:47-61,91-103,194-195,223-225` selects a rising
  FTCI edge and shares count/compare logic. Its physical sampling pipeline
  is not imported. Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:291-293` comments that
  Saturn ties FTCI high and models external selection as no clock; that
  is not corroboration for a working external-pin engine. Upstream MAME
  pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:369,431-435`, and fork base `235bd161`
  leave external counting as a TODO. No reference code imported.
- expected observable: with CKS=11 and FRC=0, N rising edges produce N
  increments (modulo 65536, unless CCLRA clears). Holding FTCI at either
  level for arbitrary CPU cycles produces zero additional increments.
  OCRA=3, CCLRA=1 yields 1,2,3,0 on the first four rising edges and repeats
  even with OCFA latched. A repeated high call after a held-high mode
  transition must not count as an edge. Counts/flags exact; input latency
  and setup/hold tolerance are not asserted.
- suggested method: drive valid high/low pulses at least six phi ticks
  wide, vary spacing and pause the clock; compare to a per-edge oracle.
  Include wrap, equal A/B, CCLRA, latched flags, FTI capture, mode changes,
  module stop, and save/load at both pin levels. Native board qualification
  must distinguish an unconnected API from an actually configured source.
- falsifier: time-based increments, falling/repeated-edge counts, count
  changes under internal CKS/MSTP1, missing compare/clear/overflow events,
  or an invented rising edge after state restoration rejects this candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `262144 external-clock streams; 2048 pin-history state-copy replays;
  770 clock-select/module-stop controls; 256 independent FTI captures`.
  With pre-change `235bd161` methods and only a no-op shim for the absent
  FTCI entry point, it exits 1:
  `line 378: d.frc_r(0,0xffff)==o.counter && d.m_ftcsr==o.status`.
  Fifteen preceding checks exit 0 after the SCI module-stop harness's
  missing new-state declaration was added in `83412e4c` (its first run
  was a mock compile failure, not a production syntax failure).
  The two IMPL-0024 conflicts remain: `frt_stop` exits 1 at
  `line 410: timer.due==release+65535*8`; `frt_phase` exits 1 at its old
  compare-deadline expression, line 346. Expectations remain untouched.
  New method binary uses UBSan. Warning-enabled TU syntax with session
  includes (`-std=c++20 -Wall -Werror -Wno-sign-compare`) and
  `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: **save-state layout break**, new saved/reset
  `m_frt_clock_input`. No old-save compatibility or native save-manager
  claim. Synchronizer latency, minimum-width rejection and physical pin
  margins are not emulated; pulse-step checks are not electrical evidence.
  No actual FTCI source is configured for Saturn/ST-V. CKS switch
  transients, CPU-register/event contention, whole-chip standby, native IRQ
  delivery and FTO outputs remain separate. The two old timing expectation
  conflicts remain visible. Frozen DMA, delay-slot, sound and game paths
  and validator assets were not edited.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0026 | CPU-03/IO-02 | 1168e29a | UNVALIDATED | FTOA/FTOB take their selected OLVL levels on compare, independently of latched flags, and reset low |

### IMPL-0026 — CPU-03/IO-02 — FRT compare output pins

- branch/commit: `arena/01a0b897-mame` @ **1168e29a** (base: d187958c).
- files: `src/devices/cpu/sh/sh7604.cpp:44-45,144-145,422-425` (output
  state/callback lifecycle), `:461-468,513-540` (scheduling/compare);
  `src/devices/cpu/sh/sh7604.h:40-41,240-241` (binders/state);
  `saturn_pending/impl_checks/check_sh7604_frt_output.py`.
  Existing FRT mock declarations gained the output fields/callback stubs;
  no existing expected values changed.
- contract: FTOA takes TOCR.OLVLA on compare A; FTOB takes OLVLB on
  compare B. TOCR writes do not immediately change a pin, and compare
  does not automatically toggle it. OCFA/OCFB acknowledgement is not
  required for a subsequent pending output change. The scheduler retains
  such matches even if the status flag is already set, while unchanged
  levels can skip redundant callbacks. Reset/module stop drives both low.
  Both internal and external clocks use the shared compare handler.
- primary source: SH7604 ADE-602-085C Rev.4, section 11.2.2 p.298
  (compare output, reset low), section 11.2.7 p.303 (OLVLA/B selection),
  section 11.4.2 p.308/Figure 11.6 (output on match), section 11.6
  p.312/Figure 11.13 (software-inverted levels, not hardware auto-toggle),
  section 14.5.1 p.393 and Table A.1 p.564 (module/reset pin state).
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/FRT.sv:91-99`, assigns the selected level on every
  matching count edge independently of the flag's prior state; it is not
  an oracle for this callback model's reset notifications. Ymir pinned
  `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_frt.hpp:327-348`, describes the
  OLVL fields but supplies no corresponding pin-waveform implementation.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:967-972`, leaves output levels as a TODO;
  fork base `d187958c` retained it. No reference code imported.
- expected observable: select OLVLA=1 while FTOA=0; the pin stays low
  until compare A, then goes high. Leaving OCFA set and selecting OLVLA=0
  produces a low transition at the next compare, not at the write. Same
  for B. A/B can change together when their compares coincide. State and
  edge counts are exact logical observations; no physical propagation
  delay/electrical tolerance is claimed. Reset callbacks explicitly
  publish zero even if the old logical level was already zero.
- suggested method: bind both callbacks to a timestamped logical probe,
  vary OLVL between count edges under all clock selections, with CCLRA
  enabled/disabled and flags left latched. Include simultaneous A/B,
  unreachable B beyond an A-clear point, pending-level save/load and
  reset/module stop. Native board wiring is a separate deliverable.
- falsifier: a TOCR write immediately moving a pin, automatic toggling,
  latched status preventing a selected-level change at the next compare,
  lost pending changes across save/load or reset not driving low rejects
  this candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `20480 scalar-oracle output streams; 1024 pending-output state-copy
  replays; 8 reset/module-stop output cases`.
  Same script against pre-change `d187958c` methods exits 1:
  `line 395: (d.m_frt_out_a|(d.m_frt_out_b<<1))==o.levels && d.wave==o.wave`.
  Sixteen prior scripts exit 0. The two previously documented timing
  conflicts still exit 1 with unchanged expectations: `frt_stop` at old
  `release+65535*8` deadline (generated line 429), `frt_phase` at old
  37/53 deadline expression (line 365). New binary uses UBSan. Full TU
  syntax with session includes and `-std=c++20 -Wall -Werror -Wno-sign-compare`
  and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: **save-state layout break**, new saved/reset
  `m_frt_out_a` and `m_frt_out_b`. Native peer/save-manager restoration
  is not established by state-copy replay. Logical output levels and
  counter clear are committed before callbacks; simultaneous notifications
  are delivered A then B, not a silicon propagation-order assertion.
  Physical drive strength, loading, pin contention, whole-chip standby/HIZ,
  register/event contention and native CPU/IRQ scheduling remain open.
  No FTO callback peer is configured for Saturn/ST-V. The two legacy
  timing conflicts remain visible. Frozen DMA, delay-slot, sound, game
  paths and validator assets were not edited.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0027 | CPU-03 | 4d997aed | UNVALIDATED | Watchdog keyed-register handlers reject byte/partial writes instead of reusing or assembling stale keys |

### IMPL-0027 — CPU-03 — watchdog keyed word-access guard

- branch/commit: `arena/01a0b897-mame` @ **4d997aed** (base: f0907753).
- files: `src/devices/cpu/sh/sh7604.cpp:1923-1929,1962-1968`;
  `saturn_pending/impl_checks/check_sh7604_wdt_access.py:1-106`.
- contract: the WTCNT/WTCSR and RSTCSR write handlers require both byte
  lanes in one word access. Byte writes, including upper/lower pairs,
  cannot reuse a previously stored key or combine to form a command.
  Rejected accesses cause no counter/status, timer or IRQ changes.
  Complete-word dispatch is unchanged in this candidate.
- primary source: SH7604 ADE-602-085C Rev.4, section 12.2.4 pp.324-325,
  Figures 12.2/12.3: keyed word writes at H'FFFFFE80 and H'FFFFFE82;
  byte writes cannot write these registers. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1430-1446,1545-1575`, ignores
  byte writes and dispatches keyed word writes separately. Upstream MAME
  pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1273-1321`, combines partial writes into
  old command data; fork base `f0907753` still has that path. No reference
  code imported; the guard is local to watchdog handlers, not general DMA.
- expected observable: after a valid H'5Axx counter write, a subsequent
  byte write to the low lane must not change WTCNT. Writing H'A5 and a
  payload in separate byte accesses must not enable/disable the timer,
  change RSTE/RSTS or acknowledge WOVF. A complete keyed word still reaches
  the prior handler. Exact state and callback-count comparisons; no new
  timing latency/tolerance claimed.
- suggested method: issue native SH-2 byte writes in both lane orders,
  before and after valid keyed words, observe registers/timer deadline/IRQ
  state, then use complete words as controls. Separately inspect native
  longword dispatch: that restriction is not established by this guard.
- falsifier: byte writes altering any watchdog register, scheduling or IRQ
  state; split bytes assembling a command; or a complete keyed word being
  rejected solely by this guard contradicts the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `6144 byte-lane writes; 131070 partial-mask robustness cases;
  1024 two-byte assembly attempts; 131072 existing full-word dispatch controls`.
  Pre-change `f0907753` methods exit 1 at `line 76: d.snapshot()==before`.
  Seventeen prior scripts exit 0; the unchanged `frt_stop` and `frt_phase`
  compare-deadline expectations still exit 1 as recorded in IMPL-0024/0026.
  UBSan enabled. Warning-enabled full TU syntax with session includes
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`) and `git diff --check`
  exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new state fields or save-layout change.
  Native CPU/DRC/address-space dispatch and timer/IRQ behavior are not
  qualified by extracted handlers. A longword may be decomposed into
  full-mask word callbacks; original transaction width is not available
  to these handlers, so this does NOT implement the manual's longword
  rejection rule. Existing overflow acknowledgement, exact RSTCSR command
  filtering, timer phase, WDTOVF output and internal reset delivery remain
  separate work. Full-word controls preserve prior behavior, not a claim
  that all prior behavior is documented hardware. Frozen DMA, delay-slot,
  sound/game paths, validator assets and fixture expectations untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0028 | CPU-03 | 157107eb | UNVALIDATED | Watchdog OVF/WOVF require independent read-one/write-zero qualifications, respecting read byte lanes and debugger inspection |

### IMPL-0028 — CPU-03 — watchdog overflow acknowledgement

- branch/commit: `arena/01a0b897-mame` @ **157107eb** (base: 81279ec8).
- files: `src/devices/cpu/sh/sh7604.cpp:48,187,244` (state lifecycle),
  `:1914-1993` (status reads and keyed writes);
  `src/devices/cpu/sh/sh7604.h:179-182,273` (read masks and state);
  `saturn_pending/impl_checks/check_sh7604_wdt_flags.py`.
  Three prior extraction mocks only gain the new field declaration;
  no expected values changed.
- contract: WTCSR.OVF and RSTCSR.WOVF may be cleared by the appropriate
  keyed write only after software reads the corresponding set flag.
  Qualifications are independent and consumed on clear. WTCSR is the
  high read lane at FE80, WTCNT the low lane at FE81; reading WTCNT alone
  does not qualify OVF. RSTCSR is the low read lane at FE83, not FE82.
  Debugger inspection neither arms nor replaces qualifications. A new
  overflow after a clear requires a fresh status read. Device reset clears
  the new read-history byte. Existing timer and reset-delivery paths are
  not changed by this register candidate.
- primary source: SH7604 ADE-602-085C Rev.4, section 12.2.2 p.322
  (OVF read/clear), section 12.2.3 pp.323-324 (WOVF read/clear), section
  12.2.4 pp.324-325/Figures 12.2/12.3 (keyed word writes and distinct
  byte read addresses). Valid WOVF clear command is H'A500. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_wdt.hpp:113-142` has a WTCSR
  read qualifier and peek guard. Its write path does not consume that
  qualifier, clears OVF additionally on TME=0, and its WOVF path
  (`:195-225`) is not read-qualified; those differences are not adopted
  as SH7604 evidence. Primary per-flag rules govern this candidate.
  Blob `331dc8d6e4096a3be637c4b923b1962c924697e3`. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1262-1321`, lacks both qualifications;
  fork base `81279ec8` has only IMPL-0027's byte-write guard added.
  No reference code imported.
- expected observable: after interval overflow, a keyed WTCSR write with
  OVF=0 leaves OVF set until a CPU WTCSR read precedes it. WTCNT-only or
  debugger reads do not suffice. After watchdog overflow, H'A500 leaves
  WOVF set until a CPU read from FE83; a high-lane read at FE82 does not
  suffice. Each successful clear protects the next newly raised event
  against an unread zero write. RSTE/RSTS writes do not consume WOVF's
  pending qualification. Exact bits; no new timing tolerance asserted.
- suggested method: generate both overflow sources separately, vary
  status-read lanes and debugger reads, then attempt keyed acknowledgements.
  Interleave qualifications, save/load between read/write and clear/event,
  and repeat a clear without another status read. Use native CPU byte
  accesses to qualify the address-space mask routing independently.
- falsifier: unread overflow clearing, unrelated-lane/debugger reads
  authorizing a clear, one register's read authorizing the other flag,
  stale qualification clearing a new event, or lost qualification across
  save/load rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `1136 qualified watchdog writes; 1136 state-copy replays;
  256 status-lane/debugger read cases`, plus actual overflow callback and
  repeated-clear probes. Same script against pre-change `81279ec8`
  methods (read signatures adapted only) exits 1:
  `line 111: unread.m_wtcsr&0x80`.
  Seventeen prior scripts exit 0. **Three expected-value conflicts remain
  visible with expectations unchanged:**
  - `frt_stop`: old `release+65535*8` deadline (line 431).
  - `frt_phase`: old 37/53 compare deadline expression (line 367).
  - `wdt_access`: `line 132: d.m_wtcsr==(data&0xff) && d.syncs==1 && d.irqs==1`.
    Its original full-word compatibility control expects an unread OVF
    clear. That part of the old behavior is superseded here; the prior
    byte-rejection contract is not withdrawn.
  New binary uses UBSan. Warning-enabled TU syntax with session includes
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`) and `git diff --check`
  exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: **save-state layout break**, new saved byte
  `m_wdt_read`, with constructor and device-reset initialization. Those
  registration/reset statements are checked, not native reset execution.
  Old saves are not assumed compatible. Native IRQ/CPU/DRC/debugger and
  on-disk save-manager behavior remain unqualified. The existing permissive
  decode of nonzero A5xx RSTCSR payloads is not repaired; the contract
  uses documented A500. Longword rejection, watchdog timer phase, WDTOVF
  output, internal reset delivery, RSTCSR hardware-reset initialization and
  whole-chip standby remain separate work. The three fixture conflicts
  need validator review, not silent expectation updates. Frozen DMA,
  delay-slot, sound/game paths and validator assets were not edited.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0029 | CPU-03 | fdcbc6e7 | UNVALIDATED | RES-style device reset initializes RSTCSR and cancels stale watchdog deadlines |

### IMPL-0029 — CPU-03 — RES-style watchdog reset lifecycle

- branch/commit: `arena/01a0b897-mame` @ **fdcbc6e7** (base: 7bbace47).
- files: `src/devices/cpu/sh/sh7604.cpp:242-250`;
  `saturn_pending/impl_checks/check_sh7604_wdt_reset.py:1-96`;
  two shared extraction mocks gain WDT timer/RSTCSR declarations only.
- contract: generic device reset is the RES-style reset path for WDT:
  WTCNT reads 00, WTCSR reads 18, RSTCSR reads 1F; the counter is stopped
  and no old watchdog timer deadline may fire after reset. Internal
  watchdog-generated reset is distinct and must preserve RSTCSR; this
  candidate does not add that reset path or wire it to generic reset.
- primary source: SH7604 ADE-602-085C Rev.4, Table 12.2 and section
  12.2.1 p.321 (reset values and counter reset), section 12.2.2 p.322
  (TME=0 stops/initializes counter), section 12.2.3 p.323 (RES initializes
  RSTCSR to 1F; WDT internal reset does not), section 12.3.1 p.326 (RES
  takes priority over simultaneous watchdog reset and clears WOVF).
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_wdt.hpp:23-31`, explicitly
  distinguishes watchdog-initiated reset, clearing RSTCSR only otherwise;
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:377` passes that reset cause.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp` device_reset WTC block, and fork base
  `7bbace47:src/devices/cpu/sh/sh7604.cpp:241-244`, initialize only counter
  and control (plus the fork's new read history); neither cancels WDT's
  old deadline nor initializes RSTCSR. No reference code imported.
- expected observable: resetting with a timer active and WOVF/RSTE/RSTS
  set yields the documented three byte-read reset values immediately.
  Advancing past the old deadline with TME still zero produces no overflow
  status/event. Re-enabling and loading a counter establishes a new
  deadline from the new control/counter, not the pre-reset schedule.
  Exact register bytes and event counts; no physical reset-pin latency
  asserted by a device-method call.
- suggested method: native reset during interval and watchdog modes,
  sweep all eight clock selections and counter values, then wait past the
  old deadline and inspect status before re-enabling. Save/load after reset
  and compare the first newly enabled interval. Qualify external RES and
  internally generated reset independently; do not route the latter through
  this generic path without handling RSTCSR preservation.
- falsifier: RSTCSR retaining old WOVF/control bits after RES-style reset,
  a stale overflow firing with TME=0, wrong reset byte reads, or old timer
  state influencing the newly enabled schedule rejects this candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `16384 active-deadline reset cases; 16384 restart controls;
  16384 state-copy replays`. Real device_reset and WDT register/timer
  methods; base CPU reset and unrelated FRT/SCI reset helpers are mocks.
  Pre-change `7bbace47` methods exit 1 at line 218, reset register-image
  assertion. UBSan enabled. Eighteen prior scripts exit 0; the three
  unchanged expectation conflicts from IMPL-0028 remain: `frt_stop`
  line 438 (65535 ticks), `frt_phase` line 374 (37/53 deadlines),
  `wdt_access` line 132 (unread OVF clear). Warning-enabled TU syntax
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes) and
  `git diff --check` exit 0. No full build or native qualification.
- state: UNVALIDATED
- not covered / known doubts: no new production state fields or save-layout
  change. Existing saved RSTCSR is initialized here; existing read-history
  reset is retained. Native CPU reset delivery/order, physical RES pulse,
  WDT-generated internal resets and WDTOVF remain unimplemented/unqualified.
  The reset fixture's watchdog restart control stops at the overflow flag,
  not a completed internal reset. WDT-local reset when RSTE=0 (sections
  12.2.3/12.4.5) remains separate from this RES path. This changes no
  sound-reset or board-clock code, DMA acknowledgement, delay-slot IRQ,
  game-specific paths, validator assets or fixture expected values.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0030 | CPU-03 | 92c86000 | UNVALIDATED | Watchdog overflow with RSTE=0 resets WTCNT/WTCSR locally, preserving RSTCSR and avoiding CPU reset |

### IMPL-0030 — CPU-03 — watchdog-local overflow reset

- branch/commit: `arena/01a0b897-mame` @ **92c86000** (base: f86da106).
- files: `src/devices/cpu/sh/sh7604.cpp:577-603`;
  `saturn_pending/impl_checks/check_sh7604_wdt_local_reset.py`;
  `saturn_pending/impl_checks/check_sh7604_wdt_flags.py` gains an explicit
  re-enable stimulus before generating a second watchdog overflow.
- contract: in watchdog mode with RSTE=0, overflow sets WOVF and resets
  WTCNT/WTCSR within the WDT; it does not reset the CPU. Thus WTCNT reads
  00 and WTCSR reads 18, TME is clear, and no new counter overflow occurs
  without another enable. RSTCSR, including RSTS and newly set WOVF, is
  preserved. Clearing WTCSR consumes its old OVF-read qualification and
  refreshes IRQ arbitration; RSTCSR's qualification is independent.
- primary source: SH7604 ADE-602-085C Rev.4, section 12.2.3 p.324 RSTE=0
  table entry and section 12.4.5 p.331 explicitly require the local WTCNT/
  WTCSR reset without internal chip reset. Sections 12.2.1-12.2.2
  pp.321-322 specify reset register values. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Saturn_MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/WDT.sv:151-168` wraps WTCNT, sets RSTCSR.WOVF and assigns
  WTCSR=18 at watchdog overflow; `:76-89` gates the internal reset output
  on RSTE. Blob `fc0d4d397dd42e2a37313e7a91919006cca0f4da`. Its pulse,
  standby, flag-ack and bus details are not imported. Ymir pinned
  `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_wdt.hpp:50-68`, sets WOVF and
  requests a chip reset only when RSTE=1, but omits this RSTE=0 local
  reset; it is a documented cross-check difference, not an oracle.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:462-475`, and fork base
  `f86da106:src/devices/cpu/sh/sh7604.cpp:577-591` only set WOVF and leave
  a reset/output TODO. No reference code imported.
- expected observable: at the overflow event with RSTE=0, WTCNT=00,
  WTCSR=18, and RSTCSR=9F or BF depending on RSTS. There is no chip reset,
  no unrelated FRT/SCI/UBC/INTC register initialization, and the stopped
  WDT does not produce a later overflow until explicitly re-enabled.
  Exact register/event comparisons; no physical reset/output timing
  tolerance claimed by a callback-level observation.
- suggested method: set RSTE=0, sweep both RSTS values and all eight CKS
  selections, load near overflow, and inspect byte registers plus CPU
  progress after overflow. Repeat after explicitly re-enabling the WDT.
  Interleave prior OVF/WOVF status reads and save/load before overflow.
  Separately qualify interval mode, which must continue periodic operation.
- falsifier: CPU reset with RSTE=0, WTCSR remaining enabled after watchdog
  overflow, RSTCSR losing WOVF/RSTS, unrelated peripheral initialization,
  a repeated overflow while stopped, or failed explicit restart rejects
  this candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `65536 watchdog-local resets; 65536 state-copy replays;
  65536 explicit restart cases; 96 interval controls`. Real WDT methods;
  mocks record base reset calls, selected unrelated registers and IRQ
  refresh count (not native IRQ delivery). Pre-change `f86da106` methods
  exit 1 at line 242, WTCNT/WTCSR/RSTCSR local-reset image assertion.
  UBSan enabled. The first rerun of `wdt_flags` exited 1 at line 194:
  its stimulus directly invoked another callback without re-enabling the
  now-stopped watchdog. Added a documented keyed enable before that second
  event; all its assertions/expected values remain unchanged. It exits 0
  again, and this new script separately asserts that no event occurs while
  stopped. Current total 23 SH7604 scripts: 20 exit 0; the three unchanged
  expectation conflicts remain (`frt_stop` line 438, `frt_phase` line 374,
  `wdt_access` line 132), as described in IMPL-0028/0029.
  Warning-enabled TU syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare`,
  session includes) and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new state fields or save-layout change.
  This is only RSTE=0 local reset; RSTE=1 internal CPU reset and WDTOVF
  output/pulse handling remain TODO. Generic RES reset remains distinct
  (IMPL-0029). Physical reset-hold timing, accesses during an active WDTOVF
  pulse, counter phase/read rounding, native IRQ priority/delivery and
  actual save-manager restoration remain unqualified. Re-enable probes
  wait beyond the documented output-pulse interval; they do not establish
  active-pulse write behavior. Frozen DMA, delay-slot IRQ, sound/game paths,
  validator assets and existing expected values were not edited.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0031 | CPU-03 | 919bc219 | UNVALIDATED | WTCNT sampling rounds remaining selected-clock periods upward so whole-phi reads do not expose the next count early |

### IMPL-0031 — CPU-03 — watchdog counter observation between edges

- branch/commit: `arena/01a0b897-mame` @ **919bc219** (base: 91e20684).
- files: `src/devices/cpu/sh/sh7604.cpp:566-577`;
  `saturn_pending/impl_checks/check_sh7604_wdt_count.py`.
- contract: WTCNT counts selected internal clock pulses, not partially
  elapsed selected-clock periods. Given the existing overflow deadline,
  whole-system-clock samples between counter edges must retain the old
  count. The remaining period count is rounded up before subtracting it
  from 256. A counter read itself must not move the timer deadline.
- primary source: SH7604 ADE-602-085C Rev.4, section 12.2.1 p.321
  (WTCNT counts pulses of the selected internal clock), section 12.2.2
  p.323 CKS table (phi/2, /64, /128, /256, /512, /1024, /4096, /8192),
  section 12.3.2 p.328/Figure 12.5 (successive interval overflows).
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_wdt.hpp:35-66`, derives increments
  from complete divider steps. Its absolute clock-grid alignment is not
  imported or established here. Saturn_MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/WDT.sv:48-60,155-168`, increments on the selected clock
  enable. Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:451-455`, and fork base `91e20684`
  floor the remaining period count, exposing the next counter value early.
  No reference code imported.
- expected observable: with counter 00, divider 2 and the current deadline
  at 512 phi, byte reads at elapsed 0/1/2 phi return 0/0/1. With divider
  64 and deadline 16384 phi, reads at elapsed 1 and 63 phi remain 0, then
  become 1 at 64 phi. The prior calculation could expose the next value
  up to P-1 phi early for divider P. Exact integer-phi sample values;
  this entry does not specify initial prescaler phase relative to RES.
- suggested method: establish an overflow deadline, sample WTCNT throughout
  the preceding counter periods without writes, compare polling and idle
  instances, and repeat across save/load. Native measurement must resolve
  CPU bus-read phase relative to the selected clock independently.
- falsifier: early/late counter values at the established whole-phi edges,
  polling moving the deadline, or state-copy/native save replay changing
  the sampled count rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `45900 counter samples; 45900 state-copy replays;
  57096 exhaustive whole-phi period positions`. Pre-change `91e20684`
  methods exit 1 at line 241, counter sample/replay assertion. UBSan
  enabled. Twenty prior scripts exit 0; the unchanged `frt_stop`,
  `frt_phase` and `wdt_access` expectation conflicts remain (lines 438,
  374, 132). Current total 24 SH7604 scripts: 21 exit 0, 3 exit 1.
  Warning-enabled TU syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare`,
  session includes) and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new fields or save-layout change.
  Timer-to-CPU-cycle conversion still quantizes to whole phi; native
  fractional-cycle/attosecond rounding and access exactly coincident with
  an unserviced expiry remain unqualified. Clock-grid startup, active
  WTCSR/WTCNT-write phase preservation, CKS changes, WDTOVF and RSTE=1
  internal reset remain separate. This fixes observation relative to the
  existing deadline, not all watchdog timing. No validator assets,
  expected values, frozen DMA, delay-slot or sound/game paths changed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0032 | CPU-03 | 10276d04 | UNVALIDATED | Same-clock active watchdog writes preserve the selected-clock partial period instead of restarting it |

### IMPL-0032 — CPU-03 — watchdog phase through active register writes

- branch/commit: `arena/01a0b897-mame` @ **10276d04** (base: 0fc51593).
- files: `src/devices/cpu/sh/sh7604.cpp:579-593`;
  `saturn_pending/impl_checks/check_sh7604_wdt_phase.py`.
- contract: while TME remains set and CKS/mode are unchanged, WTCNT reloads
  replace the counter but retain the partial selected-clock period.
  WTCSR writes affecting only status/unchanged control do not postpone
  overflow. The old active deadline supplies the residual phase; stopped
  timers have no residual deadline. The existing initial-enable convention
  is deliberately unchanged, not promoted to a physical startup claim.
- primary source: SH7604 ADE-602-085C Rev.4, sections 12.2.1-12.2.2
  pp.321-323 (WTCNT counts pulses from the selected internal divided
  clock), section 12.4.1 p.330/Figure 12.8 (counter writes on that clock;
  write has priority over a coincident increment), sections 12.4.2/12.4.3
  p.330 (stop before changing clock selection or timer mode). SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_wdt.hpp:44-45,163-166`, keeps
  the divided-clock grid while replacing WTCNT; `libs/ymir-core/src/ymir/
  hw/sh2/sh2.cpp:1550-1559` advances before register changes. Its absolute
  startup grid is not imported. Saturn_MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`, `rtl/SH/SH7604/WDT.sv:
  48-60,155-178`, uses external divided clock-enables; WTCNT writes do not
  reset those dividers. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:457-460`, and fork base `0fc51593`
  schedule a whole number of periods from every write, dropping phase.
  No reference code imported.
- expected observable: with divider 64 and an established overflow deadline
  at 16384 phi, an unchanged WTCSR write at phi 1 keeps the deadline at
  16384, not 16385. Reloading FF at phi 1 sets overflow at phi 64, not 65;
  reloading FF at phi 63 leaves one phi until overflow. These are whole-phi
  relative-deadline observations, not claims about initial clock alignment.
  Stopping/re-enabling must not inherit the canceled timer's residual phase.
- suggested method: observe overflow timestamps while repeatedly rewriting
  unchanged WTCSR, then reload WTCNT between selected-clock edges. Sweep
  clock selections and reload values; keep CKS and mode constant while
  enabled. Save/load between phase-bearing writes. Check native T3/clock
  contention independently from callback ordering.
- falsifier: same-clock WTCSR writes shifting overflow, WTCNT reloads
  restarting a full selected period instead of retaining its phase,
  a disabled timer carrying an old deadline into a new enable, or divergent
  save/load timing rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `552 active WTCSR controls; 16384 counter reloads;
  16936 state-copy replays; 64 stopped-clock-change controls`.
  Pre-change `0fc51593` methods exit 1 at line 253, deadline/replay
  assertion. UBSan enabled. Twenty-one prior scripts exit 0; the unchanged
  `frt_stop`, `frt_phase`, `wdt_access` expectation conflicts remain at
  lines 438, 374, 132. Current total 25 SH7604 scripts: 22 exit 0, 3 exit 1.
  Warning-enabled TU syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare`,
  session includes) and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new fields or save-layout change; phase
  is reconstructed from the already-scheduled timer deadline. Actual
  save-manager restoration, fractional-phi conversion, dynamic CPU clock
  changes, initial-enable phase and scheduler/bus ordering at an exact
  coincident write/clock edge remain unqualified. Active CKS/mode changes
  are forbidden by the manual and not modeled as supported transitions.
  This does not add WDTOVF output, RSTE=1 reset or longword rejection.
  No validator assets, expected values, frozen DMA acknowledgement,
  delay-slot IRQ, sound-reset/clock or game paths changed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0033 | CPU-03 | 5393c38a | UNVALIDATED | Watchdog native 32-bit write mapping accepts exactly one full word lane and rejects longword/byte writes before decomposition |

### IMPL-0033 — CPU-03 — watchdog transaction-width gate

- branch/commit: `arena/01a0b897-mame` @ **5393c38a** (base: 352d8ea3).
- files: `src/devices/cpu/sh/sh7604.cpp:299-301,1963-1973`;
  `src/devices/cpu/sh/sh7604.h:179`;
  `saturn_pending/impl_checks/check_sh7604_wdt_width.py`.
- contract: WDT register writes require a single keyed word. At the native
  32-bit, big-endian program-space map boundary, FFFF0000 dispatches the
  high word to WTCNT/WTCSR at FE80; 0000FFFF dispatches the low word to
  RSTCSR at FE82. FFFFFFFF is a longword and executes neither command.
  Byte, empty and other partial masks execute neither command. Existing
  read handlers and per-word key/flag rules remain unchanged. This adds
  the map-level width information unavailable to IMPL-0027's 16-bit guard.
- primary source: SH7604 ADE-602-085C Rev.4, Table 12.2 p.321 note 1,
  section 12.2.4 pp.324-325/Figures 12.2/12.3: write by word, not byte
  or longword, using the appropriate upper-byte key. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Saturn_MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/WDT.sv:171-187`, accepts only the two word-wide byte-enable
  patterns before keyed register dispatch, not all four enabled bytes.
  Blob `fc0d4d397dd42e2a37313e7a91919006cca0f4da`. Local SH-2 configuration
  at base `352d8ea3:src/devices/cpu/sh/sh2.cpp:35` is 32-bit big-endian.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp` WDT map entries, and fork base
  `352d8ea3:src/devices/cpu/sh/sh7604.cpp:299-300` install separate 16-bit
  write handlers, losing the original longword mask through decomposition.
  No reference code imported.
- expected observable: native MOV.L of 5A12A500 at FE80 must neither set
  WTCNT to 12 nor clear WOVF, even after a qualifying RSTCSR read. Native
  MOV.W of 5A12 at FE80 still writes WTCNT; a qualifying MOV.W A500 at
  FE82 still clears WOVF. MOV.B sequences cannot assemble either command.
  Exact register, timer and IRQ-state comparisons; no added latency claim.
- suggested method: execute native aligned SH-2 MOV.B/MOV.W/MOV.L stores
  with independently valid commands in both halves. Probe both word
  addresses, ensure inactive data lanes have no effect, and compare CPU
  interpreter/DRC and supported DMA access paths. Also qualify unchanged
  byte-read routing after splitting read/write mappings by direction.
- falsifier: a longword executing either half-command, byte writes changing
  watchdog state, a word reaching the wrong register, or a valid word
  being blocked solely by this width gate rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `524288 rejected native/partial-mask writes;
  131072 exact word-lane dispatch controls; split-byte assembly rejected`.
  It extracts the actual new selector and real keyed word handlers and
  inspects map/space declarations, but does not instantiate address_space.
  Pre-change `352d8ea3` negative explicitly uses a 32-to-16 lane-decomposition
  shim for its original two 16-bit mapping entries; it exits 1 at line 96,
  `both.m_wtcnt==0x56 && both.m_rstcsr==0xe0 && both.m_wdt_read==3`.
  This is not a native old-map execution claim. UBSan enabled. Twenty-two
  prior scripts exit 0; the unchanged `frt_stop`, `frt_phase`, `wdt_access`
  expectation conflicts remain at lines 438, 374, 132. Current total 26
  SH7604 scripts: 23 exit 0, 3 exit 1. Warning-enabled TU syntax
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes) and
  `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new state fields or save-layout change.
  Native address-map construction and CPU/DRC/DMA lane routing still need
  validator qualification. This replaces the earlier inability to reject
  longwords at the write-map boundary; it does not retroactively qualify
  IMPL-0027 or claim its 16-bit handlers can identify original width.
  Illegal word/longword reads, undocumented address aliases/open-bus data,
  exact non-A500 command decoding, WDTOVF and RSTE=1 internal reset remain
  separate. DMA acknowledgement machinery, delay-slot IRQ, sound/game
  paths, validator assets and existing expected values were not edited.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0034 | CPU-03 | — | BLOCKED(SH7604 RSTE=0 WDTOVF active-pulse re-enable/retrigger trace) | WDTOVF output needs the local-reset hold and overlapping-overflow contract, not an invented retrigger policy |

### IMPL-0034 — CPU-03 — WDTOVF pulse/retrigger boundary

- branch/base: `arena/01a0b897-mame` @ 403c6695; no production change.
- files: `src/devices/cpu/sh/sh7604.cpp`, watchdog overflow callback TODO.
- contract known: SH7604 ADE-602-085C Rev.4, section 12.3.1 pp.326-327/
  Figure 12.4, specifies WDTOVF output for 128 phi and, with RSTE=1, an
  internal reset for 512 phi. Sections 12.2.3 p.324 and 12.4.5 p.331
  require a local WTCNT/WTCSR reset with RSTE=0. These passages do not
  resolve acceptance of TME/counter writes during the output pulse or
  suppression/retrigger/extension if software causes another overflow.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Saturn_MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/WDT.sv:74-83,164-183`, releases outputs on divided clock
  enables and allows register writes after the local-reset assignment.
  This is not sufficient evidence for a fixed-width retrigger policy;
  phase/reset of those enables and hardware active-pulse access behavior
  need qualification. Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_wdt.hpp:50-68`, does not supply
  the external WDTOVF waveform. Neither resolves the missing contract.
- expected observable once resolved: isolated pulse width 128 phi;
  RSTE=0 retains CPU execution, with local-register behavior and any
  overlapping pulse response recorded rather than assumed. RSTE=1's
  512-phi internal reset additionally needs a reset-cause-aware CPU path
  preserving RSTCSR; it cannot simply invoke the generic RES-style reset.
- suggested measurement: hardware trace of phi/WDTOVF with RSTE=0,
  CKS=0 and a near-overflow preload, followed by TME/counter writes at
  several offsets inside the 128-phi pulse. Capture WTCSR/WTCNT/WOVF and
  second-overflow time. Distinguish ignored writes, held local reset,
  non-retriggerable output, restarted pulse and extended pulse.
- falsifier for any future candidate: wrong isolated width, mismatched
  active-pulse register acceptance or second-overflow waveform, or CPU
  reset with RSTE=0. No arbitrary overlap behavior is queued as hardware.
- self-check run: document/reference inspection only; no output model,
  hardware trace, native test or validation claim.
- state: **BLOCKED(SH7604 RSTE=0 WDTOVF active-pulse re-enable/retrigger trace)**.
  Unblock with a hardware trace or additional primary timing/decode
  documentation defining those transitions. Other implementation work
  continues; this is not a claim that all CPU-03 work is blocked.
- not covered: pulse callback/wiring, electrical drive/high-Z, external RES
  priority during a pending internal reset, reset-vector selection and
  active-reset save/load. Existing candidates remain UNVALIDATED.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0035 | CPU-03 | 0aec8567 | UNVALIDATED | INT64_MIN/-1 enters the existing DIVU overflow path without executing overflowing host signed division |

### IMPL-0035 — CPU-03 — DIVU signed-64 minimum guard

- branch/commit: `arena/01a0b897-mame` @ **0aec8567** (base: 557a609f).
- files: `src/devices/cpu/sh/sh7604.cpp`, `dvdntl_w` host-division guard;
  `saturn_pending/impl_checks/check_sh7604_divu_min64.py`.
- contract: starting 64/32 division with DVDNTH=80000000, DVDNTL=00000000
  and DVSR=FFFFFFFF must not evaluate host INT64_MIN/-1 or its remainder.
  It is a positive quotient overflow: set OVF and enter the existing
  overflow path. With OVFIE=0, DVDNTL is the documented positive saturation
  value 7FFFFFFF. No other overflow-result or operation-timing behavior
  is added by this safety guard.
- primary source: SH7604 ADE-602-085C Rev.4, section 10.3.1 p.292
  (signed 64/32 operation with 32-bit quotient), section 10.3.3 p.293
  (out-of-range quotient sets OVF; positive overflow saturates to 7FFFFFFF
  when OVFIE=0), section 10.4.2 p.294/Table 10.2 (sticky overflow and
  distinct intermediate-result requirements). SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:186-190,227-237`, guards
  this exact signed-64 pair and takes overflow, saturating by sign when
  interrupts are disabled. Blob `6b31b7d029449d63f68ef281dc04958d17d74339`.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1178-1187`, and fork base `557a609f`
  perform the host division before checking 32-bit quotient range.
  No reference code imported; the guard precedes that undefined operation.
- expected observable: no host arithmetic exception/UB on the initiating
  write; OVF=1, unchanged DVSR and OVFIE; with OVFIE=0, quotient=7FFFFFFF.
  In-range controls retain ordinary signed quotient/remainder and sticky
  old OVF. Exact register bits; six-cycle completion is NOT implemented
  or claimed by this change.
- suggested method: native longword writes to DVSR, DVDNTH and DVDNTL,
  then inspect DVCR and the disabled-interrupt quotient after completion.
  Repeat with old OVF both clear/set and OVFIE both ways; qualify enabled-
  interrupt intermediate results and vector delivery separately. Use
  fail-fast UBSan to expose host arithmetic before native qualification.
- falsifier: host division trap/UB, OVF remaining clear for this 64-bit
  pair, wrong disabled-interrupt positive saturation, or changed in-range
  division results rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `4 INT64_MIN/-1 cases; 65585 in-range quotient/remainder controls;
  65540 operand-state-copy replays; 5 zero-divisor status controls`.
  Pre-change `557a609f` method exits 1 under fail-fast UBSan:
  `runtime error: division of -9223372036854775808 by -1 cannot be represented
  in type 'long int'` (generated line 25). The independent in-range oracle
  uses 128-bit arithmetic; it does not assert unknown overflow intermediates.
  Twenty-three prior scripts exit 0; the unchanged `frt_stop`, `frt_phase`
  and `wdt_access` expectation conflicts remain at lines 438, 374, 132.
  Current total 27 SH7604 scripts: 24 exit 0, 3 exit 1. Warning-enabled TU
  syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes)
  and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new fields or save-layout change.
  The legacy overflow path still writes an inaccurate placeholder to
  DVDNTH and does not implement OVFIE=1 intermediate results. Other
  overflow signs/boundaries, 39/6-cycle latency, busy-access stalls,
  register aliases and native DIVU interrupt delivery remain incomplete.
  The distinct signed-32 minimum/-1 behavior is not inferred from this
  guard: pinned Ymir explicitly wraps it without new OVF, unlike a plain
  signed-range reading of the manual; see the next blocker entry. No
  native/MinGW qualification or complete DIVU claim. Frozen DMA, delay-slot
  IRQ, sound/game paths, validator assets and expected values untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0036 | CPU-03 | — | BLOCKED(SH7604 signed-32 minimum/-1 OVF and result trace) | Resolve the signed-32 boundary separately instead of assuming the signed-64 overflow rule applies |

### IMPL-0036 — CPU-03 — signed-32 DIVU boundary disagreement

- branch/base: `arena/01a0b897-mame` @ 0aec8567; no production change.
- files: `src/devices/cpu/sh/sh7604.cpp`, `dvdnt_w`; its host signed-32
  INT32_MIN/-1 expression is still unsafe and is explicitly not repaired
  by IMPL-0035.
- primary source: SH7604 ADE-602-085C Rev.4, sections 10.3.2/10.3.3
  pp.292-293 and Table 10.2 p.294 give general signed-range overflow rules
  but do not clearly resolve the reference's exact-zero-remainder boundary
  exception. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:139-146`, returns 80000000
  and remainder zero without setting new OVF for signed-32 minimum/-1.
  Its `tests/ymir-core-tests/src/hw/sh2/sh2_divu_tests.cpp:72-83` explicitly
  expects that result with OVFIE both clear and set, also distinguishing
  different 64-bit high words. Test blob
  `ad18c3f2b2b986f9e32315ddd3d6d653d4ab09cc`. Hardware provenance for that
  fixture was not established here; it is not treated as a silicon trace.
- expected observable to resolve: quotient, remainder and DVCR for
  80000000/FFFFFFFF via DVDNT, with OVFIE=0/1 and old OVF=0/1, plus the
  corresponding DVDNTH=FFFFFFFF/DVDNTL=80000000 64-bit form and nearby
  boundary/remainder controls. Values must come from a hardware trace or
  precise primary erratum, not C++ signed-overflow behavior.
- suggested method: execute on an SH7604 with operations separated by at
  least the documented 39 cycles; capture register state for both start
  registers, avoiding unrelated timing/alias assumptions.
- falsifier for a future candidate: disagreement in quotient, remainder
  or OVF with those captured boundary cases, or any host arithmetic trap.
- self-check run: primary/reference inspection only; no hardware capture.
- state: **BLOCKED(SH7604 signed-32 minimum/-1 OVF and result trace)**.
  A documented erratum or attributable hardware result can resolve the
  exception. Other DIVU work can continue without choosing it by guess.
- not covered: this blocker does not qualify Ymir's broader overflow
  algorithm or the current MAME output; the known unsafe expression remains
  a visible limitation, not an accepted hardware behavior.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0037 | CPU-03 | 8c231d4a | UNVALIDATED | Device reset clears DIVU DVCR.OVF and OVFIE without assigning dividend/divisor reset values |

### IMPL-0037 — CPU-03 — DIVU control reset image

- branch/commit: `arena/01a0b897-mame` @ **8c231d4a** (base: 0c09f1a4).
- files: `src/devices/cpu/sh/sh7604.cpp:242-246`;
  `saturn_pending/impl_checks/check_sh7604_divu_reset.py`;
  two shared reset-extraction mocks gain DIVU flag declarations only.
- contract: DVCR is initialized to zero by power-on or manual reset,
  clearing both overflow and its interrupt-enable bit. Module standby
  does not initialize DVCR. This candidate adds those flag assignments
  to generic device reset only; it does not assign documented-undefined
  reset values to dividend, divisor or vector registers.
- primary source: SH7604 ADE-602-085C Rev.4, section 10.2.3 p.290:
  DVCR=00000000 on power-on/manual reset, not initialized in standby or
  module standby; sections 10.2.1/10.2.2 pp.289-290 and 10.2.4-10.2.6
  pp.291-292 distinguish other registers' reset values. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:38-41,99-106`, clears
  DVCR flags during DIVU reset. Its chosen zero values for undefined
  registers are not imported. Blob
  `6b31b7d029449d63f68ef281dc04958d17d74339`. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp` device_reset, and fork base `0c09f1a4`
  do not reset these constructor-initialized/saved flags on later resets.
  No reference code imported.
- expected observable: after setting any combination of DVCR bits 1:0,
  device reset produces DVCR=00000000. Ordinary SCI/FRT module-stop
  entry/release must not clear DIVU flags. Exact bits; native reset-pin
  pulse timing and division completion latency are not asserted here.
- suggested method: set DVCR with legal longword/word access, perform
  power-on/manual reset and read it back; repeat after an actual overflow
  and with OVFIE set. Exercise module standby separately. Keep undefined
  dividend/vector initial values out of the reset oracle.
- falsifier: either DVCR bit surviving power-on/manual reset, or module
  standby alone clearing DVCR, rejects the corresponding contract.
- self-check run (method-level, unvalidated): new script exits 0:
  `64 DVCR full-reset images; 128 SCI/FRT module-stop retention controls;
  64 operand-state-copy replays`. Real device_reset/DVCR/SBYCR methods;
  base CPU and unrelated peripheral reset helpers are mocked. Pre-change
  `0c09f1a4` methods exit 1 at line 315, `d.dvcr_r()==0 && replay.dvcr_r()==0`.
  UBSan enabled; existing save registration checked. Twenty-four prior
  scripts exit 0; unchanged `frt_stop`, `frt_phase`, `wdt_access`
  expectation conflicts remain at lines 444, 380, 132. Current total 28
  SH7604 scripts: 25 exit 0, 3 exit 1. Warning-enabled TU syntax
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes) and
  `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new state fields/save-layout change;
  both flags already have save_item registration. Native reset entry,
  actual standby transitions, in-flight DIVU abort/busy behavior, interrupt
  delivery and actual save-manager replay remain unqualified. Undefined
  register values are deliberately not qualified as retained hardware
  values. Signed-32 boundary and WDTOVF blockers remain as recorded.
  Frozen DMA acknowledgement, delay-slot IRQ, sound/game paths, validator
  assets and existing expected values unchanged.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0038 | CPU-02 | 90a718b5 | UNVALIDATED | All seven BSC registers require one complete 32-bit write with A55A in the upper half |

### IMPL-0038 — CPU-02 — BSC keyed longword access

- branch/commit: `arena/01a0b897-mame` @ **90a718b5** (base: 011088c3).
- files: `src/devices/cpu/sh/sh7604.cpp`, BCR1/BCR2/WCR/MCR/RTCSR/RTCNT/
  RTCOR write handlers; `saturn_pending/impl_checks/check_sh7604_bsc_access.py`.
- contract: BSC writes are accepted only as complete 32-bit accesses with
  upper half A55A. Byte, word, other partial-mask and wrong-key writes
  leave the register unchanged, including separate key/payload words.
  Table 7.2's 16-bit accessibility is read-only, not permission to write
  the low word without the key. Existing accepted-write payload handling
  is unchanged by this gate.
- primary source: SH7604 ADE-602-085C Rev.4, section 7.1.4 p.134 and
  Table 7.2 notes 1/2: seven 16-bit registers, keyed 32-bit writes only;
  word reads use address+2. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1728-1762`, checks A55A before
  each of the seven writes; its word path `:1606-1614` forwards without
  fabricating the missing upper key, so a plain word cannot unlock them.
  Blob `9746b438b8a71de63ff65cd2d4325bc582a5114b`. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1373-1457`, and fork base `011088c3`
  only partially guard BCR1/BCR2, while other BSC writes are unguarded.
  No reference code imported.
- expected observable: writing 00001234 as a longword to WCR must leave
  its prior value, whereas A55A1234 reaches the existing payload handler.
  A word/byte write at the payload address cannot update WCR, MCR or a
  refresh register, even after an earlier valid keyed write. Exact
  register comparisons; no bus-grant or wait-cycle latency is asserted.
- suggested method: native stores of all three SH-2 widths to each BSC
  register, varying keys and both word halves. Include a split A55A/key
  sequence after valid commands, and controls for correctly keyed longwords.
  Inspect the architectural read masks separately from access rejection.
- falsifier: an unkeyed/partial write changing a BSC register, key reuse
  across accesses, or a complete valid-key command rejected solely by this
  guard contradicts the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `917504 partial-mask writes; 458745 wrong-key longwords;
  458752 existing valid-key dispatch controls; 14 split-key sequences`.
  Pre-change `011088c3` methods exit 1 at line 66,
  `unkeyed.m_wcr==0xaaff`. UBSan enabled. Twenty-five prior scripts exit 0;
  the unchanged `frt_stop`, `frt_phase`, `wdt_access` expectation conflicts
  remain at lines 444, 380, 132. Current working series: 29 SH7604 scripts,
  26 exit 0 and 3 exit 1. Warning-enabled TU syntax
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes) and
  `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new fields or save-layout change.
  Native lane dispatch, reserved lower-field masks, BSC reset defaults,
  upper-half readback, read-qualified RTCSR.CMF, refresh counting and bus
  timing/arbitration remain separate. In particular WCR/MCR still expose
  legacy stored upper key bits on reads; these write-gate controls preserve
  accepted-write storage, not an assertion that its readback is correct.
  No implementation of memory grants/waits is implied by register access
  handling. Frozen DMA acknowledgement, delay-slot IRQ, sound/game paths,
  validator assets and existing expected values unchanged.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0039 | CPU-02 | 80e493d5 | UNVALIDATED | BSC longword reads return zero above bit 15 rather than exposing retained write-key bits |

### IMPL-0039 — CPU-02 — BSC read width

- branch/commit: `arena/01a0b897-mame` @ **80e493d5** (base: c5853d00).
- files: `src/devices/cpu/sh/sh7604.cpp`, BCR1/BCR2/WCR/MCR read handlers;
  `saturn_pending/impl_checks/check_sh7604_bsc_read.py`.
- contract: BSC registers are 16 bits; a 32-bit read returns zero in the
  upper half. Mask those bits at the read boundary while retaining existing
  low-field behavior and BCR1's configured master/slave bit. The refresh
  register getters already narrow their result and remain unchanged.
- primary source: SH7604 ADE-602-085C Rev.4, section 7.1.4 p.134/Table 7.2:
  register size 16 bits, upper 16 bits zero on 32-bit reads; word reads at
  the listed longword address+2. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1240-1246`, returns the 16-bit
  BSC storage through the longword read path. Blob
  `9746b438b8a71de63ff65cd2d4325bc582a5114b`. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1368-1424`, and fork base `c5853d00`
  do not consistently narrow these getters; valid WCR/MCR writes leave
  A55A in their saved upper storage and expose it on subsequent reads.
  No reference code imported.
- expected observable: after A55A1234 is written to WCR, a longword read
  returns 00001234, not A55A1234. MCR similarly returns only its existing
  lower readable bits. BCR1 still reports master/slave configuration in
  bit 15, never in the high word. Exact bits; no bus latency assertion.
- suggested method: valid keyed writes followed by native longword and
  low-word reads, including save/load of state that retains upper key
  bits internally. Confirm that reads do not modify the register payload.
- falsifier: any BSC longword read exposing nonzero upper bits, incorrect
  lower values for legal field patterns, or changed master/slave indication
  rejects this read-width candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `3670016 raw-state read-width cases; 917504 keyed-write/read controls;
  917504 state-copy replays`. Lower reserved bits are kept zero and CMF
  clear so this is not an oracle for their separate write semantics.
  Pre-change `c5853d00` methods exit 1 at line 99,
  `key.wcr_r()==0x1234`. UBSan enabled. Twenty-six prior scripts exit 0;
  unchanged `frt_stop`, `frt_phase`, `wdt_access` expectation conflicts
  remain at lines 444, 380, 132. Current working series: 30 SH7604 scripts,
  27 exit 0 and 3 exit 1. Warning-enabled TU syntax
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes) and
  `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new fields/save-layout change. Saved
  internal storage is deliberately unchanged; upper bits are ignored at
  the architectural read boundary. Native byte/word lane routing, lower
  reserved-bit handling, reset defaults, CMF acknowledgement, refresh
  engine and bus timing/grants remain separate. Getter-level state-copy
  checks do not qualify native save-manager or debugger integration.
  Frozen DMA acknowledgement, delay-slot IRQ, sound/game paths, validator
  assets and existing expected values untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0040 | CPU-02 | f97d3a7e | UNVALIDATED | Cold BSC construction uses the documented BCR1/BCR2/WCR power-on image; warm reset policy is unchanged |

### IMPL-0040 — CPU-02 — cold BSC register image

- branch/commit: `arena/01a0b897-mame` @ **f97d3a7e** (base: 75c21d03).
  **Local only pending GitHub reconnection; push failed with authentication.**
- files: `src/devices/cpu/sh/sh7604.cpp:51`;
  `saturn_pending/impl_checks/check_sh7604_bsc_initial.py`.
- contract: newly constructed BSC register state uses BCR1=03F0,
  BCR2=00FC and WCR=AAFF. MCR, RTCSR, RTCNT and RTCOR already initialize
  to zero and remain so. BCR1's read-only master/slave indication continues
  to reflect the configured mode, giving 03F0 or 83F0. This is cold
  initialization only, not a new generic device-reset assignment.
- primary source: SH7604 ADE-602-085C Rev.4, section 7.1.4 p.134/Table 7.2
  (initial register image), section 7.2.1 p.136 (MASTER bit). Manual reset
  retains BSC settings, unlike power-on reset; that distinction must not
  be erased by blindly applying these values to every device_reset call.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:363-369`, assigns the same BSC
  initial values. Its wider reset-cause policy is not used as an oracle.
  Blob `9746b438b8a71de63ff65cd2d4325bc582a5114b`. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp` constructor BSC initializer list, and
  fork base `75c21d03:src/devices/cpu/sh/sh7604.cpp:51`, initialize these
  three registers to zero. No reference code imported.
- expected observable: at cold start before firmware programs the BSC,
  master/slave BCR1 reads 03F0/83F0, BCR2 reads 00FC, WCR reads AAFF,
  and MCR/RTCSR/RTCNT/RTCOR read zero. Exact register values; no timing
  claim for the wait states those register fields describe.
- suggested method: native fresh-device boot with firmware stopped before
  BSC writes, on both CPU configurations. Check saved initial state and
  reads before initial programming. Qualify later power-on and manual
  resets separately through a reset-cause-aware execution path.
- falsifier: any documented cold register value missing before programming,
  or wrong configured master/slave bit, rejects this initialization candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `14 cold BSC read images across master/slave selection; 2 state-copy controls`.
  It extracts the actual production constructor expressions and getters,
  not a native device instance. Pre-change `75c21d03` expressions/methods
  exit 1 at line 50, `d.bcr1_r()==(0x03f0|(slave?0x8000:0))`.
  UBSan enabled; existing save registrations checked. Twenty-seven prior
  scripts exit 0; unchanged `frt_stop`, `frt_phase`, `wdt_access`
  expectation conflicts remain at lines 444, 380, 132. Current working
  series: 31 SH7604 scripts, 28 exit 0 and 3 exit 1. Warning-enabled TU
  syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes)
  and `git diff --check` exit 0. No full build.
- state: UNVALIDATED; publication pending the connection blocker below.
- not covered / known doubts: no new fields or save-layout change; all
  seven BSC fields already have save_item registration. Native cold boot,
  generic-reset cause selection, later power-on reinitialization, manual
  reset retention/refresh suspension and bus timings remain unqualified.
  Generic device_reset is deliberately unchanged here: resetting BSC
  indiscriminately would destroy the required manual-reset retention.
  Frozen DMA acknowledgement, delay-slot IRQ, sound/game paths, validator
  assets and existing expected values unchanged.

### Publication blocker — 2026-09-19

- state: **BLOCKED(GitHub connection authentication for origin arena/01a0b897-mame)**.
- Last successful publication: **75c21d03**, including IMPL-0039 handoff.
- Next production commit **f97d3a7e** exists locally; the required
  `git push origin arena/01a0b897-mame` failed with
  `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- This handoff is also being committed locally. No history was rewritten,
  no alternate branch was used and no credentials were requested or stored.
- External unblock action: reconnect GitHub in Arena, then resume the
  explicit push to the same implementation branch. Publication of the
  newest candidate is not claimed until that push succeeds.
- Implementation work is paused at a clean committed checkpoint rather
  than accumulating more unpublishable changes. This is a delivery blocker,
  not evidence that remaining hardware work is complete or validated.

### Publication blocker resolved — 2026-09-19

- GitHub reconnection restored publication. The explicit push to
  `origin arena/01a0b897-mame` succeeded through **a860a91d**, including
  production **f97d3a7e** and the IMPL-0040 handoff.
- The authentication delivery blocker above is resolved; its historical
  failure record is retained. Implementation resumes on the same branch.
  No hardware validation state changes are implied.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0041 | CPU-02 | 9005dcb1 | UNVALIDATED | BCR2 returns only A3SZ/A2SZ/A1SZ; reserved bits 15–8 and 1–0 read zero |

### IMPL-0041 — CPU-02 — BCR2 reserved read bits

- branch/commit: `arena/01a0b897-mame` @ **9005dcb1** (base: 78d631ee).
- files: `src/devices/cpu/sh/sh7604.cpp`, `bcr2_r`;
  `saturn_pending/impl_checks/check_sh7604_bcr2_reserved.py`.
- contract: BCR2 exposes only its three two-bit area bus-size fields in
  bits 7–2. Reserved bits 15–8 and 1–0 always read zero, independently of
  retained internal storage. The read does not mutate stored data or
  alter the existing keyed-write gate.
- primary source: SH7604 ADE-602-085C Rev.4, section 7.2.2 pp.138–139,
  BCR2 bit layout and reserved-bit descriptions; section 7.1.4 p.134
  supplies the upper-half-zero rule already implemented by IMPL-0039.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1733-1736`, masks BCR2 writes
  to FC and returns the resulting storage at `:1241`. Blob
  `9746b438b8a71de63ff65cd2d4325bc582a5114b`. This candidate instead
  masks at the getter, preserving the existing saved representation.
  Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1387-1403`, returns raw BCR2; fork base
  `78d631ee` only narrows it to 16 bits. No reference code imported.
- expected observable: a getter over stored FFFF returns 000000FC,
  while each legal A1SZ/A2SZ/A3SZ encoding remains readable unchanged.
  Exact bits, not a claim that the selected bus widths/timings are modeled.
- suggested method: check native word/longword BCR2 reads after legal
  initialization; use controlled saved-state/debugger perturbation for
  reserved storage bits. Do not treat the robustness sweeps as permission
  to write reserved encodings or reprogram BCR2 after initialization.
- falsifier: any reserved bit reading as one, any legal size field being
  masked incorrectly, or a read changing storage rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `262144 raw-storage masks; 65536 keyed-write/read cases;
  262144 state-copy replays; 27 legal bus-size field combinations`.
  Pre-change `78d631ee` methods exit 1 at line 26,
  `polluted.bcr2_r()==0xfc`. UBSan enabled. Twenty-eight prior scripts
  exit 0; unchanged `frt_stop`, `frt_phase`, `wdt_access` expectation
  conflicts remain at lines 444, 380, 132. Current working series:
  32 SH7604 scripts, 29 exit 0 and 3 exit 1. Warning-enabled TU syntax
  (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes) and
  `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: no new state fields or save-layout change.
  Raw storage is intentionally unchanged. Native read-lane routing,
  bus-size execution, BSC reset causes and memory-grant timing remain
  unqualified. Reserved encodings and prohibited reconfiguration are
  not declared supported. Frozen DMA, delay-slot IRQ, sound/game paths,
  validator assets and existing expected values untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0042 | CPU-02 | df2780fe | UNVALIDATED | RTCSR.CMF requires a legal status read as one before a keyed zero write can clear it |

### IMPL-0042 — CPU-02 — RTCSR compare-match acknowledgement

- branch/commit: `arena/01a0b897-mame` @ **df2780fe** (base: 07a275a3).
- files: `src/devices/cpu/sh/sh7604.cpp:52,217,2175-2195`;
  `src/devices/cpu/sh/sh7604.h:200,297`;
  `saturn_pending/impl_checks/check_sh7604_rtcsr.py`. Shared BSC mock
  declarations and read-extraction signatures are adapted mechanically;
  existing expected values remain unchanged.
- contract: CMF cannot be set by software. A legal longword or low-word
  RTCSR read observing CMF=1 qualifies a subsequent keyed CMF=0 write.
  A successful clear consumes the qualification. Reading a clear flag
  removes old qualification; debugger inspection and an upper-word read
  do not change it. Rejected writes preserve history. CMIE/CKS retain
  their ordinary write behavior regardless of CMF acknowledgement.
- primary source: SH7604 ADE-602-085C Rev.4, section 7.2.5 p.146 gives
  the explicit read-one/write-zero clear condition and match set condition;
  section 7.2.7 p.148 says CMF clearing affects the interrupt, not the
  separate refresh request. Section 7.1.4 p.134/Table 7.2 defines permitted
  longword/low-word reads and keyed longword writes. The descriptive
  match/non-match labels in the p.146 bit table appear reversed; this
  candidate follows its explicit set/clear conditions, not those labels.
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- cross-checks: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1748-1752`, preserves CMF from
  software setting but explicitly leaves clear rules TODO. Blob
  `9746b438b8a71de63ff65cd2d4325bc582a5114b`. Saturn_MiSTer pinned
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/BSC.sv:998-1004,1030-1036`, directly assigns/reads the
  masked register without this read-history protocol. Blob
  `87400001ce983a1a02add311897fd482a90c00bb`. These omissions do not
  override the primary rule. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1426-1434`, and fork base `07a275a3`
  lack the qualification. No reference code imported.
- expected observable: a keyed CMF=0 write after an unread match leaves
  CMF set; a legal status read followed by that write clears it. A
  subsequent match needs a fresh read. Writing CMF=1 cannot synthesize a
  match. Upper-word/debugger reads cannot authorize clearing. Exact bits;
  no refresh-counter, memory-request or CMI-delivery timing claim.
- suggested method: generate a match with a native refresh engine when
  available, exercise longword and address+2 word reads, debugger peeks,
  ignored partial/wrong-key writes and save/load between read and clear.
  Observe the independent refresh request separately from the interrupt
  flag; this candidate does not implement the request engine.
- falsifier: unread CMF clearing, software setting CMF, invalid-lane or
  debugger reads qualifying a clear, consumed history clearing a later
  event, or lost qualification across save/load rejects the candidate.
- self-check run (method-level, unvalidated): new script exits 0:
  `128 CMF write cases; 128 state-copy replays;
  56 read-mask/debugger cases; 48 rejected-command controls`.
  Match events are seeded explicitly, not produced by a simulated refresh
  engine. Pre-change `07a275a3` methods, with read signature adapted only,
  exit 1 at line 33, `unread.rtcsr_r(0,0xffff)&0x80`. UBSan enabled.
  Twenty-eight prior scripts exit 0. **Four unchanged expectation conflicts
  remain visible:** `frt_stop` line 444, `frt_phase` line 380,
  `wdt_access` line 132, and now `bsc_access` line 98,
  `d.snapshot()==expected.snapshot()`. Its legacy valid-write storage
  control expects a software CMF set; that old behavior is superseded
  here, not silently retained or its expected value edited. Current working
  series: 33 SH7604 scripts, 29 exit 0 and 4 exit 1. Warning-enabled TU
  syntax (`-std=c++20 -Wall -Werror -Wno-sign-compare`, session includes)
  and `git diff --check` exit 0. No full build.
- state: UNVALIDATED
- not covered / known doubts: **save-state layout break**, new saved bool
  `m_rtcsr_read` with cold constructor initialization. Existing BSC storage
  and generic-reset behavior remain unchanged; warm power-on reinitialization
  and manual-reset read-history retention need cause-aware native qualification.
  Unsupported byte/partial reads are not qualified as architectural data
  accesses. Native lane dispatch, debugger integration and file-save replay
  remain open. Refresh counting, match production, independent refresh
  requests, CMI interrupt integration and memory grants are still absent/
  unqualified; no IRQ arbitration or DMA acknowledgement code was changed.
  Frozen delay-slot IRQ, sound/game paths and validator assets untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0043 | CPU-02 | — | BLOCKED(SH7604 RTCNT/RTCOR enable and equality-write timing trace) | Resolve refresh-counter comparison and first-edge semantics before choosing an event scheduler |

### IMPL-0043 — CPU-02 — refresh-counter timing boundary

- branch/base: `arena/01a0b897-mame` @ 0ceadeb3; no production change.
- files: `src/devices/cpu/sh/sh7604.cpp`, RTCNT/RTCOR/RTCSR handlers;
  `src/devices/cpu/sh/sh7604_bus.cpp`, separate unintegrated BSC device.
- known contract: SH7604 ADE-602-085C Rev.4 sections 7.2.5-7.2.7
  pp.146-148 specify clock selections, an 8-bit counter, comparison,
  CMF setting and counter clear on match. Section 7.5.7 pp.174-176
  describes starting from the current count, refresh requests waiting for
  the bus, replacement of an unserviced request and manual-reset count
  suspension. Section 7.1.1 p.130 permits interval-timer use separately
  from memory refresh. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- unresolved contract: the text calls comparison continuous, while the
  inspected implementation reference compares after an enabled increment.
  A preload equal to RTCOR, an equal RTCOR write, RTCOR=0, and enabling
  from a stopped equal state therefore need explicit observation. The
  first selected-clock edge relative to CKS enable and write/edge collision
  ordering also need evidence before a native deadline model is chosen.
- cross-checks: Saturn_MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/BSC.sv:965-978,1007-1016`, compares incremented RTCNT
  against RTCOR only at RT_CE and separately clears RFS_REQ on bus service.
  Blob `87400001ce983a1a02add311897fd482a90c00bb`. It does not supply CMF
  production/read qualification, so it is not a complete timing oracle.
  Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1748-1762`, is register storage
  with CMF rules TODO. Local `sh7604_bus.cpp` still lists timer-clock and
  bus-control TODOs and has fatal stubs for counter accesses; it is not
  a completed engine to wire in unchanged.
- expected observable to resolve: RTCNT and CMF sampled around successive
  selected-clock edges, including equal preloads and RTCOR=0, with MCR.RFSH=0
  to isolate counting from memory grants. Units: CPU/CKIO clocks; capture
  exact count/flag transition edges before assigning a timing tolerance.
- suggested method: hardware trace/test program using legal keyed writes,
  several enable phases and counter/compare values immediately below,
  equal to and above each other. Include writes between and coincident
  with count edges, and compare polling against an unpolled instance.
- falsifier for a future candidate: wrong first increment, match/clear
  edge, zero-compare period or active-write behavior against that capture.
- self-check run: primary/reference/source inspection only; no counter
  implementation, native test or hardware validation claim.
- state: **BLOCKED(SH7604 RTCNT/RTCOR enable and equality-write timing trace)**.
  Unblock with an attributable hardware capture or additional primary
  timing documentation. The selected-clock model must not be guessed
  merely because it matches the FPGA code.
- not covered: actual refresh grants/completion also depend on CPU-04 and
  BUS-01/02; an immediate nominal-time refresh is not an arbiter. CMI
  delivery and reset-cause handling are separate. This blocker does not
  prevent unrelated implementation work or alter existing candidates.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0044 | CPU-02 | ef70c104 | UNVALIDATED | OVFIE=0 strictly negative out-of-range 64/32 quotients saturate to 80000000 |

### IMPL-0044 — CPU-02 — negative quotient overflow saturation

- branch/commit/base: `arena/01a0b897-mame`; implementation `ef70c104`,
  base `c66f1816`. Production and independent method probe committed/pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:1870-1913`, `dvdntl_w`;
  `saturn_pending/impl_checks/check_sh7604_divu_saturation.py` (new).
- contract: for nonzero divisors with a finite signed-64 host quotient
  strictly less than INT32_MIN, the existing overflow path writes
  DVDNTL=80000000 when OVFIE=0, rather than the positive limit 7FFFFFFF.
  Positive saturation, OVFIE=1 legacy intermediates, overflow classification,
  sticky OVF, IRQ refresh and overflow remainder placeholder are unchanged.
  No new state fields; no save-state layout change in this candidate.
- primary source: SH7604 ADE-602-085C Rev.4, section 10.3.3 p.293 and
  section 10.4.2/Table 10.2 p.294; SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. Disabled-interrupt quotient
  saturation follows overflow sign; the remainder is an intermediate result,
  not the mathematical remainder. The latter is expressly NOT implemented
  by this change.
- cross-check: Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:208-237`, specifically
  228-234, selects signed saturation with OVFIE=0. Blob
  `6b31b7d029449d63f68ef281dc04958d17d74339`. Its exact-limit overflow
  classification at 193-200 differs from MAME, and its intermediate
  algorithm is not imported or used as a mathematical oracle here.
- provenance: existing local handler and IMPL-0035 host-overflow guard;
  upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1178-1209`, still uses 7FFFFFFF regardless
  of sign. This is a bounded source correction, not a reference-code port.
- expected observable: DVSR=00000001, DVDNTH=FFFFFFFF and DVDNTL=7FFFFFFF
  (signed dividend -2147483649), OVFIE=0, yield OVF=1 and DVDNTL=80000000.
  Units: exact 32-bit register words, zero bit tolerance after completion.
  Positive strict overflow remains 7FFFFFFF. Saturation does not clear
  pre-existing OVF. Primary latency is six CPU clocks, but this candidate
  does not implement/claim that latency or busy-access stalls.
- suggested measurement: isolated native SH7604 64/32 division program,
  legal 32-bit accesses, OVFIE=0, separating launch/readback by at least
  39 CPU clocks. Exercise both divisor signs and quotient signs, strict
  out-of-range values and undisputed in-range controls; capture DVCR and
  DVDNTL. Repeat with OVF initially set and cleared and across native saves.
  Do not use this probe's IRQ-refresh mock as evidence of interrupt delivery.
- falsifier: a strictly negative overflowing nonzero-divisor quotient with
  OVFIE=0 finishes with any DVDNTL value other than 80000000; or this change
  alters positive saturation, undisputed in-range results or sticky OVF.
- self-check run (method-level, unvalidated): actual handler extraction,
  signed-128 oracle and fail-fast UBSan: 49,414 negative saturations,
  49,088 positive saturation controls, 65,412 in-range results, 98,502
  enabled-overflow status controls, 262,416 operand-state-copy replays;
  exit 0. Enabled-overflow outputs and overflow remainders have NO hardware
  oracle assertions. Exact-limit detection ambiguities are excluded.
  Historical `c66f1816` source fails the first targeted negative-overflow
  observation (generated line 56); it still returns 7FFFFFFF.
  Prior 33 SH7604 scripts: 29 exit 0, four unchanged conflicts. Including
  the new script: 34 scripts, 30 exit 0 and four conflicts, NOT qualification.
  Conflict locations: frt_stop:444, frt_phase:380, wdt_access:132,
  bsc_access:98. Expectations unchanged; no validator assets edited.
  Warning-enabled C++20 TU syntax-only check and `git diff --check`: exit 0.
  No full build or native validation was run.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: divisor zero, signed-32 minimum/-1 (IMPL-0036),
  exact-limit overflow detection with/without nonzero remainder, OVFIE=1
  intermediate quotient, all overflowing intermediate remainders, cycle
  timing, busy stalls, mapped access widths, actual IRQ delivery and native
  save/load execution. INT64_MIN/-1 retains the IMPL-0035 guard and legacy
  positive result; it is a regression control, not this correction's target.
  Operand-object copies are not native save-manager tests. No frozen DMA,
  delay-slot, sound, video or title-specific paths changed.

### IMPL-0044 metadata correction (append-only)

The parent printed as CPU-02 in the preceding IMPL-0044 table/heading is
an indexing error: DIVU belongs to **CPU-03**, consistent with IMPL-0035
and IMPL-0037. IMPL-0044, its implementation commit `ef70c104`, contract
and UNVALIDATED status are unchanged. No milestone ID is renamed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0045 | CPU-03 | — | BLOCKED(SH7604 VCRDIV bits 15-7 readback capture or erratum) | Resolve documented reserved-zero readback versus deliberately retained word readback |

### IMPL-0045 — CPU-03 — VCRDIV reserved readback disagreement

- branch/base: `arena/01a0b897-mame` @ `921f938f`; no production edit.
- files: `src/devices/cpu/sh/sh7604.cpp:1777-1790`, VCRDIV handlers.
- contract in dispute: primary SH7604 ADE-602-085C Rev.4 section 10.2.4
  p.291 explicitly says bits 31-7 always read zero and writes should be
  zero. However, the same section depicts bits 15-0 as undefined-initial,
  read/write and says values can be set in all 16 bits, with only bits 6-0
  valid as a vector. Table 10.1 p.289 also labels the low 16 reset bits
  undefined. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
- upstream/fork provenance: upstream MAME commit
  `661381746bf01462df2c40f3567918293a70a379`, titled
  `cpu/sh/sh7604.cpp: fix BCR1/BCR2 and VCRDIV accessing`, deliberately
  changed the read mask from 007F to FFFF and added the word-readback
  comment. Its fetched commit message/patch does not identify a hardware
  capture or erratum. Pinned upstream `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1087-1099`, and the fork's baseline retain
  this behavior. Do not silently undo that deliberate change as a cleanup.
- pinned cross-checks: Ymir `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:66,113` defines uint16
  storage; `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1211,1661` reads/writes
  that word. Blobs `6b31b7d029449d63f68ef281dc04958d17d74339` and
  `9746b438b8a71de63ff65cd2d4325bc582a5114b`.
  Saturn_MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/DIVU.sv:178-179,234`, uses 16-bit VCRDIV readback;
  `rtl/SH/SH7604/SH7604_pkg.sv:366-369` has FFFF read/write masks.
  Blobs `09b259b5f91888dc0363884fd3b2c5d81644c118` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`. Agreement among these
  implementations does not prove silicon behavior or legalize reserved writes.
- expected observable to resolve: exact VCRDIV longword and low-word
  readback, especially bits 15-7, with vector extraction measured separately.
  Units: register bits; zero bit tolerance once the artifact establishes
  the contract. Valid writes with reserved bits zero cannot distinguish
  the two models after initialization.
- suggested measurement: attributable silicon readback capture including
  cold-start observations and a diagnostic reserved-bit sweep, both access
  widths, and accompanying chip/document revision. Reserved-bit injections
  are diagnostics only, not supported software programming sequences.
  Prefer an official correction specifying the readback mask if available.
- falsifier for a future candidate: retained bits 15-7 on hardware falsify
  an unconditional 007F read mask; consistently forced-zero behavior under
  an established applicable contract falsifies unconditional word readback.
- self-check run: primary, source and upstream-history inspection only;
  no new probe or production change and no native validation claim.
- state: **BLOCKED(SH7604 VCRDIV bits 15-7 readback capture or erratum)**.
- not covered: vector delivery, DIVU latency/overflow and reset value
  qualification. Existing 7-bit vector extraction and 16-bit readback are
  left intact; this is not a claim that either is verified.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0046 | CPU-03 | 27072eb9 + 7ad836e5 | UNVALIDATED | Device reset clears IPRA/IPRB and all five decoded interrupt-priority levels |

### IMPL-0046 — CPU-03 — INTC priority reset image

- branch/commit/base: `arena/01a0b897-mame`; production and new probe
  `27072eb9`, additional declaration-only mock adapter `7ad836e5`;
  base `7f2026e5`. Both commits pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:220-229`, `device_reset`;
  `saturn_pending/impl_checks/check_sh7604_intc_priority_reset.py` (new);
  existing `check_sh7604_frt_stop.py` and `check_sh7604_module_stop.py`
  gain declarations for IPRA and the decoded-priority struct only.
- contract: RES-style device reset writes IPRA=IPRB=0000 and clears all
  five cached priorities (DIVU, DMAC, WDT, SCI, FRT) before peripheral
  reset helpers run. Priority writers/getters and peripheral module-stop
  retention are unchanged. No new arbiter call, IRQ selection policy,
  acknowledgement rule or delay-slot path is added or changed.
- primary source: SH7604 ADE-602-085C Rev.4 sections 5.3.1-5.3.2
  pp.88-90, Table 5.5 p.90; SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. Both registers initialize
  to 0000 on power-on and manual reset; standby does not initialize them.
  IPRA fields decode DIVU/DMAC/WDT and IPRB fields decode SCI/FRT.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/INTC.sv:251-267` resets IPRA/IPRB on RST_N and RES_N;
  `rtl/SH/SH7604/SH7604_pkg.sv:13,23` defines both initial values as zero.
  Blobs `3018e750e3ff0c10b1bad5e7ca3f12ba67461301` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`. INTC.sv:154-170 uses
  these registers in priority selection. This supports reset values, not
  native MAME ordering/interrupt equivalence.
- provenance: existing local IPRA/IPRB writer decoding and constructor
  initializers; upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-211`, omits INTC priority reset.
  Inspected upstream file history contains no replacement reset engine.
  No external implementation was imported.
- expected observable: after programming IPRA=FED0 and IPRB=CB00, a
  device reset yields both reads 0000 and decoded priorities all zero.
  Units: exact 16-bit words and 4-bit priority fields; zero bit tolerance
  once reset is complete. Subsequent legal writes restore their decoded
  levels. Entering/releasing SCI/FRT module stop without reset retains
  the programmed priorities. No cycle-accurate reset-edge tolerance claimed.
- suggested measurement: native master/slave SH7604 register probe using
  legal INTC accesses, external reset assertion/release and reprogramming;
  repeat across save/load with nonzero priorities. Qualify delivery with
  isolated source flags and SR masks separately. Check system standby
  separately from the method probe's peripheral module-stop controls.
- falsifier: IPRA/IPRB or any derived priority retains a nonzero value
  after completed power-on/manual reset; a later write fails to restore
  the matching field; or module-stop entry unexpectedly clears them.
- self-check run (method-level, unvalidated): actual device-reset,
  IPRA/IPRB read/write and SBYCR methods, mocked base reset/peripheral
  helpers/IRQ refresh, fail-fast UBSan: 262,144 reset images, 524,288
  module-stop retention controls, 524,288 reprogramming controls and
  262,144 operand-state-copy replays; exit 0. Existing save registrations
  checked for both registers and all five derived fields. Historical
  `7f2026e5` source fails the first reset observation (generated line 318).
  Warning-enabled C++20 TU syntax-only check and diff whitespace check:
  exit 0. No full build or native qualification.
  Selected prior 34-script series initially reported 29 exit 0, four
  expectation conflicts and one module-stop mock compilation failure:
  missing IPRA/decoded-priority declarations. Commit `7ad836e5` adds only
  those declarations; module_stop then exits 0 with its expectations
  untouched. Resulting selected series including this new probe: 35
  scripts, 31 exit 0, four unchanged semantic conflicts (frt_stop now
  generated line 449, frt_phase 385, wdt_access 132, bsc_access 98).
  No existing assertion/expected value or validator asset changed.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: native reset-cause delivery, WDT-generated
  internal reset, system standby, live native save/load, INTC vector/ICR
  reset images, NMI edge selection and actual interrupt arrival/order.
  No new saved fields or save-layout change. Clearing the already-saved
  priority cache avoids stale nonzero levels; it is not a claim that the
  overall interrupt controller or DMA behavior is qualified. Frozen DMA
  acknowledgements and delay-slot IRQ implementation remain untouched.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0047 | CPU-03 | 4b1e7720 | UNVALIDATED | Device reset clears VCRA-D/VCRWDT and the three decoded FRT vectors |

### IMPL-0047 — CPU-03 — documented INTC vector reset image

- branch/commit/base: `arena/01a0b897-mame`; implementation `4b1e7720`,
  base `44382a5b`. Production, new method probe and mechanical mock
  declarations committed/pushed together.
- files: `src/devices/cpu/sh/sh7604.cpp:229-232`, `device_reset`;
  `saturn_pending/impl_checks/check_sh7604_intc_vector_reset.py` (new);
  declaration-only additions to existing `check_sh7604_frt_stop.py` and
  `check_sh7604_module_stop.py`. No existing expectations changed.
- contract: device reset initializes VCRA, VCRB, VCRC, VCRD and VCRWDT
  to 0000 and clears cached FRT ICI/OCI/OVI vector numbers. The reset
  assignments precede peripheral reset helpers. Peripheral module-stop
  retention and vector writes/readback are unchanged. VCRDIV/VCRDMA and
  their decoded vector fields are deliberately not assigned a new reset
  value. No new IRQ refresh, arbitration or acknowledgement behavior.
- primary source: SH7604 ADE-602-085C Rev.4 sections 5.3.3-5.3.7 pp.91-94,
  Table 5.6 pp.94-95 and reset statement p.95; SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. These five registers reset
  to 0000 and are not initialized in standby. Sections 9.2.5 pp.241-242
  and 10.2.4 p.291/Table 10.1 p.289 separately specify undefined initial
  vector bits for VCRDMA and VCRDIV; those are not zero-reset targets here.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/INTC.sv:253-272` initializes these five registers on
  RST_N and RES_N. `rtl/SH/SH7604/SH7604_pkg.sv:34,45,56,67,77`
  defines their initial values as zero. Blobs
  `3018e750e3ff0c10b1bad5e7ca3f12ba67461301` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`.
- provenance: local vector handlers already decode FRT vectors into saved
  fields; constructor initializes registers/caches once, but the reset
  handler omitted them. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-211`, likewise omits these vector
  resets. No external code imported or fork history rewritten.
- expected observable: program five nonzero legal vector words, assert
  and release reset, then read each as 0000. After re-enabling a FRT
  source, its decoded vector must no longer be the pre-reset value unless
  software reprograms it. Units: exact 16-bit words and 7-bit vector
  fields, zero bit tolerance after reset completion. No reset-edge timing
  or actual exception-delivery latency is established by this candidate.
- suggested measurement: native master/slave SH7604 register test with
  power-on/manual reset, legal writes, post-reset reads and reprogramming;
  isolated FRT/SCI/WDT sources and native save/load as separate delivery
  checks. Avoid interpreting undefined DIVU/DMAC vector values as zeros.
  Check whole-chip standby independently of peripheral module stop.
- falsifier: any of the five documented zero-reset vector registers or
  cached FRT vectors retains the programmed nonzero value after completed
  reset; reprogramming fails to select the written vector; or module stop
  unexpectedly clears the INTC vector registers.
- self-check run (method-level, unvalidated): actual reset, five pairs of
  vector read/write handlers and SBYCR handler, fail-fast UBSan; 262,144
  five-register reset images, 524,288 module-stop retention controls,
  524,288 reprogramming controls and 262,144 operand-state-copy replays;
  exit 0. Existing register/cache save registrations checked. Historical
  `44382a5b` source fails the first reset observation (generated line 351).
  Prior selected 35-script series: 31 exit 0/four conflicts. Including
  this new probe: selected 36-script series, 32 exit 0/four unchanged
  semantic conflicts: frt_stop generated line 454, frt_phase 390,
  wdt_access 132, bsc_access 98. No expected values or validator assets
  changed. Warning-enabled C++20 TU syntax-only and `git diff --check`:
  exit 0. No full build or native validation.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: base CPU/peripheral reset helpers and IRQ
  refresh are mocked; native reset routing, WDT internal reset, system
  standby, live save/load and actual interrupt vectors/delivery remain
  unqualified. ICR reset/NMI behavior and VCRDIV readback disagreement
  remain separate. No new saved state or layout change. No changes to
  frozen DMA acknowledgement, delay-slot IRQ, sound or video paths.

### Workspace-history recovery before IMPL-0048

On resuming, local HEAD was the session base `82152a8b`, with the prior
implementation restored as working files. The published session branch
still pointed to `1f973e3d`. Fetched that branch and compared all 49 paths
changed since the base against the published tip: all matched byte-for-byte,
including handoff/probes. Restored the same local branch/index to that tip
with a mixed reset, leaving working-file contents intact; resulting status
was clean. No published history was rewritten and no other branch used.
Temporary reference files had not survived and were retrieved again by
pinned GitHub blob identity. No downloaded reference/build files committed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0048 | CPU-03 | 663eedba | UNVALIDATED | Device reset clears ICR.NMIE/VECMD and their decoded mode flags without overwriting NMI input state |

### IMPL-0048 — CPU-03 — INTC control reset image

- branch/commit/base: `arena/01a0b897-mame`; implementation `663eedba`,
  base `1f973e3d`; committed and pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:224-227`, `device_reset`;
  `saturn_pending/impl_checks/check_sh7604_intc_control_reset.py` (new);
  declaration-only additions to existing `check_sh7604_frt_stop.py` and
  `check_sh7604_module_stop.py`. Their assertions remain unchanged.
- contract: reset clears the ICR control backing word and both cached
  flags, NMIE and VECMD. The reset control selection is falling-edge NMI
  detection and auto-vector IRL mode. This does NOT implement or qualify
  NMI edge detection: only its stored control selection is corrected.
  NMIL remains synthesized by the existing getter from the input state;
  this change does not overwrite the input or change its polarity mapping.
- primary source: SH7604 ADE-602-085C Rev.4 section 5.3.8 pp.95-96,
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`. ICR resets to
  8000 or 0000 depending on NMI input level, with NMIE/VECMD zero;
  standby does not initialize ICR. Bit 15 is read-only input-level status.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/INTC.sv:253-274` resets ICR and separately samples NMIL
  from NMI_N on RES_N; `rtl/SH/SH7604/SH7604_pkg.sv:80-89` defines the
  fields and zero ICR_INIT. Blobs
  `3018e750e3ff0c10b1bad5e7ca3f12ba67461301` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`. This supports the reset
  control bits, not the accuracy of MAME's NMI input abstraction.
- provenance: existing local ICR writer decodes two saved flags; constructor
  initializes them once, but device reset omitted them. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-211`, also omits this reset. Existing
  upstream/fork reset history was inspected during IMPL-0046/0047; no
  external implementation imported. Base SH2 reset leaves NMI line state
  intact (`src/devices/cpu/sh/sh2.cpp:85-109`); that code is not changed.
- expected observable: after programming ICR controls to 0101, completed
  power-on/manual reset yields ICR & 0101 = 0000 and both cached flags
  false. NMIL may read either 8000 or 0000 according to input. Units:
  exact register bits, zero bit tolerance after reset completion. Later
  legal writes restore either control bit. Peripheral module stop without
  reset retains them. No pin-edge or interrupt-delivery latency claimed.
- suggested measurement: native master/slave SH7604 ICR programming and
  reset/readback test with separately controlled NMI level, no coincident
  NMI transition; repeat writes and save/load. Qualify actual edge selection,
  IRL external-vector fetch and system standby separately.
- falsifier: NMIE/VECMD or their cached flags remain set after completed
  reset, readback no longer reflects the held NMI level, or subsequent
  legal writes cannot restore the controls. A module-stop entry clearing
  these INTC controls would also contradict the candidate's retention scope.
- self-check run (method-level, unvalidated): actual reset/ICR/SBYCR methods,
  mocked CPU/peripheral reset helpers and IRQ refresh, fail-fast UBSan;
  128 reset images, 256 module-stop retention controls, 256 reprogramming
  controls and 128 operand-state-copy replays; exit 0. Two input states
  exercise preservation of the existing NMIL mapping, not silicon pin
  timing. Existing save registrations checked. Historical `1f973e3d`
  source fails the first reset observation (generated line 317).
  Prior selected 36-script series: 32 exit 0/four conflicts. Including this
  probe: selected 37-script series, 33 exit 0/four unchanged semantic
  conflicts (frt_stop generated line 459, frt_phase 395, wdt_access 132,
  bsc_access 98). Expectations and validator assets untouched.
  Warning-enabled C++20 TU syntax-only and `git diff --check`: exit 0.
  No full build or native qualification.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: the getter's NMI polarity TODO and lack of
  NMIE-dependent delivery remain; no delay-slot, arbitration, DMA ack or
  external vector-fetch handler changes. Native reset routing, WDT internal
  reset, whole-chip standby and live save/load remain unqualified. No new
  saved fields or layout change. No frozen sound/video/title paths edited.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0049 | CPU-02 | e48a54e9 | UNVALIDATED | Device reset restores CCR=00 without treating reset as a cache purge |

### IMPL-0049 — CPU-02 — cache-control register reset image

- branch/commit/base: `arena/01a0b897-mame`; implementation `e48a54e9`,
  base `05d0801f`; committed and pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:229-231`, `device_reset`;
  `saturn_pending/impl_checks/check_sh7604_ccr_reset.py` (new);
  existing `check_sh7604_frt_stop.py` and `check_sh7604_module_stop.py`
  gain one CCR backing-field declaration each. No expectation changes.
- contract: device reset writes CCR=00, restoring the documented control
  image, including CE=0 (cache disabled). It does not clear cache arrays,
  valid bits or LRU state or implement a purge. Existing CCR byte access
  handlers and SCI/FRT module-stop behavior are unchanged.
- primary source: SH7604 ADE-602-085C Rev.4 section 8.2/Table 8.1 and
  bit definitions pp.214-215 establish CCR's 00 initial image. Section
  8.4.6 p.224 explicitly says CE clears on power-on/manual reset; section
  8.5.1 p.226 says cache memory is NOT initialized by reset and requires
  software initialization. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. Section 8.5.5 p.229 requires
  CCR reconfiguration with the cache disabled. No purge algorithm is inferred
  from the inconsistent first sentence about CP's write value in 8.4.6;
  purge is outside this candidate.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/CACHE.sv:409-418`, clears CCR on both RST_N and RES_N;
  `rtl/SH/SH7604/SH7604_pkg.sv:92-104` defines the fields and CCR_INIT=00.
  Blobs `31bfe3c5b81fd357ab68bf2a66c7c34032796674` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`. Reference purge/read-mask
  details at CACHE.sv:419-427 are not used as a cache-behavior oracle.
- provenance: local constructor initializes CCR once, but device reset
  omitted it; upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-211`, has the same omission. Local
  reset history reviewed; no external implementation imported. This is
  register-state work, not completion of the CPU-02 cache engine.
- expected observable: after nonzero CCR control programming, completed
  reset yields CCR readback 00, particularly CE=0, independent of prior
  W/TW/OD/ID selection. Units: exact 8-bit register image, zero bit
  tolerance after reset completion. SCI/FRT module stop alone retains CCR.
  There is no claimed hit/miss, fill, purge or reset-edge cycle result.
- suggested measurement: native SH7604 byte-access program in cache-through
  space, properly initializing the cache before any enabled-cache execution,
  writes documented CCR controls then asserts/releases reset and reads CCR.
  Reprogram from disabled state; repeat on master/slave and across native
  saves. Check cache-array retention and CPU-engine timing separately.
- falsifier: CCR retains a programmed nonzero control bit after completed
  reset, later legal writes cannot restore the controls, or SCI/FRT module
  stop unexpectedly clears them. A claim that this change purges native
  cache memory would exceed its implemented contract.
- self-check run (method-level, unvalidated): actual device-reset, CCR and
  SBYCR methods with mocked base/peripheral reset helpers, fail-fast UBSan;
  1,024 reset images, 2,048 SCI/FRT module-stop retention controls, 2,048
  reprogramming controls and 1,024 operand-state-copy replays; exit 0.
  The register sweep covers 64 non-purge, reserved-zero configurations;
  it does not execute code through a populated cache. Existing CCR save
  registration checked. Historical `05d0801f` source fails the first
  CE-reset observation (generated line 321).
  Prior selected 37-script series: 33 exit 0/four conflicts. Including
  this new probe: selected 38-script series, 34 exit 0/four unchanged
  semantic conflicts: frt_stop generated line 464, frt_phase 400,
  wdt_access 132, bsc_access 98. No expectations/validator assets changed.
  Warning-enabled C++20 TU syntax-only and `git diff --check`: exit 0.
  No full build or native qualification.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: native reset-cause delivery, cache arrays/tags/
  valid/LRU state, CP action, associative purges, replacement, RAM mode,
  DRC/interpreter cache integration, bus contention, DMA visibility,
  whole-chip standby and live save/load. No new state fields or save-layout
  change. Frozen DMA/IRQ-delay-slot/sound/video paths remain unchanged.

### Published-history reconciliation before IMPL-0050

The restored local checkout again had HEAD `82152a8b` and the prior session
files as working changes. This time the fetched session branch pointed to
`b6ecabd4`, not the previously recorded `cfdc3e08`; the latter object was
not available locally after fetching. Published commits have different IDs
and additional baseline changes outside this task. No cause is inferred.
All 51 session source/handoff/probe/inventory files compared byte-for-byte
against `b6ecabd4`: no differences. The 104 paths different from the restored
base had no added-file content collisions and no validator evidence/consumer
changes. Non-session differences were in files clean relative to the old
local base. Aligned those clean baseline paths to the published tree, then
restored this same session branch/index to `b6ecabd4`; status was clean.
No force push, published-history rewrite, other branch or validator edit.

Prior entries remain historical records, not rewritten. Current published
counterparts for the most recent production changes are:
- IMPL-0044: `760ef54e` (previously recorded `ef70c104`).
- IMPL-0046: `5c7463f8`, adapter `a924a61a` (previously `27072eb9`, `7ad836e5`).
- IMPL-0047: `ecf1a846` (previously `4b1e7720`).
- IMPL-0048: `780c7b65` (previously `663eedba`).
- IMPL-0049: `fbfcb4ac` (previously `e48a54e9`).
These associations follow published commit subjects and matching cumulative
session files, not a new native qualification. Validators should use the
current published ancestry; do not assume old object IDs are fetchable.
IMPL-0050 checks below were run after alignment, against that current tree.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0050 | CPU-03 | 5472ec1b | UNVALIDATED | Device reset restores DRCR0/1 to external DREQ selection 00 |

### IMPL-0050 — CPU-03 — DMA request-selection reset

- branch/commit/base: `arena/01a0b897-mame`; implementation `5472ec1b`,
  base `b6ecabd4`; committed and pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:250-251`, reset loop;
  `saturn_pending/impl_checks/check_sh7604_drcr_reset.py` (new);
  declaration-only mock additions to `check_sh7604_frt_stop.py` and
  `check_sh7604_module_stop.py`. No expectations changed.
- contract: reset writes both DMA request/response selection registers to
  00 (external DREQ). It does not retain prior RXI/TXI selections. Existing
  byte read/write handlers and peripheral module-stop retention remain
  unchanged. No DMA request consumer, transfer, timer, acknowledgment,
  arbitration or delay-slot handler is modified.
- primary source: SH7604 ADE-602-085C Rev.4 section 9.2.6 p.242;
  SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`. DRCR0/1 initialize
  to 00 on reset and retain values in module standby. RS=00 selects DREQ,
  01 RXI and 10 TXI; 11 is prohibited. Software changes request source
  only with CHCR.DE=0. Tests do not exercise the prohibited encoding or
  programming a live channel.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/DMAC.sv:390-404` resets DRCR0/1 on RST_N and RES_N;
  `rtl/SH/SH7604/SH7604_pkg.sv:429-436` defines the two-bit field and
  DRCRx_INIT=00. Blobs `94dbebc90f68f342a6d3f31cd63bad7ffe8e3cf7` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`. Nearby simulation-only
  DMAOR.DME overrides are not used as a hardware reset oracle.
- provenance: local constructor initializes DRCR once, but the reset loop
  omitted it. Upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-211`, has the same omission. Current
  fork reset history reviewed; no reference implementation imported.
- expected observable: with channels disabled, byte-program DRCR0=01 and
  DRCR1=02; completed power-on/manual reset yields 00 from both byte reads.
  Reprogramming either channel must not change the other. Units: exact
  8-bit register values, zero bit tolerance after reset completion. SCI/FRT
  module-stop entry/release without reset retains the selections. This
  does not imply that SCI DMA request delivery is implemented.
- suggested measurement: native master/slave SH7604 byte-access probe at
  FFFFFE71/FFFFFE72 with DE=0, reset assertion/release and readback, then
  per-channel reprogramming. Repeat across native saves; measure live
  DREQ/RXI/TXI routing and in-flight reset behavior separately.
- falsifier: either selector retains 01/02 after completed reset, module
  stop clears it, or writing one idle channel changes the other's selector.
- self-check run (method-level, unvalidated): actual reset, DRCR template
  read/write and SBYCR methods, mocked base/peripheral reset and IRQ refresh,
  fail-fast UBSan; 144 paired reset images, 288 module-stop retention
  controls, 288 channel-independent reprogramming controls and 144
  operand-state-copy replays; exit 0. Existing DRCR array-member save
  registration checked. Historical `b6ecabd4` source fails the first reset
  observation (generated line 319).
  Prior selected 38-script series: 34 exit 0/four conflicts. Including
  this new probe: selected 39-script series, 35 exit 0/four unchanged
  semantic conflicts (frt_stop generated line 467, frt_phase 403,
  wdt_access 132, bsc_access 98). Expectations/validator assets untouched.
  Warning-enabled C++20 TU syntax-only and `git diff --check`: exit 0.
  No full build or native qualification.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: CHCR/DMAOR reset images, stale DMA deadlines,
  reset while transferring/stalled, halt release, source routing and SCI
  request pacing remain separate. Native reset/standby/save handling and
  actual acknowledgments remain unqualified. No new fields or save-layout
  change; no frozen DMA acknowledgement, IRQ-delay-slot or sound/video edits.

### IMPL-0050 line-reference clarification (append-only)

At `5472ec1b`, the DRCR reset assignment is line 253; the preceding entry's
250-251 span points at the reset-loop opener, not the assignment itself.
No contract, implementation identity or state change.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0051 | CPU-03 | 2f6a6e11 | UNVALIDATED | Device reset clears CHCR0/1 and DMAOR and cancels queued DMA callbacks so reset cannot become a late transfer-end event |

### IMPL-0051 — CPU-03 — DMAC reset controls and stale completion cancellation

- branch/commit/base: `arena/01a0b897-mame`; implementation `2f6a6e11`,
  base `da165176`; committed and pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:250-267`, reset loop;
  `saturn_pending/impl_checks/check_sh7604_dmac_reset.py` (new);
  declaration-only mock expansions in `check_sh7604_frt_stop.py` and
  `check_sh7604_module_stop.py`. Existing expectations untouched.
- contract: completed device reset leaves CHCR0/CHCR1/DMAOR at 00000000
  and no pre-reset DMA callback scheduled. Existing reset already clears
  active counts and IRQ-pending bookkeeping; the old timer could otherwise
  call `sh2_do_dma` with that zero count and spuriously set TE afterward.
  Cancel both channel deadlines as part of the same reset transition.
  This is reset handling, not a change to the live transfer, acknowledgment,
  IRQ-arbitration or delay-slot algorithms. Undefined SAR/DAR/TCR and vector
  reset contents are not assigned a new value by this change.
- primary source: SH7604 ADE-602-085C Rev.4 section 9.2.4 p.237 gives
  CHCR0/1 reset value 00000000, including DE/TE/IE=0; section 9.2.7
  pp.243-244 gives DMAOR=00000000, including DME/AE/NMIF=0. Section
  9.3.8 pp.283-284 distinguishes normal transfer completion from stopping
  transfers. Sections 9.2.1-9.2.3 pp.235-236 describe undefined reset
  operand/count registers. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. No hardware bus-cycle
  collision ordering or reset recognition delay is inferred from these
  register statements.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/DMAC.sv:186-200` resets CHCR and bus-work flags on RST_N;
  lines 390-410 reset DMAOR on RST_N/RES_N. Package
  `rtl/SH/SH7604/SH7604_pkg.sv:406,427` gives both zero initial values.
  Blobs `94dbebc90f68f342a6d3f31cd63bad7ffe8e3cf7` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`. Divergences: the inspected
  CHCR reset block has no matching RES_N arm, and simulation-only code
  overrides DMAOR.DME to one. Neither divergence is treated as a hardware
  oracle; the primary reset contract governs. No FPGA bus logic imported.
- provenance: local reset cleared active counts but not timers/control
  registers; the unchanged completion arm sets TE when invoked with count
  zero. Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:180-211`, has the same reset omission.
  The current fork's reset/start/completion code was inspected before this
  change. Framework `src/emu/diexec.cpp:415-425` handles CPU suspension
  release before device reset; no extra HALT release is introduced here.
- expected observable: after completed reset, CHCR0/1 and DMAOR read zero
  and remain zero without new software setup, even after the old scheduled
  DMA deadline. No old callback may set TE, create a completion request or
  perform a memory access. Units: exact register bits and zero stale events;
  zero bit/event tolerance after reset completion. Reprogrammed fresh DMA
  must still run through the existing path. Existing two-clock callback
  scheduling is only a regression control, not a timing qualification.
- suggested measurement: native master/slave SH7604 reset during queued
  transfer work and before a queued completion, then observe beyond the old
  deadline with no new DMA programming. Capture CHCR/DMAOR and memory bus
  writes/IRQ requests; separately reset endpoint-stalled channels. Reprogram
  fresh transfers and repeat across native save/load. Exclude exact reset/
  bus-cycle collisions until their ordering is independently established.
- falsifier: CHCR/DMAOR remains nonzero after completed reset, a pre-reset
  event later raises TE or accesses memory, or fresh transfers cannot start
  after legal reprogramming. Native reset reintroducing a pending callback
  through save/load also falsifies the intended cancellation contract.
- self-check run (method-level, unvalidated): actual reset, CHCR/DMAOR
  handlers, start/check, transfer and timer-callback methods; mocked memory,
  scheduler, CPU suspend/resume, peripheral resets and IRQ refresh. Fail-fast
  UBSan: 72 queued-transfer/queued-completion/seeded-stall reset cases,
  144 quiet post-reset intervals, 144 fresh-transfer controls, 72 state-copy
  replays, eight no-reset completion controls and 16 seeded flag images;
  exit 0. Seeded TE/AE/NMIF do not assert software-settable status flags.
  Historical `da165176` fails the reset-control observation (generated
  line 633). A temporary mutant retaining register clears but deleting
  deadline cancellation fails after the stale callback sets TE (generated
  line 637). Neither historical source nor mutant is committed.
  Prior selected 39-script series: 35 exit 0/four conflicts. Including
  this new probe: selected 40-script series, 36 exit 0/four unchanged
  semantic conflicts (frt_stop generated line 474, frt_phase 410,
  wdt_access 132, bsc_access 98). Expectations/validator assets untouched.
  Warning-enabled C++20 TU syntax-only and `git diff --check`: exit 0.
  No full build or native qualification.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: native reset recognition, in-progress physical
  bus-cycle completion, reset/event timestamp ties, HALT release, interrupt
  acknowledgement/order, endpoint pacing, whole-chip standby and native
  save/load. IRQ refresh is mocked, so pending-flag values in the probe
  are NOT an oracle for native acknowledgment consumption. The stall case
  seeds the existing stalled state; it does not model a real endpoint.
  No new device fields or save-layout change; existing timer objects and
  control-register save registrations remain. No frozen transfer/ack,
  delay-slot IRQ, sound or video handler changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0052 | CPU-03 | 63d1bf91 | UNVALIDATED | CHCR0/1 read bits 31-16 as zero without changing control/status storage or DMA side effects |

### IMPL-0052 — CPU-03 — CHCR reserved read bits

- branch/commit/base: `arena/01a0b897-mame`; implementation `63d1bf91`,
  base `8427e1aa`; committed and pushed.
- files: `src/devices/cpu/sh/sh7604.cpp`, `chcr_r` template;
  `saturn_pending/impl_checks/check_sh7604_chcr_reserved.py` (new).
- contract: CHCR reads expose only bits 15-0. Bits 31-16 are reserved and
  always zero on read. Mask only the returned value; do not mutate backing
  storage, TE, other channel state, write handling, transfer scheduling or
  interrupt acknowledgements. No new fields or save-layout change.
- primary source: SH7604 ADE-602-085C Rev.4 section 9.2.4 p.237 explicitly
  identifies the upper 16 bits as reserved/read-zero and requires writing
  zero there. Section 9.5 p.285 requires longword CHCR accesses. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`.
- pinned cross-check: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/DMAC.sv:447,451` masks both CHCR reads with CHCRx_RMASK;
  `rtl/SH/SH7604/SH7604_pkg.sv:405` defines it as 0000FFFF. Blobs
  `94dbebc90f68f342a6d3f31cd63bad7ffe8e3cf7` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`.
- provenance: local/fork getter and upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1613-1616`, return unmasked backing
  storage. Local history reviewed; no external implementation imported.
- expected observable: every CHCR longword read has upper half 0000 and
  preserves all 16 low control/status bits. At method level, raw backing
  FFFF5205 returns 00005205 and A55A0006 returns 00000006. These raw
  injections are robustness diagnostics, NOT permitted software writes or
  transfer configurations. Units: exact 32-bit words, zero bit tolerance.
- suggested measurement: native longword readback for both channels after
  legal disabled-channel programming, with independently produced TE status;
  instrumented backing-state injection can discriminate the missing mask
  without interpreting reserved-one writes as supported hardware use.
  Check native save/load separately. No byte/word access contract is added.
- falsifier: a read loses a meaningful low bit, changes TE or the other
  channel, or reads upper-half ones under an applicable documented hardware
  contract. An attributable erratum making upper bits meaningful would
  also invalidate this mask. Illegal-write results alone are not a legal
  programming contract.
- self-check run (method-level, unvalidated): actual template getters and
  writer, mocked DMA start/check, fail-fast UBSan; 524,288 raw-storage masks,
  524,288 state-copy replays and 288 disabled-channel write/status controls;
  exit 0. Raw sweeps exercise all low-word images and four upper-word
  patterns on both channels; prohibited low encodings are diagnostic only.
  Defined-field write controls use DE=0 and TE=1 writes to preserve seeded
  status, not software-set it. Historical `8427e1aa` source fails the first
  poisoned-backing read (generated line 54).
  Prior selected 40-script series: 36 exit 0/four conflicts. Including the
  new probe: selected 41-script series, 37 exit 0/four unchanged semantic
  conflicts (frt_stop generated line 474, frt_phase 410, wdt_access 132,
  bsc_access 98). Existing expectations and validator assets untouched.
  Warning-enabled C++20 TU syntax-only and `git diff --check`: exit 0.
  No full build or native qualification.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: native mapping/access widths, TE read-qualified
  clearing, live transfer timing, IRQ acknowledgement and save-manager
  behavior. No DMA consumer, arbitration or completion path changed; no
  frozen DMA acknowledgement, delay-slot IRQ, sound or video handler edits.

### IMPL-0052 source line anchor (append-only)

At implementation `63d1bf91`, `chcr_r` is at
`src/devices/cpu/sh/sh7604.cpp:2438-2442`. The preceding entry names the
correct template but omitted its numeric line span. No contract/state change.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0053 | CPU-03 | f6b5d3d1 | UNVALIDATED | SBYCR bit 5 reads zero while meaningful control bits and existing write routing remain unchanged |

### IMPL-0053 — CPU-03 — SBYCR reserved read bit

- branch/commit/base: `arena/01a0b897-mame`; implementation `f6b5d3d1`,
  base `d1149c2e`; committed and pushed.
- files: `src/devices/cpu/sh/sh7604.cpp:2078-2082`, `fmr_sbycr_r`;
  `saturn_pending/impl_checks/check_sh7604_sbycr_reserved.py` (new).
- contract: mask reserved bit 5 from SBYCR readback, preserving SBY, HIZ
  and MSTP4-0. The getter does not mutate raw storage or call peripheral
  helpers. Write handling, FMR compatibility routing and reset behavior
  are unchanged. No new state field or save-layout change.
- primary source: SH7604 ADE-602-085C Rev.4 section 14.2.1 p.387 states
  bit 5 always reads zero and should be written zero; bits 7,6,4-0 are
  controls. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
  Document caveat: Table 14.2 p.386 prints initial value 60, while the
  following section/bit diagram says reset value 00. This candidate follows
  the explicit reserved-bit read rule and does not change or qualify the
  reset image. Whole-chip standby and module-clock behavior are separate.
- pinned cross-checks: Saturn_MiSTer
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/MSBY.sv:65-67` masks reads with SBYCR_RMASK;
  `rtl/SH/SH7604/SH7604_pkg.sv:493-502` defines the fields and DF mask.
  Blobs `706ffd2c60b392c1b87df129cf6af09137e2e3e4` and
  `3c2220d46fb623925b15a5e23d96a73378de6042`.
  Ymir `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/sh2/sh2.cpp:1117,1451` reads its stored
  byte and masks writes with DF; blob
  `9746b438b8a71de63ff65cd2d4325bc582a5114b`. This change only masks
  readback, without importing either reference's broader power-down model.
- provenance: local getter and upstream MAME pinned
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1323-1326`, return the raw byte. Local
  history reviewed; no external source implementation imported.
- expected observable: bit 5 is zero on every SBYCR read; all seven
  meaningful stored bits are unchanged. Raw backing 20 returns 00 and FF
  returns DF in an instrumented method probe. Reserved-one injections are
  diagnostics, not supported software programming. Units: exact 8-bit
  register image, zero bit tolerance; no clock/pin timing result claimed.
- suggested measurement: native byte readback at FFFFFE91 after supported
  programming with WDT stopped and affected modules halted, without
  executing SLEEP. Check meaningful controls and reserved read bit; use
  instrumentation for nonzero reserved backing. Qualify pin/high-impedance,
  clock gating, whole-chip standby and native save/load independently.
- falsifier: masking loses a meaningful control bit, changes backing state
  or invokes peripheral side effects; or attributable hardware/erratum
  evidence establishes bit 5 as readable/meaningful under the applicable
  contract. Illegal-write diagnostics alone do not legalize reserved writes.
- self-check run (method-level, unvalidated): actual getter/writer with
  peripheral helpers mocked, fail-fast UBSan; 256 raw-storage masks,
  256 state-copy replays, 256 byte-write/read cases (128 reserved-zero
  controls, 128 reserved-one diagnostics) and 4,096 legacy FMR routing
  controls; exit 0. The latter preserve the existing high-byte/full-word
  branches, not native FMR timing or access-width qualification. Historical
  `d1149c2e` source fails the first reserved-bit observation (generated
  line 69).
  Prior selected 41-script series: 37 exit 0/four conflicts. Including
  this new probe: selected 42-script series, 38 exit 0/four unchanged
  semantic conflicts (frt_stop generated line 475, frt_phase 410,
  wdt_access 132, bsc_access 98). Expectations/validator assets untouched.
  Warning-enabled C++20 TU syntax-only and `git diff --check`: exit 0.
  No full build or native qualification.
- state: **UNVALIDATED** — validator owns qualification and milestone status.
- not covered/known doubts: reset-image discrepancy, native bus lanes,
  SBY/SLEEP entry and wake, HIZ drive states, MULT/DIVU/DMAC clock gating,
  active-module stop restrictions, watchdog interlocks and native save/load.
  No interfaces or configured peripherals added; the supported/not-supported
  inventory is unchanged. No frozen DMA/IRQ-delay-slot/sound/video edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0054 | CPU-03 | f0296ade | UNVALIDATED | Strict finite 64/32 overflow exposes the three-step intermediate remainder and, with OVFIE=1, intermediate quotient |

### IMPL-0054 — CPU-03 — strict-overflow DIVU intermediate register image

- branch/commit/base: `arena/01a0b897-mame` @ **f0296ade2e1956cf14c1c9a271ad5a3857c20584**;
  base **a1345bb9b0f54630564bcd90633fa89f82a494ef**. Production and probe
  committed/pushed separately from this append-only handoff.
- files: `src/devices/cpu/sh/sh7604.cpp:1894-1955`, specifically the new
  arithmetic/result block at 1913-1936;
  `saturn_pending/impl_checks/check_sh7604_divu_partial.py:1-105`.
- contract: for a nonzero divisor and a host-representable mathematical
  signed-64 quotient strictly below -2^31 or strictly above +2^31, retain
  the existing overflow classification and sticky OVF handling, but replace
  the constant DVDNTH placeholder with the intermediate divide image after
  three arithmetic steps. OVFIE=1 exposes that image's low word in DVDNTL;
  OVFIE=0 retains the signed saturation quotient from IMPL-0044. The
  pre-shift sum sign, not the shifted register sign, controls the next
  add/subtract step. All intermediate add/subtract/shift operations use
  unsigned modulo-2^64 arithmetic. The exact +2^31 quotient explicitly
  retains its legacy output/classification; this is a scope guard, NOT a
  proposed hardware exception. In-range arithmetic, divisor-zero and
  INT64_MIN/-1 branches are untouched, as are all IRQ-recalculation calls.
- primary source: SH7604 ADE-602-085C Rev.4, section 10.3.3 p.293 specifies
  the six-cycle overflow result point (three flag-setting cycles then three
  division cycles), intermediate DVDNTH for either OVFIE setting, and
  intermediate versus saturated DVDNTL according to OVFIE. Section 10.4.2
  p.294/Table 10.2 specifies sticky OVF and retained DVSR/VCRDIV. Sections
  10.3.1 p.292 and 10.4.1 p.293 specify the signed 64/32 start sequence and
  longword accesses. SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
  The manual defines the result point, but does not spell out the internal
  bit recurrence: the candidate's precise recurrence is reference-derived
  and still requires a hardware comparison, not represented as a captured
  silicon result.
- cross-checks/provenance:
  - Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
    `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:208-237` (blob
    `6b31b7d029449d63f68ef281dc04958d17d74339`) performs three partial
    steps with the pre-shift sign, then selects intermediate low word or
    signed saturation and always returns the intermediate high word.
    Its broader overflow detection/exact-boundary exceptions are not
    imported. This implementation uses unsigned shifts/arithmetic rather
    than relying on the reference's signed-shift expressions.
  - Saturn_MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
    `rtl/SH/SH7604/DIVU.sv:49-50,97-107,115-117,196-205` (blob
    `09b259b5f91888dc0363884fd3b2c5d81644c118`): SUM64/T64 recurrence,
    steps 3 through 5, and R64 high/low overflow output selection agree.
    Its detection, scheduler and register-alias logic are not imported.
  - Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
    `src/devices/cpu/sh/sh7604.cpp:1178-1209`, still uses constant
    7FFFFFFF overflow placeholders. Fork history inspected with
    `git log --all -S 'OVFIE=1 intermediate results'`: published 760ef54e
    supplied disabled-interrupt signed saturation only. Base a1345bb9
    retains that result and the signed-64 safety guard. No reference file
    copied into the tree; the new local arithmetic block implements the
    cross-checked recurrence without importing reference schedulers/state.
- expected observable: exact 32-bit register words, zero bit tolerance.
  Reference-derived examples (NOT hardware captures), shown as
  dividend / divisor -> DVDNTH, DVDNTL with OVFIE=1:
  - 0000000100000000 / 00000001 -> FFFFFFFE, 00000004;
  - FFFFFFFF00000000 / 00000001 -> FFFFFFFE, 00000004;
  - 0000000080000001 / FFFFFFFF -> FFFFFFFE, 0000000D;
  - 8000000000000000 / 00000001 -> 0000000A, 00000003.
  With OVFIE=0 the same high words remain, while the low words are
  respectively 7FFFFFFF, 80000000, 80000000, 80000000. OVF becomes 1;
  DVSR/OVFIE remain unchanged. Ordinary in-range division preserves
  quotient/remainder and old OVF. This candidate changes the register
  image only: execution is still immediate, NOT six-cycle timed.
- suggested method: on SH7604 hardware and the native device, use legal
  longword DVSR/DVDNTH/DVDNTL writes, both OVFIE values and both initial OVF
  states. Mask CPU interrupt acceptance while comparing enabled-overflow
  data; qualify interrupt delivery separately. Place non-DIVU instructions
  after the start write and wait at least the documented 39 cycles before
  sampling DVCR/DVDNTH/DVDNTL (and aliases separately). Capture all four
  operand-sign combinations and low-word carry/sign-transition examples,
  including the listed words. Compare disabled-overflow saturation and
  intermediate remainder independently. Use separate measurements for
  actual six-cycle availability/busy extension, then native save/load.
- falsifier: a captured strict finite overflow produces different high
  words or enabled low words from this recurrence; a disabled quotient
  loses signed saturation; in-range results, sticky OVF, operands or
  existing IRQ-refresh count change; or host arithmetic UB occurs. A
  trace showing a different partial-step/sign convention rejects the
  candidate despite agreement between software/FPGA references.
- self-check run (method-level, unvalidated): fail-fast UBSan exit 0;
  7 reference-pattern examples, **98,524 enabled-overflow partial images,
  98,524 disabled-overflow remainder/saturation images, 65,628 in-range
  results, 262,676 operand-state-copy replays** (98,720 positive and
  98,328 negative overflow observations). The partial oracle is an
  independently expressed paired-32-bit high/low/carry recurrence;
  signed-128 arithmetic supplies ordinary division/range controls. It is
  not an independent hardware oracle. Historical a1345bb9 exits 1 at
  generated line 85 on the first intermediate-result example. Two-step
  and post-shift-sign mutants exit 1 at generated lines 110 and 111.
  Selected **43-script** series: **39 exit 0 / four unchanged conflicts**
  (frt_stop generated line 475, frt_phase 410, wdt_access 132,
  bsc_access 98); `check_sh7604_sci.py` is not in that selected series.
  Warning-enabled C++20 TU syntax-only (`-Wall -Werror
  -Wno-sign-compare`, session include paths) and `git diff --check` exit 0.
  No full build. No validator assets or fixture expectations changed.
- state: **UNVALIDATED** — qualification and milestone status remain with
  the validation agent.
- not covered/known doubts: exact-limit overflow classification (including
  the explicit +2^31 exclusion and maximum-quotient/nonzero-remainder
  cases), divisor zero, INT64_MIN/-1 partial image, signed-32 minimum/-1,
  32-bit-start overflow images, 39/6-cycle timing, bus stalls, native IRQ
  delivery/acknowledgement, aliases and native save-manager/DRC/MinGW
  behavior. No new fields or save-layout change; mock copies are not
  native save/load. The four old fixture conflicts remain unresolved.
  No frozen DMA/IRQ-delay-slot/sound/video path edits, peripheral additions
  or inventory/status changes. The ongoing peripheral audit has not yet
  established a separate defensible behavioral change.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0055 | CPU-03 | 2ddf2ba6 | UNVALIDATED | A 32-bit zero-divisor start exposes the three-step intermediate image, saturating only the quotient when OVFIE=0 |

### IMPL-0055 — CPU-03 — 32-bit divide-by-zero register image

- branch/commit/base: `arena/01a0b897-mame` @ **2ddf2ba61865b402256f8d5efd59c60ea9ad05da**;
  base **944d3322a7b0b3ed3e76b893850f063f4dc62ee6**. Production/probe
  committed and pushed before this separate append-only handoff.
- files: `src/devices/cpu/sh/sh7604.cpp:1856-1881`, zero-divisor block
  at 1869-1880; `saturn_pending/impl_checks/check_sh7604_divu_zero32.py:1-79`.
- contract: DVDNT starts signed 32/32 division. When DVSR=0, set OVF and
  return the intermediate dividend image after three arithmetic steps.
  Sign-extend the 32-bit operand, shift left three positions, and insert
  111 for a nonnegative operand or 000 for a negative operand. DVDNTH
  receives the image's upper word. With OVFIE=1, DVDNTL receives the lower
  word; with OVFIE=0, it receives 7FFFFFFF for a nonnegative operand or
  80000000 for a negative operand. Old DVDNTH does not affect a 32-bit
  start. Use unsigned shifting after signed extension to avoid host
  negative-shift/overflow dependence. Ordinary nonzero-divisor arithmetic,
  IRQ-refresh calls and the complete 64-bit start handler are unchanged.
- primary source: SH7604 ADE-602-085C Rev.4, section 10.3.2 p.292 specifies
  signed 32/32 division initiated by DVDNT; section 10.3.3 p.293 explicitly
  includes zero divisors in overflow and specifies three flag-setup plus
  three division cycles, intermediate DVDNTH for either OVFIE setting,
  and intermediate versus saturated quotient. Section 10.4.2 p.294/Table
  10.2 specifies sticky OVF, retained DVSR/VCRDIV and overflow register
  selection. Section 10.4.1 p.293 requires longword operand accesses and
  describes busy access restrictions. SDK blob
  `4c1697421398cef77c7b52defda94ef5fead7372`. As in IMPL-0054, the exact
  bit recurrence/result patterns are reference-derived, not specified as
  bit equations by the manual or represented here as hardware captures.
- cross-checks/provenance:
  - Ymir pinned `6d779960127ced72087a418c1daefc637d0aaa80`,
    `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:147-166` (blob
    `6b31b7d029449d63f68ef281dc04958d17d74339`): zero-divisor DVDNTH is
    dividend arithmetic-right-shifted by 29; enabled quotient is dividend
    shifted by three with low bits determined by its sign; disabled
    quotient saturates by dividend sign. This candidate uses unsigned
    sign-extended arithmetic rather than the reference's signed shifts.
  - Saturn_MiSTer pinned `a95b085038ace57fa621558d60a7adc7a3c53f78`,
    `rtl/SH/SH7604/DIVU.sv:97-108,110-127,173,190-205` (blob
    `09b259b5f91888dc0363884fd3b2c5d81644c118`): a 32-bit start sign-
    extends into DVDNTH/DVDNTL; zero divisor triggers overflow after
    steps 3-5. With D=0 the ordinary shift register inserts !R_SIGN
    each step. At overflow only disabled-interrupt DVDNTL is replaced by
    saturation; DIV64-only R64 output selection does not apply here.
  - Upstream MAME pinned `398bba74ed7997d29c2316316da230f6d85fda0d`,
    `src/devices/cpu/sh/sh7604.cpp:1140-1161`, and fork base 944d3322
    return constant 7FFFFFFF in both words. Local history inspection
    (`git log --all -S 'TODO: 8 cycles'`) traces that placeholder to
    baseline 60ad2f1a; no prior implementation imported. The stale
    eight-cycle TODO is corrected to six as documentation only, not a
    newly implemented delay. No reference file/code block imported.
- expected observable: exact 32-bit words, zero bit tolerance. With
  DVSR=0 and OVFIE=1, reference-derived dividend -> DVDNTH, DVDNTL examples:
  - 00000000 -> 00000000, 00000007;
  - 00000001 -> 00000000, 0000000F;
  - 7FFFFFFF -> 00000003, FFFFFFFF;
  - 80000000 -> FFFFFFFC, 00000000;
  - FFFFFFFF -> FFFFFFFF, FFFFFFF8.
  With OVFIE=0 the high words remain identical and the low words become
  7FFFFFFF for the first three inputs, 80000000 for the last two. OVF=1,
  DVSR remains zero, OVFIE unchanged. Existing getter backing reads
  DVDNT/DVDNTL identically and without side effects; separate physical
  alias/storage behavior is not newly implemented or qualified.
- suggested method: native longword DVSR=0 followed by a DVDNT operand
  write, with both OVFIE settings and old OVF clear/set. Seed DVDNTH with
  different prior values to distinguish 32-bit sign extension from a
  64-bit start. Mask CPU interrupt acceptance while observing OVFIE=1
  data; native delivery is a separate target. Place non-DIVU instructions
  after the start and wait at least 39 cycles before sampling all result
  registers/DVCR; compare nearby multiples of 2^29 and both sign limits.
  Separately measure six-cycle readiness/busy extensions and native
  save/load rather than treating this synchronous method as a scheduler.
- falsifier: an attributable zero-divisor hardware capture differs from
  the listed high/low words or sign-dependent saturation; old DVDNTH
  influences a 32-bit result; DVSR/OVFIE or getter-read state changes;
  OVF/IRQ-refresh behavior changes; ordinary nonzero division regresses;
  or host arithmetic UB occurs in this branch. Agreement with the two
  references alone is not native qualification.
- self-check run (method-level, unvalidated): fail-fast UBSan exit 0:
  **4,194,304 zero-divisor register/status/readback images**, all low16
  values at 16 selected high16 prefixes across sign/high-word transitions,
  OVFIE and old OVF each clear/set; **65,676 ordinary signed-32 controls**;
  **4,259,980 operand-state-copy replays**. The independent formula oracle
  uses mathematical floor division for the high word and multiplication/
  modulo conversion for the low word, not the production unsigned shift.
  Historical 944d3322 exits 1 at generated line 69 on the first zero
  dividend observation. Zero-extension and missing-positive-quotient-bit
  mutants each exit 1 at generated line 73. Prior selected 43 scripts:
  39 exit 0/four unchanged conflicts; with this probe the selected series
  is **44 scripts, 40 exit 0/four conflicts** (frt_stop 475, frt_phase 410,
  wdt_access 132, bsc_access 98). `check_sh7604_sci.py` remains outside that
  selected series. Warning-enabled C++20 TU syntax-only and
  `git diff --check` exit 0. No full build or native qualification;
  validator assets and existing fixture expectations untouched.
- state: **UNVALIDATED** — validation agent owns qualification/status.
- not covered/known doubts: the nonzero signed-32 INT32_MIN/-1 expression
  remains unsafe and blocked by IMPL-0036; the new probe deliberately never
  executes it. No 64-bit zero-divisor or INT64_MIN/-1 partial correction,
  new boundary classification, DIVU interrupt-source integration, busy
  state, six/39-cycle delay, native lanes/aliases/save-manager/DRC/MinGW
  qualification. No new fields/save-layout change. Frozen DMA
  acknowledgement, delay-slot IRQ and sound/video/game paths unchanged;
  no peripheral additions or inventory/milestone-status changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0056 | CPU-03 | afc75c2e | UNVALIDATED | The 64/32 zero-divisor and INT64_MIN/-1 overflow branches return the three-step intermediate image instead of constants |

### IMPL-0056 — CPU-03 — exceptional 64-bit DIVU result paths

- branch/commit/base: `arena/01a0b897-mame` @ **afc75c2e**;
  base **7e474f77137384ec682292be3d3dac2360cd64b0**.
- files: `src/devices/cpu/sh/sh7604.cpp:1898-1958` (`dvdntl_w`);
  `saturn_pending/impl_checks/check_sh7604_divu_zero64.py`.
- contract: reuse IMPL-0054's unsigned three-step overflow recurrence for
  DVSR=0 and the guarded INT64_MIN/-1 pair. DVDNTH always receives the
  intermediate high word; OVFIE=1 selects the intermediate low word while
  OVFIE=0 selects signed saturation from operand signs. Set sticky OVF
  and retain DVSR/OVFIE. Never evaluate host INT64_MIN/-1 division or
  remainder. A local lambda shares the result path without new persistent
  state. In-range arithmetic, the disputed +2^31 exclusion and existing
  IRQ-recalculation call counts remain unchanged.
- primary source: SH7604 ADE-602-085C Rev.4, section 10.3.1 p.292,
  section 10.3.3 p.293 (zero divisor and quotient overflow; three setup
  plus three division cycles; enabled intermediate versus disabled
  saturation), section 10.4.2 p.294/Table 10.2 (sticky OVF, register
  selection/retention). SDK blob `4c1697421398cef77c7b52defda94ef5fead7372`.
  Exact internal bit recurrence remains reference-derived, not spelled out
  in that manual or asserted here to be captured from silicon.
- cross-checks/provenance: Ymir pin
  `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/sh2/sh2_divu.hpp:179-188,208-237`,
  blob `6b31b7d029449d63f68ef281dc04958d17d74339`, routes both exceptional
  cases into the same partial calculation. Saturn_MiSTer pin
  `a95b085038ace57fa621558d60a7adc7a3c53f78`,
  `rtl/SH/SH7604/DIVU.sv:49-50,97-127,196-205`, blob
  `09b259b5f91888dc0363884fd3b2c5d81644c118`, supplies the matching
  SUM64/R64 recurrence and output selection. Upstream MAME pin
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/devices/cpu/sh/sh7604.cpp:1178-1209`, has constant placeholders.
  Local base 7e474f77 retains them only on the paths extended here;
  prior local recurrence is reused, not an imported reference code block.
- expected observable: exact 32-bit words, zero bit tolerance. For a
  zero divisor and dividend bit pattern A, the image is
  `((A * 8) + ((~A >> 61) & 7)) modulo 2^64`; use its upper word for
  DVDNTH and, when OVFIE=1, its lower word for DVDNTL. For A=0: high=0,
  low=7. For A=8000000000000000: high=0, low=3; disabled quotient is
  80000000. For INT64_MIN/-1: high=0000000A, enabled low=00000004,
  disabled low=7FFFFFFF. These are reference-derived examples, not
  hardware captures. OVF=1, unchanged operands/control; no host exception.
- suggested method: legal longword DVSR/DVDNTH/DVDNTL writes; both OVFIE
  and initial OVF settings, with CPU interrupt acceptance masked when
  observing enabled results. Wait at least 39 cycles using non-DIVU
  instructions after the start, then capture DVCR and all result words.
  Cover all eight original top-three-bit combinations for a zero divisor,
  both operand signs, and the signed-64 guard. Compare after native
  save/load separately; measure busy/completion timing independently.
- falsifier: attributable hardware result mismatch; wrong disabled sign,
  lost sticky OVF, changed in-range or existing strict-overflow images,
  extra IRQ-refresh invocation, or host arithmetic UB rejects this
  candidate. Two agreeing references do not qualify the native device.
- self-check run (method-level, unvalidated): fail-fast UBSan exit 0:
  **262,912 zero-divisor images, four INT64_MIN/-1 images, 262,916
  operand-state-copy replays**. The zero-divisor oracle uses a widened
  multiply/add closed form rather than the production iterative recurrence.
  Historical 7e474f77 exits 1 at generated line 90 on the first remainder
  check. Prior selected 44 scripts: 40 exit 0/four unchanged conflicts;
  including this script: **45 selected, 41 exit 0/four conflicts**
  (frt_stop 475, frt_phase 410, wdt_access 132, bsc_access 98).
  `check_sh7604_sci.py` remains excluded from the selected series.
  Warning-enabled C++20 TU syntax-only and `git diff --check` exit 0.
  No full build, native qualification or fixture expectation edits.
- state: **UNVALIDATED**.
- not covered/known doubts: disputed exact-limit classification, unsafe
  signed-32 minimum/-1 (IMPL-0036), actual six/39-cycle availability,
  restartable busy accesses, native DIVU IRQ delivery, aliases and native
  save-manager/DRC/MinGW acceptance. No new fields/save-layout change,
  frozen handler changes, peripheral additions or milestone-status claims.
  This is an implementation checkpoint, not completion of CPU-03 or a
  stopping point for the ongoing missing-emulation work.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0057 | CD-01 | 7027e048 | UNVALIDATED | CD selector chains follow false-filter and true-partition connectors using normalized sector metadata |

### IMPL-0057 — CD-01 — selector-chain routing and non-Mode-2 metadata

- branch/commit/base: `arena/01a0b897-mame` @ **7027e048**; base **4f655b1c**.
- files: `src/mame/sega/saturn_cd_hle.cpp:3845-3876,3944-3948,3990-3994`,
  `src/mame/sega/saturn_cd_hle.h:218`, and
  `saturn_pending/impl_checks/check_cd_filter_routing.py`.
- contract: evaluate the sector's saved FAD/subheader conditions, follow
  false outputs to other filters, and store through the accepting filter's
  true partition connector. Support every acyclic chain through the 24
  selectors rather than the previous two-link limit. Non-Mode-2 sectors
  carry zero subheader fields, not the preceding Mode 2 sector's metadata;
  their zero fields participate in selection. Subheader inversion remains
  outside the FAD predicate. Retain the last successfully stored CD target
  on discard/allocation failure. Normalization plus a pure routing helper
  supplies the existing disc-read consumer and the forthcoming copy/move
  consumer without reinterpreting trimmed payload bytes as headers.
- primary source: ST-162-062094, CD Communication Interface/System Library
  User's Guide, printed pp.43-47, sections 5.3.1-5.3.4/Figures 5.3-5.7 and
  Table 5.1 (connector types, partition append, last stored CD target);
  printed p.48 section 5.4 (non-Mode-2 subheaders are zero), p.88 function
  5.5 (subheader inversion excludes FAD), p.93 function 6.5 (reported
  sector metadata). SDK blob `37cf17209eb176d6580bd55bf11af1694ae1f328`.
  Extracted all 91 PDF pages by ignoring only the malformed null /Encrypt
  entry; no encryption removed or document committed.
- cross-checks/provenance: Mednafen pin
  `f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc`, `src/ss/cdb.cpp:1697-1781`,
  blob `d367dd0c0500ff7b1e2637e748015543b0a3078e`: TestFilterCond normalizes
  non-Mode-2 fields and FilterBuf walks false connectors, using TrueConn
  for storage. Ymir pin `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/include/ymir/hw/cdblock/cdblock_filter.hpp:41-74`, blob
  `d1c51615ebf26ecb20c0b32c6d3b4f628fcf19e5`, corroborates condition
  composition/inversion. For inversion with no enabled subheader tests,
  Ymir/current MAME invert the empty conjunction, whereas Mednafen gates
  inversion with mode&0F; existing MAME/Ymir behavior is retained and that
  special configuration is NOT hardware-qualified. Upstream MAME pin
  `398bba74ed7997d29c2316316da230f6d85fda0d`,
  `src/mame/sega/saturn_cd_hle.cpp:2597-2799`, and local base retain the
  old two-link/index routing and stale non-Mode-2 fields. Local history
  through 0e297cac/4101ca4f reviewed; no reference code block imported.
- expected observable: exact destination IDs, block counts/metadata and
  payload bytes, zero tolerance. For filter 0 false->1 and filter 1
  true->7, a rejecting-first/accepting-second sector lands in partition 7,
  not 1. An acyclic 24-filter chain can reach its last true connector.
  After Mode 2 then Mode 1/audio, FN/CN/SM/CI are all zero in the stored
  second sector. A required nonzero FN rejects that sector. Discard/full
  buffer leaves the previous successful last-target ID unchanged.
- suggested method: configure real filter connections/conditions through
  mapped CD commands, then read controlled Mode 1/Mode 2 sectors and query
  destination counts, Get Sector Information and Get Last Buffer
  Destination. Use nonidentity true connectors, 1-24-link chains, FAD
  boundary/inversion controls, disconnected outputs and full-buffer
  conditions. Re-run frozen CD boot/gameplay acceptance before integration;
  method-level success does not establish absence of game regressions.
- falsifier: wrong connector target, inaccessible legal chain, stale
  non-Mode-2 metadata, FAD inversion, lost payload, last-target change on
  discarded/unstored data, or a regression in those native acceptance cases.
- self-check run (method-level, unvalidated): 4,096 condition cases,
  24 acyclic chain lengths, 765 Mode 2->Mode 1/audio transitions, redirected
  connector and discard/full-buffer controls; fail-fast UBSan exit 0.
  Historical 4f655b1c fails the first actual routed allocation at generated
  line 315. Existing `regtests/saturn/test_cd_transfer.py` exits 0 with its
  262,144 HIRQ overlay cases, 336 transfer cases and observational trace
  checks; expectations unchanged. `test_cd_hirq.py` reported SKIP because
  no native binary exists; that is NOT a native result. CD HLE TU
  warning-enabled C++20 syntax-only and diff checks exit 0; no full build.
- state: **UNVALIDATED**.
- not covered/known doubts: selector timing, mid-sector reconfiguration,
  input-connector ownership, copy/move/PUT command integration, malformed
  cycles and native save state/firmware/gameplay. A bounded cyclic walk
  discards defensively; it is not a claimed hardware cycle/deadlock model.
  Stored metadata for raw host PUT remains an independent ingestion gap.
  No new fields/save-layout change or edits to HIRQ, host-transfer methods,
  validator assets, existing expectations, SH/DMA/IRQ or sound/video paths.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0058 | CD-01 | 60332b84 | UNVALIDATED | COPY/MOVE honor source ranges, selector routing and append order; MOVE transfers ownership without allocating another block |

### IMPL-0058 — CD-01 — routed sector COPY/MOVE

- branch/commit/base: `arena/01a0b897-mame` @ **60332b84**; base **b0c8f399**.
- files: `src/mame/sega/saturn_cd_hle.cpp:1969-2074`,
  `src/mame/sega/saturn_cd_hle.h:199`,
  `saturn_pending/impl_checks/check_cd_copy_move.py`.
- contract: commands 65/66 use all 16 bits of CR2/CR4 as source offset/
  count, resolving FFFF last-sector/to-end sentinels against the original
  source partition. An unavailable range or active host transfer returns
  WAIT without changing buffers/connections or newly asserting ECPY;
  invalid selectors return REJECT. Accepted operations attach the source
  stream to the destination FILTER, not a same-numbered buffer; its true/
  false chain selects append targets or discards sectors. COPY preserves
  the original and copies the entire stored sector record, including its
  size/FAD/subheader, independent of current sectlenin. MOVE detaches the
  selected identities, then routes those same blocks without allocation;
  it works with zero free blocks. A self-move places its original selected
  range after surviving sectors, once only. The input connection replaces
  prior CD/false-output producers. ECPY is newly asserted on completion,
  not a WAIT/REJECT. Last successful CD-read target is unaffected.
- primary source: ST-162-062094, printed p.97 functions 7.6/7.7 (range,
  sentinels, destination filter); pp.43-46 sections 5.3.1-5.3.3/Figures
  5.3-5.7/Table 5.1 (false-filter/true-partition routing, append storage,
  self-copy/move, one producer per filter input); p.47 section 5.3.4
  (unavailable-range WAIT and full selected-range deletion on MOVE);
  p.98 function 7.8 (async error/busy reporting remains separate).
  SDK blob `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen pin
  `f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc`, `src/ss/cdb.cpp:3610-3680`,
  blob `d367dd0c0500ff7b1e2637e748015543b0a3078e`, corroborates 16-bit
  ranges, both sentinels, WAIT before mutation, copy-space preflight,
  input disconnection, MOVE unlink/relink and shared FilterBuf routing;
  `:863-883,1750-1781` gives input ownership and discard routing. The
  preflight reservation for all requested COPY sectors follows that
  reference; the manual does not specify its internal reservation scheme.
  Yabause pin `82cb29171ebe61cf0129682794af5ceb5acaa0f2`,
  `yabause/src/cs2.c:2735-2810`, blob
  `ab2e76aa8179e99f1296efd4a51e91b8c8235159`, corroborates tail append and
  MOVE pointer transfer but has a truncated count and bypasses filtering;
  those defects are not imported. Ymir pin 6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:3023-3086`, has stubs,
  not an implementation oracle. Upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d
  CD source and local b0c8f399's two command bodies were inspected before
  replacement; old code ignores offset, overwrites slot zero onward and
  allocates a second block even for MOVE. New code uses the existing local
  allocator/compactor and IMPL-0057's router; no reference block imported.
- expected observable: exact sector order, metadata, bytes, sizes, pool
  ownership and command bits; zero tolerance. With source [A,B,C,D,E],
  offset=1/count=2 and destination [X,Y], COPY gives source unchanged and
  destination [X,Y,B,C], consuming two blocks. MOVE gives [A,D,E] and
  [X,Y,B,C] with unchanged free count. Self-MOVE gives [A,D,E,B,C]. With
  all 200 blocks occupied, full-range MOVE succeeds without allocation
  while COPY returns WAIT without mutation. Filter-selected discards free
  only the moved/copied output; a COPY never deletes its original.
- suggested method: drive mapped 65/66 commands after legal sector ingest
  and selector programming, including offset/count sentinels, nonidentity
  true targets, self routing, split targets, discard and full pool. Query
  partition counts/free space/sector metadata, then GET byte payloads and
  examine CMOK/ECPY/BFUL and WAIT/REJECT responses. Repeat after native
  save/load and with frozen CD game/boot acceptance. Qualify command
  overlap and asynchronous completion/error timing separately.
- falsifier: lost/duplicated ownership, overwritten destination prefix,
  wrong source slice, changed COPY source, MOVE requiring free storage,
  metadata loss, repeated self-appending, or mutation/ECPY on an unaccepted
  request; native command/boot regression also rejects integration.
- self-check run (method-level, unvalidated): ASan plus fail-fast UBSan:
  **120 range/self/append cases, 120 pointer-rebound state-copy replays,
  four split/discard routes, four full-buffer controls, 16 range/overlap
  WAIT cases**, plus invalid-selector REJECT controls; exit 0. Tests use
  real allocation/free/compaction/router/command bodies, recording IRQ/
  response helpers, and pool-wide unique ownership/byte-accounting checks.
  Legal CD-only/false-output producers are covered separately; a dual-
  producer injected legacy state is a diagnostic, not a legal wiring claim.
  Historical b0c8f399 fails first destination-count comparison (generated
  line 340 in the initial harness). Byte-count truncation, payload-only
  copying and MOVE-allocation mutants fail at lines 300/300/340 in the
  final harness. IMPL-0057's probe and existing CD transfer/HIRQ/trace
  method checks exit 0; expectations untouched. CD HLE warning-enabled
  C++20 syntax-only/diff checks exit 0. No full build/native qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: still an atomic synchronous HLE operation,
  not timed/asynchronous COPY/MOVE or a running SH-1. Get Copy Error's
  busy/error states and mid-command disconnect/buffer-fill events remain
  absent. Defensive malformed-pointer/pool guards have no claimed hardware
  meaning. Raw host PUT metadata ingestion, selector reset/ownership in
  other commands and native buffer save state need further work. No new
  persistent fields/save-layout change; no host-transfer/HIRQ handler,
  validator asset, existing fixture expectation, frozen SH/DMA/sound/video
  edits. These candidates require native game regression before integration.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0059 | CD-01 | dbca3640 | UNVALIDATED | Device reset restores default selector conditions/topology and disconnects stale CD/host consumers |

### IMPL-0059 — CD-01 — reset selector topology

- branch/commit/base: `arena/01a0b897-mame` @ **dbca3640**; base **2188263f**.
- files: `src/mame/sega/saturn_cd_hle.cpp:220-239` in `device_reset`;
  `saturn_pending/impl_checks/check_cd_selector_reset.py`.
- contract: device reset clears all 24 filter condition records, connects
  true output i to partition i, disconnects false outputs, disconnects the
  CD producer (pointer null/ID FF), and clears the stale host-transfer
  partition pointer. Existing buffer emptying and transfer-type cancellation
  remain unchanged. This does not reinterpret the separate Init-CD command.
- primary source: ST-162-062094 printed p.43 section 5.3/Figure 5.3
  (initial topology), p.49 section 5.5 (host information/selector/buffer
  initialization), p.88 function 5.5 (zero initial filter conditions),
  p.91 function 5.9 (selector initialization). SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Ymir pin
  `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:147-157`, blob
  `e8fedadb2d7374db35667bd064bb47fdc14b41a8`, resets filters/connections;
  `cdblock_filter.hpp:21-39`, blob d1c51615ebf26ecb20c0b32c6d3b4f628fcf19e5,
  supplies own true output, disconnected false and zero conditions.
  Mednafen pin `f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc`,
  `src/ss/cdb.cpp:1441-1458`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  agrees. Upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d and local
  2188263f reset were inspected: partition storage resets, filter topology
  and the CD/host pointers do not. No reference code block imported.
- expected observable: all filter condition values zero; true i/false FF
  for each selector; CD connection FF; no old active host partition pointer.
  Query commands and subsequent routing see defaults, not pre-reset chains.
  Exact register/connection bits, zero tolerance; reset-edge latency excluded.
- suggested method: program nondefault FAD/subheader conditions/connections,
  populate buffers and start a host transfer; machine-reset and query all
  selectors/connections, then reconnect and read a new sector. Repeat
  cold/warm, with/without media, and native save/load after reset.
- falsifier: retained pre-reset predicate/connection, routing to an old
  target, stale host consumer, or changed documented default image rejects
  the candidate. Native frozen boot/gameplay regression rejects integration.
- self-check run (method-level, unvalidated): 512 poisoned reset images,
  12,288 selector-default/routing observations, empty ownership/cancel
  controls; fail-fast UBSan exit 0. Actual reset body, mocked media/timers/
  MPEG/IRQ. First harness compile lacked a mock `playtype` declaration;
  adding it fixed the harness, with no production/expectation change.
  Historical 2188263f then fails at generated line 211 on stale consumers.
  IMPL-0057/0058 probes and existing CD transfer/HIRQ/trace checks exit 0;
  warning-enabled CD TU syntax/diff checks exit 0. No full build/native run.
- state: **UNVALIDATED**.
- not covered/known doubts: software Init-CD flag semantics/timing, selector
  reset command details, active transfer interruption timing, actual media
  mechanics, native save-manager and game/boot acceptance. No new fields or
  save-layout change; no validator/expected-value/frozen CPU/sound/video edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0060 | CD-05 | 30da470f | UNVALIDATED | Save the CD sector/selector backing state with transfer positions and reconstruct process-local ownership pointers on load |

### IMPL-0060 — CD-05 — sector-buffer save-state coherence

- branch/commit/base: `arena/01a0b897-mame` @ **30da470f**; base **a4fd43bc**.
- files: `src/mame/sega/saturn_cd_hle.cpp:179-231,277-301`,
  `src/mame/sega/saturn_cd_hle.h:36-37,230-231`;
  `saturn_pending/impl_checks/check_cd_buffer_save.py`;
  reset probe mock declaration adapter only (expectations unchanged).
- contract: save every filter predicate/connector; every partition's size,
  count and block-ID array; all 200 sector records, metadata and payload;
  and the current scratch record. Presave encodes active host-partition
  and CD-filter pointers as two saved indices. Postload rebuilds each
  partition pointer from its saved block ID and restores active consumers,
  including null consumers. No raw pointers are serialized and pointer
  repair performs no transfers or IRQ callbacks. Empty record storage is
  zero-initialized on reset for deterministic serialization; this is not
  a newly asserted hardware value for inaccessible free-sector metadata.
- primary source: ST-162-062094 printed pp.43-49 (selector, partition,
  sector format/state), pp.94-97 functions 7.1-7.7 (data retained/removed
  and transferred through host/selector operations), SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`. Saving/restoring that state
  coherently is an emulator lifecycle obligation, not a claimed hardware
  save instruction or new chip timing behavior.
- cross-checks/provenance: Ymir pin
  `6d779960127ced72087a418c1daefc637d0aaa80`,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:331-400,475-527`, blob
  `e8fedadb2d7374db35667bd064bb47fdc14b41a8`, saves/restores transfer,
  sector, metadata, scratch and filter state; partition manager
  `cdblock_partition_manager.cpp:170-218`, blob
  `17fcd0f0d6f1aacf87463ca215f9f89d3eb88bc2`, restores ownership.
  Mednafen pin f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:4228-4270` registers its buffer/link/partition state.
  Local MAME `src/emu/save.h:185-197` defines strided STRUCT_MEMBER
  registration; native syntax instantiates those actual templates.
  Upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d and local a4fd43bc
  device_start were inspected: these backing arrays/pointer hooks were
  absent while transfer positions/free counts were already saved.
- expected observable: saving during GET/GETDELETE/PUT, changing buffers
  and selectors, then loading reproduces the original remaining words,
  modified-sector image, completion count and ownership/deletion exactly.
  Zero byte/metadata/count tolerance, no extra HIRQ edge solely from load.
  Restored pointer identities refer to this device's pool, not old process
  addresses; null CD/host consumers remain null.
- suggested method: native file save/mutate/load during host transfers at
  byte-zero, last-word-before-boundary, sector boundary and end cuts; use
  noncontiguous pool IDs and each partition. Read remaining data or finish
  writing, compare all bytes/metadata/counts and final GETDELETE freeing,
  then perform a routed copy/move. Also restore disconnected consumers and
  nondefault selectors. Run across interpreter/DRC, NTSC/PAL and relevant
  native game configurations. The mock serializer below is not that test.
- falsifier: changed remaining words, stale data from the post-save mutation,
  lost metadata/ownership, duplicate deletion, process-local pointer
  restoration, reconnection of a disconnected consumer, load-only IRQ
  callback, or native save-manager rejection of the current layout.
- self-check run (method-level, unvalidated): actual registration statements,
  actual pre/post hooks and host transfer/EndTransfer/cleanup methods through
  a byte-copy serializer: **504 GET/GETDELETE/PUT replays**, 24 partitions,
  seven cuts, noncontiguous IDs 0/67/199, payload/metadata/ownership mutation,
  null-consumer and no-IRQ-edge controls; ASan/fail-fast UBSan exit 0.
  Historical a4fd43bc fails restored active pointers (generated line 387).
  Missing payload, missing ownership and reconnect-from-visible-ID mutants
  fail at lines 435/434/439. All three preceding CD probes and existing
  CD transfer/HIRQ/trace method checks exit 0. CD TU warning-enabled C++20
  syntax and diff checks exit 0. No full build/native file qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: **save-state layout break**: new registrations
  and two saved index fields mean older files are not claimed compatible.
  Both new fields are registered in this same commit and initialized/reset.
  This is NOT complete CD-05: TOC/subcode/file-info staging buffers,
  directory state, MPEG model, some drive-phase flags and whole-system
  event/IRQ reconstruction still need separate work. No native binary was
  available or built. No host-transfer algorithm/HIRQ handler, validator
  asset, existing expectation or frozen SH/sound/video edits. A transient
  write-tool timeout created no file; the probe was subsequently written
  and run. An ignored-path staging warning was resolved with deliberate
  `git add -f`; implementation and adapter are committed/pushed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0061 | CD-01 | 7bbe639c | UNVALIDATED | Filter-condition initialization clears predicates/range but preserves connectors unless separately selected for reset |

### IMPL-0061 — CD-01 — condition initialization versus connector reset

- branch/commit/base: `arena/01a0b897-mame` @ **7bbe639c**; base **fb9c337a**.
- files: `src/mame/sega/saturn_cd_hle.cpp:1481-1509,1622-1625`,
  `src/mame/sega/saturn_cd_hle.h` private helper declaration;
  `saturn_pending/impl_checks/check_cd_filter_condition_reset.py`.
- contract: Set Filter Mode's initialization strobe and Reset Selector's
  condition bit both clear mode, FAD/range and all subheader predicates.
  They do not erase true/false connectors. Reset Selector's independently
  selected connector bits still take effect. In particular the initial
  FAD range is zero, not FFFFFFFF, and initialization does not silently
  reroute the filter to partition/filter zero.
- primary source: ST-162-062094 printed p.88 function 5.5, initialization
  item 3 (zero conditions, other mode selections ignored); p.91 function
  5.9, reset-bit diagram and initial-values list separating conditions
  from input/true/false connector initialization. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:704-721,3114-3117,3945-3947`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, uses the same condition-only
  operation in both commands. Ymir 6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/include/ymir/hw/cdblock/cdblock_filter.hpp:21-39`, blob
  d1c51615ebf26ecb20c0b32c6d3b4f628fcf19e5, distinguishes ResetConditions
  from Reset topology. Upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d
  and local fb9c337a command bodies inspected: selected-mode reset memsets
  the whole filter; bulk-condition reset sets range FFFFFFFF. No reference
  code block imported.
- expected observable: Get Filter Range/Mode/Subheader report zero after
  either form; existing nonidentity/disconnected connectors remain intact
  unless their reset bits were also supplied. Ordinary mode writes retain
  conditions/connections except the written mode. Exact bits, zero tolerance.
- suggested method: set nondefault conditions and graph, invoke selected
  initialization and bulk bit4, query state and route a sector. Then combine
  bit4 with bits6/7 to distinguish individually requested connector resets;
  repeat across all selectors and native save/load.
- falsifier: a condition initializer changes an unselected connector,
  leaves a predicate nonzero, gives a nonzero initial FAD range, affects
  another selected-mode target, or changes ordinary mode-write behavior.
- self-check run (method-level, unvalidated): 4,800 selected-filter cases,
  1,536 ordinary mode controls, 1,024 bulk condition/connector-mask cases;
  fail-fast UBSan exit 0. Historical fb9c337a fails the connector assertion
  at generated line 208. All five current CD implementation probes and
  existing CD transfer/HIRQ/trace method checks exit 0; CD warning-enabled
  C++20 syntax/diff checks exit 0. No full build/native qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: actual initialization latency, live-sector
  collisions, reserved mode programming, malformed cycles, broader input
  ownership, native game/firmware/save-manager behavior. Connector-byte
  combinations include storage diagnostics, not authorization of cyclic
  graphs. No new fields or additional save-layout break; no validator or
  existing expectation edits, host-transfer algorithms or frozen CPU/
  sound/video paths changed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0062 | CD-01 | 6d66e5d2 | UNVALIDATED | Command 47 returns a selector's true/false connections instead of reaching unknown-command dispatch |

### IMPL-0062 — CD-01 — Get Filter Connection command

- branch/commit/base: `arena/01a0b897-mame` @ **6d66e5d2**; base **06b9ca36**.
- files: `src/mame/sega/saturn_cd_hle.cpp:1566-1579` and command dispatch
  case 47; matching declaration in `saturn_cd_hle.h`;
  `saturn_pending/impl_checks/check_cd_get_filter_connection.py`.
- contract: command 47, filter number CR3 high byte, returns current status
  in CR1, true connection/false connection in CR2 high/low bytes, filter
  number in CR3 high byte and zero CR4. FF means disconnected. Complete
  with CMOK, preserving existing HIRQ causes without newly setting ESEL.
  The query does not change selector conditions/connections. Invalid filter
  indices use the existing standard REJECT response helper, without indexing
  outside the 24 selectors.
- primary source: ST-162-062094 printed p.90 function 5.8 Get Filter
  Connection; p.30 Table 3.2 lists setting commands (not this query) under
  ESEL. SDK blob `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3176-3193`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  supplies the exact register layout/bounds. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:2519-2545`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, agrees. Local history/base and
  upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d command dispatch
  were checked: no case 47/handler existed. No reference block imported.
- expected observable: for filter 7 true->23/false->FF while paused,
  response CR1=0100, CR2=17FF, CR3=0700, CR4=0000, with CMOK asserted
  and no new ESEL. Exact response bits and unchanged graph, zero tolerance.
- suggested method: mapped Set Filter Connection followed by command 47
  for each selector and disconnected endpoints; read all four response
  registers/HIRQ. Also check queued command execution and native IRQ/DRC
  behavior rather than treating the extracted dispatch arm as a scheduler.
- falsifier: wrong selector/byte order, changed graph, newly generated ESEL,
  missing CMOK, unmapped dispatch or out-of-bounds invalid-filter access.
- self-check run (method-level, unvalidated): 30,000 valid connector/status
  readbacks and 232 invalid-index controls through the actual handler and
  extracted production dispatch arm, fail-fast UBSan exit 0. Historical
  06b9ca36 is rejected structurally for missing case 47; this is not a
  historical native execution. CD warning-enabled C++20 syntax/diff checks
  exit 0. No full build, existing fixture changes or native qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: mapped transport/timing, complete command
  scheduler, native IRQ/firmware/gameplay and save-manager behavior. No new
  fields/additional save-layout change; no modifications to existing data
  transfer/HIRQ handlers or frozen SH/sound/video paths.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0063 | CD-01 | 4725d0c2 | UNVALIDATED | Taking a filter input displaces its old CD/false-output producer while true-output fan-in remains legal |

### IMPL-0063 — CD-01 — selector connection ownership

- branch/commit/base: `arena/01a0b897-mame` @ **4725d0c2**; base **e28aeea2**.
- files: `src/mame/sega/saturn_cd_hle.cpp:1330-1357,1537-1559,1638-1643,2092-2094`,
  matching private helper declaration in `saturn_cd_hle.h`;
  `saturn_pending/impl_checks/check_cd_connection_ownership.py`;
  COPY/MOVE probe extraction/declaration adapter (no expectation changes).
- contract: explicit CD and false-output connector setters disconnect prior
  producers of their destination filter input before attaching their new
  producer. True-output connectors are unaffected by this exclusive-input
  rule because multiple filters can feed one partition. FF disconnects only
  the selected producer. Selected endpoints must be 0..23 or FF; reject
  invalid source/selected endpoints before any graph change, while ignoring
  unselected parameter bytes. COPY/MOVE reuses the same input-detachment
  helper after its existing preflight. Reset Selector bit5 disconnects both
  actual CD input and reported CD number, and all false-output producers.
- primary source: ST-162-062094 printed p.46 Table 5.1 single-producer filter
  input versus multi-producer partition input, pp.83-84 device connection
  functions 4.1/4.2, p.90 function 5.7's individually enabled connector
  changes/disconnected sentinel, p.91 function 5.9 input initialization.
  SDK blob `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:843-850,863-889,2979-2999,3145-3171`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e: exclusive input disconnection,
  CD connector assignment and selected-endpoint preflight. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:1646-1680,2230-2249,2483-2515`,
  blob e8fedadb2d7374db35667bd064bb47fdc14b41a8, cross-checks connection
  reassignment but is not the oracle for CD displacement/invalid outputs.
  Local/upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d setters were
  reviewed: direct assignment, no exclusive-producer handling and CD invalid
  parameter popmessage rather than rejection. Existing local COPY/MOVE had
  a narrower inline disconnector. No reference block imported.
- expected observable: after CD->7, setting filter3 false->7 leaves CD
  disconnected/number FF and filter3 owning input7. CD->7 then disconnects
  filter3's false output. Other true-output producers to partition7 remain.
  A rejected two-output update leaves both outputs and CD state unchanged.
  Input reset reads back CD number FF. Exact bytes/links, zero tolerance.
- suggested method: program all producer transitions through mapped command
  registers, query via commands31/47, route tagged sectors and repeat around
  accepted versus WAIT COPY/MOVE. Check native IRQ timing separately.
- falsifier: two remaining producers for a taken input, loss of independent
  true-output fan-in, changed unselected fields, partial rejected update,
  stale reported CD connection after input reset, or disconnecting an actual
  unrelated CD pointer because a legacy reported number disagrees with it.
- self-check run (method-level, unvalidated): 15,625 CD connector cases,
  10,800 false-output ownership cases, 8,423 selected-byte/bounds controls,
  24 input resets, actual-pointer/stale-number controls; fail-fast UBSan
  exit 0. Historical e28aeea2 fails graph preservation/ownership comparison
  at generated line 248. Existing COPY/MOVE ASan/UBSan and condition-reset
  probes exit 0; warning-enabled CD C++20 syntax/diff checks exit 0.
- state: **UNVALIDATED**.
- not covered/known doubts: file/directory commands still assign CD pointers
  directly and can leave visible connection numbers stale; the helper uses
  actual pointers so those states do not detach an unrelated active input.
  File-command complete topology/condition/partition initialization remains
  separate. Existing invalid-command ESEL convention is retained, not claimed
  as newly measured reject timing. Read File/drive-phase timing, stream
  collisions, actual command scheduler, native IRQ/save/game behavior are
  excluded. Duplicate-input/cyclic combinations are storage diagnostics, not
  claims that such graphs are legal running streams. No new state fields or
  extra layout break; no validator asset/expectation/frozen-path changes.

### IMPL-0063 primary page correction (append-only)

The CD device connection functions 4.1/4.2 are on ST-162 printed **p.86**,
not pp.83-84 as stated above. Table 5.1/p.46 and selector pp.90-91 anchors
are unchanged. No code or contract change.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0064 | CD-01 | 5f26ee35 | UNVALIDATED | Selector range/subheader/mode queries echo the filter number and complete with CMOK without generating ESEL |

### IMPL-0064 — CD-01 — selector query register images/completion

- branch/commit/base: `arena/01a0b897-mame` @ **5f26ee35**; base **efc64c4f**.
- files: `src/mame/sega/saturn_cd_hle.cpp` cmd_get_filter_range,
  cmd_get_filter_subheader_conditions, cmd_get_filter_mode;
  `saturn_pending/impl_checks/check_cd_filter_queries.py`.
- contract: commands 41/43/45 preserve the requested filter number in CR3's
  high byte, alongside respectively range high byte, file ID, or zero in
  the low byte. They return the other existing predicate words unchanged.
  Successful and rejected queries set CMOK only; pending ESEL/other HIRQ
  bits are preserved, but queries do not manufacture a selector-set event.
- primary source: ST-162-062094 printed p.87 functions 5.2/5.4 and p.89
  function 5.6 specify selector queries; p.30 Table 3.2 distinguishes ESEL
  setting commands from queries. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3038-3055,3088-3103,3128-3142`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, has CR3's echoed index and
  normal command response without TriggerIRQ(ESEL). Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:2323-2349,2391-2419,2455-2481`,
  blob e8fedadb2d7374db35667bd064bb47fdc14b41a8, agrees on register images
  but spuriously includes ESEL for subheader/mode (not range); it is NOT
  used as an IRQ oracle for those two commands. Local history/base and
  upstream MAME 398bba74ed7997d29c2316316da230f6d85fda0d implementations
  were reviewed: all three omitted CR3 index and included ESEL. No imported
  reference block or modification of HIRQ read/ack/update implementations.
- expected observable: querying filter7 returns CR3=07xx (range high/file
  number) or 0700 (mode), not 00xx. With ESEL initially clear it remains
  clear; with ESEL initially pending it stays pending. Exact register bits,
  zero tolerance; conditions/topology are unchanged by query.
- suggested method: write varied 24-bit ranges, subheader bytes and legal
  modes to all filters, clear completion causes as the host would, query,
  then compare response words and interrupt causes. Repeat with unrelated
  pending causes and rejected filter indices. Native command sequencing,
  bus mapping and IRQ timing must be tested separately by validation.
- falsifier: dropped/wrong filter index, corrupted range/subheader/mode,
  changed graph, newly set ESEL from a query, cleared pending cause, missing
  CMOK, or invalid-index out-of-bounds access.
- self-check run (method-level, unvalidated): actual six getter/setter bodies
  and extracted dispatch arms, 18,432 setter operations, 110,592 query/IRQ
  images and 696 invalid-filter controls, fail-fast UBSan exit 0. Historical
  efc64c4f fails HIRQ at generated line217; an isolated missing-CR3-index
  mutant fails the range response at line219. Warning-enabled CD C++20
  syntax/diff checks exit 0. No full build or native qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: timing and races against live selector changes,
  full scheduler, actual host transport/IRQ delivery and firmware/gameplay.
  Prior pending ESEL is intentionally not acknowledged by reads. No new
  fields/additional save-layout changes, validator asset/fixture expectation
  edits or frozen CPU/sound/video changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0065 | CD-01 | aef4ff30 | UNVALIDATED | Sector-information query honors full 16-bit position and END, returns stored metadata, and does not generate ESEL |

### IMPL-0065 — CD-01 — sector-information position/query semantics

- branch/commit/base: `arena/01a0b897-mame` @ **aef4ff30**; base **0e840253**.
- files: `src/mame/sega/saturn_cd_hle.cpp` cmd_get_sector_information;
  `saturn_pending/impl_checks/check_cd_sector_information.py`.
- contract: command54 consumes the complete CR2 sector position; FFFF means
  the selected partition's last sector. Only positions within that
  partition's count (and physical array capacity) are addressable; empty,
  invalid-selector and null-storage requests use standard REJECT instead
  of aliasing a low-byte position or dereferencing inaccessible storage.
  Return FAD and file/channel/submode/coding bytes without changing sectors.
  Complete query with CMOK, not newly generated ESEL.
- primary source: ST-162-062094 printed p.93 function 6.5 specifies END and
  selected-sector header/subheader retrieval; p.30 Table 3.2 does not list
  this query as an ESEL-setting operation. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3347-3375`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  uses full position/FFFF, rejects unavailable selectors/sectors, and returns
  matching register packing without ESEL. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:2746-2780`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, cross-checks packing/CMOK only;
  its byte-position decoder/boundary check is not an oracle for ranges.
  Local history/base and upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d were checked: low-byte masking
  and ESEL remained in the old handler. No reference code block imported.
- expected observable: with three sectors, END returns metadata of position2;
  0100 must not return position0. Each legal query returns the exact selected
  FAD/subheader bytes and leaves sector count/data unchanged. No extra ESEL;
  preserve already pending interrupt causes. Zero byte/position tolerance.
- suggested method: query all positions and END in partitions with
  0/1/3/199/200 sectors, using noncontiguous pool IDs and distinct metadata;
  compare native register responses/HIRQ and re-read stored data. Run raw/
  cooked Mode1/Mode2 ingestion separately; this change does not create raw
  PUT metadata that the existing ingestion path does not retain.
- falsifier: byte-wrapped position accepted, missing/wrong END selection,
  response from beyond the partition count, wrong metadata packing,
  out-of-bounds/null access, changed sector state or query-generated ESEL.
- self-check run (method-level, unvalidated): all 65,536 positions across
  24 partitions/five lengths, 9,768 metadata/END responses, 7,854,784 invalid/
  unavailable controls plus null-pointer diagnostic; ASan/fail-fast UBSan
  exit 0. Historical 0e840253 fails HIRQ at generated line109; low-byte
  position mutant fails reject at line108 and no-END mutant fails response
  at line105. Warning-enabled CD C++20 syntax/diff checks exit 0.
- state: **UNVALIDATED**.
- not covered/known doubts: no native transport/scheduling/game/IRQ or
  media-present standard-response qualification. The shared standard-return
  helper currently ignores its supplied status when no image is mounted;
  that separate existing defect can mask REJECT in empty-media native runs
  and is not concealed by the mocked helper used here. REJECT selection for
  invalid requests follows the specific pinned command handler, not a claim
  that all unavailable CD stream ranges reject rather than WAIT. Raw PUT
  metadata, unrelated full-width offset decoders and FAD search remain
  separate. No new state/layout change, validator or frozen-path edits.

### IMPL-0065 mutation line correction (append-only)

The stored mutant logs report byte-position rejection at generated **line109**
and no-END response at **line107**, not lines108/105. Failure predicates and
outcomes are unchanged; `/tmp/impl-ref/cd-sectorinfo-{byte-position,no-end}.log`
are method-level raw output, not native evidence.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0066 | CD-01 | 577ba67c | UNVALIDATED | Standard responses retain the requested REJECT/WAIT status even without mounted media |

### IMPL-0066 — CD-01 — empty-media command status

- branch/commit/base: `arena/01a0b897-mame` @ **577ba67c**; base **38fefea4**.
- files: `src/mame/sega/saturn_cd_hle.cpp:766-774` cr_standard_return;
  `saturn_pending/impl_checks/check_cd_empty_media_response.py`.
- contract: when the caller supplies a command response status, a missing
  image must not replace that status with the normal OPEN/NODISC drive
  status. Honor the requested status in the same way as media-present
  response branches. Retain existing low response byte/other report words
  in this no-image branch; no drive/media/IRQ side effects are introduced.
- primary source: ST-162-062094 printed p.31 section3.3 defines improper
  command REJECT and deferred WAIT responses independent of drive status;
  p.59 Data Specification4.0 defines FF as REJECT and bit7 as WAIT with a
  valid drive-status code. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:1852-1870`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  passes rejected/WAIT status into MakeReport without an image-existence
  override. Ymir 6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:1232-1242`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, packs the provided status.
  Local blame 5a6b74a52 and upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d cr_standard_return were inspected:
  the no-image branch used cd_stat instead of cur_status. No reference block
  imported; media-present branches are unchanged.
- expected observable: with cd_stat=0700 and no media, an invalid selector
  command returns status byte FF, not 07. An explicitly requested WAIT over
  OPEN/NODISC returns 86/87, not 06/07. Normal status calls still return the
  supplied normal status. Exact status byte, zero tolerance.
- suggested method: boot empty/tray-open, send invalid selector/sector
  commands, inspect CR1 high byte and unchanged graph. Exercise native
  deferred-response callers separately; compare media-present response
  words and relevant frozen boot/game paths through the validation agent.
- falsifier: suppressed REJECT/WAIT due to absent image, read of disc metadata
  in the no-image branch, changed untouched media-present formatting, or
  accidental state/IRQ change from standard-response generation alone.
- self-check run (method-level, unvalidated): actual standard-return helper,
  1,536 absent-image status images; 695 actual rejected selector/sector/CD
  connection commands using that helper; 384 media-present formatting
  controls; fail-fast UBSan exit 0. Historical 38fefea4 fails status-byte
  comparison at generated line147. CD warning-enabled C++20 syntax/diff
  checks exit 0. No native media/BIOS/full-build qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: low report fields in OPEN/NODISC, WAIT report
  validity/flag normalization, seek-track numbering, physical tray event
  ordering, command scheduler and actual IRQ/firmware behavior remain
  separate. Mock metadata controls protect untouched branches but do not
  qualify their existing hardware semantics. No new fields/layout change,
  validator asset/expectation or frozen CPU/sound/video edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0067 | CD-01 | 7761a188 | UNVALIDATED | File-information transfer deactivates after exactly the advertised six words per record, without consuming a seventh word |

### IMPL-0067 — CD-01 — file-information transfer end boundary

- branch/commit/base: `arena/01a0b897-mame` @ **7761a188**; base **aec0f985**.
- files: `src/mame/sega/saturn_cd_hle.cpp` dataxfer_word_r FILEINFO_1 and
  FILEINFO_254 cases; `saturn_pending/impl_checks/check_cd_file_transfer_length.py`.
- contract: file-information transfer finishes at 12 bytes for one record,
  or at 254*12 bytes for the existing advertised full-table transfer. The
  final advertised word makes the transfer inactive and resets its position.
  Extra reads must not consume another file word or increment DataEnd count.
- primary source: ST-162-062094 printed p.100 function 8.4 specifies 12-byte
  file information and up to254 records; p.32 section3.4 transfer procedure
  and end semantics. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3824-3840`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  specifies six words per file. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:1365-1387`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, sets transfer length to
  numFileInfos*12/sizeof(uint16). Neither is an oracle for the local legacy
  padded-short-directory policy. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d and local history/base used strict
  greater-than cutoffs for these cases; TOC/subcode cases already used >=.
- expected observable: single-file DataEnd returns six words, not seven
  after one extra read; full 254-record transfer returns1,524, not1,525.
  No advance to a nonexistent255th ordinary record. Exact words/bytes,
  zero tolerance; ordinary six-word record content is unchanged.
- suggested method: native command73, read exactly its announced word count
  and then an extra read, request DataEnd and compare counts; repeat partial
  transfers and native save/load at every word and record boundary.
- falsifier: transfer still active at the advertised boundary, extra word
  consumed/counted, early truncation, changed remaining payload, or wrong
  DataEnd word count after the boundary.
- self-check run (method-level, unvalidated): 24 advertised streams,
  6,240 every-word state-copy continuations, 224 TOC/subcode boundary
  controls and extra-read/DataEnd checks; ASan/fail-fast UBSan exit0.
  Historical aec0f985 fails exact-boundary assertion at generated line281.
  Warning-enabled CD C++20 syntax/diff checks exit0. Prior aggregate at
  aec0f985 ran all ten preceding CD probes plus existing CD transfer/HIRQ/
  trace checks, all exit0 (raw outputs are method-level, unvalidated).
- state: **UNVALIDATED**.
- not covered/known doubts: idle-bus data value and DRDY timing, short-table
  padding versus actual held-record count, file-number/attribute parsing,
  unit/gap field ordering, raw media transfer scheduling and native
  gameplay/save-manager behavior. State copies are NOT file save/load.
  No new fields/save-layout change, existing fixture expectation changes,
  HIRQ handler changes or frozen CPU/sound/video changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0068 | CD-01 | c726048c | UNVALIDATED | File-information record byte8 is file unit size and byte9 is interleave gap, in both single/all-record paths |

### IMPL-0068 — CD-01 — file-information interleave-field packing

- branch/commit/base: `arena/01a0b897-mame` @ **c726048c**; base **0b15821c**.
- files: `src/mame/sega/saturn_cd_hle.cpp` dataxfer_word_r FILEINFO_254
  record staging and cmd_get_target_file_info single-record staging;
  `saturn_pending/impl_checks/check_cd_file_info_interleave.py`.
- contract: pack file unit size before gap size in the 12-byte file-information
  record. Thus host word4 (zero based) is unit<<8|gap, not gap<<8|unit.
  Apply identically when staging a single file and a full-table record;
  retain the other existing record fields/count behavior.
- primary source: ST-162-062094 printed p.72 Data Specification6.8 CdcFile
  orders FAD, byte size, unit, gap, file number, attributes; p.100 function
  8.4 specifies its 12-byte transfer. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:908-928`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  has unit/gap in that order in its 12-byte FileInfoS. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:1390-1402`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, explicitly packs unit high/gap
  low into transfer word4. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d and local history/base had the
  reverse staging order in both paths, despite the single-file comment
  listing unit before gap. No reference block imported.
- expected observable: file unit2/gap3 returns word4=0203, not0302; both
  selectors of command73 produce the same field order. Exact bytes, zero
  tolerance; FAD/length/attribute values and transfer count are retained.
- suggested method: authored legal ISO/XA directory record with unequal
  unit/gap values, request single file and all held information, read six
  words and compare the fifth. Repeat on native command/data transport,
  including partial full-table transfer and DataEnd.
- falsifier: swapped unit/gap in either path, corrupted other unchanged
  fields, or changed word count/termination behavior.
- self-check run (method-level, unvalidated): 131,072 single/all-first-record
  images across every unit/gap byte pair, checking FAD/length/attribute
  retention and DataEnd count; fail-fast UBSan exit0. Historical0b15821c
  fails word4 at generated line282. Previous file-transfer boundary probe
  ASan/UBSan, warning-enabled CD C++20 syntax and diff checks exit0.
- state: **UNVALIDATED**.
- not covered/known doubts: all byte pairs are storage diagnostics, not a
  claim all describe legal interleave streams. ISO/XA parser validity, XA
  file number/attribute derivation, file-table window/count, native stream
  timing/gameplay/save-manager behavior remain separate. No new fields or
  layout break, validator/fixture or frozen-path edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0069 | CD-05 | 5da1c7fe | UNVALIDATED | Save staged TOC/subcode/single-file response bytes alongside their word-transfer cursors |

### IMPL-0069 — CD-05 — word-transfer staging save coherence

- branch/commit/base: `arena/01a0b897-mame` @ **5da1c7fe**; base **c6b66a01**.
- files: `src/mame/sega/saturn_cd_hle.cpp` device_start payload registrations;
  `saturn_cd_hle.h` tocbuf/subqbuf/subrwbuf/finfbuf initializers;
  `saturn_pending/impl_checks/check_cd_word_buffer_save.py`.
- contract: register all698 staging bytes (408TOC,10subQ,24subRW,256file
  staging) with the already registered transfer kind/byte counters. Loading
  an image must restore the pending word payload, not retain bytes from a
  later command. Initial backing arrays are zeroed for deterministic native
  serialization; this does not assert a hardware value for unexposed bytes.
- primary source: ST-162-062094 printed p.32 section3.4 data transfer,
  p.77 function1.3 TOC, p.85 subcode functions3.1/3.2, p.100 file-info
  function8.4 define the visible response streams; SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`. Save/load coherence is an
  emulator lifecycle obligation, not an emulated CD hardware instruction.
- cross-checks/provenance: Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:328-342,472-487`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, saves/restores transfer buffer
  with position/count. Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:4309-4314,4355,4370-4372,4382`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, includes FIFO/TOC/subcode/file
  backing. Native MAME src/emu/save.h typed array registrations are used,
  not host-pointer serialization. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d and local base device_start
  were reviewed: cursor/state saved, these response arrays absent.
- expected observable: save after any word, issue another command that
  overwrites staging, load and finish the old TOC/subQ/subRW/single-file
  transfer: remaining words and final DataEnd response match uninterrupted
  operation exactly. Zero word/byte/count tolerance and no load-only IRQ.
- suggested method: native save/mutate/load for each of the four transfer
  kinds, before/after final word and at all meaningful word boundaries;
  compare response stream/count and actual save-manager acceptance.
- falsifier: post-save payload leaks into restored transfer, type/cursor
  payload mismatch, changed remaining word/count, load-only IRQ edge or
  rejected native array registration.
- self-check run (method-level, unvalidated): actual production registrations
  and word-reader/DataEnd bodies through byte serializer;59,136 replay
  images covering every word cut and256 payload patterns across all four
  kinds, checking all backing bytes and responses; ASan/fail-fast UBSan
  exit0. Historical c6b66a01 fails replay words at generated line245.
  Warning-enabled CD C++20 syntax/diff checks exit0. No full build/native
  save-file qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: **save-state layout break** from new registered
  arrays; old files not claimed compatible. Full-table FILEINFO_254 still
  depends on unsaved dynamic curdir/root, so this does NOT close complete
  CD-05. Directory/MPEG/remaining drive-phase state, native event/IRQ/media
  reconstruction and game regressions remain separate. No transfer
  algorithms, reset-time compatibility exceptions, validator expectations
  or frozen SH/sound/video behavior changed.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0070 | CD-05 | ae7a9c56 | UNVALIDATED | Save the automatic buffer-full pause reason and seek-phase latch with the drive state |

### IMPL-0070 — CD-05 — drive-phase latch save coherence

- branch/commit/base: `arena/01a0b897-mame` @ **ae7a9c56**; base **84a51d05**.
- files: `src/mame/sega/saturn_cd_hle.cpp` device_start registrations for
  buffull_temp_pause and m_seek_in_progress;
  `saturn_pending/impl_checks/check_cd_drive_phase_save.py`.
- contract: preserve the reason for PAUSE alongside the already saved drive
  status/buffer-full flag/remaining sectors; a restored automatic pause must
  resume when space becomes available, while a restored manual pause must
  not inherit a later automatic-resume reason. Preserve the existing seek
  phase latch as well as its registered remaining-tick/status fields. No
  drive algorithm, seek approximation or callback behavior is changed.
- primary source: ST-162-062094 printed p.52 section6.2.2 item3, pause when
  full and cancel-pause/read remaining files after space becomes available;
  p.53 drive-command interaction preserves auto-pause/cancel-pause behavior.
  SDK blob `37cf17209eb176d6580bd55bf11af1694ae1f328`. Saving lifecycle
  latches is an emulator obligation, not a new hardware save command.
- cross-checks/provenance: Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:290-305,436-451`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, serializes seek ticks and
  bufferFullPause with drive state. Mednafen
  f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:4324,4416-4425`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, saves drive phase and repairs
  phase-related state on load. Local/base and upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d registrations were inspected:
  these two reset-initialized latches were absent. Native typed save_item
  registrations used; no imported reference block.
- expected observable: save automatic PAUSE, change to manual PAUSE, load
  and free space: the resumed stream follows the uninterrupted drive trace.
  Conversely a saved manual PAUSE remains paused after load even if later
  emulation had set the full-buffer pause flag. Exact state/continuation,
  zero FAD/count tolerance; no load-only IRQ.
- suggested method: fill native sector pool while playing, save during
  automatic pause, consume a sector/change playback, load and consume a
  sector again; compare status/FAD/IRQ/count sequence. Repeat manual pause
  and in-progress seeks with native file saves/timers.
- falsifier: restored auto-pause fails to resume, manual pause resumes
  spuriously, latch differs from saved value, changed remaining drive
  trace, or callback generated by registration/image restoration itself.
- self-check run (method-level, unvalidated): actual cd_playdata and
  cd_change_status through mocked media/sector/audio and byte serializer;
  160 pause and1,536 seek-phase replays with cuts and buffer-space events,
  fail-fast UBSan exit0. Historical84a51d05 fails restored latch at generated
  line234. A historical control with the immediate latch assertion omitted
  also fails actual subsequent drive trace at line235. Warning-enabled CD
  C++20 syntax/diff checks exit0. No full build/native timer qualification.
- state: **UNVALIDATED**.
- not covered/known doubts: **save-state layout break** from two additional
  existing-field registrations; no old-file compatibility claim. The seek
  flag is currently mostly bookkeeping; this does not establish physical
  seek timing. Sector allocation, CDDA output, media identity, scheduler
  events and native IRQ delivery are mocked/excluded. Directory/MPEG and
  whole-CD save acceptance remain open. No new fields, changed drive
  algorithms, validator expectations or frozen-path edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0071 | CD-01 | c802ea54 | UNVALIDATED | Read File decodes 24-bit offset/identifier and derives an untruncated range in 2048-byte logical sectors |

### IMPL-0071 — CD-01 — Read File packet/range widths

- branch/commit/base: `arena/01a0b897-mame` @ **c802ea54**; base **945275fe**.
- files: `src/mame/sega/saturn_cd_hle.cpp` cmd_read_file;
  `saturn_pending/impl_checks/check_cd_read_file_range.py`.
- contract (existing directory entry, valid offset within the file): assemble
  offset from CR1 low byte/CR2 and file identifier from CR3 low byte/CR4
  without truncation. Derive remaining logical sectors as ceil(length/2048)
  minus offset, independently of host Get Sector Length; widen rounding
  before addition and retain counts above65535. Start FAD is the24-bit sum
  of the entry FAD and logical offset. High file-ID bytes must not alias a
  smaller cached entry before the existing bounds guard.
- primary source: ST-162-062094 printed p.100 function8.5 specifies file
  identifier and logical-sector offset; p.95 function7.1 limits host sector
  length selection to fetch/write and actual-data-size behavior, SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`. ST-040-R4-051795 printed
  p.23 section3.3 defines file-sector accounting converted to2048 bytes,
  SDK blob `2e56c214c756ec98944dfca9a843c6b1bbeaf8d3`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3865-3888`, blob d367dd0c0500ff7b1e2637e748015543b0a3078e,
  has24-bit offset/ID,24-bit FAD and2048-byte sector accounting. Its own
  beyond-EOF FIXME is not a hardware oracle. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:3227-3247,928-934`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, agrees on packet widths and
 2048 accounting, but its full end-position formula is NOT adopted.
  Upstream MAME398bba74ed7997d29c2316316da230f6d85fda0d and local
  history/base were inspected: offset lost CR2 high bits/placed CR1 at bit8,
  file ID/remaining count used16-bit locals, and file length used sectlenin.
- expected observable: offset000100 starts at entryFAD+256 rather than
  entryFAD, regardless of2048/2336/2340/2352 host fetch selection. A70000
  logical-sector file at offset0 keeps70000 remaining sectors, not4464.
  ID010002 cannot read cached ID000002. Exact FAD/count/ID, zero tolerance.
- suggested method: native Read File over ordinary noninterleaved files,
  including offsets with bits8-23 set and files above128MiB; compare first
  stored FAD and remaining/end range across host fetch sizes. Separate
  diagnostic24-bit FAD-wrap/max-byte-size cases from valid physical discs.
- falsifier: discarded command bits, high-ID aliasing, host fetch size
  changes file geometry, truncated remaining range, overflow during byte
  rounding, or wrong24-bit start FAD.
- self-check run (method-level, unvalidated): actual Read File/status bodies,
  7,296 valid-offset range images across all selectors/fetch sizes, plus
  1,275 high-ID nonalias controls; fail-fast UBSan exit0. Historical945275fe
  fails FAD/count comparison at generated line157. Warning-enabled CD C++20
  syntax/diff checks exit0. No native playback/full build.
- state: **UNVALIDATED**.
- not covered/known doubts: **BLOCKED(hardware command74 response/drive
  transition for offset at/past EOF)**; do not infer a new error policy
  from the reference's unsigned underflow. Invalid/nonheld-ID response
  status, directory-held-window mapping, XA interleaving/filter setup,
  source partition clearing, full file completion/IRQ and seek timing are
  separate. Maximum-length/FAD-wrap probes are arithmetic/storage diagnostics,
  not legal-disc qualification. Existing file-command connector assignment
  remains unchanged here. No new saved state/layout or validator/frozen
  path edits; no claim that Read File/CD-01 as a whole is complete.

### Checkpoint after IMPL-0071 — publication blocker and aggregate self-check

- Production commits through **c802ea54** were pushed successfully to
  `arena/01a0b897-mame`. Handoff commit **599fe5b3** exists locally, but its
  push failed: `fatal: could not read Username for 'https://github.com':
  terminal prompts disabled`. **BLOCKED(GitHub connection authentication)**
  for further publication. The user was asked to reconnect GitHub in Arena;
  no credentials were requested or stored. Do not force-push or switch
  branches when resuming.
- Aggregate method-level, unvalidated: all **15** current `check_cd_*.py`
  implementation probes exit0; existing CD transfer/HIRQ/trace checks exit0;
  warning-enabled CD TU C++20 syntax and diff checks exit0. Raw aggregate
  logs: `/tmp/impl-ref/cd-through-0071-*.log`. No full build, native BIOS/game
  run or validation-status promotion. No existing expectation edits.
- A local range-log command naming `origin/arena/01a0b897-mame` failed because
  this checkout lacks that remote-tracking ref; this is separate from the
  authentication failure. Successful push output establishes c802ea54 as the
  last published implementation, not an assumed tracking-ref comparison.
- Next actionable review: file commands still assign CD pointers directly,
  without matching visible cddevicenum/exclusive-input ownership. Primary
  ST-162p.53 and pinned Mednafen cdb.cpp:1119-1121,3890 support routing those
  existing assignments through a common connection helper. No such change
  is included in0071. Complete file-table window/ISO-XA state and native
  directory serialization remain separate; avoid silently serializing an
  initially empty/resizing vector through the fixed-storage save wrapper.
- Commands55/56 remain absent. ST-162p.94 and Mednafen cdb.cpp:3380-3439
  define valid FAD search/response, but resolve partition-output detachment
  during active GETDELETE and failed-search result latching before guessing
  those edges: **BLOCKED(hardware command55 trace with active source output,
  and empty/invalid-position search followed by56)** for those contracts.
  This is not a reason to postpone independent documented implementations.

### Publication recovery after IMPL-0071 (append-only)

GitHub was reconnected. The resumed workspace retained file contents but its
local branch/index had reverted to82152a8b; previously local-only objects
599fe5b3/0e4c193b were absent. The remote still pointed to the successfully
published c802ea5405804e7299777dffe0a7b0a9e3280b24. A full-history fetch timed
out; its leftover processes were terminated and an exact shallow tip fetch
completed. All70 apparent changed/new files matched the published blob hashes
exactly; only the preserved handoff additions differed. A recovery copy was
saved outside the repository under /home/user/recovery-0071. The same session
branch/index was restored to c802ea54 with a mixed reset (no working files
overwritten), and the unpublished handoff text is being recommitted. This
restores local Git metadata to the existing published history, not a force
push, branch switch or rewrite of published commits. Earlier local-only
handoff commit IDs are historical notes, not claimed present after recovery.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0072 | CD-01 | 284acf62 | UNVALIDATED | Existing file-command CD connections update visible identity and displace the previous input producer |

### IMPL-0072 — CD-01 — file-command connection coherence

- branch/commit/base: `arena/01a0b897-mame` @ **284acf62**; base **a874c569**.
- files: `src/mame/sega/saturn_cd_hle.cpp:1339-1373,2187-2188` and
  cmd_read_file connection assignment; private declaration in saturn_cd_hle.h;
  `saturn_pending/impl_checks/check_cd_file_connections.py`. Three preceding
  probe declaration/extraction adapters only, no expectation edits.
- contract: wherever the existing Read File/Read Directory paths connect CD
  to an input, publish that same selector through cddevicenum and enforce
  exclusive input ownership. Reuse one helper in explicit Set CD Connection
  and both file paths. A subsequent false-output attachment to that input
  displaces CD coherently; a bounds-rejected file ID cannot take the input.
- primary source: ST-162-062094 printed p.53 section6.2.3 selector use by
  filesystem operations, p.46 Table5.1 exclusive filter input, p.86 function4.2
  reports actual CD connection. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:843-850,1119-1121,3890`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, routes filesystem attachment
  through its common connector setter. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:933-934,1646-1660`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, does the same for file playback.
  Upstream MAME398bba74ed7997d29c2316316da230f6d85fda0d and local base
  file methods had direct pointer-only assignments. No reference block
  imported; existing explicit setter bounds/response semantics retained.
- expected observable: explicit CD->5 then Read File using filter7 causes
  Get CD Connection to report07, not05. An old false producer of input7
  becomes disconnected. Subsequent filter3 false->7 reports CD disconnected
  (FF) with no stale active CD pointer. Exact links/readback, zero tolerance.
- suggested method: native file and explicit connection commands interleaved
  with31/47 queries and tagged-sector routing, including a file ID outside
  the cache and native save/load around connection replacement.
- falsifier: pointer/readback disagreement, retained competing input producer,
  changed unrelated selectors, or rejected file-ID request stealing the input.
- self-check run (method-level, unvalidated):31,250 file/directory connection
  images,48 subsequent false-output displacements and24 invalid-ID controls,
  fail-fast UBSan exit0. Historicala874c569 fails false-output ownership at
  generated line231. Existing ownership, empty-media response and Read File
  range probes, CD warning-enabled C++20 syntax/diff checks exit0.
- state: **UNVALIDATED**.
- not covered/known doubts: Read Directory still lacks held-table loading;
  full file predicate/topology initialization and partition clearing remain
  separate. FF/invalid file selectors retain the old pointer-disconnection
  path, now reportingFF coherently; diagnostic probes do NOT assert those
  selectors are legal file commands. Native firmware/game/timer/IRQ and
  directory save acceptance remain open. No new fields/layout break,
  validator expectations or frozen CPU/sound/video changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0073 | CD-01 | da1ca7c5 | UNVALIDATED | File-scope queries publish their response and CMOK without manufacturing filesystem completion |

### IMPL-0073 — CD-01 — file-scope query completion

- branch/commit/base: `arena/01a0b897-mame` @ **da1ca7c5**; base **5b9e738a**.
- files: `src/mame/sega/saturn_cd_hle.cpp` cmd_get_file_scope;
  `saturn_pending/impl_checks/check_cd_file_scope_completion.py`.
- contract: a Get File Scope query completes its command with CMOK, not a
  new EFLS event. Preserve all already pending causes. Populate its existing
  response words before the completion callback. Remove the unconditional
  four-register diagnostic dump; scope data calculations are unchanged.
- primary source: ST-162-062094 printed p.30 Table3.2 lists Move Directory,
  Hold File Information and Read File under EFLS, not Get File Scope;
  p.100 function8.3 is the scope query. SDK blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3785-3803,1872-1886`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, returns scope via BasicResults
  (CMOK without EFLS). Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:3160-3188`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, disagrees by setting EFLS;
  this candidate follows the primary flag table/Mednafen, not that behavior.
  Upstream MAME398bba74ed7997d29c2316316da230f6d85fda0d and local base
  had EFLS and callback-before-response. No reference block imported.
- expected observable: with EFLS clear, command72 leaves it clear and sets
  CMOK; with EFLS pending, it remains pending. Query completion does not
  falsely satisfy a wait for an outstanding filesystem operation. Exact
  cause bits, zero tolerance; no command72 change to directory state.
- suggested method: native query while observing/acknowledging completion
  causes, including previously pending EFLS; distinguish query CMOK from
  a genuine Read File/Read Directory end event and inspect response words.
- falsifier: query generates EFLS, loses a pending cause, fails to set CMOK,
  mutates filesystem state, or completion callback sees incomplete response.
- self-check run (method-level, unvalidated):262,144 status/pending-cause
  images using the actual getter and recording callback, fail-fast UBSan
  exit0. Historical5b9e738a fails cause comparison at generated line31.
  Warning-enabled CD C++20 syntax/diff checks exit0.
- state: **UNVALIDATED**.
- not covered/known doubts: existing scope count/first-ID/end-of-directory
  calculations, held-table validity/window, FLS-active WAIT policy, native
  timing/scheduler/bus/IRQ and gameplay remain separate. Reserved cause
  combinations are storage diagnostics. No new fields/save-layout change,
  validator expectations, HIRQ handler or frozen-path changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0074 | CD-01 | 546f6024 | UNVALIDATED | Preserve raw media data sectors and select GET/actual-size views using the fetching sector length |

### IMPL-0074 — CD-01 — lossless media backing and host sector views

- branch/commit/base: `arena/01a0b897-mame` @ **546f6024**; base **39b7c18e**.
- files: `src/mame/sega/saturn_cd_hle.h:82-107,269-270`;
  `src/mame/sega/saturn_cd_hle.cpp:148-150,216-224,294-295,419-460,
  1750-1782,1901-1912,2018-2029,3544-3545,3986-4024,4065-4077`;
  `saturn_pending/impl_checks/check_cd_raw_sector_views.py`; declaration/save
  adapters in implementation-owned buffer-save and selector-reset probes.
- contract: non-audio media data sectors retain all2352 bytes instead of
  destructively extracting the view selected at buffering time. For ordinary
  Mode1/Mode2 media, GET and GetDelete use the selected fetching length:
  2048-byte selection gives2048@byte16 for Mode1,2048@byte24 for Mode2Form1,
  and2324@byte24 for Mode2Form2;2336/2340/2352 select2336@16/2340@12/2352@0.
  Calculate Actual Data Size sums the current host-view sizes in16-bit words,
  rather than physical backing sizes. Latch the first view at GET acceptance
  and subsequent views at this HLE's logical sector boundaries; changes do
  not reinterpret a partially transferred view. Preserve legacy cooked
  audio/PUT representation and clear the raw marker when allocating anew.
  Copy/move carry the raw representation; GetDelete removes physical pool
  sizes, not variable host-view sizes. No reconstruction of discarded bytes.
- primary source: ST-162-062094 printed p.48 section5.4/Figure5.8 (sector
  layout), p.95 section8.2.7/function7.1 (four fetching/writing lengths,
  Mode2Form2 exception, fetching length reflected in actual-size calculation).
  SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 blob
  `37cf17209eb176d6580bd55bf11af1694ae1f328`, retrieved/extracted again.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:1333-1380,1416-1424,3307-3333,3509-3514`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e: raw byte views, first/next-sector
  setup and actual-size word counts. Its FIFO prefetch timing is NOT modeled
  here. Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:1316-1328,1478-1502`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, also starts a view at GET setup;
  its Mode2Form1 GetDelete extension to2324 disagrees with the primary's
  Form2-only exception and is NOT adopted. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d CD blob
  40be16847538ed7bd72934a55ab766e35b66ec20:1492-1514,2711-2747,2779-2793
  and local base39b7c18e retain buffer-time extraction/size accounting.
  Local available file history inspected; no reference source block imported.
- expected observable: buffer once at2048, then GET at2352 returns the original
  complete sector, not shifted payload/stale trailing bytes; subsequent GETs
  can select any of the four views without another media read. Actual-size
  per-sector words are1024 (Mode1/Form1) or1162 (Form2) at selection0,
  then1168/1170/1176 for selections1/2/3. Exact bytes/words, zero tolerance.
  Save/reload a partially read view after changing the fetching length:
  remaining bytes retain the old current view and the next sector uses the
  new view; no restoration IRQ. Physical block counts remain consistent.
- suggested method: native buffered mixed Mode1/Form1/Form2 media, all
  ingestion/fetching lengths, command52/53 counts and61/63 reads, length
  changes before first data access and within a sector, copy/move, native
  save/load at those cuts and DataEnd deletion/free-block accounting.
  Separately measure FIFO-prefetch boundaries; do not infer timing from the
  longword method's cursor boundary.
- falsifier: any retained raw byte missing/shifted, wrong Form2 byte count,
  count/stream disagreement for a fresh GET, mid-view reinterpretation,
  copy/move losing the marker/data, physical accounting leak, or a changed
  remaining stream/cause after state restoration.
- self-check run (method-level, unvalidated): ASan/fail-fast UBSan raw probe
  exits0:288 media/view/size/GETDELETE images,384 registered state replays
  with initial/mid-sector length changes,24 raw COPY/MOVE view controls and
  allocation-reuse control. Historical39b7c18e fails preservation at generated
  line928. Per-word geometry, missing geometry-save, missing marker-save,
  and late-first-view mutants fail at generated lines983/981/1001/983.
  All18 implementation-owned CD probes exit0. CD TU warning-enabled C++20
  syntax and diff checks exit0; no full build.
  **Fixture compilation break:** unmodified
  `regtests/saturn/test_cd_transfer.py` exits1 before behavioral assertions:
  its hand-written mock lacks `sectlenin`, `m_xfer_raw_offset`,
  `m_xfer_raw_size`, `m_xfer_raw_sector`. Validator-owned declaration adapter
  required; original file and expectations were NOT edited. A temporary,
  declaration-only in-memory adapter executes unchanged336 transfer,
  262144 HIRQ and observational trace assertions with exit0; this is not an
  unmodified-fixture or native-runtime result.
- state: **UNVALIDATED**.
- not covered/known doubts: **save-state layout break**: new pool/scratch
  raw markers and three transfer latches registered in this same change;
  old-save compatibility not claimed. Audio extraction, raw PUT layout,
  nonstandard mode-byte fallback, actual-size range/WAIT policy, active
  buffer mutations, native FIFO/bus/timer/DRQ timing, media read failure/ECC,
  firmware/gameplay and previously listed filesystem blockers remain open.
  The sector latch models logical HLE boundaries, not Mednafen's prefetched
  FIFO boundary. No validator expectations, frozen CPU/sound/video paths
  or milestone status changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0075 | CD-01 | 1ca56e77 | UNVALIDATED | Only Mode1 places the 2048-byte user-data view at byte16; other mode bytes use byte24 |

### IMPL-0075 — CD-01 — default user-data position

- branch/commit/base: `arena/01a0b897-mame` @ **1ca56e77**; base **7a8051fd**.
- files: `src/mame/sega/saturn_cd_hle.h:99-108`;
  `saturn_pending/impl_checks/check_cd_mode_fallback.py`.
- contract: when a raw block is fetched with selection2048, place user data
  at byte16 only when header byte15 is01. Otherwise use byte24. Retain the
  Form2 size exception only for Mode2 with submode bit5; no change to the
  three larger views or the legacy cooked representation. This extends0074
  beyond its ordinary Mode1/Mode2 scope without treating reserved modes as
  legal disc formats.
- primary source: ST-162-062094 printed p.48 section5.4(2)(a)-(c), Figure5.8:
  only Mode1 has user data immediately after the header; otherwise it is at
  the Mode2Form1 position. Non-Mode2 subheaders are interpreted as zero;
  non-CD user-data storage has a zero24-byte prefix. p.95/function7.1 gives
  the Form2-only length exception. SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73
  blob37cf17209eb176d6580bd55bf11af1694ae1f328.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:1345-1363`, blobd367dd0c0500ff7b1e2637e748015543b0a3078e,
  likewise distinguishes Mode1 from all others for the offset. Its GET size
  fallback also examines raw submode for non-Mode2 headers; that extension
  is not adopted, following the primary's zero interpreted subheader and
  Form2-only rule (its actual-size path3307-3321 is Mode2-specific).
  Upstream MAME398bba74ed7997d29c2316316da230f6d85fda0d,
  `src/mame/sega/saturn_cd_hle.cpp:2717-2730`, and local base use the inverse
  Mode2/otherwise test. No reference block imported.
- expected observable: a raw buffer with mode byte00 and fetching selection0
  returns2048 bytes starting at24, not16, regardless of uninterpreted byte18;
  actual size remains1024 words. Ordinary Mode1/Form1/Form2 and larger views
  retain0074 geometry. Exact byte offsets/counts, zero tolerance.
- suggested method: native raw buffers with zero/nonstandard header modes,
  distinct bytes at16 and24, compare the2048 view to the raw2352 view and
  command52/53. Treat malformed header patterns as storage diagnostics,
  not evidence of legal media modes or error-correction behavior.
- falsifier: non-01 header uses byte16, non-02 header spuriously extends to
 2324 because of uninterpreted byte18, or an ordinary/larger view changes.
- self-check run (method-level, unvalidated):262144 raw header/submode/view
  images and20 cooked controls exit0 with fail-fast UBSan. Historical
  7a8051fd header fails offset predicate at generated line39. Existing raw
  media/view/replay/copy probe, warning-enabled CD TU syntax and diff checks
  exit0. No native media, firmware or save-file acceptance claimed.
- state: **UNVALIDATED**.
- not covered/known doubts: raw PUT construction and routing, invalid media
  acceptance/ECC and FIFO timing remain open; no new state/layout change.
  The0074 validator mock compilation limitation is unchanged. No validator
  asset/expectation, frozen-path or milestone-status edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0076 | CD-01 | 51a73beb | UNVALIDATED | Set Sector Length rejects unsupported operands atomically and completes only after its response is populated |

### IMPL-0076 — CD-01 — sector-length command validation and publication

- branch/commit/base: `arena/01a0b897-mame` @ **51a73beb**; base **d5f452d3**.
- files: `src/mame/sega/saturn_cd_hle.cpp:1826-1849`;
  `saturn_pending/impl_checks/check_cd_sector_length.py`.
- contract: validate both fetching and writing length operands before changing
  either. Encodings00/01/02/03 select2048/2336/2340/2352 bytes; FF preserves
  that direction. Any other encoding rejects the whole request: preserve
  both lengths and pending causes, return REJECT with CMOK, no new ESEL.
  Accepted requests return the current standard status and CMOK|ESEL.
  Populate response before the IRQ callback. Do not change0074's latched
  active-sector geometry when updating the direction defaults.
- primary source: ST-162-062094 printed p.95 section8.2.7/function7.1 lists
  the four lengths and NOCHG; p.31 section3.3 defines malformed-command
  REJECT; p.30 Table3.2 assigns Set Sector Length to ESEL. SDK pin
  0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 blob
  37cf17209eb176d6580bd55bf11af1694ae1f328. REJECT report payload is invalid
  per p.31, so its low report words are not claimed as a hardware contract.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3445-3468,1872-1886`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, validates both byte encodings
  before applying either and generates ESEL only on the accepted branch;
  BasicResults publishes words before CMOK. Ymir
  6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:2833-2862`, ignores invalid
  encodings and still completes with ESEL: not adopted. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d CD method at1553ff and local base
  likewise silently ignore unsupported operands, can change the other
  direction, and publish after the callback. No reference block imported.
- expected observable: starting GET2336/PUT2340, command60 requesting GET0
  and PUT4 leaves both unchanged and returns REJECT/CMOK without new ESEL.
  GET0/PUTFF instead selects GET2048 while retaining PUT2340, with ESEL.
  Pending ESEL remains pending even on rejection. Exact bytes/cause bits,
  zero tolerance; callback sees the completed status rather than command60.
- suggested method: native command-port sweep of00..FF in both operand bytes
  with previously distinct lengths, pending ESEL both clear/set, and an
  active raw view; observe response, causes and subsequent GET/PUT lengths.
- falsifier: either direction changes on rejection, FF changes its direction,
  malformed input produces new ESEL, pending causes disappear, the callback
  sees stale response, or an active sector changes halfway through its view.
- self-check run (method-level, unvalidated):4194304 operand/previous-length/
  pending-cause images exit0 with fail-fast UBSan, actual setter and mock
  report/IRQ callback. Historicald5f452d3 fails combined completion/order
  predicate at generated line67; adapting only that historical callback
  order still fails the rejection-status predicate at line66. All20 own CD
  probes, warning-enabled CD TU syntax and diff checks exit0. No full build.
- state: **UNVALIDATED**.
- not covered/known doubts: native command latency, unsupported encodings on
  physical hardware, raw PUT/routing and all0074 exclusions remain open;
  reserved pending causes in the sweep are storage diagnostics. Existing
  length fields already saved; no new field/layout change. Validator mock
  declaration break from0074 remains reported, original expectations and
  frozen paths untouched. No completion-report status changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0077 | CD-01 | c5ca25a6 | UNVALIDATED | PUT privately reserves raw sectors, uses the writing length and filters the complete requested count at DataEnd |

### IMPL-0077 — CD-01 — raw PUT reservation, geometry and filter completion

- branch/commit/base: `arena/01a0b897-mame` @ **c5ca25a6**; base **25a58304**;
  includes production WIP **bc031027**. **Qualify with IMPL-0078/94da2d00**:
  the old Session Info helper spuriously marked a word transfer active,
  which would make this candidate's active-transfer preflight return WAIT.
- files: `src/mame/sega/saturn_cd_hle.h:248-249,319`;
  `src/mame/sega/saturn_cd_hle.cpp:195-198,232-253,303-308,500-556,
  1045-1106,2059-2162`; `saturn_pending/impl_checks/check_cd_raw_put.py`;
  dependency/declaration adapters in own buffer-save, raw-view, selector-reset
  and file-transfer probes; existing expectations retained.
- contract: command64 names a filter and a full16-bit sector count, not a
  partition offset. On acceptance reserve the whole count from the shared
  pool, privately, without replacing existing partition entries. Reject an
  invalid filter; WAIT for zero/unavailable count or a busy host interface,
  without changing input ownership or allocating a partial request. For
  nonoverlapping host-transfer sequences, write2352-byte backing using
  lengths2048/2336/2340/2352 at byte24/16/12/0, independently of GET length.
  Latch the first writing view at acceptance and later ones at the logical
  sector boundary. Unwritten storage is zeroed deterministically; only the
  documented absent header, not all unspecified bytes, is a hardware-zero
  claim. DataEnd derives FAD/subheader metadata, feeds **all** reserved
  sectors through the target filter, and appends accepted sectors to actual
  destinations; disconnected outputs discard/free them. This includes
  partially written and entirely unwritten sectors. Input ownership is
  reclaimed for filtering; Last Buffer Destination remains media-only.
  Zero-byte accepted PUT ends with zero transferred words, not DEND_ERR.
- primary source: ST-162-062094 printed p.48 section5.4/Figure5.8 (layout,
  non-Mode2 interpreted subheader, zero24-byte host-user-data prefix), p.95
  function7.1 (independent writing length), p.97 function7.5 (filter input,
  complete count even when interrupted, other bytes unspecified), p.81
  function1.10 (PUT block-word count equals host-word count, including partial
  transfer), pp.43-46 section5.3/Table5.1 (routing/single-producer input).
  SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 blob
  37cf17209eb176d6580bd55bf11af1694ae1f328. p.32/Table3.3 and p.80 describe
  asynchronous reservation failure; that timing/error phase is not modeled.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:723-731,1333-1340,1694-1780,2733-2759,3559-3604,
  4160-4186`, blobd367dd0c0500ff7b1e2637e748015543b0a3078e: zeroed reserved
  raw buffers, writing geometry, metadata-conditioned routing, all-buffer
  DataEnd filtering, preflight and sector-boundary writing length. Its
  clock costs are not used. Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:42-44,1333-1363,
  1556-1588,1622-1638,2983-3021`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, agrees on independent PUT layout
  and private scratch reservation but inserts directly into a partition;
  its missing filter traversal is not adopted. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d CD method at1740-1778 and local
  base truncate count to8 bits, use CR2 as an offset, allocate directly into
  the partition and use fetching size. No reference block imported.
- expected observable: PUT2 to filter0 with true->7 leaves partition7's old
  sector untouched and count unchanged while writing; DataEnd appends both
  new sectors there (or routes/discards them according to conditions), even
  after zero/partial writes. GET2048 after PUT2048 returns the submitted user
  bytes from raw byte24. Full GET2352 exposes the raw layout; command52/53
  and54 reflect the submitted view/metadata. Existing2048-byte partition
  plus two raw sectors accounts6752 physical bytes/three slots; GetDelete of
  the new pair frees exactly two slots. Exact specified bytes, words and
  ownership, zero tolerance; unspecified bytes have no hardware oracle.
- suggested method: native all PUT/GET length pairs, Mode1/Form1/Form2 raw
  submissions, nonidentity filter destinations, false chains/discard,
  initially nonempty destination, full pool, zero/partial DataEnd, high
  count bits, active-transfer refusal and native save/load while privately
  reserved after a writing-length change. Include frozen AB2/OutRun traces.
- falsifier: wrong input byte range/length, premature partition visibility,
  overwritten existing sector, fewer than the requested sectors processed
  at DataEnd, incorrect metadata/routing, count truncation, allocation/input
  mutation on refusal, leaked/double-owned pool slots, or divergent restored
  continuation. Ordinary2048 uploads must retain their user-data roundtrip.
- self-check run (method-level, unvalidated): ASan/fail-fast UBSan exits0:
  96 PUT/GET view images,72 partial/zero PUTs,240 registered-image replays,
  four filter routes,242 refusal controls and full200-sector release.
  Historical25a58304 fails private transfer ownership at generated line1076.
  Fetch-length, missing target/IDs/writing-length save, missing private pointer
  index, completed-only routing and8-bit count mutants fail at generated
  lines1135/1147/1150/1134/1191/1156/1214. All22 own CD probes at94da2d00,
  warning-enabled CD TU syntax and diff checks exit0; no full build.
  Unmodified validator transfer fixture still exits1 at compilation. It now
  additionally needs writing-length/PUT declarations and the completion helper
  dependencies. Original file/expectations untouched. A temporary adapter
  using actual finish/filter/disconnect helpers executes unchanged336 transfer,
  262144 HIRQ and observational trace assertions with exit0; not an
  unmodified-fixture, raw-PUT fixture or native-runtime result.
- state: **UNVALIDATED**.
- not covered/known doubts: **save-state layout break**: target filter and
  private partition size/count/block IDs registered with pointer repair in
  this change; transfer pointer index24 denotes the private reservation.
  Raw flags/latches/output length use their existing registrations. Native
  file compatibility not claimed. Only the existing32-bit write port is
  changed;16-bit writes, native FIFO/backpressure, asynchronous DRDY/EHST
  setup failures, timing and overlapping command/Abort File arbitration
  remain separate. Common cursors can still be disturbed by those overlapping
  commands; private ownership nevertheless survives until DataEnd/reset and
  prevents another PUT from overwriting reservations. Malformed pool-counter
  rollback is defensive, not a hardware policy. This generic PUT path was
  historically named for AB2/OutRun/Fantasy Zone/Dynamite Dux; frozen-game
  runtime acceptance is required and NOT inferred from roundtrip probes.
  No game-specific branches or CPU/sound/video/HIRQ-handler edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0078 | CD-01 | 94da2d00 | UNVALIDATED | Refreshing TOC for Session Info does not create or rewind a host transfer |

### IMPL-0078 — CD-01 — separate TOC preparation from transfer activation

- branch/commit/base: `arena/01a0b897-mame` @ **94da2d00**; base **c5ca25a6**.
- files: `src/mame/sega/saturn_cd_hle.cpp:903-908,3916-3925`;
  `saturn_pending/impl_checks/check_cd_toc_transfer_start.py`.
- contract: only Get TOC command02 starts the TOC word stream and resets its
  cursor. Preparing TOC bytes for Session Info03 must not change the active
  transfer type, cursor or transferred-word accounting. An idle Session Info
  query must not leave a phantom TOC transfer that blocks a following PUT.
  Explicit Get TOC retains its204-word response and DRDY request.
- primary source: ST-162-062094 printed p.77 section8.2.1/functions1.5/1.6
  distinguishes the408-byte TOC data transfer from four-byte session
  information; p.32 section3.4 describes explicit data-transfer setup.
  SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 blob
  37cf17209eb176d6580bd55bf11af1694ae1f328.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:2623-2655,2661-2687`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, activates DT for TOC, not the
  session response. Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:1810-1864`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, likewise separates SetupTOCTransfer
  from Session Info. Upstream MAME398bba74ed7997d29c2316316da230f6d85fda0d
  and local base put the type/cursor assignment in shared cd_readTOC, called
  by both commands. This moves those two assignments, not reference code.
- expected observable: Session Info from idle leaves word type invalid;
  during a TOC/subcode/file stream it does not reset/reclassify its cursor.
  Subsequent ordinary PUT is not refused because of a fabricated TOC stream.
  Explicit Get TOC still starts at byte0 and advertises20416-bit words.
  Exact type/cursor/counts, zero tolerance; no new DRDY from Session Info.
- suggested method: native Session Info before PUT and between word reads
  of an existing response; compare cursor/remaining words and causes; use
  explicit Get TOC as the transfer-start control.
- falsifier: query starts/reclassifies/rewinds a stream, changes its byte
  counter, manufactures DRDY, or Get TOC no longer starts at its first word.
- self-check run (method-level, unvalidated):900 query cursor images, six
  TOC starts and six Session-then-PUT reservations exit0 with ASan/fail-fast
  UBSan. Historicalc5ca25a6 fails cursor/type predicate at generated line1266.
  All22 own CD probes, CD TU warning-enabled syntax and diff checks exit0.
- state: **UNVALIDATED**.
- not covered/known doubts: Session Info metadata, unsupported sessions,
  no-media WAIT policy and legacy drive-status changes are unchanged; absent
  media/nonmatching cursor cases are storage diagnostics. Full host-transfer
  arbitration and native bus/timing remain open. No new state/layout change,
  validator expectation, game-specific code or milestone-status edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0079 | CD-01 | f9eb36c4 | UNVALIDATED | Abort File stops the filesystem producer without cancelling the independent host transfer or hiding retained sectors |

### IMPL-0079 — CD-01 — filesystem-abort/host-transfer separation

- branch/commit/base: `arena/01a0b897-mame` @ **f9eb36c4**; base **1354cfda**.
  Publication currently **BLOCKED(GitHub reconnection for push)**: git push
  returned `could not read Username ... terminal prompts disabled`; user
  asked to reconnect through Arena, no credentials requested. Last published
  tip1354cfda; this production commit and this entry are presently local.
- files: `src/mame/sega/saturn_cd_hle.cpp:2437-2451`;
  `saturn_pending/impl_checks/check_cd_file_abort.py`.
- contract: command75 stops filesystem access and requests the existing drive
  pause, but must not cancel GET/GETDELETE/PUT, zero the host transfer byte
  count, or clear the retained-sector indicator. Preserve buffered data and
  selectors. Publish the existing response before CMOK|EFLS notification,
  preserving already pending causes. This removes0077's specific Abort File
  cursor-cancellation limitation; other overlapping starts remain separate.
- primary source: ST-162-062094 printed p.101 section8.2.8/function8.6:
  Abort File stops directory move, file-information hold and file reading;
  pauses the drive, raises EFLS, does not clear the buffer partition or
  initialize selectors. Host DataEnd is a separate function1.10/p.81 and
  protocol section3.4/p.32. SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73
  blob37cf17209eb176d6580bd55bf11af1694ae1f328.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3910-3916,1070-1078,2733-2778`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e, sets FLS.Abort separately from
  DataEnd/DT. Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:3249-3265`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, instead calls EndTransfer:
  that disagreement is not adopted, following the primary's filesystem
  scope and Mednafen. Upstream MAME398bba74ed7997d29c2316316da230f6d85fda0d
  and local base cancel the32-bit transfer/count and retained-sector flag
  in cmd_abort_file. No reference block imported.
- expected observable: partial PUT -> Abort File -> remaining PUT writes ->
  DataEnd preserves the complete uploaded payload and reports the complete
  host word count; GET and GetDelete similarly continue from their previous
  cursor, with deletion only under their existing transfer completion path.
  No sector loss, selector reset or cursor rewind from Abort File. Exact
  bytes/counts/cause bits, zero tolerance; normal drive-pause latency is not
  specified by this candidate.
- suggested method: native file reading alongside each host-transfer type,
  Abort File before/between/after sector-port accesses, then continuation and
  DataEnd; inspect pool/selector state, remaining bytes, counts and HIRQ.
- falsifier: lost transfer type/cursor/count, inaccessible retained bytes,
  dropped PUT reservation, premature GetDelete removal, selector mutation,
  cleared pending causes, or an IRQ callback seeing the old response.
- self-check run (method-level, unvalidated):393216 status/pending-cause/
  cursor images and18 live raw PUT/GET/GETDELETE continuations over six cuts
  exit0 with ASan/fail-fast UBSan. Actual Abort File/drive-status/transfer
  methods; mock standard report/IRQ/media. Historical1354cfda fails transfer
  preservation at generated line1167. All23 own CD probes, warning-enabled
  CD TU syntax and diff checks exit0; no full build.
- state: **UNVALIDATED**; remote publication blocked as above.
- not covered/known doubts: held-file-information invalidation when stopping
  directory/hold operations, full filesystem state machine, native pause
  scheduling/status timing, other overlapping commands and frozen-game
  runtime acceptance remain open. Reserved cause/cursor patterns are storage
  diagnostics. No new fields/save-layout change, validator asset/expectation,
  HIRQ-handler, CPU/sound/video or milestone-status edits.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0080 | CD-01 | 64ee9883 | UNVALIDATED | An accepted host transfer remains owned through EOF until DataEnd; replacement starts and copy/move return WAIT |

### IMPL-0080 — CD-01 — explicit host-transfer lifetime

- branch/commit/base: `arena/01a0b897-mame` @ **64ee9883**; base **1adec0af**;
  production WIP **4a5294da** included. Publication still
  **BLOCKED(GitHub reconnection for push)** after another authentication
  failure; last published1354cfda. Local commits retained without rewriting.
- files: `src/mame/sega/saturn_cd_hle.h:270,321`;
  `src/mame/sega/saturn_cd_hle.cpp:183,288-290,907-930,1070,1342-1344,
  1931-1947,2050-2068,2104-2143,2231-2234,2356-2358`;
  `saturn_pending/impl_checks/check_cd_host_transfer_lifecycle.py`; own
  declaration/dependency/save adapters, with existing expectations unchanged.
- contract: track accepted TOC/subcode/file-info/GET/GETDELETE/PUT host
  transfers separately from a reader's exhausted interface type. EOF and
  extra port reads/writes do not release ownership. Until DataEnd, another
  host-transfer start or copy/move returns WAIT/CMOK without replacing
  counters, backing data, reservations, selectors or input ownership, and
  without manufacturing DRDY/EHST/ECPY. Preserve pending causes and publish
  the WAIT response before callback. DataEnd releases ownership; hard device
  reset clears it, pending PUT storage, and all host cursors/byte count.
  Session Info and Abort File do not release this independent ownership.
- primary source: ST-162-062094 printed p.32 section3.4 requires DataEnd after
  a transfer request even when no data was transferred; p.80/function1.9 and
  p.81/function1.10 distinguish setup, data movement and explicit termination;
  p.31/section3.3 defines WAIT for commands that cannot currently be accepted.
  SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 blob
  37cf17209eb176d6580bd55bf11af1694ae1f328. Hard reset initializes emulator
  transfer bookkeeping; no new software Init-CD reset policy is inferred.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:2623-2655,2733-2778,2880-2888,3488,3571,
  3632-3634,3817-3823,4107,4161,4295`, blob
  d367dd0c0500ff7b1e2637e748015543b0a3078e: separate DT.Active, WAIT gates,
  explicit DataEnd release and saved active flag. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d and local base use interface
  types that disappear at word EOF; local copy/move/PUT guards therefore
  missed drained word transfers, while other starts could overwrite live
  state. No reference implementation block imported.
- expected observable: read all204 TOC words, then request a sector transfer
  without DataEnd: WAIT, no new reservation/stream. After DataEnd, the same
  ordinary request can start. The same ownership rule applies at zero and
  partial progress and survives save/load after EOF. Reset produces inactive
  interfaces, zero cursors/count and an empty private reservation. Exact
  ownership/state/cause bits and WAIT flag, zero tolerance; no latency claim.
- suggested method: native cross-product of seven transfer kinds and new
  starts/copy/move before, during and after data exhaustion; DataEnd release
  controls, EOF save/load, hard reset during full-pool PUT, Session Info and
  Abort File coexistence. Capture response/cause publication and backing bytes.
- falsifier: replacement silently starts/rewinds/allocates, EOF releases the
  interface without DataEnd, a WAIT modifies data/ownership or generates a
  new operation-complete cause, DataEnd leaves it busy, or restore/reset loses
  the active latch or retains stale transfer counters/reservations.
- self-check run (method-level, unvalidated):567 refusal images,21 DataEnd
  release controls, four registered EOF ownership replays, seven query/Abort
  File controls and96 hard-reset/pending-PUT/cursor images exit0 with
  ASan/fail-fast UBSan. Historical1adec0af fails active-start predicate at
  generated line1581. Missing active-save, enum-only guard, missing active
  reset, missing cursor reset, missing End release and enum-only copy guard
  mutants fail at lines1632/1622/251/252/1626/1622. All24 own CD probes,
  warning-enabled CD TU syntax and diff checks exit0. The first aggregate
  stopped on duplicate mock cr_standard_return declarations inherited by two
  own file probes; declaration deduplication fixed compilation without any
  expectation changes, then the complete aggregate exited0.
  Original validator transfer fixture remains a compile failure, now also
  lacking m_host_transfer_active. A temporary declaration/dependency adapter
  executes unchanged336 transfer,262144 HIRQ and trace assertions with exit0;
  no validator file/expectation edits or unmodified-fixture claim.
- state: **UNVALIDATED**; local publication blocked as above.
- not covered/known doubts: **save-state layout break**: new active flag is
  registered in the same production change. Old-save compatibility not
  claimed. Existing WAIT/standard-report formatting is retained; other status
  bits/report words remain unqualified. Illegal sector ranges, invalid
  subcode/file-info operands, FLS-busy rules, native FIFO/prefetch/DRQ timing,
  software Init-CD cancellation and frozen-game runtime acceptance remain
  separate. In particular, do not reinterpret the frozen X-Men Init-CD
  exceptions as a reset contract; **BLOCKED(command04 active-transfer/pool/
  selector reset trace compatible with those accepted sequences)** for that
  reset policy. No validator expectations, game-specific branches, CPU,
  sound, video or milestone-status changes.

---

| ID | parent | commit | state | one-line contract |
|----|--------|--------|-------|-------------------|
| IMPL-0081 | CD-01 | d329912d | UNVALIDATED | Actual-size calculation waits for an available complete range and no host PUT, retaining its previous held result on refusal |

### IMPL-0081 — CD-01 — actual-size range and held-result semantics

- branch/commit/base: `arena/01a0b897-mame` @ **d329912d**; base **9af24b6f**.
  Publication remains **BLOCKED(GitHub reconnection for push)**; last published
  1354cfda. An incremental local Git bundle under
  `/home/user/mame-local-backup/unpublished.bundle` preserves the unpublished
  branch history outside the repository; no bundle/artifact is committed.
- files: `src/mame/sega/saturn_cd_hle.cpp` cmd_calculate_actual_data_size;
  `saturn_pending/impl_checks/check_cd_actual_size_range.py`.
- contract: resolve sector-position END and sector-count END independently
  against the partition's logical count. Empty, zero-count, unavailable or
  overlong ranges return WAIT instead of clamping or counting stale unused
  slots. Active PUT also returns WAIT, including after its last write until
  DataEnd; an existing GET does not itself block calculation. Invalid
  partition byte returns REJECT. Refusal preserves the previous held result
  and pending causes, with CMOK but no new ESEL. Accumulate a valid complete
  range's current host-view sizes in16-bit words, then replace the held result
  atomically and complete with CMOK|ESEL after populating the response.
  Malformed pool IDs/pointers/free records are guarded defensively rather
  than being dereferenced or publishing a partial sum.
- primary source: ST-162-062094 printed p.93 section8.2.6/functions6.3/6.4:
  designated range/independent END sentinels, host word count and held result;
  p.95/function7.1 connects fetching length to this calculation; p.31
  section3.3 defines WAIT/nonacceptance versus malformed-command REJECT;
  p.30 Table3.2 assigns completed calculation to ESEL. SDK
  0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 blob
  37cf17209eb176d6580bd55bf11af1694ae1f328. The p.93 partition-output
  disconnection remark is NOT implemented/qualified by this range candidate.
- cross-checks/provenance: Mednafen f0ee9d595db68ad5247ba5ac6a8367fdced9c3fc,
  `src/ss/cdb.cpp:3276-3338`, blobd367dd0c0500ff7b1e2637e748015543b0a3078e,
  resolves the range, waits during writing or insufficient range, and replaces
  CalcedActualSize only on success. Its guessed240-clock delay is not used.
  Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/cdblock/cdblock.cpp:2673-2743`, blob
  e8fedadb2d7374db35667bd064bb47fdc14b41a8, instead rejects/clamps ranges and
  raises ESEL on rejected calculations (and the result query); those
  disagreements are not adopted. Upstream MAME
  398bba74ed7997d29c2316316da230f6d85fda0d CD method1492-1514 and local base
  clear the result early; the local generic helper only bounds the physical
  array, not the available logical range. No reference block imported.
- expected observable: with three buffered sectors, offset2/count2 waits and
  preserves the old result rather than counting one sector; FFFF/FFFF selects
  exactly the last sector. A partial/fully written but unterminated PUT waits
  without ESEL; after DataEnd the same available range calculates normally.
  Get Actual Data Size still reads the prior result after any failed request.
  Exact words/held value/WAIT flag/cause bits, zero tolerance; no latency claim.
- suggested method: native mixed Mode1/Form1/Form2 partitions at all fetching
  lengths, both sentinels, empty and partially available ranges, repeated
  result queries, PUT before/at EOF/after DataEnd, and GET coexistence.
- falsifier: out-of-range request silently succeeds/truncates, result changes
  on refusal, invalid selector manufactures ESEL, a partial sum becomes
  visible, active PUT is accepted, ordinary GET alone causes WAIT, or
  successful calculation disagrees with the fresh-GET view's word count.
- self-check run (method-level, unvalidated):489216 range/END/view/pending-cause
  images,696 invalid-selector controls and nine ownership/PUT-WAIT/GET controls
  exit0 with ASan/fail-fast UBSan. Historical9af24b6f fails held-result/status
  predicate at generated line1169. Partial-result, missing PUT-WAIT,
  overbroad all-host-WAIT and rejected-ESEL mutants fail at generated
  lines1191/1199/1202/1182. All25 own CD probes, warning-enabled CD TU syntax
  and diff checks exit0; no full build.
- state: **UNVALIDATED**; local publication blocked as above.
- not covered/known doubts: partition-output/MPEG connection tracking and
  disconnection, asynchronous calculation latency, full WAIT report/status
  formatting, FIFO-prefetched GET counts and frozen-game native acceptance
  remain separate. Stale unused entries and malformed ownership are storage
  diagnostics, not legal hardware configurations. Existing calcsize save
  registration retained; no new field/layout break. Validator assets and
  expectations, HIRQ handlers, frozen CPU/sound/video paths and milestone
  status untouched. Previously reported validator mock compilation gaps
  remain; this entry does not claim an unmodified-fixture result.

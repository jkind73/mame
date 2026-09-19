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

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

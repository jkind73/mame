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

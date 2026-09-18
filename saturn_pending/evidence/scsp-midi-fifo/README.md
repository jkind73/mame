# SND-03 SCSP MIDI FIFO depth, status flags and reset — method-qualified, native pending

## What changed

`src/devices/sound/scsp.{h,cpp}` at WIP `ea928158`:

1. Both MIDI buffers are **4 bytes**, not a 32-slot ring. Occupancy
   (`m_MidiCount`, `m_MidiOutCount`) is tracked separately from the read/write
   pointers, so a full FIFO can no longer wrap and report itself empty.
2. Register `0x404[12:8]` now reports **live status**: bit8 MIEMP, bit9 MIFULL,
   bit10 MIOVF, bit11 MOEMP, bit12 MOFULL. Previously the high byte returned
   whatever stale bits happened to sit in the register file.
3. `MOBUF` (`0x406`) **reads as 0** — write-only bits read 0 per p.35.
4. An output write to a **full FIFO is rejected** (no overwrite, no wrap).
5. Input arriving at a full FIFO **latches MIOVF** and keeps the queued bytes.
   The latch retires when a consuming read leaves the FIFO empty.
6. `device_reset` clears both FIFOs, their pointers/occupancy, the overflow
   latch and the serial shift registers. Previously reset left all of it dirty.
7. A queued output byte leaves the FIFO when its **frame completes**
   (`tra_complete`), which keeps the output-empty request at the timing already
   qualified natively at `2f54b074`.

Unchanged: the `2f54b074` byte-lane/debugger/write-merge semantics, the
`53f73010` DMA self-target policy, IRQ derivation and both CPUs' interrupt
banks.

## Primary source

ST-077-R2-052594, SDK pin `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`, PDF blob
`9383eb13fe65c807e3ec48f32e284b9999cd71b8` (cached `scsp.pdf`/`scsp.txt`):

- Figure 4.59 (printed p.89 / PDF 102): MIDI-IN and MIDI-OUT are each **four
  1-byte buffers** feeding a serial/parallel converter.
- Printed p.90 / PDF 103: MIOVF is set when data arrives at a completely full
  MIDI-IN buffer; MIFULL when all 4 bytes are occupied; MIEMP when the input
  FIFO is empty; the input interrupt is requested when MIEMP goes 1→0 on
  received data and released when reading empties the buffer.
- Printed p.91 / PDF 104: MOFULL when all 4 output bytes are occupied; MOEMP
  when all data in the MIDI-OUT buffer "has been sent out", which is also when
  the output-empty interrupt may be raised. MOBUF is write-only.
- Figure 4.3 (printed p.28 / PDF 40) gives the bit grid. Text extraction loses
  the drawing, so the columns were recovered from the PDF text positions: the
  low-byte `MIBUF[7:0]` box centre aligns with `MOBUF[7:0]`'s, which fixes the
  cell pitch and places **IE=bit8, IF=bit9, IO=bit10, OE=bit11, OF=bit12**.
- Printed p.35 / PDF 47: reading a write-only register/bit returns 0B.

## Cross-checks (inspection only, no code copied)

- Beetle `1382b85dcad2e98ef9a67426a775ba548eaf0c68`, `mednafen/ss/scsp.inc`
  blob `79ac3c31102f740b0faf432de696062f25e90485`: 4-entry input/output FIFOs,
  `MIDI.Flags << 8` with `INPUT_EMPTY=0x01, INPUT_FULL=0x02, INPUT_OFLOW=0x04,
  OUTPUT_EMPTY=0x08, OUTPUT_FULL=0x10` — the same bit positions recovered from
  Figure 4.3; output writes discarded when `OutputCount == 4`; overflow cleared
  on read (marked `TODO: Test`).
- Ymir `6d779960127ced72087a418c1daefc637d0aaa80`, `scsp.cpp` blob
  `b87bfd7278b60da1e7f546d2e625825e2ae6c4dc`: models host-side MIDI queues
  (1024-byte buffers, `m_midiInputOverflow`), **not** the SCSP register FIFO or
  its status bits.
- MiSTer `a95b085038ace57fa621558d60a7adc7a3c53f78`: `rtl/Saturn/SCSP/SCSP.sv`
  blob `402dcb6eedca98547c34a799fea3dc56eddbca5a` and the whole tree contain no
  MIDI register logic at all.

So the primary manual plus Beetle agree on depth, bit positions and full-FIFO
rejection. Beetle is the only reference for the overflow-clear edge, and it
flags that behaviour as untested.

## Deliberate divergences and unproven points

- **Pop edge.** Beetle removes an output byte when its frame *starts*; this
  implementation removes it when the frame *completes*, matching the manual's
  "has been sent out" and the previously qualified output-empty interrupt
  timing. The native drain window below rejects the frame-start edge. The exact
  silicon edge is not documented; this is a reasoned choice, not proof.
- **MIOVF clear.** Chosen: retire when a consuming read empties the input FIFO
  (coincides with the documented MIEMP/interrupt-release edge, so it needs no
  extra undocumented rule). Beetle clears on the first read. Neither is
  primary-documented.
- **Fifth input byte.** Kept out of the FIFO (queued bytes preserved). Whether
  silicon discards or replaces is not documented.
- **No MIDI wiring.** The Saturn/ST-V drivers never bind `midi_out_cb` and never
  drive `midi_in`, so the input FIFO cannot be filled from a guest or from Lua.
  (`model2`/`model3` do wire `midi_out_cb` to an i8251; they inherit the same
  4-byte depth.) Input depth/overflow therefore stays **method-level** evidence.
- RX pin sampling, wire-level output bytes and 31.25 kbps bit accuracy beyond
  the frame window remain unqualified.

## Tests

`regtests/saturn/test_scsp_irq_ports.py` executes the real `read`, `write`,
`r16`, `w16`, `UpdateReg`, `UpdateRegR`, `CheckPendingIRQ`,
`MainCheckPendingIRQ`, `update_main_irq`, `ResetInterrupts`, `exec_dma`,
`tra_callback`, `tra_complete`, `rcv_complete` and `reset_midi` bodies under
UBSan. The serial engine is a stand-in: a frame completes only when the test
says so.

- **902** MIDI FIFO/status/lane/drain/reset cases: absolute golden status words
  (`0x0900`, `0x0800`, `0x0a00`, `0x0e00`, `0x0100`, `0x1100`, `0x0c00`…) that
  pin every bit position, a full input×output occupancy×overflow matrix, every
  pointer position/occupancy/lane/debugger combination, input-write rejection on
  the public and DMA-facing paths including the register file itself, output
  full-FIFO and non-data-lane rejection, FIFO drain order through the actual
  `tra_complete`, bit emission through the actual `tra_callback` (which must not
  change occupancy), input overflow depth, and reset clearing.
- **80** DMA cases still pass, now including a register→mem transfer whose DRGA
  walks from MIBUF to write-only MOBUF, gated and ungated drains, and an empty
  FIFO read that must not pop.
- **851968 + 114688** acknowledgement/mask/stale-command and pending-port cases
  still pass.
- `regtests/saturn/test_scsp_reset.py` executes the real `device_reset` and
  `reset_midi`: 24 cases now assert that a dirty MIDI interface (both FIFOs,
  occupancy, overflow latch, shift register) is cleared. `test_scsp_phase.py`
  (49152 cases) and `test_sound_boot.py` (64 cases) models were updated for the
  new occupancy field.
- **26 compiled mutants rejected** by behavioural assertions: `midi-depth-wrap`,
  `midi-status-bits` (restores the exact stale-register status), `midi-mobuf-readable`,
  `midi-in-depth`, `midi-overflow-latch`, `midi-overflow-clear`, `midi-out-count`,
  `midi-early-pop` (Beetle's frame-start pop), `midi-write-input`, plus the 17
  previously archived IRQ/MIDI/DMA selectors and `MUTATE_SCSP_MIDI_RESET`.
- Old-source override `SCSP_IRQ_SOURCE=<53f73010 scsp.cpp>` fails a clean
  assertion (`before.log`); the harness supplies an empty `reset_midi` for it
  because the pre-FIFO source had no MIDI reset at all.
- Full-translation-unit `g++ -fsyntax-only` on `scsp.cpp` passes.
- 14 result-parser controls for the new native fixture
  (`test_scsp_midi_fifo_runner.py`), no emulator execution.

## Native negative control (old binary, already run)

`saturn_pending/test_scsp_midi_fifo_runtime.py` uses only guest-visible
registers and virtual time: no private state, no injected MIDI wire. 24 cases =
2 CPU buses (SH-2 `0x05b00000`, 68000 `0x100000`) × 3 access widths × 4 values.
Each case checks the idle golden status, MOBUF reading zero, both interrupt
banks, single-byte queue/drain, four-byte fill, fifth-byte rejection and the
drain window; non-data-lane writes must queue nothing.

Polling is 50 µs. One 10-bit frame at 31.25 kbps is 320 µs, so a single byte
drains in window [250, 500] µs and four bytes in [1150, 1500] µs. Five accepted
bytes would drain at ~1600 µs and a frame-start pop edge at ~960 µs, so both
wrong behaviours fall outside the window.

Run against the qualified **old** binary `53f73010` (SHA256
`b1cc2e68c1325bae0a1f5c4bb9220964f118e7e16c0e35ca0efa80c6018f13d9`):
**0 of 24 cases pass, 185 failed observations** (`before-native.log`) —
24 `idle_status` (got 0, want 0x0900), 23 `idle_mobuf_zero` (write-back of the
last written byte), 16 each of `one_status`, `one_drained_status`, `full_status`,
`full_drained_status`, `fifth_status`, `fifth_mobuf_zero`, **16
`four_frame_window`** (the depth/timing discriminator), 8 each of the
non-data-lane status checks, and 2 idle pending observations.

## Pending

Full 71-script local/CI regression, build `35405593717`, artifact export and the
complete native consumer — including 24 new FIFO cases × 4 profiles and the
existing 1536 × 4 MIDI output cases — have not yet been run against this source.
Nothing here claims waveform, gameplay, whole-SND-parent or working-driver
acceptance, and no save-state compatibility with pre-`ea928158` states is
implied (the MIDI arrays changed size).

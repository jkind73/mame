# Sound-CPU integration: reset, shared RAM/registers, SCU DMA, SCSP interrupt (SND-01)

Fixture: `saturn_pending/test_scsp_integration_runtime.py`, run against the CI
build of `7bebd197` (binary sha256 `9a7d21c9...513cbd4`, the same binary as the
FM/PCM/MVOL/FX evidence) on four profiles: saturnjp interpreter, saturnjp DRC,
saturneu (PAL) DRC and stvbios (ST-V) DRC. All four report `SCSP_INT PASS
cases=84` with identical numbers (`masked counter=5 scipd=05c0`, `ist
2804 -> 3804`); raw transcripts in `*/runtime.log`, commands and hashes in
`*/invocation.json`, one-line summaries in `summary.txt`.

This is the integration half of SND-01: the sound 68000 as a *bus master and
interrupt target*, not the SCSP register semantics (those are the PCM/FM/MVOL/FX
gates) and not the SCU's own DMA model (that is the SCU gate).

## Qualified (measured on the emulator, not assumed)

| group | claim | measurement |
|---|---|---|
| A | sound RAM is one memory behind both CPUs | byte/word/long written by the SH-2 reads back identically through the 68000 window, and vice versa, at 0x05a04xxx; the byte image of a long word agrees in both directions (0x11/0x22/0x33/0x44 and 0x55/0x66/0x77/0x88) |
| B | SCSP registers are one register file behind both CPUs | slot 3 pitch and mixer words written through either window read back through the other; MVOL written at SH-2 `0x05b00400` reads back at 68000 `0x100400` |
| C | SCU DMA moves data between the two buses | work RAM H -> sound RAM 64 bytes: idle status, all 16 longs correct through the 68000 window *and* the SH-2 window; sound RAM -> work RAM H (the B-bus read path) all 16 longs correct; a same-bus transfer (sound RAM -> sound RAM) sets IST DMAILL and leaves the destination untouched |
| D | sound-CPU reset and SCSP interrupt delivery | SNDOFF/PDR2 holds the 68000 in reset (its program never starts, counter stays 0); release starts it at the reset vector; the free-running SCSP timer A request is delivered as level 6 through the 68000's autovector 30 (vector at 0x78); the handler is entered exactly five times and then masks level 6 in the *stacked* SR, after which delivery stops while SCIPD keeps the request pending |

## Method notes that matter

* **Common registers live at byte offset 0x400.** Slots occupy 0x000-0x3ff (32
  x 0x20 bytes); SCIEB/SCIPD/SCIRE/SCILV0-2 are 0x41e/0x420/0x422/0x424-0x429.
  Reading and writing 0x1e/0x20/0x22 instead lands in slot 0/1: it reads back
  self-consistently but never arms a timer and never acknowledges anything. The
  committed timer gate already used 0x05b00400; this fixture originally did not,
  and the symptom was a sound CPU that ran its program but never took an
  interrupt.
* **The 68000 state `PC` item cannot be written by the environment.** Its import
  sets `m_ipc = m_pc` and then `m_pc = m_ipc + 2`, so `state["PC"].value = x`
  advances the PC by two instead of setting it. Fixtures that "park" the sound
  CPU this way are not actually stopping it. This fixture stops it through the
  board's real reset path instead (SMPC SNDOFF on Saturn, SMPC PDR2 bit 4 on
  ST-V, whose `sound_reset_handler` is deliberately unwired in `stv.cpp`).
* **Level-triggered delivery needs a transition.** `scsp_irq` only re-drives
  the 68000's IPL input when the SCSP's computed level changes; the timer
  request is what creates that transition here, so the fixture never depends on
  an interrupt being sampled out of a steady line.
* **The handler's mask has to be written to the stacked SR.** `move.w
  #$2700,(2,sp)` (an earlier draft) corrupts the stacked PC; `move.w
  #$2700,(sp)` is the value RTE restores. The five-entry count is the
  discriminator: an unacknowledged (level-triggered) request races past five, a
  mask that RTE discards keeps counting.

## Failure modes exercised while building this gate (not claims about the emulator)

These are the transcripts the checks fired on; they are kept because they show
the checks discriminate rather than pass vacuously:

* handler branch `0x6600 0x0004` (BNE.S with displacement 0 followed by an
  illegal word) - counter froze at 2, SR stuck at 0x2610, PC in unmapped space;
  the gate's five-entry check failed.
* mask written to `(2,sp)` - delivery stopped after one entry with the request
  pending; the gate's five-entry check failed.
* SCIPD/SCIEB read at the wrong page - the request bit never observed, so both
  the delivery and the pending checks failed.

## Not covered here

* SCSP EXTS0/1 (the CD digital input) - needs the CD block (stage 10).
* CD-DA mixing and the SH-1/CD interface - SND-02/04, stage 10.
* Real-software audio: the promotion gate for SND asked for the sound stack to
  be exercised by a real program, which is the CD/BIOs title runs, not this
  fixture.

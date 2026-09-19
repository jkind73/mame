# SCSP / SCU / sound-CPU integration (SND-01)

`saturn_pending/test_scsp_snd01_runtime.py` measures the sound subsystem's
integration: the same sound RAM and the same SCSP registers through both CPU
windows, the SCU's DMA path into and out of sound RAM, and the SCSP's interrupt
as seen by a running sound 68000.  All four profiles (saturnjp interpreter,
saturnjp DRC, saturneu DRC, stvbios DRC) pass `SCSP_INT PASS cases=42` on binary
`9a7d21c9...`; the per-profile logs, the exact Lua and the invocation are in the
directories next to this file.

## What is asserted

| group | measurement | numbers |
| --- | --- | --- |
| sound RAM lanes | byte, word and long writes from each side, read back through the other (SH-2 window `0x05a00000`, 68000 window `0x000000`), plus the byte image of a long word | 24 cases, identical values and big endian byte images both ways |
| register lanes | slot 3 pitch (`0x10`) and mixer (`0x16`) written from each side and read through the other, and the common page checked the same way (`0x426` SCILV1) | 6 cases; the common page sits at the same byte offsets in both windows |
| SCU DMA | level 0 copy work RAM H (`0x06020000`) -> sound RAM (`0x05a01000`) and back, destination verified through **both** windows, DMA status back to idle; control: a same-bus transfer (sound RAM -> sound RAM) | 3 cases, 16/16 words each way, status `00000000`; the control sets `IST` bit 12 (`2807` -> `3807`) and leaves the destination untouched (16/16) |
| sound CPU | SNDOFF holds the 68000 (PC frozen across 20 ms, no RAM writes), the fixture's program is then uploaded and SNDON starts it: a masked delay loop runs 4096 iterations, the handler counter stays 0 while the mask is closed, and the SCSP request (SCIPD bit 6) is pending | `liveness=4096`, `masked_counter=0`, level 6 from `SCILV=0000/0040/0040` |

## Open finding (recorded, not asserted as a pass)

With the mask open the request does not reach the guest handler: the CPU is seen
outside the uploaded program (`pc_open=ffffba90`, and in the BIOS sound program's
region at `0x1604`/`0x1002`) and the handler counter never advances, while every
precondition measures as written:

* the request is pending (`scipd=0580`, bit 6) and enabled (`scieb=0040`);
* the level is 6 (`scilv=0000/0040/0040`), and the fixture's handler is installed
  in the level 6 autovector slot (`SCSP_INT vectors ... 6:00007000 7:00007300`,
  `v4=00007100`; the BIOS owns levels 1-5 in the same table);
* SNDOFF/SNDON do hold and start the CPU (PC frozen across 20 ms while held, the
  program runs after release);
* the delay loop completes with the mask closed (`liveness=4096`).

The same run also recorded that the *first* interrupt after a reset release is
taken in a half-initialised context: with the SCSP armed while the CPU is held
and the program opening the mask on its first instruction, the handler **did**
run (the handler counter advanced) but `rte` returned into the vector table,
which is why the fixture now runs a masked delay first.  That is a real
integration defect (interrupts are edge-sampled: an IRQ level change is only
re-evaluated when the level changes or software touches SR -- see the MAME 68000
notes), and the numbers above are what a fix has to move.

## Method notes

* **`0x100420` is SCIPD, not SCIRE.** A *word* write of `0x0040` there is a
  write to a read-only register and does nothing; the acknowledgement register is
  `0x100422` from the 68000 and `0x05b00422` from the SH-2.  A long write at
  `0x100420` reaches `0x422` as well, which is how the first version of the sound
  program "worked" while its word write did not: the request stayed asserted and
  the CPU stormed in the handler.
* **SCU DMA addresses are bytewise and the add fields are not what they look
  like.** `DxAD` bit 8 sets the *source* step to a dword (`src_add = 4`), the low
  three bits select the *destination* step as `1 << n` with `1 << 0` remapped to
  0 ("no increment"), so a sequential block copy is `0x00000101`, not `0`: with
  `0` the transfer writes every word to the same address (measured: one word
  changed, the rest untouched).  `DxAD` is write-only, reads return the last
  written register image.
* **The sound 68000 vectors live at 0 (`VBR = 0`)** and the BIOS owns levels 1-5;
  the fixture only replaces levels 6 and 7 so a stray request cannot be mistaken
  for its own.
* **Holding the sound CPU is SMPC SNDOFF (07H)** on Saturn and **SMPC PDR2 bit 4**
  on ST-V; the ST-V profile passes through that path.

## Limits

Not claimed: SCU DMA *timing* (the fixture waits for completion), the SCSP's own
DMA (SND-03), MIDI, CD audio, and the sound CPU's interrupt latency.  The open
finding above is the reason the end-to-end interrupt claim is not made.

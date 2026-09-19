# SCSP / SCU / sound-CPU integration (SND-01)

`saturn_pending/test_scsp_snd01_runtime.py` measures the sound subsystem's
integration: the same sound RAM and the same SCSP registers through both CPU
windows, the SCU's DMA path into and out of sound RAM, and the SCSP's interrupt
as seen by a running sound 68000.  All four profiles (saturnjp interpreter,
saturnjp DRC, saturneu DRC, stvbios DRC) pass `SCSP_INT PASS cases=49` on binary
`bb872c6215...` (the ping-pong-fix build from CI run 35431997823, source
`5bd7f203ebf`); the per-profile logs, the exact Lua and the invocation are in the
directories next to this file.

## What is asserted

| group | measurement | numbers |
| --- | --- | --- |
| sound RAM lanes | byte, word and long writes from each side, read back through the other (SH-2 window `0x05a00000`, 68000 window `0x000000`), plus the byte image of a long word | 24 cases, identical values and big endian byte images both ways |
| register lanes | slot 3 pitch (`0x10`) and mixer (`0x16`) written from each side and read through the other, and the common page checked the same way (`0x426` SCILV1) | 6 cases; the common page sits at the same byte offsets in both windows |
| SCU DMA | level 0 copy work RAM H (`0x06020000`) -> sound RAM (`0x05a01000`) and back, destination verified through **both** windows, DMA status back to idle; control: a same-bus transfer (sound RAM -> sound RAM) | 3 cases, 16/16 words each way, status `00000000`; the control sets `IST` bit 12 (`2807` -> `3807`) and leaves the destination untouched (16/16) |
| sound CPU | SNDOFF holds the 68000 (PC frozen across 20 ms, no RAM writes), the fixture's program is then uploaded and SNDON starts it: a masked delay loop runs 4096 iterations, the handler counter stays 0 while the mask is closed, and the SCSP request (SCIPD bit 6) is pending | `liveness=4096`, `masked_counter=0`, level 6 from `SCILV=0000/0040/0040` |
| interrupt delivery | the level 6 request reaches the guest handler once the mask opens, is acknowledged by the guest through SCIRE, and the count advances with the timer | 9 -> 111 -> 215 handler entries, level 7 entries 0, `ssp_after=0007fff0`, `unmasked=1` |

## Interrupt delivery (asserted)

The end-to-end chain is measured, not inferred: the SCSP request is pending and
enabled at level 6 with the sound CPU's mask closed and the handler counter stays
0; SNDON starts the uploaded program, which runs 4096 masked delay iterations and
then opens the mask.  From that point the guest handler runs continuously as the
timer keeps expiring:

| quantity | value (identical on all four profiles) |
| --- | --- |
| handler entries at the first sample after the mask opens | 9 |
| entries 300 ms later | 111 |
| entries 300 ms after the acknowledgement window | 215 |
| entries while the mask was closed | 0 |
| level 7 handler entries | 0 (the request is level 6, not 7) |
| supervisor stack after 215 exceptions | `0007fff0` (the initial SSP, unchanged) |
| program counter at the end | `00007120` (inside the uploaded program) |
| `unmasked` flag | 1 |

So CSIP -> IPL 6 -> autovector 30 -> the guest handler -> SCIRE -> back is
measured through the CPU's own exception path, with the mask proven to hold the
request off and the level proven not to be 7.  This closes the interrupt half of
SND-01 that the previous revision of this evidence recorded as an open finding.

## Tooling trap that produced the earlier "open finding"

The previous revision reported that the request never reached the guest handler
(`pc_open=ffffba90`, counter always 0).  Both symptoms were **fixture bugs with
one cause**: `COUNTER` and `UNMASKED` were never declared as Lua locals, and a
nil address argument to a debugger write lands on address **0** instead of
raising an error.

* `ssp:write_u32(COUNTER, 0)` therefore wrote zero to address 0 - the initial-SSP
  vector - so the CPU came out of reset with `SP = 0`, pushed exception frames
  below address zero and ended up executing garbage (`pc=ffffba90`, seen at
  `0x1604`/`0x1002` earlier because the BIOS's own low vectors sit there).
* `read_counter()` (`ssp:read_u32(COUNTER)`) read address 0 as well, so the
  handler's real increments were invisible: the run looked exactly like "the
  request is never delivered" while the handler was in fact running.

The fixture now declares every value it uses, re-checks the initial SSP before
releasing the reset (`initial_ssp_intact`), asserts the handler count advances,
and asserts the stack is restored.  The matrix that pinned the trap down is worth
recording because the failure is silent:

```
write_u32(0x7200, 0)          -> vector 0 unchanged
write_u32(0x7200, 0x12345678) -> vector 0 unchanged
write_u16(0x7200, 0)          -> vector 0 unchanged
write_u32(NIL, 0)             -> vector 0 = 0        <-- silent
```

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

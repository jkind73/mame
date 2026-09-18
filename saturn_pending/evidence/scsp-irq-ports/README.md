# SND-03 SCSP interrupt command ports — NATIVE QUALIFIED

The write decoder applied MCIPD's bit5-only pending-register rule to MCIRE
(address42e rather than42c). Consequently main-CPU DMA/timer/output/sample
requests could not be acknowledged there. It also accumulated old CPU-clear
commands. Both acknowledgement ports reused stale opposite-byte clear bits
when the public masked-write wrapper merged its value with the previous read.

Production corrects the pending-port address and restricts pending writes to
active bit5. SCIRE/MCIRE now consume only val & mem_mask for this command;
old inactive lanes cannot acknowledge new requests. No timer-rate, reassertion,
DMA scheduling, MIDI FIFO, interrupt priority or SCU delivery change is made.

Primary: Sega ST-077-R2-052594 pp.96–97 (PDF109–110), SDK
0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73, PDF blob
9383eb13fe65c807e3ec48f32e284b9999cd71b8. SCIPD/MCIPD are read-only except
bit5 write-one request; SCIRE/MCIRE clear selected pending requests when one
is written. Cross-check: pinned Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68,
scsp.inc blob79ac3c31102f740b0faf432de696062f25e90485,
register cases10/11/16/17 mask commands by bus lanes and distinguish pending
from reset ports. No external implementation copied.

Actual production read/write/w16/r16/UpdateReg/UpdateRegR and IRQ methods run
under UBSan:851968 acknowledgement cases and114688 pending-port cases PASS.
All2048 pending combinations, all11 single-bit/zero/all clear commands, four
masks (including no lanes), four stale command patterns and both domains are
covered. Pending writes preserve every non-CPU source. The actual IRQ methods
check both asserted/deasserted callback states after each command. Timer/stream/serial
engines are stand-ins here; expired-timer reassertion stays in existing tests.
Seven compiled mutants fail behavioral assertions: wrong decode, stale lanes,
sticky commands, clear-zero, pending clobber/unmasked writes and missing main
IRQ re-drive. Full-TU syntax and14 parser controls pass. Default suite now71.

432 native programs use both SH-2 and68000 register mappings, both domains,
word/high-byte/low-byte writes, four command histories and nine acknowledgements.
Each case seeds real timer A/B/C expiry, SCSP DMA completion, serial-output-empty,
CPU requests and sample-tick requests, then checks both pending banks against
entry state. Timer counters have moved pastFF before acknowledging. No private
IRQ injection or arbitrary sleeps as an oracle: source setup is asserted.
Qualified35f5d58b (binary SHA256
008d13e4c47b6445359d7696de1406e88af2ad5ce8573a501ec9b59ee218521d)
passes161/fails271 of432 cases. The original prototype without MIDI seeding is
not the archived fixture. Raw old-negative output is included.

Full71-script local/CI and build35398923424 PASS for production6aa9e3d8.
Build35398923424/export35399526933 and the complete native consumer PASS:
1728 IRQ cases across JP/interpreter, JP/DRC, PAL/DRC and ST-V/DRC; actual
pending-IRQ file replay; all previous3036 SCSP DSP programs and effect/address
file replay; all preceding runtime/save/BIOS and provenance gates. Binary SHA256
d16947d2e62687a2ed166b426c39f461bae7d38e7b395c67ba3c560227b2032a.
Evidence: `../6aa9e3d8-live/`; consumer revision recorded separately. This does not close the whole sound interrupt/timing parent,
SCU arbitration, external IRQ pins, waveform or game acceptance. No flags change.

Actual file replay is now required too: save pending DMA/CPU/sample requests
and a stale high-byte clear command, issue low-byte acknowledgements, poison
pending state, load, and repeat the command at exactly the restored timestamp.
Both pending banks must restore exactly and both commands must leave unrelated
requests intact. Old35f5d58b preserves/restores its bad result but fails five
expected observations (two original acknowledgements, main DMA poisoning and
two replayed acknowledgements).14 save-parser controls pass. Rebuilt native
replay PASS, including both pending banks and both independent commands. This is not sound waveform continuity or a timed DMA save.

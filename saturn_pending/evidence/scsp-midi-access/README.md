# SND-01/SND-03 SCSP MIDI register access — output native-qualified; input method-qualified

MIDI data is in the low byte. Propagate read masks through read/r16/UpdateRegR;
only data-byte reads with side effects enabled may advance input and release
its IRQ. The public write merge peeks with a zero mask. Input/status writes,
including internal DMA writes, are ignored. Output writes start/enqueue a byte
and clear output-empty IRQs only when the low byte is accessed.

Primary ST-077-R2-052594 pp.90–92 (PDF103–105), SDK
0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73, PDF blob
9383eb13fe65c807e3ec48f32e284b9999cd71b8: MIBUF/status are read-only,
reading consumes input and releases the request when empty, and MOBUF[7:0]
is the write-only output data. Byte-lane cross-check: pinned Beetle
1382b85dcad2e98ef9a67426a775ba548eaf0c68, scsp.inc blob
79ac3c31102f740b0faf432de696062f25e90485, common register cases02/03
read input/write output only for the low lane. No external source copied.
Debugger non-consumption follows MAME's side-effects-disabled convention.

2176 new complete-method cases check every existing FIFO pointer position,
empty/single/multiple entries, word/low/high/no lanes, debugger peeks, input
writes through both public and DMA-facing methods, and busy/idle output.
FIFO bytes/indices, transmission starts and both IRQ banks/callback levels
are checked. The previous966656 IRQ-port cases pass too. Twelve compiled
mutants fail assertions, including five MIDI-specific controls.14 parser
controls and full-TU syntax pass. Old-source controls add unused mask parameters
for API compatibility only; the old method bodies remain unchanged and fail.

Native output fixture:1536 cases per profile, both SH-2 and68000 maps,
all256 byte values and word/high/low writes. A real transmission seeds
output-empty; reads check sound/main IRQ clearing and real serial completion.
Qualified6aa9e3d8 (binary d16947d2e62687a2ed166b426c39f461bae7d38e7b395c67ba3c560227b2032a)
passes1024/fails512 cases; each bad high-byte write fails both IRQ observations
(1024 failure rows). Data-bearing writes and all completion controls pass.
Full71-script local/CI and build35400396608 PASS for source2f54b074.
Build35400396608/export35401015382 and the complete native consumer PASS:
6144 output-byte/serial-completion cases across JP/interpreter, JP/DRC,
PAL/DRC and ST-V/DRC; all previous1728 IRQ and3036 DSP cases, actual IRQ
and effect/read/address file replay, all preceding runtime/save/BIOS and
source/binary/BIOS provenance gates. Binary SHA256
701c7b775cb271c68e6b5900acd8622073be0395418514fc51225a62f9d35930.
Evidence: `../2f54b074-live/`; consumer revision recorded separately.

Limits: Saturn has no wired external MIDI connector in this configuration.
RX pin sampling and wire output bytes are NOT natively qualified here; input
FIFO contents and the serial setup callback are test stand-ins in method tests.
Existing32-entry FIFO capacity, status/full/overflow fidelity and serializer
timing are unchanged and remain open; primary describes four-byte FIFOs.
Model2/Model3 users share this API but are not natively qualified by these tests.
No whole sound, hardware waveform, gameplay or working-driver claim.

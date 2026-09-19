# Native-qualified12-bit loop counter:280c40e1

Source280c40e1dd77c04812f938c802c49f95dc3abff4, build35366921336,
export35367861840; binary SHA256
103e82860b5704d7ec19ad02ff49ea121d79021e1d23e547f3beba9b5e7fec36.
Consumer revision ace9bc84; complete legal-port consumer exit0. Before/after
source/binary provenance and BIOS hashes pass. Full63-script local/CI batches
pass; three optional live scripts skip locally, then execute in this consumer.

320 loop-count programs/four configurations pass. Actual scheduled file replay
restores an active4096-iteration LPS loop and its complete64-word output ring.
Observation during execution uses only PPAF EX/PC; no data-port access while EX=1.
Both setup and output inspection occur with DSP stopped. File header/payload
validation passes in the shared runner. PPAF phase selection uses existing MAME
PC+1 readback, not hardware-prefetch proof.

All256 multiplier and844 arithmetic programs/four configurations, actual48-bit
ALU/latched-V file replay, and every previous DMA/count/loader/slot/device/save/
BIOS-background gate pass. Raw DSP output retained. First native pass used an
active-RAM instrumentation probe; it is superseded by this full legal-port run.

No working flags promoted or full DSP/hardware/gameplay completion claimed.
Loop-zero terminal state, repeated-instruction latch/timing, writes inside a
repeat, parallel bus conflicts and the other documented parent gaps remain open.

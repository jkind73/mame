# DSP-01 / DSP-03: wrapped delayed control flow (candidate)

`scudsp-delay-slot.patch` is prepared, NOT APPLIED while production b5caa488
undergoes native qualification. It separates delay-slot validity from its 8-bit
address. Existing code uses address 0 as the no-slot sentinel; branches at FF
therefore drop the prefetched instruction at 00. The candidate records validity
for JMP/MVI-PC/BTM/LPS, consumes it exactly once, saves it and clears it on reset.
It preserves the current address-based fetch model, not a new full pipeline.

Primary: ST-097-R5-072694, SDK 0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73,
PDF blob ffa8932249634ebd98947dad123621cebe3f24fa. Printed p.77/PDF p.93 has PC(8)
and 256-word program RAM; p.90/PDF p.106 depicts executing the prefetched command;
pp.154-155/PDF pp.170-171 describe BTM and LPS (next step LOP+1 executions).
Ymir 6d779960127ced72087a418c1daefc637d0aaa80 SCUDSP uses separate nextInstr and
8-bit PC rather than treating address zero as invalid. No reference code copied.

393,216 extracted actual-fetch/control-method cases pass on the candidate:
every PC/target pair, unconditional and taken/untaken conditional jump, MVI-PC,
BTM and LPS, plus registered-state replay and reset. Three compiled mutants fail
assertions: old zero sentinel, missing save registration, missing reset clear.
The existing 768-case DSP DMA suite also passes on the candidate. Full-TU C++20
syntax passes with the real headers. These are not native candidate acceptance.

Historical 234c native negative: six nonwrapping cases pass; wrapping untaken
conditional passes; five wrapping taken-control cases fail. JMP/MVI/BTM omit
the 00-slot write; LPS emits one write instead of three. Setup uses real DSP
instructions via mapped SCU ports, never private DSP register writes.
The user-provided ZIP and binary hashes were rechecked before execution:
ZIP 7129a6434f59db271254f515c3f1a9fef7d00d862c9347f8f44f563c76c966f8;
binary 7508e813a6b93bd4f9650dd5f4a0cfcf73b84d128008a89bc3a8c678365c5062.
This historical negative does NOT match the current production source trees.

Runtime parser: 12 controls pass. Native positive, real pending-slot save/load,
full prefetch timing and DSP program-memory DMA remain open. The candidate must
be integrated only after b5caa488's existing DMA native gates are qualified.

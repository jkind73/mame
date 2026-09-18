# SND-03 SCSP DMA self-target safety — native WIP

A memory-to-register DMA could write its own DEXE bit, recursively entering the
host transfer routine. Even without DEXE, restoring only the visible register
copies left cached DMEA/DRGA/DDIR corrupted, breaking the next transfer.

ST-077-R2-052594 p.101/PDF114 explicitly prohibits DMA access to its control
registers and guarantees no behavior. Primary SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73,
PDF blob9383eb13fe65c807e3ec48f32e284b9999cd71b8. The former source comment
incorrectly described this as unspecified without mentioning the prohibition.

Chosen emulator safety policy: ignore DMA writes to412/414/416 while still
reading the source and advancing both addresses. Programmed parameters remain
intact and following writable registers still receive their words. Remove the
incomplete post-transfer register restoration. No new state, recursion flag,
timer or transfer scheduling change. This is NOT a claim about forbidden
hardware behavior, nor an established cause of the reported Agent1 host crash.
Ordinary transfers and register-to-memory reads retain their existing semantics.

74 actual-method cases cover non-recursive self-execution, cached-parameter
reuse, both gates/directions, zero/2/32/128-byte lengths, memory-address wrap,
completion IRQs and gated MIDI input reads (which must still consume data).
A test-only depth assertion rejects old recursion before host stack exhaustion.
Previous2176 MIDI and966656 IRQ-port cases pass. Seventeen compiled mutants
fail behavioral assertions;28 parser controls and full-TU syntax pass.

Native fixture exercises both SH-2/68000 maps. Its default safe mode never
submits DEXE in a payload. Old2f54b074 (binary SHA256
701c7b775cb271c68e6b5900acd8622073be0395418514fc51225a62f9d35930)
passes all32 ordinary transfer cases and fails8 cached-parameter reuse cases.
The old recursive behavior is tested ONLY under the extracted depth guard.
SCSP_DMA_SELF_EXECUTE=1 adds executable payloads for48 cases; the full consumer
opts in only after verifying the fixed artifact against current production.
Matching build,192 native cases/four profiles and preceding gates pending.

The self-target cases qualify host robustness only. Timer/serial stand-ins in
the extracted harness are not timing proof. Memory wrapping is an existing
emulator control, not primary acceptance of out-of-range transfers. Shared-bus
arbitration, CPU stalls, timed/in-flight DMA saves, waveforms and whole sound
remain open. No working-driver flags change.

An actual-file parameter replay is also required. After a safe non-executing
self-target transfer, save, re-use DMEA/DRGA with only a new DEXE command,
poison DMA addresses/RAM/coefficient/timer control, load, and repeat. Both
restored observations and the independent transfer must match. Old2f54b074
fails four expected observations (cached-address reuse and untouched coefficient,
before and after load); save/restore equality and mutation controls remain
intact.14 replay-parser controls pass. Rebuilt replay pending. This is a
completed-transfer parameter save, not an in-flight DMA timing qualification.

A separate fixed-point control reuses the method harness with payload DMEA8000,
DRGA412 and DEXE1008: the old core reissues the identical DMA recursively,
rather than merely nesting into another destination. Its test-only depth guard
stops the first nested call. The fixed core passes the same guarded stimulus.
Both logs and `test_scsp_dma_recursion.py` are preserved; this control is never
submitted to an old native executable. It does not identify the user's crash.

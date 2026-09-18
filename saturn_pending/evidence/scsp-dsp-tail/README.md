# SND-04: full SCSP microprogram execution — integrated, native WIP

ST-077-R2-052594, technical data (printed11/PDF23), specifies128 DSP steps per
sample. SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73, PDF blob
9383eb13fe65c807e3ec48f32e284b9999cd71b8. A zero instruction is not inert:
it updates the MAC/input latches and services an outstanding memory request.
The old LastStep optimization predates the persistent register/read pipeline;
it also ignores live writes beyond the remembered endpoint until another Start.

Read-only cross-checks (no source copied):
- Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 scsp.inc, blob
  79ac3c31102f740b0faf432de696062f25e90485, runs all128 steps.
- Ymir6d779960127ced72087a418c1daefc637d0aaa80 scsp_dsp.cpp, blob
  b59a80874929dd3f7ee310fe8c63723863eaecc2, updates its program length on
  each write and retains an extra zero instruction expressly for side effects.
  It does NOT always run all128 instruction bodies; that distinction is retained.

Production Step now visits all128 entries. LastStep remains saved bookkeeping,
not an execution bound. Existing start gating, per-sample atomic scheduling,
MAC arithmetic, memory pipeline and mixer ordering are otherwise unchanged.
This is not complete SCSP timing, sound-memory arbitration or waveform accuracy.

6531 actual complete-method UBSan cases plus a stopped control pass: all-zero
programs, signed MAC/EFREG continuity, pending raw reads, nonzero instructions
at every odd step3–127 and live extension to127 without Start. Five compiled
mutants fail (old bound, padded stale bound, missing127, reset ACC, cleared EFREG).

Qualified9b596f90 executes31 mapped-register programs:10 PASS/21 FAIL. All30
memory-read controls, zero-input and full-length controls, initialization and
unwritten-effect persistence pass.20 zero-tail effects retain an incorrect
nonzero accumulator; one later instruction is ignored. TEMP is initialized
through guest microinstructions; no private SCSP DSP state is injected. The
SH-2s and sound CPU are parked only to exclude BIOS interference. Output is
checked via MEMS/EFREG, not claimed as audible/hardware-capture qualification.

The default suite grows69→70 with one generic SCSP DSP method suite, not a new
parent ID.14 parser controls pass. Full70-script local/CI and rebuilt native
acceptance (124 programs/four configurations, all preceding gates retained)
are pending. Full DSP file replay/audio continuity, hardware phase/arbitration
and game-performance qualification remain open; no SND parent is closed.

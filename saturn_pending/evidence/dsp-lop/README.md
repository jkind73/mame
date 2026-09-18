# Integrated12-bit loop-counter correction — native WIP

The shared LOP destination setter now masks to0xfff in production. The actual
method harness is in the default suite at regtests/saturn/test_scudsp_lop.py.
It passes991,232 cases under UBSan. Latest qualified25f13c07 repeats the42-pass/
38-fail native count negative; scheduled active-loop file replay also completes
but emits65536 rather than4096 iterations both before and after load. All128
final output-ring words disagree; active/save/mutation/load sequencing succeeds.
New consumer requires320 loop programs/four configurations and actual active
4096-iteration file replay, in addition to every prior accepted gate.
Candidate native positive/full build/full63-script batch remain pending.
Earlier external-candidate notes below are historical.

# DSP-01 next candidate:12-bit loop-counter input (not integrated yet)

Primary ST-097 printed78/PDF94 calls LOP12-bit; source header already agrees.
The shared destination setter currently retains16 bits instead. Pinned Ymir
6d779960127ced72087a418c1daefc637d0aaa80, scu_dsp.hpp WriteD1Bus/WriteImm,
and Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 scu_dsp_gen.c, mask12 bits.
No reference implementation code copied. Writes during an active repeat may have
additional rules (Beetle has looped-instruction handling); those are not this
candidate and remain open.

Verified arithmetic-qualified ea9a7a7c:42 controls pass/38 iteration-count
failures across80 actual BTM/LPS programs. Every program halts, so this is not a
wait timeout. D1 memory/signed8 and MVI25/taken19/untaken19 paths are exercised.
No private register writes; full result count is observed in RAM.

A one-line external candidate masks the setter to0xfff; production is NOT yet
modified while25f13c07 native qualification completes. Complete actual ALU,
source/destination/MVI/condition/loop methods pass991,232 width/conditional and
full-countdown checks under UBSan on that candidate; old source fails. Harness
is pending-only so it does not contaminate the current artifact input trees.
Move it into the default suite with the production fix after qualification.
No native candidate positive, exact loop timing or full loop semantics claimed.

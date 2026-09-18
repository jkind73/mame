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


Three targeted mutants fail:11-bit truncation,13-bit truncation and bypassing
the mask on MVI writes. Full63-script local batch and CI35366921336 passed; native candidate acceptance remains pending.

Important remaining loop semantics: Ymir's IncrementPC/Cmd_Special_Loop wraps
LOP from0 tofff when completing a loop; current MAME leaves it at0. The manual
printed83 says BTM does nothing at0. The extracted final-zero check preserves
current MAME behavior, not proof resolving this primary/reference disagreement.
Ymir also has an explicit looping latch rather than refetching LPS for each body
execution. This width fix does not resolve that execution/timing model or
Beetle's special LOP-write behavior inside looped instructions. No full loop
parent acceptance should be inferred from corrected iteration totals.


First280c40e1 native consumer passed all320 loop programs and all older gates,
but subsequent primary review caught a fixture restriction: ST-097 printed53–54
prohibits data-port access while EX=1. Replaced the active-loop RAM probe with
control-port EX/PC observation and explicitly stopped DSP before setup RAM writes
(including the ALU save fixture). Runtime execution semantics did not change.
The stronger fixture is rerun through the entire consumer before acceptance;
its14 parser controls also enforce observation/save/mutation/load ordering.

The initial control-phase probe mistakenly compared raw internal PC4 against
PPAF, whose existing readback adds1. Corrected to public value5 and repeated the
old-source run: full save/mutation/load completed with128 output-word mismatches
(65536 rather than4096 iterations), no phase failure. The phase test is a MAME
public-port observation, not proof of physical prefetch timing.

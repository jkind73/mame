# DSP-02 / DSP-03: count-source selector implementation (NATIVE WIP)

ST-097-R5-072694 pp.135–136 describes the count source as bits0–2: two
RAM-bank bits and MCx post-increment. Bit3 is not part of that selector. Source:
SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73, PDF blob
ffa8932249634ebd98947dad123621cebe3f24fa (reviewed in the prior DMA audit).
Pinned Ymir6d779960127ced72087a418c1daefc637d0aaa80 and
Beetle/Mednafen1382b85dcad2e98ef9a67426a775ba548eaf0c68 likewise select the
bank and increment from these three bits. No reference code is copied.

Previous production passes opcode&0xf to get_source_mem_value; selectors8–15
return zero without fetching RAM or incrementing its cursor. The candidate
changes this one call to opcode&7 and updates the existing width mutant's
matching expression. It does not change the common operand helper or other
instruction formats. The portable patch is retained in Git history; do not reapply it.

Real cd074b71 tests:16 canonical controls pass,16 unused-bit aliases fail.
Both transfer directions, hold modes, M1/MC1 and source positions0/63 are covered.
The following MOV M1,MC2 independently probes the counter-fetch cursor: the
aliased MC1 cases return3 instead of7, demonstrating the missing increment as
well as wrong transfer length. All writes use mapped SCU ports.

The old executable was recovered after the sandbox lost external runtime files.
The ZIP was validated against its original Actions digest. The normal verifier
correctly rejects it against current HEAD. For this explicitly historical
negative, the unchanged verifier function instead checks its immutable cd074b71
input trees, successful source run and previously accepted executable SHA256.
`historical-artifact.json` records that scope. This is NOT new-source acceptance.

The extracted gate compiles actual op_dma AND get_source_mem_value, rather than
stubbing the fetched counter. Candidate:131,072 unused-bit/bank/MC/CT-wrap/
direction/hold/same-bank cases, five registered-state replay cuts each, pass.
Production fails the size assertion. Three correctly targeted compiled mutants
(selector, increment bit, CT wrap) fail. An initial mutation accidentally hit an
unrelated earlier opcode mask and passed; it was corrected to match the count
fetch expression exactly before recording these rejection logs. Full-TU C++20
syntax and12 parser controls pass separately.

Integrated after f1a65715 passed the full native counter/save/integration gate.
New-source native positive is pending. The full counter width/zero tests,
loader/save gates, bus timing and broader hardware parents are not replaced by
this source-selector gate. Shared-bus timing and actual save-manager acceptance
are not inferred from extracted endpoint replay.


New f1a65715 negative independently repeats16 passes/16 failures after count width
and zero encoding are fixed. Aliased reads now transfer256 instead of3 words,
and MC1 still fails to increment. This is preserved separately from cd074b71.
The extracted gate is now `regtests/saturn/test_scudsp_count_operand.py`; the
expanded native consumer requires128 operand programs across four configurations.

Integrated8881caa1 full local60-script batch passed (exit0), excluding three
optional live skips; log: `local/regressions.log`. Build35356222037 also passed
its native build and60-script CI batch. Expanded native consumption is next.

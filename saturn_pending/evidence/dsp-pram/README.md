# DSP-02 / DSP-03: program-RAM DMA loader implementation (NATIVE WIP)

The previous op_dma masks the destination to two bits: PRG selector 4 becomes
MD0, so the nominal program-RAM branch is unreachable. That branch also contains
a fatal-error stub. The implementation decodes the selector, writes program RAM
through an independently saved 8-bit cursor, allows the following MVI-to-PC to
supply the load address before stalling, then returns to TOP and discards the old
pending slot at completion. It does not import reference source code.

Primary: Sega ST-097-R5-072694, SDK commit
0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73, PDF blob
ffa8932249634ebd98947dad123621cebe3f24fa. Printed p.89/PDF p.105 gives the
MVI RA0; DMA D0,PRG; MVI PC loader sequence. Printed p.135/PDF p.151 identifies
PRG and the third destination selector bit. The manuals do not fully specify
all observable pipeline/serialization timing used below.

Cross-check: Beetle/Mednafen commit 1382b85dcad2e98ef9a67426a775ba548eaf0c68,
mednafen/ss/scu.inc, hardware notes at lines63-69 and DSP_FinishPRAMDMA describe
delayed first write using PC, completion returning to TOP and flushing prefetch,
and MVI-PC serialization. Its immediate buffered implementation is NOT copied.
Pinned Ymir 6d779960127ced72087a418c1daefc637d0aaa80 also distinguishes program
RAM and completion PC/TOP handling but has explicit timing hacks; not an oracle.

Scope is ONLY the documented MVI-PC serialized loader path. Deferred MVI RA0/WA0,
END/ENDI serialization, un-serialized self-modification, zero/large counts, exact
bus grants and prefetch timing are NOT complete. The candidate must not be called
full DSP program-RAM DMA support. Integrated after ca63041f passed its complete expanded native gate. The portable
patch is retained in Git history; do not reapply it. New production native
qualification remains pending.

Extracted actual-method checks pass: 4,096 program-target/wrap/count/hold/count-form
cases, five state-copy replay cuts each, existing 2,048 read-mirror cases, 768 DMA
cases and 393,216 control-flow cases. Five compiled mutants fail: selector alias,
early stall, missing saved cursor, wrong resume PC, missing pending-slot flush.
Full-TU C++20 syntax passes. None of this is actual save-manager qualification.

Real 89764c08 negative: all 32 host-mapped loader programs finish but put raw
instruction words in data RAM instead of executing the overlay. Cases cover
inline/out-of-line destinations and FF->00 load wrap, both count forms and hold
modes. No private DSP state is patched. A native positive for the candidate does
not exist yet. The runtime fixture does not prove exact bus timing or commercial
game operation. Twelve result-parser controls pass separately.

A real scheduled save/load negative now covers a busy 192-word program transfer
starting at slot 200 and wrapping through 00. The DSP program address space is
read only, first checked against mapped host-port uploads. Captured instruction
RAM is checked immediately after load, then the complete expected 256-slot image
is checked after DMA. All save/mutate/load notifications complete on 89764c08,
but the first program word is never written and all 192 transferred words are
wrong after both original completion and replay. This is a missing-feature
negative, not new-source acceptance. Thirteen save-parser controls and the shared
runner's seventeen file/output controls pass separately.

Integrated cd074b71 full local batch: 58 scripts passed, excluding the three
optional missing-default-binary live skips. Log: `local/regressions.log`.
Native build 35344168780 is still running; candidate acceptance is not inferred.

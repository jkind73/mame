# DSP-01 parallel data buses — integrated, native WIP

Production op_alu now keeps the instruction-entry CT addresses through X, Y and
D1, collects increment requests, and commits each bank once after D1. Explicit
CT destinations override the collected increment. A D1 RAM copy within the same
bank is a no-op, without a D1 increment; a bank being read cannot also accept a
D1 RAM write. Source increments for a different bank still occur when its D1
write is blocked. DMA count fetches and standalone MVI transfers are unchanged.
No additional saved state: the pending mask exists only inside one instruction.

## Reference contract and disagreements

Primary Sega ST-097-R5-072694, SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73,
PDF blobffa8932249634ebd98947dad123621cebe3f24fa: printed91/PDF107 permits
concurrent ALU/X/Y/D1 operations; printed107–119 describes source selection and
MC post-increments. It does not explicitly specify all read/write collisions.

Pinned Ymir6d779960127ced72087a418c1daefc637d0aaa80, scu_dsp.hpp ReadSource /
WriteD1Bus and scu_dsp.cpp Cmd_Operation, defers/merges increments and gives CT
writes precedence. Pinned Beetle/Mednafen1382b85dcad2e98ef9a67426a775ba548eaf0c68,
mednafen/ss/scu_dsp_gen.c, independently agrees, including same-bank D1 no-ops
and read-bank write suppression. No implementation code copied from either.
MAME's own2005 comment says counters update once after the DSP operation, but
its implementation committed X/Y before D1, violating that intended behavior.

Two remaining disagreements are explicit, not silently treated as hardware proof:
- X/P versus D1 register-destination priority stays MAME/Beetle-compatible (D1
  wins), unlike Ymir's suppression. This change does not alter that priority.
- On immediate D1 writes colliding with a RAM read, Ymir additionally clears the
  addressed CT's low bit before incrementing. This undocumented extra effect is
  NOT adopted. The implementation follows the normal MC increment contract and
  Beetle's merged increment, while suppressing the RAM write (both agree there).
  Immediate-collision counter tests are this selected policy, not independent
  evidence resolving the hardware disagreement. This remains open under DSP-01.

## Evidence and acceptance

Qualified280c40e1 native binary:144 guest programs give36 controls/108 failures.
All144 multiplier observations still match, independently checking input setup.
Failures expose stale/new-address disagreement, double increment, same-bank copy
corruption and read/write collisions. Tests inspect all256 RAM words, follow each
bank's next CT with marker writes, and separately observe P+A and RX*RY. All host
RAM access occurs with DSP stopped. Old source and negative output are retained.

Actual complete ALU/source/destination methods pass729,000 memory/register/CT
transitions under UBSan after the change. All four banks, wrap boundaries, X/P
and Y/A fanout, D1 source/destination combinations and explicit CT writes are
covered. Before-source tests fail. Existing80,968 ALU,34,816 multiplier and
991,232 loop cases pass, plus full-TU syntax and13 parser/runner controls.
Full batch/build/new-source native acceptance pending; consumer adds576 programs
across four configurations without dropping earlier gates. No complete DSP,
exact timing, shared grants, hardware-collision proof or working flags claimed.


Five targeted mutants fail: early CT commit, multiple increments, lost CT-write
precedence, read-bank write acceptance and same-bank D1 increment. A real active
4096-iteration parallel-copy file replay also reproduces the old error: all
save/mutation/load phases succeed, but63 of64 destination words and both product
observations disagree both before and after load (130 failures). It uses legal
PPAF-only phase observation, stopped RAM access, and poisons source/destination
RAM, counters, LOP, input/product registers and program before restoring.
The expanded consumer requires this scheduled replay too;14 save-parser controls
pass separately. Full64-script local batch and CI35369703506 are running.

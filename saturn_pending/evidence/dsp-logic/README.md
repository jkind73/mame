# DSP-01: negative-OR Z correction prototype (NOT INTEGRATED)

ST-097 printed95/PDF111 explicitly specifies OR Z=1 only for a zero result,
S=1 for a negative result and C=0. Pinned Ymir6d779960127ced72087a418c1daefc637d0aaa80
ALU_OR and Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 GeneralInstr OR/CalcZS32
both implement that rule. Reference source inspected only; no code copied.

Production still forces Z=1 for negative OR results under an old comment naming
Croc/early Psygnosis titles. That comment supplies no hardware measurement or
reproducer. Removing the workaround follows the explicit primary contract and
both references, but no Croc/Psygnosis media is available here to qualify their
compatibility or establish the original reason for the workaround. Do not claim
those games are tested/fixed. The candidate is preserved separately until the
ALU-forwarding change completes its native consumer.

../../scudsp-logic.patch removes that override and expands the EXISTING ALU
model/native suite rather than adding a new parent or default test script.
All defined flag-changing ALU operations are covered: AND/OR/XOR, ADD/SUB/AD2,
SR/RR/SL/RL/RL8. The external candidate passes222662 actual-method UBSan cases,
including sticky-V and debugger/host-read controls. Current source fails.

The expanded438-program native fixture on qualified f944ce85 passes390 and
fails48 negative-OR programs. Those produce96 flag/read-clear mismatches; ALL
result observations and the other arithmetic/logic/rotate controls pass.
Same-cycle result latching corrections are retained. Candidate native positive
has NOT run; no gameplay or full hardware completion claim.

Promotion must also update parser/consumer counts and the host-flags fixture:
its old negative-OR preset deliberately expected the legacy impossible S=Z=1
combination. The corrected negative-OR preset must expect S=1,Z=0 while retaining
all full/halfword/byte write-protection checks. Ordinary S/Z read-only logic is
not to be relaxed. Existing69-script total remains unchanged by this expansion.

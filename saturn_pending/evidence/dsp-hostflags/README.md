# Read-only S/Z correction — NATIVE QUALIFIED

The mask correction is now in production, following complete C-bus native
qualification of f1fe8e09. The default suite includes28672 actual-method UBSan
cases in regtests/saturn/test_scudsp_hostflags.py. Full-TU C++20 syntax passes.
The expanded native consumer requires448 host-flag programs/four configurations,
plus every earlier gate. Source dacd1f99 passes build35373461692/export35374507751, full67-script
local/CI batches and the COMPLETE expanded native consumer:448 host-flag
programs/four configurations, every preceding runtime/save gate, and both
source/binary/BIOS provenance checks. Evidence: ../dacd1f99-live/.
Earlier external-prototype notes below are historical; do not reapply the patch.

# DSP-01 / DSP-03: read-only S/Z prototype; legal conditional-branch setup

The production control-port mask incorrectly accepts host writes to S/Z. Sega
ST-097 printed51 (PDF67) labels S/Z/C/V read-only. Pinned Ymir
6d779960127ced72087a418c1daefc637d0aaa80 scu.cpp PPAF handlers (e.g.2121+) and
Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 scu.inc case0x80 (e.g.719+) do
not write arithmetic flags. References read only, no implementation copied.

External candidate ../../scudsp-hostflags.patch changes only the writable mask
from00630000 to00030000. NOT applied to production yet. Actual method passes
28,672 masked transitions under UBSan; production fails. Native qualified
ff717b2e completes112 full/halfword/byte cases:76 pass,36 read-only violations;
all guest-generated flag controls pass. Existing negative-OR Z behavior is a
compatibility control, not newly hardware-qualified.14 parser controls pass
without running an emulator. No candidate native positive exists yet.

FIXTURE CORRECTION: the existing pipeline fixture injected Z through a PPAF
write, contrary to the primary read-only definition. That setup depended on
the production defect. The corrected fixture generates Z with guest ALU
instructions in a prologue and jumps to each tested opcode with an inert slot.
It additionally checks a target marker to distinguish a taken conditional
branch from fall-through. All12 programs pass on qualified ff717b2e using this
legal setup. This replaces the earlier conditional-flag qualification; it is
not grounds for retracting the independently observed unconditional wrap fix.
The updated fixture remains the existing DSP pipeline gate, not a new test ID.

Pause/resume and single-step control, active LE writes, exact PC/prefetch
reporting and debugger synchronization remain open. This narrowly scoped mask
change does NOT implement those controls. Program-control writes still use
the existing execute/reset interface; no timing or broad parent closure claim.

# ALU entry-A forwarding — NATIVE QUALIFIED

The preserved prototype has been applied after complete pause qualification.
The147456-case actual-method test is in the default suite. Existing ALU,
parallel and multiplier oracles now use explicit entry A and result latching;
all targeted DSP suites and full-TU C++20 syntax pass. Source f8022878 passes full69-script local/CI batches, build35378445239/
export35379200969 and the complete expanded native consumer:768 dataflow
programs/four configurations, revised accumulator/V file replay, preceding gates
and before/after provenance/BIOS checks. Evidence: ../f8022878-live/.
The older pending-slot fixture's active data-port reads were subsequently
corrected using EP/PR; its isolated rerun passes on this same binary. The full
consumer's old raw output is preserved; see ../dsp-pipeline/README.md.

Corrected fixtures on qualified f944ce85:211 ALU,64 multiplier,144 parallel
programs and actual active parallel-copy replay PASS. The revised ALU save
fixture completes all phases and has exactly one old-binary failure: after
loading A=1 and adding1, its poisoned result incorrectly retains8000 in the
high half instead of zero. Original/restored48-bit accumulator and V controls
still pass. Nothing is removed from the result/flag/save assertions.
Earlier prototype notes below are historical; do not reapply the patch.

## Historical prototype evidence (before f8022878)

The preceding production ALU retained a prior result on NOP and retains that prior result's
upper16 bits for32-bit operations. Both pinned implementations instead begin
each operation from entry-state A: NOP bypasses A,32-bit operations replace its
low32 bits, and AD2 replaces all48 bits. Y writes occur after that evaluation.

References, read only (no source copied):
- Sega ST-097 pp.77–79: block diagram and separate ACH/ACL input registers;
  p.91 concurrent operations; p.93 NOP has no ALU command/flag change. The manual
  does not explicitly spell out every bypass/high-bit consequence here.
- Ymir6d779960127ced72087a418c1daefc637d0aaa80 scu_dsp.cpp Cmd_Operation starts
  ALU from AC before its switch and subsequent X/Y/D1 transfers.
- Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 scu_dsp_gen.c GeneralInstr_BODY
  starts its local48-bit ALU output from AC before dispatch and bus writes.
  GPL source inspected, not copied.

External candidate ../../scudsp-alu-flow.patch initializes the ALU output from
entry A before the existing decoder. No saved fields or arithmetic formulas
change. OR's historical negative-Z workaround is deliberately NOT changed;
Croc/Psygnosis compatibility and exact timings are not established here.

147456 actual-method UBSan cases cover all12 defined operations, independent
48-bit A/P/prior-ALU values, Y idle/clear/latch and following NOP. Candidate
passes; current source fails. Three mutants fail (missing bypass, stale high
bits, evaluating bypass after Y).14 parser controls pass separately.

Qualified dacd1f99 native JP/interpreter completes192 public-port programs:
58 PASS /134 FAIL; all16 AD2 controls pass. Programs construct a previous wide
ALU value with multiplication, replace A, then capture the operation result
on its own instruction and latch A for the next high-word observation. This
reproduces stale NOP output and unrelated upper16 bits without private DSP writes.
No candidate native positive existed at prototype capture; qualification is recorded above.

IMPORTANT FIXTURE CORRECTION FOR INTEGRATION: existing ALU/multiplier/parallel
fixtures sometimes read a previous result using later NOP instructions without
latching it into A. Their success depends on the old output-retention behavior.
They must capture/latch results explicitly, preserving all result, flag, RAM,
product-ordering and save/load assertions. The ALU save fixture's poisoned high
half must follow the newly loaded A, not the old ALU cache. Earlier arithmetic
formula fixes remain, but old tests do not establish hardware-correct output
lifetime/high-half behavior. Requalify the complete native consumer after these
corrections. No parent or overall hardware completion is claimed.

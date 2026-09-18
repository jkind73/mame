# SND-04 MEMS operand/write ordering — native WIP

Remove the IWT-to-INPUTS bypass: an instruction captures INPUTS before its
MEMS write, including IRA==IWA. Subsequent instructions observe the new MEMS.
This also prevents bypassing the captured operand's 24-bit sign extension.
The correction changes neither read-service latency nor write scheduling.

Read-only implementation cross-checks, no external source copied:
- Ymir6d779960127ced72087a418c1daefc637d0aaa80, DSP header
  blob8c9e0c0230c4e3dba840c2ed0059011e3e56fcfe, captures INPUTS and its
  consumers before IWT writes soundMem (lines60–74,127–129).
- Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68, scsp.inc
  blob79ac3c31102f740b0faf432de696062f25e90485: INPUTS read precedes IWT;
  no same-address bypass.
- MiSTer a95b085038ace57fa621558d60a7adc7a3c53f78, SCSP.sv
  blob402dcb6eedca98547c34a799fea3dc56eddbca5a: MEMS address uses MPRO0,
  captured MEMS_Q/operand uses MPRO1, IWT writes on CYCLE1 after CYCLE0 read.
Primary ST-077 documents the DSP register architecture but is not claimed to
explicitly specify this microinstruction collision. Hardware capture is absent.

73728 new actual-method UBSan cases cross all32 IRA/IWA pairs, six boundary
operands, six incoming values and IWT on/off. They check current MAC, YRL,
ADRL, committed MEMS and next-instruction MAC. Previous69632 address and6531
zero-tail cases/stopped control pass. Eleven compiled mutants fail behavioral
assertions, including both raw and correctly sign-extended bypass mutants.
Full-TU syntax and14 output-parser/14 save-parser controls pass.

512 mapped programs cover all32 destination registers, matching/nonmatching
IRA, IWT on/off and four signed operand pairs. Each sample re-seeds the old
operand through a guest MRD/IWT sequence, then exposes current/subsequent MAC
results via EFREG and commits via MEMS. No private DSP state injection.
Qualified source66e351f7 (binary805d46ff2b630843f28ec1d703f35626c2d4c4e80f954160acdca33cafb9573b)
passes631/fails128 of759 programs: all previous247 pass, and only enabled
same-address current-operand checks fail. Subsequent operands and committed
memory controls pass. Raw evidence included.

Full70-script local regression batch PASS for production35f5d58b.
Build35393858442 is queued after the prior documentation-triggered build;
matching3036-program/four-profile acceptance and preceding runtime/save
gates are pending. This is not complete sound timing/arbitration, waveform or
whole-driver acceptance. Signed addresses and full128 execution remain intact.

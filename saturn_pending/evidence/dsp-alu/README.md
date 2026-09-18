# DSP-01: ADD/SUB/AD2/SR arithmetic correction (NATIVE WIP)

ADD/SUB now retain a wide result for carry/borrow instead of testing sign-extended
bit32 of a narrowed result. The signed32-bit additions/subtractions no longer
invoke C++ signed-overflow UB. SUB overflow compares the result against ACL.
AD2 adds unsigned48-bit operands, extracts bit48 carry, then retains48 result bits.
SR reports input bit0 in C. Overflow latches until the existing host read clears it.
The OR-negative-Z game workaround and other opcode behavior are unchanged.

Primary/reference basis and its contradictions were recorded before implementation
in `../dsp-count-operand/alu-followup.md`. ST-097 printed100 explicitly specifies
SR bit0; printed51 defines read-to-clear V. Instruction pages97–99 contain the
48-bit ADD wording and otherwise-zero V statements. Sticky overflow and32-bit
ADD overflow therefore also rely on convergent pinned Ymir/Mednafen behavior,
not a claim of unambiguous manual text or a new hardware measurement. No reference
implementation code copied.

The test compiles complete actual op_alu and program_control_r methods with
UBSan; ALU-only opcodes have zero bus fields and asserting bus stubs. An independent
mathematical oracle covers80,968 boundary/random cases, both initial V states,
32/48-bit operand boundaries, upper-ALU preservation and debugger/ordinary host
read semantics. Old source fails flags; a separate old-source ADD probe reports
signed integer overflow (2147483647+1). Corrected source passes both. This is not
native device or real save-manager evidence.

The mapped native fixture contains203 arithmetic/flag/read-clear programs and
reads PPAF only after a bounded10us execution wait, never polling away overflow.
AD2 native operands are sign-extended32-bit words, not arbitrary48-bit boundaries.
The next full native gate requires812 programs across four configurations.
Verified old8881caa1 passes85 and fails118 of203 programs: ADD17/64 pass,
SUB32/64, AD2 32/64, SR4/8, sticky V0/3. Result words all match; failures are
flags/read-clear expectations. Source/run/ZIP/executable were independently
verified against the immutable historical commit, not the modified worktree.
New-source native positives remain pending. Seven compiled mutants are rejected:
ADD carry, SUB overflow, AD2 carry/width, SR carry, V latch and signed ADD UB.

Full-TU syntax and existing DMA/count/operand/pipeline suites pass. No complete
ALU/DSP parent closure, commercial-gameplay acceptance or working-flag promotion.


Expanded native boundary coverage: multiplier-built48-bit P operands add eight
AD2 cases around +2^47/-2^47, including signed overflow/underflow. Both the low32
result and ALU bits16–47 are read through ordinary MOV instructions. Old8881caa1
passes five of these eight; total90 pass/121 fail of211, still zero result-word
mismatches. This validates the public-port setup independently of the flag fix.
The new native gate requires844 arithmetic programs across four configurations.

An actual scheduled file save/mutate/load control also passes on8881caa1: create
a48-bit overflow, save without reading away V, read/clear flags and poison the
ALU/output, load, verify restored V/read-clear and full48-bit output, then poison
only output RAM and re-observe the restored ALU through MOVs. Shared runner
validates the real MAMESAVE file. This is prior-behavior save coverage, not an
old-source arithmetic negative or candidate acceptance. Thirteen save-parser
controls pass separately. The expanded native consumer requires this replay too.

Source ea9a7a7c passed the61-script full local batch (three optional live skips
excluded) and CI35363539017. Native new-source consumption remains pending.

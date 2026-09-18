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

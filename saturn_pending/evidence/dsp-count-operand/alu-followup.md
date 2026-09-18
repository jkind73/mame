# Historical planning note — superseded

The ADD/SUB/AD2/SR fixes described below are implemented and native-qualified in
ea9a7a7c, retained by25f13c07. See ../dsp-alu/README.md and ../ea9a7a7c-live/.
The original preimplementation findings below are retained as history only.

# DSP-01 follow-up identified during the counter rebuild (NOT IMPLEMENTED)

Do not infer ALU correctness from the DMA/control-flow gates. Inspection found
concrete arithmetic work in scudsp_cpu_device::op_alu:

- ADD computes an int32_t signed sum, potentially overflowing in C++, before
  inspecting bit32 for carry. That bit then reflects sign extension, not the
  original unsigned carry. SUB similarly inspects its already narrowed result.
- SUB's overflow expression compares the result sign with PL rather than ACL.
- AD2 sign-extends both48-bit operands into64 bits before addition; its bit48
  carry therefore needs a widened unsigned48-bit calculation, not sign extension.
- SR stores input bit31 in C. ST-097 printed100/PDF116 explicitly says bit0.
- SET_V currently clears V on a non-overflowing arithmetic operation. Both pinned
  comparison implementations instead latch overflow until the host reads it.

References recovered/read this session:
- Sega ST-097-R5-072694, SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73,
  blobffa8932249634ebd98947dad123621cebe3f24fa: printed51/PDF67 defines V
  reset by read; printed97–99/PDF113–115 defines ADD/SUB/AD2; printed100/PDF116
  specifies SR carry from bit0. Caveat: printed97 says ADD overflow exceeds48bits
  despite ACL/PL operands, and instruction pages say V is otherwise0. Do not
  present sticky V/32-bit ADD overflow as unambiguous primary wording.
- Ymir6d779960127ced72087a418c1daefc637d0aaa80,
  libs/ymir-core/include/ymir/hw/scu/scu_dsp.hpp, ALU_ADD/SUB/AD2/SR:
  widened unsigned arithmetic,32/48-bit carry/overflow, sticky overflow, SR bit0.
- Beetle/Mednafen1382b85dcad2e98ef9a67426a775ba548eaf0c68,
  mednafen/ss/scu_dsp_gen.c: independently agrees on those properties. Read-only
  comparison; no GPL code copied. Implement from the arithmetic contract.

Suggested next acceptance: actual host-uploaded arithmetic programs, read PPAF
only once after bounded execution (polling it clears V), compare result and
C/Z/S/V against mathematical boundary vectors, then check read-to-clear and
sticky-overflow sequences. Compile extracted actual methods with undefined-
behavior sanitizer. Include both32-bit and48-bit operand boundaries. These tests
and fixes do NOT exist yet; no native ALU negative or candidate positive claimed.

Preserve the existing OR-negative-Z game workaround pending its own reference/
software investigation. Do not change it incidentally, claim complete ALU or
close DSP-01 based on the planned subset.

Mapped fixture construction checked against current instruction decoding (not
executed yet): initialize CT0/CT1/CT2 with1c00/1d00/1e00; load ACL from M0 with
00060000 (00070000 for MC0), load PL from M1 with00003501, execute ALU selector
in bits29–26, copy ALU low word to MC2 with00003209, then END. Stage full32-bit
operands through host data ports. For sticky V, MC0 can load the first operand
and advance to a following zero operand for the second operation. A fixed10us
wait avoids accidentally clearing V by polling PPAF. Arbitrary48-bit boundaries
still require additional setup or extracted-method vectors; sign-extended32-bit
AD2 inputs alone do not cover48-bit signed overflow.

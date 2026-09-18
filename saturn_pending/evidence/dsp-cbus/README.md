# DSP-02 / DSP-03: C-bus write address prototype (NOT INTEGRATED)

Production ff717b2e retains legacy C-bus write strides. The external candidate
is preserved in ../../scudsp-cbus.patch, not applied to production yet.

Contract: Work RAM-H writes consume one aligned longword per transfer. Encoded
stride modes 0..7 advance the byte cursor by 0,2,4,8,16,32,64,128, independently
of immediate versus RAM-sourced counts. Mode1 therefore replaces pairs of
longwords. Keep its halfword phase in the existing saved byte cursor; preserve
HOLD and round the cumulative next WA0 to a longword boundary. B-bus and A-bus
rules are unchanged. No additional saved device fields are introduced.

References (read only; no emulator implementation source copied):
- Ymir 6d779960127ced72087a418c1daefc637d0aaa80, scu_dsp.cpp, Cmd_Special_DMA
  and RunDMA: outgoing byte stride, WRAM write alignment and one advance.
- Beetle/Mednafen 1382b85dcad2e98ef9a67426a775ba548eaf0c68, mednafen/ss/scu.inc,
  DMAInstr_BODY lines3984,4047–4054,4078–4079: same placement/stride and rounded
  final WAO. GPL code inspected, not copied.
- Sega ST-097 printed134/136/138/140 establishes B-bus halfword behavior, but
  does NOT establish these C-bus quirks. This is software-reference convergence,
  not a newly found primary hardware measurement.

IMPORTANT DISAGREEMENT: Ymir's final non-HOLD address differs from Beetle for
zero and larger strides. The prototype retains existing MAME/Beetle cumulative
update behavior, extending it to mode1 fractional phase. The native tests
qualify that selected contract, not resolution of this disagreement. The old
MAME comment about an additional 1KiB-boundary bug is not established by either
reviewed reference. Boundary cases here test the selected model, not all silicon
quirks. Shared grants, exact timing, whole-bus-boundary routing and A-bus rules
remain outside this change.

Evidence:
- 6,912 actual-method UBSan cases, each with five registered-state replay cuts,
  pass with the external candidate. Recording callbacks are not a native pass.
- Original source fails the same oracle. Four candidate mutants are rejected:
  unaligned writes, doubled stride, per-transfer rounding, lost saved half-phase.
- Qualified 2e14f275 native JP/interpreter: all512 public-port cases complete;
  212 PASS /300 FAIL. All512 source-counter observations match. Tests inspect
  full external images and guards, then use a second stopped-upload program to
  observe WA0; no private DSP register writes. Both SH-2s park away from the
  first RAM page, which the explicit 1MiB mirror-wrap cases overwrite.
- Actual scheduled save/mutate/load on that old binary completes all phases,
  but both completions have254 image mismatches and255 WA0-probe mismatches.
  Odd transfer count is identified through external RAM contents, not forbidden
  active DSP data-port reads. Candidate file replay has NOT run yet.
- 14 ordinary and15 save parser controls pass; these execute no emulator.

Native input binary SHA256:
a70a4c1663ec5c6366ce157172dfc57d8bbfa4b94d06fd42080f8aa9296f0223
Raw native output and ordinary invocation/BIOS/Lua hashes are adjacent. Old
native failures are validator failures, not reported emulator crashes. No
parent completion or working flags are claimed.

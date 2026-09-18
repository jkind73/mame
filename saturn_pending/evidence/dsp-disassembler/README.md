# Disassembler correction — NATIVE QUALIFIED

Separate MVI destinations and separated X/Y mnemonics are now in production.
The complete real-class337-case UBSan test is in the default suite as
regtests/saturn/test_scudsp_disassembler.py;13 debugger dump parser controls pass.
Native consumer adds a241-row real MAME debugger dump (JP/interpreter with the
headless debugger), not a replacement disassembler or CPU-state mutation.
Source ff717b2e: full65-script local/CI batch PASS (build35370828718).
Export35371877378 and the COMPLETE expanded native consumer PASS, including
all241 actual debugger rows and every previous runtime/save/provenance gate.
Binary SHA256: 4dbca0dcf8e093b011049a16c5eb1e2441025afa945905bad6298a40abb919ba.
Evidence: ../ff717b2e-live/.
Earlier external-candidate notes below are historical.

# DSP-01 disassembler candidate (not integrated yet)

ST-097 printed121/PDF137 explicitly lists MVI destinations MC0-3,RX,PL,RA0,
WA0,LOP,PC. D1 has TOP and CT0-3 instead. Current disassembler incorrectly
uses the D1 table for MVI: PC is printed as CT0 and reserved immediate targets
are printed as TOP/CT1-3. X/Y command strings also run together without spaces.
This is diagnostic output, not evidence of those wrong registers executing.

An external candidate separates the immediate-destination table and separates
parallel mnemonics. Complete real scudspdasm.cpp/header, util::disasm_interface
and formatter compile and link with actual MAME headers (no replacement decoder
or formatter).337 cases pass under UBSan; old source fails. Candidate patch is
stored at ../../scudsp-disassembler.patch, not applied to production while the
parallel-bus artifact is being qualified.

The real280c40e1 debugger (-debugger none, JP/interpreter) dumps241 synthetic
words uploaded through stopped DSP host ports. It passes57 rows/fails184:
10 MVI-destination and174 parallel-separation failures. Raw dump/log retained.
No private DSP register mutation and none of these synthetic words execute.
Candidate MAME build/native debugger positive remains pending. No CPU semantics,
step-over metadata, debugger/DRC synchronization or full parent closure claimed.

# Qualification update

25f13c07 is native-qualified: build35365374912/export35366355244, all256
multiplier programs/four configurations and the complete preceding native gate
pass. Full62-script local/CI batches pass. Both provenance checks pass. Complete
evidence: ../25f13c07-live/. WIP notes below are historical, not current status.

# DSP-01 multiplier input refresh — native WIP

The shared RX destination helper now marks the cached multiplier result dirty,
just as the existing X/Y-bus input paths do. D1 memory/register and signed8-bit
immediate writes, and taken25-/19-bit MVI writes, therefore refresh MUL at the
existing end-of-instruction point. P remains a separate register: a concurrent
MOV MUL,P sees the preceding operands. Untaken conditional MVI leaves RX intact.
No multiplier latency, bus-contention, DMA or counter-ordering changes claimed.

## References and implementation

Sega ST-097-R5-072694, SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73,
PDF blobffa8932249634ebd98947dad123621cebe3f24fa:
- Printed78/PDF94: RX/RY store multiplier inputs;32x32 produces low48 bits.
- Printed108/PDF124: MOV MUL,P transfers the multiplier result to PH/PL.
- Printed118–119/PDF134–135: signed8-bit immediate and source-register/RAM
  D1 transfers explicitly permit RX as destination. MVI also permits RX.

Pinned Ymir6d779960127ced72087a418c1daefc637d0aaa80,
libs/ymir-core/src/ymir/hw/scu/scu_dsp.cpp, X-bus MOV MUL,P computes from current
RX/RY before concurrent X/Y/D1 writes; its header WriteD1Bus/WriteImmediate
updates RX for these destinations. Pinned Beetle/Mednafen1382b85dcad2e98ef9a67426a775ba548eaf0c68,
mednafen/ss/scu_dsp_gen.c independently computes signed RX*RY for MOV MUL,P
before input writes. Read-only comparisons; no implementation code copied.
This fix keeps MAME's existing cache/order and invalidates it on the missed path.

## Evidence

Verified, fully arithmetic-qualified ea9a7a7c native binary SHA256
0a3c6e7a1fd2f0df9051c783c57fd3ebab6c69d74e398a1963ff49200b8756a7:
64 public-port programs give24 control passes/40 new-product failures. All64
old-P observations pass. X-bus and simultaneous X+D1 controls pass; untaken MVI
controls pass. D1 memory/immediate, unconditional/taken conditional MVI, and
concurrent P-read/D1-write cases retain stale products. Low32 and bits16–47
observe the entire48-bit result, including signed products. Bounded execution
and extra settling instructions avoid claiming exact hardware multiply latency.

The actual complete fetch/ALU/MVI/source/destination methods fail before the fix
and pass34,816 boundary/random/write-path/product-order cases after it under
UBSan. Non-exercised opcodes/device APIs are stubs, not native acceptance.
Full SCUDSP translation-unit syntax, existing80,968 ALU cases, shell syntax and
12 parser controls pass. New native consumer requires256 multiplier programs
across four configurations plus all accepted arithmetic and earlier gates.
CI35365374912 and the full62-script local batch passed; new-source native positive remains pending. No parent closed.


Reference caveat: simultaneous X-bus and D1 writes to RX have different priority
in Ymir (D1 suppressed) versus Beetle and current MAME (D1 wins). The eight such
programs are explicitly compatibility controls, not hardware-priority acceptance.
The production change does not alter this existing collision behavior. Primary
instruction concurrency text does not resolve that conflict here.

Three targeted mutants are rejected: suppressing the MVI refresh, clobbering P
while updating RX, and losing X-bus refresh. The removed destination refresh is
also rejected by the before-source run. No new-source native positive yet.


First new-source consumer attempt was rejected at the JP multiplier runner: all64
raw programs passed, but the ordinary fixture incorrectly delegated to the save
runner, requiring a nonexistent save file and lacking alternate-configuration
arguments. Corrected binding to the existing multi-configuration DSP runner; a
new parser/runner-contract control catches that mistake. Complete consumer must
be rerun; this was a fixture failure, not accepted native qualification.
